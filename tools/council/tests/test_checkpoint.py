import sys
import tempfile
from pathlib import Path

package_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(package_root))

from council.state import CouncilState, MultiSpecialistPlan, TaskItem
from council.checkpoint import (
    get_checkpoint_db_path,
    save_checkpoint,
    load_checkpoint,
    list_checkpoints
)

def test_checkpoint_save_and_load():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_checkpoints.db"
        
        state = CouncilState(
            run_id="run-12345",
            task_input="Implement distance_unit filter",
            status="PLAN_REVIEW"
        )
        
        save_checkpoint(state.run_id, state, db_path=db_path)
        assert db_path.exists()
        
        restored = load_checkpoint("run-12345", db_path=db_path)
        assert restored is not None
        assert restored.run_id == "run-12345"
        assert restored.task_input == "Implement distance_unit filter"
        assert restored.status == "PLAN_REVIEW"
        
        # Test listing
        checkpoints = list_checkpoints(db_path=db_path)
        assert len(checkpoints) == 1
        assert checkpoints[0]["run_id"] == "run-12345"

def test_checkpoint_missing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_checkpoints.db"
        assert load_checkpoint("missing-run", db_path=db_path) is None

if __name__ == "__main__":
    test_checkpoint_save_and_load()
    test_checkpoint_missing()
    print("[PASS] test_checkpoint passed successfully")
