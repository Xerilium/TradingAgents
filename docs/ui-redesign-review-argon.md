# Argon UI Redesign Review: Stress-Test, Contract Audit, and Refined Wireframes

- **Reviewer:** Gemini 4 Argon (`gemini-4-argon`)
- **Date:** 2026-10-28
- **Target Reviewed:** `docs/ui-redesign-blueprint.md` and `docs/ui-design-critique.md`
- **Source Verification:** Cross-checked against `PRODUCT.md`, `DESIGN.md`, `.impeccable/surface-brief-paper-desk.md`, `docs/desk-reference.md`, `docs/local-desk-guide.md`, and the live UI source in `tradingagents/web/static/` (`index.html`, `app.js`, `workflows.js`, `command-controls.js`, `nautilus.js`, `lists.js`, `report-format.js`, `market-chart.js`, `app.css`, and `ui-*.css`).
- **Impeccable Playbooks Applied:** `shape`, `layout`, `distill`, `operate` (Operate mode).

---

## 1. Executive Summary & Argon Verdict

**Verdict: Conditional Pass — Revise Before Implementation.**

`docs/ui-redesign-blueprint.md` diagnoses the core usability problem accurately: the current UI buries data under 250–300px of stacked headers, explanatory prose, filter rows, and always-open management toolbars, while splitting "pick stocks" and "run research" across two different pages.

However, when stress-tested against the actual code in `tradingagents/web/static/app.js` and the non-negotiable product boundaries in `PRODUCT.md`, the blueprint has **four critical failure modes** that will break implementation if not corrected first:

1. **Nine Invented or Violated Backend Contracts:** Several wireframes in the blueprint either invent data the backend does not supply (such as a `Day P/L` top-bar metric, a Markets `Fundamentals` tab, structured analyst scorecard sub-fields, and a Strategy Lab `SMA Crossover / Win Rate` template) or violate `PRODUCT.md` safety rules (such as merging the session-only **AI Proposed Portfolio** with **Human Baskets** on Portfolio, and collapsing the 3-stage **Save Draft → Approve Revision → Submit** order state machine into a 2-step form).
2. **Silently Dropped Existing Capabilities:** By oversimplifying `Markets`, `Orders`, `Strategy Lab`, and `Settings`, the blueprint accidentally deletes UI paths for **Yahoo Screener**, **Saved Multi-Timeframe Scans**, **Alpaca Option Chains**, **Chart Studies/Formulas/Drawings/Comparison**, **Saved-Plan Simulations**, **10 Trading Policy Rules**, **Native Cache Table Captures**, and **Uncertain Order Recovery (`resolve_never_dispatched`)**.
3. **Hidden Chrome-Budget Math Failures:** Although Section 4 of the blueprint promises `<20%` vertical chrome (`~100–110px`), its own Research wireframe (Section 6.4) stacks a 2-line Global Top Bar (`64px`), a Workspace Bar (`40px`), a 2-line Launch & Progress Bar (`80px`), and a 2-line Detail Header + Tabs bar (`76px`) = **`260px` of vertical chrome** (`24%` on `1080p`, `29%` on `900p`), plus retains the `36px` bottom `.workspace-footer`.
4. **Incomplete Keyboard, Accessibility, and Error/Uncertainty States:** The wireframes do not specify how to fix the P0/P1 contradictions found in live walkthroughs (e.g., L3 red `Sell` badge next to `"No final recommendation is saved"`, L4 permanent `"Loading..."` banner on cancelled stocks, L5 stuck `"Rendering workflow..."` canvas, HTTP 400 raw error on unresearched Market charts, and timeout uncertainty on order submission/cancellation).

This review corrects all four failure modes and provides contract-true, pixel-budgeted wireframes and acceptance criteria for all 10 workspaces.

---

## 2. Industry Benchmark Deep-Dive: What the Blueprint Missed

We compared `docs/ui-redesign-blueprint.md` against the five reference platforms (**Fidelity Active Trader Pro**, **IBKR Desktop / TWS Mosaic**, **TradingView Desktop**, **Koyfin**, and **FinChat / Fiscal.ai**) to identify patterns the blueprint missed:

| Platform | Real Industry Pattern | What `docs/ui-redesign-blueprint.md` Got Right | What `docs/ui-redesign-blueprint.md` Missed or Got Wrong |
|---|---|---|---|
| **Fidelity Active Trader Pro (ATP)** | **Separation of "Viewed Symbol" vs. "Batch Selection" + Multi-Step Trade Armor Preview:** Single-clicking or selecting a symbol links the Quote, Chart, and Ticket to that symbol, without wiping out checked batch items. Order tickets require explicit Preview (showing exact terms, estimated cash impact, and warnings) before Approve/Place. | Linked symbol selection across Watchlist, Chart, Research, and Order Ticket. | **Conflated Viewed Symbol with Research Batch:** In `app.js`, `selectedSymbol` (the inspected stock) and `selectedSymbols` (the checked research batch) are intentionally separate (`docs/desk-reference.md`). The blueprint's Research picker must clearly show **Inspected Stock (`AMZN`)** vs. **Queued Batch (`3 stocks checked`)** so clicking a row to read its report never overwrites the batch selection. |
| **IBKR Desktop & TWS Mosaic** | **Single-Line Compact Quote Header + Integrated Sub-Workspaces:** Mosaic never uses separate pages for Watchlist, Screener, and Scanner; they live as instant view switches in one left/top rail while the right-hand Inspector (Chart, Option Chain, Order Book) stays docked. | 2-column split on Markets and Orders. | **Dropped Screener, Saved Scans, and Option Chain from Markets (6.3):** IBKR keeps `Watchlist / Universe`, `Market Screener`, and `Saved Scanners` as peer modes in Markets, and keeps `Chart`, `Options`, and `Position / Ticket` as tabs on the right-hand instrument pane. |
| **TradingView Desktop** | **Zero-Prose Chart Canvas + Collapsible Right Inspector Rail:** 85%+ of the right pane is the chart canvas. Studies, Drawings, Comparison, and Data Window open in a narrow collapsible right-side drawer (`280px`) only when clicked, and close to give 100% width back to the chart. | Full-height chart emphasis and 1-line backfill bar. | **Forgot the Existing `.chart-inspectors` Drawer (`ui-instrument.css`):** The desk already has a right-hand `.chart-inspectors` column (`Studies and formulas`, `Drawings`, `Comparison`, `Source data`) with `.inspector-closed` support! The Markets wireframe must show this collapsible inspector drawer instead of inventing a fake `[Fundamentals]` tab. |
| **Koyfin** | **Dense Tabular Scorecards + Signed Color Formatting + No Giant Empty Placeholders:** Financial tables use uniform tabular numerals, signed percentages (`+1.14%` green, `-0.85%` rose), sparkline/weight bars, and compact 1-line empty states. | Signed currency/P&L rules and compact empty states. | **Repeated 4 Giant KPI Cards on Portfolio (6.5):** Koyfin uses a single compact summary ribbon (`36–40px` tall) above holdings tables so the table gets maximum vertical rows, rather than repeating giant KPI boxes below an already-present Global Top Bar. |
| **FinChat (Fiscal.ai)** | **Provenance-First AI Research Layout:** AI research summaries separate **Verdict & Metadata** (date, model/workflow, source coverage) from **Structured Section Cards** and **Verifiable Source Links** (domain + date + receipt status). Never fabricates structured KPIs if the underlying artifact is prose. | Verdict strip above expandable Portfolio Manager report. | **Invented Structured Scorecard Fields (6.4):** FinChat grounds cards in actual stored artifacts. Since TradingAgents stores markdown reports (`market_report`, `fundamentals_report`, `news_report`, `sentiment_report`) plus structured `social_sentiment` (Laya) and `completion_gaps`, the 4 Analyst Cards must display **real stored status, first-paragraph thesis excerpt, and Laya/source counts**, not invented micro-metrics. |

---

## 3. Backend Reality Check: 9 Contract Violations in the Blueprint

Per `PRODUCT.md`: *"Do not add new backend features to justify UI changes; unsupported business actions are removed, not faked."* Every item below in `docs/ui-redesign-blueprint.md` conflicts with the actual backend/frontend data model and must be corrected in the wireframes:

### Violation 1: `Day P/L $0.00` in Global Top Bar (Blueprint 6.1)
- **What the blueprint drew:** `[PAPER DESK] Equity $100,000 Cash $100,000 Buying Power $100,000 Day P/L $0.00`
- **Actual backend contract (`app.js` lines 454, 2743):** `state.account` provides `equity`, `cash`, `buying_power`, and `long_market_value`, plus `positions_count` and `open_orders_count`. Live intraday `Day P/L` is not a field on `state.account` (historical P/L lives in saved account-history intervals under `state.history` / `journalCollections`).
- **Argon Correction:** Do not invent `Day P/L` in the header. Show the 5 real account figures (`Equity`, `Cash`, `Buying Power`, `Long Market Value`, `Positions / Open Orders`) in the compact `40px` Account Strip on Dashboard and Portfolio, and keep the Global Top Bar focused on connection identity, symbol search, quote/account timestamp, unread alerts, and order execution gate status.

### Violation 2: Mixing Human Baskets with AI Proposed Portfolio (Blueprint 6.5)
- **What the blueprint drew:** Portfolio tabs `[*Positions (0)*] [Proposed Basket (1)] [Performance]` with the note: *"On Proposed Basket, the top half shows the Human Basket vs. AI Portfolio Synthesis side-by-side with clear 'Stage to Orders' actions."*
- **Actual backend & product contract (`PRODUCT.md` & `app.js` lines 467, 480, 2792):**
  - **Portfolio → Proposed (`renderProposedPortfolio`)** is strictly the **session-only joint deep-model synthesis** (`POST /api/portfolio-model`) with its own `Model capital (USD)` input (default `$10,000`), eligible completed research inputs, explicit exclusions, target weights, deterministic whole-share rounding, and residual cash. `PRODUCT.md` explicitly mandates: *"Keep this session-only proposal separate from per-stock research, human baskets, historical simulation and broker authority."* It has **no** "Stage to Orders" button.
  - **Human Baskets (`#allocation-workspace`)** live in **Orders → Baskets** (`Targets`, `Impact`, `Drafts`, plus `basketCommandControls` for per-leg approval admission).
- **Argon Correction:** Keep **Portfolio → Proposed** (`[Proposed Model Portfolio]`) strictly for the session-only joint model synthesis, and keep **Human Baskets** in **Orders → Baskets**.

