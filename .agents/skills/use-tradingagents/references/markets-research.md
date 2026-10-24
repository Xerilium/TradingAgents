# Dashboard, Markets, and Research reference

Source-grounded control guide for the installed desk UI.

## Contents

- [Terms and operating rules](#plain-language-terms)
- [Dashboard](#dashboard)
- [Markets: Watchlists and Universe](#watchlists--universe)
- [Markets: Screener and Saved scans](#screener)
- [Instrument workspace and Options](#instrument-workspace)
- [Chart and inspectors](#chart-base-evidence-and-source-data)
- [Instrument Research](#instrument-research)
- [Research workspace](#research-workspace)
- [Live evidence and limits](#live-evidence-and-limits)
- [Source map](#source-map)

This guide marks each workflow Observed or Source-only. A source-only path was confirmed in code but was not exercised in the live pass listed below. Do not report it as tested.

Source links use repository paths under tradingagents/web unless stated otherwise.

## Plain-language terms

- **Saved inputs/revision:** values kept for a past research run or definition. A new revision is added; an old one is not edited in place.
- **OHLCV:** open, high, low, close and volume for a recorded bar. These are historical bar values, separate from a latest trade or quote.
- **Cache:** data the app has already stored. Selecting it reads that copy; it does not ask the provider for new data.
- **Provider:** the external market-data source named in the UI, such as Yahoo or Alpaca/IEX. A configured provider can still fail or lack data.
- **Source-only:** control or behavior confirmed in code but not visible in this live sample because the needed saved data/result was absent.
- **Draft:** current form edits not yet saved or run. Previewing a draft does not mean it has been saved or executed.
 Source references point to one-based lines in `tradingagents/web/static/app.js` unless another file is named. “Observed” means seen in the live browser on 2026-10-24. “Source-only” means the conditional control or behavior was verified in implementation but its data-dependent state was not present in the live browser. Repeated rows share one schema.

## User and assistant operating rules

- The assistant should guide by explaining the current visible page, locating the relevant control, and operating safe read-only controls. Do not make the human click through a tutorial when the assistant can demonstrate it.
- Treat these pages as observation, research and draft preparation. Research recommendations do not authorize orders. For any ticket, keep preview, save, approval and broker submission distinct; never submit or approve while teaching this workflow.
- The inspected instrument is independent from research batch selection. Confirm the batch list shown in Research Setup before any user-authorized run.
- Use cached/research data with its source, feed, price basis, capture time and age. A stale/closed-session last trade, historical OHLC close, derived chart and quote are distinct observations.
- Current research is latest per ticker only. Long-term lessons belong to Maenifold memory, not a competing desk decision/reflection log. Do not promise research history, replay ledgers or resume behavior.
- When a control can collect provider data, start a paid/model task, save settings, alter saved workspace, subscribe a native quote feed, create an order draft, or otherwise write state, describe the boundary and stop unless that exact action is authorized. Merely opening a menu, reading retained data, switching a read-only view, and expanding a disclosure are safe.

## Common navigation and status

**Observed.** App navigation shows Dashboard, Portfolio, Markets, Research, Orders, Strategy lab, Journal, Alerts and Settings. Global header shows account mode, account identifier, universe name, current page, “Find a symbol” combo box, market session and snapshot time, and Refresh. The left footer shows local workspace/Maenifold MCP, configured account, snapshot market data and currency. The order-pause control shows “New orders not paused · manage”; it is outside this reference scope.

**Effects and status.** Dashboard/Markets show account observation/quote timestamps and source age. “Market closed” plus a last quote from the prior session is not a live executable price. Keep observed account state separate from quote freshness and saved daily OHLCV.

**Source.** Navigation, page rendering and event delegation: `app.js:2789–2846`; dashboard data/panels: `app.js:407–430`.

## Dashboard

**Observed page header.** Account observed timestamp and USD; “View portfolio” link. Live sample said Account verified, account observed Oct 24, equity/cash/buying power $100,000, position value $0 and 0 open orders. These are account observations, not a broker action.

**Account ledger.** Equity, Cash, Buying power, Long position value, Open orders. If a value is unavailable, it is labeled unavailable; do not infer zero.

**Dashboard panel selectors.** Watch, Chart, Research, Positions, Orders switch the content panes. They do not submit transactions.
- **Watch** embeds the configured stock list.
- **Chart** embeds the selected instrument summary/chart with “Open instrument”; that button opens the instrument workspace.
- **Research** shows saved recommendation/status and date for the selected instrument; “Open research”/inspect opens the record.
- **Positions** and **Orders** summarize observed holdings and orders.
- **Watchlist table:** search; Show choices All stocks, Selected for research, Held positions, Needs research today, Missing quotes, Stale quotes; Select N matches; Clear selection; batch selector. Each symbol has a research-inclusion checkbox separate from the symbol/open checkbox, quote price, change and expandable Price source and time. Pagination size 25/50/100 and Previous/Next when multiple pages.
- **Update quotes** requests a quote update when Nautilus is connected and the action is enabled. “Updating…”, last-update failure, reconnect-needed, snapshot feed and checked time communicate state. “Edit index” links to Settings.

**Prerequisites/effects.** Search and Show filter rows. Select N matches and Clear selection affect only the research batch list. Opening a symbol/instrument does not silently change selected research symbols. Update quotes is a data request, not an order; do not trigger when only demonstrating the page.

**Source.** `watchlist()` and row/list toolbar: `app.js:339–370`; dashboard panel markup: `app.js:407–430`; shared delegated handlers: `app.js:1284+`.

## Markets

Markets has four workspace tabs: **Watchlists**, **Universe**, **Screener**, **Saved scans**. Current top-level label may show “Watchlists” while the content includes the configured universe. Workspace save status is visible (“All changes saved”, unsaved changes, or save error). Do not edit workspace merely to inspect.

### Watchlists / Universe

**Observed controls.**
- Search symbol or company text field.
- View watchlist selector. Live values: All configured stocks; Shortlist; Shortlist (import 2); Research review; Shortlist (import 3); Research review (import 2). User-created list values vary by saved workspace.
- Expand **Filters, list management and batch actions**.
- **Universe views:** All; Owned (includes outside universe); Has saved research; No saved research; Research needs human review; Future research priorities; Price missing; Price stale; Gainers; Decliners. These are filters; counts reflect current view.
- **Min |change| ≥**: no minimum, 0.5%, 1%, 2%, 3%, 5%.
- **Sort by**: Symbol, Company, Price, Change %, Move size %, Price age, Research date, Saved rating. Sort direction button toggles descending/ascending. Clear filters resets filters.
- **List management:** New watchlist name + Create from selected; selection count; Select all filtered; Clear selection; Export selected observed holdings CSV; Edit list target selector (only existing saved list names); Add to [target]; Remove from [target]; Review research for selected stocks.
- Expand **Manage universe columns** for column visibility/order controls; expand **Snapshot provenance and data boundaries** for source meanings.
- Table column headers are sortable: Stock/company, Latest price, Change %, Price age, Saved research. Header Batch checkbox selects the stocks on the visible page. Per row: batch inclusion checkbox; symbol checkbox; ticker/company; expandable **Why in this view / source time**; price, change, source timestamp and age/freshness note; recommendation and research date. Pagination is page-scoped.
- An outside-universe discovery list can appear separately. It does not become configured universe membership or holdings unless the user adds it through the eligible retained-result action or Settings. Membership does not create a holding.

**Purpose and boundary.** Search, views, change threshold, sort and column controls change what is shown. “Create from selected” and Add/Remove write named watchlist membership; named lists do not start research, change the configured universe, create holdings or modify broker orders. “Review research for selected stocks” navigates into existing records. The CSV control exports selected observed holdings, not hypothetical universe holdings.

**Source.** `watchlist()`: `app.js:339+`; Markets tabs and table shell: `app.js:2789–2846`; list/discovery binding: `app.js:1879–1900` and shared event delegation `app.js:1284+`. The live sample had 7 configured stocks, all with retained research and a market-closed quote roughly one day old; shown ages are from event timestamps.

### Screener

**Observed initial state.** No discovery data is fetched until the user selects **Run current screen**. No screen result yet. No request was run during verification.

**Criteria controls.**
- Minimum price / USD; Maximum price / USD; Minimum market cap / USD; Minimum average 3-month volume (numeric fields).
- Sector: Any sector plus Basic Materials, Communication Services, Consumer Cyclical, Consumer Defensive, Energy, Financial Services, Healthcare, Industrials, Real Estate, Technology, Utilities.
- Sort: ticker, percentchange, dayvolume, intradaymarketcap.
- Direction: Ascending / Descending.
- **Saved criteria and provider details** disclosure:
  - Saved criteria selector, Load saved criteria (replace draft)
  - Name text input, Save as named criteria.
  - The criteria editors below are a draft until saved. Loading replaces the draft; running a screen does not save it.
- **Run current screen** starts Yahoo/yfinance discovery; while in progress it reads “Requesting screen…”. On failure, show provider error; on a successful empty page, explicitly say provider returned an empty page.

**Conditional populated result (source-only; not observed because no screen was run).**
- Dated result identity/status: provider, scope, requested/captured times, offset, returned count, total or “provider total unavailable”, page size and limitation.
- **Criteria used for this result (draft changes do not change it)** disclosure.
- Failed result error vs successful empty result.
- Rows have selection checkbox; inspect-symbol button; company name; configured/outside-universe flag; price/currency, change %, market cap, volume and provider market timestamp. Invalid symbols may be disabled.
- Previous page / Next page; Add selected matches to watchlist selector and **Add selected matches** changes only that named list. An eligible outside-universe result also has **Add this symbol to configured universe**. That action is separate and writes the configured universe from a retained completed result; it is not the list-add action. Disabled/invalid symbols cannot be added. Settings remains another route to edit the configured universe.
- Prior/next uses the saved criteria and changes offset by 25. Pages are not proof of full-market completeness; a missing provider total stays unknown.

**Source and effect.** Discovery markup and request/save/paging handlers: `app.js:1879–1900`. Provider collection is a separate explicit action from editing or saving criteria; adding matches changes only the selected named list. Yahoo discovery is not Alpaca tradability or a quote feed.

### Saved scans

**Observed initial state.** No saved definitions. “Edit a new draft, then save a revision.” No scan run was started.

**Definition and run views.**
- Saved definition selector; **Load exact definition into draft** (disabled with no selection); **New draft · scheduling off**; **Refresh saved definitions and jobs**.
- Subtabs: Definition, Runs, Matches.
- Definition draft: Scan name and Fixed symbols / comma separated. Text says Target mode fixed, Source mode retained; other target/source settings are under Advanced definition.
- **Add guided multi-timeframe conditions** appends a program draft; declarative conditions remain unchanged in Advanced definition.
- Disclosures: Advanced definition / JSON; Installed complete Yahoo operators, fields, values and typed scan schema; Run source, collection consent, and scheduling; Import and export; Immutable definition revision history; Durable schedule slots, skipped overlaps and restart gaps; Scan details.
- Copy states older cutoff is retrospective unless original knowledge evidence proves otherwise; imported definitions require review and explicit schedule/attention opt-in.
- Save immutable definition revision · schedule off; Run selected saved revision once (disabled without a selected saved revision).

**Guided multi-timeframe program (source; visible in root’s read-only pass).** **Add guided multi-timeframe conditions** adds a program draft to the definition. The program exposes:

- **Scan name** and **Fixed symbols / comma separated**; **Anchor input** selects one named input; **Condition combination** is **ALL** or **ANY**; **Knowledge policy** is **evaluate_now** or **known_then**. `known_then` needs original availability evidence. An evaluation now does not prove the condition was knowable then.
- **Named inputs:** rename or remove each input; **Add named input** adds one. Each input has **Timeframe** (1Min/5Min/15Min/30Min/1Hour/1Day), **Session** (regular/provider_day), Provider (Alpaca), Feed (iex), Adjustment (raw/split/dividend/all), Currency (USD), **Exact retained history key / blank selects compatible retained source**, **Allowed stale expected buckets**, and **Input value** (field/definition). Field values are open/high/low/close/volume. Definition values select an exact reusable saved revision and its exact output component. Formula parameters stay with that immutable Chart definition revision.
- **Typed condition parameters:** rename or remove parameter; **Add typed condition parameter** adds a parameter. Each has exact decimal **value** and **Units** (price/volume/scalar/percent).
- **Conditions:** each row has a left operand, **Comparison** (gt/gte/lt/lte/eq/cross_above/cross_below), right operand and Remove condition. **Add condition** adds a row. Each operand kind is **input**, **parameter**, or **constant**. Input and parameter kinds select an existing name. Constant adds an exact decimal and units (price/volume/scalar/percent). Input values can use raw fields or an exact saved-definition output component.
- Rolling formulas calculate on each original input axis before backward closed-bar alignment. Crossings need two actual anchor observations. Coarser intraday bars derive from retained 1-minute data on the recorded session grid; no missing bars are invented. Provider availability, compatible source, sufficient history and freshness can make an input unavailable.
- If the JSON has invalid program objects, the UI shows “Program inputs and parameters must be objects, and conditions must be an array” and points to Advanced JSON or a saved revision. If Advanced JSON is invalid, program controls are replaced by “Correct the advanced JSON before using program controls.”

**Boundary.** A draft is not a saved immutable revision. Saving does not run it. Run/schedule/data-collection actions are separate and require authorization. Runs and Matches were opened and were empty. Populated result rows and run statuses remain source-only.

**Source.** `scannerMarkup()` and scan binding: `app.js:1729–1777`; Markets tab mount: `app.js:2789+`.

## Instrument workspace

Opening a ticker from Dashboard/Markets/Research shows **Stock review** for that ticker. The Viewing selector offers the configured/filtered instruments (live sample AAPL, AMZN, GOOGL, META, MSFT, NFLX, NVDA). Header says **Batch selection: N stocks · unchanged by viewing**. **Back to universe** returns to Markets. Quote header shows symbol/company, price basis/feed, market session, event time, age and freshness boundary.

Four instrument tabs:
- **Chart:** recorded daily OHLC chart and chart inspectors.
- **Research:** saved reports, revision review, investor note and supplementary evidence.
- **Options:** Alpaca US option contract discovery.
- **Position:** observed holdings (or explicit no-position state) and an embedded Human trade proposal with **Entry** and **Review** steps. It is present even when the instrument has no holding. The ticket fields include side, shares, order type, limit, duration, session, replacement, and notes; its preview/save controls prepare terms, not an approved or submitted order. See the Orders reference for full ticket validation and authority.

Source composition/selection: `instrumentView()`, `instrumentMarkup()`, `bindInstrument()`: `app.js:2572–2610`. Viewing a different symbol leaves research batch selection unchanged.

**Position routes.** Dashboard → Positions has Symbol, Quantity, Avg. cost, Market value, Unrealized P/L, and Weight columns. Select a symbol row (`data-action="inspect"`) to set the selected symbol and open Research; the shared handler selects that symbol’s latest run when available. The instrument header offers **Back to universe** to return to Markets. This route does not require an open position. In the instrument workspace, **Position** always renders the embedded Human trade proposal, including when no holding is shown. Source: `positionsTable()` (`app.js:340+`), delegated `inspect` handler (`app.js:1284+`), `instrumentView()` / `instrumentMarkup()` (`app.js:2572–2610`).

### Instrument Options and contract discovery

**Source-confirmed controls.** Open **Options** for an instrument. The **US option contracts · Alpaca** disclosure explains that contract discovery is separate from stock discovery and research. It does not submit or approve an order.

- **Contract query / JSON** is a text area. Its initial query preset sets status to active and limit to 25. It accepts a JSON object. Supported fields are `underlying_symbols`, `expiration_date`, `expiration_date_gte`, `expiration_date_lte`, `type`, `status`, `limit`, and `page_token`. Exact contract lookup uses the symbol-only JSON form. The symbol must match the OCC form `[A-Z]{1,6}[0-9]{6}[CP][0-9]{8}`; exact lookup must contain only the symbol field. Other keys outside the listed allowlist are rejected. Invalid JSON displays its parse error without a request; query/response errors appear in the status line.
- **Request contract page / exact inspection** makes one explicit Alpaca request. The response is retained with the exact query, received time, returned contracts, next-page token, source artifact and hash. Pagination is a separate request. While busy, the button is disabled and status says **Request in progress…**. Request failures appear in the status line.
- **Retained page** selects **Latest retained page** or one captured page. This is a local view change. The view shows receive time, contract count and next-page token; **Exact retained query and response receipt** opens the retained metadata.
- Each contract disclosure shows OCC symbol, type, expiry, strike, underlying, deliverable size, status, broker tradability (**Yes**, **No**, or **Unknown**) and raw retained details. Unknown mapping or eligibility is not treated as supported.
- **Expiration** filters the selected retained page. **Type** filters calls and puts. The table columns are Contract, Type, Expiry, Strike, Multiplier, Bid / ask, Eligibility / details. Bid/ask values are native option-premium observations. Indicative quotes are labeled indicative. Errors and unavailable quotes remain visible.
- **Explicit option quote feed** choices are **Choose feed**, **opra**, and **indicative**. Entitlement is not inferred. **Select exact contract and subscribe** is disabled until a feed is chosen, while the request is busy, or when no raw contract symbol is present. It stores the exact contract and source observation. Selection and feed persist across restart. The app configures the native node for that option symbol. All selected contracts must use the same feed.
- **Apply chosen feed to all selected contracts** is disabled until a feed and at least one selected contract exist. It changes every retained selected subscription, then rereads state. A stale revision asks the user to reload retained discovery. The current live view had **No retained option page** and this action was disabled; no request, selection, or feed change was made.
- **Selected contracts · retained across restart** lists each contract/feed/selection time and provides **Open manual premium ticket**. **Prepare atomic long-only package from selected contracts** is disabled until at least two contracts are selected. The package editor then requires 2–4 distinct retained contracts and current native contract/premium evidence. Opening a ticket is order preparation, not approval or submission.
- The UI documents supported preparation as long single-leg call/put, whole contracts, buy-to-open or sell-to-close, MARKET/LIMIT/STOP/STOP_LIMIT, DAY/GTC, regular session. Short opening and full settlement acceptance are outside this profile. Exercise and do-not-exercise use separate reviewed instructions.

The request path is `bindOptions()` and `optionMarkup()` in `tradingagents/web/static/app.js:1861–1876`. The service action `option_discovery()` in `tradingagents/web/service.py:999–1079` calls `AlpacaREST.option_contracts()` in `alpaca_readonly.py:79–101`, saves its raw source artifact and exact observation, validates an explicit feed and retained revision, persists selection, and reconfigures native subscriptions. The UI renders the filtered chain and exact details in `instrumentMarkup()` in `app.js:2573–2587`. Chart plotting and pointer interaction are in `market-chart.js`; app assets vendor Lightweight Charts and its drawing plugin under `tradingagents/web/static/vendor/`. No `chart_workspace.js` exists in this checkout. It rejects unsupported feed, missing selection, stale revision, invalid mapping, or mixed feeds. Option selections and observations are retained in the discovery store. Native quote errors and dated quote receipt remain separate from contract metadata. No claim of OPRA entitlement or broker execution follows from a listed contract or quote.

Exercise/DNE instructions are a separate human-only flow. See the Orders reference for its review, approval, submission, unknown-outcome and interlock rules. This Options guide covers contract discovery and quote subscription only.

### Chart: base evidence and source data

**Observed chart.** AAPL recorded 1Day OHLC chart using Lightweight Charts, with price series and chart attribution/license links. The screen showed a last trade around $347.69 and separate daily close around $348.22; these are different sources/events. Use chart context and selected bar time before interpreting any readout. Canvas is a chart display; pointer interactions may pan/zoom/inspect but do not fetch new history.

**Inspector tabs (observed).** Studies and formulas; Drawings; Comparison; Saved calculations; Source data; Playback. Selecting an inspector changes the view, not its backing data. Selecting the same inspector again can close it in Markets.

**Source data context and retained-history fields (observed/source).**
- Chart evidence context selector: Immutable saved research inputs; Current-market context · IEX cache. Selecting a cache reads retained data. Choosing current context can load an existing selected cache; the request buttons below initiate new collection.
- Saved research inputs identify the run, research date, provider bars and any missing/unverified adjustment basis.
- Range selector: 1W, 1M, 3M, 6M, All saved.
- Recorded business day selector: all available retained business dates (sample had 1,254 options).
- Readout fields: Open, High, Low, Close, Volume, Prior saved close, Recorded close-to-close movement. Movement formula is selected recorded close / previous available recorded close − 1; it is not last trade or bid/ask midpoint.
- **Prepare a manual ticket from an exact historical price:** Recorded value selector close/open/high/low; Compatible existing ticket field selector; exact-value/source/currency message; **Review price normalization** (disabled when a compatible field or exact source evidence is missing). This copies only after explicit field selection and normalization review; it does not update live quote or authorize/submit a ticket.
- Disclosures: OHLCV source artifact; each recorded indicator (e.g. SMA/EMA/MACD/RSI/Bollinger/ATR/VWMA/MFI); Claim attribution and unresolved numeric mapping. These preserve evidence/calculation details and distinguish authored report claims from recorded values.
- Latest Nautilus price/bid/ask/source event and Snapshot checked are separate from saved bar data. Daily axes are business days; intraday timestamp basis/NY context is described in the readout. Partial pages/matched timestamps do not establish calendar completeness.
- Current-market retained history form (conditional/source-only until switched to current context): bar interval 1Min, 5Min, 15Min, 30Min, 1Hour, 1Day; Start date; End date; symbol mapping as-of date (America/New_York); adjustment basis raw/split/dividend/all; Request this stock’s chart range; Request required 252-session daily baseline; Request selected list (count) with these dates. Saved current-market cache selector has Latest retained interval and dated cached entries. These request buttons collect provider bars and must not be pressed during browse-only guidance.
- **Compare retained cache:** None or another symbol cache with the same interval, listed with symbol, dates, adjustment and capture time. Compatibility requires recorded context, interval, provider, feed, adjustment, aggregation and currency. Unmatched times are excluded. Choosing comparison does not collect data; current context/history is prerequisite. If history is absent, Comparison shows that retained current-market history is required.

**Source.** Current cache controls: `app.js:1439–1475`; source evidence composition around `app.js:1463–1480`; chart tab assignment: `app.js:2599–2610`; historical price/copy controls are emitted with chart evidence/readout around `app.js:2489+`.

### Chart inspector: Studies and formulas

**Observed empty/load state.** Disclosure **Chart analysis · transforms, studies, seasonality and formulas** says it derives from this exact retained source; raw OHLC and manual ticket source remain separate. **Load saved definitions and calculation index** reads local saved metadata; it is not a provider collection/order action. Before metadata loads, definition fields are absent. After load, one can see the editor.

**Source-only editor controls (not saved or calculated during verification).**
- **Saved definition revision** selector: New definition or exact saved definition name/kind/revision.
- **Reusable identifier** field; valid name starts with a letter and uses letters/digits/underscore.
- **Analysis kind:** transform, study, seasonality, formula.
- **Save immutable definition revision** persists a new revision; saving does not calculate.
- Total chart budget / seconds including queue wait: integer 1–600; default 60. **Calculate exact saved revision** disabled until an exact saved definition is selected and the draft has no unsaved changes. Single chart worker allows one running and one queued; expired queued work is not dispatched. Calculation uses pinned raw artifact, separate from Optuna/trading.
- Definition import/export: Export selected revision or full library; Import validated definition bundle (JSON file). Collision does not overwrite immutable history; exact dependencies resolve by revision/hash. Do not import/export while teaching.
- Saved calculations list exact entries by definition, family/kind, revision, status, created time; selecting an entry reopens its result, does not calculate again.
- **Installed calculation capabilities and conventions** disclosure lists accepted capabilities/typed operations.

**Conditional settings by kind.**
- **Transform family:** heikin_ashi, renko, kagi, line_break, point_figure. Fields: Exact brick/box size; Reversal boxes; Kagi reversal basis fixed/percent; Exact reversal amount/percent; Completed-line lookback. Controls vary by family. Completed close-based derived values and logical event ordinals are not actual prices/timestamps/volume.
- **Study family:** kama, cci, donchian, ichimoku. Fields: Period/observations; KAMA fast/slow smoothing; CCI scale and moving average (SIMPLE); Donchian lag/actual bars; Ichimoku conversion/base/span-B periods and forward/backward displacement. Initialization and gaps stay explicit.
- **Formula:** Formula expression textarea; typed causal series only, no eval/imports/application actions. Formula function buttons are inserted from loaded capabilities (source-only dynamic list). Output presentation line/histogram/overlay; declared output units from capabilities; Forward display offset/logical bars; exact scalar parameter rows (Name, Exact decimal value, Units excluding boolean), Remove parameter, Add typed parameter. Pinned reusable definitions use exact revision/hash dependency checkboxes. Buttons “Insert …” offer series from selected dependencies. Formula arguments are ordered alphabetically by parameter name. Positive displacement is a display projection, not future evidence.
- **Seasonality:** Year comparison alignment calendar/session; Comparison scale raw/normalized; exact source adjustment shown. Completed month return uses prior-month-end to month-end close; only complete eligible years enter denominator; MTD/YTD remain separate and excluded; no dividend reinvestment implied.

**Conditional result controls (source-only).** Calculation status, total budget, error/queue wait and queue/execution/termination evidence disclosure; Cancel this calculation when queued/running; calculation ID/source pin/result hash/derivation identity; coverage/provisional-inputs disclosure; when seasonality exists, Yearly value scale Common scale across years or Separate labeled scale per year; derived chart event selector by logical ordinal; exact derived geometry disclosure; actual retained source bar selector/readout Open/High/Low/Close/Source volume; **Open this actual bar in the raw chart** enters pinned retained playback; full definitions/algorithm/precision/init/source evidence disclosure. Clicking a derived event or source bar is inspection, not an execution price. Only raw source OHLC copy controls can prepare a manual ticket price.

**Source.** Chart analysis UI, editor and action handlers: `app.js:1526–1585`; rendering of SVG, series, seasonality, exact readout and click/keyboard event inspection: `static/market-chart.js:184–224`; inspector switch and load button: `app.js:2599–2610`.

### Chart inspector: Drawings

**Observed.** Price annotations, scope identity (symbol/timeframe/context/provider/feed/adjustment/currency), and an explicit note that numeric lines can feed a separately saved alert but drawing save alone creates no alert. Pointer anchors are approximations; exact retained OHLC binds only via explicit action.

**Controls and effect.**
- New annotation: horizontal-line, trend-line, text.
- Create numeric draft creates a local draft; trend line has two anchors, horizontal line one. Place with pointer starts/stops chart placement; chart clicks/drag gesture provide approximate anchor coordinates.
- Saved annotations and local drafts selector. Selecting one exposes exact numeric inputs and style fields (time/price or logical offset; text/color; line width; point coordinate basis/time/origin).
- “Use selected retained OHLC value” binds a specific visible retained bar’s chosen open/high/low/close plus pinned provenance.
- Select drawing/drag handles edits a local draft. Delete stages removal; explicit Save or Remove commits a workspace revision; Ctrl/Cmd+S saves selected annotation; Escape ends pointer placement; Discard reopens the saved record and discards local edits.
- Unresolved annotation coordinates disclosure explains incompatible/out-of-scope data. Explicit rebind is a separate action and preserves anchors; do not silently rebind.
- Create alert from eligible saved numeric annotation creates an alert draft for separate explicit save; no alert is started by drawing save.
- On comparison chart drawing controls are disabled; switch to OHLC first.

**Source.** `drawingPanel()` and scope/control generation: `app.js:1493–1508`; interaction and persistence: `app.js:1513–1523`; chart inspector grouping: `app.js:2599–2609`.

### Chart inspector: Comparison

**Observed.** In immutable saved-research context without current-market cache, only status: “Comparison setup requires current-market retained history. Choose that chart context in Source data to inspect available retained caches.”

**Source-only when eligible.** Choose Current-market context · IEX cache, then choose another retained current-market cache (same chart interval). Compare cache list contains no comparison plus symbol/date/adjustment/capture-time entries. Selection is client-side and does not request provider data. Comparison requires matching context, timeframe, provider/feed, adjustment, aggregation, currency. Matched retained timestamps only; no assumed joins or future quotes. Chart attribution shows which primary/secondary cache and exact matched rows. Drawing placement is disabled on the comparison chart. There is no observed live comparison result in the verified cache state.

**Source.** Cache list/build and comparison control: `app.js:1439–1468`; conditional comparison rendering: `app.js:2600–2604`; chart comparison and timestamp matching: `static/market-chart.js:226+` and the current comparison source module.

### Chart inspector: Saved calculations

**Observed.** Message says open Studies and formulas to load saved definitions, reopen exact calculations and inspect result/evidence. Opening result does not calculate it again. Button **Open saved calculations** switches to Studies and formulas.

**Source-only.** Loaded exact saved calculation buttons show definition/kind/revision/status and created time. Conditional result presents frozen source pin, output/result hash and derivation identity, coverage status, queue/termination evidence; current draft changes do not change the immutable result. Reopen selects that exact result; calculation is not rerun.

**Source.** Inspector placeholder: `app.js:2602, 2609`; saved calculation list/button: `app.js:1565–1568, 1570–1574`.

### Chart inspector: Playback

**Observed.** **Pin these retained inputs for playback** is the entry button; it was not pressed.

**Source-only after pin.**
- Heading says hindsight, not a backtest or live market.
- Status is Reading exact pinned artifact / Playing retained bars / Paused, includes capture time, cutoff and pinned artifact hash.
- Actual retained bar slider; Previous bar; Next bar; Play/Pause; Actual bars per second choices 0.25/0.5/1/2/4; Leave playback.
- Playback pins immutable history and a cutoff. It is not a simulation, forecast or market quote; stepping only changes selected retained bar. Leave returns to full-history context. Automatic Markets playback is not established by source; timer is explicitly Dashboard-scoped.
- Chart analysis is hidden during active playback so full-history values cannot expose future inputs.

**Source.** Playback markup and effects: `app.js:1385–1415`; chart inspector grouping: `app.js:2599–2610`; analysis suppression during replay: `app.js:1570–1574`.

### Instrument Research

Research view inside an instrument shows:

- **Investor note · [symbol]** textarea (“Your rationale and questions”), Save note; status “No saved note · notes do not run research or authorize trading.” This is authored local text, separate from research runs.
- **Review this saved revision** identifies run, revision, research date, age and observed gaps. Human disposition choices: Choose a disposition, reviewed, needs_review, deferred. Review notes textarea. **Prioritize future research · does not start a job** checkbox. **Save revision review** stores the human review separately from research. Saved opposing arguments and source text disclosure contains debate artifacts when present; otherwise says no separate debate artifact.
- **[symbol] saved research** shows saved rating/date/revision/completed status and advisory disclaimer. Saved report selector values: final trade decision; fundamentals report; investment debate state; investment plan; market report; news report; risk debate state; sentiment report; source coverage; trader investment plan. Report provenance disclosure.
- **News, business facts and dated events** states provider observations are separate from immutable research and quote entitlement is not implied. **Request supplementary data from an existing provider** disclosure; currently empty state says no supplementary evidence saved and categories remain unavailable. Opening the disclosure is not itself a request; explicit provider request must be separately authorized.

**Observed AAPL status.** No held position. Saved current recommendation is Overweight; quote/source age displayed; review remains “No saved disposition”; note unsaved; supplementary evidence empty. Do not convert any recommendation or saved claim into a live-price assessment.

**Source.** `reviewEditor()`: `app.js:2477–2486`; saved report/supplementary area in Research render: `app.js:2489+`; instrument view composition: `app.js:2572–2586`.

## Research workspace

**Page boundary.** Top status “Latest recommendations, reports, and source evidence”; current latest research date/run and status; buttons Prepare order from this research, Open instrument, Saved orders. Preparing a ticket does not approve or submit it. Research stays advisory.

### Research list and batch selection

- Find research text search.
- Show selector: Latest stocks, Completed, Running, Queued, Failed, Cancelled.
- Summary shows N/N latest stocks finished; progress indicator; completed/failed/interrupted/cancelled/running/queued counts.
- Select failed/unfinished for a new run.
- Per row: inclusion checkbox, ticker, social screening completion, rating/status. Pagination size 25/50/100 with Previous/Next.
- Current store is “Latest research per ticker”; do not instruct the user to resume history or replay older runs.

### Research detail tabs

**Summary.** Latest recommendation/rating; Executive Summary; Investment Thesis; Price Target; Time Horizon; Full source artifact disclosure. Review this saved revision and Investor note controls are described under Instrument Research.

**Reports.** Saved report index tabs:
1. Portfolio decision
2. Market analysis
3. Fundamentals
4. News analysis
5. Sentiment analysis
6. Research committee decision
7. Trader proposal
8. Social sentiment
9. Source coverage

Selecting a report changes the displayed saved report. Full source artifact is a disclosure where provided. Social sentiment report explains Laya as individual-post annotation, not trade approval; Reddit and Stocktwits show fetched/retained/screened counts and stance buckets. Unclear means classification uncertainty; unscreened means no usable classification, neither means neutral. Per-post evidence can expose text, provenance/hash, classification status, probabilities/raw prediction, stance grade, model identity/cache/device/package/revision, token budget and raw answers/usage. **Screen 5 saved posts locally** is a separate local annotation action; it does not refetch source, call the research model or change recommendation, but it changes evidence, so do not click unless requested.

**Debate.** Bull / bear debate and Risk committee selectors. They display saved debate artifacts; no debate rerun occurs on selection. Reports can contain separate “Full source artifact” disclosure.

**Sources.** Saved source links (for example SEC filings and news); **Exact saved result identity, source metadata, and coverage** disclosure shows exact run/revision/source receipts/coverage.

**Activity.** Shows recorded events, “latest 40 of 500”, JSON control, chronological event list with source receipt and status. JSON is an export control; don’t click if the user only asks to inspect.

**Setup.** New research batch lists exact checked symbols and date. Shows Inspected stock separately and warns inspection does not change research batch. Links: Choose batch stocks in Markets; Research models and limits in Settings. **Run research (N)** opens a confirmation dialog; it does not start a run. The dialog shows selected count and exact symbols, configured universe count, max parallel stocks, analysts, fast/deep model tiers, New York trade date, estimated duration based on completed samples (or no completed observations), and states there is no cost estimate. The separate **Start N-stock research** button submits `/api/runs` and begins work. Close the dialog to cancel before admission. Do not click Start during a read-only walkthrough. No autosave means Setup only previews the batch; it does not start anything until the confirmation action.

**Observed sample.** 7 latest stocks finished, all completed; AAPL, AMZN, GOOGL, META, MSFT, NFLX, NVDA. Stored report/activity showed coverage gaps (including Reddit 429) even when state said completed; completion status does not mean all optional evidence sources succeeded. Inspect Source coverage and Activity, do not infer missing data to be neutral or current.

**Source.** Research workspace: `app.js:626+`; report index renderer: `app.js:799–801`; revision review: `app.js:2477–2486`; tabs and setup state/rendering around `app.js:2460–2508`; run/list handlers around `app.js:1284+`.

## Live evidence and limits

- Browser observed: Dashboard shell/account ledger/panels/watchlist; all four Markets tabs and Watchlists filter disclosure; AAPL instrument Chart, Research, Options, Position; all six chart inspectors; Research Summary, Reports, Debate, Sources, Activity, Setup; populated saved AAPL report/review and source data.
- Source-only due no authorized data-collection/run: populated Yahoo screener result/pagination failure-empty differences; populated Saved scan definitions/runs/matches; collected current IEX history and comparison cache; calculation form after metadata loaded/results; drawing edits/saves/alerts; playback after pin; option contract page/contract quote subscriptions/chain/filters; research new run and social screening.
- The scan and screen empty states are not product failures. Missing current-market cache means Comparison cannot be exercised. No observed AAPL position means Position offers proposal fields but no holdings.
- Never claim side-effect workflows were exercised from opening the page or reading their controls.
## Source-only control detail: price drawings on Chart

The browser showed the Chart inspector. No drawing was created, edited, saved, removed, rebound, or used to make an alert. The following details are source-only (app.js:1490–1524; chart pointer gestures: market-chart.js drawing controller and app.js:1520–1523).

- Scope is shown as symbol, timeframe, context, feed and adjustment. A saved annotation matches a pane by symbol, timeframe and current/saved context. Full scope also records instrument ID, currency, provider, feed, adjustment, session and unit. If scope differs, the panel shows an incompatibility warning. The annotation remains inspectable. The app does not silently rebind it.
- **New annotation** choices are horizontal-line, trend-line, and text.
- **Create numeric draft** creates a local horizontal line or trend line with one or two manual-time anchors, based on the chosen kind. It does not save.
- **Place with pointer** turns pointer placement on for the chosen kind. For horizontal-line, one chart click places one anchor. For trend-line, two chart clicks place two anchors. The displayed status reports the tool and anchor count. **Stop pointer placement** turns the tool off. **Escape** also ends placement and clears incomplete anchors. Pointer anchors are manual approximations, not observed market values.
- Chart gestures can select a drawing and drag its handles. A change stages an unsaved local draft. The **Delete** key stages removal. **Ctrl/Cmd+S** saves the selected annotation. These gestures do not save until the explicit save path.
- **Saved annotations and local drafts** lists compatible saved annotations and drafts by kind, shortened ID, revision and unsaved marker. **Choose annotation** is the empty choice. Selecting a drawing makes its controls appear. A new draft starts at revision zero.
- **Original saved scope / current pane** shows both scope records. A changed source scope does not change the saved annotation by itself.
- For each anchor, **Coordinate basis** choices are **Manual time**, **Projected bar offset**, and (only for a retained observed anchor) **Exact retained OHLC**. Changing to **Projected bar offset** uses the current chart date as origin and starts at offset zero; changing to **Manual time** uses the current time or prior origin.
- **Actual origin bar** lists actual bars from the retained history. It appears for projected offsets. **Signed logical bar offset** accepts a signed numeric offset relative to that origin. It is not a future timestamp.
- **Time · YYYY-MM-DD** appears for daily bars. Other timeframes show **Time · UTC epoch seconds**. **Exact entered price** takes the manual price; its units follow the recorded currency, or state that units are unverified.
- **Retained value for explicit snap** choices are **Close**, **Open**, **High**, and **Low**. **Use selected retained OHLC value** uses the selected chart date's exact retained bar and pins its source receipt. It is disabled for comparison views and incompatible scope. If no source pin or value exists, the app reports **Exact retained OHLC provenance is unavailable.**
- **Text** accepts up to 500 characters. **Color** selects a color. **Line width** choices are 1, 2, 3, and 4.
- **Save exact annotation revision** explicitly saves the current local drawing as a new exact revision. It is disabled during a workspace conflict. A save can fail if the workspace write conflicts; read the displayed status.
- **Remove annotation and save tombstone** marks the drawing deleted and saves that removal. The word “tombstone” means a saved removal record. It is an explicit workspace write.
- **Stage explicit rebind to this retained source scope** is disabled when the pane lacks any of instrument ID, currency, provider, feed, adjustment, session or timeframe, or when the pane is a comparison. It stages a scope change only. Save a new revision to persist it. Existing anchors and observed pins remain unchanged. Rebind any alert separately.
- **Create alert from this saved geometry** is enabled only for a saved, non-text, non-deleted drawing with compatible scope in a non-comparison pane. It reads eligible drawing options and opens an inactive alert draft. The user must choose a positive maximum source age and save the alert rule separately. If this exact drawing revision is not eligible, the app shows an error. It never substitutes the latest geometry.
- **Discard local edits / reopen saved** discards the current local draft and reloads the saved revision. For a new unsaved annotation, there is no saved version to restore.
- **Unresolved annotation coordinates** shows coordinate-resolution statuses. **Exact observed provenance** appears only for an observed anchor and shows its pinned source details. A manual/projected anchor is not a market fact.
- Drawing controls are disabled or unavailable on the indexed comparison. Switch to the raw OHLC chart before editing. Saving a drawing alone does not create an alert.

## Source-only chart analysis control inventory

The Chart inspector can expand **Chart analysis · transforms, studies, seasonality and formulas**. The browser saw the collapsed panel only; all controls below are source-only (app.js:1526–1595 and following analysis handlers).

- **Load saved definitions and calculation index** reads the saved definition list and calculation index. It does not collect market data or place an order. If metadata is unavailable, the app shows an error.
- **Saved definition revision** choices are **New definition** and retained definitions with kind and revision. Selecting a saved definition loads that exact revision and its pinned dependencies.
- **Reusable identifier · start with a letter; letters/digits/underscore** names a reusable definition.
- **Analysis kind** choices: transform, study, seasonality, formula.
- transform family choices: heikin_ashi, renko, kagi, line_break, point_figure. Fields: **Exact brick / box size**, **Reversal boxes**, **Kagi reversal basis** (fixed, percent), **Exact reversal amount / percent**, **Completed-line lookback**.
- study family choices: kama, cci, donchian, ichimoku. Fields vary by family: **Period / observations**; **Fast smoothing period**; **Slow smoothing period**; **CCI scale**; **Moving average** (SIMPLE); **Lag / actual bars**; **Conversion period**; **Base period**; **Span-B period**; **Forward / backward display displacement**. The app retains causal initialization, gaps and display placement details in the calculation record.
- seasonality fields: **Year comparison alignment** (calendar, session) and **Comparison scale** (raw, normalized). The current source adjustment is shown. If calculation data is available, **Yearly value scale** choices are **Common scale across years** and **Separate labeled scale per year**. Only completed eligible years enter the common denominator. MTD/YTD remain separate.
- formula fields: **Formula expression**; buttons for each supported function listed in loaded capabilities; **Output presentation** (line, histogram, overlay); **Declared output units** from loaded capabilities; **Forward display offset / logical bars**; scalar parameter rows with **Name**, **Exact decimal value**, **Units** (boolean units are excluded), **Remove parameter**, and **Add typed parameter**. Formula dependencies are checkboxes for exact saved formula/study revisions. Buttons such as **Insert name(parameters)** or **Insert DefinitionName__component** insert supported references. Source capability controls which functions and units appear; do not invent options.
- **Save immutable definition revision** writes a new immutable definition revision. It does not calculate. A valid definition name and available pinned dependency revisions are required. Errors are displayed in the panel.
- **Total chart budget / seconds, including queue wait** accepts whole seconds from 1 to 600. **Calculate exact saved revision** is disabled until an unchanged saved definition is selected. It calculates against the exact pinned raw artifact. One chart worker permits at most one running and one queued calculation; queue wait counts in the budget. Calculation may fail, expire in queue, or end without confirmed worker termination. Read status and execution evidence.
- **Export selected revision or full library** exports the chosen revision or full definition library. **Import validated definition bundle** accepts JSON. Import resolves exact revision/hash dependencies; collisions do not overwrite history. Import can fail validation.
- Saved calculation buttons show definition name/family-or-kind/revision/status, or IDs if the definition is missing. Their exact calculation record disclosure shows retained values. **Reopen exact saved chart calculation** and each saved calculation button open the exact stored calculation. **Cancel this calculation** appears only while queued/running. A cancellation may report that worker termination is unconfirmed.
- A completed result can show status, total budget, queue wait, elapsed and termination details; source pin, result hash, derivation identity, coverage, provisional inputs, exact geometry and definition details. These are record values, not fresh quotes.
- **Derived event · logical ordinal** selects one calculated event. It shows exact derived geometry and source range, not execution prices. **Actual retained source bar** selects a real contributing raw bar and displays **Open**, **High**, **Low**, **Close**, **Source volume**. **Open this actual bar in the raw chart** opens retained playback at that bar. It does not fill an order.
- Playback hides full-history analysis until playback ends. If no contributing raw bar exists, the display says so. If result coverage is incomplete, the app reports gaps or unverified continuity; inspect unavailable source ordinals. Do not treat a calculation status alone as proof of complete market data.
- Source import/export controls can access local files. Do not use them during a read-only tutorial unless the user asks for that action.

## Live observation and coverage

On 2026-10-24 I inspected Dashboard, Markets, and Research in the internal browser. I used navigation links only. I did not change filters or selections, save a workspace, start research, or collect data.

- Dashboard showed account verification; equity, cash, buying power, long-position value, open-order count; panel checkboxes for Watch, Chart, Research, Positions, and Orders; FANGMAN; quote update; edit-index link; search; **Show** choices (**All stocks**, **Selected for research**, **Held positions**, **Needs research today**, **Missing quotes**, **Stale quotes**); match selection and clear selection; select-page and per-stock research checkboxes; **Symbol** and **Last** sort buttons; **Change**; **Price source and time** disclosures; row count; page-size choices 25/50/100; disabled paging at 1/1. Live values: account verified, $100,000 equity/cash/buying power, $0 long position value, zero open orders, seven configured/selected stocks. Current quote rows displayed values and changes.
- Markets showed **Watchlists**, **Universe**, **Screener**, and **Saved scans** tabs. The visible view showed connected-account status, seven stocks, an **Unsaved workspace changes** notice, **Search symbol or company**, **View watchlist** with configured universe and named lists, collapsed **Filters, list management and batch actions**, batch-select checkbox, sortable **Stock / company**, **Latest price**, **Change %**, and **Price age** columns, **Saved research**, per-row batch checkbox, symbol inspection checkbox, and **Why in this view / source time** disclosure. The displayed market events were dated Oct 23 and labeled about one day old; freshness limit was not configured and market was closed. These values are observations only. I did not expand list controls or alter workspace state.
- Research showed **New research**, **Latest research per ticker / 2026-10-24**, completed status, **Prepare order from this research**, **Open instrument**, and **Saved orders**. The list exposed **Find research**; **Show** choices Latest stocks, Completed, Running, Queued, Failed, Cancelled; 7/7 complete counts and progress; **Select failed / unfinished for a new run**; symbol checkboxes with social-screening status and recommendation; page-size choices 25/50/100; disabled paging at 1/1. Detail tabs were **Summary**, **Reports**, **Debate**, **Sources**, **Activity**, and **Setup**. The observed detail was AAPL, Debate, with **Bull / bear debate** and **Risk committee** report choices, a populated debate, recommendation, rationale, and **Full source artifact** disclosure. This does not verify the content's accuracy or any action path.

Source inventory anchor: `tradingagents/web/static/app.js` contains page rendering (`renderOverview`, `renderResearch`, `renderChrome`), global view persistence (`persistView`), navigation, event handlers, and research actions. Markets data and workspace behavior are implemented across `tradingagents/web/static/lists.js`, `market-chart.js`, `tradingagents/web/market_discovery.py`, `market_history.py`, `market_evidence.py`, `workspace.py`, and `store.py`. Research admission, work and retention also pass through `tradingagents/web/service.py`, `tradingagents/web/store.py`, and the research graph. Source-only controls require their own permitted live observation before anyone reports them exercised.

Not opened in my pass: Markets' other three tabs, list-management disclosure, instrument tabs, chart inspectors and drawing controls, Research setup dialog, analyst/provider controls, running/failed/cancelled variants, dialogs and save/error/retry/conflict states. No collection, research, chart calculation, import/export, order preparation, or save was performed. Earlier live evidence is recorded above with its 2026-10-24 date and scope.

## Renderer and handler coverage (source-confirmed)

The browser pass did not trigger provider, research, calculation, save, import, export, subscription, or order actions. The paths below were traced in source. Their effects are source-only unless the live record above says otherwise.

- **Dashboard/watch list:** `renderOverview()` and `watchlist()` (`app.js:407–430`, `339–370`) render the account ledger, panels and stock rows. Delegated click/change/input handlers filter, sort, paginate, inspect symbols, change research selection and request quotes. Quote update uses `refreshQuotes()` (`app.js:23–43`) and the connected quote route; a quote refresh is not a provider history request.
- **Markets lists/universe:** `scannerMarkup()`, `scannerProgramMarkup()`, delegated scan handlers, and `scan_action()` (`app.js:1729–1777`; `market_discovery.py:343–447`) cover immutable definitions, one-shot runs, cancel, schedule, import/export, history, slots and exact run details. Save validates schema and exact saved chart-formula bindings, then appends a new definition revision; it does not run the scan and forces scheduling off. Snapshot targets copy the selected list membership/revision. Follow targets use the linked list. A run queues the exact saved id/revision and optional historical market cutoff. Scan source/disclosure controls distinguish retrospective cutoff from original knowledge evidence and expose collection consent. Cancel changes queued/running/canceling to `canceling`; the worker stops future requests and keeps receipts/results already received.

  Scheduling requires an existing saved scan and an explicit enabled/disabled boolean. It adds a schedule revision and due time; disabling does not delete the definition or history. Saving a new definition revision cancels active runs of the prior revision. Stale scan or workspace revisions reject writes. Bundle export can include the full library or one exact retained revision plus chart definitions. Import requires `scan-definitions-v1`, 1–1000 definitions, a chart-definition list and current scan/workspace revisions; it validates scan schemas and formula bindings. Imported schedules and alerts are off; a Follow scan must map to a local saved watchlist. Import preserves source lineage and writes immutable history.
- **Yahoo Screener:** `discoveryMarkup()` and delegated actions (`app.js:1839–1843`, `1879–1906`) submit criteria, page through the result, save/load named criteria and add selected matches to an existing list. **Add selected matches** only changes the selected watchlist. An eligible outside-universe row has a separate **Add this symbol to configured universe** action. `DeskService.discovery()` (`service.py:1003–1011`) requires an exact retained successful observation and a matching result row, then saves the symbol against the expected config revision. Empty success, provider failure and unavailable provider totals are separate states. Universe membership is not proof of a quote, tradability, or current evidence.
- **Instrument Options:** `optionMarkup()`/`bindOptions()` (`app.js:1861–1876`) call `option_discovery()` (`service.py:999–1079`), then `AlpacaREST.option_contracts()` (`alpaca_readonly.py:79–101`) for explicit contract discovery. Response pages and source receipts persist. Subscription changes validate the exact retained contract revision, explicit feed and homogeneous selected feed before native subscription configuration. This does not place an order.
- **Chart cache and evidence:** instrument rendering (`app.js:1439–1480`, `2489+`, `2572–2610`) reads retained quote, OHLCV, chart evidence and chart-analysis state. History request actions go through `/api/market-history` to `MarketDataJobs.request()` (`server.py:410+`; `market_history.py:256–311`). A request is queued and the worker fetches per symbol. It records received evidence even if later symbols fail or the job is cancelled. Status distinguishes `completed`, `completed_with_gaps`, `failed`, and `cancelled`; cancel stops future requests, not saved receipts. A resumed request processes unfinished symbols. Derivation errors leave indicators empty and record a problem (`market_history.py:496–542`).
- **Chart inspectors:** `chartAnalysisMarkup()` and `analysisAction()` (`app.js:1550–1604`) cover studies/formulas, immutable definitions, saved calculations, source pins and exact open/cancel. `DeskService.chart_analysis_action()` (`service.py:760–884`) rejects a non-integer or out-of-range budget (1–600 seconds), a missing or changed definition id/revision/hash, an unavailable exact source artifact, hash mismatch, closed admission, stale workspace revision, and a full worker queue. At most one job can run and one can wait. A calculation pins the exact saved definition and source. The worker can finish `completed`, `unavailable`, `failed`, or `interrupted`. The record includes a reason and termination evidence when available. A deadline or stop can leave it `interrupted`; do not assume the worker stopped until termination is confirmed. Open reads that job; cancel targets its exact id. Definition export includes the required prior revisions/dependencies; import validates immutable definitions and does not overwrite a collision.
- **Chart drawings:** drawing controls and pointer/key handlers (`app.js:1490–1524`; `market-chart.js`) stage a local draft, then use the revisioned workspace save path. Scope mismatch does not silently rebind an annotation. Pointer placement uses one click for a horizontal line and two for a trend line; Escape clears incomplete placement. Delete stages removal; save is separate. A workspace conflict prevents overwriting the newer revision; reload discards local unsaved workspace edits.
- **Research list and report tabs:** `renderResearch()`, report renderers, `researchButton()`, and delegated run/detail handlers (`app.js:626+`, `799–801`, `1284+`, `2460–2508`) read latest-per-ticker results and saved report artifacts. `launchResearch()` posts to `/api/runs` (`app.js:140`). `DeskService._start_run()` (`service.py:2120–2212`) validates date and current config revision, readiness, selected symbols within the configured universe, current Nautilus prices for today, and one-run-at-a-time admission. It captures current account context at run creation (not a historical portfolio snapshot), stores a queued run, then schedules the worker. Worker admission failure marks the run failed. Provider/source success means the boundary returned; it does not prove usable data. Coverage receipts have separate source, Gateway and social-screening ledgers. Run completion can coexist with optional-source gaps.
- **Research social screening:** the report’s “Screen 5 saved posts locally” uses the saved-post screening action (`screen_saved_posts` in `service.py` and the corresponding `app.js` handler). It classifies retained posts; it does not refetch Reddit/Stocktwits or rerun the research graph. The per-post screen changes saved evidence, so treat it as a write.

### Additional live observations from root’s read-only pass, 2026-10-24

Root used the internal browser for these views. No provider requests, calculations, saves, imports, exports, subscriptions, research runs, or orders were started. These are labels/states visible in that pass, not proof of back-end success.

- **Markets → Universe:** the Universe view and its filters/list actions were opened. **Screener:** criteria and saved-criteria controls were viewed; **Run current screen** was not used. **Saved scans:** Definition view, guided multi-timeframe controls, Advanced JSON, run-source/collection-consent, schedule opt-in, import/export, revision history, durable slots and Scan details were opened/read. Runs and Matches were empty. No definition was saved and no scan was run, scheduled, imported or exported.
- **META → Chart:** chart data loaded after an asynchronous read. All six inspectors were opened. **Load saved definitions and calculation index** read retained metadata. Unsaved Analysis kind selections exposed transform, study, seasonality and formula fields; the original transform selection was restored. Drawings showed the initial form with horizontal-line, trend-line and text choices, **Create numeric draft**, **Place with pointer**, and saved/draft selector. No annotation was created. Comparison showed that current-market context is required. Saved calculations exposed **Open saved calculations**. Source data showed Range, recorded business day, OHLC/prior close/movement, ticket-copy normalization disabled for missing currency, OHLCV artifact, indicators and agent-claim attribution. Playback initially showed **Pin these retained inputs for playback**. Pin was not selected.
- **META → Options:** the panel showed Contract query / JSON with default active/limit 25, request control, Retained page set to Latest retained page, feed choices Choose feed/opra/indicative, disabled **Apply chosen feed to all selected contracts**, **No retained option page**, Selected contracts and disabled package preparation. No request or selection was made.
- **META → Position:** the page showed no observed position and the embedded Human trade proposal with Entry/Review steps, side, shares, order type, limit, duration, session, replacement, notes, decision disclosures, preview and save controls. No ticket was previewed or saved. See Orders reference for ticket semantics.
- **META → Research:** Summary showed Full source artifact, disposition/review notes/prioritize controls and Save revision review, opposing arguments, Investor note and Save. Reports index showed Portfolio decision, Market analysis, Fundamentals, News analysis, Sentiment analysis, Research committee decision, Trader proposal, Social sentiment and Source coverage. Social sentiment offered **Screen 5 saved posts locally**; it was not clicked. Sources showed links and **Exact saved result identity, source metadata, and coverage**. Activity showed Run activity and JSON. Setup showed batch 7 and inspected META separately, links to Choose batch stocks in Markets and Research models and limits, and **Run research (7)**. Opening that button showed the confirmation dialog: **Close research workload review**, **Research 7**, 7 selected of 7 universe stocks, concurrency 7; Market/social/news/fundamentals analysts; fast model `gpt-6-luna`, deep model `gpt-6-sol`; NY date 2026-10-24; estimate about 8 minutes based on 7 completed stocks; cost unavailable and usage-limit warning; **Selected symbols** disclosure; separate **Start 7-stock research** button. The dialog was closed without Start. No note/review was saved; Screen was not clicked; no run started.

Playback boundary: Pin is client-side state, not a backend calculation. The handler creates a retainedReplay object, then `rememberChart()` saves its reference through browser `localStorage` (`app.js:1470–1473`, `1646–1653`). Therefore it was not clicked in this pass. Seeking and speed choices also call `rememberChart()`.

## Source map

- tradingagents/web/static/app.js: shell, Dashboard, Markets and Research renderers; delegated event handlers; option discovery widget; chart inspector and study/drawing/playback controls; research list and report tabs; local view state; workspace save UI.
- tradingagents/web/static/nautilus.js: native account/runtime status and session-profile rendering.
- tradingagents/web/static/market-chart.js: chart rendering, comparison alignment and pointer/drawing interactions.
- tradingagents/web/static/vendor/lightweight-charts/ and vendor/lightweight-charts-drawing/: pinned chart and drawing libraries.
- tradingagents/web/market_discovery.py: retained Yahoo discovery and option discovery records/state.
- tradingagents/web/alpaca_readonly.py: Alpaca contract lookup and option quote reads.
- tradingagents/web/service.py: discovery routing, source retention and native subscription configuration.
- tradingagents/web/market_history.py and market_evidence.py: retained market-history requests, evidence and chart source identity.
- tradingagents/web/workspace.py and store.py: revisioned workspace persistence and local records.
- Research orchestration continues through tradingagents/web/service.py into the TradingAgents graph; saved latest-per-ticker records and artifacts use store.py.

No chart_workspace.js exists in this checkout. Chart workspace controls are split across app.js, market-chart.js, the drawing library, workspace.py and service handlers.
