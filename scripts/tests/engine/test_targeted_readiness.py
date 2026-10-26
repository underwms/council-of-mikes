"""Established infrastructure is a baseline; only declared gaps create readiness gates."""
import pytest
from council.state import CouncilState,TaskItem
from council import readiness


def targeted_plan(fixture):
    plan=fixture.plan.model_copy(deep=True)
    setup=TaskItem(id='setup',specialist='the-coder',description='Resolve a concrete changed dependency',
        kind='readiness',readiness_for=[plan.tasks[1].id],target_files=['prerequisite.txt'],
        test_commands=plan.tasks[0].test_commands)
    plan.tasks.insert(1,setup)
    return plan


def test_existing_baseline_needs_no_readiness_prefix(lifecycle):
    readiness.validate(lifecycle.plan,policy_version=3)
    with pytest.raises(ValueError):readiness.validate(lifecycle.plan,policy_version=2)


def test_targeted_setup_prepares_only_its_later_consumer(lifecycle):
    plan=targeted_plan(lifecycle)
    readiness.validate(plan,policy_version=3)
    state=lifecycle.state.model_copy(update={'plan':plan,'readiness_policy_version':3,'current_task_index':0})
    readiness.guard(state)  # Existing unrelated work needs no fresh baseline proof.
    state.current_task_index=2
    with pytest.raises(RuntimeError) as caught:readiness.guard(state)
    assert caught.value.code=='READINESS_NOT_MET'
    plan.tasks[1].status='completed'
    state.test_results=[{'task_id':'setup','command_index':1,'passed':True,'exit_code':0,'expectation_met':True}]
    readiness.guard(state)


@pytest.mark.parametrize('change',['unknown','earlier','empty','red','duplicate'])
def test_targeted_readiness_keeps_structural_guards(lifecycle,change):
    plan=targeted_plan(lifecycle);probe=plan.tasks[1]
    if change=='unknown':probe.readiness_for=['unknown']
    elif change=='earlier':probe.readiness_for=[plan.tasks[0].id]
    elif change=='empty':probe.readiness_for=[]
    elif change=='red':probe.verification_phase='red'
    else:probe.readiness_for*=2
    with pytest.raises(ValueError):readiness.validate(plan,policy_version=3)


def test_current_graph_runs_feature_verification_without_a_generic_setup(current_autonomous_run):
    from council.checkpoint import managed_sqlite_checkpointer
    run=current_autonomous_run
    run.state['readiness_policy_version']=3
    run.fixture.plan.tasks.pop(0)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert run.provider.attempts=={'task-1':1,'task-2':1}
    assert len(result['execution_records'])==2
    assert all(row['expectation_met'] for row in result['execution_records'])
    assert readiness.summary(CouncilState.model_validate(result))['status']=='not_required'


def test_policy_three_context_reaches_review_revision_and_worker(current_autonomous_run):
    from council.plan_review import review_request,revision_request,strategy_request
    from council.phase_contract import execution_prompt_context
    from council.plan_validation import plan_contract
    from council.phase_contract import PhaseRoadmap,Phase,roadmap_digest
    run=current_autonomous_run;state=CouncilState.model_validate(run.state)
    state.plan=run.fixture.plan
    state.roadmap=PhaseRoadmap(title='Feature',architecture_summary='Established baseline',
        phases=[Phase(id='feature',goal='Implement requested change',affected_services=['fixture'],
            delivered_contracts=['Feature behavior'],acceptance_outcomes=['Executable feature verification'])])
    state.accepted_roadmap_sha256=roadmap_digest(state.roadmap)
    assert state.readiness_policy_version==3
    contract=plan_contract(run.fixture.context,require_readiness=True,readiness_policy_version=3)
    assert 'optional' in contract['readiness'] and 'implementation-only' in contract['readiness']
    assert 'working baseline' in execution_prompt_context(state,state.plan.tasks[0])['decision_boundary']['instruction']
    for builder in (review_request,revision_request,strategy_request):
        request=builder(state,run.fixture.context)
        assert 'working baseline' in request['instruction']
        assert 'production-path smoke check before freezing red tests' not in request['instruction']
    assert 'working baseline' in readiness.assignment_guidance(state.plan.tasks[1],3)


def test_policy_three_roundtrips_without_reinterpreting_older_policies():
    for version in (1,2,3):
        state=CouncilState(run_id='policy',task_input='Feature',readiness_policy_version=version)
        assert CouncilState.model_validate(state.model_dump()).readiness_policy_version==version
    with pytest.raises(ValueError):CouncilState(run_id='bad',task_input='Feature',revision_evidence_policy_version=3)


def test_baseline_trust_does_not_waive_failing_feature_verification(current_autonomous_run):
    from council.checkpoint import managed_sqlite_checkpointer
    run=current_autonomous_run;run.fixture.plan.tasks.pop(0)
    run.state['max_test_retries']=0  # Observe admission failure without a diagnosis-provider fixture.
    original=run.provider.run_task
    def broken(task,*args,**kwargs):
        result=original(task,*args,**kwargs)
        if task.id=='task-1':(run.fixture.workspace/task.target_files[0]).write_text('broken')
        return result
    run.provider.run_task=broken
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED'
    assert result['diagnostic']['code']=='VERIFICATION_FAILED'
    assert result['test_results'] and all(not row['expectation_met'] for row in result['test_results'])
    assert 'task-2' not in run.provider.attempts


def test_targeted_prerequisite_only_phase_keeps_explicit_scope(lifecycle):
    plan=lifecycle.plan.model_copy(deep=True)
    for task in plan.tasks:task.kind='readiness';task.readiness_for=[]
    readiness.validate(plan,policy_version=3,phase_scoped=True)
    with pytest.raises(ValueError):readiness.validate(plan,policy_version=3,phase_scoped=False)
