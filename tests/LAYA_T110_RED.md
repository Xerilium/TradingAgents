# T-1.10 independent red review

HSM: `session-1792115727525-20224`. Review date: 2026-10-15.

## Verdict

Source/offline implementation accepted after correction; overall live acceptance remains open. The first actual social control exposed a relevance-filter defect that is now fixed and regression-tested against the captured response. A rendering fixture cannot establish live classification correctness or feed integration.

## Verified scope

| Requirement | Evidence | Result |
|---|---|---|
| Actual desk social path reaches Laya | Source trace: DeskService screen factory -> TradingAgentsGraph -> GraphSetup -> sentiment analyst -> StockTwits/Reddit screen hooks; tests cover each interface | Pass offline |
| Actual posts, not research packages | post_screen.py uses one state containing instrument/post and two typed questions; exact token preflight precedes decide | Pass source/offline |
| MCP SDK transport | Injected MaenifoldGateway.aexecute, schema discovery and transport; source no direct TypeSafe call for injected desk hook | Pass source/offline |
| No final research approval | Removed only the Laya predicates in plan_orders and DeskService._review and the post-research inference; no generic Laya tool supplied to analyst graph | Pass source/offline |
| Trading safeguards | Existing paper identity, explicit submit, pause, current completed research/date/account/config/evidence hash, fresh executable quotes, cash reserve, whole shares, caps, open orders, durable intent and unknown-outcome reconciliation remain | Pass source/offline |
| Bounded requests | 30-post shared source budget, 120-second batch budget, async calls bounded to60seconds, process lock, timeout cooldown, no ambiguous replay; explicit429 uses gateway's three bounded retries | Pass offline |
| No new unbounded identity lookup | Reviewer challenged new Yahoo lookup outside budget; worker replaced it with the already-resolved analyst instrument context | Corrected |
| UI meaning | Social counts/provenance separate from historical retired opinion; unavailable/unclear not neutral; escaped content; compact state omits bodies only | Pass source/Node tests; coordinator fixture UAT only |
| Uncertain relevance retained | First live receipt has about p(true)=0.2156 and grade reconsider, stance bullish p=0.9781; initial code dropped it as off-topic. Corrected parser only drops when the individual relevance answer is auto_execute and below the relevance threshold. Exact captured response now remains bullish with explicit uncertain relevance | Corrected and regression passed |
| Live feeds and deployed UI | No independent real-feed/model/deployed UI evidence in this review | Open |

## Executed validation

- First bounded60second Python run:402passed,3subtests in24.62seconds. Included social, service, engine, original screening, structured agents, graph tools/execution/end-to-end and UI projection/fixture tests.
- Subsequent run after initial backend fixes, adding MCP gateway tests:485passed,3subtests in28.26seconds. This predates the live-control relevance correction and is not its verification.
- Node UI regressions:22passed under30second hard timeout.
- Final post-correction run: **487 passed, 3 subtests passed in 28.08 seconds**, under a 60-second hard timeout. Same suites as the 485-test run plus the exact live-receipt and missing-relevance-grade regressions. No source edits occurred during this final run.
- All brokerage interactions in these runs are fakes. Reviewer sent no inference, order, cancellation or account mutation, did not restart anything, and installed nothing.

## Acceptance challenge and remaining work

The synthetic browser fixture proves rendering of supplied counts, not that a real research run fetches and classifies posts. Likewise graph tests plus a standalone live Laya call do not by themselves prove the complete deployed path. The corrected relevance regression and current-source rerun are complete. Require bounded live controls and a read-only feed-to-classification-to-report/UI trace before claiming integrated completion. Never use a broker test transaction to close this gap.

The UI renders the source note including the explicit count of retained posts with uncertain relevance. Per-post `relevance_uncertain` and `relevance_grade` remain visible in the full source artifact; individual preview metadata currently shows the relevance probability, not that flag. This is adequate disclosure at source level, though a per-post plain-language marker would improve scanning.

Reviewed final SHA256s:

