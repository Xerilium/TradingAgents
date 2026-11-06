# Dogfood 10: make model proposal controls readable

## Status and observed jank

In progress from live dev8099 observations on 5 November 2026. Baseline
`03f168f`, `nautilus`, `D:/src/TradingAgents`; initial working tree clean.
All work remains integrated on this branch; no new branch or worktree.

Primary inspected Portfolio Positions, Model proposal and Allocations, then
followed Open account fund plan to its correct Orders destination. No broken
outcome was observed in those read/navigation paths. No model job, simulation,
research rerun, fund-plan save or broker action was used.

At 1024 × 768, Model proposal's two field labels sit inline directly against
their inputs with no visible separation. DOM text ranges ended exactly where
the inputs began: Model capital at x=755.53125; Prices and research as of at
x=784.265625. There is no established text overlap or calculation defect. The
right-hand controls form three rows and crowd the workspace tabs onto a row
below the title, unlike the simpler Portfolio tabs. This item addresses form
scanability and header jank, not model allocation behavior or execution.

Before capture (ignored):
`.local-workspace/dogfood-20261105/model-header-layout-before.jpg`.

## Investigation and constraints

Dynamic workflow `wf_b9e931c9-fce` independently traces the header/input CSS,
source bindings and polling preservation, and researches official trading-tool
organization principles. Primary owns implementation and the built-in browser.
Choose a scoped form layout, not a global header or form redesign. Preserve
existing input IDs, attributes, values, labels and behavior; keep the Model
portfolio action separate and explicit. Do not invent a result or change model
capital/as-of semantics, eligibility, research or broker authority.

Use Impeccable Operate/layout guidance and craft floor before editing. Obtain
fresh independent code scrutiny with its own context setup, then one affected
live layout/navigation/native-input smoke at desktop and narrow widths without
activating Model portfolio. No automated tests, mocks, fabricated model records,
private configuration/credentials, production operations or broker actions.

## Research and plan

The independent source trace found that only the proposed tab passes these fields
into the shared header action group (`app.js:763–766`). The intended column-label
and input-width rules target `.proposed-portfolio`, but the controls are outside
that section, so those rules do not reach them. The labels contain text directly
followed by the input. Header flex sizing therefore competes with workspace tabs
without providing field grouping. The initial layout-only source detector found
no findings; it cannot establish rendered hierarchy or spacing.

Official sources accessed 5 November 2026:

- [Fidelity Trader+ Desktop customization](https://www.fidelity.com/trading/trader-desktop-user-guide/customization):
  primary verified that workspaces are the containers for tools.
- [Robinhood Legend layouts](https://robinhood.com/us/en/support/articles/layouts-on-legend/):
  research worker reports moving and resizing widgets. This supports coherent
  grouping and sufficient space, not adding draggable widgets or claiming an
  exact form layout/model-allocation feature in either product.

Plan: retain the title and tabs in the existing Portfolio header, and place the
existing model actions in a dedicated, proposed-only row immediately afterward,
before the account ledger. Use a wrapping flex row, end alignment and existing
spacing tokens. Stack each persistent label above its input with the existing
small gap and 180px input convention. Preserve DOM/focus order (capital, date,
explicit Model portfolio action), IDs, values, attributes, disabled conditions,
event listeners and polling restoration. Keep Performance export actions and all
other tabs/workspaces unchanged. No global header or form CSS changes.

Primary will inspect capital/date native focus and value retention across polling
and tab navigation without altering their terms or running the model. The one
live batch will cover 1024 × 768, 768 × 1024 and wide desktop grouping/reachability.
Running/queued/populated job states remain source-reviewed unless already present;
no job or fabricated result will be created to manufacture that acceptance.
