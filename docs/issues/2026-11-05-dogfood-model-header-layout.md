# Dogfood 10: make model proposal controls readable

## Status and observed jank

Completed implementation `f76ff20`, fresh independent source review and one
native-input/layout live batch on 5 November 2026. Baseline `03f168f`, `nautilus`,
`D:/src/TradingAgents`; initial working tree clean.
All work remains integrated on this branch; no new branch or worktree.

Primary inspected Portfolio Positions, Model proposal and Allocations, then
followed Open account fund plan to its correct Orders destination. No broken
outcome was observed in those read/navigation paths. No model job, simulation,
research rerun, fund-plan save or broker action was used.

At 1024 × 768, Model proposal's two field labels sit inline directly against
their inputs with no visible separation. DOM text ranges ended exactly where
the inputs began: Model capital at x=755.53125; Prices and research as of at
x=784.265625. There is no established text overlap or calculation defect. The
right-hand controls form three rows and crowd the workspace tabs onto a row
below the title, unlike the simpler Portfolio tabs. This item addresses form
scanability and header jank, not model allocation behavior or execution.

Before capture (ignored):
`.local-workspace/dogfood-20261105/model-header-layout-before.jpg`.

## Investigation and constraints

Dynamic workflow `wf_b9e931c9-fce` independently traces the header/input CSS,
source bindings and polling preservation, and researches official trading-tool
organization principles. Primary owns implementation and the built-in browser.
Choose a scoped form layout, not a global header or form redesign. Preserve
existing input IDs, attributes, values, labels and behavior; keep the Model
portfolio action separate and explicit. Do not invent a result or change model
capital/as-of semantics, eligibility, research or broker authority.

Use Impeccable Operate/layout guidance and craft floor before editing. Obtain
fresh independent code scrutiny with its own context setup, then one affected
live layout/navigation/native-input smoke at desktop and narrow widths without
activating Model portfolio. No automated tests, mocks, fabricated model records,
private configuration/credentials, production operations or broker actions.

## Research and plan

The independent source trace found that only the proposed tab passes these fields
into the shared header action group (`app.js:763–766`). The intended column-label
and input-width rules target `.proposed-portfolio`, but the controls are outside
that section, so those rules do not reach them. The labels contain text directly
followed by the input. Header flex sizing therefore competes with workspace tabs
without providing field grouping. The initial layout-only source detector found
no findings; it cannot establish rendered hierarchy or spacing.

Official sources accessed 5 November 2026:

- [Fidelity Trader+ Desktop customization](https://www.fidelity.com/trading/trader-desktop-user-guide/customization):
  primary verified that workspaces are the containers for tools.
- [Robinhood Legend layouts](https://robinhood.com/us/en/support/articles/layouts-on-legend/):
  research worker reports moving and resizing widgets. This supports coherent
  grouping and sufficient space, not adding draggable widgets or claiming an
  exact form layout/model-allocation feature in either product.

Plan: retain the title and tabs in the existing Portfolio header, and place the
existing model actions in a dedicated, proposed-only row immediately afterward,
before the account ledger. Use a wrapping flex row, end alignment and existing
spacing tokens. Stack each persistent label above its input with the existing
small gap and 180px input convention. Preserve DOM/focus order (capital, date,
explicit Model portfolio action), IDs, values, attributes, disabled conditions,
event listeners and polling restoration. Keep Performance export actions and all
other tabs/workspaces unchanged. No global header or form CSS changes.

Primary will inspect capital/date native focus and value retention across polling
and tab navigation without altering their terms or running the model. The one
live batch will cover 1024 × 768, 768 × 1024 and wide desktop grouping/reachability.
Running/queued/populated job states remain source-reviewed unless already present;
no job or fabricated result will be created to manufacture that acceptance.

## Source implementation and checks

Implementation `f76ff20` leaves `portfolioModelActions()` and every input/model
handler unchanged. Only Portfolio composition relocates its output into a
proposed-only, named input group after the common title/tab header. Three scoped
CSS rules define nonshrinking wrapping-row layout, column labels with a small
gap and the existing 180px input limit. Performance header actions remain intact.

Candidate blobs: app.js `0959964542e6c6a81fbd2b19d55884791bc6b3c3`;
ui-research-journal.css `23b12e8711fcdcbe3891ff52b64fd7f0f209d954`.
Delta: 2 added / 2 removed JavaScript lines, 3 added CSS lines. No tests added
or run. JavaScript syntax and Git whitespace checks passed. Manual Impeccable
source detector reported no anti-pattern failures and only the pre-existing
out-of-scope `#4dabf7` palette advisory at app.js line 2378. Regex-only detection
is not rendered accessibility or product acceptance evidence.

Fresh independent review `wf_13f0ef48-532` found no actionable defects against
`f76ff20be3e5552745052e749b82d9ce83c29def` and verified both candidate blobs.
The reviewer ran its own Impeccable context once and read Operate, layout, craft
floor, PRODUCT and DESIGN. It checked the unchanged model markup/conditions and
explicit handler, input preservation, scoped cascade and preserved Performance
exports. This was source-only review, not rendered acceptance.

## Live acceptance evidence and decision

Primary loaded the actual dev8099 frontend at the reviewed source without a
service restart and performed one affected batch without activating the model:

- At 1024 × 768, Portfolio title and all tabs stayed in the common header. The
  proposed-only input group appeared underneath. Positions and Model proposal
  had identical header bounds (x=188, y=89, width=820, height=60.296875); Positions
  had no model control group. Field labels now sit above inputs with the existing
  4px layout gap; the group's 8px gap separates fields and the explicit action.
- Re-entered the exact existing capital value, 10000, with native Ctrl+A/type;
  no new capital or as-of term was invented. Capital focus and value remained
  intact while actual state polling returned 200 and the observed update advanced
  from 02:25:53 to 02:26:24 UTC. The date stayed blank. Native Tab reached the date
  input. The entire segmented date-to-action Tab sequence was not established;
  no key or pointer activated Model portfolio.
- Navigating to Positions and back retained capital 10000 and blank as-of. The
  job remained idle and the visible message stayed “No joint portfolio modeled
  in this app session.” No populated model record was fabricated.
- At 768 × 1024 and 1600 × 1000 the labels, inputs and action fit one control row;
  group client/scroll dimensions matched (736 × 67 and 1360 × 67). The common
  header and account ledger stayed separate and the result surface remained usable.
- At 375 × 812 the two fields remained readable and the action wrapped to the
  next row. Group client/scroll dimensions both measured 343 × 113. Document
  width matched viewport width at all measured sizes (375, 768, 1024 and 1600).
  This was part of the same responsive batch, not a second model/test run.
- Restored 1024 × 768, then cleared viewport emulation to desktop. Console
  inspection reported no errors. Existing authority stayed “Orders: Active ·
  Manage”; job status stayed idle. No model/provider job, research rerun,
  simulation, fund-plan save, credential/private configuration inspection,
  installation, production operation, order, approval or authority action.

Primary decision: accept the discrete model-form layout correction after fresh
source scrutiny and these actual layout/input cases. Queued/running/populated
jobs, long/localized terms, 200% browser zoom, physical assistive technology and
the full segmented native-date keyboard sequence remain source-reviewed or
unexercised, not claimed as passes. No automated tests or mocks. This does not
validate model allocations or broker execution. Captures and DOM were personally
inspected; no joint human acceptance is claimed.

Ignored local captures under `.local-workspace/dogfood-20261105/`:
`model-header-layout-before.jpg`, `model-header-layout-after.jpg`,
`model-header-layout-after-tablet.jpg`, `model-header-layout-after-phone.jpg`.

Continue the completion-paced loop with requested 60-second delay, dynamic
workflows, fresh source scrutiny and integrated local commits on `nautilus`.
Scheduler minute-boundary rounding can exceed the requested delay.
