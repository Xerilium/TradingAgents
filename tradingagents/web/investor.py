"""Human policy and proposal records. No order submission or approval capability."""

import copy
import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4

from .workspace import text
from .linked_orders import exit_plan, amendment_supported, native_type, broker_payload, equity_quantity, fractional_terms, trailing_terms, native_trail, option_contract, option_terms, contract_multiplier, OPTION_ORDER_PROFILES

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


def native_balance_binding(runtime):
    projection = (runtime.get("profile_transition") or {}).get("balance_projection")
    return {key: copy.deepcopy(projection.get(key)) for key in
        ("version", "currency", "source_fields", "derived", "reported_margin", "calculate_account_state", "authority")} if projection else None


def replacement_funding_route(terms):
    version = terms.get("replacement_funding_basis")
    if version is None:
        return None
    replacement = terms.get("replacement") or {}
    if (version != "alpaca-bounded-incremental-v1" or terms.get("execution_profile") != "bounded_risk_spread_v1"
            or terms.get("asset_class") != "us_option" or terms.get("order_class") != "mleg"
            or not terms.get("account_id") or not replacement.get("order_id") or not replacement.get("client_order_id")
            or not replacement.get("order_version") or replacement.get("account_id") != terms.get("account_id")):
        raise ValueError("Broker incremental reservation routing requires exact versioned bounded package replacement terms")
    return {"version": version, "state": "not_observed", "authority": "broker", "reservation_credit": None,
        "order_id": replacement["order_id"], "account_id": terms["account_id"]}


