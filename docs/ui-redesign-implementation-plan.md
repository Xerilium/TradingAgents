# Blueprint implementation and acceptance plan

Status: Proposed for review (v2 — rubber-ducked across Sonnet 5.5, Grok 4.7, and GPT-6.1 Sol). Implementation has not started under this plan.

**Fixed scope**

Freeze [the blueprint](ui-redesign-blueprint.md) at commit `3770bbe` (which supersedes the `dfbcd47` sign-off line in §9.1 with the `dietz.estimate`, metric qualification, Options tab, and `.cm-editor` shortcut updates): all 10 workspaces, US-01–US-25, E-01–E-15, and its cross-cutting contracts and exclusions. No backend changes, new APIs, new static files (the `server.py` static allowlist is frozen), unrelated refactoring, restored documents, or policy edits.

Maintain a [[traceability]] table in `docs/issues/2026-10-26-dashboard-layout.md` (the continuing UI delivery record): requirement (`US-01`–`US-25`, `E-01`–`E-15`, `C-8`, `C-9`, `L1`–`L14`, `U1`–`U2`) → file and function → evidence (`observed`, `source-reviewed`, `failed`, `unverified`) → verdict. Audit in both directions: every requirement is covered; every change serves a requirement. Any deviation blocks the affected work. Agents cannot waive requirements or reinterpret omissions as completion.

**Team, file ownership, and implementation sequence**

Work in the primary checkout (`C:\src\TradingAgents`, branch `nautilus`). Maximum **primary + one worker** active.

- **Primary (sole `app.js` and Git owner):** sole editor of `tradingagents/web/static/app.js`, `index.html`, `app.css`, and `DESIGN.md` (superseding any function-level `app.js` split in blueprint §8), and sole owner of all Git operations and final product judgment. Ownership of `app.js` never transfers to a worker.
- **Rotating worker:** edits only explicitly assigned support files from `workflows.js`, `report-format.js`, `lists.js`, `market-chart.js`, `command-controls.js`, `nautilus.js`, and `ui-*.css`. Never simultaneous edits to one file.
- **Per-step handoff contract:** before a worker edits a support file, the primary commits the step's `app.js` markup and records the exact DOM IDs, classes, `data-*` attributes, and globals in the delivery record. Workers perform no independent builds, tests, launches, Git commits, or research, and no worker branch merges.
- Load Impeccable (`Operate` mode) before UI edits. Commit reviewed implementation batches locally with explicit file staging (`git add <paths>`, never `git add -A`) and no abandoned untracked work.

Implement in this strict serial order (each step must pass `node --check` on all `tradingagents/web/static/*.js` files before the next starts):

1. **Foundation:** selection (`selectedSymbol`, current `renderOverview`) versus batch (`selectedSymbols`) and delete (`researchDeleteSelection`) state; pinned ticket identity (`ticketSymbol`, `ticketDirty`); focus/input-preserving rendering; shared `renderTablist()`, `instrumentHeaderStrip(symbol)`, and `stockEvidencePanel(symbol)` (built once here so both Research in Step 3 and Markets in Step 4 mount the same helper); guarded shortcuts (ignoring `INPUT`, `TEXTAREA`, `SELECT`, `BUTTON`, `.cm-editor`, `isContentEditable`, `event.isComposing`, and open `<dialog>`); shell and responsive CSS (`app.css`). Keep legacy layout helpers and their call sites intact, then run a read-only 10-page browser compatibility check before Step 2.
2. **Orders and ticket:** replace `openTicket(symbol)` with the shared `380px` docked drawer (`dockedTicketDrawer`) and update `#orders` (`renderOrders`, `proposalEditor`, `approvalPanel`, `command-controls.js`, `ui-orders.css`) before Steps 3–5 consume it. Bind all ticket quotes, positions, research links, click-to-seed, and `chartPriceControls` / `reviewChartCopy` / `applyChartCopy` guards strictly to `ticketSymbol`. Preserve separate preparation, approval, and submission, every non-rule and 10-rule blocker, and operation-specific recovery (`submit`, `cancel`, `replace`). Delete `layoutOrders()` and `layoutBasketGroups()` in this same commit.
3. **Research and Workflows:** inline batch selection and confirm popover (`analysis_date` replacement notice, `exclude_fred`), unconditional launch focus to the first batch stock, six statuses (`completed`, `incomplete`, `failed`, `cancelled`, `running`, `queued`), report presentation (PM decision & Trader plan above the fold), distinct `social_sentiment` vs. `local_laya_batch` sections, unified `Activity` feed (events + receipts with explicit failure/429 states), `stockEvidencePanel(selectedSymbol)` mount, and workflow `Fit All` (`0.15` floor + pan/scroll fallback), node-click prompt chips, `Ctrl/Cmd+S` in `CodeMirror`, and in-app `<dialog>`.
4. **Dashboard, Markets and Portfolio:** shared `instrumentHeaderStrip(symbol)`, `stockEvidencePanel(selectedSymbol)` and always-reachable `Options` tab on Markets, `openTicket(selectedSymbol)` triggers, 1-line history backfill bar, populated/empty positions (`Today P/L`, `Avail Qty`), proposed portfolio live drift (`weight * 100`), and qualified performance metrics (`dietz.estimate`, scalar tiles, `external_flows`). Delete `layoutMarkets()` and `compactScannerMarkup()` in this commit.
5. **Strategy Lab, Journal, Alerts and Settings:** 3-step Strategy Lab (`renderStrategy`) accordion + `native_result` stats/fold/trade tables; Journal focus-safe search, 1-row `Position Outcomes`, guarded revert, and `openTicket(selectedSymbol)` hook; Alerts unread badge, grouped restarts, calm quote-age setup, and 3 quick rule templates; Settings 5-tab progressive disclosure, whitelisted account flags, and isolated Restore Danger Zone. Delete the post-render sibling-scraping loops in `renderAlerts()` and `renderSettingsDiagnostics()` in this commit.

