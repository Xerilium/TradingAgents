# Dogfood: make SPY portfolio the primary daily entry

Status: **complete for the scoped functional primary-entry and navigation item**,
with affected real 1920 × 1080 observations and independent source/evidence review.
This is not visual-design approval, full SPY shipping acceptance or SPY return
parity. No paper trades are authorized.

## Observation and scope

Baseline `1c396f2`, clean `nautilus`, existing development desk on 8099. At an
inspected real 1920 × 1080 viewport, the normal root URL opens Dashboard: universe,
stock chart and research dominate the first view. The sidebar has ten workspaces
and no SPY entry. SPY is accessible only through Orders → SPY Rebalance (or the
Portfolio fund-plan handoff). This conflicts with the human's SPY-first daily
index-management purpose in `PRODUCT.md` and `docs/dogfood-loop.md`.

One discrete item: add **SPY portfolio** as the first sidebar workspace and the
no-hash landing page, point the brand/home and Portfolio fund-plan handoff there,
and reuse the existing fund-plan/rebalance renderer and bindings. Preserve valid
explicit routes, all ten existing workspaces, legacy Orders → SPY Rebalance,
shared drafts/preview, disclosure/focus behavior, navigation guards and every
save/revision/eligibility/expiry/approval/submission boundary. No backend change.

## Research and approach

- Read-only source mapping `wf_ae8d8389-adb` identified shell initialization,
  render/bind dispatch, UniverseReview renderer/export, Portfolio handoff,
  brand link and Orders main-layout selector as the integration points.
- Installed Impeccable, Operate mode: primary context already loaded once in this
  session, incumbent inspected at supported size, Operate playbook and craft floor
  read before edits. Preserve the existing visual system; use familiar navigation,
  not a decorative dashboard or new backend feature.
- Reuse `refreshTicketData`, `spyRebalanceMarkup`, `orders-workspace`,
  `bindOrders` and the common guarded hash/navigation and focus-restoration paths.
  Add one root at a time; keep the legacy Orders tab intact.
- Relevant durable sources: fund-purpose/SPY-first memory and stable-summary-focus
  memory. Graph lookup of `spy-replication` had no concept; source memories were
  read directly rather than treating an empty graph lookup as absent guidance.

Primary owns writes and actual browser checks. Fresh independent source review
precedes one affected real 1080p navigation/disclosure smoke. No Preview generation,
plan save, provider/research/model/simulation job, broker approval/submission,
standing-authority change, cancellation/replacement, test/mock/build, private
configuration/credential read or production operation is included. Failed affected
local checks remain part of this development task, not a fresh approval gate.

## Evidence and delivery

Implemented first sidebar/default/home `#spy` workspace, an exported renderer
using the existing SPY root and bindings, the Portfolio editor handoff and the
main layout selector. Added existing balance readout, actual account observation
time, coverage-qualified positions and qualified reconciliation status above the
plan. One root is rendered at a time. Legacy Orders SPY remains intact.

Fresh source review `wf_2d29c879-baa` identified the missing account context in the
first navigation-only draft. After adding it, review `wf_45574a63-600` found that
an unverified account could still display a confirmed-looking reconciliation
status and an offline transition updated only the notice. Corrected the status
guard to require account verification and rerendered only the active SPY page on
an actual offline event. Other workspaces retain their original offline path.
Narrow independent verification `wf_b8b643cf-afc` found no actionable remaining
defect in those corrections. Offline/unverified cases are source-only, not live
acceptance. No state or events were fabricated to exercise them.

Reviewed final application blobs:
- app.js: `0b542c5afed80b74e2cf888e6a343d2d55246481`
- index.html: `83e49a70573ceff658ed6773d9e003fada92ce47`
- ui-orders.css: `3857d939dd7176cddd6a012db9bc178279a7600c`

Primary accepted the source batch for the affected real browser check. Syntax
and whitespace passed. Browser observations and documentation closeout follow.

