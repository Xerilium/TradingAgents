# TradingAgents UI Redesign Blueprint (Canonical Impeccable Specification)

- **Status:** Canonical v4 Master Specification (Consolidates all Council Reviews, Pro-Trader Audits, and Existing-Backend Missed Opportunities)
- **Target Surface:** `tradingagents/web/static/` (`index.html`, `app.js`, `workflows.js`, `command-controls.js`, `nautilus.js`, `lists.js`, `report-format.js`, `market-chart.js`, `app.css`, and `ui-*.css`)
- **Design System & Product Authority:** [`PRODUCT.md`](../PRODUCT.md) and [`DESIGN.md`](../DESIGN.md) (`TradingAgents Paper Desk`, Impeccable `Operate` mode)
- **Companion Defect Log:** [`docs/ui-design-critique.md`](ui-design-critique.md)

---

## 1. Non-Negotiable Ground Rules

1. **Zero New Backend Features (Frontend-Only Wiring):**
   - **No Python backend changes.** We are building UI strictly for the features, endpoints, and JSON fields that **already exist today** in `tradingagents/web/server.py`, `service.py`, and `nautilus_worker.py`.
   - Every control, badge, table column, and drawer in this specification names the exact existing `/api/*` endpoint and `state.*` field it binds to.
   - Any feature that exists only as an unwired Python helper or would require a new server route is explicitly listed in **Section 1.2 (Excluded — Do Not Build)**.
2. **Strict Separation of Authority (`PRODUCT.md`):**
   - Selecting a stock (`selectedSymbol`), checking a research batch (`selectedSymbols`), running AI research (`POST /api/runs`), synthesizing a session-only model portfolio (`POST /api/portfolio-model`), saving a draft order proposal (`POST /api/investor`), approving exact revision terms (`POST /api/approvals`), and submitting to Alpaca (`POST /api/commands`) are distinct actions. None ever implies or auto-triggers the next.
3. **The 85% Data / 15% Chrome Budget (Impeccable `operate` + `distill` + `layout`):**
   - **Global App Bar:** `36px` single line.
   - **Workspace Toolbar:** `40px` single line (Sub-tabs with `role="tablist"` + batch status chip + primary action).
   - **Active Status / Progress Strip:** `6px` bar + `24px` 1-line summary (rendered only when active or needed).
   - **Footer & Prose Headers:** `.workspace-footer` (`36px`) and multi-sentence `pageHeader` paragraphs are deleted.
   - **Result:** **84% to 91% of viewport height** on `1920×1080` and `1440×900` belongs to actual data panes (tables, charts, reports, diagrams, order tickets).
4. **Direct DOM Rendering (Delete Post-Render DOM Scraping):**
   - Delete fragile post-render DOM-moving functions (`layoutOrders()`, `layoutBasketGroups()`, `layoutMarkets()`, `compactScannerMarkup()`, and sibling-scraping loops in `renderAlerts()` / `renderSettingsDiagnostics()`). Render HTML directly into the target 2-column and tabpanel containers, and update panes in place without wiping scroll position or input focus.

---

### 1.1 Existing Backend Capabilities Newly Surfaced in This UI (Zero Backend Edits)

Our audit of all 143 Python files against `tradingagents/web/static/` found **15 existing backend capabilities** already returned in `/api/state` or accepted by `/api/*` endpoints that the old UI either hid or dumped as raw `<pre>` JSON. All 15 are wired into the wireframes in Section 6:

| ID | Existing Endpoint / `state` Path | What the Backend Already Provides Today | Where This Blueprint Wires It |
|---|---|---|---|
| **E-01** | `POST /api/runs` (`server.py:478`, `service.py:2174`) | Accepts `analysis_date` (point-in-time historical research date with SEC EDGAR filing-date and FRED vintage pinning) and `exclude_fred: bool`. | **Research Confirm Popover (`Section 6.4`)**: Optional `Analysis Date` picker (defaults to `Today`) and `[ ] Exclude FRED macro series` checkbox. |
| **E-02** | `state.nautilus.market_data[sym].quote` & `.trade` (`nautilus_worker.py:309`) | Provides `bid_price`, `ask_price`, `bid_size`, `ask_size`, `trade.price`, `trade.size`, and `previous_close`. Two policy rules (`max_spread_bps`, `min_quote_size`) check these exact numbers. | **Instrument Header & Order Ticket (`Sections 6.2, 6.3, 6.4, 6.6`)**: Shows `Bid $252.40 (300) x Ask $252.60 (100) · Spread 8 bps` (labeled `IEX displayed size`). |
| **E-03** | `state.nautilus.market_data[sym].session_eligibility` (`nautilus_worker.py:155, 183`) | Provides `fractionable`, `fractional_eh_enabled`, `overnight_tradable`, `overnight_halted`, plus `alpaca_asset` (`exchange`, `status`, `tradable`, `attributes`). | **Instrument Header & Order Ticket (`Sections 6.3, 6.4, 6.6`)**: Compact capability badges (`Fractional ✓`, `Ext-Hrs ✓`, `Overnight Halted ⚠`). |
| **E-04** | `state.positions[]` (`nautilus_worker.py:853`, `service.py:2156`) | Raw Alpaca position rows include `unrealized_intraday_pl`, `unrealized_intraday_plpc`, `change_today`, `lastday_price`, `cost_basis`, and `qty_available` (shares not locked in working sell orders). | **Portfolio Positions (`6.5`), Dashboard (`6.2`), & Order Ticket (`6.6`)**: Adds `Today P/L ($, %)` and `Avail Qty` columns/readouts. |
| **E-05** | `state.account` (`nautilus_worker.py:853`, `service.py:2155`) | Includes `status`, `trading_blocked`, `account_blocked`, `trade_suspended_by_user`, `pattern_day_trader`, `daytrade_count`, `multiplier`, `options_buying_power`, `initial_margin`, `maintenance_margin`. | **Global Shell (`6.1`) & Settings → Account (`6.11`)**: Shows a warning chip in the Shell if `trading_blocked` or `account_blocked` is true; shows a clean read-only Account Flags table in Settings. |
| **E-06** | `state.investor.current_checks[id]` (`policy_evaluation.py:53`, `investor.py:14`) | Returns `checks[]` (`name`, `passed`, `reason`, `details`) for all 10 trading rules (`cash_reserve`, `max_position`, `gross_exposure`, `loss_limit`, `scenario_loss`, `sector`, `correlation`, `spread`, `quote_size`, `quote_age`), plus `conditional_group.stop_loss_estimate_before_fees` and `risk_evaluation.policy_scenarios`. | **Orders Stage 2 (`Section 6.6`)**: Replaces the raw `<pre>` JSON dump with a **10-Rule Policy Check Table** (failing rules first, showing observed value vs. limit) and displays bracket `Stop-loss estimate before fees`. |
| **E-07** | `GET /api/stock-evidence?symbol=SYM` (`stock_evidence.py`, `server.py:239`) | Fetches and caches **SEC EDGAR Point-in-Time XBRL Statements** (`balance_sheet`, `income_statement`, `cashflow`) and `SEC SIC` industry classification, **Alpaca Corporate Actions** (`dividends`, `splits`, `mergers`, `spinoffs`), **Alpaca News**, and **Alpha Vantage Earnings/Fundamentals**. | **Markets (`6.3`) & Research (`6.4`)**: Surfaces an `[Evidence & Filings]` sub-tab/drawer with formatted XBRL financial tables, Ex-Dividend/Split dates, and news headlines instead of burying them inside order-evidence disclosures. |
| **E-08** | `POST /api/runs/local-laya` & `result.social_sentiment` (`service.py:1825`) | Runs on-demand local GPU/CPU Laya batch screening over retained StockTwits posts (`result.local_laya_batch`) and stores per-post classification (`bullish`, `bearish`, `neutral`, `status`, `stop_reason`). | **Research (`Section 6.4`)**: Places `[Screen Saved Posts Locally]` and a structured **Social Stance Breakdown** directly on the Sentiment card and `Reports → Social` view. |
| **E-09** | `state.orders[]` & `state.commands` (`command-controls.js`, `linked_orders.py`, `execution_lifecycle.py`) | Carries linked exit metadata (`group_class`: `bracket`/`oto`/`oco`, `group_role`, `exit_active`, `exit_reserved`, `replaced_by`), trailing-stop `hwm` (high-water mark) and moving `stop_price`, command states (`not_sent`, `admitted_not_dispatched`, `submitting`, `outcome_unknown`), and `POST /api/commands` `resolve_never_dispatched`. | **Orders Blotter & Stage 3 (`Section 6.6`)**: Shows plain-English transport chips (`Not sent`, `Sent`, `Outcome unknown — Refresh first`), linked-exit status chips (`Entry open · exits waiting`, `Protected`), and trailing `HWM / Moving Stop $`. |
| **E-10** | `state.fills[]` & `POST /api/native-report` (`service.py:2159, 2180`) | Provides fill `price`, `qty`, `commission`, `ts_event`, `native_application` (`proven_in_current_process`, `historical_source_only`), and `fee_provenance.fill_sources[]`. | **Orders → Fills (`Section 6.6`)**: Replaces raw `<pre>` JSON blocks in `brokerOrderTable()` with a tabular **Fills & Fee Provenance Table**. |
| **E-11** | `state.investor.data.baskets[]` (`baskets.py:117-154`, `service.py:1490`) | Computes `hypothetical_cash`, per-leg `equity_weight_pct_estimate`, `turnover_pct`, `pending_net_quantity`, `quantity_if_working_orders_fill`, `residual_cash`, and `complete_scenario` vs. `partial_scenario` policy checks. | **Orders → Baskets (`Section 6.6`)**: Replaces the `<pre>` JSON dump in `basketCommandControls()` with a **Before/After Weight, Turnover %, & Complete vs. Partial Fill Table**. |
| **E-12** | `GET /api/evaluations` (`evaluation_worker.py:1218, 1322`, `server.py:232`) | Returns `native_result` (`asdict(engine.get_result())` from Nautilus 1.231.0 containing `stats_pnls` and `stats_returns`—Win Rate, Profit Factor, Expectancy, Sharpe/Sortino, Volatility), plus walk-forward `folds`, `trials`, and `reports` (`orders`, `fills`, `positions`, `account`). | **Strategy Lab (`Section 6.7`)**: Surfaces the **Nautilus Simulation Quality Strip** (when `native_result` stats are present), **Walk-Forward Folds Table**, and **Closed-Trades Table** instead of raw JSON `<details>`. |
| **E-13** | `GET /api/reporting` & `POST /api/reporting` (`performance.py`, `report_exports.py`, `server.py:245, 456`) | Computes `time_weighted` return, `dietz` (Modified Dietz), `drawdown`, `external_flows`, `benchmark_comparison` (`benchmark_price_return`, `excess_return`), and `action: "export_csv"` (`holdings`, `activity`, `performance`). | **Portfolio → Performance (`Section 6.5`)**: Plots the benchmark series and drawdown shading on the chart, marks external cash flows, and exposes `[Export CSV ▾]` (`Holdings`, `Activity`, `Performance`). |
| **E-14** | `state.nautilus.trade_stream` (`execution_lifecycle.py:1442`) | Reports live broker execution stream status (`listening`, `connecting`, `not_started`) and `gap` details. | **Global Shell (`Section 6.1`)**: Adds a live `Stream` status dot next to `Nautilus` in the left navigation rail. |
| **E-15** | `run.gateway_evidence` & `run.source_evidence` (`service.py:1755`) | Records structured vendor attempts (`sec_edgar`, `yahoo`, `fred`, `polymarket`, `ddgs`, `laya`) and Maenifold Gateway calls (`maenifold.memory`, `maenifold.graph`, `maenifold.thinking`) with timestamps, outcomes, and `HTTP 429` retry delays. | **Research → Sources & Activity (`Section 6.4`)**: Adds a **Vendor & Memory Provenance Strip** (`SEC EDGAR`, `Yahoo`, `Polymarket`, `FRED`, `Maenifold`, `Laya`) and filters `Activity` to the focused stock with an `Errors / 429s only` toggle. |

