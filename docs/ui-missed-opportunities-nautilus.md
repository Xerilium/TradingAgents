# Missed UI opportunities: what the engine already knows

Status: audit v1 · Scope: documentation only, no application code changed
Companions: [UI redesign blueprint](ui-redesign-blueprint.md), [trader audit](ui-redesign-trader-audit.md), [desk reference](desk-reference.md)

## 1. The question

NautilusTrader 1.231.0, the Alpaca bridge and the other backend parts already
compute, store or return data that a stock trader would want on screen. Some of
it never reaches the UI. Some of it is hidden in a collapsed JSON box. This
document lists those gaps, ranks them by trader value and says where each one
fits in the blueprint wireframes without adding clutter.

This document does not repeat the six upgrades in the
[trader audit](ui-redesign-trader-audit.md) (exposure chips, price drift,
ticket sizing and so on). It adds to them.

## 2. Rules for every item

- Every item uses a field that already exists. Nothing here needs a new
  backend feature. If a field is missing, the item is on the "do not build"
  list in section 7.
- Category A: the data is already in `/api/state` or another existing route,
  but the UI hides it or buries it.
- Category B: the data exists in the Nautilus worker or Python modules, but a
  small read-only pass-through is needed before the UI can show it.
- Cash account, long only (see `PRODUCT.md`). Flags about shorting and margin
  are low value here.
- Where a section says "evidence", it means: I read the backend line and
  searched the UI scripts (`app.js`, `nautilus.js`, `command-controls.js`,
  `lists.js`) for the key. A key with zero hits is "not shown". A key with hits
  was read in context.
- Observed UI behavior and source capability are kept apart. Nothing here was
  tested against the live service and no broker action was taken.

## 3. Ranked summary

| # | Opportunity | Cat. | Trader value | Blueprint place |
|---|-------------|------|--------------|-----------------|
| 1 | Per-rule policy result with the number behind it | A | High | 6.6 Stage 2 policy check |
| 2 | Account status and trading-block flags | A | High | 6.1 Shell, 6.11 Account & Engine |
| 3 | Spread (bps) and displayed quote size next to the limits that use them | A | High | 6.3 Instrument Header Strip, 6.6 ticket |
| 4 | Today's P/L and "available to sell" on positions | A | High | 6.5 Positions Risk Table, 6.2 Dashboard |
| 5 | Nautilus return and P/L statistics for simulations | A | High | 6.7 Strategy Lab results |
| 6 | Per-fill table instead of raw JSON | A | Medium | 6.6 Fills & Audit History |
| 7 | "Not sent" or "unknown if sent" summary on each command | A | Medium | 6.6 blotter, 6.6 Stage 3 |
| 8 | One-line exit state for linked orders | A | Medium | 6.6 blotter row |
| 9 | Basket impact: weights, turnover, cash, partial-fill case | A | Medium | 6.6 Baskets, 6.5 Proposed |
| 10 | Drawdown and benchmark drawn on the performance chart | A | Medium | 6.5 Performance |
| 11 | Walk-forward folds and closed-trade list | A | Medium | 6.7 Strategy Lab |
| 12 | Asset badges: fractional, overnight, halted, exchange | A | Medium | 6.3 header strip, 6.4 Research header |
| 13 | Market opens/closes countdown | B | Medium | 6.1 Shell |
| 14 | Live-updates dot for the broker trade stream | A | Medium | 6.1 Shell |
| 15 | Fee provenance: actual or modeled | A | Medium | 6.6 Fills & Audit History |
| 16 | Reconciliation gap list in plain words | A | Medium | 6.11 Diagnostics, 6.1 Shell |
| 17 | Native risk engine trading state chip | A | Low | 6.11 Diagnostics |
| 18 | Native margin figures | A | Low | 6.11 Account & Engine |
| 19 | Instrument precision, tick and lot | B | Low | Do not surface |
| 20 | Cache persistence and epoch | B | Low | 6.11 Diagnostics |

## 4. Category A: already in `/api/state` or an existing route

### A1 · Per-rule policy result with the number behind it · High

