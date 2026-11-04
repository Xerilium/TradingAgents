"""Read recorded market inputs. Research prose never supplies chart prices."""

import csv
import hashlib
import io
import json
import math
import re
import struct
from importlib.metadata import version
from pathlib import Path

from .investor import digest


def scan_source_evidence(history, selected, cutoff):
    """Freeze actual retained rows; expected calendar buckets are evidence, never invented bars."""
    from .evaluation import chart_number, instant, reference
    from .history_coverage import scan_axis

    history = history if isinstance(history, dict) else {}
    axis = scan_axis(history, selected, cutoff)
    reasons = list(axis["reasons"])
    pin = history.get("artifact")
    if pin:
        reference(pin)
    else:
        reasons.append("Exact retained source artifact is unavailable; select or explicitly collect this input")
    profile = selected["source_profile"]
    if (history.get("provider") != profile["provider"] or history.get("feed") != profile["feed"]
            or history.get("adjustment") != profile["adjustment"] or history.get("currency", "USD") != profile["currency"]
            or history.get("timeframe") != selected["timeframe"] and not (history.get("timeframe") == "1Min" and axis.get("aggregation"))
            or selected["history_key"] and history.get("key") != selected["history_key"]):
        reasons.append("Retained source identity/timeframe/profile differs from the saved named input")
    capture = history.get("captured_at")
    if capture:
        instant(capture)
    else:
        reasons.append("Actual source capture/knowledge time is unavailable")
    if history.get("error") and not history.get("bars"):
        reasons.append(str(history["error"]))
    actual = history.get("bars", [])
    if not isinstance(actual, list) or len(actual) > 100000:
        raise ValueError("Scanner source row budget exceeded; input is not truncated")
    seen, rows, segment = set(), [], 0
    for original in sorted(actual, key=lambda item: item["t"]):
        time_key = str(original["t"])
        if time_key in seen:
            raise ValueError("Same-time scanner revisions require an exact replacement artifact")
        seen.add(time_key)
        proof = axis["observations"].get(time_key)
        if proof is None and selected["session"] == "regular":
            continue
        proof = proof or {}
        raw, row_reasons = original.get("raw", original), list(proof.get("reasons", []))
        try:
            values = {key: chart_number(str(raw[key])) for key in ("o", "h", "l", "c", "v")}
            valid = (min(values[key] for key in ("o", "h", "l", "c")) > 0 and values["v"] >= 0
                and values["h"] >= max(values[key] for key in ("o", "l", "c")) and values["l"] <= min(values[key] for key in ("o", "h", "c")))
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            row_reasons.append("missing_or_invalid_actual_source_bar")
        closed = proof.get("closed") is True and bool(proof.get("closed_at"))
        if not closed:
            row_reasons.append("closure_unverified_or_provisional")
        if not capture:
            row_reasons.append("actual_source_availability_unverified")
        if proof.get("gap_before") or row_reasons or rows and rows[-1]["reasons"]:
            segment += 1
        rows.append({"t": original["t"], "source_ordinal": len(rows), "segment": segment,
            "raw": {key: str(raw[key]) for key in ("o", "h", "l", "c", "v")} if valid else None,
            "closed": closed, "closed_at": proof.get("closed_at"), "available_at": capture,
            "closure_basis": proof.get("closure_basis"), "source_timestamp": original.get("provider_timestamp"),
            "gap_before": bool(proof.get("gap_before")), "reasons": row_reasons, "expected_ordinal": proof.get("expected_ordinal")})
    prefix = hashlib.sha256()
    for row in rows:
        prefix.update(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())
        row["history_prefix_sha256"] = prefix.hexdigest()
    source = {key: history.get(key) for key in ("symbol", "instrument_id", "currency", "timeframe", "adjustment", "captured_at", "key")}
    source.update(provider=history.get("provider"), feed=history.get("feed"), session=selected["session"],
        artifact=pin, calendar_reference=axis.get("calendar_reference"), query_bounds=axis.get("query_bounds"),
        receipts=history.get("receipts", []), requested_range={key: history.get(key) for key in ("start", "end")},
        full_history=history.get("complete") is True and history.get("pagination_complete") is True,
        calendar_available=bool(axis.get("calendar")))
    if not source["full_history"]:
        reasons.append("Retained source pagination/completeness is unestablished; missing prefixes are not warmup proof")
    if not rows:
        reasons.append("No actual retained source rows exist in the selected axis/session")
    return {"rows": rows, "source": source, "source_pin": pin, "calendar": axis.get("calendar", []),
        "calendar_coverage": axis.get("calendar_coverage"), "expected_buckets": axis["expected_buckets"],
        "axis_status": "available" if axis["status"] == "available" and not reasons else "unavailable", "axis_reasons": reasons,
        "aggregation": axis.get("aggregation"),
        "absence": axis.get("absence"),
        "source_sha256": digest({"source": source, "rows": rows, "calendar_coverage": axis.get("calendar_coverage")}),
        "source_limitations": ["Later capture/revisions do not establish historical point-in-time availability.",
            "Expected buckets identify gaps; only actual original source observations enter causal calculations."]}


