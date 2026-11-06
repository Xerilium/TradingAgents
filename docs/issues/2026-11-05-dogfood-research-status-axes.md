# Dogfood 9: distinguish processing status from research coverage

## Status and observed ambiguity

In progress from live dev8099 observations on 5 November 2026. Baseline
`b537c7f`, `nautilus`, `D:/src/TradingAgents`; initial working tree clean.
All work remains integrated on `nautilus`; no new branch or worktree.

Primary followed the real Research journey: searched AAPL, explicitly selected
its row, then opened saved Reports and Sources & Filings. These paths worked
without rerunning research. Search alone correctly left the prior BND review
selected; selecting the AAPL row opened the matching AAPL result.

The status-filter header showed “26 completed” and “0 incomplete”, while the
selected AAPL summary showed “incomplete” with two coverage gaps. Other completed
rows also had incomplete coverage. This may be two legitimate status axes, not
incorrect counters. A trader needs to know whether completed means processing
finished or evidence complete before using a research result.

Before capture (ignored):
`.local-workspace/dogfood-20261105/research-status-axes-before.jpg`.

## Investigation and constraints

A dynamic workflow independently traces the exact counter/filter/coverage
contracts and researches documented broker research limitations. Do not assume
the counts are wrong. Choose the smallest complete clarity correction only after
that trace. Preserve counts, filter keys, selection, saved result identity,
quality metadata, model-proposal eligibility and latest-only retention. No new
quality metric/filter, backend capability or research history.

Primary owns code and the built-in browser. Use Impeccable Operate/clarify and
craft floor; fresh independent code review must run its own Impeccable context.
Then one affected live smoke using the retained AAPL result and existing filters.
No research rerun, provider job, fabricated data, automated test, mock, private
configuration/credential inspection, order, approval or authority change.
