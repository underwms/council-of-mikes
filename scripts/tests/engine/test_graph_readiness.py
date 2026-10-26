"""Proactive prerequisites using the real graph, subprocesses and durable state."""
import hashlib
import json
import sys
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from council.state import CouncilState, TaskItem
from council.plan_review import plan_digest, review_request, revision_request
from council.plan_validation import validate_plan
from council.diagnostics import DiagnosticValueError
from test_engine_integration import lifecycle, open_graph
from test_autonomous_review import setup, graph_for, ACCEPT


def prepared(fixture, monkeypatch, contents=None):
    readiness = TaskItem(id='setup', specialist='the-coder', description='Prepare real prerequisite',
        kind='readiness', readiness_for=[t.id for t in fixture.plan.tasks],
        target_files=['prerequisite.txt'], acceptance_criteria=['Real prerequisite is readable'],
        test_commands=[[sys.executable, 'verify.py', 'prerequisite.txt']])
    fixture.plan.tasks.insert(0, readiness)
    state, provider, reviewer = setup(fixture, monkeypatch, [ACCEPT], contents)
    state.update(readiness_policy_version=2)
    # Feature dispatch independently asserts setup completed, beyond plan ordering.
    run_task = provider.run_task
    def checked(task, guidance, **kwargs):
        if task.id != 'setup':
            assert (fixture.workspace/'prerequisite.txt').read_text() == 'valid'
        return run_task(task, guidance, **kwargs)
    provider.run_task = checked
    return state, provider, reviewer


def run(fixture, state, provider, reviewer):
    with open_graph(fixture, provider) as saver:
        graph = graph_for(fixture, saver, provider, reviewer)
        result = graph.invoke(state, fixture.config)
        saved = graph.get_state(fixture.config).values
    return result, saved


def test_prerequisite_failure_stops_before_any_feature_work(lifecycle, monkeypatch):
    state, provider, reviewer = prepared(lifecycle, monkeypatch, {'setup': ['broken']})
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'FAILED'
    assert result['diagnostic']['code'] == 'READINESS_FAILED'
    assert provider.attempts == {'setup': 3}
    assert not list(lifecycle.workspace.glob('target-*.txt'))
    assert len(saved['test_results']) == 3


def test_setup_repair_then_real_probe_precedes_feature_work(lifecycle, monkeypatch):
    state, provider, reviewer = prepared(lifecycle, monkeypatch, {'setup': ['broken', 'valid']})
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'COMPLETED'
    assert [r['task_id'] for r in saved['test_results']] == ['setup', 'setup', 'task-1', 'task-2']
    assert provider.attempts == {'setup': 2, 'task-1': 1, 'task-2': 1}
    assert saved['test_results'][0]['exit_code'] == 7
    assert saved['test_results'][1]['exit_code'] == 0


def test_read_only_readiness_probe_skips_native_coder_and_workspace_inventory(lifecycle, monkeypatch):
    from council import native_inventory

    state, provider, reviewer = prepared(lifecycle, monkeypatch)
    setup_task = lifecycle.plan.tasks[0]
    setup_task.description = 'Verify an existing prerequisite without editing files'
    setup_task.target_files = []
    (lifecycle.workspace/'prerequisite.txt').write_text('valid', encoding='utf-8')
    inventory_calls = []
    original_snapshot = native_inventory.snapshot

    def counted_snapshot(context, relative):
        inventory_calls.append(relative)
        return original_snapshot(context, relative)

    monkeypatch.setattr(native_inventory, 'snapshot', counted_snapshot)
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert provider.attempts == {'task-1': 1, 'task-2': 1}
    assert [item['task_id'] for item in saved['test_results']] == [
        'setup', 'task-1', 'task-2']
    assert inventory_calls == ['.', '.', '.', '.']


