# UI Redesign Blueprint: Personas, Workflows, and Wireframes

This document defines the user personas, user stories, workflow rules, screen-space budgets, and wireframes for redesigning the TradingAgents desktop workspace. No UI code should be rewritten until this blueprint is reviewed and approved.

- **Design system:** Keep the dark charcoal desk palette, green action accents, and tabular numbers from `DESIGN.md`.
- **Core safety rule:** Keep research, order staging, order approval, and broker submission strictly separate (`PRODUCT.md`).
- **Why we are redesigning:** The current UI wastes up to three-quarters of the screen on stacked headers, explanatory paragraphs, filter buttons, and always-on management bars, leaving a cramped box for actual data. Core tasks—like picking a stock and running research—are split across multiple pages.

---

## 1. What We Learned from Industry Leaders

We benchmarked against **Fidelity Active Trader Pro**, **Interactive Brokers (IBKR) Desktop**, **TradingView Desktop**, **Koyfin**, and **FinChat / Fiscal.ai**:

1. **80%+ of the screen is data, not chrome (TradingView / IBKR Desktop):**
   - Industry desks use a single 36–40px toolbar per pane. Search, filter, sort, and the primary action sit on one line.
   - Bulk-delete bars, data-backfill forms, and advanced filters stay hidden inside a popover or toggle until clicked.
2. **One-click symbol linking across panels (Active Trader Pro / TradingView):**
   - Clicking a stock in any list immediately updates the chart, quote header, research summary, and order ticket.
   - Starting a batch job automatically focuses the first active stock so the screen never looks frozen.
3. **Structured research cards instead of walls of text (Koyfin / FinChat):**
   - Equity terminals never open with a 1,000-word essay. They open with a **Verdict Strip** (Rating, Date, Coverage status, Action button), a **4-Analyst Scorecard** (Market, Fundamentals, News, Social), and a **Bull vs. Bear Split Card**. Full prose sits below in an expandable section.
4. **Self-contained workspaces:**
   - You never have to visit Page A to select a ticker just to click "Run" on Page B. Every workspace has an inline symbol picker or universe selector right where the action happens.

---

## 2. User Personas

### Persona 1: Alex — Daily Active Desk Operator (Primary)
- **Goal:** Scan a 10–30 stock universe before the open or after the close, run AI research on movers, read the verdict and bull/bear case in under a minute, and stage paper orders.
- **Frustrations with current UI:**
  - Has to go to Markets to pick stocks, then switch to Research to start the run, and then click a stock manually before the right panel updates.
  - Has to scroll past 270px+ of headers, filter strips, and delete buttons just to see 3 rows of stocks.
  - Keyboard navigation breaks on fake tabs (`aria-pressed` buttons instead of arrow-key tabs).

### Persona 2: Jordan — Methodical Swing & Fundamental Researcher
- **Goal:** Audit the evidence chain behind a recommendation—checking analyst reports, bull vs. bear arguments, dated news sources, coverage gaps, and past decision outcomes.
- **Frustrations with current UI:**
  - The Research progress bar is solid green and says "24 / 24 finished" when 21 stocks were cancelled and only 3 finished.
  - Sees a red "Sell" badge right next to "No final recommendation is saved."
  - Hits walls of Portfolio Manager text, raw internal words (`human_proposal`, `needs_review`), raw UUIDs, and 25 repeated JSON blocks in Alerts.

### Persona 3: Morgan — Workflow & Strategy Architect
- **Goal:** Customize the multi-agent workflow graph/prompts in Workflows and test strategy hypotheses in Strategy Lab.
- **Frustrations with current UI:**
  - The Workflows diagram is clipped and cannot fit the whole 18-node flow on screen at once.
  - Has to hunt through a 94-option dropdown with cut-off file names to edit a prompt.
  - Faces a 30-field wall of inputs and a 90-word legalistic checkbox in Strategy Lab Setup.

---

## 3. User Stories & Acceptance Criteria

