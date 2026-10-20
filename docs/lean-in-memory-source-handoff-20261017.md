# Current source handoff: in-memory native cache

17 October 2026. This supersedes the Redis/paired-native-recovery portions of the previous handoff. The user rejected Redis and the separate native crash-recovery project (USR-RECOVERY-NO-REPLAY-20261017).

## Source completed

- Official Nautilus v1 uses CacheConfig(database=None), with native database loading and persistence snapshots disabled. Normal startup does not load a native cache configuration, read a Redis password, start Docker/Redis, restore a native dataset, run an AOF barrier or poll Redis health.
- The native worker retains current broker observations and the official native in-memory market/account cache. An initial read-only account/positions/open-orders observation becomes available before historical-fill collection. Unsupported native imports are withheld and identified separately; they do not turn available broker account/price views into a persistence error. The native cache runs in memory and no persisted native proof is produced.
- Broker positions/open-order completeness is separate from native financial comparison. The investor can see actual source holdings, counts, prices and outside-universe holdings while native comparison is incomplete. Source import errors and native comparison gaps remain distinct. General proposal principal/quantity previews can use a complete broker observation without claiming execution readiness.
- Existing SQLite application records, saved research, proposal and basket records, command identities, receipts and commitments are retained. No data migration/conversion/deletion was performed. Historical receipts remain inspectable without being promoted to current durable proof.
- Approvals, admission and transport are disabled independently of browse-only mode. The normal launched session remains browse-only, so no new research runs are authorized. Local human proposals, stock review, saved research and journal/reporting views remain available. Command recovery returns an explicit deferred status and does not try to certify the in-memory cache.
- Redis telemetry, AOF/native backup controls, paired-recovery controls and scripts are removed from active investor pages and the static allowlist. Retired native/paired API actions reject the request. Old paired-stage files do not block normal launch or local investor workflows.
- Application-only SQLite backup/restore remains. Damaged-journal application restoration can activate its validated retained sibling generation in the same web process, browse-only, with the native worker stopped. Restored approvals/exercise grants remain invalid; uncertain command authority is retained rather than released.
- Normal launcher configuration contains only application, history, native Python, credential-file path and port. It requires the existing migrated SQLite store and matches an existing service by application identity, in-memory mode, browse-only status and disabled execution. No native-cache configuration or automatic migration flag remains.
- Original Redis/native data, archives, historical source and evidence are retained. The old setup README is marked retired and no normal investor path points to that setup. Root owns actual removal of the previously created Redis containers/image; this coding chat did not run the uninstaller.

## Changed source and documentation

- C:/src/TradingAgents/tradingagents/web/nautilus_v1.py
- C:/src/TradingAgents/tradingagents/web/nautilus_worker.py
- C:/src/TradingAgents/tradingagents/web/nautilus_runtime.py
- C:/src/TradingAgents/tradingagents/web/service.py
- C:/src/TradingAgents/tradingagents/web/server.py
- C:/src/TradingAgents/tradingagents/web/recovery.py
- C:/src/TradingAgents/tradingagents/web/recovery_mode.py
- C:/src/TradingAgents/tradingagents/web/account_projection.py
- C:/src/TradingAgents/tradingagents/web/investor.py
- C:/src/TradingAgents/tradingagents/web/decision_journal.py
- C:/src/TradingAgents/tradingagents/web/static/app.js
- C:/src/TradingAgents/tradingagents/web/static/index.html
- C:/src/TradingAgents/tradingagents/web/static/recovery.html
- C:/src/TradingAgents/tradingagents/web/static/recovery.js
- C:/src/TradingAgents/Launch-TradingDesk.py
- C:/src/TradingAgents/Start-TradingDesk.ps1
- C:/src/TradingAgents/tradingdesk.launch.json
- C:/src/TradingAgents/docs/nautilus-v1-runtime-manifest.json (source-direction metadata only; installed native hashes unchanged)
- C:/src/TradingAgents/docs/paper-trading.md
- C:/src/TradingAgents/docs/nautilus-batch1-capabilities.md (supersession notice)
- C:/src/TradingAgents/docs/lean-command-recovery-source-handoff-20261017.md (supersession notice)
- C:/src/TradingAgents/.native-cache-setup/README.md (retired notice)

## Exact normal startup

Project-local entry: C:/src/TradingAgents/Start-TradingDesk.cmd, using C:/src/TradingAgents/Launch-TradingDesk.py and C:/src/TradingAgents/tradingdesk.launch.json.

Equivalent direct server arguments, from C:/src/TradingAgents, are:

~~~
rtk proxy C:/src/TradingAgents/.venv/Scripts/python.exe -m tradingagents.web.server --port 8098 --data-dir C:/src/printerv2/evidence/runtime-staging/20261017T024233Z-e3f9548d/application --history-dir C:/src/printerv2/evidence/runtime-staging/20261017T024233Z-e3f9548d/history --nautilus-python C:/src/printerv2/.venv-nautilus-v1/Scripts/python.exe --alpaca-credentials-file C:/src/printer/apps/tradingagents/.env --browse-only
~~~

There is no --native-cache-config or --migrate-journal argument. Native start in the browser starts only the configured Python worker. The launcher refuses to reuse an older Redis-backed service that lacks the new in-memory mode identity. Root must handle its owned old process before deployment; no process was stopped or started here.

## Remaining work and honest limits

The previously recorded investor-feature source inventory has no other known intentionally unfinished feasible item after this change. Investor source behavior is still unverified; this is not an acceptance audit. External source/provider coverage, investor risk/freshness/expiry/benchmark/method choices and actual authorized populated-account evidence remain outstanding where previously recorded.

Missing original command evidence, unknown fees and unsupported historical native position/P&L data remain explicit; an in-memory cache does not resolve them.

No tests/test-writing, harnesses, builds, imports, syntax probes, runtime/browser checks, research, broker operations, installations, PowerShell policy changes, migration or data conversion were performed in this batch. Source reading was used only for implementation. Approximate cumulative contribution score: -9,100; not measured by a line-count check. Source is now held for root's next development assignment; no verification is started here.

## Requirements-cited investor batch manifest — 17 October 2026

Authority: C:/src/printerv2/evidence/tradingagents-build-roadmap.md (approved specification), with requirement IDs from C:/src/printerv2/evidence/tradingagents-delivery-checklist.md. This manifest is recorded before the covered product edits. No new source acceptance audit or execution-based verification is authorized. The prior D1–D9 deletion batch remains intact; its edit ledger is .runtime-stage/source-deletion-accounting-20261017.json.

| Item | Concrete missing behavior or disposition | Requirement ID and short verbatim requirement | Existing symbols and smallest planned change |
| --- | --- | --- | --- |
| M1 | Current-market chart range/session controls use the saved-research cache key even though the renderer supplies a distinct current-market key. This is a source wiring gap, not an assertion about a browser result. | DA3/DA4/UI5: “Support chart hover and time-range selection” (specification line69); “two distinguishable evidence periods” (line150); “without losing selection” (line300). | C:/src/TradingAgents/tradingagents/web/static/app.js, UniverseReview.savedChart/bindEvidence. Put the renderer's existing evidence key on its figure; bind range, date, click and keyboard selection to that figure's state. Reuse the existing renderer and data paths. |
| M2 | Selected-bar inspection has OHLCV and prior recorded close but lacks the required movement percentage and calculation basis. | DA1/DA3: “movement percentage and its calculation basis” (specification line152), together with “inspect its exact values” (line71). | Same file, UniverseReview.savedChart. Display close-to-prior-recorded-close percentage using the existing recorded bar values, source dates and percentage formatter. Label the formula and previous available recorded session, retain exact raw closes, and show unavailable for missing/non-finite inputs or nonpositive prior close. No new data acquisition or claim mapping. |
| H1 | Holdings-specific preferences: source present, acceptance prohibited. No product edit. | UI4/UI5/AC4: “Save watchlists and preferences in the local app” (specification line79); “Browser storage is a disposable cache” (line269); “Quotes update without losing selection, typed text, table scroll, column settings” (line300). Checklist line75 calls for explicit holdings-preference disposition. | C:/src/TradingAgents/tradingagents/web/workspace.py preferences/change already accept holdingsQuery, holdingsSort, holdingsFilter, holdingsDescending. C:/src/TradingAgents/tradingagents/web/static/app.js currentPreferences/persistPreferences/saveWorkspace/adoptWorkspace and the holdings input/change/direction handlers already save and restore those fields through /api/workspace and existing SQLite records. portfolioView is also present. No new preference schema or migration is needed. |

The existing audit records general human/research proposals, baskets, policy, exact command records, journal/performance/export, attention/review, application recovery and request protection as retained required source. Disabled approval/admission/transport controls reflect the current mandatory prohibition, not permission to activate them to make a feature appear complete. They are not rewritten in this batch. MarketDataJobs remains the current-history data route and the saved evidence reader remains saved-only.

Protected exceptions remain the D1–D9 ledger's unrelated tests/UI/chart helpers, retained evidence/data/receipts/backups/secrets, required environments and historical documents. External populated-account evidence, provider coverage/entitlements and investor policy/freshness/expiry/benchmark/method choices remain prerequisites, not invented code gaps. No separate native crash-recovery project remains pending.

Planned product edits are limited to M1 and M2 in the existing active chart renderer/bindings. Every added line serves one of those cited behaviors. No tests, product imports, syntax/build probes, runtime/HTTP/browser actions, research, grants/admission/trades, installs, migrations or settings changes will occur.

### Source handoff for M1/M2; H1 disposition

M1 (DA3/DA4/UI5; specification lines69/150/300) and M2 (DA1/DA3; lines71/152) are saved in C:/src/TradingAgents/tradingagents/web/static/app.js, UniverseReview.savedChart and bindEvidence. The existing renderer exposes its exact evidence key to its range/date/click/keyboard bindings. Each active chart changes its own view state, preserving separate saved/current selections.

Movement uses the actual selected evidence's recorded close and previous available recorded bar close. It preserves their dates/raw values and the displayed price/adjustment basis, labels the formula (selected recorded close / previous available recorded close - 1) x 100, and explicitly distinguishes recorded closes from the current last trade or bid/ask midpoint. Missing/non-finite inputs, nonpositive prior closes or non-finite results display unavailable. It does not assert that an earlier available bar is the immediately previous trading session or rewrite a saved input. Saved/current data acquisition routes and immutable evidence are unchanged.

H1 (UI4/UI5/AC4; specification lines79/269/300, checklist line75) is source present, acceptance prohibited: the existing UI→workspace validator→SQLite→adoptWorkspace preference path already contains holdingsQuery, holdingsSort, holdingsFilter and holdingsDescending, with portfolioView also retained. No duplicate implementation, preference migration or schema change was made.

Product edit accounting captured during the edits: 11 lines added, 5 removed, net +6; zero test lines. Added-line score for this batch: -11. Documentation records the required manifest/disposition rather than introducing a framework. No post-edit check, test, product import, syntax/build probe, browser/runtime action, research, approval/grant/admission/broker write, installation, migration or settings change was performed. No behavioral or requirement-acceptance claim is made.

No further concrete feasible source gap is known from the previously recorded inventory and the implementation paths read for this batch. This does not convert missing acceptance into delivery. External prerequisites remain authorized populated-account evidence, provider entitlements/coverage and investor policy/freshness/expiry/benchmark/technical-method choices. No separate native crash-recovery project remains pending.

D1–D9 deletions and its exact protected exceptions remain in force: pre-existing stockChart/equityChart/watchlist/positionsTable, their handlers and chart state (selectedEvidence/evidenceKey/chartEvidence/chartRequests/chartErrors/chartLoadedAt/selectedBarDate/displayedBars/ensureChart/chartPeriod/chartMode), unrelated tests/UI, evidence/data/receipts/backups/secrets and required environments. M1/M2 change the separate active UniverseReview chart only. Request protections, official v1/in-memory adapter, SQLite records and disabled trading gates are unchanged.

Source edits are held. This source chat performs no tests or execution-based verification; the separate verifier owns checks.

## Withdrawn scenario planning — 17 October 2026

Latest direct user instruction: “Get rid of it.” The USR-RECOVERY-NO-REPLAY-20261017 planning batch introduced no product code. Its unimplemented manifest and clarifications are withdrawn, not unfinished delivery. No restart invalidation, abandonment/status flow, UI addition or replacement subsystem was implemented or removed. Established broker-first startup, command/history/proposal records, existing controls, D1–D9 cleanup and completed chart fixes remain unchanged.





## Final wording-only removal — 17 October 2026

Authority: USR-RECOVERY-NO-REPLAY-20261017, C:/src/printerv2/evidence/tradingagents-build-roadmap.md lines5–7, and the latest feature freeze. Remove only remaining human-readable statements that defer a separate native crash/cache project: this handoff, docs/paper-trading.md current instructions, nautilus_worker persistence limitation, service health/approval/command messages, admission refusal/reconciliation messages, and static/app.js cache/launch wording. Existing status keys, disabled guards, startup, reconciliation, data/history and launch behavior remain unchanged. Separate verification is owned by the verifier; this source chat holds after the edit.

