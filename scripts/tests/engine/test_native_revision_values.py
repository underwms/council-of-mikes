"""Native JSON edits, precise private correction, and bounded graph recovery."""
import io
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage

from council.document_edits import DocumentRevision, RevisionRejected, apply_revision
from council.phase_contract import Phase, PhaseRoadmap, roadmap_digest
from council.state import CouncilState, FindingLedgerEntry, MultiSpecialistPlan
from test_document_edits import edit_state, patch_for
from test_engine_integration import lifecycle, open_graph
from test_integrity_lifecycle import legacy_monolithic_integrity_setup, graph_for, frame_from, ACCEPT, REVISE, CLOSE
from test_gemini_cli import settings, output


def native_patch(state, kind='roadmap', value='Direct value', **change):
    proposal = patch_for(state, kind, **change)
    proposal['edits'][0].pop('value_json')
    proposal['edits'][0]['value'] = value
    return proposal


@pytest.mark.parametrize('value', ['Quotes: "a"\nWindows: C:\\temp\\data', '{"literal":true}', 'null'])
def test_native_strings_are_used_literally_and_untouched_requirements_survive(value):
    state = edit_state()
    result = apply_revision(state, native_patch(state, value=value), 'roadmap')
    assert result.phases[0].acceptance_outcomes == [*state.roadmap.phases[0].acceptance_outcomes, value]


def test_advertised_schema_requires_native_value_without_escaped_json():
    fields = DocumentRevision.model_json_schema()['$defs']['DocumentEdit']
    assert 'value' in fields['required']
    assert 'value_json' not in json.dumps(fields)


def test_native_phase_object_boolean_null_and_command_array_are_applied_atomically():
    state = edit_state()
    phase = Phase(id='readiness', goal='Build baseline', affected_services=['api'],
        delivered_contracts=['Ready'], acceptance_outcomes=['Existing build passes'])
    candidate = apply_revision(state, native_patch(state, value=phase.model_dump(mode='json'),
        path='/phases/readiness', after_id=''), 'roadmap')
    assert candidate.phases[0] == phase and candidate.phases[1] == state.roadmap.phases[0]
    proposal = native_patch(state, value=True, op='replace', path='/phases/fixture/final_acceptance')
    assert apply_revision(state, proposal, 'roadmap').phases[0].final_acceptance is True
    state = edit_state('plan')
    proposal = native_patch(state, 'plan', value=['python', '-c', 'print("literal")'],
        path='/tasks/seed/test_commands/-')
    assert apply_revision(state, proposal, 'plan').tasks[0].test_commands[-1] == proposal['edits'][0]['value']
    state.roadmap.phases[0].acceptance_outcomes.append('Remove only this')
    proposal = native_patch(state, value=None, op='remove', path='/phases/fixture/acceptance_outcomes/2')
    assert apply_revision(state, proposal, 'roadmap').phases[0].acceptance_outcomes == [
        'Save and assert baseline', 'Check coverage runner help']


@pytest.mark.parametrize('value', [float('nan'), float('inf'), ('tuple',), {1: 'key'}, {'x': object()}, 'x'*65537],
    ids=['nan','infinity','tuple','numeric-key','custom-object','oversized'])
def test_non_json_or_oversized_native_values_are_rejected_without_mutation(value):
    state = edit_state()
    before = state.roadmap.model_dump(mode='json')
    with pytest.raises(RevisionRejected):
        apply_revision(state, native_patch(state, value=value), 'roadmap')
    assert state.roadmap.model_dump(mode='json') == before


def test_deep_native_value_is_rejected_without_recursion_failure():
    value = 'leaf'
    for _ in range(40): value = [value]
    with pytest.raises(RevisionRejected):
        apply_revision(edit_state(), native_patch(edit_state(), value=value), 'roadmap')


def test_saved_legacy_edits_still_apply_but_ambiguous_dual_values_are_rejected():
    state = edit_state()
    assert apply_revision(state, patch_for(state), 'roadmap').phases[0].acceptance_outcomes[-1] == 'Assert three-snapshot batch'
    proposal = patch_for(state)
    proposal['edits'][0]['value'] = 'Ambiguous'
    with pytest.raises(RevisionRejected): apply_revision(state, proposal, 'roadmap')


def test_schema_feedback_identifies_missing_second_value_without_private_input():
    state = edit_state()
    proposal = native_patch(state)
    proposal['edits'].append({'op': 'add', 'path': '/phases/fixture/acceptance_outcomes/-',
        'reason_ids': ['F1']})
    with pytest.raises(RevisionRejected) as caught: apply_revision(state, proposal, 'roadmap')
    feedback = caught.value.feedback('roadmap')
    assert feedback['edit_index'] == 2
    assert feedback['schema']['field_path'] == ['edits', 1, 'value']
    assert feedback['schema']['reason'] == 'field_missing'


