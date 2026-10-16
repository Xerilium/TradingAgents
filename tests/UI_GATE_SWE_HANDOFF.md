# UI SWE handoff: T-1.2 through T-1.5

Reasoning HSM: `session-1792107665622-63768`.

## Scope and changes

- `tradingagents/web/static/app.js`: disconnected quote explanation and disabled control; recovery invokes the existing broker refresh operation. Filtered-empty proposals have a local Clear filters action. Complete in-memory settings drafts survive navigation/background reads, including reset/import; explicit discard and successful save clear the draft, failure retains it. A second submit cannot clear an in-flight draft and edits made during a save remain drafts.
- Report and raw-source disclosures begin collapsed and use per-run/per-symbol explicit choices. Detached/stale-view toggle events are ignored. Summary IDs retain keyboard focus on reconstruction. The selected report region retains scroll position and an existing reading anchor during updates.
- `app.css`: selected-stock panel is bounded at 65vh (320–680px), 60vh on narrow screens, with its own focusable scrolling region. Identity sits outside that region; raw source participates in the same scroll region. Run activity does not move when reports expand.
- T-1.1 integration: `laya_review` evidence shows actual input summary, model, token budget, full structured metadata and source artifact, collapsed by default.
- Tests: extend accepted `ui_gate_regressions.cjs`; add `ui_gate_browser_fixture.py` and two screenshots. No changes to lists.js, backend, Gate files, global settings, or user configuration. Existing quote changes preserved.

## Executed verification

`rtk proxy python .paper-desk/run-bounded.py --seconds 60 node tests/ui_gate_regressions.cjs`: **18/18 pass**, no skips, final run 2026-10-15. Original twelve behavioral expectations retained. One exact HTML regex was updated from `<summary>` to `<summary[^>]*>` because summaries now have focus-preserving IDs.

`rtk proxy python .paper-desk/run-bounded.py --seconds 10 node --check tradingagents/web/static/app.js`: exit 0.

`git diff --check` through bounded RTK: exit 0; existing CRLF warnings only.

Browser work used only cua_repl and a separate hidden IAB tab at `http://127.0.0.1:18764`. Fixture serves actual production CSS/JS; fetch is intercepted before startup, blocks unknown routes, and returns only synthetic data. No request goes to the user's service/Gateway. Browser actions used documented locators, keyboard and wheel; evaluate was read-only DOM geometry. Server and tab stopped after verification; viewport reset.

## Real browser geometry (CSS pixels)

Fixture: 110 paragraphs, five-column table, full long raw artifact, two symbols, twelve activity events. Measured activity position is document-relative (bounding top + scrollY), so intentional page scrolling does not masquerade as displacement.

| Viewport | Panel height | Inner height | Activity top | Document height | Collapsed → report → raw |
|---|---:|---:|---:|---:|---|
| 1440×900 | 585 | 487 | 886.1875 | 1329 | All three geometry values unchanged |
| 390×844 | 506.390625 | 412 | 1324.453125 | 1781 | All three geometry values unchanged |

Desktop raw end reached scrollTop 10238 of scrollHeight 10725/clientHeight 487. Narrow wheel moved scrollTop to 1688; keyboard End reached raw end at 16563 of 16975/clientHeight 412. Last paragraph and raw end were visible, with Run activity reachable by normal page scrolling. Screenshots: `tests/ui_gate_desktop.jpg`, `tests/ui_gate_narrow.jpg`.

Final Laya insertion preserved existing market/raw opens, with new News and Laya collapsed. Desktop reading sample: scrollTop 9812 and raw anchor top -3023.5625 unchanged. Narrow: scrollTop 16203 and raw anchor top -6513.609375 unchanged. Final-build settled rerender sample: scrollTop 9812 and anchor -2995.5625 unchanged. Measurements immediately following keyboard smooth scroll were not treated as settled evidence. Switching to META produced no open disclosures; returning to AAPL restored only explicit market/raw opens and scrollTop 9812.

## Other browser acceptance

- Search ZZZZ → Clear filters via Enter restores four proposal rows and blank query. Blocked-status-only → Clear filters via Enter restores four rows and `all`. No research/orders invoked.
- All ten settings values edited, then browser Back after navigation and fixture background refresh: values preserved. Simulated save failure retains draft and displays error. Synthetic successful save clears draft; later explicit discard restores saved name. Reset universe persists through navigation. CSV import preservation is covered by executable VM test (not OS file-picker UAT).
- Disconnected Update quotes is disabled with visible reason. Final browser test used the actual Refresh connection button, then verified enabled Update quotes and a newly displayed successful check timestamp. VM covers success-only timestamp advancement and one mocked request.
- Keyboard Enter expands report/raw summaries, and PageUp/End plus wheel navigate inner content. Source artifact text remains escaped and accessible.

## Limits and audit notes

- This is offline UI UAT, not a live account, provider, or research execution test. The PM owns live browser UAT and Gate advancement.
- Run-switch/new-first/Laya-only/collapse-all/stale-toggle cases are executable VM coverage; stock-switch/return and reconstruction were also exercised in browser. No fresh paid runs occurred.
- The historical Impeccable context reports missing buildPath (irrelevant to this narrow Operate refinement); no design configuration was changed.
- RTK version 0.50.0 worked; `rtk gain` could not open its analytics database. This did not prevent scoped commands.
