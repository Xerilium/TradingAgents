"""Prepare an immutable saved-plan simulation; execution is an explicit separate call."""

import ast
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from contextlib import suppress
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from importlib.metadata import PackageNotFoundError, version
from itertools import product
from pathlib import Path
from zoneinfo import ZoneInfo

VERSION = "saved-plan-nautilus-v1"
EXPERIMENT_VERSION = "declarative-experiment-v1"
STRATEGY_VERSION = "declarative-equity-rules-v1"
INDICATORS = {name: units for names, units in (
    (("close_50_sma", "close_200_sma", "close_10_ema", "macd", "macds", "macdh", "boll", "boll_ub", "boll_lb", "atr", "vwma"), "price"),
    (("rsi",), "0-100"), (("mfi",), "0-1")) for name in names}
METRICS = ("net_return_pct", "total_pnl", "max_drawdown_pct")
CHART_VERSION = "chart-calculation-v1"
CHART_UNITS = {"price", "volume", "scalar", "percent", "boolean"}
CHART_FUNCTIONS = {"abs", "where", "lag", "rolling_min", "rolling_max", "rolling_sum", "rolling_mean", "sma", "ema", "scale"}
SCAN_VERSION = "scanner-program-v1"
SCAN_LIMITS = {"inputs": 16, "conditions": 16, "source_rows": 100000, "expected_buckets": 100000, "aligned_cells": 100000, "calculated_cells": 1000000}


def scan_calculation_capabilities():
    return {"version": SCAN_VERSION, "limits": dict(SCAN_LIMITS), "units": sorted(CHART_UNITS),
        "qualified_axes": [{"timeframe": value, "session": "regular", "source_timeframe": "1Min"} for value in ("1Min", "5Min", "15Min", "30Min", "1Hour")]
            + [{"timeframe": "1Day", "session": "provider_day", "source_timeframe": "1Day"}],
        "alignment": "Latest eligible closed original-axis observation at or before each actual anchor; explicit staleness in own-axis buckets",
        "formula_engine": CHART_VERSION, "time_basis": ["evaluate_now", "known_then"],
        "known_then": "Unavailable without independent source and definition point-in-time knowledge evidence",
        "unsupported": ["Arbitrary scripts", "Unqualified provider coarse-bar grids", "Synthetic missing bars"]}


def scan_costs(axes, bindings, calculations, anchor_input):
    sources, cells, expected_buckets = {}, {}, 0
    for axis in axes.values():
        key = (axis.get("source_pin") or {}).get("sha256") or digest(axis["source"])
        sources[key] = max(sources.get(key, 0), len(axis["rows"]))
        expected_minutes = {row["t"] for row in axis["expected_buckets"]}
        derived = (axis.get("aggregation") or {}).get("buckets", [])
        expected_buckets += len(axis["expected_buckets"]) + len(derived) + len({minute for bucket in derived for minute in bucket["expected_minutes"]} - expected_minutes)
    for calculation in calculations.values():
        for definition in [*calculation["dependencies"], calculation["definition"]]:
            key = digest({"source": calculation["source_sha256"], "definition": definition, "dependencies": calculation["dependencies"]})
            weight = len(list(ast.walk(formula_tree(definition["settings"]["expression"])))) if definition["kind"] == "formula" else len(chart_calculation_capabilities()["study_components"].get(definition["settings"].get("family"), []))
            cells[key] = len(calculation["rows"]) * weight
    return {"source_rows": sum(sources.values()), "expected_buckets": expected_buckets, "aligned_cells": len(axes[bindings[anchor_input]["axis"]]["rows"]) * len(bindings),
        "calculated_cells": sum(cells.values())}


