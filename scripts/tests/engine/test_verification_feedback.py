"""Preflight explains failed verification contracts without echoing commands."""
import json

import pytest
from test_engine_integration import lifecycle
from test_tdd_phases import make_plan


CASES = [
    ('empty_commands', 'COMMANDS_EMPTY', 'test_commands', None, None),
    ('empty_command', 'COMMAND_EMPTY', 'test_commands', 1, None),
    ('empty_argument', 'ARGUMENT_EMPTY', 'test_commands', 1, None),
    ('duplicate_ids', 'TASK_IDS_DUPLICATE', 'id', None, None),
    ('green_contract', 'GREEN_CONTRACT_PRESENT', 'red_verification', None, None),
    ('missing_contract', 'RED_CONTRACT_MISSING', 'red_verification', None, None),
    ('no_targets', 'RED_TARGET_COUNT', 'target_files', None, None),
    ('many_targets', 'RED_TARGET_COUNT', 'target_files', None, None),
    ('many_commands', 'RED_COMMAND_COUNT', 'test_commands', None, None),
    ('source_target', 'RED_TARGET_TYPE', 'target_files', None, None),
    ('rewrite', 'FROZEN_TEST_TARGETED', 'target_files', None, 2),
    ('missing_pair', 'IMPLEMENTATION_MISSING', 'red_verification', None, None),
    ('earlier_pair', 'IMPLEMENTATION_ORDER', 'red_verification', None, 1),
    ('red_pair', 'IMPLEMENTATION_PHASE', 'verification_phase', None, 2),
    ('different_cwd', 'IMPLEMENTATION_CWD', 'working_directory', None, 2),
    ('duplicate_expectation', 'EXPECTATIONS_DUPLICATE', 'red_verification', None, None),
    ('missing_expectation', 'EXPECTATIONS_COMMANDS', 'red_verification', None, None),
    ('short_argv', 'RED_RUNNER', 'test_commands', 1, None),
    ('wrong_runner', 'RED_RUNNER', 'test_commands', 1, None),
    ('wrong_subcommand', 'RED_RUNNER', 'test_commands', 1, None),
    ('no_reporter', 'RED_REPORTER', 'test_commands', 1, None),
    ('duplicate_reporter', 'RED_REPORTER', 'test_commands', 1, None),
    ('other_reporter', 'RED_FLAGS', 'test_commands', 1, None),
    ('unchecked', 'RED_FLAGS', 'test_commands', 1, None),
    ('multiple_sources', 'RED_SOURCE_COUNT', 'test_commands', 1, None),
    ('no_rerun', 'GREEN_RERUN_MISSING', 'test_commands', 1, 2),
    ('undeclared_source', 'RED_SOURCE_UNDECLARED', 'target_files', 1, None),
]


def mutated(lifecycle, case):
    plan = make_plan(lifecycle)
    red, green = plan.tasks
    if case == 'empty_commands': red.test_commands = []
    elif case == 'empty_command': red.test_commands = [[]]
    elif case == 'empty_argument': red.test_commands = [['deno', '']]
    elif case == 'duplicate_ids': green.id = red.id
    elif case == 'green_contract': red.verification_phase = 'green'
    elif case == 'missing_contract': red.red_verification = None
    elif case == 'no_targets': red.target_files = []
    elif case == 'many_targets': red.target_files = [f'tests/{i}.test.ts' for i in range(33)]
    elif case == 'many_commands': red.test_commands *= 17
    elif case == 'source_target': red.target_files = ['implementation.ts']
    elif case == 'rewrite': green.target_files = red.target_files[:]
    elif case == 'missing_pair': red.red_verification.implementation_task_id = 'missing'
    elif case == 'earlier_pair': plan.tasks.reverse()
    elif case == 'red_pair': green.verification_phase = 'red'
    elif case == 'different_cwd': green.working_directory = 'other'
    elif case == 'duplicate_expectation': red.red_verification.expected_failures *= 2
    elif case == 'missing_expectation': red.red_verification.expected_failures[0].command_index = 2
    elif case == 'short_argv': red.test_commands = [['deno', 'test']]
    elif case == 'wrong_runner': red.test_commands[0][0] = 'PRIVATE_RUNNER'
    elif case == 'wrong_subcommand': red.test_commands[0][1] = 'task'
    elif case == 'no_reporter': red.test_commands[0][2] = '--allow-read'
    elif case == 'duplicate_reporter': red.test_commands[0].append('--reporter=junit')
    elif case == 'other_reporter': red.test_commands[0].append('--reporter=dot')
    elif case == 'unchecked': red.test_commands[0].append('--no-check')
    elif case == 'multiple_sources': red.test_commands[0].append('PRIVATE_SOURCE.test.ts')
    elif case == 'no_rerun': green.test_commands = [['deno', 'task', 'test']]
    elif case == 'undeclared_source':
        red.test_commands[0][-1] = 'PRIVATE_SOURCE.test.ts'
        green.test_commands = [red.test_commands[0][:]]
    return plan


