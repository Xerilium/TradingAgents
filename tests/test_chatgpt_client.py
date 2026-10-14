"""ChatGPT account protocol and tool isolation, with no CLI or network calls."""

import io
import json
import queue
import subprocess
import time
from collections import deque
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from tradingagents.llm_clients import chatgpt_client as client
from tradingagents.llm_clients.api_key_env import PROVIDER_API_KEY_ENV
from tradingagents.llm_clients.factory import create_tier_client
from tradingagents.llm_clients.model_catalog import get_model_options

pytestmark = pytest.mark.unit


class FakeServer:
    def __init__(self, events=(), *, account_type="chatgpt", model="test-model"):
        self.events = deque(events)
        self.account_type = account_type
        self.model = model
        self.calls = []
        self.closed = False

    def rpc(self, method, params):
        self.calls.append((method, params))
        return {
            "initialize": {},
            "account/read": {"account": {"type": self.account_type}},
            "config/read": {"config": {"mcp_servers": {"external": {}}}},
            "thread/start": {"thread": {"id": "thread-1"}, "model": self.model},
            "thread/inject_items": {},
            "turn/start": {"turn": {"id": "turn-1"}},
            "turn/interrupt": {},
        }[method]

    def send(self, message):
        self.calls.append((message["method"], message["params"]))

    def event(self):
        assert self.events, "Unexpected protocol read"
        return self.events.popleft()

    def close(self):
        self.closed = True


def tool_event(**changes):
    params = {
        "tool": "lookup", "namespace": "tradingagents",
        "arguments": {"ticker": "MSFT"}, "callId": "call-next",
    }
    params.update(changes)
    return {"id": 90, "method": "item/tool/call", "params": params}


def lookup(ticker: str) -> str:
    """Look up the specified ticker."""
    raise AssertionError("The account adapter must not execute tools.")


def install_server(monkeypatch, server):
    monkeypatch.setattr(client, "_AppServer", lambda timeout: server)
    return client.ChatGPTChatModel(model_name="test-model")


@pytest.mark.parametrize("required, expected_waits", [(25, [25, 50, 60]), (60, [60, 60, 60])])
def test_rate_limit_retries_three_times_with_sixty_second_cap(monkeypatch, required, expected_waits):
    servers=[]
    waits=[]
    def create(timeout):
        server=FakeServer([{'method':'turn/completed','params':{'turn':{
            'status':'failed','error':{'message':'HTTP 429','retry_after':required}}}}])
        servers.append(server)
        return server
    monkeypatch.setattr(client,'_AppServer',create)
    monkeypatch.setattr(client.time,'sleep',waits.append)
    with pytest.raises(client.GatewayRateLimited):
        client.ChatGPTChatModel(model_name='test-model').invoke([HumanMessage(content='Test')])
    assert len(servers)==4
    assert waits==expected_waits
    assert all(server.closed for server in servers)


@pytest.mark.parametrize("initial_short_wait, http_date", [(False, False), (False, True), (True, False)])
def test_long_server_delay_stops_without_early_sleep_or_replacement(monkeypatch, initial_short_wait, http_date):
    from datetime import UTC, datetime, timedelta
    from email.utils import format_datetime

    fixed = datetime(2026, 10, 14, 12, tzinfo=UTC)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz)
    monkeypatch.setattr("tradingagents.integrations.maenifold.datetime", Clock)
    required = format_datetime(fixed + timedelta(seconds=900), usegmt=True) if http_date else 900
    delays = ([5] if initial_short_wait else []) + [required]
    servers, waits = [], []
    def create(timeout):
        assert len(servers) < len(delays), "Must not replace a deferred provider call"
        server = FakeServer([{"method": "turn/completed", "params": {"turn": {
            "status": "failed", "error": {"message": "HTTP 429", "retry_after": delays[len(servers)]},
        }}}])
        servers.append(server)
        return server
    monkeypatch.setattr(client, "_AppServer", create)
    monkeypatch.setattr(client.time, "sleep", waits.append)
    with pytest.raises(client.GatewayRateLimited) as caught:
        client.ChatGPTChatModel(model_name="test-model").invoke([HumanMessage(content="Test")])
    assert caught.value.retry_after == 900
    assert waits == ([5] if initial_short_wait else [])
    assert len(servers) == len(delays)
    assert all(server.closed for server in servers)