def validate_scan_program(program):
    from uuid import UUID

    if (not isinstance(program, dict) or set(program) != {"version", "anchor_input", "inputs", "parameters", "operator", "conditions", "time_basis"}
            or program["version"] != SCAN_VERSION or program["operator"] not in {"ALL", "ANY"}
            or program["time_basis"] not in {"evaluate_now", "known_then"}):
        raise ValueError("Choose a versioned scanner program with explicit anchor, inputs, parameters, conditions and time basis")
    inputs, parameters = program["inputs"], program["parameters"]
    if (not isinstance(inputs, dict) or not 1 <= len(inputs) <= SCAN_LIMITS["inputs"] or program["anchor_input"] not in inputs
            or not isinstance(parameters, dict) or len(parameters) > 32 or set(inputs) & set(parameters)):
        raise ValueError("Scanner needs 1 to 16 uniquely named inputs, an existing anchor input and distinct typed parameters")
    for name in [*inputs, *parameters]:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
            raise ValueError("Scanner names must be bounded declarative identifiers")
    for value in inputs.values():
        if (not isinstance(value, dict) or set(value) != {"timeframe", "session", "source_profile", "history_key", "value", "max_staleness_buckets"}
                or value["timeframe"] not in {"1Min", "5Min", "15Min", "30Min", "1Hour", "1Day"}
                or value["session"] not in {"regular", "provider_day"}
                or value["history_key"] is not None and (not isinstance(value["history_key"], str) or not 1 <= len(value["history_key"]) <= 256)
                or type(value["max_staleness_buckets"]) is not int or not 0 <= value["max_staleness_buckets"] <= 10000):
            raise ValueError("Each scanner input requires its own timeframe, session, retained selection and explicit staleness in buckets")
        profile, selected = value["source_profile"], value["value"]
        if (not isinstance(profile, dict) or set(profile) != {"provider", "feed", "adjustment", "currency"}
                or profile["provider"] != "Alpaca" or profile["feed"] != "iex" or profile["currency"] != "USD"
                or profile["adjustment"] not in {"raw", "split", "dividend", "all"} or not isinstance(selected, dict)):
            raise ValueError("Scanner inputs require an exact supported Alpaca IEX USD source profile")
        if selected.get("kind") == "field":
            if set(selected) != {"kind", "field"} or selected["field"] not in {"open", "high", "low", "close", "volume"}:
                raise ValueError("Select an exact raw OHLCV field")
        elif selected.get("kind") == "definition":
            ref = selected.get("definition", {})
            if (set(selected) != {"kind", "definition", "output"} or not isinstance(ref, dict) or set(ref) != {"id", "revision", "sha256"}
                    or str(UUID(ref["id"])) != ref["id"] or type(ref["revision"]) is not int or ref["revision"] < 1
                    or not re.fullmatch(r"[a-f0-9]{64}", str(ref["sha256"])) or not isinstance(selected["output"], str)
                    or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", selected["output"])):
                raise ValueError("Select an exact saved formula/study UUID, revision, hash and output component")
        else:
            raise ValueError("Scanner values must be raw fields or exact reusable definition outputs")
    for parameter in parameters.values():
        if not isinstance(parameter, dict) or set(parameter) != {"value", "units"} or parameter["units"] not in CHART_UNITS - {"boolean"}:
            raise ValueError("Program parameters need exact decimal values and semantic units")
        chart_number(parameter["value"])
    if not isinstance(program["conditions"], list) or not 1 <= len(program["conditions"]) <= SCAN_LIMITS["conditions"]:
        raise ValueError("Choose between 1 and 16 scanner conditions")
    for condition in program["conditions"]:
        if (not isinstance(condition, dict) or set(condition) != {"left", "comparison", "right"}
                or condition["comparison"] not in {"gt", "gte", "lt", "lte", "eq", "cross_above", "cross_below"}):
            raise ValueError("Choose a supported declarative scanner comparison")
        for operand in (condition["left"], condition["right"]):
            if not isinstance(operand, dict):
                raise ValueError("Choose a named input, typed parameter or exact typed constant")
            if operand.get("kind") in {"input", "parameter"}:
                if set(operand) != {"kind", "name"} or operand["name"] not in (inputs if operand["kind"] == "input" else parameters):
                    raise ValueError("Scanner operand refers to an undeclared name")
            elif operand.get("kind") == "constant":
                if set(operand) != {"kind", "value", "units"} or operand["units"] not in CHART_UNITS - {"boolean"}:
                    raise ValueError("Scanner constants require exact values and semantic units")
                chart_number(operand["value"])
            else:
                raise ValueError("Executable scanner expressions are unavailable; use named causal inputs")
    return copy.deepcopy(program)


def prepare_scan_calculation(program, inputs, *, cutoff, definitions=(), captured_at=None, historical=False):
    from .market_evidence import scan_source_evidence

    program = validate_scan_program(program)
    instant(cutoff)
    captured_at = captured_at or datetime.now(UTC).isoformat()
    instant(captured_at)
    if not isinstance(inputs, dict) or set(inputs) != set(program["inputs"]):
        raise ValueError("Freeze every named scanner input, including unavailable inputs")
    definitions = dict(definitions)
    axes, bindings, calculations = {}, {}, {}
    for name, selected in program["inputs"].items():
        source = scan_source_evidence(inputs[name], selected, cutoff)
        axis_id = digest(source)
        axes.setdefault(axis_id, source)
        binding = {"axis": axis_id, "value": selected["value"], "calculation": None}
        if selected["value"]["kind"] == "definition":
            graph = definitions.get(name)
            if not isinstance(graph, dict) or set(graph) != {"definition", "dependencies"}:
                raise ValueError("Freeze the exact saved definition and transitive dependencies for " + name)
            definition, dependencies = graph["definition"], graph["dependencies"]
            ref = selected["value"]["definition"]
            if (definition.get("id") != ref["id"] or definition.get("revision") != ref["revision"] or digest(definition) != ref["sha256"]
                    or definition.get("kind") not in {"formula", "study"}):
                raise ValueError("Scanner definition differs from its exact saved revision or uses an unsupported event axis")
            output = selected["value"]["output"]
            available = [definition["name"]] if definition["kind"] == "formula" else chart_calculation_capabilities()["study_components"].get(definition["settings"]["family"], [])
            if output not in available:
                raise ValueError("Select an existing causal definition output component")
            calculation = {"kind": "chart_calculation", "version": CHART_VERSION, "engine_version": "1.231.0",
                "definition": definition, "dependencies": dependencies, "definition_sha256": digest(definition),
                "source_pin": source["source_pin"], **{key: source[key] for key in ("rows", "source", "calendar", "calendar_coverage", "source_sha256", "source_limitations")}}
            calculation["spec_sha256"] = digest(calculation)
            if calculation["rows"]:
                validate_chart_calculation(calculation)
            elif not isinstance(dependencies, list) or len(dependencies) > 63:
                raise ValueError("Exact reusable dependencies exceed the scanner definition budget")
            binding["calculation"] = calculation["spec_sha256"]
            calculations.setdefault(calculation["spec_sha256"], calculation)
        bindings[name] = binding
    costs = scan_costs(axes, bindings, calculations, program["anchor_input"])
    if any(value > SCAN_LIMITS[key] for key, value in costs.items()):
        raise ValueError("Scanner whole-run row/cell budget exceeded; reduce inputs/history, no rows are truncated")
    spec = {"kind": "scanner_calculation", "version": SCAN_VERSION, "program": program, "axes": axes, "bindings": bindings,
        "calculations": calculations, "market_cutoff": cutoff, "captured_at": captured_at, "costs": costs, "limits": SCAN_LIMITS,
        "time_basis": "retrospective" if historical else "evaluate_now"}
    spec["spec_sha256"] = digest(spec)
    return validate_scan_calculation(spec)


def validate_scan_calculation(spec):
    if (spec.get("kind") != "scanner_calculation" or spec.get("version") != SCAN_VERSION
            or digest({key: value for key, value in spec.items() if key != "spec_sha256"}) != spec.get("spec_sha256")
            or spec.get("limits") != SCAN_LIMITS):
        raise ValueError("Scanner immutable specification or resource limits changed")
    program = validate_scan_program(spec["program"])
    instant(spec["market_cutoff"])
    instant(spec["captured_at"])
    if set(spec["bindings"]) != set(program["inputs"]):
        raise ValueError("Scanner named input bindings changed")
    for axis_id, axis in spec["axes"].items():
        if axis_id != digest(axis) or axis.get("source_sha256") != digest({key: axis[key] for key in ("source", "rows", "calendar_coverage")}):
            raise ValueError("Scanner retained axis/calendar/source identity changed")
    for binding in spec["bindings"].values():
        if binding["axis"] not in spec["axes"] or binding["calculation"] is not None and binding["calculation"] not in spec["calculations"]:
            raise ValueError("Scanner source or reusable calculation binding is unavailable")
    for key, calculation in spec["calculations"].items():
        if key != calculation["spec_sha256"]:
            raise ValueError("Scanner reusable calculation identity changed")
        if calculation["rows"]:
            validate_chart_calculation(calculation)
    costs = scan_costs(spec["axes"], spec["bindings"], spec["calculations"], program["anchor_input"])
    if costs != spec["costs"] or any(value > SCAN_LIMITS[key] for key, value in costs.items()):
        raise ValueError("Scanner whole-run budgets changed or are exceeded; no truncation is allowed")
    return spec


def validate_scan_result(result, spec):
    validate_scan_calculation(spec)
    if (spec.get("kind") != "scanner_calculation" or spec.get("version") != SCAN_VERSION
            or digest({key: value for key, value in spec.items() if key != "spec_sha256"}) != spec.get("spec_sha256")
            or result.get("kind") != spec["kind"] or result.get("version") != SCAN_VERSION
            or result.get("spec_sha256") != spec["spec_sha256"] or result.get("status") not in {"completed", "unavailable"}
            or result.get("evaluation") not in {"true", "false", "unavailable"}
            or digest({key: value for key, value in result.items() if key != "result_sha256"}) != result.get("result_sha256")):
        raise ValueError("Scanner result differs from its immutable program, inputs or result hash")
    validate_scan_program(spec["program"])
    if result.get("matched") != (None if result["evaluation"] == "unavailable" else result["evaluation"] == "true") or result.get("input_identity") != spec["spec_sha256"]:
        raise ValueError("Scanner analytical outcome differs from its exact evidence identity")
    if not isinstance(result.get("observations"), list) or result.get("latest") != (result["observations"][-1] if result["observations"] else None):
        raise ValueError("Scanner latest evidence differs from its retained anchor observations")
    if set(result.get("axes", {})) != set(spec["axes"]):
        raise ValueError("Scanner result axes differ from its frozen source selections")
    for key, axis in result["axes"].items():
        original = spec["axes"][key]
        if axis.get("source_pin") != original["source_pin"] or axis.get("source_sha256") != digest({name: axis[name] for name in ("source", "rows", "calendar_coverage")}):
            raise ValueError("Scanner resolved source/aggregation identity changed")
        if original.get("aggregation"):
            if axis.get("original_rows") != original["rows"] and axis["rows"] != original["rows"]:
                raise ValueError("Native aggregation lost its exact original minute constituents")
        elif axis["rows"] != original["rows"]:
            raise ValueError("Scanner original-axis rows changed")
    anchor = result["axes"][spec["bindings"][spec["program"]["anchor_input"]]["axis"]]
    previous = None
    for observation in result["observations"]:
        ordinal = observation.get("anchor", {}).get("source_ordinal")
        if (type(ordinal) is not int or not 0 <= ordinal < len(anchor["rows"]) or previous is not None and ordinal <= previous
                or observation["anchor"] != anchor["rows"][ordinal] or set(observation.get("inputs", {})) != set(spec["bindings"])
                or observation.get("evaluation") not in {"true", "false", "unavailable"}):
            raise ValueError("Scanner anchor/source evidence changed")
        previous = ordinal
        for name, aligned in observation["inputs"].items():
            axis = result["axes"][spec["bindings"][name]["axis"]]
            index = aligned.get("source_ordinal")
            if index is not None:
                if type(index) is not int or not 0 <= index < len(axis["rows"]):
                    raise ValueError("Aligned scanner input refers to an unavailable actual source ordinal")
                row = axis["rows"][index]
                if (aligned.get("source_identity") != digest({"source": axis["source_sha256"], "row": row})
                        or aligned.get("source_pin") != axis["source_pin"] or aligned.get("t") != row["t"]
                        or aligned.get("closed_at") != row["closed_at"] or instant(row["closed_at"]) > instant(observation["anchor"]["closed_at"])):
                    raise ValueError("Aligned scanner evidence is not the captured backward closed-bar observation")
    return result


def execute_scan_calculation(spec, native_python, *, process_state=None, cancelled=None, timeout=None):
    result = execute(spec, native_python, process_state, cancelled=cancelled, timeout=timeout)
    if result.get("status") in {"failed", "interrupted"}:
        return result
    return validate_scan_result(result, spec)


def chart_calculation_capabilities():
    return {"version": CHART_VERSION, "transforms": ["heikin_ashi", "renko", "kagi", "line_break", "point_figure"],
        "studies": ["kama", "cci", "donchian", "ichimoku"], "formula_functions": sorted(CHART_FUNCTIONS),
        "study_components": {"kama": ["kama"], "cci": ["cci"], "donchian": ["upper", "middle", "lower"],
            "ichimoku": ["tenkan", "kijun", "span_a", "span_b", "chikou"]},
        "reusable_functions": {"arguments": "Exact typed parameters ordered lexicographically by name", "components": "dependency__component",
            "axis": "Causal raw-source observations; transformed event axes require explicit mapping and are rejected here"},
        "units": sorted(CHART_UNITS), "native_version": "1.231.0", "execution": "isolated calculation; no trading engine or optimizer",
        "limits": {"definitions": 64, "formula_nodes": 256, "period": 10000, "input_rows": 100000, "output_events": 100000,
            "numeric_significant_digits": 128, "numeric_exponent_magnitude": 128, "intermediate_rational_bits": 65536},
        "unsupported": ["ATR/log/high-low transform variants", "total returns without dividend evidence", "external formula scripts"]}


def chart_integer(value, *, zero=False):
    if type(value) is not int or not (0 if zero else 1) <= value <= 10000:
        raise ValueError("Chart periods must be explicit bounded integers")
    return value


def chart_number(value):
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError("Chart numeric inputs must be bounded exact decimal strings")
    number = finite(value)
    if len(number.as_tuple().digits) > 128 or abs(number.as_tuple().exponent) > 128 or number and abs(number.adjusted()) > 128:
        raise ValueError("Chart numeric digits/exponent exceed the published exact-calculation budget; no rounding is performed")
    return number


def formula_tree(expression):
    if not isinstance(expression, str) or not 1 <= len(expression) <= 4096:
        raise ValueError("Provide a bounded declarative formula expression")
    tree = ast.parse(expression, mode="eval")
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call, ast.Name, ast.Load, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq)
    nodes = list(ast.walk(tree))
    if len(nodes) > 256 or any(not isinstance(node, allowed) for node in nodes):
        raise ValueError("Formula contains an unsupported node; scripts, attributes and indexing are unavailable")
    for node in nodes:
        if isinstance(node, ast.Constant) and (type(node.value) not in (int, float) or not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", ast.get_source_segment(expression, node) or "")):
            raise ValueError("Formula literals must be exact finite decimal tokens")
        if isinstance(node, ast.Constant):
            chart_number(ast.get_source_segment(expression, node))
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.keywords):
            raise ValueError("Only named positional declarative functions are supported")
    return tree


