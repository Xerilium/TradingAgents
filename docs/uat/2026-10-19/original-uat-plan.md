# TradingAgents product UAT plan

Version 1.2 · 18 October 2026 · Operator: Codex, at Brett's request

## Objective and limits

Evaluate the frozen product as an investor using its actual browser UI at http://127.0.0.1:8098. Report what works, what fails, and what cannot be exercised. This plan is written before execution. Extend it when another existing feature or missing acceptance case is discovered; do not add product features or silently narrow expected behavior.

Authority: corrected `C:/src/printerv2/evidence/tradingagents-build-roadmap.md`, especially required workspace, evidence contract, A1–A17 and current user corrections. The current user authorizes UAT planning/execution and a report; prior prohibitions on new research runs, exact per-order approval and broker mutations remain. No Submit, Cancel, Replace, Approve, research Start, or live-account changes. No product edits, installs, migrations, new automated test code or fault framework. Test local reversible preferences and unapproved records through the UI only; retain ordinary audit history. No restore of the user's actual database.

The baseline account is expected to have zero positions/orders. Verify rather than assume. Cases needing holdings/fills/working orders cannot pass from empty-state evidence. Source review and earlier evidence remain supplemental, never a substitute for exercised UAT.

## Result vocabulary

- PASS: the stated expected behavior was exercised and observed.
- FAIL: observed behavior contradicts the requirement; record exact reproduction and evidence.
- PARTIAL: some explicitly listed subchecks passed, while others failed or were not exercised.
- NOT EXERCISED: prohibited action or unavailable prerequisite; state the reason. This alone is not a product defect.
- NOT APPLICABLE: demonstrably outside declared product scope, with a specification citation.

Each result records case ID, action, observed result, evidence path, date/build and severity where applicable. Severity: P0 unauthorized trade/data loss/credential exposure; P1 blocks a core investor workflow or materially misstates funds/orders; P2 incorrect or obstructive secondary behavior; P3 presentation issue. A discovered missing required feature is FAIL, not NOT EXERCISED. A known source-only clearance is not UAT PASS.

## Evidence and state handling

Use the existing visible browser, one operator, screenshots and rendered DOM evidence. Record app/source fingerprint, native version, account mode, universe N/version, browser/viewport, market session and observation times. Keep screenshots free of credentials. Public quote/history requests are allowed; they are not research-agent runs. No secret values are read into reports.

Create a consistent application backup through Settings before persistence cases, if available. Label UAT-only records `UAT 2026-10-18`. Record baseline preferences and restore them through existing UI. Import validation uses a tiny local CSV plus the exported current index; preview invalid/duplicate rows without replacing the 503-stock universe. Named lists have no known delete/rename UI; any UAT list must be reported explicitly. Save/reject proposals/baskets only if required to exercise their record workflow, and report retained audit records. Never delete user research or alter saved research text. No terminal/API workaround may count as an investor workflow pass.

## Planned cases

