# Live API and workspace UAT, 28 October 2026

## Result

Read-only inspection of the installed production desk at http://127.0.0.1:8098 held for the assigned surfaces. The paper account was verified, Nautilus 1.231.0 was connected, cash, equity, and buying power were each 100,000 USD, and the saved universe was the 24-stock PNIS list. No order was approved or submitted. No research run was started. No setting was saved through Settings.

This is not a rerun of the 19 October 49-case ledger, and it does not certify broker submission, cancellation, replacement, or a new research cycle. The 19 October report described a 503-symbol index and ten saved runs. Those counts are historical. Scoring the current 24-stock desk against them would be a false failure.

## Observation window and method

Observations ran from about 2026-10-29T02:02:00Z to 2026-10-29T02:39:01Z, which is 7:02 PM to 7:39 PM Pacific on 28 October 2026. The market was closed.

API reads used the installed production interpreter and `scripts/desk_api.py` with GET only. The helper opens the normal local session and removes the CSRF token from printed output. No POST was sent. Browser checks used the built-in browser canvas on the production origin (`http://127.0.0.1:8098/`) across all ten workspaces (`Dashboard`, `Portfolio`, `Markets`, `Research`, `Orders`, `Strategy lab`, `Journal`, `Alerts`, `Workflows`, and `Settings`). Hash navigation, in-page view tabs, and the read-only `Load` control on `Workflows` (`GET /api/workflows?name=Default`) were used. Refresh, New research, Strategy Load/Simulate, Save, Delete, Approve, Submit, Pause, Start, and Stop were not clicked.

Proposed on Portfolio was not opened. That view can start a model synthesis. Performance was opened and showed no equity history.

## Revision identity

The assigned comparison commit is `1690752f32f3b6711d4c8f177975467def2a150e` (2026-10-28 16:21:41 -0700). The running package is not a clean checkout of that commit.

Installed `payload/provenance.json` records `source_revision` `237cc048021be6798b9e975df14c1b0d0c388bca` and `working_changes_present: true`. That commit is the parent of `1690752`. The installed package directory is `tradingagents-0.7.1.dist-info`. Desk Python is 3.12.10. The recorded Nautilus wheel is 1.231.0.

Git blob comparison of the installed payload against `1690752` and this worktree (`features/docs-audit-and-uat`, rebased on `1690752`):

| File | Matches `1690752` | Matches this worktree |
|---|---|---|
| `tradingagents/web/server.py` | yes | yes |
| `tradingagents/web/static/index.html` | yes | yes |
| `tradingagents/web/service.py` | yes | yes |
| `tradingagents/web/static/app.js` | yes | yes |
| `tradingagents/default_config.py` | yes | yes |

The live Settings form showed Research data retries as 10, provider Codex, deep model `gpt-6.1-terra`, and fast model `gpt-6-luna`. That retry field is present in the `1690752` web contract. GET routes in `tradingagents/web/server.py` are unchanged between this worktree and `1690752` for the files compared above, because `server.py` blobs match.

Application identity `3f80c482d20f504d6a2469cc289460bd805937d069a9a649bf1eeae59ff72a70` is a launch-root hash from `/api/health`, not a Git revision.

## Live account and connection

`/api/health` at 2026-10-29T02:38:50Z reported service running, engine connected, engine version 1.231.0, provider Alpaca, feed IEX, and account mode `https://paper-api.alpaca.markets`. Reconciliation status was reconciled. Position and order reconciliation were true. Gaps and reporting gaps were empty. Startup errors were empty. Gateway status was ready. Local store schema was 1, journal revision 32, SQLite 3.47.1.

Compact state at 2026-10-29T02:33:03Z, and the browser account strip through 7:38 PM, agreed on these facts:

