"""Bounded rate limit receipts, shared cooldown and HTTP propagation; no network."""

import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import Mock

import httpx
import pytest

from tests.test_paper_server import handler
from tests.test_paper_service import BrokerFake
from tradingagents.integrations.maenifold import (
    GatewayRateLimited,
    MaenifoldGateway,
    _rate_limit_exception,
    normalize_tool_result,
    retry_after_seconds,
    retry_delay,
)
from tradingagents.web.service import DeskService


@pytest.mark.parametrize(
    "value, expected", [("5", 5), (None, 30), ("invalid", 30), ("nan", 30),
                        ("inf", 30), ("-5", 1), ("0", 1), ("60", 60), ("60.01", 61), ("900", 900)]
)
def test_retry_after(value, expected):
    assert retry_after_seconds(value) == expected


def test_http_date_and_nested_sdk_exception():
    date = format_datetime(datetime.now(UTC) + timedelta(seconds=60), usegmt=True)
    assert 59 <= retry_after_seconds(date) <= 60
    response = httpx.Response(
        429, headers={"Retry-After": "7"}, request=httpx.Request("POST", "http://localhost/mcp")
    )
    error = httpx.HTTPStatusError("private payload", request=response.request, response=response)
    limited = _rate_limit_exception(ExceptionGroup("AnyIO", [ExceptionGroup("nested", [error])]))
    assert limited.retry_after == 7
    assert "private payload" not in str(limited)


def test_http_date_preserves_long_deadline_and_handles_past_or_malformed(monkeypatch):
    fixed = datetime(2026, 10, 14, 12, tzinfo=UTC)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz)
    monkeypatch.setattr("tradingagents.integrations.maenifold.datetime", Clock)
    assert retry_after_seconds(format_datetime(fixed + timedelta(seconds=900), usegmt=True)) == 900
    assert retry_after_seconds(format_datetime(fixed - timedelta(seconds=10), usegmt=True)) == 1
    assert retry_after_seconds("Wed, 99 Oct 2026 12:00:00 GMT") == 30
    assert retry_delay(900, 0) == retry_delay(900, 3) == 900


@pytest.mark.parametrize(
    "payload",
    [
        {
            "isError": True,
            "content": [{"type": "text", "text": "Error: upstream HTTP 429; secret"}],
        },
        {"error": {"code": 429, "retry_after": 10}},
        {"error": {"codexErrorInfo": {"httpConnectionFailed": {"httpStatusCode": 429}}}},
    ],
)
def test_wrapped_tool_limits(payload):
    with pytest.raises(GatewayRateLimited, match="429"):
        normalize_tool_result(payload)


@pytest.mark.parametrize("payload", [
    {"isError": True, "content": [{"type": "text", "text": "Error: HTTP 429"}],
     "error": {"code": 429, "retry_after": 900}},
    {"message": "HTTP 429", "error": {"code": 429, "retryAfter": 900}},
    {"error": {"code": 429, "metadata": {"retry_after": 900}}},
    {"isError": True, "content": [{"type": "text", "text": "Error: HTTP 429"}],
     "structuredContent": {"error": {"code": 429, "retryAfter": 900}}},
    {"isError": False, "content": [{"type": "text", "text": "Error: HTTP 429"}],
     "structuredContent": {"error": {"code": 429, "retryAfter": 900}}},
    {"isError": True, "content": [
        {"type": "text", "text": "Error: HTTP 429"},
        {"type": "text", "text": json.dumps({"error": {"code": 429, "retry_after": 900}})},
    ]},
])
@pytest.mark.parametrize("mutation", [False, True])
def test_structured_deadline_precedes_text_fallback_in_gateway(monkeypatch, payload, mutation):
    clock = [100.0]
    monkeypatch.setattr("tradingagents.integrations.maenifold.time.monotonic", lambda: clock[0])
    async def no_sleep(delay):
        pytest.fail("Explicit long retry metadata must not become a short default wait")
    monkeypatch.setattr("tradingagents.integrations.maenifold.asyncio.sleep", no_sleep)
    class Transport:
        calls = 0
        async def call_tool(self, *args):
            self.calls += 1
            assert self.calls == 1
            return payload
    transport = Transport()
    gateway = MaenifoldGateway(transport=transport)
    async def check():
        with pytest.raises(GatewayRateLimited) as caught:
            await gateway._call(
                "GatewayExecute" if mutation else "GatewayIndex",
                {"domain": "alpaca", "command": "place_stock_order"} if mutation else {},
            )
        assert caught.value.retry_after == 900
        assert gateway._limited_until == 1000
        clock[0] += 60
        with pytest.raises(GatewayRateLimited) as blocked:
            await gateway._call("GatewayIndex", {})
        assert blocked.value.retry_after == 840
        assert transport.calls == 1
    with pytest.raises(StopIteration):
        check().send(None)


