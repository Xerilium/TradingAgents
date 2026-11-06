# Product dogfood loop

## Goal

Build a **personal index-management desk**. **SPY replication is the first shipping
priority and the reason to open the app every day.** Fidelity Trader+ and Robinhood
are usability references, not a reason to build a general-purpose trading suite.
Research, charts, simulations and other trading tools support this purpose.

Stay on this complete journey until it is release-ready:

**Understand the account and reserves → review the investment budget and dated
holdings → inspect the rebalance → use the authorized execution path → reconcile
outcomes and handle exceptions.**

Prioritize broken behavior, then jank, friction and missing essentials **within
that journey**. Work elsewhere only when it directly blocks this goal. A functioning
rebalance alone does not prove SPY return parity; tracking claims need qualified
account and benchmark evidence, with the actual method, dates and gaps stated.
Do not substitute hypothetical results or incomplete price-only evidence for
observed total-return parity.

Use this file as the standing brief for the completion-paced loop. Current human
instructions and the repository's security, preservation and trading-authority
rules still take precedence.

## Numbered cadence

Use [the development-loop ledger](issues/dogfood-loop-ledger.md) for the active
number, completed items and evidence. The new cadence starts at **loop 1** after
the human's 5 November 2026 instruction; do not retroactively number earlier work.

Choose the iteration type in this order:

1. **Every fifth loop is an alignment review**, overriding odd/even type. Review
   the immediately preceding four loops: 5 reviews 1–4, 10 reviews 6–9, and so on.
2. **Other even-numbered loops are UI work**: layout, clarity, interaction and
   Impeccable onboarding/critique/polish of the existing SPY journey.
3. **Other odd-numbered loops are non-UI work**: existing SPY logic, data correctness,
   safety, reliability and service/source contracts. Do not turn them into layout
   or UI-copy work, or invent backend features to occupy the slot.

Necessary documentation, independent review and affected real verification belong
with either implementation type; using the browser to verify non-UI behavior does
not make that a UI loop. Keep selecting the highest-priority in-journey item of
the scheduled type. Do not fill a slot with unrelated busywork.

At start, record the active number and type. At completion, record the actual
commit(s), issue/evidence, outcome, limits and remaining findings; advance the
number once. Resume an interrupted active loop rather than incrementing it.
Guidance edits, wakeups, notifications, retries and failed checks do not themselves
consume a number. Do not mark blocked or unverified work as completed.

An alignment review compares the preceding four deliveries with `PRODUCT.md`, the
SPY-first goal and current human direction. Check the actual diffs and recorded
outcomes, not just completion reports: contribution to the whole daily journey,
UI/non-UI scope, preserved capabilities and safeguards, independent review,
verification gaps and unresolved Impeccable findings. Record drift, missing
requirements, corrective priorities and a clear alignment decision in `docs/issues`;
link the review from the ledger and use it to order the following loops. A review
is not a new trade authorization or a reason to rerun passing checks, jobs or
broker actions. Preserve explicit unknowns and unexercised execution/return claims.

## Complete one item at a time

- Start from the actual checkout and running development desk. Preserve other
  work, commit your changes locally on `nautilus`, and do not create branch sprawl
  or push without permission.
- Dogfood the normal product at `http://127.0.0.1:8099/`. Do not add dogfood query
  labels, alternate interfaces, fake records or another server.
- Prioritize broken behavior, then jank, then friction, then missing features.
  Choose one discrete item that can be finished across its affected journey.
- Research the relevant source contracts and, where useful, official leader
  documentation. Separate documented capability from an adapted design principle.
- Use dynamic workflows for independent investigation and fresh code scrutiny.
  Keep implementation ownership clear. Do not duplicate a worker's investigation.
- Every UI implementer and reviewer must load the installed `impeccable` skill
  through the Skill tool. Run its context setup once per agent session, use the
  appropriate Operate playbook, and read its craft floor before UI edits. Use
  Read mode for documentation. Do not substitute a hardcoded asset-folder path
  for the installed skill or repeat setup on every iteration.
- Batch source fixes, obtain fresh independent review, and run the affected real
  browser smoke within the current task's authorization. If it fails, diagnose,
  fix and recheck the affected failed path as part of that same authorization;
  do not stop for another approval or repeat passing cycles. A failed observation
  is not a pass, and source review is not live acceptance. Automated tests still
  require their separate explicit authorization; no mocks or fabricated services.
- Do not use `AskUserQuestion`. Do not use the app wrap-up question/buttons to
  reauthorize development, navigation, static checks or affected local verification
  already covered by the task. Required app status stays recap-only for that work.
  Never encode a failed-local-check approval gate in an issue or wakeup prompt.
  Broker actions, credentials, destructive actions and genuinely new scope keep
  their existing separate authorization boundaries.
- Update the affected operating skill and product documentation in the same
  delivery batch. Record the reviewed revision, actual evidence and remaining
  limits in `docs/issues`; do not make the reader manage the delivery process.
- Commit the complete item and its evidence. Confirm the working tree's actual
  state before reporting completion. Broker actions remain separately authorized.

