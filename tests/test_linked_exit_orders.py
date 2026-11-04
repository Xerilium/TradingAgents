"""Three offline linked-exit scenarios; run with the installed Nautilus Python.

No credentials, network calls, broker operations, or application data are used.
"""

import asyncio
import copy
import importlib
import importlib.util
import sys
import tempfile
import traceback
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

if importlib.util.find_spec("nautilus_trader") is None:
    import pytest
    pytest.skip("Requires the installed Nautilus runtime", allow_module_level=True)

# Match the worker's thin adapter import, without loading research/provider settings.
spec = importlib.util.spec_from_file_location("_linked_exit_adapter", Path(__file__).parents[1] / "tradingagents/web/__init__.py",
    submodule_search_locations=[str(Path(__file__).parents[1] / "tradingagents/web")])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
linked = importlib.import_module(spec.name + ".linked_orders")
investor = importlib.import_module(spec.name + ".investor")
admission = importlib.import_module(spec.name + ".admission")
Lifecycle = importlib.import_module(spec.name + ".execution_lifecycle").ExecutionLifecycle
Database = importlib.import_module(spec.name + ".app_database").ApplicationDatabase


def fixture(directory, plan=None, duration="DAY", side="BUY", kind="LIMIT"):
    from nautilus_trader.common.component import TestClock
    from nautilus_trader.common.factories import OrderFactory
    from nautilus_trader.model.identifiers import StrategyId, TraderId
    factory = OrderFactory(TraderId("TESTER-001"), StrategyId("LINKED-001"), TestClock())
    runtime = {"status": "connected", "account": {"id": "fixture", "status": "ACTIVE", "cash": "10000", "equity": "10000"},
        "account_at": datetime.now(UTC).isoformat(), "positions": [], "orders": [],
        "reconciliation": {"status": "reconciled", "orders_reconciled": True, "positions_reconciled": True},
        "market_data": {"INTC": {"instrument": {"id": "INTC.ALPACA"}, "trade_supported": True,
            "quote": {"ask_price": "100", "bid_price": "99", "ts_event": int(datetime.now(UTC).timestamp() * 1e9)}}}}
    if side == "SELL":
        runtime.update(positions=[{"symbol": "INTC", "qty": "10", "qty_available": "10", "market_value": "1000", "asset_class": "us_equity"}])
        runtime["account"]["cash"] = "9000"
    limit = (plan["take_profit"] if plan and side == "SELL" else "100") if kind == "LIMIT" else ("111" if side == "BUY" else "89") if kind == "STOP_LIMIT" else None
    terms = {"symbol": "INTC", "side": side, "quantity": "10", "order_type": kind, "limit_price": limit,
             "time_in_force": duration, "exit_plan": plan}
    if kind in {"STOP_MARKET", "STOP_LIMIT"}:
        terms["stop_price"] = "110" if side == "BUY" else "90"
    saved = investor.save(copy.deepcopy(investor.DEFAULT), {"action": "draft", "terms": terms}, runtime, ["INTC"], lambda value: value)
    database = Database(directory, {})
    defaults = {"investor": saved, "commands": {**copy.deepcopy(admission.DEFAULT), "recovery_required": False}}
    database.transact(defaults, lambda records: None)
    authority = admission.CommandAdmission(database, lambda: runtime, execution_enabled=True, review_enabled=True, admission_enabled=True)
    proposal = saved["proposals"][0]
    authority.evaluate_review(proposal["id"], proposal_revision=1, policy_revision=0, constraints={}, expected=None)
    reviewed = database.read("investor")["data"]["proposals"][0]
    if side == "BUY" and kind == "STOP_MARKET":
        assert not reviewed["risk_evaluation"]["passed"]
        assert any(check["name"] == "buy_stop_mapping" and not check["passed"] for check in reviewed["risk_evaluation"]["checks"])
        assert investor.price_evidence(reviewed["terms"], runtime)["price"] == 110
        return factory, runtime, authority, None, None
    assert reviewed["risk_evaluation"]["passed"], reviewed["risk_evaluation"]["blockers"]
    approved = authority.approve(proposal["id"], actor="offline-human", reason="fixture", constraints={},
        proposal_revision=1, policy_revision=0, evaluation_binding_sha256=reviewed["risk_evaluation"]["binding_sha256"], expected=None)
    approval_id = next(iter(approved["commands"]["data"]["approvals"]))
    identity = authority.submit_approved(approval_id, expected=None)
    native = SimpleNamespace(generate_order_submitted=Mock())
    lifecycle = Lifecycle(native, database.path, Path(directory) / "unused-credentials", lambda: runtime,
                          lambda: {"INTC": {"tradable": True}}, native_epoch="offline")
    return factory, runtime, authority, lifecycle, identity


