"""Shared information is checked at real payload and execution boundaries."""
import json

import pytest

from council.state import CouncilState, MultiSpecialistPlan, TaskItem, TestExecutionResult as ExecutionResult
from test_engine_integration import lifecycle


def test_provider_context_receipts_bind_exact_calls_without_retaining_requests(current_autonomous_run):
    from datetime import datetime
    from council.checkpoint import managed_sqlite_checkpointer
    run = current_autonomous_run
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result = run.build(saver).invoke(run.state, run.fixture.config)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    bound = [r for r in result['context_receipts'] if 'call' in r]
    assert len(bound) == len(result['model_calls'])
    for receipt, call in zip(bound, result['model_calls']):
        assert receipt['call'] == call['call']
        assert receipt['operation'] == call['operation']
        assert receipt['role'] == call['role']
        assert datetime.fromisoformat(receipt['captured_utc']).utcoffset().total_seconds() == 0
        assert len(receipt['payload_sha256']) == 64
        assert set(receipt) == {'run_id','consumer','phase_index','task_id','manifest',
            'call','operation','role','captured_utc','payload_sha256'}
    assert any('call' not in r for r in result['context_receipts'])


@pytest.mark.parametrize('metadata', [
    {'call':True,'role':'orchestrator','operation':'planning'},
    {'call':2,'role':'orchestrator','operation':'planning'},
    {'call':1,'role':'PRIVATE_ROLE','operation':'planning'},
    {'call':1,'role':'orchestrator','operation':'PRIVATE_OPERATION'},
    {'call':1,'role':'orchestrator','operation':'worker'},
    {'call':1},
])
def test_invalid_call_binding_cannot_publish_a_context_receipt(metadata):
    from council.config import resolve_model_configuration
    from council.graph_integrity import prepare_payload, record_context
    state = integrity_state()
    state.model_configuration = resolve_model_configuration(autonomous=True).model_dump(mode='json')
    payload = prepare_payload(state, 'architect', {'instruction':'PRIVATE_REQUEST'})
    with pytest.raises(Exception) as caught:
        record_context(state, 'architect', payload, **metadata)
    assert caught.value.code == 'GRAPH_CONTEXT_INVALID'
    assert state.context_receipts == []
    assert 'PRIVATE' not in str(caught.value)


def test_call_binding_fingerprints_exact_graph_payload_and_keeps_old_receipts_readable():
    from council.config import resolve_model_configuration
    from council.graph import invoke_model
    from council.graph_integrity import prepare_payload, record_context, digest
    from langchain_core.messages import AIMessage
    state = integrity_state()
    state.model_configuration = resolve_model_configuration(autonomous=True).model_dump(mode='json')
    payload = prepare_payload(state, 'architect', {'instruction':'PRIVATE_REQUEST'})
    record_context(state, 'architect', payload)
    old = state.context_receipts[0].copy()
    invoke_model(state, 'orchestrator', 'planning', lambda: AIMessage(content='PRIVATE_RESPONSE'), request=payload)
    bound = state.context_receipts[-1]
    assert bound['payload_sha256'] == digest(payload)
    assert 'PRIVATE' not in json.dumps(state.context_receipts)
    assert state.context_receipts[0] == old
    assert CouncilState.model_validate(state.model_dump()).context_receipts == state.context_receipts


def integrity_state():
    return CouncilState(run_id='integrity-run', thread_id='integrity-run',
        task_input='Required baseline truth and exact user scope.', graph_integrity_policy_version=2,
        plan=MultiSpecialistPlan(title='Work', architecture_summary='Keep the original contract', tasks=[
            TaskItem(id='work', specialist='the-coder', description='Implement one item',
                acceptance_criteria=['Preserve baseline'], target_files=['item.py'],
                test_commands=[['python', 'verify.py']])]))


@pytest.mark.parametrize('origin',['roadmap','roadmap_review'])
def test_preacceptance_arbiter_can_classify_recorded_roadmap_failure(current_autonomous_run,origin):
    from council import recovery
    from council.graph_integrity import prepare_payload,validate_payload
    from test_governor import governed_state
    state=CouncilState.model_validate(current_autonomous_run.state)
    state.roadmap=governed_state().roadmap if origin=='roadmap_review' else None
    state.accepted_roadmap_sha256=None
    state.status='PLAN_BLOCKED'
    state.diagnostic={'code':'CODEX_REVIEW_TOOL_REJECTED','graph_stage':origin}
    state.recovery_policy.version=1
    recovery.open_incident(state,current_autonomous_run.fixture.context)
    payload=prepare_payload(state,'arbiter',{'incident':state.recovery_incident.model_dump(mode='json')})
    frame=validate_payload(state,'arbiter',payload)
    assert frame['records']['accepted_contracts']['roadmap_sha256'] is None
    assert frame['records']['recovery']['incident']['origin']==origin
    for consumer in ('worker','prover','architect'):
        with pytest.raises(Exception) as error:prepare_payload(state,consumer,{})
        assert error.value.code=='GRAPH_CONTEXT_INVALID'


