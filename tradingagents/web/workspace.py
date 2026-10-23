"""Investor workspace records, independent of broker and research journals."""

import copy
import re
from datetime import UTC, datetime
from math import isfinite
from uuid import uuid4


DEFAULT = {"watchlists": [{"id": "shortlist", "name": "Shortlist", "symbols": []}],
           "preferences": {}, "notes": {}, "browser_imports": [], "saved_screens": []}


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
            if (not isinstance(item, dict) or set(item) - {"symbol", "context", "timeframe", "cacheKey", "compareSymbol", "compareCacheKey", "anchor", "selectedTime", "range", "logicalRange"}
                    or not item.get("symbol") or item.get("context") not in {"saved", "current"} or item.get("timeframe") not in TIMEFRAMES
                    or item["context"] == "saved" and item["timeframe"] != "1Day"):
                raise ValueError("Invalid chart source context or interval")
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


def change(saved, request):
    patch = request.get("changes", {})
    if not isinstance(patch, dict) or set(patch) - {"watchlists", "preferences", "notes", "browser_import", "saved_screens"}:
        raise ValueError("Unknown workspace change")
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
