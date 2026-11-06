# Dogfood 11: preserve a partial native model date during polling

## Status and observed failure

Source correction complete with fresh review; the single live batch failed on
the earlier revision and final product acceptance remains open. Baseline `987cbd2`, `nautilus`, `D:/src/TradingAgents`,
actual dev8099 observations on 5 November 2026; initial working tree clean.
All work stays on this integrated branch; no new branch or worktree.

Primary followed the native Model proposal as-of-date edit. With the existing
blank date, clicked the month and pressed 1 twice. The rendered editor showed
`11/dd/yyyy`, with the day segment selected. No complete as-of term or model
request was created. Model capital stayed at the existing 10000.

After ordinary background state refresh advanced from 02:32:35 to 02:33:05 UTC,
the field reverted to `mm/dd/yyyy` and month selection. The active element still
had id `portfolio-model-as-of`, but a debug reference to the earlier element was
disconnected and was not the current node. Its `.value` was empty while incomplete;
copying that property does not preserve the native segmented editor state.
The model job remained idle. This is editing loss, not a claimed model-run failure.

Ignored before captures under `.local-workspace/dogfood-20261105/`:
`model-date-edit-before-partial.jpg`, `model-date-edit-before-lost.jpg`.

## Investigation and constraints

Dynamic workflow `wf_8e111531-b94` independently traces render/input restoration
and researches the native date-value contract and relevant source lessons.
Primary owns implementation and the built-in browser. Preserve native partial
segments and focus across ordinary polling with the smallest scoped correction.
Do not change date/capital semantics, model payloads, eligibility, job admission,
explicit reset/restore/navigation behavior, disabled states or trading authority.
Do not disguise the date as a list search or add another renderer/state store.

Use Impeccable Operate/harden and craft floor before editing. Obtain fresh
independent code scrutiny with its own context setup, then one actual native-edit
smoke using the same partial-month interaction and real background refresh. Clear
the unsaved partial edit afterward; do not activate Model portfolio. No fabricated
job state, automated test, mock, provider job, private configuration/credential
inspection, production operation or broker action.

## Diagnosis and scoped plan

Independent source diagnosis confirmed that the five-second read calls the full
renderer. `main.innerHTML` disconnects the native date editor; capture/restore
copies its empty `.value` and refocuses a replacement, losing partial segments.
The existing list-query node swap also happens after disconnection, so the date
must not be relabeled as a list search or assumed safe with that swap.

