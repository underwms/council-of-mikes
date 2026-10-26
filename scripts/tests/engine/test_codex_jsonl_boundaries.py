"""Native Codex JSONL is separated by LF, not every Unicode line separator."""

import json

import pytest

from council.codex_cli import _parse


def event_stream(message):
    events = [
        {'type': 'thread.started', 'thread_id': 'fixture-thread'},
        {'type': 'turn.started'},
        {'type': 'item.completed', 'item': {'id': 'fixture-message', 'type': 'agent_message', 'text': message}},
        {'type': 'turn.completed', 'usage': {'input_tokens': 2, 'output_tokens': 3}},
    ]
    return ('\n'.join(json.dumps(event, ensure_ascii=False) for event in events) + '\n').encode('utf-8')


@pytest.mark.parametrize('separator', ['\u2028', '\u2029', '\u0085'])
def test_valid_unicode_separator_inside_native_message_is_not_an_event_boundary(tmp_path, separator):
    message = f'before{separator}after'
    result = _parse(event_stream(message), tmp_path, tmp_path)
    assert result.content == message


def test_malformed_physical_json_line_still_fails_closed(tmp_path):
    raw = event_stream('valid').replace(b'"type": "turn.started"', b'not-json', 1)
    with pytest.raises(ValueError) as caught:
        _parse(raw, tmp_path, tmp_path)
    assert caught.value.code == 'CODEX_JSON_INVALID'


def file_change_stream(path):
    events = [
        {'type': 'thread.started', 'thread_id': 'fixture-thread'},
        {'type': 'turn.started'},
        {'type': 'item.completed', 'item': {'id': 'fixture-change', 'type': 'file_change',
                                         'status': 'completed', 'changes': [{'kind': 'add', 'path': path}]}},
        {'type': 'item.completed', 'item': {'id': 'fixture-message', 'type': 'agent_message', 'text': 'Done'}},
        {'type': 'turn.completed', 'usage': {'input_tokens': 2, 'output_tokens': 3}},
    ]
    return ('\n'.join(json.dumps(event) for event in events) + '\n').encode('utf-8')


def test_parent_segment_resolving_inside_workspace_is_recorded(tmp_path):
    workspace = tmp_path/'workspace'
    cwd = workspace/'shiprateapi'
    cwd.mkdir(parents=True)
    result = _parse(file_change_stream('../shiprateapi/tests/probe.cs'), cwd, workspace)
    assert result.additional_kwargs['native_file_changes'] == ['shiprateapi/tests/probe.cs']


def test_parent_segment_escaping_workspace_is_rejected_with_safe_category(tmp_path):
    workspace = tmp_path/'workspace'
    cwd = workspace/'shiprateapi'
    cwd.mkdir(parents=True)
    with pytest.raises(ValueError) as caught:
        _parse(file_change_stream('../../outside.cs'), cwd, workspace)
    assert caught.value.code == 'CODEX_EVENT_INVALID'
    assert caught.value.native_event['reason'] == 'FILE_PATH_OUTSIDE_WORKSPACE'
