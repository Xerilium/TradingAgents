"""Current Yahoo US equity discovery through the installed yfinance screener."""

import copy
import hashlib
import json
import math
import re
import time
from collections.abc import KeysView
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import yfinance as yf

FIELDS = {"min_price": ("GTE", "intradayprice"), "max_price": ("LTE", "intradayprice"),
          "min_market_cap": ("GTE", "intradaymarketcap"), "min_volume": ("GTE", "avgdailyvol3m")}
SORTS = ("ticker", "percentchange", "dayvolume", "intradaymarketcap")
DEFAULT = {"observations": {}, "definitions": {}, "definition_history": [], "runs": {}, "schedule_slots": {}}


def validate_options(saved):
    from urllib.parse import urlsplit

    from .linked_orders import OPTION_MAPPING, option_contract
    observations, selections = saved.get("option_observations", {}), saved.get("option_selections", {})
    if not isinstance(observations, dict) or not isinstance(selections, dict):
        raise ValueError("Invalid retained option discovery")
    for identity, observation in observations.items():
        if str(UUID(identity)) != identity or observation.get("id") != identity:
            raise ValueError("Invalid option observation identity")
        payload = {key: value for key, value in observation.items() if key != "sha256"}
        if hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest() != observation.get("sha256"):
            raise ValueError("Retained option observation hash differs")
        if not isinstance(observation.get("contracts"), list) or not isinstance(observation.get("query"), dict):
            raise ValueError("Invalid retained option contract page")
        reference = observation["artifact"]
        if not isinstance(reference.get("path"), str) or not re.fullmatch(r"[a-f0-9]{64}", reference.get("sha256", "")):
            raise ValueError("Option response artifact is unavailable")
        datetime.fromisoformat(observation["received_at"])
        for contract in observation["contracts"]:
            source = urlsplit(contract.get("source", ""))
            if (contract.get("mapping_version") != OPTION_MAPPING or not isinstance(contract.get("raw"), dict)
                    or contract.get("sha256") != hashlib.sha256(json.dumps(contract["raw"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                    or contract.get("response_sha256") != reference["sha256"] or source.scheme != "https"
                    or source.netloc not in {"paper-api.alpaca.markets", "api.alpaca.markets"}
                    or not (source.path == "/v2/options/contracts" or source.path.startswith("/v2/options/contracts/"))):
                raise ValueError("Option contract receipt binding differs")
            for key in ("requested_at", "received_at"):
                if datetime.fromisoformat(contract[key]).utcoffset() is None:
                    raise ValueError("Option receipt requires dated source observations")
    feeds = set()
    for symbol, selection in selections.items():
        observation = observations.get(selection.get("observation_id"), {})
        envelope = selection.get("contract")
        if (selection.get("symbol") != symbol or selection.get("feed") not in {"opra", "indicative"}
                or envelope not in observation.get("contracts", []) or option_contract(envelope)["symbol"] != symbol):
            raise ValueError("Selected option differs from its retained supported contract")
        datetime.fromisoformat(selection["selected_at"])
        if "feed_changed_at" in selection:
            datetime.fromisoformat(selection["feed_changed_at"])
        feeds.add(selection["feed"])
    if len(feeds) > 1:
        raise ValueError("The native option subscription uses one explicit feed")


def option_state(service):
    saved = service.store.database.read("discovery", DEFAULT)
    return {"revision": saved["revision"], "observations": saved["data"].get("option_observations", {}),
        "selections": saved["data"].get("option_selections", {})}


def scan_query(value):
    """Use the installed provider grammar; no executable expressions."""
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"operator", "operands"} or not isinstance(value["operands"], list):
        raise ValueError("A provider query contains operator and operands")
    operands = [scan_query(item) if isinstance(item, dict) else item for item in value["operands"]]
    return yf.EquityQuery(value["operator"], operands)


def scan_definition(value, previous=None):
    from .attention import validate_atom
    from .workspace import text
    if not isinstance(value, dict):
        raise ValueError("Choose a declarative scan definition")
    query = scan_query(value.get("query"))
    target = copy.deepcopy(value.get("target", {}))
    if target.get("mode") not in {"fixed", "snapshot", "follow", "provider"}:
        raise ValueError("Choose a fixed, watchlist or provider-query universe")
    if target["mode"] == "fixed":
        if not isinstance(target.get("symbols"), list) or not target["symbols"] or any(
                not isinstance(symbol, str) or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", symbol) for symbol in target["symbols"]):
            raise ValueError("Fixed scans require explicit stock symbols")
        target["symbols"] = sorted(set(target["symbols"]))
    elif target["mode"] in {"snapshot", "follow"} and not text(target.get("watchlist_id"), 100, "watchlist id"):
        raise ValueError("Select a saved watchlist")
    elif target["mode"] == "provider" and query is None:
        raise ValueError("A provider universe requires an explicit provider query")
    program = copy.deepcopy(value.get("program"))
    if program is not None:
        from .evaluation import validate_scan_program
        validate_scan_program(program)
    conditions = copy.deepcopy(value.get("atoms", []))
    if program is None and (not isinstance(conditions, list) or not 1 <= len(conditions) <= 16 or value.get("operator") not in {"ALL", "ANY"}):
        raise ValueError("Choose ALL or ANY of 1 to 16 existing scan predicates")
    if program is not None and (not isinstance(conditions, list) or conditions):
        raise ValueError("Choose a versioned program or existing scan atoms in one definition")
    for atom in conditions:
        validate_atom(atom)
        if atom["scope"] in {"account", "research"} or atom["kind"] == "policy_condition" or atom["kind"] == "indicator" and atom["parameters"].get("context") != "current":
            raise ValueError("Stock scans use current stock predicates, not account, proposal or research-agent conditions")
    collection = copy.deepcopy(value.get("collection", {}))
    if collection.get("mode") not in {"retained", "collect"} or collection.get("feed") != "iex" or collection.get("adjustment") not in {"raw", "split", "dividend", "all"}:
        raise ValueError("Choose retained-only or explicitly authorized IEX collection with an adjustment basis")
    for key, maximum in (("lookback_days", 3660), ("max_symbols", 1000), ("max_pages", 20), ("max_intervals", 6), ("max_requests", 10000), ("max_seconds", 86400)):
        if type(collection.get(key)) is not int or not 1 <= collection[key] <= maximum:
            raise ValueError("Choose a positive bounded " + key)
    intervals = {atom["parameters"]["timeframe"] for atom in conditions if atom["kind"] == "indicator"}
    if program is not None:
        intervals.update(item["timeframe"] for item in program["inputs"].values())
        if collection["mode"] == "collect" and any(item["history_key"] for item in program["inputs"].values()):
            raise ValueError("Fresh program collection cannot promise an old retained cache key")
    if any(atom["scope"] == "history" for atom in conditions):
        intervals.add("1Day")
    if len(intervals) > collection["max_intervals"]:
        raise ValueError("Scan interval count exceeds its explicit budget")
    if query is not None and collection["mode"] != "collect":
        raise ValueError("A live Yahoo query requires explicit collection authority")
    for interval in intervals:
        keys = {atom["parameters"].get("history_key") or "" for atom in conditions
                if atom["kind"] == "indicator" and atom["parameters"]["timeframe"] == interval}
        if len(keys) > 1 or collection["mode"] == "collect" and any(keys):
            raise ValueError("Each interval uses one retained cache selection; fresh collection cannot promise an old cache key")
    schedule = copy.deepcopy(value.get("schedule", {}))
    if (type(schedule.get("enabled")) is not bool or schedule.get("timezone") != "America/New_York"
            or type(schedule.get("cadence_minutes")) is not int or not 1 <= schedule["cadence_minutes"] <= 525600
            or schedule.get("session") not in {"any", "regular"} or type(value.get("alert")) is not bool):
        raise ValueError("Choose explicit schedule opt-in, New York cadence/session and alert opt-in")
    name = text(value.get("name"), 100, "scan name")
    if not name:
        raise ValueError("Name the scan")
    return {"id": previous["id"] if previous else str(uuid4()), "name": name,
        "revision": previous["revision"] + 1 if previous else 1, "query": query.to_dict() if query else None,
        "target": target, "operator": program["operator"] if program is not None else value["operator"], "atoms": conditions, "collection": collection,
        "schedule": schedule, "alert": value["alert"], "updated_at": datetime.now(UTC).isoformat(),
        **({"program": program} if program is not None else {})}


def seal(result):
    result = {**result, "id": str(uuid4())}
    result["sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return result


def validate(saved, workspace=None, resolve_artifact=None):
    if not isinstance(saved, dict) or not isinstance(saved.get("observations"), dict):
        raise ValueError("Invalid saved discovery observations")
    validate_options(saved)
    for identity, result in saved["observations"].items():
        if not isinstance(result, dict) or str(UUID(identity)) != identity or result.get("id") != identity:
            raise ValueError("Invalid saved discovery identity")
        payload = {key: value for key, value in result.items() if key != "sha256"}
        if hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest() != result.get("sha256"):
            raise ValueError("Saved discovery observation hash differs")
        criteria(result.get("criteria"))
        if result.get("status") not in {"completed", "failed"} or not isinstance(result.get("rows"), list):
            raise ValueError("Invalid saved discovery outcome")
        for name in ("requested_at", "captured_at"):
            datetime.fromisoformat(result[name])
        for row in result["rows"]:
            if not isinstance(row, dict) or "regularMarketTime" not in row:
                raise ValueError("Invalid saved discovery stock observation")
            stamp = row.get("regularMarketTime")
            if stamp is not None and (type(stamp) not in (int, float) or not math.isfinite(stamp) or not 0 <= stamp <= 253402300799):
                raise ValueError("Invalid saved discovery market timestamp")
    revisions = {}
    for definition in [*saved.get("definition_history", []), *saved.get("definitions", {}).values()]:
        scan_definition(definition)
        if workspace is not None:
            scan_formula_bindings(workspace, definition.get("program"))
        if str(UUID(definition["id"])) != definition["id"] or type(definition["revision"]) is not int or definition["revision"] < 1:
            raise ValueError("Invalid saved scan definition identity/revision")
        key = (definition["id"], definition["revision"])
        content = {name: definition[name] for name in ("name", "query", "target", "operator", "atoms", "collection", "schedule", "alert", "updated_at")}
        if "program" in definition:
            content["program"] = definition["program"]
        if "import_lineage" in definition:
            content["import_lineage"] = definition["import_lineage"]
        if key in revisions and revisions[key] != content:
            raise ValueError("Immutable scan definition revision differs")
        revisions[key] = content
        for member_id, member in definition.get("memberships", {}).items():
            if str(UUID(member_id)) != member_id or member.get("status") not in {"monitoring", "no_longer_monitored"} or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", str(member.get("symbol", ""))):
                raise ValueError("Invalid saved scan membership")
    for identity, run in saved.get("runs", {}).items():
        definition = run["definition"]
        if str(UUID(identity)) != identity or run.get("id") != identity or (definition["id"], definition["revision"]) not in revisions:
            raise ValueError("Saved scan run lacks its immutable definition")
        if {key: definition[key] for key in revisions[(definition["id"], definition["revision"]) ]} != revisions[(definition["id"], definition["revision"])]:
            raise ValueError("Saved scan run definition differs from its immutable revision")
        if run.get("status") not in {"queued", "running", "canceling", "completed", "completed_with_gaps", "canceled", "interrupted", "failed"}:
            raise ValueError("Invalid saved scan run status")
        if datetime.fromisoformat(run["cutoff"]).tzinfo is None or not isinstance(run.get("results"), dict):
            raise ValueError("Invalid saved scan cutoff/results")
        if definition.get("program"):
            from .investor import digest
            if (run.get("program_sha256") != digest(definition["program"])
                    or datetime.fromisoformat(run["cutoff"]) > datetime.fromisoformat(run["requested_at"])
                    or workspace is not None and run.get("formula_definitions") != scan_formula_bindings(workspace, definition["program"])):
                raise ValueError("Saved program run differs from its frozen definition, formula revisions or market cutoff")
        for symbol, result in run["results"].items():
            if result.get("symbol") != symbol or symbol not in run["universe"]["members"] or result.get("state") not in {"matched", "clear", "unavailable"}:
                raise ValueError("Invalid saved per-stock scan outcome")
            if definition.get("program"):
                validate_program_calculation(result.get("calculation"), definition, run["cutoff"], resolve_artifact)
        if definition.get("program") and run["status"] not in {"queued", "running", "canceling"}:
            counts = {state: sum(row["state"] == state for row in run["results"].values()) for state in ("matched", "clear", "unavailable")}
            if run.get("counts") != counts or run.get("unprocessed") != scan_unprocessed(run):
                raise ValueError("Program terminal counts/unprocessed stocks differ from retained actual results")


def validate_program_calculation(calculation, definition, cutoff, resolve_artifact=None):
    from .evaluation import reference, validate_scan_calculation, validate_scan_result
    from .investor import digest
    if not isinstance(calculation, dict):
        raise ValueError("Program outcome lacks its immutable calculation artifacts")
    for name in ("spec_artifact", "result_artifact"):
        reference(calculation.get(name))
    result = calculation.get("result")
    if (not isinstance(result, dict) or result.get("spec_sha256") != calculation.get("spec_sha256")
            or result.get("result_sha256") != calculation.get("result_sha256")
            or digest({key: value for key, value in result.items() if key != "result_sha256"}) != calculation["result_sha256"]):
        raise ValueError("Program result summary/hash differs from its immutable calculation")
    if resolve_artifact is not None:
        spec, retained = resolve_artifact(calculation["spec_artifact"]), resolve_artifact(calculation["result_artifact"])
        if (not isinstance(spec, dict) or retained != result or spec.get("program") != definition["program"]
                or spec.get("market_cutoff") != cutoff or spec.get("spec_sha256") != calculation["spec_sha256"]):
            raise ValueError("Program source/specification/result artifacts are unavailable or differ")
        validate_scan_calculation(spec)
        if result.get("status") not in {"failed", "interrupted"}:
            validate_scan_result(result, spec)


def scan_unprocessed(run):
    return [symbol for symbol in run["universe"]["members"] if symbol not in run["results"]
        or run["results"][symbol].get("processing_status") in {"failed", "interrupted", "cancelled", "canceled"}]


def metadata():
    query = yf.EquityQuery("EQ", ["region", "us"])
    def serial(value):
        if isinstance(value, dict):
            return {key: serial(item) for key, item in value.items()}
        return sorted(value) if isinstance(value, (set, frozenset, KeysView)) else value
    return {"sectors": sorted(query.valid_values["sector"]), "sorts": SORTS,
            "provider": "Yahoo Finance via yfinance", "scope": "Current US equities", "page_size": 25,
            "query_schema": {"operators": ["AND", "OR", "EQ", "IS-IN", "BTWN", "GT", "LT", "GTE", "LTE"],
                             "fields": serial(query.valid_fields), "values": serial(query.valid_values)}}


def criteria(value):
    if not isinstance(value, dict) or set(value) - {*FIELDS, "sector", "sort", "ascending"}:
        raise ValueError("Unknown US equity screen criteria")
    result = {"sort": value.get("sort", "ticker"), "ascending": value.get("ascending", True)}
    if result["sort"] not in SORTS or type(result["ascending"]) is not bool:
        raise ValueError("Choose a supported screen sort and direction")
    for name in FIELDS:
        number = value.get(name)
        if number is None or number == "":
            continue
        if type(number) not in (int, float) or not math.isfinite(number) or number < 0:
            raise ValueError("Screen thresholds must be finite nonnegative numbers")
        result[name] = number
    if result.get("min_price", 0) > result.get("max_price", math.inf):
        raise ValueError("Minimum price cannot exceed maximum price")
    sector = value.get("sector")
    if sector:
        if sector not in metadata()["sectors"]:
            raise ValueError("Choose a sector supported by the installed screener")
        result["sector"] = sector
    return result


def discover(request):
    selected = criteria(request.get("criteria", {}))
    offset = request.get("offset", 0)
    if type(offset) is not int or offset < 0:
        raise ValueError("Screen offset must be a nonnegative integer")
    clauses = [yf.EquityQuery("EQ", ["region", "us"])]
    clauses += [yf.EquityQuery(operator, [field, selected[key]])
                for key, (operator, field) in FIELDS.items() if key in selected]
    if selected.get("sector"):
        clauses.append(yf.EquityQuery("EQ", ["sector", selected["sector"]]))
    query = yf.EquityQuery("AND", clauses) if len(clauses) > 1 else clauses[0]
    result = {"provider": "Yahoo Finance via yfinance", "scope": "Current US equity screen",
              "source_url": "https://query1.finance.yahoo.com/v1/finance/screener", "library_version": yf.__version__,
              "criteria": selected, "query": query.to_dict(), "offset": offset, "page_size": 25,
              "requested_at": datetime.now(UTC).isoformat(), "rows": [], "total": None,
              "limitation": "Provider discovery observations, not Alpaca tradability or consolidated/live quotes. Missing values are unavailable; pages are not a complete market inventory."}
    try:
        response = yf.screen(query, offset=offset, size=25, sortField=selected["sort"], sortAsc=selected["ascending"])
        if not isinstance(response, dict) or not isinstance(response.get("quotes"), list):
            raise ValueError("Provider returned no valid screening response")
        for quote in response["quotes"]:
            row = {key: quote.get(key) for key in ("symbol", "shortName", "longName", "currency", "exchange")}
            stamp = quote.get("regularMarketTime")
            try:
                row["regularMarketTime"] = datetime.fromtimestamp(stamp, UTC).timestamp() if type(stamp) in (int, float) and math.isfinite(stamp) and 0 <= stamp <= 253402300799 else None
            except (OverflowError, OSError, ValueError):
                row["regularMarketTime"] = None
            for key in ("regularMarketPrice", "regularMarketChangePercent", "regularMarketVolume", "marketCap", "averageDailyVolume3Month"):
                number = quote.get(key)
                row[key] = number if type(number) in (int, float) and math.isfinite(number) else None
            result["rows"].append(row)
        total = response.get("total")
        result.update(status="completed", total=total if type(total) is int and total >= 0 else None)
    except Exception as exc:
        # An unavailable provider is distinct from a successful empty page.
        result.update(status="failed", error=f"Yahoo screen unavailable ({type(exc).__name__}); retry explicitly.")
    result["captured_at"] = datetime.now(UTC).isoformat()
    return result


def scan_state(service):
    from .attention import INDICATORS, KINDS
    from .evaluation import scan_calculation_capabilities
    from .market_history import TIMEFRAMES
    from .workspace import DEFAULT as WORKSPACE
    record = service.store.database.read("discovery", DEFAULT)
    return {"revision": record["revision"], "data": {key: record["data"].get(key, DEFAULT[key]) for key in
        ("definitions", "definition_history", "runs", "schedule_slots")},
        "formula_definitions": service.store.database.read("workspace", WORKSPACE)["data"].get("chart_definition_history", []),
        "schema": {"query": metadata()["query_schema"], "program": scan_calculation_capabilities(),
        "atom_kinds": sorted(KINDS - {"policy_condition"}), "indicators": INDICATORS, "timeframes": TIMEFRAMES,
        "request_budget_basis": "Explicit provider dispatch operations; yfinance may make internal HTTP requests/retries",
        "time_budget_basis": "Stops further dispatch; an in-flight synchronous provider call may finish after the deadline",
        "schedule_clock": "Elapsed UTC minutes; America/New_York regular-session gate follows recorded calendar/DST; no restart catch-up",
        "collection_scope": "Authorized collection refreshes Yahoo candidates and IEX OHLCV only; other stock predicates use retained sources",
        "crossing_basis": "Two genuine comparable eligible observed runs; not arbitrary historical-pattern programming"}}


def scan_action(service, request):
    from .workspace import DEFAULT as WORKSPACE
    action, database = request["action"], service.store.database
    if action == "scan_detail":
        return {"run": database.read("discovery", DEFAULT)["data"].get("runs", {})[request["run_id"]]}
    if action == "scan_export":
        saved = database.read("discovery", DEFAULT)["data"]
        definitions = list(saved.get("definitions", {}).values())
        if request.get("id"):
            definitions = [row for row in [*saved.get("definition_history", []), *definitions]
                if row["id"] == request["id"] and row["revision"] == request.get("revision")]
            definitions = definitions[:1]
            if not definitions:
                raise ValueError("Choose an exact retained scan revision to export")
        return {"bundle": {"version": "scan-definitions-v1", "definitions": copy.deepcopy(definitions),
            "chart_definitions": database.read("workspace", WORKSPACE)["data"].get("chart_definition_history", [])}}
    if action == "scan_import":
        from .investor import digest
        from .workspace import import_chart_definitions
        bundle = request.get("bundle")
        if (not isinstance(bundle, dict) or set(bundle) != {"version", "definitions", "chart_definitions"}
                or bundle["version"] != "scan-definitions-v1" or not isinstance(bundle["definitions"], list)
                or not 1 <= len(bundle["definitions"]) <= 1000 or not isinstance(bundle["chart_definitions"], list)):
            raise ValueError("Import a versioned scan bundle with exact formula dependencies")
        if type(request.get("expected_revision")) is not int or type(request.get("workspace_revision")) is not int:
            raise ValueError("Reload scan and formula libraries before importing")
        def import_bundle(records):
            if bundle["chart_definitions"]:
                import_chart_definitions(records["workspace"], {"version": "chart-definitions-v1", "definitions": bundle["chart_definitions"]})
            saved = records["discovery"]
            for raw in bundle["definitions"]:
                definition = scan_definition(raw)
                scan_formula_bindings(records["workspace"], definition.get("program"))
                definition["schedule"]["enabled"], definition["alert"] = False, False
                definition["import_lineage"] = {"id": raw.get("id"), "revision": raw.get("revision"), "sha256": digest(raw)}
                members = definition["target"].get("symbols", [])
                if definition["target"]["mode"] == "follow":
                    listing = next((row for row in records["workspace"]["watchlists"] if row["id"] == definition["target"]["watchlist_id"]), None)
                    if listing is None:
                        raise ValueError("Imported follow scan requires its local watchlist; select a retained list before importing")
                    members = listing["symbols"]
                definition["memberships"] = {str(uuid4()): {"symbol": symbol, "status": "monitoring", "added_at": definition["updated_at"]}
                    for symbol in members}
                definition["next_due_at"] = (datetime.now(UTC) + timedelta(minutes=definition["schedule"]["cadence_minutes"])).isoformat()
                saved.setdefault("definitions", {})[definition["id"]] = definition
                saved.setdefault("definition_history", []).append(copy.deepcopy(definition))
        database.transact({"discovery": DEFAULT, "workspace": WORKSPACE}, import_bundle,
            expected={"discovery": request["expected_revision"], "workspace": request["workspace_revision"]})
        return {**metadata(), "scanner": scan_state(service), "workspace": service.workspace()}
    if action == "scan_run":
        queue_scan(service.data_jobs, request["id"], request["revision"], market_cutoff=request.get("market_cutoff"))
    elif action == "scan_cancel":
        identity = request["run_id"]
        def cancel(records):
            run = records["discovery"].get("runs", {})[identity]
            if run["status"] in {"queued", "running", "canceling"}:
                run.update(status="canceling", cancel_requested_at=datetime.now(UTC).isoformat())
        database.transact({"discovery": DEFAULT}, cancel)
        service.data_jobs.canceled.add(identity)
    elif action in {"scan_save", "scan_schedule"}:
        workspace = database.read("workspace", WORKSPACE)
        def save(records):
            saved = records["discovery"]
            for key in DEFAULT:
                saved.setdefault(key, copy.deepcopy(DEFAULT[key]))
            supplied = request.get("definition", {})
            old = saved["definitions"].get(request.get("id") or supplied.get("id"))
            if (request.get("id") or supplied.get("id")) and old is None:
                raise ValueError("Saved scan definition is unavailable")
            if old and request.get("revision", supplied.get("revision")) != old["revision"]:
                raise ValueError("Scan revision changed; reload it")
            if action == "scan_schedule":
                if old is None or type(request.get("enabled")) is not bool:
                    raise ValueError("Choose a saved scan and explicit schedule opt-in")
                supplied = copy.deepcopy(old)
                supplied["schedule"]["enabled"] = request["enabled"]
            definition = scan_definition(supplied, old)
            scan_formula_bindings(workspace["data"], definition.get("program"))
            if action == "scan_save":
                definition["schedule"]["enabled"] = False
            target = definition["target"]
            if target["mode"] in {"snapshot", "follow"}:
                listing = next((item for item in workspace["data"]["watchlists"] if item["id"] == target["watchlist_id"]), None)
                if listing is None:
                    raise ValueError("Saved scan watchlist is unavailable")
                if target["mode"] == "snapshot" and action == "scan_save":
                    target.update(symbols=list(listing["symbols"]), workspace_revision=workspace["revision"])
            members = target.get("symbols", []) if target["mode"] != "follow" else listing["symbols"]
            definition["memberships"] = copy.deepcopy(old["memberships"]) if old and action == "scan_schedule" else {
                str(uuid4()): {"symbol": symbol, "status": "monitoring", "added_at": definition["updated_at"]} for symbol in members}
            definition["next_due_at"] = (datetime.now(UTC) + timedelta(minutes=definition["schedule"]["cadence_minutes"])).isoformat()
            saved["definitions"][definition["id"]] = definition
            saved["definition_history"].append(copy.deepcopy(definition))
            for identity, run in saved["runs"].items():
                if run["definition"]["id"] == definition["id"] and run["status"] in {"queued", "running", "canceling"}:
                    run.update(status="canceling", cancel_requested_at=datetime.now(UTC).isoformat())
                    service.data_jobs.canceled.add(identity)
        database.transact({"discovery": DEFAULT, "workspace": WORKSPACE}, save,
            expected={"discovery": request.get("expected_revision"), "workspace": workspace["revision"]})
    else:
        raise ValueError("Unknown scan action")
    result = {**metadata(), "scanner": scan_state(service)}
    if action in {"scan_save", "scan_schedule"}:
        result["scanner"]["saved_definition"] = next((item for item in reversed(result["scanner"]["data"]["definition_history"])), None)
    return result


def scan_formula_bindings(workspace, program):
    from .workspace import chart_definition_dependencies
    bindings = {}
    for name, input in (program or {}).get("inputs", {}).items():
        if input["value"]["kind"] != "definition":
            continue
        ref = input["value"]["definition"]
        root = chart_definition_dependencies(workspace, [ref])[-1]
        row = next(row for row in workspace["chart_definition_history"] if row["definition"] == root)
        bindings[name] = {"definition": root, "dependencies": chart_definition_dependencies(workspace, row["dependencies"])}
    return bindings


def scan_source_pin(jobs, symbol, input):
    from .market_history import DEFAULT as HISTORY
    timeframe = "1Min" if input["session"] == "regular" else input["timeframe"]
    candidates = [row for row in jobs.database.read("market_history", HISTORY)["data"]["entries"].values()
        if row["symbol"] == symbol and (row["key"] == input["history_key"] if input["history_key"] else
            row.get("timeframe") == timeframe and all(row.get(key) == input["source_profile"][key]
                for key in ("feed", "adjustment")))]
    meta = max(candidates, key=lambda row: row["captured_at"], default=None)
    return {"key": meta["key"], "artifact": copy.deepcopy(meta["artifact"])} if meta else {"error": "No matching retained source for this named interval/profile"}


def queue_scan(jobs, identity, revision, *, scheduled=False, slot=None, market_cutoff=None):
    from .workspace import DEFAULT as WORKSPACE
    workspace = jobs.database.read("workspace", WORKSPACE)
    run_id = str(uuid4())
    def queue(records):
        saved = records["discovery"]
        definition = saved.get("definitions", {})[identity]
        if definition["revision"] != revision or scheduled and not definition["schedule"]["enabled"]:
            raise ValueError("Scan definition or schedule authority changed")
        if any(run["definition"]["id"] == identity and run["status"] in {"queued", "running", "canceling"} for run in saved.get("runs", {}).values()):
            raise ValueError("This scan already has an unfinished run")
        definition = copy.deepcopy(definition)
        target = definition["target"]
        members = target.get("symbols", [])
        if target["mode"] == "follow":
            listing = next((item for item in workspace["data"]["watchlists"] if item["id"] == target["watchlist_id"]), None)
            if listing is None:
                raise ValueError("Follow watchlist is unavailable")
            members = listing["symbols"]
        stamp = datetime.now(UTC).isoformat()
        if target["mode"] != "provider":
            membership = definition.setdefault("memberships", {})
            for member in membership.values():
                if member["status"] == "monitoring" and member["symbol"] not in members:
                    member.update(status="no_longer_monitored", removed_at=stamp)
            for symbol in members:
                if not any(row["symbol"] == symbol and row["status"] == "monitoring" for row in membership.values()):
                    membership[str(uuid4())] = {"symbol": symbol, "status": "monitoring", "added_at": stamp}
            saved["definitions"][identity]["memberships"] = copy.deepcopy(membership)
        cutoff = datetime.fromisoformat(market_cutoff) if market_cutoff else datetime.fromisoformat(stamp)
        if cutoff.utcoffset() is None or cutoff > datetime.fromisoformat(stamp):
            raise ValueError("Market cutoff must have a timezone and cannot follow the request time")
        slot_id = identity + ":" + str(revision) + ":" + slot if slot else None
        if slot_id and any(run.get("slot_id") == slot_id for run in saved.get("runs", {}).values()):
            raise ValueError("This scheduled slot was already claimed")
        saved.setdefault("runs", {})[run_id] = {"id": run_id, "definition": definition, "status": "queued",
            "requested_at": stamp, "cutoff": cutoff.isoformat(), "retrospective": bool(market_cutoff), "scheduled": scheduled, "slot_id": slot_id,
            "workspace_revision": workspace["revision"],
            "universe": {"mode": target["mode"], "members": sorted(set(members)), "complete": target["mode"] != "provider"},
            "results": {}, "counts": {"matched": 0, "clear": 0, "unavailable": 0}, "query_receipts": [],
            "coverage": {"complete": False, "reasons": ["Run has not completed"]},
            "limitation": "Bar cutoff and later provider capture times differ; pages are not an atomic historical market snapshot"}
        if definition.get("program"):
            from .investor import digest
            saved["runs"][run_id].update(program_sha256=digest(definition["program"]),
                formula_definitions=scan_formula_bindings(workspace["data"], definition["program"]),
                source_pins={symbol: {name: scan_source_pin(jobs, symbol, input) for name, input in definition["program"]["inputs"].items()}
                    for symbol in members} if definition["collection"]["mode"] == "retained" else {})
        if slot_id:
            saved.setdefault("schedule_slots", {})[slot_id] = {"id": slot_id, "definition_id": identity,
                "revision": revision, "due_at": slot, "state": "claimed", "run_id": run_id, "claimed_at": stamp}
    jobs.database.transact({"discovery": DEFAULT, "workspace": WORKSPACE}, queue, expected={"workspace": workspace["revision"]})
    try:
        future = jobs.executor.submit(execute_scan, jobs, run_id)
    except RuntimeError:
        def interrupted(records):
            run = records["discovery"]["runs"][run_id]
            run.update(status="interrupted", error="Data executor unavailable; no scan dispatch occurred", unprocessed=run["universe"]["members"])
        jobs.database.transact({"discovery": DEFAULT}, interrupted)
        raise
    jobs.futures.add(future)
    future.add_done_callback(jobs.futures.discard)
    return run_id


def recover_scans(jobs):
    def recover(records):
        saved = records["discovery"]
        for run in saved.get("runs", {}).values():
            if run["status"] in {"queued", "running", "canceling"}:
                run.update(status="interrupted", error="Service restarted; no implicit scan replay or completion")
                run["unprocessed"] = scan_unprocessed(run)
                run["counts"] = {state: sum(row["state"] == state for row in run["results"].values()) for state in ("matched", "clear", "unavailable")}
        for definition in saved.get("definitions", {}).values():
            definition.setdefault("schedule_gaps", []).append({"from": definition.get("next_due_at"),
                "through": datetime.now(UTC).isoformat(), "reason": "Service restart; missed slots are not replayed"})
            definition["next_due_at"] = (datetime.now(UTC) + timedelta(minutes=definition["schedule"]["cadence_minutes"])).isoformat()
        for slot in saved.get("schedule_slots", {}).values():
            if slot.get("state") == "due":
                slot.update(state="skipped", reason="Service stopped before dispatch; this slot is not replayed")
    jobs.database.transact({"discovery": DEFAULT}, recover)


def invalidate_scan_authority(saved):
    """Restore creates disabled revisions without changing any frozen historical run."""
    stamp = datetime.now(UTC).isoformat()
    for identity, old in list(saved.get("definitions", {}).items()):
        if old["schedule"]["enabled"]:
            definition = copy.deepcopy(old)
            definition.update(revision=old["revision"] + 1, updated_at=stamp,
                next_due_at=(datetime.now(UTC) + timedelta(minutes=old["schedule"]["cadence_minutes"])).isoformat())
            definition["schedule"]["enabled"] = False
            saved["definitions"][identity] = definition
            saved.setdefault("definition_history", []).append(copy.deepcopy(definition))
    for run in saved.get("runs", {}).values():
        if run["status"] in {"queued", "running", "canceling"}:
            run.update(status="interrupted", error="Restored unfinished scan; explicit new run required and no missed slot replayed")
            run["unprocessed"] = scan_unprocessed(run)
            run["counts"] = {state: sum(row["state"] == state for row in run["results"].values()) for state in ("matched", "clear", "unavailable")}
    for slot in saved.get("schedule_slots", {}).values():
        if slot["state"] in {"due", "claimed"}:
            slot.update(state="skipped", reason="Restored schedule authority is disabled; no slot is replayed")


def due_scans(jobs):
    definitions = jobs.database.read("discovery", DEFAULT)["data"].get("definitions", {})
    for definition in definitions.values():
        schedule = definition["schedule"]
        if not schedule["enabled"] or datetime.fromisoformat(definition["next_due_at"]) > datetime.now(UTC):
            continue
        advanced = []
        def advance(records, definition=definition, schedule=schedule, advanced=advanced):
            current = records["discovery"]["definitions"][definition["id"]]
            if current["revision"] == definition["revision"] and current["schedule"]["enabled"] and current["next_due_at"] == definition["next_due_at"]:
                current["next_due_at"] = (datetime.now(UTC) + timedelta(minutes=schedule["cadence_minutes"])).isoformat()
                advanced.append(True)
                key = definition["id"] + ":" + str(definition["revision"]) + ":" + definition["next_due_at"]
                records["discovery"].setdefault("schedule_slots", {}).setdefault(key, {"id": key, "state": "due",
                    "definition_id": definition["id"], "revision": definition["revision"], "due_at": definition["next_due_at"]})
        def skip(reason, definition=definition):
            key = definition["id"] + ":" + str(definition["revision"]) + ":" + definition["next_due_at"]
            def record_slot(records):
                slots = records["discovery"].setdefault("schedule_slots", {})
                if slots.get(key, {}).get("state") != "claimed":
                    slots[key] = {"id": key, "definition_id": definition["id"], "revision": definition["revision"],
                                  "due_at": definition["next_due_at"], "state": "skipped", "reason": reason}
            jobs.database.transact({"discovery": DEFAULT}, record_slot)
        jobs.database.transact({"discovery": DEFAULT}, advance)
        if not advanced:
            continue
        if schedule["session"] == "regular":
            from .approval_review import read_artifact
            from .history_coverage import latest_calendar
            record = jobs.database.read("market_history", {"entries": {}, "coverage": {}, "jobs": {}})["data"]
            meta = latest_calendar(record, lambda ref: read_artifact(jobs.service.store.directory, ref))
            reference = (meta or {}).get("required_coverage", {}).get("provenance", {}).get("calendar_reference")
            calendar = read_artifact(jobs.service.store.directory, reference) if reference else None
            current = datetime.now(ZoneInfo(schedule["timezone"]))
            session = next((row for row in calendar or [] if row["date"] == current.date().isoformat()), None)
            if not session or not session["open"] <= current.strftime("%H:%M") < session["close"]:
                skip("Outside the recorded regular session or retained calendar unavailable")
                continue
        try:
            queue_scan(jobs, definition["id"], definition["revision"], scheduled=True, slot=definition["next_due_at"])
        except ValueError:
            skip("Definition authority changed or an unfinished run occupies this slot; no overlap or backfill")


def scan_dispatch(jobs, limit, *, charge=True, check_deadline=True):
    database = limit.get("database") or jobs.database
    run = database.read("discovery", DEFAULT)["data"]["runs"][limit["run_id"]]
    current = database.read("discovery", DEFAULT)["data"]["definitions"][run["definition"]["id"]]
    if (limit["run_id"] in jobs.canceled or run["status"] == "canceling" or current["revision"] != run["definition"]["revision"]
            or run["scheduled"] and not current["schedule"]["enabled"]):
        raise InterruptedError("Scan authority canceled or changed; no further provider dispatch")
    if check_deadline and time.monotonic() >= limit["deadline"]:
        raise InterruptedError("Scan time budget exhausted before further work")
    if not charge:
        return
    if limit["operations"] >= limit["max_operations"]:
        raise InterruptedError("Scan time/provider-operation budget exhausted before dispatch")
    limit["operations"] += 1
    database.transact({"discovery": DEFAULT}, lambda records: records["discovery"]["runs"][limit["run_id"]].update(
        provider_operations=limit["operations"]))


def execute_program_symbol(jobs, run, definition, symbol, cutoff, limit, update, store):
    from .approval_review import read_artifact
    from .evaluation import execute_scan_calculation, prepare_scan_calculation
    from .investor import digest
    from .market_history import DEFAULT as HISTORY, chart_calendar_coverage
    inputs, selected, selected_pins = {}, {}, {}
    for name, input in definition["program"]["inputs"].items():
        scan_dispatch(jobs, limit, charge=False)
        timeframe = "1Min" if input["session"] == "regular" else input["timeframe"]
        selection = digest({"timeframe": timeframe, "profile": input["source_profile"], "key": input["history_key"]})
        if selection in selected:
            inputs[name] = selected[selection]
            update(lambda item, name=name, selection=selection: item.setdefault("source_pins", {}).setdefault(symbol, {}).update({name: copy.deepcopy(selected_pins[selection])}))
            continue
        if definition["collection"]["mode"] == "collect":
            child = str(uuid4())
            request = {"start": (cutoff - timedelta(days=definition["collection"]["lookback_days"])).date().isoformat(),
                "end": cutoff.astimezone(ZoneInfo("America/New_York")).date().isoformat(),
                "asof": cutoff.astimezone(ZoneInfo("America/New_York")).date().isoformat(), "timeframe": timeframe,
                "adjustment": input["source_profile"]["adjustment"], "feed": "iex", "page_limit": definition["collection"]["max_pages"]}
            jobs.update(lambda saved, child=child, request=request: saved["jobs"].update({child: {"id": child, "scan_id": run["id"],
                "status": "running", "request": request, "symbols": {symbol: {"status": "running"}}}}))
            jobs.fetch(child, symbol, request)
            child_state = limit["database"].read("market_history", HISTORY)["data"]["jobs"][child]["symbols"][symbol]
            jobs.update(lambda saved, child=child, child_state=child_state: saved["jobs"][child].update(
                status="completed" if child_state["status"] == "completed" else "failed"))
            pin = scan_source_pin(jobs, symbol, {**input, "history_key": child_state.get("key")}) if child_state.get("key") else {"error": "Fresh collection did not retain a source"}
            if child_state["status"] != "completed":
                pin["error"] = child_state.get("error") or "Fresh interval collection failed; no older source substituted"
        else:
            pin = run.get("source_pins", {}).get(symbol, {}).get(name) or scan_source_pin(jobs, symbol, input)
        update(lambda item, name=name, pin=pin: item.setdefault("source_pins", {}).setdefault(symbol, {}).update({name: copy.deepcopy(pin)}))
        try:
            if pin.get("error"):
                raise ValueError(pin["error"])
            history = jobs.detail(symbol, pin["key"], timeframe=timeframe, artifact=pin["artifact"])
            if (not isinstance(history, dict) or history.get("symbol") != symbol or history.get("key") != pin["key"]
                    or history.get("timeframe") != timeframe or history.get("provider") != input["source_profile"]["provider"]
                    or any(history.get(key) != input["source_profile"][key] for key in ("feed", "adjustment", "currency"))):
                raise ValueError("Frozen retained source identity, interval or source profile differs")
            coverage = chart_calendar_coverage(history)
            reference = coverage["reference"] if coverage else None
            history.update(artifact=copy.deepcopy(pin["artifact"]), calendar_coverage=coverage,
                calendar=read_artifact(store.directory, reference) if reference else None, calendar_artifact=reference,
                bar_pages={row["artifact"]["sha256"]: read_artifact(store.directory, row["artifact"])
                    for row in history.get("receipts", []) if "page_token" in row})
            inputs[name] = history
        except (ValueError, KeyError, TypeError, OSError) as exc:
            inputs[name] = {"error": str(exc)}
        selected[selection] = inputs[name]
        selected_pins[selection] = pin
    scan_dispatch(jobs, limit, charge=False)
    spec = prepare_scan_calculation(definition["program"], inputs, cutoff=cutoff.isoformat(),
        definitions=run.get("formula_definitions", {}), historical=run.get("retrospective", False))
    calculation_id = str(uuid4())
    spec_ref = store._write_json_artifact(calculation_id, "scan-program-spec", spec)
    update(lambda item: item.setdefault("received_inputs", {}).update({symbol: {"spec_artifact": spec_ref, "spec_sha256": spec["spec_sha256"]}}))
    result = execute_scan_calculation(spec, jobs.service.runtime.python, cancelled=lambda: run["id"] in jobs.canceled,
        timeout=max(0, limit["deadline"] - time.monotonic()))
    if not result.get("result_sha256"):
        result["result_sha256"] = digest(result)
    result_ref = store._write_json_artifact(calculation_id, "scan-program-result", result)
    calculation = {"spec_artifact": spec_ref, "result_artifact": result_ref, "spec_sha256": spec["spec_sha256"],
        "result_sha256": result.get("result_sha256"), "result": result}
    evaluation = {key: copy.deepcopy(result.get(key)) for key in ("state", "at", "input_identity", "facts", "reason")}
    evaluation["state"] = result.get("state", {"true": "triggered", "false": "clear"}.get(result.get("evaluation"), "unavailable"))
    evaluation["at"] = result.get("calculated_at") or datetime.now(UTC).isoformat()
    evaluation["input_identity"], evaluation["facts"] = spec["spec_sha256"], result.get("facts") or result.get("latest") or {}
    evidence = {"version": "scan-program-evidence-v1", "run_id": run["id"], "symbol": symbol,
        "definition_id": definition["id"], "definition_revision": definition["revision"], "program_sha256": run["program_sha256"],
        "evaluation": evaluation, "calculation": calculation}
    member = next(key for key, value in definition["memberships"].items() if value["symbol"] == symbol and value["status"] == "monitoring")
    record = {"symbol": symbol, "state": {"triggered": "matched"}.get(evaluation["state"], evaluation["state"]),
        "evaluation": evaluation, "membership_id": member, "calculation": calculation,
        "processing_status": result.get("status"),
        "coverage_complete": result.get("coverage", {}).get("complete") is True}
    def retain(records):
        from .attention import AttentionMonitor
        observed = records["attention_observations"]
        live = records["discovery"]["definitions"][definition["id"]]
        monitored = live["revision"] == definition["revision"] and live.get("memberships", {}).get(member, {}).get("status") == "monitoring"
        key = definition["id"] + ":" + member
        AttentionMonitor.evaluate_member({**definition, "kind": "scan_program", "scope": "history",
            "condition_identity": digest(definition["program"])}, symbol, member, key, observed["rule_states"].get(key, {}), observed,
            {}, emit_occurrences=definition["alert"] and monitored and run["id"] not in jobs.canceled
                and records["discovery"]["runs"][run["id"]]["status"] == "running", precomputed=(evaluation, evidence))
        if not monitored:
            observed["rule_states"][key]["monitoring"] = "no_longer_monitored"
        records["discovery"]["runs"][run["id"]]["results"][symbol] = record
    from .attention import OBSERVATIONS
    limit["database"].transact({"discovery": DEFAULT, "attention_observations": OBSERVATIONS}, retain)
    if result.get("status") in {"interrupted", "cancelled", "canceled"}:
        raise InterruptedError("Program calculation stopped before completion; retained partial evidence is inspectable")
    if result.get("status") == "failed":
        raise ValueError("Program calculation failed; retained specification and result remain inspectable")
    return record


def execute_scan(jobs, identity):
    from .attention import OBSERVATIONS, AttentionMonitor, indicator_key, sync_memberships
    from .investor import digest
    from .market_history import DEFAULT as HISTORY
    database, store = jobs.database, jobs.service.store
    def update(change):
        database.transact({"discovery": DEFAULT}, lambda records: change(records["discovery"]["runs"][identity]))
    run = database.read("discovery", DEFAULT)["data"]["runs"][identity]
    definition, cutoff = run["definition"], datetime.fromisoformat(run["cutoff"])
    policy = definition["collection"]
    limit = {"run_id": identity, "deadline": time.monotonic() + policy["max_seconds"], "operations": 0,
             "max_operations": policy["max_requests"], "database": database}
    jobs.scan_limits.value = limit
    intervals = sorted({atom["parameters"]["timeframe"] for atom in definition["atoms"] if atom["kind"] == "indicator"}
                       | ({"1Day"} if any(atom["scope"] == "history" for atom in definition["atoms"]) else set()))
    results, reasons, members = {}, [], list(run["universe"]["members"])
    complete = True
    try:
        scan_dispatch(jobs, limit, charge=False)
        update(lambda item: item.update(status="running", started_at=datetime.now(UTC).isoformat()))
        if definition["query"] is not None:
            found, offset, total, invalid_candidates = [], 0, None, False
            complete = False
            for _ in range(policy["max_pages"]):
                jobs.budget.wait(lambda: identity in jobs.canceled or time.monotonic() >= limit["deadline"])
                scan_dispatch(jobs, limit)
                response = yf.screen(scan_query(definition["query"]), offset=offset, size=250, sortField="ticker", sortAsc=True)
                captured = datetime.now(UTC).isoformat()
                reference = jobs.service.store._write_source_result(identity, str(uuid4()), response, prefix="scan-query")
                update(lambda item, reference=reference, captured=captured, offset=offset: item["query_receipts"].append(
                    {"artifact": reference, "captured_at": captured, "offset": offset, "library_version": yf.__version__}))
                if not isinstance(response, dict) or not isinstance(response.get("quotes"), list):
                    raise ValueError("Provider query response is unavailable")
                page, total = response["quotes"], response.get("total")
                if any(not isinstance(row, dict) or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", str(row.get("symbol", ""))) for row in page):
                    invalid_candidates = True
                    reasons.append("Provider returned candidate identities outside the supported stock-symbol contract")
                found.extend(row["symbol"] for row in page if isinstance(row, dict) and re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", str(row.get("symbol", ""))))
                offset += len(page)
                if type(total) is int and offset >= total:
                    complete = not invalid_candidates
                    break
                if not page or len(set(found)) >= policy["max_symbols"]:
                    break
            members = sorted(set(found) & set(members)) if definition["target"]["mode"] != "provider" else sorted(set(found))
            if not complete:
                reasons.append("Provider candidate enumeration capped, failed or has unknown total; pages are not atomic")
        if len(members) > policy["max_symbols"]:
            complete = False
            reasons.append("Explicit symbol budget capped the evaluated universe")
            members = members[:policy["max_symbols"]]
        update(lambda item: item["universe"].update(members=members, complete=complete, resolved_at=datetime.now(UTC).isoformat()))
        # Reuse membership lifecycle and alert state; the ordinary monitor never collects for scans.
        def memberships(records):
            current = records["discovery"]["definitions"][definition["id"]]
            if current["revision"] != definition["revision"]:
                raise InterruptedError("Scan revision changed")
            if definition["target"]["mode"] == "provider":
                known = [member["symbol"] for member in current.get("memberships", {}).values() if member["status"] == "monitoring"]
                observed_members = members if complete else sorted(set(members + known))
                proxy = {"rules": {definition["id"]: {**definition, "target": {"mode": "follow", "watchlist_id": definition["id"]},
                    "memberships": current.setdefault("memberships", {})}}}
                sync_memberships(proxy, {"watchlists": [{"id": definition["id"], "symbols": observed_members}]}, records["attention_observations"])
                definition["memberships"] = copy.deepcopy(current["memberships"])
            records["discovery"]["runs"][identity]["memberships"] = copy.deepcopy(definition["memberships"])
        jobs.database.transact({"discovery": DEFAULT, "attention_observations": OBSERVATIONS}, memberships)
        context = {} if definition.get("program") else jobs.service.attention_context()
        context["indicators"] = {}
        for symbol in members:
            scan_dispatch(jobs, limit, charge=False)
            if definition.get("program"):
                results[symbol] = execute_program_symbol(jobs, run, definition, symbol, cutoff, limit, update, store)
                if not results[symbol]["coverage_complete"]:
                    reasons.append(symbol + ": program input/axis coverage is partial or unavailable")
                continue
            interval_results, local = {}, copy.deepcopy(context)
            quote = local["sources"].get("quote", {}).get(symbol)
            if quote and (not quote.get("source_event_ns") or int(quote["source_event_ns"]) > int(cutoff.timestamp() * 1e9)):
                quote.update(status="unavailable", reason="Retained quote timestamp is absent or after the frozen scan cutoff")
            for interval in intervals:
                scan_dispatch(jobs, limit, charge=False)
                if policy["mode"] == "collect":
                    if time.monotonic() >= limit["deadline"] or limit["operations"] >= limit["max_operations"]:
                        raise InterruptedError("Collection budget exhausted; remaining symbol/interval work was not dispatched")
                    child = str(uuid4())
                    request = {"start": (cutoff - timedelta(days=policy["lookback_days"])).date().isoformat(),
                        "end": cutoff.astimezone(ZoneInfo("America/New_York")).date().isoformat(), "asof": cutoff.astimezone(ZoneInfo("America/New_York")).date().isoformat(),
                        "timeframe": interval, "adjustment": policy["adjustment"], "feed": "iex", "page_limit": policy["max_pages"]}
                    jobs.update(lambda saved, child=child, request=request, symbol=symbol: saved["jobs"].update({child: {"id": child, "scan_id": identity,
                        "status": "running", "request": request, "symbols": {symbol: {"status": "running"}}}}))
                    jobs.fetch(child, symbol, request)
                    child_state = jobs.database.read("market_history", HISTORY)["data"]["jobs"][child]["symbols"][symbol]
                    key = child_state.get("key")
                    jobs.update(lambda saved, child=child, child_state=child_state: saved["jobs"][child].update(status="completed" if child_state["status"] == "completed" else "failed"))
                else:
                    key = next((atom["parameters"].get("history_key") for atom in definition["atoms"]
                                if atom["kind"] == "indicator" and atom["parameters"]["timeframe"] == interval), None)
                detail = jobs.detail(symbol, key, timeframe=interval)
                source = detail.get("source") or {}
                compatible = detail.get("feed") == policy["feed"] and detail.get("adjustment") == policy["adjustment"] and detail.get("currency") == "USD"
                collection_failed = policy["mode"] == "collect" and (child_state["status"] != "completed" or detail.get("retained_older_data"))
                if not compatible or collection_failed:
                    detail["indicators"] = []
                    detail["error"] = "Selected feed/adjustment/currency differs or the fresh collection failed; older data is not substituted"
                interval_results[interval] = {"status": "available" if detail.get("bars") else "unavailable", "key": detail.get("key"),
                    "artifact": {field: source.get(field) for field in ("path", "sha256")} if source.get("sha256") else None, "captured_at": detail.get("captured_at"),
                    "derivation_identity": detail.get("derivation_identity"), "coverage": detail.get("required_coverage"), "error": detail.get("error")}
                if not compatible or collection_failed:
                    interval_results[interval]["status"] = "unavailable"
                for series in detail.get("indicators", []):
                    series["points"] = [point for point in series["points"] if point["t"] <= (cutoff.date().isoformat() if interval == "1Day" else cutoff.timestamp())
                        and point.get("closed_at") and datetime.fromisoformat(point["closed_at"]) <= cutoff]
                    eligible = [point for point in series["points"] if point.get("alert_eligible")]
                    if eligible:
                        series["points"] = [*series["points"][:series["points"].index(eligible[-1])], eligible[-1]]
                needed = {atom["parameters"]["indicator"] for atom in definition["atoms"]
                          if atom["kind"] == "indicator" and atom["parameters"]["timeframe"] == interval}
                available = {series["name"] for series in detail.get("indicators", []) if series["points"] and series["points"][-1].get("alert_eligible")}
                interval_results[interval]["complete"] = compatible and not collection_failed and detail.get("pagination_complete") is True and needed <= available
                if any(atom["scope"] == "history" for atom in definition["atoms"]):
                    interval_results[interval]["complete"] &= detail.get("required_coverage", {}).get("sufficient") is True
                for atom in definition["atoms"]:
                    if atom["kind"] == "indicator" and atom["parameters"]["timeframe"] == interval:
                        local["indicators"][indicator_key(symbol, atom["parameters"])] = {"series": detail.get("indicators", []), "source": {
                            "observed_at": detail.get("captured_at"), "artifact": interval_results[interval]["artifact"],
                            "key": detail.get("key"), "timeframe": interval, "feed": detail.get("feed"), "currency": detail.get("currency")}}
                if interval == "1Day":
                    local["sources"].setdefault("history", {})[symbol] = {"status": "available" if interval_results[interval]["complete"] else "unavailable",
                        "reason": detail.get("error") or "; ".join(detail.get("required_coverage", {}).get("reasons", [])),
                        "observed_at": detail.get("captured_at"), "artifact": interval_results[interval]["artifact"], "input_identity": detail.get("key")}
                evidence = copy.deepcopy(interval_results[interval])
                update(lambda item, symbol=symbol, interval=interval, evidence=evidence:
                    item.setdefault("received_inputs", {}).setdefault(symbol, {}).update({interval: evidence}))
            scan_dispatch(jobs, limit, charge=False)
            atom = definition["atoms"][0]
            rule = {**definition, **atom, "active": True, "scope": atom["scope"], "symbol": symbol,
                "condition_identity": digest({**{key: definition[key] for key in ("query", "target", "atoms", "operator")},
                    "source_policy": {key: policy[key] for key in ("feed", "adjustment")}})}
            membership = next(key for key, member in definition["memberships"].items() if member["symbol"] == symbol and member["status"] == "monitoring")
            state_key = definition["id"] + ":" + membership
            def evaluate(records, rule=rule, symbol=symbol, membership=membership, state_key=state_key, local=local,
                         interval_results=interval_results):
                observed = records["attention_observations"]
                live = records["discovery"]["definitions"][definition["id"]]
                live_member = live.get("memberships", {}).get(membership, {})
                still_monitored = live["revision"] == definition["revision"] and live_member.get("status") == "monitoring"
                AttentionMonitor.evaluate_member(rule, symbol, membership, state_key, observed["rule_states"].get(state_key, {}), observed, local,
                                                 emit_occurrences=definition["alert"] and still_monitored)
                if not still_monitored:
                    observed["rule_states"][state_key]["monitoring"] = "no_longer_monitored"
                evaluation = copy.deepcopy(observed["rule_states"][state_key]["evaluation"])
                results[symbol] = {"symbol": symbol, "state": {"triggered": "matched"}.get(evaluation["state"], evaluation["state"]),
                    "evaluation": evaluation, "intervals": interval_results, "membership_id": membership,
                    "coverage_complete": all(item.get("complete") is True for item in interval_results.values())
                        and all(atom.get("state") != "unavailable" for atom in evaluation.get("atoms", [evaluation]))}
                records["discovery"]["runs"][identity]["results"][symbol] = copy.deepcopy(results[symbol])
            jobs.database.transact({"discovery": DEFAULT, "attention_observations": OBSERVATIONS}, evaluate)
            if not results[symbol]["coverage_complete"]:
                reasons.append(symbol + ": partial source/interval coverage even if the combined predicate is conclusive")
        scan_dispatch(jobs, limit, charge=False, check_deadline=False)
        update(lambda item: item.update(status="completed" if complete and not reasons else "completed_with_gaps"))
    except InterruptedError as exc:
        reasons.append(str(exc))
        update(lambda item: item.update(status="canceled" if identity in jobs.canceled else "interrupted"))
    except Exception as exc:
        reasons.append("Scan source/evaluation failed (" + type(exc).__name__ + "); retained receipts remain inspectable")
        update(lambda item: item.update(status="failed"))
    finally:
        jobs.scan_limits.value = None
        counts = {state: sum(item["state"] == state for item in results.values()) for state in ("matched", "clear", "unavailable")}
        if counts["unavailable"]:
            reasons.append("Some evaluated predicates have unavailable inputs")
        def finish(item):
            actual = item["results"]
            coverage_complete = complete and not reasons and len(actual) == len(members)
            actual_counts = {state: sum(row["state"] == state for row in actual.values()) for state in ("matched", "clear", "unavailable")}
            item.update(completed_at=datetime.now(UTC).isoformat(), counts=actual_counts, provider_operations=limit["operations"],
                unprocessed=scan_unprocessed(item),
                coverage={"complete": coverage_complete, "reasons": reasons})
            if item["status"] == "completed" and not coverage_complete:
                item["status"] = "completed_with_gaps"
        update(finish)
