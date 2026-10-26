"""Planning instructions and deadlines stay bounded and explicit per run."""
from copy import deepcopy
import io
import json
import os
import subprocess
from types import SimpleNamespace

import pytest
from test_engine_integration import lifecycle
from test_gemini_cli import settings, Answer


def write(root, name, text):
    path = root/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def policy(settings):
    return {**settings, 'timeout_policy_version': 2, 'structured_timeout_seconds': 600}


def configuration(settings):
    return {'version': 2, 'roles': {name: dict(provider='gemini-cli', model='gemini-test', settings=settings)
        for name in ('orchestrator', 'investigator')}}


def test_review_and_revision_include_each_guidance_source_once(lifecycle):
    from council.plan_review import review_request, revision_request
    root, workspace = lifecycle.context.council_root, lifecycle.workspace
    write(root, 'instructions/shared.md', 'SHARED_ONCE')
    write(root, 'rules/global.md', 'SAME_TEXT_DISTINCT_PATHS')
    write(workspace, 'AGENTS.md', 'SAME_TEXT_DISTINCT_PATHS')
    for name in ('the-architect', 'the-gatekeeper'):
        write(root, f'skills/{name}/SKILL.md', name.upper())
    write(root, 'project-instructions/repo.md', 'PROJECT_ONCE')
    write(workspace, 'repo/AGENTS.md', 'LOCAL_ONCE')
    lifecycle.plan.tasks[0].target_files = ['repo/src/a.ts']
    state = lifecycle.state
    state.plan = lifecycle.plan
    state.planning_evidence = ['OBSERVED_RECEIPT']
    original = state.model_dump(mode='json')
    reviewed, revised = review_request(state, lifecycle.context), revision_request(state, lifecycle.context)
    assert reviewed['guidance'] == revised['guidance']
    guidance = revised['guidance']
    assert guidance.count('SHARED_ONCE') == 1
    assert guidance.count('SAME_TEXT_DISTINCT_PATHS') == 2
    assert guidance.count('PROJECT_ONCE') == guidance.count('LOCAL_ONCE') == 1
    for name in ('the-architect', 'the-gatekeeper', 'the-coder'):
        assert guidance.count(f'--- Guidance: skills/{name}/SKILL.md ---') == 1
    assert state.model_dump(mode='json') == original
    assert revised['planning_evidence'] == ['OBSERVED_RECEIPT']


def test_source_deduplication_does_not_skip_file_or_package_limits(lifecycle):
    from council.prompt_context import load_guidance
    seen = set()
    root = lifecycle.context.council_root
    write(root, 'instructions/shared.md', 'initial')
    assert 'initial' in load_guidance(lifecycle.context, seen_sources=seen)
    assert load_guidance(lifecycle.context, seen_sources=seen) == ''
    write(root, 'instructions/shared.md', 'x'*65537)
    with pytest.raises(ValueError, match='byte limit'):
        load_guidance(lifecycle.context, seen_sources=seen)
    for name in ('instructions/shared.md', 'rules/global.md', 'rules/workspace.md'):
        write(root, name, 'x'*65000)
    write(lifecycle.workspace, 'AGENTS.md', 'x'*5000)
    with pytest.raises(ValueError, match='Combined guidance'):
        load_guidance(lifecycle.context, seen_sources=seen)


def test_new_settings_snapshot_declares_policy_three(settings, monkeypatch):
    from council.gemini_cli import resolve_cli_settings
    monkeypatch.setenv('COUNCIL_GEMINI_NODE_PATH', settings['node_path'])
    monkeypatch.setenv('COUNCIL_GEMINI_CLI_PATH', settings['entrypoint'])
    assert resolve_cli_settings() == {**policy(settings), 'timeout_seconds': 600, 'timeout_policy_version': 3}


@pytest.mark.parametrize('changes', [
    {'timeout_policy_version': 1}, {'timeout_policy_version': True},
    {'timeout_policy_version': '2'}, {'structured_timeout_seconds': 601},
    {'structured_timeout_seconds': True}, {'structured_timeout_seconds': None},
    {'timeout_seconds': 600}, {'PRIVATE_EXTRA': 'SECRET'},
])
def test_policy_two_rejects_unknown_or_unbounded_settings(settings, changes):
    from council.gemini_cli import validate_cli_settings
    with pytest.raises(ValueError):
        validate_cli_settings({**policy(settings), **changes})


@pytest.mark.parametrize('missing', ['timeout_policy_version', 'structured_timeout_seconds'])
def test_incomplete_policy_is_rejected(settings, missing):
    from council.gemini_cli import validate_cli_settings
    value = policy(settings)
    value.pop(missing)
    with pytest.raises(ValueError):
        validate_cli_settings(value)


@pytest.mark.parametrize('new,structured,expected', [(False, False, 180), (False, True, 180),
    (True, False, 180), (True, True, 600)])
