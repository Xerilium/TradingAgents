# Independent UI red-team review

Date: 2026-10-15. Reviewer: fresh ui_red worker. Reasoning session:
`session-1792108171675-50660`.

## Verdict

T-1.2, T-1.3, T-1.4 and T-1.5 **PASS independent offline audit**. No blocking
product defect reproduced in the reviewed scope. PM still owns the required
visible, shared-browser UAT and Gate transitions. This report does not certify
live quote/provider behavior or the Laya model integration.

## Independent evidence

Read the four task bodies and process history, shipped TDD red-team prompt,
blue-team requirements, SWE handoff, actual app.js/CSS, and executable tests.
Ran the accepted suite through the hard-timeout helper:

`rtk proxy .venv/Scripts/python.exe .paper-desk/run-bounded.py --seconds 60 -- node tests/ui_gate_regressions.cjs`

Result: **18 tests passed, zero failures/skips**. The fixture executes actual
production code and forbids network; it does not prove browser layout. Test
expectations retained the original behaviors; the summary regex accepts added
IDs without weakening the collapse expectation.

Independently opened the offline browser fixture in a separate hidden IAB tab,
served actual production JS/CSS, and used documented clicks/keyboard controls.
Server had a 600-second hard deadline. Fixture fetch intercepts known routes,
rejects unknown routes, and disables intervals. No user's service, Gateway,
research run, order, or real configuration save was invoked by browser tests.

| Item | Independently observed |
| --- | --- |
| T-1.2 | Disconnected Update quotes disabled, visible gateway explanation and Refresh connection. Actual recovery button enabled Update quotes. One explicit quote check displayed a successful checked timestamp. Suite verifies failure retains timestamp. Source retains busy/cooldown guards. |
| T-1.3 | Search ZZZZ exposes Clear filters; Enter activation restores four proposal rows. Suite separately verifies query/filter/page reset, no network, and true-empty onboarding. |
| T-1.4 | Edited universe name survives navigation to orders and browser Back. Simulated failed Save retains draft and shows failure; successful fixture Save clears unsaved indication. Suite covers all ten fields, background refresh, discard/reset and CSV draft lifecycle. Source guards concurrent submit and retains newer edits made during a save. |
| T-1.5 | Initially collapsed. Keyboard Enter opens report/raw artifact. Appending final Laya keeps existing opens and reading scroll, while new sections remain collapsed. META starts collapsed; returning to AAPL restores its explicit opens and scroll. No outside layout growth. |

### Browser geometry

Values are CSS pixels; activity is heading top plus page scroll, not panel top.
This differs by 12 pixels from the SWE handoff's panel-top measurement.

| Viewport / transition | Selected panel height | Inner height | Activity heading top | Document height |
| --- | ---: | ---: | ---: | ---: |
| 1440 x 900 collapsed | 585 | 487 | 898.1875 | 1329 |
| Desktop report open | 585 | 487 | 898.1875 | 1329 |
| Desktop raw open | 585 | 487 | 898.1875 | 1329 |
| Desktop final Laya inserted | 585 | 487 | 898.1875 | 1329 |
| 390 x 844 report/raw open | 506.390625 | 412 | 1336.453125 | 1781 |
| Narrow report collapsed | 506.390625 | 412 | 1336.453125 | 1781 |
| Narrow report reopened | 506.390625 | 412 | 1336.453125 | 1781 |

Desktop keyboard End settled at scrollTop 10238 of 10725 (487 visible).
Appending Laya increased content height to 10844 but retained scrollTop 10238.
Narrow keyboard End settled at 16682 of 17094 (412 visible); raw artifact end
was at viewport y=425.89 inside panel bottom y=627.95. Final update preserved
16682. META selection reset its new view to zero/collapsed; AAPL return restored
16682 and only its market/raw disclosures. Keyboard PageUp also accepted.
Normal navigation and outer-page controls remained reachable; no scroll trap.

After synthetic reconnect the outer status copy changed, giving a new activity
heading position of 1352.95 and document height 1797. These are state-layout
changes, not expansion displacement; subsequent disclosure/update samples
retained those values. Smooth keyboard scrolling was allowed to settle before
using measurements.

## Laya disclosure and limits

The additional regression proves actual summary text, model and token budget
are rendered under a collapsed disclosure. Source renders structured metadata
and escaped complete raw artifact. The browser fixture has a Laya result but
not a real laya_review packet; live recorded-input display remains PM's UAT.

Reading-anchor restoration uses report identity and paragraph/pre/summary
index plus relative offset. It preserves the tested unchanged report when
other sections arrive; it does not establish semantic continuity if an existing
report is arbitrarily rewritten or paragraphs are inserted ahead of the
reader. That scenario was not claimed as executed browser evidence.

No product files, task state or real settings were changed by this reviewer.
Temporary viewport was reset and the isolated tab closed. Only this report is
the review artifact; SWE screenshots remain SWE evidence rather than being
relabeled as independent red-team captures.

The scoped fixture server was stopped after verifying its listening port and
command line. Process inspection needed sandbox escalation; the bounded
fixture's 600-second deadline remained the fallback throughout.
