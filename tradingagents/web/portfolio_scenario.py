"""Validation for the fixed modeled-portfolio hindsight scenario."""

from datetime import date
from decimal import Decimal, InvalidOperation

def validate_model(model):
    if not isinstance(model, dict) or not isinstance(model.get("id"), str) or not model["id"].strip():
        raise ValueError("Model archive: expected an object with its original id")
    inputs = model.get("inputs")
    result = model.get("result")
    if not isinstance(inputs, list) or not inputs or not isinstance(result, dict):
        raise ValueError("Model archive: missing inputs or result")
    allocations = result.get("allocations")
    if not isinstance(allocations, list) or len(inputs) != len(allocations):
        raise ValueError("Model archive: input and allocation counts differ")
    try:
        symbols = [row["symbol"] for row in inputs]
        weights = {row["symbol"]: Decimal(str(row["weight"])) for row in allocations}
        capital = Decimal(str(result["capital"]))
        cash = Decimal(str(result["target_cash_weight"]))
        if (any(not isinstance(symbol, str) or not symbol.strip() for symbol in symbols)
                or len(set(symbols)) != len(symbols) or len(weights) != len(allocations)
                or set(symbols) != set(weights) or not capital.is_finite() or capital <= 0
                or not cash.is_finite() or cash < 0 or cash > 1
                or any(not weight.is_finite() or weight < 0 or weight > 1 for weight in weights.values())
                or sum(weights.values(), cash) != 1 or not any(weights.values())):
            raise ValueError("Model archive: invalid symbols, capital or weights")
    except (KeyError, TypeError, InvalidOperation) as error:
        raise ValueError("Model archive: invalid symbols, capital or weights") from error
    return model


def model_weights(model):
    return {row["symbol"]: Decimal(str(row["weight"])) for row in model["result"]["allocations"] if Decimal(str(row["weight"])) > 0}


def parse_actions(symbol, start, end, observation):
    """Reject unproven coverage or unsupported action types; never infer events from bars."""
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if not isinstance(observation, dict):
        raise ValueError(f"{symbol} {start}..{end} corporate_actions.coverage: no complete matching provider receipt")
    request = observation.get("request") or {}
    if (observation.get("symbol") != symbol or observation.get("provider") != "alpaca"
            or observation.get("complete") is not True or observation.get("status") not in {"available", "missing"}
            or not observation.get("receipts")
            or any("Provider may publish actions after announcement" not in gap for gap in observation.get("gaps", []))
            or request.get("start", "9999") > start.isoformat() or request.get("end", "") < end.isoformat()):
        raise ValueError(f"{symbol} {start}..{end} corporate_actions.coverage: no complete matching provider receipt")
    actions = []
    for record in observation.get("records", []):
        row, kind = record.get("reported") or {}, record.get("kind", "")
        if kind == "cash_mergers" and row.get("acquirer_symbol") == symbol and row.get("acquiree_symbol") not in {None, symbol}:
            effective = date.fromisoformat(row["effective_date"])
            if start <= effective <= end:
                actions.append({"kind": "issuer_acquisition", "ex_date": effective.isoformat(),
                    "target_symbol": row["acquiree_symbol"], "source_id": row.get("id"),
                    "basis": "Selected stock is the acquirer; this is not a distribution or conversion of its shareholders' holdings"})
            continue
        if kind not in {"cash_dividends", "forward_splits", "reverse_splits"}:
            raise ValueError(f"{symbol} {row.get('ex_date') or row.get('effective_date') or 'unknown'} corporate_actions.kind: unsupported {kind}")
        def field(name):
            value = row.get(name)
            if value is None or value == "":
                raise ValueError(f"{symbol} {row.get('ex_date') or 'unknown'} {name}: missing")
            return value
        try:
            ex = date.fromisoformat(field("ex_date"))
            if kind == "cash_dividends":
                payable = date.fromisoformat(field("payable_date"))
                rate = Decimal(str(field("rate")))
                if payable < ex or not rate.is_finite() or rate < 0:
                    raise ValueError(f"{symbol} {ex} rate/payable_date: invalid")
                action = {"kind": "dividend", "ex_date": ex.isoformat(), "payable_date": payable.isoformat(), "rate": str(rate)}
            else:
                new, old = Decimal(str(field("new_rate"))), Decimal(str(field("old_rate")))
                if not new.is_finite() or not old.is_finite() or new <= 0 or old <= 0:
                    raise ValueError(f"{symbol} {ex} new_rate/old_rate: invalid")
                action = {"kind": "split", "ex_date": ex.isoformat(), "new": str(new), "old": str(old)}
        except (InvalidOperation, TypeError) as error:
            raise ValueError(f"{symbol} {row.get('ex_date') or 'unknown'} corporate_actions.field: invalid") from error
        if start <= ex <= end:
            actions.append(action)
    return sorted(actions, key=lambda item: (item["ex_date"], item["kind"]))


