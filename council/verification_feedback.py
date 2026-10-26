"""Finite verification rejection metadata; never accepts model text or argv."""

# Each reason owns its field and correction. Indices are one-based positions in
# the rejected candidate, never identities from the last valid plan.
REASONS = {
    'PROOF_COMMAND_UNSUPPORTED': ('test_commands', 'Use explicit literal dotnet restore/build/test project.csproj or solution.slnx, or dotnet run --project project.csproj. Supported flags: --no-build, --no-restore, --nologo; test --filter VALUE; run may end with an empty -- separator. Exact git diff --check is supported. Remove unresolved runtime/property arguments or supply a separately supported verification contract. Preserve the required verification outcomes.'),
    'FINALIZE_MISSING': ('delivery_stage','The last task in the final acceptance phase must be delivery_stage finalize: actual scoped code/documentation polish followed by independent verification. Preserve all accepted feature outcomes.'),
    'FINALIZE_ORDER': ('delivery_stage','Only the last task in the final acceptance phase may use delivery_stage finalize. Earlier tasks and phases use implementation.'),
    'READINESS_MISSING': ('kind', 'Add initial kind readiness tasks that establish prerequisites across the whole graph before implementation.'),
    'READINESS_ORDER': ('kind', 'Move every readiness task into an initial prefix before every implementation task.'),
    'READINESS_UNCOVERED': ('readiness_for', 'Cover this implementation task ID in an initial readiness task readiness_for list with concrete prerequisite probes.'),
    'READINESS_REFERENCE': ('readiness_for', 'Give each readiness task a nonempty list of unique existing implementation task IDs; do not reference readiness tasks.'),
    'READINESS_PHASE_REFERENCE': ('readiness_for', 'An all-readiness phase must leave every readiness_for list empty. Do not reference roadmap phase IDs, future-phase task IDs or readiness tasks. Complete and verify the current prerequisite work before planning a later phase.'),
    'READINESS_GREEN_REQUIRED': ('verification_phase', 'Readiness must use green verification and pass executable prerequisite probes before feature work.'),
    'READINESS_IMPLEMENTATION_COVERAGE': ('readiness_for', 'Only readiness tasks declare readiness_for; leave this implementation task list empty.'),
    'READINESS_PENDING_REQUIRED': ('status', 'Every proposed task must start pending; only actual successful verification completes a task.'),
    'READINESS_IMPLEMENTATION_MISSING': ('kind', 'Include implementation tasks after the readiness prefix; a plan consisting solely of readiness tasks is incomplete.'),
    'COMMANDS_EMPTY': ('test_commands', 'Declare at least one explicit verification argv array.'),
    'COMMAND_EMPTY': ('test_commands', 'Replace the empty command with a nonempty argv array.'),
    'ARGUMENT_EMPTY': ('test_commands', 'Use only nonempty string arguments in the command.'),
    'EXECUTION_POLICY_OVERRIDE': ('test_commands', 'Remove PowerShell startup execution-policy overrides, including -ep and abbreviations. Use normal trusted -NoProfile -File invocation; record a blocked check instead of bypassing native policy.'),
    'TASK_IDS_DUPLICATE': ('id', 'Give every task a unique ID and update implementation references.'),
    'GREEN_CONTRACT_PRESENT': ('red_verification', 'Remove red_verification from the green task.'),
    'RED_CONTRACT_MISSING': ('red_verification', 'Declare implementation_task_id and exact expected_failures for the red task.'),
    'RED_TARGET_COUNT': ('target_files', 'Declare between 1 and 32 test source targets for this red task.'),
    'RED_COMMAND_COUNT': ('test_commands', 'Declare between 1 and 16 commands for this red task.'),
    'RED_TARGET_TYPE': ('target_files', 'Red targets must all end in .test.ts or _test.ts; prepare production interfaces in an earlier green task.'),
    'FROZEN_TEST_TARGETED': ('target_files', 'Remove frozen red test files from every later task target list, including green implementation and audit tasks. Rerun them unchanged.'),
    'IMPLEMENTATION_MISSING': ('red_verification', 'Set implementation_task_id to an existing later green task ID.'),
    'IMPLEMENTATION_ORDER': ('red_verification', 'Place the named implementation task strictly after the red task.'),
    'IMPLEMENTATION_PHASE': ('verification_phase', 'The named later implementation task must use verification_phase green.'),
    'IMPLEMENTATION_CWD': ('working_directory', 'Use the same working directory for the red task and its named green implementation.'),
    'PLAN_RED_COMMAND_LIMIT': ('test_commands', 'Keep the total number of red commands across the plan at or below 64.'),
    'EXPECTATIONS_DUPLICATE': ('red_verification', 'Declare each command_index and exact test_name pair only once.'),
    'EXPECTATIONS_COMMANDS': ('red_verification', 'Cover every one-based red command index with expected failures, without out-of-range indices.'),
    'RED_RUNNER': ('test_commands', 'Use deno test with --reporter=junit and one explicit test source per command.'),
    'RED_REPORTER': ('test_commands', 'Include exactly one --reporter=junit argument on every red command.'),
    'RED_FLAGS': ('test_commands', 'Remove shortcut, filtering, retry, watch, alternate reporter and report-redirection flags; keep type checking enabled.'),
    'RED_SOURCE_COUNT': ('test_commands', 'Pass exactly one explicit test source argument per red command; use separate commands for separate files.'),
    'GREEN_RERUN_MISSING': ('test_commands', 'Copy this red command argv unchanged into the named later green task test_commands.'),
    'RED_SOURCE_UNDECLARED': ('target_files', 'Declare the command test source as a workspace-root-relative red target; command paths are relative to working_directory.'),
}


def safe_detail(value):
    """Revalidate mutable exception/checkpoint metadata at each output boundary."""
    if type(value) is not dict or set(value) != {'reason', 'field', 'command_index', 'related_task_index'}:
        return None
    reason = value['reason']
    if type(reason) is not str or reason not in REASONS or type(value['field']) is not str or value['field'] != REASONS[reason][0]:
        return None
    for key in ('command_index', 'related_task_index'):
        index = value[key]
        if index is not None and (type(index) is not int or not 1 <= index <= 100000):
            return None
    return dict(value)


def rejection(task_index, reason, *, command_index=None, related_task_index=None):
    from council.diagnostics import DiagnosticValueError
    return DiagnosticValueError('PLAN_VERIFICATION_INVALID', task_index=task_index,
        verification=dict(reason=reason, field=REASONS[reason][0],
            command_index=command_index, related_task_index=related_task_index))


def correction(value, *, phase_scoped=False):
    detail = safe_detail(value)
    if detail is None:
        return None
    guidance = REASONS[detail['reason']][1]
    if phase_scoped and detail['reason'] in {'READINESS_REFERENCE', 'READINESS_IMPLEMENTATION_MISSING'}:
        guidance = ('For an all-readiness phase, leave every readiness_for list empty; no implementation '
            'task is required in that phase. For mixed phase plans, give readiness tasks nonempty unique '
            'implementation task IDs from this same plan. Never reference roadmap phase IDs or future-phase tasks.')
    return {**detail, 'guidance': guidance}
