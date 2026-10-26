"""Preflight correction uses the existing revision budget and never grants approval."""
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command
from test_engine_integration import lifecycle, open_graph
from test_autonomous_review import graph_for
from test_review_convergence import configured, decision


def proposal_provider(lifecycle, monkeypatch, mutate, decisions=None):
    state, provider, reviewer, _ = configured(lifecycle, monkeypatch,
        decisions or [decision('F1'), decision(resolved=['F1'], action='accept')])
    calls = []
    def structured(schema, **kwargs):
        number = len(calls)
        plan = lifecycle.plan.model_copy(deep=True)
        plan.architecture_summary += f' candidate {number}'
        if number:
            mutate(plan, number)
        def invoke(messages):
            calls.append(messages)
            assert not list(lifecycle.workspace.glob('target-*.txt')), 'No worker before accepted correction'
            return {'parsed': plan, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    return state, provider, reviewer, calls


def run(lifecycle, state, provider, reviewer):
    with open_graph(lifecycle, provider) as saver:
        return graph_for(lifecycle, saver, provider, reviewer).invoke(state, lifecycle.config)


@pytest.mark.parametrize('field,value,code', [
    ('target_files', ['../PRIVATE_REJECTED_PATH'], 'PLAN_TARGET_PATH_INVALID'),
    ('working_directory', 'missing-candidate-directory', 'PLAN_WORKING_DIRECTORY_INVALID'),
    ('test_commands', [], 'PLAN_VERIFICATION_INVALID'),
    ('specialist', 'unknown-specialist', 'PLAN_SPECIALIST_INVALID'),
])
def test_invalid_revision_corrects_then_requires_fresh_review(lifecycle, monkeypatch, field, value, code):
    def mutate(plan, number):
        if number == 1:
            setattr(plan.tasks[0], field, value)
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch, mutate)
    result = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'COMPLETED'
    assert reviewer.calls == 2
    assert result['plan_revision_count'] == 2
    assert result['plan_preflight_failure_count'] == 1
    correction = json.loads(calls[2][1]['content'])['plan_validation_feedback']
    assert correction['code'] == code and correction['field'] == field
    assert correction['task_index'] == 1
    assert result['plan_validation_feedback'] is None


def test_repeated_invalid_proposals_exhaust_existing_budget(lifecycle, monkeypatch):
    def mutate(plan, number):
        plan.tasks[0].target_files = ['../PRIVATE_REJECTED_PATH']
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch, mutate)
    result = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'PLAN_BLOCKED'
    assert result['plan_revision_count'] == 5
    assert result['plan_preflight_failure_count'] == 5
    assert reviewer.calls == 1
    assert result['diagnostic']['code'] == 'PLAN_REVIEW_EXHAUSTED'
    payload = result['__interrupt__'][0].value
    assert payload['blocker_kind'] == 'budget_exhausted'
    assert payload['last_plan_validation']['code'] == 'PLAN_TARGET_PATH_INVALID'
    assert 'PRIVATE_REJECTED_PATH' not in json.dumps(payload)
    assert result['plan']['tasks'][0]['target_files'] == lifecycle.plan.tasks[0].target_files
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_rejected_field_context_is_private_bounded_and_identifiable(lifecycle, monkeypatch, capsys):
    from council.diagnostics import DiagnosticSession
    bad_value = '../PRIVATE_REJECTED_PATH/' + '\u2603'*3000
    def mutate(plan, number):
        plan.tasks[0].target_files.append(bad_value)
        plan.tasks[0].id = 'PRIVATE_TASK_ID' + 'z'*1000
        plan.tasks[0].description = 'PRIVATE_TASK_DESCRIPTION' + 'z'*1000
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch, mutate)
    with DiagnosticSession(lifecycle.state.run_id, lifecycle.context.memory_root):
        result = run(lifecycle, state, provider, reviewer)
    private = result['plan_validation_feedback']
    assert private['field_index'] == 2 and private['task_index'] == 1
    assert private['field'] == 'target_files' and private['value_truncated']
    assert len(private['rejected_value'].encode('utf-8')) <= 2048
    assert len(private['task_id'].encode('utf-8')) <= 256
    assert len(private['task_description'].encode('utf-8')) <= 512
    assert 'PRIVATE_REJECTED_PATH' in private['rejected_value']
    console = capsys.readouterr().err
    assert 'plan_preflight_rejected' in console
    assert 'PRIVATE_' not in console
    with open_graph(lifecycle, provider) as saver:
        saved = graph_for(lifecycle, saver, provider, reviewer).get_state(lifecycle.config).values
    assert saved['plan_validation_feedback'] == private


