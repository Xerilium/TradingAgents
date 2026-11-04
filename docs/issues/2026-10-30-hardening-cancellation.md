# Research cancellation and tool-handoff hardening

Status: Reviewed — no source change; independent source review approved
Owner: Codex subagent `hardening_cancellation`
Coordinator: Codex parent
Reported: 30 October 2026

## Problem to establish

The recent Codex probe and parallel-call failures showed that cancellation,
turn completion and cleanup need precise boundaries. Review the current
implementation for a concrete remaining defect; do not reopen the already
verified fixes merely to add defensive code.

## Owned scope

- `tradingagents/llm_clients/cancellation.py`
- `tradingagents/llm_clients/chatgpt_client.py`
- This issue file

## Acceptance

- Explain any failure from actual source and evidence, including its trigger.
- Cancelled research must not accept late model results or leave an owned
  helper/retry running; teardown and the tool-handoff wait remain bounded.
- Preserve the MCP isolation and full-list tool-call contract.
- Make only an evidenced, targeted correction. A no-change review is valid.
- Record static verification and any unperformed live acceptance honestly.
- Obtain fresh independent review before coordinator sign-off.

## Constraints

No new automated/mocked tests, research reruns, broker actions, dependency
installs or production changes in the investigation. Propose real-component
verification before running it. Do not stage or commit concurrently with the
other worker; the coordinator owns delivery.

## Review outcome — 30 October 2026

Reviewed the assigned files at `000e3e6`, including the already accepted
`5b8fc417` function-handoff correction. No concrete remaining defect was
established within this scope. No source change is proposed. The coordinator
will obtain fresh independent review alongside the research-lifecycle patch.

### Source evidence

- `cancellation.py:44–74`: admission and cancellation share a lock. Cancellation
  sets the flag before cancelling tracked futures; the result path checks that
  flag before returning a model result. Cancelled futures become
  `InterruptedError` rather than successful responses.
- `chatgpt_client.py:350–385`: each retry checks the same request cancellation
  event, and backoff uses its interruptible wait. `_agenerate` retains and
  shields its worker, signals cancellation, and awaits that worker's cleanup
  before propagating cancellation.
- `chatgpt_client.py:89–137,161–177,406–411,523–526`: startup catalog polling
  and receive polling check cancellation. A successfully constructed helper is
  owned by `_generate_once` and closed in its `finally` block. Constructor
  failures attempt workspace cleanup and terminate a still-running catalog,
  with a bounded reap wait and a warning if that wait expires.
- `chatgpt_client.py:469–517`: distinct bound calls remain in arrival order;
  changed contents under one call ID fail. The drain deadline is at most
  30 seconds and respects an earlier request deadline. Return requires the
  matching thread/turn completion and finished probes. The original deadline
  is restored on exit. The accepted MCP-isolation checks remain unchanged.
- `cancellation.py:76–131` and `chatgpt_client.py:203–254`: controller cleanup
  waits up to 30 seconds for active tasks without cancelling their cleanup a
  second time. Transport waits, the outer cleanup wait, loop join, and helper
  process waits have explicit limits and warning paths. Helper termination
  targets its owned process; Windows escalation targets that process tree.

### Evidence and limits

This is a source review, supported by the existing installed function-handoff
evidence in [the resource-probe issue](2026-10-30-codex-resource-probes.md).
That earlier successful research flow does not prove active cancellation or
forced teardown. No new model request, research run, test, mock, synthetic
check, build, install, broker action, or production mutation was performed.

The explicit wait limits are not a guarantee that arbitrary synchronous pipe,
transport-close, filesystem, or OS operations always return promptly. No
observed failure in those operations was established here, so they do not
justify an architecture change. This review also does not establish cleanup
behavior for every optional provider. Research publication and terminal-state
handling belong to the separate research-lifecycle issue.

### Proposed real-component verification — not executed

In one separately authorized development round, use the actual configured
Codex provider and a real ticker/input in the isolated development profile.
Cancel through the desk while a model request is active. Observe the exact
owned helper PID and research-model loop through cleanup, verify the run stays
cancelled with no later accepted response, and record the actual elapsed time
and any cleanup warning. Preserve production state. If the run reaches a bound
tool handoff before cancellation, inspect its actual call list and completion
evidence too; otherwise that path remains covered only by the earlier record.

Change count: 0 source lines, 0 test lines; this issue is the only changed file
owned by this review. `git diff --check` passed for this issue; no source syntax
check was needed because no source changed.

Fresh review `hardening_fresh_review` approved the no-change conclusion on
30 October 2026 against patch SHA-256
`d5d2d684691ee45ceeed5bb3e42736b8aef49f92522f26b1932d8625f9cd0fb5`.
The reviewer independently checked the source paths and preserved the runtime
limitations above. No additional cancellation exercise is claimed.
