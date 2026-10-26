"""Bounded schema corrections without rejected inputs or arbitrary field names."""

FIELDS = frozenset({'response','unknown_field','run_id','artifact','base_sha256','edits',
    'op','path','value','value_json','reason_ids','after_id','title','architecture_summary',
    'phases','tasks','id','goal','affected_services','required_inputs','delivered_contracts',
    'acceptance_outcomes','depends_on','final_acceptance','kind','readiness_for','specialist',
    'description','target_files','acceptance_criteria','test_commands','working_directory',
    'verification_phase','red_verification','status','test_files','expected_failures',
    'green_task_id','assertion_names','solution_architecture','executables','executable_ids',
    'repository','contracts','producer_piece','consumer_pieces','version','definition',
    'open_questions','owner_piece','assumption','integration_strategy','contract_changes','base_version','reason',
    'quality_gates','phase','task_ids','out_of_scope_reason','baseline_challenges','delivery_stage',
    'proof_scope','project','generated_inputs','runtime_mutable','baseline_id','requirement_id',
    'evidence_refs','consequence','replacement_statement','replacement_source_refs'})
GUIDANCE = {
    'field_missing': 'Include the required field.',
    'field_unexpected': 'Remove the unexpected field; use only fields in the supplied schema.',
    'string_required': 'Use a JSON string at this field.',
    'integer_required': 'Use a JSON integer at this field.',
    'number_required': 'Use a finite JSON number at this field.',
    'boolean_required': 'Use a JSON boolean at this field.',
    'array_required': 'Use a JSON array at this field.',
    'object_required': 'Use a JSON object at this field.',
    'choice_invalid': 'Use one of the literal choices in the supplied schema.',
    'bounds_invalid': 'Follow the field length, count, or numeric limits in the supplied schema.',
    'pattern_invalid': 'Follow the field pattern in the supplied schema.',
    'json_value_invalid': 'Use finite native JSON only, at most 32 levels and 65536 UTF-8 bytes per value.',
    'schema_invalid': 'Correct this field using the supplied schema.',
    'quality_gate_scope_invalid': 'Use either nonempty unique task_ids or an explicit out_of_scope_reason, never both or neither.',
}
_REASONS = {
    'missing':'field_missing', 'extra_forbidden':'field_unexpected',
    'string_type':'string_required', 'int_type':'integer_required',
    'float_type':'number_required', 'finite_number':'number_required',
    'bool_type':'boolean_required', 'list_type':'array_required',
    'dict_type':'object_required', 'model_type':'object_required',
    'literal_error':'choice_invalid', 'string_pattern_mismatch':'pattern_invalid',
    'revision_json_value':'json_value_invalid',
    **{name:'bounds_invalid' for name in ('too_short','too_long','string_too_short',
        'string_too_long','greater_than','greater_than_equal','less_than','less_than_equal')},
}


def safe_detail(value):
    if (type(value) is not dict or set(value) != {'reason','field_path','edit_index'}
            or type(value['reason']) is not str or value['reason'] not in GUIDANCE
            or type(value['field_path']) is not list or not 1 <= len(value['field_path']) <= 12
            or any(not ((type(p) is str and p in FIELDS) or
                (type(p) is int and 0 <= p < 100000)) for p in value['field_path'])
            or (value['edit_index'] is not None and
                (type(value['edit_index']) is not int or not 1 <= value['edit_index'] <= 64))):
        return None
    return {**value,'field_path':list(value['field_path'])}


def from_error(error):
    first = error.errors(include_input=False,include_context=False,include_url=False)[0]
    path = []
    for part in first['loc'][:12]:
        if type(part) is int and 0 <= part < 100000:
            path.append(part)
        else:
            path.append(part if type(part) is str and part in FIELDS else 'unknown_field')
    edit_index = (path[1]+1 if len(path)>1 and path[0]=='edits'
        and type(path[1]) is int and path[1]<64 else None)
    reason=_REASONS.get(first['type'],'schema_invalid')
    if first['type']=='value_error' and len(first['loc'])==2 and first['loc'][0]=='quality_gates':
        reason='quality_gate_scope_invalid'
    return {'reason':reason,
        'field_path':path or ['response'],'edit_index':edit_index}


def correction(value):
    detail = safe_detail(value)
    if detail is None:
        return None
    path = ''
    for part in detail['field_path']:
        path += f'[{part}]' if type(part) is int else ('.' if path else '')+part
    return {'field':path,'guidance':GUIDANCE[detail['reason']]}