def test_native_tool_calls_and_results_round_trip_without_execution(monkeypatch):
    server = FakeServer([tool_event(arguments='{"ticker":"MSFT"}')])
    model = install_server(monkeypatch, server).bind_tools([lookup])
    response = model.invoke([
        SystemMessage(content="Analyze the company using verified data."),
        HumanMessage(content="Analyze MSFT."),
        AIMessage(content="", tool_calls=[{
            "name": "lookup", "args": {"ticker": "MSFT"}, "id": "call-old",
        }]),
        ToolMessage(content="Verified result", tool_call_id="call-old", name="lookup"),
    ])

    assert response.tool_calls == [{
        "name": "lookup", "args": {"ticker": "MSFT"},
        "id": "call-next", "type": "tool_call",
    }]
    calls = dict(server.calls)
    started = calls["thread/start"]
    assert started["baseInstructions"] == "Analyze the company using verified data."
    assert started["dynamicTools"][0]["tools"][0]["name"] == "lookup"
    assert started["dynamicTools"][0]["name"] == "tradingagents"
    assert started["environments"] == started["runtimeWorkspaceRoots"] == []
    assert started["sandbox"] == "read-only"
    assert started["approvalPolicy"] == "never"
    assert started["allowProviderModelFallback"] is False
    assert started["ephemeral"] is True
    assert started["config"]["mcp_servers.external.enabled"] is False
    history = calls["thread/inject_items"]["items"]
    assert history[1] == {
        "type": "function_call", "namespace": "tradingagents", "name": "lookup",
        "call_id": "call-old", "arguments": '{"ticker": "MSFT"}',
    }
    assert history[2] == {
        "type": "function_call_output", "namespace": "tradingagents", "name": "lookup",
        "call_id": "call-old", "output": "Verified result",
    }
    assert calls["turn/interrupt"] == {"threadId": "thread-1", "turnId": "turn-1"}
    assert server.closed


def test_final_message_takes_precedence_over_commentary_deltas(monkeypatch):
    server = FakeServer([
        {"method": "item/agentMessage/delta", "params": {"delta": "Thinking aloud."}},
        {"method": "item/completed", "params": {
            "item": {"type": "agentMessage", "phase": "commentary", "text": "Progress"},
        }},
        {"method": "item/completed", "params": {
            "item": {"type": "agentMessage", "phase": "final_answer", "text": "The result."},
        }},
        {"method": "turn/completed", "params": {"turn": {"status": "completed"}}},
    ])
    response = install_server(monkeypatch, server).invoke("Analyze MSFT.")
    assert response.content == "The result."
    assert dict(server.calls)["turn/start"]["input"] == [{"type": "text", "text": "Analyze MSFT."}]
    assert server.closed


@pytest.mark.parametrize("event,message", [
    (tool_event(tool="shell"), "outside the bound"),
    (tool_event(namespace="external"), "outside the bound"),
    (tool_event(arguments="invalid json"), "invalid function arguments"),
    (tool_event(arguments=[]), "invalid function arguments"),
    (tool_event(callId=""), "invalid function call ID"),
    ({"method": "item/started", "params": {"item": {"type": "commandExecution"}}},
     "unexpected built-in tool"),
    ({"id": 42, "method": "item/commandExecution/requestApproval", "params": {}},
     "unsupported client action"),
    ({"method": "turn/completed", "params": {"turn": {
        "status": "failed", "error": {"message": "Account limit reached"},
    }}}, "Account limit reached"),
    ({"method": "turn/completed", "params": {"turn": {"status": "completed"}}},
     "without a text response"),
])
def test_rejected_tools_and_failed_turns_close_connection(monkeypatch, event, message):
    server = FakeServer([event])
    model = install_server(monkeypatch, server).bind_tools([lookup])
    with pytest.raises(RuntimeError, match=message):
        model.invoke("Analyze MSFT.")
    assert server.closed
    assert "turn/interrupt" not in dict(server.calls)


def test_rejects_model_fallback_and_closes(monkeypatch):
    server = FakeServer(model="different-model")
    model = install_server(monkeypatch, server)
    with pytest.raises(RuntimeError, match="requested ChatGPT model"):
        model.invoke("Analyze MSFT.")
    assert server.closed
    assert "turn/start" not in dict(server.calls)


@pytest.mark.parametrize("account_type", ["chatgpt", "apiKey", None])
def test_readiness_uses_only_shared_account_handshake(monkeypatch, account_type):
    server = FakeServer(account_type=account_type)
    install_server(monkeypatch, server)
    if account_type == "chatgpt":
        assert client.check_chatgpt_account() is None
    else:
        with pytest.raises(RuntimeError, match="codex login"):
            client.check_chatgpt_account()
    assert [method for method, _ in server.calls] == ["initialize", "initialized", "account/read"]
    assert dict(server.calls)["account/read"] == {"refreshToken": False}
    assert server.closed


def test_readiness_timeout_is_actionable_and_closes(monkeypatch):
    server = FakeServer()
    server.rpc = Mock(side_effect=TimeoutError("expired"))
    install_server(monkeypatch, server)
    with pytest.raises(RuntimeError, match="account check timed out"):
        client.check_chatgpt_account()
    assert server.closed


