"""Dated, source-retained portfolio weight snapshots."""

import base64
import hashlib
import io
import re
import threading
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
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
        entries.append({"symbol": row["B"].strip().upper(), "weight": str(weight),
                        "cusip": row.get("C", ""), "name": row["A"]})
    if len(entries) < 400:
        raise ValueError("State Street holdings are incomplete")
    return as_of, entries


class PortfolioWeights:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()

    def state(self, symbols=None, as_of=None):
        data = self.store.database.read(RECORD, {"snapshots": [], "error": None})["data"]
        snapshots = data.get("snapshots", [])
        eligible = [item for item in snapshots if not as_of or item["as_of"] <= as_of]
        selected = max(eligible, key=lambda item: (item["as_of"], item["id"])) if eligible else None
        snapshot = read_artifact(self.store.directory, selected["artifact"]) if selected else None
        error = data.get("error")
        if selected and snapshot is None:
            error = "Saved holdings snapshot is missing or changed"
        known = {entry["symbol"] for entry in snapshot["entries"]} if snapshot else set()
        missing = [symbol for symbol in (symbols or []) if symbol.upper() not in known]
        return {"status": "error" if error else ("ready" if snapshot else "unavailable"),
                "snapshot": snapshot, "available_snapshots": [{k: v for k, v in item.items() if k != "artifact"} for item in snapshots],
                "missing": missing, "error": error}

    def refresh(self):
        with self.lock:
            try:
                request = Request(SOURCE_URL, headers={"User-Agent": "TradingAgents portfolio weights"})
                with urlopen(request, timeout=45) as response:
                    raw = response.read()
                as_of, entries = _parse_spy(raw)
                digest = hashlib.sha256(raw).hexdigest()
                identity = str(uuid4())
                snapshot = {"id": identity, "provider": "State Street SPY", "as_of": as_of,
                            "source_url": SOURCE_URL, "source_sha256": digest, "entries": entries}
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
