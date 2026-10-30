# Research failure terminal-state hardening

Status: Reproduction required — candidate fix shelved and not installed
Owner: Codex subagent `hardening_terminal_state`
Coordinator: Codex parent
Reported: 30 October 2026

## Problem to establish

Check research failure paths for contradictory state: a terminal failed or
cancelled run whose unstarted/result rows still say queued or running. In
particular, worker submission failure sets the run to failed before calling
`_finish_research`; establish what happens to its result rows and consumers.

## Owned scope

- Research lifecycle methods in `tradingagents/web/service.py`
- Relevant research serialization in `tradingagents/web/store.py`, only if needed
- This issue file

## Acceptance

- Establish a concrete trigger and trace the resulting persisted/API state.
- Terminal failed/cancelled runs must not advertise pending result work.
- Preserve completed results, original timestamps, latest-only retention,
  cancellation ownership and the no-fabricated-rating rule.
- Prefer one existing lifecycle boundary over duplicated recovery logic.
- Make only the smallest supported correction; record limits explicitly.
- Obtain fresh independent review before coordinator sign-off.

## Constraints

No new automated/mocked tests, research reruns, broker actions, dependency
installs or production changes in the investigation. Propose real-component
verification before running it. Do not stage or commit concurrently with the
other worker; the coordinator owns delivery.

## Candidate failure path and consumer trace

This is a [[research lifecycle]] concern identified by source analysis, not a
reproduced defect or production incident. The inspected base is `nautilus` at
`000e3e6`. The user requires a real reproduction before any fix proceeds.

1. `_start_run` creates queued results and saves the new run before submitting
   its worker (`service.py:2277`, `2302–2304`, `2313`). A failed submission
   sets the run to failed, calls `_finish_research`, and rethrows
   (`2320–2327`). Before this patch, finalization did not update the results.
   A concrete supported trigger is submission after the executor has shut
   down: [Python's executor contract](https://docs.python.org/3.11/library/concurrent.futures.html#concurrent.futures.Executor.shutdown)
   specifies `RuntimeError`. The service calls that shutdown in `close`
   (`service.py:3092`). No shutdown race was induced or observed here.
2. `_run_with_evidence` handles errors from its stock worker pool internally
   (`service.py:2653–2680`). An exception from pool construction, submission,
   or a completed future updates only the run before finalization. Because
   that exception is caught there, `_run` does not execute its former
   pending-result cleanup. Pending rows can therefore survive this path too.
3. `DeskStore.save_research` writes those rows into `latest_research`
   (`store.py:148–153`). `prune_research` retains the newest result per ticker,
   including failures (`124–146`); it does not normalize statuses. A new
   failed cycle can therefore replace the ticker's former completed result
   with a result still labeled queued.
4. Compact state computes counts from the stored row status and exposes the
   same status through `result_summary` and `research[symbol]`
   (`store.py:272–278`, `304–367`). Run/result detail returns copies of the
   same records (`service.py:1934–1947`). These feed `/api/state?compact=1`
   and `/api/runs/{id}` / `/api/runs/{id}/results/{symbol}`
   (`server.py:138–144`, `268–279`). The contradiction reaches the API;
   it is not merely an internal counter.
5. Existing startup recovery only reconciles result statuses when the parent
   run itself is queued, running, or cancelling (`store.py:98–103`). A saved
   failed run with queued rows is not repaired by that branch on restart.

## Shelved candidate change

Move `_run`'s existing pending-result cleanup into `_finish_research`
(`service.py:2341–2352`, `2375–2390`). Every caller already reaches this
boundary while holding the store lock. When the run is failed or cancelled,
queued/running/cancelling rows now take that terminal status before the save.
The error uses the existing row error first, then the run error, then
`Analysis stopped before completion.`

- Completed, failed, and cancelled rows are untouched, including their
  reports, rating, revision, errors, and original timestamps.
- Existing run timestamp behavior, evidence finalization, normal
  undispatched-result handling, and [[latest research]] retention are unchanged.
- [[Cancellation]] controller ownership and shutdown behavior are unchanged.
- The stock pool still exits its context before this terminal cleanup, so
  this change does not mark in-flight stock work terminal early.
- No serializer, UI, provider, broker, or unrelated workflow change is needed.

Source delta: 5 lines added, 3 removed; net 2 lines. Tests added: 0.

Relevant historical constraints were checked against
[the concurrency decision](memory://thinking/sequential/2026/10/23/session-1792790782501-76842)
and [the latest-research retention investigation](memory://thinking/sequential/2026/10/27/session-1793130330425-58918),
then verified against the current source.

## Validation and limits

- Passed Python AST parsing of the changed `service.py`; this does not import
  or execute the application.
- Passed `git diff --check -- tradingagents/web/service.py`.
- Reviewed both finalization call paths and the persistence/API consumers.
- Coordinator-observed read-only installed API baseline: five retained runs
  have no queued/running/cancelling rows. The newest run
  `dc6eba8a-c55b-47f4-9384-1e8f7b24abf0` has nine completed current results;
  this turn did not start it. Older failed runs retain only their still-current
  completed rows after latest-per-ticker pruning. Their historical run status
  must not be inferred from the remaining rows. This baseline does not
  reproduce the defect or validate the uninstalled source patch.
- No runtime behavior, application UI, shutdown race, research run, or
  installed-package behavior was exercised by this worker. No tests, mocks, stubs, synthetic
  inputs, builds, or broker actions were run. Production data was not opened
  or modified. The coordinator owns staging, commit, and delivery.
- This forward lifecycle fix does not backfill contradictory records already
  persisted by older code; no data migration is included.

If later authorized, observe a real user-initiated development research
completion or cancellation and compare that run's terminal state with compact
state and run/result detail. Require zero pending rows only once the run is
terminal, and preserve any already-completed results. That check would verify
normal real-component finalization, not reproduce executor rejection. The
submission-failure branch remains source-reviewed unless a real failure is
observed; no fake executor or repeated research is proposed.

## Independent review

Fresh reviewer `hardening_fresh_review` approved the scoped correction on
30 October 2026. Reviewed patch SHA-256:
`d5d2d684691ee45ceeed5bb3e42736b8aef49f92522f26b1932d8625f9cd0fb5`.
The reviewer independently checked the locked callers, executor exit ordering,
terminal result preservation, persistence/API path and cancellation boundary.
Source blob: `073a9563ca9398452630a5cdeb939910c6d55a8f`.
No runtime reproduction or installation was part of that review.

## Reproduction gate — 30 October 2026

The coordinator applied and packaged the candidate before establishing a
runtime reproduction. The user corrected this: a repro is required before
starting a fix. The candidate is retained in local commit `a86351f` and its
reviewed patch for inspection, but the active source has been returned to the
pre-fix implementation. Nothing from this hardening batch was installed.

The package under `packaging/build/hardening-terminal-20261030T213426Z`
is not approved for installation. Source review approval is not reproduction
or runtime acceptance. Next work must use unchanged code and real components
in isolation, without a fake service/executor or changes to production data.
If the scenario cannot be reproduced, keep it unconfirmed and do not ship the
candidate as a proven fix.
