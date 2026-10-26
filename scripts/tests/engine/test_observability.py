"""Prospective accounting stays bounded, idempotent and separate from admission."""
import json
import pytest


def fact(event='call_succeeded', **kwargs):
    return {'timestamp':'2026-10-25T18:00:00+00:00', 'event':event,
        'stage':'model', 'call':1, **kwargs}


def test_replay_delayed_events_and_restart_preserve_causal_status(tmp_path):
    from council.observability import ObservationStore
    path = tmp_path/'observations.sqlite'
    with ObservationStore(path) as store:
        store.open_session('run', 'session-a')
        store.append('run', 'session-a', 2, fact('node_finished', stage='worker'))
        store.append('run', 'session-a', 1, fact('node_started', stage='worker'))
        store.append('run', 'session-a', 2, fact('node_finished', stage='worker'))
        summary = store.summary('run')
        assert summary['current']['message'] == 'Coding turn finished; independent verification is pending.'
        assert summary['event_count'] == 2
        assert summary['liveness'] == 'unknown'
        store.open_session('run', 'session-b')
        store.append('run','session-b',1,fact('approval_waiting',stage='requirements_gate'))
        store.append('run','session-a',3,fact('node_started',stage='prover'))
        assert store.summary('run')['current']['state'] == 'waiting_for_human'
    with ObservationStore(path) as store:
        events = store.page('run', 'events', limit=2)
        assert len(events['items']) == 2
        assert store.page('run','events',after=events['next_cursor'],limit=2)['items']


def test_partial_missing_failed_usage_and_nested_durations_are_honest(tmp_path):
    from council.observability import ObservationStore
    with ObservationStore(tmp_path/'observations.sqlite') as store:
        store.open_session('run','s')
        store.append('run','s',1,fact('call_failed', accounting={
            'usage':{'input_tokens':10}, 'duration_seconds':3.0,
            'requested_model':'model-a', 'provider':'codex-cli', 'prompt':'secret'}))
        store.append('run','s',2,fact('call_succeeded', call=2, accounting={
            'usage':{'input_tokens':20,'output_tokens':5,'total_tokens':27},'duration_seconds':2.0}))
        store.append('run','s',3,fact('call_failed', call=3, accounting={}))
        summary = store.summary('run')
        assert summary['usage']['reported_input_tokens'] == 30
        assert summary['usage']['reported_total_tokens'] == 27
        assert summary['usage']['partial_attempts'] == 1
        assert summary['usage']['missing_attempts'] == 1
        assert summary['calls']['count'] == 3
        assert summary['calls']['median_seconds'] == 2.5
        assert summary['wall_time_seconds'] is None
        assert 'secret' not in json.dumps(store.page('run','calls'))
        assert summary['calls']['duration_semantics'] == 'inclusive; do not add to node or command durations'


def test_event_payloads_reject_identity_collisions_and_strip_sensitive_data(tmp_path):
    from council.observability import ObservationStore
    with ObservationStore(tmp_path/'observations.sqlite') as store:
        store.open_session('run','s')
        store.append('run','s',1,fact(prompt='PRIVATE', exception='PRIVATE', path='C:/PRIVATE',
            accounting={'usage':{'input_tokens':True,'total_tokens':-1},'raw':'PRIVATE'}))
        assert 'PRIVATE' not in json.dumps(store.page('run','events'))
        with pytest.raises(ValueError):
            store.append('run','s',1,fact('call_failed'))
        with pytest.raises(ValueError):
            store.page('run','events',limit=201)


def test_grouped_usage_keeps_missing_reported_model_separate(tmp_path):
    from council.observability import ObservationStore
    with ObservationStore(tmp_path/'observations.sqlite') as store:
        store.open_session('run','s')
        store.append('run','s',1,fact(accounting={'requested_model':'requested','role':'coder',
            'usage':{'input_tokens':4},'duration_seconds':1.0}))
        store.append('run','s',2,fact(call=2,accounting={'requested_model':'requested','role':'reviewer',
            'cli_reported_model':'reported','usage':{'output_tokens':2}}))
        grouped = store.summary('run',group_by='reported_model')
        assert {g['value'] for g in grouped['groups']}=={None,'reported'}
        unknown = next(g for g in grouped['groups'] if g['value'] is None)
        assert unknown['usage']['reported_total_tokens'] is None
        with pytest.raises(ValueError):
            store.summary('run',group_by='prompt')


