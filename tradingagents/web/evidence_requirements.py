"""Versioned evidence dependencies of exact human decisions and enabled policies."""

VERSION = "decision-policy-evidence-v1"
SUPPLEMENTARY = {"news", "corporate_actions", "earnings", "fundamentals", "classification"}
DECISION_SCOPES = SUPPLEMENTARY | {"history"}


def research_dependencies(result, key):
    return {"version": VERSION, "report_keys": [key], "scopes": [], "unresolved": [],
            "basis": "Immutable saved report provenance; current trade inputs follow explicit decision and enabled policy dependencies"}


def requirements(terms, policy):
    declared = terms.get("decision_evidence_scopes", [])
    unresolved = []
    if not isinstance(declared, list) or any(not isinstance(scope, str) or scope not in DECISION_SCOPES for scope in declared):
        unresolved.append("Decision evidence scopes are unsupported or malformed")
        declared = []
    if terms.get("evidence_requirements_version") != VERSION:
        unresolved.append("Save an exact proposal revision using the current evidence-requirement version")
    context = None
    if terms.get("asset_class") == "us_option":
        from .linked_orders import option_contract
        try:
            contract = option_contract(terms.get("option_contract"))
            context = {"contract_symbol": contract["symbol"], "underlying_symbol": contract["underlying_symbol"],
                "supplementary_evidence_subject": "Underlying analysis, not an option recommendation", "premium_history_subject": contract["symbol"]}
        except ValueError as exc:
            unresolved.append(str(exc))
        if "history" in declared:
            unresolved.append("Declared option premium history has no configured adapter; underlying equity history is not substituted")
    reasons = {scope: ["Explicit dependency of the human decision"] for scope in declared}
    policy_dependencies = {}
    if policy.get("rules", {}).get("max_sector_pct", {}).get("state") == "enabled":
        reasons.setdefault("classification", []).append("Enabled sector exposure policy")
        policy_dependencies["max_sector_pct"] = {"scope": "classification", "instruments": "All current/pending/proposed exposures used by the policy calculation"}
    if policy.get("rules", {}).get("max_correlation_pct", {}).get("state") == "enabled":
        policy_dependencies["max_correlation_pct"] = {"scope": "history", "instruments": "All positive resulting positions used by the paired-return calculation"}
    unresolved.extend("No configured evidence adapter supplies required scope: " + scope for scope in reasons if scope not in DECISION_SCOPES)
    return {"version": VERSION, "instrument_context": context,
            "mandatory": ["account", "quote"] + (["option_contract"] if context else []) + (["history"] if "history" in declared else []),
            "required_supplementary": {scope: reasons[scope] for scope in sorted(reasons) if scope in SUPPLEMENTARY},
            "optional_supplementary": sorted(SUPPLEMENTARY - set(reasons)),
            "policy_dependencies": policy_dependencies, "unresolved": unresolved,
            "basis": "Exact decision declarations and enabled policy dependencies; linked reports retain immutable provenance without requiring their adapters to run again"}
