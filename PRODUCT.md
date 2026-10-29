# Product

<!-- impeccable:product-schema 1 -->

## Platform

Windows desktop first, with a local browser interface and a macOS packaging target.

## Stack

Tauri owns the desktop window and app-owned processes. A local Python desk service
serves plain JavaScript/CSS workspaces. TradingAgents, LangGraph and LangChain
coordinate research. Local Laya screens social posts. Maenifold provides memory
and tools. NautilusTrader supplies native trading and isolated historical
evaluation through a custom Alpaca integration. See [README](README.md) for the
component map and [platform reference](docs/platform-reference.md) for source links.

## Users

An individual operating their research and trading desk: discover instruments,
inspect evidence, plan exact terms, evaluate historical scenarios, review account
observations and decide which orders to authorize. Their existing records and
configuration are authoritative; sample portfolios and fabricated outcomes are not.

## Product Purpose

Make existing research, analysis, planning, evaluation and trading capabilities
usable as a coherent workspace. Each task needs a clear starting point, relevant
evidence, explicit action and return path. The UI serves the operator's job rather
than mirroring internal service boundaries.

## Positioning

An integrated agentic trading platform with human control over broker actions.
The research framework is one component. Model recommendations, allocations and
simulations support judgment; they do not establish executable orders or results.

## Operating Context

- Production is the installed application on port 8098 with private runtimes and profile.
- Development uses port 8099 and a separate profile, stores and credential namespace.
- Provider/account settings must be read from actual saved configuration.
- Desktop credentials use the operating-system vault.
- Keep only the latest research result per ticker. New research replaces it;
  interrupted research is not resumed. Maenifold owns long-term research memory.
- Authored notes, lists, rules, orders, baskets and settings have separate retention.
- Source capability, visible UI behavior and exercised broker execution are distinct evidence.

## Capabilities and Constraints

The current workspace map and eight concrete stories are in
[user workflows](docs/user-workflows.md). The UI assignment reorganizes existing
capability only; it cannot invent backend actions, data, automatic handoffs or a
mandatory research-to-trade funnel.

Keep the following distinctions visible:

- The inspected stock is independent of the selected research batch.
- Place guarded research launch beside selection, with exact-batch confirmation.
- A session-only model proposal uses separate capital and eligible saved research.
- Human baskets create linked drafts with independently handled legs.
- Historical simulations require supported saved inputs and explicit assumptions.
- Approval binds exact terms; submission is a separate action.
- Performance uses actual retained observations and states missing coverage.

## Evidence on Hand

The repository contains implemented desktop, service, research, integration and
evaluation paths. Retained records may exist in the installed profile. Do not
infer their contents or the active configuration from defaults. Current verification
limits belong in [the operating guide](docs/local-desk-guide.md#acceptance-evidence);
historical reports do not certify today's interface.

## Product Principles

1. Keep selection, evidence and the action using them together.
2. Name the object and its scope: batch, stock result, model allocation, draft or order.
3. Preserve context when moving between lists, details and saved work.
4. Give the main task usable space; disclose secondary controls and technical evidence.
5. Show missing, stale, partial and failed data honestly.
6. Preserve existing order authority and production data.
7. Keep documentation concise, source-backed and useful for operation.
