"""Conservative, bounded project closure discovered from current repository metadata."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
import subprocess
import re
import xml.etree.ElementTree as ET
from council.native_inventory import snapshot, InventoryBudget
from council.tools.discovery import validate_discovery_path, validate_read_path, MAX_FILE_BYTES

CONFIG_NAMES = {'global.json', 'nuget.config', 'NuGet.Config', '.editorconfig',
    'Directory.Build.props', 'Directory.Build.targets', 'Directory.Packages.props',
    'NuGet.Config', 'packages.lock.json'}


@dataclass(frozen=True)
class DependencySnapshot:
    method: str
    hashes: dict[str, str | None]
    toolchain_sha256: str | None
    runtime_mutable: bool


def _xml(context, path, observed=None):
    with validate_read_path(context, path).open('rb') as source:
        data = source.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Unsupported project metadata')
    tree = ET.fromstring(data)
    if observed is not None:
        observed[path] = hashlib.sha256(data).hexdigest()
    return tree


def _relative(context, base, reference):
    if not reference or any(c in reference for c in '$*?;') or Path(reference).is_absolute():
        raise ValueError('Unsupported project reference')
    path = (context.workspace_path(base).parent / reference.replace('\\', '/')).resolve()
    relative = path.relative_to(context.workspace_root).as_posix()
    validate_read_path(context, relative)
    return relative


def _toolchain(task, context):
    executable = task.test_commands[0][0] if task.test_commands else ''
    path = shutil.which(executable)
    if not path:
        return None
    target = Path(path)
    try:
        # Executable identity is observed, without retaining installation paths or environment.
        if target.stat().st_size > 64 * 1024 * 1024:
            return None
        executable_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        if target.stem.lower()=='dotnet':
            result = subprocess.run([str(target),'--version'],cwd=context.workspace_path(task.working_directory),
                capture_output=True,timeout=5,check=False,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            sdk = result.stdout.decode('ascii',errors='replace').strip()
            if result.returncode or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-.A-Za-z0-9]+)?',sdk):
                return None
            return hashlib.sha256((executable_hash+':'+sdk).encode()).hexdigest()
        return executable_hash
    except (OSError,subprocess.TimeoutExpired):
        return None


def _local_item(context, project, reference):
    """Local item globs are covered by the complete project-directory inventory."""
    relative = Path(reference.replace('\\', '/'))
    if (not reference or any(c in reference for c in '$@%;:[]')
            or relative.anchor or '..' in relative.parts):
        raise ValueError('Unsupported explicit input topology')
    # Check both the selector and its literal prefix, including excluded/linked
    # directories. No glob expansion or MSBuild expression evaluation is needed.
    base = Path(project).parent
    validate_discovery_path(context, (base/relative).as_posix())
    prefix = base
    for part in relative.parts:
        if '*' in part or '?' in part:
            break
        prefix /= part
    validate_discovery_path(context, prefix.as_posix())


def _runsettings(context, project, value):
    """Observe literal optional settings even when their Exists condition is false."""
    reference = (value or '').strip().removeprefix('$(MSBuildThisFileDirectory)')
    if not reference or any(c in reference for c in '$@%*?;:') or Path(reference.replace('\\', '/')).anchor:
        raise ValueError('Unsupported settings input')
    # Normalize leading parent segments without resolving a settings symlink
    # before the discovery guard can inspect it.
    base = context.workspace_path(project).parent
    parts = list(Path(reference.replace('\\', '/')).parts)
    while parts and parts[0] == '..':
        base = base.parent
        parts.pop(0)
    if '..' in parts:
        raise ValueError('Unsupported settings traversal')
    target = base.joinpath(*parts)
    relative = target.relative_to(context.workspace_root).as_posix()
    validate_discovery_path(context, relative)
    return relative


def command_input(argv):
    """Parse only literal command inputs; shared by admission and capture."""
    if argv and Path(argv[0]).stem.lower() == 'git' and argv[1:] == ['diff', '--check']:
        return None
    if len(argv) < 3 or Path(argv[0]).stem.lower() != 'dotnet' or argv[1] not in {'restore','test','build','run'}:
        raise ValueError('Unsupported proof command')
    operation = argv[1]
    if operation == 'run' and '--project' not in argv[2:]:
        raise ValueError('Run requires explicit project')
    args, explicit = iter(argv[2:]), None
    for arg in args:
        if arg == '--' and operation == 'run':
            if next(args, None) is not None:
                raise ValueError('Unresolved runtime inputs')
            break
        if arg in {'--no-restore','--no-build','--nologo'}:
            continue
        if arg == '--filter' and operation == 'test':
            if not next(args, None):
                raise ValueError('Missing filter')
            continue
        if arg == '--project':
            arg = next(args, '')
        suffixes = ('.csproj', '.slnx') if operation in {'build','restore','test'} else ('.csproj',)
        if explicit is not None or not arg.endswith(suffixes) or arg.startswith('-'):
            raise ValueError('Unsupported proof command inputs')
        if any(c in arg for c in '$*?;') or Path(arg).is_absolute():
            raise ValueError('Nonliteral command input')
        explicit = arg
    if explicit is None:
        raise ValueError('Explicit project required')
    return explicit


def _repository(context, directory):
    """Git checks consume the complete affected repository, never just a project."""
    current = context.workspace_path(directory)
    while current != context.workspace_root and not (current/'.git').exists():
        current = current.parent
    relative = current.relative_to(context.workspace_root).as_posix()
    validate_discovery_path(context, relative)
    return relative


def resolve(task, context):
    scope = task.proof_scope
    if scope is None:
        raise ValueError('Versioned proof scope required')
    method = 'dotnet_project_closure_v2'
    selected = {}
    mutable_sdk = False
    try:
        if not scope.project.endswith('.csproj'):
            raise ValueError('Unsupported project ecosystem')
        pending, projects, metadata, settings, repositories = [scope.project], set(), {}, set(), set()
        for argv in task.test_commands:
            explicit = command_input(argv)
            if explicit is None:
                repositories.add(_repository(context, task.working_directory))
            else:
                pending.append(_relative(context, str(Path(task.working_directory)/'_command'), explicit))
        while pending:
            path = pending.pop()
            if path in projects:
                continue
            if len(projects) >= 64:
                raise ValueError('Project closure exceeds budget')
            projects.add(path)
            tree = _xml(context, path, metadata)
            if path.endswith('.slnx'):
                if tree.tag != 'Solution':
                    raise ValueError('Unsupported solution metadata')
                for node in tree.iter():
                    if node.tag == 'Project':
                        reference = node.get('Path', '')
                        if not reference.endswith(('.csproj', '.dcproj')):
                            raise ValueError('Unsupported solution project')
                        pending.append(_relative(context, path, reference))
                continue
            sdk = tree.get('Sdk')
            if sdk not in {None, 'Microsoft.NET.Sdk', 'Microsoft.NET.Sdk.Web', 'Microsoft.NET.Sdk.Worker', 'MSTest.Sdk', 'Microsoft.Docker.Sdk'} and not re.fullmatch(r'Aspire\.AppHost\.Sdk/[0-9]+\.[0-9]+\.[0-9]+', sdk or ''):
                raise ValueError('Unsupported SDK inputs')
            mutable_sdk |= sdk == 'Microsoft.Docker.Sdk' or (sdk or '').startswith('Aspire.AppHost.Sdk/')
            for node in tree.iter():
                tag = node.tag.rsplit('}', 1)[-1]
                if node.get('Condition') and tag != 'RunSettingsFilePath':
                    raise ValueError('Conditional input topology')
                if tag == 'ProjectReference':
                    if node.get('Condition') or node.get('Remove') or node.get('Update'):
                        raise ValueError('Conditional project topology')
                    pending.append(_relative(context, path, node.get('Include')))
                elif tag == 'Import':
                    raise ValueError('Unsupported explicit input topology')
                elif tag in {'Compile','Content','None','EmbeddedResource'}:
                    for attribute in ('Include', 'Update', 'Remove', 'Exclude'):
                        if node.get(attribute) is not None:
                            _local_item(context, path, node.get(attribute))
                elif tag == 'RunSettingsFilePath':
                    settings.add(_runsettings(context, path, node.text))
        directories = sorted({Path(p).parent for p in projects}, key=lambda p: (len(p.parts), str(p)))
        roots = []
        budget = InventoryBudget()
        for repository in sorted(repositories):
            selected.update(snapshot(context, repository, budget=budget))
            roots.append(Path(repository))
        for directory in directories:
            if not any(directory.is_relative_to(root) for root in roots):
                roots.append(directory)
                selected.update(snapshot(context, directory.as_posix(), budget=budget))
        for directory in directories:
            for ancestor in (directory, *directory.parents):
                for name in CONFIG_NAMES:
                    path = (ancestor/name).as_posix()
                    if path in selected:
                        continue
                    try:
                        validate_read_path(context, path)
                    except FileNotFoundError:
                        continue
                    selected.update(snapshot(context, path, budget=budget))
        for path in list(selected):
            if Path(path).suffix.lower() in {'.props', '.targets'}:
                for node in _xml(context, path, metadata).iter():
                    if node.get('Condition') or node.tag.rsplit('}', 1)[-1] in {'Import','ProjectReference','Compile','Content','None'}:
                        raise ValueError('Shared metadata has explicit external inputs')
        for path in [*task.target_files, *scope.generated_inputs]:
            if path not in selected:
                selected.update(snapshot(context, path, budget=budget))
        for path in settings:
            if path not in selected:
                try:
                    validate_read_path(context, path)
                except FileNotFoundError:
                    selected[path] = None
                else:
                    selected.update(snapshot(context, path, budget=budget))
        if not set(projects) <= selected.keys():
            raise ValueError('Incomplete project inventory')
        if any(selected.get(path) != sha for path, sha in metadata.items()):
            raise ValueError('Project metadata changed during discovery')
    except PermissionError:
        raise
    except (OSError, ValueError, ET.ParseError):
        selected, method = snapshot(context, '.'), 'workspace_fallback_v1'
        for path in [*task.target_files, *scope.generated_inputs]:
            if path not in selected:
                try:
                    target = validate_read_path(context, path)
                    selected[path] = hashlib.sha256(target.read_bytes()).hexdigest()
                except FileNotFoundError:
                    selected[path] = None
                # Excluded/generated input is not silently dropped. A protected or
                # unsupported read prevents admission instead of certifying it.
    if len(selected) > 509:  # Three receipt metadata keys share the 512-entry bound.
        from council.diagnostics import DiagnosticRuntimeError
        raise DiagnosticRuntimeError('NATIVE_INVENTORY_LIMIT')
    toolchain = _toolchain(task,context)
    runtime_mutable = (scope.runtime_mutable or mutable_sdk or method=='workspace_fallback_v1' or toolchain is None
        or any(len(argv)>1 and argv[1] in {'test','run','diff'} for argv in task.test_commands))
    return DependencySnapshot(method, dict(sorted(selected.items())), toolchain, runtime_mutable)
