"""Atomic local journal. Unknown broker submissions are never retried blindly."""

from __future__ import annotations

import copy
import hashlib
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
            if run["status"] in {"queued", "running", "cancelling"}:
                run["status"] = "interrupted"
                run["error"] = "Server stopped during analysis. Start a new run."
            if run["status"] in {"completed", "failed", "cancelled", "interrupted"}:
                self._recover_measurements(run)
                evidence = run.get("source_evidence")
                if evidence and any(a["outcome"] == "running" for a in evidence["attempts"]):
                    evidence.update(capture_complete=False, persistence_error="Source attempt interrupted; final outcome unavailable.")
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
                               if key not in {"results", "config", "events", "source_evidence"}}
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
        if str(UUID(run_id)) != run_id:
            raise ValueError("Invalid run ID for measurement export.")
        relative = Path("reports") / run_id / f"measurements-{uuid4()}.json"
        destination = self.directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(measurements, sort_keys=True, ensure_ascii=False,
                             indent=2, allow_nan=False).encode("utf-8")
        with destination.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return self._measurement_reference(destination, payload)

    def record_source_attempt(self, run_id, receipt, output=None):
        """Persist router receipts without exposing output or exception text in the journal."""
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

    def _write_source_result(self, run_id, attempt_id, output):
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
        # Withhold suspicious responses entirely; do not create a silently redacted raw artifact.
        if re.search(rb'(?i)(?:api[_ -]?key|authorization|token|password|client[_ -]?secret|secret|cookie|headers)'
                     rb'["\s]*[:=]|bearer\s+\S+|sk-(?:proj-)?[a-zA-Z0-9_-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY', payload):
            raise ValueError("Source response may contain credentials.")
        relative = Path("reports") / run_id / f"source-{attempt_id}-{uuid4()}.bin"
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
               for label in frame.columns):
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
            metadata = {"kind": type(index).__name__, "dtype": dtype_name(index.dtype),
                        "name": scalar(index.name), "values": [scalar(v) for v in index]}
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
