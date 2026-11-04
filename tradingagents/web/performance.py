"""Returns require actual, ordered valuation boundaries; missing records stay missing."""

from datetime import UTC, datetime
from decimal import Decimal

from .account_history import adjusted_report, instant
from .investor import decimal
from .performance_acceptance import assessment, qualify

TWR_METHOD = "linked-external-flow-boundaries-v1"


def time_weighted(valuations, flows, *, complete, currency):
    if complete is not True or currency != "USD" or len(valuations) < 2:
        raise ValueError("Time-weighted return requires a complete interval, USD and actual valuation boundaries")
    ordered = sorted(valuations, key=lambda row: (instant(row["at"]), row["sequence"]))
    if len({(row["at"], row["sequence"]) for row in ordered}) != len(ordered):
        raise ValueError("Valuation ordering is ambiguous")
    seen, flow_map = set(), {}
    for flow in flows:
        identity, amount, stamp = flow.get("id"), decimal(flow.get("amount")), instant(flow["time"])
        if not identity or identity in seen or amount is None:
            raise ValueError("Each external flow needs a unique identity, precise time and finite amount")
        seen.add(identity)
        flow_map[identity] = {**flow, "stamp": stamp, "amount_decimal": amount}
    growth, linked, peak, drawdown, used = Decimal(1), [], Decimal(1), Decimal(0), set()
    first = ordered[0]
    if decimal(first.get("equity")) is None or decimal(first["equity"]) <= 0:
        raise ValueError("Beginning valuation must be finite and positive")
    previous = first
    for current in ordered[1:]:
        begin, end = decimal(previous.get("equity")), decimal(current.get("equity"))
        if begin is None or begin <= 0 or end is None or end < 0:
            raise ValueError("Valuation denominator is nonpositive or a valuation is missing/non-finite")
        identity = current.get("external_flow_id")
        if current.get("boundary") == "after_flow":
            flow = flow_map.get(identity)
            if (flow is None or identity in used or current.get("boundary") != "after_flow"
                    or previous.get("boundary") != "before_flow" or previous.get("external_flow_id") != identity
                    or instant(current["at"]) != flow["stamp"] or instant(previous["at"]) != flow["stamp"]
                    or end - begin != flow["amount_decimal"]):
                raise ValueError("Each external flow requires actual before/after valuations with matching identity, order and cash effect")
            used.add(identity)
        else:
            low, high = instant(previous["at"]), instant(current["at"])
            if identity and (current.get("boundary") != "before_flow" or identity not in flow_map or high != flow_map[identity]["stamp"]):
                raise ValueError("A before-flow boundary requires the matching actual flow identity/time")
            if any(low < flow["stamp"] < high or flow["stamp"] == high and identity != key
                   for key, flow in flow_map.items() if key not in used):
                raise ValueError("External flow lacks a matching actual valuation boundary")
            factor = end / begin
            growth *= factor
            peak = max(peak, growth)
            drawdown = min(drawdown, growth / peak - 1)
            linked.append({"begin": previous, "end": current, "factor": str(factor), "linked_growth": str(growth)})
        previous = current
    if used != set(flow_map):
        raise ValueError("External flows are outside or unaccounted for in the covered interval")
    return {"method": TWR_METHOD, "calculable": True, "return": str(growth - 1), "currency": currency,
            "start": ordered[0]["at"], "end": ordered[-1]["at"], "subperiods": linked,
            "external_flows": flows, "drawdown": str(drawdown),
            "drawdown_basis": "Observed linked subperiod growth, excluding external capital; no intraperiod extrema are inferred"}


def supported_report(collection, method_assessment=None):
    review = method_assessment or assessment(collection)
    result = {"method": TWR_METHOD, "calculable": False, "reason": "Actual end-window valuations and exact external-flow before/after boundaries are not established"}
    try:
        if collection.get("valuation_boundaries") is not None:
            result = time_weighted(collection["valuation_boundaries"], collection.get("external_flows", []),
                complete=collection.get("calculation_coverage_complete") is True, currency=collection.get("currency"))
    except ValueError as exc:
        result["reason"] = str(exc)
    return qualify(result, review)


