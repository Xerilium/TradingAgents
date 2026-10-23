"""Isolated installed-v1 native saved-plan simulation; no broker imports or credentials."""

import importlib.metadata
import json
import math
import sys
from dataclasses import asdict
from decimal import Decimal

from evaluation import VERSION, digest, instant, validate_terms


def clean(value):
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def simulate(spec):
    installed_engine_version = importlib.metadata.version("nautilus_trader")
    if (spec.get("version") != VERSION or spec.get("engine_version") != "1.231.0"
            or installed_engine_version != "1.231.0"
            or digest({key: value for key, value in spec.items() if key != "spec_sha256"}) != spec.get("spec_sha256")
            or digest(spec["saved_terms"]) != spec["proposal"]["terms_sha256"]):
        raise ValueError("Native version or immutable simulation specification differs")
    from linked_orders import broker_payload, native_group, native_order
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.models import (
        FillModel,
        FixedFeeModel,
        LatencyModel,
        MakerTakerFeeModel,
    )
    from nautilus_trader.config import LoggingConfig, StrategyConfig
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.data import Bar, BarType
    from nautilus_trader.model.enums import AccountType, OmsType, OtoTriggerMode
    from nautilus_trader.model.identifiers import InstrumentId, Symbol, TraderId, Venue
    from nautilus_trader.model.instruments import Equity
    from nautilus_trader.model.objects import FIXED_PRECISION, Money, Price, Quantity
    from nautilus_trader.trading.strategy import Strategy

    terms, assumptions = spec["terms"], spec["assumptions"]
    validate_terms(terms)
    broker_payload(terms, "SIM-PLAN")  # Reuse exact supported term validation, with no transport.
    if terms["side"] != "BUY" or spec["starting_holdings"] or terms["time_in_force"] not in {"DAY", "GTC"}:
        raise ValueError("This native profile requires an empty portfolio and a BUY DAY/GTC plan")
    if terms["time_in_force"] == "DAY" and assumptions["latency_ns"] != 0:
        raise ValueError("DAY close-cancellation profile requires zero assumed latency")
    instrument_id = InstrumentId.from_str(terms["instrument_id"])
    if str(instrument_id) != terms["symbol"] + ".ALPACA":
        raise ValueError("Simulation instrument differs from the saved supported equity")
    venue = Venue("ALPACA")
    representation = spec["representation"]
    precision = representation["price_precision"]
    if type(precision) is not int or not 2 <= precision <= FIXED_PRECISION:
        raise ValueError(f"Source prices exceed installed native price precision maximum {FIXED_PRECISION}; no rounding is performed")
    instrument = Equity(instrument_id, Symbol(terms["symbol"]), USD, precision, Price.from_str(representation["price_increment"]),
                        Quantity.from_int(1), 0, 0)
    bar_type = BarType.from_str(str(instrument_id) + "-1-DAY-LAST-EXTERNAL")
    decision_ns = int(instant(spec["decision_at"]).timestamp()) * 1_000_000_000

    class PlanReplay(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig(manage_contingent_orders=False))
            self.submitted_at = None

        def on_start(self):
            self.subscribe_bars(bar_type)

        def on_bar(self, bar):
            if self.submitted_at is not None and bar.ts_event > self.submitted_at and terms["time_in_force"] == "DAY":
                self.cancel_all_orders(instrument_id)
            if self.submitted_at is None and bar.ts_event >= decision_ns:
                self.submitted_at = bar.ts_event
                if terms.get("exit_plan"):
                    self.submit_order_list(native_group(self.order_factory, terms, "SIM-PLAN"))
                else:
                    self.submit_order(native_order(self.order_factory, terms, "SIM-PLAN"))

    fee = Decimal(assumptions["fee_usd"])
    fee_model = FixedFeeModel(Money(fee, USD), charge_commission_once=assumptions["fee_per"] == "order") if fee else MakerTakerFeeModel()
    engine_config = BacktestEngineConfig(trader_id=TraderId("SIMULATION-001"),
                                        logging=LoggingConfig(bypass_logging=True))
    engine = BacktestEngine(engine_config)
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal(spec["starting_cash"]), USD)],
            base_currency=USD, allow_cash_borrowing=False, support_contingent_orders=True, oto_trigger_mode=OtoTriggerMode.FULL,
            fill_model=FillModel(prob_fill_on_limit=float(assumptions["limit_fill_probability"]),
                                 prob_slippage=float(assumptions["slippage_probability"]), random_seed=assumptions["random_seed"]),
            fee_model=fee_model, latency_model=LatencyModel(base_latency_nanos=assumptions["latency_ns"]),
            bar_execution=True, bar_adaptive_high_low_ordering=False, trade_execution=False)
        engine.add_instrument(instrument)
        bars = []
        for row in spec["bars"]:
            timestamp = int(instant(row["at"]).timestamp()) * 1_000_000_000
            bars.append(Bar(bar_type, *(Price.from_str(row[key]) for key in ("o", "h", "l", "c")),
                            Quantity.from_int(int(Decimal(row["v"]))), timestamp, timestamp))
        engine.add_data(bars)
        strategy = PlanReplay()
        engine.add_strategy(strategy)
        engine.run(start=spec["start_at"], end=spec["end_at"])
        reports = {name: json.loads(table.to_json(orient="split", date_format="iso", default_handler=str)) for name, table in {
            "orders": engine.trader.generate_orders_report(), "fills": engine.trader.generate_fills_report(),
            "positions": engine.trader.generate_positions_report(), "account": engine.trader.generate_account_report(venue)}.items()}
        analyzer = engine.portfolio.analyzer
        return clean({"kind": "simulation", "version": VERSION, "engine_version": installed_engine_version,
            "native_risk_config": engine_config.risk_engine.json_primitives(),
            "order_events": {str(order.client_order_id): [type(event).to_dict(event) for event in order.events]
                             for order in engine.cache.orders()},
            "status": "completed_with_limitations", "spec_sha256": spec["spec_sha256"], "proposal": spec["proposal"],
            "submitted_at_ns": strategy.submitted_at, "native_result": asdict(engine.get_result()), "reports": reports,
            "return_series_basis": "Native portfolio returns where available; native primary statistics can fall back to position returns",
            "portfolio_returns": {stamp.isoformat(): value for stamp, value in analyzer.portfolio_returns().items()},
            "benchmark": {"available": False, "reason": "No matching benchmark series selected in this simulation profile"},
            "assumptions": assumptions, "representation": representation, "currency_basis": spec["currency_basis"],
            "input_artifacts": spec["input_artifacts"], "limitations": spec["limitations"]})
    finally:
        engine.dispose()


if __name__ == "__main__":
    specification = json.load(sys.stdin)
    try:
        response = simulate(specification)
    except Exception as error:
        response = {"kind": "simulation", "status": "failed", "spec_sha256": specification.get("spec_sha256"),
                    "error": type(error).__name__ + ": " + str(error)}
    print(json.dumps(response, allow_nan=False, default=str))
