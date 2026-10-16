# Laya evidence-gate domain review

Read-only review, 2026-10-15. Reasoning HSM: `session-1792113855379-76817`.

## Finding

Fixing `act_probability` mapping is necessary but does not establish that the research gate discriminates valid evidence from incomplete evidence. Current `tradingagents/web/laya_review.py:17-28` asks two `yes_no` questions; the installed adapter's `src/laya_mcp/core/schema.py:34` maps that kind to `noul`. Both use only affirmative criteria. `tradingagents/web/service.py:998-1002` permits the research gate when the adapter contract is `auto_execute` and both returned values are boolean true. `tradingagents/paper/engine.py:232` and service `_review` consume that persisted permission.

The saved `.paper-desk/laya-single-forward-validation.json` demonstrates full, untruncated multilingual input but reports evidence_complete=true at 0.9935 and decision_consistent=true at 0.9916. Its `parameters.state.summary.unresolved_gaps` explicitly contains unreconciled financial period/date inconsistencies and conflicting price records. It also preserves missing capex guidance, financing terms, earnings report and unavailable FRED data. Therefore confident acceptance is not evidence that the semantic gate works. Some omissions are normal investment uncertainty rather than necessarily rating-invalidating, but the question's existing affirmative criterion explicitly requires no material source errors or missing information. The source/date inconsistencies warrant a negative control, not automatic acceptance.

The final rating can be consistent with conditional evidence while execution remains forbidden: summary preserves Overweight, a deferred conditional position, and no approved immediate full allocation. Do not conflate missing execution quotes with invalid research, nor treat a conditional Overweight as permission to submit.

## Primary-source grounding

