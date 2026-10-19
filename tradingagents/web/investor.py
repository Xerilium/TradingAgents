"""Human policy and proposal records. No order submission or approval capability."""

import copy
import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from .workspace import text

RULES = {"cash_reserve_pct": "Minimum cash reserve %", "max_position_pct": "Maximum position %",
         "max_gross_exposure_pct": "Maximum gross exposure %", "loss_limit_pct": "Loss limit %",
         "scenario_loss_pct": "Scenario loss estimate limit %", "max_sector_pct": "Maximum sector exposure %",
         "max_correlation_pct": "Maximum absolute return correlation %", "max_spread_bps": "Maximum quoted spread / bps",
         "min_quote_size": "Minimum displayed quote quantity / shares", "session_freshness": "Maximum open-session quote age / seconds"}
RULE_PARAMETERS = {
    "scenario_loss_pct": {"shock_pct": {"label": "Adverse price decrease / %", "min": 0, "max": 100},
                          "method": {"label": "Scenario method", "choices": ["parallel_long_equity_price_shock"]}},
    "max_sector_pct": {"classification": {"label": "Sector taxonomy", "choices": ["provider_sector"]},
                       "max_classification_age_seconds": {"label": "Maximum classification age / seconds", "min": 1, "max": 31536000}},
    "max_correlation_pct": {"window_sessions": {"label": "Return window / sessions", "min": 3, "max": 1000, "integer": True},
        "max_history_age_seconds": {"label": "Maximum correlation history age / seconds", "min": 1, "max": 31536000},
        "minimum_pairs": {"label": "Minimum paired return dates", "min": 3, "max": 1000, "integer": True},
        "method": {"label": "Correlation method", "choices": ["pearson_daily_close_returns"]},
        "adjustment": {"label": "Price adjustment", "choices": ["split", "all"]}},
    "max_spread_bps": {"max_quote_age_seconds": {"label": "Maximum quote age / seconds", "min": 1, "max": 31536000}},
    "min_quote_size": {"max_quote_age_seconds": {"label": "Maximum quote age / seconds", "min": 1, "max": 31536000}},
    "session_freshness": {"closed_max_age_seconds": {"label": "Maximum closed-session quote age / seconds", "min": 1, "max": 31536000},
                          "session": {"label": "Session permission", "choices": ["regular_session_required", "allow_closed_session_review"]}}}
DEFAULT = {"policy": {"revision": 0, "rules": {}}, "policy_history": [], "proposals": []}


