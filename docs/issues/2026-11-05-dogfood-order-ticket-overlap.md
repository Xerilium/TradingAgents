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
