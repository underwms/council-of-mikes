"""Offline diagnostic contracts; sentinels must never appear in diagnostic output."""
import json
from pathlib import Path

import pytest
from council import gemini_cli
from council.config import resolve_model_configuration
from council.model_evidence import build_call_record
from council.state import CouncilState
from test_engine_integration import lifecycle

SECRET = 'PRIVATE_PROMPT_RESPONSE_SECRET'


@pytest.mark.parametrize('value,expected', [
    ({'code':'INTERNAL_ERROR', 'graph_stage':'worker', 'message':SECRET},
        {'code':'INTERNAL_ERROR', 'graph_stage':'worker'}),
    ({'code':SECRET, 'graph_stage':'worker'}, None),
    ({'code':'INTERNAL_ERROR', 'graph_stage':SECRET}, None),
    ({'code':[], 'graph_stage':'worker'}, None),
    (None, None),
])
def test_failure_reference_retains_only_finite_identity(value, expected):
    from council.diagnostics import failure_reference
    assert failure_reference(value) == expected


@pytest.fixture
def model(monkeypatch, tmp_path):
    settings = {'node_path': str(tmp_path/'node.exe'), 'entrypoint': str(tmp_path/'gemini.js'),
                'cli_version': '0.64.0', 'timeout_seconds': 180}
    monkeypatch.setattr(gemini_cli, '_installed', lambda _: True)
    monkeypatch.setattr(gemini_cli, '_prepare_isolation', lambda *args: None)
    context = type('Context', (), {'memory_root': tmp_path})()
    return gemini_cli.GeminiCLIChatModel('test-model', settings, context)


@pytest.mark.parametrize('response,expected', [
    (SECRET.encode(), 'GEMINI_ENVELOPE_JSON_INVALID'),
    (json.dumps({'response': 42}).encode(), 'GEMINI_ENVELOPE_INVALID'),
    (json.dumps({'response': SECRET}).encode(), 'GEMINI_RESPONSE_JSON_INVALID'),
    (json.dumps({'response': '{"content":"' + SECRET + '"}'}).encode(), 'GEMINI_TOOL_ENVELOPE_INVALID'),
    (json.dumps({'response': json.dumps({'content': '', 'tool_calls': [
        {'name': SECRET, 'args': {}, 'id': 'a'}]})}).encode(), 'GEMINI_TOOL_NAME_UNOFFERED'),
    (json.dumps({'response': json.dumps({'content': '', 'tool_calls': [
        {'name': 'inspect', 'args': SECRET, 'id': 'a'}]})}).encode(), 'GEMINI_TOOL_ARGUMENTS_INVALID'),
])
def test_gemini_failure_is_classified_without_content(model, monkeypatch, response, expected):
    model._tools = ({'name': 'inspect'},)
    monkeypatch.setattr(gemini_cli, '_run', lambda *args: response)
    with pytest.raises(ValueError) as caught:
        model.invoke([{'role': 'user', 'content': SECRET}])
    assert getattr(caught.value, 'code', None) == expected
    assert SECRET not in str(caught.value)


def test_unknown_error_record_has_safe_fallback():
    record = build_call_record(resolve_model_configuration().model_dump(mode='json'),
                               'orchestrator', 'planning_inspection', error=ValueError(SECRET))
    assert record.get('diagnostic', {}).get('code') == 'INTERNAL_ERROR'
    assert SECRET not in json.dumps(record)


def test_gemini_partial_usage_survives_structured_parse_failure(model,monkeypatch):
    from council.state import PlanReviewDecision
    from council.model_evidence import _usage
    payload={'response':'not JSON','stats':{'models':{'reported-gemini':{'tokens':{'prompt':8,'total':11}}}}}
    monkeypatch.setattr(gemini_cli,'_run',lambda *args:json.dumps(payload).encode())
    with pytest.raises(ValueError) as caught:
        model.with_structured_output(PlanReviewDecision,include_raw=True).invoke([{'role':'user','content':SECRET}])
    assert _usage(caught.value,caught.value.response_metadata)=={'input_tokens':8,'total_tokens':11}


def test_old_state_loads_without_diagnostic():
    state = CouncilState(run_id='old', task_input='old')
    assert hasattr(state, 'diagnostic')
    assert state.diagnostic is None


