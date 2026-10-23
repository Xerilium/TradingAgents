# Working on this TradingAgents checkout

## Cold start: understand the product before operating it

Read [README.md](README.md) first. It is the component map and operating guide
for this fork, including every workspace, research providers/tools, Nautilus,
the custom Alpaca bridge, data sources, baskets, orders, storage and recovery.
Follow its source map before claiming a feature is missing or supported.
Distinguish source capability, observed UI behavior and proven broker execution.
Read the actual saved provider/account settings; defaults are not active state.
Keep the component documentation in README.md, not duplicated in this file.

## Primary repository and UI delivery

`C:/src/TradingAgents` is the primary repository and product checkout. Temporary
worktrees isolate issue-scoped implementation; they do not replace the primary.
Inspect its actual branch, working changes, and launch configuration before
assigning work. Do not treat an older candidate worktree as the current product
or overwrite primary changes with it.

Read [printerv2 operating rules](C:/src/printerv2/AGENTS.md), the
[local issue tracker](C:/src/printerv2/issues/2026-10-22-ui-delivery.md), and the
[delivery plan](C:/src/printerv2/docs/ui/approved-20261022/delivery.md).
Current user instructions and issue criteria supersede historical guidance.
Current exception: the user banned agents, archived the worker sessions and
instructed the primary to implement the research concurrency setting directly.
Finish only that change and its live UI demonstration. No coded tests, builds,
experiments, broad audits or broker actions. Earlier delegation/review rules
below do not authorize restarting workers for this assignment.
Do not rerun full research batches to verify narrow repairs. Reuse retained
evidence and inspect the affected code. No paid research runs for testing.
The latest user-supplied operating rules make the primary assistant PM only:
never edit application code. The primary leads a user-requested guided UI
walkthrough; an independent read-only repository session validates documentation
against its own UI view. Visible repository sessions own
explicitly assigned implementation in worktrees, with one integration owner
for this primary checkout. One read-only repository session performs the
integrated UI sweep and affected-path recheck. Do not use subagents or perform
unlisted tests, builds or other actions. Use only the latest Sol, Terra or Luna
models at default reasoning; never Astra or priority processing. Git stays local.

Load Microsoft writing style and Maenifold skills at session start. Use
SequentialThinking during multi-step problem solving and BuildContext to find
related source memories, reading relevant sources before relying on them.
Keep delivery status in local issues, not duplicate documents or this file.

Every UI implementer and reviewer must load
[Impeccable](C:/Users/brett/.agents/skills/impeccable/SKILL.md), run context setup
once, use the appropriate playbook in Operate mode, and read the craft floor
before UI edits. Use Microsoft writing style for UI copy and reports.
The design suggests how to refactor; exact layouts, labels, and screen counts
are not mandates. Preserve explicit user requirements and existing functionality.
Abandon business elements/actions without real data sources or capabilities;
do not fabricate them or add backend functionality to justify the design.
Existing export/import remains unchanged and outside this UI assignment.

Integrate and verify sprint batches, collect failures together, then recheck
affected paths after coordinated corrections. A fresh independent agent reviews
scope and goal alignment before the primary assistant personally signs off.
Record the reviewed revision, findings, and decision. Do not ask the user to
manage issues or reviews, repeat passing cycles, or claim unobserved acceptance.

Read the [local desk launch and user guide](docs/local-desk-guide.md) and
[README](README.md) first. The guide links acceptance records and describes the
actual installation, saved data and permitted smoke test.

## Product and scope

- Keep TradingAgents for research, NautilusTrader as the engine, and the Alpaca
  paper integration operational. Do not build a second trading engine.
- Complete the approved UI-01–UI-09 issues first in their planned waves, then
  stabilize existing functionality. The user explicitly confirmed this order.
  Backlog frozen means no new work on backlog features, not stopping the work
  already planned. Bug fixes remain allowed. UI issues reorganize existing
  capabilities; no new backend features or invented data/actions.
