"""Reviewed linked equity terms and broker/native identities, without local exit emulation."""

import copy
import re
from decimal import Decimal


LIVE = {"new", "accepted", "accepted_for_bidding", "pending_new", "partially_filled", "held", "pending_cancel", "pending_replace", "done_for_day"}


def equity_quantity(value, *, zero=False):
    text = str(value)
    if not re.fullmatch(r"(?:0|[1-9]\d{0,17})(?:\.\d{1,9})?", text):
        raise ValueError("Enter an exact share quantity with at most nine decimal places")
    quantity = Decimal(text)
    if quantity < 0 or not zero and quantity == 0:
        raise ValueError("Share quantity must be positive")
    return quantity


def asset_session_flags(asset):
    attributes = asset.get("attributes")
    return {key: asset[key] if type(asset.get(key)) is bool else True if isinstance(attributes, list) and key in attributes else None
            for key in ("overnight_tradable", "overnight_halted", "fractional_eh_enabled")}


def session_terms(terms):
    session = terms.get("session", "regular")
    if session not in {"regular", "extended"}:
        raise ValueError("Choose regular or extended sessions")
    if session == "extended" and (terms.get("order_type") != "LIMIT" or terms.get("exit_plan")
            or terms.get("time_in_force") not in {"DAY", "GTC"} or terms.get("notional") is not None):
        raise ValueError("Extended sessions require a simple quantity-sized LIMIT DAY/GTC order")
    return session


def broker_session(row):
    if type(row.get("extended_hours")) is not bool:
        raise ValueError("Broker execution-session eligibility is unknown")
    session = "extended" if row["extended_hours"] else "regular"
    session_terms({"session": session, "order_type": native_type(row.get("type")),
        "time_in_force": str(row.get("time_in_force", "")).upper(),
        "exit_plan": row if (row.get("group_class") or row.get("order_class")) not in (None, "", "simple") else None})
    return session


def fractional_terms(terms, *, fractionable=None):
    session_terms(terms)
    quantity = equity_quantity(terms["quantity"])
    if quantity % 1:
        if (terms.get("time_in_force") != "DAY" or terms.get("exit_plan")
                or terms.get("session", "regular") == "extended" and terms.get("order_type") != "LIMIT"):
            raise ValueError("Fractional shares require a simple DAY order; extended sessions require LIMIT")
        if fractionable is not None and fractionable is not True:
            raise ValueError("The observed Alpaca asset is not enabled for fractional shares")
    return quantity


def trailing_terms(terms):
    """Validate the initial broker-managed trail, never its changing observed stop."""
    fields = [key for key in ("trail_price", "trail_percent") if terms.get(key) not in (None, "")]
    if terms.get("order_type") != "TRAILING_STOP_MARKET":
        if fields:
            raise ValueError("Trail distance belongs only to a trailing-stop-market order")
        return None
    if (terms.get("side") != "SELL" or equity_quantity(terms["quantity"]) % 1
            or terms.get("time_in_force") not in {"DAY", "GTC"} or terms.get("session", "regular") != "regular"
            or terms.get("exit_plan") or terms.get("replacement") or terms.get("limit_price") not in (None, "")
            or terms.get("stop_price") not in (None, "") or len(fields) != 1):
        raise ValueError("Trailing stops require a standalone whole-share SELL, DAY/GTC, and exactly one trail distance; amendments are unavailable")
    key = fields[0]
    value = str(terms[key])
    precision = 2 if key == "trail_price" else 9
    if not re.fullmatch(r"\d{1,12}(?:\.\d{1," + str(precision) + r"})?", value) or Decimal(value) <= 0:
        raise ValueError("Enter a positive exact trail distance: USD cents or percentage with at most nine decimal places")
    return key, Decimal(value)


def native_trail(terms):
    key, value = trailing_terms(terms)
    # Nautilus uses basis points: one percent equals exactly 100 basis points.
    return (value, "PRICE") if key == "trail_price" else (value * 100, "BASIS_POINTS")


