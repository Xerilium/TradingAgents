# UI TDD blue-team evidence: T-1.2 through T-1.5

Scope: tests and acceptance specification only. Read all four task files including
T-1.5's Laya/last-report and bounded-scroll clarifications, plus
`assets/gates/tdd.json`. No product source changes, browser operation, service
restart, research launch, order, configuration save, commit, or push.

## Executed red signal

```powershell
rtk proxy .venv/Scripts/python.exe .paper-desk/run-bounded.py --seconds 60 -- node tests/ui_gate_regressions.cjs
```

2026-10-15: exit 1; 12 tests, 3 pass, 9 fail, no skips. Direct Node execution
uses node:test's TAP harness without a subprocess. `node --test` initially
failed with spawn EPERM in the sandbox; that was an infrastructure failure,
not the red signal. Direct execution subsequently ran actual assertions.
`rtk --version` returned 0.50.0; `rtk gain` failed to open its tracking database.

The fixture evaluates actual lists.js and app.js in Node VM, removes only the
startup readState call, disables timers, and throws on network. It registers
actual document/window event handlers; DOM parsing is intentionally minimal.
It is not browser DOM/layout proof. Recovery mocks api; no backend is contacted.

| Item | Executed result | Expected behavior |
| --- | --- | --- |
| T-1.2 | Disconnected control test fails: `Disconnected click must not silently do nothing`. Mocked recovery/success timestamp test passes. | Disable with a visible reason and connection recovery, or provide actionable feedback. Success alone advances checked timestamp. |
| T-1.3 | Filtered-empty test fails: `Filtered-empty proposals need a clear-filters recovery control`. Truly empty test passes. | Search/status-filter emptiness offers Clear filters; do not direct users to run new research when proposals exist. |
| T-1.4 | Background edit preservation passes before navigation; roundtrip fails `Lost draft field name`, actual Server changed, expected Unsaved desk. | Preserve all draft fields or let user cancel navigation/discard explicitly. |
| T-1.5 | First, Laya-only, collapse-all, stock switch, run switch, stale toggle defense fail; explicit open choice with final decision/Laya insertion passes. | New sections start collapsed; preserve explicit choices; no blanket collapse of already opened content. |

The stale-toggle test is defensive handler coverage, not proof that a detached
node's event reaches document in a browser. Actual queued events and DOM
reconstruction must be tested in browser; do not claim this establishes the
user's reported last-section RCA. Laya-only is directly reproduced; Laya
insertion alongside an already explicitly opened report currently passes.

## Implementation acceptance and required independent UAT

1. **T-1.2:** With a disconnected snapshot, the Update quotes control must expose
   why it is unavailable and a recovery path, or respond to click accessibly.
   Reconnect fixture, invoke once, verify one request and success timestamp.
   Failure must retain prior checked timestamp. Test busy/cooldown prevents
   duplicate traffic and preserves existing manual retry behavior.
2. **T-1.3:** Supply four AAPL proposals, search ZZZZ, activate Clear filters
   using keyboard, and require all four rows back with query/filter/page reset.
   Repeat status-filter-only emptiness. Clear action must not fetch research,
   build proposals, or submit orders. A genuinely empty proposal collection
   must retain its onboarding explanation. VM currently verifies copy only;
   SWE must add activation coverage matching its chosen recovery action.
3. **T-1.4:** Edit universe name and symbols, all four numeric limits, provider,
   endpoint, deep model, and quick model. Navigate away/back, including browser
   back, and require preserved values or a functioning stay/discard prompt.
   Refresh background snapshot while editing; no overwrite or focus loss.
   Exercise reset-universe and imported text as edits, save failure (retain
   draft), successful save (clear draft), and explicit discard if offered.
   Never save the user's real configuration during UAT; use offline fixtures.
4. **T-1.5:** Fixture sequences: no reports -> market -> news -> portfolio
   decision -> Laya. For each update test both all collapsed and one explicitly
   opened section. Also Laya as the only report, arbitrary final report name,
   close-all, ticker change, run change, and returning to a prior view. Preserve
   existing open sections during updates, source-artifact access, keyboard
   summary activation, focused summary, and reading position. Newly selected
   views start collapsed; previously visited views may restore only explicit
   user choices. Exercise actual browser toggle delivery during DOM replacement.

### Required bounded panel geometry (not established by VM)

Use offline long-report fixture at desktop 1440x900 and narrow 390x844.
Include at least 100 paragraphs, a wide table, long raw source artifact, stock
identity/run status, and enough events to show Run activity. Record bounding
rectangles and document scroll height before/after opening report and raw
artifact. Require selected-stock panel bounded relative to viewport, inner
vertical scroll, and Run activity top/outer document height unchanged within
2 CSS pixels when expanding content. Stock identity and run status stay
accessible. Activity need not always fit the first narrow screen, but must
remain reachable and not be displaced by expanding report content.

Scroll inner panel to a known paragraph using wheel, then keyboard after focus;
reach the last paragraph and raw artifact end without clipping or a scroll
trap. Record scrollTop and the anchor's viewport position; update an existing
report and append final Laya, require same reading position (2px tolerance
unless the anchor itself changed). Ensure activity stays reachable via Tab and
normal page scrolling. Record screenshots and measurements for both widths.
Do not treat CSS selector assertions or the passing VM suite as geometry proof.

## Handoff

Fresh SWE owns implementation and may extend this fixture to support added DOM
APIs, but must not weaken behavior expectations. Fresh audit and PM shared
browser UAT follow; PM alone advances Gate. Durable test-stage record:
`memory://thinking/sequential/session-1792107517372-67296.md`.
