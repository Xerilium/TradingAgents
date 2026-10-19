"""Nautilus subprocess over durable user authority; stdout is JSONL, diagnostics go to stderr."""

import asyncio
import hashlib
import json
import os
import sys
import threading
import time
import traceback
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from uuid import uuid4


def main():
    # Keep native node logging out of the protocol pipe.
    output = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    # Load the thin adapter package without the research framework's dotenv/LLM initialization.
    adapter_spec = spec_from_file_location("_tradingagents_native_adapter", Path(__file__).with_name("__init__.py"),
                                           submodule_search_locations=[str(Path(__file__).parent)])
    adapter_module = module_from_spec(adapter_spec)
    sys.modules[adapter_spec.name] = adapter_module
    adapter_spec.loader.exec_module(adapter_module)
    from _tradingagents_native_adapter.execution_lifecycle import ExecutionLifecycle
    from _tradingagents_native_adapter.native_recovery import collect_history
    from alpaca_readonly import read, trading_endpoint
    from _tradingagents_native_adapter.alpaca_reports import fill_report, order_report, position_report, timestamp, execution_id, native_quantities, market_replacement_binding
    from account_projection import reconcile, history_scope
    from nautilus_trader import __version__, __file__ as native_package_file
    from _tradingagents_native_adapter.native_types import (
        AccountBalance, AccountId, AccountType, Currency, Equity, InstrumentId,
        Money, OmsType, OrderSide, Price, Quantity, QuoteTick, Symbol, TimeInForce, Venue,
        AggressorSide, TradeId, TradeTick, ExecutionMassStatus, ClientId,
        PositionSide, PositionStatusReport, ClientOrderId, VenueOrderId, native_dict, enum_name,
        OrderFilled, retained_fill_report, require_fill_match, native_order_account, native_order_client_matches,
    )
    from _tradingagents_native_adapter.nautilus_v1 import (DataClientFactory, ExecutionClient,
        ExecutionClientFactory, MarketDataClient, Strategy, build_node)

    manifest = json.loads((Path(__file__).parents[2] / "docs/nautilus-v1-runtime-manifest.json").read_text(encoding="utf-8"))
    if __version__ != manifest["nautilus_version"]:
        raise ValueError("Native version differs from the reviewed runtime contract")
    for relative, expected in manifest["installed_files"].items():
        with (Path(native_package_file).parent / relative).open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != expected["sha256"]:
                raise ValueError("Native files differ from the reviewed official wheel: " + relative)
    native_epoch = str(uuid4())  # One identity per actual worker/native-node process, not per web adapter.
    venue, usd = Venue("ALPACA"), Currency.from_str("USD")
    startup = json.loads(sys.stdin.readline())
    endpoint = trading_endpoint(sys.argv[1])

    def diagnose(exc):
        message = str(exc)
        for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                secret = line.split("=", 1)[1].strip().strip("\"'")
                if secret:
                    message = message.replace(secret, "[redacted]")
        print(type(exc).__name__ + ": " + message[:1200], file=sys.stderr, flush=True)
        traceback.print_tb(exc.__traceback__, limit=8, file=sys.stderr)
    persistence_status = {"configured": False, "state": "in_memory", "backing": "memory",
                          "restore_ready": False, "durable_writes_confirmed": False,
                          "limitation": "Official native cache is in memory; persisted native execution proof is unavailable."}
    output.write(json.dumps({"status": "starting", "read_only": False, "endpoint": endpoint, "persistence": persistence_status}) + "\n")
    desired = list(startup["symbols"])
    authority_database = startup.get("authority_database")
    instrument_id = lambda symbol: InstrumentId.from_str(f"{symbol}.ALPACA")
    initial_account = read("/v2/account", sys.argv[1])
    account_id = AccountId("ALPACA-" + initial_account["id"])
    observed = {"account": None, "account_at": None, "error": None, "market_open": None,
                "positions": [], "orders": [], "fills": [], "gaps": [], "lookback_start": None}
    clients = {}
    strategy_holder = [None]

    def retain_observation():
        receipt = Path("account-observation.json")
        temporary = receipt.with_suffix(".tmp")
        temporary.write_text(json.dumps(observed, allow_nan=False), encoding="utf-8")
        temporary.replace(receipt)

    async def get(path, *, data=False):
        # No method/body input exists at this boundary. Never import the proof strategy.
        try:
            return await asyncio.to_thread(read, path, sys.argv[1], data=data)
        except Exception as exc:
            if data:
                raise
            reason = exc.reason if isinstance(exc, URLError) else exc
            observed["error"] = (
                "Cannot reach Alpaca: the connection was refused. Check the configured proxy/network; current balances are unavailable."
                if isinstance(reason, ConnectionRefusedError) else
                f"Cannot load Alpaca paper data ({type(reason).__name__}). Current balances are unavailable.")
            raise RuntimeError(observed["error"]) from None

    class Data(MarketDataClient):
        async def _connect(self):
            self.observations = {}
            self.refresh_lock, self.wake = asyncio.Lock(), asyncio.Event()
            self.last_attempt, self.retry_at, self.last_symbols = 0, 0, ()
            self.checked_at = None
            self.asset_metadata = {a["symbol"]: a for a in await get("/v2/assets?status=active&asset_class=us_equity")}
            self.assets = set(self.asset_metadata)
            self.register(desired)
            self.task = self.create_task(self.poll(), "read-only-index-prices")

        def register(self, symbols):
            stamp = self.clock.timestamp_ns()
            for symbol in symbols:
                if symbol in self.assets and self.cache.instrument(instrument_id(symbol)) is None:
                    self._handle_instrument(Equity(instrument_id(symbol), Symbol(symbol), usd, 2,
                        Price.from_str("0.01"), stamp, stamp, lot_size=Quantity.from_str("1")))

        async def _subscribe_quotes(self, command):
            self.wake.set()

        async def _subscribe_trades(self, command):
            pass  # Quotes and trades share the same batched snapshot request.

        def market_symbols(self):
            return tuple(dict.fromkeys(desired + [p['symbol'] for p in observed['positions'] + observed['orders'] if p.get('asset_class') == 'us_equity' and p['symbol'] in self.assets]))

        async def refresh(self):
            async with self.refresh_lock:
                symbols, now = self.market_symbols(), asyncio.get_running_loop().time()
                self.register(symbols)
                if now < self.retry_at or (symbols == self.last_symbols and now - self.last_attempt < 5):
                    return
                self.last_attempt, self.last_symbols = now, symbols
                self.observations = {s: self.observations.get(s, {"error": "Awaiting latest IEX snapshot"}) for s in symbols}
                eligible = [s for s in symbols if s in self.assets]
                for symbol in set(symbols) - self.assets:
                    self.observations[symbol] = {"error": "No active US equity instrument in Alpaca"}
                for offset in range(0, len(eligible), 100):
                    batch = eligible[offset:offset + 100]
                    try:
                        snapshots = await get("/v2/stocks/snapshots?" + urlencode(
                            {"symbols": ",".join(batch), "feed": "iex"}), data=True)
                    except Exception as exc:
                        message = f"IEX snapshot unavailable ({type(exc).__name__})"
                        if isinstance(exc, HTTPError) and exc.code == 429:
                            try:
                                delay = max(60, float(exc.headers.get("Retry-After", "60")),
                                    float(exc.headers.get("X-RateLimit-Reset", "0")) - datetime.now(UTC).timestamp())
                            except ValueError:
                                delay = 60
                            self.retry_at = asyncio.get_running_loop().time() + delay
                            message = "IEX rate limit reached; updates paused until the retry window"
                        if self.market_symbols() != symbols:
                            return
                        for symbol in eligible[offset:]:
                            self.observations[symbol] = {"error": message}
                        break
                    if self.market_symbols() != symbols:
                        return  # Discard responses for a superseded index.
                    for symbol in batch:
                        result = self.observations[symbol] = {}
                        snapshot = snapshots.get(symbol) or {}
                        for key in ("latestTrade", "latestQuote"):
                            item = snapshot.get(key) or {}
                            try:
                                stamp = int(datetime.fromisoformat(item["t"].replace("Z", "+00:00")).timestamp() * 1e9)
                                instrument = instrument_id(symbol)
                                if key == "latestTrade" and item["p"] > 0 and item["s"] > 0:
                                    tick = TradeTick(instrument, Price.from_str(str(item["p"])),
                                        Quantity.from_str(str(item["s"])), AggressorSide.NO_AGGRESSOR,
                                        TradeId(str(item["i"])), stamp, self.clock.timestamp_ns())
                                elif key == "latestQuote" and 0 < item["bp"] <= item["ap"]:
                                    tick = QuoteTick(instrument, Price.from_str(str(item["bp"])),
                                        Price.from_str(str(item["ap"])), Quantity.from_str(str(item["bs"])),
                                        Quantity.from_str(str(item["as"])), stamp, self.clock.timestamp_ns())
                                else:
                                    continue
                                self._handle_data(tick)
                                result[key] = True
                            except (KeyError, ValueError, TypeError):
                                continue
                        result["previous_close"] = (snapshot.get("prevDailyBar") or {}).get("c")
                        if not result.get("latestTrade") and not result.get("latestQuote"):
                            result["error"] = "Latest IEX trade and valid bid/ask unavailable"
                    self.checked_at = datetime.now(UTC).isoformat()

        async def poll(self):
            while True:
                self.wake.clear()
                await self.refresh()
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=30)
                except TimeoutError:
                    pass

        async def _disconnect(self):
            task = getattr(self, "task", None)
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

        async def _unsubscribe_quotes(self, command):
            pass  # A removed symbol must not stop the remaining index's shared poller.

        async def _unsubscribe_trades(self, command):
            pass

    def order_account_binding(order):
        client = clients.get("execution")
        actual = native_order_account(order, client) if order is not None and client is not None else None
        source = (observed.get("account") or {}).get("id")
        if not actual or actual != "ALPACA-" + str(source):
            return None
        return {"account_id": actual, "client_id": str(client.client_id), "venue": str(client.venue),
                "source": "native_order_events_and_execution_client",
                "event_ids": [str(event.id) for event in order.events if getattr(event, "account_id", None) is not None]}

    def order_snapshot(order):
        event = order.events[-1]
        pending = type(event).__name__ in {"OrderPendingUpdate", "OrderPendingCancel"}
        indexed = clients["execution"].cache.venue_order_id(order.client_order_id)
        return {**native_dict(order), "account_binding": order_account_binding(order),
                "venue_order_id_binding": {"venue_order_id": str(indexed), "client_order_id": str(order.client_order_id),
                    "source": "native_cache_venue_order_index"} if indexed is not None else None,
                "pending_event": {"type": type(event).__name__, "id": str(event.id), "ts_event": event.ts_event,
                                  "prior_ids": [str(item.id) for item in order.events[:-1]]} if pending else None}

    def runtime_snapshot(cache, *, include_market_data=True):
        account = cache.account(account_id)
        native_positions = [native_dict(p) for p in cache.positions_open()]
        native_orders = [order_snapshot(o) for o in cache.orders_open()]
        native_cash = str(account.balance_total(usd).as_decimal()) if account is not None else None
        execution = clients.get("execution")
        commands = execution.lifecycle.authority().database.read("commands", {})["data"].get("commands", {}) if execution and hasattr(execution, "lifecycle") else {}
        reconciliation = reconcile(observed, native_positions, native_orders, native_cash, commands=commands, native_epoch=native_epoch)
        parents = {row["id"]: row for row in observed.get("order_history", [])}
        fill_observations = []
        for fill in observed["fills"]:
            parent = parents.get(fill.get("order_id"), {})
            history = observed.get("recovery_history") or {}
            if (fill.get("id") in history.get("excluded_closed_fill_ids", [])
                    or parent.get("id") in history.get("excluded_closed_order_ids", [])):
                fill_observations.append({**fill, "native_application": "historical_source_only"})
                continue
            try:
                order = cache.order(ClientOrderId(parent.get("native_client_order_id") or parent["client_order_id"])) if parent.get("client_order_id") else None
                proven = (order_account_binding(order) is not None and ExecutionLifecycle.native_applied(order, "fill",
                    {"execution_id": fill["id"], "qty": fill["qty"], "price": fill["price"], "commission": fill.get("commission") if fill.get("commission") is not None else fill.get("native_fee", {}).get("amount")},
                    parent, None, fill["transaction_time"]))
            except (ValueError, KeyError, TypeError, ArithmeticError):
                proven = False
            fill_observations.append({**fill, "native_application": "proven_in_current_process" if proven else "unresolved"})
            if not proven:
                reconciliation["gaps"].append("Fill " + str(fill.get("id")) + ": exact current native order/fill application is unproven; source retained")
                reconciliation["status"] = "incomplete"
        reconciliation["fills"] = fill_observations
        data = clients.get("data")
        prices = {}
        for symbol in (dict.fromkeys(desired + [p["symbol"] for p in observed["positions"] + observed["orders"]]) if include_market_data else ()):
            observation = getattr(data, "observations", {}).get(symbol, {})
            instrument = cache.instrument(instrument_id(symbol))
            quote = cache.quote_tick(instrument_id(symbol))
            trade = cache.trade_tick(instrument_id(symbol))
            prices[symbol] = {**observation,
                "instrument": native_dict(instrument) if instrument else None,
                "trade_supported": getattr(data, "asset_metadata", {}).get(symbol, {}).get("tradable") is True,
                "quote": native_dict(quote) if quote and observation.get("latestQuote") else None,
                "trade": native_dict(trade) if trade and observation.get("latestTrade") else None}
        connected = len(clients) == 2 and all(c.is_connected for c in clients.values()) and observed.get("account") is not None
        return {"status": "error" if observed["error"] else "connected" if connected else "starting",
            "version": __version__, "native_epoch": native_epoch, "worker_pid": os.getpid(), "persistence": dict(persistence_status),
            "broker_observation": observed.get("broker_observation", {}),
            "native_import_gap": observed.get("native_import_gap"),
            "native_contract": {"source_commit": manifest["source_commit"], "wheel_sha256": manifest["official_wheel"]["sha256"],
                "files_match_reviewed_wheel": True, "synthetic_recovery": False,
                "actual_missing_commission_preserved": True, "commission_model_scope": "verified_direct_paper_us_equity_only",
                "limitation": "Actual fill identity and economics are required; documented direct-paper equity commission may be modeled separately from unknown actual costs",
                "blockers": list(getattr(clients.get("execution"), "reconciliation_blockers", ["Initial observation pending"]))},
            "updated_at": datetime.now(UTC).isoformat(),
            "account": observed["account"],
            "positions": reconciliation["positions"], "orders": reconciliation["orders"],
            "fills": reconciliation["fills"], "reconciliation": reconciliation,
            "account_at": observed["account_at"], "market_open": observed["market_open"],
            "nautilus_cash": native_cash,
            "market_data": prices, "symbols": list(desired), "feed": "iex",
            "recovery_history": observed.get("recovery_history"),
            "native_recovery_action": observed.get("native_recovery_action"),
            "native_deliveries": clients["execution"].lifecycle.delivery_summary() if "execution" in clients and hasattr(clients["execution"], "lifecycle") else [],
            "prices_checked_at": getattr(data, "checked_at", None),
            "error": observed["error"], "read_only": False, "endpoint": endpoint}


    class Execution(ExecutionClient):
        async def _connect(self):
            self.observation_lock = asyncio.Lock()
            self.history_cache = None
            self.recovery_fee_sources = {}
            self.last_observation = 0
            self.lifecycle = ExecutionLifecycle(self, authority_database, sys.argv[1], lambda: runtime_snapshot(self.cache), lambda: getattr(clients["data"], "asset_metadata", {}), native_epoch=native_epoch)
            self.position_reports, self.order_reports, self.fill_reports = [], [], []
            self.reconciliation_blockers = ["Initial broker observation pending"]
            try:
                await self._query_account(None, force=True)
                await self._apply_observation()
            except Exception as exc:
                observed["error"] = f"Native account client initialization failed ({type(exc).__name__})"
                diagnose(exc)
                raise
            self.stream_task = self.create_task(self.lifecycle.stream(), "trade-updates")
            self.task = self.create_task(self.poll(), "read-only-account")

        async def _query_account(self, command, *, force=False):
            async with self.observation_lock, asyncio.timeout(120):
                if not force and time.monotonic() - self.last_observation < 2:
                    return
                self.last_observation = time.monotonic()
                self.reconciliation_blockers = ["Fresh complete broker observation pending"]
                captured = self.clock.timestamp_ns()
                cutoff, timestamp_initial = 0, datetime.now(UTC).isoformat()
                account, positions, orders, clock = await asyncio.gather(
                    get("/v2/account"), get("/v2/positions"),
                    get("/v2/orders?status=open&limit=500&nested=true"), get("/v2/clock"))
                if account["id"] != initial_account["id"]:
                    raise ValueError("Broker account identity changed; restart with the intended account")
                self.fee_model_account = account
                commands = self.lifecycle.authority().database.read("commands", {})["data"].get("commands", {})
                current_symbols = {row["symbol"] for row in positions + orders}
                current_symbols.update(str(row.instrument_id).removesuffix(".ALPACA") for row in [*self.cache.positions_open(), *self.cache.orders_open()])
                current_symbols.update(row["symbol"] for row in commands.values() if row.get("account_id") == account["id"]
                    and (row.get("state") not in {"filled", "canceled", "rejected", "expired", "not_sent"} or row.get("native_pending_commitment")))
                gaps, fills = [], []
                if len(orders) == 500:
                    gaps.append("Open-order response reached the provider limit; completeness is unverified")
                fees = {}
                try:
                    collection_account = account
                    fills, fees, self.history_cache = await collect_history(self.lifecycle, collection_account, timestamp_initial, self.history_cache)
                    cutoff = timestamp(self.history_cache["from"])
                    observed["recovery_history"] = {key: value for key, value in self.history_cache.items() if key != "activities"}
                except Exception as exc:
                    if current_symbols:
                        gaps.append(f"Current-instrument fill source incomplete ({type(exc).__name__})")
                    observed["recovery_history"] = {"complete": False, "gap": str(exc),
                        "from": self.history_cache["from"] if self.history_cache else collection_account.get("created_at"),
                        "through": timestamp_initial, "limits": {"page_size": 100}}
                scoped_fills = [row for row in fills if not row.get("symbol") or row["symbol"] in current_symbols]
                observed["recovery_history"].update(current_import_symbols=sorted(current_symbols),
                    excluded_closed_fill_ids=[row["id"] for row in fills if row.get("symbol") and row["symbol"] not in current_symbols])
                observed.update(account={key: account.get(key) for key in (
                    "id", "status", "currency", "cash", "equity", "trading_blocked", "buying_power",
                    "long_market_value", "multiplier", "shorting_enabled", "initial_margin", "maintenance_margin")},
                    account_at=datetime.now(UTC).isoformat(), positions=positions, orders=orders,
                    fills=fills, market_open=clock["is_open"], gaps=gaps, lookback_start=cutoff, error=None,
                    broker_observation={"account_available": True, "positions_complete": True,
                        "orders_complete": len(orders) < 500, "source": "Alpaca paper Trading API",
                        "observed_at": datetime.now(UTC).isoformat()})
                if strategy_holder[0] is not None and strategy_holder[0].is_running:
                    strategy_holder[0].sync_markets()
                clients["data"].wake.set()
                retain_observation()
                if (account["status"] != "ACTIVE" or account["currency"] != "USD"
                        or Decimal(account.get("multiplier", "0")) != 1 or account.get("shorting_enabled")):
                    reason = "Native account mapping supports active USD CASH accounts without shorting only"
                    observed["gaps"].append(reason)
                    self.reconciliation_blockers = [reason]
                    observed["native_import_gap"] = reason
                    retain_observation()
                    return
                cash = Money.from_str(account["cash"] + " USD")
                if cash.as_decimal() != Decimal(account["cash"]):
                    reason = "Broker cash exceeds native USD precision; exact broker observation remains available"
                    observed["gaps"].append(reason)
                    self.reconciliation_blockers = [reason]
                    observed["native_import_gap"] = reason
                    retain_observation()
                    return
                native_account = self.cache.account(account_id)
                if native_account is None or native_account.balance_total(usd).as_decimal() != cash.as_decimal():
                    self.generate_account_state([AccountBalance(cash, Money(0, usd), cash)], [], True, captured)
                self.position_reports, self.order_reports, self.fill_reports = [], [], []
                by_order = {row["id"]: row for row in orders}
                native_fills = {}
                for order in self.cache.orders():
                    if str(order.instrument_id).removesuffix(".ALPACA") not in current_symbols:
                        continue
                    for event in order.events:
                        if isinstance(event, OrderFilled) and order_account_binding(order) is not None:
                            identity = execution_id(event.trade_id)
                            if identity in native_fills:
                                raise ValueError("Duplicate retained native trade identity")
                            native_fills[identity] = event
                parent_ids = {fill["order_id"] for fill in scoped_fills} | {str(event.venue_order_id) for event in native_fills.values()}
                pending = set(parent_ids) | set(by_order)
                visited = set()
                while pending:
                    identity = pending.pop()
                    if identity in visited:
                        continue
                    visited.add(identity)
                    if identity not in by_order:
                        response = await asyncio.to_thread(self.lifecycle.transport.read_receipt, "/v2/orders/" + identity)
                        self.lifecycle.receipt("native-recovery", "Alpaca fill-parent/replacement order", {"raw_response": response["raw"].decode()})
                        if response["data"].get("id") != identity:
                            raise ValueError("Fetched order identity differs")
                        by_order[identity] = response["data"]
                    pending.update(value for value in (by_order[identity].get("replaces"), by_order[identity].get("replaced_by")) if value and value not in visited)
                for row in by_order.values():
                    chain, root = set(), row
                    while root.get("replaces"):
                        if root["id"] in chain:
                            raise ValueError("Cyclic replacement chain")
                        chain.add(root["id"])
                        predecessor = by_order[root["replaces"]]
                        if (predecessor.get("replaced_by") != root["id"] or predecessor.get("status") != "replaced"
                                or any(predecessor.get(key) != root.get(key) for key in ("symbol", "side", "type", "asset_class"))
                                or root["type"] != "market" and Decimal(root["filled_qty"]) < Decimal(predecessor["filled_qty"])
                                or timestamp(root["created_at"]) < timestamp(predecessor["created_at"])):
                            raise ValueError("Replacement chain identity, economics or chronology differs")
                        predecessor["native_replacement_verified"] = True
                        root = predecessor
                    row["native_client_order_id"] = row["client_order_id"] if row["type"] == "market" else root["client_order_id"]
                    if row["type"] == "market" and row.get("replaces"):
                        row["native_replacement_quantity_binding"] = market_replacement_binding(row,
                            [by_order[identity] for identity in (chain | {root["id"]}) - {row["id"]}],
                            scoped_fills, observed["recovery_history"])
                    elif row["client_order_id"] != root["client_order_id"]:
                        row["native_client_order_binding"] = {"source": "validated_broker_replacement_chain",
                            "broker_order_id": row["id"], "broker_client_order_id": row["client_order_id"],
                            "native_client_order_id": root["client_order_id"], "order_ids": sorted(chain | {root["id"]})}
                def bind_market_observations(records):
                    for row in by_order.values():
                        binding = row.get("native_replacement_quantity_binding")
                        if not binding:
                            continue
                        for command in records["commands"]["commands"].values():
                            if (command.get("account_id") == account["id"] and command.get("client_order_id") == row["client_order_id"]
                                    and command.get("instrument_id") == row["symbol"] + ".ALPACA"):
                                command.update(native_client_order_id=row["client_order_id"],
                                    native_quantity_offset=binding["ancestor_filled_quantity"], native_replacement_quantity_binding=binding)
                self.lifecycle.authority().transaction(bind_market_observations)
                rows = positions + list(by_order.values())
                for row in rows:
                    if row.get("asset_class") == "us_equity" and self.cache.instrument(instrument_id(row["symbol"])) is None:
                        clients["data"]._handle_instrument(Equity(instrument_id(row["symbol"]), Symbol(row["symbol"]),
                            usd, 2, Price.from_str("0.01"), captured, captured, lot_size=Quantity.from_str("1")))
                unique_fills = {}
                for fill in scoped_fills:
                    identity = execution_id(fill.get("execution_id") or fill.get("id"))
                    if not identity or identity in unique_fills and unique_fills[identity] != fill:
                        gaps.append("Missing or conflicting historical fill identity; original observation retained")
                    else:
                        unique_fills[identity] = fill
                for kind, source, convert, target in (
                    ("position", positions, lambda r: position_report(r, account_id, captured), self.position_reports),
                    ("order", list(by_order.values()), lambda r: order_report(r, account_id, captured), self.order_reports),
                    ("fill", list(unique_fills.values()), lambda r: fill_report(r, by_order[r["order_id"]], account_id, usd, captured, endpoint=endpoint, account=account, linked=fees.get(execution_id(r.get("execution_id") or r["id"]))), self.fill_reports)):
                    for row in source:
                        try:
                            converted = convert(row)
                            if kind == "fill":
                                identity = execution_id(row.get("execution_id") or row["id"])
                                if identity in native_fills:
                                    require_fill_match(converted, native_fills[identity])
                            target.append(converted)
                        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
                            row["import_error"] = str(exc)
                            gaps.append(f"{kind} {row.get('id', row.get('symbol'))}: {exc}")
                reported_ids = {str(report.trade_id) for report in self.fill_reports}
                for identity, event in native_fills.items():
                    if identity not in reported_ids:
                        if str(event.venue_order_id) not in by_order:
                            gaps.append("Retained fill parent order is unavailable: " + identity)
                        else:
                            self.fill_reports.append(retained_fill_report(event, captured))
                for report in self.order_reports:
                    parent = by_order[str(report.venue_order_id)]
                    chain = {parent["id"]}
                    while parent.get("replaces") and parent["type"] != "market":
                        parent = by_order[parent["replaces"]]
                        chain.add(parent["id"])
                    reported = sum((f.last_qty.as_decimal() for f in self.fill_reports if str(f.venue_order_id) in chain), Decimal(0))
                    if reported != report.filled_qty.as_decimal():
                        gaps.append(f"Order {report.venue_order_id}: real executions do not explain cumulative fills; residual inference is disabled")
                # A complete position response is authoritative for previously known symbols now absent.
                known = {p.instrument_id for p in self.cache.positions_open()}
                known.update(r.instrument_id for r in self.order_reports)
                present = {instrument_id(row["symbol"]) for row in positions}
                for missing in known - present:
                    self.position_reports.append(PositionStatusReport(account_id, missing, PositionSide.FLAT,
                        Quantity.from_str("0"), captured, captured))
                observed["order_history"] = list(by_order.values())
                self.recovery_fee_sources = {}
                for report in self.fill_reports:
                    if report.commission is None or report.commission.currency != usd:
                        continue
                    identity = str(report.trade_id)
                    source = unique_fills.get(identity, {})
                    retained = native_fills.get(identity)
                    provenance = source.get("native_fee", {}).get("source", "current_process_native_event")
                    self.recovery_fee_sources[identity] = {"amount": str(report.commission.as_decimal()),
                        "currency": str(report.commission.currency), "execution_id": identity,
                        "account_id": str(report.account_id), "instrument_id": str(report.instrument_id),
                        "order_id": str(report.venue_order_id), "side": enum_name(report.order_side).lower(),
                        "qty": str(report.last_qty.as_decimal()), "price": str(report.last_px.as_decimal()), "ts_event": report.ts_event,
                        "source": provenance, "modeled": source.get("native_fee", {}).get("modeled", False),
                        "history_receipt": observed.get("recovery_history", {}).get("evidence"),
                        "native_evidence": {"native_epoch": native_epoch, "order_key": "orders:" + str(retained.client_order_id)} if retained is not None else None}
                self.reconciliation_blockers = list(dict.fromkeys(gaps))
                if not self.reconciliation_blockers:
                    try:
                        self.mass_status()
                    except (ValueError, TypeError, ArithmeticError) as exc:
                        self.reconciliation_blockers = [str(exc)]
                        observed["gaps"].append(str(exc))
                # Observation receipt, not a competing position ledger. Credentials are never included.
                retain_observation()

        def require_complete_reports(self):
            if self.reconciliation_blockers:
                raise ValueError("Native reconciliation withheld: " + "; ".join(self.reconciliation_blockers))

        def _calculate_commission(self, instrument, last_qty, last_px, liquidity_side):
            raise ValueError("Inferred executions are disabled; authoritative per-fill identity and economics are required")

        def mass_status(self, extra_order=None):
            self.require_complete_reports()
            mass = ExecutionMassStatus(self.client_id, account_id, venue, self.clock.timestamp_ns())
            reports = [report for report in self.order_reports if extra_order is None or report.venue_order_id != extra_order.venue_order_id] + ([extra_order] if extra_order is not None else [])
            fills = {}
            ordered_fills = sorted(self.fill_reports, key=lambda report: report.ts_event)
            for report in ordered_fills:
                fills.setdefault(report.venue_order_id, []).append(report)
            reports.sort(key=lambda report: min((fill.ts_event for fill in fills.get(report.venue_order_id, [])), default=report.ts_accepted))
            mass.add_order_reports(reports)
            mass.add_fill_reports(ordered_fills)
            mass.add_position_reports(self.position_reports)
            return mass

        async def observe_market_successor(self, row, predecessor, predecessor_row):
            quantity, filled = native_quantities(row)
            if quantity != quantity.to_integral_value() or filled != filled.to_integral_value():
                raise ValueError("Fractional MARKET successor quantity is outside the whole-share mapping")
            _, prior_filled = native_quantities(predecessor_row)
            if predecessor is None or predecessor.filled_qty.as_decimal() != prior_filled:
                raise ValueError("MARKET predecessor requires all actual fills before supersession")
            async def settled(predicate):
                for _ in range(20):
                    if predicate():
                        return
                    await asyncio.sleep(0.05)
                raise ValueError("MARKET replacement native observation is not confirmed")
            if not predecessor.is_closed:
                self.generate_order_canceled(predecessor, predecessor.venue_order_id or self.cache.venue_order_id(predecessor.client_order_id),
                    timestamp(predecessor_row["updated_at"]))
                await settled(lambda: predecessor.is_closed)
            identity = ClientOrderId(row["client_order_id"])
            order = self.cache.order(identity)
            if order is None:
                order = strategy_holder[0].order_factory.market(instrument_id=instrument_id(row["symbol"]),
                    order_side=OrderSide.BUY if row["side"] == "buy" else OrderSide.SELL,
                    quantity=Quantity.from_str(str(quantity.to_integral_value())), time_in_force=TimeInForce.DAY,
                    client_order_id=identity, tags=["broker_replacement_observation"])
                self.cache.add_order(order, client_id=self.client_id)
            if order.quantity.as_decimal() != quantity or order.instrument_id != predecessor.instrument_id or order.side != predecessor.side:
                raise ValueError("MARKET successor native identity or remaining quantity conflicts")
            if order.venue_order_id is None:
                if row["status"] == "rejected":
                    self.cache.add_venue_order_id(identity, VenueOrderId(row["id"]))
                    self.generate_order_rejected(order, row.get("reject_reason") or "Broker rejected successor", timestamp(row["updated_at"]), False)
                    await settled(lambda: enum_name(order.status) == "REJECTED")
                elif row["status"] in {"pending_new", "pending_cancel", "pending_replace"}:
                    if enum_name(order.status) == "INITIALIZED":
                        self.generate_order_submitted(order, timestamp(row.get("submitted_at") or row["created_at"]))
                        await settled(lambda: enum_name(order.status) == "SUBMITTED")
                    self.cache.add_venue_order_id(identity, VenueOrderId(row["id"]))
                else:
                    self.generate_order_accepted(order, VenueOrderId(row["id"]), timestamp(row.get("submitted_at") or row["created_at"]))
                    await settled(lambda: str(order.venue_order_id) == row["id"])
            pending = {"pending_cancel": "PENDING_CANCEL", "pending_replace": "PENDING_UPDATE"}.get(row["status"])
            if pending and enum_name(order.status) != pending:
                self.generate_observed_pending(order, VenueOrderId(row["id"]), pending, timestamp(row["updated_at"]))
                await settled(lambda: enum_name(order.status) == pending)
            return order

        async def _apply_observation(self):
            """Apply actual identities and globally ordered fills through official native interfaces."""
            async with self.observation_lock:
                try:
                    self.require_complete_reports()
                    factory = strategy_holder[0].order_factory
                    parents = {row["id"]: row for row in observed.get("order_history", [])}
                    reports = {str(report.venue_order_id): report for report in self.order_reports}

                    async def settled(predicate):
                        for _ in range(20):
                            if predicate():
                                return
                            await asyncio.sleep(0.05)
                        raise ValueError("Official native event application has not been confirmed")

                    async def advance(order, report):
                        current_venue = order.venue_order_id or self.cache.venue_order_id(order.client_order_id)
                        if current_venue == report.venue_order_id:
                            return
                        path, row = [], parents[str(report.venue_order_id)]
                        while row["id"] != str(current_venue):
                            if not row.get("replaces"):
                                raise ValueError("Native venue identity is outside the validated replacement chain")
                            path.append(row["id"])
                            row = parents[row["replaces"]]
                        for identity in reversed(path):
                            successor = reports[identity]
                            self.generate_order_updated(order, successor.venue_order_id, successor.quantity, successor.price,
                                None, False, timestamp(parents[identity]["created_at"]), venue_order_id_modified=True)
                            await settled(lambda: order.venue_order_id == successor.venue_order_id)

                    for report in self.order_reports:
                        if report.client_order_id is None:
                            raise ValueError("Broker order has no source client identity")
                        if parents[str(report.venue_order_id)].get("replaces") and enum_name(report.order_type) != "MARKET":
                            continue
                        order = self.cache.order(report.client_order_id)
                        if order is None:
                            kwargs = dict(instrument_id=report.instrument_id, order_side=report.order_side,
                                quantity=report.quantity, time_in_force=report.time_in_force, client_order_id=report.client_order_id,
                                tags=["broker_observation"])
                            order = factory.limit(**kwargs, price=report.price) if enum_name(report.order_type) == "LIMIT" else factory.market(**kwargs)
                            self.cache.add_order(order, client_id=self.client_id)
                        if order.instrument_id != report.instrument_id or order.side != report.order_side:
                            raise ValueError("Cached native order instrument or side conflicts")
                        if order.venue_order_id is None:
                            if enum_name(report.order_status) in {"SUBMITTED", "PENDING_CANCEL", "PENDING_UPDATE"}:
                                if enum_name(order.status) == "INITIALIZED":
                                    self.generate_order_submitted(order, report.ts_accepted)
                                    await settled(lambda: enum_name(order.status) == "SUBMITTED")
                                self.cache.add_venue_order_id(order.client_order_id, report.venue_order_id)
                            elif enum_name(report.order_status) != "REJECTED":
                                self.generate_order_accepted(order, report.venue_order_id, report.ts_accepted)
                                await settled(lambda: order.venue_order_id == report.venue_order_id)
                    for report in sorted(self.fill_reports, key=lambda item: item.ts_event):
                        order = self.cache.order(report.client_order_id)
                        if order is None or order_account_binding(order) is None:
                            raise ValueError("Real fill has no confirmed native account/order identity")
                        existing = [event for event in order.events if isinstance(event, OrderFilled) and execution_id(event.trade_id) == execution_id(report.trade_id)]
                        if existing:
                            if len(existing) != 1:
                                raise ValueError("Duplicate native execution identity")
                            require_fill_match(report, existing[0])
                            continue
                        await advance(order, report)
                        self._send_fill_report(report)
                        await settled(lambda: any(isinstance(event, OrderFilled) and execution_id(event.trade_id) == execution_id(report.trade_id) for event in order.events))
                        event = next(event for event in order.events if isinstance(event, OrderFilled) and execution_id(event.trade_id) == execution_id(report.trade_id))
                        require_fill_match(report, event)
                    for report in self.order_reports:
                        row = parents[str(report.venue_order_id)]
                        if row.get("native_replacement_verified") and row["type"] != "market":
                            continue  # Confirmed successor supersedes only the old remainder.
                        order = self.cache.order(report.client_order_id)
                        if order is not None and order.venue_order_id is not None:
                            await advance(order, report)
                        if (order is None or order.filled_qty != report.filled_qty
                                or order.venue_order_id is not None and order.venue_order_id != report.venue_order_id):
                            raise ValueError("Final order observation lacks exact real native fill coverage")
                        state = enum_name(report.order_status)
                        if state in {"SUBMITTED", "PENDING_CANCEL", "PENDING_UPDATE"}:
                            if order.status != report.order_status and state != "SUBMITTED":
                                self.generate_observed_pending(order, report.venue_order_id, state, report.ts_last)
                        else:
                            self._send_order_status_report(report)
                        await settled(lambda: order.status == report.order_status)
                    for report in self.position_reports:
                        quantity = sum((position.quantity.as_decimal() * (-1 if position.side == PositionSide.SHORT else 1)
                            for position in self.cache.positions_open(instrument_id=report.instrument_id)), Decimal(0))
                        expected = report.quantity.as_decimal() * (-1 if report.position_side == PositionSide.SHORT else 1)
                        if quantity != expected:
                            raise ValueError("Final broker position differs from actual native executions; no synthetic fill permitted")
                        self._send_position_status_report(report)
                    cash = Money.from_str(observed["account"]["cash"] + " USD")
                    self.generate_account_state([AccountBalance(cash, Money(0, usd), cash)], [], True, self.clock.timestamp_ns())
                    await settled(lambda: self.cache.account(account_id) is not None and self.cache.account(account_id).balance_total(usd).as_decimal() == cash.as_decimal())
                    observed.pop("native_import_gap", None)
                    if self.lifecycle.resolve_market_replacement_receipts():
                        self.lifecycle.authority().reconcile()
                except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
                    observed["native_import_gap"] = str(exc)
                    self.reconciliation_blockers = [str(exc)]
                retain_observation()

        async def observed_mass_status(self):
            async with self.observation_lock:
                try:
                    mass = self.mass_status()
                    observed.pop("native_import_gap", None)
                    return mass
                except (ValueError, TypeError, ArithmeticError) as exc:
                    observed["native_import_gap"] = str(exc)
                    # Withhold unsupported native financial imports. Broker observations
                    # remain visible; an empty import is never reported as a flat account.
                    return ExecutionMassStatus(self.client_id, account_id, venue, self.clock.timestamp_ns())

        async def _generate_mass_status(self, lookback_mins):
            await self._query_account(None)
            await self._apply_observation()
            return await self.observed_mass_status()

        async def poll(self):
            while True:
                await asyncio.sleep(30)
                try:
                    await self._query_account(None)
                    await self._apply_observation()
                except Exception as exc:
                    observed["error"] = f"Account observation unavailable ({type(exc).__name__})"

        async def _generate_order_status_reports(self, command):
            self.require_complete_reports()
            return self.order_reports

        async def _generate_position_status_reports(self, command):
            self.require_complete_reports()
            return self.position_reports

        async def _generate_fill_reports(self, command):
            self.require_complete_reports()
            return self.fill_reports

        async def _generate_order_status_report(self, command):
            async with self.observation_lock:
                self.require_complete_reports()
                self.reconciliation_blockers = ["Targeted order collection pending; prior reports cannot establish its current fill coverage"]
                broker_id = command.venue_order_id or (self.cache.venue_order_id(command.client_order_id) if command.client_order_id is not None else None)
                observed["targeted_order"] = {"venue_order_id": str(broker_id) if broker_id is not None else None, "status": "collecting"}
                try:
                    if broker_id is None and command.client_order_id is None:
                        raise ValueError("Targeted order requires an indexed broker identity or source client ID")
                    path = "/v2/orders/" + str(broker_id) if broker_id is not None else "/v2/orders:by_client_order_id?" + urlencode({"client_order_id": str(command.client_order_id)})
                    response = await asyncio.to_thread(self.lifecycle.transport.read_receipt, path)
                    reference = self.lifecycle.receipt("native-targeted-orders", "Alpaca targeted order observation", {"raw_response": response["raw"].decode()})
                    row = response["data"]
                    observed["targeted_order"].update(row=row, receipt=reference, received_at=response["received_at"])
                    known = next((item for item in observed.get("order_history", []) if item["id"] == row["id"]), None)
                    same_source = known and all(known.get(key) == row.get(key) for key in ("replaces", "replaced_by", "client_order_id", "symbol", "side", "type", "qty", "filled_qty", "time_in_force", "extended_hours", "order_class", "asset_class"))
                    if same_source:
                        row = {**row, **{key: known[key] for key in ("native_client_order_id", "native_replacement_verified", "native_replacement_quantity_binding") if key in known}}
                    if row.get("type") == "market" and row.get("replaces") and not row.get("native_replacement_quantity_binding"):
                        raise ValueError("Fresh exact MARKET replacement quantity evidence is required")
                    report = order_report(row, account_id, self.clock.timestamp_ns())
                    if broker_id is not None and str(report.venue_order_id) != str(broker_id) or command.client_order_id is not None and report.client_order_id != command.client_order_id:
                        raise ValueError("Targeted order identity differs")
                    sources = {execution_id(fill.get("execution_id") or fill["id"]): fill for fill in observed["fills"] if fill.get("order_id") == row["id"]}
                    native = self.cache.order(report.client_order_id) if report.client_order_id is not None else None
                    if sum((Decimal(fill["qty"]) for fill in sources.values()), Decimal(0)) != report.filled_qty.as_decimal() and (native is None or native.filled_qty != report.filled_qty):
                        raise ValueError("Targeted cumulative quantity lacks real fills or exact retained native coverage")
                    if native is not None and (native.quantity != report.quantity or native.filled_qty != report.filled_qty):
                        raise ValueError("Native translated quantity or fills differ from targeted response")
                    if report.filled_qty.as_decimal() > 0:
                        if order_account_binding(native) is None or native.venue_order_id != report.venue_order_id or native.instrument_id != report.instrument_id:
                            raise ValueError("Targeted filled order has no matching current native identity")
                        for source in sources.values():
                            if not ExecutionLifecycle.native_applied(native, "fill", {"execution_id": source["id"], "qty": source["qty"], "price": source["price"], "commission": source.get("commission") if source.get("commission") is not None else source.get("native_fee", {}).get("amount")}, row, None, source["transaction_time"]):
                                raise ValueError("Targeted order lacks exact current-native proof for a real fill")
                    # The candidate must also preserve the complete position lifecycle.
                    self.reconciliation_blockers = []
                    self.mass_status(report)
                except Exception as exc:
                    reason = "Targeted order reconciliation blocked; fresh identity/economics/fill coverage is incomplete (" + type(exc).__name__ + ")"
                    self.reconciliation_blockers = [reason]
                    observed["gaps"].append(reason)
                    observed["targeted_order"].update(status="withheld", reason=reason)
                    retain_observation()
                    raise ValueError(reason) from None
                self.reconciliation_blockers = []
                observed["targeted_order"]["status"] = "validated_current_native_coverage"
                retain_observation()
                return report

        async def _disconnect(self):
            if getattr(self, "stream_task", None):
                self.stream_task.cancel()
            await Data._disconnect(self)

        async def _submit_order(self, command):
            await self.lifecycle.submit(command)

        async def _cancel_order(self, command):
            await self.lifecycle.cancel(command)

        async def _modify_order(self, command):
            await self.lifecycle.replace(command)

        async def _cancel_all_orders(self, command):
            raise ValueError("Cancel-all is unsupported; exact single-order authorization is required")


    class DataFactory(DataClientFactory):
        @staticmethod
        def create(**kwargs):
            clients["data"] = Data(**kwargs, venue=venue)
            return clients["data"]

    class ExecFactory(ExecutionClientFactory):
        @staticmethod
        def create(**kwargs):
            clients["execution"] = Execution(**kwargs, venue=venue, account_id=account_id,
                account_type=AccountType.CASH, oms_type=OmsType.NETTING, base_currency=usd)
            return clients["execution"]

    class Observer(Strategy):
        def on_start(self):
            self.subscribed_symbols = set()
            strategy_holder[0] = self
            self.sync_markets()

        def sync_markets(self):
            data = clients["data"]
            symbols = {symbol for symbol in data.market_symbols() if symbol in data.assets}
            data.register(symbols)
            for symbol in self.subscribed_symbols - symbols:
                self.unsubscribe_quotes(instrument_id(symbol))
                self.unsubscribe_trades(instrument_id(symbol))
            for symbol in symbols - self.subscribed_symbols:
                self.subscribe_quotes(instrument_id(symbol))
                self.subscribe_trades(instrument_id(symbol))
            self.subscribed_symbols = symbols
            data.observations = {s: data.observations[s] for s in symbols if s in data.observations}
            data.wake.set()

        def configure(self, symbols):
            desired[:] = symbols
            if self.is_running:
                self.sync_markets()

        def dispatch(self, identity, action="submit"):
            lifecycle = clients["execution"].lifecycle
            durable = lifecycle.command(identity, sending=action == "submit")
            terms = durable["terms"]
            native_id = ClientOrderId(durable.get("native_client_order_id", durable["client_order_id"]))
            params = {"durable_command_id": identity}
            if action == "submit":
                kwargs = {"instrument_id": instrument_id(terms["symbol"]),
                    "order_side": OrderSide.BUY if terms["side"] == "BUY" else OrderSide.SELL,
                    "quantity": Quantity.from_str(terms["quantity"]), "time_in_force": TimeInForce.DAY,
                    "client_order_id": native_id}
                order = self.order_factory.limit(**kwargs, price=Price.from_str(terms["limit_price"])) if terms["order_type"] == "LIMIT" else self.order_factory.market(**kwargs)
                self.submit_order(order, params=params)
            elif action == "cancel":
                order = self.cache.order(native_id)
                lifecycle.native_action_intent(identity, durable["pending_action"]["id"], order_snapshot(order), [str(event.id) for event in order.events])
                self.cancel_order(order, params=params)
            elif action == "replace":
                replacement = lifecycle.command(durable["pending_action"]["replacement_command_id"], sending=True)
                proposed = replacement["terms"]
                order = self.cache.order(native_id)
                lifecycle.native_action_intent(identity, durable["pending_action"]["id"], order_snapshot(order), [str(event.id) for event in order.events])
                source = next(row for row in observed["orders"] if row["id"] == durable["pending_action"]["broker_order_id"])
                quantity = Decimal(proposed["quantity"]) - Decimal(str((source.get("native_replacement_quantity_binding") or {}).get("ancestor_filled_quantity", "0")))
                self.modify_order(order, quantity=Quantity.from_str(str(quantity.to_integral_value())),
                    price=Price.from_str(proposed["limit_price"]) if proposed["order_type"] == "LIMIT" else None, params=params)
            else:
                raise ValueError("Unsupported native command action")

    retained_node = [None]

    async def run():
        observer = Observer()
        strategy_holder[0] = observer
        loop = asyncio.get_running_loop()
        node = build_node(DataFactory, ExecFactory, observer, loop)
        retained_node[0] = node
        handle, cache = node, node.cache

        async def receive(command):
            reply = {"type": "reply", "request_id": command.get("request_id"), "read_only": False}
            try:
                if command.get("command") == "configure":
                    observer.configure(command["symbols"])
                elif command.get("command") == "refresh":
                    await clients["data"].refresh()
                    await clients["execution"]._query_account(None)
                    await clients["execution"]._apply_observation()
                elif command.get("command") == "dispatch":
                    observer.dispatch(command["command_id"], command.get("action", "submit"))
                    reply["queued_in_native_engine"] = True
                elif command.get("command") == "reconcile_identity":
                    await clients["execution"].lifecycle.reconcile_identity(command["command_id"])
                else:
                    raise ValueError("Unsupported native command")
            except (ValueError, KeyError, TypeError) as exc:
                reply["error"] = str(exc)
            publish_once()
            output.write(json.dumps(reply) + "\n")

        def commands():
            for line in sys.stdin:
                command = json.loads(line)
                if command.get("command") == "stop":
                    break
                asyncio.run_coroutine_threadsafe(receive(command), loop)
            if not loop.is_closed():
                loop.call_soon_threadsafe(handle.stop)

        threading.Thread(target=commands, daemon=True).start()

        def publish_once():
            output.write(json.dumps(runtime_snapshot(cache)) + "\n")

        async def publish():
            while True:
                publish_once()
                await asyncio.sleep(1)

        publisher = asyncio.create_task(publish())
        publisher.add_done_callback(lambda _: handle.stop())
        try:
            await node.run_async()
        finally:
            publisher.cancel()
            results = await asyncio.gather(publisher, return_exceptions=True)
            if isinstance(results[0], Exception):
                raise results[0]

    try:
        try:
            asyncio.run(run())
        finally:
            if retained_node[0] is not None:
                retained_node[0].dispose()
    except Exception as exc:
        diagnose(exc)
        error = observed["error"] or f"Nautilus stopped ({type(exc).__name__})"
        gaps = list(dict.fromkeys(observed["gaps"] + [error]))
        positions = [{**p, "reconciliation_status": "incomplete", "management_supported": False} for p in observed["positions"]]
        orders = [{**o, "reconciliation_status": "incomplete", "management_supported": False} for o in observed["orders"]]
        output.write(json.dumps({"status": "error", "error": error, "read_only": True,
            "persistence": dict(persistence_status),
            "positions": positions, "orders": orders, "fills": observed["fills"],
            "reconciliation": {"status": "incomplete", "gaps": gaps, "positions_reconciled": False,
                "orders_reconciled": False, "observed_at": observed["account_at"],
                **history_scope(observed), "positions": positions,
                "orders": orders, "fills": observed["fills"]}}) + "\n")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
