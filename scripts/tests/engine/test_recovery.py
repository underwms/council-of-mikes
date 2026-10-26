"""Recovery exercises real graph/checkpoint/verifier boundaries in isolated workspaces."""
from types import SimpleNamespace

import pytest

from council.checkpoint import managed_sqlite_checkpointer
from council.diagnostics import DiagnosticRuntimeError
from council.state import CouncilState
from test_codex_cli import native,completed


def arbiter_input(messages):
    import json
    assert isinstance(messages,list)
    return next(value for message in messages if isinstance(message,dict)
        and isinstance(value:=json.loads(message['content']),dict) and 'incident' in value)


def test_real_arbiter_node_uses_actual_codex_chat_adapter(current_autonomous_run,native):
    from council.codex_chat import CodexCLIChatModel
    from council.recovery_contracts import RecoveryDecision
    import json
    run=enable(current_autonomous_run);tool_failure_once(run)
    fallback=run.provider.with_structured_output
    settings,_,_,process,_=native
    adapter=CodexCLIChatModel('gpt-6.1-sol',settings,run.fixture.context)
    def structured(schema,**kwargs):
        if schema is not RecoveryDecision:return fallback(schema,**kwargs)
        def invoke(request):
            # Accept the old shape only to reproduce its failure in the actual adapter.
            incident=request['incident'] if isinstance(request,dict) else next(
                json.loads(m['content'])['incident'] for m in request
                if isinstance(m,dict) and 'incident' in json.loads(m['content']))
            process['events']=completed()
            process['events'][-2]['item']['text']=json.dumps({'incident_id':incident['id'],
                'action':'verify_partial','reason':'retained_sources_match',
                'evidence_ids':incident['evidence_ids'],'limitations':[]})
            return adapter.with_structured_output(schema,include_raw=True).invoke(request)
        return SimpleNamespace(invoke=invoke)
    run.provider.with_structured_output=structured
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config,interrupt_after=['arbiter'])
    assert result['status']=='RECOVERY_ADMIT',result.get('diagnostic')
    assert result['model_calls'][-1]['operation']=='arbiter'
    assert result['model_calls'][-1]['status']=='succeeded'
    assert result['recovery_incident']['decision']['action']=='verify_partial'


def enable(run):
    run.state['recovery_policy'] = {'version': 1, 'max_strategies_per_incident': 2,
        'max_strategies_per_run': 32}
    return run


def test_recovery_setup_failure_preserves_initiating_cause_without_model_dispatch(current_autonomous_run, monkeypatch):
    from council import recovery
    run = enable(current_autonomous_run)
    def fail_worker(*args, **kwargs):
        raise RuntimeError('private worker setup detail')
    def fail_sources(*args, **kwargs):
        raise DiagnosticRuntimeError('NATIVE_INVENTORY_LIMIT')
    run.provider.run_task = fail_worker
    monkeypatch.setattr(recovery, 'source_hashes', fail_sources)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result = run.build(saver).invoke(run.state, run.fixture.config)
    assert result['status'] == 'FAILED'
    assert result['diagnostic']['code'] == 'NATIVE_INVENTORY_LIMIT'
    assert result['diagnostic']['initiating_failure'] == {
        'code': 'INTERNAL_ERROR', 'graph_stage': 'worker'}
    assert result['diagnostic']['graph_stage'] == 'arbiter'
    assert result['recovery_incident'] is None
    assert not any(c['operation'] == 'arbiter' for c in result['model_calls'])
    assert result['execution_records'] == []
    assert 'private worker setup detail' not in str(result)


def tool_failure_once(run, *, invalid=False, action='verify_partial'):
    from council.diagnostics import DiagnosticValueError
    from council.recovery_contracts import RecoveryDecision
    original=run.provider.run_task
    original_structured=run.provider.with_structured_output
    seen=[]
    def dispatch(task,*args,**kwargs):
        seen.append(task.id)
        result=original(task,*args,**kwargs)
        if len(seen)==1:
            if invalid:(run.fixture.workspace/task.target_files[0]).write_text('invalid')
            raise DiagnosticValueError('CODEX_TOOL_FAILED')
        return result
    def structured(schema,**kwargs):
        if schema is not RecoveryDecision:return original_structured(schema,**kwargs)
        return SimpleNamespace(invoke=lambda request:{'parsed':RecoveryDecision(
            incident_id=arbiter_input(request)['incident']['id'],action=action,
            reason='retained_sources_match' if action=='verify_partial' else 'cause_unproven',
            evidence_ids=arbiter_input(request)['incident']['evidence_ids']),'raw':None,'parsing_error':None})
    run.provider.run_task=dispatch
    run.provider.with_structured_output=structured
    return seen


