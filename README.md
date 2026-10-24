# TradingAgents trading desk

A local desktop trading app that combines AI research, market analysis, order
preparation, and portfolio monitoring. This checkout extends
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents);
the browser desk, execution integration, and workflows described here are specific
to this fork.

**Start the existing installation:** run `rtk proxy .\Start-TradingDesk.cmd`
from `C:\src\TradingAgents`, then open <http://127.0.0.1:8098/>.
Normal startup connects Nautilus automatically and starts the installed local
Maenifold HTTP service if its configured loopback port is unavailable. Local Laya
already loads in the background; Codex starts its adapter when research needs it.
Browse-only and recovery modes do not start the native connection. No packages
are installed at startup.
Use one app server on **8098**. The app targets desktop windows; phone layouts
are out of scope.

## Read this first

- [Components and boundaries](#components-and-boundaries): what each integration does.
- [Daily workflow](#daily-workflow): account → markets → research → orders → portfolio.
- [Research](#research): providers, batch selection, evidence, recommendations and failures.
- [Orders and baskets](#orders-and-baskets): allocation, approval and execution.
- [Operations and storage](#operations-and-storage): launch, reconnect, restart and cleanup.
- [Source map](#source-map): where each responsibility is implemented.
- [Contributor instructions](AGENTS.md): session startup and delivery rules.
- [Detailed installed-environment guide](docs/local-desk-guide.md): additional implementation
  contracts and historical observations. Its older examples are not current account state.

This is an operating and capability guide. A feature appearing in source or in
a menu does not establish broker acceptance or successful execution of every
supported order type. Saved research is advisory. A research team's “trader” or
“portfolio manager” is a model role; its conclusion does not approve or submit
a broker order.

## Components and boundaries

| Component | What it does here | What it does not establish |
| --- | --- | --- |
| Browser desk | Dashboard, Portfolio, Markets, Research, Orders, Strategy lab, Journal, Alerts and Settings. Displays saved records and current observations; collects explicit user actions. | Opening a page does not start a trade. |
| Python desk service | Coordinates settings, research, evidence, proposals, approvals, native commands, calculations and saved records. | It is not a second broker or an independent source of actual holdings. |
| TradingAgents + LangGraph/LangChain | Runs market, social, news and fundamentals analysts, research debate, trader planning and final risk review. Routes model-requested tools through the app. | A recommendation is not an executed portfolio allocation. |
| Codex adapter | Uses the installed Codex app-server and existing sign-in for model responses and native function calls. The adapter returns calls to LangGraph for controlled execution. | It does not give the research model unrestricted computer or broker access. |
| OpenAI-compatible provider / Unsloth | Alternative model endpoint selected in Research settings. Requires a working compatible server and loaded model. | Installing or opening Unsloth does not load a model. It is not the active provider when Codex is selected. |
| Maenifold Gateway | MCP transport and schema discovery for tools. Research agents receive the configured memory and graph commands plus SequentialThinking; the app also uses selected data commands. | Gateway availability is separate from model availability and the broker connection. |
| Maenifold memory / graph / thinking | Durable notes, related-context retrieval, concept navigation and structured reasoning. Commands are discovered and validated against their schemas. | Research memory is separate from the app's saved research and SQLite records. |
| Laya | One app-owned local Python Router batches original social posts for relevance and bullish/bearish/neutral sentiment. Retains raw probabilities, model identity, token coverage and uncertainty as research evidence. | The Python API supplies no Gateway contract grades: missing grades remain unknown and stance counts remain unclear. Screening is not a trade signal, approval or order. |
| Jev | Optional framework/CLI social screening through TypeSafe/OpenRouter settings. The browser desk injects Laya instead. | It is not a selectable desk fallback, the same service as Laya, or implied to have run by a generic evidence message. |
| NautilusTrader | Native trading node, instruments, orders/events, cache, risk engine, portfolio accounting and isolated historical evaluation. Runs in the separate native Python environment. | Having the engine installed does not expose every upstream feature in this app. |
| Custom Alpaca integration | App-owned market-data and execution clients connect Nautilus interfaces to Alpaca REST and trading updates. Handles source observations, mappings and reconciliation. | This is not an assertion that Nautilus ships or configures the whole application workflow automatically. |
| Alpaca | Configured paper/live account, broker balances, buying power, positions, orders/fills and market-data services. | The local database cannot erase or replace broker state. Market-data access depends on feed and account permissions. |
| Market-data vendors | Alpaca observations/history; Yahoo Finance via yfinance; SEC EDGAR filings; optional Alpha Vantage, FRED, Polymarket, Reddit and StockTwits paths. | A configured adapter does not guarantee credentials, current service availability or complete coverage. |
| Lightweight Charts + drawing plugin | Vendored chart rendering and drawing interaction, wrapped by the app's chart module. | The renderer does not fetch market prices or prove that derived calculations are valid trading signals. |
| SQLite + report artifacts | User settings and authored trading/workspace records, plus a separate disposable cache containing only the latest research per ticker and its source files. | These records are not the broker ledger. Older research and desk resume are not retained. |
| Evaluation workers / Optuna | Existing isolated chart, scan, strategy and simulation calculations; optional Optuna dependency supports optimization paths. | Historical results are scenarios, not broker fills or proof of future returns. |

### Data and command paths

Research: selected symbols and date → configured analysts → chosen model adapter
→ app-controlled tools and data vendors/Gateway → saved reports, evidence,
debate and final recommendation.

Trading: manual terms or saved research → local proposal/basket → impact review
and exact approval → admission checks → native Nautilus command → custom Alpaca
execution client → broker → status/fill updates and reconciliation → Portfolio
and Journal.

Market display: broker/provider observations or retained history → app source
and timestamp metadata → chart/table. A fresh account observation is not
necessarily a fresh trade price, especially outside market hours.

## Daily workflow

1. **Dashboard:** verify the account mode, cash, buying power, exposure and open
   orders. Inspect quote timestamps. Select the stocks to research.
2. **Markets:** browse the configured universe, inspect an instrument and its
   retained chart, and use existing screens/scans as needed.
3. **Research:** check the batch symbols, date, analysts and provider. Start a
   batch, follow progress, and read the saved conclusion and supporting reports.
4. **Orders:** prepare exact terms or allocation targets. Review impact and
   conditions, save the proposal, then approve and submit through separate actions.
5. **Portfolio:** follow broker-observed holdings and order outcomes. Inspect
   performance only when the necessary observations have been retained.
6. **Journal:** connect the research, rationale, saved proposal, command and
   subsequent outcome. Use Alerts for configured conditions; Settings holds
   connections, research configuration, rules and diagnostics.

Research, preparing a draft, approving it and submitting it are different steps.
Stopping after a preview has not exercised broker execution.

## Dashboard, Markets and selection

The configured universe is the stock list, not the held portfolio. Fresh default
configuration uses **FANGMAN**: META, AAPL, NVDA, GOOGL, MSFT, AMZN and NFLX.
Existing stores can contain a different list.

The inspected ticker and research checkbox selection are independent.
Opening META while AAPL is checked does not change the batch to META.
Use **Clear selection**, then check the intended names, or **Select N matches**
for the current filtered set. Research setup explicitly lists the batch.

Dashboard summarizes the observed account, stock list, inspected chart, saved
research, positions and orders. Markets provides the detailed instrument
workspace and separate browse/screen/scan controls. Returning from an instrument
does not silently replace the research selection.

A retained chart has a symbol, timeframe, feed, adjustment and capture time.
Use those values to understand what it represents. Retained daily bars are not
a live consolidated quote. Derived displays and drawings remain distinct from
their source history.

### Watchlists and the Screener

In **Markets → Watchlists / Universe**, expand **Filters, list management and
batch actions** for ownership/research/priority/freshness filters, price-movement
thresholds, sorting, batch selection and column controls. **Create from selected**
creates a named watchlist; add/remove-selected actions edit its membership.
Watchlist membership does not change the configured universe or create holdings.
Outside-universe names can remain retained discovery observations without
becoming research/trading targets.

Check workspace save acknowledgment after edits. **Retry save** handles eligible
failures; **Reload saved workspace (discard unsaved edits)** replaces local edits
with saved state. Concurrent revision conflicts require reloading current state,
not overwriting another session's changes. Ordinary navigation can autosave view
preferences even when no explicit Save is clicked.

In **Markets → Screener**, enter price bounds, minimum market cap, average
three-month volume, sector and sort criteria. **Run current screen** requests
Yahoo discovery through yfinance. **Saved criteria and provider details** lets
you name/save criteria or load them into the draft. Running does not save the
draft; editing criteria does not relabel an earlier result.

Provider pages contain up to 25 rows. Previous/Next explicitly request pages
using retained criteria. Capture/request times, provider query, library version,
offset and returned observations remain attached. A provider total may be
unavailable and pages are not a complete market inventory. Empty success differs
from provider failure. Adding a result to a watchlist or configured universe is
an explicit separate action. Yahoo discovery is not Alpaca tradability or an IEX
quote.

### Instrument chart workspace

An instrument has **Chart, Research, Options and Position** tabs. Chart
inspectors are **Studies and formulas, Drawings, Comparison, Saved calculations,
Source data and Playback**.

Choose between immutable saved research inputs and separately collected
current-market IEX history. Selecting a cache reads retained data; it does not
refresh the provider. Source collection explicitly chooses interval, dates,
symbol-mapping as-of date and adjustment (`raw`, `split`, `dividend`, `all`).
Intervals are 1Min, 5Min, 15Min, 30Min, 1Hour and 1Day. Actions request this
stock's range, the 252-session daily baseline, or selected batch dates. Intraday
bars do not prove that daily baseline.

Source data exposes coverage, pagination, artifacts and data-job status.
**Stop future requests** stops further dispatch, not already received evidence.
Eligible incomplete jobs offer **Resume unfinished symbols**. A failed latest
request can leave an older usable artifact visible with its original time and
warning. Restart does not silently replay unfinished jobs.

Recorded OHLCV and close-to-close movement are separate from latest trades or
bid/ask quotes. Daily axes use business days; intraday axes use UTC with New York
context in selectors/readouts. Comparison requires compatible context, interval,
provider/feed, adjustment, aggregation and currency, and uses matching retained
timestamps only. Choosing comparison does not collect data.

Drawings support horizontal/trend lines and text, numerical or approximate pointer
placement. **Use selected retained OHLC value** binds an anchor explicitly.
Drawings retain symbol/source/timeframe/adjustment/currency and coordinate intent;
incompatible drawings remain unresolved rather than silently rebound. Saving a
drawing does not create an alert. An eligible numeric drawing can seed a separate
alert draft.

Playback pins retained data and historical cutoff, with stepping/speed/play
controls. It is hindsight inspection, not a backtest. Automatic playback in
Markets is not established: the current timer stops outside Dashboard.
Historical-price copying requires an eligible existing manual ticket field and
normalization review; it does not change a quote or approve/submit an order.

## Research

### Choose the provider

In **Settings → Research**, select **Codex (existing sign-in)** or
**OpenAI-compatible (including Unsloth)**. Codex uses the existing adapter;
its default fast/deep choices are Luna and Sol. The compatible option keeps
the endpoint/model workflow available. Save settings before starting a run.
Switching options in an editing draft is not the same as saving configuration.

“No model loaded” from a compatible endpoint means that endpoint cannot serve
the selected model. It does not mean Codex is unavailable. Check the actual
saved provider rather than configuring an unrelated service.

### Run a single stock or batch

1. Select the intended symbols on Dashboard or Markets.
2. Open **Research → New research**.
3. Check **Batch stocks for new research**. The inspected stock is informational;
   it does not replace the list.
4. Choose **Run research (N)** and review the workload dialog.
5. Choose **Start N-stock research**.

Set **Settings → Research → Concurrent stocks** to 1–8 (default 1).
New batches use that limit; changing it does not resize an existing run.
Each stock has its own fresh graph, reports and evidence attribution.
The next cycle replaces the previous result for each selected ticker, including
its local Laya annotation. Other tickers keep their latest result. There is no
historical run selector, desk resume, persisted LangGraph checkpoint or replay
ledger. Maenifold remains the long-term memory; the desk neither reads nor
extends the separate CLI decision-memory log.
Selected analyst roles can also work concurrently within a stock. A failure,
rate limit or stop prevents further stock dispatch; in-flight work settles first.
Local Laya social screening packs up to five independent posts into each
`Router.predict_batch` call, with one bounded device lane across stocks.
It does not call the Gateway or concatenate posts into one state.
Each post retains its original text/hash, ordered result and measured input
coverage. Inputs that exceed the 8,192-token sequence or question-head limits
remain unscreened. Raw probabilities remain available; absent contract grades
remain uncertain. New research batches
charge the screening time limit for processing, including model/transport waits,
not time queued behind other stocks. Waiting remains cancellable; older saved
wall-clock budgets retain their original expiry. Partial screening stays partial.
Local inference already on the device settles before a stop or expired budget
prevents the next batch; it cannot be interrupted mid-forward-pass.
The workload dialog displays the limit, models and date. Duration estimates use
observed stock durations and the selected limit; shared-service load can increase
the actual time. Cost may be unavailable.

**Stop run** is a research control, not an order cancellation. Completed reports
are retained. Do not start duplicate batches because a long-running screen
has not yet changed.

The service checks the requested date/configuration revision, model readiness,
account observation and worker ownership before admission. Current-date research
also needs selected-stock price snapshots. The saved account context is captured
at run creation, even if the analysis date is historical; it is not reconstructed
historical holdings.

| Stage | Actual responsibility / model tier |
| --- | --- |
| Market | History, indicators and deterministic symbol/date snapshot; quick model. |
| Sentiment | Prefetched news/social text and screening annotations; quick model. |
| News | Company/global news, macro, prediction markets and relevant documents; quick model. |
| Fundamentals | Company context, statements, insider/filing evidence; quick model. |
| Bull / bear researchers | Opposing investment cases after analysts; quick model. |
| Research Manager | Weighs debate and writes investment plan; deep model. |
| Trader | Advisory transaction proposal; quick model, despite older UI help associating it with deep reasoning. |
| Aggressive / conservative / neutral risk analysts | Challenge the proposal; quick model. |
| Portfolio Manager | Final research decision with risk, plans, portfolio context and lessons; deep model. |

Tool-using analysts have private message histories and bounded tool rounds,
followed by a final tool-free reporting turn. The library supports separate
providers/endpoints per tier; the desk applies its selected provider/endpoint
to both tiers. Future settings changes do not rewrite saved run configuration.

### Read results

- **Summary:** saved recommendation and conclusion.
- **Reports:** individual analyst findings.
- **Debate:** research and risk discussion.
- **Sources:** retained inputs and coverage.
- **Activity:** recorded progression and calls.
- **Setup:** configuration for a new cycle.

Ratings such as **Underweight** express the saved research's preferred exposure.
They do not by themselves mean “sell shares now.” If the account holds no shares,
there is no holding to reduce. Read the actual action, quantities, rationale and
portfolio context; missing order terms must not be invented from the label.

A final text answer can exist while a run remains interrupted. Completion
requires the app's required-input/report and evidence-persistence requirements,
not merely a model response. Company/global news, macro, prediction markets and
social classification are enrichment. A captured failure or unknown optional
request does not by itself mean evidence was lost. Gaps remain in the saved
Source coverage report and Activity, with qualified completion; they are not
changed to empty successes or silently retried. Required price/fundamental inputs,
cancellation, corrupt/missing capture and unknown stateful effects stay blocking.
Recorded failures of read-only GatewayIndex discovery remain disclosed coverage
gaps; they do not imply that the research record was lost.
Transient FRED and Reddit reads can retry once within their existing bounded
time allowance and Retry-After. Empty, invalid, access and unconfigured results
are not retried; successful inputs are retained. A completed workflow does not
claim every source or every fetched post was available or classified.
Inspect the saved run's status and errors before treating it as complete.

### Tools and failures

Research agents have an explicit tool allowlist. Memory/graph operations and
SequentialThinking support the research process; broker-write tools are not
granted merely because the Gateway exposes them.

Market, News and Fundamentals receive the supplemental Maenifold tools;
prefetched Sentiment does not receive that same tool loop. The allowlist is:

| Domain | Commands |
| --- | --- |
| Memory | SearchMemories, ReadMemory, WriteMemory, EditMemory, MoveMemory, ListMemories, DeleteMemory, ExtractConceptsFromFile |
| Graph | BuildContext, FindSimilarConcepts, Visualize, Sync, AnalyzeConceptCorruption, RepairConcepts |
| Thinking | SequentialThinking |

This includes durable mutations, not just read-only retrieval. Research guidance
requires relevant citations, checksums for editing and explicit confirmation for
deletion. A graph relationship is a retrieval aid, not verified financial evidence.
Maenifold owns long-term memory and durable lessons. The desk does not keep
a local decision/reflection log.

Codex requests use ephemeral app-server sessions advertising only the bound
TradingAgents functions. General shell/browser/computer/plugin/host MCP access
is disabled. Native function calls return to LangGraph for execution; the Codex
adapter rejects unadvertised functions or unexpected built-in tool activity.

Gateway commands use discovered schemas. SequentialThinking uses `response`
for thought content and a `conclusion` string when completing; unsupported
top-level fields are validation errors, not evidence of a network outage.
Before an analyst receives Gateway tools, the app loads canonical `GetHelp`
for each offered command into its tool description. Analysts must read this
guidance before use. A read-only `GetHelp` tool lets them reread help for only
those commands. Help is cached across concurrent stocks and retained as evidence;
missing help is surfaced rather than replaced with invented instructions.

Social source retrieval, Laya classification, model inference and evidence
persistence are separate stages. Posts can remain unclassified after failure or
screening-budget exhaustion. These gaps remain visible in saved research and
Activity. The default shared budget per stock is 100 posts or 600 seconds
across StockTwits and Reddit. Limit exhaustion is distinct from transport or
schema failure. A missing source is not a fabricated neutral result. Inspect the specific saved error:
connection failure, invalid arguments and missing evidence are different faults.

Laya records original post text/hashes, raw probabilities, model identity and
measured coverage. Direct Python results have no contract grades; these remain
unknown and stance counts remain unclear, with raw predictions retained.
Classifier off-topic predictions do not discard original posts from
analyst review. StockTwits user Bullish/Bearish tags, Laya classifications and the
analyst's sentiment report are different signals. Unclear/unscreened does not
mean neutral; a classification contract never supplies trading authority.

Source acquisition failures, unavailable/partial source data and capture failures
can block completion. One explicit exception is an app-marked supplemental
public-document read rejected with a captured HTTP error (400–599): its failed receipt remains saved,
the analyst receives a not-retrieved/unverified disclosure, and otherwise
complete required evidence may proceed. This does not bypass publisher access,
required data, transport/internal/security errors, capture or unknown-outcome checks. Legacy failures
without that explicit contract remain blocking.

Gateway capture completeness is different from tool-call success. A known, fully
recorded validation error can coexist with completed research. An unknown or
pending outcome cannot. The completion guard requires analyst reports and valid
required evidence capture. Source, Gateway, Jev, or cancellation failures can
prevent completion. Social-source gaps remain visible in Source coverage and
Activity. These gaps alone do not prevent completion.

### Data sources and historical meaning

| Research evidence | Default path |
| --- | --- |
| OHLCV, indicators, deterministic market snapshot | Yahoo Finance / yfinance |
| Financial statements | SEC EDGAR, then configured/supported Yahoo fallback |
| Company overview, insider context, company/global news | Yahoo by default |
| Macro series | FRED |
| Prediction markets | Polymarket |
| Social discussion | StockTwits / Reddit |
| Current account and desk quote context | Nautilus / Alpaca observations |

Tool-specific vendor configuration overrides category settings. An explicit
comma-separated vendor list defines the fallback chain; the router does not
silently add vendors. The `default` sentinel permits available implementations.
Alpaca desk quotes and Yahoo research bars can therefore have different feeds,
capture times and price bases.

Historical safeguards vary: SEC uses filing dates and FRED pins vintages.
Current Yahoo profiles, undated statements and live documents can be withheld
when historical availability is unproven. Trimming recent social feeds by date
does not reconstruct an archived point-in-time dataset.

The public document reader accepts readable public HTTPS sources with destination
and format checks. Historical reading requires verified document vintages. Sources
also lists URLs found in report text; that link list alone is not a verified
acquisition ledger. Inspect acquisition receipts/capture status separately.

A failed or stopped cycle keeps its latest status, partial reports and actual errors.
Start a new cycle when needed; it replaces research for the selected tickers.
Drafts that refer to replaced research keep their exact terms and original
reference, which is shown as unavailable rather than rebound to a new report.

## Orders and baskets

### Manual or research-backed order

Manual tickets do not require saved research. A research-backed ticket links the
saved rationale; it still needs explicit terms and review. Choose the instrument,
side, quantity, order type, duration and applicable prices/session. Preview
impact before saving. Saving creates a local record, not a broker order.

Review the exact saved terms, current account/price inputs and policy conditions.
Approval and submission are separate. A changed proposal or native session can
require renewed review. Watch actual order status after submission.

Unknown submission outcomes must be reconciled before another submission.
Never interpret a disconnected browser or missing reply as proof that the broker
did not receive an order.

### Basket allocation

Orders includes allocation targets and baskets. Add stocks, specify target
whole-share quantities or percentages, choose order types and provide rationale.
Preview cash, exposure, proposed legs, residuals and policy conditions.

Percentage targets use **observed total account equity**. They are not
percentages of an independently entered trading budget. For example, a $10,000
budget inside a $100,000 paper account must be translated deliberately into
targets; entering 100% would target the account's equity, not the smaller budget.

Saving a basket creates linked local proposals. A basket is **not atomic**:
legs can have different outcomes and require their relevant approval and command
checks. Hypothetical proceeds or assumed fills do not change actual buying power
or holdings. Basket allocation currently uses whole shares; manual fractional
quantity support does not imply fractional baskets.

### Specialized terms

Linked profit-target/protective-stop groups, trailing terms, eligible fractional
quantities, options and session-specific orders have explicit supported mappings
and eligibility checks. Do not assume every combination is accepted.

For linked entries, protection can depend on the entry filling completely;
partial entry exposure must not be described as fully protected. Cancellation,
replacement and group actions are distinct from creating a new proposal.
See [the installed-environment guide](docs/local-desk-guide.md) and the current
ticket's conditions for detailed supported-order contracts.

| Scenario | Implemented contract and limits |
| --- | --- |
| Target quantity | Desired total whole-share holding, including zero to close; proposed legs reflect the difference from observed holdings. |
| Target weight | `floor(observed equity × target percentage ÷ valuation price)`; each target and the sum must be at most 100%. Rounding residuals remain visible. |
| Basket admission | Exact current legs need unused approvals. The execution plan can have dependencies and pause/resume controls; it is not an all-or-nothing exchange transaction. Resume does not revive invalid approvals or uncertain legs. |
| Cancel | Authorizes one exact current broker order/version. A pending cancellation is not confirmed; fills can arrive before it completes. Cancel-all is unsupported. |
| Replace | Requires a reviewed replacement bound to its predecessor. Changes to cumulative fills can invalidate it. Retains predecessor/successor relationships and commitment accounting until resolved. A rejected replacement leaves the original authoritative. |
| Linked equity exits | Bracket, OTO or OCO relationships map to broker-managed groups. Actual child observations establish activation and coverage; the app does not manufacture local protective fills. |
| Fractional shares | Exact decimal quantities up to nine places; observed fractionable eligibility, simple DAY terms and additional eligibility for extended sessions. No fractional linked groups or baskets. |
| Extended equity sessions | Simple quantity-sized LIMIT terms; fractional terms remain DAY-only. Whole-share eligible terms can use DAY/GTC. Broker/session acceptance still applies. |
| Trailing stop | Standalone whole-share SELL, regular-session DAY/GTC, with exactly one price or percentage trail; trailing amendments are unavailable. |
| Single-leg options | Identified supported contracts, whole contracts, regular-session supported MARKET/LIMIT/STOP_MARKET/STOP_LIMIT DAY/GTC terms. Unknown/nonstandard deliverables remain observation-only. |
| Long-only options | Buy-to-open and sell-to-close intents. |
| Bounded-risk option spreads | Separately eligible account/session-bound profile; two to four legs, LIMIT terms, same-expiry protection, observed quotes and reviewed collateral/native caps. Modeled collateral is distinct from broker margin. |

Approval binds exact terms, revision, policy, account/session and evaluation
inputs. Admission reserves resources transactionally and dispatch records durable
intent before transport. A historical native `INITIALIZED` order is a draft
record, not evidence of approval, current-engine ownership or broker submission.

### Reconciliation and uncertain commands

The adapter compares account, instrument, client/venue order identities,
quantities, fills and statuses. Unsupported observations remain explicit.
The native cache is in memory; this app uses custom startup recovery and ongoing
reconciliation rather than assuming generic native startup reconciliation.

| Condition | What to do / what the state means |
| --- | --- |
| Missing funding, source prices, asset eligibility or reconciliation | Read the specific review/admission condition; do not infer readiness from Connected. |
| Missing submit/cancel/replace reply | Treat outcome as uncertain and reconcile; a lookup returning 404 alone does not prove non-submission. |
| Broker/native identity or cumulative-fill discrepancy | The gap remains explicit and resources may remain reserved. Do not create a compensating order by guesswork. |
| Stream interruption or incomplete recovery history | Full current lifecycle coverage is not established. |
| New-orders pause | Blocks new admission/dispatch and replacement; it does not itself cancel working broker orders. |

## Portfolio, Journal and Alerts

Portfolio presents broker-observed holdings, pending commitments and account
history. Empty positions mean no observed holdings; a saved basket preview
does not populate them. Unrealized results, realized outcomes and performance
series depend on their actual retained inputs and reconciliation.

**Portfolio → Proposed** offers **Model portfolio**, a single joint deep-model
allocation from the configured universe's latest completed research and cached,
dated reference prices. Model capital defaults to $10,000 with zero model
holdings; it is separate from the broker balance. The model chooses stock weights,
including zero allocations or all cash, with research-backed reasons and entry
conditions. The app computes whole shares and residual cash using Decimal.
Failed/missing research and missing dated prices are explicitly excluded.
Eligible, excluded and configured counts show actual coverage; configuring 504
symbols does not imply 504 completed research results. Full final decisions and
source-coverage notes are supplied without truncation; evidence over 120,000
characters fails before dispatch. This is synthesis, not new stock research,
historical simulation, an order or approval. The per-stock Portfolio Manager
remains a research role; human basket previews remain separate. Only the current
joint job/result exists in memory, replaced by the next explicit action and lost
on restart. Provider failures remain visible without fallback allocations.

Journal connects saved decisions with proposals, commands and recorded outcomes.
A simulation result remains separate from account returns.

Performance retains the distinction between broker-reported equity/P&L and
calculated returns. Modified Dietz needs covered endpoints and timed external
flows. Time-weighted return needs actual before/after valuations at each flow.
Missing flow boundaries and sessions are not interpolated. Benchmark comparison
uses matching completed sessions and split-adjusted USD price data; reinvested
dividends and benchmark costs are excluded. An empty history cannot produce a
meaningful performance curve.

Journal position outcomes require proven native/source relationships. It does
not arbitrarily attribute an entire position's P&L to one research decision.

Alerts evaluates saved conditions against available inputs and retains events.
Rules, Inbox and Delivery serve different purposes. A chart or indicator alert
is not a broker-hosted protective order, and closing/stopping the app can affect
local evaluation. Do not rely on an alert to execute an exit.

### Alert rules and delivery

**Inbox** retains occurrences and exact evidence; opening evidence and
acknowledging an occurrence are separate. **Rules** supports a name, compatible
target and up to 16 flat ALL/ANY conditions. Targets include a stock, global
account condition, fixed proposal, watchlist snapshot or followed list.
Conditions include price thresholds, absolute movement, missing/stale sources,
saved policy conditions, indicators and drawings. **Keep condition in group**
edits the draft; **Save rule** persists it with its enabled choice.

The monitor evaluates available snapshots every five seconds. Missing,
disconnected or incompatible inputs can be unavailable rather than clear.
Triggered conditions produce deduplicated occurrences; clearing rearms them.
Acknowledgment alone does not rearm. Pauses/restarts retain monitoring gaps;
unobserved intervals are not retrospectively evaluated as continuously monitored.
Missing exact evidence is not replaced by newer same-key data.

**Delivery** controls browser notifications for the current browser profile.
Enabling requires browser permission and starts from that point without replaying
the unread backlog. The service and browser page must remain running; OS and
background-tab behavior can delay/suppress display. Email and closed-browser
push are not configured. “Requested” records a display attempt, not proof of
delivery or reading. Failed attempts have an explicit retry; Inbox acknowledgment
remains separate.

## Strategy lab and historical evaluation

The app includes existing retained-history calculations, saved scans,
declarative strategy experiments and saved-plan simulations. These are optional
analysis workflows, separate from the ordinary research-to-order journey.

Choose and inspect the exact retained source and calculation inputs. Previewing
or saving an experiment does not launch it; use its explicit Run action.
Recorded results depend on timeframe, fees, fill assumptions, dates and available
data. A historical plan created after its simulated decision time carries
hindsight. Daily bars cannot establish every intraday order of events.

Nautilus evaluation runs in an isolated worker. Optuna is an optional evaluation
dependency, not the order execution engine. Missing packages, incompatible
inputs or unsupported profiles should remain explicit; do not install or
fabricate data merely to make a result appear successful.

### Chart calculations and reusable definitions

Definitions carry IDs, revisions, settings and hashes. Calculations bind exact
source receipts, dependency revisions, coverage and implementation identity.
Editing a definition does not rewrite an earlier result.

Derived displays include Heikin-Ashi, Renko, Kagi, line break, and point and
figure. Parameterized studies include KAMA, CCI, Donchian channels and Ichimoku.
Derived prices, event ordinals and placement are analytical outputs, not observed
quotes, trade times, volume or fills.

Chart formulas use typed parameters and causal OHLCV series. Functions include
`abs`, `where`, `lag`, `rolling_min`, `rolling_max`, `rolling_sum`, `rolling_mean`,
`sma`, `ema` and `scale`, with arithmetic/comparisons and exact saved dependencies.
Units include price, volume, scalar, percent and Boolean. A forward display offset
does not move information availability. Arbitrary scripts, imports, attribute
access, indexing, cycles and implicit transformed-event/raw-bar conversion are
rejected. Budgets bound expression size, periods, input rows and output events.

Seasonality supports calendar/session alignment and raw/normalized year
comparisons. Completed-year statistics require calendar bounds, expected
sessions and the prior December close. Incomplete years remain explicit;
MTD/YTD are separate. Price returns do not imply reinvested-dividend returns.

### Saved scans and scheduling

**Markets → Saved scans** separates Definition, Runs and Matches. Targets can be
fixed symbols, a watchlist snapshot, a following watchlist or an explicit provider
query. Saving is separate from running; collection is explicit, distinct from
retained-only evaluation.

Multi-timeframe programs support up to 16 inputs and 16 ALL/ANY conditions.
Inputs use OHLCV or exact saved formula/study revisions, with inequalities,
equality and crossings. Each input declares timeframe, source/session profile,
retained selection and maximum staleness in its own buckets. Minute axes are
regular-session 1, 5, 15, 30 minutes or 1 hour; daily axes use provider days.
Calculations retain original axes before backward alignment to eligible closed
observations. Missing bars are not fabricated. An old cutoff alone is not proof
of historical knowledge. Oversized work is rejected rather than truncated.

Scheduling requires opt-in. Missed/overlapping slots are recorded, not replayed.
Restart marks unfinished work interrupted; restored schedules lose scheduling
authority. Inspect source coverage and status before treating Matches as a
complete market screen.

### Saved strategies and walk-forward experiments

**Strategy lab** has Simulations, Experiments and Saved strategies, with Setup,
Runs and Results / Compare views. The experiment profile uses one regular-session
USD equity, whole-share sizing and empty initial holdings. Declarative rules
are not arbitrary Python. Entry/exit rules combine ALL/ANY of 1–16 conditions;
operands are OHLC prices, supported indicators, constants or finite parameters.
Comparisons are above, below, cross above and cross below. Up to eight parameters
can each have up to 256 unique integer/decimal values.

Indicators include 50/200 SMA, 10 EMA, MACD components, RSI, Bollinger components,
ATR, VWMA and MFI. RSI uses 0–100; MFI uses 0–1. A chart formula is not necessarily
a strategy operand. Entries support MARKET/LIMIT/STOP_LIMIT DAY/GTC and supported
linked protection; rule exits use MARKET terms.

Experiments require complete retained raw daily history, calendar/instrument
evidence, an explicit window, availability basis, cash, cost/fill scenarios and
budgets. Preview freezes inputs without collecting data or evaluating. Run is
separate. Rolling/expanding walk-forward windows separate training, validation,
two session-count gaps and disjoint out-of-sample periods. Warmup does not trade.
Each phase/fold resets cash, holdings and indicators; curves are independent
scenarios, not a compounded tradable portfolio.

### Optimizer and selection

Evaluation pins **Optuna 5.0.0** in the service environment and **NautilusTrader
1.231.0** in native execution. Availability, input validity and execution profile
are separate checks. Grid search covers the finite space or rejects an inadequate
budget. Adaptive search uses seeded `TPESampler`; both use `NopPruner`.
Intermediate pruning and exact sampler/RNG continuation are unavailable.

Selection uses net return, modeled total P&L or maximum drawdown with explicit
directions and a secondary tie-break. Training and validation must meet minimum
closed-trade counts. Validation ranks candidates; out-of-sample results do not
choose the winner. No qualifier means no winner or out-of-sample run for that
fold. Failed results are not zero returns. Scenario metrics average arithmetically;
minimum closed-trade count governs eligibility. Reused evaluations retain
source-trial attribution. ASK/dispatch/result/TELL/selection/out-of-sample evidence
is retained. Cancellation, deadlines and restart can leave interrupted/unknown
outcomes. Repeating creates a separate run, not exact optimizer continuation.

### Saved-plan simulations

In **Simulations**, load saved plans/data, choose the exact revision and source,
enter window, availability, cash and cost/fill assumptions, save a preview,
then run it separately. Supported saved plans are BUY whole-share regular-session
USD MARKET/LIMIT/STOP_LIMIT DAY/GTC with empty starting holdings. SELL starting
positions, replacement plans, BUY STOP_MARKET and imported initial holdings are
unsupported.

The saved-plan model submits after the first completed daily bar at/after
decision availability using an explicit open-high-low-close path. Ending
positions stay open. DAY cancellation is after the next sourced close and needs
zero latency; it is not intraday broker expiry. Declarative experiments instead
turn completed-bar signals into next modeled open-tick intents through the pinned
native OHLC converter. Compressed timestamps and allocated volume are modeled.

Fees, slippage/fill probabilities, seeds and latency are assumptions; enter zero
fees explicitly when intended. Neither profile reconstructs historical research
availability or proves point-in-time vintages. Separate native processes restrict
inherited environments and use temporary directories; this is application-level
separation, not an OS security sandbox. Results never authorize broker orders.

## Settings

- **Account:** connection identity and native start/stop controls.
- **Research:** provider, models, analysts and research limits.
- **Integrations:** configured service/data integration settings.
- **Trading rules:** application policy and supported execution configuration.
- **Diagnostics:** runtime, source, reconciliation and storage observations.

The broker, native engine and application policy each enforce different parts
of the workflow. Configuring one does not configure all three. A connected
status alone does not establish order readiness or every feature's acceptance.

## Operations and storage

### Local Laya setup and portability

In **Research → Reports → Social sentiment**, **Screen 5 saved posts locally**
annotates only the first five retained Stocktwits posts (or fewer if available).
The separate **Local Laya batch** report shows original input hashes, model,
batch receipts, token checks and per-post predictions. This does not refetch
sources, rerun research or change the saved recommendation.

The desk owns one background-loaded [Laya Python Router](https://github.com/NandhaKishorM/laya)
in its existing `.venv`; no classifier server, extra port or Gateway Laya process
is required. `pyproject.toml` pins Laya **0.4.14**, torch **2.14.1**,
transformers **5.20.2**, tokenizers **0.23.3**, huggingface-hub **2.3.0** and
safetensors **0.8.0** in the `paper` extra. The standalone
[`convaiinnovations/laya-multilingual`](https://huggingface.co/convaiinnovations/laya-multilingual/tree/1720e3e3357cfe1e281542e223f8273b0890ca34)
checkpoint is fixed at revision `1720e3e3357cfe1e281542e223f8273b0890ca34`.

For an existing checkout/environment, use the already-installed `uv` to freeze
the installed versions, inspect the missing-only resolution, then install the
same pinned classifier dependencies. Run these commands from the checkout:

```powershell
rtk proxy uv pip freeze --python .venv/Scripts/python.exe > laya-existing-constraints.txt
rtk proxy uv pip install --python .venv/Scripts/python.exe --constraint laya-existing-constraints.txt --dry-run laya==0.4.14 torch==2.14.1 transformers==5.20.2 tokenizers==0.23.3 huggingface-hub==2.3.0 safetensors==0.8.0
rtk proxy uv pip install --python .venv/Scripts/python.exe --constraint laya-existing-constraints.txt laya==0.4.14 torch==2.14.1 transformers==5.20.2 tokenizers==0.23.3 huggingface-hub==2.3.0 safetensors==0.8.0
```

Keep the generated constraints local; they can contain checkout-specific
package references. A conflict needs resolution before installation; do not
remove constraints or upgrade unrelated packages to force success. The existing
`requirements.txt` delegates to `.[paper,evaluation]` in `pyproject.toml`: one
dependency authority for the desktop service, MCP, local Laya and Optuna.
It is a component manifest, not a complete frozen lock of all transitive versions.
For initial setup on another machine with Python 3.12 and `uv` already installed,
create only that checkout's normal app environment if it does not exist, then
install the manifest:

```powershell
rtk proxy uv venv .venv --python 3.12
rtk proxy uv pip install --python .venv/Scripts/python.exe -r requirements.txt
```

Skip `uv venv` when `.venv` already exists. Do not run the unconstrained initial
install against an established installation: use its frozen constraints and
inspect conflicts first. In this installation, the retained websockets **16.1.1**
differs from the existing `paper` extra's **15.0.1** pin; the local Laya addition
preserved 16.1.1 and every other pre-existing package. No dependency installation
runs at app startup.

NautilusTrader **1.231.0** belongs in the separate `.venv-nautilus-v1`, not the
app environment. That native installation, the installed Codex app-server and
sign-in, the existing Maenifold Gateway/MCP service, Alpaca account access and
credentials are separate prerequisites; the app's pip manifest does not provision
them. Copy/configure `tradingdesk.launch.json` locally with its five fields:
`application`, `history`, `native_python`, `credentials_file` and `port` (8098).
Paths resolve against the checkout containing that file; absolute paths also
work. Retain the migrated SQLite application/history stores and keep credentials
external. The launcher rejects missing stores rather than creating replacement
records. Portability here provides the app dependency/model setup; it is not
an automatic broker, native-runtime or data migration.

The default weight cache is `.cache/laya` relative to the checkout. Reuse it
across app restarts; set `TRADINGAGENTS_LAYA_CACHE` to another cache directory
if needed (relative paths also resolve against the checkout). Prefetching is
optional; first startup downloads the same fixed revision in the background:

```powershell
rtk proxy .venv/Scripts/hf.exe download convaiinnovations/laya-multilingual --revision 1720e3e3357cfe1e281542e223f8273b0890ca34 --include rl_agent_config.json --include model.safetensors --include "tokenizer/*" --include "encoder/*" --cache-dir .cache/laya
rtk proxy .\Start-TradingDesk.cmd
```

`TRADINGAGENTS_LAYA_DEVICE=cpu` is the default. Set it to `cuda` or `cuda:0`
before launching only when the environment's PyTorch build and existing GPU
runtime support CUDA. This setup installs no drivers or system components;
select an appropriate official PyTorch build separately if GPU support is
needed. Loading failure remains visible rather than selecting a remote fallback.
The loader uses the eager backend, without model compilation or warmup inference.

In **Settings → Diagnostics → Service and observation details**, **Local Laya**
shows actual loading, ready, failed or stopped status and the device/error.
**Download diagnostics** includes the package/model revision, cache and batch
size. Ready means weights loaded, not verified inference or completed research.
Resolve the reported missing dependency, cache/network permission, model/config
or device error, then use the normal app restart. Browser refresh alone does
not restart a failed loader. App shutdown stops queued screening and releases
the model after an in-flight batch settles. Maenifold memory/graph/thinking
still use their existing Gateway tools and canonical GetHelp instructions.

### Existing installation

`tradingdesk.launch.json` supplies the application directory, history directory,
native Python, credentials-file location and port. The normal launcher uses
those values and checks the installation. A Git clone alone is not this working
installation: environments, local data and private credentials are separate.

The app runs in `.venv`; native Nautilus uses `.venv-nautilus-v1`.
Maenifold Gateway defaults to `http://localhost:8080/mcp`.
Provider endpoints and broker endpoints are separate configuration.

Normal startup starts Nautilus from the saved settings. Use **Settings → Account**
to inspect the observed account or to stop or start the engine. Check the observed
account to verify paper/live identity. Stopping Nautilus leaves saved research
and the web app available. Closing the browser does not stop the app server.

Restart only the identified app/native processes and keep port 8098. A native
restart creates a new authority session; retained broker orders are not
automatically cancelled. Apply changed credentials or execution profiles through
the documented stopped-session workflow.

### Where records live

| Location | Contents / boundary |
| --- | --- |
| Configured `application` directory | Authored settings, lists, proposals, approvals and notes; separate `latest_research` cache and latest source/report artifacts. Nested receipt observations update live state without saving the settings journal or scanning aggregate counts. Latest results are cached at cycle admission, stock completion and explicit local annotation boundaries. |
| Configured `history` directory | Not imported as research. Existing authored artifact references and explicit maintenance operations may still refer to this directory. |
| Browser storage | Browser preferences and editing state; clearing it alone does not clear server-side research/orders. |
| Native worker | In-memory Nautilus cache and session state. Application SQLite is not proof of native crash/restart durability. |
| Maenifold memory | Separate durable knowledge/graph/structured-thinking corpus. |
| Alpaca | Broker balances, positions, orders, fills and history; outside a local reset. |

Both configured local data directories currently sit under
`C:/src/TradingAgents/.local-workspace/evidence/runtime-staging/20261017T024233Z-e3f9548d/`.
Read the launch configuration each time rather than assuming this path.
Credentials are external; never print or commit them.

### Existing local backup and restore controls

These are existing optional maintenance features, not prerequisites for trading.
In **Settings → Diagnostics → Local records**, backups include application
records and referenced evidence. Legacy maintenance archives can still contain
older research/checkpoint files; the desk does not use them for history or resume.
Credentials, Python environments, unrelated files and native memory cache are excluded.

Restore inspects a supported application ZIP (maximum 64 MiB) before an explicit
restore action. It retains current records before cutover, invalidates restored
approval authority, stops native execution and requires fresh reconciliation
and exact review. Broker records stay unchanged and saved pause choice is
preserved. Do not use restore to conceal a source/evidence failure.

### Purge unreferenced research artifacts

Stop Nautilus through the UI and stop the app server before cleanup. Keep
`desk.sqlite3`: its records contain settings, authored drafts and the bounded
`latest_research` cache. Trace file references from **every** `app_records`
record, then follow references inside those files until no new files are found.
Preserve this complete reference set, including chart and draft dependencies.

Delete only unreferenced research receipts, old research logs, continuation
arguments/results, measurements and research evidence snapshots inside the
configured application directory. The desk no longer uses its local
`decision-memory.md` or `cache/checkpoints`; remove those unused app-local files
as well. A UUID directory can contain execution or chart artifacts, so its name
or age is not enough to delete the directory. Verify resolved targets, reject
junctions/symbolic links, and compare retained file hashes after deletion.
Restart on 8098 and confirm the latest results and saved drafts still open.
Leave Maenifold, model caches, environments, credentials and broker records alone.

### Clear retained research or reset the app

Cleanup is destructive and is not a routine troubleshooting step. Use it only
when requested, and identify exactly which records should be removed.

1. Read the configured application/history paths. Verify resolved absolute
   targets and reject junctions/symbolic links before recursive deletion.
2. Stop Nautilus through the UI, then stop only the app server owning 8098.
   Confirm its registered workers exited.
3. To clear separate retained history, remove and recreate only the configured
   `history` directory. Research held in the application store remains.
4. For a requested full fresh local state, clear both configured directories.
   This removes local settings, drafts, lists and research, not broker records.
5. An empty application store needs initialization. The normal launcher rejects
   a missing SQLite store. Use the existing server entry point once with the
   exact configured paths, then return to the normal launcher:

```powershell
rtk proxy .\.venv\Scripts\python.exe -m tradingagents.web.server --port 8098 --data-dir <application> --history-dir <history> --nautilus-python <native_python> --alpaca-credentials-file <credentials_file>
```

Replace every placeholder from `tradingdesk.launch.json`. Do not delete source,
environments, credentials or broker records. Do not import unwanted old browser
lists into the new store. Verify the resulting empty views after restart:
deleting a directory does not clear an already-running process's memory.

### Troubleshooting by symptom

| Symptom | Check and response |
| --- | --- |
| Page says local service unavailable / failed to fetch | Check the existing 8098 server and its logs; don't start another port or assume displayed account data is current. |
| Nautilus stopped | Start it in Account settings; web/research availability is separate. |
| Account unverified or reconciliation incomplete | Inspect connection/account observations and discrepancies before new order commands. |
| Research uses the wrong model server | Inspect saved provider/model/endpoint, not just defaults. |
| Research has reports but is interrupted | Inspect Activity and capture status; a final text report is not sufficient. |
| Tool arguments rejected | Inspect the discovered command schema and retained validation details; don't label it a transport failure. |
| Old research survives reset | Check the application's `latest_research` cache and restart the app; clearing browser storage alone does not remove server-side results. The desk no longer imports historical research. |
| Saved state changed in another session | Reload the current revision before editing; don't overwrite concurrent changes. |
| No chart, scan or performance result | Check required retained source, coverage and job status; an empty result is not evidence of a calculation. |
| Order submission reply missing | Reconcile the command/client order identity with actual broker state before retrying. |
| Recovery-only page | Original records could not be opened; execution/native workers are unavailable. Address the actual store/permission problem without overwriting originals or inventing replacement data. |

## Source map

| Area | Entry points |
| --- | --- |
| Launcher and configuration | `Start-TradingDesk.cmd`, `Launch-TradingDesk.py`, `tradingdesk.launch.json` |
| Web/API and orchestration | `tradingagents/web/server.py`, `service.py`, `config.py` |
| Browser composition | `tradingagents/web/static/app.js`, `index.html`, `app.css`, `ui-*.css` |
| Charts | `web/static/market-chart.js`, vendored `lightweight-charts/5.2.1` and drawing plugin `0.6.2` |
| Research graph and analysts | `tradingagents/graph/`, `tradingagents/agents/` |
| Model adapters | `tradingagents/llm_clients/factory.py`, `chatgpt_client.py`, `openai_client.py` |
| MCP and research tools | `tradingagents/integrations/maenifold.py`, `agents/analysts/turn.py` |
| Source routing and social screening | `tradingagents/dataflows/router.py`, `dataflows/vendors/`, `agents/post_screen.py` |
| Native runtime and broker bridge | `web/nautilus_runtime.py`, `nautilus_worker.py`, `nautilus_v1.py`, `alpaca_readonly.py`, `alpaca_stream.py`, `alpaca_reports.py` |
| Proposals, groups and policy | `web/investor.py`, `baskets.py`, `linked_orders.py`, `approval_review.py`, `admission.py`, `execution_lifecycle.py`, `policy_evaluation.py` |
| Data/history/evaluation | `web/market_history.py`, `history_coverage.py`, `market_discovery.py`, `evaluation.py`, `evaluation_worker.py` |
| Persistence and outcomes | `web/app_database.py`, `store.py`, `workspace.py`, `decision_journal.py`, `performance.py`, `attention.py` |

Implementation details can be traced directly to:

- [Research graph and model allocation](tradingagents/graph/setup.py): `GraphSetup.setup_graph`.
- [Latest research admission and completion](tradingagents/web/service.py): `start_run`, `_run_with_evidence`, `run_detail`.
- [Gateway tool allowlists and validation](tradingagents/integrations/maenifold.py): `RESEARCH_COMMANDS`, `build_langchain_tools`.
- [Laya and Jev screening](tradingagents/agents/post_screen.py): `laya_screen`, `jev_screen`.
- [Native node and custom execution bridge](tradingagents/web/nautilus_v1.py): `build_node`, `ExecutionClient`; [worker](tradingagents/web/nautilus_worker.py): `Data`, `Execution`.
- [Basket targets](tradingagents/web/baskets.py): `preview`, `save`; [admission](tradingagents/web/admission.py): `approve`, `submit_approved`, `basket_admit`.
- [Chart, scan and strategy validation](tradingagents/web/evaluation.py): `prepare_chart_calculation`, `validate_strategy`, `prepare_experiment`, `execute_experiment`.
- [Scan discovery and scheduling](tradingagents/web/market_discovery.py): `discover`, `scan_definition`, `recover_scans`, `due_scans`.
- [Alert lifecycle](tradingagents/web/attention.py): `change`, `AttentionMonitor`.
- [SQLite records](tradingagents/web/app_database.py): `ApplicationDatabase`; [source artifacts](tradingagents/web/store.py): `DeskStore`.

### Documentation coverage

This guide was assembled from the primary checkout at `515ef0a` on 23 October
2026, with four domain readers and an independent reader checking their own
browser views and source. Inspection covered all nine workspaces, saved META
research, provider configuration, empty account/order/performance states and
existing analysis/maintenance controls. This establishes the documented labels
and source contracts, not successful execution of every scenario. No new broker
order, calculation, scan, optimization, simulation, backup or restore was run
for documentation. Ordinary navigation can autosave view preferences.

Current runtime defects belong in the existing local issues. In particular,
having one completed META record does not erase the later interrupted FANGMAN
batch or establish reliable execution of all research paths.

## Development and upstream attribution

Use the existing environments and current contributor instructions; this guide
does not authorize dependency installation, test runs, broker actions or new
features. The project declares Python 3.11+, LangChain/LangGraph, pandas,
yfinance and optional paper/evaluation dependencies in [pyproject.toml](pyproject.toml).
Nautilus is installed separately in the native environment.

This fork builds on Tauric Research's TradingAgents framework. Preserve the
[license](LICENSE) and third-party notices. See the
[upstream project](https://github.com/TauricResearch/TradingAgents) and
[research paper](https://arxiv.org/abs/2412.20138) for its original research
framework. Upstream demos, release notes and model-role terminology do not
override this desk's explicit approval and broker-submission workflow.
