"""Configured Alpaca REST; native execution supplies the durable user authority."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

DEFAULT_CREDENTIALS = Path(r"C:\src\printer\apps\tradingagents\.env")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class AlpacaREST:
    def __init__(self, credentials_file=DEFAULT_CREDENTIALS, *, permit_paper_execution=False):
        self.credentials_file = Path(credentials_file)
        self.permit_paper_execution = permit_paper_execution

    def read(self, path, *, data=False):
        return self._request(path, "GET", data=data)

    def read_receipt(self, path, *, data=False):
        return self._request(path, "GET", receipt=True, data=data)

    def submit_order(self, body):
        if not self.permit_paper_execution:
            raise ValueError("This transport instance does not permit execution")
        required = {"symbol", "qty", "side", "type", "time_in_force", "client_order_id", "extended_hours"}
        if (set(body) != required | ({"limit_price"} if body.get("type") == "limit" else set())
                or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", body["symbol"])
                or body["side"] not in {"buy", "sell"} or body["type"] not in {"market", "limit"}
                or body["time_in_force"] != "day" or not re.fullmatch(r"[1-9]\d{0,17}", str(body["qty"]))
                or body["extended_hours"] is not False or not isinstance(body["client_order_id"], str)
                or not 1 <= len(body["client_order_id"]) <= 48):
            raise ValueError("Only whole-share BUY/SELL MARKET/LIMIT DAY regular-session equity terms are supported")
        if body["type"] == "limit":
            self._limit(body["limit_price"])
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
        if str(UUID(order_id)) != order_id or set(body) - {"qty", "limit_price", "client_order_id"} or "client_order_id" not in body:
            raise ValueError("Replacement requires the existing broker identity and reviewed quantity/limit terms")
        if "qty" in body and not re.fullmatch(r"[1-9]\d{0,17}", str(body["qty"])):
            raise ValueError("Replacement quantity must be positive whole shares")
        if "limit_price" in body:
            self._limit(body["limit_price"])
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
        base = "https://data.alpaca.markets" if data else trading_endpoint(self.credentials_file)
        request = Request(base + path, method=method, headers=credentials(self.credentials_file),
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
    value = _configuration(credentials_file).get("APCA_API_BASE_URL", "https://paper-api.alpaca.markets").rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Configured Alpaca base URL must be an HTTP(S) origin/path without credentials, query or fragment")
    return value[:-3] if parsed.path.endswith("/v2") else value


def credentials(credentials_file):
    values = _configuration(credentials_file)
    key = values.get("APCA_API_KEY_ID") or values.get("ACPA_API_KEY_ID")
    secret = values.get("APCA_API_SECRET_KEY") or values.get("ACPA_API_SECRET_KEY")
    if not key or not secret:
        raise ValueError("Alpaca credentials are missing from the configured file")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret, "Content-Type": "application/json"}


def read(path, credentials_file=DEFAULT_CREDENTIALS, *, data=False):
    return AlpacaREST(credentials_file).read(path, data=data)
