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


def entry_quantity(capital, weight, price, sizing="whole"):
    from decimal import ROUND_FLOOR
    if sizing not in {"whole", "fractional"}:
        raise ValueError("Share sizing must be whole or fractional")
    step = Decimal("0.000000001") if sizing == "fractional" else Decimal(1)
    return (Decimal(str(capital)) * weight / Decimal(str(price))).quantize(step, rounding=ROUND_FLOOR)


def parse_actions(symbol, start, end, observation, *, load_artifact=None, initial_shares=None, cusip=None):
    """Reject unproven coverage or unsupported action types; never infer events from bars."""
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if not isinstance(observation, dict):
        raise ValueError(f"{symbol} {start}..{end} corporate_actions.coverage: no complete matching provider receipt")
    if load_artifact is not None and any(gap.startswith("Action has no exact selected-symbol association") for gap in observation.get("gaps", [])):
        # Reinterpret the immutable provider pages with the corrected role mapping.
        # Never edit the original observation or erase an unresolved coverage gap.
        from .stock_evidence import corporate_action_records
        records, gaps = [], [gap for gap in observation["gaps"] if not gap.startswith("Action has no exact selected-symbol association")]
        pages = observation.get("receipts", [])
        for index, receipt in enumerate(pages):
            payload = load_artifact(receipt["artifact"])
            if not isinstance(payload, dict) or bool(payload.get("next_page_token")) != (index < len(pages) - 1):
                raise ValueError(f"{symbol} corporate_actions.receipt: unavailable or incomplete provider pages")
            page_records, page_gaps = corporate_action_records(symbol, payload, receipt["source_url"])
            records.extend(page_records)
            gaps.extend(page_gaps)
        observation = {**observation, "records": records, "gaps": gaps}
    request = observation.get("request") or {}
    if (observation.get("symbol") != symbol or observation.get("provider") != "alpaca"
            or observation.get("complete") is not True or observation.get("status") not in {"available", "missing"}
            or not observation.get("receipts")
            or any("Provider may publish actions after announcement" not in gap for gap in observation.get("gaps", []))
            or request.get("start", "9999") > start.isoformat() or request.get("end", "") < end.isoformat()):
        raise ValueError(f"{symbol} {start}..{end} corporate_actions.coverage: no complete matching provider receipt")
    identities = {cusip} if cusip else set()
    # Only link CUSIPs reported for the same issuer, never merger or spin-off parties.
    links = []
    for record in observation.get("records", []):
        row, kind = record.get("reported") or {}, record.get("kind")
        old, new = row.get("old_cusip"), row.get("new_cusip")
        same_split = kind in {"forward_splits", "reverse_splits"} and (row.get("symbol") == symbol or row.get("old_symbol") == row.get("new_symbol") == symbol)
        rename = kind == "name_changes" and symbol in {row.get("old_symbol"), row.get("new_symbol")}
        if old and new and (same_split or rename):
            links.append((old, new))
    while True:
        expanded = identities | {value for pair in links if identities.intersection(pair) for value in pair}
        if expanded == identities:
            break
        identities = expanded
    actions = []
    for record in observation.get("records", []):
        row, kind = record.get("reported") or {}, record.get("kind", "")
        identity = row.get("cusip") or (row.get("acquiree_cusip") if row.get("acquiree_symbol") == symbol else row.get("acquirer_cusip") if row.get("acquirer_symbol") == symbol else row.get("source_cusip") if row.get("source_symbol") == symbol else None)
        if cusip and identity and identity not in identities:
            continue
        if kind == "name_changes":
            # Provider-mapped historical bars already follow the underlying issuer.
            # A name/CUSIP change has no reported share ratio or cash entitlement.
            # Keep its full receipt in the preview; do not invent an effective date.
            if not row.get("old_symbol") or not row.get("new_symbol") or symbol not in {row["old_symbol"], row["new_symbol"]}:
                raise ValueError(f"{symbol} corporate_actions.name_change: invalid symbol mapping")
            continue
        effective = date.fromisoformat(row.get("ex_date") or row.get("effective_date") or "")
        # This portfolio is first bought at the opening date's completed close.
        if effective <= start or effective > end:
            continue
        if kind in {"cash_mergers", "stock_mergers", "stock_and_cash_mergers"} and row.get("acquirer_symbol") == symbol and row.get("acquiree_symbol") not in {None, symbol}:
            actions.append({"kind": "issuer_acquisition", "ex_date": effective.isoformat(),
                "target_symbol": row["acquiree_symbol"], "source_id": row.get("id"),
                "basis": "Selected stock is the acquirer; this is not a distribution or conversion of its shareholders' holdings"})
            continue
        if kind == "unit_splits" and row.get("new_symbol") == symbol and row.get("old_symbol") != symbol:
            actions.append({"kind": "issuer_acquisition", "ex_date": effective.isoformat(), "source_id": row.get("id")})
            continue
        if kind in {"cash_mergers", "stock_mergers", "stock_and_cash_mergers"} and row.get("acquiree_symbol") == symbol:
            cash_rate = Decimal(str(row.get("rate") if kind == "cash_mergers" else row.get("cash_rate", 0)))
            old = Decimal(str(row.get("acquiree_rate", 1)))
            new = Decimal(str(row.get("acquirer_rate", 0)))
            if not all(value.is_finite() for value in (cash_rate, old, new)) or cash_rate < 0 or old <= 0 or new < 0:
                raise ValueError(f"{symbol} {effective} merger: invalid consideration")
            actions.append({"kind": "merger", "ex_date": effective.isoformat(), "new_symbol": row.get("acquirer_symbol") if new else None,
                "new": str(new), "old": str(old), "cash_rate": str(cash_rate), "payable_date": row.get("payable_date") or effective.isoformat(), "source_id": row.get("id")})
            continue
        if kind == "spin_offs" and row.get("source_symbol") == symbol and row.get("new_symbol") not in {None, symbol}:
            if initial_shares == 0:
                actions.append({"kind": "no_position_action", "ex_date": effective.isoformat(), "source_kind": kind,
                    "source_id": row.get("id"), "basis": "Whole-share entry bought zero shares; this action has no portfolio entitlement"})
                continue
            new, old = Decimal(str(row["new_rate"])), Decimal(str(row["source_rate"]))
            if not new.is_finite() or not old.is_finite() or new <= 0 or old <= 0:
                raise ValueError(f"{symbol} {effective} spin_off ratio: invalid")
            actions.append({"kind": "stock_distribution", "ex_date": effective.isoformat(),
                "new_symbol": row["new_symbol"], "new": str(new), "old": str(old), "source_id": row.get("id"),
                "payable_date": row.get("payable_date"), "basis": "Entitlement valued from ex-date; not a broker settlement record"})
            continue
        if kind == "spin_offs" and row.get("new_symbol") == symbol and row.get("source_symbol") not in {None, symbol}:
            actions.append({"kind": "issuer_creation", "ex_date": effective.isoformat(), "source_id": row.get("id"),
                "basis": "Receipt identifies the issued security; entitlement is accounted against holdings of its parent"})
            continue
        if kind not in {"cash_dividends", "forward_splits", "reverse_splits"}:
            if initial_shares == 0:
                actions.append({"kind": "no_position_action", "ex_date": effective.isoformat(), "source_kind": kind,
                    "source_id": row.get("id"), "basis": "Whole-share entry bought zero shares; this action has no portfolio entitlement"})
                continue
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


