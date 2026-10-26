"""Finite tool failure facts; never retain exception messages or request paths."""

TOOLS = frozenset({'read_workspace_file', 'list_workspace_files', 'search_workspace_text',
    'write_workspace_file', 'patch_workspace_file', 'run_dotnet_test', 'run_deno_test',
    'run_workspace_validator', 'unknown'})
REASONS = frozenset({'SOURCE_MISSING', 'PERMISSION_DENIED', 'NOT_A_DIRECTORY',
    'IS_A_DIRECTORY', 'INVALID_PATH', 'IO_ERROR', 'TOOL_ERROR'})


def safe_detail(value):
    if (type(value) is not dict or set(value) != {'tool', 'tool_index', 'reason'}
            or type(value['tool']) is not str or value['tool'] not in TOOLS
            or type(value['reason']) is not str or value['reason'] not in REASONS
            or type(value['tool_index']) is not int or not 1 <= value['tool_index'] <= 16):
        return None
    return dict(value)


def detail(error, name, index):
    reason = 'TOOL_ERROR'
    if isinstance(error, FileNotFoundError):
        reason = 'SOURCE_MISSING'
    elif isinstance(error, PermissionError):
        reason = 'PERMISSION_DENIED'
    elif isinstance(error, NotADirectoryError):
        reason = 'NOT_A_DIRECTORY'
    elif isinstance(error, IsADirectoryError):
        reason = 'IS_A_DIRECTORY'
    elif isinstance(error, OSError):
        reason = 'INVALID_PATH' if getattr(error, 'winerror', None) == 123 else 'IO_ERROR'
    return {'tool': name if type(name) is str and name in TOOLS else 'unknown',
            'tool_index': index, 'reason': reason}


def missing_feedback():
    return {'available': False, 'rejected': True, 'reason': 'SOURCE_MISSING',
        'message': 'The requested source is unavailable because it does not exist.',
        'guidance': 'Do not repeat the unchanged request or invent source contents. '
            'Inspect available workspace sources or identify the missing evidence explicitly.'}
