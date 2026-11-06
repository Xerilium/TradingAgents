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

A dynamic workflow independently traced the exact counter/filter/coverage
contracts and researched documented broker research limitations. Do not assume
the counts are wrong. Choose the smallest complete clarity correction only after
that trace. Preserve counts, filter keys, selection, saved result identity,
quality metadata, model-proposal eligibility and latest-only retention. No new
quality metric/filter, backend capability or research history.

Primary owns code and the built-in browser. Use Impeccable Operate/clarify and
craft floor; fresh independent code review must run its own Impeccable context.
Then one affected live smoke using the retained AAPL result and existing filters.
No research rerun, provider job, fabricated data, automated test, mock, private
configuration/credential inspection, order, approval or authority change.

## Verified diagnosis and plan

The source-mapping workflow `wf_e35e7913-1e3` confirmed two separate axes.
`researchProgress()` counts unique configured and saved symbols before search,
pagination or batch selection, using the same result-status predicate as the
filters. These are not distinct-run counts. Compact saved summaries can classify
missing required reports as incomplete (`store.py` and `evidence_requirements.py`).
Source/Gateway/social/persistence coverage receipts are a separate collection in
`service.py`; a completed result may retain coverage gaps. Their count is not a
claim about unique failed providers or network calls. No incorrect counter was
established in the observed 26-completed / zero-incomplete state.

Official sources accessed 5 November 2026:

- [Fidelity research-firm information](https://research2.fidelity.com/fidelity/research/reports/release2/Research/ExploreResearchFirms.asp):
  primary read confirmed the disclaimer that supplied information is not guaranteed
  accurate, complete or timely.
- [Robinhood Cortex Digests methodology](https://robinhood.com/us/en/support/articles/cortex-digests-methodology/):
  research worker reports limits on instrument coverage and accuracy. Neither
  source defines this desk's result-status or coverage-gap counts; no exact UI
  parity is claimed.

Plan: replace the ambiguous incomplete badge only in the two coverage fragments
(row and selected summary) with the existing neutral badge containing the actual
coverage-gap count. Preserve the separate missing-required-report notice and all
status predicates. Add visible help within the existing wrapping status-filter
section: counts cover all configured and saved stocks regardless of search or
batch selection; completed results can have coverage gaps. Give the section a
consistent accessible name and description. One scoped full-width paragraph rule
keeps the explanation inside the nonshrinking filter section rather than adding
another shrinking workspace child. No new data, metric, filter or backend change.

Fresh source review follows the complete UI batch, then one retained-input smoke
covering AAPL Summary, Reports, Sources & Filings, completed/incomplete filters,
search scope and a narrower viewport. No research/provider request or broker action.

## Source implementation and checks

Implementation `e1ad50d` changes only the two coverage labels and adds the scoped
filter explanation with its accessible description. Result counts, filter keys,
selection, report/coverage metadata, eligibility and backend remain unchanged.
The help is a full-width flex item inside the existing nonshrinking filter group.

Candidate blobs: app.js `bf773b136a44cabc30a84a799e6b1fc0c2bc3637`;
ui-research-journal.css `e510a1a6f7247197d657e57f65573dbd4f64cd5f`.
Delta: 3 added / 3 removed JavaScript lines and 1 added CSS line. No tests added
or run. JavaScript syntax and Git whitespace checks passed. The manual Impeccable
detector found no anti-pattern failures and only the previously recorded,
out-of-scope `#4dabf7` palette advisory at app.js line 2378. Its regex-only source
scan is not rendered contrast or product acceptance evidence.

Fresh independent source review `wf_5a24132f-565` is in progress. Live acceptance
has not yet run on this revision.
