# Local TradingAgents desk: launch, use and handoff

Current installation documented on 20 October 2026. Start from the
[README](../README.md); agents must also read [AGENTS.md](../AGENTS.md).

## What we built

The browser app combines a configurable stock universe, Alpaca account and price
observations, saved TradingAgents research, local order proposals and baskets,
and a decision journal. NautilusTrader is the trading engine. Its adapter talks
to the configured Alpaca account. Research is advisory; approving exact order terms and
submitting them are separate actions.

### Fractional quantity orders

Manual proposals accept exact share quantities with up to nine decimal places.
New fractional orders require an observed active, tradable US-equity asset with
`fractionable: true`; that receipt and its provenance are bound to the exact
approval and checked again against the native session's asset metadata at dispatch.
Simple fractional DAY orders support regular-session MARKET, LIMIT, SELL
STOP_MARKET and BUY/SELL STOP_LIMIT, plus eligible extended-session LIMIT orders.
Extended fractional orders also require observed `fractional_eh_enabled: true`.
BUY STOP_MARKET remains unavailable; enter
an explicit reviewed stop-limit trigger and limit. Fractional linked orders and
GTC are rejected before approval. Per-order approval and separate submission remain.

The native mapping uses the public generic Instrument with EQUITY/SPOT/USD and
multiplier 1, retaining the observed equity price tick and native equity defaults.
Its nine-place size precision and 0.000000001 increment are the reviewed broker
precision contract, not fields returned in the asset receipt. Existing whole-only
instruments retain Equity. Actual fractional holdings/fills are preserved even
when current fractional eligibility is unknown or false; representation does not
grant authority for new orders. Native modeled fee defaults do not establish actual fees.

Fractional replacement preserves the exact total quantity, including prior fills.
Supported price-only amendments omit quantity from the broker PATCH. Fractional
MARKET replacement is unavailable; cancellation remains a separate exact action.
Dollar/notional sizing, fractional basket allocation, and fractional simulation
remain separate open contracts; the current basket allocator and simulation use
whole quantities. No fractional broker acceptance or native dispatch/fill behavior
has been observed for this source change.

