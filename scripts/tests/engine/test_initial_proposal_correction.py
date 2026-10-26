"""Rejected initial proposals never become execution authority."""
from types import SimpleNamespace
import json
import pytest
from council.checkpoint import managed_sqlite_checkpointer
from council.diagnostics import DiagnosticValueError
from council.state import MultiSpecialistPlan
from council.phase_contract import PhaseRoadmap


def install_rejection(run,schema,code,*,always=False):
    original=run.provider.with_structured_output
    attempts=[]
    def structured(selected,**kwargs):
        result=original(selected,**kwargs)
        if selected is not schema:return result
        def invoke(messages):
            attempts.append(messages)
            if schema in {MultiSpecialistPlan,PhaseRoadmap}:assert not run.provider.attempts
            if always or len(attempts)==1:
                if code.endswith('SCHEMA_INVALID'):
                    raise DiagnosticValueError(code,response_schema={
                        'reason':'schema_invalid','field_path':['unknown_field',0],'edit_index':None})
                raise DiagnosticValueError(code,response_json={
                    'reason':'SYNTAX_ERROR','response_bytes':100,'line':1,'column':2,'position':1})
            return result.invoke(messages)
        return SimpleNamespace(invoke=invoke)
    run.provider.with_structured_output=structured
    return attempts


@pytest.mark.parametrize('schema,operation,retry',[(MultiSpecialistPlan,'planning','planning_format_retry'),
    (PhaseRoadmap,'roadmap','roadmap_format_retry')])
@pytest.mark.parametrize('code',['CODEX_SCHEMA_INVALID','CODEX_RESPONSE_JSON_INVALID'])
def test_one_rejected_initial_native_proposal_is_corrected_before_execution(current_autonomous_run,schema,operation,retry,code):
    run=current_autonomous_run;attempts=install_rejection(run,schema,code)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert len(attempts)==2
    calls=[c for c in result['model_calls'] if c['operation'] in {operation,retry}]
    assert [c['status'] for c in calls[:2]]==['failed','succeeded']
    assert calls[1]['operation']==retry
    assert result['total_inspection_rounds']==2
    assert any(isinstance(m,dict) and 'Return exactly' in m.get('content','') for m in attempts[1])


def test_second_invalid_initial_proposal_stops_without_execution(current_autonomous_run):
    run=current_autonomous_run
    attempts=install_rejection(run,MultiSpecialistPlan,'CODEX_SCHEMA_INVALID',always=True)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED' and result['diagnostic']['code']=='CODEX_SCHEMA_INVALID'
    assert len(attempts)==2 and not run.provider.attempts
    assert result['accepted_plan_sha256'] is None and result['execution_records']==[]


def test_quality_gate_feedback_uses_finite_known_fields_without_rejected_values():
    from pydantic import ValidationError
    from council.schema_feedback import from_error,correction
    with pytest.raises(ValidationError) as caught:
        MultiSpecialistPlan.model_validate({'title':'PRIVATE_TITLE','architecture_summary':'PRIVATE_ARCH',
            'tasks':[{'id':'t','specialist':'the-coder','description':'task'}],
            'quality_gates':[{'phase':'unit_tests','task_ids':[],'out_of_scope_reason':None}]})
    detail=from_error(caught.value)
    assert detail['field_path']==['quality_gates',0]
    assert detail['reason']=='quality_gate_scope_invalid'
    assert 'PRIVATE_' not in json.dumps(detail)+json.dumps(correction(detail))


def test_arbiter_format_challenge_preserves_failed_worker_binding(current_autonomous_run):
    from test_recovery import enable,tool_failure_once
    from council.recovery_contracts import RecoveryDecision
    run=enable(current_autonomous_run);seen=tool_failure_once(run)
    attempts=install_rejection(run,RecoveryDecision,'CODEX_SCHEMA_INVALID')
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert len(attempts)==2 and seen==['setup','task-1','task-2']
    assert [c['operation'] for c in result['model_calls'] if c['operation'].startswith('arbiter')]==[
        'arbiter','arbiter_format_retry']


def test_investigator_format_challenge_preserves_actual_failure_identity(legacy_monolithic_run):
    from test_recovery import install_diagnosis
    from council.integrity_contracts import RepairAdvice
    run=legacy_monolithic_run;original=run.provider.run_task;seen=[]
    def worker(task,*args,**kwargs):
        seen.append(task.id);result=original(task,*args,**kwargs)
        if len(seen)==1:(run.fixture.workspace/task.target_files[0]).write_text('invalid')
        return result
    run.provider.run_task=worker;install_diagnosis(run)
    attempts=install_rejection(run,RepairAdvice,'CODEX_SCHEMA_INVALID')
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert len(attempts)==2 and seen==['task-1','task-1','task-2']
    assert [r['exit_code'] for r in result['execution_records']]==[7,0,0]


