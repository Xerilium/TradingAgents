"""Inspectable human decisions and versioned follow-up notes."""

import copy
import re
from datetime import UTC, date, datetime

from .workspace import text
from .investor import decimal, digest

DEFAULT = {"entries": {}, "collections": [], "benchmark": None, "horizon_days": None, "settings_history": [],
           "strategy_definitions": {}, "strategy_history": []}


def validate_experiment_event(item, event, captured):
    if (not isinstance(captured, dict) or captured.get("experiment_id") != item["id"]
            or captured.get("event_id") != event["id"] or captured.get("ordinal") != event["ordinal"] or captured.get("at") != event["at"]):
        raise ValueError("Retained experiment event envelope differs from its durable index")
    payload = captured.get("payload")
    if (not isinstance(payload, dict) or digest(payload) != event["payload_sha256"]
            or payload.get("spec_sha256") != item["spec_sha256"]
            or any(payload.get(key) != event.get(key) for key in ("type", "fold_id", "trial_id", "phase", "scenario_id", "source_event_id", "execution", "source_trial"))):
        raise ValueError("Retained event kind, source identity or complete payload hash differs")
    if event["type"] == "dispatch":
        if payload.get("native_spec_sha256") != event["native_spec_sha256"]:
            raise ValueError("Native dispatch specification differs from its durable event")
        if event.get("execution") == "native":
            spec = payload.get("native_spec") or {}
            if (spec.get("kind") != "strategy_trial" or spec.get("experiment_sha256") != item["spec_sha256"]
                    or spec.get("spec_sha256") != event["native_spec_sha256"]
                    or digest({key: value for key, value in spec.items() if key != "spec_sha256"}) != spec["spec_sha256"]):
                raise ValueError("Exact native trial kind/specification is unavailable or changed")
    if event["type"] == "result":
        result = payload.get("result") or {}
        if result.get("kind") != "strategy_trial" or result.get("spec_sha256") != event.get("native_spec_sha256"):
            raise ValueError("Actual native result kind/specification differs from its source event")
    return payload


