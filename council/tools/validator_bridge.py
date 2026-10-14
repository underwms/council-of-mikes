"""Execute available workspace validators without importing task code into the engine."""
import shutil
import sys
from pathlib import Path
from council.runner import SubprocessRunner
from council.runtime_context import resolve_context


def run_workspace_audit(workspace_root=None, *, context=None):
    if context is None and workspace_root is None:
        context = resolve_context()
    runner = SubprocessRunner(workspace_root, context=context)
    root = runner.workspace_root
    ps = root/'scripts'/'validate-workspace.ps1'
    py = root/'scripts'/'validate_workspace.py'
    if ps.is_file():
        validator = ps.resolve()
        shell = shutil.which('pwsh') or shutil.which('powershell.exe')
        if not shell:
            return False, {'error':'PowerShell is required for the workspace validator'}
        command = [shell,'-NoProfile','-File',str(validator),'-WorkspaceRoot',str(root)]
        if context:
            command += ['-GlobalGeminiRoot',str(context.council_root)]
    elif py.is_file():
        validator = py.resolve()
        command = [sys.executable,str(validator),str(root)]
    else:
        return False, {'error':'Workspace validator missing: scripts/validate-workspace.ps1 or scripts/validate_workspace.py'}
    if not validator.is_relative_to(root):
        return False, {'error':'Workspace validator resolves outside the selected workspace'}
    code,out,err = runner.run(command)
    return code == 0, {'exit_code':code, 'output':(out+'\n'+err)[-4000:]}
