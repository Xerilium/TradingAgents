"""Atomic local journal. Unknown broker submissions are never retried blindly."""

from __future__ import annotations

import copy
from contextlib import closing
import hashlib
import html
import json
import os
import re
import sqlite3
import struct
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from .app_database import ApplicationDatabase, StoreConflict
from .evidence_requirements import research_gaps


class SourceEvidenceError(ValueError):
    """A bounded, safe-to-display receipt-capture failure."""


def _local_laya_attempt(attempt):
    return (attempt.get("origin") == "local_laya" and attempt.get("vendor") == "laya"
            and attempt.get("operation") == "predict_batch" and attempt.get("boundary_kind") == "local_batch")


def source_attempt_failed(attempt, attempts=()):
    if (_local_laya_attempt(attempt) and attempt.get("ended_at") and not attempt.get("late")
            and not attempt.get("capture_error") and attempt.get("capture") == "recorded"
            and attempt.get("outcome") in {"success", "error", "unknown"}):
        return False  # Optional inference coverage is separate from original source acquisition.
    if (attempt.get("requirement") == "supplemental" and not attempt.get("capture_error")
            and attempt.get("ended_at") and not attempt.get("late")
            and attempt.get("capture") in {"recorded", "error_class_only"}
            and attempt.get("outcome") in {"success", "error"}):
        return False
    if (attempt.get("operation") == "reddit_rss" and attempt.get("vendor") == "reddit"
            and attempt.get("origin") == "http_response_bytes" and attempt.get("outcome") == "error"
            and not attempt.get("capture_error") and attempt.get("arguments", {}).get("ticker")
            and attempt.get("ended_at") and any(
                other.get("outcome") == "success" and other.get("capture") == "recorded"
                and not other.get("capture_error") and not other.get("late")
                and (other.get("started_at") or "") >= attempt["ended_at"]
                and all(other.get(key) == attempt.get(key) for key in
                        ("symbol", "operation", "vendor", "origin", "arguments", "parent_attempt_id"))
                for other in attempts)):
        return False  # Retain the failed receipt; the same input was acquired by its retry.
    return bool(attempt.get("capture_error") or (
        (attempt.get("outcome") != "success" or attempt.get("data_status") in {"unavailable", "partial", "no_usable_coverage"})
        and not (attempt.get("requirement") == "supplemental"
                 and attempt.get("operation") == "read_research_source"
                 and attempt.get("vendor") == "public_source" and attempt.get("origin") == "source_document_text"
                 and attempt.get("outcome") == "error" and attempt.get("error_class") == "HTTPError"
                 and type(attempt.get("http_status")) is int and 400 <= attempt["http_status"] <= 599
                 and attempt.get("capture") == "error_class_only")))


def call_evidence_failed(evidence):
    """Unknown optional read outcomes are gaps, not missing durable receipts."""
    optional = {
        "gateway": {"GatewayIndex"},
        "laya": {"decide"},
        "maenifold.memory": {"SearchMemories", "ReadMemory", "ListMemories", "ExtractConceptsFromFile"},
        "maenifold.graph": {"BuildContext", "FindSimilarConcepts", "Visualize", "AnalyzeConceptCorruption"},
    }
    return (not evidence.get("persistence_complete", evidence.get("capture_complete", False))
            or any(a.get("outcome") == "unknown" and a.get("operation") not in optional.get(a.get("vendor"), ())
                   for a in evidence.get("attempts", [])))


