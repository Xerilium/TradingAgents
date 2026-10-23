"""Startup recovery surface. Never opens a broker or mutates the damaged store."""

import hashlib
import json
import shutil
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from .recovery import active_paths, records, sha, validate_journal, writer_lease


def recovery_root(root):
    return root.with_name(root.name + ".recovery")


def startup_root(root):
    """Only an explicitly committed recovery marker selects the sibling generation."""
    sibling = recovery_root(root)
    marker = sibling / "recovered-for.json"
    if not marker.exists():
        return root
    value = json.loads(marker.read_text(encoding="utf-8"))
    if value.get("original_root") != str(root) or value.get("original_identity") != sha(str(root).casefold().encode()):
        raise ValueError("Recovery marker belongs to another application directory")
    active_paths(sibling, None)
    return sibling


def preflight(root, history):
    """Inspect a disposable copy, including WAL, without changing source journal bytes."""
    directory, _ = active_paths(root, history)
    database = directory / "desk.sqlite3"
    if database.exists():
        with tempfile.TemporaryDirectory(prefix="tradingagents-startup-") as temporary:
            target = Path(temporary) / "desk.sqlite3"
            for suffix in ("", "-wal"):
                source = database.with_name(database.name + suffix)
                if source.exists():
                    shutil.copyfile(source, target.with_name(target.name + suffix))
            records(target.resolve())
    elif (directory / "desk.json").exists():
        value = json.loads((directory / "desk.json").read_text(encoding="utf-8"))
        validate_journal({**value, "research_requests": value.get("research_requests", [])})


class RecoveryService:
    recovery_only = True
    browse_only = True

    def __init__(self, root, failure, runtime=None):
        self.original_root = root
        self.application_root = recovery_root(root)
        self.writer_lease = writer_lease(self.application_root)
        self.maintenance = threading.RLock()
        self.store = SimpleNamespace(revision=0, lock=self.maintenance)
        self.runtime = runtime
        self.instance_id, self.sequence = str(uuid4()), 0
        self.failure = "Saved application records could not be opened (" + type(failure).__name__ + ")."
        self.restart_required = False

    def health(self):
        return {"product": "TradingAgents", "application_identity": hashlib.sha256(str(self.original_root).casefold().encode()).hexdigest(),
                "service": "recovery_only", "browse_only": True, "execution_enabled": False,
                "engine": "not_started", "new_orders_blocked": True, "store": {"status": "unavailable", "message": self.failure},
                "original_directory": str(self.original_root), "recovery_directory": str(self.application_root),
                "native_cache_mode": "memory", "native_durability": {"state": "deferred", "durable_writes_confirmed": False},
                "restart_required": self.restart_required}

    def state(self, **_):
        self.sequence += 1
        return {"recovery_only": True, "health": self.health(), "server_instance_id": self.instance_id,
                "state_sequence": self.sequence, "execution_enabled": False}

    def close(self):
        self.writer_lease.close()
