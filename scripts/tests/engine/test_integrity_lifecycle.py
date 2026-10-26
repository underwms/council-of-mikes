"""Information preservation through native graph, SQLite, and actual subprocesses."""
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from council.graph import build_council_graph
from council.document_edits import DocumentRevision, document_digest
from council.integrity_contracts import RepairAdvice
from council.phase_contract import Phase, PhaseRoadmap
from council.state import MultiSpecialistPlan
from test_autonomous_review import setup
from test_engine_integration import lifecycle, open_graph

ACCEPT = {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []}
REVISE = {'decision': 'revise', 'findings': [
    {'id': 'F1', 'description': 'Add batch grouping proof', 'kind': 'technical'}], 'resolved_finding_ids': []}
CLOSE = {'decision': 'accept', 'findings': [], 'resolved_finding_ids': ['F1']}


def frame_from(messages):
    for message in reversed(messages if isinstance(messages, list) else []):
        if isinstance(message, dict):
            try:
                payload = json.loads(message.get('content', ''))
                if isinstance(payload, dict) and 'shared_context' in payload:
                    return payload['shared_context']
            except ValueError:
                pass
    raise AssertionError('Actual outbound provider messages lack shared content')


def graph_for(fixture, saver, provider, reviewer):
    return build_council_graph(checkpointer=saver, context=fixture.context,
        llm_factory=lambda role: reviewer if role == 'reviewer' else provider)


def legacy_monolithic_integrity_setup(lifecycle, monkeypatch, decisions, contents=None):
    state, provider, reviewer = setup(lifecycle, monkeypatch, decisions, contents)
    state.update(graph_integrity_policy_version=2, review_protocol_version=2, max_steps=400)
    lifecycle.config['recursion_limit'] = 500
    return state, provider, reviewer


