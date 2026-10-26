"""Mechanical file-target admission and ordinary MSTest run proof scope."""
import pytest

from test_engine_integration import lifecycle
from test_plan_validation import validate
from test_proof_dependencies import layout


@pytest.mark.parametrize('native', [True, False])
def test_existing_directory_target_is_planner_feedback_before_dispatch(lifecycle, native):
    (lifecycle.workspace/'migrations').mkdir()
    lifecycle.plan.tasks[0].target_files = ['migrations']
    with pytest.raises(ValueError) as caught:
        validate(lifecycle, native=native)
    assert caught.value.code == 'PLAN_TARGET_PATH_INVALID'
    assert caught.value.task_index == 1 and caught.value.field_index == 1


def test_existing_and_not_yet_generated_file_targets_remain_valid(lifecycle):
    (lifecycle.workspace/'existing.cs').write_text('existing')
    lifecycle.plan.tasks[0].target_files = ['existing.cs', 'new-migration.cs']
    assert validate(lifecycle).tasks[0].target_files == ['existing.cs', 'new-migration.cs']


def test_actual_target_stat_denial_is_not_reclassified_as_plan_feedback(lifecycle, monkeypatch):
    from pathlib import Path
    original = Path.stat
    target = lifecycle.workspace/'denied.cs'
    lifecycle.plan.tasks[0].target_files = ['denied.cs']

    def denied(path, *args, **kwargs):
        if path == target:
            raise PermissionError('native denial')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'stat', denied)
    with pytest.raises(PermissionError):
        validate(lifecycle)


def test_explicit_dotnet_run_uses_project_closure_despite_unrelated_growth(graph_workspace, monkeypatch):
    from council import proof_dependencies
    from council.tools import discovery
    task = layout(graph_workspace)
    task.test_commands = [['dotnet', 'run', '--project', 'tests.csproj']]
    task.proof_scope.runtime_mutable = False
    for index in range(80):
        (graph_workspace.workspace/'unrelated'/f'{index}.cs').write_text('unrelated')
    monkeypatch.setattr(discovery, 'MAX_VISITED_ENTRIES', 50)
    monkeypatch.setattr(proof_dependencies, '_toolchain', lambda *args: 'known-toolchain')

    result = proof_dependencies.resolve(task, graph_workspace.context)

    assert result.method == 'dotnet_project_closure_v2'
    assert result.runtime_mutable, 'Run programs may consume mutable fixture/runtime state'
    assert 'shared/code.cs' in result.hashes and 'unrelated/code.cs' not in result.hashes


@pytest.mark.parametrize('arguments', [
    ['run', 'tests.csproj'], ['run', '--project'],
    ['run', '--project', 'tests.csproj', '--', 'external-settings.json'],
])
def test_unknown_run_inputs_cannot_borrow_narrow_scope(graph_workspace, arguments):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    task.test_commands = [['dotnet', *arguments]]
    result = resolve(task, graph_workspace.context)
    assert result.method == 'workspace_fallback_v1'
    assert result.runtime_mutable
