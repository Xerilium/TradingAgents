"""Daily SPY rebalancing through the existing paper order admission path."""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from urllib.parse import urlencode
from uuid import uuid4
from zoneinfo import ZoneInfo

from .admission import ACTIVE, DEFAULT as COMMANDS, ReconciliationPending, instant
from .linked_orders import execution_id
from .approval_review import read_artifact
from .baskets import preview
from .investor import DEFAULT as INVESTOR, RULES, decimal, fractional_asset, instruments, price_evidence, save, working_commitments
from .fund_plans import DEFAULT as FUNDS, RECORD as FUND_RECORD, account_key, binding, budget
from .market_history import DEFAULT as HISTORY
from .policy_evaluation import evaluate as evaluate_policy
from .portfolio_weights import PortfolioWeights
from .stock_evidence import DEFAULT as EVIDENCE


RECORD = "spy_paper_rebalance"
DEFAULT = {"enabled": False, "account_id": None, "managed_symbols": [], "run": None}
PAPER = "https://paper-api.alpaca.markets"
NEW_YORK = ZoneInfo("America/New_York")
CONSTRAINTS = {"account_max_age_seconds": "90", "quote_max_age_seconds": "300", "approval_max_age_seconds": "30"}
ACTIVE_RUN = {"queued", "ready", "dispatching", "waiting_fill", "waiting_acceptance"}
PREVIEW_AGE = 300
QUOTE_RULES = {"max_spread_bps", "min_quote_size", "session_freshness"}


