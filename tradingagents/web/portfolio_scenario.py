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


def listing_dates():
    import json
    from pathlib import Path
    return json.loads(Path(__file__).with_name("portfolio_listing_dates.json").read_text(encoding="utf-8"))


def resolve_recipients(actions, symbols):
    """Use only same-issuer name changes to map recipients into the selected universe."""
    links = {}
    for items in actions.values():
        for item in items:
            if item["kind"] == "name_change":
                old, new = item["old_symbol"], item["new_symbol"]
                links.setdefault(old, set()).add(new)
                links.setdefault(new, set()).add(old)
    for items in actions.values():
        for item in items:
            recipient = item.get("new_symbol")
            if item["kind"] not in {"stock_distribution", "merger"} or not recipient:
                continue
            related, pending = {recipient}, [recipient]
            while pending:
                for name in links.get(pending.pop(), set()) - related:
                    related.add(name)
                    pending.append(name)
            matches = related.intersection(symbols)
            if len(matches) > 1:
                raise ValueError(f"{recipient} recipient: ambiguous same-issuer symbol mapping")
            if matches:
                item["provider_symbol"] = recipient
                item["new_symbol"] = matches.pop()


def action_observation(symbol, observation, load_artifact):
    """Re-read verified source pages so old observations use the same role mapping."""
    from .stock_evidence import corporate_action_records
    if not isinstance(observation, dict) or not observation.get("complete"):
        return observation
    records = []
    gaps = [gap for gap in observation.get("gaps", [])
            if not gap.startswith("Action has no exact selected-symbol association")]
    pages = observation.get("receipts", [])
    for index, receipt in enumerate(pages):
        payload = load_artifact(receipt["artifact"])
        if not isinstance(payload, dict) or bool(payload.get("next_page_token")) != (index < len(pages) - 1):
            raise ValueError(f"{symbol} corporate_actions.receipt: unavailable or incomplete provider pages")
        page_records, page_gaps = corporate_action_records(symbol, payload, receipt["source_url"])
        records.extend(page_records)
        gaps.extend(page_gaps)
    return {**observation, "records": records, "gaps": gaps}


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
        if kind == "name_changes":
            if not row.get("old_symbol") or not row.get("new_symbol"):
                raise ValueError(f"{symbol} corporate_actions.name_change: missing symbol mapping")
            actions.append({"kind": "name_change", "ex_date": None, "source_id": row.get("id"),
                "old_symbol": row["old_symbol"], "new_symbol": row["new_symbol"],
                "old_cusip": row.get("old_cusip"), "new_cusip": row.get("new_cusip")})
            continue
        event_date = row.get("ex_date") or row.get("effective_date")
        if event_date and not start <= date.fromisoformat(event_date) <= end:
            continue
        if kind in {"cash_mergers", "stock_mergers", "stock_and_cash_mergers"} and row.get("acquirer_symbol") == symbol and row.get("acquiree_symbol") not in {None, symbol}:
            effective = date.fromisoformat(row["effective_date"])
            if start <= effective <= end:
                actions.append({"kind": "issuer_acquisition", "ex_date": effective.isoformat(),
                    "target_symbol": row["acquiree_symbol"], "source_id": row.get("id"),
                    "basis": "Selected stock is the acquirer; this is not a distribution or conversion of its shareholders' holdings"})
            continue
        if kind == "unit_splits" and row.get("new_symbol") == symbol and row.get("old_symbol") not in {None, symbol}:
            actions.append({"kind": "issuer_acquisition", "ex_date": date.fromisoformat(event_date).isoformat(),
                "source_id": row.get("id"), "target_symbol": row["old_symbol"]})
            continue
        if kind == "spin_offs" and row.get("new_symbol") == symbol and row.get("source_symbol") not in {None, symbol}:
            actions.append({"kind": "issuer_distribution", "ex_date": date.fromisoformat(event_date).isoformat(),
                "source_id": row.get("id"), "source_symbol": row["source_symbol"]})
            continue
        if kind == "spin_offs" and row.get("source_symbol") == symbol and row.get("new_symbol") not in {None, symbol}:
            new, old = Decimal(str(row.get("new_rate"))), Decimal(str(row.get("source_rate")))
            if not new.is_finite() or not old.is_finite() or new <= 0 or old <= 0:
                raise ValueError(f"{symbol} {event_date} spin_off: invalid share ratio")
            actions.append({"kind": "stock_distribution", "ex_date": date.fromisoformat(event_date).isoformat(),
                "new_symbol": row["new_symbol"], "new": str(new), "old": str(old), "source_id": row.get("id"),
                "new_cusip": row.get("new_cusip"), "payable_date": row.get("payable_date")})
            continue
        if kind in {"cash_mergers", "stock_mergers", "stock_and_cash_mergers"} and row.get("acquiree_symbol") == symbol:
            cash_rate = Decimal(str(row.get("rate") if kind == "cash_mergers" else row.get("cash_rate", 0)))
            old = Decimal(1) if kind == "cash_mergers" else Decimal(str(row.get("acquiree_rate")))
            new = Decimal(0) if kind == "cash_mergers" else Decimal(str(row.get("acquirer_rate")))
            if not all(value.is_finite() for value in (cash_rate, old, new)) or cash_rate < 0 or old <= 0 or new < 0:
                raise ValueError(f"{symbol} {event_date} merger: invalid consideration")
            if new and not row.get("acquirer_symbol"):
                raise ValueError(f"{symbol} {event_date} merger: missing recipient symbol")
            actions.append({"kind": "merger", "ex_date": date.fromisoformat(event_date).isoformat(),
                "new_symbol": row.get("acquirer_symbol") if new else None, "new": str(new), "old": str(old),
                "cash_rate": str(cash_rate), "new_cusip": row.get("acquirer_cusip"),
                "payable_date": row.get("payable_date") or event_date, "source_id": row.get("id")})
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
    return sorted(actions, key=lambda item: (item["ex_date"] or "", item["kind"]))


