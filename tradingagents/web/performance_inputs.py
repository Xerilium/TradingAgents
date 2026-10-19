"""Map 1D provider windows and optional ALL cashflow to covered inputs."""

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from .account_history import COST, EXTERNAL, INCOME, instant
from .investor import decimal

METHOD = "alpaca-1d-completed-ny-calendar-windows-v2"
SOURCES = ["https://docs.alpaca.markets/us/reference/getaccountportfoliohistory-1",
           "https://github.com/alpacahq/alpaca-py/blob/master/alpaca/trading/models.py#L348",
           "https://docs.alpaca.markets/us/reference/legacycalendar"]


def covered_inputs(portfolio, points, activities, calendar, *, pagination_complete, currency, start, end, captured_at):
    issues, valuations, flows = [], [], []
    proof = {"method": METHOD, "documentation": SOURCES, "requested_start": start, "requested_end": end,
             "valuation_basis": "Declared daily session-close convention: map New York dates of 1D provider labels to completed calendar closes, including early closes. Preserve original labels; mapped closes are not exact broker valuation-event timestamps.",
             "flow_basis": "Compare provider-as-of ALL cashflow, when supplied, with exact-time external activity under the disclosed SDK default. Unknown capital treatment and ambiguous timing block adjusted return."}
    try:
        if not pagination_complete or currency != "USD" or portfolio.get("timeframe") != "1D":
            raise ValueError("Complete activity pagination, USD and an explicitly returned 1D timeframe are required")
        capture = instant(captured_at)
        sessions = []
        for row in calendar:
            day = row["date"]
            close = datetime.fromisoformat(day + "T" + row["close"])
            close = close.replace(tzinfo=ZoneInfo("America/New_York")) if close.tzinfo is None else close
            if not start <= day <= end or close > capture:
                raise ValueError("Calendar interval includes an incomplete or out-of-range session")
            sessions.append((day, close))
        sessions.sort()
        if len(sessions) < 2 or len({day for day, _ in sessions}) != len(sessions):
            raise ValueError("At least two distinct completed equity windows are required")
        if [point["timestamp"] for point in points] != sorted({point["timestamp"] for point in points}):
            raise ValueError("Provider equity windows are duplicated or not ordered")
        days = [datetime.fromtimestamp(point["timestamp"], UTC).astimezone(ZoneInfo("America/New_York")).date().isoformat() for point in points]
        if days != [day for day, _ in sessions]:
            raise ValueError("Daily equity labels do not exactly cover the selected completed trading sessions")
        valuations = [{"at": close.isoformat(), "sequence": index, "equity": point["equity"],
                       "boundary": "session_close", "provider_window_timestamp": point["timestamp"], "session": day}
                      for index, ((day, close), point) in enumerate(zip(sessions, points))]
        if any(decimal(row["equity"]) is None or decimal(row["equity"]) < 0 for row in valuations):
            raise ValueError("Equity endpoints contain unavailable or negative values")
        cashflow = portfolio.get("cashflow", {})
        proof["cashflow_field"] = "Omitted: official Alpaca SDK defaults to an empty map (amounts per activity type, if any); no per-type zero arrays were supplied or synthesized" if "cashflow" not in portfolio else "Present: supplied per-type series retained unchanged"
        if not isinstance(cashflow, dict):
            raise ValueError("Cashflow must be a per-type mapping when supplied; explicit null is unsupported")
        series = {}
        for kind, values in cashflow.items():
            if not isinstance(values, list) or len(values) != len(points) or any(decimal(value) is None for value in values):
                raise ValueError("Per-type cashflow windows are missing or non-finite")
            series[kind] = [decimal(value) for value in values]
            if kind not in EXTERNAL | INCOME | COST | {"FILL"} and any(series[kind][1:]):
                raise ValueError("Reported cashflow type has unresolved investment/capital treatment: " + kind)
            if kind == "ACATC":
                raise ValueError("ACAT cash or in-kind gross capital coverage is not established by net daily amounts")
        totals = {kind: [Decimal(0)] * len(points) for kind in EXTERNAL}
        for activity in activities:
            if activity["category"] == "unclassified":
                raise ValueError("Activity contains unresolved capital treatment")
            if activity["category"] != "external_flow":
                continue
            stamp = instant(activity.get("time"))
            amount = decimal(activity.get("amount"))
            if activity["issues"] or amount is None:
                raise ValueError("External activity amount, status or exact effective time is unresolved")
            if stamp <= sessions[0][1]:
                continue  # First equity already includes this window's capital.
            index = next((i for i in range(1, len(sessions)) if sessions[i-1][1] < stamp <= sessions[i][1]), None)
            if index is None:
                continue  # Outside the actual close-to-close return interval.
            totals[activity["activity_type"]][index] += amount
            flows.append({"id": activity["id"], "time": stamp.isoformat(), "amount": str(amount),
                          "activity_type": activity["activity_type"]})
        for kind in EXTERNAL:
            reported = series.get(kind, [Decimal(0)] * len(points))
            if any(totals[kind][index] != reported[index] for index in range(1, len(points))):
                raise ValueError("Effective external activities do not reconcile to reported window cashflow for " + kind)
        proof.update(complete=True, valuation_start=valuations[0]["at"], valuation_end=valuations[-1]["at"],
                     sessions=[day for day, _ in sessions], external_flow_count=len(flows),
                     capital_coverage="Provider-as-of ALL cashflow under the disclosed cashflow_field convention reconciled by external type; creation-time pagination alone does not prove economic or settlement completeness")
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        issues.append(str(exc))
        proof["complete"] = False
    proof["issues"] = issues
    proof.update(calculation_complete=proof["complete"], status="complete" if proof["complete"] else "incomplete")
    return {"coverage": proof, "valuation_boundaries": valuations, "external_flows": flows,
            "calculation_coverage_complete": proof["calculation_complete"],
            "benchmark_calendar_calculable": bool(valuations) and not issues,
            "interval_complete": proof["complete"], "benchmark_calendar_complete": bool(valuations) and not issues,
            "benchmark_sessions": [row["session"] for row in valuations]}
