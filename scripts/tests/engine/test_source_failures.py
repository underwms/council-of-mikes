"""Missing planning evidence is recoverable; real I/O failures remain terminal."""
import json
from types import SimpleNamespace

import pytest
from council.diagnostics import DiagnosticRuntimeError, DiagnosticSession, describe
from council.graph import execute_tool_calls
from council.tools.discovery import get_discovery_tools
from council.tools.tool_registry import get_council_tools
from test_engine_integration import lifecycle
from test_format_recovery import transport, execute

SECRET = 'PRIVATE_FAILED_SOURCE_SENTINEL'


def response(name='read_workspace_file', args=None):
    return SimpleNamespace(tool_calls=[dict(name=name, args=args or {}, id='source')])


@pytest.mark.parametrize('name', ['read_workspace_file', 'list_workspace_files', 'search_workspace_text'])
def test_missing_source_returns_finite_feedback(lifecycle, name):
    tools = {t.name: t for t in get_council_tools(specialist='the-architect', context=lifecycle.context)
             + get_discovery_tools(lifecycle.context)}
    args = {'rel_path': SECRET + '/missing.ts'}
    if name == 'search_workspace_text':
        args['pattern'] = SECRET
    messages = []

    execute_tool_calls(response(name, args), tools, messages, lifecycle.state, planning=True)

    detail = lifecycle.state.tool_call_history[-1]
    assert detail == {'tool': name, 'succeeded': False, 'tool_failure':
                      {'tool': name, 'tool_index': 1, 'reason': 'SOURCE_MISSING'}}
    assert 'SOURCE_MISSING' in messages[-1].content
    assert 'unavailable' in lifecycle.state.planning_evidence[-1]
    assert SECRET not in json.dumps(detail) + str(lifecycle.state.planning_evidence) + messages[-1].content


def test_missing_read_then_valid_read_reaches_gate_and_checkpoint(lifecycle, transport, capsys):
    transport.responses.extend([
        json.dumps({'content': '', 'tool_calls': [{'name': 'read_workspace_file', 'args': {'rel_path': SECRET}, 'id': 'missing'}]}),
        json.dumps({'content': '', 'tool_calls': [{'name': 'read_workspace_file', 'args': {'rel_path': 'verify.py'}, 'id': 'exists'}]}),
        '{"content":"Missing source remains unverified; inspection finished.","tool_calls":[]}',
        lifecycle.plan.model_dump_json()])
    with DiagnosticSession(lifecycle.state.run_id, lifecycle.context.memory_root) as session:
        result, saved = execute(lifecycle, transport.model)
        path = session.path

    assert '__interrupt__' in result
    assert saved['tool_call_history'][0]['tool_failure']['reason'] == 'SOURCE_MISSING'
    assert saved['tool_call_history'][1]['succeeded'] is True
    assert len(transport.requests) == 4
    assert saved['planning_inspection']['rounds_used'] == 3
    assert saved['modified_files'] == [] and saved['test_results'] == []
    assert SECRET not in json.dumps(saved) + path.read_text() + capsys.readouterr().err
    assert any(json.loads(line).get('tool_failure', {}).get('reason') == 'SOURCE_MISSING'
               for line in path.read_text().splitlines())