| Fact | Observed value |
|---|---|
| Account | `e508ad3a-e816-4978-bbf1-3904ffde15d9`, status ACTIVE |
| Paper and account verified | true |
| Nautilus | connected, 1.231.0, worker pid 57508, session `f413e35c-b3ac-400f-b464-4b400cbe5a23`, profile `long_only` |
| Cash, equity, buying power | 100000 USD each |
| Long market value | 0 |
| Positions, open orders, fills arrays | empty |
| New orders blocked | false |
| Broker mutations, review, admission | enabled |
| Execution profile in Settings | Long-only default, eligibility supported at the recorded observation |

`fill_history_records` was 1 while the fills array was empty. The count is not a visible fill and is not treated as one. Fill history was reported complete for the declared window starting 2026-10-02T20:13:24Z. Unsupported exposure was `none_observed`.

The header read "New orders not paused" on every page opened. Orders and Diagnostics repeated that new orders were not blocked. Pause was not used.

## Universe, quotes, and readiness

Config revision 30. Universe name PNIS. Exactly 24 symbols, all selected for research: META, AAPL, NVDA, GOOGL, AMZN, NFLX, INTC, TER, ENTG, MKSI, ONTO, FORM, ACLS, UCTT, ICHR, VECO, KLIC, AEIS, COHU, PLAB, AMKR, SGOV, SHY, BND.

Research provider Codex. Deep model `gpt-6.1-terra`. Fast model `gpt-6-luna`. Concurrency 8. Stop on failure true. Research data retries 10. Social screening limit 600 seconds and post limit 100, read from the Settings form and not saved. Readiness message: "Codex account is checked when research starts."

Quotes: 24 of 24 present at 2026-10-29T02:33:04Z. Feed text was "Nautilus / Alpaca IEX". Basis was `last_trade`. `stale` and `max_age_seconds` were null for every quote. Examples from that snapshot:

| Symbol | Price | Trade timestamp | Age at snapshot |
|---|---|---|---|
| AMZN | 254.69 | 2026-10-28T19:59:57Z | about 6.6 hours |
| INTC | 93.22 | 2026-10-28T20:46:17Z | about 5.8 hours |
| TER | 313.73 | 2026-10-28T19:59:57Z | about 6.6 hours |
| META | 616.26 | 2026-10-28T20:34:23Z | about 6.0 hours |

The browser said the market was closed and "Freshness limit not configured". Alerts said 0 of 24 stocks were within a price-age limit because no limit is configured, and that an unset limit does not establish freshness. That is consistent. It is not a missing-quote failure.

Laya was ready on CPU. Model `convaiinnovations/laya-multilingual`, revision `1720e3e3357cfe1e281542e223f8273b0890ca34`, package 0.4.14, pid 19336. No CPU fallback was recorded.

## Saved research

One run was present: `a1787835-aecb-4198-bdd0-5781f0578624`, trade date 2026-10-28, status cancelled, error "Research cancelled". It was created at 2026-10-28T19:09:52Z, cancel was requested at 19:16:12Z, and it completed at 19:16:13Z. `GET /api/runs` returned HTTP 404. Run detail is `GET /api/runs/{id}`. That detail contained 24 results.

The Research page showed "Latest research per ticker / 2026-10-28" and "24 / 24 latest stocks finished", with 3 completed, 0 incomplete, 0 failed, 0 interrupted, and 21 cancelled.

Completed results, confirmed in run detail and in the Research summary pane:

| Symbol | Rating | Completed | Revision | Social aggregate |
|---|---|---|---|---|
| AMZN | Hold | 2026-10-28T19:15:16Z | 166 | completed, Reddit and Stocktwits completed |
| INTC | Underweight | 2026-10-28T19:14:18Z | 166 | completed, Reddit and Stocktwits completed |
| TER | Sell | 2026-10-28T19:14:31Z | 122 | completed, Reddit empty, Stocktwits completed |

Each completed result included the expected report keys: market, sentiment, news, fundamentals, investment debate, investment plan, trader plan, risk debate, and final trade decision. AMZN and INTC had no saved price target. TER had no saved price target. INTC time horizon text said to reassess after the reported 29 October 2026 earnings release. TER time horizon text said 3 to 6 months. None of the three had a saved human disposition or investor note. Prepare order, Save note, and Delete were not used.

