import asyncio
import inspect
import logging
import math
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError as UrlHTTPError
from uuid import uuid4

from requests import HTTPError

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorUnavailableError,
)
from tradingagents.dataflows.vendors.alpha_vantage import (
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_global_news as get_alpha_vantage_global_news,
    get_income_statement as get_alpha_vantage_income_statement,
    get_indicator as get_alpha_vantage_indicator,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_stock as get_alpha_vantage_stock,
)
from tradingagents.dataflows.vendors.fred import get_macro_data as get_fred_macro_data
from tradingagents.dataflows.vendors.polymarket import (
    get_prediction_markets as get_polymarket_prediction_markets,
)
from tradingagents.dataflows.vendors.sec_edgar import (
    get_balance_sheet as get_sec_edgar_balance_sheet,
    get_cashflow as get_sec_edgar_cashflow,
    get_income_statement as get_sec_edgar_income_statement,
)
from tradingagents.dataflows.vendors.yahoo.fundamentals import (
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_fundamentals as get_yfinance_fundamentals,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from tradingagents.dataflows.vendors.yahoo.market import (
    get_stock_stats_indicators_window,
    get_YFin_data_online,
)
from tradingagents.dataflows.vendors.yahoo.news import get_global_news_yfinance, get_news_yfinance

logger = logging.getLogger(__name__)

_evidence_recorder = ContextVar("vendor_evidence_recorder", default=None)
_evidence_parent = ContextVar("vendor_evidence_parent", default=None)
_source_requirement = ContextVar("source_requirement", default="required")


@contextmanager
def capture_vendor_evidence(recorder):
    """Bind the desk's recorder to this execution context, including graph child tasks."""
    token = _evidence_recorder.set(recorder)
    parent_token = _evidence_parent.set(None)
    try:
        yield
    finally:
        _evidence_parent.reset(parent_token)
        _evidence_recorder.reset(token)


def _call_observation(domain, command, boundary, eligible, parameters, purpose, ordinal, origin):
    observation = {"receipt": {}, "output": None, "result_available": False, "parameters": parameters}
    recorder = _evidence_recorder.get()
    receipt = observation["receipt"]
    receipt.update(
        attempt_id=str(uuid4()), parent_attempt_id=_evidence_parent.get(),
        operation=command, vendor=domain, boundary_kind=boundary,
        origin=origin, purpose=purpose, ordinal=ordinal,
        category="source" if eligible else "control_plane", capture_eligible=eligible,
        started_at=datetime.now(UTC).isoformat(), ended_at=None,
        elapsed_seconds=None, outcome="running",
        representation="sdk_envelope_serialization_not_wire_bytes" if boundary == "gateway_transport"
        else "normalized_caller_value",
    )
    if origin == "jev":
        receipt["representation"] = "requests_post_body_and_parsed_json" if boundary == "jev_post" else "screening_inputs_or_results"

    def emit():
        if recorder is None:
            return
        try:
            recorder(dict(receipt), {
                "parameters": observation["parameters"],
                "result": observation["output"],
                "result_available": observation["result_available"],
            } if eligible else None)
        except Exception:
            logger.error("Call evidence persistence failed; capture is incomplete.")

    observation["emit"] = emit
    observation["enabled"] = recorder is not None
    return observation


def queued_jev_job(index, state):
    observation = _call_observation("jev", "system_one", "jev_job", True, state, None, None, "jev")
    observation["receipt"].update(outcome="queued", post_index=index, queued_at=datetime.now(UTC).isoformat(), started_at=None)
    observation["emit"]()
    return observation


def observe_jev_call(boundary, *, parameters=None, ordinal=None, observation=None):
    return observe_gateway_call("jev", "system_one" if boundary != "jev_batch" else "screen",
                                boundary, eligible=True, parameters=parameters, ordinal=ordinal,
                                origin="jev", observation=observation)


def _gateway_failure_details(error):
    """Retain bounded cause diagnostics without arbitrary exception/source text."""
    pending, seen, details = [error], set(), []
    messages = (r"All connection attempts failed|Connection refused|actively refused it|"
                r"connection reset|connection aborted|connection closed|server disconnected|"
                r"timed out|timeout|name resolution failed|No such host is known|"
                r"certificate verify failed|SSL handshake failed|unsupported protocol|"
                r"MCP operation failed|unhandled errors in a TaskGroup|invalid JSON|"
                r"JSON Schema|schema validation failed|Missing required argument|"
                r"SESSION_MISSING|CONCEPT_NOT_FOUND|concept not found|not configured|no news response|"
                r"no news articles tagged|maintenance|rate limited|temporarily unavailable")
    while pending and len(details) < 6:
        current = pending.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        text = current.args[0][:512] if current.args and isinstance(current.args[0], str) else ""
        # Extract known diagnostic phrases only: never serialize URLs, quoted inputs,
        # HTTP fields, response bodies, schema instances, or arbitrary message suffixes.
        phrases = re.findall(messages, text, flags=re.IGNORECASE)
        detail = {"class": type(current).__name__[:80],
                  "message": "; ".join(dict.fromkeys(phrases))[:256] or "Exception details withheld"}
        for name, value in (("errno", getattr(current, "errno", None)),
                            ("winerror", getattr(current, "winerror", None)),
                            ("http_status", getattr(getattr(current, "response", None), "status_code", None))):
            if type(value) is int:
                detail[name] = value
        rule = getattr(current, "validator", None)
        if isinstance(rule, str) and rule in {"required", "additionalProperties", "type", "enum", "const", "minimum", "maximum", "oneOf", "anyOf", "allOf", "format"}:
            detail["schema_rule"] = rule
        details.append(detail)
        cause = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
        reason = getattr(current, "reason", None)
        pending.extend(([cause] if cause else []) + ([reason] if isinstance(reason, BaseException) else [])
                       + list(getattr(current, "exceptions", ()))[:6])
    return details


@contextmanager
def observe_gateway_call(domain, command, boundary, *, eligible=False, parameters=None,
                         purpose=None, ordinal=None, origin="gateway", observation=None):
    """Observe an existing call without substituting its values or exceptions."""
    observation = observation or _call_observation(domain, command, boundary, eligible, parameters, purpose, ordinal, origin)
    if not observation["enabled"]:
        yield observation
        return
    receipt = observation["receipt"]
    receipt.update(outcome="running", started_at=datetime.now(UTC).isoformat())
    emit = observation["emit"]

    emit()
    started = time.monotonic()
    token = _evidence_parent.set(receipt["attempt_id"])
    try:
        yield observation
        if receipt["outcome"] == "running":
            receipt["outcome"] = "success"
    except BaseException as exc:
        kind = type(exc).__name__
        unknown = (isinstance(exc, (asyncio.CancelledError, TimeoutError)) or kind == "GatewayTimeout"
                   or (boundary == "gateway_transport" and not observation["result_available"]
                       and kind != "GatewayRateLimited"))
        receipt.update(outcome="unknown" if unknown else "deferred" if kind == "GatewayRateLimited" else
                       receipt["outcome"] if receipt["outcome"] in {"deferred", "unknown"} else "error",
                       error_class=kind if kind in {"GatewayError", "GatewayTimeout", "GatewayRateLimited",
                                                   "CancelledError", "TimeoutError", "TypeSafeError"} else "UnexpectedError")
        if origin == "gateway":
            receipt["error_details"] = _gateway_failure_details(exc)
        if kind == "GatewayRateLimited":
            receipt["retry_after_seconds"] = exc.retry_after
        raise
    finally:
        _evidence_parent.reset(token)
        receipt.update(ended_at=datetime.now(UTC).isoformat(), elapsed_seconds=time.monotonic() - started)
        emit()


def _error_class(error):
    return type(error).__name__[:80]


def _logged_error(error):
    return _error_class(error) if _evidence_recorder.get() is not None else error


def _source_arguments(function, args, kwargs):
    """Retain only recognizable supplied ticker/date values, never arbitrary kwargs."""
    try:
        bound = inspect.signature(function).bind_partial(*args, **kwargs).arguments
    except (ValueError, TypeError):
        return {}, "unavailable"
    return _safe_source_arguments(bound), "bounded_research_arguments"


def _safe_source_arguments(bound):
    selected = {}
    for key, value in bound.items():
        if isinstance(value, str) and (
            (key in {"symbol", "ticker"} and re.fullmatch(r"[A-Za-z0-9.^=+_-]{1,32}", value))
            or (key in {"indicator", "freq"} and re.fullmatch(r"[A-Za-z0-9_,-]{1,256}", value))
            or (key in {"start_date", "end_date", "curr_date", "current_date", "as_of_date", "trade_date"}
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T[0-9:.+Z-]+)?", value))
        ):
            selected[key] = value
    return selected


def observe_source_call(operation, vendor, origin, acquire, *, requirement=None, retry=None, **arguments):
    """Observe one existing acquisition, without adding calls or changing its return.

    These boundaries can nest inside router attempts; they are not additional
    provider requests. Origins describe the consumed representation, not HTTP
    internals hidden by a cache parser or SDK.
    """
    if requirement is None and operation in {"reddit_rss", "stocktwits_stream"}:
        requirement = "supplemental"
    return _invoke_vendor(operation, vendor, acquire, (), {}, origin=origin, source_arguments=arguments, requirement=requirement, retry=retry)


def source_failure_details(error):
    details = _gateway_failure_details(error)
    status = getattr(error, "http_status", None) or getattr(error, "code", None) or getattr(getattr(error, "response", None), "status_code", None)
    names = {item["class"] for item in details}
    kind = ("unconfigured" if isinstance(error, VendorNotConfiguredError) else
            "no_usable_coverage" if isinstance(error, NoMarketDataError) else
            "authentication_or_access" if status in {401, 403} else
            "invalid_request" if status in {400, 422} else
            "not_found" if status == 404 else
            "rate_limited" if status == 429 or "YFRateLimitError" in names else
            "transient_server" if status in {500, 502, 503, 504} else
            "transient_transport" if names.intersection({"Timeout", "TimeoutError", "ReadTimeout", "ConnectTimeout", "ConnectionError", "ConnectionResetError", "RemoteDisconnected", "IncompleteRead"}) else
            "invalid_response" if names.intersection({"ParseError", "JSONDecodeError", "UnicodeDecodeError"}) else
            "invalid_request" if isinstance(error, (ValueError, TypeError)) else "source_unavailable")
    return {"failure_kind": kind, "error_details": details,
            **({"http_status": status} if type(status) is int else {})}


def source_retry_plan(error, *, attempt, remaining):
    details = source_failure_details(error)
    value = getattr(error, "retry_after", None)
    if value is None:
        headers = getattr(error, "headers", None) or getattr(getattr(error, "response", None), "headers", {})
        value = headers.get("Retry-After") if headers else None
    try:
        delay = float(value)
    except (TypeError, ValueError):
        try:
            delay = parsedate_to_datetime(value).timestamp() - time.time()
        except (TypeError, ValueError, OverflowError):
            delay = 60.0 if details["failure_kind"] == "rate_limited" else 1.0
    delay = max(0.0, delay) if math.isfinite(delay) else 60.0
    eligible = details["failure_kind"] in {"rate_limited", "transient_server", "transient_transport"}
    return {"attempt": attempt, **details, "retry_after_seconds": delay,
            "retry_action": "retry" if eligible and attempt == 1 and delay < remaining and delay <= 60 else "defer" if eligible else "stop"}


def _invoke_vendor(method, vendor, function, args, kwargs, *, origin="vendor_function_return", source_arguments=None, requirement=None, retry=None):
    requirement = requirement or _source_requirement.get()
    recorder = _evidence_recorder.get()
    if recorder is None:
        return function(*args, **kwargs)
    arguments, argument_scope = _source_arguments(function, args, kwargs)
    if source_arguments is not None:
        arguments = _safe_source_arguments(source_arguments)
    receipt = {
        "attempt_id": str(uuid4()), "operation": method, "vendor": vendor,
        "origin": origin, "parent_attempt_id": _evidence_parent.get(),
        "boundary_kind": "router_function" if source_arguments is None else "acquisition",
        "function": f"{getattr(function, '__module__', '')}.{getattr(function, '__qualname__', type(function).__name__)}",
        "arguments": arguments, "argument_scope": argument_scope,
        "requirement": requirement,
        "started_at": datetime.now(UTC).isoformat(), "ended_at": None,
        "elapsed_seconds": None, "outcome": "running",
    }

    def emit(output=None):
        try:
            recorder(dict(receipt), output)
        except Exception:
            # Recording must never change vendor fallback or the analytical result.
            logger.error("Router evidence persistence failed; capture is incomplete.")

    emit()
    started = time.monotonic()
    output = None
    parent_token = _evidence_parent.set(receipt["attempt_id"])
    requirement_token = _source_requirement.set(requirement)
    try:
        output = function(*args, **kwargs)
        receipt["outcome"] = "success"
        if isinstance(output, str):
            receipt["data_status"] = ("no_usable_coverage" if output.lstrip().startswith("NO_DATA_AVAILABLE") else "empty" if re.match(
                r"(?is)\s*(?:No (?:news|articles|posts|markets) found|<no .*posts found)", output) else "unavailable" if re.match(
                r"(?is)\s*(?:DATA_UNAVAILABLE|<[^>]*unavailable|Polymarket data is currently unavailable|.*?are withheld for)", output)
                else "partial" if "DATA_PARTIAL:" in output else "returned_unvalidated")
        return output
    except Exception as exc:
        receipt.update(outcome="error", error_class=_error_class(exc), retry_action="stop", **source_failure_details(exc))
        if isinstance(exc, (HTTPError, UrlHTTPError)):
            receipt["error_class"] = "HTTPError"
        if isinstance(exc, HTTPError) and exc.response is not None:
            status = exc.response.status_code
            if type(status) is int and 100 <= status <= 599:
                receipt.update(error_class="HTTPError", http_status=status)
                if method == "read_research_source" and vendor == "public_source" and origin == "source_document_text":
                    receipt["source_url"] = exc.response.url
        raise
    finally:
        _evidence_parent.reset(parent_token)
        _source_requirement.reset(requirement_token)
        receipt.update(retry or {})
        receipt.update(ended_at=datetime.now(UTC).isoformat(), elapsed_seconds=time.monotonic() - started)
        emit(output)

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    },
    "macro_data": {
        "description": "Macroeconomic indicators (rates, inflation, labor, growth)",
        "tools": [
            "get_macro_indicators",
        ]
    },
    "prediction_markets": {
        "description": "Market-implied probabilities for forward-looking events",
        "tools": [
            "get_prediction_markets",
        ]
    }
}