def test_restart_between_rejected_candidate_and_correction_keeps_feedback(lifecycle, monkeypatch):
    def mutate(plan, number):
        if number == 1:
            plan.tasks[0].target_files = ['../PRIVATE_REJECTED_PATH']
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch, mutate)
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        graph.invoke(state, lifecycle.config, interrupt_after=['plan_revision'])
        paused = graph.get_state(lifecycle.config)
        assert paused.next == ('plan_revision',)
        assert paused.values['plan_revision_count'] == 1
        assert paused.values['plan_validation_feedback']['code'] == 'PLAN_TARGET_PATH_INVALID'
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(None, lifecycle.config)
    assert result['status'] == 'COMPLETED'
    assert result['plan_revision_count'] == 2
    assert 'PRIVATE_REJECTED_PATH' in json.dumps(calls[2])


def test_legacy_protocol_keeps_immediate_rejection(lifecycle, monkeypatch):
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch,
        lambda plan, _: setattr(plan.tasks[0], 'target_files', ['../outside']),
        [{'decision': 'revise', 'findings': ['Correct scope.']}])
    state['review_protocol_version'] = 1
    result = run(lifecycle, state, provider, reviewer)
    assert result['diagnostic']['code'] == 'PLAN_TARGET_PATH_INVALID'
    assert result['plan_revision_count'] == 1 and len(calls) == 2


def test_path_contract_is_in_shared_context_and_initial_planning(lifecycle, monkeypatch):
    from council.plan_review import review_request, revision_request
    lifecycle.state.plan = lifecycle.plan
    review = review_request(lifecycle.state, lifecycle.context)
    revision = revision_request(lifecycle.state, lifecycle.context)
    assert review['plan_contract'] == revision['plan_contract']
    assert 'workspace root' in revision['plan_contract']['target_files']
    assert 'working_directory' in lifecycle.plan.tasks[0].model_json_schema()['properties']
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch, lambda *args: None)
    run(lifecycle, state, provider, reviewer)
    assert 'workspace root' in json.dumps(calls[0])


@pytest.mark.parametrize('code', ['PLAN_SPECIALIST_UNAVAILABLE', 'PLAN_CATALOG_INVALID', 'CLI_TIMEOUT'])
def test_nonrepairable_failures_do_not_loop(lifecycle, monkeypatch, code):
    from council.diagnostics import DiagnosticRuntimeError
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch, lambda *args: None)
    original = provider.with_structured_output
    def structured(schema, **kwargs):
        if len(calls) == 1:
            raise DiagnosticRuntimeError(code)
        return original(schema, **kwargs)
    provider.with_structured_output = structured
    result = run(lifecycle, state, provider, reviewer)
    assert result['diagnostic']['code'] == code
    assert result['plan_revision_count'] == 1
    assert reviewer.calls == 1


def test_validation_context_does_not_retain_arbitrary_command_arguments(lifecycle, monkeypatch):
    def mutate(plan, number):
        plan.tasks[0].test_commands = [['PRIVATE_COMMAND', 'PRIVATE_ARG'], []]
    state, provider, reviewer, _ = proposal_provider(lifecycle, monkeypatch, mutate)
    result = run(lifecycle, state, provider, reviewer)
    assert result['plan_validation_feedback']['field'] == 'test_commands'
    assert 'PRIVATE_' not in json.dumps(result['plan_validation_feedback'])


