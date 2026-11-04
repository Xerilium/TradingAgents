"""Nautilus adapter lifecycle over durable authority. No browser transport entry point."""

import asyncio
import copy
import hashlib
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from uuid import uuid4

from .admission import DEFAULT, CommandAdmission, account_version, instant
from .alpaca_readonly import AlpacaREST
from .alpaca_stream import PaperStream
from .app_database import ApplicationDatabase
from .investor import decimal, digest, replacement_funding_route, validated_replacement
from .linked_orders import broker_payload, flatten_orders, observed_orders, native_type, order_class, fractional_terms, trailing_terms, native_trail, broker_session, is_package, package_terms, package_legs, package_observation

CONFIRMED = {"observed_current_process", "superseded_by_current_observation"}

class CommandIdentityUnresolved(ValueError):
    """One command needs reconciliation; this does not classify a connection failure."""


class ExecutionLifecycle:
    def __init__(self, native, database_path, credentials_file, observation, assets, *, native_epoch, connection=None):
        self.native, self.path = native, Path(database_path) if database_path else None
        self.credentials_file, self.observation, self.assets = credentials_file, observation, assets
        self.native_epoch = native_epoch
        self.database = None
        self.transport = AlpacaREST(credentials_file, permit_paper_execution=True, connection=connection)
        self.identity_reconciliation = {"pending": [], "unresolved": {}, "last_attempt_at": None}
        self.stream_status = {"state": "not_started", "gap": "Trade stream awaits the native account connection",
                              "identity_reconciliation": self.identity_reconciliation}
        if self.path and self.path.is_file():
            self.begin_native_epoch()

    @staticmethod
    def retain_commitment(command, item):
        reservation = item.get("pending_commitment")
        if reservation is None:
            cap, fee = decimal(command.get("price_cap")), decimal(command.get("fee_commitment"))
            from .linked_orders import contract_multiplier
            principal = Decimal(command["terms"]["quantity"]) * cap * contract_multiplier(command["terms"]) if cap is not None else None
            cash = principal + (fee or Decimal(0)) if command["side"] == "BUY" and principal is not None else None if command["side"] == "BUY" else fee or Decimal(0)
            if command["terms"].get("execution_profile") == "bounded_risk_spread_v1":
                collateral = decimal(command.get("collateral_commitment"))
                cash = cash + collateral if cash is not None and collateral is not None and collateral >= 0 else None
            reservation = {"cash_commitment": None if cash is None else str(cash), "remaining_quantity": command["terms"]["quantity"]}
        pending = command.setdefault("native_pending_commitment", {})
        for key, value in reservation.items():
            prior = pending.get(key, "0")
            pending[key] = None if prior is None or value is None else str(max(Decimal(prior), Decimal(value)))

    def begin_native_epoch(self):
        def change(records):
            state = records["commands"]
            state["native_epoch"] = self.native_epoch
            for instruction in state.setdefault("option_instructions", {}).values():
                if instruction["native_epoch"] == self.native_epoch:
                    continue
                if instruction["state"] == "transport_intent":
                    instruction["state"] = "transport_unknown"
                    instruction["attempt"].update(state="transport_unknown", error_type="WorkerRestart")
                elif instruction["state"] in {"prepared", "approved"}:
                    instruction["state"] = "not_sent"
                else:
                    continue
                instruction["timeline"].append({"at": datetime.now(UTC).isoformat(), "action": "native_epoch_changed", "state": instruction["state"]})
            for command in state["commands"].values():
                for item in command.get("native_deliveries", {}).values():
                    if item.get("status") in CONFIRMED | {"applied"} and item.get("native_epoch") != self.native_epoch:
                        item.setdefault("application_history", []).append({key: item.get(key) for key in ("native_epoch", "status", "updated_at")})
                        item.update(status="unresolved", updated_at=datetime.now(UTC).isoformat())
                        self.retain_commitment(command, item)
                        state.update(recovery_required=True, recovery_reason="Prior native-process confirmations are historical; fresh broker/native observations are required")
        self.authority().transaction(change)

    def authority(self):
        if not self.path or not self.path.is_file():
            raise ValueError("Durable application authority database is unavailable")
        if self.database is None:
            self.database = ApplicationDatabase(self.path.parent, {})
        return CommandAdmission(self.database, self.observation, execution_enabled=True)

    async def dispatch_instruction(self, identity):
        authority = self.authority()
        attempt_id = str(uuid4())
        generation = None

        def validate(records, *, claimed=False):
            state = records["commands"]
            row = state.setdefault("option_instructions", {})[identity]
            if self.native.observation_dirty:
                raise ValueError("A native update requires a fresh broker observation before instruction dispatch")
            approval = row.get("approval") or {}
            if row["state"] != ("transport_intent" if claimed else "approved") or claimed and row["attempt"]["id"] != attempt_id:
                raise ValueError("Instruction authority is one-shot and has already changed")
            if not approval.get("expires_at") or instant(approval["expires_at"]) <= datetime.now(UTC):
                raise ValueError("Instruction approval expired")
            review = authority.instruction_review(records, row["kind"], row["symbol"], row["constraints"], identity)
            if (review["blockers"] or review["binding_sha256"] != approval.get("binding_sha256")
                    or row["native_epoch"] != self.native_epoch or row["endpoint"] != self.transport.connection.endpoint
                    or row["mode"] != self.transport.connection.mode):
                raise ValueError("Material instruction facts, account/session or restrictions changed; review fresh authority")
            if row["kind"] == "exercise" and state.get("new_orders_blocked"):
                raise ValueError("New orders and exercise dispatch are paused; separately approved DNE remains available")
            return row

        async with self.native.observation_lock:
            def claim(records):
                row = records["commands"].setdefault("option_instructions", {})[identity]
                if row["state"] != "approved":
                    raise ValueError("Instruction authority is one-shot; prepare a fresh instruction")
                try:
                    row = validate(records)
                except (ValueError, KeyError, TypeError) as exc:
                    row.update(state="not_sent", attempt={"id": attempt_id, "state": "not_sent", "result_at": datetime.now(UTC).isoformat(), "reason": str(exc)})
                    row["timeline"].append({"at": datetime.now(UTC).isoformat(), "action": "admission_blocked", "state": "not_sent"})
                    return
                row.update(state="transport_intent", attempt={"id": attempt_id, "state": "in_flight", "attempted_at": datetime.now(UTC).isoformat()})
                row["timeline"].append({"at": datetime.now(UTC).isoformat(), "action": "transport_claimed", "attempt_id": attempt_id})
            claimed = authority.transaction(claim, evidence=True)
            if claimed["commands"]["data"]["option_instructions"][identity]["state"] == "not_sent":
                return
            generation = self.observation().get("observation_generation")

        def finish(state, details):
            def change(records):
                row = records["commands"]["option_instructions"][identity]
                if not row.get("attempt") or row["attempt"]["id"] != attempt_id or row["state"] not in {"transport_intent", "transport_unknown"}:
                    raise ValueError("Instruction response no longer matches its retained attempt; no state overwritten")
                row["state"] = state
                row["attempt"].update(state=state, result_at=datetime.now(UTC).isoformat(), **details)
                row["timeline"].append({"at": datetime.now(UTC).isoformat(), "action": "transport_result", "state": state, "attempt_id": attempt_id})
            authority.transaction(change)

        try:
            async with self.native.observation_lock:
                if not generation or generation != self.observation().get("observation_generation"):
                    raise ValueError("Source generation changed before dispatch; this attempt was never sent")
                saved = authority.transaction(lambda records: validate(records, claimed=True) and None, evidence=True)
                row = saved["commands"]["data"]["option_instructions"][identity]
        except (ValueError, KeyError, TypeError) as exc:
            finish("not_sent", {"error_type": type(exc).__name__, "reason": str(exc)})
            return
        # The claim and final local guards are durable. Neither SQLite nor observation locks span HTTP.
        try:
            response = await asyncio.to_thread(self.transport.option_instruction, row["symbol"], row["kind"])
            reference = self.receipt("option-instruction-" + identity, "Broker option instruction response",
                {"attempt_id": attempt_id, "account_id": row["account_id"], "endpoint": row["endpoint"], "kind": row["kind"],
                 "symbol": row["symbol"], "status": response["status"], "raw_response": self.transport.connection.redact(response["raw"].decode("utf-8", errors="replace")),
                 "received_at": response["received_at"], "source_date": response["source_date"]})
            finish("submitted" if response["status"] == 200 else "transport_unknown", {"status": response["status"], "receipt": reference})
        except HTTPError as exc:
            try:
                raw = exc.read(8 * 1024 * 1024 + 1)
                reference = self.receipt("option-instruction-" + identity, "Broker option instruction HTTP result",
                    {"attempt_id": attempt_id, "status": exc.code, "raw_response": self.transport.connection.redact(raw[:8 * 1024 * 1024].decode("utf-8", errors="replace")),
                     "truncated": len(raw) > 8 * 1024 * 1024, "received_at": datetime.now(UTC).isoformat()})
            except Exception as capture_error:
                finish("transport_unknown", {"status": exc.code, "error_type": type(capture_error).__name__})
                return
            finish("rejected" if 400 <= exc.code < 500 and exc.code != 408 else "transport_unknown",
                {"status": exc.code, "receipt": reference, "error_type": "HTTPError"})
        except Exception as exc:
            finish("transport_unknown", {"error_type": type(exc).__name__})

    def native_action_intent(self, identity, action_id, before, event_ids):
        def change(records):
            command = records["commands"]["commands"][identity]
            action = command["pending_action"]
            if (action["id"] != action_id or action.get("state") != "authorized" or not action.get("actor")
                    or action.get("kind") not in {"cancel", "replace"} or action.get("native_transition")
                    or action.get("transport_attempt") != {"version": 1, "state": "not_started"}
                    or action.get("expires_at") and instant(action["expires_at"]) <= datetime.now(UTC) or before.get("status") not in {"SUBMITTED", "ACCEPTED", "PARTIALLY_FILLED"}
                    or (before.get("venue_order_id") or ((before.get("venue_order_id_binding") or {}).get("venue_order_id")
                        if (before.get("venue_order_id_binding") or {}).get("source") == "native_cache_venue_order_index"
                        and (before.get("venue_order_id_binding") or {}).get("client_order_id") == before.get("client_order_id") else None)) != action["broker_order_id"]
                    or action["broker_order_id"] not in command["broker_order_ids"]
                    or before.get("instrument_id") != command["instrument_id"]
                    or before.get("client_order_id") != command.get("native_client_order_id", command["client_order_id"])
                    or (before.get("account_binding") or {}).get("account_id") != "ALPACA-" + command["account_id"]):
                raise ValueError("Native action requires the exact current authorized working-order intent")
            action["native_transition"] = {"native_epoch": self.native_epoch, "before": copy.deepcopy(before), "event_ids": event_ids}
        self.authority().transaction(change)

    def command(self, identity, *, sending=False):
        authority = self.authority()
        if sending:
            authority.enabled()
        state = authority.snapshot()["data"]
        command = state["commands"][identity]
        if sending and command.get("origin") in {"external_broker", "linked_broker"}:
            raise ValueError("Observed external orders have no original app submission authority")
        if sending and (command["state"] != "dispatch_intent" or not command["dispatch_intent_at"]):
            raise ValueError("Durable dispatch intent is required before transport I/O")
        if sending:
            approval = state["approvals"][command["approval_id"]]
            runtime = authority.checked_observation(approval["constraints"])
            proposal = authority.database.read("investor")["data"]
            source = next(p for p in proposal["proposals"] if p["id"] == command["proposal_id"])
            if (state["recovery_required"] or command["approval_id"] in state["revocations"]
                    or approval.get("expires_at") and instant(approval["expires_at"]) <= datetime.now(UTC) or account_version(runtime) != command["account_version"]
                    or source["revision"] != command["proposal_revision"] or source["status"] != "draft"
                    or proposal["policy"]["revision"] != command["policy_revision"]):
                raise ValueError("Durable command authority is no longer current at the native transport boundary")
        if command["account_id"] != (self.observation().get("account") or {}).get("id"):
            raise ValueError("Command and observed account differ")
        return command

    def receipt(self, command_id, source, payload):
        root = self.path.parent
        relative = Path("reports") / command_id / ("execution-" + str(uuid4()) + ".json")
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps({"source": source, "captured_at": datetime.now(UTC).isoformat(), "payload": payload},
                          ensure_ascii=False, allow_nan=False).encode()
        with target.open("xb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        return {"path": relative.as_posix(), "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "format": "json"}

    def reconstruction(self, instrument_id):
        state = self.authority().database.read("commands", {})["data"]
        record = state.get("native_reconstructions", {}).get(str(instrument_id))
        return record if record and record.get("native_epoch") == self.native_epoch else None

    def retain_reconstruction(self, payload):
        identity = payload["instrument_id"]
        prior = self.authority().database.read("commands", {})["data"].get("native_reconstructions", {}).get(identity)
        record = {**payload, "version": "native-position-reconstruction-v1", "account_id": self.observation()["account"]["id"],
            "endpoint": self.transport.connection.endpoint, "native_epoch": self.native_epoch}
        reference = self.receipt("native-reconstruction", "Explicit native position representation; not broker transactions or historical economics", record)
        record = {key: record[key] for key in ("version", "account_id", "endpoint", "native_epoch", "instrument_id", "state",
            "represented_quantity", "actual_execution_ids_applied", "native_order_ids", "native_trade_ids", "basis")}
        record.update(receipt=reference, history=(prior.get("history", []) + [prior["receipt"]]) if prior else [])
        self.authority().transaction(lambda records: records["commands"].setdefault("native_reconstructions", {}).update({identity: record}))
        return record

    def require_causal_fill(self, row, identity):
        baseline = self.reconstruction(row["symbol"] + ".ALPACA")
        if baseline is None:
            return
        if baseline.get("state") != "confirmed":
            raise ValueError("Native reconstruction remains unresolved; explicit stop/start is required before applying unseen executions")
        state = self.authority().database.read("commands", {})["data"]
        command = next((item for item in state.get("commands", {}).values() if item.get("account_id") == baseline["account_id"]
            and (item.get("instrument_id") == baseline["instrument_id"] and item.get("client_order_id") == row.get("client_order_id")
                or is_package(item.get("terms", {})) and any(member.get("id") == row.get("id") and member.get("symbol") == row.get("symbol")
                    for member in item.get("package_members", [])))
            and item.get("approval_id") and item.get("origin") != "external_broker"), {})
        parent = (command.get("reconstruction_parents", {}).get(baseline["instrument_id"]) if is_package(command.get("terms", {}))
                  else command.get("reconstruction_parent")) or {}
        if (baseline.get("state") == "confirmed" and parent.get("receipt") == baseline["receipt"]
                and parent.get("native_epoch") == self.native_epoch and parent.get("account_id") == baseline["account_id"]):
            return
        reason = "Unseen actual execution has no causal proof outside the native baseline; explicit stop/start reconstruction is required: " + str(identity)
        payload = {**baseline, "state": "reconstruction_required", "reason": reason, "new_actual_execution_id": str(identity)}
        self.retain_reconstruction(payload)
        raise ValueError(reason)

    def record_pending(self, identity, state, reason, receipt=None):
        authority = self.authority()
        def change(records):
            command = records["commands"]["commands"][identity]
            command["state"] = state
            command["timeline"].append({"at": datetime.now(UTC).isoformat(), "state": state, "reason": reason, "receipt": receipt})
            if state == "outcome_unknown":
                records["commands"].update(recovery_required=True, recovery_reason=reason)
        return authority.transaction(change)

    def delivery(self, command_id, identity, data, reference, status=None):
        """Broker receipt deduplication is independent of native application."""
        def change(records):
            state = records["commands"]
            command = state["commands"][command_id]
            deliveries = command.setdefault("native_deliveries", {})
            prior = deliveries.get(identity)
            if prior and prior["source_sha256"] != digest(data):
                prior.setdefault("conflicts", []).append(reference)
                state.update(recovery_required=True, recovery_reason="Conflicting native delivery identity")
                prior["status"] = "conflict"
                self.retain_commitment(command, prior)
                return
            item = deliveries.setdefault(identity, {"source_sha256": digest(data), "receipt": reference,
                "status": "pending", "input": copy.deepcopy(data), "native_epoch": self.native_epoch,
                "pending_commitment": {key: command.get(key, "0") for key in ("cash_commitment", "remaining_quantity")},
                "recorded_at": datetime.now(UTC).isoformat()})
            if status:
                item.update(status=status, updated_at=datetime.now(UTC).isoformat())
                if status == "observed_current_process":
                    item["native_epoch"] = self.native_epoch
            command.pop("native_pending_commitment", None)
            for pending in deliveries.values():
                if pending["status"] not in CONFIRMED or pending.get("native_epoch") != self.native_epoch:
                    self.retain_commitment(command, pending)
            if command.get("native_pending_commitment"):
                state.update(recovery_required=True, recovery_reason="Broker events await current-process native confirmation")
        self.authority().transaction(change)
        return self.command(command_id)["native_deliveries"][identity]

    def resolve_market_replacement_receipts(self):
        """Confirm only retained MARKET replacement facts after actual native fills."""
        from .alpaca_reports import execution_id, native_quantities, timestamp
        from .native_types import ClientOrderId, OrderFilled, enum_name, native_order_account
        commands = self.authority().database.read("commands", DEFAULT)["data"]["commands"]
        proven_receipt = False
        def verified(reference):
            source = (self.path.parent / reference["path"]).resolve()
            if not source.is_relative_to(self.path.parent.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest() != reference["sha256"]:
                raise ValueError("Replacement evidence is missing or changed")
        for child in commands.values():
            binding = child.get("native_replacement_quantity_binding")
            if not binding:
                continue
            for identity, delivery in child.get("native_deliveries", {}).items():
                data = delivery["input"]
                row = data.get("order") or {}
                if (delivery["status"] not in {"pending", "intent", "unresolved", "observed_current_process"} or data.get("event") != "replacement_authoritative"
                        or row.get("type") != "market" and row.get("asset_class") != "us_option" or row.get("status") not in {"partially_filled", "filled"}):
                    continue
                try:
                    if digest(data) != delivery["source_sha256"]:
                        continue
                    verified(delivery["receipt"])
                    for reference in [binding["history_receipt"], *binding.get("history_boundary_receipts", [])]:
                        verified(reference)
                    if binding.get("incoming_execution_receipt"):
                        verified(binding["incoming_execution_receipt"])
                    row = {**row, "native_replacement_quantity_binding": binding}
                    quantity, filled = native_quantities(row)
                    order = self.native.cache.order(ClientOrderId(child.get("native_client_order_id", child["client_order_id"])))
                    if (order is None or native_order_account(order, self.native) != "ALPACA-" + child["account_id"]
                            or str(order.client_order_id) != row["client_order_id"] or str(order.venue_order_id) != row["id"]
                            or str(order.instrument_id) != child["instrument_id"] or row["symbol"] + ".ALPACA" != child["instrument_id"]
                            or enum_name(order.side).lower() != row["side"] or row["side"].upper() != child["side"]
                            or enum_name(order.order_type) != native_type(row["type"]) or enum_name(order.time_in_force) != row["time_in_force"].upper() or order.quantity.as_decimal() != quantity):
                        continue
                    fills = [event for event in order.events if isinstance(event, OrderFilled)
                        and event.ts_event <= timestamp(data.get("timestamp") or row["updated_at"])]
                    if (len({execution_id(event.trade_id) for event in fills}) != len(fills)
                            or any(str(event.account_id) != "ALPACA-" + child["account_id"] or event.client_order_id != order.client_order_id
                                or str(event.venue_order_id) != row["id"] or event.instrument_id != order.instrument_id
                                or event.order_side != order.side for event in fills)
                            or sum((event.last_qty.as_decimal() for event in fills), Decimal(0)) != filled):
                        continue
                    if row["status"] == "filled" and filled != quantity or row["status"] == "partially_filled" and filled >= quantity:
                        continue
                    if delivery["status"] != "observed_current_process" or delivery.get("native_epoch") != self.native_epoch:
                        self.delivery(child["id"], identity, data, delivery["receipt"], "observed_current_process")
                    proven_receipt = True
                    for parent in commands.values():
                        if (parent.get("pending_action") or {}).get("replacement_command_id") != child["id"]:
                            continue
                        native = self.native.cache.order(ClientOrderId(parent.get("native_client_order_id", parent["client_order_id"])))
                        if (native is None or native_order_account(native, self.native) != "ALPACA-" + parent["account_id"]
                                or str(native.instrument_id) != parent["instrument_id"] or parent["instrument_id"] != child["instrument_id"]
                                or str(native.client_order_id) != parent.get("native_client_order_id", parent["client_order_id"])
                                or enum_name(native.side).upper() != parent["side"]):
                            continue
                        for prior_id, prior in parent.get("native_deliveries", {}).items():
                            source = prior["input"]
                            old = source.get("order") or {}
                            if (prior["status"] not in {"pending", "intent", "unresolved"} or source.get("event") != "replaced"
                                    or old.get("id") != row["replaces"] or old.get("replaced_by") != row["id"]
                                    or old.get("client_order_id") != parent["client_order_id"] or old.get("symbol") != row["symbol"]
                                    or old.get("side") != row["side"] or digest(source) != prior["source_sha256"]):
                                continue
                            verified(prior["receipt"])
                            if parent.get("native_replacement_quantity_binding"):
                                old = {**old, "native_replacement_quantity_binding": parent["native_replacement_quantity_binding"]}
                            if self.native_applied(native, "replaced", source, old, "canceled", source.get("timestamp") or old["updated_at"],
                                    indexed_venue_id=self.native.cache.venue_order_id(native.client_order_id)):
                                self.delivery(parent["id"], prior_id, source, prior["receipt"], "observed_current_process")
                except (OSError, ValueError, KeyError, TypeError, ArithmeticError):
                    continue
        return proven_receipt

    def delivery_summary(self):
        if not self.path or not self.path.is_file():
            return []
        commands = self.authority().database.read("commands", {})["data"].get("commands", {})
        return [{"command_id": command["id"], "event_id": identity, "status": item["status"],
                 "native_epoch": item.get("native_epoch"), "confirmed_current_process": item["status"] in CONFIRMED and item.get("native_epoch") == self.native_epoch,
                 "source_receipt": item["receipt"], "commission": item.get("input", {}).get("commission")}
                for command in commands.values() for identity, item in command.get("native_deliveries", {}).items()]

    def confirm_package_observations(self, rows, history):
        if not history.get("complete") or not history.get("evidence"):
            return False
        from .alpaca_reports import native_quantities, order_report, timestamp
        from .native_types import ClientOrderId, native_order_account
        commands = self.authority().snapshot()["data"]["commands"]
        confirmed = False
        for row in rows:
            if not row.get("package_terms"):
                continue
            matches = [command for command in commands.values() if is_package(command.get("terms", {}))
                and command["client_order_id"] == row.get("client_order_id")]
            if len(matches) != 1:
                continue
            command = matches[0]
            order = self.native.cache.order(ClientOrderId(command.get("native_client_order_id", command["client_order_id"])))
            quantity, filled = native_quantities(row)
            report = order_report(row, self.native.account_id, 0)
            if (order is None or native_order_account(order, self.native) != "ALPACA-" + command["account_id"]
                    or str(order.instrument_id) != command["instrument_id"] or str(order.venue_order_id) != row["id"]
                    or order.quantity.as_decimal() != quantity or order.filled_qty.as_decimal() != filled or order.status != report.order_status
                    or timestamp(row["updated_at"]) > timestamp(history["through"])):
                continue
            members = {member["id"] for member in row["package_members"]}
            actual = [fill for fill in self.native.fill_reports if str(fill.venue_order_id) in members | {row["id"]}]
            for fill in actual:
                if self.native.package_leg_event(fill) is None:
                    raise ValueError("Actual package leg execution proof disappeared")
            source = {"event": "package_reconciled_observation", "order": row, "actual_leg_execution_ids": [str(fill.trade_id) for fill in actual]}
            reference = self.receipt(command["id"], "Actual package members/native control and actual leg execution coverage", {"source": source, "history": history["evidence"]})
            identity = "package-observation:" + digest(source)
            self.delivery(command["id"], identity, source, reference, "observed_current_process")
            state = {"ACCEPTED": "accepted", "SUBMITTED": "submitting", "PARTIALLY_FILLED": "partially_filled", "FILLED": "filled",
                "CANCELED": "canceled", "EXPIRED": "expired", "REJECTED": "rejected", "PENDING_CANCEL": "cancel_pending", "PENDING_UPDATE": "replace_pending"}[order.status.name]
            if identity not in command["event_ids"]:
                self.authority().apply_report(command["id"], {"authoritative": True, "event_id": identity, "receipt": reference,
                    "account_id": command["account_id"], "client_order_id": command["client_order_id"], "instrument_id": command["instrument_id"],
                    "broker_order_id": row["id"], "filled_quantity": row["filled_qty"], "state": state, "source_at": row["updated_at"],
                    "fill_ids": [], "commission": None, "package_control_only": True})
            def change(records, command=command, reference=reference, source=source, members=members,
                       row=row, actual=actual, state=state, identity=identity):
                current = records["commands"]["commands"][command["id"]]
                current["package_execution_evidence"] = {"receipt": reference, "history": history["evidence"],
                    "actual_leg_execution_ids": source["actual_leg_execution_ids"], "native_epoch": self.native_epoch, "parent_economics": False}
                for delivery in current.get("native_deliveries", {}).values():
                    prior = delivery.get("input", {}).get("order") or {}
                    path = (self.path.parent / delivery["receipt"]["path"]).resolve()
                    incoming = delivery.get("input", {})
                    if prior.get("id") in members | {row["id"]} and incoming.get("event") in {"fill", "partial_fill"}:
                        from .alpaca_reports import execution_id
                        matches = [fill for fill in actual if execution_id(fill.trade_id) == execution_id(incoming.get("execution_id"))]
                        matched_members = [member for member in row["package_members"] if len(matches) == 1
                            and member["symbol"] + ".ALPACA" == str(matches[0].instrument_id)
                            and member["native_client_order_id"] == str(matches[0].client_order_id)]
                        if (len(matches) != 1 or len(matched_members) != 1
                                or str(matches[0].venue_order_id) != prior.get("id")
                                or (incoming.get("symbol") or (prior.get("symbol") if prior.get("id") in members else None))
                                    not in (None, matched_members[0]["symbol"])
                                or matches[0].last_qty.as_decimal() != decimal(incoming.get("qty"))
                                or matches[0].last_px.as_decimal() != decimal(incoming.get("price"))
                                or matches[0].ts_event != timestamp(incoming.get("timestamp"))):
                            continue
                    if (delivery["status"] != "conflict" and prior.get("id") in members | {row["id"]}
                            and delivery.get("source_sha256") == digest(delivery["input"]) and path.is_relative_to(self.path.parent.resolve())
                            and hashlib.sha256(path.read_bytes()).hexdigest() == delivery["receipt"]["sha256"]
                            and timestamp(prior.get("updated_at")) <= timestamp(row["updated_at"])):
                        delivery.update(status="superseded_by_current_observation", native_epoch=self.native_epoch, current_observation_receipt=reference)
                current.pop("native_pending_commitment", None)
                for delivery in current.get("native_deliveries", {}).values():
                    if delivery["status"] not in CONFIRMED or delivery.get("native_epoch") != self.native_epoch:
                        self.retain_commitment(current, delivery)
                action = current.get("pending_action") or {}
                if state in {"filled", "canceled", "expired", "rejected"} and action.get("broker_order_id") == row["id"]:
                    action.update(state="completed", outcome_receipt=reference, outcome_event_id=identity)
            self.authority().transaction(change)
            self.identity_reconciliation["unresolved"].pop(command["id"], None)
            confirmed = True
        return confirmed

    def confirm_linked_observations(self, rows, history):
        """Fresh complete native/fill proof can supersede old child state receipts, not replay them."""
        if not history.get("complete") or not history.get("evidence"):
            return False
        from .native_types import ClientOrderId, OrderFilled, enum_name, native_dict, native_order_account
        from .alpaca_reports import native_quantities, timestamp, execution_id, order_report
        by_id, proofs = {row["id"]: row for row in rows}, {}
        commands = self.authority().database.read("commands", DEFAULT)["data"]["commands"]
        for command in commands.values():
            root_exit = command["side"] == "SELL" and (command.get("terms", {}).get("exit_plan") or command.get("linked_group_owner_id"))
            if not (command.get("linked_exit") or root_exit) or not command.get("native_pending_commitment"):
                continue
            order = self.native.cache.order(ClientOrderId(command.get("native_client_order_id", command["client_order_id"])))
            row = by_id.get(str(order.venue_order_id)) if order is not None else None
            if not row or row.get("import_error") or row.get("side") != "sell" or row.get("symbol") != command["symbol"]:
                continue
            parent = commands[command["linked_entry_command_id"]] if command.get("linked_exit") else commands.get(command.get("linked_group_owner_id"), command)
            roots = set(parent["broker_order_ids"]) | set(parent.get("linked_root_order_ids", []))
            if ((row["id"] not in roots if root_exit else row.get("group_parent_id") not in roots)
                    or native_order_account(order, self.native) != "ALPACA-" + command["account_id"]
                    or str(order.instrument_id) != command["instrument_id"]
                    or timestamp(row["updated_at"]) > timestamp(history["through"])):
                continue
            chain, source = {row["id"]}, row
            while source.get("replaces"):
                prior = by_id.get(source["replaces"])
                if (not prior or prior.get("replaced_by") != source["id"] or prior["id"] in chain
                        or any(prior.get(key) != row.get(key) for key in ("symbol", "side", "type"))
                        or (prior["id"] not in roots if root_exit else prior.get("group_parent_id") not in roots)):
                    break
                chain.add(prior["id"])
                source = prior
            if source.get("replaces") or not chain.intersection(command["broker_order_ids"]):
                continue
            total, filled = native_quantities(row)
            actual = native_dict(order)
            events = [event for event in order.events if isinstance(event, OrderFilled)]
            if (order.quantity.as_decimal() != total or order.filled_qty.as_decimal() != filled
                    or actual.get("side") != "SELL" or actual.get("type") != native_type(row["type"])
                    or order.status != order_report(row, self.native.account_id, 0).order_status
                    or decimal(actual.get("price")) != decimal(row.get("limit_price"))
                    or decimal(actual.get("trigger_price")) != decimal(row.get("stop_price"))
                    or enum_name(order.time_in_force).lower() != row["time_in_force"]
                    or sum((event.last_qty.as_decimal() for event in events), Decimal(0)) != filled
                    or len({execution_id(event.trade_id) for event in events}) != len(events)
                    or any(str(event.venue_order_id) not in chain for event in events)):
                continue
            covered = []
            for identity, delivery in command.get("native_deliveries", {}).items():
                data = delivery["input"]
                old = data.get("order") or {}
                reference = delivery["receipt"]
                path = (self.path.parent / reference["path"]).resolve()
                if (delivery["status"] == "conflict" or old.get("id") not in chain
                        or delivery["source_sha256"] != digest(data) or not path.is_relative_to(self.path.parent.resolve())
                        or hashlib.sha256(path.read_bytes()).hexdigest() != reference["sha256"]
                        or timestamp(data.get("timestamp") or old["updated_at"]) > timestamp(row["updated_at"])):
                    continue
                if data.get("event") in {"fill", "partial_fill"} and not self.native_applied(order, data["event"], data, old,
                        "filled" if old.get("status") == "filled" else "partially_filled", data.get("timestamp") or old["updated_at"]):
                    continue
                covered.append(identity)
            if covered:
                proofs[command["id"]] = {"deliveries": covered, "native": actual, "broker_order_id": row["id"],
                    "execution_ids": [execution_id(event.trade_id) for event in events]}
        if not proofs:
            return False
        reference = self.receipt("linked-recovery", "Current broker/native linked exit proof; historical transitions not replayed",
                                 {"history": history["evidence"], "through": history["through"], "proofs": proofs})
        def change(records):
            for identity, proof in proofs.items():
                command = records["commands"]["commands"][identity]
                for delivery_id in proof["deliveries"]:
                    command["native_deliveries"][delivery_id].update(status="superseded_by_current_observation",
                        native_epoch=self.native_epoch, current_observation_receipt=reference,
                        updated_at=datetime.now(UTC).isoformat())
                command.pop("native_pending_commitment", None)
                for delivery in command["native_deliveries"].values():
                    if delivery["status"] not in CONFIRMED or delivery.get("native_epoch") != self.native_epoch:
                        self.retain_commitment(command, delivery)
        self.authority().transaction(change)
        return True

    def native_gap(self, identity, reason, receipt=None):
        self.identity_reconciliation["unresolved"][identity] = {"reason": reason, "attempted_at": datetime.now(UTC).isoformat()}
        def change(records):
            state = records["commands"]
            state.update(recovery_required=True, recovery_reason=reason)
            state["commands"][identity]["timeline"].append({"at": datetime.now(UTC).isoformat(),
                "native_application": "unresolved", "reason": reason, "receipt": receipt})
        self.authority().transaction(change)

    def checked_fractional_terms(self, terms):
        from .linked_orders import execution_profile_terms

        if execution_profile_terms(terms) == "bounded_risk_spread_v1" and getattr(self.native, "execution_profile", "long_only") != "bounded_risk_spread_v1":
            raise ValueError("Bounded risk option authority requires a separately validated native profile session")
        if is_package(terms):
            package_terms(terms)
            for leg in package_legs(terms):
                self.checked_fractional_terms(leg)
                if self.assets().get(leg["symbol"], {}).get("tradable") is not True:
                    raise ValueError("An actual package leg is not currently tradable")
            return
        asset = self.assets().get(terms["symbol"], {})
        if terms.get("asset_class") == "us_option":
            from .linked_orders import option_terms
            option_terms(terms)
            if asset.get("status") != "active" or asset.get("option_contract", {}).get("sha256") != terms["option_contract"]["sha256"]:
                raise ValueError("Current option metadata differs from exact approval")
        quantity = fractional_terms(terms, fractionable=asset.get("fractionable", False))
        if quantity % 1:
            bound = terms.get("fractional_asset") or {}
            current = {key: asset.get(key) for key in ("id", "symbol", "class", "exchange", "status", "tradable", "fractionable",
                                                      "overnight_tradable", "overnight_halted", "fractional_eh_enabled", "attributes")}
            if terms.get("session", "regular") == "extended" and asset.get("fractional_eh_enabled") is not True:
                raise ValueError("Current asset does not establish fractional extended-session eligibility")
            if bound.get("asset") != current:
                raise ValueError("Current fractional asset identity or eligibility differs from exact approval")

    def checked_native_order(self, order, durable):
        terms = durable["terms"]
        self.checked_fractional_terms(terms)
        if terms.get("asset_class") != "us_option" and terms["side"] == "BUY" and terms["order_type"] == "STOP_MARKET":
            raise ValueError("BUY stop-market broker conversion is not mapped; approve explicit STOP_LIMIT terms instead")
        from .native_types import native_dict, enum_name
        raw = native_dict(order)
        if ("extended_hours" in (raw.get("tags") or [])) != (terms.get("session", "regular") == "extended"):
            raise ValueError("Native session eligibility differs from exact durable approved terms")
        if trailing_terms(terms):
            offset, unit = native_trail(terms)
            if (decimal(raw.get("trailing_offset")) != offset or raw.get("trailing_offset_type") != unit
                    or raw.get("trigger_price") is not None or raw.get("activation_price") is not None
                    or raw.get("emulation_trigger") != "NO_TRIGGER" or raw.get("trigger_type") != "DEFAULT"):
                raise ValueError("Native trailing instructions differ from the initial approved broker-managed trail")
        if (str(order.instrument_id) != durable["instrument_id"] or str(order.client_order_id) != durable.get("native_client_order_id", durable["client_order_id"])
                or enum_name(order.side) != terms["side"] or enum_name(order.order_type) != terms["order_type"]
                or enum_name(order.time_in_force) != terms["time_in_force"] or order.is_quote_quantity
                or order.is_reduce_only != (order_class(terms) == "oco" or terms.get("position_intent") == "sell_to_close")
                or not is_package(terms) and self.assets().get(terms["symbol"], {}).get("tradable") is not True):
            raise ValueError("Unsupported native order or exact durable identity/terms mismatch")
        if is_package(terms) and "atomic_option_package" not in (raw.get("tags") or []):
            raise ValueError("Native package control differs from exact approval")
        if terms.get("asset_class") == "us_option" and not is_package(terms) and "option_intent:" + terms["position_intent"] not in (raw.get("tags") or []):
            raise ValueError("Native option intent differs from exact approval")
        if Decimal(raw["quantity"]) != Decimal(terms["quantity"]):
            raise ValueError("Native and reviewed quantities differ")
        if terms["order_type"] in {"LIMIT", "STOP_LIMIT"} and Decimal(raw["price"]) != Decimal(terms["limit_price"]):
            raise ValueError("Native and reviewed limit prices differ")
        if terms["order_type"] in {"STOP_MARKET", "STOP_LIMIT"} and Decimal(raw["trigger_price"]) != Decimal(terms["stop_price"]):
            raise ValueError("Native and reviewed stop triggers differ")

    def bind_package(self, row):
        if not row.get("package_terms"):
            raise ValueError("Exact package source mapping is unavailable")
        package_observation(row, row["package_terms"])
        def change(records):
            matches = [command for command in records["commands"]["commands"].values() if is_package(command.get("terms", {}))
                and (command.get("client_order_id") == row.get("client_order_id") or row["id"] in command.get("broker_order_ids", []))]
            if len(matches) != 1:
                raise ValueError("Package source has no unique durable command")
            command = matches[0]
            command["package_members"] = copy.deepcopy(row["package_members"])
            source = {key: copy.deepcopy(value) for key, value in row.items()
                if key not in {"package_control", "package_terms", "package_members", "package_mapping"}}
            command["package_control"] = {"internal": True, "economics": "actual_leg_fills_only",
                "source_mapping": copy.deepcopy(row["package_mapping"]), "source_order": source}
            if row.get("native_replacement_quantity_binding"):
                command.update(native_client_order_id=row["client_order_id"], native_quantity_offset=row["native_replacement_quantity_binding"]["ancestor_filled_quantity"],
                    native_replacement_quantity_binding=copy.deepcopy(row["native_replacement_quantity_binding"]))
        self.authority().transaction(change)

    def bind_group(self, rows):
        """Retain broker-assigned child IDs under the original approval, never submission authority."""
        def change(records):
            commands = records["commands"]["commands"]
            for root in rows:
                if root.get("group_class") != "oco" or root.get("group_role") != "take_profit":
                    continue
                command = next((command for command in commands.values() if command["client_order_id"] == root.get("client_order_id")), None)
                owner = commands.get(command.get("linked_group_owner_id"), command) if command else None
                if owner and owner.get("terms", {}).get("exit_plan") and owner["side"] == "SELL":
                    if (root.get("symbol") != owner["symbol"] or root.get("side") != "sell" or root.get("type") != "limit"
                            or root.get("asset_class") != "us_equity" or root.get("account_id", owner["account_id"]) != owner["account_id"]
                            or root.get("time_in_force", "").upper() != owner["terms"]["time_in_force"]
                            or decimal(root.get("limit_price")) != decimal(command["terms"].get("limit_price"))
                            or command["terms"].get("replacement") and root.get("replaces") != command["terms"]["replacement"]["order_id"]):
                        raise ValueError("Broker OCO root differs from its exact original or renewed group authority")
                    self._resize_exit(command, root, owner)
                    roots = owner.setdefault("linked_root_order_ids", [])
                    if root["id"] not in roots:
                        roots.append(root["id"])
            for row in rows:
                parent = next((command for command in commands.values() if command.get("terms", {}).get("exit_plan")
                               and row.get("group_parent_id") in command.get("broker_order_ids", []) + command.get("linked_root_order_ids", [])), None)
                if parent is None:
                    # Submission response arrives before the parent report has recorded the venue ID.
                    source = next((source for source in rows if source["id"] == row.get("group_parent_id")), None)
                    parent = next((command for command in commands.values() if source and source.get("client_order_id") == command["client_order_id"]
                                   and command.get("terms", {}).get("exit_plan")), None)
                if parent is None:
                    continue
                if row.get("account_id", parent["account_id"]) != parent["account_id"]:
                    raise ValueError("Broker exit account differs from its approved entry account")
                role = row.get("group_role")
                plan = parent["terms"]["exit_plan"]
                if role not in {"take_profit", "stop_loss"} or row["symbol"] != parent["symbol"] or row["side"] != "sell":
                    raise ValueError("Broker child does not match the approved entry exit plan")
                expected = "limit" if role == "take_profit" else "stop_limit" if plan.get("stop_limit_price") else "stop"
                if row["type"] != expected or row["time_in_force"].upper() != parent["terms"]["time_in_force"]:
                    raise ValueError("Broker child type or duration differs from the approved exit")
                native_id = parent["client_order_id"] + ("-TP" if role == "take_profit" else "-SL")
                row["native_client_order_id"] = native_id
                existing = next((command for command in commands.values() if row["id"] in command.get("broker_order_ids", [])
                    or command.get("linked_exit") and command["client_order_id"] == row.get("client_order_id")), None)
                if existing:
                    if existing.get("linked_entry_command_id") != parent["id"]:
                        raise ValueError("Broker exit identity is already bound to another command")
                    if (row.get("client_order_id") != existing["client_order_id"]
                            or decimal(row.get("limit_price")) != decimal(existing["terms"].get("limit_price"))
                            or decimal(row.get("stop_price")) != decimal(existing["terms"].get("stop_price"))):
                        raise ValueError("Broker exit economics differ from their current exact authorized terms")
                    replacement = existing["terms"].get("replacement")
                    if replacement and (row.get("replaces") != replacement["order_id"]
                            or Decimal(row["qty"]) > Decimal(existing["terms"]["quantity"])
                            or decimal(row.get("limit_price")) != decimal(existing["terms"].get("limit_price"))
                            or decimal(row.get("stop_price")) != decimal(existing["terms"].get("stop_price"))):
                        raise ValueError("Broker replacement exit differs from its renewed exact approval")
                    row["native_client_order_id"] = existing.get("native_client_order_id", native_id)
                    self._resize_exit(existing, row, parent)
                    continue
                expected_price = plan.get("take_profit") if role == "take_profit" else plan.get("stop_limit_price")
                if ((row.get("limit_price") is None) != (expected_price is None)
                        or expected_price is not None and Decimal(row["limit_price"]) != Decimal(expected_price)
                        or role == "stop_loss" and Decimal(row["stop_price"]) != Decimal(plan["stop_price"])):
                    raise ValueError("Broker-assigned exit prices differ from the exact approved group")
                quantity = Decimal(row["qty"])
                if not 0 < quantity <= Decimal(parent["terms"]["quantity"]) or quantity % 1:
                    raise ValueError("Broker exit quantity exceeds its approved entry or is not whole shares")
                terms = {**parent["terms"], "side": "SELL", "order_type": native_type(row["type"]), "quantity": row["qty"],
                         "limit_price": row.get("limit_price"), "stop_price": row.get("stop_price")}
                terms.pop("exit_plan", None)
                child = copy.deepcopy(parent)
                child.update(id=str(uuid4()), origin="linked_broker", submission_authority=False, linked_exit=True,
                    linked_entry_command_id=parent["id"], linked_role=role, terms=terms, terms_sha256=digest(terms),
                    client_order_id=row["client_order_id"], native_client_order_id=native_id, side="SELL",
                    state="submitting", filled_quantity="0", remaining_quantity=terms["quantity"], price_cap=None,
                    fee_commitment=None, cash_commitment="0", broker_order_ids=[row["id"]], fill_ids=[], event_ids=[],
                    native_deliveries={}, timeline=[{"at": datetime.now(UTC).isoformat(), "state": "submitting",
                        "reason": "Broker-assigned exit under the exact approved entry group; no independent submit authority"}],
                    transport_attempt={"version": 1, "state": "external_submission"})
                child["source_observation"] = {"order": copy.deepcopy(row), "parent_order_id": row["group_parent_id"],
                                               "native_epoch": self.native_epoch, "captured_at": datetime.now(UTC).isoformat()}
                child.pop("pending_action", None)
                child.pop("native_pending_commitment", None)
                commands[child["id"]] = child
        self.authority().transaction(change)

    @staticmethod
    def _resize_exit(command, row, parent):
        quantity, filled = Decimal(row["qty"]), Decimal(row["filled_qty"])
        ceiling = Decimal(command.get("broker_group_quantity", command["terms"]["quantity"]))
        if not 0 <= filled <= quantity <= min(ceiling, Decimal(parent["terms"]["quantity"])) or quantity <= 0 or quantity % 1:
            raise ValueError("Broker-managed exit quantity is outside its approved entry coverage")
        if ceiling != quantity:
            command["timeline"].append({"at": datetime.now(UTC).isoformat(), "reason": "Broker-managed linked exit quantity adjustment",
                                        "source": copy.deepcopy(row)})
            command["broker_group_quantity"] = str(quantity)
            command["remaining_quantity"] = str(quantity - filled)

    async def submit_group(self, native_command, factory):
        identity = (native_command.params or {}).get("durable_command_id")
        durable = self.command(identity, sending=True)
        from .linked_orders import native_group
        # Rebuild expected seeds through the same official factory and compare material terms/links.
        actual = list(native_command.order_list.orders)
        expected = native_group(factory, durable["terms"], durable["client_order_id"])
        from .native_types import native_dict
        keys = ("client_order_id", "instrument_id", "side", "type", "quantity", "price", "trigger_price", "time_in_force",
                "parent_order_id", "linked_order_ids", "order_list_id", "contingency_type", "emulation_trigger", "post_only",
                "reduce_only", "quote_quantity", "trigger_type", "tags")
        if len(actual) != len(expected.orders) or any(
                {key: native_dict(a).get(key) for key in keys} != {key: native_dict(e).get(key) for key in keys}
                for a, e in zip(actual, expected.orders)):
            raise ValueError("Native group differs from the exact approved entry and exit terms")
        self.checked_native_order(actual[0], durable)
        await self._submit(native_command, durable, actual)

    @staticmethod
    def native_applied(order, event, data, row, status, source_time, *, indexed_venue_id=None):
        from .native_types import native_dict, enum_name, native_order_account
        from .alpaca_reports import native_quantities
        total, cumulative = native_quantities(row)
        if row.get("type") == "trailing_stop":
            offset, unit = native_trail({"order_type": "TRAILING_STOP_MARKET", "quantity": row["qty"], "side": row["side"].upper(),
                "time_in_force": row["time_in_force"].upper(), "trail_price": row.get("trail_price"), "trail_percent": row.get("trail_percent")})
            actual = native_dict(order)
            if (actual.get("type") != "TRAILING_STOP_MARKET" or decimal(actual.get("trailing_offset")) != offset
                    or actual.get("trailing_offset_type") != unit):
                return False
        if event not in {"fill", "partial_fill", "replaced"} and (order.quantity.as_decimal() != total
                or (None if getattr(order, "price", None) is None else order.price.as_decimal()) != decimal(row.get("limit_price"))
                or (None if getattr(order, "trigger_price", None) is None else order.trigger_price.as_decimal()) != decimal(row.get("stop_price"))):
            return False
        if event in {"fill", "partial_fill"}:
            from .native_types import OrderFilled
            from .alpaca_reports import timestamp, execution_id
            return any(isinstance(fill, OrderFilled) and execution_id(fill.trade_id) == execution_id(data["execution_id"])
                and str(fill.account_id) == native_order_account(order)
                and str(fill.venue_order_id) == row["id"] and str(fill.instrument_id) == row["symbol"] + ".ALPACA"
                and enum_name(fill.order_side).lower() == row["side"] and fill.ts_event == timestamp(source_time)
                and fill.last_qty.as_decimal() == Decimal(str(data["qty"]))
                and fill.last_px.as_decimal() == Decimal(str(data["price"]))
                and (fill.commission is None if data.get("commission") is None else
                     fill.commission is not None and str(fill.commission.currency) == "USD"
                     and fill.commission.as_decimal() == Decimal(str(data["commission"]))) for fill in order.events)
        if status == "partially_filled" and cumulative == 0 and row.get("native_replacement_quantity_binding"):
            status = "accepted"
        if str(order.venue_order_id or indexed_venue_id or "") != row["id"]:
            return False
        if status == "submitting" and row.get("status") == "pending_new":
            return enum_name(order.status) == "SUBMITTED" and order.filled_qty.as_decimal() == cumulative
        if status == "cancel_pending" and event != "replacement_authoritative":
            return order.is_pending_cancel and order.filled_qty.as_decimal() == cumulative
        if status == "replace_pending" and event != "replacement_authoritative":
            return order.is_pending_update and order.filled_qty.as_decimal() == cumulative
        from .alpaca_reports import timestamp
        expected = {"order_cancel_rejected": "OrderCancelRejected", "order_replace_rejected": "OrderModifyRejected",
                    "replacement_authoritative": "OrderUpdated"}.get(event)
        expected = expected or {"accepted": "OrderAccepted", "canceled": "OrderCanceled", "expired": "OrderExpired", "rejected": "OrderRejected"}.get(status)
        filled = Decimal(0)
        for retained in order.events:
            if type(retained).__name__ == "OrderFilled":
                filled += retained.last_qty.as_decimal()
            if (expected and type(retained).__name__ == expected and retained.ts_event == timestamp(source_time)
                    and filled == cumulative):
                if event == "replacement_authoritative" and (retained.quantity.as_decimal() != Decimal(row["qty"])
                        or (None if retained.price is None else retained.price.as_decimal()) != (None if row.get("limit_price") is None else Decimal(row["limit_price"]))
                        or (None if retained.trigger_price is None else retained.trigger_price.as_decimal()) != (None if row.get("stop_price") is None else Decimal(row["stop_price"]))):
                    continue
                return True
        if event in {"order_cancel_rejected", "order_replace_rejected", "replacement_authoritative"}:
            return False
        native = native_dict(order)
        return (status in {"accepted", "partially_filled", "filled", "canceled", "expired", "rejected"}
                and native.get("status", "").lower() == status
                and Decimal(str(order.filled_qty.as_decimal())) == cumulative)

    async def submit(self, native_command):
        identity = (native_command.params or {}).get("durable_command_id")
        durable = self.command(identity, sending=True)
        self.checked_native_order(native_command.order, durable)
        if durable["terms"].get("exit_plan"):
            raise ValueError("An entry with exits must be submitted once as a native order list")
        await self._submit(native_command, durable, [native_command.order])

    async def _submit(self, native_command, durable, orders):
        identity = durable["id"]
        if account_version(self.observation()) != durable["account_version"]:
            raise ValueError("Source account version changed before native dispatch")
        terms = durable["terms"]
        self.require_package_valuation(durable)
        body = broker_payload(terms, durable["client_order_id"])
        self.record_pending(identity, "submitting", "Native adapter transport attempt begins after durable intent")
        if account_version(self.observation()) != durable["account_version"]:
            raise ValueError("Source account changed before native dispatch")
        self.authority().transport_boundary(identity, "submit")
        try:
            for order in orders:
                self.native.generate_order_submitted(order)
            result = await asyncio.to_thread(self.transport.submit_order, body)
            reference = self.receipt(identity, "Alpaca POST /v2/orders", {"request": body, "raw_response": result["raw"].decode()})
            self.record_pending(identity, "submitting", "HTTP response received; authoritative lifecycle confirmation remains required", reference)
            await self.handle_update({"stream": "trade_updates", "data": {"event": "rest_order_observation", "order": result["data"]}}, reference)
        except Exception as exc:
            self.record_pending(identity, "outcome_unknown", "Submit transport or mapping unresolved (" + type(exc).__name__ + "); never resubmit automatically")
            raise

    async def cancel(self, native_command):
        identity = (native_command.params or {}).get("durable_command_id")
        durable = self.command(identity)
        action = durable.get("pending_action", {})
        broker = str(native_command.venue_order_id or self.native.cache.venue_order_id(native_command.client_order_id) or "")
        if (action.get("kind") != "cancel" or not action.get("intent_at") or not action.get("actor")
                or action.get("broker_order_id") != broker or broker not in durable["broker_order_ids"]
                or str(native_command.client_order_id) != durable.get("native_client_order_id", durable["client_order_id"])):
            raise ValueError("Single-order cancellation requires explicit identity-bound durable authorization")
        self.record_pending(identity, "cancel_pending", "Durable cancel intent precedes DELETE")
        self.authority().transport_boundary(identity, "cancel")
        try:
            result = await asyncio.to_thread(self.transport.cancel_order, broker)
            reference = self.receipt(identity, "Alpaca DELETE single order", {"broker_order_id": broker, "raw_response": result["raw"].decode()})
            self.record_pending(identity, "cancel_pending", "Cancel HTTP acknowledgment does not prove cancellation", reference)
        except Exception as exc:
            self.record_pending(identity, "outcome_unknown", "Cancel outcome unresolved (" + type(exc).__name__ + ")")
            raise

    def require_package_valuation(self, command):
        if not is_package(command["terms"]):
            return
        from .linked_orders import validate_package_valuation

        value = self.native.prepare_package_valuation(command["terms"])
        validate_package_valuation(value, command["terms"], self.observation())
        if value["binding_sha256"] != command.get("package_valuation_binding_sha256"):
            raise ValueError("Actual package valuation/native cap inputs changed since exact approval")

    async def replace(self, native_command):
        parent_id = (native_command.params or {}).get("durable_command_id")
        parent = self.command(parent_id)
        action = parent.get("pending_action", {})
        child = self.command(action.get("replacement_command_id"), sending=True)
        funding_route = replacement_funding_route(child["terms"])
        if child.get("replacement_funding_basis") != (funding_route or {}).get("version"):
            raise ValueError("Replacement funding basis differs from exact admitted authority")
        self.checked_fractional_terms(child["terms"])
        self.require_package_valuation(child)
        broker = str(native_command.venue_order_id or self.native.cache.venue_order_id(native_command.client_order_id) or "")
        if (action.get("kind") != "replace" or not action.get("intent_at") or not action.get("actor")
                or action.get("broker_order_id") != broker or broker not in parent["broker_order_ids"]
                or child["instrument_id"] != parent["instrument_id"] or child["side"] != parent["side"]
                or child["terms"]["order_type"] != parent["terms"]["order_type"]
                or child["terms"].get("execution_profile", "long_only") != parent["terms"].get("execution_profile", "long_only")):
            raise ValueError("Replacement requires renewed admitted authority for the same supported instrument/side/type")
        predecessor = validated_replacement(child["terms"], self.observation())
        offset = Decimal(str((predecessor.get("native_replacement_quantity_binding") or {}).get("ancestor_filled_quantity", "0")))
        quantity = str(native_command.quantity.as_decimal() + offset) if native_command.quantity else parent["terms"]["quantity"]
        price = str(native_command.price.as_decimal()) if native_command.price else parent["terms"].get("limit_price")
        expected_price = child["terms"].get("limit_price")
        trigger = str(native_command.trigger_price.as_decimal()) if native_command.trigger_price else parent["terms"].get("stop_price")
        if (Decimal(quantity) != Decimal(child["terms"]["quantity"]) or (price is None) != (expected_price is None)
                or price is not None and (decimal(price) is None or decimal(expected_price) is None or decimal(price) != decimal(expected_price))
                or decimal(trigger) != decimal(child["terms"].get("stop_price"))):
            raise ValueError("Replacement terms differ from renewed exact review")
        body = {"qty": quantity, "client_order_id": child["client_order_id"]}
        if child["terms"].get("asset_class") == "us_option":
            body["time_in_force"] = child["terms"]["time_in_force"].lower()
        if price is not None:
            body["limit_price"] = price
        if trigger is not None:
            body["stop_price"] = trigger
        if predecessor.get("group_class") in {"bracket", "oco"} or Decimal(predecessor["qty"]) % 1:
            body.pop("qty")  # These amendments retain quantity and change prices only.
        self.record_pending(parent_id, "replace_pending", "Durable replacement intent precedes PATCH; original commitment retained")
        if account_version(self.observation()) != child["account_version"]:
            raise ValueError("Source account changed before native replacement")
        from .native_types import ClientOrderId
        native = self.native.cache.order(ClientOrderId(parent.get("native_client_order_id", parent["client_order_id"])))
        if (predecessor["id"] != broker or native is None
                or ("extended_hours" in (native.tags or [])) != (child["terms"].get("session", "regular") == "extended")
                or Decimal(str(predecessor["filled_qty"])) != native.filled_qty.as_decimal() + offset):
            raise ValueError("Replacement predecessor or cumulative native fills changed")
        self.authority().transport_boundary(parent_id, "replace")
        try:
            result = await asyncio.to_thread(self.transport.replace_order, broker, body, package=is_package(child["terms"]))
            reference = self.receipt(parent_id, "Alpaca PATCH single order", {"old_broker_order_id": broker,
                "replacement_funding_basis": child.get("replacement_funding_basis"),
                "broker_reservation_validation": copy.deepcopy(child.get("broker_reservation_validation")),
                "request": body, "raw_response": result["raw"].decode()})
            self.record_pending(parent_id, "replace_pending", "Replacement HTTP response retained; final replacement remains pending", reference)
        except Exception as exc:
            self.record_pending(parent_id, "outcome_unknown", "Replace outcome unresolved (" + type(exc).__name__ + ")")
            raise

    async def reconcile_identity(self, identity):
        from .alpaca_reports import order_report, exact, timestamp
        from .native_types import Price, Quantity
        durable = self.command(identity)
        progress = self.identity_reconciliation
        attempted = datetime.now(UTC).isoformat()
        progress["last_attempt_at"] = attempted
        if identity not in progress["pending"]:
            progress["pending"].append(identity)
        try:
            try:
                result = await asyncio.to_thread(self.transport.read_receipt, "/v2/orders:by_client_order_id?" + urlencode({"client_order_id": durable["client_order_id"]}))
            except HTTPError as exc:
                reason = "Broker identity is absent; absence never proves non-submission" if exc.code == 404 else "Identity lookup failed (HTTP " + str(exc.code) + "); connection or provider failure remains unresolved"
                self.native_gap(identity, reason)
                progress["unresolved"][identity] = {"reason": reason, "attempted_at": attempted}
                if exc.code == 404:
                    raise CommandIdentityUnresolved(reason) from None
                raise
            except (URLError, TimeoutError):
                progress["unresolved"][identity] = {"reason": "Identity lookup connection failed; no broker outcome is established", "attempted_at": attempted}
                raise
            reference = self.receipt(identity, "Alpaca client-order lookup", {"raw_response": result["raw"].decode()})
            row = result["data"]
            if is_package(durable["terms"]):
                if not isinstance(row, dict) or row.get("client_order_id") != durable["client_order_id"] or row.get("account_id", durable["account_id"]) != durable["account_id"]:
                    raise CommandIdentityUnresolved("Package lookup account/client identity differs; source retained")
                try:
                    package_observation(row, durable["terms"])
                except (ValueError, KeyError, TypeError, ArithmeticError):
                    raise CommandIdentityUnresolved("Package lookup members/terms are incomplete or differ; source retained") from None
                async with self.native.observation_lock:
                    await self.package_update({"event": "rest_order_observation", "order": row}, reference, durable)
                raise CommandIdentityUnresolved("Package identity observed; complete actual leg/native reconciliation is pending")
            if (not isinstance(row, dict) or any(not isinstance(row.get(key), str) for key in
                    ("id", "client_order_id", "symbol", "side", "qty", "filled_qty", "status", "type", "time_in_force", "created_at", "updated_at"))
                    or not row.get("id") or row["client_order_id"] != durable["client_order_id"]
                    or row["symbol"] != durable["symbol"] or row["side"].upper() != durable["side"]
                    or row.get("account_id", durable["account_id"]) != durable["account_id"]):
                self.native_gap(identity, "Broker identity lookup does not match the exact command/account/instrument", reference)
                raise CommandIdentityUnresolved("Broker identity response is malformed or differs from the exact command; outcome remains unknown")
            try:
                source_at = instant(row["updated_at"])
                filled = Decimal(row["filled_qty"])
                if not filled.is_finite() or not 0 <= filled <= Decimal(row["qty"]):
                    raise ValueError("Invalid cumulative fill")
                for leg in flatten_orders([row]):
                    if leg["status"] != "replaced":
                        order_report(leg, self.native.account_id, timestamp(row["updated_at"]))
                        continue
                    # Raw supersession requires handle_update's lineage proof; never fabricate a report status.
                    if (native_type(leg["type"]) not in {"MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT", "TRAILING_STOP_MARKET"}
                            or leg["id"] == row["id"] and native_type(leg["type"]) != durable["terms"]["order_type"]
                            or leg["time_in_force"] not in {"day", "gtc"}):
                        raise ValueError("Unsupported superseded order terms")
                    exact(Quantity.from_str, leg["qty"])
                    exact(Quantity.from_str, leg["filled_qty"])
                    timestamp(leg["created_at"])
                    timestamp(leg["updated_at"])
                    for key in {"limit": ("limit_price",), "stop": ("stop_price",), "stop_limit": ("limit_price", "stop_price")}.get(leg["type"], ()):
                        if exact(Price.from_str, leg[key]).as_decimal() <= 0:
                            raise ValueError("Invalid superseded order price")
                    if leg["type"] == "trailing_stop":
                        native_trail({"order_type": "TRAILING_STOP_MARKET", "quantity": leg["qty"], "side": leg["side"].upper(),
                            "time_in_force": leg["time_in_force"].upper(), "trail_price": leg.get("trail_price"), "trail_percent": leg.get("trail_percent")})
            except (ValueError, KeyError, TypeError, ArithmeticError):
                reason = "Broker identity response is malformed or unsupported; source receipt retained without native application"
                self.native_gap(identity, reason, reference)
                raise CommandIdentityUnresolved(reason) from None
            async with self.native.observation_lock:
                current = self.command(identity)
                if (filled < Decimal(current["filled_quantity"])
                        or any(item.get("source_at") and instant(item["source_at"]) > source_at for item in current["timeline"])):
                    raise CommandIdentityUnresolved("Lookup snapshot predates a later recorded command event; current authority and commitments are preserved")
                await self._handle_update({"stream": "trade_updates", "data": {"event": "rest_order_observation", "order": row}}, reference)
                current = self.command(identity)
                if any(item.get("status") not in CONFIRMED or item.get("native_epoch") != self.native_epoch
                       for item in current.get("native_deliveries", {}).values()):
                    raise CommandIdentityUnresolved("Broker identity observed; exact native application remains unresolved. Review the retained receipts before retrying reconciliation")
            progress["unresolved"].pop(identity, None)
        except CommandIdentityUnresolved as exc:
            progress["unresolved"][identity] = {"reason": str(exc), "attempted_at": attempted}
            raise
        finally:
            if identity in progress["pending"]:
                progress["pending"].remove(identity)

    async def reconcile_stream_commands(self, identities):
        """One sequential pass per socket connection; only explicit command gaps are isolated."""
        for identity in identities:
            try:
                await self.reconcile_identity(identity)
            except CommandIdentityUnresolved:
                continue

    async def handle_update(self, message, reference=None, **kwargs):
        async with self.native.observation_lock:
            return await self._handle_update(message, reference, **kwargs)

    async def package_update(self, data, reference, command):
        row = data["order"]
        identity = "package-source:" + digest(data)
        self.delivery(command["id"], identity, data, reference, "unresolved")
        self.native.observation_dirty = True
        if row.get("account_id", command["account_id"]) != command["account_id"] or str(self.native.account_id) != "ALPACA-" + command["account_id"]:
            self.native_gap(command["id"], "Package update account differs; raw source retained", reference)
            return
        if row.get("order_class") != "mleg":
            # Actual leg executions are replayed once from the retained account history,
            # with correction/causal checks, never from a parent aggregate price.
            self.native_gap(command["id"], "Actual package leg update awaits complete source/native reconciliation", reference)
            return
        try:
            mapped = package_observation(row, command["terms"])
            self.bind_package(mapped)
        except (ValueError, KeyError, TypeError, ArithmeticError):
            self.native_gap(command["id"], "Package source members/terms differ or are incomplete; raw receipt retained", reference)
            return
        states = {"new": "accepted", "accepted": "accepted", "held": "accepted", "accepted_for_bidding": "accepted",
            "done_for_day": "partially_filled" if Decimal(row["filled_qty"]) else "accepted", "pending_new": "submitting",
            "partially_filled": "partially_filled", "filled": "filled", "canceled": "canceled", "expired": "expired",
            "rejected": "rejected", "pending_cancel": "cancel_pending", "pending_replace": "replace_pending", "replaced": "canceled"}
        state = states.get(row.get("status"))
        if state:
            self.authority().apply_report(command["id"], {"authoritative": True, "event_id": identity, "receipt": reference,
                "account_id": command["account_id"], "client_order_id": command["client_order_id"], "instrument_id": command["instrument_id"],
                "broker_order_id": row["id"], "filled_quantity": row["filled_qty"], "state": state,
                "source_at": data.get("timestamp") or row["updated_at"], "fill_ids": [], "commission": None,
                "package_control_only": True})
        self.native_gap(command["id"], "Package parent observed; actual leg/native execution coverage awaits fresh reconciliation", reference)
        if row.get("status") == "replaced":
            action = command.get("pending_action") or {}
            child = self.command(action["replacement_command_id"]) if action.get("replacement_command_id") else None
            if child is None or not row.get("replaced_by"):
                return
            response = await asyncio.to_thread(self.transport.read_receipt, "/v2/orders/" + row["replaced_by"] + "?nested=true")
            successor = response["data"]
            source = self.receipt(child["id"], "Actual package replacement successor", {"predecessor": reference, "raw_response": response["raw"].decode()})
            if successor.get("id") != row["replaced_by"] or successor.get("replaces") != row["id"] or successor.get("client_order_id") != child["client_order_id"]:
                self.native_gap(child["id"], "Package successor identity/lineage differs; no retry", source)
                return
            await self.package_update({"event": "replacement_authoritative", "order": successor}, source, child)

    async def _handle_update(self, message, reference=None, *, replacement_predecessor=None, replacement_source=None, replacement_execution=None):
        from .alpaca_reports import exact, execution_id, fill_commission, market_replacement_binding, native_quantities, timestamp
        from .native_types import ClientOrderId, LiquiditySide, Money, Price, Quantity, TradeId, VenueOrderId, native_order_account

        data = message.get("data", {})
        canonical = execution_id(data["execution_id"]) if data.get("execution_id") else None
        fee_source = getattr(self.native, "recovery_fee_sources", {}).get(canonical)
        effective_data = data
        row = data.get("order") or {}
        reference = reference or self.receipt("broker-observation", "Alpaca trade update before native interpretation",
            {"message": message, "native_account_id": str(self.native.account_id)})
        commands = self.authority().snapshot()["data"]["commands"]
        packages = [command for command in commands.values() if is_package(command.get("terms", {})) and
            (row.get("client_order_id") == command.get("client_order_id") or row.get("id") in command.get("broker_order_ids", [])
             or any(member.get("id") == row.get("id") for member in command.get("package_members", [])))]
        if len(packages) == 1:
            await self.package_update(data, reference, packages[0])
            return
        if row:
            _, unsupported = observed_orders([row], commands.values())
            if unsupported:
                self.native.record_unsupported_event(row, reference)
                return
        if row.get("legs"):
            flattened = flatten_orders([row])
            self.bind_group(flattened)
            for leg in flattened:
                leg_data = {**data, "order": leg} if leg["id"] == row["id"] else {"event": "rest_order_observation", "order": leg}
                await self._handle_update({**message, "data": leg_data}, reference,
                    replacement_predecessor=replacement_predecessor if leg["id"] == row["id"] else None,
                    replacement_source=replacement_source if leg["id"] == row["id"] else None,
                    replacement_execution=replacement_execution if leg["id"] == row["id"] else None)
            return
        authority = self.authority()
        state = authority.snapshot()["data"]
        durable = next((c for c in state["commands"].values() if row.get("client_order_id") == c["client_order_id"] or row.get("id") in c["broker_order_ids"]), None)
        if not durable:
            return
        if durable.get("linked_exit"):
            def resize(records):
                commands = records["commands"]["commands"]
                self._resize_exit(commands[durable["id"]], row, commands[durable["linked_entry_command_id"]])
            authority.transaction(resize)
            durable = self.command(durable["id"])
        if (data.get("event") in {"fill", "partial_fill"} and (row.get("type") == "market" or row.get("asset_class") == "us_option")
                and row.get("replaces") and not durable.get("native_replacement_quantity_binding")):
            response = await asyncio.to_thread(self.transport.read_receipt, "/v2/orders/" + row["replaces"])
            predecessor = response["data"]
            parent = next((item for item in state["commands"].values() if predecessor.get("id") in item.get("broker_order_ids", [])
                and (item.get("pending_action") or {}).get("replacement_command_id") == durable["id"]), None)
            if parent is None or predecessor.get("replaced_by") != row.get("id"):
                raise ValueError("Incoming MARKET successor fill has no confirmed command/predecessor chain")
            evidence = self.receipt(durable["id"], "MARKET successor source and actual incoming execution",
                {"predecessor": response["raw"].decode(), "execution": message})
            await self._handle_update({"stream": "trade_updates", "data": {"event": "replacement_authoritative",
                "order": row, "timestamp": row["updated_at"]}}, evidence, replacement_predecessor=predecessor["id"],
                replacement_source={**predecessor, "native_client_order_id": parent.get("native_client_order_id", parent["client_order_id"]),
                    **({"native_replacement_quantity_binding": parent["native_replacement_quantity_binding"]} if parent.get("native_replacement_quantity_binding") else {})},
                replacement_execution=data)
            durable = self.command(durable["id"])
        if durable.get("native_replacement_quantity_binding"):
            row = {**row, "native_replacement_quantity_binding": durable["native_replacement_quantity_binding"]}
        if row.get("symbol") != durable["symbol"] or row.get("side", "").upper() != durable["side"]:
            reason = "Trade update does not match durable instrument/side identity; source retained without native application"
            reference = reference or self.receipt(durable["id"], "Alpaca trade-update identity gap", message)
            self.native_gap(durable["id"], reason, reference)
            raise CommandIdentityUnresolved(reason)
        if durable["terms"].get("asset_class") == "us_option":
            if row.get("asset_class") != "us_option" or row.get("position_intent") != durable["terms"]["position_intent"]:
                raise CommandIdentityUnresolved("Broker option intent or class differs from exact authority")
            row = {**row, "option_contract": durable["terms"]["option_contract"]}
        event = data.get("event")
        identity = data.get("event_id") or data.get("execution_id") or "source-sha256:" + digest(data)
        reference = reference or self.receipt(durable["id"], "Alpaca paper trade_updates", message)
        source = (self.path.parent / reference["path"]).resolve()
        if not source.is_relative_to(self.path.parent.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest() != reference["sha256"]:
            raise ValueError("Native source receipt is missing, changed or outside its boundary")
        delivery = self.delivery(durable["id"], identity, data, reference)
        if delivery["status"] == "conflict":
            return
        try:
            if fee_source:
                if data.get("commission") is not None and not fee_source.get("modeled") and Decimal(str(data["commission"])) != Decimal(fee_source["amount"]):
                    raise ValueError("Receipt commission conflicts with its recovered source amount")
                expected = {"execution_id": canonical, "account_id": "ALPACA-" + durable["account_id"],
                            "instrument_id": durable["instrument_id"], "order_id": row.get("id"), "side": row.get("side")}
                if (any(fee_source.get(key) != value for key, value in expected.items()) or fee_source.get("currency") != str(self.native.base_currency)
                        or Decimal(str(data.get("qty"))) != Decimal(fee_source["qty"])
                        or Decimal(str(data.get("price"))) != Decimal(fee_source["price"])
                        or timestamp(data.get("timestamp") or row.get("updated_at")) != fee_source.get("ts_event")):
                    raise ValueError("Effective fee provenance does not match the exact execution/account/currency")
                evidence = fee_source.get("history_receipt")
                if not evidence:
                    raise ValueError("Effective fee has no retained source receipt")
                source = (self.path.parent / evidence["path"]).resolve()
                if not source.is_relative_to(self.path.parent.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest() != evidence["sha256"]:
                    raise ValueError("Effective fee source receipt is missing or changed")
            if (data.get("commission_currency") or data.get("currency") or str(self.native.base_currency)) != str(self.native.base_currency):
                raise ValueError("Receipt fee currency is unsupported; no FX conversion")
            if durable["terms"]["order_type"] == "TRAILING_STOP_MARKET":
                if (row.get("type") != "trailing_stop" or row.get("time_in_force", "").upper() != durable["terms"]["time_in_force"]
                        or Decimal(row["qty"]) != Decimal(durable["terms"]["quantity"])
                        or any(decimal(row.get(key)) != decimal(durable["terms"].get(key)) for key in ("trail_price", "trail_percent"))):
                    raise ValueError("Broker trailing identity, initial distance or quantity differs from approved terms")
            if broker_session(row) != durable["terms"].get("session", "regular"):
                raise ValueError("Broker execution-session eligibility differs from approved terms")
            if durable["terms"].get("asset_class") == "us_option" and (
                    native_type(row.get("type")) != durable["terms"]["order_type"]
                    or str(row.get("time_in_force", "")).upper() != durable["terms"]["time_in_force"]
                    or Decimal(row["qty"]) != Decimal(durable["terms"]["quantity"])
                    or any(decimal(row.get(key)) != decimal(durable["terms"].get(key)) for key in ("limit_price", "stop_price"))):
                raise ValueError("Broker option type, duration, quantity or premium terms differ from exact authority")
            quantity = exact(Quantity.from_str, data["qty"]) if data.get("qty") is not None else None
            price = exact(Price.from_str, data["price"]) if data.get("price") is not None else None
            if quantity is not None and quantity.as_decimal() <= 0 or price is not None and price.as_decimal() <= 0:
                raise ValueError("Nonpositive receipt quantity or price")
            if event in {"fill", "partial_fill"}:
                if not data.get("execution_id") or quantity is None or price is None:
                    raise ValueError("Missing fill identity or economics")
                commission, provenance = fill_commission({**data, "id": data["execution_id"],
                        "symbol": row["symbol"], "side": row["side"], "transaction_time": data.get("timestamp") or row.get("updated_at")},
                        row, self.native.account_id, self.native.base_currency, endpoint=self.transport.connection.endpoint,
                        account=getattr(self.native, "fee_model_account", None), linked=fee_source)
                effective_data = {**data, "commission": str(commission.as_decimal()), "native_fee": provenance}
                trade_id = TradeId(canonical)
            if event == "replacement_authoritative":
                if not replacement_predecessor or row.get("replaces") != replacement_predecessor or row.get("id") == replacement_predecessor:
                    raise ValueError("Replacement update requires a validated distinct successor chain")
                if (native_type(row.get("type")) != durable["terms"]["order_type"]
                        or decimal(row.get("limit_price")) != decimal(durable["terms"].get("limit_price"))
                        or decimal(row.get("stop_price")) != decimal(durable["terms"].get("stop_price"))):
                    raise ValueError("Replacement source prices or type differ from the renewed exact approval")
                updated_quantity = exact(Quantity.from_str, row["qty"])
                updated_price = exact(Price.from_str, row["limit_price"]) if row.get("limit_price") is not None else None
                if updated_quantity.as_decimal() <= 0 or updated_price is not None and updated_price.as_decimal() <= 0:
                    raise ValueError("Nonpositive replacement quantity or price")
        except (ValueError, KeyError, TypeError, ArithmeticError):
            self.delivery(durable["id"], identity, data, reference, "unresolved")
            self.native_gap(durable["id"], "Source economics or fill identity are missing, invalid or unrepresentable exactly; native application blocked", reference)
            return
        replacement = None
        if event == "replaced":
            action = durable.get("pending_action", {})
            child = state["commands"].get(action.get("replacement_command_id"))
            if not row.get("replaced_by") or child is None:
                self.record_pending(durable["id"], "outcome_unknown", "Replacement successor identity is unresolved", reference)
                return
            response = await asyncio.to_thread(self.transport.read_receipt, "/v2/orders/" + row["replaced_by"])
            replacement = response["data"]
            if (replacement.get("id") != row["replaced_by"] or replacement.get("id") == row["id"]
                    or replacement.get("client_order_id") != child["client_order_id"] or replacement.get("replaces") != row["id"]
                    or replacement.get("symbol") != durable["symbol"] or replacement.get("side", "").upper() != durable["side"]):
                self.record_pending(durable["id"], "outcome_unknown", "Replacement chain identities differ", reference)
                return
            successor_reference = self.receipt(child["id"], "authoritative replacement successor lookup",
                {"predecessor_receipt": reference, "raw_response": response["raw"].decode()})
        states = {"new": "accepted", "accepted": "accepted", "held": "accepted", "done_for_day": "accepted", "pending_new": "submitting", "partially_filled": "partially_filled",
                  "filled": "filled", "canceled": "canceled", "expired": "expired", "rejected": "rejected",
                  "pending_cancel": "cancel_pending", "pending_replace": "replace_pending"}
        status = states.get(row.get("status"))
        if row.get("status") == "done_for_day" and Decimal(row["filled_qty"]):
            status = "partially_filled"
        if event in {"order_cancel_rejected", "order_replace_rejected"}:
            status = "partially_filled" if Decimal(row["filled_qty"]) else "accepted"
        if event == "replaced" or row.get("status") == "replaced":
            status = "canceled"  # Authoritative supersession closes only the old order remainder.
        if status is None:
            self.record_pending(durable["id"], "outcome_unknown", "Unsupported lifecycle event retained", reference)
            return
        source_time = data.get("timestamp") or row.get("updated_at") or row.get("created_at")
        report = {"authoritative": True, "event_id": identity, "receipt": reference, "account_id": durable["account_id"],
                  "client_order_id": durable["client_order_id"], "instrument_id": durable["instrument_id"],
                  "broker_order_id": row["id"], "filled_quantity": row["filled_qty"], "state": status,
                  "source_at": source_time, "fill_ids": [canonical] if canonical else [],
                  "commission": data.get("commission"), "native_fee": effective_data.get("native_fee"),
                  "raw_execution_id": data.get("execution_id"), "raw_client_order_id": row.get("client_order_id")}
        if identity not in durable["event_ids"]:
            authority.apply_report(durable["id"], report)
        if event in {"order_cancel_rejected", "order_replace_rejected", "replaced"} or status in {"filled", "canceled", "rejected", "expired"}:
            def complete_action(records):
                command = records["commands"]["commands"][durable["id"]]
                action = command.get("pending_action")
                if action and action.get("broker_order_id") == row["id"]:
                    action.update(state="completed", outcome_event_id=identity, outcome_receipt=reference)
            authority.transaction(complete_action)
        if event == "order_replace_rejected":
            child = state["commands"].get(durable.get("pending_action", {}).get("replacement_command_id"))
            if child:
                authority.apply_report(child["id"], {**report, "event_id": identity + ":replacement-rejected",
                    "client_order_id": child["client_order_id"], "filled_quantity": "0", "state": "rejected", "broker_order_id": None})
        if replacement:
            successor_data = {"event": "replacement_authoritative", "order": replacement, "timestamp": replacement["updated_at"]}
            await self._handle_update({"stream": "trade_updates", "data": successor_data},
                successor_reference, replacement_predecessor=row["id"],
                replacement_source={**row, "native_client_order_id": durable.get("native_client_order_id", durable["client_order_id"])})
        if event == "replacement_authoritative" and (row.get("type") == "market" or row.get("asset_class") == "us_option"):
            if not replacement_source or replacement_source.get("replaced_by") != row["id"]:
                raise ValueError("MARKET successor requires confirmed predecessor source")
            from .native_recovery import collect_history
            through = datetime.now(UTC).isoformat()
            try:
                fills, _, history = await collect_history(self, self.native.fee_model_account, through, self.native.history_cache)
                if replacement_execution:
                    incoming = {"id": replacement_execution["execution_id"], "order_id": row["id"], "symbol": row["symbol"],
                        "side": row["side"], "qty": replacement_execution["qty"], "price": replacement_execution["price"],
                        "transaction_time": replacement_execution["timestamp"]}
                    matches = [fill for fill in fills if execution_id(fill.get("execution_id") or fill["id"]) == execution_id(incoming["id"])]
                    if matches:
                        if any(any(str(fill[key]) != str(incoming[key]) for key in ("order_id", "symbol", "side"))
                            or any(Decimal(str(fill[key])) != Decimal(str(incoming[key])) for key in ("qty", "price"))
                            or timestamp(fill["transaction_time"]) != timestamp(incoming["transaction_time"]) for fill in matches):
                            raise ValueError("Incoming execution conflicts with collected broker activity")
                    else:
                        fills.append(incoming)
                ancestors = {replacement_source["id"]: replacement_source}
                parent = replacement_source
                while parent.get("replaces"):
                    response = await asyncio.to_thread(self.transport.read_receipt, "/v2/orders/" + parent["replaces"])
                    prior = response["data"]
                    if (prior.get("id") != parent["replaces"] or prior.get("replaced_by") != parent["id"]
                            or any(prior.get(key) != row.get(key) for key in ("symbol", "side", "type", "asset_class", "position_intent"))
                            or prior["id"] in ancestors):
                        raise ValueError("MARKET ancestor source chain differs")
                    ancestors[prior["id"]] = prior
                    parent = prior
                binding = market_replacement_binding(row, list(ancestors.values()), fills, history)
                if replacement_execution:
                    binding["incoming_execution_receipt"] = reference
            except (ValueError, KeyError, TypeError, ArithmeticError):
                self.delivery(durable["id"], identity, data, reference, "unresolved")
                self.native_gap(durable["id"], "MARKET replacement quantity inheritance is unproven; raw broker facts retained", reference)
                return
            row = {**row, "native_replacement_quantity_binding": binding}
            predecessor = self.native.cache.order(ClientOrderId(replacement_source["native_client_order_id"]))
            def bind_successor(records):
                command = records["commands"]["commands"][durable["id"]]
                command.update(native_client_order_id=row["client_order_id"],
                    native_quantity_offset=binding["ancestor_filled_quantity"], native_replacement_quantity_binding=binding)
            native_quantities(row)  # Validate source translation before retaining confirmed successor identity.
            authority.transaction(bind_successor)
            try:
                order = await self.native.observe_market_successor(row, predecessor, replacement_source)
            except (ValueError, KeyError, TypeError, ArithmeticError):
                self.delivery(durable["id"], identity, data, reference, "unresolved")
                self.native_gap(durable["id"], "MARKET replacement waits for exact predecessor/successor native facts", reference)
                return
            proven = self.native_applied(order, "market_replacement_observation", effective_data, row, status, source_time,
                indexed_venue_id=self.native.cache.venue_order_id(order.client_order_id))
            self.delivery(durable["id"], identity, data, reference, "observed_current_process" if proven else "unresolved")
            if not proven:
                self.native_gap(durable["id"], "Actual MARKET successor executions require native confirmation; no ancestor fill is replayed", reference)
            return
        native_id = durable.get("native_client_order_id", durable["client_order_id"])
        order = self.native.cache.order(ClientOrderId(native_id))
        if order is None:
            self.native_gap(durable["id"], "Native order is absent; reconstruction requires authoritative reports", reference)
            return
        if (str(order.instrument_id) != durable["instrument_id"] or str(order.client_order_id) != native_id
                or native_order_account(order, self.native) != "ALPACA-" + durable["account_id"]
                or str(self.native.account_id) != "ALPACA-" + durable["account_id"]):
            self.delivery(durable["id"], identity, data, reference, "unresolved")
            self.native_gap(durable["id"], "Native order account/instrument/client identity differs from the authoritative command", reference)
            return
        if order.venue_order_id is None and status in {"submitting", "cancel_pending", "replace_pending"}:
            self.native.cache.add_venue_order_id(order.client_order_id, VenueOrderId(row["id"]))
        if replacement:
            successor_delivery = self.command(child["id"]).get("native_deliveries", {}).get("source-sha256:" + digest(successor_data), {})
            child = self.command(child["id"])
            market_confirmed = ((replacement.get("type") == "market" or replacement.get("asset_class") == "us_option") and order.is_closed
                and child.get("native_client_order_id") == replacement["client_order_id"]
                and self.native_applied(order, "replaced", data, row, status, source_time,
                    indexed_venue_id=self.native.cache.venue_order_id(order.client_order_id)))
            if ((market_confirmed or child.get("native_client_order_id", child["client_order_id"]) == native_id)
                    and successor_delivery.get("status") == "observed_current_process" and successor_delivery.get("native_epoch") == self.native_epoch
                    and (market_confirmed or self.native_applied(order, "replacement_authoritative", successor_data, replacement,
                                            states.get(replacement.get("status")), replacement["updated_at"],
                                            indexed_venue_id=self.native.cache.venue_order_id(order.client_order_id)))):
                self.delivery(durable["id"], identity, data, reference, "observed_current_process")
            else:
                self.delivery(durable["id"], identity, data, reference, "unresolved")
                self.native_gap(durable["id"], "Predecessor supersession lacks current native successor-update confirmation", reference)
            return
        if self.native_applied(order, event, effective_data, row, status, source_time,
                               indexed_venue_id=self.native.cache.venue_order_id(order.client_order_id)):
            self.delivery(durable["id"], identity, data, reference, "observed_current_process")
            if event in {"fill", "partial_fill"}:
                self.resolve_market_replacement_receipts()
            return
        if event in {"fill", "partial_fill"} and canonical in {execution_id(item) for item in order.trade_ids}:
            self.delivery(durable["id"], identity, data, reference, "conflict")
            self.native_gap(durable["id"], "Native trade identity exists with unproven or conflicting fill economics; no duplicate application", reference)
            return
        if delivery.get("native_epoch") != self.native_epoch:
            self.native_gap(durable["id"], "Persisted receipt lacks proven native application; historical replay beside reconciled positions is unsupported", reference)
            return
        if delivery["status"] in {"applied", "intent", "unresolved"}:
            self.native_gap(durable["id"], "Prior native delivery has no proven completion; reconcile native identity without replay", reference)
            return
        if event in {"fill", "partial_fill"} and Decimal(str(order.filled_qty.as_decimal())) + Decimal(str(data["qty"])) != native_quantities(row)[1]:
            self.native_gap(durable["id"], "Native fill sequence differs from broker cumulative quantity; no residual fill is inferred", reference)
            return
        if event == "replacement_authoritative" and str(order.venue_order_id or "") != replacement_predecessor:
            self.native_gap(durable["id"], "Native predecessor venue identity differs from the validated replacement chain", reference)
            return
        venue_id, ts = VenueOrderId(row["id"]), timestamp(source_time)
        self.delivery(durable["id"], identity, data, reference, "intent")
        if event in {"fill", "partial_fill"}:
            try:
                self.require_causal_fill(row, canonical)
            except ValueError as exc:
                self.native_gap(durable["id"], str(exc), reference)
                return
            self.native.observation_dirty = True
            self.native.generate_order_filled(order, venue_id, None, trade_id, quantity,
                price, self.native.base_currency, commission, LiquiditySide.NO_LIQUIDITY_SIDE, ts)
        elif event == "order_cancel_rejected":
            self.native.generate_order_cancel_rejected(order, venue_id, "Broker rejected cancellation", ts)
        elif event == "order_replace_rejected":
            self.native.generate_order_modify_rejected(order, venue_id, "Broker rejected replacement; original remains authoritative", ts)
        elif event == "replacement_authoritative":
            self.native.generate_order_updated(order, venue_id, updated_quantity, updated_price,
                exact(Price.from_str, row["stop_price"]) if row.get("stop_price") is not None else None,
                None, ts, venue_order_id_modified=True)
        elif status in {"cancel_pending", "replace_pending"}:
            self.native.generate_observed_pending(order, venue_id, "PENDING_CANCEL" if status == "cancel_pending" else "PENDING_UPDATE", ts)
        elif status == "accepted":
            if row.get("type") == "trailing_stop":
                if order.venue_order_id is None:
                    self.native.generate_order_accepted(order, venue_id, ts)
                if row.get("stop_price") is not None:
                    self.native.generate_order_updated(order, venue_id, exact(Quantity.from_str, row["qty"]), None,
                        exact(Price.from_str, row["stop_price"]), False, ts)
            elif durable.get("linked_exit") and order.venue_order_id is not None:
                self.native.generate_order_updated(order, venue_id, exact(Quantity.from_str, row["qty"]),
                    exact(Price.from_str, row["limit_price"]) if row.get("limit_price") is not None else None,
                    exact(Price.from_str, row["stop_price"]) if row.get("stop_price") is not None else None, False, ts)
            else:
                self.native.generate_order_accepted(order, venue_id, ts)
        elif status == "canceled" and event != "replaced":
            self.native.generate_order_canceled(order, venue_id, ts)
        elif status == "expired":
            self.native.generate_order_expired(order, venue_id, ts)
        elif status == "rejected":
            self.native.generate_order_rejected(order, "Broker rejected order", ts, False)
        else:
            self.delivery(durable["id"], identity, data, reference, "unresolved")
            return
        for _ in range(20):
            observed = self.native.cache.order(ClientOrderId(native_id))
            if observed and self.native_applied(observed, event, effective_data, row, status, source_time,
                                                indexed_venue_id=self.native.cache.venue_order_id(observed.client_order_id)):
                self.delivery(durable["id"], identity, data, reference, "observed_current_process")
                if event in {"fill", "partial_fill"}:
                    self.resolve_market_replacement_receipts()
                break
            await asyncio.sleep(0.05)

    async def stream(self):
        delay = 1
        while True:
            socket = PaperStream()
            receive_task = recovery_task = None
            try:
                self.stream_status = {"state": "connecting", "gap": "Reconnection requires identity reconciliation; no submission retry",
                                      "identity_reconciliation": self.identity_reconciliation}
                await socket.connect(self.transport.connection)
                identities = [command["id"] for command in self.authority().snapshot()["data"]["commands"].values()
                    if command["dispatch_intent_at"] and command["state"] not in {"filled", "canceled", "rejected", "expired", "not_sent"}
                    or any(item.get("status") not in CONFIRMED or item.get("native_epoch") != self.native_epoch for item in command.get("native_deliveries", {}).values())]
                self.stream_status = {"state": "listening", "connected_at": datetime.now(UTC).isoformat(),
                    "gap": "Prior disconnected interval is not claimed observed; unresolved command identities remain separate",
                    "identity_reconciliation": self.identity_reconciliation}
                recovery_task = asyncio.create_task(self.reconcile_stream_commands(identities))
                receive_task = asyncio.create_task(asyncio.wait_for(socket.receive(), 90))
                delay = 1
                while True:
                    done, _ = await asyncio.wait([task for task in (receive_task, recovery_task) if task is not None], return_when=asyncio.FIRST_COMPLETED)
                    if recovery_task in done:
                        recovery_task.result()  # Shared auth/network/storage failures must reach the connection boundary.
                        recovery_task = None
                    if receive_task not in done:
                        continue
                    message = receive_task.result()
                    receive_task = asyncio.create_task(asyncio.wait_for(socket.receive(), 90))
                    if message.get("stream") == "trade_updates":
                        try:
                            async with self.native.observation_lock:
                                await self._handle_update(message)
                        except CommandIdentityUnresolved:
                            continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.stream_status = {"state": "disconnected", "at": datetime.now(UTC).isoformat(),
                    "gap": "Trade updates unavailable (" + type(exc).__name__ + "); outstanding identities remain unresolved",
                    "identity_reconciliation": self.identity_reconciliation}
            finally:
                tasks = [task for task in (receive_task, recovery_task) if task is not None]
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                await socket.close()
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)
