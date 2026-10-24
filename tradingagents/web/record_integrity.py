"""Structural contracts used before a restored generation can become active."""

import hashlib
import math
import re
from datetime import date, datetime
from pathlib import PurePosixPath
from uuid import UUID

from .investor import RULES, decimal, policy, broker_action_order, digest, native_quantity_offset, native_balance_binding, replacement_funding_route
from .linked_orders import exit_plan, native_type, broker_payload, fractional_terms, trailing_terms, is_package, package_terms, package_observation, validate_package_valuation


def retained_native_balance(evaluation, terms):
    material = (evaluation.get("bindings") or {}).get("native_balance_projection")
    if material is None:
        if terms.get("execution_profile") == "bounded_risk_spread_v1" and evaluation.get("passed") is True:
            raise ValueError("Restored passing bounded review lacks its native balance basis")
        return None
    if terms.get("execution_profile") != "bounded_risk_spread_v1":
        raise ValueError("Restored native margin projection is outside its selected profile")
    profile = next((check.get("details") for check in evaluation.get("checks", []) if check.get("name") == "execution_profile"), None)
    projection = (profile or {}).get("balance_projection")
    if not isinstance(projection, dict) or native_balance_binding({"profile_transition": profile}) != material:
        raise ValueError("Restored native balance differs from its exact profile projection")
    source, derived = projection.get("source_fields") or {}, projection.get("derived") or {}
    keys = ("cash", "equity", "initial_margin", "maintenance_margin", "options_buying_power")
    if (projection.get("version") != "alpaca-paper-equity-initial-v1" or projection.get("currency") != "USD"
            or projection.get("calculate_account_state") is not False
            or projection.get("authority") != "diagnostic_equity_less_initial_requirement_not_spendable_cash"
            or any(not isinstance(source.get(key), str) or decimal(source[key]) is None for key in keys)
            or any(not isinstance(derived.get(key), str) or decimal(derived[key]) is None for key in ("total", "locked", "free"))):
        raise ValueError("Invalid restored native equity/initial-margin projection")
    if (decimal(derived["total"]) != decimal(source["equity"]) or decimal(derived["locked"]) != decimal(source["initial_margin"])
            or decimal(derived["free"]) != decimal(source["equity"]) - decimal(source["initial_margin"])
            or projection.get("reported_margin") != {"initial": source["initial_margin"], "maintenance": source["maintenance_margin"], "currency": "USD"}):
        raise ValueError("Restored native balance projection changed its declared source basis")
    receipt = projection.get("source_receipt") or {}
    if receipt.get("path") != "/v2/account" or not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("raw_sha256", ""))):
        raise ValueError("Restored native balance lacks its actual account receipt identity")
    stamp = datetime.fromisoformat(str(receipt.get("received_at", "")).replace("Z", "+00:00"))
    if stamp.utcoffset() is None or profile.get("account_id") != terms.get("account_id"):
        raise ValueError("Restored native balance account or observation time differs")
    return material


def retained_package_valuation(evaluation, terms):
    bindings = evaluation.get("bindings") or {}
    if not is_package(terms):
        return None
    if "native_package_valuation" not in bindings and terms.get("execution_profile") != "bounded_risk_spread_v1":
        return None
    material = bindings.get("native_package_valuation")
    if material is None:
        if evaluation.get("passed") is True:
            raise ValueError("Restored passing package review lacks native valuation")
        return None
    packet = (evaluation.get("policy_scenarios") or {}).get("native_package_valuation")
    if validate_package_valuation(packet, terms) != material:
        raise ValueError("Restored native package valuation differs from its review binding")
    return packet


def retained_replacement_funding(evaluation, terms):
    declaration = replacement_funding_route(terms)
    if declaration is None:
        return None
    material = (evaluation.get("bindings") or {}).get("broker_reservation_validation")
    expected = set(declaration) | {"observed_options_buying_power", "local_net_obligation", "local_unsubmitted_option_reservations", "route_eligible"}
    if (not isinstance(material, dict) or set(material) != expected
            or any(material.get(key) != value for key, value in declaration.items())
            or material != (evaluation.get("policy_scenarios") or {}).get("broker_reservation_validation")
            or type(material.get("route_eligible")) is not bool):
        raise ValueError("Restored replacement broker validation differs from its explicit routing basis")
    for key in ("observed_options_buying_power", "local_net_obligation", "local_unsubmitted_option_reservations"):
        value = material[key]
        if value is not None and (not isinstance(value, str) or decimal(value) is None
                or key != "observed_options_buying_power" and decimal(value) < 0):
            raise ValueError("Invalid restored replacement local funding fact")
        if material["route_eligible"] and (value is None or decimal(value) < 0):
            raise ValueError("Restored replacement routing lacks required local funding facts")
    checks = evaluation.get("checks") or []
    broker = [check for check in checks if check.get("name") == "broker_incremental_buying_power"]
    if (len(broker) != 1 or broker[0].get("passed") is not None or broker[0].get("required") is not False
            or broker[0].get("state") != "not_observed" or broker[0].get("authority") != "broker"
            or "reservation_credit" not in broker[0] or broker[0]["reservation_credit"] is not None or broker[0].get("details") != material):
        raise ValueError("Restored broker-only incremental validation is not an explicit neutral check")
    local = [check for check in checks if check is not broker[0]]
    ready = bool(local) and all(check.get("passed") is True for check in local)
    if (material["route_eligible"] != ready or evaluation.get("route_eligible") is not ready or evaluation.get("passed") is not ready
            or evaluation.get("approval_scope") != "Required local checks only; broker incremental reservation remains unobserved"):
        raise ValueError("Restored replacement routing differs from required local readiness")
    return material


def retained_drawing_rule(rule):
    from .attention import validate_drawing_binding

    for atom in rule.get("atoms", [rule]):
        if atom.get("kind") == "drawing":
            drawing = validate_drawing_binding(atom.get("parameters") or {})
            if ((rule.get("target") or {}).get("mode", "symbol") != "symbol"
                    or drawing["scope"]["symbol"] != rule.get("symbol")):
                raise ValueError("Restored drawing alert differs from its fixed symbol scope")


def fields(value, required, label):
    if not isinstance(value, dict) or any(key not in value or type(value[key]) is not kind for key, kind in required.items()):
        raise ValueError("Invalid restored " + label)


def identity(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("Invalid restored record identity")


def reconstruction_receipt(value):
    fields(value, {"path": str, "sha256": str, "bytes": int, "format": str}, "native reconstruction receipt")
    match = re.fullmatch(r"reports/native-reconstruction/execution-([0-9a-f-]+)\.json", value["path"])
    if not match or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) or value["bytes"] <= 0 or value["format"] != "json":
        raise ValueError("Invalid restored native reconstruction artifact")
    identity(match[1])


