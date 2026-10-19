"""Investor rules evaluated against existing observations, without research or trading."""

import copy
import threading
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from .investor import decimal, digest
from .workspace import text

DEFAULT = {"rules": {}, "rule_history": [], "reviews": {}}
OBSERVATIONS = {"rule_states": {}, "occurrences": {}, "monitor": {"state": "not_started", "last_evaluated_at": None, "gaps": []}}
KINDS = {"price_above", "price_below", "movement", "source_missing", "source_stale", "policy_condition"}
SCOPES = {"quote", "account", "research", "history", "news", "earnings", "fundamentals", "corporate_actions", "classification"}


def now():
    return datetime.now(UTC).isoformat()


def change(saved, request, universe, research, bindings=None):
    action, stamp = request.get("action"), now()
    if action == "review":
        symbol, run, revision = request.get("symbol"), request.get("run_id"), request.get("research_revision")
        source = research.get(symbol)
        if not source or source.get("run_id") != run or source.get("revision", 0) != revision:
            raise ValueError("Review disposition must match the exact saved stock/run/revision")
        disposition = request.get("disposition")
        if disposition not in {"reviewed", "needs_review", "deferred"} or type(request.get("prioritize")) is not bool:
            raise ValueError("Choose an explicit review disposition and research-priority state")
        key = symbol + ":" + run + ":" + str(revision)
        note = {"symbol": symbol, "run_id": run, "research_revision": revision, "disposition": disposition,
                "prioritize": request["prioritize"], "notes": text(request.get("notes", ""), 20000, "review notes"), "saved_at": stamp,
                "source_bindings": copy.deepcopy((bindings or {}).get(symbol, {}))}
        old = saved["reviews"].get(key, {})
        saved["reviews"][key] = {**note, "history": old.get("history", []) + [copy.deepcopy(note)]}
        return saved
    identity = request.get("id") or str(uuid4())
    previous = saved["rules"].get(identity)
    if request.get("id") and previous is None:
        raise ValueError("Saved alert rule was not found")
    if action in {"pause", "resume", "remove"}:
        if previous is None:
            raise ValueError("Select an existing alert rule")
        previous.update(active=action == "resume", removed=action == "remove", revision=previous["revision"] + 1, updated_at=stamp)
        previous["evaluation"] = {"state": "paused" if action != "resume" else "awaiting_observation", "at": stamp,
                                  "reason": "Monitoring gap while rule was inactive; no unseen interval is claimed evaluated"}
        saved["rule_history"].append({"action": action, "rule": copy.deepcopy(previous), "at": stamp})
        return saved
    if action != "save":
        raise ValueError("Unknown attention operation")
    kind, scope, symbol = request.get("kind"), request.get("scope"), request.get("symbol")
    if kind not in KINDS or scope not in SCOPES or symbol not in universe and scope != "account" and kind != "policy_condition":
        raise ValueError("Choose a supported rule, source scope and configured/owned symbol")
    params = request.get("parameters")
    if not isinstance(params, dict):
        raise ValueError("Enter explicit rule parameters")
    if kind in {"price_above", "price_below", "movement"}:
        threshold, age = decimal(params.get("threshold")), decimal(params.get("max_age_seconds"))
        if scope != "quote" or threshold is None or threshold < 0 or age is None or age <= 0:
            raise ValueError("Price/movement rules require quote scope, threshold and maximum source age")
    if kind == "source_stale" and (decimal(params.get("max_age_seconds")) is None or decimal(params["max_age_seconds"]) <= 0):
        raise ValueError("Enter an explicit positive stale-age threshold")
    if kind == "policy_condition" and (not params.get("proposal_id") or not params.get("condition")):
        raise ValueError("Select a saved proposal and the exact condition to monitor")
    if type(request.get("active")) is not bool:
        raise ValueError("Choose active or paused explicitly")
    rule = {"id": identity, "name": text(request.get("name"), 100, "rule name"), "kind": kind, "scope": scope,
            "symbol": symbol, "parameters": copy.deepcopy(params), "active": request["active"], "removed": False,
            "revision": previous["revision"] + 1 if previous else 1, "updated_at": stamp,
            "evaluation": {"state": "awaiting_observation" if request["active"] else "paused", "at": stamp}, "active_occurrence_id": None}
    if not rule["name"]:
        raise ValueError("Name the rule")
    saved["rules"][identity] = rule
    saved["rule_history"].append({"action": "save", "at": stamp, "rule": copy.deepcopy(rule)})
    return saved