- **What exists.** The ten policy rules are listed in `investor.py:14-17`:
  cash reserve, max position, gross exposure, loss limit, scenario loss, sector,
  correlation, spread, quote size and quote age. `policy_evaluation.py:53-54`
  returns `checks[]` with `name`, `passed`, `reason` and `details` for each.
  `risk_evaluation.policy_scenarios` also holds the current, pending and
  proposed calculations.
- **What the UI does.** `impactMarkup()` in `app.js` (the `proposal-policy-scenarios`
  block) shows a list of text conditions and puts everything else in a collapsed
  `<details><pre>` JSON dump.
- **Trader value.** This is the answer to "why was my order blocked, and by how
  much?" It is the most important thing on the order screen.
- **Place it.** Blueprint 6.6, Stage 2 policy check. Show ten rows: rule name,
  pass or fail, the observed value and the limit. Fail rows first. Keep the JSON
  below as "Technical detail".
- **Limit.** There is no `headroom` field. Show headroom only where `details`
  already holds both the value and the limit. Do not compute new risk numbers
  in the browser.

### A2 · Account status and trading-block flags · High

- **What exists.** The worker keeps the whole Alpaca account row
  (`nautilus_worker.py:853`, `observed["account"]`). It reaches the UI as
  `state.account`. The row includes `status`, `trading_blocked`,
  `account_blocked`, `trade_suspended_by_user`, `pattern_day_trader`,
  `daytrade_count`, `multiplier`, `regt_buying_power`,
  `daytrading_buying_power`, `initial_margin` and `maintenance_margin`.
  `/v2/account/configurations` is read at `nautilus_worker.py:894` and returned
  as `account_configuration`.
- **What the UI does.** The Dashboard shows five numbers: equity, cash,
  buying power, long value and open orders. None of the flags above appears in
  `app.js`, `nautilus.js`, `command-controls.js` or `lists.js`.
- **Trader value.** A blocked or suspended account explains every rejected
  order. A day-trade count matters if the paper account is margin type.
- **Place it.** Blueprint 6.1 Shell: show a chip only when the account is not
  active or is blocked. Blueprint 6.11 Account & Engine: a quiet read-only table
  with the other fields. Do not add them to the Dashboard.
- **Limit.** `pattern_day_trader`, `daytrade_count` and margin fields matter only
  for a margin account. Hide them when the account is cash.

### A3 · Spread (bps) and displayed quote size next to the limits that use them · High

- **What exists.** Every native quote has bid, ask and sizes
  (`nautilus_worker.py:309-310` builds the `QuoteTick` from `bp`, `ap`, `bs`,
  `as`). It reaches the UI as `state.nautilus.market_data[symbol].quote`.
  The last trade also has size and `trade_id`. Two of the ten policy rules
  (`max_spread_bps`, `min_quote_size`) use exactly these numbers.
- **What the UI does.** Only the option header shows bid and ask
  (`bid_price`, `ask_price`). The key `bid_size` and `ask_size` appear nowhere
  in the UI scripts. Stock quotes show one price, the quote age and the feed
  (`quoteStatus`).
- **Trader value.** Spread and size show how costly a limit order will be before
  the user types a price.
- **Place it.** Blueprint 6.3 Instrument Header Strip: `bid x size · ask x size
  · spread bps`. Blueprint 6.6 ticket: the same line under the price field,
  next to the two policy limits it is checked against.
- **Limit.** Spread in bps is `(ask - bid) / mid`. That is arithmetic on two
  existing numbers, not a new source. IEX sizes cover IEX only, so label them
  "IEX displayed size".

### A4 · Today's P/L and "available to sell" on positions · High

- **What exists.** Worker positions are the raw Alpaca rows
  (`nautilus_worker.py:853`). They carry `cost_basis`, `lastday_price`,
  `change_today`, `unrealized_intraday_pl`, `unrealized_intraday_plpc`,
  `qty_available` and `side`.
- **What the UI does.** `positionsTable()` shows symbol, quantity, average cost,
  market value, total unrealized P/L and weight. The keys `cost_basis`,
  `lastday_price`, `change_today`, `qty_available` and
  `unrealized_intraday` have zero hits.
- **Trader value.** "What did I make today" and "how many shares can I still
  sell" are daily questions. `qty_available` also explains why a sell is
  refused when shares are tied up in open orders.