Sources reviewed 21 October 2026: [fractional trading supported-order section](https://docs.alpaca.markets/us/docs/fractional-trading),
[20 August 2024 fractional stop/stop-limit changelog](https://docs.alpaca.markets/us/v1.1/changelog/support-for-fractional-usd-stop-stop-limit-lct-stop-stop-limit-limit-with-extended-hours-orders),
and [replace-order API](https://docs.alpaca.markets/us/reference/patchorderbyorderid-1).
The specific supported-order section and dated changelog take precedence here
over the contradictory market-only footer and generic POST quantity description.

Bounded serialization observation, 21 October 2026: one native-Python `-c` command
opened the retained G14 SQLite snapshot read-only and immutable, selected investor
revision 91, and read its retained AAPL instrument plus the saved Alpaca asset
receipt. It called production `native_types.Equity(fractional_precision=True)`,
`native_dict`, public `Instrument.base_from_dict`, then `native_dict` again.
Nautilus 1.231.0 preserved the complete mapped dictionary: EQUITY/SPOT/USD,
multiplier 1, lot 1, price precision 2/tick 0.01, size precision 9/increment
0.000000001, and both timestamps 1792529159876523700.

Inputs under `.local-workspace/evidence/g14-isolated-preview-20261022T013846Z-d9706311/`:

- `post-run-records.sqlite3`, SHA-256 `e239bbb338d6921f3ff1febd699f8ad8507e18f09d002c2e1fb24f5132b50a73`;
  investor payload `0f40babc8648608a73d02d19a6bc5f97819a7d36993c2da2021aba103a70d173`.
- `/baskets/0/history/0/evidence/observation/market/AAPL/instrument`, canonical
  sorted compact JSON SHA-256 `7136727a613d966b5dada80e143b70c77ee5c8cb3b3ade4a1c9f59469ea59b4e`.
- Saved `history-coverage-source-481a4321-1809-4b88-b30d-96af0dd71269-6166f3b9-1fb0-4381-a9c1-9d12ba58217a.bin`
  asset receipt, SHA-256 `69bc7e35c12d1e42f5f49f34f38b32ea9755b7623806f7b263f697b097822995`.

Mapped and restored sorted compact JSON both hashed to
`bf32256f27479a3e3801988c441199ca278f0307be969b076548e86c8ff57ad4`.
The schema includes classification, identifiers, price/size precision and increments,
multiplier, lot, limits, margins, modeled fees, timestamps, tick scheme, and info.
This proves that retained-input serialization path only. It does not prove order
dispatch, risk admission, fills, broker acceptance, or fractional simulation.
The single static cycle passed AST parsing for nine changed Python files, browser
JavaScript syntax, and scoped whitespace checks. Unrestricted Ruff reported 58
findings; its captured output was truncated, so full lint is not claimed clean.

### Saved-plan simulation profile

The Decision journal has **Simulate a saved plan**. Load local plans/data, select
an exact revision and a complete raw daily-history receipt, and enter starting
cash, timezone-qualified dates, decision availability, fees, fill probabilities,
random seed and latency. Review the explicit USD scenario assumption and empty
starting portfolio. **Save simulation preview** retains the immutable inputs;
only the separate **Run this simulation** action launches isolated Nautilus.

This initial profile supports BUY whole-share regular-session MARKET, LIMIT and
STOP_LIMIT plans with DAY/GTC and optional saved linked exits. SELL starting
holdings, BUY STOP_MARKET broker conversion, dividends, corporate actions and
benchmark comparison are unavailable. Daily OHLC ordering is a declared model;
it cannot establish which target/stop occurred first. Brackets activate after
FULL entry fill. DAY cancellation occurs after the next sourced session close,
with zero assumed latency; this does not reproduce intraday broker expiry.
Historical scenarios explicitly label hindsight when the saved revision was
created after the selected decision time. Actual fees remain unknown.
Source OHLC decimal precision is preserved by lossless padding; the simulated
instrument keeps a one-cent tick. Preview/result record that representation;
the isolated worker checks the installed native precision limit before running.

Simulation indexes live in the existing reporting record under `simulations`;
preview/result artifacts use the existing `reports/<simulation-id>/` mechanism.
They remain separate from order approvals, broker commands and account returns.
Restarted unfinished simulations show interrupted and never resume automatically.
Closing the service or attempting restore terminates only its registered simulation
children; restore also invalidates the prior simulation session.
The configured native Python runs without inherited provider credentials. One
isolated observation used Nautilus 1.231.0 and five bars: BUY 1 LIMIT USD 100 DAY
was canceled on 13 October after the initial 12 October session, with zero fills;
the USD 100 reservation was released and cash remained USD 1,000. This exercises
that bounded cancellation/account path, not the other order/fill scenarios or
broad browser acceptance. See the retained
[observation](../.local-workspace/evidence/g14-isolated-preview-20261022T013846Z-d9706311/run-observation.json)
and [terminal response](../.local-workspace/evidence/g14-isolated-preview-20261022T013846Z-d9706311/run-terminal-response.json).

The current installation uses Nautilus 1.231.0 with its in-memory cache and SQLite
for application records. Redis and LEAN are not required. The 503-symbol S&P 500
universe is saved configuration, not a hardcoded stock list. Settings accepts up
to 1,000 symbols, including CSV/text imports.

## Connection identity and reconnect

The page header distinguishes configured intent from the account observed in
the current native session: **Paper trading**, **Live trading**, or **Account
unverified**. A disconnected/stale observation does not verify an account mode.
Mode is established from the official trading origin and authenticated account
observation, not from static branding or a paper-fee assumption. Command transport
availability and per-order readiness remain separate checks. Isolated saved-plan
simulations are separate from either broker account mode.

Only `https://paper-api.alpaca.markets` and `https://api.alpaca.markets` are valid
trading origins. HTTPS port 443, trailing slashes and a trailing `/v2` are
normalized to those origins; other ports, paths, schemes, query strings,
fragments and embedded credentials are rejected. Trade updates use the matching
`wss://paper-api.alpaca.markets/stream` or `wss://api.alpaca.markets/stream`.
Market-data reads retain the separate `https://data.alpaca.markets` origin.
REST and trading-stream redirects are rejected; authentication is not forwarded
to a redirected trading destination.
Sources: [official SDK origins](https://github.com/alpacahq/alpaca-py/blob/master/alpaca/common/enums.py)
and [trade-update streaming](https://docs.alpaca.markets/us/docs/websocket-streaming),
accessed 21 October 2026.

The native worker loads one private, immutable endpoint/credential set shared
by REST observation, submission and stream authentication. Editing the file
cannot retarget an already-running session. Stop and start the native connection
explicitly to apply changes; complete fresh account reconciliation and renew
unsubmitted order approvals. Every replacement worker has a new opaque authority
session even if its credentials are unchanged. Ordinary network/stream reconnect
within the same worker retains that binding and existing freshness checks.
Working orders and historical group approvals remain retained for monitoring
and recovery; this does not cancel orders or recreate exits. A new amendment
requires its own current exact review. Private credentials and credential-derived
values are not written into approval records or public connection metadata.

The documented zero-commission model is restricted to eligible direct paper
equity fills. Live fees require actual supplied evidence; missing fees remain
unknown and can block complete native fill reconciliation. G07 source/static
verification does not establish a live connection or live execution acceptance.

## Launch the existing installation

1. Open `C:\src\TradingAgents\Start-TradingDesk.cmd`, or run:

   ```powershell
   rtk proxy C:\src\TradingAgents\.venv\Scripts\python.exe C:\src\TradingAgents\Launch-TradingDesk.py
   ```

2. Open <http://127.0.0.1:8098>. The launcher reuses a matching running service
   or starts it with the configured data directories. It does not install
   packages, migrate records or stop another service occupying the port.
3. Expand **Nautilus connection**. If stopped, choose **Start Nautilus**. Wait for
   connected account status and prices before relying on current observations.
4. Confirm the account is paper, check cash/equity/buying power, and inspect
   missing prices and timestamps. A refreshed account does not mean a new market
   price event, particularly while the market is closed.

This is an existing-installation procedure, not a clean-machine installer.
A Git clone alone lacks the local data, environments and credentials.
Do not run `python -m tradingagents.web.server` without explicit configuration:
its default port and data location differ from this installation.

**Stop Nautilus** disconnects the engine; the web app and saved research remain
available. Closing the browser does not stop the web server. Stop only the
identified local app processes when maintenance requires taking it offline.

## Where things live

`tradingdesk.launch.json` is the authority for this machine's configuration.
It is ignored by Git and contains paths, not credential values.

| Item | Current location / purpose |
| --- | --- |
| App code and launcher | `C:\src\TradingAgents` |
| Web app Python | `.venv\Scripts\python.exe` under the checkout |
| Nautilus Python | `.venv-nautilus-v1\Scripts\python.exe` under the checkout |
| Application data | `.local-workspace\evidence\runtime-staging\20261017T024233Z-e3f9548d\application` |
| Saved history | Same staging folder, sibling `history` directory |
| Credential file | `C:\src\printer\apps\tradingagents\.env`, existing `ACPA_*` keys; never publish values |
| Launcher logs | `.runtime-stage\launcher.out.log` and `launcher.err.log` |
| Preserved local evidence and backups | `.local-workspace` and existing repository-local backup folders |

The application, history and native Python moved out of `C:\src\printerv2`.
Old paths inside dated evidence remain provenance, not launch instructions.
The old directory was empty but locked during migration. Python base runtimes
remain installed under the user's Windows/uv directories. Credentials remain
in `C:\src\printer`, which is a different folder from `printerv2`.
The separate dependency smoke audit must be consulted before claiming every
auxiliary environment launcher has been cleaned of old references.

Preserve these local files when moving the checkout. Do not replace them with
fresh data or commit databases, credentials, environment files or backup archives.

## Everyday workflow

| Page | How to use it |
| --- | --- |
| Portfolio overview | Check account balances and holdings; scan the universe using search, filters, sorting and columns. Select stocks to organize watchlists. Open a stock's market evidence and available charts before relying on an agent recommendation. |
| Agent research | Choose an existing run and stock. Read the reports, debate and final decision; inspect source dates and failures. Record human review disposition and priority. Saved reports do not become current research merely because today's price changed. |
| Orders and drafts | Create or review a local proposal or basket. Check symbol, side, quantity, order type, limit price when applicable and time in force. Read readiness reasons. Approve exact terms, then separately Submit only when intentionally placing an order. |
| Settings | Edit the named universe or import a Symbol/Ticker CSV or text list, review and save. Model/provider changes apply to future research. Connected-service status identifies the account and price feed. |
| Decision journal | Inspect saved decisions, research links, proposals and baskets. Record follow-up notes and export selected records. Reporting uses available records and configured periods; absent data is not fabricated performance. |

The research provider can use the existing Codex ChatGPT sign-in (`chatgpt`).
Maenifold's configured default endpoint is `http://localhost:8080/mcp`; it serves
research integration, not the Nautilus engine. New research can require that
service and provider authentication. No new research was run in the latest UAT.

**No approved order** means there is no currently approved proposal; it does not
mean the account is globally disabled. **Pause new orders** is an explicit
operator choice and does not cancel working orders. Cancel and Replace are
broker actions, not harmless smoke-test buttons. Unknown fees remain unknown.

### Purchase with linked exits

When preparing a BUY, optionally enter a **profit target**, a **stop trigger**, or
both. A stop trigger alone creates a stop-market exit; adding a stop limit creates
a stop-limit exit. Prices are USD, linked-order quantities remain whole shares, and execution
uses regular sessions. Choose DAY or GTC. Save and review the complete entry and
exit terms, approve that exact revision, then separately Submit. The adapter sends
one broker-managed Alpaca OTO (one exit) or bracket (two exits) through a native
Nautilus order list. Research agents do not acquire submission authority.

Alpaca activates the exits only after the entire entry fills. A partial entry is
not protected by the held exits. Canceling a partially filled entry can leave a
position without active exits. The orders table shows parent/child identities,
held versus active exits, and temporarily inactive orders awaiting the next
session. Mutually exclusive exit legs reserve the shares once; they do not count
as two planned sales or reduce the purchase's exposure estimate.

DAY orders expire for the trading session. GTC is not permanent: Alpaca applies
its aged-order policy (currently 90 days); inspect the broker's `expires_at` when
provided. Linked orders are DNR/DNC: prices are not automatically adjusted for
dividends or other corporate actions. A stop-market execution price is not
guaranteed; a stop-limit order may not execute. A rapid market can fill both OCO
exits before cancellation completes.

Cancel explicitly authorizes the selected broker order; Alpaca can cancel its
remaining linked orders as well. Bracket/OCO exit amendments require a newly
saved and approved exact price revision, keeping quantity, side, type, duration,
and group membership unchanged. Alpaca does not support OTO replacement; the app
rejects it. Review the remaining position and exit coverage after cancellation.
Held bracket exits from an approved app purchase support price-only amendments
through a new exact review and approval. Review binds the working purchase,
both held exits, broker/native identities, versions, quantities and prices.
The complete revised purchase/exit group is assessed using its existing cash
reservation. This conditional authority cannot submit an independent SELL or
relax ordinary owned-share checks. Any group fill, cancellation, resize or
replacement invalidates the review. A partially filled purchase remains
unprotected until Alpaca activates the exits after the complete entry fill.
Imported groups without the original app approval cannot use this held path.
Reconnect rebuilds native orders and actual fills from broker identities and
retained receipts, without recreating or resubmitting exits. Missing/conflicting
facts remain reconciliation gaps.

Sources: [Alpaca order semantics](https://docs.alpaca.markets/us/docs/orders-at-alpaca)
and [Nautilus linked orders](https://nautilustrader.io/docs/latest/concepts/orders/advanced/),
accessed 21 October 2026. This section describes the source implementation;
runtime activation and real broker lifecycle behavior require separate evidence.

### Existing holding exits and standalone stops

In a held stock's ticket, choose **Prepare exit**, then enter the whole-share
quantity and your prices. Available quantity is calculated by the server after
recorded reservations, with OCO alternatives counted once; it is distinct from
the held quantity. An unavailable or unreconciled source does not imply free
inventory. A target alone is a SELL LIMIT. A stop alone is a SELL STOP_MARKET, or
STOP_LIMIT when you also enter a limit. Both prices create one broker-managed
OCO pair: the original SELL LIMIT target and a linked stop for the same shares.
There is no new purchase or entry-fill activation step. Sale proceeds do not
fund another order before actual execution.

The exact approved OCO target equals the root limit price. Price amendments and
group cancellation use the existing approval and broker identity paths. Broker
quantity reductions after partial execution are retained separately from the
immutable approved maximum, including reductions of the root target. Reconnect
uses those identities and actual fills; it does not submit a replacement pair.

Standalone SELL stops and explicit BUY STOP_LIMIT orders support DAY/GTC and
regular sessions. Enter the exact trigger and, for STOP_LIMIT, the limit. BUY
stop limits must be at or above their trigger; SELL stop limits at or below it.
A triggered stop-market can slip; a stop-limit can remain unfilled.

BUY STOP_MARKET submission remains unavailable. Alpaca's
[versioned documentation](https://docs.alpaca.markets/us/v1.1/docs/orders-at-alpaca)
describes conversion to a stop-limit; the current unversioned page omits that
conversion. The app does not infer a limit or silently change the approved type.
Choose an explicit BUY STOP_LIMIT and enter its limit for a supported submission.
BUY stop estimates use at least the higher of the dated price and stop trigger;
this estimate is not a guaranteed fill-price cap. This mapping gap remains open.

The next offline batch extended the same three authorized test functions, with
no new test functions or harness. Existing-holding OCO, ordinary holding targets,
SELL stop-market/stop-limit, explicit BUY stop-limit, DAY/GTC, and the BUY
stop-market rejection passed the real review/admission and mocked REST boundary.
The recovery scenario passed positive historical-child supersession and rejected
mismatched native side/type without changing the historical receipt. A temporary
fixture reconciliation omission was corrected before that pass. The reservation
scenario passed OCO root auto-reduction while preserving the approved quantity;
its first attempt exposed an ordering error in the added fixture, corrected and
rerun alone. Bounded Python/Ruff and JavaScript syntax checks passed. These are
offline source checks, not evidence of an actual broker fill or app activation.

Offline checks on 21 October 2026: the three functions in
`tests/test_linked_exit_orders.py` passed under the installed Nautilus Python.
They exercise real draft/review/approval/admission records, native order-list
construction, one mocked submission, exact-term tampering rejection, partial
entry and OCO reservations, stable child identities, a reviewed stop-limit price
amendment, fill-report conversion, and explicit cancellation without transport
retry. Python syntax, bounded Ruff correctness checks, JavaScript syntax, and
`git diff --check` passed. Windows sandbox temp access blocked two fixtures on
the first attempt; the unchanged command passed with temp access permitted.
No real broker request, running app activation, visible UI interaction, native
risk-engine dispatch, native fill accounting, or complete disconnect/restart
scenario was exercised. The positive current-observation supersession path still
needs runtime evidence; these checks do not establish broker lifecycle readiness.

## Native risk limits and cached reports

In **Orders**, open **Native risk limits and cached reports**. The risk section
shows actual native engine getters: bypass state, trading state, submit/modify
rates and per-instrument notional caps. An empty cap list means none configured.
Stale or disconnected state does not supply current risk values. These settings
do not replace exact order approval, account reconciliation or investor policy.

Choose a native table and select **Capture native table** to read the existing
worker cache. This action makes no provider refresh. All captured rows remain
available through paging and the complete JSON download. Numbers are strings;
timestamps retain ISO and nanosecond forms. The report records worker epoch,
capture time, reconciliation, recovery coverage and fee sources. A complete
table does not establish complete broker history. Native modeled fees do not
establish actual zero fees. Captures from a previous worker or restored store
remain labeled historical. No reports are captured automatically.

## Decision-linked position outcomes

In Orders, expand **Native risk limits and cached reports**, choose **positions**,
then select **Capture native table** explicitly. This reads the native cache without
refreshing a provider. In Decision journal, use **Reload saved journal** to inspect
the retained position lifecycles. No position report is captured automatically.

Each lifecycle appears once, with links from all contributing commands and exact
proposal revisions. Multiple entries, partial exits and linked legs do not receive
duplicate copies of the position profit. Original rationale and saved research
references remain attached to their contributing decisions. Reopened positions and
different account modes are separate identities; ambiguous membership is flagged.

Native realized P&L already includes applicable settlement-currency commissions;
the UI does not subtract them again. Realized and dated marked unrealized P&L,
currencies, native snapshots, source precision, fees and capture epochs remain
separate. Actual, modeled and unknown fee provenance is shown; actual net profit
remains unavailable without complete supported costs and attribution. No FIFO,
pro-rata cost assignment or missing opening basis is invented. Coverage gaps explain
missing history, identity or membership. A cached mark is not guaranteed fresh.
When complete opening, membership, history, reconciliation and actual commission
proof support it, the native net outcome is shown without another fee deduction.
Its accounting scope is distinct from broker-statement or tax-lot performance.
Execution details retain real quantities, prices, times, order/execution IDs and
fee proof; captured order status does not invent historical partial-fill labels.
Observed native figures remain visible with provenance when exact net or decision
allocation is unavailable, including unattributed observations. Missing thesis links
are shown separately from financial coverage; no thesis or profit allocation is invented.

This source integration has not been accepted through a new report capture,
filled position or broker action.

## Exact saved alert evidence

Use **Open exact alert evidence** in the attention list, **Open evidence** beside a
browser attempt, or click a notification to open that occurrence. All three open
the same saved occurrence ID. They do not open a current order ticket, acknowledge
the alert, rerun research or refresh a provider.

New occurrences retain the exact rule revision/parameters, evaluated values and
threshold or age calculation, source availability/reason, basis/feed and available
source IDs/timestamps. Ephemeral price/account inputs are retained observations,
not invented receipts or independently verified historical prices. A missing or
stale source can itself be the valid triggering evidence; no artifact is required
to preserve the observed absence or staleness.

Retained sources are resolved only from the captured artifact/hash, exact research
run/symbol/revision/digest, run-scoped market inputs, or exact proposal-history
revision/terms digest and evaluated conditions. A replaced same-key history cache,
newer report or revised proposal is never substituted. Partial market/indicator
resolution is labeled partial. Missing full sources leave the original evaluated
facts readable. A different/unrecorded capture generation prevents full-source
association with the active profile. Legacy occurrences without bindings remain
readable as saved evaluations, with exact source evidence explicitly unavailable.

The existing trigger latch, acknowledgment, pause/resume, rule revisions and
explicit failed-notification retry behavior are unchanged. This source batch has
not been exercised through actual alerts, notifications or source-reader requests.

## Browser alert notifications

Rules continue to use the existing attention monitor and saved occurrences.
In the overview, open **Browser notifications**, then select **Enable browser
notifications** to request browser permission and opt in for this profile.
Notifications are off by default. Enabling starts a new cursor without replaying
the unread backlog. Tabs sharing the profile claim each occurrence once.

The desk and page must remain running. Background browser throttling and system
settings can delay or suppress notifications; closed-browser push and email are
not configured. The existing state poll is reused, with no second evaluator.
**Requested** records a best-effort browser display attempt, not confirmed
delivery or reading. Failed attempts require **Retry failed notification**;
uncertain attempts are not silently replayed. Click a notification or **Open
evidence** to review its stock/source context. Reading acknowledgment remains
separate. Denied or unavailable browser permission is shown explicitly. Restoring
records disables notification opt-in; enable again to start from the current time.

## Alpaca funding and official documents

Settings shows the configured account mode and the currently verified observed
account beside **Open Alpaca dashboard**. The link opens only
`https://app.alpaca.markets/account/login`; no account identifier or credential
is included. Sign in and select the intended account in Alpaca. That portal's
selection is independent of this desk's pinned connection.

On a live account, choose **Funds & Wallet** for bank linking, deposits and
withdrawals. Paper balances use virtual funds. Choose **Account** for statements,
trade confirmations and available tax forms. Local CSV exports and retained
activity records are not official broker statements or tax documents.

These are broker-owned workflows. The app does not log in, transfer money,
create a brokerage account or implement Broker API document/funding services.
Its existing Trading API credentials do not establish partner entitlement.
Portal access, account matching and document availability have not been exercised
by this source change; broader G16 account/broker capabilities remain open.

Official navigation references: [funding guide](https://alpaca.markets/learn/fund-live-trading-account),
[statements](https://alpaca.markets/support/statements-alpaca) and
[tax documents](https://alpaca.markets/support/tax-documents), accessed
21 October 2026. Only the broker login URL is linked from the product handoff;
no undocumented dashboard deep links are assumed.

## Daily chart and US equity discovery

The overview's stock evidence panel uses a locally served Lightweight Charts
5.2.1 build for daily candles, volume, recorded moving averages, pan, zoom and
crosshair inspection. The recorded-session selector and exact OHLCV text remain
available alongside the chart. Saved research artifacts and current-market IEX
cache entries remain separate contexts with their own dates and provenance.
Saved research inputs remain daily. Current-market history offers `1Min`, `5Min`,
`15Min`, `30Min`, `1Hour` and `1Day`. Selecting an interval or cache reads retained
data only; **Request this stock’s chart range** explicitly collects that interval.
The required 252-session baseline, benchmark, simulation and policy histories remain
daily. An unkeyed history read defaults to `1Day`; a keyed read preserves its
recorded interval. Legacy intervals require the retained artifact's recorded field,
not a guess from date-shaped values.

Intraday request dates span New York calendar days, with UTC-second bar identities;
daily requests preserve the existing UTC boundaries and provider business dates.
The chart's intraday axis is UTC; the selector and crosshair show New York time.
Raw provider OHLCV text and original timestamps are retained with interval, feed,
adjustment, capture time, pagination and source hashes. USD is the recorded
US-stock API default; aggregation is provider-defined. Neither timestamps nor
completed pagination prove exchange-calendar completeness, bar finality or trading
eligibility. Missing, partial, unsupported and provider/entitlement failures remain
visible; there is no synthetic fill or alternate-feed fallback.

**Compare retained cache** reads another symbol's saved current-market cache.
Matching context, provider, interval, feed, adjustment, aggregation and currency are
required. Only actual common timestamps are plotted. The close-price index uses
100 at the displayed common positive-close anchor; choose another common anchor
explicitly. Pan and zoom do not change it. Exact source closes, anchor closes,
capture/source identities and unmatched-bar counts remain available as text.
This is not a portfolio or dividend-reinvestment return calculation. Chart context,
cache identities, comparison, anchor, exact selected bar, display range and viewport
use the existing revisioned workspace preferences. Restoring a selection reads
retained evidence and does not collect new bars.

These interval/comparison source changes have not been exercised through new data
collection or browser UAT. Advanced drawings, Level 2 and time-and-sales remain open.

Open **Discover US equities · Yahoo screen** to prepare optional price,
market-cap, average-volume and sector criteria. The installed yfinance 1.7.0
`EquityQuery` and `screen` APIs perform the screen. **Run current screen** requests
one dated page of 25 provider matches. Next/Previous retain the criteria used by
that result; editing the draft does not silently change a displayed result.
Provider errors are distinct from successful empty pages. Missing numeric fields
remain unavailable, and Yahoo observations do not establish Alpaca tradability,
current IEX prices or complete market coverage.

Save named criteria through the app workspace's existing revision handling.
Saving a name again updates that named screen; loading explicitly replaces the
current draft. Dated screen responses are retained in the app's separate
discovery record, with observation IDs and content hashes. The selected page and
symbol restore from workspace preferences; reading them does not refresh Yahoo.
These observations are not saved agent research.

Select a result symbol to inspect its retained fields, market/capture timestamps,
criteria, query and pagination provenance without adding it to the universe.
Watchlist stocks outside the configured universe have their own inspect buttons;
when no retained observation exists, the app states that the evidence is missing.
The main stock grid still represents configured symbols only.

Adding matches to a watchlist does not change the universe. A supported-format
symbol's detail offers **Add this symbol to configured universe** as an explicit
separate action. It appends that one symbol through existing configuration
validation, the 1,000-symbol limit, current revision and research-running checks.
It does not establish Alpaca tradability, launch research or authorize orders.
Unsupported provider symbol formats are not silently converted.

The unmodified chart bundle, Apache 2.0 `LICENSE`, `NOTICE` and source/hash index
are under `tradingagents/web/static/vendor/lightweight-charts/5.2.1/`.
`SOURCE.txt` records exact upstream URLs and SHA-256 hashes; updates must keep the
version, distribution, notice, license and hashes together. The page retains
TradingView attribution and a link. No browser CDN request or package installation
is needed. Sources: [Lightweight Charts documentation](https://tradingview.github.io/lightweight-charts/docs),
[pinned upstream notice](https://github.com/tradingview/lightweight-charts/blob/v5.2.1/NOTICE)
and [yfinance screen API](https://ranaroussi.github.io/yfinance/reference/api/yfinance.screen.html),
accessed 21 October 2026. A bounded browser observation loaded one live Yahoo
25-result page, saved/reloaded named criteria, inspected AA and explicitly added
it only to the isolated universe (503 to 504 symbols), and inspected a retained
AAPL chart. This does not establish other criteria/pages, fresh chart collection
or general provider availability. See the retained
[browser observation](../.local-workspace/evidence/g14-isolated-preview-20261022T013846Z-d9706311/g09-browser-observation.md).

## Update-stream and checkpoint recovery

Settings shows the latest broker trade-stream state separately from account/order
reconciliation. A listening socket can still have unresolved commands; their IDs,
reasons, pending checks and last attempt times remain visible. Those commands keep
their commitments and applicable order blocks. Use **Refresh account and order
status** for an explicit reconciliation attempt. A historical, disconnected or
unavailable worker snapshot does not establish current update coverage.

Application backup results and restore previews show checkpoint coverage by saved
run, symbol and thread: included, missing, incompatible, blocked or legacy. Included
means checkpoint bytes were retained, not that continuation is eligible. Current
compatibility is separate from immutable capture-time coverage; later source or
installed-version changes can make archived included checkpoints incompatible.
Snapshots are sequential consistent SQLite copies while application research/data writers
are quiescent; they are not one atomic transaction across all stores. Legacy archives
remain readable without claiming missing checkpoints. Restore never resumes agents;
open the saved run and review its original budget, expiry and eligibility first.
Checkpoint bytes and hashes alone do not prove continuity. An older or foreign
archive, a different generation, or missing/unreadable current state can hide later
external research effects, budget spending or cancellation; continuation remains
blocked until continuity is established. Retained checkpoints remain evidence.
The prior-state backup reference is retained when available. With a damaged or
unreadable store, the original damaged directory is retained; no unavailable prior
state archive or completed external-effect reconciliation is claimed.
These source changes have not been exercised through a new backup/restore or broker
reconnection in this batch.

## Continue interrupted research

Open the saved run in Agent research. The continuation panel shows eligibility,
the specific blocked reason, each symbol's remaining social posts and original
absolute expiry, and the parent-linked attempt history. Refresh continuation status
only reloads saved checkpoint eligibility; it does not start agents.

For an eligible interrupted run, click **Continue this saved run** explicitly.
The server rechecks the continuation revision and eligibility before queuing the
same run. Original analysis/account context, collected evidence and social budgets
are retained. Continuation does not refresh context, reset expiry or create a new
run. It is disabled in a review-only session.

Legacy, incompatible, cancelled, expired or exhausted checkpoints and uncertain
state-changing effects are blocked with their actual reason. A blocked continuation
is not silently retried as fresh research. These source controls have not been
accepted through an actual continued research run.

## Research agents and Maenifold

The market, news, and fundamentals analysts receive the eight commands in
`maenifold.memory`, the six commands in `maenifold.graph`, and
`maenifold.thinking.SequentialThinking` through the existing MCP Gateway.
This includes memory creation, editing, moving, and deletion, and graph
synchronization and repair. Command schemas retain confirmation, checksum,
and preview parameters. Tool guidance requires explicit user confirmation
before deletion and a preview before repairs.

Use `FindSimilarConcepts` to resolve names, `BuildContext` to explore related
knowledge, and `ReadMemory` to inspect sources. Research notes should cite
sources and dates. `SequentialThinking` records concise decisions, evidence,
and unresolved questions. Retrieved knowledge must be checked against the
analysis date; current graph contents are not a historical snapshot.

The desk selects only these three domains for analyst tools. Broker actions,
shell tools, configuration, and other thinking commands are not exposed.
The sentiment analyst retains its direct collection and Laya classification
flow. Gateway evidence records research calls; state-changing commands are
not automatically retried. These source changes take effect after the desk
reloads the updated code; an already running process is not updated in place.

Review on 21 October 2026 confirmed the 15-command allowlist, unchanged schema
binding, exclusion of all seven state-changing commands from transport retries,
and the absence of broker/shell/configuration tools in the desk analyst binding.
The delegated verification reported 42 passing focused cases and three analyst
fixture subtest failures; a broader fixture timed out on native refresh. These
are not a passing full-suite or live research result. No checks were rerun during
this source review, and no code correction was necessary. Activation requires a
later authorized desk restart; this review did not restart or launch research.

## Read-only smoke test

Open all five pages in the actual browser. Confirm connected Nautilus/account
status, price coverage for the saved universe, readable saved research, visible
order readiness, persisted settings and journal entries. Capture results and
errors. Do not approve, submit, cancel, replace, launch research or restore a
backup during this smoke test. Backup preview is different from applying restore.

The 20 October post-move browser check showed $100,000 cash/equity/buying power,
zero positions/open orders, 503 priced stocks and ten saved research runs. These
are dated observations, not constants the application should enforce.

## Regular and extended order sessions

New manual proposals default to **Regular session**. **Extended sessions** is one
explicit choice for simple quantity LIMIT orders: whole shares with DAY/GTC, or
eligible fractional shares with DAY. Market, stop, trailing, linked and notional
orders are unavailable for extended sessions. Unsupported combinations remain
visible and blocked; they are not converted into different order terms.

Extended includes pre-market, after-hours and potentially overnight according to
the broker, account and asset capabilities. It is not a permanent pre/post-only
instruction. The ticket shows dated account overnight configuration and asset
overnight/fractional eligibility. Unknown flags are distinct from observed
restrictions. Fractional extended orders require observed eligible asset support;
overnight flags do not create a blanket pre/post subscription gate for whole shares.

Price/feed evidence and configured freshness rules remain separate from session
eligibility. An exact limit is not a guaranteed fill; IEX observations do not prove
overnight quote coverage. A closed regular-session clock does not prove whether
extended trading is open. Current broker/account observations remain required.

Preview, approval and order history retain the reviewed session. Imported orders
show the broker's extended-hours flag, or Unknown if it was not supplied. Supported
replacements retain their predecessor session; changing it is unavailable. No order
is silently changed to regular. Approval and submission remain separate actions.

Sources: [Alpaca session scope](https://docs.alpaca.markets/us/docs/245-trading-for-trading-api),
[order contract](https://docs.alpaca.markets/us/docs/orders-at-alpaca),
[asset metadata](https://docs.alpaca.markets/us/reference/get-v2-assets-1) and
[asset attributes](https://docs.alpaca.markets/us/changelog/attributes-of-assets-api-endpoint),
accessed 21 October 2026. This source integration has not been accepted through a
new broker order or account/provider request in this batch.

## Broker-managed trailing protection

For an existing long holding, open its human proposal ticket and choose
**Prepare standalone trailing protection**, or select SELL and
TRAILING_STOP_MARKET in the manual ticket. Enter the whole-share quantity yourself,
choose DAY or GTC, and enter exactly one initial distance: USD with at most two
decimal places, or percentage with at most nine. Preview and save the exact terms,
then use the existing separate approval and submission actions.

Alpaca maintains the high-water mark and moving stop. The approved initial distance
is shown separately from the latest broker-reported watermark and current stop;
earlier watermark movements are not reconstructed. The stop triggers during
regular hours and becomes a market order, with no guaranteed execution price.
DAY expires at regular-session end; GTC is subject to broker expiry and
corporate-action rules.

BUY, fractional quantities, linked trailing exits, trailing stop-limit and trailing
offset amendments are unavailable. An imported working trailing order can use the
existing exact-order Cancel action when current identity checks permit it; Replace
is disabled and the original broker order remains working. This source integration
has not been accepted through a new broker order or browser exercise.

## Acceptance evidence

- [Corrected product roadmap](tradingagents-build-roadmap.md): requirement reference,
  subject to subsequent explicit user corrections and feature freeze.
- [19 October UAT index](uat/2026-10-19/README.md): committed plan, case ledger,
  report and independent review. Result: 41 pass, 2 partial, 6 not exercised.
- [20 October expanded report](../.local-workspace/evidence/expanded-uat-20261020/report.md),
  [69-case ledger](../.local-workspace/evidence/expanded-uat-20261020/final-ledger.md),
  [independent sign-off](../.local-workspace/evidence/expanded-uat-20261020/independent-signoff.md).
  These links resolve in this local checkout; the evidence is not committed.
- [Relocation report](../.local-workspace/evidence/migration-20261020/report.md)
  and [post-move browser capture](../.local-workspace/evidence/migration-20261020/smoke-overview.png).

Expanded UAT passed 58 permitted cases: account/universe views, watchlists,
sorting/filtering, charts and cached evidence, saved research, local proposals
and baskets, validation, review choices, alerts, journal/export, settings/import
drafts, backup preview, and engine stop/start. Five cases lacked data and six
were reserved. Actual approval/submission, broker cancel/replace, fills and
populated-account behavior are not certified. Neither are new research,
destructive restore or the unavailable supplementary datasets. Do not describe
this as completed trading-execution UAT.

## If startup or data looks wrong

- Check `tradingdesk.launch.json` and that its four paths exist. Preserve the
  configured application/history pair; do not point at a convenient empty folder.
- Read `.runtime-stage\launcher.err.log` for launcher startup failures. The
  migration-started instance used `migration.err.log` in the same directory.
- If the port belongs to another instance, inspect its identity before changing
  or stopping anything. The launcher deliberately does not take it over.
- If the app opens but balances are unavailable, inspect Nautilus connection
  status and start the engine if stopped. Read the reported error if connection
  fails; do not invent balances or weaken order approval.
- Treat dated prices, missing data and unavailable fees according to their UI
  labels. Use saved evidence for existing research; do not silently start a run.
