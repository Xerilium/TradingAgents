# Tauri NSIS installer template

`installer.nsi` is vendored from Tauri's `tauri-cli-v2.12.0` tag, matching the
desktop's pinned `@tauri-apps/cli` 2.12.0. Its original template is 979 lines.

- [Canonical template](https://github.com/tauri-apps/tauri/blob/tauri-cli-v2.12.0/crates/tauri-bundler/src/bundle/windows/nsis/installer.nsi)
- [Ownership and shortcut helpers](https://github.com/tauri-apps/tauri/blob/tauri-cli-v2.12.0/crates/tauri-bundler/src/bundle/windows/nsis/utils.nsh)
- [Upstream MIT license](https://github.com/tauri-apps/tauri/blob/tauri-cli-v2.12.0/LICENSE-MIT), reproduced in `LICENSE-MIT`.

Local changes are limited to the Printer name transition:

- Keep `LEGACY_PRODUCTNAME=TradingAgents` for existing uninstall/manufacturer
  registry keys, default install paths and directory-selection defaults.
  `PRODUCTNAME` remains the configured display name, Printer.
- Recognize both display names for old WiX discovery.
- Omit upstream's name-only Run-entry cleanup: the desk creates no autostart
  entry and has no ownership evidence for either name. Leave all Run values
  untouched during installation, updates and uninstall.
- Rename only existing app-owned legacy shortcuts, using Tauri's exact
  `IsShortcutTarget`, `SetShortcutTarget`, `SetLnkAppUserModelId` and
  `UnpinShortcut` helpers. Keep `/NS`, `/UPDATE`, absent user-removed links and
  unrelated shortcut destinations intact. Remove either owned label only on
  ordinary uninstall, not during an update.

The bundled `utils.nsh`, standard language files, resource handling, updater,
process checks, app identifiers, executable name and profile handling remain
Tauri's normal implementation. When updating the CLI, rebase this small delta
onto that release's exact template and re-review upgrade/shortcut semantics.
