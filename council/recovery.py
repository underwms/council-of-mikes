"""Bounded recovery admission and classification; execution belongs to graph nodes."""
from council.diagnostics import DiagnosticRuntimeError, event
from council.graph_integrity import digest, source_hashes, matching_execution, command_digest
from council.plan_review import plan_digest
from council.governor import bindings
from council.recovery_contracts import RecoveryIncident, RecoveryDecision, RecoveryEvent
from datetime import datetime,timezone
from council.proposal_correction import STRUCTURED_FORMAT_CODES

RECOVERY_NODES = {'arbiter', 'recovery_admit', 'recovery_dispatch', 'recovery_result'}
HARD_STOPS = {'GRAPH_STEP_LIMIT', 'GRAPH_STATE_INVALID', 'GRAPH_CONTEXT_INVALID', 'PERMISSION_DENIED',
    'APPROVAL_REJECTED', 'PLAN_ACCEPTANCE_INVALID', 'TDD_PHASE_INCOMPLETE', 'CLI_AUTH_REQUIRED',
    'CLI_QUOTA_EXCEEDED', 'CLI_MODEL_UNSUPPORTED', 'CLI_ARGUMENTS_INVALID', 'CLI_INPUT_LIMIT',
    'CLI_INPUT_INVALID', 'NATIVE_INVENTORY_LIMIT', 'NATIVE_INVENTORY_FAILED', 'WORKSPACE_VALIDATION_FAILED',
    'RECOVERY_REJECTED','RECOVERY_EXHAUSTED','RECOVERY_NO_PROGRESS'}
HARD_STOPS |= {'CODEX_JSON_INVALID','CODEX_EVENT_INVALID','CODEX_SCHEMA_INVALID','CODEX_RESPONSE_JSON_INVALID',
    'GEMINI_SCHEMA_INVALID','GEMINI_ENVELOPE_INVALID','GEMINI_ENVELOPE_JSON_INVALID',
    'GEMINI_RESPONSE_JSON_INVALID','GEMINI_ISOLATION_FAILED','GEMINI_TOOL_DECLARATION_INVALID',
    'CLI_UNAVAILABLE','PROVIDER_UNAVAILABLE','VERIFICATION_POLICY_OVERRIDE','PROPOSAL_FORMAT_INVALID',
    'CODEX_REVIEW_ISOLATION_FAILED'}
READ_REPLAY = {'roadmap', 'roadmap_review', 'architect', 'plan_review', 'plan_revision', 'strategy_reset'}


def enabled(state):
    return state.recovery_policy.version == 1 and state.graph_integrity_policy_version == 2


def task_at(state):
    return (state.plan.tasks[state.current_task_index] if state.plan is not None
            and 0 <= state.current_task_index < len(state.plan.tasks) else None)


def exhausted_review_format(calls,code):
    last=calls[-1] if calls else {}
    return (code=='PLAN_REVIEW_INVALID' and last.get('status')=='failed'
        and last.get('operation') in {'roadmap_review_format_retry','plan_review_format_retry'}
        and (last.get('diagnostic') or {}).get('code')==code)


def wants_recovery(raw):
    """Routing only; authoritative evidence/budget checks occur during admission."""
    policy=raw.get('recovery_policy') or {}
    if policy.get('version') != 1 or raw.get('graph_integrity_policy_version') != 2:
        return False
    incident=raw.get('recovery_incident')
    if incident and incident.get('phase') == 'dispatched':
        return False
    code=(raw.get('diagnostic') or {}).get('code')
    if (code in HARD_STOPS or exhausted_review_format(raw.get('model_calls') or [],code)
            or raw.get('step_count',0) >= raw.get('max_steps',0)):
        return False
    if raw.get('status') not in {'FAILED','PLAN_BLOCKED','RECOVERY_NEEDED'}:
        return False
    if any(f.get('status')=='unresolved' and f.get('kind')=='user_decision'
           for f in raw.get('review_finding_ledger',[])):
        return False
    return not incident


def stale_tasks(state, context):
    """Only freshness of previously successful, unchanged accepted task contracts qualifies."""
    if state.plan is None or state.accepted_plan_sha256 != plan_digest(state.plan):
        return []
    stale=[]
    for index,task in enumerate(state.plan.tasks):
        if task.status != 'completed':
            return []
        changed=False
        for ci,argv in enumerate(task.test_commands,1):
            record=next((r for r in reversed(state.execution_records)
                if r.run_id==state.run_id and r.phase_index==state.current_phase_index
                and r.task_id==task.id and r.command_index==ci),None)
            if (record is None or not record.expectation_met or record.plan_sha256!=state.accepted_plan_sha256
                    or record.contract_versions!=bindings(state) or record.command_sha256!=command_digest(task,ci)):
                return []
            changed |= matching_execution(state, task, ci, context) is None
        if changed: stale.append(index)
    return stale


