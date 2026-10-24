"""Loopback-only HTTP entry point for the paper trading desk."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import socket
import subprocess
import secrets
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from zipfile import BadZipFile, LargeZipFile

from dotenv import load_dotenv

from tradingagents.integrations.maenifold import GatewayRateLimited

from .service import DeskService
from .app_database import StoreConflict
from .recovery import WriterBusy


class DeskServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, service):
        if address[0] != "127.0.0.1":
            raise ValueError("TradingAgents supports IPv4 loopback binding only")
        self.service = service
        self.csrf_token = secrets.token_urlsafe(32)
        self.session_token = secrets.token_urlsafe(32)
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

    def _same_origin(self, *, required=False):
        origin = self.headers.get("Origin")
        return (not required and origin is None) or origin in {
            f"http://127.0.0.1:{self.server.server_port}",
            f"http://localhost:{self.server.server_port}",
        }

    def _session(self):
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            value = cookie.get(f"tradingagents_session_{self.server.server_port}")
            return value is not None and secrets.compare_digest(value.value.encode(), self.server.session_token.encode())
        except CookieError:
            return False

    def _send(self, status, body, content_type="application/json; charset=utf-8", *, headers=None):
        if getattr(self, "quote_diagnostic", None) is not None:
            self.quote_diagnostic["status"] = status
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
        try:
            self.end_headers()
        except (ConnectionError, TimeoutError) as exc:
            if getattr(self, "quote_diagnostic", None) is not None:
                self.quote_diagnostic.update(transport_exception=type(exc).__name__, response_stage="headers")
            raise
        try:
            self.wfile.write(body)
            if getattr(self, "quote_diagnostic", None) is not None:
                self.quote_diagnostic["response_stage"] = "written"
        except (ConnectionError, TimeoutError) as exc:
            if getattr(self, "quote_diagnostic", None) is not None:
                self.quote_diagnostic.update(transport_exception=type(exc).__name__, response_stage="body")
            # A cancelled browser request does not invalidate the operation
            # already journaled by the service, and must not trigger a retry.
            self.close_connection = True

    def do_GET(self):
        if not urlsplit(self.path).path.startswith("/api/"):
            self._get()
            return
        with self.server.service.maintenance:
            self._get()

    def _get(self):
        if not self._same_host() or not self._same_origin():
            self._send(403, {"error": "Invalid local host."})
            return
        url = urlsplit(self.path)
        path = url.path
        if path.startswith("/api/") and not self._session():
            self._send(403, {"error": "Open or reload the local workspace to establish its session."})
            return
        if getattr(self.server.service, "recovery_only", False) and path not in {
                "/", "/index.html", "/static/recovery.js", "/static/app.css", "/api/state", "/api/health"}:
            self._send(503, {"error": "Recovery-only startup: engine, research and data operations are unavailable"})
            return
        if path == "/api/state":
            query = parse_qs(url.query)
            if query.get("compact") == ["1"]:
                state = self.server.service.state(compact=True, run_id=query.get("run_id", [None])[0])
            else:
                state = self.server.service.state()
            self._send(200, {**state, "csrf_token": self.server.csrf_token})
            return
        if path == "/api/portfolio-model":
            self._send(200, self.server.service.proposed_portfolio())
            return
        if path == "/api/workspace":
            self._send(200, self.server.service.workspace())
            return
        if path == "/api/discovery":
            query = parse_qs(url.query)
            try:
                result = self.server.service.discovery_detail(query.get("observation", [None])[0], query.get("symbol", [None])[0]) if query else self.server.service.discovery()
                self._send(200, result)
            except (ValueError, KeyError):
                self._send(400, {"error": "Retained discovery observation is unavailable"})
            return
        elif path == "/api/investor":
            self._send(200, self.server.service.investor())
            return
        if path == "/api/health":
            self._send(200, self.server.service.health())
            return
        if path == "/api/commands":
            self._send(200, self.server.service.admission.snapshot())
            return
        if path.startswith("/api/commands/") and "/receipts/" in path:
            try:
                parts = path.split("/")
                if len(parts) != 6 or parts[4] != "receipts":
                    raise ValueError("Unknown command receipt route")
                payload = self.server.service.command_receipt(parts[3], parts[5])
                self._send(200, payload, "application/json; charset=utf-8")
            except (ValueError, KeyError, OSError):
                self._send(400, {"error": "Saved command receipt is unavailable or changed"})
            return
        if path.startswith("/api/attention/occurrences/"):
            try:
                identity = path.removeprefix("/api/attention/occurrences/")
                result = self.server.service.attention_occurrence(identity, parse_qs(url.query).get("generation", [None])[0])
                self._send(200, result)
            except (OSError, ValueError, KeyError, TypeError):
                self._send(400, {"error": "Saved alert evidence is unavailable or the application generation changed"})
            return
        if path == "/api/attention":
            self._send(200, self.server.service.attention())
            return
        if path == "/api/market-history":
            try:
                query = parse_qs(url.query)
                symbol = query.get("symbol", [None])[0]
                result = self.server.service.data_jobs.detail(symbol, query.get("key", [None])[0], timeframe=query.get("timeframe", ["1Day"])[0]) if symbol else self.server.service.data_jobs.state()
                self._send(200, result)
            except (OSError, ValueError, KeyError):
                self._send(400, {"error": "Saved current-market history is unavailable or changed"})
            return
        if path == "/api/evaluations":
            try:
                query = parse_qs(url.query)
                identity, event = query.get("id", [None])[0], query.get("event_id", [None])[0]
                self._send(200, self.server.service.experiment_event(identity, event) if event else self.server.service.evaluations(identity))
            except (OSError, ValueError, KeyError):
                self._send(400, {"error": "Saved simulation evidence is unavailable or changed"})
            return
        if path == "/api/stock-evidence":
            try:
                from .stock_evidence import detail
                self._send(200, detail(self.server.service.data_jobs, parse_qs(url.query).get("symbol", [None])[0]))
            except (OSError, ValueError, KeyError):
                self._send(400, {"error": "Saved stock evidence is missing or changed"})
            return
        if path == "/api/reporting" or path.startswith("/api/reporting/collections/"):
            try:
                parts = path.split("/")
                if path == "/api/reporting":
                    self._send(200, self.server.service.reporting())
                elif len(parts) == 5:
                    self._send(200, self.server.service.reporting_detail(parts[4]))
                elif len(parts) == 7 and parts[5] == "receipts":
                    self._send(200, self.server.service.reporting_detail(parts[4], int(parts[6])), "application/json; charset=utf-8")
                else:
                    self._send(404, {"error": "Saved reporting route was not found"})
            except (ValueError, KeyError, StopIteration, IndexError, OSError):
                self._send(400, {"error": "Saved account-history source is missing, changed or unavailable"})
            return
        if path.startswith("/api/backups/"):
            try:
                payload = self.server.service.backup_download(path.removeprefix("/api/backups/"))
                self._send(200, payload, "application/zip", headers={"Content-Disposition": 'attachment; filename="tradingagents-backup.zip"'})
            except (ValueError, OSError):
                self._send(404, {"error": "Saved application backup was not found"})
            return
        if path.startswith("/api/runs/") or path.startswith("/api/instruments/"):
            try:
                parts = [unquote(part) for part in path.split("/")]
                if len(parts) == 4 and parts[2] == "instruments":
                    if parse_qs(url.query).get("refresh") == ["1"]:
                        result = self.server.service.chart(parts[3], force=True, run_id=parse_qs(url.query).get("run_id", [None])[0])
                    else:
                        result = self.server.service.chart(parts[3], run_id=parse_qs(url.query).get("run_id", [None])[0])
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
            "/static/nautilus.js": "nautilus.js",
            "/static/command-controls.js": "command-controls.js",
            "/static/market-chart.js": "market-chart.js",
            "/static/vendor/lightweight-charts-drawing/0.6.2/lightweight-charts-drawing.umd.js": "vendor/lightweight-charts-drawing/0.6.2/lightweight-charts-drawing.umd.js",
            "/static/vendor/lightweight-charts-drawing/0.6.2/LICENSE": "vendor/lightweight-charts-drawing/0.6.2/LICENSE",
            "/static/vendor/lightweight-charts-drawing/0.6.2/SOURCE.txt": "vendor/lightweight-charts-drawing/0.6.2/SOURCE.txt",
            "/static/vendor/lightweight-charts/5.2.1/lightweight-charts.standalone.production.js": "vendor/lightweight-charts/5.2.1/lightweight-charts.standalone.production.js",
            "/static/vendor/lightweight-charts/5.2.1/LICENSE": "vendor/lightweight-charts/5.2.1/LICENSE",
            "/static/vendor/lightweight-charts/5.2.1/NOTICE": "vendor/lightweight-charts/5.2.1/NOTICE",
            "/static/vendor/lightweight-charts/5.2.1/SOURCE.txt": "vendor/lightweight-charts/5.2.1/SOURCE.txt",
            "/static/styles.css": "styles.css",
            "/static/app.css": "app.css",
            "/static/ui-markets.css": "ui-markets.css",
            "/static/ui-instrument.css": "ui-instrument.css",
            "/static/ui-orders.css": "ui-orders.css",
            "/static/ui-research-journal.css": "ui-research-journal.css",
            "/static/recovery.js": "recovery.js",
        }
        if getattr(self.server.service, "recovery_only", False):
            files.update({"/": "recovery.html", "/index.html": "recovery.html"})
        if path not in files:
            self._send(404, {"error": "Not found."})
            return
        file = Path(__file__).parent / "static" / files[path]
        if not file.is_file():
            self._send(503, {"error": "Workspace assets are not installed."})
            return
        content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        headers = {"Set-Cookie": f"tradingagents_session_{self.server.server_port}={self.server.session_token}; HttpOnly; SameSite=Strict; Path=/"} if path in {"/", "/index.html"} else None
        self._send(200, file.read_bytes(), f"{content_type}; charset=utf-8", headers=headers)

    def do_POST(self):
        self.quote_diagnostic = None
        if urlsplit(self.path).path == "/api/quotes/refresh":
            request_id = self.headers.get("X-Request-ID", "")
            if len(request_id) != 32 or any(c not in "0123456789abcdef" for c in request_id):
                request_id = secrets.token_hex(16)
            self.quote_diagnostic = {"request_id": request_id, "method": "POST", "path": "/api/quotes/refresh"}
            self._quote_log("admitted")
        try:
            self._post()
        except Exception as exc:
            if self.quote_diagnostic is not None:
                self.quote_diagnostic["exception"] = type(exc).__name__
            raise
        finally:
            if self.quote_diagnostic is not None:
                self._quote_log("finished")
            self.quote_diagnostic = None

    def _quote_log(self, event):
        print(json.dumps({"time": datetime.now(timezone.utc).isoformat(), "event": event,
                          **self.quote_diagnostic}), file=sys.stderr, flush=True)

    def _post(self):
        if (
            not self._same_host()
            or not self._same_origin(required=True)
            or not self._session()
            or not secrets.compare_digest(
                self.headers.get("X-CSRF-Token", "").encode(), self.server.csrf_token.encode()
            )
        ):
            self.close_connection = True
            self._send(403, {"error": "Refresh the local workspace before making changes."})
            return
        maintenance_guard = None
        try:
            request_path = urlsplit(self.path).path
            length = int(self.headers.get("Content-Length", "0"))
            maximum = 90 * 1024 * 1024 if request_path == "/api/recovery" else 65536
            if not 0 < length <= maximum or self.headers.get("Transfer-Encoding"):
                raise ValueError("Request body exceeds the supported endpoint size boundary.")
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
            if not (path in {"/api/discovery", "/api/quotes/refresh", "/api/commands/reconcile", "/api/native-report"} or path == "/api/reporting" and data.get("action") == "collect" or
                    path == "/api/recovery" and data.get("action") in {"preview", "backup"} or
                    path == "/api/commands" and data.get("action") == "option_instruction" and data.get("operation") == "submit"):
                service.maintenance.acquire()
                maintenance_guard = service.maintenance
            if getattr(service, "recovery_only", False) and path != "/api/recovery":
                self._send(503, {"error": "Recovery-only startup accepts archive preview and deliberate restore only"})
                return
            if service.browse_only and path not in {
                    "/api/nautilus/start", "/api/nautilus/stop", "/api/refresh", "/api/quotes/refresh", "/api/config", "/api/workspace", "/api/investor", "/api/recovery", "/api/reporting", "/api/commands/reconcile", "/api/commands", "/api/trading/pause", "/api/attention", "/api/market-history", "/api/discovery", "/api/evaluations", "/api/native-report", "/api/runs/local-laya", "/api/portfolio-model"}:
                self._send(403, {"error": "Review-only session: new research, native Nautilus drafts, approvals, admission and broker writes are disabled. Local human proposals and baskets remain available."})
                return
            if path == "/api/orders" or path.startswith("/api/orders/"):
                self._send(400, {"error": "Legacy direct-order submission is unsupported. Use exact proposal approval, admission and Nautilus commands through /api/commands."})
                return
            if path == "/api/nautilus/start":
                result = service.start_native(data)
            elif path == "/api/nautilus/stop":
                result = service.runtime.stop()
            elif path == "/api/quotes/refresh":
                result = service.refresh_quotes()
            elif path == "/api/refresh":
                result = service.refresh()
            elif path == "/api/config":
                result = service.save_config(data)
            elif path == "/api/portfolio-model":
                result = service.model_portfolio(data)
            elif path == "/api/workspace":
                result = service.save_workspace(data)
            elif path == "/api/discovery":
                result = service.discovery(data)
            elif path == "/api/investor":
                result = service.save_investor(data)
            elif path == "/api/evaluations":
                result = service.evaluation_action(data)
            elif path == "/api/approvals":
                result = service.approval_action(data)
            elif path == "/api/admission":
                result = service.approval_action(data, admission=True)
            elif path == "/api/recovery":
                result = service.recovery_action(data)
                if getattr(service, "recovery_only", False) and result.get("restored"):
                    service.close()
                    try:
                        replacement = DeskService(service.application_root, runtime=service.runtime,
                                                  browse_only=service.launch_browse_only)
                        replacement.launch_browse_only = service.launch_browse_only
                    except Exception:
                        from .recovery import writer_lease
                        service.writer_lease = writer_lease(service.application_root)
                        raise
                    replacement.launch_root = service.original_root
                    self.server.service = replacement
                    result.update(promoted=True, restart_required=False,
                        message="Application records restored in a retained sibling generation. Native cache is in memory and is not restored; new orders remain blocked pending fresh reconciliation and review.")
            elif path == "/api/reporting":
                result = service.save_reporting(data)
            elif path == "/api/commands":
                result = service.command_action(data)
            elif path in {"/api/commands/dispatch", "/api/commands/cancel", "/api/commands/replace"}:
                result = service.command_action({**data, "action": {"/api/commands/dispatch": "submit", "/api/commands/cancel": "cancel", "/api/commands/replace": "replace"}[path]})
            elif path == "/api/commands/reconcile":
                result = service.reconcile_commands()
            elif path == "/api/attention":
                result = service.save_attention(data)
            elif path == "/api/native-report":
                result = service.native_report(data)
            elif path == "/api/market-history":
                result = service.data_jobs.request(data)
            elif path == "/api/runs":
                result = service.start_run(
                    data.get("symbols"), expected_revision=data.get("config_revision"),
                    analysis_date=data.get("analysis_date"),
                    exclude_fred=data.get("exclude_fred", False),
                )
            elif path == "/api/runs/local-laya":
                result = service.screen_saved_posts(data)
            elif path == "/api/runs/cancel":
                result = service.cancel_run(data["run_id"])
            elif path in {"/api/proposals", "/api/drafts"}:
                raise ValueError("Legacy native draft creation was retired. Save validated BUY/SELL proposals through the investor workspace.")
            elif path == "/api/trading/pause":
                result = service.command_action({**data, "action": "block", "blocked": data.get("paused")})
            else:
                self._send(404, {"error": "Not found."})
                return
            self._send(200, result)
        except PermissionError as exc:
            self._send(403, {"error": str(exc)})
        except StoreConflict as exc:
            self._send(409, {"error": str(exc), "current_revision": exc.revision})
        except WriterBusy as exc:
            self._send(409, {"error": str(exc), "recovery_cutover_blocked": True})
        except GatewayRateLimited as exc:
            self._send_rate_limit(exc)
        except (BadZipFile, LargeZipFile):
            self._send(400, {"error": "Invalid or damaged backup ZIP. Choose an intact TradingAgents backup archive and inspect it again."})
        except (ValueError, KeyError, StopIteration) as exc:
            if self.quote_diagnostic is not None:
                self.quote_diagnostic["exception"] = type(exc).__name__
            self.close_connection = True
            self._send(400, {"error": str(exc) or "Requested item was not found."})
        except Exception as exc:
            if self.quote_diagnostic is not None:
                self.quote_diagnostic["exception"] = type(exc).__name__
            self._send(
                502,
                {
                    "error": "The operation failed. Refresh the connection and inspect the workspace status."
                },
            )
        finally:
            if maintenance_guard is not None:
                maintenance_guard.release()

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
    parser.add_argument("--nautilus-python", type=Path, default=Path(__file__).resolve().parents[2] / ".venv-nautilus-v1" / "Scripts" / "python.exe")
    parser.add_argument("--alpaca-credentials-file", type=Path,
                        default=Path(r"C:\src\printer\apps\tradingagents\.env"))
    parser.add_argument("--browse-only", action="store_true", help="Browse saved runs and prepare local human proposals; disable research, native order drafts, approval and admission")
    parser.add_argument("--history-dir", type=Path, help="Read additional saved research without modifying its journal")
    parser.add_argument("--migrate-journal", action="store_true", help="One-time offline JSON migration; all source writers must be stopped first")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    credential_path = args.alpaca_credentials_file.resolve()
    from .recovery_mode import RecoveryService, preflight, recovery_root, startup_root
    from .recovery import writer_lease
    import sqlite3
    original_root = args.data_dir.resolve()
    protected_roots = [Path(__file__).parent / "static", original_root, recovery_root(original_root)]
    if args.history_dir:
        protected_roots.append(args.history_dir)
    if any(credential_path.is_relative_to(root.resolve()) for root in protected_roots):
        parser.error("Credentials must remain outside served assets and account/history backup directories")
    load_dotenv(credential_path, override=False)
    from tradingagents.integrations.maenifold import MaenifoldGateway

    from .nautilus_runtime import NautilusRuntime
    # Reserve the endpoint before any journal migration or startup recovery writes.
    try:
        server = DeskServer(("127.0.0.1", args.port), None)
    except OSError:
        parser.exit(2, f"Cannot bind 127.0.0.1:{args.port}. The port is occupied or unavailable; use the launcher to identify a matching instance. No processes were stopped.\n")
    try:
        try:
            directory = startup_root(original_root)
            with writer_lease(directory):
                preflight(directory, args.history_dir)
        except WriterBusy:
            raise  # Ownership conflicts are never evidence of corrupt records.
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as failure:
            runtime = NautilusRuntime(original_root / "nautilus", args.nautilus_python, args.alpaca_credentials_file,
                                      application_root=original_root)
            service = RecoveryService(original_root, failure, runtime)
        else:
            runtime = NautilusRuntime(directory / "nautilus", args.nautilus_python, args.alpaca_credentials_file,
                                      application_root=original_root)
            service = DeskService(directory, gateway=MaenifoldGateway(args.mcp_endpoint, timeout=90), runtime=runtime,
                                  browse_only=args.browse_only, history_dir=args.history_dir, migrate_legacy=args.migrate_journal)
            service.launch_root = original_root
            service.startup_errors = []
            if not args.browse_only:
                endpoint = urlsplit(args.mcp_endpoint)
                if endpoint.scheme == "http" and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}:
                    port = endpoint.port or 80
                    try:
                        with socket.create_connection((endpoint.hostname, port), timeout=1):
                            pass
                    except OSError:
                        try:
                            executable = shutil.which("maenifold")
                            if not executable:
                                raise FileNotFoundError("Installed Maenifold executable was not found on PATH")
                            subprocess.Popen([executable, "--http", "--port", str(port)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                        except OSError as failure:
                            service.startup_errors.append(f"Maenifold startup failed: {failure}")
                try:
                    service.start_native()
                except (OSError, ValueError) as failure:
                    with runtime.lock:
                        runtime.snapshot.update(status="error", read_only=True, error=f"Nautilus startup failed: {failure}")
        service.launch_browse_only = args.browse_only
        server.service = service
    except Exception:
        server.server_close()
        raise
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