### Violation 3: Collapsing the 3-Stage Order Lifecycle & Dropping Recovery Controls (Blueprint 6.6)
- **What the blueprint drew:** A 2-step form (`Step 1: [Approve Exact Terms]`, `Step 2: [Submit to Alpaca Paper]`) with only basic Equity Limit fields.
- **Actual backend contract (`app.js` lines 2249–2340, `command-controls.js` lines 18–95):**
  1. **Stage 1 — Draft & Preview (`proposalEditor`):** Supports `us_equity` (whole or fractional up to 9 decimals), `us_option` (single-leg or 2–4 leg `mleg` atomic package), order types (`MARKET`, `LIMIT`, `STOP_MARKET`, `STOP_LIMIT`, `TRAILING_STOP_MARKET`), `DAY`/`GTC`, `regular`/`extended` session, linked exits (`Bracket`, `OTO`, `OCO`), historical chart price copy, and order replacement binding. Requires **Preview Impact** and **Save Draft Revision** (`proposal.revision`, `terms_sha256`).
  2. **Stage 2 — Check & Approve (`approvalPanel`):** Evaluates against the 10 investor policy rules (`#evaluate-approval` `Check order`), optional order-level constraints (`quote_max_age_seconds`, `approval_max_age_seconds`, `max_execution_price`, `max_fees`), and records single-use approval (`#record-approval` `Approve this order`) bound to `proposal_revision`, `terms_sha256`, and `policy_revision`.
  3. **Stage 3 — Admit & Submit / Manage (`commandControls`):** Separate `Submit these approved terms` (`data-approval-submit`), `Cancel selected order`, `Replace selected order with approved terms`, imported external broker order controls, and **`Check whether submit/cancel/replace was never sent` (`resolve_never_dispatched`)** when a command is in `outcome_unknown` / `submitting` / `cancel_pending` / `replace_pending`.
- **Argon Correction:** The Orders wireframe must preserve the 3 explicit stages (**1. Draft & Save Revision → 2. Check & Approve Exact Revision → 3. Submit Separately to Broker**), progressive-disclosure tabs/accordions for `Exits / Replacement / Options`, and the **Uncertain Command Reconciliation** controls.

### Violation 4: Erasing Strategy Lab's Two Engines (Blueprint 6.7)
- **What the blueprint drew:** `Template: [SMA Crossover v]`, `Fast / Slow: [10] / [50]`, and `Win Rate` metrics.
- **Actual backend contract (`app.js` lines 1020–1255, `docs/desk-reference.md`):** Strategy Lab has **two distinct evaluation engines** and **no** `Win Rate` or `SMA Crossover` preset:
  1. **Simulations (`strategyTab = 'simulations'`):** *Simulate a saved plan* — tests an exact saved human order proposal revision against a retained daily history receipt (`starting_cash`, `start_at`, `end_at`, `decision_basis`, `fee_usd`, `fee_per`, `limit_fill_probability`, `slippage_probability`, `random_seed`, `latency_ns`) via `Save simulation preview` → `Run this simulation`.
  2. **Experiments (`strategyTab = 'experiments'` & `'strategies'`):** *Walk-forward strategy experiments* — authors a declarative strategy (1–16 ALL/ANY entry/exit conditions over OHLC, 50/200 SMA, 10 EMA, MACD, RSI, Bollinger, ATR, VWMA, MFI + up to 8 finite parameters), configures rolling/expanding `train_sessions`, `validation_sessions`, `gap_sessions`, `oos_sessions`, `step_sessions`, Grid vs. Adaptive (`TPESampler`) search, objective (`net_return_pct`, `total_pnl`, `max_drawdown_pct`), `minimum_closed_trades`, budgets, and cost scenarios via `Save immutable experiment preview` → `Run this exact experiment`.
- **Argon Correction:** Strategy Lab wireframe must expose the two real engines (`[Saved-Plan Simulations]` and `[Walk-Forward Experiments]`) with a 3-step accordion in the left setup rail and real metrics (`Net Return %`, `Modeled P&L`, `Max Drawdown %`, `Closed Trades`, `Eligible Folds`) on the right.

### Violation 5: Dropping Markets Screener, Saved Scans, Options, and Chart Inspectors (Blueprint 6.3)
- **What the blueprint drew:** Only Watchlist + Chart, with fake right-pane tabs `[Chart] [Price Bars Table] [Fundamentals]` and `[1D] [1W] [1M] [1Y]`.
- **Actual backend contract (`app.js` lines 1510–2000, 2570–2615, 2840–2900):**
  - Top-level Markets modes: **Universe & Watchlists**, **Screener** (Yahoo Finance discovery + add to universe), and **Saved Scans** (`Definition`, `Runs`, `Matches` for multi-timeframe declarative programs).
  - Instrument right-pane tabs: **Chart** (with `Immutable saved research inputs` vs. `Current-market context · IEX cache`, intervals `1Min, 5Min, 15Min, 30Min, 1Hour, 1Day`, and collapsible right inspector for `Studies and formulas`, `Drawings`, `Comparison`, `Source data`), **Research** (saved report + disposition + order preparation), **Options** (Alpaca option contract query, `opra`/`indicative` feed subscription, chain table, and 2–4 leg package builder), and **Position** (held position + shared order ticket).
- **Argon Correction:** Restore all real Markets sub-workspaces and instrument tabs while applying the 1-line toolbar and collapsible inspector pattern so the chart still owns 75%+ of the right pane.

### Violation 6: Invented Analyst Scorecard Micro-Fields on Research Summary (Blueprint 6.4)
- **What the blueprint drew:** 4 Analyst Cards with structured lines like `Neutral-Bull | Above 50d SMA` and `Strong cash | AWS margins +`.
- **Actual backend contract (`app.js` lines 690–785):** `result.reports` contains markdown strings (`market_report`, `fundamentals_report`, `news_report`, `sentiment_report`, `investment_plan`, `trader_investment_plan`, `final_trade_decision`) plus `investment_debate_state`, `risk_debate_state`, `result.social_sentiment` (structured Laya counts), `result.local_laya_batch`, and `result.completion_gaps`.
- **Argon Correction:** Each Analyst Card in the Summary scorecard must render **deterministic data that actually exists in `result`**:
  - **Card Header:** Analyst name + status badge (`Saved` green / `Missing` rose / `Running` blue).
  - **Card Body:** First non-heading sentence/thesis line extracted from that markdown report (or `"Report not generated"` if absent), plus for **Sentiment**: actual Laya classification summary (`e.g., StockTwits: 14 Bullish · 4 Bearish · 9 Unclear`), and for **News / Fundamentals**: captured URL source count and any `completion_gaps` warning.
  - **Card Action:** Clicking the card switches to the `Reports` tab scrolled directly to that analyst's full markdown report.

### Violation 7: Dropping `Activity` Sub-Tab & Misrepresenting Run Progress in Research (Blueprint 6.4)
- **What the blueprint drew:** Sub-tabs `[*Summary*] [Bull vs Bear] [Analyst Reports (4)] [Sources (9)]` — dropping `Activity`!
- **Actual backend contract (`app.js` lines 725, 745):** `Activity` (`renderEvents(run)`) is the only place showing the timestamped event log (`run.events`), token compaction chunks, HTTP 429 retry waits, and JSON run export (`data-action="export-run"`), and `result.error` explicitly tells the user `"See Activity for details."`
- **Argon Correction:** Keep all 5 evidence tabs on the Research detail pane: **`[*Summary*] [Reports] [Debate & Risk] [Sources] [Activity]`**. Only `[Setup]` is removed (replaced by the top inline Launch Bar).

### Violation 8: Inventing a `[Shared Tools (22)]` Tab in Workflows (Blueprint 6.10)
- **What the blueprint drew:** `Tabs: [*Agent Prompt*] [Shared Tools (22)] [YAML]`.
- **Actual backend contract (`workflows.js` lines 160–195, 319):** The inspector has **two** tabs (`Prompts` and `Workflow YAML`). `Shared context and tools` and `Output schema fields` are `<optgroup>` categories inside `#workflow-prompt-select` and related-file chip groups inside `#workflow-node-detail` when an agent node is clicked. Also, CodeMirror does not bind `Ctrl+S` to `workflowAction('save')` yet unless explicitly added in `bindWorkflows()`.
- **Argon Correction:** Keep the two real tabs (`[*Prompts*] [Workflow YAML]`), show the **Selected Node's Related Files** (`Primary prompt`, `Shared context & tools`, `Output schema`) as a compact horizontal chip bar above the CodeMirror editor when a node is clicked, and add a real `Ctrl/Cmd+S` listener in `bindWorkflows()` as a UI keybinding improvement.

### Violation 9: Omitting `Trading Rules`, `Stock Universe CSV Editor`, and `Native Table Capture` in Settings (Blueprint 6.11)
- **What the blueprint drew:** 4 tabs (`AI Models & Engine`, `Broker & Data Keys`, `Safety & Order Gate`, `Backup & Recovery`), omitting the 1,000-symbol Stock Universe CSV editor, the 10 Investor Policy rules, and the Native Cached Table capture tool.
- **Actual backend contract (`app.js` lines 539–615, 905–985):** Settings has **5** categories: `Account`, `Research`, `Trading rules`, `Integrations`, and `Diagnostics`.
  - `Trading rules` contains the 10 portfolio/order risk rules (`cash_reserve_pct`, `max_position_pct`, etc.) AND `nativeEnginePanel()` (`Capture native table` for `orders`, `order_fills`, `fills`, `positions`, `account` — which `Journal → Position outcomes` requires!).
  - `Integrations` (or `Universe & Data Keys`) contains the Stock Universe editor (`name`, `universe` textarea, `Use FANGMAN`, `Import CSV / text`, `Export saved index`) and `Service API keys`.
- **Argon Correction:** Preserve all 5 Settings categories (`Account & Engine`, `Research & Models`, `Universe & Data Keys`, `Trading Rules & Native Cache`, `Diagnostics & Backup`), using progressive disclosure (`<details>`) inside each category to keep every view clean.

---

## 4. Duplicate Work & Tab Boundary Audit

We audited all 10 workspaces and their sub-tabs to ensure **every tab has one distinct job** and zero duplicate surfaces remain:

