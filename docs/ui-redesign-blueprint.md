# UI Redesign Blueprint (v2 — Council-Reconciled Master Spec)

This document is the reconciled UI redesign blueprint for the TradingAgents desktop workspace (`http://127.0.0.1:8098/`). It synthesizes the baseline wireframes with independent audits by **Claude Sonnet 5.5** (`docs/ui-redesign-review-sonnet.md`), **Grok 4.7** (`docs/ui-redesign-review-grok.md`), and **Gemini 4 Argon** (`docs/ui-redesign-review-argon.md`).

- **Design system:** Keep the dark charcoal desk palette, green action accents, and tabular numbers from `DESIGN.md`.
- **Core safety rule:** Keep research, order preparation (proposals), order approval, and broker submission strictly separate (`PRODUCT.md`).
- **No fake backend fields:** Every wireframe element maps 1:1 to real fields and endpoints in `tradingagents/web/static/app.js`, `workflows.js`, and `server.py`.

---

## 1. What the Sonnet / Grok / Argon Council Fixed in v2

All three reviewers agreed the initial v1 draft diagnosed the right pain points (no stock picker on Research, 270px+ of stacked headers/filters/prose eating the page, and walls of text instead of scannable views) but caught critical flaws that v2 corrects:

1. **Separated "Inspected Stock" from "Checked Research Batch":**
   - Clicking a stock row changes only `selectedSymbol` (the stock you are reading in the chart or report pane).
   - Checking a box changes `selectedSymbols` (the batch to run research on). The toolbar explicitly says `2 checked · reading AMZN`. Filtering a list never changes what is checked, and the app never starts with all 24 universe stocks pre-checked.
2. **Kept the Compact Research Confirmation Step:**
   - Clicking **Run Research (N)** opens the compact confirmation popover (`reviewResearch`: stock count, models, New York trade date, ETA if timing samples exist or `"No timing yet"`, and `"Places no orders"`). Once confirmed, the UI automatically selects and scrolls to the **first stock in the batch**.
3. **Used the Real 7-State Research Progress Counts:**
   - Replaced the misleading green `24/24 finished` bar with the 7 real backend counts (`completed`, `incomplete`, `interrupted`, `failed`, `cancelled`, `running`, `queued`). Cancelled is neutral slate, never green.
   - A rating badge (`Buy`, `Hold`, `Underweight`, `Sell`) appears **only** when a final recommendation is saved. Cancelled stocks show `Cancelled — no verdict`, and `"Loading..."` clears immediately when loading ends.
4. **Grounded Research Cards in Real Stored Artifacts:**
   - Since analyst reports are stored as markdown (`result.reports`), the 4 Analyst Cards display the report's saved status (`Saved` / `Missing` / `Stopped`) plus the **first-paragraph excerpt** (labeled `Excerpt`), real **Laya social stance counts** (`result.social_sentiment`), and real **`completion_gaps`**.
   - Preserved all **5 evidence tabs** on Research: `Summary`, `Reports`, `Debate & Risk`, `Sources`, and `Activity` (filtered to the inspected stock by default, with a `Whole run` toggle).
5. **Cut Fixed Top Chrome to `80px` (`84%–91%` Data Height):**
   - Deleted `.workspace-footer` (`+36px`), deleted multi-paragraph page headers, and removed duplicate account numbers from the global top bar.
   - The 5 real account figures (`Equity`, `Cash`, `Buying Power`, `Long Value`, `Open Orders` — no invented `Day P/L`) appear in a single `40px` strip on **Dashboard** and **Portfolio** only.
