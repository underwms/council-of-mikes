"""Explicit Deno TDD phases; subprocess facts remain separate from expectations."""
import hashlib
from pathlib import Path, PureWindowsPath
import re
from xml.etree import ElementTree as ET

from council.state import TestExecutionResult
from council.verification_feedback import rejection
from council.tools.discovery import validate_read_path
from council.red_feedback import detail


def junit_cases(stdout, stderr):
    """Parse a bounded complete Deno report; reject errors, skips and ambiguity."""
    if len(stdout.encode('utf-8')) > 1048576 or '<!DOCTYPE' in stdout.upper() or '<!ENTITY' in stdout.upper():
        raise ValueError('Invalid report')
    clean = re.sub(r'\x1b\[[0-9;]*m', '', stderr)
    for line in clean.splitlines():
        if re.match(r'\s*(?:error:|(?:error\s+)?TS\d+|TypeError:|ReferenceError:|SyntaxError:)', line, re.I):
            if line.strip() != 'error: Test failed':
                raise ValueError('Runner error')
    root = ET.fromstring(stdout)
    if root.tag != 'testsuites' or not len(root) or any(suite.tag != 'testsuite' for suite in root):
        raise ValueError('Invalid suite')
    cases = []
    def check_counts(node, items):
        failures = sum(bool(item.findall('failure')) for item in items)
        if (int(node.get('tests', '-1')) != len(items) or int(node.get('failures', '-1')) != failures
                or any(int(node.get(key, '0')) != 0 for key in ('errors', 'skipped', 'disabled'))):
            raise ValueError('Inconsistent report')
    for suite in root:
        items = list(suite)
        if any(item.tag != 'testcase' for item in items):
            raise ValueError('Invalid test case')
        check_counts(suite, items)
        cases.extend(items)
    check_counts(root, cases)
    names = [case.get('name', '') for case in cases]
    if not 1 <= len(cases) <= 256 or len(set(names)) != len(names) or any(not name.strip() or len(name.encode('utf-8')) > 256 for name in names):
        raise ValueError('Invalid test names')
    for case in cases:
        if (case.findall('error') or case.findall('skipped') or len(case.findall('failure')) > 1
                or any(child.tag not in {'failure', 'system-out', 'system-err'} for child in case)):
            raise ValueError('Test execution error')
    return {case.get('name'): case.find('failure') for case in cases}


def _red_set_reason(code, cases, expected, expectation_count):
    if code != 1:
        return 'EXIT_CODE'
    if not expected:
        return 'EXPECTATIONS_EMPTY'
    if len(expected) != expectation_count:
        return 'EXPECTATIONS_DUPLICATE'
    if set(expected) - set(cases):
        return 'MISSING_EXPECTED_CASE'
    if any(cases[name] is None for name in expected):
        return 'EXPECTED_CASE_PASSED'
    if any(failure is not None and name not in expected for name, failure in cases.items()):
        return 'UNEXPECTED_FAILURE'
    return None


def _red_assertion_reason(failure, message):
    header = 'Uncaught AssertionError: ' + message
    reported = failure.get('message', '')
    if failure.get('type') not in (None, 'AssertionError'):
        return 'ASSERTION_TYPE'
    if not (reported == header or reported.startswith(header + ' ') or reported.startswith(header + '\n')):
        return 'ASSERTION_HEADER'
    if not (failure.text or '').startswith('AssertionError: ' + message + '\n'):
        return 'ASSERTION_BODY'
    return None


def evaluate_deno_red(code, stdout, stderr, expectations):
    result = TestExecutionResult(command='deno', passed=code == 0, exit_code=code,
        verification_phase='red', expectation_met=False, verification_reason='RED_EXPECTATION_NOT_MET')
    try:
        cases = junit_cases(stdout, stderr)
        failed = {name: failure for name, failure in cases.items() if failure is not None}
        result.tests_failed, result.tests_passed = len(failed), len(cases) - len(failed)
        result.counts_known = True
        expected = {item['test_name']: item['assertion_message'] for item in expectations}
        reason = _red_set_reason(code, cases, expected, len(expectations))
        if reason is not None:
            result.verification_detail = detail(reason, expectations, cases)
            return result
        for index, (name, message) in enumerate(expected.items(), 1):
            reason = _red_assertion_reason(failed[name], message)
            if reason is not None:
                result.verification_detail = detail(reason, expectations, cases, assertion_index=index)
                return result
        result.expectation_met, result.verification_reason = True, 'EXPECTED_RED_CONFIRMED'
    except (ValueError, ET.ParseError, IndexError):
        result.verification_detail = detail('REPORT_INVALID', expectations)
    return result


