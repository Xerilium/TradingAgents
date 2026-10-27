# Local TradingAgents desk: launch, use and handoff

The [product README](../README.md) is the current component map and complete
operating guide. This document retains detailed implementation contracts and
dated observations; older installation examples are not current account state
or blanket feature acceptance.

The Windows desktop installation and development paths below were updated on
26 October 2026. Dated observations elsewhere in this guide remain historical.
Start from the [README](../README.md); agents must also read [AGENTS.md](../AGENTS.md).

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

1. Open the TradingAgents desktop or Start menu shortcut. Both target
   `%LOCALAPPDATA%\Programs\TradingAgents\tradingagents-desktop.exe`.
2. Open <http://127.0.0.1:8098> if the browser did not open automatically.
   The installed app uses port **8098** and the production profile under
   `%LOCALAPPDATA%\com.tradingagents.desktop\production`.
3. Expand **Nautilus connection**. If stopped, choose **Start Nautilus**. Wait for
   connected account status and prices before relying on current observations.
4. Confirm the account is paper, check cash/equity/buying power, and inspect
   missing prices and timestamps. A refreshed account does not mean a new market
   price event, particularly while the market is closed.

The tray offers **Open**, **Restart**, **Check for updates**, **Open logs** and
**Quit**. Closing the browser leaves the tray app running. Normal tray Quit has
not yet been observed. A Git clone alone lacks the installed app, local data
and private credentials. Do not run `python -m tradingagents.web.server`
without explicit configuration: its defaults differ from this installation.

**Stop Nautilus** disconnects the engine; the web app and saved research remain
available. Use the tray controls for the installed app when maintenance
requires taking it offline.

For isolated source development, run `rtk proxy .\Start-TradingDesk-Dev.cmd`
from `C:\src\TradingAgents` and open <http://127.0.0.1:8099/>. It uses the
checkout's `.venv` and `.venv-nautilus-v1` and
`.local-workspace\development`. It does not copy production credentials or
share production settings or data. `Start-TradingDesk.cmd` opens the installed
production app. The old `tradingdesk.launch.json` is not its launch configuration.

Manage Alpaca credentials in **Settings → Account** and other API keys in
**Settings → Integrations**. The desktop app uses Windows Credential Manager
or macOS Keychain, with separate production and development entries. It does
not fall back to a plaintext file. Fields stay empty after saving; the page
shows only whether a value is saved. Blank fields keep existing values.
**Remove** deletes the selected credential after confirmation.

Saving credentials does not switch an active account. Stop Nautilus, then start
it to load the saved account and endpoint. Normal app startup also uses that
native store. Verify the observed paper/live account before preparing orders.

## Where things live

| Item | Current location / purpose |
| --- | --- |
| Installed app | `%LOCALAPPDATA%\Programs\TradingAgents\tradingagents-desktop.exe` |
| Production profile | `%LOCALAPPDATA%\com.tradingagents.desktop\production` |
| Application data and research | `application` and `research` within the production profile |
| API credentials | Native OS vault, under `TradingAgents.desktop.production.*` or `TradingAgents.desktop.development.*`; never publish values |
| Desk log | `logs\desk.log` within the production profile |
| Development checkout and data | `C:\src\TradingAgents` and its `.local-workspace\development` |
| Prior source-linked application and history | `.local-workspace\evidence\runtime-staging\20261017T024233Z-e3f9548d\application` and sibling `history` |
| Preserved local evidence and backups | `.local-workspace` and existing repository-local backup folders |

Old paths inside dated evidence remain provenance, not launch instructions.
The signed Windows 0.6.2 installer and its signature exist and the update is
installed locally. Windows Credential Manager storage and the paper-account
connection were verified in Settings on 27 October 2026. The update feed is
not published and an end-to-end update has not been proven. macOS dependency
locks target macOS 26 or later on Apple silicon; no macOS build has been made.
The installed desk still depends on a signed-in Codex installation and an
external Maenifold service for those integrations.

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

- Check the installed production profile and read its `logs\desk.log`. Preserve
  the application and research data; do not substitute an empty folder.
- For source development, inspect `.local-workspace\development` and the
  development launcher. The old `.runtime-stage` logs are historical.
- If the port belongs to another instance, inspect its identity before changing
  or stopping anything. The launcher deliberately does not take it over.
- If the app opens but balances are unavailable, inspect Nautilus connection
  status and start the engine if stopped. Read the reported error if connection
  fails; do not invent balances or weaken order approval.
- Treat dated prices, missing data and unavailable fees according to their UI
  labels. Use saved evidence for existing research; do not silently start a run.

### Selected US options and manual premium proposals

The Universe discovery section includes an Alpaca contract query and exact OCC inspection. Each explicit request retains the complete returned page, source URL, timestamps, contract hashes and raw-response artifact. Request subsequent pages explicitly with the returned cursor. Contract status, tradability and supported mapping are separate observations; unsupported deliverables remain inspectable but cannot be selected for this supported preparation profile.

Select a retained contract with an explicit OPRA or indicative feed. Entitlement is not assumed. Selected envelopes and their feed are validated in the existing discovery record and restored into native desired symbols after restart; they are not added to the stock research universe. The native subscription uses one option feed. The separate Apply chosen feed action explicitly changes all retained selected subscriptions and persists the new feed; choosing a contract cannot silently switch other subscriptions. A subscription failure remains visible as unavailable native evidence; saved selection is not proof of a working quote.

