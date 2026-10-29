# Product

<!-- impeccable:product-schema 1 -->

## Platform

Desktop host with a browser workspace. A Tauri 2 tray application (Windows x64 and macOS 26+ Apple Silicon) owns a local Python desk service and opens its UI in the user's default browser at `http://127.0.0.1:8098/` (production) or `http://127.0.0.1:8099/` (development). The Tauri host has no webview window of its own. Desktop windows are the target; phone layouts are out of scope.

## Stack

- **Host:** Tauri 2 / Rust (`desktop/src-tauri`): tray menu (Open, Restart, Check for updates, Open logs, Quit), single-instance guard, signed updater, and a process-group/job-object supervisor that stops only the processes it started.
- **Desk service:** Python 3.12 private runtime running `tradingagents.web.server` (standard-library HTTP server bound to loopback, SQLite application store). The browser workspace is plain static HTML, CSS and JavaScript served from `tradingagents/web/static/`; Lightweight Charts and its drawing plugin are vendored.
- **Research engine:** the upstream TauricResearch TradingAgents framework (LangGraph/LangChain) with a declarative workflow bundle (`tradingagents/workflow_assets`).
- **Native trading runtime:** NautilusTrader 1.231.0 in a separate Python 3.13 runtime, connected to Alpaca through an app-owned market-data and execution bridge.
- **Memory and reasoning:** Maenifold Gateway (MCP) for memory, graph and sequential-thinking commands.
- **Local social screening:** Laya 0.4.14 batch router in an app-owned local Python process (CPU, CUDA when a CUDA Torch build is installed, or Apple MPS).
- **Credentials:** Windows Credential Manager or macOS Keychain via `keyring`, with separate `production` and `development` namespaces.

## Users

- Primary: the individual operator of this desk. They watch a configured stock universe (fresh default **FANGMAN**: META, AAPL, NVDA, GOOGL, MSFT, AMZN, NFLX; saved configurations can differ and the live paper desk observed on 2026-10-29 tracks 24 symbols), run multi-agent research on selected stocks, and decide what to trade. Job: go from market observation to evidence-backed research to exact, separately approved orders, then follow broker-observed outcomes, without losing track of what each record actually proves.
- The operator is the only decision maker. Agents advise; they never approve or submit orders.

## Product Purpose

TradingAgents is a local trading desk that combines AI research, market analysis, order preparation and portfolio monitoring around the user's own Alpaca account. Analyst agents (market, social, news, fundamentals) feed a bull/bear research debate, a research manager, a trader proposal and a three-way risk discussion, ending in a Portfolio Manager recommendation with a rating. NautilusTrader is the execution and accounting engine; the desk reconciles it with broker state. Success is an operator who can take stocks from selection to research to a reviewed order and its reconciled outcome in one application, with each step's source, timestamp and limits visible.

## Positioning

A structured agent *process* with a controlled execution path, not a single-prompt stock picker and not an autonomous trader. The traceable chain from raw data and tool results to a saved recommendation, and the separation between research, preparation, approval, submission and broker truth, are the product. Research is advisory; a model's "trader" or "portfolio manager" role never authorizes a broker order.

## Operating Context