| ID | Requirement | User action | Expected result |
|---|---|---|---|
| U01 | A14; required workspace | Open all primary destinations; inspect labels/account context | Pages render, selected account/mode remain clear, no unexplained errors or inaccessible required destination |
| U02 | A1/G1 | Inspect account identity, cash/equity/buying power, holdings/order counts and refresh | Sourced values/times and reconciliation state; unavailable is not zero; no invented funds |
| U03 | A2 | Inspect full universe and per-symbol latest prices | N≥500, all configured rows accounted for; latest source/time/session and genuine gaps explicit |
| U04 | A2/A14 | Search by non-demo ticker/company, no-match query, clear | Correct subsets and useful empty state; full universe restored |
| U05 | A2 | Sort symbol/price/change; combine research/movement filters | Correct ordering/membership; reason/count reflect filters; no new jobs |
| U06 | A2 | Select multiple stocks; create labelled watchlist; add/remove members | Exact membership and counts; app persistence across navigation/reload; record cleanup limitation |
| U07 | A2 | Hide/reorder columns, reload, restore baseline | Visible order/preferences persist and can be restored without losing selected symbol/list |
| U08 | A2 | Export current index; inspect import preview with valid/duplicate/malformed rows | Per-row accept/reject/deduplication; explicit merge/replace; no silent prior-universe deletion |
| U09 | A2 | Import exported 503-symbol index using unchanged membership; reload | Correct 503-symbol membership retained, saved configuration persists; no research triggered |
| U10 | A14; sync contract | Open second browser tab; change harmless saved preference/list membership; return/reload | Server-owned saved state is consistent; no accidental overwrite; restore baseline |
| U11 | A1 | Open Holdings and its filters/export with current account | Honest empty state if none; totals/scope explicit, no invented positions or cost basis |
| U12 | A3 | Open researched stock, switch reports/runs, inspect source/time | Exact saved run/revision and historical inputs preserved; current market context distinct |
| U13 | A3 | Inspect saved OHLC/volume chart, dated bar, range and recorded indicators | Values, dates, parameters/source and unknown adjustment basis inspectable; no fabricated indicator |
| U14 | A3 | Read thesis, counterargument, unknowns and numeric-claim evidence | Contrary views and traceable inputs available; agent claims distinguished from measured facts |
| U15 | A3 | Save labelled human note/review disposition; navigate/reload | Note/disposition persists without modifying saved report; restore editable baseline where possible |
| U16 | A4/evidence contract | Open two supported unresearched stocks with on-demand current history | Real inspectable daily OHLC/volume, 252 completed sessions or stated shorter history; no research run |
| U17 | A4/G1 | Inspect full-universe history coverage/manifest | All configured supported symbols accounted for with history eligibility/availability/gaps; 503 prices do not substitute |
| U18 | A3/A14 | Open stock from filtered list, change report/range, refresh then return | Selected stock, open review, typed text, scroll/context retained where required |
| U19 | Research controls | Open single/multiple-symbol research workload review, then dismiss | Symbols/models/date/known usage/cost estimate or explicit unavailable shown before Start; no run starts |
| U20 | A15a/b | Inspect attention/alerts, monitoring state, evidence and acknowledgment | Active/paused/last check/downtime disclosed; existing alert acknowledgment persists if present; no fabricated alert |
| U21 | A5 | Human BUY LIMIT preview without linked research; change quantity | Exact terms/account, optional human note, limit-bound cost/cash/exposure recompute; unknown fees disclosed; no invented prose prerequisite |
| U22 | A5 | Human BUY MARKET preview | Dated actual price basis/estimated cost, no guaranteed fill or mandatory fee/timeout questionnaire |
| U23 | A5/A7 | Preview empty/zero/negative/fractional quantity, invalid limit and unsupported terms | Actionable validation; no rounding into valid order; no saved executable residue |
| U24 | A5/A6 | Preview unaffordable buy; SELL without holdings; zero/invalid symbols if UI permits | Actual funds/holdings/instrument checks fail affected operation; unrelated views stay usable |
| U25 | A5/A7 | Save clearly labelled unapproved proposal; inspect, revise, defer/reject | Exact persisted terms/history, no automatic approval/submission; rejected/deferred remains non-executable |
| U26 | A5 | Inspect optional policy fields/readiness with unset rules | Unset clearly distinguished from enabled limits; no invented defaults or account-wide prerequisite |
| U27 | A6 | Preview labelled target basket/partial-completion scenario | Current/pending/proposed, gross buy/sell/cash/conflicts visible; expected sells do not fund buys; no execution |
| U28 | A6/A7 | Save/defer/reject labelled basket if UI supports | Versioned targets, exact order identity and review state; no approval/submission; audit record retained |
| U29 | A7/order correction | Inspect Orders readiness and saved draft versus broker blotter | Exact reason for no submission and next action; no account-wide invented block; unknown/not-sent distinct |
| U30 | Pause correction/A14 | Pause new orders, reload, resume to original unpaused state | Explicit choice persists; pause is distinct from approval and never cancels existing orders |
| U31 | A11/A14 | Stop Nautilus; inspect account/research; reconnect through UI | Account unavailable/stale, saved research readable, actionable reconnect; fresh reconciliation restores real values |
| U32 | A12 | Inspect performance/allocation/cashflow/history/method/period views | Sourced metrics and interval, missing history explicit, no false gain from deposit or manufactured realized P&L |
| U33 | A12/A17 | Inspect decision journal; trace saved research/proposal/reject record | Exact origin/revisions/terms/outcome or honest lack of fills; note/reporting fields optional |
| U34 | A12/A14 | Export holdings,activity,performance,journal where provided | Downloaded files correspond to view/scope/source precision; missing export feature reported; no secrets |
| U35 | A13/P9b | Create application backup and inspect archive in restore preview | Backup obtained, contents/times/validation shown; no credentials; no actual restore |
| U36 | A13 | Inspect malformed restore archive without applying | Clear validation error, original saved data unchanged, no silent restore |
| U37 | P9a/P9b | Download diagnostics; inspect health/capabilities/launch instructions | Secret-free actionable health and supported account/order terms; normal operation documented through UI |
| U38 | A14/usability | Keyboard search/select/review/reject; inspect actual desktop layout | Labels/readable controls, visible focus, no required mouse-only dead end or misleading color-only state |
| U39 | A14/sync contract | Navigate direct links, refresh while reading; inspect console errors | Correct destination/context; no blank/stuck page or unhandled browser error |
| U40 | Feature freeze/state | Restore test preferences; inspect final account/order/research state | Original 503-symbol universe/configuration retained, no agent trades or research, retained test records listed, product source unchanged |

