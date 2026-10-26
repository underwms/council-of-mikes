"""Versioned revision research with one shared inspection budget and real receipts."""
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command
from council.diagnostics import DiagnosticSession, DiagnosticValueError
from council.state import CouncilState
from test_engine_integration import lifecycle, open_graph
from test_autonomous_review import graph_for
from test_review_convergence import configured, decision
from test_format_recovery import transport


def setup_revision(lifecycle, monkeypatch, *, rounds=11, policy=2, responses=None, decisions=None):
    state, provider, reviewer, synthesis = configured(lifecycle, monkeypatch, decisions or [
        decision('F1'), {'decision': 'escalate', 'findings': [
            {'id': 'F1', 'description': 'Fixture user decision remains.', 'kind': 'user_decision'}],
            'resolved_finding_ids': []}])
    state.update(plan=lifecycle.plan.model_dump(mode='json'), revision_evidence_policy_version=policy,
                 planning_inspection=None if rounds is None else dict(rounds_used=rounds, round_limit=12, limit_reached=rounds == 12))
    observed = []
    replies = iter(responses if responses is not None else [AIMessage(content='', tool_calls=[{
        'name': 'read_workspace_file', 'args': {'rel_path': 'verify.py'}, 'id': 'revision-read'}])])
    def bind(tools):
        observed.append({'offered': [tool.name for tool in tools]})
        def invoke(messages):
            observed.append({'messages': messages})
            item = next(replies)
            if isinstance(item, Exception):
                raise item
            return item
        return SimpleNamespace(invoke=invoke)
    provider.bind_tools = bind
    return state, provider, reviewer, synthesis, observed


def run(lifecycle, state, provider, reviewer):
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        result = graph.invoke(state, lifecycle.config)
        saved = graph.get_state(lifecycle.config).values
    return result, saved


def test_revision_observes_source_before_synthesis_review_and_workers(lifecycle, monkeypatch):
    state, provider, reviewer, synthesis, observed = setup_revision(lifecycle, monkeypatch,
        decisions=[decision('F1'), decision(resolved=['F1'], action='accept')])
    original = provider.with_structured_output
    def structured(schema, **kwargs):
        model = original(schema, **kwargs)
        def invoke(messages):
            text = json.dumps([getattr(m, 'content', m) for m in messages])
            assert 'valid = Path' in text, 'Revision must receive the actual newly requested source'
            return model.invoke(messages)
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured

    result, saved = run(lifecycle, state, provider, reviewer)

    assert result['status'] == 'COMPLETED'
    assert saved['planning_inspection'] == dict(rounds_used=12, round_limit=12, limit_reached=True)
    assert 'valid = Path' in json.dumps(saved['planning_evidence'])
    assert saved['planning_evidence_available'] is True
    assert [c['operation'] for c in saved['model_calls']][:4] == [
        'plan_review', 'plan_revision_inspection', 'plan_revision', 'plan_review']
    assert saved['model_calls'][1]['effective_timeout_seconds'] == 600
    assert saved['model_calls'][2]['effective_timeout_seconds'] == 600
    assert set(observed[0]['offered']) == {'read_workspace_file', 'list_workspace_files', 'search_workspace_text'}
    assert saved['accepted_plan_sha256'] and saved['review_finding_ledger'][0]['status'] == 'resolved'


@pytest.mark.parametrize('rounds,policy', [(12, 2), (None, 2), (11, 1)])
def test_unavailable_budget_or_legacy_policy_never_dispatches_inspector(lifecycle, monkeypatch, rounds, policy):
    state, provider, reviewer, synthesis, observed = setup_revision(lifecycle, monkeypatch, rounds=rounds, policy=policy)
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'PLAN_BLOCKED'
    assert observed == []
    assert not any(c['operation'] == 'plan_revision_inspection' for c in saved['model_calls'])
    request = json.loads(synthesis[0][1]['content'])
    if policy == 2:
        assert request['revision_inspection']['reason'] in {'BUDGET_EXHAUSTED', 'SUMMARY_UNAVAILABLE'}
    else:
        assert 'revision_inspection' not in request


def test_empty_inspection_consumes_one_round_without_receipts(lifecycle, monkeypatch):
    state, provider, reviewer, _, _ = setup_revision(lifecycle, monkeypatch,
        responses=[AIMessage(content='Existing evidence suffices.')])
    result, saved = run(lifecycle, state, provider, reviewer)
    assert saved['planning_inspection']['rounds_used'] == 12
    assert saved['planning_evidence'] == []
    assert result['status'] == 'PLAN_BLOCKED'


