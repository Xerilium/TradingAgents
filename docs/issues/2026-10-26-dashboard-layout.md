# Dashboard stock list clipped and account values wrapped

Status: Fixed and checked in Edge through Maenifold Playwright
Date: 26 October 2026
Reviewed revision: working tree over 580f1c8; app.css +5/-2 for this repair

## Cause and repair

All 23 configured stocks were present. The fixed-height watch panel used overflow:hidden; its header, wrapped controls and pager could shrink the flexible table to zero. The account ledger combined five equal columns, large metrics and overflow-wrap:anywhere, allowing currency values to split mid-number.

The CSS batch makes the watch panel scrollable, gives its table a 160px nonshrinking flex basis, and applies the existing wider grid immediately above the tab-layout breakpoint. Ledger values use the existing heading token and stay on one line; content-sized columns preserve their values with horizontal overflow when needed. No JavaScript, data, research or broker behavior changed. Existing edits were preserved.

## Observed acceptance

Primary used Maenifold Gateway Playwright against the actual Microsoft Edge page, identified by its exact TradingAgents URL. At 1677x1205, the table had 23 rows and a 280px viewport; the last AMKR row could be brought fully into view. The stock filter and pager were visibly accessible. At 1097x1076, tabs were visible, the table had 23 rows and a 408px viewport, and all five account values occupied one line. At the intermediate 1174x843 CSS viewport, the first row remained visible, the table retained 160px and balances stayed on one line. Resized CSS viewports verify layout; actual browser zoom, other engines and mobile touch were not exercised.

Primary inspected the captured wide and narrow renders and accepts the scoped repair. The original user screenshot and the internal-browser narrow view established the pre-repair failure and retained stock data. No tests, builds, research reruns or broker actions were used.

## Impeccable checks and remaining context drift

Loaded Impeccable layout/adapt guidance and craft floor in Operate mode. The original user-skill filesystem path was absent; the live Maenifold GetConfig assetsPath resolved the installed launcher at the configured Maenifold assets directory under skills/impeccable/scripts/impeccable.cmd, using the existing cached engine 0.1.17. Context ran successfully. The layout-scoped detector returned an empty result. The full app.css detector returned 63 findings outside the modified rules; its first finding was an advisory for an undocumented existing color. No claim is made that all stylesheet findings are fixed.

The user then explicitly requested resolution of all 63 findings and the stale sidecar. The follow-up preserved active RGB/alpha values, shared repeated error and focus values, removed two overridden rules, and documented the observed component-state colors by their actual roles. The implementation worker reported the retained final Impeccable detector result as exit 0 with zero findings; the primary did not repeat that scan. Independent source review confirmed the CSS substitutions and removed-rule cascade; its typography and freshness findings were corrected before completion. Action typography is 14px, table labels 13px, and standard action previews 14px. The final sidecar write/generatedAt is later than the final DESIGN.md write. Existing derived tonal previews remain labeled as previews; no unrelated colors were inserted into ramps and no ignore configuration was added.

Primary completed one read-only Edge cycle through Maenifold Playwright across all nine workspaces, with the Dashboard also checked at wide and narrow sizes. All 23 stocks remained reachable, balances stayed on one line, and real keyboard focus had a visible 2px green outline. The visited views showed no horizontal document overflow. Initial navigation sampling raced four asynchronous view renders; only those uncompleted views were finished with a heading-change wait, without repeating passing pages or changing CSS. The first observed navigation sequence emitted no page errors; no full-product execution or every exceptional UI state is claimed. Actual Market controls, research status badges, saved rejected order rows and account settings were inspected without changing records. Captures are design-cleanup-edge-{dashboard,narrow,markets,research,orders,journal,settings}-20261026.png in the same evidence directory.

The design-contract follow-up adds 6 and removes 6 application CSS lines beyond the earlier Dashboard repair. DESIGN.md changed +87/-36 and the sidecar +53/-40. No tests, builds, research reruns or broker actions. Primary accepts this scoped design-contract repair on the working tree over 580f1c8. PRODUCT.md contained historical product claims at that review; the 28 October workflow repair below replaces them.

## Evidence

