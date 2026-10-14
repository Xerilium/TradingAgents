"""Gateway protocol, schema and capability-boundary regression tests."""

import asyncio
import copy
import json
import socket
import time
import unittest
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from tradingagents.dataflows.router import capture_vendor_evidence
from tradingagents.integrations.maenifold import (
    GatewayCommand,
    GatewayError,
    GatewayTimeout,
    MaenifoldGateway,
    SdkMcpTransport,
    build_langchain_tools,
    normalize_tool_result,
    verify_paper_configuration,
)

_SOCKET_PAIR = socket.socketpair
_SOCKET_CONNECT = socket.socket.connect
_SOCKET_CONNECT_EX = socket.socket.connect_ex
_GETADDRINFO = socket.getaddrinfo


@pytest.fixture
def sdk_desk(tmp_path, monkeypatch):
    """Exercise DeskService through the real Gateway/SDK boundary, with no I/O."""
    from tests.test_paper_service import BrokerFake, ManualExecutor, ScriptedGraph, create_proposal
    from tradingagents.web.service import DeskService

    broker = BrokerFake()
    service = DeskService(tmp_path / "sdk-desk", gateway=broker, graph_factory=ScriptedGraph)
    service.executor.shutdown(wait=True)
    service.executor = ManualExecutor()
    service.save_config({"universe": ["AAPL"], "name": "SDK boundary"})
    proposal = create_proposal(service)
    state = {"initialize": lambda: None, "mutations": [], "initialized": 0, "schema": {"type": "object"}}
    original_execute = broker.execute

    @asynccontextmanager
    async def client(*args, **kwargs):
        yield None

    @asynccontextmanager
    async def stream(*args, **kwargs):
        yield None, None, None

    class Session:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def initialize(self):
            state["initialized"] += 1
            state["initialize"]()

        async def call_tool(self, name, arguments):
            assert "on_dispatch" not in json.dumps(arguments)
            if name == "GatewayIndex":
                if not arguments:
                    return result({"domains": [{"name": "alpaca"}]})
                return result({"commands": [{"name": command, "schema": state["schema"]}
                                             for command in ("place_stock_order", "cancel_order_by_id")]})
            saved = json.loads(service.store.path.read_text())["proposals"][0]
            command = arguments["command"]
            if command == "place_stock_order":
                assert saved["status"] == "submitting"
                assert saved["submission_intent"] == {"account_id": "paper-account", "arguments": arguments["parameters"]}
            else:
                assert saved["cancellation"]["status"] == "intent"
                assert saved["cancellation"]["arguments"] == arguments["parameters"]
            state["mutations"].append(copy.deepcopy(arguments))
            return result(original_execute(arguments["domain"], command, arguments["parameters"]))

    monkeypatch.setattr("mcp.client.streamable_http.streamable_http_client", stream)
    monkeypatch.setattr("mcp.ClientSession", Session)
    monkeypatch.setattr("httpx.AsyncClient", client)
    gateway = MaenifoldGateway(transport=SdkMcpTransport(broker.endpoint, timeout=1))
    gateway.discover("alpaca")

    def execute(domain, command, parameters, *, on_dispatch=None):
        if command in {"place_stock_order", "cancel_order_by_id"}:
            return gateway.execute(domain, command, parameters, on_dispatch=on_dispatch)
        return original_execute(domain, command, parameters)

    monkeypatch.setattr(broker, "execute", execute)
    yield service, broker, proposal, gateway, state
    service.close()


@pytest.mark.parametrize("change", ["age", "midnight", "pause", "account", "config", "fields", "research", "laya", "book", "quotes", "cancel"])
def test_sdk_preparation_changes_block_order_before_call_tool(sdk_desk, monkeypatch, change):
    from tradingagents.web import service as service_module
    service, broker, proposal, _, sdk = sdk_desk
    owned = service.store.data["proposals"][0]
    run = service._find_run(proposal["run_id"])

    def change_at_initialize():
        if change == "age":
            class Later(datetime):
                @classmethod
                def now(cls, tz=None):
                    return datetime.now(UTC) + timedelta(minutes=16)
            monkeypatch.setattr(service_module, "datetime", Later)
        elif change == "midnight":
            monkeypatch.setattr(service_module, "today", lambda: "2099-01-01")
        elif change == "pause":
            service.store.data["paused"] = True
        elif change == "account":
            service.store.data["paper_account_id"] = "different"
        elif change == "config":
            service.store.data["config"]["max_order_notional"] = 1
        elif change == "fields":
            owned["qty"] += 1
        elif change == "research":
            run["results"][0]["rating"] = "Sell"
        elif change == "laya":
            run["results"][0]["laya"]["auto_execute"] = False
        elif change == "book":
            service.market["positions"] = [{"symbol": "AAPL", "qty": "100"}]
        elif change == "quotes":
            service.market["quotes"]["AAPL"]["timestamp"] = "2000-01-01T00:00:00+00:00"
        else:
            owned["cancellation"] = {"status": "unknown"}

    sdk["initialize"] = change_at_initialize
    with pytest.raises((ValueError, GatewayError)):
        service.submit(proposal["id"])
    assert sdk["initialized"] == 3  # discovery twice, then mutation session preparation
    assert sdk["mutations"] == broker.submitted == []
    assert "submission_intent" not in owned


