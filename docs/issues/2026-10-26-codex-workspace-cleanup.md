# Codex helper shutdown can fail research during temporary-folder cleanup

Status: Observed ACLS research and final-adapter portfolio synthesis passed; exceptional fallback paths remain source-only
Date: 26 October 2026

## Observed problem

The 23-stock research batch recorded Windows file-in-use errors for temporary tradingagents-research folders. INTC, ONTO, FORM and ACLS were observed with this error. Source inspection found that the adapter waited for and terminated only its immediate process, then called TemporaryDirectory.cleanup unconditionally from finally. That cleanup error could replace a returned model response or hide the original request error. The precise process holding each historical folder was not independently identified.

## Repair

In tradingagents/llm_clients/chatgpt_client.py, close stdin and wait for the app-server to exit. If it does not exit within three seconds, attempt to stop the owned Windows process tree while the root PID is still alive, then retain bounded direct-process termination as a fallback. Log process-shutdown and workspace-cleanup failures separately. Use the same non-throwing workspace cleanup on startup failure, preserving the original launch error.

The change targets the helper launched by that adapter instance. It does not terminate unrelated Codex desktop processes or weaken research tool restrictions.

## Evidence and limits

One real installed Codex account handshake and shutdown returned helper_exited=True, reader_stopped=True, workspace_removed=True, exit code 0 and no stderr. This exercised actual installed components without a model inference or research run. Python AST parsing and git diff --check passed once after the source batch. No automated tests, mocks or test files were created.

The app was restarted using the unchanged canonical Start-TradingDesk.cmd launcher. The internal browser then showed Nautilus connected and the observed paper account verified. This verifies loading and one helper lifecycle, not completion of every concurrent research path. Research continuation remains separate acceptance evidence.

The current adapter delta also contains the separate MCP isolation work. Existing unrelated working changes were preserved.

## Live research validation

The authorized eleven-stock continuation completed ONTO, FORM, UCTT, VECO and KLIC on the repaired adapter. No workspace-removal warning was present in launcher.err.log. One taskkill call exceeded its five-second timeout; the direct-process fallback settled and a later process query found that owned PID absent. Do not describe this as a warning-free shutdown run.

INTC and ACLS stopped on a different guard: an unexpected built-in mcpToolCall event. Four remaining stocks were not dispatched after that failure. Combined latest state was 17 completed and 6 failed, with no running or queued work. The full-universe portfolio was not modeled from that partial set. The original folder-cleanup exception did not recur in this observed run; tool-boundary handling is a separate open blocker.

## Later concurrent research evidence

The subsequent six-stock continuation produced multiple five-second `taskkill` timeouts and five workspace-cleanup warnings, including Windows errors 32 and 5. Successful reports were retained, but that does not establish reliable helper shutdown or folder removal. The logged root PIDs 59136, 33508, 55696, 57400 and 7916 and their direct children were absent when inspected later. A read-only current-directory inspection of 582 accessible processes found no remaining `tradingagents-research-` holder; the inspected failed folders still existed. Windows Restart Manager returned access denied when asked for users of the four inspected folders. These observations do not identify the process that held any folder at the time of failure or rule out inaccessible processes and other handle types. The EOF-first source change avoids calling taskkill when normal shutdown succeeds. Its effect under concurrent research and the cause of the historical folder locks remain unverified.

## EOF-first observation

The installed CLI resolved to the standalone 0.164.0 binary. In one bounded observation using the existing adapter and a real account handshake, the idle app-server root had one `conhost.exe` child. Closing stdin made the root exit with code 0 in 0.016 seconds; its reader stopped, the child PID was subsequently absent, and its temporary folder was removed. No inference or research ran. This observes one idle lifecycle, not concurrent research shutdown. The source now waits for EOF shutdown before invoking taskkill on a timeout or wait error. A later source review found that wait errors could escape or skip termination; the working tree now logs those errors and continues the bounded fallback. This correction has static checks only; live research validation is pending.

## Latest live validation

After the canonical reload, only ACLS was researched again; the other 22 completed results were preserved. ACLS saved all four analyst reports, the trader plan, risk review and final Underweight decision, then completed with coverage gaps. The actual Research view showed 23 completed and no failed, incomplete, running or queued stocks. A read of the restarted launcher log after completion found no process-tree stop, workspace-removal, shutdown-wait or unexpected built-in-tool warnings. This observes one stock with parallel analysts and subsequent decision stages; it is not proof of every seven-stock concurrency or forced-shutdown path. The final OSError fallback correction was then loaded through another canonical restart without rerunning completed stock research. The joint deep-model portfolio synthesis then completed on the final loaded adapter, with 23 eligible of 23 configured stocks. The restarted launcher log contained none of the same shutdown or unexpected-tool warnings after that completion. Exceptional OS wait failures remain source-only, and the historical folder holders remain unidentified. Reviewed revision: working tree over 580f1c8, adapter +64/-15 and StockTwits +19/-7. Independent Terra source review found the wait-error escape; the implementation worker corrected it before final load. Primary decision: accept the observed normal-path repair and completed failed-stock recovery with those stated limits; do not claim universal concurrent or forced-shutdown coverage.

## Source

- tradingagents/llm_clients/chatgpt_client.py: _AppServer.__init__, close, _cleanup_workspace, and ChatGPTChatModel._generate_once.
- Internal-browser Activity observations for batch 52d4731d-99d3-4788-bc60-1b92832e7baa, 26 October 2026.
- Real installed-helper handshake/shutdown and internal-browser Account observation, 26 October 2026.
- Working delta over 580f1c8 on nautilus.
