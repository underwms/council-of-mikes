"""Delivery governance uses actual state and existing integrity checks."""
import hashlib
import json
import pytest

from council.state import CouncilState, MultiSpecialistPlan, TaskItem
from council.phase_contract import PhaseRoadmap, roadmap_digest, validate_roadmap
from council.plan_review import plan_digest


def architecture():
    return {
        'executables': [
            {'id': 'db', 'kind': 'database', 'repository': 'api', 'depends_on': []},
            {'id': 'api', 'kind': 'api', 'repository': 'api', 'depends_on': ['db']},
            {'id': 'ui', 'kind': 'ui', 'repository': 'ui', 'depends_on': ['api']}],
        'contracts': [{'id': 'audit', 'producer_piece': 'db', 'consumer_pieces': ['api', 'integration'],
                       'version': 1, 'definition': 'Audit row includes before and after values'}],
        'open_questions': [{'id': 'q1', 'owner_piece': 'integration', 'description': 'Historical null display',
                            'assumption': 'Follow existing UI null handling'}],
        'integration_strategy': 'Wire persisted rows through API and UI; verify actual feature end to end'}


def governed_state():
    roadmap = PhaseRoadmap.model_validate(dict(title='Audit', architecture_summary='DB then API then integration',
        solution_architecture=architecture(), phases=[dict(id=key, goal=key, affected_services=[key],
            executable_ids=executables, delivered_contracts=['audit'], acceptance_outcomes=['Works'],
            depends_on=deps, final_acceptance=key == 'integration')
            for key, executables, deps in [('db', ['db'], []), ('api', ['api'], ['db']),
                                            ('integration', ['ui', 'api'], ['api'])]]))
    state = CouncilState(run_id='fresh', thread_id='fresh', task_input='Audit feature',
        governance_policy_version=2, orchestration_policy_version=2, roadmap=roadmap,
        accepted_roadmap_sha256=roadmap_digest(roadmap))
    assert state.governance_policy_version == 2
    return state


def plan(change=False):
    return MultiSpecialistPlan.model_validate(dict(title='Piece', architecture_summary='Implement boundary',
        tasks=[dict(id='work', specialist='the-coder', description='Implement',
                    test_commands=[['python', 'verify.py']])],
        contract_changes=[dict(id='audit', base_version=1, definition='Audit row adds current value',
                               reason='Integration discovery requires current values')] if change else []))