## Required but conditionally unexercisable cases

| ID | Requirement | Prerequisite and treatment |
|---|---|---|
| U41 | A1/A5 | Populated holdings, holdings outside the universe, reduction and close. Use existing actual records if present; never manufacture positions. Otherwise NOT EXERCISED. |
| U42 | A7 | Exact approval, changed terms, expiry and concurrent-tab approval. Prior instruction forbids agent per-order approval; inspect visible controls only. No PASS for approval execution. |
| U43 | A8/A10/A16/A17 | Submit, duplicate submission, partial fills, Cancel, Replace, competing commands and the full paper cycle require prohibited broker writes; NOT EXERCISED. |
| U44 | A9/A11 | Unknown outcomes, halts, external activity, corporate actions and provider failure require existing records or retained isolated evidence. No new fault project; NOT EXERCISED if absent. |
| U45 | A12 | Deposit, dividend and filled-order accounting require actual records; no invented data. Empty reporting can be checked, but accounting cannot pass without records. |
| U46 | A13 | Actual restoration of records requires an isolated-copy workflow; do not restore the user's active workspace. Restore preview/validation does not pass full restoration. |
| U47 | Research controls | New queued/running/cancelled job transitions require a prohibited research run; existing completed/failed records and preflight can be tested. |
| U48 | P9a | Cross-origin requests, unauthorized mutations and credential-storage permissions are engineering security checks, beyond UI-only UAT. Record existing evidence separately; do not claim current attack tests. |

## Execution order and completion

Independent plan-review clarifications: U08/U09 record Merge and Replace preview/application separately. U13/U16 also inspect prior close/movement basis, bid/ask/spread, session/timezone/feed and adjustment basis. U14 includes existing news/fundamentals/events provenance or explicit gaps. U26 distinguishes seeing optional unset fields from exercising an actually configured rule; unset-only evidence cannot pass configured enforcement. These add detail to existing cases, not product scope.

First baseline/settings/backup, then universe/import/list persistence; stock/research/evidence; proposals/basket/rejection; reporting/exports/monitoring; connection/pause/keyboard; cleanup/final state. Related cases are executed as batches. Stop a case at a prohibited action, capture the boundary, and continue independent cases. Record all failures for a consolidated report; do not fix product code during UAT. An independent reviewer checks plan coverage and evidence/result claims before the final report. Completion means all feasible cases attempted, every case given an explicit result, defects reproducible, excluded execution boundaries stated honestly, and final workspace condition documented.

## Sources

- Corrected spec: C:/src/printerv2/evidence/tradingagents-build-roadmap.md (read 18 October 2026).
- Previous scoped source/browser clearance: C:/src/printerv2/evidence/rest-app-20261018/independent-review.md and delivery-evidence.md; do not carry these forward as fresh UAT passes.
- Prior handoff: memory://thinking/sequential/2026/10/18/session-1792347372622-43826.

## Extension v1.2 — discovered during execution

| ID | Requirement / existing function | Procedure | Acceptance |
|---|---|---|---|
| U49 | A5/A14: exact human terms and visible portfolio impact | Start an unsaved preview for BUY 1 MSFT LIMIT 100, immediately change quantity to 2 without saving or approving; observe the settled response. | A late response must not present the one-share impact as the current two-share form preview; invalidate it or label it as previous terms. No order action. |

This adds coverage for an existing function, not a feature or fix. Product freeze remains in force.