@pytest.mark.parametrize("kind", ["submit", "cancel"])
@pytest.mark.parametrize("failure", ["save", "expiry_during_save"])
def test_sdk_intent_persistence_and_expiry_prevent_mutation(sdk_desk, monkeypatch, kind, failure):
    from tradingagents.web import service as service_module
    service, _, proposal, _, sdk = sdk_desk
    if kind == "cancel":
        service.submit(proposal["id"])
        sdk["mutations"].clear()
    original_save = service.store.save

    def save():
        owned = service.store.data["proposals"][0]
        pending = owned.get("cancellation", {}).get("status") == "intent" if kind == "cancel" else owned["status"] == "submitting"
        if pending and failure == "save":
            raise OSError("fixture persistence failed")
        original_save()
        if pending and failure == "expiry_during_save":
            class Later(datetime):
                @classmethod
                def now(cls, tz=None):
                    return datetime.now(UTC) + timedelta(minutes=16)
            monkeypatch.setattr(service_module, "datetime", Later)

    monkeypatch.setattr(service.store, "save", save)
    with pytest.raises((ValueError, OSError, GatewayError)):
        if kind == "submit":
            service.submit(proposal["id"])
        else:
            service.cancel_order("broker-order")
    assert sdk["mutations"] == []


def test_sdk_exact_durable_intents_one_attempt_and_no_repeated_cancel(sdk_desk):
    service, broker, proposal, _, sdk = sdk_desk
    service.submit(proposal["id"])
    service.pause(True)  # Pause must still permit protective cancellation.
    assert service.cancel_order("broker-order")["status"] == "cancel_requested"
    with pytest.raises(ValueError, match="do not resend"):
        service.cancel_order("broker-order")
    assert [call["command"] for call in sdk["mutations"]] == ["place_stock_order", "cancel_order_by_id"]
    assert len(broker.submitted) == 1


def test_sdk_schema_rejection_never_initializes_mutation_or_saves_intent(sdk_desk):
    service, broker, proposal, gateway, sdk = sdk_desk
    gateway._cache["alpaca"][1]["place_stock_order"].schema.update(required=["forbidden_missing_field"])
    with pytest.raises(GatewayError):
        service.submit(proposal["id"])
    assert sdk["initialized"] == 2
    assert sdk["mutations"] == broker.submitted == []
    assert "submission_intent" not in service.store.data["proposals"][0]


@pytest.mark.parametrize("change", ["account", "identity", "intent", "receipt", "cancellation", "expiry"])
def test_sdk_cancel_preparation_rechecks_ownership_and_freshness(sdk_desk, monkeypatch, change):
    from tradingagents.web import service as service_module
    service, _, proposal, _, sdk = sdk_desk
    service.submit(proposal["id"])
    sdk["mutations"].clear()
    owned = service.store.data["proposals"][0]

    def change_at_initialize():
        if change == "account":
            service.store.data["paper_account_id"] = "changed"
        elif change == "identity":
            owned["broker_order_id"] = "changed"
        elif change == "intent":
            owned["submission_intent"]["arguments"]["qty"] = "1"
        elif change == "receipt":
            owned["broker_receipt"]["status"] = "canceled"
        elif change == "cancellation":
            owned["cancellation"] = {"status": "unknown"}
        else:
            class Later(datetime):
                @classmethod
                def now(cls, tz=None):
                    return datetime.now(UTC) + timedelta(minutes=16)
            monkeypatch.setattr(service_module, "datetime", Later)

    sdk["initialize"] = change_at_initialize
    with pytest.raises((ValueError, GatewayError)):
        service.cancel_order("broker-order")
    assert sdk["mutations"] == []


@pytest.mark.parametrize("observation", ["changed_account", "missing_account", "failed_account", "unverified_paper",
                                          "harmless", "quotes_failed", "research_failed"])
