"""Autonomous review contracts using real graph/checkpoints and inert providers."""
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command
from test_engine_integration import lifecycle, ScriptedProvider, open_graph
from council.graph import build_council_graph
from council.config import resolve_model_configuration
from council.state import CouncilState
from council.diagnostics import DiagnosticRuntimeError


class Reviewer:
    def __init__(self, decisions):
        self.decisions = iter(decisions)
        self.calls = 0

    def review_plan(self, request):
        self.calls += 1
        value = next(self.decisions)
        if isinstance(value, Exception):
            raise value
        return AIMessage(content=json.dumps(value))


def setup(lifecycle, monkeypatch, decisions, contents=None):
    state = lifecycle.state.model_dump()
    state['approval_policy'] = 'autonomous'
    configuration = resolve_model_configuration().model_dump(mode='json')
    configuration['version'] = 4
    configuration['roles']['reviewer'] = dict(configuration['roles']['coder'])
    state['model_configuration'] = configuration
    class NativeProvider(ScriptedProvider):
        def run_task(self, task, guidance, **kwargs):
            attempt = self.attempts.get(task.id, 0)
            self.attempts[task.id] = attempt + 1
            versions = self.contents.get(task.id, ['valid'])
            (lifecycle.workspace/task.target_files[0]).write_text(versions[min(attempt, len(versions)-1)])
            return AIMessage(content='Fixture task completed.')
    provider = NativeProvider(lifecycle.plan, contents)
    reviewer = Reviewer(decisions)
    return state, provider, reviewer


def graph_for(lifecycle, saver, provider, reviewer):
    return build_council_graph(checkpointer=saver, context=lifecycle.context,
        llm_factory=lambda role: reviewer if role == 'reviewer' else provider)


ACCEPT = {'decision': 'accept', 'findings': []}
REVISE = {'decision': 'revise', 'findings': ['Make verification explicit.']}
ESCALATE = {'decision': 'escalate', 'findings': ['Requirement needs clarification.']}


def test_accept_executes_and_completes_without_human_gates(lifecycle, monkeypatch):
    state, provider, reviewer = setup(lifecycle, monkeypatch, [ACCEPT])
    monkeypatch.setattr('builtins.input', lambda *args: pytest.fail('No routine human input'))
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert result['status'] == 'COMPLETED'
    assert result['plan_review_count'] == 1
    assert result['accepted_plan_sha256']
    assert len(result['test_results']) == 2
    assert not result.get('__interrupt__')


def test_reviewer_transport_execution_failure_gets_one_read_only_retry(lifecycle, monkeypatch):
    state, provider, reviewer = setup(lifecycle, monkeypatch,
        [DiagnosticRuntimeError('CLI_EXECUTION_FAILED'), ACCEPT])
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert result['status'] == 'COMPLETED'
    assert reviewer.calls == 2
    assert result['plan_review_count'] == 1
    review_calls = [call for call in result['model_calls'] if call['role'] == 'reviewer']
    assert [call['operation'] for call in review_calls] == [
        'plan_review', 'plan_review_transport_retry']
    assert [call['status'] for call in review_calls] == ['failed', 'succeeded']


def test_second_reviewer_transport_failure_still_blocks_before_workers(lifecycle, monkeypatch):
    failure = DiagnosticRuntimeError('CLI_EXECUTION_FAILED')
    state, provider, reviewer = setup(lifecycle, monkeypatch, [failure, failure])
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert result['status'] == 'PLAN_BLOCKED'
    assert result['diagnostic']['code'] == 'CLI_EXECUTION_FAILED'
    assert result['plan_review_count'] == 1 and reviewer.calls == 2
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_reviewer_auth_failure_does_not_retry(lifecycle, monkeypatch):
    state, provider, reviewer = setup(lifecycle, monkeypatch,
        [DiagnosticRuntimeError('CLI_AUTH_REQUIRED'), ACCEPT])
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert result['status'] == 'PLAN_BLOCKED'
    assert result['diagnostic']['code'] == 'CLI_AUTH_REQUIRED'
    assert reviewer.calls == 1


def test_revise_then_accept_runs_review_again_before_worker(lifecycle, monkeypatch):
    state, provider, reviewer = setup(lifecycle, monkeypatch, [REVISE, ACCEPT])
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert result['status'] == 'COMPLETED'
    assert result['plan_revision_count'] == 1
    assert reviewer.calls == 2


@pytest.mark.parametrize('decision', [ESCALATE, {'decision': 'accept', 'findings': ['unresolved']},
    {'decision': 'yes', 'findings': []}, RuntimeError('PRIVATE_ERROR')])
