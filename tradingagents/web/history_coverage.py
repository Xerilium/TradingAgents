"""Required baseline coverage is independent of a selected chart range."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from .investor import decimal, digest

REQUIRED_SESSIONS = 252


def assess(bars, calendar, instrument, *, pagination_complete, calendar_reference, instrument_reference, captured_at, listing=None):
    reasons, completed = [], []
    capture = datetime.fromisoformat(captured_at)
    for row in calendar:
        try:
            close = datetime.fromisoformat(row["date"] + "T" + row["close"])
            if close.tzinfo is None:
                close = close.replace(tzinfo=ZoneInfo("America/New_York"))
            if close <= capture:
                completed.append(row["date"])
        except (ValueError, KeyError, TypeError):
            reasons.append("Calendar session/close is missing or unsupported")
    completed = sorted(set(completed))
    required = completed[-REQUIRED_SESSIONS:]
    provenance = {"provider": "Alpaca Trading API calendar", "timezone": "America/New_York",
        "session": "US equity regular session", "calendar_reference": calendar_reference,
        "instrument_reference": instrument_reference, "exchange": instrument.get("exchange"),
        "asset_id": instrument.get("id"), "symbol": instrument.get("symbol"), "calendar_sha256": digest(calendar)}
    if not instrument.get("id") or instrument.get("class", instrument.get("asset_class")) != "us_equity" or not instrument.get("exchange"):
        reasons.append("Instrument identity/class/exchange provenance is unavailable")
    exchange = instrument.get("exchange")
    if exchange not in {"NYSE", "NASDAQ", "AMEX", "ARCA", "BATS", "NYSEARCA", "NYSEAMERICAN"}:
        reasons.append("Observed exchange has no declared compatible regular-session calendar basis")
    exception = False
    if listing:
        start = listing.get("first_trading_session")
        if (listing.get("authoritative") is True and listing.get("asset_id") == instrument.get("id")
                and listing.get("symbol") == instrument.get("symbol") and listing.get("exchange") == exchange
                and listing.get("session_basis") == "regular_way_current_symbol"
                and listing.get("source_url") and listing.get("source_reference") and start in completed
                and len([day for day in completed if day >= start]) < REQUIRED_SESSIONS):
            required = [day for day in completed if day >= start]
            exception = True
            provenance["listing"] = listing
            provenance["pre_regular_way_dates"] = sorted({bar["t"] for bar in bars if bar.get("t") and bar["t"] < start})
            provenance["pre_regular_way_basis"] = "Mapped observations before regular-way listing are retained as context, outside the required baseline; when-issued status is limited to the sourced listing fact."
        else:
            reasons.append("Shorter-listing exception is not established by matching authoritative listing/session facts")
    if len(required) < REQUIRED_SESSIONS and not exception:
        reasons.append("Calendar does not establish 252 completed sessions; shorter listing start remains unknown")
    by_date = {}
    for bar in bars:
        day = bar.get("t")
        values = {key: decimal(bar.get("raw", {}).get(key, bar.get(key))) for key in ("o", "h", "l", "c", "v")}
        valid = all(value is not None for value in values.values())
        valid = valid and all(values[k] > 0 for k in ("o", "h", "l", "c")) and values["v"] >= 0
        valid = valid and values["h"] >= max(values["o"], values["l"], values["c"]) and values["l"] <= min(values["o"], values["h"], values["c"])
        if day in by_date:
            valid = False
        by_date[day] = valid
    missing = [day for day in required if by_date.get(day) is not True]
    if not pagination_complete:
        reasons.append("Provider pagination did not complete")
    if missing:
        reasons.append("Required completed sessions have missing/invalid OHLCV")
    if not by_date:
        reasons.append("Empty history is not baseline evidence")
    if len(required) >= REQUIRED_SESSIONS and missing and not listing:
        reasons.append("No authoritative first-trading-session fact establishes a shorter-listing exception")
    return {"method": "252-completed-us-equity-sessions-v1", "required_sessions": REQUIRED_SESSIONS,
        "sufficient": bool(required) and not reasons, "required_dates": required, "observed_required_sessions": len(required) - len(missing),
        "missing_dates": missing, "latest_completed_session": completed[-1] if completed else None,
        "shorter_listing_exception": exception, "listing_start_known": bool(exception), "reasons": reasons,
        "as_of": captured_at, "provenance": provenance, "pagination_complete": bool(pagination_complete)}


def recorded_timeframe(meta, artifact=None):
    if meta.get("timeframe"):
        return meta["timeframe"]
    retained = artifact(meta.get("last_usable_artifact") or meta.get("artifact", {})) if artifact else None
    return retained.get("timeframe") if isinstance(retained, dict) else None


def latest_calendar(record, artifact=None):
    candidates = [item for item in record.get("entries", {}).values() if recorded_timeframe(item, artifact) == "1Day" and item.get("calendar_through")
                  and item.get("required_coverage", {}).get("provenance", {}).get("calendar_reference")]
    return max(candidates, key=lambda item: item.get("captured_at", ""), default=None)


def current(meta, data, artifact, now=None, calendar_meta=None):
    """Readiness now; captured coverage and immutable bar/source artifacts stay unchanged."""
    now = now or datetime.now(UTC)
    coverage = (data or meta).get("required_coverage", {})
    result = {**coverage, "captured_as_of": coverage.get("as_of"), "as_of": now.isoformat(),
              "captured_sufficient": coverage.get("sufficient"), "reasons": list(coverage.get("reasons", []))}
    try:
        source = data or meta
        if recorded_timeframe(source, artifact) != "1Day":
            raise ValueError("A recorded daily interval is required")
        if calendar_meta:
            provenance = calendar_meta.get("required_coverage", {}).get("provenance", {})
            if all(provenance.get(key) == coverage.get("provenance", {}).get(key) and provenance.get(key)
                   for key in ("provider", "timezone", "session")):
                source = calendar_meta
        reference = source["required_coverage"]["provenance"]["calendar_reference"]
        calendar = artifact(reference)
        through = source.get("calendar_through") or meta.get("calendar_through")
        if not through:
            through = datetime.fromisoformat(source["captured_at"]).astimezone(ZoneInfo("America/New_York")).date().isoformat()
        if not isinstance(calendar, list) or through < now.astimezone(ZoneInfo("America/New_York")).date().isoformat():
            raise ValueError("Current calendar interval is not established")
        completed = sorted({row["date"] for row in calendar if
            datetime.fromisoformat(row["date"] + "T" + row["close"]).replace(tzinfo=ZoneInfo("America/New_York")) <= now})
        latest = completed[-1] if completed else None
        if not latest or latest != coverage.get("latest_completed_session"):
            result["reasons"].append("Saved history does not cover the authoritative latest completed session")
        result["latest_completed_session"] = latest
        result["calendar_through"] = through
        result["current_calendar"] = {"reference": reference, "through": through, "captured_at": source.get("captured_at")}
    except (ValueError, KeyError, TypeError, AttributeError):
        result["reasons"].append("Authoritative calendar coverage for the current date is unavailable")
    result["sufficient"] = coverage.get("sufficient") is True and not result["reasons"]
    return result