6. **Restored Every Real Desk Capability (Zero Dropped Features):**
   - **Markets:** Kept `Universe & Watchlists`, `Yahoo Screener`, and `Saved Scans`; kept `Chart`, `Research`, `Options` (disabled with a reason when empty), and `Position & Ticket`; kept the collapsible `.chart-inspectors` drawer (`Studies & Formulas`, `Drawings`, `Comparison`, `Source Data`); kept 25/50/100 paging for up to 1,000 stocks.
   - **Portfolio vs. Orders:** Kept **Portfolio → Proposed** strictly for the session-only joint deep-model synthesis (`$10,000` model capital, explicit exclusions, no direct order staging) and kept **Human Baskets** in **Orders → Baskets**.
   - **Orders:** Preserved the 3-stage safety chain (`1. Draft & Save Revision → 2. Check & Approve Exact Revision → 3. Submit Separately to Broker`) plus **Uncertain Outcome Recovery (`resolve_never_dispatched`)**.
   - **Strategy Lab:** Preserved both real engines (`Saved-Plan Simulations` and `Walk-Forward Experiments` with declarative rules & Optuna/Grid search) and the required **Save Immutable Preview** gate before running.
   - **Settings:** Preserved all 5 categories (`Account & Engine`, `Research & Models`, `Universe & Keys`, `Trading Rules & Native Cache`, `Diagnostics & Backup`).

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

### 6.2 Dashboard (`#overview`) — 5-KPI Strip + Unclipped Linked Grid

- **Contract notes:** Uses the 5 real `state.account` fields (`Equity`, `Cash`, `Buying Power`, `Long Value`, `Open Orders`). Watchlist starts with `0 checked`. Bottom panes use compact 2-line empty states so buttons never clip (fixes L1). Chart uses hollow down-candles (`□`), solid up-candles (`■`), a visible overlay legend, and an expandable recent-bars table.

```text
+----------------------------------------------------------------------------------------------------------+
| DASHBOARD · Account observed Oct 28, 20:35 ET               0 checked [Run Research] [Open Portfolio ->] |
+----------------------------------------------------------------------------------------------------------+
| EQUITY $100,000.00 | CASH $100,000.00 | BUYING POWER $100,000.00 | LONG VALUE $0.00 | OPEN ORDERS 0      |
+--------------------------------------------------+-------------------------------------------------------+
| WATCHLIST: PNIS (24)          [Update Quotes]    | AMZN · $252.51 (+1.14%) · IEX 16:00 ET (Closed)       |
| [Search...] [View: All (24) v] [Manage]          | Period: [1W] [*1M*] [3M] [6M]       [Open in Markets] |
+--------------------------------------------------+-------------------------------------------------------+
| SYM     LAST      CHG%    RESEARCH    QUOTE AGE  | Legend: ■ Up  □ Down  — SMA20 ($248.10) - - SMA50     |
| AMZN *  $252.51   +1.14%  [Hold]      Closed     |  260 |          .|.                                   |
| INTC    $22.40    -0.85%  [Underwt]   Closed     |  255 |      .|. |■|  .|.                              |
| TER     $108.12   -1.40%  [Sell]      Closed     |  250 |  .|. |□|      |■|                              |
| AAPL    $231.10   +0.42%  Cancelled   Closed     |  245 |________________________________________________|
| GOOGL   $182.30   -0.12%  Cancelled   Closed     |  Vol |  ||  |||  ||  ||||   Source: Saved 1Day (IEX)  |
| 1–24 of 24                   Rows: [25v] [<] [>] | [▸ Recent OHLCV bars table (22 sessions)]             |
+-------------------------------+------------------+-----------------------------------+-------------------+
| SAVED RESEARCH: AMZN          | POSITIONS (0)                    | OPEN ORDERS (0)                       |
+-------------------------------+----------------------------------+---------------------------------------+
| [HOLD] · Trade date Oct 28    | No open positions in Alpaca.     | No open orders waiting at Alpaca.     |
| First line of saved decision  | [Browse Markets]                 | 1 saved draft proposal (SGOV).        |
| [Read Report] [Prepare Order] | (Compact — never clips!)         | [Open Orders & Drafts (1)]            |
+-------------------------------+----------------------------------+---------------------------------------+
```

---

### 6.3 Markets (`#markets`) — Universe/Watchlists, Screener, Saved Scans & Full Instrument Studio

- **Contract notes:** Preserves all 3 real Markets modes (`Universe & Watchlists`, `Yahoo Screener`, `Saved Scans`) and all 4 real Instrument tabs (`Chart`, `Research`, `Options`, `Position & Ticket`). Includes the collapsible `.chart-inspectors` drawer (`Studies & Formulas`, `Drawings`, `Comparison`, `Source Data`) and the `Current IEX Cache` vs. `Immutable Saved Research Inputs` context switcher. Collapses the 10-field backfill form into 1 line (`[Get 252 daily bars] [More ▾]`). Hides duplicate company subtitle when `companyName(sym) === sym` (fixes L13).

