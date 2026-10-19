# UAT completion — 19 October 2026

## Result

Alpaca is not blocking the exercised workflow. The actual browser shows the existing paper account connected, Nautilus 1.231.0 in sync, cash/equity/buying power each $100,000, zero positions/open orders and all 503 configured IEX latest prices present. Orders explicitly says: “Account connected · Nautilus in sync · New orders not paused.” There is no approved order because this UAT did not approve or submit one.

All remaining checks feasible under the no-trade/no-new-research boundary have been completed. Consolidated coverage is **41 PASS, 0 FAIL, 2 PARTIAL and 6 NOT EXERCISED**, across the original 49 cases. This combines retained 18 October results with the additional 19 October evidence identified in case-results.json. It is not a claim that all 41 cases were rerun today or that an unexecuted broker cycle passed. Independent sign-off is recorded separately in independent-review.md.

The two partial cases need actual working orders, holdings or accounting events to finish their remaining branches. The six unexecuted cases require prohibited approval/order/research actions or authentic account events that do not exist in the retained records. These are evidence boundaries, not added app prerequisites. No new trading restriction was introduced.

U13 establishes keyboard selection and the dated chart title/values. Native mouse-hover display was not exercised; it is not claimed as a pass.

## Completed work

| Cases | Fresh evidence and outcome |
|---|---|
| Browser, U01/U02/U03/U29 | The old tab was a connection-refused error page because the local service was down. Restarted the saved application configuration, opened its normal HTTP address and connected Nautilus through the UI. Fresh market-open account and 503 numeric prices confirmed. No browser security bypass or endpoint change. |
| U08 | Applied Merge from the mixed CSV into the settings draft. Membership remained exactly 503 unique symbols; discarded the draft without changing the saved index. |
| U13/U14 | Keyboard-activated an actual dated OHLC chart bar and observed the date/value change. Matched AAPL's September 16 SMA 319.1440350341797, October 16 SMA 325.66100036621094 and close 341.81 to saved inputs. Claims remain attributed opinions; absent indicators, unknown adjustment basis and unavailable supplementary evidence stay explicit. Independently checked 86 existing MSFT news records and their source receipts. No new research or source collection. |
| U18 | Reproduced Refresh resetting a nonzero table scroll from 1456 to 0. Applied the five-line fix, then observed 1244 to 1244 across manual Refresh and later polling. Filtered Adobe list survived opening/returning; filters intentionally reset scroll. Selected research/range/date and unsaved note survived Refresh. |
| U25/U33/U38 | Used keyboard search, selection, stock review, exact local order preview, draft save and rejection. The saved BUY 1 ADBE LIMIT 100 preview reported server checks pass; no approval was executed. Rejected revision 2 remains in the journal without approval, broker order or fills. Focus visible; desktop 1024×768 and narrower 768×800 layouts had no page-width overflow. This is the scoped desktop usability case, not accessibility certification. |
| U32/U45 | Opened the existing October 1–16 interval containing genuine +$100,000 JNLC activity. The UI correctly leaves its treatment unclassified and withholds returns/drawdown where coverage and boundary valuations are insufficient. This corrects the earlier overbroad statement that no activity existed. It does not prove deposit, dividend or filled-order accounting. |
| U46 | Uploaded and inspected the validated backup through the actual browser at isolated port 8099, then restored that isolated copy. UI reported successful restoration. Independent comparison matched 503 symbols, saved records and all 3,608 immutable artifact hashes. The active workspace was never restored. |
| U48 | Separate isolated engineering checks passed all 19 local request-protection cases. Credential ACL was limited to the user, SYSTEM and Administrators. Five configured secret values were absent from 3,611 archive entries and six retained exports. This is bounded evidence, not an exhaustive security audit. |
| U47 | Opened the genuine retained failed research run and its recorded error/events, then returned to the existing completed run. No Start or Retry. Two existing isolated cancellation tests failed in obsolete fixture setup before queueing; neither establishes a product cancellation failure or pass. |

## Surgical fix and scope

Requirement A3/A14, case U18: retain review/table context during refresh. app.js restored scroll while the newly rendered table was still empty, which clamped it to zero. It now retains the old bound table's position and restores it after the new rows are populated. Source diff: scroll-fix.diff; original: app-before-scroll-fix.js.

**Five authored product lines, one removed, net four; score −5. Zero new tests, dependencies, features or system-setting changes.** Existing unrelated working-tree changes were preserved. The earlier 18 October remediation (+80/−48 across seven files) is separate and documented in that report. Alpaca transport, Nautilus and per-order approval remain operational; no capability was disabled to obtain a pass.

## Remaining evidence boundaries