@pytest.mark.parametrize('mutation',['missing_incident','later_origin','wrong_run','accepted_plan','wrong_phase','stale_accepted_roadmap'])
def test_preacceptance_arbiter_exception_cannot_bypass_other_contexts(current_autonomous_run,mutation):
    from council import recovery
    from council.graph_integrity import prepare_payload
    from test_governor import governed_state,plan
    state=CouncilState.model_validate(current_autonomous_run.state)
    state.roadmap=governed_state().roadmap
    state.accepted_roadmap_sha256=None
    state.status='PLAN_BLOCKED'
    state.diagnostic={'code':'CODEX_REVIEW_TOOL_REJECTED','graph_stage':'roadmap_review'}
    state.recovery_policy.version=1
    recovery.open_incident(state,current_autonomous_run.fixture.context)
    if mutation=='missing_incident':state.recovery_incident=None
    elif mutation=='later_origin':state.recovery_incident.origin='worker'
    elif mutation=='wrong_run':state.recovery_incident.run_id='foreign'
    elif mutation=='accepted_plan':state.plan=plan();state.accepted_plan_sha256='a'*64
    elif mutation=='wrong_phase':state.current_phase_index=1
    elif mutation=='stale_accepted_roadmap':state.accepted_roadmap_sha256='a'*64
    with pytest.raises(Exception) as error:prepare_payload(state,'arbiter',{})
    assert error.value.code=='GRAPH_CONTEXT_INVALID'


def resolve_shared_reference(value, payload):
    if isinstance(value, dict) and set(value) == {'$ref'}:
        result = payload
        for key in value['$ref'].removeprefix('#/').split('/'):
            result = result[key]
        return result
    if isinstance(value, dict):
        return {key: resolve_shared_reference(item, payload) for key, item in value.items()}
    return value


@pytest.mark.parametrize('governance', [1, 2])
def test_phase_references_deliver_every_original_value_without_duplicate_artifacts(governance):
    from council.governor import initialize
    from council.graph_integrity import prepare_payload, validate_payload
    from council.phase_contract import phase_prompt_context
    from test_governor import governed_state
    state = governed_state()
    state.graph_integrity_policy_version = 2
    initialize(state)
    state.governance_policy_version = governance
    state.roadmap_inspection_evidence = ['Unique observed source ' + 'x' * 100000]
    state.roadmap_inspection_available = True
    state.roadmap_inspection_truncated = True
    original = phase_prompt_context(state)
    projection = phase_prompt_context(state, shared=True)
    payload = prepare_payload(state, 'architect', projection)
    validate_payload(state, 'architect', payload)
    assert resolve_shared_reference(projection['phase_context_references'], payload) == original
    assert json.dumps(payload).count(state.roadmap_inspection_evidence[0]) == 1
    assert len(json.dumps(projection)) < 4000
    assert state.roadmap_inspection_evidence == original['roadmap_inspection']['evidence']


def test_legacy_phase_projection_keeps_full_values():
    from council.phase_contract import phase_prompt_context
    from test_governor import governed_state
    state = governed_state()
    assert phase_prompt_context(state, shared=True) == phase_prompt_context(state)


def test_architect_delivers_phase_values_once_in_actual_model_messages(monkeypatch):
    from council import graph
    from council.governor import initialize
    from test_governor import governed_state, plan
    from types import SimpleNamespace
    state = governed_state()
    state.graph_integrity_policy_version = 2
    initialize(state)
    state.model_configuration = {'configured': True}
    state.roadmap_inspection_evidence = ['Full retained roadmap observation ' + 'y' * 100000]
    requests = []
    provider = SimpleNamespace(with_structured_output=lambda *a, **k:
        SimpleNamespace(invoke=lambda messages: requests.append(messages) or plan()))
    monkeypatch.setattr(graph, 'invoke_model', lambda state, role, operation, call, **kwargs: call())
    graph.the_architect_node(state, llm_factory=lambda role: provider)
    assert len(requests) == 1
    encoded = json.dumps(requests[0])
    assert encoded.count(state.roadmap_inspection_evidence[0]) == 1
    assert 'phase_context_references' in encoded


