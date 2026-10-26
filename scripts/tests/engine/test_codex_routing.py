"""Native worker handoff stays behind LangGraph approval and verification."""
import hashlib

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command

from test_engine_integration import lifecycle, ScriptedProvider, open_graph, assert_gate


def configure(fixture, version=3):
    role = {'provider': 'gpt', 'model': 'gpt-test', 'settings': {
        'use_responses_api': True, 'include_response_headers': True,
        'base_url': 'https://api.openai.com/v1'}}
    fixture.state.model_configuration = {'version': version,
        'roles': {name: role.copy() for name in (
            ('orchestrator', 'investigator', 'coder') if version == 3 else
            ('orchestrator', 'investigator'))}}
    if version == 3:
        fixture.state.model_configuration['roles']['coder'] = {
            'provider': 'codex-cli', 'model': 'gpt-test', 'settings': {
                'executable': 'C:/fixture/codex.exe', 'cli_version': '0.163.0', 'timeout_seconds': 600}}
    fixture.plan.tasks = fixture.plan.tasks[:1]


class NativeCoder:
    def __init__(self, fixture, *, contents=('valid',), fail=False, extras=()):
        self.fixture = fixture
        self.contents = contents
        self.fail = fail
        self.extras = extras
        self.calls = []

    def run_task(self, task, guidance, diagnosis='', prior_result=None):
        self.calls.append((task, guidance, diagnosis, prior_result))
        version = self.contents[min(len(self.calls) - 1, len(self.contents) - 1)]
        (self.fixture.workspace / task.target_files[0]).write_text(version, encoding='utf-8')
        for path in self.extras:
            (self.fixture.workspace / path).write_text('native extra', encoding='utf-8')
        if self.fail:
            error = RuntimeError('Native coding failed after touching declared target')
            error.native_file_changes = list(self.extras)
            raise error
        return AIMessage(content='Implementation completed', additional_kwargs={
            'native_file_changes': [*task.target_files, *self.extras]})


def graph_for(fixture, saver, coder, roles):
    from council.graph import build_council_graph
    reasoning = ScriptedProvider(fixture.plan)
    def factory(role):
        roles.append(role)
        return coder if role == 'coder' else reasoning
    return build_council_graph(checkpointer=saver, context=fixture.context, llm_factory=factory)


def test_native_coder_runs_only_after_gate_one_and_independent_prover(lifecycle):
    configure(lifecycle)
    coder = NativeCoder(lifecycle)
    roles = []
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, roles)
        paused = graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        assert_gate(paused, 'GATE_1_PLAN_APPROVAL')
        assert not coder.calls
        assert 'coder' not in roles
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert_gate(result, 'GATE_2_PRE_SUBMIT_APPROVAL')
    assert len(coder.calls) == 1
    assert result['test_results'][0]['passed'] is True
    assert result['model_calls'][-1]['role'] == 'coder'
    assert result['modified_files'] == ['target-1.txt']
    assert result['file_changes'][0]['before_sha256'] is None
    assert result['file_changes'][0]['after_sha256'] == hashlib.sha256(b'valid').hexdigest()
    assert 'native' in result['__interrupt__'][0].value['file_change_scope'].lower()


def test_gemini_investigation_hands_diagnosis_back_to_coder_for_repair(lifecycle):
    configure(lifecycle)
    coder = NativeCoder(lifecycle, contents=('invalid', 'valid'))
    roles = []
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, roles)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), 'GATE_1_PLAN_APPROVAL')
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert_gate(result, 'GATE_2_PRE_SUBMIT_APPROVAL')
    assert [item['passed'] for item in result['test_results']] == [False, True]
    assert len(coder.calls) == 2
    assert coder.calls[1][2]
    assert coder.calls[1][3]['passed'] is False
    assert roles[-3:] == ['coder', 'investigator', 'coder']
    assert result['active_role'] == 'coder'


def test_native_failure_records_declared_file_changes_and_failed_model_call(lifecycle):
    configure(lifecycle)
    (lifecycle.workspace / 'target-1.txt').write_text('original')
    coder = NativeCoder(lifecycle, fail=True)
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, [])
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), 'GATE_1_PLAN_APPROVAL')
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert result['status'] == 'FAILED'
    assert not result['test_results']
    assert result['model_calls'][-1]['role'] == 'coder'
    assert result['model_calls'][-1]['status'] == 'failed'
    assert result['file_changes'][0]['before_sha256'] == hashlib.sha256(b'original').hexdigest()
    assert result['file_changes'][0]['after_sha256'] == hashlib.sha256(b'valid').hexdigest()


