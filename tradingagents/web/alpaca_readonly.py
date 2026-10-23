"""Configured Alpaca REST; native execution supplies the durable user authority."""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

DEFAULT_CREDENTIALS = Path(r"C:\src\printer\apps\tradingagents\.env")
TRADING_ORIGINS = {"https://paper-api.alpaca.markets": "paper", "https://api.alpaca.markets": "live"}


def normalize_trading_endpoint(value):
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except (ValueError, AttributeError):
        raise ValueError("Invalid Alpaca trading origin") from None
    if (parsed.scheme != "https" or parsed.hostname not in {"paper-api.alpaca.markets", "api.alpaca.markets"}
            or port not in (None, 443) or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path.rstrip("/") not in {"", "/v2"}):
        raise ValueError("Alpaca trading URL must be the official HTTPS paper or live origin, optionally ending in /v2")
    return "https://" + parsed.hostname


@dataclass(frozen=True, repr=False)
class ConnectionConfig:
    """Private immutable authentication and destination for one native session."""
    endpoint: str
    _key: str
    _secret: str

    def __post_init__(self):
        object.__setattr__(self, "endpoint", normalize_trading_endpoint(self.endpoint))
        if not self._key or not self._secret:
            raise ValueError("Alpaca credentials are missing from the configured file")

    @classmethod
    def load(cls, credentials_file=DEFAULT_CREDENTIALS):
        values = _configuration(credentials_file)
        return cls(values.get("APCA_API_BASE_URL", "https://paper-api.alpaca.markets"),
                   values.get("APCA_API_KEY_ID") or values.get("ACPA_API_KEY_ID"),
                   values.get("APCA_API_SECRET_KEY") or values.get("ACPA_API_SECRET_KEY"))

    @property
    def mode(self):
        return TRADING_ORIGINS[self.endpoint]

    @property
    def stream_url(self):
        return self.endpoint.replace("https://", "wss://", 1) + "/stream"

    def headers(self):
        return {"APCA-API-KEY-ID": self._key, "APCA-API-SECRET-KEY": self._secret, "Content-Type": "application/json"}

    def redact(self, message):
        return message.replace(self._key, "[redacted]").replace(self._secret, "[redacted]")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class AlpacaREST:
    def __init__(self, credentials_file=DEFAULT_CREDENTIALS, *, permit_paper_execution=False, connection=None):
        self.credentials_file = Path(credentials_file)
        self.connection = connection if connection is not None else ConnectionConfig.load(credentials_file)
        self.permit_paper_execution = permit_paper_execution

    def read(self, path, *, data=False):
        return self._request(path, "GET", data=data)

    def read_receipt(self, path, *, data=False):
        return self._request(path, "GET", receipt=True, data=data)

    def submit_order(self, body):
        from .linked_orders import fractional_terms, session_terms
        if not self.permit_paper_execution:
            raise ValueError("This transport instance does not permit execution")
        required = {"symbol", "qty", "side", "type", "time_in_force", "client_order_id", "extended_hours"}
        group = body.get("order_class", "simple")
        extra = ({"order_class"} | ({"take_profit"} if "take_profit" in body else set()) | ({"stop_loss"} if "stop_loss" in body else set())) if group != "simple" else set()
        prices = ({"limit_price"} if body.get("type") in {"limit", "stop_limit"} and group != "oco" else set()) | ({"stop_price"} if body.get("type") in {"stop", "stop_limit"} else set())
        if body.get("type") == "trailing_stop":
            from .linked_orders import trailing_terms
            trail = trailing_terms({"order_type": "TRAILING_STOP_MARKET", "quantity": body["qty"], "side": body["side"].upper(),
                "time_in_force": body["time_in_force"].upper(), "exit_plan": body if group != "simple" else None,
                "trail_price": body.get("trail_price"), "trail_percent": body.get("trail_percent")})
            prices.add(trail[0])
        if (set(body) != required | prices | extra
                or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", body["symbol"])
                or body["side"] not in {"buy", "sell"} or body["type"] not in {"market", "limit", "stop", "stop_limit", "trailing_stop"}
                or body["time_in_force"] not in {"day", "gtc"}
                or type(body["extended_hours"]) is not bool or not isinstance(body["client_order_id"], str)
                or not 1 <= len(body["client_order_id"]) <= 48):
            raise ValueError("Only exact reviewed quantity-sized equity terms are supported")
        session = "extended" if body["extended_hours"] else "regular"
        session_terms({"session": session, "order_type": body["type"].upper(), "time_in_force": body["time_in_force"].upper(),
                       "exit_plan": body if group != "simple" else None})
        fractional_terms({"quantity": body["qty"], "time_in_force": body["time_in_force"].upper(),
                          "session": session, "order_type": body["type"].upper(),
                          "exit_plan": body if group != "simple" else None})
        if group != "simple":
            from .linked_orders import broker_payload
            plan = {"take_profit": (body.get("take_profit") or {}).get("limit_price"),
                    "stop_price": (body.get("stop_loss") or {}).get("stop_price"),
                    "stop_limit_price": (body.get("stop_loss") or {}).get("limit_price")}
            if group not in {"oto", "bracket", "oco"} or body["side"] != ("sell" if group == "oco" else "buy") or body != broker_payload({
                    "symbol": body["symbol"], "quantity": body["qty"], "side": body["side"].upper(), "order_type": body["type"].upper(),
                    "time_in_force": body["time_in_force"].upper(), "limit_price": plan["take_profit"] if group == "oco" else body.get("limit_price"), "exit_plan": plan}, body["client_order_id"]):
                raise ValueError("Linked payload differs from the reviewed OTO/bracket/OCO contract")
        if "limit_price" in body:
            self._limit(body["limit_price"])
        if "stop_price" in body:
            self._limit(body["stop_price"])
        if body["side"] == "buy" and body["type"] == "stop":
            raise ValueError("BUY stop-market broker conversion is not mapped; explicit stop-limit terms are required")
        if body["type"] == "stop_limit":
            from decimal import Decimal
            limit, trigger = Decimal(body["limit_price"]), Decimal(body["stop_price"])
            if (body["side"] == "buy" and limit < trigger) or (body["side"] == "sell" and limit > trigger):
                raise ValueError("Stop-limit price is on the wrong side of its trigger")
        return self._request("/v2/orders", "POST", body, receipt=True)

    @staticmethod
    def _limit(value):
        from decimal import Decimal
        if not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", str(value)) or Decimal(str(value)) <= 0:
            raise ValueError("Limit price must be positive with at most two decimal places")

    def cancel_order(self, order_id):
        if str(UUID(order_id)) != order_id:
            raise ValueError("Single-order cancellation requires an exact broker UUID")
        return self._request("/v2/orders/" + order_id, "DELETE", receipt=True)

    def replace_order(self, order_id, body):
        if str(UUID(order_id)) != order_id or set(body) - {"qty", "limit_price", "stop_price", "client_order_id"} or "client_order_id" not in body:
            raise ValueError("Replacement requires the existing broker identity and reviewed quantity/limit terms")
        if "qty" in body:
            from .linked_orders import equity_quantity
            if equity_quantity(body["qty"]) % 1:
                raise ValueError("Fractional quantity cannot be patched; retain quantity and amend prices only")
        if "limit_price" in body:
            self._limit(body["limit_price"])
        if "stop_price" in body:
            self._limit(body["stop_price"])
        if not isinstance(body["client_order_id"], str) or not 1 <= len(body["client_order_id"]) <= 48:
            raise ValueError("Replacement client identity is invalid")
        return self._request("/v2/orders/" + order_id, "PATCH", body, receipt=True)

    def _request(self, path, method, body=None, *, data=False, receipt=False):
        if method != "GET":
            single = re.fullmatch(r"/v2/orders/[0-9a-f-]{36}", path)
            if (not self.permit_paper_execution or data or not
                    (method == "POST" and path == "/v2/orders" or method in {"PATCH", "DELETE"} and single)):
                raise ValueError("Broker write is disabled or unsupported")
        allowed_data = data and method == "GET" and path.split("?", 1)[0] in {"/v1beta1/news", "/v1/corporate-actions"}
        if (not path.startswith("/v2/") and not allowed_data) or "://" in path:
            raise ValueError("Invalid Alpaca path")
        base = "https://data.alpaca.markets" if data else self.connection.endpoint
        request = Request(base + path, method=method, headers=self.connection.headers(),
                          data=None if body is None else json.dumps(body).encode("utf-8"))
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            if receipt:
                payload = response.read(8 * 1024 * 1024 + 1)
                if len(payload) > 8 * 1024 * 1024:
                    raise ValueError("Account-history response exceeds its receipt size boundary")
                return {"raw": payload, "data": json.loads(payload, parse_float=str) if payload else None,
                        "received_at": datetime.now(UTC).isoformat(), "source_date": response.headers.get("Date")}
            return json.load(response)


def _configuration(credentials_file):
    values = {}
    for line in Path(credentials_file).read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


def trading_endpoint(credentials_file=DEFAULT_CREDENTIALS):
    return normalize_trading_endpoint(_configuration(credentials_file).get("APCA_API_BASE_URL", "https://paper-api.alpaca.markets"))


def credentials(credentials_file):
    return ConnectionConfig.load(credentials_file).headers()


def read(path, credentials_file=DEFAULT_CREDENTIALS, *, data=False):
    return AlpacaREST(credentials_file).read(path, data=data)