- **Place it.** Blueprint 6.5 Positions Risk Table: add "Today" and
  "Available" columns, hidden on narrow screens. Blueprint 6.2 Dashboard: one
  "Today" figure beside equity, summed from the same field.
- **Limit.** Add a field only after reading one live position row; Alpaca
  omits some fields for some asset types.

### A5 · Nautilus return and P/L statistics for simulations · High

- **What exists.** After a simulation, `evaluation_worker.py:1218` and `:1322`
  store `asdict(engine.get_result())`. In Nautilus 1.231.0, `BacktestResult`
  has `stats_pnls` and `stats_returns` (I checked the installed package). The
  portfolio analyzer behind them calculates win rate, profit factor,
  expectancy, Sharpe-style ratios and volatility. `evaluation_worker.py:1316`
  reads the analyzer only for the return series.
- **What the UI does.** `stats_pnls`, `stats_returns`, `Sharpe`, `Win Rate` and
  `profit_factor` have zero hits in the UI scripts. The Strategy Lab shows
  net return, modeled P&L, maximum drawdown and closed-trade count.
- **Trader value.** A strategy with a 70% win rate and a profit factor under 1
  looks very different from one with a 35% win rate and a factor of 2. Today the
  user cannot see this.
- **Place it.** Blueprint 6.7 Strategy Lab, results card: add a small
  "Quality" group under the existing four metrics. Show names exactly as
  Nautilus labels them.
- **Limit.** Confirm that the `/api/evaluations` payload carries `native_result`
  (the retained result blob) before wiring. Nautilus may report short runs
  with missing values. Show "not calculable" in that case, as the Performance
  tab already does.

### A6 · Per-fill table instead of raw JSON · Medium

- **What exists.** `state.fills[]` has price, quantity, commission, time and
  `native_application` (`proven_in_current_process`, `unresolved` or
  `historical_source_only`).
- **What the UI does.** The order inspector's Fills tab prints each fill as a
  `<pre>` JSON block (`brokerOrderTable()` in `app.js`).
- **Place it.** Blueprint 6.6 Fills & Audit History: one small table (time,
  quantity, price, commission, source). Add "vs limit" only for limit orders,
  using the order's own limit price.
- **Limit.** There is no slippage figure against the quote at submit time.
  Do not invent one.

### A7 · "Not sent" or "unknown if sent" summary on each command · Medium

- **What exists.** `execution_lifecycle.py` records `not_sent`,
  `transport_intent`, `submitting` and related states with a timeline
  (`:121-124`, `:720`). The unknown-outcome case is stored as
  `outcome_unknown`.
- **What the UI does.** The strings exist but each appears only twice in the
  UI scripts. They sit inside command history text, not in a status chip.
- **Trader value.** After a timeout, the question is "did my order go out?"
  The answer must be one plain sentence, not a state name.
- **Place it.** Blueprint 6.6 blotter row and Stage 3: a chip with three words:
  "Not sent", "Sent", "Unknown. Check Alpaca".
- **Limit.** Wording only. Do not add retry or resend actions.

### A8 · One-line exit state for linked orders · Medium

- **What exists.** Orders carry `group_class`, `group_role`, `parent_order_id`,
  `exit_active` and `exit_reserved`; legs are nested in `legs`.
- **What the UI does.** The order inspector groups legs and shows each role.
  `exitPlanMarkup()` shows the planned stop and target. The summary state
  (entry waiting, protected, exit active) is not shown on the row.
  `replaced_by` has zero hits, so a replaced order's successor is not linked.
- **Place it.** Blueprint 6.6 blotter: one chip per parent row, such as
  "Entry open · exits waiting" or "Protected".
- **Limit.** Derive the chip only from existing fields.

### A9 · Basket impact: weights, turnover, cash, partial-fill case · Medium

- **What exists.** `baskets.py:117-154` returns `hypothetical_cash`,
  per-holding `equity_weight_pct_estimate`, `turnover_pct`, gross buys and
  sells, fees, and both `complete_scenario` and `partial_scenario`.
- **What the UI does.** `basketPanel()` shows target quantities and residuals.
  The impact numbers sit in a `<details>` block.
