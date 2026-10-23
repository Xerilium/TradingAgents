"""Bounded application backups and staged, non-executing recovery generations."""

import base64
import copy
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import stat
import zipfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from importlib.metadata import version
from uuid import UUID, uuid4

from .app_database import ApplicationDatabase
from .config import DeskConfig

MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_FILES = 10000
SECRET_KEYS = {"api_key", "secret_key", "password", "access_token", "refresh_token", "authorization",
               "cookie", "csrf_token", "session_token", "credentials_file", "credential_path"}


class WriterBusy(RuntimeError):
    pass


def writer_lease(root):
    root.mkdir(parents=True, exist_ok=True)
    stream = (root / ".writer.lock").open("a+b")
    if stream.seek(0, 2) == 0:
        stream.write(b"\0")
        stream.flush()
    stream.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close()
        raise WriterBusy("Another application writer owns this data directory; close it before starting or migrating") from None
    return stream


def active_paths(root, history):
    pointer = root / "active-store.json"
    if not pointer.exists():
        return root, Path(history) if history else None
    record = json.loads(pointer.read_text(encoding="utf-8"))
    name = record["generation"]
    if str(UUID(name)) != name:
        raise ValueError("Invalid active recovery generation; original stores were retained")
    generation = (root / "recovery" / "generations" / name).resolve()
    if not generation.is_relative_to(root.resolve()) or generation.is_symlink():
        raise ValueError("Recovery generation escapes the application boundary")
    if not (generation / "application" / "desk.sqlite3").is_file() or record["has_history"] and not (generation / "history" / "desk.json").is_file():
        raise ValueError("Active recovery generation is incomplete; preserve original stores and restore a retained backup instead of creating empty records")
    return generation / "application", generation / "history" if record["has_history"] else None


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def references(value, *, native_reconstruction=False):
    if isinstance(value, dict):
        if SECRET_KEYS & {str(k).lower() for k in value}:
            raise ValueError("Application record contains a credential field; backup excluded rather than exporting it")
        if "path" in value and "sha256" in value:
            name = value["path"]
            if (not isinstance(name, str) or (not re.fullmatch(r"reports/(?:[0-9a-f-]{36}|native-recovery|native-targeted-orders)/[A-Za-z0-9_.-]+", name)
                    and not (native_reconstruction and re.fullmatch(r"reports/native-reconstruction/execution-[0-9a-f-]{36}\.json", name)))
                    or not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"])):
                raise ValueError("Unsupported artifact reference; backup is incomplete")
            yield name, value["sha256"]
        for item in value.values():
            yield from references(item, native_reconstruction=native_reconstruction)
    elif isinstance(value, list):
        for item in value:
            yield from references(item, native_reconstruction=native_reconstruction)


def artifacts(root, value):
    root = root.resolve()
    queue, seen, total = list(references(value)), {}, 0
    while queue:
        relative, expected = queue.pop()
        if relative in seen:
            if seen[relative] != expected:
                raise ValueError("Artifact identity has conflicting hashes")
            continue
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError("Referenced immutable artifact is missing or escapes its backup boundary: " + relative)
        payload = path.read_bytes()
        total += len(payload)
        if sha(payload) != expected:
            raise ValueError("Referenced immutable artifact hash differs: " + relative)
        if total > MAX_EXPANDED or len(seen) >= MAX_FILES:
            raise ValueError("Referenced evidence exceeds the supported backup boundary")
        seen[relative] = expected
        if relative.endswith(".json"):
            queue.extend(references(json.loads(payload)))
        yield relative, payload


def records(database, resolve_artifact=None):
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA trusted_schema=OFF")
        if connection.execute("PRAGMA user_version").fetchone()[0] != ApplicationDatabase.VERSION:
            raise ValueError("Backup database schema version is unsupported")
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Backup database integrity check failed")
        for kind, name in connection.execute("SELECT type,name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"):
            if kind != "table" or name not in {"app_records", "migration_info"}:
                raise ValueError("Backup contains unexpected database objects")
        schemas = {"app_records": "CREATE TABLE app_records(name TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL)",
                   "migration_info": "CREATE TABLE migration_info(version INTEGER PRIMARY KEY, source_sha256 TEXT, backup_name TEXT, migrated_at TEXT NOT NULL)"}
        for name, sql in connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            if "".join(sql.split()).lower() != "".join(schemas[name].split()).lower():
                raise ValueError("Restored database schema does not match its declared version")
        rows = connection.execute("SELECT name,revision,payload FROM app_records").fetchall()
    result = {}
    for name, revision, payload in rows:
        if name not in {"journal", "workspace", "investor", "reporting", "commands", "attention", "attention_observations", "market_history", "stock_evidence", "discovery"} or type(revision) is not int or revision < 1:
            raise ValueError("Unsupported application record scope or revision")
        result[name] = json.loads(payload)
    validate_journal(result.get("journal"))
    from .record_integrity import validate
    validate(result, resolve_artifact)
    if "discovery" in result:
        from .market_discovery import validate as validate_discovery
        validate_discovery(result["discovery"], result.get("workspace"), resolve_artifact)
    workspace = result.get("workspace")
    if workspace:
        from .workspace import lists, preferences, saved_screens
        lists(workspace["watchlists"])
        preferences(workspace["preferences"])
        if "saved_screens" in workspace:
            saved_screens(workspace["saved_screens"])
        if not isinstance(workspace["notes"], dict):
            raise ValueError("Invalid saved investor notes")
    investor = result.get("investor")
    if investor and (not isinstance(investor.get("proposals"), list) or not isinstance(investor.get("policy"), dict)):
        raise ValueError("Invalid saved investor records")
    reporting = result.get("reporting")
    if reporting and (not isinstance(reporting.get("entries"), dict) or not isinstance(reporting.get("collections"), list)):
        raise ValueError("Invalid saved journal/reporting records")
    return result


def validate_journal(journal):
    if not isinstance(journal, dict):
        raise ValueError("Backup journal is missing")
    DeskConfig.model_validate(journal["config"])
    for collection in ("runs", "research_requests"):
        if not isinstance(journal.get(collection), list):
            raise ValueError("Invalid saved journal collection")
        for record in journal[collection]:
            if str(UUID(record["id"])) != record["id"]:
                raise ValueError("Invalid saved evidence owner identity")


def checkpoint_coverage(journal, metadata, *, current=False, current_journal=None, current_databases=None, current_generation=None):
    from tradingagents.graph.checkpointer import desk_checkpoint_signature
    from tradingagents.dataflows.symbols import safe_ticker_component
    metadata = metadata or {}
    versions = {name: version(name) for name in ("langgraph", "langgraph-checkpoint", "langgraph-checkpoint-sqlite")}
    signature = desk_checkpoint_signature() if current else metadata.get("source_signature")
    available = {item["path"].removeprefix("application/"): item["root_threads"] for item in metadata.get("databases", [])}
    archived = {item["path"].removeprefix("application/"): item["thread_sha256"] for item in metadata.get("databases", [])}
    present = {item["path"]: item["thread_sha256"] for item in current_databases or []}
    coverage = []
    for run in journal["runs"]:
        for symbol in run["symbols"]:
            continuation = run.get("continuation", {})
            result = next((item for item in run["results"] if item["symbol"] == symbol), {})
            checkpoint = result.get("continuation", {})
            thread = checkpoint.get("thread_id")
            status, reason = "included", "Native root checkpoint retained; explicit continuation eligibility review is still required."
            if continuation.get("version") != 1:
                status, reason = "legacy", "This run predates native desk continuation."
            elif not thread or thread not in available.get(f"cache/checkpoints/{safe_ticker_component(symbol).upper()}.db", []):
                status, reason = "missing", "No matching native root checkpoint was retained for this symbol."
            elif continuation.get("source_signature") != signature or current and metadata.get("versions") != versions:
                status, reason = "incompatible", "Execution source or installed persistence versions differ from the saved run."
            elif (run.get("cancel_requested_at") or run["status"] in {"cancelled", "cancelling"}
                    or continuation.get("blocked_reason") or any(effect["stateful"] and effect["outcome"] != "confirmed" for effect in checkpoint.get("effects", {}).values())
                    or any(row.get("status") == "pending" for source in result.get("social_sentiment", {}).get("sources", {}).values() for row in source.get("posts", []))):
                status, reason = "blocked", "Retained cancellation or uncertain external effects prevent automatic continuation."
            budget = checkpoint.get("social_budget", {})
            observed_at = datetime.now(UTC).timestamp() if current else datetime.fromisoformat(metadata["captured_at"]).timestamp() if metadata else 0
            if status == "included" and result.get("social_sentiment", {}).get("status") != "completed" and (
                    budget.get("remaining") == 0 or budget.get("expires_at", float("inf")) <= observed_at):
                status, reason = "blocked", "The original social screening budget is exhausted or expired."
            if current and status == "included":
                local = next((item for item in (current_journal or {}).get("runs", []) if item["id"] == run["id"]), None)
                keys = ("trade_date", "config", "account_context", "portfolio_evidence", "continuation", "results",
                        "cancel_requested_at", "source_evidence", "gateway_evidence", "jev_evidence")
                path = f"cache/checkpoints/{safe_ticker_component(symbol).upper()}.db"
                if current_generation != metadata.get("store_generation") or local is None:
                    status, reason = "blocked", "Same-generation local research continuity is unavailable; later external effects cannot be excluded."
                elif (any(run.get(key) != local.get(key) for key in keys)
                      or archived.get(path, {}).get(thread) != present.get(path, {}).get(thread)):
                    status, reason = "blocked", "Local research state advanced or differs from this archive; later effects, cancellation or budget use cannot be erased."
            coverage.append({"run_id": run["id"], "symbol": symbol, "thread_id": thread, "status": status, "reason": reason})
    return coverage


def backup(service):
    identity = str(uuid4())
    directory = service.application_root / "recovery" / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / (identity + ".zip")
    staged_database = directory / (identity + ".sqlite3")
    checkpoint_staging = directory / (identity + "-checkpoints")
    try:
        files = {}
        # Capture one generation; immutable artifact reads and compression need no writer lock.
        with service.maintenance, service.store.lock, service.store.database.transaction():
            if (any(not future.done() for future in service.research_futures | service.data_jobs.futures)
                    or any(run["status"] in {"queued", "running", "cancelling"} for run in service.store.data["runs"])):
                raise ValueError("Research/data writers are active. Wait for them to finish before backup")
            with closing(sqlite3.connect(service.store.database.path)) as source, closing(sqlite3.connect(staged_database)) as target:
                source.backup(target)
                target.commit()
            journal_records = records(staged_database.resolve())
            files["application/desk.sqlite3"] = staged_database.read_bytes()
            from tradingagents.graph.checkpointer import checkpoint_inventory, desk_checkpoint_signature
            checkpoint_staging.mkdir(exist_ok=False)
            inventory = checkpoint_inventory(service.store.directory, snapshot_root=checkpoint_staging)
            for item in inventory:
                files["application/" + item["path"]] = (checkpoint_staging / item["path"]).read_bytes()
                item["path"] = "application/" + item["path"]
            checkpoints = {"version": 1, "captured_at": datetime.now(UTC).isoformat(),
                "consistency": "Sequential consistent SQLite snapshots under application research/data writer quiescence; not a cross-store atomic transaction.",
                "versions": {name: version(name) for name in ("langgraph", "langgraph-checkpoint", "langgraph-checkpoint-sqlite")},
                "source_signature": desk_checkpoint_signature(), "databases": inventory}
            checkpoints["store_generation"] = sha(str(service.store.directory.resolve()).encode())
            checkpoints["coverage"] = checkpoint_coverage(journal_records["journal"], checkpoints)
            scopes = [("application", service.store.directory, journal_records)]
            history_raw = None
            history_json_source = False
            history_path = None
            if service.history_directory:
                history_path = service.history_directory / "desk.json"
                if (service.history_directory / "desk.sqlite3").exists():
                    # Export the read-only history snapshot as data, without recovery writes.
                    history_raw = json.dumps(service.store.read_existing(service.history_directory), allow_nan=False).encode()
                else:
                    history_raw = history_path.read_bytes()
                    history_json_source = True
                history = json.loads(history_raw)
                validate_journal(history)
                files["history/desk.json"] = history_raw
                scopes.append(("history", service.history_directory, history))
            application_directory = service.store.directory
        for scope, root, value in scopes:
            for relative, payload in artifacts(root, value):
                files[scope + "/" + relative] = payload
        for name in ("constituents.csv", "sp500-constituents.csv"):
            path = application_directory / name
            if path.is_file() and not path.is_symlink():
                files["application/" + name] = path.read_bytes()
        if history_json_source and history_path.read_bytes() != history_raw:
            raise ValueError("External history changed during backup; stop its writers before retrying")
        if len(files) > MAX_FILES - 1 or sum(map(len, files.values())) > MAX_EXPANDED:
            raise ValueError("Application backup exceeds the supported size/count boundary")
        manifest = {"format": "tradingagents-application-backup", "version": 1,
                    "database_version": ApplicationDatabase.VERSION, "created_at": datetime.now(UTC).isoformat(),
                    "records": sorted(journal_records), "history_included": history_raw is not None,
                    "credentials_included": False, "broker_history_restorable": False,
                     "native_cache_included": False, "native_durability": "in_memory",
                    "research_checkpoints": checkpoints,
                    "files": {name: {"sha256": sha(payload), "bytes": len(payload)} for name, payload in files.items()}}
        if len(json.dumps(manifest, allow_nan=False).encode()) > 2 * 1024 * 1024:
            raise ValueError("Checkpoint coverage exceeds the supported restore manifest boundary")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, allow_nan=False))
            for name, payload in files.items():
                archive.writestr(name, payload)
        payload = buffer.getvalue()
        if len(payload) > MAX_ARCHIVE:
            raise ValueError("Compressed application backup exceeds 64 MiB")
        with destination.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        for suffix in ("", "-wal", "-shm"):
            staged_database.with_name(staged_database.name + suffix).unlink(missing_ok=True)
        if checkpoint_staging.exists():
            if checkpoint_staging.is_symlink() or not checkpoint_staging.resolve().is_relative_to(directory.resolve()):
                raise ValueError("Checkpoint snapshot cleanup escaped the backup staging boundary")
            shutil.rmtree(checkpoint_staging)
    return {"id": identity, "sha256": sha(payload), "bytes": len(payload), "manifest": manifest,
            "checkpoint_coverage": checkpoints["coverage"],
            "checkpoint_warning": "Checkpoint inclusion does not authorize resumption; original budgets, cancellation and uncertain effects remain binding. Separate SQLite stores are not captured atomically."}


