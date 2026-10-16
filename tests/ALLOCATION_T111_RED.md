# T-1.11 independent red verification

Date: 2026-10-15. Reasoning session: `session-1792116896384-61555`.

Verdict: **PASS for the scoped source and offline regression contract**. No blocking finding. This does not certify a newly generated live model report, deployed process, rendered UI, or broker execution; those layers remain separate coordinator acceptance work.

## Independent evidence

After SWE's final-source handoff, ran:

```powershell
rtk proxy .venv/Scripts/python.exe .paper-desk/run-bounded.py --seconds 60 -- .venv/Scripts/python.exe -m pytest tests/test_desk_allocation_context.py tests/test_desk_policy_schemas.py tests/test_paper_engine.py tests/test_paper_service.py tests/test_paper_server.py tests/test_quote_refresh.py -q --tb=short
```

Result: **314 passed in 37.78 seconds**, exit 0. These are local tests with fake model/broker fixtures. The tests cover configured-policy injection, actual LangGraph state projection, all six downstream prompt consumers, successful desk/ordinary structured schema selection, invariant proposal quantities, paper execution guards, service/server regressions, and quote-reference wording.

## Source audit

- `service.py::desk_execution_policy` uses the saved configuration and full configured universe, not just selected research symbols. Buy uses `min(allocation / universe_count, position_cap)`; Overweight multiplies that target by 0.75. The text states holdings subtraction, reserve and total allocation constraints, order caps, open-order reservations, whole shares, long-only behavior, no sales funding same-batch buys, fresh two-sided execution quotes and manual submission. Underweight and Sell match the existing half/all available-holdings behavior.
- `AgentState.desk_execution_policy` preserves the context through real graph projection. Research Manager consumes it directly; Trader, Portfolio Manager and the three risk debaters consume it through portfolio context. Desk prompt branches remove the conflicting conviction/standard-allocation sizing requests.
- `DeskResearchPlan`, `DeskTraderProposal` and `DeskPortfolioDecision` remove conflicting schema instructions. The trader's sizing field is null-only. Successful structured invocation tests explicitly forbid fallback and verify the schema actually invoked; ordinary callers retain ordinary schemas. Free-text fallback tests separately verify all six consumed prompts.
- `paper/engine.py::plan_orders` quantity calculations are unchanged. Its existing working-tree diff removes the separately authorized retired Laya approval dependency; it does not change the quantity formulas. The regression suite confirms research sizing prose does not alter calculated Buy/Overweight/Underweight/Sell quantities. No new approval model, prose parser or order submission path was added for T-1.11.
- `app.js::previewOrder` explicitly identifies policy/book-derived quantity, advisory research, exact order details and manual submission, with a link to associated research. This reviewer inspected source only; coordinator owns rendered UI verification.
- `research_quote_context` preserves historical-date omission and execution freshness/validity fields. The authorized wording addition distinguishes same-session market-closed observations from execution freshness; older observations are session-unverified and are not represented as the latest close. The regression verifies that a closed-market reference can still be execution-stale and unusable for an order.
- Policy is injected and persisted for new results. No migration or rewriting of historical research reports was introduced by the allocation changes.

## Limits and confession

The reviewer edited only this report and did not change implementation, fixtures, saved live runs, configuration, accounts or Gate state. No live inference, broker transaction, install or restart was performed. Passing fake-model tests proves context/schema plumbing, not universal model compliance with prose instructions. The existing baseline's numeric substring checks are supplemented by direct formula inspection, not a claim of exhaustive mathematical proof. An initial attempt to read the acceptance file at repository root failed; its actual `tests/FINAL_PRODUCT_ACCEPTANCE.md` path was then read successfully. Gate transitions and final deployed/live acceptance belong to the coordinator.
