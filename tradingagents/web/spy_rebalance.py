"""Daily SPY rebalancing through the existing paper order admission path."""

import copy
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
ACTIVE_RUN = {"queued", "ready", "dispatching", "waiting_fill", "waiting_acceptance", "batch_dispatching"}
PREVIEW_AGE = 300
QUOTE_RULES = {"max_spread_bps", "min_quote_size", "session_freshness"}


class StockDeferred(ValueError):
    pass


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
                    command.get("id"), command.get("state"), runtime.get("account_observation_started_at"),
                    runtime.get("reconciliation", {}).get("status"), runtime.get("native_contract", {}).get("observation_in_progress"))
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
        if run and run.get("batch_id"):
            state = self.desk.store.database.read("commands", COMMANDS)["data"]
            batch = state.get("spy_batches", {}).get(run["batch_id"])
            if batch:
                counts = self.batch_counts(state, batch)
                run = {**run, "batch_counts": counts}
                if batch["state"] == "blocked":
                    run.update(status="blocked", message=batch.get("reason") or "Batch transport outcome is unresolved; no replay.")
                deferred = list(run.get("deferred", []))
                for key in batch["members"]:
                    command = state["commands"][key]
                    residual = Decimal(command["terms"]["quantity"]) - Decimal(command["filled_quantity"])
                    if (command["state"] in {"not_sent", "rejected", "canceled", "expired"} and residual > 0
                            and not any(item["terms"]["symbol"] == command["symbol"] for item in deferred)):
                        deferred.append({"terms": {**command["terms"], "quantity": str(residual)},
                                         "reasons": [command.get("deferred_reason") or f"Recorded broker outcome: {command['state']}; not filled."]})
                run["deferred"] = deferred
        return {"revision": record["revision"], "enabled": data["enabled"], "account_id": data["account_id"],
                "eligible_account_id": paper_account(runtime),
                "in_progress": bool(run and run["session"] >= datetime.now(NEW_YORK).date().isoformat()
                                    and run["status"] in ACTIVE_RUN),
                "run": {**{key: run.get(key) for key in ("session", "as_of", "status", "message", "completed", "total", "limited", "stopped_at")},
                        "deferred": run.get("deferred", []), "batch_counts": run.get("batch_counts")} if run else None}

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
        if (not run or run.get("status") not in {"blocked", "submitted"} or run.get("session") != day
                or not run.get("manual_id") or not run.get("close_at") or not (run.get("legs") or run.get("deferred"))
                or run.get("total") != len(run["legs"]) or not 0 <= run.get("completed", -1) <= run["total"]
                or run["completed"] == run["total"] and not run.get("deferred") and not run.get("batch_id")):
            raise ValueError("A same-session interrupted reviewed rebalance is required. Preview a new plan instead.")
        if (paper_account(runtime) != data["account_id"] or runtime.get("market_open") is not True
                or datetime.now(NEW_YORK) >= datetime.fromisoformat(run["close_at"])):
            raise ValueError("The original paper account and open approved session are required.")
        rebound = {**run, "connection_session": runtime["connection_session"]}
        policy = self.check_plan_policy(store, rebound)
        plan = self.check_fund_binding(store, runtime, rebound)
        commands = store.database.read("commands", COMMANDS)["data"]
        if run.get("batch_id"):
            return self.remaining_batch(store, runtime, data, commands, rebound, policy, plan)
        dispatched = dict(run.get("dispatched", {}))
        expected = self.expected_positions(runtime, commands, run)
        completed = run["completed"]
        if run.get("command_id"):
            command = commands["commands"].get(run["command_id"], {})
            leg = run["legs"][completed]
            quantity = decimal(command.get("terms", {}).get("quantity"))
            if (command.get("account_id") != run["account_id"]
                    or any(command.get(key) != leg[key] for key in ("symbol", "side", "instrument_id"))
                    or quantity > Decimal(leg["quantity"]) or leg["side"] == "SELL" and quantity != Decimal(leg["quantity"])):
                raise ValueError("The interrupted leg differs from its original reviewed order. Reconcile orders first.")
            attempt = command.get("transport_attempt", {})
            never_sent = (command.get("state") == "not_sent" and attempt.get("version") == 1
                and attempt.get("state") == "not_sent" and attempt.get("resolved_at")
                and not any(command.get(key) for key in ("broker_order_ids", "fill_ids", "native_deliveries", "native_pending_commitment", "pending_action"))
                and decimal(command.get("filled_quantity")) == 0 and decimal(command.get("cash_commitment")) == 0
                and decimal(command.get("remaining_quantity")) == 0)
            if not never_sent:
                filled = self.checked_submitted(runtime, command)
                symbol = leg["symbol"]
                expected[symbol] = expected.get(symbol, Decimal(0)) + filled * (1 if leg["side"] == "BUY" else -1)
                expected = {key: value for key, value in expected.items() if value != 0}
                dispatched[run["command_id"]] = "0"
                completed += 1
        if (not dispatched and completed == run["completed"] and run.get("fills_completed") == 0
                and decimal(runtime["account"].get("cash")) != decimal(run.get("initial_cash"))):
            raise ValueError("Paper cash changed after the original plan. Preview a new plan instead.")
        self.require_no_working_orders(runtime, commands, allowed=dispatched)
        positions = {key: value for key, value in self.check_positions(runtime, set(data["managed_symbols"])).items() if value != 0}
        if positions != expected:
            raise ValueError("Current holdings do not match the original run and its proven fills. Reconcile before continuing.")
        legs = run["legs"][completed:] + [item["terms"] for item in run.get("deferred", [])]
        fund_budget = budget(plan, runtime, policy)
        fund_budget["spendable_cash_usd"] = str(self.spendable_cash(runtime, policy, plan, commands))
        return {**rebound, "legs": legs, "completed": 0, "fills_completed": 0, "total": len(legs), "limited": 0,
                "command_id": None, "status": "ready" if legs else "submitted", "deferred": [],
                "dispatched": {key: commands["commands"][key]["filled_quantity"] for key in dispatched},
                "current": {key: str(value) for key, value in positions.items()}, "initial_cash": runtime["account"]["cash"],
                "fund_budget": fund_budget,
                "recovered_from": {"manual_id": run["manual_id"], "completed": completed, "command_id": run.get("command_id")}}

    def remaining_batch(self, store, runtime, data, commands, rebound, policy, plan):
        run = data["run"]
        batch = commands.get("spy_batches", {}).get(run["batch_id"])
        if not batch:
            raise ValueError("The original reserved batch is missing; reconcile commands before a new preview")
        tracked = {**batch["baseline"]["tracked"], **{key: "0" for key in batch["members"]}}
        legs, working = [], {}
        for key, baseline in tracked.items():
            command = commands["commands"][key]
            if command["state"] == "not_sent":
                attempt = command.get("transport_attempt") or {}
                if (attempt.get("version") != 1 or attempt.get("state") != "not_sent" or not attempt.get("resolved_at")
                        or any(command.get(name) for name in ("broker_order_ids", "fill_ids", "native_deliveries", "native_pending_commitment"))
                        or decimal(command["filled_quantity"]) != 0):
                    raise ValueError("A batch leg lacks authoritative no-send proof; it cannot be retried")
                if key in batch["members"]:
                    legs.append(copy.deepcopy(batch["members"][key]["terms"]))
                continue
            filled = self.checked_submitted(runtime, command, terminal=True)
            if command["state"] in ACTIVE:
                working[key] = str(filled)
            elif key in batch["members"] and filled < Decimal(command["terms"]["quantity"]):
                legs.append({**command["terms"], "quantity": str(Decimal(command["terms"]["quantity"]) - filled)})
        expected = self.expected_positions(runtime, commands,
            {"current": batch["baseline"]["positions"], "dispatched": tracked}, terminal=True)
        positions = {key: value for key, value in self.check_positions(runtime, set(data["managed_symbols"])).items() if value != 0}
        if positions != expected:
            raise ValueError("Current holdings differ from exact batch executions")
        self.require_no_working_orders(runtime, commands, allowed=working)
        for item in run.get("deferred", []):
            if not any(leg["symbol"] == item["terms"]["symbol"] for leg in legs) and not any(
                    commands["commands"][key]["symbol"] == item["terms"]["symbol"] for key in working):
                legs.append(copy.deepcopy(item["terms"]))
        fresh = {key: value for key, value in rebound.items()
                 if key not in {"batch_id", "batch_offset", "batch_counts", "dispatch_requested"}}
        fund_budget = budget(plan, runtime, policy)
        fund_budget["spendable_cash_usd"] = str(self.spendable_cash(runtime, policy, plan, commands))
        return {**fresh, "legs": legs, "completed": 0, "fills_completed": 0, "total": len(legs), "limited": 0,
            "command_id": None, "status": "ready" if legs else "submitted", "deferred": [], "dispatched": working,
            "current": {key: str(value) for key, value in positions.items()}, "initial_cash": runtime["account"]["cash"],
            "fund_budget": fund_budget, "recovered_from": {"manual_id": run["manual_id"], "batch_id": batch["id"]}}

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
        runtime = {**runtime, "_spy_isolated_commands": run.get("quarantined", {})}
        policy = self.check_plan_policy(store, run)
        run = self.freeze_buys(store, runtime, run, policy)
        blockers, deferred = self.review_plan_rules(store, runtime, run["legs"], policy)
        run.update(self.defer_legs(run, deferred))
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
                "quarantined_stocks": [item["symbol"] for item in run.get("quarantined", {}).values()],
                "already_completed": run.get("recovered_from", {}).get("completed", 0),
                "policy_revision": run["policy_revision"], "target_stock_pct": run["target_stock_pct"], "fund_budget": run["fund_budget"],
                "policy_blockers": blockers,
                "deferred": run["deferred"],
                "trades": [{key: terms.get(key) for key in ("symbol", "side", "quantity", "order_type", "limit_price")} for terms in run["legs"]],
                "first_sell": order(first) if first and first["side"] == "SELL" else None,
                "has_buy": buy is not None, "first_buy": order(first_buy)}

    def submit_preview(self, request):
        preview = self.manual_preview
        token = request.get("submit_token")
        if not token or not preview or token != preview["token"] or time.monotonic() >= preview["expires"]:
            raise ValueError("Preview the SPY rebalance again before submitting.")
        self.desk.admission.enabled()
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
        deadline = min(time.monotonic() + 45, preview["expires"])
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ReconciliationPending("Current broker/native observation is still being completed. No SPY rebalance was queued.")
            # The reader and record observer must be free to finish the current generation.
            self.desk.runtime.wait_for_reconciliation(preview["connection"], timeout=remaining)
            with self.desk.maintenance, self.desk.runtime.lock:
                store = self.desk.store
                if (self.stopped or self.manual_preview is not preview or store is not preview["store"]
                        or time.monotonic() >= preview["expires"] or request.get("account_id") != preview["account"]):
                    raise ValueError("The account or preview changed. Preview the SPY rebalance again.")
                current = self.desk.runtime.state()
                if current.get("connection_session") != preview["connection"]:
                    raise ValueError("The paper account reconnected. Preview the SPY rebalance again.")
                if (not current.get("local_record_error") and not current.get("native_import_gap")
                        and current.get("status") == "connected"
                        and (current.get("reconciliation", {}).get("status") != "reconciled"
                             or current.get("native_contract", {}).get("observation_in_progress") is True)):
                    continue
                runtime = self.order_account(preview["account"])
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
                self.desk.admission.reconcile()
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
                return

    def cancel_queued(self, request):
        from .admission import stamp
        with self.desk.maintenance:
            def cancel(records):
                data = records[RECORD]
                run = data["run"]
                if not run or run["status"] not in ACTIVE_RUN | {"blocked"} or run.get("stopped_at"):
                    raise ValueError("The paper rebalance is no longer queued or active.")
                state = records["commands"]
                batch = state.get("spy_batches", {}).get(run.get("batch_id"))
                if batch:
                    batch.update(state="blocked", reason="User stopped unsent rebalance orders.")
                    for key in batch["members"]:
                        command = state["commands"][key]
                        if (command.get("transport_attempt") != {"version": 1, "state": "not_started"}
                                or any(command.get(field) for field in (
                                    "broker_order_ids", "fill_ids", "native_deliveries", "native_pending_commitment", "pending_action"))):
                            continue
                        now = stamp()
                        command["transport_attempt"].update(state="not_sent", resolved_at=now)
                        command.update(state="not_sent", cash_commitment="0", remaining_quantity="0")
                        state["revocations"].setdefault(command["approval_id"], {"at": now, "reason": "User stopped the unsent rebalance order."})
                        command["timeline"].append({"at": now, "state": "not_sent",
                            "reason": "User stopped the batch before the versioned transport boundary started."})
                data["enabled"] = False
                run.update(status="blocked", stopped_at=stamp(),
                           message="Unsent rebalance trades stopped. Sent or uncertain orders were not canceled; review their exact broker outcomes in Orders.")
            self.desk.admission.transaction(cancel, expected={RECORD: request.get("rebalance_revision")}, extra={RECORD: DEFAULT})
            self.manual_preview = None

    def check_preview_account(self, store, runtime, run, symbols, cash):
        runtime = {**runtime, "_spy_isolated_commands": run.get("quarantined", {})}
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
        if not terms:
            return [], []
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
        blockers, deferred, eligible = [], [], []
        supported = instruments(runtime, [order["symbol"] for order in terms])
        for leg in legs:
            order = leg["terms"]
            reasons = []
            if not supported[order["symbol"]]["supported"]:
                reasons.append(supported[order["symbol"]]["limitation"] or "Supported stock instrument evidence is unavailable.")
            selected = price_evidence({**order, "order_type": "MARKET"}, runtime)
            event = decimal(selected["ts_event"])
            age = Decimal(str(time.time())) - event / 1000000000 if event is not None else None
            if selected["price"] is None or runtime.get("market_open") is True and (
                    age is None or not 0 <= age <= Decimal(CONSTRAINTS["quote_max_age_seconds"])):
                reasons.append("Current dated stock price evidence is required; quote age limit is " + CONSTRAINTS["quote_max_age_seconds"] + " seconds.")
            quote_failures = failed([leg], quote_rules) if quote_rules else []
            if runtime.get("market_open") is not True:
                blockers.extend(quote_failures)
            else:
                reasons.extend(quote_failures)
            if reasons:
                deferred.append({"terms": order, "reasons": reasons})
            else:
                eligible.append(leg)
        if eligible and portfolio_rules:
            blockers.extend(failed(eligible, portfolio_rules))
        return list(dict.fromkeys(blockers)), deferred

    @staticmethod
    def defer_legs(run, deferred):
        symbols = {item["terms"]["symbol"] for item in deferred}
        completed = run["completed"]
        legs = run["legs"][:completed] + [order for order in run["legs"][completed:] if order["symbol"] not in symbols]
        return {"legs": legs, "total": len(legs), "deferred": run.get("deferred", []) + deferred}

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
        runtime = {**runtime, "_spy_isolated_commands": run.get("quarantined", {})}
        policy = self.check_plan_policy(store, run)
        blockers, deferred = self.review_plan_rules(store, runtime, run["legs"], policy)
        if blockers:
            raise ValueError(blockers[0])
        changes = self.defer_legs(run, deferred)
        with self.desk.maintenance:
            if self.stopped or self.desk.store is not store:
                return
            runtime = self.checked_account(data["account_id"], session=run["session"], close_at=close_at)
            self.check_plan_policy(store, run)
            self.check_fund_binding(store, runtime, run)
            self.check_preview_account(store, runtime, run, data["managed_symbols"], run["preview_cash"])
            store.database.update(RECORD, record["revision"], lambda saved: saved["run"].update(
                **changes, status="ready" if changes["total"] else "submitted", close_at=close_at,
                message="Reviewed eligible paper orders ready to send; deferred stocks require another preview."), DEFAULT)

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
        runtime = {**runtime, "_spy_isolated_commands": run.get("quarantined", {})}
        run = self.freeze_buys(store, runtime, run, self.check_plan_policy(store, run))
        blockers, deferred = self.review_plan_rules(store, runtime, run["legs"], self.check_plan_policy(store, run))
        if blockers:
            raise ValueError(blockers[0])
        run.update(self.defer_legs(run, deferred))
        if not run["legs"]:
            run.update(status="submitted", message="No eligible orders; deferred stocks require another preview.")
        return run, symbols

    def plan(self, store, day, snapshot, runtime, managed_symbols):
        records = store.database.read("commands", COMMANDS)["data"]
        prior = store.database.read(RECORD, DEFAULT)["data"]["run"] or {}
        prior_batch = records.get("spy_batches", {}).get(prior.get("batch_id"), {})
        uncertain = set(prior.get("quarantined", {})) | set(prior_batch.get("members", {})) | ({prior["command_id"]} if prior.get("command_id") else set())
        if any(records["commands"][key]["state"] in {"dispatch_intent", "submitting", "outcome_unknown"} for key in uncertain):
            if not prior.get("stopped_at"):
                raise ValueError("Stop unsent trades before reviewing a replacement rebalance; the uncertain stock will not be replayed.")
            runtime = self.reviewed_runtime(runtime, prior, records, set(managed_symbols))
        isolated = runtime.get("_spy_isolated_commands", {})
        tracked = set(prior.get("dispatched", {})) | ({prior["command_id"]} if prior.get("command_id") else set())
        tracked.update(prior.get("quarantined", {}))
        tracked.update(records.get("spy_batches", {}).get(prior.get("batch_id"), {}).get("members", {}))
        dispatched = {key: self.checked_submitted(runtime, records["commands"][key]) for key in tracked
                      if key not in isolated and (records["commands"][key]["state"] in ACTIVE or records["commands"][key].get("native_pending_commitment"))}
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
        pending_symbols = {records["commands"][key]["symbol"] for key in set(dispatched) | set(isolated)}
        legs = [terms for terms in legs if terms["symbol"] not in pending_symbols]
        legs.sort(key=lambda terms: terms["side"] != "SELL")
        return {"session": day, "as_of": as_of, "status": "ready" if legs else "submitted" if dispatched else "completed",
                "message": "Waiting for the first order." if legs else "No new orders needed; existing orders remain tracked." if dispatched else "No orders needed.",
                "legs": legs, "completed": 0, "fills_completed": 0, "total": len(legs), "limited": 0, "command_id": None,
                "dispatched": {key: str(value) for key, value in dispatched.items()},
                "quarantined": copy.deepcopy(isolated),
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
        from .spy_batch import isolated_commands, stock_local_recovery
        allowed = set(allowed) | isolated_commands(runtime, commands)
        commitments, known = working_commitments(runtime, commands)
        if (not known or any(not item["command_ids"] or not item["command_ids"].issubset(allowed) for item in commitments)
                or commands.get("new_orders_blocked")
                or any(item["state"] in ACTIVE and key not in allowed for key, item in commands["commands"].items())):
            raise ValueError("Unrelated or unresolved orders or an account block must clear before SPY can rebalance.")
        if commands.get("recovery_required") and not stock_local_recovery(runtime, commands):
            raise ReconciliationPending("Waiting for current account and order reconciliation; no new order has been sent.")

    @staticmethod
    def checked_submitted(runtime, command, *, terminal=False):
        filled = decimal(command.get("filled_quantity"))
        quantity = decimal(command.get("terms", {}).get("quantity"))
        deliveries = command.get("native_deliveries", {})
        native = [item for item in runtime.get("native_deliveries", []) if item.get("command_id") == command.get("id")]
        if (command.get("state") not in ({"accepted", "partially_filled", "filled", "expired", "canceled", "rejected"} if terminal else {"accepted", "partially_filled", "filled"})
                or command.get("account_id") != runtime["account"]["id"]
                or command.get("pending_action") or not command.get("broker_order_ids")
                or quantity is None or quantity <= 0 or filled is None or not 0 <= filled <= quantity
                or command["state"] == "filled" and filled != quantity
                or any(item.get("status") == "conflict" for item in native)):
            raise ValueError("An existing SPY order lacks a known broker outcome or has conflicting native proof. Reconcile orders first.")
        fills = [item for item in runtime.get("fills", []) if item.get("order_id") in command["broker_order_ids"]]
        if (command.get("native_pending_commitment") or filled > 0 and not command.get("fill_ids")
                or sum((Decimal(item["qty"]) for item in fills), Decimal(0)) != filled
                or any(item.get("native_application") != "proven_in_current_process" for item in fills)):
            raise ReconciliationPending(f"Waiting for the proven fill quantity of the existing {command['symbol']} order.")
        if not {execution_id(item.get("execution_id") or item["id"]) for item in fills}.issubset(
                {execution_id(value) for value in command["fill_ids"]}):
            raise ReconciliationPending(f"Waiting for exact execution identities for the existing {command['symbol']} order.")
        if (not deliveries
                or {item.get("event_id") for item in native} != set(deliveries)
                or any(item.get("confirmed_current_process") is not True
                    or item.get("native_epoch") != runtime["native_epoch"]
                    or item.get("source_receipt") != deliveries[item["event_id"]].get("receipt") for item in native)):
            raise ReconciliationPending(f"Waiting for current native receipt confirmation for the existing {command['symbol']} order.")
        if command["state"] == "filled":
            events = [entry for entry in command.get("timeline", []) if entry.get("state") == "filled" and entry.get("at")]
            if not events or not isinstance(runtime.get("account_observation_started_at"), str):
                raise ValueError("The post-fill account observation time is unavailable.")
            if instant(runtime["account_observation_started_at"]) <= instant(events[-1]["at"]):
                raise ReconciliationPending("Waiting for a fresh post-fill account observation.")
        return filled

    @classmethod
    def expected_positions(cls, runtime, commands, run, *, terminal=False):
        expected = {key: Decimal(value) for key, value in run["current"].items()}
        for key, baseline in run.get("dispatched", {}).items():
            command = commands["commands"][key]
            if terminal and command["state"] == "not_sent" and decimal(command["filled_quantity"]) == 0:
                continue
            delta = cls.checked_submitted(runtime, command, terminal=terminal) - Decimal(baseline)
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
    def buy_terms(terms, runtime, policy, plan, commands, *, available=None):
        symbol = terms["symbol"]
        price = price_evidence(terms, runtime)["price"]
        cash = decimal(runtime["account"].get("cash"))
        if price is None or price <= 0 or cash is None or cash < 0:
            raise ValueError(f"{symbol}: The buy requires a current price and enough observed cash.")
        spendable = SpyRebalance.spendable_cash(runtime, policy, plan, commands) if available is None else available
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

    def freeze_buys(self, store, runtime, run, policy):
        commands = store.database.read("commands", COMMANDS)["data"]
        plan = self.check_fund_binding(store, runtime, run)
        available = self.spendable_cash(runtime, policy, plan, commands)
        legs, deferred, limited = [], list(run.get("deferred", [])), run["limited"]
        for original in run["legs"]:
            terms = original
            if terms["side"] == "BUY":
                terms, resized = self.buy_terms(terms, runtime, policy, plan, commands, available=available)
                limited += resized
                if terms is None:
                    deferred.append({"terms": original, "reasons": ["Observed cash above all reserves permits less than $1."]})
                    continue
                available -= Decimal(terms["quantity"]) * Decimal(terms["limit_price"])
            legs.append(terms)
        return {**run, "legs": legs, "total": len(legs), "limited": limited, "deferred": deferred}

    def reserve_batch(self, store, record, runtime):
        from .admission import account_version, stamp
        from .spy_batch import sealed
        admission = self.desk.admission
        admission.enabled()
        admission.review_allowed()
        if admission.admission_enabled is not True:
            raise PermissionError("This session does not permit SPY batch admission")
        batch_id = str(uuid4())
        run = record["data"]["run"]
        isolated = runtime.get("_spy_isolated_commands", {})
        tracked = set(run.get("dispatched", {})) | set(isolated) | ({run["command_id"]} if run.get("command_id") else set())

        def reserve(records):
            from .spy_batch import stock_local_recovery
            saved = records[RECORD]["run"]
            if saved != run or saved.get("batch_id"):
                raise ValueError("The reviewed SPY run changed before batch reservation")
            state, investor = records["commands"], records["investor"]
            policy = investor["policy"]
            if (state["recovery_required"] and not stock_local_recovery(runtime, state)
                    or policy["revision"] != run["policy_revision"]
                    or binding(records[FUND_RECORD], run["account_id"]) != run["fund_binding"]):
                raise ValueError("Current complete account, policy and fund authority are required for batch reservation")
            commitments, known = working_commitments(runtime, state)
            if not known:
                raise ReconciliationPending("Current pending commitments are required before reserving the SPY batch")
            reservations = {}
            for item in commitments:
                if len(item["command_ids"]) != 1 or not item["command_ids"].issubset(tracked):
                    raise ValueError("Unrelated or ambiguous working obligations block batch reservation")
                reservations[next(iter(item["command_ids"]))] = str(item["cash"])
            members, deferred = {}, list(saved.get("deferred", []))
            tracked_symbols = {state["commands"][key]["symbol"] for key in tracked}
            version = account_version(runtime)
            state["account_versions"][run["account_id"]] = version
            for terms in run["legs"][run["completed"]:]:
                if self.stopped or self.desk.store is not store or store.database.read_revision(RECORD) != record["revision"]:
                    raise ReconciliationPending("The rebalance changed while preparing its unsent reservations.")
                now = datetime.now(UTC)
                if (now >= instant(run["close_at"])
                        or (now - instant(runtime["account_at"])).total_seconds() > float(CONSTRAINTS["account_max_age_seconds"])):
                    raise ReconciliationPending("Batch preparation requires a fresh account observation; no partial batch was admitted.")
                if terms["symbol"] in tracked_symbols:
                    continue
                if ((terms["side"], terms["order_type"]) not in {("BUY", "LIMIT"), ("SELL", "MARKET"), ("SELL", "LIMIT")}
                        or terms["time_in_force"] != "DAY"
                        or terms.get("session", "regular") != "regular" or terms.get("asset_class") == "us_option"
                        or any(item["terms"]["symbol"] == terms["symbol"] for item in members.values())):
                    raise ValueError("Independent SPY batch requires distinct exact regular-session equity DAY orders and bounded LIMIT buys")
                if any(command["symbol"] == terms["symbol"] and (
                        command["state"] in ACTIVE or command.get("native_pending_commitment")) for command in state["commands"].values()):
                    deferred.append({"terms": copy.deepcopy(terms), "reasons": ["An exact owned working order already reserves this stock; no duplicate is submitted."]})
                    continue
                records["investor"] = save(investor, {"action": "draft", "terms": terms, "reason": terms["rationale"]},
                    runtime, (), self.desk._proposal_research, commands=state)
                proposal = records["investor"]["proposals"][0]
                review = admission.assess(records, proposal, runtime, CONSTRAINTS)
                if not review["passed"]:
                    failed = {check["name"] for check in review["checks"] if not check["passed"]}
                    if failed and failed <= QUOTE_RULES | {"instrument", "price", "fractional_asset"}:
                        deferred.append({"terms": copy.deepcopy(terms), "reasons": review["blockers"]})
                        continue
                    raise ValueError(f"{terms['symbol']}: " + "; ".join(review["blockers"]))
                identity = str(uuid4())
                state["approvals"][identity] = {
                    "id": identity, "proposal_id": proposal["id"], "proposal_revision": proposal["revision"],
                    "terms_sha256": proposal["terms_sha256"], "terms": copy.deepcopy(proposal["terms"]),
                    "policy_revision": policy["revision"], "account_id": run["account_id"],
                    "instrument_id": terms["instrument_id"], "account_version": version,
                    "account_observed_at": runtime["account_at"], "market_event_ns": price_evidence(
                        {**terms, "order_type": "MARKET"}, runtime)["ts_event"],
                    "connection_context": {"endpoint": PAPER, "mode": "paper", "account_id": run["account_id"],
                                           "connection_session": runtime["connection_session"]},
                    "constraints": copy.deepcopy(CONSTRAINTS), "actor": ("manual" if run.get("manual") else "standing") + "-paper-spy-batch",
                    "reason": terms["rationale"], "evaluation": copy.deepcopy(review),
                    "evaluation_binding_sha256": review["binding_sha256"], "approved_at": stamp(), "expires_at": ""}
                admission._admit(records, identity, batch_runtime=runtime, batch_evaluation=review)
                command = next(item for item in state["commands"].values() if item["approval_id"] == identity)
                command["spy_batch_id"] = batch_id
                members[command["id"]] = {key: copy.deepcopy(command[key]) for key in (
                    "approval_id", "proposal_id", "proposal_revision", "terms", "terms_sha256", "client_order_id")}
                members[command["id"]]["evaluation_binding_sha256"] = review["binding_sha256"]
                reservations[command["id"]] = command["cash_commitment"]
            now = datetime.now(UTC)
            age = (now - instant(runtime["account_at"])).total_seconds()
            if not 0 <= age <= float(CONSTRAINTS["account_max_age_seconds"]) or now >= instant(run["close_at"]):
                raise ValueError("The batch review outlasted its current account or approved regular session")
            granted = now.isoformat()
            for key, member in members.items():
                command = state["commands"][key]
                approval = state["approvals"][member["approval_id"]]
                approval.update(approved_at=granted, expires_at=(now + timedelta(seconds=float(CONSTRAINTS["approval_max_age_seconds"]))).isoformat(),
                                spy_batch_id=batch_id, spy_command_id=key)
                command.update(state="dispatch_intent", dispatch_intent_at=granted)
                command["timeline"].append({"at": granted, "state": "dispatch_intent",
                    "reason": "Whole reviewed SPY batch reserved transactionally before independent native dispatch"})
            plan = records[FUND_RECORD]["plans"].get(account_key(run["account_id"]))
            reserve_floor = budget(plan, runtime, policy)["required_reserve_usd"]
            if sum((Decimal(value) for value in reservations.values()), Decimal(0)) + Decimal(reserve_floor) > Decimal(runtime["account"]["cash"]):
                raise ValueError("The complete SPY batch exceeds observed cash after existing commitments and the reserve")
            baseline = {
                "cash": runtime["account"]["cash"],
                "positions": {key: str(value) for key, value in self.check_positions(runtime, set(record["data"]["managed_symbols"])).items()},
                "account": {key: runtime["account"].get(key) for key in (
                    "id", "status", "currency", "multiplier", "shorting_enabled", "trading_blocked", "account_blocked", "trade_suspended_by_user")},
                "fill_ids": sorted({execution_id(item.get("execution_id") or item["id"]) for item in runtime.get("fills", [])}),
                "fills": {item.get("execution_id") or item["id"]: {key: item.get(key) for key in
                    ("order_id", "qty", "price", "transaction_time", "commission")} for item in runtime.get("fills", [])},
                "order_ids": [item["id"] for item in runtime.get("orders", [])],
                "tracked": {key: state["commands"][key]["filled_quantity"] for key in tracked},
                "quarantined": copy.deepcopy(isolated)}
            batch = {"id": batch_id, "account_id": run["account_id"], "endpoint": PAPER,
                     "epoch": runtime["native_epoch"], "session": run["session"], "close_at": run["close_at"],
                     "policy_revision": policy["revision"], "fund_binding": copy.deepcopy(run["fund_binding"]),
                     "constraints": copy.deepcopy(CONSTRAINTS), "granted_at": granted, "members": members,
                     "baseline": baseline, "reservations": reservations, "reserve": reserve_floor, "state": "reserved"}
            batch["binding"] = sealed(batch)
            state.setdefault("spy_batches", {})[batch_id] = batch
            offset = run["completed"] + int(bool(run.get("command_id")) and run["command_id"] not in isolated)
            saved.update(batch_id=batch_id, batch_offset=offset, dispatch_requested=False,
                command_id=None,
                quarantined=copy.deepcopy(isolated),
                total=offset + len(members) + len(isolated),
                status="batch_dispatching", deferred=deferred,
                message=f"{len(members)} exact independent orders reserved; {len(isolated)} uncertain stock(s) remain quarantined, not replayed.")

        defaults = {"investor": INVESTOR, "commands": COMMANDS, "market_history": HISTORY,
                    "stock_evidence": EVIDENCE, RECORD: DEFAULT, FUND_RECORD: FUNDS}
        snapshots = {name: store.database.read(name, default) for name, default in defaults.items()}
        prepared = {name: snapshot["data"] for name, snapshot in snapshots.items()}
        expected = {name: snapshot["revision"] for name, snapshot in snapshots.items()}
        if expected[RECORD] != record["revision"]:
            raise ReconciliationPending("The rebalance changed before batch preparation.")
        # Whole-plan review is CPU/file work, not a reason to block observation or hold the writer lease.
        reserve(prepared)
        with self.desk.maintenance, self.desk.runtime.lock:
            if self.stopped or self.desk.store is not store:
                return
            admission.enabled()
            admission.review_allowed()
            if admission.admission_enabled is not True:
                raise PermissionError("This session no longer permits SPY batch admission")
            latest = self.checked_account(run["account_id"], session=run["session"], close_at=run["close_at"])
            if (latest.get("native_epoch") != runtime.get("native_epoch")
                    or account_version(latest) != account_version(runtime)):
                raise ReconciliationPending("Account authority changed while preparing the unsent batch; reviewing current evidence again.")
            def publish(records):
                records.update(prepared)
            admission.transaction(publish, expected=expected, evidence=True, extra={RECORD: DEFAULT, FUND_RECORD: FUNDS})
        self.wake_pending = True

    def advance_batch(self, store, record):
        with self.desk.maintenance:
            if self.stopped or self.desk.store is not store:
                return
            data = store.database.read(RECORD, DEFAULT)
            run = data["data"]["run"]
            if run.get("batch_id") != record["data"]["run"].get("batch_id"):
                return
            state = store.database.read("commands", COMMANDS)["data"]
            batch = state.get("spy_batches", {}).get(run["batch_id"])
            if not batch:
                raise ValueError("The durable SPY batch is missing; no replay is permitted")
            commands = [state["commands"][key] for key in batch["members"]]
            counts = self.batch_counts(state, batch)
            deferred = list(run.get("deferred", []))
            for command in commands:
                if command.get("deferred_reason") and not any(item["terms"]["symbol"] == command["symbol"] for item in deferred):
                    deferred.append({"terms": command["terms"], "reasons": [command["deferred_reason"]]})
            blocked = batch["state"] == "blocked"
            done = all(item["transport_attempt"].get("response_receipt") or item["state"] in {"not_sent", "outcome_unknown"}
                       for item in commands)
            request = bool(commands) and not run.get("dispatch_requested") and batch["state"] == "reserved" and not blocked
            store.database.update(RECORD, data["revision"], lambda saved: saved["run"].update(
                batch_counts=counts, deferred=deferred, dispatch_requested=run.get("dispatch_requested") or request,
                completed=run["batch_offset"] + counts["sent"] + counts["not_sent"],
                status="blocked" if blocked else "submitted" if done else "batch_dispatching",
                message=batch.get("reason") if blocked else (
                    "Independent dispatch finished; uncertain and working stocks retain their reservations and are not replayed."
                    if done else "Independent batch dispatch in progress; native queueing is not broker submission.")), DEFAULT)
        if request:
            try:
                self.desk.runtime.request("dispatch_spy_batch", batch_id=batch["id"])
            except ValueError as error:
                with self.desk.maintenance:
                    if self.desk.store is store:
                        latest = store.database.read(RECORD, DEFAULT)
                        store.database.update(RECORD, latest["revision"], lambda saved: saved["run"].update(
                            message=f"Native batch request needs observation, not replay: {error}"), DEFAULT)
            self.wake_pending = True

    @staticmethod
    def batch_counts(state, batch):
        commands = [state["commands"][key] for key in batch["members"]]
        return {"admitted": len(commands),
                "native_queued": sum(bool(item.get("native_enqueued_at")) for item in commands),
                "transport_started": sum(item["transport_attempt"].get("state") == "started" for item in commands),
                "sent": sum(bool(item["transport_attempt"].get("response_receipt")) for item in commands),
                "working": sum(item["state"] in {"accepted", "partially_filled"} for item in commands),
                "filled": sum(item["state"] == "filled" for item in commands),
                "expired": sum(item["state"] == "expired" for item in commands),
                "rejected": sum(item["state"] == "rejected" for item in commands),
                "unknown": sum(item["state"] == "outcome_unknown" for item in commands),
                "quarantined": sum(state["commands"][key]["state"] in {"dispatch_intent", "submitting", "outcome_unknown"}
                                   or bool(state["commands"][key].get("native_pending_commitment"))
                                   for key in batch["baseline"].get("quarantined", {})),
                "not_sent": sum(item["state"] == "not_sent" for item in commands)}

    def reviewed_runtime(self, runtime, run, state, managed):
        """Prove resources without assuming an uncertain stock was never sent."""
        from .spy_batch import cash_values
        batch = state.get("spy_batches", {}).get(run.get("batch_id"), {})
        tracked = set(run.get("dispatched", {})) | set(run.get("quarantined", {})) | set(batch.get("members", {})) | ({run["command_id"]} if run.get("command_id") else set())
        isolated, proven, executions = {}, {}, []
        for key in tracked:
            command = state["commands"][key]
            if key == run.get("command_id"):
                reviewed = run["legs"][run["completed"]]
                if any(command["terms"].get(field) != value for field, value in reviewed.items()):
                    raise ValueError("The attached SPY command differs from its original reviewed terms.")
            if command["state"] in {"dispatch_intent", "submitting", "outcome_unknown"}:
                leg = (run["legs"][run["completed"]] if key == run.get("command_id") else
                       run.get("quarantined", {}).get(key, batch.get("members", {}).get(key, {})).get("terms"))
                if (not leg or any(command.get(field) != leg[field] for field in ("symbol", "side", "instrument_id"))
                        or any(command["terms"].get(field) != value for field, value in leg.items())
                        or decimal(command["filled_quantity"]) != 0):
                    raise ReconciliationPending("The uncertain stock needs exact unchanged reviewed terms and execution evidence; it will not be replayed.")
                pending = command.get("native_pending_commitment", {})
                cash = max(Decimal(command["cash_commitment"]), Decimal(pending.get("cash_commitment", "0")))
                isolated[key] = {field: copy.deepcopy(command[field]) for field in (
                    "id", "account_id", "instrument_id", "symbol", "side", "terms", "terms_sha256", "client_order_id", "connection_context")}
                isolated[key].update(reserved_cash=str(cash), reserved_quantity=command["terms"]["quantity"])
                continue
            if (command["state"] == "not_sent" and command.get("transport_attempt", {}).get("state") == "not_sent"
                    and command["transport_attempt"].get("version") == 1 and command["transport_attempt"].get("resolved_at")
                    and not any(command.get(field) for field in ("broker_order_ids", "fill_ids", "native_deliveries", "native_pending_commitment", "pending_action"))
                    and all(decimal(command.get(field)) == 0 for field in ("cash_commitment", "remaining_quantity", "filled_quantity"))):
                continue
            filled = self.checked_submitted(runtime, command, terminal=True)
            baseline = Decimal(run.get("dispatched", {}).get(key, "0"))
            if baseline != 0:
                raise ReconciliationPending("The pre-existing execution baseline needs separate cash proof before independent dispatch.")
            proven[key] = "0"
            fills = [row for row in runtime.get("fills", []) if row.get("order_id") in command["broker_order_ids"]]
            if sum((Decimal(row["qty"]) for row in fills), Decimal(0)) != filled:
                raise ReconciliationPending("Current exact execution quantities are unavailable.")
            for row in fills:
                executions.append({"ts_event": len(executions), "execution_id": row.get("execution_id") or row["id"],
                    "side": command["side"], "quantity": row["qty"], "price": row["price"],
                    "commission": row.get("commission") if row.get("commission") is not None else row.get("native_fee", {}).get("amount")})
        expected = self.expected_positions(runtime, state, {**run, "dispatched": proven})
        observed = {key: value for key, value in self.check_positions(runtime, managed).items() if value != 0}
        if observed != expected or Decimal(runtime["account"]["cash"]) not in cash_values(run["initial_cash"], executions):
            raise ReconciliationPending("Current holdings or cash are not explained by proven executions; uncertain sale proceeds cannot finance another stock.")
        return {**runtime, "_spy_isolated_commands": isolated}

    def reserve_remaining(self, store, record):
        """Reserve the same reviewed remainder without replaying attached commands."""
        data, run = record["data"], record["data"]["run"]
        runtime = self.checked_account(data["account_id"], session=run["session"], close_at=run.get("close_at"))
        self.check_plan_policy(store, run)
        self.check_fund_binding(store, runtime, run)
        state = store.database.read("commands", COMMANDS)["data"]
        self.reserve_batch(store, record, self.reviewed_runtime(runtime, run, state, set(data["managed_symbols"])))

    def advance(self, store, record):
        if record["data"]["run"].get("batch_id"):
            return self.advance_batch(store, record)
        database = store.database
        data, run = record["data"], record["data"]["run"]
        with self.desk.maintenance:
            if self.stopped or self.desk.store is not store:
                return
            runtime = self.desk.runtime.state()
            if paper_account(runtime) != data["account_id"]:
                return
            if runtime.get("native_contract", {}).get("observation_in_progress") is True:
                return
            saved_commands = database.read("commands", COMMANDS)["data"]["commands"]
            tracked = set(run.get("dispatched", {})) | ({run["command_id"]} if run.get("command_id") else set())
            filled = {key for key in tracked if saved_commands.get(key, {}).get("state") == "filled"}
            account_age = Decimal(str((datetime.now(UTC) - instant(runtime["account_at"])).total_seconds()))
            refresh = (runtime.get("reconciliation", {}).get("status") != "reconciled"
                       or not 0 <= account_age <= Decimal(CONSTRAINTS["account_max_age_seconds"]))
            post_fill = False
            for key in filled - self.post_fill_refreshed:
                try:
                    self.checked_submitted(runtime, saved_commands[key])
                except ReconciliationPending:
                    post_fill = True
                    break
                else:
                    self.post_fill_refreshed.add(key)
        if refresh or post_fill:
            # Native replies need the observer's maintenance lock; never wait for them while holding it.
            try:
                self.desk.runtime.request("refresh", post_fill=post_fill)
            except ValueError:
                with self.desk.maintenance:
                    self.wake_pending = False
                    self.next_poll = time.monotonic() + 5
                return
        with self.desk.maintenance:
            current = database.read(RECORD, DEFAULT)
            if self.stopped or self.desk.store is not store or current["revision"] != record["revision"]:
                return
            data, run = current["data"], current["data"]["run"]
            if not data["enabled"] and not self.active_manual_run(data):
                return
            if post_fill:
                self.post_fill_refreshed.update(filled)
        self.reserve_remaining(store, current)

    def admit(self, terms, runtime, account_id, *, manual=False):
        from .admission import invalidate
        admission = self.desk.admission
        def draft(records):
            records["investor"] = save(records["investor"], {"action": "draft", "terms": terms, "reason": terms["rationale"]},
                                      runtime, (), self.desk._proposal_research, commands=records["commands"])
            proposal = records["investor"]["proposals"][0]
            review = admission.assess(records, proposal, runtime, CONSTRAINTS)
            if not review["passed"]:
                failed = {check["name"] for check in review["checks"] if not check["passed"]}
                error = StockDeferred if runtime.get("market_open") is True and failed and failed <= QUOTE_RULES | {"instrument", "price", "fractional_asset"} else ValueError
                raise error(f"{terms['symbol']}: " + "; ".join(review["blockers"]))
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
