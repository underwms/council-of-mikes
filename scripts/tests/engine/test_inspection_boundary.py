"""Controlled planning denials are unavailable evidence, never authorization."""
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from council.graph import execute_tool_calls
from council.state import CouncilState
from council.diagnostics import DiagnosticSession, DiagnosticRuntimeError
from council.tools.tool_registry import get_council_tools
from council.tools.discovery import get_discovery_tools,validate_discovery_path
from test_engine_integration import lifecycle
from test_format_recovery import transport,execute


def test_controlled_exclusion_returns_unavailable_then_synthesis(lifecycle,transport,capsys):
    (lifecycle.workspace/'.env').write_text('PRIVATE_SECRET_SENTINEL')
    transport.responses.extend([
        json.dumps({'content':'','tool_calls':[{'name':'read_workspace_file','args':{'rel_path':'.env'},'id':'blocked'}]}),
        json.dumps({'content':'','tool_calls':[{'name':'read_workspace_file','args':{'rel_path':'verify.py'},'id':'safe'}]}),
        '{"content":"Inspection complete; private input unavailable.","tool_calls":[]}',
        lifecycle.plan.model_dump_json()])
    with DiagnosticSession(lifecycle.state.run_id,lifecycle.context.memory_root) as session:
        result,saved=execute(lifecycle,transport.model)
        path=session.path
    assert '__interrupt__' in result
    assert saved['planning_inspection']['rounds_used']==3
    assert saved['tool_call_history'][0]==dict(tool='read_workspace_file',succeeded=False,boundary_reason='PATH_EXCLUDED')
    receipt=saved['planning_evidence'][0]
    assert 'PATH_EXCLUDED' in receipt and 'unavailable' in receipt
    assert '.env' not in receipt and 'PRIVATE_SECRET' not in receipt
    assert saved['modified_files']==[]
    events=[json.loads(line) for line in path.read_text().splitlines()]
    rejection=next(e for e in events if e['event']=='inspection_read_rejected')
    assert rejection['boundary_reason']=='PATH_EXCLUDED'
    assert 'PRIVATE_SECRET' not in path.read_text()+capsys.readouterr().err


@pytest.mark.parametrize('path,reason', [('.env','PATH_EXCLUDED'),('.git/config','PATH_EXCLUDED'),
    ('../outside','PATH_PARENT_TRAVERSAL')])
def test_explicit_discovery_denial_is_typed_and_does_not_expose_path(lifecycle,path,reason):
    with pytest.raises(PermissionError) as caught:
        validate_discovery_path(lifecycle.context,path)
    assert getattr(caught.value,'reason',None)==reason
    assert path not in str(caught.value)


def test_absolute_workspace_denial_is_typed(lifecycle):
    with pytest.raises(PermissionError) as caught:
        lifecycle.context.workspace_path(str(lifecycle.workspace/'PRIVATE_PATH'))
    assert getattr(caught.value,'reason',None)=='PATH_ABSOLUTE'
    assert 'PRIVATE_PATH' not in str(caught.value)


def test_link_guard_and_resolved_escape_remain_rejected(lifecycle,monkeypatch):
    monkeypatch.setattr('council.tools.discovery._linked',lambda p:True)
    with pytest.raises(PermissionError) as caught:
        validate_discovery_path(lifecycle.context,'verify.py')
    assert getattr(caught.value,'reason',None)=='PATH_LINKED'
    with pytest.raises(PermissionError) as escaped:
        lifecycle.context.workspace_path(str(lifecycle.workspace.parent/'PRIVATE_OUTSIDE'),allow_absolute=True)
    assert getattr(escaped.value,'reason',None)=='PATH_OUTSIDE_WORKSPACE'


@pytest.mark.parametrize('inspection',['planning','intake'])
def test_native_permission_failure_still_propagates(lifecycle,inspection):
    def invoke(_):raise PermissionError('PRIVATE_NATIVE_ERROR')
    response=SimpleNamespace(tool_calls=[dict(name='read_workspace_file',args={},id='native')])
    with pytest.raises(DiagnosticRuntimeError) as caught:
        execute_tool_calls(response,{'read_workspace_file':SimpleNamespace(invoke=invoke)},[],lifecycle.state,**{inspection:True})
    assert caught.value.code=='PERMISSION_DENIED'
    assert isinstance(caught.value.__cause__,PermissionError)
    assert lifecycle.state.tool_call_history[-1]['tool_failure']['reason']=='PERMISSION_DENIED'
    assert 'PRIVATE_NATIVE_ERROR' not in str(lifecycle.state.planning_evidence)


