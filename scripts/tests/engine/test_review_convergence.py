"""Versioned convergence policy with real graph/checkpoint boundaries."""
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command
from test_engine_integration import lifecycle, open_graph
from test_autonomous_review import setup, graph_for
from council import plan_review


def capture_planning_evidence(*args):
    assert hasattr(plan_review, 'capture_planning_evidence'), 'Inspection receipts must survive planning'
    return plan_review.capture_planning_evidence(*args)


def revision_request(*args):
    assert hasattr(plan_review, 'revision_request'), 'Revision must share review context'
    return plan_review.revision_request(*args)


def finding(identity, description='Correct this requirement.', kind='technical'):
    return {'id': identity, 'description': description, 'kind': kind}


def decision(*identities, resolved=(), action='revise'):
    return {'decision': action, 'findings': [finding(identity) for identity in identities],
            'resolved_finding_ids': list(resolved)}


ACCEPT = decision(action='accept')


def configured(lifecycle, monkeypatch, decisions, *, change=True):
    state, provider, reviewer = setup(lifecycle, monkeypatch, decisions)
    state['review_protocol_version'] = 2
    calls = 0
    messages_seen = []
    def structured(schema, **kwargs):
        nonlocal calls
        calls += 1
        plan = lifecycle.plan.model_copy(deep=True)
        if change:
            plan.architecture_summary += f' revision {calls}'
        def invoke(messages):
            messages_seen.append(messages)
            return {'parsed': plan, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    return state, provider, reviewer, messages_seen


def invoke(lifecycle, provider, reviewer, state):
    with open_graph(lifecycle, provider) as saver:
        return graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)


def test_progress_allows_four_revisions_before_acceptance(lifecycle, monkeypatch):
    responses = [decision('F1'), decision('F2', resolved=['F1']),
                 decision('F3', resolved=['F2']), decision('F4', resolved=['F3']),
                 decision(resolved=['F4'], action='accept')]
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch, responses)
    result = invoke(lifecycle, provider, reviewer, state)
    assert result['status'] == 'COMPLETED'
    assert result['plan_revision_count'] == 4
    assert result['review_no_progress_count'] == 0
    assert all(item['status'] == 'resolved' for item in result['review_finding_ledger'])


def test_rewording_same_finding_stalls_without_workers(lifecycle, monkeypatch):
    responses = [decision('F1') for _ in range(5)]
    responses[1]['findings'][0]['description'] = 'Reworded concern.'
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch, responses)
    result = invoke(lifecycle, provider, reviewer, state)
    assert result['diagnostic']['code'] == 'PLAN_REVIEW_STALLED'
    assert result['plan_review_count'] == 5
    assert result['strategy_reset_count'] == 1
    assert result['__interrupt__'][0].value['blocker_kind'] == 'stalled'
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_claimed_closures_without_plan_changes_stall(lifecycle, monkeypatch):
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch,
        [decision('F1'), decision('F2', resolved=['F1']), decision('F3', resolved=['F2']),
         decision('F3'), decision('F3')], change=False)
    result = invoke(lifecycle, provider, reviewer, state)
    assert result['diagnostic']['code'] == 'PLAN_REVIEW_STALLED'


def test_progress_cannot_bypass_finite_ceiling(lifecycle, monkeypatch):
    responses = [decision('F1')]
    responses += [decision(f'F{n}', resolved=[f'F{n-1}']) for n in range(2, 9)]
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch, responses)
    result = invoke(lifecycle, provider, reviewer, state)
    assert result['diagnostic']['code'] == 'PLAN_REVIEW_EXHAUSTED'
    assert result['plan_review_count'] == 8
    assert result['plan_revision_count'] == 7
    assert result['strategy_reset_count'] == 1
    assert result['__interrupt__'][0].value['blocker_kind'] == 'budget_exhausted'
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_budget_exhaustion_uses_one_architect_reset_then_independent_review(lifecycle, monkeypatch):
    responses = [decision('F1')]
    responses += [decision(f'F{n}', resolved=[f'F{n-1}']) for n in range(2, 7)]
    responses += [decision(resolved=['F6'], action='accept')]
    state, provider, reviewer, messages_seen = configured(lifecycle, monkeypatch, responses)
    result = invoke(lifecycle, provider, reviewer, state)
    assert result['status'] == 'COMPLETED'
    assert result['strategy_reset_count'] == 1
    assert result['plan_review_count'] == 7
    assert result['plan_revision_count'] == 6
    assert [call['operation'] for call in result['model_calls']].count('strategy_reset') == 1
    strategy_messages = next(str(messages) for messages in messages_seen
                             if 'circular prerequisite' in str(messages).lower())
    assert all(value in strategy_messages for value in
               ('finding_ledger', 'F6', 'target-1.txt', 'evidence_truncated', state['task_input']))


