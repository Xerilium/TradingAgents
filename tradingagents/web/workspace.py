"""Investor workspace records, independent of broker and research journals."""

import copy
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from math import isfinite
from pathlib import PurePosixPath
from uuid import uuid4


DEFAULT = {"watchlists": [{"id": "shortlist", "name": "Shortlist", "symbols": []}],
           "preferences": {}, "notes": {}, "browser_imports": [], "saved_screens": [], "drawings": {}, "drawing_history": [],
           "chart_definitions": {}, "chart_definition_history": []}


def chart_definition_dependencies(saved, references):
    from uuid import UUID

    from .investor import digest
    if not isinstance(references, list) or len(references) > 100:
        raise ValueError("Choose at most 100 exact saved chart dependencies")
    history = saved.get("chart_definition_history", [])
    result, visiting, visited = [], set(), set()
    def visit(ref):
        if (not isinstance(ref, dict) or set(ref) != {"id", "revision", "sha256"}
                or not isinstance(ref["id"], str) or str(UUID(ref["id"])) != ref["id"]
                or type(ref["revision"]) is not int or ref["revision"] < 1
                or not re.fullmatch(r"[0-9a-f]{64}", str(ref["sha256"]))):
            raise ValueError("Chart dependencies require exact id, revision and hash")
        key = (ref["id"], ref["revision"], ref["sha256"])
        if key in visiting:
            raise ValueError("Chart definition dependencies contain a cycle")
        if key in visited:
            return
        rows = [row for row in history if row["definition"]["id"] == ref["id"] and row["definition"]["revision"] == ref["revision"]]
        if len(rows) != 1 or digest(rows[0]["definition"]) != ref["sha256"]:
            raise ValueError("Exact chart dependency revision is unavailable or changed")
        visiting.add(key)
        for child in rows[0]["dependencies"]:
            visit(child)
        visiting.remove(key)
        visited.add(key)
        result.append(copy.deepcopy(rows[0]["definition"]))
    for reference in references:
        visit(reference)
    return result


def validate_chart_definitions(saved):
    from .evaluation import validate_chart_definition
    from .investor import digest
    current, history = saved.get("chart_definitions", {}), saved.get("chart_definition_history", [])
    if not isinstance(current, dict) or not isinstance(history, list):
        raise ValueError("Invalid saved chart definition registry")
    latest, revisions = {}, {}
    for row in history:
        if not isinstance(row, dict) or set(row) != {"definition", "sha256", "dependencies"}:
            raise ValueError("Invalid immutable chart definition revision")
        definition = row["definition"]
        dependencies = chart_definition_dependencies(saved, row["dependencies"])
        canonical = validate_chart_definition(definition, dependencies)
        key = canonical["id"]
        if canonical != definition or row["sha256"] != digest(definition) or canonical["revision"] != revisions.get(key, 0) + 1:
            raise ValueError("Chart definition hash, schema or revision lineage differs")
        revisions[key] = canonical["revision"]
        latest[key] = row
    if current != latest:
        raise ValueError("Current chart definitions differ from immutable revision history")


def save_chart_definition(saved, request):
    from .evaluation import validate_chart_definition
    from .investor import digest
    supplied = request.get("definition")
    if not isinstance(supplied, dict):
        raise ValueError("Choose a typed chart definition")
    identity = supplied.get("id") or str(uuid4())
    previous = saved.setdefault("chart_definitions", {}).get(identity)
    if supplied.get("revision", 0) != (previous["definition"]["revision"] if previous else 0):
        raise ValueError("Chart definition revision changed; reopen the saved definition")
    references = copy.deepcopy(request.get("dependencies", []))
    dependencies = chart_definition_dependencies(saved, references)
    definition = validate_chart_definition({**supplied, "id": identity,
        "revision": (previous["definition"]["revision"] if previous else 0) + 1,
        "updated_at": datetime.now(UTC).isoformat()}, dependencies)
    row = {"definition": definition, "sha256": digest(definition), "dependencies": references}
    saved["chart_definitions"][identity] = row
    saved.setdefault("chart_definition_history", []).append(copy.deepcopy(row))
    return identity


