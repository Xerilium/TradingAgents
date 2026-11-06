# Dogfood 1: truthful account-performance entry state

## Status and scope

Planned from live development-desk observations on 5 November 2026. Baseline
`6095882`, `nautilus`, `D:/src/TradingAgents`; working tree initially clean.
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
- Show the unsupported benchmark-method warning only when a benchmark price
  return is actually calculable but unsupported for strategy comparison.
- Preserve chart controls, CSV export/import, source details and all existing
  trade boundaries. No backend, data-provider or calculation changes.
- Apply Impeccable Operate guidance and Microsoft-style action copy. Use existing
  styles, not a redesign. Independently review the source, then one affected
  real-browser smoke batch. No automated tests, mocks or fabricated inputs.

## Acceptance and evidence

Pending implementation and one smoke batch. The real empty-account state can
verify truthful first-use guidance, disappearance of false calculation failures
and existing Journal navigation. Populated calculations, induced loading/errors
and provider collection remain unverified unless real retained inputs naturally
exercise them. No fresh account-history collection is required for this fix.
