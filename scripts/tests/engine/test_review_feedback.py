"""Finite reviewer rejection evidence; no rejected model text leaves validation."""
import json
from types import SimpleNamespace

import pytest
from langgraph.types import Command
from council.diagnostics import DiagnosticValueError, DiagnosticSession, describe
from council.plan_review import parse_review, reconcile_findings, blocked_payload, review_request
from council.state import CouncilState, FindingLedgerEntry, PlanReviewDecisionV2
from test_engine_integration import lifecycle, open_graph
from test_review_convergence import configured, decision, finding
from test_autonomous_review import graph_for


def rejected(content, version=2):
    with pytest.raises(DiagnosticValueError) as caught:
        parse_review(SimpleNamespace(content=content), version)
    return describe(caught.value)


@pytest.mark.parametrize('content,reason', [
    (None, 'CONTENT_TYPE'), ('x'*24001, 'CONTENT_LIMIT'),
    ('{PRIVATE_RESPONSE', 'JSON_INVALID'), ('[]', 'SCHEMA_TYPE'),
    ('{}', 'SCHEMA_FIELD'),
    (json.dumps(dict(decision(action='accept'), PRIVATE_KEY='PRIVATE_VALUE')), 'SCHEMA_FIELD'),
    (json.dumps(dict(decision(action='accept'), decision='unknown')), 'SCHEMA_LITERAL'),
    (json.dumps(decision('bad-id')), 'SCHEMA_PATTERN'),
    (json.dumps(decision('F1', 'F1')), 'DUPLICATE_FINDING_ID'),
    (json.dumps(decision('F1', resolved=['F2', 'F2'])), 'DUPLICATE_RESOLVED_ID'),
    (json.dumps(decision(action='revise')), 'DECISION_FINDINGS_MISMATCH'),
    (json.dumps(decision('F1', action='escalate')), 'ESCALATION_KIND_MISMATCH'),
    (json.dumps(dict(decision(), findings=[finding('F1', ' ')])), 'FINDING_BLANK'),
    (json.dumps(dict(decision(), findings=[finding('F1', 'x'*1001)])), 'SCHEMA_BOUNDS'),
    (json.dumps(dict(decision(), findings='PRIVATE_RESPONSE')), 'SCHEMA_TYPE'),
    (json.dumps(dict(decision(), findings=[finding(f'F{n}') for n in range(1,14)])), 'SCHEMA_BOUNDS'),
])
def test_parser_distinguishes_existing_failure_predicates(content, reason):
    detail = rejected(content)
    assert detail['code'] == 'PLAN_REVIEW_INVALID'
    assert detail.get('review_decision', {}).get('reason') == reason
    assert 'PRIVATE_' not in json.dumps(detail)


def test_missing_content_has_finite_reason():
    with pytest.raises(DiagnosticValueError) as caught:
        parse_review(SimpleNamespace(), 2)
    assert describe(caught.value).get('review_decision', {}).get('reason') == 'CONTENT_MISSING'


@pytest.mark.parametrize('content,reason', [
    ('x'*16001, 'CONTENT_LIMIT'),
    (json.dumps({'decision':'revise','findings':[' ']}), 'FINDING_BLANK'),
    (json.dumps({'decision':'revise','findings':['x'*1001]}), 'SCHEMA_BOUNDS'),
    (json.dumps({'decision':'accept','findings':['A finding']}), 'DECISION_FINDINGS_MISMATCH'),
])
def test_legacy_protocol_preserves_rejection_and_adds_detail(content, reason):
    assert rejected(content, 1).get('review_decision', {}).get('reason') == reason


@pytest.mark.parametrize('payload,reason', [
    (decision('F1',resolved=['F9']), 'UNKNOWN_RESOLVED_ID'),
    (decision('F1',resolved=['F1']), 'OPEN_RESOLVED_CONFLICT'),
    (decision('F3'), 'MISSING_ACTIVE_ID'),
    (decision('F2',resolved=['F1']), 'RESOLVED_ID_REUSED'),
])
def test_ledger_reasons_preserve_state_before_rejection(payload, reason, lifecycle):
    state = lifecycle.state
    state.plan = lifecycle.plan
    state.review_finding_ledger = [FindingLedgerEntry(**finding('F1'),status='unresolved'),
                                 FindingLedgerEntry(**finding('F2'),status='resolved')]
    before = state.model_dump(mode='json')
    with pytest.raises(DiagnosticValueError) as caught:
        reconcile_findings(state, PlanReviewDecisionV2.model_validate(payload))
    assert describe(caught.value).get('review_decision', {}).get('reason') == reason
    assert state.model_dump(mode='json') == before


