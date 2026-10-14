"""Verify central legacy engine paths and real-execution refusal without private writes."""
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "legacy/workspace/tools/council"))


class LegacyPathTests(unittest.TestCase):
    def test_real_execution_refuses_before_prompt_or_checkpoint(self):
        from council.cli import run_council_task
        with patch("council.cli.save_checkpoint") as checkpoint, patch("council.graph.save_checkpoint") as graph_checkpoint, patch("builtins.input") as prompt:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(2, run_council_task(prompt="Real task", auto_approve=True))
            checkpoint.assert_not_called()
            graph_checkpoint.assert_not_called()
            prompt.assert_not_called()

    def test_specialists_resolve_canonical_root_not_profile_alias(self):
        from council.specialists import SpecialistLoader
        with patch.dict(os.environ, {"COUNCIL_ROOT": str(ROOT)}):
            loader = SpecialistLoader()
            self.assertEqual((ROOT / "skills").resolve(), loader.skills_dir)
            self.assertEqual(15, len(loader.list_available_specialists()))
        with patch.dict(os.environ, {"COUNCIL_ROOT": str(ROOT / "missing")}):
            with self.assertRaises(ValueError):
                SpecialistLoader()

    def test_checkpoint_path_does_not_create_memory_during_resolution(self):
        from council.checkpoint import get_checkpoint_db_path
        scratch = ROOT / "work/legacy-path-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            cache = Path(temporary) / "memory"
            with patch.dict(os.environ, {"COUNCIL_ROOT": str(ROOT), "COUNCIL_MEMORY_ROOT": str(cache)}):
                with patch("pathlib.Path.mkdir") as mkdir:
                    result = get_checkpoint_db_path()
                mkdir.assert_not_called()
            self.assertEqual(cache / "council_checkpoints.db", result)
            self.assertFalse(cache.exists())


if __name__ == "__main__":
    unittest.main()