---

### 1.2 Excluded Capabilities (Would Require New Backend Code — Do Not Build)

To honor **"We're here to wire up what we have and nothing more"**, the following items found in unused Python files are **strictly out of scope** for this UI redesign because they have no HTTP route or state field in `server.py` / `service.py` today:

| Excluded Item | Why It Is Excluded |
|---|---|
| Market Open/Close countdown (`next_open` / `next_close`) | `service.py:2162` currently sends only `state.clock = {"is_open": ...}`. Changing `service.py` is a backend change; the UI will display `Market: Open` / `Market: Closed` from `state.clock.is_open`. |
| Standalone HTML Tear Sheet export (`tradingagents/report_html.py`) | `report_html.py` is a CLI helper with no route in `server.py`. The UI will use the existing `GET /api/runs/{id}` JSON export and browser print stylesheet. |
| 5-Day Benchmark Alpha Settlement & Reflection (`tradingagents/memory/settlement.py`, `reflection.py`) | CLI/agent memory helpers with no `/api/*` endpoint in `server.py`. Do not invent a settlement column in Journal. |
| Standalone Polymarket or FRED Macro Dashboard (`polymarket.py`, `fred.py`) | These are LangGraph agent tools (`tradingagents/agents/tools.py`), not standalone web server endpoints. Their data appears inside saved research `news_report` and `source_evidence` receipts. |
| Server-side Laya 6-field summary (`tradingagents/web/laya_review.py`) | Used inside the research graph preflight, not exposed as a standalone web route. |
| Account-level Sharpe / Money-Weighted Return / Slippage-vs-Quote | Not computed by `performance.py` or `nautilus_worker.py`. Never invent financial metrics in browser JS. |

---

## 2. Industry Leader Patterns Adopted

We benchmarked against **Fidelity Active Trader Pro**, **IBKR Desktop (Mosaic)**, **TradingView Desktop**, **Koyfin**, and **FinChat / Fiscal.ai**, adapting their patterns to our exact backend contracts:

1. **Focus Symbol vs. Batch Set (Fidelity Active Trader Pro / IBKR Mosaic):**
   - Clicking any row sets `selectedSymbol` (the **one stock you are reading** across the linked Chart, Research, and Order Ticket panes).
   - Checking a row box sets `selectedSymbols` (the **batch set** for running research or bulk list actions).
   - Clicking a row **never** changes checkboxes; checking a box **never** changes the stock you are reading.
2. **Rating + Live Quote + Price Drift + Position on One Header (Koyfin / IBKR):**
   - A trader never reads a research rating without seeing: (a) how old the research is (`1d old`), (b) how much the price has moved since the research `trade_date` close (when saved bars are loaded), and (c) whether they already own the stock (`LONG 40`), have a `WORKING` broker order, or have an unsent `DRAFT` proposal.
3. **Portfolio Manager Decision & Trader Plan Above the Fold (FinChat / Koyfin):**
   - `Research → Summary` opens with the Verdict + Drift + Exposure Strip, followed immediately by the **Portfolio Manager Decision (`final_trade_decision`)** and **Trader Proposal (`trader_investment_plan`)** excerpts, then the **Bull vs. Bear (`investment_debate_state`)** and **Risk Trio (`risk_debate_state`)** columns, then the **4 Analyst Cards (`market`, `fundamentals`, `news`, `sentiment`)**.
4. **Docked Order Proposal Drawer — Zero Context-Destroying Page Hops (TradingView / ATP):**
   - Clicking **`[Prepare Order (T)]`** on Dashboard, Markets, Research, or Journal opens a **docked Order Proposal Drawer** on `selectedSymbol` right beside the Chart or Research view (`openTicket(symbol)` + `researchPreparation`). It never navigates away, never pre-selects an illegal short sell on a 0-share cash account, and keeps **Save Draft → Check/Approve → Submit** strictly separate.
5. **85%+ Data Canvas with Collapsible Inspectors (TradingView Desktop):**
   - Chart Studies, Drawings, Comparison, and Source Data stay in the collapsible `.chart-inspectors` right drawer (`ui-instrument.css`), giving the chart full width and height until a tool is clicked.

---

## 3. User Personas & Anti-Persona

1. **Alex — Daily Active Desk Operator (Primary):** Scans a 10–1,000 stock universe before the open or after the close, checks movers on Research or Markets, runs AI research, checks price drift and spread, and prepares paper limit orders.
2. **Jordan — Methodical Fundamental & Evidence Researcher:** Audits the full evidence trail—analyst reports, SEC EDGAR XBRL filings, corporate actions, Laya social post classifications, source URLs, HTTP 429 gaps, and Decision Journal outcomes.
3. **Morgan — Workflow & Quantitative Strategy Architect:** Customizes the 18-node agent graph and 94 prompt files in Workflows, synthesizes the session-only Proposed Model Portfolio, and runs saved-plan simulations and walk-forward experiments in Strategy Lab.
4. **Sam — First-Run Operator:** Opens the desk with an empty paper account, no cached price bars, or unset quote-age limits; needs calm, 1-line setup actions instead of red error walls or clipped buttons.
5. **Riley — Execution & Recovery Operator:** Manages working orders, linked exits (`Bracket / OTO / OCO`), trailing stops, paused order gates, and `outcome_unknown` command recovery (`resolve_never_dispatched`) after a timeout or restart.
6. **Anti-Persona — Autonomous Autopilot Trader:** Nobody uses this desk for one-click unreviewed trading. No hotkey or button ever combines preparation, approval, and broker submission.