def test_strategy_reset_reuses_last_round_without_new_inspection(lifecycle, monkeypatch):
    state, provider, reviewer, _, observed = setup_revision(lifecycle, monkeypatch,
        decisions=[decision('F1') for _ in range(5)])
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['diagnostic']['code'] == 'PLAN_REVIEW_STALLED'
    assert saved['plan_revision_count'] == 4
    assert saved['strategy_reset_count'] == 1
    assert len([x for x in observed if 'offered' in x]) == 1
    assert saved['planning_inspection']['rounds_used'] == 12
    assert saved['modified_files'] == []


@pytest.mark.parametrize('code', ['GEMINI_RESPONSE_JSON_INVALID', 'GEMINI_TOOL_NAME_UNOFFERED'])
def test_revision_inspection_recovers_one_malformed_gemini_response(lifecycle, monkeypatch, code):
    state, provider, reviewer, synthesis, observed = setup_revision(lifecycle, monkeypatch,
        responses=[DiagnosticValueError(code),
                   AIMessage(content='Inspection complete.')],
        decisions=[decision('F1'), decision(resolved=['F1'], action='accept')])
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'COMPLETED'
    assert [call['operation'] for call in saved['model_calls']][:4] == [
        'plan_review', 'plan_revision_inspection', 'plan_revision_format_retry', 'plan_revision']
    assert saved['planning_inspection']['rounds_used'] == 12
    assert len([item for item in observed if 'messages' in item]) == 2
    assert code in observed[-1]['messages'][-1]['content']
    assert synthesis


@pytest.mark.parametrize('failure,expected', [
    (PermissionError('PRIVATE_REVISION_TRANSPORT'), 'PERMISSION_DENIED')])
def test_inspection_failure_has_no_retry_or_synthesis(lifecycle, monkeypatch, failure, expected):
    state, provider, reviewer, synthesis, _ = setup_revision(lifecycle, monkeypatch, responses=[failure])
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['diagnostic']['code'] == expected
    assert saved['planning_inspection']['rounds_used'] == 12
    assert saved['plan_revision_count'] == 1
    assert synthesis == [] and saved['modified_files'] == []
    assert saved['model_calls'][-1]['operation'] == 'plan_revision_inspection'


def test_second_revision_format_failure_stops_without_synthesis(lifecycle, monkeypatch):
    failure = DiagnosticValueError('GEMINI_RESPONSE_JSON_INVALID')
    state, provider, reviewer, synthesis, observed = setup_revision(lifecycle, monkeypatch,
        responses=[failure, failure])
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['diagnostic']['code'] == 'GEMINI_RESPONSE_JSON_INVALID'
    assert [call['operation'] for call in saved['model_calls']][-2:] == [
        'plan_revision_inspection', 'plan_revision_format_retry']
    assert saved['planning_inspection']['rounds_used'] == 12
    assert len([item for item in observed if 'messages' in item]) == 2
    assert synthesis == [] and saved['modified_files'] == []


@pytest.mark.parametrize('name', ['write_workspace_file', 'run_deno_test'])
def test_revision_inspector_cannot_write_or_execute_commands(lifecycle, monkeypatch, name):
    state, provider, reviewer, synthesis, _ = setup_revision(lifecycle, monkeypatch,
        responses=[AIMessage(content='', tool_calls=[{'name': name,
            'args': {'rel_path': 'PRIVATE_REVISION_TARGET', 'content': 'PRIVATE_PAYLOAD'}, 'id': 'unsafe'}])])
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'PLAN_BLOCKED'
    assert result['diagnostic']['code'] == 'TOOL_EXECUTION_FAILED'
    assert synthesis == [] and saved['modified_files'] == []
    assert not (lifecycle.workspace/'PRIVATE_REVISION_TARGET').exists()
    assert 'PRIVATE_' not in json.dumps(saved)


@pytest.mark.parametrize('path,reason', [('absent.ts', 'SOURCE_MISSING'), ('.env', 'PATH_EXCLUDED')])
def test_revision_unavailable_source_is_feedback_and_logs_only_finite_facts(lifecycle, monkeypatch, capsys, path, reason):
    state, provider, reviewer, _, _ = setup_revision(lifecycle, monkeypatch,
        responses=[AIMessage(content='', tool_calls=[{'name': 'read_workspace_file',
            'args': {'rel_path': path}, 'id': 'missing'}])])
    with DiagnosticSession(lifecycle.state.run_id, lifecycle.context.memory_root) as session:
        result, saved = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'PLAN_BLOCKED' and saved['plan_review_count'] == 2
    assert reason in json.dumps(saved['planning_evidence'])
    records = [json.loads(line) for line in session.path.read_text().splitlines()]
    assert any(r.get('operation') == 'plan_revision_inspection' for r in records)
    assert any(r['stage'] == 'plan_revision' and r['event'] == 'inspection_round_started' for r in records)
    assert not any(path in json.dumps(r) for r in records)
    capsys.readouterr()


