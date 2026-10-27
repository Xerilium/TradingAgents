"""The desk's application boundary: evidence, portfolio state, and paper execution."""

from __future__ import annotations

import asyncio
import copy
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
    verify_paper_configuration,
)
from tradingagents.llm_clients.api_key_env import PROVIDER_API_KEY_ENV
from tradingagents.paper.engine import plan_orders, validate_proposal

from .config import DeskConfig
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
    """Explain the existing engine policy from this run's saved configuration."""
    allocation = Decimal(str(config["allocation_pct"]))
    cap = Decimal(str(config["max_position_pct"]))
    total = len(config["universe"])
    target = min(allocation / total, cap)
    overweight = target * Decimal("0.75")
    return (
        "Paper desk execution policy (research is advisory; deterministic Python owns order sizing):\n"
        f"Maximum invested allocation {allocation}% of equity across the full configured universe of {total} stocks, "
        f"not just this run's selected stocks. Single-position cap {cap}%; cash reserve {config['reserve_pct']}%. "
        f"Buy target = min({allocation}% / {total}, {cap}%) = {target}% of equity; "
        f"Overweight target = 75% of that Buy target = {overweight}% of equity. "
        "Existing holdings reduce the shortfall. Underweight sells half the available held whole shares; "
        "Sell sells available held whole shares. Hold/REVIEW produces no order. "
        f"Per-order maximum USD {config['max_order_notional']}; limit-price buffer {config['price_buffer_bps']} basis points. "
        "Cash reserve, invested allocation, concentration, open-order reservations and order caps can reduce "
        "the policy target; buys round down to whole shares. No shorting, leverage or fractional orders; "
        "sales do not fund buys in the same batch. A separate fresh executable two-sided quote, current "
        "completed research, verified paper account and explicit manual submission are required. "
        "Your job is thesis, rating, evidence and conditional risk discussion, not order authorization. "
        "Do not invent a standard allocation, starter multiplier, percentage allocation or share quantity. "
        "State that proposal quantity is calculated from configured policy and the current broker book; "
        "research prose and advisory price levels do not override these rules. Distinguish current "
        "observations from conditions that must be checked at execution."
    )


def research_quote_context(symbol, trade_date, market):
    """Keep observed broker prices separate from historical analysis and execution."""
    if trade_date != datetime.now(ZoneInfo("America/New_York")).date().isoformat():
        return "Broker quote context: omitted for historical analysis to prevent future-data leakage."
    quote = copy.deepcopy(market.get("quotes", {}).get(symbol, {}))
    observed = datetime.now(UTC)
    def age(stamp):
        try:
            return (observed - datetime.fromisoformat(stamp.replace("Z", "+00:00"))).total_seconds()
        except (AttributeError, TypeError, ValueError):
            return None
    trade_age = age(quote.get("timestamp"))
    quote_age = age(quote.get("quote_timestamp"))
    fresh = all(value is not None and -60 <= value <= 900 for value in (trade_age, quote_age))
    usable = fresh and not quote.get("invalid_quote", True) and all(
        _number(quote.get(key)) is not None and _number(quote[key]) > 0 for key in ("price", "bid", "ask")
    )
    clock = market.get("clock") or {}
    reference_label = "current reference" if fresh else "execution-stale reference"
    try:
        clock_time = datetime.fromisoformat(clock["timestamp"].replace("Z", "+00:00"))
        next_open = datetime.fromisoformat(clock["next_open"].replace("Z", "+00:00"))
        if clock.get("is_open") is False and clock_time <= observed < next_open:
            stamps = [datetime.fromisoformat(quote[key].replace("Z", "+00:00")) for key in ("timestamp", "quote_timestamp")]
            if all(stamp <= observed + timedelta(seconds=60) and stamp.astimezone(ZoneInfo("America/New_York")).date()
                   == clock_time.astimezone(ZoneInfo("America/New_York")).date() for stamp in stamps):
                reference_label = "market-closed reference"
            else:
                reference_label = "older reference; session unverified"
    except (KeyError, AttributeError, TypeError, ValueError):
        pass
    evidence = {"symbol": symbol, "captured_at": market.get("quotes_updated_at", market.get("updated_at")),
                "evaluated_at": observed.isoformat(), "market_open": (market.get("clock") or {}).get("is_open"),
                "fresh": fresh, "fresh_for_execution": fresh, "reference_label": reference_label,
                "valid_two_sided_quote": usable, "quote": quote}
    return (
        "Broker quote context (Alpaca via Maenifold): " + json.dumps(evidence, allow_nan=False)
        + "\nThese are observed prices, not a streaming quote. State the feed, timestamps and freshness. "
        "Use reference_label to describe the observation separately from fresh_for_execution. A market-closed "
        "reference is not missing or stale merely because trading is closed; it is an observed IEX last trade, "
        "not an official closing-auction price. Older session-unverified references must not be described as "
        "the latest close. A missing, invalid or execution-stale quote is not an execution price. "
        "Ground conditional risk levels in verified technical evidence; do not invent support, resistance "
        "or a stop merely because a quote exists. Execution requires a separate fresh quote check."
    )