| Surface / Sub-Tab | Duplicate Work Found (Current UI & Blueprint) | Argon Consolidation Decision |
|---|---|---|
| **Global Top Bar vs. Page Headers (`pageHeader`)** | Current UI repeats `Account verified` badge, connection status, and multi-sentence descriptions at the top of every page below `.topbar`. Blueprint 6.1 + 6.5 repeats `Equity / Cash / Buying Power` in both the Global Top Bar and Portfolio KPI cards. | **Eliminate duplicate banners:** Global Top Bar (`40px`) owns connection/paper status, global symbol search, quote/account freshness, unread alerts count, and order execution gate pill. Account financial figures (`Equity`, `Cash`, `Buying Power`, `Long Value`, `Positions / Open Orders`) appear only in the `40px` Account Strip on **Dashboard** and **Portfolio**. |
| **Markets: `Watchlists` vs. `Universe` tabs** | In `app.js` (line 2847), clicking `Watchlists` or `Universe` renders the exact same `#markets-lists` DOM; only `#watchlist-discovery-members` changes visibility. | **Merge into one `Universe & Watchlists` tab:** A single `[Watchlist: All Universe (24) v]` dropdown in the left-pane toolbar switches between the full universe and any saved watchlist. Outside-universe watchlist symbols appear in a compact footer strip when a custom watchlist is active. |
| **Markets: `Saved calculations` vs. `Studies and formulas` chart inspector tabs** | In `app.js` (line 2582), the `Saved calculations` inspector tab contains only a placeholder paragraph and a button that switches to `Studies and formulas`. | **Remove the dummy `Saved calculations` tab:** Keep the 4 real chart inspector tabs: `Source & History`, `Studies & Formulas` (which already houses saved calculations), `Drawings`, and `Comparison`. |
| **Research: `Setup` sub-tab vs. Launch Toolbar** | In `app.js` (line 744), `Setup` is a 6th tab inside the right-hand stock report panel that hides the stock's report and tells the operator to go to Markets. | **Remove `Setup` sub-tab:** Promote stock selection + batch launch into the top `40px` **Research Launch Bar** on the Research page. The right-hand panel is 100% dedicated to inspecting the selected stock (`Summary`, `Reports`, `Debate & Risk`, `Sources`, `Activity`). |
| **Portfolio: `Performance` vs. Journal: `Account History`** | In `app.js` (line 489), `Portfolio → Performance` clones `accountHistoryWorkspace()` from `Journal → Account History` into a `<details>` block, duplicating the entire form and 3 tables. | **Split by job:** **Portfolio → Performance** shows the Equity/Returns chart, saved interval selector, and summary return metrics (TWR, Modified Dietz, Max Drawdown, Benchmark Excess Return) with a single `[Manage & Collect Intervals in Journal →]` button. **Journal → Account History** owns interval collection, benchmark history queueing, cash-flow classification tables, and SHA-256 receipts. |
| **Journal: `Decisions` vs. `Notes` tabs** | In `app.js` (line 1250), `Notes` renders a list of unformatted buttons above the exact same `.decision-inspector` already shown on `Decisions`. | **Merge into `Decisions & Notes`:** The master table on `Decisions & Notes` includes a `Note` indicator column and a `Has saved note` filter option; the right-hand `.decision-inspector` displays Rationale, Linked Orders/Outcomes, and the Operator Note editor in one place. |
| **Strategy Lab: `Saved strategies` top tab vs. `Experiments → Setup`** | In `app.js` (line 1236), `Saved strategies` is a top-level tab alongside `Simulations` and `Experiments`, even though strategies are only used by `Experiments`. | **Nest Strategy Authoring inside `Experiments`:** Top-level Strategy Lab mode switch has two clear modes: **`[Saved-Plan Simulations]`** and **`[Walk-Forward Experiments]`**. Inside `Walk-Forward Experiments`, Step 1 of the left setup rail is `Strategy Definition (Select saved or edit rules)`. |
| **Pause Orders Controls (Sidebar vs. Orders vs. Settings)** | Three different labels (`Pause execution`, `New orders not paused · manage`, `New orders unblocked`) and two side-by-side buttons (`Pause new orders` / `Resume new orders`) on Orders. | **Single state pill + single toggle button:** Everywhere in the app uses **`Orders: Active`** (green) or **`Orders: Paused`** (amber), with one context-appropriate action button (`[Pause New Orders]` when active, `[Resume New Orders]` when paused). |

---

## 5. Stress-Tested Personas, End-to-End Workflows & User Stories

### 5.1 Stress-Testing the Personas
The blueprint's three personas (**Alex — Daily Active Desk Operator**, **Jordan — Methodical Swing & Fundamental Researcher**, **Morgan — Workflow & Strategy Architect**) cover the core roles well, but miss two critical real-world operating states documented in `docs/local-desk-guide.md` and `docs/desk-reference.md`:
- **Alex's Multi-Asset & Recovery Reality:** Alex does not only place basic 10-share limit orders; Alex also uses **Human Baskets** (target weight/quantity allocation across multiple stocks), **Fractional share orders**, **Options / Bounded-risk spreads**, and must recover safely when a network timeout leaves an order submission or cancellation in **`outcome_unknown`**.
- **Jordan's Portfolio Synthesis Reality:** Jordan uses **Portfolio → Proposed** (`Model portfolio`) to run a joint deep-model synthesis over all completed research with a dedicated `$10,000` model capital budget, inspecting which universe stocks were **excluded** (e.g., cancelled/incomplete research or missing dated prices) before deciding whether to manually stage individual orders.

### 5.2 Four End-to-End Operator Workflows (Zero Dead Ends)

1. **Workflow A — Cold-Start / Morning Triage → Research → Order Staging (Alex):**
   - Open **Dashboard (`#overview`)** → Verify `Paper trading · Connected` and scan the 5-metric Account Strip (`40px`) + 4-panel grid (`Watchlist`, `OHLCV Chart`, `Saved Research`, `Positions & Open Orders`).
   - Click **Research (`#research`)** → In the top Launch Bar, click `[Select Unfinished (21)]` or pick symbols in `[+ Pick Stocks (2) v]` → Click **`[Run Research (2)]`** → Confirm the workload modal (`#research-dialog` showing concurrency, models, and median duration estimate) → Click **`[Start 2-stock research]`**.
   - Screen immediately selects the first active symbol, scrolls the left list to it, and updates the 4-color segmented progress bar (`Running 1 of 2 · 0 Completed · 0 Cancelled · 0 Failed`).
   - When completed, inspect the **Summary** tab (Verdict strip, 4 Analyst Cards, Debate & Risk synthesis) → Click **`[Prepare Order for AMZN →]`** → Lands in **Orders** with `AMZN` loaded in the ticket and linked to the exact research `run_id`, `revision`, and `result_sha256`.
2. **Workflow B — Joint AI Portfolio Synthesis vs. Human Basket Execution (Jordan & Alex):**
   - Open **Portfolio → Proposed (`#portfolio`)** → Enter `Model capital: $10,000` → Click **`[Model Portfolio]`**.
   - Review the session-only joint synthesis table (Target weight, Whole shares, Reference price, Rationale & entry conditions) and the **Excluded stocks (`21 excluded: research cancelled`)** disclosure.
   - To act on multiple stocks with real account equity, open **Orders → Baskets** → Add target weights/quantities → Click **`[Preview Basket Impact]`** → **`[Save Basket & Create Linked Proposals]`** → Approve each leg individually and submit via **`[Submit Next Approved Leg]`**.
3. **Workflow C — Order Preparation → Exact Approval → Submission → Uncertain Outcome Recovery (Alex):**
   - In **Orders (`#orders`)**, enter ticket terms → Click **`[Preview Impact]`** → Click **`[Save Draft Revision]`**.
   - In the Approval step, click **`[Check Order]`** (verifies the 10 investor policy rules and quote freshness) → Click **`[Approve This Order]`**.
   - In the Submission step, click **`[Submit Approved Order]`** → Review inline confirmation (`Send BUY 10 AMZN LMT $252.00 DAY to Alpaca Paper?`) → Click **`[Confirm & Send]`** → Inline receipt displays timestamp and Broker Order ID.
   - *If a network timeout occurs during Submit/Cancel/Replace:* Status badge turns Amber/Rose (`Submission outcome unknown · Refresh to reconcile`), duplicate Submit is blocked, and operator clicks **`[Refresh Account & Order Status]`** or **`[Check Whether Submit Was Never Sent]`**.
4. **Workflow D — Workflow Prompt Tuning → Historical Evaluation in Strategy Lab (Morgan):**
   - Open **Workflows (`#workflows`)** → Click **`[Fit All]`** (`35%` zoom floor) to view all 18 nodes → Click `Market Analyst` node on the canvas → Edit `prompts/market_analyst.md` in CodeMirror → Press `Ctrl+S` (or click `[Save]`) → Click **`[Use for New Research]`**.
   - Open **Strategy Lab (`#strategy`)** → Choose **`[Saved-Plan Simulations]`** or **`[Walk-Forward Experiments]`** → Click **`[Load Saved Plans & Data]`** → Complete the 3-step left-rail setup → Click **`[Save Preview]`** → Click **`[Run Simulation / Experiment]`** → Inspect the OOS Equity Curve,Accessible Table View, and Fold Comparison on the right canvas.

### 5.3 Refined & Expanded User Stories (`US-01` to `US-18`)

We retain `US-01` through `US-12` from `docs/ui-redesign-blueprint.md` with contract-true acceptance criteria corrections, and add **`US-13` through `US-18`** to cover the missing capabilities:

| ID | Persona | User Story | Refined Acceptance Criteria (Grounded in `app.js` & `PRODUCT.md`) |
|---|---|---|---|
| **US-01** | Alex | Pick stocks and run research directly on **Research**. | Research Launch Bar binds directly to `selectedSymbols` (the shared research batch Set) with `[+ Pick Stocks (N) v]`, `[Select All Universe]`, `[Select Unfinished]`, `[Clear]`, and `[Run Research (N)]` opening `#research-dialog`. Clicking a row in the left list changes `selectedSymbol` (inspected stock) without overwriting `selectedSymbols`. |
| **US-02** | Alex | Auto-focus the first active stock when research starts. | `launchResearch(symbols, revision)` sets `selectedSymbol = symbols[0]`, sets `researchTab = 'summary'`, scrolls `.research-rows` to `symbols[0]`, and shows live stage/event status from `run.events`. |
| **US-03** | Jordan | Honest segmented progress bar and badges on Research. | Replaces single-color `<progress>` with a segmented bar (`completed` green, `incomplete` amber, `running`/`queued` blue, `cancelled`/`interrupted` neutral slate, `failed` rose) and explicit counts (`3 completed · 21 cancelled`). |
| **US-04** | Jordan | Structured Research Summary grounded in real report artifacts. | Summary tab renders: (1) Verdict Strip (`result.rating` badge **only** when `status === 'completed'` and `final_trade_decision` exists; otherwise `Cancelled — No final recommendation` or `Incomplete`), (2) 4 Analyst Cards (`Market`, `Fundamentals`, `News`, `Sentiment`) showing saved status, extracted first thesis sentence, and real Laya/source counts, (3) Debate & Risk summary cards from `investment_debate_state` and `risk_debate_state`, (4) Disposition & Note bar, and (5) collapsible full `final_trade_decision` markdown. |
| **US-05** | Alex | 80%+ data / <20% chrome on every workspace. | Remove `.workspace-footer` (`36px`), cap Global Top Bar at `40px` (single line), cap Workspace Bar at `40px` (Title + `role="tablist"` + right actions on one row), cap `#main` padding at `8px 12px 12px`. Verified `≥86%` vertical data height on `1080p`. |
| **US-06** | Alex | One-click handoff from Research to Order preparation. | Clicking `[Prepare Order for SYMBOL]` calls `UniverseReview.openProposal(selectedSymbol, button, resultContext)` and navigates to `#orders` with `selectedSymbol` and research provenance pre-linked. |
| **US-07** | Alex | Unclipped Dashboard grid with honest empty & chart states. | At `≥1101×801`, Dashboard renders the `40px` 5-KPI Account Strip above a 2-row grid (`Watchlist` + `Chart` top row; `Saved Research` + `Positions` + `Open Orders` bottom row). Empty states use max 2 lines + 1 button so `322px` boxes never clip. Watchlist opens with `0` rows checked on new sessions or >50 universe (`ui-scale-research.md`). |
| **US-08** | Alex | Full-height Markets workspace with Screener, Scans, Options, and 1-line history bar. | Markets Workspace Bar switches between `[Universe & Watchlists]`, `[Yahoo Screener]`, and `[Saved Scans]`. In `Universe & Watchlists`, the left pane (`34%`) holds the table and collapsed `[Manage]` / `[Filters]` popovers; the right pane (`66%`) holds the Instrument (`Chart`, `Research`, `Options`, `Position`) with a 1-line IEX backfill bar and collapsible right-hand Chart Inspector (`Studies & Formulas`, `Drawings`, `Comparison`, `Source Data`). |
| **US-09** | Alex | 3-stage Order lifecycle, readiness visibility, and inline confirm/receipt. | Orders always shows the 1-line Readiness status at the top. Left pane (`42%`) guides `1. Draft & Save Revision → 2. Check & Approve → 3. Submit`. Right pane (`58%`) shows `Open Broker Orders`, `Saved Proposals & Baskets`, and `Command History & Receipts`. Submit/Cancel/Replace require an inline confirm step and render a timestamped receipt or uncertain-outcome recovery bar. |
| **US-10** | Morgan | Full-height Workflows diagram with true `Fit All` and 1-click node prompt editing. | `workflowFitDiagram()` supports both `Fit All` (`Math.min(widthRatio, heightRatio)` with `0.25` floor so the entire `1755px`-tall graph fits in one view) and `Fit Width`. Clicking any node loads its primary prompt in CodeMirror and shows its related files (`Shared context`, `Output schema`) as a 1-line chip bar. `Details` popover closes on `Escape` and outside click. |
| **US-11** | Morgan | Two-engine Strategy Lab (`Simulations` & `Experiments`) with 3-step left rail. | Strategy Lab switches between `[Saved-Plan Simulations]` and `[Walk-Forward Experiments]`. Left rail (`360px`) uses a 3-step accordion (`1. Plan/Strategy & Data`, `2. Window, Folds & Assumptions`, `3. Preview & Run`) with a concise 2-line model disclaimer. Right pane (`flex: 1`) shows `Preview & Results` (Equity Curve + Accessible Table + Fold/Trial tables) and `Runs & Compare`. |
| **US-12** | Jordan | Plain English labels, human-readable quote ages, and collapsed technical records. | Replace `human_proposal`, `needs_review`, `STOP_LIMIT`, `bounded_risk_spread_v1`, and `24989s old` with `Human proposal`, `Needs review`, `Stop limit`, `Bounded-risk option spreads`, and `6h 56m old (Market closed)`. Move raw JSON and SHA-256 hashes into `<details><summary>Technical record</summary>`. |
| **US-13** | Jordan | Separate Session-Only AI Proposed Portfolio vs. Human Baskets. | `Portfolio → Proposed` (`renderProposedPortfolio`) clearly states `Session-only joint model synthesis ($10,000 default model capital; separate from broker cash and human baskets)` and displays `Eligible stocks (3)` vs. `Excluded stocks (21)` side-by-side. Human Baskets remain in `Orders → Baskets`. |
| **US-14** | Alex | Safe recovery from uncertain order submission, cancellation, or replacement. | When `mutationUncertain()` is true or a command is in `outcome_unknown` / `submitting` / `cancel_pending` / `replace_pending`, Orders displays a persistent warning banner blocking duplicate sends and offering `[Refresh Account & Order Status]` and `[Check Whether Command Was Never Sent]`. |
| **US-15** | Jordan | Accessible keyboard navigation and chart text alternatives across all 10 pages. | All tab bars use `role="tablist"` / `role="tab"` / `role="tabpanel"` with `ArrowLeft`/`ArrowRight`/`Home`/`End` roving tabindex and `≥36px` height. Every SVG chart (Dashboard OHLCV, Portfolio Performance, Strategy Lab OOS Curves, Journal Equity) includes a color-blind-safe legend (hollow down-candles, dashed/dotted multi-series) and a 1-click `<details><summary>View chart data table</summary>` alternative. |
| **US-16** | Jordan | Safe guards on unsaved notes, settings, credentials, and workflow edits. | In Journal, `[Revert Unsaved Edits]` is disabled when clean and requires inline confirmation showing the count of unsaved notes when dirty. Leaving dirty Settings, Credentials, or Workflows opens an in-app `<dialog>` (`Discard changes` / `Keep editing`) instead of native browser `confirm()`. |
| **US-17** | Alex | Complete Settings organization preserving Trading Rules and Native Cache capture. | Settings organizes all existing controls into 5 tabs: `Account & Engine` (includes `Start/Stop Nautilus` and execution profile), `Research & Models` (Basic 5 fields + `<details>` Advanced 11 fields + Model Limits), `Universe & Data Keys` (1,000-stock CSV import/export + Service API keys), `Trading Rules & Native Cache` (10 policy rules + `Capture native table`), and `Diagnostics & Backup` (Health chips separated from Danger Zone Restore). |
| **US-18** | Alex | Local Laya 5-post screening and social provenance inspection. | In `Research → Reports → Social sentiment`, the `[Screen 5 saved posts locally]` action and Laya status (`Ready on CPU/GPU`) remain accessible with a 1-line explanation, and stance counts clearly distinguish `Bullish`, `Bearish`, `Neutral`, `Unclear`, `Off topic`, and `Unscreened`. |

---

## 6. Pixel-Verified 80/20 Screen Real-Estate Budget

### 6.1 Why Blueprint 6.4 Failed the Math Check (and How We Fix It)
In `docs/ui-redesign-blueprint.md`, the Global Top Bar (2 lines = `64px`) + Workspace Header (`40px`) + 2-line Launch Bar (`80px`) + 2-line Detail Header/Tabs (`76px`) consumed **`260px` of vertical height** (`24%` of `1080px` and `29%` of `900px`).

To guarantee **>80% data area** (`<20%` chrome) at both **`1920×1080`** and **`1440×900`**, we enforce five structural rules:
1. **Remove `.workspace-footer` (`36px` saved globally):** Move `Snapshot market data · USD` into the Global Top Bar freshness readout.
2. **Single-Line `40px` Global Top Bar:** Never wraps to two lines on desktop (`≥1100px`).
3. **Single-Line `40px` Workspace Header Bar:** Combines the Workspace `<h1>` Title, the primary `role="tablist"` sub-tabs, and the primary right-aligned action on **one `40px` row** (eliminating separate `.page-heading` + `.view-tabs` + `.run-toolbar` stacks).
4. **Compact `#main` Padding:** `8px` top, `12px` inline, `12px` bottom (`20px` vertical total, down from `69px` in `app.css`).
5. **Contextual Strips Capped at `38px` (1 Line):** Only pages that need a secondary strip (Dashboard 5-KPI Account Strip, Research Active Run Strip, Portfolio 5-KPI Account Strip, Orders Readiness Strip) add a single `38px` bar.

### 6.2 Measured Viewport Budget Table (`1920×1080` and `1440×900`)

| Workspace | Global Top Bar | Workspace Header + Tabs Bar | Contextual Strip (if any) | Inner Pane Header | `#main` Vertical Padding | Total Vertical Chrome (`px`) | Data Height on `1080p` (`%` Data) | Data Height on `900p` (`%` Data) |
|---|---|---|---|---|---|---|---|---|
| **1. Dashboard** | `40px` | `40px` | `40px` (5-KPI Account Strip) | `36px` per row (`×2` = `72px`) | `20px` | **`212px`** (`140px` shell + `72px` pane headers) | **`868px` (80.4% Data / 87.0% Ex-Pane-Headers)** | **`688px` (76.4% / 84.4% Ex-Pane-Headers)** |
| **2. Markets** | `40px` | `40px` (Title + 3 Mode Tabs) | `0px` (merged into pane toolbars) | `40px` (1-line Search/View or Quote/Tabs) | `20px` | **`140px`** | **`940px` (87.0% Data)** | **`760px` (84.4% Data)** |
| **3. Research** | `40px` | `40px` (Title + Launch Picker + Run Button) | `32px` (1-line Segmented Run Progress) | `40px` (Stock Title + 5 Sub-tabs on 1 row) | `20px` | **`172px`** | **`908px` (84.1% Data)** | **`728px` (80.9% Data)** |
| **4. Portfolio** | `40px` | `40px` (Title + 3 Sub-tabs + Refresh) | `40px` (5-KPI Account + Reconciliation Strip) | `36px` (Table header) | `20px` | **`176px`** | **`904px` (83.7% Data)** | **`724px` (80.4% Data)** |
| **5. Orders** | `40px` | `40px` (Title + Order Gate Pill + Pause Toggle) | `34px` (1-line Readiness & Blockers Strip) | `38px` (Ticket / Blotter Sub-tabs) | `20px` | **`172px`** | **`908px` (84.1% Data)** | **`728px` (80.9% Data)** |
| **6. Strategy Lab** | `40px` | `40px` (Title + `[Simulations]`/`[Experiments]` + Disclaimer) | `0px` | `38px` (Setup Header / Results Sub-tabs) | `20px` | **`138px`** | **`942px` (87.2% Data)** | **`762px` (84.7% Data)** |
| **7. Journal** | `40px` | `40px` (Title + 3 Sub-tabs + Revert/Export) | `0px` | `38px` (1-line Search/Filter bar) | `20px` | **`138px`** | **`942px` (87.2% Data)** | **`762px` (84.7% Data)** |
| **8. Alerts** | `40px` | `40px` (Title + 3 Sub-tabs + Freshness Setup Pill) | `0px` | `38px` (Inbox Filter / Template Picker) | `20px` | **`138px`** | **`942px` (87.2% Data)** | **`762px` (84.7% Data)** |
| **9. Workflows** | `40px` | `40px` (Title + Workflow Select + Save/Preview/Activate) | `0px` | `38px` (Zoom Controls / `[Prompts]` `[YAML]` Tabs) | `20px` | **`138px`** | **`942px` (87.2% Data)** | **`762px` (84.7% Data)** |
| **10. Settings** | `40px` | `40px` (Title + 5 Category Tabs + Save/Discard) | `0px` | `0px` (Direct section headers inside scroll pane) | `20px` | **`100px`** | **`980px` (90.7% Data)** | **`800px` (88.9% Data)** |

*Horizontal Budget:* Left navigation sidebar is reduced from `216px` (`29px` top padding, `48px` brand margin) to **`184px`** with compact `36px` nav items (icons + labels + unread badges for Orders and Alerts), leaving **`1736px` (`90.4%` of width)** on `1920×1080` and **`1256px` (`87.2%` of width)** on `1440×900`.

---

## 7. Keyboard, Accessibility (WCAG 2.2 AA), and Error/Uncertainty State Matrix

