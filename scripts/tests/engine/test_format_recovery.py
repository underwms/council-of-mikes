"""Planning-only format recovery with the real parser and synthetic transport."""
import json
from types import SimpleNamespace

import pytest
from council import gemini_cli
from council.graph import build_council_graph
from council.checkpoint import managed_sqlite_checkpointer
from council.diagnostics import DiagnosticSession, DiagnosticValueError, DiagnosticRuntimeError
from test_engine_integration import lifecycle

SECRET = 'PRIVATE_REJECTED_RESPONSE_SENTINEL'


@pytest.fixture
def transport(lifecycle, monkeypatch):
    settings = {'node_path': str(lifecycle.workspace/'node.exe'), 'entrypoint': str(lifecycle.workspace/'gemini.js'),
                'cli_version': '0.64.0', 'timeout_seconds': 180}
    model = gemini_cli.GeminiCLIChatModel('synthetic', settings, lifecycle.context)
    monkeypatch.setattr(gemini_cli, '_installed', lambda _: True)
    monkeypatch.setattr(gemini_cli, '_prepare_isolation', lambda *args: None)
    responses, requests = [], []
    def run(settings, model, payload, directory, env):
        requests.append(json.loads(payload))
        assert responses, 'Unexpected extra model attempt'
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return json.dumps({'response': response}).encode()
    monkeypatch.setattr(gemini_cli, '_run', run)
    return SimpleNamespace(model=model, responses=responses, requests=requests)


def execute(fixture, model):
    with managed_sqlite_checkpointer(context=fixture.context, db_path=fixture.db) as saver:
        graph = build_council_graph(saver, fixture.context, lambda role: model)
        result = graph.invoke(fixture.state.model_dump(mode='json'), fixture.config)
        saved = graph.get_state(fixture.config).values
    return result, saved


@pytest.mark.parametrize('malformed', [
    SECRET, '```json\n{"content":"' + SECRET + '","tool_calls":[]}\n```',
    '{"content":"' + SECRET, '{"content":"' + SECRET + '","content":"duplicate","tool_calls":[]}',
])
def test_single_format_retry_reaches_gate_one_without_executing_tools(lifecycle, transport, monkeypatch, capsys, malformed):
    transport.responses.extend([malformed, '{"content":"Inspection complete.","tool_calls":[]}', lifecycle.plan.model_dump_json()])
    monkeypatch.setattr('council.graph.execute_tool_calls', lambda *args: pytest.fail('No tool calls were validly requested'))
    with DiagnosticSession(lifecycle.state.run_id, lifecycle.context.memory_root):
        result, saved = execute(lifecycle, transport.model)
    assert result['__interrupt__'][0].value['gate'] == 'GATE_1_PLAN_APPROVAL'
    assert len(transport.requests) == 3
    assert [call['operation'] for call in saved['model_calls']] == ['planning_inspection', 'planning_format_retry', 'planning']
    assert [call['status'] for call in saved['model_calls']] == ['failed', 'succeeded', 'succeeded']
    assert [call['call'] for call in saved['model_calls']] == [1, 2, 3]
    assert SECRET not in json.dumps(saved)
    output = capsys.readouterr().err
    assert SECRET not in output
    assert 'planning_format_retry' in output
    assert SECRET not in json.dumps(transport.requests[1])
    assert SECRET not in (lifecycle.context.memory_root/'diagnostics'/f'{lifecycle.state.run_id}.jsonl').read_text()
    assert not transport.responses


def test_second_format_failure_is_terminal(lifecycle, transport):
    transport.responses.extend([SECRET, SECRET])
    result, saved = execute(lifecycle, transport.model)
    assert result['status'] == 'FAILED'
    assert len(transport.requests) == 2
    assert saved['diagnostic']['code'] == 'GEMINI_RESPONSE_JSON_INVALID'
    assert len(saved['model_calls']) == 2
    assert saved['tool_call_history'] == []


@pytest.mark.parametrize('response,expected', [
    (DiagnosticRuntimeError('CLI_TIMEOUT'), 'CLI_TIMEOUT'),
    (DiagnosticRuntimeError('CLI_AUTH_REQUIRED'), 'CLI_AUTH_REQUIRED'),
    (DiagnosticRuntimeError('CLI_QUOTA_EXCEEDED'), 'CLI_QUOTA_EXCEEDED'),
    (PermissionError(SECRET), 'PERMISSION_DENIED'),
    (DiagnosticValueError('GEMINI_NATIVE_TOOLS_REJECTED'), 'GEMINI_NATIVE_TOOLS_REJECTED'),
    (DiagnosticValueError('GEMINI_ENVELOPE_INVALID'), 'GEMINI_ENVELOPE_INVALID'),
    (DiagnosticValueError('GEMINI_SCHEMA_INVALID'), 'GEMINI_SCHEMA_INVALID'),
])
def test_nonformat_failures_only_use_the_bounded_transport_policy(lifecycle, transport, response, expected):
    attempts = 2 if expected == 'CLI_TIMEOUT' else 1
    transport.responses.extend([response] * attempts)
    result, saved = execute(lifecycle, transport.model)
    assert result['status'] == 'FAILED'
    assert saved['diagnostic']['code'] == expected
    assert len(transport.requests) == attempts