```text
+----------------------------------------------------------------------------------------------------------+
| MARKETS   [*Universe & Watchlists (24)*] [Yahoo Screener] [Saved Scans]   0 checked · [Run Research (0)] |
+----------------------------------------+-----------------------------------------------------------------+
| List: [All Universe: PNIS (24) v] [+New]| AMZN · $252.51 (+1.14%) · Bid $252.40 / Ask $252.60 · Closed   |
| [Search...] [View: All v] [Sortv] [Ed] | Tabs: [*Chart*] [Research] [Options (none)] [Position & Ticket] |
+----------------------------------------+-----------------------------------------------------------------+
| SYM     PRICE    CHG%   BARS    RATING | Context: [Current IEX Cache v]  Interval: [*1Day*] [1Hr] [15m]  |
| AMZN *  $252.51  +1.14% 1,255   [Hold] | Drawers: [Studies & Formulas] [Drawings] [Comparison] [Source▾] |
| INTC    $22.40   -0.85% Missing [Undwt]| +-------------------------------------------------------------+ |
| TER     $108.12  -1.40% Missing [Sell] | | History: 1,255 daily bars cached (Oct 28) · [Refresh] [More]| |
| AAPL    $231.10  +0.42% Missing Canceld| +-------------------------------------------------------------+ |
| GOOGL   $182.30  -0.12% Missing Canceld| |                                                             | |
| META    $590.40  +1.85% Missing Canceld| |             FULL-HEIGHT LIGHTWEIGHT CHART                   | |
| MSFT    $428.15  +0.33% Missing Canceld| |        (Hollow down-candles, volume, drawings,              | |
| NVDA    $141.80  +2.10% Missing Canceld| |         and 1-click "Copy price to ticket" anchor)          | |
| 1–24 of 24             [25v] [<] 1 [>] | |                                                             | |
| (Clicking [Ed] toggles batch checks,   | +-------------------------------------------------------------+ |
|  [Select page], [Columns▾], [Remove])  | [▸ Selected bar readout & OHLCV table (a11y / keyboard)]        |
+----------------------------------------+-----------------------------------------------------------------+
```

---

### 6.4 Research (`#research`) — Inline Picker + Confirm Dialog, 7-State Progress, & Real Excerpts

- **Solves U1, U2, L3, L4, and Research P1s:**
  - **Pick & Run on Research (U1):** Check stocks in the left rail or use `[Pick / Unfinished (21) v]` in the toolbar, then click `[▶ Run Research (N)]` to open the compact confirmation dialog (`reviewResearch`: count, models, trade date, ETA if available, `"Places no orders"`).
  - **Auto-focus on launch (U2):** Starting a run sets `selectedSymbol` to the first symbol in the batch, scrolls it into view, and opens `Summary`.
  - **7-State Progress Strip:** Shows `3 completed · 21 cancelled · 0 failed · 0 incomplete · 0 interrupted · 0 running`.
  - **No Fake "Sell" Badge (L3) or Stuck Loading Notice (L4):** Cancelled/unfinished stocks display `Cancelled — no verdict` and clear `"Loading..."` immediately.
  - **5 Evidence Tabs:** `Summary`, `Reports (7)`, `Debate & Risk`, `Sources (9)`, `Activity (40)`.

