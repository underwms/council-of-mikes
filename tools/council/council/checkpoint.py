"""SQLite persistence and session checkpoint manager for Council Orchestrator."""
import os
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from council.state import CouncilState

def get_checkpoint_db_path() -> Path:
    """Returns the persistent SQLite database path in ephemeral user memory."""
    home = Path(os.path.expanduser("~"))
    username = os.environ.get("USERNAME") or os.environ.get("USER") or "default"
    db_dir = home / ".gemini" / "tmp" / username / "memory"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "council_checkpoints.db"

def _get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target_path = (db_path or get_checkpoint_db_path()).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS council_checkpoints (
                run_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    return conn

def save_checkpoint(run_id: str, state: CouncilState, db_path: Optional[Path] = None) -> None:
    """Saves serialized state into SQLite checkpoint database."""
    conn = _get_connection(db_path)
    try:
        state_json = state.model_dump_json()
        with conn:
            conn.execute("""
                INSERT INTO council_checkpoints (run_id, state_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(run_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = CURRENT_TIMESTAMP
            """, (run_id, state_json))
    finally:
        conn.close()

def load_checkpoint(run_id: str, db_path: Optional[Path] = None) -> Optional[CouncilState]:
    """Loads and deserializes state for a given run_id from SQLite."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT state_json FROM council_checkpoints WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return CouncilState.model_validate_json(row["state_json"])
    finally:
        conn.close()

def list_checkpoints(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Returns a list of all saved checkpoints with metadata."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT run_id, updated_at FROM council_checkpoints ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        return [{"run_id": r["run_id"], "updated_at": r["updated_at"]} for r in rows]
    finally:
        conn.close()

def create_sqlite_checkpointer(db_path: Optional[Path] = None):
    """Returns LangGraph native SqliteSaver when langgraph is available."""
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        conn = _get_connection(db_path)
        return SqliteSaver(conn)
    except ImportError:
        return None
