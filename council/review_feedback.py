"""Finite reviewer rejection facts. Never serialize rejected values or error text."""

REASONS = {
    'CONTENT_MISSING': 'response', 'CONTENT_TYPE': 'response', 'CONTENT_LIMIT': 'response',
    'JSON_INVALID': 'response',
    'SCHEMA_INVALID': 'schema', 'SCHEMA_TYPE': 'schema', 'SCHEMA_FIELD': 'schema',
    'SCHEMA_BOUNDS': 'schema', 'SCHEMA_LITERAL': 'schema', 'SCHEMA_PATTERN': 'schema',
    'FINDING_BLANK': 'schema', 'DUPLICATE_FINDING_ID': 'schema',
    'DUPLICATE_RESOLVED_ID': 'schema', 'DECISION_FINDINGS_MISMATCH': 'schema',
    'ESCALATION_KIND_MISMATCH': 'schema',
    'UNKNOWN_RESOLVED_ID': 'ledger', 'OPEN_RESOLVED_CONFLICT': 'ledger',
    'MISSING_ACTIVE_ID': 'ledger', 'RESOLVED_ID_REUSED': 'ledger', 'LEDGER_LIMIT': 'ledger',
}
FIELDS = frozenset({'response', 'decision', 'findings', 'resolved_finding_ids',
                    'id', 'description', 'kind', 'ledger'})
_SCHEMA_REASONS = {
    'model_type': 'SCHEMA_TYPE', 'dict_type': 'SCHEMA_TYPE', 'list_type': 'SCHEMA_TYPE',
    'string_type': 'SCHEMA_TYPE', 'missing': 'SCHEMA_FIELD', 'extra_forbidden': 'SCHEMA_FIELD',
    'too_long': 'SCHEMA_BOUNDS', 'too_short': 'SCHEMA_BOUNDS',
    'string_too_long': 'SCHEMA_BOUNDS', 'string_too_short': 'SCHEMA_BOUNDS',
    'literal_error': 'SCHEMA_LITERAL', 'string_pattern_mismatch': 'SCHEMA_PATTERN',
    'review_finding_blank': 'FINDING_BLANK', 'review_finding_bounds': 'SCHEMA_BOUNDS',
    'review_duplicate_finding': 'DUPLICATE_FINDING_ID',
    'review_duplicate_resolved': 'DUPLICATE_RESOLVED_ID',
    'review_decision_findings': 'DECISION_FINDINGS_MISMATCH',
    'review_escalation_kind': 'ESCALATION_KIND_MISMATCH',
}


def safe_detail(value):
    if (type(value) is not dict or set(value) != {'reason', 'stage', 'field', 'index'}
            or type(value['reason']) is not str or value['reason'] not in REASONS
            or type(value['stage']) is not str or value['stage'] != REASONS[value['reason']]
            or type(value['field']) is not str or value['field'] not in FIELDS
            or (value['index'] is not None and
                (type(value['index']) is not int or not 1 <= value['index'] <= 100000))):
        return None
    return dict(value)


def reject(reason, *, field='response', index=None):
    from council.diagnostics import DiagnosticValueError
    raise DiagnosticValueError('PLAN_REVIEW_INVALID', review_decision={
        'reason': reason, 'stage': REASONS[reason], 'field': field, 'index': index}) from None


def reject_schema(error):
    # Only fixed type/location projections are used; input, context and message
    # may contain provider text and must never enter a diagnostic.
    first = error.errors(include_input=False, include_context=False, include_url=False)[0]
    reason = _SCHEMA_REASONS.get(first['type'], 'SCHEMA_INVALID')
    field, index = 'response', None
    for part in first['loc']:
        if type(part) is str and part in FIELDS:
            field = part
        elif type(part) is int and 0 <= part < 100000:
            index = part + 1
    reject(reason, field=field, index=index)


def sanitize_diagnostic(value):
    if not isinstance(value, dict):
        return value
    result = {key: item for key, item in value.items() if key not in {'review_decision','response_schema'}}
    detail = safe_detail(value.get('review_decision')) if value.get('code') == 'PLAN_REVIEW_INVALID' else None
    if detail is not None:
        result['review_decision'] = detail
    from council.schema_feedback import safe_detail as safe_schema_detail
    detail = safe_schema_detail(value.get('response_schema')) if value.get('code') in {'GEMINI_SCHEMA_INVALID','CODEX_SCHEMA_INVALID','PROPOSAL_FORMAT_INVALID'} else None
    if detail is not None:
        result['response_schema'] = detail
    return result
