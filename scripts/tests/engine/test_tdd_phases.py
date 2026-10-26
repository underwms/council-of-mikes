"""Expected red assertions require runner evidence and a later green obligation."""
import hashlib
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from test_engine_integration import lifecycle, open_graph
from test_autonomous_review import setup, graph_for, ACCEPT


def junit(*cases):
    from xml.etree.ElementTree import Element, SubElement, tostring
    root = Element('testsuites', tests=str(len(cases)), failures=str(sum(bool(failure) for _, failure in cases)), errors='0')
    suite = SubElement(root, 'testsuite', name='tests/rules.test.ts', tests=str(len(cases)),
        failures=root.attrib['failures'], errors='0', skipped='0')
    for name, message in cases:
        case = SubElement(suite, 'testcase', name=name, classname='tests/rules.test.ts')
        if message:
            SubElement(case, 'failure', message='Uncaught '+message).text = message+'\n at fixture:1:1'
    return tostring(root, encoding='unicode')


RED = junit(('missing behavior', 'AssertionError: TDD_RED: required field validation missing'))
GREEN = junit(('missing behavior', None))


def contract():
    return {'implementation_task_id': 'task-2', 'expected_failures': [
        {'command_index': 1, 'test_name': 'missing behavior',
         'assertion_message': 'TDD_RED: required field validation missing'}]}


def make_plan(lifecycle):
    from council.state import MultiSpecialistPlan
    data = lifecycle.plan.model_dump()
    for task in data['tasks']:
        task['target_files'] = ['tests/rules.test.ts'] if task['id'] == 'task-1' else ['implementation.ts']
        task['test_commands'] = [['deno', 'test', '--reporter=junit', 'tests/rules.test.ts']]
    data['tasks'][0].update(verification_phase='red', red_verification=contract())
    return MultiSpecialistPlan.model_validate(data)


def classify(code, output, stderr=''):
    import importlib.util
    assert importlib.util.find_spec('council.verification') is not None, 'Strict phase verification is missing'
    from council import verification
    assert hasattr(verification, 'evaluate_deno_red')
    return verification.evaluate_deno_red(code, output, stderr, contract()['expected_failures'])


def test_strict_report_accepts_named_assertions_only():
    result = classify(1, RED)
    assert result.expectation_met and not result.passed
    assert result.tests_failed == 1 and result.tests_passed == 0


def test_deno_literal_attribute_newlines_preserve_named_assertion_identity():
    # Deno writes literal newlines; XML normalizes attribute whitespace to spaces.
    report = RED.replace('message="Uncaught AssertionError: TDD_RED: required field validation missing"',
        'message="Uncaught AssertionError: TDD_RED: required field validation missing\n\nfalse !== true\n"')
    assert classify(1, report).expectation_met


@pytest.mark.parametrize('code,output,stderr', [
    (0, GREEN, ''), (124, RED, ''), (127, RED, ''), (1, '', 'error: Type checking failed'),
    (1, junit(('missing behavior', 'TypeError: TDD_RED: required field validation missing')), ''),
    (1, junit(('unknown test', 'AssertionError: TDD_RED: required field validation missing')), ''),
    (1, RED.replace('required field validation missing', 'unrelated assertion'), ''),
    (1, RED.replace('tests="1"', 'tests="9"'), ''),
    (1, RED.replace('errors="0"', 'errors="1"'), ''),
    (1, RED.replace('skipped="0"', 'skipped="1"'), ''),
    (1, '<testsuites tests="0" failures="0" errors="0"/>', ''),
    (1, RED+'not XML', ''), (1, '<!DOCTYPE foo>'+RED, ''),
    (1, RED, 'error: Module not found'),
], ids=[f'runner-{number}' for number in range(14)])
def test_bad_runner_results_never_satisfy_red(code, output, stderr):
    assert not classify(code, output, stderr).expectation_met


def test_phase_schema_and_legacy_defaults(lifecycle):
    from council.state import TaskItem
    assert TaskItem.model_validate(lifecycle.plan.tasks[0].model_dump()).verification_phase == 'green'
    assert make_plan(lifecycle).tasks[0].red_verification.implementation_task_id == 'task-2'


