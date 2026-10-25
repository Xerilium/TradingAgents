# Startup and global controls

## Contents

- [Global header and navigation](#global-header-and-navigation)
- [Workspace save status](#workspace-save-status)
- [Startup and runtime status](#startup-and-runtime-status)
- [Errors and retries](#error-and-read-controls)
- [Application recovery](#application-recovery-page)
- [Coverage and limits](#coverage-evidence-and-limits)

This reference is for assistant-led tutorials in the local TradingAgents desk. Use the internal browser at `http://127.0.0.1:8098/`. The normal launcher is `rtk proxy .\Start-TradingDesk.cmd`; do not start the server directly or use another port. The launcher uses `tradingdesk.launch.json`, checks the configured identity and port, and reuses the expected installation. Normal server startup starts Nautilus and starts the configured installed loopback Maenifold service if unavailable. Laya loads in the background. Codex starts its adapter when research needs it. Startup is asynchronous: an initial stopped/unverified display can precede connection. Browse-only and recovery modes do not start the native connection. Check Account and Diagnostics before declaring startup failed. Read saved provider and account settings before describing active configuration.

## Global header and navigation

The shell renders page navigation and the account/session header in `tradingagents/web/static/app.js:334` and surrounding `renderChrome` code. Navigation includes Dashboard, Portfolio, Markets, Research, Orders, Strategy lab, Journal, Alerts, and Settings. The global header includes the observed account mode and account identity, universe, current page, **Find a symbol**, market session and snapshot time, and **Refresh** and **Alt+R** use the same button handler. If connected, it calls refreshQuotes() and POSTs /api/quotes/refresh, then reads updated state. If disconnected, it calls /api/refresh. DeskService.refresh() calls runtime.start() and returns state; this is a reconnect/start action, not a quote refresh. While busy, the button is disabled and reads **Refreshing…**. Quote refresh errors show **Quote update failed:** and the error. A cooldown, hidden page, or another busy request can prevent a quote refresh. Focus in INPUT, TEXTAREA, or SELECT blocks Alt+R. Source: button/keyboard bindings in app.js:1291–1293; refreshQuotes() at :23–43; /api/refresh route in server.py:364–365; DeskService.refresh() in service.py:2104–2107.

**Find a symbol** uses a datalist of current market symbols. On change, the input is trimmed and uppercased. Only an exact symbol from the loaded market-symbol list is accepted; another string leaves the view unchanged. A valid symbol opens Markets → Stock review for that symbol. It does not change the research batch. Source: `index.html:41–42`, `app.js:412–413`, `505–506`.

The global notice area shows the current app/API error first. A quote-refresh error tells you to use **Refresh** again when connected, or to reconnect Nautilus in Settings → Account when disconnected; automatic quote retry waits until connected. With no error, it can show account-connection unavailable or account not verified. On Orders only, it can show the active order-pause block or review-only boundary. **Dismiss error** hides the current app error; it does not correct the cause. Source: `renderNotice()` in `app.js:233`.

Keyboard: **Alt+R** invokes the same Refresh button unless focus is in INPUT, TEXTAREA or SELECT. No other global keyboard shortcut or help dialog is declared in the shell source reviewed.

To check the runtime, open **Settings → Account**. Read observed mode/account and use the persistent Nautilus start/stop controls only when needed. **Settings → Diagnostics** shows **Health and recovery**, current or last-observed engine and account-import state, startup errors, local store status, and recovery controls. Its **Connection controls** button returns to Account. These controls change runtime state. Do not activate them during a read-only walkthrough.



The header pause control **New orders not paused · manage** / **New orders paused · manage** navigates to Orders and focuses account order controls. It does not toggle pause directly. Pause and resume are consequential workspace controls and do not cancel existing broker orders. Do not activate them during a read-only tutorial. Source: `app.js:1289`; Orders behavior in `references/portfolio-orders-journal.md`.

Search, pagination, sort, filters, tabs, disclosures, symbol inspection, and page size change the displayed view. The app also saves some view preferences in browser local storage through persistView() in tradingagents/web/static/app.js:137; this is separate from the server workspace. Check the page reference for each action's actual boundary. A button that says Load may read retained definitions or data; inspect its handler before treating it as safe. Do not assume that Preview, Save, Run, Collect, Import, Export, Enable, Retry, Capture, Approve, Submit, Cancel, Stop, or Restore is read-only.

## Workspace save status

Markets and chart workspace edits use a separate server save path. The status reads **All changes saved**, **Unsaved workspace changes**, **Saving workspace…**, or the returned error. queueWorkspace() in app.js:2064–2067 starts a save 450 ms after an edit. writeWorkspace() at app.js:2080–2091 sends the expected workspace revision.

On an ordinary save error, **Retry save** retries the pending change. On a revision conflict, retry is hidden because another revision changed. **Reload saved workspace (discard unsaved edits)** reads the saved server copy and discards current workspace edits, notes and drawings. Browser `persistView()` preferences and server `UniverseReview.persistPreferences()` preferences are different paths. Markets search, sort, selected watchlist, columns, instrument/chart selection and playback can queue a server workspace save even when the action only changes the view. Navigation can therefore show Saving workspace… or advance an internal revision. This does not imply a new research result or a broker change. Do not promise that all view changes are browser-only. Do not use Retry or Reload to reveal a status during a walkthrough.

## Startup and runtime status

The canonical start command is `rtk proxy .\Start-TradingDesk.cmd`. Do not wrap it, patch it, or start an alternate server. The local UI port is 8098. Use existing environments and the configured data paths from `tradingdesk.launch.json`. Do not migrate data to start the desk.

Settings → Account and Diagnostics report observed runtime status. The launcher starts Nautilus in normal mode; the observed connected account is the evidence for active account identity. A configured paper/live mode alone does not prove which account is connected. A stop or restart changes native runtime state and can require fresh reconciliation. Read the current view before you explain recovery.

## Source map

- tradingagents/web/static/app.js: page shell, global navigation/header, local view persistence, refresh binding, keyboard shortcut, and server workspace save status.
- tradingagents/web/static/nautilus.js: native status and account/runtime panel rendering.
- tradingagents/web/static/index.html: main page landmarks and global control containers.
- tradingagents/web/server.py and service.py: HTTP refresh routes and runtime service action.
- tradingdesk.launch.json and Start-TradingDesk.cmd: configured startup paths and launcher behavior.

## Error and read controls

| Control | What it does |
| --- | --- |
| **Try again** | Reads application state again after the initial state request fails. It is not a research retry. |
| **Retry this read-only request** | Rereads the Dashboard’s retained market evidence for the selected stock/run through `ensureChart(true)`. It does not start research. |
| **Try loading reports again** / **Refresh this report** | Reads the selected saved report again. A previous revision can stay visible while the newer one loads. |
| **Retry saved source** / **Retry saved data** | Rereads the selected retained artifact. It does not collect a replacement from a provider. |
| **Refresh broker data** / **Connect or refresh account** | Invokes the global Refresh button. Connected: requests quote refresh. Disconnected: calls the runtime reconnect/start path. Use the separate account/order refresh control for command reconciliation. |
| **Refresh account and order status** | Reconciles current broker orders and account facts; it does not grant an approval or resend a command. |
| **Data source diagnostics** | Expands recorded data-source errors. |
| **Research settings** / **Configure research** | Opens Settings when the provider is not ready. Check the selected category before editing. |
| **Dismiss error** | Clears the displayed app error only. |
| **NOTICE**, **License**, **TradingView**, source/document links | Open attribution or external source material. They do not validate the analysis or change order authority. |

A request can be blocked while another action is busy, the page is hidden, or a rate-limit cooldown applies. Read the displayed reason. Do not start a second run to recover a failed read.

## Application recovery page

If the journal cannot load, the server can show **Application recovery** instead of the nine workspaces. Engine, research and data workers stay stopped. This is a conditional source-only screen; do not induce corruption to demonstrate it.

- **Backup ZIP · maximum 64 MiB** selects an existing local application backup.
- **Inspect archive** uploads it to the local recovery service for validation and shows its manifest/checksum. Current records do not change at inspection.
- **Type RESTORE LOCAL RECORDS** is the required exact confirmation.
- **Restore inspected local records** stays disabled until inspection succeeds and the phrase matches. It writes a separate recovery generation. A promoted store reloads the page; a restart-required result stops further recovery actions until restart.
- The health block and status message show the actual outcome. They do not prove broker reconciliation. Restore is a separate user-authorized operation; do not use it for a tutorial.

Source: `tradingagents/web/static/recovery.html`, `recovery.js`, `tradingagents/web/recovery_mode.py`; normal recovery controls are in the Settings reference.

## Coverage evidence and limits

Source reviewed against local `nautilus` commit `b632a22` on 2026-10-25. The current review uses the internal browser and current handlers. The page references state which views were observed and which conditional effects remain source-only. Earlier screenshots and worker reports are historical evidence, not acceptance of the current product.

Read-only navigation can save view preferences. No research, calculation, collection, authored record, settings save, import/export, notification, backup/restore or broker action is required to inspect these controls.