def test_feedback_recovery_and_restart_preserve_consumed_rounds(lifecycle, monkeypatch):
    state, provider, reviewer, _, observed = setup_revision(lifecycle, monkeypatch,
        decisions=[decision('F1'), decision('F1'), decision('F1'),
                   {'decision': 'escalate', 'findings': [{'id': 'F2', 'description': 'Fixture decision', 'kind': 'user_decision'}], 'resolved_finding_ids': []}])
    run(lifecycle, state, provider, reviewer)
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        result = graph.invoke(Command(resume={'feedback': 'Preserve the original scope and bounds.'}), lifecycle.config)
        saved = graph.get_state(lifecycle.config).values
    assert result['status'] == 'PLAN_BLOCKED'
    assert saved['plan_recovery_count'] == 1 and saved['planning_inspection']['rounds_used'] == 12
    assert len([x for x in observed if 'offered' in x]) == 1


def test_legacy_default_and_new_policy_survive_state_round_trip():
    assert CouncilState(run_id='old', task_input='old').revision_evidence_policy_version == 1
    current = CouncilState(run_id='new', task_input='new', revision_evidence_policy_version=2)
    assert CouncilState.model_validate(current.model_dump()).revision_evidence_policy_version == 2


@pytest.mark.parametrize('value', [0, 3, True, '2', 2.0, None])
def test_invalid_policy_version_is_rejected(value):
    with pytest.raises(ValueError):
        CouncilState(run_id='bad', task_input='bad', revision_evidence_policy_version=value)


def test_new_autonomous_cli_enables_policy_without_altering_legacy(lifecycle, monkeypatch, capsys):
    from council.cli import run_council_task
    monkeypatch.setattr('council.cli.ORCHESTRATION_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.GRAPH_INTEGRITY_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.GOVERNANCE_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.READINESS_POLICY_VERSION', 1)
    state, provider, reviewer, _, _ = setup_revision(lifecycle, monkeypatch,
        decisions=[{'decision': 'escalate', 'findings': [{'id': 'F1', 'description': 'Fixture decision', 'kind': 'user_decision'}], 'resolved_finding_ids': []}])
    provider.bind_tools = lambda tools: SimpleNamespace(invoke=lambda _: AIMessage(content='Inspection complete.'))
    monkeypatch.setattr('council.graph.get_llm_for_role', lambda role, *args, **kw: reviewer if role == 'reviewer' else provider)
    monkeypatch.setattr('council.cli.preflight_credentials', lambda _: {'codex-cli': True})
    assert run_council_task(prompt='fixture', workspace_root=lifecycle.workspace,
        council_root=lifecycle.context.council_root, no_input=True) == 2
    payload = json.loads(capsys.readouterr().out)
    from council.checkpoint import managed_sqlite_checkpointer
    from council.runtime_context import resolve_context
    cli_context = resolve_context(lifecycle.workspace, lifecycle.context.council_root)
    with managed_sqlite_checkpointer(context=cli_context) as saver:
        values = saver.get_tuple({'configurable': {'thread_id': payload['run_id']}}).checkpoint['channel_values']
    assert values['revision_evidence_policy_version'] == 2


def test_new_policy_initial_planning_and_revision_share_summary(lifecycle, monkeypatch):
    state, provider, reviewer, _, observed = setup_revision(lifecycle, monkeypatch, rounds=None)
    state['plan'] = None
    original = provider.bind_tools
    binds = 0
    def bind(tools):
        nonlocal binds
        binds += 1
        if binds == 1:
            return SimpleNamespace(invoke=lambda _: AIMessage(content='Initial inspection done.'))
        return original(tools)
    provider.bind_tools = bind
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'PLAN_BLOCKED'
    assert saved['planning_inspection'] == dict(rounds_used=2, round_limit=12, limit_reached=False)
    assert 'valid = Path' in json.dumps(saved['planning_evidence'])
    assert saved['planning_evidence_available'] is True
    assert len([x for x in observed if 'offered' in x]) == 1


def test_user_decision_and_resolved_findings_never_trigger_research(lifecycle, monkeypatch):
    from council.revision_evidence import prepare_revision, inspection_context
    from council.state import FindingLedgerEntry
    state = lifecycle.state
    state.revision_evidence_policy_version = 2
    from council.state import PlanningInspectionSummary
    state.planning_inspection = PlanningInspectionSummary(rounds_used=3)
    state.review_finding_ledger = [
        FindingLedgerEntry(id='F1', description='Resolved', kind='technical', status='resolved'),
        FindingLedgerEntry(id='F2', description='Ask user', kind='user_decision', status='unresolved')]
    assert inspection_context(state)['reason'] == 'NO_TECHNICAL_FINDINGS'
    prepare_revision(state, None, lifecycle.context, [], None, None)
    assert state.planning_inspection.rounds_used == 3


