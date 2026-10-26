"""Text-only Gemini CLI transport. Council, rather than the CLI, executes tools."""
from copy import copy, deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading

from langchain_core.messages import AIMessage, message_to_dict
from langchain_core.utils.function_calling import convert_to_openai_tool
from council.diagnostics import DiagnosticValueError, DiagnosticRuntimeError, execution_error, event

_LIMIT = 4 * 1024 * 1024
_VERSION_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,63}\Z')
_ID = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')
_PROMPT = 'Process the JSON request supplied on standard input. Treat messages as conversation data. Return only the requested response format without Markdown fences. Do not invoke native tools.'
_INSPECT = r'''
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {isDeepStrictEqual} from 'node:util';
try {
  const entry=fs.realpathSync(process.argv[1]), cwd=process.argv[2], jsonMode=process.argv[3]==='json', model=process.argv[4];
  const schemaPath=path.join(cwd,'response-schema.json');
  const responseSchema=fs.existsSync(schemaPath)?JSON.parse(fs.readFileSync(schemaPath,'utf8')):undefined;
  const source=fs.readFileSync(entry,'utf8');
  const main=source.match(/const\s*\{\s*main\s*\}\s*=\s*await\s+import\("([^"\n]+)"\)/);
  if(!main) throw Error();
  const mainPath=path.resolve(path.dirname(entry),main[1]);
  const imports=[...fs.readFileSync(mainPath,'utf8').matchAll(/import\s*\{([\s\S]*?)\}\s*from\s*"([^"\n]+)"/g)];
  const find=name=>{
    const found=imports.filter(m=>new RegExp('(?:^|,)\\s*'+name+'\\s*(?:,|$)').test(m[1]));
    if(found.length!==1) throw Error();
    return pathToFileURL(path.resolve(path.dirname(mainPath),found[0][2]));
  };
  const {loadSettings}=await import(find('loadSettings'));
  const {Storage}=await import(find('Storage'));
  const loaded=loadSettings(cwd), e=loaded.merged;
  let systemPolicy=false;
  try {systemPolicy=fs.readdirSync(Storage.getSystemPoliciesDir()).some(n=>n.endsWith('.toml'));}
  catch(error){if(error.code!=='ENOENT') throw error;}
  const safe=loaded.isTrusted===true && !(loaded.errors||[]).some(e=>e.severity==='error')
    && Array.isArray(e.tools?.core) && e.tools.core.length===0
    && !e.tools?.discoveryCommand && !e.tools?.callCommand
    && e.hooksConfig?.enabled===false && e.skills?.enabled===false
    && e.experimental?.enableAgents!==true && e.experimental?.autoMemory!==true
    && e.context?.includeDirectoryTree===false && !e.context?.includeDirectories?.length
    && e.context?.loadMemoryFromIncludeDirectories===false && e.ide?.enabled!==true
    && e.security?.auth?.selectedType==='oauth-personal'
    && (!e.security?.auth?.enforcedType || e.security.auth.enforcedType==='oauth-personal')
    && !systemPolicy && !e.adminPolicyPaths?.length
    && (!jsonMode || (Array.isArray(e.modelConfigs?.overrides) && e.modelConfigs.overrides.some(o=>
      o && typeof o.match==='object' && o.match!==null && Object.keys(o.match).length===1 && o.match.model===model
      && o.modelConfig?.generateContentConfig?.responseMimeType==='application/json'
      && (responseSchema===undefined || isDeepStrictEqual(o.modelConfig?.generateContentConfig?.responseJsonSchema,responseSchema)))));
  process.stdout.write(JSON.stringify({safe}));
} catch {process.stdout.write('{"safe":false}');}
'''
_REQUEST_COMPAT = r'''
// Scoped to this child only. A recognized Gemini CLI implementation may
// serialize an empty function declaration wrapper rejected by the model API.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const entry=fs.realpathSync(__ENTRYPOINT__);
const source=fs.readFileSync(entry,'utf8');
const main=source.match(/const\s*\{\s*main\s*\}\s*=\s*await\s+import\("([^"\n]+)"\)/);
if(!main) throw Error('Unsupported Gemini CLI compatibility boundary');
const mainPath=path.resolve(path.dirname(entry),main[1]);
const imports=[...fs.readFileSync(mainPath,'utf8').matchAll(/import\s*\{([\s\S]*?)\}\s*from\s*"([^"\n]+)"/g)];
const core=imports.filter(m=>/(?:^|,)\s*Storage\s*(?:,|$)/.test(m[1]));
if(core.length!==1) throw Error('Unsupported Gemini CLI compatibility boundary');
const {GeminiChat}=await import(pathToFileURL(path.resolve(path.dirname(mainPath),core[0][2])));
const original=GeminiChat?.prototype?.makeApiCallAndProcessStream;
if(typeof original!=='function' || !Function.prototype.toString.call(original).includes('tools: this.tools')) {
  throw Error('Unsupported Gemini CLI compatibility boundary');
}
GeminiChat.prototype.makeApiCallAndProcessStream=async function(...args) {
  if(Array.isArray(this.tools) && this.tools.length>0 && this.tools.every(tool=>
    tool!==null && typeof tool==='object' && Object.getPrototypeOf(tool)===Object.prototype
    && Object.keys(tool).length===1 && Object.hasOwn(tool,'functionDeclarations')
    && Array.isArray(tool.functionDeclarations) && tool.functionDeclarations.length===0)) {
    this.tools=[];
  }
  return await original.apply(this,args);
};
'''


