# Dogfood 2: keep allocation actions reachable

## Status and scope

Completed implementation `13841ff` and one responsive live affected smoke on
5 November 2026. Baseline `a7cbfa4`, `nautilus`, `D:/src/TradingAgents`;
initial working tree clean.
One complete item: restore access to the existing allocation action buttons.
No changes to presets, dates, allocation math, simulations or broker authority.

## Observed failure

At the actual 1024 × 768 viewport, the action row computed to `flex-wrap: nowrap`.
Its visible width was 818px, but its scroll width was 1,239px. The October SPY
button extended from x995 to x1184, Equal weight from x1199 to x1304, and Clear
weights from x1319 to x1428. The document width stayed 1024px; the panel clipped
these actions rather than making them normally visible. The rendered capture
confirmed that the final actions could not be reached by an ordinary pointer.

This is broken access to existing core allocation controls, not a request for
more trading features or a toolbar redesign.

## Research and plan

- [Fidelity Active Trader Pro settings](https://www.fidelity.com/products/atbt/help/ActiveTraderTools_Settings_Help.html),
  accessed 5 November 2026: documented tool/workspace arrangement and sidebar
  customization reinforce access to working controls. This does not establish
  a particular supported viewport for ATP or equivalent Trader+ behavior.
- Impeccable Operate: responsive structure and familiar controls outrank
  decorative change. Preserve the incumbent labels, order and handlers.
- Source mapping confirmed SPY preset loads read shipped dated JSON and do not
  start simulations or fetch provider data. Simulation is a separate action.
  No definite weight-unit or precision mismatch was found. A source-only
  holdings-date/publication-wording concern is not part of this toolbar fix.

Add one allocation-specific action-row class. Let that row wrap and align from
its leading edge. Constrain only its own buttons to the available width and let
long labels wrap. Do not change global form actions, labels or behavior.
Independently review the final source with Impeccable context; then one responsive
live smoke batch at the original desktop width and a narrow width. Only local
session-draft actions may be exercised; no simulation or broker action.
No automated tests, mocks, fabricated allocations or new styles outside this row.

## Source change and validation

The implementation adds `portfolio-allocation-actions` only to this toolbar and
one scoped CSS rule group in `ui-instrument.css`. Labels, order, handlers and
all other action rows are unchanged. Source delta: 2 added / 1 removed lines
across JavaScript and CSS. No backend or test file changed.

Reviewed source blobs:
- `static/app.js`: `0df29a6583ddddb62b1e51c04093d0f3924df763`.
- `static/ui-instrument.css`: `947b15a9acbaef4748b93738d4e20c22229149ec`.

JavaScript syntax passed. Independent source review found no confirmed findings
against `7b562f1` and the blobs recorded above. The reviewer ran Impeccable context
successfully, read Operate/adaptation guidance and craft floor, and confirmed
cascade scope and unchanged handlers. Source review alone did not establish
reachability; the primary's live evidence follows. Scoped whitespace validation
passed after removing an extra documentation EOF blank line. No automated tests
were added or run.

## Evidence

Original draft: 503 configured symbols, all weights zero, capital $100,000, fee $0 and
blank start/end dates. Preserve these values. No live simulation or preset-load
acceptance is implied by the source mapping. Before capture:
`.local-workspace/dogfood-20261105/allocation-actions-before.jpg` (ignored).

### Live smoke and decision

The primary reloaded the actual running dev8099 app at `13841ff` and exercised
one affected responsive batch, without restarting the app or native runtime:

- At 1024 × 768 all six actions rendered within the panel. The action row's
  scroll width fell from 1,239px to its actual 818px width; computed wrap was on.
- The previously clipped Clear weights button was clicked by native pointer
  input on the existing empty draft. The result remained 0 of 503 positions,
  0% invested and 100% cash target. Capital $100,000, fee $0 and blank dates remained
  unchanged. This does not prove clearing a populated authored allocation.
- At 768 × 1024 the actions wrapped into three rows, all visible inside the
  panel. Scroll width equaled its 734px width; the page width remained 768px.
  The rendered capture showed complete labels and a reachable Clear weights.
- Browser console inspection reported no errors. Viewport emulation was reset
  to desktop immediately after the narrow capture.

Primary decision: accept the complete allocation-toolbar access repair at the
observed widths. Preset loading, simulation execution, nonzero weight editing
and other form-action rows were not live-exercised; their behavior was not
changed. No provider collection, new research, broker action, trading-authority
change, runtime installation or production operation occurred. Rendered browser
captures and DOM were inspected; the app could not show this session's pane, so
this is not joint user-visible-pane acceptance.

After captures (ignored local evidence):
- `.local-workspace/dogfood-20261105/allocation-actions-after-desktop.jpg`.
- `.local-workspace/dogfood-20261105/allocation-actions-after-narrow.jpg`.

Continue the user's loop with a requested 60-second post-completion delay;
scheduler minute-boundary rounding can exceed that requested delay.