class DeskService:
    def __init__(self, directory: Path, gateway=None, graph_factory=None):
        defaults = build_default_config()
        defaults["llm_provider"] = os.getenv("TRADINGAGENTS_LLM_PROVIDER", "codex")
        settings = DeskConfig(**{k: defaults[k] for k in DeskConfig.model_fields if k in defaults})
        self.store = DeskStore(directory, settings.model_dump())
        if not self.store.data.get("codex_provider_migrated"):
            if self.store.data["config"].get("llm_provider") == "chatgpt":
                self.store.data["config"]["llm_provider"] = "codex"
                self.store.data["config_revision"] += 1
            self.store.data["codex_provider_migrated"] = True
            self.store.save()
        DeskConfig.model_validate(self.store.data["config"])
        self.gateway = gateway or MaenifoldGateway(timeout=90)
        self.graph_factory = graph_factory
        self.lock = threading.RLock()
        self.execution_lock = threading.Lock()
        self.refresh_lock = threading.Lock()
        self.quotes_next_refresh = 0.0
        self.quotes_refresh_failed = False
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

    def state(self, *, compact=False, run_id=None):
        with self.lock:
            market = {key: value for key, value in self.market.items() if not compact or key != "bars"}
            data = {**copy.deepcopy(market), **self.store.snapshot(compact=compact, run_id=run_id)}
        data.pop("paper_account_id", None)
        data["trading_paused"] = data["paused"]
        data["readiness"] = self.readiness(data["config"], probe=False)
        return data

    def run_detail(self, run_id, symbol=None):
        with self.store.lock:
            run = self._find_run(run_id)
            if symbol is None:
                return copy.deepcopy(run)
            result = copy.deepcopy(next(r for r in run["results"] if r["symbol"] == symbol))
            result.setdefault("revision", 0)
            return result

    def chart(self, symbol, *, force=False):
        with self.store.lock:
            permitted = set(self.store.data["config"]["universe"])
        with self.lock:
            permitted.update(p.get("symbol") for p in self.market["positions"] if isinstance(p, dict))
        if symbol not in permitted:
            raise ValueError("Choose a stock in the universe or current positions.")
        with self.chart_lock:
            cached = self.chart_cache.get(symbol)
            if not force and cached and time.monotonic() - cached[0] < 300:
                return copy.deepcopy(cached[1])
            value = _payload(self.gateway.execute("alpaca", "get_stock_bars", {
                "symbols": symbol, "days": 45, "timeframe": "1Day", "limit": 1000, "feed": "iex"
            }))
            bars = value.get("bars", value) if isinstance(value, dict) else None
            if not isinstance(bars, dict) or not isinstance(bars.get(symbol, []), list):
                raise ValueError("Chart history is not a valid broker response.")
            result = {"symbol": symbol, "bars": copy.deepcopy(bars.get(symbol, [])),
                      "updated_at": now(), "feed": "iex"}
            self.chart_cache[symbol] = (time.monotonic(), result)
            while len(self.chart_cache) > 32:
                del self.chart_cache[next(iter(self.chart_cache))]
            return copy.deepcopy(result)

    def readiness(self, config, *, refresh=False, probe=True):
        provider = config["llm_provider"].lower()
        if self.graph_factory is not None:
            return {"ready": True, "message": "Injected analysis runtime."}
        if provider == "codex":
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
        with self.execution_lock, self.store.lock:
            if any(
                run["status"] in {"queued", "running", "cancelling"}
                for run in self.store.data["runs"]
            ):
                raise ValueError("Wait for the current analysis to stop before changing settings.")
            config = DeskConfig.model_validate({**self.store.data["config"], **changes})
            self.store.data["config"] = config.model_dump()
            self.store.data["config_revision"] += 1
            for proposal in self.store.data["proposals"]:
                if proposal["status"] == "proposed":
                    proposal.update(
                        status="expired", reason="Settings changed. Run fresh analysis."
                    )
            self.store.save()
        return self.state()

    def refresh_quotes(self):
        """Single-flight quote-only refresh, shared across tabs, with a 45s deadline."""
        if not self.refresh_lock.acquire(blocking=False):
            return self.state()
        try:
            if time.monotonic() < self.quotes_next_refresh:
                if self.quotes_refresh_failed:
                    raise GatewayRateLimited(self.quotes_next_refresh - time.monotonic())
                return self.state()
            if not self._book()["connection"].get("connected"):
                raise ValueError("Connect the paper account before refreshing quotes.")
            self.quotes_next_refresh = time.monotonic() + 60
            symbols = self.store.snapshot()["config"]["universe"]

            async def fetch():
                quotes = {}
                clock = await self.gateway.aexecute("alpaca", "get_clock", {})
                for offset in range(0, len(symbols), 100):
                    raw = await self.gateway.aexecute("alpaca", "get_stock_snapshot", {
                        "symbols": ",".join(symbols[offset:offset + 100]), "feed": "iex",
                    })
                    batch = normalize_quotes(raw)
                    if any(not batch.get(symbol, {}).get("timestamp") for symbol in symbols[offset:offset + 100]):
                        raise ValueError("The quote response is incomplete; the previous snapshot is retained.")
                    quotes.update(batch)
                return quotes, _payload(clock)

            async def bounded():
                return await asyncio.wait_for(fetch(), timeout=45)

            try:
                quotes, clock = asyncio.run(bounded())
            except Exception as exc:
                self.quotes_refresh_failed = True
                self.quotes_next_refresh = time.monotonic() + max(300, getattr(exc, "retry_after", 0))
                if isinstance(exc, TimeoutError):
                    raise ValueError("Quote refresh exceeded 45 seconds. The previous snapshot is retained.") from exc
                raise
            with self.lock:
                self.quotes_refresh_failed = False
                self.market.update(quotes=quotes, clock=clock, quotes_updated_at=now())
                self.market["errors"] = [e for e in self.market["errors"] if e.get("source") != "quotes"]
            return self.state()
        finally:
            self.refresh_lock.release()

    def refresh(self):
        with self.refresh_lock:
            paper_check_started = False
            config = self.store.snapshot()["config"]
            market = {
                "connection": {
                    "connected": False,
                    "paper_verified": False,
                    "endpoint": getattr(self.gateway, "endpoint", "http://localhost:8080/mcp"),
                    "domains": [],
                    "message": "Connecting",
                },
                "account": None,
                "positions": [],
                "orders": [],
                "quotes": {},
                "history": {},
                "bars": {},
                "clock": None,
                "errors": [],
                "updated_at": now(),
            }
            try:
                for domain in ("alpaca", "maenifold.memory", "laya"):
                    self.gateway.discover(domain)
                    market["connection"]["domains"].append(domain)
                market["connection"]["connected"] = True
                paper_check_started = True
                proof = verify_paper_configuration(self.gateway)
                market["connection"]["paper_verified"] = proof.get("paper") is True
                market["connection"]["message"] = (
                    "Alpaca paper mode verified from Maenifold configuration."
                )
            except Exception as exc:
                if isinstance(exc, GatewayRateLimited):
                    raise
                market["connection"]["message"] = str(exc)
                market["errors"].append({"source": "connection", "message": str(exc)})
            if market["connection"]["connected"]:
                calls = {
                    "account": ("get_account_info", {}),
                    "positions": ("get_all_positions", {}),
                    "orders": ("get_orders", {"status": "all", "limit": 100, "direction": "desc"}),
                    "open_orders": ("get_orders", {"status": "open", "limit": 500}),
                    "history": ("get_portfolio_history", {"period": "1M", "timeframe": "1D"}),
                    "clock": ("get_clock", {}),
                }
                for offset in range(0, len(config["universe"]), 100):
                    calls[f"quotes:{offset}"] = ("get_stock_snapshot", {
                        "symbols": ",".join(config["universe"][offset:offset + 100]), "feed": "iex"
                    })
                with ThreadPoolExecutor(max_workers=4) as pool:
                    futures = {
                        key: pool.submit(copy_context().run, self.gateway.execute, "alpaca", command, args)
                        for key, (command, args) in calls.items()
                    }
                    for key, future in futures.items():
                        try:
                            value = _payload(future.result())
                            if key in {"positions", "orders", "open_orders"}:
                                value = _as_list(value, "orders" if key == "open_orders" else key)
                            elif key.startswith("quotes:"):
                                value = normalize_quotes(value)
                            elif not isinstance(value, dict):
                                raise ValueError(f"Broker {key} response is not an object.")
                            if key.startswith("quotes:"):
                                market["quotes"].update(value)
                            else:
                                market[key] = value
                        except Exception as exc:
                            if isinstance(exc, GatewayRateLimited):
                                # Keep the last verified snapshot; stop queued source work.
                                for pending in futures.values():
                                    pending.cancel()
                                raise
                            error = {"source": "quotes" if key.startswith("quotes:") else key,
                                     "message": str(exc)}
                            if key.startswith("quotes:"):
                                error["symbols"] = calls[key][1]["symbols"].split(",")
                            market["errors"].append(error)
                if len(market.get("open_orders", [])) >= 500:
                    market["errors"].append(
                        {
                            "source": "open_orders",
                            "message": "Open-order limit reached; execution blocked until the full book is available.",
                        }
                    )
                account = market["account"]
                if account and market["connection"]["paper_verified"]:
                    with self.store.lock:
                        pinned = self.store.data["paper_account_id"]
                        if pinned and account.get("id") != pinned:
                            market["connection"].update(
                                paper_verified=False,
                                message="Broker account changed. Restart with a separate data directory for the new account.",
                            )
                        elif not pinned and account.get("id"):
                            self.store.data["paper_account_id"] = account["id"]
                        if market["connection"]["paper_verified"] and account.get("id") == self.store.data["paper_account_id"]:
                            self._reconcile(market.get("orders", []) + market.get("open_orders", []), account["id"])
                        self.store.save()
            with self.lock:
                if paper_check_started:
                    self._account_observation = {
                        "paper_verified": market["connection"]["paper_verified"],
                        "account_id": (market.get("account") or {}).get("id"),
                    }
                self.market = market
                self.market["quotes_updated_at"] = market["updated_at"]
                self.quotes_next_refresh = time.monotonic() + 60
                self.quotes_refresh_failed = False
        return self.state()

    @staticmethod
    def _order_arguments(proposal):
        return {**{key: str(proposal[key]) for key in ("symbol", "side", "qty", "limit_price", "client_order_id")},
                "type": "limit", "time_in_force": "day", "extended_hours": False}

    @staticmethod
    def _order_decimal(value):
        try:
            number = Decimal(str(value)) if not isinstance(value, bool) else Decimal("NaN")
        except (InvalidOperation, ValueError):
            raise ValueError("Broker order has an invalid numeric field.") from None
        if not number.is_finite():
            raise ValueError("Broker order has an invalid numeric field.")
        return number

    def _owned_receipt(self, proposal, order):
        intent = proposal.get("submission_intent") or {}
        if (not isinstance(order, dict) or not intent.get("arguments")
                or intent.get("account_id") != self.store.data["paper_account_id"]):
            raise ValueError("Broker receipt has no matching owned account and intent.")
        expected = intent["arguments"]
        reviewed = proposal.get("reviewed") or {}
        if (expected != reviewed.get("arguments") or intent["account_id"] != reviewed.get("account_id")
                or expected.get("client_order_id") != proposal.get("client_order_id")):
            raise ValueError("Saved intent differs from the reviewed owned order.")
        if (not isinstance(order.get("id"), str) or not order["id"]
                or (proposal.get("broker_order_id") and order["id"] != proposal["broker_order_id"])
                or (order.get("account_id") is not None and order["account_id"] != intent["account_id"])
                or order.get("replaces") or order.get("replaced_by")):
            raise ValueError("Broker order identity or replacement chain does not match.")
        for field in ("client_order_id", "symbol", "side", "type", "time_in_force"):
            if order.get(field) != expected[field]:
                raise ValueError("Broker order fields do not match the saved intent.")
        if order.get("extended_hours") is not False:
            raise ValueError("Broker order session does not match the saved intent.")
        quantity, price = (self._order_decimal(order.get(key)) for key in ("qty", "limit_price"))
        if (quantity <= 0 or quantity != quantity.to_integral_value() or price <= 0
                or quantity != self._order_decimal(expected["qty"])
                or price != self._order_decimal(expected["limit_price"])):
            raise ValueError("Broker order values do not match the saved intent.")
        status = order.get("status")
        status = "canceled" if status == "cancelled" else status
        if not isinstance(status, str) or status not in OWNED_ACTIVE | OWNED_TERMINAL:
            raise ValueError("Broker order status is missing or unsupported.")
        filled = self._order_decimal(order.get("filled_qty"))
        average = self._order_decimal(order["filled_avg_price"]) if order.get("filled_avg_price") is not None else None
        if (filled < 0 or filled > quantity or (average is not None and average <= 0)
                or (filled > 0 and average is None)
                or (status == "filled" and filled != quantity)
                or (status == "partially_filled" and not 0 < filled < quantity)
                or (status in {"new", "accepted", "pending_new", "held", "rejected"} and filled != 0)):
            raise ValueError("Broker fill details are inconsistent.")
        def decimal_text(value):
            # Remove scale differences without Decimal.normalize's context rounding.
            if value == 0:
                return "0"
            text = format(value, "f")
            return text.rstrip("0").rstrip(".") if "." in text else text

        receipt = {"id": order["id"], **expected, "qty": decimal_text(quantity),
                   "limit_price": decimal_text(price), "status": status, "filled_qty": decimal_text(filled),
                   "filled_avg_price": decimal_text(average) if average is not None else None}
        previous = proposal.get("broker_receipt")
        if previous:
            old_filled = self._order_decimal(previous["filled_qty"])
            if (order["id"] != previous["id"] or filled < old_filled
                    or (previous["status"] in OWNED_TERMINAL and status != previous["status"])
                    or (filled == old_filled and average != (self._order_decimal(previous["filled_avg_price"])
                                                           if previous["filled_avg_price"] is not None else None))):
                raise ValueError("Broker receipt conflicts with prior authoritative order evidence.")
        return receipt

    @staticmethod
    def _accept_receipt(proposal, receipt):
        proposal.update(status=receipt["status"], broker_order_id=receipt["id"],
                        filled_qty=receipt["filled_qty"], filled_avg_price=receipt["filled_avg_price"],
                        broker_receipt=copy.deepcopy(receipt))
        proposal.pop("reconciliation_error", None)
        if proposal.get("cancellation", {}).get("status") in CANCEL_UNCERTAIN and receipt["status"] in OWNED_TERMINAL:
            proposal["cancellation"].update(status="resolved", resolved_at=now(), order_status=receipt["status"])

    def _reconcile(self, orders, account_id):
        if not account_id or account_id != self.store.data["paper_account_id"]:
            return
        for proposal in self.store.data["proposals"]:
            if not proposal.get("submission_intent"):
                continue
            matching = [o for o in orders if isinstance(o, dict) and o.get("client_order_id") == proposal.get("client_order_id")]
            if not matching and (proposal.get("status") in {"unknown", "submitting"}
                                 or proposal.get("cancellation", {}).get("status") in CANCEL_UNCERTAIN):
                try:
                    matching = [_payload(self.gateway.execute(
                        "alpaca",
                        "get_order_by_client_id",
                        {"client_order_id": proposal["client_order_id"]},
                    ))]
                except Exception:
                    # A missing/failed lookup never proves that submission failed.
                    continue
            if matching:
                try:
                    receipts = [self._owned_receipt(proposal, order) for order in matching]
                    if any(receipt != receipts[0] for receipt in receipts[1:]):
                        raise ValueError("Conflicting duplicate broker receipts; prior evidence retained.")
                    self._accept_receipt(proposal, receipts[0])
                except ValueError as exc:
                    proposal["reconciliation_error"] = str(exc)

    def _book(self):
        with self.lock:
            market = copy.deepcopy(self.market)
        critical = {"connection", "account", "positions", "orders", "open_orders", "quotes"}
        errors = [e for e in market["errors"] if e["source"] in critical]
        if not market["connection"]["paper_verified"] or market["account"] is None or errors:
            raise ValueError(
                "A verified paper account and complete broker data are required. Refresh the connection."
            )
        account = market["account"]
        if not account.get("id") or any(
            _number(account.get(k)) is None for k in ("cash", "equity")
        ):
            raise ValueError("Broker account identity, cash, or equity is missing or invalid.")
        if any(
            not isinstance(p, dict) or not p.get("symbol") or _number(p.get("qty")) is None
            for p in market["positions"]
        ):
            raise ValueError("Broker positions are incomplete; analysis and execution are blocked.")
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
                    "description": "Current account cash and holdings captured at run creation; "
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
                self.executor.submit(self._run, run["id"], market, request_started, queued_at)
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
                        self.gateway, domains=("alpaca", "maenifold.memory"),
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
                            status="completed",
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
        with self.execution_lock:
            self.refresh()
            market = self._book()
            with self.store.lock:
                self._require_known_submissions()
                run = self._find_run(run_id)
                if run["status"] != "completed" or run["config"] != self.store.data["config"]:
                    raise ValueError("Complete a fresh analysis with the current settings first.")
                if run["trade_date"] != today() or run["account_id"] != market["account"]["id"]:
                    raise ValueError("Analysis date or paper account changed. Run fresh analysis.")
                if any(p["run_id"] == run_id for p in self.store.data["proposals"]):
                    raise ValueError(
                        "This run already has an order plan. Start a new run for a new plan."
                    )
                proposals = plan_orders(
                    run["config"],
                    market["account"],
                    market["positions"],
                    market.get("open_orders", []),
                    market["quotes"],
                    run["results"],
                    run_id,
                )
                for p in proposals:
                    p["client_order_id"] = "ta-" + p["id"]
                    p["created_at"] = now()
                    if p["status"] == "proposed":
                        p["reviewed"] = self._review(p, run)
                self.store.data["proposals"] = proposals + self.store.data["proposals"]
                self.store.save()
                return {"proposals": copy.deepcopy(proposals)}

    def _review(self, proposal, run):
        results = [r for r in run["results"] if r.get("symbol") == proposal["symbol"]]
        if len(results) != 1 or results[0].get("status") != "completed":
            raise ValueError("Completed research is required.")
        return {"arguments": self._order_arguments(proposal), "account_id": run["account_id"],
                "run_id": run["id"], "created_at": proposal["created_at"], "trade_date": run["trade_date"],
                "proposal_fields": {key: copy.deepcopy(proposal.get(key)) for key in (
                    "id", "run_id", "symbol", "side", "qty", "limit_price", "notional", "rating", "reason", "client_order_id")},
                "config": copy.deepcopy(run["config"]),
                "evidence_sha256": hashlib.sha256(json.dumps(results[0], sort_keys=True, allow_nan=False).encode()).hexdigest()}

    @staticmethod
    def _fresh(timestamp):
        try:
            age = (datetime.now(UTC) - datetime.fromisoformat(timestamp)).total_seconds()
        except (TypeError, ValueError):
            raise ValueError("A valid freshness timestamp is required.") from None
        if not 0 <= age <= 900:
            raise ValueError("This proposal or account snapshot is older than 15 minutes. Run fresh analysis.")

    def _submission_guard(self, proposal, reviewed, market, args, *, persisted=False):
        self._require_known_submissions(proposal["id"] if persisted else None)
        if self.store.data["paused"]:
            raise ValueError("New paper orders are paused.")
        if proposal["status"] != ("submitting" if persisted else "proposed"):
            raise ValueError("Only a proposed order can be submitted. Refresh to reconcile existing orders.")
        self._fresh(proposal["created_at"])
        run = self._find_run(proposal["run_id"])
        if (not reviewed or run["status"] != "completed" or run["trade_date"] != today()
                or run["config"] != self.store.data["config"]
                or run["account_id"] != self.store.data["paper_account_id"]
                or proposal.get("reviewed") != reviewed or self._review(proposal, run) != reviewed
                or args != reviewed["arguments"]):
            raise ValueError("Reviewed proposal, research, date, account or configuration changed. Run fresh analysis.")
        current = self._book()
        self._fresh(current["updated_at"])
        if current != market or current["account"]["id"] != reviewed["account_id"]:
            raise ValueError("The verified account book changed during preparation. Refresh and review again.")
        if persisted and proposal.get("submission_intent") != {
                "account_id": reviewed["account_id"], "arguments": args}:
            raise ValueError("Saved submission intent changed.")
        validate_proposal({**proposal, "status": "proposed"}, run["config"], current["account"],
                          current["positions"], current.get("open_orders", []), current["quotes"])

    def submit(self, proposal_id):
        with self.execution_lock:
            self.refresh()
            market = self._book()
            with self.lock, self.store.lock:
                proposal = next(p for p in self.store.data["proposals"] if p["id"] == proposal_id)
                reviewed = copy.deepcopy(proposal.get("reviewed"))
                args = self._order_arguments(proposal)
                self._submission_guard(proposal, reviewed, market, args)
                asset = self.gateway.execute(
                    "alpaca", "get_asset", {"symbol_or_asset_id": proposal["symbol"]}
                )
                if (
                    asset.get("tradable") is not True
                    or asset.get("class", asset.get("asset_class")) != "us_equity"
                ):
                    raise ValueError("Only tradable US equities can be submitted.")
                verify_paper_configuration(self.gateway)
            intent_started = ready = False

            def dispatch():
                nonlocal intent_started, ready
                with self.lock, self.store.lock:
                    self._submission_guard(proposal, reviewed, market, args)
                    intent_started = True
                    proposal.update(status="submitting", submission_intent={
                        "account_id": reviewed["account_id"], "arguments": copy.deepcopy(args)})
                    self.store.save()
                    self._submission_guard(proposal, reviewed, market, args, persisted=True)
                    ready = True

            try:
                order = self.gateway.execute("alpaca", "place_stock_order", args, on_dispatch=dispatch)
                if not ready:
                    raise ValueError("Transport did not verify the dispatch boundary.")
                with self.store.lock:
                    self._accept_receipt(proposal, self._owned_receipt(proposal, _payload(order)))
                    proposal["submitted_at"] = now()
                    self.store.save()
                return {"order": order}
            except Exception as exc:
                if not intent_started:
                    raise
                with self.store.lock:
                    proposal.update(
                        status="unknown" if ready else "blocked",
                        reason=("Submission outcome unknown. Refresh to reconcile by client order ID; never retry blindly."
                                if ready else "Submission was not dispatched: local validation or intent persistence failed."),
                    )
                    self.store.save()
                raise ValueError(proposal["reason"]) from exc

    def _require_known_submissions(self, own_submission_id=None):
        if any((p["status"] in {"unknown", "submitting"} and p["id"] != own_submission_id)
               or p.get("cancellation", {}).get("status") in CANCEL_UNCERTAIN
               or p.get("reconciliation_error") for p in self.store.data["proposals"]):
            raise ValueError(
                "An earlier submission or cancellation has an unknown outcome or conflicting receipt. Refresh to reconcile it before creating or submitting another order."
            )

    def cancel_order(self, order_id):
        with self.execution_lock:
            with self.store.lock:
                owned = next((p for p in self.store.data["proposals"] if p.get("broker_order_id") == order_id), None)
            if not owned:
                raise ValueError(
                    "Only paper orders created by this workspace can be cancelled here."
                )
            if owned.get("cancellation", {}).get("status") in CANCEL_UNCERTAIN:
                raise ValueError("Cancellation outcome is pending or unknown. Refresh to reconcile; do not resend.")
            with self.lock:
                account_observation = self._account_observation
            try:
                verify_paper_configuration(self.gateway)
                account = _payload(self.gateway.execute("alpaca", "get_account_info", {}))
                if (
                    not isinstance(account, dict)
                    or not account.get("id")
                    or account["id"] != self.store.snapshot()["paper_account_id"]
                ):
                    raise ValueError("Broker account identity changed or is missing.")
            except Exception as exc:
                raise ValueError(
                    "A verified current paper account is required to cancel an order."
                ) from exc
            verified_at = now()
            order = _payload(self.gateway.execute("alpaca", "get_order_by_client_id", {
                "client_order_id": owned["client_order_id"]}))
            with self.store.lock:
                try:
                    receipt = self._owned_receipt(owned, order)
                except ValueError as exc:
                    owned["reconciliation_error"] = str(exc)
                    self.store.save()
                    raise
                self._accept_receipt(owned, receipt)
                self.store.save()
                if receipt["status"] in OWNED_TERMINAL:
                    return {"status": receipt["status"]}
                intent = copy.deepcopy(owned["submission_intent"])
                prior_cancellation = copy.deepcopy(owned.get("cancellation"))
            args = {"order_id": order_id}
            cancellation = {"status": "intent", "account_id": account["id"],
                            "client_order_id": owned["client_order_id"], "order_id": order_id,
                            "arguments": copy.deepcopy(args), "created_at": verified_at}
            intent_started = ready = False

            def guard(persisted=False):
                self._fresh(verified_at)
                with self.lock:
                    current = self._account_observation
                    if current is not account_observation and (
                            current is None or current["paper_verified"] is not True
                            or current["account_id"] != account["id"]):
                        raise ValueError("Newer account or paper-mode evidence contradicts cancellation verification.")
                if (account["id"] != self.store.data["paper_account_id"]
                        or owned.get("broker_order_id") != order_id
                        or owned.get("submission_intent") != intent
                        or owned.get("broker_receipt") != receipt
                        or owned.get("status") != receipt["status"]
                        or owned.get("reconciliation_error")
                        or args != {"order_id": order_id}
                        or owned.get("cancellation") != (cancellation if persisted else prior_cancellation)):
                    raise ValueError("Owned order or verified account changed before cancellation.")
                self._owned_receipt(owned, receipt)

            def dispatch():
                nonlocal intent_started, ready
                with self.lock, self.store.lock:
                    guard()
                    intent_started = True
                    owned["cancellation"] = copy.deepcopy(cancellation)
                    self.store.save()
                    guard(persisted=True)
                    ready = True

            try:
                self.gateway.execute("alpaca", "cancel_order_by_id", args, on_dispatch=dispatch)
                if not ready:
                    raise ValueError("Transport did not verify the cancellation dispatch boundary.")
                with self.store.lock:
                    owned["cancellation"].update(status="requested", requested_at=now())
                    self.store.save()
            except Exception as exc:
                if not intent_started:
                    raise
                with self.store.lock:
                    owned["cancellation"].update(
                        status="unknown", reason=("Cancellation outcome unknown. Refresh to reconcile; do not resend."
                                                  if ready else "Cancellation was not dispatched; local persistence or validation failed."))
                    self.store.save()
                raise ValueError(owned["cancellation"]["reason"]) from exc
        return {"status": "cancel_requested"}

    def pause(self, paused):
        if not isinstance(paused, bool):
            raise ValueError("paused must be true or false.")
        with self.execution_lock, self.store.lock:
            self.store.data["paused"] = paused
            self.store.save()
        return {"paused": paused}

    def close(self):
        with self.store.lock:
            self.cancelled.update(
                r["id"] for r in self.store.data["runs"] if r["status"] in {"queued", "running"}
            )
        self.executor.shutdown(wait=False, cancel_futures=True)
