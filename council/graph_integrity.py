"""Shared run identity, owned transitions, and verified delivery of canonical data."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from council.diagnostics import DiagnosticRuntimeError
from council.integrity_contracts import VerificationRecord

_MARKER = '\n__COUNCIL_SHARED_CONTEXT_V2__\n'
_IDENTITY = ('run_id', 'thread_id', 'workspace_root', 'council_root', 'memory_root', 'model_configuration',
    'approval_policy', 'auto_approve', 'review_protocol_version', 'revision_evidence_policy_version',
    'readiness_policy_version', 'orchestration_policy_version', 'graph_integrity_policy_version',
    'max_steps', 'max_test_retries')
_APPEND = ('model_calls', 'tool_call_history', 'test_results', 'execution_records', 'completed_phases',
           'completed_red_phase_evidence', 'context_receipts', 'integrity_events', 'recovery_history')
_OWNERS = {
    'roadmap': {'roadmap'},
    'plan': {'architect', 'plan_revision', 'strategy_reset', 'roadmap_review', 'phase_complete'},
    'accepted_roadmap_sha256': {'roadmap_review'},
    'accepted_plan_sha256': {'plan_review', 'plan_revision', 'strategy_reset', 'plan_blocked',
                             'roadmap_review', 'phase_complete'},
    'roadmap_finding_ledger': {'roadmap_review'},
    'review_finding_ledger': {'plan_review', 'plan_blocked', 'roadmap_review', 'phase_complete'},
    'execution_records': {'prover'},
    'test_results': {'prover'},
    'test_result': {'prover', 'roadmap_review', 'phase_complete'},
    'completed_phases': {'phase_complete'},
    'completed_red_phase_evidence': {'phase_complete'},
    'repair_advice': {'investigation', 'prover', 'phase_complete', 'roadmap_review'},
    'human_feedback': {'plan_blocked'},
    'file_changes': {'worker'},
    'modified_files': {'worker'},
    'roadmap_inspection_evidence': {'roadmap_review'},
    'last_document_revision': {'roadmap', 'plan_revision', 'strategy_reset', 'roadmap_review', 'phase_complete'},
    'document_revision_feedback': {'roadmap', 'plan_revision', 'strategy_reset', 'roadmap_review', 'phase_complete'},
}
_MODEL_NODES = {'roadmap', 'roadmap_review', 'architect', 'plan_review', 'plan_revision',
                'strategy_reset', 'worker', 'investigation'}
_PHASE_START = {'roadmap_review', 'phase_complete'}
_PLAN_EDITORS = {'architect', 'plan_revision', 'strategy_reset'}
_OWNERS.update({
    'model_calls': _MODEL_NODES,
    'tool_call_history': {'roadmap', 'architect', 'plan_revision', 'worker'},
    'context_receipts': _MODEL_NODES | {'prover', 'phase_complete', 'gatekeeper', 'final_review'},
    'planning_evidence': {'roadmap', 'architect', 'plan_revision'} | _PHASE_START,
    'planning_evidence_available': {'roadmap', 'architect', 'plan_revision'} | _PHASE_START,
    'planning_evidence_truncated': {'roadmap', 'architect', 'plan_revision'} | _PHASE_START,
    'planning_inspection': {'roadmap', 'architect', 'plan_revision'},
    'roadmap_inspection_available': {'roadmap_review'},
    'roadmap_inspection_truncated': {'roadmap_review'},
    'red_phase_evidence': {'prover', 'phase_complete'},
    'phase_start_file_hashes': {'phase_complete'},
    'phase_start_test_result_index': _PHASE_START,
    'current_phase_index': {'phase_complete'},
    'current_task_index': {'prover'} | _PHASE_START,
    'test_retry_count': {'prover', 'investigation'},
    'active_role': {'worker', 'prover', 'investigation'},
    'active_specialist': {'worker'},
    'investigation_report': {'investigation'},
    'workspace_validator_passed': {'gatekeeper'},
    'gatekeeper_summary': {'gatekeeper'},
    'roadmap_review_count': {'roadmap_review', 'plan_blocked'},
    'roadmap_revision_count': {'roadmap', 'plan_blocked'},
    'roadmap_no_progress_count': {'roadmap_review'},
    'last_reviewed_roadmap_sha256': {'roadmap_review'},
    'roadmap_review_findings': {'roadmap_review'},
    'plan_review_count': {'plan_review'} | _PHASE_START,
    'plan_revision_count': {'plan_revision', 'strategy_reset'} | _PHASE_START,
    'plan_preflight_failure_count': _PLAN_EDITORS | _PHASE_START,
    'plan_validation_feedback': _PLAN_EDITORS | _PHASE_START,
    'plan_review_findings': _PLAN_EDITORS | {'plan_review', 'plan_blocked'} | _PHASE_START,
    'plan_recovery_count': {'plan_blocked'} | _PHASE_START,
    'recovery_review_baseline': {'plan_blocked'} | _PHASE_START,
    'recovery_revision_baseline': {'plan_blocked'} | _PHASE_START,
    'strategy_reset_count': {'strategy_reset'} | _PHASE_START,
    'review_no_progress_count': {'plan_review', 'strategy_reset', 'plan_blocked'} | _PHASE_START,
    'last_reviewed_plan_sha256': {'plan_review', 'plan_blocked'} | _PHASE_START,
    'total_inspection_rounds': {'roadmap', 'architect', 'plan_revision'},
})
_STATUSES = {
    'roadmap': {'ROADMAP_REVIEW', 'ROADMAP_REVISION', 'PLAN_BLOCKED'},
    'roadmap_review': {'PLAN_PHASE', 'ROADMAP_REVISION', 'PLAN_BLOCKED'},
    'architect': {'PLAN_REVIEW', 'PLAN_REVISION'},
    'plan_review': {'EXECUTING', 'PLAN_REVISION', 'STRATEGY_RESET', 'PLAN_BLOCKED'},
    'plan_revision': {'PLAN_REVIEW', 'PLAN_PREFLIGHT_RETRY', 'PLAN_BLOCKED'},
    'strategy_reset': {'PLAN_REVIEW', 'PLAN_PREFLIGHT_RETRY', 'PLAN_BLOCKED'},
    'plan_blocked': {'PLAN_REVISION', 'ROADMAP_REVISION'},
    'worker': {'TESTING'},
    'prover': {'FAILED', 'RETRYING', 'EXECUTING', 'GATEKEEPER_AUDIT'},
    'investigation': {'EXECUTING'},
    'phase_complete': {'PLAN_PHASE', 'GATEKEEPER_AUDIT'},
    'gatekeeper': {'FINAL_REVIEW', 'FAILED'},
    'final_review': {'COMPLETED', 'FAILED'},
}
_GOVERNANCE_CAPTURE = set(_STATUSES) | {'governor'}
_OWNERS.update(work_pieces=_GOVERNANCE_CAPTURE,
    shared_contracts={'roadmap_review', 'plan_review'}, contract_history={'plan_review'})
_OWNERS['governance_feedback'] = {'roadmap', 'architect', 'plan_revision', 'strategy_reset', 'plan_review'} | _PHASE_START
_STATUSES['governor'] = {'PLAN_PHASE', 'GATEKEEPER_AUDIT', 'PLAN_BLOCKED'}
for _node in ('roadmap_review', 'plan_review', 'phase_complete'):
    _STATUSES[_node].add('GOVERNOR')
for _field, _owners in _OWNERS.items():
    if _owners & _PHASE_START:
        _owners.add('governor')
for _field in ('planning_inspection', 'test_retry_count', 'last_error_hash', 'investigation_report'):
    _OWNERS.setdefault(_field, set()).add('governor')

_RECOVERY_NODES = {'arbiter', 'recovery_admit', 'recovery_dispatch', 'recovery_result'}
_MODEL_NODES.add('arbiter')
_OWNERS['model_calls'].add('arbiter')
_OWNERS['context_receipts'].add('arbiter')
_OWNERS.update(recovery_incident=_RECOVERY_NODES, recovery_history=_RECOVERY_NODES,
    worker_observation={'worker'})
_OWNERS['current_task_index'] |= {'recovery_dispatch', 'recovery_result'}
_GOVERNANCE_CAPTURE |= _RECOVERY_NODES
_OWNERS['work_pieces'] |= _RECOVERY_NODES
_STATUSES.update(arbiter={'RECOVERY_ADMIT'}, recovery_admit={'RECOVERY_DISPATCH'},
    recovery_dispatch={'TESTING', 'EXECUTING', 'PLAN_REVISION', 'PLAN_BLOCKED', 'FAILED'},
    recovery_result={'TESTING', 'RETRYING', 'EXECUTING', 'PLAN_BLOCKED', 'FAILED', 'GATEKEEPER_AUDIT'})
_STATUSES['investigation'].add('RECOVERY_NEEDED')
_MODEL_NODES.add('intake_draft')
for _field in ('model_calls', 'context_receipts', 'tool_call_history'):
    _OWNERS[_field].add('intake_draft')
_OWNERS['requirements'] = {'intake_draft', 'requirements_gate'}
_STATUSES.update(intake_draft={'REQUIREMENTS_WAITING'}, requirements_gate={'REQUIREMENTS_DRAFT', 'START_PLANNING'})
_MODEL_NODES.add('finished_change_review')
for _field in ('model_calls', 'context_receipts'):
    _OWNERS[_field].add('finished_change_review')
_OWNERS['finalization'] = {'worker', 'finished_change_review', 'final_review', 'gatekeeper'}
_OWNERS['delivery_result'] = {'final_review'}
_OWNERS['current_task_index'].add('finished_change_review')
_STATUSES['finished_change_review'] = {'GATEKEEPER_AUDIT', 'RECOVERY_NEEDED'}
_OWNERS['work_pieces'].add('finished_change_review')
_OWNERS['requirements'].add('requirements_reopen')
_OWNERS['requirements'].add('plan_review')
_STATUSES['requirements_reopen'] = {'REQUIREMENTS_DRAFT'}
for _field in ('roadmap','plan','accepted_plan_sha256','accepted_roadmap_sha256','work_pieces',
        'shared_contracts','contract_history','current_phase_index','current_task_index',
        'review_finding_ledger','roadmap_finding_ledger','roadmap_review_findings',
        'last_reviewed_roadmap_sha256','roadmap_no_progress_count','finalization'):
    _OWNERS.setdefault(_field,set()).add('requirements_gate')
from council.governor import _LOCAL_FIELDS as _PROOF_RESTORE_FIELDS
for _field in (*_PROOF_RESTORE_FIELDS,'current_phase_index','current_task_index','work_pieces'):
    _OWNERS.setdefault(_field,set()).add('proof_refresh')
_OWNERS['proof_refresh_piece'] = _OWNERS['proof_refresh_reason'] = {'gatekeeper','proof_refresh'}
_STATUSES['proof_refresh'] = {'FAILED','GATEKEEPER_AUDIT'}
_STATUSES['gatekeeper'] |= {'PROOF_REFRESH','PROOF_REVIEW'}


def enabled(state):
    return state.graph_integrity_policy_version == 2


def digest(value):
    if hasattr(value, 'model_dump'):
        value = value.model_dump(mode='json')
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def seal_state(state):
    if not enabled(state):
        return
    identity_values = [getattr(state, field) for field in _IDENTITY]
    if state.governance_policy_version == 2:
        identity_values.append({'governance_policy_version': 2})
    if state.recovery_policy.version:
        identity_values.append({'recovery_policy': state.recovery_policy.model_dump(mode='json')})
    if state.intake_enabled:
        identity_values.append({'intake_enabled':True})
    if state.finalization_enabled:
        identity_values.append({'finalization_enabled':True})
    requirement, identity = digest(state.task_input), digest(identity_values)
    if not state.requirement_sha256 and not state.run_identity_sha256 and state.step_count == 0:
        state.requirement_sha256, state.run_identity_sha256 = requirement, identity
    if (state.requirement_sha256, state.run_identity_sha256) != (requirement, identity):
        raise DiagnosticRuntimeError('GRAPH_STATE_INVALID')


def _plain(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return deepcopy(value)


def check_transition(before, after, consumer):
    if not enabled(before):
        return
    if not enabled(after):
        raise DiagnosticRuntimeError('GRAPH_STATE_INVALID')
    seal_state(after)
    from council.plan_review import plan_digest
    if consumer=='plan_review' and before.requirements != after.requirements:
        from council.baseline import admit_plan_challenges
        expected = before.model_copy(deep=True)
        expected.plan = after.plan
        admit_plan_challenges(expected,review_sha256=digest([plan_digest(after.plan),after.model_calls[-1]['call']]))
        if expected.requirements != after.requirements:
            raise DiagnosticRuntimeError('GRAPH_STATE_INVALID')
    if before.governance_policy_version != after.governance_policy_version:
        raise DiagnosticRuntimeError('GRAPH_STATE_INVALID')
    for field in (*_IDENTITY, 'task_input', 'requirement_sha256', 'run_identity_sha256', 'graph_integrity_policy_version'):
        if getattr(before, field) != getattr(after, field):
            raise DiagnosticRuntimeError('GRAPH_STATE_INVALID')
    if before.status != after.status and after.status not in _STATUSES.get(consumer, set()):
        raise DiagnosticRuntimeError('GRAPH_STATE_INVALID')
    for field in type(before).model_fields:
        if field in {*_IDENTITY, 'task_input', 'requirement_sha256', 'run_identity_sha256', 'status', 'error', 'diagnostic'}:
            continue
        owners = _OWNERS.get(field, set())
        old, new = getattr(before, field), getattr(after, field)
        if old == new or consumer in owners:
            continue
        if field == 'plan' and consumer in {'worker', 'prover'} and old is not None and new is not None:
            if plan_digest(old) == plan_digest(new):
                continue
        raise DiagnosticRuntimeError('GRAPH_STATE_INVALID')
    if after.accepted_plan_sha256 is not None and (after.plan is None
            or after.accepted_plan_sha256 != plan_digest(after.plan)):
        raise DiagnosticRuntimeError('GRAPH_STATE_INVALID')
    if after.accepted_roadmap_sha256 is not None:
        from council.phase_contract import roadmap_digest
        if after.roadmap is None or after.accepted_roadmap_sha256 != roadmap_digest(after.roadmap):
            raise DiagnosticRuntimeError('GRAPH_STATE_INVALID')
    for field in _APPEND:
        old, new = _plain(getattr(before, field)), _plain(getattr(after, field))
        if len(new) < len(old) or new[:len(old)] != old:
            raise DiagnosticRuntimeError('GRAPH_STATE_INVALID')
    from council.governor import verify_transition
    verify_transition(before, after, consumer)


def restore_protected(before, after):
    """Keep actual call/file observations when rejecting an internal proposal."""
    restored = before.model_copy(deep=True)
    for field in ('model_calls', 'tool_call_history', 'context_receipts'):
        old, new = getattr(before, field), getattr(after, field)
        if _plain(new[:len(old)]) == _plain(old):
            setattr(restored, field, deepcopy(new))
    for field in ('file_changes', 'modified_files'):
        setattr(restored, field, deepcopy(getattr(after, field)))
    return restored


def shared_node_context(state, consumer):
    """One canonical view, with source contents and explicit availability markers."""
    task = (state.plan.tasks[state.current_task_index] if state.plan is not None
            and state.current_task_index < len(state.plan.tasks) else None)
    phase = (state.roadmap.phases[state.current_phase_index] if state.roadmap is not None
             and state.current_phase_index < len(state.roadmap.phases) else None)
    planning = consumer in {'roadmap', 'roadmap_review', 'architect', 'plan_review', 'plan_revision', 'strategy_reset'}
    task_records = [item for item in state.execution_records if item.phase_index == state.current_phase_index
        and item.run_id == state.run_id and task is not None and item.task_id == task.id]
    repair = (state.repair_advice if state.repair_advice is not None
              and any(item.id == state.repair_advice.failure_id for item in task_records) else None)
    records = {
        'requirement': state.task_input,
        'user_feedback': state.human_feedback,
        'roadmap': _plain(state.roadmap),
        'accepted_contracts': {'roadmap_sha256': state.accepted_roadmap_sha256, 'plan_sha256': state.accepted_plan_sha256},
        'phase': _plain(phase),
        'completed_phases': _plain(state.completed_phases),
        'plan': _plain(state.plan) if planning else None,
        'plan_architecture': state.plan.architecture_summary if state.plan else None,
        'task': _plain(task),
        'findings': {'roadmap': _plain(state.roadmap_finding_ledger), 'plan': _plain(state.review_finding_ledger)},
        'observations': {'roadmap': list(state.roadmap_inspection_evidence),
            'current': list(state.planning_evidence), 'current_available': state.planning_evidence_available,
            'current_truncated': state.planning_evidence_truncated,
            'roadmap_available': state.roadmap_inspection_available, 'roadmap_truncated': state.roadmap_inspection_truncated},
        'latest_verification': _plain(state.test_result) if planning or task_records or task is None else None,
        'repair_advice': _plain(repair),
        'revision': deepcopy(state.last_document_revision) if planning else None,
        'execution_evidence': [_plain(item) for item in state.execution_records
            if consumer in {'gatekeeper', 'phase_complete'} or
               (item.phase_index == state.current_phase_index and (task is None or item.task_id == task.id))],
    }
    from council.requirements import effective_requirements, baseline_context
    if consumer not in {'intake_draft', 'requirements_gate'}:
        records['requirement'] = effective_requirements(state)
    records['baseline'] = baseline_context(state)
    from council.assignments import assignment_context
    records['assignment_handoff'] = assignment_context(state)
    if state.finalization_enabled:
        records['finalization'] = {'required':True,
            'instruction':'Final acceptance ends with a reviewed delivery_stage=finalize task for real scoped polish/documentation and independent verification. Independent complete finished-content review follows. Preserve requirements and scope.',
            'findings':[f.model_dump(mode='json') for f in state.finalization.findings],
            'polish_task_ids':state.finalization.polish_task_ids,
            'quality_gates':state.finalization.quality_gates}
    if state.intake_enabled:
        records['original_analysis'] = state.task_input
        records['requirements_approval'] = {'sha256':state.requirements.approved_sha256,
            'revision':len(state.requirements.revisions), 'limitations':state.requirements.accepted_limitations}
    if state.governance_policy_version == 2:
        from council.governor import prompt_context
        records.update(prompt_context(state))
    if state.recovery_policy.version and consumer in {'arbiter','architect','plan_revision','strategy_reset','worker','investigation'}:
        records['recovery']={'policy':state.recovery_policy.model_dump(mode='json'),
            'incident':_plain(state.recovery_incident),
            'recent_outcomes':[e.model_dump(mode='json',exclude={'incident'}) for e in state.recovery_history[-8:]]}
    sources = {'requirement': 'user', 'user_feedback': 'user', 'roadmap': 'roadmap', 'plan': 'architect',
        'findings': 'reviewer', 'observations': 'inspection', 'latest_verification': 'prover',
        'repair_advice': 'investigation', 'execution_evidence': 'prover'}
    manifest = [{'artifact_id': key, 'sha256': digest(value), 'producer': sources.get(key, 'engine'),
                 'available': value is not None} for key, value in records.items()]
    return {'policy_version': 2, 'run_id': state.run_id, 'consumer': consumer,
        'phase_index': state.current_phase_index, 'task_id': task.id if task else None,
        'records': records, 'manifest': manifest}


def _message_frame(message):
    if not isinstance(message, dict) or not isinstance(message.get('content'), str):
        return None
    try:
        value = json.loads(message['content'])
    except (ValueError, TypeError):
        return None
    return value.get('shared_context') if isinstance(value, dict) and set(value) == {'shared_context'} else None


def prepare_payload(state, consumer, payload):
    if not enabled(state):
        return payload
    frame = shared_node_context(state, consumer)
    if isinstance(payload, dict):
        result = {**payload, 'shared_context': frame}
    elif isinstance(payload, list):
        result = [message for message in payload if _message_frame(message) is None]
        result.append({'role': 'user', 'content': json.dumps({'shared_context': frame})})
    elif isinstance(payload, str):
        result = payload.split(_MARKER, 1)[0] + _MARKER + json.dumps(frame)
    else:
        raise DiagnosticRuntimeError('GRAPH_CONTEXT_INVALID')
    validate_payload(state, consumer, result)
    return result


def _preacceptance_arbiter_context(state, consumer):
    """Classification may precede acceptance; task execution never inherits this exception."""
    incident = state.recovery_incident
    return (consumer == 'arbiter' and state.recovery_policy.version == 1
        and incident is not None and incident.phase == 'proposed'
        and incident.origin in {'roadmap', 'roadmap_review'}
        and incident.run_id == state.run_id and incident.phase_index == state.current_phase_index == 0
        and incident.task_id is None and incident.plan_sha256 is None
        and state.accepted_roadmap_sha256 is None and state.accepted_plan_sha256 is None
        and state.plan is None and not state.work_pieces and not state.shared_contracts
        and not state.execution_records and not state.completed_phases)


def validate_payload(state, consumer, payload):
    if not enabled(state):
        return None
    try:
        if isinstance(payload, dict):
            frames = [payload['shared_context']]
        elif isinstance(payload, list):
            frames = [frame for message in payload if (frame := _message_frame(message)) is not None]
        else:
            frames = [json.loads(payload.rsplit(_MARKER, 1)[1])]
        if len(frames) != 1 or frames[0] != shared_node_context(state, consumer):
            raise ValueError('Context mismatch')
        frame = frames[0]
        if not frame['records']['requirement']:
            raise ValueError('Requirement absent')
        if consumer in {'worker', 'investigation', 'prover'}:
            from council.plan_review import plan_digest
            if (not frame['records']['task'] or not state.plan
                    or state.accepted_plan_sha256 != plan_digest(state.plan)):
                raise ValueError('Accepted task absent')
        if (state.orchestration_policy_version == 2
                and consumer not in {'roadmap', 'roadmap_review', 'intake_draft', 'requirements_gate'}
                and not _preacceptance_arbiter_context(state, consumer)):
            from council.phase_contract import roadmap_digest
            if state.roadmap is None or state.accepted_roadmap_sha256 != roadmap_digest(state.roadmap):
                raise ValueError('Accepted roadmap absent')
        return frame
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        raise DiagnosticRuntimeError('GRAPH_CONTEXT_INVALID') from None


def record_context(state, consumer, payload, *, call=None, role=None, operation=None):
    frame = validate_payload(state, consumer, payload)
    if frame is not None:
        receipt = {key: frame[key] for key in ('run_id', 'consumer', 'phase_index', 'task_id', 'manifest')}
        if any(value is not None for value in (call, role, operation)):
            from council.diagnostics import _ROLES, _OPERATIONS
            if (type(call) is not int or call != len(state.model_calls) + 1 or not 1 <= call <= 100000
                    or type(role) is not str or role not in _ROLES
                    or role not in state.model_configuration.get('roles', {})
                    or type(operation) is not str or operation not in _OPERATIONS
                    or context_consumer(operation) != consumer):
                raise DiagnosticRuntimeError('GRAPH_CONTEXT_INVALID')
            receipt.update(call=call, role=role, operation=operation,
                captured_utc=datetime.now(timezone.utc).isoformat(), payload_sha256=digest(_plain(payload)))
        state.context_receipts.append(receipt)


def context_consumer(operation):
    operation = operation.removesuffix('_transport_retry')
    return {'planning': 'architect', 'planning_inspection': 'architect', 'planning_format_retry': 'architect',
        'intake_inspection':'intake_draft',
        'roadmap_inspection': 'roadmap', 'roadmap_format_retry': 'roadmap',
        'plan_revision_inspection': 'plan_revision', 'plan_revision_format_retry': 'plan_revision',
        'intake_format_retry':'intake_draft','arbiter_format_retry':'arbiter',
        'investigation_format_retry':'investigation','finished_change_review_format_retry':'finished_change_review',
        'roadmap_review_format_retry':'roadmap_review','plan_review_format_retry':'plan_review'}.get(operation, operation)


def readiness_source_hashes(task, context):
    """Observe explicit readiness inputs without claiming a product dependency closure."""
    from council.native_inventory import snapshot, InventoryBudget
    from council.tools.discovery import validate_read_path
    paths = {task.proof_scope.project, *task.target_files, *task.proof_scope.generated_inputs}
    for argv in task.test_commands:
        for argument in argv:
            if argument.startswith('-') or Path(argument).is_absolute():
                continue
            candidate = (Path(task.working_directory) / argument).as_posix()
            if '..' not in Path(candidate).parts and context.workspace_path(candidate).is_file():
                paths.add(candidate)
    if len(paths) > 509:
        raise DiagnosticRuntimeError('NATIVE_INVENTORY_LIMIT')
    values, budget = {}, InventoryBudget()
    for path in sorted(paths):
        try:
            validate_read_path(context, path)
            values.update(snapshot(context, path, budget=budget))
        except FileNotFoundError:
            values[path] = None
    return {**values, '@proof:method':digest('readiness_observation_v1'),
        '@proof:toolchain':None, '@proof:runtime_mutable':digest(True)}


def source_hashes(task, context):
    """Proof names its finite source scope; unknown transitive dependencies stay unknown."""
    if task.proof_scope is not None and task.kind == 'readiness':
        return readiness_source_hashes(task, context)
    if task.proof_scope is not None:
        from council.proof_dependencies import resolve
        observed = resolve(task, context)
        return {**observed.hashes, '@proof:method':digest(observed.method),
            '@proof:toolchain':observed.toolchain_sha256, '@proof:runtime_mutable':digest(observed.runtime_mutable)}
    from council.tools.discovery import validate_read_path
    paths = set(task.target_files)
    for argv in task.test_commands:
        for argument in argv:
            if argument.startswith('-') or Path(argument).is_absolute():
                continue
            candidate = (Path(task.working_directory) / argument).as_posix()
            if '..' in Path(candidate).parts:
                continue
            try:
                if context.workspace_path(candidate).is_file():
                    paths.add(candidate)
            except (OSError, ValueError):
                continue
    values = {}
    for path in sorted(paths):
        try:
            target = validate_read_path(context, path)
            hasher = hashlib.sha256()
            with target.open('rb') as source:
                for block in iter(lambda: source.read(65536), b''):
                    hasher.update(block)
            values[path] = hasher.hexdigest()
        except FileNotFoundError:
            values[path] = None
    return values


def proof_boundary(state):
    if state.finalization_enabled:
        return f'delivery:{state.finalization.proof_epoch}'
    final = (state.status in {'FINAL_REVIEW', 'COMPLETED', 'GATEKEEPER_AUDIT'} or
        state.roadmap is not None and state.current_phase_index == len(state.roadmap.phases))
    return 'final' if final else f'phase:{state.current_phase_index}'


def command_digest(task, command_index):
    argv = task.test_commands[command_index-1]
    return digest([task.working_directory,argv]) if task.proof_scope else digest(argv)


def record_execution(state, task, command_index, result, context, *, source_snapshot=None, measurement=None):
    from council.plan_review import plan_digest
    identity = digest([state.run_id, state.current_phase_index, task.id, state.step_count, command_index])
    from council.governor import bindings
    inputs = source_snapshot if source_snapshot is not None else source_hashes(task,context)
    record = VerificationRecord(id=identity, run_id=state.run_id, phase_index=state.current_phase_index,
        contract_versions=bindings(state),
        task_id=task.id, graph_step=state.step_count, attempt=state.test_retry_count,
        plan_sha256=plan_digest(state.plan), command_index=command_index,
        command_sha256=command_digest(task,command_index),
        source_hashes=inputs,
        source_scope=('readiness_observation_v1' if task.kind == 'readiness' else 'project_dependencies_v1')
            if task.proof_scope else 'declared_targets_and_command_files',
        requirements_sha256=state.requirements.approved_sha256 if state.intake_enabled else None,
        validity_boundary=proof_boundary(state) if inputs.get('@proof:runtime_mutable')==digest(True) else None,
        exit_code=result.exit_code, expectation_met=bool(result.expectation_met),
        started_utc=measurement.get('started_utc') if measurement else None,
        ended_utc=measurement.get('ended_utc') if measurement else None,
        duration_seconds=measurement.get('duration_seconds') if measurement else None)
    existing = next((item for item in state.execution_records if item.id == identity), None)
    if existing is not None:
        if existing != record:
            raise DiagnosticRuntimeError('GRAPH_EVIDENCE_INVALID')
        return existing
    state.execution_records.append(record)
    return record


def matching_execution(state, task, command_index, context):
    from council.plan_review import plan_digest
    command = command_digest(task,command_index)
    plan = plan_digest(state.plan)
    phase_index = state.current_phase_index
    if (state.orchestration_policy_version == 2 and state.roadmap is not None
            and phase_index == len(state.roadmap.phases) and state.completed_phases):
        phase_index -= 1  # Final audit consumes the just-completed final plan.
    record = next((item for item in reversed(state.execution_records)
        if item.run_id == state.run_id and item.phase_index == phase_index
        and item.task_id == task.id and item.command_index == command_index), None)
    if (record is None or not record.expectation_met or record.plan_sha256 != plan
            or state.accepted_plan_sha256 != plan or record.command_sha256 != command
            or record.source_hashes != source_hashes(task, context)):
        return None
    if task.proof_scope and record.source_hashes.get('@proof:runtime_mutable')==digest(True) and record.validity_boundary != proof_boundary(state):
        return None
    if state.intake_enabled and record.requirements_sha256 != state.requirements.approved_sha256:
        return None
    from council.governor import bindings
    if record.contract_versions != bindings(state):
        return None
    return record


def require_execution(state, context):
    if not enabled(state):
        return
    for task in state.plan.tasks:
        for index in range(1, len(task.test_commands) + 1):
            if matching_execution(state, task, index, context) is None:
                raise DiagnosticRuntimeError('GRAPH_EVIDENCE_INVALID')