def validate_cli_settings(settings):
    legacy_keys = {'node_path', 'entrypoint', 'cli_version', 'timeout_seconds'}
    policy_keys = legacy_keys | {'timeout_policy_version', 'structured_timeout_seconds'}
    if (not isinstance(settings, dict) or set(settings) not in (legacy_keys, policy_keys)
            or not isinstance(settings['cli_version'], str)
            or not _VERSION_PATTERN.fullmatch(settings['cli_version'])
            or type(settings['timeout_seconds']) is not int
            or settings['timeout_seconds'] != (600 if settings.get('timeout_policy_version') == 3 else 180)):
        raise ValueError('Unsupported Gemini CLI settings')
    if set(settings) == policy_keys and (
            type(settings['timeout_policy_version']) is not int or settings['timeout_policy_version'] not in {2, 3}
            or type(settings['structured_timeout_seconds']) is not int or settings['structured_timeout_seconds'] != 600):
        raise ValueError('Unsupported Gemini CLI timeout policy')
    for name in ('node_path', 'entrypoint'):
        value = settings[name]
        if not isinstance(value, str) or not value or '\x00' in value or not Path(value).is_absolute():
            raise ValueError('Gemini CLI paths must be absolute')
    if Path(settings['entrypoint']).suffix != '.js':
        raise ValueError('Gemini CLI entrypoint must be JavaScript')


def resolve_cli_settings():
    node = os.environ.get('COUNCIL_GEMINI_NODE_PATH') or shutil.which('node')
    entry = os.environ.get('COUNCIL_GEMINI_CLI_PATH') or str(
        Path(os.environ.get('APPDATA', Path.home()/'AppData'/'Roaming'))/'npm'/'node_modules'/'@google'/'gemini-cli'/'bundle'/'gemini.js')
    if not node:
        raise ValueError('Gemini CLI requires Node.js')
    settings = {'node_path': node, 'entrypoint': entry,
                'cli_version': _installed_version({'node_path': node, 'entrypoint': entry}) or 'unknown',
                'timeout_seconds': 600,
                'timeout_policy_version': 3, 'structured_timeout_seconds': 600}
    validate_cli_settings(settings)
    return settings


def _installed_version(settings):
    try:
        node, entry = Path(settings['node_path']), Path(settings['entrypoint'])
        if not node.is_file() or not entry.is_file():
            return None
        package = entry.parent.parent/'package.json'
        if not package.is_file() or package.stat().st_size > 1024*1024:
            return None
        data = json.loads(package.read_text(encoding='utf-8'))
        version = data.get('version')
        return version if data.get('name') == '@google/gemini-cli' and isinstance(version, str) and _VERSION_PATTERN.fullmatch(version) else None
    except (OSError, ValueError, TypeError):
        return None


