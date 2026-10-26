"""Independent reconstruction proves native transport retains complete JSON values."""
import copy
import json
import pytest
from council.codex_input import encode_request, MAX_CHARACTERS, PREFIX

def compact(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()

def restore_payload(payload):
    if not payload.startswith(PREFIX):
        return json.loads(payload)
    envelope = json.loads(payload[len(PREFIX):])
    assert envelope['format'] == 'council-json-references-v1'
    root = envelope['request']
    def parts(pointer):
        assert pointer.startswith('/')
        return [part.replace('~1', '/').replace('~0', '~') for part in pointer[1:].split('/')]
    def locate(pointer):
        value = root
        path = parts(pointer)
        for part in path[:-1]:
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value, int(path[-1]) if isinstance(value, list) else path[-1]
    for destination, source in envelope['copies']:
        parent, key = locate(source)
        value = copy.deepcopy(parent[key])
        parent, key = locate(destination)
        parent[key] = value
    for pointer, kind in envelope['json_text']:
        parent, key = locate(pointer)
        if kind == 'json':
            parent[key] = json.dumps(parent[key], ensure_ascii=True, allow_nan=False)
        else:
            assert kind == 'json_suffix'
            parent[key] = parent[key]['prefix'] + json.dumps(parent[key]['json'], ensure_ascii=True, allow_nan=False)
    return root

def test_small_input_retains_exact_existing_bytes():
    request = {'instruction': 'retain \r\n tabs\t and éU0001f680', 'null': None, 'list': [False, 0, -0.0, '']}
    assert encode_request(request) == compact(request)

def test_repeated_large_values_are_complete_reversible_and_do_not_mutate_input():
    shared = {'evidence': 'retained evidence ' * 36000, 'value': None, 'marker': 'required'}
    request = {'instruction': 'Review both complete records.', 'one': shared, 'two': shared}
    original = compact(request)
    assert len(original) > MAX_CHARACTERS
    encoded = encode_request(request)
    assert len(encoded.decode()) <= MAX_CHARACTERS
    assert compact(restore_payload(encoded)) == original
    assert compact(request) == original

def test_embedded_canonical_json_messages_roundtrip_exactly_with_all_values():
    frame = {'shared_context': {'record': {'value': 'evidence ' * 70000, 'currency': None}}}
    message = json.dumps(frame)
    request = {'messages': [{'role': 'user', 'content': message}, {'role': 'assistant', 'content': message}]}
    original = compact(request)
    assert len(original) > MAX_CHARACTERS
    encoded = encode_request(request)
    assert len(encoded.decode()) <= MAX_CHARACTERS
    restored = restore_payload(encoded)
    assert compact(restored) == original
    assert restored['messages'][0]['content'] == message

def test_exact_native_boundary_is_unchanged():
    value = 'x' * (MAX_CHARACTERS - 2)
    assert len(encode_request(value)) == MAX_CHARACTERS
    with pytest.raises(ValueError, match='input limit'):
        encode_request(value + 'x')

def test_original_byte_bound_is_not_relaxed_by_references():
    request = {'copies': [{'evidence': 'x' * 60000}] * 80}
    with pytest.raises(ValueError, match='input limit'):
        encode_request(request)

@pytest.mark.parametrize('value', [float('nan'), float('inf'), object(), {1, 2}])
def test_invalid_json_still_fails_before_native_execution(value):
    with pytest.raises(ValueError, match='input'):
        encode_request({'value': value})


def large_record():
    return {'padding': 'evidence ' * 70000, 'truth': False, 'zero': 0, 'null': None, 'empty': ''}


def test_copy_paths_escape_keys_and_literal_reference_shapes_remain_data():
    record = large_record()
    request = {'a/b~c': record, '': [record, None], '0': {'$ref': '/not/a/transport/path'},
               'format': 'council-json-references-v1', 'copies': [['literal', 'data']]}
    encoded = encode_request(request)
    assert compact(restore_payload(encoded)) == compact(request)


def test_transport_prefix_cannot_collide_with_a_literal_small_envelope():
    request = {'format': 'council-json-references-v1', 'request': None, 'copies': [], 'json_text': []}
    assert encode_request(request) == compact(request)
    assert restore_payload(encode_request(request)) == request


@pytest.mark.parametrize('message', ['role', 'langchain'])
def test_canonical_unicode_json_text_preserves_exact_strings_and_other_copies(message):
    record = large_record()
    record['unicode'] = 'éU0001f680/~\r\n\t'
    content = json.dumps(record)
    body = {'role': 'user', 'content': content} if message == 'role' else {'type': 'human', 'data': {'content': content}}
    request = {'messages': [body, body], 'structured': record}
    encoded = encode_request(request)
    assert compact(restore_payload(encoded)) == compact(request)


def test_canonical_context_suffix_restores_prose_and_json_byte_for_byte():
    from council.graph_integrity import _MARKER
    record = large_record()
    guidance = 'Keep all instructions.\r\n' + _MARKER + json.dumps({'one': record, 'two': record})
    request = {'guidance': guidance, 'task': {'acceptance_criteria': ['unchanged']}}
    encoded = encode_request(request)
    assert compact(restore_payload(encoded)) == compact(request)


@pytest.mark.parametrize('content', [
    json.dumps(large_record(), indent=2, ensure_ascii=False),
    'not JSON ' * 70000,
    '{"not canonical": NaN}' + ' ' * 630000,
], ids=['indented', 'plain', 'nonfinite'])
def test_noncanonical_message_text_remains_literal(content):
    request = {'messages': [{'role': 'user', 'content': content}, {'role': 'assistant', 'content': content}]}
    encoded = encode_request(request)
    assert compact(restore_payload(encoded)) == compact(request)


def test_nonmessage_content_and_malformed_role_are_ordinary_data():
    record = {'role': {'ordinary': 'data'}, 'content': json.dumps(large_record())}
    request = {'one': record, 'two': record}
    assert compact(restore_payload(encode_request(request))) == compact(request)


def test_nonbeneficial_deep_copy_paths_do_not_inflate_the_request():
    record = large_record()
    request = {'one': record, 'two': record, 'a' * 1500: 'x' * 600, 'b' * 1500: 'x' * 600}
    assert compact(restore_payload(encode_request(request))) == compact(request)


def test_circular_input_remains_invalid():
    value = {}
    value['self'] = value
    with pytest.raises(ValueError, match='input'):
        encode_request(value)


def test_literal_suffix_and_json_string_values_are_not_mistaken_for_frames():
    from council.graph_integrity import _MARKER
    guidance = 'literal prefix' + _MARKER + 'not JSON ' * 70000
    request = {'guidance': guidance, 'copy': guidance}
    assert compact(restore_payload(encode_request(request))) == compact(request)
    content = json.dumps('x' * 630000)
    request = {'messages': [{'role': 'user', 'content': content}, {'role': 'assistant', 'content': content}]}
    assert compact(restore_payload(encode_request(request))) == compact(request)


def test_ambiguous_serialized_keys_fail_closed_instead_of_losing_a_value():
    record = large_record()
    with pytest.raises(ValueError, match='input'):
        encode_request({1: record, '1': record})
