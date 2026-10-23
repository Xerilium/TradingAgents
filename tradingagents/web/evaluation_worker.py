"""Isolated installed-v1 native saved-plan simulation; no broker imports or credentials."""

import hashlib
import importlib.metadata
import json
import math
import sys
from dataclasses import asdict
from decimal import Decimal

from evaluation import (
    EXPERIMENT_VERSION,
    VERSION,
    amount,
    digest,
    finite,
    instant,
    validate_strategy,
    validate_terms,
)


def clean(value):
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def calculate_seasonality(spec):
    from datetime import date, timedelta
    from fractions import Fraction

    settings, rows, calendar = spec["definition"]["settings"], spec["rows"], spec["calendar"]
    if settings["adjustment"] != spec["source"]["adjustment"]:
        raise ValueError("Seasonality adjustment must match the exact retained source")
    by_day = {row["t"]: row for row in rows}
    dates = sorted(row["date"] for row in calendar)
    bounds = spec.get("calendar_coverage") or {}
    bounds_known = bool(bounds.get("reference") and bounds.get("start") and bounds.get("end"))
    if bounds_known:
        date.fromisoformat(bounds["start"])
        date.fromisoformat(bounds["end"])
    eligible, excluded, year_rows = [], [], []
    years = sorted({int(day[:4]) for day in dates})

    def close(day):
        row = by_day.get(day)
        return Fraction(row["raw"]["c"]) if row and not row["reasons"] else None

    def average(values):
        return str(sum(values) / len(values)) if values else None

    for year in years:
        expected = [day for day in dates if day.startswith(str(year) + "-")]
        prior = [day for day in dates if day.startswith(str(year - 1) + "-12-")]
        full_calendar = bool(bounds_known and bounds["start"] <= f"{year}-01-01" and bounds["end"] >= f"{year}-12-31")
        missing = [day for day in expected if close(day) is None]
        months = {month: [day for day in expected if int(day[5:7]) == month] for month in range(1, 13)}
        if not full_calendar or not prior or close(prior[-1]) is None or missing or any(not days for days in months.values()):
            excluded.append({"year": year, "reason": "; ".join(reason for reason in (
                "Authenticated calendar request bounds are unavailable" if not bounds_known else "Calendar request does not cover the full year" if not full_calendar else None,
                "Prior December closing observation is unavailable" if not prior or close(prior[-1]) is None else None,
                "Expected retained sessions are missing" if missing else None,
                "Calendar response has no sessions for one or more months" if any(not days for days in months.values()) else None) if reason),
                "missing_sessions": missing, "prior_anchor": prior[-1] if prior else None})
            continue
        anchor = close(prior[-1])
        returns, previous = [], anchor
        for month in range(1, 13):
            value = close(months[month][-1])
            returns.append((value / previous - 1) * 100)
            previous = value
        points = [{"t": day, "session_ordinal": ordinal, "calendar_key": day[5:], "source_ordinal": by_day[day]["source_ordinal"],
            "raw_close": str(close(day)), "value": str(close(day) if settings["comparison"] == "raw" else (close(day) / anchor - 1) * 100)} for ordinal, day in enumerate(expected)]
        eligible.append(year)
        year_rows.append({"year": year, "prior_anchor": prior[-1], "prior_anchor_close": str(anchor),
            "monthly_returns": [{"month": month, "return_pct": str(value), "end_session": months[month][-1]} for month, value in enumerate(returns, 1)],
            "points": points, "complete": True})
    monthly = []
    for month in range(1, 13):
        values = [Fraction(row["monthly_returns"][month - 1]["return_pct"]) for row in year_rows]
        positive, negative = [v for v in values if v > 0], [v for v in values if v < 0]
        monthly.append({"month": month, "eligible_year_count": len(values), "positive_count": len(positive), "negative_count": len(negative),
            "flat_count": sum(v == 0 for v in values), "positive_frequency": str(Fraction(len(positive), len(values))) if values else None,
            "mean_return_pct": average(values), "conditional_gain_mean_pct": average(positive), "conditional_loss_mean_pct": average(negative)})
    actual = [row for row in rows if not row["reasons"]]
    partial = {"mtd": None, "ytd": None, "excluded_from_completed_aggregates": True}
    if actual:
        latest = actual[-1]["t"]
        year, month = latest[:4], latest[:7]
        for field, prefix in (("mtd", month), ("ytd", year)):
            required = [day for day in dates if day.startswith(prefix) and day <= latest]
            first_day = date.fromisoformat(prefix + ("-01-01" if field == "ytd" else "-01"))
            prior_month = (first_day - timedelta(days=1)).strftime("%Y-%m")
            anchors = [day for day in dates if day.startswith(prior_month)]
            anchor = anchors[-1] if anchors else None
            missing = [day for day in required if close(day) is None]
            available = bool(bounds_known and anchor and bounds["start"] <= anchor and bounds["end"] >= latest
                and bounds["start"] <= first_day.isoformat() and close(anchor) is not None and required and not missing)
            partial[field] = {"available": available, "through": latest, "prior_anchor": anchor, "missing_sessions": missing,
                "return_pct": str((close(latest) / close(anchor) - 1) * 100) if available else None,
                "reason": None if available else "Authenticated calendar request bounds are unavailable" if not bounds_known else "Calendar request does not cover the period and its prior anchor" if anchor and (bounds["start"] > min(anchor, first_day.isoformat()) or bounds["end"] < latest) else "Prior closing observation is unavailable" if not anchor or close(anchor) is None else "Expected period sessions are missing or absent"}
    comparison_years = [{**row, "included_in_monthly_aggregates": True} for row in year_rows]
    for year in years:
        if year in eligible:
            continue
        observed = [row["t"] for row in actual if row["t"].startswith(str(year) + "-")]
        anchors = [day for day in dates if day.startswith(str(year - 1) + "-12-")]
        if not observed or not anchors or close(anchors[-1]) is None:
            continue
        through, anchor = max(observed), anchors[-1]
        required = [day for day in dates if f"{year}-01-01" <= day <= through]
        if not bounds_known or bounds["start"] > anchor or bounds["end"] < through or any(close(day) is None for day in required):
            continue
        opening = close(anchor)
        comparison_years.append({"year": year, "complete": False, "through": through, "prior_anchor": anchor,
            "prior_anchor_close": str(opening), "included_in_monthly_aggregates": False,
            "points": [{"t": day, "session_ordinal": ordinal, "calendar_key": day[5:], "source_ordinal": by_day[day]["source_ordinal"],
                "raw_close": str(close(day)), "value": str(close(day) if settings["comparison"] == "raw" else (close(day) / opening - 1) * 100)} for ordinal, day in enumerate(required)]})
    return {"eligible_years": eligible, "excluded_years": excluded, "monthly": monthly, "years": year_rows, "partial": partial,
        "comparison_years": sorted(comparison_years, key=lambda row: row["year"]),
        "alignment": settings["alignment"], "comparison": settings["comparison"], "adjustment": settings["adjustment"],
        "return_basis": "Price returns only; dividends excluded; no total-return claim", "frequency_denominator": "Same fully eligible completed years for every month",
        "calendar_coverage": bounds, "axis": "Actual month-day calendar keys" if settings["alignment"] == "calendar" else "Actual expected-session ordinals; no calendar interpolation"}


