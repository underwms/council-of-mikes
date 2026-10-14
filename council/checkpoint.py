"""Managed native SQLite checkpoint resources."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

def get_checkpoint_db_path(context=None):
    if context is None:
        from council.runtime_context import resolve_context
        context = resolve_context()
    return context.memory_root / 'council_checkpoints.db'

@contextmanager
def managed_sqlite_checkpointer(*, context=None, db_path=None):
    path = Path(db_path) if db_path is not None else get_checkpoint_db_path(context)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    try:
        saver = SqliteSaver(connection, serde=JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=(), allowed_json_modules=()))
        saver.setup()
        yield saver
    finally:
        connection.close()

# Public factory is a context manager so callers cannot leak database handles.
create_sqlite_checkpointer = managed_sqlite_checkpointer