# Optional enrichment categories. These add macro/event context to the news
# analyst but are not core to a decision, so a vendor failure here degrades to a
# sentinel instead of aborting the run (a bad LLM-supplied indicator, a missing
# key, or a network blip should not crash an analysis over flavour data). Core
# categories (prices, fundamentals, news) still raise so a broken primary is loud.
OPTIONAL_CATEGORIES = {"macro_data", "prediction_markets"}

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "sec_edgar": get_sec_edgar_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "sec_edgar": get_sec_edgar_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "sec_edgar": get_sec_edgar_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
    # macro_data
    "get_macro_indicators": {
        "fred": get_fred_macro_data,
    },
    # prediction_markets
    "get_prediction_markets": {
        "polymarket": get_polymarket_prediction_markets,
    },
}


def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")


def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")


def vendor_unavailable(method: str, error: Exception) -> str:
    """What a call returns when every vendor was throttled or unreachable."""
    return (
        f"DATA_UNAVAILABLE: no configured vendor could serve {method} right now "
        f"({error}). This says nothing about the instrument; report the "
        f"data as unavailable and do not estimate or fabricate values."
    )


def no_data_available(error: NoMarketDataError) -> str:
    """What a call returns when every vendor that answered had no usable data."""
    resolved = "" if error.canonical == error.symbol else f" (resolved to '{error.canonical}')"
    # Surface the typed error's detail (e.g. "latest row is 2025-06-11 ...
    # stale") so the agent sees the specific reason — invalid symbol, no
    # coverage, or stale data — not just a generic "unavailable".
    reason = f" ({error.detail})" if error.detail else ""
    return (
        f"NO_DATA_AVAILABLE: No usable market data for '{error.symbol}'{resolved} from "
        f"any configured vendor{reason}. The symbol may be invalid, delisted, "
        f"not covered, or the vendor returned stale data. Do not estimate or "
        f"fabricate values — report that data is unavailable for this symbol."
    )


