#!/usr/bin/env python3
"""
Universal CBH Workspace Integrity Validator (Python 3.11+)
Cross-platform validator for Windows 11 and macOS.
Zero external dependencies required (pure standard library).
"""
import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Tuple, Dict, Any, List

def audit_skill_frontmatter(workspace_root: Path) -> Tuple[bool, int, List[str]]:
    skills_dir = workspace_root / ".gemini" / "skills"
    if not skills_dir.exists():
        return True, 0, []
    
    count = 0
    errors = []
    for skill_file in skills_dir.glob("**/SKILL.md"):
        count += 1
        content = skill_file.read_text(encoding="utf-8", errors="replace")
        # Match YAML frontmatter block
        match = re.search(r"\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n", content, re.DOTALL)
        if not match:
            errors.append(f"{skill_file.relative_to(workspace_root)} missing YAML frontmatter block")
            continue
        
        frontmatter = match.group(1)
        if not re.search(r"(?m)^\s*name:\s*\S+", frontmatter):
            errors.append(f"{skill_file.relative_to(workspace_root)} frontmatter missing 'name:'")
        if not re.search(r"(?m)^\s*description:\s*\S+", frontmatter):
            errors.append(f"{skill_file.relative_to(workspace_root)} frontmatter missing 'description:'")
            
    return len(errors) == 0, count, errors

def audit_gemini_imports(workspace_root: Path) -> Tuple[bool, int, List[str]]:
    gemini_md = workspace_root / ".gemini" / "GEMINI.md"
    if not gemini_md.exists():
        return True, 0, []
    
    lines = gemini_md.read_text(encoding="utf-8", errors="replace").splitlines()
    errors = []
    import_count = 0
    for idx, line in enumerate(lines, 1):
        if line.startswith("@"):
            import_count += 1
            import_path = line[1:].strip()
            resolved = (workspace_root / ".gemini" / import_path).resolve()
            if not resolved.exists():
                errors.append(f".gemini/GEMINI.md (Line {idx}) -> Broken import: {import_path}")
                
    return len(errors) == 0, import_count, errors

def audit_wikilinks(workspace_root: Path) -> Tuple[bool, int, List[str]]:
    errors = []
    total_links = 0
    wl_index: Dict[str, bool] = {}

    # Ignore folders
    ignore_parts = {".git", "node_modules", ".vs", ".idea", "bin", "obj", "temp"}
    
    def is_ignored(p: Path) -> bool:
        return any(part in ignore_parts for part in p.parts) or "template" in p.name.lower()

    md_files = [p for p in workspace_root.rglob("*.md") if not is_ignored(p)]

    # Index all .md files in the workspace
    for md in md_files:
        wl_index[md.stem.lower()] = True
        if md.name.endswith(".moc.md"):
            wl_index[md.name[:-7].lower()] = True

    # Also index global council references from ~/.gemini/skills
    home = Path(os.path.expanduser("~"))
    global_gemini = home / ".gemini"
    if global_gemini.exists():
        for gmd in global_gemini.rglob("*.md"):
            wl_index[gmd.stem.lower()] = True

    wl_pattern = re.compile(r"(?<![`\\])\[\[(?P<target>[^\]\|`#]+?)(?:\\?\|[^\]`]+)?(?:#[^\]`]+)?\]\](?!`)")

    for md in md_files:
        raw_text = md.read_text(encoding="utf-8", errors="replace")
        # Strip fenced code blocks and inline code literals so code examples don't trigger false positives
        clean_text = re.sub(r"```.*?```", "", raw_text, flags=re.DOTALL)
        clean_text = re.sub(r"`.*?`", "", clean_text)
        
        rel = str(md.relative_to(workspace_root))
        for match in wl_pattern.finditer(clean_text):
            total_links += 1
            target = match.group("target").strip().rstrip("\\")
            if target.startswith("<") and target.endswith(">"):
                continue
            if target.lower() not in wl_index:
                errors.append(f"{rel} -> Broken wikilink: [[{target}]]")

    return len(errors) == 0, total_links, errors

def audit_scripts_cleanliness(workspace_root: Path) -> Tuple[bool, int, List[str]]:
    ignore_parts = {".git", "node_modules", ".vs", ".idea", "bin", "obj", "temp"}
    
    def is_ignored(p: Path) -> bool:
        return any(part in ignore_parts for part in p.parts)

    scripts = [
        p for p in workspace_root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".ps1", ".py"} and not is_ignored(p)
    ]
    
    errors = []
    for s in scripts:
        if s.suffix.lower() == ".py":
            try:
                compile(s.read_text(encoding="utf-8", errors="replace"), str(s), "exec")
            except SyntaxError as e:
                errors.append(f"{s.relative_to(workspace_root)}: Line {e.lineno} SyntaxError: {e.msg}")
            except Exception as e:
                errors.append(f"{s.relative_to(workspace_root)}: Error: {str(e)}")
        elif s.suffix.lower() == ".ps1":
            # Check syntax using PowerShell AST parser if on Windows, else fallback to structural check
            if os.name == "nt":
                try:
                    cmd = ["powershell", "-NoProfile", "-Command", f"$e=$null; [System.Management.Automation.Language.Parser]::ParseFile('{str(s)}', [ref]$null, [ref]$e); if($e.Count -gt 0){{ exit 1 }} exit 0"]
                    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    if res.returncode != 0:
                        errors.append(f"{s.relative_to(workspace_root)}: PowerShell syntax parse error")
                except Exception as e:
                    errors.append(f"{s.relative_to(workspace_root)}: {str(e)}")
            else:
                content = s.read_text(encoding="utf-8", errors="replace")
                stripped = re.sub(r"(?s)<#.*?#>", "", content)
                stripped = re.sub(r"#[^\n]*", "", stripped)
                stripped = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', stripped)
                stripped = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", stripped)
                if stripped.count("{") != stripped.count("}"):
                    errors.append(f"{s.relative_to(workspace_root)}: Mismatched curly braces {{ }}")
                if stripped.count("(") != stripped.count(")"):
                    errors.append(f"{s.relative_to(workspace_root)}: Mismatched parentheses ( )")

    return len(errors) == 0, len(scripts), errors