def test_legacy_hashes_and_policy_remain_unchanged():
    state = CouncilState(run_id='old', task_input='old')
    assert getattr(state, 'governance_policy_version', None) == 1
    roadmap_data = dict(title='Old', architecture_summary='Old', phases=[dict(id='one', goal='Old',
        affected_services=['old'], required_inputs=[], delivered_contracts=['Old'], acceptance_outcomes=['Old'],
        depends_on=[], final_acceptance=True)])
    expected = hashlib.sha256(json.dumps(roadmap_data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert roadmap_digest(PhaseRoadmap.model_validate(roadmap_data)) == expected
    old_plan = dict(title='Old', architecture_summary='Old', affected_services=[], tasks=[dict(id='one',
        specialist='the-coder', description='Old', target_files=[], acceptance_criteria=[], test_commands=[],
        working_directory='.')])
    expected = hashlib.sha256(json.dumps(old_plan, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    assert plan_digest(MultiSpecialistPlan.model_validate(old_plan)) == expected


def test_governor_starts_one_dependency_ready_piece_and_preserves_other_records():
    from council.governor import initialize, schedule, capture_piece
    state = governed_state()
    initialize(state)
    schedule(state)
    assert state.current_phase_index == 0
    assert state.work_pieces['db'].status == 'planning'
    assert [p.status for p in state.work_pieces.values()].count('planning') == 1
    state.plan = plan()
    state.status = 'PLAN_REVIEW'
    capture_piece(state, 'architect')
    state.plan_review_count = 1
    state.status = 'EXECUTING'
    state.accepted_plan_sha256 = plan_digest(state.plan)
    capture_piece(state, 'plan_review')
    db = state.work_pieces['db'].model_copy(deep=True)
    db.status = 'completed'
    state.work_pieces['db'].status = 'completed'
    state.work_pieces['db'].verified_contract_versions = {'audit': 1}
    db = state.work_pieces['db'].model_copy(deep=True)
    schedule(state)
    assert state.current_phase_index == 1
    assert state.work_pieces['db'] == db
    assert state.work_pieces['db'].review_history[0]['accepted_plan_sha256']
    assert state.work_pieces['db'].plan_versions[0]['plan'] == plan().model_dump(mode='json')
    assert state.plan is None and state.plan_review_count == 0
    assert state.work_pieces['api'].contract_versions == {'audit': 1}


def test_reviewed_architect_refinement_reopens_affected_completed_work_and_dependents():
    from council.governor import initialize, schedule, accept_contract_changes, capture_piece
    state = governed_state()
    initialize(state)
    state.work_pieces['db'].status = 'completed'
    state.work_pieces['db'].verified_contract_versions = {'audit': 1}
    schedule(state)
    state.plan = plan(change=True)
    state.status = 'PLAN_REVIEW'
    capture_piece(state, 'architect')
    assert state.shared_contracts['audit'].version == 1
    state.accepted_plan_sha256 = plan_digest(state.plan)
    state.status = 'EXECUTING'
    accept_contract_changes(state)
    assert state.shared_contracts['audit'].version == 2
    assert state.work_pieces['db'].status == 'needs_revision'
    assert state.work_pieces['api'].status == 'needs_revision'
    assert state.work_pieces['integration'].status == 'needs_revision'
    assert state.contract_history[0]['architect_plan_sha256'] == state.accepted_plan_sha256
    schedule(state)
    assert state.current_phase_index == 0
    assert state.work_pieces['db'].contract_versions == {'audit': 2}


@pytest.mark.parametrize('mutation', ['stale', 'unknown', 'duplicate', 'unaccepted'])
def test_contract_changes_reject_invalid_proposals_atomically(mutation):
    from council.governor import initialize, schedule, accept_contract_changes
    state = governed_state()
    initialize(state)
    schedule(state)
    state.plan = plan(change=True)
    if mutation == 'stale': state.plan.contract_changes[0].base_version = 4
    if mutation == 'unknown': state.plan.contract_changes[0].id = 'unknown'
    if mutation == 'duplicate': state.plan.contract_changes.append(state.plan.contract_changes[0].model_copy())
    if mutation != 'unaccepted': state.accepted_plan_sha256 = plan_digest(state.plan)
    snapshot = state.shared_contracts.copy()
    with pytest.raises(Exception): accept_contract_changes(state)
    assert state.shared_contracts == snapshot and state.contract_history == []


def test_fresh_runs_do_not_inherit_governance_records():
    from council.governor import initialize
    first, second = governed_state(), governed_state()
    initialize(first)
    first.work_pieces['db'].status = 'blocked'
    assert second.work_pieces == {} and second.shared_contracts == {}


@pytest.mark.parametrize('mutation', ['missing', 'cycle', 'unknown_piece', 'missing_executable'])
def test_architecture_validates_real_links_without_requiring_every_unknown_resolved(mutation):
    from council.governor import initialize
    state = governed_state()
    if mutation == 'missing': state.roadmap.solution_architecture = None
    if mutation == 'cycle': state.roadmap.solution_architecture.executables[0].depends_on = ['ui']
    if mutation == 'unknown_piece': state.roadmap.solution_architecture.contracts[0].consumer_pieces = ['missing']
    if mutation == 'missing_executable': state.roadmap.phases[1].executable_ids = []
    with pytest.raises(Exception): initialize(state)
    assert state.work_pieces == {}


def test_governed_graph_replans_changed_contract_and_preserves_piece_histories(current_autonomous_run):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from council.graph import build_council_graph
    from test_engine_integration import open_graph
    from test_integrity_lifecycle import frame_from
    from test_autonomous_review import Reviewer
    run = current_autonomous_run
    run.state['governance_policy_version'] = 2
    roadmap = governed_state().roadmap
    requests, reviews = [], []
    def structured(schema, **kwargs):
        def invoke(messages):
            frame = frame_from(messages)
            if schema is PhaseRoadmap:
                value = roadmap
            else:
                assert schema is MultiSpecialistPlan
                piece = frame['records']['phase']['id']
                requests.append(piece)
                value = run.fixture.plan.model_copy(deep=True)
                value.title = piece
                if piece == 'integration' and requests.count(piece) == 1:
                    value.contract_changes = plan(True).contract_changes
            return {'parsed': value, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    run.provider.with_structured_output = structured
    reviewer = Reviewer([{'decision': 'accept', 'findings': [], 'resolved_finding_ids': []}] * 12)
    original = reviewer.review_plan
    def review(request):
        reviews.append(request)
        return original(request)
    reviewer.review_plan = review
    with open_graph(run.fixture, run.provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=run.fixture.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else run.provider)
        result = graph.invoke(run.state, run.fixture.config)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert requests == ['db', 'api', 'integration', 'db', 'api', 'integration']
    assert result['shared_contracts']['audit']['version'] == 2
    assert len(result['contract_history']) == 1
    assert len(result['completed_phases']) == 5
    assert all(record['status'] == 'completed' for record in result['work_pieces'].values())
    assert len(result['work_pieces']['db']['completion_history']) == 2
    assert len(result['work_pieces']['integration']['review_history']) == 2
    assert result['work_pieces']['db']['verified_contract_versions'] == {'audit': 2}
    assert any(r['contract_versions'] == {'audit': 1} for r in result['execution_records'])
    assert any(r['contract_versions'] == {'audit': 2} for r in result['execution_records'])
    assert any(e['node'] == 'governor' for e in result['integrity_events'])
    assert reviews[-1]['shared_context']['records']['work_piece_records']['db']['completion_history']


def test_worker_cannot_rewrite_another_piece_or_contracts():
    from council.graph_integrity import seal_state, check_transition
    from council.governor import initialize, schedule
    state = governed_state()
    state.graph_integrity_policy_version = 2
    seal_state(state)
    initialize(state)
    schedule(state)
    after = state.model_copy(deep=True)
    after.work_pieces['api'].status = 'completed'
    with pytest.raises(Exception): check_transition(state, after, 'worker')
    after = state.model_copy(deep=True)
    after.work_pieces['db'].completion_history.append({'plan_sha256': 'a' * 64})
    with pytest.raises(Exception): check_transition(state, after, 'worker')
    after = state.model_copy(deep=True)
    after.shared_contracts['audit'].definition = 'Worker bypass'
    with pytest.raises(Exception): check_transition(state, after, 'worker')


def test_verification_is_bound_to_contract_versions(graph_workspace):
    from council.graph_integrity import record_execution, matching_execution
    from council.governor import initialize, schedule
    from council.state import TestExecutionResult
    from council.runtime_context import RuntimeContext
    state = governed_state()
    initialize(state)
    schedule(state)
    state.graph_integrity_policy_version = 2
    state.plan = plan()
    state.accepted_plan_sha256 = plan_digest(state.plan)
    context = graph_workspace.context
    record_execution(state, state.plan.tasks[0], 1,
        TestExecutionResult(command='python verify.py', passed=True, exit_code=0, expectation_met=True), context)
    assert matching_execution(state, state.plan.tasks[0], 1, context)
    state.shared_contracts['audit'].version = 2
    assert matching_execution(state, state.plan.tasks[0], 1, context) is None


def test_architecture_and_contract_changes_support_atomic_targeted_revision():
    from council.document_edits import apply_revision, document_digest
    from council.state import FindingLedgerEntry
    state = governed_state()
    state.roadmap_finding_ledger = [FindingLedgerEntry(id='F1', description='Clarify boundary', kind='technical', status='unresolved')]
    proposal = dict(run_id=state.run_id, artifact='roadmap', base_sha256=roadmap_digest(state.roadmap), edits=[
        dict(op='replace', path='/solution_architecture/contracts/audit/definition', value='Explicit before and after values', reason_ids=['F1']),
        dict(op='replace', path='/solution_architecture/open_questions/q1/assumption', value='Use an empty label', reason_ids=['F1'])])
    revised = apply_revision(state, proposal, 'roadmap')
    assert revised.solution_architecture.contracts[0].definition == 'Explicit before and after values'
    assert state.roadmap.solution_architecture.contracts[0].definition != revised.solution_architecture.contracts[0].definition
    state.plan = plan()
    state.review_finding_ledger = state.roadmap_finding_ledger
    proposal.update(artifact='plan', base_sha256=plan_digest(state.plan), edits=[
        dict(op='add', path='/contract_changes/-', value=plan(True).contract_changes[0].model_dump(mode='json'), reason_ids=['F1'])])
    assert apply_revision(state, proposal, 'plan').contract_changes[0].base_version == 1


def test_current_fixture_enables_governance_for_fresh_runs(current_autonomous_run):
    assert current_autonomous_run.state['governance_policy_version'] == 2


def test_model_context_keeps_current_piece_data_without_replaying_every_old_plan():
    from council.governor import initialize, schedule, capture_piece, prompt_context
    state = governed_state()
    initialize(state)
    schedule(state)
    for index in range(3):
        state.plan = plan()
        state.plan.title = f'Revision {index}'
        capture_piece(state, 'architect')
    context = prompt_context(state)
    record = context['work_piece_records']['db']
    assert record['latest_plan']['title'] == 'Revision 2'
    assert len(record['plan_versions']) == 3
    assert all('plan' not in entry for entry in record['plan_versions'])
    assert len(state.work_pieces['db'].plan_versions) == 3
    assert all('plan' in entry for entry in state.work_pieces['db'].plan_versions)


def test_invalid_initial_architecture_gets_bounded_targeted_correction(current_autonomous_run):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from council.document_edits import DocumentRevision
    from council.graph import build_council_graph
    from test_engine_integration import open_graph
    from test_integrity_lifecycle import frame_from
    run = current_autonomous_run
    original = run.provider.with_structured_output
    repaired = []
    def structured(schema, **kwargs):
        if schema is PhaseRoadmap:
            handler = original(schema, **kwargs)
            def invoke(messages):
                result = handler.invoke(messages)
                result['parsed'].solution_architecture = None
                return result
            return SimpleNamespace(invoke=invoke)
        if schema is DocumentRevision:
            def revise(messages):
                frame = frame_from(messages)
                roadmap = PhaseRoadmap.model_validate(frame['records']['roadmap'])
                repaired.append(True)
                return {'parsed': dict(run_id=frame['run_id'], artifact='roadmap', base_sha256=roadmap_digest(roadmap), edits=[
                    dict(op='replace', path='/solution_architecture', reason_ids=['V1'], value={
                        'executables': [dict(id='fixture', kind='console', repository='.', depends_on=[])],
                        'contracts': [], 'open_questions': [], 'integration_strategy': 'Verify actual fixture subprocesses'})]),
                    'raw': AIMessage(content=''), 'parsing_error': None}
            return SimpleNamespace(invoke=revise)
        return original(schema, **kwargs)
    run.provider.with_structured_output = structured
    with open_graph(run.fixture, run.provider) as saver:
        result = run.build(saver).invoke(run.state, run.fixture.config)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert repaired == [True]
    assert result['roadmap_revision_count'] == 1


def test_only_invalidated_piece_test_freezes_are_released_for_reviewed_rework():
    from council.governor import initialize, schedule
    from council.graph import all_frozen_evidence
    from council.state import RedPhaseEvidence
    state = governed_state()
    initialize(state)
    for piece in ('db', 'api'):
        record = state.work_pieces[piece]
        record.status = 'completed'
        record.verified_contract_versions = {'audit': 1}
        record.completion_history = [{'plan_sha256': 'a' * 64}]
        state.completed_red_phase_evidence.append(RedPhaseEvidence(red_task_id='red', green_task_id='green',
            command_index=1, test_names=['Check'], source_hashes={f'{piece}/test.py': 'b' * 64}, closed=True,
            piece_id=piece, plan_sha256='a' * 64, contract_versions={'audit': 1}))
    assert len(all_frozen_evidence(state)) == 2
    state.work_pieces['db'].status = 'needs_revision'
    assert [e.piece_id for e in all_frozen_evidence(state)] == ['api']
    assert len(state.completed_red_phase_evidence) == 2  # History is retained.


def test_blocked_piece_survives_sqlite_restart_and_feedback(current_autonomous_run):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from langgraph.types import Command
    from council.document_edits import DocumentRevision
    from council.graph import build_council_graph
    from test_engine_integration import open_graph
    from test_integrity_lifecycle import frame_from
    from test_autonomous_review import Reviewer
    run = current_autonomous_run
    roadmap = governed_state().roadmap
    from council.phase_contract import Phase
    roadmap.phases.insert(2, Phase(id='independent', goal='Independent feature behavior', affected_services=['api'],
        executable_ids=['api'], delivered_contracts=['Independent behavior'], acceptance_outcomes=['Works']))
    def structured(schema, **kwargs):
        def invoke(messages):
            frame = frame_from(messages)
            if schema is PhaseRoadmap: value = roadmap
            elif schema is DocumentRevision:
                current = MultiSpecialistPlan.model_validate(frame['records']['plan'])
                value = dict(run_id=frame['run_id'], artifact='plan', base_sha256=plan_digest(current), edits=[
                    dict(op='add', path='/tasks/task-1/acceptance_criteria/-', value='User chose existing null display', reason_ids=['U1'])])
            else: value = run.fixture.plan.model_copy(deep=True)
            return {'parsed': value, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    run.provider.with_structured_output = structured
    accept = dict(decision='accept', findings=[], resolved_finding_ids=[])
    reviewer = Reviewer([accept, accept, dict(decision='escalate', findings=[
        dict(id='F1', description='Choose existing display', kind='user_decision')], resolved_finding_ids=[]), accept, accept, accept])
    def build(saver):
        return build_council_graph(checkpointer=saver, context=run.fixture.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else run.provider)
    with open_graph(run.fixture, run.provider) as saver:
        paused = build(saver).invoke(run.state, run.fixture.config)
    assert paused['__interrupt__']
    assert paused['work_pieces']['api']['status'] == 'blocked'
    assert paused['work_pieces']['independent']['status'] == 'completed'
    previous_db = paused['work_pieces']['db']
    with open_graph(run.fixture, run.provider) as saver:
        result = build(saver).invoke(Command(resume={'feedback': 'Use the existing null display'}), run.fixture.config)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert result['work_pieces']['db'] == previous_db
    assert result['work_pieces']['independent'] == paused['work_pieces']['independent']
    api = result['work_pieces']['api']
    assert len(api['plan_versions']) == 2
    assert any(r['status'] == 'PLAN_BLOCKED' for r in api['review_history'])
    assert api['checkpoint']['plan_recovery_count'] == 1


def test_governor_finishes_independent_work_before_asking_about_blocked_piece():
    from council.governor import initialize, schedule, capture_piece
    from council.phase_contract import Phase
    state = governed_state()
    state.roadmap.phases.insert(1, Phase(id='independent', goal='Independent cleanup for feature',
        affected_services=['api'], executable_ids=['api'], delivered_contracts=['Independent behavior'],
        acceptance_outcomes=['Works']))
    state.accepted_roadmap_sha256 = roadmap_digest(state.roadmap)
    initialize(state)
    schedule(state)
    state.plan = plan()
    state.plan_review_count = 1
    state.plan_review_findings = ['User decision for db']
    state.status = 'PLAN_BLOCKED'
    capture_piece(state, 'plan_review')
    original = state.work_pieces['db'].model_copy(deep=True)
    schedule(state)
    assert state.current_phase_index == 1
    assert state.work_pieces['db'] == original
    state.work_pieces['independent'].status = 'completed'
    state.work_pieces['independent'].verified_contract_versions = {}
    schedule(state)
    assert state.current_phase_index == 0 and state.status == 'PLAN_BLOCKED'
    assert state.plan_review_count == 1 and state.plan_review_findings == ['User decision for db']


@pytest.mark.parametrize('path,value', [
    ('/solution_architecture/integration_strategy', 'Verify persisted values across required boundaries'),
    ('/solution_architecture/executables/db/repository', 'existing-api'),
    ('/solution_architecture/executables/ui/depends_on/0', 'db'),
    ('/solution_architecture/contracts/audit/definition', 'Before, after and current'),
    ('/solution_architecture/open_questions/q1/assumption', 'Use existing display'),
    ('/contract_changes/audit/base_version', 1),
    ('/contract_changes/audit/definition', 'A refined contract'),
])
def test_targeted_governance_scalars_preserve_unrelated_requirements(path, value):
    from council.document_edits import apply_revision, document_digest
    from council.state import FindingLedgerEntry
    state = governed_state()
    state.plan = plan(True)
    state.review_finding_ledger = state.roadmap_finding_ledger = [FindingLedgerEntry(
        id='F1', description='Refine one field', kind='technical', status='unresolved')]
    kind = 'plan' if path.startswith('/contract_changes') else 'roadmap'
    revised = apply_revision(state, dict(run_id=state.run_id, artifact=kind,
        base_sha256=document_digest(getattr(state, kind), kind), edits=[
            dict(op='replace', path=path, value=value, reason_ids=['F1'])]), kind)
    assert revised.title == getattr(state, kind).title
    assert revised.architecture_summary == getattr(state, kind).architecture_summary


def test_invalid_contract_proposal_is_corrected_before_independent_review(current_autonomous_run):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from council.document_edits import DocumentRevision
    from test_engine_integration import open_graph
    from test_integrity_lifecycle import frame_from
    run = current_autonomous_run
    original = run.provider.with_structured_output
    revisions = []
    def structured(schema, **kwargs):
        if schema is MultiSpecialistPlan:
            value = run.fixture.plan.model_copy(deep=True)
            value.contract_changes = plan(True).contract_changes  # Unknown contract in a contract-free fixture.
            return SimpleNamespace(invoke=lambda messages: {'parsed': value, 'raw': AIMessage(content=''), 'parsing_error': None})
        if schema is DocumentRevision:
            def revise(messages):
                frame = frame_from(messages)
                current = MultiSpecialistPlan.model_validate(frame['records']['plan'])
                revisions.append(True)
                return {'parsed': dict(run_id=frame['run_id'], artifact='plan', base_sha256=plan_digest(current),
                    edits=[dict(op='remove', path='/contract_changes/0', value=None, reason_ids=['V1'])]),
                    'raw': AIMessage(content=''), 'parsing_error': None}
            return SimpleNamespace(invoke=revise)
        return original(schema, **kwargs)
    run.provider.with_structured_output = structured
    with open_graph(run.fixture, run.provider) as saver:
        result = run.build(saver).invoke(run.state, run.fixture.config)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert revisions == [True] and result['governance_feedback'] is None
    assert result['work_pieces']['fixture']['checkpoint']['plan_preflight_failure_count'] == 1


def test_producer_can_refine_contract_before_any_completed_consumer_needs_rework():
    from council.governor import initialize, schedule, accept_contract_changes
    state = governed_state()
    initialize(state)
    schedule(state)
    state.plan = plan(True)
    state.accepted_plan_sha256 = plan_digest(state.plan)
    state.status = 'EXECUTING'
    accept_contract_changes(state)
    assert state.status == 'EXECUTING' and state.work_pieces['db'].status == 'executing'
    assert state.work_pieces['db'].contract_versions == {'audit': 2}


def test_final_integration_waits_for_every_piece_even_when_its_direct_dependency_is_ready():
    from council.governor import initialize, schedule, capture_piece, bindings
    from council.phase_contract import Phase
    state = governed_state()
    state.roadmap.phases.insert(2, Phase(id='independent', goal='Independent required behavior',
        affected_services=['api'], executable_ids=['api'], delivered_contracts=['Required behavior'],
        acceptance_outcomes=['Works']))
    state.accepted_roadmap_sha256 = roadmap_digest(state.roadmap)
    initialize(state)
    for key in ('db', 'api'):
        state.work_pieces[key].status = 'completed'
        state.work_pieces[key].verified_contract_versions = bindings(state, key)
    state.current_phase_index = 2
    state.plan = plan()
    state.status = 'PLAN_BLOCKED'
    capture_piece(state, 'plan_review')
    schedule(state)
    assert state.status == 'PLAN_BLOCKED' and state.current_phase_index == 2
    assert state.work_pieces['integration'].status == 'pending'


@pytest.mark.parametrize('write_before_failure', [False, True])
def test_worker_failure_preserves_original_diagnostic_and_real_partial_evidence(current_autonomous_run, write_before_failure):
    from council.diagnostics import DiagnosticRuntimeError
    from test_engine_integration import open_graph
    run = current_autonomous_run
    def fail(task, guidance, **kwargs):
        if write_before_failure:
            (run.fixture.workspace / task.target_files[0]).write_text('partial', encoding='utf-8')
        raise DiagnosticRuntimeError('CLI_EXECUTION_FAILED')
    run.provider.run_task = fail
    with open_graph(run.fixture, run.provider) as saver:
        result = run.build(saver).invoke(run.state, run.fixture.config)
    assert result['status'] == 'FAILED'
    assert result['diagnostic']['code'] == 'CLI_EXECUTION_FAILED'
    assert result['diagnostic']['graph_stage'] == 'worker'
    assert bool(result['file_changes']) is write_before_failure
    piece = result['work_pieces']['fixture']
    assert piece['checkpoint']['plan']['tasks'][0]['status'] == 'in_progress'
    assert piece['review_history'][0]['accepted_plan_sha256']


def test_worker_failure_still_rejects_a_mutated_accepted_contract(current_autonomous_run):
    from council.diagnostics import DiagnosticRuntimeError
    from test_engine_integration import open_graph
    run = current_autonomous_run
    def fail(task, guidance, **kwargs):
        task.acceptance_criteria.append('Unauthorized contract change')
        raise DiagnosticRuntimeError('CLI_EXECUTION_FAILED')
    run.provider.run_task = fail
    with open_graph(run.fixture, run.provider) as saver:
        result = run.build(saver).invoke(run.state, run.fixture.config)
    assert result['diagnostic']['code'] == 'GRAPH_STATE_INVALID'
    assert 'Unauthorized contract change' not in result['plan']['tasks'][0]['acceptance_criteria']
