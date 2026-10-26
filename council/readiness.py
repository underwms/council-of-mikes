"""Prerequisite coverage and ordering; execution reuses ordinary reviewed tasks."""
from council.diagnostics import DiagnosticRuntimeError
from council.verification_feedback import rejection

START_WORK_GUIDANCE = (
    'At this stage, judge whether the current bounded work can begin. '
    'Require the dependencies needed for that work and an executable verification path. '
    'Keep future integration and final acceptance obligations assigned to their owners. '
    'The assigned engineer may choose reversible implementation details within approved scope. '
    'Use suitable observed repository patterns; explain a concrete constraint when departing. '
    'A blocking finding must identify an unmet required outcome or a concrete correctness failure. '
    'Equivalent coverage is sufficient; a missing repeated phrase is not a defect. '
    'Acceptance of finished work still requires actual current evidence and approved scope.'
)


BASELINE_GUIDANCE = (
    'Treat established repository infrastructure and user-confirmed behavior as the working baseline. '
    'Do not require fresh proof of unchanged dependency injection, migrations, basic database CRUD, '
    'module mounting or authentication simply to permit feature development. Requalify a dependency '
    'only when the requested change materially affects it, observed evidence identifies a relevant '
    'failure, or the user explicitly requests that qualification. A baseline assumption is not a claim '
    'that a new test passed. Verify the requested change and its affected integration paths. '
    'Engineers own routine fixture and local development setup; inspect supported existing setup '
    'before declaring new credential variables, database naming conventions or fixture frameworks '
    'to be external prerequisites. Keep real permission boundaries and final acceptance evidence.'
)

TARGETED_CONTRACT = (
    'Readiness tasks are optional. An implementation-only plan is valid against the established baseline. '
    'Declare readiness only for a specific unmet or changed dependency needed by the referenced work; '
    'explain the concrete gap and its consequence. Do not invent a generic infrastructure smoke-test '
    'harness to earn permission to start. Each readiness_for list names only later implementation '
    'task IDs actually prepared by that setup; unrelated tasks need no readiness coverage. '
    'Setup may follow unrelated implementation but must precede its consumers. Readiness commands '
    'must be green and actually pass; implementation readiness_for stays empty. All tasks start pending. '
    'A prerequisite-only roadmap phase may use all-readiness tasks with empty readiness_for lists. '
) + BASELINE_GUIDANCE


def decision_boundary(*, phase_scoped, policy_version=2):
    """Describe authority at the start boundary; never grant final acceptance."""
    return {'assessment':'start_bounded_work', 'scope':'current_phase' if phase_scoped else 'current_plan',
        'instruction':START_WORK_GUIDANCE + (' ' + BASELINE_GUIDANCE if policy_version >= 3 else ''),
        'owners':{'mechanical_admission':'program', 'reversible_implementation':'engineer',
            'semantic_review':'reviewer', 'business_scope':'user', 'scheduling':'governor',
            'recovery_proposal':'arbiter'},
        'completion':'current_execution_and_acceptance_evidence'}


def review_guidance(policy_version=2):
    if policy_version >= 3:
        return (' Assess each declared readiness task for a concrete dependency gap in its referenced '
            'work. Accept no-readiness plans when no such gap is established. Require revision for '
            'unrelated baseline requalification, invented external setup obligations or acceptance '
            'that merely tests a new harness instead of the requested behavior. ' + BASELINE_GUIDANCE)
    return (' Audit prerequisites for every task in the supplied plan against plan_contract.readiness '
        'and its decision_boundary. Require real probes for dependencies needed to start that work; '
        'do not require the future feature behavior before its implementation. A declared substitute '
        'can support bounded development but is not final integrated or live-authentication proof. '
        'A genuine current prerequisite or consequential unresolved business decision remains a blocker.')