def chart_source_evidence(history, pin):
    """Freeze real retained rows, closure evidence and expected gaps for pure calculations."""
    from datetime import datetime
    from decimal import Decimal, InvalidOperation

    from .evaluation import chart_number
    from .history_coverage import indicator_observations

    if not isinstance(pin, dict) or not history.get("bars") or not history.get("artifact") or pin.get("artifact") != history["artifact"]:
        raise ValueError("Chart calculation requires the exact verified retained artifact pin")
    coverage = history.get("required_coverage", {})
    observations = history.get("indicator_evidence", {}).get("indicator_observations", {})
    captured = history.get("captured_at")
    if not observations and captured and coverage.get("provenance", {}).get("calendar_reference"):
        observations = indicator_observations(history["bars"], coverage, captured_at=captured,
            timeframe=history.get("timeframe"), now=datetime.fromisoformat(captured))
    calendar = history.get("calendar", [])
    provenance = coverage.get("provenance", {})
    if calendar and digest(calendar) != provenance.get("calendar_sha256"):
        raise ValueError("Calculation calendar differs from the retained source receipt")
    dates = [row["date"] for row in calendar]
    if len(dates) != len(set(dates)):
        raise ValueError("Expected calendar has duplicate sessions")
    unique = {}
    for row in history["bars"]:
        if row["t"] in unique:
            raise ValueError("Same-time revisions require an exact replacement artifact")
        unique[row["t"]] = row
    ordered = sorted(unique)
    expected = sorted({day for day in dates if ordered[0] <= day <= ordered[-1]} | set(ordered)) if dates else ordered
    rows, previous, segment = [], None, 0
    for ordinal, day in enumerate(expected):
        row, proof = unique.get(day), observations.get(day, {})
        values = row.get("raw", row) if row else {}
        try:
            valid = all(key in values and chart_number(str(values[key])) >= 0 for key in ("o", "h", "l", "c", "v"))
            valid = valid and min(Decimal(str(values[key])) for key in ("o", "h", "l", "c")) > 0
            valid = valid and Decimal(str(values["h"])) >= max(Decimal(str(values[key])) for key in ("o", "l", "c")) and Decimal(str(values["l"])) <= min(Decimal(str(values[key])) for key in ("o", "h", "c"))
        except (InvalidOperation, ValueError, TypeError):
            valid = False
        closed = proof.get("closed") is True and bool(proof.get("closed_at"))
        known_times = [datetime.fromisoformat(value) for value in (captured, proof.get("available_at")) if value]
        available_at = max(known_times).isoformat() if known_times else None
        outside_calendar = bool(dates and day not in dates)
        if not valid or not closed or outside_calendar:
            segment += 1
        rows.append({"t": day, "source_ordinal": ordinal, "segment": segment,
            "raw": {key: str(values[key]) for key in ("o", "h", "l", "c", "v")} if valid else None,
            "closed": closed, "closed_at": proof.get("closed_at"), "available_at": available_at, "closure_basis": proof.get("closure_basis"),
            "source_timestamp": row.get("provider_timestamp") if row else None,
            "gap_before": previous is not None and not dates,
            "reasons": ([] if valid else ["missing_or_invalid_expected_source_bar"]) + ([] if closed else ["closure_unverified_or_provisional"])
                + (["outside_expected_calendar"] if outside_calendar else [])})
        if available_at is None:
            rows[-1]["reasons"].append("actual_source_availability_unverified")
        previous = day
    prefix = hashlib.sha256()
    for row in rows:
        prefix.update(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())
        row["history_prefix_sha256"] = prefix.hexdigest()
    source = {key: history.get(key) for key in ("symbol", "instrument_id", "currency", "timeframe", "adjustment", "session", "captured_at")}
    source.update(provider=history.get("source", {}).get("vendor"), feed=history.get("source", {}).get("feed"),
        artifact=history["artifact"], calendar_sha256=provenance.get("calendar_sha256"), provenance=provenance,
        full_history=history.get("complete") is True and history.get("pagination_complete") is True,
        calendar_available=bool(calendar))
    return {"rows": rows, "source": source, "calendar": calendar, "calendar_coverage": history.get("calendar_coverage"),
        "source_sha256": digest({"source": source, "rows": rows, "calendar_coverage": history.get("calendar_coverage")}),
        "source_limitations": ["Later capture/revisions do not establish historical point-in-time availability.",
            "Absent expected-session evidence makes continuity unverified; derived segments cannot bridge unknown gaps."]}


