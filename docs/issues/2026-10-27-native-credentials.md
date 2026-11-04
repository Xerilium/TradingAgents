# Native credential storage

Status: Windows 0.6.2 built, installed and verified through the real local API
and one affected Settings browser cycle. Existing keys were saved to the native
store without printing values. macOS support has not been run on a Mac.

## Required behavior

- Manage application API credentials in Settings using Windows Credential
  Manager and macOS Keychain through an existing library.
- Explicitly select a native backend; do not fall back to plaintext storage.
- Keep production and development credential namespaces separate.
- Return status only. Never send stored secrets back to the browser, application
  state, logs, command-line arguments, reports or backups.
- Preserve the running native session's pinned account and endpoint. Saving
  credentials does not connect or authorize a trade; reconnect is separate.
- Migrate only this app's known existing credentials deliberately. Preserve
  source files until native-store readback is verified; do not delete unrelated
  files or reset user settings and research.

## Findings

The former desktop startup required a credentials file. The desktop host,
server, package bootstrap, Alpaca account reader, native worker and history
collector now use a shared native credential store. The worker receives only
the profile name and pins one immutable account configuration per session.
Provider keys are loaded into process environment from the native store.

Settings has separate credential forms. API responses expose availability and
configured flags, not secrets. Credential mutations are serialized. Unsaved
credential fields have navigation guards; saving does not reconnect Nautilus.
Both private runtime dependency sets include keyring 25.7.0. Windows uses its
native vault backend; macOS uses Keychain. No plaintext fallback is selected.
Static Python/JavaScript syntax and whitespace checks passed. No tests or
research reruns were added or run. macOS runtime behavior is not yet observed.

The Codex-launched standalone Python resolves the expected production AppData
credentials path into Codex's private package LocalCache, without a symlink.
Thus a successful read from a tool-launched interpreter does not establish what
a normal desktop-launched consumer can read. A standalone interpreter alone
does not eliminate the parent process's package virtualization context.

Before the update, the live desk reported a missing-file error, 503 configured
stocks and no research runs. All source and profile copies were retained;
none was restored over another to clear that error.

## Installed Windows evidence

- Signed updater artifact: `TradingAgents_0.6.2_x64-setup.exe`, 389,599,254 bytes;
  SHA-256 `bd5675059c0dc4f818aa8695677e24fd91e1990cb5167a6e6a2e9ed6ea6c4c14`.
  The update feed remains unpublished; this was a local installation.
- The update ran through the Windows shell with no native UI or mouse control.
  Its two private runtimes contain framework 0.7.1 and the reviewed credential
  sources. Production `/api/credentials` reports Windows Credential Manager
  available. Existing Alpaca paper, OpenAI-compatible, FRED and Typesafe keys
  were transferred in memory through the normal session and CSRF checks.
- Explicit Nautilus Start authenticated the existing paper account. The actual
  Settings UI shows Account verified, saved key ID/secret and Nautilus 1.231.0
  connected. Integrations shows saved service keys and an empty password input;
  selecting FRED enables its Remove action. Save/remove API persistence was
  exercised by migration; destructive removal was not exercised.
- Screenshot: `native-credentials-windows-20261027.png` in the session's existing
  visualization evidence folder. No automated tests or research runs occurred.
- The updated consumer reports FAANGMAN + Semiconductors, 516 symbols and saved
  research, unlike the earlier 503-symbol/empty snapshot. The application
  identity hash is unchanged, but it hashes a path string and does not prove
  physical-file continuity under MSIX virtualization. Source review found no
  automatic startup list merge. The difference is not attributed to credential
  migration; no settings or store was overwritten to reconcile the snapshots.
- macOS native Keychain code and dependency locks are included; Mac execution,
  updater publication and an end-to-end downloaded update remain unverified.

## Source

- `tradingagents/web/nautilus_runtime.py`, `server.py`, `alpaca_readonly.py`,
  `market_history.py`, `service.py`, `tradingagents/__init__.py` and desktop host.
- Primary file-metadata and live API observations, 27 October 2026.
- https://keyring.readthedocs.io/en/stable/
- https://learn.microsoft.com/en-us/windows/msix/desktop/flexible-virtualization