def account_portfolio(bars, actions, fee_usd, native_fills, model, sizing="whole", calendar=None):
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
    dates = list(calendar) if calendar is not None else sorted(set().union(*(set(rows) for rows in bars.values())))
    if dates != sorted(set(dates)) or any(set(rows) - set(dates) for rows in bars.values()):
        raise ValueError("portfolio calendar: duplicate, unordered or off-calendar sessions")
    if not dates or any(dates[0] not in bars[symbol] for symbol in weights):
        raise ValueError("portfolio bars: every initial allocation requires an opening session mark")
    for symbol in symbols:
        for action in actions[symbol]:
            if not any(day >= action["ex_date"] for day in dates):
                raise ValueError(f"{symbol} {action['ex_date']} ex_date: no subsequent session")
    cash, shares, receivables = capital, dict.fromkeys(symbols, Decimal(0)), []
    events, curve = [], []
    for symbol in weights:
        price = Decimal(str(bars[symbol][dates[0]]["close"]))
        if not price.is_finite() or price <= 0:
            raise ValueError(f"{symbol} {dates[0]} close: invalid")
        expected = entry_quantity(capital, weights[symbol], price, sizing)
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
        opening_shares = shares.copy()
        for symbol in symbols:
            for action in actions[symbol]:
                if day != next((session for session in dates if session >= action["ex_date"]), None):
                    continue
                if day == dates[0]:
                    continue
                if action["kind"] in {"issuer_acquisition", "issuer_creation", "no_position_action"}:
                    if action["kind"] == "no_position_action" and shares[symbol] != 0:
                        raise ValueError(f"{symbol} {day} corporate_actions: ignored event has a nonzero holding")
                    events.append({"date": day, "symbol": symbol, **action})
                elif action["kind"] == "stock_distribution":
                    quantity = shares[symbol] * Decimal(action["new"]) / Decimal(action["old"])
                    if sizing == "whole" and quantity != quantity.to_integral_value():
                        raise ValueError(f"{symbol} {day} distribution: fractional entitlement requires fractional sizing or cash-in-lieu evidence")
                    shares[action["new_symbol"]] += quantity
                    events.append({"date": day, "symbol": symbol, **action, "shares_received": str(quantity)})
                elif action["kind"] == "merger":
                    quantity = shares[symbol]
                    if action["new_symbol"]:
                        shares[action["new_symbol"]] += quantity * Decimal(action["new"]) / Decimal(action["old"])
                    amount = quantity * Decimal(action["cash_rate"])
                    if amount:
                        receivables.append({"symbol": symbol, "payable_date": action["payable_date"], "amount": amount})
                    shares[symbol] = Decimal(0)
                    events.append({"date": day, "symbol": symbol, **action, "shares_converted": str(quantity), "amount_usd": str(amount)})
                elif action["kind"] == "split":
                    quantity = shares[symbol] * Decimal(action["new"]) / Decimal(action["old"])
                    if sizing == "whole" and quantity != quantity.to_integral_value():
                        raise ValueError(f"{symbol} {day} splitnew_rate/splitold_rate: fractional entitlement requires explicit cash-in-lieu evidence")
                    shares[symbol] = quantity
                    events.append({"date": day, "symbol": symbol, "kind": "split", "shares": str(quantity)})
                elif action["kind"] == "dividend":
                    receivables.append({"symbol": symbol, "payable_date": action["payable_date"], "amount": opening_shares[symbol] * Decimal(action["rate"])})
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
                raise ValueError(f"{symbol} {day} close: missing while position is held")
            price = Decimal(str(bars[symbol][day]["close"]))
            if not price.is_finite() or price <= 0:
                raise ValueError(f"{symbol} {day} close: invalid")
            value += shares[symbol] * price
        curve.append({"date": day, "equity_usd": str(value), "cash_usd": str(cash)})
    return {"cash_usd": str(cash), "shares": {key: str(value) for key, value in shares.items()},
            "receivables": [{**item, "amount": str(item["amount"])} for item in receivables], "events": events, "equity_curve": curve}