def test_candidate_type_feedback_names_the_rejected_field_not_its_value():
    state = edit_state()
    with pytest.raises(RevisionRejected) as caught:
        apply_revision(state, native_patch(state, value={'PRIVATE_VALUE': 'secret'},
            op='replace', path='/phases/fixture/goal'), 'roadmap')
    feedback = caught.value.feedback('roadmap')
    assert feedback['schema']['field_path'] == ['phases', 0, 'goal']
    assert feedback['schema']['reason'] == 'string_required'
    assert 'PRIVATE_VALUE' not in json.dumps(feedback)


def multifinding_proposal(state):
    state.roadmap_finding_ledger = [FindingLedgerEntry(id=f'F{i}', description=f'Contract {i}',
        kind='technical', status='unresolved') for i in range(1,8)]
    proposal = native_patch(state)
    proposal['edits'] = [
        {'op':'add','path':'/phases/fixture/acceptance_outcomes/-',
         'value':f'Contract {i}: sample "quoted" value at C:\\fixture\\{j}\nAssert real evidence.',
         'reason_ids':[f'F{i}']} for i in range(1,8) for j in range(3)]
    proposal['edits'].append({'op':'add','path':'/phases/readiness','after_id':'',
        'value':Phase(id='readiness',goal='Build established baseline',affected_services=['api'],
            delivered_contracts=['Working baseline'],acceptance_outcomes=['Build before implementation']).model_dump(mode='json'),
        'reason_ids':['F1']})
    return proposal


def test_multi_finding_revision_survives_actual_gemini_json_parsing(settings):
    from council.gemini_cli import GeminiCLIChatModel
    state = edit_state()
    proposal = multifinding_proposal(state)
    output(settings, {'response':json.dumps(proposal)})
    parsed = GeminiCLIChatModel('gemini-test',settings).with_structured_output(DocumentRevision).invoke([])
    result = apply_revision(state,parsed,'roadmap')
    assert len(parsed.edits) == 22
    assert result.phases[1].acceptance_outcomes[:2] == state.roadmap.phases[0].acceptance_outcomes
    assert len(result.phases[1].acceptance_outcomes) == 23


def test_gemini_schema_diagnostics_and_events_keep_only_safe_field_facts(settings,tmp_path):
    from council.gemini_cli import GeminiCLIChatModel
    from council.diagnostics import DiagnosticValueError, DiagnosticSession, describe
    state = edit_state()
    proposal = native_patch(state)
    proposal['edits'][0]['reason_ids'] = 'PRIVATE_VALUE'
    proposal['PRIVATE_UNKNOWN_FIELD'] = 'PRIVATE_VALUE'
    output(settings,{'response':json.dumps(proposal)})
    with DiagnosticSession('safe-schema',tmp_path) as session:
        with pytest.raises(DiagnosticValueError) as caught:
            GeminiCLIChatModel('gemini-test',settings).with_structured_output(DocumentRevision).invoke([])
        detail = describe(caught.value)
        session.event('call_failed',diagnostic=caught.value)
    assert detail['response_schema']['field_path'] == ['edits',0,'reason_ids']
    assert detail['response_schema']['reason'] == 'array_required'
    saved = session.path.read_text()
    assert 'response_schema' in saved
    assert 'PRIVATE_' not in saved and 'PRIVATE_' not in json.dumps(detail)


