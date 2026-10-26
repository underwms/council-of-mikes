"""Final delivery inspects every completed piece, not only the last plan."""
from council.state import CouncilState, MultiSpecialistPlan, TestExecutionResult as ExecutionResult
from council.phase_contract import PhaseRoadmap
from council.governance_contracts import WorkPieceRecord
from council.plan_review import plan_digest
from council.graph_integrity import record_execution


def test_completed_piece_source_edits_are_visible_at_final_boundary(graph_workspace):
    from council.finalization import first_stale_piece
    fixture = graph_workspace
    task = fixture.plan.tasks[0]
    (fixture.workspace/task.target_files[0]).write_text('valid')
    task.status = 'completed'
    state = CouncilState(run_id='archive',task_input='Feature',finalization_enabled=True,
        plan=MultiSpecialistPlan(title='Earlier piece',architecture_summary='Boundary',tasks=[task]),
        graph_integrity_policy_version=2)
    state.accepted_plan_sha256 = plan_digest(state.plan)
    record_execution(state,task,1,ExecutionResult(command='python',passed=True,exit_code=0,expectation_met=True),fixture.context)
    state.roadmap = PhaseRoadmap.model_validate({'title':'Feature','architecture_summary':'Pieces','phases':[
        {'id':key,'goal':key,'affected_services':['app'],'delivered_contracts':['contract'],
            'acceptance_outcomes':['works'],'final_acceptance':key=='final'} for key in ('earlier','final')]})
    state.work_pieces['earlier'] = WorkPieceRecord(id='earlier',status='completed',
        checkpoint={'plan':state.plan.model_dump(mode='json'),'accepted_plan_sha256':state.accepted_plan_sha256})
    state.current_phase_index = 2
    assert first_stale_piece(state,fixture.context) is None
    (fixture.workspace/task.target_files[0]).write_text('changed later')
    assert first_stale_piece(state,fixture.context)==0
    from council.governor import restore_for_proof
    state.governance_policy_version=2
    state.proof_refresh_piece,state.proof_refresh_reason=0,'stale'
    restore_for_proof(state)
    assert state.status=='FAILED'
    assert state.diagnostic['code']=='GRAPH_EVIDENCE_INVALID'
    assert state.current_phase_index==0


def test_later_polish_reverifies_earlier_piece_through_normal_arbiter(current_autonomous_run):
    import json
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from council.graph import build_council_graph
    from council.checkpoint import managed_sqlite_checkpointer
    from council.delivery_contracts import FinalReview
    from test_autonomous_review import Reviewer as PlanReviewer
    run = current_autonomous_run
    run.state.update(finalization_enabled=True,recovery_policy={'version':1})
    early = run.fixture.plan.model_copy(deep=True)
    early.tasks = early.tasks[:2]
    early.tasks[0].readiness_for=['task-1']
    later = run.fixture.plan.model_copy(deep=True)
    later.tasks = [later.tasks[0],later.tasks[-1]]
    later.tasks[0].id='setup-2'
    later.tasks[0].target_files=['prerequisite-2.txt']
    later.tasks[0].test_commands[0][-1]='prerequisite-2.txt'
    later.tasks[0].readiness_for=['task-2']
    later.tasks[-1].delivery_stage='finalize'
    plans=iter([early,later])
    architecture={'executables':[{'id':'fixture','kind':'console','repository':'.','depends_on':[]}],
        'contracts':[],'open_questions':[],'integration_strategy':'Verify both pieces'}
    roadmap=PhaseRoadmap.model_validate({'title':'Two pieces','architecture_summary':'Sequential boundaries',
        'solution_architecture':architecture,'phases':[
            {'id':key,'goal':key,'affected_services':['fixture'],'executable_ids':['fixture'],
                'delivered_contracts':['targets'],'acceptance_outcomes':['actual subprocesses pass'],
                'depends_on':['early'] if key=='final' else [],'final_acceptance':key=='final'} for key in ('early','final')]})
    base=run.provider
    class Provider:
        def bind_tools(self, tools):
            return SimpleNamespace(invoke=lambda messages:AIMessage(content='Inspected fixture'))
        def with_structured_output(self, schema, **kwargs):
            value=roadmap if schema is PhaseRoadmap else next(plans)
            return SimpleNamespace(invoke=lambda messages:{'parsed':value,'raw':None,'parsing_error':None})
        def run_task(self, task, guidance, **kwargs):
            result=base.run_task(task,guidance,**kwargs)
            if task.delivery_stage=='finalize':
                path=run.fixture.workspace/'verify.py'
                path.write_text(path.read_text()+'\n# Scoped polish comment\n')
            return result
    accept={'decision':'accept','findings':[],'resolved_finding_ids':[]}
    normal=PlanReviewer([accept]*4)
    class Reviewer:
        def review_plan(self, request):
            return normal.review_plan(request)
        def with_structured_output(self,schema,**kwargs):
            assert schema is FinalReview
            def review(messages):
                packet=json.loads(messages[1]['content'])
                return {'parsed':{'content_sha256':packet['content_sha256'],'decision':'accept',
                    'findings':[],'resolved_finding_ids':[]},'raw':None,'parsing_error':None}
            return SimpleNamespace(invoke=review)
    provider,reviewer=Provider(),Reviewer()
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        graph=build_council_graph(checkpointer=saver,context=run.fixture.context,
            llm_factory=lambda role:reviewer if role=='reviewer' else provider)
        result=graph.invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert base.attempts=={'setup':1,'task-1':1,'setup-2':1,'task-2':1}
    assert len([r for r in result['execution_records'] if r['task_id']=='task-1'])==2
    earlier = {e['incident_id'] for e in result['recovery_history'] if e['action']=='refresh_proofs'
        and e['outcome']=='admitted' and e['incident']['phase_index']==0}
    assert earlier and any(e['incident_id'] in earlier and e['outcome']=='resolved' for e in result['recovery_history'])
