"""Nautilus subprocess over durable user authority; stdout is JSONL, diagnostics go to stderr."""

import asyncio
import copy
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
from numbers import Integral, Real
from math import isfinite
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
    from _tradingagents_native_adapter.linked_orders import observed_orders, native_order, native_group, native_observation, LIVE, equity_quantity, asset_session_flags, option_contract, is_package
    from _tradingagents_native_adapter.alpaca_readonly import AlpacaREST, ConnectionConfig
    from _tradingagents_native_adapter.alpaca_reports import fill_report, order_report, position_report, timestamp, execution_id, native_quantities, market_replacement_binding
    from _tradingagents_native_adapter.linked_orders import broker_position_quantity, native_type, native_profile_transition, package_terms, package_valuation_key, validate_package_valuation
    from _tradingagents_native_adapter.account_projection import reconcile, history_scope
    from nautilus_trader import __version__, __file__ as native_package_file
    import pandas as pd
    from _tradingagents_native_adapter.native_types import (
        AccountBalance, AccountId, AccountType, Currency, Equity, OptionContract, InstrumentId, reported_margin_projection,
        Money, OmsType, Price, Quantity, QuoteTick, Symbol, Venue, LiquiditySide,
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
    if startup.get("option_feed") not in {None, "opra", "indicative"}:
        raise ValueError("Choose an explicit supported option feed")
    connection = ConnectionConfig.load(sys.argv[1])
    transport = AlpacaREST(sys.argv[1], connection=connection)
    endpoint = connection.endpoint

    def diagnose(exc):
        message = connection.redact(str(exc))
        print(type(exc).__name__ + ": " + message[:1200], file=sys.stderr, flush=True)
        traceback.print_tb(exc.__traceback__, limit=8, file=sys.stderr)
    persistence_status = {"configured": False, "state": "in_memory", "backing": "memory",
                          "restore_ready": False, "durable_writes_confirmed": False,
                          "limitation": "Official native cache is in memory; persisted native execution proof is unavailable."}
    output.write(json.dumps({"status": "starting", "read_only": False, "endpoint": endpoint, "persistence": persistence_status}) + "\n")
    desired = list(startup["symbols"])
    authority_database = startup.get("authority_database")
    instrument_id = lambda symbol: InstrumentId.from_str(f"{symbol}.ALPACA")
    initial_source = transport.read_receipt("/v2/account")
    initial_account = initial_source["data"]
    execution_profile = startup.get("execution_profile", "long_only")
    profile_transition = native_profile_transition(execution_profile, initial_account, endpoint=endpoint, native_epoch=native_epoch,
        source_receipt={"raw_sha256": hashlib.sha256(initial_source["raw"]).hexdigest(), "received_at": initial_source["received_at"], "path": "/v2/account"})
    if execution_profile == "bounded_risk_spread_v1" and profile_transition["eligibility"]["eligible"]:
        try:
            reported_margin_projection(profile_transition["balance_projection"])
        except (ValueError, TypeError, ArithmeticError, OverflowError):
            profile_transition["eligibility"] = {"eligible": False, "blockers": ["Actual margin projection is not exactly representable by the native account"]}
            profile_transition["native_account_type"] = None
    if execution_profile == "bounded_risk_spread_v1" and not profile_transition["eligibility"]["eligible"]:
        output.write(json.dumps({"status": "error", "read_only": True, "endpoint": endpoint,
            "execution_profile": execution_profile, "profile_transition": profile_transition,
            "error": "; ".join(profile_transition["eligibility"]["blockers"])}) + "\n")
        output.flush()
        return
    account_id = AccountId("ALPACA-" + initial_account["id"])
    session_account_type = AccountType.MARGIN if execution_profile == "bounded_risk_spread_v1" else AccountType.CASH
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
            return await asyncio.to_thread(transport.read, path, data=data)
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
            self.quote_sources, self.spread_valuations = {}, {}
            self.refresh_lock, self.wake = asyncio.Lock(), asyncio.Event()
            self.last_attempt, self.retry_at, self.last_symbols = 0, 0, ()
            self.checked_at = None
            self.asset_metadata = {a["symbol"]: a for a in await get("/v2/assets?status=active&asset_class=us_equity")}
            self.asset_metadata = {symbol: {**asset, **asset_session_flags(asset)} for symbol, asset in self.asset_metadata.items()}
            self.asset_observed_at = datetime.now(UTC).isoformat()
            self.assets = set(self.asset_metadata)
            self.option_metadata = {}
            await self.load_options(desired)
            self.register(desired)
            self.task = self.create_task(self.poll(), "read-only-index-prices")

        async def load_options(self, symbols):
            import re
            for symbol in symbols:
                if not re.fullmatch(r"[A-Z]{1,6}\d{6}[CP]\d{8}", symbol):
                    continue
                try:
                    response = await asyncio.to_thread(transport.option_contracts, {"symbol": symbol})
                    metadata = response["contracts"][0]
                    contract = option_contract(metadata)
                    if contract["symbol"] != symbol:
                        raise ValueError("Broker contract symbol differs")
                    self.option_metadata[symbol] = metadata
                    self.asset_metadata[symbol] = {**contract, "class": "us_option", "fractionable": False, "option_contract": metadata}
                    self.assets.add(symbol)
                except (ValueError, KeyError, IndexError, TypeError, ArithmeticError, HTTPError, URLError) as exc:
                    self.option_metadata.pop(symbol, None)
                    self.assets.discard(symbol)
                    self.asset_metadata.pop(symbol, None)
                    self.observations[symbol] = {"error": "Option contract unavailable (" + type(exc).__name__ + ")"}

        def register(self, symbols, *, observed=False, fractional_observation=False):
            stamp = self.clock.timestamp_ns()
            for symbol in symbols:
                if symbol in self.option_metadata:
                    prior = self.cache.instrument(instrument_id(symbol))
                    metadata = self.option_metadata[symbol]
                    if prior is None or (prior.info or {}).get("option_contract", {}).get("sha256") != metadata["sha256"]:
                        self._handle_instrument(OptionContract(metadata, stamp))
                    continue
                asset = self.asset_metadata.get(symbol, {})
                metadata = {key: asset.get(key) for key in ("id", "symbol", "class", "exchange", "status", "tradable", "fractionable",
                                                          "overnight_tradable", "overnight_halted", "fractional_eh_enabled", "attributes")}
                prior = self.cache.instrument(instrument_id(symbol))
                fractional = asset.get("fractionable") is True or fractional_observation or prior is not None and prior.size_precision == 9
                if (symbol in self.assets or observed) and (prior is None or fractional and prior.size_precision != 9
                        or (prior.info or {}).get("alpaca_asset") != metadata):
                    self._handle_instrument(Equity(instrument_id(symbol), Symbol(symbol), usd, 2,
                        Price.from_str("0.01"), stamp, stamp, lot_size=Quantity.from_str("1"), fractional_precision=fractional,
                        info={"alpaca_asset": metadata, "asset_observed_at": self.asset_observed_at,
                              "asset_source": "/v2/assets?status=active&asset_class=us_equity"}))

        async def _subscribe_quotes(self, command):
            self.wake.set()

        async def _subscribe_trades(self, command):
            pass  # Quotes and trades share the same batched snapshot request.

        def market_symbols(self):
            return tuple(dict.fromkeys(desired + [p['symbol'] for p in observed['positions'] + observed['orders'] if p.get('asset_class') in {'us_equity', 'us_option'} and p['symbol'] in self.assets]))

        async def refresh(self):
            async with self.refresh_lock:
                symbols, now = self.market_symbols(), asyncio.get_running_loop().time()
                if now < self.retry_at or (symbols == self.last_symbols and now - self.last_attempt < 5):
                    return
                await self.load_options(symbols)
                self.register(symbols)
                self.last_attempt, self.last_symbols = now, symbols
                self.observations = {s: self.observations.get(s, {"error": "Awaiting latest IEX snapshot"}) for s in symbols}
                eligible = [s for s in symbols if s in self.assets and s not in self.option_metadata]
                for symbol in symbols:
                    if symbol not in self.option_metadata:
                        continue
                    metadata = self.option_metadata[symbol]
                    result = self.observations[symbol] = {"option_contract": metadata, "market_feed": startup.get("option_feed"),
                        "source": "Alpaca option quote", "contract_observed_at": metadata["received_at"]}
                    try:
                        response = await asyncio.to_thread(transport.option_quote, symbol, startup.get("option_feed"))
                        quote = response["data"].get("quotes", {}).get(symbol) or {}
                        if not 0 <= Decimal(str(quote["bp"])) <= Decimal(str(quote["ap"])) or Decimal(str(quote["ap"])) <= 0:
                            raise ValueError("Option bid/ask is unavailable or crossed")
                        tick = QuoteTick(instrument_id(symbol), Price.from_str(str(quote["bp"])), Price.from_str(str(quote["ap"])),
                            Quantity.from_str(str(quote["bs"])), Quantity.from_str(str(quote["as"])), timestamp(quote["t"]), self.clock.timestamp_ns())
                        if any(getattr(tick, field).as_decimal() != Decimal(str(quote[key])) for field, key in
                                (("bid_price", "bp"), ("ask_price", "ap"), ("bid_size", "bs"), ("ask_size", "as"))):
                            raise ValueError("Native quote price/size precision differs from actual option quote")
                        response_hash = hashlib.sha256(response["raw"]).hexdigest()
                        prior = self.quote_sources.get(symbol)
                        cached = self.cache.quote_tick(instrument_id(symbol))
                        if (prior and cached is not None and prior["contract_sha256"] == metadata["sha256"]
                                and prior["value"]["raw_response_sha256"] == response_hash and prior["value"]["feed"] == startup.get("option_feed")
                                and all(getattr(cached, key) == getattr(tick, key) for key in ("bid_price", "ask_price", "bid_size", "ask_size", "ts_event"))):
                            tick = cached
                        else:
                            self._handle_data(tick)
                            prior = None
                        quote_values = {key: str(getattr(tick, key).as_decimal()) for key in ("bid_price", "ask_price", "bid_size", "ask_size")}
                        quote_values.update(ts_event=str(tick.ts_event), ts_init=str(tick.ts_init))
                        source = {"raw_quote_sha256": package_valuation_key(quote), "raw_response_sha256": response_hash,
                            "feed": startup.get("option_feed"), "scope": "alpaca_option_quote", "quote": quote_values}
                        source.update(source_generation=package_valuation_key(source), source_receipt=prior["value"]["source_receipt"] if prior else None)
                        if prior is None:
                            self.spread_valuations = {key: value for key, value in self.spread_valuations.items()
                                if not any(item["instrument_id"] == str(instrument_id(symbol)) for item in value["inputs"])}
                        self.quote_sources[symbol] = {"value": source, "contract_sha256": metadata["sha256"],
                            "source": response["source"], "raw_response": response["raw"].decode(), "received_at": response["received_at"]}
                        result.update(latestQuote=True, source=response["source"], received_at=response["received_at"],
                            raw_quote=quote, raw_quote_response=response["raw"].decode(), quote_sha256=hashlib.sha256(response["raw"]).hexdigest(),
                            quote_source=copy.deepcopy(source),
                            entitlement_basis="Successful response for explicitly selected feed; not evidence of another feed entitlement")
                    except (ValueError, KeyError, TypeError, ArithmeticError, HTTPError, URLError) as exc:
                        self.quote_sources.pop(symbol, None)
                        self.spread_valuations = {key: value for key, value in self.spread_valuations.items()
                            if not any(item["instrument_id"] == str(instrument_id(symbol)) for item in value["inputs"])}
                        result["error"] = "Option quote unavailable (" + type(exc).__name__ + ")"
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

        def package_native_limits(self, terms, spread, ticks, remaining, output):
            risk = retained_node[0].kernel.risk_engine
            caps = risk.max_notionals_per_order()
            quotes = {str(tick.instrument_id): tick for tick in ticks}
            blockers, per_leg = [], []

            def check(instrument, quantity, price, *, supplemental=False):
                identity = instrument.id
                raw_cap = caps.get(identity)
                cap = None if raw_cap is None else Decimal(str(raw_cap))
                currency = str(instrument.quote_currency)
                notional = instrument.notional_value(quantity, price)
                errors = []
                if currency != "USD" or str(notional.currency) != currency:
                    errors.append("Native instrument/notional currency differs")
                if cap is not None and (not cap.is_finite() or cap < 0):
                    errors.append("Original native notional cap is invalid")
                amount = abs(notional.as_decimal()) if supplemental else notional.as_decimal()
                if cap is not None and amount > cap:
                    errors.append("Supplemental ABS spread cap exceeded" if supplemental else "Original native leg notional cap exceeded")
                bounds = {name: str(getattr(instrument, name)) if getattr(instrument, name) is not None else None
                    for name in ("min_quantity", "max_quantity", "min_notional", "max_notional", "size_increment", "price_increment")}
                bounds.update(size_precision=instrument.size_precision, price_precision=instrument.price_precision)
                if quantity.precision > instrument.size_precision or instrument.min_quantity is not None and quantity < instrument.min_quantity or instrument.max_quantity is not None and quantity > instrument.max_quantity:
                    errors.append("Actual leg/native quantity bounds are exceeded")
                for name, exceeds in (("min_notional", False), ("max_notional", True)):
                    bound = getattr(instrument, name)
                    if bound is not None and (str(bound.currency) != currency or
                            (amount > bound.as_decimal() if exceeds else amount < bound.as_decimal())):
                        errors.append("Native instrument notional bound differs or is exceeded")
                return {"instrument_id": str(identity), "quantity": str(quantity.as_decimal()),
                    "notional": {"amount": str(notional.as_decimal()), "currency": str(notional.currency)},
                    "max_notional": {"configured": identity in caps, "original": None if raw_cap is None else str(raw_cap),
                        "amount": None if cap is None else str(cap), "currency": currency,
                        "basis": "RiskEngine public per-instrument cap in native quote currency; null explicitly disabled or absent"},
                    "bounds": bounds, "blockers": errors}

            for leg in terms["legs"]:
                instrument = self.cache.instrument(InstrumentId.from_str(leg["instrument_id"]))
                if instrument is None or (instrument.info or {}).get("option_contract", {}).get("sha256") != leg["option_contract"]["sha256"]:
                    raise ValueError("Native leg instrument is unavailable or differs from exact contract")
                tick = quotes[leg["instrument_id"]]
                side = "ask_price" if leg["side"] == "BUY" else "bid_price"
                item = check(instrument, Quantity.from_str(str(remaining * Decimal(leg["ratio_qty"]))), getattr(tick, side))
                item.update(side=leg["side"], quote_side=side)
                per_leg.append(item)
                blockers.extend(item["blockers"])
            supplemental = check(spread, Quantity.from_str(str(remaining)), output.ask_price, supplemental=True)
            supplemental.update(supplemental_abs=True, actual_broker_price_cap=False,
                absolute_notional=str(abs(Decimal(supplemental["notional"]["amount"]))),
                basis="ABS public derived ask premium * actual whole remaining strategy units * native multiplier; not replacement native cap")
            if terms["order_type"] == "LIMIT":
                limit = check(spread, Quantity.from_str(str(remaining)), Price.from_str(terms["limit_price"]), supplemental=True)
                supplemental["approved_limit_absolute_notional"] = str(abs(Decimal(limit["notional"]["amount"])))
                supplemental["blockers"].extend(limit["blockers"])
            blockers.extend(supplemental["blockers"])
            return {"source": "public Instrument.notional_value and RiskEngine.max_notionals_per_order",
                "per_leg": per_leg, "spread": supplemental, "blockers": list(dict.fromkeys(blockers)),
                "margin_collateral_checked": False, "account_balance_scope": "Native margin risk early-return is not a collateral check",
                "notional_rounding": "Public native Money currency precision; no hand-coded replacement notional",
                "native_caps": [{"instrument_id": str(identity), "amount": None if amount is None else str(amount)} for identity, amount in sorted(caps.items(), key=lambda item: str(item[0]))],
                "size_limits": {"native_bid_units": str(output.bid_size.as_decimal()), "native_ask_units": str(output.ask_size.as_decimal()),
                    "exact_bid_units": str(min((tick.bid_size.as_decimal() if leg["side"] == "BUY" else tick.ask_size.as_decimal()) / Decimal(leg["ratio_qty"]) for leg, tick in ((leg, quotes[leg["instrument_id"]]) for leg in terms["legs"]))),
                    "exact_ask_units": str(min((tick.ask_size.as_decimal() if leg["side"] == "BUY" else tick.bid_size.as_decimal()) / Decimal(leg["ratio_qty"]) for leg, tick in ((leg, quotes[leg["instrument_id"]]) for leg in terms["legs"]))),
                    "basis": "Actual displayed leg sizes/ratios; native make_qty rounding is separate; not a fill guarantee or broker order cap"}}

        def prepare_package(self, terms):
            from _tradingagents_native_adapter.native_types import OptionSpread
            from nautilus_trader.data.aggregation import SpreadQuoteAggregator
            from nautilus_trader.data.engine import DataEngine
            from nautilus_trader.model.greeks import GreeksCalculator

            key = package_valuation_key(terms)
            self.spread_valuations.pop(key, None)
            package = package_terms(terms)
            execution = clients["execution"]
            lifecycle = execution.lifecycle
            spread = OptionSpread(terms, self.clock.timestamp_ns())
            DataEngine.process(retained_node[0].kernel.data_engine, spread)
            total, filled, offset, replacement = Decimal(terms["quantity"]), Decimal(0), Decimal(0), None
            replacement_id = (terms.get("replacement") or {}).get("order_id")
            if replacement_id:
                matches = [row for row in observed["orders"] if row.get("id") == replacement_id and row.get("package_terms")]
                if len(matches) != 1:
                    raise ValueError("Exact replacement parent source is unavailable for package valuation")
                source = matches[0]
                if source["package_terms"]["instrument_id"] != terms["instrument_id"]:
                    raise ValueError("Replacement source package identity differs")
                filled = Decimal(source["filled_qty"])
                offset = Decimal(str((source.get("native_replacement_quantity_binding") or {}).get("ancestor_filled_quantity", "0")))
                replacement = {name: source.get(name) for name in ("id", "qty", "filled_qty", "updated_at", "package_mapping")}
            remaining = total - filled
            if remaining <= 0 or remaining % 1:
                raise ValueError("Package valuation requires remaining whole strategy units")
            inputs, ticks = [], []
            for leg in sorted(terms["legs"], key=lambda item: item["symbol"]):
                source = self.quote_sources.get(leg["symbol"])
                actual = self.observations.get(leg["symbol"], {})
                tick = self.cache.quote_tick(InstrumentId.from_str(leg["instrument_id"]))
                if (not source or actual.get("error") or tick is None or source["contract_sha256"] != leg["option_contract"]["sha256"]
                        or source["value"]["feed"] != startup.get("option_feed") or actual.get("market_feed") != startup.get("option_feed")
                        or self.option_metadata.get(leg["symbol"], {}).get("sha256") != source["contract_sha256"]
                        or hashlib.sha256(source["raw_response"].encode()).hexdigest() != source["value"]["raw_response_sha256"]
                        or package_valuation_key(actual.get("raw_quote")) != source["value"]["raw_quote_sha256"]):
                    raise ValueError("Actual package leg contract/quote receipt is unavailable or changed")
                raw = actual["raw_quote"]
                if (any(field not in raw for field in ("bp", "ap", "bs", "as", "t"))
                        or any(getattr(tick, field).as_decimal() != Decimal(str(raw[name])) for field, name in
                            (("bid_price", "bp"), ("ask_price", "ap"), ("bid_size", "bs"), ("ask_size", "as")))
                        or timestamp(raw["t"]) != tick.ts_event):
                    raise ValueError("Cached native quote does not match actual leg prices, sizes and event time")
                values = {name: str(getattr(tick, name).as_decimal()) for name in ("bid_price", "ask_price", "bid_size", "ask_size")}
                values.update(ts_event=str(tick.ts_event), ts_init=str(tick.ts_init))
                if values != source["value"]["quote"]:
                    raise ValueError("Actual native leg quote capture differs from retained source generation")
                if source["value"]["source_receipt"] is None:
                    source["value"]["source_receipt"] = lifecycle.receipt("option-quote", "Actual Alpaca option quote source",
                        {"source": source["source"], "raw_response": source["raw_response"], "received_at": source["received_at"],
                         "raw_response_sha256": source["value"]["raw_response_sha256"]})
                proof = source["value"]["source_receipt"]
                path = (lifecycle.path.parent / proof["path"]).resolve()
                if not path.is_relative_to(lifecycle.path.parent.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != proof["sha256"]:
                    raise ValueError("Actual option quote receipt is missing or changed")
                actual["quote_source"] = copy.deepcopy(source["value"])
                inputs.append({**copy.deepcopy(source["value"]), "instrument_id": leg["instrument_id"], "contract_sha256": source["contract_sha256"],
                    "contract_id": leg["option_contract"]["raw"]["id"], "signed_ratio": int(leg["ratio_qty"]) * (1 if leg["side"] == "BUY" else -1),
                    "multiplier": str(package["multiplier"]), "currency": str(spread.quote_currency)})
                ticks.append(tick)
            settings = {"implementation": "nautilus_trader.data.aggregation.SpreadQuoteAggregator", "disable_vega_pricing": True,
                "update_interval_seconds": None, "historical": False, "rounding": "public spread instrument make_price/make_qty; IEEE754 upstream calculation"}
            captured = []

            def derived(tick):
                output_values = {name: str(getattr(tick, name).as_decimal()) for name in ("bid_price", "ask_price", "bid_size", "ask_size")}
                output_values.update(ts_event=str(tick.ts_event), ts_init=str(tick.ts_init), currency=str(spread.quote_currency))
                limits = self.package_native_limits(terms, spread, ticks, remaining, tick)
                material = {"version": "native-spread-valuation-v1", "status": "blocked" if limits["blockers"] else "available",
                    "terms_sha256": key, "instrument_id": str(spread.id), "native_epoch": native_epoch, "account_id": initial_account["id"],
                    "endpoint": endpoint, "source_generation": package_valuation_key(inputs), "inputs": inputs, "settings": settings,
                    "output": output_values, "output_sha256": package_valuation_key(output_values),
                    "quantity": {"approved_total": str(total), "remaining": str(remaining), "already_filled": str(filled),
                        "ancestor_offset": str(offset), "replacement_source": replacement}, "native_limits": limits}
                binding = package_valuation_key(material)
                prior = getattr(self, "valuation_receipts", {}).get(binding)
                receipt = prior or lifecycle.receipt("package-valuation", "Public native derived spread quote; not an observed executable package quote",
                    {"material": material, "binding_sha256": binding})
                path = (lifecycle.path.parent / receipt["path"]).resolve()
                if not path.is_relative_to(lifecycle.path.parent.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != receipt["sha256"]:
                    raise ValueError("Retained native valuation receipt is missing or changed")
                if not hasattr(self, "valuation_receipts"):
                    self.valuation_receipts = {}
                self.valuation_receipts[binding] = receipt
                envelope = {**material, "binding_sha256": binding, "receipt": receipt}
                self.spread_valuations[key] = envelope  # Bind provenance before public data processing.
                try:
                    DataEngine.process(retained_node[0].kernel.data_engine, tick)
                    current = self.cache.quote_tick(spread.id)
                    if current is None or native_dict(current) != native_dict(tick):
                        raise ValueError("Public native spread quote was not synchronously confirmed in cache")
                except Exception:
                    self.spread_valuations.pop(key, None)
                    raise
                captured.append(envelope)

            aggregator = SpreadQuoteAggregator(spread, derived, GreeksCalculator(self.cache, self.clock), self.clock,
                historical=False, update_interval_seconds=None, disable_vega_pricing=True)
            for tick in sorted(ticks, key=lambda item: (item.ts_init, str(item.instrument_id))):
                aggregator.handle_quote_tick(tick)
            if len(captured) != 1:
                raise ValueError("Public native spread aggregator did not produce one complete quote")
            return captured[0]

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

    def risk_snapshot(connected):
        result = {"source": "node.kernel.risk_engine public getters", "native_epoch": native_epoch,
                  "captured_at": datetime.now(UTC).isoformat(), "engine_version": __version__,
                  "status": "unavailable", "values": None}
        if not connected or retained_node[0] is None:
            return {**result, "reason": "A connected native node is required"}
        try:
            risk = retained_node[0].kernel.risk_engine
            submit, modify = risk.max_order_submit_rate(), risk.max_order_modify_rate()
            result.update(status="available", values={"bypassed": bool(risk.is_bypassed),
                "trading_state": enum_name(risk.trading_state),
                "submit_rate": {"commands": submit[0], "interval_ns": str(pd.Timedelta(submit[1]).value)},
                "modify_rate": {"commands": modify[0], "interval_ns": str(pd.Timedelta(modify[1]).value)},
                "max_notional_per_order": [{"instrument_id": str(instrument), "amount": str(amount) if amount is not None else None}
                    for instrument, amount in risk.max_notionals_per_order().items()],
                "notional_scope": "Empty means no configured per-instrument caps; null amount means explicitly disabled"})
        except (ValueError, TypeError, AttributeError, RuntimeError, OverflowError) as exc:
            result["reason"] = "Native risk getters unavailable (" + type(exc).__name__ + ")"
        return result

    def report_cell(value):
        if value is None or isinstance(value, (str, bool)):
            return value
        if isinstance(value, dict):
            return {str(key): report_cell(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [report_cell(item) for item in value]
        if pd.isna(value):
            return None
        if isinstance(value, (pd.Timestamp, datetime)):
            stamp = pd.Timestamp(value)
            return {"iso": stamp.isoformat(), "unix_ns": str(stamp.value)}
        if isinstance(value, (Decimal, Integral, Real)):
            if not isfinite(value):
                raise ValueError("Native table contains a nonfinite number")
            return str(value)
        raise TypeError("Unsupported native table cell: " + type(value).__name__)

    def native_report(node, kind):
        generators = {"orders": node.trader.generate_orders_report,
            "order_fills": node.trader.generate_order_fills_report, "fills": node.trader.generate_fills_report,
            "positions": node.trader.generate_positions_report,
            "account": lambda: node.trader.generate_account_report(account_id=account_id)}
        if not isinstance(kind, str) or kind not in generators:
            raise ValueError("Choose native report orders, order_fills, fills, positions or account")
        context = runtime_snapshot(node.cache, include_market_data=False)
        if context["status"] != "connected":
            raise ValueError("A connected native node is required to capture a native report")
        frame = generators[kind]()
        account_context = {"account_id": str(account_id) if account_id is not None else None, "broker_account_id": context["account"]["id"],
            "endpoint": context["endpoint"], "mode": context["connection_identity"]["observed_mode"]}
        lifecycles = []
        if kind == "positions":
            execution = clients["execution"]
            reports, sources = {}, {}
            source_orders = {row["id"]: row for row in observed.get("order_history", [])}
            for report in execution.fill_reports:
                reports.setdefault(execution_id(report.trade_id), []).append(report)
            for source in context["fills"]:
                sources.setdefault(execution_id(source.get("execution_id") or source["id"]), []).append(source)
            for snapshot, positions in ((False, node.cache.positions(account_id=account_id)),
                                        (True, node.cache.position_snapshots(account_id=account_id))):
                for position in positions:
                    raw, events, gaps = report_cell(native_dict(position)), [], []
                    identity = {**account_context, "position_id": str(position.id) if position.id is not None else None,
                        "instrument_id": str(position.instrument_id) if position.instrument_id is not None else None,
                        "opening_order_id": str(position.opening_order_id) if position.opening_order_id is not None else None,
                        "ts_opened": str(position.ts_opened) if position.ts_opened is not None else None}
                    for event in position.events:
                        fill_id = execution_id(event.trade_id) if event.trade_id is not None else None
                        matches, evidence = reports.get(fill_id, []), sources.get(fill_id, [])
                        matched, validated_source = False, None
                        if len(matches) == len(evidence) == 1:
                            try:
                                require_fill_match(matches[0], event)
                                validated_source = dict(evidence[0])
                                source_report = fill_report(validated_source, source_orders[validated_source["order_id"]], account_id, usd,
                                    time.time_ns(), endpoint=endpoint, account=execution.fee_model_account,
                                    linked=execution.recovery_fee_sources.get(fill_id))
                                require_fill_match(source_report, event)
                                matched = True
                            except (ValueError, KeyError, TypeError, ArithmeticError):
                                pass
                        if not matched:
                            gaps.append("Fill " + fill_id + ": capture lacks one exact native report and broker source match")
                        native_order = node.cache.order(event.client_order_id) if event.client_order_id is not None else None
                        order_state = native_dict(native_order) if native_order is not None else None
                        events.append({"fill_id": fill_id, "event_id": str(event.id) if event.id is not None else None,
                            "client_order_id": str(event.client_order_id) if event.client_order_id is not None else None,
                            "broker_order_id": str(event.venue_order_id) if event.venue_order_id is not None else None,
                            "account_id": str(event.account_id) if event.account_id is not None else None,
                            "instrument_id": str(event.instrument_id) if event.instrument_id is not None else None, "side": enum_name(event.order_side),
                            "quantity": str(event.last_qty.as_decimal()), "price": str(event.last_px.as_decimal()), "ts_event": str(event.ts_event),
                            "commission": None if event.commission is None else {"amount": str(event.commission.as_decimal()), "currency": str(event.commission.currency)},
                            "role": "entry_or_increase" if event.order_side == position.entry else "exit_or_reduce",
                            "order_as_of_capture": None if order_state is None else {key: order_state.get(key) for key in
                                ("type", "status", "quantity", "filled_qty", "order_list_id", "parent_order_id", "linked_order_ids", "ts_last")},
                            "source_matched": matched, "source": report_cell(validated_source or evidence[0]) if len(evidence) == 1 else None,
                            "source_receipt": (context.get("recovery_history") or {}).get("evidence")})
                    mark, unrealized, total = None, None, position.realized_pnl if position.is_closed else None
                    if position.is_open and not snapshot:
                        quote, trade = node.cache.quote_tick(position.instrument_id), node.cache.trade_tick(position.instrument_id)
                        if quote is not None:
                            price = quote.bid_price if enum_name(position.side) == "LONG" else quote.ask_price
                            tick, basis = quote, "cached_bid" if enum_name(position.side) == "LONG" else "cached_ask"
                        else:
                            tick, basis, price = trade, "cached_last_trade", trade.price if trade is not None else None
                        if price is not None:
                            mark = {"price": str(price.as_decimal()), "basis": basis, "ts_event": str(tick.ts_event), "ts_init": str(tick.ts_init)}
                            cached = getattr(clients.get("data"), "observations", {}).get(str(position.instrument_id).removesuffix(".ALPACA"), {})
                            mark.update(provider=cached.get("provider"), feed=cached.get("feed"), declared_feed=context.get("feed"),
                                source_snapshot=report_cell(cached.get("latestQuote" if quote is not None else "latestTrade")),
                                provenance="Cached source fields only; missing provider/feed remain unknown, declared feed is not publisher verification")
                            if tick.ts_event < position.ts_last:
                                gaps.append("Cached mark predates the latest position event; keep the dated native estimate, capture again before claiming complete net")
                            pnl = position.unrealized_pnl(price)
                            unrealized = {"amount": str(pnl.as_decimal()), "currency": str(pnl.currency)}
                            total = position.total_pnl(price)
                        else:
                            gaps.append("Open position has no dated cached mark; explicitly capture again after market data becomes available")
                    elif position.is_open:
                        gaps.append("Historical open snapshot has no same-time mark; unrealized PnL is not reconstructed")
                    if position.adjustments:
                        gaps.append("Native position includes non-fill adjustments; their source/cost attribution requires review")
                    lifecycles.append({"identity": identity, "is_snapshot": snapshot, "native_position": raw,
                        "events": events, "client_order_ids": [str(value) if value is not None else None for value in position.client_order_ids],
                        "broker_order_ids": [str(value) if value is not None else None for value in position.venue_order_ids],
                        "fill_ids": [execution_id(value) if value is not None else None for value in position.trade_ids],
                        "adjustment_ids": [str(value.id) for value in position.adjustments],
                        "realized_pnl": None if position.realized_pnl is None else {"amount": str(position.realized_pnl.as_decimal()), "currency": str(position.realized_pnl.currency)},
                        "native_total_pnl": None if total is None else {"amount": str(total.as_decimal()), "currency": str(total.currency)},
                        "unrealized_pnl": unrealized, "mark": mark,
                        "commissions": [{"amount": str(value.as_decimal()), "currency": str(value.currency)} for value in position.commissions()], "gaps": gaps})
        return {"report_kind": kind, "generator": "node.trader.generate_" + kind + "_report",
            "account_context": account_context, "position_lifecycles": lifecycles,
            "execution_profile": context["execution_profile"], "profile_transition": context["profile_transition"],
            "native_balance": context["native_balance"],
            "native_epoch": native_epoch, "captured_at": datetime.now(UTC).isoformat(), "engine_version": __version__,
            "cache_scope": "current_native_cache", "row_count": len(frame), "complete_table": True,
            "native_reconstruction": context.get("native_reconstruction", {}),
            "native_economics_verified": False,
            "index_names": list(frame.index.names), "index": [report_cell(value) for value in frame.index],
            "columns": [str(value) for value in frame.columns],
            "data": [[report_cell(value) for value in row] for row in frame.itertuples(index=False, name=None)],
            "reconciliation": context["reconciliation"], "recovery_coverage": context.get("recovery_history"),
            "persistence": context["persistence"], "fee_provenance": {
                "native_contract": context["native_contract"],
                "fill_sources": [{"fill_id": fill.get("id"), "actual_commission": fill.get("commission"),
                    "native_fee": fill.get("native_fee"), "native_application": fill.get("native_application")} for fill in context["fills"]]},
            "limitations": ["Native cached tables are separate from broker actual performance and simulations",
                "Margin total/free/locked is a declared equity/initial requirement diagnostic; not cash or spendable authority. Native Portfolio.equity adds unrealized PnL and is not broker equity.",
                "Reconstruction orders/fills, processing chronology, reduction PnL and modeled zero commissions are internal representations, not actual broker transactions/economics",
                "Complete table does not establish complete account history or resolved reconciliation",
                "Native modeled fees do not establish actual fees; absent actual commission remains unknown",
                "Numeric cells are strings; upstream floating-point values cannot regain lost precision"]}

    def runtime_snapshot(cache, *, include_market_data=True):
        account = cache.account(account_id)
        native_positions = [native_dict(p) for p in cache.positions_open()]
        native_orders = [order_snapshot(o) for o in cache.orders_open()]
        balance_total = account.balance_total(usd) if account is not None else None
        balance_locked = account.balance_locked(usd) if account is not None else None
        balance_free = account.balance_free(usd) if account is not None else None
        native_cash = str(balance_total.as_decimal()) if balance_total is not None and session_account_type == AccountType.CASH else None
        native_balance = {"total": None if balance_total is None else str(balance_total.as_decimal()),
            "locked": None if balance_locked is None else str(balance_locked.as_decimal()),
            "free": None if balance_free is None else str(balance_free.as_decimal()), "currency": "USD",
            "account_type": enum_name(session_account_type), "calculate_account_state": None if account is None else account.calculate_account_state,
            "balance_projection": copy.deepcopy(profile_transition.get("balance_projection"))}
        if account is not None and session_account_type == AccountType.MARGIN:
            margin = account.margin_for_currency(usd)
            native_balance["reported_margin"] = None if margin is None else {"initial": str(margin.initial.as_decimal()),
                "maintenance": str(margin.maintenance.as_decimal()), "currency": str(margin.currency)}
        execution = clients.get("execution")
        commands = execution.lifecycle.authority().database.read("commands", {})["data"].get("commands", {}) if execution and hasattr(execution, "lifecycle") else {}
        reconstruction = execution.lifecycle.authority().database.read("commands", {})["data"].get("native_reconstructions", {}) if execution and hasattr(execution, "lifecycle") else {}
        reconstruction = {key: value for key, value in reconstruction.items() if value.get("native_epoch") == native_epoch}
        reconciliation = reconcile(observed, native_positions, native_orders, native_cash, commands=commands, native_epoch=native_epoch,
            native_balance=native_balance)
        if any(value.get("state") != "confirmed" for value in reconstruction.values()):
            reconciliation["gaps"].append("Native representation is unresolved; use explicit stop/start to rebuild retained actuals and fresh broker state")
            reconciliation["status"] = "incomplete"
        for position in reconciliation["positions"]:
            record = reconstruction.get(position.get("symbol", "") + ".ALPACA")
            if record:
                position["native_reconstruction"] = record
                reconciliation["reporting_gaps"].append("Native modeled chronology/PnL/fees are not actual broker economics: " + position["symbol"])
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
                if parent.get("package_parent_id") or parent.get("package_terms"):
                    reports = [report for report in execution.fill_reports if str(report.venue_order_id) == parent["id"] and execution_id(report.trade_id) == execution_id(fill["id"])]
                    proven = len(reports) == 1 and execution.package_leg_event(reports[0]) is not None
                else:
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
        for symbol in (dict.fromkeys(desired + [p["symbol"] for p in observed["positions"] + observed["orders"] if p.get("symbol") and p.get("asset_class") in {"us_equity", "us_option"}]) if include_market_data else ()):
            observation = getattr(data, "observations", {}).get(symbol, {})
            instrument = cache.instrument(instrument_id(symbol))
            quote = cache.quote_tick(instrument_id(symbol))
            trade = cache.trade_tick(instrument_id(symbol))
            prices[symbol] = {**observation,
                "option_contract": getattr(data, "option_metadata", {}).get(symbol),
                "instrument": native_dict(instrument) if instrument else None,
                "fractionable": getattr(data, "asset_metadata", {}).get(symbol, {}).get("fractionable"),
                "asset_observed_at": getattr(data, "asset_observed_at", None),
                "session_eligibility": {**{key: value if type(value := getattr(data, "asset_metadata", {}).get(symbol, {}).get(key)) is bool else None
                    for key in ("overnight_tradable", "overnight_halted", "fractionable", "fractional_eh_enabled")},
                    "observed_at": getattr(data, "asset_observed_at", None), "source": "/v2/assets?status=active&asset_class=us_equity"},
                "trade_supported": getattr(data, "asset_metadata", {}).get(symbol, {}).get("tradable") is True
                    and getattr(data, "asset_metadata", {}).get(symbol, {}).get("status") == "active",
                "quote": native_dict(quote) if quote and observation.get("latestQuote") else None,
                "trade": native_dict(trade) if trade and observation.get("latestTrade") else None}
        connected = len(clients) == 2 and all(c.is_connected for c in clients.values()) and observed.get("account") is not None
        return {"status": "error" if observed["error"] else "connected" if connected else "starting",
            "execution_profile": execution_profile, "profile_transition": profile_transition,
            "connection_session": native_epoch,
            "observation_generation": observed.get("observation_generation"),
            "connection_identity": {"configured_mode": connection.mode, "endpoint": endpoint,
                "stream_endpoint": connection.stream_url, "account_id": initial_account["id"],
                "observed_mode": connection.mode if connected and not observed["error"] else "unknown",
                "mode_basis": "Official trading origin plus authenticated account observation", "credentials_pinned": True},
            "native_risk": risk_snapshot(connected and not observed["error"]),
            "version": __version__, "native_epoch": native_epoch, "worker_pid": os.getpid(), "persistence": dict(persistence_status),
            "broker_observation": observed.get("broker_observation", {}),
            "native_import_gap": observed.get("native_import_gap"),
            "native_contract": {"source_commit": manifest["source_commit"], "wheel_sha256": manifest["official_wheel"]["sha256"],
                "files_match_reviewed_wheel": True, "synthetic_recovery": False,
                "actual_missing_commission_preserved": True, "commission_model_scope": "verified_direct_paper_us_equity_and_standard_equity_options_only",
                "limitation": "Actual fill identity and economics are required; documented direct-paper equity commission may be modeled separately from unknown actual costs",
                "blockers": list(getattr(clients.get("execution"), "reconciliation_blockers", ["Initial observation pending"]))},
            "updated_at": datetime.now(UTC).isoformat(),
            "account": observed["account"],
            "account_configuration": observed.get("account_configuration", {"disable_overnight_trading": None,
                "observed_at": None, "source": "/v2/account/configurations", "error": "Not observed"}),
            "positions": reconciliation["positions"], "orders": reconciliation["orders"], "native_reconstruction": reconstruction,
            "fills": reconciliation["fills"], "reconciliation": reconciliation,
            "account_at": observed["account_at"], "market_open": observed["market_open"],
            "nautilus_cash": native_cash,
            "native_balance": native_balance,
            "market_data": prices, "symbols": list(desired), "feed": "iex", "option_feed": startup.get("option_feed"),
            "package_valuations": copy.deepcopy(getattr(data, "spread_valuations", {})),
            "recovery_history": observed.get("recovery_history"),
            "native_recovery_action": observed.get("native_recovery_action"),
            "native_deliveries": clients["execution"].lifecycle.delivery_summary() if "execution" in clients and hasattr(clients["execution"], "lifecycle") else [],
            "trade_stream": dict(execution.lifecycle.stream_status) if execution and hasattr(execution, "lifecycle") else {"state": "not_started"},
            "prices_checked_at": getattr(data, "checked_at", None),
            "error": observed["error"], "read_only": False, "endpoint": endpoint}


    class Execution(ExecutionClient):
        def prepare_package_valuation(self, terms):
            return clients["data"].prepare_package(terms)

        async def _connect(self):
            self.execution_profile = execution_profile
            self.observation_lock = asyncio.Lock()
            self.observation_dirty = False
            self.reconstruction_context = None
            self.history_cache = None
            self.recovery_fee_sources = {}
            self.last_observation = 0
            self.lifecycle = ExecutionLifecycle(self, authority_database, sys.argv[1], lambda: runtime_snapshot(self.cache), lambda: getattr(clients["data"], "asset_metadata", {}), native_epoch=native_epoch, connection=connection)
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
                async def source(path):
                    result = await asyncio.to_thread(transport.read_receipt, path)
                    return result, path
                account_source, position_source, order_source, clock = await asyncio.gather(
                    source("/v2/account"), source("/v2/positions"), source("/v2/orders?status=open&limit=500&nested=true"), get("/v2/clock"))
                self.snapshot_sources = dict(zip(("account", "positions", "orders"), (account_source, position_source, order_source), strict=True))
                account, positions, orders = (item[0]["data"] for item in (account_source, position_source, order_source))
                observed["source_receipts"] = {name: {"raw_sha256": hashlib.sha256(result["raw"]).hexdigest(), "received_at": result["received_at"], "path": path}
                    for name, (result, path) in self.snapshot_sources.items()}
                observed["observation_generation"] = str(uuid4())
                open_response_count = len(orders)
                if account["id"] != initial_account["id"]:
                    raise ValueError("Broker account identity changed; restart with the intended account")
                observed.update(account=dict(account), account_at=datetime.now(UTC).isoformat(), positions=positions,
                    orders=orders, raw_observation={"account": copy.deepcopy(account), "positions": copy.deepcopy(positions), "orders": copy.deepcopy(orders), "clock": copy.deepcopy(clock),
                        "account_id": account["id"], "source": "Alpaca Trading API", "observed_at": timestamp_initial},
                    market_open=clock["is_open"], error=None,
                    broker_observation={"account_available": True, "positions_complete": True,
                        "orders_complete": open_response_count < 500, "source": "Alpaca Trading API", "observed_at": timestamp_initial})
                retain_observation()
                refreshed_profile = native_profile_transition(execution_profile, account, endpoint=endpoint, native_epoch=native_epoch,
                    source_receipt=observed["source_receipts"]["account"])
                refreshed_profile["native_account_type"] = enum_name(session_account_type)
                profile_transition.clear()
                profile_transition.update(refreshed_profile)
                observed["balance_projection"] = copy.deepcopy(profile_transition.get("balance_projection"))
                if execution_profile == "bounded_risk_spread_v1" and not profile_transition["eligibility"]["eligible"]:
                    self.reconciliation_blockers = profile_transition["eligibility"]["blockers"]
                    observed["native_import_gap"] = "; ".join(self.reconciliation_blockers)
                    retain_observation()
                    return
                commands = self.lifecycle.authority().database.read("commands", {})["data"].get("commands", {})
                orders, unsupported_orders = observed_orders(orders, commands.values())
                option_symbols = [row["symbol"] for row in positions + orders if row.get("asset_class") == "us_option" and not row.get("package_terms")]
                await clients["data"].load_options(option_symbols)
                clients["data"].register(option_symbols)
                for row in positions + orders:
                    if row.get("asset_class") == "us_option" and not row.get("package_terms"):
                        row["option_contract"] = clients["data"].option_metadata.get(row["symbol"])
                def unsupported_position(row):
                    try:
                        broker_position_quantity(row)
                        return (row.get("asset_class") not in {"us_equity", "us_option"}
                            or row.get("asset_class") == "us_option" and (not row.get("option_contract")
                                or row.get("side") == "short" and profile_transition.get("native_account_type") != "MARGIN"))
                    except (ArithmeticError, ValueError, TypeError, KeyError):
                        return True
                unsupported_positions = [row for row in positions if unsupported_position(row)]
                for row in unsupported_positions:
                    row.update(import_error="Position is observation-only; native equity mapping unavailable", exposure_status="unknown")
                observed["unsupported_orders"] = unsupported_orders
                observed["unsupported_exposure"] = {"status": "unknown" if unsupported_orders or unsupported_positions else "none_observed",
                    "orders": unsupported_orders, "positions": unsupported_positions, "account_id": account["id"],
                    "observed_at": timestamp_initial, "commitment": None}
                observed["orders"] = orders + unsupported_orders
                retain_observation()
                try:
                    config = await asyncio.to_thread(transport.read, "/v2/account/configurations")
                    value = config.get("disable_overnight_trading")
                    observed["account_configuration"] = {"disable_overnight_trading": value if type(value) is bool else None,
                        "observed_at": datetime.now(UTC).isoformat(), "source": "/v2/account/configurations", "error": None}
                except (HTTPError, URLError, TimeoutError, ValueError, TypeError, AttributeError) as exc:
                    observed["account_configuration"] = {"disable_overnight_trading": None, "observed_at": None,
                        "source": "/v2/account/configurations", "error": "Configuration observation unavailable (" + type(exc).__name__ + ")"}
                self.fee_model_account = account
                commands = self.lifecycle.authority().database.read("commands", {})["data"].get("commands", {})
                current_symbols = {row["symbol"] for row in positions + orders if row.get("symbol") and row.get("asset_class") in {"us_equity", "us_option"}}
                current_symbols.update(str(row.instrument_id).removesuffix(".ALPACA") for row in [*self.cache.positions_open(), *self.cache.orders_open()])
                current_symbols.update(row["symbol"] for row in commands.values() if row.get("account_id") == account["id"]
                    and (row.get("state") not in {"filled", "canceled", "rejected", "expired", "not_sent"} or row.get("native_pending_commitment")))
                current_symbols.update(leg["symbol"] for command in commands.values() if is_package(command.get("terms", {}))
                    for leg in command["terms"]["legs"])
                gaps, fills = [], []
                if unsupported_orders or unsupported_positions:
                    gaps.append("Unsupported broker exposure retained; commitments and native reconciliation remain unknown")
                if open_response_count == 500:
                    gaps.append("Open-order response reached the provider limit; completeness is unverified")
                fees = {}
                try:
                    collection_account = account
                    fills, fees, self.history_cache = await collect_history(self.lifecycle, collection_account, timestamp_initial, self.history_cache)
                    cutoff = timestamp(self.history_cache["from"])
                    observed["recovery_history"] = {key: value for key, value in self.history_cache.items() if key != "activities"}
                    observed["option_lifecycle"] = self.history_cache.get("option_lifecycle", [])
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
                    "long_market_value", "multiplier", "shorting_enabled", "initial_margin", "maintenance_margin", "options_approved_level",
                    "options_trading_level", "options_buying_power", "non_marginable_buying_power", "account_blocked", "trade_suspended_by_user")},
                    account_at=datetime.now(UTC).isoformat(), positions=positions, orders=[row for row in orders if row["status"] in LIVE] + unsupported_orders,
                    fills=fills, market_open=clock["is_open"], gaps=gaps, lookback_start=cutoff, error=None,
                    broker_observation={"account_available": True, "positions_complete": True,
                        "orders_complete": open_response_count < 500, "source": "Alpaca paper Trading API",
                        "observed_at": datetime.now(UTC).isoformat()})
                if strategy_holder[0] is not None and strategy_holder[0].is_running:
                    strategy_holder[0].sync_markets()
                clients["data"].wake.set()
                retain_observation()
                if (account["status"] != "ACTIVE" or account["currency"] != "USD"
                        or session_account_type == AccountType.CASH and (Decimal(account.get("multiplier", "0")) != 1 or account.get("shorting_enabled"))):
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
                if native_account is None:
                    balances, margins = reported_margin_projection(profile_transition["balance_projection"]) if session_account_type == AccountType.MARGIN else ([AccountBalance(cash, Money(0, usd), cash)], [])
                    self.generate_account_state(balances, margins, True, captured, info={"balance_projection": profile_transition.get("balance_projection")})
                self.position_reports, self.order_reports, self.fill_reports = [], [], []
                by_order = {row["id"]: row for row in orders}
                native_fills = {}
                for order in self.cache.orders():
                    if "RECONCILIATION" in (order.tags or []) or "atomic_option_package" in (order.tags or []):
                        continue  # Internal representation is never recovered as an actual broker execution.
                    if str(order.instrument_id).removesuffix(".ALPACA") not in current_symbols:
                        continue
                    for event in order.events:
                        if isinstance(event, OrderFilled) and order_account_binding(order) is not None:
                            identity = execution_id(event.trade_id)
                            if identity in native_fills:
                                raise ValueError("Duplicate retained native trade identity")
                            native_fills[identity] = event
                for position in [*self.cache.positions(), *self.cache.position_snapshots()]:
                    for event in position.events:
                        if isinstance(event, OrderFilled) and "-LEG-" in str(event.client_order_id) and event.account_id == account_id:
                            identity = execution_id(event.trade_id)
                            if identity in native_fills:
                                require_fill_match(retained_fill_report(event, captured), native_fills[identity])
                            native_fills[identity] = event
                parent_ids = {fill["order_id"] for fill in scoped_fills} | {str(event.venue_order_id) for event in native_fills.values()}
                pending = set(parent_ids) | set(by_order)
                pending.update(identity for command in commands.values() if command.get("terms", {}).get("exit_plan")
                               and command["symbol"] in current_symbols
                               for identity in command.get("broker_order_ids", []))
                pending.update(identity for command in commands.values() if is_package(command.get("terms", {}))
                    for identity in command.get("broker_order_ids", []))
                visited = set()
                while pending:
                    identity = pending.pop()
                    if identity in visited:
                        continue
                    visited.add(identity)
                    if identity not in by_order:
                        response = await asyncio.to_thread(self.lifecycle.transport.read_receipt, "/v2/orders/" + identity + "?nested=true")
                        self.lifecycle.receipt("native-recovery", "Alpaca fill-parent/replacement order", {"raw_response": response["raw"].decode()})
                        if response["data"].get("id") != identity:
                            raise ValueError("Fetched order identity differs")
                        supported, unsupported = observed_orders([response["data"]], commands.values())
                        if unsupported:
                            unsupported_orders.extend(unsupported)
                            gaps.append("Unsupported recovery order retained; exposure and commitments are unknown")
                            continue
                        for member in supported:
                            by_order[member["id"]] = member
                            if member["id"] not in visited:
                                pending.add(member["id"])
                    pending.update(value for value in (by_order[identity].get("replaces"), by_order[identity].get("replaced_by")) if value and value not in visited)
                self.lifecycle.bind_group(list(by_order.values()))
                commands = self.lifecycle.authority().database.read("commands", {})["data"].get("commands", {})
                for row in by_order.values():
                    if row.get("package_terms"):
                        from _tradingagents_native_adapter.native_types import OptionSpread
                        clients["data"]._handle_instrument(OptionSpread(row["package_terms"], captured))
                        if row.get("replaces"):
                            from _tradingagents_native_adapter.alpaca_reports import (
                                package_replacement_binding,
                            )

                            ancestors, parent = [], row
                            while parent.get("replaces"):
                                predecessor = by_order[parent["replaces"]]
                                if predecessor.get("replaced_by") != parent["id"] or predecessor["id"] in {item["id"] for item in ancestors}:
                                    raise ValueError("Package replacement chain is cyclic or unconfirmed")
                                prior, current = predecessor["package_terms"], row["package_terms"]
                                if (any(prior.get(key) != current.get(key) for key in ("legs", "instrument_id", "order_type"))
                                        or prior.get("execution_profile", "long_only") != current.get("execution_profile", "long_only")):
                                    raise ValueError("Package replacement changed immutable members or pricing intent")
                                predecessor["native_replacement_verified"] = True
                                ancestors.append(predecessor)
                                parent = predecessor
                            row["native_replacement_quantity_binding"] = package_replacement_binding(row, ancestors, scoped_fills, observed["recovery_history"])
                        self.lifecycle.bind_package(row)
                        continue
                    if row.get("package_parent_id"):
                        continue
                    if row.get("asset_class") == "us_option":
                        if row["symbol"] not in clients["data"].option_metadata:
                            await clients["data"].load_options([row["symbol"]])
                            clients["data"].register([row["symbol"]])
                        row["option_contract"] = clients["data"].option_metadata.get(row["symbol"])
                    chain, root = set(), row
                    while root.get("replaces"):
                        if root["id"] in chain:
                            raise ValueError("Cyclic replacement chain")
                        chain.add(root["id"])
                        predecessor = by_order[root["replaces"]]
                        if (predecessor.get("replaced_by") != root["id"] or predecessor.get("status") != "replaced"
                                or any(predecessor.get(key) != root.get(key) for key in ("symbol", "side", "type", "asset_class", "position_intent"))
                                or root["type"] != "market" and root.get("asset_class") != "us_option" and Decimal(root["filled_qty"]) < Decimal(predecessor["filled_qty"])
                                or timestamp(root["created_at"]) < timestamp(predecessor["created_at"])):
                            raise ValueError("Replacement chain identity, economics or chronology differs")
                        predecessor["native_replacement_verified"] = True
                        root = predecessor
                    bound = next((command for command in commands.values() if root["id"] in command.get("broker_order_ids", [])
                                  and command.get("linked_exit")), None)
                    row["native_client_order_id"] = bound["native_client_order_id"] if bound else row["client_order_id"] if row["type"] == "market" or row.get("asset_class") == "us_option" else root["client_order_id"]
                    if bound:
                        row["native_child_order_binding"] = {"source": "broker_nested_group", "broker_order_id": row["id"],
                            "broker_client_order_id": row["client_order_id"], "native_client_order_id": row["native_client_order_id"],
                            "parent_order_id": row.get("group_parent_id")}
                    if (row["type"] == "market" or row.get("asset_class") == "us_option") and row.get("replaces"):
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
                rows = positions + list(by_order.values()) + [
                    {**fill, "symbol": fill.get("symbol") or by_order.get(fill.get("order_id"), {}).get("symbol"),
                     "asset_class": by_order.get(fill.get("order_id"), {}).get("asset_class")}
                    for fill in scoped_fills if fill.get("symbol") in current_symbols or fill.get("order_id") in by_order]
                for row in rows:
                    if row.get("asset_class") == "us_equity":
                        try:
                            fractional = any(equity_quantity(row.get(key, "0"), zero=True) % 1 for key in ("qty", "filled_qty"))
                        except ValueError:
                            fractional = False
                        clients["data"].register([row["symbol"]], observed=True, fractional_observation=fractional)
                unique_fills = {}
                for fill in scoped_fills:
                    identity = execution_id(fill.get("execution_id") or fill.get("id"))
                    if not identity or identity in unique_fills and unique_fills[identity] != fill:
                        gaps.append("Missing or conflicting historical fill identity; original observation retained")
                    else:
                        unique_fills[identity] = fill
                for kind, source, convert, target in (
                    ("position", positions, lambda r: position_report(r, account_id, captured), self.position_reports),
                    ("order", [row for row in by_order.values() if not row.get("package_parent_id")], lambda r: order_report(r, account_id, captured), self.order_reports),
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
                            baseline = self.lifecycle.reconstruction(str(row.get("symbol")) + ".ALPACA") if kind == "fill" else None
                            if baseline and baseline["state"] == "confirmed":
                                self.lifecycle.retain_reconstruction({**baseline, "state": "reconstruction_required", "reason": str(exc),
                                    "new_actual_fill": copy.deepcopy(row), "new_actual_history_receipt": observed.get("recovery_history", {}).get("evidence")})
                reported_ids = {str(report.trade_id) for report in self.fill_reports}
                for identity, event in native_fills.items():
                    if identity not in reported_ids:
                        if str(event.venue_order_id) not in by_order:
                            gaps.append("Retained fill parent order is unavailable: " + identity)
                        else:
                            self.fill_reports.append(retained_fill_report(event, captured))
                for report in self.order_reports:
                    parent = by_order[str(report.venue_order_id)]
                    if parent.get("package_terms"):
                        for member in parent["package_members"]:
                            reported = sum((fill.last_qty.as_decimal() for fill in self.fill_reports
                                if str(fill.venue_order_id) in {member["id"], parent["id"]} and str(fill.instrument_id) == member["symbol"] + ".ALPACA"), Decimal(0))
                            if reported != report.filled_qty.as_decimal() * Decimal(member["package_ratio_qty"]):
                                gaps.append("Package " + parent["id"] + ": actual leg executions do not explain strategy units")
                        continue
                    chain = {parent["id"]}
                    while parent.get("replaces") and parent["type"] != "market" and parent.get("asset_class") != "us_option":
                        parent = by_order[parent["replaces"]]
                        chain.add(parent["id"])
                    reported = sum((f.last_qty.as_decimal() for f in self.fill_reports if str(f.venue_order_id) in chain), Decimal(0))
                    if reported != report.filled_qty.as_decimal():
                        gaps.append(f"Order {report.venue_order_id}: real executions do not explain cumulative fills; residual inference is disabled")
                # A complete position response is authoritative for previously known symbols now absent.
                known = {p.instrument_id for p in self.cache.positions_open()}
                known.update(r.instrument_id for r in self.order_reports if not by_order[str(r.venue_order_id)].get("package_terms"))
                present_symbols = {row.get("symbol") for row in positions}
                present = {identity for identity in known if str(identity).removesuffix(".ALPACA") in present_symbols}
                for missing in known - present:
                    self.position_reports.append(PositionStatusReport(account_id, missing, PositionSide.FLAT,
                        Quantity.from_str("0"), captured, captured))
                observed["order_history"] = list(by_order.values())
                observed["orders"] = [row for row in by_order.values() if row["status"] in LIVE] + unsupported_orders
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
                self.observation_dirty = False
                retain_observation()

        def record_unsupported_event(self, row, reference):
            observed.setdefault("unsupported_event_receipts", []).append(reference)
            observed["unsupported_exposure"] = {**observed.get("unsupported_exposure", {}), "status": "unknown",
                "commitment": None, "latest_event": reference, "account_id": initial_account["id"]}
            if row.get("id"):
                retained = {**copy.deepcopy(row), "import_error": "Broker order is observation-only; native equity mapping unavailable",
                            "exposure_status": "unknown"}
                observed["orders"] = [item for item in observed["orders"] if item.get("id") != row["id"]] + [retained]
            reason = "Unsupported broker event retained; exposure and commitments are unknown"
            observed["gaps"] = list(dict.fromkeys(observed["gaps"] + [reason]))
            self.reconciliation_blockers = list(dict.fromkeys(self.reconciliation_blockers + [reason]))
            retain_observation()

        def require_complete_reports(self):
            if self.reconciliation_blockers:
                raise ValueError("Native reconciliation withheld: " + "; ".join(self.reconciliation_blockers))

        def _calculate_commission(self, instrument, last_qty, last_px, liquidity_side):
            context = self.reconstruction_context
            leg = (last_qty.as_decimal(), last_px.as_decimal())
            if context and str(instrument.id) == context["instrument_id"] and leg in context["legs"]:
                context["legs"].remove(leg)
                return Money(0, instrument.quote_currency)  # Explicit model only; never an actual fee claim.
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
            equity_quantity(str(quantity))
            equity_quantity(str(filled), zero=True)
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
                order = native_observation(strategy_holder[0].order_factory, row, {})
                self.cache.add_order(order, client_id=self.client_id)
            if (order.quantity.as_decimal() != quantity or order.instrument_id != predecessor.instrument_id or order.side != predecessor.side
                    or enum_name(order.order_type) != native_type(row["type"]) or enum_name(order.time_in_force) != row["time_in_force"].upper()
                    or row.get("asset_class") == "us_option" and "option_intent:" + row["position_intent"] not in (order.tags or [])):
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

        async def align_position(self, report, settled):
            from nautilus_trader.live.reconciliation import calculate_reconciliation_price
            instrument = self.cache.instrument(report.instrument_id)
            positions = self.cache.positions_open(instrument_id=report.instrument_id, account_id=report.account_id)
            if instrument is None or (instrument.info or {}).get("option_contract") and (report.signed_decimal_qty < 0 or any(position.side == PositionSide.SHORT for position in positions)):
                raise ValueError("Position reconstruction requires the supported instrument; short options remain unsupported")
            current = sum((position.signed_decimal_qty() for position in positions), Decimal(0))
            target = report.signed_decimal_qty
            weighted = [(position.quantity.as_decimal(), Decimal(str(position.avg_px_open))) for position in positions if position.avg_px_open]
            weight = sum((quantity for quantity, _ in weighted), Decimal(0))
            average = sum((quantity * value for quantity, value in weighted), Decimal(0)) / weight if weight else None
            basis = report.avg_px_open
            crossing = current * target < 0
            increasing = abs(target) > abs(current) or crossing
            if increasing and (basis is None or not basis.is_finite() or basis <= 0):
                raise ValueError("Opening/increasing reconstruction requires actual broker position basis; quotes/zero are not substituted")
            if not increasing and target and basis is None:
                basis = average
                report = PositionStatusReport(report.account_id, report.instrument_id, report.position_side, report.quantity,
                    report.ts_last, self.clock.timestamp_ns(), avg_px_open=basis)
            transitions = [(current, Decimal(0), average, None), (Decimal(0), target, None, basis)] if crossing else [(current, target, average, basis)]
            legs = []
            for start, end, old_basis, new_basis in transitions:
                price = calculate_reconciliation_price(current_position_qty=start, current_position_avg_px=old_basis,
                    target_position_qty=end, target_position_avg_px=new_basis, instrument=instrument)
                if price is None or price.as_decimal() <= 0:
                    raise ValueError("Native reconciliation price is unavailable; quote/zero fallback is prohibited")
                legs.append((abs(end - start), price.as_decimal()))
            prior = self.lifecycle.reconstruction(str(report.instrument_id))
            if prior and prior["state"] != "confirmed":
                raise ValueError("Unresolved native reconstruction requires explicit stop/start before rebuilding retained actuals and current broker state")
            before = {str(order.client_order_id) for order in self.cache.orders()}
            sources = {name: {**observed["source_receipts"][name], "receipt": self.lifecycle.receipt("native-reconstruction", "Broker snapshot source",
                {"path": path, "raw_response": result["raw"].decode(), "received_at": result["received_at"], "source_date": result["source_date"]})}
                for name, (result, path) in self.snapshot_sources.items()}
            payload = {"instrument_id": str(report.instrument_id), "state": "prepared", "represented_quantity": str(target),
                "previous_native_quantity": str(current), "observation_generation": observed["observation_generation"],
                "source_receipts": sources, "activity_receipt": observed.get("recovery_history", {}).get("evidence"),
                "option_lifecycle": observed.get("option_lifecycle", []), "model_processing_time": datetime.now(UTC).isoformat(),
                "actual_execution_ids_applied": sorted({str(item.trade_id) for item in self.fill_reports}), "native_order_ids": [], "native_trade_ids": [],
                "basis": {"kind": "broker_position_basis" if increasing else "modeled_reduction_basis", "price": str(price.as_decimal()),
                    "current_average": str(average) if average is not None else None, "target_average": str(basis) if basis is not None else None,
                    "actual_economics_verified": False}, "modeled_legs": [{"quantity": str(quantity), "price": str(value)} for quantity, value in legs],
                "commission": {"amount": "0", "currency": "USD", "modeled": True, "actual": None}}
            self.lifecycle.retain_reconstruction(payload)
            self.reconstruction_context = {"instrument_id": str(report.instrument_id), "legs": list(legs)}
            try:
                retained_node[0].kernel.exec_engine.reconcile_execution_report(report)
                await settled(lambda: sum((position.signed_decimal_qty() for position in self.cache.positions_open(
                    instrument_id=report.instrument_id, account_id=report.account_id)), Decimal(0)) == target)
                generated = [order for order in self.cache.orders() if str(order.client_order_id) not in before and "RECONCILIATION" in (order.tags or [])]
                payload.update(state="confirmed", native_order_ids=[str(order.client_order_id) for order in generated],
                    native_trade_ids=[str(event.trade_id) for order in generated for event in order.events if isinstance(event, OrderFilled)])
                if not payload["native_order_ids"] or not payload["native_trade_ids"]:
                    raise ValueError("Native reconstruction lacks retained generated identities")
                self.lifecycle.retain_reconstruction(payload)
            except Exception:
                self.lifecycle.retain_reconstruction({**payload, "state": "reconstruction_required"})
                raise
            finally:
                self.reconstruction_context = None

        def package_leg_event(self, report):
            matches = {}
            for position in [*self.cache.positions(), *self.cache.position_snapshots()]:
                for event in position.events:
                    if isinstance(event, OrderFilled) and execution_id(event.trade_id) == execution_id(report.trade_id):
                        require_fill_match(report, event)
                        matches[str(event.id)] = event
            if len(matches) > 1:
                raise ValueError("Duplicate actual package leg native execution")
            return next(iter(matches.values()), None)

        async def apply_package_control(self, order, report, row, settled):
            """Internal spread status only; actual leg fills alone establish economics."""
            events = [event for event in order.events if isinstance(event, OrderFilled)]
            if any(not str(event.trade_id).startswith("package-control:") for event in events):
                raise ValueError("Package control contains unqualified economic executions")
            prior = sum((event.last_qty.as_decimal() * event.last_px.as_decimal() for event in events), Decimal(0))
            delta = report.filled_qty.as_decimal() - order.filled_qty.as_decimal()
            target = report.avg_px * report.filled_qty.as_decimal() if report.avg_px is not None else Decimal(0)
            if delta < 0 or delta == 0 and target != prior:
                raise ValueError("Package cumulative quantity/net average was corrected; explicit recovery is required")
            if delta == 0:
                return
            if report.avg_px is None:
                raise ValueError("Actual package net average is unavailable for internal control representation")
            from _tradingagents_native_adapter.alpaca_reports import exact
            price = exact(Price.from_str, (target - prior) / delta)
            source = {"parent": row, "native_epoch": native_epoch, "model": "spread_control_only", "actual_execution": False,
                "actual_fee": None, "modeled_control_fee": "0", "quantity_delta": str(delta), "control_price": str(price)}
            reference = self.lifecycle.receipt("package-control", "INTERNAL spread units/status representation; not broker execution economics", source)
            trade_id = TradeId("package-control:" + reference["sha256"])
            self.generate_order_filled(order, report.venue_order_id, None, trade_id, Quantity.from_str(str(delta)),
                price, usd, Money(0, usd), LiquiditySide.NO_LIQUIDITY_SIDE, report.ts_last)
            await settled(lambda: any(isinstance(event, OrderFilled) and event.trade_id == trade_id for event in order.events))

        async def _apply_observation(self):
            """Apply actual identities and globally ordered fills through official native interfaces."""
            async with self.observation_lock:
                try:
                    self.require_complete_reports()
                    if self.observation_dirty:
                        raise ValueError("A real-time update crossed this source generation; fresh broker observation is required")
                    factory = strategy_holder[0].order_factory
                    parents = {row["id"]: row for row in observed.get("order_history", [])}
                    reports = {str(report.venue_order_id): report for report in self.order_reports}

                    async def settled(predicate):
                        for _ in range(20):
                            if predicate():
                                return
                            await asyncio.sleep(0.05)
                        raise ValueError("Official native event application has not been confirmed")

                    await settled(lambda: self.cache.account(account_id) is not None)
                    account_state = self.cache.account(account_id)
                    if account_state.type != session_account_type or account_state.calculate_account_state:
                        raise ValueError("Native session must retain the selected reported, noncalculated account mapping")

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
                                successor.trigger_price, False, timestamp(parents[identity]["created_at"]), venue_order_id_modified=True)
                            await settled(lambda: order.venue_order_id == successor.venue_order_id)

                    for report in self.order_reports:
                        if report.client_order_id is None:
                            raise ValueError("Broker order has no source client identity")
                        if parents[str(report.venue_order_id)].get("replaces") and enum_name(report.order_type) != "MARKET" and parents[str(report.venue_order_id)].get("asset_class") != "us_option" and not parents[str(report.venue_order_id)].get("package_terms"):
                            continue
                        order = self.cache.order(report.client_order_id)
                        if order is None:
                            row = parents[str(report.venue_order_id)]
                            order = native_observation(factory, row, parents)
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
                        member = parents[str(report.venue_order_id)]
                        if member.get("package_terms"):
                            matches = [leg for leg in member["package_members"] if leg["native_client_order_id"] == str(report.client_order_id)
                                and leg["symbol"] + ".ALPACA" == str(report.instrument_id)]
                            if len(matches) != 1:
                                raise ValueError("Actual parent-linked leg execution has no exact retained member")
                            member = matches[0]
                        if member.get("package_parent_id"):
                            parent = parents[member["package_parent_id"]]
                            control = self.cache.order(ClientOrderId(parent.get("native_client_order_id") or parent["client_order_id"]))
                            if control is None or order_account_binding(control) is None:
                                raise ValueError("Actual package leg has no account-bound parent control")
                            if self.package_leg_event(report) is not None:
                                continue
                            self.lifecycle.require_causal_fill(member, str(report.trade_id))
                            self.generate_package_leg_filled(control, report)
                            await settled(lambda: self.package_leg_event(report) is not None)
                            continue
                        order = self.cache.order(report.client_order_id)
                        if order is None or order_account_binding(order) is None:
                            raise ValueError("Real fill has no confirmed native account/order identity")
                        existing = [event for event in order.events if isinstance(event, OrderFilled) and execution_id(event.trade_id) == execution_id(report.trade_id)]
                        if existing:
                            if len(existing) != 1:
                                raise ValueError("Duplicate native execution identity")
                            require_fill_match(report, existing[0])
                            continue
                        self.lifecycle.require_causal_fill(parents[str(report.venue_order_id)], str(report.trade_id))
                        await advance(order, report)
                        self._send_fill_report(report)
                        await settled(lambda: any(isinstance(event, OrderFilled) and execution_id(event.trade_id) == execution_id(report.trade_id) for event in order.events))
                        event = next(event for event in order.events if isinstance(event, OrderFilled) and execution_id(event.trade_id) == execution_id(report.trade_id))
                        require_fill_match(report, event)
                    for report in self.order_reports:
                        row = parents[str(report.venue_order_id)]
                        if row.get("native_replacement_verified") and row["type"] != "market" and row.get("asset_class") != "us_option" and not row.get("package_terms"):
                            continue  # Confirmed successor supersedes only the old remainder.
                        order = self.cache.order(report.client_order_id)
                        if row.get("package_terms") and order is not None:
                            await self.apply_package_control(order, report, row, settled)
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
                        await settled(lambda order=order, report=report: order.status == report.order_status)
                    for report in self.position_reports:
                        quantity = sum((position.quantity.as_decimal() * (-1 if position.side == PositionSide.SHORT else 1)
                            for position in self.cache.positions_open(instrument_id=report.instrument_id)), Decimal(0))
                        expected = report.quantity.as_decimal() * (-1 if report.position_side == PositionSide.SHORT else 1)
                        if quantity != expected:
                            await self.align_position(report, settled)
                        self._send_position_status_report(report)
                    cash = Money.from_str(observed["account"]["cash"] + " USD")
                    balances, margins = reported_margin_projection(profile_transition["balance_projection"]) if session_account_type == AccountType.MARGIN else ([AccountBalance(cash, Money(0, usd), cash)], [])
                    self.generate_account_state(balances, margins, True, self.clock.timestamp_ns(), info={"balance_projection": profile_transition.get("balance_projection")})
                    await settled(lambda: self.cache.account(account_id) is not None and self.cache.account(account_id).balance_total(usd).as_decimal() == balances[0].total.as_decimal())
                    if self.cache.account(account_id).calculate_account_state:
                        raise ValueError("Reported native account unexpectedly calculates balances from modeled fills")
                    observed.pop("native_import_gap", None)
                    state = self.lifecycle.authority().database.read("commands", {})["data"]
                    observed["native_reconstruction"] = {key: value for key, value in state.get("native_reconstructions", {}).items() if value.get("native_epoch") == native_epoch}
                    linked_confirmed = self.lifecycle.confirm_linked_observations(list(parents.values()), observed.get("recovery_history", {}))
                    package_confirmed = self.lifecycle.confirm_package_observations(list(parents.values()), observed.get("recovery_history", {}))
                    if self.lifecycle.resolve_market_replacement_receipts() or linked_confirmed or package_confirmed:
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
                    if (row.get("type") == "market" or row.get("asset_class") == "us_option") and row.get("replaces") and not row.get("native_replacement_quantity_binding"):
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

        async def _submit_order_list(self, command):
            await self.lifecycle.submit_group(command, strategy_holder[0].order_factory)

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
                account_type=session_account_type, oms_type=OmsType.NETTING, base_currency=usd)
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

        def configure(self, symbols, option_feed=None):
            if option_feed is not None:
                if option_feed not in {"opra", "indicative"}:
                    raise ValueError("Choose an explicit supported option feed")
                if option_feed != startup.get("option_feed") and "data" in clients:
                    clients["data"].quote_sources.clear()
                    clients["data"].spread_valuations.clear()
                startup["option_feed"] = option_feed
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
                lifecycle.checked_fractional_terms(terms)
                if is_package(terms):
                    valuation = clients["data"].prepare_package(terms)
                    validate_package_valuation(valuation, terms)
                    if valuation["binding_sha256"] != durable.get("package_valuation_binding_sha256"):
                        raise ValueError("Package native valuation/caps changed since exact approval")
                if terms.get("exit_plan"):
                    self.submit_order_list(native_group(self.order_factory, terms, str(native_id)), params=params)
                else:
                    self.submit_order(native_order(self.order_factory, terms, str(native_id)), params=params)
            elif action == "cancel":
                order = self.cache.order(native_id)
                lifecycle.native_action_intent(identity, durable["pending_action"]["id"], order_snapshot(order), [str(event.id) for event in order.events])
                self.cancel_order(order, params=params)
            elif action == "replace":
                replacement = lifecycle.command(durable["pending_action"]["replacement_command_id"], sending=True)
                proposed = replacement["terms"]
                lifecycle.checked_fractional_terms(proposed)
                if is_package(proposed):
                    valuation = clients["data"].prepare_package(proposed)
                    validate_package_valuation(valuation, proposed)
                    if valuation["binding_sha256"] != replacement.get("package_valuation_binding_sha256"):
                        raise ValueError("Replacement native package valuation/caps changed since exact approval")
                order = self.cache.order(native_id)
                lifecycle.native_action_intent(identity, durable["pending_action"]["id"], order_snapshot(order), [str(event.id) for event in order.events])
                source = next(row for row in observed["orders"] if row["id"] == durable["pending_action"]["broker_order_id"])
                quantity = Decimal(proposed["quantity"]) - Decimal(str((source.get("native_replacement_quantity_binding") or {}).get("ancestor_filled_quantity", "0")))
                if proposed.get("asset_class") == "us_option" and proposed["time_in_force"] != durable["terms"]["time_in_force"]:
                    from nautilus_trader.core.uuid import UUID4
                    from nautilus_trader.execution.messages import ModifyOrder
                    # Local pending intent only: actual broker successor supplies the new native TIF.
                    execution = clients["execution"]
                    execution.generate_observed_pending(order, order.venue_order_id, "PENDING_UPDATE", execution.clock.timestamp_ns())
                    retained_node[0].kernel.risk_engine.execute(ModifyOrder(trader_id=self.trader_id, strategy_id=self.id,
                        instrument_id=order.instrument_id, client_order_id=order.client_order_id, venue_order_id=order.venue_order_id,
                        quantity=Quantity.from_str(str(quantity)), price=Price.from_str(proposed["limit_price"]) if proposed.get("limit_price") else None,
                        trigger_price=Price.from_str(proposed["stop_price"]) if proposed.get("stop_price") else None,
                        command_id=UUID4(), ts_init=self.clock.timestamp_ns(), params=params))
                    return
                self.modify_order(order, quantity=Quantity.from_str(str(quantity)),
                    price=Price.from_str(proposed["limit_price"]) if proposed["order_type"] in {"LIMIT", "STOP_LIMIT"} else None,
                    trigger_price=Price.from_str(proposed["stop_price"]) if proposed.get("stop_price") else None, params=params)
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
                if command.get("command") == "native_report":
                    reply["read_only"] = True
                    try:
                        reply["native_report"] = native_report(node, command.get("report_kind"))
                    except Exception as exc:
                        raise ValueError("Native report unavailable (" + type(exc).__name__ + "): " +
                            (str(exc) if isinstance(exc, ValueError) else "generation or serialization failed")) from None
                elif command.get("command") == "configure":
                    observer.configure(command["symbols"], command.get("option_feed"))
                elif command.get("command") == "package_valuation":
                    reply["package_valuation"] = clients["data"].prepare_package(command["terms"])
                elif command.get("command") == "refresh":
                    await clients["data"].refresh()
                    await clients["execution"]._query_account(None)
                    await clients["execution"]._apply_observation()
                elif command.get("command") == "dispatch":
                    observer.dispatch(command["command_id"], command.get("action", "submit"))
                    reply["queued_in_native_engine"] = True
                elif command.get("command") == "option_instruction":
                    await clients["execution"]._query_account(None)
                    await clients["execution"]._apply_observation()
                    await clients["execution"].lifecycle.dispatch_instruction(command["instruction_id"])
                    reply["instruction_request_processed"] = True
                elif command.get("command") == "reconcile_identity":
                    try:
                        await clients["execution"].lifecycle.reconcile_identity(command["command_id"])
                    except (HTTPError, URLError, TimeoutError) as exc:
                        detail = "HTTP " + str(exc.code) if isinstance(exc, HTTPError) else type(exc).__name__
                        reply.update(error="Identity lookup connection/provider failure (" + detail + "); uncertainty is preserved",
                                     failure_scope="connection_or_provider")
                else:
                    raise ValueError("Unsupported native command")
            except (ValueError, KeyError, TypeError) as exc:
                reply["error"] = str(exc)
            publish_once()
            output.write(json.dumps(reply, allow_nan=False) + "\n")

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
        publisher.add_done_callback(lambda task: None if task.cancelled() else handle.stop())
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