| ID | Persona | User Story | Acceptance Criteria |
|---|---|---|---|
| **US-01** | Alex | As an operator on the **Research** tab, I want to pick one or more stocks (from my universe or by typing a symbol) and click **Run research** right on the Research page. | Research header includes an inline stock picker + quick "Select universe" / "Select unfinished" options and the **Run research (N)** button. Zero trips to Markets required. |
| **US-02** | Alex | When I start a research run, I want the screen to immediately focus the first running stock and show honest live progress. | Launching research switches focus to the first queued/running stock, scrolls it into view in the left list, and updates a segmented status bar (`Running 1 of 4 · 0 done · 0 failed`). |
| **US-03** | Jordan | When a research run is cancelled or has failures, I want the progress bar and badges to tell the truth at a glance. | Progress bar segments Completed (green), Running (blue), Cancelled (neutral slate), and Failed (rose). Text reads `3 of 24 completed · 21 cancelled`. |
| **US-04** | Jordan | When I open a stock on **Research**, I want to see the verdict, analyst breakdown, coverage gaps, and bull/bear summary before any long essay. | Summary opens with: (1) Verdict Strip (rating only if saved, date, coverage status), (2) 4 Analyst Cards, (3) Bull vs. Bear 2-column summary, (4) Review/Note bar, and (5) expandable full Portfolio Manager decision. |
| **US-05** | Alex | On every page, I want at least **80% of the window** dedicated to data (charts, tables, reports, diagrams) rather than labels, boxes, and filter buttons. | Total vertical chrome above the main workspace panes is capped at ~100–110px (top bar + single 40px toolbar). Bulk-delete bars and backfill forms are hidden until toggled. |
| **US-06** | Alex | When I finish reading research on a stock, I want a one-click way to draft an order for that stock without re-typing the symbol. | Research Verdict Strip includes a **"Draft order for [SYMBOL]"** button that opens Orders pre-filled with the symbol (still requiring explicit review, approval, and submission). |
| **US-07** | Alex | On **Dashboard**, I want to see my account summary, watchlist, chart, open positions/orders, and latest research in a clean 2x2 grid with nothing clipped. | At desktop resolution (1920x1080+), all 4 quadrants fit without cut-off buttons or double scrollbars. Empty states are compact (max 2 lines + 1 button). |
| **US-08** | Alex | On **Markets**, I want the watchlist and price chart side-by-side at full height, with history download tucked away unless a stock needs bars. | Markets uses a 2-column split (32% Watchlist, 68% Chart + Bar table). The 10-field history form collapses into a 1-line "Missing price history — Fetch daily bars" banner. |
| **US-09** | Alex | On **Orders**, I want to see immediately whether order execution is active or paused, why a button is disabled, and get a clear confirmation before and after submitting, cancelling, or replacing an order. | Top status pill shows `Orders active` or `Orders paused`. Readiness blockers show on 1 visible line. Submit/Cancel/Replace show an inline confirmation step and a timestamped receipt banner. |
| **US-10** | Morgan | On **Workflows**, I want to see the entire agent diagram at once and click any node to edit its prompt. | Diagram pane supports a true **Fit all** zoom (down to 35%), takes full workspace height on the left, and clicking any agent node opens its prompt in the right-hand editor. |
| **US-11** | Morgan | On **Strategy Lab**, I want a simple 3-step setup on the left and simulation results on the right, without a 30-field wall. | Left rail (340px) groups Strategy, Universe/Dates, and Risk into compact sections; right pane shows the Equity Curve, Key Metrics table, and Run Comparison. |
| **US-12** | Jordan | Across all pages, I want plain English labels instead of internal code words, hashes, and raw JSON dumps. | Words like `human_proposal`, `needs_review`, `STOP_LIMIT`, and raw UUIDs are replaced with plain labels (`Human proposal`, `Needs review`, `Stop limit`). Raw JSON moves inside a collapsed `Technical record` drawer. |

---

## 4. Screen Real-Estate & Layout Rules (The Anti-Clutter Contract)

1. **The 80/20 Viewport Rule:**
   - **Global Top Bar:** max `48px` tall (Paper/Live badge, 5 compact account figures, Global Symbol Search, Order Execution status pill, Alerts bell).
   - **Workspace Toolbar:** max `40px` tall (Page title + primary tabs + right-aligned primary action).
   - **Data Canvas:** the remaining **88%+ of vertical height** (`~990px` on a 1080p screen, `~1200px` on a 1300p screen) belongs strictly to data panes.
2. **No Stacked Control Bars:**
   - Never stack a search row, a 10-button filter row, a sort row, and a 5-button delete row.
   - Use **one row**: `[Search input] [View: All (24) v] [Sort: Symbol v] ... [Manage] [Primary Action]`.
   - Clicking `[Manage]` reveals row checkboxes and bulk actions (`Select all`, `Delete selected`) in place.
3. **No Prose Walls Above Data:**
   - Remove multi-paragraph explanations above tables and forms. If a safety or scope note is needed, keep it to **one sentence (max 1 line)** with a `Details` link.