@pytest.mark.parametrize('outside', [True, False])
def test_absolute_targets_are_not_silently_normalized(lifecycle, monkeypatch, outside):
    value = str((lifecycle.context.council_root if outside else lifecycle.workspace)/'PRIVATE_ABSOLUTE_PATH')
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch,
        lambda plan, _: setattr(plan.tasks[0], 'target_files', [value]))
    result = run(lifecycle, state, provider, reviewer)
    assert result['diagnostic']['code'] == 'PLAN_REVIEW_EXHAUSTED'
    assert result['plan_validation_feedback']['rejected_value'] == value
    assert reviewer.calls == 1
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_unavailable_package_from_preflight_never_enters_correction_loop(lifecycle, monkeypatch):
    from council.diagnostics import DiagnosticValueError
    import council.graph as module
    original = module.validate_plan
    def validate(candidate, *args, **kwargs):
        if 'candidate 1' in candidate.architecture_summary:
            raise DiagnosticValueError('PLAN_SPECIALIST_UNAVAILABLE', task_index=1)
        return original(candidate, *args, **kwargs)
    monkeypatch.setattr(module, 'validate_plan', validate)
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch, lambda *args: None)
    result = run(lifecycle, state, provider, reviewer)
    assert result['diagnostic']['code'] == 'PLAN_SPECIALIST_UNAVAILABLE'
    assert result['plan_revision_count'] == 1
    assert result['plan_validation_feedback'] is None
    assert len(calls) == 2


def test_malformed_revision_does_not_retry_or_retain_raw_error(lifecycle, monkeypatch):
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch, lambda *args: None)
    original = provider.with_structured_output
    def structured(schema, **kwargs):
        result = original(schema, **kwargs)
        if len(calls) != 1:
            return result
        def invoke(messages):
            response = result.invoke(messages)
            response['parsing_error'] = ValueError('PRIVATE_PROVIDER_ERROR')
            return response
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    result = run(lifecycle, state, provider, reviewer)
    assert result['diagnostic']['code'] == 'PLAN_REVISION_INVALID'
    assert result['plan_revision_count'] == 1
    from council.state import CouncilState
    assert 'PRIVATE_PROVIDER_ERROR' not in CouncilState.model_validate(result).model_dump_json()
    assert 'PRIVATE_PROVIDER_ERROR' not in json.dumps(result['__interrupt__'][0].value)


def test_blocked_resume_without_feedback_cannot_reset_correction_budget(lifecycle, monkeypatch):
    from council.plan_review import revision_request
    from council.state import CouncilState
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch,
        lambda plan, _: setattr(plan.tasks[0], 'target_files', ['../outside']))
    blocked = run(lifecycle, state, provider, reviewer)
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        still_blocked = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert still_blocked['plan_revision_count'] == blocked['plan_revision_count'] == 5
    assert len(calls) == 6
    request = revision_request(CouncilState.model_validate(still_blocked), lifecycle.context)
    assert request['plan_validation_feedback']['code'] == 'PLAN_TARGET_PATH_INVALID'


@pytest.mark.parametrize('task_index,field_index', [(None, 1), (99, 1), (1, None), (1, 99)])
def test_invalid_error_positions_do_not_record_a_different_field(lifecycle, task_index, field_index):
    from council.diagnostics import DiagnosticValueError
    from council.plan_review import record_preflight_failure
    error = DiagnosticValueError('PLAN_TARGET_PATH_INVALID', task_index=task_index, field_index=field_index)
    assert not record_preflight_failure(lifecycle.state, lifecycle.plan, error)
    assert lifecycle.state.plan_validation_feedback is None
    assert lifecycle.state.plan_preflight_failure_count == 0


def test_untrusted_error_attributes_cannot_trigger_correction(lifecycle):
    from council.plan_review import record_preflight_failure
    error = ValueError('PRIVATE_ERROR')
    error.code, error.task_index, error.field_index = 'PLAN_TARGET_PATH_INVALID', 1, 1
    assert not record_preflight_failure(lifecycle.state, lifecycle.plan, error)


def test_private_feedback_schema_enforces_utf8_byte_bounds():
    from council.state import PlanValidationFeedback
    with pytest.raises(ValueError):
        PlanValidationFeedback(code='PLAN_TARGET_PATH_INVALID', task_index=1, task_id='id',
            task_description='description', field='target_files', field_index=1,
            rejected_value='\u2603'*1000, value_truncated=False)


@pytest.mark.parametrize('value', [True, 0, -1, 100001, 'PRIVATE_VALUE'])
def test_rejected_field_position_cannot_carry_unbounded_metadata(value):
    from council.diagnostics import DiagnosticValueError, describe
    error = DiagnosticValueError('PLAN_TARGET_PATH_INVALID', task_index=1, field_index=value)
    assert error.field_index is None
    assert 'PRIVATE_VALUE' not in json.dumps(describe(error))
