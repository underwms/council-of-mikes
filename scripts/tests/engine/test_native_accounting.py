"""Documented native statuses and shell-side edits survive graph failures."""
import hashlib
import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command

from council.codex_cli import _parse
from test_codex_cli import completed
from test_codex_routing import configure, graph_for
from test_engine_integration import lifecycle, open_graph


def encoded(events):
    return '\n'.join(json.dumps(event) for event in events).encode()


def declined(exit_code=None):
    return {'type': 'item.completed', 'item': {'id': 'denied',
        'type': 'command_execution', 'status': 'declined', 'exit_code': exit_code,
        'command': 'PRIVATE_COMMAND', 'aggregated_output': 'PRIVATE_OUTPUT'}}


@pytest.mark.parametrize('exit_code', [None, 1, -1, -(2**31), 2**31-1])
def test_documented_declined_command_can_finish_without_becoming_verification(tmp_path, exit_code):
    try:
        result = _parse(encoded(completed([declined(exit_code)])), tmp_path, tmp_path)
    except ValueError:
        pytest.fail('TDD_RED: documented declined command rejected as a failed turn')
    assert result.response_metadata['cli_declined_command_count'] == 1
    assert result.content == 'Implemented'
    assert 'PRIVATE' not in str(result)


def test_declined_count_survives_durable_call_evidence(tmp_path):
    from council.model_evidence import build_call_record
    from council.config import resolve_model_configuration
    response = _parse(encoded(completed([declined()])), tmp_path, tmp_path)
    record = build_call_record(resolve_model_configuration().model_dump(mode='json'),
                               'coder', 'worker', response=response)
    assert record.get('cli_declined_command_count') == 1, 'TDD_RED: declined count lost from durable evidence'


@pytest.mark.parametrize('exit_code', [0, True, '1', 2**31, -(2**31)-1])
def test_malformed_declined_exit_is_rejected(tmp_path, exit_code):
    with pytest.raises(ValueError):
        _parse(encoded(completed([declined(exit_code)])), tmp_path, tmp_path)


@pytest.mark.parametrize('ending', ['failed', 'incomplete', 'review'])
def test_declined_command_does_not_bypass_turn_or_review_guards(tmp_path, ending):
    events = completed([declined()])
    if ending == 'failed':
        events[-1] = {'type': 'turn.failed', 'error': {'message': 'PRIVATE'}}
    elif ending == 'incomplete':
        events = events[:-1]
    with pytest.raises(ValueError) as caught:
        _parse(encoded(events), tmp_path, tmp_path, review_only=ending == 'review')
    expected = {'failed': 'CODEX_TURN_FAILED', 'incomplete': 'CODEX_TURN_INCOMPLETE',
                'review': 'CODEX_REVIEW_TOOL_REJECTED'}[ending]
    assert caught.value.code == expected


class ShellEdits:
    """No native file-change event: models edits made by a native shell."""
    def __init__(self, fixture, fail=False):
        self.fixture, self.fail, self.calls = fixture, fail, 0

    def run_task(self, task, guidance, **kwargs):
        self.calls += 1
        root = self.fixture.workspace
        (root/'target-1.txt').write_text('valid')
        (root/'existing.ts').write_text('changed')
        (root/'new.ts').write_text('added')
        (root/'deleted.ts').unlink()
        (root/'.env').write_text('PRIVATE_SECRET')
        (root/'node_modules/generated.ts').write_text('generated')
        if self.fail:
            raise RuntimeError('PRIVATE_FAILURE')
        return AIMessage(content='finished')


