# Development startup and SPY rebalance UAT

Status: development startup, the loaded SPY entry surface, the fund-plan
disclosure, one nontrading Preview and its filter/clear behavior are observed.
The parent recovered a visible built-in browser at 2112 × 1284 for entry
evidence; the later Edge journey used a narrower window. Focus retention
through polling remains unverified.
No SPY behavior change or broker action has been made by this worker.

## Scope

User requested development startup, real SPY rebalance UAT and the Printer
product rebrand. This record owns startup and the SPY observations. Branding
and SPY source work have separate coordinated owners. Production remains
untouched.

## Startup observed on 8 November 2026

- No development-port listener was reported by the successful initial listener
  enumeration.
- Ran the supported `Start-TradingDesk-Dev.cmd` from `D:\src\TradingAgents`.
  Its Tauri development invocation used `src-tauri/tauri.dev.conf.json`, whose
  identifier and app-directory override select the isolated development app.
- The launcher completed its debug compilation and ran
  `desktop/src-tauri/target/debug/tradingagents-desktop.exe`. Targeted process
  metadata confirmed that exact executable, rather than the installed app.
- The normal session-safe API helper with `--dev` reached port 8099. Health
  reported a running service, connected Nautilus 1.231.0, the IEX feed,
  reconciliation without listed gaps and no startup errors. A reported cache
  path was inside the development profile.
- These bounded startup observations do not establish execution acceptance or
  installed-production health.

## Initial public state, not rendered acceptance

The SPY DOM snapshot showed a verified paper identity, an empty observed account,
no open orders, no saved account fund plan, a sizing budget and cash floor,
automatic trading off, Preview needed and disabled Submit. Health reported 503
configured instruments and no complete retained history coverage. This is enough
to attempt the real rebalance Preview once the browser is visible. The worker
has not activated Preview or saved a fund plan. Parent interaction attempts
below have not yet established successful click delivery.

## Built-in-browser limitation

The available integration is `agent-browser` attached to Factory's existing
embedded CDP transport, preserving the assigned browser session. Opening
`http://127.0.0.1:8099/` returned a real SPY accessibility snapshot.

It did not establish a visible page:

- The page reported `innerWidth` and `innerHeight` as zero.
- A 1920 × 1080 override was rejected because the Factory pane controls sizing.
- Screenshot capture returned: "This browser tab is not visible to the user, so
  it cannot be captured."

The parent subsequently opened its own dev tab and explicitly handed
its exact target to this worker. Deliberate selection succeeded and returned
`Printer · Paper trading`, but the worker still observed a zero-size viewport
and the same screenshot refusal. No screenshot or visual pass by this worker
is claimed.

A separate or headless browser is not a substitute for the user's explicit
request to watch the built-in browser. The worker returned browser operation
ownership to the parent with the bounded SPY observation steps below. Subsequent
rendered evidence must be attributed to the parent, not presented as independently
observed here. This is a browser-integration limitation, not a SPY product defect.

### Parent visibility recovery

The parent reported a successful deliberate reopen: screenshot capture worked,
the page was visible, and the actual viewport was 1018 × 1235. This supersedes
the earlier parent visibility blockage, not the worker's failed capture.
The initial screenshot showed loading and is not counted as a product pass.
A subsequent full snapshot showed loaded SPY, a reconciled empty paper account,
Preview enabled, Submit disabled and no saved fund plan.

The parent retains sole browser-operation ownership. Functional observations at
that viewport can establish the specific controls and outcomes exercised, but
cannot establish the supported 1920 × 1080 desktop layout.

### Supported-size entry evidence

After the user remediated pane visibility, the parent reported a visible
2112 × 1284 viewport and captured the loaded SPY page. The worker reviewed that
parent-supplied screenshot locally. Printer branding, the account strip, the
reserve/budget and rebalance columns, and the separate automatic-trading section
were visible without obvious horizontal clipping.