def test_sdk_cancel_checks_new_account_observations_without_requiring_other_feeds(sdk_desk, monkeypatch, observation):
    service, broker, proposal, _, sdk = sdk_desk
    service.submit(proposal["id"])
    sdk["mutations"].clear()
    original_discover = broker.discover

    def refresh_during_initialize():
        if observation == "changed_account":
            broker.account["id"] = "different-account"
        elif observation == "missing_account":
            broker.account.pop("id")
        elif observation == "failed_account":
            broker.errors["get_account_info"] = GatewayError("account unavailable")
        elif observation == "unverified_paper":
            broker.paper = "false"
        elif observation == "quotes_failed":
            broker.errors["get_stock_snapshot"] = GatewayError("quotes unavailable")
        elif observation == "research_failed":
            def discover(domain):
                if domain == "laya":
                    raise GatewayError("research unavailable")
                return original_discover(domain)
            monkeypatch.setattr(broker, "discover", discover)
        service.refresh()
        assert service.store.data["paper_account_id"] == "paper-account"

    sdk["initialize"] = refresh_during_initialize
    if observation in {"harmless", "quotes_failed", "research_failed"}:
        assert service.cancel_order("broker-order")["status"] == "cancel_requested"
        assert [call["command"] for call in sdk["mutations"]] == ["cancel_order_by_id"]
    else:
        with pytest.raises(GatewayError):
            service.cancel_order("broker-order")
        assert sdk["mutations"] == []
        assert "cancellation" not in service.store.data["proposals"][0]


