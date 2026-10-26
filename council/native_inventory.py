"""Bounded source fingerprints for native shell changes, never source contents."""
import hashlib
from dataclasses import dataclass, field

from council.diagnostics import DiagnosticRuntimeError
from council.tools.discovery import _walk, validate_discovery_path, validate_read_path

MAX_SOURCE_BYTES = 64 * 1024 * 1024


@dataclass
class InventoryBudget:
    remaining_bytes: int = field(default_factory=lambda: MAX_SOURCE_BYTES)
    visited_entries: list[int] = field(default_factory=lambda: [0])


def snapshot(context, relative, *, budget=None):
    """Hash safe task-directory sources; incomplete inventories are terminal."""
    files = {}
    budget = budget if budget is not None else InventoryBudget()
    try:
        start = validate_discovery_path(context, relative)
        for path in _walk(context, start, visited_entries=budget.visited_entries):
            if path is None:
                raise DiagnosticRuntimeError('NATIVE_INVENTORY_LIMIT')
            key = path.relative_to(context.workspace_root).as_posix()
            target = validate_read_path(context, key)
            digest = hashlib.sha256()
            with target.open('rb') as source:
                for block in iter(lambda: source.read(min(65_536, budget.remaining_bytes + 1)), b''):
                    budget.remaining_bytes -= len(block)
                    if budget.remaining_bytes < 0:
                        raise DiagnosticRuntimeError('NATIVE_INVENTORY_LIMIT')
                    digest.update(block)
            files[key] = digest.hexdigest()
    except OSError:
        raise DiagnosticRuntimeError('NATIVE_INVENTORY_FAILED') from None
    return files
