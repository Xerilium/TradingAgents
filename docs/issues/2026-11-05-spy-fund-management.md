# SPY fund management: cash, distributions and gain/loss review

## Status

Implementation committed; source-review closure and real-browser verification
are tracked below. No broker execution is part of this delivery.
The user confirmed that fund-plan edits must require explicit automatic-trading
re-enablement and authorized one real affected dev-browser verification cycle
without trades, approvals, transfers, invented plan values or automated tests.
Baseline: `b906008` on
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
   household wash-sale clearance or a proven deduction. IRS Publication 550
   includes substantially identical acquisitions within 30 days before or after
   a loss sale, including spouse/controlled-corporation and IRA/Roth IRA cases.
   The ordinary replacement-basis adjustment does not apply to the IRA/Roth
   exception. The coordinator read that source section directly; none of these
   rules is represented as an implemented tax engine. An Alpaca community
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

## Implementation plan

The user confirmed the safety and validation choices through the structured
question dialog. This is the paper-account phase, not a live tax service.

### Account plans and money safety

- Save revisioned paper-account plans in the existing application store. Inputs
  are monthly net withdrawals, reserve months, tax provision and trading cushion.
  Inputs stay unset until authored. Inactive plans are planning-only; an active
  incomplete plan blocks reserve-aware SPY sizing. Other accounts' saved terms
  are inspectable, but their balances are not invented or summed.
- Calculate `monthly withdrawals * months + tax provision + trading cushion`.
  Compare that sum with the enabled percentage-policy cash floor and use the
  larger amount, not their sum. Positive observed equity and known nonnegative
  cash are required. Reserve above equity leaves no investable stock sleeve.
- Scale fractional SPY weights into full-account percentage points for the
  existing basket allocator. Apply gross and single-stock caps without silently
  renormalizing. Pending sells are not money available for buys or withdrawals.
- Bind plan presence/absence, revision and hash to preview and dispatch. Recheck
  under the maintenance boundary. Reject stale/missing bindings and require a
  reconciled account observation that reflects preceding fills before more buys.
- Material plan changes pause standing paper trading and block the current run
  before its next dispatch; the operator must re-enable explicitly. Never cancel
  an already-sent order as a side effect. Restore disables standing authority
  and makes active restored runs non-executable.

### Interface and gain/loss preparation

- Add account fund-plan terms and the derived reserve budget beside the existing
  SPY workflow. Preserve draft fields across normal refresh, expose save/conflict
  states and explain the trading pause. Missing contract values show unavailable
  and cannot produce submit readiness.
- Reuse observed holdings for a paper gain/loss review and the existing unsaved
  SELL editor route. Exact quantity, terms, review, approval and submission stay
  separate. Average-cost unrealized P&L is not selectable tax lots, realized tax
  profit/loss or wash-sale clearance.
- Keep the qualified account-history and price-only SPY comparison. No new fund
  total return, tax benefit, bank withdrawal or simultaneous-account engine.

### Delivery sequence

Research checkpoint, coherent backend/schema/recovery commit, integrated UI
commit, independent safety/scope review, coordinated corrections, then one
real affected browser cycle. Static syntax and whitespace checks are allowed;
no automated tests or synthetic inputs. Review and verification outcomes will
be recorded with the exact revision. No push or production upgrade.

## Delivery and evidence

### Integration coordination

The first implementation workflow was stopped after a resumed worker reported
concurrent edits in its backend paths. All partial changes were preserved; no
partial backend commit or runtime action was reported. The replacement workflow
has one backend integrator followed by one UI integrator, with exclusive file
ownership. Final independent review must inspect the reconciled source, not
assume the stopped worker's partial report proves correctness.

A specific review concern is post-fill freshness: a timestamp assigned after
broker reads does not prove the cash fetch began after the fill. The execution
boundary needs the pre-fetch observation time or another conservative proof.
Likewise, cash minus reserve alone is not free buying capacity when working
commitments exist. Neither figure may be labeled withdrawable cash.

### Independent review of `d98002a`

The fresh money/authority and UI/scope reviewers inspected the changes from
`b906008` to `d98002a`; separate source verifiers challenged their findings.
No test, browser, API, credential or broker action was part of this review.
Confirmed findings, deduplicated:

- P1: the new pre-dispatch guard expected `admitted_not_dispatched`, but
  `submit_approved()` already records `dispatch_intent` with transport not
  started. It would block every otherwise admissible SPY leg.
- P2: the new gain/loss view labeled connected live holdings as paper and exposed
  its preparation action without a paper-identity gate. No submission occurred.
- P1: old fund drafts lacked workspace-generation binding and could overwrite
  same-revision restored terms after a restore.
- P2: a lower restored fund-record revision could leave the old budget displayed.

The primary assistant also identified introduced exact-equity equality gates
that would reject ordinary price-driven mark changes, and editable controls
during a fund save that could strand later edits on stale revisions. All six
scenarios were corrected in `97c6cf2` before the browser cycle. Targeted review
confirmed five fixes but identified a remaining cross-restore save race before
the browser notices the new generation. `2a8109e` adds the original draft's store
generation to the save contract and checks it under the service maintenance lock
before mutation, including an in-flight request delayed across a restore.
Reviewer claims remain static source evidence, not observed broker execution.

The final targeted verifier confirmed the server generation guard and shared
maintenance lock at `2a8109e`. It also raised an old-budget retention candidate.
The primary assistant checked the complete call path and did not accept that
candidate: `readState()` calls `generationChanged()` before adopting the new
state; that handler explicitly clears `investorRecord.fund_plans` and the SPY
schedule. `refreshData()` therefore accepts the lower restored fund revision
because the old contract is absent. Dirty old drafts remain visibly conflicted.
No additional code change or test round was justified for that refuted candidate.

Primary source decision: accept implementation at `2a8109e` for the authorized
real development-browser verification, with no remaining confirmed source-review
finding. This is not UI acceptance or broker-execution sign-off. Code delta from
`b906008`: 377 added / 68 removed lines across five Python files and `app.js`;
no test file changed and no automated test ran.

### Source validation and delivery limits

Python AST parsing passed for `fund_plans.py`, `nautilus_worker.py`, `recovery.py`,
`service.py` and `spy_rebalance.py`. `node --check` passed for `static/app.js`;
Git whitespace checks passed. No automated test was created, changed or run.
Impeccable context, Operate guidance and craft floor were used. Its detector
reported only an advisory for pre-existing `#4dabf7` at line 2371, outside the
changed UI; no palette drift repair was added to this task.

The browser cycle is authorized but has not started. The development Tauri host
must restart its Python service to load backend changes; no alternate Python
launcher, process kill, production start or package installation was used.
No authored reserve amount, approval, submission, cancellation or transfer was
made by this work. Inputs remain unknown until the operator supplies them.

### Verification matrix

| Path | Required evidence | Current result |
| --- | --- | --- |
| Saved plan identity/revisions | Strict account, generation and optimistic concurrency checks | Source reviewed; runtime save not exercised |
| Blank versus explicit zero | Nullable contract; no invented values | Source reviewed; browser pending |
| Reserve overlap and weight units | Decimal max floor; fractional weights to percentage points | Source reviewed, not an executed calculation test |
| Changed plan or policy | Old preview/run blocked; auto re-enable explicit | Source reviewed; runtime mutation not exercised |
| Post-fill continuation | Observation begun after fill and expected holdings | Source reviewed; no broker execution authorized |
| Backup/restore | New record validation; standing and active authority invalidated | Source reviewed; no restore authorized or executed |
| Empty paper account | Real observed equity/cash and honest empty gain/loss state | Pending browser cycle |
| Populated gain/loss and SELL preparation | Actual retained holdings and existing unsaved ticket route | Requires real holdings; no fabricated position permitted |
| Benchmark | Existing qualified price-only comparison remains labeled | Source preserved; rendered comparison not verified |
| Runtime integration | Restarted dev service loads new API contract | Pending dev restart and one browser cycle; no production change |

Use Impeccable in Operate mode for UI implementation and review. Preserve the
established workstation and current workflows. No automated tests, mocks,
benchmarks or unrelated research runs. Static checks and an affected real
browser verification batch are the validation path; no broker action is part of
that batch. Record reviewed revision, actual findings and unverified paths here.
