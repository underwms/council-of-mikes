"""One approved coding task per native Codex exec process, using saved login."""
from copy import deepcopy
import json
import os
from pathlib import Path, PureWindowsPath
import re
import tempfile

from langchain_core.messages import AIMessage
from council.cli_process import LIMIT, run_process, failure_category, process_detail
from council.codex_input import encode_request
from council.diagnostics import (DiagnosticValueError, DiagnosticRuntimeError, execution_error, event,
                                 NATIVE_EVENT_TYPES, NATIVE_ITEM_TYPES)

_VERSION_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,63}\Z')
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}\Z')
_ITEM_TYPES = {'agent_message', 'reasoning', 'command_execution', 'file_change',
               'mcp_tool_call', 'web_search', 'todo_list', 'collab_tool_call',
               'dynamic_tool_call', 'image_view'}


class _EventRejected(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__('Native event rejected')


def validate_cli_settings(settings):
    if (not isinstance(settings, dict) or set(settings) != {'executable', 'cli_version', 'timeout_seconds'}
            or not isinstance(settings['cli_version'], str)
            or not _VERSION_PATTERN.fullmatch(settings['cli_version'])
            or type(settings['timeout_seconds']) is not int
            or settings['timeout_seconds'] != 600):
        raise ValueError('Unsupported Codex CLI settings')
    executable = settings['executable']
    if not isinstance(executable, str) or '\x00' in executable or not Path(executable).is_absolute():
        raise ValueError('Codex executable must be an absolute path')


def resolve_cli_settings():
    executable = os.environ.get('COUNCIL_CODEX_CLI_PATH') or str(Path.home()/'AppData'/'Local'/'Programs'/'OpenAI'/'Codex'/'bin'/'codex.exe')
    settings = {'executable': executable, 'cli_version': _observed_version(executable) or 'unknown',
                'timeout_seconds': 600}
    validate_cli_settings(settings)
    return settings


def _environment():
    env = dict(os.environ)
    for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_ACCESS_TOKEN', 'CODEX_ACCESS_TOKEN',
                'CHATGPT_ACCESS_TOKEN', 'CODEX_CHATGPT_ACCESS_TOKEN', 'OPENAI_AUTH_TOKEN'):
        env.pop(key, None)
    return env


def _observed_version(executable):
    try:
        if not Path(executable).is_file():
            return None
        code, out, _ = run_process([executable, '--version'], env=_environment(), timeout=15)
        match = re.fullmatch(r'codex-cli ([A-Za-z0-9][A-Za-z0-9._+-]{0,63})', out.decode('utf-8').strip())
        return match.group(1) if code == 0 and match else None
    except (ValueError, OSError, RuntimeError, UnicodeError):
        return None


def cli_ready(settings):
    """Check executable identity and native login without opening token files."""
    try:
        validate_cli_settings(settings)
        if not _observed_version(settings['executable']):
            return False
        code, out, err = run_process([settings['executable'], 'login', 'status'], env=_environment(), timeout=15)
        return code == 0 and (out + err).decode('utf-8').strip() == 'Logged in using ChatGPT'
    except (ValueError, OSError, RuntimeError, UnicodeError):
        return False


def _json(text):
    """Strict JSON decoder also used for substantive reviewer decisions."""
    return _event_json(text)[0]


def _event_json(text, cli_version=None):
    class ObjectPairs(list):
        pass

    def constant(_):
        raise ValueError('Nonfinite JSON value')

    compatibility_count = 0

    def materialize(value, path=()):
        nonlocal compatibility_count
        if isinstance(value, ObjectPairs):
            identifiers = [item for key, item in value if key == 'id']
            # Native 0.164.0 flattens the provider search ID into the item,
            # after its own lifecycle ID. Preserve the latter; never use
            # last-key-wins decoding for arbitrary events or nested payloads.
            search_id_pair = (cli_version == '0.164.0' and path == ('item',)
                and event_kind in {'item.started', 'item.updated', 'item.completed'}
                and dict(value).get('type') == 'web_search' and len(identifiers) == 2
                and all(isinstance(item, str) and _ID.fullmatch(item) for item in identifiers)
                and re.fullmatch(r'item_[0-9]+', identifiers[0]) is not None
                and identifiers[0] != identifiers[1])
            result = {}
            for key, item in value:
                if key in result:
                    if search_id_pair and key == 'id':
                        compatibility_count += 1
                        continue
                    raise ValueError('Duplicate JSON field')
                result[key] = materialize(item, (*path, key))
            return result
        if isinstance(value, list):
            return [materialize(item, (*path, index)) for index, item in enumerate(value)]
        return value

    try:
        raw = json.loads(text, object_pairs_hook=ObjectPairs, parse_constant=constant)
        event_kind = dict(raw).get('type') if isinstance(raw, ObjectPairs) else None
        return materialize(raw), compatibility_count
    except (ValueError, TypeError):
        raise DiagnosticValueError('CODEX_JSON_INVALID') from None


