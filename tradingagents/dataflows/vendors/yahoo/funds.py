"""Yahoo fund snapshots, with explicit source and point-in-time limitations."""

from datetime import datetime
import json

import yfinance as yf

from tradingagents.dataflows.date_window import is_historical
from tradingagents.dataflows.errors import VendorUnavailableError
from tradingagents.dataflows.source_document import read_source_document
from tradingagents.dataflows.symbols import normalize_symbol
from tradingagents.dataflows.vendors.yahoo.common import raise_for_empty, yf_retry
from tradingagents.dataflows.vendors.yahoo.fundamentals import get_company_profile
from tradingagents.dataflows.router import observe_source_call


# Explicit primary-source locations; classification still comes solely from Yahoo.
_ISSUER_SOURCES = {
    "SGOV": "https://www.ishares.com/us/products/314116/ishares-0-3-month-treasury-bond-etf",
    "SHY": "https://www.ishares.com/us/products/239452/ishares-1-3-year-treasury-bond-etf",
    "BND": "https://workplace.vanguard.com/assets/corp/fund_communications/pdf_publish/us-products/fact-sheet/F0928.pdf",
}

# These are the public yfinance FundsData properties, not a list of funds.
_FUND_PROPERTIES = (
    ("Fund description", "description"),
    ("Asset classes", "asset_classes"),
    ("Top holdings", "top_holdings"),
    ("Equity holdings", "equity_holdings"),
    ("Bond holdings", "bond_holdings"),
    ("Bond ratings", "bond_ratings"),
    ("Sector weightings", "sector_weightings"),
    ("Fund operations and fees", "fund_operations"),
)


def _render(value):
    if value is None:
        return None
    if hasattr(value, "empty"):
        return None if value.empty else value.to_csv()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str) if value else None
    return str(value) if value != "" else None


def get_fund_data(symbol: str, curr_date: str = None) -> str:
    """Return a live fund snapshot, or withhold it for a historical analysis.

    Yahoo's current profile and FundsData have no verified historical vintage.
    The full returned tables are retained, although Yahoo itself may only provide
    top holdings and may not provide duration, maturity or an SEC yield.
    """
    canonical = normalize_symbol(symbol)
    if is_historical(curr_date):
        raise VendorUnavailableError(
            f"Fund data for {canonical} is withheld for {curr_date}: live fund snapshots and issuer pages have no verified historical vintage.")

    info = get_company_profile(canonical)
    if not info or not any(value is not None for value in info.values()):
        raise_for_empty(symbol, canonical, "fund profile")
    kind = str(info.get("quoteType") or "").upper()
    if kind not in {"ETF", "MUTUALFUND"}:
        label = kind or "unknown"
        raise VendorUnavailableError(f"Fund classification not established for {canonical}: Yahoo quote type {label}.")

    retrieved = datetime.now().astimezone().isoformat()
    lines = [f"# Yahoo fund data for {canonical}",
             f"Retrieved: {retrieved}; requested analysis date: {curr_date or 'unspecified'}.",
             "Current snapshot; individual field and holdings dates may differ or be unknown. "
             "Percentages and units are reported in Yahoo's original format.",
             "\n## Complete Yahoo profile (original field names and values)",
             json.dumps(info, ensure_ascii=False, default=str)]
    ticker = yf.Ticker(canonical)
    for title, attr in _FUND_PROPERTIES:
        try:
            value = observe_source_call(
                f"fund_{attr}", "yfinance", "fund_table",
                lambda: yf_retry(lambda: getattr(ticker.funds_data, attr)),
                requirement="supplemental", symbol=canonical, as_of_date=curr_date,
            )
            rendered = _render(value)
            lines.extend((f"\n## Yahoo {title}", rendered if rendered is not None else "Unavailable from Yahoo."))
        except (VendorUnavailableError, AttributeError) as exc:
            lines.extend((f"\n## Yahoo {title}", f"Unavailable: {type(exc).__name__}."))

    try:
        dividends = observe_source_call(
            "fund_distributions", "yfinance", "distribution_history",
            lambda: yf_retry(lambda: ticker.dividends.to_frame(name="distribution_per_share")), requirement="supplemental",
            symbol=canonical, as_of_date=curr_date,
        )
        lines.extend(("\n## Yahoo distribution history", _render(dividends) or "Unavailable from Yahoo."))
    except (VendorUnavailableError, AttributeError) as exc:
        lines.extend(("\n## Yahoo distribution history", f"Unavailable: {type(exc).__name__}."))

    lines.append("\nDuration, maturity, yield, credit quality, fees and distribution "
                 "details are available only where explicitly supplied above; missing "
                 "fields must not be inferred. Yahoo's top holdings are not necessarily "
                 "the complete portfolio.")
    # The source receipt must capture errors before they are turned into a gap.
    website = _ISSUER_SOURCES.get(canonical) or info.get("website")
    if isinstance(website, str) and website.startswith("https://"):
        specific = canonical in _ISSUER_SOURCES
        lines.append(f"\n## {'Fund-specific issuer source' if specific else 'Provider-supplied website'}\n{website}\n"
                     + ("Official fund source; verify the date of each metric from the document."
                        if specific else "Yahoo supplies this website; its association with this specific fund and document dates must be verified."))
        try:
            document = observe_source_call(
                "fund_issuer_source", "issuer", "source_document_text",
                lambda: read_source_document(website, curr_date),
                symbol=canonical, url=website,
            )
            lines.append(document)
        except Exception as exc:
            lines.append(f"Issuer source text unavailable: {type(exc).__name__}; no issuer metrics can be inferred.")
    else:
        lines.append("\n## Issuer evidence\nNo issuer website was supplied by Yahoo; "
                     "issuer fund-specific evidence is unavailable from this collector.")
    return "\n".join(lines)
