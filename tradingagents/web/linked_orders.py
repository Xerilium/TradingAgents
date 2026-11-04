"""Reviewed linked equity terms and broker/native identities, without local exit emulation."""

import copy
import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal
from functools import reduce
from math import gcd
from urllib.parse import urlsplit
from uuid import UUID


LIVE = {"new", "accepted", "accepted_for_bidding", "pending_new", "partially_filled", "held", "pending_cancel", "pending_replace", "done_for_day"}
OPTION_MAPPING = "alpaca-us-equity-option-date-v1"


def option_contract(value):
    """Validate retained standard deliverables; native dates are representation only."""
    try:
        return _option_contract(value)
    except (KeyError, TypeError, ArithmeticError, AttributeError, OverflowError):
        raise ValueError("Option metadata is incomplete or has unsupported numeric/source fields") from None


def _option_contract(value):
    if not isinstance(value, dict) or value.get("mapping_version") != OPTION_MAPPING:
        raise ValueError("Versioned broker option metadata is unavailable")
    raw = value.get("raw") or {}
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    source = urlsplit(str(value.get("source", "")))
    if (value.get("sha256") != digest or source.scheme != "https" or source.netloc not in {"paper-api.alpaca.markets", "api.alpaca.markets"}
            or not (source.path == "/v2/options/contracts" or source.path.startswith("/v2/options/contracts/"))):
        raise ValueError("Option metadata source or content digest differs")
    UUID(raw["id"])
    UUID(raw["underlying_asset_id"])
    for key in ("requested_at", "received_at"):
        if datetime.fromisoformat(value[key].replace("Z", "+00:00")).utcoffset() is None:
            raise ValueError("Option observation requires timezone-aware timestamps")
    match = re.fullmatch(r"([A-Z]{1,6})(\d{6})([CP])(\d{8})", str(raw.get("symbol", "")))
    expiry = datetime.strptime(raw.get("expiration_date", ""), "%Y-%m-%d").date()
    size, strike = Decimal(str(raw.get("size"))), Decimal(str(raw.get("strike_price")))
    deliverables = raw.get("deliverables") or []
    if (not match or match[1] != raw.get("root_symbol") or match[2] != expiry.strftime("%y%m%d")
            or ("call" if match[3] == "C" else "put") != raw.get("type")
            or Decimal(match[4]) / 1000 != strike or raw.get("style") != "american"
            or not size.is_finite() or size <= 0 or size % 1 or not strike.is_finite() or strike <= 0
            or len(deliverables) != 1 or type(raw.get("ppind")) is not bool):
        raise ValueError("Only identified American equity options with observed whole-share deliverables are supported")
    item = deliverables[0]
    if (item.get("type") != "equity" or item.get("symbol") != raw["underlying_symbol"]
            or Decimal(str(item.get("amount"))) != size or Decimal(str(item.get("allocation_percentage"))) != 100
            or item.get("settlement_type") != "T+1" or item.get("settlement_method") != "CCC"
            or item.get("delayed_settlement") is not False or raw.get("currency") not in (None, "USD")):
        raise ValueError("Nonstandard or unknown option settlement remains observation-only")
    return raw


OPTION_ORDER_PROFILES = {kind: ["DAY", "GTC"] for kind in ("MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT")}
PACKAGE_PROFILES = {"order_types": ["MARKET", "LIMIT"], "time_in_force": ["DAY", "GTC"], "min_legs": 2, "max_legs": 4}
EXECUTION_PROFILES = {
    "long_only": {"label": "Long options only", **PACKAGE_PROFILES, "intents": ["buy_to_open", "sell_to_close"], "same_expiry": False},
    "bounded_risk_spread_v1": {"label": "Bounded risk option spreads", **PACKAGE_PROFILES, "order_types": ["LIMIT"],
        "intents": ["buy_to_open", "sell_to_open", "buy_to_close", "sell_to_close"], "same_expiry": True},
}


def execution_profile_terms(terms):
    profile = terms.get("execution_profile", "long_only")
    if profile not in EXECUTION_PROFILES:
        raise ValueError("Choose an identified execution profile")
    if profile != "long_only" and not is_package(terms) and terms.get("package_validation") is not True:
        raise ValueError("Bounded risk authority applies only to one atomic option package")
    return profile


