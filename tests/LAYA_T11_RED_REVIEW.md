# T-1.1 independent red-team audit

Outcome: **FAIL**, 2026-10-16 UTC. PM owns Gate transitions. No product edits, provider requests, model forwards, restarts, orders or Gate mutations performed by this reviewer.

## P1: summary cancellation does not stop the actual ChatGPT provider retry loop

`tradingagents/web/laya_review.py:summarize` configures native timeout fields and attempts to set `max_retries=0` only when the provider exposes that field. `ChatGPTChatModel` has no such field. Its synchronous `_generate` in `tradingagents/llm_clients/chatgpt_client.py:260` hardcodes four attempts and blocking backoff. LangChain's inherited async wrapper executes this synchronous method in an executor.

Cancelling the async invocation therefore leaves that provider thread running. `asyncio.run` waits for executor shutdown, so the advertised 65-second outer timeout cannot bound the complete operation. Worse, a rate-limit retry can start after operator cancellation. Each attempt also receives its own native timeout rather than the remaining overall budget.

Independent offline reproduction used the actual ChatGPTChatModel and actual summarize function, mocking only `_generate_once` and backoff sleep. First attempt raised `GatewayRateLimited(1)`; backoff was shortened to 0.8 seconds; cancellation became true after 0.05 seconds. Output:

```text
InterruptedError 0.813 provider_attempt_seconds [0.0, 0.813]
```

The second provider attempt started after cancellation. No network or model request occurred. A separate single slow mocked call returned InterruptedError only after 0.812 seconds despite cancellation at 0.05 seconds, confirming executor shutdown waiting.

Required repair: enforce cancellation and one overall deadline across the actual provider path, including backoff and admission of each retry. Respect the user's default three-retry policy with waits capped at 60 seconds outside the bounded summary operation. Add a regression using the real ChatGPTChatModel wrapper with mocked transport; a fully async fake does not cover this defect. Do not claim native model forward cancellation, which is separately disclosed as noninterruptible.

## Independent executed evidence

- 316 passed in 25.59 seconds: test_paper_service.py, test_mcp_gateway.py, test_laya_review_budget.py, test_laya_installed_sequence_contract.py. All offline. Initial sandbox run failed due Windows temp directory ACL; one approved fresh-temp rerun passed.
- 12 passed in 7.54 seconds: test_laya_context_runtime.py in installed adapter environment, real cached multilingual tokenizer and actual sequence builder, fake forward. No model weights inference.
- Commands used rtk and a hard 60-second outer process timeout; cancellation probes used a 10-second process timeout.

## Accepted code evidence, with limits

The actual sequence comparison detects head/options clipping and state overflow. Per-sequence 8192 limits, actual tokenizer 8191/8192/8193 counts, multilingual text, question/metadata overhead and caller 256-token reserve pass. Explicit multilingual routing and temporary effective max_len=8192 restore are present. Engine repeats preflight with the loaded agent tokenizer and refuses before forward when oversized or altered. Single-flight admission rejects overlapping native forwards; it does not terminate an existing forward.

Summary schema, exact rating, report names, source hashes/references, quote context and persistent pre-decide audit are present. Save failure and post-decide cancellation checks pass. These structural checks do not prove generated prose preserves contradictions or execution conditions: report names and hashes can survive while meaning is omitted. Original reports remain available for independent comparison.

## Remaining acceptance gates

1. Repair and independently verify the provider cancellation/deadline defect above.
2. Saved META packet versus generated summary semantic comparison remains unverified, awaiting user payload/destination approval. This reviewer made no transmission attempt.
3. Managed Gateway deployment, fresh count_context discovery and one bounded actual model forward remain unverified. Local MCP registration tests are not deployment proof.
4. Exact Laya audit UI display is under separate UI review; this reviewer did not claim browser UAT.

## ConfessionReport

Child reasoning session: `session-1792108135405-31779`. Scope was independent source/test audit only. Gate red prompt and orchestration contract read. No reusable memory source used or semantic memory note created. Test passes alone are insufficient for Gate completion. The reproducible cancellation defect and unfulfilled live/fidelity criteria require FAIL, not a qualified terminal pass.
