"""MSTest implementation receipts stay bounded without dropping consumed inputs."""
import pytest

from council.proof_dependencies import resolve
from council.state import TaskItem


def mstest_layout(fixture):
    root = fixture.workspace
    for directory in ('repo/tests', 'repo/data/SeedData', 'unrelated'):
        (root/directory).mkdir(parents=True)
    (root/'repo/tests/tests.csproj').write_text('''<Project Sdk="MSTest.Sdk">
      <PropertyGroup><RunSettingsFilePath Condition="Exists('settings')">$(MSBuildThisFileDirectory)../tests.runsettings</RunSettingsFilePath></PropertyGroup>
      <ItemGroup><ProjectReference Include="../data/data.csproj" /></ItemGroup>
    </Project>''')
    (root/'repo/data/data.csproj').write_text('''<Project Sdk="Microsoft.NET.Sdk">
      <ItemGroup><Content Include="SeedData\\**\\*.json" /></ItemGroup>
    </Project>''')
    (root/'repo/data/code.cs').write_text('data')
    (root/'repo/data/SeedData/seed.json').write_text('{}')
    (root/'repo/global.json').write_text('{"msbuild-sdks":{"MSTest.Sdk":"4.0.1"}}')
    (root/'unrelated/code.cs').write_text('unrelated')
    return TaskItem(id='schema', specialist='the-curator', description='Verify changed schema',
        working_directory='repo', target_files=['repo/data/code.cs'],
        test_commands=[['dotnet', 'test', '--project', 'tests/tests.csproj']],
        proof_scope={'version': 1, 'project': 'repo/tests/tests.csproj', 'runtime_mutable': True})


def test_mstest_closure_survives_unrelated_workspace_growth(graph_workspace, monkeypatch):
    from council.tools import discovery
    task = mstest_layout(graph_workspace)
    for index in range(80):
        (graph_workspace.workspace/'unrelated'/f'{index}.cs').write_text('unrelated')
    monkeypatch.setattr(discovery, 'MAX_VISITED_ENTRIES', 65)

    result = resolve(task, graph_workspace.context)

    assert result.method == 'dotnet_project_closure_v2'
    assert result.runtime_mutable
    assert {'repo/data/code.cs', 'repo/data/SeedData/seed.json', 'repo/global.json'} <= result.hashes.keys()
    assert result.hashes['repo/tests.runsettings'] is None
    assert not any(path.startswith('unrelated/') for path in result.hashes)


@pytest.mark.parametrize('path', ['repo/tests.runsettings', 'repo/data/SeedData/seed.json',
    'repo/global.json', 'repo/data/new.cs'])
def test_mstest_consumed_edits_invalidate_identity(graph_workspace, path):
    task = mstest_layout(graph_workspace)
    first = resolve(task, graph_workspace.context)
    assert first.method == 'dotnet_project_closure_v2'
    (graph_workspace.workspace/path).write_text('changed')
    assert resolve(task, graph_workspace.context).hashes != first.hashes


def test_optional_settings_add_edit_remove_are_observed(graph_workspace):
    task = mstest_layout(graph_workspace)
    missing = resolve(task, graph_workspace.context)
    path = graph_workspace.workspace/'repo/tests.runsettings'
    path.write_text('<RunSettings />')
    existing = resolve(task, graph_workspace.context)
    assert existing.method == 'dotnet_project_closure_v2'
    assert existing.hashes['repo/tests.runsettings'] is not None
    path.write_text('<RunSettings><Flag /></RunSettings>')
    assert resolve(task, graph_workspace.context).hashes != existing.hashes
    path.unlink()
    assert resolve(task, graph_workspace.context).hashes == missing.hashes


@pytest.mark.parametrize('selector', ['Content', 'Compile', 'None', 'EmbeddedResource'])
@pytest.mark.parametrize('attribute', ['Include', 'Update', 'Remove'])
def test_local_item_selectors_keep_narrow_scope(graph_workspace, selector, attribute):
    task = mstest_layout(graph_workspace)
    (graph_workspace.workspace/'repo/data/data.csproj').write_text(
        f'<Project><ItemGroup><{selector} {attribute}="SeedData/**/*.json" /></ItemGroup></Project>')
    assert resolve(task, graph_workspace.context).method == 'dotnet_project_closure_v2'


