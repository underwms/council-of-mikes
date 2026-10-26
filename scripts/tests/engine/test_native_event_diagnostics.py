"""Sanitized rejection facts without native payload retention or parser relaxation."""
import json

import pytest

from council.codex_cli import _parse
from council.diagnostics import DiagnosticSession, DiagnosticValueError, describe
from council.model_evidence import build_call_record
from council.config import resolve_model_configuration
from test_engine_integration import lifecycle


SECRET = 'PRIVATE_NATIVE_PAYLOAD'
START = [{'type': 'thread.started', 'thread_id': 'fixture'}, {'type': 'turn.started'}]


def rejected(tmp_path, events, **kwargs):
    raw = events if isinstance(events, bytes) else '\n'.join(json.dumps(e) for e in events).encode()
    with pytest.raises(ValueError) as caught:
        _parse(raw, tmp_path, tmp_path, **kwargs)
    assert SECRET not in str(caught.value)
    return caught.value


@pytest.mark.parametrize('event,reason,event_type,item_type', [
    ({'type': SECRET}, 'UNSUPPORTED_EVENT', 'unknown', 'none'),
    ({'type': 'item.completed', 'item': {'id': 'a', 'type': SECRET}}, 'UNSUPPORTED_ITEM', 'item.completed', 'unknown'),
    ({'type': 'item.completed', 'item': {'id': 'a', 'type': 'agent_message', 'text': ''}}, 'INVALID_FINAL_MESSAGE', 'item.completed', 'agent_message'),
    ({'type': 'thread.started', 'thread_id': SECRET}, 'INVALID_THREAD', 'thread.started', 'none'),
    ({'type': 'item.completed', 'item': {'id': 'a', 'type': 'file_change', 'status': 'completed', 'changes': [{'path': '../'+SECRET, 'kind': 'add'}]}}, 'FILE_PATH_OUTSIDE_WORKSPACE', 'item.completed', 'file_change'),
    ({'type': 'turn.failed', 'message': SECRET}, 'TURN_FAILED', 'turn.failed', 'none'),
])
def test_rejections_have_finite_reason_and_position(tmp_path, event, reason, event_type, item_type):
    error = rejected(tmp_path, START+[event])
    detail = describe(error)
    assert detail['native_event'] == {'reason': reason, 'event_index': 3, 'event_type': event_type, 'item_type': item_type}
    assert SECRET not in json.dumps(detail)


@pytest.mark.parametrize('raw,reason,index,category', [
    (b'', 'EMPTY_EVENT', 0, 'none'),
    (b'\xff', 'INVALID_ENCODING', 0, 'none'),
    (b'\n', 'EMPTY_EVENT', 1, 'invalid'),
    (b'{"type":', 'INVALID_JSON', 1, 'invalid'),
    (b'[]', 'INVALID_EVENT', 1, 'invalid'),
])
def test_unparseable_stream_has_no_payload(tmp_path, raw, reason, index, category):
    assert describe(rejected(tmp_path, raw))['native_event'] == {
        'reason': reason, 'event_index': index, 'event_type': category, 'item_type': 'none'}


def test_eof_and_duplicate_lifecycle_remain_rejected(tmp_path):
    assert describe(rejected(tmp_path, START))['native_event'] == {
        'reason': 'TURN_INCOMPLETE', 'event_index': 3, 'event_type': 'end_of_stream', 'item_type': 'none'}
    item = {'id': 'a', 'type': 'reasoning'}
    error = rejected(tmp_path, START+[{'type': 'item.started', 'item': item}]*2)
    assert describe(error)['native_event']['reason'] == 'DUPLICATE_ITEM_START'
    assert describe(error)['native_event']['event_index'] == 4


def test_review_tools_and_file_tracking_remain_protected(tmp_path):
    change = {'type': 'item.completed', 'item': {'id': 'a', 'type': 'file_change',
        'status': 'completed', 'changes': [{'path': 'changed.txt', 'kind': 'add'}]}}
    error = rejected(tmp_path, START+[change, {'type': SECRET}])
    assert error.native_file_changes == ['changed.txt']
    assert describe(error)['native_event']['reason'] == 'UNSUPPORTED_EVENT'
    review = rejected(tmp_path, START+[change], review_only=True)
    assert review.code == 'CODEX_REVIEW_TOOL_REJECTED'
    assert describe(review)['native_event']['reason'] == 'REVIEW_TOOL_REJECTED'


def test_context_survives_call_evidence_and_lifecycle(tmp_path, capsys):
    error = rejected(tmp_path, START+[{'type': SECRET}])
    detail = describe(error)['native_event']
    record = build_call_record(resolve_model_configuration().model_dump(mode='json'), 'coder', 'worker', error=error)
    assert record['diagnostic']['native_event'] == detail
    with DiagnosticSession('native-fixture', tmp_path) as session:
        session.event('call_failed', stage='model', diagnostic=error)
    lines = (tmp_path/'diagnostics/native-fixture.jsonl').read_text().splitlines()
    assert json.loads(lines[-2])['native_event'] == detail
    output = capsys.readouterr()
    assert detail['reason'] in output.err
    assert SECRET not in output.err + ''.join(lines) + json.dumps(record)


@pytest.mark.parametrize('field,value', [('reason', SECRET), ('event_type', SECRET),
    ('item_type', SECRET), ('event_index', True), ('event_index', -1), ('event_index', 4194306)])
def test_mutated_context_is_revalidated(tmp_path, field, value):
    error = rejected(tmp_path, START+[{'type': SECRET}])
    error.native_event[field] = value
    assert 'native_event' not in describe(error)


