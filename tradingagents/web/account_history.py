"""Trading API receipts and explicitly bounded performance reporting methods."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from urllib.parse import urlencode
from uuid import uuid4
from zoneinfo import ZoneInfo

from .investor import decimal

METHOD = "modified-dietz-recorded-flow-time-v1"
EXTERNAL = {"CSD", "CSW", "ACATC"}
INCOME = {"DIV", "CGD", "INT", "PTR"}
COST = {"FEE", "CFEE", "DIVFEE", "DIVNRA", "INTNRA", "INTTW", "PTC"}


def instant(value):
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("A dated activity without a recorded flow time cannot supply a Dietz weight")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Flow timestamps require a recorded time zone")
    return result


def modified_dietz(beginning, ending, start, end, flows, *, complete):
    if complete is not True:
        raise ValueError("Adjusted return unavailable: interval, valuation or activity coverage is incomplete")
    beginning, ending = decimal(beginning), decimal(ending)
    start, end = instant(start), instant(end)
    duration = Decimal(str((end - start).total_seconds()))
    if beginning is None or ending is None or beginning < 0 or ending < 0 or duration <= 0:
        raise ValueError("Adjusted return requires finite equity values and a positive covered interval")
    net, weighted, inputs = Decimal(0), Decimal(0), []
    for flow in flows:
        amount, stamp = decimal(flow["amount"]), instant(flow["time"])
        if amount is None or not start <= stamp <= end:
            raise ValueError("External flow is missing, non-finite or outside the valuation interval")
        weight = Decimal(str((end - stamp).total_seconds())) / duration
        net += amount
        weighted += amount * weight
        inputs.append({**flow, "weight": str(weight), "weighted_flow": str(amount * weight)})
    denominator = beginning + weighted
    if denominator <= 0:
        raise ValueError("Adjusted return denominator is nonpositive")
    return {"method": METHOD, "estimate": str((ending - beginning - net) / denominator),
            "beginning_equity": str(beginning), "ending_equity": str(ending), "start": start.isoformat(),
            "end": end.isoformat(), "net_external_flow": str(net), "weighted_external_flow": str(weighted),
            "denominator": str(denominator), "flows": inputs,
            "description": "Cash-flow-adjusted Modified Dietz estimate; not exact time-weighted return"}


def classify(row):
    kind = row.get("activity_type")
    category = "external_flow" if kind in EXTERNAL else "investment_income" if kind in INCOME else "investment_cost" if kind in COST else "trade" if kind == "FILL" else "unclassified"
    amount = decimal(row.get("net_amount"))
    issues = []
    if row.get("status") not in (None, "executed"):
        issues.append("Activity status is not an executed financial event")
    if category == "external_flow":
        if amount is None or kind == "CSD" and amount < 0 or kind == "CSW" and amount > 0:
            issues.append("External flow amount/direction is unavailable or inconsistent")
        try:
            stamp = instant(row.get("transaction_time") or row.get("date")).isoformat()
        except (ValueError, TypeError):
            stamp = None
            issues.append("External flow has no precise recorded time; date-only settlement data is not interpolated")
    else:
        stamp = row.get("transaction_time") or row.get("date")
    if category == "unclassified":
        issues.append("Activity type has unresolved cash/capital treatment")
    if category in {"investment_income", "investment_cost"} and amount is None:
        issues.append("Investment activity amount is unavailable")
    if category == "trade" and decimal(row.get("commission")) is None:
        issues.append("Fill commission is not present in this Trading API activity receipt")
    return {"id": row.get("id"), "activity_type": kind, "category": category, "amount": str(amount) if amount is not None else None,
            "time": stamp, "date": row.get("date"), "symbol": row.get("symbol"), "order_id": row.get("order_id"), "issues": issues}


def adjusted_report(points, activities, coverage):
    reasons = list(coverage.get("issues", []))
    if len(points) < 2:
        reasons.append("Two covered equity endpoints are required")
    reasons.extend(issue for activity in activities for issue in activity["issues"])
    try:
        if reasons:
            raise ValueError("; ".join(reasons))
        result = modified_dietz(points[0]["equity"], points[-1]["equity"], coverage["valuation_start"],
            coverage["valuation_end"], [a for a in activities if a["category"] == "external_flow"],
            complete=coverage.get("complete") is True)
        return {"calculable": True, **result}
    except (ValueError, KeyError) as exc:
        return {"method": METHOD, "calculable": False, "reasons": reasons or [str(exc)]}


def collect(client, store, start, end, expected_account):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if not first <= last or (last - first).days > 366 or last > datetime.now(UTC).date():
        raise ValueError("Choose a past/present interval no longer than 366 days")
    interval_start = datetime.combine(first, datetime.min.time(), ZoneInfo("America/New_York")).isoformat()
    interval_end = datetime.combine(last, datetime.max.time(), ZoneInfo("America/New_York")).isoformat()
    identity, receipts, issues = str(uuid4()), [], []
    def read(path):
        receipt = client.read_receipt(path)
        artifact = store._write_source_result(identity, str(uuid4()), receipt["raw"].decode("utf-8"), prefix="account-history")
        receipts.append({"path": path, "received_at": receipt["received_at"], "source_date": receipt["source_date"], "artifact": artifact})
        return receipt["data"]
    before = read("/v2/account")
    if not before.get("id") or expected_account and before["id"] != expected_account:
        raise ValueError("History account identity differs from the current Nautilus observation")
    portfolio = None
    calendar = []
    try:
        portfolio = read("/v2/account/portfolio/history?" + urlencode({"start": interval_start, "end": interval_end,
            "timeframe": "1D", "cashflow_types": "ALL", "pnl_reset": "no_reset"}))
    except Exception as exc:
        issues.append("Portfolio history request unavailable (" + type(exc).__name__ + ")")
    try:
        calendar = read("/v2/calendar?" + urlencode({"start": start, "end": end}))
        if not isinstance(calendar, list):
            raise ValueError("Calendar response is not a session list")
    except Exception as exc:
        issues.append("Valuation calendar unavailable (" + type(exc).__name__ + ")")
        calendar = []
    unique, page_token, tokens, complete = {}, None, set(), False
    try:
        for _ in range(20):
            query = {"after": interval_start, "until": interval_end, "direction": "asc", "page_size": 100}
            if page_token:
                query["page_token"] = page_token
            page = read("/v2/account/activities?" + urlencode(query))
            if not isinstance(page, list) or len(page) > 100:
                raise ValueError("Unexpected Trading API activity page")
            for row in page:
                if not isinstance(row.get("id"), str) or not row["id"]:
                    raise ValueError("Activity has no stable identity")
                if row["id"] in unique and unique[row["id"]] != row:
                    raise ValueError("Activity identity returned with conflicting contents")
                unique[row["id"]] = row
            if len(page) < 100:
                complete = True
                break
            page_token = page[-1]["id"]
            if page_token in tokens:
                raise ValueError("Activity pagination stopped advancing")
            tokens.add(page_token)
        if not complete:
            issues.append("Activity pagination reached its 2000-record budget")
    except Exception as exc:
        complete = False
        issues.append("Activity history incomplete (" + type(exc).__name__ + ")")
    try:
        after = read("/v2/account")
        if after.get("id") != before["id"]:
            complete = False
            issues.append("Account identity changed during history collection")
    except Exception as exc:
        complete = False
        issues.append("Closing account identity unavailable (" + type(exc).__name__ + ")")
    activities = [classify(row) for row in unique.values()]
    for item in activities:
        issues.extend(item["id"] + ": " + issue for issue in item["issues"])
    points = []
    if isinstance(portfolio, dict):
        timestamps = portfolio.get("timestamp", [])
        arrays = [portfolio.get(key, []) for key in ("equity", "profit_loss", "profit_loss_pct")]
        if not timestamps or any(len(a) != len(timestamps) for a in arrays) or len(set(timestamps)) != len(timestamps):
            issues.append("Broker equity/P&L series has missing or inconsistent dates")
        else:
            for index, timestamp in enumerate(timestamps):
                values = [decimal(a[index]) for a in arrays]
                if type(timestamp) is not int or any(v is None for v in values):
                    issues.append("Broker equity/P&L point is missing or non-finite")
                    continue
                points.append({"timestamp": timestamp, "equity": str(values[0]), "broker_profit_loss": str(values[1]),
                               "broker_profit_loss_pct": str(values[2])})
    from .performance_inputs import covered_inputs
    covered = covered_inputs(portfolio or {}, points, activities, calendar, pagination_complete=complete,
        currency=before.get("currency"), start=start, end=end, captured_at=datetime.now(UTC).isoformat())
    issues.extend(covered["coverage"]["issues"])
    result = {"id": identity, "account_id": before["id"], "currency": before.get("currency"),
        "requested_start": start, "requested_end": end, "collected_at": datetime.now(UTC).isoformat(),
        "source": "Alpaca paper Trading API", "receipts": receipts, "activities": activities,
        "pagination_complete": complete, **covered, "points": points,
        "broker_base_value": portfolio.get("base_value") if isinstance(portfolio, dict) else None,
        "broker_base_value_asof": portfolio.get("base_value_asof") if isinstance(portfolio, dict) else None,
        "broker_cashflow_series": portfolio.get("cashflow") if isinstance(portfolio, dict) else None,
        "timeframe": "1D", "cashflow_types": "ALL", "raw_broker_percent_method": "equity / base_value - 1; not verified cash-flow-adjusted return",
        "broker_rounding": "Cash figures rounded to two digits; percentages to four digits",
        "benchmark": None, "issues": issues,
        "allocation_observation": None, "history_holdings_reconstructed": False}
    from .performance import report_methods
    report_methods(result)
    result["methodology_inputs"] = {"method": "account-history-methods-v1", "source_receipts": receipts,
        "coverage_issues": issues, "coverage_proof": covered["coverage"], "valuation_time_basis": covered["coverage"]["valuation_basis"],
        "flow_time_basis": "Trading API transaction_time when present; non-trade date may be settlement date"}
    result["artifact"] = store._write_json_artifact(identity, "account-history-summary", result)
    return result