def test_reporter_separates_streams_and_persists_only_allowlisted_fields(tmp_path, capsys):
    from council.diagnostics import DiagnosticSession, DiagnosticValueError
    with DiagnosticSession('fixture', tmp_path) as session:
        session.event('call_started', stage='model', role=SECRET, operation=SECRET, call=1)
        session.event('call_failed', stage='model', diagnostic=DiagnosticValueError('GEMINI_RESPONSE_JSON_INVALID'))
    output = capsys.readouterr()
    assert output.out == ''
    assert SECRET not in output.err
    records = [json.loads(line) for line in (tmp_path/'diagnostics/fixture.jsonl').read_text().splitlines()]
    assert records[-1]['event'] == 'run_finished'
    assert records[-2]['code'] == 'GEMINI_RESPONSE_JSON_INVALID'
    assert all(record['run_id'] == 'fixture' for record in records)
    assert SECRET not in json.dumps(records)


def test_cli_process_facts_survive_checkpoint_and_timeline(tmp_path, capsys):
    from council.diagnostics import DiagnosticSession, execution_error, describe
    from council.state import CouncilState
    from council.cli_process import process_detail
    error = execution_error('execution_failed', cli_process=process_detail(
        'codex-cli', 12, b'PRIVATE_PROMPT_RESPONSE_SECRET connection refused', b'partial output'))
    saved = CouncilState(run_id='fixture', task_input='test', diagnostic=describe(error))
    with DiagnosticSession('fixture', tmp_path) as session:
        session.event('call_failed', stage='model', diagnostic=error)
    records = [json.loads(line) for line in (tmp_path/'diagnostics/fixture.jsonl').read_text().splitlines()]
    assert saved.diagnostic['cli_process']['exit_code'] == 12
    assert records[-2]['cli_process'] == saved.diagnostic['cli_process']
    assert SECRET not in json.dumps(records) + json.dumps(saved.diagnostic) + capsys.readouterr().err


def test_strategy_reset_stage_is_preserved_in_timeline(tmp_path, capsys):
    from council.diagnostics import DiagnosticSession
    with DiagnosticSession('strategy-fixture', tmp_path) as session:
        session.event('node_started', stage='strategy_reset')
    records = [json.loads(line) for line in (tmp_path/'diagnostics/strategy-fixture.jsonl').read_text().splitlines()]
    assert records[1]['stage'] == 'strategy_reset'


def test_reporter_is_bounded_and_preserves_unrelated_files(tmp_path, monkeypatch, capsys):
    import council.diagnostics as diagnostic
    monkeypatch.setattr(diagnostic, 'MAX_FILES', 2)
    monkeypatch.setattr(diagnostic, 'MAX_BYTES', 2048)
    root = tmp_path/'diagnostics'
    root.mkdir()
    unrelated = root/'keep.txt'
    unrelated.write_text(SECRET)
    for name in ('one', 'two', 'three'):
        with diagnostic.DiagnosticSession(name, tmp_path) as session:
            for _ in range(50):
                session.event('call_started', stage='model')
    assert len(list(root.glob('*.jsonl'))) <= 2
    assert all(file.stat().st_size <= 2048 for file in root.glob('*.jsonl'))
    assert unrelated.read_text() == SECRET
    assert SECRET not in capsys.readouterr().err


def test_persistence_failure_does_not_mask_original_exception(tmp_path, capsys):
    from council.diagnostics import DiagnosticSession, DiagnosticValueError
    (tmp_path/'diagnostics').write_text(SECRET)
    with pytest.raises(ValueError) as caught:
        with DiagnosticSession('fixture', tmp_path) as session:
            raise DiagnosticValueError('GEMINI_SCHEMA_INVALID')
    assert caught.value.code == 'GEMINI_SCHEMA_INVALID'
    assert session.summary()['diagnostics_status'] == 'unavailable'
    assert 'DIAGNOSTICS_UNAVAILABLE' in capsys.readouterr().err


def test_invalid_run_id_cannot_write_outside_log_root(tmp_path):
    from council.diagnostics import DiagnosticSession
    with pytest.raises(ValueError):
        DiagnosticSession('../escape', tmp_path)
    assert not list(tmp_path.iterdir())


