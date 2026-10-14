"""The desk's application boundary: evidence, portfolio state, and paper execution."""

from __future__ import annotations

import copy
import json
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

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
            "invalid_quote": (bid_present and bid is None) or (ask_present and ask is None),
            "volume": _number(bar.get("v", bar.get("volume"))),
            "feed": "iex",
        }
        if bid_present or ask_present:
            result[symbol]["quote_timestamp"] = quote.get("t", quote.get("timestamp"))
    return result


class DeskService:
    def __init__(self, directory: Path, gateway=None, graph_factory=None):
        defaults = build_default_config()
        defaults["llm_provider"] = os.getenv("TRADINGAGENTS_LLM_PROVIDER", "chatgpt")
        settings = DeskConfig(**{k: defaults[k] for k in DeskConfig.model_fields if k in defaults})
        self.store = DeskStore(directory, settings.model_dump())
        DeskConfig.model_validate(self.store.data["config"])
        self.gateway = gateway or MaenifoldGateway(timeout=90)
        self.graph_factory = graph_factory
        self.lock = threading.RLock()
        self.execution_lock = threading.Lock()
        self.refresh_lock = threading.Lock()
        self.account_lock = threading.Lock()
        self.account_status = None
        self.chart_lock = threading.Lock()
        self.chart_cache = {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paper-analysis")
        self.cancelled = set()
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

    def refresh(self):
        with self.refresh_lock:
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
                        key: pool.submit(self.gateway.execute, "alpaca", command, args)
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
                        self._reconcile(market.get("orders", []) + market.get("open_orders", []))
                        self.store.save()
            with self.lock:
                self.market = market
        return self.state()

    def _reconcile(self, orders):
        by_client = {o.get("client_order_id"): o for o in orders if isinstance(o, dict)}
        for proposal in self.store.data["proposals"]:
            if (
                proposal.get("status") in {"unknown", "submitting"}
                and proposal.get("client_order_id") not in by_client
            ):
                try:
                    receipt = self.gateway.execute(
                        "alpaca",
                        "get_order_by_client_id",
                        {"client_order_id": proposal["client_order_id"]},
                    )
                    if isinstance(receipt, dict) and receipt.get("id"):
                        by_client[proposal["client_order_id"]] = receipt
                except Exception:
                    # A missing/failed lookup never proves that submission failed.
                    pass
            if order := by_client.get(proposal.get("client_order_id")):
                proposal.update(
                    status=order.get("status", "submitted"),
                    broker_order_id=order.get("id"),
                    filled_qty=order.get("filled_qty"),
                    filled_avg_price=order.get("filled_avg_price"),
                )

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
        ready = self.readiness(self.store.snapshot()["config"], refresh=True)
        if not ready["ready"]:
            raise ValueError(ready["message"])
        self.refresh()
        market = self._book()
        with self.execution_lock, self.store.lock:
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
            }
            self.store.data["runs"].insert(0, run)
            self.store.save()
        self.executor.submit(self._run, run["id"], market)
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

    def _run(self, run_id, market):
        from tradingagents.agents.rating import run_rating
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.portfolio import PortfolioContext, Position

        with self.store.lock:
            run = self._find_run(run_id)
            run["status"] = "running"
            config = copy.deepcopy(run["config"])
            self.store.save()
        try:
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
                    "revision": 0,
                }
                with self.store.lock:
                    run["results"].append(result)
                    self.store.save()
                started = datetime.now(UTC)
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
                        self.gateway, symbol=symbol, trade_date=run["trade_date"]
                    )
                    graph = (self.graph_factory or TradingAgentsGraph)(
                        config=graph_config, supplemental_tools=tools
                    )
                    final = {}
                    seen = set()
                    initial = graph.create_run_state(symbol, run["trade_date"], portfolio=portfolio)
                    account_context = run.get("account_context")
                    if account_context:
                        initial["portfolio_context"] = (
                            f"{account_context['description']} Captured at {account_context['captured_at']}.\n"
                            + initial.get("portfolio_context", "")
                        )
                    for messages, state in graph.stream_run(
                        initial, **graph.propagator.get_graph_args()
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
                    graph.record_decision(symbol, run["trade_date"], final)
                    rating = run_rating(final)
                    self._event(run_id, "laya", "Checking evidence with Laya", symbol)
                    laya = self.gateway.execute(
                        "laya",
                        "decide",
                        {
                            "state": {
                                "symbol": symbol,
                                "trade_date": run["trade_date"],
                                "rating": rating,
                                "reports": result["reports"],
                            },
                            "questions": {
                                "evidence_complete": {
                                    "kind": "yes_no",
                                    "instructions": "Check the actual reports for material evidence gaps.",
                                    "criteria": {
                                        "true": "The reports contain current evidence supporting this symbol's rating, with no unresolved source errors or material missing information."
                                    },
                                },
                                "decision_consistent": {
                                    "kind": "yes_no",
                                    "instructions": "Check the final recommendation against the supplied reports.",
                                    "criteria": {
                                        "true": "The final rating is consistent with the reports and is not REVIEW or an unsupported claim."
                                    },
                                },
                            },
                            "threshold": "high",
                        },
                    )
                    laya = _payload(laya)
                    answers = laya.get("answers", {})
                    gate = laya.get("contract", {}).get("grade") == "auto_execute" and all(
                        answers.get(key, {}).get("value") is True
                        for key in ("evidence_complete", "decision_consistent")
                    )
                    with self.store.lock:
                        result.update(
                            status="completed",
                            rating=rating,
                            laya={**laya, "auto_execute": gate},
                            elapsed_seconds=round((datetime.now(UTC) - started).total_seconds(), 1),
                            revision=result["revision"] + 1,
                        )
                        self.store.save()
                    self._event(
                        run_id,
                        "complete",
                        f"{rating} · Laya {laya.get('contract', {}).get('grade', 'unknown')}",
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
                self.store.data["proposals"] = proposals + self.store.data["proposals"]
                self.store.save()
                return {"proposals": copy.deepcopy(proposals)}

    def submit(self, proposal_id):
        with self.execution_lock:
            self.refresh()
            market = self._book()
            with self.store.lock:
                self._require_known_submissions()
                if self.store.data["paused"]:
                    raise ValueError("New paper orders are paused.")
                proposal = next(p for p in self.store.data["proposals"] if p["id"] == proposal_id)
                if proposal["status"] != "proposed":
                    raise ValueError(
                        "Only a proposed order can be submitted. Refresh to reconcile existing orders."
                    )
                run = self._find_run(proposal["run_id"])
                if run["trade_date"] != today() or run["config"] != self.store.data["config"]:
                    raise ValueError("This proposal is stale. Run fresh analysis.")
                if (
                    datetime.now(UTC) - datetime.fromisoformat(proposal["created_at"])
                ).total_seconds() > 900:
                    raise ValueError("This proposal is older than 15 minutes. Run fresh analysis.")
                validate_proposal(
                    proposal,
                    run["config"],
                    market["account"],
                    market["positions"],
                    market.get("open_orders", []),
                    market["quotes"],
                )
                asset = self.gateway.execute(
                    "alpaca", "get_asset", {"symbol_or_asset_id": proposal["symbol"]}
                )
                if (
                    asset.get("tradable") is not True
                    or asset.get("class", asset.get("asset_class")) != "us_equity"
                ):
                    raise ValueError("Only tradable US equities can be submitted.")
                verify_paper_configuration(self.gateway)
                proposal["status"] = "submitting"
                self.store.save()
                args = {
                    key: str(proposal[key])
                    for key in ("symbol", "side", "qty", "limit_price", "client_order_id")
                }
                args.update(type="limit", time_in_force="day", extended_hours=False)
            try:
                order = self.gateway.execute("alpaca", "place_stock_order", args)
                if not isinstance(order, dict) or not order.get("id"):
                    raise ValueError("Broker did not return an order receipt.")
                with self.store.lock:
                    proposal.update(
                        status=order.get("status", "submitted"),
                        broker_order_id=order["id"],
                        submitted_at=now(),
                    )
                    self.store.save()
                return {"order": order}
            except Exception as exc:
                with self.store.lock:
                    proposal.update(
                        status="unknown",
                        reason="Submission outcome unknown. Refresh to reconcile by client order ID; never retry blindly.",
                    )
                    self.store.save()
                raise ValueError(proposal["reason"]) from exc

    def _require_known_submissions(self):
        if any(p["status"] in {"unknown", "submitting"} for p in self.store.data["proposals"]):
            raise ValueError(
                "An earlier submission has an unknown outcome. Refresh to reconcile it before creating or submitting another order."
            )

    def cancel_order(self, order_id):
        with self.execution_lock:
            with self.store.lock:
                owned = any(
                    p.get("broker_order_id") == order_id for p in self.store.data["proposals"]
                )
            if not owned:
                raise ValueError(
                    "Only paper orders created by this workspace can be cancelled here."
                )
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
            self.gateway.execute("alpaca", "cancel_order_by_id", {"order_id": order_id})
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
