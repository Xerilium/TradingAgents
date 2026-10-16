# T-1.1 final independent acceptance audit

Status: **PASS: final repaired UI evidence verified**. Reviewed 2026-10-15; PM owns Gate transitions. This report does not itself advance Gate.

## Independently reconciled evidence

- Gate objective and all seven acceptance criteria read against the original red audit, provider cancellation correction, semantic summary review, live receipts, and source.
- Original cancellation P1 is corrected by the independently executed real-provider-path offline probe and 62 passing scoped tests in `LAYA_PROVIDER_RED_REVIEW.md`. Earlier 316 integration and 12 actual-tokenizer checks remain applicable. No reason to repeat the entire suite solely for consolidation.
- Saved packet source fingerprint recomputed from the original source: `c7cb0b025a1ea018d7ab6a7d7cfd36aba7a6d79fb93124056e9659c0743fbec7`. All nine original report SHA256 values match the manifest. Saved summary equals the persisted audit summary; saved audit parameters exactly equal the one-forward receipt parameters. Parameters digest independently matches `d54e080e4668c6fd11b175d76c43a650cdf9d68304c5f714341ca6f51e4d9e22`.
- Saved META semantic fidelity was separately reviewed in `LAYA_SUMMARY_RED_REVIEW.md`. Its claims align with the source-bound exact rating, unresolved gaps, conditional execution and quote context in the receipt. That review acknowledges compression losses and distinguishes recommendation from permission. This consolidation does not independently verify underlying financial claims or generalize one successful summary to all future inputs.
- Independently reran only local exact token encoding because reconciling a public-request hash directly initially differed from the adapter receipt. The source explains why: the adapter hashes questions after public-schema lowering. Using `resolve_questions`, `to_laya_questions`, the actual cached multilingual tokenizer and `inspect_context` reproduces **every budget field and tokenizer identity exactly**. No inference, model download or provider transmission occurred. The read-only probe completed in 5.17 seconds under a 15-second hard timeout.
- Exact sequences are **2673 and 2677 tokens**, both below **8192 minus the 256-token reserve**. Per-sequence hashes, complete-state/question flags, effective limit and lowered-request hash match preflight and returned runtime budget. Lowered-request digest is `8ee539fb7dd919575f743171e7893496f8698a408462645325458250d16fc113`. Tokenizer digest is `609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f`, checkpoint revision `7b928d828b7b0e022f929d9bd2e44165aa270148`.
- `.paper-desk/laya-single-forward-validation.json` contains a returned result, not just a dispatch receipt: explicit multilingual routing, `cached=false`, runtime context budget matching preflight, summed input usage **5350**, latency **42348.791 ms**. The script guards an existing receipt against repetition, checks idle research, and records failed/unknown outcomes separately. No new forward was requested by this reviewer.
- `.paper-desk/laya-refresh-receipt.json` records semantically unchanged configuration and rediscovered `count_context` schema. `.paper-desk/laya-desk-restart-receipt.json` records idle research, changed owned listener, one successful health check, and semantically unchanged journal. This is deployment evidence, not evidence of a new full research run.

## Model result and limits

The actual result still escalates despite confidence around 99 percent, with the adapter's human-option reason. This does not negate the context fix and must not be presented as autonomous authorization or evidence that the unresolved source gaps disappeared. The gate remains conservative; paper-only/manual order guards remain outside the summary's authority. Existing reports were not rewritten.

Native Laya computation remains noninterruptible after admission. Single-flight admission prevents overlapping forwards while a timed-out call finishes. Provider cancellation is cooperative with separately bounded cleanup overhead. Default three retries with waits capped at 60 seconds remain; the summary itself disables retries. No promise of hard native-model cancellation is made.

## Repaired UI acceptance

The original browser audit found `[object Object]` in the top summary and token-budget preview. The initial repair recheck was blocked, so acceptance was withheld. After browser access was restored, PM performed the repaired visual check using the isolated local fixture on port 18765 with actual application assets and the saved audit. No new inference or journal mutation was needed.

A fresh final reviewer independently inspected `.impeccable/review/laya-preview-repaired.png`: the selected-stock panel visibly renders readable summary text, the Overweight recommendation and full-input counts 2673 / 2677. The PM's browser inspection additionally confirmed multilingual routing, 8192 capacity, 256 reserve, all six summary fields and the raw audit through `summary_attempts: 1`. Those inspection observations are attributed to PM, not claimed as a second browser run by this reviewer.

The reviewer independently parsed `.paper-desk/laya-preview-browser-receipt.json` and verified its complete browser-rendered raw JSON equals the saved `audit` object exactly. The receipt records zero initially open details, two after explicit Laya/raw expansion, no `[object Object]`, unchanged selected-stock height of 369.5px and unchanged run-activity top of 781.1875px. This comparison passed under a 10-second hard deadline. The current UI regression suite independently passed all 19 tests in 115ms under a 30-second hard deadline, including the real structured audit shape and nonduplicated preview.

Criterion 5's remaining presentation defect is resolved. Together with the independently reconciled evidence above, all seven criteria are accepted. This is fixture-based UI evidence for the saved live-validated input, not a claim of a new full research run or automatic execution authorization.

## ConfessionReport

Original audit HSM: `session-1792110058508-91456`. Fresh follow-up reviewer: `/root/final_gate_review`. This reviewer owns only this report. No product edit, Gate transition, new model/provider call, browser interaction, restart, order, or research batch. Direct follow-up checks were source review, 19 scoped offline tests, saved screenshot inspection and exact browser-receipt comparison. Earlier tokenizer, provider and semantic checks remain explicitly attributed to their independent reviews. The prior NOT ACCEPTED result was correct while visual evidence was missing; the new evidence closes that gap. Parent owns the red-team Gate transition.
