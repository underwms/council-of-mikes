#!/usr/bin/env python3
"""
Convenience CLI entrypoint for convening the Council.
Cross-platform: Windows 11 and macOS Darwin.

Usage:
    python scripts/convene.py "I would like to convene the Council to address: <challenge>"
    python scripts/convene.py --story temp/userstories/sprint3/ORDER-185.md
    python scripts/convene.py --dry-run "Audit loyalty API scopes"
"""
import sys
from pathlib import Path

# Ensure tools/council is discoverable
workspace_root = Path(__file__).resolve().parents[1]
council_pkg = workspace_root / "tools" / "council"
if str(council_pkg) not in sys.path:
    sys.path.insert(0, str(council_pkg))

from council.cli import main

if __name__ == "__main__":
    main()