@pytest.mark.parametrize('mutation', ['missing_pair', 'no_rerun', 'unchecked', 'wrong_runner', 'missing_contract', 'terminal_red'])
def test_preflight_rejects_incomplete_red_plans(lifecycle, mutation):
    from council.plan_validation import validate_plan
    plan = make_plan(lifecycle)
    red = plan.tasks[0]
    if mutation == 'missing_pair': red.red_verification.implementation_task_id = 'absent'
    if mutation == 'no_rerun': plan.tasks[1].test_commands = [['deno', 'test', 'other.test.ts']]
    if mutation == 'unchecked': red.test_commands[0].append('--no-check')
    if mutation == 'wrong_runner': red.test_commands[0][0] = 'echo'
    if mutation == 'missing_contract': red.red_verification = None
    if mutation == 'terminal_red': plan.tasks.reverse()
    with pytest.raises(ValueError) as caught:
        validate_plan(plan, lifecycle.context, native_coding=True)
    assert caught.value.code == 'PLAN_VERIFICATION_INVALID'


def lifecycle_run(lifecycle, monkeypatch, *, green_output=GREEN, red_output=RED, tamper=False,
                  stop_after_red=False, missing_source=False, extra_task=False):
    plan = make_plan(lifecycle)
    if extra_task:
        followup = plan.tasks[1].model_copy(deep=True)
        followup.id, followup.target_files = 'task-3', []
        plan.tasks.append(followup)
    state, provider, reviewer = setup(lifecycle, monkeypatch, [ACCEPT])
    provider.plan = plan
    def work(task, guidance, **kwargs):
        (lifecycle.workspace/'tests').mkdir(exist_ok=True)
        path = lifecycle.workspace/'tests/rules.test.ts'
        if task.id == 'task-1' and not missing_source: path.write_text('Deno.test("missing behavior", () => {});')
        elif tamper: path.write_text('Deno.test("disabled test", () => {});')
        return AIMessage(content='Fixture task complete')
    provider.run_task = work
    monkeypatch.setattr('council.graph.SubprocessRunner.run', lambda *args, **kwargs:
        (1, red_output, '') if not (lifecycle.workspace/'implementation.ts').exists() else (0, green_output, ''))
    original = work
    def worker(task, *args, **kwargs):
        response = original(task, *args, **kwargs)
        if task.id == 'task-2': (lifecycle.workspace/'implementation.ts').write_text('implementation')
        return response
    provider.run_task = worker
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        result = graph.invoke(state, lifecycle.config, interrupt_after=['prover'] if stop_after_red else None)
    return result, provider, reviewer


def test_expected_red_advances_without_repairs_then_requires_green(lifecycle, monkeypatch):
    result, _, _ = lifecycle_run(lifecycle, monkeypatch)
    assert result['status'] == 'COMPLETED'
    assert result['test_results'][0]['passed'] is False
    assert result['test_results'][0]['expectation_met'] is True
    assert result['test_results'][0]['exit_code'] == 1
    assert result['red_phase_evidence'][0]['closed'] is True
    assert not any(call['operation'] == 'investigation' for call in result['model_calls'])


@pytest.mark.parametrize('tamper,output', [(True, GREEN), (False, '<testsuites tests="0"/>')])
def test_removed_tests_or_empty_green_reports_cannot_finish(lifecycle, monkeypatch, tamper, output):
    result, _, _ = lifecycle_run(lifecycle, monkeypatch, tamper=tamper, green_output=output)
    assert result['status'] == 'FAILED'
    assert not result['red_phase_evidence'][0]['closed']


def test_expected_red_evidence_survives_restart(lifecycle, monkeypatch):
    result, provider, reviewer = lifecycle_run(lifecycle, monkeypatch, stop_after_red=True)
    assert result['current_task_index'] == 1
    assert result['red_phase_evidence'][0]['closed'] is False
    with open_graph(lifecycle, provider) as saver:
        completed = graph_for(lifecycle, saver, provider, reviewer).invoke(None, lifecycle.config)
    assert completed['status'] == 'COMPLETED'


