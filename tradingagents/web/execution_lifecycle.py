"""Nautilus adapter lifecycle over durable authority. No browser transport entry point."""

import asyncio
import copy
import hashlib
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from .admission import DEFAULT, CommandAdmission, account_version, instant
from .alpaca_readonly import AlpacaREST, trading_endpoint
from .alpaca_stream import PaperStream
from .app_database import ApplicationDatabase
from .investor import decimal, digest, validated_replacement

class ExecutionLifecycle:
    def __init__(self, native, database_path, credentials_file, observation, assets, *, native_epoch):
        self.native, self.path = native, Path(database_path) if database_path else None
        self.credentials_file, self.observation, self.assets = credentials_file, observation, assets
        self.native_epoch = native_epoch
        self.database = None
        self.transport = AlpacaREST(credentials_file, permit_paper_execution=True)
        self.stream_status = {"state": "not_started", "gap": "Trade stream awaits the native account connection"}
        if self.path and self.path.is_file():
            self.begin_native_epoch()

    @staticmethod
    def retain_commitment(command, item):
        reservation = item.get("pending_commitment")
        if reservation is None:
            cap, fee = decimal(command.get("price_cap")), decimal(command.get("fee_commitment"))
            principal = Decimal(command["terms"]["quantity"]) * cap if cap is not None else None
            cash = principal + (fee or Decimal(0)) if command["side"] == "BUY" and principal is not None else None if command["side"] == "BUY" else fee or Decimal(0)
            reservation = {"cash_commitment": None if cash is None else str(cash), "remaining_quantity": command["terms"]["quantity"]}
        pending = command.setdefault("native_pending_commitment", {})
        for key, value in reservation.items():
            prior = pending.get(key, "0")
            pending[key] = None if prior is None or value is None else str(max(Decimal(prior), Decimal(value)))

    def begin_native_epoch(self):
        def change(records):
            state = records["commands"]
            state["native_epoch"] = self.native_epoch
            for command in state["commands"].values():
                for item in command.get("native_deliveries", {}).values():
                    if item.get("status") in {"applied", "observed_current_process"} and item.get("native_epoch") != self.native_epoch:
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
        if sending and command.get("origin") == "external_broker":
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
                if pending["status"] != "observed_current_process" or pending.get("native_epoch") != self.native_epoch:
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
                        or row.get("type") != "market" or row.get("status") not in {"partially_filled", "filled"}):
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
                            or enum_name(order.order_type) != "MARKET" or order.quantity.as_decimal() != quantity):
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
                 "native_epoch": item.get("native_epoch"), "confirmed_current_process": item["status"] == "observed_current_process" and item.get("native_epoch") == self.native_epoch,
                 "source_receipt": item["receipt"], "commission": item.get("input", {}).get("commission")}
                for command in commands.values() for identity, item in command.get("native_deliveries", {}).items()]

    def native_gap(self, identity, reason, receipt=None):
        def change(records):
            state = records["commands"]
            state.update(recovery_required=True, recovery_reason=reason)
            state["commands"][identity]["timeline"].append({"at": datetime.now(UTC).isoformat(),
                "native_application": "unresolved", "reason": reason, "receipt": receipt})
        self.authority().transaction(change)

    def checked_native_order(self, order, durable):
        terms = durable["terms"]
        from .native_types import native_dict, enum_name
        raw = native_dict(order)
        if (str(order.instrument_id) != durable["instrument_id"] or str(order.client_order_id) != durable.get("native_client_order_id", durable["client_order_id"])
                or enum_name(order.side) != terms["side"] or enum_name(order.order_type) != terms["order_type"]
                or enum_name(order.time_in_force) != "DAY" or order.is_quote_quantity or order.is_reduce_only
                or self.assets().get(terms["symbol"], {}).get("tradable") is not True):
            raise ValueError("Unsupported native order or exact durable identity/terms mismatch")
        if Decimal(raw["quantity"]) != Decimal(terms["quantity"]):
            raise ValueError("Native and reviewed quantities differ")
        if terms["order_type"] == "LIMIT" and Decimal(raw["price"]) != Decimal(terms["limit_price"]):
            raise ValueError("Native and reviewed limit prices differ")

    @staticmethod
    def native_applied(order, event, data, row, status, source_time, *, indexed_venue_id=None):
        from .native_types import native_dict, enum_name, native_order_account
        from .alpaca_reports import native_quantities
        _, cumulative = native_quantities(row)
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
                        or (None if retained.price is None else retained.price.as_decimal()) != (None if row.get("limit_price") is None else Decimal(row["limit_price"]))):
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
        if account_version(self.observation()) != durable["account_version"]:
            raise ValueError("Source account version changed before native dispatch")
        terms = durable["terms"]
        body = {"symbol": terms["symbol"], "qty": terms["quantity"], "side": terms["side"].lower(),
                "type": terms["order_type"].lower(), "time_in_force": "day", "extended_hours": False,
                "client_order_id": durable["client_order_id"]}
        if terms["order_type"] == "LIMIT":
            body["limit_price"] = terms["limit_price"]
        self.record_pending(identity, "submitting", "Native adapter transport attempt begins after durable intent")
        if account_version(self.observation()) != durable["account_version"]:
            raise ValueError("Source account changed before native dispatch")
        self.authority().transport_boundary(identity, "submit")
        try:
            self.native.generate_order_submitted(native_command.order)
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

    async def replace(self, native_command):
        parent_id = (native_command.params or {}).get("durable_command_id")
        parent = self.command(parent_id)
        action = parent.get("pending_action", {})
        child = self.command(action.get("replacement_command_id"), sending=True)
        broker = str(native_command.venue_order_id or self.native.cache.venue_order_id(native_command.client_order_id) or "")
        if (action.get("kind") != "replace" or not action.get("intent_at") or not action.get("actor")
                or action.get("broker_order_id") != broker or broker not in parent["broker_order_ids"]
                or child["instrument_id"] != parent["instrument_id"] or child["side"] != parent["side"]
                or child["terms"]["order_type"] != parent["terms"]["order_type"]
                or native_command.trigger_price is not None):
            raise ValueError("Replacement requires renewed admitted authority for the same supported instrument/side/type")
        predecessor = validated_replacement(child["terms"], self.observation())
        offset = Decimal(str((predecessor.get("native_replacement_quantity_binding") or {}).get("ancestor_filled_quantity", "0")))
        quantity = str(native_command.quantity.as_decimal() + offset) if native_command.quantity else parent["terms"]["quantity"]
        price = str(native_command.price.as_decimal()) if native_command.price else parent["terms"].get("limit_price")
        expected_price = child["terms"].get("limit_price")
        if (Decimal(quantity) != Decimal(child["terms"]["quantity"]) or (price is None) != (expected_price is None)
                or price is not None and (decimal(price) is None or decimal(expected_price) is None or decimal(price) != decimal(expected_price))):
            raise ValueError("Replacement terms differ from renewed exact review")
        body = {"qty": quantity, "client_order_id": child["client_order_id"]}
        if price is not None:
            body["limit_price"] = price
        self.record_pending(parent_id, "replace_pending", "Durable replacement intent precedes PATCH; original commitment retained")
        if account_version(self.observation()) != child["account_version"]:
            raise ValueError("Source account changed before native replacement")
        from .native_types import ClientOrderId
        native = self.native.cache.order(ClientOrderId(parent.get("native_client_order_id", parent["client_order_id"])))
        if (predecessor["id"] != broker or native is None
                or Decimal(str(predecessor["filled_qty"])) != native.filled_qty.as_decimal() + offset):
            raise ValueError("Replacement predecessor or cumulative native fills changed")
        self.authority().transport_boundary(parent_id, "replace")
        try:
            result = await asyncio.to_thread(self.transport.replace_order, broker, body)
            reference = self.receipt(parent_id, "Alpaca PATCH single order", {"old_broker_order_id": broker, "request": body, "raw_response": result["raw"].decode()})
            self.record_pending(parent_id, "replace_pending", "Replacement HTTP response retained; final replacement remains pending", reference)
        except Exception as exc:
            self.record_pending(parent_id, "outcome_unknown", "Replace outcome unresolved (" + type(exc).__name__ + ")")
            raise

    async def reconcile_identity(self, identity):
        durable = self.command(identity)
        try:
            result = await asyncio.to_thread(self.transport.read_receipt, "/v2/orders:by_client_order_id?" + urlencode({"client_order_id": durable["client_order_id"]}))
        except Exception as exc:
            self.record_pending(identity, "outcome_unknown", "Identity lookup unavailable or absent (" + type(exc).__name__ + "); absence never proves non-submission")
            raise ValueError("Broker identity lookup unavailable or absent; outcome remains unknown") from None
        reference = self.receipt(identity, "Alpaca client-order lookup", {"raw_response": result["raw"].decode()})
        row = result["data"]
        if (not row.get("id") or row.get("client_order_id") != durable["client_order_id"]
                or row.get("symbol") != durable["symbol"] or row.get("side", "").upper() != durable["side"]
                or row.get("account_id", durable["account_id"]) != durable["account_id"]):
            self.record_pending(identity, "outcome_unknown", "Broker identity lookup does not match the exact command/account/instrument", reference)
            raise ValueError("Broker identity lookup differs from the exact command; outcome remains unknown")
        await self.handle_update({"stream": "trade_updates", "data": {"event": "rest_order_observation", "order": row}}, reference)

    async def handle_update(self, message, reference=None, *, replacement_predecessor=None, replacement_source=None, replacement_execution=None):
        from .native_types import ClientOrderId, VenueOrderId, Quantity, Price, TradeId, LiquiditySide, Money, native_order_account
        from .alpaca_reports import exact, timestamp, execution_id, fill_commission, native_quantities, market_replacement_binding
        data = message.get("data", {})
        canonical = execution_id(data["execution_id"]) if data.get("execution_id") else None
        fee_source = getattr(self.native, "recovery_fee_sources", {}).get(canonical)
        effective_data = data
        row = data.get("order") or {}
        authority = self.authority()
        state = authority.snapshot()["data"]
        durable = next((c for c in state["commands"].values() if row.get("client_order_id") == c["client_order_id"] or row.get("id") in c["broker_order_ids"]), None)
        if not durable:
            return
        if (data.get("event") in {"fill", "partial_fill"} and row.get("type") == "market"
                and row.get("replaces") and not durable.get("native_replacement_quantity_binding")):
            response = await asyncio.to_thread(self.transport.read_receipt, "/v2/orders/" + row["replaces"])
            predecessor = response["data"]
            parent = next((item for item in state["commands"].values() if predecessor.get("id") in item.get("broker_order_ids", [])
                and (item.get("pending_action") or {}).get("replacement_command_id") == durable["id"]), None)
            if parent is None or predecessor.get("replaced_by") != row.get("id"):
                raise ValueError("Incoming MARKET successor fill has no confirmed command/predecessor chain")
            evidence = self.receipt(durable["id"], "MARKET successor source and actual incoming execution",
                {"predecessor": response["raw"].decode(), "execution": message})
            await self.handle_update({"stream": "trade_updates", "data": {"event": "replacement_authoritative",
                "order": row, "timestamp": row["updated_at"]}}, evidence, replacement_predecessor=predecessor["id"],
                replacement_source={**predecessor, "native_client_order_id": parent.get("native_client_order_id", parent["client_order_id"]),
                    **({"native_replacement_quantity_binding": parent["native_replacement_quantity_binding"]} if parent.get("native_replacement_quantity_binding") else {})},
                replacement_execution=data)
            durable = self.command(durable["id"])
        if durable.get("native_replacement_quantity_binding"):
            row = {**row, "native_replacement_quantity_binding": durable["native_replacement_quantity_binding"]}
        if row.get("symbol") != durable["symbol"] or row.get("side", "").upper() != durable["side"]:
            raise ValueError("Trade update does not match durable instrument/side identity")
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
            quantity = exact(Quantity.from_str, data["qty"]) if data.get("qty") is not None else None
            price = exact(Price.from_str, data["price"]) if data.get("price") is not None else None
            if quantity is not None and quantity.as_decimal() <= 0 or price is not None and price.as_decimal() <= 0:
                raise ValueError("Nonpositive receipt quantity or price")
            if event in {"fill", "partial_fill"}:
                if not data.get("execution_id") or quantity is None or price is None:
                    raise ValueError("Missing fill identity or economics")
                commission, provenance = fill_commission({**data, "id": data["execution_id"],
                        "symbol": row["symbol"], "side": row["side"], "transaction_time": data.get("timestamp") or row.get("updated_at")},
                        row, self.native.account_id, self.native.base_currency, endpoint=trading_endpoint(self.credentials_file),
                        account=getattr(self.native, "fee_model_account", None), linked=fee_source)
                effective_data = {**data, "commission": str(commission.as_decimal()), "native_fee": provenance}
                trade_id = TradeId(canonical)
            if event == "replacement_authoritative":
                if not replacement_predecessor or row.get("replaces") != replacement_predecessor or row.get("id") == replacement_predecessor:
                    raise ValueError("Replacement update requires a validated distinct successor chain")
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
        states = {"new": "accepted", "accepted": "accepted", "pending_new": "submitting", "partially_filled": "partially_filled",
                  "filled": "filled", "canceled": "canceled", "expired": "expired", "rejected": "rejected",
                  "pending_cancel": "cancel_pending", "pending_replace": "replace_pending"}
        status = states.get(row.get("status"))
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
            await self.handle_update({"stream": "trade_updates", "data": successor_data},
                successor_reference, replacement_predecessor=row["id"],
                replacement_source={**row, "native_client_order_id": durable.get("native_client_order_id", durable["client_order_id"])})
        if event == "replacement_authoritative" and row.get("type") == "market":
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
                            or any(prior.get(key) != row.get(key) for key in ("symbol", "side", "type"))
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
            market_confirmed = (replacement.get("type") == "market" and order.is_closed
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
            self.native.generate_order_filled(order, venue_id, None, trade_id, quantity,
                price, self.native.base_currency, commission, LiquiditySide.NO_LIQUIDITY_SIDE, ts)
        elif event == "order_cancel_rejected":
            self.native.generate_order_cancel_rejected(order, venue_id, "Broker rejected cancellation", ts)
        elif event == "order_replace_rejected":
            self.native.generate_order_modify_rejected(order, venue_id, "Broker rejected replacement; original remains authoritative", ts)
        elif event == "replacement_authoritative":
            self.native.generate_order_updated(order, venue_id, updated_quantity, updated_price, None, None, ts, venue_order_id_modified=True)
        elif status in {"cancel_pending", "replace_pending"}:
            self.native.generate_observed_pending(order, venue_id, "PENDING_CANCEL" if status == "cancel_pending" else "PENDING_UPDATE", ts)
        elif status == "accepted":
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
            try:
                self.stream_status = {"state": "connecting", "gap": "Reconnection requires identity reconciliation; no submission retry"}
                await socket.connect(self.credentials_file)
                for command in self.authority().snapshot()["data"]["commands"].values():
                    if (command["dispatch_intent_at"] and command["state"] not in {"filled", "canceled", "rejected", "expired", "not_sent"}
                            or any(item.get("status") != "observed_current_process" or item.get("native_epoch") != self.native_epoch for item in command.get("native_deliveries", {}).values())):
                        await self.reconcile_identity(command["id"])
                self.stream_status = {"state": "listening", "connected_at": datetime.now(UTC).isoformat(), "gap": "Prior disconnected interval is not claimed observed"}
                delay = 1
                while True:
                    message = await asyncio.wait_for(socket.receive(), 90)
                    if message.get("stream") == "trade_updates":
                        async with self.native.observation_lock:
                            await self.handle_update(message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.stream_status = {"state": "disconnected", "at": datetime.now(UTC).isoformat(), "gap": "Trade updates unavailable (" + type(exc).__name__ + "); outstanding identities remain unresolved"}
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
            finally:
                await socket.close()