def validate_chart_definition(value, definitions=()):
    from uuid import UUID

    if not isinstance(value, dict) or set(value) != {"id", "revision", "updated_at", "name", "kind", "settings"}:
        raise ValueError("Select an exact versioned chart definition")
    UUID(value["id"])
    instant(value["updated_at"])
    if type(value["revision"]) is not int or value["revision"] < 1 or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", value["name"]):
        raise ValueError("Definition needs a positive revision and reusable identifier name")
    settings, kind = value["settings"], value["kind"]
    if not isinstance(settings, dict):
        raise ValueError("Chart settings must be declarative fields")
    family = settings.get("family")
    if kind == "transform":
        keys = {"heikin_ashi": {"family"}, "renko": {"family", "box_size", "reversal"},
            "kagi": {"family", "reversal_kind", "reversal_amount"}, "line_break": {"family", "lines"},
            "point_figure": {"family", "box_size", "reversal"}}
        if family not in keys or set(settings) != keys[family]:
            raise ValueError("Choose an exact supported transform and its applicable parameters")
        if family in {"renko", "point_figure"}:
            if chart_number(settings["box_size"]) <= 0:
                raise ValueError("Fixed box size must be positive")
            chart_integer(settings["reversal"])
        if family == "line_break":
            chart_integer(settings["lines"])
        if family == "kagi" and (settings["reversal_kind"] not in {"fixed", "percent"}
                or chart_number(settings["reversal_amount"]) <= 0 or settings["reversal_kind"] == "percent" and chart_number(settings["reversal_amount"]) >= 100):
            raise ValueError("Kagi needs a positive fixed amount or a percentage strictly between zero and 100")
    elif kind == "study":
        keys = {"kama": {"family", "period", "fast", "slow"}, "cci": {"family", "period", "scalar", "ma_type"},
            "donchian": {"family", "period", "lag"}, "ichimoku": {"family", "tenkan", "kijun", "senkou", "displacement"}}
        if family not in keys or set(settings) != keys[family]:
            raise ValueError("Choose a supported parameterized study")
        for key in keys[family] - {"family", "scalar", "ma_type"}:
            chart_integer(settings[key], zero=key in {"lag", "displacement"})
        if family == "kama" and settings["fast"] >= settings["slow"]:
            raise ValueError("KAMA fast period must be less than slow period")
        if family == "cci" and (settings["ma_type"] != "SIMPLE" or chart_number(settings["scalar"]) <= 0):
            raise ValueError("CCI requires explicit SIMPLE mean and positive scalar")
        if family == "ichimoku" and not settings["tenkan"] <= settings["kijun"] <= settings["senkou"]:
            raise ValueError("Ichimoku requires tenkan <= kijun <= senkou")
    elif kind == "formula":
        if (set(settings) != {"expression", "parameters", "units", "display_shift", "render"} or settings["units"] not in CHART_UNITS
                or settings["render"] not in {"line", "histogram", "overlay"} or settings["render"] == "overlay" and settings["units"] != "price"):
            raise ValueError("Formula requires expression, typed parameters, output units and display shift")
        chart_integer(settings["display_shift"], zero=True)
        if not isinstance(settings["parameters"], dict) or len(settings["parameters"]) > 32:
            raise ValueError("Formula parameters must be a bounded typed mapping")
        for name, parameter in settings["parameters"].items():
            if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name) or set(parameter) != {"value", "units"}
                    or parameter["units"] not in CHART_UNITS - {"boolean"}):
                raise ValueError("Invalid exact typed formula parameter")
            chart_number(parameter["value"])
        formula_tree(settings["expression"])
    elif kind == "seasonality":
        if (set(settings) != {"alignment", "comparison", "adjustment"} or settings["alignment"] not in {"calendar", "session"}
                or settings["comparison"] not in {"raw", "normalized"} or not isinstance(settings["adjustment"], str)):
            raise ValueError("Seasonality requires explicit alignment, comparison and adjustment basis")
    else:
        raise ValueError("Unsupported chart definition kind")
    if definitions:
        names = [item["name"] for item in definitions]
        if len(names) != len(set(names)) or value["name"] in names:
            raise ValueError("Dependency revision names must be unique and cannot refer to self")
    reserved = CHART_FUNCTIONS | {"open", "high", "low", "close", "volume"}
    if value["name"] in reserved or "__" in value["name"]:
        raise ValueError("Definition name collides with a source field, function or component separator")
    if kind == "formula" and set(settings["parameters"]) & (reserved | {value["name"], *(item["name"] for item in definitions)}):
        raise ValueError("Formula parameter names cannot shadow source fields, dependencies or functions")
    return copy.deepcopy(value)


def prepare_chart_calculation(history, request):
    from .market_evidence import chart_source_evidence

    if set(request) != {"definition", "dependencies", "source_pin"} or not isinstance(request["dependencies"], list) or len(request["dependencies"]) > 63:
        raise ValueError("Calculation requires an exact definition, dependency revisions and retained source pin")
    dependencies = [validate_chart_definition(item) for item in request["dependencies"]]
    definition = validate_chart_definition(request["definition"], dependencies)
    source = chart_source_evidence(history, request["source_pin"])
    spec = {"kind": "chart_calculation", "version": CHART_VERSION, "engine_version": "1.231.0",
        "definition": definition, "dependencies": dependencies, "definition_sha256": digest(definition),
        "source_pin": copy.deepcopy(request["source_pin"]), **source}
    spec["spec_sha256"] = digest(spec)
    return validate_chart_calculation(spec)


def validate_chart_calculation(spec):
    if (spec.get("kind") != "chart_calculation" or spec.get("version") != CHART_VERSION
            or spec.get("engine_version") != "1.231.0" or digest({key: value for key, value in spec.items() if key != "spec_sha256"}) != spec.get("spec_sha256")
            or digest(spec["definition"]) != spec.get("definition_sha256")):
        raise ValueError("Chart calculation identity changed")
    validate_chart_definition(spec["definition"], spec["dependencies"])
    if not isinstance(spec.get("rows"), list) or not 1 <= len(spec["rows"]) <= 100000:
        raise ValueError("Retained chart rows exceed the visible calculation budget")
    for row in spec["rows"]:
        if row.get("raw"):
            for value in row["raw"].values():
                chart_number(value)
    if spec.get("source_sha256") != digest({"source": spec["source"], "rows": spec["rows"], "calendar_coverage": spec.get("calendar_coverage")}):
        raise ValueError("Retained source/coverage hash differs from the calculation input")
    for dependency in spec["dependencies"]:
        validate_chart_definition(dependency)
    definitions = {item["name"]: item for item in [*spec["dependencies"], spec["definition"]]}
    if len(definitions) != len(spec["dependencies"]) + 1:
        raise ValueError("Exact dependency revisions need unique reusable names")
    visiting, visited = set(), set()

    def visit(name):
        if name in visiting:
            raise ValueError("Cyclic formula dependency revisions are forbidden")
        if name in visited:
            return
        visiting.add(name)
        item = definitions[name]
        if item["kind"] == "formula":
            parameters = item["settings"]["parameters"]
            for node in ast.walk(formula_tree(item["settings"]["expression"])):
                if not isinstance(node, ast.Name) or node.id in CHART_FUNCTIONS | {"open", "high", "low", "close", "volume"} | set(parameters):
                    continue
                dependency_name = node.id.partition("__")[0]
                if dependency_name not in definitions:
                    raise ValueError("Formula refers to an undeclared exact dependency revision")
                if definitions[dependency_name]["kind"] not in {"formula", "study"}:
                    raise ValueError("Event-axis transforms cannot be silently coerced to raw-bar formula inputs")
                visit(dependency_name)
        visiting.remove(name)
        visited.add(name)

    for name in definitions:
        visit(name)
    return spec


def validate_chart_result(result, spec):
    validate_chart_calculation(spec)
    if (result.get("kind") != "chart_calculation" or result.get("version") != CHART_VERSION
            or result.get("spec_sha256") != spec["spec_sha256"] or result.get("definition_sha256") != spec["definition_sha256"]
            or result.get("source_pin") != spec["source_pin"] or result.get("status") not in {"completed", "unavailable"}
            or digest({key: value for key, value in result.items() if key != "result_sha256"}) != result.get("result_sha256")):
        raise ValueError("Retained chart result does not match its immutable calculation")
    rows = spec["rows"]
    if result.get("source_rows") != rows or not isinstance(result.get("events"), list) or not isinstance(result.get("series"), list):
        raise ValueError("Result source rows or output axes changed")
    for ordinal, event in enumerate(result["events"]):
        index = event.get("source_ordinal")
        if (type(index) is not int or not 0 <= index < len(rows) or event.get("output_ordinal") != ordinal
                or event.get("t") != rows[index]["t"] or event.get("source_available_at") != rows[index]["available_at"]
                or event.get("origin_at") != rows[index]["source_timestamp"] or event.get("closed_at") != rows[index]["closed_at"]
                or event.get("closed") is not True or rows[index]["reasons"] or event.get("volume") is not None
                or event.get("history_prefix_sha256") != rows[index]["history_prefix_sha256"]):
            raise ValueError("Transform event is not bound to a completed actual source observation")
        limits = event.get("source_range")
        if not isinstance(limits, list) or len(limits) != 2 or any(type(n) is not int for n in limits) or not 0 <= limits[0] <= limits[1] == index:
            raise ValueError("Transform contributing range is invalid")
        for number in event["ohlc"].values():
            Fraction(number)
    for output in result["series"]:
        if len(output.get("points", [])) != len(rows) or output.get("units") not in CHART_UNITS:
            raise ValueError("Series must retain the exact raw-source observation axis and units")
        for index, point in enumerate(output["points"]):
            if (point.get("source_ordinal") != index or point.get("t") != rows[index]["t"] or point.get("source_available_at") != rows[index]["available_at"]
                    or point.get("origin_at") != rows[index]["source_timestamp"] or point.get("closed_at") != rows[index]["closed_at"]):
                raise ValueError("Series origin/availability does not match the retained source")
            if instant(point["available_at"]) < instant(point["calculated_at"]) or point["source_available_at"] and instant(point["available_at"]) < instant(point["source_available_at"]):
                raise ValueError("Calculation cannot be available before it was calculated or its inputs were known")
    expected = digest({"implementation": result["implementation"], "definition": spec["definition"], "dependencies": spec["dependencies"], "source_sha256": spec["source_sha256"]})
    if result.get("derivation_identity") != expected:
        raise ValueError("Calculation implementation/dependency/source identity changed")
    return result