def test_classified_error_survives_checkpoint_and_console(lifecycle, monkeypatch, capsys):
    from council.diagnostics import DiagnosticValueError, DiagnosticSession
    from council.graph import build_council_graph
    from council.checkpoint import managed_sqlite_checkpointer
    class Provider:
        def bind_tools(self, tools):
            return self
        def invoke(self, messages):
            raise DiagnosticValueError('GEMINI_TOOL_ENVELOPE_INVALID')
    with DiagnosticSession('integration-run', lifecycle.context.memory_root):
        with managed_sqlite_checkpointer(context=lifecycle.context, db_path=lifecycle.db) as saver:
            graph = build_council_graph(saver, lifecycle.context, lambda role: Provider())
            result = graph.invoke(lifecycle.state.model_dump(mode='json'), lifecycle.config)
            saved = graph.get_state(lifecycle.config).values
    assert result['status'] == 'FAILED'
    assert saved['diagnostic']['code'] == 'GEMINI_TOOL_ENVELOPE_INVALID'
    assert saved['model_calls'][-1]['diagnostic']['code'] == saved['diagnostic']['code']
    events = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert any(e['event'] == 'call_started' and e['call'] == 1 for e in events)
    assert any(e.get('code') == saved['diagnostic']['code'] for e in events)


def test_early_cli_failure_has_correlation_and_relative_story_hint(tmp_path, capsys):
    from council.cli import main
    from unittest.mock import patch
    context = type('Context', (), {'memory_root': tmp_path, 'workspace_path': lambda self, story: (_ for _ in ()).throw(PermissionError(SECRET))})()
    with patch('council.cli.resolve_context', return_value=context):
        assert main(['--story', str(tmp_path/'story.md')]) == 1
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result['run_id']
    assert result['diagnostic']['code'] == 'STORY_PATH_INVALID'
    assert SECRET not in output.err + output.out


def test_codex_error_preserves_file_evidence_and_classifies(tmp_path):
    from council.codex_cli import _parse
    events = [
        {'type': 'thread.started', 'thread_id': 'fixture'}, {'type': 'turn.started'},
        {'type': 'item.completed', 'item': {'id': 'f', 'type': 'file_change', 'status': 'completed',
            'changes': [{'path': str(tmp_path/'changed.txt'), 'kind': 'add'}]}},
        {'type': 'turn.failed', 'error': {'message': SECRET}},
    ]
    with pytest.raises(ValueError) as caught:
        _parse('\n'.join(json.dumps(e) for e in events).encode(), tmp_path, tmp_path)
    assert getattr(caught.value, 'code', None) == 'CODEX_TURN_FAILED'
    assert caught.value.native_file_changes == ['changed.txt']
    assert SECRET not in str(caught.value)


def test_unknown_exception_name_cannot_enter_evidence():
    untrusted = type(SECRET, (ValueError,), {})
    record = build_call_record(resolve_model_configuration().model_dump(mode='json'),
                               'orchestrator', 'planning_inspection', error=untrusted(SECRET))
    assert SECRET not in json.dumps(record)


def test_linked_log_target_is_refused_even_when_broken(tmp_path, monkeypatch, capsys):
    from council.diagnostics import DiagnosticSession
    root = tmp_path/'diagnostics'
    root.mkdir()
    target = root/'fixture.jsonl'
    # Windows symlink creation is host-restricted; model the link metadata and
    # fail if an append is attempted. Real directory/file checks remain active.
    original_link = Path.is_symlink
    original_open = Path.open
    monkeypatch.setattr(Path, 'is_symlink', lambda p: p == target or original_link(p))
    def guarded_open(path, *args, **kwargs):
        assert path != target, 'A broken link must never be opened for append'
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded_open)
    with DiagnosticSession('fixture', tmp_path) as session:
        session.event('call_started')
    assert session.summary()['diagnostics_status'] == 'unavailable'


def test_main_approval_pause_has_safe_timeline(lifecycle, monkeypatch, capsys):
    from council.cli import main
    from test_engine_integration import ScriptedProvider
    monkeypatch.setattr('council.graph.get_llm_for_role', lambda *args, **kwargs: ScriptedProvider(lifecycle.plan))
    monkeypatch.setattr('council.cli.preflight_credentials', lambda _: {'gpt': True, 'gemini': True})
    result_code = main(['--workspace', str(lifecycle.workspace), '--council-root', str(lifecycle.context.council_root),
                       '--approval-mode', 'manual', '--no-input', SECRET])
    assert result_code == 2
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result['status'] == 'PAUSED'
    assert result['diagnostics_status'] == 'available'
    assert SECRET not in output.err
    root = lifecycle.context.council_root/'memory/engine'
    records = [json.loads(line) for line in (root/result['diagnostics_file']).read_text().splitlines()]
    assert SECRET not in json.dumps(records)
    assert any(e['event'] == 'approval_waiting' for e in records)
    assert any(e['event'] == 'call_succeeded' for e in records)
    assert records[-1]['event'] == 'run_finished'
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_concurrent_session_cannot_write_or_prune_active_run(tmp_path, monkeypatch):
    import council.diagnostics as diagnostic
    monkeypatch.setattr(diagnostic, 'MAX_FILES', 1)
    with diagnostic.DiagnosticSession('active', tmp_path) as first:
        with diagnostic.DiagnosticSession('active', tmp_path) as duplicate:
            assert duplicate.summary()['diagnostics_status'] == 'unavailable'
        with diagnostic.DiagnosticSession('another', tmp_path) as another:
            assert another.summary()['diagnostics_status'] == 'unavailable'
        assert first.summary()['diagnostics_status'] == 'available'
        assert (tmp_path/'diagnostics/active.jsonl').exists()
    with diagnostic.DiagnosticSession('after', tmp_path) as after:
        assert after.summary()['diagnostics_status'] == 'available'
    assert not (tmp_path/'diagnostics/active.jsonl').exists()


