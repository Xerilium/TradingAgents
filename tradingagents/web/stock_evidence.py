"""Sourced supplementary observations, with no new provider credentials or subscriptions."""

import csv
import io
import json
import os
from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import uuid4

from .investor import decimal

DEFAULT = {"observations": {}, "history": {}}
PROVIDERS = {"alpaca": {"news", "corporate_actions"}, "sec_edgar": {"fundamentals", "classification"},
             "alpha_vantage": {"fundamentals", "classification", "earnings"}}


def usable(observation, scope=None):
    return observation.get("complete") is True and (observation.get("status") == "available" or
        observation.get("status") == "missing" and (observation.get("scope") or scope) in {"news", "corporate_actions"})


def configuration():
    return {"alpaca": "Uses existing paper credentials; news/actions access is separate from IEX entitlement and remains unverified",
            "sec_edgar": "Configured identification" if os.getenv("SEC_EDGAR_USER_AGENT", "").strip() else "Set SEC_EDGAR_USER_AGENT to your name and contact address in the server environment, then restart; no placeholder contact is used",
            "alpha_vantage": "Existing key configured; endpoint access is determined by the provider response" if os.getenv("ALPHA_VANTAGE_API_KEY") else "Set your existing ALPHA_VANTAGE_API_KEY in the server environment, then restart; no new key or plan is selected"}