def decimal(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


PRICE_DESTINATIONS = {"limit_price", "stop_price", "exit_plan.take_profit", "exit_plan.stop_price", "exit_plan.stop_limit_price"}


def copied_price_fields(reference, terms):
    field = reference["destination"]
    if (terms.get("side") == "SELL" and terms.get("order_type") == "LIMIT" and terms.get("exit_plan")
            and field in {"limit_price", "exit_plan.take_profit"}):
        return {"limit_price", "exit_plan.take_profit"}
    return {field}


def price_reference(value, terms):
    """Validate a retained manual-price receipt without treating it as a live quote."""
    from .workspace import chart_time, source_pin
    if not isinstance(value, dict) or value.get("destination") not in PRICE_DESTINATIONS:
        raise ValueError("Choose a supported ticket price destination")
    pin = source_pin(value.get("pin"))
    if value.get("derived_origin") is not None:
        from uuid import UUID
        origin = value["derived_origin"]
        if (not isinstance(origin, dict) or set(origin) != {"calculation_id", "result_sha256", "event_ordinal", "source_ordinal"}
                or str(UUID(origin.get("calculation_id", ""))) != origin["calculation_id"]
                or not re.fullmatch(r"[0-9a-f]{64}", str(origin.get("result_sha256", "")))
                or any(type(origin.get(key)) is not int or origin[key] < 0 for key in ("event_ordinal", "source_ordinal"))
                or value.get("value_kind") not in {"close", "open", "high", "low"} or value.get("approximate") is not False):
            raise ValueError("Synthetic selections require an explicit actual raw OHLC source")
    chart_time(value.get("bar_time"), pin["timeframe"])
    kind = value.get("value_kind")
    if (kind not in {"close", "open", "high", "low", "approximate_coordinate"}
            or type(value.get("approximate")) is not bool or value["approximate"] != (kind == "approximate_coordinate")
            or not isinstance(value.get("raw_value"), str) or decimal(value["raw_value"]) is None or decimal(value["raw_value"]) <= 0
            or value.get("currency") != "USD" or pin["symbol"] != terms.get("symbol")
            or not value.get("instrument") or value.get("instrument") != terms.get("instrument_id", value["instrument"])):
        raise ValueError("Price reference instrument, currency or actual value is incompatible")
    destination = value["destination"]
    if (destination == "limit_price" and terms.get("order_type") not in {"LIMIT", "STOP_LIMIT"}
            or destination == "stop_price" and terms.get("order_type") not in {"STOP_MARKET", "STOP_LIMIT"}
            or destination.startswith("exit_plan.") and not isinstance(terms.get("exit_plan"), dict)):
        raise ValueError("Price destination does not match the existing ticket")
    return copy.deepcopy(value)


def normalize_chart_price(reference, terms, runtime, detail):
    reference = price_reference(reference, terms)
    symbol = terms["symbol"]
    source = detail.get("source") or {}
    native = runtime.get("market_data", {}).get(symbol, {}).get("instrument") or {}
    asset = (native.get("info") or {}).get("alpaca_asset") or {}
    currency = detail.get("currency", source.get("currency"))
    source_asset = detail.get("required_coverage", {}).get("provenance", {}).get("asset_id", source.get("instrument"))
    increment = decimal(native.get("price_increment"))
    precision = native.get("price_precision")
    if (currency != reference["currency"] or native.get("id") != reference["instrument"]
            or native.get("quote_currency", native.get("currency")) != currency
            or not source_asset or source_asset != asset.get("id") or asset.get("symbol") != symbol
            or increment is None or increment <= 0 or type(precision) is not int or not 0 <= precision <= 2):
        raise ValueError("Matching sourced instrument, USD currency and supported native price increment are required")
    if increment.quantize(Decimal(1).scaleb(-precision)) != increment:
        raise ValueError("Observed price increment cannot be represented at the supported native ticket precision")
    bars = [bar for bar in detail.get("bars", []) if bar.get("t") == reference["bar_time"]]
    if len(bars) != 1:
        raise ValueError("Pinned source does not contain one distinct selected bar")
    if not reference["approximate"]:
        field = {"close": "c", "open": "o", "high": "h", "low": "l"}[reference["value_kind"]]
        raw = bars[0].get("raw", {}).get(field)
        if not isinstance(raw, str) or raw != reference["raw_value"]:
            raise ValueError("Selected exact OHLC value differs from its retained source")
    raw = decimal(reference["raw_value"])
    normalized = ((raw / increment).quantize(Decimal(1), rounding=ROUND_HALF_UP) * increment).quantize(Decimal(1).scaleb(-precision))
    value = format(normalized, "f")
    if not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", value) or normalized <= 0 or normalized % increment:
        raise ValueError("Normalized source price cannot fit this existing ticket")
    normalization = {"value": value, "increment": str(increment), "precision": precision,
        "rounded": normalized != raw, "method": "nearest native increment; ROUND_HALF_UP",
        "instrument_metadata_sha256": digest({"id": native["id"], "asset_id": asset["id"], "currency": currency,
            "increment": str(increment), "precision": precision}),
        "source_captured_at": detail.get("captured_at", source.get("captured_at"))}
    reference.setdefault("instrument_observed_at", (native.get("info") or {}).get("asset_observed_at"))
    reference["normalization"] = normalization
    reference["fields"] = dict.fromkeys(sorted(copied_price_fields(reference, terms)), value)
    return {"field": reference["destination"], "value": value, "raw_value": reference["raw_value"],
            "rounded": normalization["rounded"], "increment": str(increment), "fields": reference["fields"], "price_ref": reference}


def price_evidence(terms, runtime):
    if terms.get("order_class") == "mleg":
        from .linked_orders import package_legs, package_terms
        package_terms({**terms, "limit_price": None} if terms.get("order_type") == "MARKET" else terms)
        if terms.get("order_type") == "LIMIT":
            return {"price": decimal(terms.get("limit_price")), "basis": "Exact signed package net premium; not allocated leg economics", "ts_event": None}
        quotes = [(leg, price_evidence({**leg, "order_type": "MARKET"}, runtime)) for leg in package_legs(terms)]
        valid = all(item["price"] is not None and item["ts_event"] is not None for _, item in quotes)
        net = sum((item["price"] * Decimal(leg["ratio_qty"]) * (1 if leg["side"] == "BUY" else -1) for leg, item in quotes), Decimal(0)) if valid else None
        return {"price": net, "basis": "Dated leg side premiums / strategy unit; no fill cap or debit/credit sign guarantee", "ts_event": min(item["ts_event"] for _, item in quotes) if valid else None}
    """Exact limit or dated IEX estimate; neither a consolidated quote nor guaranteed fill."""
    if terms.get("order_type") in {"LIMIT", "STOP_LIMIT"}:
        price = decimal(terms.get("limit_price"))
        return {"price": price if price is not None and price > 0 else None,
                "basis": "Exact human limit / USD", "ts_event": None}
    if terms.get("order_type") not in {"MARKET", "STOP_MARKET", "TRAILING_STOP_MARKET"}:
        return {"price": None, "basis": "Unsupported order price basis", "ts_event": None}
    market = runtime.get("market_data", {}).get(terms["symbol"], {})
    quote, trade = market.get("quote") or {}, market.get("trade") or {}
    side = "ask_price" if str(terms.get("side")).upper() == "BUY" else "bid_price"
    for value, event, basis in ((quote.get(side), quote.get("ts_event"), "Dated IEX " + side + " estimate"),
                                (trade.get("price"), trade.get("ts_event"), "Dated IEX last-trade estimate")):
        if market.get("option_contract"):
            basis = "Dated Alpaca option " + str(market.get("market_feed")) + " " + side + " premium estimate"
        price, stamp = decimal(value), decimal(event)
        if price is not None and price > 0 and stamp is not None and 0 < stamp <= Decimal(str(datetime.now(UTC).timestamp())) * 1000000000:
            if terms.get("order_type") == "STOP_MARKET" and terms.get("side") == "BUY":
                trigger = decimal(terms.get("stop_price"))
                if trigger is None or trigger <= 0:
                    return {"price": None, "basis": "BUY stop trigger is unavailable", "ts_event": event}
                price = max(price, trigger)
                basis = "BUY stop estimate: higher of dated price and trigger; not a guaranteed fill cap"
            return {"price": price, "basis": basis + "; execution price is unknown", "ts_event": event}
    return {"price": None, "basis": "Dated option side premium unavailable or zero; no underlying substitution" if market.get("option_contract") else "Dated side quote or last trade unavailable",
            "ts_event": quote.get("ts_event") if market.get("option_contract") else None}


def spread_risk(terms, runtime, commands=None):
    """Expiry intrinsic bounds and close claims; not broker margin or assignment protection."""
    from .linked_orders import package_legs, package_terms
    bounded = terms.get("execution_profile") == "bounded_risk_spread_v1"
    legs = package_legs({**terms, "quantity": str(remaining_quantity(terms))}) if terms.get("order_class") == "mleg" else [terms]
    if bounded:
        package_terms(terms)
    contracts = {leg["symbol"]: option_contract(leg["option_contract"]) for leg in legs}
    if len({raw["expiration_date"] for raw in contracts.values()}) > 1:
        scopes = [spread_risk(leg, runtime, commands) for leg in legs]
        return {"method": "separate-expiry-protection-review-v1", "opening_protection": True,
            "residual_protection": all(item["residual_protection"] for item in scopes), "cohorts": scopes,
            "leg_impacts": [claim for item in scopes for claim in item["leg_impacts"]],
            "blockers": [reason for item in scopes for reason in item["blockers"]],
            "basis": "No cross-expiry protection or calendar collateral model; each touched expiry reviewed separately"}
    first = next(iter(contracts.values()))
    cohort = (first["underlying_asset_id"], first["expiration_date"], first["size"], first.get("deliverables"))
    positions, current, blockers, claims = {}, {}, [], []
    complete = runtime.get("reconciliation", {}).get("positions_reconciled") is True
    for row in runtime.get("positions", []):
        if row.get("asset_class") != "us_option":
            continue
        envelope = row.get("option_contract") or runtime.get("market_data", {}).get(row["symbol"], {}).get("option_contract")
        try:
            raw = option_contract(envelope)
        except (ValueError, KeyError, TypeError):
            complete = False
            continue
        if (raw["underlying_asset_id"], raw["expiration_date"], raw["size"], raw.get("deliverables")) != cohort:
            continue
        quantity = decimal(row.get("qty"))
        if quantity is None or quantity % 1 or row.get("import_error"):
            complete = False
            continue
        quantity = -abs(quantity) if row.get("side") == "short" else quantity
        contracts[row["symbol"]], current[row["symbol"]], positions[row["symbol"]] = raw, quantity, row
    commitments, commitments_complete = working_commitments(runtime, commands)
    replacement = (terms.get("replacement") or {}).get("order_id")
    replaced = [item for item in commitments if replacement and replacement in item["order_ids"]]
    commitments = [item for item in commitments if not replacement or replacement not in item["order_ids"]]
    proposed, opening = dict(current), {}
    # Pending new protection/closing relief is not assumed to fill. Protection removals remain adverse claims.
    for item in commitments:
        if item["symbol"] in contracts and item["side"] == "SELL" and item.get("position_intent") != "sell_to_open":
            proposed[item["symbol"]] = proposed.get(item["symbol"], Decimal(0)) - item["remaining"]
    pending = dict(proposed)
    for leg in legs:
        name, intent, quantity = leg["symbol"], leg["position_intent"], remaining_quantity(leg)
        held = current.get(name, Decimal(0)) if complete else None
        row = positions.get(name)
        available = decimal(row.get("qty_available")) if row else Decimal(0) if complete else None
        if available is not None:
            available = abs(available)
            available += sum((item["remaining"] for item in replaced if item["symbol"] == name and item["side"] == leg["side"]
                and item.get("position_intent") in {None, intent} and intent in {"sell_to_close", "buy_to_close"}), Decimal(0))
            available -= sum((item["remaining"] for item in commitments if item["symbol"] == name
                and item["side"] == leg["side"] and item["command_ids"] and not item["order_ids"]), Decimal(0))
        claims.append({"symbol": name, "position_intent": intent, "quantity": str(quantity),
            "held_quantity": str(held) if held is not None else None,
            "available_long": str(max(available, Decimal(0))) if held is not None and held > 0 and available is not None else "0" if held is not None and held <= 0 else None,
            "available_short": str(max(available, Decimal(0))) if held is not None and held < 0 and available is not None else "0" if held is not None and held >= 0 else None})
        if quantity is None or quantity <= 0:
            complete = False
            continue
        if held is None or intent == "buy_to_open" and held < 0 or intent == "sell_to_open" and held > 0:
            blockers.append("Opening intent conflicts with unknown or opposite current contract inventory: " + name)
        if intent in {"sell_to_close", "buy_to_close"} and (held is None or available is None or available < quantity
                or intent == "sell_to_close" and held < quantity or intent == "buy_to_close" and held > -quantity):
            blockers.append("Exact available matching long/short close quantity is insufficient or unknown: " + name)
        proposed[name] = proposed.get(name, Decimal(0)) + quantity * (1 if leg["side"] == "BUY" else -1)
        if intent in {"buy_to_open", "sell_to_open"}:
            opening[name] = quantity * (1 if leg["side"] == "BUY" else -1)
    def covered(holdings):
        return all(sum((max(q, Decimal(0)) for name, q in holdings.items() if contracts[name]["type"] == kind), Decimal(0))
            >= sum((-min(q, Decimal(0)) for name, q in holdings.items() if contracts[name]["type"] == kind), Decimal(0)) for kind in ("call", "put"))
    def collateral(holdings):
        if sum((q for name, q in holdings.items() if contracts[name]["type"] == "call"), Decimal(0)) < 0:
            return None
        points = {Decimal(0)} | {Decimal(contracts[name]["strike_price"]) for name in holdings}
        return max(Decimal(0), -min(sum((q * max(Decimal(0), (spot - Decimal(contracts[name]["strike_price"]))
            * (1 if contracts[name]["type"] == "call" else -1)) for name, q in holdings.items()), Decimal(0)) for spot in points)) * Decimal(first["size"])
    opening_ok, residual_ok = covered(opening), covered(proposed)
    before, after = collateral(pending), collateral(proposed)
    increment = max(Decimal(0), after - before) if complete and commitments_complete and before is not None and after is not None else None
    if bounded and not opening_ok:
        blockers.append("New short openings require equal compatible same-kind BTO protection within this package")
    if not residual_ok or after is None:
        blockers.append("Resulting same-expiry cohort has unsupported naked or unbounded exposure")
    if not complete or not commitments_complete:
        blockers.append("Current cohort metadata/quantities or working commitments are incomplete")
    premium = decimal(terms.get("limit_price"))
    opening_only = all(leg["position_intent"] in {"buy_to_open", "sell_to_open"} for leg in legs)
    opened = collateral(opening)
    maximum_loss = max(Decimal(0), opened + premium * remaining_quantity(terms) * Decimal(first["size"])) if opening_only and opened is not None and premium is not None else None
    obligation = max(Decimal(0), increment + premium * remaining_quantity(terms) * Decimal(first["size"])) if increment is not None and premium is not None else None
    return {"method": "same-expiry-intrinsic-knots-v1", "opening_protection": opening_ok, "residual_protection": residual_ok,
        "current_intrinsic_collateral": str(collateral(current)) if complete and collateral(current) is not None else None,
        "pending_intrinsic_collateral": str(before) if before is not None and complete else None,
        "intrinsic_collateral": str(after) if after is not None and complete else None,
        "collateral_increase": str(increment) if increment is not None else None,
        "net_package_obligation_before_costs": str(obligation) if obligation is not None else None,
        "modeled_expiry_max_loss_before_costs": str(maximum_loss) if maximum_loss is not None else None,
        "account_at": runtime.get("account_at"), "leg_impacts": claims, "blockers": blockers,
        "basis": "Intrinsic exercise payoff at zero/all strikes and nonnegative-price tail; premiums ignored for collateral. Net obligation=max(0, positive collateral increase + signed same-package premium). No unrelated credit or collateral-release spending. Retained entry economics may be unknown. Early assignment/exercise can break protection; not broker margin or guaranteed loss."}


def execution_costs(terms, runtime, constraints):
    if terms.get("order_class") == "mleg":
        selected = price_evidence(terms, runtime)["price"]
        ceiling = decimal(constraints.get("max_execution_price"))
        price = max(selected, Decimal(0)) if selected is not None else None
        if terms["order_type"] == "MARKET":
            price = ceiling if ceiling is not None and ceiling >= 0 and price is not None and price <= ceiling else None
        return price, decimal(constraints.get("max_fees"))
    price = price_evidence(terms, runtime)["price"]
    ceiling = decimal(constraints.get("max_execution_price"))
    if terms["order_type"] in {"MARKET", "STOP_MARKET"} and terms["side"] == "BUY" and ceiling is not None:
        price = ceiling if price is not None and price <= ceiling else None
    return price, decimal(constraints.get("max_fees"))


def order_version(order):
    return digest({key: order.get(key) for key in ("id", "client_order_id", "symbol", "asset_id", "side", "qty",
        "filled_qty", "type", "order_type", "order_class", "limit_price", "stop_price", "time_in_force",
        "trail_price", "trail_percent", "extended_hours", "status", "replaces", "replaced_by", "group_parent_id", "group_class", "group_role", "group_entry_status", "exit_reserved", "asset_class", "position_intent", "option_contract", "package_terms", "package_mapping", "package_members")})



def native_quantity_offset(order):
    """Only an execution-proven separate successor translates raw cumulative quantities."""
    proof = order.get("native_replacement_quantity_binding")
    if not proof:
        if (str(order.get("type", order.get("order_type"))).upper() == "MARKET" or order.get("asset_class") == "us_option" or order.get("order_class") == "mleg") and order.get("replaces"):
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
    if (not (str(order.get("type", order.get("order_type"))).upper() == "MARKET" and proof.get("source") == "validated_broker_market_replacement"
            or order.get("asset_class") == "us_option" and native_type(order.get("type", order.get("order_type"))) in OPTION_ORDER_PROFILES and proof.get("source") == "validated_broker_option_replacement"
            or order.get("order_class") == "mleg" and order.get("package_mapping") and proof.get("source") == "validated_broker_package_replacement")
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
    equity_quantity(order["qty"])
    equity_quantity(order["filled_qty"], zero=True)
    native = order.get("binding_native") or order.get("nautilus") or {}
    if order.get("order_class") == "mleg":
        from .linked_orders import package_observation, package_terms
        terms = order.get("package_terms") or {}
        package_terms(terms)
        mapped = package_observation(order, terms)
        marker = native.get("package_control") or {}
        binding = native.get("account_binding") or {}
        offset = native_quantity_offset(order)
        statuses = {"new": "ACCEPTED", "accepted": "ACCEPTED", "held": "ACCEPTED", "pending_new": "SUBMITTED",
            "partially_filled": "PARTIALLY_FILLED" if decimal(order["filled_qty"]) > offset else "ACCEPTED",
            "done_for_day": "PARTIALLY_FILLED" if decimal(order["filled_qty"]) > offset else "ACCEPTED"}
        if (runtime.get("status") != "connected" or runtime.get("reconciliation", {}).get("status") != "reconciled"
                or order.get("import_error") or not order.get("client_order_id")
                or binding.get("account_id") != "ALPACA-" + str((runtime.get("account") or {}).get("id"))
                or native.get("client_order_id") != order["client_order_id"] or native.get("venue_order_id") != identity
                or native.get("instrument_id") != terms["instrument_id"] or marker.get("internal") is not True
                or native.get("status") != statuses.get(order.get("status"))
                or marker.get("economics") != "actual_leg_fills_only" or marker.get("source_mapping") != mapped["package_mapping"]
                or decimal(native.get("quantity")) is None or decimal(native.get("filled_qty")) is None
                or decimal(native["quantity"]) + offset != decimal(order["qty"])
                or decimal(native["filled_qty"]) + offset != decimal(order["filled_qty"])
                or not 0 <= decimal(order["filled_qty"]) < decimal(order["qty"])
                or native.get("type") != terms["order_type"] or native.get("time_in_force") != terms["time_in_force"]
                or version is not None and version != order_version(order)):
            raise ValueError("Package action requires exact actual parent/leg mapping and current native control reconciliation")
        return order
    if order.get("type") == "trailing_stop":
        offset, unit = native_trail({"order_type": "TRAILING_STOP_MARKET", "quantity": order["qty"],
            "side": order["side"].upper(), "time_in_force": order["time_in_force"].upper(),
            "trail_price": order.get("trail_price"), "trail_percent": order.get("trail_percent")})
        if (decimal(native.get("trailing_offset")) != offset or native.get("trailing_offset_type") != unit
                or decimal(native.get("trigger_price")) != decimal(order.get("stop_price"))):
            raise ValueError("Native trailing distance or current broker-observed trigger differs")
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
    child_binding = order.get("native_child_order_binding") or {}
    client_matches = client_matches or (child_binding.get("source") == "broker_nested_group"
        and child_binding.get("broker_order_id") == identity and child_binding.get("broker_client_order_id") == order.get("client_order_id")
        and child_binding.get("native_client_order_id") == client and child_binding.get("parent_order_id") == order.get("group_parent_id"))
    if order.get("native_replacement_quantity_binding"):
        client_matches = client == order.get("client_order_id")
    venue = native.get("venue_order_id")
    indexed = native.get("venue_order_id_binding") or {}
    if (venue is None and native.get("status") in {"SUBMITTED", "PENDING_CANCEL", "PENDING_UPDATE"}
            and indexed.get("source") == "native_cache_venue_order_index"
            and indexed.get("client_order_id") == native.get("client_order_id")):
        venue = indexed.get("venue_order_id")
    expected_status = {"new": "ACCEPTED", "accepted": "ACCEPTED", "held": "ACCEPTED", "done_for_day": "PARTIALLY_FILLED" if filled else "ACCEPTED", "partially_filled": "PARTIALLY_FILLED", "pending_new": "SUBMITTED"}
    if order.get("status") == "partially_filled" and filled is not None and filled - offset == 0:
        expected_status["partially_filled"] = "ACCEPTED"
    if (runtime.get("status") != "connected" or not account_id or order.get("account_id") not in (None, account_id)
            or order.get("asset_class") not in {"us_equity", "us_option"} or order.get("side") not in {"buy", "sell"}
            or native_type(order.get("type", order.get("order_type"))) not in {"MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT", "TRAILING_STOP_MARKET"}
            or order.get("time_in_force") not in {"day", "gtc"} or type(order.get("extended_hours")) is not bool
            or order.get("order_class") not in (None, "", "simple", "oto", "bracket", "oco") or order.get("import_error")
            or total is None or total <= 0 or filled is None or not 0 <= filled < total
            or not order.get("client_order_id") or native_account != "ALPACA-" + str(account_id)
            or native.get("instrument_id") != order.get("symbol", "") + ".ALPACA"
            or not client_matches or venue != identity
            or native.get("side") != order["side"].upper()
            or native.get("type") != native_type(order.get("type", order.get("order_type")))
            or native.get("time_in_force") != order["time_in_force"].upper()
            or order.get("type") in {"limit", "stop_limit"} and decimal(native.get("price")) != decimal(order.get("limit_price"))
            or order.get("type") in {"stop", "stop_limit"} and decimal(native.get("trigger_price")) != decimal(order.get("stop_price"))
            or total is None or filled is None or decimal(native.get("quantity")) != total - offset or decimal(native.get("filled_qty")) != filled - offset
            or native.get("status") != expected_status.get(order.get("status"))
            or version is not None and version != order_version(order)):
        raise ValueError("Broker/native identity, source terms or supported equity order state differs")
    if order.get("asset_class") == "us_option":
        option_terms({"asset_class": "us_option", "symbol": order["symbol"], "quantity": order["qty"],
            "side": order["side"].upper(), "position_intent": order.get("position_intent"), "option_contract": order.get("option_contract"),
            "currency": "USD", "order_type": native_type(order.get("type")), "time_in_force": order["time_in_force"].upper(),
            "session": "extended" if order.get("extended_hours") else "regular", "limit_price": order.get("limit_price"),
            "stop_price": order.get("stop_price"),
            "exit_plan": order if order.get("order_class") not in (None, "", "simple") else None})
        if "option_intent:" + order["position_intent"] not in (native.get("tags") or []):
            raise ValueError("Current native option intent differs from broker observation")
    from .linked_orders import broker_session
    if ("extended_hours" in (native.get("tags") or [])) != (broker_session(order) == "extended"):
        raise ValueError("Native and broker execution-session eligibility differs")
    return order


def contingent_group(order, runtime, commands=None):
    """Exact conditional authority for modifying an approved, still-held bracket exit."""
    if not (order.get("group_class") == "bracket" and order.get("group_role") in {"take_profit", "stop_loss"}
            and order.get("status") == "held"):
        return None
    parent_id = order.get("group_parent_id")
    rows = [row for row in runtime.get("orders", []) if row.get("id") == parent_id or row.get("group_parent_id") == parent_id]
    parents = [row for row in rows if row.get("id") == parent_id and row.get("group_role") == "entry"]
    if (len(rows) != 3 or len(parents) != 1 or {row.get("group_role") for row in rows} != {"entry", "take_profit", "stop_loss"}
            or parents[0].get("status") not in {"new", "accepted", "partially_filled", "done_for_day"}
            or any(row.get("status") != "held" for row in rows if row["id"] != parent_id)):
        raise ValueError("A complete current held bracket and working entry are required")
    parent = parents[0]
    native_by_role = {row["group_role"]: row.get("binding_native") or row.get("nautilus") or {} for row in rows}
    exit_ids = [native_by_role[role].get("client_order_id") for role in ("take_profit", "stop_loss")]
    members = []
    for row in sorted(rows, key=lambda row: row["id"]):
        broker_action_order(runtime, row["id"])
        native = row.get("binding_native") or row.get("nautilus") or {}
        is_entry = row["id"] == parent_id
        expected_links = exit_ids if is_entry else [identity for identity in exit_ids if identity != native.get("client_order_id")]
        if (row.get("symbol") != order["symbol"] or row.get("group_class") != "bracket"
                or decimal(row.get("qty")) != decimal(parent.get("qty"))
                or row["id"] != parent_id and (row.get("side") != "sell" or decimal(row.get("filled_qty")) != 0)
                or not native.get("order_list_id") or native.get("order_list_id") != (parent.get("binding_native") or parent.get("nautilus") or {}).get("order_list_id")
                or row["id"] != parent_id and native.get("parent_order_id") != native_by_role["entry"].get("client_order_id")
                or is_entry and native.get("parent_order_id") is not None
                or native.get("reduce_only") is not (not is_entry)
                or native.get("contingency_type") != ("OTO" if is_entry else "OCO")
                or native.get("emulation_trigger") != "NO_TRIGGER"
                or not isinstance(native.get("linked_order_ids"), list) or not all(isinstance(identity, str) for identity in exit_ids)
                or sorted(native["linked_order_ids"]) != sorted(expected_links)):
            raise ValueError("Held bracket quantity or native parent/list relationship differs")
        members.append({"order_id": row["id"], "version": order_version(row), "native_client_order_id": native["client_order_id"],
                        "native_order_list_id": native["order_list_id"], "role": row["group_role"],
                        **{key: native.get(key) for key in ("parent_order_id", "linked_order_ids", "contingency_type", "reduce_only", "emulation_trigger")},
                        **{key: row.get(key) for key in ("client_order_id", "qty", "filled_qty", "status", "type", "limit_price", "stop_price", "time_in_force")}})
    result = {"parent_order_id": parent_id, "account_id": (runtime.get("account") or {}).get("id"), "members": members}
    if commands is not None:
        candidates = [command for command in commands.get("commands", {}).values() if parent_id in command.get("broker_order_ids", [])
                      and command.get("side") == "BUY" and command.get("terms", {}).get("exit_plan")]
        if len(candidates) != 1:
            raise ValueError("Held amendment requires the original approved app purchase")
        entry = candidates[0]
        approval = commands.get("approvals", {}).get(entry.get("approval_id"), {})
        if (entry.get("account_id") != result["account_id"] or entry.get("terms_sha256") != digest(entry["terms"])
                or approval.get("terms_sha256") != entry["terms_sha256"] or approval.get("account_id") != entry["account_id"]
                or decimal(entry["terms"]["quantity"]) != decimal(parent["qty"])
                or entry["terms"]["instrument_id"] != parent["symbol"] + ".ALPACA" or parent.get("side") != "buy"
                or entry["terms"]["order_type"] != native_type(parent["type"])
                or entry["terms"]["time_in_force"] != parent["time_in_force"].upper()
                or decimal(entry["terms"].get("limit_price")) != decimal(parent.get("limit_price"))):
            raise ValueError("Original purchase approval, account or quantity provenance differs")
        for row in rows:
            if row["id"] == parent_id:
                continue
            children = [child for child in commands.get("commands", {}).values() if row["id"] in child.get("broker_order_ids", [])]
            if (len(children) != 1 or children[0].get("linked_entry_command_id") != entry["id"]
                    or children[0].get("linked_role") != row["group_role"]
                    or children[0].get("account_id") != entry["account_id"]
                    or children[0].get("terms_sha256") != digest(children[0]["terms"])
                    or decimal(children[0]["terms"].get("limit_price")) != decimal(row.get("limit_price"))
                    or decimal(children[0]["terms"].get("stop_price")) != decimal(row.get("stop_price"))):
                raise ValueError("Held sibling lacks its exact approved group provenance")
        result.update(entry_command_id=entry["id"], entry_approval_id=entry["approval_id"], entry_terms_sha256=entry["terms_sha256"])
    return result


def validated_replacement(terms, runtime):
    binding = terms.get("replacement")
    if not binding:
        return None
    matches = [row for row in runtime.get("orders", []) if row.get("id") == binding.get("order_id")]
    if len(matches) != 1:
        raise ValueError("Exact replacement predecessor is not a current authoritative working order")
    order = broker_action_order(runtime, binding.get("order_id"), binding.get("order_version"))
    if terms.get("order_class") == "mleg" or order.get("order_class") == "mleg":
        from .linked_orders import package_terms
        package_terms(terms)
        original = order.get("package_terms") or {}
        if (order.get("order_class") != "mleg" or original.get("legs") != terms["legs"]
                or original.get("instrument_id") != terms["instrument_id"] or original.get("order_type") != terms["order_type"]
                or original.get("execution_profile", "long_only") != terms.get("execution_profile", "long_only")
                or binding.get("account_id") != (runtime.get("account") or {}).get("id")
                or binding.get("client_order_id") != order.get("client_order_id") or binding.get("order_version") != order_version(order)
                or binding.get("symbol") != terms["symbol"] or binding.get("side") != "BUY"
                or decimal(binding.get("filled_quantity")) != decimal(order["filled_qty"])
                or decimal(terms["quantity"]) <= decimal(order["filled_qty"])
                or order.get("status") not in {"new", "partially_filled", "done_for_day"}):
            raise ValueError("Package replacement requires immutable legs/ratios/contracts/intents/type and exact current parent authority")
        return order
    if terms.get("asset_class") == "us_option" or order.get("asset_class") == "us_option":
        option_terms(terms)
        if (order.get("asset_class") != "us_option" or order.get("position_intent") != terms["position_intent"]
                or order.get("option_contract", {}).get("sha256") != terms["option_contract"]["sha256"]):
            raise ValueError("Option replacement preserves exact contract revision and LONG intent")
        if order.get("status") in {"accepted", "pending_new", "pending_cancel", "pending_replace"}:
            raise ValueError("Broker option status is not replaceable; retain the working order and refresh")
    amendment_supported(order)
    contingent = binding.get("contingent_group")
    current = contingent_group(order, runtime)
    if bool(contingent) != bool(current) or current and any(contingent.get(key) != value for key, value in current.items()):
        raise ValueError("Conditional bracket authority changed; review the complete group again")
    filled, total = decimal(order.get("filled_qty")), decimal(terms.get("quantity"))
    if (binding.get("account_id") != (runtime.get("account") or {}).get("id")
            or binding.get("symbol") != terms["symbol"] or binding.get("side") != terms["side"]
            or order.get("symbol") != terms["symbol"] or str(order.get("side")).upper() != terms["side"]
            or native_type(order.get("type", order.get("order_type"))) != terms["order_type"]
            or terms.get("asset_class") != "us_option" and str(order.get("time_in_force")).upper() != terms["time_in_force"]
            or order.get("extended_hours") is not (terms.get("session", "regular") == "extended")
            or order.get("status") not in {"new", "accepted", "partially_filled", "pending_new", "done_for_day", "held"}
            or order.get("import_error") or not binding.get("client_order_id") or binding.get("client_order_id") != order.get("client_order_id")
            or binding.get("order_version") != order_version(order) or filled is None
            or decimal(binding.get("filled_quantity")) != filled or total is None or total <= filled):
        raise ValueError("Replacement predecessor identity, version, filled quantity or compatible terms changed")
    if order.get("group_class") in {"bracket", "oco"} and (total != decimal(order["qty"]) or terms.get("exit_plan")):
        raise ValueError("Linked exit amendments change prices only, never quantity or group membership")
    if (total % 1 or decimal(order["qty"]) % 1) and total != decimal(order["qty"]):
        raise ValueError("Fractional order replacement preserves the exact total quantity; amend prices only")
    fractional_terms(terms)
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
    packages = [row for row in local if row.get("terms", {}).get("order_class") == "mleg"]
    broker_packages = [row for row in runtime.get("orders", []) if row.get("order_class") == "mleg"]
    if packages or broker_packages:
        from .linked_orders import package_legs, package_terms
        ordinary = {**runtime, "orders": [row for row in runtime.get("orders", []) if row.get("order_class") != "mleg" and not row.get("package_parent_id")]}
        state = {**(commands or {}), "commands": {key: row for key, row in (commands or {}).get("commands", {}).items() if row.get("terms", {}).get("order_class") != "mleg"}}
        items, known = working_commitments(ordinary, state if commands is not None else None, constraints)
        covered = {key for row in packages for key in row.get("broker_order_ids", [])}
        entries = [(row, row["terms"], [order for order in broker_packages if order["id"] in row.get("broker_order_ids", []) or order.get("client_order_id") == row.get("client_order_id")]) for row in packages]
        entries += [(None, row.get("package_terms"), [row]) for row in broker_packages if row["id"] not in covered and not any(row.get("client_order_id") == command.get("client_order_id") for command in packages)]
        projected = []
        for command, terms, matches in entries:
            try:
                package_terms(terms)
                cap = decimal(command.get("price_cap")) if command else max(decimal(terms["limit_price"]), Decimal(0)) if terms.get("order_type") == "LIMIT" else None
                fee = decimal(command.get("fee_commitment")) if command else decimal(constraints.get("working_order_fee_caps", {}).get(matches[0]["id"]))
                quantities = [decimal(command.get("remaining_quantity")), decimal(command.get("native_pending_commitment", {}).get("remaining_quantity", "0"))] if command else []
                quantities += [decimal(row["qty"]) - decimal(row["filled_qty"]) for row in matches]
                remaining = max(quantities)
                if remaining < 0 or cap is None or cap < 0 or fee is not None and fee < 0:
                    raise ValueError("Package obligation inputs are unavailable")
                if command:
                    action = command.get("pending_action", {})
                    replacement_not_started = (command["state"] == "replace_pending" and action.get("kind") == "replace"
                        and action.get("state") == "authorized" and action.get("broker_order_id") in command.get("broker_order_ids", [])
                        and action.get("replacement_command_id") and action.get("transport_attempt") == {"version": 1, "state": "not_started"})
                    observed_pending = False
                    if command["state"] == "submitting" and len(matches) == 1 and matches[0].get("status") == "pending_new":
                        try:
                            broker_action_order(runtime, matches[0]["id"])
                            observed_pending = True
                        except ValueError:
                            pass
                    if (command["state"] in {"outcome_unknown", "dispatch_intent", "submitting", "replace_pending", "cancel_pending"}
                            and not replacement_not_started and not observed_pending) or command.get("native_pending_commitment"):
                        known = False
                cash = remaining * cap * contract_multiplier(terms) + (fee or Decimal(0))
                if terms.get("execution_profile") == "bounded_risk_spread_v1":
                    collateral = decimal(command.get("collateral_commitment")) if command else None
                    if collateral is None or collateral < 0:
                        raise ValueError("Retained bounded-risk collateral obligation is unavailable")
                    cash += collateral
                if command:
                    retained = [decimal(command.get("cash_commitment")), decimal(command.get("native_pending_commitment", {}).get("cash_commitment", "0"))]
                    if any(value is None for value in retained):
                        raise ValueError("Retained package commitment is unknown")
                    cash = max(cash, *retained)
                common = {"order_ids": {row["id"] for row in matches}, "command_ids": {command["id"]} if command else set(),
                    "parent": (command or {}).get("parent_command_id"), "replacement": (terms.get("replacement") or {}).get("order_id"), "fee": fee}
                projected.append({**common, "symbol": terms["symbol"], "side": "BUY", "remaining": Decimal(0), "cash": cash, "price": cap, "package_cash": True})
                for leg in package_legs({**terms, "quantity": str(remaining)}) if remaining else []:
                    projected.append({**common, "symbol": leg["symbol"], "side": leg["side"], "remaining": Decimal(leg["quantity"]),
                        "cash": Decimal(0), "price": price_evidence({**leg, "order_type": "MARKET"}, runtime)["price"], "fee": Decimal(0), "package_claim": True,
                        "position_intent": leg["position_intent"], "multiplier": contract_multiplier(leg)})
            except (ValueError, KeyError, TypeError, ArithmeticError):
                known = False
        for item in projected:
            prior = next((row for row in items if row["symbol"] == item["symbol"] and row["side"] == item["side"]
                and (item["parent"] in row["command_ids"] or item["replacement"] in row["order_ids"])), None)
            if prior:
                prior.update(remaining=max(prior["remaining"], item["remaining"]), cash=max(prior["cash"], item["cash"]),
                    order_ids=prior["order_ids"] | item["order_ids"], command_ids=prior["command_ids"] | item["command_ids"])
            else:
                items.append(item)
        return items, known
    items, covered = [], set()
    for command in local:
        matches = [o for o in runtime.get("orders", []) if o.get("id") in command.get("broker_order_ids", [])
                   or o.get("client_order_id") == command.get("client_order_id")]
        if (command.get("terms", {}).get("replacement") or {}).get("contingent_group") and (not matches or all(o.get("exit_reserved") is False for o in matches)):
            covered.update(o["id"] for o in matches)
            continue
        if command.get("linked_exit") and matches and all(o.get("exit_reserved") is False for o in matches):
            covered.update(o["id"] for o in matches)
            continue
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
            cashes.append(max((v for v in quantities if v is not None), default=Decimal(0)) * price * contract_multiplier(command["terms"]) + (fee if fee is not None else Decimal(0)))
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
        if order.get("exposure_status") == "unknown" or order.get("asset_class") not in {"us_equity", "us_option"}:
            known = False
            continue
        if not identity or identity in seen or order.get("import_error"):
            known = False
        seen.add(identity)
        if identity in covered:
            continue
        if order.get("group_role") in {"take_profit", "stop_loss"} and order.get("exit_reserved") is False:
            continue
        qty, filled = decimal(order.get("qty")), decimal(order.get("filled_qty"))
        side = str(order.get("side")).upper()
        price = price_evidence({"symbol": order.get("symbol"), "side": side,
            "order_type": native_type(order.get("type", order.get("order_type"))), "limit_price": order.get("limit_price"),
            "stop_price": order.get("stop_price")}, runtime)["price"]
        fee = decimal(constraints.get("working_order_fee_caps", {}).get(identity))
        if qty is None or filled is None or not 0 <= filled <= qty or side not in {"BUY", "SELL"} or fee is not None and fee < 0 or side == "BUY" and price is None:
            known = False
            continue
        remaining = qty - filled
        items.append({"symbol": order["symbol"], "side": side, "remaining": remaining,
            "cash": (remaining * price * contract_multiplier(order) if side == "BUY" else Decimal(0)) + (fee if fee is not None else Decimal(0)),
            "price": price, "fee": fee, "order_ids": {identity}, "command_ids": set(), "parent": None, "replacement": None})
    for item in list(items):
        previous = next((other for other in items if other is not item and
            (item["parent"] in other["command_ids"] or item["replacement"] in other["order_ids"])), None)
        if previous:
            previous.update(remaining=max(previous["remaining"], item["remaining"]), cash=max(previous["cash"], item["cash"]),
                order_ids=previous["order_ids"] | item["order_ids"], command_ids=previous["command_ids"] | item["command_ids"])
            items.remove(item)
    groups = {}
    by_id = {o["id"]: o for o in runtime.get("orders", [])}
    for item in list(items):
        rows = [by_id[identity] for identity in item["order_ids"] if identity in by_id]
        linked = next((row for row in rows if row.get("group_class") in {"bracket", "oco"}
                       and row.get("group_role") in {"take_profit", "stop_loss"}), None)
        if not linked:
            continue
        key = linked.get("group_parent_id") or linked["id"]
        prior = groups.get(key)
        if prior:
            prior.update(remaining=max(prior["remaining"], item["remaining"]), cash=max(prior["cash"], item["cash"]),
                         order_ids=prior["order_ids"] | item["order_ids"], command_ids=prior["command_ids"] | item["command_ids"])
            items.remove(item)
        else:
            groups[key] = item
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


def fractional_asset(runtime, symbol):
    market = runtime.get("market_data", {}).get(symbol, {})
    info = (market.get("instrument") or {}).get("info") or {}
    asset = info.get("alpaca_asset") or {}
    if (asset.get("fractionable") is not True or asset.get("tradable") is not True or asset.get("class") != "us_equity" or asset.get("status") != "active"
            or asset.get("symbol") != symbol or not asset.get("id") or not info.get("asset_observed_at") or not info.get("asset_source")):
        raise ValueError("Fractional trading requires an observed active fractionable Alpaca equity asset and its source provenance")
    return {"asset": copy.deepcopy(asset), "observed_at": info["asset_observed_at"], "source": info["asset_source"]}


def instruments(runtime, universe):
    observed = {p["symbol"]: p for p in runtime.get("positions", [])}
    result = {}
    for symbol in sorted(set(universe) | set(observed) | set(runtime.get("market_data", {})) | {o["symbol"] for o in runtime.get("orders", []) if o.get("symbol")}):
        holding = observed.get(symbol)
        native = runtime.get("market_data", {}).get(symbol, {}).get("instrument")
        tradable = runtime.get("market_data", {}).get(symbol, {}).get("trade_supported") is True
        supported = bool(native and tradable) or bool(tradable and holding and holding.get("asset_class") == "us_equity"
                                         and holding.get("nautilus") and not holding.get("import_error"))
        reason = (holding or {}).get("import_error")
        if holding and decimal(holding.get("qty")) is None:
            supported, reason = False, reason or "Unknown holdings are observation-only"
        try:
            fractional_asset(runtime, symbol)
            fractionable = True
        except ValueError:
            fractionable = False
        result[symbol] = {"symbol": symbol, "instrument_id": symbol + ".ALPACA" if supported else None,
                          "option_order_profiles": copy.deepcopy(OPTION_ORDER_PROFILES) if runtime.get("market_data", {}).get(symbol, {}).get("option_contract") or (holding or {}).get("asset_class") == "us_option" else None,
                          "asset_class": "us_option" if runtime.get("market_data", {}).get(symbol, {}).get("option_contract") or (holding or {}).get("asset_class") == "us_option" or (native or {}).get("type") == "OptionContract" else "us_equity",
                          "option_contract": runtime.get("market_data", {}).get(symbol, {}).get("option_contract"),
                          "supported": supported and not reason, "limitation": reason or (None if supported else "Supported equity instrument has not been observed"),
                          "holding": bool(holding), "fractionable": fractionable, "quantity_precision": 9 if fractionable else 0}
    return result


def exercise_readiness(terms, runtime, *, commands=None):
    if terms.get("asset_class") != "us_option" or terms.get("order_class") == "mleg":
        return None
    contract = option_contract(terms["option_contract"])
    quantity = remaining_quantity(terms)
    shares = quantity * Decimal(contract["size"])
    commitments, complete = working_commitments(runtime, commands)
    account = runtime.get("account") or {}
    if contract["type"] == "call":
        required = shares * Decimal(contract["strike_price"])
        available = decimal(account.get("cash"))
        if available is not None:
            available -= sum((item["cash"] for item in commitments), Decimal(0))
        unit = "USD for underlying purchase"
    else:
        required = shares
        position = next((row for row in runtime.get("positions", []) if row.get("symbol") == contract["underlying_symbol"] and row.get("asset_class") == "us_equity" and row.get("side") == "long"), None)
        available = decimal(position.get("qty_available")) if position else Decimal(0) if runtime.get("broker_observation", {}).get("positions_complete") else None
        if available is not None:
            available -= sum((item["remaining"] for item in commitments if item["symbol"] == contract["underlying_symbol"]
                and item["side"] == "SELL" and item["command_ids"] and not item["order_ids"]), Decimal(0))
        unit = "Available underlying shares"
    return {"required": str(required), "available": str(available) if available is not None else None, "unit": unit,
        "ready_at_observation": available >= required if available is not None and complete else None,
        "account_at": runtime.get("account_at"), "contract_sha256": terms["option_contract"]["sha256"],
        "basis": "Dated exercise delivery comparison before this proposal's premium; existing pending/local commitments deducted. No permanent reserve, future guarantee, liquidation assumption or exercise authority"}


def impact(terms, runtime, rules, *, commands=None):
    if terms.get("order_class") == "mleg":
        commitments, complete = working_commitments(runtime, commands)
        price = price_evidence(terms, runtime)
        principal = max(price["price"], Decimal(0)) * Decimal(terms["quantity"]) * contract_multiplier(terms) if price["price"] is not None else None
        cash = decimal((runtime.get("account") or {}).get("cash"))
        after = cash - sum((row["cash"] for row in commitments), Decimal(0)) - principal if cash is not None and principal is not None and complete else None
        spread = spread_risk(terms, runtime, commands)
        if terms.get("execution_profile") == "bounded_risk_spread_v1":
            principal = decimal(spread["net_package_obligation_before_costs"])
            after = cash - sum((row["cash"] for row in commitments), Decimal(0)) - principal if cash is not None and principal is not None and complete else None
        return {"package_funding": {"net_premium_estimate": str(price["price"]) if price["price"] is not None else None,
                    "net_debit_obligation": str(principal) if principal is not None else None, "fees": None, "basis": price["basis"]},
            "bounded_risk": spread, "leg_impacts": spread["leg_impacts"],
            "exercise_readiness": None, "price_estimate": str(price["price"]) if price["price"] is not None else None, "price_basis": price["basis"],
            "estimated_principal": str(principal) if principal is not None else None, "estimated_cash_after_commitments_before_fees": str(after) if after is not None else None,
            "conditions": [] if after is not None and after >= 0 else ["Package funding is unavailable or insufficient; review full leg and portfolio risk"],
            "value_basis": "One net package obligation; leg market values are separate from actual execution economics"}
    symbol, side, qty = terms["symbol"], terms["side"], remaining_quantity(terms)
    account = runtime.get("account") or {}
    connected = runtime.get("status") == "connected"
    reconciliation = runtime.get("reconciliation", {})
    position = next((p for p in runtime.get("positions", []) if p["symbol"] == symbol), None)
    current = decimal(position.get("qty")) if position else Decimal(0) if connected and (runtime.get("broker_observation", {}).get("positions_complete") or reconciliation.get("positions_reconciled")) else None
    selected = price_evidence(terms, runtime)
    price, price_basis = selected["price"], selected["basis"]
    multiplier = contract_multiplier(terms)
    principal = price * qty * multiplier if price is not None and qty is not None else None
    delta = (-principal if side == "BUY" else principal) if principal is not None else None
    cash = decimal(account.get("cash")) if connected else None
    equity = decimal(account.get("equity")) if connected else None
    resulting = current + (qty if side == "BUY" else -qty) if current is not None and qty is not None else None
    conditional = (terms.get("replacement") or {}).get("contingent_group")
    if conditional:
        resulting, delta = current, Decimal(0)
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
    position_value = resulting * price * multiplier if resulting is not None and price is not None else None
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
    option_funding = None
    if terms.get("asset_class") == "us_option":
        power = decimal(account.get("options_buying_power"))
        option_funding = {"broker_options_buying_power": str(power) if power is not None else None, "account_at": runtime.get("account_at"),
            "source": "Account-bound Alpaca options_buying_power; not inferred from cash", "proposed_premium_before_known_costs": str(principal) if principal is not None else None,
            "local_unsubmitted_option_reservations": str(sum((item["cash"] for item in observed if item["symbol"] in runtime.get("market_data", {})
                and runtime["market_data"][item["symbol"]].get("option_contract") and item["command_ids"] and not item["order_ids"]), Decimal(0))),
            "basis": "Preview inputs only; final review checks separate cash and options buying power with exact replacement credits. Missing/stale account inputs remain unavailable."}
    return {"conditional_group_amendment": conditional, "bounded_risk": spread_risk(terms, runtime, commands) if terms.get("asset_class") == "us_option" else None,
        "exercise_readiness": exercise_readiness(terms, runtime, commands=commands), "option_funding": option_funding,
            "value_basis": "Option premium market value, not underlying or delta exposure" if terms.get("asset_class") == "us_option" else "Equity market value",
            "existing_quantity": str(current) if current is not None else None,
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


def save(saved, request, runtime, universe, resolve_research, *, commands=None, resolve_price_ref=None):
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
    package = terms.get("order_class") == "mleg"
    if package:
        from .linked_orders import package_instrument_id, package_terms
        terms = copy.deepcopy(terms)
        terms.setdefault("currency", "USD")
        terms.setdefault("session", "regular")
        available_instruments = instruments(runtime, universe)
        for leg in terms.get("legs", []):
            selected = available_instruments.get(leg.get("symbol"), {})
            if not selected.get("supported") or selected.get("asset_class") != "us_option":
                raise ValueError("Every package leg requires a current supported option contract")
            leg.update(instrument_id=selected["instrument_id"], option_contract=copy.deepcopy(selected["option_contract"]))
        terms["instrument_id"] = package_instrument_id(terms.get("legs", []))
        underlying = option_contract(terms["legs"][0]["option_contract"])["underlying_symbol"]
        if terms.get("symbol") not in (None, "", underlying):
            raise ValueError("Package symbol differs from its actual common underlying")
        terms["symbol"] = underlying
        info = package_terms(terms)
        terms["symbol"] = info["underlying"]
    symbol = terms.get("symbol")
    instrument = {"supported": True, "asset_class": "us_option", "fractionable": False, "instrument_id": terms["instrument_id"]} if package else instruments(runtime, universe).get(symbol)
    if not instrument or not instrument["supported"]:
        raise ValueError((instrument or {}).get("limitation") or "Select an observed supported equity")
    quantity = format(equity_quantity(terms.get("quantity", "")), "f")
    if "." in quantity:
        quantity = quantity.rstrip("0").rstrip(".")
    allowed_types = {"MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT", "TRAILING_STOP_MARKET"}
    if terms.get("side") not in {"BUY", "SELL"} or terms.get("order_type") not in allowed_types:
        raise ValueError("Choose a supported market, limit, stop or standalone SELL trailing order")
    limit = terms.get("limit_price") if terms["order_type"] in {"LIMIT", "STOP_LIMIT"} else None
    if not package and limit is not None and (not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", str(limit)) or decimal(limit) <= 0):
        raise ValueError("Enter a positive limit price with at most two decimal places")
    if terms["order_type"] in {"LIMIT", "STOP_LIMIT"} and limit is None:
        raise ValueError("Limit price is required")
    duration = terms.get("time_in_force", "DAY")
    if duration not in {"DAY", "GTC"}:
        raise ValueError("Choose DAY or GTC duration")
    plan = exit_plan(terms.get("exit_plan"), terms["side"])
    stop = terms.get("stop_price") if terms["order_type"] in {"STOP_MARKET", "STOP_LIMIT"} else None
    if stop is not None and (not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", str(stop)) or decimal(stop) <= 0):
        raise ValueError("Enter a positive USD stop trigger with at most two decimal places")
    if terms["order_type"] in {"STOP_MARKET", "STOP_LIMIT"} and stop is None:
        raise ValueError("Stop trigger is required")
    if instrument.get("asset_class") != "us_option" and terms["order_type"] == "STOP_LIMIT" and ((terms["side"] == "BUY" and decimal(limit) < decimal(stop))
                                               or (terms["side"] == "SELL" and decimal(limit) > decimal(stop))):
        raise ValueError("A BUY stop limit must be at or above its trigger; a SELL stop limit must be at or below it")
    rationale = text(terms.get("rationale", ""), 10000, "proposal rationale")
    research = resolve_research(terms["research"]) if terms.get("research") else None
    from .evidence_requirements import DECISION_SCOPES, VERSION
    evidence_scopes = terms.get("decision_evidence_scopes", [])
    if not isinstance(evidence_scopes, list) or any(not isinstance(scope, str) or scope not in DECISION_SCOPES for scope in evidence_scopes):
        raise ValueError("Choose supported evidence dependencies for this decision")
    contract = option_contract(instrument["option_contract"]) if instrument.get("asset_class") == "us_option" and not package else None
    if research and research["symbol"] != (contract["underlying_symbol"] if contract else symbol):
        raise ValueError("Linked research belongs to another symbol")
    exact = {"symbol": symbol, "instrument_id": instrument["instrument_id"], "side": terms["side"],
             "quantity": quantity, "order_type": terms["order_type"], "limit_price": str(limit) if limit is not None else None,
             "time_in_force": duration, "currency": "USD", "session": terms.get("session", "regular"), "rationale": rationale, "research": research,
             "decision_evidence_scopes": sorted(set(evidence_scopes)), "evidence_requirements_version": VERSION,
             "account_id": (runtime.get("account") or {}).get("id")}
    if contract:
        exact.update(asset_class="us_option", option_contract=copy.deepcopy(instrument["option_contract"]), position_intent=terms.get("position_intent"),
            stop_price=str(stop) if stop is not None else None,
            research_context="Underlying analysis only; not an option recommendation" if research else None)
        option_terms(exact)
    if package:
        exact.update(asset_class="us_option", order_class="mleg", legs=copy.deepcopy(terms["legs"]), net_direction=terms["net_direction"],
            execution_profile=terms.get("execution_profile", "long_only"),
            research_context="Underlying analysis only; not package or leg execution evidence" if research else None)
        package_terms(exact)
    fractional_terms({**exact, "exit_plan": plan}, fractionable=instrument["fractionable"])
    if decimal(quantity) % 1:
        exact["fractional_asset"] = fractional_asset(runtime, symbol)
        if exact["session"] == "extended" and exact["fractional_asset"]["asset"].get("fractional_eh_enabled") is not True:
            raise ValueError("Fractional extended trading requires observed fractional_eh_enabled=true asset evidence")
    trail = trailing_terms({**terms, **exact, "exit_plan": plan})
    if trail:
        exact[trail[0]] = str(terms[trail[0]])
    if plan:
        exact["exit_plan"] = plan
        broker_payload(exact, "validate-reviewed-group")
    if stop is not None:
        exact["stop_price"] = str(stop)
    references = terms.get("price_references", [])
    if package and references:
        raise ValueError("An underlying chart price cannot supply a package net premium")
    if not isinstance(references, list) or len(references) > len(PRICE_DESTINATIONS):
        raise ValueError("Invalid retained chart price references")
    if references:
        if resolve_price_ref is None:
            raise ValueError("Exact retained chart source resolution is unavailable")
        verified, destinations = [], set()
        for reference in references:
            reference = price_reference(reference, exact)
            fields = copied_price_fields(reference, exact)
            if fields & destinations:
                raise ValueError("Duplicate copied price destination")
            destinations.update(fields)
            resolved = resolve_price_ref(reference, exact)
            actual = {field: exact.get("exit_plan", {}).get(field.split(".")[1]) if field.startswith("exit_plan.") else exact.get(field) for field in fields}
            if (reference.get("normalization") != resolved["price_ref"]["normalization"]
                    or reference.get("fields") != resolved["fields"] or actual != resolved["fields"]):
                raise ValueError("Copied price or source metadata changed; inspect and copy it again")
            verified.append(resolved["price_ref"])
        exact["price_references"] = verified
    if terms.get("replacement"):
        identity = terms["replacement"].get("order_id")
        order = next((o for o in runtime.get("orders", []) if o.get("id") == identity), None)
        if order is None:
            raise ValueError("Select an exact current broker order to replace")
        exact["replacement"] = {"order_id": identity, "client_order_id": order.get("client_order_id"),
            "account_id": exact["account_id"], "symbol": symbol, "side": exact["side"],
            "filled_quantity": str(order.get("filled_qty")), "order_version": order_version(order)}
        conditional = contingent_group(order, runtime, commands)
        if conditional:
            if commands is None:
                raise ValueError("Held amendments require server-owned purchase authority")
            exact["replacement"]["contingent_group"] = conditional
            entry_terms = commands["commands"][conditional["entry_command_id"]]["terms"]
            exact["decision_evidence_scopes"] = sorted(set(exact["decision_evidence_scopes"]) | set(entry_terms.get("decision_evidence_scopes", [])))
        validated_replacement(exact, runtime)
        if package and exact.get("execution_profile") == "bounded_risk_spread_v1":
            exact["replacement_funding_basis"] = "alpaca-bounded-incremental-v1"
            replacement_funding_route(exact)
    snapshot = {"account": runtime.get("account"), "account_at": runtime.get("account_at"),
                "positions": runtime.get("positions"), "orders": runtime.get("orders"),
                "market": runtime.get("market_data", {}).get(symbol), "reconciliation": runtime.get("reconciliation")}
    if package:
        snapshot["market"] = {leg["symbol"]: runtime.get("market_data", {}).get(leg["symbol"]) for leg in exact["legs"]}
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