The screenshot and parent snapshot showed no saved fund plan, a cash-floor-only
budget/reserve, source dates not loaded before Preview, Preview enabled, Submit
disabled and automatic trading off. This is supported-size entry-state evidence,
not rebalance-result, editing, expiry or broker acceptance.

A later parent command unexpectedly found a blank page. That is recorded as a
browser-pane/session lifecycle issue, not attributed to the application. The
parent is investigating a controlled same-session sequence. No hidden or
alternative browser is being used.

The parent then reported two disclosure clicks and one Preview click returning
Done while the editor stayed collapsed and the page stayed Preview needed.
Screenshot capture immediately after the Preview attempt again reported a
hidden tab. Those responses do not prove that the application received a click
or dispatched Preview. No real preview outcome, disclosure defect or other
product failure is inferred. The parent is attempting deliberate selection of
the existing tab without reloading.

The startup source hashes predate the coordinated backend changes. Subsequent
acceptance must compare loaded desk/native source hashes with the delivered
revision before attributing outcomes to those changes.

### Post-activation editor observation

The parent regained the visible main Browser pane and deliberately reacquired
the actual development tab. Screenshot capture succeeded at 2112 × 1284.
The native click on `#fund-plan-editor-toggle` opened `#fund-plan-editor`;
immediate observation showed open and `aria-expanded` true, focus on the
summary, the expected hit target and the real fund-plan fields. Save was
disabled. This passes that specific editor-disclosure interaction. It does
not establish editing, draft persistence or saving, and no disclosure defect
is claimed.

The next command returned `tab_gone` before any field focus/input operation.
No focus-through-polling or Preview result was observed. The parent deferred
the final interaction cycle until the concurrent packaging work completes,
then will reacquire the visible page. This is a transport/session boundary,
not evidence that the application rejected a field action.

## Pending real observation

- Preview result or its exact blocking message and account/budget readiness.
- Fund-plan field editing and focus retention through normal polling, without
  saving invented financial terms.
- Actual planned-share precision, table count and source dates.
- Natural expiry if reached during the work, and natural connection changes
  only if they occur. Do not induce a reconnect.
- Rebrand beyond the observed entry surface and coordinated-fix verification at
  the supported visible desktop size.

## Single backend reload prepared, not executed

After the coordinated source batch is frozen and independently reviewed, record
its revision and the raw SHA-256 of `service.py`, `spy_rebalance.py` and
`nautilus_worker.py`. Immediately before activation, confirm the development
account is paper, automatic authority is off, no manual rebalance is active and
no working, pending or unknown command/order exists.

The supported action is the existing Windows tray's **Printer Development →
Restart** (older hosts may show **TradingAgents Development**). The development
identifier selects port 8099. The supervisor stops only its owned backend job
and then starts the same development source/profile. Do not launch another host,
kill processes by name, add a restart endpoint or touch production.

The available built-in browser cannot operate the Windows tray. An authorized
read-only check subsequently confirmed that the existing Windows UI Automation
assemblies are usable and expose one enabled, onscreen **Printer Development**
button with InvokePattern. No native UI action was invoked during discovery.

After the source freeze/review and public preflight, the proposed automation is
to invoke that exact development tray button, then require the resulting Restart
menu item to belong to the confirmed development host process/path before
invoking it. The tray button's UI-host process is not assumed to be the app
process. Missing or ambiguous menu ownership stops activation; no generic
Restart, process-name termination or alternative launcher is a fallback.
The native menu has not yet been opened, so its automation remains unverified.

After one supported restart, use the normal `--dev` API helper and public health
to compare all three `source_sha256` values and `native_source_sha256` with the
reviewed files. Verify fresh paper reconciliation, no startup errors, unchanged
saved policy/floor, inactive automatic/manual execution and no new commands or
orders. Confirm a new native/server session from public state where exposed.
The parent owns the visible browser reload and fresh session-only Preview;
Submit remains prohibited.

