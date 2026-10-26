"""Finite JSON parser facts, never rejected model content or field names."""
import json

MAX_BYTES = 4 * 1024 * 1024
REASONS = frozenset({'EMPTY', 'MARKDOWN_FENCE', 'INVALID_ESCAPE', 'CONTROL_CHARACTER',
    'UNTERMINATED_STRING', 'TRAILING_DATA', 'DUPLICATE_KEY', 'NONFINITE_NUMBER',
    'INVALID_ENCODING', 'SYNTAX_ERROR'})


def from_error(text, error):
    data = text if isinstance(text, bytes) else text.encode('utf-8', errors='replace')
    stripped = data.strip()
    reason = 'SYNTAX_ERROR'
    if not stripped:
        reason = 'EMPTY'
    elif stripped.startswith(b'```'):
        reason = 'MARKDOWN_FENCE'
    elif isinstance(error, UnicodeError):
        reason = 'INVALID_ENCODING'
    elif isinstance(error, json.JSONDecodeError):
        reason = next((kind for prefix, kind in (
            ('Invalid \\escape', 'INVALID_ESCAPE'), ('Invalid control character', 'CONTROL_CHARACTER'),
            ('Unterminated string', 'UNTERMINATED_STRING'), ('Extra data', 'TRAILING_DATA'))
            if error.msg.startswith(prefix)), reason)
    elif type(error) is ValueError:
        reason = {'Duplicate JSON key': 'DUPLICATE_KEY',
                  'Invalid JSON constant': 'NONFINITE_NUMBER'}.get(str(error), reason)
    decoded = isinstance(error, json.JSONDecodeError)
    return {'reason': reason, 'response_bytes': min(len(data), MAX_BYTES),
            'line': error.lineno if decoded else None,
            'column': error.colno if decoded else None,
            'position': error.pos if decoded else None}


def safe_detail(value):
    if (type(value) is not dict or set(value) != {'reason', 'response_bytes', 'line', 'column', 'position'}
            or type(value['reason']) is not str or value['reason'] not in REASONS
            or type(value['response_bytes']) is not int or not 0 <= value['response_bytes'] <= MAX_BYTES):
        return None
    for key, minimum in (('line', 1), ('column', 1), ('position', 0)):
        if value[key] is not None and (type(value[key]) is not int or not minimum <= value[key] <= MAX_BYTES + 1):
            return None
    return dict(value)
