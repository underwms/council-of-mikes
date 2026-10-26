"""Narration worker lifecycle uses real SQLite and an inert provider boundary."""
import io
import json
import threading
from types import SimpleNamespace
import pytest
from test_narration import seed
from council.narration import NarrationQueue
from council import narration_worker as worker


def test_stopped_worker_drains_owned_job_without_graph_or_provider_calls(current_autonomous_run,monkeypatch):
    ctx=current_autonomous_run.fixture.context
    db=seed(ctx.memory_root/'observability.sqlite')
    queue=NarrationQueue(db);queue.enqueue('run','session',1,{'stage':'worker','task':'Implement requested feature'})
    db.close();seen=[]
    original=worker.process_job
    def process(job,q,owner,startup):
        def transport(argv,payload,timeout):
            seen.append(json.loads(payload)['job']['source_event_id'])
            return 0,json.dumps({'draft':{'message':'Working on the requested feature.','evidence_ids':[job['source_event_id']]},'accounting':{}}),'discarded'
        original(job,q,owner,startup,transport=transport)
    monkeypatch.setattr(worker,'process_job',process)
    stopped=threading.Event();stopped.set()
    startup={'runtime':{k:str(getattr(ctx,k)) for k in ('council_root','workspace_root','memory_root')},
        'configuration':current_autonomous_run.state['model_configuration']}
    worker.work(startup,'run','session',stopped)
    import sqlite3
    with sqlite3.connect(ctx.memory_root/'observability.sqlite') as db:
        assert db.execute('SELECT status,method FROM node_narrations').fetchall()==[('succeeded','model')]
        assert db.execute('SELECT count(*) FROM observation_events').fetchone()[0]==1
    assert len(seen)==1


@pytest.mark.parametrize('failed',[False,True])
def test_startup_uses_hidden_isolated_child_and_cleans_failed_pipe(current_autonomous_run,monkeypatch,failed):
    run=current_autonomous_run;seen={};terminated=[]
    class Pipe(io.BytesIO):
        def write(self,value):
            if failed:raise OSError('private transport failure')
            seen['payload']=value
            return super().write(value)
    process=SimpleNamespace(stdin=Pipe(),terminate=lambda:terminated.append(True))
    def popen(argv,**kwargs):seen.update(argv=argv,kwargs=kwargs);return process
    monkeypatch.setattr(worker.subprocess,'Popen',popen)
    if failed:
        with pytest.raises(OSError):worker.start_narrator(run.fixture.context,run.state['model_configuration'],'run','session')
        assert terminated==[True] and process.stdin.closed
    else:
        assert worker.start_narrator(run.fixture.context,run.state['model_configuration'],'run','session') is process
        assert seen['argv'][1:4]==['-I','-m','council.narration_worker']
        assert set(json.loads(seen['payload']))=={'configuration','runtime'}
        if worker.os.name=='nt':assert seen['kwargs']['creationflags']==worker.subprocess.CREATE_NO_WINDOW
        process.stdin.close()


@pytest.mark.parametrize('generation',[False,True])
def test_cli_input_limit_rejects_before_any_generation_or_startup(monkeypatch,generation):
    payload=b'x'*(32769 if generation else 16385)
    monkeypatch.setattr(worker.sys,'argv',['narration_worker',*(['--generate'] if generation else ['--run','run','--session','session'])])
    monkeypatch.setattr(worker.sys,'stdin',SimpleNamespace(buffer=io.BytesIO(payload)))
    def forbidden(*args,**kwargs):raise AssertionError('Oversized input must not reach model or worker startup')
    monkeypatch.setattr(worker,'generate',forbidden);monkeypatch.setattr(worker,'work',forbidden)
    assert worker.main()==1


def test_public_cli_binds_observer_without_creating_an_execution_stage(current_autonomous_run,monkeypatch):
    from council import cli
    from council.config import RunModelConfiguration
    from council.diagnostics import DiagnosticSession
    from council.narration_hooks import NodeNarrationCapture
    run=current_autonomous_run;seen=[]
    def invoke(state,configuration):
        assert len(configuration['callbacks'])==1
        observer=configuration['callbacks'][0]
        assert isinstance(observer,NodeNarrationCapture) and observer.session is session
        seen.append(state['readiness_policy_version'])
        return {**state,'status':'FAILED','error':'Inert CLI binding check'}
    monkeypatch.setattr(cli,'build_council_graph',lambda **kwargs:SimpleNamespace(invoke=invoke))
    monkeypatch.setattr(cli,'resolve_model_configuration',lambda **kwargs:RunModelConfiguration.model_validate(run.state['model_configuration']))
    monkeypatch.setattr(cli,'credentials_available',lambda configuration:True)
    monkeypatch.setattr(cli,'emit',lambda result:None)
    with DiagnosticSession('observer-binding',run.fixture.context.memory_root) as session:
        assert cli.run_council_task(prompt='Capture observer binding only',workspace_root=run.fixture.workspace,
            council_root=run.fixture.context.council_root,no_input=True,viewer=False)==1
    assert seen==[3]


def test_observer_and_shutdown_pipe_failures_do_not_change_recorded_execution(tmp_path):
    from council.diagnostics import DiagnosticSession
    def observer(*args):raise RuntimeError('PRIVATE_OBSERVER_CANARY')
    def close():raise OSError('PRIVATE_PIPE_CANARY')
    with DiagnosticSession('observation-only',tmp_path) as session:
        session._narration_observer=observer
        session._narrator=SimpleNamespace(stdin=SimpleNamespace(close=close))
        session.event('node_started',stage='worker')
        assert session.observations_status=='available'
        row=session.observations.db.execute("SELECT count(*) FROM observation_events WHERE event='node_started'").fetchone()
        assert row[0]==1
        path=session.path
    assert session.finished
    assert 'PRIVATE_' not in path.read_text()


@pytest.mark.parametrize('claim',['All tests passed.','Implementation is complete.'])
def test_generated_success_claims_cannot_replace_pending_execution_facts(tmp_path,claim):
    db=seed(tmp_path/'db.sqlite',event='call_succeeded',seq=2)
    # A source-linked node visit is required before the result can be narrated.
    from council.observability import ObservationStore
    with ObservationStore(tmp_path/'db.sqlite') as store:
        store.append('run','session',1,{'event':'node_started','stage':'worker','timestamp':'2026-10-26T16:00:00+00:00'})
    queue=NarrationQueue(db);queue.enqueue('run','session',2,{'stage':'worker','functional_complete':False})
    job=queue.claim('run','session','owner')
    with pytest.raises(ValueError):queue.finish(job,'owner',{'message':claim,'evidence_ids':[job['source_event_id']]})
    assert db.execute('SELECT count(*) FROM node_narrations').fetchone()[0]==0
    db.close()