@pytest.mark.parametrize('fail', [True, False])
def test_unreported_shell_edits_are_hashed_even_on_failed_checkpoint(lifecycle, fail):
    configure(lifecycle)
    root = lifecycle.workspace
    (root/'existing.ts').write_text('user draft')
    (root/'deleted.ts').write_text('old')
    (root/'unchanged.ts').write_text('keep')
    (root/'node_modules').mkdir()
    coder = ShellEdits(lifecycle, fail)
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, [])
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
        saved = graph.get_state(lifecycle.config).values
    assert result['modified_files'] == ['deleted.ts', 'existing.ts', 'new.ts', 'target-1.txt'], (
        'TDD_RED: shell changes missing from native result')
    assert saved['file_changes'] == result['file_changes']
    rows = {row['path']: row for row in result['file_changes']}
    assert rows['existing.ts']['before_sha256'] == hashlib.sha256(b'user draft').hexdigest()
    assert rows['existing.ts']['after_sha256'] == hashlib.sha256(b'changed').hexdigest()
    assert rows['new.ts']['before_known'] is True
    assert rows['new.ts']['before_sha256'] is None
    assert rows['deleted.ts']['after_sha256'] is None
    assert 'PRIVATE' not in json.dumps(result, default=str)
    if fail:
        assert result['status'] == 'FAILED'
    else:
        assert result['__interrupt__'][0].value['gate'] == 'GATE_2_PRE_SUBMIT_APPROVAL'


def test_inventory_preflight_limit_prevents_native_dispatch(lifecycle, monkeypatch):
    configure(lifecycle)
    monkeypatch.setattr('council.tools.discovery.MAX_VISITED_ENTRIES', 1)
    coder = ShellEdits(lifecycle)
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, [])
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert coder.calls == 0, 'TDD_RED: provider ran without a complete baseline inventory'
    assert result['diagnostic']['code'] == 'NATIVE_INVENTORY_LIMIT'


def test_snapshot_budget_and_exclusions(lifecycle, monkeypatch):
    from council import native_inventory as inventory
    root = lifecycle.workspace
    (root/'safe.ts').write_bytes(b'ab')
    (root/'.env').write_text('PRIVATE')
    (root/'node_modules').mkdir()
    (root/'node_modules/skip.ts').write_text('PRIVATE')
    monkeypatch.setattr(inventory, 'MAX_SOURCE_BYTES', 2)
    assert inventory.snapshot(lifecycle.context, 'safe.ts') == {
        'safe.ts': hashlib.sha256(b'ab').hexdigest()}
    monkeypatch.setattr(inventory, 'MAX_SOURCE_BYTES', 1)
    with pytest.raises(RuntimeError) as caught:
        inventory.snapshot(lifecycle.context, 'safe.ts')
    assert caught.value.code == 'NATIVE_INVENTORY_LIMIT'
    monkeypatch.setattr(inventory, 'MAX_SOURCE_BYTES', 100_000)
    snapshot = inventory.snapshot(lifecycle.context, '.')
    assert '.env' not in snapshot and not any('node_modules' in key for key in snapshot)


def test_snapshot_io_failure_has_fixed_diagnostic(lifecycle, monkeypatch):
    from council import native_inventory as inventory
    def fail(*args, **kwargs):
        raise PermissionError('PRIVATE_PATH')
    monkeypatch.setattr(inventory, '_walk', fail)
    with pytest.raises(RuntimeError) as caught:
        inventory.snapshot(lifecycle.context, '.')
    assert caught.value.code == 'NATIVE_INVENTORY_FAILED'
    assert 'PRIVATE' not in str(caught.value)


def test_generated_evidence_does_not_consume_source_inventory_byte_budget(lifecycle, monkeypatch):
    from council import native_inventory as inventory
    root = lifecycle.workspace
    (root/'repo/tests/.artifacts').mkdir(parents=True)
    (root/'repo/tests/.artifacts/coverage.json').write_bytes(b'x' * 200)
    (root/'repo/tests/source.ts').write_bytes(b'ab')
    monkeypatch.setattr(inventory, 'MAX_SOURCE_BYTES', 2)
    assert inventory.snapshot(lifecycle.context, 'repo') == {
        'repo/tests/source.ts': hashlib.sha256(b'ab').hexdigest()}
    assert (root/'repo/tests/.artifacts/coverage.json').stat().st_size == 200
    (root/'repo/tests/source.ts').write_bytes(b'abc')
    with pytest.raises(RuntimeError) as caught:
        inventory.snapshot(lifecycle.context, 'repo')
    assert caught.value.code == 'NATIVE_INVENTORY_LIMIT'


