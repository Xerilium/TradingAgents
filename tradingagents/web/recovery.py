"""Shared application storage ownership, integrity and artifact inspection."""

import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID

from .app_database import ApplicationDatabase
from .config import DeskConfig

MAX_ARTIFACT_BYTES = 512 * 1024 * 1024
MAX_ARTIFACT_FILES = 883011
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
        raise ValueError("Active recovery generation is incomplete; preserve original stores and repair the saved generation before restarting")
    return generation / "application", generation / "history" if record["has_history"] else None


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def references(value):
    if isinstance(value, dict):
        if SECRET_KEYS & {str(k).lower() for k in value}:
            raise ValueError("Application record contains a credential field; artifact inspection stopped")
        if "path" in value and "sha256" in value:
            name = value["path"]
            if (not isinstance(name, str) or not re.fullmatch(r"reports/(?:(?:[0-9a-f-]{36}|native-recovery|native-targeted-orders)/[A-Za-z0-9_.-]+|native-reconstruction/execution-[0-9a-f-]{36}\.json)", name)
                    or not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"])):
                raise ValueError("Unsupported artifact reference; artifact inspection is incomplete")
            yield name, value["sha256"]
        for item in value.values():
            yield from references(item)
    elif isinstance(value, list):
        for item in value:
            yield from references(item)


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
            raise ValueError("Referenced immutable artifact is missing or escapes its application boundary: " + relative)
        payload = path.read_bytes()
        total += len(payload)
        if sha(payload) != expected:
            raise ValueError("Referenced immutable artifact hash differs: " + relative)
        if total > MAX_ARTIFACT_BYTES or len(seen) >= MAX_ARTIFACT_FILES:
            raise ValueError(f"Referenced evidence requires {total:,} bytes and {len(seen) + 1:,} files; limits are {MAX_ARTIFACT_BYTES:,} artifact bytes and {MAX_ARTIFACT_FILES:,} files")
        seen[relative] = expected
        if relative.endswith(".json"):
            queue.extend(references(json.loads(payload)))
        yield relative, payload


def records(database, resolve_artifact=None):
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA trusted_schema=OFF")
        if connection.execute("PRAGMA user_version").fetchone()[0] != ApplicationDatabase.VERSION:
            raise ValueError("Application database schema version is unsupported")
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Application database integrity check failed")
        for kind, name in connection.execute("SELECT type,name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"):
            if kind != "table" or name not in {"app_records", "migration_info"}:
                raise ValueError("Application database contains unexpected database objects")
        schemas = {"app_records": "CREATE TABLE app_records(name TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL)",
                   "migration_info": "CREATE TABLE migration_info(version INTEGER PRIMARY KEY, source_sha256 TEXT, backup_name TEXT, migrated_at TEXT NOT NULL)"}
        for name, sql in connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            if "".join(sql.split()).lower() != "".join(schemas[name].split()).lower():
                raise ValueError("Application database schema does not match its declared version")
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
        raise ValueError("Application journal is missing")
    DeskConfig.model_validate(journal["config"])
    for collection in ("runs", "research_requests"):
        if not isinstance(journal.get(collection), list):
            raise ValueError("Invalid saved journal collection")
        for record in journal[collection]:
            if str(UUID(record["id"])) != record["id"]:
                raise ValueError("Invalid saved evidence owner identity")
