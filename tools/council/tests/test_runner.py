import sys
from pathlib import Path

# Add package root to sys.path
package_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(package_root))

from council.runner import SubprocessRunner

def test_runner_executes_atomic_command():
    workspace_root = Path(__file__).resolve().parents[3]
    runner = SubprocessRunner(workspace_root)
    
    # Test simple echo / output
    code, stdout, stderr = runner.run_echo("test_ok")
    assert code == 0, f"Expected returncode 0, got {code}: stderr={stderr}"
    assert "test_ok" in stdout, f"Expected 'test_ok' in stdout, got: {stdout}"

def test_runner_detects_platform():
    workspace_root = Path(__file__).resolve().parents[3]
    runner = SubprocessRunner(workspace_root)
    import platform
    assert runner.is_windows == (platform.system() == "Windows")

if __name__ == "__main__":
    test_runner_detects_platform()
    test_runner_executes_atomic_command()
    print("[PASS] test_runner tests passed successfully")
