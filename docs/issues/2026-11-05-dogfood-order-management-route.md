# Dogfood 4: make Orders Manage reach its controls

## Status and observed failure

Completed implementation `2a37df4` and one affected live navigation smoke on
5 November 2026. Baseline `9e30a78`, `nautilus`, `D:/src/TradingAgents`;
initial working tree clean.

Primary selected Orders → Human Baskets, then clicked the topbar
“Orders: Active · Manage.” The selected tab stayed Human Baskets,
`account-order-controls` was absent and focus remained on `pause-trading`.
The management shortcut therefore failed to expose its intended controls.
No pause, resume or broker action was taken.

## Source diagnosis and research

`togglePause()` navigates to Orders through the existing guarded route, calls
`showOrderTicketTab()`, renders and attempts to focus `account-order-controls`.
That helper exits SPY Rebalance only; Human Baskets, Fills & Fees and Option
Instructions remain selected. The target renders only in Ticket & Blotter and
is an existing h3 with `tabindex=-1`. Optional chaining hides the failed focus.

The narrower helper also serves the T shortcut and ordinary ticket preparation.
Do not broaden those routes or discard the selected ticket, drafts or baskets.
The workspace/credential navigation guards must remain in force; none of their
private data is needed for this task.

[Fidelity's trading FAQ](https://www.fidelity.com/trading/faqs-getting-started),
accessed 5 November 2026, documents Preview Order for review and Place Order for
submission. Primary read confirmed that distinction. It does not establish a
broker pause feature. The parity principle here is reliable access to controls,
while navigation, review, authority changes and broker actions remain separate.

## Plan

Add a dedicated exported `showOrderManagement()` method that selects only
Ticket & Blotter. Call it only inside Manage's existing `navigatePage` completion
callback before the current forced render and focus. Preserve the narrower
helper, all guards, forms, previews, ticket terms and actual command handlers.
No backend, CSS, approval, pause/resume or dispatch changes.

Use Impeccable Operate and craft floor. Every code change must receive fresh
independent agent scrutiny before primary sign-off. Run static syntax/design
checks and one affected live navigation smoke. Do not click Pause, Resume,
Approve, Submit, Cancel or Replace; do not create fake order terms for validation.

## Source implementation and checks

Manage now calls the dedicated exported `showOrderManagement()` inside the
unchanged guarded navigation callback. That helper assigns only the Orders tab.
The ordinary `showOrderTicketTab()` helper and its preparation callers are
unchanged. The existing render and focus follow the selection as before.

Source blob before smoke: `0e7bd91565460e14c59de99dd00bcdc8a870d089`.
JavaScript delta: 2 added / 2 removed lines, no backend/CSS changes. Syntax and
Git whitespace checks passed. The required Impeccable detector reported only the
pre-existing `#4dabf7` advisory at line 2378, outside this change. A fresh
independent reviewer found no confirmed findings against `81079d1` and the
recorded blob. The reviewer successfully ran Impeccable context and read Operate,
PRODUCT, DESIGN and craft floor. Source-only review confirmed guard and caller
preservation; runtime focus and dirty-form cases were not inferred from it.
Implementation checkpoint: `2a37df4`. No automated tests were added or run.

## Acceptance evidence

Primary reloaded the running dev8099 frontend at `2a37df4` and completed one
affected navigation batch at 1024 × 768, without restarting the service:

- From Human Baskets, native Manage navigation selected Ticket & Blotter and
  focused `account-order-controls`. The existing heading read “Orders: Active.”
- Fills & Fees was explicitly observed selected with no account-control target.
  Manage selected Ticket & Blotter and focused the exact existing target.
- SPY Rebalance was explicitly observed selected with no account-control target.
  Manage again selected Ticket & Blotter and focused that target.
- The topbar stayed “Orders: Active · Manage” throughout. The visible existing
  BND selection, no-approved-order state and $100,000 cash were unchanged.
  No Pause, Resume, Approve, Submit, Cancel or Replace control was used.
- Browser console inspection reported no errors. No new orders, research,
  simulations, provider collection, runtime installation or production operation.
  Coordinate/inspection batches were refused by the tool classifier; individual
  named navigation actions and separate read-only inspection were permitted.

Primary decision: accept the discrete management-routing fix after fresh source
scrutiny and observed focus/navigation. Populated dirty-form retention and
workflow/credential deferred guards remain source-reviewed, not runtime-proven;
no fake terms or private credential state were created to exercise them. No
automated tests or mocks. The capture also shows overlapping existing Stage 3
content; that layout is not repaired or accepted by this routing change.

Rendered browser capture and DOM were inspected. The app could not show this
session's pane, so this is not joint user-visible-pane acceptance. Ignored local
evidence: `.local-workspace/dogfood-20261105/orders-manage-before.jpg` and
`orders-manage-after.jpg`. Continue the requested one-minute completion-paced
loop with fresh-agent code scrutiny; scheduler rounding can exceed 60 seconds.
