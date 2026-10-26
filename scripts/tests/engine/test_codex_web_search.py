"""Compatibility for the observed native 0.164.0 flattened web-search ID pair."""
import json

import pytest

from council.codex_cli import _json, _parse


def search(kind, native='item_1', provider='search-provider-1', **fields):
    item = json.dumps({'id': native, 'type': 'web_search', **fields})
    item = item[:-1] + ',"id":' + json.dumps(provider) + '}'
    return '{"type":' + json.dumps(kind) + ',"item":' + item + '}'


def stream(*records):
    return ('\n'.join([
        '{"type":"thread.started","thread_id":"thread-test"}',
        '{"type":"turn.started"}', *records,
        '{"type":"item.completed","item":{"id":"message-1","type":"agent_message","text":"Verified"}}',
        '{"type":"turn.completed","usage":{"input_tokens":3,"output_tokens":2}}',
    ]) + '\n').encode()


def parse(tmp_path, records, version='0.164.0', **kwargs):
    return _parse(stream(*records), tmp_path, tmp_path, cli_version=version, **kwargs)


def test_native_search_uses_outer_id_when_provider_id_changes(tmp_path):
    result = parse(tmp_path, [
        search('item.started', provider='search-start', status='in_progress'),
        search('item.updated', provider='search-update', status='in_progress'),
        search('item.completed', provider='search-end', status='completed'),
    ])
    assert result.content == 'Verified'
    assert result.usage_metadata['total_tokens'] == 5
    assert result.response_metadata['cli_web_search_id_compatibility_count'] == 3


def test_separate_native_items_can_share_provider_identifier(tmp_path):
    result = parse(tmp_path, [search('item.completed', native='item_1'),
                              search('item.completed', native='item_2')])
    assert result.content == 'Verified'


def test_substantive_json_decoder_remains_strict_and_returns_an_object():
    assert _json('{"decision":"accept","findings":[]}') == {'decision': 'accept', 'findings': []}
    with pytest.raises(ValueError) as error:
        _json(search('item.completed'))
    assert error.value.code == 'CODEX_JSON_INVALID'


@pytest.mark.parametrize('version', [None, '0.163.0', '0.164.1', '0.165.0'])
def test_duplicate_search_id_compatibility_is_version_scoped(tmp_path, version):
    with pytest.raises(ValueError) as error:
        parse(tmp_path, [search('item.completed')], version=version)
    assert error.value.code == 'CODEX_JSON_INVALID'


@pytest.mark.parametrize('record', [
    # The compatibility rule cannot hide an ambiguous control or payload field.
    search('item.completed').replace('"type":"item.completed"', '"type":"item.completed","type":"item.started"'),
    search('item.completed').replace('"type": "web_search"', '"type":"web_search","type":"command_execution"'),
    search('item.completed', status='completed').replace('"status": "completed"', '"status":"completed","status":"failed"'),
    search('item.completed').replace('"type": "web_search"', '"type":"command_execution"'),
    search('item.completed', native='search-provider-1', provider='item_1'),
    search('item.completed', provider='item_1'),
    search('item.completed', provider=None),
    search('item.completed', provider='invalid identifier'),
    search('item.completed', provider='x' * 257),
    search('item.completed').replace('}}', ',"id":"search-third"}}'),
    search('turn.started'),
    search('item.completed', result={'id': 'nested'}).replace('"id": "nested"', '"id":"nested","id":"other"'),
    search('item.completed', result=0).replace('"result": 0', '"result": NaN'),
])
def test_other_duplicate_or_malformed_native_search_fields_fail_closed(tmp_path, record):
    with pytest.raises(ValueError) as error:
        parse(tmp_path, [record])
    assert error.value.code == 'CODEX_JSON_INVALID'


def test_provider_id_cannot_close_a_different_native_item(tmp_path):
    with pytest.raises(ValueError) as error:
        parse(tmp_path, [search('item.started', native='item_1'),
                         search('item.completed', native='item_2')])
    assert error.value.code == 'CODEX_TURN_INCOMPLETE'


def test_search_compatibility_does_not_enable_reviewer_tools(tmp_path):
    with pytest.raises(ValueError) as error:
        parse(tmp_path, [search('item.completed')], review_only=True)
    assert error.value.code == 'CODEX_REVIEW_TOOL_REJECTED'


def test_search_compatibility_does_not_bypass_file_boundaries(tmp_path):
    record = json.dumps({'type': 'item.completed', 'item': {'id': 'file-1',
        'type': 'file_change', 'status': 'completed',
        'changes': [{'path': '../outside.txt', 'kind': 'add'}]}})
    with pytest.raises(ValueError) as error:
        parse(tmp_path, [search('item.completed'), record])
    assert error.value.native_event['reason'] == 'FILE_PATH_OUTSIDE_WORKSPACE'
