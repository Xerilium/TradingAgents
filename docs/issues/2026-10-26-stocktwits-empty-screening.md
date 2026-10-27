# Valid empty StockTwits results were not recorded as screened

Status: Live ACLS retry completed; all 23 configured stocks have completed research
Reported: 26 October 2026

## Observed failure

The latest ACLS research saved its reports and final decision, but completion rejected StockTwits as not_screened with unknown totals. The sentiment report described no posts in the requested window. Reddit had correctly recorded its own empty result. The combined universe has 22 completed stocks and ACLS failed. Preserve the 22 completed results.

## Repair

After a successful response with a valid message list, the StockTwits empty branch now invokes the existing screening callback with an empty list. Laya records empty, total_count 0 and classified_count 0; the existing completion check accepts that evidence. The dated coverage-gap check runs first. HTTP errors, invalid JSON, malformed message lists, invalid message IDs/dates and a nonpositive or noninteger limit remain unavailable rather than becoming empty success. The configured 100-post request and classification of acquired posts remain unchanged.

The source review did not establish an application-level status schema for a successful HTTP response containing an embedded provider error. Do not claim that unverified case is covered.

## Validation and limits

Terra source review traced fetch_stocktwits_messages, Laya empty screening and research_gaps. No requests, tests, mocks, test scripts, builds or app actions were used for that review. This file currently has 19 additions and 7 removals over the starting revision, including the earlier patch. After the canonical reload, the actual ACLS retry saved Social sentiment with Screening: completed and both StockTwits and Reddit showing empty, 0 of 0 fetched posts classified, 0 retained and 0 unscreened. Its sentiment report explicitly treated absent social evidence as absent, not neutral. ACLS then saved its final Underweight decision and completed with coverage gaps at 2:09 p.m. The universe showed 23 completed and no failed, incomplete, running or queued stocks. Two public-source HTTP 404 failures remained visible as coverage gaps; valid empty screening does not erase those failures. A valid empty source is zero posts, not proof that 100 posts exist or that sentiment is neutral.

## Source

- tradingagents/dataflows/vendors/stocktwits.py, fetch_stocktwits_messages.
- tradingagents/integrations/laya.py and tradingagents/web/service.py, existing screening persistence and completion paths.
- Actual internal-browser ACLS Activity, social screening and sentiment report, 26 October 2026.
- Working tree over 580f1c8; Terra source review, 26 October 2026.
