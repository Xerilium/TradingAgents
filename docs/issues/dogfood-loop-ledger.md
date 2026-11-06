# Numbered development-loop ledger

This records development delivery, not investment research or a trading decision
log. Rules and product goals live in [the canonical brief](../dogfood-loop.md)
and [PRODUCT.md](../../PRODUCT.md). Per-item evidence stays in its issue.

## Current position

- Cadence introduced by the human on **5 November 2026**.
- Next iteration: **1 — non-UI**, pending.
- Active iteration: none.
- Last completed numbered iteration: none. Earlier work is not retroactively numbered.
- Next alignment checkpoint: **5**, reviewing iterations **1–4**.
- The requested Impeccable onboarding verification and proper SPY-layout critique
  are queued for **2**, the first UI slot. Use the resulting findings as the UI
  backlog for later loops and keep applying the relevant Impeccable playbooks.

## Iterations

| Number | Type | State | Scope / outcome | Commit(s) and evidence |
| --- | --- | --- | --- | --- |
| 1 | Non-UI | Pending | Select the highest-priority existing SPY logic/data/safety/reliability item after inspection. No item has been investigated or accepted yet. | — |
| 2 | UI | Pending | Verify Impeccable product/surface onboarding, complete any missing onboarding through its documented workflow, then critique the actual SPY workspace at 1920 × 1080 or larger. Record prioritized findings for subsequent loops. | — |
| 3 | Non-UI | Pending | Select from current in-journey priorities after loop 1. | — |
| 4 | UI | Pending | Address one coherent prioritized item/batch from the Impeccable findings. | — |
| 5 | Alignment review | Pending | Review the actual deliveries and evidence from 1–4 against the product goals, record drift/gaps/decision and reorder subsequent work. | — |

Update the active/next/completed fields and row together. Add later rows as the
cadence advances; multiples of 5 are reviews regardless of parity. For example,
6 is UI, 7 non-UI, 8 UI, 9 non-UI, and 10 reviews 6–9. Resume an interrupted active
number. Notifications, corrections to loop guidance, retries and failed checks do
not advance it. Do not invent completion evidence or fill a scheduled slot with
unrelated work.

## Cadence setup evidence

Baseline `ff28cfa`, branch `nautilus`, with unrelated README edits preserved.
This change records the human's scheduling/delivery rule only; it starts no app
workflow, research, provider job, simulation, automated test, mock or broker action.
No numbered iteration is consumed by establishing the cadence.

Fresh read-only instruction review `wf_a81ddf84-62b` found no concrete defect in
the parity/review precedence, preceding-four examples, restart/counter rules,
SPY-first/Impeccable scope or safety boundaries. It checked the relative links
between the brief and this ledger, not every external reference. Reviewed blobs:
brief `dd434bd483a9348f439956bce4fea11dec9de27c`; ledger before this evidence
append `b6e50105acb3d9bd750511c5aa264d9945d1bb7a`.

Primary accepts this instruction-only change for local delivery on `nautilus`.
Whitespace checking passed; application-code and test changes are both zero.
The single future wakeup reads the brief and ledger before choosing its numbered
slot. Unrelated README edits remain untouched and outside this commit.
