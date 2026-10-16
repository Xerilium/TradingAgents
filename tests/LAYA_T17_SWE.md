# T-1.7 adapter implementation handoff

Changed the adapter in `C:/Users/brett/maenifold/laya-mcp`:

- `src/laya_mcp/core/contract.py` ignores the unreliable action head completely, including malformed values. No inversion or replacement threshold is used.
- Selected explicit review identifiers still escalate. Unselected review options, `no_review`, `reviewed`, `approved`, and `preview` do not. Explicit `needs_human_review=true` escalates; false does not.
- Binary margin is `abs(2*p-1)`, matching top1 minus top2.
- Missing/partial answers, wrong answer kinds, invalid/nonfinite/out-of-range probabilities, missing selections, incomplete choice distributions, and non-normalized distributions fail closed with diagnostic reasons. Thresholds themselves require finite [0,1] values.
- `README.md` now describes these semantics and separates confidence in an answer from an application's authorization of the selected outcome.
- Added 14 edge-case regressions beyond the blue team's 30 cases. Original blue assertions remain intact.

## Verification

Blue suite plus added regressions: **44 passed** with TradingAgents Python, hard 30-second deadline.

Adapter environment lacks pytest; TradingAgents environment lacks FastAPI. Without installing anything, used adapter Python with the TradingAgents pure-Python pytest package appended to `sys.path`, plugin autoload disabled, warmup false. Full suite reached 33 passing tests then hit the **50-second hard timeout** in the existing routing smoke. Inspection shows `InferenceEngine.route()` calls `self.load()`, so the existing smoke's claim that it needs no model loading is inaccurate. No inference was intentionally requested. The timeout stopped that test process tree.

With Hugging Face offline enabled and that routing smoke excluded: **48 passed, 1 deselected** in 2.48 seconds (44 contracts plus four REST smoke checks), hard 30-second deadline. One existing Starlette deprecation warning. This is not a full-suite pass.

The existing `tests/test_smoke.py` contains no action-head contract assertions; it was not weakened or changed. The malformed action head and unselected human option expectations were corrected in production instead of modifying the blue tests. SDK score/choice/noul payload shapes were checked directly in the installed `laya/agent.py`.

## Limits / confession

No Gate transitions, commits, restart, live model inference, broker calls, or TradingAgents production edits. This verifies generic contract mapping, not trading evidence discrimination, which is a separate task. Review identifier recognition uses documented exact identifiers after whitespace/hyphen normalization; it does not infer arbitrary prose semantics. Independent red review and deployment verification remain required.

Thinking session: `session-1792113932666-94007`.

## Red-review correction

Independent red review found three bypasses: declared `score` with a `noul` payload; score distributions with arbitrary rather than canonical level IDs; and injected choice probabilities overriding a binary margin. Added seven regressions before the fix: **7 failed, 44 passed**. The corrected implementation requires exactly one payload kind, validates explicit type against that kind, rejects distributions/legends on binary answers, requires consecutive zero-based string score IDs, and independently calculates binary margin before considering categorical probabilities. Legacy valid payloads without a declared type remain supported.

After correction: **51 contract tests passed**. The same offline adapter/REST selection passed **55 tests, one routing smoke deselected**, preserving the earlier full-suite limitation. No deployment or inference. Continuation thinking session: `session-1792114214574-10966`. Changes returned for independent re-review; this handoff is not Gate acceptance.

## Runtime cache identity correction

The controlled reversed-criteria request exposed a cache collision. Added `tests/test_cache_identity.py` using a fake forward, deterministic character tokenizer, and the actual installed SDK sequence builder. Before production changes all three tests failed for the expected reasons: reversed criteria incorrectly hit the first cache entry, request hashes collapsed three distinct option/state orders into one, and distinct routing fields aliased.

`engine._state_fingerprint` now preserves nested insertion order and records `model`, `task`, and `lang` separately. `context.inspect_context` likewise preserves order in its request hash. Caching remains enabled. Regression verifies original request miss then identical hit, reversed criteria miss with matching fresh sequence metadata then identical reversed hit, plus routing and structured state order identities.

Combined offline adapter verification: **58 passed, one existing routing smoke deselected** in 2.52 seconds with the same hard 30-second deadline and offline configuration. No live inference, restart, commits, or historical receipt changes. Sequence-hash assertions are unchanged. New thinking session: `session-1792114440060-99078`. Independent reviewer notified for re-review; runtime acceptance remains the PM's responsibility.