4. **One Scrollbar Per Column:**
   - The page body itself does not scroll on split-pane workspaces (`Dashboard`, `Markets`, `Research`, `Orders`, `Workflows`). Each pane scrolls independently with a single scrollbar.
5. **Real Accessible Tabs Everywhere:**
   - Every sub-tab bar uses real `role="tablist"` / `role="tab"` semantics, arrow-key navigation, 40–44px hit targets, and a high-contrast active underline.

---

## 5. What Each Tab Does (Information Architecture)

We keep the 10 left-rail workspaces so no backend capability is lost, but give each a distinct icon, a single clear job, and zero duplicate clutter:

| Left Nav Tab | Distinct Icon | Primary Job | Key Change from Current UI |
|---|---|---|---|
| **1. Dashboard** | Grid | 10-second morning check: Account KPIs, Watchlist, Chart, Positions/Orders, and Latest Research Verdict. | Fixed 2x2 grid below compact KPI bar; no clipped buttons; no 24-row pre-selection. |
| **2. Markets** | Candlestick | Inspect price action, technical overlays, and universe membership; trigger research on selected symbols. | 2-column full-height split (Watchlist left, Chart right). 10-field history form collapsed into a 1-line bar. |
| **3. Research** | Microscope / Spark | Pick stocks, launch/monitor AI research runs, and read structured analyst verdicts, debates, and sources. | **Pick stocks & run directly here.** Replace Setup tab with an inline Launch Bar. Replace PM prose wall with Verdict Card + 4 Analyst Cards + Bull/Bear split. |
| **4. Portfolio** | Briefcase | Monitor broker-reconciled holdings, build/review the AI Proposed Basket, and track Historical Performance. | Formatted signed currency/P&L numbers, 3-KPI strip, capped empty-chart height, plain English reconciliation status. |
| **5. Orders** | Ticket / Check | Stage manual or research-backed orders, check readiness, approve, submit to Alpaca, and manage open orders. | 2-column layout (Order Ticket & Impact left, Open Orders & Fills right). Always-visible readiness line + confirm/receipt flow. |
| **6. Strategy Lab** | Sliders / Lab | Configure and run Nautilus backtests and Optuna experiments; compare simulated equity curves. | 2-column layout (Compact 3-part setup left, Results & Equity Curve right). Short 1-line simulation disclaimer. |
| **7. Journal** | Book | Review past trading decisions, human dispositions, position outcomes, and account history snapshots. | Master-detail table + inspector instead of 12-paragraph walls. Safe confirm before reloading/discarding notes. |
| **8. Alerts** | Bell | Triage triggered price/freshness alerts and create simple alert rules from templates. | Unread badge on Inbox, grouped restart rows ("25 service restarts"), and 3 one-click rule templates ("Price above/below", "Data stale"). |
| **9. Workflows** | Nodes / Graph | Inspect the multi-agent graph, click nodes to edit prompts/YAML, preview, save, and activate for new runs. | Full-height split: 50% Diagram (with true "Fit all" zoom) + 50% Editor. Click any node to load its prompt. |
| **10. Settings** | Gear | Configure broker keys, AI model tiers, safety/order pause controls, and backups/diagnostics. | Group 20+ research fields into Basic (Provider & Models) vs. Advanced. Separate read-only Diagnostics from Danger Zone restore. |

---

## 6. Page-by-Page Wireframes

### 6.1 Global Shell (Applies to All Pages)

```text
+--------------------------------------------------------------------------------------------------+
| [PAPER DESK]  Equity $100,000  Cash $100,000  Buying Power $100,000  Day P/L $0.00   [Find: ___] |
|               Broker: Alpaca Paper (Verified) · Orders: Active · Alerts: 0 unread                |
+------------------+-------------------------------------------------------------------------------+
| TradingAgents    |  WORKSPACE HEADER + SUB-TABS + PRIMARY ACTION (single 40px bar)               |
|                  +-------------------------------------------------------------------------------+
| [ ] Dashboard    |                                                                               |
| [ ] Markets      |                                                                               |
| [*] Research     |                                                                               |
| [ ] Portfolio    |                     88% OF SCREEN HEIGHT = DATA PANES                         |
| [ ] Orders       |                     (Zero stacked prose banners or filter walls)              |
| [ ] Strategy Lab |                                                                               |
| [ ] Journal      |                                                                               |
| [ ] Alerts   (0) |                                                                               |
| [ ] Workflows    |                                                                               |
| [ ] Settings     |                                                                               |
|                  |                                                                               |
| ---------------- |                                                                               |
| Engine: Connected|                                                                               |
| Market: Closed   |                                                                               |
+------------------+-------------------------------------------------------------------------------+
```