def test_factory_preserves_tier_provider_and_reasoning_without_starting_cli(monkeypatch):
    monkeypatch.setattr(client, "_AppServer", Mock(side_effect=AssertionError("CLI started")))
    result = create_tier_client({
        "llm_provider": "azure", "quick_think_provider": "chatgpt",
        "quick_think_llm": "test-model", "backend_url": "https://azure.invalid",
        "openai_reasoning_effort": "medium",
    }, "quick")
    assert isinstance(result, client.ChatGPTClient)
    assert result.base_url is None
    assert result.get_llm().reasoning_effort == "medium"
    assert PROVIDER_API_KEY_ENV["chatgpt"] is None
    assert get_model_options("chatgpt", "quick") == [("Custom model ID", "custom")]


def bare_server():
    server = client._AppServer.__new__(client._AppServer)
    server.deadline = time.monotonic() + 10
    server.messages = queue.Queue()
    server.events = deque()
    server.request_id = 0
    server._closed = False
    return server


def test_child_environment_keeps_login_location_but_removes_api_and_session_overrides(monkeypatch):
    process = Mock(stdin=io.StringIO(), stdout=io.StringIO())
    popen = Mock(return_value=process)
    monkeypatch.setattr(client, "_codex_path", lambda: "codex.exe")
    monkeypatch.setattr(client.subprocess, "Popen", popen)
    monkeypatch.setattr(client.threading, "Thread", Mock())
    for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE", "CODEX_API_KEY",
                 "CODEX_THREAD_ID", "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"):
        monkeypatch.setenv(name, "test-only")
    monkeypatch.setenv("CODEX_HOME", "test-login-location")
    server = client._AppServer(10)
    args = popen.call_args.args[0]
    env = popen.call_args.kwargs["env"]
    assert env["CODEX_HOME"] == "test-login-location"
    assert "OPENAI_API_KEY" not in env
    assert "OPENAI_BASE_URL" not in env
    assert "OPENAI_API_BASE" not in env
    assert "CODEX_API_KEY" not in env
    assert "CODEX_THREAD_ID" not in env
    assert "CODEX_INTERNAL_ORIGINATOR_OVERRIDE" not in env
    assert "features.shell_tool=false" in args
    assert "features.unified_exec=false" in args
    assert "features.plugins=false" in args
    assert "features.apps=false" in args
    assert "features.multi_agent=false" in args
    assert "features.hooks=false" in args
    assert "project_doc_max_bytes=0" in args
    assert "web_search=\"disabled\"" in args
    assert popen.call_args.kwargs["stderr"] == subprocess.DEVNULL
    server.close()


@pytest.mark.parametrize("line", ["not json\n", "[]\n"])
def test_invalid_protocol_fails_cleanly_and_closes_reader(line):
    server = bare_server()
    server.process = Mock(stdout=io.StringIO(line))
    server._read()
    with pytest.raises(RuntimeError, match="invalid protocol output"):
        server.receive()
    assert server.process.stdout.closed


def test_rpc_preserves_interleaved_events_and_sanitizes_error_details():
    server = bare_server()
    server.process = Mock(stdin=io.StringIO())
    event = {"method": "notice", "params": {}}
    server.messages.put(event)
    server.messages.put({"id": 1, "error": {"code": 401, "message": "private upstream text"}})
    with pytest.raises(RuntimeError, match="code 401") as failure:
        server.rpc("account/read", {"refreshToken": False})
    assert "private upstream text" not in str(failure.value)
    assert server.event() == event
    assert json.loads(server.process.stdin.getvalue())["method"] == "account/read"


def test_deadline_applies_even_when_protocol_events_are_already_queued():
    server = bare_server()
    server.deadline = time.monotonic() - 1
    server.messages.put({"method": "notice"})
    with pytest.raises(TimeoutError, match="timed out"):
        server.receive()


def test_cleanup_is_bounded_and_idempotent_after_unresponsive_process():
    server = bare_server()
    server.process = Mock(stdin=io.StringIO(), stdout=io.StringIO())
    server.process.wait.side_effect = [subprocess.TimeoutExpired("codex", 3),
                                       subprocess.TimeoutExpired("codex", 3), 0]
    server.reader = Mock()
    server.reader.is_alive.return_value = False
    server.close()
    server.close()
    assert server.process.stdin.closed
    assert server.process.stdout.closed
    server.process.terminate.assert_called_once()
    server.process.kill.assert_called_once()
    assert all(call.kwargs["timeout"] == 3 for call in server.process.wait.call_args_list)
    server.reader.join.assert_called_once_with(timeout=1)