@pytest.mark.parametrize('consumer',['roadmap_review','plan_review'])
def test_review_format_challenge_does_not_rewrite_candidate_or_consume_another_review(current_autonomous_run,consumer):
    from langchain_core.messages import AIMessage
    run=current_autonomous_run;original=run.reviewer.review_plan;attempts=[]
    def review(request):
        if request['shared_context']['consumer']==consumer:
            attempts.append(request)
            if len(attempts)==1:return AIMessage(content='PRIVATE_INVALID_REVIEW')
        return original(request)
    run.reviewer.review_plan=review
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert len(attempts)==2
    assert result['roadmap_review_count']==result['plan_review_count']==1
    assert result['plan_revision_count']==result['roadmap_revision_count']==0
    assert 'PRIVATE_INVALID_REVIEW' not in json.dumps(attempts[1])


@pytest.mark.parametrize('initial_attempts',[0,3])
def test_intake_format_challenge_charges_existing_draft_budget(current_autonomous_run,initial_attempts):
    from test_requirements_intake import draft
    from langchain_core.messages import AIMessage
    run=current_autonomous_run;run.state['intake_enabled']=True
    run.state['requirements']['drafting_attempts']=initial_attempts
    attempts=[]
    class Provider:
        def bind_tools(self,tools):return SimpleNamespace(invoke=lambda messages:AIMessage(content='Inspection complete'))
        def with_structured_output(self,schema,**kwargs):
            def invoke(messages):
                attempts.append(messages)
                if len(attempts)==1:raise DiagnosticValueError('CODEX_SCHEMA_INVALID',response_schema={
                    'reason':'schema_invalid','field_path':['unknown_field',0],'edit_index':None})
                return draft()
            return SimpleNamespace(invoke=invoke)
    run.provider=Provider()
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    if initial_attempts==0:
        assert result['status']=='REQUIREMENTS_WAITING',result.get('diagnostic')
        assert len(attempts)==2 and result['requirements']['drafting_attempts']==2
        assert result['requirements']['approved_sha256'] is None
    else:
        assert result['status']=='FAILED' and len(attempts)==1
        assert result['requirements']['drafting_attempts']==4
    assert result['execution_records']==[]


@pytest.mark.parametrize('concurrent_edit',[False,True])
def test_finished_review_format_challenge_does_not_repeat_polish_or_approve_stale_content(current_autonomous_run,concurrent_edit):
    from council.delivery_contracts import FinalReview
    from langchain_core.messages import AIMessage
    run=current_autonomous_run;run.state['finalization_enabled']=True
    run.fixture.plan.tasks[-1].delivery_stage='finalize'
    attempts=[]
    def review(messages):
        attempts.append(messages)
        if len(attempts)==1:
            if concurrent_edit:(run.fixture.workspace/run.fixture.plan.tasks[-1].target_files[0]).write_text('concurrent edit')
            raise DiagnosticValueError('CODEX_SCHEMA_INVALID',response_schema={
                'reason':'schema_invalid','field_path':['unknown_field',0],'edit_index':None})
        packets=[]
        for message in messages:
            if not isinstance(message,dict):continue
            try:value=json.loads(message['content'])
            except (ValueError,KeyError):continue
            if isinstance(value,dict) and 'content_sha256' in value:packets.append(value)
        value=FinalReview(content_sha256=packets[0]['content_sha256'],decision='accept',findings=[],
            resolved_finding_ids=[],inspected_dimensions=['polish','documentation'])
        return {'parsed':value,'raw':AIMessage(content='review'),'parsing_error':None}
    run.reviewer.review_finished=review
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    if concurrent_edit:
        assert result['status']=='FAILED' and result['finalization']['approved_content_sha256'] is None
    else:
        assert result['status']=='COMPLETED',result.get('diagnostic')
        assert result['finalization']['review_count']==1
    assert len(attempts)==2
    assert run.provider.attempts=={'setup':1,'task-1':1,'task-2':1}


