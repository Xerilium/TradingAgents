# Read-only Laya inference audit

2026-10-15. Scope: installed adapter and SDK, cached multilingual checkpoint configuration, and saved control receipts. No model inference, provider calls, restarts, package changes, or production source edits performed. One offline tokenizer pass recomputed all currently present `laya-control*.json` inputs under a 60-second process deadline; completed in approximately 8 seconds.

## Result

No checkpoint/tokenizer mismatch, label-index swap, omitted JSON values, active dropout, or probability-transport defect was found that explains the four short controls. The original reversed-options cached receipt is invalid for semantic comparison; fresh cachefix receipts have the correct distinct input hashes. The fresh order-dependent classifications remain actual recorded model outputs, not evidence of a discovered label transport bug. This is not a general finding that Laya is unsuitable.

## Trace and evidence

Paths below are relative to `C:/Users/brett/maenifold/laya-mcp/` unless stated otherwise.

| Question | Verified implementation / evidence |
|---|---|
| Explicit multilingual routing | `.venv/Lib/site-packages/laya/router.py` DEFAULT_MODELS maps multilingual to `convaiinnovations/laya`, subfolder `multilingual`; `route` gives explicit model highest priority and `load` passes that repo/subfolder to Agent. `src/laya_mcp/core/engine.py:353-368` loads precisely that routed agent, changes only max_len for the call, then invokes its system_one. Receipts identify `convaiinnovations/laya/multilingual`, explicit routing, cached false. |
| Model/tokenizer pair | SDK `agent.py:159-194` reads model.safetensors, tokenizer and encoder from the same model directory, verifies architecture and loads weights strict=True. Cached revision `7b928d828b7b0e022f929d9bd2e44165aa270148` has encoder `jhu-clsp/mmBERT-base`, max_len1024/head_max_len256, temperatures1 and no bucket overrides. Tokenizer SHA256 `609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f` matches receipts. Live weight hash is not recorded, so immutable checkpoint identity is not fully attested by the receipts alone. |
| Eval / sampling | SDK `agent.py:231,239` calls eval(), and `system_one` has no_grad at265. It computes softmax then argmax; it does not sample. No code switches the model back to train. This establishes inference mode from source, not bitwise cross-device determinism: deterministic torch algorithms are not explicitly enabled and no repeated model calls were made for this audit. |
| Schema lowering | `core/schema.py:210-225` maps kind to type and preserves instructions, criteria labels, descriptions and insertion order. MCP `server.py:201-217` uses this lowering for decide; `server.py:300-306` uses the same normalization/lowering for preflight. |
| Label order | SDK `Agent._to_internal` (`agent.py:255-263`) retains choice dictionary order. `common.py:33-40` renders its items in that order. `build_sequence` (`common.py:49-86`) creates marker positions in that same order. `collate_items` (`common.py:247+`) copies positions without permutation. `agent.py:326-344` slices logits to k, builds keys from the same criteria dictionary, selects keys[argmax] and zips keys/probabilities. Reversal changes input positions, while labels remain attached to their descriptions and corresponding output positions. No index swap found. |
| Structured state | `common.py:15-18` JSON-serializes dict/list state with ensure_ascii=False; string state passes through. Offline JSON roundtrip preserved every control state value. This is a documented supported shape, not a Python repr or lost nested object. |
| Full input | Offline preflight with actual head_max_len256 reconstructed all saved control sequence hashes. Every saved forward/context hash matched except `laya-control-complete_conditional-reverse.json`, the original known cached collision. All fresh cachefix receipts matched, all reported complete inputs. The problematic complete-but-inconsistent forward is only268/264 tokens per question, so it is not near the8192 limit. |
| Probabilities / confidence | SDK `agent.py:329-343` applies temperature (1 here), normalizes softmax to1 and emits confidence from `common.py:210-217`: `1-H(p)/log(k)`. MCP `server.py:163-198` preserves these values and derives margin top1-top2. `core/contract.py:103-125,248` reads confidence and compares it to threshold; it does not replace it with max probability. Offline recomputations from rounded probabilities agree within about0.0002. Complete-but-inconsistent p(A)=0.812, p(B)=0.188 yields entropy confidence about0.3027 versus reported0.3026 and margin0.624 exactly. |

## Concrete remaining integration issues / limits

1. **Confidence terminology is inaccurate.** `core/contract.py` introductory text describes confidence as calibration and its margin docstring calls it top1, while `server.py:79` calls it calibrated confidence in the selected answer. Installed SDK choice confidence is normalized entropy, not selected-answer probability or an empirical correctness guarantee. A threshold of0.90 on binary entropy requires roughly98.7% top probability, unlike90% on the SDK's noul max-probability confidence. This explains different gate stringency after question-type changes, but does not explain incorrect argmax classifications. Do not silently replace the metric or lower the threshold to force positive controls through.

2. **Preflight head budget mismatch is conservative but real.** `core/context.py:11` defaults head_max_len192 and `engine.py:330` calls it without reading the cached checkpoint's256 head budget. Actual inference passes the checkpoint value at `engine.py:364-365`. Long questions may therefore be rejected by preflight despite fitting the actual head budget. All audited controls fit both budgets, and their complete hashes match actual inference; this is not their semantic failure cause.

3. **Runtime revision is old relative to current docs.** Installed distribution is laya0.3.5; official current model card describes0.3.20 with direct max_len support absent from this installed Router. The adapter's scoped cfg override accomplishes the documented input allowance here. A version difference alone is not evidence that upgrading fixes these semantic failures; no upgrade performed.

4. **Receipts prove audited sequence construction and returned values, not independent instrumentation of tensor arguments at the encoder.** Code directly calls SDK system_one with the same state/questions/config, and offline reconstructed hashes match. No hostile mutation or intervening transformation was found. If stronger provenance is required, capture input_ids/attention_mask at the model boundary in a controlled test; this audit did not run another forward.

## Primary reference

Accessed2026-10-15: https://huggingface.co/convaiinnovations/laya/raw/main/README.md. It supports dict/JSON state, explicit multilingual routing and8192 with an increased limit. The SDK source above is the authority for this installed version; current docs have newer APIs. No model replacement recommendation is made.