@pytest.mark.parametrize('case,reason,field,command,related', CASES, ids=[row[0] for row in CASES])
def test_verification_rejection_identifies_actual_contract(lifecycle, case, reason, field, command, related):
    from council.plan_validation import validate_plan
    from council.diagnostics import describe
    from council.plan_review import record_preflight_failure, validation_summary, revision_request
    plan = mutated(lifecycle, case)
    with pytest.raises(ValueError) as caught:
        validate_plan(plan, lifecycle.context, native_coding=False)
    error = caught.value
    assert error.code == 'PLAN_VERIFICATION_INVALID'
    detail = describe(error).get('verification')
    assert detail == dict(reason=reason, field=field, command_index=command, related_task_index=related)
    assert record_preflight_failure(lifecycle.state, plan, error)
    feedback = lifecycle.state.plan_validation_feedback
    assert feedback.field == field
    assert feedback.verification == detail
    assert 'PRIVATE_' not in feedback.model_dump_json()
    assert validation_summary(lifecycle.state)['verification'] == detail
    lifecycle.state.plan = lifecycle.plan
    request = revision_request(lifecycle.state, lifecycle.context)
    assert request['verification_correction']['reason'] == reason
    assert request['verification_correction']['guidance']


@pytest.mark.parametrize('value', [None, {}, {'reason': 'PRIVATE_VALUE'},
    dict(reason='RED_RUNNER', field='PRIVATE_FIELD', command_index=1, related_task_index=None),
    dict(reason='RED_RUNNER', field='test_commands', command_index=True, related_task_index=None),
    dict(reason='RED_RUNNER', field='test_commands', command_index=100001, related_task_index=None),
    dict(reason='RED_RUNNER', field='test_commands', command_index=1, related_task_index=-1),
    dict(reason='RED_RUNNER', field='test_commands', command_index=1, related_task_index=None, raw='PRIVATE_VALUE'),
])
def test_untrusted_details_are_not_serialized(value):
    from council.diagnostics import DiagnosticValueError, describe
    error = DiagnosticValueError('PLAN_VERIFICATION_INVALID')
    error.verification = value
    assert 'verification' not in describe(error)
    assert 'PRIVATE_' not in json.dumps(describe(error))


def test_contract_example_passes_actual_preflight(lifecycle):
    from council.plan_validation import plan_contract, validate_plan
    from council.state import MultiSpecialistPlan
    contract = plan_contract(lifecycle.context)
    example = contract.get('tdd_example')
    assert example, 'Planner needs a complete valid red/green example'
    # The minimal fixture installs only the-coder; install the example's test
    # specialist in this isolated catalog as a real package too.
    root = lifecycle.context.council_root
    (root/'manifest.json').write_text(json.dumps({'specialists': ['the-coder', 'the-prover']}))
    package = root/'skills/the-prover'
    package.mkdir()
    (package/'SKILL.md').write_text('---\nname: the-prover\ndescription: Testing\n---\nTest the contract.\n')
    plan = MultiSpecialistPlan(title='Example', architecture_summary='Example', tasks=example)
    validate_plan(plan, lifecycle.context, native_coding=False)


def test_legacy_feedback_still_loads(lifecycle):
    from council.state import PlanValidationFeedback
    value = dict(code='PLAN_VERIFICATION_INVALID', task_index=1, task_id='old',
        task_description='old checkpoint', field='test_commands', field_index=None,
        rejected_value='', value_truncated=False)
    loaded = PlanValidationFeedback.model_validate(value)
    assert getattr(loaded, 'verification', None) is None


def test_verification_detail_reaches_diagnostic_timeline(tmp_path, capsys):
    from council.diagnostics import DiagnosticSession, DiagnosticValueError
    detail = dict(reason='FROZEN_TEST_TARGETED', field='target_files', command_index=None, related_task_index=2)
    error = DiagnosticValueError('PLAN_VERIFICATION_INVALID', task_index=1, verification=detail)
    with DiagnosticSession('verification-feedback', tmp_path) as session:
        session.event('plan_preflight_rejected', stage='plan_revision', diagnostic=error)
    records = [json.loads(line) for line in session.path.read_text().splitlines()]
    assert records[1]['verification'] == detail
    assert json.loads(capsys.readouterr().err.splitlines()[1])['verification'] == detail


