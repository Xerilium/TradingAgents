# Working on this TradingAgents checkout

Read the [local desk launch and user guide](docs/local-desk-guide.md) and
[README](README.md) first. The guide links acceptance records and describes the
actual installation, saved data and permitted smoke test.

## Product and scope

- Keep TradingAgents for research, NautilusTrader as the engine, and the Alpaca
  paper integration operational. Do not build a second trading engine.
- Feature freeze: make only requested, surgical fixes. Every product change
  needs a user requirement; do not invent blockers or expand the specification.
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
- Do not create tests unless the user specifically asks to create tests.
- For efficiency, batch all known fixes before running one verification/test
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