@pytest.mark.parametrize('invalid,code', [
    ({'content': SECRET}, 'GEMINI_TOOL_ENVELOPE_INVALID'),
    ({'content': '', 'tool_calls': [{'name': SECRET, 'args': {}, 'id': 'c'}]}, 'GEMINI_TOOL_NAME_UNOFFERED'),
    ({'content': '', 'tool_calls': [{'name': 'list_workspace_files', 'args': [], 'id': 'c'}]}, 'GEMINI_TOOL_ARGUMENTS_INVALID'),
    ({'content': '', 'tool_calls': [{'name': 'list_workspace_files', 'args': {}}]}, 'GEMINI_TOOL_CALL_INVALID'),
    ({'content': '', 'tool_calls': [{'name': 'list_workspace_files', 'args': {}, 'id': 'bad id'}]}, 'GEMINI_TOOL_CALL_INVALID'),
])
def test_rejected_inspection_contract_receives_one_safe_correction(lifecycle, transport, invalid, code):
    transport.responses.extend([json.dumps(invalid), '{"content":"Done.","tool_calls":[]}', lifecycle.plan.model_dump_json()])
    result, saved = execute(lifecycle, transport.model)
    assert result['__interrupt__'][0].value['gate'] == 'GATE_1_PLAN_APPROVAL'
    assert saved['model_calls'][0]['diagnostic']['code'] == code
    correction = transport.requests[1]['messages'][-1]['content']
    assert code in correction
    assert 'read_workspace_file' in correction and 'list_workspace_files' in correction
    assert SECRET not in correction + json.dumps(saved)
    assert saved['tool_call_history'] == []
    assert len(transport.requests) == 3


def test_rejected_batch_dispatches_no_valid_prefix_before_correction(lifecycle, transport):
    valid = {'name': 'list_workspace_files', 'args': {}, 'id': 'valid'}
    transport.responses.extend([
        json.dumps({'content': '', 'tool_calls': [valid, {'name': SECRET, 'args': {}, 'id': 'invalid'}]}),
        json.dumps({'content': '', 'tool_calls': [valid]}),
        '{"content":"Done.","tool_calls":[]}', lifecycle.plan.model_dump_json()])
    result, saved = execute(lifecycle, transport.model)
    assert '__interrupt__' in result
    assert saved['tool_call_history'] == [{'tool': 'list_workspace_files', 'succeeded': True}]
    assert len(transport.requests) == 4


@pytest.mark.parametrize('arguments', [{'path': SECRET}, {'rel_path': [SECRET]}])
def test_inspection_corrects_argument_schema_errors_before_dispatch(lifecycle, transport, arguments):
    transport.responses.extend([
        json.dumps({'content': '', 'tool_calls': [
            {'name': 'list_workspace_files', 'args': {}, 'id': 'valid-prefix'},
            {'name': 'read_workspace_file', 'args': arguments, 'id': 'bad-arguments'}]}),
        json.dumps({'content': '', 'tool_calls': [
            {'name': 'read_workspace_file', 'args': {'rel_path': 'verify.py'}, 'id': 'corrected'}]}),
        '{"content":"Done.","tool_calls":[]}', lifecycle.plan.model_dump_json()])
    result, saved = execute(lifecycle, transport.model)
    assert '__interrupt__' in result
    assert saved['model_calls'][0]['diagnostic']['code'] == 'GEMINI_TOOL_ARGUMENTS_INVALID'
    assert saved['tool_call_history'] == [{'tool': 'read_workspace_file', 'succeeded': True}]
    assert len(transport.requests) == 4
    assert SECRET not in json.dumps(transport.requests[1]) + json.dumps(saved)


def test_second_contract_failure_is_terminal_without_dispatch(lifecycle, transport):
    response = json.dumps({'content': '', 'tool_calls': [{'name': SECRET, 'args': {}, 'id': 'c'}]})
    transport.responses.extend([response, response])
    result, saved = execute(lifecycle, transport.model)
    assert result['status'] == 'FAILED'
    assert saved['diagnostic']['code'] == 'GEMINI_TOOL_NAME_UNOFFERED'
    assert len(transport.requests) == 2
    assert saved['tool_call_history'] == []