def test_final_green_verification_without_edit_targets_needs_no_coder(lifecycle, monkeypatch):
    state, provider, reviewer = prepared(lifecycle, monkeypatch)
    lifecycle.plan.tasks.append(TaskItem(id='verify-only', specialist='the-coder',
        description='Rerun declared checks', target_files=[],
        test_commands=[[sys.executable, 'verify.py', 'target-1.txt']]))
    lifecycle.plan.tasks[0].readiness_for.append('verify-only')
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert provider.attempts == {'setup': 1, 'task-1': 1, 'task-2': 1}
    assert saved['test_results'][-1]['task_id'] == 'verify-only'
    assert saved['test_results'][-1]['expectation_met'] is True


@pytest.mark.parametrize('change,reason', [
    ('missing', 'READINESS_MISSING'), ('late', 'READINESS_ORDER'),
    ('uncovered', 'READINESS_UNCOVERED'), ('unknown', 'READINESS_REFERENCE'),
    ('duplicate', 'READINESS_REFERENCE'), ('red', 'READINESS_GREEN_REQUIRED'),
    ('implementation-coverage', 'READINESS_IMPLEMENTATION_COVERAGE'),
    ('empty', 'READINESS_REFERENCE'), ('already-completed', 'READINESS_PENDING_REQUIRED'),
    ('no-implementation', 'READINESS_IMPLEMENTATION_MISSING'),
])
def test_invalid_candidates_have_finite_actionable_correction(lifecycle, monkeypatch, change, reason):
    prepared(lifecycle, monkeypatch)
    plan = lifecycle.plan
    if change == 'missing': plan.tasks.pop(0)
    elif change == 'late': plan.tasks.append(plan.tasks.pop(0))
    elif change == 'uncovered': plan.tasks[0].readiness_for = ['task-1']
    elif change == 'unknown': plan.tasks[0].readiness_for.append('unknown')
    elif change == 'duplicate': plan.tasks[0].readiness_for.append('task-1')
    elif change == 'red': plan.tasks[0].verification_phase = 'red'
    elif change == 'implementation-coverage': plan.tasks[1].readiness_for = ['task-2']
    elif change == 'empty': plan.tasks[0].readiness_for = []
    elif change == 'already-completed': plan.tasks[0].status = 'completed'
    elif change == 'no-implementation': plan.tasks = plan.tasks[:1]
    with pytest.raises(DiagnosticValueError) as caught:
        validate_plan(plan, lifecycle.context, native_coding=True, require_readiness=True)
    assert caught.value.code == 'PLAN_VERIFICATION_INVALID'
    assert caught.value.verification['reason'] == reason
    from council.verification_feedback import correction
    assert correction(caught.value.verification)['guidance']


