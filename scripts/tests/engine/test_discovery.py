import pytest

from test_prompt_context import context, put


def tools(context):
    from council.tools.discovery import get_discovery_tools
    return {tool.name: tool for tool in get_discovery_tools(context)}


def test_lists_and_searches_source_with_bounded_results(context):
    put(context.workspace_root, 'repo/a.py', 'first needle\nsecond needle\n')
    put(context.workspace_root, 'repo/b.py', 'other')
    available = tools(context)
    assert set(available) == {'list_workspace_files', 'search_workspace_text'}
    result = available['list_workspace_files'].invoke({'limit': 1})
    assert result['files'] == ['repo/a.py']
    assert result['truncated']
    result = available['search_workspace_text'].invoke({'pattern': 'needle', 'limit': 1})
    assert result['matches'][0]['path'] == 'repo/a.py'
    assert result['matches'][0]['line'] == 1
    assert result['truncated']


def test_excludes_private_generated_and_credential_files(context):
    for path in ('.git/config', '.codex/settings.json', 'repo/node_modules/x.js', 'repo/bin/x.cs', 'repo/.env', 'repo/key.pem'):
        put(context.workspace_root, path, 'needle secret')
    put(context.workspace_root, 'repo/source.py', 'needle public')
    available = tools(context)
    assert available['list_workspace_files'].invoke({})['files'] == ['repo/source.py']
    assert len(available['search_workspace_text'].invoke({'pattern': 'needle'})['matches']) == 1
    with pytest.raises(PermissionError):
        available['list_workspace_files'].invoke({'rel_path': '.git'})


def test_rejects_escapes_and_excessive_limits(context):
    available = tools(context)
    with pytest.raises(PermissionError):
        available['list_workspace_files'].invoke({'rel_path': '../outside'})
    with pytest.raises(ValueError, match='limit'):
        available['list_workspace_files'].invoke({'limit': 201})
    with pytest.raises(ValueError, match='limit'):
        available['search_workspace_text'].invoke({'pattern': 'x', 'limit': 101})


def test_search_is_literal_and_skips_large_and_binary_files(context):
    put(context.workspace_root, 'literal.txt', '[a-z] literal')
    put(context.workspace_root, 'big.txt', 'needle' * 100_000)
    (context.workspace_root / 'binary.dat').write_bytes(b'needle\x00secret')
    result = tools(context)['search_workspace_text'].invoke({'pattern': '[a-z]'})
    assert [match['path'] for match in result['matches']] == ['literal.txt']
    assert not tools(context)['search_workspace_text'].invoke({'pattern': 'needle'})['matches']


def test_excludes_common_host_indexing_artifacts(context):
    for path in ('repo/.vscode/settings.json', 'repo/.deno/cache.ts', 'repo/TestResults/run.xml', 'repo/.pytest_cache/state', 'repo/generated.pyc', 'repo/session.har', 'repo/trace.log'):
        put(context.workspace_root, path, 'private needle')
    assert tools(context)['list_workspace_files'].invoke({})['files'] == []


def test_generated_test_artifacts_are_pruned_before_traversal_budget(context, monkeypatch):
    for index in range(30):
        put(context.workspace_root, f'repo/tests/.artifacts/run-{index}.json', 'generated needle')
    put(context.workspace_root, 'repo/tests/acceptance.test.ts', 'source needle')
    put(context.workspace_root, 'repo/assets/reference.png', 'source asset')
    monkeypatch.setattr('council.tools.discovery.MAX_VISITED_ENTRIES', 20)
    available = tools(context)
    listing = available['list_workspace_files'].invoke({'rel_path': 'repo'})
    assert listing == {'files': ['repo/assets/reference.png', 'repo/tests/acceptance.test.ts'], 'truncated': False}
    matches = available['search_workspace_text'].invoke({'pattern': 'needle', 'rel_path': 'repo'})
    assert [item['path'] for item in matches['matches']] == ['repo/tests/acceptance.test.ts']
    assert not matches['truncated']
    with pytest.raises(PermissionError):
        available['list_workspace_files'].invoke({'rel_path': 'repo/tests/.artifacts'})


def test_directory_junction_cannot_list_or_search_outside(context, tmp_path):
    import os
    import subprocess
    if os.name != 'nt':
        pytest.skip('Windows junction test')
    outside = tmp_path / 'outside'
    outside.mkdir()
    put(outside, 'secret.txt', 'secret needle')
    junction = context.workspace_root / 'escape'
    result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)], capture_output=True)
    if result.returncode and b'Access is denied' in result.stderr:
        pytest.skip('Host security denies creation of directory junctions')
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    try:
        available = tools(context)
        assert available['list_workspace_files'].invoke({})['files'] == []
        assert not available['search_workspace_text'].invoke({'pattern': 'needle'})['matches']
        with pytest.raises(PermissionError):
            available['list_workspace_files'].invoke({'rel_path': 'escape'})
    finally:
        junction.rmdir()