def native_profile_transition(profile, account=None, *, endpoint=None, source_receipt=None, native_epoch=None):
    if profile not in EXECUTION_PROFILES:
        raise ValueError("Choose an identified execution profile")
    account = account or {}
    blockers = []
    required = ("cash",) if profile == "long_only" else ("cash", "equity", "initial_margin", "maintenance_margin", "options_buying_power")
    for key in required:
        try:
            value = Decimal(str(account[key]))
            if not value.is_finite() or value.quantize(Decimal(".01")) != value or key not in {"cash", "equity"} and value < 0:
                raise ValueError()
        except (KeyError, TypeError, ValueError, ArithmeticError):
            blockers.append("Actual reported " + key + " is unavailable or not exactly representable")
    if not account.get("id") or account.get("status") != "ACTIVE" or account.get("currency") != "USD" or not source_receipt:
        blockers.append("Current authenticated ACTIVE USD account source is unavailable")
    bounded = profile == "bounded_risk_spread_v1"
    projection = None
    if bounded:
        if endpoint != "https://paper-api.alpaca.markets":
            blockers.append("LIVE margin mapping requires a separate current direct brokerage contract/account decision")
        if any(account.get(key) is not False for key in ("trading_blocked", "account_blocked", "trade_suspended_by_user")):
            blockers.append("Current broker account trading permissions are blocked or unknown")
        if type(account.get("options_trading_level")) is not int or account["options_trading_level"] < 3:
            blockers.append("Current Level 3 option package permission is unavailable")
        if not blockers:
            total, locked = Decimal(str(account["equity"])), Decimal(str(account["initial_margin"]))
            projection = {"version": "alpaca-paper-equity-initial-v1", "currency": "USD",
                "source_fields": {key: account[key] for key in required},
                "derived": {"total": str(total), "locked": str(locked), "free": str(total - locked)},
                "reported_margin": {"initial": account["initial_margin"], "maintenance": account["maintenance_margin"], "currency": "USD"},
                "calculate_account_state": False, "authority": "diagnostic_equity_less_initial_requirement_not_spendable_cash",
                "source_receipt": source_receipt}
    elif Decimal(str(account.get("multiplier", "0"))) != 1 or account.get("shorting_enabled") is not False:
        blockers.append("Default native CASH representation requires observed unleveraged, non-shorting account facts")
    return {"selected_profile": profile, "account_id": account.get("id"), "endpoint": endpoint, "native_epoch": native_epoch,
        "requested_native_account_type": "MARGIN" if bounded else "CASH", "native_account_type": None if blockers else "MARGIN" if bounded else "CASH",
        "mapping_scope": "paper_margin_simulation" if bounded and endpoint == "https://paper-api.alpaca.markets" else "default_long_only" if not bounded else "live_contract_unverified",
        "legal_account_evidence": {"status": "not_a_legal_account_claim" if bounded and endpoint == "https://paper-api.alpaca.markets" else "unverified",
            "source": "https://docs.alpaca.markets/us/docs/paper-trading" if endpoint == "https://paper-api.alpaca.markets" else "https://docs.alpaca.markets/us/docs/account-plans"},
        "reported_account": {key: account.get(key) for key in required}, "source_receipt": source_receipt,
        "cash_balance_basis": "alpaca-paper-equity-initial-v1" if bounded else "existing_long_only_representation",
        "balance_projection": projection,
        "eligibility": {"eligible": not blockers, "blockers": blockers}}


def is_package(terms):
    return terms.get("order_class") == "mleg"