Primary verified the [HTML Date-state sanitization contract](https://html.spec.whatwg.org/multipage/input.html#date-state-(type=date)):
a value that is not a valid date string is sanitized to an empty string. The
research worker also read [MDN date input](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/date)
and [badInput](https://developer.mozilla.org/en-US/docs/Web/API/ValidityState/badInput).
These distinguish normalized values from browser UI state; they do not guarantee
that every incomplete edit sets badInput or that assigning `.value` preserves
native segments. This is a browser-editing requirement, not a claimed feature
comparison with a particular broker.

Plan: identify the actual periodic read explicitly, distinct from ordinary user
renders. Only for the same store/server, same model job identity/status, same
Portfolio proposed context and an editable focused as-of field, retain the
existing connected model-controls group. Parse the freshly generated markup,
compare the group's full markup after normalizing cloned input value attributes
to their live values, and retain it only when authoritative values, input type,
constraints, disabled/readonly state, button state and copy are unchanged.
Reconcile the other direct main children around that group without detaching it;
continue normal ledger/result/chrome updates. Do not assign or refocus the retained
input through the generic restore path. Otherwise use the existing full render,
including forced refresh, explicit actions, navigation, restore/generation changes,
job transitions and changed control semantics. This is one scoped connected-island
exception, not a new renderer, custom date editor or partial-date state store.

Fresh code scrutiny will check these admission/fallback boundaries. The single
live smoke will repeat month-only entry through a real changed snapshot, inspect
connected node/visible segment state, continue native keyboard editing, and clear
the unsaved date without starting a model. Job/restore/constraint combinations
will remain source-reviewed where no real state already exists.

## Source implementation and checks

Implementation `cfdb5ec` marks only the existing five-second state read as
periodic. Admission requires unchanged server/store and model job id/status.
The renderer additionally requires its normal same-context saved input and the
focused editable date. `retainModelDateControls()` compares freshly parsed group
markup with a clone whose input value attributes reflect current live values.
Only compatible groups are retained. Other direct main children are refreshed
around the still-connected group. The generic focus/value restore is skipped
only for that retained date; all other rendering and fallback paths remain.

Candidate app.js blob `902f62352eb21f6afc6beb1e370ec037952e38b7`.
Delta: 21 added / 4 removed JavaScript lines. No CSS/backend/test changes.
JavaScript syntax and Git whitespace checks passed. Manual Impeccable detector
reported no anti-pattern failures and only the pre-existing `#4dabf7` advisory,
now at line 2395 after this insertion. Regex-only source scanning is not runtime
or rendered accessibility acceptance. No tests or mocks were added or run.

Fresh independent review `wf_e50859b3-d61` found no actionable defects against
`cfdb5ec77b02d50b12693a566c60b5f5169a7857` and verified the candidate blob.
The reviewer ran its own Impeccable context once and read Operate, harden, craft
floor, PRODUCT and DESIGN. Review covered actual polling admission, compatible
connected-group replacement, generic restore bypass and fallback boundaries.
It was source-only; native browser behavior was not inferred from the review.

The single actual native-edit batch is in progress on the reviewed source.
Initial state was idle with blank date and snapshot sequence 1415 / update
2026-11-06T02:40:17.415684+00:00. Native month-only keys again displayed
`11/dd/yyyy` with the day selected. No model action was used. The same editor is
being left focused through an ordinary changed snapshot before acceptance.

The first stored DOM reference preceded focus/typing and could legitimately be
replaced before the edit began, so it is not identity evidence for this case.
The later actual screenshot at update 02:41:19 still showed `11/dd/yyyy` with the
day selected. A fresh reference was captured while that same edit remained
focused at sequence 1432 / update 02:41:49 for the connected-node observation.

During this batch the user questioned the `?dogfood=...` reload label. It is not a
product mode: the page loads the normal `/static/app.js` and other standard
scripts; the static JavaScript has no dogfood branch. All implementation is in the
existing product source on `nautilus`, not a separate UI/server. Stop adding these
unnecessary labels and return to clean `http://127.0.0.1:8099/#portfolio` after the
in-progress native edit. Production remains untouched.

## Failed live batch and revised source plan

The single authorized live batch did not establish acceptance. After capturing
references while the date was already focused at sequence 1432 / 02:41:49, state
advanced to sequence 1441 / 02:42:20. The old date/group were disconnected and
replaced; the screenshot again showed `mm/dd/yyyy` with month selected. Surrounding
ledger/result nodes updated too, and the job remained idle. Some intervening
updates had preserved the visible partial month, but that is not a pass for the
whole observed editing interval.

Source inspection shows that ordinary focus/visibility refreshes call `readState()`
without the periodic-only flag. Other non-forced feedback renders can also bypass
that flag. The exact caller of the observed replacement was not instrumented;
these are confirmed uncovered source paths, not a claimed runtime stack trace.

Revised plan: remove polling-origin plumbing. Retain the compatible focused date
on any normal same-context non-forced render. Encode server/store and model job
id/status in the existing control group's markup so full-group comparison still
rejects changed context, authoritative values, constraints, editability or action
state. Keep forced/reset/navigation behavior and all handlers unchanged. No second
live round is authorized by this failure. Correct source, obtain fresh review,
commit it, and request fresh human authorization for one more affected smoke.
The partial date is cleared by returning to the clean normal product URL; no
model request, research/provider job, approval or broker action occurred.

## Corrected source review and handoff

Correction `b0155a6c7f172a32735564facee4052ce623419e` removes the periodic-only
argument/plumbing and scopes retention at the common non-forced render boundary.
The same normal group markup now carries an escaped server/store/job context;
its comparison rejects changed identity/status as well as changed values and
control semantics. The original connected-island helper and surrounding updates
remain; no custom date state, alternate mode or parallel UI was added.

Final app.js blob: `d8d6c0800266e30a49d1116ceb78c0633996bc4c`.
Final delta against `65eca6f`: 18 added / 2 removed JavaScript lines, no CSS,
backend or test changes. Syntax/whitespace checks passed. The source detector
again found no anti-pattern failures, only the existing palette advisory now at
line 2394. No automated tests or mocks were added or run.

Fresh independent review `wf_b66bee12-ec3` found no actionable source defects
against that exact revision/blob and confirmed this is the existing product UI,
with no dogfood query handling in static source. The reviewer ran its own
Impeccable context and read Operate, harden, craft floor, PRODUCT and DESIGN.
It performed no browser/runtime check and did not claim the failure resolved.

Primary decision: source correction is ready, but do not accept the item or claim
completion of the native-edit journey. The one authorized live batch failed on
`cfdb5ec`; no second batch has run on `b0155a6`. The normal browser was returned to
`http://127.0.0.1:8099/#portfolio`, clearing the unsaved partial date. No special
query is needed to load the normal product source. Installed production is not
updated by this local development work.

Pause the completion-paced loop pending fresh human authorization for one more
affected smoke on the clean development URL. That batch should cover the partial
month through changed snapshots and ordinary focus/visibility refresh, connected
node plus surrounding updates, keyboard continuation and clearing, without a
model run. Job/restore/constraint transitions, other browser engines and full
model/broker execution remain source-reviewed or unexercised. Preserve the failed
batch evidence rather than relabeling it a pass.

Failed capture (ignored):
`.local-workspace/dogfood-20261105/model-date-edit-failed-smoke.jpg`.
Reusable lesson saved at
`memory://knowledge/projects/tradingagents/tradingagents-partial-native-dates-need-connected-editing-state-across-normal-renders`.
