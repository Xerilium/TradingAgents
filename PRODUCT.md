# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Delegated by the canvas extension contract (inferred from the skill contract, not asked): the new surface is a Copilot CLI extension canvas — plain static HTML/CSS/JS in an isolated iframe document served from the extension's Node loopback server (`extension.mjs`); no framework, no build step. The Python side stays CPython 3.11 with the existing `tradingagents` package; the run driver is a stdlib-only subprocess script that streams JSON-lines.

## Users

- Primary (inferred): the operator of this TradingAgents deployment — an individual running multi-agent LLM equity analysis on a personal watchlist from within GitHub Copilot. Job: configure a run, launch it, monitor long agent sweeps without babysitting a terminal, and evaluate the resulting trading decisions across a portfolio.
- Current watchlist (from the request): FANGMAN (META, AAPL, NVDA, GOOGL, AMZN, NFLX) plus semiconductor stocks; the exact semi list is an open decision.

## Product Purpose

TradingAgents is a multi-agent LLM financial research framework: analyst agents (market, sentiment/social, news, fundamentals) feed a bull/bear researcher debate, a trader proposal, and a risk-management committee, ending in a Portfolio Manager decision with a 5-tier rating. Success = an operator takes a portfolio of tickers from configuration to evaluated decisions through one interface, with every intermediate agent artifact visible and saved.

## Positioning

A structured agent *process* — debate rounds, opposing researchers, a risk committee, and a decision memory that settles past calls on later runs (reflection/settlement) — not a single-prompt LLM opinion. The traceable chain from raw data to final rating is the product; single-shot "LLM stock picker" tools cannot truthfully copy it.

## Operating Context

- Repo: Python 3.11, LangGraph-based graph (`tradingagents/graph/trading_graph.py`); entry points `main.py` (programmatic) and `cli/` (rich TUI via typer).
- Runs write to `~/.tradingagents/logs/<TICKER>/<date>/`: `reports/*.md` per section, `complete_report.html`, `message_tool.log`.
- Decision memory: `~/.tradingagents/memory/trading_memory.md`; past decisions settle (reflection) on subsequent same-ticker runs.
- Configuration surface: `DEFAULT_CONFIG` + `TRADINGAGENTS_*` env vars (provider, deep/quick models, debate/risk rounds, data vendors, results dir). API keys come from the environment — no `.env` exists in the repo as of 2026-10-13.
- Data vendors: yfinance, alpha_vantage, sec_edgar, fred (keyed), polymarket, reddit, stocktwits.
- The canvas surface runs inside GitHub Copilot's extension-canvas contract: loopback-only iframe, host-injected theme tokens, SSE for live updates, JSON-RPC to a Node `extension.mjs`.

## Capabilities and Constraints

- Five-tier ratings: Buy / Overweight / Hold / Underweight / Sell; `REVIEW` when no rating is parseable (must be guarded with `is_review`).
- Analysts are selectable per run (market, social, news, fundamentals); asset types stock/crypto.
- Checkpoint/resume per ticker+date when enabled; tickers must pass `safe_ticker_component` before path use.
- A backtest command exists (`tradingagents backtest`, grid of tickers × dates) — out of scope for the canvas v1 (open decision).
- Canvas constraints: loopback URLs only; no privileged iframe bridge (HTTP + SSE); durable state keyed by domain ID, never instanceId; `console.log` is forbidden in `extension.mjs`.
- Open decisions: exact semiconductor ticker list (proposed AMD, AVGO, INTC, QCOM, TXN, MU, MRVL, ARM, ASML, TSM — unconfirmed); whether the operator's actual holdings/cash will be fed to runs as portfolio context; LLM provider/models pending API keys.

## Evidence on Hand

- Codebase at `C:\src\TradingAgents` (fork of TauricResearch/TradingAgents, v0.6.0): full agent pipeline, CLI/TUI, backtest, memory, HTML reporting.
- No saved runs yet (`~/.tradingagents/logs` absent); no API keys configured; no screenshots or visual assets exist for this product. Future work must not fabricate run results, performance claims, or testimonials.

## Product Principles

1. The trace is the product: every agent's intermediate output (reports, debate history, tool calls) is first-class and inspectable, not just the final rating.
2. Decisions are accountable: a rating without a readable rationale is REVIEW, and past decisions get settled against outcomes.
3. Fail loudly at setup: missing keys or invalid config surface before any model call, not mid-run.
4. The interface mirrors the pipeline: UI structure follows the agent stages (analysts → debate → trade → risk → decision), so monitoring maps 1:1 to what is actually running.