def test_ledger_limit_reason_is_finite(lifecycle):
    state = lifecycle.state
    state.plan = lifecycle.plan
    state.review_finding_ledger = [FindingLedgerEntry(**finding(f'F{n}'), status='resolved') for n in range(1,73)]
    with pytest.raises(DiagnosticValueError) as caught:
        reconcile_findings(state, PlanReviewDecisionV2.model_validate(decision('F73')))
    assert describe(caught.value).get('review_decision', {}).get('reason') == 'LEDGER_LIMIT'


def valid_detail():
    return dict(reason='MISSING_ACTIVE_ID', stage='ledger', field='ledger', index=None)


@pytest.mark.parametrize('update', [
    {'reason':'PRIVATE_REASON'}, {'stage':'PRIVATE_STAGE'}, {'field':'PRIVATE_FIELD'},
    {'index':True}, {'index':0}, {'index':100001}, {'index':'1'},
    {'stage':'response'}, {'PRIVATE_KEY':'PRIVATE_VALUE'},
])
def test_untrusted_optional_detail_is_ignored(update):
    from council import review_feedback
    detail = {**valid_detail(), **update}
    assert review_feedback.safe_detail(detail) is None


def test_detail_revalidated_at_all_output_boundaries(lifecycle):
    error = DiagnosticValueError('PLAN_REVIEW_INVALID',review_decision=valid_detail())
    assert describe(error)['review_decision'] == valid_detail()
    error.review_decision['reason'] = 'PRIVATE_REASON'
    assert 'review_decision' not in describe(error)
    lifecycle.state.diagnostic = {**describe(error),'review_decision':{'PRIVATE_KEY':'PRIVATE_VALUE'}}
    assert 'PRIVATE_' not in json.dumps(blocked_payload(lifecycle.state)['diagnostic'])
    restored = CouncilState.model_validate(lifecycle.state.model_dump())
    assert 'review_decision' not in restored.diagnostic
    assert 'review_decision' not in describe(DiagnosticValueError('PLAN_VERIFICATION_INVALID',review_decision=valid_detail()))


@pytest.mark.parametrize('index', [None,1,100000])
def test_optional_detail_valid_index_bounds(index):
    from council import review_feedback
    detail = {**valid_detail(), 'index':index}
    assert review_feedback.safe_detail(detail) == detail


def test_graph_rejection_survives_restart_without_worker_or_retry(lifecycle,monkeypatch,capsys):
    state, provider, reviewer, _ = configured(lifecycle,monkeypatch,[decision('F1'),decision('F2')])
    with DiagnosticSession(lifecycle.state.run_id,lifecycle.context.memory_root) as session:
        with open_graph(lifecycle,provider) as saver:
            result = graph_for(lifecycle,saver,provider,reviewer).invoke(state,lifecycle.config)
        path = session.path
    assert result['diagnostic'].get('review_decision',{}).get('reason') == 'MISSING_ACTIVE_ID'
    assert result['plan_review_count'] == 2 and result['plan_revision_count'] == 1
    assert result['review_no_progress_count'] == 0
    assert result['accepted_plan_sha256'] is None and result['modified_files'] == []
    assert [(x['id'],x['status']) for x in result['review_finding_ledger']] == [('F1','unresolved')]
    assert not list(lifecycle.workspace.glob('target-*.txt'))
    with open_graph(lifecycle,provider) as saver:
        graph = graph_for(lifecycle,saver,provider,reviewer)
        saved = graph.get_state(lifecycle.config).values
        assert saved['diagnostic'] == result['diagnostic']
        again = graph.invoke(Command(resume={'approved':True}),lifecycle.config)
        assert again['diagnostic'] == result['diagnostic']
    assert reviewer.calls == 2
    records = [json.loads(line) for line in path.read_text().splitlines()]
    event = next(x for x in records if x['event']=='plan_review_rejected')
    assert event['review_decision'] == result['diagnostic']['review_decision']
    assert 'plan_review_rejected' in capsys.readouterr().err
    assert result['__interrupt__'][0].value['diagnostic'] == result['diagnostic']


def test_legacy_checkpoint_and_valid_decisions_remain_compatible(lifecycle):
    state = CouncilState.model_validate(lifecycle.state.model_dump())
    assert state.diagnostic is None
    for version,payload in [(1,{'decision':'accept','findings':[]}), (2,decision(action='accept'))]:
        assert parse_review(SimpleNamespace(content=json.dumps(payload)),version).decision == 'accept'


