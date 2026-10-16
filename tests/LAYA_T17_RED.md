# T-1.7 independent red review

Status: **T-1.7 ACCEPTED: adapter decision mapping and cache identity**, after independent offline and saved live-receipt verification below. This is not T-1.8 application or general model-semantic acceptance. No model inference, restart, Gate transition, order, or product edit was performed by this reviewer.

## Reproduced evidence

- Original 44 contract regressions pass in 0.04 seconds under the project's hard 30-second runner.
- Adapter environment plus the existing TradingAgents pytest package, plugin autoload disabled, warmup false and Hugging Face offline: **48 passed, 1 deselected** in 2.86 seconds. Four REST smoke tests passed. The excluded routing smoke calls `InferenceEngine.route()`, which invokes `self.load()`; it is not a pure no-model check. The previously reported 50-second timeout is not a mapping regression, and this is not a full-suite claim.
- Read the actual saved `.paper-desk/laya-single-forward-validation.json`, extracted each `result.answers[id].raw`, and remapped through the current `build_contract` with the saved questions. Result: `auto_execute`, margins 0.987 and 0.9832. Original receipt still contains its historical `escalate` result and was not modified. Replay proves the mapping changed, not that incomplete trading evidence should pass the application's separate gate.
- SDK source `laya/agent.py` emits choice distributions keyed by choice identifier, score distributions keyed by canonical zero-based string indices, and noul probabilities in the `noul` field without a distribution. Valid score compatibility is covered by the regression suite.

## Initial rework findings (now corrected)

All of these return `auto_execute` when passed as the `q` answer to `build_contract`, with threshold 0.9 and margin threshold 0.05:

1. `{"type":"score","noul":0.99,"confidence":0.99}` ignores a contradictory declared type.
2. `{"type":"score","score":0.01,"confidence":0.99,"probabilities":{"wrong":0.99,"other":0.01}}` accepts invalid SDK score level identifiers. Supplying a two-level score question does not prevent this; only distribution length is checked.
3. `{"noul":0.51,"confidence":0.99,"probabilities":{"a":1.0,"b":0.0}}` overrides the binary margin with an unrelated distribution. Without the extra distribution the margin is 0.02 and escalation is correct; with it the margin is 1.0 and the malformed answer becomes autonomous.

Require diagnostic non-autonomous results or explicit rejection for these malformed shapes. Preserve existing well-formed noul, choice and score payloads and legacy test fixtures with omitted `type`.

## Independent correction recheck

SWE added seven regression variants and fixed the three findings. I inspected the new validation: exactly one payload kind; declared type must agree when present; noul rejects distributions/legend; score keys must be consecutive zero-based string IDs. Binary margin also prioritizes its own noul field.

Re-ran **51 contract tests passing in 0.05 seconds**, then **55 tests passing, 1 routing smoke deselected, in 2.49 seconds** in the adapter environment using the same hard 30-second runner. Re-executed my original three payloads independently of the test file: all now return `reconsider`. Saved raw replay still returns `auto_execute` with the existing questions. No remaining blocking defect identified in this contract-mapping scope. Confidence in a selected negative evidence answer is still not affirmative trading permission; verify the separate application gate.

## Controlled live-run harness

Initial review found `MaenifoldGateway` classifies `laya.decide` as retryable analysis, so exclusive receipt creation alone did not prevent internal 429 retries. Parent added `on_dispatch=dispatch_once`; this reviewer extracted that exact callback from the runner AST and invoked it twice with an in-memory receipt/output. First call persisted `inference_dispatches: 1` once; second raised before any second write. The Gateway transport invokes its hook before dispatch. This is sufficient to prevent a repeated inference dispatch; it does not prove model semantics or cancel a forward already executing. Use the documented outer 85-second hard runner and inspect unknown outcomes without replay.

## Scope and confession

