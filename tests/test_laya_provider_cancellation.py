"""Offline real ChatGPTChatModel cancellation/retry regressions; no provider I/O."""
import asyncio
import queue
import threading
import time

import pytest
from langchain_core.messages import HumanMessage

from tests.test_mcp_gateway import _allow_event_loop_pipe  # noqa: F401
from tradingagents.llm_clients import chatgpt_client as client
from tradingagents.web import laya_review as review


def test_summary_real_provider_disables_429_retries(monkeypatch):
    calls = []
    def once(self, *args, **kwargs):
        calls.append(self.max_retries)
        raise client.GatewayRateLimited(1)
    monkeypatch.setattr(client.ChatGPTChatModel, "_generate_once", once)
    monkeypatch.setattr(client.time, "sleep", lambda _: pytest.fail("Summary retried after429"))
    with pytest.raises(client.GatewayRateLimited):
        review.summarize(client.ChatGPTChatModel(model_name="offline"), {})
    assert calls == [0]


def test_summary_cancels_actual_provider_receive_and_worker(monkeypatch):
    entered, closed = threading.Event(), threading.Event()
    calls = []
    def once(self, *args, **kwargs):
        calls.append(1)
        server = client._AppServer.__new__(client._AppServer)
        server.deadline = kwargs["_request_deadline"]
        server.cancelled = kwargs["_request_cancelled"]
        server.messages = queue.Queue()
        entered.set()
        try:
            server.receive()
        finally:
            closed.set()
    monkeypatch.setattr(client.ChatGPTChatModel, "_generate_once", once)
    started = time.monotonic()
    token = review._cancelled.set(lambda: entered.is_set() and time.monotonic() - started > .05)
    try:
        with pytest.raises(InterruptedError):
            review.summarize(client.ChatGPTChatModel(model_name="offline"), {})
    finally:
        review._cancelled.reset(token)
    assert closed.is_set() and calls == [1]
    assert time.monotonic() - started < 1


def test_async_provider_retry_wait_is_interruptible(monkeypatch):
    entered = threading.Event()
    calls = []
    def once(self, *args, **kwargs):
        calls.append(1)
        entered.set()
        raise client.GatewayRateLimited(1)
    monkeypatch.setattr(client.ChatGPTChatModel, "_generate_once", once)
    async def run():
        task = asyncio.create_task(client.ChatGPTChatModel(model_name="offline").ainvoke([HumanMessage(content="test")]))
        while not entered.is_set():
            await asyncio.sleep(.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run())
    assert calls == [1]


def test_provider_deadline_includes_retry_wait(monkeypatch):
    calls = []
    def once(self, *args, **kwargs):
        calls.append(1)
        raise client.GatewayRateLimited(1)
    monkeypatch.setattr(client.ChatGPTChatModel, "_generate_once", once)
    monkeypatch.setattr(client.time, "sleep", lambda _: pytest.fail("Must fail before waiting beyond deadline"))
    with pytest.raises(TimeoutError):
        client.ChatGPTChatModel(model_name="offline",timeout=.1).invoke([HumanMessage(content="test")])
    assert calls == [1]


def test_cancelled_server_writes_no_new_rpc():
    server = client._AppServer.__new__(client._AppServer)
    server.deadline = time.monotonic() + 60
    server.cancelled = threading.Event()
    server.cancelled.set()
    with pytest.raises(InterruptedError):
        server.send({"method":"turn/start"})
