"""Dated, source-retained portfolio weight snapshots."""

import base64
import hashlib
import io
import json
import re
import threading
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4
from xml.etree import ElementTree as ET

from .approval_review import read_artifact

SOURCE_URL = "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx"
RECORD = "portfolio_weight_snapshots"
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _parse_spy(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        shared = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = ["".join(node.itertext()) for node in shared.findall("x:si", NS)]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sheet.findall(".//x:sheetData/x:row", NS):
            cells = {}
            for cell in row.findall("x:c", NS):
                column = re.match(r"[A-Z]+", cell.get("r", ""))
                value = cell.find("x:v", NS)
                if column is None or value is None:
                    continue
                cells[column.group()] = strings[int(value.text)] if cell.get("t") == "s" else value.text
            rows.append(cells)
    date_text = next((row.get("B", "") for row in rows if row.get("A") == "Holdings:"), "")
    match = re.search(r"(\d{1,2}-[A-Za-z]{3}-\d{4})", date_text)
    if not match:
        raise ValueError("State Street holdings date is missing")
    as_of = datetime.strptime(match.group(1), "%d-%b-%Y").date().isoformat()
    entries = []
    excluded = []
    active = False
    for row in rows:
        if row.get("A") == "Name" and row.get("B") == "Ticker":
            active = True
            continue
        if not active or not row.get("A") or not row.get("B") or not row.get("E"):
            continue
        try:
            weight = Decimal(row["E"]) / Decimal(100)
        except InvalidOperation:
            continue
        if not weight.is_finite() or weight < 0:
            continue
        entry = {"symbol": row["B"].strip().upper(), "weight": str(weight),
                 "cusip": row.get("C", ""), "name": row["A"]}
        if entry["symbol"] == "USD" or entry["symbol"].endswith(".WS"):
            excluded.append({**entry, "reason": "cash" if entry["symbol"] == "USD" else "warrant"})
        else:
            entries.append(entry)
    if len(entries) < 400:
        raise ValueError("State Street holdings are incomplete")
    if len({entry["symbol"] for entry in entries}) != len(entries):
        raise ValueError("State Street holdings contain duplicate symbols")
    total = sum(Decimal(entry["weight"]) for entry in entries)
    if total > 1 or total < Decimal("0.95"):
        raise ValueError("State Street equity weights do not reconcile")
    return as_of, entries, excluded, str(1 - total)


class PortfolioWeights:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self._import_packaged_snapshots()

    def _import_packaged_snapshots(self):
        """Retain packaged public source data in the same cache as downloads."""
        directory = Path(__file__).with_name("portfolio_weight_data")
        for path in sorted(directory.glob("*.json")):
            raw = path.read_bytes()
            asset_hash = hashlib.sha256(raw).hexdigest()
            data = self.store.database.read(RECORD, {"snapshots": [], "error": None})["data"]
            if any(item.get("asset_sha256") == asset_hash for item in data["snapshots"]):
                continue
            asset = json.loads(raw)
            datetime.strptime(asset["as_of"], "%Y-%m-%d")
            if not all(asset.get(key) for key in ("provider", "source_url", "source_sha256", "entries")):
                raise ValueError(f"Invalid packaged holdings snapshot: {path.name}")
            entries = asset["entries"]
            unresolved = asset.get("unresolved", [])
            symbols = set()
            total = Decimal(0)
            for entry in entries:
                symbol = entry.get("symbol")
                weight = Decimal(entry["weight"])
                if not symbol or symbol in symbols or not weight.is_finite() or weight < 0:
                    raise ValueError(f"Invalid packaged holdings entry: {path.name}")
                symbols.add(symbol)
                total += weight
            cash = Decimal(asset["cash_weight"])
            if not cash.is_finite() or cash < 0 or total + cash != Decimal(1):
                raise ValueError(f"Packaged holdings weights do not reconcile: {path.name}")
            identity = str(uuid4())
            source = self.store._write_json_artifact(identity, "holdings-packaged-source", asset)
            snapshot = {**asset, "id": identity, "source_artifact": source, "asset_sha256": asset_hash,
                        "unresolved": unresolved}
            if asset.get("source_file"):
                source_path = (directory / asset["source_file"]).resolve()
                if not source_path.is_relative_to(directory.resolve()):
                    raise ValueError("Invalid packaged source path")
                source_raw = source_path.read_bytes()
                if hashlib.sha256(source_raw).hexdigest() != asset["source_sha256"]:
                    raise ValueError("Packaged holdings source changed")
                snapshot["original_source_artifact"] = self.store._write_json_artifact(
                    identity, "holdings-original-source", {"encoding": "base64", "content": base64.b64encode(source_raw).decode("ascii")})
            artifact = self.store._write_json_artifact(identity, "holdings-snapshot", snapshot)
            metadata = {k: snapshot[k] for k in ("id", "provider", "as_of", "source_url", "source_sha256", "asset_sha256")}
            metadata["artifact"] = artifact
            def save(records):
                items = records[RECORD]["snapshots"]
                if not any(item.get("asset_sha256") == asset_hash for item in items):
                    items.append(metadata)
            self.store.database.transact({RECORD: {"snapshots": [], "error": None}}, save)

    def state(self, symbols=None, as_of=None):
        data = self.store.database.read(RECORD, {"snapshots": [], "error": None})["data"]
        snapshots = data.get("snapshots", [])
        eligible = [item for item in snapshots if not as_of or item["as_of"] <= as_of]
        selected = max(enumerate(eligible), key=lambda item: (item[1]["as_of"], item[0]))[1] if eligible else None
        snapshot = read_artifact(self.store.directory, selected["artifact"]) if selected else None
        error = data.get("error")
        if selected and snapshot is None:
            error = "Saved holdings snapshot is missing or changed"
        known = {entry["symbol"] for entry in snapshot["entries"]} if snapshot else set()
        missing = [symbol for symbol in (symbols or []) if symbol.upper() not in known]
        return {"status": "error" if error else ("partial" if snapshot and snapshot.get("unresolved") else ("ready" if snapshot else "unavailable")),
                "snapshot": snapshot, "available_snapshots": [{k: v for k, v in item.items() if k != "artifact"} for item in snapshots],
                "missing": missing, "error": error}

    def refresh(self):
        with self.lock:
            try:
                request = Request(SOURCE_URL, headers={"User-Agent": "TradingAgents portfolio weights"})
                with urlopen(request, timeout=45) as response:
                    raw = response.read()
                as_of, entries, excluded, cash_weight = _parse_spy(raw)
                digest = hashlib.sha256(raw).hexdigest()
                identity = str(uuid4())
                snapshot = {"id": identity, "provider": "State Street SPY", "as_of": as_of,
                            "source_url": SOURCE_URL, "source_sha256": digest, "entries": entries,
                            "excluded": excluded, "cash_weight": cash_weight}
                source = self.store._write_json_artifact(identity, "holdings-source", {"encoding": "base64", "content": base64.b64encode(raw).decode("ascii")})
                snapshot["source_artifact"] = source
                artifact = self.store._write_json_artifact(identity, "holdings-snapshot", snapshot)
                def save(records):
                    data = records[RECORD]
                    if not any(item["source_sha256"] == digest for item in data["snapshots"]):
                        data["snapshots"].append({k: snapshot[k] for k in ("id", "provider", "as_of", "source_url", "source_sha256")} | {"artifact": artifact})
                    data["error"] = None
                self.store.database.transact({RECORD: {"snapshots": [], "error": None}}, save)
            except Exception as exc:
                def fail(records):
                    records[RECORD]["error"] = "Holdings refresh failed: " + str(exc)
                self.store.database.transact({RECORD: {"snapshots": [], "error": None}}, fail)
            return self.state()
