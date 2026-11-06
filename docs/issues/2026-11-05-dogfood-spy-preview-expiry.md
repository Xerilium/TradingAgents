# Dogfood 8: explain an expired SPY preview

## Status and observed failure

In progress from live dev8099 observations on 5 November 2026. Baseline
`453aca8`, `nautilus`, `D:/src/TradingAgents`; initial working tree clean.
All work stays integrated on this branch; no new branch or worktree.

The retained preview from the preceding item showed its last price check at
17:31:27 local time. At 17:40:34, the real UI still showed all 503 planned trades,
Preview was enabled and Submit disabled, with no expiry explanation or refresh
guidance. It still displayed “Submit queues this rebalance for the next regular
session.” Source currently uses a five-minute preview window on both sides.

This is a readiness-disclosure defect, not a claimed broker rejection or TTL
calculation repair. No Submit, approval, queue, enable/disable or other authority
action was used to establish it. Existing automatic trading was on and unchanged.
No new preview was needed for this initial observation.

Before capture (ignored):
`.local-workspace/dogfood-20261105/spy-preview-expiry-before.jpg`.

## Research and source diagnosis

Official sources accessed 5 November 2026:

- [Fidelity Placing Orders FAQ](https://www.fidelity.com/trading/faqs-placing-orders):
  primary read earlier in this session confirmed preview/edit before a separate
  submission and confirmation distinct from execution.
- [Fidelity Active Trader Trade Help](https://www.fidelity.com/products/atbt/help/ActiveTraderTools_Trade_Help.html):
  research worker reports a ticket-price refresh mechanism and verification
  before a separate Place action in that specific tool. It does not establish
  TradingAgents' validity duration, queue behavior or broker execution.

The source worker confirmed a presentation gap, not missing server protection.
The server's monotonic 300-second deadline begins before the response; the
client's five-minute display deadline begins after receipt and can be later.
A null token can mean zero legs or policy blockers, not expiry. Existing blockers,
busy, invalidated and queued/in-progress states remain distinct.

Plan: derive expiry only for a valid retained non-null-token preview whose
existing client deadline has passed and whose Submit eligibility is false. Add
an inline status naming the existing Preview SPY rebalance action. Keep the
original `canSubmit` expression, dry-run summary, full plan and filter unchanged.
Show the next-session hint only when the existing Submit control is available
(not busy, not replaced by queued cancellation) and the market is known closed.
No refresh request is triggered by this presentation change.

The warning updates on existing renders. State polling can skip unchanged or
hidden-page reads, so do not claim an exact idle-page deadline transition or
server-clock synchronization. One natural-expiry observation may use an ordinary
existing render if needed, without a new preview or artificial clock. Research
read the current attributed observation at
`memory://thinking/sequential/2026/11/06/session-1793929254689-46410` and the
preceding real-preview record at
`memory://thinking/sequential/2026/11/06/session-1793928248593-14002`.

## Investigation and scope

A dynamic workflow independently traces frontend/server expiry, render cadence,
null-token and blocker cases, and researches documented broker review/refresh
principles. Primary owns code and the built-in browser.

Fix only the visible expired-preview state: give an explicit reason and existing
Preview action, suppress an inapplicable current queue hint after expiry, and keep
the retained plan and view filter available for read-only inspection. Preserve
all original validity/admission checks, expiry duration, terms, token/payload,
account/revision binding and financial authority. No automatic refresh, countdown,
new timer engine or backend feature.

Use Impeccable Operate/harden and craft floor. Obtain fresh independent source
review with its own Impeccable context. Then one actual UI batch: one fresh preview
on the corrected frontend, inspect its initial state, wait for natural expiry,
and inspect the expired state without submitting. Do not shorten the TTL, alter
clocks, inject a preview or use tests/mocks. Waiting for the real validity window
is part of this same item; it does not start a new dogfood iteration. No private
settings or credentials, broker actions, research or production operation.
