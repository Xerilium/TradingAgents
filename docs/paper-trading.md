# Paper trading desk

The desk is a local workspace for researching a stock universe and placing
reviewed Alpaca paper orders through Maenifold. It starts with FANGMAN: META,
AAPL, NVDA, GOOGL, MSFT, AMZN, and NFLX. There is no frontend build step.

## Start

Use the project's Python environment. Install the optional dependencies when
setting up a new checkout:

```powershell
rtk proxy uv pip install --python .venv\Scripts\python.exe -e ".[paper]"
rtk proxy .venv\Scripts\python.exe -m tradingagents.web.server
```

Open <http://127.0.0.1:8088>. Keep Maenifold running at
<http://localhost:8080/mcp> with its `alpaca`, `laya`, and `maenifold.memory`
Gateway domains available. The server binds to loopback only. Optional flags are
`--port`, `--data-dir`, and `--mcp-endpoint`.

The registered official Alpaca MCP server must explicitly set
`ALPACA_PAPER_TRADE=true`. The desk checks its Maenifold configuration and pins
the first verified account ID. This proves the registered server configuration;
the gateway does not expose an independent runtime endpoint attestation.
Switching accounts requires a separate data directory. Broker credentials stay
in Maenifold's server configuration and are never returned to the browser.

The desk defaults to `chatgpt`: it uses your existing ChatGPT sign-in through the
installed Codex CLI. If needed, run `codex login` and choose ChatGPT. No API key
or model endpoint is required. In Settings, select the fast/deep models available
to your Codex account. Research uses your account's Codex allowance and limits.
The adapter uses the [Codex app-server protocol](https://learn.chatgpt.com/docs/app-server),
including experimental dynamic tools. It returns tool requests to TradingAgents;
the graph executes the bound tools. It does not read or copy sign-in credentials.

For another provider, choose its name, fast/deep models, and optional endpoint in
Settings. Its provider credential must already be in the server's environment.
The desk does not collect API keys in the browser.
TradingAgents loads `.env` and `.env.enterprise` on package import, searching from
the working directory upward; already exported variables take precedence.
Restart the server after changing these files or its environment.
For a local model, select Ollama or OpenAI-compatible and provide its endpoint.
Both model tiers use the provider and endpoint shown in Settings; hidden tier
environment overrides do not change them.

For Azure, use provider `azure`, enter the resource endpoint in Settings (or set
`AZURE_OPENAI_ENDPOINT`), and set `OPENAI_API_VERSION` in the server environment.
The fast/deep model fields are your text-model deployment names. If
`AZURE_OPENAI_DEPLOYMENT_NAME` is set, it overrides both tiers; the desk requires
both displayed model fields to match it. Remove that override to select separate
deployments. An API key alone or an image-only deployment is insufficient.

## Daily workflow

1. Refresh the connection. Review account cash, holdings, market-data timestamps,
   and any source errors. Prices and candles use Alpaca's IEX feed.
2. Select a stock or run the configured universe. The existing TradingAgents
   analyst, debate, trader, and risk graph receives actual portfolio context plus
   an audited set of Maenifold memory, Laya, and Alpaca read tools.
3. Inspect the reports and recorded tool activity in Agent research. Laya checks
   evidence completeness and consistency. A failed run or a Laya result requiring
   human review cannot produce an executable order proposal.
4. Build the paper order plan. Deterministic Python code calculates share counts,
   price limits, cash reservations, and allocation limits from the rating and
   current broker book. Review each proposed order and explicitly submit it.
5. Refresh Trade & orders to reconcile broker status and fills. Cancel an order
   created by this workspace from the blotter. Pause prevents new submissions;
   it does not cancel existing orders or stop analysis.

The workspace preserves its configuration, reports, run history, and order
journal in `.paper-desk/` (gitignored). Interrupted runs are marked interrupted.
An interrupted or timed-out submission is marked unknown and reconciled using
its stable client order ID. Unknown outcomes block new plans and submissions; the desk
never retries a broker mutation automatically. Do not remove the journal to
clear an unknown outcome. Use one server process per data directory.

Order recovery uses the saved reviewed order and account-bound submission intent.
After Gateway schema validation and SDK initialization, a local dispatch callback
rechecks pause, unresolved submissions/cancellations, proposal eligibility and age,
New York trade date, pinned account, configuration, frozen order fields, completed
research/Laya approval, and the complete fresh book and quotes with the unchanged
execution validator. It performs no provider call or repricing. The exact intent
is saved before the single mutation; failed persistence or freshness expiring
during that save prevents dispatch. Legacy proposals without this reviewed binding
cannot be submitted. Create fresh research and a new plan instead.

Receipts must match the owned client ID, bound broker ID, symbol, side, finite
quantity and limit, limit type, DAY duration and regular-hours flag. Missing or
unsupported status, inconsistent fills, replacements, decreasing filled quantity,
terminal-status changes and contradictory duplicates preserve prior authoritative
evidence and block new mutations pending reconciliation. A generic error or missing
lookup never proves rejection. Reconciliation stops before targeted lookups or
updates if the current paper account is unverified, missing or different.

Cancellation has its own durable state: intent, requested, unknown, or resolved.
An acknowledgment means requested, not canceled. Timeout or interrupted intent
remains unknown across restart; repeat clicks cannot send another cancel. An open
or partially filled receipt does not resolve cancellation uncertainty. Only an
exact authoritative terminal receipt resolves it. Pause still allows guarded
cancellation and explicit Refresh. Cancellation verifies the current pinned
account and owned order independently of research or quote availability.
At dispatch it also rejects any newer contradictory account or paper-mode
observation published by Refresh, even when the persistent account pin is
unchanged. A harmless refresh or unrelated quote/research failure does not
invalidate the fresh cancellation verification.
Initial submission validation and both mutation dispatch callbacks acquire the
market lock before the journal lock, matching state snapshots. Both pre-save and
post-save checks remain inside that ordered critical section, so concurrent state
reads cannot invert these locks around intent persistence.

The blotter retains the last verified owned receipt when a broker list omits it,
with cancellation state alongside broker status. A browser timeout keeps mutation
controls blocked; use explicit Refresh to reconcile, never an automatic replay.
If the owned order became terminal before cancellation could be sent, its
authoritative terminal receipt clears browser uncertainty after Refresh without
requiring a cancellation record. Missing or conflicting receipts and unresolved
durable cancellation states keep actions blocked.
These source and offline safeguards do not attest the running broker process on
each request. Paper startup proof remains a separate supervised release gate;
offline verification is not live-order or deployment evidence.

## Consumed portfolio evidence

When an accepted run first passes its `PortfolioContext` to the graph, its full
run detail and journal retain `portfolio_evidence`: the exact cash, currency and
ordered positions (ticker, quantity and nullable average price), bound to the
preflight account ID, snapshot capture timestamp and analysis date. The existing
current-account description is preserved even for historical analysis dates.
This records the context actually supplied, including the existing USD currency
policy; it does not substitute the broker's currency or change graph input text.

A unique `reports/<run-id>/portfolio-context-<uuid>.json` stores the same context
with its SHA-256, byte count and relative path. Later refreshes and store reloads
do not replace it. Compact state carries the status/reference without the full
positions. If artifact writing fails, `journal_only` explicitly identifies the
remaining journal evidence. Legacy runs have unavailable/unknown context, never
holdings reconstructed from today's account. Accepted runs that have not supplied
a context to a graph also remain explicitly unavailable. Rejected preflight
requests and their attempt accounting remain outside this evidence boundary.
No credentials, raw Gateway configuration or full broker response is included.

## Execution boundaries

Known retryable Gateway reads and Codex rate-limit failures permit at most the
initial attempt plus three retries, with exponential automatic waits capped at
60 seconds. A finite server `Retry-After` (seconds or HTTP date) longer than
60 seconds is preserved and returned as a defer/error: no automatic sleep or
replacement request is made. The shared Gateway cooldown retains the full
deadline, including for other callers and retries already waiting when a
concurrent response extends it. Requests already in flight are not canceled.
Mutations are never automatically retried. Invalid/non-finite delays use the
existing 30-second default; past/zero delays retain the one-second minimum.
These rules do not expose or count hidden provider-internal attempts. The browser
displays and honors the full server cooldown, including deadlines beyond 60
seconds. Expiry restores manual actions only; it never replays a request or an
order. Invalid or unknown browser delays retain the 30-second default.
Explicit structured retry metadata takes precedence over generic 429 text or a
parent message, including nested error metadata and JSON-encoded MCP text blocks.
Text-only rate limits use the default only when no explicit delay is present.

Jev post screening retains its separate three-total-attempt policy and 30-second
automatic wait limit. A valid longer `Retry-After`, in seconds or HTTP-date form,
defers screening without sleeping or issuing a replacement request. Posts remain
available with the explicit unscreened disclosure and the HTTP failure and delay.
Malformed or non-finite delays retain the existing bounded jittered backoff.

The existing `POST /api/runs` endpoint accepts optional `analysis_date` in canonical
`YYYY-MM-DD` format, alongside `symbols` and `config_revision`. Omission or JSON
`null` uses the current New York date; the UI retains this default. Invalid or
future dates fail before account/provider access. For example:
`{"symbols":["META"],"analysis_date":"2020-01-02"}`.

Historical research retains that date through the integrated graph, MCP tools,
reports and Laya check. It still uses current account cash and holdings captured
at run creation, explicitly labeled in the run's `account_context` and the
graph's portfolio context. This is not a historical portfolio simulation.
Historical runs cannot produce paper order proposals; existing current-date,
account, configuration and submission freshness guards still apply.

- USD stocks, long positions, whole-share DAY limit orders, regular-session
  execution only. No shorting, leverage, options, or fractional orders.
- Default allocation 70%, cash reserve 20%, per-stock cap 15%, per-order cap
  $5,000, and limit-price buffer 25 basis points; all are configurable.
- Buy targets an equal share of the allocation; Overweight targets 75% of that
  amount. Underweight sells half the held whole shares, Sell sells held whole
  shares, and Hold/REVIEW creates no order. Existing exposure and open orders
  consume capacity; expected sale proceeds never fund purchases.
- Analysis must be completed on the current New York date. Order proposals and
  market quotes expire after 15 minutes; a quoted bid/ask needs its own valid
  timestamp. Fresh account, holdings, orders, paper mode, and asset eligibility
  are checked immediately before submission.
- Research is user-triggered. Account and market data refresh on demand;
  research progress polls locally. This release does not run an unattended
  trading schedule or stream exchange ticks.
- Alpaca paper fills are simulated. They do not establish how real orders would
  execute or how a strategy would perform with real capital.

## Verification

Accepted runs retain `measurements` in the existing journal and full run-detail
response. The start timestamp is the run request's entry to the service; elapsed
time ends after a durable terminal journal checkpoint. This includes
preflight, queueing and retry waits inside measured operations. Rejected requests
have their own request evidence without creating an accepted run. Artifact publication and the final
reference save are outside the reported interval.

Stage durations cover preflight, worker queue, per-symbol setup, graph analysis,
decision persistence and the direct Laya check. They are observed boundary times,
not a decomposition of every internal provider operation. Analysis includes its
existing source acquisition and memory work. Success, failure and cancellation
retain measurements; an interrupted process exports the last available journal
checkpoint on recovery, with unknown end time and elapsed duration left null.

The existing statistics callback counts logical LLM/tool starts, normal ends and
errors. Matching callback IDs prevent double counting when the same handler is
bound to both model and graph. Callback durations sum completed matched calls
and can overlap during parallel analysis; they are not wall-clock stage totals.
Direct source-prefetch calls and the direct Laya check do not emit these tool
callbacks. Provider-internal requests/retries are unavailable, not inferred from
logical counts. Token usage is labeled complete, partial or unavailable according
to exposed response usage; missing usage is null rather than zero. Existing CLI
statistics retain their original output fields.

Each terminal run writes a unique `reports/<run-id>/measurements-<uuid>.json`
under the desk data directory. `measurement_artifact` records its relative path,
SHA-256, byte count and format in the journal/full run response. Files are created
exclusively, so subsequent runs cannot overwrite previous artifacts. The payload
contains timing/counts only, without prompts, conversations, credentials, source
results or whole configurations. An artifact-write failure is explicit and keeps
available measurements in the journal. A filesystem failure that also prevents
journal writes cannot guarantee durability.

Startup also repairs terminal runs whose measurement finalization was interrupted.
It preserves their analytical status. A unique complete artifact matching the run,
request start and terminal status is reattached with its integrity reference. If
no unambiguous final artifact exists, recovery exports the durable journal
checkpoint and labels unknown final callback counts/end time/elapsed time as
unavailable; the recovery timestamp is not an analytical completion timestamp.
Existing artifacts are never overwritten or deleted. Once the reference is
durable, subsequent startups leave finalized and recovered measurements alone.
Recovery neither resumes research nor invokes providers or order operations.

Every service-admitted research request receives an evidence ID before validation.
The existing journal's `research_requests` collection keeps rejected requests
separate from accepted runs; accepted requests and runs link their IDs. Validation,
readiness, refresh, admission and scheduling have local stage receipts. The existing
recorder covers preflight Gateway boundaries, including copied contexts in the
existing refresh workers. Readiness is a local stage, not a count of hidden account
or provider requests. HTTP parsing/authorization failures before `start_run` remain
outside this scope. Original exceptions and response shapes are preserved.

Request elapsed time ends at acceptance/rejection; accepted-run elapsed time
already includes that interval and its existing queue interval. Do not add these
overlapping totals. Queue/worker timing stays in the linked run. Request snapshots
reuse `reports/<request-id>/request-measurements-<uuid>.json` and existing receipt
writers, with integrity references in the journal. They contain sanitized metadata,
not raw request bodies, readiness errors, settings or credentials. Recording failure
marks an evidence gap without changing request acceptance or its original failure.
If all writes fail, durability is unavailable. Interrupted preflight/still-running
calls recover as interrupted/unknown with unobserved end times left null. Late
receipts create new partial snapshots; previous snapshots remain immutable.

Memory input observations reuse `source_evidence` and the same bounded, screened
source artifacts. `graph_memory_state` records exact `past_context`/`memory_note`
values at their first observed state and each change, with presence flags that
distinguish missing from empty. This is an observed graph state, not proof that a
model consumed it. `pm_memory_input` separately records the actual Portfolio Manager
state-read boundary: `past_context` enters its prompt when nonempty; `memory_note`
does not enter that prompt. Missing `past_context` reads as the existing empty-string
default, explicitly marked absent. These artifacts do not add text to prompts,
settle decisions, change memory selection, or prove provider execution. Oversized,
unsafe or unwritable captures are unavailable, never silently redacted and labeled
exact. Source, Gateway and worker boundary counts remain separate; hidden provider
requests/retries remain unknown. Source partial/terminal/late snapshots use the
existing immutable evidence path, including recovery of interrupted observations.

The full run-detail response and journal also include `source_evidence` for
vendor functions executed through `route_to_vendor` and the social/OHLCV input
boundaries below during that run. Each actual
configured fallback attempt has its own ID, operation, selected vendor/function,
allowlisted supplied ticker/date arguments, start/end timestamps, elapsed time
and return/error outcome. Error receipts contain classifications rather than
exception text. These are function attempts, not underlying HTTP requests.
An execution-context binding follows graph child tasks and isolates concurrent
runs; no recorder remains bound after the run exits.

Successful function returns are saved once as unique
`reports/<run-id>/source-<attempt-id>-<uuid>.bin` files with format, SHA-256 and
byte-count references. UTF-8 text and bytes retain their content exactly; JSON
values use JSON serialization without a fallback string representation. Raw
source outputs are not included in the polling state or journal. Compact state
includes only evidence coverage, capture status and attempt count; inspect the
full run detail for receipts and the referenced local files for source results.

Capture has an 8 MiB per-response limit. Unsupported responses, credential-like
fields/markers, or storage failures are explicitly unavailable rather than
silently truncated/redacted. No raw headers, config, credentials or arbitrary
kwargs are intentionally recorded. Existing analytical return values, errors,
configured fallback and trading guards are unchanged by capture failures.
`capture_complete` describes recording only within this router scope, never full
source coverage or evidence quality. A successful vendor return can itself be
an empty-data/error sentinel. Partial receipts/files survive later analytical
failure; interrupted attempts remain marked as having an unknown final outcome.
Gateway supplemental sources and Jev screening have separate `gateway_evidence`
and `jev_evidence` below. Hidden SDK/provider retry attempts remain outside this coverage.
It is not a replay interface or a frozen
cross-application evidence snapshot.

### Run-scoped Gateway evidence

`gateway_evidence` records analyst-tool and final-Laya invocation parents, logical
executions, discovery scopes, and actual `transport.call_tool` attempts separately.
Each scope has an ID/parent, UTC start/end and monotonic elapsed time. Transport
ordinals and retry/defer decisions record observed attempts only; an existing
cooldown can reject a logical call with zero transport attempts. Retry sleeps are
outside transport durations. These counts overlap and must not be added together.
MCP transport invocations do not establish HTTP-request or internal model-execution
counts; those fields remain null (unknown).

Payload capture is explicitly limited to Alpaca asset/clock/calendar,
portfolio-history, stock bars/latest quote/latest trade/snapshot/news reads,
Maenifold SearchMemories/ReadMemory, and Laya decide. Actual bound parameters and
normalized results are captured without changing caller values. Transport results
are labeled SDK-envelope serializations, never original wire bytes. Account,
configuration, order and unreviewed commands are metadata-only, as is discovery.
No catalogs, GetConfig parameters/results/error text, registration payloads or
credentials are archived. Eligible payloads pass the existing 8 MiB limit and
credential screening; unsafe, oversized, unsupported or unwritable evidence is
an explicit gap, not a change to the caller's result or exception.

Immutable `gateway-receipt-*.bin` JSON artifacts preserve scope observations and
screened payloads with hashes and byte counts. Run-terminal `gateway-evidence-*.json`
snapshots preserve the known receipt references/counts. Later observations append
new snapshots and are labeled late; they never replace the terminal snapshot or
make its incomplete evidence complete. Pending counts refer to scopes, not unique
requests. Timeout/cancellation retains unknown outcomes; restart marks unfinished
scopes unknown without inventing an end time. Compact state omits full receipts
and snapshot history. Full run detail and the report directory retain them.

The final Laya guard's exact questions, criteria, high threshold and strict
grade-plus-two-boolean predicate are unchanged. `use_cache` remains omitted;
capture does not override the server default. Returned cache/usage metadata is
retained when safe, but a Gateway call is not proof of a model execution. This
coverage starts inside accepted run workers. Rejected preflight ownership and
hidden SDK/provider attempts remain separate gaps. Offline fixtures
verify these boundaries; no live capture coverage is claimed.

### Jev worker and POST evidence

`jev_evidence` separately counts screening batches, worker jobs and observed
`requests.post` invocations. Jobs have IDs and post indices before submission,
queued/start/end timestamps, and parent links to their batch. Each worker and
cancellation callback receives its own copied recorder context. Only confirmed
`future.cancelled()` outcomes are labeled cancelled; these queued jobs have zero
POST attempts. Existing active workers continue after the unscreened fallback,
without a new wait, stop or retry policy. A returned worker answer does not prove
that screening used it: the batch records `screening_applied` and its keep flags.

POST receipts retain the actual JSON body (state, selected model, questions),
attempt ordinal, request start/end and monotonic duration, status or safe error
class, and the selected retry/defer/wait. Request timings exclude retry sleeps
and JSON parsing; the enclosing attempt duration also covers parsing. Existing
jitter is sampled once, and three total attempts and long-delay deferral remain
unchanged. Timeouts and connection failures leave remote outcomes unknown.

The payload from the existing single successful-response `json()` call is
captured before validation, including safely returned model/cache/usage metadata.
Error bodies are not additionally read or parsed. Headers, authorization,
environment contents, raw configured URLs, cookies, request objects and exception
text are excluded. The existing size and credential screening applies; capture
gaps cannot change the actual answer, filtering or unscreened fallback.

Screened `jev-receipt-*.bin` artifacts and `jev-evidence-*.json` snapshots reuse
the existing immutable writer and SHA-256 references. Batch/run snapshots remain
unchanged when late observations append new snapshots. Queued/running scopes keep
recording incomplete; late or unknown outcomes cannot make it complete. Restart
retains unfinished work as unknown without inventing an end time or replaying it.
Compact state carries counts/completeness, not receipt bodies or snapshot history.
Counts describe application POST invocations, not redirects, adapter retries,
server receipt or internal model passes; hidden request/model counts remain null.
Legacy runs without `jev_evidence` are unrecorded, not proof of zero screening calls.
These boundaries have offline fixture coverage only, not live verification.

StockTwits captures the existing response body bytes before JSON filtering or
screening. Reddit captures the existing capped RSS response bytes before XML/HTML
normalization. Transport errors retain safe classifications; malformed bodies
that were successfully read remain inspectable even if parsing later fails.
Neither adds a request or changes Reddit's existing retry policy.

OHLCV capture retains the frame returned by the existing cache read, before cache
eligibility checks, or the frame returned by the Yahoo SDK history/retry boundary,
before index reset, cleaning, date filtering or gap filling. Origins are explicitly
`http_response_bytes`, `parsed_cache_dataframe` or `yahoo_sdk_dataframe`; a cache
frame is not the original CSV bytes and an SDK frame is not underlying HTTP.
A cache candidate may subsequently be rejected. No mutable cache is reread for
evidence. These inputs also cover the existing verified-snapshot path through
`load_ohlcv`; calculated snapshot/analyst Markdown is not substituted for input.

Nested receipts carry `parent_attempt_id` and `boundary_kind`: a source boundary
inside a router attempt is overlapping evidence, not another provider request.
The SDK retry wrapper remains opaque. Raw acquisition may contain rows/posts
later excluded by the existing as-of filters; capture does not feed them back
into analysis or alter those filters.

DataFrames use `pandas-frame-v1-json`, a non-executable tagged representation.
It retains ordered axis labels/names, index kind/range/frequency, column dtypes
(including NumPy byte order and supported string storage/missing semantics),
and per-cell values. Numeric scalars use exact binary hex or decimal integers;
timestamps use nanoseconds plus timezone; `None`, `pd.NA`, `pd.NaT` and floating
NaN bits remain distinct. No pickle or lossy display-string conversion is used.
Supported frames have simple/Range/Datetime axes and numeric, boolean, object
with supported scalar values, string, nullable numeric or datetime columns.
MultiIndex, categories, arbitrary objects/attributes, unsupported timestamp
ranges/types, more than 100,000 cells/axis entries, or serialized payloads above
8 MiB produce explicit gaps. Source objects and analytical returns are unchanged.

Credential-marker screening checks the original UTF-8 text and bounded decoded
views for HTML/XML entities and JSON string escapes, including nested escaped
key delimiters. At most four decoding passes are allowed; deeper unresolved
encodings and non-UTF-8 bodies are explicit unsupported captures. This is a
targeted screen, not complete secret detection. Safe artifacts always retain
their original bytes and hashes, never the decoded screening view. Numeric axes
are read as positional array scalars so float32/float64 NaN payloads (including
signaling bits), signed zero and large integer labels avoid Python float coercion.

```powershell
rtk proxy .venv\Scripts\python.exe -m pytest
rtk proxy .venv\Scripts\python.exe -m ruff check tradingagents/web tradingagents/paper tradingagents/integrations
```

The new tests use an injected broker and scripted graph; they never place real
or paper orders. Live connection checks are separate evidence from simulated
workflow tests. Missing model credentials prevent live research validation even
when the broker account and market data are connected.

On Windows, the existing suite requires test caches outside the user home.
If the default Windows temporary directory is under your home, run the suite
with a process-local temporary directory instead (no system setting changes):

```powershell
rtk proxy .venv\Scripts\python.exe -c "import tempfile, pathlib, pytest; p=pathlib.Path('.paper-desk/test-temp').resolve(); p.mkdir(parents=True, exist_ok=True); tempfile.tempdir=str(p); raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp', '.paper-desk/pytest-run']))"
```

## Design references

The linked watchlist, chart, account view, and explicit preview/submit sequence
draw on Fidelity's [Active Trader tools](https://www.fidelity.com/products/atbt/help/ActiveTraderTools_Getting_Started_Help.html)
and [trade workflow](https://www.fidelity.com/products/atbt/help/ActiveTraderTools_Trade_Help.html).
Simulation limits follow [Alpaca's paper-trading documentation](https://docs.alpaca.markets/us/docs/paper-trading).
These references informed the workflow; the implementation and visual design
are tailored to this project.

The portfolio boundary also follows the recorded
[Trader source contract](memory://research/tradingagents/printer-trader-source-contract-20261013):
missing holdings are not an empty portfolio, research opinions do not own sizing,
and tool execution must be distinguished from accepted model output.
