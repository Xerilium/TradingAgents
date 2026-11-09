**DON'T BE A CUNT: SAVE YOUR WORK, COMMIT YOUR CHANGES LOCALLY, AND DO NOT LEAVE YOUR WORK UNCOMMITTED OR UNTRACKED. LEAVING OTHER PEOPLE TO RECOVER YOUR UNSAVED SHIT IS UNACCEPTABLE. KEEP SECRETS, CREDENTIALS, PRIVATE RUNTIMES, AND MACHINE-LOCAL FILES OUT OF COMMITS; EXPLICITLY IGNORE THEM. NEVER DISCARD SOMEONE ELSE'S WORK TO GET A CLEAN STATUS.**

# Working on this Printer checkout

The user stopped use of Serena. Use normal repository tools and Maenifold.
If `.serena/memories/critical_info.md` exists, read it as a file; do not start Serena.

## Credential and secret handling — hard rule

- Never read, attempt to read, enumerate, or verify the presence of credentials or
  secrets. Prohibited: Windows Credential Manager and keyring APIs
  (`CredRead`/`CredWrite`, advapi32 P/Invoke), `cmdkey`, keychain CLIs, registry
  Environment secret values, environment-variable secret lookups, `.env` files, and
  any config that may contain a secret (on Windows, including
  `C:\Users\brett\.cache\trader\production` desk configuration).
- An attempted read is a compromise. It invalidates the credential whether or not a
  value is printed, because anything that can enter a tool output or transcript is
  already in model context.
- If work requires a credential, stop and ask the human to wire it. Never wire,
  bridge, copy, relay, log, commit, push, or paste a secret or any fragment of one,
  and never stage a secret into a committed or shared file.
- If you touch a credential by accident, say so in your very first sentence, attempt
  no cleanup, rotation, or deletion, and stop that line of work until the human
  directs it.

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