- tradingagents/web/static/app.css, ledger/watch-panel/grid rules, working delta over 580f1c8.
- Terra 6.1 extra-high source implementation and primary rendered review.
- Local evidence capture: dashboard-edge-wide-fixed-20261026.png
- Same directory: dashboard-edge-narrow-fixed-20261026.png and dashboard-edge-intermediate-fixed-20261026.png.

## 28 October: source-backed workflow repair

Status: Source UI and documentation changes accepted within the verification limits below. Production installation is unchanged. Release packaging and signing are outside this assignment.

The primary personally led the Terra specialists, authored the component/workflow documentation, selected cleanup targets, reviewed source and inspected the actual development screenshots. Checkpoint before this work: 1690752f32f3b6711d4c8f177975467def2a150e. Six UI files changed (+79/-45 lines); no tests were added or run. Final app.js SHA-256: 60b31031d9924379c9625f0af7745050adc24efa1bb20e0a767d7426ae9cb5be. Final app.css SHA-256: d29cb73b0b3b4f577ab858a780024bd465bd32e569c3a43a37ad79f902ccf37d.

Research launch now sits beside selection, with exact symbols and provider/models visible in confirmation. Dashboard chrome is compact, secondary quote information is disclosed, and confirmation keeps its action reachable while content scrolls. Research distinguishes batch activity from selected evidence. Detail return labels retain context; basket edits invalidate obsolete previews. Model proposal, historical evaluation and actual performance remain distinct.

Independent source review found Mermaid escaping and a missing provider label; both were corrected. The primary caught a watchlist-collapse regression before acceptance and corrected it. JavaScript syntax, Git whitespace and canonical documentation-link checks passed. Initial Impeccable checks reported an existing unrelated color advisory; no claim of a clean full-product detector scan is made.

A visible development pass checked research selection/confirmation, Markets navigation, all Research tabs and delete disclosure without deletion, Portfolio views and the Journal link, Orders/Basket views, and Strategy lab's read-only source loading. META/NVDA stayed the selected batch while GOOGL was inspected. Zero selection disabled launch. The primary inspected captures at 1280x720, 900x700 and 1440x900; the final wide correction kept the action inside its panel, and expanded confirmation content scrolled with Start visible. Passing views were not repeated; observed defects received scoped corrections.

Development reported unavailable native credential storage and had no retained research, supported instrument receipts, drafts or populated account evidence. Populated report/basket-field behavior, simulation execution and broker lifecycles were not exercised. No research, model synthesis, simulations or broker actions were started. Production remained connected and its data/credentials were untouched.

README.md now maps the integrated platform; docs/user-workflows.md and docs/platform-reference.md provide canonical journeys and capability boundaries. The operating guide and PRODUCT.md were replaced with current facts. Sixteen obsolete generated/reference files were removed; docs/nautilus-v1-runtime-manifest.json remains because runtime code uses it. No replacement audit dump was created.


## 29 October: blueprint Step 1 Foundation

Status: Step 1 is not accepted. Commit `aaf2e3a` contains partial Foundation work and bounded compatibility evidence; the report-only confession and repair record below qualify its claims. Steps 2–5 are not implemented by this batch. Implementation authority: `docs/ui-redesign-implementation-plan.md` (v2 at `12e7700`), jointly read with `docs/ui-redesign-blueprint.md` frozen at `3770bbe`. Base revision: `477abaa`; the local commit containing this section is the candidate revision.

Primary owns app.js, index.html, app.css, DESIGN.md and Git. No support-file editing was delegated. A fresh read-only source reviewer was already running when the human corrected the added per-step review; its one result was collected without another review. It found permanent pinning, compact-state rating/draft bindings, stale tab attributes, row-focus loss and shared evidence repaint scope. Primary corrected these in one source batch; the browser subsequently found the legacy renderer omitted the new pin notice, which was included in its existing pane extraction. No independent review pass or blanket acceptance of the corrected candidate is claimed.

### Bounded preflight and design context

