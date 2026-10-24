"""The application boundary for evidence, portfolio state and configured Alpaca execution."""

from __future__ import annotations

import asyncio
import copy
import csv
import hashlib
import json
import math
import os
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager, nullcontext, suppress
from contextvars import copy_context
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from cli.stats_handler import StatsCallbackHandler
from tradingagents.agents.post_screen import SOCIAL_ADMISSION_VERSION, laya_screen
from tradingagents.dataflows.router import capture_vendor_evidence, observe_source_call
from tradingagents.default_config import build_default_config
from tradingagents.integrations.maenifold import (
    GatewayError,
    GatewayRateLimited,
    GatewayRejected,
    MaenifoldGateway,
    build_langchain_tools,
)
from tradingagents.llm_clients.api_key_env import PROVIDER_API_KEY_ENV

from .config import DeskConfig
from .alpaca_readonly import DEFAULT_CREDENTIALS
from .nautilus_runtime import NautilusRuntime
from .store import DeskStore, call_evidence_failed, source_attempt_failed

TERMINAL = {"filled", "canceled", "cancelled", "expired", "rejected", "replaced"}
OWNED_TERMINAL = {"filled", "canceled", "expired", "rejected"}
OWNED_ACTIVE = {"new", "accepted", "pending_new", "partially_filled", "pending_cancel", "held"}
CANCEL_UNCERTAIN = {"intent", "requested", "unknown"}
REPORT_KEYS = (
    "market_report",
    "sentiment_report",
    "news_report",
    "fundamentals_report",
    "investment_plan",
    "trader_investment_plan",
    "final_trade_decision",
)
DESK_ANALYSTS = ("market", "social", "news", "fundamentals")
ANALYST_REPORTS = ("market_report", "sentiment_report", "news_report", "fundamentals_report")


def now():
    return datetime.now(UTC).isoformat()


def today():
    return datetime.now(ZoneInfo("America/New_York")).date().isoformat()


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def _payload(value):
    if isinstance(value, dict) and value.get("success") is True and "data" in value:
        return value["data"]
    return value


def _as_list(value, field):
    value = _payload(value)
    if isinstance(value, dict):
        value = value.get(field)
    if not isinstance(value, list):
        raise ValueError(f"Broker {field} response is not a list.")
    return value


def normalize_quotes(raw):
    raw = _payload(raw)
    if isinstance(raw, dict) and isinstance(raw.get("snapshots"), dict):
        raw = raw["snapshots"]
    if not isinstance(raw, dict):
        raise ValueError("Broker snapshots response is not an object.")
    result = {}
    for symbol, snapshot in raw.items():
        if not isinstance(snapshot, dict):
            continue
        trade = snapshot.get("latestTrade", snapshot.get("latest_trade", {})) or {}
        bar = snapshot.get("dailyBar", snapshot.get("daily_bar", {})) or {}
        previous = snapshot.get("prevDailyBar", snapshot.get("previous_daily_bar", {})) or {}
        quote = snapshot.get("latestQuote", snapshot.get("latest_quote", {})) or {}
        price = _number(trade.get("p", trade.get("price")))
        timestamp = trade.get("t", trade.get("timestamp"))
        if price is None:
            price = _number(bar.get("c", bar.get("close")))
            timestamp = bar.get("t", bar.get("timestamp"))
        close = _number(previous.get("c", previous.get("close")))
        bid_present = "bp" in quote or "bid_price" in quote
        ask_present = "ap" in quote or "ask_price" in quote
        bid = _number(quote.get("bp", quote.get("bid_price")))
        ask = _number(quote.get("ap", quote.get("ask_price")))
        result[symbol] = {
            "price": price,
            "change_pct": (price / close - 1) * 100 if price is not None and close else None,
            "timestamp": timestamp,
            "bid": bid,
            "ask": ask,
            "invalid_quote": (bid_present and (bid is None or bid <= 0)) or (ask_present and (ask is None or ask <= 0)) or (bid is not None and ask is not None and bid > ask),
            "volume": _number(bar.get("v", bar.get("volume"))),
            "feed": "iex",
        }
        if bid_present or ask_present:
            result[symbol]["quote_timestamp"] = quote.get("t", quote.get("timestamp"))
    return result


def desk_execution_policy(config):
    return ("Research is advisory. NautilusTrader owns account and order lifecycle. "
            "The investor chooses the quantity, reviews configured rules, approves exact terms "
            "and explicitly submits any order. Ratings and price levels do not grant order authority.")


def research_quote_context(symbol, trade_date, market):
    if trade_date != today():
        return "Nautilus quote omitted for historical analysis."
    quote = market.get("quotes", {}).get(symbol)
    return (
        "Nautilus / Alpaca IEX quote observation: "
        + json.dumps({"symbol": symbol, "quote": quote, "market_open": (market.get("clock") or {}).get("is_open"),
                      "account_observed_at": market.get("updated_at")}, allow_nan=False)
        + "\nPrice follows the reported basis: last_trade or bid/ask quote_midpoint; it is not an official close. "
        "Missing quotes are unavailable, not zero. Respect the source timestamp and stale flag. "
        "This research observation grants no order authority; execution requires separate exact human approval and submission."
    )