Every wireframe in Section 8 implements the following mandatory interaction, accessibility, and error-handling states:

### 7.1 Keyboard & ARIA Accessibility Contract
1. **Standardized WAI-ARIA Tablists (`role="tablist"`):**
   - Replace every `aria-pressed` tab bar (`categoryTabs`, `workspaceTabs`, `instrument-tabs`, `orders-tabs`, `basket-tabs`, `scan-tabs`, `dashboard-tabs`, `alert-evidence-tabs`, `broker-inspector-tabs`) with a single shared helper `renderTablist(groupId, label, tabs, activeId)`:
     - Container: `<div role="tablist" aria-label="...">`
     - Each tab: `<button role="tab" id="tab-..." aria-selected="true|false" aria-controls="panel-..." tabindex="0|-1">`
     - Each panel: `<section role="tabpanel" id="panel-..." aria-labelledby="tab-..." tabindex="0">`
     - Keyboard handler: `ArrowLeft` / `ArrowRight` moves focus and activates adjacent tab (wrapping at ends); `Home` / `End` jumps to first/last tab.
     - Visual state (`DESIGN.md`): Active tab uses `--nav-active-surface` (`#203329`), `--nav-active-text` (`#a5e7bd`), `600` weight, and a `2px solid var(--accent)` bottom indicator; hover uses `--quiet-hover-surface` (`#2c3c48`) so hover never overpowers the active tab. Minimum height `36px` (`44px` in Workflows).
2. **Chart Accessibility & Color-Blind Safety:**
   - **Up vs. Down Candles (`stockChart` & `market-chart.js`):** Up candles (`b.c >= b.o`) use solid fill `--positive` (`#7bd5a2`); Down candles (`b.c < b.o`) use **hollow fill (`var(--paper)`) with `1.5px` stroke `--down-candle` (`#dc8c96`)** so direction is unmistakable without color vision.
   - **Overlay & Series Legends:** Every chart with overlays (Dashboard SMA/EMA, Strategy Lab multi-fold OOS curves) renders a visible inline legend above/below the SVG pairing color swatches with stroke patterns (`solid`, `dashed 6 3`, `dotted 2 2`).
   - **Keyboard/Screen-Reader Data Table Toggle:** Every SVG chart is accompanied by a `<details class="chart-table-disclosure"><summary>Recent bars / series table (N rows)</summary>...</details>` so keyboard and screen-reader users can read exact OHLCV or equity values without hovering `<title>` tags.
3. **Focus Restoration & Escape Handling:**
   - All `<dialog>` modals (`#order-dialog`, `#research-dialog`, `#unsaved-changes-dialog`) and all floating `<details>` popovers (`.workflow-flow-details`, `.workflow-details`, `.workflow-yaml-guidance`, `#column-picker`, `[Manage]` popovers) close on `Escape` and outside click, and restore focus to their `<summary>` or trigger button.
   - Closing `#stock-detail` (`Back to list` or `Escape`) or `#alert-occurrence-evidence` (`Close saved evidence` or `Escape`) restores focus to the row button that opened it (`returnFocus.focus()`).
4. **Polling & Input Stability:**
   - Search inputs (`#decision-search`, `#stock-search`, `#watch-search`, `#research-search`) filter rows in place without replacing the `<input>` DOM node, preventing focus or cursor loss while typing.

### 7.2 Error, Empty, Loading & Uncertainty State Matrix

| Workspace | Trigger / Condition | Required UI State & Recovery Action |
|---|---|---|
| **Global Shell** | `stateErrorMessage` or `!state.connection.connected` | Top bar shows `[● Disconnected · Last snapshot HH:MM]` in amber/rose; `#notice` banner shows 1-line cause + `[Start Nautilus in Settings]` or `[Retry Refresh]` button. Never wipes out cached research/journal reading. |
| **Global Shell** | HTTP `429` Rate Limit (`coolingDown(path)`) | Inline status shows `Rate limited (HTTP 429) · Retry available at HH:MM:SS` with countdown/timestamp; unrelated workspaces remain interactive. |
| **Dashboard** | `positions().length === 0` or `orders().length === 0` | Compact 2-line empty state inside the bottom panel (`No open positions in Alpaca Paper · Cash $100,000.00` + `[Browse Markets]`). Fits inside `180px` panel height with zero clipping (fixes L1). |
| **Markets** | Selected stock has no saved research and chart mode defaults to `saved` (causes raw `HTTP 400` in current UI) | If `!DATA.research[symbol]`, default chart mode to `current` (`Current-market IEX cache`). If user explicitly selects `Immutable saved research inputs` when none exist, show friendly empty state: `No saved research bars for [SYMBOL]. [Switch to Current IEX History] or [Run Research]`. |
| **Markets** | No cached current-market bars (`!cached?.key`) | Show 1-line inline banner above chart area: `No cached 1Day bars for [SYMBOL] · [Fetch 252-Day Baseline] [Custom Range ▾]` (replaces 10-field wall). |
| **Research** | Run cancelled / stopped before `final_trade_decision` (Critique L3 & L4) | **Never** show a `Sell`/`Buy` badge when `!result?.reports?.final_trade_decision`. Show neutral slate badge `[Cancelled — No Verdict]`. Clear `"Loading the selected stock's research reports..."` immediately when `['cancelled','failed','interrupted'].includes(result.status)` and `!result.reports`, replacing it with: `Stopped before reports were generated · [Select Unfinished & Retry]`. |
| **Research** | Partial completion gaps (`result.completion_gaps.length > 0`) | Status badge shows amber `[Incomplete]`; Verdict Strip shows 1-line amber warning: `Incomplete coverage: [gaps] · Excluded from joint portfolio synthesis`. |
| **Portfolio** | `Performance` tab has `< 2` saved equity points (Critique L2) | Cap empty state card at `140px` height (`24px` icon max). Show: `Needs at least 2 saved account-history captures to plot performance.` + visible primary button **`[Collect Account History in Journal →]`**. |
| **Orders** | Submit, Cancel, or Replace timeout (`outcome_unknown`, `mutationUncertain()`) | Display persistent Amber/Rose **Uncertain Outcome Banner** at top of Orders: `Order command timed out — broker outcome is unknown. Do not resend.` Disable new Submit buttons and surface **`[Refresh Account & Order Status]`** + **`[Check Whether Command Was Never Sent]`**. |
| **Orders** | Button disabled (`Approve`, `Submit`, `Run`) | Always render a 1-line inline reason immediately beside/below the disabled button (e.g., `Disabled: Save draft revision before approving`, or `Blocked: Quote is 7h 31m old (limit 60s) · [Refresh Quotes]`). |
| **Workflows** | Mermaid render race or failure (Critique L5) | If `w.tools === 'loading'`, show skeleton pulse `Loading diagram engine...`. Once `w.tools === 'ready'`, use `requestAnimationFrame` + container size check before `renderDiagram()`. If Mermaid throws, show error box + **`[Retry Diagram Render]`** button instead of sticking on `"Rendering workflow..."`. |
| **Journal / Workflows / Settings** | User clicks `Reload`, `Discard`, or navigates away with unsaved edits | Replace native `window.confirm()` and unguarded 1-click discard buttons with an in-app confirmation bar or `<dialog>`: `Discard N unsaved edits to [Surface]? [Discard Edits] [Keep Editing]`. |

---

## 8. Refined, Contract-True Wireframes (All 10 Workspaces)

### 8.1 Global Shell (`index.html` — `40px` Single-Line Top Bar, No Footer)

- **Fixes over Blueprint 6.1:** Single `40px` top bar (no 2-line wrap), removes `.workspace-footer` (`+36px` vertical data height), removes fake `Day P/L`, adds distinct icons for all 10 left-nav items (Critique L7), and standardizes `"Orders: Active"` / `"Orders: Paused"` wording across Sidebar, Top Bar, Orders, and Settings (Critique L6, L14).

```text
+----------------------------------------------------------------------------------------------------------+
| TradingAgents | PNIS / Research  [● Paper Verified]   [Find symbol: AMZN___]   Quotes 16:00 ET [Refresh] |
| Paper Desk    |                                                      [🔔 Alerts: 1] [Orders: Active · ▾] |
+---------------+------------------------------------------------------------------------------------------+
| [⊞] Dashboard | WORKSPACE BAR (40px): Page Title · [Role="tablist" Sub-Tabs] · Right-Aligned Action      |
| [📈] Markets  +------------------------------------------------------------------------------------------+
| [🔬] Research*|                                                                                          |
| [💼] Portfolio|                                                                                          |
| [🧾] Orders(1)|                           DATA CANVAS (84% – 91% OF HEIGHT)                              |
| [🧪] Strat Lab|                   • Zero multi-paragraph prose banners above tables                      |
| [📓] Journal  |                   • Single independent scrollbar per column                              |
| [🔔] Alerts(1)|                   • All tabs use role="tablist" + ArrowLeft/ArrowRight                   |
| [🕸] Workflows|                                                                                          |
| [⚙] Settings  |                                                                                          |
| ------------- |                                                                                          |
| ● Nautilus OK |                                                                                          |
| ● Laya CPU OK |                                                                                          |
| ● Market Closd|                                                                                          |
+---------------+------------------------------------------------------------------------------------------+
```

**Distinct 10-Icon Map (`iconPaths` in `app.js`, fixing L7):**
1. `overview` (Dashboard): 2×2 grid (`M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z`)
2. `markets` (Markets): Candlesticks (`M7 4v16M5 8h4v6H5zM17 3v18M15 7h4v8h-4z`)
3. `research` (Research): Microscope / lens (`M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16-4.35-4.35`)
4. `portfolio` (Portfolio): Briefcase (`M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m-13 0h18v13H3z`)
5. `orders` (Orders): Clipboard / check (`M8 3h8v4H8zM8 5H5v16h14V5h-3m-7 9 2.5 2.5L16 12`)
6. `strategy` (Strategy Lab): Sliders / flasks (`M4 21v-7m0-4V3m8 18v-9m0-4V3m8 18v-5m0-4V3M1 14h6m2-6h6m2 8h6`)
7. `journal` (Journal): Book / ledger (`M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5z`)
8. `alerts` (Alerts): Bell (`M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0`)
9. `workflows` (Workflows): Connected graph nodes (`M6 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm12 8a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM6 13a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm2.6-6.5 6.8 8m-6.8 0 6.8-8`)
10. `settings` (Settings): Gear / sliders (`M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zm0-5v2m0 14v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M3 12h2m14 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41`)

---

### 8.2 Dashboard (`#overview`) — 5-KPI Strip + Unclipped Linked Grid

- **Fixes over Blueprint 6.2:**
  - Uses the **5 actual backend account values** (`Equity`, `Cash`, `Buying Power`, `Long Market Value`, `Open Orders`).
  - Separates **Inspected Symbol (`AMZN`)** from **Research Batch Checkboxes (`0 checked` by default — fixing Critique Dashboard P2 where all 24 rows started checked)**.
  - Adds **hollow down-candles** (`□`) vs. solid up-candles (`■`), a **visible SMA/EMA overlay legend**, and a `<details>` **Recent OHLCV Bars Table** (fixing Critique Dashboard P1).
  - Keeps bottom row (`Saved Research`, `Positions`, `Open Orders`) compact so buttons never clip in a `322px`-high box (fixing Critique L1).

