# Dogfood 3: distinguish SPY holdings dates from availability

## Status and observed defect

Completed implementation `85f0709` and one affected real-browser smoke on
5 November 2026. Baseline `67f9f21`, `nautilus`, `D:/src/TradingAgents`;
initial tree clean. The user requires fresh
agent scrutiny for every code change and one discrete complete item per loop.

Primary loaded the shipped year-start SPY 100% stock preset through the UI after
reading its static-only handler. The page showed an SEC N-PORT source dated
2025-12-31, scenario start 2025-12-31/end 2026-11-04, and 503 allocated stocks,
without any start-date availability or hindsight warning. No simulation ran.

Both allocation and saved-result renderers compared the holdings as-of date with
the scenario start, calling a later holdings date “published after the start.”
Equal or earlier dates suppressed the warning. A holdings date does not prove
publication or availability, and start-date equality does not establish a
point-in-time strategy test. This is a financial-evidence defect, not new
benchmark functionality.

## Research

Official sources accessed 5 November 2026:

- [SEC filing index](https://www.sec.gov/Archives/edgar/data/884394/000141036826020131/0001410368-26-020131-index.htm):
  primary read confirmed SPDR S&P 500 ETF Trust, report period 2025-12-31,
  filing 2026-02-26, accepted 16:49:39. That is the linked filing's publication,
  not proof of the earliest availability of equivalent holdings elsewhere.
- [State Street SPY](https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy):
  research worker reports as-of labeling and daily holdings downloads. This does
  not establish release time of either shipped capture.
- [SEC reporting guide](https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/investment-company-reporting-modernization-rules):
  research worker reports disclosure-timing rules, not a universal first-availability
  guarantee. No rule interval is being encoded in the app.

The year-start JSON supplies a reporting date and filing source. The October
JSON supplies holdings as of 2026-10-30 and MoneyDJ source, without a verified
publication/capture timestamp. Neither establishes availability of its exact
normalized allocation at the selected start. Keep these historical presets
separate from daily automatic SPY rebalancing and broker performance.

## Plan

- Label the value explicitly “Holdings as of” in both draft and saved result.
- Always explain fixed-snapshot hindsight and unverified availability at the
  simulation start, regardless of date ordering.
- If the holdings date is after a supplied start date, state that date fact only;
  do not call it a publication date. Leave blank start dates unclassified.
- Reuse one small disclosure helper. Preserve simulation eligibility, weights,
  dates, source captures, model/results and broker boundaries. No new gate,
  backend, data collection or publication timestamp.
- Use Impeccable Operate and craft floor. Obtain fresh independent agent review,
  static syntax/whitespace validation and one affected real-browser smoke with
  actual retained presets. Do not create a simulation or fabricate a result.

## Source implementation and review

The shared `holdingsTimingDisclosure()` is used by allocation drafts and saved
portfolio scenario results. Both label the date explicitly. The missing-source
fallback no longer invents an SEC filing source. Start-date edits update only
the disclosure so the optional after-start statement remains current.
No data, source files, calculation or execution path changed.

The first fresh reviewer found an introduced native date-editor regression:
a full workspace render on every date input would replace the focused editor.
Primary corrected it to update only `allocation-holdings-timing`, leaving the
native input in place. The reviewer ran Impeccable context and source guidance;
no runtime acceptance was inferred from that review.

Corrected source blob before smoke: `e96e389f68dae80cee4719642d60ef7fb9914205`.
JavaScript delta: 9 added / 4 removed lines; no CSS, backend or tests changed.
JavaScript syntax and Git whitespace checks passed. A separate fresh correction
verifier found no confirmed findings in this exact source blob and successfully
ran Impeccable context, Operate/audit and craft-floor review. It confirmed the
native input is not replaced by the disclosure update; rendered behavior remains
for the primary's smoke, not established by source review. The required Impeccable
detector reported only the pre-existing `#4dabf7` palette advisory at line 2378,
outside this change. No palette or design-system repair was added.

## Acceptance evidence

Primary reloaded the real dev8099 app at `85f0709` and exercised one affected
smoke batch with actual shipped captures:

- The year-start 100% stock preset still supplied the same dates and 503 weights.
  It displayed “Holdings as of 2025-12-31” and the persistent hindsight/availability
  caveat even though its holdings date equaled the start. No after-start claim
  was made for equal dates.
- The October preset displayed MoneyDJ, “Holdings as of 2026-10-30”, 90% stocks
  and 10% SGOV, and the same persistent caveat. It additionally said the snapshot
  was dated after the start; it did not claim a publication time. This was 504
  allocated symbols, including SGOV, with no change to the source preset.
- Native pointer and Backspace cleared a start-date segment. The input value
  became blank and focus remained `allocation-start`. The after-start statement
  disappeared immediately while the general disclosure stayed. Capital $100,000,
  fee $0 and end 2026-11-04 were unchanged. This verifies that editing case, not
  every native date-picker or keyboard interaction.
- Rendered captures showed the disclosure and existing actions at 1024 × 768.
  Browser console inspection reported no errors. No new simulation, provider
  collection, research, approval, submission, cancellation or authority change
  occurred. The two preset actions only read shipped source data.

Primary decision: accept the timing/provenance correction for these observed
entry cases after fresh source scrutiny. Saved-result rendering is source-reviewed
but not live-exercised; no result was fabricated or run created to demonstrate it.
Source captures, calculations and broker authority are unchanged. No automated
tests or mocks. Browser captures/DOM were inspected, not joint user-visible-pane
acceptance.

Ignored local captures under `.local-workspace/dogfood-20261105/`:
`spy-timing-before.jpg`, `spy-timing-after-year-start.jpg` and
`spy-timing-after-october.jpg`.
Continue the loop with the requested one-minute completion delay and mandatory
fresh-agent scrutiny; the scheduler can round beyond 60 seconds.
