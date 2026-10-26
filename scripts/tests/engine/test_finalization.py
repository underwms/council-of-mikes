"""Finished-content approval cannot outlive edits or replace missing quality evidence."""
import hashlib
import pytest
from council.state import CouncilState


def state_for(fixture):
    return CouncilState(run_id='final', task_input='Deliver CLI', finalization_enabled=True,
        workspace_root=str(fixture.workspace), council_root=str(fixture.context.council_root),
        memory_root=str(fixture.context.memory_root), plan=fixture.plan)


def test_unchanged_non_text_file_does_not_prevent_text_review(graph_workspace):
    from council import finalization
    root = graph_workspace.workspace
    (root / 'reference.bin').write_bytes(b'\xff\x00\x80')
    state = state_for(graph_workspace)
    finalization.capture(state, graph_workspace.context, '.')
    path = root / 'target-1.txt'
    path.write_text('valid', encoding='utf-8')
    state.file_changes = [{'path': 'target-1.txt', 'before_sha256': None,
        'before_known': True, 'after_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}]
    packet = finalization.review_packet(state, graph_workspace.context)
    assert [item['path'] for item in packet['files']] == ['target-1.txt']


@pytest.mark.parametrize('before,after', [
    (b'\xff', b'\xfe'), (b'\xff', None), (b'\xff', b'text'),
    (b'text', b'\xff'), (None, b'\xff'),
])
def test_changed_non_text_content_cannot_receive_text_only_approval(graph_workspace, before, after):
    from council import finalization
    path = graph_workspace.workspace / 'reference.bin'
    if before is not None:
        path.write_bytes(before)
    state = state_for(graph_workspace)
    finalization.capture(state, graph_workspace.context, '.')
    if after is None:
        path.unlink()
    else:
        path.write_bytes(after)
    state.file_changes = [{'path': 'reference.bin', 'before_known': True,
        'before_sha256': hashlib.sha256(before).hexdigest() if before is not None else None,
        'after_sha256': hashlib.sha256(after).hexdigest() if after is not None else None}]
    with pytest.raises(ValueError, match='Non-text feature content requires a supported content-review path') as caught:
        finalization.review_packet(state, graph_workspace.context)
    assert getattr(caught.value, 'code', None) == 'FINAL_REVIEW_NON_TEXT_UNSUPPORTED'
    assert not finalization.review_current(state, graph_workspace.context)


def test_failed_capture_does_not_publish_partial_binary_baseline(graph_workspace, monkeypatch):
    from council import finalization
    state = state_for(graph_workspace)
    path = graph_workspace.workspace/'reference.bin'
    path.write_bytes(b'\xff')
    original = finalization.snapshot
    def changing(context, relative):
        result = original(context, relative)
        path.write_bytes(b'\xfe')
        return result
    monkeypatch.setattr(finalization, 'snapshot', changing)
    with pytest.raises(ValueError, match='Source changed while capturing'):
        finalization.capture(state, graph_workspace.context, '.')
    assert state.finalization.captured_scopes == []
    assert state.finalization.baseline_sha256 is None
    assert not finalization._artifact(state, graph_workspace.context).exists()


def test_legacy_text_baseline_is_read_without_rewriting(graph_workspace):
    from council import finalization
    import json
    state = state_for(graph_workspace)
    finalization.capture(state, graph_workspace.context, '.')
    artifact = finalization._artifact(state, graph_workspace.context)
    data = artifact.read_bytes()
    assert all(set(entry) == {'sha256', 'content'} for entry in json.loads(data)['files'].values())
    finalization.review_packet(state, graph_workspace.context)
    assert artifact.read_bytes() == data


def test_full_diff_includes_new_files_and_review_expires_after_edit(graph_workspace):
    from council import finalization
    state = state_for(graph_workspace)
    finalization.capture(state, graph_workspace.context, '.')
    path = graph_workspace.workspace/'target-1.txt'
    path.write_text('valid')
    state.file_changes = [{'path':'target-1.txt', 'before_sha256':None, 'before_known':True,
        'after_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]
    packet = finalization.review_packet(state, graph_workspace.context)
    assert packet['files'][0]['before'] is None
    assert packet['files'][0]['after'] == 'valid'
    finalization.accept_review(state, packet, {'content_sha256':packet['content_sha256'],
        'decision':'accept', 'findings':[], 'resolved_finding_ids':[]})
    assert finalization.review_current(state, graph_workspace.context)
    assert not finalization.delivery_result(state)['pr_ready']
    path.write_text('later edit')
    assert not finalization.review_current(state, graph_workspace.context)


def test_stronger_approved_completion_boundary_cannot_be_silently_reduced(graph_workspace):
    from council import finalization,requirements
    from test_requirements_intake import draft
    from council.diagnostics import DiagnosticRuntimeError
    state=state_for(graph_workspace)
    state.intake_enabled=True
    value=draft()
    value.completion_boundary='pr_ready'
    requirements.revise(state,value,[])
    requirements.approve(state,{'requirements_sha256':state.requirements.document_sha256})
    assert 'Agreed completion boundary: **pr_ready**' in state.requirements.markdown
    state.delivery_result={'functional_complete':True,'pr_ready':False}
    with pytest.raises(DiagnosticRuntimeError) as caught:
        finalization.enforce_boundary(state)
    assert caught.value.code=='DELIVERY_BOUNDARY_NOT_MET'
    state.delivery_result['pr_ready']=True
    finalization.enforce_boundary(state)


def test_unattributed_concurrent_edit_is_not_part_of_reviewable_feature(graph_workspace):
    from council import finalization
    state = state_for(graph_workspace)
    finalization.capture(state, graph_workspace.context, '.')
    (graph_workspace.workspace/'verify.py').write_text('concurrent unrelated edit')
    with pytest.raises(ValueError):
        finalization.review_packet(state, graph_workspace.context)


def test_feature_diff_retains_repository_identity(graph_workspace):
    from council import finalization
    import subprocess
    subprocess.run(['git','init','--quiet',str(graph_workspace.workspace)],check=True,capture_output=True)
    state = state_for(graph_workspace)
    finalization.capture(state,graph_workspace.context,'.')
    packet = finalization.review_packet(state,graph_workspace.context)
    assert packet['repositories'][0]['root']=='.'
    assert packet['repositories'][0]['kind']=='git'


@pytest.mark.parametrize('first,second',[('.', 'app'),('app','.')])
def test_overlapping_capture_scopes_cannot_rebase_away_feature_files(graph_workspace,first,second):
    from council import finalization
    app = graph_workspace.workspace/'app'
    app.mkdir()
    state = state_for(graph_workspace)
    finalization.capture(state,graph_workspace.context,first)
    path = app/'new.txt'
    path.write_text('feature')
    state.file_changes=[{'path':'app/new.txt','before_sha256':None,'before_known':True,
        'after_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]
    finalization.capture(state,graph_workspace.context,second)
    packet=finalization.review_packet(state,graph_workspace.context)
    assert packet['files'][0]['path']=='app/new.txt'
    assert packet['files'][0]['before'] is None


def test_missing_polish_assignment_gets_actionable_preflight_correction(current_autonomous_run):
    from council.checkpoint import managed_sqlite_checkpointer
    run = current_autonomous_run
    run.state['finalization_enabled']=True
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result = run.build(saver).invoke(run.state,run.fixture.config,interrupt_before=['plan_revision'])
    assert result['plan_validation_feedback']['verification']['reason']=='FINALIZE_MISSING'
    assert result['plan_validation_feedback']['field']=='delivery_stage'


def test_findings_need_locations_consequences_and_stable_resolution(graph_workspace):
    from council import finalization
    state = state_for(graph_workspace)
    finalization.capture(state, graph_workspace.context, '.')
    path = graph_workspace.workspace/'verify.py'
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_text('changed verifier')
    state.file_changes = [{'path':'verify.py', 'before_sha256':before, 'before_known':True,
        'after_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]
    packet = finalization.review_packet(state, graph_workspace.context)
    decision = {'content_sha256':packet['content_sha256'], 'decision':'revise',
        'findings':[{'id':'F1', 'location':'verify.py', 'concern':'Skips failure handling',
            'consequence':'False success for invalid target', 'kind':'correctness'}], 'resolved_finding_ids':[]}
    finalization.accept_review(state, packet, decision)
    assert not finalization.review_current(state, graph_workspace.context)
    with pytest.raises(ValueError):
        finalization.accept_review(state, packet, {'content_sha256':packet['content_sha256'],
            'decision':'accept','findings':[], 'resolved_finding_ids':[]})
    finalization.accept_review(state, packet, {'content_sha256':packet['content_sha256'],
        'decision':'accept','findings':[], 'resolved_finding_ids':['F1']})
    assert finalization.review_current(state, graph_workspace.context)


def test_real_graph_runs_polish_and_independent_finished_content_review(current_autonomous_run):
    from council.checkpoint import managed_sqlite_checkpointer
    from types import SimpleNamespace
    run = current_autonomous_run
    run.state['finalization_enabled'] = True
    run.fixture.plan.tasks[-1].delivery_stage = 'finalize'
    original = run.reviewer
    packets = []
    class Reviewer:
        def review_plan(self, request):
            return original.review_plan(request)
        def with_structured_output(self, schema, **kwargs):
            def review(messages):
                import json
                packet = json.loads(messages[1]['content'])
                packets.append(packet)
                return {'parsed':{'content_sha256':packet['content_sha256'], 'decision':'accept',
                    'findings':[], 'resolved_finding_ids':[]}, 'raw':None, 'parsing_error':None}
            return SimpleNamespace(invoke=review)
    run.reviewer = Reviewer()
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result = run.build(saver).invoke(run.state, run.fixture.config)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert packets and len(packets[0]['files']) == 3
    assert result['finalization']['polish_task_ids'] == ['task-2']
    assert result['finalization']['approved_content_sha256']
    assert result['delivery_result']['functional_complete']
    assert not result['delivery_result']['pr_ready']


def test_material_finished_diff_finding_repairs_through_existing_arbiter(current_autonomous_run):
    from council.checkpoint import managed_sqlite_checkpointer
    from types import SimpleNamespace
    import json
    run = current_autonomous_run
    run.state['finalization_enabled'] = True
    run.state['recovery_policy'] = {'version':1}
    run.fixture.plan.tasks[-1].delivery_stage = 'finalize'
    original_reviewer, original_coder = run.reviewer, run.provider.run_task
    reviewed = []
    def coding(task, guidance, **kwargs):
        response = original_coder(task, guidance, **kwargs)
        if task.id == 'task-1':
            (run.fixture.workspace/'business.txt').write_text('material defect')
        if task.delivery_stage == 'finalize' and reviewed:
            (run.fixture.workspace/'business.txt').write_text('correct behavior')
        return response
    run.provider.run_task = coding
    class Reviewer:
        def review_plan(self, request):
            return original_reviewer.review_plan(request)
        def with_structured_output(self, schema, **kwargs):
            def review(messages):
                packet = json.loads(messages[1]['content'])
                business = next(f for f in packet['files'] if f['path']=='business.txt')
                broken = business['after'] == 'material defect'
                reviewed.append(business['after'])
                return {'parsed':{'content_sha256':packet['content_sha256'],
                    'decision':'revise' if broken else 'accept',
                    'findings':[{'id':'F1','location':'business.txt','concern':'Material outcome missing',
                        'consequence':'Requested behavior fails','kind':'correctness'}] if broken else [],
                    'resolved_finding_ids':[] if broken else ['F1']}, 'raw':None,'parsing_error':None}
            return SimpleNamespace(invoke=review)
    run.reviewer = Reviewer()
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result = run.build(saver).invoke(run.state, run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert reviewed==['material defect','correct behavior']
    assert result['finalization']['review_count']==2
    assert any(e['action']=='repair_task' and e['outcome']=='resolved' for e in result['recovery_history'])
    assert len([r for r in result['execution_records'] if r['task_id']=='task-2'])==2


def test_quality_gate_claim_requires_reviewed_obligation_and_real_execution(graph_workspace):
    from council import finalization
    from council.graph_integrity import record_execution
    from council.plan_review import plan_digest
    from council.state import TestExecutionResult
    state = state_for(graph_workspace)
    from council.delivery_contracts import QualityGateSpec
    state.plan.quality_gates = [QualityGateSpec(phase='unit_tests',task_ids=['task-1'])]
    state.accepted_plan_sha256 = plan_digest(state.plan)
    finalization.qualify_gates(state,graph_workspace.context)
    assert state.finalization.quality_gates['unit_tests']=='unverified'
    (graph_workspace.workspace/'target-1.txt').write_text('valid')
    record_execution(state,state.plan.tasks[0],1,
        TestExecutionResult(command='python',passed=True,exit_code=0,expectation_met=True),graph_workspace.context)
    finalization.qualify_gates(state,graph_workspace.context)
    assert state.finalization.quality_gates['unit_tests']=='passed'
    (graph_workspace.workspace/'target-1.txt').write_text('changed')
    finalization.qualify_gates(state,graph_workspace.context)
    assert state.finalization.quality_gates['unit_tests']=='unverified'


def test_polish_source_edit_refreshes_proof_without_repeating_feature_coder(current_autonomous_run):
    from council.checkpoint import managed_sqlite_checkpointer
    from council.delivery_contracts import ProofScope
    from types import SimpleNamespace
    import json
    run = current_autonomous_run
    run.state.update(finalization_enabled=True,recovery_policy={'version':1})
    for task in run.fixture.plan.tasks:
        task.proof_scope = ProofScope(project='unsupported.project',runtime_mutable=True)
    run.fixture.plan.tasks[-1].delivery_stage = 'finalize'
    original = run.reviewer
    class Reviewer:
        def review_plan(self, request):
            return original.review_plan(request)
        def with_structured_output(self, schema, **kwargs):
            def review(messages):
                packet = json.loads(messages[1]['content'])
                return {'parsed':{'content_sha256':packet['content_sha256'],'decision':'accept',
                    'findings':[],'resolved_finding_ids':[]},'raw':None,'parsing_error':None}
            return SimpleNamespace(invoke=review)
    run.reviewer = Reviewer()
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result = run.build(saver).invoke(run.state,run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert run.provider.attempts == {'setup':1,'task-1':1,'task-2':1}
    assert any(e['action']=='refresh_proofs' and e['outcome']=='resolved' for e in result['recovery_history'])
