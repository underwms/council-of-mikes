import sys
from pathlib import Path

package_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(package_root))

from council.cli import create_parser, run_council_task

def test_create_parser_defaults():
    parser = create_parser()
    args = parser.parse_args(["Implement distance unit"])
    assert args.prompt == "Implement distance unit"
    assert args.model == "gemini"
    assert args.auto_approve is False
    assert args.dry_run is False
    assert args.max_retries == 3

def test_create_parser_flags():
    parser = create_parser()
    args = parser.parse_args([
        "Implement distance unit",
        "--model", "claude",
        "--auto-approve",
        "--dry-run",
        "--max-retries", "5"
    ])
    assert args.model == "claude"
    assert args.auto_approve is True
    assert args.dry_run is True
    assert args.max_retries == 5

def test_dry_run_executes_cleanly():
    exit_code = run_council_task(
        prompt="Audit loyalty API scopes",
        model_name="gemini",
        auto_approve=True,
        dry_run=True
    )
    assert exit_code == 0

if __name__ == "__main__":
    test_create_parser_defaults()
    test_create_parser_flags()
    test_dry_run_executes_cleanly()
    print("[PASS] test_cli passed successfully")