`saved_research` contained only AMZN, INTC, and TER. Markets labels that column "Saved research" and showed Hold, Underweight, and Sell for those three. Cancelled tickers, including META and NVDA, showed "No saved research" even when the latest run still holds a cancelled result and, for some symbols, completed social screening. Dashboard and Research show the cancelled status. This is a label difference between saved completed research and latest-run status. It is not evidence that the cancelled results were deleted. Documentation must not collapse those two fields.

Cancelled split inside the same run: META, AAPL, NVDA, GOOGL, NFLX, ENTG, MKSI, and ONTO had error "Research cancelled". FORM through BND had "Stopped before dispatch." The Research page collapses both to "Research cancelled". NFLX social was partial because the operator cancelled, not because a source failed. META and NVDA had completed social screening and no rating.

Completed research still records acquisition gaps. AMZN and TER include a public-source HTTP 404 with retry action stop. INTC and TER include Reddit HTTP 429 retries. TER Reddit source status remained `empty` after those retries. The UI phrase "Social screening completed" matches the aggregate status, not every source.

## Market history

`/api/market-history` revision 5. Coverage counts: configured 24, complete history 0, missing or incomplete 24, holdings outside universe 0. Catalog entries 1. Jobs 1, id `6c5a1f90-14f2-43de-8237-97b7806fe8df`. Budget text: at most one history or supplement request every 1.1 seconds, shared by two data workers, entitlement unverified. No new interval was requested.

AMZN detail had 501 raw IEX daily bars, start 2024-10-28, end 2026-10-27, captured 2026-10-28T21:47:52Z. `complete` and `pagination_complete` were true. The response states that provider pagination is distinct from verified session completeness. Required coverage method `252-completed-us-equity-sessions-v1` was not sufficient: 251 of 252 sessions, missing date 2026-10-28, reasons "Required completed sessions have missing/invalid OHLCV" and no shorter-listing exception. Supplementary gaps listed news, earnings, business facts, and corporate actions.

META, INTC, and TER detail returned `missing_retained_bars` and "No matching retained history; request the selected interval explicitly." That request was not made.

Stock evidence for AMZN, INTC, TER, and META was revision 1 with empty observations. Config notes say Alpaca news and corporate actions are unverified, `SEC_EDGAR_USER_AGENT` is unset, and `ALPHA_VANTAGE_API_KEY` is unset.

## Workspace contracts

Dashboard showed the verified paper account, 100,000 USD cash, equity, and buying power, zero positions and open orders, and the PNIS watchlist. A screenshot of that page was captured during inspection.

Portfolio Positions showed "No open holdings", 0 positions and 0 open orders, and "All changes saved". Performance showed no equity history and said missing points are not estimated. Proposed was not opened.

Markets showed the 24-symbol universe, quotes, and the saved-research column described above. No history request was started.

Research showed the latest-per-ticker contract above. AMZN, INTC, and TER detail panes were opened by selecting the saved row.

Orders Drafts showed one saved human proposal: BUY 1 SGOV, deferred, revision 2, saved 28 October 2026 at 2:44:11 PM Pacific. That matches `2026-10-28T21:44:11Z` and proposal id `214f4928-4ad7-49d2-a2dc-60b0cbe35dc1`. Open orders said "No open broker orders reported." History said no saved order commands were available and that proposal revisions remain in Drafts. Baskets showed 0 saved baskets and investor records revision 3. The basket form was not saved. The page states that approval and submission are separate.

Commands revision 114. Approvals, commands, basket executions, revocations, and control history were empty. `new_orders_blocked` was false. Recovery was not required.

Journal Decisions showed the same deferred SGOV human proposal. Rationale: "Strategy Lab tutorial scenario only. One SGOV share with a USD 100.69 limit using the observed reference price. Not an investment recommendation." Approval, broker order, and fills were none recorded. The page says the saved decision does not submit an order. Position outcomes said none have been captured. The reporting payload's outcome object has empty captures, groups, and unattributed lists. Notes had no saved follow-up. Account history had no selected saved interval. No export or broker-history collection was run.

