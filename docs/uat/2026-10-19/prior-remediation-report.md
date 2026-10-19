# TradingAgents UAT remediation and rerun — 18 October 2026

## Result

**All five reproduced defects are remediated. Browser rerun: 36 PASS, 0 FAIL, 5 PARTIAL, 8 NOT EXERCISED across the same 49-case plan.** This clears the exercised no-trade UAT scope; it does not claim that unexecuted approval, broker order/fill or populated-account paths have passed.

The first UAT had32 PASS,4 FAIL,5 PARTIAL,8 NOT EXERCISED. This rerun retested those four fixes and found one further historical-review persistence defect inside existing case U15; it was fixed and retested before completion. The approved feature scope was not expanded.

## Remediation tied to requirements

| Finding | Requirement | Change | Browser evidence |
|---|---|---|---|
| F1/U19: research preflight lost Universe selection | A2/A3, research controls | Universe/research share the configured-symbol selection set | Exact two-stock and single-stock preflights; clear disables Run; both dismissed without starting |
| F2/U49: old preview could describe edited terms | A5/A14 | Bind asynchronous proposal/basket results to submitted form identity and values; invalidate stale impact on edit | Quantity, limit price, stock switch and basket target edits discard stale responses; new preview matches exact terms |
| F3/U17: retained histories used exhausted calendar metadata | A4/G1 | Reuse compatible retained hash-checked Alpaca calendar; retain per-stock bar/provenance/session checks across coverage/detail/approval/correlation consumers |503 complete history records,0 missing; MSFT/ADBE old caches inspectable; no new history collection or research |
| F4/U36: malformed ZIP misleading error | A13 | Handle invalid/damaged ZIP as actionable validation error | Invalid backup upload reports invalid/damaged ZIP; no restore |
| F5/U15: historical review validated against latest run only | A3 | Resolve requested completed saved run/symbol/exact revision for existing review validation | Historic AAPL run61072a19 revision17 note/disposition saved and survives full browser reload; no source report changed |

Seven product files changed: app.js, history_coverage.py, market_history.py, approval_review.py, policy_evaluation.py, server.py, service.py. **80 authored lines,48 removed,net32; score−80; zero new test files or dependencies.** These are remediation deltas against the preserved pre-fix source snapshot, not a claim about unrelated existing repository changes. See changed-source-hashes.json. No broker transport/approval capability was disabled.

## What works in this rerun

Actual browser UAT covered503-stock prices/search/sorting/filtering/import/export, shared research selections, watchlists/preferences across reload and another browser tab, immutable reports/charts and current cached history, investor notes, exact proposal/basket previews, local save/revise/defer/reject history, optional policy behavior, actual timestamp-based alert triggering/acknowledgment/pause, journal notes, saved reporting, read-only exports, account pause/resume and Nautilus stop/reconnect, backup creation and restore inspection.

Final browser: Nautilus1.231.0 connected and reconciled to the existing Alpaca paper account; cash/equity/buying power each$100,000;0 positions,0 open broker orders; all503 configured latest IEX prices present. The regular market is closed: latest price events are from16 October, not new18 October trades. Price age is visible; freshness limits remain unset.503 historical coverage is separate from503 latest prices. Existing saved research remains unchanged.

## Limits and observations

- Five partial cases remain: U14 numeric claim/supporting-source gaps are disclosed; U18 exact scroll/text-selection preservation not exhaustive; U27 basket arithmetic is observed but actual pending-order and sale-funding conditions are absent; U32 actual cashflows/fills and benchmark comparison are absent; U38 full accessibility/other-device coverage is not claimed.
- U41–U48 were not exercised: populated holdings, exact approval execution, Submit/Cancel/Replace/fill lifecycle, rare broker/external/failure states, nonempty cashflow accounting, actual restore, new research job lifecycle and attack/OS-permission tests. These remain coverage limits, not passes or newly invented product features.
- During backup creation the UI temporarily showed account observation OperationalError/timeout while saved records remained accessible. The archive completed and later Orders showed connected, in-sync and unpaused before the final restart. No data loss observed; continuous account-monitor availability during backup is **not** established. Evidence: launch-diagnostics.txt, valid-backup-preview.txt, orders-ready.txt.
- A historical review retains its separate advisory that history provenance changed or was not bound. Saving the review now works; that does not certify all source warnings resolved.
- Activity/holdings exports use conservative unavailable wording on the genuinely empty account. Independent source comparison established there were zero corresponding records; no filled-account export precision is claimed.
- No new agent research, approval, Submit, Cancel, Replace or trade was performed. No actual restore, installation, PowerShell-policy or global system change occurred. The app remains fully capable of its existing explicit per-order workflow.

## Artifacts and retained UAT records