def test_write_failure_and_closed_console_preserve_task_error(tmp_path, monkeypatch, capsys):
    from council.diagnostics import DiagnosticSession, DiagnosticValueError
    with pytest.raises(ValueError) as caught:
        with DiagnosticSession('write-failed', tmp_path) as session:
            def unavailable(*args):
                raise OSError(SECRET)
            monkeypatch.setattr(session._file, 'write', unavailable)
            session.event('call_started')
            raise DiagnosticValueError('GEMINI_RESPONSE_JSON_INVALID')
    assert caught.value.code == 'GEMINI_RESPONSE_JSON_INVALID'
    assert session.summary()['diagnostics_status'] == 'unavailable'
    assert SECRET not in capsys.readouterr().err
    class ClosedConsole:
        def write(self, value):
            raise OSError(SECRET)
        def flush(self):
            raise OSError(SECRET)
    monkeypatch.setattr('sys.stderr', ClosedConsole())
    with DiagnosticSession('closed-console', tmp_path) as session:
        session.event('call_started')
    assert session.summary()['diagnostics_status'] == 'available'


def test_capped_file_reports_cap_and_keeps_terminal_marker(tmp_path, monkeypatch):
    import council.diagnostics as diagnostic
    monkeypatch.setattr(diagnostic, 'MAX_BYTES', 1536)
    with diagnostic.DiagnosticSession('capped', tmp_path) as session:
        for _ in range(25):
            session.event('call_started')
    assert session.summary()['diagnostics_status'] == 'capped'
    path = tmp_path/'diagnostics/capped.jsonl'
    assert path.stat().st_size <= 1536
    assert json.loads(path.read_text().splitlines()[-1])['event'] == 'run_finished'


def test_schema_failure_and_native_tool_execution_have_separate_codes(model, monkeypatch):
    from pydantic import BaseModel
    class Answer(BaseModel):
        count: int
    monkeypatch.setattr(gemini_cli, '_run', lambda *args: json.dumps({'response': '{"count":"' + SECRET + '"}'}).encode())
    with pytest.raises(ValueError) as caught:
        model.with_structured_output(Answer).invoke([])
    assert caught.value.code == 'GEMINI_SCHEMA_INVALID'
    assert SECRET not in str(caught.value)
    monkeypatch.setattr(gemini_cli, '_run', lambda *args: json.dumps({'response': SECRET, 'stats': {'tools': {'totalCalls': 1}}}).encode())
    with pytest.raises(ValueError) as caught:
        model.invoke([])
    assert caught.value.code == 'GEMINI_NATIVE_TOOLS_REJECTED'


def test_codex_json_and_incomplete_turn_fail_with_specific_codes(tmp_path):
    from council.codex_cli import _parse
    for payload, expected in ((SECRET.encode(), 'CODEX_JSON_INVALID'),
                              (b'{"type":"thread.started","thread_id":"f"}', 'CODEX_TURN_INCOMPLETE')):
        with pytest.raises(ValueError) as caught:
            _parse(payload, tmp_path, tmp_path)
        assert caught.value.code == expected
        assert caught.value.native_file_changes == []


def test_main_missing_story_and_invalid_resume_are_safe(tmp_path, capsys, monkeypatch):
    from council.cli import main
    context = type('Context', (), {'memory_root': tmp_path, 'workspace_path': lambda self, story: tmp_path/'missing'})()
    monkeypatch.setattr('council.cli.resolve_context', lambda *args: context)
    assert main(['--story', SECRET]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)['diagnostic']['code'] == 'STORY_READ_FAILED'
    assert SECRET not in output.err + output.out
    assert main(['--resume', '../' + SECRET]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)['run_id']
    assert SECRET not in output.err + output.out