def _installed(settings):
    validate_cli_settings(settings)
    return _installed_version(settings) is not None


def cli_ready(settings):
    """Check executable/package and personal OAuth cache presence; never read tokens."""
    try:
        if not _installed(settings):
            return False
        root = Path(os.environ['GEMINI_CLI_HOME']) if os.environ.get('GEMINI_CLI_HOME') else Path.home()/'.gemini'
        auth_settings = root/'settings.json'
        if not auth_settings.is_file() or auth_settings.stat().st_size > 1024*1024:
            return False
        data = json.loads(auth_settings.read_text(encoding='utf-8-sig'))
        return (data.get('security', {}).get('auth', {}).get('selectedType') == 'oauth-personal'
                and (root/'oauth_creds.json').is_file())
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def _prepare_isolation(directory, env, settings, json_mode=False, model=None, response_schema=None):
    # Keep managed settings and normal personal authentication in their native
    # locations; this project overlay only removes execution capabilities.
    project = directory/'.gemini'
    project.mkdir()
    overlay = {'hooksConfig': {'enabled': False}, 'skills': {'enabled': False},
                'tools': {'core': [], 'discoveryCommand': '', 'callCommand': ''},
                'experimental': {'enableAgents': False, 'autoMemory': False},
                'context': {'loadMemoryFromIncludeDirectories': False, 'includeDirectoryTree': False, 'includeDirectories': []},
                'ide': {'enabled': False},
                'model': {'maxSessionTurns': 1},
                'security': {'auth': {'selectedType': 'oauth-personal'}}}
    if json_mode:
        if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}', model):
            raise ValueError('JSON generation requires the selected model')
        overlay['modelConfigs'] = {'overrides': [{'match': {'model': model}, 'modelConfig': {
            'generateContentConfig': {'responseMimeType': 'application/json'}}}]}
        if response_schema is not None:
            overlay['modelConfigs']['overrides'][0]['modelConfig']['generateContentConfig']['responseJsonSchema'] = deepcopy(response_schema)
            (directory/'response-schema.json').write_text(json.dumps(response_schema), encoding='utf-8')
    (project/'settings.json').write_text(json.dumps(overlay), encoding='utf-8')
    policy = directory/'deny-native-tools.toml'
    policy.write_text('[[rule]]\ntoolName = "*"\ndecision = "deny"\npriority = 999\n', encoding='utf-8')
    # Import only the recognized settings loader and Storage, never CLI main or
    # Config initialization. Keep actual managed settings/policies in force.
    argv = [settings['node_path'], '--input-type=module', '-e', _INSPECT,
            settings['entrypoint'], str(directory), 'json' if json_mode else 'text', model or '']
    try:
        result = _run(settings, '', b'', directory, env, argv_override=argv)
        if _json(result) != {'safe': True}:
            raise ValueError('Unsafe effective settings')
    except (ValueError, RuntimeError):
        raise RuntimeError('Gemini CLI text-only isolation could not be verified') from None
    (directory/'request-compat.mjs').write_text(
        _REQUEST_COMPAT.replace('__ENTRYPOINT__', json.dumps(settings['entrypoint'])), encoding='utf-8')


def _kill_tree(process):
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
    if process.poll() is None:
        process.kill()


def _failure_category(stderr):
    """Classify transient diagnostics without returning any diagnostic text."""
    text = stderr.decode('utf-8', errors='replace').lower()
    if 'tools[0].tool_type' in text and 'required' in text:
        return 'invalid_tool_declaration'
    if any(marker in text for marker in ('unauthenticated', 'invalid credentials', 'authentication required', 'login required')):
        return 'authentication_required'
    if any(marker in text for marker in ('resource_exhausted', 'quota exceeded', 'rate limit exceeded')):
        return 'quota_exceeded'
    if 'model' in text and any(marker in text for marker in ('not found', 'unsupported model', 'not supported')):
        return 'unsupported_model'
    return 'execution_failed'


