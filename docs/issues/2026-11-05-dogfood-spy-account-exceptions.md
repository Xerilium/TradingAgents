# Dogfood: SPY account exceptions and recovery handoff

Status: complete for the scoped implementation and observed clear-state/handoff paths. Blocked states remain source-reviewed only.

## Scope and evidence

Baseline f112f77 on nautilus. Current brief read first. Preserve the completed resting layout and unrelated README/loop edits and ledger deletion. One item: expose existing account-wide conditions that block SPY submission and make the account-control handoff remain visible through normal updates. No financial/backend change or broker action.

The existing hidden recovery/ticket markup is not proof of a current incident. Actual read-only inspection showed account reasons empty and ticket label No approved order. These are different concepts. Independent contract map wf_45a7d62f-2bb confirmed that SPY server preflight rejects account-wide pause/recovery and other conditions, but the UI can retain an enabled Submit and Preview ready status after such a condition changes. That mismatch is source evidence, not an observed order or server-guard failure.

The real Manage handoff did reveal a navigation defect: focus was account-order-controls, but its top was y1572.625 while the pane ended at y1064 and scrollTop was0 after ordinary updates. The pane was not included in the existing scroll-retention selectors.

## Implementation and constraints

Extract the existing account-only reason collection unchanged from human order readiness. Both ticket readiness and SPY reuse it, without importing proposal approvals, items or a ready-order count into SPY. Existing SPY financial/preview bindings remain; a listed account condition additionally disables Submit and produces visible reasons outside disclosures. Preview is still a separate review action and never clears a block. The new Review account order controls link reuses the existing navigation-only Manage handler; it changes no pause or authority flag.

Retain the Orders review pane through the existing workspace-scroll path, keyed by its actual Orders tab. No new focus/scroll manager or timer. All original finance, server preflight, exact approval, submission, queued cancel and standing authority semantics remain.

Installed Impeccable context was already loaded once. Applied Operate harden/clarify and polish guidance, with craft floor read before UI edits. Keep existing tokens, full-width prose and native controls; no redesign. The prior official Fidelity/IBKR/thinkorswim visual research informs monitoring/action separation, not a new brokerage capability.

Only the real existing development desk on8099 at actual1920 ×1080 is used. Do not create blocked states by pausing, disconnecting, changing authority or fabricating data/events. No tests/mocks, credentials/configuration stores, production operations or new server. Source review of unobserved blocked cases remains source-only.

## Source scrutiny and affected observations

Fresh independent review wf_472d7b8e-626 found no actionable issue at app96c3d807ff0e45e65be6a559041191d6c47c8f45 and command-controls29cf7f519a5a28b1acdcef73bc92e496a66ba4a4. It checked the unchanged account predicates, independent ticket/SPY handling, bindings and navigation/scroll restoration. This is source-only review, not observed blocked-state or broker acceptance.

The initial real clear-state render showed no account reasons, no exception banner, Preview needed and disabled Submit without a preview. Ticket readiness still said No approved order. The new link was visible, the root bound once and no horizontal overflow appeared.

Native Review account order controls navigation selected Orders → Ticket & Blotter and focused account-order-controls. The pane scrolled to980; the heading was y592.625–616.922 and Pause/Resume y734.484–770.484, all inside the visible pane ending at1064. No pause control was activated. Normal replacement/retention follow-through is checked while documentation is updated.

Normal-update follow-through passed: the stored original account heading disconnected, its replacement retained focus, the pane stayed at scrollTop980 and the heading/controls remained visible. Orders stayed Active and account reasons remained empty. Fills & Fees opened with its own key and scrollTop0; returning to Ticket & Blotter restored980 and its visible account heading. No control or broker action was activated.

The selected guide image is the real clear-state SPY view with the new link, not a staged blocker. Actual viewport1920 ×1080, Browser image800 ×450, blob c3387d93be9522ffc16be6736426f866dc5ddc95. Primary visually checked it for account IDs, credentials, private notes and unrelated desktop content; none are visible. JPEG inspection found no EXIF/XMP/IPTC segment. It matches ignored spy-account-exceptions-clear-1080p.jpg byte-for-byte. The handoff screenshot remains ignored evidence; no private order/account image is promoted.

One actual dry-run Preview checked the changed no-block eligibility path. Account reasons were empty while the separate ticket label remained No approved order. SPY showed Preview ready for review with Submit enabled by its existing token gate. The response contained503 planned trades, weights dated2026-11-04 and price check5November2026 at21:40:45PST. This verifies that human-ticket approval was not accidentally imported as an account block. Submit was not activated. Automatic trading remained off and the new-order gate Active. No console errors or horizontal overflow were reported. Unchanged filtering and the prior full layout/disclosure cycle were not repeated.

Blocked, paused, disconnected, broker-blocked, browse-only and recovery transitions were not induced. Their presentation/disable behavior is source-reviewed only. No clear-state result proves the absence of working commitments, a fresh exact preflight, broker admission/execution, full SPY release readiness or total-return parity. The server remains authoritative. The existing legacy Orders SPY entry shares the reviewed renderer and handlers; this batch did not repeat its previously passing populated-preview cycle.

No order approval/submission/cancel/replace, pause/resume, authority change, fund save, research/model/simulation run, automated test/mock, production operation, private configuration/credential read, package build or server restart occurred. Only the actual dry-run preview was generated.

Final source: app96c3d807ff0e45e65be6a559041191d6c47c8f45; command-controls29cf7f519a5a28b1acdcef73bc92e496a66ba4a4. Application delta15 added/7 removed lines, no financial/backend/test changes. Syntax, whitespace and scoped layout detector passed. Product/local guide and operating reference describe exact labels and boundaries. The installed operating reference is compared against HEAD before copying and checked byte-for-byte afterward.

Primary decision: accept this complete scoped implementation with observed clear-state and handoff acceptance, and explicit source-only blocked-state limits. Fresh source review found no actionable issue and the real focus/visibility failure is corrected through normal node replacement and separate tab scroll keys. Commit locally on nautilus without push, preserving unrelated README/loop changes and ledger deletion.

Reusable evidence lesson: memory://knowledge/projects/tradingagents/tradingagents-hidden-status-text-is-not-current-broker-block-evidence. Hidden legacy markup is not a current broker-block observation.