## Consolidated observed-defect patch — 17 October 2026

Root authorized exactly three fixes before these source edits. Requirement IDs are from C:/src/printerv2/evidence/tradingagents-delivery-checklist.md; current requirement text is in C:/src/printerv2/evidence/tradingagents-build-roadmap.md.
- OP1/OP3/OP7/AC5 (checklist lines60/62/66/19; roadmap lines275–279/293): the observed backup-time native shutdown follows delivery_summary → authority → repeated ApplicationDatabase construction and its writer reservation. Reuse that lifecycle's initialized database object; retain existing consistent backup, real write transactions and disabled execution.
- DA3 (checklist line33; roadmap line158: “Identify last trade versus bid/ask midpoint versus official/session close”): correct research_quote_context's false midpoint assertion to the existing quote basis, without rewriting saved research.
- UI5 (checklist line26; roadmap line306: “Quotes update without losing selection, typed text, table scroll, column settings or open research”): two observed supplementary-form open→closed transitions match disclosure restoration preceding deferred drawer insertion. Restore the existing page+symbol disclosureViews after bind inserts the drawer; retain deliberate close behavior.
No tests, runtime checks, restarts, research, broker operations, schema changes or new features are included. The active history job is untouched.

Source-only handoff: tradingagents/web/execution_lifecycle.py +4/-2 (constructor database handle and authority reuse, new lines28/59–61); tradingagents/web/service.py +1/-1 (research_quote_context, line142); tradingagents/web/static/app.js +1/-0 (deferred drawer disclosure restoration, new line1252). Total +6/-3, net +3; zero test lines, added-line score -6. Counts/diffs were captured from edit buffers, not a post-edit check. The first edit command stopped at the UI target's indentation after completing the two Python edits; the UI insertion was then applied at its existing one-space indentation. No tests, verification, product imports, syntax/build probes or runtime actions were performed. Source is frozen for independent patch review and affected-workflow verification.

## Observed news-receipt screening correction — 17 October 2026

DA8/OP6; root authorized one token-start boundary after independent review. Actual MSFT Alpaca news for 2026-10-10 through 2026-10-17 returned 38,429 bytes and 50 articles but _write_source_result withheld the receipt: two public Benzinga article URLs matched the unbounded sk-key pattern inside a word, immediately preceded by a letter. In tradingagents/web/store.py line468, only the sk- alternative now starts with a word boundary. Standalone keys and all other credential/bearer/private-key screening, bounded decoding and pagination-field handling remain unchanged. No response or URL whitelist was added and original receipt bytes remain untouched.

Edit accounting: +1/-1 product line, net0; zero test edits, added-line score -1. No tests, product execution, runtime actions, research or trades were performed. Source is frozen for independent review and root-owned retry.

## Observed proposal instrument refresh correction — 17 October 2026

Before-edit scope: root authorizes one app.js metadata refresh for the independently confirmed disconnected→connected proposal-controls failure. UI5/UI9/PR1 are recorded at C:/src/printerv2/evidence/tradingagents-delivery-checklist.md lines26/30/41. Current roadmap requirements at C:/src/printerv2/evidence/tradingagents-build-roadmap.md line95 require “validated configured instruments”; line236 requires capabilities before constructing unsupported proposals; line306 requires updates “without losing selection, typed text”. service.investor computes live instruments independently of persisted investor revision (service.py lines383–388), while refreshData currently only replaces investorRecord on a newer persisted revision. Refresh only investorRecord.instruments from each accepted source.investor, leaving investorDirty, persisted revision/data, policy/proposal drafts and conflict handling unchanged. No other product ownership is assumed; concurrent edits are retained.

Source-only handoff: tradingagents/web/static/app.js line1227, +1/-0 product line, net+1; zero test edits, added-line score -1. The existing investor-record adoption condition is unchanged; the added assignment updates only live instruments metadata. No tests, product execution, runtime/restart actions, research, grants/admission/broker writes or trades were performed. Source is frozen for independent review and root/verifier-owned connected UI acceptance.

## Observed second-page news screening refinement — 17 October 2026

DA8/OP6; root authorized this exact refinement after independent review of the bounded actual Alpaca GET-only metadata diagnosis. For MSFT news 2026-10-10T00:00:00Z through 2026-10-17T23:59:59Z (limit50, include_content=false), page1 returned 50 articles/38,429 bytes and passed screening; page2 returned 36 articles/32,700 bytes with exactly one sk-key-prefix match at news[4].url, decoding depth0, immediately preceded by a hyphen. No body, matched text, credential or cursor value was disclosed. The word boundary still matched inside a hyphenated URL slug. In store.py line468 only that token-start boundary is refined to a negative lookbehind excluding word characters and hyphens. All other markers, decoding, pagination handling and original bytes are unchanged; no URL/response whitelist is introduced.

Edit accounting: +1/-1 product line, net0; zero test edits, added-line score -1. No tests, runtime actions or other product edits in this refinement. Source is frozen for root-owned restart and actual UI verification of the complete two-page result.

## Surgical remaining-engineering batch — 17 October 2026

Before-edit authority: root authorized existing-fixture/assertion repairs, generic source-bound shorter-listing input wiring, and removal of the unissuable per-input performance acceptance dependency. No tests/runtime actions occur until the whole batch is ready; listing provenance and named performance-method semantics remain subject to the independent reviewers' precise input.
- OP5/OP6: current roadmap C:/src/printerv2/evidence/tradingagents-build-roadmap.md line287 requires Host/Origin/session/CSRF protection and credential-free errors. Repair tests/test_paper_server.py's existing handler fixture with a real maintenance RLock, explicit ordinary-mode flags, and a matching session cookie/token. Preserve protection, body validation, dispatch-count and no-service-effect assertions. The existing order-route rejection case must expect the current unconditional403, not an obsolete missing-identifier400.
- DA3/DA10: roadmap line158 requires price-type/session/time distinctions. Repair only the two existing quote-context cases in tests/test_quote_refresh.py to assert actual invalid_quote, market_open, original/older source timestamps, disabled execution and historical omission; do not add obsolete synthetic freshness/validity fields to product code. Existing cases are renamed only where their former names imply removed semantics.

### DA1 source-bound shorter-listing wiring

Before-edit citation: current roadmap line170 requires the latest252 completed sessions “or its complete available trading history if shorter”, without synthetic bars. Root/independent reviewer specified a server-owned hashed listing-provenance-v1 artifact referenced by the existing market_history record. MarketDataJobs.listing will read market_history.listing_provenance through the existing recovery.artifacts path/hash/dependency validator, match asset_id+symbol+exchange, and supply the matching fact to the existing assess(listing=...) path. The artifact uses version="listing-provenance-v1", captured_at and records; no request field or ticker/date branch supplies authority. Existing assess additionally checks symbol, regular_way_current_symbol session basis and sourced provenance; pre-regular-way dates remain retained and explicitly identified outside the required baseline. Original cached artifacts/receipts are not rewritten; root owns one-time maintenance using existing detail/assess/artifact/update functions after freeze. No new API/UI/provider or database namespace is introduced.

### PF1–PF3/UI9 / D6b named-method correction

Before-edit citation: roadmap lines285/289/390 require independently reviewed return/source semantics, explicit valuation/cashflow methods and incomplete-data withholding; they do not require an unissuable per-account/per-input operational approval. Root's engineering-gap-closeout-20261017.md records the independently cleared direction, with exact patch review required before release. Remove the per-input acceptance lookup/default/caller dependency; retain concise stable named-method provenance and existing collection completeness. UI wording identifies method support and covered inputs without claiming independent review. A named-method match alone cannot make an uncalculable metric available.
Primary sources accessed2026-10-17: https://docs.alpaca.markets/us/reference/getaccountportfoliohistory-1 (1D trading-day/session-close normalization and simple broker P/L); https://docs.alpaca.markets/us/docs/account-activities (non-trade date occurrence/settlement ambiguity); https://www.ibkrguides.com/portfolioanalyst/money-weighted-return-white-paper-llc.pdf (declared cashflow conventions, Dietz and geometric linking). Daily calendar-close mapping remains a declared valuation convention with original provider labels retained, not a claim of exact broker valuation-event times. No return formula is replaced: missing cashflow, unclassified journals, unknown exact external-flow time, currency/pagination/calendar and benchmark-basis blockers remain; TWR still requires actual matching boundaries for external flows.

### Completed source batch; root-owned offline maintenance recipe

This batch's edit-buffer accounting (no post-edit execution/check): market_history.py +21/-2; history_coverage.py +5/-1; performance_acceptance.py +15/-42; performance_inputs.py +3/-5; performance.py +3/-3; service.py +1/-2; decision_journal.py +1/-2; static/app.js +3/-3. Product total +52/-60, net-8. Existing tests only: test_paper_server.py +6/-4 and test_quote_refresh.py +7/-7; total +13/-11, net+2, no new cases. Combined +65/-71, net-6; added-line score -78 (52 product plus2x13 test lines). Historical stored acceptance fields/receipts are not erased; they no longer issue operational method approval. The existing accepted/accepted_metric_ready output keys now represent named-method support plus calculation sufficiency, not a reviewer credential or per-account grant. Exact independent code review remains pending.

The reviewed fact JSON at C:/src/printerv2/evidence/listing-provenance-20261017.json matches the implemented version/record contract; each source_reference is an official URL, while the containing server-owned artifact supplies immutable path/hash authority. No fact artifact or database pointer has been installed by this chat.

Root's one-time maintenance after source review, with its main service stopped and writer jobs quiescent:
1. Resolve the configured application/history through recovery.active_paths to honor any active generation, and hold the existing recovery.writer_lease on the configured application root. Require its existing desk.sqlite3; do not migrate. DeskStore(active_application, {}) loads the existing store without creating a web server, native worker or research executor.
2. Read and retain the current market_history record/revision. Use DeskStore._write_json_artifact with one maintenance UUID and kind listing-provenance to save the reviewed fact JSON. With ApplicationDatabase.update on that existing record and its expected revision, set only data.listing_provenance to the returned path/hash reference.
3. Use a non-started MarketDataJobs object (allocate with __new__, assign service=SimpleNamespace(store=store); do not call its constructor) solely for its existing listing(instrument) lookup. No executor, run or fetch is needed.
4. For only the four reviewed asset records, select their saved market_history.coverage metadata and corresponding entries key. recovery.artifacts(store.directory, metadata.artifact) validates/loads the cached result and recursively referenced receipts. From the result's receipts select the calendar and instrument scopes; decode their retained artifact payloads. Do not retrieve provider data. Match the retained instrument's asset ID, symbol and exchange to the fact.
5. Call history_coverage.assess with the original bars, retained calendar/instrument, original pagination_complete, original calendar_reference/instrument_reference and cache.captured_at, plus jobs.listing(instrument). Preserve all price timestamps, original bars, page receipts and complete/pagination flags. Earlier HONA observations remain context and are identified in the new coverage provenance.
6. Copy each cached result, replacing only required_coverage, and save a new iex-history-cache artifact with the existing writer. Copy its metadata, replace required_coverage/artifact, increment revision and append the old artifact to prior_artifacts. Do not overwrite or delete any old file, change a failed/latest-attempt status, or silently replace last_usable_artifact.
7. Commit those four entries and their matching coverage metadata through ApplicationDatabase.update with the reread expected revision. Keep all other entries, jobs and record fields. If a selected entry is using last_usable_artifact or does not match its coverage key, stop that item for inspection rather than inventing a merge.
8. Release the lease before root's ordinary browse-only restart. The reviewer/verifier owns integrity/coverage and visible-browser acceptance. No maintenance command, test, product import, syntax/build probe, web/native restart, research or trade was executed by this development chat.

Source and existing tests are now frozen for independent review; tests remain held until root releases them.

### Observed existing pause-route fixture repair

OP5/OP6, roadmap line287 and the root-dispatched complete three-failure batch from engineering-gap-offline-results-20261017.md. Current server.py lines325–326 maps /api/trading/pause to command_action with original paused plus action=block and blocked=paused. Repaired only the existing fixture return, both existing exact-once dispatch assertions and the existing secret-bearing failure injection to target that method. Retained exact200 response, localhost acceptance,502 failure and no-private-detail assertions. No product shim, assertion deletion or new case. tests/test_paper_server.py +4/-4; product+0/-0; test-line score -8. No execution or runtime actions. Source/tests frozen.

### Observed PF1/PF2 New York interval wiring correction

Root's actual UI collection for2026-10-15..16 returned three UTC-labelled provider points mapping to NYOct14/15/16 against a calendar for15/16. Roadmap line289 requires declared valuation/cashflow periods; current official Alpaca portfolio-history documentation normalizes1D start by the New York trading date (https://docs.alpaca.markets/us/reference/getaccountportfoliohistory-1, accessed2026-10-17). account_history.collect now constructs explicit America/New_York midnight and end-of-day bounds once and uses the same timezone-aware ISO strings for portfolio start/end and activity after/until. Each endpoint's offset follows its own date, including DST transitions. Calendar date requests, original provider labels, strict session matching and completeness blockers remain unchanged; no extra point is discarded. Product +5/-2, net+3; zero test changes, score -5. No execution/runtime actions. Source frozen for independent review and root's affected UI retry.

