"""Hypothetical whole-share allocation previews; never a portfolio ledger."""

import copy
import re
from datetime import UTC, datetime
from decimal import Decimal, ROUND_FLOOR
from uuid import uuid4

from .investor import decimal, digest, impact, instruments, price_evidence, working_commitments
from .workspace import text


def preview(saved, request, runtime, universe, *, commands=None):
    targets = request.get("targets")
    if not isinstance(targets, list) or not 1 <= len(targets) <= 1000:
        raise ValueError("Enter at least one allocation target (maximum 1000)")
    reason = text(request.get("reason", ""), 10000, "basket rationale")
    if not reason:
        raise ValueError("Explain the basket targets")
    supported = instruments(runtime, universe)
    account = runtime.get("account") or {}
    reconciliation = runtime.get("reconciliation", {})
    positions_known = runtime.get("status") == "connected" and reconciliation.get("positions_reconciled") is True
    equity = decimal(account.get("equity")) if runtime.get("status") == "connected" else None
    cash = decimal(account.get("cash")) if runtime.get("status") == "connected" else None
    fee = decimal(request.get("fee_per_leg")) if request.get("fee_per_leg") not in (None, "") else None
    slippage = decimal(request.get("slippage_bps")) if request.get("slippage_bps") not in (None, "") else None
    if fee is not None and fee < 0 or slippage is not None and not 0 <= slippage <= 10000:
        raise ValueError("Fee estimate must be nonnegative; slippage estimate must be between 0 and 10000 bps")
    if request.get("fee_per_leg") not in (None, "") and fee is None or request.get("slippage_bps") not in (None, "") and slippage is None:
        raise ValueError("Enter decimal cost estimates or leave them unset")
    commitments, commitments_known = working_commitments(runtime, commands)
    rows, legs, conditions, symbols = [], [], [], set()
    weight_sum = Decimal(0)
    for target in targets:
        symbol = target.get("symbol")
        instrument = supported.get(symbol)
        if symbol in symbols or not instrument or not instrument["supported"]:
            raise ValueError((instrument or {}).get("limitation") or "Targets must contain distinct observed supported equities")
        symbols.add(symbol)
        mode, value = target.get("mode"), decimal(target.get("value"))
        if mode not in {"weight", "quantity"} or value is None or value < 0:
            raise ValueError("Choose a weight or quantity and enter a nonnegative target")
        if mode == "quantity" and not re.fullmatch(r"0|[1-9]\d{0,17}", str(target["value"])):
            raise ValueError("Quantity targets must be exact whole shares, including zero for closure")
        if mode == "weight":
            if value > 100:
                raise ValueError("Target weight must be between 0 and 100%")
            weight_sum += value
        if target.get("order_type") not in {"MARKET", "LIMIT"}:
            raise ValueError("Choose MARKET or LIMIT for each target")
        limit = target.get("limit_price") if target["order_type"] == "LIMIT" else None
        if target["order_type"] == "LIMIT" and (not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", str(limit)) or decimal(limit) <= 0):
            raise ValueError("Each LIMIT target needs a positive price with at most two decimal places")
        position = next((p for p in runtime.get("positions", []) if p["symbol"] == symbol), None)
        current = decimal(position.get("qty")) if position and positions_known else Decimal(0) if positions_known else None
        if current is not None and current % 1:
            raise ValueError("Unsupported fractional holdings cannot be rounded into a basket")
        lower_target = current is not None and (value < current if mode == "quantity" else
            equity is not None and decimal((position or {}).get("market_value")) is not None and equity * value / 100 < decimal(position["market_value"]))
        selected_price = price_evidence({"symbol": symbol, "side": "SELL" if lower_target else "BUY",
            "order_type": target["order_type"], "limit_price": limit}, runtime)
        price, basis = selected_price["price"], selected_price["basis"]
        desired = value if mode == "quantity" else ((equity * value / 100 / price).to_integral_value(rounding=ROUND_FLOOR)
                   if equity is not None and equity > 0 and price is not None and price > 0 else None)
        difference = desired - current if desired is not None and current is not None else None
        residual = equity * value / 100 - desired * price if mode == "weight" and desired is not None else None
        row = {"symbol": symbol, "mode": mode, "value": str(value), "order_type": target["order_type"],
               "limit_price": str(limit) if limit is not None else None, "current_quantity": str(current) if current is not None else None,
               "desired_quantity": str(desired) if desired is not None else None,
               "valuation_price": str(price) if price is not None else None, "valuation_basis": basis,
               "market_event_ns": selected_price["ts_event"], "residual_cash": str(residual) if residual is not None else None,
               "residual_weight_pct": str(residual / equity * 100) if residual is not None and equity else None,
               "current_source_market_value": position.get("market_value") if position else "0" if positions_known else None}
        pending = [item for item in commitments if item["symbol"] == symbol]
        pending_qty = sum((item["remaining"] * (1 if item["side"] == "BUY" else -1) for item in pending), Decimal(0))
        pending_known = commitments_known
        row["pending_net_quantity"] = str(pending_qty) if pending_known else None
        row["quantity_if_working_orders_fill"] = str(current + pending_qty) if pending_known and current is not None else None
        rows.append(row)
        if difference is None:
            conditions.append(symbol + ": target quantity cannot be calculated from available observations")
        elif difference:
            terms = {"symbol": symbol, "instrument_id": instrument["instrument_id"],
                     "side": "BUY" if difference > 0 else "SELL", "quantity": format(abs(difference), "f"),
                     "order_type": target["order_type"], "limit_price": row["limit_price"], "rationale": reason,
                     "research": target.get("research"), "time_in_force": "DAY", "session": "regular",
                     "account_id": account.get("id")}
            estimate = impact(terms, runtime, saved["policy"]["rules"], commands=commands)
            legs.append({"symbol": symbol, "terms": terms, "impact": estimate})
    if weight_sum > 100:
        raise ValueError("Combined entered weight targets exceed 100%")
    working = [o for o in runtime.get("orders", []) if o.get("symbol") in symbols]
    other = [p["id"] for p in saved["proposals"] if p["terms"]["symbol"] in symbols
             and p["status"] == "draft" and p["id"] not in request.get("linked_proposal_ids", [])]
    if working:
        conditions.append("Working orders overlap target symbols; pending exposure is separate from the proposed allocation")
    if other:
        conditions.append("Other draft proposals overlap target symbols")
    if not reconciliation.get("orders_reconciled"):
        conditions.append("Pending orders are not fully reconciled")
    if fee is None or slippage is None:
        conditions.append("Unknown fee/slippage amounts are excluded from estimates, not reported as zero actual costs")
    conditions.extend(["Basket orders may fill separately; each needs exact approval and explicit submission",
                       "Sale proceeds are not assumed spendable for buys; configured checks still apply"])
    reserved_cash = sum((item["cash"] for item in commitments), Decimal(0))
    assumed = request.get("assumed_filled", [])
    if not isinstance(assumed, list) or any(s not in {leg["symbol"] for leg in legs} for s in assumed):
        raise ValueError("Select assumed-filled symbols from the current proposed legs")
    def scenario(selected):
        selected_legs = [leg for leg in legs if leg["symbol"] in selected]
        amounts = [decimal(leg["impact"]["estimated_principal"]) for leg in selected_legs]
        known = all(v is not None for v in amounts) and all(row["desired_quantity"] is not None and row["current_quantity"] is not None for row in rows)
        buys = sum((v for leg, v in zip(selected_legs, amounts) if leg["terms"]["side"] == "BUY"), Decimal(0)) if known else None
        sells = sum((v for leg, v in zip(selected_legs, amounts) if leg["terms"]["side"] == "SELL"), Decimal(0)) if known else None
        fees = fee * len(selected_legs) if fee is not None else None
        slip = (buys + sells) * slippage / 10000 if known and slippage is not None else None
        known_costs = sum((amount for amount in (fees, slip) if amount is not None), Decimal(0))
        expected_cash = cash - buys + sells - known_costs if cash is not None and known else None
        spendable = cash - reserved_cash if cash is not None and commitments_known else None
        no_sale_funding = buys + known_costs <= spendable if known and spendable is not None else None
        holdings = []
        for row in rows:
            quantity = row["desired_quantity"] if row["symbol"] in selected else row["current_quantity"]
            value = Decimal(quantity) * Decimal(row["valuation_price"]) if quantity is not None and row["valuation_price"] is not None else None
            holdings.append({"symbol": row["symbol"], "quantity": quantity, "valuation_price": row["valuation_price"],
                             "market_value_estimate": str(value) if value is not None else None,
                             "equity_weight_pct_estimate": str(value / equity * 100) if value is not None and equity and equity > 0 else None})
        for position in runtime.get("positions", []):
            if position["symbol"] not in symbols:
                value = decimal(position.get("market_value")) if positions_known else None
                holdings.append({"symbol": position["symbol"], "quantity": position.get("qty") if positions_known else None,
                                 "unchanged_observation": True, "market_value_estimate": str(value) if value is not None else None,
                                 "equity_weight_pct_estimate": str(value / equity * 100) if value is not None and equity and equity > 0 else None})
        return {"assumed_filled": sorted(selected), "holdings": holdings,
                "gross_buys": str(buys) if buys is not None else None, "gross_sells": str(sells) if sells is not None else None,
                "estimated_fees": str(fees) if fees is not None else None, "estimated_slippage": str(slip) if slip is not None else None,
                "turnover_pct": str((buys + sells) / equity * 100) if known and equity and equity > 0 else None,
                "hypothetical_cash": str(expected_cash) if expected_cash is not None else None,
                "buys_fit_observed_spendable_without_sales": no_sale_funding,
                "remaining_legs": [leg["symbol"] for leg in legs if leg["symbol"] not in selected]}
    snapshot = {"account": runtime.get("account"), "account_at": runtime.get("account_at"),
                "positions": runtime.get("positions"), "orders": runtime.get("orders"),
                "market": {s: runtime.get("market_data", {}).get(s) for s in symbols}, "reconciliation": reconciliation}
    return {"targets": rows, "legs": legs, "reason": reason, "account_id": account.get("id"),
            "account_at": runtime.get("account_at"), "policy_revision": saved["policy"]["revision"],
            "observed_buying_power": account.get("buying_power"), "cash_commitments_known": commitments_known,
            "fee_per_leg": str(fee) if fee is not None else None, "slippage_bps": str(slippage) if slippage is not None else None,
            "working_orders": copy.deepcopy(working), "conflicting_proposal_ids": other, "conditions": conditions,
            "complete_scenario": scenario({leg["symbol"] for leg in legs}), "partial_scenario": scenario(set(assumed)),
            "observation_sha256": digest(snapshot), "observation": snapshot, "executable": False}


def save(saved, request, runtime, universe, resolve_research, *, commands=None):
    from .investor import save as save_proposal
    saved.setdefault("baskets", [])
    prior = next((b for b in saved["baskets"] if b["id"] == request.get("id")), None)
    action, stamp = request.get("action"), datetime.now(UTC).isoformat()
    reason = text(request.get("reason", ""), 10000, "basket rationale")
    if action in {"basket_reject", "basket_defer"}:
        if not prior:
            raise ValueError("Select a saved basket")
        decision = "reject" if action == "basket_reject" else "defer"
        for identity in prior["linked_proposal_ids"]:
            save_proposal(saved, {"action": decision, "id": identity, "reason": reason}, runtime, universe, resolve_research)
        prior.update(status="rejected" if decision == "reject" else "deferred", revision=prior["revision"] + 1,
                     approval=None, updated_at=stamp, impact_review_valid=False)
        prior["history"].append({"action": decision, "reason": reason, "at": stamp, "revision": prior["revision"]})
        return saved
    if action != "basket_draft" or request.get("id") and not prior:
        raise ValueError("Select an existing basket or create a new basket draft")
    old_ids = prior["linked_proposal_ids"] if prior else []
    evidence = preview(saved, {**request, "linked_proposal_ids": old_ids}, runtime, universe, commands=commands)
    old_by_symbol = {p["terms"]["symbol"]: p for p in saved["proposals"] if p["id"] in old_ids}
    linked = []
    for leg in evidence["legs"]:
        previous = old_by_symbol.get(leg["symbol"])
        save_proposal(saved, {"action": "draft", "id": previous["id"] if previous else None,
                             "terms": leg["terms"], "reason": reason}, runtime, universe, resolve_research)
        current = next(p for p in saved["proposals"] if p["id"] == previous["id"]) if previous else saved["proposals"][0]
        linked.append(current["id"])
        leg["proposal_id"], leg["proposal_revision"] = current["id"], current["revision"]
        leg["terms"] = copy.deepcopy(current["terms"])
    for identity in set(old_ids) - set(linked):
        save_proposal(saved, {"action": "defer", "id": identity, "reason": "Removed from revised basket: " + reason},
                      runtime, universe, resolve_research)
    revision = prior["revision"] + 1 if prior else 1
    event = {"action": "revise" if prior else "draft", "revision": revision, "at": stamp,
             "reason": reason, "evidence": copy.deepcopy(evidence), "linked_proposal_ids": linked}
    basket = {"id": prior["id"] if prior else str(uuid4()), "revision": revision, "status": "draft",
              "created_at": prior["created_at"] if prior else stamp, "updated_at": stamp, "approval": None,
              "impact_review_valid": True, "linked_proposal_ids": linked, "preview": evidence,
              "history": (prior["history"] if prior else []) + [event]}
    if prior:
        saved["baskets"][saved["baskets"].index(prior)] = basket
    else:
        saved["baskets"].insert(0, basket)
    return saved
