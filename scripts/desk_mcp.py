"""Serve read-only TradingAgents tools over local MCP stdio."""

import argparse
from typing import Annotated

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field


def serve(*, dev):
    profile, port = ("development", 8099) if dev else ("installed", 8098)
    mcp = FastMCP(
        "TradingAgents",
        instructions=f"Read the local {profile} desk. Research and market observations may be incomplete or stale.",
    )
    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                idempotentHint=True, openWorldHint=False)

    def get(path, **params):
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10,
                              trust_env=False, follow_redirects=False) as client:
                client.get("/").raise_for_status()
                response = client.get(path, params=params, headers={"Accept": "application/json"})
                if response.status_code in {400, 404, 503}:
                    raise ValueError(response.json()["error"])
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise ValueError(f"The {profile} desk rejected the read (HTTP {exc.response.status_code}).") from None
        except httpx.RequestError:
            raise ValueError(f"Cannot reach the {profile} desk on port {port}. Open the desk and try again.") from None

    @mcp.tool(annotations=read_only)
    def desk_status() -> dict:
        """Read service, engine and reconciliation status from the running desk."""
        health = get("/api/health")
        return {"profile": profile, **{key: health.get(key) for key in (
            "service", "engine", "engine_version", "browse_only",
            "account_observed_at", "prices_checked_at", "reconciliation", "history_status",
        )}}

    @mcp.tool(annotations=read_only)
    def list_research(offset: Annotated[int, Field(ge=0)] = 0,
                      limit: Annotated[int, Field(ge=1, le=100)] = 25) -> dict:
        """List the latest retained result per ticker, including failed and incomplete results."""
        return get("/api/context/research", offset=offset, limit=limit)

    @mcp.tool(annotations=read_only)
    def get_research(symbol: str, report: str | None = None) -> dict:
        """Read a ticker's latest retained research and available report keys. Pass a report key to read its text."""
        params = {"symbol": symbol}
        if report is not None:
            params["report"] = report
        return get("/api/context/research", **params)

    @mcp.tool(annotations=read_only)
    def get_portfolio() -> dict:
        """Read observed balances, position coverage, fund budget and SPY rebalance status."""
        return get("/api/context/portfolio")

    @mcp.tool(annotations=read_only)
    def get_quote(symbol: str) -> dict:
        """Read a cached stock price with its source, event time and configured freshness status."""
        return get("/api/context/quote", symbol=symbol)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", action="store_true", help="Use the isolated development desk on port 8099")
    serve(dev=parser.parse_args().dev)
