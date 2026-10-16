# T-1.7 blue-team regression evidence

Created `C:/Users/brett/maenifold/laya-mcp/tests/test_contract_regression.py` only; no production changes, inference, provider requests, broker calls, or Gate transitions.

The tests import the pure contract module directly, avoiding model startup. The saved forward receipt contributed only the two raw numeric answers (0.9935 and 0.9916, saturated action probability 1.0); no research text, account context, or full private fixture was copied.

Command (hard 30-second deadline):

```text
rtk proxy C:/src/TradingAgents/.venv/Scripts/python.exe C:/src/TradingAgents/.paper-desk/run-bounded.py --seconds 30 -- C:/src/TradingAgents/.venv/Scripts/python.exe -m pytest C:/Users/brett/maenifold/laya-mcp/tests/test_contract_regression.py -o addopts= -q --tb=no
```

Baseline: **18 failed, 12 passed**. Failures demonstrate saturated/invalid action heads forcing review or crashing; half-sized binary margins versus the public top1-minus-top2 margin; an unselected human option vetoing an ordinary selected outcome; explicit true `needs_human_review` failing to escalate; action-derived false human-risk reasons on low confidence; and empty, missing, invalid, or partial answer sets permitting autonomous contracts.

Passing controls retain selected human-review choice escalation, narrow-runner-up escalation, and false explicit human-review boolean behavior. Invalid answer tests permit explicit ValueError/TypeError rejection or a non-autonomous result with reasons; they do not require an invented production response schema.

This is intentionally red-phase evidence, not acceptance. Tests exercise the contract function, not REST/MCP serialization or a live model. A developer must fix production semantics, then an independent reviewer must inspect false-positive and false-negative behavior and integrations. Pure `auto_execute` is not proof that a trade is authorized.

Thinking HSM: `session-1792113847352-38998`.

Confession: I did not perform live UAT, run model inference, verify provider restart, or inspect every adapter endpoint. I read the existing smoke tests and actual numeric receipt. The task-specific suite is reproducible without that receipt. No private state was rewritten.
