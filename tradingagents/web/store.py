"""Atomic local journal. Unknown broker submissions are never retried blindly."""

from __future__ import annotations

import copy
from contextlib import closing
import hashlib
import html
import json
import os
import re
import struct
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from .app_database import ApplicationDatabase, StoreConflict


class SourceEvidenceError(ValueError):
    """A bounded, safe-to-display receipt-capture failure."""


class DeskStore:
    def __init__(self, directory: Path, defaults: dict, *, migrate_legacy=False):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "desk.json"
        self.lock = threading.RLock()
        self.data = {
            "config": defaults,
            "runs": [],
            "research_requests": [],
            "proposals": [],
            "paused": False,
            "paper_account_id": None,
            "config_revision": 0,
        }
        self.database = ApplicationDatabase(self.directory, self.data, migrate_legacy=migrate_legacy)
        saved = self.database.read("journal")
        self.data, self.revision = saved["data"], saved["revision"]
        for request in self.data["research_requests"]:
            interrupted = request["status"] == "preflight"
            if interrupted:
                request.update(status="interrupted", recovery_observed_at=datetime.now(UTC).isoformat(),
                               capture_complete=False)
                for stage in request["stages"]:
                    if stage["outcome"] == "running":
                        stage["outcome"] = "unknown"
            recovered_calls = False
            for origin in ("source", "gateway", "jev"):
                evidence = request.get(f"{origin}_evidence", {})
                recovered_origin = False
                for attempt in evidence.get("attempts", []):
                    if attempt["outcome"] in {"running", "queued"}:
                        attempt.update(outcome="unknown", recovery_observed_at=datetime.now(UTC).isoformat())
                        recovered_calls = recovered_origin = True
                if recovered_origin:
                    self._snapshot_call_evidence(request, "recovery_unknown", origin)
                self.finalize_call_evidence(request, origin)
            if interrupted or recovered_calls:
                self.checkpoint_request(request, "recovery_unknown")
        for run in self.data["runs"]:
            source_incomplete = any(a.get("outcome") != "success" or a.get("data_status") in {"unavailable", "partial"}
                                    for a in run.get("source_evidence", {}).get("attempts", []))
            for result in run.get("results", []):
                if (result.get("status") == "completed"
                        and (source_incomplete or result.get("social_sentiment", {}).get("status") in {"partial", "unavailable"})):
                    result.update(status="failed", error="Research incomplete: source collection or social screening failed. Saved reports are retained.")
                    result["revision"] = result.get("revision", 0) + 1
                    if run["status"] == "completed":
                        run["status"] = "failed"
            run.setdefault("portfolio_evidence", {
                "status": "unavailable",
                "reason": "Legacy run did not record its consumed portfolio context; cash and holdings are unknown.",
            })
            if run["status"] in {"queued", "running", "cancelling"}:
                run["status"] = "interrupted"
                run["error"] = "Server stopped during analysis. Start a new run."
            if run["status"] in {"completed", "failed", "cancelled", "interrupted"}:
                self._recover_measurements(run)
                evidence = run.get("source_evidence")
                if evidence and any(a["outcome"] == "running" for a in evidence["attempts"]):
                    evidence.update(capture_complete=False, persistence_error="Source attempt interrupted; final outcome unavailable.")
                if evidence and "snapshots" in evidence:
                    recovered_source = False
                    for attempt in evidence["attempts"]:
                        if attempt["outcome"] == "running":
                            attempt.update(outcome="unknown", recovery_observed_at=datetime.now(UTC).isoformat())
                            recovered_source = True
                    if recovered_source:
                        self._snapshot_call_evidence(run, "recovery_unknown", "source")
                    self.finalize_call_evidence(run, "source")
                for origin in ("gateway", "jev"):
                    calls = run.get(f"{origin}_evidence")
                    if calls and any(a["outcome"] in {"queued", "running"} for a in calls.get("attempts", [])):
                        for attempt in calls["attempts"]:
                            if attempt["outcome"] in {"queued", "running"}:
                                attempt.update(outcome="unknown", recovery_observed_at=datetime.now(UTC).isoformat())
                        self._snapshot_call_evidence(run, "recovery_unknown", origin)
                    self.finalize_call_evidence(run, origin)
        self.save()

    def _recover_measurements(self, run):
        measurements = run.get("measurements")
        if not measurements:
            return  # Older runs never collected measurements.
        finalized = bool(measurements.get("ended_at") or measurements.get("recovery_observed_at"))
        if run.get("measurement_artifact") and finalized and measurements.get("status") == run["status"]:
            return
        if str(UUID(run["id"])) != run["id"]:
            raise ValueError("Invalid run ID for measurement recovery.")
        try:
            # A crash can leave a complete immutable artifact before its journal reference.
            candidates = []
            directory = self.directory / "reports" / run["id"]
            for path in directory.glob("measurements-*.json"):
                try:
                    payload = path.read_bytes()
                    candidate = json.loads(payload)
                except (OSError, ValueError):
                    continue  # Preserve partial files; they are not completion evidence.
                if (isinstance(candidate, dict) and candidate.get("run_id") == run["id"]
                        and candidate.get("status") == run["status"]
                        and candidate.get("started_at") == measurements.get("started_at")
                        and (candidate.get("ended_at") or candidate.get("recovery_observed_at"))):
                    candidates.append((candidate, self._measurement_reference(path, payload)))
            if len(candidates) == 1:
                run["measurements"], run["measurement_artifact"] = candidates[0]
            else:
                # No unambiguous final artifact: preserve only what the journal recorded.
                measurements.update(run_id=run["id"], status=run["status"])
                measurements.setdefault("recovery_observed_at", datetime.now(UTC).isoformat())
                if not measurements.get("ended_at"):
                    measurements.update(
                        ended_at=None, elapsed_seconds=None, callbacks_final=False,
                        completeness="Partial journal checkpoint; process termination time and "
                                     "callbacks since the checkpoint are unavailable.",
                    )
                run["measurement_artifact"] = self.write_measurements(run["id"], measurements)
            run.pop("measurement_export_error", None)
        except OSError:
            run["measurement_export_error"] = "Measurement artifact could not be written; measurements remain in journal."

    def _measurement_reference(self, path, payload):
        return {"path": path.relative_to(self.directory).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload), "format": "json"}

    @staticmethod
    def result_summary(result):
        summary = {key: value for key, value in result.items() if key not in {"reports", "laya", "social_sentiment"}}
        summary["report_keys"] = list(result.get("reports", {}))
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

    def snapshot(self, *, compact=False, run_id=None):
        with self.lock:
            saved = self.database.read("journal")
            if saved["revision"] != self.revision:
                self.data, self.revision = saved["data"], saved["revision"]
            if compact:
                data = copy.deepcopy({key: value for key, value in self.data.items() if key not in {"runs", "research_requests"}})
                data["research_requests"] = [{key: copy.deepcopy(r.get(key)) for key in
                    ("id", "run_id", "status", "started_at", "ended_at", "elapsed_seconds", "capture_complete")}
                    for r in self.data["research_requests"]]
                selected = run_id if any(r["id"] == run_id for r in self.data["runs"]) else next((r["id"] for r in self.data["runs"]), None)
                data["runs"] = []
                data["research"] = {}
                for run in self.data["runs"]:
                    results = run.get("results", [])
                    counts = {status: sum(r.get("status") == status for r in results)
                              for status in ("completed", "failed", "cancelled", "running")}
                    counts["queued"] = max(0, len(run["symbols"]) - len(results))
                    summary = {key: copy.deepcopy(value) for key, value in run.items()
                               if key not in {"results", "config", "events", "source_evidence", "portfolio_evidence", "gateway_evidence", "jev_evidence"}}
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
                        results=[self.result_summary(r) for r in results] if run["id"] == selected else [],
                        events=copy.deepcopy(run.get("events", [])[-40:]) if run["id"] == selected else [],
                        event_count=len(run.get("events", [])),
                        config={key: run.get("config", {}).get(key) for key in
                                ("name", "llm_provider", "deep_think_llm", "quick_think_llm",
                                 "max_debate_rounds", "max_risk_discuss_rounds")},
                    )
                    data["runs"].append(summary)
                    for result in results:
                        if result["symbol"] not in data["research"]:
                            status = self.result_summary(result)
                            data["research"][result["symbol"]] = {
                                **{key: status.get(key) for key in
                                   ("symbol", "status", "rating", "trade_date", "elapsed_seconds", "revision")},
                                "run_id": run["id"],
                                "social_sentiment": status.get("social_sentiment"),
                                "laya": {key: status["laya"].get(key) for key in
                                         ("grade", "auto_execute", "question_contract_version")} if status["laya"] else None,
                            }
                return data
            return copy.deepcopy(self.data)

    def save(self):
        with self.lock:
            try:
                saved = self.database.update("journal", self.revision, lambda _: self.data)
                self.revision = saved["revision"]
            except StoreConflict:
                saved = self.database.read("journal")
                self.data, self.revision = saved["data"], saved["revision"]
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
                return json.loads(row[0])
        return json.loads((directory / "desk.json").read_text(encoding="utf-8"))

    def write_measurements(self, run_id, measurements):
        """Write once under the existing run report path; never replace prior evidence."""
        return self._write_json_artifact(run_id, "measurements", measurements)

    def _evidence_owner(self, owner_id):
        return next(r for collection in ("runs", "research_requests")
                    for r in self.data[collection] if r["id"] == owner_id)

    def checkpoint_request(self, request, reason):
        """Best-effort measurement only: never replace the research outcome."""
        with self.lock:
            for origin in ("source", "gateway", "jev"):
                self._call_counts(request[f"{origin}_evidence"], origin)
            request["capture_complete"] = not (request.get("persistence_error") or request["status"] == "interrupted"
                or any(not request[f"{origin}_evidence"]["capture_complete"] for origin in ("source", "gateway", "jev")))
            try:
                snapshot = {k: copy.deepcopy(v) for k, v in request.items() if k != "snapshots"}
                snapshot["snapshot_reason"] = reason
                request["snapshots"].append(self._write_json_artifact(request["id"], "request-measurements", snapshot))
            except Exception:
                request.update(capture_complete=False, persistence_error="Request measurement artifact unavailable.")
            try:
                self.save()
            except Exception:
                request.update(capture_complete=False, persistence_error="Request journal checkpoint unavailable.")

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
                evidence.update(status="journal_only", reason="Portfolio artifact could not be written; context remains in journal.")
            run["portfolio_evidence"] = evidence
            self.save()

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
        return self._measurement_reference(destination, payload)

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
            if evidence.get("terminal_observed_at"):
                attempt["late"] = True
            if receipt["outcome"] == "success":
                try:
                    attempt["artifact"] = self._write_source_result(run_id, receipt["attempt_id"], output)
                    attempt["capture"] = "recorded"
                except (OSError, TypeError, ValueError, OverflowError, RecursionError) as exc:
                    attempt["capture"] = "unavailable"
                    attempt["capture_error"] = (
                        "persistence_failed" if isinstance(exc, OSError) else "unsafe_oversized_or_unsupported_response"
                    )
                    evidence["capture_complete"] = False
            elif receipt["outcome"] == "error":
                attempt["capture"] = "error_class_only"
            if attempt.get("late"):
                evidence["capture_complete"] = False
                self._snapshot_call_evidence(run, "late_update", "source")
                if run.get("owner_kind") == "research_request":
                    self.checkpoint_request(run, "late_update")
            try:
                self.save()
            except OSError:
                evidence["capture_complete"] = False
                evidence["persistence_error"] = "Journal checkpoint failed; durability is unavailable."
                # Retain the receipt in memory for the run's next existing journal save.

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
            evidence["pending_count"] or evidence["unknown_count"] or evidence["late_count"]
            or evidence.get("persistence_error") or any(a.get("capture_error") for a in attempts)
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
            self._call_counts(evidence, origin)
            if attempt.get("late"):
                self._snapshot_call_evidence(run, "late_update", origin)
                if run.get("owner_kind") == "research_request":
                    self.checkpoint_request(run, "late_update")
            elif receipt["boundary_kind"] == "jev_batch" and receipt.get("ended_at"):
                self._snapshot_call_evidence(run, "batch_terminal", origin)
            try:
                self.save()
            except OSError:
                evidence.update(capture_complete=False, persistence_error="Call evidence journal checkpoint failed.")

    def _snapshot_call_evidence(self, run, reason, origin):
        evidence = run[f"{origin}_evidence"]
        self._call_counts(evidence, origin)
        snapshot = {key: copy.deepcopy(value) for key, value in evidence.items() if key != "snapshots"}
        snapshot.update(run_id=run["id"], run_status=run["status"], reason=reason,
                        observed_at=datetime.now(UTC).isoformat())
        if run.get("owner_kind") == "research_request":
            snapshot.update(owner_kind="research_request", request_id=run["id"], run_id=run.get("run_id"))
        try:
            evidence.setdefault("snapshots", []).append(self._write_json_artifact(run["id"], f"{origin}-evidence", snapshot))
        except OSError:
            evidence.update(capture_complete=False, persistence_error="Call evidence snapshot export failed.")

    def finalize_gateway_evidence(self, run):
        self.finalize_call_evidence(run, "gateway")

    def finalize_call_evidence(self, run, origin):
        with self.lock:
            evidence = run.get(f"{origin}_evidence")
            if evidence and not evidence.get("terminal_observed_at"):
                evidence["terminal_observed_at"] = datetime.now(UTC).isoformat()
                self._snapshot_call_evidence(run, "run_terminal", origin)

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
        marker = (r'(?i)(?:api[_ -]?key|authorization|token|password|client[_ -]?secret|secret|cookie|headers)'
                  r'''["'\s]*[:=]|bearer\s+\S+|(?<![\w-])sk-(?:proj-)?[a-zA-Z0-9_-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY''')
        for _ in range(4):
            # Only the known pagination field name is exempted, never its value or other token fields.
            screened = re.sub(r'''(["'])next_page_token\1(?=\s*:)''', r'\1pagination_cursor\1', view) if allow_pagination_cursor else view
            if re.search(marker, screened):
                raise SourceEvidenceError("Secret screening withheld the provider receipt; inspect provider configuration without sharing credentials.")
            decoded = re.sub(r'\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4})',
                             lambda match: json.loads('"' + match.group() + '"'), html.unescape(view))
            if decoded == view:
                break
            view = decoded
        else:
            raise SourceEvidenceError("Provider receipt encoding exceeds the supported screening depth; report the source format without pasting its body.")
        relative = Path("reports") / run_id / f"{prefix}-{attempt_id}-{uuid4()}.bin"
        destination = self.directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return {**self._measurement_reference(destination, payload), "format": format_name}

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
