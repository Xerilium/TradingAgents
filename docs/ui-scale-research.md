# Paper desk: usability and scale

Scope: polish and harden the existing local paper desk for a stock universe of
500 instruments. Preserve the linked workstation, existing account provider,
and deterministic paper-order policy. This is an operating interface, with
explicit research selection and individually reviewed orders.

T-1.10 supersedes the earlier Laya review UI: social classifications are source
evidence, never research or order clearance. Older screenshots and verification
observations in this document remain historical evidence of their tested revision.

## Peer evidence

Primary sources reviewed on 2026-10-13:

- [Fidelity Trader+ migration demonstration](https://www.fidelity.com/learning-center/trading-investing/trading-platforms/atp-ftplus)
  describes removing the former 50-symbol watchlist limit, importing lists or
  CSV files, and maintaining a 500-symbol list with linked chart and quote tools.
  It also exposes more watchlist columns and symbol search.
- [TradingView: scan a watchlist](https://www.tradingview.com/support/solutions/43000724549-how-to-scan-watchlist-or-flagged-list/)
  scopes the screener to a chosen watchlist. It makes an empty filtered result
  distinct from an empty universe and permits saving that scope.
- [IBKR Mosaic market scanners](https://www.interactivebrokers.com/campus/trading-lessons/mosaic-market-scanner/)
  is the peer reference for narrowing a large universe through a table of
  candidates and visible criteria, while preserving instrument context.
- [Alpaca historical bars](https://docs.alpaca.markets/us/reference/stockbars)
  documents that multi-symbol results are sorted by symbol and may require
  pagination to reach later symbols. A single limited response is not evidence
  that every stock has chart history.

These sources inform interaction patterns. They do not establish trading alpha,
model accuracy, or a performance claim for this application.

## Current evidence and changes required

| Requirement | Existing limitation | Completion evidence |
|---|---|---|
| Configure 500 stocks | Server limit is 50; symbols are typed into one field | Validated import/paste/export and server acceptance at 500 |
| Find and prioritize stocks | Every row and symbol chip is rendered | Search, filters, sorting, bounded pages, explicit selection and empty states |
| Keep linked context | Charts for all symbols fetched at refresh | Only the selected chart loads, including loading/error/retry and selection-race handling |
| Monitor research at scale | Full reports copied and polled repeatedly | Compact state plus requested report detail, queue counts and observed duration estimates |
| Review decisions honestly | Rating obscures research and source status | Visible research completion, social coverage and freshness alongside ratings and evidence |
| Operate during failures | A single error can obscure missing/stale data | Source-specific errors, timeouts, stale-state labels and input-preserving recovery |
| Keep interaction stable | Full page replaced every poll | Preserve inputs, selection, scroll, disclosures and keyboard focus |
| Handle large order/position lists | Unbounded tables | Search/filter/page counts and every existing order action remains reachable |
| Verify usability | Prior fixtures concentrate on FANGMAN | Desktop/mobile/intermediate views and realistic 500-stock fixtures plus failures |

## Working design

The index is the candidate universe. Selection names the research workload;
filtering the list never silently changes that selection. Large universes open
with no research selected. Operators can select visible matches, clear a
selection, inspect its count, and review the workload before launching it.

Research remains sequential at the existing runtime. Duration estimates must
come from recorded completed stock runs, explain their basis, and remain absent
when there is no observation. A large sweep can cross a trading-date boundary;
existing freshness gates continue to prevent stale paper execution. The desk
must explain this before a large launch. A smaller research selection keeps the
500-stock universe intact and uses its portfolio allocation policy.

Snapshots load in bounded symbol batches. History loads for the instrument in
focus. Polling carries summaries; full reports and raw artifacts load only when
requested. Test fixtures are visibly separate from the connected paper account.

## Verification record

The first implementation stage is verified:

- Before list changes, the 500-stock render fixture produced 249,855 HTML bytes,
  500 watchlist rows and 500 linked symbol buttons (31.8 ms in the Node harness).
- Live polling changed from 122,295 bytes to 12,033 bytes for the same saved
research run. Reports and raw per-post Laya output are omitted from compact polls;
  the requested AAPL detail still returns all nine report artifacts.
- The server accepts up to 1,000 symbols, fetches snapshots in batches of 100,
  and loads one chart on demand. The 500-stock batch, partial failure,
  summary/detail, caching and legacy-artifact contracts are covered by tests.
- Browser reads have 15-second deadlines and actions have 120-second deadlines.
  Stalled fetches and stalled bodies are tested, including recovery and explicit
  uncertainty for an order submission. A submission timeout never presents a
  blind retry control. Cancelled browser connections are handled quietly.
- All 89 focused backend tests, JavaScript workflow/render checks, request
  timeout checks and scoped Ruff pass. Foreground checks use a hard command
  deadline and stop their own process tree on expiry. The service startup check
  has a separate ten-second deadline; the desktop service intentionally persists.

The collection implementation was verified on 2026-10-14:

- The watchlist, run stocks, positions, proposals and order blotter have search
  and bounded pages of 25, 50 or 100. Filtering preserves the research selection;
  page selection, selecting all visible matches and clearing are explicit.
  The linked instrument panel uses previous/next controls instead of 500 chips.
- A 500-stock render produces 18,846 HTML bytes, 25 watchlist rows and no symbol
  chips (17.04 ms in the same Node harness). This is fixture evidence, not a
  production browser benchmark or a 500-stock model run.
- Browser verification imported the 500-row CSV, saved the index without
  automatically selecting all stocks, and exported a CSV verified to contain
  exactly S000 through S499. The real seven-stock paper profile was preserved.
- The final watchlist page and S499 paper-order preview are reachable. No order
  was submitted. The 500-stock workload review shows the captured selection,
  models, trade date and an estimate derived only from matching completed runs.
  A changed configuration revision rejects the reviewed workload on the server.
- Ratings, research failure and social classification coverage are separate. Missing and
  stale quote filters use the execution policy's 15-minute / 60-second bounds,
  including the quote timestamp when available. Failed research never reads as
  completed. Laya sentiment never provides trade clearance.
- Active search nodes, caret, selection, table scrolling, report disclosures
  and settings drafts survive polling. Import freezes the settings form before
  opening the file picker so polling cannot detach that input.
- The 1280-, 1024- and 390-pixel browser views were checked. Mobile research
  collections use a bounded two-column list; report text is 14 px and form
  inputs are 16 px. Wide order tables scroll within their own panel. The page
  itself does not overflow at the tested widths.
- All 1,485 offline tests and 103 subtests pass, with four expected skips and
  one integration test excluded. JavaScript collection/workflow/timeout checks
  and scoped Ruff pass. Missing Gateway domains are rediscovered on refresh;
  their later appearance does not require restarting the desk.

The browser upload tool initially stalled despite its requested timeout. The
form replacement issue was corrected and the subsequent 500-row browser import
passed under an explicit outer deadline. Foreground commands terminate their
own process tree on expiry; browser checks also carry explicit promise deadlines.

Saved visual evidence (synthetic data, isolated from the actual paper account):

- [Desktop](../.impeccable/review/scale-desktop.png)
- [Mobile research](../.impeccable/review/scale-mobile-research.png)
- [Mobile orders](../.impeccable/review/scale-mobile-orders.png)

Additional primary sources reviewed on 2026-10-14:

- [TradingView watchlist guide](https://www.tradingview.com/support/solutions/43000745825-mastering-the-tradingview-watchlists/)
  supports symbol search, metric sorting, importing lists and linked symbol
  details. These informed the bounded candidate list and instrument controls.
- [Fidelity positions/watchlist help](https://www.fidelity.com/products/atbt/help/ActiveTraderTools_Watch_List_Help.html)
  provides the peer context for combining watchlists and positions in one desk.

The 500-stock UI was verified with an explicitly labelled local fixture; it
does not represent market facts, real model output, live broker connectivity,
or a completed 500-stock trading run. The Alpaca service was not running during
this UI verification.

## Backend traffic correction, 2026-10-14

After the user reported excessive backend traffic, the agent-owned desk process
and its browser tab were stopped. Verification for this correction is offline.

The report-detail loader used revision equality as its cache guard. When the
detail revision differed from the polled summary, its completion rendered the
page and fetched the same detail again. The regression test reproduces the old
loop with a four-request cap; the corrected loader fetches once for a requested
revision, accepts newer cached detail and permits an explicit manual retry.

Idle state polling and automatic initial broker refresh are removed. Periodic
summary reads occur only for a connected, active research run, and cease after
a read failure. State reads return cached Codex readiness without spawning
account checks, including after cache expiration. Research launch still checks
the account explicitly. Chart history has no automatic expiration-triggered
fetch; an operator's refresh or selecting an uncached stock can load it.

The traffic/workflow/collection/timeout JavaScript checks and all 92 focused
backend tests pass. The live desk remains stopped; no live backend load test was
performed for this correction.

The subsequent [live verification](live-verification.md) passed against the
running Maenifold, Laya and Alpaca paper services. It includes measured idle
request counts, completed research, retained failure evidence and guarded
proposal creation. The ordinary desk is running again.
