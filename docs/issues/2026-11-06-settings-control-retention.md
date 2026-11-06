# Settings category and quote-rule controls

## Reproduced blocker and scope

Follow-up to924e204: Settings Trading Rules & Native Cache immediately lost e21
refs during ordinary updates. Reproduced on actual8099 before editing. Existing
review-control retention covered Markets/SPY, not required Settings path.
Native select click/read exposed only select refs, no option refs; Browser has
no select/keyboard/pointer action. Required quote-rule choices were unreachable
through the operator's allowed structured controls.

## Surgical extension

- Reuse unchanged Settings category and policy input/select/save/discard nodes
  after normal binding. Existing page/symbol/server/store context now also includes
  Settings category and investor revision. Changed semantic/disabled/context
  markup replaces controls; ordinary drafts, polling and conflicts stay intact.
- Normalize the fresh category tab's binding-generated aria-controls before
  exact comparison. Without this, the tab still replaced each render.
- Only Bid/ask spread and Quote freshness state choices and freshness session
  choices become labeled native radio groups using existing data-policy draft
  handling. Other rules/selects unchanged; no policy-save behavior/backend change.
- CSS keeps nested choice groups single-column and unboxed, using existing tokens.

## Actual verification

Built-in Browser8099 Settings12:27–12:29PST6November2026, normal reload only:
category e21 successfully opened Trading Rules. Same structured refs clicked
Apply this rule on spread/freshness and regular-session requirement; typed draft
spread25/age60 and freshnessopen60/closed60 across snapshot12:27:50→12:28:52.
Read-only DOM observed all draft values/checked states and native input focus.
Saved API policy remained revision1, both quote rules unset and cashfloor5%.
No Save risk-check choices, broker action, preview, injected event or automated
test. Own browser normal reload discarded this isolated unsaved draft; operator's
browser drafts/settings were not touched.

Independent review found choice-group CSS specificity collision; corrected with
explicit scoped1fr/padding0/border0. JS review found no retention/listener/policy
revision issues. Corrected review found no findings at app.js blob
`f71c2c3920eeb6ca415b144558d271e2880fb778`, app.css blob
`7e6b572632f51ecc239936f2a0ae845ef920aa75`; syntax/whitespace passed.

Static-only delivery:8099 serves updated app.js/app.css without backend/native
restart. Operator needs normal browser reload (unsaved local edits/preview will
be lost), then fresh refs. Exact draft choices/values and Save remain the
operator's separate actions. Other native selects remain outside this narrow
choice correction; no generalized custom dropdown or driver added.