def exit_plan(value, side):
    if value in (None, {}):
        return None
    if side not in {"BUY", "SELL"} or not isinstance(value, dict) or set(value) - {"take_profit", "stop_price", "stop_limit_price"}:
        raise ValueError("An exit plan contains only target and stop prices for a supported equity side")
    result = {}
    for key in ("take_profit", "stop_price", "stop_limit_price"):
        price = value.get(key)
        if price not in (None, ""):
            if not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", str(price)) or Decimal(str(price)) <= 0:
                raise ValueError("Exit prices must be positive USD amounts with at most two decimal places")
            result[key] = str(price)
    if not result or result.get("stop_limit_price") and not result.get("stop_price"):
        raise ValueError("Choose a profit target or stop trigger; a stop limit also requires its trigger")
    if side == "SELL" and not (result.get("take_profit") and result.get("stop_price")):
        raise ValueError("A paired position exit requires both prices; use a simple SELL limit or stop for a single exit")
    if result.get("take_profit") and result.get("stop_price") and Decimal(result["take_profit"]) <= Decimal(result["stop_price"]):
        raise ValueError("The profit target must be above the protective stop trigger")
    if result.get("stop_limit_price") and Decimal(result["stop_limit_price"]) > Decimal(result["stop_price"]):
        raise ValueError("A protective SELL stop limit must not exceed its stop trigger")
    return result


def order_class(terms):
    plan = terms.get("exit_plan") or {}
    return "oco" if plan and terms["side"] == "SELL" else "bracket" if plan.get("take_profit") and plan.get("stop_price") else "oto" if plan else "simple"


def broker_payload(terms, client_order_id):
    fractional_terms(terms)
    trail = trailing_terms(terms)
    body = {"symbol": terms["symbol"], "qty": terms["quantity"], "side": terms["side"].lower(),
            "type": "stop" if terms["order_type"] == "STOP_MARKET" else terms["order_type"].lower(), "time_in_force": terms["time_in_force"].lower(),
            "extended_hours": session_terms(terms) == "extended", "client_order_id": client_order_id}
    if trail:
        body.update(type="trailing_stop", **{trail[0]: terms[trail[0]]})
    if terms.get("limit_price") is not None:
        body["limit_price"] = terms["limit_price"]
    if terms.get("stop_price") is not None:
        body["stop_price"] = terms["stop_price"]
    plan = exit_plan(terms.get("exit_plan"), terms["side"])
    if plan:
        body["order_class"] = order_class(terms)
        if terms["order_type"] not in {"MARKET", "LIMIT"}:
            raise ValueError("Linked entry groups support MARKET/LIMIT entries only")
        if terms["side"] == "SELL":
            if terms["order_type"] != "LIMIT" or Decimal(str(terms.get("limit_price"))) != Decimal(plan["take_profit"]):
                raise ValueError("The OCO root must be a SELL LIMIT at the exact reviewed profit target")
            body.pop("limit_price")  # Alpaca OCO takes its root limit from take_profit.
        if plan.get("take_profit"):
            body["take_profit"] = {"limit_price": plan["take_profit"]}
        if plan.get("stop_price"):
            body["stop_loss"] = {"stop_price": plan["stop_price"]}
            if plan.get("stop_limit_price"):
                body["stop_loss"]["limit_price"] = plan["stop_limit_price"]
    return body


