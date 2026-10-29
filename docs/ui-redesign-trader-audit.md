# Professional Stock Trader Audit of UI Redesign Blueprint (Sonnet 5.5 + Grok 4.7 Rubber-Duck Reviews)

- **Date:** 2026-10-28
- **Reviewers:** Fresh `rubber-duck` subagents running **Claude Sonnet 5.5** (`sonnet-pro-trader-duck`) and **Grok 4.7** (`grok-pro-trader-duck`), instructed to evaluate `docs/ui-redesign-blueprint.md` (v2) strictly through the eyes of a professional stock trader.
- **Verification:** Every critique and fix was verified against `PRODUCT.md`, `DESIGN.md`, and the real data structures in `tradingagents/web/static/app.js`.

---

## 1. Executive Summary: Why v2 Still Felt Like a Developer App Instead of a Trading Desk

Both independent trader audits agreed that while v2 fixed the visual clutter and backend contract bugs, **it still organized screens around software database tables rather than a trader's decision loop**:

1. **The Research Verdict Was Blind to Price Drift & Age:**
   - v2 showed `VERDICT: [HOLD] · Trade Date: 2026-10-28` with **no live price, no bid/ask, no age in days, and no comparison to the close on the research date**. A trader can get burned acting on a 3-day-old `Buy` or `Hold` after the stock has already moved 6%.
   - Worse, v2 buried the **Portfolio Manager Decision** and **Trader Proposal** inside a collapsed footer at the bottom of Summary while giving top billing to 4 analyst preamble cards.
2. **Zero Position, Working Order, or Draft Awareness at the Point of Decision:**
   - When looking at `AMZN` on Dashboard, Markets, Research, or the Order Ticket, a trader could not see whether they **already owned `AMZN`** (`positions()`), had a **working order at Alpaca** (`orders()`), or had an **unsent draft proposal** (`state.investor.data.proposals`).
3. **The Order Ticket Was Blind to Market Context, Sizing Math, and Duplicate Working Orders:**
   - Stage 1 of Orders (6.6) did not display live `Last / Bid / Ask / Spread (bps)`, `Quote Age`, `Current Position`, `Cash / Buying Power`, or `% of equity` sizing math.
   - It defaulted to `MARKET` on an IEX-only feed instead of `LIMIT`, hid `Stop / Target` exits inside a collapsed accordion, and showed an unrelated `SGOV` draft on the right while editing `AMZN` on the left.
4. **Markets & Research Forced Context-Destroying Tab Hops to Stage an Order:**
   - Putting `Chart`, `Research`, `Options`, and `Position & Ticket` as four mutually exclusive tabs on Markets meant a trader had to close the chart just to see their position or fill out a ticket.
   - Clicking `Prepare Order ->` on Research navigated away to another page instead of opening a docked order-preparation drawer beside the research or chart.
5. **Watchlist Columns & Portfolio Holdings Were Built for Admins, Not Traders:**
   - Watchlists wasted columns on developer plumbing (`BARS: 1,255 / Missing` and `QUOTE AGE: Closed` repeated 24 times) instead of `LAST`, `CHG%`, `BID x ASK (SPR)`, `POS`, `UPL%`, `WORKING`, and `RATING · AGE`.
   - Portfolio (6.5) only drew the `0 positions` empty state and never specified the populated risk table, while `Proposed Model Portfolio` showed `REF PRICE (DATED)` without `LAST NOW` or `DRIFT %`.

---

## 2. The Six Trader Upgrades Incorporated into Blueprint v3

