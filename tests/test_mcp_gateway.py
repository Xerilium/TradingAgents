"""Gateway protocol, schema and capability-boundary regression tests."""

import asyncio
import json
import socket
import unittest
from unittest.mock import patch

import pytest

from tradingagents.integrations.maenifold import (
    GatewayCommand,
    GatewayError,
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


if __name__ == "__main__":
    unittest.main()