def package_valuation_key(terms):
    return hashlib.sha256(json.dumps(terms, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_package_valuation(value, terms, runtime=None):
    try:
        return _validate_package_valuation(value, terms, runtime)
    except (KeyError, TypeError, AttributeError, ArithmeticError, OverflowError):
        raise ValueError("Package valuation metadata is incomplete or unrepresentable") from None


def _validate_package_valuation(value, terms, runtime=None):
    package = package_terms(terms)
    keys = ("version", "status", "terms_sha256", "instrument_id", "native_epoch", "account_id", "endpoint", "source_generation",
            "inputs", "settings", "output", "output_sha256", "quantity", "native_limits")
    if not isinstance(value, dict) or any(key not in value for key in keys):
        raise ValueError("Complete native package valuation evidence is unavailable")
    material = {key: value[key] for key in keys}
    if (value["version"] != "native-spread-valuation-v1" or value["status"] != "available"
            or value["terms_sha256"] != package_valuation_key(terms) or value["instrument_id"] != package["instrument_id"]
            or value.get("binding_sha256") != package_valuation_key(material) or value["output_sha256"] != package_valuation_key(value["output"])
            or value["source_generation"] != package_valuation_key(value["inputs"])
            or value["settings"] != {"implementation": "nautilus_trader.data.aggregation.SpreadQuoteAggregator", "disable_vega_pricing": True,
                "update_interval_seconds": None, "historical": False, "rounding": "public spread instrument make_price/make_qty; IEEE754 upstream calculation"}
            or not value["native_epoch"] or value["endpoint"] not in {"https://paper-api.alpaca.markets", "https://api.alpaca.markets"}):
        raise ValueError("Native package valuation identity, settings or source hash differs")
    UUID(value["account_id"])
    inputs = value["inputs"]
    if not isinstance(inputs, list) or len(inputs) != len(terms["legs"]) or len({item.get("instrument_id") for item in inputs}) != len(inputs):
        raise ValueError("Every exact package leg requires unique native valuation evidence")
    for leg in terms["legs"]:
        matches = [item for item in inputs if item.get("instrument_id") == leg["instrument_id"]]
        if len(matches) != 1:
            raise ValueError("Package valuation omits an actual leg")
        item, raw = matches[0], option_contract(leg["option_contract"])
        receipt = item.get("source_receipt") or {}
        quote = item.get("quote") or {}
        if (item.get("contract_sha256") != leg["option_contract"]["sha256"] or item.get("contract_id") != raw["id"]
                or item.get("signed_ratio") != int(leg["ratio_qty"]) * (1 if leg["side"] == "BUY" else -1)
                or Decimal(str(item.get("multiplier"))) != package["multiplier"] or item.get("currency") != "USD"
                or item.get("feed") not in {"opra", "indicative"} or item.get("scope") != "alpaca_option_quote"
                or not receipt.get("path") or not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("sha256", "")))
                or any(not re.fullmatch(r"[0-9a-f]{64}", str(item.get(key, ""))) for key in ("raw_quote_sha256", "raw_response_sha256"))
                or any(key not in quote for key in ("bid_price", "ask_price", "bid_size", "ask_size", "ts_event", "ts_init"))
                or any(not Decimal(str(quote[key])).is_finite() or Decimal(str(quote[key])) < 0 for key in ("bid_price", "ask_price", "bid_size", "ask_size"))
                or Decimal(str(quote["ask_price"])) <= 0 or Decimal(str(quote["bid_price"])) > Decimal(str(quote["ask_price"]))
                or int(quote["ts_event"]) <= 0 or int(quote["ts_init"]) <= 0):
            raise ValueError("Actual package quote, sizes, timestamp or contract/source proof differs")
        if item.get("source_generation") != package_valuation_key({key: item[key] for key in
                ("raw_quote_sha256", "raw_response_sha256", "feed", "scope", "quote")}):
            raise ValueError("Actual leg quote generation differs")
        if runtime is not None:
            current = runtime.get("market_data", {}).get(leg["symbol"], {})
            if (current.get("error") or current.get("option_contract", {}).get("sha256") != item["contract_sha256"]
                    or item["feed"] != runtime.get("option_feed")
                    or current.get("quote_source") != {key: item[key] for key in
                        ("source_generation", "raw_quote_sha256", "raw_response_sha256", "feed", "scope", "source_receipt", "quote")}):
                raise ValueError("Current actual package quote source changed or is unavailable")
    quantity, limits = value["quantity"], value["native_limits"]
    output = value["output"]
    if (output.get("currency") != "USD" or any(key not in output for key in ("bid_price", "ask_price", "bid_size", "ask_size", "ts_event", "ts_init"))
            or any(not Decimal(str(output[key])).is_finite() for key in ("bid_price", "ask_price", "bid_size", "ask_size"))
            or Decimal(str(output["bid_price"])) > Decimal(str(output["ask_price"]))
            or any(Decimal(str(output[key])) < 0 or Decimal(str(output[key])) % 1 for key in ("bid_size", "ask_size"))
            or int(output["ts_event"]) <= 0 or int(output["ts_init"]) <= 0):
        raise ValueError("Public native derived output prices, sizes or times are invalid")
    if (Decimal(str(quantity.get("approved_total"))) != Decimal(terms["quantity"])
            or Decimal(str(quantity.get("remaining"))) + Decimal(str(quantity.get("already_filled"))) != Decimal(terms["quantity"])
            or not 0 < Decimal(str(quantity["remaining"])) <= Decimal(terms["quantity"]) or Decimal(str(quantity["remaining"])) % 1
            or limits.get("blockers") or len(limits.get("per_leg", [])) != len(inputs)):
        raise ValueError("Exact package quantity or native cap/bounds evidence is unavailable")
    if (not 0 <= Decimal(str(quantity["ancestor_offset"])) <= Decimal(str(quantity["already_filled"]))
            or (terms.get("replacement") or {}).get("order_id") != (quantity.get("replacement_source") or {}).get("id")):
        raise ValueError("Package replacement source/offset differs from exact approved terms")
    cap_rows = limits["native_caps"]
    cap_map = {row["instrument_id"]: row["amount"] for row in cap_rows}
    if (len(cap_rows) != len(cap_map) or limits.get("source") != "public Instrument.notional_value and RiskEngine.max_notionals_per_order"
            or limits.get("margin_collateral_checked") is not False):
        raise ValueError("Original native cap provenance is unavailable")
    expected = {leg["instrument_id"]: leg for leg in terms["legs"]}
    if len({row["instrument_id"] for row in limits["per_leg"]}) != len(expected):
        raise ValueError("Native per-leg limit evidence omits or repeats a contract")
    for item in limits["per_leg"] + [limits["spread"]]:
        spread_check = item["instrument_id"] == package["instrument_id"]
        leg = None if spread_check else expected[item["instrument_id"]]
        count = Decimal(str(quantity["remaining"])) * (1 if spread_check else Decimal(leg["ratio_qty"]))
        notional = Decimal(str(item["notional"]["amount"]))
        cap, bounds = item["max_notional"], item["bounds"]
        amount = abs(notional) if spread_check else notional
        if (item.get("blockers") or Decimal(str(item["quantity"])) != count or not notional.is_finite()
                or item["notional"]["currency"] != "USD" or cap["currency"] != "USD"
                or type(cap["configured"]) is not bool or cap["configured"] != (item["instrument_id"] in cap_map)
                or cap["original"] != cap_map.get(item["instrument_id"]) or cap["amount"] != cap["original"]
                or cap["amount"] is not None and (not Decimal(str(cap["amount"])).is_finite() or Decimal(str(cap["amount"])) < 0 or amount > Decimal(str(cap["amount"])))
                or not spread_check and (amount < 0 or item["side"] != leg["side"] or item["quote_side"] != ("ask_price" if leg["side"] == "BUY" else "bid_price"))):
            raise ValueError("Actual native notional/cap or exact per-leg side/quantity differs")
        increment = Decimal(str(bounds["size_increment"]))
        if (not increment.is_finite() or increment <= 0 or count % increment
                or bounds["min_quantity"] is not None and count < Decimal(bounds["min_quantity"])
                or bounds["max_quantity"] is not None and count > Decimal(bounds["max_quantity"])):
            raise ValueError("Actual native instrument quantity bounds are unavailable or exceeded")
        for name in ("min_notional", "max_notional"):
            if bounds[name] is not None:
                number, currency = bounds[name].rsplit(" ", 1)
                if currency != "USD" or (amount < Decimal(number) if name == "min_notional" else amount > Decimal(number)):
                    raise ValueError("Actual native instrument notional bounds are unavailable or exceeded")
    spread = limits["spread"]
    if (spread.get("supplemental_abs") is not True or spread.get("actual_broker_price_cap") is not False
            or Decimal(str(spread["absolute_notional"])) != abs(Decimal(str(spread["notional"]["amount"])))):
        raise ValueError("Supplemental ABS spread cap must remain distinct from actual broker price limits")
    if terms["order_type"] == "LIMIT":
        limit_amount = Decimal(str(spread["approved_limit_absolute_notional"]))
        cap = spread["max_notional"]["amount"]
        if not limit_amount.is_finite() or limit_amount < 0 or cap is not None and limit_amount > Decimal(str(cap)):
            raise ValueError("Approved signed LIMIT exceeds the original supplemental ABS spread cap")
    sizes = limits["size_limits"]
    bid_units = min(Decimal(str(item["quote"]["bid_size" if item["signed_ratio"] > 0 else "ask_size"])) / abs(item["signed_ratio"]) for item in inputs)
    ask_units = min(Decimal(str(item["quote"]["ask_size" if item["signed_ratio"] > 0 else "bid_size"])) / abs(item["signed_ratio"]) for item in inputs)
    if (Decimal(str(sizes["native_bid_units"])) != Decimal(str(output["bid_size"]))
            or Decimal(str(sizes["native_ask_units"])) != Decimal(str(output["ask_size"]))
            or Decimal(str(sizes["exact_bid_units"])) != bid_units or Decimal(str(sizes["exact_ask_units"])) != ask_units):
        raise ValueError("Actual leg size/ratio evidence differs from native output size rounding")
    if runtime is not None:
        native = runtime.get("native_risk") or {}
        current_caps = (native.get("values") or {}).get("max_notional_per_order")
        if native.get("status") != "available" or not isinstance(current_caps, list) or {row["instrument_id"]: row["amount"] for row in current_caps} != cap_map:
            raise ValueError("Current original native notional caps changed or are unavailable")
        current = runtime.get("package_valuations", {}).get(package_valuation_key(terms))
        if not isinstance(current, dict) or current.get("binding_sha256") != value["binding_sha256"]:
            raise ValueError("Current native-derived output, instrument bounds or notional evidence changed")
    if runtime is not None and (value["account_id"] != runtime.get("account", {}).get("id")
            or value["native_epoch"] != runtime.get("native_epoch") or value["endpoint"] != runtime.get("endpoint")):
        raise ValueError("Package valuation belongs to a different native account session")
    return material


