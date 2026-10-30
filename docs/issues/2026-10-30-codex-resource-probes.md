# Codex rejects unavailable native resource probes

Status: Follow-up source fix awaiting independent review and installed verification
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
includes `runtimeStatus` in full MCP inventory. Initial source preparation used
static checks. The coordinator subsequently installed revision `8423d6c` and
observed the validation failure below. The event-order follow-up still requires
fresh independent review and installed validation.

Sources: https://github.com/openai/codex/tree/rust-v0.164.0/codex-rs/core/src/tools/handlers/mcp_resource
and https://github.com/openai/codex/blob/rust-v0.164.0/codex-rs/codex-mcp/src/connection_manager/resources.rs

## Parallel event handoff

The parent reported that installed validation run
`f67937ad-d2bd-41f6-a843-03165f867d55` stopped UCTT with an unfinished-probe
error. The stored error did not identify which return path raised it; it does
not establish that event interleaving caused this particular failure.

Codex 0.164.0 marks both dynamic functions and native resource handlers as
parallel-capable. Its dispatcher gives them shared execution locks, so a bound
function request may arrive before an earlier resource probe completes. Retain
the validated function request while processing probe completions. Conflicting
requests fail explicitly. Interrupt only when every observed probe is validated,
then continue through the matching turn completion to validate queued native
events before returning that same single function call. Only our requested
interruption without a turn error is accepted as an expected interrupted status.

This handoff uses the existing 30-second startup allowance as a bounded drain
grace, capped by the caller's deadline. Ordinary model-generation timing stays
unchanged. Restore the prior deadline on success, error or cancellation; a drain
timeout fails explicitly without retry. Final-text and function-call unfinished
errors now identify their boundary without logging arguments or report content.

No further model request, research run, package build or installed-app change
was performed by this follow-up worker. Source review and static syntax checks
do not establish that the UCTT failure is repaired in the installed app.

Ordering sources (tag `rust-v0.164.0`, read 30 October 2026):
- https://github.com/openai/codex/blob/rust-v0.164.0/codex-rs/core/src/tools/handlers/dynamic.rs
- https://github.com/openai/codex/blob/rust-v0.164.0/codex-rs/core/src/tools/handlers/mcp_resource/list_mcp_resources.rs
- https://github.com/openai/codex/blob/rust-v0.164.0/codex-rs/core/src/tools/parallel.rs
- https://learn.chatgpt.com/docs/app-server (dynamic call and item lifecycle)
- https://github.com/openai/codex/blob/rust-v0.164.0/codex-rs/app-server/src/bespoke_event_handling.rs (interrupt acknowledgement precedes terminal notification)
