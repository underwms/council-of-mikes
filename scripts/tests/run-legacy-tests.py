"""Run archived engine regression scripts with scratch and simulated checkpoints isolated."""
import os
from pathlib import Path
import runpy
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    scratch = ROOT / "work/legacy-regression"
    scratch.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(scratch)
    os.environ["TEMP"] = str(scratch)
    os.environ["TMP"] = str(scratch)
    os.environ["COUNCIL_ROOT"] = str(ROOT)
    os.environ["COUNCIL_MEMORY_ROOT"] = str(scratch / "memory")
    os.environ["COUNCIL_MEMORY_SCOPE"] = "legacy-shared"
    os.chdir(ROOT)
    tests = sorted((ROOT / "legacy/workspace/tools/council/tests").glob("test_*.py"))
    for script in tests:
        print(f"Running {script.name}", flush=True)
        runpy.run_path(str(script), run_name="__main__")
    print(f"PASS: {len(tests)} archived regression scripts; standard-library fallback runtime.")


if __name__ == "__main__":
    main()