@pytest.mark.parametrize('metadata', [
    '<Project Sdk="Unknown.Sdk" />',
    '<Project><Import Project="custom.targets" /></Project>',
    '<Project><ItemGroup Condition="$(Unknown)"><Content Include="SeedData/*.json" /></ItemGroup></Project>',
    '<Project><ItemGroup><Content Include="../outside/**/*.json" /></ItemGroup></Project>',
    '<Project><ItemGroup><Content Include="$(Unknown)/**/*.json" /></ItemGroup></Project>',
    '<Project><ItemGroup><Compile Include="/outside/code.cs" /></ItemGroup></Project>',
    '<Project><PropertyGroup><RunSettingsFilePath>$(Unknown)/test.runsettings</RunSettingsFilePath></PropertyGroup></Project>',
])
def test_unknown_or_external_topology_keeps_conservative_fallback(graph_workspace, metadata):
    task = mstest_layout(graph_workspace)
    (graph_workspace.workspace/'repo/data/data.csproj').write_text(metadata)
    result = resolve(task, graph_workspace.context)
    assert result.method == 'workspace_fallback_v1'
    assert result.runtime_mutable
    assert 'unrelated/code.cs' in result.hashes


def test_settings_path_keeps_private_boundary(graph_workspace):
    task = mstest_layout(graph_workspace)
    path = graph_workspace.workspace/'repo/tests/tests.csproj'
    path.write_text('<Project Sdk="MSTest.Sdk"><PropertyGroup><RunSettingsFilePath>../.env</RunSettingsFilePath></PropertyGroup></Project>')
    with pytest.raises(PermissionError):
        resolve(task, graph_workspace.context)


def test_settings_uses_shared_byte_budget(graph_workspace, monkeypatch):
    from council import native_inventory
    from council.diagnostics import DiagnosticRuntimeError
    task = mstest_layout(graph_workspace)
    (graph_workspace.workspace/'repo/tests.runsettings').write_text('x'*2000)
    monkeypatch.setattr(native_inventory, 'MAX_SOURCE_BYTES', 1500)
    with pytest.raises(DiagnosticRuntimeError) as caught:
        resolve(task, graph_workspace.context)
    assert caught.value.code == 'NATIVE_INVENTORY_LIMIT'


@pytest.mark.parametrize('value', ['', '/outside/runsettings', 'folder/../settings',
    '$(Unknown)/test.runsettings', '../../../../outside.runsettings'])
def test_unresolvable_settings_keep_conservative_scope(graph_workspace, value):
    task = mstest_layout(graph_workspace)
    (graph_workspace.workspace/'repo/tests/tests.csproj').write_text(
        f'<Project Sdk="MSTest.Sdk"><PropertyGroup><RunSettingsFilePath>{value}</RunSettingsFilePath></PropertyGroup></Project>')
    assert resolve(task, graph_workspace.context).method == 'workspace_fallback_v1'


def test_settings_link_guard_and_native_denials_are_not_downgraded(graph_workspace, monkeypatch):
    from council.tools import discovery
    task = mstest_layout(graph_workspace)
    monkeypatch.setattr(discovery, '_linked', lambda p: p.name == 'tests.runsettings')
    with pytest.raises(PermissionError, match='links'):
        resolve(task, graph_workspace.context)

    def denied(*args, **kwargs):
        raise PermissionError('native denial')

    monkeypatch.setattr(discovery, '_linked', denied)
    with pytest.raises(PermissionError, match='native denial'):
        resolve(task, graph_workspace.context)


def test_project_local_settings_and_literal_content_are_already_inventoried(graph_workspace):
    task = mstest_layout(graph_workspace)
    root = graph_workspace.workspace
    (root/'repo/tests/tests.csproj').write_text('''<Project Sdk="MSTest.Sdk">
      <PropertyGroup><RunSettingsFilePath>local.runsettings</RunSettingsFilePath></PropertyGroup>
      <ItemGroup><ProjectReference Include="../data/data.csproj" /></ItemGroup></Project>''')
    (root/'repo/tests/local.runsettings').write_text('<RunSettings />')
    (root/'repo/data/data.csproj').write_text('''<Project Sdk="Microsoft.NET.Sdk">
      <ItemGroup><Content Include="SeedData/seed.json" /></ItemGroup></Project>''')

    first = resolve(task, graph_workspace.context)
    assert first.method == 'dotnet_project_closure_v2'
    assert first.hashes['repo/tests/local.runsettings'] is not None
    (root/'repo/tests/local.runsettings').write_text('<RunSettings><Flag /></RunSettings>')
    assert resolve(task, graph_workspace.context).hashes != first.hashes
