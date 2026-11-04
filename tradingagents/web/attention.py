"""Investor rules evaluated against existing observations, without research or trading."""

import copy
import threading
from datetime import UTC, datetime
from decimal import Context, Decimal
from uuid import UUID, uuid4

from .investor import decimal, digest
from .workspace import text

DEFAULT = {"rules": {}, "rule_history": [], "reviews": {}}
OBSERVATIONS = {"rule_states": {}, "occurrences": {}, "monitor": {"state": "not_started", "last_evaluated_at": None, "gaps": []}}
KINDS = {"price_above", "price_below", "movement", "source_missing", "source_stale", "policy_condition", "indicator", "drawing"}
SCOPES = {"quote", "account", "research", "history", "news", "earnings", "fundamentals", "corporate_actions", "classification", "indicator", "drawing"}
INDICATORS = ("close_50_sma", "close_200_sma", "close_10_ema", "macd", "macds", "macdh", "rsi", "boll", "boll_ub", "boll_lb", "atr", "vwma", "mfi")
EVIDENCE_SOURCE_FIELDS = {"status", "reason", "observed_at", "checked_at", "price", "change_pct", "basis", "source", "source_id",
    "provider", "feed", "account_id", "run_id", "revision", "time_basis", "trade_date", "input_identity", "artifact", "content_sha256",
    "key", "start", "end", "instrument_id", "native_epoch", "source_event_ns", "source_received_ns", "result_sha256", "market_source_sha256",
    "derivation_identity", "comparable_identity", "initialization_history_sha256", "definition_sha256", "units", "artifact_store", "timeframe", "adjustment", "currency", "session", "eligibility_evidence"}


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


def atoms(rule):
    return rule.get("atoms", [rule])


def validate_atom(atom):
    if not isinstance(atom, dict) or "atoms" in atom or "operator" in atom:
        raise ValueError("Each condition must be a flat condition object")
    kind, scope, params = atom.get("kind"), atom.get("scope"), atom.get("parameters")
    if kind not in KINDS or scope not in SCOPES or not isinstance(params, dict):
        raise ValueError("Choose an existing condition and explicit source parameters")
    if kind in {"price_above", "price_below", "movement"}:
        threshold, age = decimal(params.get("threshold")), decimal(params.get("max_age_seconds"))
        if scope != "quote" or threshold is None or threshold < 0 or age is None or age <= 0:
            raise ValueError("Price/movement conditions require quote scope, threshold and positive maximum age")
    if kind == "source_stale" and (decimal(params.get("max_age_seconds")) is None or decimal(params["max_age_seconds"]) <= 0):
        raise ValueError("Enter an explicit positive stale-age threshold")
    if kind == "policy_condition" and (not params.get("proposal_id") or not params.get("condition")):
        raise ValueError("Select a saved proposal and exact policy condition")
    if kind == "indicator":
        if (scope != "indicator" or params.get("indicator") not in INDICATORS
                or params.get("comparison") not in {"above", "below", "cross_above", "cross_below"}
                or decimal(params.get("threshold")) is None or decimal(params.get("max_age_seconds")) is None
                or decimal(params["max_age_seconds"]) <= 0 or params.get("context") not in {"current", "research"}
                or params.get("context") == "research" and not isinstance(params.get("run_id"), str)
                or params.get("context") == "current" and params.get("timeframe") not in {"1Min", "5Min", "15Min", "30Min", "1Hour", "1Day"}):
            raise ValueError("Choose an indicator, comparison, exact threshold, positive age and explicit history/run context")
    elif scope == "indicator":
        raise ValueError("Indicator scope requires an indicator condition")
    if kind == "drawing":
        ref = params.get("drawing_ref") or {}
        if (scope != "drawing" or not isinstance(ref, dict) or not isinstance(ref.get("drawing_id"), str)
                or str(UUID(ref["drawing_id"])) != ref["drawing_id"] or type(ref.get("revision")) is not int or ref["revision"] <= 0
                or not isinstance(ref.get("geometry_sha256"), str) or len(ref["geometry_sha256"]) != 64
                or params.get("field") not in {"o", "h", "l", "c"} or params.get("comparison") not in {"cross_above", "cross_below"}
                or params.get("geometry_policy") not in {"segment", "extrapolate"}
                or decimal(params.get("max_age_seconds")) is None or decimal(params["max_age_seconds"]) <= 0
                or params.get("context") not in {"current", "research"} or not params.get("timeframe")
                or params.get("context") == "current" and not params.get("history_key")
                or params["context"] == "research" and not params.get("run_id")):
            raise ValueError("Choose an exact saved numeric drawing, explicit history selection, crossing, extent and positive age")
        if "drawing" in params:
            validate_drawing_binding(params)
    elif scope == "drawing":
        raise ValueError("Drawing scope requires a drawing condition")