def native_reconstructions(commands):
    records = commands.get("native_reconstructions", {})
    if not isinstance(records, dict):
        raise ValueError("Invalid restored native reconstruction metadata")
    for instrument_id, record in records.items():
        fields(record, {"version": str, "account_id": str, "endpoint": str, "native_epoch": str, "instrument_id": str,
            "state": str, "receipt": dict, "represented_quantity": str, "actual_execution_ids_applied": list,
            "native_order_ids": list, "native_trade_ids": list, "basis": dict, "history": list}, "native reconstruction")
        identity(record["account_id"])
        identity(record["native_epoch"])
        if (record["version"] != "native-position-reconstruction-v1" or not instrument_id or record["instrument_id"] != instrument_id
                or record["endpoint"] not in {"https://paper-api.alpaca.markets", "https://api.alpaca.markets"}
                or record["state"] not in {"prepared", "confirmed", "reconstruction_required"}
                or decimal(record["represented_quantity"]) is None):
            raise ValueError("Restored native reconstruction identity/state differs")
        basis = record["basis"]
        price = decimal(basis.get("price"))
        if (basis.get("kind") not in {"broker_position_basis", "modeled_reduction_basis"}
                or price is None or price <= 0 or basis.get("actual_economics_verified") is not False):
            raise ValueError("Restored native representation requires a positive, explicitly modeled basis")
        for name in ("actual_execution_ids_applied", "native_order_ids", "native_trade_ids"):
            values = record[name]
            if any(not isinstance(value, str) or not value for value in values) or len(set(values)) != len(values):
                raise ValueError("Invalid restored execution identity list")
        if set(record["actual_execution_ids_applied"]) & set(record["native_trade_ids"]):
            raise ValueError("Modeled native trade identities cannot assert actual broker executions")
        for receipt in [record["receipt"], *record["history"]]:
            reconstruction_receipt(receipt)
    for command in commands["commands"].values():
        parent = command.get("reconstruction_parent")
        if parent is None:
            continue
        fields(parent, {"receipt": dict, "account_id": str, "native_epoch": str, "instrument_id": str}, "causal reconstruction parent")
        identity(parent["native_epoch"])
        reconstruction_receipt(parent["receipt"])
        record = records.get(parent["instrument_id"], {})
        if (parent["account_id"] != command.get("account_id") or parent["instrument_id"] != command.get("instrument_id")
                or parent["receipt"] not in [record.get("receipt"), *record.get("history", [])]):
            raise ValueError("Restored causal parent differs from its command or retained baseline")


def option_instructions(commands):
    from .admission import instant
    from .linked_orders import option_contract
    rows = commands.get("option_instructions", {})
    if not isinstance(rows, dict):
        raise ValueError("Invalid restored option instructions")
    for key, row in rows.items():
        fields(row, {"id": str, "kind": str, "symbol": str, "account_id": str, "endpoint": str, "mode": str,
            "connection_session": str, "native_epoch": str, "intent": str, "constraints": dict, "created_at": str,
            "actor": str, "reason": str, "state": str, "timeline": list}, "option instruction")
        identity(key)
        identity(row["account_id"])
        identity(row["native_epoch"])
        instant(row["created_at"])
        connection_context({name: row[name] for name in ("endpoint", "mode", "account_id", "connection_session")}, row["account_id"])
        if (row["id"] != key or row["kind"] not in {"exercise", "do_not_exercise"} or row["intent"] != "all_available"
                or not re.fullmatch(r"[A-Z]{1,6}\d{6}[CP]\d{8}", row["symbol"]) or not row["actor"]
                or row["state"] not in {"prepared", "approved", "transport_intent", "transport_unknown", "submitted", "rejected", "not_sent"}):
            raise ValueError("Unsupported restored full-position option intent")
        if any(decimal(row["constraints"].get(name)) is None or decimal(row["constraints"][name]) <= 0
               for name in ("account_max_age_seconds", "approval_max_age_seconds")):
            raise ValueError("Restored instruction lacks explicit positive observation/approval bounds")
        review, approval, attempt = row.get("review"), row.get("approval"), row.get("attempt")
        if review is not None:
            fields(review, {"facts": dict, "binding_sha256": str, "history_sha256": str, "blockers": list}, "instruction review")
            facts = review["facts"]
            if (any(facts.get(name) != row[name] for name in ("kind", "symbol", "account_id", "endpoint", "mode", "connection_session", "native_epoch", "intent"))
                    or option_contract(facts.get("option_contract"))["symbol"] != row["symbol"]
                    or any(not re.fullmatch(r"[0-9a-f]{64}", review[name]) for name in ("binding_sha256", "history_sha256"))
                    or not isinstance(facts.get("history"), list)):
                raise ValueError("Restored instruction review differs from its identity/contract/history")
            instant(facts["observed_at"])
            for name in ("observed_quantity", "broker_available_quantity", "local_sell_commitment", "review_available_quantity"):
                if decimal(facts.get(name)) is None:
                    raise ValueError("Restored instruction position evidence is unavailable")
        if approval is not None:
            fields(approval, {"actor": str, "at": str, "expires_at": str, "binding_sha256": str, "history_sha256": str, "reviewed_unknowns": bool}, "instruction approval")
            if not review or approval["binding_sha256"] != review["binding_sha256"] or approval["history_sha256"] != review["history_sha256"]:
                raise ValueError("Restored instruction approval differs from its exact review")
            instant(approval["at"])
            instant(approval["expires_at"])
        if row["state"] == "approved" and (not approval or not review or review["blockers"]):
            raise ValueError("Restored instruction has no exact unblocked approval")
        if attempt is not None:
            fields(attempt, {"id": str, "state": str}, "instruction transport attempt")
            identity(attempt["id"])
            if attempt["state"] not in {"in_flight", "transport_unknown", "submitted", "rejected", "not_sent"}:
                raise ValueError("Invalid instruction transport boundary")
            expected = {"transport_intent": "in_flight", "transport_unknown": "transport_unknown", "submitted": "submitted", "rejected": "rejected", "not_sent": "not_sent"}.get(row["state"])
            if expected != attempt["state"] or row["state"] in {"submitted", "rejected"} and not attempt.get("receipt"):
                raise ValueError("Instruction outcome differs from its retained response boundary")
            for name in ("attempted_at", "result_at"):
                if attempt.get(name):
                    instant(attempt[name])
            if attempt.get("receipt"):
                reference = attempt["receipt"]
                fields(reference, {"path": str, "sha256": str, "bytes": int, "format": str}, "instruction response receipt")
                path = PurePosixPath(reference["path"])
                if path.is_absolute() or ".." in path.parts or "\\" in str(path) or not path.parts or path.parts[0] != "reports" or not re.fullmatch(r"[0-9a-f]{64}", reference["sha256"]):
                    raise ValueError("Invalid retained instruction response artifact")
        elif row["state"] in {"transport_intent", "submitted", "rejected"} or row["state"] == "transport_unknown" and not row.get("restore_uncertainty"):
            raise ValueError("Restored possible-send state lacks its transport or archive-uncertainty evidence")
        for name in ("interlock_release", "restore_uncertainty"):
            if row.get(name):
                event = row[name]
                fields(event, {"at": str, "reason": str}, "instruction uncertainty audit")
                instant(event["at"])
                if not event["reason"].strip() or name == "interlock_release" and (row["state"] != "transport_unknown" or not event.get("actor")):
                    raise ValueError("Uncertainty release must preserve the original unknown outcome and actor/reason")
        for event in row["timeline"]:
            fields(event, {"at": str}, "instruction history event")
            instant(event["at"])


