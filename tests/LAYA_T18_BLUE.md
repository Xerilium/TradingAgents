# T-1.8 blue-team evidence

2026-10-15. HSM `session-1792113956888-65756`.

Added only `tests/test_laya_choice_contract.py`, `tests/laya_choice_controls.json`, and this report. No production edits.

## Verified red baseline

Command (60-second hard child deadline):

```
rtk proxy .venv/Scripts/python.exe .paper-desk/run-bounded.py --seconds 60 -- .venv/Scripts/python.exe -m pytest tests/test_laya_choice_contract.py -q --tb=short
```

Result: **5 failed, 23 passed in 3.89 seconds**, exit 1.

Failures demonstrate:

- Questions still use yes_no instead of neutral A/B choice.
- Persisted review lacks `question_contract_version`.
- Confident exact A/A incorrectly fails application approval.
- Historical-style boolean true/true still receives application approval.
- Unversioned historical boolean approval still produces an executable proposal.

Passing controls cover B/A and A/B denial, missing/unknown/numeric/nested/boolean-shaped answers, absent answers, malformed envelopes and non-auto_execute grades. Some malformed envelopes legitimately fail the research result; the asserted invariant is no published approval, not a forced completed status. Exact raw answers remain asserted in the passing-path test. Preflight question equality, summary field names, and exact rating preservation are also asserted.

The first harness run was invalid because this Windows environment's offline socket guard needs the existing `_allow_event_loop_pipe` fixture imported into the module. That import was added; the final run above has no warnings and reaches the real service decision path. Do not count the initial harness failures as product failures.

## Controls and bounded live handoff

`tests/laya_choice_controls.json` has four labelled synthetic states covering A/A, B/B, B/A, A/B, each with the unchanged six summary fields and exact recommendation equal to rating. Definitions derive from `tests/LAYA_DOMAIN_REVIEW.md`; the missing-source case explicitly names the failed essential report, while the contradictory-source case deliberately preserves a conditional Hold. The positive case includes future uncertainty and a closed-market execution restriction without pretending those invalidate research evidence.

Each `controls[]` entry supplies `id`, `expected`, and `state`. Add the production revised questions and unchanged multilingual/high settings at execution time. For reversal, reverse the criteria insertion order to B,A and preserve the A/B descriptions and expected answers. Preflight every exact request and record per-sequence counts/hashes; compare inference inputs against those. These are deliberately synthetic, not actual financial recommendations.

No model evaluation was run. Passing offline tests cannot establish semantic discrimination. All four forward and reverse controls plus the saved META case still need bounded evaluation; a correct neutral-choice mapping alone is insufficient.

## Remaining developer/UAT requirements

- Introduce a stable nonempty question-contract version into the persisted audit. Reject unversioned historical approvals at proposal creation without editing saved results.
- Preserve independent execution guards and 0.9/high contract threshold.
- Show readable meanings alongside A/B and identify historical boolean assessments as legacy. Browser/DOM label tests were not added in this Python-only ownership scope; independent UI verification remains required.

## ConfessionReport

Wrote only the three assigned test/control/report files. Used current local source, domain review, and existing offline service fixtures. Did not run providers, broker calls, live inference, browser automation, commits, Gate transitions, or change settings. The fixture shape is validated; semantic accuracy is explicitly unverified. HSM completed with this same scope and limitation.