```text
+----------------------------------------------------------------------------------------------------------+
| DASHBOARD · Account observed Oct 28, 20:35 ET               [Run Research (0)] [Open Portfolio ->]       |
+----------------------------------------------------------------------------------------------------------+
| EQUITY $100,000.00 | CASH $100,000.00 | BUYING POWER $100,000.00 | LONG VALUE $0.00 | OPEN ORDERS 0      |
+--------------------------------------------------+-------------------------------------------------------+
| WATCHLIST: PNIS (24)          [Update Quotes]    | AMZN · $252.51 (+1.14%) · IEX 16:00 ET (Closed)       |
| [Search...] [Show: All (24) v] [Batch: 0 ▾]      | Period: [1W] [*1M*] [3M] [6M]       [Open in Markets] |
+--------------------------------------------------+-------------------------------------------------------+
| [ ] SYM    LAST      CHG%    RESEARCH   QUOTE AGE| Legend: ■ Up  □ Down  — SMA20 ($248.10) - - SMA50     |
| [ ] AMZN * $252.51   +1.14%  [Hold]     Closed   |  260 |          .|.                                   |
| [ ] INTC   $22.40    -0.85%  [Underwt]  Closed   |  255 |      .|. |■|  .|.                              |
| [ ] TER    $108.12   -1.40%  [Sell]     Closed   |  250 |  .|. |□|      |■|                              |
| [ ] AAPL   $231.10   +0.42%  Cancelled  Closed   |  245 |________________________________________________|
| [ ] GOOGL  $182.30   -0.12%  Cancelled  Closed   |  Vol |  ||  |||  ||  ||||   Source: Saved 1Day (IEX)  |
| [ ] META   $590.40   +1.85%  Cancelled  Closed   | [▸ Recent OHLCV bars table (22 sessions)]             |
| 1–24 of 24                   Rows: [25v] [<] [>] |                                                       |
+-------------------------------+------------------+-----------------------------------+-------------------+
| SAVED RESEARCH: AMZN          | POSITIONS (0)                    | OPEN ORDERS (0)                       |
+-------------------------------+----------------------------------+---------------------------------------+
| [HOLD] · Trade date Oct 28    | No open positions in Alpaca.     | No open orders waiting at Alpaca.     |
| "Maintain existing exposure;  | Broker holdings & unrealized P/L | Staged proposals: 1 draft (SGOV)      |
|  watch AWS margin & capex..." | appear here when held.           |                                       |
| [Read Report] [Prepare Order] | [Browse Markets]                 | [Open Orders & Drafts (1)]            |
+-------------------------------+----------------------------------+---------------------------------------+
```

---

### 8.3 Markets (`#markets`) — Universe/Watchlists, Screener, Saved Scans & Full Instrument Studio

- **Fixes over Blueprint 6.3:**
  - Restores the **3 real Markets modes** in the top Workspace Bar: `[*Universe & Watchlists (24)*]`, `[Yahoo Screener]`, `[Saved Scans (0)]` (merging the duplicate `Watchlists` and `Universe` tabs into one).
  - Restores the **4 real Instrument tabs** on the right pane: `[*Chart*]`, `[Research]`, `[Options]`, `[Position & Ticket]`.
  - Shows the **collapsible right-hand Chart Inspector drawer** (`[Studies & Formulas]`, `[Drawings]`, `[Comparison]`, `[Source Data]`) and the **Chart Evidence Context switcher** (`[Context: Current IEX Cache v]` vs. `Immutable Saved Research Inputs`), preventing the raw `HTTP 400` error when viewing unresearched stocks!
  - Hides duplicate `AMZN / AMZN` company subtitle when `companyName(symbol) === symbol` (fixing Critique L13).

```text
+----------------------------------------------------------------------------------------------------------+
| MARKETS   Mode: [*Universe & Watchlists (24)*] [Yahoo Screener] [Saved Scans]     [Run Research (0) ->]  |
+----------------------------------------+-----------------------------------------------------------------+
| List: [All Universe: PNIS (24) v]      | AMZN · $252.51 (+1.14%) · Bid $252.40 / Ask $252.60 · Closed    |
| [Search...] [View: All v] [Sortv] [Ed] | Tabs: [*Chart*] [Research] [Options] [Position & Ticket]        |
+----------------------------------------+-----------------------------------------------------------------+
| SYM     PRICE    CHG%   AGE     RATING | Context: [Current IEX Cache v]  Interval: [*1Day*] [1Hr] [15m]  |
| AMZN *  $252.51  +1.14% Closed  [Hold] | Tools: [Studies & Formulas] [Drawings] [Comparison] [Source ▾]  |
| INTC    $22.40   -0.85% Closed  [Undwt]| +-------------------------------------------------------------+ |
| TER     $108.12  -1.40% Closed  [Sell] | | Banner: 1,255 daily bars cached (Oct 28) · [Fetch/Refresh]  | |
| AAPL    $231.10  +0.42% Closed  Canceld| +-------------------------------------------------------------+ |
| GOOGL   $182.30  -0.12% Closed  Canceld| |                                                             | |
| META    $590.40  +1.85% Closed  Canceld| |             FULL-HEIGHT LIGHTWEIGHT CHART                   | |
| MSFT    $428.15  +0.33% Closed  Canceld| |        (Hollow down-candles, volume, drawings,              | |
| NVDA    $141.80  +2.10% Closed  Canceld| |         and 1-click "Copy price to ticket" anchor)          | |
| ...                                    | |                                                             | |
| (Clicking [Ed] opens inline toolbar:   | |                                                             | |
|  checkboxes, [+ New Watchlist],        | +-------------------------------------------------------------+ |
|  [Select Filtered], [Columns ▾])       | [▸ Selected bar readout & OHLCV table (a11y / keyboard)]        |
+----------------------------------------+-----------------------------------------------------------------+
```

*(When `[Yahoo Screener]` is selected in the top tablist: Left rail (`300px`) shows Sector, Price, Market Cap, Volume criteria + `[Run Current Screen]`; Right pane (`flex: 1`) shows the 25-row provider results table with `[Inspect]` and `[Add to Configured Universe]`. When `[Saved Scans]` is selected: Left rail (`260px`) lists saved scan definitions; Right pane shows `[Definition]`, `[Runs]`, and `[Matches]` sub-tabs.)*

---

### 8.4 Research (`#research`) — Inline Stock Picker, Segmented Run Bar & Contract-True Summary

- **Fixes over Blueprint 6.4:**
  - Fits the **Launch Picker** into the `40px` Workspace Bar and the **Segmented Run Progress** into a single `32px` strip (`172px` total vertical chrome = **84.1% data height** on `1080p`).
  - Explicitly separates **Batch Selection (`selectedSymbols`)** in the top picker from **Inspected Stock (`selectedSymbol`)** in the left list.
  - Preserves all **5 real detail tabs**: `[*Summary*]`, `[Reports (7)]`, `[Debate & Risk]`, `[Sources (9)]`, `[Activity (40)]` (fixing Violation 7).
  - Grounds the **4 Analyst Cards** in actual stored `result.reports`, `result.social_sentiment` (Laya counts), and `result.completion_gaps` (fixing Violation 6).
  - Includes explicit wireframe state for **Cancelled / Unfinished Stocks** so L3 (fake `Sell` badge) and L4 (stuck `"Loading..."` notice) can never happen.

```text
+----------------------------------------------------------------------------------------------------------+
| RESEARCH  Batch: [2 selected: AMZN, INTC v] [Select Unfinished (21)] [All (24)]  [▶ Run Research (2)]    |
+----------------------------------------------------------------------------------------------------------+
| Run Status: [===3 Completed===|-------------21 Cancelled-------------] 3/24 completed · 21 cancelled     |
+-----------------------------+----------------------------------------------------------------------------+
| STOCKS (24)  [Filter: Allv] | AMZN · Completed Oct 28         [Open in Markets] [Prepare AMZN Order ->]  |
| [Search...]         [Delete]| Tabs: [*Summary*] [Reports (7)] [Debate & Risk] [Sources (9)] [Activity]   |
+-----------------------------+----------------------------------------------------------------------------+
| SYM    STATUS     VERDICT   | +------------------------------------------------------------------------+ |
| AMZN * Completed  [HOLD]    | | VERDICT: [HOLD] · Date: 2026-10-28 · Workflow: Default                 | |
| INTC   Completed  [UNDERWT] | | Coverage: All 7 reports saved · Social: Screened (Laya CPU)            | |
| TER    Completed  [SELL]    | +------------------------------------------------------------------------+ |
| AAPL   Cancelled  No verdict|                                                                            |
| GOOGL  Cancelled  No verdict| ANALYST REPORTS (Click any card to read full markdown in Reports tab):     |
| META   Cancelled  No verdict| +-----------------+ +-----------------+ +-----------------+ +------------+ |
| MSFT   Cancelled  No verdict| | MARKET [Saved]  | | FUNDAMENTALS[OK]| | NEWS [Saved]    | | SENTIMENT  | |
| NVDA   Cancelled  No verdict| | "Price holds    | | "Operating cash | | "9 URLs read;   | | StockTwits | |
| NFLX   Cancelled  No verdict| |  above 50d SMA  | |  flow grew 18%  | |  1 FRED retry   | | 12 Bull ·  | |
| ...                         | |  with support…" | |  YoY; AWS…"     | |  succeeded…"    | | 3 Bear ·   | |
| (Single scrollbar!          | | [Open report ->]| | [Open report ->]| | [Open report ->]| | 5 Unclear  | |
|  Clicking [Delete] reveals  | +-----------------+ +-----------------+ +-----------------+ +------------+ |
|  row checkboxes + preview   |                                                                            |
|  confirm bar in place;      | COMMITTEE DEBATE & RISK SYNTHESIS (Excerpts from saved state):             |
|  raw run_id moved to        | +-----------------------------------+ +----------------------------------+ |
|  Technical Record.)         | | RESEARCH COMMITTEE (Bull vs Bear) | | RISK COMMITTEE & TRADER PLAN     | |
|                             | | Judge plan: "Maintain Hold; wait  | | Trader proposal: "Hold current   | |
|                             | | for Q3 capex clarity before…"     | | weight; no new buy leg…"         | |
|                             | | [Read full debate ->]             | | [Read risk debate ->]            | |
|                             | +-----------------------------------+ +----------------------------------+ |
|                             |                                                                            |
|                             | OPERATOR REVIEW: Disposition [Needs review v]  Note: [___________] [Save]  |
|                             | [▸ Full Portfolio Manager decision (final_trade_decision markdown)]        |
|                             | [▸ Technical record (Run ID, revision, artifact hashes)]                   |
+-----------------------------+----------------------------------------------------------------------------+
```

