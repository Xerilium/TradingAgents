# T-1.9 blue-team: checkpoint head budget

Reproduced on 2026-10-15 with the real cached multilingual tokenizer and checkpoint configuration. Owned additions only: adapter `tests/test_context_head_budget.py` and this report. No production edits, model forwards, installs, runtime restarts, provider calls, broker actions or Gate transitions.

Cached checkpoint `convaiinnovations/laya` revision `7b928d828b7b0e022f929d9bd2e44165aa270148` has `multilingual/rl_agent_config.json` head_max_len **256**. The SDK's head budget includes instruction tokens and option tokens/markers; sequence separators are outside it. Tests construct and measure this exact combined head, not a guessed instruction length.

## Red result

**5 failed, 1 passed in 14.54 seconds**, inside a 60-second hard process deadline.

| Boundary | SDK with actual checkpoint | Current count_context |
|---|---|---|
| 255-token head | Complete | Incorrectly incomplete (FAIL) |
| 256-token head | Complete | Incorrectly incomplete (FAIL) |
| 257-token head | Clipped | Incomplete (PASS) |
| Full sequence 8191, head 256 | Head complete, entire sequence fits | Exact count, falsely incomplete head (FAIL) |
| Full sequence 8192, head 256 | Head complete, entire sequence fits | Exact count, falsely incomplete head (FAIL) |
| Full sequence 8193, head 256 | Head complete, total exceeds limit | Exact count, falsely incomplete head (FAIL) |

The test also matches counted sequence hashes to untruncated actual-config reference. Both engine.load and Agent.system_one are patched to fail if invoked. Thus these results establish preflight inconsistency, not model-answer quality. This defect does not explain the short semantic-control failures from the earlier audit.

## Reproduce

Run from `C:/Users/brett/maenifold/laya-mcp`:

```text
rtk proxy C:/src/TradingAgents/.venv/Scripts/python.exe C:/src/TradingAgents/.paper-desk/run-bounded.py --seconds 60 -- C:/Users/brett/maenifold/laya-mcp/.venv/Scripts/python.exe -c "import os,sys; os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'; sys.path.append('C:/src/TradingAgents/.venv/Lib/site-packages'); import pytest; raise SystemExit(pytest.main(['tests/test_context_head_budget.py','-o','addopts=','-q','--tb=short']))"
```

The adapter environment lacks pytest; this command imports existing pure-Python pytest from TradingAgents after the adapter's dependencies, without installation. Auto-discovery is disabled to avoid unrelated project plugins. Initial harness attempts failed due missing pytest, unrelated plugin native dependency, then too-broad cached-snapshot selection; those were corrected before the recorded red run. All snapshot reads now request local-only specific files and cannot download.

Thinking HSM: `session-1792114841567-75908`.

Confession: no live inference or UI UAT performed; only the named tokenizer/preflight scope is covered. No standalone-repository configuration case is tested. Production fixes must use the selected checkpoint configuration and retain oversized-input rejection; these tests do not authorize weakening token safeguards or changing confidence policy.