@pytest.mark.parametrize('code',['CODEX_EVENT_INVALID','CODEX_REVIEW_TOOL_REJECTED','CLI_AUTH_REQUIRED','PERMISSION_DENIED'])
def test_nonformat_failures_never_enter_proposal_correction(current_autonomous_run,code):
    from council.diagnostics import DiagnosticRuntimeError
    run=current_autonomous_run;original=run.provider.with_structured_output;attempts=[]
    def structured(schema,**kwargs):
        result=original(schema,**kwargs)
        if schema is not MultiSpecialistPlan:return result
        def invoke(messages):
            attempts.append(messages)
            if code=='PERMISSION_DENIED':raise PermissionError('PRIVATE_DENIAL')
            if code=='CLI_AUTH_REQUIRED':raise DiagnosticRuntimeError(code)
            raise DiagnosticValueError(code)
        return SimpleNamespace(invoke=invoke)
    run.provider.with_structured_output=structured
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='FAILED' and result['diagnostic']['code']==code
    assert len(attempts)==1 and not run.provider.attempts
    assert not any(c['operation']=='planning_format_retry' for c in result['model_calls'])


def test_include_raw_parse_failure_gets_one_private_correction_and_keeps_usage(current_autonomous_run):
    from langchain_core.messages import AIMessage
    run=current_autonomous_run;original=run.provider.with_structured_output;attempts=[]
    def structured(schema,**kwargs):
        result=original(schema,**kwargs)
        if schema is not MultiSpecialistPlan:return result
        def invoke(messages):
            attempts.append(messages)
            if len(attempts)==1:return {'parsed':None,'parsing_error':ValueError('PRIVATE_PARSE_CANARY'),
                'raw':AIMessage(content='PRIVATE_REJECTED_TEXT',response_metadata={'reported_usage':{'input_tokens':5,'output_tokens':2}})}
            return result.invoke(messages)
        return SimpleNamespace(invoke=invoke)
    run.provider.with_structured_output=structured
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    calls=[c for c in result['model_calls'] if c['operation'] in {'planning','planning_format_retry'}]
    assert calls[0]['diagnostic']['code']=='PROPOSAL_FORMAT_INVALID' and calls[0]['usage']['input_tokens']==5
    assert len(attempts)==2
    correction=next(m['content'] for m in attempts[1] if isinstance(m,dict) and 'Return exactly' in m.get('content',''))
    assert 'PRIVATE_' not in correction+json.dumps(calls)


def test_second_invalid_review_does_not_rewrite_plan_or_enter_execution(current_autonomous_run):
    from langchain_core.messages import AIMessage
    from test_recovery import enable
    run=enable(current_autonomous_run);original=run.reviewer.review_plan;attempts=[]
    def review(request):
        if request['shared_context']['consumer']=='plan_review':
            attempts.append(request);return AIMessage(content='PRIVATE_INVALID_REVIEW')
        return original(request)
    run.reviewer.review_plan=review
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result=run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='PLAN_BLOCKED' and len(attempts)==2
    assert result['plan_revision_count']==0 and result['accepted_plan_sha256'] is None
    assert not run.provider.attempts and result['execution_records']==[]
    assert not any(c['operation']=='arbiter' for c in result['model_calls'])


def test_arbiter_format_tail_rejects_a_permission_failure(current_autonomous_run):
    from test_recovery import enable,tool_failure_once
    from council.recovery_contracts import RecoveryDecision
    from council.state import CouncilState
    from council.recovery import observation_matches
    run=enable(current_autonomous_run);tool_failure_once(run)
    install_rejection(run,RecoveryDecision,'CODEX_SCHEMA_INVALID')
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        raw=run.build(saver).invoke(run.state,run.fixture.config,interrupt_after=['arbiter'])
    state=CouncilState.model_validate(raw)
    assert observation_matches(state,run.fixture.context)
    state.model_calls[-2]['diagnostic']['code']='PERMISSION_DENIED'
    assert not observation_matches(state,run.fixture.context)


@pytest.mark.parametrize('operation,expected',[('plan_review',True),('plan_review_format_retry',False)])
def test_only_exhausted_format_review_changes_existing_recovery_routing(operation,expected):
    from council.recovery import wants_recovery
    raw={'recovery_policy':{'version':1},'graph_integrity_policy_version':2,
        'status':'PLAN_BLOCKED','step_count':5,'max_steps':100,
        'diagnostic':{'code':'PLAN_REVIEW_INVALID'},
        'model_calls':[{'operation':operation,'status':'failed','diagnostic':{'code':'PLAN_REVIEW_INVALID'}}]}
    assert wants_recovery(raw) is expected
