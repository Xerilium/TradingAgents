# Social sentiment UI UAT

2026-10-15. Visible shared in-app browser, isolated synthetic fixture on
127.0.0.1:18766, current production static assets. This is rendering evidence,
not live model or feed verification. No broker connection or order submission.

- Opened research: AAPL partial and META unavailable correctly distinguished.
- All report sections initially collapsed.
- Clicked AAPL Laya social sentiment: source counts show bullish1, bearish1,
  neutral0, unclear1, off-topic1; Reddit unscreened2. Individual text,
  provenance, probabilities and hashes render as values, not object strings.
- UI explicitly states Laya classifies individual posts and does not approve
  trades; unclear and unscreened are distinct from neutral.
- Expanded panel measured582px client height and3864px scroll height with
  overflow auto. Run activity remained at y990 in1244px viewport.
- Clicked META: correct stock heading, unavailable label and collapsed social
  section. Opened it: retained unscreened posts and unavailable source visible.
- Historical Laya research check remains a separate collapsed section on AAPL.

Screenshot: `.impeccable/review/social-sentiment-fixture-uat.png`.

Harness issue: port18765 served an older META-only fixture. Read-only HTTP
inspection confirmed no social_sentiment fields, so that attempt was rejected.
New fixture uses exclusive Windows bind and18766 to prevent silent collisions.
No live research journal was changed. Live integrated verification remains open.
# Live desk verification, 2026-10-15 evening

## Corrected stance replay UAT

`tests/social_stance_replay_browser_fixture.py` served only local replay data on port 18767. The three actual saved problematic responses were passed through the corrected production classifier with a fake Gateway. Browser tab 10 showed 0 bullish, 0 bearish, 0 neutral and 3 unclear; each post retained its original raw prediction and `reconsider` stance grade. No new inference occurred. Screenshot: `.impeccable/review/social-stance-replay-uat.png`.

Expanded content height was 2804 pixels inside a 370-pixel `overflow:auto` report panel. Run activity's document position stayed 781.1875 pixels before/after expansion; apparent viewport movement was browser focus scrolling (45 pixels), not page reflow. Original journal data remained unchanged. This verifies the corrected admission and rendering on actual saved responses, not a claim of perfect model accuracy.

Run `56938b20-afd1-4696-9a0a-a13d48e460d0` completed META in about 280 seconds, with all nine research reports and an Overweight rating. Browser tab 5 showed 1/1 finished and the final decision. The report included the captured IEX last trade and quote timestamps, distinguished historical reference from executable quote, and prohibited immediate execution. Laya social evidence rendered per-post text, probabilities, hashes and coverage. StockTwits had 20 classified posts; Reddit was partial. Reports stayed collapsed until explicitly opened and run activity remained outside the scrolling report region.

One click on Build paper proposals produced a new META blocked proposal because the executable quote was stale; no Laya approval prerequisite appeared on that new proposal. Older immutable proposals still show their historical Laya blocker. Broker blotter remained empty. No submit or cancel order action was performed. Screenshots: `.impeccable/review/social-live-meta-completed.png` and `social-live-meta-proposal-blocked.png`.

This is NOT final acceptance: the live evidence exposed stance answers with `reconsider` contracts being counted as directional votes. T-1.10 returned to SWE for contract-aware admission. The original run is preserved, not rewritten. Independent review also found undefined standard-allocation advice inconsistent with the deterministic desk sizing policy; tracked as T-1.11. The latest timeout-message correction was not yet loaded in this run.

## Final corrected runtime and proposal UAT

Source `0287be2`, run `3f948cc2-5589-41fb-b691-33695ac18e8a`, completed October 15 evening: the shared browser shows META Overweight, 1/1 finished and nine reports. The decision assigns sizing to configured policy, labels the closed-market price as a reference, and requires separate execution checks and manual submission. StockTwits shows 14 unclear retained classifications and one off-topic; Reddit's 13 posts are explicitly deferred by the screening time budget. Independent per-row audit is in `FINAL_PRODUCT_ACCEPTANCE.md`.

Final proposal UAT shows a new META row at 7:28:05 PM blocked by executable-quote freshness. The old Laya-blocked row is explicitly historical. The journal audit confirms six other new rows blocked by missing current research. The broker blotter shows no orders. Screenshot: `.impeccable/review/social-final-proposals.png`. No submit/cancel action occurred.

The offline policy-preview fixture (`tests/policy_preview_browser_fixture.py`, port 18768) showed synthetic AAPL 10 shares at $100, $1,000 notional, policy-owned sizing and explicit manual approval. Review associated research opened the exact fixture run. Submit was not clicked. Fixture server and tab were closed. Screenshot: `.impeccable/review/policy-order-preview-uat.png`.

T-1.10 and T-1.11 passed independent red review and final functional UAT. Duplicate report labels remain isolated to display-only T-1.12; no additional model call is needed for that correction.

## T-1.12 final display verification

Reloaded the actual running desk once and explicitly opened the completed run's portfolio decision. Its display now has exactly one each of Rating, Executive Summary, Investment Thesis, Price Target and Time Horizon. DOM inspection confirms the raw source still contains the original repeated prefix. The report region remains 582 pixels tall with 1,946 pixels of internally scrolling content; the screenshot shows run activity below it. Screenshot: `.impeccable/review/social-final-clean-research.png`. No research rerun, server restart, broker call or journal rewrite was needed.