def import_chart_definitions(saved, bundle):
    if not isinstance(bundle, dict) or set(bundle) != {"version", "definitions"} or bundle["version"] != "chart-definitions-v1" or not isinstance(bundle["definitions"], list):
        raise ValueError("Import an exact versioned chart definition bundle")
    if not 1 <= len(bundle["definitions"]) <= 1000:
        raise ValueError("Import between 1 and 1000 immutable chart revisions")
    candidate = copy.deepcopy(saved)
    for row in bundle["definitions"]:
        definition = row.get("definition", {}) if isinstance(row, dict) else {}
        existing = [item for item in candidate.setdefault("chart_definition_history", []) if
            item["definition"]["id"] == definition.get("id") and item["definition"]["revision"] == definition.get("revision")]
        if existing:
            if existing != [row]:
                raise ValueError("Imported chart revision conflicts with retained evidence")
            continue
        candidate["chart_definition_history"].append(copy.deepcopy(row))
    candidate["chart_definition_history"].sort(key=lambda row: (row["definition"]["id"], row["definition"]["revision"]))
    candidate["chart_definitions"] = {row["definition"]["id"]: row for row in candidate["chart_definition_history"]}
    validate_chart_definitions(candidate)
    saved["chart_definitions"], saved["chart_definition_history"] = candidate["chart_definitions"], candidate["chart_definition_history"]


def text(value, maximum, label):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"Invalid {label} (maximum {maximum} characters)")
    return value.strip()