The isolated development profile and repository desk/native Python executables existed. The development desk subsequently showed seven default FANGMAN symbols, no retained research or human proposals, unverified account state and native credential storage unavailable. No production export/restore, credential provisioning or model-weight provisioning was performed. These missing live inputs limit populated-state coverage; they do not block frontend implementation. Production stayed stopped and untouched.

Impeccable Operate, its craft floor, PRODUCT.md and DESIGN.md were read. The one context-loader attempt used an unsupported target option; context was read directly afterward. A detector invocation with that same unsupported option did not scan; no detector pass is claimed. No design-sidecar drift repair was undertaken.

### Implemented contracts and DOM handoff

- `app.js`: `inspectSymbol`, `pinTicket`, `researchDeleteSelection`, empty initial research batch, explicit search Enter/Shift+Enter and inspection-independent checkbox changes. Legacy ticket forms retain their symbol, block another symbol's ticket/chart-copy path, and release only on explicit new/discard/reset. The docked drawer remains Step 2.
- `captureRenderInput` / `restoreRenderInput` preserve focused form values, caret and local scroll across matching-context background renders, including exit/package fields. Existing draft models, report anchors and pane scroll retention remain in place.
- `renderTablist` / `bindTablists`: native buttons with `role=tablist/tab`, `aria-selected`, roving tabindex and Left/Right/Home/End activation. Dashboard tabs use `#dashboard-panels-{watch,chart,research,positions,orders}` and `#dashboard-pane-*` with `aria-controls` / `aria-labelledby`.
- `instrumentHeaderStrip(symbol)`: explicit quote/sizes and derived IEX spread, nullable capability flags, verified exposure gate, human-draft count, detailed-result-gated rating, age and saved raw-close drift. Dashboard consumes it; later workspace mounts stay in their assigned steps.
- `stockEvidencePanel(symbol)` delegates to the single existing provider/SEC/corporate-action renderer inside UniverseReview. `UniverseReview.loadStockEvidence` and `bindStockEvidence(symbol)` expose the existing read/form binding. Async saved-evidence completion can repaint the matching Dashboard, Markets or Research mount. Existing `/api/stock-evidence` GET and explicit `/api/market-history` evidence POST contracts are unchanged; no provider job was requested.
- Shell IDs: `#context-symbol`, `#shell-alerts`, `#account-blocked`, `#shell-recovery`, `#pause-trading`, `#gateway-status`, `#stream-status`, `#laya-shell-status`. Ten distinct SVG paths; 36px desktop app bar, compact workspace heading, main padding and no footer. Order-status control opens existing management; it does not change broker authority.
- All four legacy helpers and call sites (`layoutOrders`, `layoutBasketGroups`, `layoutMarkets`, `compactScannerMarkup`) remain. Backend/API/static allowlist/export/import remain unchanged. No new served static files.

### Observed compatibility and limits

One bounded visible in-app-browser pass used actual development port 8099 and its isolated store. The normal development launcher performed its incremental Tauri dev startup; no release/package build occurred. Dashboard, Portfolio, Markets, Research, Orders, Strategy lab, Journal, Alerts, Workflows and Settings rendered. Workflows completed loading its catalog and showed Active: Default; no workflow activation/edit or research was performed. Broker, empty-research and unavailable-credential states remained explicit.

The initial render failed because attention occurrences are a keyed object; the shell now uses Object.values before filtering. Historical console errors at 21:39 UTC belong to that failed initial load. No new error was observed in the subsequent page pass. This does not certify every control or populated state.

Observed Foundation interactions: default 0 checked; typing J in the watch search retained input focus and inserted text rather than navigating; Ctrl+K focused symbol search; Shift+Enter checked AAPL while inspection remained GOOGL; tab ArrowRight selected Research with tabindex 0 and restored focus; repeated Markets X/Space kept focus on AAPL and preserved inspection separation; unsaved AAPL quantity 3 remained after inspecting MSFT and reopening the pinned ticket. No preview/save/approval/submission/cancel/replace, collection, research, simulation or model synthesis was invoked.

CSS viewport observations: 1920×1080 and 1440×900 used a 36px bar and all Dashboard panes; 1100×800 and 790×800 used one Dashboard pane with reachable tabs and natural header wrapping. No horizontal document overflow was observed at these sizes. The 1500×900 viewport was used for the Markets ticket interaction. Actual Windows 125%–150% DPI remains unverified.

