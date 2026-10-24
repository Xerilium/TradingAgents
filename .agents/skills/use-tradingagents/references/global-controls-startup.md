# Startup and global controls

## Contents

- [Global header and navigation](#global-header-and-navigation)
- [Workspace save status](#workspace-save-status)
- [Startup and runtime status](#startup-and-runtime-status)
- [Coverage and limits](#coverage-evidence-and-limits)

This reference is for assistant-led tutorials in the local TradingAgents desk. Use the internal browser at `http://127.0.0.1:8098/`. The normal launcher is `rtk proxy .\Start-TradingDesk.cmd`; do not start the server directly or use another port. The launcher uses `tradingdesk.launch.json`, checks the configured identity and port, and reuses the expected installation. Startup starts Nautilus in normal mode. Laya loads automatically. Codex loads only when requested. Read saved provider and account settings before describing active configuration.

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

On an ordinary save error, **Retry save** retries the pending change. On a revision conflict, retry is hidden because another revision changed. **Reload saved workspace (discard unsaved edits)** reads the saved server copy and discards current workspace edits, notes and drawings. A read-only view preference in local storage is not a workspace edit. Do not use Retry or Reload to reveal a status during a walkthrough.

## Startup and runtime status

The canonical start command is `rtk proxy .\Start-TradingDesk.cmd`. Do not wrap it, patch it, or start an alternate server. The local UI port is 8098. Use existing environments and the configured data paths from `tradingdesk.launch.json`. Do not migrate data to start the desk.

Settings → Account and Diagnostics report observed runtime status. The launcher starts Nautilus in normal mode; the observed connected account is the evidence for active account identity. A configured paper/live mode alone does not prove which account is connected. A stop or restart changes native runtime state and can require fresh reconciliation. Read the current view before you explain recovery.

## Source map

- tradingagents/web/static/app.js: page shell, global navigation/header, local view persistence, refresh binding, keyboard shortcut, and server workspace save status.
- tradingagents/web/static/nautilus.js: native status and account/runtime panel rendering.
- tradingagents/web/static/index.html: main page landmarks and global control containers.
- tradingagents/web/server.py and service.py: HTTP refresh routes and runtime service action.
- tradingdesk.launch.json and Start-TradingDesk.cmd: configured startup paths and launcher behavior.

## Coverage evidence and limits

I used a fresh internal-browser tab at `http://127.0.0.1:8098/` on 2026-10-24. The app was already running. In my pass, I opened Dashboard, Markets, and Research with navigation links. I did not open the other page references or retained definitions. I did not save a setting or workspace edit. I did not run research, collect provider data, simulate, experiment, calculate a chart, export, import, send notifications, capture native cache, back up, restore, approve, submit, cancel, or replace an order.

Coverage map:

- `markets-research.md`: source describes Dashboard, Markets, instrument, chart, and Research paths. My live pass observed Dashboard, Watchlists, and Research latest results. Root’s later pass observed Markets Universe, Screener, Saved scans, META’s Chart/Options/Position/Research, all chart inspectors, and the Research tabs plus workload-review dialog. Conditional result states and side-effect paths remain source-only.
- `portfolio-orders-journal.md`: Portfolio tabs; Orders tabs and source-only ticket/approval/basket paths; Journal tabs and available detail views. Empty history/position states limit live evidence for populated result rows.
- `strategy-alerts-settings.md`: Strategy lab tabs and definitions; Alerts tabs; Settings categories and disclosures. Simulation and experiment results and other conditional states are source-only.

These observations establish visible labels and current states only. They do not prove financial calculations, model outcomes, provider reliability, notifications, or broker execution. Source references establish implemented paths, not live acceptance. Current empty or populated states can change.

## Global control coverage

The shell has an order-preview dialog and a Research workload-review dialog in `index.html:63–70`. See the Orders reference for the order dialog. Research opens its workload dialog first; **Close research workload review** cancels before admission, and only **Start N-stock research** posts the run request (`reviewResearch()` and `launchResearch()` in `app.js:140–141`, click handler at `1281`).

Source-confirmed shell controls:

- `renderChrome` in `tradingagents/web/static/app.js:334` renders the navigation rail, active-page label, universe, market/session snapshot, connection status, order-pause status, and Orders readiness banner.
- `togglePause` at `app.js:1289` is the header **… · manage** action. It only navigates to Orders and focuses **Account order controls**. It does not pause or resume orders.
- `persistView` at `app.js:137` saves selected view state in browser local storage. This includes list views, research selection, inspected symbol, selected run/report, research tab, and sort. Read-only navigation can therefore persist a view preference. It does not save a research setting or workspace edit.
- `renderChrome` can show an Orders count for pending, proposed, or ready proposals. The Orders-only readiness banner shows reasons and states that the server checks again at Submit.
- The **Skip to workspace** link is present in the live Dashboard accessibility tree. **Alt+R** is documented by the refresh handler; the key handler ignores editable fields.

Live observations on 2026-10-24: I opened Dashboard, Markets, and Research. Dashboard showed the left rail, account mode and ID, **New orders not paused · manage**, **Find a symbol**, **Market closed · Snapshot**, **Refresh**, account values, Dashboard panel toggles, the FANGMAN watch table, search, filter, selection, sort buttons, source/time disclosures, page size, and disabled previous/next paging. The view showed a verified account, $100,000.00 equity/cash/buying power, no open orders, seven configured stocks, and seven research selections. These values are time-bound observations. Markets showed the Watchlists, Universe, Screener, and Saved scans tabs, current Watchlists content, an Unsaved workspace changes notice, and stock-list controls. Research showed the latest-results list, Completed status, search and scope controls, batch progress, detail tabs, and populated AAPL Debate. The companion draft records exact visible controls. These values can change.

Root’s additional read-only observation on 2026-10-24 covered Universe filters/list actions; Screener and saved criteria; Saved scans Definition/Advanced JSON/collection consent/scheduling/import-export/history/slots/details with empty Runs and Matches; and META Chart, Options, Position, and Research. Root opened the Research workload-review dialog, read the 7-stock selection, concurrency, model tiers, NY trade date, duration estimate, unavailable cost estimate and usage-limit warning, then closed it without Start. The separate markets-research reference lists its labels and states. No save, data request, run, calculation, subscription, or order action was triggered.

Not observed live: the **Alt+R** key action; disconnected refresh; quote cooldown/error outcomes; pause/resume; workspace retry/conflict notices; error branches in dialogs; and research admission after **Start**. These remain source-only. No provider collection or calculation occurred.
