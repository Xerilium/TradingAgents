# UI Redesign Blueprint (v3 — Pro-Trader & Council Reconciled Master Spec)

This document is the master UI redesign blueprint for the TradingAgents desktop workspace (`http://127.0.0.1:8098/`). It combines:
1. Initial Impeccable (`shape`, `layout`, `distill`, `operate`) wireframes and industry benchmarks.
2. Independent design & backend-contract audits by **Claude Sonnet 5.5** (`docs/ui-redesign-review-sonnet.md`), **Grok 4.7** (`docs/ui-redesign-review-grok.md`), and **Gemini 4 Argon** (`docs/ui-redesign-review-argon.md`).
3. Fresh **Professional Stock Trader rubber-duck audits** by **Sonnet 5.5** and **Grok 4.7** (`docs/ui-redesign-trader-audit.md`).

- **Design system:** Keep the dark charcoal desk palette, green action accents, and tabular numbers from `DESIGN.md`.
- **Core safety rule:** Keep research, order preparation (proposals), order approval, and broker submission strictly separate (`PRODUCT.md`).
- **No fake backend fields:** Every wireframe element maps 1:1 to real fields and endpoints in `tradingagents/web/static/app.js`, `workflows.js`, and `server.py`.

---

## 1. What the Council & Pro-Trader Rubber-Duck Audits Fixed (v1 → v2 → v3)

### Phase A: Architecture & Contract Fixes (Sonnet / Grok / Argon Council)
1. **Separated "Inspected Stock" (`selectedSymbol`) from "Checked Research Batch" (`selectedSymbols`):**
   - Clicking a stock row changes only `selectedSymbol` (the stock you are reading in the chart, research, or ticket pane).
   - Checking a box changes `selectedSymbols` (the batch to run research on). Filtering a list never changes what is checked (`N checked (M hidden by filter)`), and the app never starts with all 24 universe stocks pre-checked.
2. **Kept the Compact Research Confirmation Step & Smart Launch Focus:**
   - Clicking **Run Research** opens the compact confirmation popover (`reviewResearch`: stock count, models, New York trade date, ETA if timing samples exist or `"No timing yet"`, and `"Places no orders"`). When `0` boxes are checked, the button offers **`Run Research (AMZN)`** for the currently focused stock instead of sitting dead.
   - If the focused symbol is in the launched batch (or nothing is being read), launch focuses the first batch stock; if the trader is reading another stock, it does not yank their reading pane away.
3. **Used the Real 7-State Research Progress Counts:**
   - Replaced the misleading green `24/24 finished` bar with the 7 real backend counts (`completed`, `incomplete`, `interrupted`, `failed`, `cancelled`, `running`, `queued`). Cancelled is neutral slate, never green.
   - A rating badge (`Buy`, `Hold`, `Underweight`, `Sell`) appears **only** when a final recommendation is saved. Cancelled stocks show `Cancelled — no verdict`, and `"Loading..."` clears immediately when loading ends.
4. **Cut Fixed Top Chrome to `80px` (`84%–91%` Data Height):**
   - Deleted `.workspace-footer` (`+36px`), deleted multi-paragraph page headers, and removed duplicate account numbers from the global top bar.
   - The real account figures (`Equity`, `Cash`, `Buying Power`, `Long Value`, `Open Orders` — no invented `Day P/L`) appear in a single `40px` strip on **Dashboard**, **Portfolio**, and the **Order Ticket**.
5. **Restored Every Real Desk Capability (Zero Dropped Features):**
   - Preserved `Markets` (`Universe & Watchlists`, `Yahoo Screener`, `Saved Scans`, `Options`, collapsible `.chart-inspectors`), `Portfolio → Proposed Model Portfolio` (separate from `Orders → Baskets`), `Orders` 3-stage lifecycle + `resolve_never_dispatched` recovery, `Strategy Lab` (`Saved-Plan Simulations` + `Walk-Forward Experiments` with immutable preview gate), and all 5 `Settings` categories.

### Phase B: Professional Stock Trader Fixes (`docs/ui-redesign-trader-audit.md`)
When fresh Sonnet and Grok rubber-duck subagents reviewed v2 **through the eyes of a professional stock trader**, they caught 6 critical workflow gaps that v3 fixes:

1. **Paired Every Research Verdict with Live Price, Research Age, and Post-Research Drift:**
   - A trader never acts on a rating without knowing how old it is and how much the stock has moved since `trade_date`.
   - Every research header and watchlist row now shows **`Rating · Age`** (`HOLD · 1d old`) and compares the **saved close on `trade_date`** (when bars are loaded) to the **live IEX quote** (`Saved close @ Oct 28: $249.70 → Now $252.51 IEX (+1.1% since)`), never confusing session `change_pct` with drift since the research date.
2. **Surfaced Live Position, Working Orders, and Unsent Drafts on Every Decision Surface:**
   - Every symbol header (`Markets`, `Research`, `Orders`, `Journal`) and watchlist row joins `positions()`, working `orders()`, and `state.investor.data.proposals` into a single **Exposure Chip**:
     `FLAT` or `LONG 40 @ $248.10 (+$182 / +1.8%) · WORKING: SELL 10 LMT $255.00 · DRAFT: BUY 9 rev 2`.
3. **Reordered Research Summary for Traders (PM Decision & Trader Plan First):**
   - Instead of burying the **Portfolio Manager Decision** and **Trader Proposal** in a collapsed footer below 4 analyst cards, `Research → Summary` now places the **Verdict + Price Drift + Exposure Strip** at top, followed immediately by **Portfolio Manager Decision & Trader Proposal (first 6 lines)**, then **Bull vs. Bear & Risk Trio**, then the **4 Analyst Status/Excerpt chips**, with **Disposition & Notes** moved to a compact bottom bar.
4. **Docked `Prepare Order` Drawer (No Context-Destroying Page Hops):**
   - Clicking **`[Prepare Order]`** on Research, Markets, Dashboard, or Journal opens a **docked Order Proposal Drawer** on the focused symbol (`openTicket(symbol)` + `researchPreparation`) right beside the Chart or Research report so the trader never loses sight of the chart or thesis.
   - Respects long-only cash account rules: if a stock is rated `Sell`/`Underweight` and `0` shares are held, it notes `0 shares held (cash account, long-only)` and never pre-selects an illegal short sell.
5. **Upgraded the Order Ticket with Live Quote/Spread, Click-to-Seed Limit, Sizing %, & Duplicate Guard:**
   - Shows live `IEX Last / Bid / Ask / Spread (bps)`, `Quote Age` (`42s old ✓` or `⚠ Quote age unchecked`), `Current Position`, and `Cash / Buying Power / Equity`.
   - Clicking `Bid`, `Ask`, or `Last` seeds the `Limit $` input (`"from ask, not previewed"`); typing `Qty` shows live `% of equity`, `% of cash`, and `post-trade weight %`; `Stop $` and `Target $` are visible upfront; and Stage 3 warns if a working order already exists for that symbol.
