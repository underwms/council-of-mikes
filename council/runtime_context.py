"""Explicit installation and workspace boundaries shared by the engine."""
import json
import os
from dataclasses import dataclass
from pathlib import Path


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def validate_workspace(path, council_root=None):
    root = Path(path).expanduser().resolve()
    council = Path(council_root or os.environ.get('COUNCIL_ROOT') or Path.home()/'.council').expanduser().resolve()
    profile = council.parent if council.name == '.council' else Path.home().resolve()
    if not root.is_dir():
        raise ValueError('Selected workspace must be an existing directory')
    if _within(council, root) or _within(root, council) or _within(profile, root):
        raise ValueError('Workspace cannot contain the private profile or overlap Council source')
    for name in ('.codex', '.gemini', '.claude', '.agents', '.aws'):
        private = (profile/name).resolve()
        if _within(root, private) or _within(private, root):
            raise ValueError('Workspace cannot overlap private client-profile directories')
    return root


@dataclass(frozen=True)
class RuntimeContext:
    council_root: Path
    workspace_root: Path
    memory_root: Path

    def __post_init__(self):
        council = Path(self.council_root).expanduser().resolve()
        workspace = validate_workspace(self.workspace_root, council)
        memory = Path(self.memory_root).expanduser().resolve()
        if not council.is_dir() or not (council/'manifest.json').is_file():
            raise ValueError('Council root must contain manifest.json')
        memory_boundary = (council/'memory').resolve()
        if not _within(memory_boundary, council) or not _within(memory, memory_boundary):
            raise ValueError('Private engine memory must stay below Council memory')
        object.__setattr__(self, 'council_root', council)
        object.__setattr__(self, 'workspace_root', workspace)
        object.__setattr__(self, 'memory_root', memory)

    def workspace_path(self, path='.', *, allow_absolute=False):
        candidate = Path(path)
        if candidate.is_absolute() and not allow_absolute:
            raise PermissionError('Workspace paths must be relative')
        if '..' in candidate.parts:
            raise PermissionError('Parent traversal is not permitted')
        resolved = (self.workspace_root/candidate).resolve()
        if not _within(resolved, self.workspace_root) or _within(resolved, self.council_root):
            raise PermissionError('Path escapes selected workspace')
        return resolved


def resolve_context(workspace_root=None, council_root=None):
    council = Path(council_root or os.environ.get('COUNCIL_ROOT') or Path.home()/'.council').expanduser().resolve()
    selected = workspace_root or os.environ.get('COUNCIL_WORKSPACE_ROOT')
    if not selected:
        metadata = council/'installation.json'
        if metadata.is_file():
            selected = json.loads(metadata.read_text(encoding='utf-8-sig')).get('workspaceRoot')
    if not selected:
        raise ValueError('Select a workspace with --workspace, COUNCIL_WORKSPACE_ROOT, or installation.json')
    memory = os.environ.get('COUNCIL_MEMORY_ROOT') or council/'memory'/'engine'
    return RuntimeContext(council, Path(selected), Path(memory))


def resolve_workspace_root(workspace_root=None, council_root=None):
    return resolve_context(workspace_root, council_root).workspace_root
