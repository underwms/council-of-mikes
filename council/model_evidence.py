"""Bounded provider call evidence. Never serialize prompts, content, or errors."""
from datetime import datetime, timezone
import os
import re

from council.config import PROVIDER_KEYS, RunModelConfiguration
from council.diagnostics import describe, safe_error_type
from council.call_policy import gemini_deadline, STRUCTURED_OPERATIONS

_IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}\Z')
_TOKEN_FIELDS = {'input_tokens': ('input_tokens', 'prompt_tokens'),
                 'output_tokens': ('output_tokens', 'completion_tokens'),
                 'total_tokens': ('total_tokens',)}
_TOKEN_FIELDS['cached_input_tokens'] = ('cached_input_tokens',)


def _identifier(value):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        return None
    if value.lower().startswith(('sk-', 'aiza', 'bearer')):
        return None
    if any(secret and secret in value for key in PROVIDER_KEYS.values()
           if (secret := os.environ.get(key))):
        return None
    return value


def _openai_response_id(value):
    # AIMessage.id may be an lc_run framework ID rather than a provider ID.
    return value if isinstance(value, str) and value.startswith(('resp_', 'chatcmpl-')) else None


def _metadata_response(response):
    if isinstance(response, dict):
        if 'raw' in response:
            return response['raw']
        if 'messages' in response:
            return next((message for message in reversed(response['messages'])
                         if getattr(message, 'type', None) == 'ai'), None)
    return response


def _usage(response, metadata):
    """Only nonnegative integer token counts from known SDK fields survive."""
    sources = [getattr(response, 'usage_metadata', None), metadata.get('token_usage'),
               metadata.get('usage')]
    if isinstance(metadata.get('reported_usage'),dict):
        sources = [metadata['reported_usage']]
    result = {}
    for output, alternatives in _TOKEN_FIELDS.items():
        for source in sources:
            if not isinstance(source, dict):
                continue
            value = next((source[name] for name in alternatives if name in source), None)
            if type(value) is int and 0 <= value <= 10**12:
                result[output] = value
                break
    return result


def build_call_record(configuration, role, operation, response=None, error=None):
    """Extract allowlisted metadata, leaving absent provider facts unknown."""
    resolved = RunModelConfiguration.model_validate(configuration)
    if role not in resolved.roles:
        raise ValueError('Unknown Council role')
    selected = resolved.roles[role]
    result = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'role': role,
        'operation': _identifier(operation) or 'unknown',
        'provider': selected.provider,
        'requested_model': _identifier(selected.model),
        'settings': dict(selected.settings),
        'status': 'failed' if error is not None else 'succeeded',
        'usage': {},
    }
    if selected.provider == 'gemini-cli':
        result['effective_timeout_seconds'] = gemini_deadline(selected.settings,
            structured=operation.removesuffix('_transport_retry') in STRUCTURED_OPERATIONS)
    elif selected.provider == 'codex-cli':
        result['effective_timeout_seconds'] = selected.settings['timeout_seconds']
    if error is not None:
        result['error_type'] = safe_error_type(error)
        result['diagnostic'] = describe(error)
    raw = error if error is not None else _metadata_response(response)
    metadata = getattr(raw, 'response_metadata', {})
    if not isinstance(metadata, dict):
        metadata = {}
    if selected.provider in {'gemini-cli', 'codex-cli'}:
        result['transport'] = selected.provider
        version = _identifier(metadata.get('cli_version'))
        if version is not None:
            result['cli_version'] = version
        reported_model = _identifier(metadata.get('cli_reported_model'))
        if reported_model is not None:
            result['cli_reported_model'] = reported_model
        if selected.provider == 'codex-cli':
            for count_field in ('cli_warning_count', 'cli_failed_item_count', 'cli_declined_command_count'):
                count = metadata.get(count_field)
                if type(count) is int and 0 < count <= 1000:
                    result[count_field] = count
            thread_id = _identifier(metadata.get('cli_thread_id'))
            if thread_id is not None:
                result['cli_thread_id'] = thread_id
    headers = metadata.get('headers', {})
    if not isinstance(headers, dict):
        headers = {}
    candidates = {
        'returned_model': (metadata.get('model_name'), metadata.get('model'), metadata.get('model_version')),
        'request_id': (metadata.get('request_id'), metadata.get('_request_id'), headers.get('x-request-id')),
        'response_id': (_openai_response_id(metadata.get('id')), metadata.get('response_id'),
                        _openai_response_id(getattr(raw, 'id', None))),
    }
    for field, values in candidates.items():
        value = next((safe for candidate in values if (safe := _identifier(candidate)) is not None), None)
        if value is not None:
            result[field] = value
    result['usage'] = _usage(raw, metadata)
    return result
