"""Version-one private observations; explanatory projections never control execution."""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import statistics

IDENTITY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z')
TOKEN_FIELDS = ('input_tokens', 'output_tokens', 'total_tokens', 'cached_input_tokens')
TERMINALS = {'COMPLETED','FAILED','STOPPED','INTERRUPTED'}
STATUSES = TERMINALS | {'START','EXECUTING','TESTING','RETRYING','PLAN_BLOCKED','REQUIREMENTS_WAITING',
    'REQUIREMENTS_DRAFT','START_PLANNING','PLAN_PHASE','PLAN_REVIEW','PLAN_REVISION','ROADMAP_REVIEW',
    'ROADMAP_REVISION','GOVERNOR','GATEKEEPER_AUDIT','FINAL_REVIEW','RECOVERY_NEEDED','RECOVERY_ADMIT','RECOVERY_DISPATCH'}
STATUSES |= {'PROOF_REFRESH','PROOF_REVIEW'}
GROUP_DIMENSIONS = {'role','operation','provider','requested_model','reported_model'}


def safe_comparison(value):
    if not isinstance(value,dict):
        return {}
    result={}
    for key in ('engine_graph_sha256','requirements_sha256','accepted_plan_sha256','obligations_sha256'):
        item=value.get(key)
        result[key]=item if isinstance(item,str) and re.fullmatch('[a-f0-9]{64}',item) else None
    item=value.get('distribution_version')
    result['distribution_version']=item if isinstance(item,str) and re.fullmatch('[0-9][A-Za-z0-9.+-]{0,63}',item) else None
    result['policy']={key:version for key in ('orchestration','integrity','governance','recovery')
        if type(version:=(value.get('policy') or {}).get(key)) is int and 0<=version<=4} if isinstance(value.get('policy'),dict) else {}
    roles={}
    for role,settings in (value.get('roles') or {}).items() if isinstance(value.get('roles'),dict) else []:
        if role in {'orchestrator','coder','investigator','reviewer'} and isinstance(settings,dict):
            roles[role]=accounting(settings)
    result['roles']=roles
    return result


def comparison_context(state):
    from importlib.metadata import version,PackageNotFoundError
    from council.graph_integrity import digest, command_digest
    try:
        installed=version('council-orchestrator')
    except (PackageNotFoundError,OSError,ValueError):
        installed=None
    try:
        graph_sha256=hashlib.sha256(Path(__file__).with_name('graph.py').read_bytes()).hexdigest()
    except OSError:
        graph_sha256=None
    return safe_comparison({'distribution_version':installed,
        'engine_graph_sha256':graph_sha256,
        'requirements_sha256':state.requirements.approved_sha256,
        'accepted_plan_sha256':state.accepted_plan_sha256,
        'obligations_sha256':digest([state.accepted_plan_sha256,
            [command_digest(t,i) for t in state.plan.tasks for i in range(1,len(t.test_commands)+1)]]) if state.plan and state.accepted_plan_sha256 else None,
        'policy':{'orchestration':state.orchestration_policy_version,'integrity':state.graph_integrity_policy_version,
            'governance':state.governance_policy_version,'recovery':state.recovery_policy.version},
        'roles':{role:{'provider':settings['provider'],'requested_model':settings['model'],
            'configured_timeout_seconds':settings['settings'].get('timeout_seconds')}
            for role,settings in state.model_configuration.get('roles',{}).items()}})


def usage_summary(calls):
    coverage = {key:sum(key in c.get('usage',{}) for c in calls) for key in TOKEN_FIELDS}
    result = {f'reported_{key}':sum(c.get('usage',{}).get(key,0) for c in calls) if coverage[key] else None for key in TOKEN_FIELDS}
    result.update(field_attempt_counts=coverage,missing_attempts=sum(not c.get('usage') for c in calls),
        partial_attempts=sum(bool(c.get('usage')) and not all(k in c['usage'] for k in TOKEN_FIELDS[:3]) for c in calls),
        measured_attempts=sum(bool(c.get('usage')) for c in calls))
    return result