def validate_experiment_record(item, resolve_artifact=None):
    """Validate the durable index and event ordering, without interpreting optimizer results."""
    from uuid import UUID

    from .evaluation import EXPERIMENT_VERSION, reference, validate_experiment
    if str(UUID(item["id"])) != item["id"]:
        raise ValueError("Invalid retained experiment identity")
    if item["kind"] == "experiment_comparison":
        reference(item["comparison_artifact"])
        if len(item["members"]) < 2 or len({row["experiment_id"] for row in item["members"]}) != len(item["members"]):
            raise ValueError("Comparison requires distinct immutable experiment members")
        for row in item["members"]:
            reference(row["preview_artifact"])
            reference(row["result_artifact"])
        if resolve_artifact:
            captured = resolve_artifact(item["comparison_artifact"])
            if not isinstance(captured, dict) or captured.get("kind") != "experiment_comparison" or captured.get("members") != item["members"]:
                raise ValueError("Retained comparison payload differs from its exact member index")
        return
    if (item["kind"] != "experiment" or item.get("version") != EXPERIMENT_VERSION
            or item["status"] not in {"preview", "queued", "running", "cancelling", "completed", "no_qualifier", "cancelled", "interrupted", "failed"}
            or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("spec_sha256", "")))
            or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("strategy_sha256", ""))) or type(item.get("cancel_requested")) is not bool
            or not isinstance(item.get("events"), list) or type(item.get("strategy_revision")) is not int or item["strategy_revision"] <= 0):
        raise ValueError("Invalid retained experiment state or immutable identity")
    reference(item["preview_artifact"])
    if resolve_artifact:
        spec = resolve_artifact(item["preview_artifact"])
        if not isinstance(spec, dict):
            raise ValueError("Exact immutable experiment preview is unavailable")
        validate_experiment(spec)
        if (spec["spec_sha256"] != item["spec_sha256"] or spec["strategy_sha256"] != item["strategy_sha256"]
                or spec["strategy"]["id"] != item["strategy_id"] or spec["strategy"]["revision"] != item["strategy_revision"]):
            raise ValueError("Experiment preview differs from its immutable index")
    if item.get("result_artifact"):
        reference(item["result_artifact"])
        if resolve_artifact:
            result = resolve_artifact(item["result_artifact"])
            if not isinstance(result, dict) or result.get("kind") != "experiment" or result.get("spec_sha256") != item["spec_sha256"] or result.get("status") != item["status"]:
                raise ValueError("Retained experiment result differs from its exact immutable index")
    elif item["status"] in {"completed", "no_qualifier"}:
        raise ValueError("A completed experiment requires its actual retained result")
    asked, dispatched, results, told, ids, sources = set(), {}, {}, set(), set(), set()
    for ordinal, event in enumerate(item["events"], 1):
        if str(UUID(event["id"])) != event["id"] or event["id"] in ids or event["ordinal"] != ordinal:
            raise ValueError("Experiment events require unique durable identities and consecutive ordinals")
        ids.add(event["id"])
        reference(event["artifact"])
        kind, trial = event["type"], (event.get("fold_id"), event.get("trial_id"))
        run = (*trial, event.get("phase"), event.get("scenario_id"))
        source_id = digest({"type": kind, "fold_id": trial[0], "trial_id": trial[1], "phase": run[2], "scenario_id": run[3], "spec_sha256": item["spec_sha256"]})
        if event.get("source_event_id") != source_id or source_id in sources or not re.fullmatch(r"[0-9a-f]{64}", str(event.get("payload_sha256", ""))):
            raise ValueError("Experiment event source identity/payload hash is invalid or repeated")
        sources.add(source_id)
        payload = validate_experiment_event(item, event, resolve_artifact(event["artifact"])) if resolve_artifact else None
        if kind not in {"ask", "dispatch", "result", "tell", "selection", "oos", "budget"}:
            raise ValueError("Unknown experiment event type")
        if kind == "ask":
            if trial in asked or None in trial:
                raise ValueError("An optimizer trial cannot be asked twice or without identity")
            asked.add(trial)
        elif kind == "dispatch":
            if trial not in asked or run in dispatched or run[2] not in {"train", "validation", "oos"}:
                raise ValueError("Native dispatch needs one durable ASK and a unique actual run identity")
            if event.get("execution") not in {"native", "reused_source_trial"} or not re.fullmatch(r"[0-9a-f]{64}", str(event.get("native_spec_sha256", ""))):
                raise ValueError("Native execution and explicitly reused source trials must remain distinct")
            if event["execution"] == "reused_source_trial":
                source = event.get("source_trial") or {}
                source_run = tuple(source.get(key) for key in ("fold_id", "trial_id", "phase", "scenario_id"))
                if source_run not in results or dispatched[source_run]["native_spec_sha256"] != event["native_spec_sha256"]:
                    raise ValueError("A reused trial requires a prior retained result of the identical native specification")
            dispatched[run] = event
        elif kind == "result":
            if run not in dispatched or run in results:
                raise ValueError("Native RESULT must follow its unique durable DISPATCH")
            if event.get("native_spec_sha256") != dispatched[run].get("native_spec_sha256") or event.get("execution") != dispatched[run].get("execution"):
                raise ValueError("Trial result differs from its exact native/reused source dispatch")
            if event.get("execution") == "reused_source_trial":
                if event.get("source_trial") != dispatched[run].get("source_trial"):
                    raise ValueError("Reused result source differs from its retained dispatch")
                source_run = tuple(event["source_trial"].get(key) for key in ("fold_id", "trial_id", "phase", "scenario_id"))
                if payload is not None and payload["result"] != results[source_run]:
                    raise ValueError("Reused result bytes differ from their retained actual source result")
            results[run] = payload["result"] if payload is not None else None
        elif kind == "tell":
            if trial not in asked or trial in told or not any(row[:2] == trial and row[2] != "oos" for row in results) or any(row[:2] == trial and row[2] != "oos" and row not in results for row in dispatched):
                raise ValueError("Optimizer TELL requires durable completed results and cannot replay a trial")
            told.add(trial)


def command_outcome(command, authority, position_groups=()):
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
            "basket_execution_id": command.get("basket_execution_id"), "depends_on": command.get("depends_on", []),
            "position_outcome_ids": [group["lifecycle_id"] for group in position_groups if command["id"] in group["command_ids"]]}


