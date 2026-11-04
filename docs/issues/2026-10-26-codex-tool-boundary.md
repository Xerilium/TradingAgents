# Research stops on an unexpected Codex MCP tool event

Status: Isolation repair passed the observed six-stock continuation; separate cleanup and empty-social faults remain
Reported: 26 October 2026

## Observed failure

After the workspace-cleanup repair was loaded, the real eleven-stock continuation stopped INTC and ACLS with: Codex exposed an unexpected built-in tool (mcpToolCall) for requested model gpt-6-luna; account adapter stopped. The remaining four stocks (AEIS, COHU, PLAB, AMKR) were not dispatched. Combined latest state: 17 completed, 6 failed, no active work.

Five continuation stocks completed: ONTO, FORM, UCTT, VECO and KLIC. They can be preserved for subsequent work; do not rerun the completed set just to recover the unfinished six.

## Established facts and uncertainty

The adapter deliberately rejects built-in tool events and accepts only bound TradingAgents functions. Keep that boundary. The generic error currently omits the server/tool identity, so the actual requested tool and cause of the event are not established. Do not assume all mcpToolCall events are safe or remove the guard to make research finish.

A real no-inference app-server config and thread inventory read found configured Maenifold, REA and Node REPL servers. The adapter's per-thread disabled overrides yielded no listed tools in that ephemeral thread. That inventory does not reproduce or explain the failed model call. At failure, the source set apps/plugins/browser/computer/shell features false and derived per-thread disabled overrides from config/read.

## Implemented repair and current evidence

The adapter now reads the installed CLI MCP catalog using the same restricted feature flags, sanitized environment and empty temporary working directory as the helper. It disables each configured server in the helper startup arguments, rather than relying on an empty table or waiting until thread creation. Before any research turn, it checks every page of that thread's MCP inventory and stops if built-in tools are present. The existing event/function allowlist stays in place. Unexpected MCP events now retain bounded server/tool names without arguments.

The CLI catalog must use the same feature settings as the helper: otherwise it can include app-owned virtual endpoints that are not valid named transport overrides in the restricted helper. CLI dotted overrides use bare server keys; quoted segments were rejected by the installed CLI. These startup configuration errors were found before app reload and no research ran with those candidate configurations.

The installed-helper check showed maenifold, node_repl and rea enabled=False, each thread runtime disabled, zero tools, clean helper/reader exit and workspace removal, with no stderr. Syntax and whitespace checks passed after the complete source batch. The app was restarted through the canonical launcher and the observed paper account reconnected.

The six unfinished stocks (INTC, ACLS, AEIS, COHU, PLAB, AMKR) were then started from the actual UI, with all four analysts, to validate the repair live and complete the original research request. Seventeen existing completed results were preserved. The continuation completed INTC, AEIS, COHU, PLAB and AMKR. ACLS reached its final decision but failed a separate StockTwits empty-result completion check. No unexpected built-in MCP event recurred in these six paths. Combined state is 22 completed and ACLS failed, with no active research. This supports the observed isolation repair; it does not identify the original tool or prove every nondeterministic path. Later launcher logs still contain process-tree stop and workspace-removal warnings, so helper shutdown remains open under its separate issue. Preserve all 22 completed results for the final ACLS retry.

The remaining ACLS retry subsequently completed after the separate empty-social repair, preserving the 22 other results. The final loaded adapter also completed the joint synthesis using 23 of 23 configured stocks, without an unexpected built-in-tool or lifecycle warning in its restarted log. Combined adapter source delta for shutdown and isolation repairs: 64 lines added, 15 removed. No test files, mocks or scripted research test suite were created.

## Acceptance criteria

Establish whether the failed event represents a genuinely exposed built-in server or an incompatible representation of a bound dynamic function. Retain non-sensitive server/tool identity when rejecting an unexpected tool, without recording credentials or entire untrusted argument payloads. Correct the actual exposure or protocol handling. Preserve exact requested models, app-owned tool execution, the bound-function allowlist and fail-closed behaviour for unrelated tools. Do not enable arbitrary built-in MCP, shell, browser or broker tools.

Validate with the actual previously failing stock paths. Keep external feed failures (including Reddit rate limiting and public-source failures) distinct from adapter/protocol failures. Then continue only unfinished stocks and model the complete universe once every required stock result is available. Do not silently exclude failures or present partial research as complete.

## Source

- Internal-browser live Activity and final batch counts, 26 October 2026.
- tradingagents/llm_clients/chatgpt_client.py: _AppServer config and ChatGPTChatModel._generate_once.
- Official protocol: https://learn.chatgpt.com/docs/app-server, accessed 26 October 2026; dynamicToolCall versus mcpToolCall event handling.
- Official MCP configuration: https://learn.chatgpt.com/docs/extend/mcp, accessed 26 October 2026.
- Working tree over 580f1c8; tool-boundary repair in chatgpt_client.py, with live-validation limits recorded above.
