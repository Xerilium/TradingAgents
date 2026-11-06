# Dogfood 8: explain an expired SPY preview

## Status and observed failure

Completed implementation `93070a3`, fresh independent source review and one
natural-expiry live UI batch on 5 November 2026. Baseline `453aca8`, `nautilus`,
`D:/src/TradingAgents`; initial working tree clean.
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

## Source implementation and checks

The presentation now derives `previewExpired` for a retained token, false existing
Submit eligibility and a passed existing client deadline. It adds an inline
status naming Preview SPY rebalance. The next-session hint requires an available,
non-busy Submit control that is not replaced by queued cancellation. The original
`canSubmit` expression and all handlers, token/terms, TTL and backend are unchanged.
The dry-run summary, full retained plan and view-only filter remain intact.

Candidate blob: `072176cb38030c8dc2cd01fff06bc514fa36a5f6`.
Delta: 3 added / 1 removed JavaScript lines; no CSS/backend/test changes.
JavaScript syntax and Git whitespace checks passed. The Impeccable detector
reported only the pre-existing `#4dabf7` advisory at line 2378, outside this change.
No automated tests or mocks. A separate fresh independent reviewer found no
confirmed actionable findings against `a050feb` and the recorded blob, committed
as `93070a3`. The reviewer ran Impeccable context and read PRODUCT, DESIGN,
Operate, harden and craft floor. Source coverage included client/server deadlines,
all preview/token/blocker/queue states and preserved financial handlers. The
reviewer explicitly retained the earlier-server-deadline and next-render caveats.
The single natural-expiry live observation is complete; evidence and limits follow.

## Live observation checkpoint

Primary loaded `93070a3` in the real dev8099 browser and selected SPY Rebalance.
One fresh Preview action completed; at `2026-11-06T01:45:51.345Z` (17:45:51 local),
Preview was enabled, Submit enabled, no expiry message appeared, and the closed-
market queue hint was present. The retained summary/count showed 503 planned
trades, policy revision 0 and target exposure 99.91%. No Submit or authority
control was used. No token/whole API response was read or printed.

Initial ready-state capture (ignored):
`.local-workspace/dogfood-20261105/spy-preview-expiry-fresh.jpg`.

The same preview was left open past its natural validity window. No reload,
new preview, altered clock/TTL or new dogfood item occurred during the wait.

## Natural-expiry evidence and decision

Primary resumed this same batch at `2026-11-06T01:52:23.404Z` (17:52:23 local),
more than six minutes after the initial ready-state observation. Before any
navigation, input or manual render action on resumption:

- The actual rendered warning read “This preview has expired. Select Preview
  SPY rebalance to review a new plan before submitting.”
- Submit was disabled, Preview remained enabled and the queue hint was absent.
  The retained dry-run summary, Proposed trades (503) heading and 503-of-503
  count remained visible. Existing automatic trading was still on and unchanged.
- Native lookup of AAPL still showed 1 of 503 and its retained BUY quantity
  22.316587347, while the warning persisted and Submit stayed disabled. Clear
  restored all 503 rows without re-enabling submission or requesting a preview.
- Browser console inspection reported no errors. At 1024 × 768, the warning,
  controls and retained review content rendered without horizontal page overflow.
  No broker action, approval, queue, authority toggle, fund-plan save, research,
  simulation, runtime installation or production operation occurred.

Primary decision: accept the discrete expiry-disclosure correction after fresh
source scrutiny and this one real natural-expiry batch. Only one validation
preview was created; the expired retained preview remained the same afterward.
No clock mutation, shortened TTL, fabricated record, automated test or mock.

This proves the observed ready and post-deadline UI states, not an update at the
precise deadline, behavior while every page is hidden/idle, or synchronization
with the earlier authoritative server deadline. Server rejection, null-token,
policy-blocked, queued/in-progress and account/revision-invalidated combinations
remain source-reviewed, not separately exercised. Broker execution is unverified.
Browser captures and DOM were inspected; no joint user-visible acceptance claim.

After capture (ignored):
`.local-workspace/dogfood-20261105/spy-preview-expiry-after.jpg`.

Continue the requested completion-paced loop with a one-minute delay, dynamic
workflows, fresh independent code scrutiny and all local commits on `nautilus`.
Scheduler minute-boundary rounding can exceed 60 seconds.
