"""Narration is an observer: durable, grounded and separate from task execution."""
import json
import sqlite3
import pytest
from council.narration import NarrationQueue, narration_context, validate_draft


def seed(path, event='node_started', stage='worker', seq=1):
    from council.observability import ObservationStore
    with ObservationStore(path) as store:
        store.open_session('run','session')
        store.append('run','session',seq,{'event':event,'stage':stage,'timestamp':'2026-10-26T16:00:00+00:00'})
    return sqlite3.connect(path)


def test_queue_deduplicates_sources_and_lease_fences_competing_workers(tmp_path):
    db=seed(tmp_path/'db.sqlite')
    queue=NarrationQueue(db)
    queue.enqueue('run','session',1,{'stage':'worker','task':'Build the readiness fixture'})
    queue.enqueue('run','session',1,{'stage':'worker','task':'Build the readiness fixture'})
    job=queue.claim('run','session','worker-a',now=100)
    assert job['stage']=='worker' and job['visit_id']==job['source_event_id']
    assert queue.claim('run','session','worker-b',now=101) is None
    assert not queue.finish(job,'worker-b',{'message':'Implementing the readiness fixture.','evidence_ids':[job['source_event_id']]},now=102)
    assert queue.finish(job,'worker-a',{'message':'Implementing the readiness fixture.','evidence_ids':[job['source_event_id']]},now=102)
    assert queue.claim('run','session','worker-a',now=103) is None
    assert db.execute('SELECT count(*) FROM node_narrations').fetchone()[0]==1
    db.close()


def test_context_extracts_structured_facts_without_raw_results_or_secrets():
    from types import SimpleNamespace as S
    state=S(current_task_index=0,plan=S(tasks=[S(description='Check API readiness',kind='readiness')]),
        roadmap=None,current_phase_index=0,status='TESTING',test_results=[{'passed':False,'stdout':'PRIVATE','exception':'secret'}],
        delivery_result={'functional_complete':False,'pr_ready':False},plan_review_findings=['private'],roadmap_review_findings=[])
    context=narration_context(state,'prover')
    assert context['task']=='Check API readiness'
    assert context['verification_failed']==1
    assert 'PRIVATE' not in json.dumps(context) and 'secret' not in json.dumps(context) and 'private' not in json.dumps(context)


def test_generated_readiness_and_verification_claims_require_evidence():
    job={'source_event_id':'a'*64,'context':{'stage':'worker','event':'call_succeeded','state':'verification_pending','pr_ready':False}}
    with pytest.raises(ValueError):
        validate_draft({'message':'All tests passed and the change is ready to merge.','evidence_ids':['a'*64]},job)
    with pytest.raises(ValueError):
        validate_draft({'message':'Implementing the fixture.','evidence_ids':['b'*64]},job)
    assert validate_draft({'message':'The coding turn returned; verification is still pending.','evidence_ids':['a'*64]},job)


def test_failed_narration_uses_stored_fallback_without_changing_source(tmp_path):
    db=seed(tmp_path/'db.sqlite')
    queue=NarrationQueue(db)
    queue.enqueue('run','session',1,{'stage':'worker'})
    job=queue.claim('run','session','a',now=100)
    queue.fail(job,'a','generation_failed',now=101)
    row=db.execute('SELECT method,status,message FROM node_narrations').fetchone()
    assert row[0:2]==('event_derived','failed') and row[2]
    assert db.execute('SELECT reason FROM node_narration_failures').fetchone()[0]=='generation_failed'
    assert db.execute('SELECT count(*) FROM observation_events').fetchone()[0]==1
    db.close()


def test_expired_lease_recovers_once_and_fences_old_worker(tmp_path):
    db=seed(tmp_path/'db.sqlite');q=NarrationQueue(db)
    q.enqueue('run','session',1,{'stage':'worker'})
    first=q.claim('run','session','first',now=1)
    second=q.claim('run','session','second',now=92)
    draft={'message':'Working on the task.','evidence_ids':[first['source_event_id']]}
    assert second['attempts']==2
    assert not q.finish(first,'first',draft,now=93)
    assert q.claim('run','session','third',now=183) is None
    assert db.execute('SELECT status FROM node_narrations').fetchone()[0]=='failed'
    db.close()