@pytest.mark.parametrize('always_invalid',[False,True])
@pytest.mark.parametrize('rejection',['local_schema','provider_schema','provider_json'])
def test_graph_corrects_schema_or_blocks_as_revision_failure_without_extra_reviews(lifecycle,monkeypatch,always_invalid,rejection):
    state,provider,reviewer = legacy_monolithic_integrity_setup(lifecycle,monkeypatch,[REVISE,CLOSE,ACCEPT])
    state['orchestration_policy_version']=2
    roadmap=edit_state().roadmap
    corrections=[]
    def structured(schema,**kwargs):
        def invoke(messages):
            frame=frame_from(messages)
            if schema is PhaseRoadmap: return roadmap
            if schema is MultiSpecialistPlan: return lifecycle.plan
            assert schema is DocumentRevision
            supplied=CouncilState(run_id=frame['run_id'],task_input='Synthetic feature',
                roadmap=PhaseRoadmap.model_validate(frame['records']['roadmap']))
            proposal=native_patch(supplied)
            contracts=[json.JSONDecoder().raw_decode(m['content'])[0] for m in messages if isinstance(m,dict)
                and isinstance(m.get('content'),str) and m['content'].startswith('{')]
            contract=next(c for c in contracts if 'active_reason_ids' in c)
            corrections.append(contract['correction'])
            assert not provider.attempts
            if always_invalid or len(corrections)==1:
                if rejection=='local_schema':
                    proposal['edits'][0].pop('value')
                else:
                    from council.diagnostics import DiagnosticValueError
                    if rejection=='provider_schema':
                        raise DiagnosticValueError('GEMINI_SCHEMA_INVALID',response_schema={
                            'reason':'field_missing','field_path':['edits',0,'value'],'edit_index':1})
                    raise DiagnosticValueError('GEMINI_RESPONSE_JSON_INVALID',response_json={
                        'reason':'SYNTAX_ERROR','response_bytes':100,'line':3,'column':5,'position':12})
            return proposal
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output=structured
    with open_graph(lifecycle,provider) as saver:
        result=graph_for(lifecycle,saver,provider,reviewer).invoke(state,lifecycle.config)
    assert len(corrections)>=2, result.get('diagnostic')
    if rejection=='provider_json':
        assert corrections[1]['reason']=='EDIT_JSON_INVALID'
        assert corrections[1]['response_json']['line']==3
    else:
        assert corrections[1]['schema']['field_path']==['edits',0,'value']
        assert corrections[1]['edit_index']==1
    if always_invalid:
        assert result['diagnostic']['code']=='REVISION_CONTRACT_EXHAUSTED'
        payload=result['__interrupt__'][0].value
        assert payload['blocker_kind']=='revision_contract'
        assert result['roadmap_review_count']==1 and result['roadmap_revision_count']==3
        assert not provider.attempts
    else:
        assert result['status']=='COMPLETED',result.get('diagnostic')
        assert result['roadmap_revision_count']==2 and result['roadmap_review_count']==2
        assert result['last_document_revision'] is None  # phase startup clears prior draft metadata
        assert result['roadmap']['phases'][0]['acceptance_outcomes'][-1]=='Direct value'


def test_terminal_names_revision_failure_before_previous_review_findings():
    from council.cli import emit
    from test_console_cues import Terminal
    output_stream,errors=io.StringIO(),Terminal()
    payload={'status':'BLOCKED','blocker_kind':'revision_contract',
        'diagnostic':{'code':'REVISION_CONTRACT_EXHAUSTED','message':'Revision contract correction budget exhausted.'},
        'document_revision_feedback':{'artifact':'roadmap','reason':'EDIT_SCHEMA_INVALID','edit_index':2,
            'schema':{'reason':'field_missing','field_path':['edits',1,'value'],'edit_index':2}},
        'finding_ledger':[{'id':'F1','status':'unresolved','description':'Previous finding'}]}
    with patch('sys.stdout',output_stream),patch('sys.stderr',errors): emit(payload)
    assert 'Revision contract' in errors.getvalue()
    assert 'edits[1].value' in errors.getvalue()
    assert 'Open issues from last completed review' in errors.getvalue()
    assert errors.getvalue().index('Revision contract')<errors.getvalue().index('Previous finding')
    assert json.loads(output_stream.getvalue())==payload


@pytest.mark.parametrize('mutation',['unknown-field','bad-index','unknown-reason','extra-input','bool-index'])
def test_untrusted_schema_facts_are_dropped_at_diagnostic_boundaries(mutation):
    from council.diagnostics import DiagnosticValueError,describe
    from council.review_feedback import sanitize_diagnostic
    detail={'reason':'field_missing','field_path':['edits',0,'value'],'edit_index':1}
    if mutation=='unknown-field': detail['field_path']=['PRIVATE_UNKNOWN']
    if mutation=='bad-index': detail['edit_index']=100000
    if mutation=='unknown-reason': detail['reason']='PRIVATE_REASON'
    if mutation=='extra-input': detail['input']='PRIVATE_INPUT'
    if mutation=='bool-index': detail['field_path']=['edits',True,'value']
    assert 'response_schema' not in describe(DiagnosticValueError('GEMINI_SCHEMA_INVALID',response_schema=detail))
    assert 'response_schema' not in sanitize_diagnostic({'code':'GEMINI_SCHEMA_INVALID','response_schema':detail})


def test_total_edit_bytes_and_mutated_model_values_are_revalidated():
    state=edit_state()
    proposal=native_patch(state,value='x'*65500)
    proposal['edits']=[dict(proposal['edits'][0]) for _ in range(9)]
    with pytest.raises(RevisionRejected) as caught: apply_revision(state,proposal,'roadmap')
    assert caught.value.reason=='EDIT_LIMIT'
    parsed=DocumentRevision.model_validate(native_patch(state))
    parsed.edits[0].value=float('nan')
    with pytest.raises(RevisionRejected): apply_revision(state,parsed,'roadmap')


