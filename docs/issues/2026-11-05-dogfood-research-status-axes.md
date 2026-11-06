# Dogfood 9: distinguish processing status from research coverage

## Status and observed ambiguity

Completed implementation through `753df7a`, fresh independent source review and
one retained-input live UI batch on 5 November 2026. Baseline `b537c7f`, `nautilus`,
`D:/src/TradingAgents`; initial working tree clean.
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
ui-research-journal.css `0d5fe25412ae9b698bdef36dba8e244ef1031276`
(after corrections `16bb9ad` and `753df7a`; initial CSS blob was
`e510a1a6f7247197d657e57f65573dbd4f64cd5f`).
Final delta: 3 added / 3 removed JavaScript lines and 3 added CSS lines. No tests added
or run. JavaScript syntax and Git whitespace checks passed. The manual Impeccable
detector found no anti-pattern failures and only the previously recorded,
out-of-scope `#4dabf7` palette advisory at app.js line 2378. Its regex-only source
scan is not rendered contrast or product acceptance evidence.

Fresh independent source review `wf_5a24132f-565` confirmed the candidate blobs
and ran its own Impeccable context, Operate/clarify and craft floor. It found that
the existing nonwrapping, ellipsized metadata span can hide the list's gap badge.
Primary confirmed the narrow metadata grid and is correcting its direct span to
wrap, preserving the checkbox, symbol and quantity columns and existing selection.
This is source-reviewed visibility, not a runtime failure newly manufactured for
acceptance. The follow-up `wf_0f72301b-cd9` verified the unchanged semantics and
escaping, but noted that the nested inline-flex badge itself still inherited
nowrap and could exceed a narrower metadata column. Primary confirmed that
cascade and, in `753df7a`, scoped the nested badge to max-width 100%, normal
whitespace and anywhere wrapping. No grid columns or selection behavior changed.
Both reviews ran their own Impeccable context. Final fresh scrutiny
`wf_c98a1f6e-90a` reviewed `753df7a278578a787769b4df50e9502974f86c5f`
and found no concrete actionable defects. It ran its own Impeccable context and
read Operate, clarify, craft floor, PRODUCT and DESIGN. It checked the final
wrapping cascade/border-box sizing, escaped labels and unchanged result predicates,
notices and handlers. Source review does not prove rendered acceptance.

## Live acceptance evidence and decision

Primary loaded the actual running dev8099 frontend at the final source revision,
without restarting the service, and performed one affected retained-input batch:

- At 1024 × 768, the filter header still read 26 completed / 0 incomplete. The
  visible explanation stated the all-configured-and-saved-stock scope and that
  completed results can have coverage gaps. The section's accessible name and
  description pointed to the same explanation.
- The selected saved AAPL Summary showed Hold and a neutral “2 coverage gaps”
  badge, without calling that evidence condition an incomplete result. The row's
  matching badge was fully visible. Actual metadata and badge client/scroll sizes
  matched (184 × 52 and 112 × 27 respectively), with no clipped overflow.
- Clicking 26 completed retained the matching AAPL row and inspected result.
  Clicking 0 incomplete showed the existing explicit no-match guidance and zero
  rows; it did not replace the selected AAPL result or its two coverage gaps.
  Returning to All stocks and clearing search expanded the list while global
  counters stayed unchanged. AMD's actual row separately showed 19 coverage gaps.
  No batch checkbox was changed; the batch remained zero checked.
- AAPL Reports (10) opened its saved Portfolio decision. Sources & Filings opened
  Saved sources, Vendor & memory provenance, and Evidence and filings · AAPL with
  saved research date 2026-11-04 / revision 59. No research/provider job was started.
- Restored AAPL search and Summary, then inspected 768 × 1024. The status controls
  and explanation wrapped; the list and detail stacked. Help and row badge had
  equal client/scroll dimensions, and document width equaled viewport width at
  both sizes. Viewport emulation was reset to desktop afterward.
- Console inspection reported no errors. Existing order authority remained
  “Orders: Active · Manage.” No order preparation, approval, submission, cancel,
  authority toggle, fund-plan save, research rerun, simulation, credential/private
  configuration read, installation or production operation occurred.

Primary decision: accept this discrete status/coverage clarity correction after
fresh scrutiny and the observed retained-input cases. Missing-required-report
incomplete results, failed/cancelled/running/queued transitions, UNKNOWN exposure,
populated batch-selection combinations, physical assistive technology and broker
execution were not separately exercised. No fake records, automated tests or mocks.
This is not a claim that coverage gaps are harmless or that every research source
succeeded. Captures and DOM were personally inspected; no joint human acceptance
is claimed.

Ignored captures: `.local-workspace/dogfood-20261105/research-status-axes-after.jpg`
and `research-status-axes-after-narrow.jpg`. Reusable diagnostic lesson:
`memory://knowledge/projects/tradingagents/tradingagents-result-completion-and-coverage-gaps-are-separate-axes`.

Continue the completion-paced loop with requested 60-second delay, dynamic
workflows, fresh source scrutiny and integrated local commits on `nautilus`.
Scheduler minute-boundary rounding can exceed the requested delay.
