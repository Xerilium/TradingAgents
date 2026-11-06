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