@pytest.mark.parametrize('error,reason,code', [
    (PermissionError(13, SECRET, SECRET), 'PERMISSION_DENIED', 'PERMISSION_DENIED'),
    (OSError(5, SECRET, SECRET), 'IO_ERROR', 'TOOL_EXECUTION_FAILED'),
    (NotADirectoryError(20, SECRET, SECRET), 'NOT_A_DIRECTORY', 'TOOL_EXECUTION_FAILED'),
    (IsADirectoryError(21, SECRET, SECRET), 'IS_A_DIRECTORY', 'TOOL_EXECUTION_FAILED'),
    (ValueError(SECRET), 'TOOL_ERROR', 'TOOL_EXECUTION_FAILED'),
])
def test_terminal_tool_failure_is_classified_and_checkpointed(lifecycle, transport, monkeypatch, capsys, error, reason, code):
    from langchain_core.tools import tool
    @tool
    def read_workspace_file(rel_path: str) -> str:
        """Inject a filesystem failure at the external tool boundary."""
        raise error
    monkeypatch.setattr('council.graph.get_council_tools', lambda **kw:
                        [read_workspace_file])
    transport.responses.append(json.dumps({'content': '', 'tool_calls': [
        {'name': 'read_workspace_file', 'args': {'rel_path': SECRET}, 'id': 'bad'}]}))
    with DiagnosticSession(lifecycle.state.run_id, lifecycle.context.memory_root) as session:
        result, saved = execute(lifecycle, transport.model)
        path = session.path

    assert result['status'] == 'FAILED' and len(transport.requests) == 1
    assert saved['diagnostic']['code'] == code
    assert saved['diagnostic']['tool_failure'] == {'tool': 'read_workspace_file', 'tool_index': 1, 'reason': reason}
    assert saved['tool_call_history'][-1]['succeeded'] is False
    assert reason in saved['planning_evidence'][-1]
    assert SECRET not in json.dumps(saved) + path.read_text() + capsys.readouterr().err


@pytest.mark.parametrize('planning,name', [(False, 'read_workspace_file'), (True, 'write_workspace_file')])
def test_missing_source_outside_planning_reads_remains_terminal(lifecycle, planning, name):
    def invoke(_):
        raise FileNotFoundError(SECRET)
    with pytest.raises(DiagnosticRuntimeError) as caught:
        execute_tool_calls(response(name), {name: SimpleNamespace(invoke=invoke)}, [], lifecycle.state, planning=planning)
    assert describe(caught.value)['tool_failure']['reason'] == 'SOURCE_MISSING'
    assert isinstance(caught.value.__cause__, FileNotFoundError)
    assert lifecycle.state.tool_call_history[-1]['succeeded'] is False


def test_derived_missing_source_is_not_recoverable(lifecycle):
    class Derived(FileNotFoundError):
        pass
    def invoke(_):
        raise Derived(SECRET)
    with pytest.raises(DiagnosticRuntimeError):
        execute_tool_calls(response(), {'read_workspace_file': SimpleNamespace(invoke=invoke)}, [], lifecycle.state, planning=True)


def test_missing_sources_do_not_extend_round_budget(lifecycle, transport):
    missing = json.dumps({'content': '', 'tool_calls': [{'name': 'read_workspace_file', 'args': {'rel_path': SECRET}, 'id': 'missing'}]})
    transport.responses.extend([missing] * 12 + [lifecycle.plan.model_dump_json()])
    result, saved = execute(lifecycle, transport.model)
    assert '__interrupt__' in result
    assert saved['planning_inspection'] == dict(rounds_used=12, round_limit=12, limit_reached=True)
    assert len(transport.requests) == 13 and len(saved['tool_call_history']) == 12


def test_failure_position_identifies_second_tool_without_arguments(lifecycle):
    tools = {t.name: t for t in get_council_tools(specialist='the-architect', context=lifecycle.context)}
    calls = response(args={'rel_path': 'verify.py'})
    calls.tool_calls += [dict(name='read_workspace_file', args={'rel_path': SECRET}, id='missing')]
    execute_tool_calls(calls, tools, [], lifecycle.state, planning=True)
    assert lifecycle.state.tool_call_history[1]['tool_failure']['tool_index'] == 2


@pytest.mark.parametrize('mutation', ['tool', 'reason', 'index', 'bool', 'extra', 'type'])
def test_diagnostic_revalidates_tool_failure_details(mutation, tmp_path, capsys):
    detail = {'tool': 'read_workspace_file', 'tool_index': 1, 'reason': 'IO_ERROR'}
    if mutation == 'tool': detail['tool'] = SECRET
    if mutation == 'reason': detail['reason'] = SECRET
    if mutation == 'index': detail['tool_index'] = 17
    if mutation == 'bool': detail['tool_index'] = True
    if mutation == 'extra': detail['payload'] = SECRET
    if mutation == 'type': detail = SECRET
    error = DiagnosticRuntimeError('TOOL_EXECUTION_FAILED', tool_failure=detail)
    assert 'tool_failure' not in describe(error)
    error.tool_failure = detail  # Revalidate even after a caller mutates the exception.
    with DiagnosticSession('sanitized', tmp_path) as session:
        session.event('tool_failed', diagnostic=error)
    assert SECRET not in session.path.read_text() + capsys.readouterr().err
    assert all('tool_failure' not in json.loads(line) for line in session.path.read_text().splitlines())