def drawing_geometry(value):
    return digest({key: value.get(key) for key in ("kind", "scope", "points")})


def validate_drawing_binding(params):
    from .workspace import drawing
    value = drawing(params.get("drawing"))
    ref = params["drawing_ref"]
    if (value.get("deleted") or value["kind"] not in {"horizontal-line", "trend-line"}
            or value["id"] != ref["drawing_id"] or value["revision"] != ref["revision"]
            or drawing_geometry(value) != ref["geometry_sha256"] or value["scope"]["timeframe"] != params["timeframe"]
            or value["scope"]["context"] != ("saved" if params["context"] == "research" else "current")):
        raise ValueError("Retained numeric drawing identity/geometry/source context differs from the bound rule")
    return value


def drawing_key(symbol, params):
    return digest({"symbol": symbol, **{key: params.get(key) for key in
        ("drawing_ref", "context", "run_id", "history_key", "timeframe")}})


def drawing_history_points(bars, states=None):
    unique = {}
    for bar in bars:
        if bar["t"] in unique and unique[bar["t"]] != bar:
            raise ValueError("Conflicting retained bar revisions require explicit correction")
        unique[bar["t"]] = bar
    prefix, points = digest([]), []
    for stamp, bar in sorted(unique.items()):
        raw = copy.deepcopy(bar.get("raw") or {name: bar.get(name) for name in ("o", "h", "l", "c", "v")})
        prefix = digest({"prior": prefix, "t": stamp, "raw": raw})
        state = (states or {}).get(str(stamp), {})
        points.append({"t": stamp, "raw": raw, "history_prefix_identity": prefix,
            "eligible": state.get("closed") is True and state.get("fresh") is True, "eligibility_evidence": copy.deepcopy(state)})
    return points


def drawing_coordinates(value, points):
    arithmetic = Context(prec=256)
    def seconds(stamp):
        return Decimal(str(datetime.fromisoformat(stamp).replace(tzinfo=UTC).timestamp())) if isinstance(stamp, str) else Decimal(str(stamp))
    def logical(stamp):
        exact = next((Decimal(i) for i, row in enumerate(points) if row["t"] == stamp), None)
        if exact is not None:
            return exact
        stamp = seconds(stamp)
        for i in range(1, len(points)):
            left, right = seconds(points[i - 1]["t"]), seconds(points[i]["t"])
            if left < stamp < right:
                return arithmetic.add(Decimal(i - 1), arithmetic.divide(arithmetic.subtract(stamp, left), arithmetic.subtract(right, left)))
        raise ValueError("Timestamp anchor is outside the actual retained axis")
    anchors = []
    for anchor in value["points"]:
        if anchor["basis"] == "logical_offset":
            origin = next((Decimal(i) for i, row in enumerate(points) if row["t"] == anchor["origin_time"]), None)
            if origin is None:
                raise ValueError("Projected origin is absent from the retained axis")
            x = arithmetic.add(origin, Decimal(str(anchor["offset"])))
        else:
            x = logical(anchor["time"])
            if anchor["basis"] == "observed":
                row = next((row for row in points if row["t"] == anchor["time"]), {})
                if decimal(row.get("raw", {}).get(anchor["value_kind"])) != decimal(anchor["price"]):
                    raise ValueError("Observed anchor differs from retained OHLC; original source pin remains preserved")
        anchors.append({"logical_index": str(x), "price": anchor["price"]})
    return anchors