class DeskService:
    def __init__(self, directory: Path, gateway=None, graph_factory=None, runtime=None,
                 browse_only=False, history_dir=None, migrate_legacy=False):
        defaults = build_default_config()
        defaults["llm_provider"] = os.getenv("TRADINGAGENTS_LLM_PROVIDER", "chatgpt")
        settings = DeskConfig(**{k: defaults[k] for k in DeskConfig.model_fields if k in defaults})
        from .recovery import active_paths, writer_lease
        self.application_root = Path(directory).resolve()
        self.writer_lease = writer_lease(self.application_root)
        active_directory, active_history = active_paths(self.application_root, history_dir)
        self.store = DeskStore(active_directory, settings.model_dump(), migrate_legacy=migrate_legacy)
        self.maintenance = threading.RLock()
        self.restore_candidates = {}
        self.research_futures = set()
        self.instance_id, self.state_sequence = str(uuid4()), 0
        self.company_names = {}
        for filename in ("constituents.csv", "sp500-constituents.csv"):
            try:
                with (self.store.directory / filename).open(encoding="utf-8-sig", newline="") as source:
                    self.company_names.update({r["Symbol"]: r["Company"] for r in csv.DictReader(source)})
            except (OSError, KeyError, csv.Error):
                continue
        self.browse_only = browse_only
        self.history = {"runs": [], "drafts": []}
        self.history_error = None
        self.history_directory = active_history
        history_path = active_history / "desk.json" if active_history else None
        if history_path and history_path.resolve() != self.store.path.resolve() and (history_path.is_file() or history_path.with_name("desk.sqlite3").is_file()):
            try:
                self.history = DeskStore.read_existing(history_path.parent)
            except (OSError, ValueError) as exc:
                self.history_error = f"Saved history unavailable ({type(exc).__name__})"
        self.runtime = runtime or NautilusRuntime(
            Path(directory) / "nautilus", Path(__file__).resolve().parents[2] / ".venv-nautilus-v1" / "Scripts" / "python.exe", DEFAULT_CREDENTIALS)
        DeskConfig.model_validate(self.store.data["config"])
        self.configure_symbols()
        self.gateway = gateway or MaenifoldGateway(timeout=90)
        self.graph_factory = graph_factory
        self.lock = threading.RLock()
        self.execution_lock = threading.Lock()
        self.refresh_lock = threading.Lock()
        self.quotes_next_refresh = 0.0
        self.account_lock = threading.Lock()
        self.account_status = None
        self.chart_lock = threading.Lock()
        self.chart_cache = {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paper-analysis")
        self.simulation_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="saved-plan-simulation")
        self.chart_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chart-calculation")
        self.simulation_closed = False
        self.simulation_process_lock, self.simulation_processes = threading.Lock(), set()
        self.experiment_processes = {}
        self.chart_jobs = {}
        self.simulation_session = str(uuid4())
        self.cancelled = set()
        self._account_observation = None
        self.market = {
            "connection": {
                "connected": False,
                "paper_verified": False,
                "endpoint": getattr(self.gateway, "endpoint", "http://localhost:8080/mcp"),
                "domains": [],
                "message": "Connect to load the configured Alpaca account.",
            },
            "account": None,
            "positions": [],
            "orders": [],
            "quotes": {},
            "history": {},
            "bars": {},
            "clock": None,
            "errors": [],
            "updated_at": None,
        }
        from .admission import CommandAdmission
        self.admission = CommandAdmission(self.store.database, self.runtime.state,
            review_enabled=not browse_only, admission_enabled=not browse_only, execution_enabled=not browse_only)
        self.runtime.authority_database = self.store.database.path.resolve()
        self.admission.recover()
        self.runtime.observers.append(self._observe_runtime)
        from .market_history import MarketDataJobs
        self.data_jobs = MarketDataJobs(self)
        from .attention import AttentionMonitor
        from .market_discovery import due_scans
        self.attention_monitor = AttentionMonitor(self.store.database, self.attention_context, self.maintenance,
            tick=lambda: (self._expire_charts(), due_scans(self.data_jobs)))
        self.attention_monitor.start()

    def _observe_runtime(self, observation):
        from .admission import DEFAULT
        with self.maintenance:
            if self.store.database.read("commands", DEFAULT)["data"]["recovery_required"]:
                self.admission.reconcile()
            else:
                self.admission.observe_current(self.runtime.state())

    def attention_context(self):
        runtime = self.runtime.state()
        market = self._runtime_market()
        saved = self._saved_research_index(bind_attention=True)
        symbols = set(self.store.data["config"]["universe"]) | {p["symbol"] for p in runtime.get("positions", [])}
        sources = {scope: {} for scope in ("quote", "account", "research", "history", "news", "earnings", "fundamentals", "corporate_actions", "classification")}
        for symbol in symbols:
            for scope in ("history", "news", "earnings", "fundamentals", "corporate_actions", "classification"):
                sources[scope][symbol] = {"status": "missing", "observed_at": None,
                    "reason": "No saved " + scope + " observation; provider coverage is not established"}
            quote = market["quotes"].get(symbol, {})
            sources["quote"][symbol] = {"status": "available" if quote.get("price") is not None and market["connection"]["connected"] else "unavailable",
                "price": quote.get("price"), "change_pct": quote.get("change_pct"), "observed_at": quote.get("timestamp"),
                "reason": quote.get("error"), "checked_at": quote.get("checked_at"),
                **{key: quote.get(key) for key in ("basis", "feed", "source_id", "instrument_id", "native_epoch", "source_event_ns", "source_received_ns")}}
            result = saved.get(symbol)
            sources["research"][symbol] = {"status": "available" if result and result.get("status") == "completed" else "missing",
                "observed_at": result.get("observed_at") if result else None, "run_id": result.get("run_id") if result else None,
                "time_basis": result.get("time_basis") if result else None, "trade_date": result.get("trade_date") if result else None,
                "revision": result.get("revision") if result else None,
                **{key: result.get(key) if result else None for key in ("result_sha256", "market_source_sha256")}, "reason": (None if result.get("observed_at") else
                    "Saved research has only an analysis date; completion age is unavailable") if result else "No saved research for this stock"}
        sources["account"]["account"] = {"status": "available" if market["connection"]["connected"] and market.get("reconciliation", {}).get("status") == "reconciled" else "unavailable",
            "observed_at": runtime.get("account_at"), "account_id": (runtime.get("account") or {}).get("id"),
            "reason": market["connection"].get("message")}
        if getattr(self, "data_jobs", None):
            for scope, values in self.data_jobs.sources().items():
                sources[scope].update(values)
        proposals = self.investor()["data"]["proposals"]
        for proposal in proposals:
            if (proposal["impact"].get("account_at") != runtime.get("account_at") or runtime.get("status") != "connected"
                    or runtime.get("reconciliation", {}).get("status") != "reconciled"):
                proposal["conditions_stale"] = True
        return {"sources": sources, "research": saved, "universe_count": len(self.store.data["config"]["universe"]),
                "symbols": symbols, "proposals": {p["id"]: p for p in proposals}, "indicators": self.attention_indicators(),
                "drawings": self.attention_drawings(),
                "store_generation": self.store.directory.resolve().as_posix()}

    @staticmethod
    def drawing_scope(detail):
        source = detail.get("source") or {}
        return {"symbol": detail["symbol"], "timeframe": detail.get("timeframe", "1Day"),
            "context": "current" if detail.get("context") == "current" else "saved", "unit": "price",
            **{key: detail.get(key) if detail.get(key) is not None else source.get("vendor" if key == "provider" else key)
               for key in ("instrument_id", "currency", "provider", "feed", "adjustment", "session")},
            "instrument_id": detail.get("instrument_id") or source.get("instrument_id") or detail.get("required_coverage", {}).get("provenance", {}).get("asset_id")}

    def attention_drawings(self):
        """Resolve saved geometry against the selected retained series, never collect data."""
        from .attention import DEFAULT, atoms, drawing_geometry, drawing_history_points, drawing_key
        from .investor import digest
        from .workspace import DEFAULT as WORKSPACE
        workspace = self.store.database.read("workspace", WORKSPACE)["data"]
        values = {}
        for rule in self.store.database.read("attention", DEFAULT)["data"]["rules"].values():
            if not rule["active"] or rule["removed"]:
                continue
            for atom in atoms(rule):
                if atom["kind"] != "drawing":
                    continue
                params, symbol = atom["parameters"], rule["symbol"]
                key = drawing_key(symbol, params)
                if key in values:
                    continue
                try:
                    drawing = params["drawing"]
                    current = workspace.get("drawings", {}).get(drawing["id"])
                    if current != drawing or drawing.get("deleted") or drawing_geometry(drawing) != params["drawing_ref"]["geometry_sha256"]:
                        raise ValueError("Drawing edited/deleted; explicitly rebind its saved revision before monitoring")
                    self.validate_drawing_sources({drawing["id"]: drawing})
                    research = params["context"] == "research"
                    detail = self.chart(symbol, run_id=params["run_id"]) if research else self.data_jobs.detail(symbol, params["history_key"], timeframe=params["timeframe"])
                    scope = self.drawing_scope(detail)
                    if scope != drawing["scope"] or any(scope.get(field) in (None, "") for field in
                            ("instrument_id", "currency", "provider", "feed", "adjustment", "session")):
                        raise ValueError("Exact instrument/currency/provider/feed/session/adjustment drawing scope is unavailable or differs")
                    source = detail.get("source") or {}
                    binding = {**scope, "observed_at": detail.get("captured_at") or source.get("captured_at"),
                        "key": detail.get("key"), "artifact": {k: source[k] for k in ("path", "sha256", "format") if k in source},
                        "content_sha256": source.get("sha256"), "status": "available"}
                    binding["eligibility_evidence"] = copy.deepcopy(detail.get("required_coverage"))
                    if not source.get("path") or not source.get("sha256"):
                        raise ValueError("Retained history artifact identity is unavailable")
                    if research:
                        run = self.run_detail(params["run_id"])
                        result = copy.deepcopy(next(row for row in run["results"] if row["symbol"] == symbol))
                        binding.update(run_id=run["id"], revision=result.get("revision", 0), result_sha256=digest(result),
                            market_source_sha256=self._attention_market_signature(run, symbol),
                            artifact_store="application" if any(row["id"] == run["id"] for row in self.store.data["runs"]) else "history")
                    states = detail.get("indicator_evidence", {}).get("indicator_observations", {})
                    if not states and detail.get("indicators"):
                        states = {str(point["t"]): point for point in detail["indicators"][0].get("points", [])}
                    values[key] = {"points": drawing_history_points(detail.get("bars", []), states), "source": binding,
                        "selected_time": detail.get("required_coverage", {}).get("latest_completed_session") if params["timeframe"] == "1Day" else None,
                        "comparable_identity": digest({"scope": scope, "selection": {name: params.get(name) for name in
                            ("context", "history_key", "run_id", "timeframe")}, "store_generation": self.store.directory.resolve().as_posix()})}
                except (ValueError, KeyError, TypeError, OSError, StopIteration) as exc:
                    values[key] = {"points": [], "source": {}, "error": str(exc)}
        return values

    def attention_indicators(self):
        """Derive requested conditions from retained inputs only; never queue collection."""
        from .attention import DEFAULT, atoms, indicator_key
        from .investor import digest
        values = {}
        for rule in self.store.database.read("attention", DEFAULT)["data"]["rules"].values():
            if not rule["active"] or rule["removed"]:
                continue
            symbols = [m["symbol"] for m in rule["memberships"].values() if m["status"] == "monitoring"] if "memberships" in rule else [rule["symbol"]]
            for atom in atoms(rule):
                if atom["kind"] != "indicator":
                    continue
                params = atom["parameters"]
                for symbol in symbols:
                    key = indicator_key(symbol, params)
                    if key in values:
                        continue
                    try:
                        research = params["context"] == "research"
                        detail = self.chart(symbol, run_id=params["run_id"]) if research else self.data_jobs.detail(
                            symbol, params.get("history_key") or None, timeframe=params["timeframe"])
                        if not research and detail.get("timeframe") != params["timeframe"]:
                            raise ValueError("Selected indicator cache interval differs")
                        source = detail.get("source") or {}
                        binding = {"observed_at": source.get("captured_at") or detail.get("captured_at"),
                            "status": "available" if detail.get("indicators") else "unavailable", "key": detail.get("key"),
                            "artifact": {k: source[k] for k in ("path", "sha256", "format") if k in source} if source.get("sha256") else None,
                            "content_sha256": source.get("sha256"), "provider": source.get("vendor"),
                            **{k: detail.get(k, source.get(k)) for k in ("feed", "timeframe", "adjustment", "currency", "session")}}
                        if research:
                            run = self.run_detail(params["run_id"])
                            result = copy.deepcopy(next(r for r in run["results"] if r["symbol"] == symbol))
                            result.setdefault("revision", 0)
                            binding.update(run_id=run["id"], revision=result["revision"], result_sha256=digest(result),
                                market_source_sha256=self._attention_market_signature(run, symbol),
                                artifact_store="application" if any(r["id"] == run["id"] for r in self.store.data["runs"]) else "history")
                        values[key] = {"series": detail.get("indicators", []), "source": binding, "error": detail.get("error"),
                            "selected_time": detail.get("required_coverage", {}).get("latest_completed_session")
                                if not research and detail.get("timeframe") == "1Day" else None}
                    except (ValueError, KeyError, TypeError, OSError, StopIteration) as exc:
                        values[key] = {"series": [], "source": {}, "error": "Retained indicator input unavailable (" + type(exc).__name__ + ")"}
        return values

    def attention(self):
        from .attention import DEFAULT, OBSERVATIONS
        from .investor import digest
        record = self.store.database.read("attention", DEFAULT)
        bindings = self.review_source_bindings() if record["data"]["reviews"] else {}
        for review in record["data"]["reviews"].values():
            current = bindings.get(review["symbol"], {})
            prior = review.get("source_bindings")
            changed = [scope for scope in ("history", "corporate_actions")
                       if prior is None or digest(prior.get(scope)) != digest(current.get(scope))]
            review["review_required"] = bool(changed)
            review["review_reasons"] = [scope + " source revision changed or was not bound when reviewed" for scope in changed]
            review["current_source_bindings"] = current
        from .attention import drawing_geometry
        from .workspace import DEFAULT as WORKSPACE
        drawings = self.store.database.read("workspace", WORKSPACE)["data"].get("drawings", {})
        return {**record, "observations": self.store.database.read("attention_observations", OBSERVATIONS),
            "drawing_options": [{"drawing_ref": {"drawing_id": row["id"], "revision": row["revision"], "geometry_sha256": drawing_geometry(row)},
                "drawing": copy.deepcopy(row), "scope": copy.deepcopy(row["scope"])} for row in drawings.values()
                if not row.get("deleted") and row["kind"] in {"horizontal-line", "trend-line"}]}

    def review_source_bindings(self):
        sources = self.data_jobs.sources()
        symbols = set(sources.get("history", {})) | set(sources.get("corporate_actions", {}))
        return {symbol: {scope: {key: value for key, value in sources.get(scope, {}).get(symbol, {}).items()
                    if key in {"input_identity", "artifact", "required_coverage", "effective_dates", "content_sha256"}}
                for scope in ("history", "corporate_actions")} for symbol in symbols}

    def attention_occurrence(self, identity, generation):
        """Open only retained alert inputs; no provider request or latest-source substitution."""
        from uuid import UUID
        from .attention import OBSERVATIONS, drawing_coordinates, drawing_history_points, drawing_threshold
        from .approval_review import read_artifact
        from .investor import DEFAULT as INVESTOR_DEFAULT, decimal, digest
        from .recovery import references
        with self.maintenance:
            current = self.store.directory.resolve().as_posix()
            if generation != current or str(UUID(identity)) != identity:
                raise ValueError("Alert identity or application generation changed; reopen the saved occurrence")
            occurrence = self.store.database.read("attention_observations", OBSERVATIONS)["data"]["occurrences"].get(identity)
            if occurrence is None:
                raise ValueError("The saved alert occurrence is unavailable")
            result = {"store_generation": current, "occurrence": copy.deepcopy(occurrence), "sources": []}
            evidence = occurrence.get("evidence")
            if not evidence or evidence.get("version") != "occurrence-evidence-v1":
                return {**result, "evidence_status": "unavailable", "reason": "Legacy occurrence has no captured input bindings; no historical source is inferred"}
            result.update(evidence_status="captured", reason="Saved evaluated observations remain available even when a full retained source cannot be resolved")
            if evidence.get("store_generation") != current:
                return {**result, "reason": "Capture generation is different or unrecorded; evaluated facts remain readable but exact full-source association is unavailable",
                        "sources": [{"kind": "capture_generation", "status": "unavailable", "reason": "The captured generation does not match the active profile; query identity alone cannot establish source provenance"}]}
            captured_atoms = evidence.get("atoms", [evidence])
            for evidence in captured_atoms:
                source, symbol = evidence["source"], evidence["rule"]["symbol"]
                if evidence["rule"]["kind"] == "drawing":
                    facts = evidence["evaluation"].get("facts", {})
                    result["sources"].append({"kind": "drawing_revision", "status": "available", "data": {
                        name: copy.deepcopy(facts.get(name)) for name in ("drawing", "geometry_sha256", "algorithm", "geometry_policy",
                            "manual_time_mapping", "anchors", "field", "comparison", "previous_observation", "observation")}})
                    for name in ("previous_observation", "observation"):
                        observation = facts.get(name) or {}
                        retained_source = observation.get("source") or {}
                        reference = retained_source.get("artifact")
                        if not reference:
                            continue
                        try:
                            root = self.history_directory if retained_source.get("artifact_store") == "history" else self.store.directory
                            data = read_artifact(root, reference) if root else None
                            if not isinstance(data, dict) or data.get("symbol") != symbol:
                                raise ValueError("Exact retained drawing source is unavailable")
                            points = drawing_history_points(data.get("bars", []))
                            index = next((i for i, point in enumerate(points) if point["t"] == observation.get("t")), None)
                            if (index is None or points[index]["raw"] != observation.get("raw")
                                    or points[index]["history_prefix_identity"] != observation.get("history_prefix_identity")
                                    or decimal(observation.get("logical_index")) != Decimal(index)):
                                raise ValueError("Captured logical index/history prefix differs from its actual retained axis")
                            coordinates = drawing_coordinates(facts["drawing"], points)
                            if coordinates != observation.get("anchors") or drawing_threshold(facts["drawing"], coordinates, Decimal(index), facts["geometry_policy"]) != decimal(observation.get("threshold")):
                                raise ValueError("Captured drawing coordinates/threshold differ from the exact retained source")
                            result["sources"].append({"kind": "drawing_" + name, "status": "available", "reference": reference, "data": data})
                        except (ValueError, KeyError, TypeError, OSError, ArithmeticError):
                            result["sources"].append({"kind": "drawing_" + name, "status": "unavailable", "reference": reference,
                                "reason": "Exact retained bar, logical axis or geometry is missing/changed; retained drawing remains readable and current cache is not substituted"})
                    for anchor in facts.get("drawing", {}).get("points", []):
                        if anchor.get("basis") == "observed":
                            try:
                                detail = self.pinned_chart_source(anchor["source_pin"])
                                result["sources"].append({"kind": "drawing_anchor", "status": "available", "source_pin": anchor["source_pin"], "data": detail})
                            except (ValueError, KeyError, TypeError, OSError):
                                result["sources"].append({"kind": "drawing_anchor", "status": "unavailable", "source_pin": anchor["source_pin"],
                                    "reason": "Exact historical anchor input is unavailable; no current source was substituted"})
                if source.get("artifact") and evidence["rule"]["kind"] != "drawing":
                    try:
                        reference = source["artifact"]
                        next(references(reference, native_reconstruction=True))
                        artifact_root = self.history_directory if source.get("artifact_store") == "history" else self.store.directory
                        data = read_artifact(artifact_root, reference) if artifact_root else None
                        if data is None or isinstance(data, dict) and (data.get("symbol", symbol) != symbol
                                or evidence["rule"]["scope"] == "history" and data.get("key") != source.get("input_identity")):
                            raise ValueError("Exact retained source is unavailable")
                        result["sources"].append({"kind": evidence["rule"]["scope"], "status": "available", "reference": reference, "data": data})
                    except (ValueError, KeyError, TypeError, OSError, StopIteration):
                        result["sources"].append({"kind": evidence["rule"]["scope"], "status": "unavailable",
                            "reason": "The occurrence's retained artifact is missing, changed or mismatched; newer same-key data is not substituted"})
                if source.get("run_id"):
                    try:
                        run = self.run_detail(source["run_id"])
                        saved = copy.deepcopy(next(item for item in run["results"] if item["symbol"] == symbol))
                        saved.setdefault("revision", 0)
                        if saved["revision"] != source.get("revision") or digest(saved) != source.get("result_sha256"):
                            raise ValueError("Captured research revision differs")
                        result["sources"].append({"kind": "research_result", "status": "available", "run_id": run["id"], "data": saved})
                        if self._attention_market_signature(run, symbol) != source.get("market_source_sha256"):
                            raise ValueError("Captured run market sources differ")
                        from .market_evidence import recorded_market
                        root = self.store.directory if any(item["id"] == run["id"] for item in self.store.data["runs"]) else self.history_directory
                        market = recorded_market(root, run, symbol) if root else None
                        result["sources"].append({"kind": "run_instrument", "status": "partial" if market and market.get("source") and market.get("problems") else "available" if market and market.get("source") else "unavailable",
                            "reason": "; ".join(market.get("problems", [])) if market else "Retained run instrument sources are unavailable", "data": market})
                    except (ValueError, KeyError, TypeError, OSError, StopIteration):
                        result["sources"].append({"kind": "research_source", "status": "unavailable",
                            "reason": "Exact captured run/result or market-source revision is unavailable; no newer report or instrument source is substituted"})
                expected = evidence.get("proposal")
                if expected:
                    proposals = self.store.database.read("investor", INVESTOR_DEFAULT)["data"]["proposals"]
                    proposal = next((item for item in proposals if item["id"] == expected["id"]), {})
                    candidates = [proposal, *proposal.get("history", [])]
                    saved = next((item for item in candidates if item.get("revision") == expected["revision"]
                        and item.get("policy_revision") == expected["policy_revision"] and item.get("terms_sha256") == expected["terms_sha256"]
                        and digest(item.get("terms")) == expected["terms_sha256"]
                        and item.get("impact", {}).get("conditions") == expected["conditions"]), None)
                    result["sources"].append({"kind": "proposal_revision", "status": "available" if saved else "unavailable",
                        "reason": "Exact saved proposal terms and conditions" if saved else "Captured proposal revision/conditions are unavailable; newer terms are not substituted",
                        "data": {"id": expected["id"], **{key: copy.deepcopy(saved.get(key)) for key in ("revision", "policy_revision", "terms_sha256", "terms", "impact")}} if saved else None})
            return result

    def save_attention(self, request):
        from .attention import DEFAULT, OBSERVATIONS, change
        if str(request.get("action", "")).startswith("browser_"):
            from .attention import browser_delivery
            delivery = {}
            def update_browser(records):
                delivery.update(browser_delivery(records["attention_observations"], request, self.store.directory.resolve().as_posix()))
            self.store.database.transact({"attention_observations": OBSERVATIONS}, update_browser)
            return {**self.attention(), "browser_delivery": delivery}
        if request.get("action") == "acknowledge":
            def acknowledge(saved):
                occurrence = saved["occurrences"][request["id"]]
                if type(request.get("occurrence_revision")) is not int or occurrence["revision"] != request["occurrence_revision"]:
                    from .app_database import StoreConflict
                    raise StoreConflict(occurrence["revision"])
                occurrence.update(unread=False, acknowledged_at=now(), revision=occurrence["revision"] + 1)
            def update(records):
                acknowledge(records["attention_observations"])
            self.store.database.transact({"attention_observations": OBSERVATIONS}, update)
        else:
            context = self.attention_context()
            if request.get("action") == "review":
                source = self.run_detail(request["run_id"], request["symbol"])
                if source.get("status") != "completed" or source.get("revision", 0) != request.get("research_revision"):
                    raise ValueError("Review disposition must match the exact saved stock/run/revision")
                context["research"][request["symbol"]] = {**source, "run_id": request["run_id"]}
            from .workspace import DEFAULT as WORKSPACE
            bindings = self.review_source_bindings()
            def save(records):
                previous = copy.deepcopy(records["attention"]["rules"].get(request.get("id")))
                change(records["attention"], request, context["symbols"], context["research"], bindings,
                       records["workspace"], context["proposals"])
                if previous:
                    current = records["attention"]["rules"][previous["id"]]
                    if current["revision"] != previous["revision"] or current["removed"]:
                        for key, state in records["attention_observations"]["rule_states"].items():
                            if state.get("rule_id") == previous["id"] or key == previous["id"]:
                                state.update(monitoring="no_longer_monitored", removed_at=now(),
                                    reason="Rule removed or its content revised; prior latch is historical, not cleared")
                    elif current["active"] != previous["active"]:
                        for key, state in records["attention_observations"]["rule_states"].items():
                            if ((state.get("rule_id") == previous["id"] or key == previous["id"])
                                    and state.get("monitoring") != "no_longer_monitored"):
                                state["monitoring"] = "monitoring" if current["active"] else "paused"
            self.store.database.transact({"attention": DEFAULT, "workspace": WORKSPACE, "attention_observations": OBSERVATIONS}, save,
                                         expected={"attention": request.get("expected_revision")})
        return self.attention()

    def reconcile_commands(self):
        from .admission import DEFAULT as COMMAND_DEFAULT, TERMINAL
        with self.maintenance:
            runtime, store = self.runtime, self.store
        runtime.request("refresh")
        errors = {}
        for identity, command in store.database.read("commands", COMMAND_DEFAULT)["data"]["commands"].items():
            if command["state"] in {"not_sent", "admitted_not_dispatched"} or command["state"] in TERMINAL and not command.get("native_pending_commitment"):
                continue
            try:
                runtime.request("reconcile_identity", command_id=identity)
            except ValueError as exc:
                errors[identity] = str(exc)
        with self.maintenance:
            if self.runtime is not runtime or self.store is not store:
                raise ValueError("Application generation changed; refresh the current account again")
            return {**self.admission.reconcile(), "identity_errors": errors}

    def state(self, *, compact=False, run_id=None):
        journal = self.store.database.read("journal")
        with self.lock:
            market = self._runtime_market()
            data = {**copy.deepcopy(market), **self.store.snapshot(compact=compact, run_id=run_id, journal=journal["data"])}
        data.pop("paper_account_id", None)
        data["workspace"] = self.workspace()
        data["saved_research"] = self._saved_research_index(current=journal["data"]["runs"])
        data["investor"] = self.investor()
        data["health"] = self.health(journal_revision=journal["revision"])
        data["reporting"] = self.reporting(compact=True)
        data["commands"] = self.admission.snapshot()
        data["attention"] = self.attention()
        data["market_history"] = self.data_jobs.state()
        from .stock_evidence import DEFAULT as EVIDENCE_DEFAULT, configuration
        data["stock_evidence"] = {**self.store.database.read("stock_evidence", EVIDENCE_DEFAULT), "configuration": configuration()}
        data["historical_proposals"] = data.pop("proposals", [])
        data["proposals"] = []
        data["trading_paused"] = data["commands"]["data"].get("new_orders_blocked", False)
        data["readiness"] = self.readiness(data["config"], probe=False)
        data["nautilus"] = self.runtime.state()
        data["broker_mutations_enabled"] = self.admission.execution_enabled
        data["browse_only"] = self.browse_only
        data["company_names"] = {s: self.company_names[s] for s in set(data["config"]["universe"]) | {p["symbol"] for p in data.get("positions", [])} if s in self.company_names}
        data["history_error"] = self.history_error
        data["saved_account_contexts"] = [{"run_id": r["id"], **copy.deepcopy(r["portfolio_evidence"]["context"])}
            for r in journal["data"]["runs"] + self.history.get("runs", [])
            if r.get("portfolio_evidence", {}).get("context")]
        for r in journal["data"]["runs"] + self.history.get("runs", []):
            for result in r.get("results", []):
                data.setdefault("research", {}).setdefault(result["symbol"], {
                    "run_id": r["id"], **{key: result.get(key) for key in
                        ("symbol", "status", "rating", "trade_date", "revision")}})
        current_ids = {run["id"] for run in data["runs"]}
        for run in data["runs"]:
            saved_run = next((r for r in journal["data"]["runs"] if r["id"] == run["id"]), run)
            events = self._research_activity(saved_run)
            run.update(events=events[-40:], event_count=len(events))
            if "continuation" in run:
                saved = run["continuation"]
                run["continuation"] = {key: saved.get(key) for key in ("version", "revision", "blocked_reason")}
        for saved in self.history.get("runs", []):
            if saved["id"] in current_ids:
                continue
            summary = {key: copy.deepcopy(saved.get(key)) for key in (
                "id", "created_at", "completed_at", "trade_date", "symbols", "status", "config", "account_id")}
            results = saved.get("results", [])
            events = self._research_activity(saved)
            summary.update(history_source="Saved .paper-desk history (read-only)",
                results=[self.store.result_summary(r) for r in results],
                events=events[-40:], event_count=len(events),
                counts={status: sum(r.get("status") == status for r in results)
                        for status in ("completed", "failed", "cancelled", "running")})
            summary["counts"]["queued"] = max(0, len(saved["symbols"]) - len(results))
            data["runs"].append(summary)
        draft_ids = {d["order"]["client_order_id"] for d in data.get("drafts", [])}
        data["drafts"] = data.get("drafts", []) + [copy.deepcopy(d) for d in self.history.get("drafts", [])
            if d["order"]["client_order_id"] not in draft_ids]
        with self.lock:
            self.state_sequence += 1
            data.update(server_instance_id=self.instance_id, snapshot_sequence=self.state_sequence,
                        store_generation=self.store.directory.resolve().as_posix())
        return data

    @staticmethod
    def _attention_market_signature(run, symbol):
        from .investor import digest
        return digest({"trade_date": run.get("trade_date"), "attempts": [attempt for attempt in run.get("source_evidence", {}).get("attempts", [])
            if attempt.get("arguments", {}).get("symbol", attempt.get("arguments", {}).get("ticker")) == symbol
            and attempt.get("operation") in {"get_stock_data", "get_indicators", "ohlcv_history", "ohlcv_cache_read"}]})

    def _saved_research_index(self, *, bind_attention=False, current=None):
        saved = {}
        with self.store.lock if current is None else nullcontext():
            if current is None:
                self.store._refresh()
                current = self.store.data["runs"]
            for run in sorted(current + self.history.get("runs", []), key=lambda item: item.get("created_at") or "", reverse=True):
                for result in run.get("results", []):
                    if result.get("status") == "completed" and result["symbol"] not in saved:
                        completion = next((e.get("time") for e in reversed(run.get("events", []))
                                           if e.get("kind") == "complete" and e.get("symbol") == result["symbol"]), None)
                        observed = result.get("completed_at") or completion or run.get("completed_at")
                        basis = "stock_completion" if result.get("completed_at") or completion else "run_completion" if observed else "analysis_date_only"
                        saved.setdefault(result["symbol"], {"run_id": run["id"], "observed_at": observed, "time_basis": basis,
                            **{key: result.get(key) for key in ("symbol", "status", "rating", "trade_date", "revision")}})
                        if bind_attention:
                            from .investor import digest
                            bound = copy.deepcopy(result)
                            bound.setdefault("revision", 0)
                            saved[result["symbol"]].update(revision=bound["revision"], result_sha256=digest(bound),
                                market_source_sha256=self._attention_market_signature(run, result["symbol"]))
        return saved

    def workspace(self):
        from .workspace import DEFAULT
        return self.store.database.read("workspace", DEFAULT)

    def chart_analysis(self):
        from .evaluation import chart_calculation_capabilities
        from .market_history import DEFAULT
        self._expire_charts()
        record = self.workspace()
        return {"workspace_revision": record["revision"], "capabilities": chart_calculation_capabilities(),
            "definitions": list(record["data"].get("chart_definitions", {}).values()),
            "history": record["data"].get("chart_definition_history", []),
            "calculations": list(self.store.database.read("market_history", DEFAULT)["data"].get("chart_calculations", {}).values())}

    def chart_calculation(self, identity):
        from .approval_review import read_artifact
        from .evaluation import validate_chart_calculation, validate_chart_result
        from .market_history import DEFAULT
        item = self.store.database.read("market_history", DEFAULT)["data"].get("chart_calculations", {}).get(identity)
        if not item:
            raise ValueError("Choose a retained chart calculation")
        spec = read_artifact(self.store.directory, item["spec_artifact"])
        result = read_artifact(self.store.directory, item["result_artifact"]) if item.get("result_artifact") else None
        if not isinstance(spec, dict) or item.get("result_artifact") and not isinstance(result, dict):
            raise ValueError("Exact chart calculation evidence is unavailable or changed")
        validate_chart_calculation(spec)
        if result is not None:
            validate_chart_result(result, spec)
        if (spec["spec_sha256"] != item["spec_sha256"] or result is not None and result["result_sha256"] != item["result_sha256"]
                or spec["source_pin"] != item["source_pin"]):
            raise ValueError("Chart calculation differs from its retained source binding")
        return {**copy.deepcopy(item), "spec": spec, "result": result}

    def chart_analysis_action(self, request):
        from .app_database import StoreConflict
        from .approval_review import read_artifact
        from .investor import digest
        from .evaluation import (
            prepare_chart_calculation,
            validate_chart_calculation,
        )
        from .market_history import DEFAULT as HISTORY, chart_calendar_coverage
        from .workspace import (
            DEFAULT,
            chart_definition_dependencies,
            import_chart_definitions,
            save_chart_definition,
        )
        action, store = request.get("action"), self.store
        if action in {"chart_calculation_open", "chart_calculation_cancel"}:
            self._expire_charts()
            if action == "chart_calculation_cancel":
                self._interrupt_charts("cancelled", request.get("id"))
            return {"calculation": self.chart_calculation(request.get("id")), "chart_analysis": self.chart_analysis()}
        record = self.workspace()
        if type(request.get("workspace_revision")) is not int or request["workspace_revision"] != record["revision"]:
            raise StoreConflict(record["revision"])
        if action in {"chart_definition_save", "chart_definition_import"}:
            saved_id = None
            def change(records):
                nonlocal saved_id
                if action == "chart_definition_save":
                    saved_id = save_chart_definition(records["workspace"], request)
                else:
                    import_chart_definitions(records["workspace"], request.get("bundle"))
            store.database.transact({"workspace": DEFAULT}, change, expected={"workspace": record["revision"]})
            return {"chart_analysis": self.chart_analysis(), "saved_definition_id": saved_id}
        history = record["data"].get("chart_definition_history", [])
        if action == "chart_definition_export":
            rows = history
            if request.get("id"):
                matching = [row for row in history if row["definition"]["id"] == request["id"]
                    and row["definition"]["revision"] == request.get("revision") and row["sha256"] == request.get("sha256")]
                if len(matching) != 1:
                    raise ValueError("Export an exact retained definition revision")
                keys = set()
                def include(row):
                    definition = row["definition"]
                    key = (definition["id"], definition["revision"])
                    if key in keys:
                        return
                    keys.add(key)
                    dependencies = chart_definition_dependencies(record["data"], row["dependencies"])
                    for candidate in history:
                        value = candidate["definition"]
                        if (value["id"] == definition["id"] and value["revision"] < definition["revision"]
                                or any(value["id"] == dependency["id"] and value["revision"] <= dependency["revision"] for dependency in dependencies)):
                            include(candidate)
                include(matching[0])
                rows = [row for row in history if (row["definition"]["id"], row["definition"]["revision"]) in keys]
            return {"bundle": {"version": "chart-definitions-v1", "definitions": copy.deepcopy(rows)}}
        if action != "chart_calculate":
            raise ValueError("Choose a chart definition or exact retained calculation action")
        seconds = request.get("budget_seconds", 60)
        if type(seconds) is not int or not 1 <= seconds <= 600:
            raise ValueError("Chart total budget must be a whole number of seconds from 1 through 600")
        if self.simulation_closed:
            raise ValueError("Calculation admission is closed")
        matching = [row for row in history if row["definition"]["id"] == request.get("definition_id")
            and row["definition"]["revision"] == request.get("definition_revision") and row["sha256"] == request.get("definition_sha256")]
        if len(matching) != 1:
            raise ValueError("Calculate an exact saved chart definition revision")
        definition = matching[0]
        value = {**self.pinned_chart_source(request.get("source_pin")), "artifact": copy.deepcopy(request["source_pin"]["artifact"])}
        source = value.get("source") or {}
        for key in ("captured_at", "currency", "session", "adjustment"):
            value.setdefault(key, source.get(key))
        value.setdefault("timeframe", request["source_pin"]["timeframe"])
        source_path = (store.directory / value["artifact"]["path"]).resolve()
        if (not source_path.is_relative_to(store.directory.resolve()) or not source_path.is_file()
                or hashlib.sha256(source_path.read_bytes()).hexdigest() != value["artifact"]["sha256"]):
            raise ValueError("The exact source belongs to external history; retain its original evidence in this profile before calculating")
        provenance = value.get("required_coverage", {}).get("provenance", {})
        calendar_ref = provenance.get("calendar_reference")
        if calendar_ref:
            value = {**value, "calendar": read_artifact(store.directory, calendar_ref), "calendar_artifact": calendar_ref}
        value["calendar_coverage"] = chart_calendar_coverage(value)
        spec = prepare_chart_calculation(value, {"definition": definition["definition"],
            "dependencies": chart_definition_dependencies(record["data"], definition["dependencies"]),
            "source_pin": request["source_pin"]})
        validate_chart_calculation(spec)
        identity = str(uuid4())
        admitted, queued = time.monotonic(), datetime.now(UTC)
        execution = {"budget_seconds": seconds, "queued_at": queued.isoformat(),
            "deadline_at": (queued + timedelta(seconds=seconds)).isoformat(), "spec_sha256": spec["spec_sha256"]}
        item = {"id": identity, "version": "chart-calculation-v1", "status": "queued", "execution": execution,
            "execution_sha256": digest(execution),
            "created_at": queued.isoformat(), "spec_sha256": spec["spec_sha256"],
            "definition_id": definition["definition"]["id"], "definition_revision": definition["definition"]["revision"],
            "definition_sha256": definition["sha256"], "source_pin": copy.deepcopy(request["source_pin"])}
        with self.maintenance:
            if store is not self.store:
                raise ValueError("Application records changed during chart calculation; no current source was substituted")
            with self.simulation_process_lock:
                if len(self.chart_jobs) >= 2:
                    raise ValueError("Chart worker busy: at most one running and one queued request; wait or cancel your selected chart job")
            item["spec_artifact"] = store._write_json_artifact(identity, "chart-spec", spec)
            store.database.transact({"market_history": HISTORY, "workspace": DEFAULT},
                lambda records: records["market_history"].setdefault("chart_calculations", {}).update({identity: item}),
                expected={"workspace": record["revision"]})
            job = {"id": identity, "store": store, "session": self.simulation_session, "admitted": admitted,
                "deadline": admitted + seconds, "stopped": threading.Event(), "processes": set(),
                "execution_sha256": item["execution_sha256"], "reason": None}
            with self.simulation_process_lock:
                self.chart_jobs[identity] = job
            try:
                job["future"] = self.chart_executor.submit(self._run_chart, job, spec)
            except RuntimeError:
                self._finish_chart(job, "failed", "Executor rejected the queued calculation")
                with self.simulation_process_lock:
                    self.chart_jobs.pop(identity, None)
            else:
                def release(_):
                    with self.simulation_process_lock:
                        if not any(process.poll() is None for process in job["processes"]):
                            self.chart_jobs.pop(identity, None)
                job["future"].add_done_callback(release)
        return {"calculation": self.chart_calculation(identity), "chart_analysis": self.chart_analysis()}

    def _finish_chart(self, job, status, reason=None, *, result=None, termination=None):
        from .market_history import DEFAULT
        with self.maintenance:
            if self.store is not job["store"] or job["session"] != self.simulation_session:
                return
            def finish(records):
                item = records["market_history"]["chart_calculations"][job["id"]]
                if item["execution_sha256"] != job["execution_sha256"]:
                    return
                if item["status"] not in {"queued", "running"}:
                    if item["status"] == "interrupted" and termination is not None:
                        item.setdefault("termination_history", []).append(copy.deepcopy(termination))
                        if not item.get("termination", {}).get("termination_confirmed"):
                            item["termination"] = copy.deepcopy(termination)
                    return
                if job["stopped"].is_set() or time.monotonic() >= job["deadline"]:
                    status_value, why = "interrupted", job["reason"] or "deadline"
                else:
                    status_value, why = status, reason
                item.update(status=status_value, finished_at=now(), reason=why,
                    elapsed_seconds=max(0, time.monotonic() - job["admitted"]))
                if termination is None and status_value == "interrupted":
                    item["termination"] = copy.deepcopy(job.get("exit_evidence", {"termination_confirmed": False,
                        "reason": "Worker exit has not been confirmed"}))
                if termination is not None:
                    item["termination"] = copy.deepcopy(termination)
                if status_value in {"completed", "unavailable"}:
                    item.update(result_artifact=job["store"]._write_json_artifact(job["id"], "chart-result", result),
                        result_sha256=result["result_sha256"], derivation_identity=result["derivation_identity"])
            job["store"].database.transact({"market_history": DEFAULT}, finish)

    def _run_chart(self, job, spec):
        from .evaluation import execute_chart_calculation, stop_calculation_process
        from .market_history import DEFAULT
        def stopped():
            return (job["stopped"].is_set() or self.simulation_closed or self.store is not job["store"]
                or self.simulation_session != job["session"] or time.monotonic() >= job["deadline"])
        def process_state(process, active):
            with self.simulation_process_lock:
                if active:
                    job["processes"].add(process)
                    self.simulation_processes.add(process)
                elif process.poll() is not None:
                    job["processes"].discard(process)
                    self.simulation_processes.discard(process)
                    job["exit_evidence"] = {"pid": process.pid, "returncode": process.poll(), "observed_at": now(),
                        "termination_confirmed": True, "descendants_confirmed": False}
            if active and stopped():
                stop_calculation_process(process)
            if active:
                with self.maintenance:
                    if self.store is job["store"] and self.simulation_session == job["session"]:
                        def dispatched(records):
                            item = records["market_history"]["chart_calculations"][job["id"]]
                            item.update(worker_pid=process.pid, worker_started_at=now())
                        job["store"].database.transact({"market_history": DEFAULT}, dispatched)
            if not active and job["stopped"].is_set():
                self._finish_chart(job, "interrupted", job["reason"], termination={"processes": [{"pid": process.pid,
                    "returncode": process.poll(), "termination_confirmed": process.poll() is not None}],
                    "termination_confirmed": process.poll() is not None, "descendants_confirmed": False})
        try:
            with self.maintenance:
                if stopped():
                    self._finish_chart(job, "interrupted", job["reason"] or "deadline",
                        termination={"dispatch_prevented": True, "termination_confirmed": True, "descendants_confirmed": False})
                    return
                def start(records):
                    item = records["market_history"]["chart_calculations"][job["id"]]
                    item.update(status="running", started_at=now(), queue_wait_seconds=time.monotonic() - job["admitted"])
                job["store"].database.transact({"market_history": DEFAULT}, start)
            result = execute_chart_calculation(spec, self.runtime.python, process_state=process_state,
                cancelled=stopped, timeout=max(0, job["deadline"] - time.monotonic()))
            self._finish_chart(job, result["status"], result.get("error"), result=result,
                termination=result.get("termination"))
        except Exception as error:
            self._finish_chart(job, "failed", type(error).__name__ + ": " + str(error))

    def _interrupt_charts(self, reason, identity=None):
        from .evaluation import stop_calculation_process
        with self.simulation_process_lock:
            jobs = [job for key, job in self.chart_jobs.items() if identity is None or key == identity]
            owned = []
            for job in jobs:
                job["reason"] = job["reason"] or reason
                job["stopped"].set()
                owned.append((job, list(job["processes"])))
        for job, processes in owned:
            future = job.get("future")
            prevented = future.cancel() if future is not None else False
            termination = [stop_calculation_process(process) for process in processes]
            self._finish_chart(job, "interrupted", job["reason"], termination={"processes": termination,
                "termination_confirmed": prevented or bool(termination) and all(row["termination_confirmed"] for row in termination),
                "dispatch_prevented": prevented, "descendants_confirmed": False})

    def _expire_charts(self):
        with self.simulation_process_lock:
            expired = [key for key, job in self.chart_jobs.items()
                if not job["stopped"].is_set() and time.monotonic() >= job["deadline"]]
        for identity in expired:
            self._interrupt_charts("deadline", identity)

    def discovery(self, request=None):
        from .market_discovery import (
            DEFAULT,
            discover,
            metadata,
            option_state,
            scan_action,
            scan_state,
            seal,
        )
        if request is None:
            return {**metadata(), "scanner": scan_state(self), "options": option_state(self)}
        if request.get("action") in {"option_contracts", "option_select", "option_feed"}:
            return self.option_discovery(request)
        if str(request.get("action", "")).startswith("scan_"):
            return scan_action(self, request)
        if request.get("action") == "add_to_universe":
            with self.maintenance:
                if not isinstance(request.get("observation_id"), str) or not request["observation_id"]:
                    raise ValueError("Choose a retained discovery observation")
                result = self.discovery_detail(request.get("observation_id"))
                symbol = request.get("symbol")
                if not isinstance(symbol, str) or not symbol or result.get("status") != "completed" or not any(row.get("symbol") == symbol for row in result["rows"]):
                    raise ValueError("Select a symbol from a retained successful discovery observation")
                return self.save_config({}, add_symbol=symbol, expected_revision=request.get("config_revision"))
        if request.get("action", "screen") != "screen":
            raise ValueError("Unknown discovery action")
        store = self.store
        result = seal(discover(request))
        with self.maintenance:
            if self.store is not store:
                raise ValueError("Application records changed during discovery; reload the workspace")
            store.database.transact({"discovery": DEFAULT}, lambda records: records["discovery"]["observations"].update({result["id"]: result}))
        return result

    def configure_symbols(self):
        from .market_discovery import DEFAULT
        selections = self.store.database.read("discovery", DEFAULT)["data"].get("option_selections", {})
        symbols = list(dict.fromkeys([*self.store.data["config"]["universe"], *selections]))
        feed = next(iter(selections.values()))["feed"] if selections else None
        self.runtime.configure(symbols, **({"option_feed": feed} if feed else {}))

    def option_discovery(self, request):
        from .alpaca_readonly import AlpacaREST, ConnectionConfig
        from .linked_orders import option_contract
        from .market_discovery import DEFAULT, option_state, seal
        store = self.store
        if request["action"] == "option_contracts":
            query = request.get("query")
            if not isinstance(query, dict):
                raise ValueError("Choose explicit option contract filters or an exact OCC symbol")
            connection = ConnectionConfig.load(self.runtime.credentials_file)
            result = AlpacaREST(self.runtime.credentials_file, connection=connection).option_contracts(query)
            identity = str(uuid4())
            reference = store._write_source_result(identity, str(uuid4()), result["raw"], prefix="option-contracts", allow_pagination_cursor=True)
            observation = seal({"query": copy.deepcopy(query), "contracts": result["contracts"],
                "received_at": result["received_at"], "next_page_token": result.get("next_page_token"), "artifact": reference})
            with self.maintenance:
                if self.store is not store:
                    raise ValueError("Application records changed during option discovery")
                store.database.transact({"discovery": DEFAULT}, lambda records: records["discovery"].setdefault("option_observations", {}).update({observation["id"]: observation}))
            return {"option_observation": observation, "options": option_state(self)}
        with self.maintenance, self.execution_lock:
            if self.store is not store:
                raise ValueError("Application records changed during option selection")
            if type(request.get("expected_revision")) is not int:
                raise ValueError("Reload retained option discovery before selecting a contract")
            def select(records):
                saved = records["discovery"]
                feed = request.get("feed")
                if feed not in {"opra", "indicative"}:
                    raise ValueError("Choose OPRA or indicative explicitly; entitlement is not inferred")
                selections = saved.setdefault("option_selections", {})
                if request["action"] == "option_feed":
                    if not selections:
                        raise ValueError("Select a retained contract before changing its subscription feed")
                    for item in selections.values():
                        item.update(feed=feed, feed_changed_at=now())
                    return
                observation = saved.get("option_observations", {}).get(request.get("observation_id"), {})
                envelope = next((item for item in observation.get("contracts", []) if item["raw"].get("symbol") == request.get("symbol")), None)
                contract = option_contract(envelope)
                if any(item["feed"] != feed for symbol, item in selections.items() if symbol != contract["symbol"]):
                    raise ValueError("Existing selected contracts use a different feed; the native subscription uses one explicit feed")
                selections[contract["symbol"]] = {"symbol": contract["symbol"], "contract": copy.deepcopy(envelope),
                    "observation_id": observation["id"], "feed": feed, "selected_at": now()}
            store.database.transact({"discovery": DEFAULT}, select, expected={"discovery": request.get("expected_revision")})
            self.configure_symbols()
        return {"options": option_state(self)}

    def discovery_detail(self, identity=None, symbol=None):
        from .market_discovery import DEFAULT
        values = self.store.database.read("discovery", DEFAULT)["data"]["observations"]
        if identity:
            if identity not in values:
                raise ValueError("Retained discovery observation is unavailable")
            return values[identity]
        matches = [value for value in values.values() if not symbol or any(row.get("symbol") == symbol for row in value["rows"])]
        return max(matches, key=lambda value: value["captured_at"]) if matches else None

    def save_workspace(self, request):
        from .attention import DEFAULT as ATTENTION, OBSERVATIONS, sync_memberships
        from .market_discovery import DEFAULT as DISCOVERY
        from .workspace import DEFAULT, change
        def save(records):
            self.validate_drawing_sources(request.get("changes", {}).get("drawings", {}))
            view = request.get("changes", {}).get("preferences", {}).get("chartView", {})
            if view.get("analysis") is not None:
                analysis = view["analysis"]
                retained = self.chart_calculation(analysis.get("calculation_id"))
                if (retained["result_sha256"] != analysis.get("result_sha256")
                        or any(retained["source_pin"][field] != view.get(field) for field in ("symbol", "context", "timeframe"))):
                    raise ValueError("Chart preference differs from its exact retained analysis source")
            change(records["workspace"], request)
            sync_memberships(records["attention"], records["workspace"], records["attention_observations"])
            sync_memberships({"rules": records["discovery"].get("definitions", {})}, records["workspace"], records["attention_observations"])
        return self.store.database.transact({"workspace": DEFAULT, "attention": ATTENTION, "attention_observations": OBSERVATIONS, "discovery": DISCOVERY},
            save, expected={"workspace": request.get("expected_revision")})["workspace"]

    def validate_drawing_sources(self, drawings):
        from .investor import decimal
        if not isinstance(drawings, dict):
            raise ValueError("Drawing changes must be keyed by saved identity")
        for drawing in drawings.values():
            if not isinstance(drawing, dict) or not isinstance(drawing.get("points"), list):
                raise ValueError("Choose explicit drawing anchors")
            if drawing.get("deleted") is True:
                continue
            for point in drawing["points"]:
                if not isinstance(point, dict):
                    raise ValueError("Choose a typed drawing anchor")
                if point.get("basis") != "observed":
                    continue
                detail = self.pinned_chart_source(point.get("source_pin"))
                scope = self.drawing_scope(detail)
                bar = next((bar for bar in detail.get("bars", []) if bar["t"] == point.get("time")), {})
                raw = (bar.get("raw") or {}).get(point.get("value_kind"))
                if (drawing.get("scope") != scope or point.get("value_kind") not in {"o", "h", "l", "c"}
                        or raw is None or decimal(raw) is None or decimal(raw) != decimal(point.get("price"))):
                    raise ValueError("Observed drawing anchor differs from its exact retained scope/bar/OHLC source")

    def investor(self):
        from .investor import DEFAULT, RULES, RULE_PARAMETERS, instruments, broker_action_order, order_version, working_commitments, decimal, contingent_group
        from .approval_review import evaluate
        from .admission import DEFAULT as COMMANDS
        from .market_history import DEFAULT as HISTORY
        from .stock_evidence import DEFAULT as EVIDENCE
        record = self.store.database.read("investor", DEFAULT)
        runtime = self.runtime.state()
        commands = self.store.database.read("commands", COMMANDS)["data"]
        history = self.store.database.read("market_history", HISTORY)["data"]
        evidence = self.store.database.read("stock_evidence", EVIDENCE)["data"]
        checks = {p["id"]: evaluate(p, record["data"]["policy"], runtime, evidence, history, commands,
                  p.get("review_constraints", {}), self.store.directory) for p in record["data"]["proposals"] if p["status"] == "draft"}
        broker_actions = {}
        for order in runtime.get("orders", []):
            try:
                broker_action_order(runtime, order["id"])
                from .linked_orders import amendment_supported
                replacement_reason = None
                try:
                    amendment_supported(order)
                    contingent_group(order, runtime, commands)
                except ValueError as exc:
                    replacement_reason = str(exc)
                broker_actions[order["id"]] = {"supported": True, "cancel_supported": True,
                    "replace_supported": replacement_reason is None, "replacement_reason": replacement_reason,
                    "order_version": order_version(order)}
                if replacement_reason is None and order.get("order_class") == "mleg" and order.get("package_mapping"):
                    broker_actions[order["id"]]["package_terms"] = copy.deepcopy(order["package_terms"])
            except (ValueError, KeyError, TypeError) as exc:
                broker_actions[order.get("id")] = {"supported": False, "reason": str(exc)}
        from .linked_orders import EXECUTION_PROFILES, PACKAGE_PROFILES
        available_instruments = instruments(runtime, self.store.data["config"]["universe"])
        commitments, known = working_commitments(runtime, commands)
        for symbol, instrument in available_instruments.items():
            position = next((position for position in runtime.get("positions", []) if position["symbol"] == symbol), None)
            held = decimal((position or {}).get("qty"))
            reserved = sum((item["remaining"] for item in commitments if item["symbol"] == symbol and item["side"] == "SELL"), 0)
            quantity = max(held - reserved, 0) if known and held is not None and not position.get("import_error") else None
            broker_available = decimal((position or {}).get("qty_available"))
            if quantity is not None and broker_available is not None:
                quantity = min(quantity, max(broker_available, 0))
            instrument.update(available_exit_quantity=str(quantity) if quantity is not None else None, exit_availability_known=quantity is not None)
        return {**record, "rule_labels": RULES, "rule_parameters": RULE_PARAMETERS, "approval_records_enabled": self.admission.review_enabled,
                "command_admission_enabled": self.admission.admission_enabled, "broker_transport_enabled": self.admission.execution_enabled,
                "current_checks": checks, "broker_order_actions": broker_actions,
                "instruments": available_instruments, "option_package_profiles": copy.deepcopy(PACKAGE_PROFILES),
                "option_execution_profiles": copy.deepcopy(EXECUTION_PROFILES)}

    def health(self, *, journal_revision=None):
        import sqlite3
        runtime = self.runtime.state()
        try:
            revision = self.store.database.read_revision("journal") if journal_revision is None else journal_revision
            store = {"status": "available", "schema": self.store.database.VERSION,
                     "journal_revision": revision, "sqlite_version": sqlite3.sqlite_version}
        except (OSError, ValueError, sqlite3.Error):
            store = {"status": "unavailable", "message": "Local records could not be read; preserve the data directory and recovery files"}
        account = runtime.get("account") or {}
        from .admission import DEFAULT as COMMAND_DEFAULT
        commands = self.store.database.read("commands", COMMAND_DEFAULT)["data"]
        return {"product": "TradingAgents", "application_identity": hashlib.sha256(str(getattr(self, "launch_root", self.application_root)).casefold().encode()).hexdigest(),
                "browse_only": self.browse_only, "service": "running", "account_mode": str(runtime.get("endpoint") or "Configured Alpaca origin / not connected") + " / observed currency " + str(account.get("currency", "unknown"))
                    + " / multiplier " + str(account.get("multiplier", "unknown")) + " / shorting " + str(account.get("shorting_enabled", "unknown")) + "; native mapping supports CASH only",
                "engine": runtime.get("status", "unknown"), "engine_version": runtime.get("version"),
                "provider": "Alpaca", "feed": "IEX", "account_observed_at": runtime.get("account_at"),
                "prices_checked_at": runtime.get("prices_checked_at"), "runtime_heartbeat_at": runtime.get("updated_at"),
                "reconciliation": copy.deepcopy(runtime.get("reconciliation", {"status": "unknown"})),
                "store": store, "execution_enabled": self.admission.execution_enabled, "new_orders_blocked": commands.get("new_orders_blocked", False),
                "native_cache_mode": "memory",
                "native_durability": {"state": "in_memory", "durable_writes_confirmed": False,
                    "reason": "Native cache runs in memory. SQLite application records remain saved."},
                "capabilities": {"saved_research": True, "workspace_records": True, "human_proposals": True,
                    "allocation_previews": True, "broker_submission": self.admission.execution_enabled, "fractional_short_management": False,
                    "history_coverage": self.data_jobs.state()["coverage_counts"]},
                "research_provider": self.store.data["config"].get("llm_provider"),
                "research_enabled": not self.browse_only, "history_status": "unavailable" if self.history_error else "available"}

    def start_native(self, request=None):
        selected = (request or {}).get("execution_profile")
        current = self.runtime.state()
        if current.get("status", "stopped") in {"stopped", "disconnected"} or selected is not None and selected != current.get("execution_profile"):
            self.runtime.configure(self.runtime.symbols, execution_profile=selected if selected is not None else "long_only")
        return self.runtime.start()

    def recovery_action(self, request):
        from .recovery import backup, restore, stage
        if any(not future.done() for future in self.research_futures | self.data_jobs.futures):
            raise ValueError("Research/data writers are active. Wait for them to finish or stop their jobs before backup/restore")
        if request.get("action") == "preview":
            return stage(self, request.get("archive"))
        if request.get("action") == "backup":
            return backup(self)
        with self.maintenance, self.store.lock:
            if request.get("action") == "restore":
                self._stop_simulations()
                return restore(self, request.get("token"), request.get("confirmation"))
        raise ValueError("Choose backup, preview or restore")

    def backup_download(self, identity):
        from uuid import UUID
        if str(UUID(identity)) != identity:
            raise ValueError("Invalid backup identity")
        return (self.application_root / "recovery" / "backups" / (identity + ".zip")).read_bytes()

    def reporting(self, *, compact=False):
        from .decision_journal import DEFAULT, decisions, position_outcomes
        from .investor import DEFAULT as INVESTOR_DEFAULT
        record = self.store.database.read("reporting", DEFAULT)
        if compact:
            return {"revision": record["revision"], "collection_count": len(record["data"]["collections"]),
                    "native_position_capture_count": len(record["data"].get("native_position_captures", [])),
                    "benchmark": record["data"]["benchmark"], "horizon_days": record["data"]["horizon_days"]}
        investor = self.store.database.read("investor", INVESTOR_DEFAULT)["data"]
        from .approval_review import read_artifact
        captures = []
        for capture in record["data"].get("native_position_captures", []):
            report = read_artifact(self.store.directory, capture["artifact"])
            mismatch = bool(report and any(report.get(key) != capture.get(key) for key in ("native_epoch", "captured_at", "account_context")))
            captures.append({**capture, "report": report,
                "metadata_gap": "Capture index account/epoch/time differs from the original report; inspect both retained sources" if mismatch else None})
        authority, runtime = self.admission.snapshot()["data"], self.runtime.state()
        outcomes = position_outcomes(captures, authority, investor)
        outcomes.update(current_native_epoch=runtime.get("native_epoch"), current_native_status=runtime["status"])
        for group in outcomes["groups"]:
            represented = [capture["report"].get("native_reconstruction", {}).get(group["instrument_id"])
                for capture in captures if capture["id"] in {source["capture_id"] for source in group["source_refs"]} and capture.get("report")]
            represented = [value for value in represented if value]
            if represented:
                group.update(native_reconstruction=represented, native_economics_verified=False, actual_net=None)
                limitation = "Native representation uses modeled reduction PnL, zero model commission and processing chronology; these are not actual broker execution economics"
                group["accounting_basis"] += "; " + limitation
                group["coverage"]["gaps"] = list(dict.fromkeys([*group["coverage"]["gaps"], limitation]))
                if group["coverage"]["status"] != "ambiguous":
                    group["coverage"]["status"] = "incomplete"
            group["freshness"] = {"status": "retained_capture", "captured_at": group["latest_capture_at"],
                "native_epoch_matches_current": group["selected_source_ref"]["native_epoch"] == runtime.get("native_epoch"),
                "native_status": runtime["status"], "mark_is_live": False,
                "limitation": "Explicit retained capture; this result is not live account performance"}
        return {**record, "position_outcomes": outcomes,
                "decisions": decisions(investor, self.store.snapshot(), self.history, authority, outcomes["groups"])}

    def reporting_detail(self, identity, receipt=None):
        record = self.reporting()
        collection = next(c for c in record["data"]["collections"] if c["id"] == identity)
        def read(reference):
            from .recovery import references
            relative, expected = next(references(reference, native_reconstruction=True))
            path = (self.store.directory / relative).resolve()
            if not path.is_relative_to(self.store.directory.resolve()):
                raise ValueError("Saved account-history source escapes the application boundary")
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != expected:
                raise ValueError("Saved account-history source hash differs")
            return payload
        result = json.loads(read(collection["artifact"]))
        if receipt is not None:
            return read(result["receipts"][receipt]["artifact"])
        from .performance import report_methods
        benchmark = record["data"]["benchmark"]
        current = None
        if benchmark:
            saved = self.data_jobs.state()["data"]["entries"]
            matching = [entry for entry in saved.values() if entry["symbol"] == benchmark["symbol"]
                        and entry["start"] == result["requested_start"] and entry["end"] == result["requested_end"]
                        and entry["adjustment"] == "split" and self.data_jobs.timeframe(entry) == "1Day"]
            if matching:
                current = self.data_jobs.detail(benchmark["symbol"], max(matching, key=lambda item: item["captured_at"])["key"])
        return report_methods(result, benchmark=benchmark, history=current)

    def save_reporting(self, request):
        from .decision_journal import DEFAULT, change
        from .app_database import StoreConflict
        with self.maintenance:
            record = self.reporting()
            collection_store = self.store
            collection_runtime = self.runtime.state() if request.get("action") == "collect" else None
            collection_credentials = self.runtime.credentials_file if request.get("action") == "collect" else None
        if request.get("expected_revision") != record["revision"] or type(request.get("expected_revision")) is not int:
            raise StoreConflict(record["revision"])
        if request.get("action") == "export":
            identities = request.get("ids")
            if not isinstance(identities, list) or not identities:
                raise ValueError("Select decision records to export")
            available = {d["id"]: d for d in record["decisions"]}
            if any(identity not in available for identity in identities):
                raise ValueError("An export selection no longer exists; reload the journal")
            exported = {"format": "tradingagents-decision-journal-v1", "exported_at": now(),
                        "scope": "Selected saved local decisions and investor notes; absent executions and outcomes are not inferred",
                        "reporting_revision": record["revision"], "decisions": [available[i] for i in identities],
                        "notes": {i: record["data"]["entries"].get(i) for i in identities}, "execution_enabled": self.admission.execution_enabled}
            from .report_exports import guard
            guard(exported)
            return {"export": exported}
        if request.get("action") == "export_csv":
            return self.reporting_csv(request)
        if request.get("action") == "benchmark_history":
            benchmark = record["data"]["benchmark"]
            if not benchmark:
                raise ValueError("Choose your benchmark first")
            collection = self.reporting_detail(request["collection_id"])
            if benchmark["treatment"] != "price":
                raise ValueError("No supported reinvested-dividend benchmark source is configured; total-return comparison remains unavailable")
            self.data_jobs.request({"symbols": [benchmark["symbol"]], "start": collection["requested_start"],
                "end": collection["requested_end"], "asof": request["asof"], "adjustment": "split", "purpose": "benchmark"})
            return self.reporting()
        if request.get("action") == "refresh_methods":
            result = self.reporting_detail(request["collection_id"])
            result["method_reported_at"] = now()
            result["benchmark_choice"] = record["data"]["benchmark"]
            reference = self.store._write_json_artifact(result["id"], "performance-methods", result)
            def amend(saved):
                collection = next(c for c in saved["collections"] if c["id"] == result["id"])
                collection["artifact"] = reference
                collection["method_reported_at"] = result["method_reported_at"]
            self.store.database.update("reporting", record["revision"], amend, DEFAULT)
            return self.reporting()
        if request.get("action") == "collect":
            from .account_history import collect
            from .alpaca_readonly import AlpacaREST
            runtime = collection_runtime
            result = collect(AlpacaREST(collection_credentials), collection_store, request["start"], request["end"],
                             (runtime.get("account") or {}).get("id"))
            result["allocation_observation"] = {"account_at": runtime.get("account_at"),
                "reconciliation": runtime.get("reconciliation"), "positions": runtime.get("positions"),
                "account": runtime.get("account"), "historical_allocation": False}
            # Persist source observation beside the immutable collection, not as a holdings ledger.
            result["artifact"] = collection_store._write_json_artifact(result["id"], "account-history-with-allocation", result)
            def append(saved):
                saved["collections"].insert(0, {key: result[key] for key in
                    ("id", "account_id", "requested_start", "requested_end", "collected_at", "pagination_complete", "interval_complete", "artifact")})
                return saved
            with self.maintenance:
                if self.store is not collection_store:
                    raise ValueError("Application generation changed during collection; retained receipts were not attached to the restored store")
                if (self.runtime.state().get("account") or {}).get("id") != result["account_id"]:
                    raise ValueError("Observed account changed during collection; retained receipts were not attached")
                collection_store.database.update("reporting", record["revision"], append, DEFAULT)
                return self.reporting()
        else:
            self.store.database.update("reporting", record["revision"],
                lambda saved: change(saved, request, record["decisions"]), DEFAULT)
        return self.reporting()

    def reporting_csv(self, request):
        from .report_exports import csv_export
        runtime = self.runtime.state()
        kind = request.get("kind")
        symbols = request.get("symbols")
        if symbols is not None and (not isinstance(symbols, list) or any(not isinstance(s, str) for s in symbols)):
            raise ValueError("Filtered exports need an explicit symbol list")
        scope = "filtered subset" if symbols is not None else "full account"
        account = runtime.get("account") or {}
        context = {"scope": scope, "account_id": account.get("id"), "source_at": runtime.get("account_at"),
                   "period_start": None, "period_end": None, "currency": "USD"}
        if kind == "holdings":
            positions = runtime.get("positions", [])
            rows = [{key: p.get(key) for key in ("symbol", "qty", "side", "avg_entry_price", "cost_basis", "market_value",
                "unrealized_pl", "unrealized_plpc", "reconciliation_status", "import_error")}
                for p in positions if symbols is None or p["symbol"] in symbols]
            context.update(account_equity_source=account.get("equity"), account_long_market_value_source=account.get("long_market_value"),
                totals_basis="Full-account broker totals remain separate from the selected rows", values_basis="Broker reported cost/P&L and exact quantities; discrepancies retained",
                account_reconciliation=runtime.get("reconciliation", {}).get("status"), engine_state=runtime.get("status"))
            if runtime.get("native_reconstruction"):
                context["native_representation_economics"] = "Native reconstruction is modeled; CSV cost basis, cash and P&L remain broker-reported, not native reconstruction results"
            if not rows:
                rows = [{"symbol": None, "qty": None, "import_error": "No rows selected" if symbols is not None else
                    "Confirmed zero positions" if runtime.get("status") == "connected" and runtime.get("reconciliation", {}).get("positions_reconciled") else "Holdings unavailable"}]
        elif kind in {"activity", "performance"}:
            collection = self.reporting_detail(request["collection_id"])
            context.update(account_id=collection["account_id"], source_at=collection["collected_at"],
                period_start=collection["requested_start"], period_end=collection["requested_end"],
                interval_complete=collection["interval_complete"], source="Alpaca paper Trading API")
            if kind == "activity":
                rows = [copy.deepcopy(a) for a in collection["activities"] if symbols is None or a.get("symbol") in symbols]
                context["totals_basis"] = "Selected source activities only; no holdings or account totals reconstructed"
            else:
                if symbols is not None:
                    raise ValueError("Portfolio performance is full-account; it cannot be relabelled as a stock subset")
                rows = [copy.deepcopy(p) for p in collection["points"]]
                context.update(percent_basis="Broker P&L fraction = equity/base - 1; not verified adjusted return",
                    time_weighted=collection["time_weighted"], modified_dietz=collection["dietz"],
                    benchmark_comparison=collection["benchmark_comparison"], drawdown=collection["drawdown"],
                    technical_method_assessment=collection["technical_method_assessment"],
                    calculation_coverage_complete=collection.get("calculation_coverage_complete", False),
                    technical_method_accepted=collection["technical_method_assessment"]["accepted"],
                    accepted_metric_ready={key: collection[key]["accepted_metric_ready"] for key in
                        ("time_weighted", "dietz", "benchmark_comparison", "drawdown")},
                    rounding=collection["broker_rounding"])
            if not rows:
                rows = [{"notice": "Selected source rows unavailable; no zeros inferred"}]
        else:
            raise ValueError("Choose holdings, activity or performance CSV")
        return csv_export(kind, rows, context)

    def _proposal_research(self, reference):
        from .investor import digest
        from .evidence_requirements import research_dependencies
        result = self.run_detail(reference["run_id"], reference["symbol"])
        key = reference["report_key"]
        if (result.get("status") != "completed" or result.get("revision", 0) != reference["revision"]
                or key not in result.get("reports", {})):
            raise ValueError("Saved research revision or report differs; reload the source before linking it")
        return {**{k: reference[k] for k in ("run_id", "symbol", "revision", "report_key")},
                "research_date": result.get("trade_date"), "result_sha256": digest(result),
                "report_sha256": digest(result["reports"][key]), "evidence_dependencies": research_dependencies(result, key)}

    def assess_basket(self, records, basket, runtime):
        from .approval_review import read_artifact
        from .investor import decimal, price_evidence
        from .policy_evaluation import evaluate
        fee, slip = decimal(basket.get("fee_per_leg")), decimal(basket.get("slippage_bps"))
        legs = []
        for leg in basket["legs"]:
            terms = leg["terms"]
            price = price_evidence(terms, runtime)["price"]
            charge = (fee if fee is not None else decimal("0")) + (decimal(terms["quantity"]) * price * slip / 10000 if slip is not None else decimal("0")) if price is not None and (fee is not None or slip is not None) else None
            legs.append({"terms": terms, "price_cap": price, "fee": charge})
        results = {}
        linked_ids = set(basket.get("linked_proposal_ids", [])) | {leg.get("proposal_id") for leg in basket["legs"]}
        for label, scenario in (("complete", basket["complete_scenario"]), ("partial", basket["partial_scenario"])):
            selected = [leg for leg in legs if leg["terms"]["symbol"] in scenario["assumed_filled"]]
            checks = []
            for primary in selected or legs[:1]:
                terms = primary["terms"]
                linked = next((p for p in records["investor"]["proposals"] if p["id"] in linked_ids and p["terms"]["symbol"] == terms["symbol"]), {})
                constraints = {**linked.get("review_constraints", {}), "max_execution_price": primary["price_cap"], "max_fees": primary["fee"]}
                checks.append({"symbol": terms["symbol"], "evaluation": evaluate(terms, records["investor"]["policy"], runtime,
                    records["commands"], records["market_history"], records["stock_evidence"], constraints,
                    lambda reference: read_artifact(self.store.directory, reference), proposed_legs=selected)})
            results[label] = {"assumed_filled": scenario["assumed_filled"], "per_symbol_checks": checks,
                              "account_observed_at": runtime.get("account_at"), "policy_revision": records["investor"]["policy"]["revision"],
                              "basis": "Aggregate hypothetical legs; entered fee/slippage estimates and observed quote or exact human limit. Unknown costs are disclosed; missing required economics or failed configured checks block the affected operation. No approval or execution authority."}
        basket["policy_scenarios"] = results

    def prepare_package_valuation(self, terms):
        from .linked_orders import is_package
        if is_package(terms):
            self.runtime.prepare_package(terms)
        return self.runtime.state()

    def save_investor(self, request):
        from .investor import DEFAULT, save
        from .admission import DEFAULT as COMMAND_DEFAULT, invalidate
        if request.get("action") == "chart_source":
            return {"chart_source": self.pinned_chart_source(request.get("pin"))}
        if request.get("action") == "chart_copy":
            return {"chart_copy": self.chart_price_copy(request.get("price_ref"), request.get("terms", {}))}
        if request.get("action") == "review":
            saved = self.store.database.read("investor", DEFAULT)["data"]
            proposal = next(p for p in saved["proposals"] if p["id"] == request["id"])
            self.prepare_package_valuation(proposal["terms"])
            constraints = self.review_constraints(request.get("constraints"))
            self.admission.evaluate_review(request["id"], proposal_revision=request.get("proposal_revision"),
                policy_revision=request.get("policy_revision"), constraints=constraints,
                expected={"investor": request.get("expected_revision"), "commands": request.get("commands_revision")})
            return self.investor()
        def update(change):
            def apply(records):
                records["investor"] = change(records)
                for proposal in records["investor"]["proposals"]:
                    self.admission.assess(records, proposal, runtime, proposal.get("review_constraints", {}))
                if request.get("action") == "basket_draft":
                    baskets = records["investor"].get("baskets", [])
                    basket = next(b for b in baskets if b["id"] == request["id"]) if request.get("id") else baskets[0]
                    self.assess_basket(records, basket["preview"], runtime)
                return invalidate(records)
            from .market_history import DEFAULT as HISTORY_DEFAULT
            from .stock_evidence import DEFAULT as EVIDENCE_DEFAULT
            return self.store.database.transact({"investor": DEFAULT, "commands": COMMAND_DEFAULT,
                "market_history": HISTORY_DEFAULT, "stock_evidence": EVIDENCE_DEFAULT}, apply,
                expected={"investor": request.get("expected_revision")})
        runtime = self.runtime.state()
        universe = self.store.data["config"]["universe"]
        if request.get("action") == "preview":
            record = self.store.database.read("investor", DEFAULT)
            updated = save(copy.deepcopy(record["data"]), {**request, "action": "draft"}, runtime,
                           universe, self._proposal_research, commands=self.store.database.read("commands", COMMAND_DEFAULT)["data"],
                           resolve_price_ref=self.chart_price_copy)
            proposal = next(p for p in updated["proposals"] if p["id"] == request.get("id")) if request.get("id") else updated["proposals"][0]
            runtime = self.prepare_package_valuation(proposal["terms"])
            from .market_history import DEFAULT as HISTORY_DEFAULT
            from .stock_evidence import DEFAULT as EVIDENCE_DEFAULT
            records = {"investor": updated, "commands": self.store.database.read("commands", COMMAND_DEFAULT)["data"],
                       "market_history": self.store.database.read("market_history", HISTORY_DEFAULT)["data"],
                       "stock_evidence": self.store.database.read("stock_evidence", EVIDENCE_DEFAULT)["data"]}
            self.admission.assess(records, proposal, runtime, proposal.get("review_constraints", {}))
            return {"preview": proposal, "revision": record["revision"]}
        if request.get("action") == "basket_preview":
            from .baskets import preview
            record = self.store.database.read("investor", DEFAULT)
            prior = next((b for b in record["data"].get("baskets", []) if b["id"] == request.get("id")), None)
            commands = self.store.database.read("commands", COMMAND_DEFAULT)["data"]
            result = preview(record["data"], {**request, "linked_proposal_ids": prior["linked_proposal_ids"] if prior else []}, runtime, universe, commands=commands)
            result["linked_proposal_ids"] = prior["linked_proposal_ids"] if prior else []
            from .market_history import DEFAULT as HISTORY_DEFAULT
            from .stock_evidence import DEFAULT as EVIDENCE_DEFAULT
            records = {"investor": record["data"], "commands": commands,
                       "market_history": self.store.database.read("market_history", HISTORY_DEFAULT)["data"],
                       "stock_evidence": self.store.database.read("stock_evidence", EVIDENCE_DEFAULT)["data"]}
            self.assess_basket(records, result, runtime)
            return {"preview": result, "revision": record["revision"]}
        if str(request.get("action", "")).startswith("basket_"):
            from .baskets import save as save_basket
            update(lambda records: save_basket(records["investor"], request, runtime, universe, self._proposal_research, commands=records["commands"]))
            return self.investor()
        from .linked_orders import is_package
        if request.get("action") == "draft" and is_package(request.get("terms", {})):
            record = self.store.database.read("investor", DEFAULT)
            normalized = save(copy.deepcopy(record["data"]), request, runtime, universe, self._proposal_research,
                commands=self.store.database.read("commands", COMMAND_DEFAULT)["data"], resolve_price_ref=self.chart_price_copy)
            proposal = next(p for p in normalized["proposals"] if p["id"] == request["id"]) if request.get("id") else normalized["proposals"][0]
            runtime = self.prepare_package_valuation(proposal["terms"])
        update(lambda records: save(records["investor"], request, runtime, universe, self._proposal_research,
                                    commands=records["commands"], resolve_price_ref=self.chart_price_copy))
        return self.investor()

    def pinned_chart_source(self, pin):
        from .workspace import source_pin
        pin = source_pin(pin)
        if pin["context"] == "current":
            detail = self.data_jobs.detail(pin["symbol"], pin["cache_key"], timeframe=pin["timeframe"], artifact=pin["artifact"])
        else:
            detail = self.chart(pin["symbol"], run_id=pin["run_id"])
        source = detail.get("source") or {}
        if (any(source.get(key) != pin["artifact"][key] for key in ("path", "sha256"))
                or detail.get("symbol") != pin["symbol"] or detail.get("timeframe", "1Day") != pin["timeframe"]
                or pin.get("derivation_identity") and detail.get("derivation_identity") != pin["derivation_identity"]):
            raise ValueError("Exact pinned chart source is unavailable or changed; no latest source was substituted")
        return detail

    def chart_price_copy(self, reference, terms):
        from .investor import normalize_chart_price
        if not isinstance(reference, dict):
            raise ValueError("Choose an exact retained chart price reference")
        detail = self.pinned_chart_source(reference.get("pin"))
        if reference.get("derived_origin") is not None:
            from .investor import price_reference
            reference = price_reference(reference, terms)
            origin = reference["derived_origin"]
            calculation = self.chart_calculation(origin["calculation_id"])
            events = [event for event in calculation["result"]["events"] if event.get("output_ordinal") == origin["event_ordinal"]]
            rows = [row for row in calculation["spec"]["rows"] if row.get("source_ordinal") == origin["source_ordinal"]]
            if (calculation["result_sha256"] != origin["result_sha256"] or calculation["source_pin"] != reference["pin"]
                    or len(events) != 1 or not isinstance(events[0].get("source_range"), list)
                    or not events[0]["source_range"][0] <= origin["source_ordinal"] <= events[0]["source_range"][1]
                    or len(rows) != 1 or not rows[0].get("raw") or rows[0]["t"] != reference.get("bar_time")):
                raise ValueError("Derived selection does not resolve to that exact actual raw source bar")
        return normalize_chart_price(reference, terms, self.runtime.state(), detail)

    @staticmethod
    def review_constraints(value):
        from .investor import decimal
        allowed = {"account_max_age_seconds", "quote_max_age_seconds", "evidence_max_age_seconds",
                   "approval_max_age_seconds", "max_execution_price", "max_fees", "working_order_fee_caps"}
        if not isinstance(value, dict) or set(value) - allowed:
            raise ValueError("Only explicit review tolerances and price/fee ceilings may be supplied")
        result = {}
        for key, item in value.items():
            if key == "working_order_fee_caps":
                if not isinstance(item, dict) or len(item) > 1000:
                    raise ValueError("Working-order fee ceilings must be an object keyed by broker order identity")
                result[key] = {}
                for identity, amount in item.items():
                    parsed = decimal(amount)
                    if parsed is None or parsed < 0:
                        raise ValueError("Working-order fee ceilings must be finite and nonnegative")
                    result[key][identity] = str(parsed)
            elif item not in (None, ""):
                parsed = decimal(item)
                if parsed is None or parsed < 0:
                    raise ValueError("Review bounds must be finite and nonnegative")
                result[key] = str(parsed)
        return result

    def command_receipt(self, identity, checksum):
        from uuid import UUID
        from .recovery import references
        if str(UUID(identity)) != identity or not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise ValueError("Choose a recorded command receipt identity")
        command = self.admission.snapshot()["data"]["commands"][identity]
        matching = [relative for relative, digest in references(command, native_reconstruction=True) if digest == checksum]
        if not matching:
            raise ValueError("Receipt is not referenced by this durable command")
        path = (self.store.directory / matching[0]).resolve()
        if not path.is_relative_to(self.store.directory.resolve()) or path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("Command receipt exceeds the saved source boundary")
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != checksum:
            raise ValueError("Command receipt checksum differs")
        return payload

    def command_action(self, request):
        action = request.get("action")
        expected = {"commands": request.get("commands_revision"), "investor": request.get("investor_revision")}
        if any(type(value) is not int for value in expected.values()):
            raise ValueError("Reload current command and investor revisions before this action")
        from .workspace import text
        actor = "local-session:" + self.instance_id
        reason = text(request.get("note", request.get("reason", "")), 20000, "optional action note")
        if action == "option_instruction" and request.get("operation") == "preview":
            return {"option_preview": self.admission.preview_instruction(request.get("kind"), request.get("symbol"), request.get("constraints")),
                "commands": self.admission.snapshot()}
        if action == "block":
            self.admission.control(request.get("blocked"), actor=actor, reason=reason, expected=expected)
        elif self.browse_only:
            raise PermissionError("Browse-only mode does not permit command authorizations or dispatch")
        elif action == "option_instruction":
            operation = request.get("operation")
            if operation == "submit":
                from .app_database import StoreConflict
                with self.maintenance:
                    self.admission.enabled()
                    if self.admission.snapshot()["revision"] != expected["commands"] or self.investor()["revision"] != expected["investor"]:
                        raise StoreConflict(self.admission.snapshot()["revision"])
                    runtime = self.runtime
                runtime.request("option_instruction", instruction_id=request.get("instruction_id"))
            elif operation in {"prepare", "review", "approve", "release_interlock"}:
                prior_ids = set(self.admission.snapshot()["data"].get("option_instructions", {})) if operation == "prepare" else set()
                self.admission.option_instruction(operation, actor=actor, instruction_id=request.get("instruction_id"),
                    kind=request.get("kind"), symbol=request.get("symbol"), reason=reason, constraints=request.get("constraints"),
                    expected=expected, binding_sha256=request.get("binding_sha256"), reviewed_unknowns=request.get("reviewed_unknowns", False))
                if operation == "prepare":
                    result = self.admission.snapshot()
                    return {**result, "option_instruction_id": next(key for key in result["data"]["option_instructions"] if key not in prior_ids)}
            else:
                raise ValueError("Choose preview, prepare, review, approve, separate submit or audited interlock release")
        elif action == "exercise":
            self.admission.exercise({**request, "action": request.get("exercise_action", "authorize")}, expected=expected)
        elif action == "basket_admit":
            self.admission.basket_admit({**request, "actor": actor, "reason": reason}, expected=expected)
        elif action == "basket_control":
            self.admission.basket_control(request["id"], paused=request.get("paused"), actor=actor, reason=reason, expected=expected)
        elif action == "resolve_never_dispatched":
            self.admission.resolve_never_dispatched(request["id"], request.get("operation", "submit"), expected=expected)
        elif action == "basket_dispatch_next":
            self.admission.enabled()
            if request.get("basket_id"):
                result = self.admission.basket_admit({**request, "actor": actor, "reason": reason}, expected=expected, dispatch=True)
                group = next(item for item in result["commands"]["data"]["basket_executions"].values()
                             if item["basket_id"] == request["basket_id"] and item["basket_revision"] == request.get("basket_revision"))
                command_id = group["command_ids"][0]
            else:
                state = self.admission.snapshot()["data"]
                group = state["basket_executions"][request["id"]]
                if group["state"] not in {"ready", "running"}:
                    raise ValueError("Review and resume the basket before dispatch")
                command_id = next(key for key in group["command_ids"] if state["commands"][key]["state"] == "admitted_not_dispatched")
                self.admission.dispatch_intent(command_id, expected=expected)
            self.runtime.request("dispatch", command_id=command_id, action="submit")
        elif action in {"submit", "cancel", "replace"}:
            self.admission.enabled()
            command_id = request.get("id")
            if action == "submit":
                if request.get("approval_id"):
                    command_id = self.admission.submit_approved(request["approval_id"], expected=expected)
                else:
                    self.admission.dispatch_intent(command_id, expected=expected)
            else:
                command_id = self.admission.authorize_action(command_id, kind=action, actor=actor, reason=reason,
                    broker_order_id=request["broker_order_id"], replacement_command_id=request.get("replacement_command_id"),
                    replacement_approval_id=request.get("replacement_approval_id"), expected=expected,
                    broker_order_version=request.get("broker_order_version"))
            # Request failure is ambiguous: only the adapter's durable transport boundary can resolve no-send.
            self.runtime.request("dispatch", command_id=command_id, action=action)
        else:
            raise ValueError("Choose an explicit command, exercise, basket or order-block action")
        return self.admission.snapshot()

    def approval_action(self, request, *, admission=False):
        self.admission.review_allowed()
        expected = {"investor": request.get("expected_revision"), "commands": request.get("commands_revision")}
        if any(type(revision) is not int for revision in expected.values()):
            raise ValueError("Reload current investor and command revisions before review")
        from .workspace import text
        actor = "local-session:" + self.instance_id
        reason = text(request.get("note", request.get("reason", "")), 20000, "optional review note")
        if admission or request.get("action") == "admit":
            self.admission.admit(request["approval_id"], expected=expected)
        elif request.get("action") == "approve":
            proposal = next(p for p in self.investor()["data"]["proposals"] if p["id"] == request.get("id"))
            if request.get("terms_sha256") != proposal["terms_sha256"]:
                raise ValueError("Approval terms changed; reload and inspect the exact saved revision")
            self.prepare_package_valuation(proposal["terms"])
            self.admission.approve(proposal["id"], actor=actor, reason=reason or proposal["terms"]["rationale"],
                constraints=self.review_constraints(request.get("constraints")), proposal_revision=request.get("proposal_revision"),
                policy_revision=request.get("policy_revision"), evaluation_binding_sha256=request.get("evaluation_binding_sha256"),
                expected=expected)
        elif request.get("action") == "revoke":
            self.admission.revoke(request["approval_id"], actor=actor, reason=reason, expected=expected)
        else:
            raise ValueError("Choose an explicit approval, revocation or admission")
        return {"investor": self.investor(), "commands": self.admission.snapshot()}

    @staticmethod
    def _research_activity(run):
        events = copy.deepcopy(run.get("events", []))
        keys = {e.get("attempt_id") for e in events if isinstance(e, dict)}
        attempts = run.get("gateway_evidence", {}).get("attempts", [])
        for receipt in attempts:
            boundary = receipt.get("boundary_kind")
            if boundary != "gateway_invocation" and (boundary != "gateway_logical" or receipt.get("parent_attempt_id")):
                continue
            stamp = receipt.get("ended_at") or receipt.get("started_at")
            identity = receipt.get("attempt_id")
            if not stamp or not identity or identity in keys:
                continue
            outcome = receipt.get("outcome", "unknown")
            cause = "; ".join(d["message"] for d in receipt.get("error_details", [])
                              if d.get("message") and d["message"] != "Exception details withheld")
            message = (f"Retained evidence: {receipt.get('vendor')} / {receipt.get('operation')}: {outcome}. "
                       + f"Started: {receipt.get('started_at')}; ended: {receipt.get('ended_at')}. "
                       + (f"{receipt['failure_kind']}. " if receipt.get("failure_kind") else "")
                       + (f"{cause}. " if cause else f"Original error details unavailable ({receipt.get('error_class', 'unknown class')}). " if outcome not in {"running", "success"} else "")
                       + (f"Screening budget: {receipt['screening_budget']}. " if receipt.get("screening_budget") else "")
                       + f"Receipt attempt: {identity} (Sources).")
            events.append({"time": stamp, "kind": "source", "symbol": receipt.get("symbol"),
                           "message": message, "attempt_id": identity})
            keys.add(identity)
        for result in run.get("results", []):
            for source, evidence in result.get("social_sentiment", {}).get("sources", {}).items():
                rows = evidence.get("posts", [])
                if not rows:
                    continue
                classified = sum(row.get("status") == "classified" for row in rows)
                stamps = [a.get("ended_at") or a.get("started_at") for a in attempts
                          if a.get("symbol") == result["symbol"] and a.get("vendor") == "laya"]
                stamp = evidence.get("completed_at") or max((s for s in stamps if s), default=None)
                message = (f"Retained evidence: {source}: {classified}/{len(rows)} posts classified; "
                           f"saved status: {evidence.get('status', 'unknown')}. "
                           + (f"{evidence['stop_reason']}. " if evidence.get("stop_reason") else "")
                           + ("Progress timestamp unavailable." if not stamp else
                              "Snapshot shown at its completion time." if evidence.get("completed_at") else
                              "Snapshot shown at the last retained Laya receipt time; progress time unavailable."))
                if not any(e.get("kind") == "screening" and e.get("symbol") == result["symbol"]
                           and e.get("message") == message for e in events):
                    events.append({"time": stamp, "kind": "screening", "symbol": result["symbol"], "message": message})
        return sorted(events, key=lambda e: e.get("time") or "")[-500:]

    def run_detail(self, run_id, symbol=None):
        journal = self.store.database.read("journal")["data"]
        run = next((r for r in journal["runs"] if r["id"] == run_id), None)
        if run is None:
            run = next(r for r in self.history.get("runs", []) if r["id"] == run_id)
        if symbol is None:
            detail = copy.deepcopy(run)
            detail["events"] = self._research_activity(run)
            detail["event_count"] = len(detail["events"])
            return detail
        result = copy.deepcopy(next(r for r in run["results"] if r["symbol"] == symbol))
        result.setdefault("revision", 0)
        return result

    def chart(self, symbol, *, force=False, run_id=None):
        from .investor import digest
        from .market_evidence import recorded_market
        all_runs = self.store.data["runs"] + self.history.get("runs", [])
        run = next((r for r in all_runs if symbol in r.get("symbols", []) and
                    (r["id"] == run_id if run_id else r["status"] == "completed")), None)
        if run is None:
            raise ValueError("Select an existing research run containing this stock.")
        root = self.store.directory if any(r["id"] == run["id"] for r in self.store.data["runs"]) else self.history_directory
        with self.chart_lock:
            result = recorded_market(root, run, symbol)
            result["derivation_identity"] = digest(sorted([
                {"name": series["name"], "derivation_identity": series.get("derivation_identity") or digest(series)}
                for series in result.get("indicators", [])], key=lambda item: (item["name"], item["derivation_identity"])))
            key = (run["id"], symbol, digest({"source": result.get("source"), "problems": result.get("problems"),
                "inputs": self._attention_market_signature(run, symbol), "indicators": [
                    {key: series.get(key) for key in ("name", "definition", "derivation_identity")} for series in result.get("indicators", [])]}))
            if not force and key in self.chart_cache:
                return copy.deepcopy(self.chart_cache[key])
            self.chart_cache = {k: v for k, v in self.chart_cache.items() if k[:2] != key[:2]}
            self.chart_cache[key] = result
            return copy.deepcopy(result)

    def readiness(self, config, *, refresh=False, probe=True):
        provider = config["llm_provider"].lower()
        if self.graph_factory is not None:
            return {"ready": True, "message": "Injected analysis runtime."}
        if provider == "chatgpt":
            from tradingagents.llm_clients.chatgpt_client import check_chatgpt_account

            with self.account_lock:
                if not probe:
                    return dict(self.account_status[1]) if self.account_status else {
                        "ready": None,
                        "message": "Codex account is checked when research starts.",
                    }
                if refresh or self.account_status is None or time.monotonic() >= self.account_status[0]:
                    try:
                        check_chatgpt_account(timeout=10)
                        status = {"ready": True, "message": "Connected to your Codex ChatGPT account."}
                    except (RuntimeError, TimeoutError, OSError, ValueError) as exc:
                        status = {"ready": False, "message": str(exc)}
                    self.account_status = (time.monotonic() + 30, status)
                return dict(self.account_status[1])
        if provider not in PROVIDER_API_KEY_ENV:
            return {"ready": False, "message": "Choose a supported model provider in settings."}
        if provider in {"ollama", "openai_compatible"}:
            ready = bool(config.get("backend_url"))
            return {
                "ready": ready,
                "message": "Model endpoint configured; checked when analysis starts."
                if ready
                else "Set the local model endpoint in settings.",
            }
        key = PROVIDER_API_KEY_ENV[provider]
        if key and not os.getenv(key):
            return {
                "ready": False,
                "message": f"Research needs {key} in the server environment. Configure it and restart the workspace.",
            }
        if provider == "azure":
            missing = []
            if not config.get("backend_url") and not os.getenv("AZURE_OPENAI_ENDPOINT"):
                missing.append("a provider endpoint or AZURE_OPENAI_ENDPOINT")
            if not os.getenv("OPENAI_API_VERSION"):
                missing.append("OPENAI_API_VERSION")
            if missing:
                return {
                    "ready": False,
                    "message": "Azure research needs " + " and ".join(missing) + ".",
                }
            deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
            if deployment and any(
                config.get(f"{tier}_think_llm") != deployment for tier in ("quick", "deep")
            ):
                return {
                    "ready": False,
                    "message": "Azure's server deployment override conflicts with the model names. Match both model fields to AZURE_OPENAI_DEPLOYMENT_NAME, or remove that environment override and restart.",
                }
        return {
            "ready": True,
            "message": "Model configuration present; checked when analysis starts.",
        }

    def save_config(self, changes, *, add_symbol=None, expected_revision=None):
        if self.browse_only and set(changes) - {"name", "universe"}:
            raise ValueError("Read-only review allows only index name and symbols to change")
        with self.execution_lock, self.store.lock:
            if add_symbol is not None:
                from .app_database import StoreConflict
                if type(expected_revision) is not int or expected_revision != self.store.data["config_revision"]:
                    raise StoreConflict(self.store.data["config_revision"])
                changes = {"universe": list(dict.fromkeys([*self.store.data["config"]["universe"], add_symbol]))}
            if any(
                run["status"] in {"queued", "running", "cancelling"}
                for run in self.store.data["runs"]
            ):
                raise ValueError("Wait for the current analysis to stop before changing settings.")
            config = DeskConfig.model_validate({**self.store.data["config"], **changes})
            self.store.data["config"] = config.model_dump()
            self.store.data["config_revision"] += 1
            self.store.save()
            self.configure_symbols()
        return self.state()

    def connection_context(self, runtime):
        from .alpaca_readonly import trading_endpoint, TRADING_ORIGINS
        try:
            configured = trading_endpoint(self.runtime.credentials_file)
            intent, error = TRADING_ORIGINS[configured], None
        except (OSError, ValueError, KeyError):
            configured, intent, error = None, "unknown", "Configured Alpaca origin is unavailable or unsupported; correct the file and explicitly reconnect"
        identity = runtime.get("connection_identity") or {}
        account = runtime.get("account") or {}
        current = (runtime.get("status") == "connected" and account.get("id")
            and identity.get("account_id") == account["id"] and identity.get("endpoint") == runtime.get("endpoint")
            and runtime.get("connection_session") and runtime.get("connection_session") == runtime.get("native_epoch"))
        observed = TRADING_ORIGINS.get(runtime.get("endpoint"), "unknown") if current else "unknown"
        return {"configured_mode": intent, "configured_endpoint": configured, "configuration_error": error,
            "observed_mode": observed, "observed_account_id": account.get("id") if current else None,
            "session_endpoint": runtime.get("endpoint"), "session_id": runtime.get("connection_session"),
            "mode_basis": "Official trading origin and authenticated account in the current native session",
            "reconnect_to_apply": bool(error or configured != runtime.get("endpoint")),
            "credential_policy": "Credentials and destination are pinned until an explicit new native session"}

    def _runtime_market(self):
        runtime = self.runtime.state()
        connection_identity = self.connection_context(runtime)
        available = runtime["status"] == "connected"
        from .investor import DEFAULT as INVESTOR_DEFAULT
        rule = self.store.database.read("investor", INVESTOR_DEFAULT)["data"]["policy"]["rules"].get("session_freshness", {})
        opened = runtime.get("market_open")
        maximum = _number(rule.get("value") if opened is True else rule.get("closed_max_age_seconds"))
        configured = (rule.get("state") == "enabled" and type(opened) is bool and maximum is not None and maximum > 0
                      and rule.get("session") in {"regular_session_required", "allow_closed_session_review"})
        quotes = {}
        for symbol in dict.fromkeys(self.store.data["config"]["universe"] + [p["symbol"] for p in runtime.get("positions", [])]):
            observation = runtime.get("market_data", {}).get(symbol, {}) if available else {}
            trade, quote = observation.get("trade"), observation.get("quote")
            price = float(trade["price"]) if trade else (
                (float(quote["bid_price"]) + float(quote["ask_price"])) / 2 if quote else None)
            timestamp = (trade or quote or {}).get("ts_event")
            stamp = datetime.fromtimestamp(int(timestamp) / 1e9, UTC) if timestamp else None
            age = (datetime.now(UTC) - stamp).total_seconds() if stamp else None
            previous = observation.get("previous_close")
            quotes[symbol] = {"price": price, "basis": "last_trade" if trade else "quote_midpoint" if quote else None,
                "timestamp": stamp.isoformat() if stamp else None, "feed": "Nautilus / Alpaca IEX",
                "instrument_id": (trade or quote or {}).get("instrument_id"), "source_id": (trade or quote or {}).get("trade_id"),
                "native_epoch": runtime.get("native_epoch"), "source_event_ns": timestamp,
                "source_received_ns": (trade or quote or {}).get("ts_init"),
                "stale": (age is None or not 0 <= age <= maximum) if configured else None,
                "max_age_seconds": maximum if configured else None, "age_seconds": age,
                "session": "open" if opened is True else "closed" if opened is False else None,
                "freshness_configured": configured,
                "change_pct": (price / float(previous) - 1) * 100 if price and previous else None,
                "error": observation.get("error") or (None if price else "Latest price unavailable"),
                "checked_at": runtime.get("prices_checked_at")}
        errors = [] if available else [
            {"source": source, "message": runtime.get("error") or "Start Nautilus to load engine state."}
            for source in ("connection", "account", "positions", "orders", "quotes")]
        reconciliation = runtime.get("reconciliation", {})
        if reconciliation.get("status") == "incomplete":
            errors.append({"source": "reconciliation", "message": "; ".join(reconciliation.get("gaps", []))})
        return {
            "connection": {"connected": available, "account_verified": available and bool((runtime.get("account") or {}).get("id")),
                "identity": connection_identity,
                "paper_verified": connection_identity["observed_mode"] == "paper",
                "endpoint": runtime.get("endpoint"),
                "domains": ["NautilusTrader"] if available else [],
                "message": "Configured Alpaca account through Nautilus; reconciliation and user command authority are reported separately." if available else
                    runtime.get("error") or "Nautilus is stopped. Current cash and holdings are unavailable; saved research remains readable."},
            "account": runtime.get("account") if available else None,
            "positions": runtime.get("positions") or [],
            "orders": runtime.get("orders") or [],
            "open_orders": runtime.get("orders") or [],
            "fills": runtime.get("fills") or [], "reconciliation": reconciliation,
            "broker_observation": runtime.get("broker_observation", {}),
            "quotes": quotes, "history": {}, "bars": {},
            "clock": {"is_open": runtime.get("market_open")} if available else None,
            "errors": errors, "updated_at": runtime.get("account_at") if available else None,
            "quotes_updated_at": runtime.get("prices_checked_at") if available else None,
        }

    def refresh_quotes(self):
        with self.maintenance:
            runtime, store = self.runtime, self.store
        runtime.request("refresh")
        with self.maintenance:
            if self.runtime is not runtime or self.store is not store:
                raise ValueError("Application generation changed; refresh the current account again")
            market = self._runtime_market()
            return {key: market[key] for key in ("quotes", "clock", "quotes_updated_at")}

    def native_report(self, request):
        kind = request.get("report_kind")
        if not isinstance(kind, str) or kind not in {"orders", "order_fills", "fills", "positions", "account"}:
            raise ValueError("Choose an available native cached report")
        with self.maintenance:
            runtime, store = self.runtime, self.store
        report = runtime.request("native_report", report_kind=kind)["native_report"]
        with self.maintenance:
            if self.runtime is not runtime or self.store is not store:
                raise ValueError("Application generation changed; capture the current native report again")
            capture = None
            if kind == "positions":
                from .decision_journal import DEFAULT
                if not isinstance(report.get("position_lifecycles"), list):
                    raise ValueError("This native worker lacks position membership capture; the table alone cannot establish lifecycle attribution")
                identity = str(uuid4())
                reference = self.store._write_json_artifact(identity, "native-position-report", report)
                capture = {"id": identity, "artifact": reference, "captured_at": report["captured_at"],
                    "native_epoch": report["native_epoch"], "account_context": report["account_context"]}
                record = self.store.database.read("reporting", DEFAULT)
                def retain(saved):
                    saved.setdefault("native_position_captures", []).append(capture)
                    return saved
                self.store.database.update("reporting", record["revision"], retain, DEFAULT)
            return {**report, "capture": capture, "store_generation": self.store.directory.resolve().as_posix()}

    def refresh(self):
        # Connecting is explicit; page loads and research never start an execution strategy.
        self.runtime.start()
        return self.state()

    def _book(self):
        market = self._runtime_market()
        if not market["connection"]["connected"] or not market["account"]:
            raise ValueError("A connected, current Nautilus account is required. Start Nautilus and wait for connection.")
        return market

    def start_run(self, symbols=None, expected_revision=None, analysis_date=None, exclude_fred=False):
        if not isinstance(exclude_fred, bool):
            raise ValueError("exclude_fred must be a boolean")
        request_started = time.monotonic()
        requested_at = now()
        request = {
            "id": str(uuid4()), "owner_kind": "research_request", "run_id": None,
            "status": "preflight", "started_at": requested_at, "ended_at": None, "elapsed_seconds": None,
            "stages": [], "snapshots": [], "capture_complete": True,
            "source_evidence": {"attempts": [], "snapshots": [], "capture_complete": True,
                                "coverage": "research_preflight_local_boundaries"},
            "gateway_evidence": {"attempts": [], "snapshots": [], "capture_complete": True,
                                 "internal_http_requests": None, "internal_model_executions": None},
            "jev_evidence": {"attempts": [], "snapshots": [], "capture_complete": True,
                             "internal_http_requests": None, "internal_model_executions": None},
            "timing_scope": "Service start_run entry through acceptance or rejection, including scheduling. "
                            "Overlaps accepted run elapsed; do not add these totals. Queue/worker timing is in the linked run. "
                            "HTTP parsing and authorization before start_run are outside this scope.",
        }
        with self.store.lock:
            self.store.data["research_requests"].insert(0, request)
        self._request_checkpoint(request, "request_started")
        terminal = {"status": "accepted"}
        try:
            with capture_vendor_evidence(self._evidence_recorder(request["id"])):
                result = self._start_run(symbols, expected_revision, analysis_date, request, request_started, exclude_fred)
            return result
        except BaseException as exc:
            terminal = {"status": "interrupted" if not isinstance(exc, Exception) else
                        "failed" if request["run_id"] else "rejected",
                        "error_class": self._request_error_class(exc)}
            raise
        finally:
            with self.store.lock:
                request.update(**terminal, ended_at=now(), elapsed_seconds=time.monotonic() - request_started)
                for origin in ("source", "gateway", "jev"):
                    try:
                        self.store.finalize_call_evidence(request, origin)
                    except Exception:
                        request.update(capture_complete=False, persistence_error="Request call evidence export unavailable.")
                    if not request[f"{origin}_evidence"].get("capture_complete", False):
                        request["capture_complete"] = False
            self._request_checkpoint(request, "request_terminal")

    @staticmethod
    def _request_error_class(exc):
        kind = type(exc).__name__
        return kind if kind in {"ValueError", "TypeError", "RuntimeError", "OSError", "TimeoutError",
                                "GatewayError", "GatewayTimeout", "GatewayRateLimited", "InterruptedError"} else "UnexpectedError"

    def _request_checkpoint(self, request, reason):
        try:
            self.store.checkpoint_request(request, reason)
        except Exception:
            request.update(capture_complete=False, persistence_error="Request evidence checkpoint unavailable.")

    @contextmanager
    def _request_stage(self, request, name):
        started = time.monotonic()
        stage = {"stage": name, "started_at": now(), "ended_at": None, "elapsed_seconds": None, "outcome": "running"}
        with self.store.lock:
            request["stages"].append(stage)
        self._request_checkpoint(request, "stage_started")
        try:
            yield
            stage["outcome"] = "success"
        except BaseException as exc:
            stage.update(outcome="error" if isinstance(exc, Exception) else "unknown",
                         error_class=self._request_error_class(exc))
            raise
        finally:
            stage.update(ended_at=now(), elapsed_seconds=time.monotonic() - started)
            self._request_checkpoint(request, "stage_finished")

    def _start_run(self, symbols, expected_revision, analysis_date, request, request_started, exclude_fred=False):
        requested_at = request["started_at"]
        with self._request_stage(request, "validation"):
            trade_date = today() if analysis_date is None else analysis_date
            # Reuse the MCP binding's canonical/New York date validation without discovery.
            try:
                build_langchain_tools(self.gateway, domains=(), trade_date=trade_date)
            except GatewayError as exc:
                raise ValueError(str(exc)) from exc
            with self.store.lock:
                for prior in self.store.data["runs"]:
                    if prior.get("retry_at"):
                        remaining = (datetime.fromisoformat(prior["retry_at"]) - datetime.now(UTC)).total_seconds()
                        if remaining > 0:
                            raise GatewayRateLimited(remaining)
        with self._request_stage(request, "readiness"):
            ready = self.readiness(self.store.snapshot()["config"], refresh=True)
            if not ready["ready"]:
                raise ValueError(ready["message"])
        with self._request_stage(request, "refresh"):
            self.refresh()
            self.runtime.request("refresh")
            market = self._book()
        with self._request_stage(request, "admission"), self.execution_lock, self.store.lock:
            if expected_revision is not None and (
                isinstance(expected_revision, bool) or not isinstance(expected_revision, int)
                or expected_revision != self.store.data["config_revision"]
            ):
                raise ValueError("Workspace settings changed. Refresh and review the research selection again.")
            config = copy.deepcopy(self.store.data["config"])
            config["exclude_fred"] = exclude_fred
            config["selected_analysts"] = list(DESK_ANALYSTS)
            symbols = symbols or config["universe"]
            if (
                not isinstance(symbols, list)
                or not symbols
                or any(s not in config["universe"] for s in symbols)
            ):
                raise ValueError("Choose symbols from the configured universe.")
            symbols = list(dict.fromkeys(symbols))
            if trade_date == today() and any(market["quotes"].get(symbol, {}).get("price") is None for symbol in symbols):
                raise ValueError("Research inputs incomplete: wait for the selected symbols' Nautilus price snapshots.")
            if any(
                r["status"] in {"queued", "running", "cancelling"} for r in self.store.data["runs"]
            ) or any(not future.done() for future in self.research_futures):
                raise ValueError("An analysis is already running.")
            run = {
                "id": str(uuid4()),
                "request_id": request["id"],
                "status": "queued",
                "created_at": now(),
                "trade_date": trade_date,
                "account_context": {
                    "basis": "current",
                    "captured_at": market["updated_at"],
                    "description": "Nautilus account cash and holdings captured at run creation; "
                    "not a historical portfolio snapshot for the analysis date.",
                },
                "symbols": symbols,
                "config": config,
                "events": [],
                "results": [],
                "account_id": market["account"]["id"],
                "portfolio_evidence": {
                    "status": "unavailable",
                    "reason": "No graph has consumed a portfolio context for this run yet.",
                },
                "gateway_evidence": {
                    "attempts": [], "snapshots": [], "capture_complete": True,
                    "internal_http_requests": None, "internal_model_executions": None,
                },
                "jev_evidence": {
                    "attempts": [], "snapshots": [], "capture_complete": True,
                    "internal_http_requests": None, "internal_model_executions": None,
                },
                "source_evidence": {
                    "coverage": "router_functions_and_social_ohlcv_inputs",
                    "capture_complete": True,
                    "attempts": [],
                    "snapshots": [],
                    "limitations": "Nested acquisition boundaries overlap router attempts; do not add them "
                                   "as provider requests. Gateway calls have separate gateway_evidence. "
                                   "Jev screening has separate jev_evidence; hidden SDK/provider retries are not captured. "
                                   "Success means the boundary returned, not usable data.",
                },
                "measurements": {
                    "started_at": requested_at,
                    "ended_at": None,
                    "elapsed_seconds": None,
                    "callbacks": StatsCallbackHandler().get_measurements(),
                    "stages": [{"stage": "preflight", "elapsed_seconds": time.monotonic() - request_started}],
                },
            }
            from tradingagents.graph.checkpointer import desk_checkpoint_signature
            run["continuation"] = {"version": 1, "revision": 0, "source_signature": desk_checkpoint_signature(),
                "market": copy.deepcopy(market), "attempts": [{"id": str(uuid4()), "parent_id": None,
                    "started_at": requested_at, "status": "queued"}]}
            self.store.data["runs"].insert(0, run)
            request["run_id"] = run["id"]
            self.store.save()
        queued_at = time.monotonic()
        try:
            with self._request_stage(request, "scheduling"):
                future = self.executor.submit(self._run, run["id"], market, request_started, queued_at)
                self.research_futures.add(future)
                future.add_done_callback(self.research_futures.discard)
        except Exception:
            with self.store.lock:
                run.update(status="failed", error="Analysis worker could not be scheduled.")
                self._finish_measurements(run, StatsCallbackHandler(), request_started)
            raise
        return {"run_id": run["id"]}

    def _find_run(self, run_id):
        return next(r for r in self.store.data["runs"] if r["id"] == run_id)

    def _event(self, run_id, kind, message, symbol=None, **extra):
        with self.store.lock:
            run = self._find_run(run_id)
            run["events"].append(
                {"time": now(), "kind": kind, "message": message, "symbol": symbol, **extra}
            )
            run["events"] = run["events"][-500:]
            self.store.save()

    def _finish_measurements(self, run, stats, request_started):
        # Persist terminal state first: the measured interval includes this durable checkpoint.
        run["completed_at"] = now()
        self.store.save()
        measurements = run["measurements"]
        measurements.update(
            run_id=run["id"], status=run["status"], ended_at=now(),
            elapsed_seconds=time.monotonic() - request_started,
            callbacks=stats.get_measurements(),
            timing_scope="Request entry through durable terminal journal checkpoint; "
                         "includes preflight, queueing and observed retry waits. "
                         "Artifact publication and its final reference save are excluded.",
        )
        try:
            run["measurement_artifact"] = self.store.write_measurements(run["id"], measurements)
        except OSError:
            run["measurement_export_error"] = "Measurement artifact could not be written; measurements remain in journal."
        for origin in ("source", "gateway", "jev"):
            try:
                self.store.finalize_call_evidence(run, origin)
            except Exception:
                run.setdefault(f"{origin}_evidence", {}).update(
                    capture_complete=False, persistence_error="Call terminal evidence export failed."
                )
        if run.get("continuation"):
            continuation = run["continuation"]
            continuation["attempts"][-1].update(status=run["status"], ended_at=now(),
                reason=run.get("error"), measurements=copy.deepcopy(measurements),
                measurement_artifact=run.get("measurement_artifact"))
            continuation["revision"] += 1
        self.store.save()

    def _evidence_recorder(self, owner_id, symbol=None):
        def record(receipt, output):
            if symbol is not None:
                receipt = {**receipt, "symbol": symbol}
            try:
                self.store.record_source_attempt(owner_id, receipt, output)
            except Exception:
                with self.store.lock:
                    origin = receipt.get("origin")
                    key = f"{origin}_evidence" if origin in {"gateway", "jev"} else "source_evidence"
                    evidence = self.store._evidence_owner(owner_id).setdefault(key, {})
                    evidence.update(capture_complete=False, persistence_error="Source receipt persistence failed.")
                    # In-memory failure remains available if a later journal save succeeds.
                    with suppress(Exception):
                        self.store.save()
        return record

    def _run(self, run_id, market, request_started, queued_at):
        with capture_vendor_evidence(self._evidence_recorder(run_id)):
            self._run_with_evidence(run_id, market, request_started, queued_at)

    def continuation_status(self, run_id):
        from tradingagents.graph.checkpointer import desk_checkpoint_exists, desk_checkpoint_signature
        with self.store.lock:
            run = self._find_run(run_id)
            continuation = run.get("continuation", {})
            reason = ""
            if continuation.get("version") != 1:
                reason = "This saved run predates resumable desk checkpoints."
            elif run.get("cancel_requested_at") or run["status"] in {"cancelled", "cancelling"}:
                reason = "Operator cancellation is retained; this run cannot continue."
            elif run["status"] != "interrupted":
                reason = "Only an interrupted run can continue."
            elif any(item["status"] in {"queued", "running", "cancelling"} for item in self.store.data["runs"]) or any(not future.done() for future in self.research_futures):
                reason = "Another analysis owns the research worker."
            elif continuation.get("source_signature") != desk_checkpoint_signature():
                reason = "Execution source or installed persistence versions changed; start a new run."
            elif continuation.get("blocked_reason"):
                reason = continuation["blocked_reason"]
            elif (not run.get("source_evidence", {}).get("capture_complete", False)
                  or any(call_evidence_failed(run.get(f"{origin}_evidence", {})) for origin in ("gateway", "jev"))):
                reason = "Interrupted evidence capture is incomplete; continuation cannot verify prior outcomes."
            elif any(source_attempt_failed(attempt, run.get("source_evidence", {}).get("attempts", []))
                     for attempt in run.get("source_evidence", {}).get("attempts", [])):
                reason = "Original source collection is incomplete; retained failures cannot be silently replaced by continuation."
            symbols = []
            for symbol in run["symbols"]:
                result = next((item for item in run["results"] if item["symbol"] == symbol), {})
                saved = result.get("continuation", {})
                budget = saved.get("social_budget", {})
                exists = bool(saved.get("thread_id")) and desk_checkpoint_exists(self.store.directory / "cache", symbol, saved["thread_id"])
                pending_social = any(row.get("status") == "pending" for source in result.get("social_sentiment", {}).get("sources", {}).values() for row in source.get("posts", []))
                pending_effect = next((effect for effect in saved.get("effects", {}).values()
                                       if effect["stateful"] and effect["outcome"] != "confirmed"), None)
                unfinished_social = result.get("social_sentiment", {}).get("status") != "completed"
                if result and result.get("status") != "completed" and not reason:
                    if not exists:
                        reason = f"No durable checkpoint is available for {symbol}."
                    elif pending_effect:
                        reason = f"{pending_effect['command']} has an uncertain prior outcome; it will not be replayed."
                    elif pending_social:
                        reason = f"A {symbol} social request has an unknown outcome; it will not be replayed."
                    elif unfinished_social and budget.get("expires_at") and budget["expires_at"] <= datetime.now(UTC).timestamp():
                        reason = f"The original {symbol} social screening time budget expired."
                    elif unfinished_social and budget.get("remaining") == 0:
                        reason = f"The original {symbol} social screening post budget is exhausted."
                    elif unfinished_social and budget.get("remaining_seconds") == 0:
                        reason = f"The original {symbol} social processing allowance is exhausted."
                symbols.append({"symbol": symbol, "status": result.get("status", "not_started"),
                    "remaining_posts": budget.get("remaining", run["config"].get("social_screen_max_posts", 100)),
                    "expires_at": datetime.fromtimestamp(budget["expires_at"], UTC).isoformat() if budget.get("expires_at") else None,
                    "checkpoint_available": exists})
            if not reason and not any(item["checkpoint_available"] for item in symbols):
                reason = "No durable symbol checkpoint is available."
            return {"run_id": run_id, "revision": continuation.get("revision", 0), "eligible": not bool(reason),
                    "reason": reason, "analysis_date": run["trade_date"], "original_created_at": run["created_at"],
                    "account_captured_at": run.get("account_context", {}).get("captured_at"),
                    "attempts": [{key: attempt.get(key) for key in ("id", "parent_id", "started_at", "ended_at", "status", "reason")}
                                 for attempt in continuation.get("attempts", [])], "symbols": symbols}

    def resume_run(self, run_id, revision):
        with self.maintenance, self.execution_lock, self.store.lock:
            if self.browse_only:
                raise ValueError("Research continuation is unavailable in review-only mode.")
            status = self.continuation_status(run_id)
            if type(revision) is not int or revision != status["revision"]:
                raise ValueError("Continuation state changed. Refresh and review it again.")
            if not status["eligible"]:
                raise ValueError(status["reason"])
            run = self._find_run(run_id)
            continuation = run["continuation"]
            if run.get("retry_at") and datetime.fromisoformat(run["retry_at"]) > datetime.now(UTC):
                raise ValueError("The recorded upstream retry delay has not elapsed.")
            attempt = {"id": str(uuid4()), "parent_id": continuation["attempts"][-1]["id"],
                       "started_at": now(), "status": "queued"}
            attempt["previous_results"] = self.store._write_json_artifact(run_id, "continuation-prior-results", run["results"])
            continuation["attempts"].append(attempt)
            continuation["revision"] += 1
            run["status"] = "queued"
            continuation.setdefault("measurement_history", []).append(copy.deepcopy(run.get("measurements", {})))
            run["measurements"] = {"started_at": now(), "stages": [], "callbacks": {}}
            run.pop("error", None)
            run.pop("completed_at", None)
            for origin in ("source", "gateway", "jev"):
                evidence = run.get(f"{origin}_evidence", {})
                if "terminal_observed_at" in evidence:
                    continuation.setdefault("terminal_evidence_history", []).append(
                        {"origin": origin, "terminal_observed_at": evidence.pop("terminal_observed_at")})
            self.store.save()
            started = time.monotonic()
            try:
                future = self.executor.submit(self._run, run_id, copy.deepcopy(continuation["market"]), started, started)
                self.research_futures.add(future)
                future.add_done_callback(self.research_futures.discard)
            except Exception:
                run["status"] = "interrupted"
                attempt.update(status="interrupted", ended_at=now(), reason="Continuation scheduling failed.")
                self.store.save()
                raise
            return {"run_id": run_id, "status": "queued", "continuation_revision": continuation["revision"]}

    def _research_effect(self, run, result, domain, command, call_id, parameters, dispatch, *, stateful=True, interruptible=True):
        from .approval_review import read_artifact
        identity = hashlib.sha256(f"{domain}:{command}:{call_id}".encode()).hexdigest()
        arguments = hashlib.sha256(json.dumps(parameters, sort_keys=True, allow_nan=False).encode()).hexdigest()
        with self.store.lock:
            effects = result["continuation"].setdefault("effects", {})
            prior = effects.get(identity)
            reason = run["continuation"].get("blocked_reason")
            if run.get("cancel_requested_at"):
                reason = "Analysis stopped by operator; cancellation remains in force."
            if not reason and prior and prior["arguments_sha256"] != arguments:
                reason = "A retained external call identity has different arguments."
            elif not reason and prior and prior["outcome"] == "rejected":
                raise GatewayRejected(prior["error"])
            elif not reason and prior and prior["outcome"] == "confirmed":
                retained_arguments = read_artifact(self.store.directory, prior["arguments"])
                if (retained_arguments is None or retained_arguments != parameters
                        or hashlib.sha256(json.dumps(retained_arguments, sort_keys=True, allow_nan=False).encode()).hexdigest() != arguments):
                    reason = "A retained external call's argument artifact is missing or changed."
                else:
                    retained = read_artifact(self.store.directory, prior["result"])
                    if isinstance(retained, dict) and "value" in retained:
                        return retained["value"]
                    reason = "A confirmed external result is missing or changed."
            elif not reason and prior and stateful:
                reason = f"{command} has an uncertain prior outcome and cannot be replayed."
            if reason:
                run["continuation"]["blocked_reason"] = reason
                self.store.save()
        if reason:
            if interruptible:
                from langgraph.types import interrupt
                interrupt(reason)
            raise ValueError(reason)
        attempt = None

        def on_dispatch():
            nonlocal attempt
            with self.store.lock:
                attempt = {"id": str(uuid4()), "parent_id": prior["id"] if prior else None,
                    "domain": domain, "command": command, "tool_call_id": call_id, "arguments_sha256": arguments,
                    "stateful": stateful, "outcome": "intent", "started_at": now(),
                    "history": [*prior.get("history", []), {key: value for key, value in prior.items() if key != "history"}] if prior else []}
                attempt["arguments"] = self.store._write_source_result(run["id"], attempt["id"], parameters, prefix="continuation-arguments")
                effects[identity] = attempt
                self.store.save()
        try:
            if domain == "local":
                on_dispatch()
                value = dispatch()
            else:
                value = dispatch(on_dispatch=on_dispatch)
            with self.store.lock:
                attempt["result"] = self.store._write_source_result(run["id"], attempt["id"], {"value": value}, prefix="continuation-result")
                attempt.update(outcome="confirmed", ended_at=now())
                self.store.save()
            return value
        except BaseException as exc:
            if attempt is None:
                raise
            with self.store.lock:
                rejected = isinstance(exc, GatewayRejected)
                attempt.update(outcome="rejected" if rejected else "unknown" if stateful else "error", ended_at=now())
                if rejected:
                    attempt["error"] = str(exc)
                if stateful and not rejected:
                    run["continuation"]["blocked_reason"] = f"{command} has an uncertain outcome; automatic replay is blocked."
                self.store.save()
            raise

    def _publish_research_coverage(self, run, result):
        run_id = run["id"]
        symbol = result["symbol"]
        with self.store.lock:
            evidence_by_origin = {}
            for origin in ("source", "gateway", "jev"):
                evidence = copy.deepcopy(run.get(f"{origin}_evidence", {}))
                evidence["attempts"] = [a for a in evidence.get("attempts", [])
                                        if a.get("symbol") in {None, symbol}]
                self.store._call_counts(evidence, origin)
                evidence_by_origin[origin] = evidence
        social = result["social_sentiment"]
        result["coverage_gaps"] = [
            {key: a.get(key) for key in ("attempt_id", "operation", "vendor", "arguments", "outcome", "data_status", "error_class",
                                        "failure_kind", "error_details", "http_status", "attempt", "ordinal", "retry_action", "retry_after_seconds", "capture_error", "artifact", "receipts", "parent_attempt_id", "boundary_kind") if key in a}
            for origin in ("source", "gateway", "jev") for a in evidence_by_origin[origin]["attempts"]
            if a.get("capture_error") or a.get("outcome") != "success" or a.get("data_status") in {"partial", "unavailable", "no_usable_coverage"}
        ] + [{"source": name, "status": s.get("status"), "classified_count": s.get("classified_count"),
              "total_count": s.get("total_count"), "stop_reason": s.get("stop_reason"), "error": s.get("error")}
             for name, s in social["sources"].items() if s.get("status") not in {"completed", "empty"}]
        result["coverage_gaps"] += [{"source": origin, "error": evidence["persistence_error"], "status": "persistence_failed"}
                                    for origin, evidence in evidence_by_origin.items() if evidence.get("persistence_error")]
        if result["coverage_gaps"]:
            grouped = {}
            activity = set()
            for gap in result["coverage_gaps"]:
                cause = (gap.get("capture_error") or gap.get("error") or ("HTTP " + str(gap["http_status"]) if gap.get("http_status") else "")
                         or "; ".join(dict.fromkeys(detail["message"] for detail in gap.get("error_details", [])
                                                   if detail.get("message") and detail["message"] != "Exception details withheld"))
                         or gap.get("stop_reason")
                         or "Cause not captured" + (" (" + gap["error_class"] + ")" if gap.get("error_class") else ""))
                coverage = (str(gap.get("classified_count", 0)) + "/" + str(gap.get("total_count", "unknown")) + " posts classified"
                            if "total_count" in gap else gap.get("data_status") or gap.get("status") or gap.get("outcome", "unknown"))
                line = (f"{gap.get('operation') or gap.get('source')} / {gap.get('vendor') or ('Laya' if gap.get('source') in {'reddit', 'stocktwits'} else 'local capture')}: {cause}. "
                        f"Coverage: {coverage}. Attempt: {gap.get('attempt', gap.get('ordinal', 'not captured'))}; "
                        f"retry decision: {gap.get('retry_action', 'not captured')}. Receipt: {gap.get('attempt_id', 'not captured')}. "
                        "Use retained evidence only; do not infer missing values or neutral sentiment.")
                grouped[line] = grouped.get(line, 0) + 1
                if not gap.get("parent_attempt_id") and gap.get("boundary_kind") != "gateway_invocation":
                    activity.add(line)
            limitations = ("Source failures and screening limits remain part of this research. "
                           "Workflow completion does not establish complete data coverage. "
                           "Unknown optional outcomes are not replayed. Full receipts remain in Sources.\n\n"
                           + "\n".join(f"- {line}" + (f" ({count} matching receipts)" if count > 1 else "")
                                       for line, count in grouped.items()))
            with self.store.lock:
                changed = result["reports"].get("source_coverage") != limitations
                if changed:
                    result["reports"]["source_coverage"] = limitations
                    result["revision"] += 1
                    self.store.save()
            if changed:
                for line in sorted(activity):
                    self._event(run_id, "coverage", line, symbol)
        return evidence_by_origin

    def _run_with_evidence(self, run_id, market, request_started, queued_at):
        stats = StatsCallbackHandler()
        with self.store.lock:
            run = self._find_run(run_id)
            run["status"] = "running"
            run["continuation"]["attempts"][-1]["status"] = "running"
            run["measurements"]["worker_started_at"] = now()
            run["measurements"]["stages"].append({"stage": "queue", "elapsed_seconds": time.monotonic() - queued_at})
            config = copy.deepcopy(run["config"])
            self.store.save()
        try:
            from tradingagents.agents.rating import run_rating
            from tradingagents.graph.trading_graph import TradingAgentsGraph
            from tradingagents.portfolio import PortfolioContext, Position

            portfolio = PortfolioContext(
                cash=float(market["account"]["cash"]),
                currency="USD",
                positions=[
                    Position(
                        ticker=p["symbol"],
                        quantity=float(p["qty"]),
                        average_price=_number(p.get("avg_entry_price")),
                    )
                    for p in market["positions"]
                ],
            )
            stop_dispatch = threading.Event()

            def run_symbol(symbol):
                if stop_dispatch.is_set() or run_id in self.cancelled:
                    return
                result = next((item for item in run["results"] if item["symbol"] == symbol), None)
                if result and result["status"] == "completed":
                    return
                with self.store.lock:
                    for origin in ("source", "gateway", "jev"):
                        evidence = run.get(f"{origin}_evidence", {})
                        if "terminal_observed_at" in evidence:
                            run["continuation"].setdefault("terminal_evidence_history", []).append(
                                {"origin": origin, "terminal_observed_at": evidence.pop("terminal_observed_at")})
                self._event(run_id, "symbol", "Analysis continued" if result else "Analysis started", symbol,
                            attempt_id=run["continuation"]["attempts"][-1]["id"])
                existing_result = result is not None
                result = result or {
                    "symbol": symbol,
                    "status": "running",
                    "trade_date": run["trade_date"],
                    "reports": {},
                    "rating": None,
                    "laya": None,
                    "social_sentiment": {"status": "not_requested", "model": "multilingual", "sources": {}},
                    "revision": 0,
                }
                with self.store.lock:
                    if not existing_result:
                        run["results"].append(result)
                    result["status"] = "running"
                    result.pop("error", None)
                    self.store.save()
                started = datetime.now(UTC)
                stage = "setup"
                stage_started = time.monotonic()

                def next_stage(name, measured_symbol=symbol):
                    nonlocal stage, stage_started
                    ended = time.monotonic()
                    with self.store.lock:
                        run["measurements"]["stages"].append({
                            "symbol": measured_symbol, "stage": stage,
                            "elapsed_seconds": ended - stage_started,
                        })
                    stage, stage_started = name, ended

                try:
                    graph = None
                    graph_config = build_default_config()
                    graph_config.update(config)
                    graph_config.update(
                        quick_think_provider=config["llm_provider"],
                        deep_think_provider=config["llm_provider"],
                        quick_think_backend_url=config.get("backend_url"),
                        deep_think_backend_url=config.get("backend_url"),
                        results_dir=str(self.store.directory / "reports" / run_id),
                        data_cache_dir=str(self.store.directory / "cache"),
                        memory_log_path=str(self.store.directory / "decision-memory.md"),
                        checkpoint_enabled=True,
                    )
                    saved = result.setdefault("continuation", {"thread_id": f"{run_id}:{symbol}", "effects": {},
                        "social_budget": {"remaining": config.get("social_screen_max_posts", 100),
                                          "time_policy": "active_lane_v1",
                                          "remaining_seconds": config.get("social_screen_timeout_seconds", 600),
                                          "max_seconds": config.get("social_screen_timeout_seconds", 600)}})
                    def effect(domain, command, call_id, parameters, dispatch, *, stateful=True, current=result, interruptible=True):
                        return self._research_effect(run, current, domain, command, call_id, parameters, dispatch,
                                                     stateful=stateful, interruptible=interruptible)
                    tools = build_langchain_tools(
                        self.gateway, domains=("maenifold.memory", "maenifold.graph", "maenifold.thinking"),
                        symbol=symbol, trade_date=run["trade_date"], research_effect=effect
                    )
                    social_budget = {**saved["social_budget"], "deadline": None}
                    social_gateway = (MaenifoldGateway(self.gateway.endpoint, timeout=social_budget["max_seconds"])
                                      if isinstance(self.gateway, MaenifoldGateway) else self.gateway)
                    def screen_factory(ticker, source, current=result, budget=social_budget, gateway=social_gateway, *, instrument_context=""):
                        retained = copy.deepcopy(current["social_sentiment"]["sources"].get(source))
                        def record(evidence):
                            with self.store.lock:
                                current["continuation"]["social_budget"] = {key: value for key, value in budget.items() if key != "deadline"}
                                social = current["social_sentiment"]
                                social["sources"][source] = evidence
                                statuses = [s["status"] for s in social["sources"].values()]
                                social["status"] = ("completed" if all(s in {"completed", "empty"} for s in statuses)
                                                    else "unavailable" if all(s in {"unavailable", "not_screened"} for s in statuses) else "partial")
                                current["revision"] += 1
                                self.store.save()
                        def progress(evidence, budget):
                            evidence["classified_count"] = sum(row["status"] == "classified" for row in evidence["posts"])
                            evidence["status"] = "partial"
                            with self.store.lock:
                                previous = current["social_sentiment"]["sources"].get(source, {})
                                count = evidence["classified_count"]
                                milestone = (count // 5, evidence.get("stop_reason"), evidence.get("error"))
                                changed = milestone != (previous.get("classified_count", 0) // 5,
                                    previous.get("stop_reason"), previous.get("error")) or not previous.get("posts")
                                current["continuation"]["social_budget"] = {key: value for key, value in budget.items() if key != "deadline"}
                                record(evidence)
                                if changed:
                                    self._event(run_id, "screening", f"{source}: {count}/{evidence['total_count']} posts classified. "
                                        + (evidence.get("stop_reason") or "Screening in progress."), ticker)
                        with self.store.lock:
                            if retained is None:
                                current["social_sentiment"]["sources"][source] = {
                                    "admission_version": SOCIAL_ADMISSION_VERSION,
                                    "status": "not_screened", "source": source, "counts": {}, "posts": [],
                                    "note": "No eligible posts supplied by the source; inspect the sentiment report for source availability."}
                            current["social_sentiment"]["status"] = "partial"
                            self.store.save()
                        company = re.search(r"(?:Company|Name): ([^\n;]+)", instrument_context)
                        instrument = f"{company.group(1)} ({ticker})" if company else ticker
                        return laya_screen(ticker, gateway, budget=budget, instrument=instrument,
                                           source=source, on_evidence=record,
                                           cancelled=lambda: run_id in self.cancelled,
                                           retained=retained if retained and retained.get("posts") else None, on_progress=progress)
                    graph = (self.graph_factory or TradingAgentsGraph)(
                        selected_analysts=config["selected_analysts"],
                        config=graph_config, supplemental_tools=tools, callbacks=[stats],
                        social_screen_factory=screen_factory,
                        research_effect=effect,
                    )
                    graph_signature = graph._run_signature("stock", portfolio)
                    if saved.get("graph_signature") and saved["graph_signature"] != graph_signature:
                        raise ValueError("Saved graph settings or tool schemas changed; continuation is blocked.")
                    saved["graph_signature"] = graph_signature
                    final = {}
                    seen = set()
                    memory_seen = None
                    initial = copy.deepcopy(saved.get("initial"))
                    if initial is None:
                        initial = graph.create_run_state(symbol, run["trade_date"], portfolio=portfolio)
                    initial["desk_execution_policy"] = desk_execution_policy(config)
                    quote_context = result.get("quote_context") or research_quote_context(symbol, run["trade_date"], market)
                    if "initial" not in saved:
                        initial["instrument_context"] = initial.get("instrument_context", f"Instrument: {symbol}.") + "\n\n" + quote_context
                    if config.get("exclude_fred") and "initial" not in saved:
                        initial["instrument_context"] += "\nFRED macro data excluded by operator for this run during provider maintenance. Macro coverage is unverified; do not claim complete macro coverage."
                    with self.store.lock:
                        result["quote_context"] = quote_context
                        result["desk_execution_policy"] = initial["desk_execution_policy"]
                        self.store.save()
                    if "initial" not in saved:
                        self.store.record_portfolio_context(run_id, {
                        "schema_version": 1,
                        "run_id": run_id,
                        "analysis_date": run["trade_date"],
                        "account_id": market["account"]["id"],
                        "account_context": copy.deepcopy(run["account_context"]),
                        "portfolio": portfolio.model_dump(mode="json"),
                        })
                    account_context = run.get("account_context")
                    if account_context and "initial" not in saved:
                        initial["portfolio_context"] = (
                            f"{account_context['description']} Captured at {account_context['captured_at']}.\n"
                            + initial.get("portfolio_context", "")
                        )
                    with self.store.lock:
                        saved["initial"] = initial
                        self.store.save()
                    graph.begin_checkpoint(symbol, run["trade_date"], portfolio=portfolio, identity=saved["thread_id"])
                    graph_args = graph.propagator.get_graph_args()
                    graph_args["config"] = {**graph_args.get("config", {}), "callbacks": [stats],
                                            "configurable": {"thread_id": saved["thread_id"]}}
                    graph_args["durability"] = "sync"
                    snapshot = graph.graph.get_state(graph_args["config"], subgraphs=True)
                    final.update(snapshot.values)
                    if snapshot.metadata:
                        remaining_steps = graph_config["max_recur_limit"] - max(0, snapshot.metadata.get("step", 0))
                        if remaining_steps <= 0 and snapshot.next:
                            raise ValueError("The original research graph step budget is exhausted.")
                        graph_args["config"]["recursion_limit"] = max(1, remaining_steps)
                    next_stage("analysis")
                    stream = (() if graph._resuming and not snapshot.next else
                              graph.stream_run(graph.checkpoint_input(initial), **graph_args))
                    for messages, state in stream:
                        if run_id in self.cancelled:
                            raise InterruptedError("Analysis stopped by operator.")
                        for message in messages:
                            key = getattr(message, "id", None) or str(message)[:300]
                            if key in seen:
                                continue
                            seen.add(key)
                            for call in getattr(message, "tool_calls", []) or []:
                                self._event(run_id, "tool", call.get("name", "Tool call"), symbol)
                        if state:
                            final.update(state)
                            memory = {key: {"present": key in state, "value": state.get(key)}
                                      for key in ("past_context", "memory_note")}
                            if memory != memory_seen:
                                observe_source_call(
                                    "memory_context", "local", "graph_memory_state", lambda memory=memory: memory,
                                    symbol=symbol, trade_date=run["trade_date"],
                                )
                                memory_seen = memory
                            for key in REPORT_KEYS:
                                if state.get(key) and result["reports"].get(key) != state[key]:
                                    with self.store.lock:
                                        result["reports"][key] = state[key]
                                        result["revision"] += 1
                                        self.store.save()
                                    self._event(
                                        run_id, "report", key.replace("_", " ").capitalize(), symbol
                                    )
                            for key in ("investment_debate_state", "risk_debate_state"):
                                if state.get(key):
                                    with self.store.lock:
                                        content = json.dumps(state[key], ensure_ascii=False, indent=2)
                                        if result["reports"].get(key) != content:
                                            result["reports"][key] = content
                                            result["revision"] += 1
                    next_stage("decision_persistence")
                    if run["continuation"].get("blocked_reason"):
                        raise ValueError(run["continuation"]["blocked_reason"])
                    terminal = graph.graph.get_state(graph_args["config"], subgraphs=True)
                    if terminal.next or terminal.interrupts:
                        raise ValueError("Research checkpoint still has pending steps; continuation did not complete.")
                    final.update(terminal.values)
                    with self.store.lock:
                        for key in (*REPORT_KEYS, "investment_debate_state", "risk_debate_state"):
                            if final.get(key):
                                content = (json.dumps(final[key], ensure_ascii=False, indent=2)
                                           if key.endswith("_debate_state") else final[key])
                                if result["reports"].get(key) != content:
                                    result["reports"][key] = content
                                    result["revision"] += 1
                        self.store.save()
                    evidence_by_origin = self._publish_research_coverage(run, result)
                    missing = [key for key in ANALYST_REPORTS if not result["reports"].get(key)]
                    if missing:
                        raise ValueError(f"Research incomplete: missing analyst reports: {', '.join(missing)}")
                    failures = [a["operation"] for a in evidence_by_origin["source"]["attempts"]
                                if source_attempt_failed(a, evidence_by_origin["source"]["attempts"])]
                    if failures or not evidence_by_origin["source"].get("capture_complete"):
                        raise ValueError(f"Research incomplete: source collection or evidence capture failed: {', '.join(sorted(set(failures))) or 'source evidence persistence'}")
                    if any(call_evidence_failed(evidence_by_origin[origin]) for origin in ("gateway", "jev")):
                        raise ValueError("Research incomplete: Gateway or Jev evidence capture failed.")
                    for origin in ("source", "gateway", "jev"):
                        with self.store.lock:
                            self.store._snapshot_call_evidence(run, f"symbol_terminal:{symbol}", origin)
                    if any(run.get(f"{origin}_evidence", {}).get("persistence_error")
                           for origin in ("source", "gateway", "jev")):
                        raise ValueError("Research incomplete: terminal evidence publication failed.")
                    effect("local", "Record decision", "record-decision", {"final": {key: value for key, value in final.items() if key != "messages"}},
                           lambda: graph.record_decision(symbol, run["trade_date"], final), interruptible=False)
                    rating = run_rating(final)
                    if run_id in self.cancelled:
                        raise InterruptedError("Analysis stopped by operator.")
                    with self.store.lock:
                        result.update(
                            status="completed", completed_at=now(),
                            rating=rating,
                            elapsed_seconds=round((datetime.now(UTC) - started).total_seconds(), 1),
                            revision=result["revision"] + 1,
                        )
                        self.store.save()
                    self._event(
                        run_id,
                        "complete",
                        f"{rating} · Research completed" + (" with coverage gaps; inspect Source coverage and Activity" if result["coverage_gaps"] else ""),
                        symbol,
                    )
                except InterruptedError as exc:
                    stop_dispatch.set()
                    with self.store.lock:
                        result.update(status="cancelled", error=str(exc))
                        self.store.save()
                    return
                except Exception as exc:
                    stop_dispatch.set()
                    with self.store.lock:
                        resumable = bool(result.get("continuation", {}).get("thread_id"))
                        result.update(status="interrupted" if resumable else "failed", error=str(exc)[:600])
                        run["error"] = str(exc)[:600]
                        self.store.save()
                    self._publish_research_coverage(run, result)
                    self._event(run_id, "error", str(exc)[:600], symbol)
                    if isinstance(exc, GatewayRateLimited):
                        # Stop the sweep. Keep completed evidence and leave later stocks unstarted.
                        with self.store.lock:
                            run["error"] = str(exc)
                            run["retry_at"] = (datetime.now(UTC) + timedelta(seconds=exc.retry_after)).isoformat()
                        return
                    if resumable:
                        return
                finally:
                    if graph is not None:
                        graph.end_checkpoint()
                    next_stage(None)
                    with self.store.lock:
                        result["elapsed_seconds"] = round((datetime.now(UTC) - started).total_seconds(), 3)
                        run["measurements"]["callbacks"] = stats.get_measurements()
                        self.store.save()

            def research_symbol(symbol):
                with capture_vendor_evidence(self._evidence_recorder(run_id, symbol)):
                    run_symbol(symbol)

            pending_symbols = iter(run["symbols"])
            with ThreadPoolExecutor(max_workers=config.get("research_concurrency", 1),
                                    thread_name_prefix="stock-research") as workers:
                active = set()

                def fill_slots():
                    while (len(active) < config.get("research_concurrency", 1)
                           and not stop_dispatch.is_set() and run_id not in self.cancelled):
                        symbol = next(pending_symbols, None)
                        if symbol is None:
                            break
                        active.add(workers.submit(copy_context().run, research_symbol, symbol))

                fill_slots()
                while active:
                    finished, active = wait(active, return_when=FIRST_COMPLETED)
                    for future in finished:
                        future.result()
                    fill_slots()
            with self.store.lock:
                run["status"] = (
                    "cancelled"
                    if run_id in self.cancelled
                    else (
                        "completed"
                        if len(run["results"]) == len(run["symbols"]) and all(r["status"] == "completed" for r in run["results"])
                        else "interrupted" if any(r["status"] == "interrupted" for r in run["results"]) else "failed"
                    )
                )
                run["completed_at"] = now()
                self.store.save()
        except Exception as exc:
            with self.store.lock:
                run.update(status="failed", error=str(exc)[:600])
                self.store.save()
        finally:
            with self.store.lock:
                self._finish_measurements(run, stats, request_started)

    def cancel_run(self, run_id):
        with self.store.lock:
            run = self._find_run(run_id)
            if run["status"] not in {"queued", "running", "cancelling"}:
                raise ValueError("This analysis is no longer running.")
            self.cancelled.add(run_id)
            run.setdefault("cancel_requested_at", now())
            if run.get("continuation"):
                run["continuation"]["revision"] += 1
            run["status"] = "cancelling"
            self.store.save()
        return {
            "status": "cancelling",
            "message": "Stops at the next agent step; in-flight calls finish first.",
        }

    def propose(self, run_id):
        raise ValueError("Order creation unavailable: no Nautilus sizing policy is configured.")

    def evaluations(self, identity=None):
        from .approval_review import read_artifact
        from .decision_journal import DEFAULT as REPORTING_DEFAULT
        store = self.store
        record = store.database.read("reporting", REPORTING_DEFAULT)
        if any(item.get("kind") == "experiment" and item.get("session_id") != self.simulation_session
               and item["status"] in {"queued", "running", "cancelling"} for item in record["data"].get("simulations", {}).values()):
            def interrupted(records):
                for item in records["reporting"].get("simulations", {}).values():
                    if item.get("kind") == "experiment" and item.get("session_id") != self.simulation_session and item["status"] in {"queued", "running", "cancelling"}:
                        item.update(status="interrupted", interruption={"at": datetime.now(UTC).isoformat(),
                            "reason": "Service generation changed; dispatched outcomes may be unknown. No automatic retry, continuation or RNG resume."})
            with self.maintenance:
                if self.store is not store:
                    raise ValueError("Application generation changed; reopen the retained evaluation")
                record = store.database.transact({"reporting": REPORTING_DEFAULT}, interrupted)["reporting"]
        items = copy.deepcopy(record["data"].get("simulations", {}))
        for item in items.values():
            if item.get("session_id") != self.simulation_session and item["status"] in {"queued", "running"}:
                item.update(status="interrupted", error="Service stopped; this simulation is not resumed automatically")
        if identity:
            item = items[identity]
            if item.get("kind") in {"experiment", "experiment_comparison"}:
                return self.experiment_detail(item, record["revision"])
            for kind in ("preview", "result"):
                if item.get(kind + "_artifact"):
                    value = read_artifact(self.store.directory, item[kind + "_artifact"])
                    if value is None:
                        raise ValueError("Saved simulation evidence is unavailable or changed")
                    item[kind] = {key: val for key, val in value.items() if key != "bars"}
            return item
        from .evaluation import digest, experiment_capabilities
        from .investor import DEFAULT as INVESTOR_DEFAULT
        from .market_history import DEFAULT as HISTORY_DEFAULT
        proposals = self.store.database.read("investor", INVESTOR_DEFAULT)["data"]["proposals"]
        histories = self.store.database.read("market_history", HISTORY_DEFAULT)["data"]["entries"]
        return {"revision": record["revision"], "capabilities": experiment_capabilities(),
            "strategies": [{"definition": value, "strategy_sha256": digest(value)} for value in record["data"].get("strategy_definitions", {}).values()],
            "strategy_history": copy.deepcopy(record["data"].get("strategy_history", [])),
            "items": list(items.values()), "proposals": [{key: p[key] for key in
            ("id", "revision", "updated_at", "terms", "terms_sha256")} for p in proposals],
            "histories": [{key: h.get(key) for key in ("key", "symbol", "start", "end", "captured_at", "adjustment", "complete", "pagination_complete", "error")}
                          for h in histories.values() if self.data_jobs.timeframe(h) == "1Day"]}

    def evaluation_action(self, request):
        if request.get("action") in {"save_strategy", "preview_experiment", "run_experiment", "cancel_experiment", "repeat_experiment", "compare_experiments"}:
            return self.experiment_action(request)
        from .approval_review import read_artifact
        from .decision_journal import DEFAULT as REPORTING_DEFAULT
        from .evaluation import execute, prepare, reference
        from .investor import DEFAULT as INVESTOR_DEFAULT
        from .market_history import DEFAULT as HISTORY_DEFAULT
        store = self.store
        def save(item):
            store.database.transact({"reporting": REPORTING_DEFAULT},
                lambda records: records["reporting"].setdefault("simulations", {}).update({item["id"]: item}))
        action = request.get("action")
        if action == "preview":
            proposal = next((p for p in store.database.read("investor", INVESTOR_DEFAULT)["data"]["proposals"]
                             if p["id"] == request.get("proposal_id")), None)
            if proposal is None:
                raise ValueError("Choose an existing saved proposal")
            meta = store.database.read("market_history", HISTORY_DEFAULT)["data"]["entries"].get(request.get("history_key"))
            if not meta or self.data_jobs.timeframe(meta) != "1Day":
                raise ValueError("Choose existing saved daily history")
            history_ref = reference(meta.get("last_usable_artifact") or meta.get("artifact"))
            history = read_artifact(store.directory, history_ref)
            if history is None:
                raise ValueError("Saved history evidence is unavailable or changed")
            history["artifact"] = history_ref
            provenance = history.get("required_coverage", {}).get("provenance", {})
            calendar = read_artifact(store.directory, reference(provenance.get("calendar_reference")))
            instrument = read_artifact(store.directory, reference(provenance.get("instrument_reference")))
            if calendar is None or not isinstance(instrument, dict) or instrument.get("symbol") != proposal["terms"]["symbol"]:
                raise ValueError("Saved calendar/instrument evidence is unavailable, changed or mismatched")
            spec = prepare(proposal, history, request, calendar=calendar)
            identity = str(uuid4())
            save({"id": identity, "kind": "simulation", "status": "preview", "created_at": datetime.now(UTC).isoformat(),
                "proposal": spec["proposal"], "spec_sha256": spec["spec_sha256"],
                "preview_artifact": store._write_json_artifact(identity, "simulation-preview", spec)})
            return self.evaluations(identity)
        if action != "run" or self.simulation_closed:
            raise ValueError("Choose Preview or explicitly Run simulation")
        item = self.evaluations(request.get("id"))
        if item["status"] != "preview" or request.get("spec_sha256") != item["spec_sha256"]:
            raise ValueError("Run only the exact saved preview once; create a new preview for another scenario")
        spec = read_artifact(store.directory, item["preview_artifact"])
        if spec is None:
            raise ValueError("Saved simulation preview is unavailable or changed")
        item.pop("preview", None)
        session = self.simulation_session
        item.update(status="queued", session_id=session)
        save(item)
        def run():
            with self.maintenance:
                if self.store is not store or self.simulation_closed or session != self.simulation_session:
                    return
                item.update(status="running")
                save(item)
            try:
                result = execute(spec, self.runtime.python,
                    lambda process, active: self._simulation_process(process, active, store, session))
            except Exception as error:
                result = {"kind": "simulation", "status": "failed", "spec_sha256": spec["spec_sha256"],
                          "error": type(error).__name__ + ": " + str(error)}
            with self.maintenance:
                if self.store is not store or self.simulation_closed or session != self.simulation_session:
                    return
                item.update(status=result["status"], finished_at=datetime.now(UTC).isoformat(),
                    result_artifact=store._write_json_artifact(item["id"], "simulation-result", result))
                save(item)
        queued = copy.deepcopy(item)
        self.simulation_executor.submit(run)
        return queued

    def experiment_detail(self, item, revision):
        from .approval_review import read_artifact
        value = {**copy.deepcopy(item), "revision": revision, "evidence_errors": []}
        for name in ("preview", "result", "comparison"):
            reference = item.get(name + "_artifact")
            if reference:
                try:
                    payload = read_artifact(self.store.directory, reference)
                    if not isinstance(payload, dict) or name != "comparison" and payload.get("spec_sha256") != item["spec_sha256"]:
                        raise ValueError("Retained experiment evidence differs")
                    value[name] = {key: field for key, field in payload.items() if key != "bars"}
                except (OSError, ValueError, KeyError, TypeError):
                    value["evidence_errors"].append(name + " evidence is unavailable or changed; no newer result is substituted")
        return value

    def experiment_event(self, identity, event_id):
        from .approval_review import read_artifact
        from .decision_journal import validate_experiment_event
        item = self.evaluations(identity)
        entry = next((event for event in item.get("events", []) if event["id"] == event_id), None)
        if not entry:
            raise ValueError("Choose an exact retained event in this experiment")
        payload = read_artifact(self.store.directory, entry["artifact"])
        validate_experiment_event(item, entry, payload)
        return {"experiment_id": identity, "event": payload, "reference": entry["artifact"], "revision": item["revision"]}

    def experiment_action(self, request):
        from .approval_review import read_artifact
        from .decision_journal import DEFAULT as REPORTING
        from .evaluation import (
            prepare_experiment,
            reference,
            validate_experiment,
            validate_strategy,
        )
        from .market_history import DEFAULT as HISTORY
        if type(request.get("expected_revision")) is not int:
            raise ValueError("Reload the exact reporting revision before changing experiment records")
        store, action = self.store, request["action"]
        record = store.database.read("reporting", REPORTING)
        def update(writer):
            def current(records):
                if self.store is not store:
                    raise ValueError("Application generation changed before experiment persistence")
                writer(records["reporting"])
            return store.database.transact({"reporting": REPORTING}, current,
                expected={"reporting": request["expected_revision"]})["reporting"]
        if action == "save_strategy":
            identity = request.get("strategy_id") or str(uuid4())
            old = record["data"].get("strategy_definitions", {}).get(identity)
            if request.get("strategy_id") and (not old or request.get("strategy_revision") != old["revision"]):
                raise ValueError("Choose the exact saved strategy revision")
            definition = validate_strategy({**request.get("strategy", {}), "id": identity,
                "revision": old["revision"] + 1 if old else 1, "updated_at": datetime.now(UTC).isoformat()})
            def save_definition(saved):
                saved.setdefault("strategy_definitions", {})[identity] = definition
                saved.setdefault("strategy_history", []).append(copy.deepcopy(definition))
            update(save_definition)
            return {**self.evaluations(), "saved_strategy_id": identity}
        if action == "preview_experiment":
            strategy = record["data"].get("strategy_definitions", {}).get(request.get("strategy_id"))
            if not strategy or strategy["revision"] != request.get("strategy_revision"):
                raise ValueError("Select the exact saved reusable strategy revision")
            entries = store.database.read("market_history", HISTORY)["data"]["entries"]
            def history(key):
                meta = entries.get(key)
                if not meta or self.data_jobs.timeframe(meta) != "1Day":
                    raise ValueError("Select an actual retained daily history cache")
                ref = reference(meta.get("last_usable_artifact") or meta.get("artifact"))
                value = read_artifact(store.directory, ref)
                if not isinstance(value, dict):
                    raise ValueError("Exact retained daily history is unavailable or changed")
                return {**value, "artifact": ref}
            value = history(request.get("history_key"))
            provenance = value.get("required_coverage", {}).get("provenance", {})
            calendar = read_artifact(store.directory, reference(provenance.get("calendar_reference")))
            instrument = read_artifact(store.directory, reference(provenance.get("instrument_reference")))
            if calendar is None or not isinstance(instrument, dict) or instrument.get("symbol") != strategy["symbol"] or instrument.get("class") != "us_equity":
                raise ValueError("Exact retained calendar and equity instrument evidence are required")
            benchmark = history(request["benchmark_history_key"]) if request.get("benchmark_history_key") else None
            spec = prepare_experiment(strategy, value, request.get("experiment", {}), calendar=calendar, benchmark=benchmark, native_python=self.runtime.python)
            parent = record["data"].get("simulations", {}).get(request.get("parent_id")) if request.get("parent_id") else None
            if request.get("parent_id") and (not parent or parent.get("kind") != "experiment" or request.get("parent_spec_sha256") != parent["spec_sha256"]):
                raise ValueError("A new experiment branch must identify its exact retained parent preview")
        elif action == "repeat_experiment":
            parent = record["data"].get("simulations", {}).get(request.get("id"))
            if not parent or parent.get("kind") != "experiment" or request.get("spec_sha256") != parent["spec_sha256"]:
                raise ValueError("Repeat only an exact retained experiment as a fresh branch")
            spec = read_artifact(store.directory, parent["preview_artifact"])
            if not isinstance(spec, dict):
                raise ValueError("Exact parent preview is unavailable or changed")
            validate_experiment(spec)
        else:
            spec = None
        if spec is not None:
            validate_experiment(spec)
            identity = str(uuid4())
            item = {"id": identity, "kind": "experiment", "version": spec["version"], "status": "preview", "created_at": datetime.now(UTC).isoformat(),
                "spec_sha256": spec["spec_sha256"], "strategy_id": spec["strategy"]["id"], "strategy_revision": spec["strategy"]["revision"],
                "strategy_sha256": spec["strategy_sha256"], "events": [], "cancel_requested": False,
                "parent_id": parent["id"] if parent else None,
                "parent_spec_sha256": parent["spec_sha256"] if parent else None,
                "history_key": parent.get("history_key") if action == "repeat_experiment" else request.get("history_key"),
                "benchmark_history_key": parent.get("benchmark_history_key") if action == "repeat_experiment" else request.get("benchmark_history_key"),
                "lineage": "Fresh explicit branch; no trial, optimizer state or RNG continuation" if parent else "Explicit immutable preview",
                "preview_artifact": store._write_json_artifact(identity, "experiment-preview", spec)}
            update(lambda saved: saved.setdefault("simulations", {}).update({identity: item}))
            return self.evaluations(identity)
        if action == "compare_experiments":
            ids = request.get("ids")
            if not isinstance(ids, list) or len(ids) < 2 or len(set(ids)) != len(ids):
                raise ValueError("Choose at least two distinct retained experiments")
            members, rows = [], []
            for identity in ids:
                item = record["data"].get("simulations", {}).get(identity)
                if not item or item.get("kind") != "experiment" or not item.get("result_artifact"):
                    raise ValueError("Compare only experiments with exact retained results")
                result = read_artifact(store.directory, item["result_artifact"])
                if not result or result.get("spec_sha256") != item["spec_sha256"]:
                    raise ValueError("Exact comparison result is unavailable or changed")
                members.append({"experiment_id": identity, **{key: copy.deepcopy(item[key]) for key in ("spec_sha256", "preview_artifact", "result_artifact")}})
                rows.append({"experiment_id": identity, **{key: copy.deepcopy(result.get(key)) for key in
                    ("status", "analytical_outcome", "counts", "reasons", "comparison", "folds", "coverage")}})
            identity = str(uuid4())
            item = {"id": identity, "kind": "experiment_comparison", "status": "completed", "created_at": datetime.now(UTC).isoformat(), "members": members,
                "comparison_artifact": store._write_json_artifact(identity, "experiment-comparison", {"kind": "experiment_comparison", "members": members, "rows": rows,
                    "basis": "Side-by-side retained experiments; no aggregation, OOS re-selection or broker performance claim"})}
            update(lambda saved: saved.setdefault("simulations", {}).update({identity: item}))
            return self.evaluations(identity)
        item = record["data"].get("simulations", {}).get(request.get("id"))
        if not item or item.get("kind") != "experiment":
            raise ValueError("Choose an exact saved experiment")
        if action == "cancel_experiment":
            def cancel(saved):
                current = saved["simulations"][item["id"]]
                if current["status"] not in {"preview", "queued", "running", "cancelling"}:
                    raise ValueError("This experiment is already terminal")
                current.update(cancel_requested=True, cancel_requested_at=datetime.now(UTC).isoformat(),
                    status="cancelled" if current["status"] in {"preview", "queued"} else "cancelling")
            update(cancel)
            with self.simulation_process_lock:
                for process in self.experiment_processes.get(item["id"], set()):
                    if process.poll() is None:
                        process.terminate()
            return self.evaluations(item["id"])
        if action != "run_experiment" or self.simulation_closed or request.get("spec_sha256") != item["spec_sha256"]:
            raise ValueError("Run only the exact saved experiment preview explicitly")
        spec = read_artifact(store.directory, item["preview_artifact"])
        if not isinstance(spec, dict):
            raise ValueError("Exact experiment preview is unavailable or changed")
        validate_experiment(spec)
        from .evaluation import experiment_capabilities
        capability = experiment_capabilities()["optimizer"]
        if not capability["available"]:
            raise ValueError(capability["reason"])
        session = self.simulation_session
        def queue(saved):
            current = saved["simulations"][item["id"]]
            if current["status"] != "preview":
                raise ValueError("This immutable preview has already been claimed; use an explicit fresh repeat branch")
            current.update(status="queued", session_id=session, queued_at=datetime.now(UTC).isoformat())
        update(queue)
        self.simulation_executor.submit(self._run_experiment, store, session, item["id"], spec)
        return self.evaluations(item["id"])

    def _run_experiment(self, store, session, identity, spec):
        from .decision_journal import DEFAULT as REPORTING, validate_experiment_record
        from .evaluation import EXPERIMENT_VERSION, digest, execute_experiment
        def current():
            return self.store is store and not self.simulation_closed and session == self.simulation_session
        def update(writer):
            def write(records):
                if not current():
                    raise InterruptedError("Experiment source generation changed; no implicit continuation")
                item = records["reporting"]["simulations"][identity]
                writer(item)
                validate_experiment_record(item)
            return store.database.transact({"reporting": REPORTING}, write)
        with self.maintenance:
            if not current():
                return
            item = store.database.read("reporting", REPORTING)["data"]["simulations"][identity]
            if item["status"] != "queued":
                return
            update(lambda value: value.update(status="running", started_at=datetime.now(UTC).isoformat()))
        def cancelled():
            return not current() or store.database.read("reporting", REPORTING)["data"]["simulations"][identity]["cancel_requested"]
        def event(payload):
            if payload.get("spec_sha256") != spec["spec_sha256"]:
                raise ValueError("Experiment event belongs to a different immutable preview")
            with self.maintenance:
                def append(item):
                    event_id, ordinal = str(uuid4()), len(item["events"]) + 1
                    captured = {"experiment_id": identity, "event_id": event_id, "ordinal": ordinal,
                        "at": datetime.now(UTC).isoformat(), "payload": copy.deepcopy(payload)}
                    entry = {"id": event_id, "ordinal": ordinal, "at": captured["at"],
                        **{key: copy.deepcopy(payload.get(key)) for key in ("type", "fold_id", "trial_id", "phase", "scenario_id", "execution", "source_trial", "source_event_id")},
                        "native_spec_sha256": payload.get("native_spec_sha256") or (payload.get("result") or {}).get("spec_sha256"),
                        "payload_sha256": digest(payload),
                        "artifact": store._write_json_artifact(event_id, "experiment-event", captured)}
                    item["events"].append(entry)
                update(append)  # Commit ASK/RESULT and their bytes before optimizer/dispatch proceeds.
        def process_state(process, active):
            with self.simulation_process_lock:
                owned = self.experiment_processes.setdefault(identity, set())
                if active and current():
                    owned.add(process)
                    self.simulation_processes.add(process)
                else:
                    owned.discard(process)
                    self.simulation_processes.discard(process)
                should_stop = active and (not current() or cancelled())
                if should_stop and process.poll() is None:
                    process.terminate()
        try:
            result = execute_experiment(spec, self.runtime.python, event=event, process_state=process_state, cancelled=cancelled)
        except Exception as error:
            result = {"kind": "experiment", "version": EXPERIMENT_VERSION, "spec_sha256": spec["spec_sha256"],
                "status": "interrupted" if isinstance(error, InterruptedError) else "failed",
                "error": type(error).__name__ + ": " + str(error),
                "limitations": ["A dispatch without a durably retained result remains unknown; no automatic retry or optimizer resume"]}
        with self.maintenance:
            if not current():
                return
            def finish(item):
                if result.get("spec_sha256") != item["spec_sha256"]:
                    raise ValueError("Experiment result differs from its immutable preview")
                item.update(status=result["status"], finished_at=datetime.now(UTC).isoformat(),
                    **{key: copy.deepcopy(result.get(key)) for key in ("analytical_outcome", "counts", "reasons")},
                    result_artifact=store._write_json_artifact(identity, "experiment-result", result))
            update(finish)

    def _simulation_process(self, process, active, store, session):
        with self.simulation_process_lock:
            if active and not self.simulation_closed and self.store is store and session == self.simulation_session:
                self.simulation_processes.add(process)
            else:
                self.simulation_processes.discard(process)
                if active and process.poll() is None:
                    process.terminate()

    def _stop_simulations(self, *, closing=False):
        from .evaluation import stop_calculation_process
        with self.maintenance:
            self.simulation_closed = closing
            self._interrupt_charts("shutdown" if closing else "restore")
            with self.simulation_process_lock:
                self.simulation_session = str(uuid4())
                processes = list(self.simulation_processes)
            for process in processes:
                if process.poll() is None:
                    stop_calculation_process(process)

    def close(self):
        self._stop_simulations(closing=True)
        self.chart_executor.shutdown(wait=False, cancel_futures=True)
        self.simulation_executor.shutdown(wait=False, cancel_futures=True)
        self.attention_monitor.close()
        self.data_jobs.close()
        self.runtime.stop()
        with self.store.lock:
            self.cancelled.update(
                r["id"] for r in self.store.data["runs"] if r["status"] in {"queued", "running"}
            )
        self.executor.shutdown(wait=False, cancel_futures=True)