def test_legacy_accepted_digest_does_not_change_with_default_phase_fields(lifecycle):
    from council.plan_review import plan_digest
    original = lifecycle.plan.model_dump(mode='json')
    original.pop('contract_changes', None)
    original.pop('quality_gates', None)
    original.pop('baseline_challenges', None)
    for task in original['tasks']:
        task.pop('status', None)
        task.pop('verification_phase', None)
        task.pop('red_verification', None)
        task.pop('kind', None)
        task.pop('readiness_for', None)
        task.pop('proof_scope', None)
        task.pop('delivery_stage', None)
    legacy = hashlib.sha256(json.dumps(original, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    assert plan_digest(lifecycle.plan) == legacy


@pytest.mark.parametrize('output', [
    RED.replace('<failure ', '<failure type="TypeError" '),
    RED.replace('failures="1"', 'failures="0"'),
    RED.replace('</testcase>', '<skipped/></testcase>'),
    RED.replace('</testcase>', '<error/></testcase>'),
    RED.replace('</testcase>', '<unexpected/></testcase>'),
    RED.replace('<testcase ', '<not-a-case ').replace('</testcase>', '</not-a-case>'),
    RED.replace('name="missing behavior"', 'name=""'),
    '<testsuites><invalid/></testsuites>',
    RED.replace('<testsuites ', '<wrong-root '),
    'x'*1048577,
], ids=[f'malformed-{number}' for number in range(10)])
def test_malformed_or_contradictory_reports_reject(output):
    assert not classify(1, output).expectation_met


@pytest.mark.parametrize('mutation', ['target_not_test', 'duplicate_ids', 'other_directory', 'extra_contract',
    'duplicate_expected', 'out_of_range', 'missing_reporter', 'unsafe_flag', 'wrong_target', 'rewrite_tests'])
def test_red_plan_boundaries_are_enforced(lifecycle, mutation):
    from council.plan_validation import validate_plan
    plan = make_plan(lifecycle)
    task = plan.tasks[0]
    if mutation == 'target_not_test': task.target_files = ['implementation.ts']
    if mutation == 'duplicate_ids': plan.tasks[1].id = task.id
    if mutation == 'other_directory':
        (lifecycle.workspace/'other').mkdir()
        plan.tasks[1].working_directory = 'other'
    if mutation == 'extra_contract': plan.tasks[1].red_verification = task.red_verification
    if mutation == 'duplicate_expected': task.red_verification.expected_failures *= 2
    if mutation == 'out_of_range': task.red_verification.expected_failures[0].command_index = 2
    if mutation == 'missing_reporter': task.test_commands[0].remove('--reporter=junit')
    if mutation == 'unsafe_flag': task.test_commands[0].append('--junit-path=elsewhere.xml')
    if mutation == 'wrong_target':
        task.test_commands[0][-1] = 'tests/different.test.ts'
        plan.tasks[1].test_commands[0][-1] = 'tests/different.test.ts'
    if mutation == 'rewrite_tests': plan.tasks[1].target_files = task.target_files
    with pytest.raises(ValueError) as caught:
        validate_plan(plan, lifecycle.context, native_coding=True)
    assert caught.value.code == 'PLAN_VERIFICATION_INVALID'


def test_real_deno_reports_distinguish_assertions_compile_import_and_runtime(tmp_path):
    import shutil
    import subprocess
    from council.verification import green_transition_met
    executable = shutil.which('deno')
    assert executable, 'Deno is required for this offline reporter integration test'
    path = tmp_path/'rules.test.ts'
    source = ('import assert from "node:assert/strict";\n'
        'import { enabled } from "./feature.ts";\n'
        'Deno.test("missing behavior", () => assert.equal(enabled, true, '
        '"TDD_RED: required field validation missing"));\n')
    path.write_text(source)
    feature = tmp_path/'feature.ts'
    feature.write_text('export const enabled = false;')
    def execute():
        result = subprocess.run([executable, 'test', '--no-config', '--no-lock', '--no-remote', '--reporter=junit', str(path)],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30, cwd=tmp_path)
        return result.returncode, result.stdout, result.stderr
    assert classify(*execute()).expectation_met
    feature.write_text('export const enabled = true;')
    assert green_transition_met(*execute(), ['missing behavior'])
    for invalid in ['const value: number = "not a number";\n'+source,
                    source.replace('./feature.ts', './missing.ts'),
                    'Deno.test("missing behavior", () => { throw new TypeError("TDD_RED: required field validation missing"); });']:
        path.write_text(invalid)
        assert not classify(*execute()).expectation_met


def test_final_audit_cannot_skip_an_open_red_obligation(lifecycle, monkeypatch):
    result, provider, reviewer = lifecycle_run(lifecycle, monkeypatch, stop_after_red=True)
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        graph.update_state(lifecycle.config, {'status': 'GATEKEEPER_AUDIT'}, as_node='prover')
        failed = graph.invoke(None, lifecycle.config)
    assert failed['status'] == 'FAILED'
    assert failed['diagnostic']['code'] == 'TDD_PHASE_INCOMPLETE'


def test_final_audit_detects_late_changes_to_closed_red_tests(lifecycle, monkeypatch):
    result, provider, reviewer = lifecycle_run(lifecycle, monkeypatch)
    assert result['red_phase_evidence'][0]['closed']
    (lifecycle.workspace/'tests/rules.test.ts').write_text('changed after green')
    with open_graph(lifecycle, provider) as saver:
        graph = graph_for(lifecycle, saver, provider, reviewer)
        graph.update_state(lifecycle.config, {'status': 'GATEKEEPER_AUDIT'}, as_node='prover')
        failed = graph.invoke(None, lifecycle.config)
    assert failed['diagnostic']['code'] == 'TDD_PHASE_INCOMPLETE'


@pytest.mark.parametrize('missing_source', [False, True])
def test_bad_red_execution_or_missing_source_never_advances(lifecycle, monkeypatch, missing_source):
    result, _, _ = lifecycle_run(lifecycle, monkeypatch, missing_source=missing_source,
        red_output=RED if missing_source else junit(('missing behavior', 'TypeError: broken test harness')))
    assert result['status'] == 'FAILED'
    assert result['current_task_index'] == 0
    assert result['red_phase_evidence'] == []
    assert not (lifecycle.workspace/'implementation.ts').exists()


def test_closed_red_obligations_allow_unrelated_followup(lifecycle, monkeypatch):
    result, _, _ = lifecycle_run(lifecycle, monkeypatch, extra_task=True)
    assert result['status'] == 'COMPLETED'
    assert result['current_task_index'] == 3
    assert len(result['red_phase_evidence']) == 1 and result['red_phase_evidence'][0]['closed']


def test_source_hashing_rejects_missing_and_oversized_files(lifecycle):
    from council.verification import test_source_hashes, frozen_tests_unchanged
    from council.state import RedPhaseEvidence
    task = make_plan(lifecycle).tasks[0]
    evidence = RedPhaseEvidence(red_task_id='red', green_task_id='green', command_index=1,
        test_names=['fixture'], source_hashes={'tests/rules.test.ts': '0'*64})
    assert test_source_hashes(task, lifecycle.context) is None
    assert not frozen_tests_unchanged([evidence], lifecycle.context)
    (lifecycle.workspace/'tests').mkdir()
    (lifecycle.workspace/'tests/rules.test.ts').write_bytes(b'x'*262145)
    assert test_source_hashes(task, lifecycle.context) is None
    assert not frozen_tests_unchanged([evidence], lifecycle.context)


def test_plan_cannot_exceed_total_red_command_limit(lifecycle):
    from council.state import MultiSpecialistPlan
    from council.plan_validation import validate_plan
    templates = make_plan(lifecycle).model_dump()
    tasks = []
    for number in range(5):
        import copy
        red, green = copy.deepcopy(templates['tasks'])
        red.update(id=f'red-{number}', target_files=[f'tests/rules-{number}.test.ts'])
        green.update(id=f'green-{number}', target_files=[f'implementation-{number}.ts'])
        argv = ['deno', 'test', '--reporter=junit', f'tests/rules-{number}.test.ts']
        red['test_commands'], green['test_commands'] = [argv]*16, [argv]*16
        red['red_verification']['implementation_task_id'] = green['id']
        red['red_verification']['expected_failures'] = [
            {**contract()['expected_failures'][0], 'command_index': command} for command in range(1, 17)]
        tasks.extend([red, green])
    templates['tasks'] = tasks
    with pytest.raises(ValueError) as caught:
        validate_plan(MultiSpecialistPlan.model_validate(templates), lifecycle.context, native_coding=True)
    assert caught.value.code == 'PLAN_VERIFICATION_INVALID'
