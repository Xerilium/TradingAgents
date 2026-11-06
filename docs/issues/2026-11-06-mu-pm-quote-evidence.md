# Bounded MU and PM stock-snapshot evidence

## Observed diagnostic gap

MU/PM normalized quotes were null while a latestTrade remained available. Public
stock state did not retain raw provider fields or mapping rejection reason, so
absent/one-sided/crossed provider input could not be distinguished from native
mapping rejection. PM event timestamps advanced despite an unchanged price;
public/native timestamps matched in the read sample. No causative data defect
was established. Human requested the minimum evidence prerequisite, not relaxed
quote rules or fabricated freshness.

## Evidence-only implementation

Existing batched IEX refresh now includes `stock_snapshot_evidence` only for MU
and PM: fixed source/feed, batch response capture time, allowlisted raw trade
`t,p,s,i` and quote `t,bp,ap,bs,as`, normalization status/stage/error type/reason,
input event and cached event timestamps. Latest in-memory observation replaces
it on refresh; no disk history, full payload, auth header, secret, provider request
or endpoint added. Existing quote acceptance/fallback/policy paths are unchanged.
Malformed diagnostic input/cache reads cannot turn evidence into a new refresh
failure or override an accepted event. Request failures retain existing errors.

## Checks and activation boundary

AST and whitespace checks pass; independent review identified diagnostic capture
outside the old exception boundary and cache diagnostics altering rejection
claims. Both corrected with guarded allowlist and separately caught cache read.
Corrected-source review found no findings at native worker SHA256
`206b4f83174472f2186edefc4c5279e817e951a1901613eff383c0273668243c`. No tests/mocks/events,
quote fetch through a new path, financial/broker actions or restart performed.

Existing running worker cannot expose these new fields until native code reload.
Exact supported activation: **TradingAgents Development → Restart** in the
existing Windows tray. Human/operator must first recheck no working/pending/
unknown commands/orders, no active manual run and autooff; restart not performed
by coding session. Latest read12:41PST6November2026 had zero orders/commands,
runnull, autooff, savedpolicy2 cashfloor5%, oldnative
`468e59a3-7456-4306-91a5-daa086716a69`.

After separately confirmed activation, compare actual MU/PM raw fields and
capture/event times to native mapping/cache evidence on one normal existing
refresh. Fix only a demonstrated defect; if provider input is missing/invalid/
stale, attribute exact fields and stop. No root-cause or successful correction
claim until that real evidence exists.

## Real capture and demonstrated MU defect

Human confirmed Development restart. At12:44:03PST the loaded worker hash exactly
matched reviewed206b4f…243c, newnative
`c12c2a9b-732e-4f7c-8d1c-7de10e1b1ff6`; paper15d9/reconciled,policy2floor5%,
spread25age60/freshness60regular,autooff,zeroorders/commands/approvals/run.

One actual existing refresh captured at12:43:36.934130PST from Alpaca IEX:
MU raw bid690/ask690.39,size10/20,event12:43:35.456255926. Provider values were
positive/noncrossed, but native tick construction raised ValueError and no quote
was published. Exact real-field replay through installed Nautilus1.231.0 returned
`bid_price.precision`0 not equal to `ask_price.precision`2. This confirms a desk
normalization defect, not provider-absent MU quote in this sample.

Surgical fix reuses existing option mapping pattern: losslessly pad both stock
prices to their maximum input precision before QuoteTick construction. Captured
MU replay then returned690.00/690.39,size10/20 with exact decimal values preserved.
No price rounding, fabricated quote, freshness change or policy relaxation.
Diagnostic cache lookup uses the constructed tick's instrument identity; a null
immediate cache result still is not proof cache application failed asynchronously.

PM in the SAME real capture had valid accepted bid197.95/ask198.05,event
12:43:33.444714411 and trade197.97,event12:43:25.968738357. Its old historical
staleness cannot be reconstructed; this sample shows no PM input-age defect.
Mixed bid/ask decimal precision can affect any stock, including PM when present;
shared correction applies once in the stock mapper. Differing decimal precision
is representation, not a valid reason to reject two numerically valid prices.

Independent scoped correction review found no significant issues. AST and
whitespace passed; corrected worker SHA256
`81052a10d19700516b8ac2e9f1a077ef1872b2b526947dafb81fcc61fc633e76`. Fixed worker activation still requires the supported human
Development tray Restart after the same empty-order/autooff precheck. No restart
or broker action performed by coding session. Real post-fix live MU/PM mapping
remains unverified until that activation; exact captured-value native replay is
bounded evidence, not execution acceptance.
