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