def test_tool_request_from_corrective_attempt_executes_only_after_validation(lifecycle, transport):
    transport.responses.extend([SECRET,
        json.dumps({'content': '', 'tool_calls': [{'name': 'list_workspace_files', 'args': {}, 'id': 'c'}]}),
        '{"content":"Done.","tool_calls":[]}', lifecycle.plan.model_dump_json()])
    result, saved = execute(lifecycle, transport.model)
    assert '__interrupt__' in result
    assert saved['tool_call_history'] == [{'tool': 'list_workspace_files', 'succeeded': True}]
    assert len(transport.requests) == 4


def test_structured_plan_parse_error_has_one_format_retry_then_stops(lifecycle, transport):
    transport.responses.extend(['{"content":"Done.","tool_calls":[]}', SECRET, SECRET])
    result, saved = execute(lifecycle, transport.model)
    assert result['status'] == 'FAILED'
    assert [call['operation'] for call in saved['model_calls']] == ['planning_inspection', 'planning','planning_format_retry']
    assert saved['diagnostic']['code']=='GEMINI_RESPONSE_JSON_INVALID'
    assert SECRET not in json.dumps(saved['model_calls'])


def test_api_role_does_not_receive_cli_format_recovery(lifecycle, transport, monkeypatch):
    monkeypatch.setenv('COUNCIL_ORCHESTRATOR_PROVIDER', 'gpt')
    transport.responses.append(SECRET)
    result, saved = execute(lifecycle, transport.model)
    assert result['status'] == 'FAILED'
    assert len(saved['model_calls']) == 1
    assert not transport.responses


def test_legacy_coding_call_does_not_receive_inspection_recovery(lifecycle, transport):
    configuration = {'version':2,'roles':{role:{'provider':'gemini-cli','model':'synthetic',
        'settings':dict(transport.model.settings)} for role in ('orchestrator','investigator')}}
    lifecycle.state.model_configuration = configuration
    lifecycle.state.auto_approve = True
    transport.responses.extend(['{"content":"Done.","tool_calls":[]}', lifecycle.plan.model_dump_json(), SECRET])
    result, saved = execute(lifecycle, transport.model)
    assert result['status'] == 'FAILED'
    assert [call['operation'] for call in saved['model_calls']] == ['planning_inspection', 'planning', 'worker']
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_corrective_call_must_also_pass_tool_validation(lifecycle, transport):
    transport.responses.extend([SECRET, json.dumps({'content': '', 'tool_calls': [
        {'name': 'unoffered', 'args': {}, 'id': 'c'}]})])
    result, saved = execute(lifecycle, transport.model)
    assert result['status'] == 'FAILED'
    assert saved['diagnostic']['code'] == 'GEMINI_TOOL_NAME_UNOFFERED'
    assert len(saved['model_calls']) == 2
    assert saved['tool_call_history'] == []


def test_corrective_tool_execution_failure_never_retries(lifecycle, transport, monkeypatch):
    transport.responses.extend([SECRET, json.dumps({'content': '', 'tool_calls': [
        {'name': 'list_workspace_files', 'args': {}, 'id': 'c'}]})])
    def fail(*args, **kwargs):
        raise DiagnosticRuntimeError('TOOL_EXECUTION_FAILED')
    monkeypatch.setattr('council.graph.execute_tool_calls', fail)
    result, saved = execute(lifecycle, transport.model)
    assert result['status'] == 'FAILED'
    assert saved['diagnostic']['code'] == 'TOOL_EXECUTION_FAILED'
    assert len(transport.requests) == 2


def test_recovery_does_not_extend_twelve_inspection_round_limit(lifecycle, transport):
    for number in range(12):
        transport.responses.extend([SECRET, json.dumps({'content': '', 'tool_calls': [
            {'name': 'list_workspace_files', 'args': {}, 'id': f'c-{number}'}]})])
    transport.responses.append(lifecycle.plan.model_dump_json())
    result, saved = execute(lifecycle, transport.model)
    assert result['__interrupt__'][0].value['gate'] == 'GATE_1_PLAN_APPROVAL'
    assert len(transport.requests) == 25
    assert len(saved['tool_call_history']) == 12
    assert len([call for call in saved['model_calls'] if call['operation'] == 'planning_inspection']) == 12
    assert len([call for call in saved['model_calls'] if call['operation'] == 'planning_format_retry']) == 12
    assert saved['model_calls'][-1]['operation'] == 'planning'
    assert all(call['settings']['timeout_seconds'] == 600 for call in saved['model_calls'])
