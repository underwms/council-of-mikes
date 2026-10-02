"""OS-aware subprocess execution runner for Windows 11 and macOS."""
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Optional, List

class SubprocessRunner:
    """Executes atomic shell commands across Windows (PowerShell) and macOS (zsh)."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()
        self.is_windows = platform.system() == "Windows"

    def _resolve_shell(self) -> List[str]:
        if self.is_windows:
            # Prefer pwsh if installed on Windows, fallback to powershell.exe
            pwsh_path = shutil.which("pwsh")
            shell_bin = pwsh_path if pwsh_path else "powershell.exe"
            return [shell_bin, "-NoProfile", "-Command"]
        else:
            # macOS / POSIX: prefer zsh, fallback to bash
            zsh_path = shutil.which("zsh")
            shell_bin = zsh_path if zsh_path else "/bin/zsh"
            return [shell_bin, "-c"]

    def run(self, command: str, cwd: Optional[Path] = None, timeout: int = 120) -> Tuple[int, str, str]:
        work_dir = (cwd or self.workspace_root).resolve()
        shell_prefix = self._resolve_shell()
        full_cmd = shell_prefix + [command]

        try:
            proc = subprocess.run(
                full_cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {timeout} seconds: {command}"
        except Exception as e:
            return 1, "", str(e)

    def run_echo(self, message: str) -> Tuple[int, str, str]:
        if self.is_windows:
            return self.run(f"Write-Output '{message}'")
        else:
            return self.run(f"echo '{message}'")