def stage(service, encoded):
    if not isinstance(encoded, str) or len(encoded) > (MAX_ARCHIVE * 4 // 3 + 8):
        raise ValueError("Restore upload exceeds 64 MiB")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except ValueError:
        raise ValueError("Invalid restore archive encoding") from None
    if len(payload) > MAX_ARCHIVE:
        raise ValueError("Restore archive exceeds 64 MiB")
    identity = str(uuid4())
    root = service.application_root / "recovery" / "staged" / identity
    root.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = archive.infolist()
        if len(members) > MAX_FILES or len({m.filename for m in members}) != len(members) or sum(m.file_size for m in members) > MAX_EXPANDED:
            raise ValueError("Restore archive exceeds size/count limits or repeats a path")
        for item in members:
            name, mode = item.filename, item.external_attr >> 16
            if item.is_dir() or item.flag_bits & 1 or stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                raise ValueError("Restore archive contains encrypted, linked or non-file entries")
            if "\\" in name or ":" in name or PurePosixPath(name).is_absolute() or any(p in {"", ".", ".."} for p in name.split("/")):
                raise ValueError("Restore archive contains an unsafe path")
            allowed = name in {"manifest.json", "application/desk.sqlite3", "history/desk.json",
                               "application/constituents.csv", "application/sp500-constituents.csv"}
            allowed = allowed or re.fullmatch(r"application/cache/checkpoints/[A-Z0-9_.-]+\.db", name)
            if not allowed and not re.fullmatch(r"(?:application|history)/reports/(?:[0-9a-f-]{36}|native-recovery|native-targeted-orders)/[A-Za-z0-9_.-]+", name):
                raise ValueError("Restore archive contains files outside application records and evidence")
        entry = archive.getinfo("manifest.json")
        if entry.file_size > 2 * 1024 * 1024:
            raise ValueError("Restore manifest is oversized")
        manifest = json.loads(archive.read(entry))
        if (manifest.get("format") != "tradingagents-application-backup" or manifest.get("version") != 1
                or manifest.get("database_version") != ApplicationDatabase.VERSION
                or manifest.get("credentials_included") is not False):
            raise ValueError("Unsupported backup format or credential boundary")
        expected = manifest["files"]
        if set(expected) != {m.filename for m in members} - {"manifest.json"}:
            raise ValueError("Manifest does not exactly describe the archive")
        for item in members:
            content = archive.read(item)
            if item.filename != "manifest.json" and (len(content) != expected[item.filename]["bytes"] or sha(content) != expected[item.filename]["sha256"]):
                raise ValueError("Restore archive checksum differs from its manifest")
            path = root / item.filename
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(content)
    values = records((root / "application" / "desk.sqlite3").resolve())
    from tradingagents.graph.checkpointer import checkpoint_inventory
    checkpoints = manifest.get("research_checkpoints")
    checkpoint_files = {name for name in manifest["files"] if name.startswith("application/cache/checkpoints/")}
    if checkpoints is not None:
        if (not isinstance(checkpoints, dict) or checkpoints.get("version") != 1
                or not isinstance(checkpoints.get("databases"), list) or not isinstance(checkpoints.get("coverage"), list)
                or not isinstance(checkpoints.get("versions"), dict)
                or set(checkpoints["versions"]) != {"langgraph", "langgraph-checkpoint", "langgraph-checkpoint-sqlite"}
                or any(not isinstance(value, str) for value in checkpoints["versions"].values())
                or not isinstance(checkpoints.get("source_signature"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", checkpoints["source_signature"])
                or not isinstance(checkpoints.get("store_generation"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", checkpoints["store_generation"])
                or not isinstance(checkpoints.get("captured_at"), str) or not isinstance(checkpoints.get("consistency"), str)):
            raise ValueError("Unsupported research checkpoint manifest")
        datetime.fromisoformat(checkpoints["captured_at"])
        inventory = checkpoint_inventory(root / "application")
        for item in inventory:
            item["path"] = "application/" + item["path"]
        if (inventory != checkpoints["databases"] or {item["path"] for item in inventory} != checkpoint_files
                or checkpoint_coverage(values["journal"], checkpoints) != checkpoints["coverage"]):
            raise ValueError("Native checkpoint schema, thread coverage or declared run coverage differs")
    elif checkpoint_files:
        raise ValueError("Native checkpoint files are missing their schema and coverage manifest")
    with service.maintenance, service.store.lock:
        local = None
        local_databases = None
        if not getattr(service, "recovery_only", False) and not any(not future.done() for future in service.research_futures | service.data_jobs.futures):
            try:
                local = service.store.database.read("journal")["data"]
                if not isinstance(local, dict):
                    local = None
                local_databases = checkpoint_inventory(service.store.directory)
            except (OSError, ValueError, KeyError, sqlite3.Error):
                local = None
        coverage = checkpoint_coverage(values["journal"], checkpoints, current=True, current_journal=local,
            current_databases=local_databases,
            current_generation=None if getattr(service, "recovery_only", False) else sha(str(service.store.directory.resolve()).encode()))
    checkpoint_warning = ("Legacy backup contains no native research checkpoint coverage; interrupted research cannot continue."
                          if checkpoints is None else "Checkpoint bytes do not guarantee continuation eligibility. Older/foreign generations or changed local lineage stay blocked; original budgets/cancellation and uncertain effects remain binding. Separate snapshots are not cross-store atomic.")
    scopes = [("application", values)]
    if manifest.get("history_included"):
        history = json.loads((root / "history" / "desk.json").read_text(encoding="utf-8"))
        validate_journal(history)
        scopes.append(("history", history))
    for scope, value in scopes:
        for relative, _ in artifacts(root / scope, value):
            if scope + "/" + relative not in manifest["files"]:
                raise ValueError("Referenced evidence was omitted from the restore manifest")
    if manifest["records"] != sorted(values):
        raise ValueError("Backup record scope differs from the database")
    # Preserve the uploaded authority exactly; sanitization affects only a later staged copy.
    (root / "original.zip").write_bytes(payload)
    token = str(uuid4())
    with service.store.lock:
        service.restore_candidates[token] = {"id": identity, "archive_sha256": sha(payload),
                                             "store_revision": service.store.revision, "manifest": manifest}
    return {"token": token, "archive_sha256": sha(payload), "manifest": manifest,
            "checkpoint_coverage": coverage, "checkpoint_warning": checkpoint_warning,
            "warning": "Restores local records only. Broker history is unchanged; approvals will be invalidated and fresh reconciliation is required."}


def invalidate_authority(database, *, retained_commands=(), checkpoint_coverage=(), recovery_reference=None):
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA trusted_schema=OFF")
        for name, payload in connection.execute("SELECT name,payload FROM app_records").fetchall():
            value = json.loads(payload)
            if name == "journal":
                value["paused"] = True
                for run in value["runs"]:
                    limitation = next((item for item in checkpoint_coverage if item["run_id"] == run["id"] and item["status"] != "included"), None)
                    if limitation and run.get("continuation"):
                        run["continuation"].setdefault("blocked_reason", "Restored checkpoint limitation: " + limitation["reason"])
                        if recovery_reference is not None:
                            run["continuation"].setdefault("recovery_limits", []).append({"at": datetime.now(UTC).isoformat(),
                                "limitations": [item for item in checkpoint_coverage if item["run_id"] == run["id"] and item["status"] != "included"],
                                **recovery_reference})
                collections = ("proposals", "drafts")
            elif name == "investor":
                collections = ("proposals", "baskets")
            elif name == "commands":
                value.setdefault("new_orders_blocked", False)
                value.update(recovery_required=True, recovery_reason="Restored authority requires fresh identity reconciliation")
                for authorization in value.get("exercise_authorizations", {}).values():
                    authorization["revocation"] = {"at": datetime.now(UTC).isoformat(), "reason": "Restored exercise authorization is invalid"}
                for group in value.get("basket_executions", {}).values():
                    group["state"] = "review_required"
                for identity in value["approvals"]:
                    value["revocations"][identity] = {"at": datetime.now(UTC).isoformat(), "reason": "Restored approvals have no executable authority"}
                for command in value["commands"].values():
                    if command["id"] not in retained_commands:
                        for target in (command, command.get("pending_action") or {}):
                            if target.get("transport_attempt") == {"version": 1, "state": "not_started"}:
                                target["transport_attempt"] = {"version": 1, "state": "restored_unproven",
                                    "reason": "A snapshot predates possible later transport; no current durable boundary was retained"}
                    if command["state"] not in {"not_sent", "filled", "canceled", "rejected", "expired"}:
                        command["state"] = "outcome_unknown"
                collections = ()
            elif name == "attention_observations":
                monitor = value["monitor"]
                monitor["gaps"].append({"from": monitor.get("last_evaluated_at"), "to": datetime.now(UTC).isoformat(), "reason": "Restored monitoring history; intervening interval was not observed"})
                monitor["state"] = "awaiting_observation"
                for profile in value.get("browser_profiles", {}).values():
                    profile["enabled"] = False
                collections = ()
            else:
                continue
            for collection in collections:
                for item in value.get(collection, []):
                    item.update(approval=None, risk_approved=False, conditions_stale=True,
                                impact_review_valid=False, restored_requires_review=True)
                    item.setdefault("history", []).append({"action": "restored_authority_invalidated", "at": datetime.now(UTC).isoformat()})
            connection.execute("UPDATE app_records SET payload=?,revision=revision+1,updated_at=? WHERE name=?",
                               (ApplicationDatabase.encode(value), datetime.now(UTC).isoformat(), name))


def retain_command_authority(service, database, destination, *, allow_missing_artifacts=False):
    """A past application snapshot cannot erase later possible broker commitments."""
    from .admission import DEFAULT, ACTIVE
    from decimal import Decimal
    current = service.store.database.read("commands", DEFAULT)["data"]
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA trusted_schema=OFF")
        row = connection.execute("SELECT payload FROM app_records WHERE name='commands'").fetchone()
        restored = json.loads(row[0]) if row else copy.deepcopy(DEFAULT)
        if current.get("authority_history_incomplete"):
            restored["authority_history_incomplete"] = True
        for key in ("approvals", "exercise_authorizations"):
            for identity, value in current.get(key, {}).items():
                if identity in restored.get(key, {}) and key == "approvals" and restored[key][identity] != value:
                    raise ValueError("Conflicting immutable approval identity in recovery")
                restored.setdefault(key, {})[identity] = copy.deepcopy(value)
        restored["revocations"].update(current["revocations"])
        for identity, live in current["commands"].items():
            old = restored["commands"].get(identity)
            value = copy.deepcopy(live)
            if old and (old["terms_sha256"] != live["terms_sha256"] or old["client_order_id"] != live["client_order_id"]):
                raise ValueError("Conflicting durable command identity in recovery")
            if old and old != live:
                value["state"] = "outcome_unknown"
                value["cash_commitment"] = (None if old["cash_commitment"] is None or live["cash_commitment"] is None
                    else str(max(Decimal(old["cash_commitment"]), Decimal(live["cash_commitment"]))))
                value["remaining_quantity"] = str(max(Decimal(old["remaining_quantity"]), Decimal(live["remaining_quantity"])))
                for key in ("broker_order_ids", "fill_ids", "event_ids"):
                    value[key] = list(dict.fromkeys(old.get(key, []) + live.get(key, [])))
                value["timeline"] = old["timeline"] + [item for item in live["timeline"] if item not in old["timeline"]]
                for event_id, delivery in old.get("native_deliveries", {}).items():
                    value.setdefault("native_deliveries", {}).setdefault(event_id, delivery)
                value["timeline"].append({"at": datetime.now(UTC).isoformat(), "state": "outcome_unknown",
                    "reason": "Different recovery snapshots retain both sets of command evidence; fresh reconciliation required"})
            if value["state"] in ACTIVE or value.get("native_pending_commitment"):
                pending = value.setdefault("native_pending_commitment", {})
                cap = Decimal(value["price_cap"]) if value.get("price_cap") is not None else None
                total = Decimal(value["terms"]["quantity"])
                known_fee = Decimal(value["fee_commitment"]) if value.get("fee_commitment") is not None else None
                full_cash = (None if value["side"] == "BUY" and cap is None else
                    sum(amount for amount in (total * cap if value["side"] == "BUY" else Decimal(0), known_fee) if amount is not None))
                prior_cash = pending.get("cash_commitment", "0")
                pending["cash_commitment"] = None if full_cash is None or prior_cash is None else str(max(full_cash, Decimal(prior_cash)))
                pending["remaining_quantity"] = str(max(total, Decimal(pending.get("remaining_quantity", "0"))))
            restored["commands"][identity] = value
        restored.setdefault("basket_executions", {}).update(copy.deepcopy(current.get("basket_executions", {})))
        restored["new_orders_blocked"] = current.get("new_orders_blocked", False)
        restored.setdefault("control_history", []).extend(copy.deepcopy(current.get("control_history", [])))
        for relative, expected in references(current):
            try:
                _, payload = next(artifacts(service.store.directory, {"path": relative, "sha256": expected}))
            except (OSError, ValueError):
                if not allow_missing_artifacts:
                    raise
                restored["authority_history_incomplete"] = True
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.read_bytes() != payload:
                    raise ValueError("Conflicting immutable command receipt during restore")
            else:
                with target.open("xb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
        if row:
            connection.execute("UPDATE app_records SET payload=?,revision=revision+1,updated_at=? WHERE name='commands'",
                (ApplicationDatabase.encode(restored), datetime.now(UTC).isoformat()))
        else:
            connection.execute("INSERT INTO app_records(name,revision,payload,updated_at) VALUES('commands',1,?,?)",
                (ApplicationDatabase.encode(restored), datetime.now(UTC).isoformat()))
    return set(current["commands"])


def retain_damaged_authority(service, database, destination):
    """Recover readable command authority independently of an invalid research journal."""
    from .admission import DEFAULT
    from .record_integrity import validate
    from types import SimpleNamespace
    pause_choice = None
    try:
        directory, _ = active_paths(service.original_root, None)
        source = (directory / "desk.sqlite3").resolve()
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as connection:
            connection.execute("PRAGMA trusted_schema=OFF")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Original authority integrity is unproven")
            schema = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='app_records'").fetchone()
            expected = "CREATE TABLE app_records(name TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL)"
            if not schema or "".join(schema[0].split()).lower() != "".join(expected.split()).lower():
                raise ValueError("Original authority schema differs")
            row = connection.execute("SELECT payload FROM app_records WHERE name='commands'").fetchone()
            if row and len(row[0].encode()) > 16 * 1024 * 1024:
                raise ValueError("Original authority exceeds the recovery boundary")
            commands = json.loads(row[0]) if row else copy.deepcopy(DEFAULT)
        if isinstance(commands, dict) and type(commands.get("new_orders_blocked")) is bool:
            pause_choice = commands["new_orders_blocked"]
        validate({"commands": commands})
        snapshot = SimpleNamespace(store=SimpleNamespace(directory=directory,
            database=SimpleNamespace(read=lambda *args: {"data": commands})))
        return retain_command_authority(snapshot, database, destination, allow_missing_artifacts=True)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        with closing(sqlite3.connect(database)) as connection, connection:
            row = connection.execute("SELECT payload FROM app_records WHERE name='commands'").fetchone()
            value = json.loads(row[0]) if row else copy.deepcopy(DEFAULT)
            value["new_orders_blocked"] = pause_choice if pause_choice is not None else value.get("new_orders_blocked", False)
            value.update(authority_history_incomplete=True, recovery_required=True,
                recovery_reason="Original authority is unreadable; possible later commands remain unresolved. Broker absence cannot prove non-dispatch.")
            connection.execute("INSERT INTO app_records(name,revision,payload,updated_at) VALUES('commands',1,?,?) "
                "ON CONFLICT(name) DO UPDATE SET payload=excluded.payload,revision=app_records.revision+1,updated_at=excluded.updated_at",
                (ApplicationDatabase.encode(value), datetime.now(UTC).isoformat()))
        return set()


def restore(service, token, confirmation):
    with service.maintenance, service.store.lock:
        if (any(not future.done() for future in service.research_futures | service.data_jobs.futures)
                or any(run["status"] in {"queued", "running", "cancelling"} for run in service.store.data["runs"])):
            raise ValueError("Research/data writers must be quiescent before restore")
        return _restore_quiescent(service, token, confirmation)


def _restore_quiescent(service, token, confirmation):
    if confirmation != "RESTORE LOCAL RECORDS" or token not in service.restore_candidates:
        raise ValueError("Preview the archive and type RESTORE LOCAL RECORDS to confirm")
    candidate = service.restore_candidates[token]
    if service.store.database.read("journal")["revision"] != candidate["store_revision"]:
        raise ValueError("Application journal changed after restore preview; preview the archive again")
    source = service.application_root / "recovery" / "staged" / candidate["id"]
    payload = (source / "original.zip").read_bytes()
    if sha(payload) != candidate["archive_sha256"]:
        raise ValueError("Staged backup changed; preview the original archive again")
    # Re-stage and revalidate at commit time, rather than trusting editable staging files.
    reviewed = stage(service, base64.b64encode(payload).decode())
    fresh = service.restore_candidates.pop(reviewed["token"])
    generation = fresh["id"]
    staged = service.application_root / "recovery" / "staged" / generation
    retained_commands = retain_command_authority(service, staged / "application" / "desk.sqlite3", staged / "application")
    invalidate_authority(staged / "application" / "desk.sqlite3", retained_commands=retained_commands,
                         checkpoint_coverage=reviewed["checkpoint_coverage"])
    if candidate["manifest"].get("history_included"):
        history_path = staged / "history" / "desk.json"
        history = json.loads(history_path.read_text(encoding="utf-8"))
        for collection in ("proposals", "drafts"):
            for item in history.get(collection, []):
                item.update(approval=None, risk_approved=False, restored_requires_review=True)
        history_path.write_text(json.dumps(history, allow_nan=False), encoding="utf-8")
    from .store import DeskStore
    restored_store = DeskStore(staged / "application", service.store.data["config"])
    restored_history = DeskStore.read_existing(staged / "history") if candidate["manifest"].get("history_included") else {"runs": [], "drafts": []}
    retained = backup(service)
    with restored_store.lock:
        for run in restored_store.data["runs"]:
            limits = [item for item in reviewed["checkpoint_coverage"] if item["run_id"] == run["id"] and item["status"] != "included"]
            if limits and run.get("continuation"):
                run["continuation"].setdefault("recovery_limits", []).append({"at": datetime.now(UTC).isoformat(),
                    "limitations": limits, "prior_state_backup": retained["id"], "archive_sha256": candidate["archive_sha256"]})
        restored_store.save()
    service.runtime.stop()
    # Directory movement is confined to these two server-owned recovery subdirectories.
    destination = service.application_root / "recovery" / "generations" / generation
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not staged.resolve().is_relative_to(service.application_root.resolve()) or not destination.resolve().is_relative_to(service.application_root.resolve()):
        raise ValueError("Recovery generation escaped the application boundary")
    staged.rename(destination)
    restored_store.directory = destination / "application"
    restored_store.path = restored_store.directory / "desk.json"
    restored_store.database.path = restored_store.directory / "desk.sqlite3"
    pointer = service.application_root / "active-store.json"
    pending = pointer.with_name("active-store-" + generation + ".tmp")
    with pending.open("x", encoding="utf-8") as stream:
        json.dump({"generation": generation, "has_history": candidate["manifest"].get("history_included", False)}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, pointer)
    service.store, service.history = restored_store, restored_history
    service.admission.database = restored_store.database
    service.attention_monitor.database = restored_store.database
    service.runtime.authority_database = restored_store.database.path.resolve()
    service.history_directory = destination / "history" if candidate["manifest"].get("history_included") else None
    service.history_error = None
    service.company_names = {}
    import csv
    for filename in ("constituents.csv", "sp500-constituents.csv"):
        try:
            with (restored_store.directory / filename).open(encoding="utf-8-sig", newline="") as stream:
                service.company_names.update({row["Symbol"]: row["Company"] for row in csv.DictReader(stream)})
        except (OSError, KeyError, csv.Error):
            continue
    service.chart_cache.clear()
    service.runtime.configure(service.store.data["config"]["universe"])
    service.restore_candidates.clear()
    return {"restored": True, "generation": generation, "prior_state_backup": retained["id"],
            "checkpoint_coverage": reviewed["checkpoint_coverage"], "checkpoint_warning": reviewed["checkpoint_warning"],
            "message": "Local records restored. Original store and recovery backup retained. Your pause choice is preserved; reconnect Nautilus for fresh reconciliation and review. Previous approvals are invalid."}