def position_outcomes(captures, authority, investor):
    """Project retained native observations once per proven lifecycle; never allocate PnL to decisions."""
    groups, unattributed = {}, []
    commands = authority.get("commands", {})
    proposal_ids = {item["id"] for item in investor.get("proposals", [])}
    contexts = {}
    for capture in captures:
        report = capture.get("report") or {}
        if not capture.get("metadata_gap") and report.get("native_epoch") and report.get("account_context"):
            contexts.setdefault(report["native_epoch"], []).append(report["account_context"])
    for capture in captures:
        report = capture.get("report")
        if capture.get("metadata_gap") or not report or not isinstance(report.get("position_lifecycles"), list):
            unattributed.append({"capture_id": capture["id"], "artifact": capture["artifact"], "captured_at": capture["captured_at"],
                "observation": copy.deepcopy(report), "gaps": [capture.get("metadata_gap") or "Retained native report is unavailable, changed, or lacks lifecycle membership; inspect the original artifact"]})
            continue
        for observation in report.get("position_lifecycles", []):
            identity = observation.get("identity", {})
            if any(command.get("terms", {}).get("order_class") == "mleg" and command.get("instrument_id") == identity.get("instrument_id") for command in commands.values()):
                unattributed.append({"capture_id": capture["id"], "artifact": capture["artifact"], "captured_at": capture["captured_at"],
                    "observation": copy.deepcopy(observation), "gaps": ["Internal package control position/status is not actual leg economics, fees or PnL"]})
                continue
            if (any(not isinstance(identity.get(key), str) or identity[key] in ("", "None") for key in
                    ("account_id", "broker_account_id", "endpoint", "mode", "position_id", "instrument_id", "opening_order_id", "ts_opened"))
                    or identity["mode"] not in {"paper", "live"} or not identity["ts_opened"].isdigit() or int(identity["ts_opened"]) <= 0
                    or any(identity.get(key) != report["account_context"].get(key) for key in ("account_id", "broker_account_id", "endpoint", "mode"))):
                unattributed.append({"capture_id": capture["id"], "artifact": capture["artifact"], "captured_at": capture["captured_at"],
                    "native_epoch": report["native_epoch"], "identity": identity, "observation": copy.deepcopy(observation),
                    "gaps": ["Native position lacks exact account/mode/opening identity; inspect the original report"]})
                continue
            lifecycle = "native-position:" + digest(identity)
            source = {"capture_id": capture["id"], "artifact": capture["artifact"], "captured_at": capture["captured_at"],
                "native_epoch": report["native_epoch"], "is_snapshot": observation["is_snapshot"],
                "ts_last": observation["native_position"].get("ts_last")}
            group = groups.setdefault(lifecycle, {"lifecycle_id": lifecycle, **identity, "account_context": report["account_context"],
                "source_refs": [], "observations": [], "coverage": {"status": "incomplete", "gaps": []}})
            group["source_refs"].append(source)
            group["observations"].append({"observation": observation, "source": source, "report": report})
    for group in groups.values():
        observations = group.pop("observations")
        selected = max(observations, key=lambda item: (int(item["observation"]["native_position"].get("ts_last") or 0), item["source"]["captured_at"]))
        latest, report = selected["observation"], selected["report"]
        gaps = group["coverage"]["gaps"]
        events = {event["fill_id"]: event for event in latest["events"]}
        if any(any(not isinstance(event.get(key), str) or not event[key] or event[key] == "None" for key in
                   ("fill_id", "client_order_id", "broker_order_id", "account_id", "instrument_id")) for event in latest["events"]):
            gaps.append("Native fill lacks exact order/account/execution identity; source attribution remains unknown")
        if len(events) != len(latest["events"]) or set(events) != set(latest["fill_ids"]):
            gaps.append("Native fill membership is duplicated or incomplete; inspect the original native position events")
            group["membership_ambiguous"] = True
        if set(latest["client_order_ids"]) != {event["client_order_id"] for event in latest["events"]}:
            gaps.append("Native order membership differs from fill events")
        if not any(event["client_order_id"] == group["opening_order_id"] and event["ts_event"] == group["ts_opened"] and event["source_matched"] for event in latest["events"]):
            gaps.append("Opening fill lacks exact source evidence; collect the original opening history and capture again")
        for instance in observations:
            old = instance["observation"]
            for event in old["events"]:
                current = events.get(event["fill_id"])
                keys = ("client_order_id", "broker_order_id", "account_id", "instrument_id", "side", "ts_event", "commission")
                if (not current or any(event.get(key) != current.get(key) for key in keys)
                        or any(decimal(event.get(key)) != decimal(current.get(key)) for key in ("quantity", "price"))):
                    gaps.append("Retained captures disagree on lifecycle fill membership/economics; reconcile the original captures")
                    group["membership_ambiguous"] = True
        gaps.extend(latest.get("gaps", []))
        if (report.get("reconciliation") or {}).get("status") != "reconciled":
            gaps.append("Capture native/broker reconciliation was incomplete")
        if (report.get("recovery_coverage") or {}).get("complete") is not True or not (report.get("recovery_coverage") or {}).get("evidence"):
            gaps.append("Declared source history is incomplete; collect missing history before claiming a complete lifecycle")
        fee_sources, fee_states = [], set()
        for event in latest["events"]:
            source = event.get("source") or {}
            fee = source.get("native_fee") or {}
            state = "actual" if event["source_matched"] and fee.get("modeled") is False else "modeled" if fee.get("modeled") is True else "unknown"
            fee_states.add(state)
            fee_sources.append({"fill_id": event["fill_id"], "status": state, "native_commission": event["commission"],
                "actual_commission": source.get("commission"), "native_fee": fee})
        if fee_states != {"actual"}:
            gaps.append("Actual commissions are not established for every lifecycle fill; modeled/unknown fees are not actual costs")
        if any(value["currency"] != latest["native_position"].get("settlement_currency") for value in latest["commissions"]):
            gaps.append("Native commissions include another currency; no FX conversion or combined net is inferred")
        member_clients, member_brokers, member_fills = (set(value for value in latest[key] if value is not None)
            for key in ("client_order_ids", "broker_order_ids", "fill_ids"))
        original_mode_proof = {identity for identity, command in commands.items() if (
            (context := command.get("connection_context") or authority.get("approvals", {}).get(command.get("approval_id"), {}).get("connection_context") or {})
            and context.get("account_id") == group["broker_account_id"] and context.get("endpoint") == group["endpoint"]
            and context.get("mode") == group["mode"] and context.get("connection_session"))}
        mode_bound = original_mode_proof | {identity for identity, command in commands.items() if any(
            all(context.get(key) == group["account_context"].get(key) for key in ("account_id", "broker_account_id", "endpoint", "mode"))
            for context in contexts.get((command.get("source_observation") or {}).get("native_epoch"), []))}
        package_members = {identity for identity, command in commands.items() if command.get("account_id") == group["broker_account_id"]
            and command.get("terms", {}).get("order_class") == "mleg" and any(
                member.get("symbol", "") + ".ALPACA" == latest["native_position"]["instrument_id"]
                and (member.get("id") in member_brokers or member.get("package_parent_id") in member_brokers)
                and member.get("native_client_order_id") in member_clients for member in command.get("package_members", []))}
        candidates = package_members | {identity for identity, command in commands.items() if command.get("account_id") == group["broker_account_id"]
            and command.get("instrument_id") == latest["native_position"]["instrument_id"] and (
                command.get("native_client_order_id", command.get("client_order_id")) in member_clients
                or member_brokers.intersection(command.get("broker_order_ids", [])) or member_fills.intersection(command.get("fill_ids", [])))}
        members = candidates.intersection(mode_bound)
        while True:
            prior = set(members)
            broker_ids = {value for identity in members for value in commands[identity].get("broker_order_ids", [])}
            for identity, command in commands.items():
                if identity not in mode_bound or command.get("account_id") != group["broker_account_id"] or command.get("instrument_id") != latest["native_position"]["instrument_id"] and identity not in package_members:
                    continue
                relations = {command.get(key) for key in ("parent_command_id", "linked_entry_command_id", "linked_group_owner_id")}
                if identity in members:
                    members.update(value for value in relations if value in mode_bound)
                elif relations.intersection(members) or (command.get("terms", {}).get("replacement") or {}).get("order_id") in broker_ids:
                    members.add(identity)
            if members == prior:
                break
        contributors, links = [], set()
        for identity in sorted(members):
            command = commands[identity]
            decision_links = ["command:" + identity]
            if command.get("proposal_id") in proposal_ids and identity in original_mode_proof:
                decision_links.append("proposal:" + command["proposal_id"])
            links.update(decision_links)
            contributors.append({"command_id": identity, "proposal_id": command.get("proposal_id"), "proposal_revision": command.get("proposal_revision"),
                "terms_sha256": command["terms_sha256"], "terms": copy.deepcopy(command["terms"]), "origin": command.get("origin", "app_proposal"),
                "research": copy.deepcopy(command["terms"].get("research")) if identity in original_mode_proof else None,
                "rationale": command["terms"].get("rationale"), "decision_links": decision_links})
        decision_gaps = []
        if candidates - mode_bound:
            decision_gaps.append("Original account mode/session evidence is unavailable for command(s) " + ", ".join(sorted(candidates - mode_bound)) + "; financial results are not attributed to those decisions")
        if not member_clients.issubset({commands[identity].get("native_client_order_id", commands[identity].get("client_order_id")) for identity in members}):
            decision_gaps.append("Some native orders have no saved decision authority; broker-only provenance is retained without inventing thesis links")
        group.update(instrument_id=latest["native_position"]["instrument_id"], native_position=latest["native_position"],
            is_snapshot=latest["is_snapshot"], latest_capture_at=selected["source"]["captured_at"], selected_source_ref=selected["source"],
            realized_pnl=latest["realized_pnl"], unrealized_pnl=latest["unrealized_pnl"], mark=latest["mark"], commissions=latest["commissions"],
            fills=latest["events"], fill_ids=sorted(member_fills), command_ids=sorted(members), contributors=contributors, decision_links=sorted(links),
            decision_link_gaps=decision_gaps,
            fee_provenance={"status": next(iter(fee_states)) if len(fee_states) == 1 else "mixed" if fee_states else "unknown", "fill_sources": fee_sources}, actual_net=None,
            accounting_basis="Native position accounting; realized PnL already includes native commissions. No second fee subtraction, proposal allocation, FX or broker-statement net claim",
            precision_limitation="Decimal strings preserve native reported values; installed average-price/PnL computation uses upstream floating-point precision and Money rounding")
        gaps[:] = list(dict.fromkeys(gaps))
        group["coverage"]["status"] = "source_matched" if not gaps else "ambiguous" if group.get("membership_ambiguous") else "incomplete"
        if not gaps and latest.get("native_total_pnl") is not None:
            group["actual_net"] = {"realized_pnl": latest["realized_pnl"], "unrealized_pnl": latest["unrealized_pnl"],
                "total_pnl": latest["native_total_pnl"], "basis": "Native accounting with sourced actual commissions; not broker statement or tax-lot performance"}
    values = list(groups.values())
    for group in values:
        overlaps = [other["lifecycle_id"] for other in values if other is not group
            and all(other["account_context"].get(key) == group["account_context"].get(key) for key in ("account_id", "broker_account_id", "endpoint", "mode"))
            and set(other["fill_ids"]).intersection(group["fill_ids"])]
        if overlaps:
            group["coverage"]["status"] = "ambiguous"
            group["coverage"]["gaps"].append("Fill membership overlaps another native lifecycle; resolve identity/reopen evidence before attributing results")
            group.update(ambiguous_lifecycle_ids=overlaps, actual_net=None)
    return {"captures": [{key: value for key, value in capture.items() if key != "report"} for capture in captures],
            "groups": values, "unattributed": unattributed, "aggregation": "No totals across lifecycle groups or decision references"}


def decisions(investor, journal, history, authority=None, position_groups=()):
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
        item["command_outcomes"] = [command_outcome(command, authority, position_groups) for command in linked]
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
            "command_outcomes": [command_outcome(command, authority, position_groups)], "executable": False})
    for item in result:
        item["position_outcome_ids"] = [group["lifecycle_id"] for group in position_groups if item["id"] in group["decision_links"]]
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