def broker_rows(kind="bracket", status="new"):
    def row(side, type_, **values):
        stamp = datetime.now(UTC).isoformat()
        return {"id": str(uuid4()), "client_order_id": "broker-" + uuid4().hex, "symbol": "INTC", "asset_class": "us_equity",
                "side": side, "type": type_, "qty": "10", "filled_qty": "0", "status": status,
                "limit_price": None, "stop_price": None, "time_in_force": "gtc", "extended_hours": False,
                "created_at": stamp, "submitted_at": stamp, "updated_at": stamp, **values}
    parent = row("buy", "limit", order_class=kind, limit_price="100")
    parent["legs"] = [row("sell", "limit", limit_price="120", status="held"),
                      row("sell", "stop_limit", stop_price="90", limit_price="89", status="held")]
    return parent


def test_exact_approval_native_group_single_transport_and_tampering():
    cases = [("BUY", "LIMIT", plan) for plan in (None, {"take_profit": "120"}, {"stop_price": "90"},
        {"take_profit": "120", "stop_price": "90"}, {"take_profit": "120", "stop_price": "90", "stop_limit_price": "89"})]
    cases += [("SELL", "LIMIT", {"take_profit": "120", "stop_price": "90", "stop_limit_price": "89"}),
              ("SELL", "LIMIT", {"take_profit": "120", "stop_price": "90"}), ("SELL", "LIMIT", None)]
    cases += [(side, kind, None) for side in ("BUY", "SELL") for kind in ("STOP_MARKET", "STOP_LIMIT")]
    for duration in ("DAY", "GTC"):
        for side, kind, plan in cases:
            with tempfile.TemporaryDirectory(prefix="linked-exit-") as directory:
                factory, runtime, authority, lifecycle, identity = fixture(directory, plan, duration, side, kind)
                if lifecycle is None:
                    assert not authority.database.read("commands")["data"]["commands"]
                    continue
                command = lifecycle.command(identity)
                if side == "SELL":
                    assert command["remaining_quantity"] == "10" and command["cash_commitment"] == "0"
                posts = []
                lifecycle.transport._request = lambda path, method, body, **kwargs: posts.append(body) or {"raw": b"{}", "data": {}}
                lifecycle.handle_update = AsyncMock()
                if plan:
                    group = linked.native_group(factory, command["terms"], command["client_order_id"])
                    changed = {**command["terms"], "exit_plan": {**plan, "take_profit": "121"}}
                    if side == "SELL":
                        changed["limit_price"] = "121"
                    tampered = linked.native_group(factory, changed, command["client_order_id"])
                    try:
                        asyncio.run(lifecycle.submit_group(SimpleNamespace(params={"durable_command_id": identity}, order_list=tampered), factory))
                        raise AssertionError("Altered native exit escaped exact approval")
                    except ValueError:
                        pass
                    assert not posts
                    asyncio.run(lifecycle.submit_group(SimpleNamespace(params={"durable_command_id": identity}, order_list=group), factory))
                    assert len(group.orders) == (1 if side == "BUY" else 0) + bool(plan.get("take_profit")) + bool(plan.get("stop_price"))
                    assert all(str(order.emulation_trigger.name) == "NO_TRIGGER" for order in group.orders)
                    assert all(order.is_reduce_only for order in group.orders[1:])
                else:
                    order = linked.native_order(factory, command["terms"], command["client_order_id"])
                    asyncio.run(lifecycle.submit(SimpleNamespace(params={"durable_command_id": identity}, order=order)))
                assert len(posts) == 1 and posts[0]["qty"] == "10" and posts[0]["time_in_force"] == duration.lower() and posts[0]["side"] == side.lower()
                assert posts[0].get("order_class", "simple") == ("oco" if plan and side == "SELL" else "bracket" if plan and plan.get("take_profit") and plan.get("stop_price") else "oto" if plan else "simple")
                assert posts[0]["type"] == ("stop" if kind == "STOP_MARKET" else kind.lower())
                if kind in {"STOP_MARKET", "STOP_LIMIT"}:
                    assert posts[0]["stop_price"] == command["terms"]["stop_price"]
                if plan and side == "SELL":
                    assert len(group.orders) == 2 and all(order.parent_order_id is None and order.is_reduce_only for order in group.orders)
                assert posts[0].get("take_profit") == ({"limit_price": "120"} if plan and plan.get("take_profit") else None)
                assert posts[0].get("stop_loss") == ({"stop_price": "90", **({"limit_price": "89"} if plan.get("stop_limit_price") else {})} if plan and plan.get("stop_price") else None)
                try:
                    authority.dispatch_intent(identity)
                    raise AssertionError("Transported command acquired another dispatch intent")
                except ValueError:
                    pass


