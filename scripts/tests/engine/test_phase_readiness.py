"""Prerequisite-only phases qualify later work without future task references."""
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from council.diagnostics import DiagnosticRuntimeError, DiagnosticValueError
from council.graph import build_council_graph
from council.phase_contract import roadmap_digest
from council.plan_review import review_request, revision_request
from council.plan_validation import plan_contract, validate_plan
from council.readiness import guard
from council.state import CouncilState, MultiSpecialistPlan
from test_engine_integration import lifecycle, open_graph
from test_graph_readiness import prepared
from test_phased_orchestration import roadmap


def prerequisite_plan(lifecycle, monkeypatch):
    state, provider, reviewer = prepared(lifecycle, monkeypatch)
    plan = lifecycle.plan.model_copy(deep=True)
    plan.tasks = plan.tasks[:1]
    plan.tasks[0].readiness_for = []
    return plan, state, provider, reviewer


def test_prerequisite_only_plan_is_valid_only_when_phase_scoped(lifecycle, monkeypatch):
    plan, _, _, _ = prerequisite_plan(lifecycle, monkeypatch)
    with pytest.raises(DiagnosticValueError) as caught:
        validate_plan(plan, lifecycle.context, native_coding=True, require_readiness=True)
    assert caught.value.verification['reason'] == 'READINESS_IMPLEMENTATION_MISSING'
    result = validate_plan(plan, lifecycle.context, native_coding=True, require_readiness=True, phase_scoped=True)
    assert result == plan and result is not plan


@pytest.mark.parametrize('change,reason', [
    ('future-phase', 'READINESS_PHASE_REFERENCE'),
    ('self', 'READINESS_PHASE_REFERENCE'),
    ('red', 'READINESS_GREEN_REQUIRED'),
    ('completed', 'READINESS_PENDING_REQUIRED'),
    ('no-command', 'COMMANDS_EMPTY'),
])
def test_prerequisite_only_phase_keeps_executable_local_contract(lifecycle, monkeypatch, change, reason):
    plan, _, _, _ = prerequisite_plan(lifecycle, monkeypatch)
    task = plan.tasks[0]
    if change == 'future-phase': task.readiness_for = ['backend-api-implementation']
    elif change == 'self': task.readiness_for = [task.id]
    elif change == 'red': task.verification_phase = 'red'
    elif change == 'completed': task.status = 'completed'
    elif change == 'no-command': task.test_commands = []
    with pytest.raises(DiagnosticValueError) as caught:
        validate_plan(plan, lifecycle.context, native_coding=True, require_readiness=True, phase_scoped=True)
    assert caught.value.verification['reason'] == reason


def test_mixed_phase_still_requires_local_implementation_coverage(lifecycle, monkeypatch):
    prepared(lifecycle, monkeypatch)
    lifecycle.plan.tasks[0].readiness_for = ['ui']
    with pytest.raises(DiagnosticValueError) as caught:
        validate_plan(lifecycle.plan, lifecycle.context, native_coding=True, require_readiness=True, phase_scoped=True)
    assert caught.value.verification['reason'] == 'READINESS_REFERENCE'


def test_phase_planning_review_and_revision_share_scope(lifecycle, monkeypatch):
    plan, raw, _, _ = prerequisite_plan(lifecycle, monkeypatch)
    state = CouncilState.model_validate({**raw, 'orchestration_policy_version': 2, 'plan': plan.model_dump()})
    state.roadmap = roadmap()
    state.accepted_roadmap_sha256 = roadmap_digest(state.roadmap)
    contracts = [plan_contract(lifecycle.context, require_readiness=True, phase_scoped=True),
                 review_request(state, lifecycle.context)['plan_contract'],
                 revision_request(state, lifecycle.context)['plan_contract']]
    assert all(contract['readiness'] == contracts[0]['readiness'] for contract in contracts)
    assert 'all-readiness' in contracts[0]['readiness']
    assert 'phase IDs' in contracts[0]['readiness']


