"""Narrow guards for explicit direct PowerShell verification policy overrides."""
from pathlib import PureWindowsPath


def has_policy_override(command):
    if not isinstance(command, (list, tuple)) or not command or not isinstance(command[0], str):
        return False
    executable = PureWindowsPath(command[0]).name.casefold()
    if executable not in {'powershell', 'powershell.exe', 'pwsh', 'pwsh.exe'}:
        return False
    for argument in command[1:]:
        if not isinstance(argument, str) or not argument.startswith(('-', '/')):
            continue
        flag = argument.lstrip('-/').split(':', 1)[0].split('=', 1)[0].casefold()
        # After -File, remaining arguments belong to the script, not startup.
        if flag and 'file'.startswith(flag):
            return False
        if flag and (flag == 'ep' or 'executionpolicy'.startswith(flag)):
            return True
    return False


def validate_command_policy(commands, task_index):
    from council.verification_feedback import rejection
    for command_index, command in enumerate(commands, 1):
        if has_policy_override(command):
            raise rejection(task_index, 'EXECUTION_POLICY_OVERRIDE', command_index=command_index)
