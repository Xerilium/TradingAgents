# Bounded SPY refresh and progress wakeups

## Scope

User-directed implementation over924e204: refresh existing native inputs before
next-leg LIMIT derivation, coalesce authoritative full-fill account refresh and
wake the existing single-step executor. No parallel orders, new feed, threshold,
policy, broker authority or dependency. No performance/completion-time claim.

## Implementation

- SpyRebalance.advance requests existing native refresh outside maintenance for
  a ready next leg. Afterwards the same locked block rereads durable run revision
  and rechecks current authority, account/session, policy, fund binding, expected
  holdings and cash before deriving terms and unchanged admission/transport.
- Once for the current authoritative filled command, refresh requests a forced
  account fetch under the existing native observation lock (avoiding only its
  two-second duplicate suppression). Existing post-fill-start/quantity/receipt/
  exact-holdings reconciliation gates remain. A partial or unknown command never
  authorizes progress.
- Existing runtime observers wake on durable run/command/account progress. A
  maintenance-serialized tick admits only one future; pending wakeups coalesce
  until that future completes. The normal timer remains fallback. Callbacks
  schedule work, never perform broker dispatch or wait for native reads.
- Transient native refresh transport failures return an explicit error reply;
  SPY sends nothing and leaves progress for the normal fallback timer. Strict
  account/reconciliation checks run after refresh, not before the read that can
  restore a pending post-fill observation.
- Existing data refresh duplicate throttle and rate-limit cooldown are retained;
  capture success is not a fresh exchange event. Applied quote/spread rules and
  per-order freshness/approval checks remain authoritative.
- Health records startup SHA256 for the three source files; native runtime reports
  its own startup worker hash. These contain source hashes, not config/secrets.

## Verification and activation

AST parsing and whitespace checks pass for the three changed Python modules.
Independent scoped review found early strict reconciliation admission could block
its own repair read and transient native read failures could stall then block.
Corrected: pre-refresh identity mismatches skip, strict checks remain after the
read; native refresh returns explicit transport errors and SPY waits for fallback
without dispatching. Corrected source review found no significant issues (static
only). A possible recovery-clear observer race still fails closed for review.

Reviewed SHA256:
- service.py: `2c1ae26df3ce5e6407fad73b149f223e4dd2b91eeb678d433265f05142d109e1`
- spy_rebalance.py: `1a9c5459fb3e3d1b6f94162a4accf48758a6d900c1f0eddcd07afed6ed0ed020`
- nautilus_worker.py: `1d2e32d5e177c73f3977eddd5348dc835251da3991aefecb1733dc2026b5baa0`

Activation has not occurred: the current native session remains the old source,
health has no startup hashes yet. The supported native tray action is required. No automated tests, mock transports, synthetic events or
broker actions were authorized/performed. Actual fill-driven execution remains
unverified without separately authorized real orders and native/broker receipts.

Read-only dev preflights12:08 and12:12PST on6November2026: verified USD paper
account15d9,100000 cash/equity, no commands/approvals/open orders/positions/manual
run, autooff, policy revision1 cash floor5%, reconciliation clear. Recheck
immediately before restart; new activity blocks activation.

Supported activation is only **TradingAgents Development → Restart** in the
existing Windows tray. No restart API/CLI exists. Debug dev reloads desk Python
and native worker from checkout, without rebuilding host or changing production.
Do not relaunch the dev command while running. Browser automation cannot operate
the Windows tray; the exact native tray action is a human/operator activation
blocker, not permission to add a restart endpoint or terminate arbitrary processes.

After activation compare startup source hashes with committed bytes; verify a new
server/native session, fresh paper identity/reconciliation, floor/policy, autooff
and no orders. Old session-only preview must be regenerated after normal browser
reload; changed native binding rejects old approvals/previews.
