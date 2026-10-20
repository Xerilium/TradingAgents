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
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, suppress
from contextvars import copy_context
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

from cli.stats_handler import StatsCallbackHandler
from tradingagents.agents.post_screen import SOCIAL_ADMISSION_VERSION, laya_screen
from tradingagents.dataflows.router import capture_vendor_evidence, observe_source_call
from tradingagents.default_config import build_default_config
from tradingagents.integrations.maenifold import (
    GatewayError,
    GatewayRateLimited,
    MaenifoldGateway,
    build_langchain_tools,
)
from tradingagents.llm_clients.api_key_env import PROVIDER_API_KEY_ENV

from .config import DeskConfig
from .alpaca_readonly import DEFAULT_CREDENTIALS
from .nautilus_runtime import NautilusRuntime
from .store import DeskStore

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
        self.runtime.configure(self.store.data["config"]["universe"])
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
        self.cancelled = set()
        self._account_observation = None
        self.market = {
            "connection": {
                "connected": False,
                "paper_verified": False,
                "endpoint": getattr(self.gateway, "endpoint", "http://localhost:8080/mcp"),
                "domains": [],
                "message": "Connect to load the paper account.",
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
        self.attention_monitor = AttentionMonitor(self.store.database, self.attention_context, self.maintenance)
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
        saved = self._saved_research_index()
        symbols = set(self.store.data["config"]["universe"]) | {p["symbol"] for p in runtime.get("positions", [])}
        sources = {scope: {} for scope in ("quote", "account", "research", "history", "news", "earnings", "fundamentals", "corporate_actions", "classification")}
        for symbol in symbols:
            for scope in ("history", "news", "earnings", "fundamentals", "corporate_actions", "classification"):
                sources[scope][symbol] = {"status": "missing", "observed_at": None,
                    "reason": "No saved " + scope + " observation; provider coverage is not established"}
            quote = market["quotes"].get(symbol, {})
            sources["quote"][symbol] = {"status": "available" if quote.get("price") is not None and market["connection"]["connected"] else "unavailable",
                "price": quote.get("price"), "change_pct": quote.get("change_pct"), "observed_at": quote.get("timestamp"),
                "reason": quote.get("error"), "checked_at": quote.get("checked_at")}
            result = saved.get(symbol)
            sources["research"][symbol] = {"status": "available" if result and result.get("status") == "completed" else "missing",
                "observed_at": result.get("observed_at") if result else None, "run_id": result.get("run_id") if result else None,
                "time_basis": result.get("time_basis") if result else None, "trade_date": result.get("trade_date") if result else None,
                "revision": result.get("revision") if result else None, "reason": (None if result.get("observed_at") else
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
                "symbols": symbols, "proposals": {p["id"]: p for p in proposals}}

    def attention(self):
        from .attention import DEFAULT, OBSERVATIONS
        from .investor import digest
        record = self.store.database.read("attention", DEFAULT)
        bindings = self.review_source_bindings()
        for review in record["data"]["reviews"].values():
            current = bindings.get(review["symbol"], {})
            prior = review.get("source_bindings")
            changed = [scope for scope in ("history", "corporate_actions")
                       if prior is None or digest(prior.get(scope)) != digest(current.get(scope))]
            review["review_required"] = bool(changed)
            review["review_reasons"] = [scope + " source revision changed or was not bound when reviewed" for scope in changed]
            review["current_source_bindings"] = current
        return {**record, "observations": self.store.database.read("attention_observations", OBSERVATIONS)}

    def review_source_bindings(self):
        sources = self.data_jobs.sources()
        symbols = set(sources.get("history", {})) | set(sources.get("corporate_actions", {}))
        return {symbol: {scope: {key: value for key, value in sources.get(scope, {}).get(symbol, {}).items()
                    if key in {"input_identity", "artifact", "required_coverage", "effective_dates", "content_sha256"}}
                for scope in ("history", "corporate_actions")} for symbol in symbols}

    def save_attention(self, request):
        from .attention import DEFAULT, OBSERVATIONS, change
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
            self.store.database.update("attention", request.get("expected_revision"),
                lambda saved: change(saved, request, context["symbols"], context["research"], self.review_source_bindings()), DEFAULT)
        return self.attention()

    def reconcile_commands(self):
        from .admission import DEFAULT as COMMAND_DEFAULT, TERMINAL
        self.runtime.request("refresh")
        errors = {}
        for identity, command in self.store.database.read("commands", COMMAND_DEFAULT)["data"]["commands"].items():
            if command["state"] in {"not_sent", "admitted_not_dispatched"} or command["state"] in TERMINAL and not command.get("native_pending_commitment"):
                continue
            try:
                self.runtime.request("reconcile_identity", command_id=identity)
            except ValueError as exc:
                errors[identity] = str(exc)
        return {**self.admission.reconcile(), "identity_errors": errors}

    def state(self, *, compact=False, run_id=None):
        with self.lock:
            market = self._runtime_market()
            data = {**copy.deepcopy(market), **self.store.snapshot(compact=compact, run_id=run_id)}
        data.pop("paper_account_id", None)
        data["workspace"] = self.workspace()
        data["saved_research"] = self._saved_research_index()
        data["investor"] = self.investor()
        data["health"] = self.health()
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
            for r in self.store.data["runs"] + self.history.get("runs", [])
            if r.get("portfolio_evidence", {}).get("context")]
        for r in self.store.data["runs"] + self.history.get("runs", []):
            for result in r.get("results", []):
                data.setdefault("research", {}).setdefault(result["symbol"], {
                    "run_id": r["id"], **{key: result.get(key) for key in
                        ("symbol", "status", "rating", "trade_date", "revision")}})
        current_ids = {run["id"] for run in data["runs"]}
        for saved in self.history.get("runs", []):
            if saved["id"] in current_ids:
                continue
            summary = {key: copy.deepcopy(saved.get(key)) for key in (
                "id", "created_at", "completed_at", "trade_date", "symbols", "status", "config", "account_id")}
            results = saved.get("results", [])
            summary.update(history_source="Saved .paper-desk history (read-only)",
                results=[self.store.result_summary(r) for r in results],
                events=copy.deepcopy(saved.get("events", [])[-40:]), event_count=len(saved.get("events", [])),
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

    def _saved_research_index(self):
        saved = {}
        current = self.store.snapshot()["runs"]
        for run in sorted(current + self.history.get("runs", []), key=lambda item: item.get("created_at") or "", reverse=True):
            for result in run.get("results", []):
                if result.get("status") == "completed":
                    completion = next((e.get("time") for e in reversed(run.get("events", []))
                                       if e.get("kind") == "complete" and e.get("symbol") == result["symbol"]), None)
                    observed = result.get("completed_at") or completion or run.get("completed_at")
                    basis = "stock_completion" if result.get("completed_at") or completion else "run_completion" if observed else "analysis_date_only"
                    saved.setdefault(result["symbol"], {"run_id": run["id"], "observed_at": observed, "time_basis": basis,
                        **{key: result.get(key) for key in ("symbol", "status", "rating", "trade_date", "revision")}})
        return saved

    def workspace(self):
        from .workspace import DEFAULT
        return self.store.database.read("workspace", DEFAULT)

    def save_workspace(self, request):
        from .workspace import DEFAULT, change
        return self.store.database.update("workspace", request.get("expected_revision"),
                                          lambda saved: change(saved, request), DEFAULT)

    def investor(self):
        from .investor import DEFAULT, RULES, RULE_PARAMETERS, instruments, broker_action_order, order_version
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
                broker_actions[order["id"]] = {"supported": True, "order_version": order_version(order)}
            except (ValueError, KeyError, TypeError) as exc:
                broker_actions[order.get("id")] = {"supported": False, "reason": str(exc)}
        return {**record, "rule_labels": RULES, "rule_parameters": RULE_PARAMETERS, "approval_records_enabled": self.admission.review_enabled,
                "command_admission_enabled": self.admission.admission_enabled, "broker_transport_enabled": self.admission.execution_enabled,
                "current_checks": checks, "broker_order_actions": broker_actions,
                "instruments": instruments(runtime, self.store.data["config"]["universe"])}

    def health(self):
        import sqlite3
        runtime = self.runtime.state()
        try:
            journal = self.store.database.read("journal")
            store = {"status": "available", "schema": self.store.database.VERSION,
                     "journal_revision": journal["revision"], "sqlite_version": sqlite3.sqlite_version}
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

    def start_native(self):
        return self.runtime.start()

    def recovery_action(self, request):
        from .recovery import backup, restore, stage
        if any(not future.done() for future in self.research_futures | self.data_jobs.futures):
            raise ValueError("Research/data writers are active. Wait for them to finish or stop their jobs before backup/restore")
        if request.get("action") == "preview":
            return stage(self, request.get("archive"))
        if request.get("action") == "backup":
            return backup(self)
        with self.store.lock:
            if request.get("action") == "restore":
                return restore(self, request.get("token"), request.get("confirmation"))
        raise ValueError("Choose backup, preview or restore")

    def backup_download(self, identity):
        from uuid import UUID
        if str(UUID(identity)) != identity:
            raise ValueError("Invalid backup identity")
        return (self.application_root / "recovery" / "backups" / (identity + ".zip")).read_bytes()

    def reporting(self, *, compact=False):
        from .decision_journal import DEFAULT, decisions
        from .investor import DEFAULT as INVESTOR_DEFAULT
        record = self.store.database.read("reporting", DEFAULT)
        if compact:
            return {"revision": record["revision"], "collection_count": len(record["data"]["collections"]),
                    "benchmark": record["data"]["benchmark"], "horizon_days": record["data"]["horizon_days"]}
        investor = self.store.database.read("investor", INVESTOR_DEFAULT)["data"]
        return {**record, "decisions": decisions(investor, self.store.snapshot(), self.history, self.admission.snapshot()["data"])}

    def reporting_detail(self, identity, receipt=None):
        record = self.reporting()
        collection = next(c for c in record["data"]["collections"] if c["id"] == identity)
        def read(reference):
            from .recovery import references
            relative, expected = next(references(reference))
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
                        and entry["adjustment"] == "split"]
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

    def save_investor(self, request):
        from .investor import DEFAULT, save
        from .admission import DEFAULT as COMMAND_DEFAULT, invalidate
        if request.get("action") == "review":
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
                           universe, self._proposal_research)
            proposal = next(p for p in updated["proposals"] if p["id"] == request.get("id")) if request.get("id") else updated["proposals"][0]
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
        update(lambda records: save(records["investor"], request, runtime, universe, self._proposal_research))
        return self.investor()

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
        matching = [relative for relative, digest in references(command) if digest == checksum]
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
        if action == "block":
            self.admission.control(request.get("blocked"), actor=actor, reason=reason, expected=expected)
        elif self.browse_only:
            raise PermissionError("Browse-only mode does not permit command authorizations or dispatch")
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
            self.admission.approve(proposal["id"], actor=actor, reason=reason or proposal["terms"]["rationale"],
                constraints=self.review_constraints(request.get("constraints")), proposal_revision=request.get("proposal_revision"),
                policy_revision=request.get("policy_revision"), evaluation_binding_sha256=request.get("evaluation_binding_sha256"),
                expected=expected)
        elif request.get("action") == "revoke":
            self.admission.revoke(request["approval_id"], actor=actor, reason=reason, expected=expected)
        else:
            raise ValueError("Choose an explicit approval, revocation or admission")
        return {"investor": self.investor(), "commands": self.admission.snapshot()}

    def run_detail(self, run_id, symbol=None):
        with self.store.lock:
            run = next((r for r in self.store.data["runs"] if r["id"] == run_id), None)
            if run is None:
                run = next(r for r in self.history.get("runs", []) if r["id"] == run_id)
            if symbol is None:
                return copy.deepcopy(run)
            result = copy.deepcopy(next(r for r in run["results"] if r["symbol"] == symbol))
            result.setdefault("revision", 0)
            return result

    def chart(self, symbol, *, force=False, run_id=None):
        from .market_evidence import recorded_market
        all_runs = self.store.data["runs"] + self.history.get("runs", [])
        run = next((r for r in all_runs if symbol in r.get("symbols", []) and
                    (r["id"] == run_id if run_id else r["status"] == "completed")), None)
        if run is None:
            raise ValueError("Select an existing research run containing this stock.")
        root = self.store.directory if any(r["id"] == run["id"] for r in self.store.data["runs"]) else self.history_directory
        key = (run["id"], symbol)
        with self.chart_lock:
            if not force and key in self.chart_cache:
                return copy.deepcopy(self.chart_cache[key])
            result = recorded_market(root, run, symbol)
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

    def save_config(self, changes):
        if self.browse_only and set(changes) - {"name", "universe"}:
            raise ValueError("Read-only review allows only index name and symbols to change")
        with self.execution_lock, self.store.lock:
            if any(
                run["status"] in {"queued", "running", "cancelling"}
                for run in self.store.data["runs"]
            ):
                raise ValueError("Wait for the current analysis to stop before changing settings.")
            config = DeskConfig.model_validate({**self.store.data["config"], **changes})
            self.store.data["config"] = config.model_dump()
            self.store.data["config_revision"] += 1
            self.store.save()
            self.runtime.configure(config.universe)
        return self.state()

    def _runtime_market(self):
        runtime = self.runtime.state()
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
                "paper_verified": available and urlsplit(runtime.get("endpoint") or "").hostname == "paper-api.alpaca.markets",
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
        self.runtime.request("refresh")
        return self.state()

    def refresh(self):
        # Connecting is explicit; page loads and research never start an execution strategy.
        self.runtime.start()
        return self.state()

    def _book(self):
        market = self._runtime_market()
        if not market["connection"]["connected"] or not market["account"]:
            raise ValueError("A connected, current Nautilus account is required. Start Nautilus and wait for connection.")
        return market

    def start_run(self, symbols=None, expected_revision=None, analysis_date=None):
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
                result = self._start_run(symbols, expected_revision, analysis_date, request, request_started)
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

    def _start_run(self, symbols, expected_revision, analysis_date, request, request_started):
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
            market = self._book()
        with self._request_stage(request, "admission"), self.execution_lock, self.store.lock:
            if expected_revision is not None and (
                isinstance(expected_revision, bool) or not isinstance(expected_revision, int)
                or expected_revision != self.store.data["config_revision"]
            ):
                raise ValueError("Workspace settings changed. Refresh and review the research selection again.")
            config = copy.deepcopy(self.store.data["config"])
            symbols = symbols or config["universe"]
            if (
                not isinstance(symbols, list)
                or not symbols
                or any(s not in config["universe"] for s in symbols)
            ):
                raise ValueError("Choose symbols from the configured universe.")
            symbols = list(dict.fromkeys(symbols))
            if any(
                r["status"] in {"queued", "running", "cancelling"} for r in self.store.data["runs"]
            ):
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
        self.store.save()

    def _evidence_recorder(self, owner_id):
        def record(receipt, output):
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

    def _run_with_evidence(self, run_id, market, request_started, queued_at):
        stats = StatsCallbackHandler()
        with self.store.lock:
            run = self._find_run(run_id)
            run["status"] = "running"
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
            for symbol in run["symbols"]:
                if run_id in self.cancelled:
                    break
                self._event(run_id, "symbol", "Analysis started", symbol)
                result = {
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
                    run["results"].append(result)
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
                        checkpoint_enabled=False,
                    )
                    tools = build_langchain_tools(
                        self.gateway, domains=("maenifold.memory",),
                        symbol=symbol, trade_date=run["trade_date"]
                    )
                    social_budget = {"remaining": 30, "deadline": None}
                    def screen_factory(ticker, source, current=result, budget=social_budget, *, instrument_context=""):
                        def record(evidence):
                            with self.store.lock:
                                social = current["social_sentiment"]
                                social["sources"][source] = evidence
                                statuses = [s["status"] for s in social["sources"].values()]
                                social["status"] = ("completed" if all(s in {"completed", "empty"} for s in statuses)
                                                    else "unavailable" if all(s in {"unavailable", "not_screened"} for s in statuses) else "partial")
                                current["revision"] += 1
                                self.store.save()
                        with self.store.lock:
                            current["social_sentiment"]["sources"][source] = {
                                "admission_version": SOCIAL_ADMISSION_VERSION,
                                "status": "not_screened", "source": source, "counts": {}, "posts": [],
                                "note": "No eligible posts supplied by the source; inspect the sentiment report for source availability."}
                            current["social_sentiment"]["status"] = "partial"
                            self.store.save()
                        company = re.search(r"(?:Company|Name): ([^\n;]+)", instrument_context)
                        instrument = f"{company.group(1)} ({ticker})" if company else ticker
                        return laya_screen(ticker, self.gateway, budget=budget, instrument=instrument,
                                           source=source, on_evidence=record,
                                           cancelled=lambda: run_id in self.cancelled)
                    graph = (self.graph_factory or TradingAgentsGraph)(
                        selected_analysts=config.get("selected_analysts", ["market", "social", "news", "fundamentals"]),
                        config=graph_config, supplemental_tools=tools, callbacks=[stats],
                        social_screen_factory=screen_factory,
                    )
                    final = {}
                    seen = set()
                    memory_seen = None
                    initial = graph.create_run_state(symbol, run["trade_date"], portfolio=portfolio)
                    initial["desk_execution_policy"] = desk_execution_policy(config)
                    quote_context = research_quote_context(symbol, run["trade_date"], market)
                    initial["instrument_context"] = initial.get("instrument_context", f"Instrument: {symbol}.") + "\n\n" + quote_context
                    with self.store.lock:
                        result["quote_context"] = quote_context
                        result["desk_execution_policy"] = initial["desk_execution_policy"]
                        self.store.save()
                    self.store.record_portfolio_context(run_id, {
                        "schema_version": 1,
                        "run_id": run_id,
                        "analysis_date": run["trade_date"],
                        "account_id": market["account"]["id"],
                        "account_context": copy.deepcopy(run["account_context"]),
                        "portfolio": portfolio.model_dump(mode="json"),
                    })
                    account_context = run.get("account_context")
                    if account_context:
                        initial["portfolio_context"] = (
                            f"{account_context['description']} Captured at {account_context['captured_at']}.\n"
                            + initial.get("portfolio_context", "")
                        )
                    graph_args = graph.propagator.get_graph_args()
                    graph_args["config"] = {**graph_args.get("config", {}), "callbacks": [stats]}
                    next_stage("analysis")
                    for messages, state in graph.stream_run(
                        initial, **graph_args
                    ):
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
                    graph.record_decision(symbol, run["trade_date"], final)
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
                        f"{rating} · Research completed",
                        symbol,
                    )
                except InterruptedError as exc:
                    with self.store.lock:
                        result.update(status="cancelled", error=str(exc))
                        self.store.save()
                    break
                except Exception as exc:
                    with self.store.lock:
                        result.update(status="failed", error=str(exc)[:600])
                        self.store.save()
                    self._event(run_id, "error", str(exc)[:600], symbol)
                    if isinstance(exc, GatewayRateLimited):
                        # Stop the sweep. Keep completed evidence and leave later stocks unstarted.
                        with self.store.lock:
                            run["error"] = str(exc)
                            run["retry_at"] = (datetime.now(UTC) + timedelta(seconds=exc.retry_after)).isoformat()
                        break
                finally:
                    next_stage(None)
                    with self.store.lock:
                        result["elapsed_seconds"] = round((datetime.now(UTC) - started).total_seconds(), 3)
                        run["measurements"]["callbacks"] = stats.get_measurements()
                        self.store.save()
            with self.store.lock:
                run["status"] = (
                    "cancelled"
                    if run_id in self.cancelled
                    else (
                        "completed"
                        if all(r["status"] == "completed" for r in run["results"])
                        else "failed"
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
            run["status"] = "cancelling"
            self.store.save()
        return {
            "status": "cancelling",
            "message": "Stops at the next agent step; in-flight calls finish first.",
        }

    def propose(self, run_id):
        raise ValueError("Order creation unavailable: no Nautilus sizing policy is configured.")

    def close(self):
        self.attention_monitor.close()
        self.data_jobs.close()
        self.runtime.stop()
        with self.store.lock:
            self.cancelled.update(
                r["id"] for r in self.store.data["runs"] if r["status"] in {"queued", "running"}
            )
        self.executor.shutdown(wait=False, cancel_futures=True)
