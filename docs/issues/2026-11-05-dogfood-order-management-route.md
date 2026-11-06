# Dogfood 4: make Orders Manage reach its controls

## Status and observed failure

Planned from live dev8099 observations on 5 November 2026. Baseline `9e30a78`,
`nautilus`, `D:/src/TradingAgents`; initial working tree clean.

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
pre-existing `#4dabf7` advisory at line 2378, outside this change. Fresh source
review is pending. No automated tests were added or run.

## Acceptance evidence

Pending one live affected smoke. It will cover the original Human Baskets
failure, another affected Orders context and the existing SPY route, plus
inspection that management remains navigation-only. Any populated dirty form or
deferred workflow guard not naturally available stays source-reviewed, not an
invented acceptance case. No automated tests or mocks.