def test_transport_receives_effective_deadline_without_mutating_snapshot(settings, monkeypatch, new, structured, expected):
    from council import gemini_cli
    selected = policy(settings) if new else settings
    before = deepcopy(selected)
    observed = []
    monkeypatch.setattr(gemini_cli, '_installed', lambda _: True)
    def run(effective, *args):
        observed.append(deepcopy(effective))
        return json.dumps({'response': '{"count":1}' if structured else 'plain'}).encode()
    monkeypatch.setattr(gemini_cli, '_run', run)
    base = gemini_cli.GeminiCLIChatModel('gemini-test', selected)
    model = base.with_structured_output(Answer) if structured else base
    model.invoke([])
    assert observed[0]['timeout_seconds'] == expected
    assert selected == base.settings == model.settings == before


@pytest.mark.parametrize('new,operation,expected', [(False, 'planning', 180), (False, 'plan_revision', 180),
    (True, 'planning', 600), (True, 'plan_revision', 600), (True, 'planning_inspection', 180),
    (True, 'planning_format_retry', 180), (True, 'investigation', 180)])
@pytest.mark.parametrize('failed', [False, True])
def test_effective_deadline_is_recorded_on_success_and_failure(settings, new, operation, expected, failed):
    from council.model_evidence import build_call_record
    from council.diagnostics import DiagnosticRuntimeError
    selected = policy(settings) if new else settings
    record = build_call_record(configuration(selected), 'orchestrator', operation,
        error=DiagnosticRuntimeError('CLI_TIMEOUT') if failed else None)
    assert record.get('effective_timeout_seconds') == expected
    assert record['settings'] == selected


def test_legacy_and_new_configuration_roundtrip_independently(settings):
    from council.config import RunModelConfiguration
    old = RunModelConfiguration.model_validate(configuration(settings))
    new = RunModelConfiguration.model_validate(configuration(policy(settings)))
    assert RunModelConfiguration.model_validate(old.model_dump(mode='json')).model_dump() == old.model_dump()
    assert old.roles['orchestrator'].settings == settings
    assert new.roles['orchestrator'].settings == policy(settings)


@pytest.mark.parametrize('timeout', [180, 600])
def test_timeout_transport_kills_child_and_closes_streams(settings, tmp_path, monkeypatch, timeout):
    from council import gemini_cli
    calls = []
    child = SimpleNamespace(stdin=io.BytesIO(), stdout=io.BytesIO(), stderr=io.BytesIO(), returncode=None)
    def wait(timeout=None):
        calls.append(timeout)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired('inert-child', timeout)
        child.returncode = -9
    child.wait = wait
    monkeypatch.setattr(gemini_cli.subprocess, 'Popen', lambda *args, **kwargs: child)
    killed = []
    monkeypatch.setattr(gemini_cli, '_kill_tree', lambda process: killed.append(process))
    with pytest.raises(RuntimeError) as caught:
        gemini_cli._run({**settings, 'timeout_seconds': timeout}, 'gemini-test', b'{}', tmp_path, dict(os.environ))
    assert caught.value.code == 'CLI_TIMEOUT'
    assert calls == [timeout, None] and killed == [child]
    assert all(stream.closed for stream in (child.stdin, child.stdout, child.stderr))


@pytest.mark.parametrize('new', [False, True])
def test_graph_call_failure_evidence_uses_snapshot_deadline(settings, new):
    from council.graph import invoke_model
    from council.state import CouncilState
    from council.diagnostics import DiagnosticRuntimeError
    selected = policy(settings) if new else settings
    state = CouncilState(run_id='offline-deadline', task_input='offline', model_configuration=configuration(selected))
    original = deepcopy(state.model_configuration)
    def fail():
        raise DiagnosticRuntimeError('CLI_TIMEOUT')
    with pytest.raises(RuntimeError):
        invoke_model(state, 'orchestrator', 'plan_revision', fail)
    assert state.model_calls[0]['effective_timeout_seconds'] == (600 if new else 180)
    assert state.model_calls[0]['diagnostic']['code'] == 'CLI_TIMEOUT'
    assert state.model_configuration == original


def test_new_policy_is_persisted_in_fresh_run_configuration(settings, monkeypatch):
    from council.config import resolve_model_configuration, RunModelConfiguration
    monkeypatch.setenv('COUNCIL_ORCHESTRATOR_PROVIDER', 'gemini-cli')
    monkeypatch.setenv('COUNCIL_INVESTIGATOR_PROVIDER', 'gemini-cli')
    monkeypatch.setenv('COUNCIL_GEMINI_NODE_PATH', settings['node_path'])
    monkeypatch.setenv('COUNCIL_GEMINI_CLI_PATH', settings['entrypoint'])
    resolved = resolve_model_configuration(autonomous=True)
    saved = RunModelConfiguration.model_validate(resolved.model_dump(mode='json'))
    current = {**policy(settings), 'timeout_seconds': 600, 'timeout_policy_version': 3}
    assert saved.roles['orchestrator'].settings == current
    assert saved.roles['investigator'].settings == current
    assert saved.roles['coder'].settings['timeout_seconds'] == 600
    assert 'timeout_policy_version' not in saved.roles['coder'].settings
