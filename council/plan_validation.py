"""Canonical specialist identifiers and safe plan preflight, before approval."""
import json
import re
import shutil
import stat
import sys

from council.diagnostics import DiagnosticValueError, DiagnosticRuntimeError
from council.prompt_context import _read, _safe
from council.specialists import SpecialistLoader
from council.tools.discovery import validate_discovery_path
from council.verification_feedback import rejection
from council.command_policy import validate_command_policy
from council.readiness import CONTRACT as READINESS_CONTRACT
from council.readiness import PHASE_CONTRACT, TARGETED_CONTRACT
from council.readiness import decision_boundary

_NAME = re.compile(r'[a-z][a-z0-9-]{0,127}\Z')


def _multi_repository_workspace(context):
    repositories = 0
    for child in context.workspace_root.iterdir():
        if child.is_symlink() or getattr(child, 'is_junction', lambda: False)():
            continue
        if child.is_dir() and (child / '.git').exists():
            repositories += 1
            if repositories > 1:
                return True
    return False


def plan_contract(context, *, require_readiness=False, phase_scoped=False, readiness_policy_version=2):
    """The same path/argv contract for planning, review and tool-free revisions."""
    return {
        **({'readiness': TARGETED_CONTRACT if readiness_policy_version >= 3 else PHASE_CONTRACT if phase_scoped else READINESS_CONTRACT,
            'decision_boundary': decision_boundary(phase_scoped=phase_scoped,
                policy_version=readiness_policy_version)} if require_readiness else {}),
        'workspace_root': str(context.workspace_root),
        'execution_environment': {'platform': sys.platform, 'python_executable': sys.executable,
            'available_commands': {name: shutil.which(name) is not None
                for name in ('pwsh', 'powershell.exe', 'node', 'npm', 'deno', 'dotnet', 'docker', 'git')},
            'rule': 'Use observed installed executables. Any missing tool needs an explicit readiness setup '
                'and probe before later use. Availability does not establish permissions, authentication or service readiness.'},
        'target_files': 'Every target is relative to the workspace root, NOT relative to working_directory. '
            'List individual existing or planned files, never directories. Proposed generated filenames may be listed before they exist. '
            'Include the project prefix, for example project/app/file.ts. No absolute paths, parent traversal, '
            'or paths resolving outside the workspace. Council instruction paths are read-only context, not edit targets. '
            'Green tasks with no edit targets run only their declared test_commands, without a coding session.',
        'working_directory': 'Use a workspace-relative existing safe directory for native coding, such as project or ".". '
            'In a multi-repository workspace, any task with edit targets must use a narrower project or target directory; '
            'a workspace-root source inventory is too broad. Adjust verification argv to that directory. '
            'Never use an absolute path, parent traversal, or a redirected/private discovery path.',
        'test_commands': 'Every task requires nonempty explicit argv arrays containing only nonempty strings. '
            'Commands run from working_directory. Do not declare external validation scripts as edit targets. '
            'No execution-policy overrides: do not use PowerShell -ExecutionPolicy, -ep or abbreviations. '
            'Use normal trusted -NoProfile -File invocations and record native policy limitations without bypassing them.',
        'specialists': list(plan_specialists(context)),
        'proof_scope': 'When supported project metadata has been observed, declare proof_scope version 1 with '
            'its workspace-relative project path and any consumed generated inputs. Keep runtime_mutable true '
            'for tests, fixtures, services or uncertainty. Dependency discovery, not model assertions, decides '
            'the actual scope; unsupported relationships take the conservative fallback. Never narrow old receipts. '
            'For .NET proof scopes use literal dotnet restore/build/test project.csproj or solution.slnx, '
            'or dotnet run --project project.csproj, with optional --no-build/--no-restore/--nologo, '
            'test --filter VALUE, and an optional empty trailing run -- separator. Exact git diff --check '
            'is supported and observes the repository. Other arguments require a separately supported verification contract.',
        'tdd': 'Default verification_phase is green and requires exit zero. Test-writing tasks intended to fail '
            'must declare verification_phase red and red_verification with implementation_task_id and expected_failures '
            '(command_index, exact test_name, assertion_message starting TDD_RED: with a meaningful reason). '
            'Use deno test --reporter=junit with one declared .test.ts/_test.ts file per command; keep type checking enabled. '
            'Every red command must be rerun unchanged by the named later green task in the same working directory. '
            'Tests must compile/load; prepare required interfaces or harness in an earlier green task. '
            'Accepted red test files are frozen through final audit; do not weaken or rewrite them to obtain green.',
        'tdd_frozen_targets': 'Red tasks target only test sources. No later task may list those files in target_files, '
            'including green implementation, verification, documentation or final audit tasks. Rerunning tests does not require targeting them for edits.',
        'tdd_example': [
            dict(id='example-red', description='Write compile-ready failing behavior test', specialist='the-prover',
                working_directory='.', target_files=['tests/behavior.test.ts'],
                test_commands=[['deno', 'test', '--reporter=junit', 'tests/behavior.test.ts']],
                verification_phase='red', red_verification=dict(implementation_task_id='example-green',
                    expected_failures=[dict(command_index=1, test_name='required behavior',
                        assertion_message='TDD_RED: required behavior missing')])),
            dict(id='example-green', description='Implement required behavior without editing the frozen test',
                specialist='the-coder', working_directory='.', target_files=['implementation.ts'],
                test_commands=[['deno', 'test', '--reporter=junit', 'tests/behavior.test.ts']],
                verification_phase='green'),
        ],
    }