**Cancelled / Unfinished Stock State on Research (e.g., clicking `AAPL` — fixes L3 & L4):**
```text
+------------------------------------------------------------------------+
| VERDICT: [Cancelled — No Final Recommendation] · Stopped Oct 28        |
| This stock was cancelled before the pipeline completed.                |
| [▶ Run Research on AAPL Now]     [Select All 21 Unfinished Stocks]     |
+------------------------------------------------------------------------+
| Saved Partial Reports: 0 of 7 reports generated before cancellation.   |
| (Never displays "Sell" badge or "Loading research reports…")           |
+------------------------------------------------------------------------+
```

---

### 8.5 Portfolio (`#portfolio`) — Broker Holdings, Session-Only AI Proposed Model, & Performance

- **Fixes over Blueprint 6.5:**
  - Keeps **Portfolio → Proposed** (`[Proposed Model Portfolio]`) strictly for the session-only joint deep-model synthesis (`/api/portfolio-model`), never mixing it with Human Baskets (fixing Violation 2).
  - Formats all holdings numbers with `money()`, `percent()`, and `color()` helpers (Critique Portfolio P1).
  - Hides empty table headers when `positions.length === 0` (Critique L11).
  - Caps the empty Performance state to a `140px` card with a visible **`[Collect Account History in Journal →]`** button (fixing Critique L2).

```text
+----------------------------------------------------------------------------------------------------------+
| PORTFOLIO   Tabs: [*Positions (0)*]  [Proposed Model Portfolio]  [Performance]         [Refresh Account] |
+----------------------------------------------------------------------------------------------------------+
| EQUITY $100,000.00 | CASH $100,000.00 | LONG VALUE $0.00 | UNREALIZED P/L $0.00 (0.00%) | SYNC: Clean ✓  |
+----------------------------------------------------------------------------------------------------------+
| (TAB 1: POSITIONS — when empty, hides empty table headers and shows compact 120px card:)                 |
| +------------------------------------------------------------------------------------------------------+ |
| | No open positions in your connected Alpaca Paper account.                                            | |
| | [Browse Universe in Markets]    [Open Proposed Model Portfolio]    [Open Orders & Baskets (1)]       | |
| +------------------------------------------------------------------------------------------------------+ |
| [▸ Technical reconciliation record (native cache, broker snapshot & epoch details)]                      |
|                                                                                                          |
| (TAB 2: PROPOSED MODEL PORTFOLIO — Session-only joint synthesis over latest completed research:)         |
| +------------------------------------------------------------------------------------------------------+ |
| | JOINT AI MODEL PORTFOLIO (Session-Only Advisory Synthesis · Does Not Approve or Stage Orders)        | |
| | Model Capital (USD): [$10,000.00 ]  [▶ Model Portfolio]   Eligible: 3 of 24 stocks · 21 excluded     | |
| | ---------------------------------------------------------------------------------------------------- | |
| | SYM    TARGET WT   WHOLE SHARES   REF PRICE (DATED)          REF VALUE    RATIONALE & ENTRY          | |
| | AMZN   25.00%      9 shares       $252.51 (Oct 28, IEX)      $2,272.59    [▸ View rationale & rules] | |
| | Residual Model Cash: $7,727.41 (77.27%) · Cash rationale: "Preserve dry powder while 21 stocks..."   | |
| | [▸ Excluded stocks (21): AAPL (cancelled), GOOGL (cancelled), INTC (underweight/0% target)...]       | |
| | [▸ Saved research bindings & source coverage]                                                        | |
| +------------------------------------------------------------------------------------------------------+ |
|                                                                                                          |
| (TAB 3: PERFORMANCE — Capped 140px empty state when <2 captures exist, fixing L2:)                       |
| +------------------------------------------------------------------------------------------------------+ |
| | View: [*Equity*] [Returns %]   Saved Interval: [No saved intervals v]   Basis: Broker-reported USD   | |
| | +--------------------------------------------------------------------------------------------------+ | |
| | | [📈 24px] Not enough saved equity observations (needs at least 2 captured points).               | | |
| | |           [Collect Account History in Journal ->]                                                | | |
| | +--------------------------------------------------------------------------------------------------+ | |
| +------------------------------------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------------------------------+
```

---

### 8.6 Orders (`#orders`) — 3-Stage Order Lifecycle, Baskets, & Uncertain Outcome Recovery

- **Fixes over Blueprint 6.6:**
  - Restores the true **3-Stage Order Authority Contract**: `1. Draft & Save Revision → 2. Check & Approve Exact Revision → 3. Submit Separately to Broker` (fixing Violation 3).
  - Exposes all 4 right-pane tabs: `[*Open Broker Orders (0)*]`, `[Saved Drafts & Proposals (1)]`, `[Baskets]`, `[Command History & Receipts]`.
  - Shows a single toggle button (`[Pause New Orders]` when active, `[Resume New Orders]` when paused — fixing Critique L14) and hides the action note field on Pause/Resume (Critique Orders P2).
  - Includes the **Inline Confirmation + Receipt Flow** AND the **Uncertain Outcome Recovery Banner** (`resolve_never_dispatched`).

```text
+----------------------------------------------------------------------------------------------------------+
| ORDERS & EXECUTION   Gate: [● Orders Active] [Pause New Orders]               [Refresh Account & Orders] |
+----------------------------------------------------------------------------------------------------------+
| Readiness: Ready for paper orders · Cash $100,000.00 · Sync: Reconciled · Regular session closed         |
+---------------------------------------------+------------------------------------------------------------+
| ORDER TICKET & AUTHORITY (42% width)        | ORDER BOOK & BASKETS (58% width)                           |
| Mode: [*Single Ticket*] [Option Package]    | Tabs: [*Open Orders (0)*] [Proposals (1)] [Baskets] [Logs] |
+---------------------------------------------+------------------------------------------------------------+
| STEP 1: DRAFT & PREVIEW TERMS               | SAVED PROPOSALS AWAITING ACTION (1):                       |
| Symbol: [SGOV     v]  Asset: [US Equity v]  | SYM   TERMS              STATUS     NEXT ACTION            |
| Side:   [(*)Buy ( )Sell]  Qty: [1         ] | SGOV  BUY 1 MKT DAY      Deferred   [Load into Ticket]     |
| Type:   [Market   v]      TIF: [DAY       v]|                                                            |
| Session:[Regular  v]  [▸ Exits / Replace]   | OPEN BROKER ORDERS (0):                                    |
| Rationale: [Park cash in T-bill ETF       ] | No working orders at Alpaca Paper.                         |
| Linked Research: None (Human proposal)      | (When open orders exist, shows 6 clean columns:            |
| [Preview Impact]  [Save Draft Revision]     |  Symbol, Side/Type/TIF, Qty/Filled, Price, Status,         |
| ------------------------------------------- |  [Inspect / Cancel / Replace ->] opening right drawer)     |
| STEP 2: CHECK & APPROVE REVISION (#rev 1)   | ---------------------------------------------------------- |
| Est. Principal: $100.42 · Cash After: $99.9k| INLINE CONFIRMATION / LAST RECEIPT / RECOVERY:             |
| Policy Check: 10/10 rules passed            | +--------------------------------------------------------+ |
| [▸ Optional quote-age & fee bounds]         | | Confirm Submission: Send BUY 1 SGOV MKT DAY (Rev 1)    | |
| [Check Order]  [Approve This Order]         | | to Alpaca Paper Account #PA3...?                       | |
| ------------------------------------------- | | [Confirm & Send to Alpaca]   [Cancel]                  | |
| STEP 3: SEPARATE BROKER SUBMISSION          | +--------------------------------------------------------+ |
| Approval Status: Approved (Single-use)      | (If request times out / outcome_unknown:                   |
| [Submit Approved Order to Alpaca Paper]     |  [! Uncertain outcome — Refresh before acting]             |
| [▸ Technical record (SHA-256 & bindings)]   |  [Refresh Status] [Check if Submit Was Never Sent])        |
+---------------------------------------------+------------------------------------------------------------+
```

---

### 8.7 Strategy Lab (`#strategy`) — Saved-Plan Simulations & Walk-Forward Experiments