def test_unresolved_review_checkpoints_before_any_worker(lifecycle, monkeypatch, decision):
    state, provider, reviewer = setup(lifecycle, monkeypatch, [decision])
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        result = graph.invoke(state, lifecycle.config)
        assert result['status'] == 'PLAN_BLOCKED'
        assert result['__interrupt__'][0].value['gate'] == 'PLAN_REVIEW_BLOCKED'
        assert graph.get_state(lifecycle.config).values['plan_review_count'] == 1
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_budget_survives_restart_and_boolean_does_not_approve(lifecycle, monkeypatch):
    state, provider, reviewer = setup(lifecycle, monkeypatch, [REVISE]*3)
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
        assert result['plan_review_count'] == 3
        assert result['plan_revision_count'] == 2
        assert result['status'] == 'PLAN_BLOCKED'
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(Command(resume={'approved': True}), lifecycle.config)
        assert result['status'] == 'PLAN_BLOCKED'
        assert result['__interrupt__']
        assert reviewer.calls == 3
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_explicit_feedback_starts_recorded_recovery_review(lifecycle, monkeypatch):
    state, provider, reviewer = setup(lifecycle, monkeypatch, [ESCALATE, ACCEPT])
    with open_graph(lifecycle, provider) as saver:
        graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(
            Command(resume={'feedback': 'Keep the original scope and declared checks.'}), lifecycle.config)
    assert result['status'] == 'COMPLETED'
    assert result['plan_recovery_count'] == 1
    assert result['plan_review_count'] == 2
    assert reviewer.calls == 2


def test_verification_exhaustion_is_reported_without_final_approval(lifecycle, monkeypatch):
    state, provider, reviewer = setup(lifecycle, monkeypatch, [ACCEPT], {'task-1': ['broken']})
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert result['status'] == 'FAILED'
    assert result['diagnostic']['code'] == 'VERIFICATION_FAILED'
    assert not result.get('__interrupt__')


def test_legacy_state_does_not_gain_autonomous_policy():
    assert CouncilState.model_validate({'run_id': 'old', 'task_input': 'old'}).approval_policy is None


def test_cli_policy_flags_are_mutually_exclusive():
    from council.cli import create_parser
    parser = create_parser()
    assert parser.parse_args(['--approval-mode', 'autonomous']).approval_mode == 'autonomous'
    with pytest.raises(SystemExit):
        parser.parse_args(['--approval-mode', 'manual', '--auto-approve'])


@pytest.fixture
def autonomous_cli(lifecycle, monkeypatch):
    state, provider, reviewer = setup(lifecycle, monkeypatch, [ACCEPT])
    monkeypatch.setattr('council.graph.get_llm_for_role', lambda role, *args, **kwargs: reviewer if role == 'reviewer' else provider)
    monkeypatch.setattr('council.cli.preflight_credentials', lambda *args: {'codex-cli': True, 'gemini-cli': True})
    monkeypatch.setattr('council.cli.uuid.uuid4', lambda: SimpleNamespace(hex='autonomous-cli'))
    # These cases exercise the persisted 0.2.8 protocol; convergence tests cover new runs.
    monkeypatch.setattr('council.cli.REVIEW_PROTOCOL_VERSION', 1)
    monkeypatch.setattr('council.cli.READINESS_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.ORCHESTRATION_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.GRAPH_INTEGRITY_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.GOVERNANCE_POLICY_VERSION', 1)
    monkeypatch.setattr('builtins.input', lambda *args: pytest.fail('Autonomous CLI must not use stdin'))
    return lifecycle, reviewer


def call_cli(fixture, **kwargs):
    from council.cli import run_council_task
    return run_council_task(workspace_root=fixture.workspace, council_root=fixture.context.council_root, **kwargs)


def test_cli_defaults_to_autonomous_even_with_no_input(autonomous_cli, capsys):
    fixture, reviewer = autonomous_cli
    assert call_cli(fixture, prompt='fixture', no_input=True) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'COMPLETED'
    assert result['approval_policy'] == 'autonomous'
    assert result['model_configuration']['version'] == 4
    assert result['plan_review_count'] == 1


def test_cli_blocker_resume_requires_feedback_not_autoapprove(autonomous_cli, capsys):
    fixture, reviewer = autonomous_cli
    reviewer.decisions = iter([ESCALATE, ACCEPT])
    assert call_cli(fixture, prompt='fixture') == 2
    blocked = json.loads(capsys.readouterr().out)
    assert blocked['status'] == 'BLOCKED'
    assert blocked['findings'] == ESCALATE['findings']
    assert not list(fixture.workspace.glob('target-*.txt'))
    assert call_cli(fixture, resume_id='autonomous-cli') == 2
    capsys.readouterr()
    with pytest.raises(ValueError, match='policy'):
        call_cli(fixture, resume_id='autonomous-cli', auto_approve=True)
    (fixture.workspace/'feedback.txt').write_text('Keep existing requirements.')
    assert call_cli(fixture, resume_id='autonomous-cli', feedback_file='feedback.txt', no_input=True) == 0
    assert json.loads(capsys.readouterr().out)['plan_recovery_count'] == 1
    assert reviewer.calls == 2


