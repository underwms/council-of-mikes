"""Read-only, bounded repository discovery without following junctions or symlinks."""
import os
import stat
import json
from pathlib import Path

from langchain_core.tools import tool
from council.boundaries import WorkspaceBoundaryError

_EXCLUDED = {'.git', '.hg', '.svn', '.council', '.aws', '.agents', '.codex',
             '.gemini', '.claude', '.ssh', 'node_modules', 'bin', 'obj', '.venv',
             'venv', '__pycache__', 'dist', 'build', 'coverage', '.next', '.cache',
             'memory', '.vs', '.idea', '.vscode', '.vscode-shared', '.deno',
             '.pytest_cache', '.artifacts', '.react-router', 'debug', 'release', 'testresults'}
MAX_FILE_BYTES = 262_144
MAX_SEARCH_BYTES = 8_388_608
MAX_VISITED_ENTRIES = 20_000


def _excluded(path):
    return any(part.lower() in _EXCLUDED for part in path.parts) or path.name.lower().startswith('.env') or path.suffix.lower() in {'.pem', '.key', '.pfx', '.p12', '.sqlite', '.db', '.pyc', '.log', '.har', '.tmp'} or path.name.lower() in {'thumbs.db', 'desktop.ini'}


def _linked(path):
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def _metadata_file(path):
    if _linked(path):
        return False
    try:
        return stat.S_ISREG(path.stat().st_mode)
    except FileNotFoundError:
        return False


def _deno_vendor(path, workspace_root):
    """Recognize Deno's generated dependency tree, not arbitrary vendor sources."""
    if not any(part.lower() == 'vendor' for part in path.relative_to(workspace_root).parts):
        return False
    for directory in (path, *path.parents):
        if directory == workspace_root:
            break
        if directory.name.lower() != 'vendor':
            continue
        if not any(_metadata_file(directory.parent/name) for name in ('deno.json', 'deno.jsonc')):
            continue
        manifest = directory/'manifest.json'
        if not _metadata_file(manifest):
            continue
        with manifest.open('rb') as source:
            data = source.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            continue
        try:
            value = json.loads(data)
        except (ValueError, UnicodeError):
            continue
        if isinstance(value, dict) and isinstance(value.get('modules'), dict):
            return True
    return False


def _start(context, relative):
    candidate = Path(relative)
    if _excluded(candidate):
        raise WorkspaceBoundaryError('PATH_EXCLUDED')
    target = context.workspace_path(relative)
    current = context.workspace_root
    for part in candidate.parts:
        current = current / part
        if _linked(current):
            raise WorkspaceBoundaryError('PATH_LINKED')
    if _deno_vendor(target, context.workspace_root):
        raise WorkspaceBoundaryError('PATH_EXCLUDED')
    return target


def validate_discovery_path(context, rel_path):
    """Validate a workspace path against private/generated exclusions and links."""
    return _start(context, rel_path)


def validate_read_path(context, rel_path):
    """Validate a direct source read using the discovery exclusions and link boundary."""
    target = _start(context, rel_path)
    # is_file() suppresses native stat errors on current Python. Preserve real
    # missing/permission failures and distinguish directories from absent files.
    mode = target.stat().st_mode
    if stat.S_ISDIR(mode):
        raise IsADirectoryError('Discovery read requires a workspace file')
    if not stat.S_ISREG(mode):
        raise OSError('Discovery read requires a regular workspace file')
    return target


def _walk(context, start, *, visited_entries=None):
    """Yield safe files; a None sentinel marks the traversal budget being reached."""
    # Validate the explicit starting source. A missing directory is unavailable
    # evidence, not a successfully observed empty listing/search.
    start.stat()
    pending = [start]
    visited = visited_entries if visited_entries is not None else [0]
    while pending:
        path = pending.pop()
        relative = path.relative_to(context.workspace_root)
        if _excluded(relative) or _linked(path):
            continue
        if not path.resolve().is_relative_to(context.workspace_root):
            continue
        if _deno_vendor(path, context.workspace_root):
            continue
        visited[0] += 1
        if visited[0] > MAX_VISITED_ENTRIES:
            yield None
            return
        if path.is_dir():
            # scandir iteration is bounded even for exceptionally large directories.
            children = []
            with os.scandir(path) as entries:
                for entry in entries:
                    visited[0] += 1
                    if visited[0] > MAX_VISITED_ENTRIES:
                        yield None
                        return
                    children.append(Path(entry.path))
            pending.extend(sorted(children, reverse=True))
        elif path.is_file():
            yield path


def _limit(value, maximum):
    if not 1 <= value <= maximum:
        raise ValueError(f'limit must be between 1 and {maximum}')


def get_discovery_tools(context):
    """Return bounded listing and literal text search tools for the selected workspace."""
    @tool
    def list_workspace_files(rel_path: str = '.', limit: int = 200) -> dict:
        """List source file paths, excluding private/generated files and links (limit 1-200)."""
        _limit(limit, 200)
        files = []
        for path in _walk(context, _start(context, rel_path)):
            if path is None or len(files) == limit:
                return {'files': files, 'truncated': True}
            files.append(path.relative_to(context.workspace_root).as_posix())
        return {'files': files, 'truncated': False}

    @tool
    def search_workspace_text(pattern: str, rel_path: str = '.', limit: int = 100) -> dict:
        """Search literal text in bounded UTF-8 source files (limit 1-100); return line references."""
        _limit(limit, 100)
        if not pattern or len(pattern) > 512:
            raise ValueError('Search pattern must contain 1-512 characters')
        matches = []
        scanned = 0
        skipped = 0
        for path in _walk(context, _start(context, rel_path)):
            if path is None or scanned >= MAX_SEARCH_BYTES:
                return {'matches': matches, 'truncated': True, 'skipped_files': skipped}
            with path.open('rb') as source:
                data = source.read(MAX_FILE_BYTES + 1)
            scanned += len(data)
            if len(data) > MAX_FILE_BYTES or b'\x00' in data:
                skipped += 1
                continue
            try:
                content = data.decode('utf-8-sig')
            except UnicodeDecodeError:
                skipped += 1
                continue
            for number, line in enumerate(content.splitlines(), 1):
                if pattern in line:
                    if len(matches) == limit:
                        return {'matches': matches, 'truncated': True, 'skipped_files': skipped}
                    matches.append({'path': path.relative_to(context.workspace_root).as_posix(),
                                    'line': number, 'text': line[:500]})
        return {'matches': matches, 'truncated': False, 'skipped_files': skipped}

    return [list_workspace_files, search_workspace_text]
