# Bounded feeds acceptance plan

Prepared from current source on 2026-10-15. This is a plan, not live proof. No feed, model, account, broker, or restart call was made during preparation.

## Configured path

`.paper-desk/desk.json` top-level config selects ChatGPT via the installed Codex app-server, quick model `gpt-6-luna`, deep model `gpt-6.1-sol`, and no backend URL. No Azure endpoint or new credentials are needed for this configured path. Current sign-in and model availability remain unverified here. `chatgpt_client.check_chatgpt_account(timeout=10)` is the existing bounded readiness probe, without credential disclosure.

`service.py` builds the research graph with `social_screen_factory`. `create_sentiment_analyst` fetches news, StockTwits, then Reddit; it injects per-source `laya_screen` callbacks. The quick-tier model receives those source blocks and produces `sentiment_report`; it neither places orders nor decides the portfolio recommendation. The full graph must still be verified separately for recommendation propagation.

## Feed bounds and caveats

- StockTwits: `vendors/stocktwits.py:fetch_stocktwits_messages`, public symbol stream, one request, default timeout 10 seconds. Date filter precedes screening. All eligible received bodies go to the screen; `limit=30` limits displayed rows, not screening inputs. The Laya callback separately caps classified posts. Failure returns an explicit unavailable marker.
- Reddit: `vendors/reddit.py:fetch_reddit_posts`, one combined subreddit RSS search, default timeout 10 seconds, 5 MiB response cap. One 429 retry. Numeric Retry-After capped at 60 seconds; absent-header jitter is 48–72 seconds, so the existing fallback is not strictly clamped to 60. Screening gets title/body excerpts capped at 1,000 characters. Failure is distinct from no matching posts.
- News: `vendors/yahoo/news.py:get_news_yfinance`, Yahoo quote feed then search fallback. `yf_retry` allows three 429 retries with 2/4/8 second waits. No explicit request timeout is passed by this function; a hard process deadline is essential for acceptance. Default news article limit 20. Date filtering does not make live feeds a historical archive.
- Laya: `agents/post_screen.py:laya_screen`, shared serial 30-post/120-second budget, 60-second per-command outer bound, multilingual token preflight then classification. Uncertain/error/unprocessed posts remain visible. Classification is evidence, not authorization. For the smallest live acceptance use a shared **one-post** budget across both social callbacks, not a 30-post batch.

## Proposed smallest actual-source acceptance harness

The separate `tests/feeds_live_acceptance.py` is implemented and syntax-checked, but has not been executed. It does not instantiate DeskService or TradingAgentsGraph: that would add unrelated account/tool surfaces. The harness does the following:

1. Read only the top-level desk config; build default config plus those values. Apply `quick_think_provider=config['llm_provider']` exactly as the service does. Initialize dataflow config with the resulting defaults. Do not print configuration or environment wholesale.
2. Exclusively create a unique receipt before dispatch, recording ticker META, current analysis date, seven-day window, configured provider/model, and prepared status. Refuse existing receipts to prevent accidental replay. Do not touch the saved journal.
3. Create a `MaenifoldGateway(timeout=60)` wrapper which permits only `laya/count_context` and `laya/decide`, discovers only Laya, and journals each dispatch/result. Reject every other domain/command, including every Alpaca command.
4. Create the real sentiment node with `create_tier_client(config, 'quick', timeout=90).get_llm()` and `create_sentiment_analyst(llm, screen_factory=...)`. The factory wraps production `laya_screen` with one shared remaining-post budget, captures evidence, and records source identity. Feed functions remain real and unmocked; capture returned source blocks and raw-source observation receipts without refetching.
5. Invoke that node exactly once with `company_of_interest='META'`, current `trade_date`, empty messages, and instrument context identifying Meta Platforms. No graph propagation, risk decision, proposal creation, or order submission. Structured-output helper may fall back once to free text; instrument and record actual model-call counts rather than claiming exactly one inference.
6. Save source blocks, source errors/coverage, post text/hash, Laya typed answers and preflight/actual input hashes, model report, timings, and errors. Mark a transport failure as unavailable, never neutral sentiment. Persist before and after each stage so deadline termination leaves useful evidence.

Command for the coordinator's later live run:

```powershell
rtk proxy .venv/Scripts/python.exe .paper-desk/run-bounded.py --seconds 300 -- .venv/Scripts/python.exe -m tests.feeds_live_acceptance --ticker META
```

The parent should inspect the same process handle if the tool yields. Do not restart after an observation timeout. Stop after this one run and inspect the receipt. If all social sources fail, feed handling can pass but real-post Laya propagation remains unverified; synthetic controls are not a substitute for that claim.

## Acceptance criteria

- At least one actual dated social post is classified through the MCP SDK; exact post/hash and typed results are retained. Preflight and inference hashes/counts agree.
- Real source failures and unscreened remainder appear honestly in the analyst input and final report; no fabricated posts, votes, or sentiment observations.
- Analyst report is produced by configured quick provider/model from the captured feed blocks. No final-research Laya approval occurs.
- Receipt contains zero Alpaca calls and zero saved-journal writes. Safeguards are verified with offline engine/service tests, never test transactions in the user's paper account.
- Broader recommendation and proposal acceptance is a separate frozen-evidence graph/engine test. Preserve manual approval, paper account verification, fresh quote handling, allocation/position/cash/notional checks, duplicate-submit prevention, and stale-research protection. A successful sentiment-only run cannot prove the whole goal complete.

## Existing coverage to reuse

`test_laya_social_contract.py` covers per-post role, bounded behavior, legacy gate removal, and retained trading checks. `test_social_lookahead.py` covers date-window behavior. `laya_social_live_control.py` covers synthetic single-post labels and input hashes; it does not prove real feed availability or analyst consumption. UI fixtures establish rendering only, not live source execution.

## Source

Current working tree: `tradingagents/agents/post_screen.py`, `agents/analysts/sentiment_analyst.py`, `agents/structured.py`, `dataflows/vendors/stocktwits.py`, `dataflows/vendors/reddit.py`, `dataflows/vendors/yahoo/news.py`, `dataflows/vendors/yahoo/common.py`, `llm_clients/factory.py`, `llm_clients/chatgpt_client.py`, `web/service.py`, `default_config.py`, `README.md`; inspected 2026-10-15. No memory corpus relied upon.
