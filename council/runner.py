"""Run literal argument lists with a workspace-bound working directory."""
import subprocess
import sys
from council.runtime_context import RuntimeContext, validate_workspace
from council.command_policy import has_policy_override
from council.diagnostics import DiagnosticRuntimeError


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

    def run(self, command, cwd=None, timeout=600):
        work_dir = self.resolve_cwd(cwd)
        if not isinstance(command, (list, tuple)) or not command or not all(isinstance(x,str) for x in command):
            raise ValueError('Commands must be nonempty literal argument lists; shell text is unsupported')
        if has_policy_override(command):
            raise DiagnosticRuntimeError('VERIFICATION_POLICY_OVERRIDE')
        try:
            child = subprocess.Popen(command, cwd=work_dir, shell=False, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            try:
                out, err = child.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                from council.cli_process import _kill,cleanup_evidence
                _kill(child)
                out, err = child.communicate()
                cleanup_evidence(child)
                return 124, out, err + '\nCommand timed out'
            return child.returncode, out, err
        except OSError as error:
            return 127, '', str(error)

    def run_echo(self, message):
        return self.run([sys.executable,'-c','import sys;print(sys.argv[1])',message])
