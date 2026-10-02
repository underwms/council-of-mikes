import os
import sys
from pathlib import Path

package_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(package_root))

from council.config import get_llm, resolve_model_provider

def test_resolve_model_provider_defaults():
    assert resolve_model_provider("gemini") == "gemini"
    assert resolve_model_provider("claude") == "claude"
    assert resolve_model_provider("gpt") == "gpt"

def test_resolve_model_provider_unknown():
    try:
        resolve_model_provider("unknown_vendor")
        assert False, "Should have raised ValueError for unknown model"
    except ValueError:
        pass

def test_get_llm_requires_api_key():
    # Ensure env var is unset for test
    old_val = os.environ.pop("GEMINI_API_KEY", None)
    try:
        try:
            get_llm("gemini")
            assert False, "Should have raised ValueError for missing GEMINI_API_KEY"
        except ValueError as e:
            assert "GEMINI_API_KEY" in str(e)
    finally:
        if old_val:
            os.environ["GEMINI_API_KEY"] = old_val

if __name__ == "__main__":
    test_resolve_model_provider_defaults()
    test_resolve_model_provider_unknown()
    test_get_llm_requires_api_key()
    print("[PASS] test_config passed successfully")