---

### 6.2 Dashboard (`#overview`) — 2x2 Linked Command Grid

- **Purpose:** Instant overview without scrolling. Clicking any row in the Watchlist updates the Chart (top-right) and Research Verdict (bottom-right).
- **Space budget:** Top KPI strip `48px`, 2x2 grid takes `90%` of height (`55%` top row, `35%` bottom row).

```text
+------------------------------------------+-------------------------------------------------------+
| WATCHLIST (24)   [Search] [Filter v] [+] | AMZN $252.51 (+1.14%)   [1D] [1W] [1M] [Indicators v] |
+------------------------------------------+-------------------------------------------------------+
| SYM    LAST     CHG%    RESEARCH  ACTION |  260 |          .|.                                   |
| AMZN * $252.51  +1.14%  Hold      [Run]  |  255 |      .|. | |  .|.                              |
| INTC   $22.40   -0.85%  Underwt   [Run]  |  250 |  .|. | |      | |                              |
| TER    $108.12  -1.40%  Sell      [Run]  |  245 |________________________________________________|
| AAPL   $231.10  +0.42%  Cancelled [Run]  |  Vol |  ||  |||  ||  ||||                             |
| NVDA   $141.80  +2.10%  Cancelled [Run]  |  [v Show recent price bars table (keyboard/screen)]   |
+------------------------------------------+-------------------------------------------------------+
| POSITIONS (0) | OPEN ORDERS (0)          | LATEST RESEARCH: AMZN               [Open Research ->]|
+------------------------------------------+-------------------------------------------------------+
| No open positions in Alpaca Paper.       | [HOLD]  Completed Oct 28 · Default workflow           |
| Cash available: $100,000.00              | • Market: Bullish trend above 20d MA                  |
|                                          | • Fundamentals: AWS margin expansion intact           |
| [Browse Markets]   [Draft Order]         | • Risk: Valuation stretched; 1 news rate-limit gap    |
| (Compact — never clips at bottom!)       | [Read full report]              [Draft AMZN Order ->] |
+------------------------------------------+-------------------------------------------------------+
```

---

### 6.3 Markets (`#markets`) — Full-Height Watchlist + Chart Inspector

- **Purpose:** Screen the universe, inspect charts and historical bars, manage symbols, and kick off research right from the selected stock or checked rows.
- **Key fix:** The 10-control history backfill form is collapsed into a single 36px bar when history is missing (`No local price bars for AAPL · [Fetch 1Y daily bars] [Custom range v]`). The 10 filter buttons become one `View` dropdown.

```text
+-----------------------------------+--------------------------------------------------------------+
| UNIVERSE: PNIS (24)  [+ Add Sym]  | AMZN · Amazon.com Inc.   $252.51 (+1.14%) · Quote 16:00 ET   |
| [Search...] [View: All v] [Manage]| [Chart] [Price Bars Table] [Fundamentals]   [Run Research]   |
+-----------------------------------+--------------------------------------------------------------+
| SYM     PRICE    CHG%   HISTORY   | Timeframe: [1D] [1W] [1M] [1Y]  Overlays: [SMA20] [Drawings] |
| AMZN *  $252.51  +1.14% 1,255 bars| +----------------------------------------------------------+ |
| AAPL    $231.10  +0.42% Missing   | |                                                          | |
| GOOGL   $182.30  -0.12% Missing   | |                 FULL-HEIGHT OHLCV CHART                  | |
| META    $590.40  +1.85% Missing   | |                 (75% of right-pane height)               | |
| MSFT    $428.15  +0.33% Missing   | |                                                          | |
| NVDA    $141.80  +2.10% Missing   | +----------------------------------------------------------+ |
| TER     $108.12  -1.40% Missing   | | DATA BACKFILL & FRESHNESS (1-line bar, expandable)       | |
| ... (single clean scrollbar)      | | 1,255 daily bars cached through Oct 28 · [Refresh bars]  | |
|                                   | +----------------------------------------------------------+ |
| (When [Manage] is clicked:        | | KEY STATS: Open $249.80 · High $254.90 · Low $249.10     | |
|  shows checkboxes + [Run (N)]     | |            Volume 38.2M · Saved Research: HOLD (Oct 28)  | |
|  + [Remove from universe])        | +----------------------------------------------------------+ |
+-----------------------------------+--------------------------------------------------------------+
```