def assignment_guidance(task, policy_version=2):
    if policy_version >= 3:
        return (('Resolve only the declared concrete prerequisite for its referenced work. '
            'Reuse established setup and preserve real guards; do not expand this into generic '
            'infrastructure requalification. ' if task.kind == 'readiness' else
            'Implement and verify the requested change against the established baseline. '
            'No blanket claim that all environment dependencies were newly qualified is implied. '
            'Address concrete newly discovered blockers for the affected work. ') + BASELINE_GUIDANCE)
    if task.kind == 'readiness':
        return ('This is a readiness/setup task. Qualify the dependencies needed for the declared bounded '
            'work using real probes; do not implement later feature behavior. An unfinished downstream '
            'boundary may use a declared substitute when appropriate; retain its real integration '
            'obligation for the owning task. Preserve existing work and native policy. Accepted '
            'verification argv cannot change during execution; an incompatible command or a genuinely '
            'required unavailable authenticated session remains a blocker.')
    return ('Prerequisites were qualified for the accepted bounded work. Preserve qualified tooling and '
        'accepted verification argv; do not silently introduce new unqualified dependencies. '
        'Report newly discovered execution prerequisites explicitly. A substitute is not final integrated proof.')

_PROBES = (
    'Use existing repository tooling when possible. Inspect dependency versions and lifecycle-script '
    'policy, runtime permissions and exact argv, production module loading, services and endpoints, '
    'browser installation/launch and authentication/authorization where relevant. '
    'Readiness tasks own concrete setup files, corrections and executable probes with observable '
    'success criteria; resolve blockers to the current bounded work before that work or frozen red tests begin. '
    'Probe an existing production import/mount path and a basic event when needed to qualify the current harness. '
    'When a downstream implementation does not exist yet, a declared substitute against the observed '
    'contract may support bounded development. Keep its later real integration and acceptance obligations '
    'with their owners; do not require future feature behavior to prove permission to start. '
    'Use the same runtime capabilities and dependency resolution as later verification. '
    'A pure helper test, version output or printed success message does not prove component/browser readiness. '
    'Distinguish mocked component fixtures from live authenticated writer-session evidence; inspect how '
    'the actual test browser acquires a session, never assume the user browser login transfers. '
    'Do not bypass authentication or native policy, silently expand permissions, or embed secrets. '
    'If a prerequisite needed for the current bounded work requires unavailable credentials or a '
    'consequential unresolved user decision, report the blocker. '
    'Do not implement feature behavior in readiness tasks. Keep probes scoped and group shared '
    'prerequisites rather than inventing infrastructure every task does not need. '
    'On every revision reassess changed and newly added tasks and their prerequisites. '
    'Readiness proves prerequisites at probe time, not application correctness or every possible future failure.'
)

CONTRACT = (
    'Inspect prerequisites across the ENTIRE planned graph before implementation. Declare a nonempty '
    'initial prefix of kind readiness tasks, verification_phase green, with readiness_for listing the '
    'later implementation task IDs they prepare. Collectively cover every implementation task; '
    'implementation tasks leave readiness_for empty. All proposed tasks start pending. '
) + _PROBES

PHASE_CONTRACT = (
    'Readiness is scoped to the CURRENT phase of the accepted roadmap. readiness_for references only '
    'later implementation task IDs in this phase task plan, never roadmap phase IDs or future-phase tasks. '
    'A phase consisting entirely of prerequisites may use an all-readiness task plan: every task has '
    'kind readiness, verification_phase green, and an empty readiness_for list. Do not invent feature '
    'implementation work to qualify this phase. Each declared command must actually pass before the '
    'phase completes and the next phase can be planned. '
    'If this phase includes implementation tasks, require a nonempty initial readiness prefix whose '
    'nonempty readiness_for lists collectively cover every current-plan implementation task. '
    'Implementation tasks leave readiness_for empty. All proposed tasks start pending. '
) + _PROBES