---

## 4. Complete User Stories & Acceptance Criteria (US-01 to US-34)

| ID | Persona | User Story | Acceptance Criteria & Exact Backend Binding |
|---|---|---|---|
| **US-01** | Alex | Pick stocks and start research directly on **Research** (`U1`). | Research toolbar includes an inline universe search/picker, `[Unfinished (N)]`, `[Needs Research Today (N)]`, `[Clear]`, and `[▶ Run Research (N)]` (`POST /api/runs`). When `0` boxes are checked, the button offers `[▶ Run Research (SYM)]` for `selectedSymbol`. |
| **US-02** | Alex | Confirm research parameters (including optional historical date & FRED toggle) and auto-focus on launch (`U2`, `E-01`). | Clicking `Run Research` opens the compact confirm popover (`reviewResearch`: symbol count, models, ETA from `DeskLists.estimate` or `"No timing yet"`, optional `analysis_date`, `exclude_fred` checkbox, `"Places no orders"`). Confirming focuses the first batch stock if `selectedSymbol` is empty or in the batch. |
| **US-03** | Jordan | See honest 7-state run progress and never see a fake `Sell` badge (`L3`, `L4`). | Progress strip uses all 7 real counts (`completed`, `incomplete`, `interrupted`, `failed`, `cancelled`, `running`, `queued`). Rating badge (`Buy`/`Hold`/`Underweight`/`Sell`) renders **only** when `status === 'completed'` and `reports.final_trade_decision` exists. Cancelled stocks show `Cancelled — no verdict`, and `"Loading..."` clears when loading ends. |
| **US-04** | Alex | See research age, price drift since `trade_date`, and my live exposure on every verdict. | Research header joins `state.research[sym]` (`rating`, `trade_date`, `revision`), `state.quotes[sym]` (`price`, `change_pct`, `age_seconds`), `state.nautilus.market_data[sym].quote` (`bid_price`, `ask_price`, `bid_size`, `ask_size`), saved bar close on `trade_date` (when loaded in `DATA.history`), `positions()`, working `orders()`, and draft `state.investor.data.proposals`. |
| **US-05** | Jordan | Read Portfolio Manager Decision & Trader Proposal above the fold on Research `Summary`. | `Summary` orders content as: (1) Verdict + Price Drift + Exposure Strip, (2) **Portfolio Manager Decision** & **Trader Proposal** (first 6 lines + `[Read full]`), (3) **Bull vs. Bear** & **Risk Trio** columns, (4) **4 Analyst Status/Excerpt Chips** (`Market`, `Fundamentals`, `News`, `Sentiment` with Laya counts), and (5) compact bottom Disposition/Note bar. |
| **US-06** | Alex | Prepare an order from any screen via a docked drawer without losing chart or research context. | Clicking `[Prepare Order (T)]` on Dashboard, Markets, Research, or Journal opens a docked Order Proposal Drawer for `selectedSymbol` (`openTicket` + `researchPreparation`), leaving Side/Qty explicit and blocking illegal short sales when `positions()` is 0 on a long-only cash account. |
| **US-07** | Alex | Dedicate **84%–91% of viewport height** to data panes across all 10 tabs. | `.topbar` is `36px` single-line; Workspace Bar is `40px` single-line; `.workspace-footer` (`36px`) and multi-sentence `pageHeader` paragraphs are removed; `#main` padding is tightened to `8px 12px 12px`. |
| **US-08** | Alex | Scan a morning triage strip and unclipped 2×2 grid on **Dashboard** (`L1`). | Top 1-line `Needs attention` strip (`dashboardAttentionSummary`) shows working orders, unread alerts, stale quotes, and unresearched holdings (hidden when empty). Watchlist starts with `0 checked`, sorted by `Held first` + `|Chg%|`. Bottom panes (`Saved Research`, `Positions`, `Open Orders & Drafts`) never clip at `1080p` or `900p`. |
| **US-09** | Alex | See trader scan columns and a persistent Instrument Header on **Markets** (`L13`, `E-02`, `E-03`). | Scan table columns: `SYM | LAST | CHG% | BID×ASK (SPR) | POS | UPL% | WORKING | RSCH·AGE` (moving `BARS` count to the 1-line chart history bar and hiding duplicate `AMZN / AMZN` subtitles). Right pane keeps a persistent Instrument Header above `Chart | Research | Evidence & Filings | Options`. |
| **US-10** | Jordan | Inspect SEC EDGAR XBRL financials, Corporate Actions, and Alpaca News on **Markets** and **Research** (`E-07`). | `[Evidence & Filings]` tab/drawer renders cached `GET /api/stock-evidence?symbol=SYM` records: SEC EDGAR point-in-time `Balance Sheet`, `Income Statement`, `Cash Flow`, and `SIC` industry; Alpaca `Dividends / Splits / Mergers`; and Alpaca `News` headlines. |
| **US-11** | Jordan | Screen saved StockTwits posts locally with Laya and inspect post-level sentiment (`E-08`). | Sentiment card and `Reports → Social` expose `[Screen Saved Posts Locally]` (`POST /api/runs/local-laya`) and display Laya `bullish / bearish / neutral` counts, latency, and post table. |
| **US-12** | Jordan | Inspect structured Vendor & Maenifold provenance and filter `Activity` on **Research** (`E-15`). | `Sources` shows domain, capture date, and report category (never labeling every URL `"News analysis"`), plus vendor/gateway call summary chips (`SEC EDGAR`, `Yahoo`, `Polymarket`, `FRED`, `Maenifold`). `Activity` defaults to `selectedSymbol` with a `Whole run` toggle and an `Errors / 429s` filter. |
| **US-13** | Alex | Monitor populated Holdings with `Today P/L` and `Avail Qty` on **Portfolio** (`L11`, `E-04`). | `Portfolio → Positions` shows `SYM | QTY | AVAIL | AVG COST | LAST | TODAY P/L ($, %) | MKT VALUE | TOTAL UPL ($, %) | WT% | WORKING | RSCH·AGE | ACT` using `money()`, `percent()`, and `color()`. When `0` positions exist, hides empty `<thead>` headers and shows a compact 2-line empty card. |
| **US-14** | Morgan | Run the session-only **Proposed Model Portfolio** alongside live prices and drift (`Violation 2`). | `Portfolio → Proposed Model Portfolio` (`POST /api/portfolio-model`) stays strictly separate from Human Baskets (`Orders → Baskets`) and displays `MODEL REF (DATED)`, `LAST NOW (IEX)`, `DRIFT %`, and `YOUR POS` beside each target weight and whole-share allocation. |
| **US-15** | Jordan | View **Portfolio → Performance** with benchmark overlay, drawdown shading, CSV exports, and a capped empty state (`L2`, `E-13`). | When `<2` points exist, shows a `120px` card with a `24px` icon and `[Collect Account History in Journal →]`. When calculable, plots `time_weighted`, `benchmark_comparison` series, and `drawdown` shading, plus `[Export CSV ▾]` (`Holdings`, `Activity`, `Performance`). |
| **US-16** | Alex | Stage orders with live Bid/Ask/Size/Spread, click-to-seed Limit price, and `% of equity` sizing math (`E-02`, `E-04`). | `Orders` Stage 1 defaults to `LIMIT`, displays live `Bid×Size / Ask×Size / Spread bps`, `Quote Age`, `Current Position (`qty`, `qty_available`)`, and `Cash / Buying Power / Equity`. Clicking `Bid`, `Ask`, or `Last` seeds `Limit $` (`"from ask, not previewed"`); typing `Qty` shows live `$ notional`, `% of equity`, `% of cash`, and `post-trade weight %`; keeps `Stop $` and `Target $` visible. |
| **US-17** | Riley | See the 10-Rule Policy Check Table and Bracket Stop-Loss Risk in **Orders Stage 2** (`E-06`). | Stage 2 renders all 10 `checks[]` rows from `policy_evaluation.py` (failing rules first, with observed value vs. rule limit) and `conditional_group.stop_loss_estimate_before_fees` above a collapsed `<details>Technical record</details>`. |
| **US-18** | Riley | Confirm Submit/Cancel/Replace with duplicate-order guard, transport chips, and `resolve_never_dispatched` recovery (`E-09`). | Stage 3 warns if a working order already exists in that symbol, requires a 2-step inline confirmation showing exact terms, disables in-flight buttons to prevent double-submit, displays a timestamped receipt, and shows plain chips (`Not sent`, `Sent`, `Outcome unknown — Refresh first`) with `[Resolve Never Dispatched]`. |
| **US-19** | Riley | Inspect structured Fills (`fee_provenance`) and Human Baskets (`complete` vs. `partial` scenarios) without raw JSON dumps (`E-10`, `E-11`). | `Orders → Fills` renders a tabular fills blotter (`Time | Sym | Side | Qty | Fill $ | vs. Limit | Fee & Provenance`). `Orders → Baskets` renders a before/after weight, `turnover_pct`, and `Complete vs. Partial Fill` policy table instead of `<pre>` JSON. |
| **US-20** | Morgan | Run both **Saved-Plan Simulations** and **Walk-Forward Experiments** with Nautilus quality stats and fold tables (`L10`, `E-12`). | `Strategy Lab` (`#strategy`) places `[Load Saved Plans & Data]` below the heading, uses a 3-step left accordion (`360px`) with the required immutable preview gate, and renders `native_result` (`stats_pnls`, `stats_returns` when present), walk-forward `Folds` table, and `Closed Trades` table on the right. |
| **US-21** | Jordan | Use **Decision Journal** with focus-safe search, guarded revert, and 1-row Position Outcomes (`L8`). | `Journal` (`#journal`) merges Notes into `Decisions & Notes`, formats `Human proposal` plainly, keeps focus inside `#decision-search` while typing, guards `[Revert Unsaved Edits]` with a dirty count, and collapses 12-paragraph `Position Outcomes` groups into a 1-row summary table + right inspector. |
| **US-22** | Riley | Triage **Alerts** with unread badge, grouped restarts, calm freshness setup, and 3 quick rule templates (`L12`). | `Alerts` (`#alerts`) shows unread count on `Inbox`, collapses `25 service restarts` into 1 expandable row, frames unset quote-age limit as a calm setup prompt with `[Set in Trading Rules →]`, and provides 3 one-click rule templates (`Price Above $`, `Price Below $`, `Quote Stale > s`) above the collapsible 16-condition builder. |
| **US-23** | Morgan | See the entire 18-node **Workflows** diagram with `Fit All` and click any node to edit its prompt (`L5`). | `Workflows` (`#workflows`) adds `Fit All` (`0.25` zoom floor) as the default opening zoom, shows an inline `[Retry]` banner if rendering fails, loads a node's prompt + related files chip bar on node click, supports `Ctrl/Cmd+S`, closes popovers on `Escape`/outside-click, and replaces native `window.confirm()` with an in-app `<dialog>`. |
| **US-24** | Riley | Manage all 5 **Settings** categories with Basic vs. Advanced disclosure and an isolated Danger Zone (`L6`, `E-05`). | `Settings` (`#settings`) keeps `Account & Engine`, `Research & Models` (5 core fields upfront + 11 advanced in `<details>`), `Universe & Keys` (1,000-stock CSV import/export), `Trading Rules & Native Cache` (10 rules + native table capture), and `Diagnostics & Backup` (top health chips + bottom red-bordered Restore Danger Zone). |
| **US-25** | All | Use real WAI-ARIA `role="tablist"` tabs, keyboard shortcuts, and chart text alternatives across all 10 pages. | Every sub-tab bar uses `role="tablist"` + roving `tabindex` + Left/Right arrow keys and `40–44px` hit targets. All 4 SVG charts include hollow down-candles (`□`), solid up-candles (`■`), dashed/solid legends, and `<details>` data tables. |