def package_instrument_id(legs):
    """Public generic-spread identifier format; native construction verifies it."""
    return "___".join(("(" + str(leg["ratio_qty"]) + ")" if leg["side"] == "BUY" else "((" + str(leg["ratio_qty"]) + "))")
                      + leg["symbol"] for leg in sorted(legs, key=lambda item: item["symbol"])) + ".ALPACA"


def package_legs(terms):
    quantity = equity_quantity(terms["quantity"])
    return [{**leg, "asset_class": "us_option", "order_class": "simple", "currency": "USD", "session": "regular",
             "order_type": "MARKET", "time_in_force": terms["time_in_force"],
             "execution_profile": terms.get("execution_profile", "long_only"), "package_validation": True,
             "instrument_id": leg["symbol"] + ".ALPACA", "quantity": format(quantity * Decimal(str(leg["ratio_qty"])), "f")}
            for leg in terms["legs"]]


def package_terms(terms):
    profile = execution_profile_terms(terms)
    legs = terms.get("legs")
    if (not is_package(terms) or not isinstance(legs, list) or not 2 <= len(legs) <= 4
            or terms.get("asset_class") != "us_option" or terms.get("side") != "BUY" or terms.get("currency") != "USD"
            or terms.get("order_type") not in {"MARKET", "LIMIT"} or terms.get("time_in_force") not in {"DAY", "GTC"}
            or terms.get("session", "regular") != "regular" or any(terms.get(key) not in (None, "") for key in ("exit_plan", "stop_price", "trail_price", "trail_percent", "notional"))):
        raise ValueError("Atomic option packages require 2–4 BTO/STC legs and MARKET/LIMIT DAY/GTC regular-session terms")
    quantity = equity_quantity(terms["quantity"])
    if terms["order_type"] not in EXECUTION_PROFILES[profile]["order_types"]:
        raise ValueError("The bounded risk spread profile requires an explicit signed NET LIMIT")
    if quantity % 1:
        raise ValueError("Package quantity must be whole strategy units")
    contracts, ratios, ids, symbols = [], [], set(), set()
    for leg in legs:
        if not isinstance(leg, dict) or set(leg) != {"id", "symbol", "instrument_id", "side", "position_intent", "ratio_qty", "option_contract"}:
            raise ValueError("Invalid package leg")
        raw = option_contract(leg.get("option_contract"))
        ratio = equity_quantity(leg.get("ratio_qty"))
        if (ratio % 1 or str(int(ratio)) != str(leg["ratio_qty"]) or leg.get("symbol") != raw["symbol"]
                or leg.get("instrument_id") != raw["symbol"] + ".ALPACA" or not isinstance(leg.get("id"), str) or not leg["id"]
                or leg["id"] in ids or raw["symbol"] in symbols
                or leg.get("position_intent") not in EXECUTION_PROFILES[profile]["intents"]
                or leg.get("side") != ("BUY" if str(leg.get("position_intent", "")).startswith("buy_") else "SELL")):
            raise ValueError("Package legs require distinct identities/contracts, whole ratios and exact BTO/STC intent")
        if contracts and any(raw[key] != contracts[0][key] for key in ("underlying_symbol", "underlying_asset_id", "size", "deliverables")):
            raise ValueError("Package legs require the same underlying and compatible actual deliverables/multiplier")
        if contracts and EXECUTION_PROFILES[profile]["same_expiry"] and raw["expiration_date"] != contracts[0]["expiration_date"]:
            raise ValueError("Bounded risk spreads require the same actual expiration date")
        ids.add(leg["id"])
        symbols.add(raw["symbol"])
        contracts.append(raw)
        ratios.append(int(ratio))
    if reduce(gcd, ratios) != 1:
        raise ValueError("Package ratios must already be normalized to GCD 1; quantities and prices are never silently changed")
    if profile == "bounded_risk_spread_v1" and any(leg["position_intent"] == "sell_to_open" for leg in legs) and not any(leg["position_intent"] == "buy_to_open" for leg in legs):
        raise ValueError("New short openings require protection bought within the same complete atomic package")
    identity = package_instrument_id(legs)
    if terms.get("instrument_id") != identity or terms.get("symbol") != contracts[0]["underlying_symbol"]:
        raise ValueError("Package internal instrument identity differs from its actual leg contract")
    price = terms.get("limit_price")
    if terms.get("net_direction") not in {"debit", "credit"}:
        raise ValueError("Choose an explicit net debit/credit intent; MARKET direction remains an estimate")
    if terms["order_type"] == "LIMIT":
        if not re.fullmatch(r"-?\d{1,12}(?:\.\d{1,2})?", str(price)) or Decimal(str(price)) == 0:
            raise ValueError("Package LIMIT requires exact signed nonzero cent-representable pricing")
        if (Decimal(str(price)) > 0) != (terms["net_direction"] == "debit"):
            raise ValueError("Positive package limits mean debit; negative limits mean credit")
    elif price not in (None, ""):
        raise ValueError("MARKET package has no broker-enforced price or debit/credit cap")
    expanded = package_legs(terms)
    for leg in expanded:
        equity_quantity(leg["quantity"])
    return {"underlying": contracts[0]["underlying_symbol"], "multiplier": Decimal(contracts[0]["size"]),
            "instrument_id": identity, "contracts": contracts, "legs": expanded}