def test_coding_denial_remains_terminal(lifecycle):
    tools={t.name:t for t in get_council_tools(context=lifecycle.context,specialist='the-architect')}
    response=SimpleNamespace(tool_calls=[dict(name='read_workspace_file',args={'rel_path':'.env'},id='blocked')])
    with pytest.raises(DiagnosticRuntimeError) as caught:execute_tool_calls(response,tools,[],lifecycle.state,planning=False)
    assert caught.value.code=='PERMISSION_DENIED'
    assert lifecycle.state.tool_call_history[-1]['succeeded'] is False


def test_denied_rounds_cannot_extend_inspection_budget(lifecycle,transport):
    for n in range(12):
        transport.responses.append(json.dumps({'content':'','tool_calls':[{'name':'read_workspace_file','args':{'rel_path':'.env'},'id':f'blocked-{n}'}]}))
    transport.responses.append(lifecycle.plan.model_dump_json())
    result,saved=execute(lifecycle,transport.model)
    assert '__interrupt__' in result
    assert saved['planning_inspection']==dict(rounds_used=12,round_limit=12,limit_reached=True)
    assert len(transport.requests)==13
    assert len(saved['tool_call_history'])==12
    assert all(not item['succeeded'] for item in saved['tool_call_history'])
    assert saved['modified_files']==[]


@pytest.mark.parametrize('inspection',['planning','intake'])
@pytest.mark.parametrize('name', ['list_workspace_files','search_workspace_text'])
def test_discovery_list_and_search_denials_are_also_read_only_feedback(lifecycle,name,inspection):
    tools={t.name:t for t in get_discovery_tools(lifecycle.context)}
    args={'rel_path':'.git'}
    if name=='search_workspace_text':args['pattern']='fixture'
    response=SimpleNamespace(tool_calls=[dict(name=name,args=args,id='blocked')])
    messages=[]
    execute_tool_calls(response,tools,messages,lifecycle.state,**{inspection:True})
    assert lifecycle.state.tool_call_history[0]['succeeded'] is False
    assert 'PATH_EXCLUDED' in messages[0].content


@pytest.mark.parametrize('inspection',['planning','intake'])
def test_unknown_and_forged_boundary_errors_remain_terminal(lifecycle,inspection):
    from council.boundaries import WorkspaceBoundaryError,read_feedback
    with pytest.raises(ValueError):WorkspaceBoundaryError('PRIVATE_UNKNOWN_REASON')
    assert read_feedback(PermissionError('PRIVATE_NATIVE_ERROR')) is None
    for mutation in ['unknown','subclass']:
        if mutation=='subclass':
            class Derived(WorkspaceBoundaryError):pass
            error=Derived('PATH_EXCLUDED')
        else:
            error=WorkspaceBoundaryError('PATH_EXCLUDED');error.reason=['PRIVATE_REASON']
        def invoke(_,error=error):raise error
        response=SimpleNamespace(tool_calls=[dict(name='read_workspace_file',args={},id='denied')])
        with pytest.raises(DiagnosticRuntimeError) as caught:
            execute_tool_calls(response,{'read_workspace_file':SimpleNamespace(invoke=invoke)},[],lifecycle.state,**{inspection:True})
        assert caught.value.code=='PERMISSION_DENIED'


@pytest.mark.parametrize('inspection',['planning','intake'])
def test_planning_flag_cannot_recover_a_write_tool_denial(lifecycle,inspection):
    from council.boundaries import WorkspaceBoundaryError
    def invoke(_):raise WorkspaceBoundaryError('PATH_OUTSIDE_WORKSPACE')
    response=SimpleNamespace(tool_calls=[dict(name='write_workspace_file',args={},id='denied')])
    with pytest.raises(DiagnosticRuntimeError) as caught:
        execute_tool_calls(response,{'write_workspace_file':SimpleNamespace(invoke=invoke)},[],lifecycle.state,**{inspection:True})
    assert caught.value.code=='PERMISSION_DENIED'
    assert lifecycle.state.tool_call_history[-1]['succeeded'] is False


