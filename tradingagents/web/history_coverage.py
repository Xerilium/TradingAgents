"""Required baseline coverage is independent of a selected chart range."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from .investor import decimal, digest

REQUIRED_SESSIONS = 252


def scan_axis(history, input, cutoff):
    """Qualified provider buckets; expected slots never create price observations."""
    cutoff = datetime.fromisoformat(cutoff) if isinstance(cutoff, str) else cutoff
    calendar, coverage = history.get("calendar"), history.get("calendar_coverage")
    reference = history.get("calendar_artifact")
    result = {"observations": {}, "expected_buckets": [], "status": "unavailable", "reasons": [],
        "calendar": calendar, "calendar_coverage": coverage, "calendar_reference": reference,
        "query_bounds": {key: history.get(key) for key in ("start", "end")}}
    try:
        selected, session = input["timeframe"], input["session"]
        timeframe = history.get("timeframe", selected)
        derived = selected in {"5Min", "15Min", "30Min", "1Hour"} and session == "regular" and timeframe == "1Min"
        if not derived and (selected, session) not in {("1Min", "regular"), ("1Day", "provider_day")}:
            raise ValueError("Provider bucket grid/session convention is unqualified for " + selected + "/" + session
                + "; retain the requested interval and qualify its origin and closing bucket before evaluation")
        if not cutoff or cutoff.utcoffset() is None:
            raise ValueError("Market cutoff requires an explicit timezone")
        if not history.get("captured_at"):
            raise ValueError("Actual source capture time is unavailable")
        capture = datetime.fromisoformat(history["captured_at"])
        if capture.utcoffset() is None:
            raise ValueError("Source capture timezone is unavailable")
        if (not isinstance(calendar, list) or not isinstance(coverage, dict) or not reference
                or coverage.get("reference") != reference):
            raise ValueError("Exact retained calendar response and authenticated request bounds are required")
        first, last = date.fromisoformat(coverage["start"]), date.fromisoformat(coverage["end"])
        zone = ZoneInfo("America/New_York")
        if not first <= cutoff.astimezone(zone).date() <= last:
            raise ValueError("Retained calendar request does not cover the market cutoff; collect explicit calendar coverage")
        from urllib.parse import parse_qs, urlsplit

        from .evaluation import SCAN_LIMITS
        receipts = [row for row in history.get("receipts", []) if "page_token" in row]
        pages = history.get("bar_pages", {})
        bounds, next_token = None, None
        absence_proven = timeframe == "1Min" and bool(receipts) and history.get("pagination_complete") is True
        for receipt in receipts:
            path = urlsplit(receipt.get("request_path", ""))
            query = parse_qs(path.query)
            if not query.get("start") or not query.get("end"):
                absence_proven = False
                continue
            lower, upper = (datetime.fromisoformat(query[key][0].replace("Z", "+00:00")) for key in ("start", "end"))
            if lower.utcoffset() is None or upper.utcoffset() is None or lower > upper or bounds and bounds != (lower, upper):
                raise ValueError("Provider page request bounds are conflicting or unsupported")
            bounds = (lower, upper)
            payload = pages.get(receipt.get("artifact", {}).get("sha256"))
            absence_proven &= (path.path == "/v2/stocks/bars" and query.get("symbols") == [history["symbol"]]
                and query.get("timeframe") == [timeframe] and query.get("feed") == [history["feed"]]
                and query.get("adjustment") == [history["adjustment"]] and query.get("asof") == [history["asof"]]
                and receipt.get("page_token") == next_token and query.get("page_token", [None]) == [next_token]
                and isinstance(payload, dict) and isinstance(payload.get("bars"), dict)
                and not set(payload.get("bars", {})) - {history["symbol"]} and "next_page_token" in payload)
            next_token = payload.get("next_page_token") if isinstance(payload, dict) else None
        absence_proven &= not next_token and bounds is not None
        warmup_start = bounds[0] if bounds else datetime.combine(date.fromisoformat(history["start"]), datetime.min.time(), zone)
        result["query_bounds"] = {"start_at": bounds[0].isoformat(), "end_at": bounds[1].isoformat()} if bounds else {
            "start": history["start"], "end": history["end"], "limitation": "Legacy source has no exact per-page request paths; absence is unproven"}
        sessions, expected = {}, []
        for row in calendar:
            day = date.fromisoformat(row["date"])
            opening = datetime.fromisoformat(row["date"] + "T" + row["open"])
            closing = datetime.fromisoformat(row["date"] + "T" + row["close"])
            opening = opening.replace(tzinfo=zone) if opening.tzinfo is None else opening.astimezone(zone)
            closing = closing.replace(tzinfo=zone) if closing.tzinfo is None else closing.astimezone(zone)
            if day in sessions or not first <= day <= last or not opening < closing or opening.date() != day or closing.date() != day:
                raise ValueError("Retained calendar contains conflicting or unsupported sessions")
            sessions[day] = (opening, closing)
        for day, (opening, closing) in sorted(sessions.items()):
            if day < warmup_start.astimezone(zone).date():
                continue
            if timeframe == "1Day":
                end = datetime.combine(day + timedelta(days=1), datetime.min.time(), zone)
                if end <= cutoff:
                    if len(expected) >= SCAN_LIMITS["expected_buckets"]:
                        raise ValueError("Expected bucket budget exceeded; reduce the requested source range, no slots were truncated")
                    expected.append({"t": day.isoformat(), "closed_at": end.isoformat()})
            else:
                start = opening.astimezone(UTC)
                if start.second or start.microsecond or closing.second or closing.microsecond:
                    raise ValueError("Retained session boundaries do not establish a whole-minute grid")
                start = max(start, warmup_start.astimezone(UTC))
                if start.second or start.microsecond:
                    start = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
                count = max(0, int((min(closing, cutoff) - start).total_seconds() // 60))
                if len(expected) + count > SCAN_LIMITS["expected_buckets"]:
                    raise ValueError("Expected minute budget exceeded; reduce the requested source range, no slots were truncated")
                while start + timedelta(minutes=1) <= min(closing, cutoff):
                    expected.append({"t": start.timestamp(), "closed_at": (start + timedelta(minutes=1)).isoformat()})
                    start += timedelta(minutes=1)
        result["expected_buckets"] = expected
        absence_basis = {}
        if timeframe == "1Min":
            observed_through = min([capture, *[datetime.fromisoformat(row["captured_at"]) for row in receipts]])
            lower, upper = bounds or (warmup_start, warmup_start)
            absence_basis = {"start_at": lower.isoformat(), "end_at": min(upper,
                observed_through.replace(second=0, microsecond=0)).isoformat(), "receipts": receipts,
                "source_url": "https://docs.alpaca.markets/us/docs/market-data-faq#how-are-bars-aggregated",
                "meaning": "provider_reported_no_eligible_bar; does not prove zero trades or volume"}
            result["absence"] = {"proven": bool(absence_proven), "basis": absence_basis}
        if derived:
            step = timedelta(minutes={"5Min": 5, "15Min": 15, "30Min": 30, "1Hour": 60}[selected])
            buckets = []
            for _, (opening, closing) in sorted(sessions.items()):
                start = opening.astimezone(UTC)
                if closing <= warmup_start:
                    continue
                while start < closing:
                    end = min(start + step, closing)
                    if end > warmup_start and end <= cutoff:
                        if len(buckets) >= SCAN_LIMITS["expected_buckets"]:
                            raise ValueError("Derived bucket budget exceeded; no requested buckets were truncated")
                        buckets.append({"t": start.timestamp(), "closed_at": end.isoformat(),
                            "expected_minutes": [(start + timedelta(minutes=offset)).timestamp()
                                for offset in range(int((end - start).total_seconds() // 60))],
                            "partial_session_close": end - start < step})
                    start = end
            result["aggregation"] = {"version": "regular-minute-native-v1", "timeframe": selected, "buckets": buckets,
                "absence_proven": bool(absence_proven), "absence_basis": absence_basis}
        ordinals = {row["t"]: index for index, row in enumerate(expected)}
        previous = None
        for bar in sorted(history.get("bars", []), key=lambda row: row["t"]):
            stamp = datetime.fromisoformat(bar["provider_timestamp"].replace("Z", "+00:00"))
            if stamp.utcoffset() is None:
                raise ValueError("Provider bucket timestamp has no timezone")
            stamp = stamp.astimezone(zone)
            if timeframe == "1Day":
                end = datetime.combine(date.fromisoformat(bar["t"]) + timedelta(days=1), datetime.min.time(), zone)
                identity_matches = stamp.date().isoformat() == bar["t"] and stamp.time().replace(tzinfo=None) == datetime.min.time()
                basis = "Alpaca provider New York calendar day; closes at next New York midnight, not regular-session close"
            else:
                end = stamp + timedelta(minutes=1)
                bounds = sessions.get(stamp.date())
                if not bounds or not bounds[0] <= stamp < end <= bounds[1]:
                    continue
                identity_matches = stamp.timestamp() == bar["t"] and not stamp.second and not stamp.microsecond
                basis = "Alpaca left-closed right-open minute bucket, filtered to the retained regular session"
            ordinal = ordinals.get(bar["t"])
            reasons = []
            if not identity_matches:
                reasons.append("Provider timestamp differs from the recorded bucket identity")
            if ordinal is None or capture < end or cutoff < end:
                reasons.append("Bucket is unfinished, outside qualified calendar coverage or not observed after closure")
            first_missing = previous + 1 if previous is not None else 0
            gap = ordinal is None or ordinal != first_missing
            if gap and ordinal is not None and absence_proven:
                absent = expected[first_missing:ordinal]
                gap = any(datetime.fromtimestamp(row["t"], UTC) < datetime.fromisoformat(absence_basis["start_at"])
                    or datetime.fromisoformat(row["closed_at"]) > datetime.fromisoformat(absence_basis["end_at"]) for row in absent)
            result["observations"][str(bar["t"])] = {"closed": not reasons, "closed_at": end.isoformat(),
                "closure_basis": basis, "gap_before": gap,
                "reasons": reasons, "expected_ordinal": ordinal}
            if ordinal is not None:
                previous = ordinal
        if history.get("pagination_complete") is not True:
            raise ValueError("Provider pagination is incomplete; retained rows do not establish complete axis coverage")
        if not expected:
            raise ValueError("No completed expected bucket is established by the retained calendar at this cutoff")
        result["status"] = "available"
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        result["reasons"].append(str(exc))
    return result


def indicator_observations(bars, coverage, *, captured_at, timeframe, now=None):
    """Separate provider daily-bucket closure from regular-session coverage."""
    now = now or datetime.now(UTC)
    capture = datetime.fromisoformat(captured_at)
    completed = set(coverage.get("required_dates", []))
    latest = coverage.get("latest_completed_session")
    provenance = coverage.get("provenance", {})
    calendar_known = bool(provenance.get("calendar_reference") and provenance.get("instrument_reference"))
    recent = 0 <= (now - capture).total_seconds() <= 900
    observations = {}
    for bar in bars:
        end = None
        if timeframe == "1Day":
            end = datetime.combine(date.fromisoformat(bar["t"]) + timedelta(days=1),
                                   datetime.min.time(), ZoneInfo("America/New_York"))
        observations[str(bar["t"])] = {"closed": end is not None and capture >= end,
        "closed_at": end.isoformat() if end else None,
        "closure_basis": "Alpaca daily bucket: New York midnight to next midnight; later corrections remain possible",
        "closure_policy_source": "https://docs.alpaca.markets/us/docs/market-data-faq#how-are-bars-aggregated",
        "fresh": timeframe == "1Day" and calendar_known and recent and bar["t"] == latest,
        "session_completed": timeframe == "1Day" and calendar_known and bar["t"] in completed,
        "source_recent": recent, "freshness_policy": "capture within 900 seconds; latest completed calendar session",
        "latest_completed_session": latest,
        "limitation": "Bucket closure does not prove immutable prices or complete regular-session coverage"}
    return observations


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


def current(meta, data, artifact, now=None, calendar_meta=None, calendar_cache=None):
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
        cache = calendar_cache if calendar_cache is not None else {}
        key = (reference.get("path"), reference.get("sha256"), now)
        if key not in cache:
            cache[key] = sorted({row["date"] for row in calendar if
                datetime.fromisoformat(row["date"] + "T" + row["close"]).replace(tzinfo=ZoneInfo("America/New_York")) <= now})
        completed = cache[key]
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