def derive_indicators(bars, source, *, coverage=None, now=None):
    """Derive research formulas only from identified, supplied OHLCV history."""
    import pandas as pd
    from tradingagents.dataflows.vendors.yahoo.market import calculate_stockstats

    specifications = {
        "close_50_sma": (50, "close rolling mean; min_periods=1", "price"),
        "close_200_sma": (200, "close rolling mean; min_periods=1", "price"),
        "close_10_ema": (10, "close EWM span=10; adjust=True; min_periods=1", "price"),
        "macd": (26, "close EWM12 minus EWM26; adjust=True", "price"),
        "macds": (34, "MACD EWM9; adjust=True", "price"),
        "macdh": (34, "MACD minus signal; multiplier=1", "price"),
        "rsi": (15, "SMMA14 gains/(gains+losses)*100; adjust=True; flat=50", "0-100"),
        "boll": (20, "close SMA20", "price"),
        "boll_ub": (20, "close SMA20 + 2*sample_std20; ddof=1", "price"),
        "boll_lb": (20, "close SMA20 - 2*sample_std20; ddof=1", "price"),
        "atr": (14, "true range SMMA14; adjust=True", "price"),
        "vwma": (14, "SUM14(volume*typical_price)/SUM14(volume); zero=0", "price"),
        "mfi": (15, "positive_flow14/total_flow14; first14=0.5; zero=0.5", "0-1"),
    }
    # Conflicting revisions require an explicit replacement history, never last-write wins.
    unique = {}
    for bar in bars:
        if bar["t"] in unique and unique[bar["t"]].get("raw", unique[bar["t"]]) != bar.get("raw", bar):
            raise ValueError("Conflicting OHLCV revisions at one timestamp")
        unique[bar["t"]] = bar
    ordered = sorted(unique.values(), key=lambda bar: bar["t"])
    valid, gaps = [], []
    for bar in ordered:
        values = [bar.get("raw", {}).get(k, bar.get(k)) for k in ("o", "h", "l", "c", "v")]
        if not all(value is not None and math.isfinite(float(value)) for value in values):
            gaps.append(bar["t"])
        else:
            valid.append((bar, values))
    identity = {key: source.get(key) for key in ("vendor", "feed", "symbol", "instrument", "timeframe", "currency",
        "session", "session_timezone", "adjustment", "symbol_mapping_asof", "sha256", "history_hashes", "precision")}
    history_sha = digest([{ "t": bar["t"], "values": values} for bar, values in valid])
    prefixes, prefix = [], hashlib.sha256()
    for bar, values in valid:
        prefix.update(json.dumps({"t": bar["t"], "values": values}, sort_keys=True, separators=(",", ":")).encode())
        prefixes.append(prefix.hexdigest())
    import stockstats
    implementation = {"library": "stockstats", "version": version("stockstats"), "boundary": "research-stockstats-v1",
        "implementation_sha256": hashlib.sha256(Path(stockstats.__file__).read_bytes()).hexdigest()}
    frame = pd.DataFrame([values for _, values in valid], columns=["Open", "High", "Low", "Close", "Volume"]).apply(pd.to_numeric)
    output, failure = None, None
    if valid:
        try:
            output = calculate_stockstats(frame)
        except Exception as exc:
            failure = type(exc).__name__
    states = (coverage or {}).get("indicator_observations", {})
    result = []
    for name, (minimum, formula, units) in specifications.items():
        definition = {**implementation, "name": name, "formula": formula, "units": units,
            "minimum_observations": minimum, "initialization": "all supplied history; minimum count is not convergence proof",
            "ewm_adjust": True if name in {"close_10_ema", "macd", "macds", "macdh", "rsi", "atr"} else None}
        comparable = digest({"definition": definition, "source": {k: v for k, v in identity.items()
            if k not in {"sha256", "history_hashes"}}})
        derivation = digest({"definition": definition, "source": identity, "history_sha256": history_sha})
        points = []
        for index, (bar, _) in enumerate(valid):
            value = None if output is None else float(output[name].iloc[index])
            numeric = value is not None and math.isfinite(value)
            evidence = states.get(str(bar["t"]), {})
            initialized = index + 1 >= minimum and source.get("full_history") is True and not gaps
            closed, fresh = evidence.get("closed") is True, evidence.get("fresh") is True
            reasons = ([] if numeric else ["calculation_failure" if failure else "missing_value"])
            reasons += ([] if initialized else ["initialization_unverified_or_short"])
            reasons += ([] if closed else ["bar_finality_unverified"])
            reasons += ([] if fresh else ["source_freshness_unverified_or_stale"])
            points.append({"t": bar["t"], "value": value if numeric else None, "raw": repr(value) if numeric else None,
                "numerical_available": numeric, "initialized": initialized, "closed": closed, "fresh": fresh,
                "alert_eligible": not reasons, "reasons": reasons, "observations": index + 1,
                "observation_identity": digest({"derivation": derivation, "t": bar["t"]}),
                "history_prefix_identity": prefixes[index],
                "closed_at": evidence.get("closed_at"), "source_revision": history_sha})
        result.append({"name": name, "points": points, "definition": definition, "units": units,
            "source": source, "derivation_identity": derivation, "comparable_identity": comparable,
            "initialization_history_sha256": history_sha, "excluded_times": gaps,
            "calculation_failure": failure, "window_start": valid[0][0]["t"] if valid else None,
            "window_end": valid[-1][0]["t"] if valid else None})
    return result