def test_revision_tool_permission_failure_is_terminal_and_sanitized(lifecycle, monkeypatch, capsys):
    from langchain_core.tools import tool
    @tool
    def read_workspace_file(rel_path: str) -> str:
        """Inject an actual tool-side access failure."""
        raise PermissionError('PRIVATE_REVISION_DENIAL')
    monkeypatch.setattr('council.revision_evidence.get_council_tools', lambda **kwargs: [read_workspace_file])
    state, provider, reviewer, synthesis, _ = setup_revision(lifecycle, monkeypatch)
    with DiagnosticSession(lifecycle.state.run_id, lifecycle.context.memory_root) as session:
        result, saved = run(lifecycle, state, provider, reviewer)
    assert result['diagnostic']['code'] == 'PERMISSION_DENIED'
    assert saved['tool_call_history'][-1]['tool_failure']['reason'] == 'PERMISSION_DENIED'
    assert synthesis == [] and saved['modified_files'] == []
    assert 'PRIVATE_' not in json.dumps(saved) + session.path.read_text() + capsys.readouterr().err


def test_inspection_preserves_receipt_truncation_and_reviewer_restrictions(lifecycle, monkeypatch):
    state, provider, reviewer, _, _ = setup_revision(lifecycle, monkeypatch)
    state['planning_evidence'] = ['original bounded receipt']
    state['planning_evidence_truncated'] = True
    requests = []
    original = reviewer.review_plan
    def review(request):
        requests.append(request)
        return original(request)
    reviewer.review_plan = review
    _, saved = run(lifecycle, state, provider, reviewer)
    assert saved['planning_evidence'][0] == 'original bounded receipt'
    assert saved['planning_evidence_truncated'] is True
    assert 'valid = Path' in json.dumps(requests[1]['planning_evidence'])
    assert 'execute tools' in requests[1]['instruction']


def test_policy_two_corrections_require_concrete_tasks_without_relaxing_legacy(lifecycle):
    from council.plan_review import revision_request
    state = lifecycle.state
    state.plan = lifecycle.plan
    legacy = revision_request(state, lifecycle.context)
    state.revision_evidence_policy_version = 2
    current = revision_request(state, lifecycle.context)
    assert current['instruction'].startswith(legacy['instruction'])
    assert 'producer and consumer signatures' in current['instruction']
    assert 'production-path smoke check before freezing red tests' in current['instruction']
    assert 'Only the independent reviewer may close findings' in current['instruction']


@pytest.mark.parametrize('malformed', [False, True])
def test_real_transport_parser_and_structured_synthesis_boundary(lifecycle, monkeypatch, transport, malformed):
    state, _, reviewer, _, _ = setup_revision(lifecycle, monkeypatch)
    transport.responses.append('PRIVATE_INVALID_INSPECTION' if malformed else json.dumps({
        'content': '', 'tool_calls': [{'name': 'read_workspace_file', 'args': {'rel_path': 'verify.py'}, 'id': 'read'}]}))
    if malformed:
        transport.responses.append('PRIVATE_INVALID_INSPECTION')
    else:
        transport.responses.append(lifecycle.plan.model_dump_json())
    result, saved = run(lifecycle, state, transport.model, reviewer)
    assert result['status'] == 'PLAN_BLOCKED'
    assert len(transport.requests) == 2
    assert saved['planning_inspection']['rounds_used'] == 12
    if malformed:
        assert saved['diagnostic']['code'] == 'GEMINI_RESPONSE_JSON_INVALID'
        assert saved['planning_evidence'] == []
    else:
        assert 'valid = Path' in json.dumps(saved['planning_evidence'])
    assert 'PRIVATE_INVALID' not in json.dumps(saved)


def test_unoffered_requests_are_rejected_without_new_inspection_budget(lifecycle, monkeypatch):
    calls = [{'name': 'read_workspace_file', 'args': {'rel_path': 'verify.py'}, 'id': str(i)} for i in range(17)]
    state, provider, reviewer, synthesis, _ = setup_revision(lifecycle, monkeypatch,
        responses=[AIMessage(content='', tool_calls=calls)])
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['diagnostic']['code'] == 'TOOL_EXECUTION_FAILED'
    assert saved['planning_evidence'] == [] and saved['tool_call_history'] == []
    assert saved['planning_inspection']['rounds_used'] == 12 and synthesis == []
