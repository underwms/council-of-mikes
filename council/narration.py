"""Durable, source-linked narration. These records never authorize execution."""
import json
import re
import time
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

EVENTS = {'node_started', 'node_finished', 'node_failed', 'approval_waiting',
          'planning_blocked', 'delivery_state', 'call_started', 'call_succeeded',
          'call_failed', 'verification_started', 'verification_finished',
          'recovery_dispatched', 'recovery_resolved'}
PRIVATE = re.compile(r'(?i)(?:https?://|[A-Z]:[\\/]|[\w.+-]+@[\w.-]+\.[a-z]{2,}|'
                     r'\b(?:sk-|ghp_|eyJ)[\w.-]{12,}|\b(?:password|secret|token|api.key)\s*[:=]|'
                     r'\b\d[\d ()+-]{8,}\d\b)')


def safe_text(value, limit=180):
    if not isinstance(value, str) or PRIVATE.search(value):
        return None
    return ' '.join(value.split())[:limit] or None


def _get(value, name, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def narration_context(state, stage):
    """Extract a small result contract, never free-form stdout or provider prose."""
    result = {'stage': stage}
    plan = _get(state, 'plan', None)
    index = _get(state, 'current_task_index', 0)
    if plan is not None and 0 <= index < len(_get(plan, 'tasks', [])):
        task = _get(plan, 'tasks', [])[index]
        result.update(task=safe_text(_get(task, 'description')), task_kind=_get(task, 'kind'))
    roadmap = _get(state, 'roadmap', None)
    phase = _get(state, 'current_phase_index', 0)
    if roadmap is not None and 0 <= phase < len(_get(roadmap, 'phases', [])):
        result['phase'] = safe_text(_get(_get(roadmap, 'phases', [])[phase], 'goal'))
    results = _get(state, 'test_results', [])[-64:]
    result['verification_passed'] = sum(r.get('expectation_met', r.get('passed')) is True for r in results)
    result['verification_failed'] = sum(r.get('expectation_met', r.get('passed')) is False for r in results)
    delivery = _get(state, 'delivery_result', {})
    for field in ('functional_complete', 'pr_ready'):
        if type(delivery.get(field)) is bool:
            result[field] = delivery[field]
    result['review_findings'] = min(24, len(_get(state, 'plan_review_findings', [])) +
                                    len(_get(state, 'roadmap_review_findings', [])))
    if results:
        latest = results[-1]
        met = latest.get('expectation_met', latest.get('passed'))
        if type(met) is bool:
            result['last_check_expectation_met'] = met
        reason = latest.get('verification_reason')
        if isinstance(reason, str) and re.fullmatch(r'[A-Z][A-Z_]{0,95}', reason):
            result['verification_reason'] = reason
    from council.diagnostics import CATALOG
    code = (_get(state, 'diagnostic') or {}).get('code')
    if code in CATALOG:
        result['failure_code'] = code
    incident = _get(state, 'recovery_incident')
    action = _get(_get(incident, 'decision'), 'action')
    if action in {'replan', 'repair', 'verify_partial', 'refresh_proofs', 'stop', 'human_input'}:
        result['recovery_action'] = action
    return {k: v for k, v in result.items() if v is not None}


class NarrationDraft(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    message: str = Field(min_length=1, max_length=320)
    evidence_ids: list[str] = Field(min_length=1, max_length=1)


def validate_draft(value, job):
    draft = NarrationDraft.model_validate(value, strict=True)
    if draft.evidence_ids != [job['source_event_id']] or not safe_text(draft.message, 320):
        raise ValueError('Narration has invalid evidence or private content')
    context = job['context']
    text = draft.message.lower()
    # Negative/pending statements must not be mistaken for positive proof claims.
    claims = re.sub(r'\b(?:not|never|no)\b[^.;]*|[^.;]*\b(?:pending|awaiting)\b[^.;]*', '', text)
    if re.search(r'ready (?:to merge|for (?:merge|release|production))|pr.ready', claims) and context.get('pr_ready') is not True:
        raise ValueError('Narration invented readiness')
    if re.search(r'(?:tests?|checks?|verification) (?:have |has )?(?:all )?(?:passed|succeeded)', claims):
        if context.get('state') not in {'verification_passed', 'completed'}:
            raise ValueError('Narration invented verification')
    if re.search(r'(?:work|implementation|delivery|task) (?:is |has )?(?:complete|completed|finished successfully)', claims):
        if context.get('functional_complete') is not True and context.get('state') != 'completed':
            raise ValueError('Narration invented completion')
    return safe_text(draft.message, 320)


def _dict(cursor):
    row = cursor.fetchone()
    return dict(zip((col[0] for col in cursor.description), row)) if row else None


class NarrationQueue:
    """Atomic claims and fenced publication; SQLite is owned by the caller's thread."""
    def __init__(self, db):
        self.db = db
        db.executescript('''
            CREATE TABLE IF NOT EXISTS node_narration_meta(version INTEGER NOT NULL);
            INSERT INTO node_narration_meta SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM node_narration_meta);
            CREATE TABLE IF NOT EXISTS node_narration_jobs(
                source_event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, session_id TEXT NOT NULL,
                stage TEXT NOT NULL, visit_id TEXT NOT NULL, source_position INTEGER NOT NULL,
                context TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                owner TEXT, lease_until REAL NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS narration_pending ON node_narration_jobs(run_id,session_id,status,source_position);
            CREATE TABLE IF NOT EXISTS node_narrations(
                position INTEGER PRIMARY KEY AUTOINCREMENT, source_event_id TEXT NOT NULL UNIQUE,
                run_id TEXT NOT NULL, session_id TEXT NOT NULL, stage TEXT NOT NULL, visit_id TEXT NOT NULL,
                source_position INTEGER NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL,
                method TEXT NOT NULL, generated_at TEXT NOT NULL, accounting TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS narration_run ON node_narrations(run_id,position);
            CREATE TABLE IF NOT EXISTS node_narration_failures(
                source_event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, reason TEXT NOT NULL);
        ''')
        if db.execute('SELECT version FROM node_narration_meta').fetchall() != [(1,)]:
            raise ValueError('Unsupported narration schema')

    def enqueue(self, run_id, session_id, seq, context):
        from council.observability import interpretation
        from council.diagnostics import _STAGES
        source = _dict(self.db.execute('SELECT * FROM observation_events WHERE run_id=? AND session_id=? AND source_seq=?',
                                      (run_id, session_id, seq)))
        if not source or source['event'] not in EVENTS:
            return
        event = json.loads(source['payload'])
        stage = event['stage'] if event['stage'] != 'model' else context.get('stage')
        if stage not in _STAGES or stage in {'runtime', 'model'}:
            return
        visit = self.db.execute("SELECT event_id FROM observation_events WHERE run_id=? AND session_id=? AND source_seq<=? "
                                "AND event='node_started' AND json_extract(payload,'$.stage')=? ORDER BY source_seq DESC LIMIT 1",
                                (run_id, session_id, seq, stage)).fetchone()
        if not visit:
            return
        safe = {'stage': stage, 'event': event['event'], **interpretation(event)}
        safe['fallback'] = safe.pop('message')
        for name in ('task', 'phase'):
            text = safe_text(context.get(name))
            if text:
                safe[name] = text
        for name in ('functional_complete', 'pr_ready', 'last_check_expectation_met'):
            value = event.get(name, context.get(name))
            if type(value) is bool:
                safe[name] = value
        for name in ('verification_passed', 'verification_failed', 'review_findings'):
            value = context.get(name)
            if type(value) is int and 0 <= value <= 64:
                safe[name] = value
        if context.get('task_kind') in {'readiness', 'implementation'}:
            safe['task_kind'] = context['task_kind']
        for name in ('failure_code', 'verification_reason', 'recovery_action'):
            value = context.get(name)
            if isinstance(value, str) and re.fullmatch(r'[A-Za-z][A-Za-z_]{0,127}', value):
                safe[name] = value
        if event['event'] in {'node_started', 'call_started', 'verification_started'}:
            safe['state'] = 'verifying' if event['event'] == 'verification_started' else 'running'
        elif event['event'] == 'call_succeeded':
            safe['state'] = 'verification_pending' if stage == 'worker' else 'result_returned'
        elif event['event'] == 'call_failed':
            safe['state'] = 'failure_recorded'
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if self.db.execute('SELECT 1 FROM node_narration_jobs WHERE source_event_id=?', (source['event_id'],)).fetchone():
                return
            counts = self.db.execute("SELECT count(*),sum(status IN ('pending','running')) FROM node_narration_jobs WHERE run_id=?", (run_id,)).fetchone()
            if counts[0] >= 512 or (counts[1] or 0) >= 64:
                return
            # Retain raw facts, but avoid spending model turns on already superseded progress.
            self.db.execute("UPDATE node_narration_jobs SET status='superseded' WHERE run_id=? AND session_id=? AND visit_id=? AND status='pending'",
                            (run_id, session_id, visit[0]))
            self.db.execute('INSERT OR IGNORE INTO node_narration_jobs(source_event_id,run_id,session_id,stage,visit_id,source_position,context) VALUES(?,?,?,?,?,?,?)',
                            (source['event_id'], run_id, session_id, stage, visit[0], source['position'], json.dumps(safe)))

    def claim(self, run_id, session_id, owner, *, now=None):
        now = time.time() if now is None else now
        # A worker can die on its final attempt; publish a fallback instead of leaving an eternal lease.
        expired = self.db.execute("SELECT source_event_id,owner FROM node_narration_jobs WHERE run_id=? AND session_id=? AND status='running' AND attempts>=2 AND lease_until<=?",
                                  (run_id, session_id, now)).fetchall()
        for source, old_owner in expired:
            job = _dict(self.db.execute('SELECT * FROM node_narration_jobs WHERE source_event_id=?', (source,)))
            self._publish(job, old_owner, 'failed', 'event_derived', json.loads(job['context'])['fallback'], {}, now,
                          expired=True, failure_code='lease_expired')
        with self.db:
            row = _dict(self.db.execute("UPDATE node_narration_jobs SET status='running',owner=?,lease_until=?,attempts=attempts+1 "
                "WHERE source_event_id=(SELECT source_event_id FROM node_narration_jobs WHERE run_id=? AND session_id=? AND attempts<2 "
                "AND (status='pending' OR (status='running' AND lease_until<=?)) ORDER BY source_position LIMIT 1) RETURNING *",
                (owner, now + 90, run_id, session_id, now)))
        if row:
            row['context'] = json.loads(row['context'])
        return row

    def _publish(self, job, owner, status, method, message, accounting, now, *, expired=False, failure_code=None):
        from council.observability import accounting as safe_accounting
        predicate = 'lease_until<=?' if expired else 'lease_until>?'
        with self.db:
            changed = self.db.execute("UPDATE node_narration_jobs SET status=? WHERE source_event_id=? AND owner=? AND status='running' AND " + predicate,
                                      (status, job['source_event_id'], owner, now)).rowcount
            if not changed:
                return False
            self.db.execute('INSERT OR IGNORE INTO node_narrations(source_event_id,run_id,session_id,stage,visit_id,source_position,message,status,method,generated_at,accounting) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                            (job['source_event_id'], job['run_id'], job['session_id'], job['stage'], job['visit_id'], job['source_position'],
                             message, status, method, datetime.now(timezone.utc).isoformat(), json.dumps(safe_accounting(accounting))))
            if status == 'failed':
                reason = failure_code if failure_code in {'generation_failed', 'lease_expired', 'budget_exhausted'} else 'generation_failed'
                self.db.execute('INSERT OR IGNORE INTO node_narration_failures VALUES(?,?,?)',
                                (job['source_event_id'], job['run_id'], reason))
        return True

    def finish(self, job, owner, draft, *, accounting=None, now=None):
        message = validate_draft(draft, job)
        return self._publish(job, owner, 'succeeded', 'model', message, accounting or {}, time.time() if now is None else now)

    def fail(self, job, owner, reason, *, now=None, accounting=None):
        return self._publish(job, owner, 'failed', 'event_derived', job['context']['fallback'], accounting or {},
                             time.time() if now is None else now, failure_code=reason)
