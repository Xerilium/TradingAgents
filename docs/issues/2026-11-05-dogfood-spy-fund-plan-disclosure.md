# Dogfood: make SPY fund-plan editing deliberate

## Observation and scope

Baseline `2dd6907`, clean `nautilus`, normal development desk on 8099. The human
made the Browser pane visible before this pass resumed. Initial inspection used
1024 × 768. The human then explicitly limited all design and visual UAT to
**1920 × 1080 or higher** and asked to fix the actual UI size, not optimize a fake
scenario. No smaller-layout verification is part of acceptance.

Primary set and inspected the real browser viewport at **1920 × 1080**, preserved
the draft, temporarily restored only its own two source files to the committed
baseline, reloaded the actual app and opened SPY Rebalance. The original fund-plan
section was **1242.61 px** tall (top167.78, bottom1410.39); Preview was at
**1495.17–1531.17 px**, below the1080px viewport. This confirms the presentation
friction at the supported minimum, not just in the smaller pane. No sizing or
execution failure is established. The draft was reapplied without its now-unneeded
smaller-layout CSS override; `ui-orders.css` has no diff.

Supported-size raw baseline (ignored):
`.local-workspace/dogfood-20261105/spy-fund-plan-disclosure-before-1080p.jpg`.
The earlier smaller-pane capture is retained as historical setup evidence only.
Both contain account identifiers and must not be promoted into guide images.
`PRODUCT.md` and the canonical loop brief now record the1080p minimum; durable
lesson: `memory://knowledge/projects/tradingagents/tradingagents-ui-targets-1080p-or-higher-only`.

One item: make fund-plan editing a deliberate disclosure, while keeping saved
reserve/budget context and material blockers visible. Preserve all fields, full
budget evidence, unknown values, account/generation/revision binding, unsaved
changes, explicit fund-plan navigation/focus, save/reload behavior and separate
trading authority. No backend or sizing changes.

## Plan

- Source/interaction advice through read-only workflow `wf_54aa72eb-09f`.
- Use installed Impeccable in Operate/distill mode; primary context already loaded
  in this session. Read craft floor immediately before UI edits.
- Primary implements one small presentation batch; fresh independent scrutiny
  precedes one affected real-browser smoke.
- Update affected operating skill/product docs, save useful real evidence and
  commit locally on `nautilus`. No push, app build or production operation.

No reserve terms will be invented or saved. No Preview generation, provider jobs,
research/simulation run, broker approval/submission/cancel/replace, authority
change, credential/private configuration read, automated tests or mocks.

## Research and decision

[Fidelity's Trader+ Web guide](https://www.fidelity.com/learning-center/trading-investing/trading-platforms/how-to-use-trader-plus-web/)
(accessed 5 November 2026) documents expanding Positions with a navigation arrow
and resizing tool panels. It does not document this reserve feature or this exact
disclosure design. Adapted principle: keep review information in view, reveal
editing/detail controls deliberately; no parity or broker-capability claim.

Source advice completed in `wf_54aa72eb-09f`: retain visible saved reserve/sleeve,
shortfall, spendable error, dirty/conflict/save status; use native disclosures with
stable IDs; open the editor after render/restoration on explicit Portfolio entry.
The first draft included a scoped field-grid override for the initial small pane.
It was removed after the human clarified the1080p minimum; existing desktop form
layout is sufficient and no CSS changes remain.

Implementation: a compact saved-budget summary; separate **Edit account fund plan**
and **Saved budget and account details** disclosures; all existing fields, full
budget rows and evidence remain. Dirty state, conflict, positive shortfall, missing
budget and spendable-cash errors remain outside the disclosures. The Portfolio
route opens/focuses the editor after render. Save/reload/sizing/authority handlers
are unchanged. No new UI state store or backend change.

## Review and evidence

Fresh independent source review `wf_a30c1698-13f` reviewed app blob
`435817c92a471941e2bdd838f2993479b05ba459` and found two copy defects:

1. An active plan could say Reserve applied while its budget was unavailable.
2. A budget without an active saved plan was attributed to saved plan terms.

Corrected the label to use a valid active budget, otherwise Reserve needs attention
for an active saved plan, and labeled budget origin **Saved plan and Trading Rules**
or **Trading Rules only**. Narrow independent verification `wf_535e1957-2a0`
confirmed both resolved with no remaining concrete defect in that scope. Final
reviewed app blob: `cdbe5dca2f044e30b8f3aba16878262806ef5da5`.

Primary source decision: accept for one affected real1080p smoke. Syntax and
whitespace passed; code delta9 added/4 removed JavaScript lines, zero CSS/backend
or test changes. The CSS hook had no deterministic quality finding on the removed
CSS draft; it also noted a pre-existing stale design sidecar, which was not repaired
as an unrelated side effect. Runtime acceptance remains pending.
