"""Bounded, explicit instruction assembly; private session history is never loaded."""
import json
import re
from pathlib import Path

MAX_GUIDANCE_FILE_BYTES = 65_536
MAX_GUIDANCE_BYTES = 196_608
_PRIVATE = {'memory', 'work', 'runtime', '.git', '.aws', '.agents', '.ssh', '.codex', '.gemini', '.claude'}


def _safe(root, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or any(p.lower() in _PRIVATE for p in path.parts):
        raise PermissionError('Guidance must reference public Council source')
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise PermissionError('Guidance escapes its source root')
    if any(p.lower() in _PRIVATE for p in resolved.relative_to(root).parts):
        raise PermissionError('Private guidance sources are forbidden')
    return resolved


def _read(path):
    if not path.is_file():
        return None
    with path.open('rb') as source:
        data = source.read(MAX_GUIDANCE_FILE_BYTES + 1)
    if len(data) > MAX_GUIDANCE_FILE_BYTES:
        raise ValueError('Guidance file exceeds byte limit')
    return data.decode('utf-8-sig')


def load_guidance(context, specialist=None, project_names=None, *, seen_sources=None) -> str:
    """Load canonical shared/profile guidance and explicitly targeted project instructions.

    Missing optional documents are permitted. Oversized or escaped instructions fail
    explicitly, so important instructions cannot silently disappear from a prompt.
    Project names may be workspace-relative target files or working directories.
    A request-local seen_sources set suppresses repeated resolved source paths in
    output only; all source reads and per-package limits are still checked.
    """
    root = context.council_root
    manifest = json.loads(_read(_safe(root, 'manifest.json')) or '{}')
    paths = manifest.get('paths', {})
    sources = [_safe(root, paths.get(key, default)) for key, default in (
        ('shared', 'instructions/shared.md'), ('host_rules', 'rules/global.md'),
        ('workspace_rules', 'rules/workspace.md'))]
    selected = manifest.get('default_profile')
    profile_ref = manifest.get('profiles', {}).get(selected)
    if profile_ref:
        profile_path = _safe(root, profile_ref)
        profile = json.loads(_read(profile_path) or '{}')
        for key in ('rules', 'corporate_rules'):
            if profile.get(key):
                sources.append(_safe(root, profile_path.parent.relative_to(root) / profile[key]))
    if specialist:
        if not re.fullmatch(r'[a-z][a-z0-9-]*', specialist):
            raise ValueError('Invalid specialist name')
        sources.append(_safe(root, f'skills/{specialist}/SKILL.md'))
    workspace = context.workspace_root
    sources.append(_safe(workspace, 'AGENTS.md'))
    if isinstance(project_names, str):
        project_names = [project_names]
    for name in project_names or []:
        target = context.workspace_path(name)
        relative = target.relative_to(workspace)
        if not relative.parts:
            continue
        project = relative.parts[0]
        if project.lower() in _PRIVATE:
            raise PermissionError('Private project guidance is forbidden')
        sources.append(_safe(root, f'project-instructions/{project}.md'))
        parent = target if target.is_dir() else target.parent
        for directory in [*reversed(parent.relative_to(workspace).parents), parent.relative_to(workspace)]:
            sources.append(_safe(workspace, directory / 'AGENTS.md'))
    sections = []
    total = 0
    for source in dict.fromkeys(sources):
        content = _read(source)
        if content is None:
            continue
        label = source.relative_to(root) if source.is_relative_to(root) else source.relative_to(workspace)
        section = f'\n--- Guidance: {label.as_posix()} ---\n{content}\n'
        total += len(section.encode('utf-8'))
        if total > MAX_GUIDANCE_BYTES:
            raise ValueError('Combined guidance exceeds byte limit')
        if seen_sources is None or source not in seen_sources:
            sections.append(section)
        if seen_sources is not None:
            seen_sources.add(source)
    return ''.join(sections)
