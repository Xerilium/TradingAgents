# SPY fund management: cash, distributions and gain/loss review

## Status

Research complete; implementation design in progress. Baseline: `b906008` on
`nautilus`, 5 November 2026. Work is in `D:/src/TradingAgents`; the documented
`C:/src/TradingAgents` checkout does not exist on this machine.

The user authorized research, planning, implementation and incremental local
commits. They selected US jurisdiction and paper accounts for this phase.
They did not authorize broker orders, approvals, cancellations, standing trading
authority, account transfers, credentials work or a production upgrade.
No arbitrary 2% or 5% reserve has been saved.

## Goal

Operate a small self-owned SPY-benchmarked portfolio of accounts that can fund
living expenses, retain enough liquidity and support deliberate gain/loss
management. Do not optimize tracking at the expense of required distributions,
or describe cash withdrawals as investment losses.

### Required outcomes

- Explicit account-bound reserve and distribution terms, without invented
  household spending, tax rates or risk preferences.
- Dollar-based spending reserve, tax provision and operating liquidity, with
  clear interaction with the existing percentage cash-floor trading rule.
- SPY constituent sizing against investable capital after the effective reserve;
  show the resulting full-account exposure and tracking trade-off.
- A useful paper gain/loss review and ordinary exact sell-draft preparation,
  without claiming average cost is a selectable tax lot or granting authority.
- Separate account plans without treating stale or unobserved accounts as a
  consolidated live fund. Current broker runtime observes one account at a time.
- Existing account-history coverage and benchmark-method limits remain visible.
  No fabricated total returns, tax savings, withdrawable cash or bank transfers.
- Plans, previews and dispatch checks bind to the same account and revision.
  Recovery validates new durable records. Existing approval/submission boundaries
  remain intact.

## Research findings

1. **Reserve dollars follow spending needs.** Vanguard describes moving a year's
   withdrawals into a money market account and considering sending taxable
   dividends/capital gains there instead of reinvesting. This is a planning
   suggestion, not a universal reserve percentage or a default we may silently
   apply. The operator must supply the withdrawal amount and coverage period.
2. **Cash has a cost and a purpose.** A spending reserve can avoid a forced sale
   on a particular date, but reduces stock participation. A SPY equity benchmark
   must not hide that deliberate allocation difference.
3. **Settlement is not withdrawability.** Most US equity transactions settle T+1
   business day; broker withdrawal availability and bank arrival are separate.
   Pending sales must not fund purchases before receipt. Cash/buying power alone
   does not establish money available for household withdrawal.
4. **Paper P&L is not a tax event.** Broker average position cost can support a
   labeled paper gain/loss estimate, not lot selection, holding-period taxation,
   household wash-sale clearance or a proven deduction. An Alpaca community
   response says FIFO/no lot selection; it is not a formal API guarantee.
5. **Benchmarking needs matching evidence.** Existing qualified account-history
   comparisons can show SPY price return, explicitly excluding dividends and
   costs. A fund total-return comparison needs dividend and cash-flow coverage
   not established by that feature. Retain unavailable states rather than
   relabeling the price comparison.

## Existing source and observed limits

- `tradingagents/web/spy_rebalance.py` supports a dedicated connected paper
  account, dated State Street holdings, manual previews and existing standing
  paper rebalancing. No authorization is inherited from those existing controls.
- `investor.py` and `policy_evaluation.py` implement revisioned percentage cash
  and other optional risk checks; human baskets and saved proposals remain
  distinct from approvals and broker orders.
- `account_history.py` and `performance.py` support account-identified retained
  intervals, qualified flow-adjusted methods and price-only comparisons.
- `recovery.py` validates durable record shapes during restore.
- Browser dev8099 showed policy revision 0. Its existing SPY preview displayed
  `Trading Rules revision undefined` and `Target stock exposure NaN%`. Source at
  the baseline supplies both fields, so a running backend/UI mismatch is a
  hypothesis, not a diagnosed cause. Missing fields must block readiness and
  render unavailable, not misleading numbers.
- No tax-lot selection, household transaction completeness, multiple simultaneous
  broker sessions, real fund aggregation or transfer execution is established.

## Sources

Accessed 5 November 2026. Primary sources distinguish guidance from requirements.

- [Vanguard: How to set up withdrawals](https://investor.vanguard.com/investor-resources-education/retirement/income-how-to-set-up-withdrawals).
  Coordinator read confirms the one-year withdrawal example and distribution
  routing suggestion; this is general guidance.
- [Schwab: How to create a retirement paycheck](https://www.schwab.com/learn/story/how-to-create-retirement-paycheck).
  Research worker reported one year of net spending in cash plus two to four
  years in liquid investments. Direct access was blocked; search evidence only.
- [SEC: T+1 settlement](https://www.sec.gov/newsroom/press-releases/2024-62).
- [Alpaca: Broker API FAQ](https://docs.alpaca.markets/us/docs/broker-api-faq).
  Broker API terminology does not establish the current Trading API mapping.
- [Alpaca: Placing orders](https://docs.alpaca.markets/us/docs/orders-at-alpaca).
  Open buys reserve buying power; pending sells are not available proceeds.
- [Alpaca community: Closing individual lots](https://forum.alpaca.markets/t/closing-individual-lots-within-a-profitable-position/18549).
  `Dan_Whitnable_Alpaca`, 8 March 2026, says FIFO/no lot selection. The fetched
  page does not establish the author's official role; treat as attributed
  community evidence, not an execution contract.
- [IRS Publication 550](https://www.irs.gov/publications/p550) and
  [Topic 409](https://www.irs.gov/taxtopics/tc409). US tax background only; no
  personal tax calculation or tax-effective paper harvesting is claimed.
- [Fidelity: Performance reporting](https://www.fidelity.com/webcontent/ap002390-mlo-content/19.09/help/learn_performancereporting.shtml).
- [State Street: SPY](https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy).

## Delivery and evidence

Use Impeccable in Operate mode for UI implementation and review. Preserve the
established workstation and current workflows. No automated tests, mocks,
benchmarks or unrelated research runs. Static checks and an affected real
browser verification batch are the validation path; no broker action is part of
that batch. Record reviewed revision, actual findings and unverified paths here.