def package_observation(row, terms):
    """Bind actual nested broker members to retained authority, preserving raw parent fields."""
    package_terms(terms)
    children = row.get("legs")
    if (row.get("order_class") != "mleg" or not isinstance(children, list) or len(children) != len(terms["legs"])
            or native_type(row.get("type")) != terms["order_type"] or str(row.get("time_in_force", "")).upper() != terms["time_in_force"]
            or Decimal(str(row.get("qty"))) != Decimal(terms["quantity"])
            or (Decimal(str(row["limit_price"])) if row.get("limit_price") is not None else None)
                != (Decimal(terms["limit_price"]) if terms.get("limit_price") is not None else None)
            or row.get("extended_hours") not in (None, False)):
        raise ValueError("Broker package parent differs from exact approved units/type/duration/pricing")
    UUID(row["id"])
    members, seen, matched = [], set(), set()
    for source in children:
        matches = [leg for leg in terms["legs"] if source.get("symbol") == leg["symbol"]]
        if len(matches) != 1 or source.get("id") in seen:
            raise ValueError("Broker package member identity is missing, duplicated or differs")
        leg = matches[0]
        if leg["id"] in matched:
            raise ValueError("Broker package repeats a canonical contract and omits another member")
        UUID(source["id"])
        if (source.get("side") != leg["side"].lower() or source.get("position_intent") != leg["position_intent"]
                or source.get("asset_class") != "us_option" or source.get("legs")
                or Decimal(str(source.get("qty"))) != Decimal(terms["quantity"]) * Decimal(leg["ratio_qty"])
                or source.get("ratio_qty") is not None and Decimal(str(source["ratio_qty"])) != Decimal(leg["ratio_qty"])
                or source.get("asset_id") is not None and source["asset_id"] != leg["option_contract"]["raw"]["id"]):
            raise ValueError("Broker package leg quantity, ratio, contract or BTO/STC intent differs")
        seen.add(source["id"])
        matched.add(leg["id"])
        members.append({**copy.deepcopy(source), "option_contract": copy.deepcopy(leg["option_contract"]),
            "package_parent_id": row["id"], "package_leg_id": leg["id"], "package_ratio_qty": leg["ratio_qty"],
            "execution_profile": terms.get("execution_profile", "long_only"),
            "native_client_order_id": row["client_order_id"] + "-LEG-" + source["id"]})
    if matched != {leg["id"] for leg in terms["legs"]}:
        raise ValueError("Broker package does not cover every canonical contract")
    mapping = {"parent_id": row["id"], "leg_ids": sorted(seen), "basis": "actual_nested_members_and_exact_retained_terms"}
    return {**copy.deepcopy(row), "package_terms": copy.deepcopy(terms), "package_members": members, "package_mapping": mapping,
            "package_control": {"internal": True, "economics": "actual_leg_fills_only", "source_mapping": mapping}}


