import threading
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult


class StatsCallbackHandler(BaseCallbackHandler):
    """Callback handler that tracks LLM calls, tool calls, and token usage."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self.llm_calls = 0
        self.tool_calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self._calls = {
            kind: {"started": 0, "ended": 0, "errors": 0, "elapsed_seconds": 0.0}
            for kind in ("llm", "tool")
        }
        self._started = {}
        self._finished = set()
        self._usage_calls = 0

    def _start(self, kind, run_id):
        key = (kind, run_id)
        with self._lock:
            if run_id is not None and (key in self._started or key in self._finished):
                return
            self._calls[kind]["started"] += 1
            if kind == "llm":
                self.llm_calls += 1
            else:
                self.tool_calls += 1
            if run_id is not None:
                self._started[key] = time.monotonic()

    def _finish(self, kind, run_id, outcome):
        key = (kind, run_id)
        with self._lock:
            if run_id is not None and key in self._finished:
                return False
            self._calls[kind][outcome] += 1
            started = self._started.pop(key, None)
            if started is not None:
                self._calls[kind]["elapsed_seconds"] += time.monotonic() - started
            if run_id is not None:
                self._finished.add(key)
            return True

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Increment LLM call counter when an LLM starts."""
        self._start("llm", kwargs.get("run_id"))

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        **kwargs: Any,
    ) -> None:
        """Increment LLM call counter when a chat model starts."""
        self._start("llm", kwargs.get("run_id"))

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Extract token usage from LLM response."""
        if not self._finish("llm", kwargs.get("run_id"), "ended"):
            return
        try:
            generation = response.generations[0][0]
        except (IndexError, TypeError):
            return

        usage_metadata = None
        if hasattr(generation, "message"):
            message = generation.message
            if isinstance(message, AIMessage) and hasattr(message, "usage_metadata"):
                usage_metadata = message.usage_metadata

        if usage_metadata:
            with self._lock:
                self._usage_calls += 1
                self.tokens_in += usage_metadata.get("input_tokens", 0)
                self.tokens_out += usage_metadata.get("output_tokens", 0)

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Increment tool call counter when a tool starts."""
        self._start("tool", kwargs.get("run_id"))

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self._finish("llm", kwargs.get("run_id"), "errors")

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        self._finish("tool", kwargs.get("run_id"), "ended")

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        self._finish("tool", kwargs.get("run_id"), "errors")

    def get_measurements(self) -> dict[str, Any]:
        """Content-free observed callbacks, not provider HTTP attempt counts."""
        with self._lock:
            return {
                "logical_calls": {kind: dict(value) for kind, value in self._calls.items()},
                "usage": {
                    "availability": ("unavailable" if not self._usage_calls else
                                     "complete" if self._usage_calls == self.llm_calls else "partial"),
                    "calls_with_usage": self._usage_calls,
                    "input_tokens": self.tokens_in if self._usage_calls else None,
                    "output_tokens": self.tokens_out if self._usage_calls else None,
                },
                "provider_internal_attempts": None,
                "provider_internal_attempts_availability": "unavailable",
                "scope": "Observed LangChain callbacks only; direct source calls, direct Laya calls "
                         "and provider-internal retries are not logical tool counts. Callback elapsed "
                         "times sum matched completed calls and may overlap.",
            }

    def get_stats(self) -> dict[str, Any]:
        """Return current statistics."""
        with self._lock:
            return {
                "llm_calls": self.llm_calls,
                "tool_calls": self.tool_calls,
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
            }