- **Processes and ports:** production desk on 8098 using the installed app's private profile; development desk on 8099 with the `%USERPROFILE%\.cache\trader\development` profile (production uses `%USERPROFILE%\.cache\trader\production`). Settings, stores, runtimes and credentials are isolated between them.
- **Profile layout:** `application` (`desk.sqlite3`, authored workspace and workflow records, `reports` for latest-research report artifacts, `cache` for market and SEC data, and `nautilus` for the native runtime's logs), `research` (the legacy history directory and results-log root; empty in the observed profile), `private`, `logs` (`desk.log`), `cache` (Laya and Hugging Face caches), `tmp`, `updates`, and `runtimes/desk` plus `runtimes/native`, seeded once from a full setup installer.
- **Research retention:** only the latest research result per ticker is kept; the next cycle replaces it. There is no desk history import, research resume, replay ledger or persisted LangGraph checkpoint. Maenifold owns long-term memory; the desk keeps no competing decision log.
- **Providers:** the desk's research setting selects **Codex (existing sign-in)** through the installed Codex app-server, or an **OpenAI-compatible** endpoint (including Unsloth). Deep and Fast model tiers have separate token budgets and reasoning levels. The upstream framework also supports other LLM providers through its CLI.
- **Data vendors:** Alpaca (IEX feed observations and history), Yahoo Finance via yfinance, SEC EDGAR, and Alpha Vantage, FRED, Polymarket (keyless), Reddit and StockTwits paths where configured. Availability depends on credentials and service state.
- **Workspaces:** Dashboard, Portfolio, Markets, Research, Orders, Strategy lab, Journal, Alerts, Workflows and Settings.
- **Entry points:** the installed desktop app (`Start-TradingDesk.cmd` opens it), `Start-TradingDesk-Dev.cmd` for development, and `scripts/desk_api.py` for authenticated local API reads and authorized actions. The upstream `main.py` and `tradingagents` CLI remain in the repository.

## Capabilities and Constraints

- **Research:** single-stock or batch runs with selectable analysts, saved reports, evidence and debate; Laya batch screening of retained social posts with raw outputs, model identity and uncertainty retained as evidence.
- **Workflows studio:** a validated YAML workflow plus prompt bundle drives agents, model tiers, rounds and graph limits. The diagram is generated from the same YAML; edits are previewed, saved, and explicitly activated for new research. Bundles live in the profile's `application/workflows`.
- **Portfolio → Proposed:** one joint deep-model synthesis over eligible latest research and cached dated prices, with separate model capital and deterministic whole-share sizing. It is session-only, never replaces failed research, truncates candidates or invents allocations, and is separate from per-stock research, human baskets, simulations and broker authority.
- **Orders:** manual or research-backed tickets and baskets with impact review, exact approval and separate submission, admitted through Nautilus to Alpaca. Per-order approval never implies submission, and agents do not place trades.
- **Strategy lab:** isolated Nautilus simulations, Optuna-backed experiments and saved strategies; results are scenarios, not broker fills or account returns.
- **Alerts:** attention rules evaluated by the desk and delivered as browser notifications only.
- **Installation and updates:** a per-user NSIS installer at `%LOCALAPPDATA%\Programs\TradingAgents`. App-only updates come from a signed GitHub release feed and never carry the Python runtimes; those are seeded once by a full setup installer.
- **Reconciliation:** broker balances, positions, orders and fills are authoritative; the local database cannot erase or replace them. The native cache currently runs in memory with SQLite application records saved. The native account mapping supports cash accounts only, without shorting.
- **Constraints:** broker trades, order approvals and cancel/replace actions require explicit user authorization. The desk is a single-user local service bound to loopback. Nautilus 1.231.0 wheels are not published for Intel macOS, so macOS builds target Apple Silicon only. Do not add new backend features to justify UI changes; unsupported business actions are removed, not faked.
- **Open decisions:** none recorded here; see the local issues under `docs/issues` and `docs/uat`.

## Evidence on Hand

- Codebase at `C:\src\TradingAgents`, a fork of TauricResearch/TradingAgents. Python package version 0.7.1; desktop host 0.6.22.
- Live observation on 2026-10-29 UTC (the evening of 28 October local time): the production desk reports paper-account mode, NautilusTrader 1.231.0 connected, Alpaca IEX feed, Laya ready on CPU, Gateway ready, and the `Default` workflow active with four analysts, one debate round and one risk round. Reconciliation was clean for an empty paper account. This is a read-only observation, not acceptance of any workflow.
- Acceptance records and observed limits live in `docs/local-desk-guide.md` and `docs/uat`. Do not fabricate run results, performance claims or testimonials, and do not treat source capability as proven broker execution.

## Product Principles

1. The trace is the product: reports, debate, tool calls, source timestamps and coverage are inspectable, not just the final rating.
2. Research, preparation, approval and submission are different steps; none implies the next.
3. Broker state is the truth. Local records, simulations and model output are labelled for what they are.
4. Fail loudly and visibly: missing keys, stale data, incomplete research or coverage gaps are shown, never silently replaced, truncated or invented.
5. The interface follows the real workflow (account → markets → research → orders → portfolio) and exposes only actions with real data sources and capabilities.
