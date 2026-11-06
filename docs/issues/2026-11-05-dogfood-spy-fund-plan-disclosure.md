# Dogfood: make SPY fund-plan editing deliberate

Current status: **the scoped fund-plan presentation and corrected disclosure-focus
paths are accepted at a real 1920 × 1080 viewport**. The follow-through below
preserves the earlier failed round and its correction. This is not acceptance of
the full SPY shipping journey, broker execution or SPY return parity. No paper
trades were authorized or performed.

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
as an unrelated side effect.

## One real affected round at1920 ×1080

Source revision `cfb7493`, app blob `cdbe5dca2f044e30b8f3aba16878262806ef5da5`.
A pane resize cleared emulation during setup; it was reset to1920 ×1080 before
observations. The first cached view was not acceptance evidence. A real reload
loaded the committed source; no dogfood URL parameter or alternate UI was used.

Observed:

- Collapsed fund plan height172.06px; Preview at424.63–460.63px, inside the1080px
  viewport. Editor and full-budget disclosures started closed. No horizontal
  page overflow. Main labels showed Planning only / No saved plan and Trading
  Rules only, reserve$0 and SPY budget$100,000 from the actual observed paper state.
- Native pointer/Enter opened, closed and reopened the editor; Tab entered Plan
  status. All four authored terms remained blank and status inactive. Save stayed
  disabled. Open editor and field focus persisted while snapshot advanced from
  07:38:53 to07:39:24. No terms were invented or saved.
- The budget disclosure exposed all ten original rows. Unknown authored terms
  stayed Unavailable; the actual rule floor, required reserve, cash, shortfall,
  cash above reserve and SPY sleeve stayed available as before.
- Portfolio's Open account fund plan selected SPY Rebalance and opened the editor.
  **Failure:** on the later observation, focus was BODY rather than the editor
  summary. A prior keyboard close attempt on the other ID-less summary also did
  not reliably persist its intended action through polling.
- No console errors. Automatic trading remained off; no Preview generation,
  approval, submission, authority change, provider job, research or simulation.

Overall round: **not accepted**, because disclosure-heading focus was lost.
Do not turn the passing layout/field observations into full workflow acceptance.

Raw after captures (ignored): `spy-fund-plan-disclosure-after-1080p.jpg` and
`spy-fund-plan-editor-after-1080p.jpg` under `.local-workspace/dogfood-20261105/`.
The collapsed image has no visible account identifier or credential; expanded
account-detail evidence stays private/ignored. Existing README preview image
still illustrates the unchanged view-only stock lookup, not this new focus path.

## Coordinated focus correction

The common render restores focus by element ID, plus specific ID-less links and
action buttons; it does not restore an ID-less SUMMARY. Added stable unique IDs
to both new summary controls so the existing path can restore them. No new focus
manager, event dispatch, timer, backend or authority change.

Fresh source review `wf_676d928b-ad3` found no actionable defect in the two-ID
correction, confirmed unique IDs and restoration-before-focus ordering, and
reviewed app blob `5e9b27533a4498f94af9b65629556c4c5b8114c3` against `cfb7493`.
Primary accepts the source correction, not runtime acceptance. No second smoke was
run under the then-current reapproval rule. The human has since deleted that rule:
the remaining native disclosure focus/toggle and Portfolio-entry check is covered
by existing development authorization. Continue at 1920 × 1080 with real retained
inputs and no save/trade action; no approval prompt is required.

## SPY-first direction persisted before closing this iteration

The human explicitly reprioritized the loop to a personal index-management desk:
SPY replication is the first shipping priority and daily reason to open the app.
The complete account/reserves → budget/dated holdings → rebalance → specifically
authorized execution → reconciliation/exceptions journey takes precedence over
supporting research, charts, simulations or general tool parity. Other work must
directly block that journey. Real1080p or larger only; a working rebalance is not
SPY return-parity evidence. No paper trades were authorized.

As requested, this focus was updated **first**: `93fd8bb` commits `PRODUCT.md` and
the canonical loop brief before iteration closeout. The future wakeup carries this
intent. Its earlier failed-smoke approval gate was explicitly removed by the human;
failed local checks are corrected and rechecked without redundant approval prompts.
Durable fund-purpose memory was updated in place, preserving reserve/liquidity
requirements.
Navigation must become an obvious primary daily workspace; this disclosure patch
does not claim that larger navigation change is already delivered or release-ready.

At the prior closeout, source was corrected and independently reviewed, but the
live focus confirmation and new guide image were still pending. The later
operating-rule correction removed the redundant approval gate; it did not convert
the earlier failed observations into passes.

