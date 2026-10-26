"""Bounded inspection transitions to synthesis using real tools and fake transport."""
import json

from council.state import CouncilState
from council.diagnostics import DiagnosticSession
from test_engine_integration import lifecycle
from test_format_recovery import transport, execute


def read_rounds(fixture, transport, count):
    for number in range(count):
        path = f'inspection-{number}.txt'
        (fixture.workspace/path).write_text(f'OBSERVED_EVIDENCE_{number}', encoding='utf-8')
        transport.responses.append(json.dumps({'content': '', 'tool_calls': [
            {'name': 'read_workspace_file', 'args': {'rel_path': path}, 'id': f'read-{number}'}]}))


def test_budget_handoff_preserves_final_read_and_pauses_before_coding(lifecycle, transport, capsys):
    read_rounds(lifecycle, transport, 12)
    transport.responses.append(lifecycle.plan.model_dump_json())
    with DiagnosticSession(lifecycle.state.run_id, lifecycle.context.memory_root):
        result, saved = execute(lifecycle, transport.model)
    assert result['__interrupt__'][0].value['gate'] == 'GATE_1_PLAN_APPROVAL'
    expected = {'rounds_used': 12, 'round_limit': 12, 'limit_reached': True}
    assert saved['planning_inspection'] == expected
    assert result['__interrupt__'][0].value['planning_inspection'] == expected
    assert len(transport.requests) == 13
    assert 'response_schema' in transport.requests[-1]
    assert 'tools' not in transport.requests[-1]
    assert 'OBSERVED_EVIDENCE_11' in json.dumps(transport.requests[-1])
    assert len(saved['tool_call_history']) == 12
    assert saved['modified_files'] == [] and saved['test_results'] == []
    assert all(call['role'] == 'orchestrator' for call in saved['model_calls'])
    assert not list(lifecycle.workspace.glob('target-*.txt'))
    output = capsys.readouterr().err
    assert 'inspection_budget_reached' in output
    assert 'OBSERVED_EVIDENCE_' not in output
    assert saved['diagnostic'] is None
    # Round and remaining allowance must be observable in the actual requests.
    for number, request in enumerate(transport.requests[:12], start=1):
        budget = json.loads(request['messages'][0]['content'].rsplit('\n', 1)[-1])['inspection_budget']
        assert budget == {'round': number, 'round_limit': 12, 'remaining_rounds': 12-number}
    final_instruction = transport.requests[-1]['messages'][-1]['content'].lower()
    assert 'missing evidence' in final_instruction and 'assumptions' in final_instruction


def test_early_completion_records_one_round_without_limit_notice(lifecycle, transport, capsys):
    transport.responses.extend(['{"content":"Done.","tool_calls":[]}', lifecycle.plan.model_dump_json()])
    with DiagnosticSession(lifecycle.state.run_id, lifecycle.context.memory_root):
        result, saved = execute(lifecycle, transport.model)
    assert '__interrupt__' in result
    assert saved['planning_inspection'] == {'rounds_used': 1, 'round_limit': 12, 'limit_reached': False}
    assert 'inspection_budget_reached' not in capsys.readouterr().err


def test_natural_completion_on_last_round_is_not_forced_handoff(lifecycle, transport):
    read_rounds(lifecycle, transport, 11)
    transport.responses.extend(['{"content":"Done.","tool_calls":[]}', lifecycle.plan.model_dump_json()])
    result, saved = execute(lifecycle, transport.model)
    assert '__interrupt__' in result
    assert saved['planning_inspection'] == {'rounds_used': 12, 'round_limit': 12, 'limit_reached': False}
    assert len(saved['tool_call_history']) == 11


def test_failed_synthesis_preserves_real_error_and_inspection_summary(lifecycle, transport):
    read_rounds(lifecycle, transport, 12)
    transport.responses.extend(['SYNTHETIC_INVALID_PLAN','SYNTHETIC_INVALID_PLAN'])
    result, saved = execute(lifecycle, transport.model)
    assert result['status'] == 'FAILED'
    assert saved['diagnostic']['code'] == 'GEMINI_RESPONSE_JSON_INVALID'
    assert saved['planning_inspection']['limit_reached'] is True
    assert saved['model_calls'][-1]['operation'] == 'planning_format_retry'
    assert saved['test_results'] == []


def test_old_checkpoints_do_not_invent_inspection_metadata():
    state = CouncilState(run_id='old', task_input='fixture')
    assert getattr(state, 'planning_inspection', 'missing') is None


def test_cli_pause_and_resume_preserve_budget_without_reinspection(lifecycle, transport, monkeypatch, capsys):
    from council.cli import main
    read_rounds(lifecycle, transport, 12)
    transport.responses.append(lifecycle.plan.model_dump_json())
    monkeypatch.setattr('council.graph.get_llm_for_role', lambda *args, **kwargs: transport.model)
    monkeypatch.setattr('council.cli.preflight_credentials', lambda _: {'gpt': True, 'gemini': True})
    args = ['--workspace', str(lifecycle.workspace), '--council-root', str(lifecycle.context.council_root), '--no-input']
    assert main([*args, '--approval-mode', 'manual', 'Synthetic inspection budget fixture']) == 2
    output = capsys.readouterr()
    paused = json.loads(output.out)
    assert paused['planning_inspection'] == {'rounds_used': 12, 'round_limit': 12, 'limit_reached': True}
    assert len(transport.requests) == 13
    assert main([*args, '--resume', paused['run_id']]) == 2
    resumed = json.loads(capsys.readouterr().out)
    assert resumed['planning_inspection'] == paused['planning_inspection']
    assert resumed['resume_required'] is True
    assert len(transport.requests) == 13
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_cli_dryrun_exposes_early_completion_metadata(lifecycle, transport, monkeypatch, capsys):
    from council.cli import main
    transport.responses.extend(['{"content":"Done.","tool_calls":[]}', lifecycle.plan.model_dump_json()])
    monkeypatch.setattr('council.graph.get_llm_for_role', lambda *args, **kwargs: transport.model)
    monkeypatch.setattr('council.cli.preflight_credentials', lambda _: {'gpt': True, 'gemini': True})
    assert main(['--workspace', str(lifecycle.workspace), '--council-root', str(lifecycle.context.council_root),
                 '--dry-run', 'Synthetic budget fixture']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'PLAN_ONLY'
    assert result['planning_inspection'] == {'rounds_used': 1, 'round_limit': 12, 'limit_reached': False}


def test_budget_events_reject_out_of_range_or_noninteger_fields(tmp_path, capsys):
    with DiagnosticSession('numeric-fixture', tmp_path) as session:
        session.event('inspection_round_started', inspection_round=True, remaining_rounds=-1)
        session.event('inspection_budget_reached', inspection_round=13, remaining_rounds='PRIVATE_SENTINEL')
    records = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert all('inspection_round' not in r and 'remaining_rounds' not in r for r in records)
    assert 'PRIVATE_SENTINEL' not in json.dumps(records)
