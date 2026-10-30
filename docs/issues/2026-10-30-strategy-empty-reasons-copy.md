# Completed experiment shows a false empty-comparison message

Status: Reproduced; source review approved; installed verification pending
Owner: Codex subagent `strategy_layout`
Coordinator: Codex parent
Reported: 30 October 2026

## Real reproduction before the fix

The coordinator opened completed experiment
`d2a35c96-21a3-47e5-919a-f09081fd3742` in Strategy Lab > Preview & Results.
The page shows **No comparison rows retained.** directly above nine populated
comparison rows. The independent reviewer inspected the real result: `reasons` is an
empty array and `comparison` contains the nine retained rows.

The worker inspected the captured result screenshot:
`C:/src/printer/.local/strategy-lab-results-20261030.jpg`.
It visibly confirms the contradictory message, Completed status and populated
table. No extra experiment was created or run to establish this reproduction.

## Source and documentation reviewed

`experimentResults` calls the generic `experimentTable` for `result.reasons`.
That helper renders **No comparison rows retained.** for an empty array.
The later comparison-table call has real rows; it is not the source of the
empty message. The existing platform reference, local desk guide, product
context, Impeccable Operate guidance and craft floor govern this scoped change.

## Targeted change and acceptance

Omit the reasons-table call when no reason rows exist. Preserve nonempty
reason rendering and every real comparison/result table. Do not change the
shared table helper's behavior for other callers or alter calculation data.

Acceptance: reopen the same completed result and confirm the false message is
absent while the nine existing comparison rows remain. No simulation rerun,
backend change, dependency change or general wording overhaul is required.

## Source review

Independent reviewer `strategy_preview_fresh_review` approved the single
expression change at `app.js` SHA-256
`329ab865fdcda02544ab7eb515cca446885bf68c9a5ea1cf58f0022dd1e1b8ad`.
It suppresses only the inappropriate message for an empty reasons array and
preserves nonempty reason arrays and real comparison rows. The reviewer also
approved the separate UI-only deployment mode, which permits changes only to
`app.js` and its wheel record and retains artifact/preservation checks.
