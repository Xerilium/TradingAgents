"""Keyless source discovery in the existing research process."""

from datetime import UTC, datetime

from tradingagents.dataflows.date_window import is_historical
from tradingagents.dataflows.errors import VendorUnavailableError
from tradingagents.dataflows.router import retry_source_call


def search_sources(query: str, max_results: int, trade_date: str) -> dict:
    if not query.strip():
        raise ValueError("Supply a non-empty source search query.")
    if type(max_results) is not int or max_results < 1:
        raise ValueError("max_results must be a positive integer.")
    if is_historical(trade_date):
        raise VendorUnavailableError("Live web search has no verified historical vintage; use dated SEC tools.")
    from ddgs import DDGS

    def acquire():
        # A network-request timeout, not a deadline on an agent or research run.
        with DDGS(timeout=30) as search:
            rows = search.text(query, max_results=max_results)
        return {"query": query, "provider": "ddgs",
                "retrieved_at": datetime.now(UTC).isoformat(),
                "results": [{"title": row["title"], "url": row["href"], "snippet": row["body"]}
                            for row in rows]}

    return retry_source_call("search_research_sources", "ddgs", "web_search_results",
                             acquire, query=query, max_results=max_results, trade_date=trade_date)
