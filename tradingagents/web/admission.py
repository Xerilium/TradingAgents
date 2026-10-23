"""Durable user approval, account-wide admission and native dispatch authority."""

import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from .investor import DEFAULT as INVESTOR_DEFAULT, RULES, decimal, digest, execution_costs, price_evidence, validated_replacement, remaining_quantity, broker_action_order, order_version, native_quantity_offset
from .linked_orders import native_type, contract_multiplier

DEFAULT = {"approvals": {}, "revocations": {}, "commands": {}, "account_versions": {},
           "native_reconstructions": {}, "option_instructions": {},
           "new_orders_blocked": False, "control_history": [], "exercise_authorizations": {}, "basket_executions": {},
           "recovery_required": True, "recovery_reason": "Fresh account reconciliation and outstanding-command rebuild required"}
ACTIVE = {"admitted_not_dispatched", "dispatch_intent", "submitting", "outcome_unknown", "accepted",
          "partially_filled", "cancel_pending", "replace_pending"}
TERMINAL = {"filled", "canceled", "rejected", "expired"}


def stamp():
    return datetime.now(UTC).isoformat()


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Authority timestamps require a time zone")
    return result


def account_version(runtime, symbols=()):
    from .investor import native_balance_binding
    def stable(value, path=()):
        if isinstance(value, dict):
            if "binding_native" in value and value.get("reconciliation_status") == "reconciled":
                value = {key: value["binding_native"] if key == "nautilus" else item for key, item in value.items() if key != "binding_native"}
            return {key: stable(item, path + (key,)) for key, item in value.items()
                    if key not in {"ts_init", "received_at", "checked_at", "observed_at"}
                    and not (key == "updated_at" and (not path or path[0] not in {"account", "positions", "orders"} or "nautilus" in path))}
        if isinstance(value, list):
            return [stable(item, path) for item in value]
        return value
    account, reconciliation = runtime.get("account") or {}, runtime.get("reconciliation") or {}
    position_keys = ("asset_id", "symbol", "asset_class", "exchange", "qty", "qty_available", "side")
    inputs = {
        "account": {key: account.get(key) for key in ("id", "status", "currency", "cash", "equity", "initial_margin", "maintenance_margin", "trading_blocked", "multiplier", "shorting_enabled", "options_approved_level", "options_trading_level", "options_buying_power", "account_blocked", "trade_suspended_by_user")},
        "profile_transition": {key: (runtime.get("profile_transition") or {}).get(key) for key in
            ("selected_profile", "native_account_type", "account_id", "endpoint", "native_epoch", "eligibility", "mapping_scope", "cash_balance_basis", "reported_account")},
        "native_epoch": runtime.get("native_epoch"),
        "native_balance_projection": native_balance_binding(runtime),
        "positions": sorted(({key: row.get(key) for key in position_keys} for row in runtime.get("positions") or []),
                            key=lambda row: (str(row["symbol"]), str(row["asset_id"]))),
        "orders": sorted(({key: row.get(key) for key in ("id", "client_order_id", "symbol", "asset_class", "position_intent", "side", "qty", "filled_qty", "type", "order_type", "order_class", "limit_price", "stop_price", "trail_price", "trail_percent", "time_in_force", "extended_hours", "status", "replaces", "replaced_by", "group_parent_id", "group_class", "group_role", "group_entry_status", "exit_reserved", "package_terms", "package_parent_id", "legs")} for row in runtime.get("orders") or []), key=lambda row: str(row["id"])),
        "reconciliation": {key: reconciliation.get(key) for key in ("status", "gaps", "positions_reconciled", "orders_reconciled", "broker_cash", "native_cash")},
        "option_contracts": {symbol: {key: item.get("option_contract", {}).get(key) for key in ("sha256", "mapping_version")}
            for symbol, item in runtime.get("market_data", {}).items() if item.get("option_contract")},
        "endpoint": runtime.get("endpoint"), "connection_session": runtime.get("connection_session")}
    if symbols:
        inputs["market_data"] = {symbol: runtime.get("market_data", {}).get(symbol) for symbol in sorted(set(symbols))}
        inputs["market_open"] = runtime.get("market_open")
    return digest(stable(inputs))


def invalidate(records):
    """Immutable approvals stay intact; revocations and unsent release events are appended."""
    state, investor = records["commands"], records["investor"]
    proposals = {p["id"]: p for p in investor["proposals"]}
    for identity, approval in state["approvals"].items():
        proposal = proposals.get(approval["proposal_id"])
        reason = None
        if not proposal or proposal["revision"] != approval["proposal_revision"] or proposal["status"] != "draft":
            reason = "Proposal changed, rejected, deferred or removed"
        elif investor["policy"]["revision"] != approval["policy_revision"]:
            reason = "Policy revision changed"
        elif approval.get("expires_at") and instant(approval["expires_at"]) <= datetime.now(UTC):
            reason = "Approval expired"
        elif state["account_versions"].get(approval["account_id"]) not in (None, approval["account_version"]):
            reason = "Relevant account/market observation changed"
        if reason and identity not in state["revocations"]:
            state["revocations"][identity] = {"at": stamp(), "reason": reason}
    for command in state["commands"].values():
        if command["approval_id"] in state["revocations"] and command["state"] == "admitted_not_dispatched":
            command.update(state="not_sent", cash_commitment="0", remaining_quantity="0")
            command["timeline"].append({"at": stamp(), "state": "not_sent", "reason": "Authority invalidated before any dispatch intent"})
    for group in state.get("basket_executions", {}).values():
        legs = [state["commands"][identity] for identity in group["command_ids"]]
        group["completion"] = [{"command_id": leg["id"], "state": leg["state"], "filled_quantity": leg["filled_quantity"],
                               "native_pending": bool(leg.get("native_pending_commitment"))} for leg in legs]
        if all(leg["state"] == "filled" and not leg.get("native_pending_commitment") for leg in legs):
            group["state"] = "completed"
        elif any(leg["state"] in {"not_sent", "outcome_unknown", "canceled", "rejected", "expired"}
                 or leg["approval_id"] in state["revocations"] and leg["state"] == "admitted_not_dispatched" for leg in legs):
            group["state"] = "review_required"
        elif group["state"] not in {"paused", "review_required"}:
            group["state"] = "running" if any(leg["state"] != "admitted_not_dispatched" for leg in legs) else "ready"
    return records


