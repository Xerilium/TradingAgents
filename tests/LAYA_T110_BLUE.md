# T-1.10 blue-team regression baseline

Scope: per-post social sentiment through Maenifold; remove final research approval; preserve deterministic trading safeguards. No production edits. Reference: Printer `apps/tradingagents/tradingagents/agents/post_screen.py` uses one local request at a time, relevance probability, winning stance probability, and unscreened retention. The current repository has a Jev screening hook but no Maenifold social hook.

## Proposed test seam

`tradingagents.agents.post_screen.laya_screen(ticker, gateway, *, max_posts=30)` returns the existing social-fetcher callback `(posts) -> (keep_flags, note)`. Gateway is the existing injectable MCP SDK-backed Gateway interface, never direct TypeSafe HTTP. One raw post plus instrument per `laya.decide`, typed `about` and `stance`, multilingual routing. Low entropy-derived confidence and `reconsider` are not a trade decision. Count stance using valid winning-label probability; retain uncertainty. Explicit maximum posts bounds work and retains excess posts as unscreened. Timeout with unknown inference outcome stops the batch without replaying it.

The fixture represents normalized Laya answers with `kind`, `value`, `probabilities`, and original `raw`; production must validate against the actual adapter contract. The seam is negotiable but behavior is not. Adapt fixture schema only when grounded in the real contract.

## Exact scoped command and baseline

`rtk proxy .venv/Scripts/python.exe .paper-desk/run-bounded.py --seconds 60 -- .venv/Scripts/python.exe -m pytest tests/test_laya_social_contract.py -q --tb=short`

**16 failed, 2 passed in 2.96 seconds.** Exit 1, completed before timeout. No warnings in final run.

- 11 parameterized social tests fail because `laya_screen` is missing.
- No Laya opinion / negative historical Laya opinion still block otherwise valid proposals (2 failures).
- Stale quote and cash reserve checks are masked by the obsolete Laya gate (2 failures).
- Completed research calls `count_context` and `decide` despite a graph with no social posts (1 failure).
- Positive historical opinion case still creates a bounded proposal (pass).
- Pause and paper-account provenance prevent fake submission (pass).

The first run was 17 failed / 1 passed because the new module had not imported the suite's Windows event-loop pipe exception fixture. This was a test setup defect, fixed before the reported baseline. Neither run contacted a real broker or model.

## Coverage and limitations

Covered: raw separate post payloads; no TypeSafe key dependency; multilingual request; individual stance counts; weak relevance retained; low stance probability unclear; malformed/nonfinite distributions retain posts; timeout not retried; bounded post count; empty input sends no inference; historical gate independence; quote and cash reserve enforcement; research creates no final model-review request; proposal creation places no orders; pause and paper identity remain enforced.

Not proven by these offline fakes: actual semantic accuracy, real model token budget, SDK network timeout, cross-batch singleflight, cancellation after a remote timeout, UI behavior, real social feed wiring, or durable historical artifact preservation. The fake's peak concurrency checks only a single callback batch. SWE/red must add integration tests for actual social-fetcher wiring, effective timeout/global dispatch bounds, and genuine MCP response shapes. PM must perform bounded live validation and visible UAT, without converting fake success into end-to-end claims.

Confession: I implemented only the two owned test/evidence files, did not alter production, and did not advance Gate. The suite deliberately fails current behavior; this is successful red-baseline preparation, not a product PASS. The existing service tests supply fake fixtures; those shared fixtures may evolve, so independent red review should inspect their continued fidelity.

Reasoning HSM: `session-1792115123684-82944`.
