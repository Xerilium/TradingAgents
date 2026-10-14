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
its stable client order ID. Unknown outcomes block new submissions; the desk
never retries a broker mutation automatically. Do not remove the journal to
clear an unknown outcome. Use one server process per data directory.

## Execution boundaries

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
that never create a run have no run artifact. Artifact publication and the final
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