---

## 5. Focus vs. Batch Contract & Safe Trader Hotkeys

### 5.1 One Focus Symbol (`selectedSymbol`) vs. One Batch Set (`selectedSymbols`)
- **`selectedSymbol` (Focus / Reading):** Changed by clicking any stock row, picking from Global Search (`Ctrl+K`), or clicking an alert/order row. Drives the linked Chart, Instrument Header, Research Inspector, and Order Ticket.
- **`selectedSymbols` (Checked Batch):** Changed **only** by row checkboxes, `X` / `Space` key, `[Select Filtered]`, `[Select Unfinished]`, or `[Clear]`. Persists across tab switches and never starts with all 24 universe symbols auto-checked.
- **Delete Selection (`researchDeleteSelection`):** Lives strictly inside the `[Manage / Delete]` mode on Research and never overwrites `selectedSymbols`.

### 5.2 Safe Trader Keyboard Shortcuts
| Key | Action | Safety Rule |
|---|---|---|
| `Ctrl+K` or `/` | Focus Global Symbol Search (`Enter` = inspect symbol; `Shift+Enter` = toggle in research batch). | Never starts a run or stages an order. |
| `J` / `K` or `↓` / `↑` | Move `selectedSymbol` down/up in the active stock table. | Never toggles checkboxes. |
| `X` or `Space` | Toggle batch checkbox (`selectedSymbols`) on the focused stock row. | Never changes `selectedSymbol`. |
| `Enter` (on row) | Open `Research → Summary` for the focused stock (or `Preview Impact` when inside Order Ticket). | **Never** triggers `Approve` or `Submit`. |
| `T` | Toggle the docked **Prepare Order** proposal drawer for `selectedSymbol`. | Stages a draft only; never approves or submits. |
| `←` / `→` | Move between tabs in any focused `role="tablist"`. | Standard WAI-ARIA tab pattern. |
| `Escape` | Close any open popover, `<dialog>`, or docked drawer and restore focus to the trigger. | Never discards saved data without confirmation. |
| `Alt+R` | Refresh workspace state (`readState()`). | Existing shortcut preserved. |

---

## 6. Page-by-Page Impeccable Wireframes & Exact Data Bindings

### 6.1 Global Shell (`index.html` — `36px` App Bar, `188px` Nav Rail, Zero Footer)

- **Data bindings:**
  - `state.connection.paper_verified`, `state.account.trading_blocked`, `state.account.account_blocked` (shows `[⚠ Account Blocked]` chip only if true).
  - `state.quotes_updated_at`, `state.clock.is_open` (`Market: Open` / `Market: Closed`).
  - `state.attention.observations.occurrences` (unread count badge on Alerts).
  - `state.trading_paused` (`Orders: Active` green pill vs. `Orders: Paused` amber pill — standardized everywhere, fixing `L6` & `L14`).
  - `state.commands.data.recovery_required` (1-line recovery banner shown under header only when `true`).
  - Left nav rail: **10 distinct SVG icons** (`iconPaths` in `app.js`, fixing `L7`), plus compact engine status dots (`Nautilus: state.nautilus.status`, `Stream: state.nautilus.trade_stream.stream_status`, `Laya: state.health.local_laya.status`).

```text
+---------------+------------------------------------------------------------------------------------------+
| TradingAgents | RESEARCH · PNIS (24)   [Find symbol (Ctrl+K): AMZN___]   IEX Quotes 16:00 ET [⟳ Refresh] |
| Paper Desk    |                                                 [🔔 Alerts: 1] [● Orders: Active · Pause]|
+---------------+------------------------------------------------------------------------------------------+
| [⊞] Dashboard | (Shown only if commands.data.recovery_required:                                          |
| [📈] Markets  |  ⚠ Order outcome recovery needed before new submissions · [Open Recovery on Orders ->])  |
| [🔬] Research*+------------------------------------------------------------------------------------------+
| [💼] Portfolio| WORKSPACE BAR (40px): [Role="tablist" Sub-Tabs] · Batch Scope Chip · Primary Action      |
| [🧾] Orders(1)+------------------------------------------------------------------------------------------+
| [🧪] Strat Lab|                                                                                          |
| [📓] Journal  |                           DATA CANVAS (84% – 91% OF HEIGHT)                              |
| [🔔] Alerts(1)|                   • Zero multi-paragraph prose banners above tables                      |
| [🕸] Workflows|                   • Single independent scrollbar per pane                                |
| [⚙] Settings  |                   • All tabs use role="tablist" + ArrowLeft/ArrowRight                   |
| ------------- |                                                                                          |
| ● Nautilus OK |                                                                                          |
| ● Stream: Lsn |                                                                                          |
| ● Laya CPU OK |                                                                                          |
| ● Mkt: Closed |                                                                                          |
+---------------+------------------------------------------------------------------------------------------+
```

---

### 6.2 Dashboard (`#overview`) — Morning Triage Strip, 5-KPI Bar & Linked 2×2 Grid

