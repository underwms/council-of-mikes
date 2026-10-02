"""Bridge integrating the universal workspace validator into the Council engine."""
import sys
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

def run_workspace_audit(workspace_root: Optional[Path] = None) -> Tuple[bool, Dict[str, Any]]:
    """Invokes scripts/validate_workspace.py and returns (passed, summary)."""
    if workspace_root is None:
        # Resolve workspace root from tools/council/council/tools -> workspace_root
        workspace_root = Path(__file__).resolve().parents[4]
    
    scripts_dir = workspace_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
        
    import validate_workspace
    return validate_workspace.run_audit(workspace_root)
