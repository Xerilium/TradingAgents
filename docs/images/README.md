# Product-guide images

These are real development-desk captures selected from accepted affected-workflow
evidence. They are dated examples, not current account facts. No account identifier,
credential, private note or unrelated desktop content is visible in the selected
images. Prices, plan quantities and visible paper-trading status are retained;
no values or states were repainted.

| Image | Captured | Source revision / viewport | What it demonstrates |
| --- | --- | --- | --- |
| `research-review.jpg` | 5 November 2026 | `753df7a`; 1024 × 768 browser viewport, 800 × 600 image | AAPL inspection, search separate from batch selection, result-status filters and coverage gaps |
| `spy-rebalance-preview.jpg` | 5 November 2026 | `38b94f1`; 1024 × 768 browser viewport, 800 × 600 image | A real 503-trade preview with a view-only AAPL filter showing one row |
| `spy-fund-plan.png` | 5 November 2026 | `7df8b5b`, app blob `5e9b27533a4498f94af9b65629556c4c5b8114c3`; real 1920 × 1080 viewport, 706 × 153 detail image | Compact reserve/SPY budget, secondary editing/details and native keyboard focus |
| `spy-portfolio.jpg` | 5 November 2026 | Source batch based on `1c396f2`, app blob `0b542c5afed80b74e2cf888e6a343d2d55246481`; real 1920 × 1080 viewport, 800 × 450 Browser capture | Primary SPY entry, observed balances/reconciliation and existing fund-plan/rebalance controls |

`spy-portfolio.jpg` is an unchanged full Browser screenshot from the accepted
primary-entry check, not a cropped smaller layout. Its actual page viewport was
1920 × 1080; the tool rendered the capture at 800 × 450. Both fund disclosures are
closed, automatic trading is off and Submit is disabled. The selected JPEG matches
the ignored raw file byte-for-byte and has no EXIF/XMP/IPTC segment. Its Git blob is
`ccef138324a02d5befbaae5527b07af583df345a`. No visible identifier or private note
was found in the selected rendered image. This is navigation/account-context
evidence, not proof of a complete rebalance, broker acceptance or return parity.

The first two images predate the user's 1080p-only direction. They remain historical
workflow examples, not acceptance evidence for smaller layouts going forward.
The new detail image was captured with the Browser tool's region capture from the
rendered 800 × 450 pane image: region (90, 42)–(796, 195). The actual page viewport
remained 1920 × 1080. The crop removes surrounding navigation and blank space, not
information inside the fund-plan section; it is not a smaller responsive layout.

`spy-rebalance-preview.jpg` shows the pre-existing **Automatic trading on** state.
`spy-fund-plan.png` shows the later **Automatic trading off** state. Neither capture
enabled, disabled, approved, submitted or executed anything. The preview image is
not broker acceptance; the fund-plan image is not a performance or return-parity claim.

Original ignored evidence under `.local-workspace/dogfood-20261105/`:

- `research-status-axes-after.jpg`
- `spy-preview-filter-after-aapl.jpg`
- `spy-fund-plan-focus-corrected-after-1080p.jpg` — full rendered pane image
- `spy-fund-plan-focus-corrected-detail-1080p.png` — exact promoted region capture
- `spy-primary-entry-after-1080p.jpg` — exact promoted primary-entry capture

Acceptance records:

- [Research status and coverage](../issues/2026-11-05-dogfood-research-status-axes.md)
- [SPY preview lookup](../issues/2026-11-05-dogfood-spy-preview-filter.md)
- [Preview expiry](../issues/2026-11-05-dogfood-spy-preview-expiry.md)
- [Fund-plan presentation and corrected focus](../issues/2026-11-05-dogfood-spy-fund-plan-disclosure.md)
- [Primary SPY entry and navigation](../issues/2026-11-05-dogfood-spy-primary-workspace.md)

When a pictured workflow changes, replace its guide image after affected
verification and update this note. Preserve raw evidence separately; do not create
research, models, simulations or broker actions just to stage a screenshot.
