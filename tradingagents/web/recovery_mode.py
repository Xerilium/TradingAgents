"""Startup recovery surface. Never opens a broker or mutates the damaged store."""

import base64
import hashlib
import json
import os
import shutil
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from .recovery import active_paths, invalidate_authority, records, retain_damaged_authority, sha, stage, validate_journal, writer_lease


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
        self.restore_candidates = {}
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

    def recovery_action(self, request):
        if self.restart_required:
            raise ValueError("Recovery has committed. Stop this recovery instance and restart with the original data directory.")
        action = request.get("action")
        if action == "preview":
            return stage(self, request.get("archive"))
        if action != "restore":
            raise ValueError("Choose archive preview or deliberate restore")
        # The sibling lease alone cannot establish that the original writer is stopped.
        with self.maintenance, writer_lease(self.original_root):
            return self.restore(request)

    def restore(self, request):
        token = request.get("token")
        if request.get("confirmation") != "RESTORE LOCAL RECORDS" or token not in self.restore_candidates:
            raise ValueError("Preview a backup archive, then type RESTORE LOCAL RECORDS to restore")
        candidate = self.restore_candidates[token]
        source = self.application_root / "recovery" / "staged" / candidate["id"]
        payload = (source / "original.zip").read_bytes()
        if sha(payload) != candidate["archive_sha256"]:
            raise ValueError("Reviewed archive changed; preview the original archive again")
        reviewed = stage(self, base64.b64encode(payload).decode())
        fresh = self.restore_candidates[reviewed["token"]]
        generation = fresh["id"]
        staged = self.application_root / "recovery" / "staged" / generation
        retained_commands = retain_damaged_authority(self, staged / "application" / "desk.sqlite3", staged / "application")
        invalidate_authority(staged / "application" / "desk.sqlite3", retained_commands=retained_commands,
            checkpoint_coverage=reviewed["checkpoint_coverage"], recovery_reference={
                "prior_state_backup": None, "original_store_preserved": True, "original_directory": str(self.original_root),
                "reason": "Damaged original store retained; local continuation history and a prior-state backup could not be established.",
                "archive_sha256": candidate["archive_sha256"]})
        if fresh["manifest"].get("history_included"):
            history_path = staged / "history" / "desk.json"
            history = json.loads(history_path.read_text(encoding="utf-8"))
            for name in ("proposals", "drafts"):
                for item in history.get(name, []):
                    item.update(approval=None, risk_approved=False, restored_requires_review=True)
            history_path.write_text(json.dumps(history, allow_nan=False), encoding="utf-8")
        records((staged / "application" / "desk.sqlite3").resolve())
        destination = self.application_root / "recovery" / "generations" / generation
        if not staged.resolve().is_relative_to(self.application_root.resolve()) or not destination.resolve().is_relative_to(self.application_root.resolve()):
            raise ValueError("Recovery destination escaped its dedicated directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        staged.rename(destination)
        self.commit_json("active-store.json", {"generation": generation, "has_history": fresh["manifest"].get("history_included", False)})
        self.commit_json("recovered-for.json", {"original_root": str(self.original_root),
            "original_identity": sha(str(self.original_root).casefold().encode()), "archive_sha256": candidate["archive_sha256"]})
        self.restart_required = True
        self.restore_candidates.clear()
        return {"restored": True, "restart_required": True, "generation": generation,
                "checkpoint_coverage": reviewed["checkpoint_coverage"], "checkpoint_warning": reviewed["checkpoint_warning"],
                "prior_state_backup": None, "original_store_preserved": True,
                "message": "Recovery committed in the sibling recovery directory. Original records remain untouched. Stop this instance and restart with the original data directory; fresh account reconciliation is required and execution stays disabled."}

    def commit_json(self, name, value):
        destination = self.application_root / name
        pending = self.application_root / (name + "." + str(uuid4()) + ".tmp")
        with pending.open("x", encoding="utf-8") as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, destination)

    def close(self):
        self.writer_lease.close()