def accounting(value):
    if not isinstance(value, dict):
        return {}
    from council.model_evidence import _identifier
    output = {}
    for key in ('requested_model','returned_model','cli_reported_model','provider','operation','role'):
        safe = _identifier(value.get(key))
        if safe is not None:
            output[key] = safe
    output['usage'] = {key:count for key in TOKEN_FIELDS
        if type(count := (value.get('usage') or {}).get(key)) is int and 0 <= count <= 10**12} if isinstance(value.get('usage'),dict) else {}
    for key in ('duration_seconds','effective_timeout_seconds','configured_timeout_seconds','request_bytes'):
        count = value.get(key)
        if type(count) in (int,float) and math.isfinite(count) and 0 <= count <= 10**12:
            output[key] = count
    return output


def measurement(value):
    if not isinstance(value, dict):
        return {}
    output = {}
    for key in ('execution_id', 'command_sha256'):
        if isinstance(value.get(key), str) and re.fullmatch('[a-f0-9]{64}',value[key]):
            output[key] = value[key]
    for key in ('started_utc','ended_utc'):
        if _timestamp(value.get(key)):
            output[key] = value[key]
    count = value.get('duration_seconds')
    if type(count) in (int,float) and math.isfinite(count) and 0 <= count <= 10**9:
        output['duration_seconds'] = count
    if value.get('completion') in {'completed','incomplete'}:
        output['completion'] = value['completion']
    return output


def _timestamp(value):
    try:
        return isinstance(value,str) and len(value)<=40 and datetime.fromisoformat(value).utcoffset().total_seconds()==0
    except (ValueError, AttributeError, TypeError):
        return False


def safe_event(value):
    from council.diagnostics import _EVENTS, _STAGES, _ROLES, _OPERATIONS, CATALOG
    if not isinstance(value,dict) or value.get('event') not in _EVENTS or not _timestamp(value.get('timestamp')):
        raise ValueError('Unsupported observation event')
    output = {'timestamp':value['timestamp'], 'event':value['event'],
        'stage':value.get('stage') if value.get('stage') in _STAGES else 'runtime'}
    for key, allowed in (('role',_ROLES),('operation',_OPERATIONS),('code',CATALOG),('run_status',STATUSES)):
        if isinstance(value.get(key),str) and value[key] in allowed:
            output[key] = value[key]
    for key in ('call','task_index','command_index','phase_index'):
        if type(value.get(key)) is int and 0 <= value[key] <= 100000:
            output[key] = value[key]
    if type(value.get('elapsed_seconds')) in (int,float) and math.isfinite(value['elapsed_seconds']) and 0<=value['elapsed_seconds']<=10**9:
        output['elapsed_seconds']=value['elapsed_seconds']
    for key in ('functional_complete','pr_ready'):
        if type(value.get(key)) is bool:
            output[key] = value[key]
    if 'accounting' in value:
        output['accounting'] = accounting(value['accounting'])
    if 'measurement' in value:
        output['measurement'] = measurement(value['measurement'])
    if 'comparison' in value:
        output['comparison']=safe_comparison(value['comparison'])
    from council.diagnostics import safe_recovery
    recovery = value.get('recovery')
    if isinstance(recovery,dict):
        recovery = safe_recovery({k:v for k,v in recovery.items() if k!='message'})
        if recovery:
            output['recovery'] = recovery
    return output


def interpretation(event):
    name, stage = event['event'], event['stage']
    status = event.get('run_status')
    if event.get('code')=='DELIVERY_BOUNDARY_NOT_MET':
        return {'state':'quality_blocked','message':'Functional behavior is verified; required PR-readiness evidence remains unresolved.'}
    if status in TERMINALS:
        return {'state':status.lower(),'message':
            'Functional delivery completed; PR readiness follows separately recorded quality evidence.' if status=='COMPLETED'
            else 'Execution ended with its recorded outcome and limitations preserved.'}
    if name in {'approval_waiting','planning_blocked'} or status in {'PLAN_BLOCKED','REQUIREMENTS_WAITING'}:
        return {'state':'waiting_for_human','message':'Waiting for explicit human input; silence does not approve this gate.'}
    if name.startswith('recovery_'):
        recovery = event.get('recovery',{})
        return {'state':'recovering','message':recovery.get('message','A recovery event was recorded; recommendation and execution remain distinct.')}
    if (name=='node_finished' and stage=='worker') or (name=='delivery_state' and stage=='worker' and status=='TESTING'):
        return {'state':'verification_pending','message':'Coding turn finished; independent verification is pending.'}
    if name=='delivery_state' and stage=='prover' and status in {'EXECUTING','GATEKEEPER_AUDIT'}:
        return {'state':'verification_passed','message':'Independent task verification passed; phase and final delivery checks still apply.'}
    if name=='delivery_state' and stage=='arbiter':
        return {'state':'recovering','message':'Recovery was proposed; admission and actual execution are separate remaining steps.'}
    if name=='verification_finished':
        return {'state':'verification_recorded','message':'A verification command ended; acceptance is determined by its independent result.'}
    if name=='node_failed' and event.get('code')=='GRAPH_EVIDENCE_INVALID':
        return {'state':'stale_proof','message':'Execution proof is absent or stale; this alone does not establish a product defect.'}
    if name in {'runtime_failed','node_failed'}:
        return {'state':'failure_recorded','message':'A failure was recorded; subsequent recovery or a terminal outcome may follow.'}
    if name=='run_finished':
        return {'state':'session_ended','message':'This process session ended; run completion is not implied.'}
    return {'state':'recorded_activity','message':f'Recorded {stage} activity; next work depends on remaining checks.'}


