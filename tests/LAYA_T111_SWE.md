# T-1.11 implementation evidence

The desk passes its actual configuration into declared graph state as
`desk_execution_policy`. Research manager, trader, portfolio manager, and all
three risk debators consume it. The denominator is the configured universe, not
the selected research subset. Desk-only structured schemas remove requests for
invented numerical position sizing; upstream callers retain their original
schemas. The deterministic engine and its rating-to-quantity behavior are unchanged.

The UI explains policy-owned quantities and opens the proposal's associated
research run. New social evidence carries `stance-contract-v1`; uncertain posts
show their raw prediction and grade. Historical counts and retired Laya blockers
are labeled, preserving original records. Closed-market research context now
distinguishes a same-session reference from execution freshness, without calling
an IEX last trade an official close or changing validity checks.

## Offline verification

- Blue-team baseline: 8 failed, 4 passed in allocation context tests.
- Allocation, successful structured schema invocation, structured agents, paper
  service, and social tests: 293 passed in 20.86 seconds (before the final quote
  wording addition).
- Final focused allocation, schema, quote refresh, and social projection tests:
  25 passed in 1.24 seconds, including the quote wording addition.
- UI regression suite: 25 passed, including exact proposal-to-run navigation,
  preserved historical counts, raw stance grades, and retired blocker labels.
- Python checks found two import formatting issues; both were corrected.

Tests use fake models and brokers. The new schema tests capture the schema used
by successful `invoke`, cover desk and ordinary callers, and forbid fallback.
No model call, broker order, process restart, or deployment was performed by this
worker. Independent review, running-UI verification, and the PM's bounded live
acceptance remain separate evidence; these offline checks do not establish them.
