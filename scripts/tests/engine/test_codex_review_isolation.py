"""Cross the real read-only adapter/child seam; never call a model in pytest."""
import json

import pytest

from council.codex_cli import CodexCLIWorker
from test_codex_cli import native, completed


def test_read_only_turn_removes_catalog_tools_and_checks_inventory_before_exec(native, monkeypatch):
    settings, context, _, state, calls = native
    monkeypatch.setenv('CODEX_HOME', 'retained-auth-home')
    monkeypatch.setenv('OPENAI_API_KEY', 'PRIVATE_KEY')

    result = CodexCLIWorker('gpt-exact', settings, context).invoke_read_only({'instruction':'Synthetic review'})

    assert result.content == 'Implemented'
    assert any('models' in argv and '--bundled' in argv for argv, _ in calls)
    preflight = next((argv, kw) for argv, kw in calls if 'prompt-input' in argv)
    execute = next((argv, kw) for argv, kw in calls if 'exec' in argv)
    assert calls.index(preflight) < calls.index(execute)
    assert '--no-daemon' in preflight[0] and '--no-daemon' in execute[0]
    assert preflight[1]['env']['CODEX_HOME'] != 'retained-auth-home'
    assert execute[1]['env']['CODEX_HOME'] == 'retained-auth-home'
    assert 'OPENAI_API_KEY' not in execute[1]['env']
    assert '--ignore-user-config' in execute[0] and '--approve-for-me' not in execute[0]
    selected, = state['observed_catalog']['models']
    assert selected['slug'] == 'gpt-exact' and selected['context_window'] == 123456
    assert selected['tool_mode'] is None and selected['multi_agent_version'] is None
    assert selected['experimental_supported_tools'] == [] and selected['apply_patch_tool_type'] is None
    assert selected['node_repl_disabled'] is True and selected['supports_search_tool'] is False


@pytest.mark.parametrize('inventory', [
    [{'type':'additional_tools','tools':[{'type':'namespace','name':'functions','tools':[{'name':'exec'}]}]}],
    [{'type':'additional_tools','tools':[{'type':'function','name':'unexpected'}]}],
    [{'type':'additional_tools','tools':'PRIVATE_TOOL_PAYLOAD'}],
    [{'type':'unrecognized_prompt_item'}], {}, [],
])
def test_uncertified_or_exposed_tools_prevent_model_dispatch(native, inventory):
    from council.diagnostics import describe
    settings, context, _, state, calls = native
    state['inventory'] = inventory

    with pytest.raises(RuntimeError) as caught:
        CodexCLIWorker('gpt-exact', settings, context).invoke_read_only({})

    assert caught.value.code == 'CODEX_REVIEW_ISOLATION_FAILED'
    assert 'PRIVATE_' not in json.dumps(describe(caught.value))
    assert not any('exec' in argv for argv, _ in calls)


@pytest.mark.parametrize('failure', ['catalog_exit', 'inventory_exit', 'missing_model', 'duplicate_model', 'invalid_inventory'])
def test_local_preflight_failures_are_finite_and_prevent_exec(native, failure):
    settings, context, _, state, calls = native
    if failure.endswith('_exit'):
        state[failure] = 1
    elif failure == 'missing_model':
        state['catalog'] = {'models':[]}
    elif failure == 'duplicate_model':
        state['catalog'] = {'models':[{'slug':'gpt-exact'}, {'slug':'gpt-exact'}]}
    else:
        state['inventory_raw'] = '[{"type":"message","type":"additional_tools","tools":[]}]'

    with pytest.raises(RuntimeError) as caught:
        CodexCLIWorker('gpt-exact', settings, context).invoke_read_only({})

    assert caught.value.code == 'CODEX_REVIEW_ISOLATION_FAILED'
    assert not any('exec' in argv for argv, _ in calls)


def test_unexpected_native_tool_still_fails_after_empty_inventory(native):
    settings, context, _, state, _ = native
    state['events'] = completed([{'type':'item.started','item':{'id':'bad','type':'mcp_tool_call','status':'in_progress'}}])
    with pytest.raises(ValueError) as caught:
        CodexCLIWorker('gpt-exact', settings, context).invoke_read_only({})
    assert caught.value.code == 'CODEX_REVIEW_TOOL_REJECTED'


def test_worker_retains_existing_authority_and_does_not_use_review_catalog(native):
    settings, context, task, _, calls = native
    CodexCLIWorker('gpt-exact', settings, context).run_task(task, 'Synthetic worker')
    argv, _ = calls[-1]
    assert '--approve-for-me' in argv
    assert '--no-daemon' not in argv
    assert not any('debug' in args for args, _ in calls)


def test_uncertified_isolation_is_a_programmatic_hard_stop():
    from council.recovery import HARD_STOPS
    assert 'CODEX_REVIEW_ISOLATION_FAILED' in HARD_STOPS


@pytest.mark.parametrize('catalog', [{'models':{}}, {'models':[None]}, {'models':float('nan')}, None])
def test_malformed_bundled_metadata_cannot_supply_capabilities(native, catalog):
    settings, context, _, state, calls = native
    state['catalog'] = catalog
    with pytest.raises(RuntimeError) as caught:
        CodexCLIWorker('gpt-exact', settings, context).invoke_read_only({})
    assert caught.value.code == 'CODEX_REVIEW_ISOLATION_FAILED'
    assert not any('exec' in argv for argv, _ in calls)


def test_catalog_write_denial_preserves_permission_boundary(native, monkeypatch):
    from pathlib import Path
    settings, context, _, _, calls = native
    original = Path.write_text

    def denied(path, *args, **kwargs):
        if path.name == 'reasoning-model.json':
            raise PermissionError('PRIVATE_DENIAL')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'write_text', denied)
    with pytest.raises(PermissionError):
        CodexCLIWorker('gpt-exact', settings, context).invoke_read_only({})
    assert not any('exec' in argv for argv, _ in calls)


def test_per_turn_catalog_and_empty_diagnostic_home_are_cleaned(native):
    from pathlib import Path
    settings, context, _, _, calls = native
    CodexCLIWorker('gpt-exact', settings, context).invoke_read_only({})
    _, preflight = next((args, kw) for args, kw in calls if 'prompt-input' in args)
    _, execute = next((args, kw) for args, kw in calls if 'exec' in args)
    assert not Path(preflight['env']['CODEX_HOME']).exists()
    assert not Path(execute['cwd']).exists()