Evidence: `.local-workspace/evidence/foundation-20261029/markets-pin-and-focus.png` and `dashboard-{1920x1080,1440x900,1100x800,790x800}.png`. These local captures contain the actual empty development state; no fabricated market or account inputs were used.

Syntax: `node --check` passed all eight top-level `tradingagents/web/static/*.js` files. Corrections were followed by parser checks of the final changed app.js. `git diff --check` passed after removing the extra CSS EOF blank line. No tests were authored/run. The earlier primary source sign-off was withdrawn after the report-only confession; only the listed empty/unavailable-state observations stand; real retained populated data, editor-local save, shared-evidence populated mounts, all exceptional broker lifecycles and the future docked drawer remain unverified or deferred as shown below.

### Continuing requirement traceability

Each row tracks the full blueprint requirement. Partial Foundation coverage never marks a later workspace requirement complete. Evidence categories are observed, source-reviewed, failed and unverified.

| Requirement | File and function / remaining stage | Evidence | Verdict |
|---|---|---|---|
| US-01 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-02 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-03 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-04 | app.js instrumentHeaderStrip; complete Research mounting in Step 3 | source-reviewed | Foundation helper implemented; populated verdict unverified |
| US-05 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-06 | app.js inspectSymbol/pinTicket/proposalEditor/chart-copy guards; drawer in Step 2 | observed | Legacy unsaved pin retention observed; drawer deferred |
| US-07 | index.html; app.css shell; app.js pageHeader | observed | Foundation shell implemented; actual Windows DPI unverified |
| US-08 | app.js readState/renderOverview; Dashboard refinements in Step 4 | observed | Empty initial batch and compatibility observed; full story deferred |
| US-09 | app.js instrumentHeaderStrip; Markets mounting in Step 4 | source-reviewed | Shared helper implemented; scan/header composition deferred |
| US-10 | app.js stockEvidencePanel/evidenceRecords/loadStockEvidence/bindSupplementary; later mounts in Steps 3–4 | source-reviewed | Shared compact collection/read primitive repaired; empty state and form validation observed. Populated records and collection execution unverified. |
| US-11 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-12 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-13 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-14 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-15 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-16 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-17 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-18 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-19 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-20 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-21 | app.js captureRenderInput/restoreRenderInput; Journal redesign in Step 5 | source-reviewed | Shared focus primitive implemented; full Journal story deferred |
| US-22 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-23 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-24 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| US-25 | app.js renderTablist/bindTablists/traderShortcut; chart alternatives in later stages | observed | Foundation tabs/guards implemented; chart story remains partial |
| E-01 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| E-02 | app.js instrumentHeaderStrip | source-reviewed | Nullable quote/size/derived-spread helper; populated feed unverified |
| E-03 | app.js instrumentHeaderStrip | observed | Unknown capability state observed; true/false retained states unverified |
| E-04 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| E-05 | app.js renderShellStatus; Settings in Step 5 | source-reviewed | Shell whitelist warning implemented; populated flag states unverified |
| E-06 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| E-07 | app.js evidenceRecords/stockEvidencePanel/bindSupplementary | source-reviewed | SEC statement/SIC, corporate-action and news rendering implemented from existing record schema; populated runtime evidence unverified. |
| E-08 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| E-09 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| E-10 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| E-11 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| E-12 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| E-13 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| E-14 | app.js renderShellStatus; index.html #stream-status | source-reviewed | Implemented in aaf2e3a; unknown stream state observed. Listening/connecting/not_started/disconnected transitions and optional gaps unverified. |
| E-15 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| C-8 | app.js exposureKnown/instrumentHeaderStrip | observed | UNKNOWN observed on unverified account; verified positions unverified |
| C-9 | app.js inspectSymbol/pinTicket/legacy ticket guards; Step 2 drawer | observed | Pin/retain/reopen observed; full drawer handoff deferred |
| L1 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| L2 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| L3 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| L4 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| L5 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| L6 | app.js renderChrome; Orders/Settings remaining Steps 2/5 | observed | Shell Orders: Active/Paused wording; full cross-page story partial |
| L7 | app.js iconPaths | source-reviewed | Ten distinct paths; journal alias removed |
| L8 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| L9 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| L10 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| L11 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| L12 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| L13 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| L14 | app.js renderChrome; remaining Steps 2/5 | observed | Shell pause-management wording; cross-page work deferred |
| U1 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |
| U2 | Blueprint §§5–8; assigned workspace stage 2–5 | unverified | Deferred; not claimed complete by Step 1 |


