"""Completion must enforce fresh proof through the real graph and checkpoint."""

import pytest

from test_engine_integration import open_graph


def pause_before_completion(run):
    with open_graph(run.fixture, run.provider) as saver:
        graph = run.build(saver)
        result = graph.invoke(run.state, run.fixture.config, interrupt_before=['gatekeeper'])
        assert graph.get_state(run.fixture.config).next == ('gatekeeper',)
    assert result['status'] == 'GATEKEEPER_AUDIT'
    assert all(task['status'] == 'completed' for task in result['plan']['tasks'])
    assert result['execution_records']
    assert all(record['expectation_met'] for record in result['execution_records'])


def resume_at_completion(run):
    with open_graph(run.fixture, run.provider) as saver:
        return run.build(saver).invoke(None, run.fixture.config)


def assert_changed_source_rejected(run, changed_file):
    pause_before_completion(run)
    (run.fixture.workspace / changed_file).write_text(
        'changed after all task verification completed', encoding='utf-8')
    result = resume_at_completion(run)
    assert result['status'] == 'FAILED', 'Earlier passing proof cannot certify changed source'
    assert result['diagnostic']['code'] == 'GRAPH_EVIDENCE_INVALID'


@pytest.mark.parametrize('changed_file', ['target-1.txt', 'verify.py'], ids=['deliverable', 'verifier'])
def test_current_completion_rejects_source_changed_after_verification(current_autonomous_run, changed_file):
    assert_changed_source_rejected(current_autonomous_run, changed_file)


@pytest.mark.parametrize('changed_file', ['target-1.txt', 'verify.py'], ids=['deliverable', 'verifier'])
def test_monolithic_completion_rejects_source_changed_after_verification(legacy_monolithic_run, changed_file):
    assert_changed_source_rejected(legacy_monolithic_run, changed_file)


def test_current_completion_accepts_unchanged_verified_source(current_autonomous_run):
    pause_before_completion(current_autonomous_run)
    assert resume_at_completion(current_autonomous_run)['status'] == 'COMPLETED'


def test_failed_phase_completion_keeps_piece_open_and_has_no_success_history(current_autonomous_run):
    run = current_autonomous_run
    with open_graph(run.fixture,run.provider) as saver:
        graph = run.build(saver)
        graph.invoke(run.state,run.fixture.config,interrupt_before=['phase_complete'])
        assert graph.get_state(run.fixture.config).next == ('phase_complete',)
        (run.fixture.workspace/'target-1.txt').write_text('Changed after successful task verification',encoding='utf-8')
        result = graph.invoke(None,run.fixture.config)
    assert result['status'] == 'FAILED'
    assert result['diagnostic']['code'] == 'GRAPH_EVIDENCE_INVALID'
    piece = result['work_pieces']['fixture']
    assert piece['status'] == 'executing'
    assert piece['completion_history'] == []
    assert result['completed_phases'] == []


def test_monolithic_completion_accepts_unchanged_verified_source(legacy_monolithic_run):
    pause_before_completion(legacy_monolithic_run)
    assert resume_at_completion(legacy_monolithic_run)['status'] == 'COMPLETED'
