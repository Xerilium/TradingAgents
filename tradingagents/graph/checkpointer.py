"""LangGraph checkpoint support for resumable analysis runs.

Per-ticker SQLite databases so concurrent tickers don't contend.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from pathlib import Path
from importlib.metadata import version

from langgraph.checkpoint.sqlite import SqliteSaver

from tradingagents.dataflows.symbols import safe_ticker_component


def desk_checkpoint_signature():
    """Reject continuation across changed execution code or persistence versions."""
    root = Path(__file__).resolve().parents[1]
    paths = [*root.glob("agents/**/*.py"), *root.glob("graph/*.py"),
             root / "integrations/maenifold.py", root / "web/service.py", root / "web/store.py"]
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    for name in ("langgraph", "langgraph-checkpoint", "langgraph-checkpoint-sqlite"):
        digest.update(f"{name}={version(name)}".encode())
    return digest.hexdigest()


def desk_checkpoint_exists(data_dir, ticker, identity):
    """Inspect an existing saver without creating or migrating a database."""
    path = Path(data_dir) / "checkpoints" / f"{safe_ticker_component(ticker).upper()}.db"
    if not path.is_file():
        return False
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            return connection.execute("SELECT 1 FROM checkpoints WHERE thread_id=? LIMIT 1", (identity,)).fetchone() is not None
    except sqlite3.Error:
        return False


def checkpoint_inventory(application, *, snapshot_root=None):
    """Inspect native saver schema/coverage, optionally using consistent SQLite backups.

    The caller holds application writer quiescence across journal and saver capture.
    Each SQLite snapshot is consistent; separate stores are not one transaction.
    """
    application = Path(application).resolve()
    directory = application / "cache" / "checkpoints"
    if (directory.is_symlink() or directory.parent.is_symlink()
            or not directory.resolve().is_relative_to(application)):
        raise ValueError("Checkpoint directory escapes the application boundary")
    # Exact schema published by the installed langgraph-checkpoint-sqlite 3.1.2.
    schemas = {
        "checkpoints": "CREATE TABLE checkpoints(thread_id TEXT NOT NULL,checkpoint_ns TEXT NOT NULL DEFAULT '',checkpoint_id TEXT NOT NULL,parent_checkpoint_id TEXT,type TEXT,checkpoint BLOB,metadata BLOB,PRIMARY KEY(thread_id,checkpoint_ns,checkpoint_id))",
        "writes": "CREATE TABLE writes(thread_id TEXT NOT NULL,checkpoint_ns TEXT NOT NULL DEFAULT '',checkpoint_id TEXT NOT NULL,task_id TEXT NOT NULL,task_path TEXT NOT NULL DEFAULT '',idx INTEGER NOT NULL,channel TEXT NOT NULL,type TEXT,value BLOB,PRIMARY KEY(thread_id,checkpoint_ns,checkpoint_id,task_id,idx))",
    }
    inventory = []
    for path in sorted(directory.glob("*.db")):
        if (path.is_symlink() or not path.resolve().is_relative_to(application)
                or path.stem != safe_ticker_component(path.stem).upper()):
            raise ValueError("Invalid native checkpoint database path")
        if snapshot_root is not None:
            destination = Path(snapshot_root) / "cache" / "checkpoints" / path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink() or not destination.resolve().is_relative_to(Path(snapshot_root).resolve()):
                raise ValueError("Native checkpoint snapshot target is not a new confined file")
            with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(destination)) as target:
                source.backup(target)
                target.commit()
                target.execute("PRAGMA journal_mode=DELETE")
            inspected = destination
        else:
            inspected = path
        with closing(sqlite3.connect(inspected.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("BEGIN")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Native checkpoint database integrity check failed")
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            actual = {name: sql for kind, name, sql in connection.execute(
                "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")
                if kind == "table" and name in schemas}
            objects = connection.execute("SELECT count(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchone()[0]
            if (user_version != 0 or objects != len(schemas) or set(actual) != set(schemas)
                    or any("".join(actual[name].split()).lower() != "".join(sql.split()).lower() for name, sql in schemas.items())):
                raise ValueError("Unsupported native SqliteSaver schema; checkpoint continuation was not exported")
            threads = [row[0] for row in connection.execute("SELECT thread_id FROM checkpoints UNION SELECT thread_id FROM writes ORDER BY thread_id")]
            roots = [row[0] for row in connection.execute("SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns='' ORDER BY thread_id")]
            if any(not isinstance(thread, str) for thread in threads):
                raise ValueError("Invalid native checkpoint thread identity")
            thread_hashes = {}
            for thread in threads:
                state = hashlib.sha256()
                for table in ("checkpoints", "writes"):
                    state.update(table.encode())
                    order = "checkpoint_ns,checkpoint_id" + (",task_id,idx" if table == "writes" else "")
                    for row in connection.execute(f"SELECT * FROM {table} WHERE thread_id=? ORDER BY {order}", (thread,)):
                        state.update((json.dumps([{"bytes": value.hex()} if isinstance(value, bytes) else value for value in row],
                                                 allow_nan=False, separators=(",", ":")) + "\n").encode())
                thread_hashes[thread] = state.hexdigest()
            inventory.append({"path": path.relative_to(application).as_posix(), "sqlite_user_version": user_version,
                "schema_sha256": hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest(),
                "state_sha256": hashlib.sha256(json.dumps(thread_hashes, sort_keys=True).encode()).hexdigest(),
                "thread_sha256": thread_hashes,
                "threads": threads, "root_threads": roots})
    return inventory


def _db_path(data_dir: str | Path, ticker: str) -> Path:
    """Return the SQLite checkpoint DB path for a ticker."""
    # Reject ticker values that would escape the checkpoints directory.
    safe = safe_ticker_component(ticker).upper()
    p = Path(data_dir) / "checkpoints"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{safe}.db"


def thread_id(ticker: str, date: str, signature: str = "") -> str:
    """Deterministic thread ID for a ticker+date pair.

    ``signature`` folds in graph-shape-affecting run choices so a resume under a
    different graph can't reuse this checkpoint (#1089); omitting it keeps the
    legacy ID.
    """
    base = f"{ticker.upper()}:{date}"
    if signature:
        base = f"{base}:{signature}"
    return hashlib.sha256(base.encode()).hexdigest()[:16]


@contextmanager
def get_checkpointer(data_dir: str | Path, ticker: str) -> Generator[SqliteSaver, None, None]:
    """Context manager yielding a SqliteSaver backed by a per-ticker DB."""
    db = _db_path(data_dir, ticker)
    conn = sqlite3.connect(str(db), check_same_thread=False)
    try:
        saver = SqliteSaver(conn)
        saver.setup()
        yield saver
    finally:
        conn.close()


def checkpoint_step(data_dir: str | Path, ticker: str, date: str, signature: str = "") -> int | None:
    """Return the step number of the latest checkpoint, or None if none exists."""
    db = _db_path(data_dir, ticker)
    if not db.exists():
        return None
    tid = thread_id(ticker, date, signature)
    with get_checkpointer(data_dir, ticker) as saver:
        config = {"configurable": {"thread_id": tid}}
        cp = saver.get_tuple(config)
        if cp is None:
            return None
        return cp.metadata.get("step")


def clear_all_checkpoints(data_dir: str | Path) -> int:
    """Remove all checkpoint databases. Returns the number of databases deleted.

    SQLite keeps committed state in ``-wal`` and ``-shm`` files beside the
    database, so deleting only the ``.db`` leaves a cleared checkpoint with data
    still on disk.
    """
    cp_dir = Path(data_dir) / "checkpoints"
    if not cp_dir.exists():
        return 0
    dbs = list(cp_dir.glob("*.db"))
    for db in dbs:
        for path in (db, *cp_dir.glob(f"{db.name}-*")):
            path.unlink(missing_ok=True)
    return len(dbs)


def clear_checkpoint(data_dir: str | Path, ticker: str, date: str, signature: str = "") -> None:
    """Remove checkpoint for a specific ticker+date by deleting the thread's rows."""
    db = _db_path(data_dir, ticker)
    if not db.exists():
        return
    tid = thread_id(ticker, date, signature)
    conn = sqlite3.connect(str(db))
    try:
        for table in ("writes", "checkpoints"):
            conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (tid,))
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
