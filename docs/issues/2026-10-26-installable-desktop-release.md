# Installable desktop release with isolated development

Status: Windows 0.6.1 installed outside the repository after the model-token-limit
batch; see `2026-10-26-model-token-limits.md`. The 0.6.0 installer is retained.
Desktop and Start menu shortcuts point to the installed executable. The user
parked the Due Negligence rebrand; this package retains TradingAgents and its
existing square icon. macOS execution and the published update feed remain open.
Source reviewed: nautilus at 580f1c8 plus the current working changes.
Requested platforms: Windows and macOS.

## Problem

The current desktop shortcuts start the source checkout. The launcher uses the
checkout's .venv, native environment and configured stores. Editing or changing
that checkout can affect the running desk. Closing the browser does not stop
the service. This is a development launch arrangement, not a distributable install.

The user requires an installed release outside the repository, an update path,
and a clear way to stop the app and its owned processes. Development must not
change the installed code, dependencies, settings or data.

## Proposed implementation

Use a small native tray host and retain the existing browser UI and Python desk.
The user selected Tauri on 26 October 2026. Use its existing Windows/macOS
bundler, single-instance, opener, dialog and updater support. Use process-wrap
for Windows job objects and macOS process groups instead of a custom process
enumerator. Package private portable Python distributions with uv at build time.
The observed Windows results and remaining limits are recorded below.
Do not rewrite the trading engine or browser UI.

1. Package a named release from an identified source revision, including web
   assets and private, pinned Python runtimes for the desk and Nautilus.
   Build platform-native artifacts; do not copy the existing Windows virtual
   environments and call them portable. Ensure model and native dependencies
   are present or have an explicit supported first-run setup.
2. Install release files outside the checkout. Keep mutable user data, logs,
   model caches and private configuration outside both the release and repo.
   No editable installs, source symlinks, checkout working directory, or
   development PYTHONPATH may be required by the installed app.
3. Give development its own runtime, settings, stores, logs, identity and browser
   origin. Production keeps the existing 8098 endpoint during cutover. Define
   the separate development endpoint explicitly; do not start another instance
   against the production stores. Development must not auto-connect to the
   production broker configuration.
4. The tray menu offers Open, Restart, Check for updates and Quit.
   Open uses the default browser. Closing that browser leaves the tray app
   running. Quit stops this instance's work and closes its owned children.
   Show Starting, Running, Stopping and Failed states with access to logs.
5. A second launch opens the same installed instance. Keep a handle to every
   owned child. Use graceful shutdown first and a bounded forced fallback for
   children that do not exit. Complete server, research executor, Laya, native
   worker and model-helper shutdown. Do not kill processes by executable name.
   A reused Maenifold service or another chat's tools must remain running.
6. Update only from a verified release package. Stage and verify the new release
   before replacing the active code. Let the user apply the update when work is
   stopped. Preserve data and private settings. Keep the previous release for
   recovery; rollback must respect schema compatibility. A schema change needs
   a consistent backup and an explicit recovery path before activation.
7. Replace the source-linked shortcuts only after the installed release works.
   First stop writers, preserve the current stores and private configuration,
   then perform a controlled one-time transfer. Never run two versions against
   the same database. Preserve the source installation until cutover succeeds.

## Dependencies and ownership

The package must account for the desk Python dependencies, Nautilus and custom
Alpaca bridge, Laya and model files, static/vendor web assets, and model-provider
integration. The current Codex provider uses an installed signed-in app-server;
Maenifold can be a separately installed shared service. Document those real
prerequisites and supported versions. Do not claim a clean-machine install is
complete while those requirements still depend on paths on this PC.

Do not bundle credentials, account configuration, developer tool servers,
research results, logs, or this user's model-provider session. Installation
must not change unrelated applications or global Python environments.

## Packaging inventory

- Installed desk runtime: Python 3.12.10. Native runtime: Python 3.13.7 with
  NautilusTrader 1.231.0. Keep their dependencies separate.
- Rust 1.98.1, Cargo 1.98.1, Node 24.20.0, uv 0.12.22 and Visual Studio 2022
  Build Tools are present. No toolchain installation was performed.
- The native worker reads its reviewed runtime manifest from a repository docs
  path. Package that manifest as application data and supply platform-specific
  wheel evidence; a Windows file-hash manifest cannot establish macOS validity.
