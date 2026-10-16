# T-1.10 active social sentiment flow

Read-only investigation, 2026-10-15. HSM: session-1792115128957-97499.

## Active route

The desk does not dispatch Printer workflows. `tradingagents/web/service.py:904` constructs local `TradingAgentsGraph`, then streams it. `tradingagents/graph/trading_graph.py:102` constructs `GraphSetup`; `tradingagents/graph/setup.py:131` constructs the social analyst. That analyst deliberately receives no supplemental tools (`graph/analyst_execution.py:30,74`). Adding a Laya LangChain tool does not connect it to social screening.

`agents/analysts/sentiment_analyst.py:73` obtains `jev_screen(ticker)` and supplies it to StockTwits and Reddit fetchers. Both fetchers filter by analysis window before calling their screen hook. StockTwits supplies message bodies (`dataflows/vendors/stocktwits.py:131`); Reddit supplies title/body clipped to 1000 characters (`dataflows/vendors/reddit.py:305`). The hook returns one keep flag per supplied post plus a textual summary; that summary enters the LLM sentiment prompt alongside retained posts. The LLM creates the sentiment report and does not itself execute trades.

Printer's sibling `C:/src/printer/apps/tradingagents/tradingagents/agents/post_screen.py` names Laya, uses one worker and a 60-second timeout, but still calls TypeSafe-compatible `/v1/systemone` with environment-based endpoint/key and default `jev-latest`. Its narrow relevance/stance questions are a useful reference; its transport is not the requested Maenifold SDK integration. No Printer edits are needed for this desk.

## Minimal implementation boundary

Inject an optional screen factory through TradingAgentsGraph, GraphSetup and create_sentiment_analyst. The desk supplies a factory using its existing Gateway object and a distinct source identity for each StockTwits/Reddit callback. Other graph consumers can retain the existing optional Jev behavior. The classifier reads individual actual post text, not the generated sentiment report. Preserve uncertain posts and mark unavailable screening explicitly. Do not copy concurrency-heavy upstream behavior; use bounded serial requests and a total sample/time budget with an explicit unclassified remainder.

Persist per-source counts and per-post classifications under a new result field such as `social_sentiment`, with status, text/hash, model, timestamps and uncertainty. The service factory can capture its current result/run and update under the existing store lock with revision/save. This avoids requiring a new LangGraph state field. Existing `gateway_observation` plus service `_run`'s `capture_vendor_evidence` already records exact gateway request/response artifacts. A callback must be created for the current symbol rather than accidentally retaining a later loop result.

Display the new evidence as social classification, never trading clearance. Store compact summaries should exclude long per-post payloads. Keep legacy Laya review artifacts readable as historical, retired research checks; do not rewrite them. Clearly distinguish unavailable/unscreened from neutral sentiment. Reddit's clipping must be disclosed as excerpt provenance or removed before exact input-size preflight; never label an excerpt as the full post.

## Approval removals and preserved safeguards

Remove the post-research call and approval calculation in `web/service.py:979-1014`; graph completion/rating should finish research independently of social classifier availability. Remove `paper/engine.py:232`'s Laya auto_execute prerequisite. Remove only the Laya portion of `web/service.py:1106` `_review` predicate; retain exactly-one completed result and its evidence hash.

Preserve `_submission_guard` in full: paused state, proposed status, 15-minute freshness, same account/date/config/run, unchanged evidence and order arguments, current verified broker snapshot, durable submission intent, and `validate_proposal`. Preserve paper-server verification immediately before submit, tradable US-equity check, unknown-submission reconciliation, universe restriction, quote freshness, whole-share sizing, no overselling, open-order reservations, cash reserve, concentration/allocation/order caps and manual submission.

UI locations: `web/static/app.js:103-106` Laya clearance labels/filters; watchlist filters at272; report rendering at366-411. Replace clearance language with research status and show the new social evidence. `web/store.py:149-159,206-214` currently reduces the old Laya gate for dashboard snapshots; update those summaries consistently.

## Verification limits

Source mapping only. No production edits, inference, orders, server restart, live social fetch, or UI claims. Source lines may move during parallel implementation. No memory sources used.