- **Place it.** Blueprint 6.6 Baskets: a small before-and-after weight table
  and one line, "Cash after: X · Turnover: Y%". Add the same table to the
  Portfolio > Proposed tab (6.5).
- **Limit.** These are estimates. Keep the existing estimate wording.

### A10 · Drawdown and benchmark drawn on the performance chart · Medium

- **What exists.** `performance.py` computes linked time-weighted return,
  drawdown, a Modified Dietz estimate, external flows and the benchmark
  price-return and excess return. `account_history.py` stores portfolio history
  with `cashflow` and `profit_loss_pct`.
- **What the UI does.** Return, drawdown and benchmark excess are already shown,
  but as text lines (`performanceMetric()`). The chart shows equity or
  returns only. The benchmark series is in a JSON `<details>`.
- **Place it.** Blueprint 6.5 Performance: draw the benchmark as a second line
  and shade the drawdown. Mark external cash flows as small ticks.
- **Limit.** Keep "not calculable" states. Do not infer intraperiod extremes;
  `performance.py` says it does not.

### A11 · Walk-forward folds and closed-trade list · Medium

- **What exists.** Strategy runs keep fold results, trial parameters and the
  native `orders`, `fills`, `positions` and `account` tables
  (`evaluation_worker.py:1181-1182`, `:1314-1315`).
- **What the UI does.** Headline metrics, equity curve and benchmark curve are
  shown. Folds, trials and the native tables are in `<details>` JSON.
  `parameter_importance` and `subperiods` have zero hits.
- **Place it.** Blueprint 6.7 Strategy Lab: a "Folds" table (one row per fold:
  period, return, drawdown) and a "Trades" table from `reports.positions`.
- **Limit.** Folds measure stability, not profit. Keep the existing warning
  that these are modeled results.

### A12 · Asset badges: fractional, overnight, halted, exchange · Medium

- **What exists.** `market_data[symbol].session_eligibility` has
  `overnight_tradable`, `overnight_halted`, `fractionable` and
  `fractional_eh_enabled`. The instrument `info.alpaca_asset`
  (`nautilus_worker.py:183-184`) also keeps `exchange`, `status`, `tradable`
  and `attributes`.
- **What the UI does.** `proposalSessionMarkup()` writes these as a sentence
  inside the order ticket. Nothing appears on the watchlist or the stock
  header. `alpaca_asset` and `attributes` have zero hits.
- **Place it.** Blueprint 6.3 Instrument Header Strip and the 6.4 Research
  header: up to three small badges, shown only when something is unusual
  ("Fractional", "Overnight halted", "Not tradable").
- **Limit.** The Alpaca `attributes` list is shown as returned. Do not
  translate values that are not documented by Alpaca.

### A13 · Live-updates dot for the broker trade stream · Medium

- **What exists.** `execution_lifecycle.py:36`, `:1442`, `:1448` set
  `stream_status` (`not_started`, `connecting`, `listening`) with a `gap`
  text. It is in `state.nautilus.trade_stream`.
- **What the UI does.** `tradeStreamMarkup()` is already written but lives in
  Diagnostics. The Shell does not show it.
- **Trader value.** If updates stop, fills may not appear. The user should see
  this without opening Settings.
- **Place it.** Blueprint 6.1 Shell: one dot beside the existing engine status.
  Click opens the existing text.
- **Limit.** Reuse the existing wording and states.

### A14 · Fee provenance: actual or modeled · Medium

- **What exists.** The native report returns `fee_provenance.fill_sources[]`
  with `actual_commission`, `native_fee` and `native_application`.
- **What the UI does.** It is only in the native report `<details>` JSON.
  `native_fee` has zero hits.
- **Place it.** Blueprint 6.6 Fills & Audit History: one column, "Fee:
  actual / modeled / unknown".
- **Limit.** Alpaca equity commission is zero in the model. Label it as modeled.

### A15 · Reconciliation gap list in plain words · Medium

- **What exists.** `reconciliation.gaps`, `reporting_gaps`, `native_recovery_action`
  and `recovery_history`. `service.py:2146` copies `gaps` into `state.errors`.