def drawing_threshold(value, anchors, logical_index, policy):
    arithmetic = Context(prec=256)
    if not isinstance(anchors, list) or len(anchors) != len(value["points"]):
        raise ValueError("Every typed drawing anchor requires its retained resolved coordinate")
    pairs = [(decimal(anchor.get("logical_index")), decimal(anchor.get("price"))) for anchor in anchors]
    if logical_index is None or any(x is None or price != decimal(point["price"]) for (x, price), point in zip(pairs, value["points"], strict=True)):
        raise ValueError("Retained resolved drawing anchors differ from the exact numeric geometry")
    if value["kind"] == "horizontal-line":
        return pairs[0][1]
    (a, price_a), (b, price_b) = pairs
    if a == b or policy == "segment" and not min(a, b) <= logical_index <= max(a, b):
        raise ValueError("Vertical/undefined trendline or observation outside its explicit segment")
    return arithmetic.add(price_a, arithmetic.divide(arithmetic.multiply(arithmetic.subtract(logical_index, a), arithmetic.subtract(price_b, price_a)), arithmetic.subtract(b, a)))


def validate_drawing_evidence(rule, evaluation):
    """Validate retained numeric evidence structure; source bytes remain independently hash checked."""
    params, facts = rule["parameters"], evaluation.get("facts", {})
    value = validate_drawing_binding(params)
    if (facts.get("drawing") != value or facts.get("geometry_sha256") != drawing_geometry(value)
            or facts.get("algorithm") != "retained-logical-axis-decimal-residual-v1"
            or facts.get("field") != params["field"] or facts.get("comparison") != params["comparison"]
            or facts.get("geometry_policy") != params["geometry_policy"]):
        raise ValueError("Captured drawing geometry/algorithm differs from its exact rule revision")
    observations = [facts.get(name) for name in ("previous_observation", "observation")]
    for observation in observations:
        if observation is None:
            continue
        source = observation.get("source") or {}
        numbers = [decimal(observation.get(name)) for name in ("value", "threshold", "residual", "logical_index")]
        if (any(number is None for number in numbers) or Context(prec=256).subtract(numbers[0], numbers[1]) != numbers[2]
                or drawing_threshold(value, observation.get("anchors"), numbers[3], params["geometry_policy"]) != numbers[1]
                or decimal(observation.get("raw", {}).get(params["field"])) != numbers[0]
                or observation.get("eligible") is not True or not observation.get("history_prefix_identity")
                or (observation.get("eligibility_evidence") or {}).get("closed") is not True
                or (observation.get("eligibility_evidence") or {}).get("fresh") is not True
                or not observation.get("comparable_identity") or not (source.get("artifact") or {}).get("sha256")
                or any(source.get(key) != value["scope"][key] for key in value["scope"])):
            raise ValueError("Captured drawing raw value/residual/source identity is incomplete or inconsistent")
    if evaluation.get("state") == "triggered":
        old, current = observations
        if not old or not current or old["t"] >= current["t"] or old["comparable_identity"] != current["comparable_identity"]:
            raise ValueError("A drawing occurrence requires two newer comparable eligible observations")
        before, after = Decimal(old["residual"]), Decimal(current["residual"])
        if not (before <= 0 < after if params["comparison"] == "cross_above" else before >= 0 > after):
            raise ValueError("Captured drawing residuals do not establish the selected crossing")
    return True