def flatten_orders(rows):
    """Retain every broker leg once; relationships come only from a nested broker response."""
    output = {}
    def add(source, parent=None):
        row = copy.deepcopy(source)
        children = row.pop("legs", None) or []
        kind = (parent or row).get("group_class") or (parent or row).get("order_class") or "simple"
        if kind not in {"simple", "bracket", "oto", "oco"}:
            raise ValueError("Unsupported broker order class")
        if parent:
            if row.get("symbol") != parent.get("symbol") or row.get("side") != "sell":
                raise ValueError("Linked equity exit identity differs from its broker parent")
            row.update(group_parent_id=parent["id"], group_class=kind,
                       group_entry_status=parent["status"],
                       group_role="stop_loss" if row.get("type") in {"stop", "stop_limit"} else "take_profit")
        elif kind != "simple":
            row.update(group_class=kind, group_role="take_profit" if kind == "oco" else "entry")
        if row.get("group_role") in {"take_profit", "stop_loss"}:
            row["exit_active"] = row.get("status") in LIVE - {"held", "done_for_day"} and (kind == "oco" or row.get("group_entry_status") == "filled")
            row["exit_reserved"] = row.get("status") in LIVE and (kind == "oco" or row.get("group_entry_status") == "filled")
        prior = output.get(row["id"])
        if prior:
            # The same leg can also appear at the top level. Preserve the nested binding.
            if any(prior.get(key) != row.get(key) for key in ("client_order_id", "symbol", "side", "type", "qty", "filled_qty", "status",
                                                          "limit_price", "stop_price", "trail_price", "trail_percent", "hwm", "time_in_force", "extended_hours")):
                raise ValueError("Conflicting duplicate broker leg")
            if parent:
                output[row["id"]] = row
        else:
            output[row["id"]] = row
        for child in children:
            add(child, row)
    for row in rows:
        add(row)
    return list(output.values())


def native_order(factory, terms, client_order_id, *, observed_trigger=None):
    from nautilus_trader.model.enums import OrderSide, TimeInForce, TriggerType, TrailingOffsetType
    from nautilus_trader.model.identifiers import ClientOrderId, InstrumentId
    from nautilus_trader.model.objects import Price, Quantity
    fractional_terms(terms)
    kwargs = dict(instrument_id=InstrumentId.from_str(terms["instrument_id"]),
                  order_side=OrderSide.BUY if terms["side"] == "BUY" else OrderSide.SELL,
                  quantity=Quantity.from_str(terms["quantity"]), time_in_force=TimeInForce[terms["time_in_force"]],
                  client_order_id=ClientOrderId(client_order_id), tags=["extended_hours"] if session_terms(terms) == "extended" else None)
    kind = terms["order_type"]
    if kind == "TRAILING_STOP_MARKET":
        offset, unit = native_trail(terms)
        return factory.trailing_stop_market(**kwargs, trailing_offset=offset, trailing_offset_type=TrailingOffsetType[unit],
            trigger_type=TriggerType.DEFAULT, trigger_price=Price.from_str(observed_trigger) if observed_trigger is not None else None,
            emulation_trigger=TriggerType.NO_TRIGGER)
    if kind == "LIMIT":
        return factory.limit(**kwargs, price=Price.from_str(terms["limit_price"]))
    if kind in {"STOP_MARKET", "STOP_LIMIT"}:
        kwargs.update(trigger_price=Price.from_str(terms["stop_price"]), trigger_type=TriggerType.DEFAULT)
        return factory.stop_limit(**kwargs, price=Price.from_str(terms["limit_price"])) if kind == "STOP_LIMIT" else factory.stop_market(**kwargs)
    if kind == "MARKET":
        return factory.market(**kwargs)
    raise ValueError("Unsupported native order type: " + str(kind))


def native_group(factory, terms, client_order_id):
    """Use native seed events for OTO/bracket including stop-limit, absent from bracket factory."""
    from nautilus_trader.model.events import OrderInitialized
    from nautilus_trader.model.identifiers import OrderListId
    from nautilus_trader.model.orders import OrderList, OrderUnpacker
    plan = exit_plan(terms.get("exit_plan"), terms["side"])
    if not plan:
        raise ValueError("Native linked submission requires reviewed exit terms")
    group_id = OrderListId(client_order_id)
    oco = terms["side"] == "SELL"
    broker_payload(terms, client_order_id)  # Validate the same exact canonical group at both boundaries.
    specs = [("take_profit" if oco else "entry", terms, client_order_id)]
    if plan.get("take_profit") and not oco:
        specs.append(("take_profit", {**terms, "side": "SELL", "order_type": "LIMIT", "limit_price": plan["take_profit"]}, client_order_id + "-TP"))
    if plan.get("stop_price"):
        specs.append(("stop_loss", {**terms, "side": "SELL", "order_type": "STOP_LIMIT" if plan.get("stop_limit_price") else "STOP_MARKET",
                                   "stop_price": plan["stop_price"], "limit_price": plan.get("stop_limit_price")}, client_order_id + "-SL"))
    orders = []
    for role, spec, identity in specs:
        seed = native_order(factory, spec, identity).init_event
        values = OrderInitialized.to_dict(seed)
        values.update(order_list_id=str(group_id), parent_order_id=None if role == "entry" or oco else client_order_id,
                      linked_order_ids=[other for name, _, other in specs if name != "entry" and name != role],
                      contingency_type="OTO" if role == "entry" else "OCO" if oco or len(specs) == 3 else "NO_CONTINGENCY",
                      reduce_only=role != "entry", tags=["broker_managed_exit", role])
        orders.append(OrderUnpacker.unpack(values))
    return OrderList(group_id, orders)