def test_no_progress_uses_reset_once_before_hard_stop(lifecycle, monkeypatch):
    responses = [decision('F1'), decision('F1'), decision('F1'),
                 decision('F1'), decision('F1')]
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch, responses)
    result = invoke(lifecycle, provider, reviewer, state)
    assert result['status'] == 'PLAN_BLOCKED'
    assert result['strategy_reset_count'] == 1
    assert [call['operation'] for call in result['model_calls']].count('strategy_reset') == 1
    assert result['plan_review_count'] <= 8
    assert not list(lifecycle.workspace.glob('target-*.txt'))


@pytest.mark.parametrize('invalid', [
    decision('F2'), decision('F1', resolved=['unknown']),
    decision('F1', 'F1'), decision('F1', resolved=['F1']),
    decision(action='accept'), decision('F1', action='escalate'),
])
def test_unaccounted_or_invalid_findings_block_without_dispatch(lifecycle, monkeypatch, invalid):
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch, [decision('F1'), invalid, invalid])
    result = invoke(lifecycle, provider, reviewer, state)
    assert result['status'] == 'PLAN_BLOCKED'
    assert result['diagnostic']['code'] == 'PLAN_REVIEW_INVALID'
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_resolved_id_cannot_be_reintroduced(lifecycle, monkeypatch):
    responses = [decision('F1'), decision('F2', resolved=['F1']), decision('F1', resolved=['F2'])]
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch, responses)
    result = invoke(lifecycle, provider, reviewer, state)
    assert result['diagnostic']['code'] == 'PLAN_REVIEW_INVALID'


def test_user_decision_escalates_with_specific_reason(lifecycle, monkeypatch):
    response = decision('F1', action='escalate')
    response['findings'][0]['kind'] = 'user_decision'
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch, [response])
    result = invoke(lifecycle, provider, reviewer, state)
    payload = result['__interrupt__'][0].value
    assert payload['blocker_kind'] == 'user_decision'
    assert payload['finding_ledger'][0]['id'] == 'F1'
    assert result['plan_revision_count'] == 0


def test_restart_keeps_streak_and_feedback_starts_new_attempt(lifecycle, monkeypatch):
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch,
        [decision('F1'), decision('F1'), decision('F1'), decision('F1'), decision('F1'), ACCEPT])
    first = invoke(lifecycle, provider, reviewer, state)
    assert first['review_no_progress_count'] == 2
    assert first['strategy_reset_count'] == 1
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        still_blocked = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
        assert still_blocked['review_no_progress_count'] == 2
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(
            Command(resume={'feedback': 'Use the original scope.'}), lifecycle.config)
    assert result['status'] == 'COMPLETED'
    assert result['plan_recovery_count'] == 1
    assert result['review_no_progress_count'] == 0


def test_shared_evidence_and_guidance_reach_revision(lifecycle, monkeypatch):
    from council.plan_review import review_request
    from council.state import CouncilState
    state = lifecycle.state
    state.plan = lifecycle.plan
    capture_planning_evidence(state, {'name': 'read_workspace_file', 'args': {'rel_path': 'verify.py'}}, 'observed source')
    state.planning_evidence_available = True
    reviewed = review_request(state, lifecycle.context)
    revised = revision_request(state, lifecycle.context)
    assert reviewed['guidance'] == revised['guidance']
    assert reviewed['planning_evidence'] == revised['planning_evidence']
    assert 'observed source' in json.dumps(revised['planning_evidence'])
    restored = CouncilState.model_validate(state.model_dump(mode='json'))
    assert restored.planning_evidence == state.planning_evidence


def test_receipt_bounds_are_utf8_and_truncation_is_explicit(lifecycle):
    state = lifecycle.state
    for _ in range(100):
        capture_planning_evidence(state, {'name': 'read_workspace_file', 'args': {'path': 'x'*4000}}, '\u2603'*20000)
    assert state.planning_evidence_truncated
    assert len(state.planning_evidence) <= 64
    assert all(len(record.encode('utf-8')) <= 16384 for record in state.planning_evidence)
    assert sum(len(record.encode('utf-8')) for record in state.planning_evidence) <= 131072


def test_legacy_context_never_claims_observed_evidence(lifecycle):
    from council.plan_review import review_request
    lifecycle.state.plan = lifecycle.plan
    request = review_request(lifecycle.state, lifecycle.context)
    assert request['evidence_available'] is False
    assert request['planning_evidence'] == []
    assert lifecycle.state.review_protocol_version == 1


def test_observed_tool_receipt_survives_sqlite_and_reaches_reviewer(lifecycle, monkeypatch):
    state, provider, reviewer, revision_messages = configured(lifecycle, monkeypatch,
        [decision('F1'), decision(resolved=['F1'], action='accept')])
    class Inspector:
        calls = 0
        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(content='', tool_calls=[{'name': 'read_workspace_file',
                    'args': {'rel_path': 'verify.py'}, 'id': 'evidence-read', 'type': 'tool_call'}])
            return AIMessage(content='Inspection complete.')
    provider.bind_tools = lambda tools: Inspector()
    requests = []
    original = reviewer.review_plan
    def review(request):
        requests.append(request)
        return original(request)
    reviewer.review_plan = review
    result = invoke(lifecycle, provider, reviewer, state)
    assert result['status'] == 'COMPLETED'
    assert result['planning_evidence_available']
    assert 'valid = Path' in json.dumps(result['planning_evidence'])
    assert requests[0]['planning_evidence'] == requests[1]['planning_evidence']
    revision = json.loads(revision_messages[1][1]['content'])
    assert revision['planning_evidence'] == result['planning_evidence']
    with open_graph(lifecycle, provider) as saver:
        saved = graph_for(lifecycle, saver, provider, reviewer).get_state(lifecycle.config).values
    assert saved['planning_evidence'] == result['planning_evidence']


