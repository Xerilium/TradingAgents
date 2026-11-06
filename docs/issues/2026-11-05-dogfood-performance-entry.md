# Dogfood 1: truthful account-performance entry state

## Status and scope

Completed source fix and one live affected smoke batch on 5 November 2026.
Implementation `265ec22`; baseline `6095882`, `nautilus`,
`D:/src/TradingAgents`; working tree initially clean.
The user requested a self-paced professional-trader dogfood loop: broken behavior,
then jank, friction and missing features. Each iteration delivers one complete
item. Discrete-stock S&P 500 tracking is the core journey; research is supporting.
All delivery remains local. No broker action or authority change is authorized.

## Observed broken behavior

Dashboard and Portfolio showed a verified empty USD paper account with $100,000
cash/equity. On Portfolio → Performance, with no saved interval loaded, five
metric tiles displayed unavailable results, unreported provisional status and
“No readiness reason recorded.” The benchmark tile also claimed “Unsupported
source method for strategy comparison.” Only below those tiles did the page
explain that an interval must be opened.

Source: `static/app.js` `renderPerformance()` unconditionally passed absent
collection metrics to `performanceTile()`. That helper treated missing benchmark
availability as an unsupported method. Missing data is not evidence of an
unsupported calculation, and this false failure obscures the first step toward
an S&P 500 comparison.

## Research and parity boundary

Official sources accessed 5 November 2026:

- [Fidelity performance methodology](https://www.fidelity.com/webcontent/ap002390-mlo-content/19.09/help/learn_performancereporting.shtml):
  account return, cash-flow timing, benchmark comparison and availability are
  distinct. Fidelity's money-weighted account method is not a mandate to replace
  TradingAgents' qualified existing methods. Primary read confirmed this source.
- [Fidelity Active Trader Pro chart help](https://www.fidelity.com/products/atbt/help/ActiveTraderTools_Chart_Help.html):
  research worker reports relative-price comparison with indexes including the
  S&P 500, not proof of account total-return parity.
- [Robinhood Strategies charts](https://robinhood.com/us/en/support/articles/strategies-charts/):
  research worker reports time-weighted managed-account benchmark comparison.
  This does not establish the same feature for ordinary self-directed accounts.

The relevant parity principle is understandable performance prerequisites and
qualified comparisons, not fabricated prices, returns, distributions or account
history. No leader account was accessed. Source capability is not live acceptance.

## Plan

- Render metric tiles only for an opened collection that is not loading or in
  an error state. Preserve actual loaded metric calculations and qualifications.
- Explain loading, no saved intervals and saved-but-unopened intervals honestly.
  Reuse the existing Journal → Account history navigation; clicking it must not
  collect data or save reporting terms.
- Use recorded backend readiness reasons for benchmark availability. Do not
  infer unsupported methods from the overall comparison's availability flag.
- Preserve chart controls, CSV export/import, source details and all existing
  trade boundaries. No backend, data-provider or calculation changes.
- Apply Impeccable Operate guidance and Microsoft-style action copy. Use existing
  styles, not a redesign. Independently review the source, then one affected
  real-browser smoke batch. No automated tests, mocks or fabricated inputs.

## Source review and corrections

The first independent source reviewer found that gating the inferred benchmark
warning on calculable price return was still insufficient: an accepted benchmark
method can have a price return but lack the strategy valuation boundaries needed
for comparison. Primary confirmed this in `performance.py:101-111` and
`performance_acceptance.py:33-46`, removed the inferred warning and retained the
backend's recorded readiness reasons. The new entry state also uses the existing
`.empty-state` component, not the old 120px-height-capped `.performance-empty`,
so its explanation and navigation do not require an inner scroll area.

Final JavaScript blob before live smoke:
`9cf16cfdec77e7fd0d3daff2b3bb9cffa03a2339`. The source delta is 4 added / 2
removed lines in `static/app.js`; no backend or CSS changes. JavaScript syntax
and scoped Git whitespace checks passed. No automated test was added or run.
Targeted independent correction review found no surviving source defects.
A separate UI-context reviewer successfully ran Impeccable context, read PRODUCT,
DESIGN, Operate and craft floor, and found no source-level scope/layout findings.
Both reviewed blob `9cf16cfdec77e7fd0d3daff2b3bb9cffa03a2339`; their source-only
reports are not runtime acceptance.

## Acceptance and evidence

Primary inspected the real dev8099 app after a browser reload of `265ec22`.
One affected smoke batch observed:

- The natural reporting read displayed “Loading saved account-history intervals…”
  without calculation failures, then resolved to the real no-interval entry state.
- “Open account history to compare performance” explained the next step and
  qualified benchmark prerequisites. There were zero metric tiles, no false
  unsupported-method warning and no horizontal page overflow at 1024 × 768.
- The rendered capture showed the explanation and Journal action fully visible,
  without the old inner height cap. The action opened Journal → Account History;
  no collection was started or reporting terms saved.
- CSV export and source-detail controls remained present. Console inspection
  reported no errors. No research, simulation, approval, submission, cancellation,
  transfer, trading-authority change or production operation occurred.

Primary decision: accept this complete first-use/readiness correction for the
observed empty-account journey. Populated calculations, saved-but-unopened
intervals, induced failures and provider collection remain source-reviewed but
not live-exercised; no fabricated inputs or extra cycles were used. The Browser
pane could not be shown because the app reported no session window; rendered
captures/DOM were inspected, not joint user-visible-pane acceptance.

After capture: `.local-workspace/dogfood-20261105/performance-entry-after.jpg`
(ignored local evidence). The next loop iteration must start within four minutes
of completion, per the user's cadence correction; use a three-minute wakeup.
