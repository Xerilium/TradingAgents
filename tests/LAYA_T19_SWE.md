# T-1.9 SWE: checkpoint-specific head budget

2026-10-15. Adapter source at `C:/Users/brett/maenifold/laya-mcp`.

## Change

`src/laya_mcp/core/context.py` now reads `rl_agent_config.json` from the same selected cached checkpoint directory as the tokenizer. It returns the effective `head_max_len` with checkpoint identity. Bundled and standalone repository layouts are supported. Missing field uses 192, matching installed SDK `laya/agent.py:282`; malformed, noninteger, boolean, zero or negative values fail closed. Missing config file still fails rather than guessing.

`src/laya_mcp/core/engine.py:count_context` passes that value explicitly to `inspect_context`. Thus the installed bundled multilingual checkpoint's 256-token head is measured exactly. No global switch to a guessed 256 constant. Inference continues to check the loaded agent's own configuration and reject incomplete questions or sequences beyond 8192; that path is unchanged.

Added `tests/test_context_config.py` for both selected repository layouts, a deliberately nonstandard 273-token configured head, SDK missing-field fallback, local-only resolution, and invalid configuration. Blue team's `tests/test_context_head_budget.py` is unchanged.

## Validation

Original blue baseline: 5 failed, 1 passed. First green run with cache identity tests: 9 passed in 12.99 seconds.

Expanded final run: **69 passed in 17.43 seconds**, hard deadline 60 seconds:

```text
rtk proxy C:/src/TradingAgents/.venv/Scripts/python.exe C:/src/TradingAgents/.paper-desk/run-bounded.py --seconds 60 -- C:/Users/brett/maenifold/laya-mcp/.venv/Scripts/python.exe -c "import os,sys; os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'; sys.path.append('C:/src/TradingAgents/.venv/Lib/site-packages'); import pytest; raise SystemExit(pytest.main(['tests/test_context_head_budget.py','tests/test_context_config.py','tests/test_cache_identity.py','tests/test_contract_regression.py','-o','addopts=','-q','--tb=short']))"
```

Run cwd: `C:/Users/brett/maenifold/laya-mcp`. Tests use the real cached multilingual tokenizer for head 255/256/257 and total sequence 8191/8192/8193 boundaries; weights loading and forward methods are prohibited by blue fixtures. Standalone resolution is tested with isolated synthetic configuration, not a live standalone checkpoint.

## Confession

No inference, provider requests, installs, runtime restart, broker actions, commit, or Gate transition. This is a source fix with offline exact-tokenizer validation, not deployed runtime verification. The preserved 8192 rejection is source-inspected and boundary-count tested; no real forward was attempted. It does not assert classification quality. Independent review remains the coordinator's next step.

Thinking HSM: `session-1792115518722-87190`. No memory:// sources used or changed.