def execute_chart_calculation(spec, native_python, *, process_state, cancelled, timeout):
    validate_chart_calculation(spec)
    result = execute(spec, native_python, process_state, cancelled=cancelled, timeout=timeout)
    if result.get("status") in {"failed", "interrupted"}:
        return result
    return validate_chart_result(result, spec)


def experiment_capabilities():
    try:
        installed = version("optuna")
    except PackageNotFoundError:
        installed = None
    return {"version": EXPERIMENT_VERSION, "strategy_version": STRATEGY_VERSION,
        "optimizer": {"name": "optuna", "required_version": "5.0.0", "installed_version": installed,
            "available": installed == "5.0.0", "reason": None if installed == "5.0.0" else "Optuna 5.0.0 must be explicitly installed in the service environment"},
        "indicators": INDICATORS, "metrics": METRICS, "search_modes": ["grid", "adaptive"],
        "execution": {"entry_order_type": "MARKET", "exit_order_type": "MARKET", "time_in_force": "DAY",
            "timing": "native_ohlc_path_next_modeled_open", "pending_entry_exit": "cancel_then_exit_actual_position",
            "brackets": "native_full_oto", "limit_price": None, "stop_price": None, "exit_plan": None},
        "entry_order_types": ["MARKET", "LIMIT", "STOP_LIMIT"],
        "window_preset": {"mode": "rolling", "train_sessions": 126, "validation_sessions": 21,
            "gap_sessions": 1, "oos_sessions": 21, "step_sessions": 21},
        "search_preset": {"mode": "adaptive", "seed": 0, "max_trials": 64, "sampler": "TPESampler", "pruner": "NopPruner"},
        "time_in_force": ["DAY", "GTC"],
        "gap_basis": "expected_calendar_sessions", "clock_duration_embargo": "unavailable",
        "limits": {"parameters": 8, "values_per_parameter": 256, "atoms_per_rule": 16, "scenarios": 32, "finite_candidates": 100000},
        "open_capabilities": ["carry and overlapping OOS", "actual intraday/session-open execution",
            "intermediate pruning", "exact adaptive resume", "other assets and starting holdings"]}


def finite(value):
    if not isinstance(value, str):
        raise ValueError("Rule numbers and finite parameter values must be exact decimal strings")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError("Rule value is not a decimal") from None
    if not number.is_finite():
        raise ValueError("Rule value must be finite")
    return number


def validate_strategy(value):
    required = {"version", "id", "revision", "updated_at", "name", "symbol", "instrument_id", "currency", "session",
        "quantity", "entry", "exit", "parameters", "execution"}
    if not isinstance(value, dict) or set(value) != required or value["version"] != STRATEGY_VERSION:
        raise ValueError("Choose the exact declarative strategy schema; scripts and unknown fields are unavailable")
    from uuid import UUID

    if str(UUID(value["id"])) != value["id"] or type(value["revision"]) is not int or value["revision"] < 1:
        raise ValueError("Strategy identity and positive immutable revision are required")
    instant(value["updated_at"])
    if (not isinstance(value["name"], str) or not 1 <= len(value["name"].strip()) <= 200
            or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", value["symbol"])
            or value["instrument_id"] != value["symbol"] + ".ALPACA" or value["currency"] != "USD" or value["session"] != "regular"):
        raise ValueError("Strategy requires one explicit regular-session USD equity identity")
    parameters = value["parameters"]
    if not isinstance(parameters, dict) or len(parameters) > 8:
        raise ValueError("Use at most eight named finite parameters")
    for name, parameter in parameters.items():
        if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", name) or not isinstance(parameter, dict)
                or set(parameter) != {"type", "values"} or parameter["type"] not in {"integer", "decimal"}
                or not isinstance(parameter["values"], list) or not 1 <= len(parameter["values"]) <= 256):
            raise ValueError("Parameters require a type and a nonempty bounded finite value list")
        numbers = [finite(item) for item in parameter["values"]]
        if len(set(numbers)) != len(numbers) or parameter["type"] == "integer" and any(n % 1 for n in numbers):
            raise ValueError("Parameter values must be unique and match their declared exact type")
    def operand(item):
        if not isinstance(item, dict):
            raise ValueError("Choose a typed rule operand")
        kind = item.get("kind")
        if kind == "price" and set(item) == {"kind", "field"} and item["field"] in {"open", "high", "low", "close"}:
            return "price"
        if kind == "indicator" and set(item) == {"kind", "name"} and item["name"] in INDICATORS:
            return INDICATORS[item["name"]]
        if kind == "constant" and set(item) == {"kind", "value", "units"}:
            finite(item["value"])
        elif kind == "parameter" and set(item) == {"kind", "name", "units"} and item["name"] in parameters:
            pass
        else:
            raise ValueError("Unsupported operand or arbitrary expression")
        if item["units"] not in {"price", "0-100", "0-1", "shares"}:
            raise ValueError("Declare the actual operand units")
        return item["units"]
    quantity = value["quantity"]
    if operand(quantity) != "shares" or quantity["kind"] not in {"constant", "parameter"}:
        raise ValueError("Sizing requires a fixed whole-share value or finite whole-share parameter")
    quantities = [quantity["value"]] if quantity["kind"] == "constant" else parameters[quantity["name"]]["values"]
    if (quantity["kind"] == "parameter" and parameters[quantity["name"]]["type"] != "integer"
            or any(finite(item) <= 0 or finite(item) % 1 for item in quantities)):
        raise ValueError("Every sizing variant must be positive whole shares")
    for key in ("entry", "exit"):
        rule = value[key]
        if (not isinstance(rule, dict) or set(rule) != {"operator", "atoms"} or rule["operator"] not in {"ALL", "ANY"}
                or not isinstance(rule["atoms"], list) or not 1 <= len(rule["atoms"]) <= 16):
            raise ValueError("Entry and exit require ALL/ANY with one to sixteen explicit atoms")
        for atom in rule["atoms"]:
            if (not isinstance(atom, dict) or set(atom) != {"left", "right", "comparison"}
                    or atom["comparison"] not in {"above", "below", "cross_above", "cross_below"}
                    or operand(atom["left"]) != operand(atom["right"]) or operand(atom["left"]) == "shares"):
                raise ValueError("Rule comparisons require compatible price/indicator units")
    execution = value["execution"]
    expected = experiment_capabilities()["execution"]
    if not isinstance(execution, dict) or set(execution) != set(expected) or execution.get("time_in_force") not in {"DAY", "GTC"}:
        raise ValueError("Choose the supported explicit reusable-rule execution contract")
    if (execution["entry_order_type"] not in {"MARKET", "LIMIT", "STOP_LIMIT"}
            or any(execution[key] != expected[key] for key in ("exit_order_type", "timing", "pending_entry_exit", "brackets"))):
        raise ValueError("Choose native modeled-O entry, MARKET residual exit and FULL native linked protection")
    for key in ("limit_price", "stop_price"):
        needed = execution["entry_order_type"] == "STOP_LIMIT" or key == "limit_price" and execution["entry_order_type"] == "LIMIT"
        if needed != (execution[key] is not None) or execution[key] is not None and operand(execution[key]) != "price":
            raise ValueError("Entry templates require only their exact typed limit/trigger price operands")
    plan = execution["exit_plan"]
    if plan is not None and (not isinstance(plan, dict) or not plan or set(plan) - {"take_profit", "stop_price", "stop_limit_price"}
            or "stop_limit_price" in plan and "stop_price" not in plan or any(operand(item) != "price" for item in plan.values())):
        raise ValueError("Linked protection requires typed target/stop prices; stop-limit also requires a trigger")
    return copy.deepcopy(value)


def validate_experiment(spec):
    if (spec.get("kind") != "experiment" or spec.get("version") != EXPERIMENT_VERSION
            or spec.get("engine_version") != "1.231.0"
            or digest({key: value for key, value in spec.items() if key != "spec_sha256"}) != spec.get("spec_sha256")
            or digest(validate_strategy(spec["strategy"])) != spec.get("strategy_sha256")):
        raise ValueError("Immutable experiment specification, strategy or native version differs")


def conversion_manifest(native_python):
    """Read installed converter identity without importing or launching the native environment."""
    library = Path(native_python).resolve().parent.parent / "Lib" / "site-packages"
    directory = library / "nautilus_trader" / "persistence"
    binaries = list(directory.glob("wranglers*.pyd"))
    metadata = library / "nautilus_trader-1.231.0.dist-info" / "METADATA"
    source = directory / "wranglers.pyx"
    if len(binaries) != 1 or not source.is_file() or not metadata.is_file() or "Version: 1.231.0" not in metadata.read_text(encoding="utf-8"):
        raise ValueError("Exact installed native 1.231.0 converter metadata is unavailable")
    return {"name": "TradeTickDataWrangler.process_bar_data", "engine_version": "1.231.0",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "binary_sha256": hashlib.sha256(binaries[0].read_bytes()).hexdigest(),
        "settings": {"ts_init_delta": 0, "offset_interval_ms": 100, "timestamp_is_close": True,
            "random_seed": None, "is_raw": False, "sort_data": True}, "bar_processing_offset_ns": 1,
        "bar_execution": False, "trade_execution": True, "book_type": "L1_MBP", "oto_trigger_mode": "FULL",
        "volume_basis": "Native rounded maximum(volume/4, size_increment) per modeled tick; not observed executable liquidity",
        "time_basis": "Compressed modeled OHLC path before actual provider bucket close; not real intraday/session-open times"}