Open its manual premium ticket and choose buy to open or sell to close, whole contracts and an instrument-supported order type and duration. The documented long single-leg profile supports MARKET, LIMIT, STOP and STOP_LIMIT, each with DAY or GTC, regular session only. Enter the exact USD premium limit for LIMIT/STOP_LIMIT and trigger for STOP/STOP_LIMIT; MARKET has no fixed broker premium limit. Premium times the observed contract deliverable size times quantity is distinct from an underlying share price. Preview binds current server-observed metadata and feed; saving grants no approval or submission authority. Any linked research is an explicitly selected exact underlying report, labeled underlying analysis only, not an option recommendation.

Option BUY stops retain the actual stop type; the equity BUY stop-to-stop-limit rule is not applied. A stop-market can fill beyond its trigger, and a stop-limit may not fill. Dated side-specific option premium evidence supports estimates. A reviewed maximum execution price bounds local review/reservation only; it is not a broker market/stop-market execution guarantee. GTC remains subject to contract expiration and broker rules.

For an eligible broker order in new, partially_filled or done_for_day state, select its exact predecessor in the manual ticket. Amendment keeps the contract, intent and order type, and permits total quantity, applicable prices and DAY/GTC changes. Total quantity includes actual prior fills. Preview and obtain renewed exact approval, then use the separate Replace control. The native successor is the actual broker successor with its own identity and duration; ancestor fill offsets require retained execution proof rather than a fabricated duration update. Pending or otherwise nonreplaceable broker states remain blocked.

Options buying power is displayed separately from cash, with account observation time and the exact local-unsubmitted commitment / replacement basis in preview. Missing or stale observations remain unavailable; equity cash is not an options-buying-power substitute. Exercise readiness compares dated funding or deliverable shares after the applicable local commitments; it is not a permanent reserve, future funding guarantee or exercise instruction.

This is source implementation, not executed broker/native acceptance. Short opening, short-containing packages, full expiry/share/cash settlement acceptance and complete native lifecycle acceptance remain open. Exercise and DNE use the separate explicit instruction workflow below. Raw broker non-trade activities and dated current account facts alone do not establish full lifecycle acceptance.

