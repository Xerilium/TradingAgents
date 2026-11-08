# Development startup and SPY rebalance UAT

Status: development startup and the loaded SPY entry surface are observed.
The parent recovered a visible built-in browser at 2112 × 1284, superseding the
initial narrow-viewport limitation. Rebalance interactions are still pending.
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

The source owner reports final-fill account/holdings guards, a preview binding to
the captured native session and request-start expiry. Independent source review
and activation evidence are still pending. A nontrading Preview journey cannot
establish the final-fill broker path.

No tests, mocks, synthetic data, research rerun, production operation,
credential/private-configuration inspection, order approval, submission,
cancel/replace, or trading-authority change has been performed.