def test_total_red_command_limit_is_identified(lifecycle):
    from council.plan_validation import validate_plan
    from council.diagnostics import describe
    plan = make_plan(lifecycle)
    red, green = plan.tasks
    reds = []
    green.test_commands = []
    for number in range(5):
        task = red.model_copy(deep=True)
        task.id = f'red-{number}'
        task.target_files = [f'tests/{number}.test.ts']
        task.test_commands = [['deno', 'test', '--reporter=junit', task.target_files[0]]] * 16
        reds.append(task)
        green.test_commands.extend(task.test_commands)
    plan.tasks = [*reds, green]
    with pytest.raises(ValueError) as caught:
        validate_plan(plan, lifecycle.context, native_coding=False)
    assert describe(caught.value)['verification']['reason'] == 'PLAN_RED_COMMAND_LIMIT'


@pytest.mark.parametrize('reason,field', [('PRIVATE_VALUE', 'test_commands'), ('RED_RUNNER', 'target_files')])
def test_checkpoint_feedback_rejects_unknown_or_mismatched_detail(reason, field):
    from council.state import PlanValidationFeedback
    with pytest.raises(ValueError):
        PlanValidationFeedback(code='PLAN_VERIFICATION_INVALID', task_index=1, task_id='id',
            task_description='description', field=field, rejected_value='', value_truncated=False,
            verification=dict(reason=reason, field=field, command_index=1, related_task_index=None))


def test_valid_detail_cannot_be_attached_to_unrelated_error():
    from council.diagnostics import DiagnosticValueError, describe
    detail = dict(reason='RED_RUNNER', field='test_commands', command_index=1, related_task_index=None)
    error = DiagnosticValueError('PLAN_TARGET_PATH_INVALID', verification=detail)
    error.verification = detail
    assert 'verification' not in describe(error)


def test_mutated_error_detail_is_revalidated():
    from council.diagnostics import DiagnosticValueError, describe
    detail = dict(reason='RED_RUNNER', field='test_commands', command_index=1, related_task_index=None)
    error = DiagnosticValueError('PLAN_VERIFICATION_INVALID', verification=detail)
    detail['reason'] = 'PRIVATE_INPUT'
    assert describe(error)['verification']['reason'] == 'RED_RUNNER'
    error.verification['reason'] = 'PRIVATE_INPUT'
    assert 'verification' not in describe(error)


def test_graph_correction_and_restart_keep_specific_reason(lifecycle, monkeypatch):
    from test_preflight_recovery import proposal_provider
    from test_autonomous_review import graph_for
    from test_engine_integration import open_graph
    def mutate(plan, number):
        if number == 1:
            plan.tasks[0].verification_phase = 'red'
            plan.tasks[0].red_verification = None
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch, mutate)
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        graph.invoke(state, lifecycle.config, interrupt_after=['plan_revision'])
        paused = graph.get_state(lifecycle.config)
        detail = paused.values['plan_validation_feedback']['verification']
        assert detail['reason'] == 'RED_CONTRACT_MISSING'
    with open_graph(lifecycle, provider) as saver:
        result = graph_for(lifecycle, saver, provider, reviewer).invoke(None, lifecycle.config)
    assert result['status'] == 'COMPLETED'
    assert result['plan_revision_count'] == 2 and reviewer.calls == 2
    correction = json.loads(calls[2][1]['content'])['verification_correction']
    assert correction['reason'] == 'RED_CONTRACT_MISSING'
    assert 'implementation_task_id' in correction['guidance']


def test_graph_budget_exhaustion_reports_specific_reason(lifecycle, monkeypatch):
    from test_preflight_recovery import proposal_provider, run
    def mutate(plan, number):
        plan.tasks[0].verification_phase = 'red'
    state, provider, reviewer, calls = proposal_provider(lifecycle, monkeypatch, mutate)
    result = run(lifecycle, state, provider, reviewer)
    assert result['status'] == 'PLAN_BLOCKED'
    assert result['plan_revision_count'] == result['plan_preflight_failure_count'] == 5
    assert reviewer.calls == 1 and len(calls) == 6
    payload = result['__interrupt__'][0].value
    assert payload['last_plan_validation']['verification']['reason'] == 'RED_CONTRACT_MISSING'
    assert result['plan']['tasks'] == lifecycle.plan.model_dump(mode='json')['tasks']
    assert result['plan']['architecture_summary'].endswith('candidate 0')
    assert not list(lifecycle.workspace.glob('target-*.txt'))
