"""Daily SPY rebalancing through the existing paper order admission path."""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .admission import ACTIVE, DEFAULT as COMMANDS
from .baskets import preview
from .investor import DEFAULT as INVESTOR, decimal, fractional_asset, instruments, price_evidence, save, working_commitments
from .portfolio_weights import PortfolioWeights


RECORD = "spy_paper_rebalance"
DEFAULT = {"enabled": False, "account_id": None, "managed_symbols": [], "run": None}
PAPER = "https://paper-api.alpaca.markets"
NEW_YORK = ZoneInfo("America/New_York")
CONSTRAINTS = {"account_max_age_seconds": "90", "quote_max_age_seconds": "300", "approval_max_age_seconds": "30"}


def paper_account(runtime):
    account = runtime.get("account") or {}
    identity = runtime.get("connection_identity") or {}
    if (runtime.get("status") == "connected" and runtime.get("endpoint") == PAPER
            and identity.get("observed_mode") == "paper" and identity.get("endpoint") == PAPER
            and account.get("id") and identity.get("account_id") == account["id"]
            and runtime.get("connection_session") and runtime["connection_session"] == runtime.get("native_epoch")
            and account.get("currency") == "USD"):
        return account["id"]
    return None


class SpyRebalance:
    def __init__(self, desk):
        self.desk = desk
        self.future = None
        self.next_poll = 0.0
        self.stopped = False
        self.weights = None

    def status(self, runtime):
        record = self.desk.store.database.read(RECORD, DEFAULT)
        data = record["data"]
        run = data["run"]
        return {"revision": record["revision"], "enabled": data["enabled"], "account_id": data["account_id"],
                "eligible_account_id": paper_account(runtime),
                "run": {key: run.get(key) for key in ("session", "as_of", "status", "message", "completed", "total", "limited")} if run else None}

    def configure(self, request):
        database = self.desk.store.database
        enabled = request["action"] == "spy_rebalance_enable"
        if enabled:
            self.desk.admission.enabled()
            account_id = paper_account(self.desk.admission.checked_observation(CONSTRAINTS))
            if not account_id or request.get("account_id") != account_id or request.get("dedicated") is not True:
                raise ValueError("Confirm the exact connected Alpaca paper account is dedicated to tracking SPY.")
        def update(data):
            if enabled:
                if data["account_id"] not in (None, account_id):
                    raise ValueError("This SPY loop is bound to a different paper account.")
                data["account_id"] = account_id
            data["enabled"] = enabled
        database.update(RECORD, request.get("rebalance_revision"), update, DEFAULT)

    def latest_weights(self, store):
        with self.desk.maintenance:
            if self.desk.store is not store:
                raise ValueError("The application workspace changed.")
            if self.weights is None or self.weights.store is not store:
                self.weights = PortfolioWeights(store)
            weights = self.weights
        result = weights.refresh()
        snapshot = result.get("snapshot") or {}
        if result["status"] != "ready" or snapshot.get("provider") != "State Street SPY":
            raise ValueError(result.get("error") or "State Street SPY holdings are unavailable.")
        positive = sum(Decimal(entry["weight"]) > 0 for entry in snapshot["entries"])
        if not 500 <= positive <= 510 or Decimal(snapshot["cash_weight"]) > Decimal("0.01"):
            raise ValueError("State Street holdings do not reconcile to a complete SPY portfolio.")
        return snapshot

    def check_weights(self):
        snapshot = self.latest_weights(self.desk.store)
        return {"as_of": snapshot["as_of"], "positions": len(snapshot["entries"]), "cash_weight": snapshot["cash_weight"]}

    def tick(self):
        if self.stopped or self.desk.browse_only or time.monotonic() < self.next_poll:
            return
        self.next_poll = time.monotonic() + 5
        if self.future is not None and not self.future.done():
            return
        store = self.desk.store
        data = store.database.read(RECORD, DEFAULT)["data"]
        if not data["enabled"]:
            return
        runtime = self.desk.runtime.state()
        if runtime.get("market_open") is not True or paper_account(runtime) != data["account_id"]:
            return
        session = datetime.now(NEW_YORK).date()
        run = data["run"]
        if run and run["session"] == session.isoformat() and run["status"] in {"completed", "blocked"}:
            return
        self.future = self.desk.data_jobs.executor.submit(self.step, store, session)

    def step(self, store, session):
        database = store.database
        record = database.read(RECORD, DEFAULT)
        data = record["data"]
        if not data["enabled"] or self.stopped or self.desk.store is not store:
            return
        day, run = session.isoformat(), data["run"]
        fresh_run = not run or run["session"] != day or run["status"] == "waiting"
        try:
            if fresh_run:
                self.next_poll = time.monotonic() + 60
                new_run, symbols = self.prepare(store, session, data)
                def save_plan(saved):
                    saved.update(run=new_run, managed_symbols=symbols)
                database.update(RECORD, record["revision"], save_plan, DEFAULT)
                self.next_poll = time.monotonic() + 5
                return
            self.advance(store, record)
        except (ValueError, PermissionError, ArithmeticError, OSError, KeyError, TypeError) as error:
            from .app_database import StoreConflict
            if isinstance(error, StoreConflict):
                return
            current = database.read(RECORD, DEFAULT)
            if not current["data"]["enabled"] or self.desk.store is not store:
                return
            def fail(saved):
                if fresh_run:
                    saved["run"] = {"session": day, "status": "waiting", "message": str(error)}
                else:
                    saved["run"].update(status="blocked", message=str(error))
            try:
                database.update(RECORD, current["revision"], fail, DEFAULT)
            except StoreConflict:
                pass

    def checked_account(self, account_id):
        self.desk.admission.enabled()
        runtime = self.desk.admission.checked_observation(CONSTRAINTS)
        if paper_account(runtime) != account_id or runtime.get("market_open") is not True:
            raise ValueError("The dedicated paper account and an open regular session are required.")
        return runtime

    def prepare(self, store, session, data):
        self.checked_account(data["account_id"])
        query = urlencode({"start": (session - timedelta(days=14)).isoformat(), "end": session.isoformat()})
        calendar = self.desk.data_jobs.read("/v2/calendar?" + query, data=False, canceled=lambda: self.stopped)["data"]
        day = session.isoformat()
        dates = {item["date"] for item in calendar}
        prior = max((value for value in dates if value < day), default=None)
        if day not in dates or not prior:
            raise ValueError("The Alpaca calendar does not confirm this session and the previous session.")
        snapshot = self.latest_weights(store)
        if snapshot["as_of"] != prior:
            raise ValueError(f"Waiting for State Street SPY holdings dated {prior}.")
        runtime = self.checked_account(data["account_id"])
        records = store.database.read("commands", COMMANDS)["data"]
        self.require_no_working_orders(runtime, records)
        weights = {entry["symbol"]: Decimal(entry["weight"]) for entry in snapshot["entries"] if Decimal(entry["weight"]) > 0}
        positions = self.check_positions(runtime, set(weights) | set(data["managed_symbols"]))
        symbols = sorted(set(weights) | set(positions))
        self.ensure_symbols(store, data["account_id"], runtime, symbols)
        supported = instruments(runtime, symbols)
        missing = [symbol for symbol in symbols if not supported[symbol]["supported"]]
        if missing:
            raise ValueError(f"Waiting for {len(missing)} supported Alpaca assets, including " + ", ".join(missing[:8]) + ".")
        reason = f"Daily SPY paper rebalance using State Street holdings dated {prior} (SHA-256 {snapshot['source_sha256']})."
        targets = [{"symbol": symbol, "mode": "weight", "value": str(weight * 100), "order_type": "MARKET"}
                   for symbol, weight in weights.items()]
        targets.extend({"symbol": symbol, "mode": "quantity", "value": "0", "order_type": "MARKET"}
                       for symbol in sorted(positions.keys() - weights.keys()))
        investor = store.database.read("investor", INVESTOR)["data"]
        basket = preview(investor, {"targets": targets, "reason": reason}, runtime, (), commands=records)
        missing = [row["symbol"] for row in basket["targets"] if row["desired_quantity"] is None or row["valuation_price"] is None]
        if missing:
            raise ValueError("Waiting for prices to size: " + ", ".join(missing))
        legs = [leg["terms"] for leg in basket["legs"] if leg["terms"]["side"] == "SELL"
                or (decimal(leg["impact"]["estimated_principal"]) or Decimal(0)) >= 1]
        legs.sort(key=lambda terms: terms["side"] != "SELL")
        return {"session": day, "as_of": prior, "status": "ready" if legs else "completed",
                "message": "Waiting for the first order." if legs else "No orders needed.",
                "legs": legs, "completed": 0, "total": len(legs), "limited": 0, "command_id": None,
                "source_sha256": snapshot["source_sha256"],
                "current": {symbol: str(quantity) for symbol, quantity in positions.items()}}, symbols

    def ensure_symbols(self, store, account_id, runtime, symbols):
        if set(symbols).issubset(runtime["desired_symbols"]):
            return
        with self.desk.maintenance:
            if self.desk.store is not store or not store.database.read(RECORD, DEFAULT)["data"]["enabled"]:
                raise ValueError("The daily SPY loop was paused or the workspace changed.")
            self.checked_account(account_id)
            self.desk.configure_symbols(additional_symbols=symbols)
        raise ValueError("Waiting for Alpaca instruments and prices for the SPY holdings.")

    @staticmethod
    def check_positions(runtime, managed):
        positions = {}
        for row in runtime.get("positions", []):
            symbol = row["symbol"]
            quantity = decimal(row.get("qty"))
            if symbol not in managed or quantity is None or quantity < 0 or row.get("side") == "short":
                raise ValueError(f"{symbol}: The dedicated account has an unrelated or unsupported holding.")
            positions[symbol] = quantity
        return positions

    @staticmethod
    def require_no_working_orders(runtime, commands):
        commitments, known = working_commitments(runtime, commands)
        if (not known or commitments or commands.get("recovery_required") or commands.get("new_orders_blocked")
                or any(item["state"] in ACTIVE for item in commands["commands"].values())):
            raise ValueError("Existing orders or an account block must clear before SPY can rebalance.")

    def advance(self, store, record):
        database = store.database
        data, run = record["data"], record["data"]["run"]
        def update(**changes):
            def change(saved):
                saved["run"].update(changes)
            return database.update(RECORD, record["revision"], change, DEFAULT)

        runtime = self.checked_account(data["account_id"])
        commands = database.read("commands", COMMANDS)["data"]
        if run["command_id"]:
            command = commands["commands"].get(run["command_id"]) or {}
            if command.get("state") in ACTIVE:
                return
            if command.get("state") != "filled":
                raise ValueError("The prior SPY order did not fill. Review its broker result.")
            completed = run["completed"] + 1
            done = completed == run["total"]
            update(status="completed" if done else "ready", completed=completed, command_id=None,
                   message="Daily plan complete." if done else "Waiting for the next order.")
            return
        if run["status"] == "dispatching":
            raise ValueError("An interrupted SPY order needs review before another order can be sent.")
        self.require_no_working_orders(runtime, commands)
        if not set(data["managed_symbols"]).issubset(runtime["desired_symbols"]):
            try:
                self.ensure_symbols(store, data["account_id"], runtime, data["managed_symbols"])
            except ValueError as error:
                update(message=str(error))
            return
        positions = self.check_positions(runtime, set(data["managed_symbols"]))
        terms = dict(run["legs"][run["completed"]])
        symbol = terms["symbol"]
        if positions.get(symbol, Decimal(0)) != Decimal(run["current"].get(symbol, "0")):
            raise ValueError(f"{symbol}: The holding changed after the daily plan was made.")
        limited = run["limited"]
        if terms["side"] == "BUY":
            price = price_evidence(terms, runtime)["price"]
            cash = decimal(runtime["account"].get("cash"))
            if price is None or cash is None or cash < 0:
                raise ValueError(f"{symbol}: The buy requires a current price and enough observed cash.")
            limit = price.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
            try:
                fractional_asset(runtime, symbol)
                increment = Decimal("0.000000001")
            except ValueError:
                increment = Decimal(1)
            planned = Decimal(terms["quantity"])
            quantity = min(planned, cash / limit).quantize(increment, rounding=ROUND_FLOOR)
            if quantity * limit < 1:
                completed = run["completed"] + 1
                update(completed=completed, limited=limited + 1,
                       status="completed" if completed == run["total"] else "ready",
                       message=f"{symbol}: Buy skipped because observed cash allows less than $1.")
                return
            limited += quantity < planned
            terms.update(order_type="LIMIT", limit_price=str(limit), quantity=format(quantity.normalize(), "f"))
        with self.desk.maintenance:
            if self.stopped or self.desk.store is not store:
                return
            self.checked_account(data["account_id"])
            claimed = update(status="dispatching", message=f"Preparing {symbol}.")
            command_id = self.admit(terms, runtime, data["account_id"])
            database.update(RECORD, claimed["revision"], lambda saved: saved["run"].update(
                status="waiting_fill", command_id=command_id, limited=limited, message=f"Waiting for {symbol} to fill."), DEFAULT)
            self.desk.runtime.request("dispatch", command_id=command_id, action="submit")

    def admit(self, terms, runtime, account_id):
        from .admission import invalidate
        admission = self.desk.admission
        def draft(records):
            records["investor"] = save(records["investor"], {"action": "draft", "terms": terms, "reason": terms["rationale"]},
                                      runtime, (), self.desk._proposal_research, commands=records["commands"])
            proposal = records["investor"]["proposals"][0]
            review = admission.assess(records, proposal, runtime, CONSTRAINTS)
            if not review["passed"]:
                raise ValueError(f"{terms['symbol']}: " + "; ".join(review["blockers"]))
            return invalidate(records)
        result = admission.transaction(draft, evidence=True)
        proposal = result["investor"]["data"]["proposals"][0]
        expected = {name: result[name]["revision"] for name in ("investor", "commands")}
        approved = admission.approve(proposal["id"], actor=f"standing-paper-spy:{account_id}", reason=terms["rationale"],
            constraints=CONSTRAINTS, proposal_revision=proposal["revision"], policy_revision=proposal["policy_revision"],
            evaluation_binding_sha256=proposal["risk_evaluation"]["binding_sha256"], expected=expected)
        approval = next(item for item in approved["commands"]["data"]["approvals"].values() if item["proposal_id"] == proposal["id"])
        context = approval.get("connection_context") or {}
        if (context.get("account_id"), context.get("endpoint"), context.get("mode")) != (account_id, PAPER, "paper"):
            raise ValueError("Approval does not match the dedicated Alpaca paper account.")
        self.checked_account(account_id)
        return admission.submit_approved(approval["id"], expected={name: approved[name]["revision"] for name in ("investor", "commands")})
