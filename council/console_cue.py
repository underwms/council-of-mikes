"""Short interactive severity cues alongside unchanged JSON output."""

import os
import shutil
import sys
import textwrap

from rich.console import Console

_PREFLIGHT_GUIDANCE = {
    'PLAN_TARGET_PATH_INVALID': 'Use declared workspace-relative targets inside the workspace boundary.',
    'PLAN_WORKING_DIRECTORY_INVALID': 'Use an existing safe workspace-relative working directory with the required project scope.',
    'PLAN_SPECIALIST_INVALID': 'Use an installed canonical Council specialist identifier.',
    'PLAN_VERIFICATION_INVALID': 'Correct the task verification argv or phase contract; see last_plan_validation in the JSON.',
}


def _open_issues(value):
    ledger = value.get('finding_ledger')
    if isinstance(ledger, list) and ledger:
        issues = [(str(item.get('id') or index), str(item.get('description') or '').strip())
                for index, item in enumerate(ledger, 1)
                if isinstance(item, dict) and item.get('status') != 'resolved' and item.get('description')]
    else:
        findings = value.get('findings')
        issues = [(str(index), item.strip()) for index, item in enumerate(findings, 1)
                  if isinstance(item, str) and item.strip()] if isinstance(findings, list) else []
    validation = value.get('last_plan_validation')
    code = validation.get('code') if isinstance(validation, dict) else None
    if isinstance(code, str) and code in _PREFLIGHT_GUIDANCE:
        from council.verification_feedback import correction
        detail = (correction(validation.get('verification'), phase_scoped=value.get('orchestration_policy_version') == 2)
                  if code == 'PLAN_VERIFICATION_INVALID' else None)
        index = validation.get('task_index')
        if type(index) is int and 1 <= index <= 100000:
            description = f'{detail["reason"]}. {detail["guidance"]}' if detail else f'{code}. {_PREFLIGHT_GUIDANCE[code]}'
            issues.append(('Preflight', f'Task {index}: {description}'))
    return issues


def show_status_cue(value):
    """Mark a final blocker or error for a human terminal, without altering JSON."""
    stream = sys.stderr
    if not stream.isatty():
        return

    status = value.get('status')
    if status == 'BLOCKED':
        label, color = 'BLOCKED', 'yellow'
    elif status == 'FAILED':
        label, color = 'ERROR', 'red'
    else:
        return

    if 'NO_COLOR' in os.environ:
        print(f'COUNCIL {label}', file=stream, flush=True)
    else:
        Console(file=stream, force_terminal=True, color_system='standard', highlight=False).print(
            f'[bold {color}]COUNCIL {label}[/]', end='\n')

    if status == 'BLOCKED':
        issues = _open_issues(value)
        diagnostic = value.get('diagnostic') or {}
        operational = value.get('blocker_kind') == 'operational_failure'
        revision_contract = value.get('blocker_kind') == 'revision_contract'
        if revision_contract:
            print(f'Revision contract correction failed: {diagnostic.get("message") or "See full JSON."}', file=stream)
            feedback = value.get('document_revision_feedback')
            if isinstance(feedback, dict):
                from council.schema_feedback import correction
                detail = correction(feedback.get('schema'))
                if detail:
                    print(f'  {detail["field"]}: {detail["guidance"]}', file=stream)
                from council.json_feedback import safe_detail
                parser = safe_detail(feedback.get('response_json'))
                if parser:
                    print(f'  JSON {parser["reason"]}, line {parser["line"]}, column {parser["column"]}.', file=stream)
        if operational and isinstance(diagnostic, dict) and diagnostic.get('code'):
            print(f'Review interrupted ({diagnostic["code"]}): {diagnostic.get("message") or "See full JSON."}', file=stream)
        heading = 'Open issues from last completed review' if operational or revision_contract else 'Open issues'
        print(f'{heading} ({len(issues)}):', file=stream)
        width = max(60, min(shutil.get_terminal_size(fallback=(100, 24)).columns, 120))
        for identity, description in issues:
            prefix = f'  {identity}. '
            print(textwrap.fill(description, width=width, initial_indent=prefix,
                                subsequent_indent=' ' * len(prefix), break_long_words=False), file=stream)
        if not issues:
            message = diagnostic.get('message') if isinstance(diagnostic, dict) else None
            print(f'  {message or "No unresolved review findings were reported."}', file=stream)
        print('Full JSON (copy/paste):', file=stream, flush=True)
