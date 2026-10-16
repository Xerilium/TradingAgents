# T-1.9 independent red review

2026-10-15. Verdict: **PASS for source and offline tokenizer verification; runtime deployment remains unverified.**

Reviewed the actual adapter diff in `C:/Users/brett/maenifold/laya-mcp`: `src/laya_mcp/core/context.py` and `core/engine.py`, plus both new context test modules. No production files changed by this reviewer.

## Findings

- Preflight resolves the bundled `convaiinnovations/laya/multilingual` or standalone `convaiinnovations/laya-multilingual` layout according to the same `standalone_repos` setting used when constructing the runtime router. Configuration and tokenizer are read from the same resolved snapshot directory. Installed SDK router repository mappings agree.
- The checkpoint's `rl_agent_config.json` supplies `head_max_len`; a missing field falls back to 192 exactly as installed `laya/agent.py` does. The actual cached bundled checkpoint uses 256. The synthetic 273 test prevents accidentally accepting a hardcoded 256 fix.
- Nonpositive, boolean, string and null head limits fail closed. Missing or malformed configuration also raises before inference rather than substituting a guessed limit.
- `count_context` now passes the effective configured head budget explicitly. The inference path still measures with the loaded agent's own configuration and rejects incomplete question/options or any sequence exceeding 8192 before `system_one` executes. This rejection path was not weakened by the diff.
- Real cached tokenizer tests verify exact hashes/counts and head boundaries 255/256/257 plus full sequence boundaries 8191/8192/8193. They prohibit weights loading and forward execution. The total-boundary tests count overflow; they are not a live inference rejection test.

## Independent execution

Ran the exact expanded command from `LAYA_T19_SWE.md`, from the adapter repository, through `.paper-desk/run-bounded.py --seconds 60`. Result: **69 passed in 15.11 seconds**, exit 0. Modules: `test_context_head_budget.py`, `test_context_config.py`, `test_cache_identity.py`, `test_contract_regression.py`. No installations or network model downloads were performed.

## Deployment gap and confession

This review proves the inspected source and bounded offline tests, not that an already-running Laya process has imported the change. No inference, runtime restart, provider or broker action, commit, or Gate transition was performed. Standalone layout coverage uses synthetic configuration; only the bundled tokenizer was tested from a real cached checkpoint. No claim about sentiment classification quality is made. PM owns deployment verification and Gate transition.

Reasoning HSM: `session-1792115655957-91646`. No memory sources used or changed.