---

### 6.4 Research (`#research`) — Self-Contained Picker, Honest Progress, Structured Verdict

- **Solves User Issues U1 & U2 and Critique L3/P1s:**
  1. **Pick & Run right here (U1):** Top launch bar lets you pick any symbol(s) (`[+ Pick stocks: AMZN, NVDA... v]`, `[All Universe (24)]`, `[Retry Unfinished (21)]`) and click **`[Run Research (N)]`** without ever visiting Markets.
  2. **Auto-focus & live progress on launch (U2):** Starting a run immediately selects the first running ticker, scrolls the left rail to it, and shows a live stage indicator (`Stage 2/5: Bull vs. Bear Debate...`).
  3. **Honest Run Bar:** Replaces the fake full-green `24/24 finished` bar with a 4-color segmented bar (`3 Completed · 21 Cancelled · 0 Failed`).
  4. **No Fake "Sell" Badge (L3):** If a stock has no saved final recommendation (e.g. cancelled before completion), the badge says **`[CANCELLED — NO VERDICT]`** in neutral slate, never a red `Sell` badge.
  5. **Structured Summary instead of a Prose Wall:** Leads with the Verdict Strip, 4 Analyst Cards, and Bull vs. Bear columns.

```text
+--------------------------------------------------------------------------------------------------+
| RESEARCH LAUNCH & RUN BAR (44px):                                                                |
| Stocks: [AMZN, INTC + Add/Pick v] [Select Unfinished (21)] [Run Research (2)]  Workflow: Default |
| Last Run: [===3 Completed===|---------21 Cancelled---------] 3 of 24 completed · Run cancelled   |
+----------------------------+---------------------------------------------------------------------+
| RESEARCH LIST (24)         | AMZN · Amazon.com Inc.                     [Draft Order for AMZN ->]|
| [Search] [Show: All v] [Ed]| Tabs: [*Summary*] [Bull vs Bear] [Analyst Reports (4)] [Sources (9)]|
+----------------------------+---------------------------------------------------------------------+
| SYM    STATUS     VERDICT  | +-----------------------------------------------------------------+ |
| AMZN * Completed  [HOLD]   | | VERDICT: [HOLD] · Completed Oct 28, 19:42 · Workflow: Default   | |
| INTC   Completed  [UNDERWT]| | Coverage: 4/4 analysts finished · 1 warning (News HTTP 429)     | |
| TER    Completed  [SELL]   | +-----------------------------------------------------------------+ |
| AAPL   Cancelled  —        |                                                                     |
| GOOGL  Cancelled  —        | ANALYST SCORECARD (Click any card to open full report):             |
| META   Cancelled  —        | +---------------+ +---------------+ +---------------+ +-----------+ |
| MSFT   Cancelled  —        | | MARKET        | | FUNDAMENTALS  | | NEWS          | | SOCIAL    | |
| NVDA   Cancelled  —        | | Neutral-Bull  | | Strong cash   | | Mixed macro   | | Screened  | |
| NFLX   Cancelled  —        | | Above 50d SMA | | AWS margins + | | 1 rate limit  | | Laya 0.4  | |
| ...                        | +---------------+ +---------------+ +---------------+ +-----------+ |
| (Single scrollbar;         |                                                                     |
|  auto-scrolls to active    | DEBATE & RISK SYNTHESIS:                                            |
|  stock when run starts.    | +-------------------------------+ +-------------------------------+ |
|  Clicking [Ed] toggles     | | BULL CASE (Researcher)        | | BEAR CASE (Researcher)        | |
|  checkboxes & Delete bar)  | | • AWS backlog accelerating    | | • Retail capex compression    | |
|                            | | • Operating leverage in N.A.  | | • Multiple near 5-yr peak     | |
|                            | +-------------------------------+ +-------------------------------+ |
|                            |                                                                     |
|                            | YOUR DISPOSITION: [Needs review v]  Note: [________________] [Save] |
|                            | [> Read full Portfolio Manager decision (18,400 chars)]             |
+----------------------------+---------------------------------------------------------------------+
```

---

### 6.5 Portfolio (`#portfolio`) — Reconciled Holdings, Proposed Basket, & Performance

- **Fixes:** Formats all currency/percentage columns with signs and colors, caps the empty Performance chart icon to a compact box, and puts plain-English reconciliation status in a single top strip.

