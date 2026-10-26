"""Deterministic sequential scheduling; only reviewed architect plans change contracts."""
from copy import deepcopy

from council.diagnostics import DiagnosticRuntimeError, DiagnosticValueError, describe
from council.governance_contracts import WorkPieceRecord

ARCHITECT_INSTRUCTION = (
    'Act as solution architect: identify executables to build/touch and their repositories/dependencies. '
    'Bind each work piece to executable_ids. Supply solution_architecture with workable version-1 shared '
    'contracts (producer_piece, consumer_pieces, definition), localized open_questions and working assumptions, '
    'and an integration_strategy. Distinguish true dependencies from independent work even though execution '
    'is sequential. Use enough existing code to agree initial contracts; do not demand all details up front. '
    'The final piece integrates completed components and refines contracts. Engineers own routine details. '
    'Test a piece against mocks at unfinished boundaries when appropriate; verify actual integration later. ')

_LOCAL_FIELDS = (
    'plan', 'accepted_plan_sha256', 'current_task_index', 'review_finding_ledger', 'plan_review_findings',
    'plan_review_count', 'plan_revision_count', 'plan_preflight_failure_count', 'plan_validation_feedback',
    'plan_recovery_count', 'strategy_reset_count', 'recovery_review_baseline', 'recovery_revision_baseline',
    'review_no_progress_count', 'last_reviewed_plan_sha256', 'planning_inspection', 'planning_evidence',
    'planning_evidence_available', 'planning_evidence_truncated', 'phase_start_test_result_index',
    'phase_start_file_hashes', 'test_retry_count', 'last_error_hash', 'investigation_report',
    'test_result', 'document_revision_feedback', 'last_document_revision', 'repair_advice', 'governance_feedback',
    'error', 'diagnostic')

_CORRECTIONS = {
    'ARCHITECTURE_MISSING': 'Supply solution_architecture with executables, initial contracts, owned questions and integration strategy.',
    'EXECUTABLE_LINK_INVALID': 'Use unique executable IDs with known, acyclic dependencies.',
    'PIECE_EXECUTABLE_INVALID': 'Bind every piece to known executable_ids and cover all declared executables.',
    'CONTRACT_LINK_INVALID': 'Use unique initial version-1 contract IDs with known producer/consumer piece IDs.',
    'QUESTION_OWNER_INVALID': 'Use unique question IDs and assign each question to a known piece.',
    'CONTRACT_CHANGE_INVALID': 'Use unique existing contract IDs owned/consumed by this piece, current base_version, and a changed definition. Do not repeat applied changes.',
    'CONTRACT_CHANGE_LIMIT': 'The bounded contract revision budget is exhausted; retain current contracts or request a fresh decomposition.',
}


class GovernanceRejected(DiagnosticValueError):
    def __init__(self, reason):
        super().__init__('GOVERNANCE_CONTRACT_INVALID')
        self.reason = reason

    def feedback(self, artifact):
        return {'artifact': artifact, 'reason': self.reason, 'guidance': _CORRECTIONS[self.reason]}


def reject(reason):
    raise GovernanceRejected(reason)


def enabled(state):
    return state.governance_policy_version == 2


def invalid():
    raise DiagnosticRuntimeError('GRAPH_STATE_INVALID')