@pytest.mark.parametrize('shape', ['request', 'messages', 'text'])
def test_actual_payload_contains_the_required_content_and_validated_versions(shape):
    from council.graph_integrity import prepare_payload, validate_payload, seal_state
    state = integrity_state()
    seal_state(state)
    original = {} if shape == 'request' else [] if shape == 'messages' else 'Task guidance'
    payload = prepare_payload(state, 'plan_review', original)
    frame = validate_payload(state, 'plan_review', payload)
    assert frame['records']['requirement'] == state.task_input
    assert frame['records']['plan']['architecture_summary'] == state.plan.architecture_summary
    assert frame['run_id'] == state.run_id
    assert json.dumps(payload).count(state.task_input) == 1


def test_manifest_alone_does_not_count_as_content_delivery():
    from council.graph_integrity import prepare_payload, validate_payload
    state = integrity_state()
    payload = prepare_payload(state, 'plan_review', {})
    del payload['shared_context']['records']['requirement']
    with pytest.raises(Exception) as error:
        validate_payload(state, 'plan_review', payload)
    assert error.value.code == 'GRAPH_CONTEXT_INVALID'


def test_stale_or_other_run_context_is_rejected_before_model_dispatch():
    from council.graph_integrity import prepare_payload, validate_payload
    state = integrity_state()
    payload = prepare_payload(state, 'plan_revision', {})
    state.plan.architecture_summary = 'A changed draft'
    with pytest.raises(Exception) as error:
        validate_payload(state, 'plan_revision', payload)
    assert error.value.code == 'GRAPH_CONTEXT_INVALID'
    state = integrity_state()
    state.run_id = 'new-independent-run'
    with pytest.raises(Exception): validate_payload(state, 'plan_revision', payload)


def test_context_refresh_replaces_old_frame_instead_of_accumulating_snapshots():
    from council.graph_integrity import prepare_payload, validate_payload
    state = integrity_state()
    payload = prepare_payload(state, 'plan_revision', [])
    state.plan.architecture_summary = 'Updated draft'
    payload = prepare_payload(state, 'plan_revision', payload)
    assert len(payload) == 1
    assert validate_payload(state, 'plan_revision', payload)['records']['plan']['architecture_summary'] == 'Updated draft'


@pytest.mark.parametrize('mutation', ['requirement', 'plan-contract', 'history', 'policy', 'revision-history',
    'integrity-downgrade', 'observations', 'review-counter', 'self-completion'])
def test_worker_cannot_rewrite_other_nodes_information(mutation):
    from council.graph_integrity import seal_state, check_transition
    state = integrity_state()
    seal_state(state)
    state.test_results = [{'task_id': 'work', 'exit_code': 7}]
    before = state.model_copy(deep=True)
    if mutation == 'requirement': state.task_input = 'Silently replace requirements'
    if mutation == 'plan-contract': state.plan.tasks[0].acceptance_criteria = []
    if mutation == 'history': state.test_results = []
    if mutation == 'policy': state.readiness_policy_version = 2
    if mutation == 'revision-history': state.last_document_revision = {'replacement': 'not owned by worker'}
    if mutation == 'integrity-downgrade': state.graph_integrity_policy_version = 1
    if mutation == 'observations': state.planning_evidence = ['Invented source observation']
    if mutation == 'review-counter': state.plan_review_count += 1
    if mutation == 'self-completion': state.status = 'COMPLETED'
    with pytest.raises(Exception) as error: check_transition(before, state, 'worker')
    assert error.value.code == 'GRAPH_STATE_INVALID'


def test_worker_may_change_progress_without_changing_the_accepted_contract():
    from council.graph_integrity import seal_state, check_transition
    state = integrity_state()
    seal_state(state)
    before = state.model_copy(deep=True)
    state.plan.tasks[0].status = 'in_progress'
    check_transition(before, state, 'worker')


def test_verification_records_are_bound_to_command_source_and_phase(lifecycle):
    from council.graph_integrity import record_execution, matching_execution
    from council.plan_review import plan_digest
    state = lifecycle.state.model_copy(update={'graph_integrity_policy_version': 2, 'plan': lifecycle.plan})
    state.accepted_plan_sha256 = plan_digest(state.plan)
    task = state.plan.tasks[0]
    (lifecycle.workspace/task.target_files[0]).write_text('valid')
    result = ExecutionResult(command='python', passed=True, exit_code=0, expectation_met=True, command_index=1)
    record = record_execution(state, task, 1, result, lifecycle.context)
    assert matching_execution(state, task, 1, lifecycle.context).id == record.id
    task.test_commands[0].append('--different-command')
    assert matching_execution(state, task, 1, lifecycle.context) is None
    task.test_commands[0].pop()
    (lifecycle.workspace/task.target_files[0]).write_text('changed source')
    assert matching_execution(state, task, 1, lifecycle.context) is None


