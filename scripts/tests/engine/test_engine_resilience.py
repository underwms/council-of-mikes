"""Failure injection at model, process and phase boundaries; no provider requests."""
import io
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from council.diagnostics import DiagnosticRuntimeError, describe
from council.graph import invoke_model
from council.state import CouncilState
from test_gemini_cli import settings
from test_engine_integration import lifecycle


OPERATIONS = [
    ('orchestrator', 'roadmap_inspection'), ('orchestrator', 'roadmap'),
    ('reviewer', 'roadmap_review'), ('orchestrator', 'planning_inspection'),
    ('orchestrator', 'planning'), ('reviewer', 'plan_review'),
    ('orchestrator', 'plan_revision_inspection'), ('orchestrator', 'plan_revision'),
    ('orchestrator', 'strategy_reset'), ('investigator', 'investigation'),
]


def state_for(settings):
    roles = {name: dict(provider='gemini-cli', model='gemini-2.5-pro', settings=settings)
             for name in ('orchestrator', 'investigator')}
    roles.update({name: dict(provider='codex-cli', model='gpt-6.1-sol', settings={
        'executable': 'C:/trusted/codex.exe', 'cli_version': '0.163.0', 'timeout_seconds': 600})
        for name in ('coder', 'reviewer')})
    return CouncilState(run_id='resilience', task_input='offline',
                        model_configuration={'version': 4, 'roles': roles})


@pytest.mark.parametrize('role,operation', OPERATIONS)
@pytest.mark.parametrize('code', ['CLI_TIMEOUT', 'CLI_EXECUTION_FAILED', 'CLI_IO_FAILED', 'CLI_START_FAILED'])
def test_read_only_calls_retry_one_transient_failure_and_keep_both_receipts(settings, monkeypatch, role, operation, code):
    monkeypatch.setattr('time.sleep', lambda _: None)
    state = state_for(settings)
    calls = []
    def invoke():
        calls.append(True)
        if len(calls) == 1:
            raise DiagnosticRuntimeError(code)
        return AIMessage(content='Recovered')
    assert invoke_model(state, role, operation, invoke).content == 'Recovered'
    assert len(calls) == 2
    assert [item['status'] for item in state.model_calls] == ['failed', 'succeeded']
    assert [item['operation'] for item in state.model_calls] == [operation, operation + '_transport_retry']
    assert state.model_calls[0]['diagnostic']['code'] == code


@pytest.mark.parametrize('role,operation', OPERATIONS)
def test_second_transient_failure_stops_at_two_attempts(settings, monkeypatch, role, operation):
    monkeypatch.setattr('time.sleep', lambda _: None)
    state = state_for(settings)
    def fail():
        raise DiagnosticRuntimeError('CLI_TIMEOUT')
    with pytest.raises(DiagnosticRuntimeError):
        invoke_model(state, role, operation, fail)
    assert len(state.model_calls) == 2


@pytest.mark.parametrize('code', ['CLI_AUTH_REQUIRED', 'CLI_QUOTA_EXCEEDED', 'CLI_MODEL_UNSUPPORTED',
                                 'CLI_ARGUMENTS_INVALID', 'CLI_OUTPUT_LIMIT'])
def test_permanent_failure_does_not_retry(settings, code):
    state = state_for(settings)
    def fail():
        raise DiagnosticRuntimeError(code)
    with pytest.raises(DiagnosticRuntimeError):
        invoke_model(state, 'orchestrator', 'planning_inspection', fail)
    assert len(state.model_calls) == 1


def test_native_worker_is_not_replayed_after_possible_mutations(settings):
    state = state_for(settings)
    with pytest.raises(DiagnosticRuntimeError):
        invoke_model(state, 'coder', 'worker', lambda: (_ for _ in ()).throw(DiagnosticRuntimeError('CLI_TIMEOUT')))
    assert len(state.model_calls) == 1