def validate_architecture(roadmap):
    from council.phase_contract import validate_roadmap
    validate_roadmap(roadmap)
    architecture = roadmap.solution_architecture
    if architecture is None:
        reject('ARCHITECTURE_MISSING')
    pieces = {p.id for p in roadmap.phases}
    executable_ids = {e.id for e in architecture.executables}
    if len(executable_ids) != len(architecture.executables):
        reject('EXECUTABLE_LINK_INVALID')
    dependencies = {e.id: e.depends_on for e in architecture.executables}
    visited = set()
    def visit(key, ancestors):
        if key in ancestors or key not in dependencies:
            reject('EXECUTABLE_LINK_INVALID')
        if key in visited:
            return
        if len(set(dependencies[key])) != len(dependencies[key]):
            reject('EXECUTABLE_LINK_INVALID')
        for predecessor in dependencies[key]:
            visit(predecessor, ancestors | {key})
        visited.add(key)
    for key in dependencies:
        visit(key, set())
    for piece in roadmap.phases:
        if (not piece.executable_ids or len(set(piece.executable_ids)) != len(piece.executable_ids)
                or not set(piece.executable_ids) <= executable_ids):
            reject('PIECE_EXECUTABLE_INVALID')
    if set().union(*(set(p.executable_ids) for p in roadmap.phases)) != executable_ids:
        reject('PIECE_EXECUTABLE_INVALID')
    if len({c.id for c in architecture.contracts}) != len(architecture.contracts):
        reject('CONTRACT_LINK_INVALID')
    for contract in architecture.contracts:
        if (contract.version != 1 or contract.producer_piece not in pieces
                or not set(contract.consumer_pieces) <= pieces
                or len(set(contract.consumer_pieces)) != len(contract.consumer_pieces)):
            reject('CONTRACT_LINK_INVALID')
    if (len({q.id for q in architecture.open_questions}) != len(architecture.open_questions)
            or any(q.owner_piece not in pieces for q in architecture.open_questions)):
        reject('QUESTION_OWNER_INVALID')


def initialize(state):
    from council.phase_contract import roadmap_digest
    if not enabled(state):
        return
    if (state.roadmap is None or state.accepted_roadmap_sha256 != roadmap_digest(state.roadmap)
            or state.work_pieces or state.shared_contracts or state.contract_history):
        invalid()
    validate_architecture(state.roadmap)
    state.shared_contracts = {c.id: c.model_copy(deep=True) for c in state.roadmap.solution_architecture.contracts}
    state.work_pieces = {p.id: WorkPieceRecord(id=p.id) for p in state.roadmap.phases}
    state.status = 'GOVERNOR'


def bindings(state, piece_id=None):
    if not enabled(state) or not state.work_pieces:
        return {}
    if piece_id is None:
        index = min(state.current_phase_index, len(state.roadmap.phases) - 1)
        piece_id = state.roadmap.phases[index].id
    final = state.roadmap.phases[-1].id
    return {key: contract.version for key, contract in state.shared_contracts.items()
        if piece_id in {contract.producer_piece, *contract.consumer_pieces, final}}


def schedule(state):
    from council.graph import begin_phase
    if not enabled(state) or set(state.work_pieces) != {p.id for p in state.roadmap.phases}:
        invalid()
    for index, phase in enumerate(state.roadmap.phases):
        record = state.work_pieces[phase.id]
        if record.status == 'completed' and record.verified_contract_versions != bindings(state, phase.id):
            invalid()
        if record.status in {'completed', 'blocked'}:
            continue
        if phase.final_acceptance and any(p.id != phase.id and p.status != 'completed'
                                          for p in state.work_pieces.values()):
            continue
        if not all(state.work_pieces[key].status == 'completed' for key in phase.depends_on):
            continue
        # No concurrent writers or simultaneous active pieces in this policy.
        if any(p.status in {'planning', 'reviewing', 'executing'} and p.id != phase.id
               for p in state.work_pieces.values()):
            invalid()
        state.current_phase_index = index
        begin_phase(state)
        state.planning_inspection = None
        state.test_retry_count = 0
        state.last_error_hash = None
        state.investigation_report = None
        state.error, state.diagnostic = None, None
        state.phase_start_file_hashes = {c['path']: c.get('after_sha256') for c in state.file_changes}
        record.status = 'planning'
        record.contract_versions = bindings(state, phase.id)
        return
    for index, phase in enumerate(state.roadmap.phases):
        record = state.work_pieces[phase.id]
        if record.status != 'blocked':
            continue
        raw = state.model_dump(mode='json')
        raw.update(deepcopy(record.checkpoint))
        restored = type(state).model_validate(raw)
        for key in _LOCAL_FIELDS:
            setattr(state, key, deepcopy(getattr(restored, key)))
        state.current_phase_index = index
        state.status = 'PLAN_BLOCKED'
        return
    if any(p.status != 'completed' for p in state.work_pieces.values()):
        invalid()
    state.current_phase_index = len(state.roadmap.phases)
    state.status = 'GATEKEEPER_AUDIT'


