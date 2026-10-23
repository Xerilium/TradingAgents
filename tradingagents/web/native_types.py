"""Model types and report signatures for the pinned official Nautilus v1 contract."""
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.model.identifiers import (AccountId, ClientId, ClientOrderId,
    InstrumentId, Symbol, TradeId, TraderId, Venue, VenueOrderId)
from nautilus_trader.model.enums import (AccountType, AggressorSide, LiquiditySide,
    OmsType, OrderSide, OrderStatus, OrderType, PositionSide, TimeInForce)
from nautilus_trader.model.objects import AccountBalance, Currency, Money, Price, Quantity
from nautilus_trader.model.data import QuoteTick, TradeTick
from nautilus_trader.model.events import OrderFilled
from nautilus_trader.model.instruments import Equity as _Equity
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.execution import reports as _reports

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
