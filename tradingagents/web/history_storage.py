"""Paths for retained daily prices in the shared research folder."""

import hashlib
import json
import os
import re
from pathlib import Path


SHARED_RESEARCH = Path("D:/src/printer-data/maenifold/memory/research")
SHARED_HISTORY = re.compile(
    r"reports/[0-9a-f-]{36}/shared-iex-history-([A-Z0-9][A-Z0-9.-]{0,31})"
    r"-(series|[0-9]{4}-[0-9]{2}(?:-[0-9]{2})?)-([0-9a-f-]{36})\.json"
)


def shared_history_path(relative):
    match = SHARED_HISTORY.fullmatch(relative) if isinstance(relative, str) else None
    if match is None or os.name != "nt":
        return None
    symbol, period, identity = match.groups()
    root = SHARED_RESEARCH.resolve()
    folder = root / symbol
    if period != "series":
        folder = folder.joinpath(*period.split("-"))
    path = folder / f"iex-history-cache-{identity}.json"
    if not path.resolve().is_relative_to(root):
        raise ValueError("Daily price file escapes the shared research folder")
    return path


def artifact_path(root, relative, *, allow_shared=True):
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Evidence file escapes its storage folder")
    if allow_shared and not path.exists():
        return shared_history_path(relative) or path
    return path


def load_daily_bars(root, result):
    if not isinstance(result, dict) or "daily_bar_artifacts" not in result:
        return result
    bars = []
    for relative, expected_hash in result["daily_bar_artifacts"]:
        payload = artifact_path(root, relative).read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected_hash:
            raise ValueError("Daily price file hash differs")
        daily = json.loads(payload)
        if any(daily[field] != result[field] for field in ("symbol", "provider", "feed", "timeframe", "adjustment")):
            raise ValueError("Daily price file does not match its history receipt")
        bars.append(daily["bar"])
    return {**result, "bars": bars}
