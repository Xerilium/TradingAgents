"""Investor workspace records, independent of broker and research journals."""

import copy
import re
from datetime import UTC, datetime
from uuid import uuid4


DEFAULT = {"watchlists": [{"id": "shortlist", "name": "Shortlist", "symbols": []}],
           "preferences": {}, "notes": {}, "browser_imports": []}


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
               "holdingsSort", "holdingsFilter", "holdingsDescending"}
    if set(value) - allowed:
        raise ValueError("Unknown workspace preference")
    for key, item in value.items():
        if key == "columns":
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


def change(saved, request):
    patch = request.get("changes", {})
    if not isinstance(patch, dict) or set(patch) - {"watchlists", "preferences", "notes", "browser_import"}:
        raise ValueError("Unknown workspace change")
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