def benchmark_report(collection, benchmark, history, method_assessment=None):
    review = method_assessment or assessment(collection, benchmark=benchmark, history=history)
    def finish(result):
        return qualify(result, review)
    unavailable = {"available": False, "benchmark": benchmark, "reason": "Investor benchmark is unset"}
    if not benchmark:
        return finish(unavailable)
    unavailable["reason"] = "Matching benchmark history is unavailable or incomplete"
    if not history or history.get("symbol") != benchmark["symbol"] or not history.get("complete") or history.get("retained_older_data"):
        return finish(unavailable)
    if benchmark.get("currency") != "USD":
        return finish({**unavailable, "reason": "Benchmark currency does not match the USD account interval"})
    if benchmark.get("treatment") == "total_return":
        return finish({**unavailable, "reason": "IEX adjusted prices alone do not establish a reinvested-dividend total-return series and costs"})
    if history.get("adjustment") != "split":
        return finish({**unavailable, "reason": "Price-return benchmark requires explicitly split-adjusted prices; dividend-adjusted or raw data is not silently substituted"})
    bars = history.get("bars", [])
    sessions = collection.get("benchmark_sessions")
    if (not sessions or collection.get("benchmark_calendar_calculable") is not True
            or [bar["t"] for bar in bars] != sessions):
        return finish({**unavailable, "reason": "Benchmark bars do not exactly cover the account's completed calendar sessions; weekends are not endpoints and missing sessions are not interpolated"})
    values = [decimal(bar.get("raw", {}).get("c", bar.get("c"))) for bar in bars]
    if any(value is None or value <= 0 for value in values):
        return finish({**unavailable, "reason": "Benchmark prices are missing, non-finite or nonpositive"})
    strategy = supported_report(collection, review)
    result = {"calculable": False, "benchmark_price_return_calculable": True, "benchmark": benchmark, "benchmark_price_return": str(values[-1] / values[0] - 1),
              "start": bars[0]["t"], "end": bars[-1]["t"], "currency": "USD", "feed": "IEX", "session": "America/New_York daily",
              "treatment": "Split-adjusted price return; dividends and investor transaction costs excluded",
              "source": history.get("source"), "missing_dates": [], "calendar_sessions": sessions,
              "reason": "A matching supported strategy time-weighted series and session/calendar coverage are required for comparison"}
    if strategy.get("calculable") and collection.get("benchmark_calendar_calculable") is True:
        result.update(calculable=True, strategy_time_weighted_return=strategy["return"],
                      excess_return=str(Decimal(strategy["return"]) - Decimal(result["benchmark_price_return"])),
                      reason=None, costs="Benchmark frictionless price reference; strategy costs remain reflected only where source equity includes them")
    return finish(result)


def report_methods(collection, *, benchmark=None, history=None):
    coverage = collection.get("coverage", {})
    # Legacy coverage describes arithmetic inputs, not method support.
    legacy_complete = coverage.get("complete") if coverage.get("method") in {
        "alpaca-1d-completed-ny-calendar-windows-v1", "alpaca-1d-completed-ny-calendar-windows-v2"} else False
    collection["calculation_coverage_complete"] = collection.get("calculation_coverage_complete",
        coverage.get("calculation_complete", legacy_complete)) is True
    collection["benchmark_calendar_calculable"] = collection.get("benchmark_calendar_calculable",
        collection.get("benchmark_calendar_complete", False)) is True
    review = assessment(collection, benchmark=benchmark, history=history)
    collection["technical_method_assessment"] = review
    collection["interval_complete"] = review["accepted"] and collection.get("calculation_coverage_complete") is True
    collection["benchmark_calendar_complete"] = review["accepted"] and collection.get("benchmark_calendar_calculable") is True
    calculation = adjusted_report(
        [{"equity": row["equity"]} for row in collection.get("valuation_boundaries", [])],
        [{**flow, "category": "external_flow", "issues": []} for flow in collection.get("external_flows", [])],
        {**coverage, "complete": collection.get("calculation_coverage_complete") is True})
    collection["dietz"] = qualify(calculation, review)
    collection["time_weighted"] = supported_report(collection, review)
    collection["benchmark_comparison"] = benchmark_report(collection, benchmark, history, review)
    twr = collection["time_weighted"]
    collection["drawdown"] = qualify(
        {"method": TWR_METHOD, "calculable": twr["calculable"], "value": twr.get("drawdown"),
         "basis": twr.get("drawdown_basis"), "reason": None if twr["calculable"] else twr.get("reason")}, review)
    return collection
