# Dogfood 3: distinguish SPY holdings dates from availability

## Status and observed defect

Planned from live dev8099 observations on 5 November 2026. Baseline `67f9f21`,
`nautilus`, `D:/src/TradingAgents`; initial tree clean. The user requires fresh
agent scrutiny for every code change and one discrete complete item per loop.

Primary loaded the shipped year-start SPY 100% stock preset through the UI after
reading its static-only handler. The page showed an SEC N-PORT source dated
2025-12-31, scenario start2025-12-31/end2026-11-04, and 503 allocated stocks,
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
  primary read confirmed SPDR S&P 500 ETF Trust, report period2025-12-31,
  filing2026-02-26, accepted16:49:39. That is the linked filing's publication,
  not proof of the earliest availability of equivalent holdings elsewhere.
- [State Street SPY](https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy):
  research worker reports as-of labeling and daily holdings downloads. This does
  not establish release time of either shipped capture.
- [SEC reporting guide](https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/investment-company-reporting-modernization-rules):
  research worker reports disclosure-timing rules, not a universal first-availability
  guarantee. No rule interval is being encoded in the app.

The year-start JSON supplies a reporting date and filing source. The October
JSON supplies holdings as of2026-10-30 and MoneyDJ source, without a verified
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

## Acceptance evidence

Pending implementation and one live affected smoke. Drafts can exercise the
real year-start equal-date and October after-start cases. Saved-result rendering
is source-only unless a suitable actual retained result can be opened without
starting a new run. No automated tests, mocks or broker actions.