6. **Replaced Admin Table Columns with Trader Scan Columns & Safe Hotkeys:**
   - Default Watchlist / Markets columns: `SYM | LAST | CHG% | BID x ASK (SPR) | POS | UPL% | WORKING | RATING · AGE` (moving `BARS 1,255` into the chart history bar and replacing repeated `Closed` cells with actual quote age / stale flags).
   - Added full **Populated Portfolio Positions** wireframe and `LAST NOW / DRIFT % / YOUR POS` columns on `Proposed Model Portfolio`.
   - Defined safe trader hotkeys (`J/K` move focus, `X/Space` toggle batch check, `Enter` open research or preview ticket, `T` toggle docked ticket — no hotkey ever approves or submits an order).

---

## 2. Industry Leader Patterns Adopted

Benchmarked against **Fidelity Active Trader Pro**, **IBKR Desktop (Mosaic)**, **TradingView Desktop**, **Koyfin**, and **FinChat / Fiscal.ai**:

| Platform | Pattern Adopted | How It Applies to TradingAgents |
|---|---|---|
| **Fidelity Active Trader Pro** | **Focus Symbol vs. Batch Set + Multi-Step Ticket Preview** | Clicking a row updates linked panes (`selectedSymbol`); checkboxes control the batch (`selectedSymbols`). Order tickets require Save Draft → Check/Approve → Submit. |
| **IBKR Desktop (Mosaic)** | **Single-Line Toolbar + Docked Sub-Modes** | Watchlists, Yahoo Screener, and Saved Scans switch inside one `40px` Markets bar while the right-hand instrument pane stays docked. |
| **TradingView Desktop** | **85%+ Canvas + Collapsible Right Inspector Drawer** | Chart Studies, Drawings, Comparison, and Source Data stay in the collapsible `.chart-inspectors` drawer so the chart gets full width and height. |
| **Koyfin** | **Dense Tabular Scorecards + Signed Formatting** | Uniform `tabular-nums`, signed green/rose percentages, compact 1-line empty states, and 25/50/100 paging. |
| **FinChat / Fiscal.ai** | **Verdict & Provenance First, Prose Second** | Research opens with Verdict + Coverage Gaps + Analyst Excerpts + Bull/Bear columns + Source domains/dates before the expandable Portfolio Manager text. |

---

## 3. User Personas & Anti-Persona

1. **Alex — Daily Active Desk Operator (Primary):** Scans a 10–1,000 stock universe, checks movers on Research or Markets, runs AI research, reads the verdict and bull/bear case in under a minute, and prepares paper orders.
2. **Jordan — Methodical Fundamental Researcher:** Audits the full evidence chain—analyst reports, bull vs. bear debate, dated source links, HTTP 429 coverage gaps, and Decision Journal outcomes.
3. **Morgan — Workflow & Strategy Architect:** Customizes the 18-node agent workflow and 94 prompt files in Workflows, and runs saved-plan simulations and walk-forward experiments in Strategy Lab.
4. **Sam — First-Run Operator:** Opens the desk with an empty account, no cached price bars, or unset quote-age limits; needs calm, 1-line setup guidance instead of red error walls or clipped buttons.
5. **Riley — Recovery & Operations Operator:** Handles service restarts, paused order gates, or timed-out order commands (`outcome_unknown`) without risking duplicate broker submissions.
6. **Anti-Persona — Autonomous Autopilot Trader:** Nobody uses this desk for one-click unreviewed trading. Every shortcut preserves separate preparation, approval, and submission.

---

## 4. Complete User Stories & Acceptance Criteria (US-01 to US-28)

| ID | Persona | User Story | Acceptance Criteria |
|---|---|---|---|
| **US-01** | Alex | Pick stocks and start research directly on **Research**. | Research toolbar has an inline universe search/picker, `Select unfinished`, `Clear`, and `Run Research (N)` (which opens the compact confirm popover). Zero trips to Markets required. |
| **US-02** | Alex | Auto-focus the first running stock when research starts. | Confirming a run sets `selectedSymbol` to the first symbol in the batch, scrolls it into view in the left list, and opens `Summary`. |
| **US-03** | Jordan | See honest 7-state run progress at a glance. | Progress strip shows `completed`, `incomplete`, `interrupted`, `failed`, `cancelled`, `running`, and `queued`. Cancelled is neutral slate, never green `"finished"`. |
| **US-04** | Jordan | See the verdict, analyst excerpts, social counts, and debate before long prose. | Research `Summary` shows: (1) Verdict Strip (rating badge only if saved, trade date, completion gaps), (2) 4 Analyst Excerpt Cards + Laya social counts, (3) Bull/Bear & Risk excerpts, (4) Disposition link, and (5) expandable full Portfolio Manager decision. |
| **US-05** | Alex | Dedicate **84%–91% of viewport height** to data panes. | Fixed top chrome is capped at `~80px` (`36px` App Bar + `40px` Workspace Bar + `6px` status strip). `.workspace-footer` and multi-paragraph page headers are removed. |
| **US-06** | Alex | Prepare an order from Research without skipping safety gates. | Clicking `Prepare Order` stages/opens a human order proposal with linked research context; approval and broker submission remain separate steps. |
| **US-07** | Alex | View Dashboard without clipped buttons or 24 pre-checked rows. | Watchlist starts with `0 checked`. Empty Positions and Open Orders use compact 2-line states that never clip at `1080p` or `900p`. |
| **US-08** | Alex | Inspect charts at full height on Markets with 1-line history backfill. | Markets uses a 2-column split (left list with 25/50/100 pager; right Chart/Research/Options/Position pane). The 10-field backfill form collapses into a 1-line bar (`[Get 252 daily bars] [More ▾]`). |
| **US-09** | Riley | See order readiness, confirm exact terms, and recover from uncertain outcomes. | Orders shows a 1-line readiness banner, 3 explicit stages (Draft → Approve → Submit), inline confirm + receipt for Submit/Cancel/Replace, and `resolve_never_dispatched` recovery when an order outcome is unknown. |
| **US-10** | Morgan | Fit the entire 18-node workflow diagram on screen and click nodes to edit prompts. | Workflows adds `Fit All` (zoom floor `0.25`), shows a Retry banner if rendering fails, and loads a node's primary prompt and related files when clicked. |
| **US-11** | Morgan | Run both Saved-Plan Simulations and Walk-Forward Experiments cleanly. | Strategy Lab exposes both real engines in a 3-step left accordion (`360px`) with the required immutable preview gate, and shows equity curves + metrics on the right. |
| **US-12** | Jordan | Read plain English labels everywhere, with raw hashes/JSON in `Technical record`. | Replaces `human_proposal`, `needs_review`, `STOP_LIMIT`, and raw UUIDs with plain labels; moves raw JSON/hashes into `<details>Technical record</details>`. |
| **US-13** | Sam | See calm 1-line first-run actions on empty panes. | Empty panes show one plain sentence and one next-step button (e.g., `[Collect Account History in Journal →]`), never a 1660×817px empty SVG or empty table headers. |
| **US-14** | Alex | Keep `selectedSymbol` (reading) separate from `selectedSymbols` (checked batch). | Clicking a row never changes checkboxes; checking a box never changes the inspected stock. Toolbar displays `N checked · reading SYM`. |
| **US-15** | Alex | Filter and retry failed or unfinished research stocks in one click. | Research queue includes a `Select unfinished / failed (N)` action that populates the batch set and opens the confirm popover. |
| **US-16** | Alex | Stop an active research run safely. | `Stop run` is visible while a run is active, confirms once, and marks remaining queued symbols as `Cancelled`. |
| **US-17** | Alex | Delete saved research records behind a `Manage / Delete` toggle. | The 5-control delete toolbar and delete checkboxes stay hidden until `[Manage]` is toggled, then show a preview confirmation before deleting. |
| **US-18** | Jordan | Switch watchlists, use the Shortlist, and customize columns on Markets. | Markets list toolbar includes the watchlist switcher, `[+ New]`, `[Columns ▾]`, and `[Manage]` without stacking multiple bars. |
| **US-19** | Jordan | Run Yahoo Screener and Saved Multi-Timeframe Scans on Markets. | Top Markets tablist switches cleanly between `Universe & Watchlists`, `Yahoo Screener`, and `Saved Scans`. |
| **US-20** | Jordan | Record and search decision notes without losing input focus. | Typing in `#decision-search` on Journal filters rows in place without rebuilding the input or losing caret focus. |
| **US-21** | Jordan | Use Chart Studies, Drawings, Comparison, and Option Chains on Markets. | Right-hand `.chart-inspectors` drawer toggles open on demand; `Options` tab is disabled with a clear tooltip when a stock has no option data. |
| **US-22** | Morgan | Synthesize the session-only AI Proposed Model Portfolio on Portfolio. | `Portfolio → Proposed` runs joint synthesis over completed research with `$10,000` model capital, showing whole shares, residual cash, and excluded stocks separately from Human Baskets. |
| **US-23** | Riley | Prevent double-submission on Order Submit, Cancel, and Replace. | In-flight buttons disable immediately on click and require a 2-step inline confirmation showing exact terms. |
| **US-24** | Riley | Spot and resolve `recovery_required` states immediately after a restart. | When `commands.recovery_required` is true, a 1-line header banner links directly to the Orders recovery controls. |
| **US-25** | Riley | Use one consistent phrase for the order gate across the entire app. | Sidebar, Top Bar, Orders, and Settings all use `Orders: Active` / `Orders: Paused` (`[Pause new orders]` / `[Resume new orders]`), never mixing `"unblocked"` or `"Stop Nautilus"`. |
| **US-26** | All | Navigate all tabs and dialogs with the keyboard. | All sub-tabs use WAI-ARIA `role="tablist"` with roving `tabindex` and Left/Right arrow keys; popovers and `<dialog>` modals close on `Escape` and restore focus. |
| **US-27** | All | Read every chart via a text summary and expandable data table. | All 4 SVG charts (Dashboard, Markets, Portfolio Performance, Strategy Lab) use hollow down-candles, dashed/solid legends, and a `<details>` table of recent observations. |
| **US-28** | Alex | Manage the 1,000-stock universe, 10 trading rules, and native cache captures in Settings. | Settings preserves all 5 categories (`Account & Engine`, `Research & Models`, `Universe & Keys`, `Trading Rules & Native Cache`, `Diagnostics & Backup`) with progressive disclosure. |

