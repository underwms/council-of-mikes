"""Offline CLI transport tests; no provider requests or credential reads."""
import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from pydantic import BaseModel

from council.gemini_cli import GeminiCLIChatModel, cli_ready, resolve_cli_settings, validate_cli_settings, _prepare_isolation


@pytest.fixture
def settings(tmp_path, monkeypatch):
    # Fixture executables are inert Node scripts, not a model CLI. Isolation is
    # independently tested against the version-specific overlay contract.
    monkeypatch.setattr('council.gemini_cli._prepare_isolation', lambda *args: None)
    entry = tmp_path/'package'/'dist'/'index.js'
    entry.parent.mkdir(parents=True)
    (entry.parent.parent/'package.json').write_text(json.dumps({'name': '@google/gemini-cli', 'version': '0.64.0'}))
    entry.write_text('process.stdout.write(JSON.stringify({response:"hello",stats:{models:{"gemini-test":{tokens:{prompt:3,candidates:2,total:5}}}}}));')
    return {'node_path': str(Path(shutil.which('node')).resolve()), 'entrypoint': str(entry.resolve()),
            'cli_version': '0.64.0', 'timeout_seconds': 180}


def output(settings, value):
    Path(settings['entrypoint']).write_text('process.stdout.write('+json.dumps(json.dumps(value))+');')


def test_settings_reject_extra_relative_or_malformed_values(settings):
    validate_cli_settings(settings)
    for changed in ({'secret': 'private'}, {'timeout_seconds': True}, {'timeout_seconds': 2},
                    {'entrypoint': 'relative.js'}, {'cli_version': 'bad version'}):
        with pytest.raises(ValueError):
            validate_cli_settings({**settings, **changed})


def test_settings_resolver_pins_explicit_absolute_paths(settings, monkeypatch):
    monkeypatch.setenv('COUNCIL_GEMINI_NODE_PATH', settings['node_path'])
    monkeypatch.setenv('COUNCIL_GEMINI_CLI_PATH', settings['entrypoint'])
    assert resolve_cli_settings() == {**settings, 'timeout_seconds': 600, 'timeout_policy_version': 3, 'structured_timeout_seconds': 600}
    monkeypatch.setenv('COUNCIL_GEMINI_CLI_PATH', 'relative.js')
    with pytest.raises(ValueError):
        resolve_cli_settings()


