"""Alpaca observations translated to the explicitly pinned native report types."""

import re
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from .linked_orders import broker_position_quantity, equity_quantity, native_trail, option_contract

from .native_types import (
    ClientOrderId, FillReport, InstrumentId, LiquiditySide, Money, OrderSide,
    OrderStatus, OrderStatusReport, OrderType, PositionSide, PositionStatusReport,
    Price, Quantity, TimeInForce, TradeId, VenueOrderId,
)



def execution_id(value):
    raw = str(value or "")
    candidate = raw.rsplit("::", 1)[-1]
    if "::" in raw and not raw.split("::", 1)[0].isdigit():
        raise ValueError("Invalid historical execution prefix")
    try:
        return str(UUID(candidate))
    except ValueError:
        if not raw or "::" in raw:
            raise ValueError("Missing or invalid execution identity") from None
        return raw


def fill_commission(row, order, account_id, currency, *, endpoint=None, account=None, linked=None):
    """Return required native Money and provenance without changing raw commission."""
    identity = execution_id(row.get("execution_id") or row.get("id"))
    supplied = row.get("commission")
    if row.get("id") and row.get("execution_id") and execution_id(row["id"]) != identity:
        raise ValueError("Fill activity and execution identities conflict")
    if linked:
        expected = {"execution_id": identity, "order_id": order["id"], "account_id": str(account_id),
                    "instrument_id": row["symbol"] + ".ALPACA", "side": row["side"]}
        if any(linked.get(key) is not None and str(linked[key]) != value for key, value in expected.items()):
            raise ValueError("Linked commission execution or order identity differs")
        if linked.get("currency") != str(currency):
            raise ValueError("Linked commission currency differs")
        if supplied is not None and not linked.get("modeled") and Decimal(str(supplied)) != Decimal(str(linked["amount"])):
            raise ValueError("Inline commission conflicts with linked evidence")
        for key in ("qty", "price"):
            if linked.get(key) is not None and Decimal(str(linked[key])) != Decimal(str(row[key])):
                raise ValueError("Linked commission fill economics differ")
        if linked.get("ts_event") is not None and linked["ts_event"] != timestamp(row["transaction_time"]):
            raise ValueError("Linked commission execution time differs")
    amount = supplied if supplied is not None else linked["amount"] if linked and not linked.get("modeled") else None
    modeled = amount is None
    if modeled:
        if order.get("asset_class") == "us_option":
            option_contract(order.get("option_contract"))
        if (endpoint != "https://paper-api.alpaca.markets" or not account
                or str(account_id) != "ALPACA-" + str(account.get("id"))
                or account.get("currency") != "USD" or str(currency) != "USD"
                or order.get("asset_class") not in {"us_equity", "us_option"}
                or order.get("order_class") not in (None, "", "simple", "bracket", "oto", "oco") and not order.get("package_parent_id")
                or any(account.get(key) for key in ("broker_id", "partner_id", "elite", "is_elite"))):
            raise ValueError("Actual commission unavailable; documented paper simulation model is inapplicable")
        amount = "0"
    if (row.get("commission_currency") or row.get("currency") or str(currency)) != str(currency):
        raise ValueError("Fill commission currency differs; no FX conversion")
    commission = exact(lambda value: Money.from_str(value + " " + str(currency)), amount)
    return commission, {"amount": str(commission.as_decimal()), "currency": str(currency),
        "modeled": modeled, "actual_commission": supplied,
        "source": "direct_paper_" + order["asset_class"] + "_simulation" if modeled else "broker_fill_commission" if supplied is not None else "execution_linked_broker_commission",
        "documentation": ["https://docs.alpaca.markets/us/docs/paper-trading", "https://alpaca.markets/algotrading"] if modeled else []}




