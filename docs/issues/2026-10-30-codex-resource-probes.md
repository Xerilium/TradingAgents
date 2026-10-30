# Codex rejects unavailable native resource probes

Status: Source fix awaiting independent review and installed verification
Reported: 30 October 2026

## Observed failure

The installed Codex account adapter stopped the shared-stock research batches
on native `list_mcp_resources` and `read_mcp_resource` starts. The requested
model remained gpt-6.1-terra. Full app-server inventory inspection showed the
configured MCP runtimes explicitly disabled, with no tools, resources or
resource templates. A tool-start event alone did not prove resource access.

## Source correction

Before research, require that full runtime inventory for every page. Track
each native resource probe from start to matching completion. Permit only
exact empty resource/template listings or a no-result failure with Codex's
exact unknown-server/unavailable-tool message. Reject successful resource
reads, any content or metadata outside the empty-list contract, other native
tools, changed identities and unfinished probes before returning a bound
function call or final answer. Disabled connections remain the access boundary;
checking completion cannot undo access.

## Evidence and limits

The implementation follows Codex `rust-v0.164.0`: `codex-mcp/src/connection_manager/resources.rs`
and `core/src/tools/handlers/mcp_resource/` establish the exact unavailable
errors, listing payloads and item lifecycle. The generated app-server schema
includes `runtimeStatus` in full MCP inventory. No model request, research run,
mock test, package build or production update was performed for this fix.
Static syntax validation and independent review are recorded by the coordinator.

Sources: https://github.com/openai/codex/tree/rust-v0.164.0/codex-rs/core/src/tools/handlers/mcp_resource
and https://github.com/openai/codex/blob/rust-v0.164.0/codex-rs/codex-mcp/src/connection_manager/resources.rs
