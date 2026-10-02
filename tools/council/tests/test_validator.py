import sys
from pathlib import Path

def test_workspace_validator_passes():
    workspace_root = Path(__file__).resolve().parents[3]
    validator_script = workspace_root / "scripts" / "validate_workspace.py"
    assert validator_script.exists(), "validate_workspace.py must exist"
    
    # Import and run audit
    sys.path.insert(0, str(workspace_root / "scripts"))
    import validate_workspace
    
    passed, summary = validate_workspace.run_audit(workspace_root)
    assert passed is True, f"Validator audit failed: {summary}"
    assert summary["skills_passed"] is True
    assert summary["imports_passed"] is True
    assert summary["wikilinks_passed"] is True
    assert summary["scripts_passed"] is True
    assert summary["specialists_passed"] is True

if __name__ == "__main__":
    test_workspace_validator_passes()
    print("[PASS] test_workspace_validator_passes passed successfully")
