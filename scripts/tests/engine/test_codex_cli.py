"""Native worker tests using inert real child processes, never a model request."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from council.codex_cli import CodexCLIWorker, cli_ready, resolve_cli_settings, validate_cli_settings


def completed(extra=()):
    return [{'type': 'thread.started', 'thread_id': 'thread-test'}, {'type': 'turn.started'},
            *extra, {'type': 'item.completed', 'item': {'id': 'message-1', 'type': 'agent_message', 'text': 'Implemented'}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 3, 'cached_input_tokens': 1, 'output_tokens': 2}}]


@pytest.fixture
def native(tmp_path, monkeypatch):
    calls = []
    state = {'events': completed(), 'stderr': '', 'exit_code': 0, 'sleep': False,
             'version': 'codex-cli 0.163.0', 'login': 'Logged in using ChatGPT'}
    original = subprocess.Popen

    def launch(argv, **kwargs):
        if Path(argv[0]).name == 'taskkill.exe':
            return original(argv, **kwargs)
        calls.append((list(argv), kwargs.copy()))
        if argv[-1] == '--version':
            code = 'print('+repr(state['version'])+')'
        elif argv[-2:] == ['login', 'status']:
            code = 'import sys;sys.stderr.write('+repr(state['login'])+')'
        elif 'debug' in argv and 'models' in argv:
            catalog = state.get('catalog', {'models': [dict(slug=name, tool_mode='code_mode_only',
                multi_agent_version='v2', experimental_supported_tools=['clock'], apply_patch_tool_type='freeform',
                node_repl_disabled=False, supports_search_tool=True, context_window=123456)
                for name in ('gpt-exact', 'gpt-6.1-sol')]})
            code = 'import sys;print('+repr(json.dumps(catalog))+');sys.exit('+str(state.get('catalog_exit', 0))+')'
        elif 'debug' in argv and 'prompt-input' in argv:
            output = state.get('inventory_raw', json.dumps(state.get('inventory', [{'type':'message','role':'user','content':[]}])) )
            code = 'import sys;print('+repr(output)+');sys.exit('+str(state.get('inventory_exit', 0))+')'
        else:
            for arg in argv:
                if arg.startswith('model_catalog_json='):
                    state['observed_catalog'] = json.loads(Path(json.loads(arg.split('=', 1)[1])).read_text())
            rendered = repr(state.get('raw_output', '\n'.join(json.dumps(e) for e in state['events'])))
            if 'raw_output' in state and len(state['raw_output']) > 65536:
                rendered = repr(state['raw_output'][0]) + '*' + str(len(state['raw_output']))
            code = ('import sys,json,time;payload=sys.stdin.buffer.read();'
                    + ('time.sleep(10);' if state['sleep'] else '')
                    + 'sys.stdout.write('+rendered+');'
                    + 'sys.stderr.write('+repr(state['stderr'])+');'
                    + 'sys.exit('+str(state['exit_code'])+')')
        return original([sys._base_executable, '-I', '-c', code], **kwargs)

    monkeypatch.setattr('council.cli_process.subprocess.Popen', launch)
    settings = {'executable': str(Path(sys.executable).resolve()), 'cli_version': '0.163.0', 'timeout_seconds': 600}
    workspace = tmp_path/'workspace'
    workspace.mkdir()
    context = SimpleNamespace(workspace_root=workspace, workspace_path=lambda value: (workspace/value).resolve())
    task = SimpleNamespace(description='PRIVATE_TASK', working_directory='.', target_files=['changed.txt'], acceptance_criteria=['works'])
    return settings, context, task, state, calls


def test_settings_and_offline_native_login(native, monkeypatch):
    settings, _, _, _, calls = native
    validate_cli_settings(settings)
    monkeypatch.setenv('COUNCIL_CODEX_CLI_PATH', settings['executable'])
    assert resolve_cli_settings() == settings
    assert cli_ready(settings)
    assert len(calls) == 3
    for change in ({'executable': 'relative.exe'}, {'timeout_seconds': True}, {'timeout_seconds': 10}, {'cli_version': 'bad version'}, {'api_key': 'secret'}):
        with pytest.raises(ValueError):
            validate_cli_settings({**settings, **change})


@pytest.mark.parametrize('mode', ['read_only', 'coding'])
def test_complete_oversized_input_uses_references_without_changing_native_permissions(native, monkeypatch, mode):
    from council import codex_cli
    from test_codex_input import restore_payload
    settings, context, task, state, calls = native
    original = codex_cli.run_process
    captured = []
    def observe(argv, *args, **kwargs):
        if 'exec' in argv:
            captured.append(args[0])
        return original(argv, *args, **kwargs)
    monkeypatch.setattr(codex_cli, 'run_process', observe)
    worker = CodexCLIWorker('gpt-exact', settings, context)
    evidence = 'complete evidence ' * 40000
    if mode == 'read_only':
        request = {'instruction': 'Review all evidence.', 'one': evidence, 'two': evidence}
        result = worker.invoke_read_only(request)
    else:
        task.acceptance_criteria = [evidence, evidence]
        result = worker.run_task(task, 'guidance')
    assert result.content == 'Implemented'
    assert len(captured) == 1 and len(captured[0].decode()) <= 1048576
    reconstructed = restore_payload(captured[0])
    if mode == 'read_only':
        assert reconstructed == request
    else:
        assert reconstructed['task']['acceptance_criteria'] == [evidence, evidence]
    argv = next(argv for argv, _ in calls if 'exec' in argv)
    assert '--ephemeral' in argv
    if mode == 'read_only':
        assert argv[argv.index('--sandbox') + 1] == 'read-only'
        assert 'features.shell_tool=false' in argv and '--approve-for-me' not in argv
    else:
        assert '--approve-for-me' in argv


@pytest.mark.parametrize('coding', [False, True])
def test_native_prompt_character_limit_is_checked_before_dispatch(native, coding):
    settings, context, task, _, calls = native
    worker = CodexCLIWorker('gpt-exact', settings, context)
    with pytest.raises(ValueError) as caught:
        if coding:
            worker.run_task(task, 'x' * 1048577)
        else:
            worker.invoke_read_only({'instruction': 'x' * 1048577})
    assert caught.value.code == 'CLI_INPUT_LIMIT'
    assert not calls


def test_newer_codex_cli_version_uses_same_event_contract(native, monkeypatch):
    settings, context, task, state, _ = native
    state['version'] = 'codex-cli 0.164.0'
    monkeypatch.setenv('COUNCIL_CODEX_CLI_PATH', settings['executable'])
    assert resolve_cli_settings()['cli_version'] == '0.164.0'
    assert cli_ready(settings)
    response = CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    assert response.content == 'Implemented'
    assert response.response_metadata['cli_version'] == '0.164.0'


@pytest.mark.parametrize('repository', [None, 'directory', 'worktree'])
def test_worker_supports_approved_non_git_docs_without_changing_native_approvals(native, repository):
    settings, context, task, _, calls = native
    if repository == 'directory':
        (context.workspace_root / '.git').mkdir()
    elif repository == 'worktree':
        (context.workspace_root / '.git').write_text('gitdir: synthetic-metadata', encoding='utf-8')
    directory = context.workspace_root / 'docs' / 'contracts'
    directory.mkdir(parents=True)
    task.working_directory = 'docs/contracts'
    CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'approved docs')
    argv, kwargs = calls[-1]
    assert ('--skip-git-repo-check' in argv) is (repository is None)
    assert '--approve-for-me' in argv and '--dangerously-bypass-approvals-and-sandbox' not in argv
    assert '--sandbox' not in argv  # --approve-for-me selects workspace-write without conflicting flags.
    assert kwargs['cwd'] == directory.resolve()


def test_worker_argv_completion_usage_and_native_file_events(native, monkeypatch):
    settings, context, task, state, calls = native
    state['events'] = completed([{'type': 'item.completed', 'item': {'id': 'change-1', 'type': 'file_change', 'status': 'completed', 'changes': [{'path': str(context.workspace_root/'changed.txt'), 'kind': 'add'}]}}])
    monkeypatch.setenv('OPENAI_API_KEY', 'PRIVATE_KEY')
    monkeypatch.setenv('CODEX_HOME', 'retain-home')
    result = CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'PRIVATE_GUIDANCE')
    assert result.content == 'Implemented'
    assert result.response_metadata == {'transport': 'codex-cli', 'cli_version': '0.163.0', 'cli_thread_id': 'thread-test',
        'reported_usage':{'input_tokens':3,'output_tokens':2,'cached_input_tokens':1}}
    assert result.usage_metadata == {'input_tokens': 3, 'output_tokens': 2, 'total_tokens': 5}
    assert result.additional_kwargs['native_file_changes'] == ['changed.txt']
    argv, kwargs = calls[-1]
    assert argv[-1] == '-'
    assert '--json' in argv and '--ephemeral' in argv and '--approve-for-me' in argv
    # Native 0.163.0 selects workspace-write through automatic review; its
    # explicit --sandbox option conflicts with --approve-for-me.
    assert '--sandbox' not in argv
    assert kwargs['shell'] is False
    assert 'PRIVATE_TASK' not in str(argv) and 'PRIVATE_GUIDANCE' not in str(argv)
    assert 'OPENAI_API_KEY' not in kwargs['env']
    assert kwargs['env']['CODEX_HOME'] == 'retain-home'


def test_failed_native_attempt_preserves_available_usage(native):
    settings,context,task,state,_ = native
    state['exit_code']=1
    with pytest.raises(RuntimeError) as caught:
        CodexCLIWorker('gpt-exact',settings,context).run_task(task,'guidance')
    assert caught.value.response_metadata['reported_usage']['input_tokens']==3


def test_finished_review_parse_failure_preserves_native_usage(native):
    settings,context,_,_,_ = native
    with pytest.raises(ValueError) as caught:
        CodexCLIWorker('gpt-exact',settings,context).review_finished([{'role':'user','content':'Review'}])
    assert caught.value.response_metadata['reported_usage']['input_tokens']==3


def test_reviewer_is_read_only_and_uses_no_coding_permissions(native):
    settings, context, _, state, calls = native
    state['events'] = completed()
    state['events'][-2]['item']['text'] = '{"decision":"accept","findings":[]}'
    result = CodexCLIWorker('gpt-exact', settings, context).review_plan({'requirement': 'PRIVATE_REVIEW'})
    assert 'accept' in result.content
    argv, kwargs = calls[-1]
    assert '--approve-for-me' not in argv
    assert argv[argv.index('--sandbox')+1] == 'read-only'
    assert 'features.shell_tool=false' in argv
    assert '--ignore-user-config' in argv
    assert 'features.plugins=false' in argv
    assert 'project_doc_max_bytes=0' in argv
    assert '--output-schema' in argv
    assert 'PRIVATE_REVIEW' not in str(argv)
    assert kwargs['shell'] is False


def test_reviewer_rejects_native_tool_events(native):
    settings, context, _, state, _ = native
    state['events'] = completed([{'type': 'item.completed', 'item': {'id': 'tool-1',
        'type': 'command_execution', 'status': 'completed', 'exit_code': 0}}])
    with pytest.raises(ValueError) as error:
        CodexCLIWorker('gpt-exact', settings, context).review_plan({})
    assert error.value.code == 'CODEX_REVIEW_TOOL_REJECTED'


def test_reviewer_protocol_two_uses_matching_native_output_schema(native, monkeypatch):
    import council.codex_cli as transport
    settings, context, _, state, calls = native
    original = transport.run_process
    schemas = []
    def run(argv, *args, **kwargs):
        if '--output-schema' in argv:
            schemas.append(json.loads(Path(argv[argv.index('--output-schema')+1]).read_text()))
        return original(argv, *args, **kwargs)
    monkeypatch.setattr(transport, 'run_process', run)
    CodexCLIWorker('gpt-exact', settings, context).review_plan({'review_protocol_version': 2})
    assert 'resolved_finding_ids' in schemas[0]['required']
    assert schemas[0]['$defs']['ReviewFinding']['additionalProperties'] is False


@pytest.mark.parametrize('scenario, expected', [('input', 'CLI_INPUT_INVALID'), ('limit', 'CLI_INPUT_LIMIT'),
    ('unavailable', 'CLI_UNAVAILABLE'), ('exit', 'CLI_EXECUTION_FAILED')])
def test_reviewer_failure_boundaries_are_sanitized(native, monkeypatch, scenario, expected):
    settings, context, _, state, _ = native
    request = {'requirement': 'PRIVATE_REVIEW'}
    if scenario == 'input':
        request['invalid'] = object()
    elif scenario == 'limit':
        monkeypatch.setattr('council.codex_cli.LIMIT', 1)
    elif scenario == 'unavailable':
        state['login'] = 'not logged in'
    else:
        state['exit_code'] = 9
        state['stderr'] = 'PRIVATE_ERROR'
    with pytest.raises((ValueError, RuntimeError)) as caught:
        CodexCLIWorker('gpt-exact', settings, context).review_plan(request)
    assert caught.value.code == expected
    assert 'PRIVATE' not in str(caught.value)


@pytest.mark.parametrize('events', [
    [{'type': 'turn.completed', 'usage': {}}],
    completed()+[{'type': 'turn.completed', 'usage': {}}],
    completed([{'type': 'turn.failed', 'error': {'message': 'PRIVATE_ERROR'}}]),
    completed([{'type': 'unknown'}]),
    completed([{'type': 'item.completed', 'item': {'id': 'bad', 'type': 'file_change', 'status': 'completed', 'changes': [{'path': '../escape', 'kind': 'add'}]}}]),
])
def test_invalid_events_fail_closed_without_raw_errors(native, events):
    settings, context, task, state, _ = native
    state['events'] = events
    with pytest.raises(ValueError) as error:
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    assert 'PRIVATE_ERROR' not in str(error.value)


def test_nonzero_exit_sanitizes_stderr(native):
    settings, context, task, state, _ = native
    state.update(exit_code=1, stderr='PRIVATE_ERROR authentication required')
    with pytest.raises(RuntimeError, match='authentication_required') as error:
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    assert 'PRIVATE_ERROR' not in str(error.value)


def test_reviewer_exit_keeps_bounded_process_facts_without_stderr(native, monkeypatch, tmp_path):
    from council.diagnostics import DiagnosticSession, describe
    settings, context, _, state, _ = native
    monkeypatch.setattr('council.codex_cli.cli_ready', lambda _: True)
    state.update(exit_code=7, stderr='PRIVATE_ERROR connection refused')
    with DiagnosticSession('codex-failure', tmp_path):
        with pytest.raises(RuntimeError) as caught:
            CodexCLIWorker('gpt-exact', settings, context).review_plan({})
    detail = describe(caught.value)['cli_process']
    assert detail['provider'] == 'codex-cli'
    assert detail['exit_code'] == 7
    assert detail['stderr_bytes'] >= len(state['stderr'].encode())
    assert detail['stderr_sha256']
    assert 'connection_refused' in detail['signals']
    assert 'PRIVATE_ERROR' not in json.dumps(detail)
    records = [json.loads(line) for line in (tmp_path/'diagnostics/codex-failure.jsonl').read_text().splitlines()]
    assert any(record['event'] == 'cli_attempt_failed' and record['cli_process'] == detail for record in records)


def test_coding_exit_records_process_facts_without_automatic_retry(native, monkeypatch):
    from council.diagnostics import describe
    settings, context, task, state, calls = native
    monkeypatch.setattr('council.codex_cli.cli_ready', lambda _: True)
    state.update(exit_code=8, stderr='PRIVATE_ERROR bad gateway')
    with pytest.raises(RuntimeError) as caught:
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    detail = describe(caught.value)['cli_process']
    assert detail['exit_code'] == 8
    assert 'server_error' in detail['signals']
    assert len([argv for argv, _ in calls if argv[-1] == '-']) == 1


def test_native_argument_conflict_has_static_category(native):
    settings, context, task, state, _ = native
    state.update(exit_code=2, stderr='PRIVATE_ERROR --approve-for-me cannot be used with --sandbox')
    with pytest.raises(RuntimeError, match='invalid_arguments') as error:
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    assert 'PRIVATE_ERROR' not in str(error.value)


def test_workspace_escape_rejected_before_process(native):
    settings, context, task, _, calls = native
    task.working_directory = '..'
    with pytest.raises((ValueError, PermissionError)):
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    assert calls == []


@pytest.mark.parametrize('relative', ['node_modules', '.codex'])
def test_excluded_task_cwd_rejected_before_process(native, relative):
    settings, context, task, _, calls = native
    (context.workspace_root/relative).mkdir()
    task.working_directory = relative
    with pytest.raises(PermissionError):
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    assert calls == []


def test_internal_link_task_cwd_rejected_before_process(native, monkeypatch):
    from council.tools import discovery
    settings, context, task, _, calls = native
    linked = context.workspace_root/'linked'
    # Exercise worker admission using a detected link, without constructing one
    # or modifying directory topology on the host.
    monkeypatch.setattr(discovery, '_linked', lambda path: path == linked)
    task.working_directory = 'linked'
    with pytest.raises(PermissionError):
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    assert calls == []


@pytest.mark.parametrize('field,value', [('version', 'other-client 0.164.0'), ('login', 'Logged in using an API key')])
def test_worker_rechecks_version_and_chatgpt_login_before_execution(native, field, value):
    settings, context, task, state, calls = native
    state[field] = value
    assert not cli_ready(settings)
    calls.clear()
    with pytest.raises(RuntimeError, match='unavailable'):
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    assert not any('exec' in argv for argv, _ in calls)


@pytest.mark.parametrize('raw', ['PRIVATE_MALFORMED', '{"type":"thread.started","type":"turn.failed"}',
                                  '{"type":"thread.started","value":NaN}', '\n'])
def test_malformed_jsonl_has_static_error(native, raw):
    settings, context, task, state, _ = native
    state['raw_output'] = raw
    with pytest.raises(ValueError, match='Invalid or failed') as error:
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    assert 'PRIVATE_MALFORMED' not in str(error.value)


@pytest.mark.parametrize('event', [
    {'type': 'item.completed', 'item': {'id': 'unknown', 'type': 'unsupported_item'}},
    {'type': 'item.started', 'item': {'id': 'invalid', 'type': 'file_change', 'changes': [{'path': '../escape', 'kind': 'add'}]}},
])
def test_unknown_item_shapes_and_invalid_incremental_file_paths_fail_closed(native, event):
    settings, context, task, state, _ = native
    state['events'] = completed([event])
    with pytest.raises(ValueError):
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')


@pytest.mark.parametrize('items', [
    [{'type': 'item.started', 'item': {'id': 'pending', 'type': 'command_execution', 'status': 'in_progress'}}],
    [{'type': 'item.completed', 'item': {'id': 'closed', 'type': 'reasoning', 'text': 'done'}},
     {'type': 'item.updated', 'item': {'id': 'closed', 'type': 'reasoning', 'text': 'changed'}}],
])
def test_turn_cannot_complete_with_open_or_reopened_items(native, items):
    settings, context, task, state, _ = native
    state['events'] = completed(items)
    with pytest.raises(ValueError):
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')


def test_completed_nonfatal_error_item_can_precede_turn_without_persisting_message(native):
    settings, context, task, state, _ = native
    events = completed()
    events.insert(1, {'type': 'item.completed', 'item': {'id': 'warning-1', 'type': 'error', 'message': 'PRIVATE_NONFATAL_DIAGNOSTIC'}})
    state['events'] = events
    result = CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    assert result.content == 'Implemented'
    assert result.response_metadata['cli_warning_count'] == 1
    assert 'PRIVATE_NONFATAL_DIAGNOSTIC' not in result.model_dump_json()


@pytest.mark.parametrize('diagnostic', [
    {'type': 'error', 'message': 'PRIVATE_FATAL_DIAGNOSTIC'},
    {'type': 'item.completed', 'item': {'id': 'warning', 'type': 'error', 'message': 123}},
    {'type': 'item.completed', 'item': {'id': 'warning', 'type': 'error', 'message': 'x'*4097}},
])
def test_fatal_or_malformed_diagnostics_still_fail_closed(native, diagnostic):
    settings, context, task, state, _ = native
    state['events'] = completed([diagnostic])
    with pytest.raises(ValueError) as error:
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    assert 'PRIVATE_FATAL_DIAGNOSTIC' not in str(error.value)


@pytest.mark.parametrize('failed', [
    {'id': 'red', 'type': 'command_execution', 'status': 'failed', 'exit_code': 1},
    {'id': 'red', 'type': 'file_change', 'status': 'failed', 'changes': [{'path': 'changed.txt', 'kind': 'update'}]},
])
def test_completed_turn_can_recover_known_failed_native_operations(native, failed):
    settings, context, task, state, _ = native
    state['events'] = completed([
        {'type': 'item.completed', 'item': failed},
        {'type': 'item.completed', 'item': {'id': 'green', 'type': 'command_execution', 'status': 'completed', 'exit_code': 0}},
    ])
    result = CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')
    assert result.response_metadata['cli_failed_item_count'] == 1
    assert result.content == 'Implemented'


def test_completed_failed_mcp_turn_is_not_success_and_retains_later_file_evidence(native):
    from council.diagnostics import describe
    settings, context, task, state, _ = native
    state['events']=completed([
        {'type':'item.completed','item':{'id':'mcp-1','type':'mcp_tool_call','status':'failed',
            'server':'PRIVATE_SERVER','tool':'PRIVATE_TOOL','error':{'message':'PRIVATE_ERROR'}}},
        {'type':'item.completed','item':{'id':'file-1','type':'file_change','status':'completed',
            'changes':[{'path':'changed.txt','kind':'add'}]}},
    ])
    with pytest.raises(ValueError) as caught:
        CodexCLIWorker('gpt-exact',settings,context).run_task(task,'guidance')
    assert caught.value.code=='CODEX_TOOL_FAILED'
    assert caught.value.native_file_changes==['changed.txt']
    assert caught.value.response_metadata['reported_usage']['output_tokens']==2
    detail=describe(caught.value)
    assert detail['native_event']=={'reason':'TOOL_FAILED','event_index':3,
        'event_type':'item.completed','item_type':'mcp_tool_call'}
    assert 'PRIVATE_' not in json.dumps(detail)


@pytest.mark.parametrize('tail,expected', [('not json','CODEX_JSON_INVALID'),
    (json.dumps({'type':'unexpected'}),'CODEX_EVENT_INVALID')])
def test_failed_mcp_does_not_hide_invalid_native_tail(native,tail,expected):
    settings, context, task, state, _ = native
    events=completed([{'type':'item.completed','item':{'id':'mcp-1','type':'mcp_tool_call','status':'failed'}}])
    state['raw_output']='\n'.join(json.dumps(e) for e in events[:-1])+'\n'+tail
    with pytest.raises(ValueError) as caught:
        CodexCLIWorker('gpt-exact',settings,context).run_task(task,'guidance')
    assert caught.value.code==expected


@pytest.mark.parametrize('mode,expected', [('incomplete','CODEX_TURN_INCOMPLETE'),
    ('escaping_change','CODEX_EVENT_INVALID'),('duplicate_item','CODEX_EVENT_INVALID'),
    ('review','CODEX_REVIEW_TOOL_REJECTED')])
def test_failed_mcp_preserves_stream_and_read_only_rejection_boundaries(native,mode,expected):
    settings, context, task, state, _ = native
    failure={'type':'item.completed','item':{'id':'mcp-1','type':'mcp_tool_call','status':'failed'}}
    extra=[failure]
    if mode=='escaping_change':extra.append({'type':'item.completed','item':{'id':'file-1',
        'type':'file_change','status':'completed','changes':[{'path':'../outside.txt','kind':'add'}]}})
    if mode=='duplicate_item':extra.append(failure)
    state['events']=completed(extra)
    if mode=='incomplete':state['events'].pop()
    with pytest.raises(ValueError) as caught:
        worker=CodexCLIWorker('gpt-exact',settings,context)
        if mode=='review':worker.invoke_read_only({})
        else:worker.run_task(task,'guidance')
    assert caught.value.code==expected


@pytest.mark.parametrize('failed', [
    {'id': 'bad', 'type': 'command_execution', 'status': 'failed', 'exit_code': 0},
    {'id': 'bad', 'type': 'command_execution', 'status': 'failed'},
    {'id': 'bad', 'type': 'command_execution', 'status': 'unexpected', 'exit_code': 1},
    {'id': 'bad', 'type': 'command_execution', 'status': 'declined', 'exit_code': 0},
    {'id': 'bad', 'type': 'file_change', 'status': 'cancelled', 'changes': []},
    {'id': 'bad', 'type': 'mcp_tool_call', 'status': 'failed'},
    {'id': 'bad', 'type': 'web_search', 'status': 'failed'},
])
def test_unsupported_failed_or_denied_operations_remain_fatal(native, failed):
    settings, context, task, state, _ = native
    state['events'] = completed([{'type': 'item.completed', 'item': failed}])
    with pytest.raises(ValueError):
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'guidance')


def test_bounded_input_and_child_timeout(native):
    from council.cli_process import run_process
    settings, context, task, state, calls = native
    with pytest.raises(ValueError, match='input limit'):
        CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'x'*(4*1024*1024))
    state['sleep'] = True
    with pytest.raises(RuntimeError, match='timed out'):
        run_process([settings['executable'], 'exec'], timeout=0.2, env=dict(os.environ))
    state['sleep'] = False
    state['raw_output'] = 'x'*(4*1024*1024+1)
    with pytest.raises(RuntimeError, match='output limit'):
        run_process([settings['executable'], 'exec'], env=dict(os.environ))
