"""Finite call deadlines and safe replay boundaries shared by graph adapters."""

READ_ONLY_OPERATIONS = frozenset({
    'roadmap_inspection', 'roadmap_format_retry', 'roadmap', 'roadmap_review', 'planning_inspection',
    'planning_format_retry', 'planning', 'plan_review', 'plan_revision_inspection',
    'plan_revision_format_retry', 'plan_revision', 'strategy_reset', 'investigation',
    'intake_inspection', 'intake_draft',
    'finished_change_review',
})
STRUCTURED_OPERATIONS = frozenset({'roadmap', 'planning', 'plan_revision', 'strategy_reset'})
TRANSIENT_CLI_CODES = frozenset({'CLI_TIMEOUT', 'CLI_EXECUTION_FAILED', 'CLI_IO_FAILED', 'CLI_START_FAILED'})
INSPECTION_OPERATIONS = frozenset({'roadmap_inspection', 'planning_inspection', 'plan_revision_inspection'})
RUN_INSPECTION_LIMIT = 32


def inspection_rounds_used(state):
    """Older checkpoints may omit revision/failed rounds from their counter."""
    recorded = sum(isinstance(call.get('operation'), str) and call['operation'] in INSPECTION_OPERATIONS
                   for call in state.model_calls)
    return min(RUN_INSPECTION_LIMIT, max(state.total_inspection_rounds, recorded))


def inspection_round_limit(state):
    return min(4, RUN_INSPECTION_LIMIT - inspection_rounds_used(state)) if state.orchestration_policy_version == 2 else 12


def charge_inspection_round(state):
    """Charge one original response before dispatch; correction/retry is not a new round."""
    summary = state.planning_inspection
    if summary is None or summary.rounds_used >= summary.round_limit:
        return False
    if state.orchestration_policy_version == 2:
        used = inspection_rounds_used(state)
        if used >= RUN_INSPECTION_LIMIT:
            return False
        state.total_inspection_rounds = used + 1
    summary.rounds_used += 1
    return True


def gemini_deadline(settings, *, structured=False):
    # Legacy snapshots have no policy key and retain their original deadline.
    if settings.get('timeout_policy_version') == 3:
        return 600
    return 600 if structured and settings.get('timeout_policy_version') == 2 else 180