---

## 5. Screen Real-Estate & Anti-Clutter Contract

1. **Pixel Budget on Desktop (`1920×1080` and `1440×900`):**
   - **Global App Bar:** `36px` single line (Workspace title, Symbol search, Quote/Account freshness timestamp, Alerts bell with unread count, `Orders: Active / Paused` pill).
   - **Workspace Toolbar:** `40px` single line (Sub-tabs with `role="tablist"` + batch status chip + primary action).
   - **Status / Progress Strip:** `6px` bar + `24px` 1-line summary only when active or needed.
   - **Footer:** Removed (`0px`, saving `36px`).
   - **Result:** **84% to 91% of vertical height** belongs strictly to data panes.
2. **One Focus Symbol (`selectedSymbol`) vs. One Batch Set (`selectedSymbols`):**
   - Row click = inspect (`selectedSymbol`).
   - Checkbox = batch (`selectedSymbols`).
   - Delete checkboxes in Research live only inside the `[Manage]` mode and never overwrite `selectedSymbols`.
3. **Direct DOM Rendering (No Post-Render DOM Scraping):**
   - Delete fragile post-render DOM-moving helpers (`layoutOrders`, `layoutBasketGroups`, `layoutMarkets`, `compactScannerMarkup`, and sibling-scraping loops in `renderAlerts`/`renderSettingsDiagnostics`). Render directly into the target 2-column and tabpanel templates.

---

## 6. Page-by-Page Reconciled Wireframes

### 6.1 Global Shell (`index.html` — `36px` App Bar, `188px` Nav Rail, Zero Footer)

```text
+---------------+------------------------------------------------------------------------------------------+
| TradingAgents | RESEARCH · PNIS (24)    [Find symbol: AMZN___]    Quotes 16:00 ET [⟳]   [🔔 1] [Orders:  |
| Paper Desk    |                                                                          Active ▾]       |
+---------------+------------------------------------------------------------------------------------------+
| [⊞] Dashboard | WORKSPACE TOOLBAR (40px): [Role="tablist" Sub-Tabs] · Scope Chip · Primary Action        |
| [📈] Markets  +------------------------------------------------------------------------------------------+
| [🔬] Research*|                                                                                          |
| [💼] Portfolio|                           DATA CANVAS (84% – 91% OF HEIGHT)                              |
| [🧾] Orders(1)|                   • Zero multi-paragraph prose banners above tables                      |
| [🧪] Strat Lab|                   • Single independent scrollbar per pane                                |
| [📓] Journal  |                   • All tabs use role="tablist" + ArrowLeft/ArrowRight                   |
| [🔔] Alerts(1)|                                                                                          |
| [🕸] Workflows|                                                                                          |
| [⚙] Settings  |                                                                                          |
| ------------- |                                                                                          |
| ● Nautilus OK |                                                                                          |
| ● Laya CPU OK |                                                                                          |
| ● Market Closd|                                                                                          |
+---------------+------------------------------------------------------------------------------------------+
```

---

### 6.2 Dashboard (`#overview`) — Morning Triage Strip, 5-KPI Bar & Trader Command Grid

- **Pro-Trader upgrades:**
  - Restores the 1-line **Needs Attention** morning triage strip (`dashboardAttentionSummary`: working orders, unread alerts, stale quotes, held positions needing fresh research) and hides it when empty.
  - Uses trader scan columns (`SYM | LAST | CHG% | SPR | POS | WORKING | RATING · AGE`), defaulting to `Held first` + `|Chg %|` movers, with `0 checked` initially.
  - When `0` boxes are checked, `[Run Research (AMZN)]` offers to run the currently focused stock.
  - Bottom panes use compact states that never clip, and `Saved Research` shows rating age, price drift since `trade_date`, and a `[Prepare Order]` button that opens the docked order proposal drawer.