Broker capability and app implementation are separate. The [Alpaca options guide](https://docs.alpaca.markets/docs/options-trading) documents broker capabilities; this table does not promise every combination.

| Profile | Current boundary |
| --- | --- |
| Whole-contract long single-leg BTO/STC, MARKET/LIMIT/STOP/STOP_LIMIT, each DAY/GTC, regular | Current source workflow; broker/native execution unexercised |
| Fractional, notional, extended-hours options | Broker unsupported |
| Naked/unbounded or otherwise unsupported short-containing packages | Outside supported profiles |
| Selected bounded-risk same-expiry option spreads | Separate source profile below; current eligibility/balance mapping must be proven, runtime unexercised |
| Long-only atomic combinations, 2–4 BTO/STC legs, MARKET/LIMIT DAY/GTC regular | Current source workflow below; runtime acceptance unexercised |
| Exercise and DNE | Separate preview/review/approval/submission source workflow; broker acceptance unexercised |
| Full settlement/native reconstruction acceptance | Open; no lifecycle acceptance claim |

### Atomic long-only option packages

Select exact retained option contracts in discovery, then choose **Prepare atomic long-only package**. The manual ticket accepts 2–4 distinct BTO/STC legs with one underlying, compatible observed deliverables/multiplier, positive whole ratios with greatest common divisor 1, and positive whole strategy units. Each leg quantity is strategy units × ratio. Opening, closing and long-only rolls use this same explicit package path; no independent leg submissions are synthesized. Server-observed contracts and public native spread identity bind the complete revision.

Choose MARKET or LIMIT, DAY or GTC, regular session only. LIMIT requires a nonzero signed net price: positive debit or negative credit. Zero/even price remains unsupported and is never changed into MARKET. For MARKET, select expected debit/credit intent explicitly; estimates cannot guarantee price or actual debit/credit direction. An explicit local net debit review bound covers possible worsening/sign change; it is not a broker limit. Review exact leg quantities, current holdings/STC availability, premiums, fees, one package net debit obligation and configured portfolio/leg checks. BTO leg premium is not reserved again, STC claims are counted once, and expected credit is not spendable. Missing required calculations cannot pass.

Preview, save, check and approve the exact complete package revision. Submit remains a separate action sending one atomic MLeg request. Prepared proposals and approval alone reserve nothing. The separate D55 exercise/DNE interlock does not grant or block ordinary package authority. For an eligible observed parent, amendments preserve contracts, legs, ratios, intents and order type; only total strategy quantity, applicable signed limit and supported duration change under fresh complete-package approval and the separate Replace action. Cancel remains explicit; acknowledgement is not final cancellation.

Monitoring retains actual parent versus leg broker IDs, internal native IDs, predecessor/successor identity and raw source evidence. Actual leg executions supply prices, quantities, fees and cash flows. Parent net average or status never substitutes for missing leg economics. Pending, partial, corrected and unknown outcomes retain obligations and recovery restrictions without automatic resubmission. This is source implementation only: package execution, amendments, cancel/fill/recovery and broader P01 acceptance have not been exercised. Other short-containing profiles remain open; the separate bounded-risk source profile below has its own requirements.

The public native spread-quote aggregator source path uses actual leg quotes with vega disabled and quote-driven updates. It retains exact contracts, ratios, observed multiplier/feed, real bid/ask prices and sizes, timestamps, receipt IDs/hashes, source generation, calculation settings and derived output hash. Missing or materially changed required inputs invalidate the valuation under the existing configured freshness/material-change rules; unrelated stale ticks or a trade fallback cannot substitute. This derived valuation is not a broker spread quote, fill, fee or atomic-liquidity guarantee.

Native signed-price risk checks and original configured instrument caps remain intact. A configured cap can additionally produce a supplemental application ABS premium check with the original cap/provenance retained; absent caps remain absent. This does not claim that the native margin balance branch, which can return early, validates all collateral/price-dependent risk. Source/static implementation and runtime acceptance remain separate.

### Selectable bounded-risk spread profile

The package ticket has a separate **bounded-risk spread** execution profile; the existing long-only profile remains the default and historical records keep their original profile. This selected source capability accepts 2–4 compatible option legs on one underlying and expiration, positive whole normalized ratios, whole strategy units and explicit signed nonzero net LIMIT, DAY/GTC regular only. Four intents are explicit: BTO, STO, BTC and STC. A new STO requires protection from BTO within that complete package; retained long positions alone do not establish the opening profile. This does not establish naked, unbounded, equity-leg, calendar or unsupported roll support.

Use the existing native controls to stop the session, select its execution profile, then explicitly Start to revalidate actual account identity, endpoint, current permissions, balances, margins, options buying power and native balance-mapping basis. An active session cannot change profile. Source selection does not enable the account or permissions and does not mutate its legal type. [Alpaca paper trading](https://docs.alpaca.markets/us/docs/paper-trading) documents margin simulation; the PAPER profile is explicitly that simulation, not a legal classification. The [account-plans statement](https://docs.alpaca.markets/us/docs/account-plans) about brokerage margin accounts is scoped to LIVE and cannot prove PAPER legal type or LIVE eligibility for this application. LIVE requires its own verified current broker contract/account evidence. Native Portfolio.equity can add unrealized P/L to the projected equity balance and is therefore not broker actual equity; application performance/equity curves and configured rules continue to use actual broker fields. Captured native report/download labels retain their own profile and basis, never the latest session as a substitute. The versioned alpaca-paper-equity-initial-v1 projection uses actual broker equity as native total, actual initial_margin as locked, and equity minus initial_margin as free, with calculate_account_state=false. Signed negative excess is preserved. Maintenance margin and local commitments are not deducted again. This is a derived diagnostic projection, not spendable cash, unrestricted funds, a pending reservation or broker legal classification. Actual broker cash, equity, margins, options buying power and restrictions retain authority; missing inputs are never zero or substituted by buying power. Historical long-only records retain their cash basis.

Preview exposes modeled intrinsic collateral and expiry maximum loss separately from actual broker margins, available options buying power, fees and per-leg signed holdings/close claims. The modeled package obligation before costs is the nonnegative result of intrinsic collateral increase plus signed package LIMIT premium, with declared costs counted once. Same-package credit may offset that obligation; no expected credit funds unrelated commitments, and no duplicate leg premium or full-delivery reserve is added. A modeled finite expiry loss is not a broker margin figure or an assignment/exercise guarantee. Early assignment can break protection; closing/removing protective legs re-reviews resulting retained exposure, commitments and current evidence. Required unsupported/missing calculations remain unverified and block their applicable checks.

Opening, closing, amendment and cancel use the existing exact complete-package revision review, approval and separate send actions. Amendments preserve profile, contracts, intents, ratios and order type. Actual signed legs, parent/control identities, partial/unknown outcomes, corrections and recovery history remain distinct from modeled maximum loss. This is unexercised source capability, not broker acceptance or activated account support. D58 MARKET runtime acceptance remains open. The derived-valuation source path below requires complete actual leg inputs; it does not establish an executed native risk pass or broker acceptance.

### Bounded package replacement reservation review

A newly saved/revised supported bounded MLeg replacement can record the explicit routing version alpaca-bounded-incremental-v1. Historical proposals/approvals do not acquire it automatically. It applies only to the exact bound account, predecessor/client/version and immutable bounded option package replacement; ordinary new orders and configured hard limits retain their existing rules.

Review exact old/current predecessor evidence, proposed full terms, actual account options buying power/margins and known fee assumptions. Required local facts, commitments, collateral and policy checks still must pass. Only the broker's incremental reservation validation is broker-owned and **not observed at approval**, with reservation credit null/unknown. The neutral check has passed=null and required=false; this is not a generic funding pass or permission to skip another missing required input. Local routing eligibility is shown separately. No old-order credit or released funds are invented, and preserved pending/cash commitments are not removed.

Fresh exact approval precedes the existing separate Replace action and one native PATCH path. The broker can reject after its own buying-power/margin validation. Approval-time not_observed is immutable review evidence; actual submitted/rejected/unknown/pending outcomes are separately retained in the command/order lifecycle. An acknowledgement or pending replacement is not final completion or permission to release obligations, retry or resubmit. This source workflow and broker behavior remain unexercised.

### Native position reconstruction and global recovery

Current broker cash, positions, cost basis and activity receipts remain source facts. Native position reconstruction represents quantities through official native objects, with immutable receipt pointers, source hashes, account, instrument and worker epoch. Its reduction P&L, zero model commissions and processing chronology are modeled; they do not establish actual historical broker economics. Captured native tables/JSON preserve that qualification, and affected position outcomes do not claim actual net. Broker CSV values remain broker-reported.

Prepared, ambiguous or causally unproven reconstruction keeps the existing global reconciliation restriction. There is no per-instrument bypass. A new local command can carry an exact confirmed current-epoch baseline receipt; historical receipt membership or timestamps alone cannot prove a later actual fill belongs outside that baseline. Unknown/open/external executions require reconstruction rather than a blind native increment.

Use the existing explicit Stop Nautilus, then Start Nautilus controls when reconstruction is required. Rebuild uses current broker facts and retained causal receipts; reconnect does not replay commands or grant approval. Successful reconciliation returns to the normal existing admission checks. Missing metadata, basis or source evidence can leave the global restriction unresolved. Old epochs are historical evidence, not current native proof.

This source work has not exercised native reconstruction, broker expiry settlement or reconnect acceptance. Full lifecycle acceptance remains open.

### Saved price annotations

Retained OHLC charts support horizontal lines, two-anchor trend lines and text. Choose a tool and place its anchor(s) with the pointer, or Create numeric draft and enter exact prices/times. Select a drawing to drag its handles or edit numeric fields; keyboard users can tab through the same controls. Ctrl/Cmd+S saves the selected annotation; Delete on a selected chart drawing stages removal, and Escape ends placement. Save and Remove use the existing workspace revision flow. Reopen saved annotations from the list; unsaved drafts survive ordinary polling and source refresh, and remain separate from saved immutable revisions.

Pointer coordinates are manual approximations. Use selected retained OHLC explicitly for an observed anchor: the exact artifact/hash, bar time, OHLC field and raw decimal are validated on save. Editing that anchor price/time converts it to manual provenance. Manual times between retained bars are annotation coordinates; unavailable/out-of-range coordinates are disclosed. Projected bar offsets retain an actual origin plus an explicit logical offset, without inventing future market bars or timestamps. Drawings use exact instrument/currency/feed/adjustment/session/interval context; incompatible or indexed-comparison panes do not convert percentage coordinates into prices. Replay cannot reveal future observed anchors.

Saving an annotation alone does not create an alert. Numeric lines can be explicitly linked to the separate crossing-rule flow below; text remains nonnumeric. This is source implementation; pointer/browser execution and save/reopen acceptance have not been exercised.

External broker equity SHORT positions and negative cash are represented as signed source facts. Short options remain outside the supported native representation, and new short or margin-opening authority is not granted. The existing negative-holdings policy can still block cover proposals; that is a separate admission limitation, not an unknown actual holding.

### Saved drawing crossing alerts

Save a horizontal level or trendline, then choose **Create alert from this saved geometry**. The draft is inactive: select the retained OHLC field, cross-above/cross-below comparison, positive maximum source age and retained input context, then explicitly Save the rule and its evaluation choice. The rule binds the server-provided drawing UUID, revision, geometry hash, full typed anchors and exact instrument/currency/provider/feed/session/adjustment/interval scope. Text annotations are not numeric predicates. Drawing rules use a fixed symbol; they can join existing flat ALL/ANY conditions without changing that symbol identity.

Horizontal levels remain constant across the actual retained logical-bar axis. Trendlines require defined nonvertical geometry and an explicit segment or extrapolation policy. Manual times can locate an actual retained timestamp or interpolate between adjacent actual bar times; projected anchors retain an actual origin plus explicit logical offset. No synthetic future bars/calendar are invented. Observed anchors retain their exact OHLC artifact/hash/value provenance. Saved research is static evidence/baseline and cannot advance to future bars; current-history rules can observe compatible eligible retained appends without collecting provider data themselves.

Cross-above requires previous residual ≤0 and current residual >0; cross-below uses the inverse. Both observations must be eligible/comparable and advance time. Repeated/older bars and corrected history prefixes/source basis reset continuity without retroactive crossings or rearming. Unavailable inputs, acknowledgment and pause do not rearm; only an eligible opposite-side clear does. Drawing edit/delete leaves an existing pinned rule unavailable. Edit the rule, choose a saved current revision, explicitly Bind it and Save a new rule revision to establish a fresh baseline; old occurrences retain their old geometry and latch history.

Older drawings with missing or changed scope stay inspectable. **Stage explicit rebind to this retained source scope** copies only actual retained scope evidence (including the provider asset ID), keeps anchors/original observed pins, and requires Save of a new drawing revision. It never silently upgrades history. Then explicitly bind the desired rule revision. Missing current scope/provenance stays unavailable.

**Open exact alert evidence** opens the captured occurrence with immutable geometry/algorithm, typed anchors, both observations/residuals and separately hash-verified previous/current source artifacts and observed-anchor pins. Missing historical evidence is disclosed; current geometry or latest history is never substituted. This is source implementation only; chart-to-alert, monitoring/corrections, save/rebind/reopen and external delivery acceptance have not been exercised in this batch.

### Explicit option exercise and DNE

Use the option contract view or Orders to choose Exercise all available or Request DNE. Enter explicit positive account-observation age and approval-lifetime bounds, preview current facts, prepare a saved intent, review its exact current evidence/history, approve that review, then separately Submit. Prepared and approved intents hold no resources. There is no partial-quantity field: exercise targets all contracts available when processed. The observed count/time, exact contract/deliverable, account/mode/session/epoch, commitments, configured policy applicability and prior requests remain visible. Material evidence changes require renewed review/approval. Research tools receive no instruction authority.

Exercise readiness is a dated funding/delivery comparison, not a new permanent reserve. Existing evidenced hard restrictions remain blocking; unsupported models do not claim a passing check. DNE does not inherit exercise funding requirements. Ordinary BTO/STC/orders retain their existing controls and are not blocked by another contract instruction. Only an in-flight or transport-unknown instruction interlocks the same account/contract.

Pause blocks exercise admission and the final pre-HTTP boundary. Separately approved DNE and ordinary authorized cancellation remain available; review/approval are separate. Pause cannot recall an already-started request or working broker order. A 200 submission is a known request result, not settlement. DNE is not guaranteed to undo prior exercise or govern later acquisitions; published timing guidance does not establish a universal cutoff. Broker changes can race the final preflight because no fixed-quantity or idempotency contract is available.

Unknown outcomes have no blind-retry control. Actual attributable evidence or a separate reasoned human release can resolve the local interlock. Release preserves the original unknown outcome and grants no retry authority. A later request needs fresh authority and explicit review of the unresolved prior request; known submitted requests also remain in history and are not atomic reversals.

### Reusable strategy experiments (D61 source integration)

In **Decision journal → Reusable strategy experiments**, load the saved definitions and retained daily data. Use the guided entry/exit condition editor, matching operand units and finite integer/decimal parameter domains; save an immutable strategy revision before preview. The supported account scope is one USD equity, whole shares and empty starting holdings. Choose MARKET, LIMIT or STOP_LIMIT and DAY/GTC, with optional linked take-profit and stop/stop-limit protection. Applicable price operands freeze at the completed decision bar as exact positive USD cents, without rounding. Native FULL-entry protection may leave partial entry exposure unprotected; rule exit cancels the working entry and its live protection, waits for actual native terminal events/late fills, then exits actual residual holdings. No pyramiding or duplicate exits. Wider assets remain open.

Selected timing is native OHLC-path next modeled open: public TradeTickDataWrangler, fixed 100 ms compressed OHLC offsets and seed None, with trade execution enabled and bar execution disabled. A close tick precedes the completed decision bar; the next generated open tick updates the native book before a queued intent. This is not an actual session open, tick/BBO or liquidity reconstruction. DAY uses the declared session boundary. Converter/path, source identity, volume allocation/floor, precision and model flags remain bound in the immutable preview.

Configure rolling/expanding windows, sourced-calendar session counts, expected-calendar-session gaps at both train→validation and validation→OOS boundaries, and untouched OOS periods. Clock-duration embargo is unavailable; later-captured history/benchmark requires the explicit hindsight basis. The visible starting preset is 126/21/1/21 sessions with a 21-session step. Dynamic warmup is separate from trading; each fold resets. Boundary orders cancel and retained positions are marked without fabricated closing fills. Choose objective/direction, secondary metric/direction, positive minimum closed trades in both training and validation, scenario cash, explicit fees/fill/slippage assumptions and native-run budgets. Each experiment/trial deadline needs a positive value or its explicit no-time-cap checkbox. Actual fees remain unknown.

**Save immutable experiment preview** records the exact strategy, data artifacts, full grid manifest or adaptive configuration, folds, scenarios, costs and search identity. Grid is complete or rejected for insufficient budget. Adaptive binds TPESampler, NopPruner, seed 0 and a visible editable 64-ask preset per outer fold, including failures/repeats. No qualifying candidate means no winner. **Run this exact experiment** is separate. Optional service-only Optuna 5.0.0 must be available; an absent/different version disables Run without a fallback optimizer or installation. The optional dependency declaration does not establish installation.

Inspect execution status separately from analytical outcome: finished with no eligible strategy or selection gaps is explicit, and an unselected fold has no performed OOS. Required selected-stage failure/missing evidence prevents an unqualified completion; a valid negative OOS result is not failure or a reason to reselect. Inspect fold/trial comparison tables, coverage, exact native events/reports, source fingerprints and any reused source-trial identity. OOS equity/benchmark paths use retained actual timestamps and remain separate by fold/scenario; they are not compounded, rebased to conceal differences or presented as actual account performance. Missing curves or benchmarks remain unavailable. **Request cancellation** preserves completed evidence; interruption does not resume. A repeat/branch receives a new preview ID and still requires Run. Exact resume, pruning, carry, overlapping OOS and wider profiles remain open. Source integration has not been exercised here; no experiment, provider request, native session or broker action was run.


### Retained chart analysis (D63 source integration)

Chart jobs use a separate single-worker queue from simulation and optimization.
At most one chart runs and one waits; another request receives a busy response
without displacing existing work. The visible total budget defaults to 60 seconds,
editable in whole seconds from 1 through 600. It starts at accepted admission,
includes the chart queue wait and uses a live monotonic deadline. Expired or
canceled queued work is not dispatched. The panel shows queued/running/terminal
state and supports cancellation and reopening the exact retained record.

Admission saves the actual timestamps, immutable inputs and budget before dispatch.
Cancellation, timeout and shutdown interrupt owned chart work; restart
marks unfinished jobs interrupted without replay. Stop evidence is saved before
session invalidation, and late results cannot replace an interrupted record.
Failed/interrupted jobs have no invented numerical result artifact. Historical
valid calculations and their actual result artifacts remain readable.

Stopping uses exact owned process handles: terminate and wait up to one second,
then kill and wait up to one second. Worker pipe draining is separately bounded
to one second. These are containment limits, not a promise of graceful native
cleanup or descendant termination. Unconfirmed exit/cleanup remains explicit;
temporary files can remain after a failed cleanup. No TradingNode, BacktestEngine,
broker session or Optuna is started by a chart job. This lifecycle implementation
has source/static evidence only until separately authorized runtime observation.

#### Acceptance debt

| Ready source slice | Exact frozen version | Still unobserved | Smallest real observation |
| --- | --- | --- | --- |
| D63 chart analysis | `1212fab985c19a257350aca01c295da4edbad54a` includes D63 | Numerical output, rendering, saved reopening and positive seasonality | One isolated visible-browser batch using real Intel daily history with production-ingested calendar provenance |
| D66 multi-timeframe program | `1212fab985c19a257350aca01c295da4edbad54a` | Actual minute aggregation, original-axis formulas and alignment evidence | One bounded real minute collection and one retained program observation; unknown coverage stays unavailable |
| D69 chart lifecycle | Not checkpointed; working delta over `1212fab985c19a257350aca01c295da4edbad54a` | Independent queue, capacity, deadline, cancel, shutdown and restart behavior | Bind its accepted checkpoint, then observe real chart jobs and honest interrupted outcomes in an isolated copy |

Static checks do not close these rows. D67 staging must bind the subsequently
accepted D69 checkpoint. Provider/calculation activation and trading-lifecycle
observations require their separate explicit assignments; neither has run here.

Open **Chart analysis** below an existing raw OHLC chart. Load saved definitions, choose transform/study/seasonality/formula, edit its applicable parameters and Save an immutable revision. **Calculate exact saved revision** is a separate explicit action against the pinned retained source. It uses the isolated pure calculation worker; no Optuna, trading session, BacktestEngine, provider collection or broker action is required. Load a prior calculation by its immutable ID/hash; chart preferences retain that exact reference. Import/export uses validated versioned definition bundles and pinned transitive dependency revisions, without overwriting collisions or executing scripts.

All five transformed families are separate derived displays: seeded recursive Heikin Ashi; configurable traditional fixed-size Renko; fixed/percentage Kagi with shoulder/waist thickness changes; N-Line Break; and fixed-grid Point & Figure. The calculation retains seeds, equality/reversal/rounding rules, segment initialization prefixes and exact rational coordinates. Kagi renders stepped thick/thin geometry and P&F renders X/O columns with configured-box glyph height centered on the exact box level; that height is derived display geometry, not observed OHLC. Logical event/column positions are not fabricated market dates; several outputs may share one actual source timestamp. Gaps break continuity, incomplete outputs remain provisional, and generated event volume is not observed volume to sum. The installed native one-brick Renko is not substituted for the selected traditional/configurable reversal contract. ATR/log/high-low variants remain explicitly outside this selected construction contract.

KAMA uses N actual changes and squared smoothing, first-source-close seed held unchanged until N+1 closes, and ER=0 for a flat window. This is an explicit app convention, without an identical-TradingView-output claim. The official [KAMA calculation](https://www.tradingview.com/support/solutions/43000773012-kaufman-s-adaptive-moving-average-kama/) specifies full-window ER and squared smoothing but does not settle this seed/zero/readiness convention. Installed native source anchors are .venv-nautilus-v1/Lib/site-packages/nautilus_trader/indicators/averages.pyx:627,692 and momentum.pyx:675–676,717–718; the rolling N-input/N-change mismatch prevents simply relabeling native AMA. Native CCI, Donchian and qualified public Ichimoku composition retain implementation/source/binary hashes. Initialization is not convergence proof; native binary64 and exact rational outputs retain their distinct precision basis.

Full Ichimoku displays current conversion/base lines, forward leading cloud and backward actual-close Chikou with separate origin, closure evidence, source availability, calculation time and display offset. Zero displacement does not use an invalid zero-offset native constructor. Public current Tenkan/Kijun and parallel Donchian midpoint supply leading components; no private queues or fake future bars are used. Numerical seed/warmup values remain inspectable but are omitted from ready plots. Raw price overlays use only the calculation's actual retained source rows.

Seasonality requires complete expected calendar/session coverage and each prior-year December anchor. Completed month returns are prior-month-end → month-end; all eligible complete years share the frequency denominator, including flats. Whole-sample means and conditional gain/loss means retain separate counts; empty samples stay unavailable. Yearly comparisons offer calendar/session alignment and raw/normalized values, with selectable common or separately labeled per-year value scales on the same aligned x domain. MTD/YTD remain separate and excluded. A proven complete current-year prefix may appear as a dashed partial comparison, explicitly excluded from monthly samples; it never changes the completed-year denominator. Exact adjustment/dividend basis is disclosed; price returns do not imply reinvested-dividend total return, and missing sessions are never invented zeros.

Formulas use the allowlisted parsed AST and typed causal series operations, not eval, imports, arbitrary Python/JavaScript or application actions. Choose line, histogram or price overlay; add exact typed scalar parameters and pin reusable formula/study revisions. Formula-call arguments follow alphabetical parameter-name order; study references use DefinitionName__component. Units, lookback, initialization, gaps, cycles and availability are validated. Display displacement never creates earlier availability. For example sma(close,20) is a causal price series; its rendering choice is separate from its calculation. External scripts and transform-event-to-raw-axis coercion are unavailable.

Selecting derived geometry cannot copy its price into a ticket. Choose a real contributing source row, **Open this actual bar in the raw chart**, then explicitly review the original raw O/H/L/C and existing normalization. The reference binds calculation/result hash, event/source ordinal and raw source identity where applicable. No quantity, account, session, order approval or submission changes. The selected actual bar opens in the normal full-history chart; range selection, comparisons and source inspection remain available.

Peer-reference catalog: [Heikin Ashi](https://www.tradingview.com/support/solutions/43000619436-understanding-heikin-ashi-charts/), [Renko/Kagi/Line Break/P&F](https://www.tradingview.com/support/solutions/43000758617-advanced-intraday-chart-types/), [CCI](https://www.tradingview.com/support/solutions/43000502001-commodity-channel-index-cci/), [Donchian](https://www.tradingview.com/support/solutions/43000502253-donchian-channels-dc/), [Ichimoku](https://www.tradingview.com/support/solutions/43000589152-ichimoku-cloud/). These identify capabilities, not numerical parity or acceptance. This source integration has not been visually or numerically exercised here; no chart calculation or runtime activation was performed.


## Compound and watchlist attention rules

The existing alert editor accepts one condition or a flat group of 1–16 existing
conditions. Use **Keep condition in group** to add another condition and choose
**ALL** or **ANY**. ALL clears when any condition clears, triggers when every
condition triggers, and otherwise remains unavailable. ANY triggers when any
condition triggers, clears only when every condition clears, and otherwise remains
unavailable. Every condition's evaluated facts and exact captured source bindings
remain in the occurrence evidence, including unavailable conditions.

Choose one stock, a watchlist **Snapshot**, or **Follow watchlist**. Snapshot keeps
the membership at rule save. Follow records membership transitions atomically
with workspace saves, including removal and re-addition between monitor passes.
Continuous members keep their own active latch; unrelated list edits do not
rearm them. Removal is **no longer monitored**, never a false clear; re-addition
creates a new membership identity. Each member has its own occurrences and latch.
Account conditions evaluate once globally. Fixed-policy conditions bind once to
one saved proposal and its symbol; incompatible account/stock/proposal/watchlist
mixtures are rejected.

The first eligible matching observation can trigger a new or revised rule/member.
These conditions are state comparisons, not a two-observation crossing detector.
Only a valid aggregate clear rearms an active latch; unavailable observations and
acknowledgment do not. Pause/resume preserves rule revision and active latches and
records the monitoring gap without backfill. Changing rule content creates a new
revision. The rule view shows membership histories, per-member results, condition
evidence and gaps. Existing single-condition rules remain readable and usable.

This source batch has static verification only; it has not been activated or
accepted through live monitoring, workspace edits, notifications or browser UAT.


## Chart inspection and exact historical price copying

Historical charts provide range selection, pan/zoom, a recorded-bar selector and
raw OHLCV inspection. Derived calculations can open an exact contributing raw bar
in the normal chart. Source identity is checked before that bar is selected.
Charts do not have playback controls or saved playback state.

For the selected actual bar, **Recorded value** defaults to Close; explicitly
choose Open, High or Low if wanted. This uses exact source numeric text, not chart
coordinates, comparison indexes or rounded display prices. Choose a compatible
existing manual ticket limit, stop trigger, stop limit or linked exit field.
**Review price normalization** validates the exact source, instrument, USD currency
and observed native price increment. Raw and normalized prices, increment,
rounding and the declared nearest-increment `ROUND_HALF_UP` preparation method are
shown before **Copy reviewed historical price into ticket** becomes available.
Unknown source currency, instrument mapping or increment leaves copying unavailable.

Copy changes only that price and its retained reference. It preserves quantity,
session, account and live quotes, and invalidates the ticket preview. Cursor
movement never updates a ticket automatically. Manual edits remove the
affected price receipt. An existing paired SELL target has two names for the same
price: order limit and linked target. Both are shown before copy and changed
together; editing either invalidates their shared receipt. Preview and save use the existing exact-revision flow and
revalidate the source/reference; approval and submission remain separate actions.
Price review works from Dashboard, Markets and Portfolio. Its response is accepted
only while the same page, chart source, selected bar and ticket terms remain current.
Broker approval and execution are outside this chart-copy operation.


## Indicator evidence and attention

Saved research full OHLCV frames and current-history collections use the installed
Stockstats calculation boundary for all 13 research indicators. Retained output
text without full inputs remains display evidence with initialization unverified.
The chart shows exact calculation values and units, definitions, library/source
hashes, history identity, excluded times and separate numerical, warmup,
interval-closed, source-fresh and calculation-failure states. RSI uses 0–100;
MFI uses 0–1. EWM `adjust=True` describes smoothing weights, not corporate-action
price adjustment. The latter remains an independently recorded source field.

**Prepare indicator alert** copies the chart's symbol and exact retained run or
current-history cache into the existing rule editor. Choose **indicator** scope,
an above/below threshold or cross-above/cross-below comparison, and an explicit
maximum source age. A blank current-history cache key follows the latest retained
cache for the chosen interval; selecting or monitoring it never queues collection.
Use the existing history request controls to collect fresh inputs explicitly.
These conditions also participate in ALL/ANY groups and Snapshot/Follow lists.
Fixed saved-run inputs retain their date and do not become fresh market inputs.

A threshold needs an eligible numerical, initialized, closed-as-of, fresh point.
A crossing additionally needs two eligible observations seen by the monitor at
increasing bar times, with matching calculation/source comparability and unchanged
exact history through the prior observation. Initial observation, formula/source
replacement or retained correction establishes a baseline without manufacturing a
crossing. Unavailable observations affect their own condition; they do not clear
an active aggregate latch. Occurrences retain the unrounded evaluated values,
prior crossing observation, definition and exact hashed input references. Opening
an occurrence resolves those retained inputs without substituting current data.

Alpaca daily aggregation uses New York midnight to the following midnight.
Closed-as-of requires capture after that bucket end; regular-session close alone
does not close the daily bucket. This is not immutable finality: later corrections
remain possible. Freshness, calendar/instrument coverage, pagination and sufficient
warmup remain separate checks. Intraday or legacy data without the needed closure
and coverage evidence remains visible and unavailable to indicator alerts.
Source: [Alpaca market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq#how-are-bars-aggregated),
accessed 21 October 2026. This batch has no live monitoring or browser acceptance.


## Saved declarative data scans

Open the existing Yahoo discovery section and **Saved declarative data scans**.
Use **Add programmable multi-timeframe conditions** to name inputs, select the
anchor input, add typed threshold parameters and build ALL/ANY comparisons with
the condition controls. Each input selects its own timeframe, session, exact
source profile, raw field or immutable chart formula/study revision and component,
and explicit allowed stale-bucket count. All six timeframes remain visible.
1Min/regular uses actual provider minute bars; 5Min, 15Min, 30Min and 1Hour/regular
use public native BarBuilder aggregates of retained minute OHLCV on the actual
calendar session-open grid, clipping the final bucket at session close. Derived
aggregate provenance remains distinct from provider coarse bars. Missing minute
coverage, incompatible native price precision or noninteger volume remains
unavailable; no empty bars are invented. 1Day/provider_day closes at the next
New York midnight. Other combinations remain unavailable with a reason.
App qualification is separate from provider entitlement.

Edit reusable formula expressions and typed formula parameters in the existing
**Chart analysis** editor, save a new immutable revision, then refresh scanner
metadata and select that exact UUID/revision/hash/component. Programs reuse the
D63 allowlisted AST engine; no Pine code, arbitrary scripts or second engine is
supported. Formula rolling calculations run on each original input axis before
backward closed-bar alignment. Program crossings require two actual anchor
observations. Existing D42 observed-run crossings keep their original behavior.
The advanced JSON editor retains Yahoo queries, targets, collection bounds and
existing typed conditions; **Apply advanced JSON to program controls** refreshes
the controls after a manual edit.

Export the selected revision or full scan library; import validates the bundle
and exact transitive chart definitions. Imported definitions receive fresh scan
identities with scheduling and attention authority off, requiring explicit review.
Saving and importing do not run a scan. Select a saved revision before Run.
An optional historical UTC cutoff is retrospective unless original availability
evidence establishes historical knowledge. **known_then** is unavailable without
that evidence; actual capture, knowledge and calculation times stay separate.
Inspect an exact retained run, select its symbol and actual anchor observation,
then inspect selected source identities, ordinals, expected buckets, ages,
availability, condition values and prior/current crossing evidence. Calculation
artifacts retain exact dependencies, implementation and source hashes. A true or
false aggregate can still have partial coverage; failed, canceled and unprocessed
work remain separately recorded. Source integration has not been exercised here;
no scan, chart calculation, collection, schedule or runtime activation was run.

Save an immutable definition revision before running it. Its target is an explicit
fixed symbol list, saved watchlist Snapshot/Follow, or provider query. Each run
retains its exact definition and frozen membership/provider selection, cutoff and
source evidence. Edits do not rewrite old runs. Provider captures after the cutoff
remain separately dated; a dispatch cutoff is not a claim of historical knowledge.
Each interval requires its own eligible closed-as-of/fresh observations; another
interval cannot supply its freshness. Missing or incompatible data stays unavailable.
With a query plus fixed/watchlist target, only their intersection is evaluated.
Omitted members have no new predicate result and do not clear an existing latch.
Re-entry is not a membership reset; another occurrence needs an evaluated clear
first. Partial query enumeration cannot prove omitted symbols are non-matches.

The selected saved revision exposes source mode, IEX feed, adjustment, lookback,
symbol/page/interval/request-work bounds and the time limit. Retained mode reads
saved inputs; provider queries and fresh history require explicit collection mode
and the separate collection-consent checkbox before Run or schedule opt-in.
Bounds stop future dispatch, not a provider call already in flight; inspect actual
budget counters and partial-universe coverage in the retained run. Canceled or
unprocessed work is separate from evaluated missing/failed data.
`max_requests` counts explicit provider dispatch operations; yfinance can make or
retry additional HTTP calls internally. It is not a strict HTTP-call count.

New and edited definitions have scheduling off. **Explicitly opt in selected saved
schedule** is a separate action using the displayed immutable revision, cadence,
America/New_York timezone and session gate. Only one run per definition is active;
durable schedule slots, skipped overlaps and restart gaps remain inspectable.
Cadence uses elapsed UTC minutes; the regular-session gate follows the recorded
New York calendar and daylight-saving rules, rather than a local-time cron promise.
Stopped/restarted intervals are not backfilled. Disable scheduling or cancel future
work explicitly; old results retain their original source and revision.
Scheduling while the app is stopped requires a separate capability and is not
provided by saving or opting in to an in-app schedule.

ALL clears when any condition clears, otherwise is unavailable if any input is
unknown, otherwise matches. ANY matches when any condition matches, otherwise is
unavailable if any input is unknown, otherwise clears. Partial evidence remains
visible even with a conclusive aggregate. Only conclusive clear rearms an optional
deduplicated attention event; unknown and acknowledgment do not. Exact per-symbol,
per-interval evidence is retained for inspection. Scanning grants no trade, agent
research or notification authority. These source changes have not been activated
or accepted through an actual scan, schedule, provider collection or browser run.


## Broker update-stream recovery

Settings shows the latest broker trade-stream state separately from account/order
reconciliation. A listening socket can still have unresolved commands; their IDs,
reasons, pending checks and last attempt times remain visible. Those commands keep
their commitments and applicable order blocks. Use **Refresh account and order
status** for an explicit reconciliation attempt. A historical, disconnected or
unavailable worker snapshot does not establish current update coverage.


## Dated FRED availability observation

A CPIAUCSL observations request returned HTTP 200 on 21 October 2026 at
23:41:12 PDT. This supersedes only the earlier CPI maintenance failure for that
request. It does not establish availability, completeness or correctness of every
macro series, or acceptance of a new research run. Broader macro collection and
research acceptance remain open; no new report was generated for this check.


## Unsupported broker instruments and order groups

Broker observations retain unsupported asset classes, multi-leg parents and their
actual nested legs. Missing parent symbols, quantities, fills and commitments stay
unavailable or unknown; they are not reconstructed as an equity order. Open orders
and holdings expose the retained broker identity, class, legs and import assessment
as JSON. Source-reported numeric fields remain readable beside supported equities.
Unsupported rows have no stock-inspection action, native conversion or management
eligibility; their remaining exposure, reservations and account weight are unknown.
Their presence does not hide supported equity facts or make unknown commitments
zero. This source integration has static verification only, without broker requests
or browser/runtime acceptance.