def observation_matches(state, context):
    task=task_at(state); obs=state.worker_observation
    worker_index=next((i for i in reversed(range(len(state.model_calls)))
        if state.model_calls[i].get('operation')=='worker'),None)
    call=state.model_calls[worker_index] if worker_index is not None else {}
    later=state.model_calls[worker_index+1:] if worker_index is not None else []
    incident=state.recovery_incident
    classified=(len(later)==1 and later[0].get('operation')=='arbiter' and later[0].get('status')=='succeeded')
    corrected=(len(later)==2 and later[0].get('operation')=='arbiter' and later[0].get('status')=='failed'
        and (later[0].get('diagnostic') or {}).get('code') in STRUCTURED_FORMAT_CODES
        and later[1].get('operation')=='arbiter_format_retry' and later[1].get('status')=='succeeded')
    arbiter_only=((classified or corrected) and incident is not None
        and incident.category=='tool_failure' and obs is not None
        and 'call:'+str(obs.call) in incident.evidence_ids)
    return bool(task and obs and obs.run_id==state.run_id and obs.phase_index==state.current_phase_index
        and (not later or arbiter_only)
        and obs.task_id==task.id and obs.plan_sha256==state.accepted_plan_sha256==plan_digest(state.plan)
        and obs.call==call.get('call') and call.get('operation')=='worker' and call.get('status')=='failed'
        and obs.source_hashes==source_hashes(task,context)
        and all(path in obs.source_hashes for path in task.target_files))


def append_event(state, outcome):
    incident=state.recovery_incident
    execution_ids=[r.id for r in state.execution_records[incident.execution_cursor:]][-32:]
    elapsed=max(0.0,(datetime.now(timezone.utc)-datetime.fromisoformat(incident.opened_utc)).total_seconds())
    charged=[e for e in state.recovery_history if e.outcome=='admitted']
    used_run=len(charged)+int(outcome=='admitted')
    used_incident=sum(e.lineage==incident.lineage for e in charged)+int(outcome=='admitted')
    entry=RecoveryEvent(incident_id=incident.id,lineage=incident.lineage,
        outcome=outcome,action=incident.decision.action if incident.decision else None,
        step=state.step_count,evidence_ids=list(incident.evidence_ids),execution_ids=execution_ids,
        elapsed_seconds=round(elapsed,3),category=incident.category,
        reason=incident.decision.reason if incident.decision else 'cause_unproven',
        run_budget_remaining=max(0,state.recovery_policy.max_strategies_per_run-used_run),
        incident_budget_remaining=max(0,state.recovery_policy.max_strategies_per_incident-used_incident),
        resource_cleanup=incident.resource_cleanup,diagnostic_code=(state.diagnostic or {}).get('code'),
        incident=incident.model_copy(deep=True) if outcome=='admitted' else None)
    state.recovery_history.append(entry)
    event('recovery_'+outcome,stage='arbiter',recovery_detail={'incident_id':incident.id,
        'category':incident.category,'action':entry.action,'outcome':outcome,
        'elapsed_seconds':entry.elapsed_seconds,'execution_ids':execution_ids,'reason':entry.reason,
        'run_budget_remaining':entry.run_budget_remaining,'incident_budget_remaining':entry.incident_budget_remaining})


def incident_sources(state,context):
    incident=state.recovery_incident
    if incident and incident.source_tasks:
        values={}
        for index in incident.source_tasks:
            values.update(source_hashes(state.plan.tasks[index],context))
        return values
    task=task_at(state)
    return source_hashes(task,context) if task else {}


