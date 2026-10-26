"""Bounded runtime red-verification facts and private accepted-contract guidance."""

REASONS = {
    'REPORT_INVALID': 'Repair report, compiler, import or runtime problems; obtain a complete valid JUnit report.',
    'EXIT_CODE': 'Run the declared command unchanged; expected red requires actual exit code 1.',
    'EXPECTATIONS_EMPTY': 'The accepted red command must have explicit expected assertion failures.',
    'EXPECTATIONS_DUPLICATE': 'Expected failure identities must be unique within the command.',
    'MISSING_EXPECTED_CASE': 'Create every missing accepted test and the genuine harness it needs.',
    'EXPECTED_CASE_PASSED': 'Inspect why a declared missing behavior already passes; do not manufacture a failure.',
    'UNEXPECTED_FAILURE': 'Repair failures outside the accepted named red assertions without deleting coverage.',
    'ASSERTION_TYPE': 'Use the accepted meaningful AssertionError rather than a harness/runtime exception.',
    'ASSERTION_HEADER': 'Use the exact accepted TDD_RED assertion message for the intended failing assertion.',
    'ASSERTION_BODY': 'Ensure the failing assertion body identifies the exact accepted TDD_RED assertion.',
    'FROZEN_SOURCE_CHANGED': 'Restore stable declared test sources before verification; do not rewrite frozen tests.',
}
_KEYS = {'reason', 'expected_count', 'observed_count', 'missing_expected', 'passed_expected',
         'unexpected_failure_count', 'assertion_index'}
_GUIDANCE = (' Preserve baseline passing tests. Do not omit or delete accepted tests, use unconditional throws, '
    'weaken assertions, or implement later green work to force red. Fail through meaningful assertions. '
    'If the required harness cannot support the accepted contract, identify that blocker explicitly.')


def safe_detail(value):
    if (type(value) is not dict or set(value) != _KEYS
            or type(value['reason']) is not str or value['reason'] not in REASONS):
        return None
    for field, limit in [('expected_count', 64), ('observed_count', 256), ('unexpected_failure_count', 256)]:
        number = value[field]
        if number is not None and (type(number) is not int or not 0 <= number <= limit):
            return None
    bound = value['expected_count'] or 0
    for field in ('missing_expected', 'passed_expected'):
        indices = value[field]
        if (type(indices) is not list or len(indices) > 64
                or any(type(n) is not int or not 1 <= n <= bound for n in indices)
                or len(set(indices)) != len(indices)):
            return None
    index = value['assertion_index']
    if index is not None and (type(index) is not int or not 1 <= index <= bound):
        return None
    return {**value, 'missing_expected': list(value['missing_expected']), 'passed_expected': list(value['passed_expected'])}


def detail(reason, expectations, cases=None, *, assertion_index=None):
    names = {item['test_name'] for item in expectations}
    return safe_detail(dict(reason=reason, expected_count=len(expectations),
        observed_count=len(cases) if cases is not None else None,
        missing_expected=[n for n, item in enumerate(expectations, 1) if item['test_name'] not in cases] if cases is not None else [],
        passed_expected=[n for n, item in enumerate(expectations, 1) if item['test_name'] in cases and cases[item['test_name']] is None] if cases is not None else [],
        unexpected_failure_count=sum(failure is not None and name not in names for name, failure in cases.items()) if cases is not None else None,
        assertion_index=assertion_index))


def command_index(value):
    return value if type(value) is int and 1 <= value <= 100000 else None


def sanitize_result(value):
    if not isinstance(value, dict):
        return value
    result = {key: item for key, item in value.items() if key not in {'verification_detail', 'command_index'}}
    index = command_index(value.get('command_index'))
    if index is not None:
        result['command_index'] = index
    facts = safe_detail(value.get('verification_detail')) if value.get('verification_phase') == 'red' else None
    if facts is not None:
        result['verification_detail'] = facts
    return result


def correction(task, result):
    contract = getattr(task, 'red_verification', None)
    if not contract or result is None:
        return None
    data = result.model_dump() if hasattr(result, 'model_dump') else sanitize_result(result)
    if not isinstance(data, dict):
        return None
    facts = safe_detail(data.get('verification_detail')) if data.get('verification_phase') == 'red' else None
    index = command_index(data.get('command_index'))
    if facts is None or index is None or index > len(task.test_commands):
        return None
    expected = [item for item in contract.expected_failures if item.command_index == index]
    if facts['expected_count'] != len(expected):
        return None
    selected = set(facts['missing_expected'] + facts['passed_expected'])
    if facts['assertion_index'] is not None:
        selected.add(facts['assertion_index'])
    return {'command_index': index, 'verification_detail': facts,
        'guidance': REASONS[facts['reason']] + _GUIDANCE,
        'required_expectations': [item.model_dump() for n, item in enumerate(expected, 1) if n in selected]}
