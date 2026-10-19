"""Inspectable human decisions and versioned follow-up notes."""

import copy
import re
from datetime import UTC, date, datetime

from .workspace import text

DEFAULT = {"entries": {}, "collections": [], "benchmark": None, "horizon_days": None, "settings_history": []}


def command_outcome(command, authority):
    deliveries = command.get("native_deliveries", {})
    native = "not_applicable_never_sent" if command["state"] == "not_sent" else "durability_deferred"
    if command.get("native_pending_commitment") or any(item.get("status") in {"unresolved", "conflict"} for item in deliveries.values()):
        native = "unresolved"
    return {"command_id": command["id"], "proposal_id": command["proposal_id"],
            "proposal_revision": command["proposal_revision"], "terms_sha256": command["terms_sha256"],
            "terms": copy.deepcopy(command["terms"]), "origin": command.get("origin", "app_proposal"),
            "source_observation": copy.deepcopy(command.get("source_observation")), "client_order_id": command["client_order_id"],
            "native_client_order_id": command.get("native_client_order_id", command["client_order_id"]),
            "broker_order_ids": copy.deepcopy(command["broker_order_ids"]), "fill_ids": copy.deepcopy(command.get("fill_ids", [])),
            "broker_outcome": command["state"], "filled_quantity": command["filled_quantity"],
            "native_application": native, "native_durability": "deferred", "native_receipts": copy.deepcopy(deliveries),
            "timeline": copy.deepcopy(command["timeline"]), "approval": copy.deepcopy(authority.get("approvals", {}).get(command["approval_id"])),
            "approval_revocation": copy.deepcopy(authority.get("revocations", {}).get(command["approval_id"])),
            "exercise_authorization": copy.deepcopy(authority.get("exercise_authorizations", {}).get(command.get("exercise_id"))),
            "pending_action": copy.deepcopy(command.get("pending_action")),
            "action_exercise_authorization": copy.deepcopy(authority.get("exercise_authorizations", {}).get((command.get("pending_action") or {}).get("exercise_id"))),
            "retained_cash_commitment": command["cash_commitment"],
            "native_pending_commitment": copy.deepcopy(command.get("native_pending_commitment")),
            "basket_execution_id": command.get("basket_execution_id"), "depends_on": command.get("depends_on", [])}


