"""Structural contracts used before a restored generation can become active."""

import hashlib
import math
import re
from datetime import date, datetime
from pathlib import PurePosixPath
from uuid import UUID

from .investor import RULES, decimal, policy, broker_action_order, digest, native_quantity_offset
from .linked_orders import exit_plan, native_type, broker_payload, fractional_terms, trailing_terms


def fields(value, required, label):
    if not isinstance(value, dict) or any(key not in value or type(value[key]) is not kind for key, kind in required.items()):
        raise ValueError("Invalid restored " + label)


def identity(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("Invalid restored record identity")


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


def validate(values):
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
            quantity = fractional_terms(terms)
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
                if terms.get(key) is not None and (not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", str(terms[key])) or decimal(terms[key]) <= 0):
                    raise ValueError("Invalid restored USD order price")
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
            identity(command["id"])
            connection_context(command.get("connection_context"), command.get("account_id"))
            if (command.get("connection_context") is not None and not external
                    and command["connection_context"] != commands["approvals"].get(command["approval_id"], {}).get("connection_context")):
                raise ValueError("Restored command connection context differs from its original approval")
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
                if (command.get("approval_id") is not None or command.get("proposal_id") is not None
                        or command.get("proposal_revision") is not None or command.get("policy_revision") is not None
                        or command.get("submission_authority") is not False
                        or order["id"] not in command["broker_order_ids"] or command["client_order_id"] != order["client_order_id"]
                        or command["native_client_order_id"] != order["nautilus"]["client_order_id"]
                        or terms.get("account_id") != command["account_id"] or terms.get("symbol") != order["symbol"]
                        or command.get("symbol") != terms.get("symbol") or command.get("side") != terms.get("side")
                        or terms.get("instrument_id") != command["instrument_id"] or command["instrument_id"] != order["nautilus"]["instrument_id"]
                        or terms.get("side") != order["side"].upper() or decimal(terms.get("quantity")) != decimal(order["qty"])
                        or terms.get("order_type") != native_type(order.get("type", order.get("order_type")))
                        or terms.get("time_in_force") != order.get("time_in_force", "").upper()
                        or terms.get("session") != ("extended" if order["extended_hours"] else "regular")
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
        from .attention import EVIDENCE_SOURCE_FIELDS, KINDS, SCOPES
        for occurrence_id, occurrence in observations["occurrences"].items():
            if "evidence" not in occurrence:
                continue  # Legacy observations remain readable without invented bindings.
            identity(occurrence_id)
            if occurrence.get("id") != occurrence_id:
                raise ValueError("Captured alert occurrence identity differs")
            evidence = occurrence["evidence"]
            fields(evidence, {"version": str, "evaluated_at": str, "rule": dict, "evaluation": dict,
                              "source": dict, "reference_status": str}, "alert occurrence evidence")
            fields(evidence["rule"], {"id": str, "revision": int, "kind": str, "scope": str, "symbol": str, "parameters": dict}, "captured alert rule")
            fields(evidence["evaluation"], {"state": str, "at": str, "input_identity": str, "facts": dict}, "captured alert evaluation")
            if (evidence["version"] != "occurrence-evidence-v1" or evidence["reference_status"] not in {"recorded_not_validated", "observation_only"}
                    or evidence["evaluated_at"] != evidence["evaluation"]["at"] or evidence["rule"]["kind"] not in KINDS or evidence["rule"]["scope"] not in SCOPES
                    or any(evidence["rule"][key] != occurrence[target] for key, target in (("id", "rule_id"), ("revision", "rule_revision"), ("scope", "scope"), ("symbol", "symbol")))
                    or evidence["evaluation"] != occurrence["evaluation"] or set(evidence["source"]) - EVIDENCE_SOURCE_FIELDS):
                raise ValueError("Restored alert evidence identity differs from its occurrence")
            if any(key != "artifact" and value is not None and type(value) not in {str, int, float, bool}
                   for key, value in evidence["source"].items()):
                raise ValueError("Captured alert source must contain bounded scalars and its retained artifact reference")
            proposal = evidence.get("proposal")
            if proposal is not None:
                fields(proposal, {"id": str, "revision": int, "policy_revision": int, "terms_sha256": str, "conditions": list}, "captured alert proposal")
                if proposal["id"] != evidence["rule"]["parameters"].get("proposal_id") or not all(isinstance(value, str) for value in proposal["conditions"]):
                    raise ValueError("Captured alert proposal binding differs")
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
    market = values.get("market_history")
    if market:
        fields(market, {"entries": dict, "coverage": dict, "jobs": dict}, "market data jobs/cache")
        from .market_history import TIMEFRAMES
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
