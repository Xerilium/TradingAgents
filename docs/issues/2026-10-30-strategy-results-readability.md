# Completed Strategy Lab results are hard to read

Status: Source review and mechanical layout scan passed; installed verification pending
Owner: Codex subagent `strategy_layout`
Coordinator: Codex parent
Reported: 30 October 2026

## Real reproduction

Open completed experiment `d2a35c96-21a3-47e5-919a-f09081fd3742` in
**Strategy Lab > Walk-Forward Experiments > Preview & Results**. The user
reported that tables, numbers and explanatory text run together and the
layout is hard to understand. The coordinator reproduced that view in the
built-in browser. The comparison table contains ten columns, long internal
labels and repeated technical values, with computed header and cell padding
of only 1px. It occupies 865px within a 1522px results pane. Diagnostic counts,
all training/validation/later-test rows and technical prose compete before
the chart and the main result is not clearly identified.

Screenshot: `C:/src/printer/.local/strategy-results-readability-before-20261030.jpg`.
The existing result is complete and independently verified. No rerun is
needed to reproduce or verify this presentation issue.

## Documentation and scope

Review `PRODUCT.md`, `DESIGN.md`, the Strategy Lab sections in the platform
reference and user guide, and Impeccable Operate/layout/craft guidance before
changing the UI. Keep the existing visual system, source contracts and full-width
Setup/Results/Runs views. This issue changes presentation only.

## Acceptance

- Make the result for each later-test period clear, with plain labels and
  properly separated, aligned table columns.
- Group explanatory text with the information it explains. Move technical
  identifiers and detailed calculations out of the primary reading path while
  keeping the complete data inspectable.
- Preserve exact source metrics, missing/failed/unselected states, independent
  periods and scenarios. Do not invent or aggregate returns.
- Reopen the same completed result and verify its presentation and unchanged
  result identity. No new experiment, research run or broker action.
- Fresh independent review before installation; verify the rendered result.

Baseline: installed `68a10e19cd553249c912846254973184185ddd9c`; source `654d4c4`
also contains the separately reviewed empty-reasons message correction, not
yet installed. Batch that correction with this presentation update.

## Assessment and implementation

The screenshot and source show two separate causes: the generic experiment
table lacked the shared table class and scoped spacing, and the first reading
path was a dump of internal counts and all three evaluation stages. Widening
the pane alone did not make the result understandable.

The result now starts with **Results for each test period** and one row for
each saved period/scenario. Each row presents its genuine saved date window,
simulated USD gain/loss, return, worst fall, closed trades and explicit status.
Requested periods/scenarios with no saved result remain visible as unavailable;
unselected and failed periods retain their recorded reasons. No totals or
combined return are calculated. Display rounding keeps exact source values in
tooltips and the complete saved evidence.

The existing chart follows the main table with readable period/scenario
labels. **Training, validation and detailed reports** retains the original
counts, reasons, complete comparison, native reports, trials, qualifications
and full result data. Existing event controls remain separately inspectable.
The prior empty-reasons suppression is unchanged.
All experiment tables now have scoped padding, separators, left-aligned labels
and right-aligned numeric cells, with wrapping text and horizontal scrolling
when the available width requires it. Existing colors, fonts, full-width tabs,
Run gates and backend calculations are preserved.

The relevant platform/local-guide documentation and Impeccable layout,
Operate and craft-floor guidance were reviewed before editing. Source syntax
and whitespace checks are separate from the pending rendered verification.
No experiment or research rerun is part of this change.

## Source review and release checks

The coordinator reported independent approval from `strategy_results_review`,
with no evidenced material blocker. The reviewed application assets are:

- `app.js`: SHA-256 `3d433e5c192fd8c4adff4661e2d9a5a01db40e6abdc966acb116f63cdb70a4a0`.
- `ui-research-journal.css`: SHA-256 `9910358d870847e35247ed43422389c390b10b1647be5fb556fec7da9b31acf8`.

The release worker ran the cached Impeccable 0.1.17 command `detect --json
--scope layout` on both assets on 30 October 2026. It returned exit 0 and an
empty findings list (`[]`). The prior worker's JavaScript syntax and whitespace
checks had passed; those checks were not repeated for unchanged application
source. This mechanical scan is not evidence of rendered acceptance.

The app-only package is staged under
`packaging/build/strategy-results-readability-20261030`. Installation and
inspection of the same completed experiment remain pending. No new experiment,
research run or broker action is authorized by these release checks.