def test_after_inventory_failure_retains_declared_evidence(lifecycle, monkeypatch):
    from council import native_inventory as inventory
    configure(lifecycle)
    class Coder:
        def run_task(self, *args, **kwargs):
            (lifecycle.workspace/'target-1.txt').write_text('valid')
            monkeypatch.setattr(inventory, 'MAX_SOURCE_BYTES', 0)
            raise RuntimeError('native failure')
    coder = Coder()
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, [])
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert result['status'] == 'FAILED'
    assert result['diagnostic']['code'] == 'NATIVE_INVENTORY_LIMIT'
    assert result['modified_files'] == ['target-1.txt']


def test_restoring_source_during_repair_removes_cumulative_change(lifecycle):
    configure(lifecycle)
    (lifecycle.workspace/'existing.ts').write_text('user draft')
    class Coder:
        calls = 0
        def run_task(self, *args, **kwargs):
            self.calls += 1
            (lifecycle.workspace/'target-1.txt').write_text('invalid' if self.calls == 1 else 'valid')
            (lifecycle.workspace/'existing.ts').write_text('changed' if self.calls == 1 else 'user draft')
            return AIMessage(content='finished')
    coder = Coder()
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, [])
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert coder.calls == 2
    assert result['modified_files'] == ['target-1.txt']
    assert (lifecycle.workspace/'existing.ts').read_text() == 'user draft'


def test_event_outside_task_snapshot_keeps_unknown_before(lifecycle):
    import sys
    configure(lifecycle)
    (lifecycle.workspace/'repo').mkdir()
    task = lifecycle.plan.tasks[0]
    task.working_directory = 'repo'
    task.test_commands = [[sys.executable, '../verify.py', '../target-1.txt']]
    class Coder:
        def run_task(self, *args, **kwargs):
            (lifecycle.workspace/'target-1.txt').write_text('valid')
            (lifecycle.workspace/'extra.ts').write_text('new')
            return AIMessage(content='finished', additional_kwargs={'native_file_changes': ['extra.ts']})
    coder = Coder()
    with open_graph(lifecycle, coder) as saver:
        graph = graph_for(lifecycle, saver, coder, [])
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    row = next(row for row in result['file_changes'] if row['path'] == 'extra.ts')
    assert row['before_known'] is False


@pytest.mark.parametrize('status', ['unexpected', ['PRIVATE']])
def test_unknown_status_is_sanitized_contract_failure(tmp_path, status):
    item = declined()
    item['item']['status'] = status
    with pytest.raises(ValueError) as caught:
        _parse(encoded(completed([item])), tmp_path, tmp_path)
    from council.diagnostics import describe
    diagnostic = describe(caught.value)
    assert diagnostic['code'] == 'CODEX_EVENT_INVALID'
    assert diagnostic['native_event']['reason'] == 'INVALID_ITEM_STATUS'
    assert 'PRIVATE' not in str(diagnostic)


@pytest.mark.parametrize('mutation', ['started', 'file_change', 'missing_exit'])
def test_declined_is_only_valid_as_completed_command(tmp_path, mutation):
    item = declined()
    if mutation == 'started':
        item['type'] = 'item.started'
    elif mutation == 'file_change':
        item['item'].update(type='file_change', changes=[])
    else:
        item['item'].pop('exit_code')
    with pytest.raises(ValueError) as caught:
        _parse(encoded(completed([item])), tmp_path, tmp_path)
    assert caught.value.native_event['reason'] == 'INVALID_DECLINED_COMMAND'
