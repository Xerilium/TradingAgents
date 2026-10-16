# T-1.6 blue-team specification

## Verified regression

The real `tradingagents/web/static/lists.js` quoteState accepts a closed market only while the clock timestamp is at most 900,000 ms old. The real `app.js` renderChrome trusts a truthy clock object and falsy is_open indefinitely. At 2026-10-15 23:53 UTC with the clock observed at 23:31:12 UTC and next_open at October 16 13:30 UTC, the header says Market closed but the recent completed-session trade says stale. This is a display-classification inconsistency, not evidence the broker refresh failed.

## Test design and red evidence

`quote_clock_regressions.cjs` loads both real source files in a VM with frozen time, no startup readState, disabled timers, and fetch that throws. DOM stubs capture actual renderChrome text; quoteStatus is actual application code. No copied classification implementation, network, research, orders, packages, or product edits.

Run with a hard deadline:

```powershell
rtk proxy .venv/Scripts/python.exe .paper-desk/run-bounded.py --seconds 15 -- node tests/quote_clock_regressions.cjs
```

Baseline: **12 tests; 8 failed, 4 passed**, exit 1, about 40 ms. Failed cases:

1. Exact 22-minute clock age reproducer: stale instead of closed.
2. Overnight reference before verified next open: stale instead of closed.
3. Friday reference on Sunday before broker-provided Monday next open: stale instead of closed.
4. Prior-session trade with fresh closed clock: closed instead of stale.
5. At next-open boundary, header still claims closed instead of unknown/unverified.
6. Missing is_open incorrectly renders closed.
7. Invalid clock timestamp incorrectly renders closed.
8. Future clock timestamp incorrectly renders closed.

Passing controls: open-market old quote stale; open-market recent quote current; absent price missing; recent closed reference says Last trade and never official close/closing price/auction.

Initial Node --test invocation failed on sandbox child spawning (EPERM), not a product failure. Direct node execution uses node:test without that child and executes all assertions. An initial fixture lacked a DOM listener stub; corrected before reported red evidence.

## SWE contract

- Share a defensible clock classification between header and reference labels. A clock snapshot can establish a closed interval up to its supplied next open; a short age alone must not invalidate that interval.
- Preserve explicit unknown/unverified market status when clock evidence is absent, invalid, future, incomplete, or beyond its verified boundary. Do not silently coerce missing is_open to false.
- Preserve timestamp visibility and distinguish prices from older sessions. Do not label arbitrary old trades official closing auction prices.
- Use exchange-local dates and actual broker schedule boundaries; avoid a fixed weekday or 24-hour assumption for weekends, holidays, early closes, and DST. If existing fields cannot prove a particular session, expose uncertainty rather than invent calendar certainty. The tests provide explicit next_open/next_close and observed date; they do not exhaustively prove exchange-calendar behavior.
- Keep execution freshness guard and quote polling/backoff/call volume unchanged. This suite verifies display only; source review must verify those non-goals.

## Independent acceptance still required

All tests green, independent negative cases around unknown/session boundaries, source review for unchanged execution and refresh cadence, then visible shared-browser UAT of header/watchlist/chart consistency without research or orders. VM tests are not pixel/layout/browser proof. Parent owns Gate transitions.

Reasoning session: `session-1792108334238-75564`.