def evaluate_rule(rule, context):
    params, scope, symbol = rule["parameters"], rule["scope"], rule["symbol"]
    source = context["sources"].get(scope, {}).get(symbol if scope != "account" else "account", {})
    identity = digest({"source": source, "rule_revision": rule["revision"]})
    result = {"state": "unavailable", "at": now(), "input_identity": identity,
              "source_at": source.get("observed_at"), "reason": source.get("reason") or "Required input is unavailable"}
    kind = rule["kind"]
    if kind == "policy_condition":
        proposal = context["proposals"].get(params["proposal_id"])
        if proposal and not proposal.get("conditions_stale"):
            matched = params["condition"] in proposal["impact"]["conditions"]
            result.update(state="triggered" if matched else "clear", reason="Saved source-bound proposal condition is present" if matched else "Condition is absent from the saved review",
                          input_identity=digest({"id": proposal["id"], "revision": proposal["revision"], "policy": proposal["policy_revision"]}))
        return result
    if kind == "source_missing":
        result.update(state="triggered" if source.get("status") in {"missing", "unavailable", "disconnected"} else "clear" if source.get("status") == "available" else "unavailable",
                      reason=source.get("reason") or "Observed source availability: " + str(source.get("status", "unknown")))
        return result
    observed = source.get("observed_at")
    try:
        stamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return result
        age = Decimal(str((datetime.now(UTC) - stamp).total_seconds()))
    except (ValueError, TypeError, AttributeError):
        return result
    maximum = decimal(params.get("max_age_seconds"))
    if maximum is None or maximum <= 0 or age < 0:
        return result
    result["input_identity"] = digest({"source": identity, "stale": age > maximum})
    if kind == "source_stale":
        if source.get("status") != "available":
            result["reason"] = "Unavailable or disconnected source cannot produce a clean freshness result"
            return result
        result.update(state="triggered" if age > maximum else "clear", reason="Observed source age " + str(age) + " seconds; configured limit " + str(maximum))
        return result
    if source.get("status") != "available" or age > maximum:
        result["reason"] = "Missing, disconnected or stale input prevents a threshold result"
        return result
    value = decimal(source.get("change_pct" if kind == "movement" else "price"))
    if value is None:
        return result
    threshold = Decimal(str(params["threshold"]))
    matched = abs(value) >= threshold if kind == "movement" else value > threshold if kind == "price_above" else value < threshold
    result.update(state="triggered" if matched else "clear", reason="Observed " + str(value) + "; investor threshold " + str(threshold))
    return result


class AttentionMonitor:
    def __init__(self, database, context, lock):
        self.database, self.context, self.lock = database, context, lock
        self.stopped = threading.Event()
        self.thread = None

    def start(self):
        record = self.database.read("attention_observations", OBSERVATIONS)
        def restart(saved):
            monitor = saved["monitor"]
            monitor["gaps"].append({"from": monitor.get("last_evaluated_at"), "to": now(), "reason": "Service restart; stopped interval was not observed"})
            monitor.update(state="starting", started_at=now())
            return saved
        self.database.update("attention_observations", record["revision"], restart, OBSERVATIONS)
        self.thread = threading.Thread(target=self.run, name="investor-attention", daemon=True)
        self.thread.start()

    def evaluate(self):
        context = self.context()
        def update(records):
            saved, observed = records["attention"], records["attention_observations"]
            for rule in saved["rules"].values():
                if not rule["active"] or rule["removed"]:
                    continue
                prior = observed["rule_states"].get(rule["id"], {})
                if prior.get("rule_revision") != rule["revision"]:
                    prior = {"rule_revision": rule["revision"], "active_occurrence_id": None}
                result = evaluate_rule(rule, context)
                previous = prior.get("evaluation", {})
                if previous.get("input_identity") == result["input_identity"] and previous.get("state") == result["state"]:
                    continue
                prior["evaluation"] = result
                if result["state"] == "triggered" and not prior.get("active_occurrence_id"):
                    identity = str(uuid4())
                    prior["active_occurrence_id"] = identity
                    observed["occurrences"][identity] = {"id": identity, "rule_id": rule["id"], "rule_revision": rule["revision"],
                        "symbol": rule["symbol"], "scope": rule["scope"], "name": rule["name"], "evaluation": copy.deepcopy(result),
                        "created_at": now(), "unread": True, "acknowledged_at": None, "revision": 1}
                elif result["state"] == "clear":
                    prior["active_occurrence_id"] = None
                observed["rule_states"][rule["id"]] = prior
            observed["monitor"].update(state="evaluating", last_evaluated_at=now(), universe_count=context["universe_count"])
        self.database.transact({"attention": DEFAULT, "attention_observations": OBSERVATIONS}, update)

    def run(self):
        while not self.stopped.wait(5):
            try:
                with self.lock:
                    self.evaluate()
            except Exception:
                # The UI compares the last evaluation time to the service clock and shows the gap.
                continue

    def close(self):
        self.stopped.set()
