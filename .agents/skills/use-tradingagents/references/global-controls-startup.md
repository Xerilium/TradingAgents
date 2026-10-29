# Startup and global controls

## Contents

- [Global header and navigation](#global-header-and-navigation)
- [Workspace save status](#workspace-save-status)
- [Startup and runtime status](#startup-and-runtime-status)
- [Errors and retries](#error-and-read-controls)
- [Application recovery](#application-recovery-page)
- [Coverage and limits](#coverage-evidence-and-limits)

This reference is for assistant-led tutorials in the local TradingAgents desk. Use the internal browser at `http://127.0.0.1:8098/`, the installed production app. The production app is the Tauri desktop shell at `%LOCALAPPDATA%\Programs\TradingAgents\tradingagents-desktop.exe`. Open it from the desktop or Start menu shortcut, or with `.\Start-TradingDesk.cmd`, which only starts that installed executable (it exits with “Install TradingAgents before using this launcher.” if the file is missing). The app stays in the system tray after the browser closes. The tray offers **Open**, **Restart**, **Check for updates**, **Open logs** and **Quit**. Do not start the server directly or use another port. Development is separate: `.\Start-TradingDesk-Dev.cmd` runs Tauri dev on port 8099 with its own profile (`%USERPROFILE%\.cache\trader\development`) and its own credential entries. Do not use the dev instance to inspect production state.

Normal server startup starts Nautilus from the saved settings and starts the configured installed Maenifold service if it is unavailable. Laya loads in the background. Codex starts its adapter when research needs it. Startup is asynchronous: an initial stopped/unverified display can precede connection. Browse-only and recovery modes do not start the native connection. Check Account and Diagnostics before declaring startup failed. Read saved provider and account settings before describing active configuration. The old `tradingdesk.launch.json` and `Launch-TradingDesk.py` are not the installed app’s launch path.

## Global header and navigation

The shell is defined in `index.html` and drawn by `renderChrome()`, `renderNotice()` and `renderConnectionIdentity()` in `app.js`. The shell has a left sidebar and a top bar.

- **Sidebar navigation** (`workspaceLabels` in `app.js`): ten workspaces — Dashboard (`#overview`), Portfolio, Markets, Research, Orders, Strategy lab (`#strategy`), Journal, Alerts, **Workflows** and Settings. The Orders link shows a count of pending, proposed or ready order proposals. Links are hash routes such as `#workflows`. Leaving Workflows with unsaved edits asks **Discard unsaved workflow changes?**. Leaving Settings with an unsaved credential entry asks **Discard unsaved credential changes?**. Declining keeps you on the page.
- **Sidebar footer**: account identity (**Paper trading**, **Live trading** or **Account unverified**, with the observed account id and **Connected** / **Connection unconfirmed**), the pause-management button (see below), gateway status (**Nautilus connected**, **Nautilus stopped / disconnected** or **Connection unconfirmed · last snapshot**) and `TradingAgents + maenifold`.
- **Top bar**: the universe name and current page, **Find a symbol**, the market session and snapshot time text (for example “Market open · Snapshot …”, “Market closed” or “Market status unknown”; “No account snapshot” when none exists), and **Refresh**.

**Refresh** and **Alt+R** use the same button handler. If connected, it calls `refreshQuotes({manual:true})`, which POSTs `/api/quotes/refresh`, then reads updated state. If disconnected, it POSTs `/api/refresh`. `DeskService.refresh()` in `service.py` calls `runtime.start()` and returns state; this is a reconnect/start action, not a quote refresh. While busy, the button is disabled and reads **Refreshing…**; it is also disabled during a rate-limit cooldown. Quote refresh errors show **Quote update failed:** and the error. A cooldown, hidden page, or another busy request can prevent a quote refresh. Focus in INPUT, TEXTAREA, or SELECT blocks Alt+R. Source: the `#refresh` click and `keydown` bindings near the end of `app.js`; `refreshQuotes()`; the `/api/refresh` and `/api/quotes/refresh` routes in `server.py`; `DeskService.refresh()` in `service.py`.

**Find a symbol** uses a datalist of current market symbols. On change, the input is trimmed and uppercased. Only an exact symbol from the loaded market-symbol list is accepted; another string leaves the view unchanged. A valid committed symbol change opens Markets → Stock review for that symbol (via `UniverseReview.openTicker`). From Settings it first applies the credential-draft discard prompt. In the 25 October internal-browser check, native typing of META followed by Tab opened META; filling text alone did not commit the change. When automating this control, type the actual code and commit it with Tab, then inspect the resulting stock heading. Do not inject a custom change event. The input keeps the last typed lookup text; it need not match a stock selected later elsewhere. In the browser check it still showed META while Dashboard displayed the subsequently selected AAPL. Confirm the selected stock from the panel heading. Lookup does not change the research batch. Source: the `#context-symbol` markup in `index.html` and its `change` listener in `app.js`.

The global notice area shows the current app/API error first. A quote-refresh error tells you to use **Refresh** again when connected, or to reconnect Nautilus in Settings → Account when disconnected; automatic quote retry waits until connected. With no error, it can show account-connection unavailable or account not verified. On Orders only, it can show the active order-pause block or review-only boundary. The **×** button (accessible name **Dismiss error**) hides the current app error; it does not correct the cause. A separate order-readiness line (`#order-status`) under the top bar states whether an order can be approved or submitted. Source: `renderNotice()` in `app.js`.

Keyboard: **Alt+R** invokes the same Refresh button unless focus is in INPUT, TEXTAREA or SELECT. No other global keyboard shortcut or help dialog is declared in the shell source reviewed.

To check the runtime, open **Settings → Account**. Read observed mode/account and use the persistent Nautilus start/stop controls only when needed. **Settings → Diagnostics** shows **Health and recovery**, current or last-observed engine and account-import state, startup errors, local store status, and recovery controls. Its **Connection controls** button returns to Account. These controls change runtime state. Do not activate them during a read-only walkthrough.



The sidebar pause control **New orders not paused · manage** / **New orders paused · manage** (`#pause-trading`, handler `togglePause()`) navigates to Orders and attempts to focus the account order controls (`#account-order-controls`, heading **Pause new orders**). It does not toggle pause directly. **Observed limitation:** an already-open stock ticket can remain open and hide the pause controls. Use **Back to universe**, then **Orders → Drafts** if needed, to expose them. In the 25 October check the pause button became visible after closing the ticket, and the control kept the label **New orders not paused · manage** throughout. The separate **Pause new orders** and **Resume new orders** buttons (rendered in `command-controls.js`, route `/api/trading/pause`) change the account order gate; Manage only opens the controls. Pause and resume do not cancel existing broker orders. Do not activate those state-changing buttons during a read-only tutorial. Source: `togglePause()` in `app.js`; `command-controls.js`; Orders behavior in `references/portfolio-orders-journal.md`.

Search, pagination, sort, filters, tabs, disclosures, symbol inspection, and page size change the displayed view. The app also saves some view preferences in browser local storage (key `paper-desk-view`) through `persistView()` in `tradingagents/web/static/app.js`; this is separate from the server workspace. Check the page reference for each action's actual boundary. A button that says Load may read retained definitions or data; inspect its handler before treating it as safe. Do not assume that Preview, Save, Run, Collect, Import, Export, Enable, Retry, Capture, Approve, Submit, Cancel, Stop, or Restore is read-only.

## Workspace save status

Markets and chart workspace edits use a separate server save path (`/api/workspace`). The status reads **All changes saved**, **Unsaved workspace changes**, **Saving workspace…**, or the returned error. `queueWorkspace()` in `app.js` starts a save 450 ms after an edit. `writeWorkspace()` sends the expected workspace revision. Workflows (`/api/workflows`) and Settings (`/api/config`, `/api/credentials`) save through their own explicit buttons, not this auto-save path.

On an ordinary save error, **Retry save** retries the pending change. On a revision conflict, retry is hidden because another revision changed. **Reload saved workspace (discard unsaved edits)** reads the saved server copy and discards current workspace edits, notes and drawings. Browser `persistView()` preferences and server `UniverseReview.persistPreferences()` preferences are different paths. Markets search, sort, selected watchlist, columns, instrument/chart selection can queue a server workspace save even when the action only changes the view. Navigation can therefore show Saving workspace… or advance an internal revision. This does not imply a new research result or a broker change. Do not promise that all view changes are browser-only. Do not use Retry or Reload to reveal a status during a walkthrough.

## Startup and runtime status

The canonical production start is the installed desktop app (tray or Start menu shortcut; `.\Start-TradingDesk.cmd` opens the same executable). Do not wrap it, patch it, or start an alternate server. The local UI port is 8098. The installed app uses its private runtimes and the production profile under `%USERPROFILE%\.cache\trader\production`; its desk log is `logs\desk.log` there (tray **Open logs**). Do not migrate data to start the desk.

Settings → Account and Diagnostics report observed runtime status. The launcher starts Nautilus in normal mode; the observed connected account is the evidence for active account identity. A configured paper/live mode alone does not prove which account is connected. A stop or restart changes native runtime state and can require fresh reconciliation. Read the current view before you explain recovery.

## Source map

- tradingagents/web/static/app.js: page shell (`workspaceLabels`, `renderChrome()`, `renderNotice()`), global navigation/header, local view persistence, refresh binding, keyboard shortcut, and server workspace save status.
- tradingagents/web/static/workflows.js: the Workflows workspace (`renderWorkflows()`, `/api/workflows`); see `references/workflows.md`.
- tradingagents/web/static/nautilus.js: native status and account/runtime panel rendering.
- tradingagents/web/static/command-controls.js: pause/resume new orders, approval and reconciliation controls.
- tradingagents/web/static/index.html: main page landmarks and global control containers.
- tradingagents/web/server.py and service.py: HTTP refresh routes and runtime service action.
- Start-TradingDesk.cmd, Start-TradingDesk-Dev.cmd and desktop/src-tauri: production and development launch (installed Tauri app; dev on port 8099).

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
| **Dismiss error** (the **×** button) | Clears the displayed app error only. |
| **NOTICE**, **License**, **TradingView**, source/document links | Open attribution or external source material. They do not validate the analysis or change order authority. |

A request can be blocked while another action is busy, the page is hidden, or a rate-limit cooldown applies. Read the displayed reason. Do not start a second run to recover a failed read.

## Application recovery page

If the journal cannot load, the server can show **Application recovery** instead of the ten workspaces. Engine, research and data workers stay stopped. This is a conditional source-only screen; do not induce corruption to demonstrate it.

- **Backup ZIP · maximum 64 MiB** selects an existing local application backup.
- **Inspect archive** uploads it to the local recovery service for validation and shows its manifest/checksum. Current records do not change at inspection.
- **Type RESTORE LOCAL RECORDS** is the required exact confirmation.
- **Restore inspected local records** stays disabled until inspection succeeds and the phrase matches. It writes a separate recovery generation. A promoted store reloads the page; a restart-required result stops further recovery actions until restart.
- The health block and status message show the actual outcome. They do not prove broker reconciliation. Restore needs a user-authorized recovery task for the exact inspected archive; it is not incidental tutorial navigation.

Source: `tradingagents/web/static/recovery.html`, `recovery.js`, `tradingagents/web/recovery_mode.py`; normal recovery controls are in the Settings reference.

## Coverage evidence and limits

### Requirement audit · 25 October 2026 (historical)

This is a control guide review, not certification that every product workflow works. It predates the Workflows workspace, the native credential vault controls, the Deep/Fast token budgets and the removal of chart playback (commits after `b632a22`, including `9c0e0c8`, `aad6d37`, `9aa4bb1`, `f663fd4` and `ea82136`). The 28 October 2026 source audit re-checked the shell, Workflows and Settings text against the code and the live read-only API only; it did not re-run the browser checks in the table below. The references cover the following control groups, their choices, prerequisites, draft/save/request boundaries and result meanings. Later dated observations supersede earlier empty states only for the checked path.

| Area | Documentation and observed checks | Runtime limits |
| --- | --- | --- |
| Shared shell | Nine workspace links at the time (ten now, with Workflows), header lookup, refresh, pause-management route, save/error states and recovery controls. Lookup and management navigation checked. | Reconnect failure, pause changes and recovery cutover not induced. |
| Dashboard | Account/panel meanings, watchlist filters, columns, selection, pagination, ticker selection, report/data retry and Open instrument route. | No holding row exists in this account. |
| Markets | Four tabs; list/screener/scan forms; instrument Chart/Research/Options/Position; five chart inspectors and conditional editors. One retained-input chart calculation and one real option page checked. | Collection, scheduling, drawing saves and option subscriptions remain source-traced where stated. |
| Research | Selection versus inspection, six detail tabs, report/debate/source readers, notes/review forms, workload confirmation and model/tool/receipt flow. | No research rerun or saved-post rescreening in this review. |
| Portfolio | Positions, Proposed and Performance controls; model capital, source/eligibility limits, deterministic sizing and retained outcomes. | No held position, new joint synthesis or populated captured performance was produced. |
| Orders | Ticket terms and steps; stock, single-option and package rules; Drafts/Open orders/History/Baskets; basket panes; exact approval/submission and exercise/DNE boundaries. Rejected NVDA and saved basket paths checked. | Broker effects and empty option states are source-only. After repair, the saved leg and revision history stayed open across refresh; the leg review button opened the exact saved AAPL order. |
| Journal | Decisions, Position outcomes, Notes and Account history; search/export selection, decision detail tabs, source links and authored note fields. Existing decision and Notes shortcuts checked. | No note/export/capture saved. No saved note is not a saved-note record. |
| Strategy lab | Simulation/experiment editors, saved strategies, conditional operands/exits, scenario rows, preview/run/result/comparison controls and worker flow. Draft field changes checked and discarded. | Existing split-adjusted META data is ineligible for raw-history simulation. Populated run/results remain source-only. |
| Alerts | Inbox/Rules/Delivery, conditional target/atom/drawing/policy forms, occurrence evidence, acknowledgment and notification actions. Conditional draft forms checked. | No rule activated or notification permission changed. Indicator threshold label now states recorded series units; the price/movement label remains separate. |
| Settings | Account/Research/Trading rules/Integrations/Diagnostics, draft save/discard, presets/import review, native report and recovery actions. Saved forms and conditional provider draft checked. | No configuration save or recovery performed. Corrected model helper text matches the fast/deep assignments and was checked live. |
| Workflows | Not part of the 25 October audit. Documented from `workflows.js` and `workflows.py` on 28 October 2026 in `references/workflows.md`; live read-only API showed one saved workflow, `Default`, active. | Browser rendering, editing, preview, save and activation not exercised. |

Label and field inventories were compared with the reference text, then navigation and conditional logic were traced through the final renderers, handlers and services. An inventory match alone is not behavioral proof. Conditional effects without usable records remain explicitly source-only; do not silently promote them to a live pass.

The 25 October table was reviewed against local `nautilus` commit `b632a22`. The shell, Workflows and Settings text was re-audited against source at commit `237cc04` and the live read-only API on 2026-10-28. The current review uses the internal browser and current handlers. The page references state which views were observed and which conditional effects remain source-only. Earlier screenshots and worker reports are historical evidence, not acceptance of the current product.

Read-only navigation can save view preferences. No research, calculation, collection, authored record, settings save, import/export, notification, backup/restore or broker action is required to inspect these controls.