def test_repeated_task_id_in_another_phase_cannot_reuse_old_proof(lifecycle):
    from council.graph_integrity import record_execution, matching_execution
    from council.plan_review import plan_digest
    state = lifecycle.state.model_copy(update={'graph_integrity_policy_version': 2, 'plan': lifecycle.plan})
    state.accepted_plan_sha256 = plan_digest(state.plan)
    task = state.plan.tasks[0]
    (lifecycle.workspace/task.target_files[0]).write_text('valid')
    record_execution(state, task, 1, ExecutionResult(command='python', passed=True, exit_code=0,
        expectation_met=True, command_index=1), lifecycle.context)
    state.current_phase_index = 1
    assert matching_execution(state, task, 1, lifecycle.context) is None


def test_record_identity_is_idempotent_at_the_same_graph_step(lifecycle):
    from council.graph_integrity import record_execution
    state = lifecycle.state.model_copy(update={'graph_integrity_policy_version': 2, 'plan': lifecycle.plan})
    task = state.plan.tasks[0]
    (lifecycle.workspace/task.target_files[0]).write_text('valid')
    result = ExecutionResult(command='python', passed=False, exit_code=7, expectation_met=False, command_index=1)
    first = record_execution(state, task, 1, result, lifecycle.context)
    second = record_execution(state, task, 1, result, lifecycle.context)
    assert first.id == second.id
    assert len(state.execution_records) == 1


def test_model_dispatch_rejects_missing_required_context_before_invoking_provider():
    from council.graph import invoke_model
    from council.config import resolve_model_configuration
    state = integrity_state()
    state.model_configuration = resolve_model_configuration().model_dump(mode='json')
    calls = []
    with pytest.raises(Exception) as error:
        invoke_model(state, 'orchestrator', 'planning', lambda: calls.append('invoked'))
    assert error.value.code == 'GRAPH_CONTEXT_INVALID'
    assert not calls and not state.model_calls


def test_inspection_format_correction_delivers_the_same_intact_shared_content():
    from council.revision_evidence import invoke_inspection
    from council.graph_integrity import validate_payload
    from council.diagnostics import DiagnosticValueError
    from langchain_core.messages import AIMessage
    state = integrity_state()
    state.model_configuration = {'roles': {'orchestrator': {'provider': 'gemini-cli'}}}
    delivered = []
    class Inspector:
        calls = 0
        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1: raise DiagnosticValueError('GEMINI_RESPONSE_JSON_INVALID')
            return AIMessage(content='Inspection complete')
    def dispatch(state, role, operation, invoke, **kwargs):
        delivered.append(validate_payload(state, 'architect', kwargs['request']))
        return invoke()
    response = invoke_inspection(state, Inspector(), [], [{'role': 'user', 'content': 'Inspect only.'}],
        dispatch, 'planning_inspection', 'planning_format_retry')
    assert response.content == 'Inspection complete'
    assert len(delivered) == 2
    assert all(frame['records']['requirement'] == state.task_input for frame in delivered)
    assert delivered[0]['manifest'] == delivered[1]['manifest']


def test_scoped_readiness_runs_real_verifier_with_recovery_without_product_inventory(current_autonomous_run,monkeypatch):
    from council import proof_dependencies
    from council.checkpoint import managed_sqlite_checkpointer
    run=current_autonomous_run
    run.state['recovery_policy']={'version':1,'max_strategies_per_incident':2,'max_strategies_per_run':32}
    task=run.fixture.plan.tasks[0]
    (run.fixture.workspace/'fixture.csproj').write_text('<Project />')
    from council.delivery_contracts import ProofScope
    task.proof_scope=ProofScope(version=1,project='fixture.csproj',runtime_mutable=True)
    # Revalidate assignment as the same typed plan the graph consumes.
    from council.state import TaskItem
    task=TaskItem.model_validate(task.model_dump());run.fixture.plan.tasks[0]=task
    def forbidden(*args,**kwargs):raise AssertionError('Readiness must not request product closure')
    monkeypatch.setattr(proof_dependencies,'resolve',forbidden)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config,interrupt_after=['prover'])
    assert result.get('diagnostic') is None,result.get('diagnostic')
    rows=[r for r in result['execution_records'] if r['task_id']=='setup']
    assert rows and all(r['expectation_met'] for r in rows)
    assert all(r['source_scope']=='readiness_observation_v1' for r in rows)
    assert all(r['validity_boundary'] is not None for r in rows)
    from council.graph_integrity import matching_execution
    state=CouncilState.model_validate(result);task=state.plan.tasks[0]
    assert matching_execution(state,task,1,run.fixture.context) is not None
    state.status='FINAL_REVIEW'
    assert matching_execution(state,task,1,run.fixture.context) is None
