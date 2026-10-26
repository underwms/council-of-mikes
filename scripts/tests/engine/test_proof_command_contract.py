"""Accepted command forms capture real inputs before native worker dispatch."""
import pytest
from test_proof_dependencies import layout
from test_engine_integration import lifecycle
from test_plan_validation import validate


def test_empty_run_separator_preserves_closed_project_inputs(graph_workspace):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    task.test_commands = [['dotnet', 'run', '--project', 'tests.csproj', '--no-build', '--']]
    value = resolve(task, graph_workspace.context)
    assert value.method == 'dotnet_project_closure_v2'
    assert 'shared/code.cs' in value.hashes and 'unrelated/code.cs' not in value.hashes
    assert value.runtime_mutable


def test_solution_build_and_git_check_capture_solution_and_repository(graph_workspace):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    root = graph_workspace.workspace
    (root/'.git').mkdir()
    (root/'sample.slnx').write_text('<Solution><Folder Name="src"><Project Path="app/app.csproj" />'
        '<Project Path="host/host.csproj" /></Folder><Project Path="docker.dcproj" /></Solution>')
    (root/'host').mkdir()
    (root/'host/host.csproj').write_text('<Project Sdk="Aspire.AppHost.Sdk/13.0.0" />')
    (root/'docker.dcproj').write_text('<Project Sdk="Microsoft.Docker.Sdk"><ItemGroup>'
        '<None Include="compose.yml" /></ItemGroup></Project>')
    (root/'compose.yml').write_text('services: {}')
    task.working_directory = '.'
    task.test_commands = [['dotnet', 'build', 'sample.slnx'], ['git', 'diff', '--check']]
    value = resolve(task, graph_workspace.context)
    assert value.method == 'dotnet_project_closure_v2'
    assert {'sample.slnx', 'host/host.csproj', 'docker.dcproj', 'compose.yml', 'unrelated/code.cs'} <= value.hashes.keys()
    before = value.hashes
    (root/'unrelated/code.cs').write_text('changed unstaged input')
    assert resolve(task, graph_workspace.context).hashes != before
    assert value.runtime_mutable


def test_git_check_in_nested_directory_observes_repo_and_cross_repo_project(graph_workspace):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    root = graph_workspace.workspace
    (root/'tests/.git').mkdir()
    (root/'tests/nested').mkdir()
    task.working_directory = 'tests/nested'
    task.test_commands = [['dotnet', 'build', '../tests.csproj'], ['git', 'diff', '--check']]
    value = resolve(task, graph_workspace.context)
    assert value.method == 'dotnet_project_closure_v2'
    assert 'shared/code.cs' in value.hashes and 'tests/code.cs' in value.hashes
    assert 'unrelated/code.cs' not in value.hashes
    assert value.runtime_mutable


def test_solution_hosting_sdks_cannot_certify_external_runtime_freshness(graph_workspace, monkeypatch):
    from council import proof_dependencies
    task = layout(graph_workspace)
    root = graph_workspace.workspace
    (root/'host.csproj').write_text('<Project Sdk="Aspire.AppHost.Sdk/13.0.0" />')
    (root/'sample.slnx').write_text('<Solution><Project Path="host.csproj" /></Solution>')
    task.test_commands = [['dotnet', 'build', '../sample.slnx']]
    monkeypatch.setattr(proof_dependencies, '_toolchain', lambda *args: 'known-toolchain')
    value = proof_dependencies.resolve(task, graph_workspace.context)
    assert value.method == 'dotnet_project_closure_v2'
    assert value.runtime_mutable, 'Hosting/container inputs may change without repository changes'


@pytest.mark.parametrize('solution', [
    '<Other />', '<Solution><Project Path="unknown.proj" /></Solution>',
    '<Solution><Project Path="$(External)/app.csproj" /></Solution>',
])
def test_unresolved_solution_relationship_keeps_conservative_fallback(graph_workspace, solution):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    (graph_workspace.workspace/'sample.slnx').write_text(solution)
    task.test_commands = [['dotnet', 'build', '../sample.slnx']]
    value = resolve(task, graph_workspace.context)
    assert value.method == 'workspace_fallback_v1'
    assert 'unrelated/code.cs' in value.hashes and value.runtime_mutable


@pytest.mark.parametrize('arguments', [
    ['dotnet', 'run', '--project', 'test.csproj', '--', 'external.json'],
    ['dotnet', 'build', 'test.csproj', '-p:External=elsewhere'],
    ['dotnet', 'build', '$(External)/test.csproj'],
    ['git', 'diff', '--check', '--', 'only.cs'],
])
def test_unsupported_proof_argv_is_located_plan_feedback(lifecycle, arguments):
    from council.delivery_contracts import ProofScope
    task = lifecycle.plan.tasks[0]
    task.proof_scope = ProofScope(version=1, project='test.csproj', runtime_mutable=True)
    task.test_commands = [arguments]
    with pytest.raises(ValueError) as caught:
        validate(lifecycle)
    assert caught.value.code == 'PLAN_VERIFICATION_INVALID'
    assert caught.value.task_index == 1
    assert caught.value.verification['reason'] == 'PROOF_COMMAND_UNSUPPORTED'
    assert caught.value.verification['command_index'] == 1


def test_supported_proof_commands_pass_admission(lifecycle):
    from council.delivery_contracts import ProofScope
    task = lifecycle.plan.tasks[0]
    task.proof_scope = ProofScope(version=1, project='test.csproj', runtime_mutable=True)
    task.test_commands = [['dotnet', 'build', 'test.csproj'],
        ['dotnet', 'run', '--project', 'test.csproj', '--'], ['git', 'diff', '--check']]
    assert validate(lifecycle).tasks[0].test_commands == task.test_commands