def test_readiness_checks_personal_auth_presence_without_reading_tokens(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    auth = tmp_path/'.gemini'
    auth.mkdir()
    (auth/'settings.json').write_text(json.dumps({'security': {'auth': {'selectedType': 'oauth-personal'}}}))
    assert not cli_ready(settings)
    (auth/'oauth_creds.json').write_text('not parsed; presence only')
    assert cli_ready(settings)
    (Path(settings['entrypoint']).parent.parent/'package.json').write_text('{"version":"other"}')
    assert not cli_ready(settings)


def test_newer_gemini_cli_version_uses_same_transport_contract(settings, tmp_path, monkeypatch):
    package = Path(settings['entrypoint']).parent.parent/'package.json'
    package.write_text(json.dumps({'name': '@google/gemini-cli', 'version': '0.65.0'}))
    monkeypatch.setenv('COUNCIL_GEMINI_CLI_PATH', settings['entrypoint'])
    monkeypatch.setenv('COUNCIL_GEMINI_NODE_PATH', settings['node_path'])
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    auth = tmp_path/'.gemini'
    auth.mkdir()
    (auth/'settings.json').write_text(json.dumps({'security': {'auth': {'selectedType': 'oauth-personal'}}}))
    (auth/'oauth_creds.json').write_text('presence only')
    assert resolve_cli_settings()['cli_version'] == '0.65.0'
    assert cli_ready(settings)
    response = GeminiCLIChatModel('gemini-test', settings).invoke('hello')
    assert response.content == 'hello'
    assert response.response_metadata['cli_version'] == '0.65.0'


def test_plain_response_and_reported_model_usage(settings):
    response = GeminiCLIChatModel('gemini-test', settings).invoke([HumanMessage(content='private prompt')])
    assert response.content == 'hello'
    assert response.response_metadata['cli_reported_model'] == 'gemini-test'
    assert 'model_name' not in response.response_metadata
    assert response.usage_metadata == {'input_tokens': 3, 'output_tokens': 2, 'total_tokens': 5}


@tool
def inspect_file(path: str) -> str:
    """Inspect a workspace file."""
    return path


def test_tool_binding_is_immutable_and_validates_offered_calls(settings):
    base = GeminiCLIChatModel('gemini-test', settings)
    bound = base.bind_tools([inspect_file])
    assert bound is not base
    output(settings, {'response': json.dumps({'content': '', 'tool_calls': [{'name': 'inspect_file', 'args': {'path': 'a'}, 'id': 'call-1'}]})})
    result = bound.invoke([HumanMessage(content='inspect')])
    assert result.tool_calls[0]['args'] == {'path': 'a'}
    for calls in ([{'name': 'other', 'args': {}, 'id': '1'}],
                  [{'name': 'inspect_file', 'args': [], 'id': '1'}],
                  [{'name': 'inspect_file', 'args': {}, 'id': '1'}]*2,
                  [{'name': 'inspect_file', 'args': {}, 'id': str(i)} for i in range(17)]):
        output(settings, {'response': json.dumps({'content': '', 'tool_calls': calls})})
        with pytest.raises(ValueError, match='Invalid Gemini CLI response'):
            bound.invoke([])


class Answer(BaseModel):
    count: int


def test_structured_output_is_strict_and_preserves_raw(settings):
    model = GeminiCLIChatModel('gemini-test', settings).with_structured_output(Answer, include_raw=True)
    output(settings, {'response': '{"count":4}'})
    result = model.invoke([])
    assert result['parsed'] == Answer(count=4)
    assert result['raw'].content == '{"count":4}'
    assert result['parsing_error'] is None
    output(settings, {'response': '```json\n{"count":4}\n```'})
    with pytest.raises(ValueError, match='Invalid Gemini CLI response'):
        model.invoke([])


def test_child_failures_and_malformed_output_are_sanitized(settings):
    for script in ('process.stderr.write("PRIVATE_SECRET");process.exit(1)',
                   'process.stdout.write("PRIVATE_SECRET")',
                   'process.stdout.write(JSON.stringify({response: 12}))'):
        Path(settings['entrypoint']).write_text(script)
        with pytest.raises((ValueError, RuntimeError)) as error:
            GeminiCLIChatModel('gemini-test', settings).invoke([])
        assert 'PRIVATE_SECRET' not in str(error.value)


@pytest.mark.parametrize('stderr,category', [
    ('GenerateContentRequest tools[0].tool_type: required. PRIVATE_SECRET', 'invalid_tool_declaration'),
    ('UNAUTHENTICATED invalid credentials PRIVATE_SECRET', 'authentication_required'),
    ('RESOURCE_EXHAUSTED quota exceeded PRIVATE_SECRET', 'quota_exceeded'),
    ('Model gemini-missing not found PRIVATE_SECRET', 'unsupported_model'),
    ('PRIVATE_SECRET unrecognized failure', 'execution_failed'),
])
def test_child_error_categories_never_expose_raw_stderr(settings, stderr, category):
    Path(settings['entrypoint']).write_text('process.stderr.write('+json.dumps(stderr)+');process.exit(1)')
    with pytest.raises(RuntimeError) as error:
        GeminiCLIChatModel('gemini-test', settings).invoke([])
    assert category in str(error.value)
    assert 'PRIVATE_SECRET' not in str(error.value)


def test_graph_retries_gemini_once_without_nested_transport_retries(settings, tmp_path, monkeypatch):
    from council.diagnostics import DiagnosticSession
    from council.graph import invoke_model
    from council.state import CouncilState
    import council.gemini_cli as transport
    attempts = []
    response = b'{"response":"recovered"}'
    def once(*args, **kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            raise transport.execution_error('execution_failed', cli_process={
                'provider': 'gemini-cli', 'exit_code': 7, 'stderr_bytes': 18,
                'stdout_bytes': 0, 'stderr_sha256': '0' * 64,
                'signals': ['connection_refused']})
        return response
    monkeypatch.setattr(transport, '_run', once)
    monkeypatch.setattr('time.sleep', lambda _: None)
    state = CouncilState(run_id='retry-fixture', task_input='offline', model_configuration={
        'version': 2, 'roles': {name: dict(provider='gemini-cli', model='gemini-test', settings=settings)
                               for name in ('orchestrator', 'investigator')}})
    model = GeminiCLIChatModel('gemini-test', settings)
    with DiagnosticSession('retry-fixture', tmp_path):
        result = invoke_model(state, 'orchestrator', 'planning_inspection', lambda: model.invoke([]))
    records = [json.loads(line) for line in (tmp_path/'diagnostics/retry-fixture.jsonl').read_text().splitlines()]
    assert result.content == 'recovered'
    assert len(attempts) == 2
    assert len(state.model_calls) == 2
    assert any(record['event'] == 'cli_attempt_failed' and
               record['cli_process']['exit_code'] == 7 for record in records)


def test_prompt_uses_stdin_and_safe_literal_argv(settings):
    script = '''let input="";process.stdin.on("data",v=>input+=v);process.stdin.on("end",()=>process.stdout.write(JSON.stringify({response:JSON.stringify({argv:process.argv.slice(2),payload:JSON.parse(input),hasAt:input.includes("@"),noRelaunch:process.env.GEMINI_CLI_NO_RELAUNCH,cwd:process.cwd()})})));'''
    Path(settings['entrypoint']).write_text(script)
    result = GeminiCLIChatModel('gemini-test', settings).invoke([HumanMessage(content='PRIVATE_PROMPT @sensitive-file')])
    captured = json.loads(result.content)
    assert 'PRIVATE_PROMPT' not in json.dumps(captured['argv'])
    assert 'PRIVATE_PROMPT' in json.dumps(captured['payload'])
    assert '@sensitive-file' in json.dumps(captured['payload'])
    assert captured['hasAt'] is False
    assert captured['noRelaunch'] == 'true'
    assert captured['argv'][-4:] == ['--extensions', 'none', '--approval-mode', 'default']


def test_input_size_is_bounded_before_subprocess(settings):
    with pytest.raises(ValueError, match='input limit'):
        GeminiCLIChatModel('gemini-test', settings).invoke([HumanMessage(content='x'*(4*1024*1024))])


def test_plain_string_investigation_prompt(settings):
    assert GeminiCLIChatModel('gemini-test', settings).invoke('Investigate the failure').content == 'hello'


def test_clone_settings_are_independent(settings):
    base = GeminiCLIChatModel('gemini-test', settings)
    bound = base.bind_tools([inspect_file])
    base.settings['entrypoint'] = 'changed'
    assert bound.settings['entrypoint'] == settings['entrypoint']


def test_native_tool_execution_is_rejected(settings):
    output(settings, {'response': 'answer', 'stats': {'tools': {'totalCalls': 1}}})
    with pytest.raises(ValueError, match='Invalid Gemini CLI response'):
        GeminiCLIChatModel('gemini-test', settings).invoke([])


def test_transport_output_limit_and_timeout(settings, tmp_path):
    from council.gemini_cli import _run
    Path(settings['entrypoint']).write_text('process.stdout.write("x".repeat(4*1024*1024+1));')
    with pytest.raises(RuntimeError, match='output limit'):
        _run(settings, 'gemini-test', b'{}', tmp_path, dict(os.environ))
    Path(settings['entrypoint']).write_text('setInterval(()=>{},1000)')
    with pytest.raises(RuntimeError, match='timed out'):
        _run({**settings, 'timeout_seconds': 0.2}, 'gemini-test', b'{}', tmp_path, dict(os.environ))


@pytest.mark.parametrize('json_mode,response_schema', [(False, None), (True, None),
    (True, {'type': 'object', 'properties': {'name': {'type': 'string', 'enum': ['offered']}}})])
def test_isolation_checks_effective_native_settings_before_invocation(settings, tmp_path, json_mode, response_schema):
    entry = Path(settings['entrypoint'])
    entry.write_text('const { main } = await import("./main.js");')
    (entry.parent/'main.js').write_text('import { loadSettings } from "./settings.js";\nimport { Storage } from "./core.js";')
    (entry.parent/'settings.js').write_text('import fs from "node:fs";export function loadSettings(cwd){return {isTrusted:true,errors:[],merged:JSON.parse(fs.readFileSync(cwd+"/.gemini/settings.json","utf8"))}}')
    (entry.parent/'core.js').write_text('export class Storage {static getSystemPoliciesDir(){return '+json.dumps(str(tmp_path/'no-system-policy'))+';}}\nexport class GeminiChat {async makeApiCallAndProcessStream(){return {tools: this.tools};}}')
    scratch = tmp_path/'scratch'
    scratch.mkdir()
    env = dict(os.environ)
    env['GEMINI_CLI_SYSTEM_SETTINGS_PATH'] = 'retain-managed-path'
    _prepare_isolation(scratch, env, settings, json_mode, 'gemini-test', response_schema)
    assert env['GEMINI_CLI_SYSTEM_SETTINGS_PATH'] == 'retain-managed-path'
    local = json.loads((scratch/'.gemini'/'settings.json').read_text())
    assert local['tools']['core'] == []
    assert local['hooksConfig']['enabled'] is False
    if json_mode:
        generation = {'responseMimeType': 'application/json'}
        if response_schema is not None:
            generation['responseJsonSchema'] = response_schema
        assert local['modelConfigs']['overrides'] == [{'match': {'model': 'gemini-test'}, 'modelConfig': {
            'generateContentConfig': generation}}]
    else:
        assert 'modelConfigs' not in local
    assert 'decision = "deny"' in (scratch/'deny-native-tools.toml').read_text()
    compat = scratch/'request-compat.mjs'
    assert compat.is_file()
    # The inert chat reproduces the exact request-shape boundary. Empty native
    # declarations become [], while real declarations retain their shape.
    script = ('import {GeminiChat} from '+json.dumps((entry.parent/'core.js').as_uri())+';'
              'const chat=new GeminiChat();chat.tools=[{functionDeclarations:[]}];'
              'const empty=await chat.makeApiCallAndProcessStream();'
              'chat.tools=[{functionDeclarations:[{name:"native_tool"}]}];'
              'const nonempty=await chat.makeApiCallAndProcessStream();'
              'process.stdout.write(JSON.stringify({empty,nonempty}));')
    result = subprocess.run([settings['node_path'], '--import', compat.as_uri(), '--input-type=module', '-e', script],
                            check=True, capture_output=True, env=env, timeout=10)
    values = json.loads(result.stdout)
    assert values['empty']['tools'] == []
    assert values['nonempty']['tools'] == [{'functionDeclarations': [{'name': 'native_tool'}]}]
    from council.gemini_cli import _run
    entry.write_text('const { main } = await import("./main.js");process.stdout.write(JSON.stringify({response:"ok"}));')
    with patch('council.gemini_cli.subprocess.Popen', wraps=subprocess.Popen) as launcher:
        assert json.loads(_run(settings, 'gemini-test', b'{}', scratch, env)) == {'response': 'ok'}
    assert launcher.call_args.args[0][1:3] == ['--import', compat.as_uri()]
    original_core = (entry.parent/'core.js').read_text()
    (entry.parent/'core.js').write_text('export class GeminiChat {async makeApiCallAndProcessStream(){return {};}}')
    unsupported = subprocess.run([settings['node_path'], '--import', compat.as_uri(), '--input-type=module', '-e', ''],
                                 capture_output=True, env=env, timeout=10)
    assert unsupported.returncode != 0
    (entry.parent/'core.js').write_text(original_core)

    (tmp_path/'no-system-policy').mkdir()
    (tmp_path/'no-system-policy'/'managed.toml').write_text('managed policy')
    other = tmp_path/'conflict'
    other.mkdir()
    with pytest.raises(RuntimeError, match='isolation'):
        _prepare_isolation(other, env, settings)