def test_model_worker_uses_bounded_child_and_persists_separate_accounting(tmp_path):
    from council.narration_worker import process_job
    db=seed(tmp_path/'db.sqlite');q=NarrationQueue(db)
    q.enqueue('run','session',1,{'stage':'worker'})
    job=q.claim('run','session','a')
    def transport(argv,payload,timeout):
        assert argv[-1]=='--generate' and timeout==60
        request=json.loads(payload)
        assert set(request['job'])=={'source_event_id','context'}
        return 0,json.dumps({'draft':{'message':'Implementing the fixture.','evidence_ids':[job['source_event_id']]},
            'accounting':{'provider':'codex-cli','operation':'node_narration','usage':{'input_tokens':12},'raw':'PRIVATE'}}).encode(),b''
    process_job(job,q,'a',{},transport=transport)
    row=db.execute('SELECT method,accounting FROM node_narrations').fetchone()
    assert row[0]=='model' and json.loads(row[1])['usage']['input_tokens']==12
    assert 'PRIVATE' not in row[1]
    assert db.execute('SELECT count(*) FROM observation_events').fetchone()[0]==1
    db.close()


def test_callback_captures_result_without_graph_modifications(tmp_path,monkeypatch):
    from types import SimpleNamespace as S
    from council.diagnostics import DiagnosticSession
    from council.narration_hooks import NodeNarrationCapture
    import council.narration_worker as worker
    monkeypatch.setenv('COUNCIL_NARRATION_ENABLED','1')
    closed=[]
    monkeypatch.setattr(worker,'start_narrator',lambda *a:S(stdin=S(close=lambda:closed.append(True))))
    with DiagnosticSession('run',tmp_path) as session:
        capture=NodeNarrationCapture(None,session)
        inputs={'model_configuration':{'roles':{}},'plan':{'tasks':[{'description':'Check readiness','kind':'readiness'}]},'current_task_index':0}
        capture.on_chain_start(None,inputs,run_id='visit',name='worker',metadata={'langgraph_node':'worker'})
        session.event('node_started',stage='worker')
        session.event('call_started',stage='model',call=1)
        session.event('node_finished',stage='worker')
        session.event('delivery_state',stage='worker',run_status='TESTING')
        capture.on_chain_end({**inputs,'current_task_index':1},run_id='visit')
        rows=session.observations.db.execute("SELECT context FROM node_narration_jobs WHERE status='pending'").fetchall()
        assert len(rows)==1
        assert json.loads(rows[0][0])['task']=='Check readiness'
        assert json.loads(rows[0][0])['state']=='verification_pending'
    assert closed==[True]


def test_real_langgraph_callbacks_publish_jobs_without_affecting_results(current_autonomous_run,monkeypatch):
    from types import SimpleNamespace as S
    from council.diagnostics import DiagnosticSession
    from council.checkpoint import managed_sqlite_checkpointer
    from council.narration_hooks import NodeNarrationCapture
    import council.narration_worker as worker
    monkeypatch.setenv('COUNCIL_NARRATION_ENABLED','1')
    monkeypatch.setattr(worker,'start_narrator',lambda *a:S(stdin=S(close=lambda:None)))
    run=current_autonomous_run
    with DiagnosticSession(run.state['run_id'],run.fixture.context.memory_root) as session:
        handler=NodeNarrationCapture(run.fixture.context,session)
        with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
            result=run.build(saver).invoke(run.state,{**run.fixture.config,'callbacks':[handler]})
        assert result['status']=='COMPLETED'
        jobs=session.observations.db.execute('SELECT stage,context,visit_id FROM node_narration_jobs').fetchall()
        assert {'worker','prover','architect'} <= {r[0] for r in jobs}
        assert all(len(r[2])==64 for r in jobs)
        assert any('Implement unique integration target' in r[1] for r in jobs if r[0]=='worker')


