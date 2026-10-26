"""Bounded, shell-free native child transport without persistent output files."""
import os
import hashlib
import subprocess
import threading
from council.diagnostics import DiagnosticRuntimeError, DiagnosticValueError

LIMIT = 4 * 1024 * 1024

_SIGNALS = {
    'connection_refused': ('connection refused', 'econnrefused'),
    'network_unreachable': ('network unreachable', 'enetunreach', 'network is unreachable'),
    'dns_failure': ('dns error', 'name resolution', 'getaddrinfo', 'enotfound'),
    'tls_failure': ('certificate verify failed', 'tls handshake', 'ssl error'),
    'proxy_failure': ('proxy error', 'proxy authentication', 'proxy connection'),
    'timeout': ('timed out', 'timeout', 'etimedout'),
    'server_error': ('internal server error', 'bad gateway', 'service unavailable'),
    'invalid_schema': ('invalid schema', 'schema validation', 'output schema'),
    'broken_pipe': ('broken pipe', 'epipe'),
    'panic': ('thread panicked', 'panic occurred', 'fatal error'),
}


def process_detail(provider, exit_code, stderr, stdout=b''):
    """Keep finite process facts, never provider text or model output."""
    text = stderr.decode('utf-8', errors='replace').lower()
    signals = [name for name, markers in _SIGNALS.items() if any(marker in text for marker in markers)]
    return {'provider': provider, 'exit_code': exit_code, 'stderr_bytes': len(stderr),
            'stdout_bytes': len(stdout), 'stderr_sha256': hashlib.sha256(stderr).hexdigest(),
            'signals': signals or ['unclassified']}


def failure_category(stderr):
    text = stderr.decode('utf-8', errors='replace').lower()
    if any(marker in text for marker in ('cannot be used with', 'unexpected argument', 'unrecognized argument')):
        return 'invalid_arguments'
    if any(marker in text for marker in ('unauthenticated', 'authentication required', 'not logged in', 'invalid credentials')):
        return 'authentication_required'
    if any(marker in text for marker in ('quota exceeded', 'rate limit', 'usage limit')):
        return 'quota_exceeded'
    if 'model' in text and any(marker in text for marker in ('not found', 'unsupported', 'does not exist')):
        return 'unsupported_model'
    return 'execution_failed'


def _kill(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
    if process.poll() is None:
        process.kill()


def cleanup_evidence(process):
    """Attest only the process handle we created; detached resources are unobserved."""
    from council.diagnostics import event
    detail={'owned_process_exit_confirmed':process.returncode is not None,'detached_resources':'unobserved'}
    event('resource_cleanup_observed',stage='runtime',resource_cleanup=detail)
    return detail


def run_process(argv, payload=b'', *, cwd=None, env=None, timeout=600):
    if len(payload) > LIMIT:
        raise DiagnosticValueError('CLI_INPUT_LIMIT')
    try:
        child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, cwd=cwd, env=env, shell=False)
    except OSError:
        raise DiagnosticRuntimeError('CLI_START_FAILED') from None
    stdout, stderr = bytearray(), bytearray()
    received, lock, overflow, failures = [0], threading.Lock(), threading.Event(), []

    def read(stream, destination):
        try:
            while chunk := stream.read(65536):
                with lock:
                    received[0] += len(chunk)
                    exceeded = received[0] > LIMIT
                if exceeded:
                    overflow.set()
                    _kill(child)
                    break
                destination.extend(chunk)
        except OSError:
            failures.append(True)
        finally:
            stream.close()

    def write():
        try:
            child.stdin.write(payload)
        except OSError:
            pass
        finally:
            child.stdin.close()

    threads = [threading.Thread(target=read, args=(child.stdout, stdout), daemon=True),
               threading.Thread(target=read, args=(child.stderr, stderr), daemon=True),
               threading.Thread(target=write, daemon=True)]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill(child)
        child.wait()
    finally:
        for thread in threads:
            thread.join(timeout=10)
    detail = process_detail('codex-cli', child.returncode, bytes(stderr), bytes(stdout))
    if timed_out:
        raise DiagnosticRuntimeError('CLI_TIMEOUT', cli_process=detail,resource_cleanup=cleanup_evidence(child)) from None
    if overflow.is_set():
        raise DiagnosticRuntimeError('CLI_OUTPUT_LIMIT', cli_process=detail)
    if failures or any(thread.is_alive() for thread in threads):
        raise DiagnosticRuntimeError('CLI_IO_FAILED', cli_process=detail)
    return child.returncode, bytes(stdout), bytes(stderr)