## Make index management the primary daily workspace

- Rethink navigation and layout so the complete SPY journey is the obvious daily
  starting point, not a feature buried under Orders. This is a shipping priority,
  not a claim that the current navigation already achieves it.
- Make the current situation and next useful action clear at a glance: account
  and reserve state, usable investment budget, dated holdings, proposed rebalance,
  execution/reconciliation state and any exception that blocks progress.
- Keep setup, editing and technical evidence secondary but accessible. Reuse the
  existing account, fund-plan, holdings, rebalance, execution and reporting paths;
  do not invent functionality or data to fill a design.
- Release readiness requires evidence across the complete journey, including
  exceptions and outcomes, not just a working preview or submitted request. Keep
  unexercised execution and unsupported tracking claims explicitly unproven.
- This loop does not authorize paper trades. The execution stage remains gated
  by separate explicit human authorization for the specific action. Preserve all
  existing verification, review, documentation, commit and authorization rules.

## Onboard, critique, then improve with Impeccable

The first UI iteration in the new cadence (loop 2, pending in the ledger) must
verify that this product and the SPY daily workspace are properly onboarded into
the installed Impeccable skill, then perform its critique. Once that checkpoint
is complete, consume its findings rather than repeating onboarding each loop.
Check the actual product/design context and applicable surface brief against the
human's current purpose and rendered product. Complete missing onboarding through
the skill's documented workflow; merely loading the skill is not onboarding.
Reuse context setup already completed in the same agent session.

Record the critique in `docs/issues`, tied to the reviewed source revision and
real 1920 × 1080 or larger observations. Prioritize concrete task-flow, hierarchy,
density, space-use and interaction problems. A functional navigation check is not
visual-design approval. Do not invent capabilities or data to fill a layout.

Use those findings as the improvement backlog for subsequent loops. Complete one
coherent item or coordinated batch at a time, record what was actually resolved,
and retain outstanding findings instead of restarting the critique every loop.
Keep using installed Impeccable to polish and improve the product: choose its
appropriate polish, layout, distill, clarify or harden playbook for each UI batch,
not just for the initial critique. Verify the affected rendered result without
repeating passing cycles. All existing scope, review, documentation, preservation
and trading-authorization boundaries remain in force.

## Design for a glance

Target **1920 × 1080 (1080p) or higher**. The user will not run the desk below
1080p. Do not spend implementation or verification cycles on phone, tablet or
smaller-window layouts. Set the browser viewport to at least 1920 × 1080 for
visual checks, even when the embedded pane scales its displayed image down.

Use simple English and a deliberate layout. Visible content should help the user
understand the current situation or take the next action.

- Lead with the stock or portfolio, the relevant state, and the next useful action.
- Group related controls; preserve clear selection, focus, scroll and navigation.
- Prefer concise labels and readable values to paragraphs and a textbox for every
  internal setting. Show editing controls when the task calls for editing.
- Remove repeated disclaimers and explanations that do not change a decision.
  Put detailed provenance, receipts, raw data and uncommon options behind clear
  disclosures or in the product reference.
- Keep material blockers, stale or missing decision inputs, exact order terms,
  and the distinction between approval and submission visible where they matter.
  Simplify the explanation, not the underlying protection.
- Avoid technical jargon in the main task flow. Use exact codes or identifiers
  only where the user needs to inspect them, with a plain-English label.
- Use the installed Impeccable distill, clarify, layout, adapt or harden playbook
  as appropriate. Do not turn every refinement into a global redesign.

## Keep the guide as useful as the product

- `README.md` is the illustrated introduction and task-led product guide. Keep it
  polished, concise and accurate; link to deeper references instead of dumping
  every control and caveat into it.
- `docs/platform-reference.md` explains capabilities, workflows and source paths.
  `docs/local-desk-guide.md` covers launch, storage, recovery and acceptance evidence.
- Update the versioned `.agents/skills/use-tradingagents/` source and synchronize
  only its affected files to the installed skill, comparing before overwrite.
  Keep its references aligned with verified labels, routes, prerequisites and action effects. Preserve the
  distinction between current observation, historical evidence and source-only
  behavior without repeating warnings beside every control.
- Save useful real screenshots during authorized work. Keep raw evidence ignored;
  put selected, privacy-reviewed guide images in `docs/images/` and commit them.
  Check for credentials, account identifiers, private notes and unrelated desktop
  content before promotion. Crop or visibly redact private information; never
  fabricate a cleaner result or alter financial values to imply different behavior.
- Use a few strong screenshots with short captions that explain a task. Keep
  capture date, source revision, viewport and limits in the image notes. Replace
  obsolete screenshots when the pictured workflow changes. Do not run research,
  simulations or broker actions just to manufacture a prettier README.

## Schedule after completion

Request the next iteration 60 seconds after the current item finishes. Use one
dynamic wakeup, not overlapping recurring timers. Disclose scheduler rounding
when it makes the actual delay longer. While work is running, its completion
notification is the wake signal; use only a long fallback if needed. Each wakeup
must read this file so updates to the standing brief are not lost in an old prompt.