No public API or backend schema changes. Shared frontend helpers reuse existing contracts.

**Environment preflight, resource budget, and validation**

Before implementation and before running any live job, run a read-only preflight check:

- **Development profile provisioning (`Start-TradingDesk-Dev.cmd`, port `8099`, `%USERPROFILE%\.cache\trader\development`):** On disk, the development SQLite store starts empty (`16 KB`) with no credentials and 0-byte Laya weights. Seed development **only** through the app's own workspace backup export from production (`8098`, read-only via `~/.cache/trader/production/runtimes/desk/python.exe -I scripts/desk_api.py`) and restore into `8099`, or export/import the 24-stock `PNIS` universe CSV. Never copy or share live SQLite files, WAL files, or OS vault credentials; development credentials and non-zero Laya weights must be present in the development profile before live jobs run.
- **Pre-cutover backup inventory:** Before any production update or destructive test, stop the target app cleanly via the tray (verifying no process holds `desk.sqlite3-wal` or `8098`) and back up `%LOCALAPPDATA%\Programs\TradingAgents\payload\app\`, `payload\provenance.json`, and `%USERPROFILE%\.cache\trader\production\application\` (including `active-store.json`, recovery generations, and `application\workflows\`, which the built-in ZIP export omits) to a timestamped folder outside both profiles (`%USERPROFILE%\.cache\trader\backups\ui-redesign\<UTC>\`). Release signing keys are out of scope.

Batch implementation before **one integrated validation cycle**, with **one consolidated correction cycle** available. The primary dispatches one execution worker with an explicit job manifest; builds and live jobs run serially.

The live validation batch (executed in strict order so latest-only research replacement never wipes out inputs needed by earlier checks) is:

1. **Small subset research smoke run (2–3 stocks)** first to confirm the Research UI, launch focus, and 6-state progress bar.
2. **One portfolio synthesis (`POST /api/portfolio-model`)** once the 2–3 smoke stocks have completed research with `final_trade_decision` and positive dated quotes.
3. **One local Laya batch (`POST /api/runs/local-laya`, up to 5 saved StockTwits posts)** on a completed stock with retained StockTwits posts (if 0 posts were returned by the vendor, record the empty-state guard as observed rather than rerunning research).
4. **One saved-plan simulation (`preview` → `run`)** using a draft proposal and complete raw `1Day` history receipt for the **same** symbol (at least 2 completed sessions at/after decision time).
5. **One bounded walk-forward experiment (`save_strategy` → `preview_experiment` → `run_experiment`):** two grid candidates, one scenario, and a history window whose computed `preview_counts` yields two folds (at most ten native runs); confirm `preview_counts` before running.
6. **Complete the 10-workspace visible browser pass and capture all smoke-dependent evidence and screenshots**, then take a backup snapshot **before** starting the final **24-stock load-test run** (because `store.prune_research()` replaces each ticker's latest result as the 24-stock batch runs).

Reuse results throughout. No automatic second 24-stock run, automated test suite, mocks, benchmarks, or per-page compilation.

Run consolidated syntax (`node --check`), selector/reference, and `git diff --check` whitespace checks. Then use the visible browser across all ten workspaces, covering ticket pinning (`selectedSymbol` vs. `ticketSymbol`), refresh/focus preservation, keyboard/editor behavior (`.cm-editor` guard and `Ctrl/Cmd+S`), empty/error states, metric qualifications, desktop layouts (`1920×1080`, `1440×900`), and specified responsive fallbacks (`1500px`, `1100px`, `790px`, `≤800px` height). Browser zoom does not count as observed Windows DPI testing (mark 125%–150% Windows DPI `unverified` unless observed on actual Windows scaling).

**Audit and delivery**

A fresh read-only reviewer replaces the worker and audits the complete candidate against the frozen blueprint (`3770bbe`), including omissions and unrelated additions. Record revision, findings, and evidence in `docs/issues/2026-10-26-dashboard-layout.md`; the primary personally signs off.

Evidence distinguishes **observed**, **source-reviewed**, **failed**, and **unverified**. Broker actions remain unauthorized. Unpopulated broker states (live multi-position holdings, option-chain quotes, `mleg` approvals, held-bracket amendments, and `outcome_unknown` transport recovery) remain **source-reviewed** unless real retained inputs exist, and missing real-state coverage blocks any claim of blanket runtime acceptance.

After validation, commit the clean candidate (no further commits before cutover verification), run `.venv\Scripts\python.exe -I packaging\refresh_project.py` to stage `desktop\src-tauri\payload\app\` and `provenance.json` (or build with `tauri.release.local.json` where `createUpdaterArtifacts=false`; never require a signing key), quit production (`8098`) cleanly, swap the backed-up `payload\app` and `provenance.json` together, and restart. Verify startup/shutdown, matching `provenance.json` commit SHA, data revisions, settings, and ticker selection against the captured production baseline (`~/.cache/trader/production/runtimes/desk/python.exe -I scripts/desk_api.py`). Preserve private runtimes and CUDA; do not repeat research during installed smoke checks. Use the consolidated correction allowance if needed, or roll back `payload\app` and `provenance.json` from the pre-cutover backup without touching production data.

Keep commits local. Remote publication requires a separate request.