def test_partial_entry_oco_reservations_and_activation():
    parent = broker_rows()
    runtime = {"account": {"id": "fixture"}, "reconciliation": {"orders_reconciled": True}}
    for filled, status, expected_buy, expected_sell in (("0", "new", 10, 0), ("3", "partially_filled", 7, 0), ("10", "filled", 0, 10)):
        parent.update(filled_qty=filled, status=status)
        if status == "filled":
            for leg in parent["legs"]:
                leg["status"] = "new"
        rows = linked.flatten_orders([parent])
        runtime["orders"] = [row for row in rows if row["status"] in linked.LIVE]
        items, known = investor.working_commitments(runtime, {"commands": {}})
        assert known
        assert sum(item["remaining"] for item in items if item["side"] == "BUY") == expected_buy
        assert sum(item["remaining"] for item in items if item["side"] == "SELL") == expected_sell
        assert all(row["exit_active"] == (status == "filled") for row in rows[1:])
    parent["legs"][0].update(status="partially_filled", filled_qty="4")
    parent["legs"][1].update(qty="6", status="done_for_day")
    runtime["orders"] = linked.flatten_orders([parent])[1:]
    items, known = investor.working_commitments(runtime, {"commands": {}})
    assert known and sum(item["remaining"] for item in items) == 6
    assert runtime["orders"][1]["exit_reserved"] and not runtime["orders"][1]["exit_active"]
    oco = {**parent["legs"][0], "order_class": "oco", "legs": [parent["legs"][1]]}
    runtime["orders"] = linked.flatten_orders([oco])
    items, known = investor.working_commitments(runtime, {"commands": {}})
    assert known and sum(item["remaining"] for item in items) == 6
    root = {"id": "root-command", "account_id": "fixture", "symbol": "INTC", "side": "SELL", "state": "accepted",
        "terms": {"quantity": "10", "exit_plan": {"take_profit": "120", "stop_price": "90"}}, "timeline": [],
        "remaining_quantity": "10", "filled_quantity": "0", "cash_commitment": "0", "price_cap": None,
        "fee_commitment": None, "broker_order_ids": [oco["id"]], "client_order_id": oco["client_order_id"]}
    resized = {**runtime["orders"][0], "qty": "7", "filled_qty": "0"}
    Lifecycle._resize_exit(root, resized, root)
    assert root["broker_group_quantity"] == "7" and root["remaining_quantity"] == "7" and root["terms"]["quantity"] == "10"
    runtime["orders"] = [resized, {**runtime["orders"][1], "qty": "10", "filled_qty": "3", "status": "partially_filled"}]
    items, known = investor.working_commitments(runtime, {"commands": {root["id"]: root}})
    assert known and sum(item["remaining"] for item in items) == 7


