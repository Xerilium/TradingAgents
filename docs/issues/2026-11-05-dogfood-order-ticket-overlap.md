# Dogfood 5: keep order-ticket stages from overlapping

## Status and observed failure

In progress from live dev8099 observations on 5 November 2026. Baseline
`6033ab4`, `nautilus`, `D:/src/TradingAgents`; initial working tree clean.
All work stays integrated on this branch. No new worktree or branch.

The real Orders → Ticket & Blotter view at 1024 × 768 shows preparation labels,
inputs and summary text painted over the Stage 3 heading and submission guidance.
The lower account-order controls remain readable. The observed ticket is the
existing BND selection, with no approved order and $100,000 cash. No order terms,
approval, authority or broker action were changed to reproduce the failure.

Read-only DOM geometry showed `.orders-preparation` only 207px high with 1,220px
of scrolling content and visible overflow. Its following `.orders-review-pane`
was 350px high with 2,158px of content and visible overflow. Their parent
`.orders-direct-grid` was a 569px-high flex container. These are observations,
not yet a complete source diagnosis. The initial layout-scoped Impeccable detector
reported no findings; that does not establish a working rendered layout.

Before capture (ignored):
`.local-workspace/dogfood-20261105/order-ticket-overlap-before.jpg`.

## Research and source diagnosis

Official broker documentation accessed 5 November 2026:

- [Fidelity order FAQ](https://www.fidelity.com/trading/faqs-placing-orders): primary
  read confirmed preview/edit before submission, with order confirmation distinct
  from execution. Readable exact terms and separate actions are the applicable
  principles; this is not broker UI or execution acceptance.
- [Robinhood order instructions](https://robinhood.com/us/en/support/articles/360001357526/):
  research worker reports review/edit before a separate submit action. This is
  documented flow, not an observed Robinhood account or full feature parity.

The independent source worker traced `ui-orders.css`: under 1500px, the two
panes switch to visible overflow while retaining `min-height:0`. The short/narrow
breakpoint also stacks them as flex items, whose default shrink compresses their
boxes. Their content then paints into later stages. Primary additionally inspected
1024 × 1024 before editing: even the one-column grid gave each pane only 406px
while their content measured 1,003px and 2,414px. A flex-only fix would miss this
same failure in the taller grid layout.

Scoped plan: in the existing under-1500px rule that permits visible overflow,
restore `min-height:auto` for those two panes. Their content-based minimum then
reserves space in both stacked flex and one-column grid layouts. Preserve the
wide layout's `min-height:0` and independent `overflow:auto`. No markup, copy,
JavaScript, handler or global layout change. Reading order stays preparation,
exact-revision review, then separate broker action; existing density and spacing
remain. The source classes also serve Fills & Fees, Human Baskets and Option
Instructions; SPY Rebalance uses a separate layout.

The research worker retrieved the current and previous overlap observations at
`memory://thinking/sequential/2026/11/06/session-1793926836756-62604` and
`memory://thinking/sequential/2026/11/06/session-1793926754557-32527`. These are
attributed historical evidence, not independent UI acceptance or new authority.

## Investigation and constraints

A dynamic workflow independently traces the source/cascade and researches official
broker order-review guidance plus applicable Maenifold lessons. Primary owns the
browser and implementation. Source workers do not operate the app, edit files or
run tests. Every final code change requires a separate fresh independent review
with Impeccable context before primary sign-off.

Keep all existing preparation, review and separate broker-action content, fields,
terms, handlers, focus/navigation routes and authority boundaries. Fix this one
observed layout failure, not the product identity or trading engine. Use Impeccable
Operate/layout guidance and craft floor. No fabricated order, private configuration,
credential inspection, broker action, provider collection or production operation.
No automated tests or mocks. Plan one affected responsive live smoke after the
coordinated source fix and fresh scrutiny; unexercised populated states remain
explicitly unverified.

## Source implementation and checks

One declaration, `min-height:auto`, was added to the existing under-1500px pane
rule in `ui-orders.css`. No other code, markup, CSS rule or runtime changed.
Source delta: 1 added / 1 removed CSS line. Reviewed candidate blob:
`4d93ce8fe93499debd4d8ad5f2a6c56a4e471de8`.
Git whitespace validation and the layout-scoped Impeccable detector passed; the
detector returned no findings. There is no JavaScript change requiring a syntax
check. No automated tests were added or run.

A separate fresh independent reviewer is scrutinizing the actual diff against
`7c2188b`, cascade, both responsive modes and shared Orders views. Review and one
live affected responsive smoke remain pending; no acceptance is implied yet.
