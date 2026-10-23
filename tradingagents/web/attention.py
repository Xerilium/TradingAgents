"""Investor rules evaluated against existing observations, without research or trading."""

import copy
import threading
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from .investor import decimal, digest
from .workspace import text

DEFAULT = {"rules": {}, "rule_history": [], "reviews": {}}
OBSERVATIONS = {"rule_states": {}, "occurrences": {}, "monitor": {"state": "not_started", "last_evaluated_at": None, "gaps": []}}
KINDS = {"price_above", "price_below", "movement", "source_missing", "source_stale", "policy_condition"}
SCOPES = {"quote", "account", "research", "history", "news", "earnings", "fundamentals", "corporate_actions", "classification"}
EVIDENCE_SOURCE_FIELDS = {"status", "reason", "observed_at", "checked_at", "price", "change_pct", "basis", "source", "source_id",
    "provider", "feed", "account_id", "run_id", "revision", "time_basis", "trade_date", "input_identity", "artifact", "content_sha256",
    "key", "start", "end", "instrument_id", "native_epoch", "source_event_ns", "source_received_ns", "result_sha256", "market_source_sha256"}


def now():
    return datetime.now(UTC).isoformat()


def browser_delivery(saved, request, generation):
    """Persist opt-in and one best-effort request per browser/occurrence; never send a notification."""
    profile_id = request.get("profile_id")
    if not isinstance(profile_id, str) or str(UUID(profile_id)) != profile_id:
        raise ValueError("A stable browser profile identity is required")
    if request.get("store_generation") != generation:
        raise ValueError("Application records changed; reload before changing browser notifications")
    profile = saved.setdefault("browser_profiles", {}).setdefault(profile_id,
        {"enabled": False, "enabled_after": "", "generation": generation, "deliveries": {}})
    action = request["action"]
    if action == "browser_enable":
        if request.get("permission") != "granted":
            raise ValueError("Enable browser permission before enabling notifications")
        profile.update(enabled=True, enabled_after=now(), generation=generation)
        return {"enabled": True}
    if action == "browser_disable":
        profile["enabled"] = False
        return {"enabled": False}
    occurrence = saved["occurrences"].get(request.get("id"))
    if not occurrence:
        raise ValueError("The saved alert occurrence is unavailable")
    prior = profile["deliveries"].get(occurrence["id"])
    if action == "browser_failed":
        if not prior or prior.get("attempt_id") != request.get("attempt_id") or prior["state"] != "requested":
            raise ValueError("Notification failure must match its exact requested attempt")
        prior.update(state="failed", updated_at=now(), error=text(request.get("error", "Browser notification failed"), 4000, "notification error"))
        return {"state": "failed"}
    if action not in {"browser_claim", "browser_retry"}:
        raise ValueError("Unknown browser notification operation")
    if not profile["enabled"] or profile["generation"] != generation:
        raise ValueError("Browser notifications are disabled for this application generation")
    retry = action == "browser_retry"
    if retry and (not prior or prior["state"] != "failed" or prior.get("generation") != generation):
        raise ValueError("Only an explicitly selected failed current-generation attempt can be retried")
    if not retry and (prior or not occurrence["unread"] or
            datetime.fromisoformat(occurrence["created_at"]) <= datetime.fromisoformat(profile["enabled_after"])):
        return {"claimed": False}
    attempt = {"attempt_id": str(uuid4()), "state": "requested", "generation": generation, "requested_at": now(),
               "limitation": "Browser display requested; delivery and reading are not confirmed"}
    profile["deliveries"][occurrence["id"]] = attempt
    return {"claimed": True, "attempt_id": attempt["attempt_id"], "occurrence": copy.deepcopy(occurrence)}


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
              "source_at": source.get("observed_at"), "reason": source.get("reason") or "Required input is unavailable",
              "facts": {"source_present": bool(source), "source_status": source.get("status")}}
    kind = rule["kind"]
    if kind == "policy_condition":
        proposal = context["proposals"].get(params["proposal_id"])
        if proposal and not proposal.get("conditions_stale"):
            matched = params["condition"] in proposal["impact"]["conditions"]
            result["facts"].update(condition_present=matched)
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
        age_at = datetime.now(UTC)
        age = Decimal(str((age_at - stamp).total_seconds()))
    except (ValueError, TypeError, AttributeError):
        return result
    maximum = decimal(params.get("max_age_seconds"))
    if maximum is None or maximum <= 0 or age < 0:
        return result
    result["facts"].update(source_age_seconds=str(age), max_age_seconds=str(maximum), age_calculated_at=age_at.isoformat())
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
    result["facts"].update(value=str(value), threshold=str(threshold),
                           comparison="absolute_greater_or_equal" if kind == "movement" else "greater_than" if kind == "price_above" else "less_than")
    matched = abs(value) >= threshold if kind == "movement" else value > threshold if kind == "price_above" else value < threshold
    result.update(state="triggered" if matched else "clear", reason="Observed " + str(value) + "; investor threshold " + str(threshold))
    return result


def occurrence_evidence(rule, context, evaluation):
    """Retain the inputs actually evaluated; never resolve a newer source for an old occurrence."""
    source = context["sources"].get(rule["scope"], {}).get(rule["symbol"] if rule["scope"] != "account" else "account", {})
    retained = {key: copy.deepcopy(value) for key, value in source.items() if key in EVIDENCE_SOURCE_FIELDS}
    proposal = context["proposals"].get(rule["parameters"]["proposal_id"]) if rule["kind"] == "policy_condition" else None
    snapshot = None if proposal is None else {key: copy.deepcopy(proposal.get(key))
        for key in ("id", "revision", "policy_revision", "terms_sha256", "conditions_stale")}
    if snapshot is not None:
        snapshot["conditions"] = copy.deepcopy(proposal["impact"]["conditions"])
    reference = bool(retained.get("artifact") or retained.get("run_id") and retained.get("revision") is not None or snapshot)
    return {"version": "occurrence-evidence-v1", "evaluated_at": evaluation["at"], "store_generation": context.get("store_generation"),
            "rule": {key: copy.deepcopy(rule[key]) for key in ("id", "name", "revision", "kind", "scope", "symbol", "parameters", "active", "updated_at")},
            "evaluation": copy.deepcopy(evaluation), "source": retained, "proposal": snapshot,
            "reference_status": "recorded_not_validated" if reference else "observation_only"}


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
                        "evidence": occurrence_evidence(rule, context, result),
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