- [Official model card, Honest Limits](https://huggingface.co/convaiinnovations/laya/blob/main/README.md#honest-limits), accessed 2026-10-15: boolean option labels may dominate state; recommends neutral two-option choice as a mitigation. Also warns of base-checkpoint overconfidence and advises domain calibration. This is a documented risk, not proof of the precise cause of this META answer.
- [Upstream issue 156](https://github.com/NandhaKishorM/laya/issues/156), accessed 2026-10-15: reproductions compare changed labels and positive/negative inputs. This establishes why testing only one polarity is inadequate. Those sentiment tests do not validate financial-domain behavior.
- Installed source paths above; saved source/summary at `.paper-desk/laya-saved-packet-review.json`; exact inference receipt at `.paper-desk/laya-single-forward-validation.json`.

## Minimal recommended correction

1. Keep the two evidence checks and multilingual/token-budget path. Change this application's questions to `choice` with neutral keys A/B and explicit, contrasting descriptions. Avoid true/false and yes/no keys. Do not change global adapter boolean semantics as part of this application fix.
2. Evidence question: A means sources support assessing this rating with no unresolved material source contradiction or absent essential evidence; B means a material source contradiction, failed essential source, or absent essential evidence prevents that assessment. State that ordinary disclosed future uncertainty is not by itself missing evidence. The distinction needs a testable product definition rather than a requirement for perfect foresight.
3. Consistency question: A means the rating follows the evidence and respects counterarguments and conditional restrictions; B means unsupported/REVIEW rating, contradicted claims, or a rating that discards a material restriction. Neither answer authorizes an order.
4. Application mapping must require the exact expected A value for both questions plus the existing confident contract. Reject absent/unknown/malformed answers. Version the question contract in the persisted audit so historical boolean outputs are not silently reinterpreted. Preserve raw answers for audit and render understandable labels alongside A/B.
5. Keep independent paper/account/quote/sizing/submission guards unchanged. Do not loosen the 0.9 threshold to make the saved sample pass. Do not replace the model with a regex that blocks every nonempty unresolved_gaps string: valid summaries explicitly state when there are no gaps.

## Discriminating acceptance controls

Concrete proposed schema (adapter `core/schema.py:120-130` accepts a choice criteria mapping):

```json
{
  "evidence_complete": {
    "kind": "choice",
    "instructions": "Classify research evidence quality, not order readiness. Disclosed future uncertainty alone is not missing evidence.",
    "criteria": {
      "A": "Essential source evidence is present; no material unresolved source error, contradiction or missing fact prevents assessing the rating.",
      "B": "An essential source is missing, or a material unresolved source error, contradiction or missing fact prevents assessing the rating."
    }
  },
  "decision_consistent": {
    "kind": "choice",
    "instructions": "Classify whether the final rating follows the supplied evidence and respects its restrictions. This does not authorize trading.",
    "criteria": {
      "A": "The rating is supported by the evidence and counterarguments and respects all material conditions and restrictions.",
      "B": "The rating is REVIEW or unsupported, contradicts the evidence, or disregards a material condition or restriction."
    }
  }
}
```

Exact small synthetic controls for the developer's bounded model check (put this text in the same state shape and provide the unchanged six summary fields; keep recommendation equal to rating):

- Positive: `Rating: Hold. Verified company filing reports revenue 100 and profit 10 for this quarter. The cited filing was retrieved successfully and these values were reconciled. No material source contradiction or essential missing fact remains. Hold is supported by stable revenue and profit. Future growth is uncertain; no forecast is presented as fact. No purchase is recommended. Market is closed; closing price is a research reference and any future order requires a fresh quote.` Expected A/A.
- Missing evidence: `Rating: Buy. The thesis depends entirely on a claimed doubling of current quarterly profit. The only essential earnings report failed to load. No alternative source supports the profit claim, which is unknown. Nevertheless the final rating says Buy because the missing report proves profit doubled.` Expected B/B.
- Contradictory source: `Rating: Hold pending reconciliation. The two retrieved versions of the same filing give profit 10 and profit -10 for the same quarter. Both are claimed authoritative; the discrepancy remains unresolved and prevents assessing profitability. The final rating explicitly defers a directional conclusion until reconciliation and does not claim positive profit is verified.` Expected B/A.
- Inconsistent conclusion: `Rating: Buy immediately without conditions. Verified complete source evidence establishes declining revenue and a loss, with no offsetting positive evidence. The report explicitly forbids buying until profitability recovers. The final recommendation ignores this condition and asserts verified profitable growth as its sole reason for immediate Buy.` Expected A/B.

These are labelled fixtures, not real investment recommendations. Repeat with criteria order B,A while preserving each description; a stable gate must preserve semantics. A single successful positive case is insufficient. The saved META case is a harder separate regression and must not be replaced by these easy cases.

Offline tests prove schema/mapping only; real bounded model evaluation is required to claim discrimination. No such calls were made by this reviewer.

| Control | Expected evidence / consistency | Purpose |
|---|---|---|
| Complete cited packet, coherent conditional rating, explicitly no material source gaps | A / A | Proves this is not block-all |
| Same packet, one essential financial fact replaced by unresolved contradictory figures | B / potentially A | Isolates completeness from coherence |
| Same packet, key report failed with no substitute evidence | B / B if rating asserts that report proves thesis | Tests actual missing evidence |
| Complete packet, final recommendation contradicts supplied facts or ignores explicit condition | A / B | Isolates consistency |
| Valid conditional rating, market closed with usable closing reference and fresh execution check required | A / A if research facts otherwise complete | Avoids confusing research and execution |
| Saved META summary with unreconciled source errors | B expected for completeness | Regression against observed false acceptance |
| Identical controls with option order swapped but descriptions retained | Same semantic answers | Exposes position/label bias |
| Missing, numeric, boolean, unknown label, or low-confidence answer | Application gate false | Confirms fail-closed mapping |

Use preflight on the exact revised questions and save hashes/counts for each bounded real control. Keep full-request reserve and complete sequence checks. If choices still fail polarity or label-order controls, report the semantic gate as unverified and investigate domain calibration/model suitability; do not silently accept all or substitute a blanket rejection as a completed fix.

## ConfessionReport

Changed only this report. Reviewed local source and existing saved inference, plus primary upstream documentation. Did not run inference, providers, browser, tests, or change runtime configuration. Neutral choice is a source-backed mitigation proposal, not a validated solution on this domain. No durable semantic memory notes were used or changed; only the reasoning HSM records this review.

## Follow-up: neutral-choice control failures

Reasoning HSM `session-1792114395436-96538`. Reviewed new `.paper-desk/laya-control-complete_but_inconsistent-forward.json` and `laya-control-contradiction_deferred-forward.json`; no additional inference by this reviewer.

The inconsistent packet returned A/A instead of the fixed A/B expectation, but **did not clear the application gate**: its contract is reconsider, with confidence 0.0687 / 0.3026. Its option probabilities are separately 0.6531 / 0.812 for A. Do not replace SDK confidence with maximum option probability without a separate justified contract change. The deferred packet returned B/B rather than B/A, also reconsider (0.0036 / 0.0067). These are genuine semantic failures, not evidence of an executed unsafe trade. A positive control's correct labels alone are also insufficient: check whether its full confidence contract actually permits the intended legitimate path.

Both inspected runs are cached=false, have preflight and actual sequence hashes equal, and report complete input. Installed `laya/common.py:33-86` renders instructions, options, then state. Each option has a 48-token cap and the head has a separate budget, but adapter `core/context.py:9-34` independently constructs the unlimited representation and compares actual IDs/marker positions. A clipped criterion would set questions_complete=false. The saved complete=true and exact matching sequences do not support blaming these two failures on clipping. Revised wording still requires exact preflight; word count alone is not token proof. The separate cache/order problem is outside this review.

The v1 consistency criterion conflates two tests: whether evidence is complete enough for a directional conclusion, and whether a recommendation faithfully acknowledges its incompleteness. The word REVIEW as a blanket negative also conflicts with a faithful deferral. This explains a plausible ambiguity for the deferred control, **not** the inconsistent packet's wrong A answer: that packet expressly says the final recommendation contradicts facts and ignores a restriction. The latter is a model discrimination failure on current wording. Upstream's documented weak zero-shot domain results/overconfidence remain relevant; prompt changes are candidates, not guarantees.

### Candidate v2 wording, with unchanged fixed expectations

Keep existing A/B semantics, threshold, model and complete-state evidence. Shorten criteria and ask for a concrete contradiction/restriction comparison rather than broad agreement with a rating:

```json
{
  "evidence_complete": {
    "kind": "choice",
    "instructions": "Assess source evidence only, not the final recommendation. Is an essential source missing or a material source fact unreconciled? Ordinary future uncertainty and a closed market alone are not missing evidence.",
    "criteria": {
      "A": "Source evidence is complete and reconciled. Any error is in the recommendation, not the sources.",
      "B": "An essential source is missing or material source facts remain contradictory or unreconciled."
    }
  },
  "decision_consistent": {
    "kind": "choice",
    "instructions": "Compare the final recommendation against source facts and explicit restrictions. A decision that defers until missing facts are resolved can be consistent. A recommendation that invents support or ignores a restriction is inconsistent.",
    "criteria": {
      "A": "The recommendation faithfully follows facts and restrictions, including any required deferral. It asserts no contradicted support.",
      "B": "The recommendation asserts contradicted or unsupported facts, or recommends acting despite a restriction that forbids it."
    }
  }
}
```

Exact expected outcomes remain positive A/A, missing B/B, deferred B/A, inconsistent A/B. REVIEW stays blocked by the existing rating eligibility layer; removing that literal from a semantic consistency criterion must not authorize REVIEW proposals. If product scope instead requires REVIEW to be intrinsically inconsistent, that conflicts with the fixed deferred control and needs explicit reconciliation rather than changing test labels silently.

Before further real inference, freeze this candidate and all four expected labels, verify schema and tokenizer completeness offline, then perform one bounded evaluation per case with fresh request hashes. Also verify swapped option order after the independent cache fix. Do not iteratively rewrite test input to mention the expected option label. Add held-out paraphrases with the same semantic contradictions to distinguish rule understanding from matching one fixture's phrasing. If the original controls still fail, report the gate unverified; do not weaken confidence, hide the failure behind reconsider, or declare a blanket refusal a working evidence gate. Calibration can improve confidence estimation but cannot by itself reverse an incorrect argmax.

Follow-up ConfessionReport: report-only update; exact saved inputs/results and installed rendering/preflight implementation inspected. No model call, runtime change, or test execution. Candidate v2 remains unvalidated, and source-completeness/faithful-deferral distinction is an explicit product interpretation for parent review.

### Evaluation ledger required before choosing v2

Use a separate frozen candidate identifier `research-choice-v2-candidate`, not an unrecorded overwrite of v1 receipts. Record question JSON/hash, immutable fixture hash, checkpoint/tokenizer revision, option order, input hash/count, expected labels, actual labels/probabilities/confidences, raw contract grade, and application gate result. Retain v1 failures as baseline. A model-card-style typed choice defines concrete competing descriptions; instructions establish their scope. Neither is a hidden prompt promising reasoning capabilities.

Acceptance has two separate metrics:

1. Semantic discrimination: both labels match each fixed case, including deferred B/A and inconsistent A/B; swapped order preserves the meaning. Report numerator/denominator, not only an aggregate pass count.
2. Gate usefulness: the complete valid positive must clear the existing confidence/contract requirements; every incomplete or inconsistent negative must remain blocked. Correct A/A labels with reconsider is not a functional positive pass. A wrong A/A negative that remains blocked is a semantic failure but not an unsafe approval.

Saved META remains a separate hard negative for completeness: its unreconciled source facts must produce B, regardless of whether the conditional final rating is judged consistent. Evaluate it using its unchanged saved summary/source; do not replace it with a simplified hand-labelled equivalent. Add at least one held-out phrasing of a complete consistent packet and one of complete sources with a recommendation violating an explicit restriction, selected before observing v2 results. No calibration claims follow from these small acceptance controls; domain accuracy beyond them remains unmeasured.

### Confidence semantics and positive-path failure

The coordinator's aggregate receipts show all four v1 control contracts are reconsider, including the positive A/A case (confidence 0.1847 / 0.6787). Therefore v1 has not demonstrated an operable positive path. The missing-source B/B case is 0.0868 / 0.1716; this is still blocked, but weak confidence cannot validate semantic competence.

Installed SDK `laya/common.py:210` defines choice confidence as normalized entropy reduction, `1 - H(p)/log(k)`, not probability that the chosen label is correct. `laya/agent.py:334-360` applies that score to choice/score answers, while noul confidence is the maximum of its two probabilities. Switching primitive changes confidence semantics even with an unchanged numeric threshold. A binary choice with A probability 0.812 yields approximately 0.303 entropy confidence, matching the observed inconsistent receipt. Do not call 0.303 a 30.3% empirical correctness estimate. Nor should this discovery be used to replace or lower the threshold solely to turn the positive green; the false-A argmax already demonstrates an independent semantic problem.

Require the positive to meet the existing gate contract in v2. If v2 still cannot both admit legitimate evidence and reject contradictions under the frozen controls, the base multilingual model is not validated as the application's zero-shot gate. That requires an explicit product/model-suitability decision or properly held-out domain training/calibration work, rather than more threshold relaxation or a claim that fail-closed alone meets the intended feature.
