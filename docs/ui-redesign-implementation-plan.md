# Blueprint implementation and acceptance plan

Status: Proposed for review. Implementation has not started under this plan.

**Fixed scope**

Freeze [the blueprint](ui-redesign-blueprint.md) at commit `3770bbe`: all 10 workspaces, US-01–US-25, E-01–E-15, and its cross-cutting contracts and exclusions. No backend changes, new APIs, unrelated refactoring, restored documents, or policy edits.

Maintain a [[traceability]] table in the existing delivery record: requirement → implementation → evidence → verdict. Audit in both directions: every requirement is covered; every change serves a requirement. Any deviation blocks the affected work. Agents cannot waive requirements or reinterpret omissions as completion.

**Team and implementation sequence**

Work in the primary checkout. Maximum **primary + one worker** active.

- **Primary:** owns `app.js`, shared shell/state, integration, all Git operations, and final product judgment.
- **Rotating worker:** owns explicitly assigned support modules and styles. Ownership transfers only at a recorded handoff; never simultaneous edits to one file.
- Workers perform no independent builds, tests, launches, or research. No worker branch merges.
- Commit reviewed implementation batches locally, with exact file staging and no abandoned untracked work.

Implement in this order:

1. **Foundation:** selection versus batch state, pinned ticket identity, focus-preserving rendering, accessible tabs, guarded shortcuts, shell and responsive behavior. Keep legacy layout helpers until their replacements exist.
2. **Orders and ticket:** establish the shared ticket before other pages consume it; preserve separate preparation, approval and submission, every blocker, and operation-specific recovery.
3. **Research and Workflows:** batch selection, six statuses, report presentation, distinct Laya results, activity receipts, workflow navigation.
4. **Dashboard, Markets and Portfolio:** shared instrument context, evidence/options access, positions, proposed portfolio and qualified performance metrics.
5. **Strategy Lab, Journal, Alerts and Settings:** complete the remaining blueprint requirements and replace their legacy layout manipulation.

No public API or backend schema changes. Shared frontend helpers reuse existing contracts.

**Resource budget and validation**

Before implementation, confirm development prerequisites, real input availability, existing release signing access and rollback package. Use isolated development settings; preserve production data and credentials.

Batch implementation before **one integrated validation cycle**, with **one consolidated correction cycle** available. One designated worker owns expensive execution; builds and live jobs run serially.

The live batch is:

- One research run covering **all 24 currently selected stocks**.
- One portfolio synthesis using eligible results.
- One five-post local Laya batch.
- One saved-plan simulation.
- One bounded walk-forward experiment: two candidates, two folds, one scenario, at most ten native runs; confirm the existing preview fits before execution.

Reuse results throughout. No automatic second 24-stock run, automated test suite, mocks, benchmarks, or per-page compilation.

Run consolidated syntax, reference and whitespace checks. Then use the visible browser across all ten workspaces, covering ticket pinning, refresh/focus preservation, keyboard/editor behavior, empty/error states, metric qualifications, desktop layouts and specified responsive fallbacks. Browser zoom does not count as observed Windows DPI testing.

**Audit and delivery**

A fresh read-only reviewer replaces the worker and audits the complete candidate against the frozen blueprint, including omissions and unrelated additions. Record revision, findings and evidence; the primary personally signs off.

Evidence distinguishes **observed**, **source-reviewed**, **failed**, and **unverified**. Broker actions remain unauthorized. Missing real-state coverage stays unverified and blocks any claim of complete acceptance.

After validation, commit the clean candidate, perform one app-only release build and controlled installed update. Verify startup/shutdown, loaded revision, settings and ticker selection against the captured production baseline. Preserve private runtimes; do not repeat research during installed smoke checks. Use the consolidated correction allowance if needed, or restore the previous application package without resetting data.

Keep commits local. Remote publication requires a separate request.