[Fidelity's Trader+ Web guide](https://www.fidelity.com/learning-center/trading-investing/trading-platforms/how-to-use-trader-plus-web/),
accessed 5 November 2026, describes essential tools together on one dashboard and
Positions monitoring with adjustable panels. Adapted principle: put this product's
primary task and account context at entry. This is not a claim that Fidelity has
this SPY/fund-plan feature, nor a feature-parity or execution claim.

## Affected real browser check

Normal development URL, fresh Browser tab, inspected actual viewport **1920 ×
1080**. The initial opening/loading state was not treated as acceptance. No
query-labelled UI, alternate server, fake records, clocks or injected events.

| Path | Observation |
| --- | --- |
| Fresh root `/` | `#main[data-page=spy]`, SPY portfolio heading and first/current sidebar entry; eleven links including all original workspaces; one bound SPY root. |
| Current situation | Existing balance strip showed $100,000 equity/cash/buying power, $0 long value, 0 open orders; 0 observed positions and reconciled status, with actual account observation time. These are dated paper facts, not defaults or expected constants. |
| Supported layout | No horizontal page overflow. Preview occupied y538.25–574.25 within the1080px viewport; collapsed editor and full-budget details kept the main review compact. |
| View portfolio | Opened Portfolio → Positions. The empty observed holdings and fund-plan entry remained available. |
| Open account fund plan | Navigated to `#spy`, opened editor, kept budget closed and focused `fund-plan-editor-toggle`. Root had `data-bound=1`. |
| Normal update/focus | Snapshot08:34:26 →08:35:28; original focused node disconnected, replacement SUMMARY retained focus and editor stayed open. Native Enter closed it. |
| Explicit Dashboard | `#overview` opened the existing Dashboard. This checked route preservation, not every dashboard tool or chart result. |
| Brand/home | Ordinary click returned to settled `#spy`, SPY portfolio heading/current nav and main scroll0. An immediate same-batch sample preceded hash rendering; only the later settled observation was accepted. |
| Legacy Orders | Explicit `#orders` opened Ticket & Blotter; native SPY Rebalance tab opened the existing single bound SPY panel. Automatic trading remained off and Save disabled. |
| Manage from primary | Top-bar Manage opened Orders → Ticket & Blotter and focused `account-order-controls` even after legacy SPY selection. Orders gate remained Active; no gate action. |
| First sidebar entry | Native click returned to `#spy`, one root, main scroll0, disclosures closed; blank authored terms/inactive status unchanged, Save and Submit disabled, automatic trading off. |

No console errors were reported. No plan save, Preview generation, enable/pause,
trade, approval, submission/cancel/replace, provider/research/model/simulation job,
test/mock, app build, credential/private configuration or production operation.
Offline/unverified-account and populated holdings/preview cases were not fabricated
or live-exercised; source reviews are not live acceptance of those cases. Existing
workflow/credential discard guards were preserved in source without creating
private drafts just to stage a check. The complete SPY input/execution/outcome
journey and qualified return-parity measurement remain outside this item's acceptance.

A blank-tab resize request and a stale element reference were setup failures,
not product passes. The auto classifier refused one combined coordinate-navigation
and inspection batch before it ran. A named navigation-control attempt then had a
stale reference; a fresh screenshot and standalone native navigation click opened
the editor. No connected-app write or broker action was performed or bypassed.

## Guide image, documentation and preservation

Raw ignored evidence under `.local-workspace/dogfood-20261105/`:
- `spy-primary-entry-before-1080p.jpg` — original root Dashboard.
- `spy-primary-entry-legacy-before-1080p.jpg` — legacy Orders SPY entry.
- `spy-primary-entry-after-1080p.jpg` — accepted final primary entry.

The final capture is promoted unchanged to `docs/images/spy-portfolio.jpg`:
800 ×450 Browser-rendered JPEG from an inspected1920 ×1080 viewport, blob
`ccef138324a02d5befbaae5527b07af583df345a`, byte-identical to raw evidence,
no EXIF/XMP/IPTC segment. Primary visually inspected it: no visible account
identifier, credential, private note or unrelated desktop. Actual paper figures,
off authority state and disabled submission are not repainted. README/image notes
explain the dated scope and original viewport.

Updated platform/local guides and the operating skill for the actual primary
entry and Portfolio handoff. Three affected installed skill files were compared
against their full tracked HEAD baselines (normalizing only line endings), copied
only when matching and then verified byte-for-byte with updated source.
Unrelated installed files were untouched.

Unexpected README frontmatter/WikiLink edits appeared after the clean baseline.
They are not part of this navigation change. Coordination to the other local
session was held and expired undelivered because its permission mode differed;
no consent or ownership was inferred. The changes are preserved in the working
README and ignored snapshot/patch; only this task's three explicit README edits
are prepared for the index from HEAD. No unrelated work is overwritten or staged.

Application delta: **15 added /9 removed lines** across JavaScript, HTML and CSS;
zero backend/test changes. Static JavaScript syntax and whitespace checks passed.
Primary accepts this discrete navigation/account-context item based on reviewed
source and the observed affected paths, not broader release readiness. Final
independent documentation/privacy scrutiny and local delivery follow.

The human subsequently rejected the layout quality and explicitly assigned an
Impeccable critique to the **next loop**, asking to finish this item first. This
record accepts only scoped functional entry/navigation; it is not visual-design
approval. The next wakeup must begin that requested critique at the real supported
viewport before selecting another implementation item.

Final evidence review `wf_f73b565e-54c` found no actionable documentation or visible
privacy defect in the staged guide/evidence batch. It inspected the real image
but did not independently rerun browser or metadata checks. Primary retains those
observations and their limits. All18 local targets in the staged README resolve;
three changed source/installed skill files still match byte-for-byte. Primary
final decision: accept the scoped functional item and finish local delivery on
`nautilus`, with no push. Only unrelated concurrent README edits remain outside
the commit; no owned application/documentation change is left unstaged.