def account_portfolio(bars, actions, fee_usd, native_fills, model):
    """Account for one synchronized hindsight portfolio; bars are validated raw daily marks."""
    from decimal import ROUND_FLOOR

    fee = Decimal(str(fee_usd))
    if not fee.is_finite() or fee < 0 or fee.as_tuple().exponent < -2:
        raise ValueError("transaction_cost.fee_usd: expected a nonnegative USD amount with at most two decimal places")
    weights = model_weights(validate_model(model))
    capital = Decimal(str(model["result"]["capital"]))
    symbols = tuple(weights)
    if set(bars) != set(symbols) or set(actions) != set(symbols):
        raise ValueError("portfolio inputs: bars and corporate actions are required for every positive allocation")
    dates = sorted(bars[symbols[0]])
    if not dates or any(set(bars[symbol]) != set(dates) for symbol in symbols):
        raise ValueError("portfolio bars: every symbol must have the same actual dated sessions")
    for symbol in symbols:
        for action in actions[symbol]:
            if action["ex_date"] not in dates:
                raise ValueError(f"{symbol} {action['ex_date']} ex_date: no synchronized session mark")
    cash, shares, receivables = capital, {}, []
    events, curve = [], []
    for symbol in symbols:
        price = Decimal(str(bars[symbol][dates[0]]["close"]))
        if not price.is_finite() or price <= 0:
            raise ValueError(f"{symbol} {dates[0]} close: invalid")
        expected = (capital * weights[symbol] / price).to_integral_value(rounding=ROUND_FLOOR)
        fill = native_fills.get(symbol) or {}
        if (Decimal(str(fill.get("shares", "-1"))) != expected or Decimal(str(fill.get("price", "-1"))) != price
                or Decimal(str(fill.get("fee_usd", "-1"))) != (fee if expected else 0)):
            raise ValueError(f"{symbol} {dates[0]} native_fill: expected {expected} shares at close {price} with fee {fee if expected else 0}; observed {fill}")
        shares[symbol] = expected
        cost = shares[symbol] * price + (fee if shares[symbol] else 0)
        cash -= cost
        events.append({"date": dates[0], "symbol": symbol, "kind": "entry", "shares": str(shares[symbol]), "price": str(price), "fee_usd": str(fee if shares[symbol] else 0)})
    if cash < 0:
        raise ValueError(f"{dates[0]} transaction_cost.fee_usd: entry costs exceed available cash")
    for day in dates:
        for symbol in symbols:
            for action in actions[symbol]:
                if action["ex_date"] != day:
                    continue
                if day == dates[0]:
                    continue
                if action["kind"] == "issuer_acquisition":
                    events.append({"date": day, "symbol": symbol, **action})
                elif action["kind"] == "split":
                    quantity = shares[symbol] * Decimal(action["new"]) / Decimal(action["old"])
                    if quantity != quantity.to_integral_value():
                        raise ValueError(f"{symbol} {day} splitnew_rate/splitold_rate: fractional entitlement requires explicit cash-in-lieu evidence")
                    shares[symbol] = quantity
                    events.append({"date": day, "symbol": symbol, "kind": "split", "shares": str(quantity)})
                elif action["kind"] == "dividend":
                    receivables.append({"symbol": symbol, "payable_date": action["payable_date"], "amount": shares[symbol] * Decimal(action["rate"])})
        due = [item for item in receivables if item["payable_date"] <= day]
        for item in due:
            cash += item["amount"]
            events.append({"date": item["payable_date"], "symbol": item["symbol"], "kind": "dividend_payment", "amount_usd": str(item["amount"])})
            receivables.remove(item)
        value = cash + sum(item["amount"] for item in receivables)
        for symbol in symbols:
            price = Decimal(str(bars[symbol][day]["close"]))
            if not price.is_finite() or price <= 0:
                raise ValueError(f"{symbol} {day} close: invalid")
            value += shares[symbol] * price
        curve.append({"date": day, "equity_usd": str(value), "cash_usd": str(cash)})
    return {"cash_usd": str(cash), "shares": {key: str(value) for key, value in shares.items()},
            "receivables": [{**item, "amount": str(item["amount"])} for item in receivables], "events": events, "equity_curve": curve}

