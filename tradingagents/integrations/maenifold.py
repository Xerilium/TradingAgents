"""Schema-discovered Maenifold Gateway calls over the official MCP SDK.

The transport owns a complete MCP session inside each operation. This avoids
sharing AnyIO task groups across LangGraph threads or event loops. Read-only
429 failures get three retries with capped exponential backoff. A lost order
response must be reconciled by client order ID before another submission.
"""

from __future__ import annotations

import asyncio
import copy
import json
import math
import re
import threading
import time
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime, time as datetime_time, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Protocol, TypeVar
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

DEFAULT_ENDPOINT = "http://localhost:8080/mcp"
# Capture policy is narrower than model-call permission. Account/configuration,
# order and unknown commands are metadata-only, even if their results look safe.
_EVIDENCE_COMMANDS = {
    "alpaca": frozenset({"get_asset", "get_clock", "get_calendar", "get_portfolio_history",
                         "get_stock_bars", "get_stock_latest_quote", "get_stock_latest_trade",
                         "get_stock_snapshot", "get_news"}),
    "maenifold.memory": frozenset({"SearchMemories", "ReadMemory"}),
    "laya": frozenset({"decide"}),
}


def gateway_observation(domain, command, boundary, *, parameters=None, purpose=None, ordinal=None):
    from tradingagents.dataflows.router import observe_gateway_call

    eligible = command in _EVIDENCE_COMMANDS.get(domain, ())
    known = eligible or command in ANALYSIS_COMMANDS.get(domain, ()) or (
        (domain, command) in {("maenifold.system", "GetConfig"), ("gateway", "GatewayIndex")}
    )
    return observe_gateway_call(
        domain if known else "unreviewed_domain", command if known else "unreviewed_command", boundary,
        eligible=eligible, parameters=parameters if eligible else None, purpose=purpose, ordinal=ordinal,
    )


_EXTRAS_MESSAGE = (
    "The Maenifold integration requires the optional dependencies. "
    'Install this project with its paper extra: pip install -e ".[paper]".'
)


class GatewayError(RuntimeError):
    """A connection, discovery, validation, or upstream tool failure."""


class GatewayTimeout(GatewayError):
    """The operation timed out; an upstream mutation may have completed."""


def retry_after_seconds(value=None):
    """Preserve the server's required delay; only automatic backoff is capped."""
    try:
        delay = float(value)
    except (TypeError, ValueError, OverflowError):
        try:
            delay = (parsedate_to_datetime(str(value)) - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            delay = 30
    return max(1, math.ceil(delay)) if math.isfinite(delay) else 30


def retry_delay(retry_after, retry_index):
    """Capped backoff, never shorter than Retry-After; callers defer above 60."""
    required = retry_after_seconds(retry_after)
    return max(required, min(60, required * (2 ** retry_index)))


class GatewayRateLimited(GatewayError):
    """A rate limit receipt; never authorizes retrying a mutation."""

    def __init__(self, retry_after=None):
        self.retry_after = retry_after_seconds(retry_after)
        super().__init__(f"Upstream rate limit (429). Wait {self.retry_after} seconds before trying again.")


def reported_rate_limit(value):
    """Prefer explicit nested retry metadata over text-only rate-limit defaults."""
    if not isinstance(value, dict):
        return None
    pending, nodes, seen = [(value, 0)], [], set()
    while pending:
        node, depth = pending.pop()
        if not isinstance(node, dict) or id(node) in seen or depth > 16:
            continue
        seen.add(id(node))
        nodes.append(node)
        pending.extend((nested, depth + 1) for nested in node.values() if isinstance(nested, dict))
        for block in node.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                # Plain-text fallback is considered only after structured metadata.
                with suppress(ValueError, TypeError):
                    pending.append((json.loads(block.get("text", "")), depth + 1))
    pattern = r"\b429\b|too many requests|rate.?limit|usage limit"
    matched = any(
        any(str(node.get(key)) in {"429", "rateLimitExceeded", "usageLimitExceeded"}
            for key in ("status_code", "httpStatusCode", "status", "code", "type"))
        or re.search(pattern, str(node.get("message", "")), re.I)
        or any(isinstance(block, dict) and block.get("type") == "text"
               and re.search(pattern, str(block.get("text", "")), re.I)
               for block in node.get("content") or [])
        for node in nodes
    )
    if not matched:
        return None
    for node in nodes:
        required = node.get("retry_after", node.get("retryAfter"))
        if required is not None:
            return GatewayRateLimited(required)
    return GatewayRateLimited()


def _rate_limit_exception(exc):
    """The SDK can wrap HTTP failures in nested AnyIO exception groups."""
    pending, seen = [exc], set()
    while pending:
        error = pending.pop()
        if id(error) in seen:
            continue
        seen.add(id(error))
        response = getattr(error, "response", None)
        if getattr(response, "status_code", None) == 429:
            return GatewayRateLimited(response.headers.get("Retry-After"))
        pending.extend(getattr(error, "exceptions", ()))
        pending.extend(e for e in (error.__cause__, error.__context__) if e is not None)
    return None


@dataclass(frozen=True)
class GatewayCommand:
    domain: str
    name: str
    description: str
    schema: dict[str, Any]
    safety_class: str = "unknown"


class Gateway(Protocol):
    """Small injectable interface used by analysis and deterministic execution."""

    def discover(self, domain: str) -> dict[str, GatewayCommand]: ...

    def execute(self, domain: str, command: str, parameters: dict[str, Any], *, on_dispatch=None) -> Any: ...


class McpTransport(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any], *, on_dispatch=None) -> Any: ...