def evaluate_drawing(rule, context, previous):
    params = rule["parameters"]
    data = context.get("drawings", {}).get(drawing_key(rule["symbol"], params), {})
    source, drawing = data.get("source", {}), params.get("drawing", {})
    old = (previous or {}).get("facts", {}).get("observation")
    result = {"state": "unavailable", "at": now(), "input_identity": digest(data), "source_at": source.get("observed_at"),
        "indicator_source": source, "reason": data.get("error") or "Drawing inputs are unavailable",
        "facts": {"drawing": copy.deepcopy(drawing), "geometry_sha256": params["drawing_ref"]["geometry_sha256"],
            "algorithm": "retained-logical-axis-decimal-residual-v1", "geometry_policy": params["geometry_policy"],
            "arithmetic": "Decimal precision 256, ROUND_HALF_EVEN; repeating logical interpolation is rounded",
            "manual_time_mapping": "exact retained time or linear interpolation between adjacent actual bar times",
            "field": params["field"], "comparison": params["comparison"], "observation": None,
            "high_water_time": (previous or {}).get("facts", {}).get("high_water_time") or (old or {}).get("t")}}
    if data.get("error") or not data.get("points"):
        return result
    points = data["points"]
    try:
        selected = data.get("selected_time")
        index = next((i for i, point in enumerate(points) if point["t"] == selected), None) if selected is not None else len(points) - 1
        if index is None:
            raise ValueError("Declared latest completed session is absent from actual retained bars")
        point = points[index]
        arithmetic = Context(prec=256)
        age = Decimal(str((datetime.now(UTC) - datetime.fromisoformat(source["observed_at"].replace("Z", "+00:00"))).total_seconds()))
        if age < 0 or age > decimal(params["max_age_seconds"]) or not point.get("eligible"):
            result["reason"] = "Raw bar finality/freshness or configured source age is unavailable"
            return result
        high = result["facts"]["high_water_time"]
        result["facts"]["high_water_time"] = max(high, point["t"]) if high is not None else point["t"]
        if high is not None and point["t"] <= high:
            result["facts"]["observation"] = old if old and point["t"] == old["t"] and point["history_prefix_identity"] == old.get("history_prefix_identity") else None
            result["reason"] = "Repeated/older/corrected same-bar observations cannot advance continuity or re-arm"
            return result
        anchors = drawing_coordinates(drawing, points)
        x = Decimal(index)
        threshold = drawing_threshold(drawing, anchors, x, params["geometry_policy"])
        value = decimal(point["raw"].get(params["field"]))
        if value is None:
            raise ValueError("Exact selected raw OHLC value is unavailable")
        comparable = digest({"drawing": params["drawing_ref"], "scope": drawing["scope"], "source": data["comparable_identity"],
            "algorithm": result["facts"]["algorithm"], "extent": params["geometry_policy"], "field": params["field"], "rule_updated_at": rule["updated_at"]})
        current = {"t": point["t"], "raw": copy.deepcopy(point["raw"]), "value": str(value), "threshold": str(threshold),
            "residual": str(arithmetic.subtract(value, threshold)), "logical_index": str(x), "history_prefix_identity": point["history_prefix_identity"],
            "comparable_identity": comparable, "source": copy.deepcopy(source), "eligible": True,
            "eligibility_evidence": copy.deepcopy(point.get("eligibility_evidence")), "anchors": copy.deepcopy(anchors)}
        result["facts"].update(anchors=copy.deepcopy(anchors), observation=current)
        retained = next((row for row in points if old and row["t"] == old["t"]), None)
        if not old or old.get("comparable_identity") != comparable or not retained or retained["history_prefix_identity"] != old.get("history_prefix_identity"):
            result["reason"] = "Fresh crossing baseline; corrections/source changes require two comparable eligible observations"
            return result
        if point["t"] <= old["t"]:
            result["facts"]["observation"] = old
            result["reason"] = "Repeated or older observations cannot advance the baseline or re-arm a latch"
            return result
        before, residual = Decimal(old["residual"]), arithmetic.subtract(value, threshold)
        matched = before <= 0 < residual if params["comparison"] == "cross_above" else before >= 0 > residual
        result["facts"]["previous_observation"] = copy.deepcopy(old)
        clear = residual <= 0 if params["comparison"] == "cross_above" else residual >= 0
        result.update(state="triggered" if matched else "clear" if clear else "unavailable",
            reason="Two eligible comparable actual bars; only the opposite-side eligible residual re-arms, not absence of a new crossing")
    except (ValueError, KeyError, TypeError, ArithmeticError, AttributeError) as exc:
        result["reason"] = str(exc)
    return result


def indicator_key(symbol, params):
    return digest({"symbol": symbol, **{key: params.get(key) for key in ("context", "run_id", "history_key", "timeframe")}})