def indicator_evidence(evidence):
    if evidence["rule"]["kind"] != "indicator":
        return
    from .attention import validate_atom
    validate_atom({key: evidence["rule"][key] for key in ("kind", "scope", "parameters")})
    evaluation, source = evidence["evaluation"], evidence["source"]
    facts = evaluation.get("facts", {})
    if (evaluation.get("indicator_source") != source or source.get("definition_sha256") != digest(facts.get("definition"))
            or source.get("units") != facts.get("units")):
        raise ValueError("Captured indicator formula or input binding differs")
    point = facts.get("point", {})
    if point.get("numerical_available") is True and decimal(point.get("raw")) is None:
        raise ValueError("Captured numerical indicator lacks its precise finite value")
    if evaluation["state"] in {"clear", "triggered"} and not point.get("alert_eligible"):
        raise ValueError("Captured indicator comparison lacks eligible inputs")


def connection_context(value, account_id):
    if value is None:
        return  # Legacy evidence has no inferred mode/session binding.
    fields(value, {"endpoint": str, "mode": str, "account_id": str, "connection_session": str}, "connection context")
    if (value["account_id"] != account_id or value["connection_session"] in ("", "None")
            or {"paper": "https://paper-api.alpaca.markets", "live": "https://api.alpaca.markets"}.get(value["mode"]) != value["endpoint"]):
        raise ValueError("Restored connection context differs from account or official trading mode/origin")


def conditional_authority(terms, commands):
    binding = (terms.get("replacement") or {}).get("contingent_group")
    if binding is None:
        return
    fields(binding, {"parent_order_id": str, "account_id": str, "members": list, "entry_command_id": str,
                     "entry_approval_id": str, "entry_terms_sha256": str}, "conditional group")
    parent = commands.get("commands", {}).get(binding["entry_command_id"], {})
    approval = commands.get("approvals", {}).get(binding["entry_approval_id"], {})
    if (terms.get("side") != "SELL" or terms.get("exit_plan") or parent.get("side") != "BUY"
            or parent.get("terms_sha256") != binding["entry_terms_sha256"] or not parent.get("terms", {}).get("exit_plan")
            or digest(parent["terms"]) != binding["entry_terms_sha256"]
            or approval.get("terms_sha256") != binding["entry_terms_sha256"] or parent.get("approval_id") != binding["entry_approval_id"]
            or binding["account_id"] != terms.get("account_id") or parent.get("account_id") != binding["account_id"]
            or binding["parent_order_id"] not in parent.get("broker_order_ids", []) or len(binding["members"]) != 3):
        raise ValueError("Restored held amendment lacks its original exact purchase authority")
    for member in binding["members"]:
        fields(member, {"order_id": str, "version": str, "native_client_order_id": str, "native_order_list_id": str,
                        "role": str, "qty": str, "filled_qty": str, "status": str, "type": str, "time_in_force": str,
                        "linked_order_ids": list, "contingency_type": str, "reduce_only": bool, "emulation_trigger": str}, "conditional member")
        if (decimal(member["qty"]) != decimal(parent["terms"]["quantity"])
                or member["role"] != "entry" and (member["status"] != "held" or decimal(member["filled_qty"]) != 0)):
            raise ValueError("Restored held amendment quantity or activation differs")
    if ({member["role"] for member in binding["members"]} != {"entry", "take_profit", "stop_loss"}
            or len({member["order_id"] for member in binding["members"]}) != 3
            or len({member["native_order_list_id"] for member in binding["members"]}) != 1
            or terms["replacement"].get("order_id") not in {member["order_id"] for member in binding["members"] if member["role"] != "entry"}):
        raise ValueError("Restored held amendment has inconsistent bracket membership")
    entry = next(member for member in binding["members"] if member["role"] == "entry")
    exits = [member["native_client_order_id"] for member in binding["members"] if member["role"] != "entry"]
    for member in binding["members"]:
        is_entry = member["role"] == "entry"
        links = exits if is_entry else [identity for identity in exits if identity != member["native_client_order_id"]]
        if (member.get("parent_order_id") != (None if is_entry else entry["native_client_order_id"])
                or member["reduce_only"] is not (not is_entry) or member["contingency_type"] != ("OTO" if is_entry else "OCO")
                or member["emulation_trigger"] != "NO_TRIGGER"
                or not all(isinstance(identity, str) for identity in member["linked_order_ids"])
                or sorted(member["linked_order_ids"]) != sorted(links)):
            raise ValueError("Restored held amendment native sibling or contingency relationship differs")
    # A restored snapshot is evidence only. Current group validation is mandatory before replacement.


