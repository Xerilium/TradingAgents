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


def _rate_limited(retry_after: str | None) -> openai.RateLimitError:
    """A real SDK 429 carrying an optional Retry-After header."""
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    response = httpx.Response(
        429, headers=headers,
        request=httpx.Request("POST", "http://127.0.0.1:9/v1/chat/completions"),
    )
    return openai.RateLimitError("Rate limit reached", response=response, body=None)


class AsyncRateLimitRetryTests(unittest.IsolatedAsyncioTestCase):
    """One retry allowed (rate_limit_retries=1), spaced by a tiny wait."""

    def _client(self, handler,
                rate_limit_wait_seconds: float = 0.01,
                ) -> tuple[LocalCompatibleChatOpenAI, httpx.AsyncClient]:
        aclient = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        model = LocalCompatibleChatOpenAI(
            model="test-model",
            api_key="test-key",
            base_url="http://127.0.0.1:9/v1",
            max_retries=0,                 # keep the SDK out of the retry loop
            rate_limit_retries=1,
            rate_limit_wait_seconds=rate_limit_wait_seconds,
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

    async def test_configured_wait_is_used_even_with_a_retry_after_hint(self):
        """Providers answer a token-per-minute 429 with a small ``Retry-After``.

        The hint is ignored outright: only the app-configured wait spaces the
        retries, so the next attempt lands outside the blocked quota window.
        """
        calls = []

        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(429, headers={"Retry-After": "0.05"}, json={
                    "error": {"message": "Too Many Requests",
                              "type": "rate_limit_error", "code": "rate_limit_exceeded"},
                })
            return httpx.Response(200, json=_completion_body("fixed"))

        # The hint is larger than the configured wait, so a regression to
        # hint-following would log 0.05s. Both values keep the real sleep tiny.
        model, aclient = self._client(handler, rate_limit_wait_seconds=0.01)
        try:
            with self.assertLogs("tradingagents.llm_clients.openai_client", "WARNING") as logs:
                result = await model.ainvoke([HumanMessage(content="hi")])
        finally:
            await aclient.aclose()

        self.assertEqual(result.content, "fixed")
        self.assertEqual(len(calls), 2, "the 429 must still be retried once")
        self.assertIn("retry 1/2 in 0.01s", "\n".join(logs.output),
                      "the configured wait must be used, not the server hint")

    def test_retry_after_hints_never_change_the_wait(self):
        """A server hint is ignored whichever way it points."""
        model = LocalCompatibleChatOpenAI(
            model="test-model", api_key="test-key",
            base_url="http://127.0.0.1:9/v1",
            rate_limit_retries=1, rate_limit_wait_seconds=5.0,
        )
        for hint in ("0", "90", None):
            self.assertEqual(model._rate_limit_delay(0, _rate_limited(hint)), 5.0,
                             f"the configured wait must survive a Retry-After: {hint} hint")
        self.assertIsNone(model._rate_limit_delay(1, _rate_limited("90")),
                          "a spent retry budget must still give up, hint or no hint")


if __name__ == "__main__":
    unittest.main()
