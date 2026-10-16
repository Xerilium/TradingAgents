# T-1.11 allocation context: independent red baseline

Date: 2026-10-15. Reasoning session: `session-1792116804784-40934`.

Scope: write offline tests before implementation. Production files were not edited. No live provider, broker, install or restart calls were made. Gate transitions belong to the coordinator.

## Source findings and contract

`tradingagents/paper/engine.py::plan_orders` already defines deterministic quantities from saved configuration and the broker book. Research prose is advisory. `tests/FINAL_PRODUCT_ACCEPTANCE.md` records the observed undefined 0.05x starter suggestion and correctly narrows the defect to absent policy context and conflicting prompts.

Agreed interface with SWE: `desk_execution_policy`, a rendered string in graph state. The service must inject the saved configuration; the declared `AgentState` must preserve it; Research Manager, Trader, Portfolio Manager and all three risk debaters must consume it. Desk prompts must stop positively soliciting invented standard allocations or conviction-dependent sizes. The ordinary research path remains separate. Structured output field descriptions also need desk-specific treatment; the baseline tests do not prove those descriptions.

## Executed baseline

Command:

```powershell
rtk proxy .venv/Scripts/python.exe .paper-desk/run-bounded.py --seconds 60 -- .venv/Scripts/python.exe -m pytest tests/test_desk_allocation_context.py -q --tb=short
```

Result: **8 failed, 4 passed in 1.39 seconds**, exit 1. All eight failures are expected missing-feature assertions, not import/runtime setup errors:

- Actual `DeskService` run does not inject policy into `stream_run` input.
- A real compiled LangGraph with production `AgentState` drops the undeclared policy key.
- Each of the six downstream model prompts omits the policy marker.

Four passing engine tests demonstrate unchanged quantities with and without invented sizing commentary: Buy 100, Overweight 75, Underweight 10, Sell 20, with no price buffer and sufficient caps/cash. Whole-share deterministic sizing remains the contract.

The service test uses a four-symbol configured universe with only AAPL selected for research, checking that custom allocation 64%, position cap 19%, reserve 23%, order cap 4321 and buffer 17 basis points reach the context. Derived Buy target is 16% and Overweight target 12%. This catches using the selected research subset as the denominator. It uses an existing fake broker and asserts no submitted order.

## Limits and handoff

The baseline is deliberately red and is not acceptance of delivered behavior. The graph test checks actual schema projection with a single consumer node; the prompt tests invoke the real node factories with a fake model. They do not make a full remote model run. Numeric text checks prove presence, not every formula's wording; independent review must check the prose accurately states caps, holdings subtraction, reserve, whole shares, long-only, executable quote freshness and explicit manual submission. UI and structured-schema behavior require SWE/reviewer coverage. Historical live reports must remain unchanged.
