# Research failure terminal-state hardening

Status: Assigned — investigation
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