```text
+--------------------------------------------------------------------------------------------------+
| PORTFOLIO    Tabs: [*Positions (0)*]  [Proposed Basket (1)]  [Performance]                       |
| Reconciliation: Clean · Alpaca Paper matches local ledger as of 20:35 ET      [Refresh Account]  |
+--------------------------------------------------------------------------------------------------+
| +----------------------+ +----------------------+ +----------------------+ +-------------------+ |
| | NET EQUITY           | | CASH & SWEEP         | | OPEN POSITIONS VALUE | | UNREALIZED P/L    | |
| | $100,000.00          | | $100,000.00 (100%)   | | $0.00 (0 positions)  | | $0.00 (0.00%)     | |
| +----------------------+ +----------------------+ +----------------------+ +-------------------+ |
|                                                                                                  |
| OPEN POSITIONS                                                                                   |
| +----------------------------------------------------------------------------------------------+ |
| | No open positions in your Alpaca Paper account.                                              | |
| | Start by researching stocks or reviewing your saved human basket (1 deferred proposal: SGOV).| |
| | [Go to Research]    [Review Proposed Basket (1)]    [Stage Manual Order]                     | |
| +----------------------------------------------------------------------------------------------+ |
| [> Technical reconciliation record (raw broker snapshot & epoch details)]                        |
+--------------------------------------------------------------------------------------------------+
```

*(On **Proposed Basket**, the top half shows the Human Basket vs. AI Portfolio Synthesis side-by-side with clear "Stage to Orders" actions; on **Performance**, if no position captures exist yet, a compact 140px card explains how captures work and offers `[Capture current account snapshot]` without a giant 800px empty SVG.)*

---

### 6.6 Orders (`#orders`) — Two-Column Execution & Order Book

- **Fixes:** Always shows the top readiness line (never hidden inside a collapsed drawer), uses one consistent term (`Pause new orders` / `Orders active`), explains why any button is disabled, and adds an inline confirmation + receipt banner for Submit, Cancel, and Replace.

```text
+--------------------------------------------------------------------------------------------------+
| ORDERS & EXECUTION   Status: [Orders Active] [Pause New Orders]   Broker: Alpaca Paper Connected |
| Readiness: Ready for paper orders · Cash available: $100,000.00 · Cash account (no shorting)     |
+----------------------------------------+---------------------------------------------------------+
| STAGE & APPROVE ORDER (40% width)      | OPEN ORDERS & RECENT FILLS (60% width)                  |
| Source: [Manual Ticket v] [Load Basket]| Tabs: [*Open Orders (0)*] [Staged Proposals (1)] [Fills]|
+----------------------------------------+---------------------------------------------------------+
| Symbol:   [AMZN      ]  Last: $252.51  | STAGED PROPOSALS AWAITING ACTION:                       |
| Side:     [(*) Buy  ( ) Sell        ]  | SYM   SIDE  QTY  TYPE    STATUS     ACTION              |
| Quantity: [10        ]  whole shares   | SGOV  BUY   1    Market  Deferred   [Load into Ticket]  |
| Type:     [Limit     v]                |                                                         |
| Limit $:  [252.00    ]  TIF: [DAY v]   | OPEN BROKER ORDERS (0):                                 |
|                                        | No open orders working at Alpaca Paper.                 |
| ESTIMATED IMPACT:                      |                                                         |
| Est. Cost:        $2,520.00 (2.5% eq)  | ------------------------------------------------------- |
| Cash After Order: $97,480.00           | LAST ACTION RECEIPT:                                    |
| Saved Research:   HOLD (Oct 28)        | No orders submitted in this session.                    |
|                                        | (When submitted, shows: "Sent BUY 10 AMZN LMT $252.00   |
| Step 1: [Approve Exact Terms]          |  to Alpaca Paper at 14:02:11 ET · Broker ID #9f8a...")  |
| Step 2: [Submit to Alpaca Paper]       |                                                         |
| (Disabled until Step 1 is checked;     | [> Technical order audit & SHA-256 verification]        |
|  shows inline confirm before sending)  |                                                         |
+----------------------------------------+---------------------------------------------------------+
```

---

### 6.7 Strategy Lab (`#strategy`) — Left Parameter Rail + Right Results Canvas

- **Fixes:** Replaces the 30-field single-column form and 90-word legalistic consent wall with a compact 340px 3-step parameter rail on the left and a full-height Results & Runs workspace on the right.