def amendment_supported(order):
    if order.get("type") == "trailing_stop":
        raise ValueError("Trailing offset amendments are unavailable in this desk; the original broker order remains working")
    if equity_quantity(order.get("qty", "1")) % 1 and order.get("type") == "market":
        raise ValueError("Fractional MARKET quantity cannot be replaced; cancel the exact order separately")
    if (order.get("group_class") or order.get("order_class")) == "oto":
        raise ValueError("Alpaca does not support OTO replacement; cancel the group and review remaining position coverage")
    if order.get("group_class") in {"bracket", "oco"} and order.get("group_role") == "entry":
        raise ValueError("Only linked exit prices can be amended; entry quantity and group membership remain unchanged")
    if order.get("group_class") == "bracket" and order.get("group_entry_status") not in (None, "filled") and order.get("status") != "held":
        raise ValueError("An inactive bracket exit requires an exact held-child observation")


def native_type(broker_type):
    return {"stop": "STOP_MARKET", "stop_limit": "STOP_LIMIT", "trailing_stop": "TRAILING_STOP_MARKET"}.get(broker_type, str(broker_type).upper())


def native_observation(factory, row, by_order):
    """Reconstruct native relationships from broker facts; never send an order during recovery."""
    order = native_order(factory, {"instrument_id": row["symbol"] + ".ALPACA", "side": row["side"].upper(),
        "quantity": str(Decimal(row["qty"]) - Decimal(str((row.get("native_replacement_quantity_binding") or {}).get("ancestor_filled_quantity", "0")))),
        "time_in_force": row["time_in_force"].upper(), "order_type": native_type(row["type"]),
        "limit_price": row.get("limit_price"), "stop_price": None if row["type"] == "trailing_stop" else row.get("stop_price"),
        "trail_price": row.get("trail_price"), "trail_percent": row.get("trail_percent"), "session": broker_session(row)}, row.get("native_client_order_id") or row["client_order_id"],
        observed_trigger=row.get("stop_price") if row["type"] == "trailing_stop" else None)
    kind = row.get("group_class")
    if kind not in {"bracket", "oto", "oco"}:
        return order
    from nautilus_trader.model.events import OrderInitialized
    from nautilus_trader.model.orders import OrderUnpacker
    parent = by_order.get(row.get("group_parent_id"), row)
    members = [member for member in by_order.values() if member.get("group_parent_id") == parent["id"]
               or kind == "oco" and member["id"] == parent["id"]]
    identity = lambda source: source.get("native_client_order_id") or source["client_order_id"]
    entry = row.get("group_role") == "entry"
    linked = list(dict.fromkeys(identity(member) for member in members if identity(member) != identity(row)))
    values = OrderInitialized.to_dict(order.init_event)
    values.update(order_list_id=identity(parent), parent_order_id=None if entry or kind == "oco" else identity(parent),
                  linked_order_ids=linked, contingency_type="OTO" if entry and linked else "OCO" if linked else "NO_CONTINGENCY",
                  reduce_only=not entry, tags=["broker_managed_exit", row["group_role"]])
    return OrderUnpacker.unpack(values)
