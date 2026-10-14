"""Specialist skill package loader and persona binder."""
import re
from pathlib import Path
from typing import Optional, List

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
    """Discovers and parses the canonical Council specialist skill packages."""

    def __init__(self, skills_dir: Optional[Path] = None, *, context=None):
        from council.runtime_context import resolve_context
        self.context = context or resolve_context()
        canonical = (self.context.council_root / "skills").resolve()
        if not canonical.is_relative_to(self.context.council_root):
            raise PermissionError("Canonical specialist root escapes Council source")
        self.skills_dir = Path(skills_dir).resolve() if skills_dir else canonical
        if not self.skills_dir.is_relative_to(canonical):
            raise PermissionError("Specialists must come from canonical Council skills")

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
        if not re.fullmatch(r"[a-z][a-z0-9-]*", specialist_name):
            raise ValueError("Invalid specialist name")
        pkg_dir = (self.skills_dir / specialist_name).resolve()
        if not pkg_dir.is_relative_to(self.skills_dir):
            raise PermissionError("Specialist escapes canonical skills")
        skill_file = pkg_dir / "SKILL.md"
        if not skill_file.exists():
            return None

        if not skill_file.resolve().is_relative_to(self.skills_dir):
            raise PermissionError("Specialist instructions escape canonical skills")
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
