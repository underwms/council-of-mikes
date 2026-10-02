"""Specialist skill package loader and persona binder."""
import os
import re
from pathlib import Path
from typing import Optional, List, Dict

class SpecialistPackage:
    """Represents a loaded Council specialist skill package."""

    def __init__(self, name: str, description: str, instructions: str, call_sign: str):
        self.name = name
        self.description = description
        self.instructions = instructions
        self.call_sign = call_sign

    def __repr__(self) -> str:
        return f"<SpecialistPackage {self.call_sign}: {self.description[:40]}...>"

class SpecialistLoader:
    """Discovers and parses specialist skill packages from ~/.gemini/skills/."""

    def __init__(self, skills_dir: Optional[Path] = None):
        if skills_dir:
            self.skills_dir = skills_dir.resolve()
        else:
            home = Path(os.path.expanduser("~"))
            self.skills_dir = (home / ".gemini" / "skills").resolve()

    def list_available_specialists(self) -> List[str]:
        """Lists all discovered specialist packages containing a valid SKILL.md."""
        if not self.skills_dir.exists():
            return []
        
        specialists = []
        for child in sorted(self.skills_dir.iterdir()):
            if child.is_dir() and (child / "SKILL.md").exists():
                specialists.append(child.name)
        return specialists

    def get_specialist(self, specialist_name: str) -> Optional[SpecialistPackage]:
        """Loads and returns a SpecialistPackage for the requested name."""
        pkg_dir = self.skills_dir / specialist_name
        skill_file = pkg_dir / "SKILL.md"
        if not skill_file.exists():
            return None
        
        content = skill_file.read_text(encoding="utf-8", errors="replace")
        
        # Extract description from frontmatter
        desc_match = re.search(r"(?m)^\s*description:\s*(.+)$", content)
        description = desc_match.group(1).strip() if desc_match else specialist_name
        
        # Extract call-sign (e.g. "the-coder" -> "[THE CODER]")
        call_sign = f"[{specialist_name.upper().replace('-', ' ')}]"
        
        return SpecialistPackage(
            name=specialist_name,
            description=description,
            instructions=content,
            call_sign=call_sign
        )