@pytest.mark.parametrize("boundary", ["submit_initial", "submit_dispatch", "cancel_dispatch"])
def test_mutation_guards_complete_with_concurrent_state_snapshot(sdk_desk, monkeypatch, boundary):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    service, _, proposal, _, sdk = sdk_desk
    if boundary == "cancel_dispatch":
        service.submit(proposal["id"])
        sdk["mutations"].clear()
    start_reader, reader_holds_market, mutation_waits_market = (threading.Event() for _ in range(3))
    mutation_thread = {}
    market_lock = service.lock

    class BoundedLock:
        """Keep a regression failure bounded even if the two threads invert locks."""
        def __init__(self, lock, market=False):
            self.lock, self.market = lock, market

        def __enter__(self):
            if self.market and threading.get_ident() == mutation_thread.get("id") and reader_holds_market.is_set():
                mutation_waits_market.set()
            assert self.lock.acquire(timeout=2), "Mutation/state lock acquisition exceeded its bound"
            return self

        def __exit__(self, *args):
            self.lock.release()

    monkeypatch.setattr(service, "lock", BoundedLock(market_lock, market=True))
    monkeypatch.setattr(service.store, "lock", BoundedLock(service.store.lock))

    def prepare_contention():
        start_reader.set()
        assert reader_holds_market.wait(2), "Concurrent state reader did not acquire market lock"

    if boundary == "submit_initial":
        book = service._book

        def initial_book():
            value = book()
            if not start_reader.is_set():
                prepare_contention()
            return value

        monkeypatch.setattr(service, "_book", initial_book)
    else:
        sdk["initialize"] = prepare_contention

    def read_state():
        assert start_reader.wait(2), "Mutation did not reach the selected boundary"
        with market_lock:
            reader_holds_market.set()
            assert mutation_waits_market.wait(2), "Mutation did not contend for market lock"
            return service.state()

    def mutate():
        mutation_thread["id"] = threading.get_ident()
        return service.cancel_order("broker-order") if boundary == "cancel_dispatch" else service.submit(proposal["id"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        reader = executor.submit(read_state)
        mutation = executor.submit(mutate)
        snapshot = reader.result(timeout=5)
        outcome = mutation.result(timeout=5)
    assert snapshot["account"]["id"] == "paper-account"
    assert len(sdk["mutations"]) == 1
    assert outcome["status"] == "cancel_requested" if boundary == "cancel_dispatch" else outcome["order"]["status"] == "accepted"


def test_sdk_lost_submission_reply_is_unknown_and_never_replayed(sdk_desk):
    service, broker, proposal, _, sdk = sdk_desk
    broker.submit_error = TimeoutError("lost reply")
    with pytest.raises(ValueError, match="unknown"):
        service.submit(proposal["id"])
    assert service.store.data["proposals"][0]["status"] == "unknown"
    with pytest.raises(ValueError, match="unknown"):
        service.submit(proposal["id"])
    assert len(sdk["mutations"]) == len(broker.submitted) == 1


@pytest.mark.parametrize("kind", ["submit", "cancel"])
def test_sdk_crash_after_durable_intent_recovers_unknown_without_resend(sdk_desk, monkeypatch, kind):
    from tradingagents.web.store import DeskStore
    service, _, proposal, _, sdk = sdk_desk
    if kind == "cancel":
        service.submit(proposal["id"])
        sdk["mutations"].clear()
    original_save = service.store.save

    class Interrupted(BaseException):
        pass

    def save_then_stop():
        original_save()
        owned = service.store.data["proposals"][0]
        pending = owned.get("cancellation", {}).get("status") == "intent" if kind == "cancel" else owned["status"] == "submitting"
        if pending:
            raise Interrupted()

    monkeypatch.setattr(service.store, "save", save_then_stop)
    with pytest.raises(Interrupted):
        if kind == "submit":
            service.submit(proposal["id"])
        else:
            service.cancel_order("broker-order")
    assert sdk["mutations"] == []
    service.store = DeskStore(service.store.directory, service.store.data["config"])
    owned = service.store.data["proposals"][0]
    assert (owned["cancellation"]["status"] if kind == "cancel" else owned["status"]) == "unknown"
    with pytest.raises(ValueError, match="unknown"):
        if kind == "submit":
            service.submit(proposal["id"])
        else:
            service.cancel_order("broker-order")
    assert sdk["mutations"] == []


@pytest.fixture(autouse=True)
def _allow_event_loop_pipe(_no_network, monkeypatch):
    """Windows asyncio needs socketpair even when every tool is a local fake.

    Keep the suite's network refusal active except while Python itself creates
    its anonymous event-loop socket pair. This does not allow tool networking.
    """

    def socketpair(*args, **kwargs):
        with (
            patch.object(socket.socket, "connect", _SOCKET_CONNECT),
            patch.object(socket.socket, "connect_ex", _SOCKET_CONNECT_EX),
            patch.object(socket, "getaddrinfo", _GETADDRINFO),
        ):
            return _SOCKET_PAIR(*args, **kwargs)

    monkeypatch.setattr(socket, "socketpair", socketpair)


def result(value, **extra):
    return {"content": [{"type": "text", "text": json.dumps(value)}], "isError": False, **extra}


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.response = result({"equity": "100000"})
        self.schema = {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
            "additionalProperties": False,
        }

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "GatewayIndex" and not arguments:
            return result({"domains": [{"name": "alpaca"}]})
        if name == "GatewayIndex":
            return result(
                {
                    "domain": "alpaca",
                    "commands": [
                        {
                            "name": "get_asset",
                            "schema": self.schema,
                            "description": "Read asset.",
                            "safety_class": "mutate",
                        }
                    ],
                }
            )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class NormalizationTests(unittest.TestCase):
    def test_nested_federated_text_and_alpaca_wrapper(self):
        inner = {"_alpaca_mcp_security": {"trust": "untrusted_tool_output"}, "data": {"cash": "12"}}
        self.assertEqual(normalize_tool_result(result(result(inner))), {"cash": "12"})

    def test_structured_content_preferred(self):
        self.assertEqual(
            normalize_tool_result(result("summary", structuredContent={"cash": "12"})),
            {"cash": "12"},
        )

    def test_outer_error(self):
        with self.assertRaises(GatewayError):
            normalize_tool_result({"content": [], "isError": True})

    def test_nested_error_even_when_outer_is_successful(self):
        with self.assertRaises(GatewayError):
            normalize_tool_result(result({"content": [], "isError": True}))

    def test_structured_success_cannot_hide_text_error(self):
        with self.assertRaises(GatewayError):
            normalize_tool_result(result({"isError": True}, structuredContent={"ok": True}))

    def test_alpaca_data_error(self):
        with self.assertRaises(GatewayError):
            normalize_tool_result({"_alpaca_mcp_security": {}, "data": {"error": "secret"}})

    def test_errors_do_not_echo_payload_secrets(self):
        with self.assertRaises(GatewayError) as raised:
            normalize_tool_result({"error": "secret-api-key"})
        self.assertNotIn("secret-api-key", str(raised.exception))

    def test_plain_evidence_remains_plain(self):
        self.assertEqual(
            normalize_tool_result(result("No matching memories.")), "No matching memories."
        )

    def test_multiple_text_blocks_preserved(self):
        self.assertEqual(
            normalize_tool_result(
                {
                    "content": [
                        {"type": "text", "text": "first"},
                        {"type": "text", "text": "second"},
                    ]
                }
            ),
            ["first", "second"],
        )


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.gateway = MaenifoldGateway(transport=self.transport)

    def test_discover_before_execute_and_preserve_exact_arguments(self):
        value = self.gateway.execute("alpaca", "get_asset", {"symbol": "AAPL"})
        self.assertEqual(value, {"equity": "100000"})
        self.assertEqual(
            self.transport.calls,
            [
                ("GatewayIndex", {}),
                ("GatewayIndex", {"domain": "alpaca", "includeSchemas": True}),
                (
                    "GatewayExecute",
                    {"domain": "alpaca", "command": "get_asset", "parameters": {"symbol": "AAPL"}},
                ),
            ],
        )

    def test_reject_unknown_command_before_execution(self):
        with self.assertRaises(GatewayError):
            self.gateway.execute("alpaca", "place_stock_order", {})
        self.assertFalse(any(name == "GatewayExecute" for name, _ in self.transport.calls))

    def test_reject_unknown_domain_before_domain_discovery(self):
        with self.assertRaises(GatewayError):
            self.gateway.discover("invented")
        self.assertEqual(self.transport.calls, [("GatewayIndex", {})])

    def test_missing_domain_is_rediscovered_after_it_becomes_available(self):
        original = self.transport.call_tool
        available = False

        async def changing_catalog(name, arguments):
            if name == "GatewayIndex" and not arguments and not available:
                return result({"domains": [{"name": "laya"}]})
            return await original(name, arguments)

        self.transport.call_tool = changing_catalog
        with self.assertRaisesRegex(GatewayError, "unavailable"):
            self.gateway.discover("alpaca")
        available = True
        self.assertIn("get_asset", self.gateway.discover("alpaca"))
        self.assertFalse(any(name == "GatewayExecute" for name, _ in self.transport.calls))

    def test_schema_rejects_missing_required_argument(self):
        with self.assertRaisesRegex(GatewayError, "schema validation"):
            self.gateway.execute("alpaca", "get_asset", {})
        self.assertFalse(any(name == "GatewayExecute" for name, _ in self.transport.calls))

    def test_schema_rejects_invalid_argument_type(self):
        with self.assertRaisesRegex(GatewayError, "schema validation"):
            self.gateway.execute("alpaca", "get_asset", {"symbol": 42})
        self.assertFalse(any(name == "GatewayExecute" for name, _ in self.transport.calls))

    def test_schema_rejects_additional_arguments(self):
        with self.assertRaises(GatewayError):
            self.gateway.execute("alpaca", "get_asset", {"symbol": "AAPL", "live": True})

    def test_failed_execution_is_not_retried(self):
        self.transport.response = GatewayError("indeterminate")
        with self.assertRaisesRegex(GatewayError, "indeterminate"):
            self.gateway.execute("alpaca", "get_asset", {"symbol": "AAPL"})
        self.assertEqual(sum(name == "GatewayExecute" for name, _ in self.transport.calls), 1)

    def test_discovery_cache_is_not_mutable_by_caller(self):
        commands = self.gateway.discover("alpaca")
        commands["get_asset"].schema["required"] = []
        with self.assertRaises(GatewayError):
            self.gateway.execute("alpaca", "get_asset", {})

    def test_schema_cache_avoids_repeated_discovery(self):
        self.gateway.execute("alpaca", "get_asset", {"symbol": "AAPL"})
        self.gateway.execute("alpaca", "get_asset", {"symbol": "MSFT"})
        self.assertEqual(sum(name == "GatewayIndex" for name, _ in self.transport.calls), 2)

    def test_async_api_and_sync_loop_guard(self):
        async def run():
            self.assertEqual(
                await self.gateway.aexecute("alpaca", "get_asset", {"symbol": "AAPL"}),
                {"equity": "100000"},
            )
            with self.assertRaisesRegex(GatewayError, "async"):
                self.gateway.discover("alpaca")

        asyncio.run(run())

    def test_missing_sdk_gives_actionable_error(self):
        with (
            patch.dict("sys.modules", {"mcp": None}),
            self.assertRaisesRegex(GatewayError, r"\[paper\]"),
        ):
            asyncio.run(SdkMcpTransport("http://localhost:8080/mcp").call_tool("GatewayIndex", {}))

    def test_invalid_endpoint_and_timeout_rejected(self):
        for endpoint in (
            "file:///etc/passwd",
            "http://key:secret@localhost/mcp",
            "localhost:8080/mcp",
        ):
            with self.assertRaises(ValueError):
                SdkMcpTransport(endpoint)
        for timeout in (0, -1, float("nan"), 301):
            with self.assertRaises(ValueError):
                SdkMcpTransport("http://localhost:8080/mcp", timeout)


class FakeGateway:
    def __init__(self):
        self.config = {
            "mcpServers": {
                "alpaca": {
                    "command": "uv",
                    "args": ["tool", "run", "alpaca-mcp-server"],
                    "env": {"ALPACA_PAPER_TRADE": "true", "ALPACA_API_KEY": "secret"},
                }
            }
        }
        self.calls = []

    def discover(self, domain):
        return {
            name: GatewayCommand(domain, name, name, {"type": "object", "properties": {}}, "mutate")
            for name in (
                "get_account_info",
                "place_stock_order",
                "cancel_all_orders",
                "get_new_mutation",
                "GetConfig",
            )
        }

    def execute(self, domain, command, parameters):
        self.calls.append((domain, command, parameters))
        return self.config if command == "GetConfig" else {"ok": True}


class ToolBoundaryTests(unittest.TestCase):
    def test_only_exact_reviewed_commands_are_exposed(self):
        gateway = FakeGateway()
        tools = build_langchain_tools(gateway, domains=("alpaca",))
        self.assertEqual([tool.name for tool in tools], ["alpaca__get_account_info"])
        self.assertEqual(json.loads(tools[0].invoke({})), {"ok": True})
        self.assertEqual(gateway.calls, [("alpaca", "get_account_info", {})])

    def test_system_commands_cannot_be_exposed_to_model(self):
        with self.assertRaises(GatewayError):
            build_langchain_tools(FakeGateway(), domains=("maenifold.system",))

    def test_verified_configuration_is_sanitized_and_honest(self):
        evidence = verify_paper_configuration(FakeGateway())
        self.assertTrue(evidence["paper"])
        self.assertFalse(evidence["runtime_endpoint_attested"])
        self.assertNotIn("secret", json.dumps(evidence))

    def test_missing_or_false_paper_setting_fails_closed(self):
        for value in (None, "false", "1", True):
            gateway = FakeGateway()
            gateway.config["mcpServers"]["alpaca"]["env"]["ALPACA_PAPER_TRADE"] = value
            with self.assertRaises(GatewayError):
                verify_paper_configuration(gateway)

    def test_conflicting_endpoint_fails_closed(self):
        gateway = FakeGateway()
        gateway.config["mcpServers"]["alpaca"]["env"]["APCA_API_BASE_URL"] = (
            "https://api.alpaca.markets"
        )
        with self.assertRaises(GatewayError):
            verify_paper_configuration(gateway)

    def test_unknown_launcher_fails_closed(self):
        gateway = FakeGateway()
        gateway.config["mcpServers"]["alpaca"]["command"] = "custom-proxy"
        with self.assertRaises(GatewayError):
            verify_paper_configuration(gateway)

    def test_indirect_environment_fails_closed(self):
        gateway = FakeGateway()
        gateway.config["mcpServers"]["alpaca"]["envFromFile"] = {"ALPACA_PAPER_TRADE": "live.txt"}
        with self.assertRaises(GatewayError):
            verify_paper_configuration(gateway)

    def test_extra_launcher_arguments_prevent_paper_attestation(self):
        gateway = FakeGateway()
        gateway.config["mcpServers"]["alpaca"]["args"].append("--live")
        with self.assertRaises(GatewayError):
            verify_paper_configuration(gateway)


class MarketGateway(FakeGateway):
    def discover(self, domain):
        return {
            name: GatewayCommand(
                domain,
                name,
                name,
                {
                    "type": "object",
                    "properties": {
                        key: {"type": "string"} for key in ("symbols", "start", "end", "asof")
                    },
                    "required": ["symbols"],
                },
            )
            for name in ("get_stock_bars", "get_stock_snapshot")
        }


class BoundContextTests(unittest.TestCase):
    def test_calendar_uses_session_date_without_next_utc_day(self):
        gateway = MarketGateway()
        command = GatewayCommand(
            "alpaca",
            "get_calendar",
            "Calendar",
            {
                "type": "object",
                "properties": {"start": {"type": "string"}, "end": {"type": "string"}},
            },
        )
        gateway.discover = lambda domain: {"get_calendar": command}
        tools = build_langchain_tools(gateway, domains=("alpaca",), trade_date="2026-01-02")
        tools[0].invoke({})
        self.assertEqual(gateway.calls[0][2]["end"], "2026-01-02")

    def test_symbol_and_asof_are_bound_and_future_end_is_clamped(self):
        gateway = MarketGateway()
        tools = build_langchain_tools(
            gateway, domains=("alpaca",), symbol="AAPL", trade_date="2026-01-02"
        )
        tools[0].invoke({"symbols": "AAPL", "end": "2999-01-01"})
        parameters = gateway.calls[0][2]
        self.assertEqual(parameters["symbols"], "AAPL")
        self.assertEqual(parameters["asof"], "2026-01-02")
        self.assertEqual(parameters["end"], "2026-01-03T04:59:59.999999+00:00")
        self.assertLess(parameters["start"], parameters["end"])
        self.assertEqual(len(tools), 1, "A current snapshot is not a historical data source")

    def test_cross_symbol_query_fails_without_gateway_call(self):
        gateway = MarketGateway()
        tools = build_langchain_tools(
            gateway, domains=("alpaca",), symbol="AAPL", trade_date="2026-01-02"
        )
        error = tools[0].invoke({"symbols": "MSFT"})
        self.assertIn("must match", error)
        self.assertEqual(gateway.calls, [])

    def test_start_beyond_cutoff_fails_without_gateway_call(self):
        gateway = MarketGateway()
        tools = build_langchain_tools(
            gateway, domains=("alpaca",), symbol="AAPL", trade_date="2026-01-02"
        )
        error = tools[0].invoke({"symbols": "AAPL", "start": "2999-01-01"})
        self.assertIn("starts after", error)
        self.assertEqual(gateway.calls, [])

    def test_invalid_context_fails_before_discovery(self):
        for parameters in (
            {"symbol": "AAPL,MSFT"},
            {"trade_date": "not-a-date"},
            {"trade_date": "2999-01-01"},
        ):
            with self.assertRaises(GatewayError):
                build_langchain_tools(MarketGateway(), **parameters)


def test_gateway_evidence_distinguishes_invocation_logical_discovery_and_transport():
    events = []
    transport = FakeTransport()
    gateway = MaenifoldGateway(transport=transport)
    with capture_vendor_evidence(lambda receipt, output: events.append(copy.deepcopy((receipt, output)))):
        tools = build_langchain_tools(gateway, domains=("alpaca",), symbol="AAPL")
        returned = tools[0].invoke({"symbol": "AAPL"})
    assert json.loads(returned) == {"equity": "100000"}
    latest = {r["attempt_id"]: (r, o) for r, o in events}
    receipts = [r for r, _ in latest.values()]
    assert {kind: sum(r["boundary_kind"] == kind for r in receipts) for kind in
            ("gateway_invocation", "gateway_logical", "gateway_discovery", "gateway_transport")} == {
        "gateway_invocation": 1, "gateway_logical": 1, "gateway_discovery": 2, "gateway_transport": 3,
    }
    invocation = next(r for r in receipts if r["boundary_kind"] == "gateway_invocation")
    logical, output = next((r, o) for r, o in latest.values() if r["boundary_kind"] == "gateway_logical")
    assert invocation["purpose"] == "analyst_tool"
    assert logical["parent_attempt_id"] == invocation["attempt_id"]
    assert output == {"parameters": {"symbol": "AAPL"}, "result": {"equity": "100000"}, "result_available": True}
    attempts = [r for r in receipts if r["boundary_kind"] == "gateway_transport"]
    assert len(attempts) == len(transport.calls)
    assert sum(r["category"] == "source" for r in attempts) == 1
    assert all(o is None for r, o in events if r["category"] == "control_plane")
    assert all(r["ended_at"] and r["elapsed_seconds"] >= 0 for r in receipts)
    assert all(len([e for e, _ in events if e["attempt_id"] == r["attempt_id"]]) == 2 for r in receipts)


@pytest.mark.parametrize("command,domain", [("GetConfig", "maenifold.system"), ("get_account_config", "alpaca"),
                                           ("register", "custom")])
@pytest.mark.parametrize("failed", [False, True])
def test_control_plane_never_supplies_parameters_results_or_errors_to_recorder(command, domain, failed):
    transport = FakeTransport()
    secret = {"api_key": "never-record", "settings": "private-config"}
    error = GatewayError("private-error-text")
    transport.response = error if failed else secret
    gateway = MaenifoldGateway(transport=transport)
    gateway._cache[domain] = (time.monotonic(), {command: GatewayCommand(domain, command, "", {"type": "object"})})
    events = []
    with capture_vendor_evidence(lambda receipt, output: events.append(copy.deepcopy((receipt, output)))):
        if failed:
            with pytest.raises(GatewayError) as caught:
                gateway.execute(domain, command, secret)
            assert caught.value is error
        else:
            # Normalization rejects error-like dictionaries; this payload has no error marker.
            assert gateway.execute(domain, command, secret) == secret
    assert events and all(output is None for _, output in events)
    encoded = json.dumps(events)
    assert all(value not in encoded for value in ("never-record", "private-config", "private-error-text"))
    assert len(transport.calls) == 1


@pytest.mark.parametrize("error", [GatewayTimeout("private-timeout"), asyncio.CancelledError("private-cancel")])
def test_gateway_timeout_and_cancellation_keep_unknown_outcome_and_exception_identity(error):
    class Transport(FakeTransport):
        async def call_tool(self, name, arguments):
            if name == "GatewayExecute":
                self.calls.append((name, arguments))
                raise error
            return await super().call_tool(name, arguments)
    events = []
    transport = Transport()
    gateway = MaenifoldGateway(transport=transport)
    async def run():
        with capture_vendor_evidence(lambda receipt, output: events.append(copy.deepcopy((receipt, output)))):
            with pytest.raises(type(error)) as caught:
                await gateway.aexecute("alpaca", "get_asset", {"symbol": "AAPL"})
            assert caught.value is error
    asyncio.run(run())
    latest = {r["attempt_id"]: r for r, _ in events}
    source = [r for r in latest.values() if r["category"] == "source"]
    assert len(source) == 2
    assert all(r["outcome"] == "unknown" for r in source)
    assert sum(name == "GatewayExecute" for name, _ in transport.calls) == 1
    assert "private-" not in json.dumps(events)


def test_gateway_schema_failure_is_one_logical_call_with_no_execution_attempt():
    gateway = MaenifoldGateway(transport=FakeTransport())
    events = []
    with (capture_vendor_evidence(lambda r, o: events.append(copy.deepcopy(r))),
          pytest.raises(GatewayError, match="schema validation")):
        gateway.execute("alpaca", "get_asset", {})
    latest = {r["attempt_id"]: r for r in events}.values()
    assert sum(r["boundary_kind"] == "gateway_logical" for r in latest) == 1
    assert not any(r["boundary_kind"] == "gateway_transport" and r["category"] == "source" for r in latest)


@pytest.mark.parametrize("cancel", [False, True])
def test_late_gateway_completion_preserves_incomplete_terminal_snapshot(tmp_path, cancel):
    import hashlib
    from uuid import uuid4

    from tradingagents.web.store import DeskStore

    async def run():
        started, release = asyncio.Event(), asyncio.Event()
        class Transport(FakeTransport):
            async def call_tool(self, name, arguments):
                if name == "GatewayExecute":
                    self.calls.append((name, arguments))
                    started.set()
                    await release.wait()
                    return result({"symbol": "AAPL", "cache": {"hit": True}, "usage": {"input_tokens": 5}})
                return await super().call_tool(name, arguments)
        transport = Transport()
        gateway = MaenifoldGateway(transport=transport)
        await gateway.adiscover("alpaca")
        store = DeskStore(tmp_path / "late", {})
        run_id = str(uuid4())
        record = {"id": run_id, "status": "running", "symbols": ["AAPL"], "results": []}
        store.data["runs"].append(record)
        with capture_vendor_evidence(lambda r, o: store.record_source_attempt(run_id, r, o)):
            task = asyncio.create_task(gateway.aexecute("alpaca", "get_asset", {"symbol": "AAPL"}))
            await started.wait()
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), timeout=0.01)
        record["status"] = "failed"
        store.finalize_gateway_evidence(record)
        store.save()
        evidence = record["gateway_evidence"]
        terminal = evidence["snapshots"][0]
        path = store.directory / terminal["path"]
        original = path.read_bytes()
        frozen = json.loads(original)
        assert frozen["pending_count"] == 2  # Logical call and its one transport attempt.
        assert frozen["capture_complete"] is False
        assert frozen["counts"]["gateway_transport"]["source"] == 1
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            release.set()
            assert (await task)["cache"] == {"hit": True}
        assert evidence["pending_count"] == 0
        assert evidence["unknown_count"] == (2 if cancel else 0)
        assert evidence["late_count"] == 2
        assert evidence["capture_complete"] is False
        assert len(evidence["snapshots"]) == 3
        assert path.read_bytes() == original
        assert hashlib.sha256(original).hexdigest() == terminal["sha256"]
        recovered = DeskStore(store.directory, {})
        assert recovered.snapshot()["runs"][0]["gateway_evidence"] == evidence
        compact = recovered.snapshot(compact=True)["runs"][0]["gateway_evidence"]
        assert "attempts" not in compact and "snapshots" not in compact
        assert compact["capture_complete"] is False
        assert sum(name == "GatewayExecute" for name, _ in transport.calls) == 1
    asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