```text
+----------------------------------------------------------------------------------------------------------+
| RESEARCH  [Pick: 2 checked (AMZN, INTC) v] [Select Unfinished (21)] [Clear]   [▶ Run Research (2)...]    |
+----------------------------------------------------------------------------------------------------------+
| [===3 Completed===|-------------21 Cancelled-------------] 3 completed · 21 cancelled · 0 running        |
+-----------------------------+----------------------------------------------------------------------------+
| STOCKS (24)  [Show: All v]  | AMZN · Reading (Completed Oct 28)   [Open in Markets] [Prepare Order ->]   |
| [Search...]        [Manage] | Tabs: [*Summary*] [Reports (7)] [Debate & Risk] [Sources (9)] [Activity]   |
+-----------------------------+----------------------------------------------------------------------------+
| [ ] SYM   STATUS    VERDICT | +------------------------------------------------------------------------+ |
| [x] AMZN* Completed [HOLD]  | | VERDICT: [HOLD] · Trade Date: 2026-10-28 · Workflow: Default           | |
| [x] INTC  Completed [UNDWT] | | Coverage: 7/7 reports saved · 1 gap (News rate limit HTTP 429)         | |
| [ ] TER   Completed [SELL]  | +------------------------------------------------------------------------+ |
| [ ] AAPL  Cancelled —       |                                                                            |
| [ ] GOOGL Cancelled —       | ANALYST REPORT EXCERPTS (First saved paragraph · click to open full text): |
| [ ] META  Cancelled —       | +-----------------+ +-----------------+ +-----------------+ +------------+ |
| [ ] MSFT  Cancelled —       | | MARKET [Saved]  | | FUNDAMENTALS    | | NEWS [1 gap]    | | SENTIMENT  | |
| [ ] NVDA  Cancelled —       | | Excerpt: first  | | Excerpt: first  | | Excerpt: first  | | Laya CPU:  | |
| 1–24 of 24   [25v] [<] 1 [>]| | saved lines...  | | saved lines...  | | saved lines...  | | Bull/Bear  | |
| (Row click = inspect;       | | [Open report ->]| | [Open report ->]| | [Open report ->]| | counts     | |
|  Checkbox = run batch;      | +-----------------+ +-----------------+ +-----------------+ +------------+ |
|  [Manage] = delete mode)    |                                                                            |
|                             | COMMITTEE DEBATE & RISK EXCERPTS (Saved text from debate state):           |
|                             | +-----------------------------------+ +----------------------------------+ |
|                             | | BULL vs BEAR DEBATE (Saved)       | | RISK & TRADER PROPOSAL (Saved)   | |
|                             | | Clipped first lines of bull, bear,| | Clipped first lines of trader    | |
|                             | | and research manager synthesis... | | plan and 3-way risk discussion...| |
|                             | | [Read full debate ->]             | | [Read risk debate ->]            | |
|                             | +-----------------------------------+ +----------------------------------+ |
|                             |                                                                            |
|                             | DISPOSITION: [Needs review v]  Note: [________________________] [Save]     |
|                             | [▸ Read full Portfolio Manager decision (`final_trade_decision`)]          |
|                             | [▸ Technical record (Run ID, config revision, artifact details)]           |
+-----------------------------+----------------------------------------------------------------------------+
```

---

### 6.5 Portfolio (`#portfolio`) — Reconciled Holdings, Session-Only Proposed Model, & Performance

- **Contract notes:** Keeps **Proposed Model Portfolio** (`POST /api/portfolio-model`, session-only joint synthesis with `$10,000` default model capital and explicit exclusions) strictly separate from Human Baskets (`Orders → Baskets`). Formats numbers with `money()`, `percent()`, and `color()`. Hides empty table headers (L11) and caps the empty Performance state to `140px` with a visible `[Collect Account History in Journal →]` button (L2).