@pytest.mark.parametrize('reason', ['READINESS_REFERENCE', 'READINESS_IMPLEMENTATION_MISSING'])
def test_historical_preflight_feedback_uses_current_phase_semantics(lifecycle, monkeypatch, reason):
    from council.plan_review import record_preflight_failure
    from council.verification_feedback import rejection
    plan, raw, _, _ = prerequisite_plan(lifecycle, monkeypatch)
    state = CouncilState.model_validate({**raw, 'orchestration_policy_version': 2, 'plan': plan.model_dump()})
    state.roadmap = roadmap()
    state.accepted_roadmap_sha256 = roadmap_digest(state.roadmap)
    assert record_preflight_failure(state, plan, rejection(1, reason))
    feedback = revision_request(state, lifecycle.context)['verification_correction']
    assert feedback['reason'] == reason
    assert 'all-readiness' in feedback['guidance'] and 'empty' in feedback['guidance']


def test_phase_guard_requires_real_previous_probe_evidence(lifecycle, monkeypatch):
    plan, raw, _, _ = prerequisite_plan(lifecycle, monkeypatch)
    plan.tasks.append(plan.tasks[0].model_copy(deep=True, update={'id': 'second-probe'}))
    state = CouncilState.model_validate({**raw, 'orchestration_policy_version': 2,
        'plan': plan.model_dump(), 'current_task_index': 1})
    state.plan.tasks[0].status = 'completed'
    with pytest.raises(DiagnosticRuntimeError, match='prerequisite'):
        guard(state)
    state.test_results = [{'task_id': 'setup', 'command_index': 1, 'passed': True,
                           'exit_code': 0, 'expectation_met': True}]
    guard(state)


@pytest.mark.parametrize('scenario', ['success', 'failed-probe', 'revision'])
def test_prerequisite_phase_must_verify_before_next_phase_is_planned(lifecycle, monkeypatch, scenario):
    setup_plan, state, provider, reviewer = prerequisite_plan(lifecycle, monkeypatch)
    state['orchestration_policy_version'] = 2
    state['review_protocol_version'] = 2
    reviewer.decisions = iter([{'decision': 'accept', 'findings': []},
        {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []},
        {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []}])
    feature_plan = lifecycle.plan.model_copy(deep=True)
    feature_plan.tasks[0].id = 'phase-local-check'
    feature_plan.tasks[0].target_files = []
    value = roadmap()
    value.phases[0].id = 'setup'
    value.phases[0].goal = 'Qualify execution prerequisites only'
    value.phases[1].depends_on = ['setup']
    candidates = []
    if scenario == 'revision':
        invalid = setup_plan.model_copy(deep=True)
        invalid.tasks[0].readiness_for = ['ui']
        candidates.append(invalid)
    candidates += [setup_plan, feature_plan]
    generated = []
    if scenario == 'failed-probe':
        original = provider.run_task
        def broken(task, guidance, **kwargs):
            result = original(task, guidance, **kwargs)
            (lifecycle.workspace/'prerequisite.txt').write_text('broken')
            return result
        provider.run_task = broken

    def structured(schema, **kwargs):
        def invoke(messages):
            if schema is MultiSpecialistPlan:
                result = candidates[len(generated)]
                if result is feature_plan:
                    assert (lifecycle.workspace/'prerequisite.txt').read_text() == 'valid'
                provider.plan = result
                generated.append(result)
            else:
                result = value
            return {'parsed': result, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)

    provider.with_structured_output = structured
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else provider)
        result = graph.invoke(state, lifecycle.config)
    if scenario == 'failed-probe':
        assert result['status'] == 'FAILED'
        assert result['diagnostic']['code'] == 'READINESS_FAILED'
        assert len(generated) == 1 and result['completed_phases'] == []
        assert not list(lifecycle.workspace.glob('target-*.txt'))
    else:
        assert result['status'] == 'COMPLETED', result.get('diagnostic')
        assert [item['id'] for item in result['completed_phases']] == ['setup', 'ui']
        assert [item['task_id'] for item in result['test_results']] == [
            'setup', 'phase-local-check', 'task-1', 'task-2']
        assert len(generated) == (3 if scenario == 'revision' else 2)
