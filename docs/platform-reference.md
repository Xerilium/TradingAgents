# Platform reference

Use the [root README](../README.md) for the component map and
[local operating guide](local-desk-guide.md) for deployment and recovery.
This reference describes the current source capability, not an acceptance log.

## Markets, charts and selection

The configured universe, named watchlists, broker holdings, inspected instrument
and research batch are different collections. Viewing a stock does not change
the batch. Discovery results outside the universe do not automatically become
research or trading targets.

Markets includes Watchlists, Universe, Screener and Saved scans. Batch selection and the research action stay together above the list.
Secondary filters and list-management controls remain in their disclosure.
Check the exact selection before confirming research.
Membership changes do not create holdings.

Yahoo discovery uses explicit provider requests and pagination. Saving criteria
does not run them; editing a draft does not change an earlier result. Provider
totals and complete market coverage can be unavailable. Yahoo discovery does not
establish Alpaca tradability or an IEX quote.

An instrument has Chart, Research, Options and Position views. The chart renderer
is Lightweight Charts; it does not fetch prices. App modules collect and qualify
inputs and run calculations separately.

### Chart and scan evidence

- Every history source has symbol, interval, feed, adjustment, capture time and
  coverage. Retained daily bars are not a current consolidated quote.
- Saved research inputs and separately collected market history remain distinct.
  Selecting a cache does not refresh it. Collection is an explicit action.
- Studies, formula revisions, comparison, drawings, source inspection and playback
  retain source identity. Unsupported or incompatible inputs stay unavailable.
- Derived minute aggregates are distinguished from provider coarse bars.
  Closed-bar, warmup, source-freshness and numerical-validity checks are separate.
- Saved declarative scans combine typed conditions and allowlisted formula
  expressions across qualified timeframes. They do not execute arbitrary scripts
  or Pine code.
- Scan definitions, exact revisions, membership selection, collection consent,
  budgets and historical cutoff are explicit. A later capture does not establish
  what was known at an earlier date.
- In-app scan scheduling requires separate opt-in. Editing/importing a definition
  does not enable its schedule, and stopped intervals are not backfilled.
- Formula/drawing-derived alerts retain their evidence. Saving a drawing is not
  itself an alert or an order.

## Research

TradingAgents supplies the analyst and deliberation roles. LangGraph executes the
validated workflow; LangChain-compatible adapters supply model messages and tools.
The default stages cover market, fundamentals, news and social analysis, bull/bear
debate, research management, trader planning and risk/portfolio review.

Workflows can edit graph connections, prompts and supported runtime limits.
Validation enforces registered nodes, required stages, joins and bounded debate
routing. This is research configuration, not arbitrary code execution or a
second trading engine. Runs use their captured workflow/settings revision.

### Model providers and tools

The desktop's Codex provider uses the installed, signed-in Codex app-server.
Its adapter returns function calls to the app-controlled research workflow.
It does not give a research model unrestricted computer or broker access.

The OpenAI-compatible provider uses the configured endpoint and loaded model.
Unsloth is one possible compatible server; launching it does not load a model.
The framework has other provider adapters, including a distinct Responses API
path named `chatgpt`. Do not equate that path with the desktop's `codex`
app-server provider. Read saved settings to establish the active selection.

The Maenifold integration discovers Gateway command schemas and applies allowed
tool boundaries. Configured agents can use context retrieval, memory reads,
concept graphs and SequentialThinking. Not every model call, data request or
local classifier pass travels through Maenifold.

### Research data and evidence

Supported source paths include Yahoo/yfinance, SEC EDGAR, Alpha Vantage, FRED,
Polymarket, Reddit, StockTwits and selected Alpaca observations. The router and
saved configuration determine which sources are attempted. Source support is
not a promise of entitlement, completeness or current availability.

Research keeps reports, conclusions, debate, source references and completion
gaps for the latest result. Source, Gateway and social-screening receipts cover
different boundaries. Their counts must not be added as if each were a unique
network call. Hidden SDK/provider attempts remain unknown.

Valid empty data differs from failed acquisition. Captured raw inputs can
contain records later excluded by date/relevance filters. Successful capture
does not prove evidence quality, and a tool invocation does not prove the model
used every returned field. Oversized, unsupported or unsafe captures remain gaps;
they must not be silently replaced by fabricated content.

Rate-limit and transient-source retries use configured bounded backoff.
FRED and Reddit no longer have a universal one-retry rule. A long retry delay
can defer work; it does not authorize an unbounded wait or automatic broker retry.

### Laya and social screening