class DeskStore:
    def __init__(self, directory: Path, defaults: dict, *, migrate_legacy=False):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "desk.json"
        self.lock = threading.RLock()
        self.data = {
            "config": defaults,
            "runs": [],
            "proposals": [],
            "paused": False,
            "paper_account_id": None,
            "config_revision": 0,
        }
        self.database = ApplicationDatabase(self.directory, self.data, migrate_legacy=migrate_legacy)
        saved = self.database.read("journal")
        self.data, self.revision = saved["data"], saved["revision"]
        latest = self.database.read("latest_research", {"runs": []})
        self.research_revision = latest["revision"]
        self.data["runs"] = latest["data"]["runs"] if latest["revision"] else self.data.get("runs", [])
        self.data.pop("research_requests", None)
        self.prune_research()
        for run in self.data["runs"]:
            if run["status"] in {"queued", "running", "cancelling"}:
                run.update(status="failed", error="Service stopped during research. Start a new cycle; desk research does not resume.")
                for result in run["results"]:
                    if result["status"] in {"queued", "running", "cancelling"}:
                        result.update(status="failed", error=run["error"])
            for origin in ("source", "gateway", "jev"):
                evidence = run.get(f"{origin}_evidence")
                if evidence is None:
                    continue
                for attempt in evidence.get("attempts", []):
                    if attempt.get("outcome") in {"queued", "running"}:
                        attempt.update(outcome="unknown", recovery_observed_at=datetime.now(UTC).isoformat())
                self._call_counts(evidence, origin)
            attempts = run.get("source_evidence", {}).get("attempts", [])
            for result in run["results"]:
                if result.get("status") == "completed" and any(
                        source_attempt_failed(a, attempts) for a in attempts
                        if a.get("symbol") in {None, result["symbol"]}):
                    result.update(status="failed", revision=result.get("revision", 0) + 1,
                                  error="Research incomplete: required source collection or evidence capture failed. Saved reports are retained.")
                    if run["status"] == "completed":
                        run["status"] = "failed"
        self.save_research()
        self.save()

    def prune_research(self):
        """Keep exactly the newest cycle's result for each ticker, including failures."""
        seen, runs = set(), []
        for run in sorted(self.data["runs"], key=lambda r: (r.get("created_at", ""), r["id"]), reverse=True):
            results = [r for r in run.get("results", []) if r["symbol"] not in seen]
            if not results:
                continue
            symbols = {r["symbol"] for r in results}
            seen.update(symbols)
            run.update(results=results, symbols=[s for s in run["symbols"] if s in symbols])
            for key in ("continuation", "request_id", "measurement_artifact", "measurements", "measurement_export_error"):
                run.pop(key, None)
            for result in results:
                result.pop("continuation", None)
                if result.get("local_laya_batch"):
                    result["local_laya_batch"].pop("previous_artifacts", None)
            run["events"] = [e for e in run.get("events", []) if e.get("symbol") in symbols or not e.get("symbol")][-500:]
            for origin in ("source", "gateway", "jev"):
                evidence = run.get(f"{origin}_evidence", {})
                evidence["attempts"] = [a for a in evidence.get("attempts", []) if a.get("symbol") in symbols or not a.get("symbol")]
                evidence["snapshots"] = []
            runs.append(run)
        self.data["runs"] = runs

    def save_research(self):
        with self.lock:
            self.prune_research()
            saved = self.database.update("latest_research", self.research_revision,
                lambda _: {"runs": self.data["runs"]}, {"runs": []})
            self.research_revision = saved["revision"]

    def _research_cleanup_files(self, old, remaining, connection, run_ids):
        """Find verified, unreferenced evidence without reading binary artifacts."""
        from .recovery import references, MAX_EXPANDED

        def paths(value, allowed_runs=None):
            queue, seen, total = list(references(value)), {}, 0
            while queue:
                relative, digest = queue.pop()
                if allowed_runs is not None and relative.split("/")[1] not in allowed_runs:
                    continue
                if relative in seen:
                    if seen[relative] != digest:
                        raise ValueError("Artifact identity has conflicting hashes")
                    continue
                seen[relative] = digest
                if relative.endswith(".json"):
                    target = self.directory / relative
                    if (any(part.is_symlink() or getattr(part, "is_junction", lambda: False)()
                            for part in (target, target.parent, target.parent.parent))
                            or not target.resolve().is_relative_to(self.directory.resolve()) or not target.is_file()):
                        raise ValueError("Evidence path is unavailable or unsafe")
                    payload = target.read_bytes()
                    total += len(payload)
                    if total > MAX_EXPANDED or hashlib.sha256(payload).hexdigest() != digest:
                        raise ValueError("Evidence JSON could not be verified")
                    queue.extend(references(json.loads(payload)))
            return seen

        try:
            candidates = paths(old, run_ids)
            records = [json.loads(row[0]) for row in connection.execute(
                "SELECT payload FROM app_records WHERE name != 'latest_research'")]
            records.append(remaining)
            for backup in self.directory.glob("desk.migration-*.json"):
                if backup.is_symlink() or getattr(backup, "is_junction", lambda: False)():
                    raise ValueError("Migration backup is a link")
                records.append(json.loads(backup.read_text(encoding="utf-8")))
            protected = paths(records)
            eligible = {}
            for relative, digest in candidates.items():
                if relative in protected or relative.split("/")[1] not in run_ids:
                    continue
                target = self.directory / relative
                if (any(part.is_symlink() or getattr(part, "is_junction", lambda: False)()
                        for part in (target, target.parent, target.parent.parent))
                        or not target.resolve().is_relative_to(self.directory.resolve()) or not target.is_file()):
                    raise ValueError("Evidence path is unavailable or unsafe")
                eligible[relative] = (digest, target.stat().st_size)
            return eligible, []
        except (OSError, ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError):
            return {}, ["Some evidence could not be verified; research artifacts will be retained."]

    def delete_research(self, symbols, expected_revision=None, preview=False):
        """Remove selected latest results while preserving shared and pinned evidence."""
        if (not isinstance(symbols, list) or not symbols or any(not isinstance(s, str) or not s or s != s.upper() for s in symbols)
                or len(set(symbols)) != len(symbols)):
            raise ValueError("Select one or more distinct uppercase ticker symbols.")
        selected = set(symbols)
        with self.lock:
            known = {result["symbol"] for run in self.data["runs"] for result in run.get("results", [])}
            if not selected <= known:
                raise ValueError("Selected research is no longer available. Refresh and select again.")
            old = copy.deepcopy({"runs": self.data["runs"]})
            run_ids = {run["id"] for run in old["runs"] if any(result["symbol"] in selected for result in run.get("results", []))}
            if any(str(UUID(run_id)) != run_id for run_id in run_ids):
                raise ValueError("Invalid saved research run identity.")
            remaining = copy.deepcopy(old)
            count = 0
            runs = []
            for run in remaining["runs"]:
                count += sum(result["symbol"] in selected for result in run.get("results", []))
                run["results"] = [result for result in run.get("results", []) if result["symbol"] not in selected]
                if not run["results"]:
                    continue
                run["symbols"] = [symbol for symbol in run.get("symbols", []) if symbol not in selected]
                run["events"] = [event for event in run.get("events", []) if event.get("symbol") not in selected]
                for origin in ("source", "gateway", "jev"):
                    evidence = run.get(f"{origin}_evidence", {})
                    evidence["attempts"] = [attempt for attempt in evidence.get("attempts", []) if attempt.get("symbol") not in selected]
                runs.append(run)
            remaining["runs"] = runs
            if preview:
                with self.database.transaction() as connection:
                    revision = connection.execute("SELECT revision FROM app_records WHERE name='latest_research'").fetchone()
                    revision = revision[0] if revision else 0
                    if revision != self.research_revision:
                        raise StoreConflict(revision)
                    files, warnings = self._research_cleanup_files(old, remaining, connection, run_ids)
                return {"symbols": symbols, "expected_revision": revision, "result_count": count,
                        "artifact_count": len(files), "artifact_bytes": sum(size for _, size in files.values()), "warnings": warnings}
            saved = self.database.update("latest_research", expected_revision, lambda _: remaining, {"runs": []})
            self.data["runs"], self.research_revision = saved["data"]["runs"], saved["revision"]
        deleted, warnings = 0, []
        try:
            with self.database.transaction() as connection:
                files, warnings = self._research_cleanup_files(old, remaining, connection, run_ids)
                for relative, (digest, size) in files.items():
                    target = self.directory / relative
                    try:
                        if (any(part.is_symlink() or getattr(part, "is_junction", lambda: False)()
                                for part in (target, target.parent, target.parent.parent))
                                or not target.resolve().is_relative_to(self.directory.resolve())
                                or target.stat().st_size != size or hashlib.sha256(target.read_bytes()).hexdigest() != digest):
                            raise ValueError("Evidence changed")
                        target.unlink()
                        deleted += 1
                    except (OSError, ValueError):
                        warnings.append("Some evidence changed or could not be removed; it was retained.")
        except (OSError, sqlite3.Error):
            warnings.append("Evidence references could not be rechecked; remaining artifacts were retained.")
        return {"deleted_symbols": symbols, "deleted_results": count, "deleted_artifacts": deleted, "warnings": list(dict.fromkeys(warnings))}

    def _artifact_reference(self, path, payload):
        return {"path": path.relative_to(self.directory).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload), "format": "json"}

    @staticmethod
    def result_summary(result):
        summary = {key: value for key, value in result.items() if key not in {"reports", "laya", "social_sentiment", "continuation"}}
        summary["report_keys"] = list(result.get("reports", {}))
        summary["completion_gaps"] = research_gaps(result) if result.get("status") == "completed" else []
        if summary["completion_gaps"]:
            summary["status"] = "incomplete"
        summary["revision"] = result.get("revision", 0)
        laya = result.get("laya") or {}
        summary["laya"] = {
            "question_contract_version": laya.get("question_contract_version"),
            "grade": laya.get("contract", {}).get("grade", laya.get("grade")),
            "auto_execute": laya.get("auto_execute") is True,
            "summary": laya.get("contract", {}).get("summary", laya.get("summary")),
        } if laya else None
        social = result.get("social_sentiment")
        if social:
            summary["social_sentiment"] = {
                "status": social.get("status"), "model": social.get("model"),
                "sources": {source: {key: copy.deepcopy(value.get(key)) for key in
                                     ("status", "counts", "note", "admission_version", "stop_reason", "classified_count", "retained_count")}
                            for source, value in social.get("sources", {}).items()},
            }
        return copy.deepcopy(summary)

    def _refresh(self):
        """Refresh external journal changes while the caller holds self.lock."""
        with closing(sqlite3.connect(self.database.path, timeout=5)) as connection:
            revision = connection.execute("SELECT revision FROM app_records WHERE name='journal'").fetchone()[0]
        if revision != self.revision:
            saved = self.database.read("journal")
            self.data, self.revision = {**saved["data"], "runs": self.data["runs"]}, saved["revision"]

    def snapshot(self, *, compact=False, run_id=None, journal=None):
        # Settings come from the committed journal; research is the live latest cache.
        with self.lock:
            if journal is None:
                self._refresh()
                journal = self.data
            journal = {**journal, "runs": journal.get("runs", self.data["runs"])}
            if compact:
                data = copy.deepcopy({key: value for key, value in journal.items() if key != "runs"})
                selected = run_id if any(r["id"] == run_id for r in journal["runs"]) else next((r["id"] for r in journal["runs"]), None)
                data["runs"] = []
                data["research"] = {}
                for run in journal["runs"]:
                    results = run.get("results", [])
                    counts = {status: sum(r.get("status") == status for r in results)
                              for status in ("completed", "failed", "cancelled", "running")}
                    counts["queued"] = sum(r.get("status") == "queued" for r in results)
                    summary = {key: copy.deepcopy(value) for key, value in run.items()
                               if key not in {"results", "config", "events", "source_evidence", "portfolio_evidence", "gateway_evidence", "jev_evidence", "continuation"}}
                    for name in ("gateway_evidence", "jev_evidence"):
                        if name in run:
                            summary[name] = {
                                key: copy.deepcopy(value) for key, value in run[name].items()
                                if key not in {"attempts", "snapshots"}
                            }
                    portfolio_evidence = run.get("portfolio_evidence", {})
                    summary["portfolio_evidence"] = {
                        key: copy.deepcopy(value) for key, value in portfolio_evidence.items() if key != "context"
                    }
                    if "source_evidence" in run:
                        evidence = run["source_evidence"]
                        summary["source_evidence"] = {
                            "coverage": evidence["coverage"],
                            "capture_complete": evidence["capture_complete"],
                            "attempt_count": len(evidence["attempts"]),
                        }
                    summary.update(
                        counts=counts,
                        results=[self.result_summary(r) for r in results],
                        events=copy.deepcopy(run.get("events", [])[-40:]) if run["id"] == selected else [],
                        event_count=len(run.get("events", [])),
                        config={key: run.get("config", {}).get(key) for key in
                                ("name", "llm_provider", "deep_think_llm", "quick_think_llm",
                                 "max_debate_rounds", "max_risk_discuss_rounds")},
                    )
                    incomplete = sum(bool(item.get("completion_gaps")) for item in summary["results"])
                    summary["counts"]["incomplete"] = incomplete
                    summary["counts"]["completed"] -= incomplete
                    if summary["status"] == "completed" and incomplete:
                        summary["status"] = "incomplete"
                    data["runs"].append(summary)
                    for result in results:
                        if result["symbol"] not in data["research"]:
                            status = self.result_summary(result)
                            data["research"][result["symbol"]] = {
                                **{key: status.get(key) for key in
                                   ("symbol", "status", "rating", "trade_date", "elapsed_seconds", "revision", "completion_gaps")},
                                "run_id": run["id"],
                                "social_sentiment": status.get("social_sentiment"),
                                "laya": {key: status["laya"].get(key) for key in
                                         ("grade", "auto_execute", "question_contract_version")} if status["laya"] else None,
                            }
                return data
            return copy.deepcopy(journal)

    def save(self):
        with self.lock:
            try:
                with self.database.transaction() as connection:
                    row = connection.execute("SELECT revision,payload FROM app_records WHERE name='journal'").fetchone()
                    revision = row[0] if row else 0
                    if type(self.revision) is not int or self.revision != revision:
                        raise StoreConflict(revision)
                    encoded = self.database.encode({**self.data, "runs": []})
                    if row is None or encoded != row[1]:
                        revision += 1
                        connection.execute("INSERT INTO app_records VALUES('journal',?,?,?) ON CONFLICT(name) DO UPDATE SET revision=excluded.revision,payload=excluded.payload,updated_at=excluded.updated_at",
                            (revision, encoded, datetime.now(UTC).isoformat()))
                self.revision = revision
            except StoreConflict:
                saved = self.database.read("journal")
                self.data, self.revision = {**saved["data"], "runs": self.data["runs"]}, saved["revision"]
                raise

    @staticmethod
    def read_existing(directory):
        directory = Path(directory).resolve()
        database = directory / "desk.sqlite3"
        if database.exists():
            import sqlite3
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
                row = connection.execute("SELECT payload FROM app_records WHERE name='journal'").fetchone()
                if row is None:
                    raise ValueError("Saved database journal is missing")
                saved = json.loads(row[0])
        else:
            saved = json.loads((directory / "desk.json").read_text(encoding="utf-8"))
        saved.pop("research_requests", None)
        return {**saved, "runs": []}

    def _evidence_owner(self, owner_id):
        return next(r for r in self.data["runs"] if r["id"] == owner_id)

    def record_portfolio_context(self, run_id, context):
        """Keep the consumed context, never reconstruct it from a later account refresh."""
        with self.lock:
            run = next(r for r in self.data["runs"] if r["id"] == run_id)
            if "context" in run.get("portfolio_evidence", {}):
                return
            evidence = {"status": "recorded", "context": copy.deepcopy(context)}
            try:
                evidence["artifact"] = self._write_json_artifact(run_id, "portfolio-context", context)
            except OSError:
                evidence.update(status="cache_only", reason="Portfolio artifact could not be written; context remains in the latest research cache.")
            run["portfolio_evidence"] = evidence

    def _write_json_artifact(self, run_id, kind, content):
        if str(UUID(run_id)) != run_id:
            raise ValueError("Invalid run ID for evidence export.")
        relative = Path("reports") / run_id / f"{kind}-{uuid4()}.json"
        destination = self.directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(content, sort_keys=True, ensure_ascii=False,
                             indent=2, allow_nan=False).encode("utf-8")
        with destination.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return self._artifact_reference(destination, payload)

    def record_source_attempt(self, run_id, receipt, output=None):
        """Persist router receipts without exposing output or exception text in the journal."""
        if receipt.get("origin") in {"gateway", "jev"}:
            self._record_call_attempt(run_id, receipt, output)
            return
        with self.lock:
            run = self._evidence_owner(run_id)
            evidence = run["source_evidence"]
            attempt = next((r for r in evidence["attempts"] if r["attempt_id"] == receipt["attempt_id"]), None)
            if attempt is None:
                attempt = {}
                evidence["attempts"].append(attempt)
            attempt.update(copy.deepcopy(receipt))
            if _local_laya_attempt(attempt):
                attempt["requirement"] = "supplemental"
            if evidence.get("terminal_observed_at"):
                attempt["late"] = True
            if receipt["outcome"] == "success" or (_local_laya_attempt(receipt) and receipt.get("ended_at")
                                                   and receipt["outcome"] in {"error", "unknown"}):
                try:
                    attempt["artifact"] = self._write_source_result(run_id, receipt["attempt_id"], output)
                    attempt["capture"] = "recorded"
                except (OSError, TypeError, ValueError, OverflowError, RecursionError) as exc:
                    attempt["capture"] = "unavailable"
                    attempt["capture_error"] = (
                        "persistence_failed" if isinstance(exc, OSError) else "unsafe_oversized_or_unsupported_response"
                    )
                    if isinstance(exc, SourceEvidenceError):
                        attempt["capture_error_details"] = str(exc)
                    evidence["capture_complete"] = False
            elif receipt["outcome"] == "error":
                attempt["capture"] = "error_class_only"
            if attempt.get("late"):
                evidence["capture_complete"] = False

    @staticmethod
    def _call_counts(evidence, origin):
        attempts = evidence.get("attempts", [])
        if origin == "source":
            evidence["counts"] = {kind: sum(a["origin"] == kind for a in attempts)
                                  for kind in {a["origin"] for a in attempts}}
            evidence["unavailable_data_count"] = sum(a.get("data_status") == "unavailable" for a in attempts)
            evidence["partial_data_count"] = sum(a.get("data_status") == "partial" for a in attempts)
            evidence["data_validation"] = "Request capture does not verify source relevance, factual accuracy, or complete requested coverage."
        elif origin == "gateway":
            evidence["counts"] = {
                kind: {category: sum(a["boundary_kind"] == kind and a["category"] == category for a in attempts)
                       for category in ("source", "control_plane")}
                for kind in ("gateway_invocation", "gateway_logical", "gateway_discovery", "gateway_transport")
            }
        else:
            evidence["counts"] = {kind: sum(a["boundary_kind"] == kind for a in attempts)
                                  for kind in ("jev_batch", "jev_job", "jev_post")}
            evidence["queued_count"] = sum(a["outcome"] == "queued" for a in attempts)
            evidence["cancelled_count"] = sum(a["outcome"] == "cancelled" for a in attempts)
        evidence["pending_count"] = sum(a["outcome"] in {"queued", "running"} for a in attempts)
        evidence["unknown_count"] = sum(a["outcome"] == "unknown" for a in attempts)
        evidence["late_count"] = sum(a.get("late", False) for a in attempts)
        evidence["capture_complete"] = not (
            evidence["pending_count"] or any(a.get("outcome") == "unknown" and source_attempt_failed(a, attempts)
                                             for a in attempts) or evidence["late_count"]
            or evidence.get("persistence_error") or any(a.get("capture_error") for a in attempts)
        )
        evidence["persistence_complete"] = not (
            evidence["pending_count"] or evidence["late_count"] or evidence.get("persistence_error")
            or any(a.get("capture_error") or a.get("capture") not in {"recorded", "metadata_only", "error_class_only"}
                   for a in attempts)
        )

    def _record_call_attempt(self, run_id, receipt, output):
        with self.lock:
            run = self._evidence_owner(run_id)
            origin = receipt["origin"]
            evidence = run.setdefault(f"{origin}_evidence", {
                "attempts": [], "snapshots": [], "capture_complete": True,
                "internal_http_requests": None, "internal_model_executions": None,
            })
            evidence.setdefault("attempts", [])
            evidence.setdefault("snapshots", [])
            attempt = next((a for a in evidence["attempts"] if a["attempt_id"] == receipt["attempt_id"]), None)
            if attempt is None:
                attempt = {"receipts": []}
                evidence["attempts"].append(attempt)
            attempt.update(copy.deepcopy(receipt))
            if evidence.get("terminal_observed_at"):
                attempt["late"] = True
            if origin == "jev":
                parent_id = attempt.get("parent_attempt_id")
                parents = {a["attempt_id"]: a for a in evidence["attempts"]}
                while parent_id in parents:
                    parent = parents[parent_id]
                    if parent["boundary_kind"] == "jev_batch" and parent.get("ended_at"):
                        attempt["late"] = True
                        break
                    parent_id = parent.get("parent_attempt_id")
            try:
                # Only eligible scopes supply a payload. Control-plane data never reaches a writer.
                body = {"receipt": {**copy.deepcopy(receipt), "late": attempt.get("late", False)}}
                if receipt["capture_eligible"]:
                    body["payload"] = dict(output)
                    result = output.get("result")
                    if receipt["boundary_kind"] == "gateway_transport" and result is not None:
                        from mcp.types import CallToolResult
                        if isinstance(result, CallToolResult):
                            body["payload"]["result"] = result.model_dump(mode="json")
                reference = self._write_source_result(run_id, receipt["attempt_id"], body, f"{origin}-receipt")
                attempt["receipts"].append(reference)
                attempt["capture"] = "recorded" if receipt["capture_eligible"] else "metadata_only"
            except (OSError, TypeError, ValueError, OverflowError, RecursionError) as exc:
                attempt["capture"] = "unavailable"
                attempt["capture_error"] = (
                    "persistence_failed" if isinstance(exc, OSError) else "unsafe_oversized_or_unsupported_response"
                )
                if isinstance(exc, SourceEvidenceError):
                    attempt["capture_error_details"] = str(exc)

    def _write_source_result(self, run_id, attempt_id, output, prefix="source", *, allow_pagination_cursor=False):
        import pandas as pd

        if str(UUID(run_id)) != run_id or str(UUID(attempt_id)) != attempt_id:
            raise ValueError("Invalid source evidence ID.")
        if isinstance(output, pd.DataFrame):
            payload = json.dumps(self._frame_evidence(output), ensure_ascii=False, allow_nan=False).encode("utf-8")
            format_name = "pandas-frame-v1-json"
        elif isinstance(output, str):
            payload, format_name = output.encode("utf-8"), "utf-8-text"
        elif isinstance(output, bytes):
            payload, format_name = output, "bytes"
        elif output is None or isinstance(output, (dict, list, bool, int, float)):
            payload = json.dumps(output, ensure_ascii=False, allow_nan=False).encode("utf-8")
            format_name = "json"
        else:
            raise TypeError("Unsupported source response type.")
        if len(payload) > 8 * 1024 * 1024:
            raise SourceEvidenceError("Provider receipt exceeds the 8 MiB evidence limit; reduce the requested page size.")
        # Screen bounded textual views only; successful artifacts keep the original bytes.
        # RSS can entity-escape JSON, which can itself contain escaped key delimiters.
        view = payload.decode("utf-8")  # Non-UTF-8 bodies are an explicit unsupported capture.
        marker = (r'''(?im)(?:^\s*|[{,]\s*|["'])[\w-]*(?:api[_ -]?key|authorization|token|password|client[_ -]?secret|secret|cookie|headers)'''
                  r'''["'\s]*[:=]|bearer\s+\S+|(?<![\w-])sk-(?:(?:proj|svcacct)-[a-zA-Z0-9_-]{16,}|[a-zA-Z0-9]{32,})(?![\w-])|-----BEGIN [A-Z ]*PRIVATE KEY''')
        screening_work = 0
        screening_work_limit = 4 * 8 * 1024 * 1024
        while True:
            screening_work += len(view)
            if screening_work > screening_work_limit:
                raise SourceEvidenceError("Provider receipt secret screening exceeded its cumulative work limit; report the source format without pasting its body.")
            # Only the known pagination field name is exempted, never its value or other token fields.
            screened = re.sub(r'''(["'])next_page_token\1(?=\s*:)''', r'\1pagination_cursor\1', view) if allow_pagination_cursor else view
            if re.search(marker, screened):
                raise SourceEvidenceError("Secret screening withheld the provider receipt; inspect provider configuration without sharing credentials.")
            decoded = re.sub(r'\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4})',
                             lambda match: json.loads('"' + match.group() + '"'), html.unescape(view))
            if decoded == view:
                break
            view = decoded
        relative = Path("reports") / run_id / f"{prefix}-{attempt_id}-{uuid4()}.bin"
        destination = self.directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return {**self._artifact_reference(destination, payload), "format": format_name}

    @staticmethod
    def _frame_evidence(frame):
        """Safe tagged values: exact numeric bits, axes and dtypes; no executable codec."""
        import numpy as np
        import pandas as pd

        if frame.size > 100_000 or len(frame.index) > 100_000 or len(frame.columns) > 100_000 or frame.attrs:
            raise ValueError("Unsupported frame size or attributes.")
        if any(isinstance(label, str) and re.search(r"(?i)api[_ -]?key|authorization|token|password|secret|cookie|headers", label)
               for label in (frame.columns.array[i] for i in range(len(frame.columns)))):
            raise ValueError("Frame columns may contain credentials.")

        def dtype_name(dtype):
            name = str(dtype)
            if not re.fullmatch(r"(?:u?int(?:8|16|32|64)|float(?:16|32|64)|bool|object|str|string|"
                                r"U?Int(?:8|16|32|64)|Float(?:32|64)|boolean|datetime64\[(?:ns|us|ms|s)(?:, [^\]]+)?\])", name):
                raise ValueError("Unsupported frame dtype.")
            metadata = {"name": name}
            if isinstance(dtype, np.dtype):
                metadata["numpy_dtype"] = dtype.str
            if isinstance(dtype, pd.StringDtype):
                metadata.update(storage=dtype.storage, missing=scalar(dtype.na_value))
            return metadata

        def scalar(value):
            if value is pd.NA:
                return {"type": "pd.NA"}
            if value is pd.NaT:
                return {"type": "pd.NaT"}
            if value is None:
                return {"type": "none"}
            if isinstance(value, pd.Timestamp):
                return {"type": "timestamp", "nanoseconds": str(value.value),
                        "timezone": str(value.tz) if value.tz is not None else None}
            if isinstance(value, np.generic) and value.dtype.kind in "biuf" and value.dtype.itemsize <= 8:
                return {"type": "numpy", "dtype": value.dtype.str, "hex": value.tobytes().hex()}
            if isinstance(value, bool):
                return {"type": "bool", "value": value}
            if isinstance(value, int):
                return {"type": "int", "decimal": str(value)}
            if isinstance(value, float):
                return {"type": "float64", "hex": struct.pack(">d", value).hex()}
            if isinstance(value, str):
                return {"type": "str", "value": value}
            raise TypeError("Unsupported frame cell or axis label.")

        def axis(index):
            if type(index) not in {pd.Index, pd.RangeIndex, pd.DatetimeIndex}:
                raise ValueError("Unsupported frame axis.")
            # Index iteration can coerce float32 to Python float and quiet signaling
            # NaNs. Positional array scalars preserve their original dtype and bits.
            values = index.array
            metadata = {"kind": type(index).__name__, "dtype": dtype_name(index.dtype),
                        "name": scalar(index.name), "values": [scalar(values[i]) for i in range(len(index))]}
            if isinstance(index, pd.RangeIndex):
                metadata["range"] = [index.start, index.stop, index.step]
            if isinstance(index, pd.DatetimeIndex):
                metadata["frequency"] = index.freqstr
            return metadata

        return {
            "schema": "pandas-frame-v1", "index": axis(frame.index), "columns": axis(frame.columns),
            "dtypes": [dtype_name(dtype) for dtype in frame.dtypes],
            "allows_duplicate_labels": frame.flags.allows_duplicate_labels,
            "data": [[scalar(frame.iat[row, column]) for column in range(len(frame.columns))]
                     for row in range(len(frame.index))],
        }
