# Printer product identity

## Scope and status

The user named the whole product **Printer**. **TradingAgents** remains the
research framework/component. This source batch preserves the existing dark
Operate visual system and mark; it is not an aesthetic redesign.

Base revision: `371ead5` on `nautilus` in `D:\src\TradingAgents`.
The complete display rebrand and review corrections were independently approved
and committed as `ffe0fccd4fd25f5cff822fe3d5f18893532bbbd0`. Windows compilation
and custom-template bundling passed; overall release signing is not complete.
Pre-fix visible Edge UAT observed entry, disclosure persistence, real Preview
and filtering. Focus retention, draft expiry and execution remain
unproven. UAT also found a shared rule-heading copy defect; its scoped correction
is committed in `c3abd0bbf51fe703dbe118802242761ba6c1e119` and independently
source-approved. The revised `c3abd0b` app-only build compiled and bundled, but
signing is still incomplete. A post-fix API Preview returned the corrected
closed-session reason; corrected visual Edge acceptance remains unproven. No
production installation or acceptance is claimed.

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

## Windows build observations

### Prior build: `ffe0fcc`

The separate build worker reported the authorized app-only build against frozen
source `ffe0fccd4fd25f5cff822fe3d5f18893532bbbd0`:

- The first attempt failed with compiler error E0463 before bundling.
- Nine scoped `serde_repr` release outputs were regenerated, without source,
  dependency or toolchain changes. The original cause of E0463 was not proven.
- The corrective standard build compiled the app and `makensis` successfully
  produced `Printer_0.6.22_x64-setup.exe`, reported as 23.91 MiB.
- The overall command then exited **1** because `TAURI_SIGNING_PRIVATE_KEY` was
  not supplied while a public updater key is configured.

**Compilation and custom-template bundling: PASS. Overall release signing:
NOT COMPLETE.** This is not an overall successful release-build claim. No key,
key-presence, vault or private-profile inspection, signing retry or installation
was performed. There is no `.sig` output and this is not a completed
updater-signed release.

**Artifact boundary:** the artifacts identified by the hashes below were built
from `ffe0fcc`, before the later `investor.py` rule-heading correction. They do
not include that wording fix and are superseded by the revised installer
identified below. These prior hashes do not prove the revised payload. No
signing-key access is authorized or planned.

Prior-build artifacts reported by the builder:

- Installer:
  `desktop/src-tauri/target/release/bundle/nsis/Printer_0.6.22_x64-setup.exe`
  (25,075,960 bytes). SHA-256:
  `63e727537932cdca2a6d9e0ec766548dc09f33a2b590f6f77c4e967565553f7b`.
- Launcher: `desktop/src-tauri/target/release/tradingagents-desktop.exe`
  (13,440,000 bytes). SHA-256:
  `d5b888205d87c91d27c5f9016a45ae1867bd5c8cf8164cbf44c3376061ae14a0`.
- Both Windows version resources report ProductName and FileDescription
  **Printer**, version **0.6.22**.
- Generated NSIS script SHA-256:
  `05b360e73ca4ac475ea403537234a0f14a6e66f422c7ec68586a4fccb10651df`.
  Its defines use Printer display names and TradingAgents legacy identity, with
  unchanged `com.tradingagents.desktop`, `tradingagents-desktop` and
  `currentUser`. The uninstall key
  `Software\Microsoft\Windows\CurrentVersion\Uninstall\TradingAgents`,
  manufacturer key `Software\tradingagents\TradingAgents` and default directory
  `%LOCALAPPDATA%\TradingAgents` remain unchanged.

The generated app-only resource map contains 306 app entries and one provenance
entry, with no wheel or setup payload. Provenance identifies source `ffe0fcc`;
the builder reported abbreviated provenance hash `36f85359…17c1` and project
wheel hash `e2dc6dea…8d9`. Bundled `app.js`, `spy_rebalance.py` and `index.html` match
committed bytes. Private-runtime and lock inputs were unchanged. The first
E0463 log, scoped-clean log and corrective exit-1 build log remain local and
ignored under `packaging/build`; logs and generated artifacts are not committed.

### Revised build: `c3abd0b`

The separate builder reported successful compilation and NSIS bundling for
`c3abd0bbf51fe703dbe118802242761ba6c1e119`. The standard command again exited
**1** only at the missing private updater-signing key. **Compilation and NSIS
bundling: PASS. Signed release: NOT COMPLETE.** No `.sig` was generated and no
key was touched. This is not an overall successful release-build claim.

Rebuilt installer:

- `desktop/src-tauri/target/release/bundle/nsis/Printer_0.6.22_x64-setup.exe`
  (25,076,140 bytes). SHA-256:
  `5457f3202a09e28c6a958710b4a27c87de98bf43ac708eba2b649cd55ad38292`.
- Actual bundled provenance identifies source
  `c3abd0bbf51fe703dbe118802242761ba6c1e119`. Its SHA-256 is
  `b7fcad155aa8d3886a4158f5a3cfae921298595cddaf768b0b55088970e87762`,
  matching the refreshed provenance.
- Actual bundled project wheel SHA-256:
  `62b80758ebaee4275023c9a1a5d38a5b0457eaa097d3f22edc30a6ae2f2d6f82`.
- Revised main executable SHA-256:
  `95ef6729c5400715d604d9cf234303a0018890bd93b9a2ad12a4430ad5f00f71`.
- Revised generated NSIS script SHA-256:
  `68c34becc418de83bca27d9c166a170aef1725a921023b66b7754509d5fe8982`.