- **Data bindings:**
  - **Morning Triage Strip:** `dashboardAttentionSummary()` (`working orders`, `unread alerts`, `stale/missing quotes`, `held positions needing research today`). Hidden when all counts are 0.
  - **5-KPI Account Strip:** `state.account.equity`, `state.account.cash`, `state.account.buying_power`, `state.account.long_market_value`, plus summed `unrealized_intraday_pl` (`Today P/L` when positions exist) and `state.orders.length`.
  - **Watchlist (Top-Left):** Starts with `0 checked`. Columns: `SYM | LAST | CHG% | SPR (bps) | POS | WORKING | RSCH · AGE`. Sorted by `Held first` + `|change_pct|`.
  - **Chart (Top-Right):** `stockChart()` for `selectedSymbol` with hollow down-candles (`□`), solid up-candles (`■`), overlay legend, and `<details>` recent OHLCV bars table.
  - **Bottom Row (`Saved Research`, `Positions`, `Open Orders & Drafts`):** Compact height so buttons never clip (`L1`). When positions exist, renders `SYM | QTY | AVAIL | LAST | TODAY P/L | UPL%`.

```text
+----------------------------------------------------------------------------------------------------------+
| DASHBOARD · Observed Oct 28, 20:35 ET   [⚠ Triage: 1 unread alert · 21 unresearched today] [Select 21]   |
+----------------------------------------------------------------------------------------------------------+
| EQUITY $100,000.00 | CASH $100,000.00 | BUYING POWER $100,000.00 | LONG VALUE $0.00 | OPEN ORDERS 0      |
+--------------------------------------------------+-------------------------------------------------------+
| WATCHLIST (24)  [☑ Held first] [Sort: |Chg%| v]  | AMZN · $252.51 (+1.14%) · Bid 252.40×300 Ask 252.60×100|
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
| [HOLD · 1d] Close@10-28 249.70| No open positions in Alpaca.     | Working broker orders: 0              |
| Now 252.51 (+1.1% since rsch) | Cash account, long only.         | Unsent drafts: SGOV BUY 1 MKT (rev 2) |
| [Read Report] [Prepare Order] | [Browse Markets]                 | [Open SGOV in Ticket]                 |
+-------------------------------+----------------------------------+---------------------------------------+
```

---

### 6.3 Markets (`#markets`) — Persistent Instrument Header, Scan Table, Chart, Filings & Docked Ticket

- **Data bindings:**
  - **Top Mode Tablist (`role="tablist"`):** `[*Universe & Watchlists (24)*]`, `[Yahoo Screener]` (`/api/discovery`), `[Saved Scans]` (`market_history` scan definitions, runs, and matches).
  - **Persistent Instrument Header Strip:** Joins `state.quotes[sym]`, `state.nautilus.market_data[sym].quote` (`bid_price`, `bid_size`, `ask_price`, `ask_size`, spread bps), `session_eligibility` badges (`Fractional ✓`, `Ext-Hrs ✓`, `Overnight Halted ⚠`), `positions()`, working `orders()`, draft `proposals`, and `state.research[sym]` (`rating`, `trade_date` age & drift). Hides duplicate company subtitle when `companyName(sym) === sym` (`L13`).
  - **Right-Pane Sub-Tabs:** `[*Chart*]`, `[Research]`, `[Evidence & Filings]` (binds to `GET /api/stock-evidence?symbol=SYM`: SEC EDGAR XBRL statements, SIC, Alpaca Corporate Actions, Alpaca News — `E-07`), `[Options]` (disabled with tooltip `"No option contracts loaded for this stock"` when empty).
  - **1-Line History Backfill Bar:** Collapses the 10-field history form into `History: 1,255 daily bars cached (Oct 28) · [Get 252 Daily Bars] [More: Interval / Dates / Adjustment ▾]` (`POST /api/market-history`).
  - **Docked `[Prepare Order (T)]` Drawer:** Opens alongside the chart so the trader can click `[Bid]`, `[Ask]`, or `[Last]` to seed `Limit $` (or use 2-step `chart_copy` for historical bars) without closing the chart.

```text
+----------------------------------------------------------------------------------------------------------+
| MARKETS   [*Universe & Watchlists (24)*] [Yahoo Screener] [Saved Scans]   0 checked · [Run Research (AMZN)]|
+----------------------------------------+-----------------------------------------------------------------+
| List: [All Universe: PNIS (24) v] [+New]| AMZN $252.51 (+1.14%) [Bid 252.40×300] [Ask 252.60×100] (8bp)   |
| [Search...] [View: All v] [Sortv] [Ed] | [Fractional ✓] · YOU: FLAT · WRK: — · RSCH: [HOLD · 1d (+1.1%)] |
+----------------------------------------+-----------------------------------------------------------------+
| SYM    LAST    CHG%   SPR  POS  RSCH   | Tabs: [*Chart*] [Research] [Evidence & Filings] [Options] [Order]|
| AMZN*  252.51  +1.14% 8bp  —    Hold·1d| Source: [*Live IEX Cache* | Research Date]  [*1Day*] [1Hr] [15m]|
| INTC    22.40  -0.85% 5bp  —    Undw·1d| Drawers: [Studies & Formulas] [Drawings] [Comparison] [Alert+$] |
| TER    108.12  -1.40% 9bp  —    Sell·1d| +-------------------------------------------------------------+ |
| AAPL   231.10  +0.42% 4bp  —    Cancel | | History: 1,255 daily bars cached (Oct 28) · [252d] [More ▾] | |
| GOOGL  182.30  -0.12% 6bp  —    Cancel | +-------------------------------------------------------------+ |
| META   590.40  +1.85% 7bp  —    Cancel | |                                                             | |
| MSFT   428.15  +0.33% 5bp  —    Cancel | |             FULL-HEIGHT LIGHTWEIGHT CHART                   | |
| NVDA   141.80  +2.10% 6bp  —    Cancel | |     • Clicking [Order (T)] docks the Proposal Drawer        | |
| ... sticky-header scroll (25/50/100    | |       right beside this chart                               | |
|     batch scope in [Ed] menu)          | |     • Clicking [Evidence & Filings] shows SEC EDGAR XBRL    | |
|                                        | |       Balance Sheet / Income / Cash Flow & Corp Actions     | |
|                                        | +-------------------------------------------------------------+ |
|                                        | [▸ Selected bar readout & OHLCV table (a11y / keyboard)]        |
+----------------------------------------+-----------------------------------------------------------------+
```

---

### 6.4 Research (`#research`) — Self-Contained Picker, Confirm Popover, 7-State Queue, & Trader Summary

- **Data bindings & fixes (`U1`, `U2`, `L3`, `L4`, `E-01`, `E-07`, `E-08`, `E-15`):**
  1. **Inline Stock Picker & Confirm Popover:** Check stocks in the left rail or click `[Unfinished (21)]` / `[Needs Today]`, then click `[▶ Run Research (N)...]`. Opens the compact confirm popover showing symbol list, active workflow (`Default`), deep/fast models, ETA (`DeskLists.estimate`), optional **`Analysis Date`** (`analysis_date`) and **`[ ] Exclude FRED macro series`** (`exclude_fred`), and `"Places no orders"`.
  2. **7-State Progress Strip:** Displays `completed`, `incomplete`, `interrupted`, `failed`, `cancelled`, `running`, and `queued` counts. Cancelled is slate, never green.
  3. **Trader Verdict & Drift Header:** Pairs `rating` (shown **only** if `status === 'completed'` and `final_trade_decision` is saved) with `trade_date` age (`1d old`), price drift from saved `trade_date` close to live `quotes[sym].price`, live `Bid×Size / Ask×Size`, `positions()` / `orders()` / `proposals` exposure chip, `review_required`, and explicit `completion_gaps` warning.
  4. **PM Decision & Trader Plan First:** Places `final_trade_decision` and `trader_investment_plan` excerpts above the fold, followed by `investment_debate_state` (Bull/Bear) and `risk_debate_state` (Aggressive/Neutral/Conservative), then the 4 Analyst Cards (including `[Screen Saved Posts Locally]` for `POST /api/runs/local-laya`).
  5. **5 Evidence Tabs:** `[*Summary*]`, `[Reports (7)]`, `[Debate & Risk]`, `[Sources & Filings]` (links with domain + date + Vendor/Maenifold provenance chips + `/api/stock-evidence` SEC XBRL & corporate actions), and `[Activity]` (filtered to `selectedSymbol` by default with `[Whole run]` and `[Errors / 429s only]` toggles).

