"""Interactive severity cues keep the existing JSON stream unchanged."""
import io
import json
import os
from unittest.mock import patch

from council.cli import emit


class Terminal(io.StringIO):
    def isatty(self):
        return True


def test_interactive_blocker_cue_preserves_json():
    output, errors = io.StringIO(), Terminal()
    payload = {'status': 'BLOCKED', 'gate': 'PLAN_REVIEW_BLOCKED', 'run_id': 'fixture'}
    with patch('sys.stdout', output), patch('sys.stderr', errors), patch.dict(os.environ, {}, clear=True):
        emit(payload)
    assert json.loads(output.getvalue()) == payload
    assert 'COUNCIL BLOCKED' in errors.getvalue()
    assert '\x1b[' in errors.getvalue()


def test_interactive_blocker_lists_only_open_issues_before_full_json():
    output, errors = io.StringIO(), Terminal()
    payload = {
        'status': 'BLOCKED', 'gate': 'PLAN_REVIEW_BLOCKED', 'run_id': 'fixture',
        'finding_ledger': [
            {'id': 'F1', 'status': 'resolved', 'description': 'Resolved detail must stay out of summary.'},
            {'id': 'F2', 'status': 'unresolved', 'description': 'Wire the batch-aware fixture after its migration.'},
        ],
        'findings': ['Wire the batch-aware fixture after its migration.'],
        'diagnostic': {'code': 'PLAN_REVIEW_EXHAUSTED'},
    }
    with patch('sys.stdout', output), patch('sys.stderr', errors), patch.dict(os.environ, {'NO_COLOR': '1'}):
        emit(payload)
    human = errors.getvalue()
    assert 'Open issues (1)' in human
    assert 'F2' in human and 'Wire the batch-aware fixture' in human
    assert 'Resolved detail' not in human and 'F1' not in human
    assert human.index('Open issues') < human.index('Full JSON')
    assert json.loads(output.getvalue()) == payload
    assert 'Resolved detail' in output.getvalue()


def test_interactive_blocker_uses_unresolved_findings_without_ledger():
    output, errors = io.StringIO(), Terminal()
    payload = {'status': 'BLOCKED', 'findings': ['First open issue', 'Second open issue']}
    with patch('sys.stdout', output), patch('sys.stderr', errors), patch.dict(os.environ, {'NO_COLOR': '1'}):
        emit(payload)
    human = errors.getvalue()
    assert 'Open issues (2)' in human
    assert '1. First open issue' in human
    assert '2. Second open issue' in human
    assert json.loads(output.getvalue()) == payload


def test_operational_blocker_labels_last_completed_review():
    output, errors = io.StringIO(), Terminal()
    payload = {'status': 'BLOCKED', 'blocker_kind': 'operational_failure',
               'diagnostic': {'code': 'CLI_EXECUTION_FAILED', 'message': 'Native CLI execution failed.'},
               'finding_ledger': [{'id': 'F4', 'status': 'unresolved', 'description': 'Earlier review finding.'}]}
    with patch('sys.stdout', output), patch('sys.stderr', errors), patch.dict(os.environ, {'NO_COLOR': '1'}):
        emit(payload)
    human = errors.getvalue()
    assert 'Review interrupted (CLI_EXECUTION_FAILED)' in human
    assert 'Open issues from last completed review (1)' in human
    assert 'F4. Earlier review finding.' in human
    assert json.loads(output.getvalue()) == payload


def test_interactive_error_cue_is_distinct_and_respects_no_color():
    output, errors = io.StringIO(), Terminal()
    payload = {'status': 'FAILED', 'diagnostic': {'code': 'PROVIDER_UNAVAILABLE'}}
    with patch('sys.stdout', output), patch('sys.stderr', errors), patch.dict(os.environ, {'NO_COLOR': '1'}):
        emit(payload)
    assert json.loads(output.getvalue()) == payload
    assert 'COUNCIL ERROR' in errors.getvalue()
    assert 'COUNCIL BLOCKED' not in errors.getvalue()
    assert '\x1b[' not in errors.getvalue()


def test_redirected_output_has_no_extra_cue():
    output, errors = io.StringIO(), io.StringIO()
    with patch('sys.stdout', output), patch('sys.stderr', errors):
        emit({'status': 'BLOCKED'})
    assert errors.getvalue() == ''
    assert json.loads(output.getvalue()) == {'status': 'BLOCKED'}


def test_current_preflight_blocker_is_visible_when_review_has_no_open_findings():
    output, errors = io.StringIO(), Terminal()
    payload = {'status': 'BLOCKED', 'blocker_kind': 'budget_exhausted', 'orchestration_policy_version': 2,
        'finding_ledger': [{'id': 'F1', 'status': 'resolved', 'description': 'Resolved private detail'}],
        'findings': [], 'diagnostic': {'code': 'PLAN_REVIEW_EXHAUSTED'},
        'last_plan_validation': {'code': 'PLAN_VERIFICATION_INVALID', 'task_index': 1,
            'field': 'readiness_for', 'task_description': 'PRIVATE_DESCRIPTION',
            'verification': {'reason': 'READINESS_REFERENCE', 'field': 'readiness_for',
                'command_index': None, 'related_task_index': None}}}
    with patch('sys.stdout', output), patch('sys.stderr', errors), patch.dict(os.environ, {'NO_COLOR': '1'}):
        emit(payload)
    human = errors.getvalue()
    assert 'Open issues (1)' in human
    assert 'Task 1' in human and 'READINESS_REFERENCE' in human
    assert 'implementation task IDs' in human
    assert 'all-readiness' in human and 'empty' in human
    assert 'Resolved private detail' not in human and 'PRIVATE_DESCRIPTION' not in human
    assert json.loads(output.getvalue()) == payload
