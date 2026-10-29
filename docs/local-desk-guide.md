# Local operating guide

This guide covers the installed desktop app and isolated source development.
For the platform architecture, use the [README](../README.md); for application
behavior, use [user workflows](user-workflows.md) and the
[platform reference](platform-reference.md).

## Launch the existing installation

1. Open the Windows TradingAgents desktop or Start menu shortcut. Both target
   `%LOCALAPPDATA%\Programs\TradingAgents\tradingagents-desktop.exe`.
   The repository's `Start-TradingDesk.cmd` opens that installed executable too.
2. The production desk serves <http://127.0.0.1:8098/>. If the browser does not
   open automatically, open that address.
3. Inspect the configured account and Nautilus connection in Settings. Startup
   uses saved settings; if the engine is stopped, use its explicit Start control.
4. Verify paper/live identity, account observation time, balances, positions
   and price timestamps before relying on them.

The tray offers Open, Restart, Check for updates, Open logs and Quit.
Closing the browser leaves the app running. Stop Nautilus disconnects the
engine while leaving the web app and saved research available.
The supervisor is designed to stop only processes it owns; do not substitute
a broad process-kill command.

A clone is not a complete installed environment. Do not start the old Python
launcher with its defaults or restore historical printerv2 paths.

## Production and development

| Item | Production | Development |
| --- | --- | --- |
| Launcher | Installed shortcut / `Start-TradingDesk.cmd` | `rtk proxy .\Start-TradingDesk-Dev.cmd` |
| Port | 8098 | 8099 |
| Profile | `%USERPROFILE%\.cache\trader\production` | `%USERPROFILE%\.cache\trader\development` |
| Python | Private installed `runtimes/desk` and `runtimes/native` | Checkout `.venv` and `.venv-nautilus-v1` |
| Credential namespace | `TradingAgents.desktop.production` | `TradingAgents.desktop.development` |

Development must not share production stores, credentials or endpoints.
An installed release contains its own application files; editing checkout source
does not establish that the installed app is running those changes.

The production desk log is `logs/desk.log` under its profile. The app also has
profile-specific private, cache and temporary directories. Model caches and
runtime dependencies are separate from application records.

## Credentials and account changes

Use Settings → Account for Alpaca credentials and Settings → Integrations for
service API keys. Desktop credentials use Windows Credential Manager or macOS
Keychain; there is no plaintext-file fallback. Fields do not return saved secrets.
Blank values keep existing credentials; Remove is an explicit separate action.

Saving credentials does not reconnect an active engine. Stop Nautilus and then
start it to load the saved account/endpoint. Recheck observed paper/live identity
and readiness. An execution-profile change also requires a stopped-session
transition and current capability checks.

Codex authentication, compatible model endpoints and Maenifold are separate
dependencies. The desktop `codex` provider uses the signed-in app-server;
`chatgpt` is a distinct framework Responses API adapter. Read actual saved
provider/model/endpoint settings instead of assuming defaults.

## Records and retention

| Location or owner | Contents |
| --- | --- |
| Profile `application` | SQLite application records: settings, lists, rules, notes, drafts, baskets and referenced artifacts; separate latest-research cache |
| Profile `research` | Existing referenced artifacts or maintenance data; not a research-history import source |
| Native worker | In-memory Nautilus cache/session; not a durable broker ledger |
| Browser storage | View preferences and editing state; clearing it does not clear server records |
| Maenifold | Durable research knowledge, graph and structured reasoning |
| Alpaca | Actual broker account, holdings, orders and fills |

Keep only the latest research per ticker. A new cycle replaces that ticker's
previous research. Interrupted cycles are not resumed from LangGraph checkpoints.
Authored settings, lists, rules, notes, chart definitions and order records remain
separate. An old research link can become unavailable without invalidating its
existence as a saved reference.

Preserve `.local-workspace`, both development environments, private installed
runtimes, existing backups and source-linked records during maintenance. Older
paths in saved evidence describe provenance, not the current launch configuration.

## API reads and maintenance

For production API and AppData operations on this PC, use the **installed standalone
desk Python with `-I`**. The development interpreter can resolve a different AppData
database at the same apparent path. The helper uses the ordinary local session
and CSRF protections and suppresses tokens in printed state.

```powershell
rtk proxy "$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py get /api/health
rtk proxy "$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py get '/api/state?compact=1'
rtk proxy "$env:USERPROFILE/.cache/trader/production/runtimes/desk/python.exe" -I scripts/desk_api.py get /api/workspace --field revision
```

Production is fixed to 127.0.0.1:8098; `--dev` selects isolated 8099.
Before production maintenance, compare loaded settings, revision and ticker list
with the captured pre-change state. Matching the launch path alone is insufficient.

A POST timeout does not prove the action failed; read resulting state before
deciding whether to retry. Never pass secrets through CLI arguments, files or logs.
Credential POST bodies stay in memory. API access does not combine approval with
submission or authorize broker actions.

## Backup and recovery

Existing Local records controls inspect supported application backups before
explicit restore. Credentials, environments and native memory cache are excluded.
Research checkpoints are neither created nor restored. Restore invalidates old
approval authority, stops native execution and requires fresh reconciliation and
exact review. It does not change broker records.

Do not erase a store to work around a loading failure. First confirm profile,
logs, native connection and actual loaded data. A directory's name, age or UUID
does not establish that its artifacts are unreferenced: drafts and chart records
may still depend on them.

If explicitly authorized to remove application artifacts, trace references from
all application records and referenced files, verify resolved targets, reject
junctions/symlinks, preserve referenced content and compare retained hashes.
Stop only the app-owned processes first. This documentation cleanup is not an
instruction to clean production data.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Service unavailable | Correct profile, owning app, port and desk log; do not start a competing instance |
| Account unavailable | Nautilus status and saved identity; never infer zero holdings |
| Old or missing prices | Feed, market session, source time and coverage; fresh account data is not a new trade price |
| Wrong research provider | Saved provider, endpoint, model and workflow revision |
| Partial or interrupted research | Saved reports, completion gaps and Activity; start a new cycle when appropriate |
| Laya not ready | Diagnostics reports model/device/cache/load errors; browser refresh does not restart a failed worker |
| Empty performance/simulation | Required retained observations, historical coverage and declared assumptions |
| Concurrent edit conflict | Reload the current saved revision instead of overwriting another session |
| Unknown command outcome | Read reconciliation/command status; never automatically resubmit |

## Packaging

Normal releases refresh application files and run `npm run build:release` in
`desktop`. They preserve installed private runtimes and CUDA.
Dependency preparation and `build:setup` are separate full-setup operations.
Follow [packaging/README.md](../packaging/README.md); do not reinstall dependencies
for an ordinary UI, code or prompt release.

Windows x64 is the locally installed target. macOS locks target Apple Silicon on
macOS 26 or later; support requires a matching-host build and runtime verification.

## Acceptance evidence

Documentation and source inspection are not proof of current runtime behavior.
The older October UAT exercised read-only views and some local authoring, but did
not establish all broker approval/submission, cancel/replace, fill, populated-account
or full event-accounting paths. Historical case counts do not certify a new release.

Windows installation, native credential storage and a paper-account connection
have dated observations in the [release issue](issues/2026-10-26-installable-desktop-release.md)
and [credential issue](issues/2026-10-27-native-credentials.md).
End-to-end updater delivery and macOS execution remain unproven in those records.
Normal tray Quit also needs observed acceptance before claiming it works here.

Laya weights loading or a small device sample does not establish calibrated
classification quality; see [Laya social review](laya-validation.md).
Use the [local issues](issues) for actual delivery status, not duplicate audit logs.