```text
+----------------------------------------------------------------------------------------------------------+
| RESEARCH  Batch: 2 checked [Unfinished (21)] [Needs Today] [Clear]  [▶ Run Research (2) · places no order]|
+----------------------------------------------------------------------------------------------------------+
| Queue: [===3 Completed===|-----------21 Cancelled-----------] 3 completed · 21 cancelled · 0 running     |
+-------------------------------+--------------------------------------------------------------------------+
| STOCKS (24)  [Filter: All v]  | AMZN  Last $252.51 (+1.14%)  Bid 252.40×300 Ask 252.60×100  [Prepare (T)]|
| [Search...]          [Manage] | YOU: FLAT · WORKING: — · DRAFT: — · Review required: No     [Export JSON]|
+-------------------------------+--------------------------------------------------------------------------+
| [ ] SYM   RSCH·AGE  DRIFT POS | Tabs: [*Summary*] [Reports (7)] [Debate & Risk] [Sources & SEC] [Activity]|
| [x] AMZN* Hold·1d   +1.1% —   | +----------------------------------------------------------------------+ |
| [x] INTC  Undw·1d   -0.4% —   | | [HOLD] · 1d old (2026-10-28) · Saved close $249.70 → Now +1.1% (IEX) | |
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
|                               | ANALYSTS: [Market ✓] [Fundamentals ✓] [News ⚠ 429] [Social: 12↑ 3↓ Laya] |
|                               | Footer: Disposition [Needs review v] Note [______________] [Save] [Tech▸]|
+-------------------------------+--------------------------------------------------------------------------+
```

**Research Confirm Popover (opened by `[▶ Run Research (2)...]`):**
```text
+--------------------------------------------------------------------------------+
| CONFIRM RESEARCH RUN (2 stocks: AMZN, INTC)                                    |
| Workflow: Default · Models: Fast (gpt-6-luna) / Deep (gpt-6-sol) · Est: ~12m   |
| Analysis Date: [2026-10-28 (Today) v]   [ ] Exclude FRED macro series          |
| Advisory only: replaces latest saved reports for these stocks; places no order.|
| [ ] Keep batch selection checked after launch       [Cancel]  [Start Research] |
+--------------------------------------------------------------------------------+
```

---

### 6.5 Portfolio (`#portfolio`) — Populated Holdings Risk Table (`Today P/L` & `Avail Qty`), Proposed Model, & Performance

- **Data bindings (`L2`, `L11`, `E-04`, `E-13`):**
  - **Positions Tab:** Renders `symbol`, `qty`, `qty_available` (`AVAIL`), `avg_entry_price`, `current_price`, `unrealized_intraday_pl` / `unrealized_intraday_plpc` (`TODAY P/L`), `market_value`, `unrealized_pl` / `unrealized_plpc` (`TOTAL UPL`), derived `weight %`, working orders in symbol, and `state.research[sym]` (`rating · age`). When `positions.length === 0`, hides `<thead>` and renders a 2-line empty card.
  - **Proposed Model Portfolio Tab:** Strictly the session-only joint deep-model synthesis (`POST /api/portfolio-model`), showing `MODEL REF (DATED)` alongside `LAST NOW (IEX)`, `DRIFT %`, and `YOUR POS`.
  - **Performance Tab:** Plots `time_weighted`, `benchmark_comparison`, and `drawdown` shading with external flow markers and `[Export CSV ▾]` (`holdings`, `activity`, `performance` via `POST /api/reporting`). When `<2` points exist, caps the empty card to `120px` with `[Collect Account History in Journal →]`.

```text
+----------------------------------------------------------------------------------------------------------+
| PORTFOLIO   Tabs: [*Positions*]  [Proposed Model Portfolio]  [Performance]   [Export CSV ▾] [Refresh]    |
+----------------------------------------------------------------------------------------------------------+
| EQUITY $100,000 | CASH $90,385 | BUYING POWER $90,385 | LONG VAL $9,615 | TODAY +$112 | TOTAL UPL +$754 ✓|
+----------------------------------------------------------------------------------------------------------+
| (TAB 1: POSITIONS — Populated Holdings Risk Table; when 0 positions, hides header & shows 2-line card:)  |
| SYM   QTY  AVAIL  AVG COST  LAST    TODAY P/L       MKT VAL   TOTAL UPL ($, %)   WT%  WORKING   RSCH·AGE |
| NVDA  50   30     $128.40   $141.80 +$145 (+2.10%)  $7,090.00 +$670.00 (+10.4%)  7.1% SELL 20   Buy·3d ⚠ |
| AMZN  10   10     $244.10   $252.51 +$28  (+1.14%)  $2,525.10 +$84.10  (+3.4%)   2.5% —         Hold·1d  |
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
| (TAB 3: PERFORMANCE — Benchmark overlay, drawdown shading & 120px capped empty state when <2 points:)   |
| +------------------------------------------------------------------------------------------------------+ |
| | TWR: — · Modified Dietz: — · Benchmark Excess (SPY): — · Max Drawdown: —          [Export CSV ▾]     | |
| | [📈 24px] Needs at least 2 saved account-history observations. [Collect Account History in Journal->]| |
| +------------------------------------------------------------------------------------------------------+ |
```

---

### 6.6 Orders (`#orders`) — Full-Context Ticket, 10-Rule Policy Table, Blotter, Fills & Baskets

- **Data bindings (`E-02`, `E-03`, `E-04`, `E-06`, `E-09`, `E-10`, `E-11`):**
  - **Stage 1 (Prepare Draft Proposal):** Shows live `IEX Last`, `[Bid×Size]`, `[Ask×Size]`, `Spread bps`, `Quote Age`, `Session Eligibility` (`Fractional ✓`, `Ext-Hrs ✓`), `Current Position (qty, qty_available)`, and `Cash / Buying Power / Equity`. Clicking `Bid`, `Ask`, or `Last` seeds `Limit $`. Shows live sizing math (`$ notional`, `% of equity`, `% of cash`, `weight after`) and keeps `Stop $` / `Target $` visible.
  - **Stage 2 (10-Rule Policy Check & Single-Use Approval):** Renders all 10 `checks[]` rows from `state.investor.current_checks[proposal_id]` (`cash_reserve`, `max_position`, `gross_exposure`, `loss_limit`, `scenario_loss`, `sector`, `correlation`, `spread`, `quote_size`, `quote_age`) with observed value vs. limit (failing rules first!), plus bracket `stop_loss_estimate_before_fees`.
  - **Stage 3 (Separate Broker Submission & Recovery):** Checks for duplicate working orders in the same symbol, requires a 2-step inline confirmation showing exact terms, disables in-flight buttons, shows plain transport chips (`Not sent`, `Sent`, `Outcome unknown — Refresh first`), and exposes `[Resolve Never Dispatched]` when `c.state === 'outcome_unknown'`.
  - **Sub-Tabs on Right Pane:**
    - `[*Working & Drafts Blotter*]`: Working orders (with `Bracket / OTO / OCO` exit chips and trailing `HWM / Moving Stop $`) + Unsent Drafts (filtered/sorted with `selectedSymbol` first).
    - `[Fills & Fee Provenance]`: Tabular fills (`Time | Sym | Side | Qty | Fill $ | vs. Limit | Fee & Provenance` from `state.fills` & `fee_provenance`).
    - `[Human Baskets]`: Before/after weight, `turnover_pct`, `residual_cash`, and `Complete vs. Partial Fill` policy scenario table (`baskets.py`).
    - `[Option Instructions]`: Exercise / Do-Not-Exercise (`option_instruction`) workflow when option contracts are present.