def validate(values, resolve_artifact=None):
    for run in values.get("journal", {}).get("runs", []):
        if "continuation" not in run:
            continue
        fields(run, {"id": str, "config": dict, "results": list}, "checkpointed research run")
        saved = run["continuation"]
        fields(saved, {"version": int, "revision": int, "source_signature": str, "market": dict, "attempts": list}, "research continuation")
        if saved["version"] != 1 or saved["revision"] < 0 or not re.fullmatch(r"[0-9a-f]{64}", saved["source_signature"]) or not saved["attempts"]:
            raise ValueError("Unsupported restored research continuation")
        parent = None
        for attempt in saved["attempts"]:
            fields(attempt, {"id": str, "started_at": str, "status": str}, "continuation attempt")
            identity(attempt["id"])
            datetime.fromisoformat(attempt["started_at"])
            if attempt.get("parent_id") != parent:
                raise ValueError("Restored continuation attempt lineage differs")
            parent = attempt["id"]
        for result in run["results"]:
            if "continuation" not in result:
                continue
            checkpoint = result["continuation"]
            fields(checkpoint, {"thread_id": str, "effects": dict, "social_budget": dict}, "research checkpoint")
            if checkpoint["thread_id"] != f"{run['id']}:{result['symbol']}":
                raise ValueError("Restored research checkpoint identity differs")
            budget = checkpoint["social_budget"]
            if (type(budget.get("remaining")) is not int or not 0 <= budget["remaining"] <= run["config"].get("social_screen_max_posts", 100)
                    or budget.get("max_seconds") != run["config"].get("social_screen_timeout_seconds", 600)
                    or "expires_at" in budget and (type(budget["expires_at"]) not in (int, float) or not math.isfinite(budget["expires_at"]))):
                raise ValueError("Restored social screening budget differs")
            if "expires_at" in budget:
                try:
                    datetime.fromtimestamp(budget["expires_at"])
                except (ValueError, OverflowError, OSError) as exc:
                    raise ValueError("Invalid restored social expiry") from exc
            for key, effect in checkpoint["effects"].items():
                fields(effect, {"id": str, "domain": str, "command": str, "tool_call_id": str,
                                "arguments_sha256": str, "arguments": dict, "stateful": bool, "outcome": str, "history": list}, "research effect")
                identity(effect["id"])
                expected = hashlib.sha256(f"{effect['domain']}:{effect['command']}:{effect['tool_call_id']}".encode()).hexdigest()
                if (key != expected or not re.fullmatch(r"[0-9a-f]{64}", effect["arguments_sha256"])
                        or effect["outcome"] not in {"intent", "confirmed", "unknown", "error"}):
                    raise ValueError("Invalid restored research effect identity or outcome")
                if effect["outcome"] == "confirmed":
                    fields(effect, {"result": dict}, "confirmed research effect")
                for reference in (effect["arguments"], *([effect["result"]] if effect["outcome"] == "confirmed" else [])):
                    fields(reference, {"path": str, "sha256": str, "bytes": int, "format": str}, "research effect artifact")
                    if (reference["bytes"] < 0 or reference["format"] != "json"
                            or not re.fullmatch(r"[0-9a-f]{64}", reference["sha256"])
                            or not reference["path"].startswith(f"reports/{run['id']}/")
                            or ".." in reference["path"].replace("\\", "/").split("/")):
                        raise ValueError("Invalid restored research effect artifact reference")
    workspace = values.get("workspace")
    if workspace:
        from .workspace import validate_chart_definitions, validate_drawings
        validate_drawings(workspace)
        validate_chart_definitions(workspace)
        fields(workspace, {"watchlists": list, "preferences": dict, "notes": dict}, "workspace")
        for symbol, note in workspace["notes"].items():
            fields(note, {"symbol": str, "text": str, "updated_at": str}, "symbol note")
            if symbol != note["symbol"] or len(note["text"]) > 20000:
                raise ValueError("Restored note identity or size differs")
    investor = values.get("investor")
    if investor:
        fields(investor, {"policy": dict, "policy_history": list, "proposals": list}, "investor records")
        fields(investor["policy"], {"revision": int, "rules": dict}, "policy")
        if set(investor["policy"]["rules"]) - set(RULES):
            raise ValueError("Unsupported restored policy rules")
        restored_rules = {key: investor["policy"]["rules"].get(key, {"state": "unset"}) for key in RULES}
        policy({"rules": restored_rules, "reason": "Validate restored policy units and parameters"}, {"revision": 0})
        proposals = set()
        for proposal in investor["proposals"]:
            fields(proposal, {"id": str, "revision": int, "status": str, "terms": dict, "history": list,
                              "impact": dict, "terms_sha256": str, "policy_revision": int, "updated_at": str, "created_at": str}, "proposal")
            identity(proposal["id"])
            if proposal["id"] in proposals or proposal["revision"] < 1:
                raise ValueError("Duplicate restored proposal or invalid revision")
            proposals.add(proposal["id"])
            terms = proposal["terms"]
            replacement_funding_route(terms)
            fields(terms, {"symbol": str, "instrument_id": str, "side": str, "quantity": str, "order_type": str, "rationale": str}, "proposal terms")
            package = is_package(terms)
            if package:
                package_terms(terms)
                broker_payload(terms, "validate-restored-package")
                retained_package_valuation(proposal.get("risk_evaluation") or {}, terms)
                retained_native_balance(proposal.get("risk_evaluation") or {}, terms)
                if proposal.get("risk_evaluation"):
                    retained_replacement_funding(proposal["risk_evaluation"], terms)
            quantity = decimal(terms["quantity"]) if package else fractional_terms(terms)
            trailing_terms(terms)
            if quantity % 1:
                bound = terms.get("fractional_asset", {})
                fields(bound, {"asset": dict, "observed_at": str, "source": str}, "fractional asset evidence")
                asset = bound["asset"]
                if (asset.get("fractionable") is not True or asset.get("tradable") is not True
                        or terms.get("session") == "extended" and asset.get("fractional_eh_enabled") is not True
                        or asset.get("symbol") != terms["symbol"] or asset.get("class") != "us_equity"
                        or asset.get("status") != "active" or not asset.get("id")
                        or not bound["observed_at"] or not bound["source"]):
                    raise ValueError("Restored fractional proposal lacks eligible asset evidence")
            if (terms["side"] not in {"BUY", "SELL"}
                    or terms["order_type"] not in {"MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT", "TRAILING_STOP_MARKET"}
                    or terms.get("time_in_force") not in {"DAY", "GTC"}
                    or terms.get("session") not in {"regular", "extended"} or not isinstance(proposal["impact"].get("conditions"), list)):
                raise ValueError("Unsupported restored proposal terms or review")
            exit_plan(terms.get("exit_plan"), terms["side"])
            if terms.get("exit_plan"):
                broker_payload(terms, "validate-restored-group")
            for key in ("limit_price", "stop_price"):
                if not package and terms.get(key) is not None and (not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", str(terms[key])) or decimal(terms[key]) <= 0):
                    raise ValueError("Invalid restored USD order price")
            references = terms.get("price_references", [])
            if not isinstance(references, list) or len(references) > 5 or package and references:
                raise ValueError("Invalid restored chart price references")
            from .investor import copied_price_fields, price_reference
            destinations = set()
            for reference in references:
                price_reference(reference, terms)
                copied = copied_price_fields(reference, terms)
                normalized = reference.get("normalization") or {}
                actual = {field: terms.get("exit_plan", {}).get(field.split(".")[1]) if field.startswith("exit_plan.") else terms.get(field) for field in copied}
                increment = decimal(normalized.get("increment"))
                if increment is None or increment <= 0:
                    raise ValueError("Restored copied price increment is unavailable")
                if (copied & destinations or reference.get("fields") != actual
                        or any(normalized.get("value") != value or decimal(value) is None or decimal(value) % increment
                               for value in actual.values())
                        or not re.fullmatch(r"[0-9a-f]{64}", str(normalized.get("instrument_metadata_sha256", "")))):
                    raise ValueError("Restored copied price differs from its retained normalization")
                destinations.update(copied)
            if terms["order_type"] in {"STOP_MARKET", "STOP_LIMIT"} and terms.get("stop_price") is None:
                raise ValueError("Restored stop amendment has no trigger")
            if terms["order_type"] in {"LIMIT", "STOP_LIMIT"} and terms.get("limit_price") is None:
                raise ValueError("Restored limit order has no limit price")
            if (terms["order_type"] not in {"LIMIT", "STOP_LIMIT"} and terms.get("limit_price") is not None
                    or terms["order_type"] not in {"STOP_MARKET", "STOP_LIMIT"} and terms.get("stop_price") is not None
                    or terms.get("exit_plan") and terms.get("replacement")):
                raise ValueError("Restored price or exit fields do not match the supported order type")
            if terms["order_type"] == "STOP_LIMIT" and ((terms["side"] == "BUY" and decimal(terms["limit_price"]) < decimal(terms["stop_price"]))
                    or (terms["side"] == "SELL" and decimal(terms["limit_price"]) > decimal(terms["stop_price"]))):
                raise ValueError("Restored stop limit is on the wrong side of its trigger")
        for basket in investor.get("baskets", []):
            fields(basket, {"id": str, "revision": int, "status": str, "preview": dict, "linked_proposal_ids": list, "history": list, "updated_at": str}, "basket")
            identity(basket["id"])
            fields(basket["preview"], {"targets": list, "reason": str, "legs": list, "complete_scenario": dict, "partial_scenario": dict}, "basket preview")
            if set(basket["linked_proposal_ids"]) - proposals:
                raise ValueError("Restored basket refers to a missing proposal")
    reporting = values.get("reporting")
    if reporting:
        fields(reporting, {"entries": dict, "collections": list, "settings_history": list}, "decision journal")
        from .decision_journal import validate_experiment_record
        from .evaluation import validate_strategy

        definitions, history = reporting.get("strategy_definitions", {}), reporting.get("strategy_history", [])
        if not isinstance(definitions, dict) or not isinstance(history, list) or not isinstance(reporting.get("simulations", {}), dict):
            raise ValueError("Invalid reusable strategy or experiment index")
        latest = {}
        for definition in history:
            canonical = validate_strategy(definition)
            old = latest.get(canonical["id"])
            if canonical != definition or canonical["revision"] != (old["revision"] + 1 if old else 1):
                raise ValueError("Strategy revisions must retain complete immutable canonical history")
            latest[canonical["id"]] = canonical
        if latest != definitions:
            raise ValueError("Current strategy definitions differ from retained revision history")
        experiments = reporting.get("simulations", {})
        for identity_value, item in experiments.items():
            if item.get("kind") in {"experiment", "experiment_comparison"}:
                if item["id"] != identity_value:
                    raise ValueError("Retained experiment index identity differs")
                validate_experiment_record(item, resolve_artifact)
                if item.get("parent_id"):
                    parent = experiments.get(item["parent_id"])
                    if not parent or parent.get("kind") != "experiment" or parent["id"] == item["id"] or parent["spec_sha256"] != item.get("parent_spec_sha256"):
                        raise ValueError("Experiment branch requires its distinct retained parent")
                    trail, ancestor = {item["id"]}, parent
                    while ancestor:
                        if ancestor["id"] in trail:
                            raise ValueError("Experiment branch lineage cannot contain a cycle")
                        trail.add(ancestor["id"])
                        ancestor = experiments.get(ancestor.get("parent_id"))
                if item["kind"] == "experiment":
                    versions = [row for row in history if row["id"] == item["strategy_id"] and row["revision"] == item["strategy_revision"]]
                    if len(versions) != 1 or digest(versions[0]) != item["strategy_sha256"]:
                        raise ValueError("Experiment must bind one exact retained reusable strategy revision")
                else:
                    for member in item["members"]:
                        source = experiments.get(member["experiment_id"])
                        if not source or any(source.get(key) != member[key] for key in ("spec_sha256", "preview_artifact", "result_artifact")):
                            raise ValueError("Comparison must retain exact experiment source identities")
        if not isinstance(reporting.get("technical_method_acceptances", {}), dict):
            raise ValueError("Invalid technical method acceptance records")
        captures = reporting.get("native_position_captures", [])
        if not isinstance(captures, list):
            raise ValueError("Invalid restored native position capture index")
        seen = set()
        for capture in captures:
            fields(capture, {"id": str, "artifact": dict, "captured_at": str, "native_epoch": str, "account_context": dict}, "native position capture")
            identity(capture["id"])
            if capture["id"] in seen or not capture["native_epoch"] or capture["native_epoch"] == "None":
                raise ValueError("Duplicate capture identity or missing native epoch")
            seen.add(capture["id"])
            stamp = datetime.fromisoformat(capture["captured_at"].replace("Z", "+00:00"))
            if stamp.utcoffset() is None:
                raise ValueError("Native position capture time requires a timezone")
            reference = capture["artifact"]
            fields(reference, {"path": str, "sha256": str, "bytes": int, "format": str}, "native report artifact")
            path = PurePosixPath(reference["path"])
            if (path.is_absolute() or ".." in path.parts or "\\" in reference["path"] or not reference["path"].startswith("reports/" + capture["id"] + "/")
                    or path.suffix != ".json" or reference["format"] != "json" or reference["bytes"] <= 0
                    or not re.fullmatch(r"[0-9a-f]{64}", reference["sha256"])):
                raise ValueError("Invalid restored native report artifact reference")
            context = capture["account_context"]
            fields(context, {"account_id": str, "broker_account_id": str, "endpoint": str, "mode": str}, "native capture account context")
            if context["broker_account_id"] in ("", "None") or context["account_id"] != "ALPACA-" + context["broker_account_id"]:
                raise ValueError("Native capture account identity differs")
            connection_context({"endpoint": context["endpoint"], "mode": context["mode"], "account_id": context["broker_account_id"],
                                "connection_session": capture["native_epoch"]}, context["broker_account_id"])
        for collection in reporting["collections"]:
            fields(collection, {"id": str, "account_id": str, "artifact": dict, "requested_start": str, "requested_end": str, "collected_at": str}, "account history")
            identity(collection["id"])
            date.fromisoformat(collection["requested_start"])
            date.fromisoformat(collection["requested_end"])
    commands = values.get("commands")
    if commands:
        for proposal in (investor or {}).get("proposals", []):
            conditional_authority(proposal["terms"], commands)
        fields(commands, {"approvals": dict, "revocations": dict, "commands": dict, "account_versions": dict, "recovery_required": bool}, "command authority")
        native_reconstructions(commands)
        option_instructions(commands)
        if "new_orders_blocked" in commands and type(commands["new_orders_blocked"]) is not bool:
            raise ValueError("Invalid restored order-block control")
        if "authority_history_incomplete" in commands and type(commands["authority_history_incomplete"]) is not bool:
            raise ValueError("Invalid restored authority coverage")
        for authorization in commands.get("exercise_authorizations", {}).values():
            fields(authorization, {"id": str, "account_id": str, "commands": dict, "operations": list,
                                   "actor": str, "reason": str, "expires_at": str, "paper": bool}, "paper exercise")
            identity(authorization["id"])
            if authorization["paper"] is not True or set(authorization["operations"]) - {"submit", "cancel", "replace"}:
                raise ValueError("Unsupported restored exercise scope")
            from .admission import instant
            instant(authorization["expires_at"])
            if any(key not in commands["commands"] or commands["commands"][key]["terms_sha256"] != value
                   for key, value in authorization["commands"].items()):
                raise ValueError("Restored exercise command binding differs")
        for group in commands.get("basket_executions", {}).values():
            fields(group, {"id": str, "basket_id": str, "basket_revision": int, "command_ids": list,
                           "frozen_legs": list, "state": str, "history": list}, "basket execution")
            identity(group["id"])
            if not group["command_ids"] or any(key not in commands["commands"] for key in group["command_ids"]):
                raise ValueError("Restored basket has missing durable commands")
        for approval in commands["approvals"].values():
            fields(approval, {"id": str, "proposal_id": str, "proposal_revision": int, "policy_revision": int, "account_id": str, "account_version": str, "expires_at": str}, "approval reference")
            identity(approval["id"])
            retained_package_valuation(approval.get("evaluation") or {}, approval.get("terms") or {})
            retained_native_balance(approval.get("evaluation") or {}, approval.get("terms") or {})
            retained_replacement_funding(approval.get("evaluation") or {}, approval.get("terms") or {})
            connection_context(approval.get("connection_context"), approval["account_id"])
        for command in commands["commands"].values():
            conditional_authority(command.get("terms", {}), commands)
            external = command.get("origin") == "external_broker"
            required = {"id": str, "client_order_id": str, "terms": dict, "timeline": list,
                        "state": str, "broker_order_ids": list, "event_ids": list, "filled_quantity": str,
                        "remaining_quantity": str}
            if not external:
                required.update(approval_id=str, cash_commitment=str)
            fields(command, required, "command commitment")
            if (not external and is_package(command["terms"]) and command["terms"].get("execution_profile") == "bounded_risk_spread_v1"
                    or "package_valuation_binding_sha256" in command or "package_valuation_receipt" in command):
                approved = commands["approvals"].get(command.get("approval_id"), {})
                packet = retained_package_valuation(approved.get("evaluation") or {}, command["terms"])
                if (packet is None or command.get("package_valuation_binding_sha256") != packet["binding_sha256"]
                        or command.get("package_valuation_receipt") != packet["receipt"]):
                    raise ValueError("Restored command native valuation differs from its exact approved receipt")
            if (is_package(command["terms"]) and command["terms"].get("execution_profile") == "bounded_risk_spread_v1"
                    or "native_balance_projection" in command):
                approved = commands["approvals"].get(command.get("approval_id"), {})
                material = retained_native_balance(approved.get("evaluation") or {}, command["terms"])
                if material is None or command["native_balance_projection"] != material:
                    raise ValueError("Restored command native balance differs from its approved basis")
            route = replacement_funding_route(command["terms"])
            if route is not None or "replacement_funding_basis" in command or "broker_reservation_validation" in command:
                approved = commands["approvals"].get(command.get("approval_id"), {})
                material = retained_replacement_funding(approved.get("evaluation") or {}, approved.get("terms") or {})
                if (route is None or material is None or command.get("replacement_funding_basis") != route["version"]
                        or approved.get("terms", {}).get("replacement_funding_basis") != route["version"]
                        or command.get("broker_reservation_validation") != material
                        or any(material.get(key) != value for key, value in route.items())):
                    raise ValueError("Restored replacement command differs from its exact approved broker-owned validation basis")
            collateral = command.get("collateral_commitment")
            bounded = is_package(command["terms"]) and command["terms"].get("execution_profile") == "bounded_risk_spread_v1"
            if ((bounded or "collateral_commitment" in command)
                    and (not bounded or not isinstance(collateral, str) or decimal(collateral) is None or decimal(collateral) < 0)):
                raise ValueError("Restored bounded package collateral commitment is missing or invalid")
            identity(command["id"])
            connection_context(command.get("connection_context"), command.get("account_id"))
            if (command.get("connection_context") is not None and not external
                    and command["connection_context"] != commands["approvals"].get(command["approval_id"], {}).get("connection_context")):
                raise ValueError("Restored command connection context differs from its original approval")
            if is_package(command["terms"]):
                package_terms(command["terms"])
                broker_payload(command["terms"], "validate-restored-package-command")
            trailing_terms(command["terms"])
            from .linked_orders import session_terms
            session_terms(command["terms"])
            if external:
                fields(command, {"account_id": str, "instrument_id": str, "native_client_order_id": str,
                    "source_observation": dict, "terms_sha256": str}, "external order provenance")
                source = command["source_observation"]
                fields(source, {"order": dict, "order_version": str, "account_observed_at": str, "native_epoch": str}, "external source observation")
                order = broker_action_order({"status": "connected", "account": {"id": command["account_id"]},
                    "orders": [source["order"]]}, source["order"]["id"], source["order_version"])
                terms = command["terms"]
                if is_package(terms):
                    package_observation(source["order"], terms)
                if (command.get("approval_id") is not None or command.get("proposal_id") is not None
                        or command.get("proposal_revision") is not None or command.get("policy_revision") is not None
                        or command.get("submission_authority") is not False
                        or order["id"] not in command["broker_order_ids"] or command["client_order_id"] != order["client_order_id"]
                        or command["native_client_order_id"] != order["nautilus"]["client_order_id"]
                        or terms.get("account_id") != command["account_id"]
                        or not is_package(terms) and terms.get("symbol") != order["symbol"]
                        or command.get("symbol") != terms.get("symbol") or command.get("side") != terms.get("side")
                        or terms.get("instrument_id") != command["instrument_id"] or command["instrument_id"] != order["nautilus"]["instrument_id"]
                        or not is_package(terms) and terms.get("side") != order["side"].upper()
                        or decimal(terms.get("quantity")) != decimal(order["qty"])
                        or terms.get("order_type") != native_type(order.get("type", order.get("order_type")))
                        or terms.get("time_in_force") != order.get("time_in_force", "").upper()
                        or terms.get("session") != (order["package_terms"]["session"] if is_package(terms) else "extended" if order["extended_hours"] else "regular")
                        or decimal(terms.get("limit_price")) != decimal(order.get("limit_price"))
                        or decimal(terms.get("stop_price")) != (None if order.get("type") == "trailing_stop" else decimal(order.get("stop_price")))
                        or order.get("type") == "trailing_stop" and any(decimal(terms.get(key)) != decimal(order.get(key)) for key in ("trail_price", "trail_percent"))
                        or command["terms_sha256"] != digest(terms)):
                    raise ValueError("Restored external order identity or provenance differs")
                unknown_cash = command.get("cash_commitment") is None and command.get("price_cap") is None and terms["side"] == "BUY"
                if not unknown_cash and (not isinstance(command.get("cash_commitment"), str)
                        or decimal(command["cash_commitment"]) is None or decimal(command["cash_commitment"]) < 0):
                    raise ValueError("Invalid restored external principal commitment")
            elif command["approval_id"] not in commands["approvals"]:
                raise ValueError("Restored command approval is missing")
            if command.get("linked_exit"):
                parent = commands["commands"].get(command.get("linked_entry_command_id"))
                if (not parent or not parent.get("terms", {}).get("exit_plan") or command.get("side") != "SELL"
                        or command.get("account_id") != parent.get("account_id") or command.get("instrument_id") != parent.get("instrument_id")
                        or command.get("linked_role") not in {"take_profit", "stop_loss"}
                        or decimal(command["terms"].get("quantity")) is None
                        or not 0 < decimal(command["terms"]["quantity"]) <= decimal(parent["terms"]["quantity"])):
                    raise ValueError("Restored linked exit lacks its approved entry identity and quantity bound")
                if command.get("origin") == "linked_broker" and (command.get("submission_authority") is not False
                        or command["approval_id"] != parent["approval_id"] or not command.get("source_observation", {}).get("order")):
                    raise ValueError("Restored broker-assigned child provenance or authority differs")
                if command.get("origin") == "linked_broker":
                    source = command["source_observation"]["order"]
                    suffix = "-TP" if command["linked_role"] == "take_profit" else "-SL"
                    if (source.get("id") not in command["broker_order_ids"]
                            or source.get("group_parent_id") not in parent["broker_order_ids"] + parent.get("linked_root_order_ids", [])
                            or source.get("client_order_id") != command["client_order_id"]
                            or command.get("native_client_order_id") != parent["client_order_id"] + suffix
                            or command.get("terms_sha256") != digest(command["terms"])):
                        raise ValueError("Restored linked exit broker/native source binding differs")
            if command.get("linked_group_owner_id"):
                owner = commands["commands"].get(command["linked_group_owner_id"])
                if (not owner or owner.get("side") != "SELL" or not owner.get("terms", {}).get("exit_plan")
                        or command.get("account_id") != owner.get("account_id")
                        or command.get("instrument_id") != owner.get("instrument_id")
                        or not command["terms"].get("replacement")):
                    raise ValueError("Restored OCO root amendment lacks its original approved group identity")
            if command.get("broker_group_quantity") is not None:
                quantity = decimal(command["broker_group_quantity"])
                if (command.get("side") != "SELL" or not (command.get("linked_exit") or command.get("linked_group_owner_id") or command["terms"].get("exit_plan"))
                        or quantity is None or not 0 < quantity <= decimal(command["terms"]["quantity"]) or quantity % 1):
                    raise ValueError("Restored broker group quantity is outside its immutable approved quantity bound")
            quantity_proof = command.get("native_replacement_quantity_binding")
            if quantity_proof:
                proof_order = {"id": quantity_proof.get("broker_order_id"), "client_order_id": command["client_order_id"],
                    "type": command["terms"].get("order_type", "").lower(), "asset_class": command["terms"].get("asset_class"), "order_class": command["terms"].get("order_class"),
                    "replaces": quantity_proof.get("predecessor_order_id"),
                    "qty": command["terms"].get("quantity"), "filled_qty": quantity_proof.get("broker_filled_quantity"),
                    "native_replacement_quantity_binding": quantity_proof}
                if is_package(command["terms"]):
                    control = command.get("package_control") or {}
                    source = control.get("source_order") or command.get("source_observation", {}).get("order")
                    if not isinstance(source, dict):
                        raise ValueError("Restored package successor lacks its actual parent observation")
                    mapping = package_observation(source, command["terms"])["package_mapping"]
                    if (control.get("internal") is not True or control.get("economics") != "actual_leg_fills_only"
                            or control.get("source_mapping") != mapping or mapping["parent_id"] != proof_order["id"]):
                        raise ValueError("Restored package successor actual parent mapping differs")
                    proof_order["package_mapping"] = mapping
                offset = native_quantity_offset(proof_order)
                if (proof_order["id"] not in command["broker_order_ids"]
                        or decimal(command.get("native_quantity_offset")) != offset):
                    raise ValueError("Restored successor native quantity binding differs")
            elif decimal(command.get("native_quantity_offset", "0")) != 0:
                raise ValueError("Restored native quantity offset has no execution provenance")
            if any(decimal(command[k]) is None or decimal(command[k]) < 0 for k in
                   (("filled_quantity", "remaining_quantity") if external else ("filled_quantity", "remaining_quantity", "cash_commitment"))):
                raise ValueError("Restored command authority or commitments are incomplete")
    attention = values.get("attention")
    if attention:
        fields(attention, {"rules": dict, "reviews": dict, "rule_history": list}, "attention rules")
        from .attention import KINDS, SCOPES, validate_atom
        for entry in attention["rule_history"]:
            if isinstance(entry, dict) and isinstance(entry.get("rule"), dict):
                retained_drawing_rule(entry["rule"])
        for rule in attention["rules"].values():
            fields(rule, {"id": str, "name": str, "kind": str, "scope": str, "symbol": str, "parameters": dict, "active": bool, "revision": int}, "alert rule")
            retained_drawing_rule(rule)
            if rule["kind"] not in KINDS or rule["scope"] not in SCOPES:
                raise ValueError("Unsupported restored alert source")
            if "atoms" in rule:
                if not isinstance(rule["atoms"], list) or not 1 <= len(rule["atoms"]) <= 16 or rule.get("operator") not in {"ALL", "ANY"}:
                    raise ValueError("Invalid restored compound alert")
                for atom in rule["atoms"]:
                    validate_atom(atom)
                target = rule.get("target", {})
                mode = target.get("mode")
                account = [a["scope"] == "account" for a in rule["atoms"]]
                policies = {a["parameters"]["proposal_id"] for a in rule["atoms"] if a["kind"] == "policy_condition"}
                if (mode not in {"symbol", "account", "proposal", "snapshot", "follow"}
                        or any(account) and (not all(account) or mode != "account" or policies)
                        or mode == "account" and not all(account)
                        or policies and (len(policies) != 1 or mode != "proposal" or target.get("proposal_id") not in policies)
                        or mode == "proposal" and not policies):
                    raise ValueError("Restored alert target mixes incompatible evaluation identities")
                if mode in {"symbol", "proposal"} and target.get("symbol") != rule["symbol"]:
                    raise ValueError("Restored alert symbol binding differs")
                if mode in {"snapshot", "follow"}:
                    fields(rule, {"memberships": dict}, "watchlist alert memberships")
                    fields(target, {"watchlist_id": str}, "watchlist alert target")
                    current = set()
                    for member_id, member in rule["memberships"].items():
                        identity(member_id)
                        fields(member, {"symbol": str, "status": str, "added_at": str}, "alert membership")
                        if (not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", member["symbol"])
                                or member["status"] not in {"monitoring", "no_longer_monitored"}
                                or member["status"] == "monitoring" and member["symbol"] in current
                                or member["status"] == "no_longer_monitored" and not isinstance(member.get("removed_at"), str)):
                            raise ValueError("Invalid restored watchlist membership lifecycle")
                        if member["status"] == "monitoring":
                            current.add(member["symbol"])
    observations = values.get("attention_observations")
    if observations:
        fields(observations, {"rule_states": dict, "occurrences": dict, "monitor": dict}, "attention observations")
        fields(observations["monitor"], {"gaps": list}, "monitor history")
        from .attention import (
            EVIDENCE_SOURCE_FIELDS,
            KINDS,
            SCOPES,
            validate_atom,
            validate_drawing_evidence,
        )
        for occurrence_id, occurrence in observations["occurrences"].items():
            if "evidence" not in occurrence:
                continue  # Legacy observations remain readable without invented bindings.
            identity(occurrence_id)
            if occurrence.get("id") != occurrence_id:
                raise ValueError("Captured alert occurrence identity differs")
            evidence = occurrence["evidence"]
            if evidence.get("version") == "scan-program-evidence-v1":
                run = values.get("discovery", {}).get("runs", {}).get(evidence.get("run_id"), {})
                definition = run.get("definition", {})
                retained = run.get("results", {}).get(occurrence.get("symbol"), {})
                if (not definition.get("program") or evidence.get("definition_id") != occurrence.get("rule_id")
                        or evidence.get("definition_id") != definition.get("id")
                        or evidence.get("definition_revision") != occurrence.get("rule_revision")
                        or evidence.get("definition_revision") != definition.get("revision")
                        or evidence.get("program_sha256") != run.get("program_sha256")
                        or evidence.get("symbol") != occurrence.get("symbol") or occurrence.get("scope") != "history"
                        or evidence.get("evaluation") != occurrence.get("evaluation")
                        or evidence.get("evaluation") != retained.get("evaluation")
                        or evidence.get("calculation") != retained.get("calculation")
                        or occurrence.get("membership_id") != retained.get("membership_id")):
                    raise ValueError("Captured program alert differs from its frozen run, membership or exact calculation")
                continue
            fields(evidence, {"version": str, "evaluated_at": str, "rule": dict, "evaluation": dict,
                              "source": dict, "reference_status": str}, "alert occurrence evidence")
            fields(evidence["rule"], {"id": str, "revision": int, "kind": str, "scope": str, "symbol": str, "parameters": dict}, "captured alert rule")
            fields(evidence["evaluation"], {"state": str, "at": str, "input_identity": str, "facts": dict}, "captured alert evaluation")
            if (evidence["version"] != "occurrence-evidence-v1" or evidence["reference_status"] not in {"recorded_not_validated", "observation_only"}
                    or evidence["evaluated_at"] != evidence["evaluation"]["at"] or evidence["rule"]["kind"] not in KINDS or evidence["rule"]["scope"] not in SCOPES
                    or any(evidence["rule"][key] != occurrence[target] for key, target in (("id", "rule_id"), ("revision", "rule_revision"), ("scope", "scope"), ("symbol", "symbol")))
                    or evidence["evaluation"] != occurrence["evaluation"] or set(evidence["source"]) - EVIDENCE_SOURCE_FIELDS):
                raise ValueError("Restored alert evidence identity differs from its occurrence")
            retained_drawing_rule(evidence["rule"])
            if "membership_id" in evidence["rule"] and evidence["rule"]["membership_id"] != occurrence.get("membership_id"):
                raise ValueError("Captured alert membership differs from its occurrence")
            if "atoms" not in evidence:
                indicator_evidence(evidence)
                if evidence["rule"]["kind"] == "drawing":
                    validate_drawing_evidence(evidence["rule"], evidence["evaluation"])
            if "eligibility_evidence" in evidence["source"] and (evidence["rule"]["kind"] != "drawing" or not isinstance(evidence["source"]["eligibility_evidence"], dict)):
                raise ValueError("Only drawing sources may retain structured eligibility evidence")
            if any(key not in {"artifact", "eligibility_evidence"} and value is not None and type(value) not in {str, int, float, bool}
                   for key, value in evidence["source"].items()):
                raise ValueError("Captured alert source must contain bounded scalars and its retained artifact reference")
            proposal = evidence.get("proposal")
            if proposal is not None:
                fields(proposal, {"id": str, "revision": int, "policy_revision": int, "terms_sha256": str, "conditions": list}, "captured alert proposal")
                if proposal["id"] != evidence["rule"]["parameters"].get("proposal_id") or not all(isinstance(value, str) for value in proposal["conditions"]):
                    raise ValueError("Captured alert proposal binding differs")
            if "atoms" in evidence:
                parts = evidence["atoms"]
                definitions = evidence["rule"].get("atoms", [])
                evaluations = evidence["evaluation"].get("atoms", [])
                if (not isinstance(parts, list) or not 1 <= len(parts) <= 16 or len(parts) != len(definitions)
                        or len(parts) != len(evaluations) or evidence["rule"].get("operator") not in {"ALL", "ANY"}):
                    raise ValueError("Invalid captured compound evidence")
                for atom, definition, evaluation in zip(parts, definitions, evaluations, strict=True):
                    fields(atom, {"version": str, "rule": dict, "evaluation": dict, "source": dict, "evaluated_at": str}, "captured condition evidence")
                    validate_atom(atom["rule"])
                    indicator_evidence(atom)
                    if atom["rule"]["kind"] == "drawing":
                        validate_drawing_evidence(atom["rule"], atom["evaluation"])
                    if (atom["version"] != "occurrence-evidence-v1" or atom["evaluation"] != evaluation
                            or atom["evaluated_at"] != evaluation.get("at") or atom.get("store_generation") != evidence.get("store_generation")
                            or any(atom["rule"].get(k) != definition.get(k) for k in ("kind", "scope", "parameters"))
                            or any(atom["rule"].get(k) != evidence["rule"].get(k) for k in ("id", "revision", "symbol"))
                            or set(atom["source"]) - EVIDENCE_SOURCE_FIELDS or "atoms" in atom):
                        raise ValueError("Captured condition identity or evidence differs")
                    if "eligibility_evidence" in atom["source"] and (atom["rule"]["kind"] != "drawing" or not isinstance(atom["source"]["eligibility_evidence"], dict)):
                        raise ValueError("Only drawing condition sources may retain structured eligibility evidence")
                    if any(key not in {"artifact", "eligibility_evidence"} and value is not None and type(value) not in {str, int, float, bool} for key, value in atom["source"].items()):
                        raise ValueError("Captured condition source must retain bounded fields")
                    bound = atom.get("proposal")
                    if bound is not None:
                        fields(bound, {"id": str, "revision": int, "policy_revision": int, "terms_sha256": str, "conditions": list}, "captured condition proposal")
                        if bound["id"] != definition["parameters"].get("proposal_id") or not all(isinstance(v, str) for v in bound["conditions"]):
                            raise ValueError("Captured condition proposal binding differs")
        if not isinstance(observations.get("browser_profiles", {}), dict):
            raise ValueError("Invalid restored browser notification profiles")
        for profile_id, profile in observations.get("browser_profiles", {}).items():
            identity(profile_id)
            fields(profile, {"enabled": bool, "enabled_after": str, "generation": str, "deliveries": dict}, "browser notification profile")
            if profile["enabled"]:
                from .admission import instant
                instant(profile["enabled_after"])
            for occurrence_id, delivery in profile["deliveries"].items():
                fields(delivery, {"attempt_id": str, "state": str, "generation": str, "requested_at": str}, "browser notification attempt")
                identity(delivery["attempt_id"])
                if occurrence_id not in observations["occurrences"] or delivery["state"] not in {"requested", "failed"}:
                    raise ValueError("Restored browser notification occurrence or attempt state differs")
    discovery = values.get("discovery")
    if discovery:
        from .market_discovery import validate as validate_discovery
        validate_discovery(discovery, values.get("workspace"), resolve_artifact)
        for observation in discovery.get("option_observations", {}).values():
            fields(observation["artifact"], {"path": str, "sha256": str}, "option response artifact")
            path = PurePosixPath(observation["artifact"]["path"])
            if path.is_absolute() or ".." in path.parts or "\\" in str(path) or not path.parts or path.parts[0] != "reports":
                raise ValueError("Restored option response path must remain inside retained artifacts")
    market = values.get("market_history")
    if market:
        fields(market, {"entries": dict, "coverage": dict, "jobs": dict}, "market data jobs/cache")
        from .market_history import TIMEFRAMES, validate_chart_calculations
        validate_chart_calculations(market, workspace, resolve_artifact)
        for job in market["jobs"].values():
            fields(job, {"request": dict}, "market data job")
        for item in [*market["entries"].values(), *market["coverage"].values(), *(job.get("request", {}) for job in market["jobs"].values())]:
            if not isinstance(item, dict) or "timeframe" in item and item["timeframe"] not in TIMEFRAMES:
                raise ValueError("Invalid restored market-history interval")
            for key, expected in (("feed", "iex"), ("session", "provider_bar_aggregation"), ("currency", "USD")):
                if key in item and item[key] != expected:
                    raise ValueError("Restored history API provenance differs")
    evidence = values.get("stock_evidence")
    if evidence:
        fields(evidence, {"observations": dict, "history": dict}, "stock evidence")
