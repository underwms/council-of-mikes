"""Actual document edits preserve unrelated requirements and reject stale proposals."""
import json

import pytest

from council.phase_contract import Phase, PhaseRoadmap, roadmap_digest
from council.plan_review import plan_digest
from council.state import CouncilState, FindingLedgerEntry, MultiSpecialistPlan, TaskItem


def edit_state(kind='roadmap'):
    state = CouncilState(run_id='edit-run', task_input='Preserve the complete feature.',
        graph_integrity_policy_version=2,
        roadmap=PhaseRoadmap(title='Feature', architecture_summary='Accepted scope', phases=[
            Phase(id='fixture', goal='Build fixture', affected_services=['api'],
                  delivered_contracts=['Shared fixture'],
                  acceptance_outcomes=['Save and assert baseline', 'Check coverage runner help'],
                  final_acceptance=True)]),
        plan=MultiSpecialistPlan(title='Fixture', architecture_summary='Preserve baseline', tasks=[
            TaskItem(id='seed', specialist='the-coder', description='Implement the fixture',
                     target_files=['api/seed.py'], acceptance_criteria=['Assert saved baseline'],
                     test_commands=[['python', 'verify.py']])]))
    finding = FindingLedgerEntry(id='F1', description='Add batch grouping assertions',
                                kind='technical', status='unresolved')
    state.review_finding_ledger = [finding]
    state = state.model_copy(update={'roadmap_finding_ledger': [finding]})
    return state


def patch_for(state, kind='roadmap', **change):
    return {'run_id': state.run_id, 'artifact': kind,
        'base_sha256': roadmap_digest(state.roadmap) if kind == 'roadmap' else plan_digest(state.plan),
        'edits': [{'op': 'add', 'path': '/phases/fixture/acceptance_outcomes/-',
                   'value_json': json.dumps('Assert three-snapshot batch'), 'reason_ids': ['F1'],
                   **change}]}


def test_unrelated_revision_cannot_drop_baseline_or_coverage_clauses():
    from council.document_edits import apply_revision
    state = edit_state()
    before = state.roadmap.model_copy(deep=True)
    candidate = apply_revision(state, patch_for(state), 'roadmap')
    assert candidate.phases[0].acceptance_outcomes == [
        'Save and assert baseline', 'Check coverage runner help', 'Assert three-snapshot batch']
    assert state.roadmap == before


@pytest.mark.parametrize('mutation', ['stale', 'wrong-run', 'unknown-finding', 'unknown-target',
    'whole-phase', 'whole-list', 'conflict', 'invalid-json', 'duplicate-json', 'bad-number'])
def test_rejected_edit_is_atomic_and_preserves_the_previous_document(mutation):
    from council.document_edits import apply_revision, RevisionRejected
    state = edit_state()
    before = state.roadmap.model_dump(mode='json')
    patch = patch_for(state)
    if mutation == 'stale': patch['base_sha256'] = '0' * 64
    if mutation == 'wrong-run': patch['run_id'] = 'another-run'
    if mutation == 'unknown-finding': patch['edits'][0]['reason_ids'] = ['F99']
    if mutation == 'unknown-target': patch['edits'][0]['path'] = '/phases/unknown/acceptance_outcomes/-'
    if mutation == 'whole-phase': patch['edits'][0].update(op='replace', path='/phases/fixture', value_json='{}')
    if mutation == 'whole-list': patch['edits'][0].update(op='replace', path='/phases/fixture/acceptance_outcomes', value_json='[]')
    if mutation == 'conflict': patch['edits'].append(dict(patch['edits'][0]))
    if mutation == 'invalid-json': patch['edits'][0]['value_json'] = '{'
    if mutation == 'duplicate-json': patch['edits'][0]['value_json'] = '{"x":1,"x":2}'
    if mutation == 'bad-number': patch['edits'][0]['value_json'] = 'NaN'
    with pytest.raises(RevisionRejected):
        apply_revision(state, patch, 'roadmap')
    assert state.roadmap.model_dump(mode='json') == before


def test_explicit_phase_insertion_preserves_existing_phase_identity_and_content():
    from council.document_edits import apply_revision
    state = edit_state()
    phase = Phase(id='readiness', goal='Check existing prerequisites', affected_services=['api'],
        delivered_contracts=['Working baseline'], acceptance_outcomes=['Build existing code'])
    patch = patch_for(state, path='/phases/readiness', value_json=phase.model_dump_json(), after_id='')
    candidate = apply_revision(state, patch, 'roadmap')
    assert [p.id for p in candidate.phases] == ['readiness', 'fixture']
    assert candidate.phases[1] == state.roadmap.phases[0]


def test_phase_plan_edit_preserves_commands_and_unrelated_acceptance():
    from council.document_edits import apply_revision
    state = edit_state('plan')
    patch = patch_for(state, 'plan', path='/tasks/seed/acceptance_criteria/-')
    candidate = apply_revision(state, patch, 'plan')
    assert candidate.tasks[0].acceptance_criteria == ['Assert saved baseline', 'Assert three-snapshot batch']
    assert candidate.tasks[0].test_commands == state.plan.tasks[0].test_commands


def test_worker_status_cannot_be_set_by_a_plan_revision():
    from council.document_edits import apply_revision, RevisionRejected
    state = edit_state('plan')
    patch = patch_for(state, 'plan', op='replace', path='/tasks/seed/status', value_json='"completed"')
    with pytest.raises(RevisionRejected): apply_revision(state, patch, 'plan')


def test_multiple_removals_resolve_against_the_same_base_indices():
    from council.document_edits import apply_revision
    state = edit_state()
    state.roadmap.phases[0].acceptance_outcomes = ['A', 'B', 'C', 'D']
    patch = patch_for(state, op='remove', path='/phases/fixture/acceptance_outcomes/0', value_json='null')
    patch['edits'].append({**patch['edits'][0], 'path': '/phases/fixture/acceptance_outcomes/2'})
    assert apply_revision(state, patch, 'roadmap').phases[0].acceptance_outcomes == ['B', 'D']


def test_preflight_can_correct_an_initial_nonpending_status_without_granting_execution():
    from council.document_edits import apply_revision
    from council.state import PlanValidationFeedback
    state = edit_state('plan')
    state.plan.tasks[0].status = 'completed'
    state.plan_validation_feedback = PlanValidationFeedback(code='PLAN_VERIFICATION_INVALID',
        task_index=1, task_id='seed', task_description='Fixture', field='status', rejected_value='completed',
        value_truncated=False)
    patch = patch_for(state, 'plan', op='replace', path='/tasks/seed/status',
        value_json='"pending"', reason_ids=['V1'])
    assert apply_revision(state, patch, 'plan').tasks[0].status == 'pending'