def market_replacement_binding(row, ancestors, fills, history):
    if not history.get("complete") or not history.get("evidence") or timestamp(history["through"]) < timestamp(row["updated_at"]):
        raise ValueError("MARKET replacement requires complete execution evidence through the order observation")
    chain = {parent["id"] for parent in ancestors}
    if row.get("replaces") not in chain or row["id"] in chain:
        raise ValueError("MARKET replacement ancestor identities differ")
    executions, own, inherited = {}, Decimal(0), Decimal(0)
    for fill in fills:
        if fill.get("order_id") not in chain | {row["id"]}:
            continue
        identity = execution_id(fill.get("execution_id") or fill["id"])
        if identity in executions or fill.get("symbol") != row["symbol"] or fill.get("side") != row["side"]:
            raise ValueError("MARKET replacement execution identity or economics conflict")
        quantity = equity_quantity(fill["qty"])
        if timestamp(fill["transaction_time"]) > timestamp(history["through"]):
            raise ValueError("MARKET replacement execution quantity or time is invalid")
        executions[identity] = fill["order_id"]
        if fill["order_id"] == row["id"]:
            own += quantity
        else:
            inherited += quantity
    offset = Decimal(str(row["filled_qty"])) - own
    if offset not in {Decimal(0), inherited} or offset >= Decimal(str(row["qty"])):
        raise ValueError("MARKET replacement cumulative quantity is unexplained by actual executions")
    return {"source": "validated_broker_market_replacement" if row["type"] == "market" else "validated_broker_option_replacement", "broker_order_id": row["id"],
        "broker_client_order_id": row["client_order_id"], "predecessor_order_id": row["replaces"],
        "ancestor_filled_quantity": str(offset), "broker_filled_quantity": row["filled_qty"], "own_filled_quantity": str(own),
        "ancestor_execution_quantity": str(inherited), "ancestor_execution_ids": sorted(key for key, parent in executions.items() if parent in chain),
        "order_ids": sorted(chain | {row["id"]}), "history_receipt": history["evidence"],
        "history_boundary_receipts": history.get("boundary_pages", []), "history_through": history["through"]}


def package_replacement_binding(row, ancestors, fills, history):
    if not history.get("complete") or not history.get("evidence") or timestamp(history["through"]) < timestamp(row["updated_at"]):
        raise ValueError("Package replacement requires complete actual leg execution history")
    parents = ancestors + [row]
    if row.get("replaces") not in {parent["id"] for parent in ancestors}:
        raise ValueError("Package replacement ancestor chain is unavailable")
    units, execution_ids, ancestor_execution_ids = {}, set(), set()
    for parent in parents:
        totals = []
        for leg in parent["package_members"]:
            total = Decimal(0)
            for fill in fills:
                if fill.get("order_id") not in {leg["id"], parent["id"]} or fill.get("symbol") != leg["symbol"]:
                    continue
                identity = execution_id(fill.get("execution_id") or fill["id"])
                if identity in execution_ids or fill.get("symbol") != leg["symbol"] or fill.get("side") != leg["side"]:
                    raise ValueError("Package replacement execution identity conflicts")
                execution_ids.add(identity)
                if parent["id"] != row["id"]:
                    ancestor_execution_ids.add(identity)
                total += equity_quantity(fill["qty"])
            totals.append(total / Decimal(leg["package_ratio_qty"]))
        if len(set(totals)) != 1 or totals[0] % 1:
            raise ValueError("Actual package legs do not explain whole strategy units")
        units[parent["id"]] = totals[0]
    inherited = sum((units[parent["id"]] for parent in ancestors), Decimal(0))
    offset = Decimal(row["filled_qty"]) - units[row["id"]]
    if offset not in {Decimal(0), inherited} or offset >= Decimal(row["qty"]):
        raise ValueError("Package successor cumulative units are unexplained")
    return {"source": "validated_broker_package_replacement", "broker_order_id": row["id"],
        "broker_client_order_id": row["client_order_id"], "predecessor_order_id": row["replaces"],
        "ancestor_filled_quantity": str(offset), "broker_filled_quantity": row["filled_qty"], "own_filled_quantity": str(units[row["id"]]),
        "ancestor_execution_quantity": str(inherited), "ancestor_execution_ids": sorted(ancestor_execution_ids),
        "order_ids": sorted(parent["id"] for parent in parents), "history_receipt": history["evidence"],
        "history_boundary_receipts": history.get("boundary_pages", []), "history_through": history["through"]}


