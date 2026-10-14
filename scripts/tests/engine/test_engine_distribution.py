"""Verify actual wheel layout, independent of the orchestration implementation."""
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]


def test_Wheel_ContainsCouncilPackageAndConsoleEntryPoint_WhenBuilt(tmp_path):
    source = tmp_path / "engine source"
    shutil.copytree(ROOT / "council", source, ignore=shutil.ignore_patterns("__pycache__", "build", "*.egg-info"))
    output = tmp_path / "wheels"

    built = subprocess.run(
        [sys.executable, "-I", "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--disable-pip-version-check", "--wheel-dir", str(output), str(source)],
        capture_output=True, text=True, timeout=120,
    )

    assert built.returncode == 0, built.stdout + built.stderr
    wheels = list(output.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as wheel:
        assert "council/cli.py" in wheel.namelist(), "Wheel must install the council namespace used by its console script"
        assert "council/tools/tool_registry.py" in wheel.namelist()
        assert not any("__pycache__" in name for name in wheel.namelist())
        entry = next(name for name in wheel.namelist() if name.endswith(".dist-info/entry_points.txt"))
        assert "council = council.cli:main" in wheel.read(entry).decode()
        metadata = next(name for name in wheel.namelist() if name.endswith(".dist-info/METADATA"))
        assert "Requires-Dist: langgraph-checkpoint-sqlite" in wheel.read(metadata).decode()