Provenance records `working_changes_present=true`: the two evidence issues and
known untracked dependencies were present during packaging. The builder checked
the actual bundled files against reviewed source:

- `investor.py` SHA-256:
  `d49d98c3218412709e698c08b5b0d16a9165e48316e9bdea8015b407d17a1a6c`.
- `policy_evaluation.py` SHA-256:
  `843315aaf5b3668ae19f2f824ed95581fad6c97552a02967ad83a193d0d67520`.

Both match reviewed source, demonstrating that the wording fix is included in
the revised installer. This is not a clean-worktree provenance claim.

The rebuilt installer was not executed. Its bytes replaced the earlier installer
at the same path. The previous installer hash and wheel hash above are historical
evidence of the superseded `ffe0fcc` build, not the current file.

An installer compiled by NSIS is not evidence that its upgrade, shortcut,
uninstall or runtime behavior has been exercised. Those installed paths and
macOS remain unobserved.

## Development UAT boundary

### Pre-fix visible Edge: `ffe0fcc`

After the built-in pane became unavailable, the parent and SPY UAT owner used a
separate visible Edge window against the isolated development app at source
`ffe0fcc`, before the rule-heading follow-up. The Printer page showed a paper,
reconciled account with zero positions and orders, and automatic trading off.

Observed results:

- The investment budget disclosure stayed open across a natural account
  refresh.
- Real Preview reported State Street weights dated **2026-11-05**, a price check
  on **2026-11-08 at 14:29:51 PST**, **503 stocks / 503 planned trades** and a
  **94.90% target**.
- The AAPL row showed **BUY 21.966418766**, with an **estimated limit of
  342.41 USD**. This is a preview, not a placed order or fill.
- Filtering for AAPL showed **1 / 503**; Clear restored **503 / 503**.
- The header showed **Market closed**. Trading Rules reported a quote-age
  submission block for all 503 rows, and Submit was disabled. Underlying quote
  timestamps were not exposed.
- The real pre-fix policy was enabled, with **180-second open-session and
  closed-session quote limits** and `regular_session_required`. The blocker was
  confirmed to be **regular-session permission**, not proof that all quotes
  were stale.
- The source owner confirmed a UI-copy defect:
  **Maximum open-session quote age** incorrectly labels the shared
  `session_freshness` rule when the market is closed. The scoped correction in
  `investor.py` is **Quote freshness and session permission**. Policy values
  and guards are unchanged. The correction is committed and independently
  source-approved in `c3abd0b`. The later backend-only check below does not prove
  corrected visual wording. The observed block does not establish the underlying
  quote age.

### Post-fix API Preview: `c3abd0b`

The parent reported one actual API Preview after the source correction. The
service was healthy and automatic authority remained off. It returned:

- State Street weights dated **2026-11-05** and a price check at
  **2026-11-08T23:02:07.123732Z**.
- **503 stocks / 503 planned trades**, target **94.9019818500%**.
- AAPL **BUY 21.966418766**, estimated limit **342.41 USD**.
- The exact reason:

> Quote freshness and session permission: The regular market session is closed. This rule requires it to be open. Affected stocks: 503 (AAPL, NVDA, MSFT, AMZN, GOOGL, …).

No submission token was present. This is **backend-only evidence**, not proof
that the corrected page rendered or its Submit button was disabled.

The old external Edge window was gone. One new isolated launch presented an
uncertain personal-profile/unrelated-page context and was left untouched. No
further windows were attempted. The prior pre-fix visible Edge journey remains
separate evidence; it does not prove the corrected page.

### Remaining limits

**Focus retention remains unresolved**: native Windows denied foreground
activation and UI Automation `SetFocus` failed. This does not prove a product
defect. Draft expiry, final fills, live broker execution, signed updates,
installer execution/upgrade/uninstall and macOS remain unproven.

No broker order, order approval, submission or trade was performed. The
coordinated SPY issue records the detailed observations. These results replace
the earlier pane-control boundary; they do not establish full-journey
acceptance.

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
after the original corrections. All findings from that review were resolved in
`ffe0fcc`; it does not approve the later UAT-discovered rule-heading correction.
The reviewed frozen tracked-diff identity is
`65605a2b3433019d1675082ca99d89faee0cf6c2`;
reviewed blob prefixes are installer `0659d311`, app `79e8fc4d` and SPY `62d2b84`.
The coordinated source batch in `ffe0fcc` is **1,102 lines added and 52 removed**,
including the 1,048-line vendored template, with **0 test changes/runs**.

The heading-only follow-up was committed separately as
`c3abd0bbf51fe703dbe118802242761ba6c1e119` (two files, three lines added and one
removed). Focused independent source review gave **APPROVE**, with **no
findings**, against diff identity `457fae07f5804fb28952c9894e000beb6e18bf1e`.
This approves the source correction, not replacement visual UAT or a completed
signed release. Revised compilation/bundling and the post-fix API result are
recorded separately above; corrected visual Edge acceptance remains unproven.

The source owner handed both shared implementation files to the branding owner,
and the orchestrator granted an exclusive staging/commit turn. Exactly 33 task
files were committed locally in `ffe0fccd4fd25f5cff822fe3d5f18893532bbbd0`,
with the required coauthor and no push. The post-commit index and tracked tree
were clean; all 51 pre-existing untracked dependency files remained excluded.
This branding-issue follow-up is documentation only. The separate shared
rule-heading correction is committed and source-approved, with revised compiled
installer provenance recorded separately from the prior build. The post-fix API
reason is verified; corrected visual Edge acceptance remains unproven and
release signing is incomplete.
Source/static approval and compilation/bundling do not establish installed-app,
broker or full-journey acceptance.
