"""Explicit IEX history jobs and immutable cache receipts, separate from research."""

import copy
import json
from decimal import Decimal
from math import isfinite
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

from .alpaca_readonly import AlpacaREST
from .investor import decimal, digest
from .store import SourceEvidenceError

DEFAULT = {"entries": {}, "coverage": {}, "jobs": {}, "chart_calculations": {}}
TIMEFRAMES = ("1Min", "5Min", "15Min", "30Min", "1Hour", "1Day")


def chart_calendar_coverage(history):
    coverage = history.get("calendar_coverage")
    if not isinstance(coverage, dict) or set(coverage) != {"start", "end", "reference"}:
        return None
    reference = history.get("required_coverage", {}).get("provenance", {}).get("calendar_reference")
    matches = [row for row in history.get("receipts", []) if row.get("scope") == "calendar"
        and row.get("artifact") == coverage["reference"] == reference and row.get("request_path")]
    if len(matches) != 1:
        return None
    path = urlsplit(matches[0]["request_path"])
    query = parse_qs(path.query)
    if path.path != "/v2/calendar" or query != {"start": [coverage["start"]], "end": [coverage["end"]]}:
        return None
    if date.fromisoformat(coverage["start"]) > date.fromisoformat(coverage["end"]):
        raise ValueError("Recorded calendar request bounds are reversed")
    return copy.deepcopy(coverage)


def validate_chart_calculations(saved, workspace=None, resolve_artifact=None):
    from uuid import UUID

    from .evaluation import validate_chart_calculation, validate_chart_result
    from .workspace import source_pin
    rows = saved.get("chart_calculations", {})
    if not isinstance(rows, dict):
        raise ValueError("Invalid retained chart calculation registry")
    history = (workspace or {}).get("chart_definition_history", [])
    for key, item in rows.items():
        if (not isinstance(item, dict) or str(UUID(key)) != key or item.get("id") != key
                or item.get("version") != "chart-calculation-v1" or item.get("status") not in {"queued", "running", "completed", "unavailable", "interrupted", "failed"}
                or any(not isinstance(item.get(field), str) or len(item[field]) != 64 or any(c not in "0123456789abcdef" for c in item[field])
                    for field in ("spec_sha256", "definition_sha256"))):
            raise ValueError("Invalid chart calculation identity or digest")
        successful = item["status"] in {"completed", "unavailable"}
        if successful:
            if any(not isinstance(item.get(field), str) or len(item[field]) != 64
                    or any(c not in "0123456789abcdef" for c in item[field]) for field in ("result_sha256", "derivation_identity")):
                raise ValueError("Chart result identity is invalid")
        elif any(field in item for field in ("result_artifact", "result_sha256", "derivation_identity")):
            raise ValueError("Unfinished or failed calculation cannot claim a numerical result")
        execution = item.get("execution")
        if execution is not None:
            if (not isinstance(execution, dict) or set(execution) != {"budget_seconds", "queued_at", "deadline_at", "spec_sha256"}
                    or type(execution["budget_seconds"]) is not int or not 1 <= execution["budget_seconds"] <= 600
                    or execution["spec_sha256"] != item["spec_sha256"] or execution["queued_at"] != item.get("created_at")
                    or digest(execution) != item.get("execution_sha256")):
                raise ValueError("Chart execution budget or immutable admission identity changed")
            queued, deadline = datetime.fromisoformat(execution["queued_at"]), datetime.fromisoformat(execution["deadline_at"])
            if queued.utcoffset() is None or deadline.utcoffset() is None or (deadline - queued).total_seconds() != execution["budget_seconds"]:
                raise ValueError("Chart admission deadline differs from its explicit budget")
            if item["status"] in {"interrupted", "failed"} and not item.get("reason"):
                raise ValueError("Stopped chart calculation requires its actual reason")
            for name in ("started_at", "finished_at"):
                if name in item and (datetime.fromisoformat(item[name]).utcoffset() is None or datetime.fromisoformat(item[name]) < queued):
                    raise ValueError("Chart lifecycle timestamps must follow admission")
            if item["status"] not in {"queued", "running"} and "finished_at" not in item:
                raise ValueError("Terminal chart calculation requires its finish time")
        elif not successful:
            raise ValueError("Chart jobs require their frozen execution budget")
        source_pin(item.get("source_pin"))
        if datetime.fromisoformat(item["created_at"]).utcoffset() is None:
            raise ValueError("Chart calculation requires its actual capture time")
        definition = [row for row in history if row["definition"]["id"] == item.get("definition_id")
            and row["definition"]["revision"] == item.get("definition_revision") and row["sha256"] == item["definition_sha256"]]
        if workspace is not None and len(definition) != 1:
            raise ValueError("Chart calculation lacks its exact saved definition revision")
        for name in (("spec_artifact", "result_artifact") if successful else ("spec_artifact",)):
            from .evaluation import reference
            reference(item.get(name))
        if resolve_artifact is None:
            continue
        spec = resolve_artifact(item["spec_artifact"])
        if not isinstance(spec, dict):
            raise ValueError("Exact chart calculation artifact is unavailable or changed")
        validate_chart_calculation(spec)
        if (spec["spec_sha256"] != item["spec_sha256"] or spec["source_pin"] != item["source_pin"]
                or digest(spec["definition"]) != item["definition_sha256"]):
            raise ValueError("Chart specification differs from its durable identity")
        if not successful:
            continue
        result = resolve_artifact(item["result_artifact"])
        if not isinstance(result, dict):
            raise ValueError("Exact chart result artifact is unavailable or changed")
        validate_chart_result(result, spec)
        if (spec["spec_sha256"] != item["spec_sha256"] or result["result_sha256"] != item["result_sha256"]
                or result["status"] != item["status"] or result["derivation_identity"] != item["derivation_identity"]
                or spec["source_pin"] != item["source_pin"]
                or digest(spec["definition"]) != item["definition_sha256"]):
            raise ValueError("Chart calculation artifact differs from its durable identity")
    analysis = (workspace or {}).get("preferences", {}).get("chartView", {}).get("analysis")
    if analysis is not None and (analysis.get("calculation_id") not in rows
            or not rows[analysis["calculation_id"]].get("result_sha256")
            or rows[analysis["calculation_id"]].get("result_sha256") != analysis.get("result_sha256")):
        raise ValueError("Saved chart selection lacks its exact calculation result")


