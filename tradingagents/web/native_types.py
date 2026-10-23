"""Model types and report signatures for the pinned official Nautilus v1 contract."""
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.model.identifiers import (AccountId, ClientId, ClientOrderId,
    InstrumentId, Symbol, TradeId, TraderId, Venue, VenueOrderId)
from nautilus_trader.model.enums import (AccountType, AggressorSide, LiquiditySide,
    OmsType, OrderSide, OrderStatus, OrderType, PositionSide, TimeInForce, AssetClass, OptionKind)
from nautilus_trader.model.objects import AccountBalance, Currency, MarginBalance, Money, Price, Quantity
from nautilus_trader.model.data import QuoteTick, TradeTick
from nautilus_trader.model.events import OrderFilled
from nautilus_trader.model.instruments import Equity as _Equity
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.instruments import OptionContract as _OptionContract
from nautilus_trader.model.instruments import OptionSpread as _OptionSpread
from nautilus_trader.execution import reports as _reports


def OptionContract(metadata, ts_init):
    from datetime import UTC, datetime

    from .linked_orders import option_contract
    raw = option_contract(metadata)
    expiry = int(datetime.fromisoformat(raw["expiration_date"]).replace(tzinfo=UTC).timestamp()) * 1_000_000_000
    observed = int(datetime.fromisoformat(metadata["received_at"].replace("Z", "+00:00")).timestamp() * 1_000_000_000)
    return _OptionContract(instrument_id=InstrumentId.from_str(raw["symbol"] + ".ALPACA"), raw_symbol=Symbol(raw["symbol"]),
        asset_class=AssetClass.EQUITY, currency=Currency.from_str("USD"), price_precision=2, price_increment=Price.from_str("0.01"),
        multiplier=Quantity.from_str(raw["size"]), lot_size=Quantity.from_str("1"), underlying=raw["underlying_symbol"],
        option_kind=OptionKind.CALL if raw["type"] == "call" else OptionKind.PUT, strike_price=Price.from_str(raw["strike_price"]),
        activation_ns=0, expiration_ns=expiry, ts_event=observed, ts_init=ts_init,
        info={"option_contract": metadata, "activation_time": None, "expiration_time": None,
              "native_time_semantics": "Activation=operational lower bound; expiry=UTC date carrier. Not listing/expiry instants; no native chains/Greeks/simulation.",
              "currency_basis": "US equity-option dollar premium product mapping; absent broker currency remains absent in raw metadata",
              "price_step_basis": "Cent representation only; ppind quoting tiers and conditional broker routing are separate"})


def reported_margin_projection(value):
    if (value.get("version") != "alpaca-paper-equity-initial-v1" or value.get("currency") != "USD"
            or value.get("calculate_account_state") is not False):
        raise ValueError("Identified noncalculated native margin projection is unavailable")
    from decimal import Decimal

    source, projected = value["source_fields"], value["derived"]
    if (Decimal(projected["total"]) != Decimal(str(source["equity"]))
            or Decimal(projected["locked"]) != Decimal(str(source["initial_margin"]))
            or Decimal(projected["free"]) != Decimal(str(source["equity"])) - Decimal(str(source["initial_margin"]))):
        raise ValueError("Declared margin projection differs from actual reported equity/initial requirement")
    def money(raw):
        amount = Decimal(str(raw))
        result = Money.from_str(format(amount, "f") + " USD")
        if not amount.is_finite() or result.as_decimal() != amount:
            raise ValueError("Actual margin balance is not exactly representable in native USD")
        return result
    balance = AccountBalance(money(projected["total"]), money(projected["locked"]), money(projected["free"]))
    margin = MarginBalance(money(source["initial_margin"]), money(source["maintenance_margin"]))
    return [balance], [margin]

