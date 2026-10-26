"""Accepted tasks remain the assignment unit; handoffs never certify worker prose."""
from council.state import CouncilState


def test_handoff_separates_observed_changes_from_verified_completion(graph_workspace):
    from council.assignments import assignment_context
    fixture = graph_workspace
    path = fixture.workspace / 'target-1.txt'
    path.write_text('valid')
    import hashlib
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    state = CouncilState(run_id='assign', task_input='Implement targets', workspace_root=str(fixture.workspace),
        council_root=str(fixture.context.council_root), memory_root=str(fixture.context.memory_root))
    state.plan = fixture.plan
    state.file_changes = [{'path':'target-1.txt', 'before_sha256':None, 'after_sha256':sha}]
    context = assignment_context(state)
    assert context['changes'][0]['freshness'] == 'current'
    assert context['verified_execution_ids'] == []
    path.write_text('changed by another assignment')
    assert assignment_context(state)['changes'][0]['freshness'] == 'changed'
    assert context['assignment_unit'] == 'accepted_task'


def test_native_call_groups_checklist_and_leaves_verification_to_prover(current_autonomous_run):
    import json
    run = current_autonomous_run
    original = run.provider.run_task
    seen = []
    def coding(task, guidance, **kwargs):
        seen.append((task.id, guidance))
        assert 'focused development checks' in guidance
        assert 'independent prover' in guidance
        return original(task, guidance, **kwargs)
    run.provider.run_task = coding
    from council.checkpoint import managed_sqlite_checkpointer
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        result = run.build(saver).invoke(run.state, run.fixture.config)
    assert result['status'] == 'COMPLETED'
    assert [task_id for task_id, _ in seen] == ['setup', 'task-1', 'task-2']
    assert len(result['execution_records']) == 3
    for _, guidance in seen:
        assert 'accepted_task' in guidance
    assert len([c for c in result['model_calls'] if c['operation'] == 'worker']) == 3
