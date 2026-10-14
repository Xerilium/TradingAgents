"""Gateway protocol, schema and capability-boundary regression tests."""

import asyncio
import copy
import json
import socket
import time
import unittest
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
