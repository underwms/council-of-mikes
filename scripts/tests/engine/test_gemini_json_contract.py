"""JSON generation is requested at the provider boundary; parsing stays strict."""
import json

import pytest

from council import gemini_cli
from council.diagnostics import DiagnosticSession, describe
from test_gemini_cli import settings, Answer, inspect_file, output
from test_engine_integration import lifecycle
from test_format_recovery import transport, execute


@pytest.mark.parametrize('mode,expected', [('plain', False), ('tools', True), ('schema', True)])
def test_generation_mode_matches_the_bound_response_contract(settings, monkeypatch, mode, expected):
    observed = []
    def prepare(*args):
        observed.append(args[3] if len(args) > 3 else False)
    monkeypatch.setattr(gemini_cli, '_prepare_isolation', prepare)
    model = gemini_cli.GeminiCLIChatModel('gemini-test', settings)
    if mode == 'tools':
        model = model.bind_tools([inspect_file])
        response = '{"content":"ready","tool_calls":[]}'
    elif mode == 'schema':
        model = model.with_structured_output(Answer)
        response = '{"count":1}'
    else:
        response = 'ready'
    monkeypatch.setattr(gemini_cli, '_run', lambda *args: json.dumps({'response': response}).encode())
    model.invoke([])
    assert observed == [expected]


def test_inspection_generation_schema_limits_names_and_describes_arguments(settings, monkeypatch):
    from copy import deepcopy
    observed = []
    monkeypatch.setattr(gemini_cli, '_prepare_isolation', lambda *args: observed.append(args[5]))
    monkeypatch.setattr(gemini_cli, '_run', lambda *args: b'{"response":"{\\"content\\":\\"ready\\",\\"tool_calls\\":[]}"}')
    read = inspect_file.model_copy(update={'name': 'read_workspace_file'})
    model = gemini_cli.GeminiCLIChatModel('gemini-test', settings).bind_tools([read])
    original = deepcopy(model._tools)
    model.invoke([])
    schema = observed[0]
    assert schema['required'] == ['content', 'tool_calls']
    calls = schema['properties']['tool_calls']
    variant = calls['items']
    assert variant['properties']['name'] == {'type': 'string', 'enum': ['read_workspace_file']}
    assert variant['properties']['args']['properties'] == original[0]['parameters']['properties']
    assert variant['required'] == ['name', 'args', 'id']
    variant['properties']['args']['properties'].clear()
    assert model._tools == original


def test_generation_schema_is_limited_to_compatible_read_only_tools():
    schema = gemini_cli._tool_response_schema
    def definition(name, kind, default):
        return {'name': name, 'parameters': {'type': 'object', 'properties': {'rel_path': {'type': kind, 'default': default}}}}
    tools = [definition('read_workspace_file', 'string', '.'), definition('list_workspace_files', 'string', 'src')]
    combined = schema(tools)
    assert combined['properties']['tool_calls']['items']['properties']['name']['enum'] == [tool['name'] for tool in tools]
    assert combined['properties']['tool_calls']['items']['properties']['args']['properties'] == {'rel_path': {'type': 'string'}}
    assert schema([]) is None
    assert schema([definition('write_workspace_file', 'string', '.')]) is None
    assert schema([tools[0], definition('list_workspace_files', 'integer', 1)]) is None


@pytest.mark.parametrize('response,reason', [
    ('', 'EMPTY'),
    ('```json\n{"content":"PRIVATE_RESPONSE","tool_calls":[]}\n```', 'MARKDOWN_FENCE'),
    ('{"content":"PRIVATE_RESPONSE\\q","tool_calls":[]}', 'INVALID_ESCAPE'),
    ('{"content":"PRIVATE_RESPONSE', 'UNTERMINATED_STRING'),
    ('{"content":"a","content":"PRIVATE_RESPONSE","tool_calls":[]}', 'DUPLICATE_KEY'),
    ('{"content":NaN,"tool_calls":[]}', 'NONFINITE_NUMBER'),
    ('{"content":"PRIVATE_RESPONSE","tool_calls":[]} trailing', 'TRAILING_DATA'),
])
def test_rejected_model_json_keeps_finite_reason_without_payload(settings, response, reason):
    output(settings, {'response': response})
    model = gemini_cli.GeminiCLIChatModel('gemini-test', settings).bind_tools([inspect_file])
    with pytest.raises(ValueError) as caught:
        model.invoke([])
    detail = describe(caught.value)
    assert detail['code'] == 'GEMINI_RESPONSE_JSON_INVALID'
    assert detail['response_json']['reason'] == reason
    assert detail['response_json']['response_bytes'] == len(response.encode())
    assert 'PRIVATE_RESPONSE' not in json.dumps(detail) + str(caught.value)