```text
+----------------------------------------------------------------------------------------------------------+
| DASHBOARD · Observed Oct 28, 20:35 ET   [⚠ Needs attention: 1 unread alert · 21 unresearched] [Select 21]|
+----------------------------------------------------------------------------------------------------------+
| EQUITY $100,000.00 | CASH $100,000.00 | BUYING POWER $100,000.00 | LONG VALUE $0.00 | OPEN ORDERS 0      |
+--------------------------------------------------+-------------------------------------------------------+
| WATCHLIST (24)  [☑ Held first] [Sort: |Chg%| v]  | AMZN · $252.51 (+1.14%) · Bid 252.40 x 252.60 (8bp)   |
| [Search...] [View: All v] [Batch: 0] [Run (AMZN)]| YOU: FLAT · WORKING: — · DRAFT: —    [Open in Markets]|
+--------------------------------------------------+-------------------------------------------------------+
| [ ] SYM   LAST    CHG%   SPR  POS  WRK  RSCH·AGE | Period: [1W] [*1M*] [3M] [6M]   Legend: ■Up □Dn —SMA20|
| [ ] AMZN* 252.51  +1.14% 8bp  —    —    Hold·1d  |  260 |          .|.                                   |
| [ ] INTC   22.40  -0.85% 5bp  —    —    Undw·1d  |  255 |      .|. |■|  .|.                              |
| [ ] TER   108.12  -1.40% 9bp  —    —    Sell·1d  |  250 |  .|. |□|      |■|                              |
| [ ] AAPL  231.10  +0.42% 4bp  —    —    Cancel   |  245 |________________________________________________|
| [ ] NVDA  141.80  +2.10% 6bp  —    —    Cancel   |  Vol |  ||  |||  ||  ||||   Source: Saved 1Day (IEX)  |
| J/K move · X check · Enter research · T ticket   | [▸ Recent OHLCV bars table (22 sessions)]             |
+-------------------------------+------------------+-----------------------------------+-------------------+
| SAVED RESEARCH: AMZN          | POSITIONS (0)                    | OPEN ORDERS (0) & DRAFTS (1)          |
+-------------------------------+----------------------------------+---------------------------------------+
| [HOLD · 1d] Close@10-28 249.70| No open positions in Alpaca.     | Working orders: 0                     |
| Now 252.51 (+1.1% since rsch) | Cash account, long only.         | Unsent drafts: SGOV BUY 1 MKT (rev 2) |
| [Read Report] [Prepare Order] | [Browse Markets]                 | [Open SGOV in Ticket]                 |
+-------------------------------+----------------------------------+---------------------------------------+
```

---

### 6.3 Markets (`#markets`) — Persistent Instrument Header, Trader Scan Table & Docked Ticket

- **Pro-Trader upgrades:**
  - Drops developer-plumbing `BARS 1,255` from the scan table (moves it to the 1-line chart history bar) and shows **`SYM | LAST | CHG% | BID x ASK | POS | WORKING | RATING · AGE`**.
  - Adds a **persistent Instrument Header Strip** above the right-pane tabs so the trader always sees live IEX price, Bid/Ask/Spread, Position (`LONG` / `FLAT`), Working Orders, Unsent Drafts, and Research Rating + Age.
  - Clicking `Last`, `Bid`, or `Ask` seeds the docked Order Ticket's `Limit $` field; clicking `[Prepare Order (T)]` docks the order proposal drawer beside the chart so the trader never loses the chart while staging a proposal!

```text
+----------------------------------------------------------------------------------------------------------+
| MARKETS   [*Universe & Watchlists (24)*] [Yahoo Screener] [Saved Scans]   0 checked · [Run Research (AMZN)]|
+----------------------------------------+-----------------------------------------------------------------+
| List: [All Universe: PNIS (24) v] [+New]| AMZN  $252.51 (+1.14%)  [Bid 252.40] x [Ask 252.60] (8bp) · 42s|
| [Search...] [View: All v] [Sortv] [Ed] | YOU: FLAT · WORKING: — · DRAFT: — · RSCH: [HOLD · 1d (+1.1%)]   |
+----------------------------------------+-----------------------------------------------------------------+
| SYM    LAST    CHG%   SPR  POS  RSCH   | Tabs: [*Chart*] [Research] [Options (none)]   [Prepare Order(T)]|
| AMZN*  252.51  +1.14% 8bp  —    Hold·1d| Source: [*Live IEX Cache* | Research Date]  [*1Day*] [1Hr] [15m]|
| INTC    22.40  -0.85% 5bp  —    Undw·1d| Drawers: [Studies & Formulas] [Drawings] [Comparison] [Alert+$] |
| TER    108.12  -1.40% 9bp  —    Sell·1d| +-------------------------------------------------------------+ |
| AAPL   231.10  +0.42% 4bp  —    Cancel | | History: 1,255 daily bars cached (Oct 28) · [Refresh] [More]| |
| GOOGL  182.30  -0.12% 6bp  —    Cancel | +-------------------------------------------------------------+ |
| META   590.40  +1.85% 7bp  —    Cancel | |                                                             | |
| MSFT   428.15  +0.33% 5bp  —    Cancel | |             FULL-HEIGHT LIGHTWEIGHT CHART                   | |
| NVDA   141.80  +2.10% 6bp  —    Cancel | |     (Clicking [Prepare Order (T)] opens a slim docked       | |
| ... sticky-header scroll (25/50/100    | |      Order Proposal rail right beside this chart;           | |
|     batch scope in [Ed] menu)          | |      clicking Bid/Ask seeds Limit $; bar copy validates)    | |
|                                        | +-------------------------------------------------------------+ |
|                                        | [▸ Selected bar readout & OHLCV table (a11y / keyboard)]        |
+----------------------------------------+-----------------------------------------------------------------+
```

---

### 6.4 Research (`#research`) — Price Drift Header, PM Decision First, & 7-State Queue

- **Pro-Trader upgrades (Solves U1, U2, L3, L4, and Trader Dealbreakers 1 & 2):**
  1. **Pick & Run on Research (U1):** Check stocks in the left rail or use `[Select Unfinished (21)]` / `[Not Researched Today]`, then click `[▶ Run Research (N)...]` to open the compact confirmation popover.
  2. **Verdict Paired with Live Price, Research Age & Drift:** Shows `HOLD · 1d old (2026-10-28)` next to `Saved close @ Oct 28: $249.70 → Now $252.51 IEX (+1.1% since)` (or `Research-date close not loaded — [Open chart]`) plus `YOU: FLAT · WORKING: — · DRAFT: —`.
  3. **PM Decision & Trader Proposal Above the Fold:** Places the first 6 lines of `final_trade_decision` and `trader_investment_plan` right under the verdict strip, followed by `Bull vs. Bear` and `Risk Trio` columns, then the compact 4-Analyst status/excerpt row.
  4. **Docked `Prepare Order` Drawer:** Opens the proposal drawer in place without leaving Research; disables SELL when `0` shares are held on a long-only cash account.