def _run(settings, model, payload, directory, env, *, argv_override=None):
    preload = Path(directory)/'request-compat.mjs'
    argv = [settings['node_path']]
    if preload.is_file():
        argv.extend(['--import', preload.resolve().as_uri()])
    argv.extend([settings['entrypoint'], '-m', model, '-p', _PROMPT,
            '--output-format', 'json', '--allowed-mcp-server-names', '__council_no_mcp_servers__',
            '--admin-policy', str(Path(directory)/'deny-native-tools.toml'),
            '--extensions', 'none', '--approval-mode', 'default'])
    if argv_override is not None:
        argv = argv_override
    try:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   cwd=directory, env=env, shell=False)
    except OSError:
        raise DiagnosticRuntimeError('CLI_START_FAILED') from None
    output, diagnostics, errors = bytearray(), bytearray(), []
    received, counter_lock = [0], threading.Lock()
    overflow = threading.Event()

    def read(stream, collect):
        try:
            while chunk := stream.read(65536):
                with counter_lock:
                    received[0] += len(chunk)
                    exceeded = received[0] > _LIMIT
                if exceeded:
                    overflow.set()
                    _kill_tree(process)
                    break
                if collect:
                    output.extend(chunk)
                else:
                    diagnostics.extend(chunk)
        except OSError:
            errors.append(True)
        finally:
            stream.close()

    def write():
        try:
            process.stdin.write(payload)
        except (OSError, BrokenPipeError):
            pass
        finally:
            process.stdin.close()

    readers = [threading.Thread(target=read, args=(process.stdout, True), daemon=True),
               threading.Thread(target=read, args=(process.stderr, False), daemon=True)]
    writer = threading.Thread(target=write, daemon=True)
    for thread in [*readers, writer]:
        thread.start()
    timed_out = False
    try:
        process.wait(timeout=settings['timeout_seconds'])
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(process)
        process.wait()
    finally:
        for thread in [*readers, writer]:
            thread.join(timeout=10)
    from council.cli_process import process_detail
    detail = process_detail('gemini-cli', process.returncode, bytes(diagnostics), bytes(output))
    if timed_out:
        raise DiagnosticRuntimeError('CLI_TIMEOUT', cli_process=detail) from None
    if overflow.is_set():
        raise DiagnosticRuntimeError('CLI_OUTPUT_LIMIT', cli_process=detail)
    if errors or any(thread.is_alive() for thread in [*readers, writer]):
        raise DiagnosticRuntimeError('CLI_IO_FAILED', cli_process=detail)
    if process.returncode:
        error = execution_error(_failure_category(diagnostics), cli_process=process_detail(
            'gemini-cli', process.returncode, bytes(diagnostics), bytes(output)))
        raise error
    return bytes(output)


def _json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON constant')))


def _parse_response_json(text, code):
    try:
        return _json(text)
    except (ValueError, UnicodeError) as error:
        from council.json_feedback import from_error
        raise DiagnosticValueError(code, response_json=from_error(text, error)) from None


def _message(envelope, cli_version):
    if not isinstance(envelope, dict) or not isinstance(envelope.get('response'), str) or envelope.get('error'):
        raise DiagnosticValueError('GEMINI_ENVELOPE_INVALID')
    metadata = {'transport': 'gemini_cli', 'cli_version': cli_version}
    usage = None
    tool_stats = envelope.get('stats', {}).get('tools', {})
    if isinstance(tool_stats, dict) and 'totalCalls' in tool_stats:
        if type(tool_stats['totalCalls']) is not int or tool_stats['totalCalls'] != 0:
            raise DiagnosticValueError('GEMINI_NATIVE_TOOLS_REJECTED')
    models = envelope.get('stats', {}).get('models', {})
    if isinstance(models, dict) and len(models) == 1:
        name, data = next(iter(models.items()))
        if isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,256}', name):
            metadata['cli_reported_model'] = name
        tokens = data.get('tokens', {}) if isinstance(data, dict) else {}
        values = {out: tokens.get(key) for out, key in [('input_tokens', 'prompt'), ('output_tokens', 'candidates'), ('total_tokens', 'total')]}
        metadata['reported_usage']={key:value for key,value in values.items()
            if type(value) is int and 0<=value<=10**12}
        if all(type(value) is int and 0 <= value <= 10**12 for value in values.values()):
            usage = values
    return AIMessage(content=envelope['response'], response_metadata=metadata, usage_metadata=usage)


