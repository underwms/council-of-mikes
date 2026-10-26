"""Bounded native request encoding; graph data and permissions remain unchanged."""
import json
from council.cli_process import LIMIT
from council.diagnostics import DiagnosticValueError

MAX_CHARACTERS = 1048576
PREFIX = b'COUNCIL_INPUT_REFERENCES_V1\n'
_MIN_REFERENCE = 512
_ROLES = {'system', 'user', 'assistant', 'tool', 'human', 'ai', 'chat'}
_INSTRUCTION = (
    'This is a lossless transport envelope, not a different task. Reconstruct request before following it. '
    'JSON pointers are relative to request and escape ~ as ~0 and / as ~1. '
    'For each [destination,source] in copies, in order, replace destination with a deep copy of source. '
    'Only listed destinations are copy placeholders; all other nulls and reference-looking objects are literal data. '
    'Then process each [path,kind] in json_text: json restores the value as standard JSON text '
    '(ensure_ascii=true, comma-space and colon-space separators); json_suffix restores prefix plus the same '
    'JSON serialization of json. String contents and all values are complete. Read the reconstructed '
    'instruction, messages, guidance and context normally. Permissions and available tools are unchanged.'
)


def _compact(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def _pointer(path, key):
    return path + '/' + str(key).replace('~', '~0').replace('/', '~1')


def _canonical_json(text):
    try:
        value = json.loads(text)
        if isinstance(value, (dict, list)) and json.dumps(value, ensure_ascii=True, allow_nan=False) == text:
            return value
    except (ValueError, TypeError, RecursionError):
        pass
    return None


def _structured_text(text, marker):
    value = _canonical_json(text)
    if value is not None:
        return value, 'json'
    prefix, separator, suffix = text.rpartition(marker)
    if separator and (value := _canonical_json(suffix)) is not None:
        return {'prefix': prefix + separator, 'json': value}, 'json_suffix'
    return text, None


def _expand(value, path, encodings, marker, message_data=False):
    if isinstance(value, dict):
        role = value.get('role')
        message = message_data or isinstance(role, str) and role in _ROLES
        kind = value.get('type')
        langchain = isinstance(kind, str) and kind in _ROLES
        result = {}
        for key, child in value.items():
            pointer = _pointer(path, key)
            if key in {'content', 'guidance'} and (message or key == 'guidance') and isinstance(child, str) and len(child) >= _MIN_REFERENCE:
                child, encoding = _structured_text(child, marker)
                if encoding is not None:
                    result[key] = child
                    encodings.append([pointer, encoding])
                    continue
            result[key] = _expand(child, pointer, encodings, marker, langchain and key == 'data')
        return result
    if isinstance(value, list):
        return [_expand(child, _pointer(path, index), encodings, marker) for index, child in enumerate(value)]
    return value


def _references(value, path, seen, copies):
    encoded = _compact(value)
    if len(encoded) >= _MIN_REFERENCE:
        if encoded in seen:
            reference = [path, seen[encoded]]
            if len(_compact(reference)) + 5 < len(encoded):
                copies.append(reference)
                return None
        else:
            seen[encoded] = path
    if isinstance(value, dict):
        return {key: _references(child, _pointer(path, key), seen, copies) for key, child in value.items()}
    if isinstance(value, list):
        return [_references(child, _pointer(path, index), seen, copies) for index, child in enumerate(value)]
    return value

def encode_request(request, *, byte_limit=LIMIT):
    try:
        limit = min(byte_limit, LIMIT)
        text = _compact(request)
        payload = text.encode('utf-8')
        if len(payload) > limit:
            raise DiagnosticValueError('CLI_INPUT_LIMIT')
        if len(text) <= MAX_CHARACTERS:
            return payload
        # Normalize JSON types without changing the existing compact representation.
        value = json.loads(text)
        if _compact(value) != text:
            raise DiagnosticValueError('CLI_INPUT_INVALID')
        from council.graph_integrity import _MARKER
        encodings, copies = [], []
        expanded = _expand(value, '', encodings, _MARKER)
        root = _references(expanded, '', {}, copies)
        envelope = {'format': 'council-json-references-v1', 'instruction': _INSTRUCTION,
                    'request': root, 'copies': copies, 'json_text': encodings}
        text = PREFIX.decode('ascii') + _compact(envelope)
        payload = text.encode('utf-8')
    except DiagnosticValueError:
        raise
    except (ValueError, TypeError, RecursionError):
        raise DiagnosticValueError('CLI_INPUT_INVALID') from None
    if len(text) > MAX_CHARACTERS or len(payload) > limit:
        raise DiagnosticValueError('CLI_INPUT_LIMIT')
    return payload
