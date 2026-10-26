"""All-role Codex routing and graph chat contracts over inert native processes."""
import json
import os
from unittest.mock import patch

import pytest
from langchain_core.tools import tool
from pydantic import BaseModel

from test_codex_cli import native,completed


def chat(native):
    from council.codex_chat import CodexCLIChatModel
    settings,context,_,_,_=native
    return CodexCLIChatModel('gpt-6.1-sol',settings,context)


def respond(native,value,*,plain=False):
    native[3]['events']=completed()
    native[3]['events'][-2]['item']['text']=value if plain else json.dumps(value)


def test_every_new_default_role_uses_requested_model_and_saved_login(native,monkeypatch):
    from council.config import resolve_model_configuration,get_llm_for_role,preflight_credentials
    monkeypatch.setattr('council.codex_cli.resolve_cli_settings',lambda:dict(native[0]))
    with patch.dict(os.environ,{},clear=True),patch('council.gemini_cli.resolve_cli_settings',side_effect=AssertionError('Gemini must not resolve')):
        configuration=resolve_model_configuration(autonomous=True)
        assert set(configuration.roles)=={'orchestrator','investigator','coder','reviewer'}
        assert {item.model for item in configuration.roles.values()}=={'gpt-6.1-sol'}
        assert {item.provider for item in configuration.roles.values()}=={'codex-cli'}
        assert preflight_credentials(configuration)=={'codex-cli':True}
        for role in configuration.roles:
            instance=get_llm_for_role(role,configuration,context=native[1])
            if role in {'orchestrator','investigator'}:
                assert type(instance).__name__=='CodexCLIChatModel'
            else:
                assert type(instance).__name__=='CodexCLIWorker'


def test_plain_reasoning_preserves_usage_and_runs_without_native_tools(native):
    respond(native,'Observed safe fixture',plain=True)
    response=chat(native).invoke('Read supplied data only.')
    assert response.content=='Observed safe fixture'
    assert response.usage_metadata['total_tokens']==5
    argv,kwargs=native[4][-1]
    assert argv[argv.index('--model')+1]=='gpt-6.1-sol'
    assert argv[argv.index('--sandbox')+1]=='read-only'
    assert '--ephemeral' in argv and '--ignore-user-config' in argv
    assert '--approve-for-me' not in argv and '--output-schema' not in argv
    assert 'features.shell_tool=false' in argv and 'mcp_servers={}' in argv
    assert kwargs['cwd']!=native[1].workspace_root


class Answer(BaseModel):
    count:int


def test_structured_reasoning_validates_native_json_and_keeps_raw_evidence(native):
    respond(native,{'count':4})
    result=chat(native).with_structured_output(Answer,include_raw=True).invoke([])
    assert result['parsed']==Answer(count=4)
    assert result['raw'].response_metadata['transport']=='codex-cli'
    assert result['parsing_error'] is None


@pytest.mark.parametrize('value,code',[
    ('```json\n{}\n```','CODEX_RESPONSE_JSON_INVALID'),
    ('{"count":"PRIVATE_VALUE"}','CODEX_SCHEMA_INVALID'),
    ('{"count":1,"count":2}','CODEX_RESPONSE_JSON_INVALID'),
    ('{"count":NaN}','CODEX_RESPONSE_JSON_INVALID')])
def test_reasoning_rejections_have_finite_diagnostics(native,value,code):
    from council.diagnostics import DiagnosticValueError,describe
    respond(native,value,plain=True)
    with pytest.raises(DiagnosticValueError) as caught:
        chat(native).with_structured_output(Answer).invoke([])
    assert caught.value.code==code
    facts=describe(caught.value)
    assert ('response_schema' if code=='CODEX_SCHEMA_INVALID' else 'response_json') in facts
    assert 'PRIVATE_VALUE' not in json.dumps(facts)


@tool
def read_workspace_file(path:str)->str:
    """Read an allowed fixture file."""
    raise AssertionError('The adapter must never execute graph tools itself')


def test_tool_requests_are_validated_before_graph_dispatch(native):
    respond(native,{'content':'Need fixture','tool_calls':[
        {'name':'read_workspace_file','args':{'path':'fixture.txt'},'id':'read-1'}]})
    base=chat(native)
    bound=base.bind_tools([read_workspace_file])
    result=bound.invoke([])
    assert result.tool_calls[0]['args']=={'path':'fixture.txt'}
    assert base._tools==() and len(bound._tools)==1
    assert base.with_structured_output(Answer)._tools==()


@pytest.mark.parametrize('mutation,code',[
    ('envelope','CODEX_TOOL_ENVELOPE_INVALID'),('unoffered','CODEX_TOOL_NAME_UNOFFERED'),
    ('missing-argument','CODEX_TOOL_ARGUMENTS_INVALID'),('wrong-type','CODEX_TOOL_ARGUMENTS_INVALID'),
    ('duplicate-id','CODEX_TOOL_CALL_INVALID'),('too-many','CODEX_TOOL_ENVELOPE_INVALID'),
    ('call-shape','CODEX_TOOL_CALL_INVALID'),('args-shape','CODEX_TOOL_ARGUMENTS_INVALID')])