```text
+----------------------------------------------------------------------------------------------------------+
| PORTFOLIO   Tabs: [*Positions (0)*]  [Proposed Model Portfolio]  [Performance]         [Refresh Account] |
+----------------------------------------------------------------------------------------------------------+
| EQUITY $100,000.00 | CASH $100,000.00 | LONG VALUE $0.00 | UNREALIZED P/L $0.00 (0.00%) | SYNC: Clean ✓  |
+----------------------------------------------------------------------------------------------------------+
| (TAB 1: POSITIONS — hides empty table headers when 0 positions; shows compact 120px card:)               |
| +------------------------------------------------------------------------------------------------------+ |
| | No open positions in your connected Alpaca Paper account (Cash account, long only).                  | |
| | [Browse Universe in Markets]    [Open Proposed Model Portfolio]    [Open Orders & Baskets (1)]       | |
| +------------------------------------------------------------------------------------------------------+ |
| [▸ Technical reconciliation record (native cache, broker snapshot & epoch details)]                      |
|                                                                                                          |
| (TAB 2: PROPOSED MODEL PORTFOLIO — Session-only joint synthesis; never stages orders directly:)          |
| +------------------------------------------------------------------------------------------------------+ |
| | JOINT AI MODEL PORTFOLIO (Session-Only Advisory Synthesis · Separate from Human Baskets & Orders)    | |
| | Model Capital (USD): [$10,000.00 ]  [▶ Model Portfolio]   Eligible: 3 of 24 stocks · 21 excluded     | |
| | ---------------------------------------------------------------------------------------------------- | |
| | SYM    TARGET WT   WHOLE SHARES   REF PRICE (DATED)          REF VALUE    RATIONALE & ENTRY          | |
| | AMZN   25.00%      9 shares       $252.51 (Oct 28, IEX)      $2,272.59    [▸ View rationale & rules] | |
| | Residual Cash: $7,727.41 · Excluded (21): AAPL (cancelled), GOOGL (cancelled), INTC (0% weight)...   | |
| +------------------------------------------------------------------------------------------------------+ |
|                                                                                                          |
| (TAB 3: PERFORMANCE — Capped 140px empty state when <2 captures exist, fixing L2:)                       |
| +------------------------------------------------------------------------------------------------------+ |
| | View: [*Equity*] [Returns %]   Saved Interval: [No saved intervals v]   Basis: Broker-reported USD   | |
| | [📈 24px] Needs at least 2 saved account-history observations. [Collect Account History in Journal->]| |
| +------------------------------------------------------------------------------------------------------+ |
```

---

### 6.6 Orders (`#orders`) — 3-Stage Order Lifecycle, Baskets, & Uncertain Command Recovery

- **Contract notes:** Preserves the 3-stage safety chain (`1. Draft & Save Revision → 2. Check & Approve Exact Revision → 3. Submit Separately to Broker`), progressive disclosure for `Options / Multi-Leg / Exits / Replacement`, `Orders → Baskets` (`Targets`, `Impact`, `Drafts`), always-visible 1-line readiness blocker, inline confirmation + timestamped receipt for Submit/Cancel/Replace, and `resolve_never_dispatched` recovery when an order command times out.

```text
+----------------------------------------------------------------------------------------------------------+
| ORDERS   [*Single Order Ticket*] [Open Orders (0)] [Proposals & History (1)] [Baskets]  [Orders: Active▾]|
+----------------------------------------------------------------------------------------------------------+
| Readiness: Ready for paper orders · Cash $100,000.00 · Cash account (no shorting) · Policy rev 1         |
+---------------------------------------------+------------------------------------------------------------+
| STAGE 1: DRAFT & SAVE ORDER PROPOSAL (44%)  | STAGE 2 & 3: APPROVAL, SUBMISSION & OPEN ORDERS (56%)      |
+---------------------------------------------+------------------------------------------------------------+
| Asset: [*US Equity*] [US Option / MLeg]     | SELECTED PROPOSAL: SGOV · Revision #2 (Deferred)           |
| Symbol: [SGOV    ]  Side: [(*) Buy ( ) Sell]| Terms: BUY 1 SGOV · MARKET · DAY · Regular session         |
| Qty:    [1       ]  Type: [Market        v] | Estimated Cost: ~$100.32 · Cash After: ~$99,899.68         |
| TIF:    [DAY     v] Sess: [Regular       v] | ---------------------------------------------------------- |
| [▸ Exits (Bracket/OTO/OCO) & Replacement]   | STAGE 2: POLICY CHECK & EXACT-REVISION APPROVAL            |
| [▸ Evidence Scopes & Linked Research]       | Policy Check: Passed all 10 trading rules     [Check Order]|
|                                             | [Approve Exact Revision #2] (Single-use, bound to SHA-256) |
| [Preview Impact]    [Save Draft Revision]   | ---------------------------------------------------------- |
|                                             | STAGE 3: SEPARATE BROKER SUBMISSION                        |
|                                             | [Submit Approved Order to Alpaca Paper] (Confirms terms)   |
|                                             | Last Receipt: None this session.                           |
|                                             | (If outcome_unknown: [! Uncertain outcome — Refresh first] |
|                                             |  [Refresh Status] [Check if Submit Was Never Sent])        |
|                                             | [▸ Technical record (Terms SHA-256, policy & audit IDs)]   |
+---------------------------------------------+------------------------------------------------------------+
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