def evaluate_indicator(rule, context, previous):
    params = rule["parameters"]
    data = context.get("indicators", {}).get(indicator_key(rule["symbol"], params), {})
    series = next((s for s in data.get("series", []) if s["name"] == params["indicator"]), {})
    point = series.get("points", [{}])[-1] if series.get("points") else {}
    if data.get("selected_time"):
        point = next((p for p in series.get("points", []) if p["t"] == data["selected_time"]), {})
    source = {**data.get("source", {}), **{key: series.get(key) for key in
        ("derivation_identity", "comparable_identity", "initialization_history_sha256", "units")},
        "definition_sha256": digest(series.get("definition"))}
    old = (previous or {}).get("facts", {}).get("observation")
    result = {"state": "unavailable", "at": now(), "input_identity": digest({"source": source, "point": point}),
        "source_at": source.get("observed_at"), "indicator_source": source,
        "reason": data.get("error") or "Indicator inputs are not eligible",
        "facts": {"indicator": params["indicator"], "definition": series.get("definition"), "units": series.get("units"),
            "point": copy.deepcopy(point), "selection_time": data.get("selected_time"),
            "calculation_failure": series.get("calculation_failure"), "observation": old,
            "threshold": str(params["threshold"]), "comparison": params["comparison"]}}
    try:
        stamp = datetime.fromisoformat(source["observed_at"].replace("Z", "+00:00"))
        age = Decimal(str((datetime.now(UTC) - stamp).total_seconds()))
    except (KeyError, ValueError, TypeError, AttributeError):
        return result
    value = decimal(point.get("raw"))
    if not point.get("alert_eligible") or value is None or age < 0 or age > decimal(params["max_age_seconds"]):
        result["reason"] = "; ".join(point.get("reasons", [])) or "Missing, uninitialized, unfinished or stale indicator input"
        return result
    current = {"t": point["t"], "raw": point["raw"], "history_prefix_identity": point.get("history_prefix_identity"),
        "comparable_identity": series["comparable_identity"], "derivation_identity": series["derivation_identity"]}
    result["facts"]["observation"] = current
    comparison, threshold = params["comparison"], Decimal(str(params["threshold"]))
    if comparison.startswith("cross_"):
        retained = next((p for p in series["points"] if old and p["t"] == old["t"]), None)
        if (not old or old.get("comparable_identity") != series["comparable_identity"] or not retained
                or not old.get("history_prefix_identity") or retained.get("history_prefix_identity") != old["history_prefix_identity"]):
            result["reason"] = "Crossing baseline recorded; two comparable eligible observations are required after any input correction or replacement"
            return result
        if point["t"] <= old["t"]:
            result.update(state=previous["state"] if point["t"] == old["t"] else "unavailable",
                          reason="No newer eligible observation; repeated or older bars cannot create a crossing")
            return result
        before = decimal(old["raw"])
        matched = before <= threshold < value if comparison == "cross_above" else before >= threshold > value
        result["facts"]["previous_observation"] = old
    else:
        matched = value > threshold if comparison == "above" else value < threshold
    result.update(state="triggered" if matched else "clear", reason="Eligible indicator " + comparison + ": " + point["raw"] + " " + str(series["units"]))
    return result


def sync_memberships(saved, workspace, observed):
    """Called in the workspace writer transaction, including while monitoring is paused."""
    lists = {item["id"]: item["symbols"] for item in workspace["watchlists"]}
    for rule in saved["rules"].values():
        if rule.get("target", {}).get("mode") != "follow" or rule.get("removed"):
            continue
        wanted = set(lists.get(rule["target"]["watchlist_id"], []))
        members = rule["memberships"]
        current = {m["symbol"] for m in members.values() if m["status"] == "monitoring"}
        for member in members.values():
            if member["status"] == "monitoring" and member["symbol"] not in wanted:
                member.update(status="no_longer_monitored", removed_at=now())
        for identity, member in members.items():
            if member["status"] == "no_longer_monitored":
                state = observed["rule_states"].setdefault(rule["id"] + ":" + identity, {})
                state.update(rule_id=rule["id"], symbol=member["symbol"], membership_id=identity,
                             monitoring="no_longer_monitored", removed_at=member["removed_at"])
        for symbol in sorted(wanted - current):
            members[str(uuid4())] = {"symbol": symbol, "status": "monitoring", "added_at": now()}


