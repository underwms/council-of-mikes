"""Cross-node contracts are exercised through real graph/checkpoint boundaries."""
import io
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage

from council.graph import build_council_graph, execute_tool_calls
from council.state import CouncilState, MultiSpecialistPlan, PlanningInspectionSummary, FindingLedgerEntry
from council.revision_evidence import inspection_context, prepare_revision
from test_engine_integration import lifecycle, open_graph
from test_autonomous_review import setup, ACCEPT
from test_phased_orchestration import roadmap


def phased(lifecycle, monkeypatch, decisions=None, contents=None):
    state, provider, reviewer = setup(lifecycle, monkeypatch, decisions or [ACCEPT, ACCEPT], contents)
    state.update(orchestration_policy_version=2, review_protocol_version=2, max_steps=400)
    lifecycle.config['recursion_limit'] = 500
    value = roadmap()
    value.phases = value.phases[:1]
    value.phases[0].final_acceptance = True
    return state, provider, reviewer, value


def invoke_graph(lifecycle, state, provider, reviewer, **kwargs):
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else provider)
        return graph.invoke(state, lifecycle.config, **kwargs)


@pytest.mark.parametrize('restart', [False, True])
def test_roadmap_revision_receives_the_same_inspection_as_its_reviewer(lifecycle, monkeypatch, restart):
    state, provider, reviewer, value = phased(lifecycle, monkeypatch, [
        {'decision': 'revise', 'findings': ['Use the observed baseline.']}, ACCEPT,
        {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []}])
    inspections, revisions, reviews = [], [], []
    def inspect(messages):
        inspections.append(messages)
        return (AIMessage(content='', tool_calls=[{'name': 'read_workspace_file',
            'args': {'rel_path': 'verify.py'}, 'id': 'baseline'}]) if len(inspections) == 1
            else AIMessage(content='Inspection complete'))
    provider.bind_tools = lambda _: SimpleNamespace(invoke=inspect)
    def structured(schema, **kwargs):
        def invoke(messages):
            if schema is not MultiSpecialistPlan:
                revisions.append(json.dumps(messages, default=str))
            return {'parsed': lifecycle.plan if schema is MultiSpecialistPlan else value,
                    'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    original = reviewer.review_plan
    def review(request):
        reviews.append(request)
        return original(request)
    reviewer.review_plan = review
    if restart:
        paused = invoke_graph(lifecycle, state, provider, reviewer, interrupt_after=['roadmap_review'])
        assert paused['status'] == 'ROADMAP_REVISION'
        state = None
    result = invoke_graph(lifecycle, state, provider, reviewer)
    assert result['status'] == 'COMPLETED'
    assert len(revisions) == 2 and reviews[0]['planning_evidence']
    assert 'valid = Path' in revisions[1]
    assert 'evidence_available' in revisions[1] and 'evidence_truncated' in revisions[1]


@pytest.mark.parametrize('field,value,code', [
    ('target_files', ['../PRIVATE_PATH'], 'PLAN_TARGET_PATH_INVALID'),
    ('working_directory', 'missing-directory', 'PLAN_WORKING_DIRECTORY_INVALID'),
    ('test_commands', [], 'PLAN_VERIFICATION_INVALID'),
    ('specialist', 'unknown-specialist', 'PLAN_SPECIALIST_INVALID'),
    ('specialist', '../PRIVATE_SPECIALIST', 'PLAN_SPECIALIST_INVALID'),
])
def test_initial_autonomous_preflight_uses_the_same_correction_as_revision(lifecycle, monkeypatch, field, value, code):
    from test_review_convergence import configured, decision
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch, [decision(action='accept')])
    invalid = lifecycle.plan.model_copy(deep=True)
    setattr(invalid.tasks[0], field, value)
    if value == 'unknown-specialist':
        unregistered = lifecycle.context.council_root/'skills'/'unknown-specialist'
        unregistered.mkdir()
        (unregistered/'SKILL.md').write_text('PRIVATE_UNREGISTERED_INSTRUCTION')
    proposals = iter([invalid, lifecycle.plan])
    requests = []
    def structured(schema, **kwargs):
        def invoke(messages):
            requests.append(messages)
            assert not list(lifecycle.workspace.glob('target-*.txt'))
            return {'parsed': next(proposals), 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    result = invoke_graph(lifecycle, state, provider, reviewer)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert result['plan_preflight_failure_count'] == 1 and result['plan_revision_count'] == 1
    assert reviewer.calls == 1
    assert json.loads(requests[1][1]['content'])['plan_validation_feedback']['code'] == code
    assert 'PRIVATE_UNREGISTERED_INSTRUCTION' not in json.dumps(requests[1])


def revision_state(lifecycle, total):
    state = lifecycle.state.model_copy(deep=True)
    state.orchestration_policy_version = 2
    state.revision_evidence_policy_version = 2
    state.total_inspection_rounds = total
    state.planning_inspection = PlanningInspectionSummary(rounds_used=1, round_limit=4)
    state.review_finding_ledger = [FindingLedgerEntry(id='F1', description='Missing source evidence',
        kind='technical', status='unresolved')]
    return state


def test_revision_inspection_consumes_the_global_budget_before_the_call(lifecycle):
    state = revision_state(lifecycle, 31)
    observed = []
    explorer = SimpleNamespace(invoke=lambda messages: AIMessage(content='No more reads'))
    provider = SimpleNamespace(bind_tools=lambda _: explorer)
    def invoke(state, role, operation, run):
        observed.append(state.total_inspection_rounds)
        return run()
    prepare_revision(state, provider, lifecycle.context, [], invoke, None)
    assert observed == [32] and state.total_inspection_rounds == 32
    assert inspection_context(state)['reason'] == 'BUDGET_EXHAUSTED'
    prepare_revision(state, None, lifecycle.context, [], None, None)


def test_old_checkpoint_call_records_prevent_an_extra_revision_inspection(lifecycle):
    state = revision_state(lifecycle, 29)
    state.model_calls = [{'operation': 'planning_inspection'} for _ in range(29)] + [
        {'operation': 'plan_revision_inspection'} for _ in range(3)]
    assert inspection_context(state)['reason'] == 'BUDGET_EXHAUSTED'
    prepare_revision(state, None, lifecycle.context, [], None, None)


def test_transport_and_format_corrections_do_not_consume_extra_inspection_rounds(lifecycle):
    from council.call_policy import inspection_rounds_used, charge_inspection_round
    state = revision_state(lifecycle, 0)
    state.model_calls = [{'operation': 'roadmap_inspection'}, {'operation': 'roadmap_inspection_transport_retry'},
        {'operation': 'roadmap_format_retry'}, {'operation': 'roadmap_format_retry_transport_retry'}]
    assert inspection_rounds_used(state) == 1
    assert charge_inspection_round(state)
    assert state.total_inspection_rounds == 2


@pytest.mark.parametrize('total,used,limit', [(32, 0, 4), (0, 4, 4), (0, 0, 0)])
def test_exhausted_global_or_local_budget_cannot_be_charged(lifecycle, total, used, limit):
    from council.call_policy import charge_inspection_round
    state = revision_state(lifecycle, total)
    state.planning_inspection = PlanningInspectionSummary(rounds_used=used, round_limit=limit)
    before = state.model_dump()
    assert charge_inspection_round(state) is False
    assert state.model_dump() == before


def test_failed_roadmap_inspection_is_still_charged(lifecycle, monkeypatch):
    from council.diagnostics import DiagnosticRuntimeError
    state, provider, reviewer, _ = phased(lifecycle, monkeypatch)
    def fail(messages):
        raise DiagnosticRuntimeError('CLI_AUTH_REQUIRED')
    provider.bind_tools = lambda _: SimpleNamespace(invoke=fail)
    result = invoke_graph(lifecycle, state, provider, reviewer)
    assert result['status'] == 'FAILED'
    assert result['planning_inspection']['rounds_used'] == result['total_inspection_rounds'] == 1


def test_investigator_receives_the_accepted_task_and_phase_context(lifecycle, monkeypatch):
    state, provider, reviewer, value = phased(lifecycle, monkeypatch,
        [ACCEPT, {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []}],
        {'task-1': ['broken', 'valid']})
    value.architecture_summary = 'GLOBAL CONTRACT: exact before and after states'
    provider.with_structured_output = lambda schema, **kwargs: SimpleNamespace(invoke=lambda messages:
        {'parsed': lifecycle.plan if schema is MultiSpecialistPlan else value,
         'raw': AIMessage(content=''), 'parsing_error': None})
    prompts = []
    original = provider.invoke
    def invoke(messages):
        if isinstance(messages, str):prompts.append(messages)
        return original(messages)
    provider.invoke = invoke
    result = invoke_graph(lifecycle, state, provider, reviewer)
    assert result['status'] == 'COMPLETED'
    assert prompts and 'GLOBAL CONTRACT' in prompts[0]
    assert lifecycle.plan.tasks[0].description in prompts[0]
    assert 'verify.py' in prompts[0] and 'accepted_plan_sha256' in prompts[0]


@pytest.mark.parametrize('invalid', ['unknown-name', 'duplicate-id', 'missing-argument'])
def test_entire_tool_batch_is_validated_before_any_prefix_executes(lifecycle, invalid):
    from langchain_core.tools import tool
    seen = []
    @tool
    def write_workspace_file(rel_path: str, content: str) -> str:
        """Record whether an offered write tool was dispatched."""
        seen.append(rel_path)
        return 'written'
    valid = {'name': 'write_workspace_file', 'args': {'rel_path': 'prefix.txt', 'content': 'valid'}, 'id': 'one'}
    bad = {'name': 'write_workspace_file', 'args': {'rel_path': 'later.txt', 'content': 'valid'}, 'id': 'two'}
    if invalid == 'unknown-name':bad['name'] = 'PRIVATE_UNKNOWN_TOOL'
    elif invalid == 'duplicate-id':bad['id'] = 'one'
    else:bad['args'].pop('content')
    with pytest.raises((ValueError, RuntimeError)) as caught:
        execute_tool_calls(SimpleNamespace(tool_calls=[valid, bad]),
            {'write_workspace_file': write_workspace_file}, [], lifecycle.state)
    assert seen == []
    assert caught.value.tool_failure['tool_index'] == 2
    assert lifecycle.state.tool_call_history == []
    assert 'PRIVATE_' not in str(caught.value)


@pytest.mark.parametrize('code', ['PLAN_TARGET_PATH_INVALID', 'PLAN_WORKING_DIRECTORY_INVALID', 'PLAN_SPECIALIST_INVALID'])
def test_console_shows_every_repairable_preflight_failure_without_private_fields(code):
    from council.cli import emit
    class Terminal(io.StringIO):
        def isatty(self):return True
    payload = {'status': 'BLOCKED', 'findings': [], 'last_plan_validation': {
        'code': code, 'task_index': 2, 'rejected_value': 'PRIVATE_REJECTED_VALUE'}}
    out, err = io.StringIO(), Terminal()
    with patch('sys.stdout', out), patch('sys.stderr', err), patch.dict(os.environ, {'NO_COLOR': '1'}):
        emit(payload)
    assert 'Open issues (1)' in err.getvalue() and 'Task 2' in err.getvalue()
    assert code in err.getvalue() and 'PRIVATE_' not in err.getvalue()
    assert json.loads(out.getvalue()) == payload


def test_final_audit_rejects_unclosed_archived_red_evidence(lifecycle, monkeypatch):
    import hashlib
    from council.state import RedPhaseEvidence
    state, provider, reviewer, value = phased(lifecycle, monkeypatch,
        [ACCEPT, {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []}])
    frozen = lifecycle.workspace/'frozen.test.ts'
    frozen.write_text('accepted source')
    state['completed_red_phase_evidence'] = [RedPhaseEvidence(red_task_id='prior-red',
        green_task_id='prior-green', command_index=1, test_names=['prior test'],
        source_hashes={'frozen.test.ts': hashlib.sha256(frozen.read_bytes()).hexdigest()},
        closed=False).model_dump()]
    provider.with_structured_output = lambda schema, **kwargs: SimpleNamespace(invoke=lambda messages:
        {'parsed': lifecycle.plan if schema is MultiSpecialistPlan else value,
         'raw': AIMessage(content=''), 'parsing_error': None})
    result = invoke_graph(lifecycle, state, provider, reviewer)
    assert result['status'] == 'FAILED'
    assert result['diagnostic']['code'] == 'TDD_PHASE_INCOMPLETE'


def test_eight_phase_journey_keeps_local_state_and_global_budget_aligned(lifecycle, monkeypatch):
    from test_graph_readiness import prepared
    from council.phase_contract import PhaseRoadmap
    state, provider, reviewer = prepared(lifecycle, monkeypatch)
    state.update(orchestration_policy_version=2, review_protocol_version=2, max_steps=400)
    lifecycle.config['recursion_limit'] = 500
    reviewer.decisions = iter([ACCEPT] + [
        {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []} for _ in range(8)])
    phases, plans = [], []
    for index in range(8):
        phases.append({'id': f'phase-{index}', 'goal': 'Qualify setup' if index == 0 else 'Deliver one verified increment',
            'affected_services': ['fixture'], 'delivered_contracts': [f'contract-{index}'],
            'acceptance_outcomes': ['Real fixture verification passes'],
            'depends_on': [] if index == 0 else [f'phase-{index-1}'], 'final_acceptance': index == 7})
        plan = lifecycle.plan.model_copy(deep=True)
        if index == 0:
            plan.tasks = plan.tasks[:1]
            plan.tasks[0].readiness_for = []
        else:
            plan.tasks[0].target_files = []
            for task in plan.tasks[1:]:
                filename = f'phase-{index}-{task.id}.txt'
                task.target_files = [filename]
                task.test_commands[0][-1] = filename
        plans.append(plan)
    value = PhaseRoadmap(title='Eight incremental phases', architecture_summary='Preserve verified contracts', phases=phases)
    generated, inspections, investigations = [], [], []
    def inspect(messages):
        inspections.append(messages)
        return AIMessage(content='', tool_calls=[{'name': 'read_workspace_file',
            'args': {'rel_path': 'verify.py', 'start_line': 1 + (len(inspections)-1) % 4},
            'id': f'read-{len(inspections)}'}])
    provider.bind_tools = lambda _: SimpleNamespace(invoke=inspect)
    def structured(schema, **kwargs):
        def invoke(messages):
            if schema is MultiSpecialistPlan:
                plan = plans[len(generated)]
                generated.append(plan)
                provider.plan = plan
                result = plan
            else:result = value
            return {'parsed': result, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    original_run = provider.run_task
    failed = False
    def run_task(task, guidance, **kwargs):
        nonlocal failed
        result = original_run(task, guidance, **kwargs)
        if len(generated) == 4 and task.id == 'task-1' and not failed:
            failed = True
            (lifecycle.workspace/task.target_files[0]).write_text('broken')
        return result
    provider.run_task = run_task
    original_invoke = provider.invoke
    def invoke(messages):
        if isinstance(messages, str):investigations.append(messages)
        return original_invoke(messages)
    provider.invoke = invoke
    result = invoke_graph(lifecycle, state, provider, reviewer)
    assert result['status'] == 'COMPLETED', (result.get('diagnostic'), len(generated), len(inspections),
        result.get('model_calls', [])[-1].get('operation'), result.get('tool_call_history', [])[-2:])
    assert len(result['completed_phases']) == len(generated) == 8
    assert result['total_inspection_rounds'] == len(inspections) == 32
    assert result['planning_inspection']['round_limit'] == 0
    assert result['planning_evidence_available'] is False
    assert investigations and 'phase-3' in investigations[0]
    assert result['test_retry_count'] == 0


@pytest.mark.parametrize('stage', ['revision', 'strategy_reset'])
def test_pending_status_corrections_follow_the_same_policy_at_every_proposal_stage(lifecycle, monkeypatch, stage):
    from test_graph_readiness import prepared
    from test_review_convergence import decision
    state, provider, reviewer = prepared(lifecycle, monkeypatch)
    state['review_protocol_version'] = 2
    review_count = 1 if stage == 'revision' else 3
    reviewer.decisions = iter([decision('F1') for _ in range(review_count)] + [
        decision(resolved=['F1'], action='accept')])
    candidates = [lifecycle.plan.model_copy(deep=True) for _ in range(review_count + 2)]
    candidates[review_count].tasks[1].status = 'completed'
    generated = []
    def structured(schema, **kwargs):
        def invoke(messages):
            plan = candidates[len(generated)]
            plan.architecture_summary += f' proposal {len(generated)}'
            generated.append(plan)
            return {'parsed': plan, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    result = invoke_graph(lifecycle, state, provider, reviewer)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert result['plan_preflight_failure_count'] == 1
    assert result['strategy_reset_count'] == (1 if stage == 'strategy_reset' else 0)


def test_roadmap_recovery_preserves_guidance_without_spending_first_phase_recovery(lifecycle, monkeypatch):
    from langgraph.types import Command
    state, provider, reviewer, value = phased(lifecycle, monkeypatch, [
        {'decision': 'escalate', 'findings': ['Clarify the baseline.']}, ACCEPT,
        {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []}])
    feedback = 'USER DECISION: the historical baseline must be explicit.'
    phase_messages, reviews = [], []
    def structured(schema, **kwargs):
        def invoke(messages):
            if schema is MultiSpecialistPlan:phase_messages.append(json.dumps(messages, default=str))
            return {'parsed': lifecycle.plan if schema is MultiSpecialistPlan else value,
                    'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    original = reviewer.review_plan
    def review(request):
        reviews.append(request)
        return original(request)
    reviewer.review_plan = review
    blocked = invoke_graph(lifecycle, state, provider, reviewer)
    assert blocked['status'] == 'PLAN_BLOCKED'
    paused = invoke_graph(lifecycle, Command(resume={'feedback': feedback}), provider, reviewer,
                          interrupt_before=['architect'])
    assert paused['status'] == 'PLAN_PHASE'
    assert paused['human_feedback'] == feedback
    assert paused['plan_recovery_count'] == paused['recovery_revision_baseline'] == 0
    result = invoke_graph(lifecycle, None, provider, reviewer)
    assert result['status'] == 'COMPLETED'
    assert reviews[1]['user_feedback'] == feedback
    assert feedback in phase_messages[0]
