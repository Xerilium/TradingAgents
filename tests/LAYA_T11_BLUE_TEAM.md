# T-1.1 blue-team evidence and implementation handoff

Recorded 2026-10-15. This is test/spec-stage evidence, not implementation or final verification.

The caller drafts in `tradingagents/web/laya_review.py` and `service.py` already existed before this stage. The failures below were executed against those incomplete drafts and the installed adapter. They are not evidence that product development started test-first. This worker changed only the two new test modules and this handoff.

## Executed command and result

```powershell
rtk proxy .venv/Scripts/python.exe -X utf8 .paper-desk/run-bounded.py --seconds 60 -- .venv/Scripts/python.exe -X utf8 -m pytest tests/test_laya_review_budget.py tests/test_laya_installed_sequence_contract.py -q -p no:cacheprovider --basetemp .paper-desk/laya-blue-tests-elevated
```

Exit 1: **7 failed, 29 passed in 3.79s**. The initial sandbox run hit Windows temp-directory ACL errors, so the successful execution used approved escalation and a fresh temporary directory. No tests contacted a backend. No inference, research, order, installation, restart or deployment was performed.

Red assertions:

- `test_preflight_must_prove_state_complete_and_effective_capacity`, four cases: incomplete/unknown state completeness and effective capacity 1024/unknown were accepted (`DID NOT RAISE ValueError`).
- `test_cancellation_during_preflight_does_not_return_inference_request`: cancellation set during the count call was not observed (`DID NOT RAISE InterruptedError`). The enclosing service currently checks cancellation separately before decide; this test strengthens the preparer's own contract.
- `test_summary_cannot_change_exact_rating`: source Hold could become Strong Buy in the summary (`DID NOT RAISE ValueError`).
- `test_adapter_exposes_preflight_for_the_draft_callers_gateway_command`: installed MCP server has no `count_context` function. This is a source-contract assertion, not runtime Gateway discovery.

Passing tests establish caller fail-closed shape validation, explicit multilingual/high routing, per-question threshold with reserve, exactly two maximum summary attempts, compaction from original source, no retry after timeout, cancellation before summary, summary schema rejection, native timeout configuration, audit payload identity and source fingerprint. These use synthetic Gateway counts and fake LLM responses; they do not prove model correctness.

Six installed-builder characterization cases execute the actual pure functions from installed `laya/common.py` via AST extraction, without importing models. They demonstrate complete encoded overhead at 8191/8192/8193 and silent clipping of long question/options even below 8192. Their explicitly fake tokenizer maps Unicode characters to IDs; **it does not prove multilingual token counts**.

## Proposed minimal interface contract

Retain the draft `laya.count_context(state, questions, model="multilingual")` API only if implemented and discoverable through Gateway. Existing question lowering must be identical to decide. Proposed response fields:

- `model`: actual selected checkpoint, multilingual.
- `max_tokens`: supported full sequence ceiling, exactly 8192.
- `effective_max_tokens`: verified inference configuration, exactly 8192; supported capacity alone is insufficient.
- `sequence_tokens`: untruncated complete counts keyed by every question ID, including state serialization, instructions, options, markers and special tokens.
- `questions_complete`: proof that head and every option are represented without clipping; false is a hard failure.
- `state_complete`: proof the counting process covers the full serialized state, not a clipped token list. This does **not** mean an oversized state fits: raw counts may exceed 8192, allowing bounded resummarization.

Names are provisional interface recommendations. If implementation uses equivalent fields, revise tests with PM approval and preserve these invariants. Preflight should bind evidence to exact request content and tokenizer/checkpoint identity; decide must revalidate or use the identical prepared encoding to prevent configuration drift. A trusted boolean alone is not implementation proof. Do not pass unsupported `max_len` to installed Router.predict; inspect/configure the actual Agent path and test the effective encoded sequence.

Caller reserve boundary is `8192 - 256 = 7936`, not 8192. Each complete sequence independently fits; aggregate usage for two questions can exceed 8192. Preserve confidence threshold high and existing manual submission/broker guards.

## Remaining required validation

1. Actual multilingual tokenizer and actual lowered questions/sequence builder together, offline and local-files-only; no downloads by this stage. Test ASCII, CJK/multibyte, metadata growth, long instructions/options, 8191/8192/8193 raw sequences, and exact preservation under inference configuration. Default HF cache inspected here contained only English Laya snapshots.
2. Runtime MCP tool registration and Gateway discovery/schema/invocation, plus engine refusal before model forward for incomplete/oversized/unverifiable input. Source function existence is only an initial red signal.
3. Service-level save/read-back: exact summary and fingerprint persist before decide, original reports remain intact, model/routing/count evidence stays with result, save failure prevents decide, cancellation/timeout prevents subsequent calls, and UI exposes evidence. Current tests check returned audit payload, not disk durability or UI.
4. Compare summary with the saved ~97k-character packet for supporting facts, strongest counterarguments, unresolved contradictions, source references/errors, exact rating, quote/date/feed and execution conditions. Schema validity cannot establish semantic fidelity. No saved-packet comparison completed here.
5. Run existing paper-service/Gateway regression suites with appropriately updated offline fakes. Existing BrokerFake has no count_context and ScriptedGraph has no summarizer; failures must not be hidden with production fallback.
6. Independently verify effective model configuration and bounded live behavior only after offline checks and PM authorization, preserving active research.

## Process confession

Requested maenifold, maenifold-thinking and maenifold-orchestrate skills were read. Worker tool inventory exposed no Maenifold/Gateway tools. PM explicitly authorized continuing local test-only scope and will record the exception centrally. No child SequentialThinking session or persisted ConfessionReport was fabricated; no CLI fallback was used. Memory URIs used: none. No Gate task transitions were performed by this worker.