def fetch(jobs, identity, symbol, scope, provider, request):
    records, receipts, gaps = [], [], []
    captured = datetime.now(UTC).isoformat()
    observation = {"id": str(uuid4()), "symbol": symbol, "scope": scope, "provider": provider,
        "captured_at": captured, "complete": False, "status": "unavailable", "records": records, "receipts": receipts,
        "gaps": gaps, "request": request, "immutable_research_changed": False}
    canceled = lambda: identity in jobs.canceled
    def preserve(payload, source, source_date=None):
        artifact = jobs.service.store._write_source_result(identity, str(uuid4()), payload.decode("utf-8") if isinstance(payload, bytes) else payload,
            prefix="stock-evidence", allow_pagination_cursor=provider == "alpaca")
        receipts.append({"source_url": source, "artifact": artifact, "captured_at": datetime.now(UTC).isoformat(), "source_date": source_date})
        return artifact
    try:
        if provider not in PROVIDERS or scope not in PROVIDERS[provider]:
            raise ValueError("This provider does not supply the selected evidence scope")
        if provider == "alpaca":
            endpoint = "/v1beta1/news" if scope == "news" else "/v1/corporate-actions"
            query = {"symbols": symbol, "start": request["start"], "end": request["end"], "limit": 50 if scope == "news" else 1000}
            if scope == "news":
                query.update(start=request["start"] + "T00:00:00Z", end=request["end"] + "T23:59:59Z")
            query.update({"include_content": "false"} if scope == "news" else {"data_quality": "all"})
            token, tokens = None, set()
            for _ in range(20):
                if token:
                    query["page_token"] = token
                response = jobs.read(endpoint + "?" + urlencode(query), data=True, canceled=canceled)
                source = "https://data.alpaca.markets" + endpoint
                preserve(response["raw"], source, response["source_date"])
                payload = response["data"]
                if scope == "news":
                    rows = payload.get("news")
                    if not isinstance(rows, list):
                        raise ValueError("News response has no supported article collection")
                    for row in rows:
                        if symbol not in row.get("symbols", []):
                            gaps.append("A news article did not identify the selected symbol")
                            continue
                        records.append({"kind": "news", "id": row.get("id"), "title": row.get("headline"),
                            "summary": row.get("summary"), "published_at": row.get("created_at"), "updated_at": row.get("updated_at"),
                            "source_url": row.get("url"), "publisher": row.get("source"), "retrieved_at": captured})
                else:
                    groups = payload.get("corporate_actions")
                    if not isinstance(groups, dict):
                        raise ValueError("Corporate-action response schema is unsupported")
                    for kind, rows in groups.items():
                        if not isinstance(rows, list):
                            raise ValueError("Corporate-action group is unsupported")
                        for row in rows:
                            if symbol not in {row.get("symbol"), row.get("old_symbol"), row.get("new_symbol"), row.get("initiating_symbol"), row.get("target_symbol")}:
                                gaps.append("Action has no exact selected-symbol association; inspect its source receipt")
                                continue
                            effective = row.get("ex_date") or row.get("effective_date")
                            records.append({"kind": kind, "id": row.get("id"), "effective_at": effective,
                                "process_date": row.get("process_date"), "date_basis": "ex/effective date as reported; API interval filters process date",
                                "source_url": source, "reported": row, "comparison_requires_review": True,
                                "limitation": None if effective else "Effective date is missing; action timing remains unconfirmed"})
                    gaps.append("Provider may publish actions after announcement; process-date coverage is not proof of timely announcement coverage")
                token = payload.get("next_page_token")
                if not token:
                    observation["complete"] = True
                    break
                if token in tokens:
                    raise ValueError("Supplementary pagination stopped advancing")
                tokens.add(token)
            if token:
                gaps.append("Supplementary page budget exhausted")
        elif provider == "sec_edgar":
            if not os.getenv("SEC_EDGAR_USER_AGENT", "").strip():
                observation["status"] = "not_configured"
                raise ValueError("SEC_EDGAR_USER_AGENT is required; no placeholder identity is sent")
            from tradingagents.dataflows.vendors.sec_edgar import _fetch_json, _STATEMENTS
            def sec(url):
                jobs.budget.wait(canceled)
                response = _fetch_json(url, receipt=True)
                preserve(response["raw"], url, response["source_date"])
                return response["data"]
            tickers = sec("https://www.sec.gov/files/company_tickers.json")
            match = next((v for v in tickers.values() if v.get("ticker", "").upper() == symbol), None)
            if not match:
                raise ValueError("Selected symbol has no SEC ticker/CIK mapping; no filer identity is guessed")
            cik = str(match["cik_str"]).zfill(10)
            if scope == "classification":
                source = "https://data.sec.gov/submissions/CIK" + cik + ".json"
                profile = sec(source)
                records.append({"kind": "industry", "value": profile.get("sicDescription"), "code": profile.get("sic"),
                    "classification_system": "SEC SIC", "source_url": source, "published_at": None, "retrieved_at": captured})
                gaps.append("SEC SIC industry is not a sector classification; sector remains unavailable")
            else:
                facts = sec("https://data.sec.gov/api/xbrl/companyfacts/CIK" + cik + ".json").get("facts", {}).get("us-gaap", {})
                for statement, items in _STATEMENTS.items():
                    for label, tags in items:
                        tag = next((t for t in tags if t in facts), None)
                        if not tag:
                            continue
                        for units, values in facts[tag].get("units", {}).items():
                            eligible = [v for v in values if v.get("filed") and v["filed"] <= request["end"] and decimal(v.get("val")) is not None]
                            if not eligible:
                                continue
                            value = max(eligible, key=lambda v: (v["filed"], v.get("end", "")))
                            accession = value.get("accn", "")
                            records.append({"kind": "reported_fact", "name": label, "statement": statement, "tag": tag,
                                "value": str(value["val"]), "units": units, "currency": "USD" if units == "USD" else None,
                                "period_start": value.get("start"), "period_end": value.get("end"), "published_at": value["filed"],
                                "form": value.get("form"), "provenance": "reported SEC XBRL fact; latest eligible filed vintage",
                                "source_url": "https://www.sec.gov/Archives/edgar/data/" + str(int(cik)) + "/" + accession.replace("-", "") + "/" + accession + "-index.html"})
                if not records:
                    gaps.append("No supported filed facts in this requested as-of boundary")
            observation["complete"] = True
        else:
            if not os.getenv("ALPHA_VANTAGE_API_KEY"):
                observation["status"] = "not_configured"
                raise ValueError("Existing ALPHA_VANTAGE_API_KEY is required; access to this endpoint is not inferred")
            from tradingagents.dataflows.vendors.alpha_vantage.common import _make_api_request
            jobs.budget.wait(canceled)
            if scope == "earnings":
                horizon = request.get("earnings_horizon")
                if horizon not in {"3month", "6month", "12month"}:
                    raise ValueError("Choose an explicit earnings-calendar horizon")
                payload = _make_api_request("EARNINGS_CALENDAR", {"symbol": symbol, "horizon": horizon})
                preserve(payload, "https://www.alphavantage.co/documentation/#earnings-calendar")
                for row in csv.DictReader(io.StringIO(payload)):
                    if row.get("symbol") != symbol:
                        continue
                    records.append({"kind": "earnings_calendar", "effective_at": row.get("reportDate"), "period_end": row.get("fiscalDateEnding"),
                        "estimate": row.get("estimate"), "currency": row.get("currency"), "date_status": "Provider calendar date; announcement versus estimate status not supplied",
                        "source_url": "https://www.alphavantage.co/documentation/#earnings-calendar"})
            else:
                from tradingagents.dataflows.vendors.alpha_vantage.fundamentals import get_fundamentals
                payload = get_fundamentals(symbol)
                preserve(payload, "https://www.alphavantage.co/documentation/#company-overview")
                profile = json.loads(payload) if isinstance(payload, str) else payload
                if profile.get("Symbol") != symbol:
                    raise ValueError("Company overview symbol identity differs")
                names = ("Name", "Description", "Sector", "Industry", "Country", "Exchange") if scope == "classification" else ("Name", "Description", "MarketCapitalization", "PERatio", "PriceToBookRatio", "EPS", "RevenueTTM", "EBITDA")
                for name in names:
                    value = profile.get(name)
                    records.append({"kind": "provider_ratio" if name in {"PERatio", "PriceToBookRatio"} else "provider_fact", "name": name,
                        "value": value, "units": "USD" if name in {"MarketCapitalization", "RevenueTTM", "EBITDA"} and profile.get("Currency") == "USD" else "provider stated / unspecified",
                        "currency": profile.get("Currency"), "period_end": None, "reported_latest_quarter": profile.get("LatestQuarter"),
                        "numerator_date": None, "denominator_date": None, "provenance": "Provider reported; not recomputed",
                        "limitation": "Current overview has no per-field vintage. Ratio component dates are unknown; incompatible-date comparisons require review.",
                        "source_url": "https://www.alphavantage.co/documentation/#company-overview"})
            observation["complete"] = True
        observation["status"] = "available" if records and observation["complete"] else "incomplete" if records else "missing"
    except Exception as exc:
        observation["status"] = observation["status"] if observation["status"] == "not_configured" else "unavailable"
        gaps.append("Evidence retrieval unavailable (" + type(exc).__name__ + "); " + configuration().get(provider, "select a supported existing provider"))
    observation["artifact"] = jobs.service.store._write_json_artifact(identity, "stock-evidence-observation", observation)
    def update(values):
        saved = values["stock_evidence"]
        current = saved["observations"].setdefault(symbol, {}).get(scope)
        meta = {k: observation[k] for k in ("id", "symbol", "scope", "provider", "captured_at", "complete", "status", "artifact", "gaps")}
        if current and usable(current, scope) and not usable(observation, scope):
            meta["last_usable_artifact"] = current["artifact"]
        elif current and current.get("last_usable_artifact") and not usable(observation, scope):
            meta["last_usable_artifact"] = current["last_usable_artifact"]
        from .investor import digest
        meta["effective_dates"] = sorted({str(record["effective_at"]) for record in records if record.get("effective_at")})
        meta["content_sha256"] = digest(records)
        saved["history"][observation["id"]] = meta
        saved["observations"][symbol][scope] = meta
    jobs.database.transact({"stock_evidence": DEFAULT}, update)
    return observation


def detail(jobs, symbol):
    import hashlib
    metadata = jobs.database.read("stock_evidence", DEFAULT)
    observations = {}
    for scope, item in metadata["data"]["observations"].get(symbol, {}).items():
        fallback = item.get("last_usable_artifact") if not usable(item, scope) else None
        reference = fallback or item["artifact"]
        path = (jobs.service.store.directory / reference["path"]).resolve()
        if not path.is_relative_to(jobs.service.store.directory.resolve()):
            raise ValueError("Stock-evidence reference escapes its boundary")
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != reference["sha256"]:
            raise ValueError("Stock-evidence source checksum differs")
        observation = json.loads(payload)
        observation.update(latest_attempt=item, retained_older_data=bool(fallback))
        observations[scope] = observation
    return {"symbol": symbol, "revision": metadata["revision"], "observations": observations, "configuration": configuration()}