def validate_contract_changes(state, plan):
    if not enabled(state):
        if plan.contract_changes:
            reject('CONTRACT_CHANGE_INVALID')
        return
    if len({c.id for c in plan.contract_changes}) != len(plan.contract_changes):
        reject('CONTRACT_CHANGE_INVALID')
    historical_changes = sum(len(h.get('contract_history',[])) for h in state.requirements.superseded_deliveries)
    if historical_changes + len(state.contract_history) + len(plan.contract_changes) > 32:
        reject('CONTRACT_CHANGE_LIMIT')
    piece = state.roadmap.phases[state.current_phase_index].id
    for change in plan.contract_changes:
        current = state.shared_contracts.get(change.id)
        if (current is None or current.version != change.base_version or current.definition == change.definition
                or piece not in {current.producer_piece, *current.consumer_pieces, state.roadmap.phases[-1].id}):
            reject('CONTRACT_CHANGE_INVALID')


def accept_contract_changes(state):
    from council.plan_review import plan_digest
    if state.plan is None or state.accepted_plan_sha256 != plan_digest(state.plan):
        invalid()
    validate_contract_changes(state, state.plan)
    if not state.plan.contract_changes:
        return
    affected = set()
    for change in state.plan.contract_changes:
        contract = state.shared_contracts[change.id]
        affected.update([contract.producer_piece, *contract.consumer_pieces, state.roadmap.phases[-1].id])
    for phase in state.roadmap.phases:
        if set(phase.depends_on) & affected:
            affected.add(phase.id)
    # All proposals validated above: no partially applied contract batch.
    for change in state.plan.contract_changes:
        current = state.shared_contracts[change.id]
        updated = current.model_copy(update={'version': current.version + 1, 'definition': change.definition})
        state.shared_contracts[change.id] = updated
        state.contract_history.append({'id': change.id, 'before': current.model_dump(mode='json'),
            'after': updated.model_dump(mode='json'), 'reason': change.reason,
            'architect_piece': state.roadmap.phases[state.current_phase_index].id,
            'architect_plan_sha256': state.accepted_plan_sha256, 'review_step': state.step_count})
    active_id = state.roadmap.phases[state.current_phase_index].id
    prior_invalidated = False
    for phase in state.roadmap.phases:
        if phase.id in affected:
            record = state.work_pieces[phase.id]
            if record.status == 'completed':
                prior_invalidated = True
            record.status = 'needs_revision'
    state.work_pieces[active_id].contract_versions = bindings(state, active_id)
    if prior_invalidated:
        state.status = 'GOVERNOR'
    else:
        state.work_pieces[active_id].status = 'executing'


def capture_piece(state, node):
    from council.plan_review import plan_digest
    if not enabled(state) or not state.work_pieces or state.current_phase_index >= len(state.roadmap.phases):
        return
    record = state.work_pieces[state.roadmap.phases[state.current_phase_index].id]
    payload = state.model_dump(mode='json', include=set(_LOCAL_FIELDS))
    record.checkpoint = payload
    if state.plan is not None:
        sha = plan_digest(state.plan)
        if not record.plan_versions or record.plan_versions[-1]['sha256'] != sha:
            record.plan_versions.append({'sha256': sha, 'plan': state.plan.model_dump(mode='json'), 'step': state.step_count})
    if node in {'plan_review', 'plan_blocked'}:
        record.review_history.append({'step': state.step_count, 'status': state.status,
            'accepted_plan_sha256': state.accepted_plan_sha256,
            'finding_ledger': [f.model_dump(mode='json') for f in state.review_finding_ledger],
            'review_count': state.plan_review_count, 'revision_count': state.plan_revision_count})
    record.execution_record_ids = [r.id for r in state.execution_records if r.phase_index == state.current_phase_index]
    if node == 'phase_complete' and state.status == 'GOVERNOR':
        record.status = 'completed'
        record.verified_contract_versions = bindings(state)
        record.completion_history.append({'plan_sha256': state.accepted_plan_sha256,
            'contract_versions': bindings(state), 'execution_record_ids': list(record.execution_record_ids),
            'step': state.step_count})
    elif state.status == 'GOVERNOR':
        pass  # Reviewed refinement may have invalidated this piece.
    elif state.status == 'PLAN_BLOCKED':
        record.status = 'blocked'
    elif state.status in {'PLAN_REVIEW', 'PLAN_REVISION', 'PLAN_PREFLIGHT_RETRY', 'STRATEGY_RESET'}:
        record.status = 'reviewing'
    elif state.status in {'EXECUTING', 'TESTING', 'RETRYING', 'GATEKEEPER_AUDIT'}:
        record.status = 'executing'