Read [README.md](README.md) first for the platform map, then the
[platform reference](docs/platform-reference.md) for every workspace, research providers and
tools, Nautilus, the custom Alpaca bridge, data sources, baskets, orders, storage,
recovery and its [source map](docs/platform-reference.md#source-map).
Distinguish source capability, observed UI behavior and proven broker execution.
Read the actual saved provider/account settings; defaults are not active state.
Keep component documentation in those files, not duplicated in this file.

## Primary repository and delivery

`D:/src/TradingAgents` is the primary repository and product checkout on this PC. Temporary
worktrees isolate scoped implementation; they do not replace the primary.
Inspect its actual branch, working changes, and launch configuration before
assigning work. Do not treat an older candidate worktree as the current product
or overwrite primary changes with it.

The older `C:/src/printerv2` operating rules, issue tracker and delivery plan
are historical context only. Current user instructions, this file and
`docs/local-desk-guide.md` supersede them; do not restore printerv2 paths.
Desktop packaging with Tauri (Windows first, macOS second) is the standing
release path; see `packaging/README.md`. Scoped repository workers may help;
use the latest Claude Sonnet and Grok models unless the user names others, and the lowest practical reasoning effort. Increase it only when the
task needs it or the user asks. Coordinate file ownership and preserve existing
working changes.
Use off-the-shelf packaging, updater and process-management components where
practical. Install released code and its private runtimes outside the source
checkout. Isolate development settings, stores, runtime and endpoint from the
installed production instance. The tray must stop only processes the app owns.
Batch implementation before one packaging/build and affected UI verification
cycle; delegate builds to a worker. No automated tests, mock services or
research reruns unless the current task authorizes them. A package build and real
installed-app startup/shutdown verification are authorized for packaging tasks.
In-place upgrade is the supported release path: the app-only installer replaces
the payload, provenance and launcher only, leaving the production profile, private
runtimes, CUDA, saved research and credentials untouched. Never copy, snapshot or
robocopy the production profile or the installed payload before an upgrade; recover
from a bad bundle by installing the previous app-only bundle, and use the app's own
workspace backup for data restore. Historical UAT records that require a pre-cutover
profile copy are superseded by this rule. Broker actions still require explicit
authorization. Git stays local unless the user asks to publish or push.

Load Microsoft writing style and Maenifold skills at session start. Use
SequentialThinking during multi-step problem solving and BuildContext to find
related source memories, reading relevant sources before relying on them.
Keep delivery status in local issues (`docs/issues`), not duplicate documents or this file.

Every UI implementer and reviewer must load the installed `impeccable` skill
through the Skill tool, run context setup once per agent session, use the
appropriate playbook in Operate mode, and read the craft floor before UI edits.
Use Read mode for documentation and Microsoft writing style for UI copy/reports.
Follow [the dogfood loop brief](docs/dogfood-loop.md): keep operating skills and
product docs current, use privacy-reviewed real screenshots in the README, and
prefer plain English, intuitive grouping and glanceable, load-bearing information
over repeated disclaimers, jargon and dense text or textbox-heavy dashboards.
The design suggests how to refactor; exact layouts, labels, and screen counts
are not mandates. Preserve explicit user requirements and existing functionality.
Abandon business elements/actions without real data sources or capabilities;
do not fabricate them or add backend functionality to justify the design.
Existing export/import remains unchanged unless the current task says otherwise.

Integrate and verify batches, collect failures together, then recheck
affected paths after coordinated corrections. A fresh independent agent reviews
scope and goal alignment before the primary assistant personally signs off.
Record the reviewed revision, findings, and decision. Do not ask the user to
manage issues or reviews, repeat passing cycles, or claim unobserved acceptance.

Read the [local desk launch and user guide](docs/local-desk-guide.md) first for the
actual installation, saved data and permitted smoke test.

## Product and scope

- Printer is the product; TradingAgents is its research component. Preserve the
  existing package/import names, executable/build target, app identifier,
  Windows install/upgrade bindings, profiles and credential namespaces when
  changing display labels. A rebrand is not a data migration.

- Keep TradingAgents for research, NautilusTrader as the engine, and the Alpaca
  paper integration operational. Do not build a second trading engine.
- UI work reorganizes existing capabilities; no new backend features or invented
  data/actions. Bug fixes remain allowed.
- Do not rerun a standalone INTC walkthrough; the user banned that repeated demo.
  Verify the changed workflows instead.
- The user's restriction on agents placing trades is not permission to disable
  the integration. Preserve per-order approval and separate submission.
- Research runs and existing local simulations needed to exercise in-scope
  features are authorized development and UAT actions when the current task
  calls for them; they need no separate permission.
- If the current task is an operating-rule correction, finish that documentation
  task first. Do not start a run merely because its permission gate was removed.
- Broker trades, order approvals and cancel/replace actions remain separate
  and require explicit authorization; dev/test permission grants none of these.
- Use the actual visible browser for requested visual UAT. Batch fixes and
  verification; do not treat unexecuted cases as passes. Follow the user's
  current instruction on when verification may run.

## Local operation and preservation

- Work in `D:\src\TradingAgents`; its application branch is `nautilus` unless the task says otherwise.
- Use the installed desktop/Start menu shortcut for production. The repository
  `.\Start-TradingDesk.cmd` opens that installed executable too.
  Production uses port 8098 and its private production profile. Development uses
  `.\Start-TradingDesk-Dev.cmd`, port 8099 and the
  `~/.cache/trader/development` profile. Never share production stores or
  credentials with development. Do not start the old Python launcher directly.
- Development reloads: no tray. Leave a healthy, correctly loaded service alone.
  Before restarting, confirm automatic authority off, no active work/manual run
  and no working, pending or unknown orders/commands. First stop only proven old
  checkout DEV host/backend PIDs (exact executable, dev data/port arguments and
  ancestry), then launch the provided Desktop `Start-TradingDesk-Dev.lnk`.
  Never use name-wide/production kills, inspect credentials or change authority.
- Agents must resolve that exact link and retain its unchanged target/arguments
  in a background `Execute` (`fireAndForget: true`), not detach the launch:

  ```powershell
  $link = (New-Object -ComObject WScript.Shell).CreateShortcut(
      "$env:USERPROFILE\OneDrive\Desktop\Start-TradingDesk-Dev.lnk")
  Start-Process -FilePath $link.TargetPath -ArgumentList $link.Arguments `
      -WorkingDirectory $link.WorkingDirectory -Wait -PassThru
  ```

  Keep the supervisor alive without polling it. Require ready/reconciled
  `127.0.0.1:8099` and the affected live label/UI, not just a new PID.
- `WriterBusy`: identify the OS lock owner; never delete `.writer.lock`, bypass
  the lease or blindly relaunch. Do not substitute a direct Python server.
- Do not assume Edge survives. Reuse the exact local Printer tab, or open one
  authorized isolated visible window if absent; never use a personal profile.
- Preserve `.local-workspace`, both Python environments, saved research,
  account configuration and backups. These local files are not all in Git.
- Do not restore old `printerv2` paths from historical UAT records or manifests;
  `docs/local-desk-guide.md` describes the current launch and storage layout.
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
- Authorized development includes the affected real local verification needed to
  finish the work. A failed check is work to diagnose, fix and recheck, not a new
  permission gate. Batch corrections and recheck the affected failed paths without
  asking again; do not repeat passing cycles or claim unobserved acceptance.
- A broker-action restriction or missing live execution evidence blocks that
  specific action or acceptance claim, not authorized development. Do not pause
  the development loop or require the operator to supply another defect on that
  basis. Continue investigating and completing meaningful non-trading work; keep
  broker, credential, destructive-action, production and testing boundaries intact.
- Question-widget prompting is banned for already-authorized work. Do not call
  `AskUserQuestion` in this checkout. Do not populate `ask` or `actions` on the
  app's `mcp__ccd_turn__wrap_up` to reauthorize development, ordinary navigation,
  static checks or affected local verification. Use its required status recap
  without an approval question. Never turn a failed local check into a human-
  approval hold, recurring reminder or a reason to stop doing the authorized work.
  Separate broker actions, credentials, destructive actions and genuinely new
  scope still require their existing authorization; this rule grants none of them.
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

Normal releases are app-only: refresh with `packaging/refresh_project.py`.
The signing-dependent `build:release` command was removed. Do not rerun dependency preparation
or include `payload/desk` and `payload/native` for ordinary code/prompt updates.
Full setup is an explicit separate build for first installation/dependency changes;
see `packaging/README.md`. Preserve installed private runtimes and CUDA.

### Local API helper

Production data lives under `%USERPROFILE%\.cache\trader\production` (the
`appDirectoriesOverride` in `desktop/src-tauri/tauri.conf.json`). Production
maintenance must use the installed standalone runtime at
`~/.cache/trader/production/runtimes/desk/python.exe`
with `-I`, including API calls, backups, restore and file verification. A leftover
`%LOCALAPPDATA%\com.tradingagents.desktop\production` store also exists on this PC
from earlier builds; it is not the live production data, so do not open it for
production operations. Compare the loaded API settings,
revision and ticker list with the captured pre-update state before starting work;
a matching launch-root identity alone does not prove the correct data is loaded.

Use `scripts/desk_api.py` with Python 3.11+; it uses only the standard library.
It opens the normal local session, supplies the CSRF token for POST, keeps
session tokens in memory and removes the CSRF token from printed state.
Production is fixed to `127.0.0.1:8098`; `--dev` selects isolated port 8099.
Redirects and proxies are disabled. No request is retried automatically.

```powershell
"$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py --help
"$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py get /api/health
"$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py get /api/model-limits --timeout 120
"$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py get '/api/state?compact=1'
"$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py get /api/workspace --field revision
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
  useful code. Keep progress comments concise and avoid redundant updates. Do
  not change PowerShell policy.

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
