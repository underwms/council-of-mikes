"""Approved architecture and source receipts survive scoped phase planning."""
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from council.state import CouncilState, MultiSpecialistPlan
from council.phase_contract import roadmap_digest
from council.plan_review import review_request, revision_request, strategy_request
from test_engine_integration import lifecycle, open_graph
from test_autonomous_review import setup, ACCEPT
from test_phased_orchestration import roadmap


@pytest.mark.parametrize('build_request', [review_request, revision_request, strategy_request])
def test_current_phase_consumers_distinguish_start_permission_from_finished_proof(lifecycle, build_request):
    state = CouncilState(run_id='ownership', task_input='Approved outcome', plan=lifecycle.plan,
        readiness_policy_version=2, orchestration_policy_version=2, roadmap=roadmap())
    state.accepted_roadmap_sha256 = roadmap_digest(state.roadmap)
    payload = build_request(state, lifecycle.context)
    boundary = payload['plan_contract']['decision_boundary']
    assert boundary['assessment'] == 'start_bounded_work'
    assert boundary['scope'] == 'current_phase'
    assert boundary['owners']['reversible_implementation'] == 'engineer'
    assert boundary['owners']['semantic_review'] == 'reviewer'
    assert boundary['completion'] == 'current_execution_and_acceptance_evidence'
    assert 'Equivalent coverage is sufficient' in boundary['instruction']


def test_real_graph_delivers_role_authority_and_one_shared_frame(current_autonomous_run):
    from copy import deepcopy
    from council.checkpoint import managed_sqlite_checkpointer
    from council.graph_integrity import _MARKER, _message_frame
    from council.plan_review import plan_digest
    run = current_autonomous_run
    planned, reviewed, worked = [], [], []
    original_structured = run.provider.with_structured_output
    original_review, original_worker = run.reviewer.review_plan, run.provider.run_task
    def structured(schema, **kwargs):
        binding = original_structured(schema, **kwargs)
        def invoke(messages):
            if schema is MultiSpecialistPlan:
                planned.append(deepcopy(messages))
            return binding.invoke(messages)
        return SimpleNamespace(invoke=invoke)
    def review(request):
        if 'plan_contract' in request:
            reviewed.append(deepcopy(request))
        return original_review(request)
    def work(task, guidance, **kwargs):
        worked.append((task.id, guidance))
        return original_worker(task, guidance, **kwargs)
    run.provider.with_structured_output = structured
    run.reviewer.review_plan, run.provider.run_task = review, work
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result = run.build(saver).invoke(run.state, run.fixture.config)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    text = next(m['content'] for m in planned[0] if isinstance(m, dict)
        and 'Required plan contract: ' in m.get('content', ''))
    contract, _ = json.JSONDecoder().raw_decode(text.split('Required plan contract: ', 1)[1])
    assert contract['decision_boundary'] == reviewed[0]['plan_contract']['decision_boundary']
    assert sum(_message_frame(m) is not None for m in planned[0]) == 1
    expected_plan = plan_digest(run.fixture.plan)
    for task_id, guidance in worked:
        assert guidance.count(_MARKER) == 1
        frame = json.loads(guidance.rsplit(_MARKER, 1)[1])
        assert frame['records']['accepted_contracts']['plan_sha256'] == expected_plan
        assert frame['records']['task']['id'] == task_id
        assert '"assessment": "start_bounded_work"' in guidance
        assert 'reversible implementation details' in guidance
        assert 'suitable observed repository patterns' in guidance


def test_start_boundary_respects_legacy_policy_and_current_plan_scope(lifecycle):
    from council.plan_validation import plan_contract
    from council.phase_contract import execution_prompt_context
    state = CouncilState(run_id='compatibility', task_input='Approved outcome', plan=lifecycle.plan)
    task = lifecycle.plan.tasks[0]
    assert 'decision_boundary' not in plan_contract(lifecycle.context)
    assert 'decision_boundary' not in execution_prompt_context(state, task)
    state.readiness_policy_version = 2
    assert plan_contract(lifecycle.context, require_readiness=True)['decision_boundary']['scope'] == 'current_plan'
    assert execution_prompt_context(state, task)['decision_boundary']['scope'] == 'current_plan'