def test_windows_invalid_path_error_is_sanitized(lifecycle):
    error = OSError(22, SECRET, SECRET)
    error.winerror = 123
    def invoke(_):
        raise error
    with pytest.raises(DiagnosticRuntimeError) as caught:
        execute_tool_calls(response(), {'read_workspace_file': SimpleNamespace(invoke=invoke)}, [], lifecycle.state, planning=True)
    assert describe(caught.value)['tool_failure']['reason'] == 'INVALID_PATH'
    assert SECRET not in str(lifecycle.state.tool_call_history) + str(lifecycle.state.planning_evidence)


def test_returned_tool_error_is_terminal_and_records_second_position(lifecycle):
    results = iter(['safe result', {'passed': False, 'error': SECRET}])
    tool = SimpleNamespace(invoke=lambda _: next(results))
    calls = response()
    calls.tool_calls += [dict(name='read_workspace_file', args={}, id='failure')]
    with pytest.raises(DiagnosticRuntimeError) as caught:
        execute_tool_calls(calls, {'read_workspace_file': tool}, [], lifecycle.state, planning=True)
    assert caught.value.code == 'TOOL_EXECUTION_FAILED'
    assert describe(caught.value)['tool_failure']['tool_index'] == 2
    assert SECRET not in str(lifecycle.state.planning_evidence)


def test_unknown_offered_tool_name_is_not_copied_into_failure(lifecycle):
    def invoke(_):
        raise OSError(SECRET)
    with pytest.raises(DiagnosticRuntimeError) as caught:
        execute_tool_calls(response(SECRET), {SECRET: SimpleNamespace(invoke=invoke)}, [], lifecycle.state)
    assert describe(caught.value)['tool_failure']['tool'] == 'unknown'
    assert SECRET not in json.dumps(lifecycle.state.tool_call_history)


def test_discovery_can_still_list_an_existing_source_file(lifecycle):
    tools = {t.name: t for t in get_discovery_tools(lifecycle.context)}
    result = tools['list_workspace_files'].invoke({'rel_path': 'verify.py'})
    assert result == {'files': ['verify.py'], 'truncated': False}


def test_reading_existing_directory_is_terminal_not_missing_evidence(lifecycle):
    tools = {t.name: t for t in get_council_tools(specialist='the-architect', context=lifecycle.context)}
    with pytest.raises(DiagnosticRuntimeError) as caught:
        execute_tool_calls(response(args={'rel_path': 'scripts'}), tools, [], lifecycle.state, planning=True)
    assert describe(caught.value)['tool_failure']['reason'] == 'IS_A_DIRECTORY'


def test_direct_read_stat_permission_error_is_not_mislabeled_missing(lifecycle, monkeypatch):
    from pathlib import Path
    original = Path.stat
    def stat(path, *args, **kwargs):
        if path == lifecycle.workspace/'verify.py':
            raise PermissionError(13, SECRET)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', stat)
    tools = {t.name: t for t in get_council_tools(specialist='the-architect', context=lifecycle.context)}
    with pytest.raises(DiagnosticRuntimeError) as caught:
        execute_tool_calls(response(args={'rel_path': 'verify.py'}), tools, [], lifecycle.state, planning=True)
    assert caught.value.code == 'PERMISSION_DENIED'


def test_direct_read_rejects_nonregular_source(lifecycle, monkeypatch):
    from pathlib import Path
    import stat
    original = Path.stat
    def stat_result(path, *args, **kwargs):
        if path == lifecycle.workspace/'verify.py':
            return SimpleNamespace(st_mode=stat.S_IFIFO)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', stat_result)
    tools = {t.name: t for t in get_council_tools(specialist='the-architect', context=lifecycle.context)}
    with pytest.raises(DiagnosticRuntimeError) as caught:
        execute_tool_calls(response(args={'rel_path': 'verify.py'}), tools, [], lifecycle.state, planning=True)
    assert describe(caught.value)['tool_failure']['reason'] == 'IO_ERROR'