def audit_host_specialists() -> Tuple[bool, int, List[str]]:
    """Audits that all 15 Council V2 specialist skill packages are installed and healthy in ~/.gemini/skills/."""
    errors = []
    user_profile = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
    skills_dir = user_profile / ".gemini" / "skills"
    
    expected = [
        "the-architect", "the-builder", "the-coder", "the-codex",
        "the-coordinator", "the-curator", "the-gatekeeper", "the-pipelineer",
        "the-prover", "the-provisioner", "the-purifier", "the-relay",
        "the-renderer", "the-sentinel", "the-watcher"
    ]
    
    if not skills_dir.exists():
        return False, 0, [f"Host skills directory missing: {skills_dir}. Run scripts/setup-council.ps1 to install."]
        
    found_count = 0
    for name in expected:
        skill_file = skills_dir / name / "SKILL.md"
        if not skill_file.exists():
            errors.append(f"Missing Council specialist: ~/.gemini/skills/{name}/SKILL.md (Run scripts/setup-council.ps1 to install)")
        else:
            content = skill_file.read_text(encoding="utf-8", errors="replace")
            if not content.startswith("---") or "name:" not in content or "description:" not in content:
                errors.append(f"Specialist ~/.gemini/skills/{name}/SKILL.md has invalid frontmatter")
            else:
                found_count += 1
                
    return len(errors) == 0, found_count, errors

def run_audit(workspace_root: Path) -> Tuple[bool, Dict[str, Any]]:
    skills_pass, skill_count, skill_errors = audit_skill_frontmatter(workspace_root)
    imports_pass, import_count, import_errors = audit_gemini_imports(workspace_root)
    wikilinks_pass, link_count, link_errors = audit_wikilinks(workspace_root)
    scripts_pass, script_count, script_errors = audit_scripts_cleanliness(workspace_root)
    specialists_pass, specialist_count, specialist_errors = audit_host_specialists()
    
    all_passed = skills_pass and imports_pass and wikilinks_pass and scripts_pass and specialists_pass
    summary = {
        "passed": all_passed,
        "skills_passed": skills_pass,
        "skill_count": skill_count,
        "imports_passed": imports_pass,
        "import_count": import_count,
        "wikilinks_passed": wikilinks_pass,
        "link_count": link_count,
        "scripts_passed": scripts_pass,
        "script_count": script_count,
        "specialists_passed": specialists_pass,
        "specialist_count": specialist_count,
        "errors": skill_errors + import_errors + link_errors + script_errors + specialist_errors
    }
    return all_passed, summary

def main():
    if len(sys.argv) > 1:
        root = Path(sys.argv[1]).resolve()
    else:
        root = Path(__file__).resolve().parents[1]

    print("=========================================")
    print(" CBH Workspace Integrity Validator (Universal)")
    print(f" Root: {root}")
    print("=========================================\n")
    
    passed, summary = run_audit(root)
    
    print("[1/5] Auditing SKILL.md frontmatter...")
    if summary["skills_passed"]:
        print(f"  [PASS] All {summary['skill_count']} SKILL.md files have valid frontmatter metadata\n")
    else:
        print(f"  [FAIL] {len(summary['errors'])} frontmatter failures\n")
        
    print("[2/5] Auditing Gemini configuration imports...")
    if summary["imports_passed"]:
        print(f"  [PASS] All {summary['import_count']} configuration imports in GEMINI.md resolve correctly\n")
    else:
        print(f"  [FAIL] Import resolution failures detected\n")
        
    print("[3/5] Auditing Markdown [[wikilinks]]...")
    if summary["wikilinks_passed"]:
        print(f"  [PASS] All {summary['link_count']} [[wikilinks]] across the workspace resolve successfully\n")
    else:
        print(f"  [FAIL] Broken wikilinks detected\n")
        
    print("[4/5] Auditing Universal Script Cleanliness...")
    if summary["scripts_passed"]:
        print(f"  [PASS] All {summary['script_count']} scripts syntactically valid\n")
    else:
        print(f"  [FAIL] Script syntax errors detected\n")

    print("[5/5] Auditing Council V2 Specialist Skills in host ~/.gemini/skills/...")
    if summary["specialists_passed"]:
        print(f"  [PASS] All {summary['specialist_count']} Council V2 specialist skills installed and healthy in host ~/.gemini/skills/\n")
    else:
        print(f"  [FAIL] Council specialist installation errors detected\n")
        
    print("=========================================")
    if passed:
        print(" [PASS] INTEGRITY AUDIT PASSED")
        print(" Your workspace is perfectly clean and tight!")
        print("=========================================")
        sys.exit(0)
    else:
        print(" [FAIL] INTEGRITY AUDIT FAILED")
        for err in summary["errors"]:
            print(f"  - {err}")
        print("=========================================")
        sys.exit(1)

if __name__ == "__main__":
    main()