class HistoryResponseError(ValueError):
    """A controlled schema error which contains no provider body or credentials."""


class RequestBudget:
    def __init__(self):
        self.lock, self.next_request = threading.Lock(), 0

    def wait(self, canceled):
        while True:
            if canceled():
                raise InterruptedError("Data job canceled before its next provider request")
            with self.lock:
                delay = self.next_request - time.monotonic()
                if delay <= 0:
                    self.next_request = time.monotonic() + 1.1
                    return
            time.sleep(min(delay, .2))

    def backoff(self, seconds):
        with self.lock:
            self.next_request = max(self.next_request, time.monotonic() + seconds)


class MarketDataJobs:
    def __init__(self, service):
        self.service, self.budget = service, RequestBudget()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="stock-data")
        self.canceled, self.futures = set(), set()
        self.lock = threading.RLock()
        self.intervals = {}
        self.scan_limits = threading.local()
        def recover(saved):
            for job in saved["jobs"].values():
                if job["status"] in {"queued", "running", "canceling"}:
                    job.update(status="interrupted", message="Service stopped; unfinished symbols require explicit resume")
            for item in saved.get("chart_calculations", {}).values():
                if item["status"] in {"queued", "running"}:
                    item.update(status="interrupted", finished_at=datetime.now(UTC).isoformat(),
                        reason="Service restarted; unfinished chart work is not replayed",
                        termination={"termination_confirmed": False, "reason": "Prior process lifetime is unknown after restart"})
            return saved
        self.update(recover)
        from .market_discovery import recover_scans
        recover_scans(self)

    @property
    def database(self):
        return self.service.store.database

    def update(self, change):
        def apply(records):
            change(records["market_history"])
        return self.database.transact({"market_history": DEFAULT}, apply)["market_history"]

    def current_coverage(self, record):
        from .approval_review import read_artifact
        from .history_coverage import current, latest_calendar
        calendars, completed_calendars, now = {}, {}, datetime.now(UTC)
        for item in record.get("entries", {}).values():
            item["timeframe"] = self.timeframe(item)
        def artifact(reference):
            key = (reference.get("path"), reference.get("sha256"))
            if key not in calendars:
                calendars[key] = read_artifact(self.service.store.directory, reference)
            return calendars[key]
        calendar_meta = latest_calendar(record, artifact)
        for item in record.get("coverage", {}).values():
            item["timeframe"] = self.timeframe(item)
            if item["timeframe"] == "1Day":
                item["required_coverage"] = current(item, None, artifact, now=now, calendar_meta=calendar_meta, calendar_cache=completed_calendars)
            else:
                item["required_coverage"] = {"sufficient": False, "reasons": ["A recorded daily interval is required for baseline coverage"]}
        return record

    def timeframe(self, meta):
        if meta.get("timeframe"):
            return meta["timeframe"]
        from .approval_review import read_artifact
        reference = meta.get("last_usable_artifact") or meta.get("artifact", {})
        key = (str(self.service.store.directory.resolve()), reference.get("path"), reference.get("sha256"))
        if key not in self.intervals:
            retained = read_artifact(self.service.store.directory, reference)
            value = retained.get("timeframe") if isinstance(retained, dict) else None
            if value in TIMEFRAMES:
                self.intervals[key] = value
            return value
        return self.intervals[key]

    def state(self):
        record = self.database.read("market_history", DEFAULT)
        self.current_coverage(record["data"])
        universe = self.service.store.data["config"]["universe"]
        instruments = self.service.investor()["instruments"]
        eligibility = {symbol: {**item, "required_coverage": record["data"]["coverage"].get(symbol, {}).get("required_coverage", {
            "sufficient": False, "reasons": ["Required 252-session baseline has not been collected"]})} for symbol, item in instruments.items()}
        return {**record, "chart_analysis": self.service.chart_analysis(), "eligibility": eligibility, "coverage_counts": {"configured": len(universe),
            "complete_history": sum(record["data"]["coverage"].get(s, {}).get("required_coverage", {}).get("sufficient") is True for s in universe),
            "missing_or_incomplete": sum(record["data"]["coverage"].get(s, {}).get("required_coverage", {}).get("sufficient") is not True for s in universe),
            "holdings_outside_universe": sum(item["holding"] and symbol not in universe for symbol, item in instruments.items())},
            "local_request_budget": "At most one history/supplement request every 1.1 seconds, shared by two data workers; provider entitlement remains unverified"}

    def sources(self):
        saved = self.current_coverage(self.database.read("market_history", DEFAULT)["data"])
        result = {"history": {symbol: {"status": "available" if item.get("required_coverage", {}).get("sufficient") else "unavailable", "observed_at": item.get("captured_at"),
            "reason": item.get("error"), "input_identity": item.get("key"), "artifact": item.get("artifact"),
            "required_coverage": item.get("required_coverage")} for symbol, item in saved["coverage"].items()}}
        from .stock_evidence import DEFAULT as EVIDENCE_DEFAULT
        for symbol, observations in self.database.read("stock_evidence", EVIDENCE_DEFAULT)["data"]["observations"].items():
            for scope, item in observations.items():
                result.setdefault(scope, {})[symbol] = {"status": item["status"], "observed_at": item["captured_at"],
                    "input_identity": item["id"], "reason": "; ".join(item["gaps"]), "artifact": item.get("artifact"),
                    "effective_dates": item.get("effective_dates"), "content_sha256": item.get("content_sha256")}
        return result

    def evidence_request(self, body):
        from .stock_evidence import PROVIDERS
        provider, scopes, symbols = body.get("provider"), body.get("scopes"), body.get("symbols")
        if provider not in PROVIDERS or not isinstance(scopes, list) or not scopes or set(scopes) - PROVIDERS[provider]:
            raise ValueError("Choose an existing provider and its supported evidence scopes")
        known = self.service.investor()["instruments"]
        if not isinstance(symbols, list) or not 1 <= len(symbols) <= 1000 or any(s not in known for s in symbols):
            raise ValueError("Choose configured stocks or observed holdings")
        first, last = date.fromisoformat(body["start"]), date.fromisoformat(body["end"])
        if first > last or (last - first).days > 3660:
            raise ValueError("Choose an explicit supplementary-evidence interval up to ten years")
        identity = str(uuid4())
        job = {"id": identity, "kind": "supplementary", "status": "queued", "created_at": datetime.now(UTC).isoformat(),
            "request": {"provider": provider, "scopes": scopes, "start": first.isoformat(), "end": last.isoformat(),
                "earnings_horizon": body.get("earnings_horizon")},
            "symbols": {s: {"status": "queued"} for s in dict.fromkeys(symbols)}}
        self.update(lambda saved: saved["jobs"].update({identity: job}))
        future = self.executor.submit(self.run, identity)
        self.futures.add(future)
        future.add_done_callback(self.futures.discard)
        return self.state()

    def request(self, body):
        if str(body.get("action", "")).startswith("chart_"):
            return self.service.chart_analysis_action(body)
        today = datetime.now(ZoneInfo("America/New_York")).date()
        action = body.get("action", "start")
        if action == "evidence":
            return self.evidence_request(body)
        if action == "baseline":
            body = {**body, "start": (today - timedelta(days=730)).isoformat(), "end": today.isoformat(),
                    "asof": body.get("asof") or today.isoformat(), "purpose": "required_baseline", "timeframe": "1Day"}
        if action == "cancel":
            identity = body["id"]
            def cancel(saved):
                job = saved["jobs"][identity]
                if job["status"] not in {"queued", "running", "canceling"}:
                    raise ValueError("This data job has already finished")
                self.canceled.add(identity)
                job.update(status="canceling", message="Cancellation stops future data requests; received receipts remain saved")
            self.update(cancel)
            return self.state()
        if action == "resume":
            old = self.database.read("market_history", DEFAULT)["data"]["jobs"][body["id"]]
            if old["status"] not in {"interrupted", "canceled", "failed", "completed_with_gaps"}:
                raise ValueError("Resume an interrupted, canceled or incomplete data job")
            remaining = [s for s, item in old["symbols"].items() if item["status"] != "completed"]
            if not remaining:
                raise ValueError("No unfinished symbols remain")
            if old.get("kind") == "supplementary":
                return self.evidence_request({**old["request"], "symbols": remaining})
            body = {**old["request"], "symbols": remaining, "resumes": old["id"]}
        first, last, asof = date.fromisoformat(body["start"]), date.fromisoformat(body["end"]), date.fromisoformat(body["asof"])
        if first > last or (last - first).days > 3660 or last > today or asof > today:
            raise ValueError("Choose an explicit past/present history interval up to ten years and symbol-mapping as-of date, using America/New_York dates")
        symbols = body.get("symbols")
        if not isinstance(symbols, list) or not 1 <= len(symbols) <= 1000 or any(not isinstance(s, str) for s in symbols):
            raise ValueError("Select between 1 and 1000 configured stocks or observed holdings")
        instruments = self.service.investor()["instruments"]
        benchmark = self.service.reporting(compact=True).get("benchmark")
        benchmark_symbol = benchmark["symbol"] if benchmark and body.get("purpose") == "benchmark" else None
        if any(s not in instruments and s != benchmark_symbol for s in symbols):
            raise ValueError("Select configured symbols or observed holdings")
        adjustment = body.get("adjustment")
        if adjustment not in {"raw", "split", "dividend", "all"}:
            raise ValueError("Choose an explicit historical adjustment basis")
        timeframe = body.get("timeframe", "1Day")
        if timeframe not in TIMEFRAMES:
            raise ValueError("Unsupported chart interval; choose " + ", ".join(TIMEFRAMES))
        if body.get("purpose") in {"required_baseline", "benchmark"} and timeframe != "1Day":
            raise ValueError("Required baselines and daily benchmarks require the recorded 1Day interval")
        identity = str(uuid4())
        request = {"start": first.isoformat(), "end": last.isoformat(), "asof": asof.isoformat(), "adjustment": adjustment,
                   "timeframe": timeframe, "feed": "iex", "session": "provider_bar_aggregation", "currency": "USD"}
        job = {"id": identity, "status": "queued", "created_at": datetime.now(UTC).isoformat(), "request": request,
            "resumes": body.get("resumes"), "symbols": {s: {"status": "queued" if s == benchmark_symbol or instruments.get(s, {}).get("supported") else "unsupported",
                "error": instruments.get(s, {}).get("limitation")} for s in dict.fromkeys(symbols)}}
        job["request"]["purpose"] = body.get("purpose")
        self.update(lambda saved: saved["jobs"].update({identity: job}))
        future = self.executor.submit(self.run, identity)
        self.futures.add(future)
        future.add_done_callback(self.futures.discard)
        return self.state()

    def read(self, path, *, data, canceled):
        from tradingagents.credentials import CredentialStore
        client = AlpacaREST(connection=CredentialStore(self.service.runtime.credential_profile).connection_config())
        for attempt in range(3):
            limit = getattr(self.scan_limits, "value", None)
            if limit:
                from .market_discovery import scan_dispatch
            self.budget.wait(lambda limit=limit: canceled() or bool(limit and (limit["run_id"] in self.canceled or time.monotonic() >= limit["deadline"])))
            if limit:
                scan_dispatch(self, limit)
            try:
                return client.read_receipt(path, data=data)
            except HTTPError as exc:
                if exc.code != 429 or attempt == 2:
                    raise
                try:
                    delay = max(1, min(300, float(exc.headers.get("Retry-After", "60"))))
                except ValueError:
                    delay = 60
                self.budget.backoff(delay)
        raise ValueError("Provider retry budget exhausted")

    def listing(self, instrument):
        reference = self.database.read("market_history", DEFAULT)["data"].get("listing_provenance")
        if not reference:
            return None
        import json
        from .recovery import artifacts
        payloads = dict(artifacts(self.service.store.directory, reference))
        facts = json.loads(payloads[reference["path"]])
        if (facts.get("version") != "listing-provenance-v1" or not facts.get("captured_at")
                or not isinstance(facts.get("records"), list)):
            raise ValueError("Unsupported listing provenance artifact")
        matches = [row for row in facts["records"] if
                   (row.get("asset_id"), row.get("symbol"), row.get("exchange")) ==
                   (instrument.get("id"), instrument.get("symbol"), instrument.get("exchange"))]
        if len(matches) > 1:
            raise ValueError("Listing provenance has ambiguous instrument facts")
        return {**matches[0], "registry_reference": reference} if matches else None

    def fetch(self, identity, symbol, request):
        timeframe = request.get("timeframe", "1Day")
        if timeframe not in TIMEFRAMES:
            raise ValueError("Unsupported recorded history-job interval")
        request = {**request, "timeframe": timeframe, "feed": "iex", "session": "provider_bar_aggregation", "currency": "USD"}
        key = digest({"provider": "Alpaca", "symbol": symbol, **request})
        bars, receipts, token, tokens = {}, [], None, set()
        complete, error, error_kind = False, None, None
        calendar, instrument, calendar_reference, instrument_reference, listing = [], {}, None, None, None
        diagnostic, phase = {}, "requesting provider page"
        canceled = lambda: identity in self.canceled
        try:
            for _ in range(request.get("page_limit", 20)):
                query = {"symbols": symbol, "timeframe": timeframe, "start": request["start"] + "T00:00:00Z",
                    "end": request["end"] + "T23:59:59Z", "feed": "iex", "adjustment": request["adjustment"],
                    "asof": request["asof"], "limit": 10000}
                if timeframe != "1Day":
                    first = datetime.combine(date.fromisoformat(request["start"]), datetime.min.time(), ZoneInfo("America/New_York"))
                    last = datetime.combine(date.fromisoformat(request["end"]) + timedelta(days=1), datetime.min.time(), ZoneInfo("America/New_York"))
                    query.update(start=first.astimezone(UTC).isoformat(), end=(last - timedelta(microseconds=1)).astimezone(UTC).isoformat())
                if token:
                    query["page_token"] = token
                phase = "requesting provider page"
                response = self.read("/v2/stocks/bars?" + urlencode(query), data=True, canceled=canceled)
                diagnostic.update(response_received_at=response["received_at"], response_bytes=len(response["raw"]),
                                  pagination_field_present=isinstance(response["data"], dict) and "next_page_token" in response["data"])
                phase = "saving provider page"
                reference = self.service.store._write_source_result(identity, str(uuid4()), response["raw"].decode(),
                    prefix="iex-history", allow_pagination_cursor=True)
                receipts.append({"artifact": reference, "captured_at": response["received_at"], "source_date": response["source_date"],
                    "page_token": token, "request_path": "/v2/stocks/bars?" + urlencode(query)})
                payload = json.loads(response["raw"], parse_float=Decimal)
                phase = "validating provider page"
                if not isinstance(payload.get("bars"), dict) or set(payload["bars"]) - {symbol}:
                    raise HistoryResponseError("Provider bars do not match the requested symbol; confirm the symbol mapping/as-of date before retrying.")
                for row in payload["bars"].get(symbol, []):
                    if not all(decimal(row.get(k)) is not None and isfinite(float(row[k])) for k in ("o", "h", "l", "c", "v")) or not isinstance(row.get("t"), str):
                        raise HistoryResponseError("Provider OHLCV is missing or non-finite; the affected page cannot establish history coverage.")
                    stamp = datetime.fromisoformat(row["t"].replace("Z", "+00:00"))
                    if stamp.tzinfo is None:
                        raise HistoryResponseError("Provider bar timestamp has no timezone; no session or instant was inferred.")
                    chart_time = stamp.astimezone(ZoneInfo("America/New_York")).date().isoformat() if timeframe == "1Day" else stamp.timestamp()
                    if timeframe != "1Day" and not chart_time.is_integer():
                        raise HistoryResponseError("Intraday aggregation timestamp is not an exact UTC second; source bytes are retained.")
                    if chart_time in bars and bars[chart_time] != row:
                        raise HistoryResponseError("Provider returned conflicting values for the same bar; retain the receipts and request a fresh interval.")
                    bars[chart_time] = row
                token = payload.get("next_page_token")
                if not token:
                    complete = True
                    break
                if token in tokens:
                    raise HistoryResponseError("Provider repeated its pagination cursor; retry the interval rather than treating the partial history as complete.")
                tokens.add(token)
            else:
                error, error_kind = "Historical page budget exhausted", "pagination"
        except InterruptedError:
            error, error_kind = "Canceled before interval completion", "canceled"
        except HTTPError as exc:
            error_kind = "entitlement" if exc.code in {401, 403} else "rate_limit" if exc.code == 429 else "provider"
            error = "IEX history HTTP " + str(exc.code) + "; no feed fallback was attempted"
        except (SourceEvidenceError, HistoryResponseError) as exc:
            error, error_kind = "IEX history " + phase + " failed: " + str(exc), "evidence_capture" if isinstance(exc, SourceEvidenceError) else "response_schema"
        except ValueError:
            error, error_kind = "IEX history " + phase + " failed: the response could not be decoded or retained. Check the saved job diagnostics and retry after correcting the source format.", "response_format"
        except Exception as exc:
            error, error_kind = "IEX history " + phase + " failed (" + type(exc).__name__ + "); check the local connection and saved job diagnostics before retrying.", "transport_or_schema"
        diagnostic.update(failure_phase=phase if error else None, saved_price_pages=len(receipts), error_kind=error_kind)
        converted = []
        for chart_time, row in sorted(bars.items()):
            converted.append({"t": chart_time, "provider_timestamp": row["t"], "raw": {k: str(row[k]) for k in ("o", "h", "l", "c", "v")},
                              **{k: float(row[k]) for k in ("o", "h", "l", "c", "v")}})
        captured = datetime.now(UTC).isoformat()
        today = datetime.now(ZoneInfo("America/New_York")).date()
        scan_limit = getattr(self.scan_limits, "value", None)
        needs_calendar = timeframe == "1Day" or bool(scan_limit)
        calendar_through = (today + timedelta(days=366)).isoformat() if needs_calendar else None
        calendar_query = {"start": min((today - timedelta(days=730)).isoformat(), request["start"]) if scan_limit else
            (today - timedelta(days=730)).isoformat(), "end": calendar_through}
        metadata_cache = scan_limit.setdefault("metadata_receipts", {}) if scan_limit else {}
        calendar_coverage = None
        try:
            for path, scope in ((("/v2/calendar?" + urlencode(calendar_query), "calendar"),
                                ("/v2/assets/" + symbol, "instrument")) if needs_calendar else ()):
                if path not in metadata_cache:
                    response = self.read(path, data=False, canceled=canceled)
                    reference = self.service.store._write_source_result(identity, str(uuid4()), response["raw"].decode(), prefix="history-coverage-source")
                    metadata_cache[path] = (response, reference)
                response, reference = metadata_cache[path]
                receipts.append({"artifact": reference, "captured_at": response["received_at"], "scope": scope, "request_path": path})
                if scope == "calendar":
                    if not isinstance(response["data"], list):
                        raise ValueError("Unsupported calendar response")
                    calendar, calendar_reference = response["data"], reference
                    calendar_coverage = {**calendar_query, "reference": reference}
                else:
                    if response["data"].get("symbol") != symbol:
                        raise ValueError("Instrument provenance symbol differs")
                    instrument, instrument_reference = response["data"], reference
            listing = self.listing(instrument) if timeframe == "1Day" else None
        except Exception as exc:
            error_kind = error_kind or "coverage_source"
            error = error or "Calendar/listing provenance unavailable (" + type(exc).__name__ + ")"
        from .history_coverage import assess
        required_coverage = assess(converted, calendar, instrument, pagination_complete=complete,
            calendar_reference=calendar_reference, instrument_reference=instrument_reference, captured_at=datetime.now(UTC).isoformat(), listing=listing) if timeframe == "1Day" else {
                "sufficient": False, "reasons": ["Intraday chart bars do not establish the required daily baseline"],
                "provenance": {"calendar_reference": calendar_reference, "instrument_reference": instrument_reference,
                    "asset_id": instrument.get("id"), "exchange": instrument.get("exchange")}}
        result = {"key": key, "symbol": symbol, "context": "current", "run_id": None, "research_date": None,
            "provider": "Alpaca", "session_timezone": "America/New_York", **request,
            "time_basis": "provider_business_day" if timeframe == "1Day" else "utc_epoch_seconds",
            "coverage_scope": "Provider pagination is distinct from verified session completeness, bar finality and execution permission.",
            "captured_at": captured, "bars": converted, "complete": complete, "pagination_complete": complete,
            "required_coverage": required_coverage, "calendar_through": calendar_through, "calendar_coverage": calendar_coverage,
            "pages": len([r for r in receipts if "page_token" in r]), "receipts": receipts,
            "error": error, "error_kind": error_kind, "diagnostic": diagnostic, "indicators": [], "claims": [], "problems": [error] if error else [],
            "price_basis": "Current-market " + timeframe + " provider-aggregated OHLCV · " + request["adjustment"] + " adjustment · IEX only",
            "source": {"vendor": "Alpaca IEX", "captured_at": captured},
            "missing_fields": [] if converted else ["daily_ohlcv" if timeframe == "1Day" else "intraday_ohlcv"], "supplementary_gaps": ["news", "earnings", "business_facts", "corporate_actions"]}
        self.derive(result)
        result["artifact"] = self.service.store._write_json_artifact(identity, "iex-history-cache", result)
        meta = {k: result[k] for k in ("key", "symbol", "captured_at", "complete", "pagination_complete", "required_coverage", "calendar_through", "pages", "error", "error_kind", "diagnostic", "artifact", "missing_fields")}
        meta.update(request)
        def save(saved):
            previous = saved["entries"].get(key)
            meta["revision"] = previous.get("revision", 0) + 1 if previous else 1
            meta["prior_artifacts"] = previous.get("prior_artifacts", []) + [previous["artifact"]] if previous else []
            if previous and previous.get("complete") and (not complete or not converted):
                meta["last_usable_artifact"] = previous["artifact"]
            elif previous and previous.get("last_usable_artifact") and not complete:
                meta["last_usable_artifact"] = previous["last_usable_artifact"]
            saved["entries"][key] = meta
            prior_baseline = saved["coverage"].get(symbol, {})
            if timeframe != "1Day":
                pass  # Chart-only caches never replace daily evidence coverage.
            elif (required_coverage["sufficient"] or not prior_baseline.get("required_coverage", {}).get("sufficient")
                    or prior_baseline["required_coverage"].get("latest_completed_session") != required_coverage.get("latest_completed_session")):
                saved["coverage"][symbol] = copy.deepcopy(meta)
            else:
                prior_baseline["last_chart_attempt"] = copy.deepcopy(meta)
            saved["jobs"][identity]["symbols"][symbol] = {"status": "completed" if complete else "canceled" if canceled() else "failed", "error": error, "error_kind": error_kind, "diagnostic": diagnostic, "key": key}
        self.update(save)

    def run(self, identity):
        try:
            self.update(lambda saved: saved["jobs"][identity].update(status="running"))
            job = self.database.read("market_history", DEFAULT)["data"]["jobs"][identity]
            for symbol, item in job["symbols"].items():
                if identity in self.canceled:
                    break
                if item["status"] != "unsupported":
                    if job.get("kind") == "supplementary":
                        from .stock_evidence import fetch, usable
                        results = {}
                        for scope in job["request"]["scopes"]:
                            if identity in self.canceled:
                                break
                            observation = fetch(self, identity, symbol, scope, job["request"]["provider"], job["request"])
                            results[scope] = {"status": observation["status"], "complete": observation["complete"], "gaps": observation["gaps"], "scope": scope}
                        self.update(lambda saved: saved["jobs"][identity]["symbols"][symbol].update(
                            status="completed" if len(results) == len(job["request"]["scopes"]) and all(usable(v) for v in results.values()) else "failed", results=results))
                    else:
                        self.fetch(identity, symbol, job["request"])
            def finish(saved):
                job = saved["jobs"][identity]
                job.update(status="canceled" if identity in self.canceled else "completed" if all(v["status"] == "completed" for v in job["symbols"].values()) else "completed_with_gaps", completed_at=datetime.now(UTC).isoformat())
            self.update(finish)
        except Exception as exc:
            self.update(lambda saved, problem=type(exc).__name__: saved["jobs"][identity].update(status="failed", message="Data job stopped (" + problem + "); received evidence remains saved"))

    def derive(self, result):
        from .history_coverage import indicator_observations
        from .market_evidence import derive_indicators
        source = {**{key: value for key, value in result.get("source", {}).items() if key not in {"path", "sha256"}}, **{key: result.get(key) for key in
            ("symbol", "feed", "timeframe", "currency", "session", "session_timezone", "adjustment")},
            "symbol_mapping_asof": result.get("asof"), "full_history": result.get("pagination_complete") is True,
            "precision": "provider decimal strings; Stockstats float64 calculation",
            "history_hashes": [row["artifact"]["sha256"] for row in result.get("receipts", []) if "page_token" in row],
            "instrument": result.get("required_coverage", {}).get("provenance", {}).get("asset_id")}
        coverage = {"indicator_observations": indicator_observations(result.get("bars", []), result.get("required_coverage", {}),
            captured_at=result["captured_at"], timeframe=result["timeframe"])}
        try:
            result["indicators"] = derive_indicators(result.get("bars", []), source, coverage=coverage)
        except (ValueError, TypeError, KeyError) as exc:
            result["indicators"] = []
            result.setdefault("problems", []).append("Indicator derivation unavailable (" + type(exc).__name__ + ")")
        result["indicator_evidence"] = coverage
        result["derivation_identity"] = digest(sorted([
            {"name": series["name"], "derivation_identity": series.get("derivation_identity") or digest(series)}
            for series in result["indicators"]], key=lambda item: (item["name"], item["derivation_identity"])))

    def detail(self, symbol, key=None, *, timeframe="1Day", artifact=None):
        if timeframe not in TIMEFRAMES:
            raise ValueError("Unsupported chart interval")
        record = self.database.read("market_history", DEFAULT)["data"]
        entries = record["entries"]
        candidates = [v for v in entries.values() if v["symbol"] == symbol and (v["key"] == key if key else self.timeframe(v) == timeframe)]
        if not candidates:
            return {"symbol": symbol, "context": "current", "timeframe": timeframe, "bars": [], "complete": False, "error_kind": "missing_retained_bars",
                    "error": "No matching retained history; request the selected interval explicitly"}
        meta = max(candidates, key=lambda item: item["captured_at"])
        reference = meta.get("last_usable_artifact") or meta["artifact"]
        if artifact is not None:
            retained = [meta.get("artifact"), meta.get("last_usable_artifact"), *meta.get("prior_artifacts", [])]
            if not any(ref and all(ref.get(field) == artifact.get(field) for field in ("path", "sha256")) for ref in retained):
                raise ValueError("Pinned history artifact is not retained for this exact cache")
            reference = artifact
        path = (self.service.store.directory / reference["path"]).resolve()
        if not path.is_relative_to(self.service.store.directory.resolve()):
            raise ValueError("History cache reference escapes its boundary")
        import json
        payload = path.read_bytes()
        import hashlib
        if hashlib.sha256(payload).hexdigest() != reference["sha256"]:
            raise ValueError("History cache artifact hash differs")
        result = json.loads(payload)
        if result.get("timeframe") not in TIMEFRAMES:
            raise ValueError("Retained history interval is missing or unsupported; no interval was inferred from its dates")
        if result.get("symbol") != symbol or result.get("key") != meta["key"] or meta.get("timeframe", result["timeframe"]) != result["timeframe"]:
            raise ValueError("Retained history identity or interval differs from the selected cache")
        result.setdefault("currency", "USD")  # Recorded Alpaca US-stock bars API default currency.
        result.setdefault("session", "provider_bar_aggregation")
        result["source"].update(path=reference["path"], sha256=reference["sha256"])
        from .history_coverage import current, latest_calendar
        from .approval_review import read_artifact
        result["required_coverage"] = result.get("required_coverage", {}) if artifact is not None else current(meta, result, lambda ref: read_artifact(self.service.store.directory, ref),
                                             calendar_meta=latest_calendar(record, lambda ref: read_artifact(self.service.store.directory, ref))) if result["timeframe"] == "1Day" else {
            "sufficient": False, "reasons": ["Intraday chart bars do not establish the required daily baseline"]}
        result["latest_attempt"] = None if artifact is not None else meta
        result["retained_older_data"] = reference.get("sha256") != meta["artifact"].get("sha256")
        self.derive(result)
        return result

    def close(self):
        from .market_discovery import DEFAULT as DISCOVERY
        self.canceled.update(run["id"] for run in self.database.read("discovery", DISCOVERY)["data"].get("runs", {}).values()
            if run["status"] in {"queued", "running", "canceling"})
        for job in self.database.read("market_history", DEFAULT)["data"]["jobs"].values():
            if job["status"] in {"queued", "running"}:
                self.canceled.add(job["id"])
        self.executor.shutdown(wait=False, cancel_futures=True)
