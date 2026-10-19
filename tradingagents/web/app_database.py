"""Versioned application records. Native portfolio state does not live here."""

import copy
import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path


class StoreConflict(ValueError):
    def __init__(self, revision):
        self.revision = revision
        super().__init__("Saved state changed in another session. Reload it before saving again.")


class ApplicationDatabase:
    VERSION = 1

    def __init__(self, directory, defaults, *, migrate_legacy=False):
        self.path = Path(directory) / "desk.sqlite3"
        legacy = Path(directory) / "desk.json"
        existed = self.path.exists()
        if legacy.exists() and not existed and not migrate_legacy:
            raise ValueError("Offline migration required: stop all journal/artifact writers, capture a source backup, then start once with --migrate-journal. Existing files were not changed.")
        with self.transaction() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, self.VERSION):
                raise ValueError("Unsupported application database version; preserve the database and backups.")
            if version == self.VERSION:
                if connection.execute("SELECT 1 FROM app_records WHERE name='journal'").fetchone() is None:
                    raise ValueError("Application journal record is missing; restore a valid database backup.")
                return
            if existed:
                raise ValueError("Existing database has no committed schema; preserve recovery inputs before retrying migration.")
            raw = legacy.read_bytes() if legacy.exists() else None
            digest = hashlib.sha256(raw).hexdigest() if raw is not None else None
            backup = legacy.with_name("desk.migration-" + digest[:16] + ".json") if digest else None
            if backup:
                if not backup.exists():
                    with backup.open("xb") as stream:
                        stream.write(raw)
                        stream.flush()
                        import os
                        os.fsync(stream.fileno())
                if backup.read_bytes() != raw:
                    raise ValueError("Migration backup differs from the source journal; migration aborted.")
            saved = json.loads(raw) if raw is not None else {}
            if not isinstance(saved, dict):
                raise ValueError("Journal is not an object; original and migration backup were preserved.")
            initial = {**copy.deepcopy(defaults), **saved}
            connection.execute("CREATE TABLE app_records(name TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
            connection.execute("CREATE TABLE migration_info(version INTEGER PRIMARY KEY, source_sha256 TEXT, backup_name TEXT, migrated_at TEXT NOT NULL)")
            stamp = datetime.now(UTC).isoformat()
            connection.execute("INSERT INTO app_records VALUES('journal',1,?,?)", (self.encode(initial), stamp))
            connection.execute("INSERT INTO migration_info VALUES(?,?,?,?)", (self.VERSION, digest, backup.name if backup else None, stamp))
            if raw is not None and legacy.read_bytes() != raw:
                raise ValueError("Source journal changed during migration. Stop all writers; original and backup are preserved.")
            connection.execute("PRAGMA user_version=1")

    @staticmethod
    def encode(data):
        return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @contextmanager
    def transaction(self):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def read(self, name, default=None):
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            row = connection.execute("SELECT revision,payload FROM app_records WHERE name=?", (name,)).fetchone()
        return {"revision": row[0], "data": json.loads(row[1])} if row else {"revision": 0, "data": copy.deepcopy(default)}

    def update(self, name, expected_revision, change, default=None):
        with self.transaction() as connection:
            row = connection.execute("SELECT revision,payload FROM app_records WHERE name=?", (name,)).fetchone()
            revision = row[0] if row else 0
            if type(expected_revision) is not int or expected_revision != revision:
                raise StoreConflict(revision)
            data = json.loads(row[1]) if row else copy.deepcopy(default)
            result = change(data)
            if result is not None:
                data = result
            encoded = self.encode(data)
            if row and encoded == row[1]:
                return {"revision": revision, "data": data}
            revision += 1
            connection.execute("INSERT INTO app_records VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET revision=excluded.revision,payload=excluded.payload,updated_at=excluded.updated_at",
                               (name, revision, encoded, datetime.now(UTC).isoformat()))
            return {"revision": revision, "data": data}

    def transact(self, defaults, change, expected=None):
        """Reread and update related records under one SQLite writer reservation."""
        with self.transaction() as connection:
            records = {}
            for name, default in defaults.items():
                row = connection.execute("SELECT revision,payload FROM app_records WHERE name=?", (name,)).fetchone()
                revision = row[0] if row else 0
                if expected is not None and name in expected and (type(expected[name]) is not int or expected[name] != revision):
                    raise StoreConflict(revision)
                records[name] = {"revision": revision, "data": json.loads(row[1]) if row else copy.deepcopy(default),
                                 "encoded": row[1] if row else None}
            values = {name: record["data"] for name, record in records.items()}
            result = change(values)
            if result is not None:
                values = result
            saved = {}
            for name, record in records.items():
                encoded = self.encode(values[name])
                revision = record["revision"]
                if encoded != record["encoded"]:
                    revision += 1
                    connection.execute("INSERT INTO app_records VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET revision=excluded.revision,payload=excluded.payload,updated_at=excluded.updated_at",
                                       (name, revision, encoded, datetime.now(UTC).isoformat()))
                saved[name] = {"revision": revision, "data": values[name]}
            return saved