| Cases | What has not been established | Why it remains |
|---|---|---|
| U27 PARTIAL | Basket conflicts with actual pending orders and sale-funded-buy conditions | The account has no holdings or working orders. Existing exact quantity/weight/partial-completion previews passed; no broker state was manufactured. |
| U32 PARTIAL | Complete performance accounting across real fills/cashflows | Flat-account reporting and real unclassified-activity handling are established. Full event accounting lacks sufficient genuine records. An optional benchmark is not a prerequisite. |
| U41 NOT EXERCISED | Populated holdings, outside-universe positions, reductions and closes | Current and retained account evidence has no positions. |
| U42 NOT EXERCISED | Executed approval, invalidation and concurrent-approval scenarios | Per-order approval was not performed. Visible exact-order review and successful pre-approval checks were exercised. |
| U43 NOT EXERCISED | Submit, fills, duplicate submission, Cancel, Replace and completed paper cycle | These require broker mutations expressly excluded from agent UAT. |
| U44 NOT EXERCISED | Unknown-order outcomes, halts, corporate actions and related exceptional states | No authentic qualifying order records; no new fault-injection project. Retained JNLC activity is separately covered above. |
| U45 NOT EXERCISED | Verified deposit/dividend/filled-order accounting | JNLC exists but is unclassified, and fills/dividends are absent. Unknown treatment is not silently promoted into verified accounting. |
| U47 NOT EXERCISED | New queued/running/cancelled research transitions | No new research permitted. Existing completed/failed history and preflight are covered. The two legacy fixture failures are explicitly reported, not counted as passes. |

No hidden installation, subscription or permission prompt is waiting on the user. Beginning a real paper order still requires the user's exact order approval and explicit Submit action. That broker cycle remains unproven until exercised; this report does not certify it from an empty account.

## Operational observation

During isolated archive inspection/restoration, background snapshot GET requests temporarily exceeded their 15-second timeout while the maintenance lock protected extraction/cutover. The restore operation completed successfully, without resubmission or source changes. The UI displayed the successful outcome; the original isolated store and backup were retained. Continuous snapshot responsiveness during maintenance is not claimed. This did not interrupt the production Alpaca connection.

The old connection-refused browser tab was not a browser-policy failure: the service was stopped. Restarting its existing saved command resolved access. No PowerShell policy, credential, account mode or service endpoint was changed.

## Final state and evidence

- Production remains running at http://127.0.0.1:8098/#overview, with Nautilus connected and market-open account observations on 19 October. final-overview.txt/.png, orders-final.txt and final-price-coverage.json record the visible state. Browser console capture contains no warnings or errors.
- All ten saved research runs (one current plus nine historical) match the 18 October backup exactly. No new run IDs/content. All ten optional policy fields remain unset at revision 4, exactly matching the backup.
- Independent final preservation evidence is in remaining-evidence.md, under its final preservation audit: exact run and policy comparisons, the retained ADBE record, and zero approvals/commands. These are source-record comparisons in addition to the browser observations.
- One new labelled local UAT record remains: ADBE proposal 5bd1161e-c109-4b45-9011-68dacad26274, rejected revision 2, rationale “UAT October19 keyboard-only draft; no approval or order.” Seven proposals total; none approved or submitted. Zero approvals, commands or revocations. Existing historical draft remains separate from broker orders.
- Index/model configuration retained. Filters cleared, selection zero, viewport reset, investor note restored blank without saving a change; no new watchlist/alert/policy. Temporary settings import discarded. Existing labelled 18 October UAT history remains documented in the prior report.
- Isolated restore had no usable credentials/native executable and never connected to the broker. Its owned server on 8099 was stopped after comparison, and its browser tab was closed. Production service and engine were left running.
- Backup used: tradingagents-backup (7).zip, SHA-256 1b0fe50a6ec48e89cd254556219471e297bf92f2e9f54c6f60ff41d9b384212f. restore-security.md and isolated-restore-security/ui-after.json contain comparison details.

See case-results.json for the complete 49-case ledger, fresh versus retained evidence and exact file references; remaining-evidence.md for source/account preservation review; independent-review.md for independent sign-off.

## Sources

- C:/src/printerv2/evidence/tradingagents-build-roadmap.md — corrected approved requirements, A1–A17 and current user corrections.
- C:/src/printerv2/evidence/uat-20261018/uat-plan.md — original 49-case UAT acceptance and explicit action boundaries.
- C:/src/printerv2/evidence/uat-remediation-20261018/uat-report.md — retained 18 October remediation results.
- memory://thinking/sequential/2026/10/18/session-1792356103370-49563 — prior UAT handoff used by the completion plan.