def green_transition_met(code, stdout, stderr, prior_names):
    try:
        cases = junit_cases(stdout, stderr)
        return (code == 0 and 'error:' not in stderr.lower() and set(prior_names) <= set(cases)
                and all(failure is None for failure in cases.values()))
    except (ValueError, ET.ParseError):
        return False


def test_source_hashes(task, context):
    """Freeze only declared test sources, without persisting file contents."""
    hashes = {}
    try:
        for path in task.target_files:
            with validate_read_path(context, path).open('rb') as source:
                data = source.read(262145)
            if len(data) > 262144:
                return None
            hashes[path] = hashlib.sha256(data).hexdigest()
    except (OSError, ValueError):
        return None
    return hashes or None


def frozen_tests_unchanged(evidence, context):
    try:
        for item in evidence:
            for path, digest in item.source_hashes.items():
                with validate_read_path(context, path).open('rb') as source:
                    data = source.read(262145)
                if len(data) > 262144 or hashlib.sha256(data).hexdigest() != digest:
                    return False
        return True
    except (OSError, ValueError):
        return False


def validate_red_contracts(plan, context):
    """Preflight pairs every red command with a later green rerun of the same argv."""
    red_tasks = [task for task in plan.tasks if task.verification_phase == 'red']
    if not red_tasks and not any(task.red_verification for task in plan.tasks):
        return
    ids = [task.id for task in plan.tasks]
    for index, task in enumerate(plan.tasks, start=1):
        def reject(reason, *, command_index=None, related_task_index=None):
            raise rejection(index, reason, command_index=command_index, related_task_index=related_task_index)
        if len(set(ids)) != len(ids):
            reject('TASK_IDS_DUPLICATE')
        if task.verification_phase == 'green':
            if task.red_verification is not None:
                reject('GREEN_CONTRACT_PRESENT')
            continue
        contract = task.red_verification
        if not contract:
            reject('RED_CONTRACT_MISSING')
        if not 1 <= len(task.target_files) <= 32:
            reject('RED_TARGET_COUNT')
        if not 1 <= len(task.test_commands) <= 16:
            reject('RED_COMMAND_COUNT')
        if any(not path.endswith(('.test.ts', '_test.ts')) for path in task.target_files):
            reject('RED_TARGET_TYPE')
        frozen = {context.workspace_path(path) for path in task.target_files}
        for later_index, later in enumerate(plan.tasks[index:], start=index + 1):
            if any(context.workspace_path(path) in frozen for path in later.target_files):
                reject('FROZEN_TEST_TARGETED', related_task_index=later_index)
        match = next(((position, other) for position, other in enumerate(plan.tasks)
            if other.id == contract.implementation_task_id), None)
        if not match:
            reject('IMPLEMENTATION_MISSING')
        related = match[0] + 1
        if match[0] < index:
            reject('IMPLEMENTATION_ORDER', related_task_index=related)
        if match[1].verification_phase != 'green':
            reject('IMPLEMENTATION_PHASE', related_task_index=related)
        if context.workspace_path(match[1].working_directory) != context.workspace_path(task.working_directory):
            reject('IMPLEMENTATION_CWD', related_task_index=related)
        if sum(len(other.test_commands) for other in red_tasks) > 64:
            reject('PLAN_RED_COMMAND_LIMIT')
        expected = contract.expected_failures
        keys = [(item.command_index, item.test_name) for item in expected]
        if len(set(keys)) != len(keys):
            reject('EXPECTATIONS_DUPLICATE')
        if {item.command_index for item in expected} != set(range(1, len(task.test_commands) + 1)):
            reject('EXPECTATIONS_COMMANDS')
        for command_index, argv in enumerate(task.test_commands, start=1):
            files = [arg for arg in argv[2:] if not arg.startswith('-')]
            forbidden = ('--no-check', '--no-run', '--junit-path', '--watch', '--filter', '--retry',
                         '--fail-fast', '--ignore', '--permit-no-files', '--repeats', '--doc')
            if (len(argv) < 4 or PureWindowsPath(argv[0]).name.lower() not in {'deno', 'deno.exe'}
                    or argv[1] != 'test'):
                reject('RED_RUNNER', command_index=command_index)
            if argv.count('--reporter=junit') != 1:
                reject('RED_REPORTER', command_index=command_index)
            if any(arg.startswith(forbidden) or (arg.startswith('--reporter') and arg != '--reporter=junit') for arg in argv):
                reject('RED_FLAGS', command_index=command_index)
            if len(files) != 1:
                reject('RED_SOURCE_COUNT', command_index=command_index)
            if argv not in match[1].test_commands:
                reject('GREEN_RERUN_MISSING', command_index=command_index, related_task_index=related)
            path = context.workspace_path(Path(task.working_directory)/files[0])
            if path not in [context.workspace_path(target) for target in task.target_files]:
                reject('RED_SOURCE_UNDECLARED', command_index=command_index)