### Final observed optional-cashflow and visible-listing batch

Before-edit authority: root dispatched exactly these PF1–PF3 and DA1/DA2 fixes. Roadmap lines285/289 require declared source/cashflow completeness; actual collection8ae539fc omitted cashflow. Official Alpaca PortfolioHistory declares a missing-field empty-map default (https://alpaca.markets/sdks/python/api_reference/trading/models.html#alpaca.trading.models.PortfolioHistory and https://github.com/alpacahq/alpaca-py/blob/master/alpaca/trading/models.py#L348, accessed2026-10-17). Apply only get("cashflow", {}), preserving explicit-null rejection, ALL request, pagination, per-type comparison and activity/timing blockers. Coverage must identify omission/default distinctly from reported zero arrays and limit calculation to provider-as-of semantics, with creation-time pagination not settlement proof. Roadmap line170 requires truthful shorter history: add first regular-way date, retained pre-regular-way date count and safe source link to the existing current-history coverage paragraph using its existing provenance. No ticker branch, new controls or test cases.

Final two-fix source handoff: performance_inputs.py +6/-5; static/app.js +3/-1. Product total +9/-6, net+3; zero test changes, score -9. Original cashflow payload/arrays and existing financial blockers remain unchanged; only missing-key normalization is added. Existing coverage paragraph now visibly explains every sourced shorter listing, including retained mapped pre-regular-way dates. No tests, runtime actions, research or trades performed. Source frozen for independent review and root-owned restart/affected browser retry.

### A13/OP3 restored-proposal reason correction

Root's actual isolated UI restore confirmed restored_requires_review=true/impact_review_valid=false with unchanged policy. Roadmap line277 requires truthful restore/invalidation behavior. Before this wording edit, saved cards attributed all invalidation to policy. app.js line1044 now shows “Restored records; impact review required” when the existing restore flag is set, otherwise preserving the existing policy-change reason. Product +1/-1, score-1; no state/logic outside reason selection, new tests, execution or runtime actions. Source frozen for review and root's affected browser refresh.

### D4/D5/D6b existing-form copy clarification

Before-edit scope: only existing policy/reporting-choice markup/helpers in app.js, plus this handoff. Roadmap lines178/387/388/390 require explicit investor choices, concrete UI options and explained technical/reporting rules. Copy follows investor.py RULES/RULE_PARAMETERS/policy, policy_evaluation.evaluate, decision_journal.change(settings) and performance.benchmark_report. Add units/purpose for the existing ten limits and readable display labels for the existing states/method/adjustment/session options; preserve their exact submitted values, IDs/data attributes, numeric semantics, unset states and save actions. Explain that decisions can be deferred for browsing while required unset policy choices block approval, and that an unset benchmark still permits account observations. No defaults, saved data, authority, backend, controls, tests or runtime are changed. Impeccable clarify guidance was used only for this scoped copy pass; existing product/design context was read directly without running its launcher.

D4/D5/D6b source handoff: app.js +17/-3, net+14; zero test/backend/data changes, score -17. Changes are limited to existing form copy plus display-only copy tables. State options now carry explicit values matching their former implicit values so readable labels cannot change submitted state. Required option values, identifiers, data attributes and save/evaluation behavior remain intact. No tests, product execution, browser/native/server actions, research, trades or approvals performed. Source frozen for independent review and affected browser inspection.

Independent review correction: app.js line1058 restored the missing string concatenation before the policy summary closing tag. Exactly one existing line replaced (+1/-1; incremental score-1), no scope expansion or runtime/tests. Source held pending consolidated copy/value review.


## H01–H16 bounded source correction batch — 18 October 2026

Before-edit scope: complete only the independently reviewed findings in C:/src/printerv2/evidence/hardcoding-source-audit-20261018.md and hardcoding-audit-independent-review-20261018.md. Requirements below refer to C:/src/printerv2/evidence/tradingagents-build-roadmap.md; its latest user override at lines5–7 controls. No tests, product imports, syntax probes, runtime actions, installs or new dependencies; root retains deployment and grouped verification ownership. The old queued migration approval is not a new cutover instruction: the recorded staged migration already exists, preserved originals remain untouched, and main8098 is coordinator-owned.

- H01/H02: native delivery reservations and validated replacement venue IDs (5–7,65–67,105,226,228,244,404/EX6/A10); native worker owns execution_lifecycle.py, nautilus_v1.py, nautilus_worker.py, nautilus_runtime.py and active v1 manifest.
- H03/H04: functional no-broker-write approval review and ordinary reconciliation, relevant stable observation bindings, without admission/dispatch/exercise enabling (228,232–235,244,259,263,328,369,371); root owns admission/service integration, data worker owns approval_review.py.
- H05/H07/H09/H10: current authoritative calendar readiness, cash-only basket affordability including known commitments, removal of unconditional blockers, and complete empty news/actions semantics (17,65,99,144,170–172,183,258,303/A6); data worker owns market_history.py, history_coverage.py, baskets.py, investor.py, stock_evidence.py and the current-coverage correlation callsite in policy_evaluation.py. Root passes commands through service preview/save.
- H06/H08: release global maintenance lock during external account collection with generation/account/revision-validated commit; research age uses retained completion timing or an explicitly unavailable date-only legacy timestamp (85,145–146,293,305,308/A15b/P4); root owns service.py/server.py.
- H11–H15: authoritative broker-order table, explicit policy/session/age quote display, supplied company names, configured versus outside-held quote counts, exact originating research/report context (7,15,99,138,143–145,148,152,158,166,170–172,195,234–235,258,303/A1/A14); UI worker owns static/app.js and static/nautilus.js, root supplies freshness metadata.
- H16: actual current history coverage and truthful in-memory native metadata (5–7,150,170–172,293); root owns service/recovery/server metadata, native worker owns runtime/active manifest. Historical artifacts remain unchanged.

Workers were explicitly told they share the checkout and must preserve others' edits. This document records the authorized batch, not acceptance evidence.


### Completed H01–H16 source handoff

All sixteen findings have source dispositions in the single batch; no deployment or acceptance claim is made.

| Finding | Completed source disposition | Roadmap requirement |
| --- | --- | --- |
| H01 | Native delivery confirmation is current-process/epoch bound. Only genuinely confirmed delivery reservations leave native_pending_commitment; unresolved/conflicting/other-epoch reservations and ordinary broker cash/remaining commitments remain. | 5–7,65–67,105,228,244 |
| H02 | A validated broker replacement successor and matching native predecessor explicitly permit the official venue-order-ID update flag. Ordinary updates retain the default. | 226,404/EX6/A10 |
| H03 | checked_observation returns the validated observation; permitted sessions can record exact revision/binding/confirmation-based approval or revocation. Browse-only rejects these records. Existing GET-only refresh/identity lookup feeds ordinary reconciliation, with visible lookup failures and unresolved commitments retained. Admission, transport, dispatch and exercise authorization stay disabled; dependency validation no longer has an unrelated unconditional refusal. | 228,235,259,263,328,369,371 |
| H04 | Base account versions exclude watched quotes; review versions include only the proposal symbol and observed market-session state. Receipt-only metadata is stripped while source economic/event times remain. Existing material state, evidence, policy, age and expiry checks remain. | 232–233,244 |
| H05 | Present readiness is derived from hash-validated retained authoritative calendar coverage, including newly completed sessions. Captured sufficiency is disclosed separately; missing current calendar authority is unavailable. Future existing calendar GETs retain their queried horizon; reads make no provider calls and historical artifacts remain immutable. | 170–172,258 |
| H06 | Only reporting collection bypasses the global POST lock. It captures store/runtime/revision under maintenance, makes existing provider GETs outside that lock using the captured store, then checks unchanged store generation/account and expected reporting revision before commit under maintenance. A losing collection retains receipts without attaching them to a restored store. Other requests retain their existing protections. | 293,305,308 |
| H07 | Basket previews/save use cash and known local/native commitments rather than margin buying power. Broker identities are deduplicated; absent command context or unsourced external fee bounds make affordability unknown. Service supplies the actual commands record in both paths. | 17,65,183/A6 |
| H08 | Research-age context uses retained stock completion, exact completion event, or labelled run completion; legacy analysis-date-only records disclose unavailable completion age. New successful stock results record their actual completion time. Opening reports cannot refresh age. | 85,145–146/A15b/P4 |
| H09 | Unconditional unresolved freshness/coverage prose is removed; actual evaluator blockers and execution/unknown-fee disclosures remain. | 99,258 |
| H10 | Complete empty news/actions are successful observations, with aligned classification/detail/readiness and failure fallback. Old successful artifacts remain retained; fundamentals/classification still require actual records. | 144,258,303 |
| H11 | Orders displays current broker orders and completeness directly, including exact decimal quantity/filled/remaining, statuses, reasons, source and related holdings. Retired receipt overlays are not used as authoritative rows. | 7,148,152,234–235/A1/A14 |
| H12 | Price displays/filter/counts use explicit configured open/closed age tolerances, source observation age and market-session context. Unset remains unconfigured with null stale/max-age metadata; no replacement default or official-close claim. Approval continues to evaluate the actual quote independently. | 158,258 |
| H13 | Company labels come from supplied company_names with symbol fallback, replacing the limited hardcoded dictionary. | 138,143–145 |
| H14 | Configured quote coverage excludes outside-held stocks from its numerator, with outside holdings reported separately. | 15,170–172,303 |
| H15 | Optional report-to-proposal linking preserves the exact originating run, research revision and visible report, including older reports. | 99,138,166,195 |
| H16 | Health exposes actual current coverage counts. Current native runtime, health, backup/restore messages and active v1 manifest describe in-memory/nonpersistent cache truthfully. Rejected Redis recovery metadata is removed from the active manifest; wheel/version/source pins and archived evidence remain. | 5–7,150,170–172,293 |

Edit-buffer accounting only: native worker +50/-92 across execution_lifecycle.py, nautilus_v1.py, nautilus_worker.py, nautilus_runtime.py and docs/nautilus-v1-runtime-manifest.json; data worker +95/-23 across market_history.py, history_coverage.py, approval_review.py, investor.py, baskets.py, stock_evidence.py and policy_evaluation.py; UI worker +62/-42 across static/app.js and static/nautilus.js. Root: admission.py +49/-7, service.py +81/-24, server.py +9/-3, recovery.py +1/-1. Combined eighteen product/active-contract files: +347/-192, net+155; zero test changes, added-product-line score -347. Documentation/accounting artifacts are separate.

No tests, product imports, syntax/build probes, browser checks, migration, restart, provider requests, research, approval records, admission, exercise grants or trades were performed by this batch. Shell work was limited to source/evidence reads and exact-target source/document edits. An rg source-read invocation failed due to quoting and was replaced by an ordinary source read; no execution result is represented as validation.

Source is frozen for coordinator-owned grouped review and verification. The affected verification areas are current-process native reservation/replacement handling; no-write review plus exact stable bindings; current-calendar and empty-evidence semantics; cash-only basket preview/save; concurrent account collection versus navigation/Stop/restore/revision/account changes; research-age alerts; current broker orders; configured quote/session/count behavior; source names and older-report proposal origin; health and active native metadata. Main8098, staged SQLite and preserved JSON/backup data remain coordinator-owned and untouched.


## Independent-review correction batch — H01/H02, H04, H10 — 18 October 2026

Before-edit authority: coordinator's independent review identified exactly three remaining cases in the completed H01–H16 patch. Correct them together, with no new items or tests/runtime actions. H01/H02 (roadmap5–7,65–67,105,226,228,244,404/EX6/A10): after the validated replacement updates the shared native order, confirm predecessor supersession from that successor's current-process delivery and actual OrderUpdated proof, then return without attempting a predecessor cancellation against the successor. H04 (232–233,244): compare the current review's account-plus-relevant-market version with the saved review's corresponding version; preserve the separate base account version used by account/command authority and retain exact binding checks. H10 (144,258,303): pass the known scope to usable() for saved metadata, including legacy records without scope, so complete empty news/actions take precedence over stale fallback pointers and survive a subsequent genuine failure. Existing immutable history/failure fallback remains. Main8098 and all read-only guards remain coordinator-owned and unchanged.


Completed together and frozen: execution_lifecycle.py +16/-4 (edited blocks start at new lines 185, 187, 420, 433); admission.py +1/-1 (new line 268); stock_evidence.py +5/-5 (new line starts 18, 20, 184, 186, 202). Incremental product total +22/-10, net+12; zero test changes, incremental added-line score -22. H01–H16 plus this correction batch: +369/-202, net+167; cumulative batch score -369. Counts/locations come from edit buffers, not a post-edit check.

Predecessor confirmation requires the validated successor's delivery to be observed_current_process in the current native_epoch, the same shared native client identity, existing account/instrument validation, and actual matching successor OrderUpdated evidence. Pending native status alone cannot prove that replacement update. A missing/conflicting/unconfirmed successor retains unresolved reservations and records the gap. No native cancellation or cached-input replay is introduced. Review-version equality now compares the saved evaluation's relevant-market version with the fresh evaluation's relevant-market version; approval.account_version remains the account-only authority version. usable(observation, scope=None) preserves existing one-argument raw-observation callers and supplies scope at every saved-metadata fallback decision, including legacy metadata; new metadata already carries scope in this checkout.

No tests, imports, syntax/build probes, post-edit verification, browser/runtime actions, restart, migration, provider calls, research, approvals, grants, admission or trades were performed. Read-only guards and existing main8098 runtime were not changed. This three-case batch is ready for coordinator-owned independent review and grouped verification. Existing full handoff path: C:/src/TradingAgents/docs/lean-in-memory-source-handoff-20261017.md.


## USR-ALPACA-CAPABILITY-20261018 integration correction

Before-edit authority: the latest direct-user correction recorded at C:/src/printerv2/evidence/tradingagents-build-roadmap.md:11 supersedes the earlier H03 keep-disabled staging boundary. The prohibition is on agents trading or starting research; it is not an application capability restriction. Root explicitly redispatched this source-only batch. Neither the withdrawn paper-capability proposal nor its withdrawn endpoint restrictions produced any edits.

Concrete change map: preserve the configured credentials path, APCA/ACPA key aliases and the existing APCA_API_BASE_URL; make REST, trade_updates and displayed origin agree without a new mode selector or changed env value. Remove PAPER_WRITES_ENABLED and constant native/read-only protocol refusals; use existing durable human authority in the normal TradingAgents -> Nautilus -> Alpaca path. Wire service approval/admission/dispatch and capability metadata to the existing browse_only state; remove the launcher's forced browse-only argument, retaining the deliberate existing option and recovery-only protection. Remove testing-only exercise permission as a prerequisite for ordinary user commands and its UI ceremony; retain actual exact proposal approval, serialized commitments, user order block, and explicit identity-bound cancel/replace actor/reason/expiry plus renewed replacement approval. Update existing controls and status copy accordingly. Legacy native draft/direct-order execution is not resurrected.

Citations: current roadmap user override USR-ALPACA-CAPABILITY-20261018 and target17; execution contract228–236/account admission240–244 (section text is authoritative after top-of-file insertions); existing P5/P7 workflow and A7–A10; user block234, no blind resubmission229/248, request protection287, launch/recovery293. Existing supported-term, account/policy/evidence/freshness checks, immutable source receipts, default new-order block, official Nautilus native commands and existing configured origin remain. No new investor defaults, endpoint deny lists, environment restrictions, product modes, capabilities framework, dependencies, tests or research/trading permissions are added.

All product files are owned by this integration chat for this single cohesive batch; others' existing changes are preserved. Root owns deployment and no-trade browser verification. No imports/probes/checks/tests or runtime actions occur until all source changes are frozen; no broker mutation, research run, restart, migration or saved-data/env edit is performed by this chat.


### Completed configured-origin user-workflow source handoff — frozen

All source work in this cohesive redispatch is complete. The configured credentials file, APCA/ACPA key aliases, existing APCA_API_BASE_URL value, saved SQLite/data and running main8098 were not changed. No account or environment was selected/switched by the agent. REST Trading API reads and native mutations resolve the existing configured base URL; trade_updates derives ws/wss and the same host/path from that URL; runtime and UI publish that actual configured origin. The existing fallback when no base URL exists is unchanged. Configuration validation accepts an HTTP(S) origin/path without embedded credentials/query/fragment; it introduces no host allow/deny list, paper/live selector or additional endpoint capability restriction. The data API retains its existing separate data origin.

PAPER_WRITES_ENABLED and its global native refusals are removed. ExecutionLifecycle supplies the existing transport instance permission only within the durable-authority native adapter. Its existing keyword's legacy name permit_paper_execution does not select or constrain an endpoint. Native submit/cancel/modify remain official Nautilus commands feeding the existing lifecycle. Runtime JSON protocol validates read_only as a boolean rather than insisting every capable worker claim true. Normal service construction enables the existing review/admission/execution paths; the existing deliberately requested browse_only option and genuine recovery-only startup remain supported. No new capability switch/config field/mode was added. The launcher stops forcing browse-only and reuses a matching identity/cache-mode instance without assuming the investor's block state.

Ordinary user submission: save exact proposal -> evaluate current sources/policy -> record exact revision/digest human approval -> serialize/reserve through admission -> explicitly click Submit. Approval/admission do not themselves submit. New orders start blocked and require the existing explicit actor/reason block control to unblock; current source/approval/terms/account/revision/evidence/policy/age/expiry/commitment checks remain. Adding the configured endpoint to the account binding also preserves source/environment identity across review and dispatch.

D7's scoped paper-exercise permission was a connected-verification ceremony. Ordinary dispatch/action/transport boundaries no longer require require_exercise, exercise_id or a separate exercise approval. The old optional helper/API/record shape remains only for compatibility with retained history; it cannot grant or bypass ordinary exact order authority and is absent from the normal UI workflow. Cancel and replace continue to require an explicit exact working-order action, human actor/reason and future action expiry. Replacement additionally requires its separately approved/admitted current exact terms, matching account/instrument/side/type and the existing original/successor identity chain. No fresh financial defaults or automatic dispatch were introduced.

Current capability/health/order-block fields and UI copy reflect actual session/record state. Generic account verification replaces misleading paper-only UI gating, while the compatibility paper_verified flag describes the actual configured paper hostname only. Current broker observations and historical native drafts remain distinct; legacy direct-order/draft execution is not resurrected and its route explains the authoritative approval/admission/Nautilus command contract. Unconditional historical execution-disabled placeholders and direct legacy submit/cancel handlers are removed from active UI. Existing header control opens the existing actor/reason account-block controls.

| File | Edit-buffer +/- | New edited block starts |
| --- | --- | --- |
| tradingagents/web/alpaca_readonly.py | +18/-4 | 1, 7, 32, 76, 89, 95 |
| tradingagents/web/alpaca_stream.py | +9/-5 | 1, 6, 14, 22, 26 |
| tradingagents/web/execution_lifecycle.py | +3/-12 | 20, 26, 58, 208, 234, 253 |
| tradingagents/web/nautilus_worker.py | +9/-14 | 1, 31, 33, 57, 71, 278, 288, 631, 682, 714, 728 |
| tradingagents/web/nautilus_runtime.py | +3/-3 | 1, 55, 67 |
| tradingagents/web/admission.py | +10/-15 | 1, 40, 93, 346, 357, 360, 376, 386, 390, 405, 407, 482, 492 |
| tradingagents/web/service.py | +21/-17 | 1, 21, 219, 403, 416, 419, 425, 430, 515, 785, 790, 794, 802, 808, 822, 964, 968 |
| tradingagents/web/investor.py | +1/-1 | 142 |
| tradingagents/web/account_projection.py | +1/-2 | 113 |
| tradingagents/web/recovery.py | +1/-1 | 510 |
| tradingagents/web/server.py | +2/-2 | 273, 306 |
| tradingagents/web/static/app.js | +40/-42 | 203, 219, 294, 296, 327, 532, 545, 634, 641, 644, 677, 1042, 1051, 1069, 1073 |
| tradingagents/web/static/command-controls.js | +12/-16 | 4, 12, 17 |
| tradingagents/web/static/nautilus.js | +1/-1 | 5 |
| Launch-TradingDesk.py | +2/-4 | 40, 58 |

Exact fifteen-file product delta: +133/-139, net-6. Incremental score -133; cumulative authored additions across H01–H16, its three-case correction and this integration batch: +502/-341, net+161, score -502. Zero test changes. Root accounting comes from original-to-final edit buffers retained under .runtime-stage/alpaca-workflow-source-before-20261018; the UI worker supplied its corresponding exact final-buffer counts. The accounting artifact is .runtime-stage/alpaca-workflow-accounting-20261018.json. Counts and line starts are not post-edit verification evidence.

Per-change requirement mapping: configured REST/stream/runtime/labels -> USR-ALPACA-CAPABILITY-20261018 and actual account/source identity in the execution contract; native lifecycle/service/admission -> that override plus existing per-order approval, pre-dispatch revalidation, serialized account commitments, explicit cancel/replace and A7–A10; UI/investor/status/capability metadata -> target user-operated workflow, exact approval terms, actual working-order visibility and user block; launcher -> existing launcher/health requirements; projection/recovery text -> truthful current capability versus reconciliation and retained order block. Earlier numeric citations remain section references after the new override insertion; no rejected crash/replay requirement is reinstated.

Legitimate constraints retained: actual configured account identity, saved-revision/term hashes and valid human approval; current reconciled/fresh observations and explicitly chosen policy limits; default/user block; whole-share supported BUY/SELL MARKET/LIMIT DAY/regular-session terms and the existing documented native CASH mapping; exact single-order cancel/replace identity and source-backed native lifecycle/commission proof; unknown outcomes retain commitments with no blind resubmission. These are existing supported behavior or actual source/authorization checks, not substitutes for the agent's no-trade instruction. Imported external observations alone do not manufacture an app-owned execution command or authorization.

No tests, product imports, syntax/build probes, post-edit verification, browser actions, broker GETs/mutations, research runs, approvals/admissions/action grants, migration/restart/deployment, environment edits or saved-data writes were performed by this batch. Root owns grouped no-trade acceptance and independent source sign-off after freeze. Source completion is not a successful-order or profitability claim. Full source handoff: C:/src/TradingAgents/docs/lean-in-memory-source-handoff-20261017.md.


## Consolidated replacement correction — 18 October 2026

Before-edit authority: independent review of the frozen USR-ALPACA-CAPABILITY-20261018 batch identified exactly two remaining replacement blockers. The pinned official Strategy.modify_order applies OrderPendingUpdate to cache before the execution-client ModifyOrder callback. Recognize only a durably authorized, current-epoch exact native action's first pending event when comparing/binding the unchanged broker account state; retain actual native display and every broker/economic/account/expiry check. Apply the same exact mechanism to the corresponding cancel transition where necessary; never replay an action. Compare limit-price economics with finite exact Decimal values while preserving missing/present distinctions, so 700 and 700.00 are equivalent.

Requirement authority: current roadmap USR-ALPACA-CAPABILITY-20261018 plus existing exact working-order identity, renewed replacement approval/terms, pre-dispatch account validation and no-blind-resubmission contract. No other capability or account/endpoint change is authorized. Root owns no-trade reload/browser verification. No tests/new tests, imports/probes, startup, broker operations or research runs in this correction.


Completed together; source frozen. Observer.dispatch now records the exact current authorized native action's pre-command order snapshot, prior native event IDs and native epoch before invoking official modify/cancel. This is provenance for a single native transition, not replay or new user authorization. It rejects reuse/expired/different action, non-working order, mismatched account/instrument/client/venue identity or an already-started transport boundary.

Reconciliation recognizes only the next matching official OrderPendingUpdate/OrderPendingCancel event with the identical full prior-event sequence, current epoch, exact bound command/action identities, actor/reason, action time and future expiry, while the broker still reports the pre-command ACCEPTED/PARTIALLY_FILLED state. All existing native-versus-broker account/instrument/client/venue/quantity/fill/side/type/TIF/price/average checks remain. The displayed nautilus snapshot remains actual pending state. Only the proven row's binding uses its saved pre-command native snapshot; every broker row/account/position field and unrelated native order remains bound normally. New native events/fills, broker changes, wrong epoch/action/identity or expiry remove the exception. No general pending-state suppression, auto-dispatch or replay is added.

Price equality now uses the existing finite Decimal parser, preserves None-versus-present semantics and requires exact economic equality; equivalent decimal spelling no longer fails. Quantity equality and renewed replacement approval remain unchanged.

| File | Edit-buffer +/- | New edited block starts |
| --- | --- | --- |
| tradingagents/web/execution_lifecycle.py | +20/-2 | 18, 59, 282 |
| tradingagents/web/nautilus_worker.py | +17/-4 | 220, 230, 232, 704, 710 |
| tradingagents/web/account_projection.py | +24/-2 | 4, 21, 80, 101, 116 |
| tradingagents/web/admission.py | +2/-0 | 34 |

Incremental product total +63/-8, net+55; zero test changes. Incremental score -63; cumulative score -565. Exact counts/locations are from the edit buffers and recorded in .runtime-stage/replacement-correction-accounting-20261018.json. No tests, imports, syntax probes, verification, browser/runtime/startup/restart/deployment, env/saved-data changes, broker reads/mutations, research, approvals or actual action dispatch were performed. Source is frozen for root-owned review and grouped no-trade verification. Full handoff: C:/src/TradingAgents/docs/lean-in-memory-source-handoff-20261017.md.


## Observed configured /v2 joining correction — 18 October 2026

Before-edit authority: root's actual normal-mode browser rollout found APCA_API_BASE_URL includes terminal /v2. The existing shared helper retained that version path while REST callers supply /v2/account and trade_updates supplies /stream, causing /v2/v2/account and /v2/stream. USR-ALPACA-CAPABILITY-20261018 requires honoring the configured endpoint. Normalize only a terminal /v2 path segment once in trading_endpoint after the existing URL validation. Preserve scheme, host and any earlier intended prefix; root and terminal-/v2 configuration forms then share the existing REST/stream joining behavior. No env, origin, account, allowlist, other product path or earlier replacement correction is changed.


Completed and frozen: tradingagents/web/alpaca_readonly.py line103, exactly +1/-1 product line, net0; zero test changes, incremental score -1, cumulative score -566. Both existing REST and stream callers consume the corrected shared base. No tests, imports/probes, verification, browser/runtime actions, startup/restart, provider requests, research, trades or saved-data/env changes were performed. All other batch source remains frozen. Full handoff: C:/src/TradingAgents/docs/lean-in-memory-source-handoff-20261017.md.


## Observed stale account-integration sentence — 18 October 2026

USR-ALPACA-CAPABILITY-20261018; root's actual normal-mode browser acceptance found static/index.html line41 still claimed all submissions/cancellations/replacements were disabled. Replace only that paragraph with the actual Nautilus-to-Alpaca account/order integration and explicit human approval/submission/cancel/replace authorization wording. Exactly +1/-1 product line, net0; zero test changes; incremental score -1, cumulative score -567. No state/feature/transport changes, tests, imports/probes, verification, runtime/browser actions, broker calls, research, trades, env or saved-data changes. All earlier source remains frozen; this copy-only correction is frozen for root's HTML refresh. Full handoff: C:/src/TradingAgents/docs/lean-in-memory-source-handoff-20261017.md.


## USR-ORDER-BLOCK-DEFAULT-20261018 source batch

Before-edit authority: direct user instruction recorded at C:/src/printerv2/evidence/tradingagents-build-roadmap.md:13 makes the ordinary account-wide new-order default unblocked and requires saved explicit choices to survive normal reload/restart. Update only admission default/snapshot/check fallbacks, service health/current trading_paused metadata and the existing UI missing-value fallbacks. Preserve explicit saved true; never reset the field on every read/restart. CommandAdmission.recover already preserves the saved choice, so its fresh reconciliation/no-replay behavior needs no edit. Per-order exact approval/admission/explicit dispatch, source/account/terms/policy/expiry validation and user block controls remain. Restore/corrupt-store protections are separate explicit recovery semantics and remain unchanged. Root alone owns clearing the current saved flag through the authorized existing control and browser/restart acceptance. This dev chat performs no current-state, runtime, server or broker action.


Completed together and frozen. DEFAULT.new_orders_blocked and all ordinary backend missing-value fallbacks are false. Snapshot setdefault preserves either saved boolean. Service trading_paused now mirrors the commands record with the same false fallback instead of always reporting true; health agrees. Existing header/health/single-order admission/command/basket controls interpret a missing block value as false while retaining explicit true. No saved choice is overwritten by these source edits; normal recover still requires reconciliation and retains uncertain commitments without resetting the user block.

| File | Edit-buffer +/- | New edited block starts |
| --- | --- | --- |
| tradingagents/web/admission.py | +6/-6 | 13, 109, 254, 360, 405, 494 |
| tradingagents/web/service.py | +2/-2 | 338, 425 |
| tradingagents/web/static/app.js | +3/-3 | 203, 646, 1049 |
| tradingagents/web/static/command-controls.js | +2/-2 | 5, 14 |

Product total +13/-13, net0; zero tests; incremental added-line score -13; cumulative score -580. Counts/locations are from edit buffers, recorded in .runtime-stage/order-block-default-accounting-20261018.json. Every change implements USR-ORDER-BLOCK-DEFAULT-20261018; existing exact-order human approval and execution validation are unchanged, as are invalid-record checks and unrelated recovery behavior. The current saved flag has not been cleared by this chat. No tests, product imports, syntax/build probes, verification, browser/runtime/server/startup/restart/actions, installs, research, approvals, admission, broker reads/mutations, env or saved-data writes were performed. Root owns the current unblock, normal restart and actual-browser verification. Full handoff: C:/src/TradingAgents/docs/lean-in-memory-source-handoff-20261017.md.


## Consolidated workflow simplification — 18 October 2026

Before shared edits: complete the ten confirmed corrections as one source batch: (1) session-audited pause/resume without typed identity or rationale; (2) readable exact approval with automatically supplied revision/hash and derived expiry; (3) internal reservation on explicit approved submission, including replacements and one explicit next basket leg; (4) exact one-use cancel/replace authorization with server-derived expiry from the entered approval lifetime; (5) observed-order numeric fee ceilings and applicable saved review values, without invented financial defaults; (6) ordinary authoritative reconciliation automatically clears recovery when genuinely complete and restore preserves intended launch mode; (7) retryable quote refresh and scoped rate limiting with research independent of broker verification; (8) immutable report provenance separate from explicitly declared/enabled current evidence dependencies; (9) remove arbitrary native history ceilings, scope current account imports, official closed-history selection and per-instrument ordering, and separate reported cost differences; (10) remove provider-access attestation and false disabled/fee-blocker metadata or copy. Requirement authority: C:/src/printerv2/evidence/tradingagents-build-roadmap.md:5–19,105–111,176,184–193,234–250,262–264,291; USR-ALPACA-CAPABILITY-20261018 and USR-ORDER-BLOCK-DEFAULT-20261018. Parent/coordinating chat owns grouped checks and rollout; this implementation batch performs no tests, imports/probes, post-edit verification, browser/runtime/provider/trading/research actions or saved-data changes. Starting cumulative product score -580.


Product source frozen for coordinating-root grouped acceptance and independent source review. Shared integration is complete; no further product edits are pending in this batch. Freeze was announced before completing documentation. No active implementation blocker remains. The human's migration/restart approval was received; this implementation chat did not perform migration or restart.

### Ten-item disposition

1. Pause/resume: ordinary controls send only the selected action/block state and current revisions. The backend records the actual local application session instance, action and timestamp; optional notes are actual input, not generated explanations or a claimed personal identity. Missing new_orders_blocked remains false, saved true remains preserved, and normal recover does not reset the saved choice.
2. Approval: readable exact terms remain displayed. Approve automatically supplies the actual proposal revision, policy revision, terms digest and reviewed evaluation binding; the server still validates them and expected record revisions. The manually transcribed APPROVE string is removed. The actual saved proposal rationale is reused unless a separate optional note is entered. The entered positive approval lifetime determines the server expiry; there is no second timestamp entry and approval never submits.
3. Reservation/submission: explicit Submit with approval_id invokes existing admission/revalidation and dispatch-intent code within one existing database transaction before requesting native I/O. Duplicate approvals/commands cannot acquire another intent. Existing admitted command IDs remain usable. A separately approved replacement reserves internally in the same action transaction while retaining both commitments until authoritative supersession/rejection. The first explicit Submit next approved leg reserves all exact basket legs and records only the first leg's intent in the same transaction; subsequent legs require another explicit request and authoritative dependency completion. There is no automatic basket dispatch, sale-credit funding, replay or timeout release.
4. Cancel/replace: the server binds one exact command, broker order, action UUID, current initiating session and timestamp to a one-use transport boundary. Expiry comes from the applicable already-entered approval lifetime; replacement is additionally bounded by its current separately approved terms' expiry. Cancel does not depend on reviving an expired submit approval. Exact native-transition proof no longer demands a non-empty optional note; every actual action/account/instrument/client/venue/epoch/expiry/pre-I/O check remains.
5. Review inputs: numeric fee controls are labelled with actual observed broker order identities. Applicable explicit saved constraints, policy freshness and exact LIMIT price are reused. MARKET ceilings, unknown fees, risk choices and tolerances receive no invented financial defaults. Explicit fee ceilings continue to participate in account-wide commitments and review.
6. Recovery: ordinary runtime observations call the existing read-only reconcile path. Complete current broker/native observations, including an empty account, can clear recovery_required automatically. Unknown transport outcomes, missing current native confirmation, mismatched account identity and genuine reconciliation gaps remain blocked with commitments retained. Restore promotion preserves the actual CLI launch browse_only choice instead of forcing browse-only. No dispatch/replay is introduced.
7. Retry/scope: a transient quote failure no longer latches the visible refresh off indefinitely. The ordinary refresh action can retry; 429 timing is associated with the failed operation/provider instead of disabling unrelated account/research work. Research UI enablement is independent of broker verification. No research was run.
8. Evidence/provenance: linked saved report keys do not invent current adapter requirements such as sentiment. Original exact run/revision/report/date/result/report hashes remain bound in saved immutable proposal terms; the existing report resolver still verifies the exact linked artifact when saving the draft. Current inputs follow explicit decision scopes and enabled policies. Ordinary human orders no longer require an unconditional 252-session history gate; explicit history dependencies and actual enabled correlation calculations still require their real source coverage. No new per-snapshot resolver gate was added.
9. Native history/current account: removed arbitrary lifetime/page-fill and 200-parent ceilings; retained actual pagination/identity/cursor validation and the existing observation timeout. Native fill/parent import work is scoped to current broker positions/open orders, native open positions/orders and unresolved/admitted command symbols. Unrelated closed-symbol observations remain retained as historical_source_only reporting context. Existing official closed-history selection precedes interleaving checks, which are per instrument. Exact reported cost differences remain visible as native_cost_comparison_gap/reporting_gaps while exact account, quantity, direction, cash, order identity/type/TIF/price checks still determine readiness. No tolerance, synthetic fill or invented zero commission was added.
10. Truthful capability/provider copy: AlphaVantage access follows the real configured key/provider response, with no overview_access_confirmed checkbox or job-payload attestation. Unknown actual fees are disclosed separately rather than imposing an unconditional blocker after a finite explicit fee ceiling is supplied. Reconciliation copy and broker_mutations_enabled reflect actual session capability. Research context explicitly grants no order authority without falsely saying all broker writes are disabled.

Consumer integration: approval_review consumes the changed mandatory/supplementary sets; explicit history remains accepted by investor draft validation, while policy_evaluation retains genuine enabled-correlation history requirements. Command controls and proposal controls submit the real revisions/hash/approval IDs consumed by service/admission; replacements retain existing admitted-command compatibility. Native account projection maps economic cost discrepancies into separate reporting fields and leaves import_error for actual source/identity/quantity/lifecycle gaps, so existing instrument, impact and policy consumers do not re-impose the removed cost-equality gate. The backend job payload's unused access-attestation field and obsolete quote-latch initializer were removed. This was source implementation/consumer reasoning, not post-edit verification.

### Exact product accounting

| File | Added | Removed | Responsibility |
| --- | ---: | ---: | --- |
| tradingagents/web/admission.py | 75 | 44 | Session audit, derived authority expiry, transactional approved submit/replacement/basket intent |
| tradingagents/web/service.py | 33 | 23 | Shared UI contracts, automatic read-only reconciliation, capability metadata |
| tradingagents/web/server.py | 4 | 1 | Preserve intended launch mode after restore promotion |
| tradingagents/web/market_history.py | 1 | 1 | Remove obsolete access-attestation job field |
| tradingagents/web/evidence_requirements.py | 8 | 23 | Explicit decision/policy current-input requirements |
| tradingagents/web/approval_review.py | 11 | 10 | Conditional explicitly required history |
| tradingagents/web/stock_evidence.py | 1 | 4 | Provider response establishes access |
| tradingagents/web/investor.py | 5 | 4 | Fee disclosure and supported explicit evidence scopes |
| tradingagents/web/nautilus_worker.py | 28 | 17 | Relevant-symbol import and remove arbitrary history ceilings |
| tradingagents/web/native_recovery.py | 2 | 10 | Official selection first; per-instrument interleaving |
| tradingagents/web/account_projection.py | 20 | 16 | Exact cost reporting separated; optional action note proof |
| tradingagents/web/execution_lifecycle.py | 1 | 1 | Optional action note does not negate actual native authority |
| tradingagents/web/static/app.js | 49 | 36 | Readable exact approval, numeric fee fields, retry/rate-limit and evidence/provider copy |
| tradingagents/web/static/command-controls.js | 15 | 10 | Explicit submit/internal reservation, exact replacement selection, optional notes and basket submit |
| **Total** | **253** | **200** | **14 product files; net +53; zero test changes** |

Counts come from editing buffers and helper handoffs, not a post-edit diff/check. Incremental product score -253; cumulative score -833 from the previous -580. Root-owned edit-buffer block starts/accounting are in .runtime-stage/workflow-simplification-accounting-20261018.json; source-before buffers are in .runtime-stage/workflow-simplification-source-before-20261018. Existing unrelated dirty checkout changes were preserved. This documentation is the fifteenth changed batch file and is not product-code score.

Deliberately retained genuine limits: unknown commission or incomplete historical native lifecycle for a currently relevant symbol can still withhold that import; same-instrument grouped-order interleaving can still require source resolution. Unknown order outcomes/current native gaps retain commitments; no time-based release or blind retry. Unsupported fractional/short instruments remain observation-only. Actual enabled policy, relevant evidence/freshness, current account, finite reviewed price/fee limits, exact human approval, exact identity and one-use transport checks remain. Source completion is not a successful-order, deployment or profitability claim.

No tests, test edits, product imports, syntax/build probes, post-edit verification, browser/runtime/server/provider actions, research runs, approvals/admissions/actual order actions, migration/restart/deployment, installations, environment/settings or saved-data changes were performed by this implementation batch. The coordinating root now owns one grouped check/acceptance phase and independent review against this frozen source, under the applicable human authorization. Full handoff: C:/src/TradingAgents/docs/lean-in-memory-source-handoff-20261017.md.

Helper edit-buffer locations were added to the consolidated accounting record after their final handoffs; counts and frozen product source did not change. Native worker starts:239,324,362,412,556,565; native recovery:12,17,59; account projection:29,40,49,89,110,132; execution lifecycle:64. UI app starts:23,105,220,221,295,296,680,686,722,734,892,1015,1024,1053,1065,1078; command controls:2,4,14,18,19,20,32,34. Source remains frozen, cumulative score -833.


## Independent review correction — W5, W8 and W3/W6 — 18 October 2026

Before edits: exactly three review cases plus directly related stale copy, per coordinating root and C:/src/printerv2/evidence/workflow-gate-audit-20261018.md. W5: reseed cached review constraints when proposal revision, terms hash, current policy revision or active store identity changes; retain unsaved edits within the same identity; reuse only applicable existing explicit inputs and exact LIMIT terms. W8: expose the already-supported explicit history decision dependency and describe account/quote, selected inputs/enabled policy and immutable saved research provenance truthfully; align Refresh and internal reservation on explicit Submit wording. Blocking W3/W6: change when automatic readiness reconciliation runs using the existing recovery_required flag; a healthy current-process pending command must not manufacture its own recovery block. Keep ordinary source/approval observations, startup/native restart/genuine unknown recovery, commitments, conflicting admission checks and all existing per-command/native/one-use transport checks. No new recovery framework, blanket in-flight exemption, replay or new product feature. No tests, runtime/server/browser/provider/research/order actions. Starting score -833. Root owns grouped acceptance/review after the complete source freeze.


All three review cases and directly related stale copy completed together; product source frozen. Freeze was announced immediately after the two product files were saved, before this prose/accounting handoff. No remaining product edits are pending for this correction batch.

W5 disposition: approvalForm now compares a cached identity containing active store_generation, proposal ID, proposal revision, exact terms hash and current policy revision on every access. A changed identity reseeds the form; same-identity unsaved input remains untouched. Prior saved approval constraints and bound review constraints are inherited only for the exact applicable proposal revision/hash/current policy revision. Exact saved LIMIT terms supply the reseeded limit ceiling, so revising the same proposal from LIMIT100 to LIMIT120 cannot retain the old100 cap. Store-generation changes after restore invalidate the old cached identity. MARKET ceilings, fees and tolerances still have no invented financial default.

W8/copy disposition: history is now included in the existing explicit decision-input checkbox list, matching the already-supported backend scope. The editor explains mandatory account/actual quote, explicit selected inputs and enabled policy dependencies, and saved report provenance without mandatory adapter reruns. Approval remains separate from submission; Submit performs internal reservation. The quote-failure message names the actual Refresh control. Existing overview, order-page, broker blotter and command-activity statements now describe exact approval plus explicit Submit/internal reservation instead of requiring a separate Admit action.

Blocking W3/W6 disposition: DeskService._observe_runtime invokes the existing full admission.reconcile only while the durable recovery_required flag is already true. Otherwise it performs existing observe_current source/approval checks. Therefore the healthy current-process command's own queued/pending native observation no longer calls the full restart/unknown rebuild that classifies dispatch_intent/submitting/replace_pending as an unresolved recovery gap before the first one-use transport attempt. Startup recovery is still latched by recover; genuine outcome_unknown explicitly latches recovery in ExecutionLifecycle.record_pending; native-process confirmation loss keeps its existing recovery handling. Existing full reconciliation and genuine-gap behavior are unchanged. Conflicting admission checks, current source/approval invalidation, retained commitments, exact command/account/policy/expiry/native checks and one-use transport boundary are unchanged. No in-flight-state blanket exemption, new epoch/state framework, auto-dispatch or replay was added. Automatic reconciliation scheduling alone changed; admission.py, execution_lifecycle.py and nautilus_worker.py required no edits.

| Product file | Added | Removed | Edited-block starts |
| --- | ---: | ---: | --- |
| tradingagents/web/service.py | 5 | 1 | 229, 231 |
| tradingagents/web/static/app.js | 13 | 11 | 38, 360, 528, 535, 638, 1025, 1030, 1086 |
| **Total** | **18** | **12** | **2 product files, net +6; zero test changes** |

Edit-buffer accounting: .runtime-stage/workflow-review-correction-accounting-20261018.json. Before-source buffers: .runtime-stage/workflow-review-correction-source-before-20261018. Incremental score -18; cumulative score -851 from -833. This handoff is the third changed batch file and adds no product code. Other source edits were preserved.

No tests, test edits, imports, syntax/build probes, post-edit verification, browser/runtime/server/startup/restart/provider calls, research, approval/admission/order actions, environment/settings or saved application-data changes were performed. Root's earlier successful syntax checks applied to the preceding frozen source, not this unverified correction. Root owns the grouped acceptance and independent review of this newly frozen source. Genuine native commission/current-symbol lifecycle, same-instrument grouping and observation-timeout limitations remain as previously disclosed. Source completion does not claim broker execution or profitability. Full handoff: C:/src/TradingAgents/docs/lean-in-memory-source-handoff-20261017.md.


## Plain order workflow and unsupported setup gates — 18 October 2026

Before edits: direct user authorization relayed by coordinating root: remove jargon and blockers not required by actual user scope, clearly show whether an order can be submitted and its real blockers, preserve Alpaca and exact per-order approval, verify in the browser without new research or trades. Source ownership remains here; root owns spec provenance review, runtime/restart and browser acceptance after all source work is frozen. Starting cumulative product score -851. Initial UI/source mapping: current pause-off copy incorrectly implies readiness; current order controls follow old saved demonstration drafts; unconditional blocker prose, independent-review language and empty basket boilerplate do not represent an actual order's checks. Current roadmap references are supporting evidence only, not blanket authority for agent-authored setup gates; root is auditing provenance against direct user history. Each final gate removal/retention and edit group will be mapped to direct user instruction or confirmed requirement. No tests/test code, product imports, runtime/server/browser/provider/research/order/approval actions, installations, settings or saved application-data changes in this source batch.


### Completed source freeze

All feasible product changes in this batch are saved and frozen; freeze was announced before final documentation. Root owns restart, actual-browser acceptance and independent source review. This implementation chat did not alter the running service, current account/configuration, environment or saved application data. The only development execution issue was an oversized Windows edit-command envelope rejected before process creation; the edits were split into smaller source-edit calls. No product runtime/check was run.

Authority is the current direct user instruction and the physically corrected C:/src/printerv2/evidence/tradingagents-build-roadmap.md, especially its operative lines5–9, browser-only ordinary workflow29, actual supported scope33, configured-rule/cost disclosure115, ordinary shared commitments260, corrected D4/D5 at403–404 and readiness437. The pre-correction document is historical evidence, not authority for the removed gates; root archived it at C:/src/printerv2/evidence/order-readiness-20261018/spec-before.md. This chat did not edit that specification.

### Exact readiness data and control flow

DeskService.investor now returns current_checks for each saved draft by calling the existing approval_review.evaluate with the current runtime, saved policy, ordinary command commitments, saved source artifacts and that order's existing explicit review choices. This is a read-only calculation: no admission transaction/dry-run, resource reservation, permission grant, provider call or second financial engine. Actual LIMIT terms and observed bid/ask/previous explicit BUY bound are normalized by shared execution_costs used by the existing review/policy/admission paths.

The header and Orders page use those current server results plus existing execution capability, account connection, user pause, native reconciliation, actual Alpaca trading_blocked and current approval/command states. They distinguish account-wide reasons from each order's failed server checks and missing/expired/used/invalidated approval. “Not paused” never means ready. A connected, synchronized empty account with zero saved proposals says “No approved order” and offers Create an order; it does not demand a settings questionnaire or render a generic error. A Ready result requires a currently usable exact approval and passing current backend checks; Submit still rechecks on the server.

Orders now renders the plain order workflow before broker observations and older saved demonstration drafts; the latter remain preserved in a collapsed “Older saved drafts” section. Existing actions connect/refresh, refresh account/order status, pause/resume, open the exact saved order for review, approve and explicitly submit. There is no automatic submission. Market closed is a separate informational statement about DAY/regular-session terms, not a new unconditional block. Concrete native sync reasons are attributed to Nautilus/source state; missing commission/grouped-fill limitations are not called broker restrictions.

### Authority-semantic changes and requirement mapping

| Changed or retained gate / edit group | Disposition and current authority |
| --- | --- |
| Global policy-completeness gate | Removed in approval and policy evaluation/impact. Unset optional rules remain stored as unset and are reported “Optional check not configured”; they are not silently disabled or assigned values. Every actually enabled rule still runs with its real required inputs. Direct user correction; roadmap7,115,403–404,437. |
| Compulsory policy notes / manual rationale / saved research prerequisite | Removed mandatory prose for policy changes, rule choices, draft save and reject/defer. Exact order terms and explicit human approval remain. Existing notes and linked report hashes are preserved. Optional fields are labelled honestly. Direct user no-questionnaire/no-invented-barrier instruction; roadmap5–7,29,115,403. |
| Mandatory account-age, evidence-age, quote-age and approval-duration blanks | Removed as prerequisites. Current connected/reconciled account, actual dated bid/ask and actual declared evidence remain checked. A configured positive age/lifetime still applies and an invalid supplied value fails. No arbitrary time tolerance is substituted. Operative roadmap7; D5 at404. |
| Approval validity without a configured numeric TTL | Existing expires_at field remains a string; empty string means no configured clock cutoff. Exact terms/account/policy/relevant source-change invalidation and single-use command identity still constrain authority. Existing configured expiry remains enforced in approval, native sending, exact cancel/replace transition proof and transport boundary; broker DAY/order terminal behavior is unchanged. No reusable blanket approval, replay or numeric default. Direct user exact single-use approval/current recheck requirement; roadmap7,404. |
| Repeated price ceiling | LIMIT uses the exact saved limit; MARKET uses the observed side quote unless an existing explicit BUY bound applies. A configured BUY bound is checked against the observed ask; it does not guarantee a market fill. No separate SELL ceiling or compulsory new price setting. Operative roadmap7 and D5 at404; actual whole-share BUY/SELL scope33. |
| Per-order fee / per-broker-UUID fee paperwork | Removed blank fee-cap blockers and the working-order UUID form. Existing explicitly configured amounts still participate in checks/reservations. Missing fee amounts remain None/unknown in records/results; math adds only known/configured components and disclosures state that unknown actual fees are excluded, never assumed zero. Working quantities/price terms, cash, holdings and current broker/source facts remain required. Direct user/spec correction; roadmap7,115,260,404. |
| Shared commitments and uncertain outcomes | Preserved current atomic reservation, duplicate-command protection, retained principal/known-cost commitments, exact sellable-share/funds checks, conflicting pending/unknown outcomes and no timeout release/blind resubmission. Native/recovery arithmetic now tolerates an explicitly unknown fee component without manufacturing a fee amount or releasing principal/quantity. Roadmap7,260 and existing direct no-replay instruction15. |
| Every quote-event hash invalidates approval | Removed quote/tick events from the account-version component of the evaluation binding. Current quote validity, configured freshness/spread/liquidity/price bounds and enabled risk checks still execute on every current review and before transport through existing authority observations. Actual account/position/order/policy/terms/required-artifact changes remain bound. Receive/event timestamp changes alone are not a material price policy. Operative roadmap7 and D5 at404; current root material-change steering. |
| Real Alpaca trading_blocked | Added the supplied boolean to actual backend review and checked_observation immediately before sending, and to visible readiness. An absent field is not invented as a restriction. Cancellation retains its existing exact selected-order path. Preserve real broker restrictions: roadmap7,33,437; explicit root account-field finding. |
| Separate Check click / second approver | Check order remains available, but explicit Approve runs the existing server review itself before recording exact approval; no compulsory preceding click or second person is introduced. Approval never submits. Delivery independent review remains outside the investor workflow. Direct user instruction and roadmap9. |
| Plain workflow/readiness display and direct actions | Replaced Durable command activity, Account order block, Basket command coordination and read-only identity reconciliation main-flow labels with Place an order, Pause new orders, Basket orders and Refresh account and order status. Removed unconditional blocker essay and empty basket boilerplate. Technical source records/history remain available under disclosure. Current user plain status/action request; roadmap5,9,29,437. |

Single-use submit semantics are unchanged: approve records exact authority only; explicit Submit rechecks, atomically reserves resources/dispatch intent, and invokes native dispatch once. Existing admitted commands, cancel/replace identity and separately approved replacement terms remain compatible. The prior healthy-observer race correction and default-unpaused/saved-pause behavior are preserved. No account/endpoint restriction, configured broker endpoint change or new capability mode was added.

### Exact edit-buffer accounting

| Product file | Added | Removed | Edited-block starts |
| --- | ---: | ---: | --- |
| tradingagents/web/policy_evaluation.py | 16 | 13 | 6, 39, 64, 69, 92, 96, 123, 144, 167, 254 |
| tradingagents/web/execution_lifecycle.py | 3 | 3 | 34, 67, 90 |
| tradingagents/web/account_projection.py | 1 | 1 | 96 |
| tradingagents/web/recovery.py | 2 | 1 | 377 |
| tradingagents/web/service.py | 11 | 1 | 403, 408, 416 |
| tradingagents/web/investor.py | 14 | 13 | 55, 65, 79, 162, 182, 202, 234 |
| tradingagents/web/static/index.html | 1 | 0 | 37 |
| tradingagents/web/static/command-controls.js | 34 | 4 | 4, 28, 30, 33, 38, 68 |
| tradingagents/web/static/app.js | 23 | 18 | 293, 295, 535, 636, 1017, 1049, 1055, 1059, 1063, 1074, 1091, 1096, 1110, 1342 |
| tradingagents/web/approval_review.py | 20 | 16 | 8, 34, 47, 49, 62, 64, 82, 107, 110, 120, 123, 137 |
| tradingagents/web/admission.py | 33 | 45 | 10, 60, 113, 120, 122, 126, 149, 192, 209, 210, 211, 223, 284, 287, 306, 316, 325, 336, 420, 512, 647 |
| **Total** | **158** | **115** | **11 product files; net +43; zero test changes** |


Incremental product score -158; cumulative score -1009 from -851. Counts are computed from retained edit buffers, not a post-edit diff/test. Exact accounting is .runtime-stage/plain-order-workflow-accounting-20261018.json; before-source buffers are .runtime-stage/plain-order-workflow-source-before-20261018. This handoff is the twelfth changed batch file and is not product-code score. Source freeze remains in effect.

Deliberately retained genuine limitations: actual unsupported account/instrument/native mapping, missing current-symbol commission/lifecycle proof or same-instrument grouped-fill import incompatibility can still block native synchronization; the UI now shows the actual supplied reason. They are application/source integration limits, not assertions that Alpaca itself forbids trading. Unknown broker order outcomes remain unresolved with retained commitments. Market order prices and unknown fees are estimates/unknowns, not fixed or zero costs. Current server-ready state is an observation, not a promise of a broker fill.

No tests/new tests, product imports, syntax/build probes, runtime/server/browser/startup/restart/provider calls, research runs, per-order approval/admission/submission/cancel/replace, installation, configuration/environment change or saved application-data write was performed. No execution or browser-success claim is made for this frozen batch. Root now owns grouped acceptance against the corrected spec and real browser, preserving the no-trades/no-research instruction. Full handoff: C:/src/TradingAgents/docs/lean-in-memory-source-handoff-20261017.md.


## Approval binding and matching-review correction — 18 October 2026

Before edits: consolidate exactly the two confirmed independent-review defects and directly related plain-language copy. (1) Bind authoritative account identity/permissions, cash, holding identity/quantity/cost and order economics independently of valuation-only marks, including duplicated valuations in reconciliation; retain current valuations in existing configured-policy checks and invalidate real failed checks/economic/permission changes. (2) Choose an eligible approval matching the current exact evaluation binding, so an older approval under different optional choices cannot mask a later matching approval. Remove the unsolicited empty-account/questionnaire sentence and simplify command-controls approval/submit/cancel/replace wording without changing behavior. Authority: latest explicit user instruction relayed by coordinating root and corrected C:/src/printerv2/evidence/tradingagents-build-roadmap.md:5–9,246–252,258–260. Preserve other agents' work, source records, configured account/endpoints, exact approval and pre-submit validation. Starting cumulative score -1009. No features/tests/runtime/provider/research/approval/admission/order actions or environment/saved application-data changes. Root owns actual browser acceptance and independent review after full source freeze.


Both confirmed review defects and the directly related copy changes are complete together. Product source is frozen; freeze was announced before final handoff prose. No additional production edits are pending in this correction batch.

1. Valuation-only approval churn: account_version now selects the authoritative account identity/status/currency/cash/trading permission/multiplier/shorting fields; position asset identity/class/exchange, total/available quantity, side, average entry cost and cost basis; ordinary full order state; native/broker cash and actual reconciliation status/gaps/completeness; and the configured endpoint. It no longer hashes account equity, long market value, mark-dependent buying power/margins, position current marks/market value/unrealized changes, or duplicated valuation/reporting fields in reconciliation. Positions and orders are sorted by stable identity so an observation's row ordering is not an economic change. Existing order binding_native handling for a proven exact pending native action and ordinary timestamp filtering remain intact.

This is a binding projection only. Actual current valuations still flow unchanged into approval_review/policy_evaluation; enabled concentration/loss/scenario and other configured checks still run and a failed check still revokes approval. Actual cash, quantity, position cost, order identity/terms/status, account permission or reconciliation failure remains binding. Exact account/terms/policy/required artifact references and configured expiry/freshness remain checked. No prices, source records, native observations, policy values, reservations, endpoints or transport logic were modified. Requirement authority: latest user instruction to remove unsupported blockers while preserving exact approval and real Alpaca/Nautilus behavior; corrected roadmap7,246,250–251,258–260. This closes the duplicate account/reconciliation valuation paths rather than masking only the top-level mark.

2. Matching current review: orderReadiness first collects eligible approvals using the existing approval/command states, then selects an eligible approval whose evaluation_binding_sha256 equals the current exact server evaluation binding. An older still-eligible approval under different optional review choices cannot hide a newer matching approval. The redundant mismatch-after-first-selection branch was removed. When eligible approvals exist but none matches, the UI says approved conditions differ from the current checks and offers the existing review action. Revoked/expired/used approvals and already-sent commands do not become eligible. Requirement authority: latest explicit order-specific readiness request and corrected roadmap9,249–251.

3. Plain copy: removed the unsolicited empty-account/questionnaire sentence. The command-controls explanation now gives actual steps: review and Approve, Submit to send to Alpaca, Cancel the selected working order, and review/approve new terms before Replace. The unconfigured-expiry approval label now describes approved terms and possible renewed review without single-use/configured-expiry jargon. Configured expiry is still shown when present and remains enforced. No authority or trading capability changed through copy. Requirement authority: latest plain-language user request and corrected roadmap5,9,29.

| Product file | Added | Removed | Edited-block starts |
| --- | ---: | ---: | --- |
| tradingagents/web/admission.py | 9 | 1 | 42 |
| tradingagents/web/static/command-controls.js | 4 | 5 | 13, 15, 23, 29 |
| **Total** | **13** | **6** | **2 product files, net +7; zero test changes** |

Edit-buffer accounting: .runtime-stage/approval-binding-review-accounting-20261018.json. Retained before-source buffers: .runtime-stage/approval-binding-review-source-before-20261018. Incremental score -13; cumulative score -1022 from -1009. Existing unrelated edits were preserved. This handoff is the third changed batch file and adds no product-code score.

No tests, test code, product imports, syntax/build probes, post-edit verification, runtime/server/browser/provider calls, research, per-order approval/admission/submission/cancel/replace, installations, settings/environment or saved application-data changes were performed by this correction batch. Root owns grouped runtime/browser acceptance and independent review of the frozen source. Source completion does not establish broker execution or profitability. Full handoff: C:/src/TradingAgents/docs/lean-in-memory-source-handoff-20261017.md.


## Browser-observed broker-order copy correction — 18 October 2026

Before edit: root's actual browser acceptance found the remaining broker-order-list copy cluster describing observations, receipts, resource reservation/dispatch and engine state. Latest direct user plain-language request and corrected roadmap5,9,29 authorize replacing only this cluster with Open orders at Alpaca, actual source/update time or unavailable, explicit older saved-data distinction, the plain Review/Approve/Submit-to-Alpaca steps and Connect your account to see current orders. Preserve all source/date/error conditions, actual error contents other than the exact identified generic engine-state fallback, order data and behavior. No other UI or runtime/test action is authorized in this copy correction. Starting score -1022.

Completed and frozen: tradingagents/web/static/app.js, edited-block starts528 and531, exactly +2/-2 product lines, net0; zero test changes. Heading is Open orders at Alpaca. The existing source and observed_at values remain escaped and displayed, with Last update/Unavailable and current/incomplete/disconnected older-data distinctions. Saved order history is explicitly separate. The paragraph now says Review and approve the exact order, then choose Submit to send it to Alpaca. Only the exact generic Start Nautilus to load engine state error is displayed as Connect your account to see current orders; every other actual error still follows the unchanged existing error branch and escaping. The existing unavailable empty-list branch now says Current orders are unavailable, without claiming the list is empty. All flags, row data, filters, pagination, timestamps, error conditions and execution behavior are unchanged.

Edit-buffer accounting: .runtime-stage/broker-order-copy-accounting-20261018.json; before-source buffer: .runtime-stage/broker-order-copy-source-before-20261018/tradingagents/web/static/app.js. Incremental score -2; cumulative score -1024 from -1022. This handoff is the second changed file and adds no product-code score. No tests, product imports, syntax/build probes, post-edit verification, browser/runtime/server/provider/research/approval/admission/trading/configuration or saved application-data actions were performed. Root can reload the changed static asset for actual browser acceptance; no backend restart is needed. Source remains frozen. Full handoff: C:/src/TradingAgents/docs/lean-in-memory-source-handoff-20261017.md.


## Rest-of-app consolidated R01–R13 correction batch — 18 October 2026

Before edits: implement all thirteen confirmed source-audit corrections in C:/src/printerv2/evidence/rest-app-20261018/correction-batch.md as one production batch under the latest direct user request. That ledger supplies exact requirement citations, official native APIs, simulation-fee inference boundaries and preservation requirements. Starting cumulative score -1024. R01–R05 cover optional notes, truthful basket/research state and universal workload review; R06–R09 unify actual order-price evidence, exact local/broker commitments, predecessor-bound replacement alternatives and reductions in exposure; R10–R13 repair the actual native chronological fill/replacement path using official model/events/report interfaces, canonical execution identity, raw-fee preservation and explicitly modelled direct-paper US-equity commission only where applicable. Preserve previous approval/readiness/default-pause fixes, other agents' edits, configured account/endpoints, ordinary store/event structures and real financial/source constraints. No new engine/crash project, tests/scaffold, runtime/provider/research/approval/admission/trading/configuration or installation actions. Root owns grouped browser/runtime acceptance and independent sign-off after the full source freeze.

    
## Consolidated R01-R14 source freeze - 18 October 2026

All sixteen production files in this batch are now frozen for coordinator-owned independent review and grouped runtime/browser acceptance. Authority and requirements remain C:/src/printerv2/evidence/rest-app-20261018/correction-batch.md and the corrected roadmap; R14 is included in the original R01-R13 scope entry above.

R01/R02 preserve optional supplied notes, requiring no new prose for reporting preferences or basket reject/defer. Basket preview/save rationale remains required by spec117. R03 corrects saved basket state/copy and shares ordinary proposal unknown-cost handling. R04 future research context is advisory with human quantity, exact approval and explicit submission; existing research is untouched. R05 every selected research count passes through the workload review, with unavailable cost estimate stated honestly; no run was started.

R06 uses investor.price_evidence/execution_costs across preview, basket, approval, policy, admission and pre-I/O: exact LIMIT terms supply the price bound; MARKET uses dated side quote or last trade with an estimate/source label. Configured spread, liquidity, session and age checks remain. R07 investor.working_commitments matches exact local/broker identities, retains local reservations, estimates supported external MARKET BUY commitments from available source evidence, reserves SELL shares and blocks genuinely missing required economics. Native market/instrument paths include open-order-only symbols.

R08 proposals bind replacement order/client/account/symbol/side, filled_quantity and an exact broker order_version. The shared validated_replacement helper and policy use conservative alternative old/new reservations, preserving unrelated commitments; total quantity includes existing fills. The native adapter rechecks matched predecessor ID and native filled quantity immediately before PATCH. Its pre-I/O checks distinguish only the exact authorized, not-started local pending action from uncertain/started outcomes. R09 SELL/full close reduces resulting configured exposure; expected sale proceeds do not fund BUYs. R14 unconditional account_version excludes reporting-only cost basis and native diagnostics while retaining actual authority/economics; configured dependent cost checks still use current costs.

R10 alpaca_reports.fill_commission resolves explicit broker commission, exact linked evidence, then the documented direct-paper US-equity simulation model only for the supported authenticated account/origin/instrument scope. Raw missing actual commission stays null; native_fee records modeled input, amount, scope/source and documentation separately. The same resolver feeds historical and live native Money, with retained receipt/identity/economics checks. Custom/live origins and unsupported instruments retain genuine missing-fee failures; configured endpoints are never disabled or rewritten. Native applied comparisons include account and normalized execution identity.

R11 canonicalizes historical timestamp::UUID and stream UUID identity while raw activity IDs, pagination tokens, messages and source receipts remain intact. Native reports, cache matching, fee links and proof use the canonical identity. Cached proof still checks actual account/order/client/instrument/side/quantity/price/time and resolved fee economics; conflicting duplicates remain errors.

R12 the adapter no longer forwards grouped mass status reports. Initial connection, poll, refresh and generated-observation paths call _apply_observation: initialize real source order identities with official OrderFactory/cache/account events; apply actual FillReports globally by event time through the official single-report interface; wait for exact native event confirmation; check real cumulative quantities before final order reports and native quantities before position reports. Native account cash is reasserted from the source observation after actual history application. No synthetic executions, invented filled_qty, custom position ledger, native-library patch or new engine was introduced. Mass status objects remain report inventories only. Unsupported/conflicting observations retain explicit gaps.

R13 fetches and validates both replacement-chain directions, identity/economics/chronology and cumulative fills. Confirmed predecessor remainder is superseded only with its source successor available. The native root client identity and actual venue transitions retain prior fills; transitions occur when the next actual successor fill/final observation needs them, so interleaved predecessor/other-order fills keep global ordering. account_projection's single identity comparison now accepts that adapter-derived root client identity after chain validation; all other comparisons remain.

| File | Edit-buffer +/- | Edited block starts at freeze |
| --- | --- | --- |
| tradingagents/web/native_types.py | +6/-3 | 55, 62 |
| tradingagents/web/native_recovery.py | +2/-1 | 9, 47 |
| tradingagents/web/alpaca_reports.py | +63/-11 | 6, 13, 117, 148, 155, 160, 168, 172 |
| tradingagents/web/nautilus_v1.py | +1/-4 | 51, 106 |
| tradingagents/web/account_projection.py | +1/-1 | 72 |
| tradingagents/web/nautilus_worker.py | +161/-110 | 32, 34, 36, 129, 247, 260, 277, 301, 304, 310, 313, 326, 335, 384, 389, 394, 402, 429, 430, 438, 441, 442, 458, 465, 481, 487, 519, 629, 637, 663, 669, 796 |
| tradingagents/web/execution_lifecycle.py | +29/-17 | 15, 18, 187, 293, 326, 328, 350, 352, 369, 374, 422, 468, 529 |
| tradingagents/web/investor.py | +161/-29 | 55, 75, 80, 230, 245, 252, 258, 281, 306, 333, 364 |
| tradingagents/web/approval_review.py | +15/-39 | 8, 51, 58, 60, 74, 105 |
| tradingagents/web/policy_evaluation.py | +69/-84 | 6, 30, 34, 37, 38, 55, 59, 71, 80, 84, 95, 98, 106, 150, 161, 191, 203 |
| tradingagents/web/admission.py | +43/-69 | 10, 43, 48, 175, 217, 273, 274, 287, 291, 301, 373, 473, 500, 565 |
| tradingagents/web/baskets.py | +22/-45 | 9, 32, 59, 72, 75, 89, 103, 118, 121, 161, 192 |
| tradingagents/web/decision_journal.py | +0/-2 | 113 |
| tradingagents/web/service.py | +6/-7 | 130, 644, 650 |
| tradingagents/web/static/app.js | +14/-7 | 133, 607, 671, 1017, 1062, 1091, 1115, 1170 |
| tradingagents/web/static/command-controls.js | +6/-6 | 18, 23, 29 |

Product total +599/-435; net +164. Zero test changes. Incremental score -599; cumulative score -1623. Exact accounting: .runtime-stage/rest-app-accounting-20261018.json. Approval_review, policy_evaluation and command-controls original buffers were reconstructed from the worker's retained exact pre-edit reads; other baselines were retained directly during editing.

Known retained limitation: the existing Replace authority route requires a locally managed command. Imported/external broker orders remain visible and count toward commitments; this batch does not invent a new external-order ownership/Replace command route. No compatible retained native replay entry point is known; the old batch1 replay driver is stale and was not adapted. No new test/harness was created and no retained command is claimed compatible without acceptance.

No tests, product imports, syntax/build probes, post-edit checks, browser/runtime/server/provider/research/approval/admission/trading actions, installation, environment/configuration edits, migration or saved-account-data mutations were performed in this batch. The asynchronously answered old JSON migration approval did not trigger any migration, restart or saved-state mutation; the current coordinator retains restart ownership after source freeze. Normal capability and configured state have not been changed.

Official source basis, accessed 18 October 2026: https://docs.alpaca.markets/us/docs/paper-trading and https://alpaca.markets/algotrading support only the labelled simulation-fee inference described in the scope ledger, not observed actual zero; https://docs.alpaca.markets/us/docs/account-activities and https://docs.alpaca.markets/us/docs/websocket-streaming provide the source identity formats; https://docs.alpaca.markets/us/reference/patchorderbyorderid-1 documents replacement reservation/race behavior. Installed official Nautilus 1.231.0 client.pyx single-report/event interfaces, common/factories.pyx OrderFactory and cache/cache.pyx add_order are used without modification.


## Consolidated C01-C05 review-correction batch - 18 October 2026

Before edits: implement C01-C05 from C:/src/printerv2/evidence/rest-app-20261018/review-corrections.md under its cited corrected-roadmap requirements. C01/C02 use the actual registered desk strategy owner and official native transitional events; C03 extends existing exact human action authorization to supported imported orders while preserving external provenance; C04 corrects basket cost wording; C05 preserves saved pause choice/default False through restore while retaining stale-approval invalidation and real reconciliation/unresolved-history checks. Starting score -1623. All R01-R14 edits remain. Running root-owned port8098/PID34840 stays untouched. No tests, checks, product imports, runtime/browser/research/approval/broker/restore/configuration/install/migration actions. Existing data, installed native libraries and root-owned service are not changed. Worker owns the existing UI/authority files plus decision_journal; root owns native/action boundary alignment, account_projection and recovery.py. Freeze the combined batch before coordinator verification.


### Combined C01-C05 source freeze

All required source dependencies are saved and frozen together. R01-R14 remains preserved. No source verification was performed here.

C01: imported orders use the actual registered Observer.order_factory, registered before client connection; broker-observation provenance remains in tags/source records. Imports and human orders therefore share the desk strategy used by official native netting.

C02: actual pending observations use official OrderSubmitted/OrderPendingCancel/OrderPendingUpdate events. SUBMITTED is seeded only from INITIALIZED; already exact states are preserved. Pending-new does not pass through a final status report that invents acceptance. The readonly missing venue ID remains null; exact official cache venue indexing is exposed separately and strictly checked by projection/action boundaries. Native fill account proof uses consistent actual native event account identity.

C03: supported imported orders use existing human Cancel/Replace authorization, actual broker/native identities/version/filled quantity and ordinary transport proof. External records explicitly have no original app submission approval; UI, journal and record-integrity consumers support that provenance. Unknown MARKET BUY principal can remain null on cancellation, including commitment retention/restore. LIMIT retains the validated root-client alias and official OrderUpdated path.

Required MARKET completion: confirmed broker replacements are distinct native MARKET successors with their actual client/venue IDs and the same desk strategy. Deduplicated exact actual executions establish S (successor sum) and A (validated ancestor sum), against raw broker F (filled) and Q (quantity): F==S gives offset0; F==S+A gives offsetA; other values remain incomplete. Native filled=S and quantity=Q-offset=S+(Q-F). Raw Q/F, canonical/raw execution identities, chain IDs, history/boundary receipts and any actual incoming stream-fill receipt remain separate. Startup/poll/refresh and live confirmation use this translation; no ancestor execution is replayed. A source partial with S0 has native ACCEPTED while raw source partial status is retained. Predecessor remainder closes only after confirmed chain and exact actual predecessor fills. Later action matching/modify uses current proven source offset, preserving raw approval/commitment economics.

Installed API evidence: C:/src/printerv2/.venv-nautilus-v1/Lib/site-packages/nautilus_trader/model/orders/market.pyx:168-170 updates quantity only via _update_quantity; it ignores venue changes. base.pxd:76 exposes readonly venue_order_id; base.pyx:1024-1025 rejects differing venue IDs for events other than OrderUpdated. cache/cache.pyx:2110ff changes indexes only. Official OrderFactory.market/cache.add_order plus actual events implement the successor; no installed library patch, fake acceptance/fill, order-type substitution or second position ledger was added.

C04: basket basis now discloses unknown optional costs and identifies required missing economics/configured-check failures correctly. C05: ordinary restore retains current explicit pause/defaultFalse, damaged-original fallback uses an available explicit choice/default, while stale approvals remain invalid and real recovery/history checks remain. Settings and restore response agree. No actual restore was executed.

| Changed production file | Edit-buffer +/- | Edited block starts |
| --- | --- | --- |
| tradingagents/web/nautilus_v1.py | +10/-2 | 3, 73, 75 |
| tradingagents/web/recovery.py | +16/-8 | 308, 365, 377, 380, 387, 421, 437, 447, 519 |
| tradingagents/web/alpaca_reports.py | +56/-3 | 69, 178, 197 |
| tradingagents/web/account_projection.py | +14/-5 | 58, 77, 80, 86, 102 |
| tradingagents/web/execution_lifecycle.py | +133/-29 | 33, 41, 71, 89, 192, 200, 208, 212, 215, 217, 227, 237, 269, 289, 296, 311, 313, 340, 342, 353, 441, 476, 546, 550, 557, 565, 579, 596, 611 |
| tradingagents/web/nautilus_worker.py | +96/-18 | 34, 36, 41, 223, 225, 418, 423, 480, 541, 592, 604, 608, 622, 627, 634, 659, 667, 849, 860 |
| tradingagents/web/investor.py | +99/-2 | 88, 185, 226, 234 |
| tradingagents/web/admission.py | +66/-10 | 10, 271, 304, 347, 353, 395, 398, 426, 440, 513, 682, 685 |
| tradingagents/web/service.py | +14/-5 | 402, 414, 423, 675, 823, 825 |
| tradingagents/web/decision_journal.py | +4/-2 | 19, 81 |
| tradingagents/web/record_integrity.py | +50/-5 | 7, 94, 102 |
| tradingagents/web/static/app.js | +2/-2 | 646, 1091 |
| tradingagents/web/static/command-controls.js | +18/-5 | 30, 32, 51, 60 |

Total +578/-96, net +482; zero test changes. Incremental score -578; cumulative code score -2201. Exact accounting: .runtime-stage/review-corrections-accounting-20261018.json; retained before buffers: .runtime-stage/review-corrections-source-before-20261018. Approval_review and policy_evaluation required no changes in this correction batch.

Root owns subsequent grouped source/runtime/browser verification and independent review. No tests, product import/syntax/build probes, post-edit checks, runtime/browser/provider/research/approval/broker/configuration/install/migration/restore actions or saved-account mutations were performed. Running port8098/PID34840 was left alone. One worker command-quoting failure occurred before its source read; it was not a product probe. No compatible retained populated replay command is known and no harness was created. The empty real account cannot establish populated-fill or broker-execution acceptance.


## Final A1/N1/N2/N3 correction freeze - 18 October 2026

Authority/citations: C:/src/printerv2/evidence/rest-app-20261018/final-source-corrections.md. Exactly these four corrections are saved and frozen; C01-C05 and R01-R14 remain intact.

A1 uses the actual native dictionary type field. N1 sets only official LiveExecEngineConfig.inflight_check_interval_ms=0, retaining the real30s broker poll, account reads and all action endpoints; targeted identity uses official cache indexing or authenticated source client-ID lookup, never /orders/None. N2 retains an exact validated MARKET quantity binding only when broker identities, quantity/fills and supported source terms match; otherwise a genuinely missing fresh binding is withheld. Native quantities/fills are compared after translation.

N3 reevaluates only existing MARKET replacement receipts for partial/full source fills against retained input digest, receipt/history hashes and exact current native account/client/venue/instrument/side/quantity and unique actual fill prefixes at the original observation time. Confirmed child facts release that specific delivery's pending commitment; an exact matching waiting predecessor is confirmed only with its own source receipt and native supersession proof. Actual fill callbacks and successful full observations invoke this path. Already proven child facts can confirm a later-proven predecessor; existing admission.reconcile owns global readiness after full observations. Other pending/conflicting/unproven facts remain retained. No resubmit, fill replay or new recovery subsystem was added.

| Changed production file | Edit-buffer +/- | Edited block starts |
| --- | --- | --- |
| tradingagents/web/investor.py | +1/-1 | 168 |
| tradingagents/web/nautilus_v1.py | +1/-1 | 139 |
| tradingagents/web/nautilus_worker.py | +16/-7 | 685, 734, 737, 745, 751, 757 |
| tradingagents/web/execution_lifecycle.py | +81/-0 | 159, 645, 693 |

Product +99/-9, net +90; zero test changes. Incremental score -99; cumulative score -2300. Accounting: .runtime-stage/final-corrections-accounting-20261018.json; before buffers: .runtime-stage/final-corrections-source-before-20261018. No tests/checks, product imports, syntax/build probes, post-edit verification, runtime/browser/research/provider/approval/broker/config/install/migration actions occurred. Root owns the affected grouped checks and independent review.
