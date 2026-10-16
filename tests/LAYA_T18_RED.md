# T-1.8 independent red review

2026-10-15. HSM `session-1792114277869-34223`.

## Verdict

**Source and offline contract checks PASS. Final acceptance PENDING real-model controls and browser UAT.** No blocking defect found in the reviewed change. This does not establish semantic reliability of Laya's financial evidence classification.

## Source findings

- `laya_review.approved_review` requires a dictionary envelope and audit, exact `research-choice-v1`, the complete current question mapping, multilingual model, high threshold, adapter `auto_execute`, and dictionary answers with exact A for both expected question names. Boolean, unknown, missing, malformed, and negative values do not pass.
- `prepare_review` persists that version with a deep copy of the exact preflight parameters. Questions distinguish research evidence sufficiency from order readiness and require both supporting and opposing criteria. Full-request token checking and the 256-token reserve are unchanged.
- `DeskService._review` recomputes approval from the persisted raw assessment and audit rather than trusting the historical `auto_execute` flag. `propose` invokes it before storing executable proposals. `_submission_guard` invokes it again before submission and at the actual dispatch boundary; the existing evidence digest detects changes since proposal review. Legacy saved results are not rewritten.
- Paper-account validation, manual submission, market/quote freshness, account/config/date identity, position sizing, uncertain-outcome protection, and submission-intent checks remain unchanged. Read those call paths, not just the patch.
- Compact store serialization preserves question-contract provenance. Watchlist cleared filtering excludes legacy results; review filtering includes legacy and current non-cleared results. Current negative answers with an adapter confidence grade of auto_execute display Review required in the review label. Detailed reports retain original A/B values with readable meanings, and historical results remain labelled legacy.

## Independently executed checks

All commands used `rtk proxy` and the existing hard child deadline helper.

- 60-second bound: `pytest tests/test_laya_choice_contract.py tests/test_paper_service.py tests/test_laya_review_budget.py -q --tb=short`: **259 passed in 26.02s**.
- 30-second bound: `pytest tests/test_paper_engine.py tests/test_report_html.py -q --tb=short`: **80 passed in 1.26s**.
- 30-second bound: `node --test tests/ui_gate_regressions.cjs`: **21 passed**, including neutral meanings, historical labels, review/cleared filters, and previous report-scroll/settings/quote controls.

These cover exact approval and rejection mapping, changed audit version/questions/model/threshold at submission, historical proposal rejection without mutating source results, compact provenance, budget behavior, existing execution guards, and rendered HTML. They are not actual browser or actual-model results.

## Live evaluation handoff

Reviewed `tests/laya_choice_controls.json` and `tests/laya_live_control.py`. The four deliberately synthetic cases isolate A/A, B/B, B/A and A/B; the positive case correctly includes ordinary future uncertainty and closed-market execution restrictions. Reversed criteria preserve label meanings and expected answers. They are valid discriminating controls, not real investment recommendations.

The runner loads the current production questions, uses multilingual/high, records an exclusive receipt before dispatch, preflights each exact input, refuses a second inference dispatch, and compares per-question sequence hashes and token counts. Run one case at a time under its documented 85-second outer deadline. A timeout is an unknown outcome, not permission to rerun or clear its receipt; native compute may continue. A zero exit status proves transport checks only: acceptance must explicitly inspect `semantics_match`, observed labels, adapter contract, model and context metadata in every receipt. The runner intentionally does not assert semantic success.

Still required: all four cases in both criterion orders; saved META regression with unreconciled source gaps; readable current and legacy UI with correct review filters; current deployment and audit evidence. Reject semantic false positives or position dependence rather than lowering the threshold or redefining negative controls. Preserve independent execution guards regardless of model outcome.

## ConfessionReport

Changed only this report. Inspected current source, worker handoff, blue-team fixtures, domain review and runner; independently ran 339 Python tests and 21 JavaScript tests. No inference, provider calls, broker calls, browser automation, deployment, configuration change, commit, Gate transition, or historical research edits. No durable semantic memory source was used. Final acceptance remains pending live evidence.