```text
+--------------------------------------------------------------------------------------------------+
| STRATEGY LAB   Scope: Simulations run on cached bars only and never place broker orders. [Details]|
+------------------------------------+-------------------------------------------------------------+
| SIMULATION SETUP (340px rail)      | RESULTS & RUNS   Tabs: [*Latest Result*] [Compare Runs (0)] |
+------------------------------------+-------------------------------------------------------------+
| 1. STRATEGY & UNIVERSE             | EQUITY CURVE & BENCHMARK                                    |
| Template: [SMA Crossover    v]     | +---------------------------------------------------------+ |
| Symbols:  [AMZN             v]     | |                                                         | |
| Dates:    [2025-10-01] to [Today]  | |               SIMULATED EQUITY CHART                    | |
|                                    | |          (With toggleable [Table View] for a11y)        | |
| 2. CAPITAL & RISK                  | +---------------------------------------------------------+ |
| Starting Cash: [$100,000    ]      |                                                             |
| Max Position:  [20%         ]      | SUMMARY METRICS:                                            |
| Fast / Slow:   [10 ] / [50  ]      | Return   Sharpe   Max Drawdown   Win Rate   Trade Count     |
| [> Advanced fees & slippage (4)]   |  —        —        —              —          —              |
|                                    |                                                             |
| 3. RUN                             | SIMULATED TRADES & LOG:                                     |
| [x] I understand this is a model   | Run a simulation on the left or [Load saved experiment]     |
| [Run Simulation] [Save Strategy]   | to inspect trade-by-trade entries and exits.                |
+------------------------------------+-------------------------------------------------------------+
```

---

### 6.8 Journal (`#journal`) — Master-Detail Decision & Outcome Ledger

- **Fixes:** Eliminates the 12-paragraph walls per position group and the unguarded "Reload saved journal (discard unsaved notes)" button. Uses a scannable table on the left and a clean inspector on the right.

```text
+--------------------------------------------------------------------------------------------------+
| DECISION JOURNAL   Tabs: [*Decisions & Dispositions*] [Position Outcomes] [Account History]      |
| [Search symbol or note...]  [Filter: All Dispositions v]             [Revert Unsaved Edits (0)]  |
+--------------------------------------------------+-----------------------------------------------+
| RECORDED DECISIONS (Table, 55% width)            | DECISION INSPECTOR (45% width)                |
+--------------------------------------------------+-----------------------------------------------+
| DATE     SYM   SOURCE          VERDICT  STATUS   | SGOV · Human Proposal (Saved Oct 28)          |
| Oct 28 * SGOV  Human proposal  BUY 1    Deferred |                                               |
| Oct 28   AMZN  AI Research     Hold     Reviewed | Action:       BUY 1 share (Paper)             |
| Oct 28   INTC  AI Research     Underwt  Unreview | Disposition:  [Deferred       v]              |
| Oct 28   TER   AI Research     Sell     Unreview | Linked Order: Not submitted                   |
|                                                  |                                               |
|                                                  | OPERATOR NOTES:                               |
|                                                  | [Holding cash in T-bill ETF pending tech     ]|
|                                                  | [earnings next week.                         ]|
|                                                  |                                               |
|                                                  | [Save Note & Disposition]  [Stage on Orders->]|
|                                                  | [> Technical record (IDs & timestamps)]       |
+--------------------------------------------------+-----------------------------------------------+
```

---

### 6.9 Alerts (`#alerts`) — Compact Triage Inbox + 1-Click Rule Templates

- **Fixes:** Restores the unread count badge, groups the 25 repetitive "Service restart" JSON blocks into a single collapsible summary line, softens "no price-age limit configured" into a setup prompt, and adds 3 simple rule templates before any advanced dropdowns.

```text
+--------------------------------------------------------------------------------------------------+
| ALERTS & MONITORING   Tabs: [*Inbox (1 unread)*] [Alert Rules (0)]   Delivery: Browser notifications|
| Freshness Setup: Price-age limit not set (market currently closed) · [Set Default 15m Limit]     |
+--------------------------------------------------+-----------------------------------------------+
| ATTENTION INBOX (55% width)                      | QUICK CREATE RULE (45% width)                 |
+--------------------------------------------------+-----------------------------------------------+
| [Mark All Read]  [Filter: All Events v]          | Pick a template:                              |
|                                                  | [Price Above $] [Price Below $] [Data Stale]  |
| • [INFO] Service restarted (25 occurrences)      |                                               |
|   Latest: Oct 28, 20:14 ET · [> Expand 25 logs]  | Symbol:    [AMZN          v]                  |
|                                                  | Condition: [Price Above   v]                  |
| • [SETUP] Price-age threshold unset              | Threshold: [$260.00        ]                  |
|   Set a threshold on the right to monitor feed   |                                               |
|   delays during market hours.                    | [Create Alert Rule]                           |
|                                                  | [> Advanced conditions (indicators & scopes)] |
+--------------------------------------------------+-----------------------------------------------+
```