Reviewed adapter contract source, SDK result shapes, original blue/SWE handoffs, saved raw result, Gateway retry source and live-control script. No private research text copied into this report. No inferred model outcome is represented as an actual call. Acceptance is limited to proceeding with controlled actual-model/application verification by the parent. The callback test is isolated, not a fake network transport integration test; the source inspection establishes hook placement before dispatch.

Thinking HSM: `session-1792114141025-53088` (completed with scoped acceptance and confession).

## Runtime follow-up: order-sensitive cache collision

Runtime acceptance is **withheld** after the controlled reversed-choice request exposed a separate cache defect. Read-only examination of `.paper-desk/laya-control-complete_conditional-forward.json` and `laya-control-complete_conditional-reverse.json` establishes:

- The forward questions have criteria insertion order `A,B`; reverse has `B,A`.
- Evaluating the actual `_state_fingerprint` function extracted from `core/engine.py` yields identical keys for both parameter sets. It recursively serializes with `sort_keys=True`, erasing an order that SDK option rendering preserves.
- Reverse returned `cached: true`. Its returned `usage.context_budget.sequence_sha256` exactly equals the prior forward result and differs from its own reverse preflight hashes. This was an old cached answer, not evidence of a reverse-order model inference.
- `core/context.py` also uses sorted dictionary serialization for `request_sha256`, so that request hash collides as well. The separate sequence hashes correctly exposed the mismatch.

Required correction: preserve sequence-affecting insertion order in cache identity and request identity, or key against the exact encoded inputs. Preserve `model`, `task`, and `lang` as separate routing inputs; the current `model or task or lang` expression also conflates distinct routing requests.

Required offline regression: fake `_run_blocking` with a call counter and order-dependent sequence metadata. `predict(use_cache=True)` must hit for the identical request, miss for reversed choice criteria and return new matching hashes, then hit for that exact reversed request. Include distinct routing arguments. Do not weaken the live harness hash assertion or simply disable caching to hide the production defect.

No additional inference, receipt rewrite, or runtime mutation was performed for this diagnosis.

### Cache correction independently accepted for controlled refresh

Reviewed the fix: `_state_fingerprint` preserves insertion order and includes `model`, `task`, and `lang` separately. `inspect_context.request_sha256` also preserves insertion order. The new fake-forward tests exercise the real SDK sequence builder with a character tokenizer, asserting identical-request hits, reversed-options misses with new matching sequence hashes, repeated-reverse hits, state/option ordering, and seven distinct routing argument combinations.

Independent rerun under the hard 30-second runner: **58 passed, 1 routing smoke deselected, in 2.76 seconds**. Independently evaluated the corrected fingerprint against the two actual saved control parameter sets: forward and reversed now produce distinct keys. No live inference executed by reviewer.

**Accepted for one controlled adapter refresh and a new reversed-order live proof**, retaining the original failed receipt. This acceptance does not substitute fake-tokenizer test hashes for actual multilingual inference hashes. Final runtime acceptance still requires the new preflight/result comparison and semantic checks.

### Final controlled runtime evidence verified

Independently read `.paper-desk/laya-control-cachefix-complete_conditional-forward.json` and `laya-control-cachefix-complete_conditional-reverse.json`. Both are `verified_transport`, `cached: false`, with exactly one recorded inference dispatch. Each actual usage sequence hash and token count equals its own preflight. Forward/reverse exact sequence hashes differ; both requests have 267 and 263 tokens. Thus the reversed request was newly evaluated and did not reuse the forward cached answer.

Recomputed the decision contracts from each saved raw answer and its recorded thresholds using current `build_contract`. Both exactly reproduce grade `reconsider` because calibrated confidences are below 0.90. Forward confidences are 0.1847 and 0.6787; reverse confidences 0.1269 and 0.5282. All four selected outcomes are A, matching this control's expected outcomes. These results correctly remain non-autonomous; a passing transport or correct selected label alone does not authorize trading.

T-1.7 mapping/cache requirements now pass. T-1.8 broader evidence discrimination and application handling remain separately open. No further inference was performed for this audit. Final completed thinking HSM: `session-1792114666103-26555`.
