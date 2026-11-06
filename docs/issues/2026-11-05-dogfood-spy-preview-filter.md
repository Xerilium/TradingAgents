# Dogfood 7: find a stock in the SPY trade preview

## Status and observed friction

In progress from live dev8099 observations on 5 November 2026. Baseline
`946fcf2`, `nautilus`, `D:/src/TradingAgents`; initial working tree clean.
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