def option_order_prices(terms):
    if terms.get("time_in_force") not in OPTION_ORDER_PROFILES.get(terms.get("order_type"), ()):
        raise ValueError("Single-leg options support MARKET/LIMIT/STOP_MARKET/STOP_LIMIT with DAY/GTC")
    fields = ({"limit_price"} if terms["order_type"] in {"LIMIT", "STOP_LIMIT"} else set()) | ({"stop_price"} if terms["order_type"] in {"STOP_MARKET", "STOP_LIMIT"} else set())
    for key in {"limit_price", "stop_price"}:
        value = terms.get(key)
        if key in fields and (not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", str(value)) or Decimal(str(value)) <= 0):
            raise ValueError("Option " + key + " must be an exact positive cent-representable premium")
        if key not in fields and value not in (None, ""):
            raise ValueError("Option price field does not belong to the selected order type")
    return fields


def option_terms(terms):
    if is_package(terms):
        return package_terms(terms)
    contract = option_contract(terms.get("option_contract"))
    quantity = equity_quantity(terms["quantity"])
    profile = execution_profile_terms(terms)
    intent = terms.get("position_intent")
    if (quantity % 1 or intent not in EXECUTION_PROFILES[profile]["intents"]
            or terms.get("side") != ("BUY" if str(intent).startswith("buy_") else "SELL")
            or terms.get("symbol") != contract["symbol"] or terms.get("asset_class") != "us_option"
            or terms.get("currency") != "USD" or terms.get("session", "regular") != "regular"
            or terms.get("exit_plan") or terms.get("trail_price") or terms.get("trail_percent")):
        raise ValueError("Options require whole-contract LONG BTO/STC, standalone regular-session terms")
    option_order_prices(terms)
    return contract


def contract_multiplier(terms):
    if is_package(terms):
        return package_terms(terms)["multiplier"]
    return Decimal(option_contract(terms["option_contract"])["size"]) if terms.get("asset_class") == "us_option" else Decimal(1)


def broker_position_quantity(row):
    quantity = Decimal(str(row["qty"]))
    if not quantity.is_finite() or row.get("side") not in {"long", "short"}:
        raise ValueError("Broker position quantity/direction is unavailable")
    if quantity < 0 and row["side"] != "short":
        raise ValueError("Broker position sign conflicts with its direction")
    magnitude = equity_quantity(format(abs(quantity), "f"))
    return -magnitude if row["side"] == "short" else magnitude


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
    if terms.get("asset_class") == "us_option":
        option_terms(terms)
        return equity_quantity(terms["quantity"])
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
    if is_package(terms):
        return "mleg"
    plan = terms.get("exit_plan") or {}
    return "oco" if plan and terms["side"] == "SELL" else "bracket" if plan.get("take_profit") and plan.get("stop_price") else "oto" if plan else "simple"


def broker_payload(terms, client_order_id):
    if terms.get("package_validation"):
        raise ValueError("Internal leg validation terms are never independently submitted")
    if is_package(terms):
        package_terms(terms)
        body = {"order_class": "mleg", "qty": terms["quantity"], "type": terms["order_type"].lower(),
                "time_in_force": terms["time_in_force"].lower(), "client_order_id": client_order_id,
                "legs": [{"symbol": leg["symbol"], "ratio_qty": leg["ratio_qty"], "side": leg["side"].lower(),
                          "position_intent": leg["position_intent"]} for leg in terms["legs"]]}
        if terms["order_type"] == "LIMIT":
            body["limit_price"] = terms["limit_price"]
        return body
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
    if terms.get("asset_class") == "us_option":
        body["position_intent"] = terms["position_intent"]
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


class UnsupportedOrderClass(ValueError):
    """Broker observations remain valid outside the supported equity order classes."""


def observed_orders(rows, commands=()):
    """Partition observations without reinterpreting unsupported parents or legs."""
    supported, unsupported = [], []
    def equity(row):
        return (row.get("asset_class") in {"us_equity", "us_option"}
                and (row.get("asset_class") != "us_option" or row.get("order_class") in (None, "", "simple") and not row.get("legs"))
                and row.get("order_class") in {None, "", "simple", "bracket", "oto", "oco"}
                and all(equity(child) for child in row.get("legs") or []))
    for row in rows:
        if row.get("order_class") == "mleg":
            matches = [command for command in commands if is_package(command.get("terms", {})) and
                (row.get("client_order_id") == command.get("client_order_id") or row.get("id") in command.get("broker_order_ids", []))]
            try:
                if len(matches) != 1:
                    raise ValueError("Package has no unique retained canonical authority")
                parent = package_observation(row, matches[0]["terms"])
                supported.append(parent)
                continue
            except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
                unsupported.append({**copy.deepcopy(row), "import_error": str(exc), "exposure_status": "unknown"})
                continue
        if not equity(row):
            unsupported.append({**copy.deepcopy(row), "import_error": "Broker order is observation-only; native equity mapping unavailable",
                                "exposure_status": "unknown"})
        else:
            supported.append(row)
    return flatten_orders(supported), unsupported


def flatten_orders(rows):
    """Retain every broker leg once; relationships come only from a nested broker response."""
    output = {}
    def add(source, parent=None):
        row = copy.deepcopy(source)
        if row.get("order_class") == "mleg":
            if not row.get("package_terms") or parent:
                raise UnsupportedOrderClass("Package requires an exact retained member mapping")
            prior = output.get(row["id"])
            if prior and any(prior.get(key) != row.get(key) for key in ("client_order_id", "qty", "filled_qty", "filled_avg_price", "type", "time_in_force", "status", "limit_price", "legs")):
                raise ValueError("Conflicting duplicate actual package parent")
            output[row["id"]] = row
            for member in row["package_members"]:
                prior = output.get(member["id"])
                if prior and (prior.get("package_parent_id") not in (None, row["id"])
                        or any(prior.get(key) != member.get(key) for key in ("client_order_id", "symbol", "side", "type", "qty", "filled_qty", "status", "filled_avg_price", "position_intent"))):
                    raise ValueError("Conflicting actual package leg observations")
                output[member["id"]] = copy.deepcopy(member)
            return
        children = row.pop("legs", None) or []
        kind = (parent or row).get("group_class") or (parent or row).get("order_class") or "simple"
        if kind not in {"simple", "bracket", "oto", "oco"}:
            raise UnsupportedOrderClass("Unsupported broker order class")
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
                  client_order_id=ClientOrderId(client_order_id),
                  reduce_only=terms.get("position_intent") == "sell_to_close",
                  tags=["atomic_option_package"] if is_package(terms) else ["option_intent:" + terms["position_intent"]] if terms.get("asset_class") == "us_option" else ["extended_hours"] if session_terms(terms) == "extended" else None)
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
    if row.get("package_terms"):
        offset = Decimal(str((row.get("native_replacement_quantity_binding") or {}).get("ancestor_filled_quantity", "0")))
        return native_order(factory, {**row["package_terms"], "quantity": str(Decimal(row["qty"]) - offset)}, row.get("native_client_order_id") or row["client_order_id"])
    order = native_order(factory, {"instrument_id": row["symbol"] + ".ALPACA", "side": row["side"].upper(),
        "symbol": row["symbol"], "asset_class": row.get("asset_class"), "currency": "USD",
        "option_contract": row.get("option_contract"), "position_intent": row.get("position_intent"),
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