def test_default_fields_preserve_historical_digest(lifecycle):
    original = lifecycle.plan.model_dump(mode='json')
    original.pop('contract_changes', None)
    original.pop('quality_gates', None)
    original.pop('baseline_challenges', None)
    for task in original['tasks']:
        for key in ('status', 'verification_phase', 'red_verification', 'kind', 'readiness_for', 'proof_scope', 'delivery_stage'):
            task.pop(key, None)
    digest = hashlib.sha256(json.dumps(original, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    assert plan_digest(lifecycle.plan) == digest
    changed = lifecycle.plan.model_copy(deep=True)
    changed.tasks[0].kind = 'readiness'
    changed.tasks[0].readiness_for = ['task-2']
    assert plan_digest(changed) != digest


def test_missing_policy_is_legacy_and_strict_current_policy_roundtrips():
    assert CouncilState(run_id='old', task_input='old').readiness_policy_version == 1
    state = CouncilState(run_id='new', task_input='new', readiness_policy_version=2)
    assert CouncilState.model_validate(state.model_dump()).readiness_policy_version == 2


@pytest.mark.parametrize('value', [0, 4, True, '2', 2.0, None])
def test_policy_version_rejects_coercion(value):
    with pytest.raises(ValueError):
        CouncilState(run_id='bad', task_input='bad', readiness_policy_version=value)


def test_review_and_revision_require_whole_graph_prerequisites(lifecycle, monkeypatch):
    raw, _, _ = prepared(lifecycle, monkeypatch)
    state = CouncilState.model_validate({**raw, 'plan': lifecycle.plan.model_dump()})
    for request in (review_request(state, lifecycle.context), revision_request(state, lifecycle.context)):
        contract = request['plan_contract']['readiness']
        assert all(word in contract for word in ['permissions', 'authentication', 'readiness_for', 'services', 'lifecycle'])
    legacy = state.model_copy(update={'readiness_policy_version': 1})
    assert 'readiness' not in review_request(legacy, lifecycle.context)['plan_contract']


def test_initial_missing_readiness_enters_bounded_revision(lifecycle, monkeypatch):
    state, provider, reviewer = prepared(lifecycle, monkeypatch)
    bad = lifecycle.plan.model_copy(deep=True)
    bad.tasks.pop(0)
    state['plan'] = bad.model_dump()
    result, saved = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'COMPLETED'
    assert saved['plan_preflight_failure_count'] == 1
    assert saved['plan_revision_count'] == 1
    assert reviewer.calls == 1
    assert saved['model_calls'][0]['operation'] == 'plan_revision'


def test_worker_guard_rejects_skipped_readiness_even_with_accepted_digest(lifecycle, monkeypatch):
    from council.readiness import guard
    raw, _, _ = prepared(lifecycle, monkeypatch)
    state = CouncilState.model_validate({**raw, 'plan': lifecycle.plan.model_dump(), 'current_task_index': 1})
    state.accepted_plan_sha256 = plan_digest(state.plan)
    with pytest.raises(Exception) as caught:
        guard(state)
    assert caught.value.code == 'READINESS_NOT_MET'


def test_summary_reports_prefix_progress_without_command_or_session_data(lifecycle, monkeypatch):
    from council.readiness import summary
    raw, _, _ = prepared(lifecycle, monkeypatch)
    state = CouncilState.model_validate({**raw, 'plan': lifecycle.plan.model_dump()})
    assert summary(state)['status'] == 'pending'
    state.status = 'FAILED'
    assert summary(state)['status'] == 'blocked'
    state.plan.tasks[0].status = 'completed'
    state.test_results = [{'task_id': 'setup', 'command_index': 1, 'expectation_met': True, 'passed': True, 'exit_code': 0}]
    assert summary(state)['status'] == 'ready'
    assert summary(state)['tasks'] == [{'task_index': 1, 'status': 'completed', 'covers_task_indices': [2, 3]}]
    state.readiness_policy_version = 1
    assert summary(state) == {'policy_version': 1, 'status': 'legacy', 'tasks': []}


@pytest.mark.parametrize('evidence', [[], [dict(task_id='setup', command_index=1, expectation_met=False, passed=False, exit_code=7)]])
def test_completed_status_alone_cannot_bypass_actual_probe_evidence(lifecycle, monkeypatch, evidence):
    from council.readiness import guard, summary
    raw, _, _ = prepared(lifecycle, monkeypatch)
    state = CouncilState.model_validate({**raw, 'plan': lifecycle.plan.model_dump(), 'current_task_index': 1})
    state.plan.tasks[0].status = 'completed'
    state.test_results = evidence
    with pytest.raises(Exception) as caught:
        guard(state)
    assert caught.value.code == 'READINESS_NOT_MET'
    assert summary(state)['status'] != 'ready'


def test_revised_candidate_cannot_add_uncovered_late_work(lifecycle, monkeypatch):
    raw, provider, reviewer = prepared(lifecycle, monkeypatch)
    raw['plan'] = lifecycle.plan.model_dump()
    reviewer.decisions = iter([{'decision': 'revise', 'findings': ['Add late verification.']}])
    bad = lifecycle.plan.model_copy(deep=True)
    bad.tasks.append(bad.tasks[-1].model_copy(update={'id': 'late-check'}))
    provider.with_structured_output = lambda *args, **kw: SimpleNamespace(invoke=lambda _: {'parsed': bad, 'parsing_error': None})
    result, saved = run(lifecycle, raw, provider, reviewer)
    assert result['status'] == 'PLAN_BLOCKED'
    assert saved['plan_validation_feedback']['verification']['reason'] == 'READINESS_UNCOVERED'
    assert saved['plan_revision_count'] == 1
    assert provider.attempts == {}


def test_new_autonomous_cli_enables_readiness_and_emits_proof(lifecycle, monkeypatch, capsys):
    from council.cli import run_council_task
    monkeypatch.setattr('council.cli.ORCHESTRATION_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.GRAPH_INTEGRITY_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.GOVERNANCE_POLICY_VERSION', 1)
    raw, provider, reviewer = prepared(lifecycle, monkeypatch)
    reviewer.decisions = iter([dict(decision='accept', findings=[], resolved_finding_ids=[])])
    monkeypatch.setattr('council.graph.get_llm_for_role', lambda role, *args, **kw: reviewer if role == 'reviewer' else provider)
    monkeypatch.setattr('council.cli.preflight_credentials', lambda _: {'codex-cli': True})
    assert run_council_task(prompt='fixture', workspace_root=lifecycle.workspace,
        council_root=lifecycle.context.council_root, no_input=True) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['readiness']['policy_version'] == 3
    assert result['readiness']['status'] == 'ready'
    assert [r['task_id'] for r in result['test_results']] == ['setup', 'task-1', 'task-2']


def test_late_readiness_and_duplicate_ids_are_rejected(lifecycle, monkeypatch):
    prepared(lifecycle, monkeypatch)
    from council.readiness import validate
    late = lifecycle.plan.model_copy(deep=True)
    late.tasks.append(late.tasks[0].model_copy(update={'id': 'late-setup'}))
    with pytest.raises(DiagnosticValueError) as error:
        validate(late)
    assert error.value.verification['reason'] == 'READINESS_ORDER'
    late.tasks[-1].id = late.tasks[0].id
    with pytest.raises(DiagnosticValueError) as error:
        validate(late)
    assert error.value.verification['reason'] == 'TASK_IDS_DUPLICATE'


def test_all_probe_commands_must_have_current_successful_receipts(lifecycle, monkeypatch):
    from council.readiness import guard, summary
    raw, _, _ = prepared(lifecycle, monkeypatch)
    state = CouncilState.model_validate({**raw, 'plan': lifecycle.plan.model_dump(), 'current_task_index': 1})
    task = state.plan.tasks[0]
    task.status = 'completed'
    task.test_commands *= 2
    passed = dict(task_id='setup', expectation_met=True, passed=True, exit_code=0)
    state.test_results = [{**passed, 'command_index': 1}]
    with pytest.raises(Exception): guard(state)
    state.test_results.append({**passed, 'command_index': 2})
    guard(state)
    assert summary(state)['status'] == 'ready'
    state.test_results[-1]['exit_code'] = 7
    with pytest.raises(Exception): guard(state)
    # Legacy states do not retroactively acquire prerequisite requirements.
    state.readiness_policy_version = 1
    guard(state)


def test_summary_before_planning_and_coverage_are_digest_bound(lifecycle, monkeypatch):
    from council.readiness import summary
    state = CouncilState(run_id='new', task_input='new', readiness_policy_version=2)
    assert summary(state) == dict(policy_version=2, status='pending', tasks=[])
    prepared(lifecycle, monkeypatch)
    digest = plan_digest(lifecycle.plan)
    lifecycle.plan.tasks[0].readiness_for.pop()
    assert plan_digest(lifecycle.plan) != digest


def test_invalid_initial_readiness_exhausts_existing_revision_budget_without_coding(lifecycle, monkeypatch):
    raw, provider, reviewer = prepared(lifecycle, monkeypatch)
    raw['review_protocol_version'] = 2
    provider.plan.tasks.pop(0)
    result, saved = run(lifecycle, raw, provider, reviewer)
    assert result['status'] == 'PLAN_BLOCKED'
    assert saved['plan_revision_count'] == 5
    assert saved['plan_review_count'] == 0
    assert saved['plan_preflight_failure_count'] == 6
    assert saved['diagnostic']['code'] == 'PLAN_REVIEW_EXHAUSTED'
    assert provider.attempts == {}