def _is_result_envelope(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if "isError" in value or "structuredContent" in value:
        return True
    blocks = value.get("content")
    return isinstance(blocks, list) and all(
        isinstance(block, dict) and "type" in block for block in blocks
    )


def _raise_reported_error(value: dict[str, Any]) -> None:
    if (
        value.get("isError") is True
        or value.get("success") is False
        or value.get("status") in ("error", "failed")
        or value.get("action") == "error"
        or bool(value.get("error"))
        or (_is_result_envelope(value) and any(
            isinstance(block, dict) and block.get("type") == "text"
            and isinstance(block.get("text"), str)
            and block["text"].lstrip().lower().startswith(("error:", "tool error:"))
            for block in value.get("content") or []
        ))
    ):
        # Do not echo arbitrary upstream payloads: system configuration results
        # can contain secrets. Callers receive a stable, non-secret error.
        error = value.get("error")
        if limited := reported_rate_limit(value):
            raise limited
        for block in value.get("content") or []:
            if (isinstance(block, dict) and block.get("type") == "text"
                    and re.search(r"\b429\b|too many requests|rate.?limit", block.get("text", ""), re.I)):
                raise GatewayRateLimited()
        metadata = error if isinstance(error, dict) else value
        status = metadata.get("status_code", metadata.get("code", metadata.get("status")))
        if str(status) == "429" or re.search(r"\b429\b|too many requests|rate.?limit", str(error or value.get("message", "")), re.I):
            raise GatewayRateLimited(metadata.get("retry_after", metadata.get("retryAfter")))
        raise GatewayError("The upstream Gateway tool reported an error.")


def normalize_tool_result(value: Any, *, _depth: int = 0) -> Any:
    """Unwrap SDK models, nested MCP results and Alpaca's data envelope.

    Federated tools can return another CallToolResult encoded in a text block.
    Inspect every envelope for errors before preferring structured content.
    Ordinary strings remain strings; unstructured evidence is not invented.
    """
    if _depth > 16:
        raise GatewayError("The Gateway response contains too many nested envelopes.")
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", by_alias=True)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            if value.lstrip().lower().startswith(("error:", "tool error:")):
                if re.search(r"\b429\b|too many requests|rate.?limit", value, re.I):
                    raise GatewayRateLimited() from None
                raise GatewayError("The upstream Gateway tool reported a text error.") from None
            return value
        return normalize_tool_result(parsed, _depth=_depth + 1)
    if not isinstance(value, dict):
        return value
    _raise_reported_error(value)
    if _is_result_envelope(value):
        parts = []
        for block in value.get("content") or []:
            if block.get("type") == "text":
                parts.append(normalize_tool_result(block.get("text", ""), _depth=_depth + 1))
            else:
                parts.append(block)
        structured = value.get("structuredContent")
        if structured is not None:
            return normalize_tool_result(structured, _depth=_depth + 1)
        if len(parts) == 1:
            return parts[0]
        return parts
    if "_alpaca_mcp_security" in value and "data" in value:
        return normalize_tool_result(value["data"], _depth=_depth + 1)
    if "result" in value and set(value) <= {"result", "id", "jsonrpc", "_meta"}:
        return normalize_tool_result(value["result"], _depth=_depth + 1)
    return value


class SdkMcpTransport:
    """Official SDK Streamable HTTP transport, without custom MCP HTTP code."""

    def __init__(self, endpoint: str, timeout: float = 30.0):
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("MCP endpoint must be an absolute HTTP or HTTPS URL.")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("MCP endpoint must not embed credentials or a URL fragment.")
        if not math.isfinite(timeout) or timeout <= 0 or timeout > 300:
            raise ValueError("MCP timeout must be greater than zero and at most 300 seconds.")
        self.endpoint = endpoint
        self.timeout = timeout

    async def call_tool(self, name: str, arguments: dict[str, Any], *, on_dispatch=None) -> Any:
        try:
            import httpx
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except ImportError as exc:
            raise GatewayError(_EXTRAS_MESSAGE) from exc

        try:
            # This bounds initialization, the tool call, and session teardown.
            async with (
                asyncio.timeout(self.timeout),
                httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout),
                    follow_redirects=False,
                    trust_env=False,
                ) as http_client,
                streamable_http_client(self.endpoint, http_client=http_client) as (
                    read_stream,
                    write_stream,
                    _,
                ),
                ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=self.timeout),
                ) as session,
            ):
                await session.initialize()
                if on_dispatch is not None:
                    on_dispatch()
                return await session.call_tool(name, arguments=arguments)
        except TimeoutError as exc:
            raise GatewayTimeout(
                "MCP operation timed out. Its result may be unknown; mutations must not be retried."
            ) from exc
        except GatewayError:
            raise
        except Exception as exc:
            if limited := _rate_limit_exception(exc):
                raise limited from exc
            raise GatewayError(
                f"MCP operation failed ({type(exc).__name__}). "
                "Check that the configured Maenifold endpoint is running. "
                "If this was an order submission, reconcile its client order ID before retrying."
            ) from exc