def calculate_chart(spec, shared_cache=None):
    """Pure retained-input calculations; deliberately no strategy, node, broker or optimizer."""
    from datetime import UTC, datetime
    from fractions import Fraction
    from pathlib import Path

    from evaluation import CHART_VERSION, chart_integer, formula_tree, validate_chart_calculation

    validate_chart_calculation(spec)
    if importlib.metadata.version("nautilus_trader") != spec["engine_version"]:
        raise ValueError("Chart native library version differs from the selected implementation")
    rows, definition = spec["rows"], spec["definition"]
    calculated_at = datetime.now(UTC).isoformat()
    initialization_starts, start = [], 0
    for index, row in enumerate(rows):
        if index == 0 or row["gap_before"] or row["reasons"] or rows[index - 1]["reasons"] or row["segment"] != rows[index - 1]["segment"]:
            start = index
        initialization_starts.append(start)
    series, events, provisional, native_sources = [], [], [], {}

    def rational(value):
        return Fraction(str(value))

    def point(index, value, *, initialized=True, offset=0, first=None, units="price"):
        row = rows[index]
        available = value is not None and (not isinstance(value, float) or math.isfinite(value))
        availability = max(instant(value) for value in (row["available_at"], calculated_at, *(item["updated_at"] for item in [definition, *spec["dependencies"]])) if value)
        try:
            display_value = float(value) if available else None
        except OverflowError:
            display_value = None
        display_value = display_value if display_value is None or math.isfinite(display_value) else None
        return {"source_ordinal": index, "output_ordinal": index, "t": row["t"], "origin_at": row["source_timestamp"],
            "closed_at": row["closed_at"], "source_available_at": row["available_at"], "calculated_at": calculated_at,
            "available_at": availability.isoformat(), "display_offset": offset,
            "raw": str(value) if available else None, "value": display_value,
            "numerical_available": available, "initialized": initialized and available and not row["reasons"], "closed": row["closed"],
            "units": units, "reasons": row["reasons"] + ([] if available and initialized else ["missing_or_initializing"]),
            "source_range": [min(initialization_starts[index], index if first is None else first), index], "history_prefix_sha256": row["history_prefix_sha256"]}

    def native_source(module):
        path = Path(module.__file__)
        native_sources[module.__name__] = {"version": spec["engine_version"], "binary_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_sha256": hashlib.sha256(path.with_name(path.name.split(".")[0] + ".pyx").read_bytes()).hexdigest()}

    def study(settings):
        key = "study:" + digest({"source": spec["source_sha256"], "settings": settings})
        prior = reused(key)
        if prior is not None:
            return {name: [point(index, rational(item["raw"]) if item["raw"] is not None else None, initialized=item["initialized"],
                offset=item["display_offset"], first=item["source_range"][0], units=item["units"]) for index, item in enumerate(points)] for name, points in prior.items()}
        from nautilus_trader.indicators import averages, momentum, trend, volatility

        for module in (averages, momentum, trend, volatility):
            native_source(module)
        family = settings["family"]
        names = {"kama": ["kama"], "cci": ["cci"], "donchian": ["upper", "middle", "lower"],
            "ichimoku": ["tenkan", "kijun", "span_a", "span_b", "chikou"]}[family]
        result = {name: [] for name in names}
        indicator, channel, closes, prior_segment, seed, start = None, None, [], None, None, 0
        for index, row in enumerate(rows):
            if row["segment"] != prior_segment or row["gap_before"] or row["reasons"]:
                closes, indicator, channel, seed, start = [], None, None, None, index
            prior_segment = row["segment"]
            if row["reasons"]:
                for name in names:
                    result[name].append(point(index, None, initialized=False))
                continue
            high, low, close = (float(row["raw"][key]) for key in ("h", "l", "c"))
            if not all(math.isfinite(value) for value in (high, low, close)):
                raise ValueError("Native study input cannot be represented as finite binary64")
            closes.append(close)
            if family == "kama":
                n = settings["period"]
                if seed is None:
                    seed = close
                ready = len(closes) >= n + 1
                if ready:
                    window = closes[-n - 1:]
                    volatility_sum = sum(abs(right - left) for left, right in zip(window, window[1:], strict=False))
                    efficiency = abs(window[-1] - window[0]) / volatility_sum if volatility_sum else 0.0
                    slow, fast = 2.0 / (settings["slow"] + 1), 2.0 / (settings["fast"] + 1)
                    seed += (efficiency * (fast - slow) + slow) ** 2 * (close - seed)
                result["kama"].append(point(index, seed, initialized=ready, first=start))
            elif family == "cci":
                if indicator is None:
                    indicator = momentum.CommodityChannelIndex(settings["period"], float(settings["scalar"]), None)
                indicator.update_raw(high, low, close)
                result["cci"].append(point(index, indicator.value, initialized=indicator.initialized, first=max(start, index - settings["period"] + 1), units="scalar"))
            elif family == "donchian":
                if indicator is None:
                    indicator = volatility.DonchianChannel(settings["period"])
                indicator.update_raw(high, low)
                for name in names:
                    result[name].append(point(index, getattr(indicator, name), initialized=indicator.initialized,
                        first=max(start, index - settings["period"] + 1)))
            else:
                if indicator is None:
                    indicator = trend.IchimokuCloud(settings["tenkan"], settings["kijun"], settings["senkou"], max(1, settings["displacement"]))
                    channel = volatility.DonchianChannel(settings["senkou"])
                indicator.update_raw(high, low, close)
                channel.update_raw(high, low)
                values = {"tenkan": (indicator.tenkan_sen, len(closes) >= settings["tenkan"], 0),
                    "kijun": (indicator.kijun_sen, len(closes) >= settings["kijun"], 0),
                    "span_a": ((indicator.tenkan_sen + indicator.kijun_sen) / 2, len(closes) >= settings["kijun"], settings["displacement"]),
                    "span_b": (channel.middle, channel.initialized, settings["displacement"]), "chikou": (close, True, -settings["displacement"])}
                for name, (value, ready, shift) in values.items():
                    result[name].append(point(index, value, initialized=ready, offset=shift, first=start))
        if family == "donchian" and settings["lag"]:
            lag = settings["lag"]
            for name in names:
                original = result[name]
                result[name] = [point(index, original[index - lag]["raw"] if index >= lag and rows[index - lag]["segment"] == row["segment"]
                    and not any(rows[i]["gap_before"] or rows[i]["reasons"] for i in range(index - lag + 1, index + 1)) else None,
                    initialized=index >= lag and original[index - lag]["initialized"], first=max(0, index - lag - settings["period"] + 1)) for index, row in enumerate(rows)]
                for item in result[name]:
                    if item["raw"] is not None:
                        item["raw"] = str(item["raw"])
        return remember(key, result)

    def transform(settings):
        family, previous_segment, state, first = settings["family"], None, {}, 0
        input_outputs, seeds = {}, []

        def emit(index, opening, closing, *, high=None, low=None, geometry=None, direction=None, column=None, style=None):
            if len(events) >= 100000:
                raise ValueError("Transform exceeds the visible output-event budget; no truncation")
            row = rows[index]
            events.append({"output_ordinal": len(events), "source_ordinal": index, "source_range": [first, index],
                "input_output_ordinal": input_outputs.get(index, 0),
                "t": row["t"], "origin_at": row["source_timestamp"], "closed_at": row["closed_at"],
                "source_available_at": row["available_at"], "calculated_at": calculated_at,
                "available_at": max(instant(row["available_at"]), instant(calculated_at), instant(definition["updated_at"])).isoformat(), "segment": row["segment"],
                "ohlc": {"open": str(opening), "high": str(max(opening, closing) if high is None else high),
                    "low": str(min(opening, closing) if low is None else low), "close": str(closing)},
                "geometry": geometry, "direction": direction, "column": column, "style": style,
                "closed": True, "provisional": False, "derived": True, "volume": None, "history_prefix_sha256": row["history_prefix_sha256"]})
            input_outputs[index] = input_outputs.get(index, 0) + 1

        for index, row in enumerate(rows):
            if row["segment"] != previous_segment or row["gap_before"] or row["reasons"]:
                state, first = {}, index
            previous_segment = row["segment"]
            if row["reasons"]:
                provisional.append({"source_ordinal": index, "t": row["t"], "reasons": row["reasons"], "completed": False})
                continue
            x = rational(row["raw"]["c"])
            if not state:
                seed = {"source_ordinal": index, "t": row["t"], "actual_close": str(x), "derived": True}
                if family == "point_figure":
                    seed["grid_anchor"] = str((x // rational(settings["box_size"])) * rational(settings["box_size"]))
                if family == "kagi":
                    seed.update(shoulder=str(x), waist=str(x), basis="bootstrap extrema are derived seed values")
                seeds.append(seed)
            if family == "heikin_ashi":
                o, h, low, c = (rational(row["raw"][key]) for key in ("o", "h", "l", "c"))
                close = (o + h + low + c) / 4
                opening = (state["open"] + state["close"]) / 2 if state else (o + c) / 2
                emit(index, opening, close, high=max(h, opening, close), low=min(low, opening, close))
                state = {"open": opening, "close": close}
            elif family == "renko":
                box, reversal = rational(settings["box_size"]), settings["reversal"]
                if not state:
                    state = {"close": x, "direction": 0}
                while True:
                    p, direction = state["close"], state["direction"]
                    up, down = x >= p + box, x <= p - box
                    if direction >= 0 and up:
                        opening, close, direction = p, p + box, 1
                    elif direction <= 0 and down:
                        opening, close, direction = p, p - box, -1
                    elif direction == 1 and x <= p - reversal * box:
                        opening, close, direction = p - (reversal - 1) * box, p - reversal * box, -1
                    elif direction == -1 and x >= p + reversal * box:
                        opening, close, direction = p + (reversal - 1) * box, p + reversal * box, 1
                    else:
                        break
                    emit(index, opening, close, direction=direction)
                    state.update(close=close, direction=direction)
                provisional.append({"source_ordinal": index, "t": row["t"], "anchor": str(state["close"]), "actual_close": str(x), "completed": False})
            elif family == "line_break":
                if not state:
                    state = {"seed": x, "lines": []}
                lines = state["lines"]
                if not lines and x != state["seed"]:
                    opening = state["seed"]
                elif lines:
                    last, lookback = lines[-1], lines[-settings["lines"]:]
                    direction = 1 if last[1] > last[0] else -1
                    if direction == 1 and x > last[1] or direction == -1 and x < last[1]:
                        opening = last[1]
                    elif direction == 1 and x < min(min(line) for line in lookback) or direction == -1 and x > max(max(line) for line in lookback):
                        opening = last[0]
                    else:
                        continue
                else:
                    continue
                lines.append((opening, x))
                emit(index, opening, x, direction=1 if x > opening else -1)
            elif family == "point_figure":
                box, reversal = rational(settings["box_size"]), settings["reversal"]
                if not state:
                    state = {"level": x // box, "direction": 0, "column": 0}
                i, direction = state["level"], state["direction"]
                floor, ceil = x // box, -((-x) // box)
                if direction >= 0 and floor >= i + 1:
                    target, step = floor, 1
                elif direction <= 0 and ceil <= i - 1:
                    target, step = ceil, -1
                elif direction == 1 and ceil <= i - reversal:
                    target, step = ceil, -1
                    state["column"] += 1
                elif direction == -1 and floor >= i + reversal:
                    target, step = floor, 1
                    state["column"] += 1
                else:
                    continue
                if direction == 0:
                    emit(index, i * box, i * box, direction=step, column=state["column"], style="X" if step == 1 else "O")
                for level in range(int(i + step), int(target + step), step):
                    emit(index, level * box, level * box, direction=step, column=state["column"], style="X" if step == 1 else "O")
                state.update(level=target, direction=step)
            else:
                if not state:
                    state = {"endpoint": x, "direction": 0, "shoulder": x, "waist": x, "style": "thin", "column": 0}
                    continue
                p, direction = state["endpoint"], state["direction"]
                amount = rational(settings["reversal_amount"])
                threshold = p - amount if direction == 1 else p + amount
                if settings["reversal_kind"] == "percent":
                    threshold = p * (1 - amount / 100 if direction == 1 else 1 + amount / 100)
                reverse = direction == 1 and x <= threshold or direction == -1 and x >= threshold
                if direction == 0 and x != p:
                    direction = 1 if x > p else -1
                    state["style"] = "thick" if direction == 1 else "thin"
                elif reverse:
                    state["shoulder" if direction == 1 else "waist"] = p
                    direction = -direction
                    state["column"] += 1
                elif direction == 1 and x <= p or direction == -1 and x >= p or x == p:
                    continue
                boundary = state["shoulder"] if direction == 1 else state["waist"]
                crossed = direction == 1 and p <= boundary < x or direction == -1 and p >= boundary > x
                if crossed and p != boundary:
                    emit(index, p, boundary, geometry={"kind": "vertical", "reversal": reverse}, direction=direction, column=state["column"], style=state["style"])
                    p = boundary
                if crossed:
                    state["style"] = "thick" if direction == 1 else "thin"
                emit(index, p, x, geometry={"kind": "vertical", "reversal": reverse}, direction=direction, column=state["column"], style=state["style"])
                state.update(endpoint=x, direction=direction)
        return {"family": family, "threshold_arithmetic": "exact rational; raw may be numerator/denominator", "seed_policy": "new explicit seed after each unknown gap",
            "provisional": provisional, "seeds": seeds, "events": events}

    definitions = {item["name"]: item for item in [*spec["dependencies"], definition]}
    active, cache = set(), {}
    shared_cache = shared_cache if shared_cache is not None else {}
    identities = {}

    def calculation_identity(item):
        import ast

        name = item["name"]
        if name not in identities:
            dependencies = {}
            if item["kind"] == "formula":
                for node in ast.walk(formula_tree(item["settings"]["expression"])):
                    if isinstance(node, ast.Name):
                        dependency = node.id.partition("__")[0]
                        if dependency in definitions and dependency != name and node.id not in item["settings"]["parameters"]:
                            dependencies[dependency] = calculation_identity(definitions[dependency])
            identities[name] = digest({"source": spec["source_sha256"], "definition": item, "dependencies": dependencies})
        return identities[name]

    def reused(key):
        entry = shared_cache.get(key)
        if entry is not None:
            native_sources.update(entry["native"])
            return entry["result"]
        return None

    def remember(key, value):
        shared_cache[key] = {"result": value, "native": dict(native_sources)}
        return value

    def vector(values, units, lookback=0, *, constant=False):
        return {"values": values, "units": units, "lookback": lookback, "constant": constant}

    def compute_formula(item, overrides=None):
        import ast

        name, settings = item["name"], item["settings"]
        key = calculation_identity(item) + digest({name: {**value, "values": [str(number) for number in value["values"]]}
            for name, value in (overrides or {}).items()})
        prior = reused(key)
        if prior is not None:
            return prior
        if name in active:
            raise ValueError("Cyclic reusable formula dependencies are unavailable")
        active.add(name)
        parameters = {key: vector([rational(value["value"])] * len(rows), value["units"], constant=True) for key, value in settings["parameters"].items()}
        parameters.update(overrides or {})

        def operand(node):
            if isinstance(node, ast.Constant):
                token = ast.get_source_segment(settings["expression"], node)
                return vector([rational(token)] * len(rows), "scalar", constant=True)
            if isinstance(node, ast.Name):
                if node.id in parameters:
                    return parameters[node.id]
                raw_key = {"open": "o", "high": "h", "low": "l", "close": "c", "volume": "v"}.get(node.id)
                if raw_key:
                    return vector([rational(row["raw"][raw_key]) if not row["reasons"] else None for row in rows], "volume" if raw_key == "v" else "price")
                dependency_name, _, component = node.id.partition("__")
                if dependency_name not in definitions or dependency_name == name:
                    raise ValueError("Formula name must resolve an exact declared dependency revision")
                outputs = compute_definition(definitions[dependency_name])
                if component:
                    if component not in outputs:
                        raise ValueError("Unknown dependency output component")
                    return outputs[component]
                if len(outputs) != 1:
                    raise ValueError("Multi-output study references need dependency__component")
                return next(iter(outputs.values()))
            if isinstance(node, ast.UnaryOp):
                value = operand(node.operand)
                if value["units"] == "boolean":
                    raise ValueError("Boolean series cannot be signed")
                return {**value, "values": [(-x if isinstance(node.op, ast.USub) else x) if x is not None else None for x in value["values"]]}
            if isinstance(node, (ast.BinOp, ast.Compare)):
                if isinstance(node, ast.Compare) and len(node.comparators) != 1:
                    raise ValueError("Use explicit separate comparisons in where expressions")
                left = operand(node.left)
                right = operand(node.right if isinstance(node, ast.BinOp) else node.comparators[0])
                operation = node.op if isinstance(node, ast.BinOp) else node.ops[0]
                if isinstance(operation, (ast.Add, ast.Sub, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq)):
                    if left["units"] != right["units"]:
                        raise ValueError("Addition, subtraction and comparison require identical units")
                    units = "boolean" if isinstance(node, ast.Compare) else left["units"]
                elif isinstance(operation, ast.Mult):
                    if "scalar" not in (left["units"], right["units"]):
                        raise ValueError("Multiplication requires an explicit dimensionless scalar")
                    units = right["units"] if left["units"] == "scalar" else left["units"]
                elif isinstance(operation, ast.Div):
                    if right["units"] != "scalar" and left["units"] != right["units"]:
                        raise ValueError("Division requires matching dimensions or a scalar divisor")
                    units = left["units"] if right["units"] == "scalar" else "scalar"
                else:
                    if (right["units"] != "scalar" or not right["constant"] or len(set(right["values"])) != 1 or right["values"][0].denominator != 1
                            or not 0 <= right["values"][0] <= 8 or left["units"] != "scalar" and right["values"][0] not in (0, 1)):
                        raise ValueError("Powers require a bounded constant integer and compatible dimensions")
                    units = "scalar" if right["values"][0] == 0 else left["units"]
                values = []
                for a, b in zip(left["values"], right["values"], strict=True):
                    if a is not None and b is not None:
                        bits = max(abs(a.numerator).bit_length(), a.denominator.bit_length())
                        other = max(abs(b.numerator).bit_length(), b.denominator.bit_length())
                        expected = bits * int(b) if isinstance(operation, ast.Pow) else 2 * (bits + other)
                        if expected > 65536:
                            raise ValueError("Formula intermediate rational exceeds the published bit budget; no approximation is substituted")
                    if a is None or b is None or isinstance(operation, ast.Div) and b == 0:
                        values.append(None)
                    elif isinstance(operation, ast.Add):
                        values.append(a + b)
                    elif isinstance(operation, ast.Sub):
                        values.append(a - b)
                    elif isinstance(operation, ast.Mult):
                        values.append(a * b)
                    elif isinstance(operation, ast.Div):
                        values.append(a / b)
                    elif isinstance(operation, ast.Pow):
                        values.append(a ** int(b))
                    else:
                        values.append({ast.Gt: a > b, ast.GtE: a >= b, ast.Lt: a < b, ast.LtE: a <= b, ast.Eq: a == b, ast.NotEq: a != b}[type(operation)])
                return vector(values, units, max(left["lookback"], right["lookback"]), constant=left["constant"] and right["constant"])
            if not isinstance(node, ast.Call):
                raise ValueError("Unsupported formula operation")
            function, arguments = node.func.id, [operand(argument) for argument in node.args]
            if function in definitions:
                dependency = definitions[function]
                if dependency["kind"] != "formula":
                    raise ValueError("Only exact reusable formula definitions can be called")
                declared = dependency["settings"]["parameters"]
                names = sorted(declared)
                if len(arguments) != len(declared) or any(argument["units"] != declared[key]["units"] for argument, key in zip(arguments, names, strict=True)):
                    raise ValueError("Reusable function arguments must match the exact typed parameter list")
                return compute_formula(dependency, dict(zip(names, arguments, strict=True)))
            if function == "where":
                if len(arguments) != 3 or arguments[0]["units"] != "boolean" or arguments[1]["units"] != arguments[2]["units"]:
                    raise ValueError("where requires a boolean condition and equally typed alternatives")
                return vector([None if condition is None else a if condition else b for condition, a, b in zip(*(arg["values"] for arg in arguments), strict=True)],
                    arguments[1]["units"], max(arg["lookback"] for arg in arguments), constant=all(arg["constant"] for arg in arguments))
            if function == "abs" and len(arguments) == 1:
                return {**arguments[0], "values": [abs(x) if x is not None else None for x in arguments[0]["values"]]}
            if function == "scale" and len(arguments) == 2 and arguments[1]["units"] == "scalar":
                for a, b in zip(arguments[0]["values"], arguments[1]["values"], strict=True):
                    if a is not None and b is not None and 2 * (max(abs(a.numerator).bit_length(), a.denominator.bit_length()) + max(abs(b.numerator).bit_length(), b.denominator.bit_length())) > 65536:
                        raise ValueError("Formula intermediate rational exceeds the published bit budget; no approximation is substituted")
                return vector([a * b if a is not None and b is not None else None for a, b in zip(arguments[0]["values"], arguments[1]["values"], strict=True)],
                    arguments[0]["units"], max(arg["lookback"] for arg in arguments), constant=all(arg["constant"] for arg in arguments))
            if function not in {"lag", "rolling_min", "rolling_max", "rolling_sum", "rolling_mean", "sma", "ema"} or len(arguments) != 2:
                raise ValueError("Unsupported function or arity")
            source, period = arguments
            if period["units"] != "scalar" or not period["constant"] or len(set(period["values"])) != 1 or period["values"][0] is None or period["values"][0].denominator != 1:
                raise ValueError("Lookback must be an exact constant integer; dynamic and future offsets are forbidden")
            n = chart_integer(int(period["values"][0]), zero=function == "lag")
            values, indicator = [], None
            if function in {"sma", "ema"}:
                from nautilus_trader.indicators import averages

                native_source(averages)
            for index, value in enumerate(source["values"]):
                if row_gap(index) or value is None:
                    indicator = None
                if function == "lag":
                    values.append(source["values"][index - n] if index >= n and rows[index - n]["segment"] == rows[index]["segment"] and not any(rows[i]["gap_before"] for i in range(index - n + 1, index + 1)) else None)
                elif function in {"sma", "ema"}:
                    if value is None:
                        values.append(None)
                        continue
                    if indicator is None:
                        indicator = (averages.SimpleMovingAverage if function == "sma" else averages.ExponentialMovingAverage)(n)
                    native_value = float(value)
                    if not math.isfinite(native_value):
                        raise ValueError("Formula native-operation input cannot be represented as finite binary64")
                    indicator.update_raw(native_value)
                    values.append(Fraction(str(indicator.value)) if indicator.initialized else None)
                else:
                    window = source["values"][max(0, index - n + 1):index + 1]
                    if len(window) != n or any(v is None for v in window) or any(row_gap(i) for i in range(index - n + 2, index + 1)):
                        values.append(None)
                    elif function == "rolling_min":
                        values.append(min(window))
                    elif function == "rolling_max":
                        values.append(max(window))
                    else:
                        values.append(sum(window) / (n if function == "rolling_mean" else 1))
            return vector(values, source["units"], source["lookback"] + n)

        try:
            result = operand(formula_tree(settings["expression"]).body)
            if result["units"] != settings["units"]:
                raise ValueError("Formula output units differ from the declared units")
            return remember(key, result)
        finally:
            active.remove(name)

    def row_gap(index):
        return bool(rows[index]["reasons"] or rows[index]["gap_before"] or index and rows[index]["segment"] != rows[index - 1]["segment"])

    def compute_definition(item):
        name = item["name"]
        if name in cache:
            return cache[name]
        key = calculation_identity(item)
        prior = reused(key)
        if prior is not None:
            cache[name] = prior
            return prior
        if item["kind"] == "formula":
            result = {name: compute_formula(item)}
        elif item["kind"] == "study":
            result = {key: vector([rational(p["raw"]) if p["initialized"] and p["raw"] is not None else None for p in points],
                points[0]["units"] if points else "price", item["settings"].get("period", item["settings"].get("senkou", 0))) for key, points in study(item["settings"]).items()}
        else:
            raise ValueError("Formula dependencies must be causal study or formula definitions; transformed coordinates are not raw prices")
        cache[name] = result
        return remember(key, result)

    settings, transform_result, seasonal = definition["settings"], None, None
    if definition["kind"] == "transform":
        transform_result = transform(settings)
    elif definition["kind"] == "study":
        series = [{"name": name, "units": "scalar" if settings["family"] == "cci" else "price", "points": points} for name, points in study(settings).items()]
    elif definition["kind"] == "formula":
        value = compute_formula(definition)
        series = [{"name": definition["name"], "units": value["units"], "lookback": value["lookback"], "render": settings["render"],
            "points": [point(index, x, offset=settings["display_shift"], first=max(0, index - value["lookback"]), units=value["units"]) for index, x in enumerate(value["values"])]}]
    else:
        seasonal = calculate_seasonality(spec)
    implementation = {"version": CHART_VERSION, "worker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "native": native_sources, "thresholds": "exact fractions from source decimal strings", "studies": "native float64; KAMA conventional squared float64 first-close seed",
        "kama_seed": "first_source_close held unchanged until full N+1 closes; flat ER=0; reset after any gap",
        "display": "Offsets are display positions only; origin and availability are unchanged; no future observed data"}
    valid_seed = bool(transform_result and transform_result["seeds"])
    result = {"kind": "chart_calculation", "version": CHART_VERSION, "status": "completed" if valid_seed or any(p["initialized"] for s in series for p in s["points"]) or seasonal and seasonal["eligible_years"] else "unavailable",
        "empty_transform_reason": "Valid segment seeds have not produced a completed threshold event" if valid_seed and not events else None,
        "spec_sha256": spec["spec_sha256"], "definition_sha256": spec["definition_sha256"], "source_pin": spec["source_pin"],
        "derivation_identity": digest({"implementation": implementation, "definition": definition, "dependencies": spec["dependencies"], "source_sha256": spec["source_sha256"]}),
        "implementation": implementation, "series": series, "events": events, "transform": transform_result, "seasonality": seasonal,
        "calculated_at": calculated_at, "source_rows": rows,
        "coverage": {"complete": not any(row["reasons"] or row["gap_before"] for row in rows), "source_rows": len(rows),
            "unavailable_source_ordinals": [i for i, row in enumerate(rows) if row["reasons"]],
            "unverified_continuity_before": [i for i, row in enumerate(rows) if row["gap_before"]]},
        "limitations": spec["source_limitations"] + ["Synthetic coordinates are not observed executable prices or actual volume.",
            "Parameterized studies use native binary64 arithmetic; no exact external-platform parity is claimed."]}
    result["result_sha256"] = digest(result)
    return result


def calculate_scan(spec):
    """Calculate original axes once, then retain backward closed-bar aligned evidence."""
    import copy
    from bisect import bisect_right
    from datetime import UTC, datetime
    from fractions import Fraction
    from pathlib import Path

    from evaluation import SCAN_VERSION, validate_scan_calculation, validate_scan_result

    validate_scan_calculation(spec)
    calculated_at = datetime.now(UTC).isoformat()
    cutoff = instant(spec["market_cutoff"])
    axes, calculation_results, calculation_specs, shared_cache = copy.deepcopy(spec["axes"]), {}, {}, {}
    aggregation_implementation = {}

    def aggregate(axis):
        from nautilus_trader.data import aggregation
        from nautilus_trader.model import data, objects
        from nautilus_trader.model.currencies import USD
        from nautilus_trader.model.identifiers import InstrumentId, Symbol
        from nautilus_trader.model.instruments import equity

        contract, originals = axis["aggregation"], axis["rows"]
        if importlib.metadata.version("nautilus_trader") != "1.231.0":
            raise ValueError("Scanner native aggregation version differs from the pinned implementation")
        for module in (aggregation, data, objects, equity):
            path = Path(module.__file__)
            aggregation_implementation[module.__name__] = {"version": "1.231.0", "binary_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source_sha256": hashlib.sha256(path.with_name(path.name.split(".")[0] + ".pyx").read_bytes()).hexdigest()}
        precision = max((max(0, -Decimal(value).as_tuple().exponent) for row in originals if row["raw"] for key, value in row["raw"].items() if key != "v"), default=0)
        symbol = axis["source"]["symbol"]
        instrument_id = InstrumentId.from_str(symbol + ".SCAN")
        increment = "1" if precision == 0 else "0." + "0" * (precision - 1) + "1"
        instrument = equity.Equity(instrument_id, Symbol(symbol), USD, precision, objects.Price.from_str(increment), objects.Quantity.from_int(1), 0, 0)
        minutes = {str(row["t"]): row for row in originals}
        minute_type = data.BarType.from_str(symbol + ".SCAN-1-MINUTE-LAST-EXTERNAL")
        step = {"5Min": 5, "15Min": 15, "30Min": 30, "1Hour": 60}[contract["timeframe"]]
        output_type = data.BarType.from_str(f"{symbol}.SCAN-{step}-MINUTE-LAST-INTERNAL")
        output, coverage, segment, gap = [], [], 0, False
        basis = contract.get("absence_basis") or {}
        for expected_ordinal, bucket in enumerate(contract["buckets"]):
            constituents, missing, absent, invalid = [], [], [], []
            for minute in bucket["expected_minutes"]:
                row = minutes.get(str(minute))
                if row is not None:
                    constituents.append(row)
                    if row["reasons"] or not row["closed"]:
                        invalid.append(minute)
                elif (contract.get("absence_proven") is True and basis.get("start_at") and basis.get("end_at")
                        and instant(basis["start_at"]).timestamp() <= float(minute)
                        and float(minute) + 60 <= instant(basis["end_at"]).timestamp()):
                    absent.append(minute)
                else:
                    missing.append(minute)
            receipt = {**bucket, "expected_ordinal": expected_ordinal, "constituent_source_ordinals": [row["source_ordinal"] for row in constituents],
                "unknown_missing_minutes": missing, "provider_reported_no_eligible_bar_minutes": absent, "invalid_minutes": invalid,
                "absence_basis": basis if absent else None, "status": "unavailable" if missing or invalid else "no_eligible_bar" if not constituents else "available"}
            if instant(bucket["closed_at"]) > cutoff or missing or invalid or not constituents:
                coverage.append(receipt)
                gap = gap or bool(missing or invalid)
                continue
            try:
                builder = aggregation.BarBuilder(instrument, output_type)
                for row in constituents:
                    prices = [objects.Price.from_str(format(Decimal(row["raw"][key]), "f")) for key in ("o", "h", "l", "c")]
                    if any(Decimal(str(price)) != Decimal(row["raw"][key]) for price, key in zip(prices, ("o", "h", "l", "c"), strict=True)):
                        raise ValueError("Source OHLC cannot be represented exactly by native Price")
                    volume = Decimal(row["raw"]["v"])
                    if volume != volume.to_integral_value():
                        raise ValueError("Native equity aggregation requires exact integer source volume; no rounding is performed")
                    quantity = objects.Quantity.from_str(format(volume.to_integral_value(), "f"))
                    if Decimal(str(quantity)) != volume:
                        raise ValueError("Source volume cannot be represented exactly by native Quantity")
                    timestamp = int(instant(row["closed_at"]).timestamp() * 1000000000)
                    bar = data.Bar(minute_type, *prices, quantity, int(float(row["t"]) * 1000000000), timestamp)
                    builder.update_bar(bar, quantity, timestamp)
                timestamp = int(instant(bucket["closed_at"]).timestamp() * 1000000000)
                built = builder.build(timestamp, timestamp)
                raw = {key: str(value) for key, value in zip(("o", "h", "l", "c", "v"), (built.open, built.high, built.low, built.close, built.volume), strict=True)}
            except (ValueError, OverflowError, TypeError) as error:
                receipt.update(status="unavailable", error=str(error))
                coverage.append(receipt)
                gap = True
                continue
            if gap:
                segment += 1
            output.append({"t": bucket["t"], "source_ordinal": len(output), "segment": segment, "raw": raw, "closed": True,
                "closed_at": bucket["closed_at"], "available_at": max((row["available_at"] for row in constituents), key=instant),
                "closure_basis": "Explicit regular session partition anchored at actual calendar open and clipped at actual close",
                "source_timestamp": [row["source_timestamp"] for row in constituents], "gap_before": gap, "reasons": [],
                "expected_ordinal": expected_ordinal, "constituent_source_ordinals": receipt["constituent_source_ordinals"],
                "partial_session_close": bucket["partial_session_close"]})
            coverage.append(receipt)
            gap = False
        prefix = hashlib.sha256()
        for row in output:
            prefix.update(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())
            row["history_prefix_sha256"] = prefix.hexdigest()
        axis.update(rows=output, original_rows=originals, aggregation_coverage=coverage,
            expected_buckets=[{"t": row["t"], "closed_at": row["closed_at"]} for row in contract["buckets"]])
        axis["source"] = {**axis["source"], "timeframe": contract["timeframe"], "derived_profile": contract["version"],
            "aggregation_implementation": dict(aggregation_implementation), "representation_price_precision": precision,
            "representation_size_precision": 0, "representation_basis": "Calculation-only source decimal precision; no exchange tick or order authority"}
        axis["source_sha256"] = digest({key: axis[key] for key in ("source", "rows", "calendar_coverage")})

    for axis in axes.values():
        if axis.get("aggregation") and axis["axis_status"] == "available":
            try:
                aggregate(axis)
            except (ValueError, OverflowError, TypeError) as error:
                axis["axis_status"] = "unavailable"
                axis["axis_reasons"].append("Native aggregation unavailable: " + str(error))
    for binding in spec["bindings"].values():
        if binding["calculation"] is None or binding["calculation"] in calculation_results:
            continue
        axis = axes[binding["axis"]]
        if not axis["rows"] or axis["axis_status"] != "available":
            continue
        chart_spec = copy.deepcopy(spec["calculations"][binding["calculation"]])
        chart_spec.update({key: axis[key] for key in ("rows", "source", "calendar", "calendar_coverage", "source_sha256", "source_limitations")})
        chart_spec["spec_sha256"] = digest({key: value for key, value in chart_spec.items() if key != "spec_sha256"})
        calculation_specs[binding["calculation"]] = chart_spec
        calculation_results[binding["calculation"]] = calculate_chart(chart_spec, shared_cache)
    values, expected_times, candidate_times, candidates = {}, {}, {}, {}
    for name, binding in spec["bindings"].items():
        axis, selected = axes[binding["axis"]], spec["program"]["inputs"][name]
        expected_times[name] = [instant(row["closed_at"]) for row in axis["expected_buckets"]]
        points = []
        if binding["calculation"] is None:
            field = {"open": "o", "high": "h", "low": "l", "close": "c", "volume": "v"}[selected["value"]["field"]]
            points = [{"raw": row["raw"][field] if row["raw"] else None, "units": "volume" if field == "v" else "price",
                "initialized": not row["reasons"], "calculated_at": calculated_at, "available_at": max(row["available_at"], calculated_at, key=instant) if row["available_at"] else calculated_at} for row in axis["rows"]]
        elif binding["calculation"] in calculation_results:
            output = next((series for series in calculation_results[binding["calculation"]]["series"] if series["name"] == selected["value"]["output"]), None)
            points = output["points"] if output else []
        values[name] = points
        candidates[name] = [(index, row) for index, row in enumerate(axis["rows"]) if row["closed_at"] and row["closed"]
            and not row["reasons"] and index < len(points) and points[index]["raw"] is not None and points[index]["initialized"]]
        candidate_times[name] = [instant(row["closed_at"]) for _, row in candidates[name]]
    program, observations = spec["program"], []
    anchor_axis = axes[spec["bindings"][program["anchor_input"]]["axis"]]
    strict_reason = "Known-then source revisions and definition knowledge evidence is unavailable; choose evaluate_now for disclosed retrospective evaluation"

    def operand(item, aligned):
        if item["kind"] == "input":
            return aligned[item["name"]]
        value = program["parameters"][item["name"]] if item["kind"] == "parameter" else item
        return {"value": value["value"], "units": value["units"], "eligible": True, "reasons": []}

    def number(value):
        return value == "True" if value in {"True", "False"} else Fraction(value)

    for anchor in anchor_axis["rows"]:
        if not anchor["closed_at"] or not anchor["closed"] or instant(anchor["closed_at"]) > cutoff:
            continue
        at, aligned = instant(anchor["closed_at"]), {}
        for name, binding in spec["bindings"].items():
            axis, selected = axes[binding["axis"]], program["inputs"][name]
            expected_index = bisect_right(expected_times[name], at) - 1
            expected = axis["expected_buckets"][expected_index] if expected_index >= 0 else None
            position = bisect_right(candidate_times[name], at) - 1
            index, row = candidates[name][position] if position >= 0 else (None, None)
            point = values[name][index] if row is not None else {}
            age = expected_index - row["expected_ordinal"] if row is not None and type(row.get("expected_ordinal")) is int and expected_index >= 0 else None
            reasons = list(axis["axis_reasons"])
            if row is None:
                reasons.append("No eligible closed initialized original-axis input exists at this actual anchor")
            if age is None or age < 0 or age > selected["max_staleness_buckets"]:
                reasons.append("Input does not cover its latest expected completed bucket within the saved staleness allowance")
            if program["time_basis"] == "known_then":
                reasons.append(strict_reason)
            aligned[name] = {"value": point.get("raw"), "units": point.get("units"), "eligible": not reasons,
                "source_ordinal": index, "source_identity": digest({"source": axis["source_sha256"], "row": row}) if row else None,
                "source_sha256": axis["source_sha256"], "source_pin": axis["source_pin"], "t": row["t"] if row else None,
                "closed_at": row["closed_at"] if row else None, "source_available_at": row["available_at"] if row else None,
                "calculated_at": point.get("calculated_at"), "available_at": point.get("available_at"),
                "segment": row["segment"] if row else None, "gap_before": row["gap_before"] if row else None,
                "expected_latest_bucket": expected, "age_buckets": age, "max_staleness_buckets": selected["max_staleness_buckets"],
                "coverage_complete": not reasons and age == 0 and not row["gap_before"], "reasons": reasons}
        condition_results = []
        previous = observations[-1] if observations else None
        for condition in program["conditions"]:
            left, right = operand(condition["left"], aligned), operand(condition["right"], aligned)
            reasons = [*left["reasons"], *right["reasons"]]
            if left["units"] != right["units"]:
                reasons.append("Comparison operands have different semantic units")
            eligible = left["eligible"] and right["eligible"] and not reasons and not anchor["reasons"] and anchor_axis["axis_status"] == "available"
            residual, evaluation, prior_evidence = None, "unavailable", None
            if eligible:
                a, b = number(left["value"]), number(right["value"])
                if isinstance(a, bool) or isinstance(b, bool):
                    eligible = condition["comparison"] == "eq" and type(a) is type(b)
                    if not eligible:
                        reasons.append("Boolean inputs support equality with another boolean input")
                else:
                    residual = str(a - b)
                if eligible and condition["comparison"] in {"cross_above", "cross_below"}:
                    old_left = operand(condition["left"], previous["inputs"]) if previous else None
                    old_right = operand(condition["right"], previous["inputs"]) if previous else None
                    continuous = bool(previous and not anchor["gap_before"] and previous["anchor"]["segment"] == anchor["segment"]
                        and not previous["anchor"]["reasons"] and old_left["eligible"] and old_right["eligible"])
                    for item in (condition["left"], condition["right"]):
                        if item["kind"] == "input" and previous:
                            before, current = previous["inputs"][item["name"]], aligned[item["name"]]
                            continuous = continuous and before["segment"] == current["segment"] and (before["source_ordinal"] == current["source_ordinal"] or not current["gap_before"])
                    if continuous:
                        prior_residual = number(old_left["value"]) - number(old_right["value"])
                        prior_evidence = {"anchor": previous["anchor"], "inputs": previous["inputs"], "left": old_left, "right": old_right, "residual": str(prior_residual)}
                        matched = prior_residual <= 0 and a > b if condition["comparison"] == "cross_above" else prior_residual >= 0 and a < b
                        evaluation = "true" if matched else "false"
                    else:
                        reasons.append("Crossing requires two consecutive eligible actual anchors with independent aligned evidence and no unknown gap")
                elif eligible:
                    matched = {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b, "eq": a == b}[condition["comparison"]]
                    evaluation = "true" if matched else "false"
            condition_results.append({"comparison": condition["comparison"], "left": left, "right": right, "residual": residual,
                "evaluation": evaluation, "previous": prior_evidence, "reasons": reasons})
        states = [item["evaluation"] for item in condition_results]
        evaluation = ("false" if "false" in states else "true" if all(value == "true" for value in states) else "unavailable") if program["operator"] == "ALL" else (
            "true" if "true" in states else "false" if all(value == "false" for value in states) else "unavailable")
        observation = {"anchor": anchor, "inputs": aligned, "conditions": condition_results, "evaluation": evaluation,
            "coverage_complete": all(item["coverage_complete"] for item in aligned.values()) and all(value != "unavailable" for value in states),
            "reasons": [*anchor["reasons"], *anchor_axis["axis_reasons"], *[reason for item in condition_results for reason in item["reasons"]]]}
        observation["observation_sha256"] = digest(observation)
        observations.append(observation)
    latest = observations[-1] if observations else None
    anchor_expected = [instant(row["closed_at"]) for row in anchor_axis["expected_buckets"]]
    cutoff_expected = bisect_right(anchor_expected, cutoff) - 1
    anchor_age = cutoff_expected - latest["anchor"]["expected_ordinal"] if latest and type(latest["anchor"].get("expected_ordinal")) is int else None
    anchor_fresh = anchor_age is not None and 0 <= anchor_age <= program["inputs"][program["anchor_input"]]["max_staleness_buckets"]
    evaluation = latest["evaluation"] if latest and anchor_fresh else "unavailable"
    reasons = list(latest["reasons"]) if latest else ["No eligible actual anchor observation is retained"]
    if not anchor_fresh:
        reasons.append("Actual anchor does not cover the latest expected completed anchor bucket at market cutoff within its saved staleness allowance")
    implementation = {"version": SCAN_VERSION, "formula_engine": "chart-calculation-v1", "worker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "aggregation": aggregation_implementation, "alignment": "original-axis causal calculations before backward closed_at alignment; carried values do not create bars",
        "crossing": "Previous/current actual anchor alignments, no unknown gap bridge", "time_basis": spec["time_basis"]}
    result = {"kind": "scanner_calculation", "version": SCAN_VERSION, "status": "unavailable" if evaluation == "unavailable" else "completed",
        "spec_sha256": spec["spec_sha256"], "program_sha256": digest(program), "evaluation": evaluation,
        "matched": None if evaluation == "unavailable" else evaluation == "true", "state": {"true": "triggered", "false": "clear", "unavailable": "unavailable"}[evaluation],
        "at": calculated_at, "input_identity": spec["spec_sha256"], "facts": latest, "calculated_at": calculated_at,
        "market_cutoff": spec["market_cutoff"], "captured_at": spec["captured_at"], "time_basis": spec["time_basis"],
        "observations": observations, "latest": latest, "axes": axes, "calculation_specs": calculation_specs, "calculations": calculation_results,
        "coverage_complete": bool(latest and latest["coverage_complete"] and anchor_age == 0),
        "coverage": {"complete": bool(latest and latest["coverage_complete"] and anchor_age == 0), "anchor_age_buckets": anchor_age,
            "latest_expected_anchor_bucket": anchor_axis["expected_buckets"][cutoff_expected] if cutoff_expected >= 0 else None}, "reasons": reasons,
        "implementation": implementation, "derivation_identity": digest({"spec": spec["spec_sha256"], "implementation": implementation}),
        "limitations": ["Retained source capture/revisions do not prove known-then availability; actual source knowledge and calculation times remain separate from market cutoff.",
            "Native aggregation is an explicitly defined regular-session derived profile, not provider coarse-bar parity; missing bars are never fabricated."]}
    result["result_sha256"] = digest(result)
    return validate_scan_result(result, spec)


def operand_value(operand, row, parameters):
    if operand["kind"] == "constant":
        return finite(operand["value"])
    if operand["kind"] == "parameter":
        return finite(parameters[operand["name"]])
    if operand["kind"] == "price":
        return Decimal(row[{"open": "o", "high": "h", "low": "l", "close": "c"}[operand["field"]]])
    point = row.get("indicators", {}).get(operand["name"], {})
    if (point.get("numerical_available") is not True or point.get("initialized") is not True or point.get("closed") is not True
            or not point.get("closed_at") or instant(point["closed_at"]) > instant(row["at"]) or point.get("raw") is None):
        return None
    return finite(point["raw"])


def rule_result(rule, row, previous, parameters):
    states, facts = [], []
    for atom in rule["atoms"]:
        left, right = (operand_value(atom[key], row, parameters) for key in ("left", "right"))
        prior = [operand_value(atom[key], previous, parameters) for key in ("left", "right")] if previous else [None, None]
        state = None
        if left is not None and right is not None:
            if atom["comparison"] == "above":
                state = left > right
            elif atom["comparison"] == "below":
                state = left < right
            elif all(item is not None for item in prior):
                state = prior[0] <= prior[1] and left > right if atom["comparison"] == "cross_above" else prior[0] >= prior[1] and left < right
        states.append(state)
        facts.append({"left": str(left) if left is not None else None, "right": str(right) if right is not None else None,
            "previous": [str(item) if item is not None else None for item in prior], "comparison": atom["comparison"], "state": state})
    state = (False if False in states else None if None in states else True) if rule["operator"] == "ALL" else (True if True in states else None if None in states else False)
    return {"state": state, "at": row["at"], "previous_at": previous["at"] if previous else None, "operator": rule["operator"], "atoms": facts}


def simulate_strategy(spec):
    """Execute typed closed-bar rules with public native OHLC conversion and accounting."""
    from pathlib import Path

    import pandas as pd
    from linked_orders import broker_payload, native_group, native_order
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.models import (
        FillModel,
        FixedFeeModel,
        LatencyModel,
        MakerTakerFeeModel,
    )
    from nautilus_trader.config import LoggingConfig, StrategyConfig
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.data import Bar, BarType
    from nautilus_trader.model.enums import AccountType, OmsType, OtoTriggerMode
    from nautilus_trader.model.identifiers import InstrumentId, Symbol, TraderId, Venue
    from nautilus_trader.model.instruments import Equity
    from nautilus_trader.model.objects import FIXED_PRECISION, Money, Price, Quantity
    from nautilus_trader.persistence import wranglers
    from nautilus_trader.persistence.wranglers import TradeTickDataWrangler
    from nautilus_trader.trading.strategy import Strategy

    if (spec.get("version") != EXPERIMENT_VERSION or spec.get("engine_version") != "1.231.0"
            or importlib.metadata.version("nautilus_trader") != "1.231.0"
            or digest({key: value for key, value in spec.items() if key != "spec_sha256"}) != spec.get("spec_sha256")
            or spec["starting_holdings"]):
        raise ValueError("Exact native version, empty starting portfolio and immutable strategy trial are required")
    strategy_definition = validate_strategy(spec["strategy"])
    parameters = spec["parameters"]
    if (set(parameters) != set(strategy_definition["parameters"])
            or any(value not in strategy_definition["parameters"][name]["values"] for name, value in parameters.items())):
        raise ValueError("Trial parameters differ from the immutable finite space")
    conversion = spec["conversion"]
    binary = Path(wranglers.__file__)
    if (hashlib.sha256(binary.read_bytes()).hexdigest() != conversion["binary_sha256"]
            or hashlib.sha256(binary.with_name("wranglers.pyx").read_bytes()).hexdigest() != conversion["source_sha256"]
            or conversion["settings"] != {"ts_init_delta": 0, "offset_interval_ms": 100, "timestamp_is_close": True,
                "random_seed": None, "is_raw": False, "sort_data": True}
            or conversion["bar_processing_offset_ns"] != 1 or conversion["bar_execution"] is not False or conversion["trade_execution"] is not True):
        raise ValueError("Installed public converter or declared simulation flags differ from the preview")
    precision = spec["representation"]["price_precision"]
    if type(precision) is not int or not 2 <= precision <= FIXED_PRECISION:
        raise ValueError("Source prices exceed native precision; no rounding is allowed")
    instrument_id = InstrumentId.from_str(strategy_definition["instrument_id"])
    venue = Venue("ALPACA")
    instrument = Equity(instrument_id, Symbol(strategy_definition["symbol"]), USD, precision,
        Price.from_str(spec["representation"]["price_increment"]), Quantity.from_int(1), 0, 0,
        maker_fee=Decimal(0), taker_fee=Decimal(0))
    segment = spec["segment"]
    rows = segment["bars"]
    stamps = [int(pd.Timestamp(row["at"]).value) for row in rows]
    if not rows or any(right - 300_000_000 <= left + 1 for left, right in zip(stamps, stamps[1:], strict=False)):
        raise ValueError("Modeled OHLC paths overlap, repeat or are not strictly monotonic")
    frame = pd.DataFrame([{name: row[key] for name, key in (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"), ("volume", "v"))} for row in rows],
        index=pd.DatetimeIndex([row["at"] for row in rows], name="timestamp")).apply(pd.to_numeric)
    if frame.isna().any().any() or len(frame) != len(rows):
        raise ValueError("Missing source rows cannot be silently dropped by the converter")
    ticks = TradeTickDataWrangler(instrument).process_bar_data(frame, **conversion["settings"])
    if len(ticks) != len(rows) * 4:
        raise ValueError("Public converter dropped or added required modeled tick rows")
    roles, generated, allocation = {}, [], []
    for index, row in enumerate(rows):
        selected = ticks[index * 4:index * 4 + 4]
        for tick, field, offset in zip(selected, ("o", "h", "l", "c"), (-300_000_000, -200_000_000, -100_000_000, 0), strict=True):
            if (tick.ts_event != stamps[index] + offset or tick.ts_init != tick.ts_event
                    or tick.price.as_decimal() != Decimal(row[field]) or str(tick.instrument_id) != str(instrument_id)):
                raise ValueError("Native conversion changed canonical prices or modeled timestamp ordering")
            roles[tick.ts_event] = {"role": field, "session": row["session"], "source_closed_at": row["at"]}
            generated.append({"ts_event": tick.ts_event, "ts_init": tick.ts_init, "price": str(tick.price.as_decimal()),
                "size": str(tick.size.as_decimal()), "modeled_trade_id": str(tick.trade_id), "source_session": row["session"], "role": field})
        allocation.append({"session": row["session"], "source_volume": row["v"],
            "modeled_volume": str(sum((tick.size.as_decimal() for tick in selected), Decimal(0))),
            "modeled_tick_sizes": [str(tick.size.as_decimal()) for tick in selected]})
    bar_type = BarType.from_str(str(instrument_id) + "-1-DAY-LAST-EXTERNAL")
    bars = [Bar(bar_type, *(Price.from_str(format(Decimal(row[key]), f".{precision}f")) for key in ("o", "h", "l", "c")),
        Quantity.from_int(int(Decimal(row["v"]))), stamp, stamp + 1) for row, stamp in zip(rows, stamps, strict=True)]
    closed_rows = dict(zip(stamps, rows, strict=True))
    start_ns, end_ns = (int(pd.Timestamp(segment[key]).value) for key in ("start_at", "end_at"))

    class RuleStrategy(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig(manage_contingent_orders=False))
            self.previous = None
            self.intent = None
            self.exit_wait = False
            self.exit_order = None
            self.boundary = False
            self.cycle = []
            self.signals, self.curve, self.unavailable = [], [], []
            self.entry_sequence = 0

        def on_start(self):
            self.subscribe_bars(bar_type)
            self.subscribe_trade_ticks(instrument_id)

        def held(self):
            return sum((Decimal(str(position.signed_qty)) for position in self.cache.positions_open(instrument_id=instrument_id, strategy_id=self.id)), Decimal(0))

        def known_orders(self):
            return [self.cache.order(identity) for identity in self.cycle]

        def terminal(self):
            return all(order is not None and order.is_closed for order in self.known_orders())

        def cancel_cycle(self):
            orders = self.known_orders()
            # Cancel a working OTO parent first; its native cascade owns held children.
            parents = [order for order in orders if order is not None and order.parent_order_id is None and not order.is_closed]
            if parents:
                for order in parents:
                    if not order.is_pending_cancel:
                        self.cancel_order(order)
                return
            for order in orders:
                if order is not None and order.is_open and not order.is_pending_cancel:
                    self.cancel_order(order)

        def terms(self, row):
            execution = strategy_definition["execution"]
            quantity = operand_value(strategy_definition["quantity"], row, parameters)
            terms = {key: strategy_definition[key] for key in ("symbol", "instrument_id", "currency", "session")}
            terms.update(side="BUY", quantity=format(quantity, ".0f") if quantity is not None else "", order_type=execution["entry_order_type"], time_in_force=execution["time_in_force"])
            if quantity is None or quantity <= 0 or quantity % 1:
                raise ValueError("Source-bound whole-share sizing is unavailable")
            for key in ("limit_price", "stop_price"):
                if execution[key] is not None:
                    price = operand_value(execution[key], row, parameters)
                    if price is None:
                        raise ValueError("Entry price initialization is unavailable")
                    terms[key] = amount(str(price), positive=True, places=2)
            if execution["exit_plan"] is not None:
                terms["exit_plan"] = {}
                for key, operand in execution["exit_plan"].items():
                    price = operand_value(operand, row, parameters)
                    if price is None:
                        raise ValueError("Protection price initialization is unavailable")
                    terms["exit_plan"][key] = amount(str(price), positive=True, places=2)
            broker_payload(terms, "SIM-RULE-VALIDATE")
            return terms

        def exit_if_confirmed(self):
            if self.boundary or not self.exit_wait or not self.terminal():
                return
            quantity = self.held()
            if quantity < 0 or quantity % 1:
                raise ValueError("Native residual is outside the whole long-only contract")
            self.exit_wait = False
            if quantity > 0:
                terms = {key: strategy_definition[key] for key in ("symbol", "instrument_id", "currency", "session")}
                terms.update(side="SELL", quantity=format(quantity, ".0f"), order_type="MARKET", time_in_force="DAY", position_intent="sell_to_close")
                self.entry_sequence += 1
                order = native_order(self.order_factory, terms, "SIM-EXIT-" + str(self.entry_sequence))
                self.cycle = [order.client_order_id]
                self.exit_order = order.client_order_id
                self.submit_order(order)

        def on_order_canceled(self, event):
            self.exit_if_confirmed()

        def on_order_expired(self, event):
            self.exit_if_confirmed()

        def on_order_filled(self, event):
            self.exit_if_confirmed()

        def on_trade_tick(self, tick):
            role = roles.get(tick.ts_event)
            if not role or tick.ts_event < start_ns - 300_000_000 or tick.ts_event > end_ns:
                return
            if self.exit_order is not None:
                order = self.cache.order(self.exit_order)
                if order is None or not order.is_closed:
                    return  # A working residual exit is never canceled/repeated on each tick.
                self.exit_order = None
            if self.exit_wait:
                self.cancel_cycle()
                self.exit_if_confirmed()
                return
            if role["role"] != "o" or self.intent is None:
                return
            intent, self.intent = self.intent, None
            if tick.ts_event <= intent["decision_ns"]:
                raise ValueError("Queued decision cannot execute at its own or an earlier source bar")
            if intent["action"] == "exit":
                self.exit_wait = True
                self.cancel_cycle()
                self.exit_if_confirmed()
            elif self.held() == 0 and self.terminal():
                self.entry_sequence += 1
                identity = "SIM-ENTRY-" + str(self.entry_sequence)
                if intent["terms"].get("exit_plan"):
                    group = native_group(self.order_factory, intent["terms"], identity)
                    self.cycle = [order.client_order_id for order in group.orders]
                    self.submit_order_list(group)
                else:
                    order = native_order(self.order_factory, intent["terms"], identity)
                    self.cycle = [order.client_order_id]
                    self.submit_order(order)

        def on_bar(self, bar):
            row = closed_rows[bar.ts_event]
            previous, self.previous = self.previous, row
            if bar.ts_event < start_ns:
                return  # Warmup primes only closed-bar history; no orders or metrics.
            account = self.cache.account_for_venue(venue)
            equity = account.balance_total(USD).as_decimal() + self.held() * Decimal(row["c"])
            self.curve.append({"at": row["at"], "equity": str(equity)})
            entry = rule_result(strategy_definition["entry"], row, previous, parameters)
            exit_result = rule_result(strategy_definition["exit"], row, previous, parameters)
            self.signals.append({"at": row["at"], "entry": entry, "exit": exit_result, "held_quantity": str(self.held())})
            if entry["state"] is None or exit_result["state"] is None:
                self.unavailable.append(row["at"])
            if strategy_definition["execution"]["time_in_force"] == "DAY":
                self.cancel_cycle()  # One provider daily boundary, never every modeled tick.
            if bar.ts_event == end_ns:
                self.boundary = True
                self.cancel_cycle()
            if self.exit_order is not None:
                order = self.cache.order(self.exit_order)
                if order is None or not order.is_closed:
                    return
                self.exit_order = None
            if self.exit_wait:
                if self.terminal() and self.held() == 0:
                    self.exit_wait = False
                else:
                    return
            if entry["state"] is None or exit_result["state"] is None:
                return
            if exit_result["state"] is True:
                if self.held() > 0 or not self.terminal():
                    self.intent = {"action": "exit", "decision_ns": bar.ts_event, "source": exit_result}
            elif entry["state"] is True and self.held() == 0 and self.terminal() and self.intent is None:
                try:
                    terms = self.terms(row)
                except ValueError as exc:
                    self.unavailable.append(row["at"])
                    self.signals[-1]["template_unavailable"] = str(exc)
                else:
                    self.intent = {"action": "entry", "decision_ns": bar.ts_event, "terms": terms, "source": entry}

    assumptions = spec["assumptions"]
    fee = Decimal(assumptions["fee_usd"])
    fee_model = FixedFeeModel(Money(fee, USD), charge_commission_once=assumptions["fee_per"] == "order") if fee else MakerTakerFeeModel()
    engine_config = BacktestEngineConfig(trader_id=TraderId("SIMULATION-001"), logging=LoggingConfig(bypass_logging=True))
    engine = BacktestEngine(engine_config)
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal(spec["starting_cash"]), USD)], base_currency=USD,
            allow_cash_borrowing=False, support_contingent_orders=True, oto_trigger_mode=OtoTriggerMode.FULL,
            fill_model=FillModel(prob_fill_on_limit=float(assumptions["limit_fill_probability"]),
                prob_slippage=float(assumptions["slippage_probability"]), random_seed=assumptions["random_seed"]),
            fee_model=fee_model,
            latency_model=LatencyModel(base_latency_nanos=0), bar_execution=False, trade_execution=True)
        engine.add_instrument(instrument)
        engine.add_data(ticks)
        engine.add_data(bars)
        strategy = RuleStrategy()
        engine.add_strategy(strategy)
        engine.run(start=pd.Timestamp(ticks[0].ts_init, tz="UTC"), end=pd.Timestamp(stamps[-1] + 1, tz="UTC"))
        reports = {name: json.loads(table.to_json(orient="split", date_format="iso", default_handler=str)) for name, table in {
            "orders": engine.trader.generate_orders_report(), "fills": engine.trader.generate_fills_report(),
            "positions": engine.trader.generate_positions_report(), "account": engine.trader.generate_account_report(venue)}.items()}
        orders = engine.cache.orders()
        unresolved = [str(order.client_order_id) for order in orders if not order.is_closed]
        cash = Decimal(spec["starting_cash"])
        ending = Decimal(strategy.curve[-1]["equity"]) if strategy.curve else cash
        peak, drawdown = cash, Decimal(0)
        for point in strategy.curve:
            value = Decimal(point["equity"])
            peak = max(peak, value)
            drawdown = max(drawdown, (peak - value) / peak * 100)
        benchmark_curve, benchmark_error = [], None
        if spec["benchmark"].get("available"):
            benchmark = {row["t"]: Decimal(row["raw"]["c"]) for row in spec["benchmark"]["bars"]}
            scored_rows = [row for row in rows if int(pd.Timestamp(row["at"]).value) >= start_ns]
            if all(row["session"] in benchmark and benchmark[row["session"]] > 0 for row in scored_rows):
                first = benchmark[scored_rows[0]["session"]]
                benchmark_curve = [{"at": row["at"], "equity": str(cash * benchmark[row["session"]] / first)} for row in scored_rows]
            else:
                benchmark_error = "Actual compatible benchmark observations do not cover every scored source session"
        return clean({"kind": "strategy_trial", "version": EXPERIMENT_VERSION, "status": "completed_with_limitations",
            "spec_sha256": spec["spec_sha256"], "experiment_sha256": spec["experiment_sha256"],
            "engine_version": "1.231.0", "native_risk_config": engine_config.risk_engine.json_primitives(),
            "metrics": {"net_return_pct": str((ending - cash) / cash * 100), "total_pnl": str(ending - cash),
                "max_drawdown_pct": str(drawdown), "closed_trades": len(engine.cache.positions_closed())
                    + sum(position.is_closed for position in engine.cache.position_snapshots())},
            "equity_curve": strategy.curve, "benchmark_curve": benchmark_curve, "benchmark_unavailable": benchmark_error or spec["benchmark"].get("reason"),
            "metric_basis": "Independent reset-capital source-close equity including actual native marked inventory; modeled costs, not broker performance",
            "coverage": {"complete": not unresolved and not strategy.unavailable and len(strategy.curve) == segment["scored_sessions"],
                "expected_sessions": segment["scored_sessions"], "observed_sessions": len(strategy.curve),
                "signal_unavailable_at": strategy.unavailable, "unresolved_order_ids": unresolved},
            "signals": strategy.signals, "ending_intent_unexecuted": strategy.intent or ({"action": "exit", "reason": "Rule exit awaited native cancellation confirmation at the horizon"} if strategy.exit_wait else None),
            "ending_held_quantity": str(strategy.held()), "ending_protection": "unprotected_partial_or_boundary_cancelled" if strategy.held() else "flat",
            "conversion_receipt": {"manifest": conversion, "generated_ticks_sha256": digest(generated), "generated_ticks": generated,
                "volume_allocation": allocation, "source_rows_sha256": digest(rows), "source_identity": spec["input_artifacts"],
                "modeled_ids_are_broker_ids": False, "bar_processing_order": "C tick first; source Bar ts_init=source closed_at + 1ns"},
            "order_events": {str(order.client_order_id): [type(item).to_dict(item) for item in order.events] for order in orders},
            "reports": reports, "native_result": asdict(engine.get_result()), "input_artifacts": spec["input_artifacts"],
            "fee_model_receipt": {"model": type(fee_model).__name__, "fixed_fee_usd": assumptions["fee_usd"],
                "fixed_fee_basis": assumptions["fee_per"], "maker_rate": str(instrument.maker_fee), "taker_rate": str(instrument.taker_fee),
                "percentage_model_active": not bool(fee), "basis": "Explicit simulation assumptions; native fee model updates native accounting, not observed broker fees",
                "percentage_fee_configuration": "Not part of this fixed-USD scenario profile; zero fixed fee uses native zero maker/taker rates"},
            "limitations": spec["limitations"], "assumptions": assumptions})
    finally:
        engine.dispose()


def simulate(spec):
    installed_engine_version = importlib.metadata.version("nautilus_trader")
    if (spec.get("version") != VERSION or spec.get("engine_version") != "1.231.0"
            or installed_engine_version != "1.231.0"
            or digest({key: value for key, value in spec.items() if key != "spec_sha256"}) != spec.get("spec_sha256")
            or digest(spec["saved_terms"]) != spec["proposal"]["terms_sha256"]):
        raise ValueError("Native version or immutable simulation specification differs")
    from linked_orders import broker_payload, native_group, native_order
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.models import (
        FillModel,
        FixedFeeModel,
        LatencyModel,
        MakerTakerFeeModel,
    )
    from nautilus_trader.config import LoggingConfig, StrategyConfig
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.data import Bar, BarType
    from nautilus_trader.model.enums import AccountType, OmsType, OtoTriggerMode
    from nautilus_trader.model.identifiers import InstrumentId, Symbol, TraderId, Venue
    from nautilus_trader.model.instruments import Equity
    from nautilus_trader.model.objects import FIXED_PRECISION, Money, Price, Quantity
    from nautilus_trader.trading.strategy import Strategy

    terms, assumptions = spec["terms"], spec["assumptions"]
    validate_terms(terms)
    broker_payload(terms, "SIM-PLAN")  # Reuse exact supported term validation, with no transport.
    if terms["side"] != "BUY" or spec["starting_holdings"] or terms["time_in_force"] not in {"DAY", "GTC"}:
        raise ValueError("This native profile requires an empty portfolio and a BUY DAY/GTC plan")
    if terms["time_in_force"] == "DAY" and assumptions["latency_ns"] != 0:
        raise ValueError("DAY close-cancellation profile requires zero assumed latency")
    instrument_id = InstrumentId.from_str(terms["instrument_id"])
    if str(instrument_id) != terms["symbol"] + ".ALPACA":
        raise ValueError("Simulation instrument differs from the saved supported equity")
    venue = Venue("ALPACA")
    representation = spec["representation"]
    precision = representation["price_precision"]
    if type(precision) is not int or not 2 <= precision <= FIXED_PRECISION:
        raise ValueError(f"Source prices exceed installed native price precision maximum {FIXED_PRECISION}; no rounding is performed")
    instrument = Equity(instrument_id, Symbol(terms["symbol"]), USD, precision, Price.from_str(representation["price_increment"]),
                        Quantity.from_int(1), 0, 0)
    bar_type = BarType.from_str(str(instrument_id) + "-1-DAY-LAST-EXTERNAL")
    decision_ns = int(instant(spec["decision_at"]).timestamp()) * 1_000_000_000

    class PlanReplay(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig(manage_contingent_orders=False))
            self.submitted_at = None

        def on_start(self):
            self.subscribe_bars(bar_type)

        def on_bar(self, bar):
            if self.submitted_at is not None and bar.ts_event > self.submitted_at and terms["time_in_force"] == "DAY":
                self.cancel_all_orders(instrument_id)
            if self.submitted_at is None and bar.ts_event >= decision_ns:
                self.submitted_at = bar.ts_event
                if terms.get("exit_plan"):
                    self.submit_order_list(native_group(self.order_factory, terms, "SIM-PLAN"))
                else:
                    self.submit_order(native_order(self.order_factory, terms, "SIM-PLAN"))

    fee = Decimal(assumptions["fee_usd"])
    fee_model = FixedFeeModel(Money(fee, USD), charge_commission_once=assumptions["fee_per"] == "order") if fee else MakerTakerFeeModel()
    engine_config = BacktestEngineConfig(trader_id=TraderId("SIMULATION-001"),
                                        logging=LoggingConfig(bypass_logging=True))
    engine = BacktestEngine(engine_config)
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal(spec["starting_cash"]), USD)],
            base_currency=USD, allow_cash_borrowing=False, support_contingent_orders=True, oto_trigger_mode=OtoTriggerMode.FULL,
            fill_model=FillModel(prob_fill_on_limit=float(assumptions["limit_fill_probability"]),
                                 prob_slippage=float(assumptions["slippage_probability"]), random_seed=assumptions["random_seed"]),
            fee_model=fee_model, latency_model=LatencyModel(base_latency_nanos=assumptions["latency_ns"]),
            bar_execution=True, bar_adaptive_high_low_ordering=False, trade_execution=False)
        engine.add_instrument(instrument)
        bars = []
        for row in spec["bars"]:
            timestamp = int(instant(row["at"]).timestamp()) * 1_000_000_000
            bars.append(Bar(bar_type, *(Price.from_str(row[key]) for key in ("o", "h", "l", "c")),
                            Quantity.from_int(int(Decimal(row["v"]))), timestamp, timestamp))
        engine.add_data(bars)
        strategy = PlanReplay()
        engine.add_strategy(strategy)
        engine.run(start=spec["start_at"], end=spec["end_at"])
        reports = {name: json.loads(table.to_json(orient="split", date_format="iso", default_handler=str)) for name, table in {
            "orders": engine.trader.generate_orders_report(), "fills": engine.trader.generate_fills_report(),
            "positions": engine.trader.generate_positions_report(), "account": engine.trader.generate_account_report(venue)}.items()}
        analyzer = engine.portfolio.analyzer
        return clean({"kind": "simulation", "version": VERSION, "engine_version": installed_engine_version,
            "native_risk_config": engine_config.risk_engine.json_primitives(),
            "order_events": {str(order.client_order_id): [type(event).to_dict(event) for event in order.events]
                             for order in engine.cache.orders()},
            "status": "completed_with_limitations", "spec_sha256": spec["spec_sha256"], "proposal": spec["proposal"],
            "submitted_at_ns": strategy.submitted_at, "native_result": asdict(engine.get_result()), "reports": reports,
            "return_series_basis": "Native portfolio returns where available; native primary statistics can fall back to position returns",
            "portfolio_returns": {stamp.isoformat(): value for stamp, value in analyzer.portfolio_returns().items()},
            "benchmark": {"available": False, "reason": "No matching benchmark series selected in this simulation profile"},
            "assumptions": assumptions, "representation": representation, "currency_basis": spec["currency_basis"],
            "input_artifacts": spec["input_artifacts"], "limitations": spec["limitations"]})
    finally:
        engine.dispose()


if __name__ == "__main__":
    specification = json.load(sys.stdin)
    try:
        response = calculate_scan(specification) if specification.get("kind") == "scanner_calculation" else calculate_chart(specification) if specification.get("kind") == "chart_calculation" else simulate_strategy(specification) if specification.get("kind") == "strategy_trial" else simulate(specification)
    except Exception as error:
        response = {"kind": specification.get("kind", "simulation"), "status": "failed", "spec_sha256": specification.get("spec_sha256"),
                    "error": type(error).__name__ + ": " + str(error)}
    print(json.dumps(response, allow_nan=False, default=str))