@pytest.mark.parametrize('feedback', ['', 'x'*12001])
def test_feedback_file_limits_preserve_blocked_checkpoint(autonomous_cli, feedback):
    fixture, reviewer = autonomous_cli
    reviewer.decisions = iter([ESCALATE])
    assert call_cli(fixture, prompt='fixture') == 2
    (fixture.workspace/'feedback.txt').write_text(feedback)
    with pytest.raises(ValueError):
        call_cli(fixture, resume_id='autonomous-cli', feedback_file='feedback.txt')
    assert reviewer.calls == 1


def test_revision_revalidates_changed_plan_before_second_review(lifecycle, monkeypatch):
    state, provider, reviewer = setup(lifecycle, monkeypatch, [REVISE, ACCEPT])
    original = provider.with_structured_output
    calls = 0
    def structured(schema, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            changed = lifecycle.plan.model_copy(deep=True)
            changed.tasks[0].target_files = ['../escape.txt']
            return SimpleNamespace(invoke=lambda messages: {'parsed': changed, 'raw': AIMessage(content=''), 'parsing_error': None})
        return original(schema, **kwargs)
    provider.with_structured_output = structured
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert result['status'] == 'PLAN_BLOCKED'
    assert result['diagnostic']['code'] == 'PLAN_TARGET_PATH_INVALID'
    assert reviewer.calls == 1
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_digest_covers_scope_but_allows_execution_status(lifecycle):
    from council.plan_review import plan_digest
    digest = plan_digest(lifecycle.plan)
    changed = lifecycle.plan.model_copy(deep=True)
    changed.tasks[0].status = 'completed'
    assert plan_digest(changed) == digest
    changed.tasks[0].test_commands[0].append('different')
    assert plan_digest(changed) != digest


def test_autonomous_configuration_keeps_legacy_versions():
    from council.config import RunModelConfiguration
    config = resolve_model_configuration(autonomous=True)
    assert config.version == 4
    assert config.roles['reviewer'].provider == 'codex-cli'
    legacy = resolve_model_configuration()
    assert legacy.version == 3
    assert 'reviewer' not in legacy.roles
    invalid = config.model_dump()
    invalid['roles']['reviewer']['provider'] = 'gpt'
    invalid['roles']['reviewer']['settings'] = {'use_responses_api':True,
        'include_response_headers':True,'base_url':'https://api.openai.com/v1'}
    with pytest.raises(ValueError):
        RunModelConfiguration.model_validate(invalid)


def test_changed_accepted_plan_is_rejected_before_worker(lifecycle, monkeypatch):
    state, provider, reviewer = setup(lifecycle, monkeypatch, [ACCEPT])
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        paused = graph.invoke(state, lifecycle.config, interrupt_before=['worker'])
        assert paused['accepted_plan_sha256']
        changed = paused['plan']
        changed['tasks'][0]['description'] = 'Different work contract'
        graph.update_state(lifecycle.config, {'plan': changed})
        result = graph.invoke(None, lifecycle.config)
    assert result['status'] == 'FAILED'
    assert result['diagnostic']['code'] == 'PLAN_ACCEPTANCE_INVALID'
    assert not list(lifecycle.workspace.glob('target-*.txt'))


@pytest.mark.parametrize('content', [None, 'x'*16001, '{"decision":"accept","findings":[],"extra":true}',
    '{"decision":"revise","findings":[" "]}', '{"decision":"revise","findings":["'+'x'*1001+'"]}'])
def test_review_parser_rejects_invalid_or_unbounded_payloads(content):
    from council.plan_review import parse_review
    with pytest.raises(ValueError) as caught:
        parse_review(SimpleNamespace(content=content))
    assert caught.value.code == 'PLAN_REVIEW_INVALID'


def test_review_guidance_limit_is_enforced(lifecycle, monkeypatch):
    from council.plan_review import review_request
    lifecycle.state.plan = lifecycle.plan
    monkeypatch.setattr('council.plan_review.load_guidance', lambda *args, **kwargs: 'x'*(300*1024))
    with pytest.raises(ValueError) as caught:
        review_request(lifecycle.state, lifecycle.context)
    assert caught.value.code == 'CLI_INPUT_LIMIT'


@pytest.mark.parametrize('stage', ['review', 'revision'])
def test_persisted_budget_guard_cannot_dispatch_work(lifecycle, monkeypatch, stage):
    state, provider, reviewer = setup(lifecycle, monkeypatch, [])
    state.update(plan=lifecycle.plan.model_dump(), plan_review_count=3, plan_revision_count=2,
                 status='PLAN_REVISION' if stage == 'revision' else 'START')
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        if stage == 'revision':
            graph.update_state(lifecycle.config, state, as_node='plan_blocked')
            result = graph.invoke(None, lifecycle.config)
        else:
            result = graph.invoke(state, lifecycle.config)
    assert result['status'] == 'PLAN_BLOCKED'
    assert result['diagnostic']['code'] == 'PLAN_REVIEW_EXHAUSTED'
    assert reviewer.calls == 0
    assert not list(lifecycle.workspace.glob('target-*.txt'))


@pytest.mark.parametrize('kind', ['parse_error', 'completed_task', 'plain_plan'])
def test_revision_schema_and_plain_provider_contract(lifecycle, monkeypatch, kind):
    state, provider, reviewer = setup(lifecycle, monkeypatch, [REVISE, ACCEPT])
    original = provider.with_structured_output
    calls = 0
    def structured(schema, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return original(schema, **kwargs)
        plan = lifecycle.plan.model_copy(deep=True)
        if kind == 'completed_task':
            plan.tasks[0].status = 'completed'
        response = plan if kind == 'plain_plan' else {'parsed': plan, 'raw': AIMessage(content=''),
            'parsing_error': ValueError('PRIVATE_ERROR') if kind == 'parse_error' else None}
        return SimpleNamespace(invoke=lambda messages: response)
    provider.with_structured_output = structured
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert result['status'] == ('COMPLETED' if kind == 'plain_plan' else 'PLAN_BLOCKED')


@pytest.mark.parametrize('kwargs', [{'approval_mode':'invalid'}, {'approval_mode':'manual', 'auto_approve':True},
    {'feedback_file':'feedback.txt'}])
def test_cli_rejects_invalid_policy_or_feedback_context(autonomous_cli, kwargs):
    fixture, _ = autonomous_cli
    with pytest.raises(ValueError):
        call_cli(fixture, prompt='fixture', **kwargs)


def test_cli_rejects_oversize_feedback_and_feedback_on_completed_run(autonomous_cli):
    fixture, _ = autonomous_cli
    assert call_cli(fixture, prompt='fixture') == 0
    (fixture.workspace/'feedback.txt').write_bytes(b'x'*48001)
    with pytest.raises(ValueError):
        call_cli(fixture, resume_id='autonomous-cli', feedback_file='feedback.txt')
    (fixture.workspace/'feedback.txt').write_text('Feedback')
    with pytest.raises(ValueError):
        call_cli(fixture, resume_id='autonomous-cli', feedback_file='feedback.txt')


def test_unavailable_transport_during_feedback_keeps_checkpoint_blocked(autonomous_cli, monkeypatch):
    fixture, reviewer = autonomous_cli
    reviewer.decisions = iter([ESCALATE])
    assert call_cli(fixture, prompt='fixture') == 2
    (fixture.workspace/'feedback.txt').write_text('Feedback')
    monkeypatch.setattr('council.cli.preflight_credentials', lambda *args: {'codex-cli': False})
    assert call_cli(fixture, resume_id='autonomous-cli', feedback_file='feedback.txt') == 1
    assert reviewer.calls == 1


def test_unavailable_transport_prevents_new_autonomous_execution(autonomous_cli, monkeypatch, capsys):
    fixture, reviewer = autonomous_cli
    monkeypatch.setattr('council.cli.preflight_credentials', lambda *args: {'codex-cli': False})
    assert call_cli(fixture, prompt='fixture') == 1
    assert json.loads(capsys.readouterr().out)['diagnostic']['code'] == 'PROVIDER_UNAVAILABLE'
    assert reviewer.calls == 0
    assert not list(fixture.workspace.glob('target-*.txt'))


def test_unavailable_transport_on_manual_resume_preserves_pending_gate(autonomous_cli, monkeypatch, capsys):
    fixture, reviewer = autonomous_cli
    assert call_cli(fixture, prompt='fixture', approval_mode='manual', no_input=True) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'PAUSED'
    monkeypatch.setattr('council.cli.sys.stdin.isatty', lambda: True)
    monkeypatch.setattr('council.cli.preflight_credentials', lambda *args: {'codex-cli': False})
    assert call_cli(fixture, resume_id='autonomous-cli') == 1
    assert reviewer.calls == 0
    assert not list(fixture.workspace.glob('target-*.txt'))
    assert call_cli(fixture, resume_id='autonomous-cli', no_input=True) == 2