def validate_parameters(parameters: dict[str, Any], schema: dict[str, Any]) -> None:
    try:
        from jsonschema import exceptions, validators
    except ImportError as exc:
        raise GatewayError(_EXTRAS_MESSAGE) from exc
    try:
        validator = validators.validator_for(schema)
        validator.check_schema(schema)
        validator(schema).validate(parameters)
    except exceptions.SchemaError as exc:
        raise GatewayError("Gateway command advertised an invalid JSON Schema.") from exc
    except exceptions.ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path) or "parameters"
        # Validation messages can include the entire input, so do not surface
        # them to the UI (which may be handling credentials or private notes).
        raise GatewayError(f"Gateway parameters failed schema validation at {path}.") from exc


_T = TypeVar("_T")


def _run_sync(factory: Callable[[], Awaitable[_T]]) -> _T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    raise GatewayError("Use adiscover/aexecute from an async event loop, or asyncio.to_thread.")


class MaenifoldGateway:
    """Discover live domain schemas before sending exact command parameters."""

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 30.0,
        *,
        transport: McpTransport | None = None,
        schema_validator: Callable[[dict[str, Any], dict[str, Any]], None] = validate_parameters,
        cache_seconds: float = 60.0,
    ):
        self.endpoint = endpoint
        self.transport = transport or SdkMcpTransport(endpoint, timeout)
        self._validate = schema_validator
        self._cache_seconds = cache_seconds
        self._cache: dict[str, tuple[float, dict[str, GatewayCommand]]] = {}
        self._domains: set[str] | None = None
        self._domains_at = 0.0
        self._lock = threading.RLock()
        self._limited_until = 0.0
        self._retrying = False

    async def _call(self, name, arguments, *, on_dispatch=None):
        with self._lock:
            remaining = self._limited_until - time.monotonic()
            retrying = self._retrying
        if remaining > 0 or retrying:
            raise GatewayRateLimited(remaining)
        safe = name == "GatewayIndex" or (
            name == "GatewayExecute" and (
                arguments.get("command") in ANALYSIS_COMMANDS.get(arguments.get("domain"), ())
                or (arguments.get("domain"), arguments.get("command")) == ("maenifold.system", "GetConfig")
            )
        )
        owns_retry = False
        try:
            for attempt in range(4):
                # A concurrent in-flight call may extend the shared deadline while
                # this call sleeps. Do not issue its scheduled retry before then.
                with self._lock:
                    remaining = self._limited_until - time.monotonic()
                    if remaining > 0 or (self._retrying and not owns_retry):
                        raise GatewayRateLimited(remaining)
                domain = arguments.get("domain") if name == "GatewayExecute" else "gateway"
                command = arguments.get("command") if name == "GatewayExecute" else "GatewayIndex"
                with gateway_observation(domain, command, "gateway_transport",
                                         parameters=arguments.get("parameters"), ordinal=attempt + 1) as observed:
                    try:
                        if on_dispatch is None:
                            raw = await self.transport.call_tool(name, arguments)
                        else:
                            def dispatch(retry_owner=owns_retry):
                                with self._lock:
                                    remaining = self._limited_until - time.monotonic()
                                    if remaining > 0 or (self._retrying and not retry_owner):
                                        raise GatewayRateLimited(remaining)
                                on_dispatch()
                            raw = await self.transport.call_tool(name, arguments, on_dispatch=dispatch)
                        observed.update(output=raw, result_available=True)
                        return normalize_tool_result(raw)
                    except GatewayRateLimited as exc:
                        delay = retry_delay(exc.retry_after, attempt)
                        observed["receipt"].update(outcome="rate_limited", retry_after_seconds=exc.retry_after)
                        with self._lock:
                            self._limited_until = max(self._limited_until, time.monotonic() + delay)
                            remaining = self._limited_until - time.monotonic()
                            if (exc.retry_after > 60 or remaining > 60 or not safe or attempt == 3
                                    or (self._retrying and not owns_retry)):
                                observed["receipt"]["retry_action"] = "defer"
                                raise GatewayRateLimited(max(delay, remaining)) from exc
                            self._retrying = owns_retry = True
                        observed["receipt"].update(retry_action="retry", scheduled_wait_seconds=delay)
                await asyncio.sleep(delay)
        finally:
            if owns_retry:
                with self._lock:
                    self._retrying = False
                    # A successful retry releases the shared cooldown immediately.
                    if self._limited_until <= time.monotonic():
                        self._limited_until = 0.0

    async def adiscover(self, domain: str) -> dict[str, GatewayCommand]:
        with gateway_observation("gateway", "GatewayIndex", "gateway_discovery"):
            return await self._adiscover(domain)

    async def _adiscover(self, domain: str) -> dict[str, GatewayCommand]:
        if not domain:
            raise GatewayError("A Gateway domain is required.")
        with self._lock:
            cached = self._cache.get(domain)
            if cached and time.monotonic() - cached[0] < self._cache_seconds:
                return copy.deepcopy(cached[1])
        if (
            self._domains is None
            or domain not in self._domains
            or time.monotonic() - self._domains_at >= self._cache_seconds
        ):
            index = await self._call("GatewayIndex", {})
            if not isinstance(index, dict) or not isinstance(index.get("domains"), list):
                raise GatewayError("GatewayIndex did not return a domain catalog.")
            domains = {
                item["name"]
                for item in index["domains"]
                if isinstance(item, dict) and "name" in item
            }
            with self._lock:
                self._domains = domains
                self._domains_at = time.monotonic()
        if domain not in self._domains:
            raise GatewayError(f"Gateway domain is unavailable: {domain}.")
        catalog = normalize_tool_result(
            await self._call(
                "GatewayIndex", {"domain": domain, "includeSchemas": True}
            )
        )
        if not isinstance(catalog, dict) or not isinstance(catalog.get("commands"), list):
            raise GatewayError("GatewayIndex did not return command schemas.")
        commands: dict[str, GatewayCommand] = {}
        for item in catalog["commands"]:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise GatewayError("GatewayIndex returned a malformed command.")
            schema = item.get("schema")
            if not isinstance(schema, dict):
                raise GatewayError(f"Gateway command has no JSON Schema: {item['name']}.")
            commands[item["name"]] = GatewayCommand(
                domain=domain,
                name=item["name"],
                description=item.get("description", ""),
                schema=copy.deepcopy(schema),
                safety_class=item.get("safety_class", "unknown"),
            )
        with self._lock:
            self._cache[domain] = (time.monotonic(), commands)
        return copy.deepcopy(commands)

    def discover(self, domain: str) -> dict[str, GatewayCommand]:
        return _run_sync(lambda: self.adiscover(domain))

    async def aexecute(self, domain: str, command: str, parameters: dict[str, Any], *, on_dispatch=None) -> Any:
        with gateway_observation(domain, command, "gateway_logical", parameters=parameters) as observed:
            response = await self._aexecute(domain, command, parameters, on_dispatch=on_dispatch)
            observed.update(output=response, result_available=True)
            return response

    async def _aexecute(self, domain: str, command: str, parameters: dict[str, Any], *, on_dispatch=None) -> Any:
        if not isinstance(parameters, dict):
            raise GatewayError("Gateway parameters must be an object.")
        commands = await self.adiscover(domain)
        if command not in commands:
            raise GatewayError(f"Gateway command is unavailable: {domain}.{command}.")
        self._validate(parameters, commands[command].schema)
        response = await self._call(
            "GatewayExecute", {"domain": domain, "command": command, "parameters": parameters},
            on_dispatch=on_dispatch,
        )
        return normalize_tool_result(response)

    def execute(self, domain: str, command: str, parameters: dict[str, Any], *, on_dispatch=None) -> Any:
        return _run_sync(lambda: self.aexecute(domain, command, parameters, on_dispatch=on_dispatch))