## 29 October: bounded Foundation repair after confession

Scope: the explicit correction to Step 1, jointly governed by `docs/ui-redesign-implementation-plan.md` and `docs/ui-redesign-blueprint.md` at `3770bbe`. Base revision `aaf2e3a`; the local commit containing this repair record identifies the repaired source. No Step 2 implementation or new acceptance declaration is implied.

The single shared `stockEvidencePanel` now contains a compact provider/scopes/start/end/earnings-horizon bar, validation and in-flight handling. Its saved read has explicit loading, empty and error states plus an explicit read-only retry. Error guards prevent repeated render-driven retry loops. Provider collection remains an explicit existing POST `/api/market-history` with `{action: evidence, symbols, provider, scopes, start, end, earnings_horizon}`; saved observations use the existing GET `/api/stock-evidence?symbol=...`. No endpoint/backend/static file was added. The collection request itself was not executed.

`evidenceRecords` renders backend-selected latest eligible SEC XBRL facts in Balance sheet, Income statement and Cash flow tables with exact values/units, period, filing date/form and original filing links. It labels these as supported line items, not complete financial statements. SIC classification has its code/system/industry and expressly does not imply a sector. Corporate actions retain action/effective/process dates and reported terms with comparison warnings. News retains titles, publisher, publication/update/retrieval times, summaries and original links. Other provider records remain inspectable. Observation completeness, latest-attempt gaps, retained-older-data warnings, request qualifications, receipts, hashes and exact source fields remain available. These populated render paths are source-reviewed against `stock_evidence.py`; no records were fabricated to exercise them.

`instrumentHeaderStrip` now requests existing retained research details through `ensureResultDetail` for the header's own run/symbol, using the existing epoch/request/error/cache guards. The final-decision/revision check still gates its rating. `loadedDailyHistory` supplies the applicable already-loaded daily source, including the Dashboard's displayed retained history or the selected instrument's current/saved history; drift can also fall back to its matching research chart evidence. It uses an exact trade-date bar and positive `raw.c`, rejects non-daily/explicitly adjusted or mismatched sources, and does not collect new history. Completed ratings and numerical drift remain unverified in the empty development profile.

The investor reload now awaits its GET into a local `loaded` value before assigning the record or clearing ticket identity/dirty state/draft maps. A rejected GET enters the existing error path with pin and terms intact. This failed-request property was source-reviewed; no failure injection, fake service, or destructive input was used to claim runtime acceptance.

Affected visible-browser evidence: actual isolated development 8099, Markets → AAPL → Research displayed the shared panel and honest no-evidence state. SEC selection exposed fundamentals/classification; missing dates disabled collection; valid draft dates enabled it without a request. Non-earnings horizon remained disabled; Alpha Vantage earnings selection enabled the horizon and kept collection disabled without a horizon. No queue button was clicked. The API-read and form-binding path produced no captured console error. Screenshot: `.local-workspace/evidence/foundation-20261029/repair-evidence-sec-controls.png`. Loading/error presentation, populated SEC/SIC/action/news records, completed rating, numerical drift and failed-reload behavior remain source-reviewed/unverified, not observed passes.

All eight top-level static JavaScript files passed `node --check` after batching the main changes. The final daily-history selection correction received an additional app.js parser check; whitespace passed on the final changed files. No test suite, mock, extra reviewer, live job, provider collection, production action, drawer implementation or later-page redesign was performed. Existing legacy layout helpers and call sites remain.

This repair corrects the named Foundation source gaps and E-14 tracking; it does not retroactively accept aaf2e3a or certify populated behavior. The broader Step 1 acceptance decision remains with the human.