The desktop injects an app-owned local Laya Python worker, using the pinned
multilingual model and typed per-post relevance/stance questions. Several posts
can share a batch while retaining separate questions and original inputs.
The integration records model identity, raw outputs, token coverage, probabilities,
policy and uncertainty.

Missing Gateway grades in Laya 0.4.14 do not by themselves make a result uncertain.
The policy evaluates valid probabilities and a unique qualifying stance.
Unclear, unscreened and neutral are different outcomes. Source author tags, such
as StockTwits Bullish/Bearish tags, have different denominators and are not
classifier output or independent ground truth.

CPU/GPU support and fallback depend on the installed runtime. Ready means weights
loaded, not successful inference or calibrated quality. Cancellation/timeout can
terminate the owned worker; an interrupted pass has no accepted late result.
A later request uses a fresh worker. Neither screening nor its absence grants
order authority.

Jev remains an optional framework/CLI screening path. It is not the desk's
selectable fallback for Laya. See [Laya social review](laya-validation.md) for the
file-only human-label workflow and its limits.

### Latest research and interrupted cycles

The desk retains only the latest result per ticker in its application-side
research cache. Starting the next cycle for a ticker replaces its previous
research. Other tickers keep their latest result.

Research is not imported from a desk history folder. Interrupted runs become
failed/interrupted latest results with explicit gaps; start a new cycle rather
than resuming a checkpoint. The desk does not retain LangGraph checkpoints or a
competing long-term research decision log. Maenifold owns durable research memory.

Authored settings, watchlists, rules, notes, chart definitions, drafts and baskets
have separate retention. A saved record's old research reference may become
unavailable; do not silently substitute today's report.

## Portfolio and proposal types

| Object | Inputs and meaning | Authority and lifetime |
| --- | --- | --- |
| Research recommendation | One ticker's analyst evidence and model review | Advisory; latest-per-ticker retention |
| Joint model portfolio | Eligible latest research, cached dated prices and separate model capital | Session-only hypothetical allocation |
| Human basket | User-authored target quantities/weights and explicit terms | Saved linked local drafts; not atomic execution |
| Order draft | Exact instrument, side, quantity, type, prices and duration | Saved preparation; no approval or submission |
| Approved order | Reviewed exact terms and required current context | Still needs separate submission |
| Actual portfolio | Broker-observed balances, positions, orders and fills | Broker state; not replaced by local modeling |

Portfolio → Model proposal invokes one joint deep-model synthesis. It starts with model
cash rather than copying actual holdings. Deterministic sizing floors each
allocation to whole shares using the supplied dated prices and reports residual
cash. Invalid/omitted allocations and failed inputs are not silently invented
or replaced. It neither creates a human basket nor authorizes orders.

Portfolio performance uses retained observations and declared methods. Missing
account history, fees or complete event coverage stays unavailable. Native cache
tables, broker performance and hypothetical scenarios are different reports.

## Orders, approval and execution

The path is:

```text
Human terms or selected research
  → draft / human basket
  → preview and exact review
  → per-order approval
  → separate submission and admission checks
  → Nautilus native command
  → custom Alpaca client
  → broker observations and reconciliation
```

A model's trader or portfolio-manager role is not broker authority. Approval
does not dispatch a command. Terms, account identity, policy, source freshness,
commitments and current eligibility can invalidate readiness. Baskets create
linked proposals; each leg needs its own review/approval and can fill separately.

The bridge implements app-owned Nautilus market-data and execution clients using
Alpaca REST and trading updates. Native memory cache is not durable execution
proof. Broker observations and application commands are reconciled; an unknown
submission outcome must not be treated as permission to submit again.

### Supported source profiles and limits

| Area | Implemented boundary |
| --- | --- |
| Equity orders | App/native capability and current broker eligibility determine available order types, prices, durations and session choices; do not assume the old limit-only paper profile. |
| Cancel/replace | Explicit separate actions against eligible observed orders; replacement requires renewed review of changed terms. Acknowledgment is not final cancellation. |
| Trailing protection and linked exits | Dedicated controls and declared ownership/remaining-quantity rules; not an implicit consequence of a research recommendation. |
| Selected options | Retained contract identity, feed, account permissions, whole contracts and supported premium-order profile are required. Underlying research is not an option recommendation. |
| Option packages | Separate long-only and bounded-risk profiles have explicit leg, ratio, expiry, price, collateral and account requirements. They do not imply unrestricted short-option support. |
| Exercise / do not exercise | Separate exact-instruction preview, review, approval and submission; not ordinary order approval. |
| Unsupported observations | Remain inspectable with limitations. Missing parent/leg economics, exposure or commitments must not become zero or a fabricated equity order. |