The source owner delivered final-fill account/holdings guards, a preview binding
to the captured native session and request-start expiry. Independent source
review approved the frozen source committed at
`ffe0fccd4fd25f5cff822fe3d5f18893532bbbd0`. A nontrading Preview journey cannot
establish the final-fill broker path.

### Actual preflight and activation attempt

After the activation signal, the worker confirmed that exact committed revision
and read only the development public health, portfolio, commands and investor
projections. The service was connected to the official paper endpoint and
reconciled without listed gaps. Positions, orders, commands and approvals were
empty; automatic authority was off, no manual run was active, and the saved
policy retained its enabled cash floor.

Before any native restart, public health already matched the final reviewed
source bytes, consistent with the Tauri watcher restarting during the earlier
branding edits:

| File / public startup field | Matching SHA-256 |
| --- | --- |
| `service.py` | `f360df19dde119234578f55216e2ffd1317b7e3ae463aeb9e4eaeb90180c3642` |
| `spy_rebalance.py` | `ac0bb680c0ccd95df6461dd8228247e2d4b9ca42511b5134d690466a1ea0b9c4` |
| `nautilus_worker.py`, including native startup | `81052a10d19700516b8ac2e9f1a077ef1872b2b526947dafb81fcc61fc633e76` |

The development application identity matched the initial dev read, and targeted
process metadata again confirmed the expected debug executable. No private
configuration, native credential store or credential-presence flag was read.

The unique visible **Printer Development** tray button was invoked using its
native UI Automation InvokePattern. The resulting tree exposed no MenuItems
owned by the confirmed development app process. Restart ownership therefore
could not be proven, so **Restart was not invoked**. No generic action, process
termination, duplicate launcher or browser command was used.

This is a native-menu automation limit, not a backend defect. The final source
hashes provide observed loaded-revision evidence. The primary accepted automatic
Tauri watcher activation of the final source as sufficient and declined an
unnecessary additional restart or operator request. An explicit tray restart
and the real Preview journey have not been claimed.

### Fresh post-build readiness

After the coordinated builder stopped, a fresh set of read-only development
public requests at approximately 14:05 PST on 8 November confirmed:

- Printer running, Nautilus connected to the official paper endpoint and the
  same development application identity.
- Account observation at 14:04:38 PST and runtime heartbeat at 14:05:03 PST.
- Reconciled status, no listed gaps, zero positions/orders and no startup or
  configuration error.
- Automatic authority off, `in_progress` false and `run` null.
- Zero commands, approvals and option instructions; recovery not required.
- All reviewed desk/native hashes above still match exactly. The native epoch
  is unchanged from the activation preflight.

No restart, native UI or browser action accompanied these reads. They establish
readiness for the parent's final visible nontrading UAT cycle, not its outcome.

The builder separately reported a produced Printer installer followed by a
nonzero exit at updater signing because no signing key was supplied. No signing
credential was inspected and no production installation occurred in this work.
Full packaging evidence belongs to the branding delivery record; artifact
production is not signed-release acceptance.

No tests, mocks, synthetic data, research rerun, production operation,
credential/private-configuration inspection, order approval, submission,
cancel/replace, or trading-authority change has been performed.

## Visible Edge preview and filter, 8 November 2026

The replacement UAT owner used the user's offered Edge window after the
orchestrator authorized that specific browser. Native UI Automation checked the
exact document title and compared its address in memory to the isolated
`127.0.0.1:8099` development page before each action. The window was onscreen;
its outer bounds were approximately 1734 × 1399, so this observation does not
establish supported 1920 × 1080 layout acceptance. Existing browser tabs,
favorites, settings and credentials were not operated.

The session-safe development health read returned Printer, connected to the
paper endpoint, reconciled, with no startup errors. All three source hashes and
the native hash matched the reviewed revision listed above. No restart was
needed. The visible entry showed verified paper, zero positions and open
orders, automatic trading off, a $95,000 sizing budget and a $5,000 cash
reserve. Submit was disabled.