def change(saved, request, universe, research, bindings=None, workspace=None, proposals=None):
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
        previous.update(active=action == "resume", removed=action == "remove", updated_at=stamp)
        if action in {"pause", "remove"} and not previous.get("gap_started_at"):
            previous["gap_started_at"] = stamp
        if action == "resume" and previous.get("gap_started_at"):
            previous.setdefault("gaps", []).append({"from": previous.pop("gap_started_at"), "to": stamp,
                "reason": "Rule paused; no backfill or continuous coverage is claimed"})
        previous["evaluation"] = {"state": "paused" if action != "resume" else "awaiting_observation", "at": stamp,
                                  "reason": "Monitoring gap while rule was inactive; no unseen interval is claimed evaluated"}
        saved["rule_history"].append({"action": action, "rule": copy.deepcopy(previous), "at": stamp})
        return saved
    if action != "save":
        raise ValueError("Unknown attention operation")
    conditions = request.get("atoms", [{key: request.get(key) for key in ("kind", "scope", "parameters")}])
    if not isinstance(conditions, list) or not 1 <= len(conditions) <= 16 or request.get("operator", "ALL") not in {"ALL", "ANY"}:
        raise ValueError("Choose ALL or ANY with 1 to 16 flat conditions")
    for condition in conditions:
        validate_atom(condition)
        if condition["kind"] == "drawing":
            params = condition["parameters"]
            ref = params["drawing_ref"]
            value = (workspace or {}).get("drawings", {}).get(ref["drawing_id"])
            if (not value or value.get("deleted") or value["kind"] not in {"horizontal-line", "trend-line"}
                    or value["revision"] != ref["revision"] or drawing_geometry(value) != ref["geometry_sha256"]
                    or value["scope"]["timeframe"] != params["timeframe"]
                    or value["scope"]["context"] != ("saved" if params["context"] == "research" else "current")):
                raise ValueError("Explicitly select/rebind the current saved numeric drawing revision and compatible history context")
            params["drawing"] = copy.deepcopy(value)
            validate_drawing_binding(params)
    conditions = [{key: copy.deepcopy(c[key]) for key in ("kind", "scope", "parameters")} for c in conditions]
    target = copy.deepcopy(request.get("target", {"mode": "symbol", "symbol": request.get("symbol")}))
    if not isinstance(target, dict):
        raise ValueError("Choose an explicit alert target")
    mode = target.get("mode")
    account = any(c["scope"] == "account" for c in conditions)
    policies = {c["parameters"]["proposal_id"] for c in conditions if c["kind"] == "policy_condition"}
    if account:
        if not all(c["scope"] == "account" and c["kind"] != "policy_condition" for c in conditions) or mode in {"snapshot", "follow"}:
            raise ValueError("Account conditions evaluate once globally and cannot mix with stock/proposal conditions")
        target, symbol = {"mode": "account"}, ""
    elif policies:
        proposal = (proposals or {}).get(next(iter(policies)))
        if len(policies) != 1 or not proposal or mode in {"snapshot", "follow"}:
            raise ValueError("Bind policy conditions to exactly one saved proposal, without a watchlist")
        symbol = proposal.get("symbol") or proposal.get("terms", {}).get("symbol")
        target = {"mode": "proposal", "proposal_id": proposal["id"], "symbol": symbol}
    elif mode in {"snapshot", "follow"}:
        listing = next((item for item in (workspace or {}).get("watchlists", []) if item["id"] == target.get("watchlist_id")), None)
        if listing is None:
            raise ValueError("Select a saved watchlist")
        target = {"mode": mode, "watchlist_id": listing["id"]}
        symbol = ""
    else:
        symbol = target.get("symbol")
        if mode != "symbol" or symbol not in universe:
            raise ValueError("Select a configured or owned symbol")
        target = {"mode": "symbol", "symbol": symbol}
    if any(c["kind"] == "drawing" and (mode != "symbol" or c["parameters"]["drawing"]["scope"]["symbol"] != symbol) for c in conditions):
        raise ValueError("A drawing alert binds exactly its saved drawing symbol, not a watchlist or another instrument")
    kind, scope, params = conditions[0]["kind"], conditions[0]["scope"], conditions[0]["parameters"]
    if type(request.get("active")) is not bool:
        raise ValueError("Choose active or paused explicitly")
    rule = {"id": identity, "name": text(request.get("name"), 100, "rule name"), "kind": kind, "scope": scope,
            "symbol": symbol, "parameters": copy.deepcopy(params), "active": request["active"], "removed": False,
            "revision": previous["revision"] + 1 if previous else 1, "updated_at": stamp,
            "evaluation": {"state": "awaiting_observation" if request["active"] else "paused", "at": stamp}, "active_occurrence_id": None}
    rule.update(atoms=conditions, operator=request.get("operator", "ALL"), target=target)
    if not rule["active"]:
        rule["gap_started_at"] = stamp
    if target["mode"] in {"snapshot", "follow"}:
        rule["memberships"] = {str(uuid4()): {"symbol": s, "status": "monitoring", "added_at": stamp} for s in listing["symbols"]}
    if not rule["name"]:
        raise ValueError("Name the rule")
    content = ("name", "atoms", "operator", "target")
    if previous and all(rule.get(key) == previous.get(key) for key in content):
        if previous["active"] != rule["active"]:
            return change(saved, {"action": "resume" if rule["active"] else "pause", "id": identity}, universe, research)
        return saved
    saved["rules"][identity] = rule
    saved["rule_history"].append({"action": "save", "at": stamp, "rule": copy.deepcopy(rule)})
    return saved