def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    optional = category in OPTIONAL_CATEGORIES or method in {"get_news", "get_global_news"}
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    all_available_vendors = list(VENDOR_METHODS[method].keys())

    # The configured vendor list IS the chain: we do NOT silently fall back to
    # vendors the user did not choose (#988/#289) — that returned data from an
    # unexpected source and caused cross-vendor inconsistencies. For multi-vendor
    # fallback, list them in order, e.g. data_vendors="yfinance,alpha_vantage".
    # The "default" sentinel (no explicit config) uses all available vendors.
    explicit = [v for v in primary_vendors if v and v != "default"]
    if explicit:
        vendor_chain = [v for v in explicit if v in VENDOR_METHODS[method]]
        if not vendor_chain:
            raise ValueError(
                f"Configured vendor(s) {explicit} not available for '{method}'. "
                f"Available: {all_available_vendors}."
            )
    else:
        vendor_chain = all_available_vendors

    last_no_data: NoMarketDataError | None = None
    last_unavailable: VendorUnavailableError | None = None
    failed: Exception | None = None     # a vendor that raised something untyped
    first_error: Exception | None = None
    for vendor in vendor_chain:
        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return _invoke_vendor(method, vendor, impl_func, args, kwargs,
                                  requirement="supplemental" if optional else "required")
        except VendorUnavailableError as e:
            logger.warning("Vendor %r unavailable for %s: %s; trying next vendor.", vendor, method, _logged_error(e))
            # Kept so an all-unavailable chain can say the vendor was the
            # problem, rather than reporting nothing about the symbol.
            last_unavailable = e
            continue
        except VendorNotConfiguredError as e:
            logger.warning("Vendor %r not configured for %s; trying next vendor.", vendor, method)
            if first_error is None:
                first_error = e  # Surface it if no other vendor can serve the call.
            continue
        except NoMarketDataError as e:
            last_no_data = e  # No data here; another configured vendor may have it
            continue
        except Exception as e:
            # Don't let one vendor's failure crash the call when another can
            # serve it, but never swallow silently: a broken primary must be
            # visible in the logs (#989), not hidden behind a fallback's verdict.
            logger.warning("Vendor %r failed for %s: %s", vendor, method, _logged_error(e))
            if first_error is None:
                first_error = e
            failed = e
            continue

    # A vendor that throttled or failed the request never said whether it has
    # the symbol, so no other vendor's "no data" can speak for the whole chain:
    # report the vendors as the problem, not the instrument. It must not end
    # the run either.
    if last_unavailable is not None:
        return vendor_unavailable(method, last_unavailable)
    if failed is not None and last_no_data is not None:
        return vendor_unavailable(method, failed)

    # Every vendor that answered reported "no data": the symbol is genuinely unavailable.
    # Return one explicit, instructive sentinel rather than a vendor-specific
    # empty string, so the agent reports "unavailable" instead of inventing a
    # value. This takes precedence over incidental fallback errors.
    if last_no_data is not None:
        if first_error is not None:
            # A vendor also hit a real error; surface it in logs so the no-data
            # verdict can't hide a broken primary (network/auth/etc.).
            logger.warning(
                "Returning NO_DATA for %s, but a vendor errored earlier: %s",
                method, _logged_error(first_error),
            )
        return no_data_available(last_no_data)

    # No vendor returned data and none reported clean "no data" — surface the
    # first real error (e.g. the primary vendor's network failure). Optional
    # enrichment categories degrade to a sentinel instead, so flavour data can't
    # abort the run.
    if first_error is not None:
        if optional:
            logger.warning("Optional %s unavailable for %s: %s", category, method, _logged_error(first_error))
            return (
                f"DATA_UNAVAILABLE: optional {category} could not be retrieved "
                f"({first_error}). Proceed without it; do not fabricate values."
            )
        raise first_error

    raise RuntimeError(f"No available vendor for '{method}'")
