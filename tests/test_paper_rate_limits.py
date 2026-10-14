"""Bounded rate limit receipts, shared cooldown and HTTP propagation; no network."""

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
)
from tradingagents.web.service import DeskService


@pytest.mark.parametrize(
    "value, expected", [("5", 5), (None, 30), ("invalid", 30), ("nan", 30), ("0", 1), ("900", 60)]
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


def test_three_retries_clamped_to_sixty_and_no_mutation_replay(monkeypatch):
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
            raise GatewayRateLimited(25)

    async def check():
        transport = Transport()
        gateway = MaenifoldGateway(transport=transport)
        with pytest.raises(GatewayRateLimited):
            await gateway._call("GatewayIndex", {})
        assert transport.calls == 4
        assert waits == [25, 50, 60]
        transport = Transport()
        gateway = MaenifoldGateway(transport=transport)
        with pytest.raises(GatewayRateLimited):
            await gateway._call(
                "GatewayExecute", {"domain": "alpaca", "command": "place_stock_order"}
            )
        assert transport.calls == 1
        assert waits == [25, 50, 60]

    with pytest.raises(StopIteration):
        check().send(None)


@pytest.mark.parametrize(
    "route, method", [("/api/instruments/META", "GET"), ("/api/refresh", "POST")]
)
def test_http_preserves_rate_limit_and_retry_after(route, method):
    request, service = handler(path=route, body=b"{}")
    service.chart.side_effect = GatewayRateLimited(8)
    service.refresh.side_effect = GatewayRateLimited(8)
    getattr(request, "do_" + method)()
    assert request._send.call_args.args[0] == 429
    assert request._send.call_args.kwargs["headers"] == {"Retry-After": 8}
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
