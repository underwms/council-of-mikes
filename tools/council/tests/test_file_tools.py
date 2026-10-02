import sys
import tempfile
from pathlib import Path

package_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(package_root))

from council.tools.file_tools import FileTools

def test_file_read_write_patch_sandboxed():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        tools = FileTools(root)
        
        # Test write
        rel_path = "sub/test.txt"
        tools.write_file(rel_path, "hello world\nline 2\nline 3\nline 4")
        assert (root / rel_path).exists()
        
        # Test read range
        content = tools.read_file(rel_path, start_line=2, end_line=3)
        assert content == "line 2\nline 3"
        
        # Test patch success
        success = tools.patch_file(rel_path, "hello world", "hello mike")
        assert success is True
        assert "hello mike" in tools.read_file(rel_path)
        
        # Test patch collision failure (multiple matches)
        tools.write_file("sub/duplicate.txt", "abc\nabc\n")
        assert tools.patch_file("sub/duplicate.txt", "abc", "def") is False

def test_sandboxing_prevents_escape():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        tools = FileTools(root)
        
        try:
            tools.read_file("../../outside.txt")
            assert False, "Should have raised PermissionError"
        except PermissionError:
            pass

if __name__ == "__main__":
    test_file_read_write_patch_sandboxed()
    test_sandboxing_prevents_escape()
    print("[PASS] test_file_tools passed successfully")