@pytest.mark.parametrize('restart', [False, True])
@pytest.mark.parametrize('reject_first_patch', [False, True, 'always'])
def test_roadmap_revision_keeps_prior_requirements_and_reaches_workers(lifecycle, monkeypatch, restart, reject_first_patch):
    state, provider, reviewer = legacy_monolithic_integrity_setup(lifecycle, monkeypatch, [REVISE, CLOSE, ACCEPT])
    state['orchestration_policy_version'] = 2
    value = PhaseRoadmap(title='Full feature', architecture_summary='Shared original requirements', phases=[
        Phase(id='fixture', goal='Build and verify fixture', affected_services=['api'],
            delivered_contracts=['Shared fixture'], acceptance_outcomes=[
                'Save and assert baseline', 'Check coverage runner help'], final_acceptance=True)])
    schemas, requests, worker_inputs = [], [], []
    def structured(schema, **kwargs):
        def invoke(messages):
            schemas.append(schema)
            frame = frame_from(messages)
            if schema is PhaseRoadmap: response = value
            elif schema is MultiSpecialistPlan: response = lifecycle.plan
            elif schema is DocumentRevision:
                from council.phase_contract import roadmap_digest
                response = {'run_id': frame['run_id'], 'artifact': 'roadmap',
                    'base_sha256': roadmap_digest(PhaseRoadmap.model_validate(frame['records']['roadmap'])),
                    'edits': [{'op': 'add', 'path': '/phases/fixture/acceptance_outcomes/-',
                        'value': 'Assert three-snapshot batch', 'reason_ids': ['F1']}]}
                if reject_first_patch == 'always' or (reject_first_patch and schemas.count(DocumentRevision) == 1):
                    response['base_sha256'] = '0' * 64
            else: pytest.fail('Unexpected model schema')
            return {'parsed': response, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    original_review, original_worker = reviewer.review_plan, provider.run_task
    def review(request):
        requests.append(request)
        return original_review(request)
    def worker(task, guidance, **kwargs):
        worker_inputs.append(guidance)
        return original_worker(task, guidance, **kwargs)
    reviewer.review_plan, provider.run_task = review, worker
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        result = graph.invoke(state, lifecycle.config, **({'interrupt_after': ['roadmap_review']} if restart else {}))
    if restart:
        assert result['status'] == 'ROADMAP_REVISION'
        with open_graph(lifecycle, provider) as saver:
            result = graph_for(lifecycle, saver, provider, reviewer).invoke(None, lifecycle.config)
    if reject_first_patch == 'always':
        assert result['status'] == 'PLAN_BLOCKED', result.get('diagnostic')
        assert result['roadmap_revision_count'] == 3 and result['roadmap_review_count'] == 1
        assert schemas.count(DocumentRevision) == 3
        assert result['roadmap']['phases'][0]['acceptance_outcomes'] == [
            'Save and assert baseline', 'Check coverage runner help']
        assert result['__interrupt__'][0].value['finding_ledger'][0]['id'] == 'F1'
        assert result['document_revision_feedback']['reason'] == 'STALE_BASE'
        assert not worker_inputs and not provider.attempts
        return
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert schemas.count(PhaseRoadmap) == 1 and schemas.count(DocumentRevision) == 1 + int(reject_first_patch)
    assert result['roadmap']['phases'][0]['acceptance_outcomes'] == [
        'Save and assert baseline', 'Check coverage runner help', 'Assert three-snapshot batch']
    assert all('Save and assert baseline' in text and state['task_input'] in text for text in worker_inputs)
    assert requests[1]['shared_context']['records']['findings']['roadmap'][0]['id'] == 'F1'
    assert all(record['run_id'] == state['run_id'] for record in result['execution_records'])
    assert {item['consumer'] for item in result['context_receipts']} >= {'roadmap', 'roadmap_review', 'architect', 'worker'}


def patching_provider(provider, lifecycle):
    original = provider.with_structured_output
    def structured(schema, **kwargs):
        if schema is not DocumentRevision:
            return original(schema, **kwargs)
        def invoke(messages):
            frame = frame_from(messages)
            plan = MultiSpecialistPlan.model_validate(frame['records']['plan'])
            return {'parsed': {'run_id': frame['run_id'], 'artifact': 'plan',
                'base_sha256': document_digest(plan, 'plan'), 'edits': [
                    {'op': 'add', 'path': '/tasks/task-1/acceptance_criteria/-',
                     'value': 'Batch proof ' + str(len(plan.tasks[0].acceptance_criteria)),
                     'reason_ids': ['F1']}]}, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured


@pytest.mark.parametrize('reset', [False, True])
@pytest.mark.parametrize('normalize_alias', [False, True])
def test_plan_revision_and_strategy_reset_use_edits_and_preserve_the_task_contract(lifecycle, monkeypatch, reset, normalize_alias):
    decisions = [REVISE, REVISE, REVISE, CLOSE] if reset else [REVISE, CLOSE]
    state, provider, reviewer = legacy_monolithic_integrity_setup(lifecycle, monkeypatch, decisions)
    patching_provider(provider, lifecycle)
    if normalize_alias:
        original = provider.with_structured_output
        def structured(schema, **kwargs):
            target = original(schema, **kwargs)
            if schema is not DocumentRevision: return target
            def invoke(messages):
                response = target.invoke(messages)
                response['parsed']['edits'].append({'op': 'replace',
                    'path': '/tasks/task-1/specialist', 'value': '[THE CODER]', 'reason_ids': ['F1']})
                return response
            return SimpleNamespace(invoke=invoke)
        provider.with_structured_output = structured
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert result['plan']['tasks'][0]['acceptance_criteria'][0] == 'Verification exits zero'
    assert len(result['plan']['tasks'][0]['acceptance_criteria']) > 1
    assert result['plan']['tasks'][0]['test_commands'] == lifecycle.plan.tasks[0].test_commands
    assert result['strategy_reset_count'] == int(reset)
    assert result['last_document_revision']['candidate_sha256'] == document_digest(
        MultiSpecialistPlan.model_validate(result['plan']), 'plan')


@pytest.mark.parametrize('provider_raises', [False, True])
def test_worker_contract_mutation_fails_and_keeps_observed_file_changes(lifecycle, monkeypatch, provider_raises):
    state, provider, reviewer = legacy_monolithic_integrity_setup(lifecycle, monkeypatch, [ACCEPT])
    original = provider.run_task
    def malicious(task, guidance, **kwargs):
        result = original(task, guidance, **kwargs)
        task.acceptance_criteria.clear()
        if provider_raises:
            raise RuntimeError('Private failure after attempted contract mutation')
        return result
    provider.run_task = malicious
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert result['status'] == 'FAILED'
    assert result['diagnostic']['code'] == 'GRAPH_STATE_INVALID'
    assert result['plan']['tasks'][0]['acceptance_criteria'] == ['Verification exits zero']
    assert result['file_changes']
    assert result['model_calls'][-1]['operation'] == 'worker'


def test_repair_advice_survives_a_new_graph_process_without_raw_output(lifecycle, monkeypatch):
    state, provider, reviewer = legacy_monolithic_integrity_setup(lifecycle, monkeypatch, [ACCEPT], {'task-1': ['broken', 'valid']})
    original = provider.with_structured_output
    def structured(schema, **kwargs):
        if schema is not RepairAdvice: return original(schema, **kwargs)
        def invoke(messages):
            frame = frame_from(messages)
            failure = frame['records']['execution_evidence'][-1]
            return {'parsed': {'failure_id': failure['id'], 'category': 'implementation',
                'action': 'repair_implementation', 'target_files': frame['records']['task']['target_files'],
                'limitations': ['cause_unproven', 'needs_source_inspection']},
                'raw': AIMessage(content='PRIVATE_DIAGNOSIS_MUST_NOT_BE_SAVED'), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    with open_graph(lifecycle, provider) as saver:
        paused = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config,
            interrupt_after=['investigation'])
    assert paused.get('repair_advice'), paused.get('diagnostic')
    assert paused['repair_advice']['action'] == 'repair_implementation'
    seen = []
    original_worker = provider.run_task
    def worker(task, guidance, **kwargs):
        seen.append(guidance)
        return original_worker(task, guidance, **kwargs)
    provider.run_task = worker
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(None, lifecycle.config)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert 'repair_implementation' in seen[0]
    assert 'PRIVATE_DIAGNOSIS_MUST_NOT_BE_SAVED' not in json.dumps(result)
    assert len({item['id'] for item in result['execution_records']}) == len(result['execution_records'])


def test_investigation_binds_first_failed_command_even_when_a_later_command_passes(lifecycle, monkeypatch):
    state, provider, reviewer = legacy_monolithic_integrity_setup(lifecycle, monkeypatch, [ACCEPT], {'task-1': ['broken', 'valid']})
    lifecycle.plan.tasks[0].test_commands.append([lifecycle.plan.tasks[0].test_commands[0][0], '-c', 'print("ok")'])
    original = provider.with_structured_output
    def structured(schema, **kwargs):
        if schema is not RepairAdvice: return original(schema, **kwargs)
        def invoke(messages):
            frame = frame_from(messages)
            failures = [item for item in frame['records']['execution_evidence'] if not item['expectation_met']]
            return {'parsed': {'failure_id': failures[-1]['id'], 'category': 'implementation',
                'action': 'repair_implementation', 'target_files': frame['records']['task']['target_files'],
                'limitations': ['cause_unproven']}, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    seen = []
    original_worker = provider.run_task
    def worker(task, guidance, **kwargs):
        seen.append((task.id, guidance))
        return original_worker(task, guidance, **kwargs)
    provider.run_task = worker
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    second_task_guidance = next(text for task_id, text in seen if task_id == 'task-2')
    assert 'repair_implementation' not in second_task_guidance


def test_two_fresh_graph_runs_share_storage_without_importing_prior_execution(lifecycle, monkeypatch):
    state, provider, reviewer = legacy_monolithic_integrity_setup(lifecycle, monkeypatch, [ACCEPT, ACCEPT])
    with open_graph(lifecycle, provider) as saver:
        first = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert first['status'] == 'COMPLETED'
    second = dict(state, run_id='independent-second-run', thread_id='independent-second-run')
    config = {**lifecycle.config, 'configurable': {'thread_id': second['thread_id']}}
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(second, config)
    assert result['status'] == 'COMPLETED', result.get('diagnostic')
    assert all(record['run_id'] == second['run_id'] for record in result['execution_records'])
    assert result['plan_review_count'] == 1


def test_verification_that_changes_its_source_cannot_certify_the_changed_source(lifecycle, monkeypatch):
    state, provider, reviewer = legacy_monolithic_integrity_setup(lifecycle, monkeypatch, [ACCEPT])
    state['max_test_retries'] = 0
    (lifecycle.workspace/'verify.py').write_text(
        'from pathlib import Path\nimport sys\n'
        'assert Path(sys.argv[1]).read_text() == "valid"\n'
        'Path(sys.argv[1]).write_text("changed after assertion")\n'
        'print("Passed: 1 Failed: 0")\n')
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)
    assert result['status'] == 'FAILED'
    assert result['test_result']['exit_code'] == 0
    assert result['test_result']['verification_reason'] == 'SOURCE_INPUT_CHANGED'
    assert result['execution_records'][0]['expectation_met'] is False