class ObservationStore:
    def __init__(self, path):
        path = Path(path)
        for parent in (path,*path.parents):
            if parent.is_symlink() or getattr(parent,'is_junction',lambda:False)():
                raise OSError('Observation storage cannot traverse links')
        self.db = sqlite3.connect(path, timeout=0.1)
        self.db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS observation_meta(version INTEGER NOT NULL);
            INSERT INTO observation_meta SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM observation_meta);
            CREATE TABLE IF NOT EXISTS observation_sessions(
                generation INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                session_id TEXT NOT NULL, UNIQUE(run_id,session_id));
            CREATE TABLE IF NOT EXISTS observation_events(
                position INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                session_id TEXT NOT NULL, source_seq INTEGER NOT NULL, event_id TEXT NOT NULL UNIQUE,
                event TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(run_id,session_id,source_seq));
            CREATE INDEX IF NOT EXISTS observation_run_events ON observation_events(run_id,position);
        ''')
        if self.db.execute('SELECT version FROM observation_meta').fetchall() != [(1,)]:
            self.db.close()
            raise ValueError('Unsupported observation schema')

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.db.close()

    def open_session(self, run_id, session_id):
        if any(not isinstance(x,str) or not IDENTITY.fullmatch(x) for x in (run_id,session_id)):
            raise ValueError('Invalid observation identity')
        with self.db:
            if self.db.execute('SELECT COUNT(*) FROM observation_sessions').fetchone()[0] >= 1024:
                raise ValueError('Observation retention capacity reached')
            self.db.execute('INSERT OR IGNORE INTO observation_sessions(run_id,session_id) VALUES (?,?)',(run_id,session_id))

    def append(self, run_id, session_id, source_seq, value):
        if type(source_seq) is not int or not 1<=source_seq<=100000:
            raise ValueError('Invalid observation sequence')
        if not self.db.execute('SELECT 1 FROM observation_sessions WHERE run_id=? AND session_id=?',(run_id,session_id)).fetchone():
            raise ValueError('Unknown observation session')
        payload = json.dumps(safe_event(value),sort_keys=True,separators=(',',':'))
        event_id = hashlib.sha256(f'{run_id}:{session_id}:{source_seq}'.encode()).hexdigest()
        with self.db:
            prior = self.db.execute('SELECT payload FROM observation_events WHERE event_id=?',(event_id,)).fetchone()
            if prior:
                if prior[0]!=payload:
                    raise ValueError('Observation identity collision')
                return
            if (self.db.execute('SELECT COUNT(*) FROM observation_events WHERE run_id=?',(run_id,)).fetchone()[0]>=8192
                    or self.db.execute('SELECT COUNT(*) FROM observation_events').fetchone()[0]>=100000):
                raise ValueError('Observation retention capacity reached')
            self.db.execute('INSERT INTO observation_events(run_id,session_id,source_seq,event_id,event,payload) VALUES (?,?,?,?,?,?)',
                (run_id,session_id,source_seq,event_id,value['event'],payload))

    def page(self, run_id, kind='events', *, after=0, limit=100):
        filters = {'events':None,'milestones':('node_finished','node_failed','approval_waiting','planning_blocked','delivery_state','recovery_dispatched','recovery_resolved'),
            'calls':('call_succeeded','call_failed'),'commands':('verification_finished',),'sessions':None,'export':None}
        if kind not in filters or type(after) is not int or after<0 or type(limit) is not int or not 1<=limit<=200:
            raise ValueError('Invalid observation query')
        if kind=='sessions':
            rows = self.db.execute('SELECT generation,session_id FROM observation_sessions WHERE run_id=? AND generation>? ORDER BY generation LIMIT ?',
                (run_id,after,limit)).fetchall()
            return {'version':1,'items':[{'position':r[0],'session_id':r[1]} for r in rows], 'next_cursor':rows[-1][0] if rows else after}
        sql, args = 'SELECT position,e.session_id,source_seq,event_id,payload,s.generation FROM observation_events e JOIN observation_sessions s USING(run_id,session_id) WHERE e.run_id=? AND position>?', [run_id,after]
        if filters[kind]:
            sql += ' AND event IN ('+','.join('?' for _ in filters[kind])+')'
            args.extend(filters[kind])
        rows = self.db.execute(sql+' ORDER BY position LIMIT ?',[*args,limit]).fetchall()
        return {'version':1,'items':[{'position':r[0],'session_id':r[1],'source_seq':r[2],
            'session_generation':r[5], 'event_id':r[3], **json.loads(r[4]),'method':'event_derived',
            **({'explanation':interpretation(json.loads(r[4]))} if kind=='milestones' else {})} for r in rows],
            'next_cursor':rows[-1][0] if rows else after}

    def summary(self, run_id, *, group_by=None):
        if group_by is not None and group_by not in GROUP_DIMENSIONS:
            raise ValueError('Unsupported accounting dimension')
        rows = self.db.execute('SELECT e.payload FROM observation_events e JOIN observation_sessions s USING(run_id,session_id) WHERE e.run_id=? ORDER BY s.generation,e.source_seq LIMIT 8192',(run_id,)).fetchall()
        events = [json.loads(r[0]) for r in rows]
        waiting,waits={},[]
        for entry in events:
            if entry['event'] in {'approval_waiting','planning_blocked'}:
                waiting.setdefault(entry['stage'],entry['timestamp'])
            elif entry['event']=='human_input_received' and entry['stage'] in waiting:
                start=waiting.pop(entry['stage'])
                duration=(datetime.fromisoformat(entry['timestamp'])-datetime.fromisoformat(start)).total_seconds()
                if duration>=0:
                    waits.append(duration)
        # Session-end is not a stronger state than the last recorded delivery outcome.
        current = next((e for e in reversed(events) if e['event']!='run_finished'), events[-1] if events else None)
        calls = [e.get('accounting',{}) for e in events if e['event'] in {'call_succeeded','call_failed'}]
        durations = [c['duration_seconds'] for c in calls if 'duration_seconds' in c]
        usage = usage_summary(calls)
        grouped = {}
        for call in calls if group_by else []:
            key = (call.get('returned_model') or call.get('cli_reported_model')) if group_by=='reported_model' else call.get(group_by)
            grouped.setdefault(key,[]).append(call)
        groups = [{'value':key,'attempts':len(values),'usage':usage_summary(values)}
            for key,values in list(grouped.items())[:64]]
        return {'version':1,'run_id':run_id,'event_count':len(events),
            'current':{**interpretation(current),'timestamp':current['timestamp']} if current else None,
            'liveness':'unknown','coverage':'prospective_events_only' if events else 'unavailable',
            'usage':usage,'calls':{'count':len(calls),'duration_population':len(durations),
                'median_seconds':statistics.median(durations) if durations else None,
                'duration_semantics':'inclusive; do not add to node or command durations'},
            'wall_time_seconds':None,'unclassified_gaps':True,
            'human_wait_seconds':sum(waits) if waits else None,'completed_human_waits':len(waits),
            'unmatched_human_waits':len(waiting),
            'completed_session_durations_seconds':[e['elapsed_seconds'] for e in events
                if e['event']=='run_finished' and 'elapsed_seconds' in e],
            'history_capped':len(events)>=8192,
            'comparison':next((e['comparison'] for e in reversed(events) if 'comparison' in e),None),
            'group_by':group_by,'groups':groups,'groups_truncated':len(grouped)>64,
            'interpretation':{'method':'event_derived','model_enabled':False,'model_calls':0}}
