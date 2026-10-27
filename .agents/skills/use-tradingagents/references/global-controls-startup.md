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

**Find a symbol** uses a datalist of current market symbols. On change, the input is trimmed and uppercased. Only an exact symbol from the loaded market-symbol list is accepted; another string leaves the view unchanged. A valid committed symbol change opens Markets → Stock review for that symbol. In the 25 October internal-browser check, native typing of META followed by Tab opened META; filling text alone did not commit the change. When automating this control, type the actual code and commit it with Tab, then inspect the resulting stock heading. Do not inject a custom change event. The input keeps the last typed lookup text; it need not match a stock selected later elsewhere. In the browser check it still showed META while Dashboard displayed the subsequently selected AAPL. Confirm the selected stock from the panel heading. Lookup does not change the research batch. Source: `index.html:41–42`, `app.js:412–413`, `505–506`.

The global notice area shows the current app/API error first. A quote-refresh error tells you to use **Refresh** again when connected, or to reconnect Nautilus in Settings → Account when disconnected; automatic quote retry waits until connected. With no error, it can show account-connection unavailable or account not verified. On Orders only, it can show the active order-pause block or review-only boundary. **Dismiss error** hides the current app error; it does not correct the cause. Source: `renderNotice()` in `app.js:233`.

Keyboard: **Alt+R** invokes the same Refresh button unless focus is in INPUT, TEXTAREA or SELECT. No other global keyboard shortcut or help dialog is declared in the shell source reviewed.

To check the runtime, open **Settings → Account**. Read observed mode/account and use the persistent Nautilus start/stop controls only when needed. **Settings → Diagnostics** shows **Health and recovery**, current or last-observed engine and account-import state, startup errors, local store status, and recovery controls. Its **Connection controls** button returns to Account. These controls change runtime state. Do not activate them during a read-only walkthrough.



The header pause control **New orders not paused · manage** / **New orders paused · manage** navigates to Orders and attempts to focus account order controls. It does not toggle pause directly. **Observed limitation:** an already-open stock ticket can remain open and hide the pause controls. Use **Back to universe**, then **Orders → Drafts** if needed, to expose them. In the 25 October check the pause button became visible after closing the ticket, and the header remained **New orders not paused · manage** throughout. The separate **Pause new orders** and **Resume new orders** buttons change the account order gate; Manage only opens the controls. Pause and resume do not cancel existing broker orders. Do not activate those state-changing buttons during a read-only tutorial. Source: `app.js:1289`; Orders behavior in `references/portfolio-orders-journal.md`.

Search, pagination, sort, filters, tabs, disclosures, symbol inspection, and page size change the displayed view. The app also saves some view preferences in browser local storage through persistView() in tradingagents/web/static/app.js:137; this is separate from the server workspace. Check the page reference for each action's actual boundary. A button that says Load may read retained definitions or data; inspect its handler before treating it as safe. Do not assume that Preview, Save, Run, Collect, Import, Export, Enable, Retry, Capture, Approve, Submit, Cancel, Stop, or Restore is read-only.

## Workspace save status

Markets and chart workspace edits use a separate server save path. The status reads **All changes saved**, **Unsaved workspace changes**, **Saving workspace…**, or the returned error. queueWorkspace() in app.js:2064–2067 starts a save 450 ms after an edit. writeWorkspace() at app.js:2080–2091 sends the expected workspace revision.

On an ordinary save error, **Retry save** retries the pending change. On a revision conflict, retry is hidden because another revision changed. **Reload saved workspace (discard unsaved edits)** reads the saved server copy and discards current workspace edits, notes and drawings. Browser `persistView()` preferences and server `UniverseReview.persistPreferences()` preferences are different paths. Markets search, sort, selected watchlist, columns, instrument/chart selection can queue a server workspace save even when the action only changes the view. Navigation can therefore show Saving workspace… or advance an internal revision. This does not imply a new research result or a broker change. Do not promise that all view changes are browser-only. Do not use Retry or Reload to reveal a status during a walkthrough.

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
- The health block and status message show the actual outcome. They do not prove broker reconciliation. Restore needs a user-authorized recovery task for the exact inspected archive; it is not incidental tutorial navigation.