def _file_path(value, cwd, workspace):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise _EventRejected('INVALID_FILE_PATH')
    path = Path(value)
    if os.name != 'nt' and PureWindowsPath(value).is_absolute():
        raise _EventRejected('INVALID_FILE_PATH')
    resolved = path.resolve() if path.is_absolute() else (cwd/path).resolve()
    if not resolved.is_relative_to(workspace):
        raise _EventRejected('FILE_PATH_OUTSIDE_WORKSPACE')
    if resolved == workspace:
        raise _EventRejected('INVALID_FILE_PATH')
    return resolved.relative_to(workspace).as_posix()


def _parse(output, cwd, workspace, *, review_only=False, cli_version=None):
    changes = []
    event_index, event_type, item_type = 0, 'none', 'none'
    try:
        thread_id, started, completed, final = None, False, False, None
        item_ids = set()
        open_items = {}
        usage = None
        reported_usage = {}
        warning_count = 0
        failed_item_count = 0
        failed_tool_event = None
        declined_command_count = 0
        search_id_compatibility_count = 0
        # JSONL records end at LF bytes; Unicode line separators are valid inside JSON strings.
        lines = output.decode('utf-8').split('\n')
        if lines and lines[-1] == '':
            lines.pop()
        if not lines:
            raise _EventRejected('EMPTY_EVENT')
        blank = next((index for index, line in enumerate(lines, 1) if not line.strip()), None)
        if blank is not None:
            event_index, event_type = blank, 'invalid'
            raise _EventRejected('EMPTY_EVENT')
        for event_index, line in enumerate(lines, 1):
            event_type, item_type = 'invalid', 'none'
            event, compatibility_count = _event_json(line, cli_version)
            search_id_compatibility_count += compatibility_count
            if isinstance(event, dict) and isinstance(event.get('type'), str):
                event_type = event['type'] if event['type'] in NATIVE_EVENT_TYPES else 'unknown'
                item = event.get('item')
                if event_type in {'item.started', 'item.updated', 'item.completed'}:
                    item_type = (item['type'] if item['type'] in NATIVE_ITEM_TYPES else 'unknown') if isinstance(item, dict) and isinstance(item.get('type'), str) else 'invalid'
            if not isinstance(event, dict) or not isinstance(event.get('type'), str) or completed:
                raise _EventRejected('INVALID_EVENT')
            kind = event['type']
            if kind == 'thread.started':
                if thread_id is not None or started or not isinstance(event.get('thread_id'), str) or not _ID.fullmatch(event['thread_id']):
                    raise _EventRejected('INVALID_THREAD')
                thread_id = event['thread_id']
            elif kind == 'turn.started':
                if not thread_id or started:
                    raise _EventRejected('INVALID_TURN')
                started = True
            elif kind in ('error', 'turn.failed'):
                raise DiagnosticValueError('CODEX_TURN_FAILED')
            elif kind in ('item.started', 'item.updated', 'item.completed'):
                item = event.get('item')
                # Native exec_events.rs defines completed ErrorItem as
                # nonfatal, unlike top-level error/turn.failed. Only retain a
                # count; never carry its diagnostic message into evidence.
                if isinstance(item, dict) and item.get('type') == 'error':
                    if (not thread_id or kind != 'item.completed' or set(item) != {'id', 'type', 'message'}
                            or not isinstance(item['id'], str) or not _ID.fullmatch(item['id'])
                            or item['id'] in item_ids or item['id'] in open_items
                            or not isinstance(item['message'], str) or not 1 <= len(item['message']) <= 4096):
                        raise _EventRejected('INVALID_DIAGNOSTIC')
                    item_ids.add(item['id'])
                    warning_count += 1
                    continue
                if not started or not isinstance(item, dict) or not isinstance(item.get('id'), str) or not _ID.fullmatch(item['id']) or not isinstance(item.get('type'), str):
                    raise _EventRejected('INVALID_ITEM')
                if item['type'] not in _ITEM_TYPES:
                    raise _EventRejected('UNSUPPORTED_ITEM')
                if review_only and item['type'] not in {'agent_message', 'reasoning'}:
                    raise DiagnosticValueError('CODEX_REVIEW_TOOL_REJECTED')
                if item['id'] in item_ids or (item['id'] in open_items and open_items[item['id']] != item['type']):
                    raise _EventRejected('INVALID_ITEM_LIFECYCLE')
                if kind == 'item.started' and item['id'] in open_items:
                    raise _EventRejected('DUPLICATE_ITEM_START')
                if kind != 'item.completed':
                    open_items[item['id']] = item['type']
                if item['type'] == 'file_change':
                    if not isinstance(item.get('changes'), list):
                        raise _EventRejected('INVALID_FILE_CHANGES')
                    for change in item['changes']:
                        if not isinstance(change, dict) or change.get('kind') not in ('add', 'delete', 'update'):
                            raise _EventRejected('INVALID_FILE_CHANGE')
                        value = _file_path(change.get('path'), cwd, workspace)
                        if value not in changes:
                            changes.append(value)
                status = item.get('status')
                if status == 'declined':
                    exit_code = item.get('exit_code')
                    if (kind != 'item.completed' or item['type'] != 'command_execution'
                            or 'exit_code' not in item or (exit_code is not None and
                            (type(exit_code) is not int or exit_code == 0 or not -(2**31) <= exit_code < 2**31))):
                        raise _EventRejected('INVALID_DECLINED_COMMAND')
                    item_ids.add(item['id'])
                    open_items.pop(item['id'], None)
                    declined_command_count += 1
                    continue
                if 'status' in item and status not in ('in_progress', 'completed', 'failed'):
                    raise _EventRejected('INVALID_ITEM_STATUS')
                recovered_failure = status == 'failed'
                if recovered_failure:
                    if kind != 'item.completed' or item['type'] not in ('command_execution', 'file_change', 'mcp_tool_call'):
                        raise _EventRejected('UNSUPPORTED_FAILED_ITEM')
                    if item['type'] == 'mcp_tool_call' and failed_tool_event is None:
                        failed_tool_event = (event_index, event_type, item_type)
                    if item['type'] == 'command_execution' and (type(item.get('exit_code')) is not int
                            or item['exit_code'] == 0 or not -(2**31) <= item['exit_code'] < 2**31):
                        raise _EventRejected('INVALID_FAILED_COMMAND')
                    failed_item_count += 1
                if kind == 'item.completed':
                    item_ids.add(item['id'])
                    open_items.pop(item['id'], None)
                    if item['type'] == 'agent_message':
                        if not isinstance(item.get('text'), str) or not item['text'].strip():
                            raise _EventRejected('INVALID_FINAL_MESSAGE')
                        final = item['text']
                    elif item['type'] == 'file_change':
                        if item.get('status') not in ('completed', 'failed'):
                            raise _EventRejected('INVALID_FILE_CHANGES')
                    elif item['type'] == 'command_execution':
                        if status not in ('completed', 'failed') or type(item.get('exit_code')) is not int:
                            raise _EventRejected('INVALID_COMPLETED_COMMAND')
            elif kind == 'turn.completed':
                if not started or final is None or open_items:
                    raise DiagnosticValueError('CODEX_TURN_INCOMPLETE')
                counts = event.get('usage')
                if not isinstance(counts, dict):
                    raise _EventRejected('INVALID_USAGE')
                input_tokens, output_tokens = counts.get('input_tokens'), counts.get('output_tokens')
                if any(type(value) is not int or not 0 <= value <= 10**12 for value in (input_tokens, output_tokens)):
                    raise _EventRejected('INVALID_USAGE')
                usage = {'input_tokens': input_tokens, 'output_tokens': output_tokens, 'total_tokens': input_tokens+output_tokens}
                reported_usage = {key:count for key in ('input_tokens','output_tokens','total_tokens','cached_input_tokens')
                    if type(count := counts.get(key)) is int and 0<=count<=10**12}
                completed = True
            else:
                raise _EventRejected('UNSUPPORTED_EVENT')
        if not completed:
            event_index, event_type, item_type = len(lines) + 1, 'end_of_stream', 'none'
            raise DiagnosticValueError('CODEX_TURN_INCOMPLETE')
        if failed_tool_event is not None:
            event_index, event_type, item_type = failed_tool_event
            raise DiagnosticValueError('CODEX_TOOL_FAILED')
        metadata = {'transport': 'codex-cli', 'cli_thread_id': thread_id, 'reported_usage':reported_usage}
        if cli_version is not None:
            metadata['cli_version'] = cli_version
        if warning_count:
            metadata['cli_warning_count'] = warning_count
        if failed_item_count:
            metadata['cli_failed_item_count'] = failed_item_count
        if declined_command_count:
            metadata['cli_declined_command_count'] = declined_command_count
        if search_id_compatibility_count:
            metadata['cli_web_search_id_compatibility_count'] = search_id_compatibility_count
        return AIMessage(content=final, response_metadata=metadata,
                         usage_metadata=usage, additional_kwargs={'native_file_changes': changes})
    except (ValueError, TypeError, KeyError, UnicodeError) as cause:
        error = cause if type(cause) is DiagnosticValueError else DiagnosticValueError('CODEX_EVENT_INVALID')
        reason = (cause.reason if type(cause) is _EventRejected else
                  'INVALID_ENCODING' if isinstance(cause, UnicodeError) else
                  {'CODEX_JSON_INVALID': 'INVALID_JSON', 'CODEX_TURN_FAILED': 'TURN_FAILED',
                   'CODEX_TURN_INCOMPLETE': 'TURN_INCOMPLETE',
                   'CODEX_TOOL_FAILED': 'TOOL_FAILED',
                   'CODEX_REVIEW_TOOL_REJECTED': 'REVIEW_TOOL_REJECTED'}.get(error.code, 'CONTRACT_INVALID'))
        error.native_event = {'reason': reason, 'event_index': min(event_index, 4194305),
                              'event_type': event_type, 'item_type': item_type}
        error.native_file_changes = changes
        error.response_metadata = {'reported_usage':reported_usage}
        raise error from None


