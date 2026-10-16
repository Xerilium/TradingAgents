# T-1.1 provider cancellation re-audit

Scope: the prior provider cancellation P1 only. Full Gate acceptance is not granted by this review. No product files changed, provider transmissions, inference, restarts, or Gate transitions performed.

## Independent reproduction

The following offline probe exercises actual `summarize`, `ChatGPTChatModel._agenerate`, `_generate`, `_generate_once`, and `_AppServer.receive/rpc`. Only process startup, wire writes, and process teardown are replaced with an in-memory transport. No Codex process starts.

```python
import asyncio
import queue
import threading
import time
from collections import deque
from unittest.mock import patch
from tradingagents.llm_clients import chatgpt_client as c
from tradingagents.web import laya_review as r

servers = []
class Transport(c._AppServer):
    def __init__(self, timeout):
        self.deadline = time.monotonic() + timeout
        self.messages = queue.Queue()
        self.events = deque()
        self.request_id = 0
        self.closed = False
        self.writes = []
        for i, result in enumerate([{}, {'account': {'type': 'chatgpt'}},
                {'config': {}}, {'thread': {'id': 'offline'}, 'model': 'offline'},
                {'turn': {'id': 'offline'}}], 1):
            self.messages.put({'id': i, 'result': result})
        servers.append(self)
    def send(self, message):
        self._check_request()
        self.writes.append(message)
    def close(self):
        self.closed = True

started = time.monotonic()
token = r._cancelled.set(lambda: time.monotonic() - started > .05)
try:
    with patch.object(c, '_AppServer', Transport):
        try:
            r.summarize(c.ChatGPTChatModel(model_name='offline'), {})
        except InterruptedError:
            elapsed = time.monotonic() - started
        else:
            raise AssertionError('Expected cancellation')
finally:
    r._cancelled.reset(token)
assert len(servers) == 1 and servers[0].closed
assert elapsed < 1
assert len([m for m in servers[0].writes if m.get('method') == 'turn/start']) == 1
print('actual provider path cancellation:', round(elapsed, 3), 'seconds; one helper, closed; one turn')

servers.clear()
started = time.monotonic()
with patch.object(c, '_AppServer', Transport):
    try:
        c.ChatGPTChatModel(model_name='offline', timeout=.05).invoke('offline')
    except TimeoutError:
        elapsed = time.monotonic() - started
    else:
        raise AssertionError('Expected deadline')
assert len(servers) == 1 and servers[0].closed and elapsed < 1
print('actual provider path deadline:', round(elapsed, 3), 'seconds; one helper, closed')
```

## Result

**PASS for correction of the prior cancellation P1**, independently verified on current working files.

- Probe above: cancellation returned in **0.125 seconds**, exactly one helper and one turn, helper closed before return. Actual provider deadline returned in **0.063 seconds**, one helper closed. Both executed under a 10-second hard process timeout.
- **62 passed in 1.01 seconds**: `test_laya_provider_cancellation.py`, `test_chatgpt_client.py`, `test_laya_review_budget.py`, under a 60-second hard process timeout. Initial sandbox execution failed during test setup due the known Windows temporary-directory permissions issue; the one approved fresh-directory rerun passed. No failed product test was hidden.
- Summary clones now expose and set `max_retries=0`; the actual provider test verifies one attempt after 429. Default provider remains three retries with capped waits, verified `[25, 50, 60]` and `[60, 60, 60]`. Server-requested delays over 60 seconds remain deferred rather than retried early, as before.
- The async wrapper sends a request-specific cancellation signal and joins its worker. The actual receive loop checks every 100 milliseconds; backoff uses interruptible event waiting. Retry admission checks both cancellation and a single monotonic deadline. Each helper receives only the remaining budget. No timeout retry was added.

Limits: cancellation is cooperative, not hard thread termination. Process cleanup is separately bounded by three 3-second waits plus a 1-second reader join, so the inference/request deadline does not promise an identical wall-clock completion deadline including cleanup. This review used an in-memory transport and existing mocked process-cleanup tests; it did not prove live helper shutdown or cancel a native Laya model forward. OS process creation and pipe writes are not independently interruptible by this cooperative signal. No residual reproducible retry-after-cancel defect was found in the reviewed path.

Full T-1.1 still requires the separate saved-packet semantic-fidelity approval/check, managed live Gateway/model validation and UI acceptance. This narrow pass must not be used as overall Gate completion evidence.

## ConfessionReport

Reasoning HSM: `session-1792108409447-53118`. Creation succeeded but printing its response hit a Windows encoding error; the exact persisted session was recovered without creating a duplicate. Only this review file was edited. No reusable project memory was read or written. Source, scoped regression execution, and a transport-boundary independent probe support the narrow pass; no live provider behavior is claimed.