def native_quantities(row):
    quantity, filled = Decimal(str(row["qty"])), Decimal(str(row["filled_qty"]))
    binding = row.get("native_replacement_quantity_binding")
    if binding:
        offset = Decimal(str(binding["ancestor_filled_quantity"]))
        chain = binding.get("order_ids", [])
        if (not (row.get("type") == "market" and binding.get("source") == "validated_broker_market_replacement"
                or row.get("asset_class") == "us_option" and binding.get("source") == "validated_broker_option_replacement"
                or row.get("package_terms") and binding.get("source") == "validated_broker_package_replacement")
                or binding.get("broker_order_id") != row["id"] or binding.get("broker_client_order_id") != row["client_order_id"]
                or binding.get("predecessor_order_id") != row.get("replaces")
                or len(chain) < 2 or len(set(chain)) != len(chain) or row["id"] not in chain or row["replaces"] not in chain
                or not offset.is_finite() or offset < 0 or offset > filled or offset >= quantity
                or Decimal(str(binding["broker_filled_quantity"])) - Decimal(str(binding["own_filled_quantity"])) != offset
                or offset not in {Decimal(0), Decimal(str(binding["ancestor_execution_quantity"]))} or not binding.get("history_receipt")):
            raise ValueError("Invalid confirmed MARKET successor quantity binding")
        quantity, filled = quantity - offset, filled - offset
    return quantity, filled


def timestamp(value):
    """Preserve the provider's fractional seconds, including nanoseconds."""
    match = re.fullmatch(r"(.{19})(?:\.(\d{1,9}))?(Z|[+-]\d\d:\d\d)", value or "")
    if not match:
        raise ValueError("Missing or unsupported broker event timestamp")
    seconds = int(datetime.fromisoformat(match[1] + match[3].replace("Z", "+00:00")).timestamp())
    return seconds * 1_000_000_000 + int((match[2] or "").ljust(9, "0"))


def exact(factory, value):
    decimal = Decimal(str(value))
    if not decimal.is_finite():
        raise ValueError("Non-finite broker decimal")
    result = factory(str(value))
    if result.as_decimal() != decimal:
        raise ValueError("Broker decimal cannot round-trip through the Nautilus type")
    return result


def eligible(row):
    if row.get("asset_class") == "us_option":
        contract = option_contract(row.get("option_contract"))
        if contract["symbol"] != row.get("symbol") or equity_quantity(row["qty"]) % 1:
            raise ValueError("Option report quantity or contract identity differs")
        if row.get("side") in {"buy", "sell"}:
            allowed = {("buy", "buy_to_open"), ("sell", "sell_to_close")}
            if row.get("package_parent_id") and row.get("execution_profile") == "bounded_risk_spread_v1":
                allowed |= {("buy", "buy_to_close"), ("sell", "sell_to_open")}
            if (row["side"], row.get("position_intent")) not in allowed:
                raise ValueError("Option report intent is unsupported or unknown")
    elif row.get("asset_class") != "us_equity":
        raise ValueError("Instrument class is observation-only; native equity mapping unavailable")
    if row.get("side") in {"long", "short"}:
        broker_position_quantity(row)
    else:
        equity_quantity(row["qty"])
    return InstrumentId.from_str(row["symbol"] + ".ALPACA")


