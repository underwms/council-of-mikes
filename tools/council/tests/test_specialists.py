import sys
from pathlib import Path

package_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(package_root))

from council.specialists import SpecialistLoader

def test_specialist_loader_loads_skill():
    loader = SpecialistLoader()
    coder_skill = loader.get_specialist("the-coder")
    assert coder_skill is not None, "the-coder skill package should exist"
    assert coder_skill.name == "the-coder"
    assert coder_skill.call_sign == "[THE CODER]"
    assert "description" in coder_skill.description.lower() or len(coder_skill.description) > 0
    assert len(coder_skill.instructions) > 50

def test_specialist_loader_handles_missing():
    loader = SpecialistLoader()
    missing = loader.get_specialist("non-existent-specialist-xyz")
    assert missing is None

def test_specialist_loader_lists_all_skills():
    loader = SpecialistLoader()
    specialists = loader.list_available_specialists()
    assert len(specialists) >= 15, f"Expected at least 15 specialists, got {len(specialists)}: {specialists}"
    assert "the-architect" in specialists
    assert "the-coder" in specialists
    assert "the-curator" in specialists
    assert "the-prover" in specialists
    assert "the-gatekeeper" in specialists

if __name__ == "__main__":
    test_specialist_loader_loads_skill()
    test_specialist_loader_handles_missing()
    test_specialist_loader_lists_all_skills()
    print("[PASS] test_specialists passed successfully")