def test_context_redacts_sensitive_task_text_and_preserves_only_finite_outcome_facts():
    context=narration_context({'plan':{'tasks':[{'description':'password=PRIVATE customer@example.com','kind':'readiness'}]},'current_task_index':0,
        'test_results':[{'passed':False,'expectation_met':False,'verification_reason':'COMMAND_CONTRACT_INVALID','stdout':'PRIVATE'}],
        'diagnostic':{'code':'READINESS_FAILED','raw':'PRIVATE'},'recovery_incident':{'decision':{'action':'replan','reason':'PRIVATE'}}},'prover')
    assert 'task' not in context and 'PRIVATE' not in json.dumps(context)
    assert context['last_check_expectation_met'] is False
    assert context['failure_code']=='READINESS_FAILED'
    assert context['recovery_action']=='replan'


@pytest.mark.parametrize('failure',[None,'timeout','invalid'])
def test_generation_is_tool_free_and_failures_are_only_narration_facts(current_autonomous_run,monkeypatch,failure):
    from council.narration_worker import generate
    from council.narration import NarrationDraft
    from langchain_core.messages import AIMessage
    run=current_autonomous_run;seen=[]
    class Provider:
        def with_structured_output(self,schema,include_raw):
            assert schema is NarrationDraft and include_raw
            return self
        def invoke(self,messages):
            seen.append(messages)
            if failure=='timeout':raise TimeoutError('PRIVATE')
            draft=NarrationDraft(message='All tests passed.' if failure=='invalid' else 'Implementing the readiness fixture.',evidence_ids=['a'*64])
            return {'parsed':draft,'parsing_error':None,'raw':AIMessage(content='PRIVATE',usage_metadata={'input_tokens':10,'output_tokens':5,'total_tokens':15})}
    monkeypatch.setattr('council.config.get_llm_for_role',lambda role,configuration,context:Provider())
    request={'configuration':run.state['model_configuration'],'runtime':{k:str(getattr(run.fixture.context,k)) for k in ('workspace_root','council_root','memory_root')},
        'job':{'source_event_id':'a'*64,'context':{'stage':'worker','state':'running','task':'Readiness fixture'}}}
    result=generate(request)
    assert 'PRIVATE' not in json.dumps(result)
    if failure:
        assert result['error']=='generation_failed'
        if failure=='invalid':assert result['accounting']['usage']['total_tokens']==15
    else:assert result['accounting']['usage']['total_tokens']==15
    assert len(seen)==1 and 'No tools' in seen[0][0]['content']


def test_observer_start_failure_cannot_block_a_real_graph(current_autonomous_run,monkeypatch):
    from council.diagnostics import DiagnosticSession
    from council.checkpoint import managed_sqlite_checkpointer
    from council.narration_hooks import NodeNarrationCapture
    monkeypatch.setenv('COUNCIL_NARRATION_ENABLED','1')
    def fail(*args):raise OSError('PRIVATE')
    monkeypatch.setattr('council.narration_worker.start_narrator',fail)
    run=current_autonomous_run
    with DiagnosticSession(run.state['run_id'],run.fixture.context.memory_root) as session:
        capture=NodeNarrationCapture(run.fixture.context,session)
        with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
            result=run.build(saver).invoke(run.state,{**run.fixture.config,'callbacks':[capture]})
        assert result['status']=='COMPLETED' and capture.launches==3