def test_current_failed_native_tool_reaches_real_arbiter_and_prover_without_replaying_worker(current_autonomous_run):
    run=enable(current_autonomous_run);seen=tool_failure_once(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert seen==['setup','task-1','task-2']
    assert len([c for c in result['model_calls'] if c['operation']=='arbiter'])==1
    events=result['recovery_history']
    assert events[0]['category']=='tool_failure'
    assert [e['outcome'] for e in events]==['opened','admitted','dispatched','resolved']
    assert events[1]['action']=='verify_partial'
    assert all(r['expectation_met'] for r in result['execution_records'])


def test_failed_native_tool_partial_defect_uses_real_investigator_and_bounded_repair(legacy_monolithic_run):
    run=enable(legacy_monolithic_run);seen=tool_failure_once(run,invalid=True);install_diagnosis(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert seen==['task-1','task-1','task-2']
    assert [r['exit_code'] for r in result['execution_records']]==[7,0,0]
    assert any(c['operation']=='arbiter' for c in result['model_calls'])


def test_failed_native_tool_arbiter_can_stop_without_forging_verification(current_autonomous_run):
    run=enable(current_autonomous_run);seen=tool_failure_once(run,action='stop')
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED'
    assert result['diagnostic']['code']=='CODEX_TOOL_FAILED'
    assert seen==['setup'] and result['execution_records']==[]
    assert result['recovery_history'][-1]['outcome']=='stopped'


def test_failed_native_tool_admission_rejects_sources_changed_after_arbiter(current_autonomous_run):
    run=enable(current_autonomous_run);seen=tool_failure_once(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        graph=run.build(saver)
        paused=graph.invoke(run.state,run.fixture.config,interrupt_after=['arbiter'])
        assert paused['recovery_incident']['category']=='tool_failure'
        target=paused['plan']['tasks'][0]['target_files'][0]
        (run.fixture.workspace/target).write_text('changed outside worker observation')
        result=graph.invoke(None,run.fixture.config)
    assert result['status']=='FAILED' and result['diagnostic']['code']=='RECOVERY_REJECTED'
    assert seen==['setup'] and result['execution_records']==[]


def test_failed_native_tool_observation_rejects_unrelated_intervening_model_call(current_autonomous_run):
    from council import recovery
    run=enable(current_autonomous_run);tool_failure_once(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        raw=run.build(saver).invoke(run.state,run.fixture.config,interrupt_after=['arbiter'])
    state=CouncilState.model_validate(raw)
    assert recovery.observation_matches(state,run.fixture.context)
    state.model_calls[-1]['operation']='planning'
    assert not recovery.observation_matches(state,run.fixture.context)


def test_current_preacceptance_review_failure_reaches_arbiter_without_approving_work(current_autonomous_run):
    from council.recovery_contracts import RecoveryDecision
    run=enable(current_autonomous_run)
    def fail_review(request):raise DiagnosticRuntimeError('CODEX_REVIEW_TOOL_REJECTED')
    run.reviewer.review_plan=fail_review
    original=run.provider.with_structured_output
    def structured(schema,**kwargs):
        if schema is not RecoveryDecision:return original(schema,**kwargs)
        return SimpleNamespace(invoke=lambda request:{'parsed':RecoveryDecision(
            incident_id=arbiter_input(request)['incident']['id'],action='stop',reason='cause_unproven',
            evidence_ids=arbiter_input(request)['incident']['evidence_ids']),'raw':None,'parsing_error':None})
    run.provider.with_structured_output=structured
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED'
    assert result['diagnostic']['code']=='CODEX_REVIEW_TOOL_REJECTED'
    assert len([call for call in result['model_calls'] if call['operation']=='arbiter'])==1
    assert [entry['outcome'] for entry in result['recovery_history']]==['opened','admitted','dispatched','stopped']
    assert result['accepted_roadmap_sha256'] is None and result['accepted_plan_sha256'] is None
    assert not run.provider.attempts and not result['execution_records']


def timeout_once(run, *, valid=True):
    original = run.provider.run_task
    seen = []
    def dispatch(task, *args, **kwargs):
        seen.append(task.id)
        result = original(task, *args, **kwargs)
        if len(seen) == 1:
            if not valid:
                (run.fixture.workspace/task.target_files[0]).write_text('invalid')
            raise DiagnosticRuntimeError('CLI_TIMEOUT')
        return result
    run.provider.run_task = dispatch
    return seen


def test_timeout_partial_work_is_verified_without_repeating_coder(legacy_monolithic_run):
    run=enable(legacy_monolithic_run)
    seen=timeout_once(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert seen==['task-1','task-2']
    assert any(c['status']=='failed' for c in result['model_calls'])
    assert len(result['execution_records'])==2
    assert result['recovery_history'][-1]['outcome']=='resolved'


def test_disabled_policy_preserves_terminal_timeout(legacy_monolithic_run):
    run=legacy_monolithic_run
    timeout_once(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED'
    assert result['diagnostic']['code']=='CLI_TIMEOUT'


@pytest.mark.parametrize('boundary',['arbiter','recovery_admit','recovery_dispatch','prover'])
def test_restart_at_recovery_boundary_retains_action_and_history(legacy_monolithic_run,boundary):
    run=enable(legacy_monolithic_run);seen=timeout_once(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        graph=run.build(saver)
        paused=graph.invoke(run.state,run.fixture.config,interrupt_after=[boundary])
        assert paused['status']!='COMPLETED'
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(None,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert seen==['task-1','task-2']
    assert [r['outcome'] for r in result['recovery_history']]==['opened','admitted','dispatched','resolved']


@pytest.mark.parametrize('boundary',['arbiter','recovery_admit','recovery_dispatch'])
def test_external_source_edit_rejects_recovery_before_verification(legacy_monolithic_run,boundary):
    run=enable(legacy_monolithic_run);seen=timeout_once(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        graph=run.build(saver)
        graph.invoke(run.state,run.fixture.config,interrupt_after=[boundary])
        (run.fixture.workspace/'target-1.txt').write_text('external PR edit')
        result=graph.invoke(None,run.fixture.config)
    assert result['status']=='FAILED'
    assert result['diagnostic']['code']=='RECOVERY_REJECTED'
    assert result['execution_records']==[]
    assert seen==['task-1']


def test_global_recovery_budget_is_not_reset_on_restart(legacy_monolithic_run):
    from council.recovery_contracts import RecoveryEvent
    run=enable(legacy_monolithic_run);timeout_once(run)
    run.state['recovery_policy']['max_strategies_per_run']=1
    run.state['recovery_history']=[RecoveryEvent(incident_id='a'*64,lineage='b'*64,
        outcome='admitted',action='verify_partial',step=0).model_dump()]
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED'
    assert result['diagnostic']['code']=='RECOVERY_EXHAUSTED'
    assert len([e for e in result['recovery_history'] if e['outcome']=='admitted'])==1
    assert not result['execution_records']
    assert result['recovery_history'][-1]['outcome']=='rejected'


def test_legacy_sealed_checkpoint_keeps_original_identity(legacy_monolithic_run):
    from council.graph_integrity import seal_state
    run=legacy_monolithic_run
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        raw=run.build(saver).invoke(run.state,run.fixture.config,interrupt_after=['plan_review'])
    identity=raw['run_identity_sha256']
    for field in ('recovery_policy','recovery_incident','recovery_history','worker_observation'):
        raw.pop(field,None)
    state=CouncilState.model_validate(raw)
    seal_state(state)
    assert state.run_identity_sha256==identity
    assert state.recovery_policy.version==0


def test_arbiter_cannot_change_sealed_policy_or_forge_verification(legacy_monolithic_run):
    from council.graph_integrity import check_transition
    run=enable(legacy_monolithic_run);timeout_once(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        raw=run.build(saver).invoke(run.state,run.fixture.config,interrupt_after=['arbiter'])
    before=CouncilState.model_validate(raw)
    after=before.model_copy(deep=True)
    after.recovery_policy.max_strategies_per_run=31
    with pytest.raises(DiagnosticRuntimeError):check_transition(before,after,'arbiter')
    after=before.model_copy(deep=True);after.current_task_index=1
    with pytest.raises(DiagnosticRuntimeError):check_transition(before,after,'arbiter')


def test_current_policy_timeout_recovers_with_governance(current_autonomous_run):
    run=enable(current_autonomous_run);seen=timeout_once(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert seen==['setup','task-1','task-2']
    assert result['work_pieces']['fixture']['status']=='completed'


def test_stale_shared_helper_proofs_refresh_without_recoding(current_autonomous_run):
    run=enable(current_autonomous_run)
    original=run.provider.run_task
    seen=[]
    def dispatch(task,*args,**kwargs):
        seen.append(task.id)
        value=original(task,*args,**kwargs)
        if task.id=='task-2':
            path=run.fixture.workspace/'verify.py'
            path.write_text(path.read_text()+'\n# Later approved helper edit\n')
        return value
    run.provider.run_task=dispatch
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert seen==['setup','task-1','task-2']
    assert [r['task_id'] for r in result['execution_records']]==['setup','task-1','task-2','setup','task-1']
    assert result['current_task_index']==3
    assert result['recovery_history'][-1]['action']=='refresh_proofs'


def install_diagnosis(run,category='implementation',action='repair_implementation'):
    from council.integrity_contracts import RepairAdvice
    import json
    original=run.provider.with_structured_output
    def structured(schema,**kwargs):
        if schema is not RepairAdvice: return original(schema,**kwargs)
        def invoke(messages):
            # The model double reads the real shared-context failure binding.
            from council.graph_integrity import _message_frame
            frame=next(_message_frame(m) for m in reversed(messages) if _message_frame(m))
            records=frame['records']['execution_evidence']
            failure=next(r for r in reversed(records) if not r['expectation_met'])
            advice=RepairAdvice(failure_id=failure['id'],category=category,action=action,
                target_files=frame['records']['task']['target_files'],limitations=[])
            return {'parsed':advice,'raw':None,'parsing_error':None}
        return SimpleNamespace(invoke=invoke)
    run.provider.with_structured_output=structured


def test_timeout_with_real_failure_is_repaired_then_verified(legacy_monolithic_run):
    run=enable(legacy_monolithic_run)
    seen=timeout_once(run,valid=False);install_diagnosis(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert seen==['task-1','task-1','task-2']
    assert [r['exit_code'] for r in result['execution_records']]==[7,0,0]


def test_observed_missing_partial_target_is_verified_as_a_real_defect(legacy_monolithic_run):
    run=enable(legacy_monolithic_run);install_diagnosis(run)
    original=run.provider.run_task;seen=[]
    def dispatch(task,*args,**kwargs):
        seen.append(task.id)
        value=original(task,*args,**kwargs)
        if len(seen)==1:
            (run.fixture.workspace/task.target_files[0]).unlink()
            raise DiagnosticRuntimeError('CLI_TIMEOUT')
        return value
    run.provider.run_task=dispatch
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert seen==['task-1','task-1','task-2']
    assert [r['exit_code'] for r in result['execution_records']]==[1,0,0]


def test_timeout_during_a_defect_repair_verifies_the_repaired_partial_work(legacy_monolithic_run):
    run=enable(legacy_monolithic_run);install_diagnosis(run)
    original=run.provider.run_task;seen=[]
    def dispatch(task,*args,**kwargs):
        seen.append(task.id)
        value=original(task,*args,**kwargs)
        if len(seen)==1:(run.fixture.workspace/task.target_files[0]).write_text('invalid')
        if len(seen)==2:raise DiagnosticRuntimeError('CLI_TIMEOUT')
        return value
    run.provider.run_task=dispatch
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert seen==['task-1','task-1','task-2']
    assert [r['exit_code'] for r in result['execution_records']]==[7,0,0]


def test_exhausted_task_repairs_do_not_gain_an_arbiter_retry_budget(legacy_monolithic_run):
    run=enable(legacy_monolithic_run);install_diagnosis(run)
    original=run.provider.run_task
    seen=[]
    def dispatch(task,*args,**kwargs):
        seen.append(task.id)
        value=original(task,*args,**kwargs)
        (run.fixture.workspace/task.target_files[0]).write_text('invalid')
        return value
    run.provider.run_task=dispatch
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED'
    assert seen==['task-1']*3
    assert len(result['execution_records'])==3


def test_unknown_arbiter_failure_does_not_recurse(legacy_monolithic_run):
    from council.recovery_contracts import RecoveryDecision
    run=enable(legacy_monolithic_run)
    def fail(*a,**k):raise DiagnosticRuntimeError('CODEX_TURN_INCOMPLETE')
    run.provider.run_task=fail
    original=run.provider.with_structured_output
    def structured(schema,**kwargs):
        if schema is RecoveryDecision:
            return SimpleNamespace(invoke=lambda request: (_ for _ in ()).throw(DiagnosticRuntimeError('CLI_TIMEOUT')))
        return original(schema,**kwargs)
    run.provider.with_structured_output=structured
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED'
    assert len([c for c in result['model_calls'] if c['operation']=='arbiter'])==1


def test_exhausted_review_transport_does_not_trigger_plan_rewrites(legacy_monolithic_run):
    from test_autonomous_review import Reviewer
    run=enable(legacy_monolithic_run)
    run.reviewer=Reviewer([DiagnosticRuntimeError('CLI_EXECUTION_FAILED')]*2)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED'
    assert run.reviewer.calls==2
    assert not [c for c in result['model_calls'] if c['operation']=='plan_revision']
    assert result['recovery_history'][-1]['reason']=='safe_retry_exhausted'


def test_model_decision_cannot_select_arbitrary_node_or_command():
    from pydantic import ValidationError
    from council.recovery_contracts import RecoveryDecision
    with pytest.raises(ValidationError):
        RecoveryDecision(incident_id='a'*64,action='__import__',command=['anything'])


def test_policy_version_rejects_boolean_and_resource_payloads_are_finite():
    from pydantic import ValidationError
    from council.recovery_contracts import RecoveryPolicy
    from council.diagnostics import safe_recovery,safe_resource_cleanup
    with pytest.raises(ValidationError):RecoveryPolicy(version=True)
    assert safe_resource_cleanup({'owned_process_exit_confirmed':True,'detached_resources':'none','secret':'x'}) is None
    assert safe_recovery({'incident_id':'a'*64,'category':[],'action':[],
        'outcome':'opened','elapsed_seconds':0.0,'execution_ids':[]}) is None


def test_lineage_budget_survives_task_rename_and_plan_wording(legacy_monolithic_run):
    from council import recovery
    from council.plan_review import plan_digest
    from council.recovery_contracts import RecoveryDecision,RecoveryEvent
    run=enable(legacy_monolithic_run);timeout_once(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        raw=run.build(saver).invoke(run.state,run.fixture.config,interrupt_after=['arbiter'])
    state=CouncilState.model_validate(raw);lineage=state.recovery_incident.lineage
    state.recovery_history.extend(RecoveryEvent(incident_id=str(i)*64,lineage=lineage,
        outcome='admitted',action='verify_partial',step=i) for i in (1,2))
    state.recovery_incident=None
    state.plan.tasks[0].id='renamed-task'
    state.plan.architecture_summary='Same contract with different descriptive wording'
    state.accepted_plan_sha256=plan_digest(state.plan)
    recovery.open_incident(state,run.fixture.context)
    assert state.recovery_incident.lineage==lineage
    state.recovery_incident.decision=RecoveryDecision(incident_id=state.recovery_incident.id,action='stop')
    with pytest.raises(DiagnosticRuntimeError) as error:recovery.admit(state,run.fixture.context)
    assert error.value.code=='RECOVERY_EXHAUSTED'


def test_ambiguous_diagnosis_is_accounted_and_only_finite_action_executes(legacy_monolithic_run):
    from council.recovery_contracts import RecoveryDecision
    run=enable(legacy_monolithic_run)
    def fail(*a,**k):raise DiagnosticRuntimeError('CODEX_TURN_INCOMPLETE')
    run.provider.run_task=fail
    original=run.provider.with_structured_output
    def structured(schema,**kwargs):
        if schema is RecoveryDecision:
            return SimpleNamespace(invoke=lambda request:{'parsed':RecoveryDecision(
                incident_id=arbiter_input(request)['incident']['id'],action='stop',limitations=['cause_unproven']),
                'raw':None,'parsing_error':None})
        return original(schema,**kwargs)
    run.provider.with_structured_output=structured
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED'
    assert [c['role'] for c in result['model_calls'] if c['operation']=='arbiter']==['orchestrator']
    assert result['recovery_history'][-1]['outcome']=='stopped'
    assert not result['execution_records']


def test_recovery_events_have_bound_evidence_and_finite_progress_text(legacy_monolithic_run):
    from council.diagnostics import DiagnosticSession
    import json
    run=enable(legacy_monolithic_run);timeout_once(run)
    with DiagnosticSession('recovery-event-fixture') as diagnostic:
        diagnostic.attach(run.fixture.context.memory_root)
        with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
            result=run.build(saver).invoke(run.state,run.fixture.config)
    rows=[json.loads(line) for line in diagnostic.path.read_text().splitlines()]
    events=[e for e in rows if e['event'].startswith('recovery_')]
    assert [e['event'] for e in events]==['recovery_opened','recovery_admitted','recovery_dispatched','recovery_resolved']
    assert events[-1]['recovery']['execution_ids']==[result['execution_records'][0]['id']]
    assert events[2]['recovery']['message']=='Verifying retained worker files before requesting more coding.'
    final=result['recovery_history'][-1]
    assert final['category']=='timeout'
    assert final['reason']=='retained_sources_match'
    assert final['run_budget_remaining']==31
    assert final['incident_budget_remaining']==1
    admitted=next(e for e in result['recovery_history'] if e['outcome']=='admitted')
    assert admitted['incident']['task_id']=='task-1'
    assert admitted['incident']['phase']=='admitted'
    assert 'target-1.txt' in admitted['incident']['source_hashes']
    assert result['worker_observation']['task_id']=='task-2'


def test_native_timeout_records_owned_exit_without_claiming_detached_cleanup():
    import sys
    from council.cli_process import run_process
    from council.diagnostics import describe
    with pytest.raises(DiagnosticRuntimeError) as error:
        run_process([sys.executable,'-c','import time;time.sleep(10)'],timeout=.05)
    detail=describe(error.value)
    assert detail['code']=='CLI_TIMEOUT'
    assert detail['resource_cleanup']=={'owned_process_exit_confirmed':True,'detached_resources':'unobserved'}


def test_known_unresolved_resource_cleanup_blocks_recovery_without_deletion(legacy_monolithic_run):
    run=enable(legacy_monolithic_run)
    original=run.provider.run_task
    def dispatch(task,*args,**kwargs):
        original(task,*args,**kwargs)
        raise DiagnosticRuntimeError('CLI_TIMEOUT',resource_cleanup={
            'owned_process_exit_confirmed':True,'detached_resources':'cleanup_required'})
    run.provider.run_task=dispatch
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED'
    assert not result['execution_records']
    assert (run.fixture.workspace/'target-1.txt').read_text()=='valid'
    assert result['recovery_history'][-1]['reason']=='resources_unresolved'


@pytest.mark.parametrize('flag', ['--cached-only','--collect:XPlat Code Coverage'])
def test_recorded_unsupported_runner_argument_routes_to_command_contract(legacy_monolithic_run,flag):
    # A subprocess fixture exposes the actual finite failure shape without using
    # Deno/MTP installations or replaying RATE application tests.
    run=enable(legacy_monolithic_run)
    script=run.fixture.workspace/'verify.py'
    script.write_text("import sys\nif any(x.startswith('--') for x in sys.argv):\n print('Unknown option');sys.exit(5)\nprint('Passed: 1 Failed: 0')\n")
    run.fixture.plan.tasks[0].test_commands[0].append(flag)
    install_diagnosis(run,'command_contract','report_command_contract')
    from council.document_edits import DocumentRevision,document_digest
    from council.graph_integrity import _message_frame
    from council.state import MultiSpecialistPlan
    from test_autonomous_review import Reviewer
    original=run.provider.with_structured_output
    def structured(schema,**kwargs):
        if schema is not DocumentRevision:return original(schema,**kwargs)
        def invoke(messages):
            frame=next(_message_frame(m) for m in reversed(messages) if _message_frame(m))
            plan=MultiSpecialistPlan.model_validate(frame['records']['plan'])
            return {'parsed':DocumentRevision(run_id=run.fixture.state.run_id,artifact='plan',
                base_sha256=document_digest(plan,'plan'),edits=[{
                    'op':'replace','path':'/tasks/task-1/test_commands/0',
                    'value':plan.tasks[0].test_commands[0][:-1],'reason_ids':['R1']}]),
                'raw':None,'parsing_error':None}
        return SimpleNamespace(invoke=invoke)
    run.provider.with_structured_output=structured
    run.reviewer=Reviewer([{'decision':'accept','findings':[],'resolved_finding_ids':[]}]*2)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        graph=run.build(saver)
        result=graph.invoke(run.state,run.fixture.config,interrupt_after=['recovery_admit'])
        incident=result['recovery_incident']
        assert incident['category']=='command_contract'
        assert incident['decision']['action']=='replan'
        assert run.provider.attempts=={'task-1':1}
        result=graph.invoke(None,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert run.reviewer.calls==2
    assert flag not in result['plan']['tasks'][0]['test_commands'][0]
    assert result['execution_records'][0]['exit_code']==5
    assert [r['exit_code'] for r in result['execution_records']]==[5,0,0]


@pytest.mark.parametrize('code',['GRAPH_STATE_INVALID','PERMISSION_DENIED','CLI_AUTH_REQUIRED','CLI_INPUT_LIMIT','APPROVAL_REJECTED'])
def test_hard_stop_is_not_arbitrated(legacy_monolithic_run,code):
    run=enable(legacy_monolithic_run)
    def fail(*a,**k): raise DiagnosticRuntimeError(code)
    run.provider.run_task=fail
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED'
    assert result['diagnostic']['code']==code
    assert result['recovery_history']==[]


def test_accepted_cosmetic_replan_cannot_repeat_same_invalid_command(legacy_monolithic_run):
    from council.document_edits import DocumentRevision,document_digest
    from council.graph_integrity import _message_frame
    from council.state import MultiSpecialistPlan
    from test_autonomous_review import Reviewer
    run=enable(legacy_monolithic_run)
    run.fixture.plan.tasks[0].test_commands[0][-1]='wrong-target.txt'
    install_diagnosis(run,'command_contract','report_command_contract')
    original=run.provider.with_structured_output
    def structured(schema,**kwargs):
        if schema is not DocumentRevision:return original(schema,**kwargs)
        def invoke(messages):
            frame=next(_message_frame(m) for m in reversed(messages) if _message_frame(m))
            plan=MultiSpecialistPlan.model_validate(frame['records']['plan'])
            return {'parsed':DocumentRevision(run_id=run.fixture.state.run_id,artifact='plan',
                base_sha256=document_digest(plan,'plan'),edits=[{
                    'op':'replace','path':'/title','value':'A cosmetic new title','reason_ids':['R1']}]),
                'raw':None,'parsing_error':None}
        return SimpleNamespace(invoke=invoke)
    run.provider.with_structured_output=structured
    run.reviewer=Reviewer([{'decision':'accept','findings':[],'resolved_finding_ids':[]}]*2)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED'
    assert result['diagnostic']['code']=='RECOVERY_NO_PROGRESS'
    assert run.provider.attempts=={'task-1':1}
    assert len(result['execution_records'])==1


def test_recovery_review_allows_one_correction_and_preserves_cumulative_counts(legacy_monolithic_run):
    from council.document_edits import DocumentRevision,document_digest
    from council.graph_integrity import _message_frame
    from council.state import MultiSpecialistPlan
    from test_autonomous_review import Reviewer
    run=enable(legacy_monolithic_run)
    run.fixture.plan.tasks[0].test_commands[0][-1]='wrong-target.txt'
    install_diagnosis(run,'command_contract','report_command_contract')
    original=run.provider.with_structured_output
    def structured(schema,**kwargs):
        if schema is not DocumentRevision:return original(schema,**kwargs)
        def invoke(messages):
            frame=next(_message_frame(m) for m in reversed(messages) if _message_frame(m))
            plan=MultiSpecialistPlan.model_validate(frame['records']['plan'])
            bad=plan.tasks[0].test_commands[0][-1]=='wrong-target.txt'
            edit=({'op':'replace','path':'/tasks/task-1/test_commands/0',
                'value':[plan.tasks[0].test_commands[0][0],'verify.py','target-1.txt'],'reason_ids':['R1']}
                if bad else {'op':'add','path':'/tasks/task-1/acceptance_criteria/-',
                'value':'Verify the corrected command through the real subprocess','reason_ids':['F1']})
            return {'parsed':DocumentRevision(run_id=run.fixture.state.run_id,artifact='plan',
                base_sha256=document_digest(plan,'plan'),edits=[edit]),'raw':None,'parsing_error':None}
        return SimpleNamespace(invoke=invoke)
    run.provider.with_structured_output=structured
    run.reviewer=Reviewer([
        {'decision':'accept','findings':[],'resolved_finding_ids':[]},
        {'decision':'revise','findings':[{'id':'F1','description':'Retain explicit corrected-command acceptance','kind':'technical'}],'resolved_finding_ids':[]},
        {'decision':'accept','findings':[],'resolved_finding_ids':['F1']}])
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert result['plan_review_count']==3 and result['plan_revision_count']==2
    assert result['review_finding_ledger'][0]['status']=='resolved'
    assert len([e for e in result['recovery_history'] if e['outcome']=='admitted'])==1


def test_admitted_decision_cannot_be_admitted_twice(legacy_monolithic_run):
    from council import recovery
    run=enable(legacy_monolithic_run);timeout_once(run)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        raw=run.build(saver).invoke(run.state,run.fixture.config,interrupt_after=['recovery_admit'])
    state=CouncilState.model_validate(raw)
    state.recovery_incident.phase='proposed'
    with pytest.raises(DiagnosticRuntimeError) as error:
        recovery.admit(state,run.fixture.context)
    assert error.value.code=='RECOVERY_EXHAUSTED'


@pytest.mark.parametrize('category,action',[('command_contract','report_command_contract'),('prerequisite','resolve_prerequisite')])
def test_command_contract_uses_reviewed_revision_instead_of_coder_retry(legacy_monolithic_run,category,action):
    from council.document_edits import DocumentRevision,document_digest
    from council.graph_integrity import _message_frame
    from test_autonomous_review import Reviewer
    run=enable(legacy_monolithic_run)
    # Existing syntactically valid argv has an unsupported semantic argument.
    run.fixture.plan.tasks[0].test_commands[0][-1]='wrong-target.txt'
    install_diagnosis(run,category,action)
    original=run.provider.with_structured_output
    revised=[]
    def structured(schema,**kwargs):
        if schema is not DocumentRevision: return original(schema,**kwargs)
        def invoke(messages):
            frame=next(_message_frame(m) for m in reversed(messages) if _message_frame(m))
            plan=frame['records']['plan']
            from council.state import MultiSpecialistPlan
            value=DocumentRevision(run_id=run.fixture.state.run_id,artifact='plan',
                base_sha256=document_digest(MultiSpecialistPlan.model_validate(plan),'plan'),edits=[{
                    'op':'replace','path':'/tasks/task-1/test_commands/0',
                    'value':[plan['tasks'][0]['test_commands'][0][0],'verify.py','target-1.txt'],'reason_ids':['R1']}])
            revised.append(value)
            return {'parsed':value,'raw':None,'parsing_error':None}
        return SimpleNamespace(invoke=invoke)
    run.provider.with_structured_output=structured
    run.reviewer=Reviewer([{'decision':'accept','findings':[],'resolved_finding_ids':[]}]*2)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert len(revised)==1 and run.reviewer.calls==2
    assert run.provider.attempts=={'task-1':2,'task-2':1}
    assert [r['exit_code'] for r in result['execution_records']]==[1,0,0]
    assert result['plan_review_count']==2 and result['plan_revision_count']==1
    assert any(r['action']=='replan' and r['outcome']=='resolved' for r in result['recovery_history'])


def test_real_user_decision_uses_durable_interrupt_without_arbitrating(legacy_monolithic_run):
    from test_autonomous_review import Reviewer
    run=enable(legacy_monolithic_run)
    run.reviewer=Reviewer([{'decision':'escalate','findings':[
        {'id':'F1','description':'Choose the required business behavior','kind':'user_decision'}],
        'resolved_finding_ids':[]}])
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['__interrupt__']
    assert not result['recovery_history']
    assert not result['file_changes']


def test_refresh_failure_repairs_task_and_retains_remaining_queue(current_autonomous_run):
    run=enable(current_autonomous_run);install_diagnosis(run)
    original=run.provider.run_task
    seen=[]
    def dispatch(task,*args,**kwargs):
        seen.append(task.id)
        value=original(task,*args,**kwargs)
        if task.id=='task-2':
            script=run.fixture.workspace/'verify.py'
            script.write_text(script.read_text().replace("== 'valid'", "== ('repaired' if sys.argv[1] == 'prerequisite.txt' else 'valid')"))
        if task.id=='setup' and seen.count('setup')==2:
            (run.fixture.workspace/'prerequisite.txt').write_text('repaired')
        return value
    run.provider.run_task=dispatch
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert seen==['setup','task-1','task-2','setup']
    assert [r['task_id'] for r in result['execution_records']]==['setup','task-1','task-2','setup','setup','task-1']
    assert result['recovery_history'][-1]['outcome']=='resolved'


@pytest.mark.parametrize('mode,version',[(None,1),('disabled',0)])
def test_cli_new_run_selects_recovery_policy(current_autonomous_run,monkeypatch,mode,version):
    from council import cli
    from council.config import RunModelConfiguration
    run=current_autonomous_run;captured={}
    def invoke(state,config):
        captured.update(state)
        return {**state,'status':'FAILED'}
    monkeypatch.setattr(cli,'build_council_graph',lambda **kw:SimpleNamespace(invoke=invoke))
    monkeypatch.setattr(cli,'resolve_model_configuration',lambda **kw:RunModelConfiguration.model_validate(run.fixture.state.model_configuration))
    monkeypatch.setattr(cli,'credentials_available',lambda *a:True)
    monkeypatch.setattr(cli,'emit',lambda *a:None)
    cli.run_council_task(prompt='Synthetic startup',workspace_root=run.fixture.workspace,
        council_root=run.fixture.context.council_root,recovery_mode=mode)
    assert captured['recovery_policy']['version']==version


@pytest.mark.parametrize('boundary',['worker','recovery_admit','recovery_dispatch'])
def test_cli_resume_continues_checkpointed_recovery(legacy_monolithic_run,monkeypatch,boundary):
    from council import cli
    run=enable(legacy_monolithic_run);seen=timeout_once(run)
    monkeypatch.setattr(cli,'resolve_context',lambda *a:run.fixture.context)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        run.build(saver).invoke(run.state,run.fixture.config,interrupt_after=[boundary])
    monkeypatch.setattr(cli,'managed_sqlite_checkpointer',lambda **kw:managed_sqlite_checkpointer(db_path=run.fixture.db))
    monkeypatch.setattr(cli,'build_council_graph',lambda **kw:run.build(kw['checkpointer']))
    monkeypatch.setattr(cli,'credentials_available',lambda *a:True)
    output=[];monkeypatch.setattr(cli,'emit',output.append)
    code=cli.run_council_task(resume_id=run.fixture.state.run_id,workspace_root=run.fixture.workspace,
        council_root=run.fixture.context.council_root,no_input=True)
    assert code==0,output
    assert output[-1]['status']=='COMPLETED'
    assert seen==['task-1','task-2']
