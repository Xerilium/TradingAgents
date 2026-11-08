# Printer product identity

## Scope and status

The user named the whole product **Printer**. **TradingAgents** remains the
research framework/component. This source batch preserves the existing dark
Operate visual system and mark; it is not an aesthetic redesign.

Base revision: `371ead5` on `nautilus` in `D:\src\TradingAgents`.
The complete display rebrand and review corrections are implemented and approved
by independent source review. An authorized app-only build, coordinated
development UAT and local delivery evidence remain with the orchestrator.
No production installation or acceptance is claimed.

## Implemented

- Web brand, home accessible name, initial loading copy, browser titles and the
  legacy Universe review heading say Printer. Research pipeline labels still
  accurately say TradingAgents.
- Desktop tray tooltips, notices, update dialogs and dependency/launch errors say
  Printer. The isolated debug host is named Printer Development.
- Release `productName` is Printer. Windows installer/wizard/locale text, Apps
  entry, new shortcut labels and executable metadata use Printer. Normal macOS
  metadata and bundle naming follow the same product name.
- Normal/recovery health reports and the read-only desk MCP server identify
  Printer. The legacy launcher accepts both old and new health product names
  while retaining the same application-identity and cache-mode checks.
- README, PRODUCT, DESIGN, contributor guidance, platform/local/packaging guides,
  active UI blueprint and operating-skill source distinguish the product from
  its research component. Current checkout instructions use the observed
  `D:\src\TradingAgents` location. Historical records remain unchanged.
- The README leads with the parent session's real 8 November Printer development
  entry at 2112 × 1284. The branding owner privacy-reviewed that capture and copied
  it unchanged to `docs/images/printer-spy-entry.png`; provenance is recorded in
  `docs/images/README.md`. Earlier screenshots remain unchanged and dated.
  This is entry-display evidence, not a completed rebalance or broker acceptance.
- Corrected the local guide's stale claim that basket allocation is whole-only:
  basket/SPY sizing follows observed fractional eligibility and precision.
  Portfolio's model proposal and saved-plan simulation whole-share rules remain
  unchanged.

### Files

The branding scope is 31 files, including the two shared `app.js` label lines:

- `tradingagents/web/static/index.html`, `app.js`, `recovery.html`
- `tradingagents/web/service.py`, `server.py`, `recovery_mode.py`
- `desktop/src-tauri/src/main.rs`, `backend.rs`
- `desktop/src-tauri/tauri.conf.json`, `tauri.dev.conf.json`
- `desktop/src-tauri/windows/installer.nsi`, `LICENSE-MIT`, `UPSTREAM.md`
- `desktop/ui/index.html`
- `scripts/desk_mcp.py`, `Launch-TradingDesk.py`, `Start-TradingDesk.cmd`
- `README.md`, `PRODUCT.md`, `DESIGN.md`, `AGENTS.md`
- `docs/platform-reference.md`, `docs/local-desk-guide.md`,
  `docs/ui-redesign-blueprint.md`, `packaging/README.md`
- `docs/images/printer-spy-entry.png`, `docs/images/README.md`
- `.agents/skills/use-tradingagents/SKILL.md`,
  `references/global-controls-startup.md`, `references/strategy-alerts-settings.md`
- This issue record.

The branding owner changed exactly two product-label lines in `app.js`, then
released that file to the SPY owner before its behavior edits. SPY source changes
and their evidence are separate from this record.

## Compatibility and installer source

Kept unchanged: the `tradingagents` package/imports and upstream component name;
`tradingagents-desktop` executable, Cargo/npm build target and version;
`com.tradingagents.desktop` production/development identifiers; Windows install
directories and uninstall/manufacturer registry keys; profile paths; private
runtimes; `TradingAgents.desktop.*` vault namespaces; browser-storage keys; export
filenames/formats; API routes; repository URLs; and all approval/submission
controls. No storage migration is needed or added. The macOS display/bundle name
may become Printer without changing its identifier, executable or profile.

Tauri 2.12 normally derives NSIS install/upgrade identity from `productName`.
The supported custom-template configuration now uses the exact pinned upstream
template plus a small compatibility delta, not a parallel installer engine.
`windows/UPSTREAM.md` records tag, source URLs, helpers, license and the change.
The earlier Apps-entry-only hook and incomplete-label exception were removed.

### Exact template delta

The upstream tag is `tauri-cli-v2.12.0`, matching `@tauri-apps/cli` 2.12.0.
Direct comparison with the canonical source found **87 added and 17 removed
lines**, producing a 1,048-line template from 978 source lines (979 split lines
including the terminal empty line).

- Add provenance comments and `LEGACY_PRODUCTNAME=TradingAgents`.
- Use that legacy constant only for uninstall/manufacturer registry keys,
  directory-selector/multiuser defaults and Program Files/LocalAppData paths.
  Keep `PRODUCTNAME` as Printer for every normal display/locale/Apps/new-link use.