def test_new_gemini_deadline_covers_inspection_and_synthesis(settings, monkeypatch):
    from council.gemini_cli import resolve_cli_settings, validate_cli_settings
    from council.call_policy import gemini_deadline
    monkeypatch.setenv('COUNCIL_GEMINI_NODE_PATH', settings['node_path'])
    monkeypatch.setenv('COUNCIL_GEMINI_CLI_PATH', settings['entrypoint'])
    selected = resolve_cli_settings()
    validate_cli_settings(selected)
    assert selected['timeout_policy_version'] == 3
    assert gemini_deadline(selected) == gemini_deadline(selected, structured=True) == 600
    assert gemini_deadline(settings) == 180
    assert gemini_deadline({**settings, 'timeout_policy_version': 2,
                            'structured_timeout_seconds': 600}, structured=True) == 600


@pytest.mark.parametrize('operation', ['roadmap', 'strategy_reset', 'plan_revision_transport_retry'])
def test_structured_timeout_evidence_matches_transport_for_all_synthesis_operations(settings, operation):
    from council.model_evidence import build_call_record
    selected = {**settings, 'timeout_policy_version': 2, 'structured_timeout_seconds': 600}
    record = build_call_record(state_for(selected).model_configuration, 'orchestrator', operation)
    assert record['effective_timeout_seconds'] == 600


@pytest.mark.parametrize('provider', ['codex-cli', 'gemini-cli'])
def test_timeout_preserves_finite_process_facts_and_closes_streams(settings, tmp_path, monkeypatch, provider):
    from council import cli_process, gemini_cli
    child = SimpleNamespace(stdin=io.BytesIO(), stdout=io.BytesIO(b'partial result'),
        stderr=io.BytesIO(b'connection refused PRIVATE_SECRET'), returncode=None)
    waits = []
    def wait(timeout=None):
        waits.append(timeout)
        if len(waits) == 1:
            raise subprocess.TimeoutExpired('fixture', timeout)
        child.returncode = -9
    child.wait = wait
    module = cli_process if provider == 'codex-cli' else gemini_cli
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *args, **kwargs: child)
    monkeypatch.setattr(module, '_kill' if provider == 'codex-cli' else '_kill_tree', lambda _: None)
    with pytest.raises(DiagnosticRuntimeError) as caught:
        if provider == 'codex-cli':
            cli_process.run_process(['fixture'], timeout=600)
        else:
            gemini_cli._run(settings, 'gemini-test', b'{}', tmp_path, {})
    detail = describe(caught.value)
    assert detail['code'] == 'CLI_TIMEOUT'
    assert detail['cli_process']['provider'] == provider
    assert detail['cli_process']['stdout_bytes'] == len(b'partial result')
    assert detail['cli_process']['signals'] == ['connection_refused']
    assert 'PRIVATE_SECRET' not in json.dumps(detail)
    assert all(stream.closed for stream in (child.stdin, child.stdout, child.stderr))


def test_requested_model_defaults_cover_every_role(settings, monkeypatch):
    from council import config
    for role in ('orchestrator', 'investigator', 'coder', 'reviewer'):
        monkeypatch.delenv(f'COUNCIL_{role.upper()}_MODEL', raising=False)
        monkeypatch.delenv(f'COUNCIL_{role.upper()}_PROVIDER', raising=False)
    monkeypatch.setattr(config, '_provider_settings', lambda provider:
        settings if provider == 'gemini-cli' else state_for(settings).model_configuration['roles']['coder']['settings'])
    selected = config.resolve_model_configuration(autonomous=True)
    assert {name: role.model for name, role in selected.roles.items()} == {
        'orchestrator': 'gpt-6.1-sol', 'investigator': 'gpt-6.1-sol',
        'coder': 'gpt-6.1-sol', 'reviewer': 'gpt-6.1-sol'}


def test_later_plan_cannot_target_a_completed_phase_frozen_test(lifecycle):
    from council.plan_validation import validate_plan
    lifecycle.plan.tasks[0].target_files = ['previous.test.ts']
    with pytest.raises(ValueError) as caught:
        validate_plan(lifecycle.plan, lifecycle.context, native_coding=True,
                      frozen_files=['previous.test.ts'])
    assert caught.value.verification['reason'] == 'FROZEN_TEST_TARGETED'


def test_verification_timeout_keeps_output_emitted_before_failure(lifecycle):
    from council.runner import SubprocessRunner
    code, out, err = SubprocessRunner(context=lifecycle.context).run([
        sys.executable, '-c', "import time; print('probe started', flush=True); time.sleep(10)"], timeout=0.4)
    assert code == 124
    assert 'probe started' in out
    assert 'timed out' in err