def invalidate_baskets(saved, identity, stamp):
    for basket in saved.get("baskets", []):
        if identity is None or identity in basket["linked_proposal_ids"]:
            basket.update(approval=None, impact_review_valid=False)
            basket["history"].append({"action": "policy_changed" if identity is None else "proposal_changed",
                                      "proposal_id": identity, "at": stamp})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def decimal(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def price_evidence(terms, runtime):
    """Exact limit or dated IEX estimate; neither a consolidated quote nor guaranteed fill."""
    if terms.get("order_type") == "LIMIT":
        price = decimal(terms.get("limit_price"))
        return {"price": price if price is not None and price > 0 else None,
                "basis": "Exact human limit / USD", "ts_event": None}
    if terms.get("order_type") != "MARKET":
        return {"price": None, "basis": "Unsupported order price basis", "ts_event": None}
    market = runtime.get("market_data", {}).get(terms["symbol"], {})
    quote, trade = market.get("quote") or {}, market.get("trade") or {}
    side = "ask_price" if str(terms.get("side")).upper() == "BUY" else "bid_price"
    for value, event, basis in ((quote.get(side), quote.get("ts_event"), "Dated IEX " + side + " estimate"),
                                (trade.get("price"), trade.get("ts_event"), "Dated IEX last-trade estimate")):
        price, stamp = decimal(value), decimal(event)
        if price is not None and price > 0 and stamp is not None and 0 < stamp <= Decimal(str(datetime.now(UTC).timestamp())) * 1000000000:
            return {"price": price, "basis": basis + "; execution price is unknown", "ts_event": event}
    return {"price": None, "basis": "Dated side quote or last trade unavailable", "ts_event": None}


def execution_costs(terms, runtime, constraints):
    price = price_evidence(terms, runtime)["price"]
    ceiling = decimal(constraints.get("max_execution_price"))
    if terms["order_type"] == "MARKET" and terms["side"] == "BUY" and ceiling is not None:
        price = ceiling if price is not None and price <= ceiling else None
    return price, decimal(constraints.get("max_fees"))


def order_version(order):
    return digest({key: order.get(key) for key in ("id", "client_order_id", "symbol", "asset_id", "side", "qty",
        "filled_qty", "type", "order_type", "order_class", "limit_price", "stop_price", "time_in_force",
        "extended_hours", "status", "replaces", "replaced_by")})



def native_quantity_offset(order):
    """Only an execution-proven MARKET successor translates raw cumulative quantities."""
    proof = order.get("native_replacement_quantity_binding")
    if not proof:
        if str(order.get("type", order.get("order_type"))).upper() == "MARKET" and order.get("replaces"):
            raise ValueError("MARKET successor execution quantity proof is unavailable")
        return Decimal(0)
    if not isinstance(proof, dict):
        raise ValueError("MARKET successor quantity provenance is malformed")
    offset, bound, own, ancestors = (decimal(proof.get(key)) for key in
        ("ancestor_filled_quantity", "broker_filled_quantity", "own_filled_quantity", "ancestor_execution_quantity"))
    total, filled = decimal(order.get("qty")), decimal(order.get("filled_qty"))
    chain, executions = proof.get("order_ids"), proof.get("ancestor_execution_ids")
    def receipt(value):
        return isinstance(value, dict) and isinstance(value.get("path"), str) and bool(value["path"]) and bool(
            re.fullmatch(r"[0-9a-f]{64}", str(value.get("sha256", ""))))
    boundary = proof.get("history_boundary_receipts")
    try:
        through = datetime.fromisoformat(proof.get("history_through", "").replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        through = None
    if (str(order.get("type", order.get("order_type"))).upper() != "MARKET"
            or proof.get("source") != "validated_broker_market_replacement"
            or proof.get("broker_order_id") != order.get("id") or proof.get("broker_client_order_id") != order.get("client_order_id")
            or not order.get("replaces") or proof.get("predecessor_order_id") != order["replaces"]
            or not isinstance(chain, list) or len(chain) < 2 or any(not isinstance(v, str) or not v for v in chain)
            or len(set(chain)) != len(chain) or order["id"] not in chain or order["replaces"] not in chain
            or any(v is None or v < 0 for v in (offset, bound, own, ancestors, total, filled))
            or offset not in {Decimal(0), ancestors} or bound != own + offset or bound > filled
            or not offset <= filled <= total or offset >= total
            or not isinstance(executions, list) or any(not isinstance(v, str) or not v for v in executions)
            or len(set(executions)) != len(executions) or ancestors > 0 and not executions
            or not receipt(proof.get("history_receipt")) or not isinstance(boundary, list) or not all(receipt(v) for v in boundary)
            or through is None or through.tzinfo is None
            or proof.get("incoming_execution_receipt") is not None and not receipt(proof["incoming_execution_receipt"])):
        raise ValueError("MARKET successor quantity translation lacks exact execution and receipt provenance")
    return offset


def broker_action_order(runtime, identity, version=None):
    """Current supported broker order and exact native identity for explicit human actions."""
    matches = [o for o in runtime.get("orders", []) if o.get("id") == identity]
    if len(matches) != 1:
        raise ValueError("The selected broker order is not a distinct current observation")
    order = matches[0]
    native = order.get("binding_native") or order.get("nautilus") or {}
    account_id = (runtime.get("account") or {}).get("id")
    total, filled = decimal(order.get("qty")), decimal(order.get("filled_qty"))
    offset = native_quantity_offset(order)
    native_account = (native.get("account_binding") or {}).get("account_id")
    client = native.get("client_order_id")
    alias = order.get("native_client_order_binding") or {}
    chain = alias.get("order_ids", [])
    client_matches = client == order.get("client_order_id") or (
        alias.get("source") == "validated_broker_replacement_chain" and alias.get("broker_order_id") == identity
        and alias.get("broker_client_order_id") == order.get("client_order_id")
        and alias.get("native_client_order_id") == client and isinstance(chain, list) and len(chain) >= 2
        and all(isinstance(item, str) and item for item in chain) and len(set(chain)) == len(chain) and identity in chain)
    if order.get("native_replacement_quantity_binding"):
        client_matches = client == order.get("client_order_id")
    venue = native.get("venue_order_id")
    indexed = native.get("venue_order_id_binding") or {}
    if (venue is None and native.get("status") in {"SUBMITTED", "PENDING_CANCEL", "PENDING_UPDATE"}
            and indexed.get("source") == "native_cache_venue_order_index"
            and indexed.get("client_order_id") == native.get("client_order_id")):
        venue = indexed.get("venue_order_id")
    expected_status = {"new": "ACCEPTED", "accepted": "ACCEPTED", "partially_filled": "PARTIALLY_FILLED", "pending_new": "SUBMITTED"}
    if order.get("status") == "partially_filled" and filled is not None and filled - offset == 0:
        expected_status["partially_filled"] = "ACCEPTED"
    if (runtime.get("status") != "connected" or not account_id or order.get("account_id") not in (None, account_id)
            or order.get("asset_class") != "us_equity" or order.get("side") not in {"buy", "sell"}
            or str(order.get("type", order.get("order_type"))).upper() not in {"MARKET", "LIMIT"}
            or order.get("time_in_force") != "day" or order.get("extended_hours") is not False
            or order.get("order_class") not in (None, "", "simple") or order.get("import_error")
            or total is None or total <= 0 or total % 1 or filled is None or not 0 <= filled < total
            or not order.get("client_order_id") or native_account != "ALPACA-" + str(account_id)
            or native.get("instrument_id") != order.get("symbol", "") + ".ALPACA"
            or not client_matches or venue != identity
            or native.get("side") != order["side"].upper()
            or native.get("type") != str(order.get("type", order.get("order_type"))).upper()
            or native.get("time_in_force") != "DAY"
            or str(order.get("type", order.get("order_type"))).upper() == "LIMIT" and decimal(native.get("price")) != decimal(order.get("limit_price"))
            or total is None or filled is None or decimal(native.get("quantity")) != total - offset or decimal(native.get("filled_qty")) != filled - offset
            or native.get("status") != expected_status.get(order.get("status"))
            or version is not None and version != order_version(order)):
        raise ValueError("Broker/native identity, source terms or supported regular DAY equity order state differs")
    return order


def validated_replacement(terms, runtime):
    binding = terms.get("replacement")
    if not binding:
        return None
    matches = [row for row in runtime.get("orders", []) if row.get("id") == binding.get("order_id")]
    if len(matches) != 1:
        raise ValueError("Exact replacement predecessor is not a current authoritative working order")
    order = broker_action_order(runtime, binding.get("order_id"), binding.get("order_version"))
    filled, total = decimal(order.get("filled_qty")), decimal(terms.get("quantity"))
    if (binding.get("account_id") != (runtime.get("account") or {}).get("id")
            or binding.get("symbol") != terms["symbol"] or binding.get("side") != terms["side"]
            or order.get("symbol") != terms["symbol"] or str(order.get("side")).upper() != terms["side"]
            or str(order.get("type", order.get("order_type"))).upper() != terms["order_type"]
            or str(order.get("time_in_force")).upper() != terms["time_in_force"]
            or order.get("status") not in {"new", "accepted", "partially_filled", "pending_new"}
            or order.get("import_error") or not binding.get("client_order_id") or binding.get("client_order_id") != order.get("client_order_id")
            or binding.get("order_version") != order_version(order) or filled is None
            or decimal(binding.get("filled_quantity")) != filled or total is None or total <= filled):
        raise ValueError("Replacement predecessor identity, version, filled quantity or compatible terms changed")
    return order


def remaining_quantity(terms):
    filled = decimal((terms.get("replacement") or {}).get("filled_quantity", "0"))
    total = decimal(terms.get("quantity"))
    return total - filled if total is not None and filled is not None and 0 <= filled < total else None


def working_commitments(runtime, commands=None, constraints=None):
    """One reservation per exact local/broker identity, or max of replacement alternatives."""
    from .admission import ACTIVE
    constraints = constraints or {}
    account_id = (runtime.get("account") or {}).get("id")
    known = commands is not None and runtime.get("reconciliation", {}).get("orders_reconciled") is True
    local = [c for c in (commands or {}).get("commands", {}).values()
             if c.get("account_id") == account_id and (c.get("state") in ACTIVE or c.get("native_pending_commitment"))]
    items, covered = [], set()
    for command in local:
        matches = [o for o in runtime.get("orders", []) if o.get("id") in command.get("broker_order_ids", [])
                   or o.get("client_order_id") == command.get("client_order_id")]
        if any(o.get("symbol") != command["symbol"] or str(o.get("side")).upper() != command["side"]
                or o.get("client_order_id") != command.get("client_order_id")
                or o.get("account_id") not in (None, account_id) for o in matches):
            known = False
        action = command.get("pending_action", {})
        replacement_not_started = (command.get("state") == "replace_pending" and action.get("kind") == "replace"
            and action.get("state") == "authorized" and action.get("broker_order_id") in command.get("broker_order_ids", [])
            and action.get("replacement_command_id") and action.get("transport_attempt") == {"version": 1, "state": "not_started"})
        observed_pending = False
        if command.get("state") == "submitting" and len(matches) == 1 and matches[0].get("status") == "pending_new":
            try:
                broker_action_order(runtime, matches[0]["id"])
                observed_pending = True
            except ValueError:
                pass
        if (command.get("state") in {"outcome_unknown", "dispatch_intent", "submitting", "cancel_pending", "replace_pending"}
                and not replacement_not_started and not observed_pending) or command.get("native_pending_commitment"):
            known = False
        pending = command.get("native_pending_commitment", {})
        quantities = [decimal(command.get("remaining_quantity")), decimal(pending.get("remaining_quantity", "0"))]
        cashes = [decimal(command.get("cash_commitment")), decimal(pending.get("cash_commitment", "0"))]
        for order in matches:
            total, filled = decimal(order.get("qty")), decimal(order.get("filled_qty"))
            if total is None or filled is None or not 0 <= filled <= total:
                known = False
                continue
            quantities.append(total - filled)
        price, fee = decimal(command.get("price_cap")), decimal(command.get("fee_commitment"))
        if command["side"] == "BUY" and price is not None:
            cashes.append(max((v for v in quantities if v is not None), default=Decimal(0)) * price + (fee if fee is not None else Decimal(0)))
        if any(v is None or v < 0 for v in quantities + cashes):
            known = False
            continue
        ids = set(command.get("broker_order_ids", [])) | {o.get("id") for o in matches}
        covered.update(o.get("id") for o in matches)
        items.append({"symbol": command["symbol"], "side": command["side"], "remaining": max(quantities),
            "cash": max(cashes), "price": decimal(command.get("price_cap")), "fee": decimal(command.get("fee_commitment")),
            "order_ids": ids, "command_ids": {command["id"]}, "parent": command.get("parent_command_id"),
            "replacement": (command.get("terms", {}).get("replacement") or {}).get("order_id")})
    seen = set()
    for order in runtime.get("orders", []):
        identity = order.get("id")
        if not identity or identity in seen or order.get("import_error"):
            known = False
        seen.add(identity)
        if identity in covered:
            continue
        qty, filled = decimal(order.get("qty")), decimal(order.get("filled_qty"))
        side = str(order.get("side")).upper()
        price = price_evidence({"symbol": order.get("symbol"), "side": side,
            "order_type": str(order.get("type", order.get("order_type"))).upper(), "limit_price": order.get("limit_price")}, runtime)["price"]
        fee = decimal(constraints.get("working_order_fee_caps", {}).get(identity))
        if qty is None or filled is None or not 0 <= filled <= qty or side not in {"BUY", "SELL"} or fee is not None and fee < 0 or side == "BUY" and price is None:
            known = False
            continue
        remaining = qty - filled
        items.append({"symbol": order["symbol"], "side": side, "remaining": remaining,
            "cash": (remaining * price if side == "BUY" else Decimal(0)) + (fee if fee is not None else Decimal(0)),
            "price": price, "fee": fee, "order_ids": {identity}, "command_ids": set(), "parent": None, "replacement": None})
    for item in list(items):
        previous = next((other for other in items if other is not item and
            (item["parent"] in other["command_ids"] or item["replacement"] in other["order_ids"])), None)
        if previous:
            previous.update(remaining=max(previous["remaining"], item["remaining"]), cash=max(previous["cash"], item["cash"]),
                order_ids=previous["order_ids"] | item["order_ids"], command_ids=previous["command_ids"] | item["command_ids"])
            items.remove(item)
    return items, known


def policy(request, previous):
    reason = text(request.get("reason", ""), 4000, "policy note")
    rules = request.get("rules")
    if not isinstance(rules, dict) or set(rules) != set(RULES):
        raise ValueError("Specify each policy rule as unset, enabled or disabled")
    result = {}
    for key, rule in rules.items():
        state = rule.get("state")
        if state not in {"unset", "enabled", "disabled"}:
            raise ValueError("Invalid policy rule state")
        why = text(rule.get("reason", ""), 2000, "rule reason")
        value = decimal(rule.get("value")) if state == "enabled" else None
        maximum = 31536000 if key == "session_freshness" else 100000 if key == "max_spread_bps" else 1000000000000 if key == "min_quote_size" else 100
        if state == "enabled" and (value is None or not 0 <= value <= maximum):
            raise ValueError("Enabled policy limit is missing or outside its supported units/range")
        result[key] = {"state": state, "value": str(value) if value is not None else None, "reason": why}
        for parameter, definition in RULE_PARAMETERS.get(key, {}).items():
            entered = rule.get(parameter)
            if state != "enabled":
                result[key][parameter] = entered if entered not in (None, "") else None
                continue
            if "choices" in definition:
                if entered not in definition["choices"]:
                    raise ValueError("Choose " + definition["label"])
                result[key][parameter] = entered
            else:
                number = decimal(entered)
                if (number is None or not definition["min"] <= number <= definition["max"]
                        or definition.get("integer") and number % 1):
                    raise ValueError("Enter " + definition["label"] + " within its supported range")
                result[key][parameter] = str(int(number)) if definition.get("integer") else str(number)
        if state == "enabled" and key == "max_correlation_pct" and Decimal(result[key]["minimum_pairs"]) > Decimal(result[key]["window_sessions"]):
            raise ValueError("Minimum paired dates cannot exceed the correlation window")
    return {"revision": previous["revision"] + 1, "rules": result, "reason": reason,
            "saved_at": datetime.now(UTC).isoformat()}


def instruments(runtime, universe):
    observed = {p["symbol"]: p for p in runtime.get("positions", [])}
    result = {}
    for symbol in sorted(set(universe) | set(observed) | {o["symbol"] for o in runtime.get("orders", []) if o.get("symbol")}):
        holding = observed.get(symbol)
        native = runtime.get("market_data", {}).get(symbol, {}).get("instrument")
        tradable = runtime.get("market_data", {}).get(symbol, {}).get("trade_supported") is True
        supported = bool(native and tradable) or bool(tradable and holding and holding.get("asset_class") == "us_equity"
                                         and holding.get("nautilus") and not holding.get("import_error"))
        reason = (holding or {}).get("import_error")
        if holding and (decimal(holding.get("qty")) is None or decimal(holding["qty"]) % 1 or holding.get("side") == "short"):
            supported, reason = False, reason or "Fractional/short holdings are observation-only"
        result[symbol] = {"symbol": symbol, "instrument_id": symbol + ".ALPACA" if supported else None,
                          "supported": supported and not reason, "limitation": reason or (None if supported else "Supported equity instrument has not been observed"),
                          "holding": bool(holding)}
    return result


def impact(terms, runtime, rules, *, commands=None):
    symbol, side, qty = terms["symbol"], terms["side"], remaining_quantity(terms)
    account = runtime.get("account") or {}
    connected = runtime.get("status") == "connected"
    reconciliation = runtime.get("reconciliation", {})
    position = next((p for p in runtime.get("positions", []) if p["symbol"] == symbol), None)
    current = decimal(position.get("qty")) if position else Decimal(0) if connected and (runtime.get("broker_observation", {}).get("positions_complete") or reconciliation.get("positions_reconciled")) else None
    selected = price_evidence(terms, runtime)
    price, price_basis = selected["price"], selected["basis"]
    principal = price * qty if price is not None and qty is not None else None
    delta = (-principal if side == "BUY" else principal) if principal is not None else None
    cash = decimal(account.get("cash")) if connected else None
    equity = decimal(account.get("equity")) if connected else None
    resulting = current + (qty if side == "BUY" else -qty) if current is not None and qty is not None else None
    observed, known_orders = working_commitments(runtime, commands)
    replacement = (terms.get("replacement") or {}).get("order_id")
    commitments = [{"id": next(iter(o["order_ids"]), None), "symbol": o["symbol"], "side": o["side"],
                    "remaining_principal_at_limit": str(o["cash"]) if o["side"] == "BUY" else None} for o in observed]
    committed_cash = sum((o["cash"] for o in observed), Decimal(0))
    predecessor = next((o for o in observed if replacement in o["order_ids"]), None)
    reserve = principal if side == "BUY" else Decimal(0)
    if predecessor and reserve is not None:
        committed_cash -= predecessor["cash"]
        reserve = max(reserve, predecessor["cash"])
    unknown_orders = not known_orders
    blockers = []
    if not connected or reconciliation.get("status") != "reconciled":
        blockers.append("Account observation is unavailable or incompletely reconciled")
    if price is None:
        blockers.append("Price estimate is unavailable")
    if resulting is None:
        blockers.append("Resulting quantity is unknown")
    elif resulting < 0:
        blockers.append("Proposed SELL exceeds observed long quantity; shorting is unsupported")
    if not reconciliation.get("orders_reconciled") or unknown_orders:
        blockers.append("Open-order commitments are incomplete or unpriced")
    after = cash - reserve - committed_cash if cash is not None and reserve is not None and not unknown_orders else None
    position_value = resulting * price if resulting is not None and price is not None else None
    for key, label in RULES.items():
        rule = rules.get(key, {})
        if rule.get("state") == "enabled":
            value = Decimal(rule["value"])
            if key == "cash_reserve_pct" and after is not None and equity and equity > 0:
                if after / equity * 100 < value:
                    blockers.append("Estimated principal would breach the cash reserve")
            elif key == "max_position_pct" and position_value is not None and equity and equity > 0:
                if position_value / equity * 100 > value:
                    blockers.append("Estimated position would breach the concentration limit")
            else:
                blockers.append(label + " requires additional sourced valuation/loss/scenario inputs")
    return {"existing_quantity": str(current) if current is not None else None,
            "resulting_quantity": str(resulting) if resulting is not None else None,
            "price_estimate": str(price) if price is not None else None, "price_basis": price_basis,
            "estimated_principal": str(principal) if principal is not None else None,
            "estimated_cash_change_before_fees": str(delta) if delta is not None else None,
            "estimated_cash_after_commitments_before_fees": str(after) if after is not None else None,
            "cash": str(cash) if cash is not None else None, "equity": str(equity) if equity is not None else None,
            "position_value_estimate": str(position_value) if position_value is not None else None,
            "account_long_market_value": account.get("long_market_value") if connected else None,
            "open_order_commitments": commitments, "fees": None, "conditions": blockers,
            "fee_disclosure": "Actual execution fees are unknown where the broker has not supplied them. Estimates and reservations exclude unknown fees; no zero fee is assumed.",
            "account_at": runtime.get("account_at"), "price_event_ns": selected["ts_event"],
            "executable": False}


def save(saved, request, runtime, universe, resolve_research):
    action = request.get("action")
    stamp = datetime.now(UTC).isoformat()
    if action == "policy":
        saved["policy"] = policy(request, saved["policy"])
        saved["policy_history"].append(copy.deepcopy(saved["policy"]))
        for proposal in saved["proposals"]:
            proposal["approval"] = None
            proposal["conditions_stale"] = True
            proposal["history"].append({"action": "policy_changed", "at": stamp, "policy_revision": saved["policy"]["revision"]})
        invalidate_baskets(saved, None, stamp)
        return saved
    prior = next((p for p in saved["proposals"] if p["id"] == request.get("id")), None)
    reason = text(request.get("reason", ""), 4000, "review rationale")
    if action in {"reject", "defer"}:
        if not prior:
            raise ValueError("Select a saved order")
        prior.update(status=action + "red" if action == "defer" else "rejected", approval=None,
                     revision=prior["revision"] + 1, updated_at=stamp)
        prior["history"].append({"action": action, "reason": reason, "at": stamp, "revision": prior["revision"]})
        invalidate_baskets(saved, prior["id"], stamp)
        return saved
    if action != "draft":
        raise ValueError("Choose a draft, reject, defer or policy edit; approve an exact saved order through its approval action")
    if request.get("id") and prior is None:
        raise ValueError("Saved proposal was not found")
    terms = request.get("terms", {})
    symbol = terms.get("symbol")
    instrument = instruments(runtime, universe).get(symbol)
    if not instrument or not instrument["supported"]:
        raise ValueError((instrument or {}).get("limitation") or "Select an observed supported equity")
    quantity = str(terms.get("quantity", ""))
    if not re.fullmatch(r"[1-9]\d{0,17}", quantity):
        raise ValueError("Enter a positive whole-share quantity; no rounding is performed")
    if terms.get("side") not in {"BUY", "SELL"} or terms.get("order_type") not in {"MARKET", "LIMIT"}:
        raise ValueError("Only BUY/SELL and MARKET/LIMIT proposals are supported")
    limit = terms.get("limit_price") if terms["order_type"] == "LIMIT" else None
    if limit is not None and (not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", str(limit)) or decimal(limit) <= 0):
        raise ValueError("Enter a positive limit price with at most two decimal places")
    if terms["order_type"] == "LIMIT" and limit is None:
        raise ValueError("Limit price is required")
    rationale = text(terms.get("rationale", ""), 10000, "proposal rationale")
    research = resolve_research(terms["research"]) if terms.get("research") else None
    from .evidence_requirements import DECISION_SCOPES, VERSION
    evidence_scopes = terms.get("decision_evidence_scopes", [])
    if not isinstance(evidence_scopes, list) or any(not isinstance(scope, str) or scope not in DECISION_SCOPES for scope in evidence_scopes):
        raise ValueError("Choose supported evidence dependencies for this decision")
    if research and research["symbol"] != symbol:
        raise ValueError("Linked research belongs to another symbol")
    exact = {"symbol": symbol, "instrument_id": instrument["instrument_id"], "side": terms["side"],
             "quantity": quantity, "order_type": terms["order_type"], "limit_price": str(limit) if limit is not None else None,
             "time_in_force": "DAY", "session": "regular", "rationale": rationale, "research": research,
             "decision_evidence_scopes": sorted(set(evidence_scopes)), "evidence_requirements_version": VERSION,
             "account_id": (runtime.get("account") or {}).get("id")}
    if terms.get("replacement"):
        identity = terms["replacement"].get("order_id")
        order = next((o for o in runtime.get("orders", []) if o.get("id") == identity), None)
        if order is None:
            raise ValueError("Select an exact current broker order to replace")
        exact["replacement"] = {"order_id": identity, "client_order_id": order.get("client_order_id"),
            "account_id": exact["account_id"], "symbol": symbol, "side": exact["side"],
            "filled_quantity": str(order.get("filled_qty")), "order_version": order_version(order)}
        validated_replacement(exact, runtime)
    snapshot = {"account": runtime.get("account"), "account_at": runtime.get("account_at"),
                "positions": runtime.get("positions"), "orders": runtime.get("orders"),
                "market": runtime.get("market_data", {}).get(symbol), "reconciliation": runtime.get("reconciliation")}
    revision = prior["revision"] + 1 if prior else 1
    event = {"action": "revise" if prior else "draft", "revision": revision, "at": stamp,
             "terms": exact, "terms_sha256": digest(exact), "reason": reason or rationale,
             "policy_revision": saved["policy"]["revision"], "observation_sha256": digest(snapshot),
             "observation": snapshot, "impact": impact(exact, runtime, saved["policy"]["rules"])}
    proposal = {"id": prior["id"] if prior else str(uuid4()), "revision": revision, "status": "draft",
                "created_at": prior["created_at"] if prior else stamp, "updated_at": stamp, "terms": exact,
                "terms_sha256": event["terms_sha256"], "policy_revision": event["policy_revision"],
                "impact": event["impact"], "approval": None, "broker_submitted": False,
                "conditions_stale": False, "history": (prior["history"] if prior else []) + [event]}
    if prior:
        saved["proposals"][saved["proposals"].index(prior)] = proposal
        invalidate_baskets(saved, prior["id"], stamp)
    else:
        saved["proposals"].insert(0, proposal)
    return saved