def _tool_response_schema(tools):
    """Constrain inspection names without the service's nested-union failure."""
    from council.boundaries import READ_TOOLS
    if not tools or any(tool['name'] not in READ_TOOLS for tool in tools):
        return None
    properties = {}
    for tool in tools:
        for name, definition in tool['parameters'].get('properties', {}).items():
            definition = deepcopy(definition)
            definition.pop('default', None)
            if name in properties and properties[name] != definition:
                # A future incompatible argument union retains ordinary JSON
                # generation and local validation instead of a rejected schema.
                return None
            properties[name] = definition
    call = {'type': 'object', 'properties': {
        'name': {'type': 'string', 'enum': [tool['name'] for tool in tools]},
        'args': {'type': 'object', 'properties': properties},
        'id': {'type': 'string'},
    }, 'required': ['name', 'args', 'id']}
    return {'type': 'object', 'properties': {
        'content': {'type': 'string'},
        'tool_calls': {'type': 'array', 'items': call},
    }, 'required': ['content', 'tool_calls']}


class GeminiCLIChatModel:
    def __init__(self, model, settings, context=None):
        validate_cli_settings(settings)
        if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}', model):
            raise ValueError('Invalid model identifier')
        self.model, self.settings, self.context = model, deepcopy(settings), context
        self._tools, self._schema, self._include_raw = (), None, False
        self._input_schemas = {}

    def bind_tools(self, tools):
        clone = copy(self)
        clone.settings = deepcopy(self.settings)
        tools = tuple(tools)
        clone._tools = tuple(deepcopy(convert_to_openai_tool(tool)['function']) for tool in tools)
        clone._input_schemas = {definition['name']: tool.get_input_schema()
            for tool, definition in zip(tools, clone._tools) if callable(getattr(tool, 'get_input_schema', None))}
        names = [tool['name'] for tool in clone._tools]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate offered tools')
        clone._schema = None
        return clone

    def with_structured_output(self, schema, include_raw=False):
        clone = copy(self)
        clone.settings = deepcopy(self.settings)
        clone._schema, clone._include_raw, clone._tools = schema, include_raw, ()
        clone._input_schemas = {}
        return clone

    def invoke(self, messages):
        if isinstance(messages, str):
            messages = [{'role': 'user', 'content': messages}]
        request = {'messages': [deepcopy(message) if isinstance(message, dict) else message_to_dict(message) for message in messages]}
        if self._schema:
            request['response_schema'] = self._schema.model_json_schema()
        elif self._tools:
            request.update(tools=self._tools, response_format={'content': 'string', 'tool_calls': [{'name': 'offered tool name', 'args': 'object', 'id': 'unique identifier'}]})
            request['response_instructions'] = (
                'Return exactly one JSON object with exactly "content" (string) and "tool_calls" (array). '
                'Place all explanation inside "content"; never return surrounding prose or Markdown fences. '
                'Each tool call must contain exactly "name" (an offered tool name), "args" (a JSON object '
                'matching that tool), and "id" (a unique string identifier). '
                'When no further tools are needed, return {"content":"Inspection complete.","tool_calls":[]}. '
                'An empty tool_calls array ends tool inspection; it does not authorize task execution.'
            )
        else:
            request['response_format'] = 'plain text'
        try:
            # CLI @file preprocessing runs before tool policy. Preserve the
            # character as JSON data without presenting an @ trigger to it.
            payload = json.dumps(request, ensure_ascii=False, allow_nan=False).replace('@', '\\u0040').encode('utf-8')
        except (TypeError, ValueError):
            raise DiagnosticValueError('CLI_INPUT_INVALID') from None
        if len(payload) > _LIMIT:
            raise DiagnosticValueError('CLI_INPUT_LIMIT')
        if not _installed(self.settings):
            raise DiagnosticRuntimeError('CLI_UNAVAILABLE')
        cli_version = _installed_version(self.settings) or self.settings['cli_version']
        parent = Path(self.context.memory_root) if self.context else Path.home()/'.council'/'memory'/'engine'
        parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        for key in ('GEMINI_API_KEY', 'GOOGLE_API_KEY', 'GOOGLE_GENAI_USE_VERTEXAI'):
            env.pop(key, None)
        env['GEMINI_CLI_NO_RELAUNCH'] = 'true'
        with tempfile.TemporaryDirectory(prefix='gemini-text-', dir=parent) as directory:
            try:
                _prepare_isolation(Path(directory), env, self.settings, bool(self._tools or self._schema), self.model,
                                   _tool_response_schema(self._tools) if self._tools else None)
            except RuntimeError:
                raise DiagnosticRuntimeError('GEMINI_ISOLATION_FAILED') from None
            from council.call_policy import gemini_deadline
            # This transport-only copy never replaces the validated run snapshot.
            effective = {**self.settings, 'timeout_seconds': gemini_deadline(self.settings, structured=self._schema is not None)}
            try:
                result = _run(effective, self.model, payload, directory, env)
            except DiagnosticRuntimeError as error:
                event('cli_attempt_failed', stage='model', diagnostic=error)
                raise
        code = 'GEMINI_ENVELOPE_JSON_INVALID'
        raw = None
        try:
            envelope = _parse_response_json(result, code)
            code = 'GEMINI_ENVELOPE_INVALID'
            raw = _message(envelope, cli_version)
            if self._schema:
                code = 'GEMINI_RESPONSE_JSON_INVALID'
                data = _parse_response_json(raw.content, code)
                code = 'GEMINI_SCHEMA_INVALID'
                from pydantic import ValidationError
                try:
                    parsed = self._schema.model_validate(data, strict=True)
                except ValidationError as error:
                    from council.schema_feedback import from_error
                    raise DiagnosticValueError(code, response_schema=from_error(error)) from None
                return {'raw': raw, 'parsed': parsed, 'parsing_error': None} if self._include_raw else parsed
            if self._tools:
                code = 'GEMINI_RESPONSE_JSON_INVALID'
                data = _parse_response_json(raw.content, code)
                if not isinstance(data, dict) or set(data) != {'content', 'tool_calls'} or not isinstance(data['content'], str) or not isinstance(data['tool_calls'], list) or len(data['tool_calls']) > 16:
                    raise DiagnosticValueError('GEMINI_TOOL_ENVELOPE_INVALID')
                ids, offered = set(), {tool['name'] for tool in self._tools}
                for call in data['tool_calls']:
                    if not isinstance(call, dict) or set(call) != {'name', 'args', 'id'}:
                        raise DiagnosticValueError('GEMINI_TOOL_CALL_INVALID')
                    if not isinstance(call['name'], str) or call['name'] not in offered:
                        raise DiagnosticValueError('GEMINI_TOOL_NAME_UNOFFERED')
                    if not isinstance(call['args'], dict):
                        raise DiagnosticValueError('GEMINI_TOOL_ARGUMENTS_INVALID')
                    if call['name'] in self._input_schemas:
                        code = 'GEMINI_TOOL_ARGUMENTS_INVALID'
                        self._input_schemas[call['name']].model_validate(call['args'])
                    if not isinstance(call['id'], str) or not _ID.fullmatch(call['id']) or call['id'] in ids:
                        raise DiagnosticValueError('GEMINI_TOOL_CALL_INVALID')
                    ids.add(call['id'])
                code = 'GEMINI_TOOL_CALL_INVALID'
                raw = raw.model_copy(update={'content': data['content'], 'tool_calls': data['tool_calls']})
            return raw
        except DiagnosticValueError as error:
            if raw is not None:
                error.response_metadata=raw.response_metadata
                error.usage_metadata=raw.usage_metadata
            raise
        except (ValueError, TypeError, KeyError, AttributeError):
            error=DiagnosticValueError(code)
            if raw is not None:
                error.response_metadata=raw.response_metadata
                error.usage_metadata=raw.usage_metadata
            raise error from None