def test_review_contract_includes_carry_and_close_examples(lifecycle):
    lifecycle.state.plan = lifecycle.plan
    lifecycle.state.review_protocol_version = 2
    instruction = review_request(lifecycle.state,lifecycle.context)['instruction']
    assert 'resolved_finding_ids":["F1"]' in instruction
    assert '"id":"F2"' in instruction


@pytest.mark.parametrize('version,limit', [(1,16000),(2,24000)])
def test_exact_response_and_finding_bounds_remain_accepted(version,limit):
    payload = {'decision':'revise','findings':['x'*1000]*12} if version == 1 else decision(*[f'F{n}' for n in range(1,13)])
    content = json.dumps(payload)
    content += ' '*(limit-len(content))
    assert parse_review(SimpleNamespace(content=content),version).decision == 'revise'
    assert rejected(content+' ',version)['review_decision']['reason'] == 'CONTENT_LIMIT'


@pytest.mark.parametrize('value', [None,[], 'PRIVATE_VALUE', {},
    dict(reason=[],stage='ledger',field='ledger',index=None),
    dict(reason='MISSING_ACTIVE_ID',stage=[],field='ledger',index=None),
    dict(reason='MISSING_ACTIVE_ID',stage='ledger',field=[],index=None)])
def test_optional_detail_rejects_wrong_shapes_without_exception(value):
    from council.review_feedback import safe_detail
    assert safe_detail(value) is None


def test_schema_location_is_bounded_and_never_copies_unknown_keys():
    detail = rejected(json.dumps(dict(decision(),findings=[finding('F1',description='x'*1001)])))['review_decision']
    assert detail == dict(reason='SCHEMA_BOUNDS',stage='schema',field='description',index=1)
    unknown = rejected(json.dumps(dict(decision(action='accept'),PRIVATE_KEY='PRIVATE_VALUE')))['review_decision']
    assert unknown['field'] == 'response' and unknown['index'] is None


def test_json_duplicate_keys_and_nonfinite_numbers_remain_rejected():
    for content in ['{"decision":"accept","decision":"accept","findings":[]}',
                    '{"decision":NaN,"findings":[]}']:
        assert rejected(content)['review_decision']['reason'] == 'JSON_INVALID'


def test_schema_fallback_uses_only_finite_reason():
    from pydantic import BaseModel,ConfigDict,ValidationError
    from council.review_feedback import reject_schema
    class OtherSchema(BaseModel):
        model_config = ConfigDict(strict=True)
        number: int
    try:
        OtherSchema.model_validate({'number':'PRIVATE_VALUE'})
    except ValidationError as source:
        with pytest.raises(DiagnosticValueError) as caught:
            reject_schema(source)
    detail = describe(caught.value)
    assert detail['review_decision']['reason'] == 'SCHEMA_INVALID'
    assert 'PRIVATE_' not in json.dumps(detail)


def test_schema_rejected_event_never_exposes_rejected_content(lifecycle,monkeypatch,capsys):
    invalid=dict(decision(action='accept'),PRIVATE_KEY='PRIVATE_VALUE')
    state,provider,reviewer,_ = configured(lifecycle,monkeypatch,[invalid,invalid])
    with DiagnosticSession(lifecycle.state.run_id,lifecycle.context.memory_root) as session:
        with open_graph(lifecycle,provider) as saver:
            result = graph_for(lifecycle,saver,provider,reviewer).invoke(state,lifecycle.config)
        path = session.path
    assert result['diagnostic']['review_decision']['reason'] == 'SCHEMA_FIELD'
    assert result['plan_review_count'] == 1 and result['plan_revision_count'] == 0
    assert not list(lifecycle.workspace.glob('target-*.txt'))
    assert 'PRIVATE_' not in path.read_text() and 'PRIVATE_' not in capsys.readouterr().err
    assert 'plan_review_format_retry' in path.read_text()


def test_known_legacy_diagnostic_without_optional_detail_roundtrips(lifecycle):
    diagnostic = describe(DiagnosticValueError('PLAN_REVIEW_INVALID'))
    lifecycle.state.diagnostic = diagnostic
    assert CouncilState.model_validate(lifecycle.state.model_dump()).diagnostic == diagnostic
    assert blocked_payload(lifecycle.state)['diagnostic'] == diagnostic