@pytest.mark.parametrize('build_request', [review_request, revision_request, strategy_request])
def test_phase_review_consumers_receive_approved_blueprint_without_mutating_state(lifecycle, build_request):
    value = roadmap(architecture_summary='GLOBAL CONTRACT: stable historical tier identity')
    state = CouncilState(run_id='lineage', task_input='original story', plan=lifecycle.plan,
        orchestration_policy_version=2, roadmap=value, accepted_roadmap_sha256=roadmap_digest(value))
    before = state.model_dump(mode='json')
    payload = build_request(state, lifecycle.context)
    assert payload['approved_roadmap'] == value.model_dump(mode='json')
    assert payload['approved_roadmap_sha256'] == state.accepted_roadmap_sha256
    assert payload['requirement'] == 'original story'
    assert payload['roadmap_inspection']['available'] is False
    assert state.model_dump(mode='json') == before


def test_phase_review_rejects_a_blueprint_changed_after_acceptance(lifecycle):
    value = roadmap()
    state = CouncilState(run_id='lineage', task_input='story', plan=lifecycle.plan,
        orchestration_policy_version=2, roadmap=value, accepted_roadmap_sha256=roadmap_digest(value))
    state.roadmap.architecture_summary = 'unreviewed replacement'
    with pytest.raises(RuntimeError) as caught:
        review_request(state, lifecycle.context)
    assert caught.value.code == 'PLAN_ACCEPTANCE_INVALID'


def test_roadmap_receipts_reach_reviewer_planner_and_checkpoint(lifecycle, monkeypatch):
    from council.graph import build_council_graph
    state, provider, reviewer = setup(lifecycle, monkeypatch, [ACCEPT, ACCEPT])
    state['orchestration_policy_version'] = 2
    value = roadmap(architecture_summary='GLOBAL CONTRACT: stable historical tier identity')
    value.phases = value.phases[:1]
    value.phases[0].final_acceptance = True
    observations, reviews, phase_prompts, worker_guidance = [], [], [], []
    def inspect(messages):
        observations.append(messages)
        if len(observations) == 1:
            return AIMessage(content='', tool_calls=[dict(name='read_workspace_file',
                args={'rel_path': 'verify.py'}, id='baseline', type='tool_call')])
        return AIMessage(content='Inspection done')
    provider.bind_tools = lambda _: SimpleNamespace(invoke=inspect)
    def structured(schema, **kwargs):
        def invoke(messages):
            if schema is MultiSpecialistPlan:
                phase_prompts.append(json.dumps(messages, default=str))
            return {'parsed': lifecycle.plan if schema is MultiSpecialistPlan else value,
                    'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    original_review = reviewer.review_plan
    def review(request):
        reviews.append(request)
        return original_review(request)
    reviewer.review_plan = review
    original_run = provider.run_task
    def run_task(task, guidance, **kwargs):
        worker_guidance.append(guidance)
        return original_run(task, guidance, **kwargs)
    provider.run_task = run_task
    with open_graph(lifecycle, provider) as saver:
        result = build_council_graph(checkpointer=saver, context=lifecycle.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else provider).invoke(state, lifecycle.config)
    assert result['status'] == 'COMPLETED'
    assert reviews[0]['planning_evidence']
    receipts = reviews[0]['planning_evidence']
    assert reviews[1]['roadmap_inspection']['evidence'] == receipts
    assert 'GLOBAL CONTRACT' in phase_prompts[0] and 'read_workspace_file' in phase_prompts[0]
    assert worker_guidance and all('GLOBAL CONTRACT' in guidance for guidance in worker_guidance)
    saved = CouncilState.model_validate(result)
    assert saved.roadmap_inspection_evidence == receipts
    assert saved.roadmap_inspection_available is True
    assert saved.planning_evidence == []
