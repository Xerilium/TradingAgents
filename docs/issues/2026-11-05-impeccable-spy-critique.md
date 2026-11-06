# Impeccable: SPY onboarding and layout critique

Status: onboarding and dual-agent critique complete. Five open design findings form the next improvement backlog. No application UI change is part of this iteration.

## Scope and observed baseline

The human asked for proper Impeccable onboarding and a direct critique of the current SPY layout, with findings driving subsequent loops. Target: tradingagents/web/static/app.js, rendered at http://127.0.0.1:8099/#spy in the existing development desk. Actual viewport1920×1080; Browser screenshot800×450. No smaller-layout work.

Baseline source6dfccd4; application blob0b542c5afed80b74e2cf888e6a343d2d55246481. The initial read-only view showed an empty reconciled paper account, no saved fund plan and automatic trading off. These are dated observations, not defaults or proof of populated/active/error/execution states. Raw primary image: .local-workspace/dogfood-20261105/spy-critique-entry-2054-1080p.jpg.

Unrelated working changes at entry: README.md, docs/dogfood-loop.md and deletion of docs/issues/dogfood-loop-ledger.md. They are preserved and excluded from this task's commits. Current working loop brief and current human instruction direct this onboarding/critique iteration; no older cadence is restored.

## Onboarding correction

Read-only audit wf_549bca14-200 confirmed that the context loader read PRODUCT.md but returned no surface brief. The old freeform paper-desk brief was not registered with the installed surface resolver and described a general watchlist-first, narrow-screen workstation.

Commit8474ad3 registers .impeccable/surfaces/tradingagents-web-static-app-js.md with the installed surface-brief writer. The read command now returns the correct primary/related targets and Operate scope. PRODUCT's last principle is SPY-first. DESIGN and its existing sidecar now identify the actual first workspace and supported viewport, retaining the incumbent visual tokens and recording current composition without approving it. This was a factual context correction, not a new visual-world choice or an invented concept seed. No repeat of the primary session's context setup.

## Assessment method

Two isolated fresh agents perform A (unanchored design review) and B (detector plus factual browser evidence). Each owns a fresh Browser tab at1920×1080 and reads the installed critique playbook. Assessment outputs remain separate until both finish. No user questions: the human supplied scope and priority, and redundant prompt widgets are banned.

No application edits, plan values/saves, Preview generation, research/model/simulation jobs, broker approvals/submissions/cancel/replace, authority changes, credentials/private runtime configuration, tests/mocks or production actions. No new app/overlay server is started; any visualization limitation will be reported rather than called a success.

## Combined critique and next batch

Method: dual-agent A a84c8307b65ff8bf1 and B ad465cf511bb81803, workflow wf_dee56a16-bdf. Each used a fresh browser tab at1920×1080 and returned before synthesis. The provisional heuristic score is21/40, not release or visual-design acceptance.

| ID | Priority | Open finding | Next batch |
| --- | --- | --- | --- |
| S1 | P1 | No clear daily answer: account, reserve, budget and readiness are fragments | Task-led resting overview |
| S2 | P1 | No saved spending plan is insufficiently distinguished from the rules-based budget | Plain-English reserve/budget interpretation; math unchanged |
| S3 | P1 | Standing automatic authority competes with the manual preview/submit path | Separate explicit groups; preserve all authority guards |
| S4 | P2 | Source timing and reconciliation links are abstract | Display already-available dates or explicitly unavailable state; no invented/fetched data |
| S5 | P2 | A large panel remains mostly empty while important meaning is compressed | Natural-height grouping and stronger information hierarchy |

### Next coherent implementation item

Use Impeccable layout/clarify/distill, followed by polish, to reorganize the resting SPY overview as one batch. Address S1–S3 and S5 together; expose only existing date/readiness information for S4. Do not add a new backend, invented metrics, chart filler or a second engine. Preserve all workspaces, exact financial calculations, native focus/disclosures, saves/revisions and approval/submission/automatic-authority semantics.

Acceptance: at actual1920×1080 or larger, the account/reserve/budget situation and next useful action are clear without opening the editor; no-plan versus rules-based sizing is explicit; manual review and standing authority are distinguishable; source dates are qualified; and meaningful blockers remain visible. Verify the changed real paths without repeating previous passing cycles or creating trades, tests or mock states. Record what was exercised and what remains source-only.

### Evidence qualification

A opened the fund-plan editor. The budget-disclosure and keyboard checks were not completed and are not passes. The CLI detector returned one advisory for a chart-annotation color (#4dabf7 at app.js:2395), outside the observed SPY surface; do not divert the next SPY batch to it. No user-visible overlay was created under the no-new-server/page-mutation constraint; real screenshots and computed styles were the fallback. No measured contrast failure or full accessibility pass is claimed.

Primary checked the supplied images and excluded A's unsupported claim of a visible global order-recovery warning. The corrected error-recovery rationale is source-limited budget/conflict/expiry feedback, not an observed error-state pass. Attempts to resume the completed workflow agent were unavailable; no result was invented. Existing screenshots and actual source were sufficient to bound the conclusion.

The full report is archived by the installed critique-storage helper: [scored critique](../../.impeccable/critique/2026-11-06T05-01-55Z__tradingagents-web-static-app-js.md). It records 21/40, zero P0 and three P1 findings, and an exact SHA-256 target fingerprint. This is the first run for this target; no trend is claimed. Final independent evidence review wf_e49ed39f-607 found no concrete artifact defect. It checked the report, issue and detector result, not live UI or screenshots; primary retains the observed evidence and its limits. Source review and rendered empty-state evidence do not prove the full SPY workflow or SPY return parity.


## Delivery decision

Primary accepts this onboarding-and-critique item as complete, not the visual design or full SPY journey. S1–S5 remain open for subsequent loops. Onboarding was committed in8474ad3; this delivery preserves the full fingerprinted critique and actionable backlog locally on nautilus. There are zero application/backend/test changes in this iteration. The generated empty-heuristic metadata was normalized to an explicit empty YAML string after the static whitespace check. No runtime checks were repeated.

Reusable onboarding lesson: memory://knowledge/projects/tradingagents/tradingagents-impeccable-onboarding-requires-a-resolved-current-surface-brief. Unrelated README and loop-brief changes and the ledger deletion remain untouched and excluded from these commits.