def prompt_context(state):
    if not enabled(state):
        return {}
    records = {}
    for key, record in state.work_pieces.items():
        records[key] = {
            'id': record.id, 'status': record.status,
            'contract_versions': dict(record.contract_versions),
            'verified_contract_versions': dict(record.verified_contract_versions),
            'latest_plan': deepcopy(record.checkpoint.get('plan')),
            'accepted_plan_sha256': record.checkpoint.get('accepted_plan_sha256'),
            'plan_versions': [{k: deepcopy(v) for k, v in version.items() if k != 'plan'}
                              for version in record.plan_versions],
            'review_history': deepcopy(record.review_history),
            'execution_record_ids': list(record.execution_record_ids),
            'completion_history': deepcopy(record.completion_history),
        }
    return {'solution_architecture': state.roadmap.solution_architecture.model_dump(mode='json') if state.roadmap and state.roadmap.solution_architecture else None,
        'shared_contracts': {key: value.model_dump(mode='json') for key, value in state.shared_contracts.items()},
        'work_piece_records': records,
        'contract_history': deepcopy(state.contract_history),
        'contract_rule': 'Only the solution architect proposes contract_changes in a piece plan; independent plan review '
            'accepts them. Use current base_version and explain the concrete discovery. Completed affected work is '
            'replanned and reverified. Keep unrelated decisions intact. Do not repeat already-applied changes. '
            'The governor only coordinates. Local unknowns and routine engineering details do not block unrelated work.'}


def verify_transition(before, after, node):
    """Replay governance projections, so node ownership cannot authorize forged history."""
    if not enabled(before):
        if any(getattr(before, key) != getattr(after, key) for key in
               ('work_pieces', 'shared_contracts', 'contract_history')):
            invalid()
        return
    expected = after.model_copy(deep=True)
    for key in ('work_pieces', 'shared_contracts', 'contract_history'):
        setattr(expected, key, deepcopy(getattr(before, key)))
    if node == 'proof_refresh':
        expected = before.model_copy(deep=True)
        restore_for_proof(expected)
    elif node == 'requirements_gate' and before.requirements.reopening and not after.requirements.reopening:
        expected.work_pieces, expected.shared_contracts, expected.contract_history = {}, {}, []
    elif node == 'roadmap_review' and before.accepted_roadmap_sha256 is None and after.accepted_roadmap_sha256:
        initialize(expected)
    elif node == 'governor':
        expected = before.model_copy(deep=True)
        schedule(expected)
        if expected.status != after.status or expected.current_phase_index != after.current_phase_index:
            invalid()
        for key in _LOCAL_FIELDS:
            if getattr(expected, key) != getattr(after, key):
                invalid()
    elif node == 'plan_review' and after.accepted_plan_sha256:
        accept_contract_changes(expected)
        if expected.status != after.status:
            invalid()
    capture_piece(expected, node)
    for key in ('work_pieces', 'shared_contracts', 'contract_history'):
        if getattr(expected, key) != getattr(after, key):
            invalid()


def restore_for_proof(state):
    from council.finalization import piece_probe
    if not enabled(state) or state.proof_refresh_piece is None or state.roadmap is None:
        invalid()
    index,reason = state.proof_refresh_piece,state.proof_refresh_reason
    record = state.work_pieces.get(state.roadmap.phases[index].id)
    if record is None or record.status!='completed' or not record.checkpoint:
        invalid()
    probe = piece_probe(state,index)
    for key in _LOCAL_FIELDS:
        setattr(state,key,deepcopy(getattr(probe,key)))
    state.current_phase_index = index
    state.current_task_index = len(state.plan.tasks)
    record.status='executing'
    state.proof_refresh_piece,state.proof_refresh_reason=None,None
    state.status='FAILED' if reason=='stale' else 'GATEKEEPER_AUDIT'
    state.diagnostic=describe(DiagnosticRuntimeError('GRAPH_EVIDENCE_INVALID')) if reason=='stale' else None