### Upgrade 1: Shared Symbol Exposure & Price-Drift Header on Every Decision Surface
Every symbol header (Markets, Research, Order Ticket) and every scan table now joins existing `state` data (`quotes`, `nautilus.market_data`, `positions()`, `orders()`, `state.investor.data.proposals`, `research`) to show:
- **Live Quote & Venue:** `LAST $252.51 (+1.14%) · Bid $252.40 x Ask $252.60 (8 bps) · IEX · 42s old`
- **Research Verdict, Age & Drift Since Research Date:** `HOLD · 1d old (2026-10-28) · Saved close @ Oct 28: $249.70 → Now +1.1%` (or `Research-date close not loaded` when daily bars aren't in memory — never confusing session `change_pct` with post-research drift).
- **Your Live Exposure Chip:** `FLAT` or `LONG 40 @ $248.10 (+$182 / +1.8%) · WORKING: SELL 10 LMT $255.00 · DRAFT: BUY 9 rev 2`.

### Upgrade 2: Trader-First Research Summary Hierarchy
On `Research → Summary`:
1. **Top Verdict, Drift & Exposure Strip:** Rating badge (only if saved), Research Date & Age (`1d old`), Saved Close vs. Live IEX Price (`+1.1% since research date`), Position/Working/Draft chip, `review_required` status, and explicit `completion_gaps` warning (`⚠ News: HTTP 429 — verdict built without News`).
2. **Portfolio Manager Decision & Trader Proposal First (Above the Fold):** First 6 lines of `final_trade_decision` and `trader_investment_plan` side-by-side, plus dated agent-claimed price levels labeled honestly (`Agent claims, dated & unmapped`).
3. **Bull vs. Bear & Risk Trio Columns:** Side-by-side excerpts from `investment_debate_state` and `risk_debate_state`.
4. **Compact Analyst Status Strip:** `Market [Saved ✓] · Fundamentals [Saved ✓] · News [⚠ 1 gap] · Sentiment [Laya: 12 Bull / 3 Bear / 5 Unclear]` — click any chip to open that report.
5. **Footer Bookkeeping:** Operator Disposition (`Needs review`) and Note moved to a compact bottom bar so they never push evidence below the fold.

### Upgrade 3: Docked `Prepare Order` Drawer (Stay on Chart or Research)
- Clicking **`[Prepare Order]`** on Research, Markets, Dashboard, or Journal opens a **docked right-side Order Proposal Drawer** on the current symbol (`openTicket(symbol)` + `researchPreparation`), without navigating away from the chart or research report.
- **Long-Only Cash Account Awareness:** If the research rating is `Sell` or `Underweight` and `positions()` has `0` shares, the button states `0 shares held (cash account, long-only)` and never pre-selects an illegal short sell. Side and Quantity remain explicit trader inputs.

### Upgrade 4: Full-Context Order Ticket with Sizing Math, Click-to-Seed Limit, & Working Blotter
On `Orders` (and in the docked ticket):
- **Header Context:** Shows `AMZN` live IEX price, `Bid / Ask / Spread (bps)`, `Quote Age` (`42s old ✓` or `⚠ Quote age unchecked` if freshness limit is unset), `Current Position`, and `Cash / Buying Power / Equity`.
- **Click-to-Seed Limit Price:** Clicking `Bid`, `Ask`, or `Last` copies that price into the `Limit $` input (labeled `"from ask, not previewed"`); historical chart bar copy retains the two-step `chart_copy` increment validation.
- **Live Sizing Math:** Typing `Qty: 20` displays `≈ $5,052.00 · 5.1% of equity · 5.1% of cash · Position weight after: 5.1%`.
- **Visible Exits:** `Stop $` and `Target $` sit directly on the ticket (not hidden in a drawer), with advanced `Bracket / OTO / OCO` details expandable.
- **Same-Symbol Alignment & Duplicate-Send Guard:** The right-hand pane always filters/highlights the **focused symbol's** drafts and working orders first, and displays a pre-submit warning if a working order already exists for that symbol (`Working in AMZN: BUY 20 LMT $252.60 — this order adds 20 more`).

### Upgrade 5: Populated Portfolio Risk Table & Proposed Model Live-Drift Columns
- **Portfolio → Positions** now specifies the full populated holdings table (`SYM | QTY | AVG COST | LAST | QUOTE CHG% | MKT VALUE | UNREAL P/L ($, %) | WEIGHT% | WORKING/PENDING | RESEARCH · AGE | ACTIONS`), flagging held positions whose research is stale or rated `Underweight / Sell`.
- **Portfolio → Proposed Model Portfolio** pairs `MODEL REF PRICE (DATED)` with `LAST NOW`, `DRIFT %`, and `YOUR POSITION` so the trader never mistakes a stale reference price for the current market.

### Upgrade 6: Trader Watchlist Columns & Non-Destructive Keyboard Flow
- **Default Watchlist / Markets Columns:** `SYM | LAST | CHG% | BID x ASK (SPR) | POS | UPL% | WORKING | RATING · AGE` (removing `BARS 1,255` and repeated `Closed` strings; `BARS` stays in the chart history bar).
- **Default Sort & Triage:** Supports `Held first` + `|Chg %|` magnitude sort, and restores the 1-line **Needs Attention** triage bar on Dashboard (`working orders`, `unread alerts`, `stale quotes`, `held positions needing fresh research`).
- **Safe Trader Hotkeys:**
  - `J / K` or `↑ / ↓`: Move focused symbol (`selectedSymbol`) without changing checkboxes.
  - `X` or `Space`: Toggle batch checkbox (`selectedSymbols`) on the focused row.
  - `Enter`: Open Research on focused symbol (or run `Preview Impact` inside the Order Ticket — **never** `Approve` or `Submit`).
  - `T`: Toggle docked Order Proposal drawer for the focused symbol.
  - When `0` stocks are checked in the batch, `[Run Research]` offers `[Run Research on AMZN]` (still opening the confirm popover) instead of sitting dead.