def test_unknown_provider_field_name_is_replaced_with_fixed_sentinel():
    state=edit_state()
    proposal=native_patch(state)
    proposal['edits'][0]['PRIVATE_FIELD']='PRIVATE_VALUE'
    with pytest.raises(RevisionRejected) as caught: apply_revision(state,proposal,'roadmap')
    feedback=caught.value.feedback('roadmap')
    assert feedback['schema']['field_path']==['edits',0,'unknown_field']
    assert feedback['schema']['reason']=='field_unexpected'
    assert 'PRIVATE_' not in json.dumps(feedback)


@pytest.mark.parametrize('value',[0,1.25,False,None,{'array':[1,True,None,'literal']}])
def test_native_json_schema_preserves_supported_scalar_and_nested_types(value):
    parsed=DocumentRevision.model_validate(native_patch(edit_state(),value=value))
    assert parsed.edits[0].value==value
    assert type(parsed.edits[0].value) is type(value)


def test_terminal_reports_finite_json_parser_location_without_payload():
    from council.cli import emit
    from test_console_cues import Terminal
    errors=Terminal()
    with patch('sys.stdout',io.StringIO()),patch('sys.stderr',errors):
        emit({'status':'BLOCKED','blocker_kind':'revision_contract','diagnostic':{},
            'document_revision_feedback':{'response_json':{
                'reason':'SYNTAX_ERROR','response_bytes':100,'line':3,'column':5,'position':12}}})
    assert 'JSON SYNTAX_ERROR, line 3, column 5' in errors.getvalue()


@pytest.mark.parametrize('flow',['plan_correct','plan_exhaust','strategy_correct'])
def test_phase_plan_and_strategy_schema_failures_use_the_same_bounded_correction(lifecycle,monkeypatch,flow):
    decisions=[REVISE,REVISE,REVISE,CLOSE] if flow=='strategy_correct' else [REVISE,CLOSE]
    state,provider,reviewer=legacy_monolithic_integrity_setup(lifecycle,monkeypatch,decisions)
    original=provider.with_structured_output
    corrections=[]
    def structured(schema,**kwargs):
        if schema is not DocumentRevision: return original(schema,**kwargs)
        def invoke(messages):
            frame=frame_from(messages)
            plan=MultiSpecialistPlan.model_validate(frame['records']['plan'])
            contracts=[json.JSONDecoder().raw_decode(m['content'])[0] for m in messages if isinstance(m,dict)
                and isinstance(m.get('content'),str) and m['content'].startswith('{')]
            corrections.append(next(c for c in contracts if 'active_reason_ids' in c)['correction'])
            index=len(corrections)
            fails=(flow=='plan_exhaust' or index==(3 if flow=='strategy_correct' else 1))
            if fails:
                from council.diagnostics import DiagnosticValueError
                raise DiagnosticValueError('GEMINI_SCHEMA_INVALID',response_schema={
                    'reason':'array_required','field_path':['edits',0,'reason_ids'],'edit_index':1})
            supplied=CouncilState(run_id=frame['run_id'],task_input='Synthetic feature',plan=plan)
            return native_patch(supplied,'plan',value=f'Additional acceptance proof {index}',
                path='/tasks/task-1/acceptance_criteria/-')
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output=structured
    with open_graph(lifecycle,provider) as saver:
        result=graph_for(lifecycle,saver,provider,reviewer).invoke(state,lifecycle.config)
    if flow=='plan_exhaust':
        assert result['status']=='PLAN_BLOCKED'
        assert result['diagnostic']['code']=='REVISION_CONTRACT_EXHAUSTED'
        assert result['plan_revision_count']==5 and result['plan_review_count']==1  # existing monolithic policy
        assert not provider.attempts
    else:
        assert result['status']=='COMPLETED',result.get('diagnostic')
        correction=corrections[3 if flow=='strategy_correct' else 1]
        assert correction['schema']['field_path']==['edits',0,'reason_ids']
        assert result['strategy_reset_count']==int(flow=='strategy_correct')
        assert result['plan']['tasks'][0]['test_commands']==lifecycle.plan.tasks[0].test_commands
        assert result['plan']['tasks'][0]['acceptance_criteria'][0]=='Verification exits zero'


def test_safe_schema_diagnostic_survives_output_sanitization():
    from council.review_feedback import sanitize_diagnostic
    detail={'reason':'field_missing','field_path':['edits',0,'value'],'edit_index':1}
    assert sanitize_diagnostic({'code':'GEMINI_SCHEMA_INVALID','response_schema':detail})['response_schema']==detail


def test_invalid_legacy_type_and_final_phase_contract_keep_the_previous_document():
    state=edit_state()
    proposal=patch_for(state,value_json=123)
    with pytest.raises(RevisionRejected): apply_revision(state,proposal,'roadmap')
    proposal=native_patch(state,value=False,op='replace',path='/phases/fixture/final_acceptance')
    with pytest.raises(RevisionRejected): apply_revision(state,proposal,'roadmap')
    assert state.roadmap.phases[0].final_acceptance is True