def test_shared_gateway_cooldown_blocks_new_calls_and_recovers(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("tradingagents.integrations.maenifold.time.monotonic", lambda: clock[0])

    class Transport:
        calls = 0

        async def call_tool(self, *args):
            self.calls += 1
            if self.calls == 1:
                return {"error": {"code": 429, "retry_after": 9}}
            return {"domains": []}

    transport = Transport()
    gateway = MaenifoldGateway(transport=transport)
    # _call is independent of event-loop creation; suite's SDK fixtures test loops.
    waits = []

    async def sleep(delay):
        waits.append(delay)
        for _ in range(20):
            with pytest.raises(GatewayRateLimited):
                await gateway._call("GatewayIndex", {})
        assert transport.calls == 1
        clock[0] += delay

    monkeypatch.setattr("tradingagents.integrations.maenifold.asyncio.sleep", sleep)

    async def check():
        assert await gateway._call("GatewayIndex", {}) == {"domains": []}
        assert transport.calls == 2
        assert waits == [9]

    # Drive these immediately completing coroutines without a networked event loop.
    coroutine = check()
    with pytest.raises(StopIteration):
        coroutine.send(None)


@pytest.mark.parametrize("required, expected_waits", [(25, [25, 50, 60]), (60, [60, 60, 60])])
def test_three_retries_clamped_to_sixty_and_no_mutation_replay(monkeypatch, required, expected_waits):
    clock = [100.0]
    monkeypatch.setattr("tradingagents.integrations.maenifold.time.monotonic", lambda: clock[0])
    waits = []

    async def sleep(delay):
        waits.append(delay)
        clock[0] += delay

    monkeypatch.setattr("tradingagents.integrations.maenifold.asyncio.sleep", sleep)

    class Transport:
        calls = 0

        async def call_tool(self, *args):
            self.calls += 1
            raise GatewayRateLimited(required)

    async def check():
        transport = Transport()
        gateway = MaenifoldGateway(transport=transport)
        with pytest.raises(GatewayRateLimited):
            await gateway._call("GatewayIndex", {})
        assert transport.calls == 4
        assert waits == expected_waits
        transport = Transport()
        gateway = MaenifoldGateway(transport=transport)
        with pytest.raises(GatewayRateLimited):
            await gateway._call(
                "GatewayExecute", {"domain": "alpaca", "command": "place_stock_order"}
            )
        assert transport.calls == 1
        assert waits == expected_waits

    with pytest.raises(StopIteration):
        check().send(None)


@pytest.mark.parametrize("name, arguments", [
    ("GatewayIndex", {}),
    ("GatewayExecute", {"domain": "alpaca", "command": "place_stock_order"}),
])
def test_long_retry_after_defers_and_preserves_shared_cooldown(monkeypatch, name, arguments):
    clock = [100.0]
    monkeypatch.setattr("tradingagents.integrations.maenifold.time.monotonic", lambda: clock[0])
    async def no_sleep(delay):
        pytest.fail("A long server deadline must defer, not sleep or retry early")
    monkeypatch.setattr("tradingagents.integrations.maenifold.asyncio.sleep", no_sleep)
    class Transport:
        calls = 0
        async def call_tool(self, *args):
            self.calls += 1
            if self.calls == 1:
                raise GatewayRateLimited(900)
            return {"domains": []}
    transport = Transport()
    gateway = MaenifoldGateway(transport=transport)
    async def check():
        with pytest.raises(GatewayRateLimited) as caught:
            await gateway._call(name, arguments)
        assert caught.value.retry_after == 900
        assert transport.calls == 1
        clock[0] += 60
        for _ in range(20):
            with pytest.raises(GatewayRateLimited) as blocked:
                await gateway._call("GatewayIndex", {})
            assert blocked.value.retry_after == 840
        assert transport.calls == 1
        clock[0] += 839
        with pytest.raises(GatewayRateLimited) as blocked:
            await gateway._call("GatewayIndex", {})
        assert blocked.value.retry_after == 1
        clock[0] += 1
        assert await gateway._call("GatewayIndex", {}) == {"domains": []}
        assert transport.calls == 2
    with pytest.raises(StopIteration):
        check().send(None)


def test_inflight_long_limit_stops_another_call_scheduled_retry(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("tradingagents.integrations.maenifold.time.monotonic", lambda: clock[0])
    class Hold:
        def __await__(self):
            yield "inflight"
    class Transport:
        calls = 0
        async def call_tool(self, *args):
            self.calls += 1
            if self.calls == 1:
                await Hold()
                raise GatewayRateLimited(900)
            raise GatewayRateLimited(5)
    transport = Transport()
    gateway = MaenifoldGateway(transport=transport)
    inflight = gateway._call("GatewayIndex", {})
    assert inflight.send(None) == "inflight"
    waits = []
    async def sleep(delay):
        waits.append(delay)
        with pytest.raises(GatewayRateLimited) as first:
            inflight.send(None)
        assert first.value.retry_after == 900
        clock[0] += delay
    monkeypatch.setattr("tradingagents.integrations.maenifold.asyncio.sleep", sleep)
    waiting = gateway._call("GatewayIndex", {})
    with pytest.raises(GatewayRateLimited) as second:
        waiting.send(None)
    assert second.value.retry_after == 895
    assert waits == [5]
    assert transport.calls == 2  # Only the two requests already in flight.
    assert gateway._limited_until == 1000


@pytest.mark.parametrize(
    "route, method", [("/api/instruments/META", "GET"), ("/api/refresh", "POST")]
)
@pytest.mark.parametrize("delay", [8, 900])
def test_http_preserves_rate_limit_and_retry_after(route, method, delay):
    request, service = handler(path=route, body=b"{}")
    service.chart.side_effect = GatewayRateLimited(delay)
    service.refresh.side_effect = GatewayRateLimited(delay)
    getattr(request, "do_" + method)()
    assert request._send.call_args.args[0] == 429
    assert request._send.call_args.kwargs["headers"] == {"Retry-After": delay}
    assert len(service.mock_calls) == 1


def test_refresh_rate_limit_preserves_last_verified_snapshot(tmp_path):
    broker = BrokerFake()
    service = DeskService(tmp_path, gateway=broker, graph_factory=Mock())
    try:
        service.refresh()
        previous = service.state()
        broker.errors["get_account_info"] = GatewayRateLimited(30)
        with pytest.raises(GatewayRateLimited):
            service.refresh()
        after = service.state()
        for key in ("account", "quotes", "positions", "orders", "updated_at", "connection"):
            assert after[key] == previous[key]
        assert broker.submitted == []
    finally:
        service.close()


def test_research_cooldown_precedes_provider_probe_and_broker_refresh(tmp_path):
    broker = BrokerFake()
    service = DeskService(tmp_path, gateway=broker, graph_factory=Mock())
    service.store.data["runs"] = [
        {
            "id": "limited",
            "status": "failed",
            "retry_at": (datetime.now(UTC) + timedelta(seconds=60)).isoformat(),
        }
    ]
    service.readiness = Mock(side_effect=AssertionError("No account probe during cooldown"))
    try:
        with pytest.raises(GatewayRateLimited):
            service.start_run(["META"])
        assert broker.calls == []
        service.readiness.assert_not_called()
    finally:
        service.close()