def plan_specialists(context):
    """Use only the declared specialist catalog, never the workflow inventory."""
    try:
        manifest = json.loads(_read(_safe(context.council_root, 'manifest.json')) or '{}')
        names = manifest.get('specialists')
        if (not isinstance(names, list) or not names or len(names) > 64
                or any(not isinstance(name, str) or not _NAME.fullmatch(name) for name in names)
                or len(set(names)) != len(names)):
            raise ValueError('Invalid catalog')
        return tuple(names)
    except (OSError, ValueError, TypeError, AttributeError):
        raise DiagnosticRuntimeError('PLAN_CATALOG_INVALID') from None


def validate_plan(plan, context, *, native_coding, require_readiness=False, frozen_files=(), phase_scoped=False, readiness_policy_version=2):
    """Validate a copy; accept canonical IDs or their exact known display aliases."""
    names = plan_specialists(context)
    aliases = {'[' + name.upper().replace('-', ' ') + ']': name for name in names}
    validated = plan.model_copy(deep=True)
    frozen = {context.workspace_path(path) for path in frozen_files}
    if require_readiness:
        from council.readiness import validate
        validate(validated, phase_scoped=phase_scoped, policy_version=readiness_policy_version)
    for index, task in enumerate(validated.tasks, start=1):
        if not task.test_commands:
            raise rejection(index, 'COMMANDS_EMPTY')
        for command_index, command in enumerate(task.test_commands, start=1):
            if not command:
                raise rejection(index, 'COMMAND_EMPTY', command_index=command_index)
            if any(not isinstance(arg, str) or not arg for arg in command):
                raise rejection(index, 'ARGUMENT_EMPTY', command_index=command_index)
        validate_command_policy(task.test_commands, index)
        if task.proof_scope is not None and task.proof_scope.project.endswith('.csproj') and task.kind != 'readiness':
            from council.proof_dependencies import command_input
            for command_index, command in enumerate(task.test_commands, start=1):
                try:
                    command_input(command)
                except ValueError:
                    raise rejection(index, 'PROOF_COMMAND_UNSUPPORTED', command_index=command_index) from None
        try:
            context.workspace_path(task.working_directory)
            if native_coding and not validate_discovery_path(context, task.working_directory).is_dir():
                raise ValueError('Missing directory')
            if (native_coding and task.target_files and task.working_directory in {'.', ''}
                    and _multi_repository_workspace(context)):
                raise ValueError('Native edit scope spans multiple repositories')
        except (OSError, ValueError):
            raise DiagnosticValueError('PLAN_WORKING_DIRECTORY_INVALID', task_index=index) from None
        for field_index, path in enumerate(task.target_files, start=1):
            try:
                target = context.workspace_path(path)
            except (OSError, ValueError):
                raise DiagnosticValueError('PLAN_TARGET_PATH_INVALID', task_index=index, field_index=field_index) from None
            try:
                mode = target.stat().st_mode
            except FileNotFoundError:
                pass  # New files, including generated migrations, are valid planned targets.
            else:
                if not stat.S_ISREG(mode):
                    raise DiagnosticValueError('PLAN_TARGET_PATH_INVALID', task_index=index, field_index=field_index)
            if context.workspace_path(path) in frozen:
                raise rejection(index, 'FROZEN_TEST_TARGETED')
        identifier = aliases.get(task.specialist, task.specialist)
        if identifier not in names:
            raise DiagnosticValueError('PLAN_SPECIALIST_INVALID', task_index=index)
        try:
            package = SpecialistLoader(context=context).get_specialist(identifier)
            if package is None:
                raise ValueError('Missing package')
        except (OSError, ValueError):
            raise DiagnosticValueError('PLAN_SPECIALIST_UNAVAILABLE', task_index=index) from None
        task.specialist = identifier
    from council.verification import validate_red_contracts
    validate_red_contracts(validated, context)
    return validated