- post_screen.py: `3c73ca1387abeb5c1a8a933423953db10f34acdf33c50e26091442f42ecb2a30`
- service.py: `e9ebcae8a5051b3ca8cfed147567d56918dc3267f0c2822e0ebbb500e3f2c915`
- maenifold.py: `abd892b28030d7785a9fef8ca1ad95ad4d20190971ed8ae96ed975ce9314a760`
- app.js: `a6aa8aad4e27e2aa4d6b680bb6ce3d7ca3f052d33575f31a296d3c688c322af5`

The abandoned broad research-choice tests concern a retired product requirement. Their disposition must be recorded as superseded, not silently counted as passing or used to reintroduce approval.

Confession: review only; no production edits. Source and offline correction verification is complete; live integration remains explicitly unproven here. No memory sources used. A PowerShell hash command was unavailable; Python SHA256 produced the hashes above instead.

## Final two-sided relevance follow-up

Follow-up HSM: `session-1792116114014-29870` (completed).

The final question-only correction restores explicit true and false relevance criteria. Independently inspected installed SDK `laya/common.py:33` `render_options`: noul renders false and true criteria explicitly, with generic fallbacks when either is omitted. This is supported encoding, not a switch to a different task or threshold reduction.

- Final social suite: **30 passed in 2.43 seconds**, hard timeout 30 seconds.
- Independently compared `.paper-desk/laya-social-neutral-two-sided.json` request questions with current `LAYA_QUESTIONS`; equal. Count-context and actual inference sequence token counts, sequence hashes and request hash also match.
- Live neutral control: post asks when Meta reports earnings; retained, neutral probability 0.9796, relevance probability 0.5579 with reconsider grade, explicitly recorded as uncertain relevance. Correct observed behavior for this control.
- Final post_screen.py SHA256 supersedes the earlier hash: `28c65516a990802b05aa0d4c651b2ee0bf972a941657fdce36f5f1cb2dbfdbb5`.
- Earlier bullish/bearish controls used the prior question definition. Do not describe them as a complete semantic suite on the final definition. No broad calibration claim follows from these few controls.

Final source correction accepted. Real feed-to-report/deployed UI verification remains open with the coordinator. This reviewer made no additional inference or broker calls.

## Coverage and deferred-screening follow-up

HSM `session-1792116222119-13706` completed. Reviewed final coverage correction: source notes now state classified/fetched/retained counts; analyst instructions explicitly separate classifier output from user tags and forbid treating different denominators as an inconsistency. These are instructions, not proof of subsequent analyst behavior.

Budget-only unprocessed source batches now report `deferred` with a stop reason, while retaining fetched posts. Partial batches remain partial. UI renders the source status and coverage note directly, so deferred is visible without pretending that the feed is unavailable. Aggregate screening may remain partial when a source is deferred; detailed source disclosure preserves the reason.

Validation: **124 scoped Python tests passed in 2.20 seconds**, **22 UI regressions passed**, and independent `tests/social_red_audit.cjs` passed for deferred/coverage/not-a-source-failure/unscreened-not-neutral rendering. The new audit initially lacked the URL global in its wrapper; corrected and rerun successfully. All checks forbid network access or use fakes.

Accepted for runtime verification. Full META research/report/UI verification remains coordinator work; this reviewer did not call providers, place orders, or restart processes.

## Timeout diagnostics and Reddit fallback cap

HSM `session-1792116609450-24149` completed. Independently reviewed the latest correction without production edits.

- `test_laya_social_contract.py` plus `test_reddit_fallback.py`: **68 passed in 1.50 seconds**, under a 30-second hard timeout.
- Additional fake-gateway check raised an empty `TimeoutError()`: the post remained retained, exactly one decision attempt occurred, error_class was TimeoutError, stop_reason was inference_timeout, and the error read: "Laya request timed out; remaining posts are unscreened. The in-flight result is unknown and will not be replayed."
- The async deadline regression separately confirms an expired shared budget records time_budget_exhausted and a nonempty explanation. Timeout cooldown/no ambiguous replay remains unchanged.
- Reddit's headerless fallback now applies min(60.0, jitter). The maximum-jitter test forces the prior 72-second case and asserts exactly 60 seconds. Both success-after-429 and repeated-429 tests still assert two total HTTP attempts: the original request plus the existing one retry. This change does not alter Maenifold's three-retry behavior.

Scoped correction accepted. No live calls, restarts, installs, or broker operations were performed. Runtime verification is not claimed by these offline tests.