def position_report(row, account_id, ts_init):
    instrument = eligible(row)
    signed = broker_position_quantity(row)
    qty = exact(Quantity.from_str, abs(signed))
    average = Decimal(str(row["avg_entry_price"]))
    if qty.as_decimal() <= 0 or not average.is_finite() or average <= 0:
        raise ValueError("Position average cost is unavailable or invalid")
    return PositionStatusReport(account_id, instrument, PositionSide.SHORT if signed < 0 else PositionSide.LONG, qty,
                                ts_init, ts_init, avg_px_open=average)


def order_report(row, account_id, ts_init):
    from .linked_orders import broker_session, package_observation
    package = row.get("package_terms")
    if package:
        package_observation(row, package)
        instrument = InstrumentId.from_str(package["instrument_id"])
    else:
        broker_session(row)
        instrument = eligible(row)
    if row.get("asset_class") == "us_option" and not package:
        from .linked_orders import native_type, option_terms
        option_terms({"asset_class": "us_option", "symbol": row["symbol"], "currency": "USD", "quantity": row["qty"],
            "side": row["side"].upper(), "position_intent": row.get("position_intent"), "option_contract": row.get("option_contract"),
            "order_type": native_type(row.get("type")), "time_in_force": str(row.get("time_in_force", "")).upper(),
            "session": broker_session(row), "limit_price": row.get("limit_price"), "stop_price": row.get("stop_price")})
    if not package and (row.get("order_class") not in {None, "", "simple", "bracket", "oto", "oco"} or row.get("legs")):
        raise ValueError("Linked orders must be flattened from their authoritative broker relationship before import")
    statuses = {"new": "ACCEPTED", "accepted": "ACCEPTED", "held": "ACCEPTED", "done_for_day": "ACCEPTED", "pending_new": "SUBMITTED",
                "accepted_for_bidding": "ACCEPTED", "partially_filled": "PARTIALLY_FILLED",
                "filled": "FILLED", "canceled": "CANCELED", "expired": "EXPIRED",
                "rejected": "REJECTED", "pending_cancel": "PENDING_CANCEL", "pending_replace": "PENDING_UPDATE"}
    if row.get("status") == "replaced" and row.get("native_replacement_verified"):
        statuses["replaced"] = "CANCELED"
    types = {"market": OrderType.MARKET, "limit": OrderType.LIMIT, "stop": OrderType.STOP_MARKET, "stop_limit": OrderType.STOP_LIMIT,
             "trailing_stop": OrderType.TRAILING_STOP_MARKET}
    tifs = {"day": TimeInForce.DAY, "gtc": TimeInForce.GTC, "ioc": TimeInForce.IOC,
            "fok": TimeInForce.FOK, "opg": TimeInForce.AT_THE_OPEN, "cls": TimeInForce.AT_THE_CLOSE}
    if row.get("status") not in statuses or row.get("type") not in types or row.get("time_in_force") not in tifs:
        raise ValueError("Order status/type/TIF is preserved as an unsupported broker observation")
    if not package and row.get("side") not in {"buy", "sell"}:
        raise ValueError("Unknown order side")
    native_quantity, native_filled = native_quantities(row)
    quantity = exact(Quantity.from_str, native_quantity)
    filled = exact(Quantity.from_str, native_filled)
    if quantity.as_decimal() <= 0 or filled.as_decimal() > quantity.as_decimal():
        raise ValueError("Order filled quantity exceeds its total or total quantity is invalid")
    equity_quantity(row["filled_qty"], zero=True)
    average = Decimal(str(row["filled_avg_price"])) if row.get("filled_avg_price") is not None else None
    if average is not None and (not average.is_finite() or not package and average <= 0):
        raise ValueError("Filled average price must be finite and positive")
    if filled.as_decimal() > 0 and average is None:
        raise ValueError("Filled average price is unavailable")
    limit = exact(Price.from_str, row["limit_price"]) if row.get("limit_price") is not None else None
    if row["type"] in {"limit", "stop_limit"} and (limit is None or (limit.as_decimal() == 0 if package else limit.as_decimal() <= 0)):
        raise ValueError("Limit price must be present and positive")
    trigger = exact(Price.from_str, row["stop_price"]) if row.get("stop_price") is not None else None
    if row["type"] in {"stop", "stop_limit"} and (trigger is None or trigger.as_decimal() <= 0):
        raise ValueError("Stop trigger must be present and positive")
    from nautilus_trader.model.enums import TrailingOffsetType, TriggerType
    offset, offset_type = None, "NO_TRAILING_OFFSET"
    if row["type"] == "trailing_stop":
        offset, offset_type = native_trail({"order_type": "TRAILING_STOP_MARKET", "quantity": row["qty"],
            "side": row["side"].upper(), "time_in_force": row["time_in_force"].upper(),
            "exit_plan": row if row.get("order_class") not in (None, "", "simple") else None,
            "trail_price": row.get("trail_price"), "trail_percent": row.get("trail_percent")})
    return OrderStatusReport(
        account_id, instrument, VenueOrderId(row["id"]),
        OrderSide.BUY if package or row["side"] == "buy" else OrderSide.SELL,
        types[row["type"]], tifs[row["time_in_force"]], getattr(OrderStatus, "PARTIALLY_FILLED" if row["status"] == "done_for_day" and filled.as_decimal() > 0 else "ACCEPTED" if row["status"] == "partially_filled" and filled.as_decimal() == 0 else statuses[row["status"]]),
        quantity, filled,
        timestamp(row.get("submitted_at") or row["created_at"]),
        timestamp(row.get("updated_at") or row["created_at"]), ts_init,
        client_order_id=ClientOrderId(row.get("native_client_order_id") or row["client_order_id"]) if row.get("client_order_id") else None,
        price=limit, avg_px=average, trigger_price=trigger,
        trigger_type=TriggerType.DEFAULT if trigger is not None or offset is not None else TriggerType.NO_TRIGGER,
        cancel_reason=row.get("reject_reason"),
        trailing_offset=offset, trailing_offset_type=TrailingOffsetType[offset_type],
    )


