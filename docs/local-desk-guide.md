# Local TradingAgents desk: launch, use and handoff

Current installation documented on 20 October 2026. Start from the
[README](../README.md); agents must also read [AGENTS.md](../AGENTS.md).

## What we built

The browser app combines a configurable stock universe, Alpaca account and price
observations, saved TradingAgents research, local order proposals and baskets,
and a decision journal. NautilusTrader is the trading engine. Its adapter talks
to Alpaca paper trading. Research is advisory; approving exact order terms and
submitting them are separate actions.

The current installation uses Nautilus 1.231.0 with its in-memory cache and SQLite
for application records. Redis and LEAN are not required. The 503-symbol S&P 500
universe is saved configuration, not a hardcoded stock list. Settings accepts up
to 1,000 symbols, including CSV/text imports.

## Launch the existing installation

1. Open `C:\src\TradingAgents\Start-TradingDesk.cmd`, or run:

   ```powershell
   rtk proxy C:\src\TradingAgents\.venv\Scripts\python.exe C:\src\TradingAgents\Launch-TradingDesk.py
   ```

2. Open <http://127.0.0.1:8098>. The launcher reuses a matching running service
   or starts it with the configured data directories. It does not install
   packages, migrate records or stop another service occupying the port.
3. Expand **Nautilus connection**. If stopped, choose **Start Nautilus**. Wait for
   connected account status and prices before relying on current observations.
4. Confirm the account is paper, check cash/equity/buying power, and inspect
   missing prices and timestamps. A refreshed account does not mean a new market
   price event, particularly while the market is closed.

This is an existing-installation procedure, not a clean-machine installer.
A Git clone alone lacks the local data, environments and credentials.
Do not run `python -m tradingagents.web.server` without explicit configuration:
its default port and data location differ from this installation.

**Stop Nautilus** disconnects the engine; the web app and saved research remain
available. Closing the browser does not stop the web server. Stop only the
identified local app processes when maintenance requires taking it offline.

## Where things live

`tradingdesk.launch.json` is the authority for this machine's configuration.
It is ignored by Git and contains paths, not credential values.

| Item | Current location / purpose |
| --- | --- |
| App code and launcher | `C:\src\TradingAgents` |
| Web app Python | `.venv\Scripts\python.exe` under the checkout |
| Nautilus Python | `.venv-nautilus-v1\Scripts\python.exe` under the checkout |
| Application data | `.local-workspace\evidence\runtime-staging\20261017T024233Z-e3f9548d\application` |
| Saved history | Same staging folder, sibling `history` directory |
| Credential file | `C:\src\printer\apps\tradingagents\.env`, existing `ACPA_*` keys; never publish values |
| Launcher logs | `.runtime-stage\launcher.out.log` and `launcher.err.log` |
| Preserved local evidence and backups | `.local-workspace` and existing repository-local backup folders |

The application, history and native Python moved out of `C:\src\printerv2`.
Old paths inside dated evidence remain provenance, not launch instructions.
The old directory was empty but locked during migration. Python base runtimes
remain installed under the user's Windows/uv directories. Credentials remain
in `C:\src\printer`, which is a different folder from `printerv2`.
The separate dependency smoke audit must be consulted before claiming every
auxiliary environment launcher has been cleaned of old references.

Preserve these local files when moving the checkout. Do not replace them with
fresh data or commit databases, credentials, environment files or backup archives.

## Everyday workflow

| Page | How to use it |
| --- | --- |
| Portfolio overview | Check account balances and holdings; scan the universe using search, filters, sorting and columns. Select stocks to organize watchlists. Open a stock's market evidence and available charts before relying on an agent recommendation. |
| Agent research | Choose an existing run and stock. Read the reports, debate and final decision; inspect source dates and failures. Record human review disposition and priority. Saved reports do not become current research merely because today's price changed. |
| Orders and drafts | Create or review a local proposal or basket. Check symbol, side, quantity, order type, limit price when applicable and time in force. Read readiness reasons. Approve exact terms, then separately Submit only when intentionally placing an order. |
| Settings | Edit the named universe or import a Symbol/Ticker CSV or text list, review and save. Model/provider changes apply to future research. Connected-service status identifies the account and price feed. |
| Decision journal | Inspect saved decisions, research links, proposals and baskets. Record follow-up notes and export selected records. Reporting uses available records and configured periods; absent data is not fabricated performance. |

The research provider can use the existing Codex ChatGPT sign-in (`chatgpt`).
Maenifold's configured default endpoint is `http://localhost:8080/mcp`; it serves
research integration, not the Nautilus engine. New research can require that
service and provider authentication. No new research was run in the latest UAT.

**No approved order** means there is no currently approved proposal; it does not
mean the account is globally disabled. **Pause new orders** is an explicit
operator choice and does not cancel working orders. Cancel and Replace are
broker actions, not harmless smoke-test buttons. Unknown fees remain unknown.

## Read-only smoke test

Open all five pages in the actual browser. Confirm connected Nautilus/account
status, price coverage for the saved universe, readable saved research, visible
order readiness, persisted settings and journal entries. Capture results and
errors. Do not approve, submit, cancel, replace, launch research or restore a
backup during this smoke test. Backup preview is different from applying restore.

The 20 October post-move browser check showed $100,000 cash/equity/buying power,
zero positions/open orders, 503 priced stocks and ten saved research runs. These
are dated observations, not constants the application should enforce.

## Acceptance evidence

- [Corrected product roadmap](tradingagents-build-roadmap.md): requirement reference,
  subject to subsequent explicit user corrections and feature freeze.
- [19 October UAT index](uat/2026-10-19/README.md): committed plan, case ledger,
  report and independent review. Result: 41 pass, 2 partial, 6 not exercised.
- [20 October expanded report](../.local-workspace/evidence/expanded-uat-20261020/report.md),
  [69-case ledger](../.local-workspace/evidence/expanded-uat-20261020/final-ledger.md),
  [independent sign-off](../.local-workspace/evidence/expanded-uat-20261020/independent-signoff.md).
  These links resolve in this local checkout; the evidence is not committed.
- [Relocation report](../.local-workspace/evidence/migration-20261020/report.md)
  and [post-move browser capture](../.local-workspace/evidence/migration-20261020/smoke-overview.png).

Expanded UAT passed 58 permitted cases: account/universe views, watchlists,
sorting/filtering, charts and cached evidence, saved research, local proposals
and baskets, validation, review choices, alerts, journal/export, settings/import
drafts, backup preview, and engine stop/start. Five cases lacked data and six
were reserved. Actual approval/submission, broker cancel/replace, fills and
populated-account behavior are not certified. Neither are new research,
destructive restore or the unavailable supplementary datasets. Do not describe
this as completed trading-execution UAT.

## If startup or data looks wrong

- Check `tradingdesk.launch.json` and that its four paths exist. Preserve the
  configured application/history pair; do not point at a convenient empty folder.
- Read `.runtime-stage\launcher.err.log` for launcher startup failures. The
  migration-started instance used `migration.err.log` in the same directory.
- If the port belongs to another instance, inspect its identity before changing
  or stopping anything. The launcher deliberately does not take it over.
- If the app opens but balances are unavailable, inspect Nautilus connection
  status and start the engine if stopped. Read the reported error if connection
  fails; do not invent balances or weaken order approval.
- Treat dated prices, missing data and unavailable fees according to their UI
  labels. Use saved evidence for existing research; do not silently start a run.
