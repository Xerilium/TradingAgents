# Dogfood 5: keep order-ticket stages from overlapping

## Status and observed failure

Completed implementation `d7d4abf`, fresh independent source review and one
affected live responsive smoke on 5 November 2026. Baseline `6033ab4`,
`nautilus`, `D:/src/TradingAgents`; initial working tree clean.
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

A separate fresh independent reviewer found no confirmed actionable findings
against `7c2188b` and the recorded blob, committed as `d7d4abf`. The reviewer
successfully ran Impeccable context and read PRODUCT, DESIGN, Operate, layout and
craft floor. Source review confirmed both responsive modes, the preserved wide
scrolling rules and shared Orders callers. It did not establish runtime behavior.

## Acceptance evidence and decision

Primary reloaded the running dev8099 app at `d7d4abf` and completed one affected
responsive live smoke batch, without restarting the service or creating terms:

- At 1024 × 768, the existing bracket/replacement disclosure was expanded by
  native pointer. Preparation reserved 1,296px and the following review pane
  started 12px below it. The review pane reserved 2,172px. The Manage shortcut
  scrolled to clean, readable Stage 3 content, with no preparation fields painted
  over it. No order-action control was used.
- At 1024 × 1024, the one-column grid also reserved its full content heights:
  client/scroll heights matched at 1,077px for preparation and 2,426px for review.
  This covers the taller grid failure that a flex-only fix would have missed.
- At 768 × 1024, the stacked panes' client/scroll heights matched at 1,315px and
  2,479px, with 12px between panes. The rendered Stage 2/3 boundary was readable.
- At 1600 × 768, the existing bounded panes retained `min-height:0` and
  `overflow:auto`. Native scrolling inside preparation moved its scroll position
  to 600px while the review pane and main stayed at zero. At 1600 × 1000, the
  two-column grid retained bounded independent panes and readable Stage 1/2.
  An immediate resize capture was stale; the settled wide/short capture, not that
  stale frame, was inspected and retained.
- Document width equaled viewport width at all five sizes. Viewport emulation was
  reset to desktop. Human Baskets was then selected through the actual tab: the
  existing empty basket view started below preparation, client/scroll heights
  matched, and the rendered boundary did not overlap. This does not validate
  populated baskets. Fills & Fees and Option Instructions were source-reviewed
  shared callers, not separately live-exercised.
- The topbar remained “Orders: Active · Manage”, with the existing BND selection,
  no approved order and $100,000 cash. No console errors were reported. No draft
  save, preview, approval, submission, pause/resume, cancel/replace, simulation,
  provider collection, research run, installation or production operation.

Primary decision: accept this discrete pane-sizing repair after fresh source
scrutiny and the observed responsive batch. Filled or dirty drafts, populated
approvals/orders/baskets and every disclosure variant remain unverified; none was
fabricated for acceptance. No automated tests or mocks were added or run. This is
not full order-workflow or broker-execution acceptance. Browser captures and DOM
were inspected; the session's pane could not be jointly shown in the prior
iteration, so no joint user-visible acceptance is claimed.

Ignored local evidence under `.local-workspace/dogfood-20261105/`:
`order-ticket-overlap-before.jpg`, `order-ticket-overlap-after-desktop.jpg`,
`order-ticket-overlap-after-narrow.jpg`, `order-ticket-overlap-after-tall-grid.jpg`,
`order-ticket-overlap-after-wide-short.jpg` and
`order-ticket-overlap-after-baskets.jpg`.

Continue the completion-paced loop with its requested one-minute delay, dynamic
workflows, fresh code scrutiny and local commits integrated on `nautilus`.
Scheduler minute-boundary rounding can exceed 60 seconds.
