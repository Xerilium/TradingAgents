"""Named performance methods; availability depends on actual collection inputs."""

from .investor import digest

VERSION = "performance-method-assessment-v2"
METHODS = {"inputs": "alpaca-1d-completed-ny-calendar-windows-v2",
           "modified_dietz": "modified-dietz-recorded-flow-time-v1",
           "time_weighted": "linked-external-flow-boundaries-v1",
           "benchmark": "matched-sessions-split-price-reference-v2"}
SEMANTICS = {
    "valuation": "Declared daily session-close convention: map the New York date of each 1D provider label to its completed calendar close, including early closes. Original labels remain recorded; mapped closes are not broker-supplied exact valuation-event timestamps.",
    "flows": "ALL per-type window cashflow reconciled to precise effective external activity; creation-time pagination alone is insufficient. Unknown capital types and ACAT/in-kind coverage block calculation.",
    "boundaries": "Daily close mapping does not create before/after-flow valuations. Time-weighting requires actual matching boundaries for every external flow.",
    "benchmark": "USD IEX split-adjusted daily price reference over identical sessions; excludes reinvested dividends and benchmark costs.",
    "sources": ["https://docs.alpaca.markets/us/reference/getaccountportfoliohistory-1",
                "https://docs.alpaca.markets/us/docs/account-activities",
                "https://www.ibkrguides.com/portfolioanalyst/money-weighted-return-white-paper-llc.pdf",
                "https://docs.alpaca.markets/us/reference/legacycalendar"],
}


def assessment(collection, *, benchmark=None, history=None):
    binding = {"version": VERSION, "methods": METHODS, "source_semantics": SEMANTICS}
    supported = (collection.get("coverage", {}).get("method") == METHODS["inputs"]
                 and collection.get("source") == "Alpaca paper Trading API"
                 and collection.get("currency") == "USD" and collection.get("timeframe") == "1D"
                 and collection.get("cashflow_types") == "ALL")
    return {"version": VERSION, "accepted": supported, "status": "supported_method" if supported else "unsupported_method",
            "source_semantics_sha256": digest(SEMANTICS), "binding_sha256": digest(binding), "binding": binding,
            "reasons": [] if supported else ["Collection source, currency, timeframe or cashflow contract does not match the named method."]}


def qualify(calculation, method_assessment):
    calculable = calculation.get("calculable", calculation.get("available")) is True
    accepted = method_assessment["accepted"]
    result = {**calculation, "calculable": calculable, "available": calculable and accepted,
              "accepted_metric_ready": calculable and accepted, "provisional": not accepted,
              "status": "available" if calculable and accepted else "unsupported_method" if calculable else "uncalculable",
              "method_assessment": method_assessment}
    reasons = list(method_assessment["reasons"])
    if calculation.get("reason"):
        reasons.insert(0, calculation["reason"])
    reasons.extend(calculation.get("reasons", []))
    result["readiness_reasons"] = list(dict.fromkeys(reasons))
    if not result["available"]:
        result["reason"] = "; ".join(result["readiness_reasons"]) or "Required calculation inputs are unavailable"
    return result