## Material live-feed finding: stance uncertainty was discarded

Audit HSM: `session-1792116704704-96509`. Overall semantic acceptance reopened. Saved run `56938b20-afd1-4696-9a0a-a13d48e460d0` contains these unsupported directional classifications:

| Actual post | Reported stance / winning probability | Stance confidence / grade |
|---|---|---|
| `$META .` | Bearish / 0.5339 | 0.175 / reconsider |
| META plus X link ending 2110864335576932754 | Bearish / 0.8475 | 0.5152 / reconsider |
| AMD promotional thesis with trailing META tag | Bullish / 0.9159 | 0.7323 / reconsider |

The saved source text does not support those as META directional views. The first two contain no own price view; the third concerns another stock. Independently read all 21 recorded gateway invocation payloads: every question set matches production LAYA_QUESTIONS, including explicit false relevance criteria and neutral stance. Selected post sequence hashes match actual inference. This is not evidence of lost criteria or truncation.

There are two distinct issues. The model makes incorrect relevance predictions (including high confidence on the AMD post), which is an observed model limitation on this sample. Separately, our integration converts any winning stance probability at least 0.5 into an admitted directional count, ignoring the individual stance's reconsider grade. That is a correctable admission defect: uncertain raw predictions should be preserved but counted/displayed as unclear, not promoted into asserted sentiment. SDK common.py explicitly defines confidence_from_probs as normalized entropy; neither it nor the winning probability is proof that a label is factually correct. The adapter contract nevertheless explicitly marks these answers uncertain, and the caller should preserve that signal.

Added independent `tests/test_social_stance_admission.py`. Red baseline: **5 failed, 1 passed in 2.80 seconds** under a 30-second bound. Reconsider, escalate, ask_human, absent and unknown grades must retain raw predictions/probabilities while admitting unclear; an auto_execute stance with sufficient existing probability remains admitted. Developer notified after the red baseline. No model/threshold tuning or additional live calls were performed.

### Admission correction verified

Worker now requires the individual stance grade auto_execute as well as the unchanged probability threshold before admitting its label; other grades are unclear. Raw prediction, grade, probability, and full original result are preserved. The obsolete probability-only acceptance test was explicitly replaced. Independent final run: **157 passed in 7.13 seconds** across new admission, social, Reddit, and MCP gateway suites, with a 30-second hard bound. One initial command named a nonexistent test file and ran zero tests; the corrected command is the reported pass.

Independently replayed the three exact saved problematic responses through the current classifier with a fake gateway. All three are retained as unclear; raw bearish/bearish/bullish and probabilities 0.8475/0.5339/0.9159 remain unchanged. This is offline replay, not fresh inference; the historical journal was not edited. The timer diagnostic correction also records the expired asyncio limit directly so an early event-loop timer tick cannot mislabel shared-budget expiry.

Admission correction accepted; HSM completed. Observed relevance-model mistakes remain a disclosed limitation. This fix does not establish general semantic accuracy, and old analyst reports containing the former counts remain historical. Coordinator must verify final deployed/UI behavior and the complete goal before closing Gate.

### Actual-response browser replay fixture

`tests/social_stance_replay_browser_fixture.py` now builds a META-only fixture from the three exact saved problematic responses in run 56938b20-afd1-4696-9a0a-a13d48e460d0. It checks source text hashes, replays count/decision responses through the corrected production hook, asserts all three are retained unclear, preserves each full response/raw label/probability, and verifies journal bytes remain unchanged. Text is embedded with JSON/HTML-safe escaping; the production renderer escapes the display.

Launch by coordinator: `python -m tests.social_stance_replay_browser_fixture --port 18767`, then open `http://127.0.0.1:18767/#research`. Exclusive bind prevents fixture collisions. The source note and activity event explicitly identify offline replay verification, not new inference. No proposals are seeded. Unrelated synthetic control buttons are removed.

Reviewer ran `--check` successfully and checked the generated BOOT JavaScript syntax with Node under bounded subprocess timeouts. No server was started. Result: 0 bullish, 0 bearish, 0 neutral, 3 unclear, 0 off-topic, 0 unscreened. HSM `session-1792116856625-32714` completed. Visible browser UAT remains with coordinator.