Source: `tradingagents/web/static/recovery.html`, `recovery.js`, `tradingagents/web/recovery_mode.py`; normal recovery controls are in the Settings reference.

## Coverage evidence and limits

### Requirement audit · 25 October 2026

This is a control guide review, not certification that every product workflow works. The references cover the following control groups, their choices, prerequisites, draft/save/request boundaries and result meanings. Later dated observations supersede earlier empty states only for the checked path.

| Area | Documentation and observed checks | Runtime limits |
| --- | --- | --- |
| Shared shell | Nine workspace links, header lookup, refresh, pause-management route, save/error states and recovery controls. Lookup and management navigation checked. | Reconnect failure, pause changes and recovery cutover not induced. |
| Dashboard | Account/panel meanings, watchlist filters, columns, selection, pagination, ticker selection, report/data retry and Open instrument route. | No holding row exists in this account. |
| Markets | Four tabs; list/screener/scan forms; instrument Chart/Research/Options/Position; five chart inspectors and conditional editors. One retained-input chart calculation and one real option page checked. | Collection, scheduling, drawing saves and option subscriptions remain source-traced where stated. |
| Research | Selection versus inspection, six detail tabs, report/debate/source readers, notes/review forms, workload confirmation and model/tool/receipt flow. | No research rerun or saved-post rescreening in this review. |
| Portfolio | Positions, Proposed and Performance controls; model capital, source/eligibility limits, deterministic sizing and retained outcomes. | No held position, new joint synthesis or populated captured performance was produced. |
| Orders | Ticket terms and steps; stock, single-option and package rules; Drafts/Open orders/History/Baskets; basket panes; exact approval/submission and exercise/DNE boundaries. Rejected NVDA and saved basket paths checked. | Broker effects and empty option states are source-only. After repair, the saved leg and revision history stayed open across refresh; the leg review button opened the exact saved AAPL order. |
| Journal | Decisions, Position outcomes, Notes and Account history; search/export selection, decision detail tabs, source links and authored note fields. Existing decision and Notes shortcuts checked. | No note/export/capture saved. No saved note is not a saved-note record. |
| Strategy lab | Simulation/experiment editors, saved strategies, conditional operands/exits, scenario rows, preview/run/result/comparison controls and worker flow. Draft field changes checked and discarded. | Existing split-adjusted META data is ineligible for raw-history simulation. Populated run/results remain source-only. |
| Alerts | Inbox/Rules/Delivery, conditional target/atom/drawing/policy forms, occurrence evidence, acknowledgment and notification actions. Conditional draft forms checked. | No rule activated or notification permission changed. Indicator threshold label now states recorded series units; the price/movement label remains separate. |
| Settings | Account/Research/Trading rules/Integrations/Diagnostics, draft save/discard, presets/import review, native report and recovery actions. Saved forms and conditional provider draft checked. | No configuration save or recovery performed. Corrected model helper text matches the fast/deep assignments and was checked live. |

Label and field inventories were compared with the reference text, then navigation and conditional logic were traced through the final renderers, handlers and services. An inventory match alone is not behavioral proof. Conditional effects without usable records remain explicitly source-only; do not silently promote them to a live pass.

Source reviewed against local `nautilus` commit `b632a22` on 2026-10-25. The current review uses the internal browser and current handlers. The page references state which views were observed and which conditional effects remain source-only. Earlier screenshots and worker reports are historical evidence, not acceptance of the current product.

Read-only navigation can save view preferences. No research, calculation, collection, authored record, settings save, import/export, notification, backup/restore or broker action is required to inspect these controls.