def open_incident(state, context):
    if not enabled(state) or state.recovery_incident is not None:
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    diagnostic=state.diagnostic or {}
    code=diagnostic.get('code','VERIFICATION_FAILED')
    last_call=state.model_calls[-1] if state.model_calls else {}
    from council.graph_integrity import context_consumer
    origin=diagnostic.get('graph_stage') or (context_consumer(last_call['operation'])
        if last_call.get('status')=='failed' else 'investigation')
    if (code in HARD_STOPS or exhausted_review_format(state.model_calls,code)
            or origin in RECOVERY_NODES or state.step_count >= state.max_steps):
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    task=task_at(state)
    category='unknown'; action=None; queue=[]
    advice=state.repair_advice
    records=[r for r in state.execution_records if r.run_id==state.run_id
             and r.phase_index==state.current_phase_index and task and r.task_id==task.id]
    if (origin=='investigation' and state.status=='RECOVERY_NEEDED' and advice
            and any(r.id==advice.failure_id and not r.expectation_met for r in records)):
        if advice.category in {'command_contract','prerequisite'}:
            category=advice.category; action='replan'
        elif advice.category in {'implementation','test_harness'}:
            category='verification'; action='repair_task'
    if state.status=='FAILED' and code in {'VERIFICATION_FAILED','READINESS_FAILED'} and state.test_retry_count>=state.max_test_retries:
        category='verification'; action='stop'
    if action is None and code=='CLI_TIMEOUT' and origin=='worker':
        category='timeout'
        if observation_matches(state,context): action='verify_partial'
    if action is None and code=='CODEX_TOOL_FAILED' and origin=='worker' and observation_matches(state,context):
        category='tool_failure'
    if action is None and code=='GRAPH_EVIDENCE_INVALID' and origin in {'phase_complete','finished_change_review','proof_refresh'}:
        queue=stale_tasks(state,context)
        if queue: category='stale_proof'; action='refresh_proofs'
    if action is None and origin=='finished_change_review' and state.status=='RECOVERY_NEEDED' and state.finalization.findings:
        category='planning' if any(f.kind=='scope_change' for f in state.finalization.findings) else 'verification'
        action='stop' if category=='planning' or state.finalization.review_count>=3 else 'repair_task'
    if action is None and origin in READ_REPLAY and code in {'CLI_TIMEOUT','CLI_IO_FAILED','CLI_START_FAILED','CLI_EXECUTION_FAILED'}:
        # invoke_model already charges its safe transient retry; do not invent another.
        category='transport'; action='stop'
    if action is None and state.status=='PLAN_BLOCKED' and state.plan is not None:
        category='planning'; action='replan'
    sources=source_hashes(task,context) if task else {}
    if queue:
        sources={path:value for index in queue for path,value in source_hashes(state.plan.tasks[index],context).items()}
    evidence_ids=[r.id for r in records[-16:]]
    if state.model_calls: evidence_ids.append('call:'+str(state.model_calls[-1]['call']))
    from council.diagnostics import safe_resource_cleanup
    resource_cleanup=safe_resource_cleanup((state.model_calls[-1].get('diagnostic') or {}).get('resource_cleanup')) if state.model_calls else None
    if resource_cleanup and (resource_cleanup['owned_process_exit_confirmed'] is False
            or resource_cleanup['detached_resources']=='cleanup_required'):
        action='stop'
    # Lineage deliberately excludes task names, plan digest and source content.
    # Category + piece + failing command identity survives cosmetic plan/task changes.
    command_identity=([digest(task.test_commands),digest(task.target_files)] if task
                      else [origin])
    lineage=digest([state.run_id,state.current_phase_index,category,command_identity])
    incident=RecoveryIncident(id=digest([state.run_id,state.step_count,lineage]),lineage=lineage,
        category=category,origin=origin,code=code,run_id=state.run_id,phase_index=state.current_phase_index,
        task_id=task.id if task else None,plan_sha256=state.accepted_plan_sha256,
        contract_versions=bindings(state),source_hashes=sources,evidence_ids=evidence_ids,
        cursor=state.current_task_index,queue=queue,source_tasks=list(queue),review_baseline=state.plan_review_count,
        revision_baseline=state.plan_revision_count,resume_status=state.status,
        opened_utc=datetime.now(timezone.utc).isoformat(),execution_cursor=len(state.execution_records),
        resource_cleanup=resource_cleanup or {'owned_process_exit_confirmed':None,'detached_resources':'unobserved'},
        failure_commands=list(dict.fromkeys(r.command_sha256 for r in records if not r.expectation_met))[-16:])
    state.recovery_incident=incident
    append_event(state,'opened')
    return action


def decision_reason(incident,action):
    if incident.resource_cleanup.get('detached_resources')=='cleanup_required' or incident.resource_cleanup.get('owned_process_exit_confirmed') is False:
        return 'resources_unresolved'
    if action=='verify_partial':return 'retained_sources_match'
    if action=='refresh_proofs':return 'stale_bound_proof'
    if action=='repair_task':return 'repair_existing_task'
    if action=='ask_user':return 'user_decision_required'
    if action=='replan':
        return {'command_contract':'command_correction_required','prerequisite':'prerequisite_scope_review'}.get(incident.category,'technical_plan_correction')
    if incident.category=='transport':return 'safe_retry_exhausted'
    if incident.category=='verification' and incident.code in {'READINESS_FAILED','VERIFICATION_FAILED'}:
        return 'repair_budget_exhausted'
    return 'cause_unproven'


