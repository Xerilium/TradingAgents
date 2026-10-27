# Native credential storage

Status: source investigation complete; implementation follows the requested
upstream integration. No credential values have been printed or changed.

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

The native runtime currently checks for a credentials file and passes that path
to its worker. The server, package bootstrap, Alpaca account reader and history
collector also load credentials from files. They need one shared credential
interface. Provider and data-feed keys are consumed from process environment.

The Codex-launched standalone Python resolves the expected production AppData
credentials path into Codex's private package LocalCache, without a symlink.
Thus a successful read from a tool-launched interpreter does not establish what
a normal desktop-launched consumer can read. A standalone interpreter alone
does not eliminate the parent process's package virtualization context.

The live desk currently reports a missing-file error, 503 configured stocks
and no research runs. Preserve that active configuration and all older profiles;
do not overwrite it with an older shadow profile to clear the startup error.

## Source

- `tradingagents/web/nautilus_runtime.py`, `server.py`, `alpaca_readonly.py`,
  `market_history.py`, `service.py`, `tradingagents/__init__.py` and desktop host.
- Primary file-metadata and live API observations, 27 October 2026.
- https://keyring.readthedocs.io/en/stable/
- https://learn.microsoft.com/en-us/windows/msix/desktop/flexible-virtualization
