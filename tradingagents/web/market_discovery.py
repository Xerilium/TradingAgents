"""Current Yahoo US equity discovery through the installed yfinance screener."""

import hashlib
import json
import math
from datetime import UTC, datetime
from uuid import UUID, uuid4

import yfinance as yf

FIELDS = {"min_price": ("GTE", "intradayprice"), "max_price": ("LTE", "intradayprice"),
          "min_market_cap": ("GTE", "intradaymarketcap"), "min_volume": ("GTE", "avgdailyvol3m")}
SORTS = ("ticker", "percentchange", "dayvolume", "intradaymarketcap")
DEFAULT = {"observations": {}}


def seal(result):
    result = {**result, "id": str(uuid4())}
    result["sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return result


def validate(saved):
    if not isinstance(saved, dict) or not isinstance(saved.get("observations"), dict):
        raise ValueError("Invalid saved discovery observations")
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


def metadata():
    query = yf.EquityQuery("EQ", ["region", "us"])
    return {"sectors": sorted(query.valid_values["sector"]), "sorts": SORTS,
            "provider": "Yahoo Finance via yfinance", "scope": "Current US equities", "page_size": 25}


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