def prepare_experiment(strategy, history, request, *, calendar, benchmark=None, native_python=None):
    """Freeze retained sources and an experiment; never collect or execute anything."""
    from .history_coverage import indicator_observations
    from .market_evidence import derive_indicators

    strategy = validate_strategy(strategy)
    if native_python is None:
        raise ValueError("Trusted configured native interpreter is required to bind converter metadata")
    conversion = conversion_manifest(native_python)
    start, end = instant(request["start_at"]), instant(request["end_at"])
    if start >= end or request.get("currency_basis") != "declared_simulation_assumption":
        raise ValueError("Choose an explicit historical window and simulation USD assumption")
    basis = request.get("decision_basis")
    if basis not in {"recorded_decision", "hindsight_scenario"} or basis == "recorded_decision" and start < instant(strategy["updated_at"]):
        raise ValueError("Recorded strategy availability cannot precede its saved revision; select hindsight explicitly")
    if basis == "recorded_decision" and instant(history["captured_at"]) > start:
        raise ValueError("Source capture is later than the chosen decision window; explicitly select hindsight, not point-in-time evidence")
    if (history.get("symbol") != strategy["symbol"] or history.get("timeframe") != "1Day" or history.get("adjustment") != "raw"
            or history.get("complete") is not True or history.get("pagination_complete") is not True or history.get("error")):
        raise ValueError("Use complete exact-symbol retained raw daily history")
    provenance = history.get("required_coverage", {}).get("provenance", {})
    if digest(calendar) != provenance.get("calendar_sha256"):
        raise ValueError("Calendar differs from the retained source coverage")
    refs = [reference(history.get("artifact")), reference(provenance.get("calendar_reference")), reference(provenance.get("instrument_reference"))]
    observations = indicator_observations(history["bars"], history["required_coverage"], captured_at=history["captured_at"],
        timeframe="1Day", now=instant(history["captured_at"]))
    by_date = {}
    for bar in history["bars"]:
        if bar["t"] in by_date:
            raise ValueError("Duplicate or corrected same-time rows require an exact replacement artifact")
        by_date[bar["t"]] = bar
    bars = []
    if len({row["date"] for row in calendar}) != len(calendar):
        raise ValueError("Retained calendar has duplicate sessions")
    for session in sorted(calendar, key=lambda row: row["date"]):
        day = session["date"]
        proof = observations.get(day, {})
        closed = instant(proof["closed_at"]) if proof.get("closed_at") else None
        if closed is None or closed > end:
            continue
        raw = by_date.get(day, {}).get("raw")
        if not raw or proof.get("closed") is not True:
            if closed >= start or day >= min(by_date):
                raise ValueError("Every expected scored calendar session requires actual closed OHLCV evidence")
            continue
        row = {key: amount(raw[key], positive=True) for key in ("o", "h", "l", "c")}
        row["v"] = amount(raw["v"], places=0)
        if Decimal(row["h"]) < max(Decimal(row[k]) for k in ("o", "l", "c")) or Decimal(row["l"]) > min(Decimal(row[k]) for k in ("o", "h", "c")):
            raise ValueError("Retained OHLC relationships are invalid")
        bars.append({**row, "t": day, "session": day, "at": closed.isoformat(), "source_timestamp": by_date[day]["provider_timestamp"],
            "closed_at": proof["closed_at"], "closure_basis": proof["closure_basis"]})
    scored = [index for index, bar in enumerate(bars) if instant(bar["at"]) >= start]
    if not scored:
        raise ValueError("No complete eligible historical sessions in the requested window")
    window = request["window"]
    if set(window) != {"mode", "train_sessions", "validation_sessions", "gap_sessions", "oos_sessions", "step_sessions"} or window["mode"] not in {"rolling", "expanding"}:
        raise ValueError("Declare exact rolling/expanding expected-session windows")
    if any(type(window[key]) is not int or window[key] < (0 if key == "gap_sessions" else 1) for key in window if key != "mode") or window["step_sessions"] < window["oos_sessions"]:
        raise ValueError("Window counts must be positive, gaps nonnegative and OOS windows disjoint")
    search, selection, budgets = request["search"], request["selection"], request["budgets"]
    if (set(search) != {"mode", "seed", "max_trials", "sampler", "pruner"} or search["mode"] not in {"grid", "adaptive"}
            or search["sampler"] != ("GridSampler" if search["mode"] == "grid" else "TPESampler") or search["pruner"] != "NopPruner"
            or type(search["seed"]) is not int or type(search["max_trials"]) is not int or search["max_trials"] < 1):
        raise ValueError("Choose a finite grid or seeded adaptive TPE with explicit positive trial budget and NopPruner")
    if (set(selection) != {"objective", "direction", "secondary_metric", "secondary_direction", "minimum_closed_trades"}
            or any(selection[key] not in METRICS for key in ("objective", "secondary_metric"))
            or any(selection[key] not in {"maximize", "minimize"} for key in ("direction", "secondary_direction"))):
        raise ValueError("Choose an objective, its direction, a secondary metric and its direction")
    if type(selection["minimum_closed_trades"]) is not int or selection["minimum_closed_trades"] < 1:
        raise ValueError("Minimum closed trades must be a whole number of at least 1 in both training and validation")
    if set(budgets) != {"max_native_runs", "experiment_seconds", "trial_seconds", "no_experiment_time_cap", "no_trial_time_cap"}:
        raise ValueError("Declare every visible run and time budget")
    for key, flag in (("experiment_seconds", "no_experiment_time_cap"), ("trial_seconds", "no_trial_time_cap")):
        if type(budgets[flag]) is not bool or (budgets[key] is None) != budgets[flag] or budgets[key] is not None and (type(budgets[key]) is not int or budgets[key] <= 0):
            raise ValueError("Each deadline needs a positive seconds value or an explicit no-time-cap choice")
    if type(budgets["max_native_runs"]) is not int or budgets["max_native_runs"] < 1:
        raise ValueError("An explicit positive native-run budget is required")
    scenarios = copy.deepcopy(request["scenarios"])
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 32:
        raise ValueError("Choose one to thirty-two explicit fill/cost/seed scenarios")
    for scenario in scenarios:
        if (set(scenario) != {"id", "fee_usd", "fee_per", "limit_fill_probability", "slippage_probability", "random_seed", "latency_ns"}
                or not isinstance(scenario["id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", scenario["id"])
                or scenario["fee_per"] not in {"order", "fill"} or type(scenario["random_seed"]) is not int or scenario["latency_ns"] != 0):
            raise ValueError("Scenario requires exact identifiers, fee basis, native seed and zero-latency daily-close model")
        scenario["fee_usd"] = amount(scenario["fee_usd"], places=2)
        for key in ("limit_fill_probability", "slippage_probability"):
            scenario[key] = amount(scenario[key])
            if Decimal(scenario[key]) > 1:
                raise ValueError("Scenario probabilities must be within zero to one")
    if len({item["id"] for item in scenarios}) != len(scenarios):
        raise ValueError("Scenario IDs must be unique")
    names = sorted(strategy["parameters"])
    count = 1
    for name in names:
        count *= len(strategy["parameters"][name]["values"])
    if count > 100000:
        raise ValueError("Finite space exceeds the explicit preview safety bound of 100000 variants")
    candidates = None
    if search["mode"] == "grid":
        if count > search["max_trials"]:
            raise ValueError(f"Full grid has {count} candidates; trial budget is {search['max_trials']}. No silent truncation is permitted")
        candidates = [{"parameters": dict(zip(names, values, strict=True))} for values in product(*(strategy["parameters"][name]["values"] for name in names))]
        for candidate in candidates:
            candidate["id"] = digest(candidate["parameters"])
    operands = [operand for key in ("entry", "exit") for atom in strategy[key]["atoms"] for operand in (atom["left"], atom["right"])]
    operands.extend(strategy["execution"].get(key) for key in ("limit_price", "stop_price"))
    operands.extend((strategy["execution"].get("exit_plan") or {}).values())
    indicator_names = {operand["name"] for operand in operands if operand and operand["kind"] == "indicator"}
    source = {**history.get("source", {}), "symbol": strategy["symbol"], "instrument": strategy["instrument_id"],
        "timeframe": "1Day", "currency": history.get("currency"), "session": history.get("session"), "adjustment": "raw",
        "full_history": True, "history_hashes": [refs[0]["sha256"]], "precision": "exact source strings; Stockstats float64 calculation"}
    source_bars = [{"t": bar["t"], "raw": {key: bar[key] for key in ("o", "h", "l", "c", "v")}} for bar in bars]
    definitions = derive_indicators(source_bars, source, coverage={"indicator_observations": observations}) if indicator_names else []
    required = max((series["definition"]["minimum_observations"] for series in definitions if series["name"] in indicator_names), default=1) + 1
    folds, cursor = [], scored[0]
    while True:
        train_start = scored[0] if window["mode"] == "expanding" else cursor
        train_end = cursor + window["train_sessions"]
        validation_start = train_end + window["gap_sessions"]
        validation_end = validation_start + window["validation_sessions"]
        oos_start = validation_end + window["gap_sessions"]
        oos_end = oos_start + window["oos_sessions"]
        if oos_end > len(bars):
            break
        fold = {"id": "fold-" + str(len(folds) + 1)}
        for phase, left, right in (("train", train_start, train_end), ("validation", validation_start, validation_end), ("oos", oos_start, oos_end)):
            warmup = max(0, left - required)
            segment = copy.deepcopy(bars[warmup:right])
            derived = derive_indicators(source_bars[warmup:right], source, coverage={"indicator_observations": observations}) if indicator_names else []
            selected_series = [series for series in derived if series["name"] in indicator_names]
            for row in segment:
                row["indicators"] = {series["name"]: next(point for point in series["points"] if point["t"] == row["t"]) for series in selected_series}
            fold[phase] = {"start_at": bars[left]["at"], "end_at": bars[right - 1]["at"], "bars": segment,
                "scored_sessions": right - left, "warmup_sessions": left - warmup,
                "indicator_sources": [{key: series[key] for key in ("name", "definition", "derivation_identity", "comparable_identity", "initialization_history_sha256")} for series in selected_series]}
        folds.append(fold)
        cursor += window["step_sessions"]
    if not folds:
        raise ValueError("Retained history cannot cover one full train/validation/gap/disjoint-OOS fold")
    trial_count = count if search["mode"] == "grid" else search["max_trials"]
    native_runs = len(folds) * (trial_count * 2 + 1) * len(scenarios)
    if native_runs > budgets["max_native_runs"]:
        raise ValueError(f"Complete experiment requires at most {native_runs} native runs; budget is {budgets['max_native_runs']}")
    precision = max(2, max(max(0, -Decimal(row[key]).as_tuple().exponent) for row in bars for key in ("o", "h", "l", "c")))
    frozen_request = {key: copy.deepcopy(request[key]) for key in ("start_at", "end_at", "starting_cash", "decision_basis", "currency_basis", "window", "search", "selection", "budgets")}
    frozen_request.update(starting_cash=amount(request["starting_cash"], positive=True, places=2), scenarios=scenarios)
    benchmark_value = {"available": False, "reason": "No exact retained compatible benchmark selected"}
    if benchmark is not None:
        try:
            benchmark_provenance = benchmark.get("required_coverage", {}).get("provenance", {})
            if (benchmark.get("timeframe") != "1Day" or benchmark.get("adjustment") != "raw" or benchmark.get("complete") is not True
                    or benchmark.get("pagination_complete") is not True or benchmark.get("currency") != "USD"
                    or benchmark.get("error") or benchmark_provenance.get("calendar_sha256") != digest(calendar)
                    or benchmark_provenance.get("session") != provenance.get("session")
                    or not benchmark_provenance.get("instrument_reference")):
                raise ValueError("Benchmark lacks compatible raw daily USD calendar/session and instrument evidence")
            benchmark_proof = indicator_observations(benchmark["bars"], benchmark["required_coverage"],
                captured_at=benchmark["captured_at"], timeframe="1Day", now=instant(benchmark["captured_at"]))
            benchmark_dates = [row["t"] for row in benchmark["bars"]]
            if len(set(benchmark_dates)) != len(benchmark_dates):
                raise ValueError("Benchmark has duplicate source dates")
            selected_dates = {row["t"] for row in bars if instant(row["at"]) >= start}
            if any(benchmark_proof.get(day, {}).get("closed") is not True
                    or instant(benchmark_proof[day]["closed_at"]) != instant(observations[day]["closed_at"]) for day in selected_dates):
                raise ValueError("Benchmark lacks matching closed observations for every scored expected session")
            for row in benchmark["bars"]:
                amount(row["raw"]["c"], positive=True)
            if basis == "recorded_decision" and instant(benchmark["captured_at"]) > start:
                raise ValueError("Later-captured benchmark is unavailable under recorded-decision availability")
            benchmark_refs = [reference(benchmark["artifact"]), reference(benchmark_provenance["calendar_reference"]),
                reference(benchmark_provenance["instrument_reference"])]
            benchmark_value = {"available": True, "symbol": benchmark["symbol"], "artifact": benchmark_refs[0],
                "bars": copy.deepcopy(benchmark["bars"]), "captured_at": benchmark["captured_at"],
                "closure_evidence": {day: benchmark_proof[day] for day in sorted(selected_dates)},
                "provenance": copy.deepcopy(benchmark_provenance), "basis": "Raw price return; dividends excluded"}
            refs.extend(benchmark_refs)
        except (KeyError, TypeError, ValueError) as exc:
            benchmark_value = {"available": False, "reason": str(exc)}
    spec = {"kind": "experiment", "version": EXPERIMENT_VERSION, "engine_version": "1.231.0", "strategy": strategy,
        "strategy_sha256": digest(strategy), "request": frozen_request, "bars": bars, "folds": folds, "candidates": candidates,
        "optimizer": {"name": "optuna", "version": "5.0.0", "sampler": search["sampler"], "pruner": "NopPruner",
            "settings": {"seed": search["seed"], "n_jobs": 1, "n_startup_trials": 10, "n_ei_candidates": 24,
                "multivariate": True, "group": False, "constant_liar": False}},
        "preview_counts": {"finite_candidates": count, "folds": len(folds), "ask_budget_per_fold": trial_count,
            "maximum_native_runs": native_runs, "scenarios": len(scenarios)}, "input_artifacts": refs,
        "representation": {"price_precision": precision, "price_increment": format(Decimal("0.01"), f".{precision}f")},
        "indicator_sources": definitions and [{"name": series["name"], "definition": series["definition"]} for series in definitions if series["name"] in indicator_names],
        "benchmark": benchmark_value, "limitations": ["Retained historical prices can include later revisions; capture time is not historical point-in-time availability.",
            "Signals use completed provider buckets; prior intents execute after the NEXT modeled O tick updates the native book. These compressed path times are not real session-open timestamps.",
            "OHLC ordering, slippage, costs and fills are explicit native simulation assumptions; actual broker fees/fills are not established.",
            "Indicator minimum observation counts are not convergence proof; unavailable initialization prevents a signal.",
            "Each fold and phase resets holdings, cash and indicator state; separate curves are not one tradable compounded portfolio.",
            "Boundary cancels do not fabricate closing fills; ending inventory remains marked only from actual eligible bars.",
            "Adaptive restart is interrupted; public trial history does not restore exact sampler RNG state."]}
    spec["data_availability"] = {"basis": basis, "history_captured_at": history["captured_at"],
        "benchmark_captured_at": benchmark_value.get("captured_at"), "strategy_recorded_at": strategy["updated_at"],
        "point_in_time_established": False, "reason": "A strategy revision timestamp does not prove historical source vintages or availability"}
    spec["conversion"] = conversion
    spec["spec_sha256"] = digest(spec)
    return spec


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def amount(value, *, positive=False, places=None):
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Simulation amounts must be explicit finite decimals") from None
    if not number.is_finite() or number < 0 or positive and number == 0:
        raise ValueError("Simulation amounts must be finite and nonnegative; prices/funds must be positive")
    if places is not None and number != number.quantize(Decimal(1).scaleb(-places)):
        raise ValueError("Simulation input exceeds the installed instrument precision; no rounding is performed")
    return str(number.quantize(Decimal(1).scaleb(-places))) if places is not None else str(number)


def instant(value):
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Simulation timestamps require an explicit timezone")
    return result.astimezone(UTC)


def reference(value):
    if (not isinstance(value, dict) or not re.fullmatch(r"[a-f0-9]{64}", value.get("sha256", ""))
            or not isinstance(value.get("path"), str) or not value["path"].startswith("reports/")
            or ".." in value["path"].split("/") or "\\" in value["path"]):
        raise ValueError("Select a verified saved evidence artifact")
    return {key: value[key] for key in ("path", "sha256")}


def validate_terms(terms):
    if terms.get("currency") != "USD" or terms.get("session") != "regular":
        raise ValueError("Saved terms must explicitly identify USD and regular-session execution; legacy missing fields are not inferred")
    if terms.get("side") != "BUY":
        raise ValueError("SELL-plan simulation requires explicit native starting holdings/cost-basis import; not supported yet")
    if terms.get("order_type") == "STOP_MARKET":
        raise ValueError("BUY STOP_MARKET is not supported by the Alpaca saved-plan profile; use an explicitly reviewed STOP_LIMIT plan")
    if terms.get("order_type") not in {"MARKET", "LIMIT", "STOP_LIMIT"}:
        raise ValueError("Choose a supported saved BUY MARKET, LIMIT or STOP_LIMIT plan")
    if not re.fullmatch(r"[1-9]\d{0,17}", str(terms.get("quantity", ""))):
        raise ValueError("Saved quantity must be positive whole shares; no rounding is performed")
    if (not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", str(terms.get("symbol", "")))
            or terms.get("instrument_id") != terms["symbol"] + ".ALPACA"):
        raise ValueError("Saved instrument must match the supported equity symbol")
    for field in (("limit_price", "stop_price") if terms["order_type"] == "STOP_LIMIT" else ("limit_price",) if terms["order_type"] == "LIMIT" else ()):
        amount(terms.get(field), positive=True, places=2)


def prepare(proposal, history, request, *, calendar):
    """Caller must resolve/hash-check saved history and its calendar artifact first.

    Does not fetch data, write records, launch a process, or approve any order.
    SELL plans require initial native holdings support, which this slice does not invent.
    """
    original_terms = proposal["terms"]
    if request.get("currency") != "USD" or request.get("currency_basis") != "declared_simulation_assumption":
        raise ValueError("Explicitly review USD as the simulation currency assumption; saved order terms remain unchanged")
    if original_terms.get("currency") not in (None, "USD"):
        raise ValueError("Simulation currency conflicts with the saved plan")
    terms = {**original_terms, "currency": "USD"}
    validate_terms(terms)
    if (proposal["revision"] != request.get("proposal_revision") or digest(original_terms) != proposal.get("terms_sha256")
            or terms.get("currency") != "USD" or terms.get("session") != "regular" or terms.get("replacement")):
        raise ValueError("Choose the exact immutable regular-session USD proposal revision, not a replacement")
    if terms.get("time_in_force") not in {"DAY", "GTC"}:
        raise ValueError("Simulation supports saved DAY/GTC plans only")
    if request.get("starting_holdings") != []:
        raise ValueError("This simulation requires an explicitly empty starting portfolio")
    if (request.get("submission_model") != "after_first_completed_bar" or request.get("end_positions") != "leave_open"
            or request.get("actual_fees") != "unknown" or request.get("bar_path") != "open_high_low_close"):
        raise ValueError("Choose explicit daily-close submission, OHLC path, open-ending-position and unknown-actual-fee assumptions")
    start, end, decision = (instant(request[key]) for key in ("start_at", "end_at", "decision_at"))
    if not start <= decision < end:
        raise ValueError("Decision availability must be within the simulation window")
    basis = request.get("decision_basis")
    if basis not in {"recorded_decision", "hindsight_scenario"}:
        raise ValueError("Declare recorded-decision availability or a hindsight scenario")
    if basis == "recorded_decision" and decision < instant(proposal["updated_at"]):
        raise ValueError("A saved revision cannot be available before it was recorded")
    if (history.get("symbol") != terms["symbol"] or history.get("timeframe") != "1Day"
            or history.get("adjustment") != "raw" or history.get("complete") is not True
            or history.get("pagination_complete") is not True or history.get("error")):
        raise ValueError("Simulation requires complete saved raw daily history for the exact symbol")
    provenance = history.get("required_coverage", {}).get("provenance", {})
    if digest(calendar) != provenance.get("calendar_sha256"):
        raise ValueError("Saved calendar does not match the history coverage receipt")
    refs = [reference(history.get("artifact")), reference(provenance.get("calendar_reference")),
            reference(provenance.get("instrument_reference"))]
    sessions = {}
    for session in calendar:
        close = datetime.fromisoformat(session["date"] + "T" + session["close"])
        close = close.replace(tzinfo=ZoneInfo("America/New_York")) if close.tzinfo is None else close
        if start <= close.astimezone(UTC) <= end:
            sessions[session["date"]] = close.astimezone(UTC).isoformat()
    selected = [bar for bar in history["bars"] if bar["t"] in sessions]
    if len(selected) < 2 or len({bar["t"] for bar in selected}) != len(selected) or set(sessions) != {bar["t"] for bar in selected}:
        raise ValueError("Saved data must cover every selected completed calendar session without duplicates")
    precision = max(2, max(max(0, -Decimal(amount(bar["raw"][key], positive=True)).as_tuple().exponent)
                           for bar in selected for key in ("o", "h", "l", "c")))
    representation = {"price_precision": precision, "price_increment": format(Decimal("0.01"), f".{precision}f"),
                      "basis": "Source OHLC precision padded losslessly; cent order tick and saved prices unchanged; no price rounding"}
    bars = []
    for bar in sorted(selected, key=lambda item: item["t"]):
        raw = bar.get("raw", {})
        values = {key: amount(raw[key], positive=True, places=precision) for key in ("o", "h", "l", "c")}
        values["v"] = amount(raw["v"], places=0)
        if Decimal(values["h"]) < max(Decimal(values[k]) for k in ("o", "l", "c")) or Decimal(values["l"]) > min(Decimal(values[k]) for k in ("o", "h", "c")):
            raise ValueError("Saved OHLC relationships are invalid")
        bars.append({**values, "at": sessions[bar["t"]], "session": bar["t"], "source_timestamp": bar["provider_timestamp"]})
    if instant(bars[-2]["at"]) < decision or instant(bars[-1]["at"]) > instant(history["captured_at"]):
        raise ValueError("At least two completed bars at/after decision availability must be retained")
    assumptions = {key: request[key] for key in ("submission_model", "end_positions", "actual_fees", "bar_path")}
    assumptions.update(fee_usd=amount(request["fee_usd"], places=2), fee_per=request["fee_per"],
                       limit_fill_probability=amount(request["limit_fill_probability"]),
                       slippage_probability=amount(request["slippage_probability"]), random_seed=request["random_seed"],
                       latency_ns=request["latency_ns"])
    if assumptions["fee_per"] not in {"order", "fill"} or any(Decimal(assumptions[key]) > 1 for key in ("limit_fill_probability", "slippage_probability")):
        raise ValueError("Choose a fee basis and fill/slippage probabilities within zero to one")
    if (type(assumptions["random_seed"]) is not int or type(assumptions["latency_ns"]) is not int
            or not 0 <= assumptions["latency_ns"] < 2**64):
        raise ValueError("Choose an integer random seed and nonnegative native latency in nanoseconds")
    if terms["time_in_force"] == "DAY" and assumptions["latency_ns"] != 0:
        raise ValueError("The native daily-close DAY profile currently requires zero assumed latency for final-session cancellation")
    keys = ("symbol", "instrument_id", "currency", "session", "side", "quantity", "order_type", "limit_price", "stop_price", "time_in_force", "exit_plan")
    safe_terms = {key: copy.deepcopy(terms[key]) for key in keys if key in terms}
    spec = {"version": VERSION, "engine_version": "1.231.0", "proposal": {"id": proposal["id"], "revision": proposal["revision"],
            "terms_sha256": proposal["terms_sha256"], "recorded_at": proposal["updated_at"]},
            "saved_terms": copy.deepcopy(original_terms), "terms": safe_terms,
            "start_at": start.isoformat(), "end_at": end.isoformat(), "decision_at": decision.isoformat(), "decision_basis": basis,
            "starting_cash": amount(request["starting_cash"], positive=True, places=2), "starting_holdings": [],
            "currency_basis": {"currency": "USD", "basis": request["currency_basis"], "saved_terms_currency": original_terms.get("currency")},
            "bars": bars, "input_artifacts": refs, "assumptions": assumptions, "representation": representation,
            "limitations": ["Daily bars do not reveal within-session target/stop ordering; OHLC path is a model assumption.",
                "Orders are submitted after the first completed bar at/after decision availability; native close-price fills are simulated, not broker predictions.",
                "Actual fees are unknown; supplied fees, fill probabilities and latency are scenario assumptions.",
                "No dividends/corporate actions, live execution, historical research reconstruction or forced liquidation are modeled."]}
    if basis == "hindsight_scenario":
        spec["limitations"].append("Hindsight scenario: plan availability at the selected historical time is not established.")
    if terms["time_in_force"] == "DAY":
        spec["limitations"].append("DAY orders submitted after the first close are canceled after the next sourced session's bar processing; this is a daily-close scenario, not intraday broker expiry.")
    spec["spec_sha256"] = digest(spec)
    return spec


def stop_calculation_process(process):
    """Bound exact-handle termination/reaping; this does not supervise descendants."""
    actions, errors = [], []
    for action in ("terminate", "kill"):
        if process.poll() is not None:
            break
        try:
            actions.append(action)
            getattr(process, action)()
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired) as error:
            errors.append(type(error).__name__)
    return {"pid": process.pid, "returncode": process.poll(), "termination_confirmed": process.poll() is not None,
            "actions": actions, "errors": errors, "descendants_confirmed": False}