The fresh backup is C:/Users/brett/Downloads/tradingagents-backup (7).zip,30,766,330bytes,SHA2561b0fe50a6ec48e89cd254556219471e297bf92f2e9f54c6f60ff41d9b384212f. Independent artifact review passed all12 checks including3611 ZIP entries/3610 manifest payloads, CRC/hash/length/member-set/database integrity, exact503 index membership, matching exports and absence of the five configured secret values. This is a bounded comparison, not an exhaustive security audit. See artifact-validation.md and downloads.json.

Retained labelled local records: rejected MSFT proposal f48b55e6-ac35-408f-8363-4304396ec3dd revision4; rejected basket c69b2e02-4551-461f-b9d7-ea448985b1bb revision3 and its two rejected legs; its MSFT journal note; historical AAPL review on run61072a19 revision17; acknowledged/paused alert87c8de40-d32d-4b0c-9c0c-97587626db0d; empty watchlist3ddab3f0-c21a-4e09-87f4-4d7ad8a653f5 (UI has no list deletion). Prior UAT records remain. Optional policy fields restored unset, investor note restored blank, index/models unchanged, selection cleared, baseline columns/filters restored, new orders unpaused. Configuration/policy revisions incremented because UAT exercised save/restore; no trading authority created.

## Case results

| Case | Result | Observed result / boundary |
|---|---|---|
| U01 | PASS | All five primary routes rendered with shared paper account context; no inaccessible destination. |
| U02 | PASS | Connected Alpaca paper account shows100000cash/equity/buying power and0positions/0orders after reconnect. |
| U03 | PASS | All503 configured rows have numeric latest dated IEX prices; closed-market session disclosed. |
| U04 | PASS | Adobe/MSFT searches match correct stocks; no-match text and clear return503 rows. |
| U05 | PASS | All503numeric Price/Change% rows ascend correctly; saved-research plus minimum2%movement returnsMETA. |
| U06 | PASS | Created labelled2-member list, removed/readded MSFT, verified persistence, then emptied list; named emptyUAT list retained. |
| U07 | PASS | Hide age/reorder Change% persisted on reload and second tab. Defaults restored. |
| U08 | PASS | Mixed CSV identifies2accepted,2rejected,1duplicate; both Merge and Replace choices visible. Replace affects draft only; discard restored503; full503accepted. Merge application was not separately exercised. |
| U09 | PASS | Full503 index imported, saved, reloaded and exported through UI; configured models retained. |
| U10 | PASS | Second actual tab read the saved2-member watchlist and changed columns; no concurrent approval attempted. |
| U11 | PASS | Full-account holdings and outside-universe filter show honest zero positions and explicit funds/totals. Export coveredU34. |
| U12 | PASS | Latest/older reports readable; older AAPL run61072a19revision17 retained through human-proposal transition. |
| U13 | PASS | Saved AAPL dated OHLCV/priorclose/movement/recordedindicators and1Mdate dropdown work; adjustment unknown disclosed. Chart hover not exercised. |
| U14 | PARTIAL | Saved thesis, contrary views and unresolved numeric mapping readable; existing MSFT news has source dates/links. Absent supplementary categories remain explicit. |
| U15 | PASS | Investor note persisted then restored blank. Historical AAPL run61072a19 revision17 now saves needs_review plus labelled note and persists after full browser reload and explicit re-selection; advisory source-review gap remains explicit, does not reject saving. |
| U16 | PASS | MSFT and ADBE legacy caches expose501actual daily bars, dated OHLCV and sufficient current coverage; ADBE range/date controls work. No new agent or history job required. |
| U17 | PASS | Configured capabilities now reports503/503 complete histories and0missing using retained authoritative calendar, without another503-stock data job. Per-stock detail checked below. |
| U18 | PARTIAL | Refresh retained AAPL/run/report/range/date and unsaved note text. Exact scroll and text-selection preservation not comprehensively exercised. |
| U19 | PASS | Shared selection gives exact AAPL/MSFT two-stock preflight; clear disables Run; singleAAPL preflight also opened and dismissed with models/date/usage disclosure. No Start action. |
| U20 | PASS | Explicit AAPL60second quote-age rule triggered from real retained quote timestamp, acknowledged0unread, paused and persisted through app restart. Existing monitor timestamps/gap disclosure visible; continuous downtime coverage not claimed. |
| U21 | PASS | Blank optional rationale/unlinked BUY1MSFT LIMIT100 preview shows principal100/cash99900; quantity2 matching preview also verified. |
| U22 | PASS | MARKET preview uses dated IEX last trade528.99, estimated cash99471.01 and unknown execution price/fees. |
| U23 | PASS | Blank/zero/negative/fractional quantities and negative limit rejected with settled explicit messages; no invalid drafts saved. |
| U24 | PASS | Million-share buy reports negative cash/affordability condition; SELL1against0holdings reports shorting unsupported and excludes sale proceeds from cash. |
| U25 | PASS | MSFT local proposal saved1 share, revised2, deferred and rejected; final revision4 appears in journal with no approval/broker order/fills. |
| U26 | PASS | All policy states initially unset; temporary99.95%cash rule flagged100buy, then was restored unset. Matching basket at policyrevision4 no longer shows reserve violation. |
| U27 | PARTIAL | Quantity basket2AAPL+1MSFT at100 gives99700cash; AAPL-only fill99800/MSFTremaining.1%weight at100gives10shares/99000cash. Working-order conflicts and sale-funded-buy cases not exercised. |
| U28 | PASS | Labelled basket and linked proposals saved/deferred/rejected through revisions1–3 without approval/submission. |
| U29 | PASS | Connected and reconciled account, no approved order, explicit approve then Submit workflow, market-closed notice; actual broker open orders0 and older saved draft1 separate. |
| U30 | PASS | Explicit Pause persisted after browser reload; Resume restored unpaused state and survived final app restart; no orders cancelled. |
| U31 | PASS | Stopped account values became unavailable while saved AAPL report remained readable; Start reconnected same account and503prices. |
| U32 | PARTIAL | Existing completed Oct15–16 interval opens at100000 equity with zero TWR/Dietz/drawdown; methods and timestamps explicit, benchmark unset. No actual flows/fills available to substantiate full accounting. |
| U33 | PASS | Journal lists exact local proposal and basket revisions, honest no-approval/no-fill state; labelled follow-up note persists after reload. |
| U34 | PASS | Fresh UI downloads for holdings/activity/performance/selected decision and503index parsed and independently matched source records; known-empty holdings/activity rows retain conservative unavailable wording. |
| U35 | PASS | Created and downloaded consistent backup, then inspected exact archive in restore preview (3610files and savedhistory). No restore applied. Temporary account-observation OperationalError during backup recovered to connected/reconciled without restart; recorded as operational observation. Artifact integrity reviewed separately. |
| U36 | PASS | Malformed ZIP rejected with actionable invalid/damaged backup archive message; active workspace unchanged. |
| U37 | PASS | Diagnostics downloaded and independently checked for credential values; connected/reconciled100k0positions0orders,503history coverage and existing launch guidance inspectable. |
| U38 | PARTIAL | Actual desktop browser workflow exercised with keyboard navigation, search, selections, form edits and revision actions; full accessibility and other viewport/device coverage not performed. |
| U39 | PASS | All direct navigation and reload actions completed; no captured browser warning/error entries at final inspection. Temporary account observation OperationalError during backup recovered and is reported separately. |
| U40 | PASS | Final503-stock configuration retained, baseline filters/columns restored, selection cleared, notes restored blank except labelled historical review/journal records; temporary rule paused, policies unset, orders unpaused. Nautilus connected100k/0positions/0orders. No research or broker mutations. Exactly7 authorized product files changed (+80/-48), no new tests. |
| U41 | NOT EXERCISED | Actual account has no populated holdings or outside-universe positions; none manufactured. |
| U42 | NOT EXERCISED | Per-order approval execution, expiry and concurrent approval were not authorized; visible controls inspected only. |
| U43 | NOT EXERCISED | Submit, duplicate submission, fills, Cancel, Replace and the paper trade cycle require prohibited broker writes. |
| U44 | NOT EXERCISED | No actual unknown outcome, halt, corporate action or external activity record available; no fault injection. |
| U45 | NOT EXERCISED | No actual deposit/dividend/filled-order records; flat-account reporting cannot establish full accounting. |
| U46 | NOT EXERCISED | Archive inspection performed; actual restoration of active records not performed. |
| U47 | NOT EXERCISED | No new research runs; queued/running/cancelled transitions not exercised. |
| U48 | NOT EXERCISED | Current attack testing/cross-origin mutation and OS credential-permission assessment outside UI UAT scope. |
| U49 | PASS | Quantity and price edits discard obsolete previews; fresh previews match BUY2MSFT/200 and BUY1ADBE LIMIT101/101. Switching to AAPL leaves its blank independent form without ADBE impact. |

Machine-readable observations, timestamps and evidence paths: case-results.json. Plan: uat-plan.md. Original baseline: ../uat-20261018/uat-report.md. Final screenshot: final-overview.png.

## Independent sign-off

Independent reviewer cleared the five fixes and exercised no-trade UAT delivery after reconciling all46 baseline sources,7 changed files,+80/-48 lines, final hashes,49-case counts and cited evidence. The separate artifact review passed12checks. See independent-review.md and artifact-validation.md.

Reviewer limit: U08 demonstrated import validation and Replace-draft/discard; Merge was visible but its application was not separately exercised. Existing partial/untested, backup-time observation and research-advisory limits remain. This is scoped remediation sign-off, not whole-product trading acceptance.