The fund-plan disclosure opened and remained expanded while its account
observation naturally advanced from 2:28:47 to 2:29:18 PM PST. No terms were
entered or saved. UI Automation could not focus the monthly-withdrawal field:
the exposed element reported nonfocusable and `SetFocus` failed. A subsequent
native mouse attempt verified the field's hit target, but Windows denied
foreground activation before a click occurred. This does not prove a product
focus defect or focus retention across polling.

Exactly one real Preview was invoked. The result showed State Street SPY
weights dated 2026-11-05, a price check on Nov 8 at 2:29:51 PM PST, 503 stocks
and 503 planned trades, and 94.90% target stock exposure. The first row was
BUY 21.966418766 AAPL, with a $342.41 estimated limit. The result explicitly
showed **Trading Rules block submission**, with Submit disabled. The expanded
blocker read:

> Maximum open-session quote age / seconds: Broker regular-session state and
> investor-selected open/closed age tolerances Affected stocks: 503 (AAPL,
> NVDA, MSFT, AMZN, GOOGL, …).

The header showed Market closed. The visible blocker did not expose an
individual symbol's quote timestamp or a more specific per-symbol reason; the
displayed price-check time is not asserted to be a quote timestamp. Whether
the rule outcome is expected remains under source investigation.

Filtering by the actual first row, AAPL, showed **1 of 503 planned trades** and
the same share quantity. Clear filter restored **503 of 503 planned trades**.
No retry, refresh, fabricated plan, order approval, submission, cancellation
or automatic-authority change occurred. Natural expiry and broker execution
remain unobserved; the retained preview is not proof of fill or broker
acceptance.

An initial separate Edge launch carried a fresh temporary-profile argument but
its debugging-port ownership could not be established. A literal-port browser
capture unexpectedly showed an unrelated login page, not Printer. No input was
entered there and it was not used for UAT. Its profile and window were not
deleted or modified. The later scoped native UIA observation above is the
actual Printer evidence.

### Closed-session wording correction and reload attempt

After the first Preview, targeted read-only policy fields showed
`session_freshness` enabled, open and closed age limits both 180 seconds, and
`regular_session_required`. The rule's source requires an open market for that
choice; it does not establish the age of every affected symbol's quote. A later
separate AAPL context read reported last-trade event
`2026-11-06T20:59:57.566180+00:00`, closed session and stale status under the
180-second limit. That later read is not evidence of the first Preview's
captured event timestamp or of all 503 symbols being stale.

The correction was independently reviewed and committed at
`c3abd0bbf51fe703dbe118802242761ba6c1e119`. After the app-only build, a fresh
development preflight confirmed the exact debug host executable, running paper
connection, reconciled account, no startup errors, automatic authority off,
no active run, no commands or approvals and no observed broker order actions.
The single onscreen `Printer Development` tray button was identified, but
`TryGetClickablePoint` returned false and its center hit-test resolved a pane,
not the button. The attempt stopped before a mouse click or Restart. No popup
was opened and no Preview was retried. The corrected label and reason have not
yet been observed in the running backend or Edge; final recheck remains pending.

The user subsequently prohibited tray restart and authorized the specific
`Start-TradingDesk-Dev.lnk` desktop shortcut. Before invoking it, the owner
confirmed exactly one matching debug host, PID 31664, and repeated the paper,
reconciliation, inactive run and empty order/command/approval preflight.
The shortcut was launched once through Windows Shell. Two subsequent public
state reads still showed PID 31664 and the old
`Maximum open-session quote age / seconds` label, with the paper service
connected. The shortcut's metadata identified PowerShell and referenced the
exact development host and launcher, but did not establish that its restart
action completed. No duplicate shortcut launch or second Preview was attempted.
The corrected reason remains unobserved. A later bounded observation still
showed the same sole debug host and old label. The launch did not retain a PID
in the initiating command; no new PowerShell process matching the shortcut's
development-host and launcher signatures could be identified, so no console
error was attributed to it.

