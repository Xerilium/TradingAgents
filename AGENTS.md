# Working on this TradingAgents checkout

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
The primary assistant owns planning, documentation, local Git, and issue/PR
administration; it never edits application code or resolves code conflicts.
Implementation agents work from scoped issues with explicit worktree/file
ownership; one integration agent owns shared files. Agents report through the
primary assistant. Use only the latest available Sol, Terra, or Luna models at
default reasoning unless the task warrants more; never Astra. Git stays local.

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
- Backlog frozen except bug fixes. An open issue, design or existing plan does
  not authorize features or discretionary refactoring. Establish a concrete
  failure in existing behavior, then make a surgical fix and verify the result.
- The user's restriction on agents placing trades is not permission to disable
  the integration. Preserve per-order approval and separate submission.
- Until explicitly authorized otherwise: no trades, order approvals, broker
  cancel/replace actions or new research runs. Read existing research.
- Use the actual visible browser for requested visual UAT. Batch fixes and
  verification; do not treat unexecuted cases as passes. Follow the user's
  current instruction on when verification may run.

## Local operation and preservation

- Work in `C:\src\TradingAgents`; current application branch is `nautilus`.
- The single canonical startup command is `rtk proxy .\Start-TradingDesk.cmd`.
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
  observed results. Static checks remain appropriate. This does not authorize
  broker actions, research runs or runtime activation. Preserve production data.
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
