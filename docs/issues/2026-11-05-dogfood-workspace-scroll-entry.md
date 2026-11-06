# Dogfood 6: enter a workspace with its controls visible

## Status and observed failure

In progress from live dev8099 observations on 5 November 2026. Baseline
`311a41c`, `nautilus`, `D:/src/TradingAgents`; initial working tree clean.
Keep this work integrated on `nautilus`; no new branch or worktree.

The primary followed the native Portfolio sidebar link from a deeply scrolled
Orders → Human Baskets view. Portfolio opened with Observed positions near the
top of the visible content, but its title, workspace tabs and account balances
were above the viewport. This was the first Portfolio visit since the current
frontend reload. The user could not reach the SPY-related portfolio controls
without first discovering that they needed to scroll upward.

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
