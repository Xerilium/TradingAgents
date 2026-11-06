# Dogfood: SPY submit-error recovery

Status: complete for the scoped source correction, independently reviewed and normal-state checked at 1920 × 1080. Submit-error branches remain source-only, not live broker-error acceptance. No paper trades are authorized.

## Defect and bounded scope

Baseline `5227965` on `nautilus`. Read the current standing brief and active pause correction first. Completed onboarding, critique and prior UI checkpoints were not repeated. Used the existing development desk on 8099, not another server.

Completed investigation `wf_1f4d5040-7a2` independently found and adversarially verified two facets of one defect: failed SPY submits retained the client token after a rejection or lost response, so the UI could still look ready and enable Submit until a later update. Server consumed-token and active-run guards remained; duplicate execution was not established. The investigation was not rerun.

Scope: revoke failed-submit client authority, retain truthful account-attributed error/recovery evidence and the still-current full plan, and preserve existing financial and broker controls. No backend feature, retry engine, calculation, persisted ledger or authority change.

## Implementation and independent scrutiny

Installed Impeccable Operate/harden/clarify and craft-floor guidance informed implementation; primary context had already run once. This is error-state correction, not another redesign or critique. Existing qualified professional-interface research informs evidence/recovery grouping, not local transaction semantics.

- Every current-generation failed submit clears the retained preview's submit token. Trades, filter, sizing and expiry are not rewritten.
- A session-only last failed-submit result stores request-start account identity, generation, exact error and response category independently of preview authority. Fund-plan save and account/connection/revision invalidation cannot erase it. Explicit new Preview clears it; another workspace generation does not display it.
- **Service returned an error** identifies an HTTP error response. **Check submission outcome** identifies an unconfirmed response. Neither proves failure: the warning says the rebalance may already be queued and directs checking that account's latest rebalance, orders and fills before another preview.
- The failed-submit warning and current-action message render separately, so a later enable/pause error is not hidden. Exact error text is escaped. Higher-priority unavailable, in-progress, account-condition and blocked-run status/guidance remain intact. Invalid plan bindings still hide the plan and disable submission; retaining an error restores no authority.

Corrected findings are recorded rather than presented as first-pass success:

| Review | Reviewed app blob | Findings and disposition |
| --- | --- | --- |
| `wf_e242cfb3-f34` | `d6f77923423f0536bf5943377868b3d16cc683cf` | HTTP 400 can follow queued persistence during response construction; 429 is header-derived; recovery displaced operational guidance. Removed rejection inference and restored precedence. |
| `wf_23b1ab74-ef3` | `f1477d295a7195f0d73eb1218fd2e3433810dd10` | Invalid plan context hid the error. Decoupled error display and attributed the submitted account. |
| `wf_b583813d-ef9` | `4f73cf5c89164cce4eabefdfa7a981d7ccc497f0` | Fund-plan save cleared preview-bound outcome state. Introduced the separate session-only failed-submit result. |
| `wf_64d89842-9c4` | `2ec9a4e0e277b593a038bede6011f6633e6b90ed` | Older receipt hid a later enable/pause failure. Rendered the two messages separately. |
| `wf_334c08cf-0e7` | **`06d1bb8db6dcb180301e984ae9b1f6c60ac16800`** | **No material findings.** Reviewed token revocation, account/generation attribution, escaping, invalidation/save paths, later action messages, status priority, API/service contracts and both affected reference diffs. Source-only review. |

Primary inspected the exact diff, submit-before-response service sequence, server error map and potentially throwing retained option-draft validation. HTTP status alone cannot establish a definite pre-commit rejection with this contract. Conservative copy is used instead of broadening the API or pretending that distinction exists.

## Affected real-browser evidence

Normal `http://127.0.0.1:8099/`; actual **1920 × 1080**, 800 × 450 Browser images. Initial loading screens were not counted as passes.

| Check | Actual observation and limit |
| --- | --- |
| Initial clear state | Served blob `d6f77923423f0536bf5943377868b3d16cc683cf`; Preview needed, Submit disabled, automatic trading off; no horizontal overflow or console error. |
| One actual dry-run Preview | On that initial implementation: **503 planned trades**, **Preview ready for review**, full table/count and no false error warning. Submit enabled but never activated. Returned weights date **2026-11-05**, price-check time **6 November 2026, 07:28:03 PST**. Automatic trading off. Qualified pre-correction healthy-path evidence, not final failure acceptance. |
| Final corrected source | Fresh normal document served **`06d1bb8db6dcb180301e984ae9b1f6c60ac16800`**, matching reviewed source. Account observed **07:37:16 PST**: Preview needed, Submit disabled, automatic off, reconciled account, zero positions/open orders. No false warning, horizontal overflow or console error. No additional preview merely to repeat a passing cycle. |
| Failure/recovery | Rejection, post-queue response error, timeout, unreadable response, account/connection/revision changes, fund-save recovery and subsequent authority-action errors are source-reviewed only. No broker action, forced failure, fake response/state/event/clock or synthetic test. |

Source inspection read the actual served asset and used CRLF-normalized Git-blob hashing; no application data was injected. Normal document reload discards session-only previews as before. This proves neither rendered failure recovery nor broker submission, reconciliation execution, full SPY release acceptance or return parity.

Ignored raw evidence in `.local-workspace/dogfood-20261106/`:

- `spy-submit-recovery-resting-1080p.jpg` — initial clear state.
- `spy-submit-recovery-initial-healthy-preview-1080p.jpg` — qualified initial dry run.
- `spy-submit-recovery-final-clear-1080p.jpg` — final corrected-source clear state.

Primary inspected visible privacy. Normal-state images are not promoted as error-branch illustrations; useful existing guide images remain unchanged. No financial value or state was repainted.

## Delivery and decision

Updated the platform reference and affected operating reference. Before editing, the installed reference matched its full tracked HEAD baseline after CRLF-only normalization. Later copies checked known owned content for divergence and were byte-identical after synchronization.

Application delta: **16 added/5 removed JavaScript lines**; zero CSS, backend or test changes. JavaScript syntax and scoped whitespace checks passed. No automated tests, mocks, research rerun, new server, production operation, credential/private configuration read, approval, submission, cancel/replace, standing-authority or pause change. One actual dry-run preview only.

Primary decision: accept the complete bounded source fix on the independently reviewed final revision and qualified real normal-state evidence, with failure rendering/execution explicitly unproven. Commit only JavaScript, the two affected references and this issue locally on `nautilus`; no branch, push or PR. Preserve/exclude unrelated `README.md`, `docs/dogfood-loop.md` and deletion of `docs/issues/dogfood-loop-ledger.md`.

This item is complete. The next loop should select the next useful SPY-journey improvement, not repeat this implementation or its passing normal checks. Remaining broker-evidence limits do not globally pause authorized development.