- The current web server lacks a parent-controlled normal shutdown route. Add
  an inherited control pipe so the tray can request graceful shutdown without
  adding a public shutdown HTTP endpoint. Preserve its existing service close.
- Keep handles to app-started Gateway children; a reused external Gateway stays
  outside the application ownership group. macOS children that create their own
  sessions need explicit ownership and shutdown handling.
- Tauri updater signatures and release hosting must be configured honestly.
  Never ship a placeholder public key or report an unavailable feed as current.
  Keep the private release key outside Git and installed client packages.
- Maenifold became available later in this session. Relevant knowledge was read
  and the Windows Store Python profile lesson was saved to the existing note.

## Acceptance

- Install on Windows without requiring this source checkout or its environments.
- With the checkout unavailable, launch from the installed shortcut, load all
  nine workspaces and access preserved settings and latest research.
- Verify the configured paper account through the installed native runtime.
- Close the browser, reopen from the tray and verify the same instance is used.
- Quit and observe that all app-owned children exit; unrelated tools remain.
- Run isolated development and production together. A source edit, dev restart
  or dev setting change must not change the installed app or production data.
- Install a second release and verify version change and preserved data. Exercise
  the supported recovery path without assuming database rollback is safe.
- Build and exercise the corresponding macOS application on macOS. Windows-only
  source review does not establish macOS acceptance.
- No automated tests, research reruns or broker actions were performed.

## Observed Windows delivery, 26 October 2026

- Signed updater installer: `desktop/src-tauri/target/release/bundle/nsis/TradingAgents_0.6.0_x64-setup.exe`
  and companion `.sig`, 246,618,425 bytes. SHA-256:
  `6828115505acf7c981b0999edc159e939b5efee3f35864264e8de36f85a8f5df`.
  This is a Tauri updater signature, not a claim of Windows Authenticode signing.
- Installed executable: `%LOCALAPPDATA%/Programs/TradingAgents/tradingagents-desktop.exe`.
  Both existing shortcuts now target it. The package contains separate standalone
  desk and native runtimes. Repository edits cannot change those installed files.
- Production profile: `%LOCALAPPDATA%/com.tradingagents.desktop/production`.
  The original source stores were preserved. The installed UI showed all 23
  FAANGMAN + Semiconductor names, saved research, the verified paper account,
  Nautilus 1.231.0 connected and the original $100,000 balances. All nine workspace
  views loaded in the integrated check; this does not prove every workflow.
- Initial migration exposed Windows Store Python AppData redirection. The verified
  copy was moved into real AppData using the standalone runtime. Initial defaults
  were retained separately, and the migration utility now refuses Store Python.
- Development uses source runtimes, port 8099 and `.local-workspace/development`.
  One actual startup showed separate defaults and no production account while the
  installed 8098 app retained its verified account. The temporary development host
  was then stopped by its verified PID; its Python child exited and production
  remained running. This checks forced ownership cleanup, not normal tray Quit.
- Tray Open/Restart/Check for updates/Open logs/Quit are implemented. Normal Quit
  and Restart have not been operated through the tray. The UI automation surface
  did not expose the Windows tray, so those actions are not marked as passes.
- Real update key and prospective release manifest are prepared. No feed or release
  was published, and no end-to-end upgrade or rollback was exercised.
- macOS 26+ Apple Silicon locks and configuration are present. No Mac binary,
  signing, notarization or runtime check was performed. Intel Mac support is not
  claimed for the pinned Torch/Nautilus packages.

## Evidence and sources

Local source: Launch-TradingDesk.py, Start-TradingDesk.cmd, pyproject.toml,
tradingagents/web/server.py, README.md and docs/local-desk-guide.md.
Current source revision: 580f1c8; working changes remain separate.

Official documentation accessed 26 October 2026:
- https://v2.tauri.app/learn/system-tray/
- https://v2.tauri.app/develop/sidecar/
- https://v2.tauri.app/distribute/
- https://v2.tauri.app/plugin/updater/
- https://docs.python.org/3/library/venv.html
- https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html

Reusable profile-migration lesson saved in
`memory://lessons/tradingagents/trading-product-pm-delegation-and-capability-assessment`.