```text
+----------------------------------------------------------------------------------------------------------+
| RESEARCH  Batch: 2 checked [Unfinished (21)] [Needs Today] [Clear]  [▶ Run Research (2) · places no order]|
+----------------------------------------------------------------------------------------------------------+
| Queue: [===3 Rated===|-------------21 Cancelled-------------] 3 completed · 21 cancelled · 0 running     |
+-------------------------------+--------------------------------------------------------------------------+
| STOCKS (24)  [Filter: All v]  | AMZN  Last $252.51 (+1.14%)  Bid 252.40 x 252.60 · IEX 42s   [Prepare ▾] |
| [Search...]          [Manage] | YOU: FLAT · WORKING: — · DRAFT: — · Review required: No                  |
+-------------------------------+--------------------------------------------------------------------------+
| [ ] SYM   RSCH·AGE  DRIFT POS | Tabs: [*Summary*] [Reports (7)] [Debate & Risk] [Sources (9)] [Activity] |
| [x] AMZN* Hold·1d   +1.1% —   | +----------------------------------------------------------------------+ |
| [x] INTC  Undw·1d   -0.4% —   | | [HOLD] · 1d old (2026-10-28) · Saved close $249.70 → Now +1.1%       | |
| [ ] TER   Sell·1d   -1.2% —   | | Coverage: 6/7 reports · ⚠ News gap: HTTP 429 (built without News)    | |
| [ ] AAPL  Cancelled —     —   | +----------------------------------------------------------------------+ |
| [ ] GOOGL Cancelled —     —   |                                                                          |
| [ ] META  Cancelled —     —   | +----------------------------------+ +---------------------------------+ |
| [ ] MSFT  Cancelled —     —   | | PORTFOLIO MANAGER DECISION       | | TRADER PROPOSAL                 | |
| [ ] NVDA  Cancelled —     —   | | First 6 lines of saved           | | First 6 lines of saved          | |
| ...                           | | `final_trade_decision`...        | | `trader_investment_plan`...     | |
| (Row click = inspect;         | | [Read full PM decision ->]       | | Agent claims (dated, unmapped)  | |
|  X/Checkbox = run batch;      | +----------------------------------+ +---------------------------------+ |
|  [Manage] = delete checks)    |                                                                          |
|                               | +----------------------------------+ +---------------------------------+ |
|                               | | BULL vs BEAR DEBATE (Saved)      | | RISK COMMITTEE (3-Way Saved)    | |
|                               | | Bull & Bear researcher lines +   | | Aggressive / Neutral / Conserv. | |
|                               | | Research Manager synthesis...    | | lines & Risk Judge synthesis... | |
|                               | | [Open full debate ->]            | | [Open risk debate ->]           | |
|                               | +----------------------------------+ +---------------------------------+ |
|                               |                                                                          |
|                               | ANALYSTS: [Market ✓] [Fundamentals ✓] [News ⚠ HTTP 429] [Social: 12↑ 3↓] |
|                               | Footer: Disposition [Needs review v] Note [______________] [Save] [Tech▸]|
+-------------------------------+--------------------------------------------------------------------------+
```

---

### 6.5 Portfolio (`#portfolio`) — Populated Holdings Risk Table, Proposed Model with Live Drift, & Performance

- **Pro-Trader upgrades:**
  - Draws both the **Populated Positions Risk Table** (`SYM | QTY | AVG COST | LAST | QUOTE CHG% | MKT VALUE | UNREAL P/L ($, %) | WT% | WORKING | RESEARCH · AGE | ACTIONS`) and the compact `0 positions` state.
  - On **Proposed Model Portfolio**, shows `LAST NOW`, `DRIFT %`, and `YOUR POS` right beside `MODEL REF PRICE (DATED)` so a trader never confuses a stale reference price with current execution prices.
  - Caps empty Performance chart to `140px` with `[Collect Account History in Journal →]`.

```text
+----------------------------------------------------------------------------------------------------------+
| PORTFOLIO   Tabs: [*Positions*]  [Proposed Model Portfolio]  [Performance]             [Refresh Account] |
+----------------------------------------------------------------------------------------------------------+
| EQUITY $100,000 | CASH $90,385 | BUYING POWER $90,385 | LONG VALUE $9,615 | UNREAL P/L +$754 (+8.5%) ✓   |
+----------------------------------------------------------------------------------------------------------+
| (TAB 1: POSITIONS — Populated Holdings Risk Table; when 0 positions, shows compact 2-line empty card:)   |
| SYM   QTY  AVG COST  LAST    Q.CHG%  MKT VAL   UNREAL P/L ($, %)   WT%   WORKING          RSCH·AGE   ACT |
| NVDA  50   $128.40   $141.80 +2.10%  $7,090.00 +$670.00 (+10.4%)   7.1%  SELL 20 LMT 150  Buy·3d ⚠  [Exit]|
| AMZN  10   $244.10   $252.51 +1.14%  $2,525.10 +$84.10  (+3.4%)    2.5%  —                Hold·1d   [Exit]|
| [▸ Technical reconciliation record (native cache, broker snapshot & epoch details)]                      |
|                                                                                                          |
| (TAB 2: PROPOSED MODEL PORTFOLIO — Session-only joint synthesis; pairs Model Ref with Live Quote:)       |
| +------------------------------------------------------------------------------------------------------+ |
| | JOINT AI MODEL PORTFOLIO (Session-Only Advisory Synthesis · Does Not Stage or Approve Orders)        | |
| | Model Capital (USD): [$10,000.00 ]  [▶ Model Portfolio]   Eligible: 3 of 24 stocks · 21 excluded     | |
| | SYM   WT%     SHARES  MODEL REF (DATED)     LAST NOW (IEX)    DRIFT   YOUR POS    RATIONALE          | |
| | AMZN  25.00%  9 sh    $252.51 (Oct 28)      $252.51 (Closed)  0.0%    LONG 10     [▸ View rationale] | |
| | Residual Model Cash: $7,727.41 · [▸ Excluded stocks (21): AAPL (cancelled), INTC (0% weight)...]     | |
| +------------------------------------------------------------------------------------------------------+ |
|                                                                                                          |
| (TAB 3: PERFORMANCE — Capped 140px empty state when <2 captures exist, fixing L2:)                       |
| +------------------------------------------------------------------------------------------------------+ |
| | View: [*Equity*] [Returns %]   Saved Interval: [No saved intervals v]   Basis: Broker-reported USD   | |
| | [📈 24px] Needs at least 2 saved account-history observations. [Collect Account History in Journal->]| |
| +------------------------------------------------------------------------------------------------------+ |
```

---

### 6.6 Orders (`#orders`) — Full-Context Ticket, Sizing Math, Same-Symbol Blotter, & 3-Stage Chain

