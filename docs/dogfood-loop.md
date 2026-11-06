# Product dogfood loop

## Goal

Build a trading desk that is clear, dependable and useful beside Fidelity Trader+
and Robinhood. The main journey is holding discrete stocks to track or exceed the
S&P 500. Research supports that goal; it is not a reason to add unrelated features.

Use this file as the standing brief for the completion-paced loop. Current human
instructions and the repository's security, preservation and trading-authority
rules still take precedence.

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
  browser smoke within the current task's authorization. Keep automated tests to
  the repository's explicit authorization rules; no mocks or fabricated services.
  Do not ask again for ordinary steps already authorized. A failed observation is
  not a pass, and source review is not live acceptance.
- Update the affected operating skill and product documentation in the same
  delivery batch. Record the reviewed revision, actual evidence and remaining
  limits in `docs/issues`; do not make the reader manage the delivery process.
- Commit the complete item and its evidence. Confirm the working tree's actual
  state before reporting completion. Broker actions remain separately authorized.

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
