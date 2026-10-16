"""Loopback-only HTTP entry point for the paper trading desk."""

from __future__ import annotations

import argparse
import json
import mimetypes
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from tradingagents.integrations.maenifold import GatewayRateLimited

from .service import DeskService


class DeskServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, service):
        self.service = service
        self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(address, DeskHandler)


class DeskHandler(BaseHTTPRequestHandler):
    server: DeskServer
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def _same_host(self):
        return self.headers.get("Host") in {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }

    def _send(self, status, body, content_type="application/json; charset=utf-8", *, headers=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, str(value))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        self.end_headers()
        try:
            self.wfile.write(body)
        except (ConnectionError, TimeoutError):
            # A cancelled browser request does not invalidate the operation
            # already journaled by the service, and must not trigger a retry.
            self.close_connection = True

    def do_GET(self):
        if not self._same_host():
            self._send(403, {"error": "Invalid local host."})
            return
        url = urlsplit(self.path)
        path = url.path
        if path == "/api/state":
            query = parse_qs(url.query)
            if query.get("compact") == ["1"]:
                state = self.server.service.state(compact=True, run_id=query.get("run_id", [None])[0])
            else:
                state = self.server.service.state()
            self._send(200, {**state, "csrf_token": self.server.csrf_token})
            return
        if path.startswith("/api/runs/") or path.startswith("/api/instruments/"):
            try:
                parts = [unquote(part) for part in path.split("/")]
                if len(parts) == 4 and parts[2] == "instruments":
                    if parse_qs(url.query).get("refresh") == ["1"]:
                        result = self.server.service.chart(parts[3], force=True)
                    else:
                        result = self.server.service.chart(parts[3])
                elif len(parts) == 4 and parts[2] == "runs":
                    result = self.server.service.run_detail(parts[3])
                elif len(parts) == 6 and parts[2] == "runs" and parts[4] == "results":
                    result = self.server.service.run_detail(parts[3], parts[5])
                else:
                    self._send(404, {"error": "Not found."})
                    return
                self._send(200, result)
            except GatewayRateLimited as exc:
                self._send_rate_limit(exc)
            except (KeyError, StopIteration):
                self._send(404, {"error": "Research result was not found. Refresh the run list."})
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
            except Exception:
                self._send(502, {"error": "The detail could not be loaded. Try again."})
            return
        # Exact allowlist, never a caller-selected filesystem path.
        files = {
            "/": "index.html",
            "/index.html": "index.html",
            "/app.js": "app.js",
            "/styles.css": "styles.css",
            "/static/app.js": "app.js",
            "/static/lists.js": "lists.js",
            "/static/styles.css": "styles.css",
            "/static/app.css": "app.css",
        }
        if path not in files:
            self._send(404, {"error": "Not found."})
            return
        file = Path(__file__).parent / "static" / files[path]
        if not file.is_file():
            self._send(503, {"error": "Workspace assets are not installed."})
            return
        content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        self._send(200, file.read_bytes(), f"{content_type}; charset=utf-8")

    def do_POST(self):
        origin = self.headers.get("Origin")
        allowed_origins = {
            f"http://127.0.0.1:{self.server.server_port}",
            f"http://localhost:{self.server.server_port}",
        }
        if (
            not self._same_host()
            or (origin and origin not in allowed_origins)
            or not secrets.compare_digest(
                self.headers.get("X-CSRF-Token", ""), self.server.csrf_token
            )
        ):
            self.close_connection = True
            self._send(403, {"error": "Refresh the local workspace before making changes."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536 or self.headers.get("Transfer-Encoding"):
                raise ValueError("Request body must be between 1 and 65536 bytes.")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Send application/json.")
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Request body was truncated.")
            data = json.loads(
                body,
                parse_constant=lambda _: (_ for _ in ()).throw(
                    ValueError("Non-finite JSON number.")
                ),
            )
            if not isinstance(data, dict):
                raise ValueError("Request must be a JSON object.")
            service = self.server.service
            path = urlsplit(self.path).path
            if path == "/api/quotes/refresh":
                result = service.refresh_quotes()
            elif path == "/api/refresh":
                result = service.refresh()
            elif path == "/api/config":
                result = service.save_config(data)
            elif path == "/api/runs":
                result = service.start_run(
                    data.get("symbols"), expected_revision=data.get("config_revision"),
                    analysis_date=data.get("analysis_date"),
                )
            elif path == "/api/runs/cancel":
                result = service.cancel_run(data["run_id"])
            elif path == "/api/proposals":
                result = service.propose(data["run_id"])
            elif path == "/api/orders":
                result = service.submit(data["proposal_id"])
            elif path == "/api/orders/cancel":
                result = service.cancel_order(data["order_id"])
            elif path == "/api/trading/pause":
                result = service.pause(data["paused"])
            else:
                self._send(404, {"error": "Not found."})
                return
            self._send(200, result)
        except GatewayRateLimited as exc:
            self._send_rate_limit(exc)
        except (ValueError, KeyError, StopIteration) as exc:
            self.close_connection = True
            self._send(400, {"error": str(exc) or "Requested item was not found."})
        except Exception:
            self._send(
                502,
                {
                    "error": "The operation failed. Refresh the connection and inspect the workspace status."
                },
            )

    def _send_rate_limit(self, exc):
        self._send(429, {"error": str(exc), "retry_after": exc.retry_after},
                   headers={"Retry-After": exc.retry_after})

    def log_message(self, format, *args):
        # Never log request bodies, account details, or arbitrary URL query strings.
        pass


def main():
    parser = argparse.ArgumentParser(description="TradingAgents paper trading workspace")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--data-dir", type=Path, default=Path.cwd() / ".paper-desk")
    parser.add_argument("--mcp-endpoint", default="http://localhost:8080/mcp")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    from tradingagents.integrations.maenifold import MaenifoldGateway

    service = DeskService(args.data_dir, gateway=MaenifoldGateway(args.mcp_endpoint, timeout=90))
    server = DeskServer(("127.0.0.1", args.port), service)
    print(f"TradingAgents paper workspace: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.close()


if __name__ == "__main__":
    main()