class CodexCLIWorker:
    def review_finished(self, messages):
        from council.codex_chat import CodexCLIChatModel
        from council.delivery_contracts import FinalReview
        return CodexCLIChatModel(self.model,self.settings,context=self.context).with_structured_output(
            FinalReview,include_raw=True).invoke(messages)

    def __init__(self, model, settings, context):
        validate_cli_settings(settings)
        if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}', model):
            raise ValueError('Invalid Codex model identifier')
        self.model, self.settings, self.context = model, deepcopy(settings), context

    def review_plan(self, request):
        from council.state import PlanReviewDecision, PlanReviewDecisionV2
        decision_schema = PlanReviewDecisionV2 if request.get('review_protocol_version') == 2 else PlanReviewDecision
        return self.invoke_read_only(request, response_schema=decision_schema.model_json_schema())

    def invoke_read_only(self, request, *, response_schema=None):
        """One isolated text turn; graph tools are data, never native execution."""
        payload = encode_request(request, byte_limit=LIMIT)
        if not cli_ready(self.settings):
            raise DiagnosticRuntimeError('CLI_UNAVAILABLE')
        cli_version = _observed_version(self.settings['executable'])
        # An empty directory prevents project configuration and instructions from
        # introducing tools. Keep the existing login; never copy credential files.
        root = Path(getattr(self.context, 'council_root', self.context.workspace_root.parent))/'work'/'review-only'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='turn-', dir=root) as temporary:
            cwd = Path(temporary)
            from council.codex_review_isolation import prepare
            env = _environment()
            flags = prepare(self.settings['executable'], self.model, cwd, env, run_process)
            argv = [self.settings['executable'], '--no-daemon', 'exec', '--json', '--ephemeral',
                    '--ignore-user-config', '--sandbox', 'read-only', '--skip-git-repo-check']
            if response_schema is not None:
                schema = cwd/'decision.schema.json'
                schema.write_text(json.dumps(response_schema), encoding='utf-8')
                argv.extend(['--output-schema', str(schema)])
            argv.extend(['-C', str(cwd), '--model', self.model, *flags, '-'])
            code, out, err = run_process(argv, payload, cwd=cwd, env=env, timeout=self.settings['timeout_seconds'])
            if code:
                error = execution_error(failure_category(err), cli_process=process_detail('codex-cli', code, err, out))
                event('cli_attempt_failed', stage='model', diagnostic=error)
                try:
                    observed = _parse(out,cwd,Path(self.context.workspace_root).resolve(),review_only=True,cli_version=cli_version)
                    error.response_metadata = observed.response_metadata
                except ValueError as parsed:
                    error.response_metadata = getattr(parsed,'response_metadata',{})
                raise error
            return _parse(out, cwd, Path(self.context.workspace_root).resolve(), review_only=True,
                          cli_version=cli_version)

    def run_task(self, task, guidance, diagnosis='', prior_result=None):
        workspace = Path(self.context.workspace_root).resolve()
        selected = task.working_directory
        if not isinstance(selected, str) or Path(selected).is_absolute() or '..' in Path(selected).parts:
            raise PermissionError('Codex task directory escapes workspace')
        from council.tools.discovery import validate_discovery_path
        cwd = validate_discovery_path(self.context, selected)
        if not cwd.is_relative_to(workspace) or not cwd.is_dir():
            raise PermissionError('Codex task directory escapes workspace')
        request = {'instruction': 'Implement only the approved task using the supplied Council guidance. Return a concise final report. Preserve existing user changes; do not commit, push, publish, or deploy. '
                   'Respect verification_phase and red_verification. Red tasks create compilable/loadable tests with the declared named assertion failures, not compiler/import failures. '
                   'Do not implement later tasks or weaken assertions to obtain exit zero. Accepted red tests are frozen; implement the named green task against those unchanged tests. '
                   'Every declared expected test must exist and fail through meaningful assertions. Do not omit tests or use unconditional throws; identify an unsupported harness as a blocker. '
                   'Do not override native execution policy or use PowerShell -ExecutionPolicy/-ep bypasses. Record blocked checks without weakening permissions. '
                   'passed records the actual test outcome; expectation_met identifies whether that phase met its contract.',
                   'task': task.model_dump(mode='json') if hasattr(task, 'model_dump') else vars(task),
                   'guidance': guidance, 'diagnosis': diagnosis, 'prior_result': prior_result}
        if hasattr(prior_result, 'model_dump'):
            request['prior_result'] = prior_result.model_dump(mode='json')
        from council.red_feedback import correction, sanitize_result
        request['prior_result'] = sanitize_result(request['prior_result'])
        request['red_verification_correction'] = correction(task, prior_result)
        payload = encode_request(request, byte_limit=LIMIT)
        if not cli_ready(self.settings):
            raise DiagnosticRuntimeError('CLI_UNAVAILABLE')
        cli_version = _observed_version(self.settings['executable'])
        argv = [self.settings['executable'], 'exec', '--json', '--approve-for-me',
                '--ephemeral', '-C', str(cwd), '--model', self.model, '-c', 'forced_login_method="chatgpt"', '-']
        # Approved shared documentation can live outside a repository. This only
        # relaxes Git discovery; automatic approval review/sandboxing stay active.
        if not any((parent/'.git').exists() for parent in (cwd, *cwd.parents)
                   if parent.is_relative_to(workspace)):
            argv.insert(-1, '--skip-git-repo-check')
        code, out, err = run_process(argv, payload, cwd=cwd, env=_environment(), timeout=self.settings['timeout_seconds'])
        if code:
            error = execution_error(failure_category(err), cli_process=process_detail('codex-cli', code, err, out))
            event('cli_attempt_failed', stage='model', diagnostic=error)
            try:
                observed = _parse(out, cwd, workspace)
                error.native_file_changes = observed.additional_kwargs['native_file_changes']
                error.response_metadata = observed.response_metadata
            except ValueError as parsed:
                error.native_file_changes = parsed.native_file_changes
                error.response_metadata = getattr(parsed,'response_metadata',{})
            raise error
        return _parse(out, cwd, workspace, cli_version=cli_version)
