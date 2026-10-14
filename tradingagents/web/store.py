"""Atomic local journal. Unknown broker submissions are never retried blindly."""

from __future__ import annotations

import copy
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


class DeskStore:
    def __init__(self, directory: Path, defaults: dict):
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
        if self.path.exists():
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                raise ValueError(
                    "Paper journal is not an object; preserve it and restore a valid journal."
                )
            self.data.update(saved)
        for run in self.data["runs"]:
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
                gateway = run.get("gateway_evidence")
                if gateway and any(a["outcome"] == "running" for a in gateway.get("attempts", [])):
                    for attempt in gateway["attempts"]:
                        if attempt["outcome"] == "running":
                            attempt.update(outcome="unknown", recovery_observed_at=datetime.now(UTC).isoformat())
                    self._snapshot_gateway_evidence(run, "recovery_unknown")
                self.finalize_gateway_evidence(run)
        for proposal in self.data["proposals"]:
            if proposal["status"] == "submitting":
                proposal["status"] = "unknown"
                proposal["reason"] = (
                    "Submission interrupted. Refresh broker orders to reconcile; do not resubmit."
                )
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
        summary = {key: value for key, value in result.items() if key not in {"reports", "laya"}}
        summary["report_keys"] = list(result.get("reports", {}))
        summary["revision"] = result.get("revision", 0)
        laya = result.get("laya") or {}
        summary["laya"] = {
            "grade": laya.get("contract", {}).get("grade", laya.get("grade")),
            "auto_execute": laya.get("auto_execute") is True,
            "summary": laya.get("contract", {}).get("summary", laya.get("summary")),
        } if laya else None
        return copy.deepcopy(summary)

    def snapshot(self, *, compact=False, run_id=None):
        with self.lock:
            if compact:
                data = copy.deepcopy({key: value for key, value in self.data.items() if key != "runs"})
                selected = run_id if any(r["id"] == run_id for r in self.data["runs"]) else next((r["id"] for r in self.data["runs"]), None)
                data["runs"] = []
                data["research"] = {}
                for run in self.data["runs"]:
                    results = run.get("results", [])
                    counts = {status: sum(r.get("status") == status for r in results)
                              for status in ("completed", "failed", "cancelled", "running")}
                    counts["queued"] = max(0, len(run["symbols"]) - len(results))
                    summary = {key: copy.deepcopy(value) for key, value in run.items()
                               if key not in {"results", "config", "events", "source_evidence", "portfolio_evidence", "gateway_evidence"}}
                    if "gateway_evidence" in run:
                        summary["gateway_evidence"] = {
                            key: copy.deepcopy(value) for key, value in run["gateway_evidence"].items()
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
                                "laya": {key: status["laya"].get(key) for key in
                                         ("grade", "auto_execute")} if status["laya"] else None,
                            }
                return data
            return copy.deepcopy(self.data)

    def save(self):
        with self.lock:
            temporary = self.path.with_suffix(".tmp")
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(self.data, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            # Windows indexers can briefly hold the destination open. Retry
            # only this local atomic rename; never repeat broker operations.
            for attempt in range(3):
                try:
                    os.replace(temporary, self.path)
                    break
                except PermissionError:
                    if attempt == 2:
                        raise
                    time.sleep(0.05 * (attempt + 1))

    def write_measurements(self, run_id, measurements):
        """Write once under the existing run report path; never replace prior evidence."""
        return self._write_json_artifact(run_id, "measurements", measurements)

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
        if receipt.get("origin") == "gateway":
            self._record_gateway_attempt(run_id, receipt, output)
            return
        with self.lock:
            run = next(r for r in self.data["runs"] if r["id"] == run_id)
            evidence = run["source_evidence"]
            attempt = next((r for r in evidence["attempts"] if r["attempt_id"] == receipt["attempt_id"]), None)
            if attempt is None:
                attempt = {}
                evidence["attempts"].append(attempt)
            attempt.update(copy.deepcopy(receipt))
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
            try:
                self.save()
            except OSError:
                evidence["capture_complete"] = False
                evidence["persistence_error"] = "Journal checkpoint failed; durability is unavailable."
                # Retain the receipt in memory for the run's next existing journal save.

    @staticmethod
    def _gateway_counts(evidence):
        attempts = evidence.get("attempts", [])
        evidence["counts"] = {
            kind: {category: sum(a["boundary_kind"] == kind and a["category"] == category for a in attempts)
                   for category in ("source", "control_plane")}
            for kind in ("gateway_invocation", "gateway_logical", "gateway_discovery", "gateway_transport")
        }
        evidence["pending_count"] = sum(a["outcome"] == "running" for a in attempts)
        evidence["unknown_count"] = sum(a["outcome"] == "unknown" for a in attempts)
        evidence["late_count"] = sum(a.get("late", False) for a in attempts)
        evidence["capture_complete"] = not (
            evidence["pending_count"] or evidence["unknown_count"] or evidence["late_count"]
            or evidence.get("persistence_error") or any(a.get("capture_error") for a in attempts)
        )

    def _record_gateway_attempt(self, run_id, receipt, output):
        with self.lock:
            run = next(r for r in self.data["runs"] if r["id"] == run_id)
            evidence = run.setdefault("gateway_evidence", {
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
                reference = self._write_source_result(run_id, receipt["attempt_id"], body, "gateway-receipt")
                attempt["receipts"].append(reference)
                attempt["capture"] = "recorded" if receipt["capture_eligible"] else "metadata_only"
            except (OSError, TypeError, ValueError, OverflowError, RecursionError) as exc:
                attempt["capture"] = "unavailable"
                attempt["capture_error"] = (
                    "persistence_failed" if isinstance(exc, OSError) else "unsafe_oversized_or_unsupported_response"
                )
            self._gateway_counts(evidence)
            if evidence.get("terminal_observed_at"):
                self._snapshot_gateway_evidence(run, "late_update")
            try:
                self.save()
            except OSError:
                evidence.update(capture_complete=False, persistence_error="Gateway journal checkpoint failed.")

    def _snapshot_gateway_evidence(self, run, reason):
        evidence = run["gateway_evidence"]
        self._gateway_counts(evidence)
        snapshot = {key: copy.deepcopy(value) for key, value in evidence.items() if key != "snapshots"}
        snapshot.update(run_id=run["id"], run_status=run["status"], reason=reason,
                        observed_at=datetime.now(UTC).isoformat())
        try:
            evidence.setdefault("snapshots", []).append(self._write_json_artifact(run["id"], "gateway-evidence", snapshot))
        except OSError:
            evidence.update(capture_complete=False, persistence_error="Gateway snapshot export failed.")

    def finalize_gateway_evidence(self, run):
        with self.lock:
            evidence = run.get("gateway_evidence")
            if evidence and not evidence.get("terminal_observed_at"):
                evidence["terminal_observed_at"] = datetime.now(UTC).isoformat()
                self._snapshot_gateway_evidence(run, "run_terminal")

    def _write_source_result(self, run_id, attempt_id, output, prefix="source"):
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
            raise ValueError("Source response exceeds evidence size limit.")
        # Screen bounded textual views only; successful artifacts keep the original bytes.
        # RSS can entity-escape JSON, which can itself contain escaped key delimiters.
        view = payload.decode("utf-8")  # Non-UTF-8 bodies are an explicit unsupported capture.
        marker = (r'(?i)(?:api[_ -]?key|authorization|token|password|client[_ -]?secret|secret|cookie|headers)'
                  r'''["'\s]*[:=]|bearer\s+\S+|sk-(?:proj-)?[a-zA-Z0-9_-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY''')
        for _ in range(4):
            if re.search(marker, view):
                raise ValueError("Source response may contain credentials.")
            decoded = re.sub(r'\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4})',
                             lambda match: json.loads('"' + match.group() + '"'), html.unescape(view))
            if decoded == view:
                break
            view = decoded
        else:
            raise ValueError("Source response encoding exceeds screening depth.")
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