def execute(spec, native_python, process_state=None, *, cancelled=None, timeout=None):
    """Explicit simulation action; caller runs off the HTTP thread and persists returned evidence.

    Never call from preview/prepare. Native executable is trusted launch configuration,
    not a request parameter. This worker has no inherited credential environment.
    """
    if digest({key: value for key, value in spec.items() if key != "spec_sha256"}) != spec.get("spec_sha256"):
        raise ValueError("Simulation preview changed")
    environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    environment.update(PYTHONIOENCODING="utf-8", PYTHONNOUSERSITE="1")
    directory = tempfile.mkdtemp(prefix="tradingagents-simulation-")
    process = None
    try:
        environment.update(TEMP=directory, TMP=directory)
        payload = json.dumps(spec, allow_nan=False)
        process = subprocess.Popen([str(native_python), "-s", str(Path(__file__).with_name("evaluation_worker.py"))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                cwd=directory, env=environment, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            if process_state:
                process_state(process, True)
            started, pending_input = time.monotonic(), payload
            while True:
                if (cancelled and cancelled()) or timeout is not None and time.monotonic() - started >= timeout:
                    stopped = stop_calculation_process(process)
                    if stopped["termination_confirmed"]:
                        try:
                            process.communicate(timeout=1)
                            stopped["pipes_drained"] = True
                        except subprocess.TimeoutExpired:
                            stopped["pipes_drained"] = False
                    return {"kind": spec.get("kind", "simulation"), "status": "interrupted", "spec_sha256": spec["spec_sha256"],
                        "interruption_reason": "cancelled" if cancelled and cancelled() else "deadline",
                        "process_returncode": process.returncode, "termination": stopped,
                        "temporary_directory": directory, "native_outcome": "unknown_partial_outcome",
                        "native_report_available": False,
                        "error": "Owned native process cancelled or explicit deadline reached; no completed result established"}
                try:
                    output, _ = process.communicate(pending_input, timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    pending_input = None
        finally:
            if process.poll() is None:
                stop_calculation_process(process)
            if process_state:
                process_state(process, False)
    finally:
        if process is None or process.poll() is not None:
            # Retained files do not establish completed work or clean shutdown.
            with suppress(OSError):
                shutil.rmtree(directory)
    if process.returncode:
        raise ValueError("Native simulation worker failed; no execution result established")
    output = json.loads(output)
    if output.get("spec_sha256") != spec["spec_sha256"] or output.get("kind") != spec.get("kind", "simulation"):
        raise ValueError("Native simulation result binding differs from its preview")
    return output


def execute_experiment(spec, native_python, *, event, process_state=None, cancelled=None):
    """Public service-only optimizer; every native execution remains in its isolated worker.

    Event persistence is synchronous. Its errors propagate before any subsequent TELL or
    dispatch. Interruption never pretends to restore the sampler's private random state.
    """
    validate_experiment(spec)
    capability = experiment_capabilities()["optimizer"]
    if not capability["available"]:
        raise ValueError(capability["reason"])
    import optuna

    if optuna.__version__ != "5.0.0":
        raise ValueError("Installed optimizer implementation version differs from the immutable preview")
    config = spec["request"]
    selection, budgets = config["selection"], config["budgets"]
    started, native_runs = time.monotonic(), 0
    completed, trials, comparisons, reuse = [], [], [], {}
    overall_status = "completed"

    def stopped():
        return bool(cancelled and cancelled()) or budgets["experiment_seconds"] is not None and time.monotonic() - started >= budgets["experiment_seconds"]

    def emit(kind, fold_id, trial_id=None, **values):
        payload = {"type": kind, "fold_id": fold_id, "trial_id": trial_id, "spec_sha256": spec["spec_sha256"], **values}
        payload["source_event_id"] = digest({key: payload.get(key) for key in ("type", "fold_id", "trial_id", "phase", "scenario_id", "spec_sha256")})
        event(payload)

    def run_phase(fold, trial_id, parameters, phase):
        nonlocal native_runs
        outputs = []
        for scenario in config["scenarios"]:
            if stopped():
                return {"status": "interrupted", "scenarios": outputs, "metrics": None}
            native_spec = {"kind": "strategy_trial", "version": EXPERIMENT_VERSION, "engine_version": spec["engine_version"],
                "experiment_sha256": spec["spec_sha256"], "strategy": spec["strategy"], "parameters": parameters,
                "segment": fold[phase], "starting_cash": config["starting_cash"], "starting_holdings": [],
                "assumptions": scenario, "representation": spec["representation"], "input_artifacts": spec["input_artifacts"],
                "benchmark": spec["benchmark"], "limitations": spec["limitations"], "conversion": spec["conversion"]}
            native_spec["spec_sha256"] = digest(native_spec)
            fingerprint = digest({key: native_spec[key] for key in native_spec if key != "spec_sha256"})
            reused = fingerprint in reuse
            if reused:
                source_trial, result = reuse[fingerprint]
                emit("dispatch", fold["id"], trial_id, phase=phase, scenario_id=scenario["id"], parameters=parameters,
                    native_spec_sha256=native_spec["spec_sha256"], execution="reused_source_trial", source_trial=source_trial)
            else:
                if native_runs >= budgets["max_native_runs"]:
                    emit("budget", fold["id"], trial_id, phase=phase, scenario_id=scenario["id"], reason="Native-run budget reached")
                    return {"status": "interrupted", "scenarios": outputs, "metrics": None}
                emit("dispatch", fold["id"], trial_id, phase=phase, scenario_id=scenario["id"], parameters=parameters,
                    native_spec_sha256=native_spec["spec_sha256"], execution="native", native_spec=native_spec)
                native_runs += 1
                seconds = budgets["trial_seconds"]
                if budgets["experiment_seconds"] is not None:
                    remaining = max(0, budgets["experiment_seconds"] - (time.monotonic() - started))
                    seconds = min(seconds, remaining) if seconds is not None else remaining
                try:
                    result = execute(native_spec, native_python, process_state, cancelled=cancelled, timeout=seconds)
                except (ValueError, OSError) as exc:
                    result = {"kind": "strategy_trial", "status": "failed", "spec_sha256": native_spec["spec_sha256"],
                        "error": type(exc).__name__ + ": " + str(exc)}
                if result.get("status") == "interrupted" and result.get("interruption_reason") == "deadline" and not stopped():
                    result = {**result, "status": "timed_out", "error": "Native process deadline; partial native outcome unknown, exploratory attempt unscored; no automatic retry or resume"}
                source_trial = {"fold_id": fold["id"], "trial_id": trial_id, "phase": phase, "scenario_id": scenario["id"]}
                if result.get("status") == "completed_with_limitations":
                    reuse[fingerprint] = (source_trial, copy.deepcopy(result))
            emit("result", fold["id"], trial_id, phase=phase, scenario_id=scenario["id"], result=result,
                source_trial=source_trial, execution="reused_source_trial" if reused else "native")
            outputs.append({"scenario_id": scenario["id"], "result": result, "source_trial": source_trial})
            comparisons.append({"fold_id": fold["id"], "trial_id": trial_id, "phase": phase, "scenario_id": scenario["id"],
                "status": result["status"], "metrics": result.get("metrics"), "source_trial": source_trial})
            if result["status"] == "interrupted":
                return {"status": "interrupted", "scenarios": outputs, "metrics": None}
        available = all(item["result"].get("status") == "completed_with_limitations" and item["result"].get("metrics")
            and item["result"].get("coverage", {}).get("complete") is True for item in outputs)
        metrics = None
        if available:
            metrics = {name: str(sum((Decimal(item["result"]["metrics"][name]) for item in outputs), Decimal(0)) / len(outputs)) for name in METRICS}
            metrics["closed_trades"] = min(item["result"]["metrics"]["closed_trades"] for item in outputs)
            metrics["aggregation"] = "Arithmetic mean of independent scenario metrics; minimum closed-trade count; not compounded equity"
        return {"status": "completed" if available else "unavailable", "scenarios": outputs, "metrics": metrics}

    def ranking(item):
        metrics = item["validation"]["metrics"]
        return (Decimal(metrics[selection["objective"]]) * (-1 if selection["direction"] == "maximize" else 1),
            Decimal(metrics[selection["secondary_metric"]]) * (-1 if selection["secondary_direction"] == "maximize" else 1), item["parameter_id"])

    domains = {name: item["values"] for name, item in sorted(spec["strategy"]["parameters"].items())}
    for fold in spec["folds"]:
        if stopped():
            overall_status = "cancelled" if cancelled and cancelled() else "interrupted"
            break
        optimizer = spec["optimizer"]
        if optimizer["sampler"] == "GridSampler":
            sampler = optuna.samplers.GridSampler(domains, seed=config["search"]["seed"])
        else:
            sampler = optuna.samplers.TPESampler(**{key: value for key, value in optimizer["settings"].items() if key != "n_jobs"})
        study = optuna.create_study(direction=selection["direction"], sampler=sampler, pruner=optuna.pruners.NopPruner())
        eligible = []
        maximum = len(spec["candidates"]) if spec["candidates"] is not None else config["search"]["max_trials"]
        interrupted = False
        for _ in range(maximum):
            if stopped():
                interrupted = True
                break
            trial = study.ask()
            parameters = {name: trial.suggest_categorical(name, values) for name, values in domains.items()}
            identity = str(trial.number)
            emit("ask", fold["id"], identity, parameters=parameters, parameter_id=digest(parameters), optimizer=optimizer)
            train = run_phase(fold, identity, parameters, "train")
            validation = run_phase(fold, identity, parameters, "validation") if train["status"] != "interrupted" else {"status": "interrupted", "metrics": None, "scenarios": []}
            item = {"fold_id": fold["id"], "trial_id": identity, "parameters": parameters, "parameter_id": digest(parameters),
                "train": train, "validation": validation, "execution_status": "completed" if train["status"] == validation["status"] == "completed" else "unavailable"}
            metrics = validation["metrics"]
            ready = bool(metrics and train["metrics"] and all(phase["metrics"]["closed_trades"] >= selection["minimum_closed_trades"]
                and all(row["result"].get("coverage", {}).get("complete") is True for row in phase["scenarios"])
                for phase in (train, validation)))
            item["eligible"] = ready
            item["analytical_outcome"] = "eligible" if ready else "ineligible_unscored"
            trials.append(item)
            if train["status"] == "interrupted" or validation["status"] == "interrupted":
                item["status"] = "interrupted"
                interrupted = True
                break  # Retain ASK/received facts; an unobserved objective is never TELLed.
            if ready:
                eligible.append(item)
            state = optuna.trial.TrialState.COMPLETE if ready else optuna.trial.TrialState.FAIL
            score = float(Decimal(metrics[selection["objective"]])) if ready else None
            # Native RESULT events above are durably retained before optimizer state is changed.
            try:
                study.tell(trial, score, state=state)
            except RuntimeError:
                if not isinstance(sampler, optuna.samplers.GridSampler) or not sampler.is_exhausted(study) or study.trials[trial.number].state != state:
                    raise
            emit("tell", fold["id"], identity, state=state.name, score=score, eligible=ready,
                reason=None if ready else "Required actual results or minimum closed-trade eligibility are unavailable")
        if interrupted:
            completed.append({"id": fold["id"], "status": "interrupted", "winner": None, "reason": "Cancellation or explicit budget interrupted this fold"})
            overall_status = "cancelled" if cancelled and cancelled() else "interrupted"
            break
        if not eligible:
            completed.append({"id": fold["id"], "status": "no_qualifier", "winner": None, "reason": "No candidate meets the explicit eligibility requirements"})
            emit("selection", fold["id"], winner=None, reason="No qualifying strategy")
            continue
        winner = min(eligible, key=ranking)
        emit("selection", fold["id"], winner["trial_id"], parameters=winner["parameters"], parameter_id=winner["parameter_id"], basis="Train/validation only; OOS excluded")
        oos = run_phase(fold, winner["trial_id"], winner["parameters"], "oos")
        emit("oos", fold["id"], winner["trial_id"], result=oos)
        completed.append({"id": fold["id"], "status": oos["status"], "winner": winner["parameters"], "selected_trial_id": winner["trial_id"],
            "train": winner["train"], "validation": winner["validation"], "oos": oos, "eligibility": selection})
        if oos["status"] == "interrupted":
            overall_status = "cancelled" if cancelled and cancelled() else "interrupted"
            break
        if oos["status"] != "completed":
            overall_status = "failed"
    if overall_status == "completed" and not any(row.get("winner") for row in completed):
        overall_status = "no_qualifier"
    selected_count = sum(row.get("winner") is not None for row in completed)
    gaps = sum(row["status"] == "no_qualifier" for row in completed)
    analytical_outcome = "no_qualifier" if not selected_count else "selection_gaps" if gaps else "evaluated"
    reasons = [{"fold_id": row["id"], "stage": "selection" if row["status"] == "no_qualifier" else "oos",
        "status": row["status"], "reason": row.get("reason") or "Required selected-strategy OOS result is unavailable"}
        for row in completed if row["status"] != "completed"]
    return {"kind": "experiment", "version": EXPERIMENT_VERSION, "spec_sha256": spec["spec_sha256"], "status": overall_status,
        "analytical_outcome": analytical_outcome, "reasons": reasons,
        "counts": {"asked_trials": len(trials), "eligible_trials": sum(item["eligible"] for item in trials),
            "unscored_trials": sum(not item["eligible"] for item in trials), "selected_folds": selected_count,
            "selection_gap_folds": gaps, "oos_completed_folds": sum(row.get("oos", {}).get("status") == "completed" for row in completed),
            "oos_unperformed_no_selection": gaps, "unprocessed_folds": len(spec["folds"]) - len(completed)},
        "folds": completed, "trials": trials, "comparison": comparisons, "optimizer": spec["optimizer"], "limitations": spec["limitations"],
        "native_runs": native_runs, "elapsed_seconds": time.monotonic() - started,
        "coverage": {"expected_folds": len(spec["folds"]), "finished_folds": len(completed), "synthetic_compound": {"available": False,
            "reason": "Independent reset-capital folds are displayed separately; no compounded portfolio is asserted"}}}
