"""Generated frontend dependencies never consume feature-source baselines."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_prompt_context import context, put
from test_finalization import state_for


def frontend(root):
    put(root,'admin/deno.jsonc','{}')
    put(root,'admin/deno.lock','{}')
    put(root,'admin/vendor/manifest.json',json.dumps({'modules':{}}))
    for index in range(530):put(root,f'admin/vendor/jsr.io/package/{index}.ts','third-party source')
    for index in range(30):put(root,f'admin/.react-router/types/{index}.ts','generated type')
    put(root,'admin/app/page.tsx','export const page = true;')


def test_generated_dependencies_pruned_before_inventory_budget(context,monkeypatch):
    from council.native_inventory import snapshot
    from council.tools import discovery
    frontend(context.workspace_root)
    monkeypatch.setattr(discovery,'MAX_VISITED_ENTRIES',25)
    assert set(snapshot(context,'admin'))=={'admin/app/page.tsx','admin/deno.jsonc','admin/deno.lock'}
    with pytest.raises(PermissionError):discovery.validate_read_path(context,'admin/vendor/manifest.json')
    with pytest.raises(PermissionError):discovery.validate_discovery_path(context,'admin/.react-router')


def test_feature_baseline_keeps_both_repositories_without_generated_dependencies(graph_workspace):
    from council import finalization
    root=graph_workspace.workspace
    put(root,'api/source.cs','application source')
    frontend(root)
    state=state_for(graph_workspace)
    finalization.capture(state,graph_workspace.context,'api')
    finalization.capture(state,graph_workspace.context,'admin')
    captured=json.loads(finalization._artifact(state,graph_workspace.context).read_text())
    assert set(captured['files'])=={'api/source.cs','admin/app/page.tsx','admin/deno.jsonc','admin/deno.lock'}
    assert state.finalization.captured_scopes==['api','admin']


@pytest.mark.parametrize('configuration,manifest',[(False,{'modules':{}}),(True,None),(True,{'files':[]}),(True,[])])
def test_ordinary_vendor_sources_are_not_hidden(context,configuration,manifest):
    from council.native_inventory import snapshot
    put(context.workspace_root,'repo/vendor/owned.ts','first-party source')
    if configuration:put(context.workspace_root,'repo/deno.json','{}')
    if manifest is not None:put(context.workspace_root,'repo/vendor/manifest.json',json.dumps(manifest))
    assert 'repo/vendor/owned.ts' in snapshot(context,'repo')


@pytest.mark.parametrize('directory_marker',['deno.json','vendor/manifest.json'])
def test_directory_instead_of_metadata_file_cannot_hide_sources(context,directory_marker):
    from council.native_inventory import snapshot
    root=context.workspace_root
    put(root,'repo/vendor/owned.ts','source')
    if directory_marker!='deno.json':put(root,'repo/deno.json','{}')
    if directory_marker!='vendor/manifest.json':put(root,'repo/vendor/manifest.json','{"modules":{}}')
    (root/'repo'/directory_marker).mkdir()
    assert 'repo/vendor/owned.ts' in snapshot(context,'repo')


@pytest.mark.parametrize('manifest',[b'{invalid',b'\xff',b' '*40])
def test_unrecognized_or_oversized_marker_keeps_conservative_source_inventory(context,monkeypatch,manifest):
    from council.native_inventory import snapshot
    from council.tools import discovery
    put(context.workspace_root,'repo/deno.json','{}')
    put(context.workspace_root,'repo/vendor/owned.ts','source')
    (context.workspace_root/'repo/vendor/manifest.json').write_bytes(manifest)
    monkeypatch.setattr(discovery,'MAX_FILE_BYTES',20)
    assert 'repo/vendor/owned.ts' in snapshot(context,'repo')


def test_linked_marker_cannot_hide_vendor_sources(context,monkeypatch):
    from council.native_inventory import snapshot
    from council.tools import discovery
    put(context.workspace_root,'repo/deno.json','{}')
    put(context.workspace_root,'repo/vendor/owned.ts','source')
    put(context.workspace_root,'repo/vendor/manifest.json','{"modules":{}}')
    marker=context.workspace_root/'repo/vendor/manifest.json'
    original=discovery._linked
    monkeypatch.setattr(discovery,'_linked',lambda path:path==marker or original(path))
    assert 'repo/vendor/owned.ts' in snapshot(context,'repo')


def test_native_marker_read_denial_is_not_a_successful_empty_inventory(context,monkeypatch):
    from council.tools import discovery
    put(context.workspace_root,'repo/deno.json','{}')
    put(context.workspace_root,'repo/vendor/owned.ts','source')
    put(context.workspace_root,'repo/vendor/manifest.json','{"modules":{}}')
    marker=context.workspace_root/'repo/vendor/manifest.json'
    original=Path.open
    def denied(path,*args,**kwargs):
        if path==marker:raise PermissionError('native denial')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',denied)
    with pytest.raises(PermissionError):discovery.validate_read_path(context,'repo/vendor/owned.ts')


def test_real_first_party_limit_remains_a_finite_atomic_failure(graph_workspace):
    from council import finalization
    from council.diagnostics import describe
    for index in range(513):put(graph_workspace.workspace,f'app/{index}.ts','first-party')
    state=state_for(graph_workspace)
    with pytest.raises(ValueError) as caught:finalization.capture(state,graph_workspace.context,'app')
    assert describe(caught.value)['code']=='FINALIZATION_BASELINE_LIMIT'
    assert not finalization._artifact(state,graph_workspace.context).exists()
    assert state.finalization.baseline_sha256 is None


def test_real_byte_limit_remains_a_finite_atomic_failure(graph_workspace,monkeypatch):
    from council import finalization
    from council.diagnostics import describe
    put(graph_workspace.workspace,'app/source.ts','first-party')
    class Oversized:
        def __len__(self):return 70*1024*1024+1
    class Encoded:
        def encode(self,*args,**kwargs):return Oversized()
    monkeypatch.setattr(finalization,'json',SimpleNamespace(dumps=lambda *args,**kwargs:Encoded()))
    state=state_for(graph_workspace)
    with pytest.raises(ValueError) as caught:finalization.capture(state,graph_workspace.context,'app')
    assert describe(caught.value)['code']=='FINALIZATION_BASELINE_LIMIT'
    assert not finalization._artifact(state,graph_workspace.context).exists()