```text
+----------------------------------------------------------------------------------------------------------+
| ORDERS   [*Ticket & Blotter*] [Fills & Fees (0)] [Human Baskets (0)] [Option Instr.]  [Orders: Active ▾] |
+----------------------------------------------------------------------------------------------------------+
| Readiness: Ready · Cash $100,000.00 · Buying Power $100,000.00 (Cash acct, long only) · Policy rev 1     |
+-------------------------------------------------+--------------------------------------------------------+
| STAGE 1: PREPARE ORDER PROPOSAL (45% width)     | STAGE 2 & 3: 10-RULE CHECK, SUBMIT & BLOTTER (55%)     |
+-------------------------------------------------+--------------------------------------------------------+
| Symbol: [AMZN  ]  Last [252.51]  [Bid 252.40×300] [Ask 252.60×100] (8bp) · IEX 42s ✓ · [Fractional ✓]    |
| YOU: FLAT (0 sh, 0 avail) · WORKING IN AMZN: none · RSCH: [HOLD · 1d (+1.1% since close)]                |
| ----------------------------------------------- | SELECTED DRAFT: AMZN · Rev #3 · Status: [Not Sent]     |
| Asset: [*US Equity*] [US Option / MLeg]         | Terms: BUY 20 AMZN · LMT $252.60 · DAY · Regular       |
| Side:  [(*) Buy  ( ) Sell]   Type: [Limit    v] | ------------------------------------------------------ |
| Qty:   [20      ] sh  Limit $: [252.60] (←Ask)  | STAGE 2: 10-RULE POLICY CHECK & EXACT APPROVAL         |
| TIF:   [DAY     v]    Session: [Regular      v] | RULE               VALUE          LIMIT       STATUS   |
| Sizing: ≈ $5,052.00 · 5.1% Equity · 5.1% Cash   | Max position wt    5.1%           20.0%       Pass ✓   |
| Exits:  Stop $ [245.00]  Target $ [268.00]      | Bid/Ask spread     8 bps          50 bps      Pass ✓   |
|         Est. stop loss before fees: -$152.00    | Quote size / age   100 sh / 42s   ≥1 / ≤60s   Pass ✓   |
| [▸ Bracket / OTO / OCO & Replace working order] | [▸ Show all 10 passing rules]                          |
|                                                 | [1. Check Order]   [2. Approve Exact Revision #3]      |
| [Preview Impact (Enter)]  [Save Draft Revision] | ------------------------------------------------------ |
| (Draft ≠ Approved ≠ Submitted)                  | STAGE 3: SEPARATE BROKER SUBMISSION                    |
|                                                 | Duplicate Check: 0 working orders in AMZN              |
|                                                 | [3. Submit Approved Order to Alpaca Paper]             |
|                                                 | ------------------------------------------------------ |
|                                                 | WORKING ORDERS (0) & UNSENT DRAFTS (1):                |
|                                                 | SYM   SIDE  QTY  TYPE       EXIT/TRAIL  STATUS  ACTION |
|                                                 | SGOV  BUY   1    MKT · DAY  —           Draft   [Load] |
|                                                 | [▸ Technical record (Terms SHA-256 & audit trail)]     |
+-------------------------------------------------+--------------------------------------------------------+
```

---

### 6.7 Strategy Lab (`#strategy`) — Saved-Plan Simulations, Walk-Forward Experiments & Nautilus Analyzer Stats

- **Data bindings (`L10`, `E-12`):**
  - Top Engine Switcher: `[*Saved-Plan Simulations*]` and `[Walk-Forward Experiments]`.
  - Places `[Load Saved Plans & Data]` below the Setup heading (`L10`).
  - Left Rail (`360px`): 3-step accordion with a 2-line visible scope notice and the required `[Save Immutable Preview]` gate before `[▶ Run]`.
  - Right Canvas: Equity curve + benchmark overlay + `<details>` observations table, **Headline Metrics** (`Net Return %`, `Modeled P&L`, `Max Drawdown %`, `Closed Trades`), **Nautilus Portfolio Analyzer Stats** (`native_result.stats_pnls` / `stats_returns`: Win Rate, Profit Factor, Expectancy, Sharpe when present in `/api/evaluations`), **Walk-Forward Folds Table** (`Fold | Period | In-Sample | OOS Return | OOS Drawdown`), and **Simulated Positions / Fills Table** (`reports.positions` / `reports.fills`).

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
|                                        | HEADLINE & NAUTILUS ANALYZER METRICS (`native_result`):         |
| ▾ 3. IMMUTABLE PREVIEW & RUN           | Net Return %  Modeled P&L  Max Drawdown %  Closed Trades        |
|   [x] Acknowledge simulation limits    |  0.00%         $0.00        0.00%           0 (DAY expired)     |
|   [Save Immutable Preview]  [▶ Run]    | [▸ Walk-Forward Folds Table & Native Simulated Orders/Fills]    |
|                                        | [▸ Technical record (Immutable spec SHA-256 & source pins)]     |
+----------------------------------------+-----------------------------------------------------------------+
```

---

### 6.8 Journal (`#journal`) — Master-Detail Decision Ledger, 1-Row Position Outcomes, & Account History

- **Data bindings (`L8`):**
  - Consolidates tabs into `[*Decisions & Notes*]`, `[Position Outcomes]`, and `[Account History]`.
  - Formats `human_proposal` as `Human proposal` (`L8`), keeps focus stable inside `#decision-search` during typing, and guards `[Revert Unsaved Edits]` (disabled at `0`; prompts `"Discard N unsaved notes?"` when dirty).
  - Separates AI Research ratings (`Hold`, `Underweight`, `Sell`) from order draft review states (`Deferred` / `Not approved`), and shows the live position (`Current holding: FLAT`) inside the inspector.
  - Collapses the 12-paragraph `Position Outcomes` groups into a **1-row summary table** (`Sym | Lifecycle State | Qty | Realized P/L | Unrealized P/L | Coverage | [Inspect]`) with a direct `[Capture Native Position Table in Settings →]` link when empty.

```text
+----------------------------------------------------------------------------------------------------------+
| DECISION JOURNAL   Tabs: [*Decisions & Notes (4)*] [Position Outcomes (0)] [Account History]             |
+----------------------------------------------------+-----------------------------------------------------+
| [Find symbol or text...] [Filter: All v] [Export]  | DECISION INSPECTOR: SGOV · Human Order Draft        |
+----------------------------------------------------+-----------------------------------------------------+
| DATE     SYM   KIND          CALL / TERMS  STATUS  | Tabs: [*Rationale & Note*] [Linked Orders & Outcome]|
| Oct 28 * SGOV  Order draft   BUY 1 MKT     Deferred| --------------------------------------------------- |
| Oct 28   AMZN  AI research   [Hold]        Reviewed| Saved: Oct 28, 2026 · Current holding: FLAT (0 sh)  |
| Oct 28   INTC  AI research   [Underwt]     Unrevwd | Proposed Action: BUY 1 share SGOV (Market · DAY)    |
| Oct 28   TER   AI research   [Sell]        Unrevwd |                                                     |
|                                                    | FOLLOW-UP NOTE & DISPOSITION:                       |
| [Revert Unsaved Edits (0)] (Disabled at 0;         | Disposition: [Deferred         v]                   |
|  prompts "Discard N unsaved notes?" when dirty)    | Note: [Waiting for next week's FOMC meeting...    ] |
|                                                    | [Save Note]  [Open Linked Research]  [Prepare (T)]  |
|                                                    | [▸ Technical record (Decision ID, run ID, SHA-256)] |
+----------------------------------------------------+-----------------------------------------------------+
```

---

### 6.9 Alerts (`#alerts`) — Triage Inbox, Deduped Occurrences, & 1-Click Rule Templates

- **Data bindings (`L12`):**
  - Tabs: `[*Inbox (1 unread)*]`, `[Alert Rules (0)]`, `[Browser Delivery]`.
  - Collapses repetitive occurrences (`25 service restarts`) into a single expandable summary row (`• [GROUPED] Service restart recorded (25 events) · Latest: Oct 28, 20:14 ET · [▸ Expand 25 logs]`).
  - Turns `"no price-age limit configured"` into a calm setup row with `[Set Quote-Age Limit in Trading Rules →]` and notes when the regular market is closed.
  - Provides **3 Quick Rule Templates** (`[Price Above $]`, `[Price Below $]`, `[Quote Stale > s]`) above the collapsible 16-condition advanced rule builder, and restores focus to the trigger row when closing evidence.

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
|   Latest: Oct 28, 20:14 ET · [▸ Expand 25 logs]    | QUICK CREATE RULE (Browser notifications when open):|
|                                                    | Templates: [Price Above $] [Price Below $] [Stale]  |
|                                                    | [▸ Advanced 16-condition / indicator / drawing rule]|
+----------------------------------------------------+-----------------------------------------------------+
```

---

### 6.10 Workflows (`#workflows`) — True `Fit All` Diagram & Node-Linked Prompt Studio

- **Data bindings (`L5`):**
  - Adds **`Fit All`** (`Math.min((clientWidth - 32) / naturalWidth, (clientHeight - 32) / naturalHeight)` with a `0.25` zoom floor) as the default opening zoom so the entire `1,755px`-tall 18-node flow fits in the left pane without clipping (`L5`). Shows an inline `[Retry Diagram]` banner if Mermaid rendering fails.
  - Clicking any node in the diagram selects its primary prompt and displays its related files (`Primary prompt`, `Shared context & tools`, `Output schema`) as a 1-line chip bar above the editor.
  - Binds `Ctrl/Cmd+S` to save, closes `[About]` / `[Details]` popovers on `Escape` and outside click, and replaces native `window.confirm()` on unsaved changes with an in-app `<dialog>`.

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

