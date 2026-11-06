# Local desk MCP interface

## Scope and design

Provide a local MCP client with desk status, the latest retained research and
one selected report, observed portfolio and fund budget, and cached stock quotes.
Use stdio and the official Python SDK already pinned in both desk runtime locks.
The adapter uses HTTPX, an installed SDK dependency, for the existing loopback
session. The SDK handles transport, tool discovery and schemas.

The general state route consults the credential store while building its market
view. Use dedicated GET projections for research, portfolio and quotes. Reuse
the desk's existing quote, fund-budget and research completeness logic. Keep
the latest result even if it failed or has missing evidence. The desk's normal
session checks protect the new routes. The MCP catalog has five read-only tools.

## Review and verification

- Independent review of `266a42e` confirmed the scope and flagged the nested
  reconciliation payload in status. `24341a3` limits it to status and gaps,
  uses a count for research coverage gaps, and declares structured tool results.
- The installed SDK client initialized over stdio with protocol `2025-11-25`,
  found five read-only tools with output schemas, and received the projected
  status from the development desk on port 8099.
- The running backend predates the context routes and returned HTTP 404. After
  the development tray reloads it, verify a retained research page and report,
  observed portfolio and a cached quote through the same SDK client. Check an
  unavailable research symbol and session enforcement.

Setup is in the [local desk guide](../local-desk-guide.md#connect-a-local-mcp-client).
The protocol and SDK choice use the [official Python SDK v1 guide](https://py.sdk.modelcontextprotocol.io/v1/).
