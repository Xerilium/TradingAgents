# Dogfood 6: enter a workspace with its controls visible

## Status and observed failure

Completed implementation `92f5866`, fresh independent source review and one
affected live navigation smoke on 5 November 2026. Baseline `311a41c`,
`nautilus`, `D:/src/TradingAgents`; initial working tree clean.
Keep this work integrated on `nautilus`; no new branch or worktree.

The primary followed the native Portfolio sidebar link from a deeply scrolled
Orders → Human Baskets view. Portfolio opened with Observed positions near the
top of the visible content, but its title, workspace tabs and account balances
were above the viewport. This was the first Portfolio visit since the current
frontend reload. The SPY-related portfolio controls were not visible on entry;
a working user recovery by scrolling was not established.

Read-only DOM inspection at 1024 × 768 showed `main[data-page=portfolio]` with
`scrollTop=176`. The Portfolio heading was at y=-69 to -46 and the tabs at
approximately y=-83 to -44, above the visible main region. No draft, research,
account, authority or broker action caused or was used to reproduce the failure.

Before capture (ignored):
`.local-workspace/dogfood-20261105/workspace-scroll-entry-before.jpg`.

## Research and source diagnosis

Official documentation accessed 5 November 2026:

- [Fidelity Trader+ Desktop customization](https://www.fidelity.com/trading/trader-desktop-user-guide/customization):
  primary read confirmed workspaces are containers for tools and layouts collect
  workspaces. The page does not specify switching or scroll-reset behavior.
- [Robinhood Legend layouts](https://robinhood.com/us/en/support/articles/layouts-on-legend/):
  research worker reports separate layout tabs and saved template changes. This
  is documented capability, not an observed account or scroll behavior.

The applicable principle is a distinct, accessible destination context with
intentional state preservation. Neither source establishes a specific scroll
rule, feature parity or broker execution. Research retrieved the attributed
observation and preservation constraints at
`memory://thinking/sequential/2026/11/06/session-1793927479365-85492`.

Independent source diagnosis traced `app.js:645`: `render()` replaces persistent
`#main` contents and changes its page marker without resetting its own offsets.
The hash handler's `window.scrollTo(0,0)` targets a different scroller. Existing
keyed workspace-scroll capture/restore covers descendant panes, not `#main`.
Portfolio's hidden overflow does not guarantee a zero retained scroll offset.

Plan: compare `main.dataset.page` with `activePage` at the committed render
boundary. Immediately after markup/page assignment, reset only the main scroller's
vertical and horizontal offsets on an actual workspace change. Do this before
binding and caller completion focus/anchors. Preserve early-return/guard behavior,
same-workspace renders (including forced refresh), existing keyed descendant
scroll restoration, native input restoration and all handlers. Comparing the
rendered marker covers sidebar/hash, guarded callbacks and direct page assignments
without resetting on an attempted or deferred navigation. Do not replace the
router or add per-workspace main-scroll history.

## Investigation and scope

A dynamic workflow independently traces the render/capture/restore, navigation,
hash and deferred-guard paths and researches documented trading-workspace
navigation. Primary owns implementation and the built-in browser.

Choose the smallest complete correction that prevents an unrelated workspace's
main scroll offset from hiding a newly entered page's controls. Preserve normal
same-workspace refresh scroll, focused native input state, drafts, intentional
completion focus/anchors and existing guarded navigation. Do not add persistent
per-page scroll storage, a new router, new capabilities or broker behavior.

Use Impeccable Operate/harden guidance and craft floor. Obtain fresh independent
source review with its own Impeccable context, then one affected real-navigation
smoke batch. No automated tests, mocks, fabricated populated records, credential
or private configuration inspection, authority changes or broker actions.

## Source implementation and checks

`render()` now compares the existing main page marker with `activePage`, then
zeros only `#main`'s two offsets just after committing a different workspace.
Same-page early returns, rendering, input/descendant-scroll restoration, bindings
and completion callbacks are unchanged. No CSS, markup, backend, terms or handlers
changed. Source delta: 1 added / 1 removed JavaScript line; reviewed candidate
blob `bec580927e352ee36a4cb6c24c3bb3b94d168705`.

JavaScript syntax and Git whitespace checks passed. The Impeccable detector
reported only the previously documented `#4dabf7` palette advisory at line 2378,
outside this change. No palette repair, automated tests or mocks were added.
A separate fresh independent reviewer found no confirmed actionable findings
against `065d5e5` and the recorded blob, committed as `92f5866`. The reviewer ran
Impeccable context once and read PRODUCT, DESIGN, Operate, harden and craft floor.
Source coverage included render early returns, keyed scroll/input restoration,
focus/anchor ordering, guards, hash/direct/async paths and external navigation
callers. No runtime acceptance was inferred from that source-only review.

## Acceptance evidence and decision

Primary reloaded the running dev8099 frontend at `92f5866` and completed one
real navigation batch at 1024 × 768, without restarting the service:

- Selected Human Baskets and used native scrolling. `#main` reached 1,000px.
  It remained at 1,000px across observed normal background state polling; the
  selected workspace/tab did not change. This covers that same-workspace case,
  not every forced refresh or native-editor interaction.
- Followed the native Portfolio sidebar link. The committed Portfolio view had
  main vertical and horizontal offsets zero. Its heading was at y=107 to 130,
  its tabs at y=93 to 132, both below the main viewport start at y=73. The rendered
  capture showed the title, all four tabs, balances and position-entry content.
- From Portfolio, selected topbar Manage. Orders opened Ticket & Blotter, then
  deliberately scrolled main to 2,137px and focused `account-order-controls` at
  y=408. The destination focus was not overridden by a later reset. The rendered
  Stage 3 content remained readable.
- The topbar stayed “Orders: Active · Manage”, with the existing BND selection,
  no approved order and $100,000 cash. Console inspection reported no errors.
  No order terms, preview, save, approval, submission, pause/resume, cancel/replace,
  research, simulation, provider collection, installation or production operation.

Primary decision: accept the discrete main-scroller entry correction after fresh
source scrutiny and these observed navigation cases. Deferred workflow/credential
guards, nonzero horizontal offsets, every hash/direct caller, forced refreshes,
populated dirty drafts and import/export remain source-reviewed, not separately
runtime-proven. No private credential state or fake terms were used to manufacture
acceptance. No automated tests or mocks. No full workspace or broker-execution
acceptance is claimed. Rendered captures and DOM were inspected; joint user-visible
pane acceptance is not claimed.

Ignored local captures under `.local-workspace/dogfood-20261105/`:
`workspace-scroll-entry-before.jpg`, `workspace-scroll-entry-after.jpg` and
`workspace-scroll-entry-manage-focus.jpg`.

Continue the completion-paced loop with its requested one-minute delay, dynamic
workflows, fresh independent code scrutiny and all local commits on `nautilus`.
Scheduler minute-boundary rounding can exceed 60 seconds.
