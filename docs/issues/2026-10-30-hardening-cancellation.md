# Research cancellation and tool-handoff hardening

Status: Assigned — investigation
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
