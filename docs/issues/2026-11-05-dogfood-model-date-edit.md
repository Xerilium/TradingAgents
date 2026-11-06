# Dogfood 11: preserve a partial native model date during polling

## Status and observed failure

In progress from actual dev8099 observations on 5 November 2026. Baseline
`987cbd2`, `nautilus`, `D:/src/TradingAgents`; initial working tree clean.
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
