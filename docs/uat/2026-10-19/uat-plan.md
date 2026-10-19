# Remaining UAT completion — 19 October 2026

Goal: finish every remaining feasible acceptance check without trades or new research, resolve browser access, preserve feature freeze, and obtain independent sign-off. No feature disable switches, new prerequisites, installations or automated test files. Surgical fixes only for demonstrated failures. Complete any fix batch before verification of that batch.

Baseline: ../uat-remediation-20261018/uat-report.md (36 passed, 5 partial, 8 not exercised). Requirements: ../tradingagents-build-roadmap.md, with its current user corrections overriding historical assessment. Prior outcome: memory://thinking/sequential/2026/10/18/session-1792356103370-49563.

## Work batch

| Cases | Work and evidence | Restrictions |
|---|---|---|
| Browser / runtime | Diagnose unreachable tab, start existing saved application, load actual browser and connect Nautilus; observe current account and prices | No security-policy bypass, endpoint changes or broker writes |
| U14 | Compare saved claims with dated input artifacts; inspect explicit unsupported claims | No research or new source collection |
| U18 | Filtered-list return, selected run/report/date, unsaved note and table scroll during refresh | Browser text highlighting is not an added acceptance prerequisite |
| U38 | Actual desktop keyboard workflow, focus, labels and smaller supported layout | No exhaustive device/certification project |
| U08/U13 | Finish unexercised Merge import branch and inspect chart hover if existing UI supports it | Restore baseline index/preferences; no research |
| U27/U32/U41/U44/U45 | Independently reconcile retained legitimate populated/event/accounting evidence where available; run existing isolated checks only | Label recorded/offline evidence; do not claim current populated-account UAT or manufacture broker state |
| U42/U43/U47 | Inspect existing workflow and evidence; document exact boundary to human-operated paper cycle | No agent per-order approval, Submit, Cancel, Replace or new research; no disabling capability |
| U46 | Restore validated backup into a separate temporary application copy and compare records | Never restore active workspace or connect isolated copy to broker |
| U48 | Inspect and exercise existing local request protection and credential permission checks when safe and isolated | No attacks on external services; no security-setting changes |
| Closeout | Current source/runtime comparison, retained test-record inventory, no unintended active changes, independent review | Do not translate old passes or source inspection into fresh UI passes |

Root owns browser actions and final report. Separate workers own isolated restore/security and retained evidence work. Independent reviewer evaluates completed evidence and any surgical diffs. Report a case by evidence type and branch coverage; unavailable broker/simulator events are not fabricated or quietly passed. Optional benchmark, expiry and investor limits remain optional.

## Browser diagnosis

The existing tab inventory showed a connection-refused error page at a data: URL. That explains the earlier protocol-policy rejection. Local process/port inspection found no TradingAgents server or Nautilus worker and no listener on8098. The remedy is restart of the existing application using tradingdesk.launch.json, then ordinary access to its permitted HTTP page. No browser safety setting is changed and the blocked data: error page is not accessed.
