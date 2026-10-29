**DON'T BE A CUNT: SAVE YOUR WORK, COMMIT YOUR CHANGES LOCALLY, AND DO NOT LEAVE YOUR WORK UNCOMMITTED OR UNTRACKED. LEAVING OTHER PEOPLE TO RECOVER YOUR UNSAVED SHIT IS UNACCEPTABLE. KEEP SECRETS, CREDENTIALS, PRIVATE RUNTIMES, AND MACHINE-LOCAL FILES OUT OF COMMITS; EXPLICITLY IGNORE THEM. NEVER DISCARD SOMEONE ELSE'S WORK TO GET A CLEAN STATUS.**

# Working on this TradingAgents checkout

The user stopped use of Serena. Use normal repository tools and Maenifold.
If `.serena/memories/critical_info.md` exists, read it as a file; do not start Serena.

## Current research retention

Keep only the latest research result per ticker; the next cycle replaces it.
No desk history import, research resume, replay ledger or persisted LangGraph
checkpoints are required. Maenifold owns long-term memory; the desk must not
maintain a competing local decision log. Settings, authored lists/rules/notes,
draft and basket terms, and broker approval semantics remain separate. This
supersedes historical research-preservation or resume guidance below.

Portfolio → Proposed performs one joint deep-model synthesis of eligible latest
research and cached dated prices, with separate model capital and deterministic
whole-share sizing. Keep this session-only proposal separate from per-stock
research, human baskets, historical simulation and broker authority. Never
silently replace failed research, truncate candidates or invent allocations.

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
Current assignment: package TradingAgents with Tauri for Windows first, with
macOS support. The user explicitly authorized the primary to implement and
build here on 26 October 2026, replacing the old PM-only and no-subagent
restrictions for this assignment. Scoped repository workers may help; use
GPT-6.1 Terra. Prefer the lowest practical reasoning effort (currently `low`)
for subagents. Increase it only when the task needs it or the user asks.
Coordinate file ownership and preserve existing working changes.
Use off-the-shelf packaging, updater and process-management components where
practical. Install released code and its private runtimes outside the source
checkout. Isolate development settings, stores, runtime and endpoint from the
installed production instance. The tray must stop only processes the app owns.
Batch implementation before one packaging/build and affected UI verification
cycle; delegate builds to a worker. No automated tests, mock services or
research reruns. A package build and real installed-app startup/shutdown
verification are authorized. Preserve production data and credentials during
controlled cutover. Broker actions still require explicit authorization.
Git stays local unless the user asks to publish or push.

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
- Use the installed desktop/Start menu shortcut for production. The repository
  `rtk proxy .\Start-TradingDesk.cmd` opens that installed executable too.
  Production uses port 8098 and its private production profile. Development uses
  `rtk proxy .\Start-TradingDesk-Dev.cmd`, port 8099 and the
  `~/.cache/trader/development` profile. Never share production stores or
  credentials with development. Do not start the old Python launcher directly.
- Preserve `.local-workspace`, both Python environments, saved research,
  account configuration and backups. These local files are not all in Git.
- Do not restore old `printerv2` paths from historical UAT records or manifests.
  The guide explains the relocation and remaining external dependencies.
- Never print or commit credential values. Credentials stay outside served
  assets and application/history backup directories.
- Desktop API keys belong in Windows Credential Manager or macOS Keychain,
  managed through Settings. Production and development use separate vault
  namespaces. Do not add a desktop plaintext credential-file fallback.
- This is the user's computer. Leave unrelated files, processes and settings
  alone. No installation or system-setting change without specific permission.
- Use KISS/YAGNI. Prefer an available LSP for code navigation. Track the user's
  score: each code line written costs 1, each test costs 2, a missed scope
  requirement costs 10,000; disclose code/test changes.
- Start with visible failures and affected feature journeys in the built-in
  browser. Investigate the root cause and make the smallest KISS fix.
- A human-authorized test or research round means one round. A failure does
  not authorize another. Do not repeat runs or test cycles without fresh
  authorization. Fix source in one batch and report its actual validation status.
- Solve data rate limits with simple configurable retries and exponential
  backoff. Do not add a queue engine or scheduler for this purpose.
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
- Use the app's local API where it makes sense for reads, progress checks and
  user-authorized actions. Use its existing session and CSRF protections; do
  not bypass them or expose tokens. API access does not authorize extra work.
- Use the built-in browser for visual checks and UI behavior. An API response
  alone does not prove the page renders or its controls work.
- Keep order preparation, per-order approval and broker submission separate
  through both interfaces. Approval does not authorize submission. Broker
  actions still require the explicit authorization stated above.

### Release packaging

Normal releases are app-only: refresh with `packaging/refresh_project.py` and
build `desktop` with `npm run build:release`. Do not rerun dependency preparation
or include `payload/desk` and `payload/native` for ordinary code/prompt updates.
Full setup is an explicit separate build for first installation/dependency changes;
see `packaging/README.md`. Preserve installed private runtimes and CUDA.

### Local API helper

Production profile maintenance must use the installed standalone runtime at
`~/.cache/trader/production/runtimes/desk/python.exe`
with `-I`, including API calls, backups, restore and file verification. On this
PC, the development Python sees a different AppData database at the same path.
Do not use it for production AppData operations. Compare the loaded API settings,
revision and ticker list with the captured pre-update state before starting work;
a matching launch-root identity alone does not prove the correct data is loaded.

Use `scripts/desk_api.py` with Python 3.11+; it uses only the standard library.
It opens the normal local session, supplies the CSRF token for POST, keeps
session tokens in memory and removes the CSRF token from printed state.
Production is fixed to `127.0.0.1:8098`; `--dev` selects isolated port 8099.
Redirects and proxies are disabled. No request is retried automatically.

```powershell
rtk proxy "$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py --help
rtk proxy "$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py get /api/health
rtk proxy "$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py get /api/model-limits --timeout 120
rtk proxy "$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py get '/api/state?compact=1'
rtk proxy "$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py get /api/workspace --field revision
```

For an authorized change, use `post /api/<route> --json-file <body.json>`.
Read the actual route and service handler for its body contract; preserve
required revisions and exact order terms. `--timeout <seconds>` changes the
per-request timeout. A timeout or connection error does not prove a POST failed;
read the resulting state before deciding whether to retry. Do not print private
configuration or credential files. The helper grants no additional authority,
does not combine approval with submission and does not replace visual UI checks.

`get /api/credentials` returns native-store availability and configured flags,
never secret values. Credential POST bodies must stay in memory; do not use
`--json-file`, shell arguments, logs or temporary files to carry secrets.
Saving credentials does not reconnect Nautilus or authorize broker actions.

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
analysts must read canonical GetHelp before Gateway tool use. The app preloads
that help into tool descriptions and exposes GetHelp for allowed commands.
use the Maenifold/Gate skills when applicable. Retrieve durable project decisions
when needed and cite their `memory://` sources. Do not switch to its CLI without
user direction.