def decisions(investor, journal, history, authority=None):
    result = []
    authority = authority or {}
    commands = list(authority.get("commands", {}).values())
    for proposal in investor.get("proposals", []):
        terms = proposal["terms"]
        result.append({"id": "proposal:" + proposal["id"], "kind": "human_proposal", "record_id": proposal["id"],
            "symbol": terms["symbol"], "revision": proposal["revision"], "status": proposal["status"],
            "saved_at": proposal["updated_at"], "rationale": terms["rationale"], "terms": copy.deepcopy(terms),
            "research": copy.deepcopy(terms.get("research")), "policy_revision": proposal["policy_revision"],
            "terms_sha256": proposal["terms_sha256"], "history": copy.deepcopy(proposal["history"]),
            "approval_recorded": copy.deepcopy(proposal.get("approval")), "engine_order_id": proposal.get("engine_order_id"),
            "broker_order_id": proposal.get("broker_order_id"), "fill_ids": copy.deepcopy(proposal.get("fill_ids")), "executable": False})
    for basket in investor.get("baskets", []):
        result.append({"id": "basket:" + basket["id"], "kind": "allocation_basket", "record_id": basket["id"],
            "symbol": ", ".join(t["symbol"] for t in basket["preview"]["targets"]), "revision": basket["revision"],
            "status": basket["status"], "saved_at": basket["updated_at"], "rationale": basket["preview"]["reason"],
            "linked_proposal_ids": copy.deepcopy(basket["linked_proposal_ids"]), "policy_revision": basket["preview"]["policy_revision"],
            "account_id": basket["preview"]["account_id"], "history": copy.deepcopy(basket["history"]),
            "approval_recorded": copy.deepcopy(basket.get("approval")), "executable": False})
    seen = set()
    for draft in journal.get("drafts", []) + history.get("drafts", []):
        order = draft.get("order", {})
        identity = order.get("client_order_id")
        if not identity or identity in seen:
            continue
        seen.add(identity)
        result.append({"id": "native_draft:" + identity, "kind": "saved_native_draft", "record_id": identity,
            "symbol": draft.get("symbol"), "status": draft.get("status"), "saved_at": draft.get("created_at"),
            "revision": draft.get("revision"), "terms": copy.deepcopy(order), "research": copy.deepcopy(draft.get("source")),
            "approval_recorded": copy.deepcopy(draft.get("approval")), "broker_submitted_recorded": draft.get("broker_submitted"),
            "engine_order_id": identity, "broker_order_id": draft.get("broker_order_id"),
            "fill_ids": copy.deepcopy(draft.get("fill_ids")), "executable": False,
            "limitation": "A saved initialized order does not establish ownership by the current engine or a broker execution"})
    for item in result:
        proposal_ids = item.get("linked_proposal_ids", []) if item["kind"] == "allocation_basket" else [item["record_id"]] if item["kind"] == "human_proposal" else []
        linked = [command for command in commands if command["proposal_id"] in proposal_ids]
        item["command_outcomes"] = [command_outcome(command, authority) for command in linked]
        item["decision_links"] = ["command:" + command["id"] for command in linked]
        if item["kind"] == "allocation_basket":
            item["execution_plans"] = [copy.deepcopy(group) for group in authority.get("basket_executions", {}).values() if group["basket_id"] == item["record_id"]]
    for command in commands:
        result.append({"id": "command:" + command["id"], "kind": "durable_command", "record_id": command["id"],
            "symbol": command["symbol"], "revision": command["proposal_revision"], "status": command["state"],
            "saved_at": command["timeline"][0]["at"], "rationale": command["terms"].get("rationale"),
            "research": copy.deepcopy(command["terms"].get("research")), "policy_revision": command["policy_revision"],
            "decision_links": ["proposal:" + command["proposal_id"]] if command.get("proposal_id") else [],
            "origin": command.get("origin", "app_proposal"),
            "command_outcomes": [command_outcome(command, authority)], "executable": False})
    return sorted(result, key=lambda item: item.get("saved_at") or "", reverse=True)


def change(saved, request, available):
    stamp = datetime.now(UTC).isoformat()
    action = request.get("action")
    if action == "note":
        identity = request.get("id")
        if identity not in {item["id"] for item in available}:
            raise ValueError("Select an existing saved decision")
        review_date = request.get("review_date") or None
        if review_date:
            review_date = date.fromisoformat(review_date).isoformat()
        entry = {"assumptions": text(request.get("assumptions", ""), 20000, "assumptions"),
                 "review_date": review_date, "outcome_notes": text(request.get("outcome_notes", ""), 20000, "outcome notes"),
                 "saved_at": stamp, "revision": saved["entries"].get(identity, {}).get("revision", 0) + 1}
        prior = saved["entries"].get(identity, {})
        saved["entries"][identity] = {**entry, "history": prior.get("history", []) + [copy.deepcopy(entry)]}
    elif action == "settings":
        benchmark = request.get("benchmark")
        if benchmark:
            symbol = text(benchmark.get("symbol"), 30, "benchmark symbol")
            currency = text(benchmark.get("currency"), 3, "benchmark currency")
            treatment = benchmark.get("treatment")
            if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", symbol) or currency != "USD" or treatment not in {"price", "total_return"}:
                raise ValueError("Benchmark requires a symbol, USD currency and explicit price/total-return treatment")
            benchmark = {"symbol": symbol, "currency": currency, "treatment": treatment}
        horizon = request.get("horizon_days")
        if horizon is not None and (type(horizon) is not int or not 1 <= horizon <= 36500):
            raise ValueError("Enter a positive whole-day review horizon or leave it unset")
        reason = text(request.get("reason", ""), 4000, "reporting settings reason")
        saved.update(benchmark=benchmark, horizon_days=horizon)
        saved["settings_history"].append({"benchmark": benchmark, "horizon_days": horizon, "reason": reason, "saved_at": stamp})
    else:
        raise ValueError("Unknown decision journal edit")
    return saved