def decode_frame(payload):
    """Decode the store's safe tagged frame format with its recorded dtypes."""
    import numpy as np
    import pandas as pd
    frame = json.loads(payload)
    if frame.get("schema") != "pandas-frame-v1":
        raise ValueError("Unsupported recorded frame schema")
    def scalar(cell):
        kind = cell["type"]
        if kind == "numpy":
            dtype = np.dtype(cell["dtype"])
            if dtype.kind not in "biuf" or dtype.itemsize > 8:
                raise ValueError("Unsupported numeric frame cell")
            return np.frombuffer(bytes.fromhex(cell["hex"]), dtype=dtype)[0]
        if kind == "float64":
            return struct.unpack(">d", bytes.fromhex(cell["hex"]))[0]
        if kind == "timestamp":
            stamp = pd.Timestamp(int(cell["nanoseconds"]), unit="ns", tz="UTC")
            return stamp.tz_convert(cell["timezone"]) if cell.get("timezone") else stamp.tz_localize(None)
        if kind in {"pd.NA", "pd.NaT", "none"}:
            return {"pd.NA": pd.NA, "pd.NaT": pd.NaT, "none": None}[kind]
        if kind == "int":
            return int(cell["decimal"])
        if kind in {"str", "bool"}:
            return cell["value"]
        raise ValueError("Unsupported recorded frame cell")
    def dtype(meta):
        if meta.get("storage"):
            return pd.StringDtype(storage=meta["storage"], na_value=scalar(meta["missing"]))
        return meta.get("numpy_dtype", meta["name"])

    def axis(meta):
        values, name = [scalar(cell) for cell in meta["values"]], scalar(meta["name"])
        if meta["kind"] == "RangeIndex":
            result = pd.RangeIndex(*meta["range"], name=name)
            if list(result) != values:
                raise ValueError("Recorded range axis differs from its values")
            return result
        if meta["kind"] == "DatetimeIndex":
            return pd.DatetimeIndex(values, dtype=dtype(meta["dtype"]), name=name, freq=meta.get("frequency"))
        if meta["kind"] != "Index":
            raise ValueError("Unsupported recorded frame axis")
        return pd.Index(values, dtype=dtype(meta["dtype"]), name=name)

    data = pd.DataFrame({i: pd.Series([scalar(row[i]) for row in frame["data"]], dtype=dtype(meta))
                         for i, meta in enumerate(frame["dtypes"])})
    data.columns = axis(frame["columns"])
    data.index = axis(frame["index"])
    data.flags.allows_duplicate_labels = frame["allows_duplicate_labels"]
    return data


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
                frame = decode_frame(payload)
                bars = []
                for position, index in enumerate(frame.index):
                    row = {column: frame[column].iloc[position] for column in frame.columns}
                    stamp = row.get("Date", index)
                    if not hasattr(stamp, "isoformat"):
                        import pandas as pd
                        stamp = pd.Timestamp(stamp)
                    bars.append({"t": stamp.date().isoformat(), "provider_timestamp": stamp.isoformat(),
                        "raw": {k: str(row[c]) for k, c in
                            (("o", "Open"), ("h", "High"), ("l", "Low"), ("c", "Close"), ("v", "Volume"))},
                        **{k: float(row[c]) if row[c] is not None and str(row[c]) not in {"<NA>", "NaT"} else float("nan") for k, c in
                            (("o", "Open"), ("h", "High"), ("l", "Low"), ("c", "Close"), ("v", "Volume"))}})
                source.update(full_history=True, symbol=symbol, timeframe="1Day", feed=attempt.get("vendor"),
                    adjustment="auto_adjust=False" if operation == "ohlcv_history" else "cache_reported_basis_unverified",
                    session="unverified", currency=None, precision="recorded frame numeric bits",
                    history_hashes=[artifact["sha256"]])
                candidates.append((bars, source))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            problems.append(f"Saved market input unavailable ({type(exc).__name__})")
    bars, source = next(((b, s) for b, s in sorted(candidates, key=lambda item: (item[1].get("full_history") is True, len(item[0])), reverse=True) if b), ([], None))
    if not bars:
        problems.append("Recorded market inputs are missing; request current history separately in current market context.")
    bars = sorted((b for b in bars if str(b["t"])[:10] <= run["trade_date"]), key=lambda b: b["t"])
    if source and source.get("full_history"):
        try:
            indicators = derive_indicators(bars, source)
        except (ValueError, TypeError, KeyError) as exc:
            indicators = []
            problems.append("Retained indicator derivation unavailable (" + type(exc).__name__ + ")")
    else:
        for item in indicators:
            item.update(name=item["name"].lower(), units=None, eligibility="output_only_unverified_initialization")
            item["points"] = sorted(item["points"], key=lambda point: point["t"])
            for point in item["points"]:
                point.update(alert_eligible=False, reasons=["output_only_unverified_initialization"])
    bars = [bar for bar in bars if all(math.isfinite(bar[k]) for k in ("o", "h", "l", "c", "v"))]
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