def fill_report(row, order, account_id, currency, ts_init, *, endpoint=None, account=None, linked=None):
    if order.get("package_terms"):
        matches = [member for member in order["package_members"] if member["symbol"] == row.get("symbol") and member["side"] == row.get("side")]
        if len(matches) != 1 or row.get("order_id") != order["id"]:
            raise ValueError("Parent-linked actual execution has no unique actual package member")
        order = {**matches[0], "id": row["order_id"], "package_member_broker_id": matches[0]["id"]}
    if (row.get("order_id") != order.get("id") or row.get("symbol") != order.get("symbol")
            or row.get("side") != order.get("side")):
        raise ValueError("Fill order identity, symbol or side does not match its parent order")
    eligible({**order, "qty": row["qty"]})
    commission, provenance = fill_commission(row, order, account_id, currency, endpoint=endpoint, account=account, linked=linked)
    row["native_fee"] = provenance
    if row.get("side") not in {"buy", "sell"}:
        raise ValueError("Unknown fill side")
    quantity, price = exact(Quantity.from_str, row["qty"]), exact(Price.from_str, row["price"])
    if quantity.as_decimal() <= 0 or price.as_decimal() <= 0:
        raise ValueError("Fill quantity and price must be positive")
    return FillReport(account_id, InstrumentId.from_str(row["symbol"] + ".ALPACA"),
        VenueOrderId(row["order_id"]), TradeId(execution_id(row.get("execution_id") or row["id"])),
        OrderSide.BUY if row["side"] == "buy" else OrderSide.SELL,
        quantity, price, commission,
        LiquiditySide.NO_LIQUIDITY_SIDE, timestamp(row["transaction_time"]), ts_init,
        client_order_id=ClientOrderId(order.get("native_client_order_id") or order["client_order_id"])
            if order.get("native_client_order_id") or order.get("client_order_id") else None)
