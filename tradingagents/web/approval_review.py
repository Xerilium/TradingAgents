"""Server-owned review of exact terms against recorded evidence and observations."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

from .investor import RULES, decimal, digest, execution_costs, price_evidence, validated_replacement


def read_artifact(root, reference):
    try:
        path = (root / reference["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            return None
        raw = path.read_bytes()
        return json.loads(raw) if hashlib.sha256(raw).hexdigest() == reference["sha256"] else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def evaluate(proposal, policy, runtime, evidence, history, commands, constraints, root):
    from .admission import account_version, instant
    from .evidence_requirements import SUPPLEMENTARY, requirements
    checks, references = [], {}
    def check(name, passed, reason, source=None):
        checks.append({"name": name, "passed": bool(passed), "reason": reason, "source": source})
    def artifact(reference):
        return read_artifact(root, reference)
    def age(value, maximum):
        try:
            limit = decimal(maximum)
            elapsed = Decimal(str((datetime.now(UTC) - instant(value)).total_seconds()))
            return elapsed >= 0 and (maximum in (None, "") or limit is not None and limit > 0 and elapsed <= limit)
        except (ValueError, TypeError, AttributeError):
            return False
    terms, symbol = proposal["terms"], proposal["terms"]["symbol"]
    required = requirements(terms, policy)
    check("evidence_requirements", not required["unresolved"],
          "; ".join(required["unresolved"]) or "Versioned decision/policy evidence dependencies are established", required)
    account, reconciliation = runtime.get("account") or {}, runtime.get("reconciliation", {})
    check("exact_terms", proposal["terms_sha256"] == digest(terms) and proposal["status"] == "draft",
          "Saved draft terms and their digest must match")
    check("buy_stop_mapping", not (terms["side"] == "BUY" and terms["order_type"] == "STOP_MARKET"),
          "BUY stop-market submission is unavailable: broker documentation describes conversion to stop-limit; review an explicit STOP_LIMIT trigger and limit instead")
    from .linked_orders import trailing_terms, session_terms
    session_terms(terms)
    trailing_terms(terms)
    if decimal(terms["quantity"]) % 1:
        from .investor import fractional_asset
        from .linked_orders import fractional_terms
        try:
            fractional_terms(terms, fractionable=True)
            valid = terms.get("fractional_asset") == fractional_asset(runtime, symbol)
            if terms.get("session", "regular") == "extended":
                valid = valid and terms["fractional_asset"]["asset"].get("fractional_eh_enabled") is True
        except ValueError:
            valid = False
        check("fractional_asset", valid, "Exact fractional DAY terms must retain current observed fractionable asset identity and provenance", terms.get("fractional_asset"))
    check("account", runtime.get("status") == "connected" and reconciliation.get("status") == "reconciled"
          and account.get("id") == terms.get("account_id") and not runtime.get("local_record_error"),
          "Current account identity and complete native/broker reconciliation are required")
    check("broker_permission", account.get("trading_blocked") is not True, "Alpaca reports trading blocked for this account" if account.get("trading_blocked") is True else "No broker trading block is reported")
    check("account_age", age(runtime.get("account_at"), constraints.get("account_max_age_seconds")),
          "Account observation must be current and satisfy any configured age limit", runtime.get("account_at"))
    market = runtime.get("market_data", {}).get(symbol, {})
    selected = price_evidence(terms, runtime)
    observed = price_evidence({**terms, "order_type": "MARKET"}, runtime)
    event = observed["ts_event"]
    try:
        event_time = datetime.fromtimestamp(int(event) / 1e9, UTC).isoformat()
    except (ValueError, TypeError, OverflowError):
        event_time = None
    check("instrument", market.get("trade_supported") is True and market.get("instrument") is not None,
          "An observed tradable equity instrument is required")
    needs_observation = terms["order_type"] in {"MARKET", "STOP_MARKET", "TRAILING_STOP_MARKET"} or constraints.get("quote_max_age_seconds") not in (None, "")
    check("price", selected["price"] is not None and (not needs_observation or age(event_time, constraints.get("quote_max_age_seconds"))),
          "Use exact LIMIT terms or dated IEX side-quote/last-trade evidence; configured freshness checks still apply", selected["basis"])
    plan = terms.get("exit_plan") or {}
    if plan:
        from .linked_orders import exit_plan
        try:
            exit_plan(plan, terms["side"])
            bases = [price for price in (observed["price"], selected["price"]) if price is not None]
            valid = bool(bases) and (not plan.get("stop_price") or decimal(plan["stop_price"]) <= min(bases) - Decimal("0.01"))
        except (ValueError, TypeError, KeyError):
            valid = False
        check("exit_plan", valid, "Linked exit USD prices must be valid; the stop trigger must be at least USD 0.01 below entry and current price bases")
    try:
        predecessor = validated_replacement(terms, runtime)
        replacement_valid = True
    except ValueError:
        predecessor, replacement_valid = None, False
    if terms.get("replacement"):
        check("replacement", replacement_valid, "Exact predecessor identity, filled quantity and version must still match", terms["replacement"])
    check("policy_revision", proposal["policy_revision"] == policy["revision"], "Proposal must use the current policy revision")
    cap, fees = execution_costs(terms, runtime, constraints)
    ceiling = decimal(constraints.get("max_execution_price"))
    check("price_and_fee_bounds", cap is not None and cap > 0 and (fees is None or fees >= 0)
          and (terms["side"] != "BUY" or terms["order_type"] not in {"MARKET", "STOP_MARKET"} or ceiling is None or selected["price"] is not None and selected["price"] <= ceiling),
          "Use exact limit terms or an observed market-price estimate; honor configured buy/fee bounds. Unknown fees are excluded, not zero.")
    lifetime = decimal(constraints.get("approval_max_age_seconds"))
    check("expiry_tolerance", constraints.get("approval_max_age_seconds") in (None, "") or lifetime is not None and lifetime > 0,
          "Approval is single-use; any configured lifetime must be positive")
    if "history" in required["mandatory"]:
        saved = history.get("coverage", {}).get(symbol, {})
        bars = artifact(saved.get("artifact", {}))
        from .history_coverage import current, latest_calendar
        coverage = current(saved, bars, artifact, calendar_meta=latest_calendar(history, artifact))
        valid_history = bool(bars and bars.get("symbol") == symbol and coverage.get("sufficient") is True
                             and bars.get("bars") and not bars.get("missing_fields"))
        if saved.get("artifact"):
            references["history"] = saved["artifact"]
        check("market_history", valid_history and age(saved.get("captured_at"), constraints.get("evidence_max_age_seconds")),
              "Declared history must be complete, dated, hash-matching and satisfy any configured age limit", saved.get("artifact"))
    for scope in sorted(SUPPLEMENTARY):
        if scope not in required["required_supplementary"]:
            continue
        saved = evidence.get("observations", {}).get(symbol, {}).get(scope, {})
        data = artifact(saved.get("artifact", {}))
        valid = bool(data and data.get("symbol") == symbol and data.get("scope") == scope
                     and data.get("complete") is True and data.get("status") in {"available", "missing"}
                     and (not saved.get("last_usable_artifact") or data.get("status") == "missing"
                          and scope in {"news", "corporate_actions"}))
        if scope in {"fundamentals", "classification"}:
            valid = valid and bool(data.get("records"))
        if saved.get("artifact"):
            references[scope] = saved["artifact"]
        check(scope, valid and age(saved.get("captured_at"), constraints.get("evidence_max_age_seconds")),
              "Required dated " + scope + " coverage is missing, incomplete, stale or not hash-matching", saved.get("artifact"))
    from .policy_evaluation import evaluate as evaluate_policy
    own_commands = {identity for identity, item in commands.get("commands", {}).items()
                    if item.get("proposal_id") == proposal["id"] and item.get("proposal_revision") == proposal["revision"]}
    scoped = {**commands, "commands": {identity: item for identity, item in commands.get("commands", {}).items() if identity not in own_commands}}
    risk = evaluate_policy(terms, policy, runtime, scoped, history, evidence, constraints, artifact)
    checks.extend(risk["checks"])
    references.update(risk["source_references"])
    relevant_symbols = [symbol]
    version = account_version(runtime)
    binding = {"proposal_revision": proposal["revision"], "terms_sha256": proposal["terms_sha256"],
               "policy_revision": policy["revision"], "account_version": version, "market_symbols": relevant_symbols,
               "source_references": references, "constraints": constraints,
               "evidence_requirements": required}
    ready = all(item["passed"] for item in checks)
    return {"method": "server-exact-terms-review-v2", "evaluated_at": datetime.now(UTC).isoformat(), "passed": ready,
            "evidence_requirements": required,
            "evidence_ready": ready, "checks": checks, "blockers": [c["reason"] for c in checks if not c["passed"]],
            "account_version": version, "policy_revision": policy["revision"], "policy_scenarios": risk, "bindings": binding, "binding_sha256": digest(binding)}
