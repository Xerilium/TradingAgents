"""Prepare an immutable saved-plan simulation; execution is an explicit separate call."""

import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

VERSION = "saved-plan-nautilus-v1"


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


def execute(spec, native_python, process_state=None):
    """Explicit simulation action; caller runs off the HTTP thread and persists returned evidence.

    Never call from preview/prepare. Native executable is trusted launch configuration,
    not a request parameter. This worker has no inherited credential environment.
    """
    if digest({key: value for key, value in spec.items() if key != "spec_sha256"}) != spec.get("spec_sha256"):
        raise ValueError("Simulation preview changed")
    environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    environment.update(PYTHONIOENCODING="utf-8", PYTHONNOUSERSITE="1")
    with tempfile.TemporaryDirectory(prefix="tradingagents-simulation-") as directory:
        environment.update(TEMP=directory, TMP=directory)
        payload = json.dumps(spec, allow_nan=False)
        with subprocess.Popen([str(native_python), "-s", str(Path(__file__).with_name("evaluation_worker.py"))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                cwd=directory, env=environment, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
            try:
                if process_state:
                    process_state(process, True)
                output, _ = process.communicate(payload)
            finally:
                if process_state:
                    process_state(process, False)
    if process.returncode:
        raise ValueError("Native simulation worker failed; no execution result established")
    output = json.loads(output)
    if output.get("spec_sha256") != spec["spec_sha256"] or output.get("kind") != "simulation":
        raise ValueError("Native simulation result binding differs from its preview")
    return output
