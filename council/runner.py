"""Run literal argument lists with a workspace-bound working directory."""
import subprocess
import sys
from council.runtime_context import RuntimeContext, validate_workspace


class SubprocessRunner:
    def __init__(self, workspace_root=None, *, context=None):
        self.context = context or (workspace_root if isinstance(workspace_root, RuntimeContext) else None)
        self.workspace_root = self.context.workspace_root if self.context else validate_workspace(workspace_root)

    def resolve_cwd(self, cwd=None):
        from pathlib import Path
        candidate = Path(cwd) if cwd is not None else self.workspace_root
        resolved = (self.workspace_root/candidate).resolve()
        if not resolved.is_relative_to(self.workspace_root) or not resolved.is_dir():
            raise PermissionError('Subprocess working directory must remain within the selected workspace')
        return resolved

    def run(self, command, cwd=None, timeout=120):
        work_dir = self.resolve_cwd(cwd)
        if not isinstance(command, (list, tuple)) or not command or not all(isinstance(x,str) for x in command):
            raise ValueError('Commands must be nonempty literal argument lists; shell text is unsupported')
        try:
            result = subprocess.run(command, cwd=work_dir, shell=False, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, '', 'Command timed out'
        except OSError as error:
            return 127, '', str(error)

    def run_echo(self, message):
        return self.run([sys.executable,'-c','import sys;print(sys.argv[1])',message])
