"""Paths for retained daily prices in the shared research folder."""

import os
import re
from pathlib import Path


SHARED_RESEARCH = Path("D:/src/printer-data/maenifold/memory/research")
SHARED_HISTORY = re.compile(
    r"reports/[0-9a-f-]{36}/shared-iex-history-([A-Z0-9][A-Z0-9.-]{0,31})"
    r"-(\d{4})-(\d{2})-(\d{2})-([0-9a-f-]{36})\.json"
)


def shared_history_path(relative):
    match = SHARED_HISTORY.fullmatch(relative) if isinstance(relative, str) else None
    if match is None or os.name != "nt":
        return None
    symbol, year, month, day, identity = match.groups()
    root = SHARED_RESEARCH.resolve()
    path = root / symbol / year / month / day / f"iex-history-cache-{identity}.json"
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