def test_extra_native_event_in_snapshot_has_known_original_hash(lifecycle):
    configure(lifecycle)
    (lifecycle.workspace / 'extra.txt').write_text('existing user content')
    coder = NativeCoder(lifecycle, extras=['extra.txt'])
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, [])
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert_gate(result, 'GATE_2_PRE_SUBMIT_APPROVAL')
    extra = next(item for item in result['file_changes'] if item['path'] == 'extra.txt')
    assert extra['before_known'] is True
    assert extra['before_sha256'] == hashlib.sha256(b'existing user content').hexdigest()
    assert extra['after_sha256'] == hashlib.sha256(b'native extra').hexdigest()


def test_failed_native_turn_retains_extra_observed_file_events(lifecycle):
    configure(lifecycle)
    coder = NativeCoder(lifecycle, fail=True, extras=['extra.txt'])
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, [])
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert result['status'] == 'FAILED'
    assert result['modified_files'] == ['extra.txt', 'target-1.txt']
    extra = next(item for item in result['file_changes'] if item['path'] == 'extra.txt')
    assert extra['before_known'] is True
    assert extra['after_sha256'] == hashlib.sha256(b'native extra').hexdigest()
    assert result['model_calls'][-1]['status'] == 'failed'


@pytest.mark.parametrize('version', [1, 2])
def test_legacy_two_role_runs_keep_orchestrator_worker(version, lifecycle):
    from council.graph import build_council_graph
    configure(lifecycle, version)
    provider = ScriptedProvider(lifecycle.plan)
    roles = []
    def factory(role):
        roles.append(role)
        return provider
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context, llm_factory=factory)
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert_gate(result, 'GATE_2_PRE_SUBMIT_APPROVAL')
    assert set(roles) == {'orchestrator'}
    assert result['active_role'] == 'orchestrator'


def test_excluded_native_extra_path_fails_without_losing_declared_hash_evidence(lifecycle):
    configure(lifecycle)
    coder = NativeCoder(lifecycle, extras=['.env'])
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, [])
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert result['status'] == 'FAILED'
    assert result['modified_files'] == ['target-1.txt']
    assert result['file_changes'][0]['after_sha256'] == hashlib.sha256(b'valid').hexdigest()


@pytest.mark.parametrize('directory', ['node_modules', '.aws'])
def test_native_private_or_generated_working_directory_is_rejected_before_gate(lifecycle, directory):
    configure(lifecycle)
    (lifecycle.workspace / directory).mkdir()
    lifecycle.plan.tasks[0].working_directory = directory
    lifecycle.plan.tasks[0].target_files = []
    coder = NativeCoder(lifecycle)
    roles = []
    with open_graph(lifecycle, coder) as saver:
        result = graph_for(lifecycle, saver, coder, roles).invoke(lifecycle.state.model_dump(), lifecycle.config)
    assert result['status'] == 'FAILED'
    assert not result.get('__interrupt__')
    assert not coder.calls
    assert 'coder' not in roles


def test_native_nested_working_directory_and_independent_verification_are_supported(lifecycle):
    import sys
    configure(lifecycle)
    (lifecycle.workspace / 'repo').mkdir()
    lifecycle.plan.tasks[0].working_directory = 'repo'
    lifecycle.plan.tasks[0].test_commands = [[sys.executable, '../verify.py', '../target-1.txt']]
    coder = NativeCoder(lifecycle)
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, [])
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), 'GATE_1_PLAN_APPROVAL')
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert_gate(result, 'GATE_2_PRE_SUBMIT_APPROVAL')
    assert result['test_results'][0]['passed'] is True
    assert coder.calls[0][0].working_directory == 'repo'


def test_native_working_directory_is_rechecked_after_approval(lifecycle, monkeypatch):
    configure(lifecycle)
    directory = lifecycle.workspace / 'repo'
    directory.mkdir()
    lifecycle.plan.tasks[0].working_directory = 'repo'
    coder = NativeCoder(lifecycle)
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, [])
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), 'GATE_1_PLAN_APPROVAL')
        monkeypatch.setattr('council.tools.discovery._linked', lambda path: path == directory)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert result['status'] == 'FAILED'
    assert not coder.calls
