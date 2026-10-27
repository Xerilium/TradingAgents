"""Call the running local desk API using its normal session and CSRF checks."""

import argparse
from http.cookiejar import CookieJar
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPCookieProcessor, HTTPRedirectHandler, ProxyHandler, Request, build_opener,
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        "Requests never retry automatically. POST requires user authorization. "
        "Order approval and submission remain separate actions."
    ))
    parser.add_argument("method", choices=["get", "post"])
    parser.add_argument("path", help="API path, for example /api/state?compact=1")
    parser.add_argument("--json-file", type=Path, help="POST body: a UTF-8 JSON object")
    parser.add_argument("--dev", action="store_true", help="Use isolated development on 8099")
    parser.add_argument("--timeout", type=float, default=30, help="Seconds per request (default: 30)")
    parser.add_argument("--field", help="Print one dotted object field from the response")
    args = parser.parse_args()
    path = urlsplit(args.path)
    if path.scheme or path.netloc or path.fragment or not path.path.startswith("/api/"):
        parser.error("Use a local /api/ path, with an optional query string.")
    if args.timeout <= 0 or args.timeout == float("inf") or args.timeout != args.timeout:
        parser.error("--timeout must be a positive finite number.")
    if (args.method == "post") != (args.json_file is not None):
        parser.error("Use --json-file for POST only; POST requires a JSON object.")
    try:
        body = None
        if args.json_file:
            value = json.loads(args.json_file.read_text(encoding="utf-8-sig"))
            if not isinstance(value, dict):
                parser.error("The POST body must be a JSON object.")
            body = json.dumps(value, allow_nan=False).encode("utf-8")
        base = f"http://127.0.0.1:{8099 if args.dev else 8098}"
        opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()), NoRedirect())

        def call(route, data=None, headers=None):
            request = Request(base + route, data=data, headers=headers or {})
            with opener.open(request, timeout=args.timeout) as response:
                return response.read()

        call("/")
        headers = {"Accept": "application/json"}
        if body is not None:
            state = json.loads(call("/api/state?compact=1"))
            headers.update({"Origin": base, "Content-Type": "application/json",
                            "X-CSRF-Token": state["csrf_token"]})
        result = json.loads(call(args.path, body, headers))
        if isinstance(result, dict):
            result.pop("csrf_token", None)
        if args.field:
            for key in args.field.split("."):
                result = result[key]
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except HTTPError as exc:
        print(f"HTTP {exc.code}: request failed; no automatic retry. Inspect the app's state before retrying a POST.", file=sys.stderr)
        try:
            detail = json.loads(exc.read())
            if isinstance(detail, dict) and "error" in detail:
                print(json.dumps({"error": detail["error"]}, ensure_ascii=False), file=sys.stderr)
        except (OSError, ValueError):
            pass
    except (OSError, URLError, ValueError, KeyError, TypeError) as exc:
        print(f"Request failed ({type(exc).__name__}); no automatic retry. Inspect the app's state before retrying a POST.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