def test_restart_child_identity_cancel_and_amendment_boundaries():
    with tempfile.TemporaryDirectory(prefix="linked-exit-") as directory:
        factory, runtime, authority, lifecycle, identity = fixture(directory,
            {"take_profit": "120", "stop_price": "90", "stop_limit_price": "89"}, "GTC")
        entry = lifecycle.command(identity)
        parent = broker_rows()
        parent["client_order_id"] = entry["client_order_id"]
        rows = linked.flatten_orders([parent])
        lifecycle.bind_group(rows)
        lifecycle.bind_group(rows)
        commands = authority.database.read("commands")["data"]["commands"]
        assert len(commands) == 3
        restarted = Lifecycle(lifecycle.native, authority.database.path, Path(directory) / "unused-credentials",
                              lambda: runtime, lambda: {}, native_epoch="restarted")
        restarted.bind_group(rows)
        rebuilt = [linked.native_observation(factory, row, {source["id"]: source for source in rows}) for row in rows]
        assert len({str(order.client_order_id) for order in rebuilt}) == 3
        assert all(str(order.parent_order_id) == entry["client_order_id"] for order in rebuilt[1:])
        assert len(authority.database.read("commands")["data"]["commands"]) == 3
        # A fresh current-state proof supersedes an older quantity observation without replay.
        from nautilus_trader.core.uuid import UUID4
        from nautilus_trader.model.events import OrderAccepted
        from nautilus_trader.model.identifiers import AccountId, ClientId, Venue, VenueOrderId
        stop_command = next(command for command in commands.values() if command.get("linked_role") == "stop_loss")
        old = next(row for row in rows if row.get("group_role") == "stop_loss")
        old["status"] = "new"
        reference = restarted.receipt(identity, "offline historical child observation", old)
        authority.apply_report(identity, {"authoritative": True, "event_id": "entry-accepted", "receipt": reference,
            "account_id": "fixture", "client_order_id": entry["client_order_id"], "instrument_id": "INTC.ALPACA",
            "filled_quantity": "0", "state": "accepted", "broker_order_id": parent["id"]})
        data = {"event": "rest_order_observation", "order": copy.deepcopy(old)}
        restarted.delivery(stop_command["id"], "historical-child", data, reference, "unresolved")
        current = {**old, "qty": "6", "updated_at": datetime.now(UTC).isoformat()}
        actual = linked.native_observation(factory, current, {row["id"]: row for row in rows})
        actual.apply(OrderAccepted(actual.trader_id, actual.strategy_id, actual.instrument_id, actual.client_order_id,
            VenueOrderId(current["id"]), AccountId("ALPACA-fixture"), UUID4(), 1, 1))
        restarted.native.account_id, restarted.native.client_id, restarted.native.venue = AccountId("ALPACA-fixture"), ClientId("ALPACA"), Venue("ALPACA")
        restarted.native.cache = SimpleNamespace(order=lambda key: actual if str(key) == stop_command["native_client_order_id"] else None,
                                                  client_id=lambda key: ClientId("ALPACA"))
        history = {"complete": True, "through": current["updated_at"], "evidence": reference}
        native_types = importlib.import_module(spec.name + ".native_types")
        original = native_types.native_dict
        for wrong in ({"side": "BUY"}, {"type": "MARKET"}):
            with patch.object(native_types, "native_dict", side_effect=lambda value: {**original(value), **wrong}):
                assert not restarted.confirm_linked_observations([rows[0], current], history)
            assert restarted.command(stop_command["id"])["native_deliveries"]["historical-child"]["status"] == "unresolved"
        assert restarted.confirm_linked_observations([rows[0], current], history)
        confirmed = restarted.command(stop_command["id"])
        assert confirmed["native_deliveries"]["historical-child"]["status"] == "superseded_by_current_observation"
        assert confirmed["native_deliveries"]["historical-child"]["input"] == data and not confirmed.get("native_pending_commitment")
        child = next(command for command in commands.values() if command.get("linked_exit"))
        try:
            restarted.command(child["id"], sending=True)
            raise AssertionError("Broker-managed exit acquired independent submit authority")
        except ValueError:
            pass
        for kind in ("bracket", "oco"):
            linked.amendment_supported({"group_class": kind, "group_role": "stop_loss"})
        try:
            linked.amendment_supported({"group_class": "oto", "group_role": "stop_loss"})
            raise AssertionError("Unsupported OTO amendment was permitted")
        except ValueError:
            pass
        restarted.transport.cancel_order = Mock(side_effect=AssertionError("No unapproved broker call"))
        from nautilus_trader.model.identifiers import ClientOrderId, VenueOrderId
        try:
            asyncio.run(restarted.cancel(SimpleNamespace(params={"durable_command_id": child["id"]},
                client_order_id=ClientOrderId("wrong-child"), venue_order_id=VenueOrderId(child["broker_order_ids"][0]))))
            raise AssertionError("Unapproved child cancellation was permitted")
        except ValueError:
            pass
        restarted.transport.cancel_order.assert_not_called()
        # Present complete synthetic broker/native observations to the real authority.
        parent.update(status="filled", filled_qty="10")
        for leg in parent["legs"]:
            leg["status"] = "new"
        rows = linked.flatten_orders([parent])
        restarted.bind_group(rows)
        commands = authority.database.read("commands")["data"]["commands"]
        for command in commands.values():
            row = next(row for row in rows if row["client_order_id"] == command["client_order_id"])
            reference = restarted.receipt(command["id"], "offline broker fixture", row)
            authority.apply_report(command["id"], {"authoritative": True, "event_id": row["id"], "receipt": reference,
                "account_id": "fixture", "client_order_id": command["client_order_id"], "instrument_id": "INTC.ALPACA",
                "filled_quantity": row["filled_qty"], "state": "filled" if row["status"] == "filled" else "accepted", "broker_order_id": row["id"]})
            if command.get("linked_exit"):
                row["native_child_order_binding"] = {"source": "broker_nested_group", "broker_order_id": row["id"],
                    "broker_client_order_id": row["client_order_id"], "native_client_order_id": command["native_client_order_id"],
                    "parent_order_id": parent["id"]}
                row["nautilus"] = {"client_order_id": command["native_client_order_id"], "venue_order_id": row["id"],
                    "instrument_id": "INTC.ALPACA", "account_binding": {"account_id": "ALPACA-fixture"}, "side": "SELL",
                    "type": linked.native_type(row["type"]), "time_in_force": "GTC", "quantity": "10", "filled_qty": "0",
                    "price": row.get("limit_price"), "trigger_price": row.get("stop_price"), "status": "ACCEPTED"}
        runtime.update(orders=rows[1:], positions=[{"symbol": "INTC", "qty": "10", "market_value": "1000", "asset_class": "us_equity"}])
        runtime.update(native_epoch="restarted", native_deliveries=[{"command_id": command["id"],
            "confirmed_current_process": True, "native_epoch": "restarted"} for command in commands.values()])
        assert authority.reconcile()["ready"]
        stop = next(row for row in runtime["orders"] if row["group_role"] == "stop_loss")
        stop_command = next(command for command in commands.values() if stop["id"] in command["broker_order_ids"])
        saved = investor.save(authority.database.read("investor")["data"], {"action": "draft", "terms": {
            "symbol": "INTC", "side": "SELL", "quantity": "10", "order_type": "STOP_LIMIT", "limit_price": "90", "stop_price": "91",
            "time_in_force": "GTC", "replacement": {"order_id": stop["id"]}}}, runtime, ["INTC"], lambda value: value)
        authority.database.transact({"investor": {}}, lambda records: records["investor"].update(saved))
        proposal = saved["proposals"][0]
        authority.evaluate_review(proposal["id"], proposal_revision=1, policy_revision=0, constraints={}, expected=None)
        reviewed = authority.database.read("investor")["data"]["proposals"][0]
        assert reviewed["risk_evaluation"]["passed"], reviewed["risk_evaluation"]["blockers"]
        approved = authority.approve(proposal["id"], actor="offline-human", reason="price amendment", constraints={},
            proposal_revision=1, policy_revision=0, evaluation_binding_sha256=reviewed["risk_evaluation"]["binding_sha256"], expected=None)
        approval_id = next(key for key, value in approved["commands"]["data"]["approvals"].items() if value["proposal_id"] == proposal["id"])
        authority.authorize_action(stop_command["id"], kind="replace", actor="offline-human", reason="amend stop", broker_order_id=stop["id"],
            broker_order_version=investor.order_version(stop), replacement_approval_id=approval_id)
        from nautilus_trader.model.objects import Price, Quantity
        restarted.native.cache = SimpleNamespace(order=lambda identity: SimpleNamespace(filled_qty=Quantity.from_str("0")))
        restarted.transport.replace_order = Mock(return_value={"raw": b"{}"})
        asyncio.run(restarted.replace(SimpleNamespace(params={"durable_command_id": stop_command["id"]},
            client_order_id=ClientOrderId(stop_command["native_client_order_id"]), venue_order_id=VenueOrderId(stop["id"]),
            quantity=Quantity.from_str("10"), price=Price.from_str("90"), trigger_price=Price.from_str("91"))))
        body = restarted.transport.replace_order.call_args.args[1]
        assert body["limit_price"] == "90" and body["stop_price"] == "91" and "qty" not in body
        replacement = {**stop, "id": str(uuid4()), "client_order_id": body["client_order_id"], "replaces": stop["id"],
                       "limit_price": "90", "stop_price": "91"}
        restarted.bind_group([rows[0], replacement])
        assert len(authority.database.read("commands")["data"]["commands"]) == 4
        assert replacement["native_client_order_id"] == stop_command["native_client_order_id"]
        reports = importlib.import_module(spec.name + ".alpaca_reports")
        from nautilus_trader.model.identifiers import AccountId
        from nautilus_trader.model.objects import Currency
        report = reports.fill_report({"id": str(uuid4()), "order_id": replacement["id"], "symbol": "INTC", "side": "sell",
            "qty": "3", "price": "91", "commission": "0", "transaction_time": datetime.now(UTC).isoformat()}, replacement,
            AccountId("ALPACA-fixture"), Currency.from_str("USD"), 1)
        assert report.last_qty.as_decimal() == 3 and str(report.client_order_id) == stop_command["native_client_order_id"]
        target = next(row for row in runtime["orders"] if row["group_role"] == "take_profit")
        target_command = next(command for command in commands.values() if target["id"] in command["broker_order_ids"])
        authority.authorize_action(target_command["id"], kind="cancel", actor="offline-human", reason="cancel linked group",
            broker_order_id=target["id"], broker_order_version=investor.order_version(target))
        restarted.transport.cancel_order = Mock(return_value={"raw": b""})
        cancel = SimpleNamespace(params={"durable_command_id": target_command["id"]},
            client_order_id=ClientOrderId(target_command["native_client_order_id"]), venue_order_id=VenueOrderId(target["id"]))
        asyncio.run(restarted.cancel(cancel))
        restarted.transport.cancel_order.assert_called_once_with(target["id"])
        try:
            asyncio.run(restarted.cancel(cancel))
            raise AssertionError("Cancel transport retried without new authority")
        except ValueError:
            pass
        restarted.transport.cancel_order.assert_called_once()


if __name__ == "__main__":
    failures = 0
    for test in (test_exact_approval_native_group_single_transport_and_tampering,
                 test_partial_entry_oco_reservations_and_activation, test_restart_child_identity_cancel_and_amendment_boundaries):
        if sys.argv[1:] and test.__name__ not in sys.argv[1:]:
            continue
        try:
            test()
            print(test.__name__ + ": passed")
        except Exception:
            failures += 1
            traceback.print_exc()
    sys.exit(bool(failures))