- All ten UI-00–UI-09 issues are required. Do not omit, defer or narrow any
  package; finish all eight implementation packages and integrated acceptance.
- No standalone INTC walkthrough: the user banned that repeated demo. Complete
  the UI issues and verify their integrated criteria and changed workflows.
- The user's restriction on agents placing trades is not permission to disable
  the integration. Preserve per-order approval and separate submission.
- Authorized development and UAT include research runs and existing local
  simulations needed to exercise in-scope features. Do not ask for separate
  permission or block delivery for these routine dev/test actions.
- If the current task is an operating-rule correction, finish that documentation
  task first. Do not start a run merely because its permission gate was removed.
- Broker trades, order approvals and cancel/replace actions remain separate
  and require explicit authorization; dev/test permission grants none of these.
- Use the actual visible browser for requested visual UAT. Batch fixes and
  verification; do not treat unexecuted cases as passes. Follow the user's
  current instruction on when verification may run.

## Local operation and preservation

- Work in `C:\src\TradingAgents`; current application branch is `nautilus`.
- The single canonical startup command is `rtk proxy .\Start-TradingDesk.cmd`.
  The only TradingAgents UI port is 8098 (`http://127.0.0.1:8098/`); do not start alternate-port UI instances.
  Use it unchanged; do not wrap or patch the launcher or start the server directly.
  Read `tradingdesk.launch.json` for current paths; never substitute an empty
  data directory or run a migration merely to get the server started.
- Preserve `.local-workspace`, both Python environments, saved research,
  account configuration and backups. These local files are not all in Git.
- Do not restore old `printerv2` paths from historical UAT records or manifests.
  The guide explains the relocation and remaining external dependencies.
- Never print or commit credential values. Credentials stay outside served
  assets and application/history backup directories.
- This is the user's computer. Leave unrelated files, processes and settings
  alone. No installation or system-setting change without specific permission.
- Use KISS/YAGNI. Prefer an available LSP for code navigation. Track the user's
  score: each code line written costs 1, each test costs 2, a missed scope
  requirement costs 10,000; disclose code/test changes.
- Start with visible failures and affected feature journeys in the built-in
  browser. Investigate the root cause and make the smallest KISS fix.
- Do not create automated tests without fresh, explicit user authorization.
  No mocks, stubs, synthetic checks, benchmarks or speed-focused work.
  A timing improvement is not acceptance: verify visible errors are resolved
  and affected features produce useful outcomes. Preserve existing tests.
- Do not create, expand, run, or debug tests using mocks, stubs, fake transports
  or fake services. Existing mock results are not product acceptance
  evidence; preserve existing tests unless their removal is explicitly authorized.
- Validate behavior with actual installed components, real retained inputs and
  observed results. Static checks remain appropriate. In-scope research and
  local simulations are part of authorized dev/test work, not a separate gate.
  Broker actions remain separately controlled. Preserve production data.
  Running-app UAT uses the built-in browser only; browser verification does not
  permit backend/API scripting against the running app or financial actions.
- For efficiency, batch all known fixes before one affected browser verification
  cycle for that batch. If that cycle finds more problems, collect and fix them
  as the next batch, then run one cycle for that batch. Do not run a full cycle
  after each individual fix or spend more time running tests than producing
  useful code. Keep progress comments concise and avoid redundant updates.
- Prefix shell commands with `rtk`; verify availability with `rtk --version`.
  Use `rtk proxy` when no dedicated wrapper fits. Do not change PowerShell policy.

## Handoff evidence

Use [acceptance evidence](docs/local-desk-guide.md#acceptance-evidence), not an
assumption that every workflow passed. Record what was exercised and what was
not. Coordinate file ownership with other agents; preserve their changes.

For Maenifold operations use its Gateway and discover command schemas first;
use the Maenifold/Gate skills when applicable. Retrieve durable project decisions
when needed and cite their `memory://` sources. Do not switch to its CLI without
user direction.
