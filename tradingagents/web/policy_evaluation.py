"""Hypothetical exposure and policy calculations over observed state, never a ledger."""

from datetime import UTC, datetime
from decimal import Decimal

from .investor import RULES, decimal, execution_costs, price_evidence, working_commitments, validated_replacement, remaining_quantity


def evaluate(terms, policy, runtime, commands, history, evidence, constraints, artifact, proposed_legs=None):
    from .admission import ACTIVE, instant
    checks, source_refs = [], {}
    def check(name, passed, reason, details=None):
        checks.append({"name": name, "passed": bool(passed), "reason": reason, "details": details})
    def fresh(timestamp, maximum):
        try:
            age = Decimal(str((datetime.now(UTC) - instant(timestamp)).total_seconds()))
            limit = decimal(maximum)
            return limit is not None and limit > 0 and 0 <= age <= limit
        except (ValueError, TypeError, AttributeError):
            return False
    symbol = terms["symbol"]
    account = runtime.get("account") or {}
    rec = runtime.get("reconciliation", {})
    positions = {p["symbol"]: p for p in runtime.get("positions", [])}
    equity, cash = decimal(account.get("equity")), decimal(account.get("cash"))
    known = runtime.get("status") == "connected" and rec.get("positions_reconciled") is True and rec.get("orders_reconciled") is True
    quantities, current_values, marks = {}, {}, {}
    for name, position in positions.items():
        quantity, value = decimal(position.get("qty")), decimal(position.get("market_value"))
        if quantity is None or quantity < 0 or position.get("import_error"):
            known = False
            continue
        quantities[name], current_values[name] = quantity, value
        marks[name] = value / quantity if quantity > 0 and value is not None else None
    quote = runtime.get("market_data", {}).get(symbol, {}).get("quote") or {}
    bid, ask = decimal(quote.get("bid_price")), decimal(quote.get("ask_price"))
    cap, fee = execution_costs(terms, runtime, constraints)
    selected_price = price_evidence(terms, runtime)
    preview_price_basis = selected_price["basis"]
    commitments, commitments_known = working_commitments(runtime, commands, constraints)
    known = known and commitments_known
    pending_qty, pending_buys, pending_sells = {}, {}, {}
    reserved_cash = sum((item["cash"] for item in commitments), Decimal(0))
    pending_fees = sum((item["fee"] for item in commitments if item["fee"] is not None), Decimal(0))
    for item in commitments:
        name, remaining = item["symbol"], item["remaining"]
        if marks.get(name) is None and item["price"] is not None:
            marks[name] = item["price"]
        pending_qty[name] = pending_qty.get(name, Decimal(0)) + remaining * (1 if item["side"] == "BUY" else -1)
        if item["side"] == "BUY":
            pending_buys[name] = pending_buys.get(name, Decimal(0)) + item["cash"]
        else:
            pending_sells[name] = pending_sells.get(name, Decimal(0)) + remaining
    legs = proposed_legs if proposed_legs is not None else [{"terms": terms, "price_cap": cap, "fee": fee}]
    proposed_buys, proposed_sells, deltas, charges, principals = {}, {}, {}, [], []
    sellable = True
    for leg in legs:
        term = leg["terms"]
        name, quantity, ceiling, charge = term["symbol"], remaining_quantity(term), decimal(leg.get("price_cap")), decimal(leg.get("fee"))
        try:
            predecessor = validated_replacement(term, runtime)
        except ValueError:
            predecessor, known = None, False
        old = next((item for item in commitments if predecessor and predecessor["id"] in item["order_ids"]), None)
        if quantity is None or ceiling is None or ceiling <= 0 or charge is not None and charge < 0 or predecessor and old is None:
            known = False
            continue
        value = quantity * ceiling
        principals.append(value)
        charges.append(charge)
        previous = old["remaining"] if old else Decimal(0)
        if old:
            reserved_cash -= old["cash"]
            pending_qty[name] -= previous * (1 if old["side"] == "BUY" else -1)
            if old["side"] == "BUY":
                pending_buys[name] -= old["cash"]
            else:
                pending_sells[name] -= previous
        deltas[name] = deltas.get(name, Decimal(0)) + quantity * (1 if term["side"] == "BUY" else -1)
        new_reserve = (value if term["side"] == "BUY" else Decimal(0)) + (charge if charge is not None else Decimal(0))
        # Replace reserves the larger alternative, never both predecessor and successor.
        reserved_cash += max(old["cash"] if old else Decimal(0), new_reserve)
        if term["side"] == "BUY":
            proposed_buys[name] = proposed_buys.get(name, Decimal(0)) + max(old["cash"] if old else Decimal(0), value)
        else:
            sellable = sellable and pending_sells.get(name, Decimal(0)) + max(previous, quantity) <= quantities.get(name, Decimal(0))
            pending_sells[name] = pending_sells.get(name, Decimal(0)) + max(previous, quantity)
            proposed_sells[name] = proposed_sells.get(name, Decimal(0)) + (min(previous, quantity) if old else quantity)
        mark = price_evidence({**term, "order_type": "MARKET"}, runtime)["price"]
        if marks.get(name) is None:
            marks[name] = mark if mark is not None else ceiling
    principal = sum(principals, Decimal(0)) if known and len(principals) == len(legs) else None
    fees_known = all(charge is not None and charge >= 0 for charge in charges) and len(charges) == len(legs)
    fee = sum((charge for charge in charges if charge is not None), Decimal(0))
    cash_after = cash - reserved_cash if cash is not None and known and principal is not None else None
    pending = {s: quantities.get(s, Decimal(0)) + pending_qty.get(s, Decimal(0)) for s in set(quantities) | set(pending_qty)}
    proposed = {s: pending.get(s, Decimal(0)) + deltas.get(s, Decimal(0)) for s in set(pending) | set(deltas)}
    check("account_commitments", known and sellable and cash_after is not None and cash_after >= 0 and all(q >= 0 for q in proposed.values()),
          "Current, pending and proposed quantities must be known, long-only and affordable without crediting sale proceeds")
    scenarios = {}
    for label, holdings in (("current", quantities), ("pending", pending), ("proposed", proposed)):
        values = {s: q * marks[s] if marks.get(s) is not None else None for s, q in holdings.items() if q != 0}
        scenarios[label] = {"quantities": {s: str(q) for s, q in holdings.items()},
                            "market_values": {s: str(v) if v is not None else None for s, v in values.items()},
                            "gross_exposure": str(sum((abs(v) for v in values.values()), Decimal(0))) if known and all(v is not None for v in values.values()) else None}
    conservative = {}
    for name in set(current_values) | set(pending_buys) | set(proposed_buys) | set(proposed_sells):
        current = current_values.get(name, Decimal(0))
        relief = proposed_sells.get(name, Decimal(0))
        value = max(Decimal(0), current - (relief * marks[name] if relief else Decimal(0))) if current is not None and (not relief or marks.get(name) is not None) else None
        conservative[name] = value + pending_buys.get(name, Decimal(0)) + proposed_buys.get(name, Decimal(0)) if value is not None else None
    exposure_known = known and all(value is not None for value in conservative.values())
    gross = sum(conservative.values(), Decimal(0)) if exposure_known and principal is not None else None
    position = max(conservative.values(), default=Decimal(0)) if exposure_known and principal is not None else None
    for key, label in RULES.items():
        rule = policy.get("rules", {}).get(key, {})
        state, limit = rule.get("state", "unset"), decimal(rule.get("value"))
        passed, reason, details = False, label + " is unset or required source inputs are unavailable", None
        if state in {"unset", "disabled"}:
            check(key, True, "Optional check not configured" if state == "unset" else "Investor chose not to apply this check")
            continue
        if state != "enabled" or limit is None or equity is None or equity <= 0 or not known:
            check(key, False, reason)
            continue
        if key in {"cash_reserve_pct", "max_position_pct", "max_gross_exposure_pct"}:
            value = cash_after if key == "cash_reserve_pct" else position if key == "max_position_pct" else gross
            if value is not None:
                pct = value / equity * 100
                passed = pct >= limit if key == "cash_reserve_pct" else pct <= limit
                reason, details = "Conservative source exposure/commitment calculation", {"value": str(value), "equity_pct": str(pct), "limit_pct": str(limit)}
        elif key == "loss_limit_pct":
            pnl = [decimal(p.get("unrealized_pl")) for p in positions.values()]
            costs = [decimal(p.get("cost_basis")) for p in positions.values()]
            if all(v is not None for v in pnl + costs):
                base = sum(costs, Decimal(0))
                loss = -sum(pnl, Decimal(0)) / base * 100 if base > 0 else None
                passed = not positions or loss is not None and loss <= limit
                reason = "Current broker-reported aggregate unrealized loss / reported cost; no future loss guarantee"
                details = {"loss_pct": str(loss) if loss is not None else None, "not_applicable": not positions}
        elif key == "scenario_loss_pct":
            shock = decimal(rule.get("shock_pct"))
            if shock is not None and 0 <= shock <= 100 and rule.get("method") == "parallel_long_equity_price_shock":
                outputs = {}
                for name, scenario in scenarios.items():
                    exposure = decimal(scenario["gross_exposure"])
                    loss = exposure * shock / 100 + (fee if name == "proposed" else 0) if exposure is not None else None
                    outputs[name] = {"loss_estimate": str(loss) if loss is not None else None,
                                     "equity_loss_pct": str(loss / equity * 100) if loss is not None else None}
                # A basket is non-atomic: buys may fill while every proposed/working sale remains unfilled.
                before_sales = gross + sum((proposed_sells.get(name, Decimal(0)) * marks[name] for name in proposed_sells), Decimal(0)) if gross is not None else None
                worst = before_sales * shock / 100 + pending_fees + fee if before_sales is not None else None
                outputs["buys_without_sale_relief"] = {"loss_estimate": str(worst) if worst is not None else None,
                    "equity_loss_pct": str(worst / equity * 100) if worst is not None else None}
                available = outputs["buys_without_sale_relief"]["equity_loss_pct"]
                passed = available is not None and Decimal(available) <= limit
                reason, details = "Investor-configured adverse long-equity price scenario; estimated loss, not a guaranteed loss cap", {"shock_pct": str(shock), "states": outputs}
        elif key == "max_sector_pct":
            sectors, complete = {}, rule.get("classification") == "provider_sector"
            exposures = conservative
            for name, value in exposures.items():
                if value == 0:
                    continue
                if value is None:
                    complete = False
                    continue
                meta = evidence.get("observations", {}).get(name, {}).get("classification", {})
                source = artifact(meta.get("artifact", {}))
                sector = next((r.get("value") for r in (source or {}).get("records", []) if r.get("name") == "Sector" and r.get("value") not in (None, "", "None")), None)
                if not sector or not fresh(meta.get("captured_at"), rule.get("max_classification_age_seconds")) or meta.get("status") != "available":
                    complete = False
                else:
                    sectors[sector] = sectors.get(sector, Decimal(0)) + value
                    source_refs["sector:" + name] = meta["artifact"]
            passed = complete and all(v / equity * 100 <= limit for v in sectors.values())
            reason, details = "Provider sector taxonomy; unknown sectors are unavailable, never zero exposure", {"complete": complete, "sector_equity_pct": {s: str(v / equity * 100) for s, v in sectors.items()}}
        elif key in {"max_spread_bps", "min_quote_size", "session_freshness"}:
            event = quote.get("ts_event")
            try:
                observed = datetime.fromtimestamp(int(event) / 1e9, UTC).isoformat()
            except (ValueError, TypeError, OverflowError):
                observed = None
            if key == "max_spread_bps" and bid is not None and ask is not None and 0 < bid <= ask:
                spread = (ask - bid) / ((ask + bid) / 2) * 10000
                passed = fresh(observed, rule.get("max_quote_age_seconds")) and spread <= limit
                reason, details = "Actual same-event IEX bid/ask spread; not a consolidated-liquidity claim", {"spread_bps": str(spread), "quote_event_ns": event}
            elif key == "min_quote_size":
                size = decimal(quote.get("ask_size" if terms["side"] == "BUY" else "bid_size"))
                passed = size is not None and fresh(observed, rule.get("max_quote_age_seconds")) and size >= limit
                reason, details = "Displayed IEX side quantity only; no hidden depth or future execution guarantee", {"quoted_shares": str(size) if size is not None else None, "quote_event_ns": event}
            elif key == "session_freshness":
                event = price_evidence({**terms, "order_type": "MARKET"}, runtime)["ts_event"]
                observed = datetime.fromtimestamp(int(event) / 1e9, UTC).isoformat() if event is not None else None
                opened, choice = runtime.get("market_open"), rule.get("session")
                maximum = limit if opened is True else decimal(rule.get("closed_max_age_seconds"))
                passed = type(opened) is bool and choice in {"regular_session_required", "allow_closed_session_review"} and (opened or choice == "allow_closed_session_review") and fresh(observed, maximum)
                reason, details = "Broker regular-session state and investor-selected open/closed age tolerances", {"regular_session_open": opened, "session_choice": choice, "maximum_age_seconds": str(maximum) if maximum is not None else None}
        elif key == "max_correlation_pct":
            try:
                window, minimum = int(rule["window_sessions"]), int(rule["minimum_pairs"])
                if not 3 <= minimum <= window <= 1000 or rule.get("method") != "pearson_daily_close_returns":
                    raise ValueError("Correlation method/window is unset")
                series = {}
                if not exposure_known:
                    raise ValueError("Resulting exposure inputs are unavailable")
                names = {s for s, value in conservative.items() if value > 0}
                for name in names:
                    candidates = [v for v in history.get("entries", {}).values() if v["symbol"] == name and v.get("adjustment") == rule.get("adjustment") and v.get("required_coverage", {}).get("sufficient") is True]
                    meta = max(candidates, key=lambda v: v["captured_at"]) if candidates else {}
                    data = artifact(meta.get("artifact", {}))
                    from .history_coverage import current, latest_calendar
                    if not data or not current(meta, data, artifact, calendar_meta=latest_calendar(history)).get("sufficient") or not fresh(meta.get("captured_at"), rule.get("max_history_age_seconds")):
                        raise ValueError("Required history/calendar coverage missing for " + name)
                    closes = [(b["t"], decimal(b.get("raw", {}).get("c", b.get("c")))) for b in data["bars"]][-window - 1:]
                    if len(closes) < window + 1 or any(v is None or v <= 0 for _, v in closes):
                        raise ValueError("Declared return window missing for " + name)
                    series[name] = {closes[i][0]: closes[i][1] / closes[i - 1][1] - 1 for i in range(1, len(closes))}
                    source_refs["correlation:" + name] = meta["artifact"]
                pairs, passed = [], True
                for left in sorted(names):
                    for right in sorted(s for s in names if s > left):
                        dates = sorted(set(series[left]) & set(series[right]))[-window:]
                        if len(dates) < minimum:
                            raise ValueError("Insufficient paired return dates")
                        xs, ys = [series[left][d] for d in dates], [series[right][d] for d in dates]
                        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
                        vx, vy = sum((v - mx) ** 2 for v in xs), sum((v - my) ** 2 for v in ys)
                        if vx <= 0 or vy <= 0:
                            raise ValueError("Correlation variance is nonpositive")
                        value = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (vx * vy).sqrt()
                        pairs.append({"left": left, "right": right, "paired_dates": dates, "correlation": str(value)})
                        passed = passed and abs(value) * 100 <= limit
                reason, details = "Declared Pearson correlation of paired daily close returns; estimates do not establish diversification guarantees", {"method": rule["method"], "window_sessions": window, "minimum_pairs": minimum, "adjustment": rule["adjustment"], "pairs": pairs}
            except (ValueError, KeyError, TypeError) as exc:
                reason = str(exc)
        check(key, passed, reason, details)
    return {"checks": checks, "source_references": source_refs, "states": scenarios,
            "cash_after_reserved_buys_before_actual_fees": str(cash_after) if cash_after is not None else None,
            "method": "observed-current-pending-proposed-policy-v1", "hypothetical": True,
            "proposed_price_basis": preview_price_basis, "proposed_fees": str(fee) if fees_known else None,
            "fee_basis": "Includes known/configured fee amounts only; missing actual fees remain unknown and are excluded", "conservative_exposure_by_symbol": {s: str(v) for s, v in conservative.items()}}