Compact `proposals` and `historical_proposals` were empty. The deferred draft is retained in reporting and shown in Orders Drafts and Journal. It is not an active proposal list entry, an approval, or a broker order.

Alerts Inbox had no occurrences. The monitor was evaluating and repeated the unset price-age limit. Rules had no saved rules and no research priorities. Delivery showed browser permission denied, saved preference disabled, and no display attempts. Notifications were not enabled.

Workflows showed Editing none and Active Default on initial open, with saved catalog `["Default"]`. Effective config from `GET /api/workflows`: selected analysts market, social, news, and fundamentals; max debate rounds 1; max risk discuss rounds 1; max tool rounds 20; max recur limit 100. In the built-in browser canvas walkthrough, clicking **Load** (`GET /api/workflows?name=Default`, read-only) switched the status pill to `Editing: Default` and rendered the interactive Mermaid SVG workflow graph (`Market Analyst` → `Social Analyst` → `News Analyst` → `Fundamentals Analyst` → `Bull Researcher` / `Bear Researcher` → `Research Manager` → `Trader` → `Aggressive Debator` / `Conservative Debator` / `Neutral Debator` → `Portfolio Manager`), the twelve role prompt tabs (`Market`, `Social`, `News`, `Fundamentals`, `Bull`, `Bear`, `Research Manager`, `Trader`, `Aggressive`, `Neutral`, `Conservative`, `Risk Manager`), and the `Workflow YAML` tab (`prompts.yaml` and `workflow.yaml` under `tradingagents/workflows/default/`). Save, Save as, Discard, and Use for new research were not clicked.