def test_human_wait_requires_explicit_endpoints_across_sessions(tmp_path):
    from council.observability import ObservationStore
    with ObservationStore(tmp_path/'observations.sqlite') as store:
        store.open_session('run','first')
        store.append('run','first',1,fact('approval_waiting',stage='requirements_gate'))
        store.open_session('run','second')
        store.append('run','second',1,fact('run_started',timestamp='2026-10-25T18:01:00+00:00'))
        assert store.summary('run')['human_wait_seconds'] is None
        store.append('run','second',2,fact('human_input_received',stage='requirements_gate',timestamp='2026-10-25T18:02:00+00:00'))
        summary=store.summary('run')
        assert summary['human_wait_seconds']==120.0
        assert summary['unclassified_gaps'] is True


def test_progress_distinguishes_functional_delivery_from_blocked_quality_boundary(tmp_path):
    from council.observability import ObservationStore
    with ObservationStore(tmp_path/'observations.sqlite') as store:
        store.open_session('run','s')
        store.append('run','s',1,fact('node_failed',stage='final_review',code='DELIVERY_BOUNDARY_NOT_MET'))
        assert store.summary('run')['current']['state']=='quality_blocked'


def test_failed_attempt_retains_available_usage(current_autonomous_run):
    from council.model_evidence import build_call_record
    error = RuntimeError('private error')
    error.usage_metadata = {'input_tokens':8}
    error.response_metadata = {'cli_reported_model':'reported-model'}
    record = build_call_record(current_autonomous_run.state['model_configuration'], 'coder','worker',error=error)
    assert record['usage'] == {'input_tokens':8}
    assert record['cli_reported_model']=='reported-model'


def test_diagnostic_session_persists_safe_call_and_command_measurements(current_autonomous_run):
    from council.diagnostics import DiagnosticSession
    from council.checkpoint import managed_sqlite_checkpointer
    from council.observability import ObservationStore
    run = current_autonomous_run
    with DiagnosticSession(run.state['run_id'],run.fixture.context.memory_root):
        with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
            result = run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED'
    path = run.fixture.context.memory_root/'observability.sqlite'
    assert path.exists()
    with ObservationStore(path) as store:
        commands = store.page(run.state['run_id'],'commands')['items']
        assert len(commands)==3
        assert all(c['measurement']['duration_seconds']>=0 and c['measurement']['completion']=='completed' for c in commands)
        assert len({c['measurement']['execution_id'] for c in commands})==3
        assert {c['measurement']['execution_id'] for c in commands} == {r['id'] for r in result['execution_records']}
        assert store.summary(run.state['run_id'])['calls']['count']==len(result['model_calls'])
        nodes = [e for e in store.page(run.state['run_id'],'events',limit=200)['items'] if e['event']=='node_finished']
        assert nodes and all(e['measurement']['duration_seconds']>=0 for e in nodes)
        comparison=store.summary(run.state['run_id'])['comparison']
        assert comparison['accepted_plan_sha256']==result['accepted_plan_sha256']
        assert len(comparison['engine_graph_sha256'])==64


def test_configured_native_reviewer_supports_finished_content_schema(current_autonomous_run, monkeypatch):
    from council.config import get_llm_for_role
    from council.codex_chat import CodexCLIChatModel
    reviewer = get_llm_for_role('reviewer',current_autonomous_run.state['model_configuration'],
        context=current_autonomous_run.fixture.context)
    seen = []
    monkeypatch.setattr(CodexCLIChatModel,'invoke',lambda self,messages:seen.append((self.model,messages)) or {'parsed':{}})
    assert reviewer.review_finished([{'role':'user','content':'private full diff'}])=={'parsed':{}}
    assert seen[0][0]==current_autonomous_run.state['model_configuration']['roles']['reviewer']['model']


def test_native_reported_counts_do_not_invent_provider_total(current_autonomous_run):
    from council.codex_cli import _parse
    from council.model_evidence import build_call_record
    from test_codex_cli import completed
    raw = _parse('\n'.join(json.dumps(e) for e in completed()).encode(),
        current_autonomous_run.fixture.workspace,current_autonomous_run.fixture.workspace)
    record = build_call_record(current_autonomous_run.state['model_configuration'],'coder','worker',response=raw)
    assert record['usage'] == {'input_tokens':3,'output_tokens':2,'cached_input_tokens':1}