def rule_limit(policy, name, default):
    rule = policy["rules"].get(name, {})
    return Decimal(rule["value"]) if rule.get("state") == "enabled" else Decimal(default)


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
        self.manual_preview = None
        self.observed_progress = None
        self.post_fill_refreshed = set()
        self.wake_pending = False

    def step_finished(self, future):
        with self.desk.maintenance:
            wake, self.wake_pending = self.wake_pending, False
            if wake:
                self.tick(wake=True)

    def observe(self, runtime):
        run = self.desk.store.database.read(RECORD, DEFAULT)["data"]["run"]
        if not run or run["status"] not in ACTIVE_RUN:
            return
        command = self.desk.store.database.read("commands", COMMANDS)["data"]["commands"].get(run.get("command_id"), {})
        progress = (run.get("manual_id"), run["session"], run["status"], run["completed"],
                    command.get("id"), command.get("state"), runtime.get("account_observation_started_at"))
        if progress != self.observed_progress:
            self.observed_progress = progress
            self.tick(wake=True)

    @staticmethod
    def active_manual_run(data):
        run = data["run"]
        return run and run.get("manual") is True and run["status"] in ACTIVE_RUN

    def status(self, runtime):
        record = self.desk.store.database.read(RECORD, DEFAULT)
        data = record["data"]
        run = data["run"]
        return {"revision": record["revision"], "enabled": data["enabled"], "account_id": data["account_id"],
                "eligible_account_id": paper_account(runtime),
                "in_progress": bool(run and run["session"] >= datetime.now(NEW_YORK).date().isoformat()
                                    and run["status"] in ACTIVE_RUN),
                "run": {key: run.get(key) for key in ("session", "as_of", "status", "message", "completed", "total", "limited")} if run else None}

    def configure(self, request):
        with self.desk.maintenance:
            return self._configure(request)

    def _configure(self, request):
        database = self.desk.store.database
        enabled = request["action"] == "spy_rebalance_enable"
        if enabled:
            self.desk.admission.enabled()
            runtime = self.desk.admission.checked_observation(CONSTRAINTS)
            account_id = paper_account(runtime)
            if not account_id or request.get("account_id") != account_id or request.get("dedicated") is not True:
                raise ValueError("Confirm the exact connected Alpaca paper account is dedicated to tracking SPY.")
            plans = database.read(FUND_RECORD, FUNDS)["data"]
            binding(plans, account_id)
            budget(plans["plans"].get(account_key(account_id)), runtime, database.read("investor", INVESTOR)["data"]["policy"])
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

    def remaining_plan(self, store, runtime, data):
        run = data["run"]
        day = datetime.now(NEW_YORK).date().isoformat()
        if (not run or run.get("status") != "blocked" or run.get("session") != day
                or not run.get("manual_id") or not run.get("close_at") or not run.get("legs")
                or run.get("total") != len(run["legs"]) or not 0 <= run.get("completed", -1) < run["total"]):
            raise ValueError("A same-session interrupted reviewed rebalance is required. Preview a new plan instead.")
        if (paper_account(runtime) != data["account_id"] or runtime.get("market_open") is not True
                or datetime.now(NEW_YORK) >= datetime.fromisoformat(run["close_at"])):
            raise ValueError("The original paper account and open approved session are required.")
        rebound = {**run, "connection_session": runtime["connection_session"]}
        policy = self.check_plan_policy(store, rebound)
        plan = self.check_fund_binding(store, runtime, rebound)
        commands = store.database.read("commands", COMMANDS)["data"]
        dispatched = dict(run.get("dispatched", {}))
        expected = self.expected_positions(runtime, commands, run)
        completed = run["completed"]
        if run.get("command_id"):
            command = commands["commands"].get(run["command_id"], {})
            leg = run["legs"][completed]
            filled = self.checked_submitted(runtime, command)
            quantity = decimal(command.get("terms", {}).get("quantity"))
            if (command.get("account_id") != run["account_id"]
                    or any(command.get(key) != leg[key] for key in ("symbol", "side", "instrument_id"))
                    or quantity > Decimal(leg["quantity"]) or leg["side"] == "SELL" and quantity != Decimal(leg["quantity"])):
                raise ValueError("The interrupted leg differs from its original reviewed order. Reconcile orders first.")
            symbol = leg["symbol"]
            expected[symbol] = expected.get(symbol, Decimal(0)) + filled * (1 if leg["side"] == "BUY" else -1)
            expected = {key: value for key, value in expected.items() if value != 0}
            dispatched[run["command_id"]] = "0"
            completed += 1
        elif not dispatched and run.get("fills_completed") == 0 and decimal(runtime["account"].get("cash")) != decimal(run.get("initial_cash")):
            raise ValueError("Paper cash changed after the original plan. Preview a new plan instead.")
        self.require_no_working_orders(runtime, commands, allowed=dispatched)
        positions = {key: value for key, value in self.check_positions(runtime, set(data["managed_symbols"])).items() if value != 0}
        if positions != expected:
            raise ValueError("Current holdings do not match the original run and its proven fills. Reconcile before continuing.")
        legs = run["legs"][completed:]
        fund_budget = budget(plan, runtime, policy)
        fund_budget["spendable_cash_usd"] = str(self.spendable_cash(runtime, policy, plan, commands))
        return {**rebound, "legs": legs, "completed": 0, "fills_completed": 0, "total": len(legs), "limited": 0,
                "command_id": None, "status": "ready" if legs else "submitted",
                "dispatched": {key: commands["commands"][key]["filled_quantity"] for key in dispatched},
                "current": {key: str(value) for key, value in positions.items()}, "initial_cash": runtime["account"]["cash"],
                "fund_budget": fund_budget,
                "recovered_from": {"manual_id": run["manual_id"], "completed": completed, "command_id": run.get("command_id")}}

    def preview_plan(self, account_id, *, remaining=False):
        store = self.desk.store
        record = store.database.read(RECORD, DEFAULT)
        data = record["data"]
        snapshot = self.latest_weights(store)
        runtime = self.desk.admission.checked_observation(CONSTRAINTS)
        account = paper_account(runtime)
        if self.desk.store is not store or not account or account != account_id or data["account_id"] not in (None, account):
            raise ValueError("Connect the dedicated Alpaca paper account to preview the rebalance.")
        symbols = [entry["symbol"] for entry in snapshot["entries"]] + data["managed_symbols"]
        if not set(symbols).issubset(runtime["desired_symbols"]):
            with self.desk.maintenance:
                if self.desk.store is not store or paper_account(self.desk.runtime.state()) != account:
                    raise ValueError("The paper account or workspace changed. Open a new preview.")
                self.desk.configure_symbols(additional_symbols=[*runtime["desired_symbols"], *symbols])
            self.desk.refresh_quotes()
            runtime = self.desk.admission.checked_observation(CONSTRAINTS)
            if self.desk.store is not store or paper_account(runtime) != account:
                raise ValueError("The paper account or workspace changed. Open a new preview.")
        session = datetime.now(NEW_YORK).date().isoformat()
        if remaining:
            run = self.remaining_plan(store, runtime, data)
            if snapshot["source_sha256"] != run["source_sha256"] or snapshot["as_of"] != run["as_of"]:
                raise ValueError("The original SPY weights changed. Preview a new plan instead.")
            symbols = data["managed_symbols"]
        else:
            run, symbols = self.plan(store, session, snapshot, runtime, data["managed_symbols"])
        policy = self.check_plan_policy(store, run)
        blockers = self.review_plan_rules(store, runtime, run["legs"], policy)
        token = uuid4().hex if run["legs"] and not blockers else None
        with self.desk.maintenance:
            if self.desk.store is not store:
                raise ValueError("The application workspace changed. Preview again.")
            current_runtime = self.desk.admission.checked_observation(CONSTRAINTS)
            if paper_account(current_runtime) != account:
                raise ValueError("The paper account changed. Preview again.")
            self.check_plan_policy(store, run)
            self.check_fund_binding(store, current_runtime, run)
            self.check_preview_account(store, current_runtime, run, symbols, runtime["account"].get("cash"))
            self.manual_preview = {"token": token, "store": store, "revision": record["revision"], "account": account,
                                   "connection": runtime["connection_session"], "cash": runtime["account"].get("cash"),
                                   "expires": time.monotonic() + PREVIEW_AGE, "run": run, "symbols": symbols}
        first = next(iter(run["legs"]), None)
        buy = next((terms for terms in run["legs"] if terms["side"] == "BUY"), None)
        fund_plan = self.check_fund_binding(store, runtime, run)
        first_buy, _ = self.buy_terms(buy, runtime, policy, fund_plan, store.database.read("commands", COMMANDS)["data"]) if buy else (None, False)
        def order(terms):
            return {key: terms[key] for key in ("symbol", "side", "quantity", "order_type", "limit_price")} if terms else None
        return {"as_of": snapshot["as_of"], "positions": len(symbols), "total": run["total"],
                "quote_at": runtime.get("prices_checked_at"),
                "submit_token": token,
                "already_completed": run.get("recovered_from", {}).get("completed", 0),
                "policy_revision": run["policy_revision"], "target_stock_pct": run["target_stock_pct"], "fund_budget": run["fund_budget"],
                "policy_blockers": blockers,
                "trades": [{key: terms[key] for key in ("symbol", "side", "quantity")} for terms in run["legs"]],
                "first_sell": order(first) if first and first["side"] == "SELL" else None,
                "has_buy": buy is not None, "first_buy": order(first_buy)}

    def submit_preview(self, request):
        preview = self.manual_preview
        token = request.get("submit_token")
        if not token or not preview or token != preview["token"] or time.monotonic() >= preview["expires"]:
            raise ValueError("Preview the SPY rebalance again before submitting.")
        self.order_account(preview["account"])
        day = datetime.now(NEW_YORK).date().isoformat()
        clock = self.desk.data_jobs.read("/v2/clock", data=False, canceled=lambda: self.stopped)["data"]
        market_open = clock.get("is_open")
        if market_open is True:
            session = day
        else:
            try:
                next_open = datetime.fromisoformat(clock["next_open"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("The next regular session could not be confirmed. Preview again.") from error
            if next_open.tzinfo is None or clock.get("is_open") is not False or next_open <= datetime.now(UTC):
                raise ValueError("The next regular session could not be confirmed. Preview again.")
            session = next_open.astimezone(NEW_YORK).date().isoformat()
        with self.desk.maintenance:
            store = self.desk.store
            if (self.stopped or self.manual_preview is not preview or store is not preview["store"]
                    or time.monotonic() >= preview["expires"] or request.get("account_id") != preview["account"]):
                raise ValueError("The account or preview changed. Preview the SPY rebalance again.")
            runtime = self.order_account(preview["account"])
            if runtime["connection_session"] != preview["connection"]:
                raise ValueError("The paper account reconnected. Preview the SPY rebalance again.")
            if runtime.get("market_open") is not market_open or datetime.now(NEW_YORK).date().isoformat() != day:
                raise ValueError("The market session changed. Preview the SPY rebalance again.")
            database = store.database
            record = database.read(RECORD, DEFAULT)
            data = record["data"]
            run = data["run"]
            if run and run["session"] >= day and run["status"] in ACTIVE_RUN:
                raise ValueError("A SPY rebalance is already queued or running.")
            if record["revision"] != preview["revision"]:
                raise ValueError("The SPY rebalance changed. Preview it again before submitting.")
            if preview["run"].get("recovered_from"):
                if session != preview["run"]["session"] or self.remaining_plan(store, runtime, data)["recovered_from"] != preview["run"]["recovered_from"]:
                    raise ValueError("The interrupted run or approved session changed. Preview the remaining trades again.")
            self.check_plan_policy(store, preview["run"])
            self.check_fund_binding(store, runtime, preview["run"])
            self.check_preview_account(store, runtime, preview["run"], preview["symbols"], preview["cash"])
            queued = {**preview["run"], "manual": True, "manual_id": token, "session": session, "status": "queued",
                      "preview_cash": preview["cash"], "message": f"Paper rebalance queued for {session}."}
            database.update(RECORD, record["revision"], lambda saved: saved.update(
                account_id=preview["account"], managed_symbols=preview["symbols"], run=queued), DEFAULT)
            self.manual_preview = None
            self.next_poll = 0.0

    def cancel_queued(self, request):
        def cancel(data):
            run = data["run"]
            if not run or run.get("manual") is not True or run["status"] != "queued":
                raise ValueError("The paper rebalance is no longer queued.")
            run.update(status="blocked", message="Queued paper rebalance canceled.")
        self.desk.store.database.update(RECORD, request.get("rebalance_revision"), cancel, DEFAULT)

    def check_preview_account(self, store, runtime, run, symbols, cash):
        commands = store.database.read("commands", COMMANDS)["data"]
        self.require_no_working_orders(runtime, commands, allowed=run.get("dispatched", {}))
        positions = self.check_positions(runtime, set(symbols))
        if {key: value for key, value in positions.items() if value != 0} != self.expected_positions(runtime, commands, run):
            raise ValueError("Paper holdings changed. Preview the SPY rebalance again.")
        if decimal(cash) is None or decimal(runtime["account"].get("cash")) != decimal(cash):
            raise ValueError("Paper cash changed. Preview the SPY rebalance again.")

    @staticmethod
    def check_plan_policy(store, run):
        policy = store.database.read("investor", INVESTOR)["data"]["policy"]
        if run.get("policy_revision") != policy["revision"]:
            raise ValueError("Trading Rules changed. Preview the SPY rebalance again.")
        return policy

    @staticmethod
    def check_fund_binding(store, runtime, run):
        account_id = paper_account(runtime)
        if (not account_id or run.get("account_id") != account_id or run.get("endpoint") != PAPER
                or run.get("connection_session") != runtime.get("connection_session")
                or run.get("fund_binding") != binding(store.database.read(FUND_RECORD, FUNDS)["data"], account_id)):
            raise ValueError("The paper account, connection, or fund plan changed. Preview the rebalance again.")
        return store.database.read(FUND_RECORD, FUNDS)["data"]["plans"].get(account_key(account_id))

    @staticmethod
    def review_plan_rules(store, runtime, terms, policy):
        rules = {key: rule for key, rule in policy["rules"].items()
                 if rule.get("state") == "enabled" and key != "cash_reserve_pct"}
        if not terms or not rules:
            return []
        commands = store.database.read("commands", COMMANDS)["data"]
        history = store.database.read("market_history", HISTORY)["data"]
        evidence = store.database.read("stock_evidence", EVIDENCE)["data"]
        legs = [{"terms": order, "price_cap": price_evidence(order, runtime)["price"], "fee": None} for order in terms]

        def failed(selected, group):
            result = evaluate_policy(selected[0]["terms"], {**policy, "rules": group}, runtime, commands, history,
                                     evidence, CONSTRAINTS, lambda ref: read_artifact(store.directory, ref),
                                     proposed_legs=selected)
            return [f"{RULES[check['name']]}: {check['reason']}" for check in result["checks"]
                    if check["name"] in group and not check["passed"]]

        portfolio_rules = {key: rule for key, rule in rules.items() if key not in QUOTE_RULES}
        quote_rules = {key: rule for key, rule in rules.items() if key in QUOTE_RULES}
        blockers = failed(legs, portfolio_rules) if portfolio_rules else []
        if quote_rules:
            symbols_by_reason = {}
            for leg in legs:
                for reason in failed([leg], quote_rules):
                    symbols_by_reason.setdefault(reason, []).append(leg["terms"]["symbol"])
            for reason, symbols in symbols_by_reason.items():
                examples = ", ".join(symbols[:5])
                blockers.append(f"{reason} Affected stocks: {len(symbols)} ({examples}{', …' if len(symbols) > 5 else ''}).")
        return blockers

    def tick(self, *, wake=False):
        with self.desk.maintenance:
            if self.stopped or self.desk.browse_only or not wake and time.monotonic() < self.next_poll:
                return
            if self.future is not None and not self.future.done():
                self.wake_pending |= wake
                return
            self.next_poll = time.monotonic() + 5
            store = self.desk.store
            data = store.database.read(RECORD, DEFAULT)["data"]
            if not data["enabled"] and not self.active_manual_run(data):
                return
            runtime = self.desk.runtime.state()
            if runtime.get("market_open") is not True or paper_account(runtime) != data["account_id"]:
                return
            session = datetime.now(NEW_YORK).date()
            run = data["run"]
            if run and (run["session"] > session.isoformat() or
                        run["session"] == session.isoformat() and run["status"] in {"completed", "submitted", "blocked"}):
                return
            self.future = self.desk.data_jobs.executor.submit(self.step, store, session)
            self.future.add_done_callback(self.step_finished)

    def step(self, store, session):
        if session != datetime.now(NEW_YORK).date():
            return
        database = store.database
        record = database.read(RECORD, DEFAULT)
        data = record["data"]
        manual = self.active_manual_run(data)
        if not (data["enabled"] or manual) or self.stopped or self.desk.store is not store:
            return
        day, run = session.isoformat(), data["run"]
        if run and (run["session"] > day or run["session"] == day and run["status"] in {"completed", "submitted", "blocked"}):
            return
        unbound = run and run["status"] in ACTIVE_RUN and not all(key in run for key in ("fund_binding", "account_id", "endpoint", "connection_session", "policy_revision", "fills_completed"))
        expired = run and run["status"] in ACTIVE_RUN and run["session"] < day
        if unbound or expired:
            from .app_database import StoreConflict
            with self.desk.maintenance:
                if self.desk.store is not store:
                    return
                def block_old_run(saved):
                    saved["enabled"] = False
                    saved["run"].update(status="blocked", message="The prior rebalance is unbound or its session ended. Review it and preview again.")
                try:
                    database.update(RECORD, record["revision"], block_old_run, DEFAULT)
                except StoreConflict:
                    pass
            return
        fresh_run = not run or run["session"] != day or run["status"] == "waiting"
        try:
            if manual and run["session"] != day:
                fresh_run = False
                raise ValueError("The approved regular session ended. Preview again before submitting.")
            if manual and run["status"] == "queued":
                self.release_queued(store, record, session)
                return
            if fresh_run:
                self.next_poll = time.monotonic() + 60
                new_run, symbols = self.prepare(store, session, data)
                def save_plan(saved):
                    saved.update(run=new_run, managed_symbols=symbols)
                with self.desk.maintenance:
                    runtime = self.checked_account(data["account_id"], session=day)
                    self.check_fund_binding(store, runtime, new_run)
                    self.check_plan_policy(store, new_run)
                    self.check_preview_account(store, runtime, new_run, symbols, new_run["initial_cash"])
                    database.update(RECORD, record["revision"], save_plan, DEFAULT)
                self.next_poll = time.monotonic() + 5
                return
            self.advance(store, record)
        except (ValueError, PermissionError, ArithmeticError, OSError, KeyError, TypeError) as error:
            from .app_database import StoreConflict
            if isinstance(error, StoreConflict):
                return
            current = database.read(RECORD, DEFAULT)
            if self.desk.store is not store or not (current["data"]["enabled"] or self.active_manual_run(current["data"])):
                return
            if current["revision"] != record["revision"]:
                current_run = current["data"]["run"]
                if (fresh_run or run["status"] == "queued" or not current_run
                        or (current_run["session"], current_run.get("manual_id")) != (run["session"], run.get("manual_id"))):
                    return
            def fail(saved):
                if isinstance(error, ReconciliationPending) and not fresh_run:
                    saved["run"]["message"] = str(error)
                elif fresh_run:
                    saved["run"] = {**(saved["run"] or {}), "session": day, "status": "waiting", "message": str(error)}
                else:
                    saved["run"].update(status="blocked", message=str(error))
            try:
                database.update(RECORD, current["revision"], fail, DEFAULT)
            except StoreConflict:
                pass

    def order_account(self, account_id):
        self.desk.admission.enabled()
        runtime = self.desk.admission.checked_observation(CONSTRAINTS)
        if not account_id or paper_account(runtime) != account_id:
            raise ValueError("Connect the dedicated Alpaca paper account.")
        return runtime

    def checked_account(self, account_id, *, session=None, close_at=None):
        runtime = self.order_account(account_id)
        if runtime.get("market_open") is not True:
            raise ValueError("The dedicated paper account and an open regular session are required.")
        now = datetime.now(NEW_YORK)
        if (session is not None and session != now.date().isoformat()
                or close_at is not None and now >= datetime.fromisoformat(close_at)):
            raise ValueError("The approved regular session ended. Preview again before submitting.")
        return runtime

    def session_calendar(self, session):
        query = urlencode({"start": (session - timedelta(days=14)).isoformat(), "end": session.isoformat()})
        calendar = self.desk.data_jobs.read("/v2/calendar?" + query, data=False, canceled=lambda: self.stopped)["data"]
        day = session.isoformat()
        dates = {item["date"]: item for item in calendar}
        prior = max((value for value in dates if value < day), default=None)
        if day not in dates or not prior:
            raise ValueError("The Alpaca calendar does not confirm this session and the previous session.")
        return prior, dates[day]

    def release_queued(self, store, record, session):
        data, run = record["data"], record["data"]["run"]
        prior, calendar = self.session_calendar(session)
        close_at = datetime.fromisoformat(f"{run['session']}T{calendar['close']}").replace(tzinfo=NEW_YORK).isoformat()
        snapshot = self.latest_weights(store)
        if snapshot["as_of"] != prior or snapshot["source_sha256"] != run["source_sha256"]:
            raise ValueError("The approved SPY weights are no longer current. Preview and submit again.")
        runtime = self.checked_account(data["account_id"], session=run["session"], close_at=close_at)
        policy = self.check_plan_policy(store, run)
        blockers = self.review_plan_rules(store, runtime, run["legs"], policy)
        if blockers:
            raise ValueError(blockers[0])
        with self.desk.maintenance:
            if self.stopped or self.desk.store is not store:
                return
            runtime = self.checked_account(data["account_id"], session=run["session"], close_at=close_at)
            self.check_plan_policy(store, run)
            self.check_fund_binding(store, runtime, run)
            self.check_preview_account(store, runtime, run, data["managed_symbols"], run["preview_cash"])
            store.database.update(RECORD, record["revision"], lambda saved: saved["run"].update(
                status="ready", close_at=close_at, message="Reviewed paper rebalance ready to send."), DEFAULT)

    def prepare(self, store, session, data):
        self.checked_account(data["account_id"])
        prior, _ = self.session_calendar(session)
        day = session.isoformat()
        snapshot = self.latest_weights(store)
        if snapshot["as_of"] != prior:
            raise ValueError(f"Waiting for State Street SPY holdings dated {prior}.")
        runtime = self.checked_account(data["account_id"])
        symbols = [entry["symbol"] for entry in snapshot["entries"]]
        self.ensure_symbols(store, data["account_id"], runtime, [*symbols, *data["managed_symbols"]])
        run, symbols = self.plan(store, day, snapshot, runtime, data["managed_symbols"])
        blockers = self.review_plan_rules(store, runtime, run["legs"], self.check_plan_policy(store, run))
        if blockers:
            raise ValueError(blockers[0])
        return run, symbols

    def plan(self, store, day, snapshot, runtime, managed_symbols):
        records = store.database.read("commands", COMMANDS)["data"]
        prior = store.database.read(RECORD, DEFAULT)["data"]["run"] or {}
        tracked = set(prior.get("dispatched", {})) | ({prior["command_id"]} if prior.get("command_id") else set())
        dispatched = {key: self.checked_submitted(runtime, records["commands"][key]) for key in tracked
                      if records["commands"][key]["state"] in ACTIVE or records["commands"][key].get("native_pending_commitment")}
        self.require_no_working_orders(runtime, records, allowed=dispatched)
        weights = {entry["symbol"]: Decimal(entry["weight"]) for entry in snapshot["entries"] if Decimal(entry["weight"]) > 0}
        positions = self.check_positions(runtime, set(weights) | set(managed_symbols))
        symbols = sorted(set(weights) | set(positions))
        supported = instruments(runtime, symbols)
        missing = [symbol for symbol in symbols if not supported[symbol]["supported"]]
        if missing:
            raise ValueError(f"Waiting for {len(missing)} supported Alpaca assets, including " + ", ".join(missing[:8]) + ".")
        as_of = snapshot["as_of"]
        reason = f"Daily SPY paper rebalance using State Street holdings dated {as_of} (SHA-256 {snapshot['source_sha256']})."
        investor = store.database.read("investor", INVESTOR)["data"]
        policy = investor["policy"]
        fund_data = store.database.read(FUND_RECORD, FUNDS)["data"]
        account_id = paper_account(runtime)
        if not account_id:
            raise ValueError("A reconciled USD paper account is required.")
        fund_binding = binding(fund_data, account_id)
        fund_plan = fund_data["plans"].get(account_key(account_id))
        fund_budget = budget(fund_plan, runtime, policy)
        fund_budget["spendable_cash_usd"] = str(self.spendable_cash(runtime, policy, fund_plan, records))
        equity = Decimal(fund_budget["equity_usd"])
        invested = min(Decimal(fund_budget["investable_sleeve_usd"]) / equity * 100,
                       rule_limit(policy, "max_gross_exposure_pct", 100))
        position_limit = rule_limit(policy, "max_position_pct", 100)
        target_weights = {symbol: min(weight * invested, position_limit) for symbol, weight in weights.items()}
        targets = [{"symbol": symbol, "mode": "weight", "value": str(weight), "order_type": "MARKET"}
                   for symbol, weight in target_weights.items()]
        targets.extend({"symbol": symbol, "mode": "quantity", "value": "0", "order_type": "MARKET"}
                       for symbol in sorted(positions.keys() - weights.keys()))
        basket = preview(investor, {"targets": targets, "reason": reason}, runtime, (), commands=records)
        missing = [row["symbol"] for row in basket["targets"] if row["desired_quantity"] is None or row["valuation_price"] is None]
        if missing:
            raise ValueError("Waiting for prices to size: " + ", ".join(missing))
        legs = [leg["terms"] for leg in basket["legs"] if leg["terms"]["side"] == "SELL"
                or (decimal(leg["impact"]["estimated_principal"]) or Decimal(0)) >= 1]
        pending_symbols = {records["commands"][key]["symbol"] for key in dispatched}
        legs = [terms for terms in legs if terms["symbol"] not in pending_symbols]
        legs.sort(key=lambda terms: terms["side"] != "SELL")
        return {"session": day, "as_of": as_of, "status": "ready" if legs else "submitted" if dispatched else "completed",
                "message": "Waiting for the first order." if legs else "No new orders needed; existing orders remain tracked." if dispatched else "No orders needed.",
                "legs": legs, "completed": 0, "fills_completed": 0, "total": len(legs), "limited": 0, "command_id": None,
                "dispatched": {key: str(value) for key, value in dispatched.items()},
                "source_sha256": snapshot["source_sha256"],
                "policy_revision": policy["revision"], "target_stock_pct": str(sum(target_weights.values(), Decimal(0))),
                "account_id": account_id, "endpoint": PAPER, "connection_session": runtime["connection_session"],
                "fund_binding": fund_binding, "fund_budget": fund_budget, "initial_cash": runtime["account"].get("cash"),
                "current": {symbol: str(quantity) for symbol, quantity in positions.items()}}, symbols

    def ensure_symbols(self, store, account_id, runtime, symbols):
        if set(symbols).issubset(runtime["desired_symbols"]):
            return
        with self.desk.maintenance:
            data = store.database.read(RECORD, DEFAULT)["data"]
            if self.desk.store is not store or not (data["enabled"] or self.active_manual_run(data)):
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
    def require_no_working_orders(runtime, commands, *, allowed=()):
        commitments, known = working_commitments(runtime, commands)
        if (not known or any(not item["command_ids"] or not item["command_ids"].issubset(allowed) for item in commitments)
                or commands.get("new_orders_blocked")
                or any(item["state"] in ACTIVE and key not in allowed for key, item in commands["commands"].items())):
            raise ValueError("Unrelated or unresolved orders or an account block must clear before SPY can rebalance.")
        if commands.get("recovery_required"):
            raise ReconciliationPending("Waiting for current account and order reconciliation; no new order has been sent.")

    @staticmethod
    def checked_submitted(runtime, command):
        filled = decimal(command.get("filled_quantity"))
        quantity = decimal(command.get("terms", {}).get("quantity"))
        deliveries = command.get("native_deliveries", {})
        native = [item for item in runtime.get("native_deliveries", []) if item.get("command_id") == command.get("id")]
        if (command.get("state") not in {"accepted", "partially_filled", "filled"}
                or command.get("account_id") != runtime["account"]["id"]
                or command.get("pending_action") or not command.get("broker_order_ids")
                or quantity is None or quantity <= 0 or filled is None or not 0 <= filled <= quantity
                or command["state"] == "filled" and filled != quantity
                or any(item.get("status") == "conflict" for item in native)):
            raise ValueError("An existing SPY order lacks a known broker outcome or has conflicting native proof. Reconcile orders first.")
        fills = [item for item in runtime.get("fills", []) if item.get("order_id") in command["broker_order_ids"]]
        if (command.get("native_pending_commitment") or filled > 0 and not command.get("fill_ids")
                or sum((Decimal(item["qty"]) for item in fills), Decimal(0)) != filled
                or any(item.get("native_application") != "proven_in_current_process" for item in fills)
                or {execution_id(item["id"]) for item in fills} != {execution_id(value) for value in command["fill_ids"]}
                or not deliveries
                or {item.get("event_id") for item in native} != set(deliveries)
                or any(item.get("confirmed_current_process") is not True
                    or item.get("native_epoch") != runtime["native_epoch"] for item in native)):
            raise ReconciliationPending("Waiting for current native confirmation of an existing SPY order.")
        if command["state"] == "filled":
            events = [entry for entry in command.get("timeline", []) if entry.get("state") == "filled" and entry.get("at")]
            if not events or not isinstance(runtime.get("account_observation_started_at"), str):
                raise ValueError("The post-fill account observation time is unavailable.")
            if instant(runtime["account_observation_started_at"]) <= instant(events[-1]["at"]):
                raise ReconciliationPending("Waiting for a fresh post-fill account observation.")
        return filled

    @classmethod
    def expected_positions(cls, runtime, commands, run):
        expected = {key: Decimal(value) for key, value in run["current"].items()}
        for key, baseline in run.get("dispatched", {}).items():
            command = commands["commands"][key]
            delta = cls.checked_submitted(runtime, command) - Decimal(baseline)
            if delta < 0:
                raise ValueError("An existing SPY order's proven filled quantity regressed.")
            symbol = command["symbol"]
            expected[symbol] = expected.get(symbol, Decimal(0)) + delta * (1 if command["side"] == "BUY" else -1)
        return {key: value for key, value in expected.items() if value != 0}

    @staticmethod
    def spendable_cash(runtime, policy, plan, commands):
        commitments, known = working_commitments(runtime, commands)
        if not known:
            raise ValueError("Current pending cash and share commitments are unavailable.")
        return max(Decimal(0), Decimal(budget(plan, runtime, policy)["spendable_cash_usd"])
                   - sum((item["cash"] for item in commitments), Decimal(0)))

    @staticmethod
    def buy_terms(terms, runtime, policy, plan, commands):
        symbol = terms["symbol"]
        price = price_evidence(terms, runtime)["price"]
        cash = decimal(runtime["account"].get("cash"))
        if price is None or price <= 0 or cash is None or cash < 0:
            raise ValueError(f"{symbol}: The buy requires a current price and enough observed cash.")
        spendable = SpyRebalance.spendable_cash(runtime, policy, plan, commands)
        limit = price.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        try:
            fractional_asset(runtime, symbol)
            increment = Decimal("0.000000001")
        except ValueError:
            increment = Decimal(1)
        planned = Decimal(terms["quantity"])
        quantity = min(planned, spendable / limit).quantize(increment, rounding=ROUND_FLOOR)
        if quantity * limit < 1:
            return None, True
        return {**terms, "order_type": "LIMIT", "limit_price": str(limit),
                "quantity": format(quantity.normalize(), "f")}, quantity < planned

    def advance(self, store, record):
        database = store.database
        data, run = record["data"], record["data"]["run"]
        with self.desk.maintenance:
            if self.stopped or self.desk.store is not store:
                return
            if paper_account(self.desk.runtime.state()) != data["account_id"]:
                return
            saved_commands = database.read("commands", COMMANDS)["data"]["commands"]
            tracked = set(run.get("dispatched", {})) | ({run["command_id"]} if run.get("command_id") else set())
            filled = {key for key in tracked if saved_commands.get(key, {}).get("state") == "filled"}
            refresh = not run["command_id"] and run["status"] == "ready"
            post_fill = bool(filled - self.post_fill_refreshed)
        if refresh or post_fill:
            # Native replies need the observer's maintenance lock; never wait for them while holding it.
            try:
                self.desk.runtime.request("refresh", post_fill=post_fill)
            except ValueError:
                with self.desk.maintenance:
                    self.wake_pending = False
                    self.next_poll = time.monotonic() + 5
                return
        def update(**changes):
            def change(saved):
                saved["run"].update(changes)
            return database.update(RECORD, record["revision"], change, DEFAULT)

        with self.desk.maintenance:
            current = database.read(RECORD, DEFAULT)
            if self.stopped or self.desk.store is not store or current["revision"] != record["revision"]:
                return
            data, run = current["data"], current["data"]["run"]
            if not data["enabled"] and not self.active_manual_run(data):
                return
            if post_fill:
                self.post_fill_refreshed.update(filled)
            runtime = self.desk.runtime.state()
            policy = self.check_plan_policy(store, run)
            plan = self.check_fund_binding(store, runtime, run)
            commands = database.read("commands", COMMANDS)["data"]
            dispatched = dict(run.get("dispatched", {}))
            tracked = set(dispatched) | ({run["command_id"]} if run.get("command_id") else set())
            if runtime.get("local_record_error") or runtime.get("native_import_gap"):
                raise ValueError(runtime.get("local_record_error") or runtime["native_import_gap"])
            if (runtime.get("account", {}).get("trading_blocked") is True
                    or commands.get("new_orders_blocked")
                    or any(item.get("status") == "conflict" for item in runtime.get("native_deliveries", []))):
                raise ValueError("The paper account or native command evidence is blocked. Review before continuing.")
            for key in tracked:
                state = commands["commands"].get(key, {}).get("state")
                if state not in {"dispatch_intent", "submitting", "accepted", "partially_filled", "filled"}:
                    raise ValueError("An existing SPY order has an unresolved or unsuccessful broker result. Review before continuing.")
            if runtime.get("reconciliation", {}).get("status") != "reconciled":
                raise ReconciliationPending("Waiting for current broker/native reconciliation; existing orders stay reserved.")
            runtime = self.checked_account(data["account_id"], session=run["session"], close_at=run.get("close_at"))
            if run["command_id"]:
                command = commands["commands"][run["command_id"]]
                if command["state"] in {"dispatch_intent", "submitting"}:
                    raise ReconciliationPending("Waiting for the existing order's broker acknowledgment; it will not be resubmitted.")
                self.checked_submitted(runtime, command)
                leg = run["legs"][run["completed"]]
                if (any(command.get(key) != leg[key] for key in ("symbol", "side", "instrument_id"))
                        or Decimal(command["terms"]["quantity"]) > Decimal(leg["quantity"])
                        or leg["side"] == "SELL" and Decimal(command["terms"]["quantity"]) != Decimal(leg["quantity"])):
                    raise ValueError("The attached SPY command differs from its reviewed leg.")
                completed = run["completed"] + 1
                done = completed == run["total"]
                dispatched[run["command_id"]] = "0"
                expected = self.expected_positions(runtime, commands, {**run, "dispatched": dispatched})
                positions = {key: value for key, value in self.check_positions(runtime, set(data["managed_symbols"])).items() if value != 0}
                if positions != expected:
                    raise ValueError("Current holdings do not match the reviewed SPY run and its proven executions.")
                self.require_no_working_orders(runtime, commands, allowed=dispatched)
                update(status="submitted" if done else "ready", completed=completed, command_id=None, dispatched=dispatched,
                       message="All reviewed orders processed; accepted unfilled orders remain reserved." if done else f"{command['symbol']} accepted; preparing the next stock without waiting for its fill.")
                self.wake_pending = not done
                return
            if run["status"] == "dispatching":
                raise ValueError("An interrupted SPY order needs review before another order can be sent.")
            self.require_no_working_orders(runtime, commands, allowed=dispatched)
            if not set(data["managed_symbols"]).issubset(runtime["desired_symbols"]):
                self.ensure_symbols(store, data["account_id"], runtime, data["managed_symbols"])
                return
            positions = {key: value for key, value in self.check_positions(runtime, set(data["managed_symbols"])).items() if value != 0}
            expected = self.expected_positions(runtime, commands, run)
            if positions != expected:
                raise ValueError("Paper holdings changed after the daily plan was made.")
            own_fills = any(decimal(commands["commands"][key].get("filled_quantity")) > Decimal(baseline) for key, baseline in dispatched.items())
            if not own_fills and run["fills_completed"] == 0 and (decimal(run["initial_cash"]) is None
                    or decimal(runtime["account"].get("cash")) != decimal(run["initial_cash"])):
                raise ValueError("Paper cash changed after the daily plan was made.")
            terms = dict(run["legs"][run["completed"]])
            symbol, limited = terms["symbol"], run["limited"]
            if any(item["symbol"] == symbol and item["state"] in ACTIVE for item in commands["commands"].values()):
                raise ValueError(f"{symbol}: An existing working order prevents a duplicate SPY order.")
            if terms["side"] == "BUY":
                terms, resized = self.buy_terms(terms, runtime, policy, plan, commands)
                limited += resized
                if terms is None:
                    completed = run["completed"] + 1
                    update(completed=completed, limited=limited,
                           status="submitted" if completed == run["total"] else "ready",
                           message=f"{symbol}: Buy skipped because observed cash allows less than $1.")
                    self.wake_pending = completed < run["total"]
                    return
            claimed = update(status="dispatching", message=f"Preparing {symbol}.")
            try:
                command_id = self.admit(terms, runtime, data["account_id"], manual=run.get("manual") is True)
            except ReconciliationPending:
                database.update(RECORD, claimed["revision"], lambda saved: saved["run"].update(status="ready"), DEFAULT)
                raise
            attached = database.update(RECORD, claimed["revision"], lambda saved: saved["run"].update(
                status="waiting_acceptance", command_id=command_id, limited=limited, message=f"Waiting for {symbol} broker acknowledgment, not its fill."), DEFAULT)
            try:
                latest = self.checked_account(data["account_id"], session=run["session"], close_at=run.get("close_at"))
                self.check_plan_policy(store, run)
                current_plan = self.check_fund_binding(store, latest, run)
                latest_commands = database.read("commands", COMMANDS)["data"]
                admitted = latest_commands["commands"].get(command_id) or {}
                if (admitted.get("state") != "dispatch_intent"
                        or admitted.get("transport_attempt") != {"version": 1, "state": "not_started"}):
                    raise ValueError("The admitted SPY order changed before dispatch. Review the rebalance.")
                other_commands = {**latest_commands, "commands": {key: value for key, value in latest_commands["commands"].items() if key != command_id}}
                self.require_no_working_orders(latest, other_commands, allowed=dispatched)
                if terms["side"] == "BUY":
                    commitment = decimal(admitted.get("cash_commitment"))
                    available = self.spendable_cash(latest, policy, current_plan, other_commands)
                    if commitment is None or commitment < 0 or commitment > available:
                        raise ValueError("The admitted buy commitment exceeds cash available above the reserve.")
                if (decimal(latest["account"].get("cash")) != decimal(runtime["account"].get("cash"))
                        or latest.get("orders") != runtime.get("orders")
                        or self.check_positions(latest, set(data["managed_symbols"])) != self.check_positions(runtime, set(data["managed_symbols"]))):
                    observed = {key: value for key, value in self.check_positions(latest, set(data["managed_symbols"])).items() if value != 0}
                    if observed != self.expected_positions(latest, other_commands, run):
                        raise ValueError("Paper holdings changed outside the reviewed SPY executions.")
                    raise ReconciliationPending("The account observation changed before dispatch; rechecking the unsent leg.")
            except (ValueError, PermissionError) as error:
                self.desk.admission.resolve_never_dispatched(command_id)
                if isinstance(error, ReconciliationPending):
                    database.update(RECORD, attached["revision"], lambda saved: saved["run"].update(
                        status="ready", command_id=None, limited=run["limited"]), DEFAULT)
                raise
            self.desk.runtime.request("dispatch", command_id=command_id, action="submit")
            self.wake_pending = True

    def admit(self, terms, runtime, account_id, *, manual=False):
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
        authority = "manual-paper-spy" if manual else "standing-paper-spy"
        approved = admission.approve(proposal["id"], actor=f"{authority}:{account_id}", reason=terms["rationale"],
            constraints=CONSTRAINTS, proposal_revision=proposal["revision"], policy_revision=proposal["policy_revision"],
            evaluation_binding_sha256=proposal["risk_evaluation"]["binding_sha256"], expected=expected)
        approval = next(item for item in approved["commands"]["data"]["approvals"].values() if item["proposal_id"] == proposal["id"])
        context = approval.get("connection_context") or {}
        if (context.get("account_id"), context.get("endpoint"), context.get("mode")) != (account_id, PAPER, "paper"):
            raise ValueError("Approval does not match the dedicated Alpaca paper account.")
        self.checked_account(account_id)
        return admission.submit_approved(approval["id"], expected={name: approved[name]["revision"] for name in ("investor", "commands")})
