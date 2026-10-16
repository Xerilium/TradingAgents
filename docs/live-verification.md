# Corrected paper desk: live verification

Historical verification record: this describes the 2026-10-14 implementation.
Its final research Laya approval gate was retired by T-1.10. Current behavior
uses Laya for per-post social sentiment and retains manual/deterministic trading
safeguards; see [current operation](paper-trading.md). The observations below
remain unchanged as historical evidence.

Verified on 2026-10-14 against `http://localhost:8080/mcp`, using the official
MCP SDK and the existing FANGMAN profile. Account identifiers, credentials and
financial payloads were excluded from the request-count log.

| Requirement | Observed evidence |
|---|---|
| Live Alpaca paper connection | Paper mode verified; seven quotes, linked AAPL daily chart, holdings and order reads succeeded |
| Maenifold tool integration | The AAPL-scoped LangChain `maenifold_memory__SearchMemories` tool returned a structured response through the SDK |
| Live Codex research | Run `7fcdcca7-6820-48f3-83f1-7b3f17561369` completed AAPL research for 2026-10-14 in 188.2 seconds, with all nine reports/debates |
| Live Laya review | `laya.decide` returned `ask_human`, with `auto_execute=false`; the UI displays the review requirement alongside the Overweight rating |
| Guarded paper proposals | Seven proposals created; AAPL blocked by Laya and the other six stocks blocked by missing current research |
| No unintended execution | Zero `place_stock_order` or `cancel_order_by_id` calls; no paper order submitted |
| Idle traffic removed | Disconnected idle: 48 seconds; connected idle: 82.4 seconds; post-completion idle: 80.8 seconds. Each window had zero desk HTTP requests, MCP calls and Codex account checks |
| Report loop removed | Successful verification run: 13 detail fetches across 50 state reads and 17 result revisions, rather than repeated fetches for an unchanged revision |
| Account checks are explicit | One account check for the successful research launch; state reads did not launch checks |
| Retained failed-run evidence | The failed attempt's nine reports remain visible with its failure message |
| Regression checks | 1,486 offline tests and 103 subtests passed; four expected skips and one integration test excluded. JavaScript workflow, collection, timeout and request-count checks pass |

The first live attempt, `e6b2cda7-41ba-40f8-89d0-4cbdd1c13ddf`, failed because
the temporary verification harness used a 30-second MCP timeout. Laya reported
38.1 seconds of model loading and 43.4 seconds of inference. The failed run was
preserved. The successful attempt used the ordinary desk's 90-second MCP limit.

Live verification found and corrected two UI issues: a failed result's `error`
field was mistaken for an HTTP failure, hiding its reports; and removing a
focused filtered row could access a missing replacement input. Both have
regression coverage.

The temporary harness recorded request names and counts around the actual
`DeskService`, `DeskHandler` and SDK transport. It was bounded by a fifteen-minute
watchdog and has stopped. The ordinary desk was then started against the same
profile and completed research journal.

This verifies live research and the execution guard for this observed review
case. It does not claim a broker fill: Laya required human review, so submitting
an order would have violated the execution policy. The 500-stock collection
checks are documented separately in [UI scale verification](ui-scale-research.md).

## META selection and 429 UAT — October 14, 2026

The workspace checkbox previously changed only the research selection; it did
not focus the chart. Clicking a stock while account equity was selected also
left the equity chart in place. Initial chart loading could display an empty
state instead of progress, and an empty snapshot array prevented a detail fetch.

Stock rows, ticker buttons and checked research boxes now link the quote,
stock chart and research context. An empty snapshot fetches once; a genuinely
empty response offers explicit retry. Rapid switching keeps one chart request
in flight and then loads only the latest selected stock.

Rate-limited read-only Gateway calls and Codex model requests make at most four
attempts: the initial call plus three retries. Delay is
`min(60, Retry-After-or-30 * 2**retry_index)` seconds. Numeric and HTTP-date
Retry-After values are supported. Shared Gateway backoff suppresses competing
requests. Orders are not replayed. After exhaustion, the UI shows an actionable
429 state; completed research and the last verified account snapshot remain.
SDK attempts retain their 90-second deadlines. Chart/refresh browser requests
have a 550-second deadline to accommodate four bounded attempts plus backoff;
ordinary local reads retain 15 seconds. Retries are owned by the backend, so
the browser does not multiply the retry count.

Verified in the actual browser: META row selection, checkbox focus from account
equity mode, AAPL/META linked charts, watchlist filtering and next-stock
navigation. The isolated HTTP/UI fixture on port 8090 used no model or broker:
META failed three times and loaded on attempt four; NVDA failed four times and
stopped. Recorded counts: AAPL 1, META 4, NVDA 4. Offline checks passed:
167 Python tests, five frontend regression scripts, and Ruff. No research or
order was submitted during this UAT.

Artifacts: `.impeccable/review/linked-uat-check.cjs`,
`serve-retry-uat.py`, `retry-uat-counts.json`, and `tests/test_paper_rate_limits.py`.

Retry semantics reference: [RFC 6585, section 4](https://www.rfc-editor.org/rfc/rfc6585#section-4)
(accessed October 14, 2026). The 60-second clamp is the user's explicit policy.

## Implementation sources

- `tradingagents/web/service.py`: `state`, `readiness`, `_run`, `propose`.
- `tradingagents/web/static/app.js`: `api`, `ensureResultDetail`, `readState`, polling guard.
- `tradingagents/integrations/maenifold.py`: `SdkMcpTransport`, `build_langchain_tools`.
- Local receipts: `.paper-desk/live-final-audit.json`, `live-proof.jsonl`,
  `live-proof-first.jsonl`, `live-idle-connected-result.json`,
  `live-run-first-result.json`, `live-proposal-result.json`.
- Request-count regression: `.impeccable/review/backend-traffic-check.cjs`.
