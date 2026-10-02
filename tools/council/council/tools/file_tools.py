"""Python-native safe, sandboxed UTF-8 file operations."""
from pathlib import Path
from typing import Optional

class FileTools:
    """Provides sandboxed file reading, writing, and surgical patching."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()
        self._recent_calls = []

    def _track_call(self, op: str, key: str) -> None:
        """Detects repetitive tool invocations and trips circuit breaker."""
        call = (op, key)
        self._recent_calls.append(call)
        if len(self._recent_calls) > 6:
            self._recent_calls.pop(0)
        if len(self._recent_calls) >= 3 and self._recent_calls[-1] == self._recent_calls[-2] == self._recent_calls[-3]:
            raise RuntimeError(
                f"Loop detected: Repetitive operation '{op}' with identical parameters attempted 3 times consecutively."
            )

    def _resolve_safe(self, rel_path: str) -> Path:
        target = (self.workspace_root / rel_path).resolve()
        try:
            target.relative_to(self.workspace_root)
        except ValueError:
            raise PermissionError(f"Access denied: Path escapes workspace root: {rel_path}")
        return target

    def read_file(self, rel_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        self._track_call("read_file", f"{rel_path}:{start_line}:{end_line}")
        target = self._resolve_safe(rel_path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {rel_path}")
        
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = (start_line - 1) if start_line and start_line > 0 else 0
        end = end_line if end_line else len(lines)
        return "\n".join(lines[start:end])

    def write_file(self, rel_path: str, content: str) -> None:
        self._track_call("write_file", f"{rel_path}:{len(content)}")
        target = self._resolve_safe(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def patch_file(self, rel_path: str, old_string: str, new_string: str) -> bool:
        self._track_call("patch_file", f"{rel_path}:{old_string}")
        target = self._resolve_safe(rel_path)
        if not target.exists():
            return False
        
        content = target.read_text(encoding="utf-8")
        occurrences = content.count(old_string)
        if occurrences != 1:
            return False
        
        updated = content.replace(old_string, new_string, 1)
        target.write_text(updated, encoding="utf-8")
        return True