def lists(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 100:
        raise ValueError("Save between 1 and 100 watchlists")
    result, ids = [], set()
    for item in value:
        identity = text(item.get("id"), 100, "watchlist id")
        name = text(item.get("name"), 60, "watchlist name")
        symbols = item.get("symbols")
        if not identity or identity in ids or not name or not isinstance(symbols, list) or len(symbols) > 5000:
            raise ValueError("Invalid watchlist")
        if any(not isinstance(s, str) or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", s) for s in symbols):
            raise ValueError("Invalid watchlist symbol")
        ids.add(identity)
        result.append({"id": identity, "name": name, "symbols": sorted(set(symbols))})
    return result


def preferences(value):
    if not isinstance(value, dict):
        raise ValueError("Preferences must be an object")
    allowed = {"columns", "search", "view", "sortKey", "descending", "minMove", "activeListId",
               "targetListId", "portfolioView", "symbol", "reportKey", "runId", "holdingsQuery",
               "holdingsSort", "holdingsFilter", "holdingsDescending", "discoveryObservationId", "discoverySymbol", "chartView"}
    if set(value) - allowed:
        raise ValueError("Unknown workspace preference")
    for key, item in value.items():
        if key == "chartView":
            from .market_history import TIMEFRAMES
            if (not isinstance(item, dict) or set(item) - {"symbol", "context", "timeframe", "cacheKey", "compareSymbol", "compareCacheKey", "anchor", "selectedTime", "range", "logicalRange", "replay", "analysis"}
                    or not item.get("symbol") or item.get("context") not in {"saved", "current"} or item.get("timeframe") not in TIMEFRAMES
                    or item["context"] == "saved" and item["timeframe"] != "1Day"):
                raise ValueError("Invalid chart source context or interval")
            if item.get("analysis") is not None:
                from uuid import UUID
                analysis = item["analysis"]
                if (not isinstance(analysis, dict) or set(analysis) != {"calculation_id", "result_sha256"}
                        or str(UUID(analysis.get("calculation_id", ""))) != analysis["calculation_id"]
                        or not re.fullmatch(r"[0-9a-f]{64}", str(analysis.get("result_sha256", "")))):
                    raise ValueError("Select an exact retained chart calculation")
            for field in ("symbol", "compareSymbol"):
                symbol = item.get(field, "")
                if not isinstance(symbol, str) or symbol and not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", symbol):
                    raise ValueError("Invalid chart symbol")
            if item.get("compareSymbol") == item["symbol"]:
                raise ValueError("Choose a different comparison symbol")
            for field in ("cacheKey", "compareCacheKey"):
                text(item.get(field, ""), 300, field)
            if item.get("range", "all") not in {"all", "7", "30", "90", "180"}:
                raise ValueError("Invalid retained chart range")
            for field in ("anchor", "selectedTime"):
                point = item.get(field)
                if point is not None:
                    if item["timeframe"] == "1Day":
                        if not isinstance(point, str) or datetime.strptime(point, "%Y-%m-%d").strftime("%Y-%m-%d") != point:
                            raise ValueError("Invalid daily chart business day")
                    elif type(point) not in (int, float) or not isfinite(point) or point != int(point) or not 0 <= point <= 253402300799:
                        raise ValueError("Invalid intraday UTC-second chart time")
            span = item.get("logicalRange")
            if span is not None and (not isinstance(span, dict) or set(span) != {"from", "to"}
                    or any(type(value) not in (int, float) or not isfinite(value) for value in span.values()) or span["from"] > span["to"]):
                raise ValueError("Invalid chart viewport")
            replay = item.get("replay")
            if replay is not None:
                if not isinstance(replay, dict) or set(replay) - {"pin", "comparison_pin", "cutoff", "speed", "anchor"}:
                    raise ValueError("Invalid retained replay preferences")
                pin = source_pin(replay.get("pin"))
                if any(pin[field] != item[field] for field in ("symbol", "context", "timeframe")):
                    raise ValueError("Replay pin differs from the selected chart")
                chart_time(replay.get("cutoff"), pin["timeframe"])
                if replay.get("anchor") is not None:
                    chart_time(replay["anchor"], pin["timeframe"])
                if type(replay.get("speed")) not in (int, float) or replay["speed"] not in {.25, .5, 1, 2, 4, 8}:
                    raise ValueError("Unsupported replay speed")
                if replay.get("comparison_pin") is not None:
                    other = source_pin(replay["comparison_pin"])
                    if other["symbol"] == pin["symbol"] or other["timeframe"] != pin["timeframe"] or other["context"] != pin["context"]:
                        raise ValueError("Replay comparison needs distinct matching retained sources")
        elif key == "discoveryObservationId":
            from uuid import UUID
            if item != "" and (not isinstance(item, str) or str(UUID(item)) != item):
                raise ValueError("Invalid selected discovery observation")
        elif key == "discoverySymbol":
            if item != "" and (not isinstance(item, str) or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", item)):
                raise ValueError("Invalid selected discovery symbol")
        elif key == "columns":
            if not isinstance(item, dict) or set(item) != {"order", "visible"} or any(
                    not isinstance(v, list) or len(v) > 30 or any(not isinstance(s, str) or len(s) > 40 for s in v)
                    for v in item.values()):
                raise ValueError("Invalid column preferences")
        elif key in {"descending", "holdingsDescending"}:
            if type(item) is not bool:
                raise ValueError("Invalid sort direction")
        elif key == "minMove":
            if item not in (0, .5, 1, 2, 3, 5):
                raise ValueError("Invalid minimum movement")
        else:
            text(item, 300, key)
    return copy.deepcopy(value)


def chart_time(value, timeframe):
    if timeframe == "1Day":
        if not isinstance(value, str) or datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") != value:
            raise ValueError("Invalid retained daily bar time")
    elif type(value) not in (int, float) or not isfinite(value) or value != int(value) or not 0 <= value <= 253402300799:
        raise ValueError("Invalid retained intraday bar time")
    return value


def source_pin(value):
    from uuid import UUID

    from .market_history import TIMEFRAMES
    if (not isinstance(value, dict) or set(value) - {"context", "symbol", "timeframe", "cache_key", "run_id", "artifact", "derivation_identity"}
            or value.get("context") not in {"current", "saved"} or value.get("timeframe") not in TIMEFRAMES
            or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", str(value.get("symbol", "")))):
        raise ValueError("Invalid exact chart source pin")
    ref = value.get("artifact")
    if (not isinstance(ref, dict) or set(ref) != {"path", "sha256"} or not isinstance(ref.get("path"), str)
            or PurePosixPath(ref["path"]).is_absolute() or ".." in PurePosixPath(ref["path"]).parts
            or "\\" in ref["path"] or not ref["path"] or not re.fullmatch(r"[0-9a-f]{64}", str(ref.get("sha256", "")))):
        raise ValueError("Invalid retained chart artifact reference")
    if value["context"] == "saved":
        if value["timeframe"] != "1Day" or str(UUID(value.get("run_id", ""))) != value.get("run_id") or value.get("cache_key"):
            raise ValueError("Saved replay requires an exact daily research run")
    elif not text(value.get("cache_key"), 300, "retained chart key") or value.get("run_id"):
        raise ValueError("Current replay requires an exact retained cache")
    if value.get("derivation_identity") is not None and not re.fullmatch(r"[0-9a-f]{64}", str(value["derivation_identity"])):
        raise ValueError("Invalid pinned calculation identity")
    return copy.deepcopy(value)


def saved_screens(value):
    from .market_discovery import criteria
    screens = value
    if not isinstance(screens, list) or len(screens) > 100:
        raise ValueError("Save at most 100 named screens")
    normalized, ids = [], set()
    for screen in screens:
        if not isinstance(screen, dict):
            raise ValueError("Each saved screen must be an object")
        identity, name = text(screen.get("id"), 100, "screen id"), text(screen.get("name"), 60, "screen name")
        if not identity or not name or identity in ids:
            raise ValueError("Each saved screen needs a unique id and name")
        ids.add(identity)
        normalized.append({"id": identity, "name": name, "criteria": criteria(screen.get("criteria"))})
    return normalized


def drawing(value):
    """Validate annotation intent; observed evidence is checked by the service."""
    from uuid import UUID

    from .market_history import TIMEFRAMES
    if not isinstance(value, dict) or set(value) - {"id", "revision", "kind", "scope", "points", "text", "style", "deleted"}:
        raise ValueError("Invalid drawing fields")
    if not isinstance(value.get("id"), str) or str(UUID(value["id"])) != value["id"] or type(value.get("revision")) is not int or value["revision"] < 0:
        raise ValueError("Invalid drawing identity or revision")
    scope = value.get("scope")
    fields = {"symbol", "timeframe", "context", "instrument_id", "currency", "unit", "provider", "feed", "adjustment", "session"}
    if (not isinstance(scope, dict) or set(scope) != fields or scope["timeframe"] not in TIMEFRAMES
            or scope["context"] not in {"saved", "current"} or scope["unit"] != "price"
            or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", str(scope["symbol"]))):
        raise ValueError("Invalid drawing source scope")
    for key in fields - {"symbol", "timeframe", "context", "unit"}:
        if scope[key] is not None and not text(scope[key], 300, "drawing " + key):
            raise ValueError("Empty drawing compatibility evidence")
    count = {"horizontal-line": 1, "trend-line": 2, "text": 1}.get(value.get("kind"))
    points = value.get("points")
    if count is None or not isinstance(points, list) or len(points) != count or type(value.get("deleted", False)) is not bool:
        raise ValueError("Invalid drawing kind or anchors")
    for point in points:
        if not isinstance(point, dict):
            raise ValueError("Invalid drawing anchor")
        basis = point.get("basis")
        allowed = {"basis", "price", "origin_time", "offset"} if basis == "logical_offset" else {"basis", "price", "time"}
        if basis == "observed":
            allowed |= {"source_pin", "value_kind"}
        if basis not in {"observed", "manual_time", "logical_offset"} or set(point) != allowed:
            raise ValueError("Invalid drawing anchor basis")
        price = point.get("price")
        try:
            if (not isinstance(price, str) or len(price) > 100 or not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", price)
                    or not Decimal(price).is_finite() or not isfinite(float(price))):
                raise ValueError("Drawing price must be a finite decimal string")
        except (InvalidOperation, OverflowError):
            raise ValueError("Invalid drawing price") from None
        chart_time(point["origin_time" if basis == "logical_offset" else "time"], scope["timeframe"])
        if basis == "logical_offset" and (type(point["offset"]) not in (int, float) or not isfinite(point["offset"]) or abs(point["offset"]) > 1000000):
            raise ValueError("Invalid projected logical bar offset")
        if basis == "observed":
            pin = source_pin(point["source_pin"])
            if any(pin[key] != scope[key] for key in ("symbol", "timeframe", "context")) or point["value_kind"] not in {"o", "h", "l", "c"}:
                raise ValueError("Observed anchor source differs from the drawing")
    style = value.get("style")
    if (not isinstance(style, dict) or set(style) != {"color", "width"}
            or not re.fullmatch(r"#[0-9a-fA-F]{6}", str(style.get("color"))) or type(style.get("width")) is not int or not 1 <= style["width"] <= 4):
        raise ValueError("Invalid drawing style")
    text(value.get("text"), 2000, "drawing thesis")
    return copy.deepcopy(value)


def validate_drawings(saved):
    current, history = saved.get("drawings", {}), saved.get("drawing_history", [])
    if not isinstance(current, dict) or not isinstance(history, list):
        raise ValueError("Invalid saved drawing records")
    latest = {}
    for entry in history:
        if not isinstance(entry, dict) or set(entry) != {"drawing", "saved_at"}:
            raise ValueError("Invalid drawing revision history")
        value = drawing(entry["drawing"])
        prior = latest.get(value["id"])
        if value["revision"] != (prior["revision"] + 1 if prior else 1) or prior and prior.get("deleted"):
            raise ValueError("Drawing revision history is incomplete or conflicting")
        if not isinstance(entry["saved_at"], str) or datetime.fromisoformat(entry["saved_at"]).tzinfo is None:
            raise ValueError("Drawing revision time is unavailable")
        latest[value["id"]] = value
    if current != latest:
        raise ValueError("Current drawings differ from their retained revision history")


def change(saved, request):
    patch = request.get("changes", {})
    if not isinstance(patch, dict) or set(patch) - {"watchlists", "preferences", "notes", "browser_import", "saved_screens", "drawings"}:
        raise ValueError("Unknown workspace change")
    if "drawings" in patch:
        updates = patch["drawings"]
        if not isinstance(updates, dict) or not 1 <= len(updates) <= 100:
            raise ValueError("Save between 1 and 100 drawing changes")
        checked = {identity: drawing(value) for identity, value in updates.items()}
        current = saved.setdefault("drawings", {})
        for identity, value in checked.items():
            prior = current.get(identity)
            if identity != value["id"] or value["revision"] != (prior["revision"] if prior else 0) or prior and prior.get("deleted"):
                raise ValueError("Drawing revision changed; reopen the saved drawing before editing")
        for identity, value in checked.items():
            value["revision"] += 1
            current[identity] = value
            saved.setdefault("drawing_history", []).append({"drawing": copy.deepcopy(value), "saved_at": datetime.now(UTC).isoformat()})
    if "saved_screens" in patch:
        saved["saved_screens"] = saved_screens(patch["saved_screens"])
    if "watchlists" in patch:
        saved["watchlists"] = lists(patch["watchlists"])
    if "preferences" in patch:
        saved["preferences"].update(preferences(patch["preferences"]))
    for symbol, note in patch.get("notes", {}).items():
        if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", symbol):
            raise ValueError("Invalid note symbol")
        saved["notes"][symbol] = {"symbol": symbol, "text": text(note.get("text"), 20000, "note"),
                                  "updated_at": datetime.now(UTC).isoformat()}
    imported = patch.get("browser_import")
    if imported:
        identity = text(imported.get("id"), 100, "import id")
        if identity not in saved["browser_imports"]:
            names = {item["name"] for item in saved["watchlists"]}
            for item in lists(imported["watchlists"]):
                name, suffix = item["name"], 1
                while name in names:
                    suffix += 1
                    name = item["name"][:45] + f" (import {suffix})"
                names.add(name)
                saved["watchlists"].append({**item, "id": str(uuid4()), "name": name})
            skipped = []
            for key, value in preferences(imported.get("preferences", {})).items():
                if key in saved["preferences"]:
                    skipped.append(key)
                else:
                    saved["preferences"][key] = value
            saved["browser_imports"].append(identity)
            saved["last_import"] = {"id": identity, "skipped_preferences": skipped,
                                    "updated_at": datetime.now(UTC).isoformat()}
    return saved
