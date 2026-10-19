"""Read recorded market inputs. Research prose never supplies chart prices."""

import csv
import hashlib
import io
import json
import math
import re
import struct
from datetime import datetime
from zoneinfo import ZoneInfo



def recorded_market(root, run, symbol):
    indicators, candidates, problems = [], [], []
    for attempt in run.get("source_evidence", {}).get("attempts", []):
        args, artifact = attempt.get("arguments", {}), attempt.get("artifact", {})
        if args.get("symbol", args.get("ticker")) != symbol or not artifact:
            continue
        operation = attempt.get("operation")
        if operation not in {"get_stock_data", "get_indicators", "ohlcv_history", "ohlcv_cache_read"}:
            continue
        path = (root / artifact["path"]).resolve()
        if not path.is_relative_to((root / "reports" / run["id"]).resolve()):
            continue
        try:
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != artifact["sha256"]:
                raise ValueError("Recorded market artifact checksum differs")
            source = {**artifact, "captured_at": attempt.get("ended_at"), "vendor": attempt.get("vendor"),
                      "adjustment": args.get("adjustment"), "symbol_mapping_asof": args.get("asof")}
            if operation == "get_indicators" and artifact["format"] == "utf-8-text":
                text = payload.decode("utf-8")
                heading = re.search(r"## (\w+) values from (\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})", text)
                points = [{"t": d, "value": float(v), "raw": v} for d, v in re.findall(
                    r"(?m)^(\d{4}-\d{2}-\d{2}): (-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*$", text)]
                if heading and points:
                    indicators.append({"name": heading[1], "window_start": heading[2], "window_end": heading[3],
                        "points": points, "source": source})
            elif operation == "get_stock_data" and artifact["format"] == "utf-8-text":
                rows = csv.DictReader(io.StringIO("\n".join(line for line in payload.decode("utf-8").splitlines()
                                                            if line and not line.startswith("#"))))
                bars = [{"t": row["Date"][:10], "raw": {k: row[c] for k, c in
                    (("o", "Open"), ("h", "High"), ("l", "Low"), ("c", "Close"), ("v", "Volume"))}, **{k: float(row[c]) for k, c in
                    (("o", "Open"), ("h", "High"), ("l", "Low"), ("c", "Close"), ("v", "Volume"))}} for row in rows]
                candidates.insert(0, (bars, source))
            elif artifact["format"] == "pandas-frame-v1-json":
                frame = json.loads(payload)
                def scalar(cell):
                    if cell["type"] == "numpy":
                        import numpy as np
                        return float(np.frombuffer(bytes.fromhex(cell["hex"]), dtype=cell["dtype"])[0])
                    if cell["type"] == "float64":
                        return struct.unpack(">d", bytes.fromhex(cell["hex"]))[0]
                    if cell["type"] == "timestamp":
                        return datetime.fromtimestamp(int(cell["nanoseconds"]) / 1e9,
                            ZoneInfo(cell.get("timezone") or "UTC")).date().isoformat()
                    return cell.get("value", cell.get("decimal"))
                columns = [scalar(c) for c in frame["columns"]["values"]]
                bars = []
                for index, row in zip(frame["index"]["values"], frame["data"]):
                    values = dict(zip(columns, map(scalar, row)))
                    bars.append({"t": str(values.get("Date", scalar(index)))[:10],
                        "raw": {k: str(values[c]) for k, c in
                            (("o", "Open"), ("h", "High"), ("l", "Low"), ("c", "Close"), ("v", "Volume"))}, **{k: float(values[c])
                        for k, c in (("o", "Open"), ("h", "High"), ("l", "Low"), ("c", "Close"), ("v", "Volume"))}})
                candidates.append((bars, source))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            problems.append(f"Saved market input unavailable ({type(exc).__name__})")
    bars, source = next(((b, s) for b, s in candidates if b), ([], None))
    if not bars:
        problems.append("Recorded market inputs are missing; request current history separately in current market context.")
    bars = sorted((b for b in bars if str(b["t"])[:10] <= run["trade_date"]
                   and all(math.isfinite(b[k]) for k in ("o", "h", "l", "c", "v"))), key=lambda b: b["t"])
    result = next((r for r in run.get("results", []) if r["symbol"] == symbol), {})
    report = result.get("reports", {}).get("market_report", "")
    claims = [{"text": line.strip(), "symbol": symbol, "run_id": run["id"], "research_revision": result.get("revision", 0),
               "research_date": result.get("trade_date") or run["trade_date"], "report_key": "market_report",
               "report_text_sha256": hashlib.sha256(report.encode("utf-8")).hexdigest(),
               "numeric_tokens": re.findall(r"(?<!\w)[+-]?\d[\d,]*(?:\.\d+)?%?", line),
               "market_input": source if source and source.get("sha256") else None,
               "indicator_inputs": [{"name": item["name"], "source": item["source"],
                    "window_start": item["window_start"], "window_end": item["window_end"]} for item in indicators],
               "adjustment": (source or {}).get("adjustment"), "level_date": None,
               "mapping_status": "Dated report attribution only. Numeric tokens, level dates and indicator formulas are not independently mapped or verified against these recorded inputs."}
              for line in report.splitlines() if len(line.strip()) > 25
              and re.search(r"(?i)sma|ema|rsi|macd|support|resistan|breakout|stop|entry", line)]
    return {"symbol": symbol, "run_id": run["id"], "research_date": run["trade_date"], "bars": bars,
        "source": source, "feed": (source or {}).get("vendor"), "updated_at": (source or {}).get("captured_at"),
        "indicators": indicators, "claims": claims, "problems": problems,
        "price_basis": "Saved provider OHLCV; adjustment basis not recorded in receipt",
        "not_latest": True}