Settings Account showed paper mode, the same account id, IEX, saved Alpaca key and secret flags, paper endpoint, and Nautilus 1.231.0 connected. Credential fields were left blank. Nothing was saved or removed. Research showed the live model and retry values above. Trading rules showed risk-check revision 0 and investor records revision 3. Optional checks were present and were not saved. Integrations showed Nautilus connected and Windows Credential Manager, production profile. OPENAI_COMPATIBLE, FRED, and TYPESAFE were saved. OPENAI, ANTHROPIC, GOOGLE, ALPHA_VANTAGE, and the other listed provider keys were not saved. Diagnostics said engine connected, account import reconciled, local store available, and new orders unblocked; `Local records → Launch and restart` still displays legacy `tradingdesk.launch.json` copy in the UI (`app.js`), which is documented as stale in the [historical desk reference](https://github.com/Xerilium/TradingAgents/blob/ac5f97e8f1047f7dc28ab8c4412806394dd5c111/docs/desk-reference.md), `docs/local-desk-guide.md`, and `.agents/skills/use-tradingagents/references/strategy-alerts-settings.md`. Diagnostics were not downloaded.

Strategy lab Simulations (`#strategy`) rendered **Simulate a saved plan**, the **Saved strategies** selector (`Amazon 50-day moving average demonstration`), and **No simulation selected**. Experiments said no experiment was selected. The evaluations API, revision 1, has one saved strategy, "Amazon 50-day moving average demonstration", zero items, and one proposal with the same id as the deferred SGOV draft. Optuna 5.0.0 was reported available. Strategy Load and Simulate were not used. Portfolio model status was idle.

Discovery is a Yahoo Finance schema for current US equities, page size 25, with 11 sectors. It was not a live scan result, and no scan was started.

## GET routes checked

Live GET, unless noted:

| Route | Result |
|---|---|
| `/api/health` | running, connected, reconciled |
| `/api/state?compact=1` | account, quotes, research, and empty order arrays |
| `/api/workspace` | revision 98 before navigation, 102 after |
| `/api/credentials` | configured flags only, no secret values |
| `/api/workflows` | Default active, effective config present |
| `/api/model-limits` | both roles unknown at 2026-10-29T02:39:01Z |
| `/api/evaluations` | one strategy, zero items, one proposal |
| `/api/market-history` | 24 configured, 0 complete under the 252-session gate |
| `/api/market-history?symbol=AMZN` | 501 bars, pagination complete, eligibility insufficient |
| `/api/market-history?symbol=META`, `INTC`, `TER` | no matching retained history |
| `/api/stock-evidence` for those four symbols | empty observations |
| `/api/runs/a1787835-aecb-4198-bdd0-5781f0578624` | 24 results |
| `/api/commands` | revision 114, no approvals or commands |
| `/api/attention` | no occurrences, no rule states |
| `/api/reporting` | one deferred decision, no captured outcomes |
| `/api/investor` | revision 3 |
| `/api/portfolio-model` | idle |
| `/api/discovery` | schema only |

`GET /api/runs` is not a list route. It returned HTTP 404 with "Not found." That matches `server.py`: detail is under `/api/runs/{id}`.

Model-limit discovery returned status unknown and "Limit discovery is unavailable for this provider." Endpoint was null. This was not a timeout.

Source-only paths, present in `server.py` and not called: backup download, command receipts, attention occurrence detail, reporting collection detail, and instrument refresh. Instrument refresh and backup download can mutate or export more than this UAT allowed.

## Inspection side effect

Hash navigation and row selection persisted view preferences. Workspace revision moved from 98 to 102. Compared fields: selected symbol changed from AMZN to TER, and `portfolioView` changed from `universe` to `holdings`. Notes, chart definitions, drawings, saved screens, and watchlist symbols did not change. The shortlist remained empty. No settings save, research delete, or order action was sent. Reverting the preference would require a POST, so it was left as observed.

## Unexercised paths

These remain unproven. They are boundaries of this UAT, not evidence that the controls are absent.

| Path | Why it was not exercised |
|---|---|
| Approve, admit, submit, cancel, replace | Broker and command mutations were excluded |
| Pause or resume new orders | Changes account command state |
| New research, retry, or delete research | Starts or removes research |
| Portfolio Proposed synthesis | Can start a model run |
| Strategy Load or Simulate | Loads or runs a simulation |
| Workflow Save, Save as, or Use for new research | Mutates saved or active workflow bundles (`Load` of `Default` was exercised read-only) |
| Settings save, credential change, Nautilus stop or start | Mutates configuration or the engine |
| Alert rule save and browser notification opt-in | Writes rules or browser permission |
| History interval request | Writes retained history |
| Journal export and broker-history collection | Export or broker read beyond the assigned GET set |
| Basket save | Creates local proposals |

The deferred SGOV draft is a tutorial record. It was not approved in this session, and its text says it is not an investment recommendation.

## Documentation consequences

Do not document the running desk as a clean `1690752` tree. Provenance names `237cc04` with working changes. The compared web handlers that differ from this worktree match `1690752`, and the live retry value is 10.

Do not document `GET /api/runs` as the research list. The list is in state. Detail is `GET /api/runs/{id}`.

Do not treat pagination `complete: true` as the 252-session gate. AMZN is the counterexample.

Do not treat "Social screening completed" as every source returning posts. TER Reddit was empty.

Do not treat Markets "No saved research" as deletion of a cancelled latest result.

Do not treat the deferred SGOV journal row as an open broker order or an active proposal.

Do not reuse the 19 October 503-symbol and ten-run criteria as the current expected state.

## Sources

- Live production desk, http://127.0.0.1:8098, observation window 2026-10-29T02:30:00Z to 2026-10-29T02:39:01Z.
- Installed provenance, `C:/Users/brett/AppData/Local/Programs/TradingAgents/payload/provenance.json`.
- Installed web files under `C:/Users/brett/AppData/Local/Programs/TradingAgents/payload/app`.
- `tradingagents/web/server.py` GET dispatch in this worktree, blob-identical to `1690752`.
- [Prior criteria at the retained Git revision](https://github.com/Xerilium/TradingAgents/blob/1690752f32f3b6711d4c8f177975467def2a150e/docs/uat/2026-10-19/uat-report.md), used only as historical context.
