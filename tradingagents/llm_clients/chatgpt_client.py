"""ChatGPT subscription access through the installed Codex app-server.

The adapter receives native function calls and returns them to LangGraph. It
never executes tools, reads credentials, or exposes a general-purpose agent.
Protocol reference: https://learn.chatgpt.com/docs/app-server
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from collections import deque
from contextlib import suppress
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

from tradingagents.integrations.maenifold import (
    GatewayRateLimited,
    reported_rate_limit,
    retry_delay,
)

from .base_client import BaseLLMClient

_NAMESPACE = "tradingagents"
_LOGGER = logging.getLogger(__name__)


def _codex_path() -> str:
    located = shutil.which("codex")
    if not located:
        raise RuntimeError("Codex CLI is missing. Install Codex, then run `codex login` with ChatGPT.")
    return located


class _AppServer:
    """One bounded stdio RPC connection, with no credential handling."""

    def __init__(self, timeout: float):
        self.deadline = time.monotonic() + timeout
        self.messages: queue.Queue = queue.Queue()
        self.events: deque = deque()
        self.request_id = 0
        self._closed = False
        config = {
            "project_doc_max_bytes": 0,
            "developer_instructions": "",
            "web_search": "disabled",
            "features.shell_tool": False,
            "features.unified_exec": False,
            "features.plugins": False,
            "features.apps": False,
            "features.browser_use": False,
            "features.computer_use": False,
            "features.multi_agent": False,
            "features.hooks": False,
            "features.memories": False,
            "features.skip_host_skill_discovery": True,
        }
        args = [_codex_path(), "app-server", "--listen", "stdio://"]
        for key, value in config.items():
            # JSON scalars and the empty inline table are also valid TOML.
            args.extend(["-c", f"{key}={json.dumps(value)}"])
        # Reuse Codex's own login, without inheriting API billing, alternate
        # OpenAI endpoints, or the hosting agent's session identity.
        excluded_env = {
            "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE",
            "CODEX_API_KEY", "CODEX_THREAD_ID", "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
        }
        child_env = {key: value for key, value in os.environ.items() if key.upper() not in excluded_env}
        self.workspace = tempfile.TemporaryDirectory(prefix="tradingagents-research-")
        try:
            catalog = subprocess.run(
                [args[0], "mcp", "list", "--json", *args[4:]], cwd=self.workspace.name,
                env=child_env, capture_output=True, text=True, encoding="utf-8",
                check=True, timeout=max(0.1, self.deadline - time.monotonic()),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            for entry in json.loads(catalog.stdout):
                name = entry["name"]
                if not isinstance(name, str) or not name:
                    raise ValueError("Invalid MCP server name")
                args.extend(["-c", f"mcp_servers.{name}.enabled=false"])
            self.process = subprocess.Popen(
                args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                env=child_env, cwd=self.workspace.name,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except OSError as exc:
            self._cleanup_workspace()
            raise RuntimeError("Codex app-server could not start. Check the Codex CLI and its permissions.") from exc
        except (subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
            self._cleanup_workspace()
            raise RuntimeError("Codex MCP configuration could not be isolated; account adapter stopped.") from exc
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("Expected a protocol object.")
                self.messages.put(message)
        except (ValueError, OSError):
            self.messages.put(RuntimeError("Codex app-server returned invalid protocol output."))
        finally:
            self.messages.put(RuntimeError("Codex app-server closed before completing the request."))
            with suppress(OSError, ValueError):
                self.process.stdout.close()

    def send(self, message):
        self._check_request()
        try:
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError) as exc:
            raise RuntimeError("Codex app-server connection closed.") from exc

    def _check_request(self):
        cancelled = getattr(self, "cancelled", None)
        if cancelled is not None and cancelled.is_set():
            raise InterruptedError("ChatGPT request cancelled.")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("ChatGPT request timed out. Check Codex sign-in and account limits.")
        return remaining

    def receive(self):
        while True:
            remaining = self._check_request()
            try:
                item = self.messages.get(timeout=min(remaining, 0.1))
                break
            except queue.Empty:
                continue
        if isinstance(item, Exception):
            raise item
        return item

    def rpc(self, method, params):
        self.request_id += 1
        request_id = self.request_id
        self.send({"id": request_id, "method": method, "params": params})
        while True:
            item = self.receive()
            if item.get("id") == request_id and "method" not in item:
                if "error" in item:
                    if limited := reported_rate_limit(item["error"]):
                        raise limited
                    code = item["error"].get("code", "unknown")
                    raise RuntimeError(
                        f"Codex rejected {method} (code {code}). Check Codex login, model access, and CLI version."
                    )
                return item.get("result", {})
            self.events.append(item)

    def event(self):
        self._check_request()
        return self.events.popleft() if self.events else self.receive()

    def close(self):
        if self._closed:
            return
        self._closed = True
        # The stdio app-server normally exits on EOF; keep forceful tree
        # termination for a helper that does not finish on its own.
        with suppress(OSError, ValueError):
            self.process.stdin.close()
        try:
            self.process.wait(timeout=3)
        except (subprocess.TimeoutExpired, OSError) as exc:
            if isinstance(exc, OSError):
                _LOGGER.warning("Could not wait for Codex app-server shutdown", exc_info=True)
            if os.name == "nt" and self.process.poll() is None:
                try:
                    subprocess.run(
                        ["taskkill.exe", "/PID", str(self.process.pid), "/T", "/F"],
                        check=True, timeout=5, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                except (OSError, subprocess.SubprocessError):
                    if self.process.poll() is None:
                        _LOGGER.warning("Could not stop the Codex app-server process tree", exc_info=True)
            if self.process.poll() is None:
                with suppress(OSError):
                    self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except (subprocess.TimeoutExpired, OSError) as exc:
                if isinstance(exc, OSError):
                    _LOGGER.warning("Could not wait for Codex app-server termination", exc_info=True)
                with suppress(OSError):
                    self.process.kill()
                try:
                    self.process.wait(timeout=3)
                except (subprocess.TimeoutExpired, OSError):
                    _LOGGER.warning("Could not wait for Codex app-server kill", exc_info=True)
        finally:
            self.reader.join(timeout=1)
            # The reader owns stdout while it is active: closing the buffered
            # pipe concurrently could wait indefinitely on its read lock.
            if not self.reader.is_alive():
                with suppress(OSError, ValueError):
                    self.process.stdout.close()
            self._cleanup_workspace()

    def _cleanup_workspace(self):
        try:
            self.workspace.cleanup()
        except OSError:
            # Housekeeping must not replace a completed response or its real error.
            _LOGGER.warning("Could not remove Codex research workspace %s", self.workspace.name, exc_info=True)


def _initialize_chatgpt(server: _AppServer) -> None:
    server.rpc("initialize", {
        "clientInfo": {"name": "tradingagents", "title": "TradingAgents", "version": "0.1.0"},
        "capabilities": {"experimentalApi": True},
    })
    server.send({"method": "initialized", "params": {}})
    account = server.rpc("account/read", {"refreshToken": False}).get("account") or {}
    if account.get("type") != "chatgpt":
        raise RuntimeError("ChatGPT account sign-in is required. Run `codex login` and choose ChatGPT.")


def check_chatgpt_account(timeout: float = 10) -> None:
    """Check the CLI-managed account type without exposing account information."""
    if timeout <= 0:
        raise ValueError("ChatGPT account check timeout must be positive.")
    server = _AppServer(timeout)
    try:
        _initialize_chatgpt(server)
    except TimeoutError as exc:
        raise RuntimeError("ChatGPT account check timed out. Check Codex sign-in and try again.") from exc
    finally:
        server.close()


def _text(message: BaseMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    texts = []
    for part in message.content:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, dict) and part.get("type") in {"text", "input_text", "output_text"}:
            texts.append(part.get("text", ""))
        else:
            raise ValueError("The ChatGPT account adapter currently accepts text messages only.")
    return "\n".join(texts)


def _history(messages: list[BaseMessage]) -> tuple[str, list[dict], str]:
    instructions, items = [], []
    remaining = list(messages)
    user_text = "Continue with the next assistant response using the conversation and tool results above."
    if remaining and isinstance(remaining[-1], HumanMessage):
        user_text = _text(remaining.pop())
    for message in remaining:
        if message.type == "system" or getattr(message, "role", None) == "developer":
            instructions.append(_text(message))
            continue
        if isinstance(message, ToolMessage):
            items.append({
                "type": "function_call_output", "call_id": message.tool_call_id,
                "namespace": _NAMESPACE, "name": message.name, "output": _text(message),
            })
            continue
        role = "assistant" if isinstance(message, AIMessage) else "user"
        content = _text(message)
        if content:
            items.append({"type": "message", "role": role, "content": [{
                "type": "output_text" if role == "assistant" else "input_text", "text": content,
            }]})
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                items.append({
                    "type": "function_call", "call_id": call["id"], "namespace": _NAMESPACE,
                    "name": call["name"], "arguments": json.dumps(call["args"]),
                })
    return "\n\n".join(instructions), items, user_text


class ChatGPTChatModel(BaseChatModel):
    """Native LangChain chat and function tools, billed to a ChatGPT login."""

    model_name: str
    timeout: float = Field(default=300, gt=0)
    max_retries: int = Field(default=3, ge=0, le=3)
    reasoning_effort: str = "high"

    @property
    def _llm_type(self) -> str:
        return "chatgpt-account"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model_name": self.model_name}

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        functions = [convert_to_openai_tool(tool)["function"] for tool in tools]
        return self.bind(tools=functions, tool_choice=tool_choice, **kwargs)

    def _generate(
        self, messages: list[BaseMessage], stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None, **kwargs,
    ) -> ChatResult:
        deadline = kwargs.setdefault("_request_deadline", time.monotonic() + self.timeout)
        cancelled = kwargs.get("_request_cancelled")
        for attempt in range(self.max_retries + 1):
            if cancelled is not None and cancelled.is_set():
                raise InterruptedError("ChatGPT request cancelled.")
            if time.monotonic() >= deadline:
                raise TimeoutError("ChatGPT request timed out.")
            try:
                return self._generate_once(messages, stop, run_manager, **kwargs)
            except GatewayRateLimited as exc:
                if attempt == self.max_retries or exc.retry_after > 60:
                    raise
                delay = retry_delay(exc.retry_after, attempt)
                if time.monotonic() + delay >= deadline:
                    raise TimeoutError("ChatGPT request deadline does not allow another retry.") from exc
                if cancelled is None:
                    time.sleep(delay)
                elif cancelled.wait(delay):
                    raise InterruptedError("ChatGPT request cancelled.") from exc

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        # BaseChatModel's default executor path cannot stop a synchronous retry
        # loop. Give this specific request a cooperative cancellation signal.
        cancelled = threading.Event()
        kwargs["_request_cancelled"] = cancelled
        kwargs["_request_deadline"] = time.monotonic() + self.timeout
        manager = run_manager.get_sync() if run_manager is not None else None
        worker = asyncio.create_task(asyncio.to_thread(self._generate, messages, stop, manager, **kwargs))
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            cancelled.set()
            # Actual receive/retry waits observe the signal; _generate_once then
            # closes its own helper. Do not leave an orphan provider retry loop.
            await asyncio.gather(worker, return_exceptions=True)
            raise

    def _generate_once(
        self, messages: list[BaseMessage], stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None, **kwargs,
    ) -> ChatResult:
        if stop:
            raise ValueError("ChatGPT account requests do not support stop sequences.")
        instructions, history, user_text = _history(messages)
        functions = kwargs.get("tools", [])
        permitted = {tool["name"] for tool in functions}
        if kwargs.get("tool_choice") == "any" and len(functions) == 1:
            instructions += f"\nReturn your answer by calling the {functions[0]['name']} function."
        cancelled = kwargs.get("_request_cancelled")
        if cancelled is not None and cancelled.is_set():
            raise InterruptedError("ChatGPT request cancelled.")
        remaining = kwargs.get("_request_deadline", time.monotonic() + self.timeout) - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("ChatGPT request timed out.")
        server = _AppServer(min(self.timeout, remaining))
        server.cancelled = cancelled
        try:
            _initialize_chatgpt(server)
            dynamic = [{"type": "namespace", "name": _NAMESPACE, "description": "TradingAgents functions", "tools": [{
                "type": "function", "name": tool["name"], "description": tool.get("description", ""),
                "inputSchema": tool.get("parameters", {"type": "object", "properties": {}}),
            } for tool in functions]}] if functions else []
            started = server.rpc("thread/start", {
                "model": self.model_name, "modelProvider": "openai", "allowProviderModelFallback": False,
                "ephemeral": True, "environments": [], "runtimeWorkspaceRoots": [],
                "cwd": server.workspace.name,
                "sandbox": "read-only", "approvalPolicy": "never", "dynamicTools": dynamic,
                "baseInstructions": instructions or "Answer the user's request.",
                "developerInstructions": "This session performs financial research only. Repository and personal coding-workflow instructions, code scores, test policies and task bookkeeping do not apply to research reports. Return only the requested financial analysis or bound research tool call.",
                "config": {"model_reasoning_effort": self.reasoning_effort},
                "serviceTier": "default",
            })
            thread_id = started["thread"]["id"]
            if started.get("model", self.model_name) != self.model_name:
                raise RuntimeError("Codex did not select the requested ChatGPT model.")
            cursor = None
            while True:
                inventory = server.rpc("mcpServerStatus/list", {
                    "threadId": thread_id, "detail": "toolsAndAuthOnly", "cursor": cursor,
                })
                if any(item.get("tools") for item in inventory.get("data", [])):
                    raise RuntimeError("Codex exposed built-in MCP tools; account adapter stopped before research.")
                cursor = inventory.get("nextCursor")
                if not cursor:
                    break
            if history:
                server.rpc("thread/inject_items", {"threadId": thread_id, "items": history})
            turn = {"threadId": thread_id, "input": [{"type": "text", "text": user_text}], "environments": []}
            if self.reasoning_effort:
                turn["effort"] = self.reasoning_effort
            turn_id = server.rpc("turn/start", turn)["turn"]["id"]
            text_parts = []
            final_text = None
            while True:
                event = server.event()
                method, params = event.get("method"), event.get("params", {})
                if method == "item/tool/call":
                    name = params["tool"]
                    if name not in permitted or params.get("namespace") != _NAMESPACE:
                        raise RuntimeError("Codex requested a tool outside the bound TradingAgents functions.")
                    arguments = params["arguments"]
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except ValueError as exc:
                            raise RuntimeError("Codex returned invalid function arguments.") from exc
                    if not isinstance(arguments, dict):
                        raise RuntimeError("Codex returned invalid function arguments.")
                    if not isinstance(params.get("callId"), str) or not params["callId"]:
                        raise RuntimeError("Codex returned an invalid function call ID.")
                    server.rpc("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})
                    message = AIMessage(content="", tool_calls=[{
                        "name": name, "args": arguments, "id": params["callId"], "type": "tool_call",
                    }])
                    return ChatResult(generations=[ChatGeneration(message=message)])
                if method == "item/agentMessage/delta":
                    text_parts.append(params["delta"])
                if method == "item/completed":
                    item = params.get("item", {})
                    if item.get("type") == "agentMessage" and item.get("phase") != "commentary":
                        final_text = item.get("text", "")
                if method == "item/started" and params.get("item", {}).get("type") in {
                    "commandExecution", "fileChange", "mcpToolCall", "webSearch", "computerUse",
                }:
                    item = params["item"]
                    identity = item["type"]
                    if identity == "mcpToolCall":
                        identity += f"; server={str(item.get('server', 'unknown'))[:120]}; tool={str(item.get('tool', 'unknown'))[:120]}"
                    raise RuntimeError(
                        f"Codex exposed an unexpected built-in tool ({identity}) "
                        f"for requested model {self.model_name}; account adapter stopped."
                    )
                if "id" in event and method:
                    raise RuntimeError("Codex requested an unsupported client action; account adapter stopped.")
                if method == "turn/completed":
                    if params["turn"]["status"] != "completed":
                        error = params["turn"].get("error") or {}
                        if limited := reported_rate_limit(error):
                            raise limited
                        detail = error.get("message") or params["turn"]["status"]
                        raise RuntimeError(f"ChatGPT response failed: {detail}")
                    content = final_text if final_text is not None else "".join(text_parts)
                    if not content:
                        raise RuntimeError("ChatGPT completed without a text response.")
                    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
        finally:
            server.close()


class ChatGPTClient(BaseLLMClient):
    """Factory-compatible account provider; no API endpoint or key required."""

    def get_llm(self) -> ChatGPTChatModel:
        return ChatGPTChatModel(
            model_name=self.model, timeout=self.kwargs.get("timeout", 300),
            max_retries=self.kwargs.get("max_retries", 3),
            reasoning_effort=self.kwargs.get("reasoning_effort") or "high", callbacks=self.kwargs.get("callbacks"),
        )

    def get_provider_name(self) -> str:
        return "codex"

    def validate_model(self) -> bool:
        # The account catalog and inference enforce availability, without a
        # stale hardcoded model list or a fallback to a different model.
        return bool(self.model)