def evaluate_rule(rule, context, previous=None):
    if rule["kind"] == "drawing":
        return evaluate_drawing(rule, context, previous)
    if rule["kind"] == "indicator":
        return evaluate_indicator(rule, context, previous)
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
    source = evaluation.get("indicator_source") or context["sources"].get(rule["scope"], {}).get(rule["symbol"] if rule["scope"] != "account" else "account", {})
    retained = {key: copy.deepcopy(value) for key, value in source.items() if key in EVIDENCE_SOURCE_FIELDS}
    proposal = context["proposals"].get(rule["parameters"]["proposal_id"]) if rule["kind"] == "policy_condition" else None
    snapshot = None if proposal is None else {key: copy.deepcopy(proposal.get(key))
        for key in ("id", "revision", "policy_revision", "terms_sha256", "conditions_stale")}
    if snapshot is not None:
        snapshot["conditions"] = copy.deepcopy(proposal["impact"]["conditions"])
    reference = bool(retained.get("artifact") or retained.get("run_id") and retained.get("revision") is not None or snapshot)
    return {"version": "occurrence-evidence-v1", "evaluated_at": evaluation["at"], "store_generation": context.get("store_generation"),
            "rule": {key: copy.deepcopy(rule[key]) for key in ("id", "name", "revision", "kind", "scope", "symbol", "parameters", "active", "updated_at", "membership_id") if key in rule},
            "evaluation": copy.deepcopy(evaluation), "source": retained, "proposal": snapshot,
            "reference_status": "recorded_not_validated" if reference else "observation_only"}


def evaluate_conditions(rule, context, previous=None):
    results, evidence = [], []
    previous_atoms = previous.get("atoms", [previous]) if previous else []
    for index, atom in enumerate(atoms(rule)):
        bound = {**rule, **atom}
        result = evaluate_rule(bound, context, previous_atoms[index] if index < len(previous_atoms) else None)
        results.append(result)
        evidence.append(occurrence_evidence(bound, context, result))
    if "atoms" not in rule:
        return results[0], evidence[0]
    states = [result["state"] for result in results]
    operator = rule["operator"]
    state = ("clear" if "clear" in states else "triggered" if all(s == "triggered" for s in states) else "unavailable") if operator == "ALL" else (
        "triggered" if "triggered" in states else "clear" if all(s == "clear" for s in states) else "unavailable")
    result = {"state": state, "at": now(), "input_identity": digest([r["input_identity"] for r in results]),
        "reason": operator + " conditions: " + ", ".join(states), "facts": {"operator": operator}, "atoms": results}
    captured = occurrence_evidence(rule, context, result)
    captured["atoms"] = evidence
    captured["reference_status"] = "recorded_not_validated" if any(e["reference_status"] == "recorded_not_validated" for e in evidence) else "observation_only"
    captured["rule"].update(operator=operator, atoms=copy.deepcopy(rule["atoms"]), target=copy.deepcopy(rule["target"]))
    return result, captured