def account_portfolio(bars, actions, fee_usd, native_fills, model):
    """Account for one synchronized hindsight portfolio; bars are validated raw daily marks."""
    from decimal import ROUND_FLOOR

    fee = Decimal(str(fee_usd))
    if not fee.is_finite() or fee < 0 or fee.as_tuple().exponent < -2:
        raise ValueError("transaction_cost.fee_usd: expected a nonnegative USD amount with at most two decimal places")
    weights = model_weights(validate_model(model))
    capital = Decimal(str(model["result"]["capital"]))
    symbols = tuple(bars)
    if not set(weights).issubset(bars) or set(actions) != set(bars):
        raise ValueError("portfolio inputs: bars and corporate actions are required for every positive allocation")
    dates = sorted({day for rows in bars.values() for day in rows})
    if not dates or any(not rows for rows in bars.values()):
        raise ValueError("portfolio bars: actual dated sessions are required")
    cash, shares, receivables = capital, dict.fromkeys(symbols, Decimal(0)), []
    events, curve = [], []
    entries = {}
    for symbol, weight in weights.items():
        first = min(bars[symbol])
        price = Decimal(str(bars[symbol][first]["close"]))
        if not price.is_finite() or price <= 0:
            raise ValueError(f"{symbol} {first} close: invalid")
        expected = (capital * weight / price).to_integral_value(rounding=ROUND_FLOOR)
        fill = native_fills.get(symbol) or {}
        if (Decimal(str(fill.get("shares", "-1"))) != expected or Decimal(str(fill.get("price", "-1"))) != price
                or Decimal(str(fill.get("fee_usd", "-1"))) != (fee if expected else 0)):
            raise ValueError(f"{symbol} {first} native_fill: expected {expected} shares at close {price} with fee {fee if expected else 0}; observed {fill}")
        entries.setdefault(first, []).append((symbol, expected, price))
    previous_day = ""
    for day in dates:
        opening_shares = shares.copy()
        day_actions = [(symbol, action) for symbol in symbols for action in actions[symbol]
            if action["ex_date"] and previous_day < action["ex_date"] <= day]
        day_actions.sort(key=lambda item: item[1]["kind"] != "split")
        for symbol, action in day_actions:
            quantity = opening_shares[symbol]
            if not quantity:
                continue
            if action["kind"] in {"issuer_acquisition", "issuer_distribution"}:
                events.append({"date": day, "symbol": symbol, **action})
            elif action["kind"] == "split":
                adjusted = quantity * Decimal(action["new"]) / Decimal(action["old"])
                shares[symbol] += adjusted - quantity
                opening_shares[symbol] = adjusted
                events.append({"date": day, "symbol": symbol, "kind": "split", "shares": str(adjusted)})
            elif action["kind"] == "dividend":
                receivables.append({"symbol": symbol, "payable_date": action["payable_date"], "amount": quantity * Decimal(action["rate"])})
            elif action["kind"] in {"stock_distribution", "merger"}:
                recipient = action.get("new_symbol")
                if recipient:
                    if recipient not in shares:
                        raise ValueError(f"{symbol} {day} recipient {recipient}: missing verified price history")
                    entitlement = quantity * Decimal(action["new"]) / Decimal(action["old"])
                    shares[recipient] += entitlement
                    events.append({"date": day, "symbol": symbol, "kind": action["kind"],
                        "recipient": recipient, "shares": str(entitlement), "source_id": action.get("source_id"),
                        "basis": "Share entitlement retained at raw daily value; no cash-in-lieu sale is assumed"})
                if action["kind"] == "merger":
                    receivables.append({"symbol": symbol, "payable_date": action["payable_date"],
                        "amount": quantity * Decimal(action["cash_rate"])})
                    shares[symbol] -= quantity
        for symbol, quantity, price in entries.get(day, []):
            shares[symbol] += quantity
            cash -= quantity * price + (fee if quantity else 0)
            events.append({"date": day, "symbol": symbol, "kind": "entry", "shares": str(quantity),
                "price": str(price), "fee_usd": str(fee if quantity else 0)})
        if cash < 0:
            raise ValueError(f"{day} transaction_cost.fee_usd: entry costs exceed available cash")
        due = [item for item in receivables if item["payable_date"] <= day]
        for item in due:
            cash += item["amount"]
            events.append({"date": item["payable_date"], "symbol": item["symbol"], "kind": "dividend_payment", "amount_usd": str(item["amount"])})
            receivables.remove(item)
        value = cash + sum(item["amount"] for item in receivables)
        for symbol in symbols:
            if not shares[symbol]:
                continue
            if day not in bars[symbol]:
                raise ValueError(f"{symbol} {day} close: missing mark for a held share entitlement")
            price = Decimal(str(bars[symbol][day]["close"]))
            if not price.is_finite() or price <= 0:
                raise ValueError(f"{symbol} {day} close: invalid")
            value += shares[symbol] * price
        curve.append({"date": day, "equity_usd": str(value), "cash_usd": str(cash)})
        previous_day = day
    return {"cash_usd": str(cash), "shares": {key: str(value) for key, value in shares.items()},
            "receivables": [{**item, "amount": str(item["amount"])} for item in receivables], "events": events, "equity_curve": curve}