def test_parse_reason_survives_graph_checkpoint_and_diagnostic_events(lifecycle, transport):
    malformed = '```json\n{"content":"PRIVATE_RESPONSE","tool_calls":[]}\n```'
    transport.responses.extend([malformed, malformed])
    with DiagnosticSession(lifecycle.state.run_id, lifecycle.context.memory_root):
        result, saved = execute(lifecycle, transport.model)
    assert result['status'] == 'FAILED'
    assert saved['diagnostic']['response_json']['reason'] == 'MARKDOWN_FENCE'
    assert saved['model_calls'][0]['diagnostic']['response_json']['reason'] == 'MARKDOWN_FENCE'
    recorded = (lifecycle.context.memory_root/'diagnostics'/f'{lifecycle.state.run_id}.jsonl').read_text()
    events = [json.loads(line) for line in recorded.splitlines()]
    assert any(event.get('response_json', {}).get('reason') == 'MARKDOWN_FENCE' for event in events)
    assert 'PRIVATE_RESPONSE' not in recorded + json.dumps(saved)


def test_format_correction_uses_safe_parse_reason_without_rejected_content(lifecycle, transport):
    transport.responses.extend(['{"content":"PRIVATE_RESPONSE\\q","tool_calls":[]}',
        '{"content":"Inspection complete.","tool_calls":[]}', lifecycle.plan.model_dump_json()])
    result, saved = execute(lifecycle, transport.model)
    assert '__interrupt__' in result
    correction = transport.requests[1]['messages'][-1]['content']
    assert 'INVALID_ESCAPE' in correction and 'forward slashes' in correction
    assert 'PRIVATE_RESPONSE' not in correction + json.dumps(saved)


@pytest.mark.parametrize('changes', [
    {'reason': 'PRIVATE_RESPONSE'}, {'line': True}, {'line': 0}, {'position': -1},
    {'column': 4194306}, {'response_bytes': True}, {'response_bytes': 4194305},
    {'PRIVATE_RESPONSE': 'PRIVATE_RESPONSE'},
])
def test_mutated_json_diagnostics_are_revalidated(changes):
    from council.diagnostics import DiagnosticValueError
    original = {'reason': 'INVALID_ESCAPE', 'response_bytes': 100, 'line': 1, 'column': 20, 'position': 19}
    error = DiagnosticValueError('GEMINI_RESPONSE_JSON_INVALID', response_json=original)
    error.response_json.update(changes)
    assert 'response_json' not in describe(error)


def test_json_mode_is_rejected_if_native_settings_drop_the_generation_contract(settings, tmp_path):
    from pathlib import Path
    from test_gemini_cli import _prepare_isolation
    entry = Path(settings['entrypoint'])
    entry.write_text('const { main } = await import("./main.js");')
    (entry.parent/'main.js').write_text('import { loadSettings } from "./settings.js";\nimport { Storage } from "./core.js";')
    (entry.parent/'settings.js').write_text('import fs from "node:fs";export function loadSettings(cwd){const merged=JSON.parse(fs.readFileSync(cwd+"/.gemini/settings.json","utf8"));delete merged.modelConfigs;return {isTrusted:true,errors:[],merged}}')
    (entry.parent/'core.js').write_text('export class Storage {static getSystemPoliciesDir(){return '+json.dumps(str(tmp_path/'no-policy'))+';}}')
    scratch = tmp_path/'isolation'
    scratch.mkdir()
    with pytest.raises(RuntimeError, match='isolation'):
        _prepare_isolation(scratch, {}, settings, True, 'gemini-test')


@pytest.mark.parametrize('mutation', [
    'delete config.responseJsonSchema;',
    'config.responseJsonSchema.properties.name.enum=["unoffered"];',
])
def test_native_schema_must_survive_effective_settings_exactly(settings, tmp_path, mutation):
    from pathlib import Path
    from test_gemini_cli import _prepare_isolation
    entry = Path(settings['entrypoint'])
    entry.write_text('const { main } = await import("./main.js");')
    (entry.parent/'main.js').write_text('import { loadSettings } from "./settings.js";\nimport { Storage } from "./core.js";')
    (entry.parent/'settings.js').write_text('import fs from "node:fs";export function loadSettings(cwd){const merged=JSON.parse(fs.readFileSync(cwd+"/.gemini/settings.json","utf8"));const config=merged.modelConfigs.overrides[0].modelConfig.generateContentConfig;'+mutation+'return {isTrusted:true,errors:[],merged}}')
    (entry.parent/'core.js').write_text('export class Storage {static getSystemPoliciesDir(){return '+json.dumps(str(tmp_path/'no-policy'))+';}}')
    scratch = tmp_path/'isolation'
    scratch.mkdir()
    schema = {'type': 'object', 'properties': {'name': {'type': 'string', 'enum': ['offered']}}}
    with pytest.raises(RuntimeError, match='isolation'):
        _prepare_isolation(scratch, {}, settings, True, 'gemini-test', schema)
