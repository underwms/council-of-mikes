"""Current-policy graph uses real Codex response parsing and real verification."""
import json

from langchain_core.messages import AIMessage

from council.codex_chat import CodexCLIChatModel
from council.graph import build_council_graph
from council.phase_contract import Phase,PhaseRoadmap
from council.state import MultiSpecialistPlan
from test_engine_integration import open_graph
from test_integrity_lifecycle import frame_from
from test_autonomous_review import Reviewer


def test_current_graph_uses_codex_chat_for_inspection_revision_and_repair(current_autonomous_run,monkeypatch):
    run=current_autonomous_run
    attempts={'revision':0,'repair':0,'inspection':0}
    payloads=[]
    def read_only(worker,request,**kwargs):
        payloads.append(request)
        if 'tools' in request:
            attempts['inspection']+=1
            value={'content':'Inspection complete.','tool_calls':[]}
        else:
            title=request['response_schema']['title']
            frame=frame_from(request['messages'])
            if title=='PhaseRoadmap':
                value=PhaseRoadmap(title='Current Codex fixture',architecture_summary='Verify only declared fixture targets.',phases=[
                    Phase(id='fixture',goal='Implement and verify fixture targets',affected_services=['fixture'],
                        executable_ids=['fixture'],delivered_contracts=['Verified targets'],acceptance_outcomes=['Actual checks pass'],final_acceptance=True)],
                    solution_architecture={'executables':[{'id':'fixture','kind':'console','repository':'.','depends_on':[]}],
                        'contracts':[],'open_questions':[],'integration_strategy':'Verify actual fixture subprocesses'}).model_dump(mode='json')
            elif title=='MultiSpecialistPlan':value=run.fixture.plan.model_dump(mode='json')
            elif title=='DocumentRevision':
                from council.plan_review import plan_digest
                attempts['revision']+=1
                plan=MultiSpecialistPlan.model_validate(frame['records']['plan'])
                value={'run_id':frame['run_id'],'artifact':'plan','base_sha256':plan_digest(plan),'edits':[
                    {'op':'add','path':'/tasks/task-1/acceptance_criteria/-','reason_ids':['F1'],
                        'value':'Additional fixture outcome'}]}
                if attempts['revision']==1:value['edits'][0].pop('value')
            else:
                assert title=='RepairAdvice'
                attempts['repair']+=1
                failure=[entry for entry in frame['records']['execution_evidence'] if not entry['expectation_met']][-1]
                value={'failure_id':failure['id'],'category':'implementation','action':'repair_implementation',
                    'target_files':frame['records']['task']['target_files'],'limitations':['cause_unproven']}
        return AIMessage(content=json.dumps(value),response_metadata={'transport':'codex-cli','cli_version':'fixture'})
    monkeypatch.setattr('council.codex_cli.CodexCLIWorker.invoke_read_only',read_only)
    accept={'decision':'accept','findings':[],'resolved_finding_ids':[]}
    reviewer=Reviewer([accept,{'decision':'revise','findings':[{'id':'F1','description':'Add fixture outcome','kind':'technical'}],
        'resolved_finding_ids':[]},{'decision':'accept','findings':[],'resolved_finding_ids':['F1']}])
    requests=[]
    original_review=reviewer.review_plan
    def review(request):
        requests.append(request)
        return original_review(request)
    reviewer.review_plan=review
    original_worker=run.provider.run_task
    def worker(task,guidance,**kwargs):
        result=original_worker(task,guidance,**kwargs)
        if task.id=='task-1' and run.provider.attempts[task.id]==1:
            (run.fixture.workspace/task.target_files[0]).write_text('broken',encoding='utf-8')
        return result
    run.provider.run_task=worker
    def factory(role):
        if role=='reviewer':return reviewer
        if role=='coder':return run.provider
        selected=run.state['model_configuration']['roles'][role]
        return CodexCLIChatModel(selected['model'],selected['settings'],run.fixture.context)
    with open_graph(run.fixture,run.provider) as saver:
        graph=build_council_graph(checkpointer=saver,context=run.fixture.context,llm_factory=factory)
        result=graph.invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert attempts['revision']==2 and attempts['repair']==1 and attempts['inspection']>=2
    assert run.provider.attempts['task-1']==2
    assert all(call['provider']=='codex-cli' and call['requested_model']=='gpt-6.1-sol' for call in result['model_calls'])
    assert any(call['diagnostic']['code']=='CODEX_SCHEMA_INVALID' for call in result['model_calls'] if call['status']=='failed')
    assert all('Routine implementation decisions' in (request.get('instruction') or request['review_protocol']) for request in requests)
    assert result['completed_phases'] and result['execution_records']
    assert payloads and all('messages' in request for request in payloads)