def OptionSpread(terms, ts_init):
    from datetime import UTC, datetime

    from nautilus_trader.model.identifiers import new_generic_spread_id

    from .linked_orders import package_terms

    package = package_terms(terms)
    identity = new_generic_spread_id([(InstrumentId.from_str(leg["instrument_id"]),
        int(leg["ratio_qty"]) * (1 if leg["side"] == "BUY" else -1)) for leg in terms["legs"]])
    if str(identity) != package["instrument_id"]:
        raise ValueError("Public native spread identity differs from exact approved leg ratios")
    expiry = min(int(datetime.fromisoformat(raw["expiration_date"]).replace(tzinfo=UTC).timestamp()) * 1_000_000_000 for raw in package["contracts"])
    observed = max(int(datetime.fromisoformat(leg["option_contract"]["received_at"].replace("Z", "+00:00")).timestamp() * 1_000_000_000) for leg in terms["legs"])
    return _OptionSpread(instrument_id=identity, raw_symbol=identity.symbol, asset_class=AssetClass.EQUITY,
        currency=Currency.from_str("USD"), price_precision=2, price_increment=Price.from_str("0.01"),
        multiplier=Quantity.from_str(str(package["multiplier"])), lot_size=Quantity.from_str("1"), underlying=package["underlying"],
        strategy_type="atomic_bounded_risk_option_spread" if terms.get("execution_profile") == "bounded_risk_spread_v1" else "atomic_long_option_package",
        activation_ns=0, expiration_ns=expiry, ts_event=observed, ts_init=ts_init,
        info={"package_legs": terms["legs"], "execution_profile": terms.get("execution_profile", "long_only"), "internal_control": True, "broker_symbol": None,
              "native_time_semantics": "Earliest leg UTC date carrier only; not a broker expiry instant or exercise schedule",
              "economics": "Actual leg executions only; parent control never establishes leg prices, fees or positions",
              "price_step_basis": "Cent package representation; not an inferred leg quoting tier"})


def Equity(instrument_id, raw_symbol, currency, price_precision, price_increment, ts_event, ts_init, *, lot_size,
           fractional_precision=False, info=None):
    legacy = _Equity(instrument_id, raw_symbol, currency, price_precision, price_increment, lot_size, ts_event, ts_init, info=info)
    if not fractional_precision:
        return legacy
    values = Instrument.base_to_dict(legacy)
    values.update(size_precision=9, size_increment="0.000000001", info={**(info or {}),
        "fractional_quantity_contract": {"precision": 9, "increment": "0.000000001",
            "source": "https://docs.alpaca.markets/us/docs/fractional-trading",
            "basis": "Reviewed broker precision contract, not fields supplied by asset metadata; native equity defaults retain EQUITY/SPOT/USD/multiplier1"}})
    return Instrument.base_from_dict(values)

def PositionStatusReport(*args, **kwargs):
    return _reports.PositionStatusReport(*args[:4], UUID4(), *args[4:], **kwargs)

def OrderStatusReport(*args, **kwargs):
    return _reports.OrderStatusReport(*args[:9], UUID4(), *args[9:], **kwargs)

def FillReport(*args, **kwargs):
    return _reports.FillReport(*args[:9], UUID4(), *args[9:], **kwargs)

def ExecutionMassStatus(client_id, account_id, venue, ts_init):
    return _reports.ExecutionMassStatus(client_id, account_id, venue, UUID4(), ts_init)

def native_dict(value):
    return Instrument.base_to_dict(value) if type(value) is Instrument else type(value).to_dict(value)


def enum_name(value):
    return value.name


def native_order_client_matches(order, client):
    routed = client.cache.client_id(order.client_order_id)
    return order.instrument_id.venue == client.venue and (routed is None or routed == client.client_id)


def native_order_account(order, client=None):
    accounts = {str(event.account_id) for event in order.events if getattr(event, "account_id", None) is not None}
    if order.account_id is not None:
        accounts.add(str(order.account_id))
    actual = next(iter(accounts)) if len(accounts) == 1 else None
    if client is not None:
        if actual != str(client.account_id) or not native_order_client_matches(order, client):
            return None
    return actual


def retained_fill_report(event, ts_init):
    if event.commission is None:
        raise ValueError("Retained fill fee provenance is unknown; required-Money report withheld")
    from .alpaca_reports import execution_id
    return FillReport(event.account_id, event.instrument_id, event.venue_order_id, TradeId(execution_id(event.trade_id)),
        event.order_side, event.last_qty, event.last_px, event.commission, event.liquidity_side,
        event.ts_event, ts_init, client_order_id=event.client_order_id)


def require_fill_match(report, event):
    from .alpaca_reports import execution_id
    fields = ("account_id", "instrument_id", "venue_order_id", "client_order_id", "order_side", "ts_event")
    if (execution_id(report.trade_id) != execution_id(event.trade_id)
            or any(getattr(report, key) != getattr(event, key) for key in fields)
            or report.last_qty.as_decimal() != event.last_qty.as_decimal()
            or report.last_px.as_decimal() != event.last_px.as_decimal()
            or report.commission is None or event.commission is None
            or report.commission.currency != event.commission.currency
            or report.commission.as_decimal() != event.commission.as_decimal()):
        raise ValueError("Retained native fill identity, economics or actual fee currency conflicts with the source report")