def test_invalid_tool_batch_is_rejected_as_a_whole(native,mutation,code):
    from council.diagnostics import DiagnosticValueError
    first={'name':'read_workspace_file','args':{'path':'safe.txt'},'id':'one'}
    data={'content':'','tool_calls':[first,{'name':'read_workspace_file','args':{'path':'other.txt'},'id':'two'}]}
    if mutation=='envelope':data['extra']='PRIVATE'
    if mutation=='unoffered':data['tool_calls'][1]['name']='delete_everything'
    if mutation=='missing-argument':data['tool_calls'][1]['args']={}
    if mutation=='wrong-type':data['tool_calls'][1]['args']={'path':123}
    if mutation=='duplicate-id':data['tool_calls'][1]['id']='one'
    if mutation=='too-many':data['tool_calls']=[{**first,'id':str(i)} for i in range(17)]
    if mutation=='call-shape':data['tool_calls'][1].pop('args')
    if mutation=='args-shape':data['tool_calls'][1]['args']=[]
    respond(native,data)
    with pytest.raises(DiagnosticValueError) as caught:
        chat(native).bind_tools([read_workspace_file]).invoke([])
    assert caught.value.code==code


def test_native_tool_events_are_rejected_during_reasoning(native):
    from council.diagnostics import DiagnosticValueError
    native[3]['events']=completed([{'type':'item.completed','item':{
        'id':'shell','type':'command_execution','status':'completed','exit_code':0,'command':'not executed'}}])
    with pytest.raises(DiagnosticValueError) as caught:chat(native).invoke([])
    assert caught.value.code=='CODEX_REVIEW_TOOL_REJECTED'


def test_native_document_edits_keep_objects_arrays_and_strings_unencoded(native):
    from council.document_edits import DocumentRevision,apply_revision
    from test_document_edits import edit_state,patch_for
    state=edit_state()
    proposal=patch_for(state)
    proposal['edits'][0].pop('value_json')
    proposal['edits'][0]['value']='Preserve "quoted" fixture'
    respond(native,proposal)
    parsed=chat(native).with_structured_output(DocumentRevision).invoke([])
    assert apply_revision(state,parsed,'roadmap').phases[0].acceptance_outcomes[-1]=='Preserve "quoted" fixture'


@pytest.mark.parametrize('kind',['plan','roadmap'])
def test_already_closed_finding_acknowledgements_are_idempotent(kind):
    from council.plan_review import reconcile_findings
    from council.state import FindingLedgerEntry,PlanReviewDecisionV2
    from test_document_edits import edit_state
    state=edit_state()
    ledger=[FindingLedgerEntry(id='F1',description='Previously resolved',kind='technical',status='resolved'),
        FindingLedgerEntry(id='F2',description='Currently addressed',kind='technical',status='unresolved')]
    setattr(state,'roadmap_finding_ledger' if kind=='roadmap' else 'review_finding_ledger',ledger)
    decision=PlanReviewDecisionV2(decision='accept',findings=[],resolved_finding_ids=['F1','F2'])
    reconcile_findings(state,decision,artifact=kind)
    assert all(entry.status=='resolved' for entry in getattr(state,'roadmap_finding_ledger' if kind=='roadmap' else 'review_finding_ledger'))


def test_repeated_old_closure_does_not_fabricate_new_progress():
    from council.plan_review import reconcile_findings,plan_digest
    from council.state import FindingLedgerEntry,PlanReviewDecisionV2
    from test_document_edits import edit_state
    state=edit_state()
    state.review_finding_ledger=[FindingLedgerEntry(id='F1',description='Closed',kind='technical',status='resolved'),
        FindingLedgerEntry(id='F2',description='Still open',kind='technical',status='unresolved')]
    state.last_reviewed_plan_sha256=plan_digest(state.plan)
    state.review_no_progress_count=1
    decision=PlanReviewDecisionV2(decision='revise',findings=[{'id':'F2','description':'Still open','kind':'technical'}],
        resolved_finding_ids=['F1'])
    reconcile_findings(state,decision)
    assert state.review_no_progress_count==2


def test_unknown_closure_still_rejects_atomically():
    from council.plan_review import reconcile_findings
    from council.state import PlanReviewDecisionV2
    from test_document_edits import edit_state
    from council.diagnostics import DiagnosticValueError
    state=edit_state()
    before=state.model_dump(mode='json')
    with pytest.raises(DiagnosticValueError) as caught:
        reconcile_findings(state,PlanReviewDecisionV2(decision='accept',findings=[],resolved_finding_ids=['F1','F99']))
    assert caught.value.review_decision['reason']=='UNKNOWN_RESOLVED_ID'
    assert state.model_dump(mode='json')==before


def test_reasoning_context_can_resolve_lazily_without_changing_bindings(native,monkeypatch):
    from council.codex_chat import CodexCLIChatModel
    monkeypatch.setattr('council.runtime_context.resolve_context',lambda:native[1])
    respond(native,{'count':4})
    base=CodexCLIChatModel('gpt-6.1-sol',native[0])
    bound=base.bind_tools([read_workspace_file])
    structured=bound.with_structured_output(Answer)
    assert structured.invoke([]).count==4
    assert len(bound._tools)==1 and structured._tools==()
    assert bound._schema is None


def test_reasoning_rejects_duplicate_or_write_tool_bindings(native):
    @tool
    def write_workspace_file(path:str)->str:
        """Writing is unavailable to this adapter."""
        raise AssertionError('Must not execute')
    model=chat(native)
    with pytest.raises(ValueError):model.bind_tools([read_workspace_file,read_workspace_file])
    with pytest.raises(ValueError):model.bind_tools([write_workspace_file])


def test_reasoning_rejects_malformed_model_identifier(native):
    from council.codex_chat import CodexCLIChatModel
    with pytest.raises(ValueError):CodexCLIChatModel('invalid model',native[0],native[1])