def test_excluded_file_is_never_opened(lifecycle,monkeypatch):
    from pathlib import Path
    original=Path.open
    def opened(path,*args,**kwargs):
        assert path.name!='.env','Excluded file content must never be accessed'
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',opened)
    tools={t.name:t for t in get_council_tools(context=lifecycle.context,specialist='the-architect')}
    response=SimpleNamespace(tool_calls=[dict(name='read_workspace_file',args={'rel_path':'.env'},id='denied')])
    execute_tool_calls(response,tools,[],lifecycle.state,planning=True)
    assert lifecycle.state.tool_call_history[0]['succeeded'] is False


def test_boundary_event_revalidates_finite_reason(lifecycle,capsys):
    with DiagnosticSession(lifecycle.state.run_id,lifecycle.context.memory_root) as session:
        session.event('inspection_read_rejected',boundary_reason='PATH_EXCLUDED')
        session.event('inspection_read_rejected',boundary_reason='PRIVATE_UNKNOWN_REASON')
        path=session.path
    records=[json.loads(line) for line in path.read_text().splitlines() if json.loads(line)['event']=='inspection_read_rejected']
    assert records[0]['boundary_reason']=='PATH_EXCLUDED'
    assert 'boundary_reason' not in records[1]
    assert 'PRIVATE_' not in path.read_text()+capsys.readouterr().err


def test_intake_rejection_diagnostics_retain_only_finite_reason(lifecycle):
    tools={t.name:t for t in get_discovery_tools(lifecycle.context)}
    response=SimpleNamespace(tool_calls=[dict(name='list_workspace_files',args={'rel_path':'../PRIVATE_TARGET_CANARY'},id='blocked')])
    with DiagnosticSession(lifecycle.state.run_id,lifecycle.context.memory_root) as session:
        execute_tool_calls(response,tools,[],lifecycle.state,intake=True)
        path=session.path
    events=[json.loads(line) for line in path.read_text().splitlines()]
    rejection=next(e for e in events if e['event']=='inspection_read_rejected')
    assert rejection['stage']=='intake_draft'
    assert rejection['boundary_reason']=='PATH_PARENT_TRAVERSAL'
    assert 'PRIVATE_TARGET_CANARY' not in path.read_text()+str(lifecycle.state.tool_call_history)
    assert lifecycle.state.planning_evidence==[]


def test_intake_native_permission_diagnostic_has_correct_stage(lifecycle):
    def invoke(_):raise PermissionError('PRIVATE_NATIVE_CANARY')
    response=SimpleNamespace(tool_calls=[dict(name='read_workspace_file',args={},id='denied')])
    with DiagnosticSession(lifecycle.state.run_id,lifecycle.context.memory_root) as session:
        with pytest.raises(DiagnosticRuntimeError):
            execute_tool_calls(response,{'read_workspace_file':SimpleNamespace(invoke=invoke)},[],lifecycle.state,intake=True)
        path=session.path
    failure=next(json.loads(line) for line in path.read_text().splitlines() if json.loads(line)['event']=='tool_failed')
    assert failure['stage']=='intake_draft'
    assert failure['tool_failure']['reason']=='PERMISSION_DENIED'
    assert 'PRIVATE_NATIVE_CANARY' not in path.read_text()


@pytest.mark.parametrize('inspection',['planning','intake'])
def test_read_inspection_missing_file_is_feedback(lifecycle,inspection):
    def invoke(_):raise FileNotFoundError('PRIVATE_MISSING_CANARY')
    response=SimpleNamespace(tool_calls=[dict(name='read_workspace_file',args={},id='missing')])
    messages=[]
    execute_tool_calls(response,{'read_workspace_file':SimpleNamespace(invoke=invoke)},messages,lifecycle.state,**{inspection:True})
    assert 'SOURCE_MISSING' in messages[0].content
    assert 'PRIVATE_MISSING_CANARY' not in str(lifecycle.state.tool_call_history)+str(lifecycle.state.planning_evidence)
    assert lifecycle.state.tool_call_history[-1]['succeeded'] is False