def admit(state, context, *, record=True):
    incident=state.recovery_incident
    if not incident or incident.phase!='proposed' or incident.decision is None:
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    decision=incident.decision
    if decision.incident_id!=incident.id or not set(decision.evidence_ids)<=set(incident.evidence_ids):
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    if (incident.run_id!=state.run_id or incident.phase_index!=state.current_phase_index
            or incident.plan_sha256!=state.accepted_plan_sha256 or incident.contract_versions!=bindings(state)):
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    task=task_at(state)
    if (task.id if task else None)!=incident.task_id or incident_sources(state,context)!=incident.source_hashes:
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    admitted=[r for r in state.recovery_history if r.outcome=='admitted']
    if (len(admitted)>=state.recovery_policy.max_strategies_per_run
            or sum(r.lineage==incident.lineage for r in admitted)>=state.recovery_policy.max_strategies_per_incident
            or any(r.incident_id==incident.id for r in admitted) or state.step_count>=state.max_steps):
        raise DiagnosticRuntimeError('RECOVERY_EXHAUSTED')
    allowed={'timeout':{'verify_partial','stop'},'tool_failure':{'verify_partial','stop'},'stale_proof':{'refresh_proofs','stop'},
        'command_contract':{'replan','stop'},'prerequisite':{'replan','ask_user','stop'},
        'verification':{'repair_task','stop'},'planning':{'replan','ask_user','stop'},
        'transport':{'stop'},'unknown':{'stop','ask_user'}}
    if decision.action not in allowed[incident.category]:
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    if decision.reason!=decision_reason(incident,decision.action):
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    if decision.reason=='resources_unresolved' and decision.action!='stop':
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    if decision.action=='ask_user' and not any(f.status=='unresolved' and f.kind=='user_decision'
            for f in state.review_finding_ledger):
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    if decision.action=='verify_partial' and not observation_matches(state,context):
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    if decision.action=='refresh_proofs' and incident.queue!=stale_tasks(state,context):
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    if decision.action=='repair_task' and (state.test_retry_count>state.max_test_retries
            or incident.resume_status!='RECOVERY_NEEDED'):
        raise DiagnosticRuntimeError('RECOVERY_EXHAUSTED')
    if decision.action=='replan' and state.plan is None:
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    incident.phase='admitted'
    if record:append_event(state,'admitted')


def recheck_dispatch(state,context):
    """Repeat admission evidence checks after the intervening checkpoint, without charging twice."""
    incident=state.recovery_incident
    if not incident or incident.phase!='admitted': raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    probe=state.model_copy(deep=True)
    probe.recovery_incident.phase='proposed'
    probe.recovery_history=[e for e in probe.recovery_history if not (e.incident_id==incident.id and e.outcome=='admitted')]
    admit(probe,context,record=False)


def verify_inputs(state,context,*,allow_repair=True):
    incident=state.recovery_incident
    if not incident or incident.phase!='dispatched':return None
    if incident.decision.action not in {'verify_partial','refresh_proofs','repair_task'}:return None
    if (incident.run_id!=state.run_id or incident.phase_index!=state.current_phase_index
            or incident.plan_sha256!=state.accepted_plan_sha256 or incident.contract_versions!=bindings(state)):
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    expected=dict(incident.source_hashes)
    if (incident.repairing or incident.decision.action=='repair_task') and allow_repair:
        task=task_at(state); obs=state.worker_observation
        call=state.model_calls[-1] if state.model_calls else {}
        if (not task or not obs or obs.task_id!=task.id or obs.run_id!=state.run_id
                or obs.phase_index!=state.current_phase_index or obs.plan_sha256!=state.accepted_plan_sha256
                or obs.call!=call.get('call') or call.get('operation')!='worker'
                or call.get('status')!='succeeded' or obs.source_hashes!=source_hashes(task,context)):
            raise DiagnosticRuntimeError('RECOVERY_REJECTED')
        expected.update(obs.source_hashes)
    if incident_sources(state,context)!=expected:
        raise DiagnosticRuntimeError('RECOVERY_REJECTED')
    return expected


def close(state, outcome):
    append_event(state,outcome)
    state.recovery_incident=None


def review_active(state):
    incident=state.recovery_incident
    return bool(incident and incident.phase=='dispatched' and incident.decision and incident.decision.action=='replan')


def context_record(state):
    incident=state.recovery_incident
    return incident.model_dump(mode='json') if incident else None