---

### 6.10 Workflows (`#workflows`) — Full-Height Diagram + Node-Linked Prompt Studio

- **Fixes:** Fixes the broken/clipped diagram render, lowers the zoom floor so **Fit all** shows the entire 18-node graph in one view, lets the user click any node in the diagram to load its prompt in the editor, and replaces native `confirm()` with an in-app dialog.

```text
+--------------------------------------------------------------------------------------------------+
| WORKFLOWS STUDIO   Workflow: [Default v] [Active for new research]   Status: Saved (No changes)  |
| Actions: [Preview & Validate]  [Save Changes]  [Use for New Research]  [Save Copy As...]         |
+----------------------------------------------+---------------------------------------------------+
| AGENT FLOW DIAGRAM (48% width, full height)  | PROMPT & YAML INSPECTOR (52% width, full height)  |
| [Fit All] [Fit Width] [-] 55% [+]  [Details] | Selected Node: Market Analyst (Fast Tier)         |
+----------------------------------------------+---------------------------------------------------+
|        +--------------------+                | Tabs: [*Agent Prompt*] [Shared Tools (22)] [YAML] |
|        |   Start Research   |                | File: [market_analyst / system_prompt.md       v] |
|        +---------+----------+                | +-----------------------------------------------+ |
|                  |                           | | 1 | You are the Market Analyst on a structured| |
|   +--------------+--------------+            | | 2 | equity research desk. Analyze OHLCV price | |
|   v              v              v            | | 3 | action, key moving averages, RSI/MACD,    | |
| [Market]     [Social]       [News]  [Fund.]  | | 4 | and volume regimes...                     | |
|   \              |              /     /      | |   |                                           | |
|    +-------------+-------------+-----+       | |   | (Full-height CodeMirror editor;           | |
|                  v                           | |   |  Ctrl+S saves; clicking any node on the   | |
|        [Bull vs. Bear Debate (1 rd)]         | |   |  left switches the active prompt file)    | |
|                  v                           | |   |                                           | |
|           [Trader Proposal]                  | +-----------------------------------------------+ |
|                  v                           | [Revert File]                      [Save (Ctrl+S)]|
|         [Risk Debate (1 rd)]                 |                                                   |
|                  v                           |                                                   |
|          [Portfolio Manager]                 |                                                   |
+----------------------------------------------+---------------------------------------------------+
```

---

### 6.11 Settings (`#settings`) — Clean Vertical Sections with Advanced Drawers

- **Fixes:** Cuts the 20-field wall on Research Settings down to 5 core fields (Provider, Deep Model, Fast Model, Reasoning Effort, API Status) with `[> Advanced token budgets, concurrency & Laya social router]` expandable below. Separates read-only Diagnostics from the destructive Restore section.

```text
+------------------------+-------------------------------------------------------------------------+
| SETTINGS SECTIONS      | AI MODELS & RESEARCH ENGINE                           [Save Settings]   |
+------------------------+-------------------------------------------------------------------------+
| [*] AI Models & Engine | PRIMARY RESEARCH PROVIDER                                               |
| [ ] Broker & Data Keys | Provider:     [Codex (Existing Sign-In)        v]  Status: [Connected]  |
| [ ] Safety & Order Gate| Deep Model:   [gpt-5.3-codex                   v]  Reasoning: [High  v] |
| [ ] Backup & Recovery  | Fast Model:   [gpt-5.3-codex                   v]  Reasoning: [Mediumv] |
|                        |                                                                         |
|                        | [> Advanced Budgets, Concurrency & Laya Screening (14 fields)]          |
|                        |                                                                         |
|                        | ----------------------------------------------------------------------- |
|                        | (On "Backup & Recovery" tab:                                            |
|                        |  Top card = System Health Chips [Desk: OK] [Nautilus: OK] [SQLite: OK]  |
|                        |  Middle card = [Export Workspace Backup]                                |
|                        |  Bottom red-bordered card = DANGER ZONE: Restore from Backup            |
|                        |  with typed confirmation phrase.)                                       |
+------------------------+-------------------------------------------------------------------------+
```
