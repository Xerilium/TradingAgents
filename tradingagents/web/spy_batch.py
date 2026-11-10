"""Exact SPY batch authority backed by a fully reserved execution envelope."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class BatchStockDeferred(ValueError):
    pass


class BatchObservationPending(ValueError):
    pass


def sealed(batch):
    material = {key: value for key, value in batch.items() if key not in {"binding", "state", "reason"}}
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def consumed(state, approval):
    batch = state.get("spy_batches", {}).get(approval.get("spy_batch_id"))
    if not batch:
        return False
    member = batch["members"].get(approval.get("spy_command_id"))
    return bool(member and member["approval_id"] == approval["id"]
                and batch["granted_at"] >= approval["approved_at"]
                and (not approval["expires_at"] or batch["granted_at"] <= approval["expires_at"]))


def decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid SPY batch economics") from None
    if not result.is_finite():
        raise ValueError("Nonfinite SPY batch economics")
    return result


def cash_values(initial, executions):
    """Compare USD-cent broker cash with the executions represented by its holdings."""
    cash = decimal(initial)
    for event in sorted(executions, key=lambda row: (row["ts_event"], row["execution_id"])):
        cost = decimal(event["quantity"]) * decimal(event["price"])
        cash += cost * (-1 if event["side"] == "BUY" else 1) - decimal(event["commission"])
    return {cash.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)}


def isolated_commands(runtime, state):
    """Only an internal, exact SPY reservation snapshot can localize an unknown."""
    snapshots = runtime.get("_spy_isolated_commands", {})
    account = (runtime.get("account") or {}).get("id")
    for identity, snapshot in snapshots.items():
        command = state["commands"].get(identity, {})
        terms = command.get("terms", {})
        never_sent = (command.get("state") == "not_sent"
            and command.get("transport_attempt", {}).get("version") == 1
            and command["transport_attempt"].get("state") == "not_sent"
            and command["transport_attempt"].get("resolved_at")
            and not any(command.get(key) for key in ("broker_order_ids", "fill_ids", "native_deliveries", "native_pending_commitment", "pending_action"))
            and all(decimal(command.get(key)) == 0 for key in ("cash_commitment", "remaining_quantity", "filled_quantity")))
        if (any(command.get(key) != snapshot.get(key) for key in (
                "id", "account_id", "instrument_id", "symbol", "side", "terms", "terms_sha256", "client_order_id"))
                or any(command.get(key) != terms.get(key) for key in ("account_id", "instrument_id", "symbol", "side"))
                or command.get("terms_sha256") != hashlib.sha256(json.dumps(terms, sort_keys=True, allow_nan=False).encode()).hexdigest()
                or command.get("account_id") != account or terms.get("asset_class") == "us_option"
                or terms.get("side") not in {"BUY", "SELL"}
                or terms.get("order_class") not in (None, "simple")
                or terms.get("replacement") or terms.get("exit_plan") or command.get("pending_action")
                or command.get("connection_context") != snapshot.get("connection_context")
                or command.get("state") not in {"dispatch_intent", "submitting", "outcome_unknown", "accepted", "partially_filled", "filled", "canceled", "expired", "rejected"} and not never_sent
                or any(item.get("status") == "conflict" for item in command.get("native_deliveries", {}).values())
                or any(item.get("status") == "conflict" for item in runtime.get("native_deliveries", [])
                       if item.get("command_id") == identity)):
            raise ValueError("An isolated SPY command changed identity, authority or receipt proof")
        quantity = decimal(terms["quantity"])
        pending = command.get("native_pending_commitment", {})
        cash = max(decimal(command["cash_commitment"]), decimal(pending.get("cash_commitment", "0")))
        remaining = max(decimal(command["remaining_quantity"]), decimal(pending.get("remaining_quantity", "0")))
        if (quantity <= 0 or decimal(snapshot["reserved_quantity"]) != quantity
                or not 0 <= decimal(command["filled_quantity"]) <= quantity
                or not 0 <= remaining <= quantity or not 0 <= cash <= decimal(snapshot["reserved_cash"])
                or command["side"] == "BUY" and (
                    terms.get("order_type") != "LIMIT" or decimal(command["price_cap"]) != decimal(terms["limit_price"])
                    or decimal(snapshot["reserved_cash"]) < quantity * decimal(command["price_cap"]))):
            raise ValueError("The isolated SPY command no longer has a bounded full reservation")
    return set(snapshots)


def stock_local_recovery(runtime, state):
    isolated = isolated_commands(runtime, state)
    if not isolated or state.get("authority_history_incomplete") or runtime.get("local_record_error") or runtime.get("native_import_gap"):
        return False
    if (runtime.get("status") != "connected" or runtime.get("reconciliation", {}).get("status") != "reconciled"
            or not runtime.get("native_epoch") or state.get("native_epoch") != runtime["native_epoch"]
            or runtime.get("native_contract", {}).get("observation_in_progress") is True):
        return False
    confirmed = {item["command_id"] for item in runtime.get("native_deliveries", [])
                 if item.get("confirmed_current_process") is True and runtime.get("native_epoch")
                 and item.get("native_epoch") == runtime["native_epoch"]}
    for identity, command in state["commands"].items():
        if identity in isolated or command["state"] in {"filled", "canceled", "rejected", "expired", "not_sent"} and not command.get("native_pending_commitment"):
            continue
        if (command.get("account_id") != runtime["account"]["id"] or command.get("native_pending_commitment")
                or command["state"] in {"dispatch_intent", "submitting", "outcome_unknown", "cancel_pending", "replace_pending"}
                or command["state"] != "admitted_not_dispatched" and identity not in confirmed):
            return False
    return True


def validate(batch, records, runtime, *, command_id=None):
    state, investor = records["commands"], records["investor"]
    if batch["binding"] != sealed(batch) or batch["state"] not in {"reserved", "dispatching", "submitted"}:
        raise ValueError(batch.get("reason") or "SPY batch authority is blocked or changed")
    now = datetime.now(UTC)
    close = datetime.fromisoformat(batch["close_at"])
    account = runtime.get("account") or {}
    if (runtime.get("status") != "connected" or runtime.get("native_epoch") != batch["epoch"]
            or runtime.get("connection_session") != batch["epoch"] or runtime.get("endpoint") != batch["endpoint"]
            or account.get("id") != batch["account_id"] or runtime.get("market_open") is not True
            or now >= close or now.astimezone(close.tzinfo).date().isoformat() != batch["session"]):
        raise ValueError("SPY batch account, connection or approved regular session is no longer current")
    age = decimal((now - datetime.fromisoformat(runtime["account_at"])).total_seconds())
    if not 0 <= age <= decimal(batch["constraints"]["account_max_age_seconds"]):
        raise ValueError("SPY batch account observation exceeds its unchanged age limit")
    if runtime.get("local_record_error") or runtime.get("native_import_gap") or state.get("authority_history_incomplete"):
        raise ValueError(runtime.get("local_record_error") or runtime.get("native_import_gap") or "Authority recovery is incomplete")
    if runtime.get("trade_stream", {}).get("state") != "listening":
        raise ValueError("Current real-time broker connection is unavailable; reserved batch dispatch is stopped")
    if state.get("new_orders_blocked") or investor["policy"]["revision"] != batch["policy_revision"]:
        raise ValueError("SPY batch order authority or Trading Rules changed")
    for key, value in batch["baseline"]["account"].items():
        if account.get(key) != value:
            raise ValueError("External account identity, permission or trading-block change")
    risk = runtime.get("native_risk") or {}
    if (risk.get("status") != "available" or risk.get("values", {}).get("bypassed") is not False
            or risk["values"].get("trading_state") != "ACTIVE"):
        raise ValueError("Current native risk authority is unavailable or not active")
    owned = set(batch["members"]) | set(batch["baseline"]["tracked"])
    commands = state["commands"]
    isolated_commands({**runtime, "_spy_isolated_commands": batch["baseline"].get("quarantined", {})}, state)
    if command_id is not None and commands[command_id]["state"] not in {"dispatch_intent", "submitting"}:
        raise ValueError("This batch member no longer has unused dispatch authority")
    for identity, command in commands.items():
        if command.get("account_id") != batch["account_id"]:
            continue
        action = command.get("pending_action") or {}
        if (command["state"] in {"cancel_pending", "replace_pending"}
                or command["state"] == "outcome_unknown" and identity not in owned
                or action and action.get("state") not in {"completed", "not_sent"}
                or any(item.get("status") == "conflict" for item in command.get("native_deliveries", {}).values())):
            raise ValueError("A genuine unknown outcome, action or conflicting receipt blocks SPY dispatch")
        if identity not in owned and command["state"] in {
                "admitted_not_dispatched", "dispatch_intent", "submitting", "accepted", "partially_filled"}:
            raise ValueError("An unrelated working command blocks the reserved SPY batch")
    proposals = {item["id"]: item for item in investor["proposals"]}
    for identity, member in batch["members"].items():
        command = commands[identity]
        proposal = proposals.get(member["proposal_id"], {})
        approval = state["approvals"][member["approval_id"]]
        attempt = command.get("transport_attempt") or {}
        never_sent = (command["state"] == "not_sent" and attempt.get("version") == 1
            and attempt.get("state") == "not_sent" and attempt.get("resolved_at")
            and not any(command.get(key) for key in ("broker_order_ids", "fill_ids", "native_deliveries", "native_pending_commitment"))
            and decimal(command["filled_quantity"]) == 0 and decimal(command["cash_commitment"]) == 0)
        if (command.get("spy_batch_id") != batch["id"] or command["terms"] != member["terms"]
                or command["terms_sha256"] != member["terms_sha256"] or command["approval_id"] != member["approval_id"]
                or command["client_order_id"] != member["client_order_id"] or command["account_id"] != batch["account_id"]
                or command["instrument_id"] != member["terms"]["instrument_id"]
                or command["symbol"] != member["terms"]["symbol"] or command["side"] != member["terms"]["side"]
                or proposal.get("revision") != member["proposal_revision"] or proposal.get("status") != "draft"
                or proposal.get("terms") != member["terms"] or member["approval_id"] in state["revocations"] and not never_sent
                or approval.get("evaluation_binding_sha256") != member["evaluation_binding_sha256"]
                or approval.get("terms") != member["terms"] or approval["account_id"] != batch["account_id"]
                or not consumed(state, approval)):
            raise ValueError("An exact SPY batch proposal, approval or reserved command changed")
    facts = runtime.get("spy_batch_evidence", {}).get(batch["id"])
    if not facts or facts["native_epoch"] != batch["epoch"] or facts["foreign_native_orders"]:
        raise ValueError("Current native batch identity coverage is unavailable or contains an unrelated order")
    baseline = batch["baseline"]
    def uncovered(reason):
        if (runtime.get("native_contract", {}).get("observation_in_progress") is True
                or runtime.get("native_contract", {}).get("observation_retry_required") is True):
            raise BatchObservationPending(reason)
        raise ValueError(reason)

    executions, seen = [], set()
    for event in facts["executions"]:
        key = event["execution_id"]
        if key in seen:
            raise ValueError("Duplicate native batch execution identity")
        seen.add(key)
        if key in baseline["fill_ids"]:
            continue
        command = commands[event["command_id"]]
        if (event["command_id"] not in owned or event["proven"] is not True
                or event["side"] != command["side"] or event["symbol"] != command["symbol"]
                or decimal(event["quantity"]) <= 0 or decimal(event["price"]) <= 0
                or decimal(event["commission"]) < 0
                or command["side"] == "BUY" and decimal(event["price"]) > decimal(command["price_cap"])):
            uncovered("New execution lacks exact current native identity, economics or receipt proof")
        executions.append(event)
    for identity in owned:
        if sum((decimal(event["quantity"]) for event in facts["executions"]
                if event["command_id"] == identity), Decimal(0)) > decimal(commands[identity]["terms"]["quantity"]):
            raise ValueError("Native execution quantity exceeds the exact approved member quantity")
    expected = {key: decimal(value) for key, value in baseline["positions"].items()}
    prefixes = {key: {value} for key, value in expected.items()}
    levels = {key: {value: []} for key, value in expected.items()}
    symbol_events = {}
    spent = {}
    for event in sorted(executions, key=lambda row: (row["ts_event"], row["execution_id"])):
        symbol = event["symbol"]
        delta = decimal(event["quantity"]) * (1 if event["side"] == "BUY" else -1)
        expected[symbol] = expected.get(symbol, Decimal(0)) + delta
        prefixes.setdefault(symbol, {Decimal(0)}).add(expected[symbol])
        symbol_events.setdefault(symbol, []).append(event)
        levels.setdefault(symbol, {Decimal(0): []})[expected[symbol]] = list(symbol_events[symbol])
        spent[event["command_id"]] = spent.get(event["command_id"], Decimal(0)) + (
            decimal(event["quantity"]) * decimal(event["price"]) if event["side"] == "BUY" else Decimal(0)
        ) + decimal(event["commission"])
    native_positions = {key: decimal(value) for key, value in facts["positions"].items() if decimal(value) != 0}
    if native_positions != {key: value for key, value in expected.items() if value != 0}:
        uncovered("Native positions changed outside the batch's proven executions")
    positions = {row["symbol"]: decimal(row["qty"]) for row in runtime.get("positions", [])}
    if len(positions) != len(runtime.get("positions", [])) or any(value < 0 for value in positions.values()):
        raise ValueError("Duplicate or unsupported broker position identities")
    if any(positions.get(symbol, Decimal(0)) not in prefixes.get(symbol, {Decimal(0)})
           for symbol in set(positions) | set(prefixes)):
        uncovered("Broker holdings changed outside exact owned execution prefixes")
    observed_executions = [event for symbol in levels for event in levels[symbol][positions.get(symbol, Decimal(0))]]
    if decimal(account["cash"]) not in cash_values(baseline["cash"], observed_executions):
        uncovered("Broker cash changed outside exact owned executions; no cached balance is substituted")
    for row in runtime.get("fills", []):
        identity = row.get("execution_id") or row["id"]
        # Source identity normalization is supplied by the native snapshot.
        original = baseline.get("fills", {}).get(identity)
        if original is not None and any(row.get(key) != original.get(key) for key in ("order_id", "qty", "price", "transaction_time", "commission")):
            raise ValueError("An existing authoritative execution changed")
    allowed_orders = set(baseline["order_ids"]) | {
        key for identity in owned for key in commands[identity].get("broker_order_ids", [])}
    clients = {commands[identity]["client_order_id"] for identity in owned}
    if any(row["id"] not in allowed_orders and row.get("client_order_id") not in clients for row in runtime.get("orders", [])):
        raise ValueError("An unrelated broker order changed the batch account")
    floor = decimal(batch["reserve"])
    rule = investor["policy"]["rules"].get("cash_reserve_pct", {})
    if rule.get("state") == "enabled":
        floor = max(floor, decimal(account["equity"]) * decimal(rule["value"]) / 100)
    obligation = Decimal(0)
    for identity, reservation in batch["reservations"].items():
        command = commands[identity]
        remaining = max(Decimal(0), decimal(command["terms"]["quantity"]) - sum(
            (decimal(event["quantity"]) for event in facts["executions"] if event["command_id"] == identity), Decimal(0)))
        # Price improvements, sales and unacknowledged releases never finance another leg.
        obligation += max(decimal(reservation), spent.get(identity, Decimal(0)) + (
            remaining * decimal(command["price_cap"]) if command["side"] == "BUY" else Decimal(0)))
    if decimal(baseline["cash"]) - obligation < floor:
        raise ValueError("The complete reserved batch no longer protects the required cash floor")
    if command_id is not None:
        member = batch["members"][command_id]
        terms = member["terms"]
        market = runtime.get("market_data", {}).get(terms["symbol"], {})
        if market.get("trade_supported") is not True or market.get("instrument") is None:
            raise BatchStockDeferred("Current tradable instrument evidence is unavailable")
        quote = market.get("quote") or {}
        trade = market.get("trade") or {}
        event = quote.get("ts_event") or trade.get("ts_event")
        age = decimal(now.timestamp()) - decimal(event) / Decimal(1_000_000_000) if event else None
        if age is None or not 0 <= age <= decimal(batch["constraints"]["quote_max_age_seconds"]):
            raise BatchStockDeferred("Current quote exceeds the unchanged freshness limit")
        for name in ("max_spread_bps", "min_quote_size", "session_freshness"):
            rule = investor["policy"]["rules"].get(name, {})
            if rule.get("state") != "enabled":
                continue
            limit = decimal(rule["value"])
            if name == "session_freshness":
                valid = age <= limit
            else:
                quote_age = decimal(now.timestamp()) - decimal(quote["ts_event"]) / Decimal(1_000_000_000) if quote.get("ts_event") else None
                valid = quote_age is not None and 0 <= quote_age <= decimal(rule["max_quote_age_seconds"])
                if name == "min_quote_size":
                    valid = valid and quote.get("ask_size") is not None and decimal(quote["ask_size"]) >= limit
                else:
                    bid, ask = quote.get("bid_price"), quote.get("ask_price")
                    valid = valid and bid is not None and ask is not None and 0 < decimal(bid) <= decimal(ask)
                    valid = valid and (decimal(ask) - decimal(bid)) / ((decimal(ask) + decimal(bid)) / 2) * 10000 <= limit
            if not valid:
                raise BatchStockDeferred(f"{name}: current stock-local evidence failed")
    return batch