These are source capabilities, not proof of exercised broker/native acceptance
for every profile. The live account, current permissions and readiness checks
control actual availability. Paper fills also do not establish live execution.

## Strategy lab and historical evaluation

Evaluation workers use retained qualified sources and Nautilus BacktestEngine
for saved-plan simulations and strategy experiments. Chart and scan calculations
share source/calculation infrastructure but are not broker execution.

A simulation declares capital, source identity, dates, fees, slippage and fill
assumptions. Synthetic ticks derived from bars are a modeling basis, not observed
tick/BBO liquidity. Incomplete prices, calendars or coverage remain explicit.
A simulation does not become a historical account reconstruction merely because
it shares a research date.

Strategies use validated declarative definitions and immutable revisions.
Experiments can use rolling/expanding training, validation and untouched
out-of-sample windows with explicit gaps and budgets. Optimization is available
only when the required compatible Optuna runtime is present. Do not infer it from
a menu label alone.

Runs, results, saved strategies and experiments are optional evaluation branches.
Neither simulation nor a joint portfolio proposal is a required stage before
preparing a manual order. Loading saved inputs does not run a simulation.

## Journal, alerts and configuration

Journal relates saved decisions, human notes, available outcomes and account
history. It does not restore replaced research or prove missing fills.

Alerts distinguishes rule definitions, observed occurrences and delivery.
Compound/watchlist conditions retain source identity; unavailable observations
are not false predicates. Acknowledgment does not necessarily rearm a rule.
Browser notification delivery requires browser permission and an active supported
surface; it is not an always-on external notification service.

Settings owns accounts, model selection, rules, integrations and diagnostics.
Credentials are stored in the desktop OS vault. Saving them does not reconnect
an active engine. Workspace preferences and drafts use revision-aware saves;
reload a concurrent change rather than silently overwriting it.

## Source map

| Responsibility | Implementation |
| --- | --- |
| Desktop ownership and profiles | [main.rs](../desktop/src-tauri/src/main.rs), [backend.rs](../desktop/src-tauri/src/backend.rs) |
| HTTP/session boundary and coordination | [server.py](../tradingagents/web/server.py), [service.py](../tradingagents/web/service.py) |
| UI, charts and workflows | [static](../tradingagents/web/static), [market-chart.js](../tradingagents/web/static/market-chart.js), [workflows.js](../tradingagents/web/static/workflows.js) |
| Research graph and validation | [graph/setup.py](../tradingagents/graph/setup.py), [workflows.py](../tradingagents/workflows.py) |
| Provider selection and adapters | [factory.py](../tradingagents/llm_clients/factory.py), [chatgpt_client.py](../tradingagents/llm_clients/chatgpt_client.py), [openai_client.py](../tradingagents/llm_clients/openai_client.py) |
| Laya and social policy | [integrations/laya.py](../tradingagents/integrations/laya.py), [post_screen.py](../tradingagents/agents/post_screen.py) |
| Maenifold and data routing | [integrations/maenifold.py](../tradingagents/integrations/maenifold.py), [dataflows/router.py](../tradingagents/dataflows/router.py) |
| Joint model allocation | [portfolio_model.py](../tradingagents/web/portfolio_model.py) |
| Drafts, baskets and exact review | [investor.py](../tradingagents/web/investor.py), [baskets.py](../tradingagents/web/baskets.py), [approval_review.py](../tradingagents/web/approval_review.py) |
| Admission and command lifecycle | [admission.py](../tradingagents/web/admission.py), [execution_lifecycle.py](../tradingagents/web/execution_lifecycle.py) |
| Nautilus and Alpaca | [nautilus_worker.py](../tradingagents/web/nautilus_worker.py), [nautilus_runtime.py](../tradingagents/web/nautilus_runtime.py), [alpaca_readonly.py](../tradingagents/web/alpaca_readonly.py), [alpaca_stream.py](../tradingagents/web/alpaca_stream.py) |
| History, discovery and evaluation | [market_history.py](../tradingagents/web/market_history.py), [market_discovery.py](../tradingagents/web/market_discovery.py), [evaluation.py](../tradingagents/web/evaluation.py), [evaluation_worker.py](../tradingagents/web/evaluation_worker.py) |
| Records, latest research and recovery | [app_database.py](../tradingagents/web/app_database.py), [store.py](../tradingagents/web/store.py), [workspace.py](../tradingagents/web/workspace.py), [recovery.py](../tradingagents/web/recovery.py) |
| Credentials | [credentials.py](../tradingagents/credentials.py) |
| Runtime contract | [nautilus-v1-runtime-manifest.json](nautilus-v1-runtime-manifest.json) is a live source-development fallback, not an audit attachment. |