def validate(plan, *, pending=True, phase_scoped=False, policy_version=2):
    """Require local coverage; phased prerequisite-only plans need no fake work."""
    tasks = plan.tasks
    ids = [task.id for task in tasks]
    if len(set(ids)) != len(ids):
        raise rejection(1, 'TASK_IDS_DUPLICATE')
    implementations = {task.id for task in tasks if task.kind == 'implementation'}
    readiness_only = phase_scoped and not implementations
    if not implementations and not readiness_only:
        raise rejection(1, 'READINESS_IMPLEMENTATION_MISSING')
    targeted = policy_version >= 3
    positions = {task.id: index for index, task in enumerate(tasks, 1)}
    if not targeted and tasks[0].kind != 'readiness':
        reason = 'READINESS_ORDER' if any(t.kind == 'readiness' for t in tasks) else 'READINESS_MISSING'
        raise rejection(1, reason)
    seen_implementation = False
    covered = set()
    for index, task in enumerate(tasks, 1):
        if pending and task.status != 'pending':
            raise rejection(index, 'READINESS_PENDING_REQUIRED')
        if task.kind == 'implementation':
            seen_implementation = True
            if task.readiness_for:
                raise rejection(index, 'READINESS_IMPLEMENTATION_COVERAGE')
            continue
        if seen_implementation and not targeted:
            raise rejection(index, 'READINESS_ORDER')
        if task.verification_phase != 'green':
            raise rejection(index, 'READINESS_GREEN_REQUIRED')
        references = task.readiness_for
        if readiness_only:
            if references:
                raise rejection(index, 'READINESS_PHASE_REFERENCE')
            continue
        if not references or len(set(references)) != len(references) or not set(references) <= implementations:
            raise rejection(index, 'READINESS_REFERENCE')
        if targeted and any(positions[key] <= index for key in references):
            raise rejection(index, 'READINESS_ORDER')
        covered.update(references)
    for index, task in enumerate(tasks, 1):
        if not targeted and task.kind == 'implementation' and task.id not in covered:
            raise rejection(index, 'READINESS_UNCOVERED')


def _verified(task, state):
    results = [item for item in state.test_results if item.get('task_id') == task.id]
    count = len(task.test_commands)
    return (task.status == 'completed' and count > 0 and len(results) >= count
            and all(item.get('command_index') == index and item.get('expectation_met') is True
                    and item.get('passed') is True and item.get('exit_code') == 0
                    for index, item in enumerate(results[-count:], 1)))


def guard(state):
    """Do not dispatch feature work before the accepted prerequisite prefix passes."""
    if state.readiness_policy_version not in (2, 3):
        return
    validate(state.plan, pending=False, phase_scoped=state.orchestration_policy_version == 2,
        policy_version=state.readiness_policy_version)
    if state.readiness_policy_version == 3:
        current = state.plan.tasks[state.current_task_index]
        if any(current.id in task.readiness_for and not _verified(task, state) for task in state.plan.tasks):
            raise DiagnosticRuntimeError('READINESS_NOT_MET')
        return
    if any(t.kind == 'readiness' and not _verified(t, state)
           for t in state.plan.tasks[:state.current_task_index]):
        raise DiagnosticRuntimeError('READINESS_NOT_MET')


def summary(state):
    """Expose positions and finite progress, never probe output or session material."""
    if state.readiness_policy_version not in (2, 3):
        return dict(policy_version=1, status='legacy', tasks=[])
    tasks = state.plan.tasks if state.plan else []
    positions = {task.id: index for index, task in enumerate(tasks, 1)}
    checks = [dict(task_index=index, status=task.status,
                   covers_task_indices=[positions[key] for key in task.readiness_for if key in positions])
              for index, task in enumerate(tasks, 1) if task.kind == 'readiness']
    ready = bool(checks) and all(_verified(task, state) for task in tasks if task.kind == 'readiness')
    if state.readiness_policy_version == 3 and state.plan and not checks:
        return dict(policy_version=3, status='not_required', tasks=[])
    return dict(policy_version=state.readiness_policy_version, status='ready' if ready else 'blocked' if state.status in ('FAILED', 'PLAN_BLOCKED') else 'pending', tasks=checks)