## Completed focused verification — 5 November 2026

Baseline `7df8b5b`, clean `nautilus`; unchanged reviewed app blob
`5e9b27533a4498f94af9b65629556c4c5b8114c3`. Resumed the affected failed paths under
existing authorization, without repeating the earlier passing layout/budget cycle.
The actual browser viewport was inspected as **1920 × 1080** at each focus case.
The normal `http://127.0.0.1:8099/#orders` and `#portfolio` routes were used.

| Affected path | Observed normal updates | Result |
| --- | --- | --- |
| Editor summary | Snapshot 08:01:00 → 08:01:32 | `fund-plan-editor-toggle` remained the active SUMMARY; the original node was disconnected and the replacement focused. Editor stayed open; native Enter closed it. |
| Budget summary | Snapshot 08:01:32 → 08:02:34 | `fund-plan-budget-toggle` remained the active SUMMARY after node replacement. Budget stayed open; native Enter closed it, with both disclosures then closed. |
| Portfolio → Open account fund plan | Snapshot 08:04:07 → 08:04:37 | Selected SPY Rebalance, opened the editor and focused its summary despite the remembered closed state. Focus survived replacement; native Enter still closed it. Budget stayed closed. |

All four authored terms stayed blank, status stayed inactive and Save stayed
disabled. Automatic trading remained off; no plan save, Preview generation, order
approval/submission/cancel/replace, authority change, research/model/simulation job,
automated test, mock, build, credential/private configuration or production action.
Console inspection returned no errors. No application code changed in this
follow-through.

The pane was off-screen and could not be fronted because the session was not open
in a window. Primary requested visibility without blocking the work, inspected the
actual rendered browser through tools and saved screenshots. This is tool-observed
functional/rendered evidence, not a claim of human-witnessed foreground UAT or a
timing/performance benchmark. Snapshot advances prove intervening normal renders;
no page events, records, clocks or data were fabricated.

A coordinate-action batch for the Portfolio entry was refused before execution.
A safer named-control attempt had a stale reference. A fresh screenshot followed
by the ordinary standalone native click opened the actual navigation button. No
connected-app write, broker action or permission bypass was performed.

## Guide image and closeout

- Raw full capture: `.local-workspace/dogfood-20261105/spy-fund-plan-focus-corrected-after-1080p.jpg`.
- Raw native Browser region capture: `spy-fund-plan-focus-corrected-detail-1080p.png`
  in that same ignored folder. Region (90, 42)–(796, 195) of the rendered 800 × 450
  pane capture; the page viewport remained 1920 × 1080.
- Promoted unchanged to `docs/images/spy-fund-plan.png` (706 × 153), Git blob
  `63b4ea0fd402daa36fe3b75bf0acae73396b23bb`, matching the raw file byte-for-byte.
  No visible identifier, credential, private note or unrelated desktop content.
  PNG chunks are IHDR/IDAT/IEND only; the selected full JPEG had no EXIF/XMP block.
  No financial value or status was repainted.
- README includes the real detail image and image notes explain its viewport,
  capture framing, revision, dated figures and authority-state limits.
- The operating reference now records the observed focus correction. Its changed
  installed copy is synchronized separately with an overwrite guard.

Primary acceptance: **complete for this discrete fund-plan presentation and
native-summary focus item**. The failed round remains recorded above. Active-plan
save/error/shortfall and account-switch cases were not exercised by this focused
follow-through; their source review is not runtime acceptance. The broader primary
daily workspace, complete SPY execution/reconciliation journey and return-parity
measurement are not accepted by this item. No paper trades are authorized.

Fresh final evidence/privacy review `wf_904a70a8-145` completed against `7df8b5b`
and this documentation/image diff, with the app blob unchanged. It found no
actionable defect, confirmed the failed history and bounded acceptance, and
visually inspected both new captures without finding visible identifiers, secrets,
private notes or misleading framing. It did not independently rerun the browser
or metadata checks; the live results above are primary observations.

Primary final decision: accept this discrete item. The changed tracked/installed
operating reference matches byte-for-byte; unrelated installed files were untouched.
All 21 checked local documentation/image targets resolve and whitespace checks
passed. This completion batch adds **zero application-code lines and zero tests**.
Raw captures remain ignored; only the reviewed guide PNG is promoted. Delivery is
local on `nautilus`, with no push or production release.

Reusable lesson:
`memory://knowledge/projects/tradingagents/tradingagents-disclosure-summaries-need-their-own-stable-focus-ids`.
The SPY-first loop can move to its next discrete in-journey item; this record does
not claim overall release readiness or authorize any paper trade.
