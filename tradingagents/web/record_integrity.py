"""Structural contracts used before a restored generation can become active."""

import re
from datetime import date
from uuid import UUID

from .investor import RULES, decimal, policy, broker_action_order, digest, native_quantity_offset


def fields(value, required, label):
    if not isinstance(value, dict) or any(key not in value or type(value[key]) is not kind for key, kind in required.items()):
        raise ValueError("Invalid restored " + label)


def identity(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("Invalid restored record identity")


def validate(values):
    workspace = values.get("workspace")
    if workspace:
        fields(workspace, {"watchlists": list, "preferences": dict, "notes": dict, "browser_imports": list}, "workspace")
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
            fields(terms, {"symbol": str, "instrument_id": str, "side": str, "quantity": str, "order_type": str, "rationale": str}, "proposal terms")
            if (not re.fullmatch(r"[1-9]\d{0,17}", terms["quantity"]) or terms["side"] not in {"BUY", "SELL"}
                    or terms["order_type"] not in {"MARKET", "LIMIT"} or terms.get("time_in_force") != "DAY"
                    or terms.get("session") != "regular" or not isinstance(proposal["impact"].get("conditions"), list)):
                raise ValueError("Unsupported restored proposal terms or review")
        for basket in investor.get("baskets", []):
            fields(basket, {"id": str, "revision": int, "status": str, "preview": dict, "linked_proposal_ids": list, "history": list, "updated_at": str}, "basket")
            identity(basket["id"])
            fields(basket["preview"], {"targets": list, "reason": str, "legs": list, "complete_scenario": dict, "partial_scenario": dict}, "basket preview")
            if set(basket["linked_proposal_ids"]) - proposals:
                raise ValueError("Restored basket refers to a missing proposal")
    reporting = values.get("reporting")
    if reporting:
        fields(reporting, {"entries": dict, "collections": list, "settings_history": list}, "decision journal")
        if not isinstance(reporting.get("technical_method_acceptances", {}), dict):
            raise ValueError("Invalid technical method acceptance records")
        for collection in reporting["collections"]:
            fields(collection, {"id": str, "account_id": str, "artifact": dict, "requested_start": str, "requested_end": str, "collected_at": str}, "account history")
            identity(collection["id"])
            date.fromisoformat(collection["requested_start"])
            date.fromisoformat(collection["requested_end"])
    commands = values.get("commands")
    if commands:
        fields(commands, {"approvals": dict, "revocations": dict, "commands": dict, "account_versions": dict, "recovery_required": bool}, "command authority")
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
        for command in commands["commands"].values():
            external = command.get("origin") == "external_broker"
            required = {"id": str, "client_order_id": str, "terms": dict, "timeline": list,
                        "state": str, "broker_order_ids": list, "event_ids": list, "filled_quantity": str,
                        "remaining_quantity": str}
            if not external:
                required.update(approval_id=str, cash_commitment=str)
            fields(command, required, "command commitment")
            identity(command["id"])
            if external:
                fields(command, {"account_id": str, "instrument_id": str, "native_client_order_id": str,
                    "source_observation": dict, "terms_sha256": str}, "external order provenance")
                source = command["source_observation"]
                fields(source, {"order": dict, "order_version": str, "account_observed_at": str, "native_epoch": str}, "external source observation")
                order = broker_action_order({"status": "connected", "account": {"id": command["account_id"]},
                    "orders": [source["order"]]}, source["order"]["id"], source["order_version"])
                terms = command["terms"]
                if (command.get("approval_id") is not None or command.get("proposal_id") is not None
                        or command.get("proposal_revision") is not None or command.get("policy_revision") is not None
                        or command.get("submission_authority") is not False
                        or order["id"] not in command["broker_order_ids"] or command["client_order_id"] != order["client_order_id"]
                        or command["native_client_order_id"] != order["nautilus"]["client_order_id"]
                        or terms.get("account_id") != command["account_id"] or terms.get("symbol") != order["symbol"]
                        or command.get("symbol") != terms.get("symbol") or command.get("side") != terms.get("side")
                        or terms.get("instrument_id") != command["instrument_id"] or command["instrument_id"] != order["nautilus"]["instrument_id"]
                        or terms.get("side") != order["side"].upper() or decimal(terms.get("quantity")) != decimal(order["qty"])
                        or terms.get("order_type") != str(order.get("type", order.get("order_type"))).upper()
                        or terms.get("time_in_force") != "DAY" or terms.get("session") != "regular"
                        or decimal(terms.get("limit_price")) != decimal(order.get("limit_price"))
                        or command["terms_sha256"] != digest(terms)):
                    raise ValueError("Restored external order identity or provenance differs")
                unknown_cash = command.get("cash_commitment") is None and command.get("price_cap") is None and terms["side"] == "BUY"
                if not unknown_cash and (not isinstance(command.get("cash_commitment"), str)
                        or decimal(command["cash_commitment"]) is None or decimal(command["cash_commitment"]) < 0):
                    raise ValueError("Invalid restored external principal commitment")
            elif command["approval_id"] not in commands["approvals"]:
                raise ValueError("Restored command approval is missing")
            quantity_proof = command.get("native_replacement_quantity_binding")
            if quantity_proof:
                proof_order = {"id": quantity_proof.get("broker_order_id"), "client_order_id": command["client_order_id"],
                    "type": command["terms"].get("order_type", "").lower(), "replaces": quantity_proof.get("predecessor_order_id"),
                    "qty": command["terms"].get("quantity"), "filled_qty": quantity_proof.get("broker_filled_quantity"),
                    "native_replacement_quantity_binding": quantity_proof}
                offset = native_quantity_offset(proof_order)
                if (proof_order["id"] not in command["broker_order_ids"]
                        or decimal(command.get("native_quantity_offset")) != offset):
                    raise ValueError("Restored MARKET successor native quantity binding differs")
            elif decimal(command.get("native_quantity_offset", "0")) != 0:
                raise ValueError("Restored native quantity offset has no execution provenance")
            if any(decimal(command[k]) is None or decimal(command[k]) < 0 for k in
                   (("filled_quantity", "remaining_quantity") if external else ("filled_quantity", "remaining_quantity", "cash_commitment"))):
                raise ValueError("Restored command authority or commitments are incomplete")
    attention = values.get("attention")
    if attention:
        fields(attention, {"rules": dict, "reviews": dict, "rule_history": list}, "attention rules")
        from .attention import KINDS, SCOPES
        for rule in attention["rules"].values():
            fields(rule, {"id": str, "name": str, "kind": str, "scope": str, "symbol": str, "parameters": dict, "active": bool, "revision": int}, "alert rule")
            if rule["kind"] not in KINDS or rule["scope"] not in SCOPES:
                raise ValueError("Unsupported restored alert source")
    observations = values.get("attention_observations")
    if observations:
        fields(observations, {"rule_states": dict, "occurrences": dict, "monitor": dict}, "attention observations")
        fields(observations["monitor"], {"gaps": list}, "monitor history")
    market = values.get("market_history")
    if market:
        fields(market, {"entries": dict, "coverage": dict, "jobs": dict}, "market data jobs/cache")
    evidence = values.get("stock_evidence")
    if evidence:
        fields(evidence, {"observations": dict, "history": dict}, "stock evidence")