class AttentionMonitor:
    def __init__(self, database, context, lock, tick=None):
        self.database, self.context, self.lock = database, context, lock
        self.tick = tick
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
        rules = self.database.read("attention", DEFAULT)["data"]["rules"]
        context = self.context() if any(rule["active"] and not rule["removed"] for rule in rules.values()) else None
        def update(records):
            saved, observed = records["attention"], records["attention_observations"]
            for configured in saved["rules"].values():
                rule = configured
                if not rule["active"] or rule["removed"]:
                    continue
                members = rule.get("memberships", {"": {"symbol": rule["symbol"], "status": "monitoring"}})
                for membership, member in members.items():
                    key = rule["id"] + (":" + membership if membership else "")
                    prior = observed["rule_states"].get(key, {})
                    if member["status"] != "monitoring":
                        prior.update(rule_id=rule["id"], symbol=member["symbol"], membership_id=membership,
                            monitoring="no_longer_monitored", removed_at=member.get("removed_at"))
                        observed["rule_states"][key] = prior
                        continue
                    self.evaluate_member(rule, member["symbol"], membership, key, prior, observed, context)
            observed["monitor"].update(state="evaluating", last_evaluated_at=now())
            if context is not None:
                observed["monitor"]["universe_count"] = context["universe_count"]
        self.database.transact({"attention": DEFAULT, "attention_observations": OBSERVATIONS}, update)

    @staticmethod
    def evaluate_member(configured, symbol, membership, key, prior, observed, context, *, emit_occurrences=True, precomputed=None):
        rule = {**configured, "symbol": symbol, "membership_id": membership}
        if prior.get("rule_revision") != rule["revision"]:
            prior = ({"rule_revision": rule["revision"], "active_occurrence_id": prior.get("active_occurrence_id")} if any(a["kind"] == "drawing" for a in atoms(rule)) else
                     {**prior, "rule_revision": rule["revision"]} if rule.get("condition_identity")
                     and prior.get("condition_identity") == rule["condition_identity"] else
                     {"rule_revision": rule["revision"], "active_occurrence_id": None})
        if rule.get("condition_identity"):
            prior["condition_identity"] = rule["condition_identity"]
        prior.update(rule_id=rule["id"], symbol=symbol, membership_id=membership, monitoring="monitoring")
        result, evidence = precomputed if precomputed is not None else evaluate_conditions(rule, context, prior.get("evaluation"))
        previous = prior.get("evaluation", {})
        if previous.get("input_identity") == result["input_identity"] and previous.get("state") == result["state"]:
            return
        prior["evaluation"] = result
        if emit_occurrences and result["state"] == "triggered" and not prior.get("active_occurrence_id"):
            identity = str(uuid4())
            prior["active_occurrence_id"] = identity
            observed["occurrences"][identity] = {"id": identity, "rule_id": rule["id"], "rule_revision": rule["revision"],
                "symbol": rule["symbol"], "scope": rule["scope"], "name": rule["name"], "evaluation": copy.deepcopy(result),
                "evidence": evidence, "membership_id": membership,
                "created_at": now(), "unread": True, "acknowledged_at": None, "revision": 1}
        elif result["state"] == "clear":
            prior["active_occurrence_id"] = None
        observed["rule_states"][key] = prior

    def run(self):
        while not self.stopped.wait(5):
            try:
                if self.tick:
                    self.tick()  # Only queue opted-in due work; provider calls run on the data executor.
                with self.lock:
                    self.evaluate()
            except Exception:
                # The UI compares the last evaluation time to the service clock and shows the gap.
                continue

    def close(self):
        self.stopped.set()
