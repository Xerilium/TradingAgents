# T-1.10 social UI implementation

HSM: `session-1792115421044-18322`.

The UI no longer labels stocks Laya cleared or Laya review required, and those filters are removed. Social screening status is separate from research completion. Persisted source evidence displays bullish, bearish, neutral, unclear, off-topic and unscreened counts, original post/excerpt text, provenance, hash and recorded probabilities. Missing counts say Not recorded. Unavailable screening is never converted to neutral.

Saved research checks and their exact input audits remain accessible under Historical Laya labels, explicitly retired with no proposal authority. Existing user-controlled disclosures, bounded report scroll and activity placement are unchanged.

Compact snapshots keep source summaries and exclude post bodies; detailed results retain the complete evidence. Backend and UI workers agreed the `social_sentiment.sources` schema directly.

## Verification

- UI regression tests before implementation: 19 passed, 3 failed, proving retired-label/social-evidence behavior missing.
- After implementation: 22 UI tests passed via 30-second hard timeout.
- Compact projection test: 1 passed via 45-second hard timeout. Confirms source counts retained, post bodies excluded only from compact output, source evidence not mutated.
- No inference, broker calls, production restart or order submissions.

## Browser handoff

`python -m tests.social_sentiment_browser_fixture` serves an isolated fixture at `http://127.0.0.1:18766/#research` (override with `--port`). Windows binding is exclusive to fail on collisions. It uses production static assets with explicitly synthetic counts/posts and unavailable Reddit screening. It has not been started by this worker. Open Laya social sentiment, inspect source counts and posts, inspect Historical Laya research check, switch stocks, and confirm the activity panel stays placed and disclosures remain user-controlled. Fixture is not proof of a live model or source call; coordinator must separately verify those receipts.

The initial coordinator browser check at18765 showed the wrong META-only fixture. A bounded HTTP read confirmed the actual served body was114957bytes and contained zero social_sentiment fields plus the old laya_input META seed. This was a serving mismatch, not evidence of successful rendering. The new default18766 removes that collision. Offline Node execution independently verifies the social fixture BOOT initializes both symbols and social evidence; visual verification still required.

Visual UAT and integrated backend validation remain pending with the coordinator.
