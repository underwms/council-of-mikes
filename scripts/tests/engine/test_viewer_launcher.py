"""Viewer startup must stay optional and isolated from Council execution."""
from unittest.mock import Mock


def test_interactive_run_launches_viewer_with_private_paths(monkeypatch, tmp_path):
    from council.viewer import launch_viewer

    root = tmp_path / 'council-root'
    (root / 'visualizer' / 'server').mkdir(parents=True)
    (root / 'visualizer' / 'dist').mkdir()
    (root / 'visualizer' / 'dist' / 'index.html').write_text('')
    (root / 'visualizer' / 'server' / 'main.ts').write_text('')
    context = Mock(council_root=root, memory_root=root / 'memory' / 'engine')
    spawned = []
    monkeypatch.setattr('council.viewer.shutil.which', lambda name: 'deno.exe')
    monkeypatch.setattr('council.viewer.subprocess.Popen', lambda *args, **kwargs: spawned.append((args, kwargs)) or Mock())
    monkeypatch.setattr('council.viewer._ready', lambda url: True)
    monkeypatch.setattr('council.viewer.webbrowser.open', lambda url: True)
    monkeypatch.setattr('council.viewer._free_port', lambda: 43210)

    url = launch_viewer(context, 'safe-run', interactive=True)

    assert url == 'http://127.0.0.1:43210/?run=safe-run'
    command = spawned[0][0][0]
    assert command[:4] == ['deno.exe', 'run', '--no-config', '--allow-read']
    assert '--checkpoint-db' in command
    assert str(context.memory_root / 'council_checkpoints.db') in command
    assert spawned[0][1]['stdin'] is not None


def test_viewer_skips_noninteractive_and_missing_assets(monkeypatch, tmp_path):
    from council.viewer import launch_viewer

    context = Mock(council_root=tmp_path, memory_root=tmp_path / 'memory')
    monkeypatch.setattr('council.viewer.subprocess.Popen', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('spawned')))
    assert launch_viewer(context, 'run', interactive=False) is None
    assert launch_viewer(context, 'run', interactive=True) is None


def test_viewer_failure_cannot_fail_task(monkeypatch, tmp_path):
    from council.viewer import launch_viewer

    (tmp_path / 'visualizer' / 'server').mkdir(parents=True)
    (tmp_path / 'visualizer' / 'dist').mkdir()
    (tmp_path / 'visualizer' / 'dist' / 'index.html').write_text('')
    (tmp_path / 'visualizer' / 'server' / 'main.ts').write_text('')
    context = Mock(council_root=tmp_path, memory_root=tmp_path / 'memory')
    monkeypatch.setattr('council.viewer.shutil.which', lambda name: 'deno.exe')
    monkeypatch.setattr('council.viewer._free_port', lambda: 43210)
    monkeypatch.setattr('council.viewer.subprocess.Popen', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('unavailable')))
    assert launch_viewer(context, 'run', interactive=True) is None


def test_cli_viewer_is_interactive_and_can_be_disabled(monkeypatch):
    from council import cli

    calls = []
    monkeypatch.setattr(cli, 'run_council_task', lambda *args, **kwargs: calls.append(kwargs) or 0)
    monkeypatch.setattr(cli.sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr(cli.sys.stdout, 'isatty', lambda: True)
    assert cli.main(['fixture']) == 0
    assert calls[-1]['viewer'] is True
    assert cli.main(['fixture', '--no-viewer']) == 0
    assert calls[-1]['viewer'] is False
    assert cli.main(['fixture', '--no-input']) == 0
    assert calls[-1]['viewer'] is False