- **Fixes over Blueprint 6.7:**
  - Restores the two real backend evaluation engines (`[*Saved-Plan Simulations*]` and `[Walk-Forward Experiments]`) instead of the fictional "SMA Crossover" form (fixing Violation 4).
  - Places the `[Load Saved Plans & Data]` button **below** the Setup heading (fixing Critique L10).
  - Replaces the 90-word consent wall with a 2-line always-visible `What this model does not establish` box + 1-line confirm checkbox (Critique Strategy Lab P1 & P2).
  - Orders right-pane tabs in workflow order: `[*Preview & Results*]` then `[Runs & Compare]` (Critique Strategy Lab P2).
  - Adds dashed/solid stroke patterns + `<details>` Table View for OOS equity curves (Critique Theme #4).

```text
+----------------------------------------------------------------------------------------------------------+
| STRATEGY LAB   Engine: [*Saved-Plan Simulations*] [Walk-Forward Experiments]   [Load Saved Plans & Data] |
+----------------------------------------+-----------------------------------------------------------------+
| SETUP RAIL (360px, 3-Step Accordion)   | EVALUATION CANVAS   Tabs: [*Preview & Results*] [Runs & Compare]|
+----------------------------------------+-----------------------------------------------------------------+
| [! Model Scope: Uses cached daily bars | SELECTED RUN: Simulation #sim-01 · Status: [Completed]          |
|    only; never proves intraday order   |                                                                 |
|    of events or places broker orders.] | MODELED EQUITY CURVE (with dashed benchmark & table toggle):    |
|                                        | +-------------------------------------------------------------+ |
| ▾ 1. PLAN / STRATEGY & DATA SOURCE     | | $1,010 |        _______________                             | |
|   Saved Plan:  [BUY 1 AAPL LMT $100 v] | | $1,000 |_______/               \_______________             | |
|   History Key: [AAPL 1Day (1,255b)  v] | |   $990 |____________________________________________________| |
|   Window:      [2026-10-12]–[10-19]    | | Legend: — Modeled Equity ($1,000.00)  - - Benchmark         | |
|   Basis:       [Hindsight scenario  v] | | [▸ View dated equity & bar observations table (5 rows)]     | |
|                                        | +-------------------------------------------------------------+ |
| ▸ 2. CAPITAL, FEES & FILL ASSUMPTIONS  |                                                                 |
|   Cash: $1,000 · Fee: $0 · Fill: 100%  | SUMMARY METRICS:                                                |
|   (Click to edit slippage, seed, ns)   | Net Return %   Modeled P&L   Max Drawdown %   Closed Trades     |
|                                        |  0.00%          $0.00         0.00%            0 (DAY expired)  |
| ▾ 3. PREVIEW & RUN                     |                                                                 |
|   [x] I understand this is a model     | [▸ Retained execution events & native simulation tables]        |
|   [Save Preview]  [▶ Run Simulation]   | [▸ Technical record (Immutable spec SHA-256 & source pins)]     |
+----------------------------------------+-----------------------------------------------------------------+
```

*(When `[Walk-Forward Experiments]` is selected at top: Step 1 edits/selects the declarative `Saved Strategy` (1–16 ALL/ANY entry/exit conditions + finite parameter domains); Step 2 configures Rolling/Expanding `Train / Validation / Gap / OOS` session counts, Grid vs. Adaptive Optuna search, and `Minimum closed trades`; Right pane shows Fold-by-Fold OOS curves, Trial rankings, and Multi-Experiment Comparison.)*

---

### 8.8 Journal (`#journal`) — Master-Detail Decision Ledger, Position Outcomes, & Account History

- **Fixes over Blueprint 6.8:**
  - Merges the redundant `Notes` tab into `[*Decisions & Notes*]` (`3` clean tabs: `[*Decisions & Notes*]`, `[Position Outcomes]`, `[Account History]`).
  - Replaces raw `human_proposal` with `Human proposal` and strips raw UUID suffixes from row labels (fixing Critique L8 & Journal P3).
  - Keeps focus stable inside `#decision-search` while typing (Critique Journal P2).
  - Guards `[Reload Saved Journal]` so it is disabled when no unsaved edits exist and opens an inline confirmation showing the count of unsaved notes when dirty (fixing Critique Journal P1).
  - Collapses the 12-paragraph `Position Outcomes` groups into a **1-row summary table** (`Instrument`, `Lifecycle State`, `Qty`, `Realized P&L`, `Unrealized P&L`, `Coverage`, `[Inspect Outcome]`) with the detailed attribution and native capture button (`[Go to Native Table Capture in Settings →]`) in the right-hand inspector!

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
| Oct 28   TER   AI research     [Sell]     —        | Original Thesis: "Park idle cash in T-bill ETF..."  |
|                                                    |                                                     |
| (Typing in [Find...] filters table rows in-place   | FOLLOW-UP NOTE & DISPOSITION:                       |
|  without losing input focus or caret position.)    | Disposition: [Deferred         v]                   |
|                                                    | Note: [Waiting for next week's FOMC meeting...    ] |
| [Revert Unsaved Edits (0)] (Disabled when clean;   |                                                     |
|  asks inline confirm if unsaved notes exist)       | [Save Note]  [Open Linked Research]  [Open Ticket->]|
|                                                    | [▸ Technical record (Decision ID, run ID, SHA-256)] |
+----------------------------------------------------+-----------------------------------------------------+
```

---

### 8.9 Alerts (`#alerts`) — Triage Inbox, Deduped Occurrences, & 1-Click Rule Templates

- **Fixes over Blueprint 6.9:**
  - Keeps all **3 real tabs** (`[*Inbox (1 unread)*]`, `[Rules (0)]`, `[Delivery: Browser Off]`) with an unread badge on `Inbox` (Critique Alerts P1).
  - Groups repetitive occurrences (e.g., `25 service restarts`) into a single expandable summary row instead of 25 raw JSON blocks (Critique Alerts P1).
  - Turns the `"no price-age limit configured"` warning into a calm setup prompt with a 1-click `[Configure Quote Freshness in Trading Rules →]` link and closed-market context note (Critique Alerts P1).
  - Adds **3 Quick Rule Templates** (`[Price Above $]`, `[Price Below $]`, `[Source Stale > Ns]`) on the `Rules` tab while preserving `[▸ Advanced Multi-Condition Builder (Indicators, Drawings, Policy, 1–16 ALL/ANY)]` underneath.
  - Restores focus to the clicked occurrence row when `[Close Saved Evidence]` is clicked (Critique Alerts Minor).

```text
+----------------------------------------------------------------------------------------------------------+
| ALERTS   Tabs: [*Inbox (1 unread)*] [Alert Rules (0)] [Browser Delivery]   Quote Age Limit: Not set [Set]|
+----------------------------------------------------+-----------------------------------------------------+
| ATTENTION INBOX (52% width)                        | OCCURRENCE EVIDENCE / QUICK RULE BUILDER (48% width)|
| [Filter: All Events v]      [Acknowledge Selected] | Tabs: [*Event Summary*] [Captured Evidence] [Rule]  |
+----------------------------------------------------+-----------------------------------------------------+
| • [UNREAD] Price-age threshold not configured      | SELECTED EVENT: Price-age threshold not configured  |
|   Account · Setup gap (Market currently closed)    | State: Unread · Evaluated Oct 28, 20:35 ET          |
|   [Inspect Evidence]  [Set Quote-Age Limit ->]     | Reason: No maximum quote age is enabled in Trading  |
|                                                    | Rules. Note: The regular market is currently closed.|
| • [ grouped ] Service restart recorded (25 events) |                                                     |
|   Latest: Oct 28, 20:14 ET · All acknowledged      | [Acknowledge Event]   [Set Limit in Trading Rules]  |
|   [▸ Expand 25 individual restart timestamps]      | [▸ Technical record (Exact captured evaluation JSON)|
|                                                    |                                                     |
| -------------------------------------------------- | --------------------------------------------------- |
| QUICK CREATE ALERT RULE:                           | [Price Above $]  [Price Below $]  [Quote Stale > s] |
| Symbol: [AMZN v]  When: [Price Above v] [$260.00]  | [Save Rule]  [▸ Advanced 16-condition / drawing]    |
+----------------------------------------------------+-----------------------------------------------------+
```

---

### 8.10 Workflows (`#workflows`) — True `Fit All` Diagram & Node-Linked Prompt Studio

- **Fixes over Blueprint 6.10:**
  - Keeps the **2 real inspector tabs** (`[*Prompts*]` and `[Workflow YAML]`, fixing Violation 8) and renders the **Selected Node's Related Files** (`Primary prompt`, `Shared context & tools`, `Output schema`) as a 1-line chip bar directly above CodeMirror when a node is clicked.
  - Fixes `workflowFitDiagram()` by adding **`[Fit All]`** (`Math.min((clientWidth - 32) / naturalWidth, (clientHeight - 32) / naturalHeight)` with a `0.25` zoom floor) alongside `[Fit Width]`, so the entire `1,755px`-tall 18-node flow fits inside the left pane without clipping (fixing Critique Workflows P1 & L5).
  - Closes `[About Diagram]` and `[Details]` popovers on `Escape` and outside click (Critique Workflows P2).
  - Formats the 94-option prompt selector cleanly (`market_analyst — Guides technical market analysis`) and replaces native `window.confirm()` on unsaved changes with an in-app `<dialog>` (Critique Workflows P2).

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
|                      v                         | |   | (Full-height CodeMirror editor;                 | |
|          [Bull / Bear Debate (1r)]             | |   |  Clicking any node on the left diagram selects  | |
|                      v                         | |   |  it and loads its primary prompt here;          | |
|          [Research Manager (Deep)]             | |   |  Ctrl/Cmd+S saves bundle;                       | |
|                      v                         | |   |  Discard / Leave opens in-app confirm dialog)   | |
|              [Trader Proposal]                 | +-----------------------------------------------------+ |
|                      v                         | Path: prompts/market_analyst.md · [Discard Changes]     |
|             [Risk Debate (1r)]                 |                                                         |
|                      v                         |                                                         |
|          [Portfolio Manager (Deep)]            |                                                         |
+------------------------------------------------+---------------------------------------------------------+
```

---

### 8.11 Settings (`#settings`) — All 5 Complete Categories with Progressive Disclosure

- **Fixes over Blueprint 6.11:**
  - Preserves all **5 real backend Settings categories** (`[*Account & Engine*]`, `[Research & Models]`, `[Universe & Data Keys]`, `[Trading Rules & Native Cache]`, `[Diagnostics & Backup]`, fixing Violation 9).
  - Keeps `Start Nautilus` / `Stop Nautilus` and `Native execution profile` visible on both `Account & Engine` and `Universe & Data Keys` (`Integrations`, fixing Critique Settings P2).
  - Splits `Research & Models` into **Core Model Configuration (5 fields + Model Limits)** and a collapsible **`[▸ Advanced Token Budgets, Concurrency, Retries & Laya Device (11 fields)]`** drawer (Critique Settings P1).
  - Separates read-only **System Health Chips** at the top of `Diagnostics & Backup` from the red-bordered **Danger Zone: Restore Workspace from Backup** card at the bottom, and uses dynamic `location.origin` instead of hardcoded port `8098` (Critique Settings P1 & Minor).

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
|                                                                                                          |
| [▸ Advanced Token Budgets, Concurrency, Retries & Local Laya Router (11 fields — collapsed by default)]  |
|   (Contains: Deep/Fast Max Total & Output Tokens, Concurrent Stocks [1], Research Retries [10],          |
|    Stop Cycle on Failure [ ], Social Timeout [600s], Max Posts [100], Laya Device [CPU v · Ready])       |
|                                                                                                          |
| -------------------------------------------------------------------------------------------------------- |
| OTHER SETTINGS TABS SUMMARY:                                                                             |
| • [Account & Engine]: Observed Paper/Live ID, Start/Stop Nautilus, Execution Profile, Alpaca Vault Keys. |
| • [Universe & Keys]:  Universe Name, 1,000-stock Textarea, FANGMAN Preset, CSV Import/Export, Data Keys. |
| • [Trading Rules]:    10 Deterministic Investor Policy Rules + Capture Native Cache Table (for Journal). |
| • [Diagnostics]:      Top: [● Engine: Connected] [● Sync: Reconciled] [● Store: OK] + Evidence Drawers.  |
|                       Bottom: [Export Backup] + Red-Bordered DANGER ZONE: [Restore Workspace Backup].    |
+----------------------------------------------------------------------------------------------------------+
```

---

## 9. DOM Refactoring Guardrails for Implementation Phase

Critique Theme #5 noted: *"Several pages are built by moving page pieces around after drawing them (Orders, Markets, Alerts, Settings). This is fragile and causes the layout problems."*

When we move from this approved wireframe review to implementation, workers must follow three architectural rules in `tradingagents/web/static/`:
1. **Render Target Topologies Directly (Stop Post-Render DOM Reparenting):**
   - Replace the post-render DOM-scraping functions (`layoutOrders()`, `layoutBasketGroups()`, `layoutMarkets()`, `compactScannerMarkup()`, `renderAlerts()` node-splicing, and `renderSettingsDiagnostics()` `while`-loop sibling scraping) with direct template rendering into the target 2-column / tabpanel containers.
2. **One Shared `renderTablist()` Component:**
   - Replace `categoryTabs()`, `workspaceTabs()`, and ad-hoc `<nav class="view-tabs">` markup with one WAI-ARIA `renderTablist()` + keyboard arrow-navigation handler in `app.js`.
3. **Preserve All Existing API Endpoints, State Keys, and Safety Gates:**
   - Zero backend route changes are required. Every action button, `data-*` attribute, revision token, and `terms_sha256` binding remains intact.