def test_concurrent_duplicate_enqueue_keeps_one_pending_job(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    path=tmp_path/'db.sqlite';db=seed(path);NarrationQueue(db);db.close();barrier=Barrier(2)
    def enqueue():
        connection=sqlite3.connect(path,timeout=2);queue=NarrationQueue(connection);barrier.wait()
        queue.enqueue('run','session',1,{'stage':'worker'});connection.close()
    with ThreadPoolExecutor(max_workers=2) as executor:list(executor.map(lambda _:enqueue(),range(2)))
    with sqlite3.connect(path) as connection:assert connection.execute('SELECT status FROM node_narration_jobs').fetchall()==[('pending',)]


def test_narrator_launcher_uses_hidden_isolated_child_and_bounded_configuration(current_autonomous_run,monkeypatch):
    from types import SimpleNamespace as S
    import io
    from council.narration_worker import start_narrator
    calls=[];pipe=io.BytesIO();process=S(stdin=pipe,terminate=lambda:None)
    monkeypatch.setattr('council.narration_worker.subprocess.Popen',lambda argv,**kwargs:calls.append((argv,kwargs)) or process)
    run=current_autonomous_run
    assert start_narrator(run.fixture.context,run.state['model_configuration'],'run','session') is process
    assert calls[0][0][1:4]==['-I','-m','council.narration_worker']
    assert calls[0][1]['creationflags']>=0
    assert len(pipe.getvalue())<16384
    assert json.loads(pipe.getvalue())['configuration']==run.state['model_configuration']


def test_worker_drains_durable_jobs_without_graph_calls(current_autonomous_run,monkeypatch):
    from threading import Event
    from council.observability import ObservationStore
    import council.narration_worker as worker
    run=current_autonomous_run;root=run.fixture.context.memory_root;stopped=Event()
    with ObservationStore(root/'observability.sqlite') as store:
        store.open_session('run','session')
        store.append('run','session',1,{'event':'node_started','stage':'worker','timestamp':'2026-10-26T16:00:00+00:00'})
        NarrationQueue(store.db).enqueue('run','session',1,{'stage':'worker'})
    def generate(job,queue,owner,startup):
        queue.finish(job,owner,{'message':'Implementing the assigned fixture.','evidence_ids':[job['source_event_id']]})
        stopped.set()
    monkeypatch.setattr(worker,'process_job',generate)
    worker.work({'configuration':run.state['model_configuration'],'runtime':{k:str(getattr(run.fixture.context,k)) for k in ('council_root','workspace_root','memory_root')}},'run','session',stopped)
    with sqlite3.connect(root/'observability.sqlite') as db:assert db.execute('SELECT method FROM node_narrations').fetchone()[0]=='model'


@pytest.mark.parametrize('mode',['generate','worker','oversize'])
def test_worker_entrypoint_is_bounded_and_does_not_open_a_graph(monkeypatch,capsys,mode):
    from types import SimpleNamespace as S
    import io,sys
    import council.narration_worker as worker
    calls=[]
    if mode=='generate':
        monkeypatch.setattr(sys,'argv',['narrator','--generate'])
        monkeypatch.setattr(sys,'stdin',S(buffer=io.BytesIO(b'{"sample":true}')))
        monkeypatch.setattr(worker,'generate',lambda value:{'test_result':value['sample']})
        assert worker.main()==0 and json.loads(capsys.readouterr().out)['test_result'] is True
    else:
        monkeypatch.setattr(sys,'argv',['narrator','--run','run','--session','session'])
        payload=b'x'*16385 if mode=='oversize' else b'{"configuration":{},"runtime":{}}\n'
        monkeypatch.setattr(sys,'stdin',S(buffer=io.BytesIO(payload)))
        monkeypatch.setattr(worker,'work',lambda startup,run,session,stopped:calls.append((run,session)))
        assert worker.main()==(1 if mode=='oversize' else 0)
        assert len(calls)==(0 if mode=='oversize' else 1)


@pytest.mark.parametrize('output',[b'not-json',b'{}'])
def test_bad_transport_returns_persisted_fallback_without_raw_error(tmp_path,output):
    from council.narration_worker import process_job
    db=seed(tmp_path/'db.sqlite');q=NarrationQueue(db);q.enqueue('run','session',1,{'stage':'worker'});job=q.claim('run','session','a')
    process_job(job,q,'a',{},transport=lambda *a,**k:(0,output,b'PRIVATE'))
    row=db.execute('SELECT status,message FROM node_narrations').fetchone()
    assert row[0]=='failed' and 'PRIVATE' not in row[1]
    db.close()