- Recognize old and new display names during existing WiX discovery. Keep the
  existing manufacturer derivation, executable name, bundle identifier,
  versions, payload/resources, updater, language-registry and data-deletion
  handling unchanged.
- Extend existing non-update uninstall cleanup to ownership-check, unpin and
  delete either old or new shortcut label. Preserve the outer `/UPDATE` guard.
  Omit upstream's name-only Run-entry cleanup entirely: the desk creates no
  autostart entry and has no ownership evidence for either name. All Run values
  remain untouched during install, update and uninstall.
- In the existing Start menu and desktop functions, rename only an existing
  app-owned legacy link. Reuse upstream `IsShortcutTarget`,
  `SetShortcutTarget`, `SetLnkAppUserModelId` and `UnpinShortcut`; keep ownership
  results in `$R1`/`$R2` because those helpers clobber `$0`–`$5`.
  `$OldMainBinaryName` already includes `.exe`; the current name gets that suffix
  exactly once.
- If the Printer destination is unrelated, or rename fails, preserve the links
  and stop that shortcut operation. Protect new creation from overwriting an
  unrelated existing destination. Missing legacy links are never created by
  the rename helper. Existing `/NS`, `/UPDATE` and WiX creation guards remain,
  so an update does not recreate user-removed links.
- Keep GUI desktop handling in its existing finish-page function; silent
  handling remains in its original location. A post-install-only hook would
  not cover this lifecycle.

### Artifact/helper inspection

The active bundle/build scripts, project refresh/preparation and release metadata
helper contain no hardcoded TradingAgents installer/app artifact glob to change.
The project wheel remains `tradingagents-*.whl`, and repository/release URLs remain
unchanged. The expected Windows app-only artifact is
`Printer_0.6.22_x64-setup.exe`, while the default installed location stays
`%LOCALAPPDATA%\TradingAgents\tradingagents-desktop.exe`; remembered older install
directories remain discoverable through the unchanged keys.

## Validation and limits

Passed static checks:

- `node --check tradingagents/web/static/app.js` after the two branding edits.
- AST parsing of all five changed Python source files, without importing or
  starting application components.
- JSON parsing of the two changed Tauri configuration files.
- Rust syntax parsing of both changed host files through
  `rustfmt --edition 2021 --emit stdout --config skip_children=true`, without
  formatting or modifying them.
- Direct canonical-template comparison and source review of ownership,
  update/no-shortcut guards, registry keys, paths and artifact consumers.
- `git diff --check` and scoped diff review. Git emitted LF-to-CRLF normalization
  warnings, not whitespace errors.

No automated tests were added, changed or run. No mocks, synthetic services,
benchmarks, research reruns, broker actions, credential operations, profile reads,
production changes or app-process management were performed by this owner.
The parent supplied the real screenshot; browser/startup/UAT belongs to the
separate SPY development owner. Native dialogs, recovery, MCP runtime, installer
execution/upgrade/uninstall and macOS build remain unobserved here. The authorized
app-only build belongs to a separate build worker, not this owner.

Change accounting: **1,085 code/config/markup lines added and 35 removed**,
including the full 1,048-line vendored template and the two `app.js` lines handed
off. The local template delta is stated separately above. **0 test lines changed
and 0 tests run.** Documentation/license/image changes are separate from those
code counts. Existing unrelated untracked dependencies are preserved.

## Review record

The independent review requested changes because the initial Apps-entry-only
hook left Windows wizard/shortcut and macOS display names incomplete. The
orchestrator selected global Printer product metadata and the supported pinned
NSIS template with legacy install identity. Those corrections are implemented;
the prior incomplete-label exception is withdrawn.

The correction review also rejected name-only HKCU Run cleanup because the desk
does not create those startup values. That block is removed entirely, with no
registry read and no retained name-only deletion under either product name.

Independent reviewer `66f5800c-32a5-4517-a9ac-77d1ec7aaf5c` gave **SOURCE APPROVE**
after the corrections. All reported source findings are resolved. The reviewed
frozen tracked-diff identity is `65605a2b3433019d1675082ca99d89faee0cf6c2`;
reviewed blob prefixes are installer `0659d311`, app `79e8fc4d` and SPY `62d2b84`.
The complete coordinated source batch is **1,102 lines added and 52 removed**,
including the 1,048-line vendored template, with **0 test changes/runs**.

The source owner handed both shared implementation files to the branding owner,
and the orchestrator granted an exclusive staging/commit turn. The exact task
files are staged together; existing untracked dependency files are excluded.
Build evidence, final UAT scope and the committed revision will be recorded in
the later evidence update. Source/static approval and a package build do not
establish installed-app, broker or full-journey acceptance.