def test_arbitrary_exception_context_is_not_trusted():
    error = ValueError(SECRET)
    error.native_event = {'reason': SECRET}
    assert describe(error)['code'] == 'INTERNAL_ERROR'
    assert SECRET not in json.dumps(describe(error))
    assert 'native_event' not in describe(DiagnosticValueError('CODEX_EVENT_INVALID'))


def test_parser_diagnostic_survives_graph_checkpoint(lifecycle, capsys):
    from council.checkpoint import managed_sqlite_checkpointer
    from council.graph import build_council_graph

    class Provider:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            _parse(b'{"type":"PRIVATE_NATIVE_PAYLOAD"}', lifecycle.workspace, lifecycle.workspace)

    with DiagnosticSession('native-checkpoint', lifecycle.context.memory_root):
        with managed_sqlite_checkpointer(context=lifecycle.context, db_path=lifecycle.db) as saver:
            graph = build_council_graph(saver, lifecycle.context, lambda role: Provider())
            result = graph.invoke(lifecycle.state.model_dump(mode='json'), lifecycle.config)
            saved = graph.get_state(lifecycle.config).values
    assert result['status'] == 'FAILED'
    detail = saved['diagnostic']['native_event']
    assert detail['reason'] == 'UNSUPPORTED_EVENT'
    assert saved['model_calls'][-1]['diagnostic']['native_event'] == detail
    events = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    for name in ('call_failed', 'node_failed'):
        assert any(e['event'] == name and e.get('native_event') == detail for e in events)
    assert SECRET not in json.dumps(saved['diagnostic']) + json.dumps(events)


@pytest.mark.parametrize('events,reason', [
    ([{'type': 'turn.started'}], 'INVALID_TURN'),
    (START+[{'type': 'item.completed', 'item': {'id': 'a', 'type': 'error', 'message': 1}}], 'INVALID_DIAGNOSTIC'),
    (START+[{'type': 'item.completed', 'item': []}], 'INVALID_ITEM'),
    (START+[{'type': 'item.completed', 'item': {'id': 'a', 'type': 'reasoning'}}]*2, 'INVALID_ITEM_LIFECYCLE'),
    (START+[{'type': 'item.completed', 'item': {'id': 'a', 'type': 'file_change', 'changes': None}}], 'INVALID_FILE_CHANGES'),
    (START+[{'type': 'item.completed', 'item': {'id': 'a', 'type': 'file_change', 'changes': []}}], 'INVALID_FILE_CHANGES'),
    (START+[{'type': 'item.completed', 'item': {'id': 'a', 'type': 'file_change', 'changes': [{'kind': SECRET}]}}], 'INVALID_FILE_CHANGE'),
    (START+[{'type': 'item.completed', 'item': {'id': 'a', 'type': 'web_search', 'status': 'failed'}}], 'UNSUPPORTED_FAILED_ITEM'),
    (START+[{'type': 'item.completed', 'item': {'id': 'a', 'type': 'mcp_tool_call', 'status': 'failed'}}], 'TURN_INCOMPLETE'),
    (START+[{'type': 'item.completed', 'item': {'id': 'a', 'type': 'command_execution', 'status': 'failed', 'exit_code': 0}}], 'INVALID_FAILED_COMMAND'),
    (START+[{'type': 'item.completed', 'item': {'id': 'a', 'type': 'command_execution', 'status': 'completed'}}], 'INVALID_COMPLETED_COMMAND'),
    (START+[{'type': 'item.completed', 'item': {'id': 'a', 'type': 'agent_message', 'text': 'ok'}}, {'type': 'turn.completed', 'usage': {}}], 'INVALID_USAGE'),
    (START+[{'type': 'item.completed', 'item': {'id': 'a', 'type': 'agent_message', 'text': 'ok'}}, {'type': 'turn.completed', 'usage': None}], 'INVALID_USAGE'),
])
def test_distinct_contract_failures_keep_their_identity(tmp_path, events, reason):
    assert describe(rejected(tmp_path, events))['native_event']['reason'] == reason


@pytest.mark.parametrize('value', [None, [], {'reason': SECRET},
    {'reason': 'INVALID_EVENT', 'event_index': 1, 'event_type': 'invalid', 'item_type': 'none', 'extra': SECRET}])
def test_malformed_context_is_dropped(value):
    error = DiagnosticValueError('CODEX_EVENT_INVALID')
    error.native_event = value
    assert 'native_event' not in describe(error)


@pytest.mark.parametrize('path,reason', [
    (None, 'INVALID_FILE_PATH'),
    ('.', 'INVALID_FILE_PATH'),
    ('outside', 'FILE_PATH_OUTSIDE_WORKSPACE'),
])
def test_invalid_file_path_rejection_is_classified(tmp_path, path, reason):
    path = str(tmp_path.parent/'outside.txt') if path == 'outside' else path
    event = {'type': 'item.completed', 'item': {'id': 'a', 'type': 'file_change',
        'changes': [{'kind': 'add', 'path': path}]}}
    assert describe(rejected(tmp_path, START+[event]))['native_event']['reason'] == reason


def test_unexpected_parser_exception_uses_constant_fallback(tmp_path, monkeypatch):
    def fail(*args):
        raise TypeError(SECRET)
    monkeypatch.setattr('council.codex_cli._file_path', fail)
    event = {'type': 'item.completed', 'item': {'id': 'a', 'type': 'file_change',
        'changes': [{'kind': 'add', 'path': SECRET}]}}
    detail = describe(rejected(tmp_path, START+[event]))
    assert detail['native_event']['reason'] == 'CONTRACT_INVALID'
    assert SECRET not in json.dumps(detail)
