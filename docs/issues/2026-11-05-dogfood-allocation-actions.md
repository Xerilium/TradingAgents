# Dogfood 2: keep allocation actions reachable

## Status and scope

Planned from the real dev8099 Portfolio → Allocations view on 5 November 2026.
Baseline `a7cbfa4`, `nautilus`, `D:/src/TradingAgents`; initial working tree clean.
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
cascade scope and unchanged handlers. Source review does not prove reachability;
one affected responsive live smoke is pending. No automated tests were added
or run.

## Evidence

Original draft: 503 configured symbols, all weights zero, capital100000, fee0 and
blank start/end dates. Preserve these values. No live simulation or preset-load
acceptance is implied by the source mapping. Before capture:
`.local-workspace/dogfood-20261105/allocation-actions-before.jpg` (ignored).