- **Data bindings (`L6`, `E-05`):**
  - Preserves all **5 real categories**: `[Account & Engine]`, `[*Research & Models*]`, `[Universe & Keys]`, `[Trading Rules & Native Cache]`, `[Diagnostics & Backup]`.
  - **Account & Engine:** Shows observed Alpaca Paper/Live account ID once, read-only Account Status Flags (`status`, `trading_blocked`, `account_blocked`, `pattern_day_trader`, `daytrade_count` — `E-05`), `Start / Stop Nautilus`, `Native Execution Profile`, and OS Credential Manager keys.
  - **Research & Models:** Shows 5 core model fields upfront + `[▸ Advanced Token Budgets, Concurrency, Retries & Local Laya Router (11 fields)]` collapsed.
  - **Universe & Keys:** 1,000-stock Universe editor, `Use FANGMAN`, CSV Import/Export with preview, and vendor API keys.
  - **Trading Rules & Native Cache:** 10 Investor Policy Rules + `Capture Native Cache Table` (`orders`, `order_fills`, `fills`, `positions`, `account`).
  - **Diagnostics & Backup:** Top health chips (`Engine`, `Reconciliation`, `SQLite`, `Trade Stream`) + dynamic `location.origin` launch note + `[Export Workspace Backup]` + bottom red-bordered **Danger Zone: Restore Workspace from Backup**.

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
| • [Account & Engine]: Paper/Live ID (once), Account Status Flags, Start/Stop Nautilus, Alpaca Vault Keys.|
| • [Universe & Keys]:  Universe Name, 1,000-stock Textarea, FANGMAN Preset, CSV Import/Export, Data Keys. |
| • [Trading Rules]:    10 Investor Policy Rules + Capture Native Cache Table (for Journal Outcomes).      |
| • [Diagnostics]:      Top: [● Engine: Connected] [● Sync: Reconciled] [● Stream: Listening] + Origin URL.|
|                       Bottom: [Export Backup] + Red-Bordered DANGER ZONE: [Restore Workspace Backup].    |
+----------------------------------------------------------------------------------------------------------+
```

---

## 7. Complete Traceability Matrix (Critique + Trader Audits + Existing Backend Gems)

| Issue / Capability | Source | How This Canonical Blueprint Solves It (Frontend Only) |
|---|---|---|
| **U1:** Pick stocks & run on Research | User | Inline stock picker + batch selectors + `[▶ Run Research]` in `Research` toolbar (`6.4`). |
| **U2:** Screen stuck on old stock after launch | User | Smart launch auto-focuses first batch symbol and updates 7-state progress strip (`6.4`). |
| **L1:** Dashboard Positions button clipped | Live Critique | Compact 2-line empty state + flexible bottom row height (`6.2`). |
| **L2:** Giant 1660×817px empty Performance SVG | Live Critique | Capped `120px` empty state with `24px` icon + `[Collect Account History in Journal →]` (`6.5`). |
| **L3:** Red `Sell` badge with `"No final recommendation"` | Live Critique | Rating badge renders **only** when `status === 'completed'` and `final_trade_decision` exists (`6.4`). |
| **L4:** Stuck `"Loading research reports..."` | Live Critique | Cleared immediately when fetch settles or stock is cancelled/unresearched (`6.4`). |
| **L5:** Workflows diagram stuck / clipped | Live Critique | Default `Fit All` (`0.25` zoom floor) + inline `[Retry Diagram]` error state (`6.10`). |
| **L6 & L14:** Inconsistent Pause/Unblocked buttons | Live Critique | Unified `Orders: Active` / `Orders: Paused` toggle across Shell, Orders, and Settings (`6.1`, `6.6`). |
| **L7:** Repeated sidebar icons | Live Critique | 10 distinct SVG line icons in `iconPaths` (`6.1`). |
| **L8:** Raw `human_proposal`, `needs_review`, `STOP_LIMIT` | Live Critique | Plain English labels (`Human proposal`, `Needs review`, `Stop limit`); raw JSON/IDs in `Technical record`. |
| **L9:** Raw run UUID + nested scrollbars on Research | Live Critique | Run UUID moved to `Technical record`; single scrollbar on left stock rail (`6.4`). |
| **L10:** Strategy Lab button above its own heading | Live Critique | `[Load Saved Plans & Data]` placed in the workspace toolbar / below heading (`6.7`). |
| **L11:** Empty table headers on Portfolio Positions | Live Critique | `<thead>` hidden when `positions.length === 0` (`6.5`). |
| **L12:** 3 equal paragraphs + 25 restart JSON blocks in Alerts | Live Critique | 1-line status + grouped `25 service restarts` row + 3 quick rule templates (`6.9`). |
| **L13:** `AMZN / AMZN` duplicate subtitle on Markets | Live Critique | Subtitle hidden when `companyName(sym) === sym` (`6.3`). |
| **T1–T6:** Price drift, exposure strip, PM first, docked ticket | Trader Audit | Verdict strip pairs rating with `trade_date` close drift, `Bid×Size/Ask×Size`, `POS/WORKING/DRAFT`, PM decision above fold, and docked `Prepare Order (T)` drawer (`6.2–6.6`). |
| **E-01 to E-15:** 15 hidden existing backend features | Backend Audit | Wired into `6.1–6.11` with zero Python backend changes (see Table 1.1). |

---

## 8. Frontend Implementation Workstreams (Zero Backend Changes)

When approved to build, implementation runs across 4 frontend-only workstreams in `tradingagents/web/static/`:

1. **Workstream 1 — Global Shell, Chrome Diet, Shared `renderTablist()` & Hotkeys (`index.html`, `app.css`, `app.js` shell):**
   - `36px` top bar, delete `.workspace-footer`, remove multi-sentence `pageHeader` descriptions, add 10 distinct sidebar SVG icons, add `Stream` status dot & account-blocked warning chip, standardize `Orders: Active / Paused`, implement WAI-ARIA `renderTablist()` with Left/Right arrow keys, and bind safe hotkeys (`J/K`, `X`, `T`, `Escape`).
2. **Workstream 2 — Research & Workflows (`app.js`, `report-format.js`, `workflows.js`, `ui-research-journal.css`, `ui-workflows.css`):**
   - Research inline stock picker + confirm popover (with existing `analysis_date` and `exclude_fred` parameters), 7-state progress strip, no fake `Sell` badge or stuck `Loading...`, Trader Verdict + Price Drift + Exposure header, PM Decision & Trader Plan above the fold, `[Screen Saved Posts Locally]` Laya view, `[Sources & SEC Filings]` tab (`/api/stock-evidence` + vendor/Maenifold chips), `[Manage]` delete toggle, and Workflows `Fit All` (`0.25` floor) + node-click prompt chips + in-app `<dialog>`.
3. **Workstream 3 — Dashboard, Markets & Portfolio (`app.js`, `market-chart.js`, `lists.js`, `ui-markets.css`, `ui-instrument.css`):**
   - Dashboard morning triage strip, `0 checked` default, trader scan columns (`SYM | LAST | CHG% | BID×ASK | POS | WORKING | RSCH·AGE`), hollow down-candles + legends + `<details>` bar tables, Markets persistent Instrument Header + 1-line history backfill + `[Evidence & Filings]` tab + docked `Prepare Order (T)` drawer, Portfolio populated Positions table (`Today P/L`, `Avail Qty`), Proposed Model live drift columns, and Performance benchmark/drawdown chart + capped `120px` empty state.
4. **Workstream 4 — Orders, Strategy Lab, Journal, Alerts & Settings (`app.js`, `command-controls.js`, `nautilus.js`, `ui-orders.css`):**
   - Direct 2-column DOM rendering (removing `layoutOrders`/`layoutMarkets`), Stage 1 full-context ticket (`Bid×Size/Ask×Size`, click-to-seed `Limit $`, `% of equity` sizing math, visible `Stop/Target`), Stage 2 10-Rule Policy Table + bracket stop-loss dollar risk, Stage 3 duplicate-order check + inline confirm/receipt + transport chips, tabular `Fills` (`fee_provenance`) & `Baskets` (`turnover_pct`, partial-fill table), Strategy Lab 3-step accordion + `native_result` stats/fold/trade tables, Journal focus-safe search + 1-row outcomes, Alerts grouped restarts + 3 quick rule templates, and Settings 5-tab progressive disclosure + isolated Restore Danger Zone.

---

## 9. Professional Stock Trader Sign-Off Record

*(Pending final verification pass on this consolidated v4 specification by fresh Claude Sonnet 5.5 and Grok 4.7 pro-trader subagents.)*
