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
| **E-01** | `POST /api/runs` (`server.py`, `service.py` `start_run`) | Accepts `analysis_date` (ISO New York date for point-in-time historical research with SEC EDGAR filing-date and FRED vintage pinning; uses current account context) and `exclude_fred: bool`. | **Research Confirm Popover (`Section 6.4`)**: Optional `Analysis Date` input (omitted for today's live run) and `[ ] Exclude FRED macro series` checkbox. |
| **E-02** | `state.nautilus.market_data[sym].quote`, `.trade` & `.previous_close` | Provides `bid_price`, `ask_price`, `bid_size`, `ask_size`, `trade.price`, `trade.size`, and sibling `previous_close` (nullable when unavailable). Two policy rules (`max_spread_bps`, `min_quote_size`) check these numbers. | **Instrument Header & Order Ticket (`Sections 6.2, 6.3, 6.4, 6.6`)**: Shows `Bid $252.40 (300) x Ask $252.60 (100) · Spread 8 bps` (labeled `IEX displayed size / derived spread`; shows `Unavailable` when `quote` is null). |
| **E-03** | `state.nautilus.market_data[sym].session_eligibility` | Provides `fractionable`, `fractional_eh_enabled`, `overnight_tradable`, `overnight_halted`, `observed_at`, and `source` (`null` = unknown, never rendered as `✗`). | **Instrument Header & Order Ticket (`Sections 6.3, 6.4, 6.6`)**: Compact capability badges (`Fractional ✓`, `Fractional Ext-Hrs ✓`, `Overnight Tradable ✓`, `Overnight Halted ⚠`). |
| **E-04** | `state.positions[]` & `state.investor.instruments[sym]` | Raw Alpaca position rows include string decimals `unrealized_intraday_pl`, `unrealized_intraday_plpc` (fraction, scale `× 100`), `change_today` (fraction, scale `× 100`), `lastday_price`, `cost_basis`, and `qty_available`, plus `instruments[sym].available_exit_quantity` (`exit_availability_known`). | **Portfolio Positions (`6.5`), Dashboard (`6.2`), & Order Ticket (`6.6`)**: Adds `Today P/L ($, %)` and `Avail to Sell` columns/readouts (rendering `—` when absent). |
| **E-05** | `state.account` & `state.nautilus.account_configuration` (`nautilus_worker.py:929`) | Whitelisted account fields: `id`, `status`, `currency`, `cash`, `equity`, `trading_blocked`, `account_blocked`, `trade_suspended_by_user`, `buying_power`, `long_market_value`, `multiplier`, `shorting_enabled`, `initial_margin`, `maintenance_margin`, `options_*`, `non_marginable_buying_power`, plus `disable_overnight_trading`. | **Global Shell (`6.1`) & Settings → Account (`6.11`)**: Shows a warning chip in the Shell if `trading_blocked`, `account_blocked`, or `trade_suspended_by_user` is true; shows a read-only Account Flags table in Settings. |
| **E-06** | `state.investor.current_checks[id]` & `proposal.risk_evaluation` (`policy_evaluation.py`, `investor.py`) | Evaluates the 10 `state.investor.rule_labels` keys (`cash_reserve_pct`, `max_position_pct`, `max_gross_exposure_pct`, `loss_limit_pct`, `scenario_loss_pct`, `max_sector_pct`, `max_correlation_pct`, `max_spread_bps`, `min_quote_size`, `session_freshness`) with `details` (`equity_pct`/`limit_pct`, `spread_bps`, `quoted_quantity`, `loss_pct`) and held-bracket amendment `conditional_group.stop_loss_estimate_before_fees`. | **Orders Stage 2 (`Section 6.6`)**: Filters `checks[]` to the 10 rule keys (failing rules first, observed value from `details` vs. limit from `policy.rules[key].value`, and grey `Not configured` when `state` is `unset`/`disabled`). |
| **E-07** | `GET /api/stock-evidence?symbol=SYM` & `POST /api/market-history` (`action: "evidence"`) | Reads saved `observations[scope].records[]` and triggers collection via `POST /api/market-history` (`{action: "evidence", symbols, provider, scopes, start, end, earnings_horizon}`) for **SEC EDGAR** (`reported_fact` per tag for `balance_sheet`/`income_statement`/`cashflow`, plus `industry` SIC), **Alpaca** (`news`, `corporate_actions`), and **Alpha Vantage** (`fundamentals`, `classification`, `earnings`). | **Markets (`6.3`) & Research (`6.4`)**: `[Evidence & Filings]` sub-tab includes the compact collection request bar (`Provider`, `Scopes`, `Dates`, `[Fetch Evidence]`) and renders saved SEC facts, corporate actions, and news in tables. |
| **E-08** | `POST /api/runs/local-laya` & `GET /api/runs/{id}/results/{sym}` | Screens the first 5 saved StockTwits posts locally (`{run_id, symbol, request_id}` → `result.local_laya_batch`) and stores `social_sentiment.sources.*.counts` plus per-post `post.stance`, `status`, and source `stop_reason`. | **Research (`Section 6.4`)**: Places `[Screen Saved Posts Locally]` and the Laya stance counts (`counts`) on the Sentiment card and `Reports → Social` view. |
| **E-09** | `state.orders[]` & `state.commands` (`command-controls.js`, `linked_orders.py`, `execution_lifecycle.py`) | Carries linked exit metadata (`group_class`: `bracket`/`oto`/`oco`, `group_role`, `exit_active`, `exit_reserved`, `replaced_by`), trailing-stop `hwm` and moving `stop_price`, command states (`not_sent`, `admitted_not_dispatched`, `submitting`, `outcome_unknown`), and `POST /api/commands` `resolve_never_dispatched`. | **Orders Blotter & Stage 3 (`Section 6.6`)**: Shows plain-English transport chips (`Not sent`, `Sent`, `Outcome unknown — Refresh first`), linked-exit status chips (`Entry open · exits waiting`, `Protected`), and trailing `HWM / Moving Stop $`. |
| **E-10** | `state.fills[]` & `POST /api/native-report` (`{report_kind: "fills"}` / `"positions"`) | `state.fills[]` provides `transaction_time`, `price`, `qty`, `commission`, and `native_application` (`proven_in_current_process` \| `unresolved` \| `historical_source_only`); native reports provide `fee_provenance.fill_sources[]`. | **Orders → Fills (`Section 6.6`)**: Replaces raw `<pre>` JSON blocks in `brokerOrderTable()` with a tabular **Fills & Fee Provenance Table** (`Time | Sym | Side | Qty | Fill $ | Commission | Application`). |
| **E-11** | `state.investor.data.baskets[].preview` & `POST /api/investor` (`action: "basket_preview"`) | Computes `targets[]` (`residual_cash`, `pending_net_quantity`, `quantity_if_working_orders_fill`) and `complete_scenario` / `partial_scenario` (`hypothetical_cash`, `equity_weight_pct_estimate`, `turnover_pct`, `per_symbol_checks`). | **Orders → Baskets (`Section 6.6`)**: Replaces the `<pre>` JSON dump in `basketCommandControls()` with a **Before/After Weight, Turnover %, & Complete vs. Partial Fill Table**. |
| **E-12** | `GET /api/evaluations` (`evaluation_worker.py:1218, 1322`, `server.py:232`) | Returns `native_result` (`stats_pnls` and `stats_returns` display dicts from Nautilus 1.231.0 `BacktestResult`), walk-forward `folds[]` (`train`, `validation`, and `oos.scenarios[].result`), `trials[]`, and `reports` (`orders`, `fills`, `positions`, `account`). | **Strategy Lab (`Section 6.7`)**: Surfaces the **Nautilus Analyzer Stats** (with a short-window caveat), **Walk-Forward Folds (`Train | Validation | OOS`) Table**, and **Simulated Positions/Fills Tables**. |
| **E-13** | `GET /api/reporting/collections/{id}` & `POST /api/reporting` (`action: "export_csv"`) | Returns equity `points[]`, scalar `time_weighted` (`return`, `drawdown`, `subperiods[]`), scalar `dietz`, scalar `benchmark_comparison` (`benchmark_price_return`, `excess_return`, `reason`), `external_flows[]`, and scoped CSV exports (`holdings`, `activity`, `performance`). | **Portfolio → Performance (`Section 6.5`)**: Displays scalar metric tiles (`TWR`, `Modified Dietz`, `Max Drawdown`, `Benchmark Return`, `Excess Return` or `reason`), the equity/`profit_loss_pct` chart, `external_flows` table, and `[Export CSV ▾]`. |
| **E-14** | `state.nautilus.trade_stream` (`execution_lifecycle.py:1442, 1472`) | Reports `trade_stream.state` (`listening` \| `connecting` \| `disconnected` \| `not_started`) and optional `trade_stream.gap`. | **Global Shell (`Section 6.1`)**: Adds a live `Stream` status dot (green `listening`, amber `connecting`/`not_started`, red `disconnected`) next to `Nautilus` in the left rail. |
| **E-15** | `GET /api/runs/{id}` (`run.gateway_evidence`, `run.source_evidence`) | Full run detail records structured vendor attempts (`sec_edgar`, `yahoo`, `fred`, `polymarket`, `ddgs`, `laya` with `http_status`) and Maenifold Gateway calls (`maenifold.memory`, `maenifold.graph`, `maenifold.thinking`). | **Research → Sources & Activity (`Section 6.4`)**: Renders **Vendor & Memory Provenance Chips** from the loaded run detail and filters `Activity` to `selectedSymbol` with `[Whole run]` and `[Errors / 429s]` toggles. |

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

## 4. Complete User Stories & Acceptance Criteria (US-01 to US-25)

| ID | Persona | User Story | Acceptance Criteria & Exact Backend Binding |
|---|---|---|---|
| **US-01** | Alex | Pick stocks and start research directly on **Research** (`U1`). | Research toolbar includes an inline universe search/picker, `[Unfinished (N)]`, `[Needs Research Today (N)]`, `[Clear]`, and `[▶ Run Research (N)]` (`POST /api/runs`). When `0` boxes are checked, the button offers `[▶ Run Research (SYM)]` for `selectedSymbol`. |
| **US-02** | Alex | Confirm research parameters (including optional historical date & FRED toggle) and auto-focus on launch (`U2`, `E-01`). | Clicking `Run Research` opens the compact confirm popover (`reviewResearch`: symbol count, models, ETA from `DeskLists.estimate` or `"No timing yet"`, optional ISO New York `analysis_date`, `exclude_fred` checkbox, `"Uses current account context; places no orders"`). Confirming focuses the first batch stock if `selectedSymbol` is empty or in the batch. |
| **US-03** | Jordan | See honest 6-state run progress and never see a fake `Sell` badge (`L3`, `L4`). | Progress strip uses all 6 real research statuses (`completed`, `incomplete` when `completion_gaps` is non-empty, `failed`, `cancelled`, `running`, `queued`). Rating badge (`Buy`/`Hold`/`Underweight`/`Sell`) renders **only** when `status === 'completed'` and `reports.final_trade_decision` exists. Cancelled stocks show `Cancelled — no verdict`, and `"Loading..."` clears when loading ends. |
| **US-04** | Alex | See research age, unadjusted price drift since `trade_date`, and my live exposure on every verdict. | Research header joins `state.research[sym]` (`rating`, `trade_date`, `revision`, `completion_gaps`), `state.attention.data.reviews` (`review_required`), `state.quotes[sym]` (`price`, `change_pct`, `age_seconds`), `state.nautilus.market_data[sym].quote` (`bid_price`, `ask_price`, `bid_size`, `ask_size`), unadjusted `bar.raw.c` on `trade_date` (when loaded in `DATA.history`; otherwise `"Drift: — (Load daily bars)"`), `positions()`, working `orders()`, and draft `state.investor.data.proposals`. When Nautilus is disconnected or `reconciliation.status !== 'reconciled'`, shows `YOU: UNKNOWN` (amber) instead of `FLAT`. |
| **US-05** | Jordan | Read Portfolio Manager Decision & Trader Proposal above the fold on Research `Summary`. | From loaded `GET /api/runs/{id}/results/{sym}`, `Summary` orders content as: (1) Verdict + Price Drift + Exposure Strip, (2) **Portfolio Manager Decision** & **Trader Proposal** (first 6 lines + `[Read full]`), (3) **Bull vs. Bear** & **Risk Trio** columns, (4) **4 Analyst Status/Excerpt Chips** (`Market`, `Fundamentals`, `News`, `Sentiment` with Laya `counts`), and (5) compact bottom Disposition/Note bar. |
| **US-06** | Alex | Prepare an order from any screen via a docked drawer without losing chart or research context. | Clicking `[Prepare Order (T)]` on Dashboard, Markets, Research, or Journal opens a `380px` docked Stage 1 Order Proposal Drawer for `selectedSymbol` (`openTicket` + `researchPreparation`), with empty default Side/Qty, blocking illegal short sales when `positions()` is 0 on a long-only cash account, and providing `[Save Draft & Open Stage 2/3 in Orders →]`. |
| **US-07** | Alex | Dedicate **84%–91% of viewport height** to data panes across all 10 tabs. | `.topbar` is `36px` single-line; Workspace Bar is `40px` single-line; `.workspace-footer` (`36px`) and multi-sentence `pageHeader` paragraphs are removed; `#main` padding is tightened to `8px 12px 12px`; `DESIGN.md` is updated alongside the CSS. |
| **US-08** | Alex | Scan a morning triage strip and unclipped 2-row grid on **Dashboard** (`L1`). | Top 1-line `Needs attention` strip (`dashboardAttentionSummary`) shows working orders, unread alerts, stale quotes, and unresearched holdings (hidden when empty). Watchlist starts with `0 checked`, sorted by `Held first` + `|Chg%|`. Bottom 3 panes (`Saved Research`, `Positions`, `Open Orders & Drafts`) never clip at `1080p` or `900p`. |
| **US-09** | Alex | See trader scan columns and a persistent Instrument Header on **Markets** (`L13`, `E-02`, `E-03`). | Scan table columns: `SYM | LAST | CHG% | BID×ASK (SPR) | POS | UPL% | WORKING | RSCH·AGE` (moving `BARS` count to the 1-line chart history bar and hiding duplicate `AMZN / AMZN` subtitles). Right pane keeps a persistent Instrument Header above `Chart | Research | Evidence & Filings | Options`, plus a `[Prepare Order (T)]` drawer button. |
| **US-10** | Jordan | Request and inspect SEC EDGAR XBRL facts, Corporate Actions, and Alpaca News on **Markets** and **Research** (`E-07`). | `[Evidence & Filings]` includes the compact collection bar (`POST /api/market-history` `{action: "evidence", symbols, provider, scopes, start, end, earnings_horizon}`) and renders saved `GET /api/stock-evidence?symbol=SYM` `observations[scope].records[]`: SEC EDGAR latest filed `reported_fact` per line item (`balance_sheet`, `income_statement`, `cashflow`) and `industry` SIC; Alpaca `Dividends / Splits / Mergers`; and Alpaca `News`. |
| **US-11** | Jordan | Screen saved StockTwits posts locally with Laya and inspect post-level sentiment (`E-08`). | Sentiment card and `Reports → Social` expose `[Screen Saved Posts Locally]` (`POST /api/runs/local-laya` for the first 5 saved StockTwits posts) and display `social_sentiment.sources.*.counts`, `stop_reason`, and per-post `post.stance` from `GET /api/runs/{id}/results/{sym}`. |
| **US-12** | Jordan | Inspect structured Vendor & Maenifold provenance and filter `Activity` on **Research** (`E-15`). | `Sources & Filings` shows domain, capture date, and report category, plus vendor/gateway call summary chips (`SEC EDGAR`, `Yahoo`, `Polymarket`, `FRED`, `Maenifold`) from `GET /api/runs/{id}`. `Activity` defaults to `selectedSymbol` with a `Whole run` toggle and an `Errors / 429s` (`http_status === 429`) filter. |
| **US-13** | Alex | Monitor populated Holdings with `Today P/L` and `Avail Qty` on **Portfolio** (`L11`, `E-04`). | `Portfolio → Positions` shows `SYM | QTY | AVAIL | AVG COST | LAST | TODAY P/L ($, %) | MKT VALUE | TOTAL UPL ($, %) | WT% | WORKING | RSCH·AGE | ACT` (scaling Alpaca fraction strings `unrealized_plpc * 100` and `unrealized_intraday_plpc * 100`, and reading `available_exit_quantity` / `qty_available`). When `0` positions exist, hides empty `<thead>` headers and shows a compact 2-line empty card. |
| **US-14** | Morgan | Run the session-only **Proposed Model Portfolio** alongside live prices and drift (`Violation 2`). | `Portfolio → Proposed Model Portfolio` (`POST /api/portfolio-model` with `request_id`) stays strictly separate from Human Baskets (`Orders → Baskets`), scales `weight * 100`, and displays `MODEL REF (DATED)` (`reference.price`), `LAST NOW (IEX)` (`quotes[sym].price`), derived `DRIFT %` (`(quotes[sym].price / reference.price - 1) * 100` or `"Unavailable"`), and `YOUR POS`. |
| **US-15** | Jordan | View **Portfolio → Performance** with scalar return/drawdown/benchmark tiles, external flows, CSV exports, and a capped empty state (`L2`, `E-13`). | When `<2` points exist, shows a `120px` card with a `24px` icon and `[Collect Account History in Journal →]`. When a collection is loaded (`GET /api/reporting/collections/{id}`), displays scalar tiles (`time_weighted.return`, `dietz`, `drawdown`, `benchmark_comparison.benchmark_price_return` / `excess_return` or `reason`), the equity/`profit_loss_pct` chart, `external_flows[]` table, and `[Export CSV ▾]`. |
| **US-16** | Alex | Stage orders with live Bid/Ask/Size/Spread, click-to-seed Limit price, and `% of equity` sizing math (`E-02`, `E-04`). | `Orders` Stage 1 leaves Side/Qty blank until chosen, defaults Type to `LIMIT`, displays live `Bid×Size / Ask×Size / Spread bps`, `Quote Age`, `Current Position` (`qty`, `available_exit_quantity`), and `Cash / Buying Power / Equity`. Clicking `Bid`, `Ask`, or `Last` seeds `Limit $` (`"from ask, not previewed"`); typing `Qty` shows client-derived `$ notional`, `% of equity`, `% of cash`, and `post-trade weight %`; keeps `Stop $` and `Target $` visible with a UI-estimated stop-loss readout. |
| **US-17** | Riley | See the 10-Rule Policy Check Table and Held-Bracket Stop-Loss Risk in **Orders Stage 2** (`E-06`). | Stage 2 filters `checks[]` to the 10 `state.investor.rule_labels` keys (`cash_reserve_pct`, `max_position_pct`, `max_gross_exposure_pct`, `loss_limit_pct`, `scenario_loss_pct`, `max_sector_pct`, `max_correlation_pct`, `max_spread_bps`, `min_quote_size`, `session_freshness`), showing failing rules first, observed value from `details` vs. limit from `policy.rules[key].value`, grey `Not configured` when `state` is `unset`/`disabled`, and held-bracket `conditional_group.stop_loss_estimate_before_fees`. |
| **US-18** | Riley | Confirm Submit/Cancel/Replace with duplicate-order guard, transport chips, and `resolve_never_dispatched` recovery (`E-09`). | Stage 3 warns if a working order already exists in that symbol, requires a 2-step inline confirmation showing exact terms, disables in-flight buttons to prevent double-submit, displays a timestamped receipt, and shows plain chips (`Not sent`, `Sent`, `Outcome unknown — Refresh first`) with `[Resolve Never Dispatched]`. |
| **US-19** | Riley | Inspect structured Fills (`commission` & `native_application`) and Human Baskets (`complete` vs. `partial` scenarios) without raw JSON dumps (`E-10`, `E-11`). | `Orders → Fills` renders a tabular fills blotter (`transaction_time | Sym | Side | Qty | Fill $ | Commission | native_application`, plus `fee_provenance` when a native fills/positions report is captured). `Orders → Baskets` renders `baskets[].preview` before/after weight, `turnover_pct`, and `Complete vs. Partial Fill` policy checks in a table instead of `<pre>` JSON. |
| **US-20** | Morgan | Run both **Saved-Plan Simulations** and **Walk-Forward Experiments** with Nautilus quality stats and fold tables (`L10`, `E-12`). | `Strategy Lab` (`#strategy`) places `[Load Saved Plans & Data]` below the heading, uses a 3-step left accordion (`360px`) with the required immutable preview gate, and renders `native_result` (`stats_pnls`, `stats_returns` when present, with a short-window caveat), walk-forward `Folds` (`Train | Validation | OOS`) table, and `reports.positions` / `reports.fills` tables on the right. |
| **US-21** | Jordan | Use **Decision Journal** with focus-safe search, guarded revert, and 1-row Position Outcomes (`L8`). | `Journal` (`#journal`) merges Notes into `Decisions & Notes`, formats `Human proposal` plainly, keeps focus inside `#decision-search` while typing, guards `[Revert Unsaved Edits]` with a dirty count, and collapses 12-paragraph `Position Outcomes` groups into a 1-row summary table + right inspector. |
| **US-22** | Riley | Triage **Alerts** with unread badge, grouped restarts, calm freshness setup, and 3 quick rule templates (`L12`). | `Alerts` (`#alerts`) shows unread count (`state.attention.observations.data.occurrences`) on `Inbox`, collapses `25 service restarts` into 1 expandable row, frames unset quote-age limit as a calm setup prompt with `[Set in Trading Rules →]`, and provides 3 one-click rule templates (`price_above`, `price_below`, `source_stale`) above the collapsible 16-condition builder. |
| **US-23** | Morgan | See the entire 18-node **Workflows** diagram with `Fit All` and click any node to edit its prompt (`L5`). | `Workflows` (`#workflows`) adds `Fit All` (`0.25` zoom floor) as the default opening zoom, shows an inline `[Retry]` banner if rendering fails, loads a node's prompt + related files chip bar on node click, supports `Ctrl/Cmd+S`, closes popovers on `Escape`/outside-click, and replaces native `window.confirm()` with an in-app `<dialog>`. |
| **US-24** | Riley | Manage all 5 **Settings** categories with Basic vs. Advanced disclosure and an isolated Danger Zone (`L6`, `E-05`). | `Settings` (`#settings`) keeps all `DeskConfig` controls across `Account & Engine` (with whitelisted account flags), `Research & Models` (core fields upfront + advanced budgets/rounds/Laya device in `<details>`), `Universe & Keys` (1,000-stock CSV import/export), `Trading Rules & Native Cache` (10 rules + native table capture), and `Diagnostics & Backup` (top health chips + bottom red-bordered Restore Danger Zone). |
| **US-25** | All | Use real WAI-ARIA `role="tablist"` tabs, keyboard shortcuts, and chart text alternatives across all 10 pages. | Every sub-tab bar uses `role="tablist"` + roving `tabindex` + Left/Right arrow keys and `36–40px` control heights matching `DESIGN.md`. All 4 SVG charts include hollow down-candles (`□`), solid up-candles (`■`), dashed/solid legends, and `<details>` data tables. |

---

## 5. Focus vs. Batch Contract & Safe Trader Hotkeys

### 5.1 One Focus Symbol (`selectedSymbol`) vs. One Batch Set (`selectedSymbols`)
- **`selectedSymbol` (Focus / Reading):** Changed by clicking any stock row, picking from Global Search (`Ctrl+K`), or clicking an alert/order row. Drives the linked Chart, Instrument Header, Research Inspector, and Order Ticket.
- **`selectedSymbols` (Checked Batch):** Changed **only** by row checkboxes, `X` / `Space` key, `[Select Filtered]`, `[Select Unfinished]`, or `[Clear]`. Persists across tab switches and never starts with all 24 universe symbols auto-checked.
- **Delete Selection (new frontend state `researchDeleteSelection`):** Lives strictly inside the `[Manage / Delete]` mode on Research and never overwrites `selectedSymbols`.
- **Loud `UNKNOWN` Exposure State (`C-8`):** Whenever `state.connection.account_verified !== true`, `state.nautilus.status !== 'connected'`, or `state.nautilus.reconciliation.status !== 'reconciled'`, the exposure chip displays `YOU: UNKNOWN · WORKING: UNKNOWN` in amber and disables ticket position-based seeding (never printing `FLAT` when broker state is unverified).

### 5.2 Safe Trader Keyboard Shortcuts
*(All single-key shortcuts are ignored whenever focus is inside an `INPUT`, `TEXTAREA`, `SELECT`, `BUTTON`, or open `<dialog>`.)*

| Key | Action | Safety Rule |
|---|---|---|
| `Ctrl+K` or `/` | Focus Global Symbol Search (`Enter` = inspect symbol; `Shift+Enter` = toggle in research batch). | Never starts a run or stages an order. |
| `J` / `K` or `↓` / `↑` | Move `selectedSymbol` down/up in the active stock table. | Never toggles checkboxes. |
| `X` or `Space` | Toggle batch checkbox (`selectedSymbols`) on the focused stock row. | Never changes `selectedSymbol`. |
| `Enter` (on row) | Open `Research → Summary` for the focused stock (or `Preview Impact` when inside Order Ticket). | **Never** triggers `Approve` or `Submit`. |
| `T` | Toggle the `380px` docked **Prepare Order** Stage 1 proposal drawer for `selectedSymbol`. | Stages a draft only; never approves or submits. |
| `←` / `→` | Move between tabs in any focused `role="tablist"`. | Standard WAI-ARIA tab pattern. |
| `Escape` | Close any open popover, `<dialog>`, or docked drawer and restore focus to the trigger. | Never discards saved data without confirmation. |
| `Alt+R` | Refresh workspace state (`readState()`). | Existing shortcut preserved. |

### 5.3 Docked `Prepare Order (T)` Stage 1 Drawer Specification (`C-9`)
Opened from Dashboard, Markets, Research, or Journal without navigating away (`width: 380px`, docked right, closes on `Escape` and restores focus to trigger):

```text
+-------------------------------------------------------+
| PREPARE ORDER PROPOSAL · AMZN                 [Esc ✕] |
| IEX $252.51 (+1.14%)  [Bid 252.40×300] [Ask 252.60×100]|
| YOU: FLAT (0 sh, 0 avail) · WORKING: none             |
| Linked Research: HOLD · 2026-10-28 (rev 3)            |
+-------------------------------------------------------+
| Side:     [( ) Buy   ( ) Sell]  (Blank until chosen)  |
| Quantity: [________] sh         Type: [Limit       v] |
| Limit $:  [252.60  ] (←Click Bid/Ask/Last to seed)    |
| TIF:      [DAY     v]           Sess: [Regular     v] |
| Sizing:   — (% of Equity / Cash shown once Qty typed) |
| Exits:    Stop $ [______]       Target $ [______]     |
| Rationale:[_________________________________________] |
|                                                       |
| [1. Preview Impact]       [2. Save Draft Revision]    |
| (After saving draft:                                  |
|  [Open Stage 2/3 Policy Check & Approval in Orders->])|
+-------------------------------------------------------+
```

---

## 6. Page-by-Page Impeccable Wireframes & Exact Data Bindings

### 6.1 Global Shell (`index.html` — `36px` App Bar, `172px/208px` Nav Rail, Zero Footer)

- **Data bindings:**
  - `state.connection.paper_verified`, `state.account.trading_blocked`, `state.account.account_blocked`, `state.account.trade_suspended_by_user` (shows `[⚠ Account Blocked]` chip only if true).
  - `state.quotes_updated_at`, `state.clock?.is_open` (`Market: Open` / `Market: Closed` / `Unknown` when `clock` is null).
  - `state.attention.observations.data.occurrences` (filter `unread === true` for unread count badge on Alerts).
  - `state.trading_paused` (`Orders: Active` green pill vs. `Orders: Paused` amber pill — standardized everywhere, fixing `L6` & `L14`).
  - `state.commands.data.recovery_required` (1-line recovery banner shown under header only when `true`).
  - Left nav rail: **10 distinct SVG icons** (`iconPaths` in `app.js`, fixing `L7`), plus compact engine status dots (`Nautilus: state.nautilus.status`, `Stream: state.nautilus.trade_stream.state` — green `listening`, amber `connecting`/`not_started`, red `disconnected`, `Laya: state.health.local_laya.status`).

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
  - **Top Mode Tablist (`role="tablist"`):** `[*Universe & Watchlists (24)*]`, `[Yahoo Screener]` (`/api/discovery`), `[Saved Scans]` (`GET /api/discovery` → `scanner.data.definitions/runs`).
  - **Persistent Instrument Header Strip:** Joins `state.quotes[sym]`, `state.nautilus.market_data[sym].quote` (`bid_price`, `bid_size`, `ask_price`, `ask_size`, derived IEX spread bps), `session_eligibility` badges (`Fractional ✓`, `Fractional Ext-Hrs ✓`, `Overnight Halted ⚠`), `positions()`, working `orders()`, draft `proposals`, and `state.research[sym]` (`rating`, `trade_date` age & unadjusted `bar.raw.c` drift). Hides duplicate company subtitle when `companyName(sym) === sym` (`L13`).
  - **Right-Pane Sub-Tabs:** `[*Chart*]`, `[Research]`, `[Evidence & Filings]` (binds to `GET /api/stock-evidence?symbol=SYM` `observations[scope].records[]` + `POST /api/market-history` `{action: "evidence"}` collection bar — `E-07`), `[Options]` (disabled with tooltip `"No option contracts loaded for this stock"` when empty), plus the right-aligned `[Prepare Order (T)]` drawer button.
  - **1-Line History Backfill Bar:** Collapses the 10-field history form into `History: 1,255 daily bars cached (Oct 28) · [Get 252 Daily Bars] [More: Interval / Dates / Adjustment ▾]` (`POST /api/market-history`).
  - **Docked `[Prepare Order (T)]` Drawer:** Opens alongside the chart so the trader can click `[Bid]`, `[Ask]`, or `[Last]` to seed `Limit $` (or use 2-step `chart_copy` for historical bars) without closing the chart.

```text
+----------------------------------------------------------------------------------------------------------+
| MARKETS   [*Universe & Watchlists (24)*] [Yahoo Screener] [Saved Scans]   0 checked · [Run Research (AMZN)]|
+----------------------------------------+-----------------------------------------------------------------+
| List: [All Universe: PNIS (24) v] [+New]| AMZN $252.51 (+1.14%) [Bid 252.40×300] [Ask 252.60×100] (8bp)   |
| [Search...] [View: All v] [Sortv] [Ed] | [Fractional ✓] · YOU: FLAT · WRK: — · RSCH: [HOLD · 1d (+1.1%)] |
+----------------------------------------+-----------------------------------------------------------------+
| SYM    LAST    CHG%   SPR  POS  RSCH   | Tabs: [*Chart*] [Research] [Evidence & Filings] [Options]  [T▸] |
| AMZN*  252.51  +1.14% 8bp  —    Hold·1d| Source: [*Live IEX Cache* | Research Date]  [*1Day*] [1Hr] [15m]|
| INTC    22.40  -0.85% 5bp  —    Undw·1d| Drawers: [Studies & Formulas] [Drawings] [Comparison] [Alert+$] |
| TER    108.12  -1.40% 9bp  —    Sell·1d| +-------------------------------------------------------------+ |
| AAPL   231.10  +0.42% 4bp  —    Cancel | | History: 1,255 daily bars cached (Oct 28) · [252d] [More ▾] | |
| GOOGL  182.30  -0.12% 6bp  —    Cancel | +-------------------------------------------------------------+ |
| META   590.40  +1.85% 7bp  —    Cancel | |                                                             | |
| MSFT   428.15  +0.33% 5bp  —    Cancel | |             FULL-HEIGHT LIGHTWEIGHT CHART                   | |
| NVDA   141.80  +2.10% 6bp  —    Cancel | |     • Clicking [T▸ Prepare Order] docks the 380px Stage 1   | |
| ... sticky-header scroll (25/50/100    | |       Proposal Drawer right beside this chart               | |
|     batch scope in [Ed] menu)          | |     • Clicking [Evidence & Filings] shows SEC EDGAR XBRL    | |
|                                        | |       reported facts, Corporate Actions, & request bar      | |
|                                        | +-------------------------------------------------------------+ |
|                                        | [▸ Selected bar readout & OHLCV table (a11y / keyboard)]        |
+----------------------------------------+-----------------------------------------------------------------+
```

---

### 6.4 Research (`#research`) — Self-Contained Picker, Confirm Popover, 6-State Queue, & Trader Summary

- **Data bindings & fixes (`U1`, `U2`, `L3`, `L4`, `E-01`, `E-07`, `E-08`, `E-15`):**
  1. **Inline Stock Picker & Confirm Popover:** Check stocks in the left rail or click `[Unfinished (21)]` / `[Needs Today]`, then click `[▶ Run Research (N)...]`. Opens the compact confirm popover showing symbol list, active workflow (`Default`), deep/fast models, ETA (`DeskLists.estimate`), optional ISO New York **`Analysis Date`** (`analysis_date`, omitted for today) and **`[ ] Exclude FRED macro series`** (`exclude_fred`), and `"Uses current account context; places no orders"`.
  2. **6-State Progress Strip:** Displays `completed`, `incomplete` (derived when `completion_gaps` is non-empty), `failed`, `cancelled`, `running`, and `queued` counts. Cancelled is slate, never green.
  3. **Trader Verdict & Drift Header:** Pairs `rating` (shown **only** if `status === 'completed'` and `final_trade_decision` is saved) with `trade_date` age (`1d old`), unadjusted price drift from saved `bar.raw.c` on `trade_date` to live `quotes[sym].price` (`Drift: — (Load daily bars)` when bars are not loaded), live `Bid×Size / Ask×Size`, `positions()` / `orders()` / `proposals` exposure chip (`YOU: UNKNOWN` in amber when Nautilus is stopped/unreconciled), `state.attention.data.reviews` `review_required`, and explicit `completion_gaps` warning.
  4. **PM Decision & Trader Plan First:** Loaded from `GET /api/runs/{id}/results/{sym}`, places `final_trade_decision` and `trader_investment_plan` excerpts above the fold, followed by `investment_debate_state` (Bull/Bear) and `risk_debate_state` (Aggressive/Neutral/Conservative), then the 4 Analyst Cards (including `[Screen Saved Posts Locally]` for `POST /api/runs/local-laya`).
  5. **5 Evidence Tabs:** `[*Summary*]`, `[Reports (7)]`, `[Debate & Risk]`, `[Sources & Filings]` (links with domain + date + Vendor/Maenifold provenance chips from `GET /api/runs/{id}` + `/api/stock-evidence` SEC XBRL & corporate actions), and `[Activity]` (filtered to `selectedSymbol` by default with `[Whole run]` and `[Errors / 429s only]` toggles).

```text
+----------------------------------------------------------------------------------------------------------+
| RESEARCH  Batch: 2 checked [Unfinished (21)] [Needs Today] [Clear]  [▶ Run Research (2) · places no order]|
+----------------------------------------------------------------------------------------------------------+
| Queue: [===3 Completed===|-----------21 Cancelled-----------] 3 completed · 21 cancelled · 0 running     |
+-------------------------------+--------------------------------------------------------------------------+
| STOCKS (24)  [Filter: All v]  | AMZN  Last $252.51 (+1.14%)  Bid 252.40×300 Ask 252.60×100  [Prepare (T)]|
| [Search...]          [Manage] | YOU: FLAT · WORKING: — · DRAFT: — · Review required: No     [Export JSON]|
+-------------------------------+--------------------------------------------------------------------------+
| [ ] SYM   RSCH·AGE  DRIFT POS | Tabs: [*Summary*] [Reports (7)] [Debate & Risk] [Sources & Filings] [Act]|
| [x] AMZN* Hold·1d   +1.1% —   | +----------------------------------------------------------------------+ |
| [x] INTC  Undw·1d   -0.4% —   | | [HOLD] · 1d old (2026-10-28) · Unadj close $249.70 → Now +1.1% (IEX) | |
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
| Analysis Date: [Today (live) or YYYY-MM-DD]   [ ] Exclude FRED macro series    |
| Uses current account context; date-pins vendor inputs. Places no broker order. |
| [ ] Keep batch selection checked after launch       [Cancel]  [Start Research] |
+--------------------------------------------------------------------------------+
```

---

### 6.5 Portfolio (`#portfolio`) — Populated Holdings Risk Table (`Today P/L` & `Avail Qty`), Proposed Model, & Performance

- **Data bindings (`L2`, `L11`, `E-04`, `E-13`):**
  - **Positions Tab:** Renders `symbol`, `qty`, `available_exit_quantity` / `qty_available` (`AVAIL`), `avg_entry_price`, `current_price`, `unrealized_intraday_pl` & `Number(unrealized_intraday_plpc) * 100` (`OPEN POS TODAY P/L`), `market_value`, `unrealized_pl` & `Number(unrealized_plpc) * 100` (`TOTAL UPL`), derived `weight %`, working orders in symbol, and `state.research[sym]` (`rating · age`). When `positions.length === 0`, hides `<thead>` and renders a 2-line empty card.
  - **Proposed Model Portfolio Tab:** Strictly the session-only joint deep-model synthesis (`POST /api/portfolio-model` with `request_id`), scaling `weight * 100` and showing `MODEL REF (DATED)` (`reference.price`) alongside `LAST NOW (IEX)` (`quotes[sym].price`), derived `DRIFT %` (`(quotes[sym].price / reference.price - 1) * 100` or `"Unavailable"`), and `YOUR POS`.
  - **Performance Tab:** Loads selected collection via `GET /api/reporting/collections/{id}`, displaying scalar metric tiles (`time_weighted.return`, `dietz`, `drawdown`, `benchmark_comparison.benchmark_price_return` & `excess_return` or `reason`), the equity / `profit_loss_pct` chart, `external_flows[]` table, and `[Export CSV ▾]` (`holdings`, `activity`, `performance` via `POST /api/reporting`). When `<2` points exist, caps the empty card to `120px` with `[Collect Account History in Journal →]`.

```text
+----------------------------------------------------------------------------------------------------------+
| PORTFOLIO   Tabs: [*Positions*]  [Proposed Model Portfolio]  [Performance]   [Export CSV ▾] [Refresh]    |
+----------------------------------------------------------------------------------------------------------+
| EQUITY $100,000 | CASH $90,385 | BUYING POWER $90,385 | LONG VAL $9,615 | OPEN TODAY +$173 | UPL +$754 ✓ |
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
| (TAB 3: PERFORMANCE — Scalar metric tiles, equity/P&L% chart, external flows & 120px empty state:)       |
| +------------------------------------------------------------------------------------------------------+ |
| | TWR: — · Modified Dietz: — · Benchmark Return / Excess (SPY): — · Max Drawdown: —   [Export CSV ▾]   | |
| | [📈 24px] Needs at least 2 saved account-history observations. [Collect Account History in Journal->]| |
| +------------------------------------------------------------------------------------------------------+ |
```

---

### 6.6 Orders (`#orders`) — Full-Context Ticket, 10-Rule Policy Table, Blotter, Fills & Baskets

- **Data bindings (`E-02`, `E-03`, `E-04`, `E-06`, `E-09`, `E-10`, `E-11`):**
  - **Stage 1 (Prepare Draft Proposal):** Leaves Side and Qty blank by default until chosen; defaults Order Type to `LIMIT`; shows live `IEX Last`, `[Bid×Size]`, `[Ask×Size]`, derived IEX `Spread bps`, `Quote Age`, `Session Eligibility` (`Fractional ✓`, `Fractional Ext-Hrs ✓`), `Current Position (qty, available_exit_quantity)`, and `Cash / Buying Power / Equity`. Clicking `Bid`, `Ask`, or `Last` seeds `Limit $` (`"from ask, not previewed"`). Shows client-derived sizing math (`$ notional`, `% of equity`, `% of cash`, `weight after`) and keeps `Stop $` / `Target $` visible with a UI-estimated stop-loss readout (`"UI estimate before fees; server check authoritative"`).
  - **Stage 2 (10-Rule Policy Check & Single-Use Approval):** Filters `checks[]` from `state.investor.current_checks[proposal_id]` / `proposal.risk_evaluation` to the 10 `state.investor.rule_labels` keys (`cash_reserve_pct`, `max_position_pct`, `max_gross_exposure_pct`, `loss_limit_pct`, `scenario_loss_pct`, `max_sector_pct`, `max_correlation_pct`, `max_spread_bps`, `min_quote_size`, `session_freshness`) with observed value from `details` vs. limit from `policy.rules[key].value` (failing rules first; grey `Not configured` when `state` is `unset`/`disabled`), plus held-bracket amendment `conditional_group.stop_loss_estimate_before_fees`.
  - **Stage 3 (Separate Broker Submission & Recovery):** Checks for duplicate working orders in the same symbol, requires a 2-step inline confirmation showing exact terms, disables in-flight buttons, shows plain transport chips (`Not sent`, `Sent`, `Outcome unknown — Refresh first`), and exposes `[Resolve Never Dispatched]` when `c.state === 'outcome_unknown'`.
  - **Sub-Tabs on Right Pane:**
    - `[*Working & Drafts Blotter*]`: Working orders (with `Bracket / OTO / OCO` exit chips and trailing `HWM / Moving Stop $`) + Unsent Drafts (filtered/sorted with `selectedSymbol` first).
    - `[Fills & Fee Provenance]`: Tabular fills (`transaction_time | Sym | Side | Qty | Fill $ | Commission | native_application` from `state.fills`, plus `fee_provenance` when a native fills/positions report is captured).
    - `[Human Baskets]`: Renders `state.investor.data.baskets[].preview` (`targets[]` `residual_cash`, `pending_net_quantity`, `quantity_if_working_orders_fill`, and `complete_scenario` / `partial_scenario` `turnover_pct`, `hypothetical_cash`, `equity_weight_pct_estimate`).
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
| Side:  [( ) Buy  ( ) Sell]   Type: [Limit    v] | ------------------------------------------------------ |
| Qty:   [________] sh  Limit $: [252.60] (←Ask)  | STAGE 2: 10-RULE POLICY CHECK & EXACT APPROVAL         |
| TIF:   [DAY     v]    Session: [Regular      v] | RULE (`rule_labels`)  VALUE       LIMIT      STATUS    |
| Sizing: — (shows $ & % Equity/Cash once typed)  | max_position_pct      5.1%        20.0%      Pass ✓    |
| Exits:  Stop $ [______]  Target $ [______]      | max_spread_bps        8 bps       50 bps     Pass ✓    |
|         (UI est. stop loss shown when entered)  | min_quote_size        100 sh      1 sh       Pass ✓    |
| [▸ Bracket / OTO / OCO & Replace working order] | session_freshness     42s         —          Not cfg   |
|                                                 | [▸ Show all 10 policy rules]                           |
| [Preview Impact (Enter)]  [Save Draft Revision] | [1. Check Order]   [2. Approve Exact Revision #3]      |
| (Draft ≠ Approved ≠ Submitted)                  | ------------------------------------------------------ |
|                                                 | STAGE 3: SEPARATE BROKER SUBMISSION                    |
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
  - Right Canvas: Equity curve + benchmark overlay + `<details>` observations table, **Headline Metrics** (`Net Return %`, `Modeled P&L`, `Max Drawdown %`, `Closed Trades`), **Nautilus Portfolio Analyzer Stats** (`native_result.stats_pnls` / `stats_returns` display dicts when present in `/api/evaluations`, with a 1-line note that ratios are meaningless on short windows), **Walk-Forward Folds Table** (`Fold | Train | Validation | OOS Return & Drawdown` from `fold.oos.scenarios[].result`), and **Simulated Positions / Fills Table** (`reports.positions` / `reports.fills`).

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
  - **Account & Engine:** Shows observed Alpaca Paper/Live account ID once, read-only whitelisted Account Status Flags (`status`, `trading_blocked`, `account_blocked`, `trade_suspended_by_user`, `shorting_enabled`, `multiplier`, `disable_overnight_trading` — `E-05`), `Start / Stop Nautilus`, `Native Execution Profile`, and OS Credential Manager keys.
  - **Research & Models:** Keeps all `DeskConfig` controls, with core model fields upfront + `[▸ Advanced Token Budgets, Rounds, Concurrency, Retries & Local Laya Router]` collapsed.
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
| [▸ Advanced Token Budgets, Rounds, Concurrency, Retries & Local Laya Router (collapsed by default)]      |
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
| **U2:** Screen stuck on old stock after launch | User | Smart launch auto-focuses first batch symbol and updates 6-state progress strip (`6.4`). |
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
| **T1–T6:** Price drift, exposure strip, PM first, docked ticket | Trader Audit | Verdict strip pairs rating with unadjusted `bar.raw.c` drift, `Bid×Size/Ask×Size`, `POS/WORKING/DRAFT` (`UNKNOWN` when disconnected), PM decision above fold, and `380px` docked `Prepare Order (T)` drawer (`5.3`, `6.2–6.6`). |
| **E-01 to E-15:** 15 hidden existing backend features | Backend Audit | Wired into `6.1–6.11` with zero Python backend changes (see Table 1.1). |

---

## 8. Frontend Implementation Workstreams (Zero Backend Changes)

When approved to build, implementation runs across 4 frontend-only workstreams in `tradingagents/web/static/` (plus updating `DESIGN.md` to match the `36px` top bar and removed footer):

1. **Workstream 1 — Global Shell, Chrome Diet, Shared `renderTablist()` & Hotkeys (`index.html`, `app.css`, `app.js` shell, `DESIGN.md`):**
   - `36px` top bar, delete `.workspace-footer`, remove multi-sentence `pageHeader` descriptions, add 10 distinct sidebar SVG icons, add `trade_stream.state` dot & account-blocked warning chip, standardize `Orders: Active / Paused`, implement WAI-ARIA `renderTablist()` with Left/Right arrow keys, and bind input-guarded safe hotkeys (`J/K`, `X`, `T`, `Escape`).
2. **Workstream 2 — Research & Workflows (`app.js`, `report-format.js`, `workflows.js`, `ui-research-journal.css`, `ui-workflows.css`):**
   - Research inline stock picker + confirm popover (with existing `analysis_date` and `exclude_fred` parameters), 6-state progress strip, no fake `Sell` badge or stuck `Loading...`, Trader Verdict + Unadjusted Close Drift + Exposure header (`UNKNOWN` when disconnected), PM Decision & Trader Plan above the fold, `[Screen Saved Posts Locally]` Laya view, `[Sources & Filings]` tab (`/api/stock-evidence` + vendor/Maenifold chips), `[Manage]` delete toggle, and Workflows `Fit All` (`0.25` floor) + node-click prompt chips + in-app `<dialog>`.
3. **Workstream 3 — Dashboard, Markets & Portfolio (`app.js`, `market-chart.js`, `lists.js`, `ui-markets.css`, `ui-instrument.css`):**
   - Dashboard morning triage strip, `0 checked` default, trader scan columns (`SYM | LAST | CHG% | BID×ASK | POS | WORKING | RSCH·AGE`), hollow down-candles + legends + `<details>` bar tables, Markets persistent Instrument Header + 1-line history backfill + `[Evidence & Filings]` tab + `380px` docked `Prepare Order (T)` drawer, Portfolio populated Positions table (`Open Pos Today P/L`, `Avail Qty`), Proposed Model live drift columns (`weight * 100`), and Performance scalar metric tiles + equity/P&L% chart + `external_flows` table + capped `120px` empty state.
4. **Workstream 4 — Orders, Strategy Lab, Journal, Alerts & Settings (`app.js`, `command-controls.js`, `nautilus.js`, `ui-orders.css`):**
   - Direct 2-column DOM rendering (removing `layoutOrders`/`layoutMarkets`), Stage 1 full-context ticket (blank default Side/Qty, `Bid×Size/Ask×Size`, click-to-seed `Limit $`, `% of equity` sizing math, visible `Stop/Target`), Stage 2 10-Rule Policy Table (`rule_labels`, grey `Not configured` when unset/disabled, held-bracket `stop_loss_estimate_before_fees`), Stage 3 duplicate-order check + inline confirm/receipt + transport chips, tabular `Fills` (`transaction_time`, `commission`, `native_application`) & `Baskets` (`baskets[].preview` `turnover_pct`, partial-fill table), Strategy Lab 3-step accordion + `native_result` stats/fold/trade tables, Journal focus-safe search + 1-row outcomes, Alerts grouped restarts + 3 quick rule templates, and Settings 5-tab progressive disclosure + isolated Restore Danger Zone.

---

## 9. Professional Stock Trader Sign-Off Record

### 9.1 Claude Sonnet 5.5 Pro-Trader & Contract Audit Sign-Off (`sonnet-v4-trader-signoff`)
> **Pro-Trader / Backend-Contract Sign-Off — v4:** Reviewed against `server.py`, `service.py`, `nautilus_worker.py` and `app.js`. **APPROVED.** Every control and column binds to an existing `/api/*` route and `state.*` field, with zero Python changes (`trade_stream.state`, the 10 `rule_labels` keys, whitelisted `state.account` fields, scalar Performance tiles + `external_flows` table, and the `/api/market-history` `{action: "evidence"}` collection path verified). All six trader dealbreakers are specified: dated price drift using unadjusted closes (`bar.raw.c`), position/working/draft awareness with an explicit `UNKNOWN` state when disconnected or unreconciled, PM decision and trader plan above the fold, a `380px` docked Stage 1 proposal drawer with a defined hand-off to Orders Stage 2/3, a full-context ticket with the 10-rule policy table, and the holdings risk table with Today P/L and Avail Qty. Unset policy rules display as `"Not configured"`, never as `"Pass"`.

### 9.2 Grok 4.7 Pro-Trader & Contract Audit Sign-Off (`grok-v4-trader-signoff`)
> **Professional Stock-Trader Sign-Off — 2026-10-28: APPROVED.** The v4 blueprint is a true frontend-only trading desk and does not authorize or require new backend features. All API bindings match the live server contracts: whitelisted `state.account` flags, the ten `state.investor.rule_labels` keys filtered from approval `checks[]`, unread alerts at `state.attention.observations.data.occurrences`, trade stream at `state.nautilus.trade_stream.state`, Alpaca fractional P/L percentages and 0–1 model weights scaled by 100, performance collections and stock-evidence observations bound to their real endpoints without fabricated series, and PM/trader text plus vendor provenance loaded from `GET /api/runs/{id}`. This is the exact UI to build and nothing more.