# This list is code-owned. Federated Gateway metadata currently labels even
# Alpaca getters as "mutate"; descriptions or naming prefixes are not an
# authority to expand what an LLM may call. New capabilities require review.
ANALYSIS_COMMANDS: Mapping[str, frozenset[str]] = {
    "alpaca": frozenset(
        {
            "get_account_info",
            "get_account_config",
            "get_all_positions",
            "get_open_position",
            "get_orders",
            "get_order_by_client_id",
            "get_asset",
            "get_clock",
            "get_calendar",
            "get_portfolio_history",
            "get_stock_bars",
            "get_stock_latest_quote",
            "get_stock_latest_trade",
            "get_stock_snapshot",
            "get_news",
        }
    ),
    "maenifold.memory": frozenset({"SearchMemories", "ReadMemory"}),
    "laya": frozenset({"decide"}),
}


_CURRENT_ONLY = frozenset(
    {
        "get_account_info",
        "get_account_config",
        "get_all_positions",
        "get_open_position",
        "get_orders",
        "get_order_by_client_id",
        "get_asset",
        "get_clock",
        "get_stock_latest_quote",
        "get_stock_latest_trade",
        "get_stock_snapshot",
    }
)


def _parse_date_parameter(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise GatewayError(f"{name} must be an ISO date or timestamp.")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Alpaca accepts YYYY-MM-DD as UTC midnight. Be explicit when clamping.
        return stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp
    except ValueError as exc:
        raise GatewayError(f"{name} must be an ISO date or timestamp.") from exc


def _bound_parameters(
    command: GatewayCommand,
    parameters: dict[str, Any],
    symbol: str | None,
    trade_date: str | None,
) -> dict[str, Any]:
    """Constrain model-supplied market requests to the immutable run context."""
    bounded = copy.deepcopy(parameters)
    if command.domain != "alpaca":
        return bounded
    properties = command.schema.get("properties", {})
    if symbol:
        for key in ("symbols", "symbol", "symbol_or_asset_id"):
            if key in properties:
                provided = bounded.get(key)
                if provided is not None and str(provided).strip().upper() != symbol:
                    raise GatewayError(f"{key} must match the analysis symbol {symbol}.")
                bounded[key] = symbol
    if trade_date:
        as_of = date.fromisoformat(trade_date)
        market_zone = ZoneInfo("America/New_York")
        now = datetime.now(UTC)
        if as_of > now.astimezone(market_zone).date():
            raise GatewayError("The analysis date cannot be in the future.")
        if as_of != now.astimezone(market_zone).date() and command.name in _CURRENT_ONLY:
            raise GatewayError("This current-data tool cannot be used for a historical analysis.")
        cutoff = min(datetime.combine(as_of, datetime_time.max, market_zone), now)
        end_keys = [key for key in ("end", "until") if key in properties]
        for key in end_keys:
            provided = bounded.get(key)
            end = min(_parse_date_parameter(provided, key), cutoff) if provided else cutoff
            bounded[key] = end.astimezone(UTC).isoformat()
        for key in ("start", "after"):
            if key in bounded and bounded[key] is not None:
                start = _parse_date_parameter(bounded[key], key)
                if start > cutoff or any(
                    start > _parse_date_parameter(bounded[end], end) for end in end_keys
                ):
                    raise GatewayError("The requested date range starts after its analysis cutoff.")
        if "start" in properties and not bounded.get("start"):
            if command.name == "get_stock_bars":
                try:
                    lookback = timedelta(
                        days=float(bounded.get("days", 30)),
                        hours=float(bounded.get("hours", 0)),
                        minutes=float(bounded.get("minutes", 0)),
                    )
                except (ValueError, TypeError, OverflowError) as exc:
                    raise GatewayError("Invalid market-data lookback interval.") from exc
                if lookback <= timedelta(0) or lookback > timedelta(days=3650):
                    raise GatewayError(
                        "Market-data lookback must be positive and at most ten years."
                    )
            else:
                lookback = timedelta(days=30)
            end = _parse_date_parameter(bounded["end"], "end") if "end" in bounded else cutoff
            bounded["start"] = (end - lookback).astimezone(UTC).isoformat()
        if "asof" in properties:
            bounded["asof"] = trade_date
        if command.name == "get_calendar":
            # Calendar dates are session labels, not UTC instants. A New York
            # day's end falls on the following UTC date, which must not leak an
            # additional future session into a historical request.
            for key in ("start", "end"):
                original = parameters.get(key)
                if isinstance(original, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", original):
                    bounded[key] = min(date.fromisoformat(original), as_of).isoformat()
                elif key in bounded:
                    bounded[key] = (
                        _parse_date_parameter(bounded[key], key)
                        .astimezone(market_zone)
                        .date()
                        .isoformat()
                    )
        if command.name == "get_portfolio_history":
            bounded.pop("period", None)  # Alpaca forbids period with both start and end.
    return bounded


def build_langchain_tools(
    gateway: Gateway,
    *,
    domains: tuple[str, ...] | None = None,
    symbol: str | None = None,
    trade_date: str | None = None,
) -> list[Any]:
    """Bind only reviewed analysis commands, retaining each live JSON Schema."""
    from langchain_core.tools import StructuredTool, ToolException

    if symbol is not None:
        symbol = symbol.strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", symbol):
            raise GatewayError("Analysis symbol must be a valid US equity symbol.")
    if trade_date is not None:
        try:
            if date.fromisoformat(trade_date).isoformat() != trade_date:
                raise ValueError("noncanonical date")
        except (ValueError, TypeError) as exc:
            raise GatewayError("Analysis date must be YYYY-MM-DD.") from exc
        if date.fromisoformat(trade_date) > datetime.now(ZoneInfo("America/New_York")).date():
            raise GatewayError("The analysis date cannot be in the future.")
    tools = []
    for domain in domains if domains is not None else tuple(ANALYSIS_COMMANDS):
        if domain not in ANALYSIS_COMMANDS:
            raise GatewayError(f"Domain is not permitted for analysis tools: {domain}.")
        commands = gateway.discover(domain)
        for name in sorted(ANALYSIS_COMMANDS[domain] & commands.keys()):
            command = commands[name]
            if (
                trade_date
                and trade_date != datetime.now(ZoneInfo("America/New_York")).date().isoformat()
                and command.name in _CURRENT_ONLY
            ):
                continue

            def bind(selected: GatewayCommand) -> Callable[..., str]:
                def invoke(**parameters: Any) -> str:
                    with gateway_observation(selected.domain, selected.name, "gateway_invocation",
                                             purpose="analyst_tool") as observed:
                        try:
                            bounded = _bound_parameters(selected, parameters, symbol, trade_date)
                            observed["parameters"] = bounded
                            value = gateway.execute(selected.domain, selected.name, bounded)
                        except GatewayError as exc:
                            raise ToolException(str(exc)) from exc
                        observed.update(output=value, result_available=True)
                        return json.dumps(value, ensure_ascii=False, default=str)

                return invoke

            description = command.description
            schema = copy.deepcopy(command.schema)
            if symbol and domain == "alpaca":
                for key in ("symbols", "symbol", "symbol_or_asset_id"):
                    if key in schema.get("properties", {}):
                        schema["properties"][key]["const"] = symbol
                        schema["properties"][key]["default"] = symbol
            if trade_date and domain == "alpaca":
                description += f" Bound to analysis date {trade_date}; later end times are clamped."
            if domain == "laya":
                description += (
                    " Advisory analysis only. Report contract.grade and uncertainty. "
                    "The result never authorizes an order or overrides deterministic trading limits."
                )
            tools.append(
                StructuredTool.from_function(
                    func=bind(command),
                    name=f"{domain.replace('.', '_')}__{name}",
                    description=description,
                    args_schema=schema,
                    handle_tool_error=True,
                )
            )
    return tools


def verify_paper_configuration(gateway: Gateway) -> dict[str, Any]:
    """Return sanitized evidence that the Gateway Alpaca server is configured paper.

    Account balances, account-number prefixes and successful reads cannot prove
    paper mode. The current Alpaca MCP tool surface does not attest its runtime
    URL, so require the registered official server's explicit paper setting.
    Call immediately before submission and do not expose the raw system config.
    """
    config = gateway.execute("maenifold.system", "GetConfig", {})
    if not isinstance(config, dict):
        raise GatewayError("Unable to verify Alpaca paper configuration.")
    server = config.get("mcpServers", {}).get("alpaca", {})
    if not isinstance(server, dict):
        raise GatewayError("The Gateway has no verifiable Alpaca server configuration.")
    env = server.get("env") or {}
    args = server.get("args") or []
    command = str(server.get("command", "")).replace("\\", "/").rsplit("/", 1)[-1]
    official_server = (command in {"alpaca-mcp-server", "alpaca-mcp-server.exe"} and not args) or (
        command in {"uv", "uv.exe"} and args == ["tool", "run", "alpaca-mcp-server"]
    )
    if not official_server or not isinstance(env, dict):
        raise GatewayError("Cannot attest paper mode for this Alpaca MCP server command.")
    paper = env.get("ALPACA_PAPER_TRADE")
    if not isinstance(paper, str) or paper.strip().lower() != "true":
        raise GatewayError("Alpaca MCP must explicitly set ALPACA_PAPER_TRADE=true.")
    # Refuse conflicting overrides rather than assuming the boolean wins.
    for key in (
        "APCA_API_BASE_URL",
        "ALPACA_BASE_URL",
        "ALPACA_API_BASE_URL",
        "ALPACA_TRADE_API_URL",
    ):
        if key in env and str(env[key]).rstrip("/") != "https://paper-api.alpaca.markets":
            raise GatewayError("Alpaca has a conflicting trading endpoint override.")
    if server.get("envFromFile") or server.get("envFromCommand"):
        raise GatewayError("Indirect Alpaca environment overrides prevent paper verification.")
    return {
        "paper": True,
        "source": "maenifold.system.GetConfig:mcpServers.alpaca.env.ALPACA_PAPER_TRADE",
        "verification": "registered_server_configuration",
        "runtime_endpoint_attested": False,
    }
