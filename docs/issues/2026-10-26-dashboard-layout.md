# Dashboard stock list clipped and account values wrapped

Status: Fixed and checked in Edge through Maenifold Playwright
Date: 26 October 2026
Reviewed revision: working tree over 580f1c8; app.css +5/-2 for this repair

## Cause and repair

All 23 configured stocks were present. The fixed-height watch panel used overflow:hidden; its header, wrapped controls and pager could shrink the flexible table to zero. The account ledger combined five equal columns, large metrics and overflow-wrap:anywhere, allowing currency values to split mid-number.

The CSS batch makes the watch panel scrollable, gives its table a 160px nonshrinking flex basis, and applies the existing wider grid immediately above the tab-layout breakpoint. Ledger values use the existing heading token and stay on one line; content-sized columns preserve their values with horizontal overflow when needed. No JavaScript, data, research or broker behavior changed. Existing edits were preserved.

## Observed acceptance

Primary used Maenifold Gateway Playwright against the actual Microsoft Edge page, identified by its exact TradingAgents URL. At 1677x1205, the table had 23 rows and a 280px viewport; the last AMKR row could be brought fully into view. The stock filter and pager were visibly accessible. At 1097x1076, tabs were visible, the table had 23 rows and a 408px viewport, and all five account values occupied one line. At the intermediate 1174x843 CSS viewport, the first row remained visible, the table retained 160px and balances stayed on one line. Resized CSS viewports verify layout; actual browser zoom, other engines and mobile touch were not exercised.

Primary inspected the captured wide and narrow renders and accepts the scoped repair. The original user screenshot and the internal-browser narrow view established the pre-repair failure and retained stock data. No tests, builds, research reruns or broker actions were used.

## Impeccable checks and remaining context drift

Loaded Impeccable layout/adapt guidance and craft floor in Operate mode. The original user-skill filesystem path was absent; the live Maenifold GetConfig assetsPath resolved the installed launcher at the configured Maenifold assets directory under skills/impeccable/scripts/impeccable.cmd, using the existing cached engine 0.1.17. Context ran successfully. The layout-scoped detector returned an empty result. The full app.css detector returned 63 findings outside the modified rules; its first finding was an advisory for an undocumented existing color. No claim is made that all stylesheet findings are fixed.

The user then explicitly requested resolution of all 63 findings and the stale sidecar. The follow-up preserved active RGB/alpha values, shared repeated error and focus values, removed two overridden rules, and documented the observed component-state colors by their actual roles. The implementation worker reported the retained final Impeccable detector result as exit 0 with zero findings; the primary did not repeat that scan. Independent source review confirmed the CSS substitutions and removed-rule cascade; its typography and freshness findings were corrected before completion. Action typography is 14px, table labels 13px, and standard action previews 14px. The final sidecar write/generatedAt is later than the final DESIGN.md write. Existing derived tonal previews remain labeled as previews; no unrelated colors were inserted into ramps and no ignore configuration was added.

Primary completed one read-only Edge cycle through Maenifold Playwright across all nine workspaces, with the Dashboard also checked at wide and narrow sizes. All 23 stocks remained reachable, balances stayed on one line, and real keyboard focus had a visible 2px green outline. The visited views showed no horizontal document overflow. Initial navigation sampling raced four asynchronous view renders; only those uncompleted views were finished with a heading-change wait, without repeating passing pages or changing CSS. The first observed navigation sequence emitted no page errors; no full-product execution or every exceptional UI state is claimed. Actual Market controls, research status badges, saved rejected order rows and account settings were inspected without changing records. Captures are design-cleanup-edge-{dashboard,narrow,markets,research,orders,journal,settings}-20261026.png in the same evidence directory.

The design-contract follow-up adds 6 and removes 6 application CSS lines beyond the earlier Dashboard repair. DESIGN.md changed +87/-36 and the sidecar +53/-40. No tests, builds, research reruns or broker actions. Primary accepts this scoped design-contract repair on the working tree over 580f1c8. PRODUCT.md contained historical product claims at that review; the 28 October workflow repair below replaces them.

## Evidence

- tradingagents/web/static/app.css, ledger/watch-panel/grid rules, working delta over 580f1c8.
- Terra 6.1 extra-high source implementation and primary rendered review.
- Local evidence capture: dashboard-edge-wide-fixed-20261026.png
- Same directory: dashboard-edge-narrow-fixed-20261026.png and dashboard-edge-intermediate-fixed-20261026.png.

## 28 October: source-backed workflow repair

Status: Source UI and documentation changes accepted within the verification limits below. Production installation is unchanged. Release packaging and signing are outside this assignment.

The primary personally led the Terra specialists, authored the component/workflow documentation, selected cleanup targets, reviewed source and inspected the actual development screenshots. Checkpoint before this work: 1690752f32f3b6711d4c8f177975467def2a150e. Six UI files changed (+79/-45 lines); no tests were added or run. Final app.js SHA-256: 60b31031d9924379c9625f0af7745050adc24efa1bb20e0a767d7426ae9cb5be. Final app.css SHA-256: d29cb73b0b3b4f577ab858a780024bd465bd32e569c3a43a37ad79f902ccf37d.

Research launch now sits beside selection, with exact symbols and provider/models visible in confirmation. Dashboard chrome is compact, secondary quote information is disclosed, and confirmation keeps its action reachable while content scrolls. Research distinguishes batch activity from selected evidence. Detail return labels retain context; basket edits invalidate obsolete previews. Model proposal, historical evaluation and actual performance remain distinct.

Independent source review found Mermaid escaping and a missing provider label; both were corrected. The primary caught a watchlist-collapse regression before acceptance and corrected it. JavaScript syntax, Git whitespace and canonical documentation-link checks passed. Initial Impeccable checks reported an existing unrelated color advisory; no claim of a clean full-product detector scan is made.

A visible development pass checked research selection/confirmation, Markets navigation, all Research tabs and delete disclosure without deletion, Portfolio views and the Journal link, Orders/Basket views, and Strategy lab's read-only source loading. META/NVDA stayed the selected batch while GOOGL was inspected. Zero selection disabled launch. The primary inspected captures at 1280x720, 900x700 and 1440x900; the final wide correction kept the action inside its panel, and expanded confirmation content scrolled with Start visible. Passing views were not repeated; observed defects received scoped corrections.

Development reported unavailable native credential storage and had no retained research, supported instrument receipts, drafts or populated account evidence. Populated report/basket-field behavior, simulation execution and broker lifecycles were not exercised. No research, model synthesis, simulations or broker actions were started. Production remained connected and its data/credentials were untouched.

README.md now maps the integrated platform; docs/user-workflows.md and docs/platform-reference.md provide canonical journeys and capability boundaries. The operating guide and PRODUCT.md were replaced with current facts. Sixteen obsolete generated/reference files were removed; docs/nautilus-v1-runtime-manifest.json remains because runtime code uses it. No replacement audit dump was created.
