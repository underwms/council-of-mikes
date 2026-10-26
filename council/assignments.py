"""Bounded assignment handoff assembled from retained graph observations."""
import hashlib
from pathlib import Path

GUIDANCE = (
    'The accepted task is one coherent assignment. Checklist actions are internal development steps, '
    'not separate native calls. The assigned engineer may choose reversible implementation details '
    'within approved scope and use suitable observed repository patterns; explain a concrete constraint '
    'when departing. Routine local choices do not require another human approval. Preserve public '
    'contracts, business meaning and the agreed acceptance boundary. Development steps are '
    'internal to this assignment. Use focused development checks to implement and diagnose; the independent '
    'prover executes the accepted admission commands. Do not mechanically duplicate expensive acceptance '
    'runs without a development reason. A worker report is navigation, not verification. '
    'Plan meaningful outcome boundaries with headroom for checks and handoff inside the configured deadline. '
    'Use observed durations as uncertain planning evidence, never as a precise prediction. '
    'Split or combine tasks only through normal independent plan review. Preserve models, deadlines, '
    'acceptance obligations and existing arbiter recovery; report partial work and blockers honestly.'
)


def assignment_context(state):
    from council.runtime_context import RuntimeContext
    from council.tools.discovery import validate_read_path
    context = (RuntimeContext(Path(state.council_root), Path(state.workspace_root), Path(state.memory_root))
        if state.workspace_root and state.council_root and state.memory_root else None)
    changes = []
    remaining_bytes = 64*1024*1024
    for item in state.file_changes[-32:]:
        status = 'unknown'
        if context:
            try:
                target = validate_read_path(context, item['path'])
                hasher = hashlib.sha256()
                with target.open('rb') as source:
                    while remaining_bytes>=0:
                        block = source.read(min(65536,remaining_bytes+1))
                        if not block:
                            break
                        remaining_bytes-=len(block)
                        hasher.update(block)
                status = ('unknown' if remaining_bytes<0 else 'current' if
                    hasher.hexdigest()==item.get('after_sha256') else 'changed')
            except FileNotFoundError:
                status = 'current' if item.get('after_sha256') is None else 'changed'
            except (OSError, ValueError):
                status = 'unknown'
        elif state.workspace_root:
            # Incomplete identity is never sufficient to certify a source observation.
            status = 'unknown'
        changes.append({'path':item['path'], 'sha256':item.get('after_sha256'), 'freshness':status,
            'provenance':'graph_observed_change'})
    calls = [{key:call.get(key) for key in ('call','operation','status','duration_seconds','effective_timeout_seconds')}
        for call in state.model_calls if call.get('operation') == 'worker'][-8:]
    verified = []
    if context and state.plan:
        from council.graph_integrity import matching_execution
        for task in state.plan.tasks:
            for index in range(1, len(task.test_commands)+1):
                record = matching_execution(state, task, index, context)
                if record:
                    verified.append(record.id)
    role = state.model_configuration.get('roles', {}).get('coder', {})
    return {'assignment_unit':'accepted_task', 'guidance':GUIDANCE,
        'configured_deadline_seconds':role.get('settings', {}).get('timeout_seconds'),
        'changes':changes, 'recent_worker_calls':calls, 'verified_execution_ids':verified[-32:],
        'remaining_task_ids':[t.id for t in state.plan.tasks if t.status != 'completed'] if state.plan else [],
        'limitations':['worker reports do not establish completion', 'native calls are black boxes']}