class CommandAdmission:
    def __init__(self, database, observation, *, execution_enabled=False, review_enabled=False, admission_enabled=False):
        self.database, self.observation, self.execution_enabled = database, observation, execution_enabled
        self.review_enabled, self.admission_enabled = review_enabled, admission_enabled

    def review_allowed(self):
        if not self.review_enabled:
            raise PermissionError("Browse-only mode does not permit approval or revocation records")

    def instruction_review(self, records, kind, symbol, constraints, identity=None):
        from .investor import exercise_readiness, working_commitments
        from .linked_orders import broker_position_quantity, option_contract
        if kind not in {"exercise", "do_not_exercise"}:
            raise ValueError("Choose Exercise all available or Request DNE")
        if not isinstance(constraints, dict):
            raise ValueError("Current configured instruction constraints are required")
        if any(decimal(constraints.get(key)) is None or decimal(constraints[key]) <= 0
               for key in ("account_max_age_seconds", "approval_max_age_seconds")):
            raise ValueError("Configured positive account and approval age limits are required")
        runtime = self.checked_observation(constraints)
        position = next((row for row in runtime.get("positions", []) if row.get("symbol") == symbol), None)
        if not position or position.get("asset_class") != "us_option" or position.get("import_error"):
            raise ValueError("An identified reconciled long option position is required")
        envelope = position.get("option_contract") or runtime.get("market_data", {}).get(symbol, {}).get("option_contract")
        contract = option_contract(envelope)
        if not envelope["source"].startswith(runtime.get("endpoint", "") + "/v2/options/contracts"):
            raise ValueError("Option metadata belongs to a different account mode/origin")
        quantity, available = broker_position_quantity(position), decimal(position.get("qty_available"))
        if contract["symbol"] != symbol or quantity <= 0 or quantity % 1 or available is None or available <= 0 or available > quantity or available % 1:
            raise ValueError("Current available whole long contracts are required")
        account, state = runtime["account"], records["commands"]
        if not runtime.get("connection_session") or not runtime.get("native_epoch") or not runtime.get("endpoint"):
            raise ValueError("Current account connection and native epoch are required")
        history = [{key: copy.deepcopy(row.get(key)) for key in ("id", "kind", "symbol", "account_id", "created_at", "state", "approval", "attempt", "interlock_release", "restore_uncertainty", "timeline")}
                   for key, row in state.setdefault("option_instructions", {}).items()
                   if key != identity and row["account_id"] == account["id"] and row["symbol"] == symbol]
        history.sort(key=lambda row: (row["created_at"], row["id"]))
        commitments, complete = working_commitments(runtime, state)
        local_sells = sum((item["remaining"] for item in commitments if item["symbol"] == symbol
            and item["side"] == "SELL" and item["command_ids"] and not item["order_ids"]), Decimal(0))
        blockers = []
        if kind == "exercise" and available - local_sells <= 0:
            blockers.append("Available long position is exhausted by known local sell commitments")
        if account.get("status") != "ACTIVE" or any(account.get(key) is True for key in ("account_blocked", "trade_suspended_by_user")):
            blockers.append("Broker account restrictions prohibit this instruction")
        if any(row["state"] in {"transport_intent", "transport_unknown"} and not row.get("interlock_release") for row in history):
            blockers.append("A prior instruction has an in-flight or unknown transport outcome")
        terms = {"asset_class": "us_option", "option_contract": envelope, "quantity": str(available)}
        readiness = exercise_readiness(terms, runtime, commands=state) if kind == "exercise" else None
        policy = records["investor"]["policy"]
        policy_review = {key: {"state": rule.get("state"), "applicability": "No supported instruction-specific model; no passing claim"}
                         for key, rule in policy.get("rules", {}).items() if rule.get("state") == "enabled"}
        if kind == "exercise":
            risk = runtime.get("native_risk", {})
            if risk.get("values", {}).get("trading_state") == "HALTED":
                blockers.append("Native trading is halted")
            loss_rule = policy.get("rules", {}).get("loss_limit_pct", {})
            pnl = [decimal(row.get("unrealized_pl")) for row in runtime.get("positions", [])]
            costs = [decimal(row.get("cost_basis")) for row in runtime.get("positions", [])]
            if loss_rule.get("state") == "enabled" and all(value is not None for value in pnl + costs) and sum(costs) > 0:
                if -sum(pnl) / sum(costs) * 100 > Decimal(loss_rule["value"]):
                    blockers.append("Configured current broker loss limit is exceeded")
                policy_review["loss_limit_pct"]["applicability"] = "Current broker aggregate unrealized loss / reported cost"
            reserve = policy.get("rules", {}).get("cash_reserve_pct", {})
            equity = decimal(account.get("equity"))
            cash = decimal(readiness.get("available")) if contract["type"] == "call" else decimal(account.get("cash"))
            if contract["type"] == "put" and cash is not None:
                cash -= sum((item["cash"] for item in commitments), Decimal(0))
            if reserve.get("state") == "enabled" and equity is not None and equity > 0 and cash is not None:
                remaining_cash = cash - Decimal(readiness["required"]) if contract["type"] == "call" else cash
                policy_review["cash_reserve_pct"].update(applicability="Call delivery or current put cash after known commitments, without crediting put proceeds", cash=str(remaining_cash))
                if remaining_cash / equity * 100 < Decimal(reserve["value"]):
                    blockers.append("Configured minimum cash reserve would be violated")
            # Reuse broker valuations and existing classification artifacts; unknown components are not zero.
            values = {row["symbol"]: decimal(row.get("market_value")) for row in runtime.get("positions", [])}
            delivery_values = dict(values)
            underlying = contract["underlying_symbol"]
            held = next((row for row in runtime.get("positions", []) if row["symbol"] == underlying), None)
            mark = decimal(held.get("current_price")) if held else None
            if mark is not None and mark > 0:
                delta = available * Decimal(contract["size"]) * mark * (1 if contract["type"] == "call" else -1)
                delivery_values[underlying] = (values.get(underlying) or Decimal(0)) + delta if not held or values.get(underlying) is not None else None
                delivery_values[symbol] = values.get(symbol) * (quantity - available) / quantity if values.get(symbol) is not None else None
            else:
                delivery_values[underlying] = None
            for key in ("max_position_pct", "max_gross_exposure_pct", "max_sector_pct"):
                rule = policy.get("rules", {}).get(key, {})
                if rule.get("state") != "enabled" or equity is None or equity <= 0:
                    continue
                scopes, references = [], {}
                for exposures in (values, delivery_values):
                    known_values = [abs(value) for value in exposures.values() if value is not None]
                    if key == "max_position_pct":
                        scopes.append(max(known_values, default=Decimal(0)))
                    elif key == "max_gross_exposure_pct":
                        scopes.append(sum(known_values))
                    else:
                        from .approval_review import read_artifact
                        sectors = {}
                        for name, value in exposures.items():
                            meta = records.get("stock_evidence", {}).get("observations", {}).get(name, {}).get("classification", {})
                            maximum = decimal(rule.get("max_classification_age_seconds"))
                            age = (datetime.now(UTC) - instant(meta["captured_at"])).total_seconds() if meta.get("captured_at") else None
                            source = read_artifact(self.database.path.parent, meta.get("artifact", {}))
                            sector = next((item.get("value") for item in (source or {}).get("records", []) if item.get("name") == "Sector"), None)
                            if value is not None and sector and rule.get("classification") == "provider_sector" and meta.get("status") == "available" and age is not None and maximum is not None and 0 <= age <= maximum:
                                sectors[sector] = sectors.get(sector, Decimal(0)) + abs(value)
                                references[name] = meta["artifact"]
                        scopes.append(max(sectors.values(), default=Decimal(0)))
                policy_review[key].update(applicability="Known current/delivery valuation lower bounds; incomplete inputs are not a passing claim", lower_bounds=[str(value) for value in scopes], source_references=references)
                if any(value / equity * 100 > Decimal(rule["value"]) for value in scopes):
                    blockers.append("Configured " + RULES[key] + " is exceeded by evidenced current/delivery exposure")
        facts = {"kind": kind, "symbol": symbol, "account_id": account["id"], "endpoint": runtime["endpoint"],
            "mode": runtime.get("connection_identity", {}).get("configured_mode"), "connection_session": runtime["connection_session"],
            "native_epoch": runtime["native_epoch"], "intent": "all_available", "option_contract": copy.deepcopy(envelope),
            "observed_quantity": str(quantity), "broker_available_quantity": str(available), "local_sell_commitment": str(local_sells),
            "review_available_quantity": str(available - local_sells), "observed_at": runtime["account_at"],
            "exercise_readiness": readiness, "policy": copy.deepcopy(policy), "policy_review": policy_review, "history": history,
            "commitments": json.loads(json.dumps(commitments, default=str)), "commitments_complete": complete,
            "limits": "No fixed-quantity broker parameter, atomic undo, cutoff guarantee or settlement confirmation; broker changes may race preflight"}
        history_hash = digest([row for row in history if row.get("attempt") or row["state"] == "transport_unknown"])
        binding = {"kind": kind, "symbol": symbol, "account_version": account_version(runtime), "native_epoch": runtime["native_epoch"],
            "contract_sha256": envelope["sha256"], "policy": policy, "constraints": constraints, "history_sha256": history_hash,
            "commitments": facts["commitments"], "policy_review": policy_review, "blockers": blockers}
        return {"facts": facts, "binding_sha256": digest(binding), "history_sha256": history_hash, "blockers": blockers}

    def preview_instruction(self, kind, symbol, constraints):
        from .stock_evidence import DEFAULT as EVIDENCE
        records = {"commands": self.database.read("commands", DEFAULT)["data"],
                   "investor": self.database.read("investor", INVESTOR_DEFAULT)["data"],
                   "stock_evidence": self.database.read("stock_evidence", EVIDENCE)["data"]}
        return self.instruction_review(records, kind, symbol, constraints)

    def option_instruction(self, action, *, actor, instruction_id=None, kind=None, symbol=None, reason="", constraints=None,
                           expected=None, binding_sha256=None, reviewed_unknowns=False):
        self.review_allowed()
        if not isinstance(expected, dict) or any(type(expected.get(key)) is not int for key in ("commands", "investor")):
            raise ValueError("Reload exact commands and investor revisions before changing instruction authority")
        if not actor or action not in {"prepare", "review", "approve", "release_interlock"}:
            raise ValueError("Explicit initiating session and instruction action are required")
        def change(records):
            instructions = records["commands"].setdefault("option_instructions", {})
            if action == "prepare":
                review = self.instruction_review(records, kind, symbol, constraints)
                facts, identity = review["facts"], str(uuid4())
                instructions[identity] = {key: facts[key] for key in ("kind", "symbol", "account_id", "endpoint", "mode", "connection_session", "native_epoch", "intent")}
                instructions[identity].update(id=identity, constraints=copy.deepcopy(constraints), created_at=stamp(), actor=actor,
                    reason=reason, state="prepared", review=None, approval=None, attempt=None, timeline=[])
                row = instructions[identity]
            else:
                row = instructions[instruction_id]
                if action == "release_interlock":
                    if row["state"] != "transport_unknown" or row.get("interlock_release") or not reason.strip():
                        raise ValueError("Only an unknown outcome permits a separate reasoned interlock release")
                    row["interlock_release"] = {"actor": actor, "reason": reason, "at": stamp()}
                else:
                    if row["state"] != "prepared":
                        raise ValueError("Instruction authority is one-shot; prepare a fresh instruction")
                    review = self.instruction_review(records, row["kind"], row["symbol"], row["constraints"], row["id"])
                    if any(row[key] != review["facts"][key] for key in ("account_id", "endpoint", "connection_session", "native_epoch")):
                        raise ValueError("Instruction account/session changed; prepare fresh authority")
                    if action == "review":
                        row["review"] = review
                    else:
                        if review["blockers"] or not row["review"] or binding_sha256 != row["review"]["binding_sha256"] or review["binding_sha256"] != binding_sha256:
                            raise ValueError("Review the exact current instruction facts and restrictions again")
                        unknowns = any(prior["state"] == "transport_unknown" for prior in review["facts"]["history"])
                        if unknowns and reviewed_unknowns is not True:
                            raise ValueError("Explicit review of prior unknown outcomes is required")
                        row.update(state="approved", approval={"actor": actor, "at": stamp(), "binding_sha256": binding_sha256,
                            "history_sha256": review["history_sha256"], "reviewed_unknowns": reviewed_unknowns,
                            "expires_at": (datetime.now(UTC) + timedelta(seconds=float(row["constraints"]["approval_max_age_seconds"]))).isoformat()})
            row["timeline"].append({"action": action, "actor": actor, "reason": reason, "at": stamp()})
        return self.transaction(change, expected=expected, evidence=True)

    def enabled(self):
        if self.execution_enabled is not True:
            raise ValueError("This session does not permit command execution")

    def transaction(self, change, *, expected=None, evidence=False):
        defaults = {"investor": INVESTOR_DEFAULT, "commands": DEFAULT}
        if evidence:
            from .market_history import DEFAULT as HISTORY
            from .stock_evidence import DEFAULT as EVIDENCE
            defaults.update(market_history=HISTORY, stock_evidence=EVIDENCE)
        return self.database.transact(defaults, change, expected=expected)

    def snapshot(self):
        if self.database.read("commands", DEFAULT)["data"]["approvals"]:
            self.observe_current(self.observation())
        record = self.database.read("commands", DEFAULT)
        record["data"].setdefault("new_orders_blocked", False)
        return {**record, "execution_enabled": self.execution_enabled, "review_enabled": self.review_enabled,
                "admission_enabled": self.admission_enabled,
                "approval_states": {identity: "invalidated" if identity in record["data"]["revocations"] else
                    "expired" if approval.get("expires_at") and instant(approval["expires_at"]) <= datetime.now(UTC) else
                    "admitted" if any(c["approval_id"] == identity for c in record["data"]["commands"].values()) else "approved_awaiting_admission"
                    for identity, approval in record["data"]["approvals"].items()}}

    def checked_observation(self, constraints):
        runtime = self.observation()
        if (runtime.get("status") != "connected" or runtime.get("reconciliation", {}).get("status") != "reconciled"
                or not runtime.get("account", {}).get("id") or not runtime.get("account_at") or runtime.get("local_record_error")):
            raise ValueError("Current complete Nautilus/broker reconciliation is required")
        if runtime["account"].get("trading_blocked") is True:
            raise ValueError("Alpaca reports trading blocked for this account")
        maximum = decimal(constraints.get("account_max_age_seconds"))
        age = Decimal(str((datetime.now(UTC) - instant(runtime["account_at"])).total_seconds()))
        if age < 0 or constraints.get("account_max_age_seconds") not in (None, "") and (maximum is None or maximum <= 0 or age > maximum):
            raise ValueError("Account observation exceeds the configured age limit")
        return runtime

    def observe_current(self, runtime):
        existing = self.database.read("commands", DEFAULT)["data"]
        if not existing["approvals"]:
            return
        def change(records):
            identity = (runtime.get("account") or {}).get("id")
            if identity:
                records["commands"]["account_versions"][identity] = account_version(runtime)
            if runtime.get("status") != "connected" or runtime.get("reconciliation", {}).get("status") != "reconciled":
                records["commands"].update(recovery_required=True, recovery_reason="Account source is stale, unavailable or incompletely reconciled")
            from .approval_review import evaluate
            proposals = {p["id"]: p for p in records["investor"]["proposals"]}
            for approval_id, approval in records["commands"]["approvals"].items():
                proposal = proposals.get(approval["proposal_id"])
                if approval_id in records["commands"]["revocations"] or proposal is None:
                    continue
                result = evaluate(proposal, records["investor"]["policy"], runtime, records["stock_evidence"],
                                  records["market_history"], records["commands"], approval["constraints"], self.database.path.parent)
                if not result["passed"] or result["binding_sha256"] != approval.get("evaluation", {}).get("binding_sha256"):
                    records["commands"]["revocations"][approval_id] = {"at": stamp(), "reason": "; ".join(result["blockers"]) if not result["passed"] else "Relevant account, policy, terms or required source contents changed"}
            return invalidate(records)
        return self.transaction(change, evidence=True)

    @staticmethod
    def proposal(records, identity):
        proposal = next((p for p in records["investor"]["proposals"] if p["id"] == identity), None)
        if not proposal or proposal["status"] != "draft":
            raise ValueError("Select an exact saved draft revision")
        return proposal

    def assess(self, records, proposal, runtime, constraints):
        from .approval_review import evaluate
        from .investor import impact
        result = evaluate(proposal, records["investor"]["policy"], runtime, records["stock_evidence"],
                          records["market_history"], records["commands"], constraints, self.database.path.parent)
        proposal.update(evidence_ready=result["evidence_ready"], risk_evaluation=result,
                        review_constraints=copy.deepcopy(constraints))
        proposal["impact"] = impact(proposal["terms"], runtime, records["investor"]["policy"]["rules"], commands=records["commands"])
        legacy = proposal["impact"]["conditions"]
        labels = tuple(RULES.values())
        proposal["impact"]["conditions"] = list(dict.fromkeys([condition for condition in legacy
            if not any(condition.startswith(label) for label in labels)] + result["blockers"]))
        return result

    @staticmethod
    def exact_revision(records, proposal, proposal_revision, policy_revision):
        if (type(proposal_revision) is not int or proposal["revision"] != proposal_revision
                or type(policy_revision) is not int or records["investor"]["policy"]["revision"] != policy_revision):
            raise ValueError("Proposal or policy revision changed; reload the exact terms before review")

    def evaluate_review(self, proposal_id, *, proposal_revision, policy_revision, constraints, expected):
        def change(records):
            proposal = self.proposal(records, proposal_id)
            self.exact_revision(records, proposal, proposal_revision, policy_revision)
            self.assess(records, proposal, self.observation(), constraints)
        return self.transaction(change, expected=expected, evidence=True)

    def approve(self, proposal_id, *, actor, reason, expires_at=None, constraints, proposal_revision, policy_revision, evaluation_binding_sha256, expected):
        self.review_allowed()
        if not actor:
            raise ValueError("Approval requires the initiating local session")
        ttl = decimal(constraints.get("approval_max_age_seconds"))
        expires = instant(expires_at) if expires_at else datetime.now(UTC) + timedelta(seconds=float(ttl)) if ttl is not None and ttl > 0 else None
        if expires and (expires <= datetime.now(UTC) or ttl is not None and Decimal(str((expires - datetime.now(UTC)).total_seconds())) > ttl):
            raise ValueError("Configured approval lifetime is exceeded")
        def change(records):
            proposal = self.proposal(records, proposal_id)
            self.exact_revision(records, proposal, proposal_revision, policy_revision)
            if not evaluation_binding_sha256 or proposal.get("risk_evaluation", {}).get("binding_sha256") != evaluation_binding_sha256:
                raise ValueError("Evaluate and inspect the exact saved revision before approving it")
            runtime = self.checked_observation(constraints)
            evaluation = self.assess(records, proposal, runtime, constraints)
            if evaluation["binding_sha256"] != evaluation_binding_sha256:
                raise ValueError("Review inputs or source observations changed; evaluate and inspect them again")
            if not evaluation["passed"]:
                raise ValueError("Approval blocked: " + "; ".join(evaluation["blockers"]))
            terms, policy = proposal["terms"], records["investor"]["policy"]
            if terms["account_id"] != runtime["account"]["id"] or proposal["policy_revision"] != policy["revision"]:
                raise ValueError("Proposal account or policy revision differs from current review")
            event = price_evidence({**terms, "order_type": "MARKET"}, runtime)["ts_event"]
            state = records["commands"]
            version = account_version(runtime)
            state["account_versions"][terms["account_id"]] = version
            invalidate(records)
            identity = str(uuid4())
            mode = (runtime.get("connection_identity") or {}).get("observed_mode")
            context = {"endpoint": runtime.get("endpoint"), "mode": mode, "account_id": terms["account_id"],
                       "connection_session": runtime.get("connection_session")}
            if mode not in {"paper", "live"} or {"paper": "https://paper-api.alpaca.markets", "live": "https://api.alpaca.markets"}[mode] != context["endpoint"] or not context["connection_session"]:
                context = None  # Legacy/unavailable observations do not establish historical mode.
            state["approvals"][identity] = {"id": identity, "proposal_id": proposal_id,
                "connection_context": context,
                "proposal_revision": proposal["revision"], "terms_sha256": proposal["terms_sha256"],
                "terms": copy.deepcopy(terms), "policy_revision": policy["revision"], "account_id": terms["account_id"],
                "instrument_id": terms["instrument_id"], "account_version": version,
                "account_observed_at": runtime["account_at"], "market_event_ns": event,
                "constraints": copy.deepcopy(constraints), "actor": actor, "reason": reason,
                "evaluation": copy.deepcopy(evaluation), "evaluation_binding_sha256": evaluation["binding_sha256"],
                "approved_at": stamp(), "expires_at": expires.isoformat() if expires else ""}
        return self.transaction(change, expected=expected, evidence=True)

    def revoke(self, approval_id, *, actor, reason, expected):
        self.review_allowed()
        if not actor:
            raise ValueError("Revocation requires the initiating local session")
        def change(records):
            state = records["commands"]
            if approval_id not in state["approvals"]:
                raise ValueError("Approval record was not found")
            state["revocations"].setdefault(approval_id, {"actor": actor, "reason": reason, "at": stamp()})
            invalidate(records)
        return self.transaction(change, expected=expected)

    def admit(self, approval_id, *, expected=None):
        if not self.admission_enabled:
            raise PermissionError("Browse-only mode does not permit command admission")
        return self.transaction(lambda records: self._admit(records, approval_id), expected=expected, evidence=True)

    def _admit(self, records, approval_id):
        state = records["commands"]
        if state.get("new_orders_blocked", False):
            raise ValueError("Account-wide block-new-orders is active")
        approval = state["approvals"][approval_id]
        runtime = self.checked_observation(approval["constraints"])
        state["account_versions"][runtime["account"]["id"]] = account_version(runtime)
        invalidate(records)
        if state["recovery_required"] or approval_id in state["revocations"]:
            raise ValueError("Recovery or invalidated approval blocks admission")
        if any(c["approval_id"] == approval_id for c in state["commands"].values()):
            return records
        proposal = self.proposal(records, approval["proposal_id"])
        evaluation = self.assess(records, proposal, runtime, approval["constraints"])
        if not evaluation["passed"] or evaluation["binding_sha256"] != approval.get("evaluation_binding_sha256"):
            raise ValueError("Evidence, policy or source observations changed after approval; renewed exact review is required")
        terms = proposal["terms"]
        risk = proposal.get("risk_evaluation", {})
        if risk.get("passed") is not True or risk.get("account_version") != approval.get("evaluation", {}).get("account_version") or risk.get("policy_revision") != approval["policy_revision"]:
            raise ValueError("Current source-bound loss/scenario and evidence review is unavailable")
        if any(c["state"] in {"outcome_unknown", "dispatch_intent", "submitting", "replace_pending", "cancel_pending"}
               and c["account_id"] == terms["account_id"] and not (
                   c["state"] == "submitting" and not c.get("pending_action")
                   and (terms.get("replacement") or {}).get("order_id") in c.get("broker_order_ids", []))
               for c in state["commands"].values()):
            raise ValueError("Unresolved command outcome blocks conflicting account admission")
        cap, fees = execution_costs(terms, runtime, approval["constraints"])
        quantity = remaining_quantity(terms)
        if cap is None or quantity is None:
            raise ValueError("Required price or remaining quantity is unavailable")
        validated_replacement(terms, runtime)
        reserve = (quantity * cap * contract_multiplier(terms) if terms["side"] == "BUY" else Decimal(0)) + (fees if fees is not None else Decimal(0))
        collateral = Decimal(0)
        if terms.get("execution_profile") == "bounded_risk_spread_v1":
            from .investor import spread_risk
            spread = spread_risk(terms, runtime, state)
            obligation = decimal(spread["net_package_obligation_before_costs"])
            if spread["blockers"] or obligation is None:
                raise ValueError("Current bounded-risk collateral/protection evidence is unavailable")
            collateral = max(Decimal(0), obligation - quantity * cap * contract_multiplier(terms))
            reserve += collateral
        if (terms.get("replacement") or {}).get("contingent_group"):
            reserve = Decimal(0)
        identity = str(uuid4())
        state["commands"][identity] = {"id": identity, "client_order_id": "ta-" + uuid4().hex,
            "proposal_id": proposal["id"], "proposal_revision": proposal["revision"], "approval_id": approval_id,
            "policy_revision": approval["policy_revision"], "account_id": terms["account_id"],
            "account_version": approval["account_version"], "instrument_id": terms["instrument_id"],
            "connection_context": copy.deepcopy(approval.get("connection_context")),
            "symbol": terms["symbol"], "side": terms["side"], "terms": copy.deepcopy(terms),
            "terms_sha256": proposal["terms_sha256"], "state": "admitted_not_dispatched", "dispatch_intent_at": None,
            "transport_attempt": {"version": 1, "state": "not_started"},
            "remaining_quantity": str(quantity), "filled_quantity": str((terms.get("replacement") or {}).get("filled_quantity", "0")), "cash_commitment": str(reserve),
            "price_cap": str(cap), "fee_commitment": str(fees) if fees is not None else None,
            "cash_commitment_basis": "Principal plus known/configured fee amount; unknown actual fees are excluded, not zero", "broker_order_ids": [], "fill_ids": [], "event_ids": [],
            "timeline": [{"at": stamp(), "state": "admitted_not_dispatched", "reason": "Resources reserved transactionally; transport has not been called"}]}
        if terms.get("execution_profile") == "bounded_risk_spread_v1":
            from .investor import native_balance_binding
            state["commands"][identity].update(collateral_commitment=str(collateral), collateral_evidence=spread,
                native_balance_projection=native_balance_binding(runtime),
                cash_commitment_basis="One modeled same-package net collateral/premium obligation plus declared costs; not broker-reported margin")
        if terms.get("replacement_funding_basis"):
            from .investor import replacement_funding_route

            route = replacement_funding_route(terms)
            material = evaluation["bindings"].get("broker_reservation_validation")
            if not material or material.get("route_eligible") is not True or any(material.get(key) != value for key, value in route.items()):
                raise ValueError("Exact approved broker-owned incremental reservation route is unavailable")
            state["commands"][identity].update(replacement_funding_basis=route["version"], broker_reservation_validation=copy.deepcopy(material))
        baseline = state.get("native_reconstructions", {}).get(terms["instrument_id"])
        if baseline and baseline.get("state") == "confirmed" and baseline.get("native_epoch") == state.get("native_epoch"):
            state["commands"][identity]["reconstruction_parent"] = {key: copy.deepcopy(baseline[key])
                for key in ("receipt", "account_id", "native_epoch", "instrument_id")}
        if terms.get("order_class") == "mleg":
            from .linked_orders import package_valuation_key
            state["commands"][identity].update(
                package_valuation_binding_sha256=package_valuation_key(evaluation["bindings"]["native_package_valuation"]),
                package_valuation_receipt=copy.deepcopy(evaluation["policy_scenarios"]["native_package_valuation"]["receipt"]))
            state["commands"][identity]["reconstruction_parents"] = {
                leg["instrument_id"]: {key: copy.deepcopy(baseline[key]) for key in ("receipt", "account_id", "native_epoch", "instrument_id")}
                for leg in terms["legs"] for baseline in [state.get("native_reconstructions", {}).get(leg["instrument_id"], {})]
                if baseline.get("state") == "confirmed" and baseline.get("native_epoch") == state.get("native_epoch")}
        if terms.get("replacement"):
            parent = next((c for c in state["commands"].values() if c["id"] != identity and
                terms["replacement"]["order_id"] in c.get("broker_order_ids", [])), None)
            if parent:
                state["commands"][identity]["parent_command_id"] = parent["id"]
        return records

    def _dispatch_intent(self, records, command_id):
        state = records["commands"]
        command = state["commands"][command_id]
        if command.get("origin") in {"external_broker", "linked_broker"}:
            raise ValueError("An imported broker order has no app submission authority")
        if command["terms"].get("replacement"):
            raise ValueError("Replacement terms can only be sent through Replace on their exact predecessor")
        approval = state["approvals"][command["approval_id"]]
        runtime = self.checked_observation(approval["constraints"])
        state["account_versions"][runtime["account"]["id"]] = account_version(runtime)
        invalidate(records)
        if state["recovery_required"] or command["state"] != "admitted_not_dispatched" or command["approval_id"] in state["revocations"]:
            raise ValueError("Only a reconciled, current, admitted and never-dispatched command can acquire dispatch intent")
        self.require_dependencies(state, command)
        if state.get("new_orders_blocked", False):
            raise ValueError("Account-wide block-new-orders is active")
        command.update(state="dispatch_intent", dispatch_intent_at=stamp(),
                       transport_attempt={"version": 1, "state": "not_started"})
        command["timeline"].append({"at": stamp(), "state": "dispatch_intent", "reason": "Durable intent precedes any transport call"})

    def dispatch_intent(self, command_id, exercise_id=None, *, expected=None):
        self.enabled()
        return self.transaction(lambda records: self._dispatch_intent(records, command_id), expected=expected)

    def submit_approved(self, approval_id, *, expected):
        self.enabled()
        if not self.admission_enabled:
            raise PermissionError("This session does not permit command admission")
        def change(records):
            self._admit(records, approval_id)
            command = next(item for item in records["commands"]["commands"].values() if item["approval_id"] == approval_id)
            self._dispatch_intent(records, command["id"])
        result = self.transaction(change, expected=expected, evidence=True)
        return next(item["id"] for item in result["commands"]["data"]["commands"].values() if item["approval_id"] == approval_id)

    def recover(self):
        def change(records):
            state = records["commands"]
            state.update(recovery_required=True, recovery_reason="Restart requires authoritative identity reconciliation; unknown outcomes retain commitments")
            for command in state["commands"].values():
                if command["state"] in {"dispatch_intent", "submitting", "cancel_pending", "replace_pending"}:
                    command["state"] = "outcome_unknown"
                    command["timeline"].append({"at": stamp(), "state": "outcome_unknown", "reason": "Restart after possible transport I/O; no automatic resubmit"})
            return invalidate(records)
        return self.transaction(change)

    def authorize_action(self, command_id, *, kind, actor, reason, broker_order_id, expires_at=None, replacement_command_id=None, replacement_approval_id=None, expected=None, exercise_id=None, broker_order_version=None):
        self.enabled()
        if kind not in {"cancel", "replace"} or not actor:
            raise ValueError("Authorize a single-order action from the initiating local session")
        def change(records):
            state = records["commands"]
            runtime = self.observation()
            order = broker_action_order(runtime, broker_order_id, broker_order_version)
            if not broker_order_version:
                raise ValueError("Reload the exact broker order version before authorizing its action")
            command = state["commands"].get(command_id) if command_id else next((c for c in state["commands"].values()
                if c["account_id"] == runtime["account"]["id"] and broker_order_id in c.get("broker_order_ids", [])), None)
            if command is None:
                identity = str(uuid4())
                terms = {"account_id": runtime["account"]["id"], "symbol": order["symbol"],
                    "instrument_id": order["nautilus"]["instrument_id"], "side": order["side"].upper(),
                    "quantity": str(order["qty"]), "order_type": native_type(order.get("type", order.get("order_type"))),
                    "limit_price": order.get("limit_price"), "stop_price": None if order.get("type") == "trailing_stop" else order.get("stop_price"),
                    "time_in_force": order["time_in_force"].upper(), "session": "extended" if order["extended_hours"] else "regular",
                    "rationale": "", "research": None}
                if order.get("type") == "trailing_stop":
                    terms.update({key: order[key] for key in ("trail_price", "trail_percent") if order.get(key) is not None})
                if order.get("asset_class") == "us_option":
                    terms.update(asset_class="us_option", currency="USD", option_contract=copy.deepcopy(order["option_contract"]), position_intent=order.get("position_intent"))
                cap = price_evidence(terms, runtime)["price"]
                remaining = decimal(order["qty"]) - decimal(order["filled_qty"])
                command = {"id": identity, "origin": "external_broker", "submission_authority": False,
                    "proposal_id": None, "proposal_revision": None, "policy_revision": None, "approval_id": None,
                    "account_id": terms["account_id"], "account_version": account_version(runtime),
                    "instrument_id": terms["instrument_id"], "symbol": terms["symbol"], "side": terms["side"],
                    "terms": terms, "terms_sha256": digest(terms), "client_order_id": order["client_order_id"],
                    "native_client_order_id": order["nautilus"]["client_order_id"],
                    "native_quantity_offset": str(native_quantity_offset(order)),
                    "native_replacement_quantity_binding": copy.deepcopy(order.get("native_replacement_quantity_binding")),
                    "state": "submitting" if order["status"] == "pending_new" else "partially_filled" if decimal(order["filled_qty"]) else "accepted",
                    "dispatch_intent_at": None, "transport_attempt": {"version": 1, "state": "external_submission"},
                    "filled_quantity": str(order["filled_qty"]), "remaining_quantity": str(remaining),
                    "price_cap": str(cap) if cap is not None else None, "fee_commitment": None,
                    "cash_commitment": str(remaining * cap * contract_multiplier(terms)) if terms["side"] == "BUY" and cap is not None else "0" if terms["side"] == "SELL" else None,
                    "cash_commitment_basis": "Retained broker order principal estimate; unknown actual fees excluded",
                    "broker_order_ids": [broker_order_id], "fill_ids": [], "event_ids": [],
                    "source_observation": {"order": copy.deepcopy(order), "order_version": order_version(order),
                        "account_observed_at": runtime.get("account_at"), "native_epoch": runtime.get("native_epoch")},
                    "timeline": [{"at": stamp(), "state": order["status"], "reason": "Observed external broker order; no app submission or original approval is claimed"}]}
                state["commands"][identity] = command
            observed_pending = command["state"] == "submitting" and order["status"] == "pending_new"
            if (command["state"] not in {"accepted", "partially_filled"} and not observed_pending
                    or broker_order_id not in command["broker_order_ids"] or command["account_id"] != runtime["account"]["id"]
                    or command["client_order_id"] != order["client_order_id"]
                    or decimal(command["filled_quantity"]) != decimal(order["filled_qty"])):
                raise ValueError("Authorize the exact authoritative working order identity")
            if command.get("pending_action") and command["pending_action"].get("state") not in {"not_sent", "completed"}:
                raise ValueError("An existing action requires authoritative resolution")
            command.update(native_quantity_offset=str(native_quantity_offset(order)),
                native_replacement_quantity_binding=copy.deepcopy(order.get("native_replacement_quantity_binding")))
            action = {"id": str(uuid4()), "state": "authorized",
                      "native_quantity_offset": command["native_quantity_offset"],
                      "native_replacement_quantity_binding": copy.deepcopy(command["native_replacement_quantity_binding"]),
                      "transport_attempt": {"version": 1, "state": "not_started"}, "kind": kind, "actor": actor, "reason": reason, "broker_order_id": broker_order_id,
                      "broker_order_version": order_version(order), "filled_quantity": str(order["filled_qty"]), "intent_at": stamp()}
            approval = {"constraints": {}}
            if kind == "replace":
                from .linked_orders import amendment_supported
                amendment_supported(order)
                if replacement_approval_id:
                    self._admit(records, replacement_approval_id)
                    child = next(item for item in state["commands"].values() if item["approval_id"] == replacement_approval_id)
                else:
                    child = state["commands"][replacement_command_id]
                approval = state["approvals"][child["approval_id"]]
                runtime = self.checked_observation(approval["constraints"])
                state["account_versions"][approval["account_id"]] = account_version(runtime)
                invalidate(records)
                if (child["state"] != "admitted_not_dispatched" or child["account_id"] != command["account_id"]
                        or child["instrument_id"] != command["instrument_id"] or child["side"] != command["side"]
                        or child["terms"]["order_type"] != command["terms"]["order_type"] or state["recovery_required"]
                        or child["approval_id"] in state["revocations"]):
                    raise ValueError("Replacement requires separately reviewed exact terms and current reservations")
                if state.get("new_orders_blocked", False):
                    raise ValueError("Account-wide block-new-orders prevents replacement")
                predecessor = validated_replacement(child["terms"], runtime)
                if predecessor is None or predecessor["id"] != broker_order_id:
                    raise ValueError("Approved replacement must bind this exact predecessor")
                if decimal(command["filled_quantity"]) != decimal(child["terms"]["replacement"]["filled_quantity"]):
                    raise ValueError("Predecessor filled quantity changed after replacement review")
                # Alternative reservations remain retained at max(old, new) until resolution.
                child.update(parent_command_id=command["id"], native_client_order_id=command.get("native_client_order_id", command["client_order_id"]),
                             state="dispatch_intent", dispatch_intent_at=stamp(),
                             transport_attempt={"version": 1, "state": "not_started"})
                for key in ("linked_exit", "linked_entry_command_id", "linked_role"):
                    if key in command:
                        child[key] = command[key]
                if command.get("linked_group_owner_id") or command["side"] == "SELL" and command["terms"].get("exit_plan"):
                    child["linked_group_owner_id"] = command.get("linked_group_owner_id", command["id"])
                action["replacement_command_id"] = child["id"]
            ttl = decimal(approval["constraints"].get("approval_max_age_seconds"))
            bounds = [instant(value) for value in (expires_at, approval.get("expires_at") if kind == "replace" else None) if value]
            if ttl is not None and ttl > 0:
                bounds.append(datetime.now(UTC) + timedelta(seconds=float(ttl)))
            expires = min(bounds) if bounds else None
            if expires and expires <= datetime.now(UTC):
                raise ValueError("Configured action authorization lifetime has expired")
            action["expires_at"] = expires.isoformat() if expires else ""
            command["pending_action"] = action
            command["timeline"].append({"at": stamp(), "state": kind + "_intent", "action": copy.deepcopy(action)})
        result = self.transaction(change, expected=expected, evidence=bool(replacement_approval_id))
        return next(c["id"] for c in result["commands"]["data"]["commands"].values()
                    if c.get("pending_action", {}).get("broker_order_id") == broker_order_id
                    and c["pending_action"].get("kind") == kind and c["pending_action"].get("state") == "authorized")

    def control(self, blocked, *, actor, reason, expected):
        if type(blocked) is not bool or not actor:
            raise ValueError("Explicit block state and initiating local session are required")
        if not blocked:
            self.review_allowed()
        def change(records):
            state = records["commands"]
            state["new_orders_blocked"] = blocked
            state.setdefault("control_history", []).append({"at": stamp(), "blocked": blocked, "action": "pause" if blocked else "resume", "actor": actor, "note": reason})
        return self.transaction(change, expected=expected)

    def exercise(self, request, *, expected):
        self.enabled()
        self.review_allowed()
        def change(records):
            state = records["commands"]
            identity = request.get("id")
            if request.get("action") == "revoke":
                value = state.setdefault("exercise_authorizations", {})[identity]
                if not request.get("actor") or not request.get("reason"):
                    raise ValueError("Revocation requires human identity and reason")
                value["revocation"] = {"at": stamp(), "actor": request["actor"], "reason": request["reason"]}
                return
            identities, operations = request.get("command_ids"), request.get("operations")
            if (not isinstance(identities, list) or not 1 <= len(identities) <= 100 or len(set(identities)) != len(identities)
                    or not isinstance(operations, list) or not operations or set(operations) - {"submit", "cancel", "replace"}
                    or not request.get("actor") or not request.get("reason") or request.get("confirmation") != "AUTHORIZE PAPER EXERCISE"):
                raise ValueError("Authorize exact commands, operations, paper scope, actor, reason and confirmation")
            expires = instant(request["expires_at"])
            commands = [state["commands"][item] for item in identities]
            if expires <= datetime.now(UTC) or len({item["account_id"] for item in commands}) != 1:
                raise ValueError("One account and a future exercise expiry are required")
            identity = str(uuid4())
            state.setdefault("exercise_authorizations", {})[identity] = {
                "id": identity, "account_id": commands[0]["account_id"], "paper": True,
                "commands": {item["id"]: item["terms_sha256"] for item in commands},
                "operations": operations, "actor": request["actor"], "reason": request["reason"],
                "created_at": stamp(), "expires_at": expires.isoformat()}
        return self.transaction(change, expected=expected)

    @staticmethod
    def require_exercise(state, command, identity, operation):
        value = state.get("exercise_authorizations", {}).get(identity, {})
        if (value.get("paper") is not True or value.get("revocation") or not value.get("actor")
                or value.get("account_id") != command["account_id"] or operation not in value.get("operations", [])
                or value.get("commands", {}).get(command["id"]) != command["terms_sha256"]
                or instant(value["expires_at"]) <= datetime.now(UTC)):
            raise ValueError("Separate current human paper-exercise authorization is required for these exact command terms")
        return value

    @staticmethod
    def require_dependencies(state, command):
        group = state.get("basket_executions", {}).get(command.get("basket_execution_id"))
        if not group:
            return
        if group["state"] in {"paused", "review_required"}:
            raise ValueError("Basket is paused for explicit review")
        for identity in command.get("depends_on", []):
            prior = state["commands"][identity]
            if prior["state"] != "filled" or prior.get("native_pending_commitment") or not prior["broker_order_ids"] or not prior["fill_ids"]:
                raise ValueError("Basket dependency needs authoritative full completion; existing commitments remain retained")

    def transport_boundary(self, identity, operation):
        self.enabled()
        def change(records):
            state = records["commands"]
            command = state["commands"][identity]
            action = command if operation == "submit" else command["pending_action"]
            if operation != "submit":
                current_order = broker_action_order(self.observation(), action["broker_order_id"], action.get("broker_order_version"))
                if decimal(current_order["filled_qty"]) != decimal(action.get("filled_quantity")):
                    raise ValueError("Observed cumulative fills changed after action authorization")
            if operation != "cancel":
                target = command if operation == "submit" else state["commands"][action["replacement_command_id"]]
                approval = state["approvals"][target["approval_id"]]
                runtime = self.checked_observation(approval["constraints"])
                state["account_versions"][approval["account_id"]] = account_version(runtime)
                invalidate(records)
                if (state["recovery_required"] or target["approval_id"] in state["revocations"]
                        or target["state"] not in {"dispatch_intent", "submitting"}
                        or account_version(runtime) != target["account_version"]):
                    raise ValueError("Current exact authority is required immediately before network I/O")
                proposal = self.proposal(records, approval["proposal_id"])
                evaluation = self.assess(records, proposal, runtime, approval["constraints"])
                if not evaluation["passed"] or evaluation["binding_sha256"] != approval.get("evaluation_binding_sha256"):
                    raise ValueError("Required current order conditions changed before transport")
                if (target.get("replacement_funding_basis") != target["terms"].get("replacement_funding_basis")
                        or target.get("broker_reservation_validation") != evaluation["bindings"].get("broker_reservation_validation")):
                    raise ValueError("Exact broker reservation validation basis changed before transport")
                cap, fee = execution_costs(target["terms"], runtime, approval["constraints"])
                remaining = remaining_quantity(target["terms"])
                if cap is None or remaining is None:
                    raise ValueError("Current price or remaining quantity is unavailable before transport")
                target.update(price_cap=str(cap), cash_commitment=str(
                    (remaining * cap * contract_multiplier(target["terms"]) if target["side"] == "BUY" else Decimal(0)) + (fee if fee is not None else Decimal(0))
                    + Decimal(target.get("collateral_commitment", "0"))))
                if (target["terms"].get("replacement") or {}).get("contingent_group"):
                    target["cash_commitment"] = "0"
                if operation == "submit" and target["terms"].get("replacement"):
                    raise ValueError("Replacement authority cannot submit a new order")
                if operation == "replace":
                    predecessor = validated_replacement(target["terms"], runtime)
                    if predecessor is None or predecessor["id"] != action["broker_order_id"]:
                        raise ValueError("Exact replacement predecessor changed before transport")
                if state.get("new_orders_blocked", False):
                    raise ValueError("Account-wide block-new-orders is active")
                self.require_dependencies(state, command)
            if operation != "submit" and action.get("expires_at") and instant(action["expires_at"]) <= datetime.now(UTC):
                raise ValueError("Action authorization expired")
            attempt = action.get("transport_attempt", {})
            if attempt != {"version": 1, "state": "not_started"}:
                raise ValueError("Transport attempt already started or has no proven local boundary")
            attempt.update(state="started", started_at=stamp(), native_epoch=state.get("native_epoch"), operation=operation)
            if operation == "replace":
                target["transport_attempt"] = copy.deepcopy(attempt)
        return self.transaction(change, evidence=True)

    def resolve_never_dispatched(self, identity, operation="submit", *, expected=None):
        """Only the versioned durable local boundary can prove absence of network I/O."""
        if operation not in {"submit", "cancel", "replace"}:
            raise ValueError("Choose the exact supported operation")
        def change(records):
            state = records["commands"]
            command = state["commands"][identity]
            action = command if operation == "submit" else command.get("pending_action", {})
            if operation != "submit" and action.get("kind") != operation:
                raise ValueError("Pending action identity differs")
            if action.get("transport_attempt") != {"version": 1, "state": "not_started"}:
                raise ValueError("Durable facts do not prove this operation never reached transport")
            if operation == "submit" and (command["broker_order_ids"] or command["fill_ids"] or command.get("native_deliveries")):
                raise ValueError("Broker/native evidence prevents a never-dispatched resolution")
            action["transport_attempt"].update(state="not_sent", resolved_at=stamp())
            if operation == "submit":
                command.update(state="not_sent", cash_commitment="0", remaining_quantity="0")
                command.pop("native_pending_commitment", None)
                state["revocations"].setdefault(command["approval_id"], {"at": stamp(), "reason": "Never-dispatched command resolved; new attempt requires renewed exact approval"})
            else:
                action["state"] = "not_sent"
                if operation == "replace":
                    child = state["commands"][action["replacement_command_id"]]
                    if child.get("transport_attempt") != {"version": 1, "state": "not_started"}:
                        raise ValueError("Replacement child may have reached transport")
                    child.update(state="not_sent", cash_commitment="0", remaining_quantity="0")
                    child.pop("native_pending_commitment", None)
                    state["revocations"].setdefault(child["approval_id"], {"at": stamp(), "reason": "Replacement never dispatched"})
                # Do not infer the current broker state or release the original order.
                state.update(recovery_required=True, recovery_reason="Action never dispatched; reconcile the existing order")
            command["timeline"].append({"at": stamp(), "state": "not_sent" if operation == "submit" else operation + "_not_sent",
                                        "reason": "Versioned durable transport boundary never started"})
        return self.transaction(change, expected=expected)

    def basket_admit(self, request, *, expected, dispatch=False):
        if dispatch:
            self.enabled()
        if not self.admission_enabled:
            raise PermissionError("Browse-only mode does not permit basket admission")
        def change(records):
            state = records["commands"]
            basket = next(item for item in records["investor"]["baskets"] if item["id"] == request["basket_id"])
            legs = request.get("legs")
            if (basket["revision"] != request.get("basket_revision") or basket["status"] != "draft"
                    or not isinstance(legs, list) or not legs or len(legs) > 100
                    or {item["proposal_id"] for item in legs} != set(basket["linked_proposal_ids"])
                    or len(legs) != len(basket["linked_proposal_ids"])
                    or not request.get("actor")):
                raise ValueError("Select every exact current basket leg with its approval and initiating local session")
            if any(group["basket_id"] == basket["id"] and group["basket_revision"] == basket["revision"]
                   for group in state.get("basket_executions", {}).values()):
                raise ValueError("This basket revision already has an execution plan; review it before creating revised proposals")
            identity, command_ids, mapped = str(uuid4()), [], {}
            for leg in legs:
                approval = state["approvals"][leg["approval_id"]]
                frozen = next(item for item in basket["preview"]["legs"] if item["proposal_id"] == leg["proposal_id"])
                proposal = self.proposal(records, leg["proposal_id"])
                if (digest(frozen["terms"]) != proposal["terms_sha256"] or approval["proposal_id"] != proposal["id"] or approval["proposal_revision"] != leg.get("proposal_revision")
                        or proposal["revision"] != leg.get("proposal_revision")
                        or approval["terms_sha256"] != leg.get("terms_sha256")
                        or any(item not in mapped for item in leg.get("depends_on", []))
                        or any(item["approval_id"] == approval["id"] for item in state["commands"].values())):
                    raise ValueError("Each leg needs unused exact approval and dependencies on preceding legs")
                if proposal["terms"].get("replacement"):
                    raise ValueError("Replacement orders use their exact predecessor action, not basket Submit")
                self._admit(records, approval["id"])
                command = next(item for item in state["commands"].values() if item["approval_id"] == approval["id"])
                command.update(basket_execution_id=identity, depends_on=[mapped[item] for item in leg.get("depends_on", [])])
                mapped[proposal["id"]] = command["id"]
                command_ids.append(command["id"])
            state.setdefault("basket_executions", {})[identity] = {
                "id": identity, "basket_id": basket["id"], "basket_revision": basket["revision"],
                "state": "ready", "command_ids": command_ids, "frozen_legs": copy.deepcopy(legs),
                "actor": request["actor"], "reason": request["reason"], "created_at": stamp(),
                "non_atomic": True, "history": []}
            if dispatch:
                self._dispatch_intent(records, command_ids[0])
        return self.transaction(change, expected=expected, evidence=True)

    def basket_control(self, identity, *, paused, actor, reason, expected):
        self.review_allowed()
        if type(paused) is not bool or not actor:
            raise ValueError("Explicit basket pause/review decision and initiating local session are required")
        def change(records):
            invalidate(records)
            group = records["commands"]["basket_executions"][identity]
            if not paused and any(records["commands"]["commands"][key]["state"] in {"not_sent", "outcome_unknown", "rejected", "canceled", "expired"}
                    or records["commands"]["commands"][key]["approval_id"] in records["commands"]["revocations"]
                    and records["commands"]["commands"][key]["state"] == "admitted_not_dispatched" for key in group["command_ids"]):
                raise ValueError("Basket needs newly reviewed proposals and approvals; a resume cannot revive invalid authority")
            group["state"] = "paused" if paused else "ready"
            group["history"].append({"at": stamp(), "actor": actor, "reason": reason, "state": group["state"]})
        return self.transaction(change, expected=expected)

    def apply_report(self, command_id, report):
        """Later adapter supplies identity-bound, authoritative reports with immutable receipt refs."""
        def change(records):
            state = records["commands"]
            command = state["commands"][command_id]
            if (report.get("authoritative") is not True or not report.get("event_id") or not report.get("receipt")
                    or report.get("account_id") != command["account_id"] or report.get("client_order_id") != command["client_order_id"]
                    or report.get("instrument_id") != command["instrument_id"]):
                raise ValueError("Authoritative command/account/instrument identity and source receipt are required")
            if report["event_id"] in command["event_ids"]:
                if command.get("event_digests", {}).get(report["event_id"]) not in (None, digest(report)):
                    state.update(recovery_required=True, recovery_reason="Conflicting contents for an authoritative event identity")
                    command["timeline"].append({"at": stamp(), "reason": "Conflicting duplicate event retained", "report": copy.deepcopy(report)})
                return records
            filled = decimal(report.get("filled_quantity"))
            previous, total = Decimal(command["filled_quantity"]), Decimal(command.get("broker_group_quantity", command["terms"]["quantity"]))
            if filled is None or not previous <= filled <= total:
                command["timeline"].append({"at": stamp(), "reason": "Out-of-order or inconsistent cumulative fill; retained for reconciliation", "report": copy.deepcopy(report)})
                state.update(recovery_required=True, recovery_reason="Inconsistent cumulative fill report")
                return records
            status = report.get("state")
            if status not in TERMINAL | {"submitting", "accepted", "partially_filled", "cancel_pending", "replace_pending", "outcome_unknown"}:
                raise ValueError("Unsupported authoritative lifecycle state")
            if command["state"] in TERMINAL and status not in TERMINAL:
                command["timeline"].append({"at": stamp(), "reason": "Late nonterminal event retained without reviving terminal authority", "report": copy.deepcopy(report)})
                command["event_ids"].append(report["event_id"])
                return records
            if status == "filled" and filled != total or status == "rejected" and filled:
                raise ValueError("Terminal state conflicts with cumulative filled quantity")
            if status == "accepted" and 0 < filled < total:
                status = "partially_filled"
            remaining = total - filled
            price, fee = decimal(command.get("price_cap")), decimal(command.get("fee_commitment"))
            principal = remaining * price * contract_multiplier(command["terms"]) if command["side"] == "BUY" and price is not None else Decimal(0) if command["side"] == "SELL" else None
            command.update(state=status, filled_quantity=str(filled), remaining_quantity=str(remaining),
                           cash_commitment=str(principal + (fee if fee is not None else Decimal(0)) + Decimal(command.get("collateral_commitment", "0"))) if principal is not None else None)
            if status in TERMINAL:
                command.update(remaining_quantity="0", cash_commitment="0")
            if report.get("broker_order_id") and report["broker_order_id"] not in command["broker_order_ids"]:
                command["broker_order_ids"].append(report["broker_order_id"])
            for identity in report.get("fill_ids", []):
                if identity not in command["fill_ids"]:
                    command["fill_ids"].append(identity)
            command["event_ids"].append(report["event_id"])
            command.setdefault("event_digests", {})[report["event_id"]] = digest(report)
            command["timeline"].append({"at": stamp(), "state": status, "source_at": report.get("source_at"), "report": copy.deepcopy(report)})
        return self.transaction(change)

    def reconcile(self):
        runtime = self.observation()
        gaps = []
        account_id = (runtime.get("account") or {}).get("id")
        if (runtime.get("status") != "connected" or not account_id or not runtime.get("account_at")
                or runtime.get("reconciliation", {}).get("status") != "reconciled" or runtime.get("local_record_error")):
            gaps.append("Fresh complete account/native observation is unavailable")
        confirmed = {item["command_id"] for item in runtime.get("native_deliveries", [])
                     if item.get("confirmed_current_process") is True and runtime.get("native_epoch")
                     and item.get("native_epoch") == runtime["native_epoch"]}
        def change(records):
            state = records["commands"]
            if account_id:
                state["account_versions"][account_id] = account_version(runtime)
            invalidate(records)
            for command in state["commands"].values():
                if command["state"] in TERMINAL | {"not_sent"} and not command.get("native_pending_commitment"):
                    continue
                if command["account_id"] != account_id:
                    gaps.append(command["id"] + ": observed account differs")
                if command.get("native_pending_commitment"):
                    gaps.append(command["id"] + ": native confirmation remains unresolved")
                if command["state"] in {"dispatch_intent", "submitting", "outcome_unknown", "cancel_pending", "replace_pending"}:
                    gaps.append(command["id"] + ": broker outcome remains unresolved")
                elif command["state"] != "admitted_not_dispatched" and command["id"] not in confirmed:
                    gaps.append(command["id"] + ": current native confirmation is unavailable")
            state.update(recovery_required=bool(gaps), recovery_reason="; ".join(gaps) if gaps else None)
        self.transaction(change)
        self.observe_current(runtime)
        record = self.database.read("commands", DEFAULT)
        return {**record, "ready": not record["data"]["recovery_required"], "reconciliation_deferred": False,
                "reason": record["data"]["recovery_reason"], "execution_enabled": self.execution_enabled,
                "admission_enabled": self.admission_enabled}
