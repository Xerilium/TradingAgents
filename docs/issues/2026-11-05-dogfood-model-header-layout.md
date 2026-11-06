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
