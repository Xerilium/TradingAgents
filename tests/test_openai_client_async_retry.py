"""Async rate-limit retry regression for the OpenAI-compatible chat client.

Research runs invoke every model call through the async path
(``cancellation.ResearchCancellationController`` -> ``ainvoke``), so
``NormalizedChatOpenAI`` must honour its retry budget there too. Before the
``_agenerate`` override, a 429 from an ``openai_compatible`` endpoint aborted
the run even with ``llm_retries`` configured.

Drives the real ``openai_compatible`` class (``LocalCompatibleChatOpenAI``) over
a mocked httpx transport, so the SDK's own error types exercise ``_is_rate_limit``
unchanged. No network. Written as a ``unittest`` TestCase so it runs under
``python -m unittest`` (pytest is not installed in the desk venv).
"""
from __future__ import annotations

import unittest

import httpx
import openai
from langchain_core.messages import HumanMessage

from tradingagents.llm_clients.openai_client import LocalCompatibleChatOpenAI


def _completion_body(text: str) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1,
        "model": "test-model",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": text},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class AsyncRateLimitRetryTests(unittest.IsolatedAsyncioTestCase):
    """One retry allowed (rate_limit_retries=1), spaced by a tiny wait."""

    def _client(self, handler) -> tuple[LocalCompatibleChatOpenAI, httpx.AsyncClient]:
        aclient = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        model = LocalCompatibleChatOpenAI(
            model="test-model",
            api_key="test-key",
            base_url="http://127.0.0.1:9/v1",
            max_retries=0,                 # keep the SDK out of the retry loop
            rate_limit_retries=1,
            rate_limit_wait_seconds=0.01,
            http_async_client=aclient,
        )
        return model, aclient

    async def test_429_is_retried_on_async_path(self):
        calls = []

        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(429, json={
                    "error": {"message": "Too Many Requests",
                              "type": "rate_limit_error", "code": "rate_limit_exceeded"},
                })
            return httpx.Response(200, json=_completion_body("recovered"))

        model, aclient = self._client(handler)
        try:
            result = await model.ainvoke([HumanMessage(content="hi")])
        finally:
            await aclient.aclose()

        self.assertEqual(result.content, "recovered")
        self.assertEqual(len(calls), 2, "the 429 must be retried once on the async path")

    async def test_non_rate_limit_400_is_not_retried_on_async_path(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(400, json={
                "error": {"message": "Bad Request", "type": "invalid_request_error"},
            })

        model, aclient = self._client(handler)
        try:
            with self.assertRaises(openai.BadRequestError):
                await model.ainvoke([HumanMessage(content="hi")])
        finally:
            await aclient.aclose()

        self.assertEqual(len(calls), 1, "a permanent 4xx must fail fast, no retry")


if __name__ == "__main__":
    unittest.main()