- **What the UI does.** The Health table shows "Account import: incomplete".
  The gap sentences appear as an error source. `reporting_gaps` has zero hits.
- **Place it.** Blueprint 6.11 Diagnostics: a list under the status row.
  Blueprint 6.1 Shell: the existing chip links to it.
- **Limit.** Show text as written. Do not paraphrase gap meaning.

### A16 · Native risk engine trading state chip · Low

- **What exists.** `native_risk.values.trading_state`, submit and modify rate
  limits, and per-instrument notional caps.
- **What the UI does.** Already shown in the Orders panel "Native risk limits
  and cached reports", closed by default.
- **Place it.** Blueprint 6.11 Diagnostics only. Add a shell chip only if
  `trading_state` is not active.

### A17 · Native margin figures · Low

- **What exists.** `native_balance` (`total`, `locked`, `free`) and
  `reported_margin` for margin accounts.
- **What the UI does.** A JSON box in the Nautilus panel (`nautilus.js`).
- **Place it.** Blueprint 6.11 Account & Engine, only when the profile is the
  margin simulation. A cash account has no margin to show.

## 5. Category B: needs a small read-only pass-through

### B1 · Market opens/closes countdown · Medium

- **What exists.** The Alpaca clock row has `next_open` and `next_close`. The
  worker reads it (`nautilus_worker.py:841`, `:853`) and keeps it in
  `raw_observation.clock`.
- **Gap.** `service.py:2162` returns only `{"is_open": ...}` as `state.clock`.
  `lists.js` `marketState()` expects `timestamp`, `next_open` and `next_close`,
  so it can never use them. The UI falls back to `is_open`.
- **Wiring.** Pass the three fields through `state.clock`.
- **Place it.** Blueprint 6.1 Shell: "Market closed · opens in 14 h 20 m".
  It also explains stale quotes outside regular hours.
- **Limit.** This does not show extended hours. Alpaca's clock covers regular
  hours only; keep the existing extended-session warning.

### B2 · Instrument precision, tick and lot · Low · do not surface

- The worker builds each equity with fixed `price_precision=2`, tick `0.01` and
  lot size `1` (`nautilus_worker.py:188-190`, `native_types.py:25`). Only size
  precision changes (9 for fractional assets). Showing this adds no
  information beyond the Fractional badge in A12.

### B3 · Cache persistence and epoch · Low

- `persistence` and `native_epoch` are in `state.nautilus`. The Nautilus cache
  is in memory by design (`PRODUCT.md`). A "last verified snapshot" line in
  Diagnostics (6.11) is enough. Do not show it on trading screens.

## 6. What the UI already shows well (no work needed)

Checked in the code, so they are not missed opportunities:

- Native cached reports for orders, fills, positions and account, with
  download, in the Orders "Native risk limits and cached reports" panel.
- Order inspector with Terms, Timeline and Fills tabs, and grouped legs.
- Quote freshness, session state and change percent (`quoteStatus`).
- Session and fractional eligibility sentence in the ticket.
- Linked time-weighted return, drawdown and benchmark excess as text rows.
- Position outcomes, activities and dividends in the Journal.
- Broker trade stream text and reconcile button in Diagnostics.

## 7. Do not build or surface

- Money-weighted return, attribution and portfolio Sharpe for the real account.
  `performance.py` does not compute them. Nautilus ratios in A5 belong to
  simulations only.
- Shortable, easy-to-borrow and short-selling flags as primary content. The
  desk is long only. Use them at most as the reason a sell is disabled.
- Instrument precision tables (B2).
- Any "slippage versus quote" number. The data is not captured.

## 8. Suggested order of work

1. A1, A2, A3 and A4. These sit on the order path and the daily view.
2. A5 and A11. They give Strategy Lab results a real quality read.
3. A6 to A9 and A13. These calm the order lifecycle screen.
4. B1, A10, A12, A14 and A15.
5. The Low items only when Settings is redesigned.

## 9. Evidence gaps

- Field names for Alpaca rows come from the Alpaca API and the way the worker
  stores them. I did not read a live account row. Check each field on a real
  row before building.
- Whether `/api/evaluations` returns the full `native_result` blob was not
  traced end to end.
- No browser test or live-service call was made for this audit.
