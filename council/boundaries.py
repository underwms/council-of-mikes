"""Typed explicit path guards; native OS denials must remain distinguishable."""

REASONS = {
    'PATH_ABSOLUTE': 'Workspace paths must be relative',
    'PATH_PARENT_TRAVERSAL': 'Parent traversal is not permitted',
    'PATH_OUTSIDE_WORKSPACE': 'Path escapes selected workspace',
    'PATH_EXCLUDED': 'Private or generated discovery path is excluded',
    'PATH_LINKED': 'Discovery does not follow links or junctions',
}
READ_TOOLS = frozenset({'read_workspace_file', 'list_workspace_files', 'search_workspace_text'})


class WorkspaceBoundaryError(PermissionError):
    def __init__(self, reason):
        if type(reason) is not str or reason not in REASONS:
            raise ValueError('Unknown workspace boundary reason')
        self.reason = reason
        super().__init__(REASONS[reason])


def read_feedback(error):
    if type(error) is not WorkspaceBoundaryError or type(error.reason) is not str or error.reason not in REASONS:
        return None
    return {'available': False, 'rejected': True, 'reason': error.reason,
        'message': REASONS[error.reason],
        'guidance': 'This source is unavailable. Do not retry the unchanged request or cross the boundary. '
            'Use allowed workspace-relative sources, or identify the missing evidence explicitly. '
            'A denied read is not an observation of the target contents.'}
