# Strategy Lab setup is cramped beside an empty results pane

Status: Reproduced; scoped implementation ready for independent review
Owner: Codex subagent `strategy_layout`
Coordinator: Codex parent
Reported: 30 October 2026

## Real reproduction before a fix

Open the installed desk's **Strategy Lab > Walk-Forward Experiments**, load
the saved strategies and data, and select the existing Amazon demonstration.
At the observed 1834 by 1036 desktop viewport, all configuration is forced into
a 360-pixel scrolling column. Most of the remaining width displays an empty
results panel and **Go to Setup**, even though setup is already visible.
The long strategy editor and assumptions require extensive scrolling in that
small area while the main working area is unused.

The coordinator observed this in the built-in browser, and the user explicitly
reported the same problem. Screenshot of the unchanged layout (also showing a
separate preview error):
`C:/src/printer/.local/strategy-preview-error-20261030.jpg`.

## Source and documentation checked

- `tradingagents/web/static/ui-research-journal.css`, lines 41-45, fixes the
  rail width and makes its content independently scroll.
- `tradingagents/web/static/app.js::renderStrategy` always renders that rail
  beside the results canvas, including before a preview or result exists.
- `PRODUCT.md`, `DESIGN.md`, `docs/platform-reference.md`, and the Strategy
  Lab section of `docs/ui-redesign-blueprint.md` describe the current product.
  The old design explicitly prescribed this narrow rail; the user's current
  request supersedes that layout.
- Impeccable Operate/layout guidance applies. Preserve the current visual
  system and all real controls; avoid a broader redesign.

## Acceptance

Give configuration the available working width while the user is setting up.
Keep preview/results and saved-run inspection directly reachable, with clear
navigation back to setup. Preserve entered values, selected strategy, exact
preview/run gates, busy states and keyboard tab behavior. Verify both existing
simulation and experiment modes in the built-in browser, including a narrower
desktop width. Do not add backend features, change order authority, hide
required fields or use generated results to fill the empty pane.

Source baseline: `b9ba6ba`; engine-path fix is a separate, already reproduced
issue. No layout code was changed before this record and source diagnosis.

## Source review

Independent reviewer `strategy_preview_fresh_review` found no code-level
blocker in the full-width views, shared unchanged Run gates, state retention,
or tab/focus/scroll handling. The reviewer identified one remaining blueprint
table row prescribing the old rail; that row was corrected before packaging.

Reviewed SHA-256 values:
- `app.js`: `d3d4138647718dc8659a3d8908ba254fb5182976179e49e6b3367d60bac9b58e`
- `ui-research-journal.css`: `c75e7e6218ce5d2b88e3210310752ffbe1da791adc377805e20f772672199450`

The worker's JavaScript syntax and whitespace checks passed. One final
Impeccable layout scan of both changed UI files returned no findings. These
are source/static results only; installed rendering and behavior remain to
be verified with the user's real saved example.

## Independent layout assessment

The captured empty state gives the results pane most of the page's visual weight
while the active task occupies a fixed 360px column. The three-step grouping is
useful, but forced single-column fields create excessive vertical reading and
scrolling. The old 790px breakpoint stacks both panes without separating their
tasks. A long form, a blank result, and a validation error all compete in the
same composition. These are observed/source-backed layout findings; no new
runtime or data defect is inferred from them.

Keep the existing visual identity and spacing scale. Configuration is the first
task; preview/results and saved-run inspection are distinct subsequent views.
Let the active view use the available width and height. Preserve the logical DOM
and keyboard order, existing disclosure groups and the preview/run boundary.

Impeccable context ran once using its existing cached 0.1.16 binary. PRODUCT.md,
the complete DESIGN.md, the platform reference, local desk guide, Strategy Lab
blueprint section, and the live layout/Operate/craft-floor references were read
before editing. The coordinator owns the separate mechanical scan.

## Scoped implementation

- Expose the already-supported Setup view beside Preview & Results and
  Runs & Compare; render only the selected full-width view.
- Remove the fixed 360px/320px rail split and its single-column field override.
  Existing paired fields remain paired on desktop and stack below 600px.
- Use one content scroller per view and retain the existing scroll/focus state.
- Share the existing Run-button conditions between setup and a saved preview's
  results view; no duplicate controls or weaker checks.
- Return the existing Edit configuration as a new branch action to Setup so
  the draft is visible. Saved-record opening still goes to results.
- Update only the corresponding layout description and blueprint section.

No backend, broker authority, saved data, dependencies, calculations or
simulation rules changed. No browser actions, tests, builds, staging or commits
were performed by this worker. Installed-app and narrower-desktop verification
remain pending the coordinator's integrated package.