The orchestrator then authorized one observable invocation of the same
shortcut target and arguments. A new safe preflight again showed one exact
debug host, PID 31664, reconciled paper, automatic authority off, no active
SPY run, and no observed broker orders, commands or approvals. The shortcut
target launched as PowerShell PID 32176. The original debug host did not exit
within a bounded 15-second wait, and the launched PowerShell had exited by
inspection; its exit code and console error were unavailable. The service
remained connected and reconciled with the old label. No further launch or
Preview was attempted; activation and the corrected visible result remain
unverified.

After another unchanged safe preflight, one explicitly authorized Windows
Shell `ShellExecute` call opened the exact shortcut. The COM call returned, but
the original PID 31664 did not exit within 15 seconds and remained the sole
matching debug host; the live label was still unchanged. No new matching
shortcut PowerShell process or attributable console error was identified.
There was no further launch, tray action or Preview.

The orchestrator next authorized one retained background invocation of the
same unchanged shortcut target and arguments. Its supervisor started as PID
31124. The original debug host PID 31664 exited and a single replacement debug
host PID 24472 appeared. Initial and subsequent development API reads returned
connection errors, so readiness, the corrected live label and the affected
Preview are not yet established. No additional launcher action, tray action or
Preview was taken.

The retained supervisor's scoped output showed only that it started the
shortcut target and was waiting. The replacement host still matched the debug
executable but had no direct child at the time of inspection; its own
UI Automation windows exposed no error text. A later public health read still
returned a connection error. No specific startup cause or corrected running
state is established.

The source owner subsequently reported a `WriterBusy` development application
lock error in PID 24472's startup log. The lock owner had not yet been
identified; this does not establish a stale lock file or authorize its removal.

The development service later became healthy; the recovery trigger was not
established. A fresh public preflight showed Printer running, connected and
reconciled to paper, no startup errors, automatic authority off, no active SPY
run, no observed broker orders,
commands or approvals, and the live label **Quote freshness and session
permission**. This establishes the new live label, not the rendered blocker.

The previously verified Edge window PID 26760 no longer existed. Narrow
visible-window checks found no Printer-titled Edge document at port 8099. One
new headed Edge window was then launched with a fresh isolated-profile
argument under a retained supervisor. Although its browser process carried
that argument, its visible window reported a Personal profile and did not
identify the local Printer page. Because profile and page identity were
uncertain, the owner stopped without clicking, navigating, reading other tabs,
capturing a screenshot or invoking Preview. The corrected closed-session
reason remains unverified in the rendered application.

### Post-fix API Preview

After the transient `WriterBusy` condition, the development service was again
running and reconciled to paper. The lock owner and recovery trigger remain
unknown. A fresh preflight showed automatic authority off, no active SPY run,
and no observed broker orders, commands or approvals.

One real Preview was then requested through the normal session-safe local API.
The result reported policy revision 6, weights dated **2026-11-05**, price
check **2026-11-08T23:02:07.123732Z**, 503 stocks and 503 planned trades,
and target stock exposure **94.9019818500%**. Its first buy estimate was
**BUY 21.966418766 AAPL, limit $342.41**. The response contained no submission
token and reported:

> Quote freshness and session permission: The regular market session is
> closed. This rule requires it to be open. Affected stocks: 503 (AAPL, NVDA,
> MSFT, AMZN, GOOGL, …).

This is actual backend response evidence, not rendered Edge acceptance or
proof of a disabled Submit button. No per-symbol event age is inferred from
the price-check timestamp. A post-Preview read again showed automatic authority
off, no active run, and no observed broker orders, commands or approvals.
No trade, approval, submission or cancellation occurred.
