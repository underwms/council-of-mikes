"""Best-effort local viewer startup for interactive Council runs."""
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

_children = []


def _free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def _ready(url):
    health = url.split('/?run=', 1)[0] + '/api/health'
    for _ in range(10):
        try:
            with urllib.request.urlopen(health, timeout=0.1) as response:
                return response.status == 200
        except (OSError, TimeoutError):
            time.sleep(0.1)
    return False


def launch_viewer(context, run_id, *, interactive):
    """Start the local viewer and return its URL, or None on any startup failure."""
    if not interactive:
        return None
    try:
        root = Path(context.council_root) / 'visualizer'
        server = root / 'server' / 'main.ts'
        dist = root / 'dist'
        deno = shutil.which('deno')
        if not server.is_file() or not (dist / 'index.html').is_file() or not deno:
            return None
        port = _free_port()
        diagnostics = Path(context.memory_root) / 'diagnostics'
        checkpoint = Path(context.memory_root) / 'council_checkpoints.db'
        command = [deno, 'run', '--no-config', '--allow-read', '--allow-net=127.0.0.1',
                   str(server), '--run-id', run_id, '--diagnostics-dir', str(diagnostics),
                   '--checkpoint-db', str(checkpoint), '--port', str(port), '--watch-stdin']
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, creationflags=flags)
        if process.stdin is None:
            process.terminate()
            return None
        url = f'http://127.0.0.1:{port}/?run={run_id}'
        if not _ready(url):
            process.terminate()
            process.stdin.close()
            return None
        _children.append(process)
        print(f'Council viewer: {url}', file=sys.stderr, flush=True)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        return url
    except Exception:
        return None
