# Dogfood 7: find a stock in the SPY trade preview

## Status and observed friction

Completed implementation `38b94f1`, fresh independent source review and one
affected real-preview UI smoke on 5 November 2026. Baseline `946fcf2`,
`nautilus`, `D:/src/TradingAgents`; initial working tree clean.
Keep all work integrated on `nautilus`; no branch or worktree sprawl.

Primary navigated the real Orders → SPY Rebalance view and traced Preview before
using it once. It refreshes holdings/quotes, may extend the quote universe if
needed, and builds an in-memory manual preview; it does not submit or queue
orders. The existing automatic-trading setting was on and left unchanged.
No fund plan or reserve values were invented or saved.

The dry run returned 503 stocks / 503 planned trades, weights dated 2026-11-04,
Trading Rules revision 0 and 99.91% target stock exposure. The first AAPL row
showed a real planned quantity. No broken preview outcome was observed; this
iteration addresses review friction, not a claimed calculation or execution bug.

The proposed-trades table had 503 rows in a 190px-high region with 22,828px of
content. Its headers were already sticky, but there was no symbol lookup. The
only inputs in the SPY section were the four fund-plan fields. A reviewer looking
for a specific constituent had to scan/scroll the full list. Those source trades
must remain intact: a view filter is not an allocation, approval or order filter.

Before capture (ignored):
`.local-workspace/dogfood-20261105/spy-preview-filter-before.jpg`.

## Research and plan

Official sources accessed 5 November 2026:

- [Robinhood Legend widgets](https://robinhood.com/us/en/support/articles/widgets-in-robinhood-legend/):
  primary read confirmed symbol search when adding a watchlist item and column
  sorting, not filtering existing contents or a trade preview. Local preview
  lookup is an adaptation, not a claim of exact feature parity.
- [Fidelity Basket Portfolios FAQ](https://www.fidelity.com/direct-indexing/customized-investing/faqs):
  research worker reports saved drafts containing securities/target weights
  separate from editing and trading. This does not prove a preview-filter feature
  or execution acceptance.

Independent source mapping confirmed that `spyRebalanceAction()` retains the
complete validated trade array and submits its existing token, not displayed rows.
`bindBaskets()` already delegates local input/click events. Use that path without
calling the full renderer on each keystroke.

Add a session-only symbol query, trimmed case-insensitive substring matching,
a labeled native search input, separate matching/full-plan count, clear action
and no-match guidance. Derive display rows without mutating source trades. Keep
the full Proposed trades heading and dry-run summary unchanged and state that
filtering does not change the full rebalance plan. Input updates replace only the
table body/count, preserve the input node/caret, and reset vertical table scroll
while retaining horizontal position. Use the existing focused-node reuse marker
for ordinary polling renders, not a new focus mechanism. Keep the input value and
rendered rows synchronized from the same query. Clear resets/focuses the search;
starting a new preview or explicit preview reset clears the query. Preserve every
financial admission, expiry and dispatch path.

The research worker read the current attributed observation at
`memory://thinking/sequential/2026/11/06/session-1793928248593-14002`.
That is source evidence, not independent UI acceptance.

## Investigation and constraints

A dynamic workflow independently maps preview state, rendering/binding and input
preservation, and researches documented broker review affordances. Primary owns
code and the built-in browser. Plan a small local symbol lookup with a truthful
matching count, clear/no-match behavior, and explicit view-only wording. Do not
add backend features, prices, invented allocations or order terms. Preserve all
source trades, full-plan totals, tokens, expiry/admission checks and submission
behavior. Never print a preview token or the whole API response.

Use Impeccable Operate/harden guidance and craft floor. Obtain fresh independent
code review with its own Impeccable context, then one affected real UI smoke with
one fresh preview after loading the corrected frontend. No automated tests,
mocks, fake preview records, broker actions, authority changes, private settings
or credential inspection. Populated retained preview rows, not fabricated fixtures,
are the verification input. Filtering must not initiate another preview or submit.

## Source implementation and checks

The SPY preview now renders a native Find planned stock field, Clear filter,
matching/full-plan count, view-only explanation and an explicit no-match row.
A separate session query derives display rows from the complete preview without
mutating it. Delegated input replaces only body/count; the existing focused-node
reuse marker preserves the native input during ordinary renders. Query edits
reset table vertical scroll and update its existing keyed scroll record while
retaining horizontal position. Clear restores/focuses the input. Explicit preview
resets and new previews clear the query. Financial handlers and payload are intact.

Candidate source blob: `7f5b54eb68265bd84dc3d2bf051cc8e4ec0f9e84`.
Delta: 21 added / 7 removed JavaScript lines. No backend, CSS or tests changed.
JavaScript syntax and Git whitespace checks passed. The Impeccable detector
reported only the pre-existing `#4dabf7` palette advisory at line 2378, outside
this change. No automated tests or mocks were added or run. A separate fresh
independent reviewer found no confirmed actionable findings against `3520a12` and
the recorded blob, committed as `38b94f1`. The reviewer successfully ran Impeccable
context and read PRODUCT, DESIGN, Operate, harden and craft floor. Source coverage
included escaping, delegated input/native-node reuse, scroll, invalidation and
full-plan authority boundaries. Runtime acceptance was not inferred from review.

## Acceptance evidence and decision

Primary reloaded the actual running dev8099 frontend at `38b94f1`, without a
service restart, then completed one affected UI batch using one fresh dry run:

- Before preview, no lookup or misleading no-match state appeared. The validation
  preview returned the real 503-trade plan. Initial count was “Showing 503 of 503
  planned trades” and the heading stayed “Proposed trades (503).” There were two
  dry-run actions in this item: one for initial dogfooding and one for validation,
  not repeated submission, research or simulation runs.
- Native scrolling moved the trade table to 600px. Typing lowercase `aapl` reset
  it to zero and showed only AAPL, BUY, 22.316587347. That exact quantity matched
  this preview's initial unfiltered row. Focus stayed in the native search input,
  with selection/caret at 4. No full-plan total was replaced by the match count.
- Native Ctrl+A and typing ` brk.b ` matched BRK.B despite case, punctuation and
  surrounding spaces. Count stayed 1 of 503; the retained row showed BUY,
  2.841465247, with input focus and caret at 7.
- The existing selected research symbol BND is not in this stock-only plan.
  Looking it up showed 0 of 503, retained the full-plan heading, and displayed
  “No matching symbols. Clear the filter to show all planned trades.” No fake
  order or preview was fabricated for the empty-match case.
- At 768 × 1024 the search, count, explanation, no-match row and Clear filter
  rendered without page overflow. Native Tab moved from search to Clear filter;
  after confirming that exact button held focus, Enter restored all 503 rows and
  returned focus to the empty search input. AAPL's quantity was still unchanged.
  Viewport emulation was reset to desktop. The 1024px page width also matched its
  viewport, and the cleared field/focus/count remained consistent through the
  observed background refresh period. Physical IME composition was not tested.
- Console inspection reported no errors. The existing “Automatic trading on”
  setting was unchanged. There was no fund-plan save, reserve edit, approval,
  submission, queue, cancel/replace, enable/disable, research run, simulation,
  installation or production operation. Filtering/clear invoke no API in source;
  no token or complete API response was printed.

Primary decision: accept the discrete view-only constituent lookup after fresh
source scrutiny and these observed real-preview cases. The entire plan, sizing
and submission authority remain separate from the view filter. Zero-trade plans,
restore/account/revision invalidation, nonzero horizontal scroll, physical IME and
broker execution were source-reviewed or left unexercised, not claimed as passes.
No automated tests or mocks. Rendered captures and DOM were inspected; no joint
user-visible-pane acceptance is claimed.

Ignored local captures under `.local-workspace/dogfood-20261105/`:
`spy-preview-filter-before.jpg`, `spy-preview-filter-after-full-list.jpg`,
`spy-preview-filter-after-aapl.jpg` and
`spy-preview-filter-after-no-match-narrow.jpg`.

Continue the completion-paced loop with the requested one-minute delay, dynamic
workflows, fresh independent code scrutiny and local commits on `nautilus`.
Scheduler minute-boundary rounding can exceed 60 seconds.
