"""Isolated, visibly labelled UI fixture. No MCP, model, broker or credentials."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

STATIC = Path(__file__).resolve().parents[2] / "tradingagents/web/static"
SYMBOLS = [f"S{i:03}" for i in range(500)]
now = datetime.now(timezone.utc)
stamp = now.isoformat()
config = {"name": "500-stock verification fixture", "universe": SYMBOLS,
    "allocation_pct": 70, "reserve_pct": 20, "max_position_pct": 15,
    "max_order_notional": 5000, "llm_provider": "chatgpt", "backend_url": None,
    "deep_think_llm": "gpt-6-sol", "quick_think_llm": "gpt-6-luna",
    "max_debate_rounds": 1, "max_risk_discuss_rounds": 1}
results = [{"symbol": symbol, "status": "failed" if i % 17 == 0 else "completed",
    "rating": ["Buy", "Hold", "Sell"][i % 3], "trade_date": now.date().isoformat(),
    "revision": 1, "elapsed_seconds": 180,
    "error": "Simulated source failure" if i % 17 == 0 else None,
    "report_keys": ["market_report", "final_trade_decision"],
    "laya": {"grade": "ask_human" if i % 3 == 2 else "pass",
             "auto_execute": i % 3 != 2}}
    for i, symbol in enumerate(SYMBOLS)]
run = {"id": "verification-run", "status": "completed", "created_at": stamp,
    "symbols": SYMBOLS, "config": config.copy(), "results": results,
    "counts": {"completed": 470, "failed": 30, "queued": 0, "running": 0},
    "events": [{"timestamp": stamp, "message": "Synthetic verification evidence only"}],
    "event_count": 1}
state = {"config": config, "config_revision": 1, "csrf_token": "fixture",
    "connection": {"connected": True, "paper_verified": True,
                   "domains": ["maenifold", "laya", "alpaca"]},
    "readiness": {"ready": True}, "account": {"equity": "100000", "cash": "75000",
        "buying_power": "75000", "last_equity": "99000"},
    "quotes": {symbol: {"price": 100+i, "change_pct": (i % 21-10)/10,
        "bid": 99.9+i, "ask": 100.1+i,
        "timestamp": (now-timedelta(hours=1)).isoformat() if i >= 450 else stamp,
        "feed": "Synthetic fixture"} for i, symbol in enumerate(SYMBOLS[:480])},
    "positions": [{"symbol": symbol, "qty": "2", "market_value": "100",
                   "avg_entry_price": "50", "unrealized_pl": "0"} for symbol in SYMBOLS],
    "orders": [{"id": f"fixture-order-{i}", "symbol": symbol, "side": "buy",
                "status": "filled", "qty": "2", "filled_qty": "2",
                "limit_price": "50", "filled_avg_price": "50", "submitted_at": stamp}
               for i, symbol in enumerate(SYMBOLS)],
    "proposals": [{"id": f"fixture-proposal-{i}", "symbol": symbol, "side": "buy",
        "status": "blocked" if i % 3 == 2 else "ready", "qty": "2", "limit_price": "50",
        "notional": "100", "reason": "Synthetic fixture: individually reviewed order"}
        for i, symbol in enumerate(SYMBOLS)],
    "research": {result["symbol"]: {**result, "run_id": run["id"]} for result in results},
    "runs": [run], "errors": [], "history": {}, "updated_at": stamp,
    "clock": {"is_open": False}, "trading_paused": False}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, value, status=200, kind="application/json"):
        data = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except ConnectionError:
            pass

    def do_GET(self):
        route = self.path.split("?")[0]
        if route == "/api/state":
            return self.send(state)
        if route.startswith("/api/instruments/"):
            return self.send({"symbol": route.rsplit("/", 1)[-1], "bars": [
                {"t": (now-timedelta(days=30-i)).date().isoformat(), "o": 100+i,
                 "h": 102+i, "l": 99+i, "c": 101+i, "v": 10000} for i in range(30)]})
        if "/results/" in route:
            symbol = route.rsplit("/", 1)[-1]
            result = next((r for r in results if r["symbol"] == symbol), None)
            if not result:
                return self.send({"error": "Fixture result not found"}, 404)
            return self.send({**result, "reports": {"market_report":
                "# Synthetic evidence\n\nThis isolated fixture does not represent market facts.\n\n| Check | Result |\n| --- | --- |\n| Symbol | " + symbol + " |",
                "final_trade_decision": "# Fixture decision\n\n**Rating:** " + result["rating"]}})
        if route == "/api/runs/verification-run":
            return self.send(run)
        allowed = {"/": ("index.html", "text/html"), "/static/app.js": ("app.js", "text/javascript"),
            "/static/lists.js": ("lists.js", "text/javascript"), "/static/app.css": ("app.css", "text/css")}
        if route in allowed:
            file, kind = allowed[route]
            content = (STATIC/file).read_bytes()
            if file == "index.html":
                content = content.replace(b'<main id="main"', b'<div role="note" style="padding:12px;background:#684c11;color:white">VERIFICATION FIXTURE \xc2\xb7 500 synthetic stocks \xc2\xb7 No broker or model connected</div><main id="main"')
            return self.send(content, kind=kind)
        self.send({"error": "Fixture route not found"}, 404)

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        if self.path == "/api/config":
            state["config"] = {**state["config"], **data}
            state["config_revision"] += 1
            return self.send(state["config"])
        if self.path == "/api/refresh":
            return self.send(state)
        # The workload review can be inspected but never starts actual research.
        self.send({"error": "Verification fixture: no research or execution is performed."}, 409)

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8090), Handler).serve_forever()