- **Pro-Trader upgrades:**
  - Shows live **IEX Last, Bid, Ask, Spread (bps), Quote Age (`42s ✓` or `⚠ Quote age unchecked`), Current Position, Working Orders in that symbol, and Cash/Buying Power/Equity** at the top of the ticket.
  - Defaults Order Type to **`LIMIT`** (not `MARKET`), and makes `[Bid]`, `[Ask]`, and `[Last]` clickable to seed `Limit $` (`"from ask, not previewed"`).
  - Shows live **Position-Sizing Math** (`20 sh ≈ $5,052.00 = 5.1% of equity · 5.1% of cash · weight after: 5.1%`) and keeps optional `Stop $` / `Target $` visible upfront.
  - Keeps **Working Orders & Unsent Drafts** visible in the right-hand blotter (filtering/highlighting the ticket's symbol first so an unrelated `SGOV` draft never hijacks an `AMZN` ticket), displays the **exact failed policy rule** when blocked, and warns before Stage 3 Submit if a working order already exists for that symbol.

```text
+----------------------------------------------------------------------------------------------------------+
| ORDERS   [*Order Ticket & Blotter*] [Baskets] [Fills & Audit History]          [Orders: Active · Pause ▾]|
+----------------------------------------------------------------------------------------------------------+
| Readiness: Ready · Cash $100,000.00 · Buying Power $100,000.00 (Cash acct, long only) · Policy rev 1     |
+-------------------------------------------------+--------------------------------------------------------+
| STAGE 1: PREPARE ORDER PROPOSAL (46% width)     | STAGE 2 & 3: APPROVE, SUBMIT & LIVE BLOTTER (54% width)|
+-------------------------------------------------+--------------------------------------------------------+
| Symbol: [AMZN  ]  Last [252.51]  [Bid 252.40] x [Ask 252.60] (8bp) · IEX 42s ✓                           |
| YOU: FLAT (0 sh) · WORKING IN AMZN: none · RSCH: [HOLD · 1d (+1.1% since close)]                         |
| ----------------------------------------------- | SELECTED DRAFT: AMZN · Rev #3 (or click any draft row) |
| Asset: [*US Equity*] [US Option / MLeg]         | Terms: BUY 20 AMZN · LMT $252.60 · DAY · Regular       |
| Side:  [(*) Buy  ( ) Sell]   Type: [Limit    v] | ------------------------------------------------------ |
| Qty:   [20      ] sh  Limit $: [252.60] (←Ask)  | STAGE 2: POLICY CHECK & SINGLE-USE APPROVAL            |
| TIF:   [DAY     v]    Session: [Regular      v] | Policy Check: Passed all 10 rules (Spread 8bp ≤ max)   |
| Sizing: ≈ $5,052.00 · 5.1% Equity · 5.1% Cash   | [1. Check Order]   [2. Approve Exact Revision #3]      |
| Exits:  Stop $ [______]  Target $ [______]      | ------------------------------------------------------ |
| [▸ Bracket / OTO / OCO & Replace working order] | STAGE 3: SEPARATE BROKER SUBMISSION                    |
|                                                 | Duplicate Check: 0 working orders in AMZN              |
| [Preview Impact (Enter)]  [Save Draft Revision] | [3. Submit Approved Order to Alpaca Paper]             |
| (Draft ≠ Approved ≠ Submitted)                  | (If outcome_unknown: [! Refresh before acting]         |
|                                                 |  [Refresh Status] [Resolve Never Dispatched])          |
|                                                 | ------------------------------------------------------ |
|                                                 | WORKING BROKER ORDERS (0) & UNSENT DRAFTS (1):         |
|                                                 | SYM   SIDE  QTY  TYPE       STATUS        ACTION       |
|                                                 | SGOV  BUY   1    MKT · DAY  Draft (rev 2) [Load Ticket]|
|                                                 | [▸ Technical record (Terms SHA-256 & audit trail)]     |
+-------------------------------------------------+--------------------------------------------------------+
```

---

### 6.7 Strategy Lab (`#strategy`) — Saved-Plan Simulations & Walk-Forward Experiments

- **Contract notes:** Preserves both real evaluation engines (`Saved-Plan Simulations` and `Walk-Forward Experiments` with declarative rules & Optuna/Grid search) and the required **Save Immutable Preview** gate before running. Places `[Load Saved Plans & Data]` below the heading (fixes L10), keeps a 2-line visible scope notice, and orders right-pane tabs as `[*Preview & Results*] [Runs & Compare]`.

```text
+----------------------------------------------------------------------------------------------------------+
| STRATEGY LAB   Engine: [*Saved-Plan Simulations*] [Walk-Forward Experiments]   [Load Saved Plans & Data] |
+----------------------------------------+-----------------------------------------------------------------+
| SETUP RAIL (360px, 3-Step Accordion)   | EVALUATION CANVAS   Tabs: [*Preview & Results*] [Runs & Compare]|
+----------------------------------------+-----------------------------------------------------------------+
| [! Scope: Isolated model over cached   | SELECTED RUN: Simulation #sim-01 · Status: [Completed]          |
|    bars; never proves broker fills.]   |                                                                 |
|                                        | MODELED EQUITY CURVE (with dashed benchmark & table toggle):    |
| ▾ 1. PLAN / STRATEGY & HISTORY RECEIPT | +-------------------------------------------------------------+ |
|   Saved Plan:  [BUY 1 SGOV MKT       v]| | $1,010 |        _______________                             | |
|   History Key: [AMZN 1Day (1,255b)   v]| | $1,000 |_______/               \_______________             | |
|   Window:      [2026-10-12]–[10-19]    | |   $990 |____________________________________________________| |
|   Basis:       [Hindsight scenario   v]| | Legend: — Modeled Equity ($1,000.00)  - - Benchmark         | |
|                                        | | [▸ View dated equity & bar observations table]              | |
| ▸ 2. CAPITAL, FEES & FILL ASSUMPTIONS  | +-------------------------------------------------------------+ |
|   Cash: $1,000 · Fee: $0 · Fill: 100%  |                                                                 |
|                                        | SUMMARY METRICS (Real computed fields only):                    |
| ▾ 3. IMMUTABLE PREVIEW & RUN           | Net Return %   Modeled P&L   Max Drawdown %   Closed Trades     |
|   [x] Acknowledge simulation limits    |  0.00%          $0.00         0.00%            0                |
|   [Save Immutable Preview]  [▶ Run]    | [▸ Retained execution events & Technical record (SHA-256)]      |
+----------------------------------------+-----------------------------------------------------------------+
```

---

### 6.8 Journal (`#journal`) — Master-Detail Decision Ledger, Position Outcomes, & Account History

- **Contract notes:** Consolidates tabs into `Decisions & Notes`, `Position Outcomes`, and `Account History`. Replaces `human_proposal` with `Human proposal` (L8), keeps focus stable inside `#decision-search` while typing, guards `[Revert Unsaved Edits]` with a count confirmation, and turns the 12-paragraph `Position Outcomes` groups into a 1-row summary table + right-hand inspector with a direct `[Go to Native Table Capture in Settings →]` link.

```text
+----------------------------------------------------------------------------------------------------------+
| DECISION JOURNAL   Tabs: [*Decisions & Notes (4)*] [Position Outcomes (0)] [Account History]             |
+----------------------------------------------------+-----------------------------------------------------+
| [Find symbol or text...] [Filter: All v] [Export]  | DECISION INSPECTOR: SGOV · Human Proposal           |
+----------------------------------------------------+-----------------------------------------------------+
| DATE     SYM   KIND            VERDICT    NOTE     | Tabs: [*Rationale & Note*] [Linked Orders & Outcome]|
| Oct 28 * SGOV  Human proposal  [Deferred] Saved ✓  | --------------------------------------------------- |
| Oct 28   AMZN  AI research     [Hold]     —        | Saved: Oct 28, 2026 · Status: [Deferred]            |
| Oct 28   INTC  AI research     [Underwt]  —        | Proposed Action: BUY 1 share SGOV (Market · DAY)    |
| Oct 28   TER   AI research     [Sell]     —        |                                                     |
|                                                    | FOLLOW-UP NOTE & DISPOSITION:                       |
| [Revert Unsaved Edits (0)] (Disabled at 0;         | Disposition: [Deferred         v]                   |
|  prompts "Discard N unsaved notes?" when dirty)    | Note: [Waiting for next week's FOMC meeting...    ] |
|                                                    | [Save Note]  [Open Linked Research]  [Open Ticket->]|
|                                                    | [▸ Technical record (Decision ID, run ID, SHA-256)] |
+----------------------------------------------------+-----------------------------------------------------+
```

---

### 6.9 Alerts (`#alerts`) — Triage Inbox, Deduped Occurrences, & 1-Click Rule Templates

- **Contract notes:** Keeps `Inbox (unread count)`, `Alert Rules`, and `Browser Delivery`. Collapses the 25 repeated `"Service restart"` JSON blocks into one expandable summary line. Softens `"no price-age limit configured"` into a calm setup prompt with `[Set Limit in Trading Rules →]`. Adds 3 Quick Rule Templates (`Price Above $`, `Price Below $`, `Quote Stale > s`) above the collapsible 16-condition advanced builder.

```text
+----------------------------------------------------------------------------------------------------------+
| ALERTS   Tabs: [*Inbox (1 unread)*] [Alert Rules (0)] [Browser Delivery]   Quote Age Limit: Not set [Set]|
+----------------------------------------------------+-----------------------------------------------------+
| ATTENTION INBOX (52% width)                        | EVENT EVIDENCE / QUICK RULE BUILDER (48% width)     |
| [Filter: All Events v]      [Acknowledge Selected] | Tabs: [*Event Summary*] [Captured Evidence] [Rule]  |
+----------------------------------------------------+-----------------------------------------------------+
| • [UNREAD] Price-age threshold not configured      | SELECTED EVENT: Price-age threshold not configured  |
|   Account · Setup prompt (Market currently closed) | Evaluated Oct 28, 20:35 ET · Regular market closed  |
|   [Inspect]  [Set Limit in Trading Rules ->]       | [Acknowledge]  [Set Quote-Age Limit in Settings ->] |
|                                                    | [▸ Technical record (Captured evaluation JSON)]     |
| • [GROUPED] Service restart recorded (25 events)   | --------------------------------------------------- |
|   Latest: Oct 28, 20:14 ET · [▸ Expand 25 logs]    | QUICK CREATE RULE (or click [Alert Rules] tab):     |
|                                                    | Templates: [Price Above $] [Price Below $] [Stale]  |
|                                                    | [▸ Advanced 16-condition / indicator / drawing rule]|
+----------------------------------------------------+-----------------------------------------------------+
```

---

### 6.10 Workflows (`#workflows`) — True `Fit All` Diagram & Node-Linked Prompt Studio

- **Contract notes:** Keeps the 2 real inspector tabs (`Prompts` and `Workflow YAML`). Adds **`Fit All`** (`0.25` zoom floor) as the default opening zoom so the entire 1,755px-tall 18-node flow fits in the left pane, plus an inline Retry banner if rendering fails (fixes L5). Clicking any diagram node selects its primary prompt and shows its related files (`Primary prompt`, `Shared context & tools`, `Output schema`) as a compact chip bar above the editor. Replaces native `confirm()` with an in-app `<dialog>`.

```text
+----------------------------------------------------------------------------------------------------------+
| WORKFLOWS   Saved: [Default v] [Load] · Active: Default · Status: Saved   [Preview] [Save] [Save As] [Use]|
+------------------------------------------------+---------------------------------------------------------+
| AGENT FLOW DIAGRAM (48% width, full height)    | WORKFLOW INSPECTOR (52% width, full height)             |
| [*Fit All (42%)*] [Fit Width] [-] [+]  [About▾]| Tabs: [*Prompts (94)*] [Workflow YAML]      [Details ▾] |
+------------------------------------------------+---------------------------------------------------------+
|          +------------------------+            | [Search prompts...]  File: [market_analyst — Guides...v]|
|          |     Start Research     |            | Node Files: [*market_analyst*] [shared_tools▾] [schema▾]|
|          +-----------+------------+            | +-----------------------------------------------------+ |
|                      |                         | | 1 | You are the Market Analyst on a structured      | |
|    +---------+-------+-------+---------+       | | 2 | equity research desk. Analyze OHLCV price       | |
|    v         v               v         v       | | 3 | action, moving averages, RSI/MACD, and          | |
| [Market*] [Social]        [News]    [Fund.]    | | 4 | volume regimes using only verified tool         | |
|    \         |               |        /        | | 5 | outputs...                                      | |
|     +--------+-------+-------+-------+         | |   |                                                 | |
|                      v                         | |   | (Clicking any node on the left diagram selects  | |
|          [Bull / Bear Debate (1r)]             | |   |  it and loads its primary prompt here;          | |
|                      v                         | |   |  Ctrl/Cmd+S saves; leaving while dirty opens    | |
|          [Research Manager (Deep)]             | |   |  an in-app Discard / Keep Editing <dialog>)     | |
|                      v                         | +-----------------------------------------------------+ |
|              [Trader Proposal]                 | Path: prompts/market_analyst.md · [Discard Changes]     |
|                      v                         |                                                         |
|             [Risk Debate (1r)]                 |                                                         |
|                      v                         |                                                         |
|          [Portfolio Manager (Deep)]            |                                                         |
+------------------------------------------------+---------------------------------------------------------+
```

---

### 6.11 Settings (`#settings`) — All 5 Complete Categories with Progressive Disclosure

- **Contract notes:** Preserves all 5 real categories (`Account & Engine`, `Research & Models`, `Universe & Keys`, `Trading Rules & Native Cache`, `Diagnostics & Backup`). Keeps `Start/Stop Nautilus` on `Account & Engine` and `Universe & Keys`. Splits `Research & Models` into 5 core fields + collapsible `Advanced (11 fields)`. Separates read-only Health Chips from the red-bordered `Danger Zone: Restore Workspace Backup` card.

```text
+----------------------------------------------------------------------------------------------------------+
| SETTINGS   Tabs: [Account & Engine] [*Research & Models*] [Universe & Keys] [Trading Rules] [Diagnostics]|
+----------------------------------------------------------------------------------------------------------+
| CORE RESEARCH MODELS (Applies to future research runs)                   [Discard] [Save Settings (Clean)]|
| +------------------------------------------------------------------------------------------------------+ |
| | Provider:         [Codex (existing sign-in)         v]   Endpoint: [Disabled for Codex            ]  | |
| | Deep Model:       [gpt-6-sol                        v]   Deep Reasoning: [High                    v] | |
| | Fast Model:       [gpt-6-luna                       v]   Fast Reasoning: [Medium                  v] | |
| | Server Limits:    Deep context 128,000 (max out 32,000) · Fast context 128,000   [Refresh Limits]    | |
| +------------------------------------------------------------------------------------------------------+ |
| [▸ Advanced Token Budgets, Concurrency, Retries & Local Laya Router (11 fields — collapsed by default)]  |
|                                                                                                          |
| OTHER SETTINGS TABS SUMMARY:                                                                             |
| • [Account & Engine]: Paper/Live ID (once), Start/Stop Nautilus, Execution Profile, Alpaca Vault Keys.   |
| • [Universe & Keys]:  Universe Name, 1,000-stock Textarea, FANGMAN Preset, CSV Import/Export, Data Keys. |
| • [Trading Rules]:    10 Investor Policy Rules + Capture Native Cache Table (for Journal Outcomes).      |
| • [Diagnostics]:      Top: [● Engine: Connected] [● Sync: Reconciled] [● Store: OK] + Dynamic Origin URL.|
|                       Bottom: [Export Backup] + Red-Bordered DANGER ZONE: [Restore Workspace Backup].    |
+----------------------------------------------------------------------------------------------------------+
```

---

## 7. Implementation Workstreams (Ready for Execution)

When we move from this blueprint to code implementation, the work splits cleanly into 4 parallel workstreams:

1. **Workstream 1 — Shell, Shared Tablist, Chrome Diet & Icons (`index.html`, `app.css`, `app.js` shell):**
   - `36px` single-line top bar, remove `.workspace-footer`, remove multi-paragraph `pageHeader` prose, add 10 distinct sidebar SVG icons, unify `Orders: Active / Paused`, and add shared WAI-ARIA `renderTablist()` with keyboard arrow navigation.
2. **Workstream 2 — Research & Workflows Redesign (`app.js` research, `report-format.js`, `workflows.js`, `ui-research-journal.css`, `ui-workflows.css`):**
   - Inline stock picker + batch selector on Research, auto-focus first running stock on launch, 7-state honest progress bar, no fake `Sell` badge or stuck `Loading...` line, structured Summary with real Analyst Excerpt cards + Laya counts + Bull/Bear split, `[Manage]` toggle for deletion, Workflows `Fit All` (`0.25` zoom floor) + node-click prompt chip bar + in-app unsaved `<dialog>`.
3. **Workstream 3 — Dashboard, Markets & Portfolio (`app.js`, `market-chart.js`, `ui-markets.css`, `ui-instrument.css`):**
   - Unclipped Dashboard bottom panes, `0 checked` initial watchlist state, hollow down-candles + overlay legends + `<details>` bar tables, Markets 1-line history backfill bar + Current IEX vs. Saved Research chart context, Portfolio formatted numbers + capped 140px Performance empty state.
4. **Workstream 4 — Orders, Strategy Lab, Journal, Alerts & Settings (`app.js`, `command-controls.js`, `nautilus.js`, `ui-orders.css`):**
   - Direct 2-column DOM rendering (deleting `layoutOrders`/`layoutMarkets` post-render scraping), 1-line order readiness + inline confirm/receipt + `resolve_never_dispatched` recovery, Strategy Lab 3-step accordion rail, Journal focus-safe search + 1-row outcome table + guarded revert, Alerts grouped restarts + 3 quick rule templates, Settings Basic vs. Advanced split + isolated Restore Danger Zone.

---

## 8. High-Value Backend Capabilities Surfaced in v3+ (`docs/ui-missed-opportunities.md`)

Our backend-to-UI audit ([`docs/ui-missed-opportunities.md`](ui-missed-opportunities.md) and [`docs/ui-missed-opportunities-nautilus.md`](ui-missed-opportunities-nautilus.md)) identified 20+ existing backend and Nautilus 1.231.0 capabilities that were previously hidden or dumped as raw JSON. They slot cleanly into the wireframes above:

1. **Global Shell (`6.1`):**
   - **Market Open/Close Countdown (`state.clock.next_open` / `next_close`):** Pass `next_open` and `next_close` through `service.py:2162` so `lists.js` `marketState()` renders `"Market Closed · Opens in 11h 32m"`.
   - **Live Broker Trade Stream Dot (`state.nautilus.trade_stream`):** Show `Stream: Listening` dot next to `Nautilus OK`.
   - **Account Restriction Chip (`state.account.trading_blocked` / `account_blocked`):** Show a warning chip if Alpaca blocks or suspends trading.
2. **Markets & Research (`6.3`, `6.4`):**
   - **Historical Point-in-Time Research Date & `exclude_fred` (`POST /api/runs`):** Expose optional `analysis_date` and `exclude_fred` inside the Research Confirm Popover.
   - **Asset Capability Badges & Displayed Quote Sizes (`state.nautilus.market_data`):** Show `Bid $252.40 (300) x Ask $252.60 (100) · 8 bps` plus `Fractional ✓` / `Overnight Halted` badges.
   - **SEC EDGAR Point-in-Time Financials, Corporate Actions & Alpaca News (`/api/stock-evidence`):** Surface an `[Evidence & Filings]` drawer with XBRL Balance Sheet / Income / Cash Flow, Ex-Dividend / Split dates, and SIC industry.
   - **Local Laya Post Screening (`/api/runs/local-laya`) & Standalone HTML Tear Sheet (`report_html.py`):** Surface `[Screen Saved Posts Locally]` on Sentiment and `[Export HTML Tear Sheet]` in the Research header.
3. **Portfolio & Orders (`6.5`, `6.6`):**
   - **Today's Intraday P/L & `qty_available` (`state.positions`):** Add `Today P/L` (`unrealized_intraday_pl`) and `Avail Qty` (`qty_available`) to Positions and the Order Ticket.
   - **10-Rule Policy Value vs. Limit Table (`policy_evaluation.py`):** Show all 10 policy checks with observed value vs. limit (failing rules first) instead of a `<pre>` JSON block, plus bracket `stop_loss_estimate_before_fees`.
   - **Structured Fills Table (`state.fills`) & Basket Weight/Turnover Table (`baskets.py`):** Replace `<pre>` JSON dumps in `Orders → Fills` and `Orders → Baskets` with tabular views including `Fee Provenance (actual / modeled)` and `Turnover %`.
4. **Strategy Lab & Journal (`6.7`, `6.8`):**
   - **Nautilus `BacktestResult` Portfolio Analyzer Metrics (`stats_pnls`, `stats_returns`):** Surface `Win Rate`, `Profit Factor`, `Expectancy`, and `Sharpe` alongside Walk-Forward Fold tables and Closed-Trade lists.
   - **Benchmark Alpha Settlement & Analyst Self-Reflection (`settlement.py`, `reflection.py`):** Surface `5d Return`, `5d Alpha vs. SPY`, and the 2–4 sentence `Reflection Lesson` in `Journal → Decisions & Outcomes`.