def test_planning_blocked_event_never_logs_findings_or_receipts(lifecycle, monkeypatch, capsys):
    from council.diagnostics import DiagnosticSession
    response = decision('F1', action='escalate')
    response['findings'][0].update(kind='user_decision', description='PRIVATE_FINDING')
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch, [response])
    state['planning_evidence'] = ['PRIVATE_RECEIPT']
    with DiagnosticSession(lifecycle.state.run_id, lifecycle.context.memory_root):
        invoke(lifecycle, provider, reviewer, state)
    console = capsys.readouterr().err
    assert 'planning_blocked' in console
    assert 'approval_waiting' not in console
    assert 'PRIVATE_FINDING' not in console and 'PRIVATE_RECEIPT' not in console


def test_new_cli_run_uses_protocol_two_without_stdin(lifecycle, monkeypatch, capsys):
    from council.cli import run_council_task
    # Isolate the 0.2.19 review protocol; readiness CLI activation has its own lifecycle test.
    monkeypatch.setattr('council.cli.READINESS_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.ORCHESTRATION_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.GRAPH_INTEGRITY_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.GOVERNANCE_POLICY_VERSION', 1)
    _, provider, reviewer, _ = configured(lifecycle, monkeypatch, [ACCEPT])
    monkeypatch.setattr('council.graph.get_llm_for_role', lambda role, *args, **kwargs:
        reviewer if role == 'reviewer' else provider)
    monkeypatch.setattr('council.cli.preflight_credentials', lambda _: {'codex-cli': True})
    monkeypatch.setattr('builtins.input', lambda *args: pytest.fail('No routine input'))
    assert run_council_task(prompt='fixture', workspace_root=lifecycle.workspace,
        council_root=lifecycle.context.council_root, no_input=True) == 0
    assert json.loads(capsys.readouterr().out)['review_protocol_version'] == 2


def test_receipt_count_bound_and_state_size_validation(lifecycle):
    from council.state import CouncilState
    for number in range(65):
        capture_planning_evidence(lifecycle.state, {'name': 'read', 'args': {}}, str(number))
    assert len(lifecycle.state.planning_evidence) == 64
    assert lifecycle.state.planning_evidence_truncated
    for records in [['x'*16385], ['x'*16000]*9]:
        with pytest.raises(ValueError):
            CouncilState(run_id='fixture', task_input='fixture', planning_evidence=records)


@pytest.mark.parametrize('content', [None, 'x'*24001,
    json.dumps({'decision': 'accept', 'findings': [finding('F1')], 'resolved_finding_ids': []}),
    json.dumps({'decision': 'revise', 'findings': [finding('bad id')], 'resolved_finding_ids': []}),
    json.dumps({'decision': 'revise', 'findings': [finding('F1', '  ')], 'resolved_finding_ids': []}),
    json.dumps({'decision': 'revise', 'findings': [finding('F1')], 'resolved_finding_ids': ['F2', 'F2']})])
def test_protocol_two_parser_rejects_malformed_decisions(content):
    with pytest.raises(ValueError) as caught:
        plan_review.parse_review(SimpleNamespace(content=content), 2)
    assert caught.value.code == 'PLAN_REVIEW_INVALID'


@pytest.mark.parametrize('stage', ['review', 'revision'])
def test_protocol_two_persisted_ceiling_guards(lifecycle, monkeypatch, stage):
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch, [])
    state.update(plan=lifecycle.plan.model_dump(), plan_review_count=6, plan_revision_count=5)
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        if stage == 'revision':
            graph.update_state(lifecycle.config, state, as_node='plan_blocked')
            result = graph.invoke(None, lifecycle.config)
        else:
            result = graph.invoke(state, lifecycle.config)
    assert result['diagnostic']['code'] == 'PLAN_REVIEW_EXHAUSTED'
    assert reviewer.calls == 0


def test_ledger_ceiling_is_validated_before_state_mutation(lifecycle):
    from council.state import FindingLedgerEntry, PlanReviewDecisionV2
    lifecycle.state.plan = lifecycle.plan
    lifecycle.state.review_finding_ledger = [FindingLedgerEntry(**finding(f'F{n}'), status='resolved')
        for n in range(1, 73)]
    with pytest.raises(ValueError) as caught:
        plan_review.reconcile_findings(lifecycle.state, PlanReviewDecisionV2.model_validate(decision('F73')))
    assert caught.value.code == 'PLAN_REVIEW_INVALID'
    assert len(lifecycle.state.review_finding_ledger) == 72
