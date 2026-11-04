# Design critique findings

Working log of what the design critique found in the installed desk app. It is a to-do list, not a spec. Nothing here has been fixed yet. Mark items done as they are fixed.

- Date: 2026-10-28
- App checked: installed app on `http://127.0.0.1:8098/`, paper account, 24-stock universe "PNIS"
- Pages covered: Dashboard, Portfolio, Markets, Research, Orders, Strategy lab, Journal, Alerts, Workflows, Settings
- Method: live walk-through of every page in the built-in browser (screenshots), plus code-based reviews by helper sessions (Dashboard/Portfolio/Markets, Orders/Strategy lab/Journal, Alerts/Settings). Research/Workflows was reviewed the same way.
- Rule for all fixes: keep the existing desk look (`DESIGN.md`) and the promise that nothing here places an order by accident (`PRODUCT.md`).

Priority key: P0 broken or unsafe, P1 fix first, P2 fix next, P3 polish.

## Reported by the user (top priority)

| # | Problem | Likely cause | Fix |
|---|---|---|---|
| U1 | To research a stock you pick it on Markets, then go to Research and press the button. Two pages for one task. | Stock selection lives only on Markets. Research Setup just links back to Markets (`app.js` research setup, ~line 744). | Let the user pick stocks and press "Run research" from one place. |
| U2 | After research starts, the screen looks stuck until you click a stock that is being researched. | `launchResearch` (~line 181) opens Research but leaves the right-hand panel on the previously selected stock. The page does re-check every 5 seconds, so data likely arrives but the panel shows the wrong stock. Not yet reproduced live. | After starting, jump the panel to the first stock being researched. Show a live "N of M done" line at the top. |

## Found by walking the live app

| # | P | Page | Problem | Fix |
|---|---|---|---|---|
| L1 | P1 | Dashboard | The "Browse universe in Markets" button in the Positions box is cut off at the bottom and can't be clicked (box is 322px high, content 374px). Caused by the onboarding change. | Shrink the empty-state block or let the box grow. |
| L2 | P1 | Portfolio > Performance | The empty chart icon is huge (about 1660 x 817px) and fills the page. The "Collect account history" link added earlier is not visible. | Cap the icon size. Put the link where it can be seen. |
| L3 | P0/P1 | Research | Shows a red "Sell" badge and also says "No final recommendation is saved." That contradicts itself. | Show a badge only when a final recommendation is saved. Otherwise say "No final recommendation". |
| L4 | P2 | Research | "Loading the selected stock's research reports..." stays on screen after loading. | Clear it when loading ends. |
| L5 | P1 | Workflows | The diagram area stays on "Rendering workflow..." and never draws. | Find why the render does not finish. Show an error if it fails. |
| L6 | P2 | Sidebar vs Settings | Sidebar says "New orders not paused". Settings says "New orders unblocked". | Use one wording everywhere. |
| L7 | P2 | Sidebar | Same grid icon on five pages (Dashboard, Portfolio, Markets, Strategy lab, Alerts). Same flask icon on Research and Journal. | Give each page its own icon. |
| L8 | P2 | Journal | Shows the raw internal word `human_proposal`. | Use a plain label ("Human proposal"). |
| L9 | P2 | Research | Raw run ID under the ticker. Two scrollbars, one inside the other, in the left list. | Hide the ID behind details. Use one scroll area. |
| L10 | P2 | Strategy lab > Setup | Nearly empty. The "Load saved plans and data" button sits above its own heading. | Put the heading first, then the button. Explain what Setup needs. |
| L11 | P3 | Portfolio > Positions | A huge empty table with only column headings. | Hide the table header when there are no rows. |
| L12 | P2 | Alerts | Three paragraphs in the same style. No clear most-important line. | Make one status line stand out. Move the rest into details. |
| L13 | P3 | Markets | Rows show "AMZN / AMZN" (company name missing, so ticker repeats). Shows "Unsaved workspace changes" with no clear reason. | Hide the second line when it equals the ticker. Explain or remove the unsaved note. |
| L14 | P3 | Orders | "Pause new orders" and "Resume new orders" sit side by side with no sign which one applies. | Show current state. Enable only the button that applies. |

Good, keep: consistent dark desk look, easy-to-read numbers, plain statements that nothing here places a trade.

## Dashboard, Portfolio, Markets (helper report)

Scores out of 40: Dashboard 24, Portfolio 23, Markets 23. No P0.

- P1 Portfolio Positions shows raw unformatted numbers, no signs or colours (inconsistent with Dashboard). Reuse the Dashboard number helpers (`money`, `percent`, `color`).
- P1 Portfolio uses jargon: "atomic package", "principal unpriced", "native comparison". Use short plain sentences. Long text into details.
- P1 Dashboard candle chart: up and down colours too close in brightness. Overlay lines have no legend. No text alternative. Make down candles hollow, add a legend, add a table of recent bars.
- P1 Dashboard Saved research box is only a badge, a date and a button. Show the saved summary when present. Show "No completed research. Last run cancelled." otherwise.
- P1 Markets history form has about 10 controls and a long paragraph, and almost every stock needs it (only AMZN has history). Collapse into one "Get more history" section with one main action.
- P2 Markets filters: 10 equal filter buttons, 8 sort options, about 7 bulk controls. Keep four common views, put the rest under "More views".
- P2 Dashboard watchlist: 24 of 24 rows start selected. 8+ controls above the data. Pagination overlaps row 2 and there is a double scroll. Start with none selected. Show bulk actions only when something is selected. Fix the overlap.
- P2 Tabs on Dashboard and Markets are buttons with `aria-pressed`, not real tabs. All four Markets tabs point to the same panel. Use real tab roles and arrow keys.
- P2 Quote age shows raw seconds ("24989s old"). No warning for stale because the limit is unset. Show "7h 31m old, market closed".
- P2 Markets shows a raw error (HTTP 400) for a stock with no saved research. Replace with "No saved research run for this stock. Run research to see the chart."
- P2 Dashboard Open orders and Positions boxes are thin. Empty state should say "No open orders. Nothing is waiting."
- P2 Portfolio Positions: lead with three values (market value, unrealized P/L, count), one reconciliation banner, put the technical JSON last and label it "Technical record".
- P2 Portfolio Performance empty state is a dead end. Say what creates data ("Needs saved position captures. None yet.") with one next step.
- P3 Options tab always shown with no data. Disable it with a reason.
- P3 The AMZN chart download is 13.9 MB (1,255 bars, 13 indicators). Could freeze rendering. Three numbers for today's AMZN price disagree (252.51, 253.98, 254.69).
- P3 Chart axis is UTC while the selector uses New York time. Two colours in code (`#4dabf7`, `#386c58`) are not in `DESIGN.md`.
- Good: honest "Unavailable" states, signed percentages, the Markets bar selector with a text route to every bar, wording that keeps research, preparation and submission apart.

## Orders, Strategy lab, Journal (helper report)

Scores out of 40: Orders 21, Strategy lab 22, Journal 22. No P0. Reviewed source only, not the rendered page.

Orders
- P1 Submit, Cancel and Replace have no "are you sure" step and no "done" message afterward. Add a confirm line showing the exact terms, then a result line ("Sent to Alpaca paper at HH:MM, id ...").
- P1 The reason an order can't be submitted is hidden in a collapsed "Account readiness and order guidance". Always show the headline and first blocker.
- P1 "Review this order" jumps to the Dashboard. Keep the user in Orders.
- P2 Pause wording differs ("Pause execution", "Pause new orders", "Stop Nautilus"). Pick one.
- P2 Disabled buttons give no reason. Add one line of why.
- P2 Raw JSON and SHA-256 text in the main path. Show a summary row. Label the dump "Technical record".
- P2 The note box is shown for Pause/Resume but is not sent. Hide it there.
- P2 Tabs are `aria-pressed` buttons, not real tabs.
- P3 Open orders table has 9 packed columns. "Place an order" vs "Create an order". Raw order-type names (STOP_LIMIT). Tab buttons 32px tall vs 36px in `DESIGN.md`.
- To verify live: whether double-clicking Submit can send twice (server side).

Strategy lab
- P1 Every warning about what the results do not prove is folded into a disclosure. Keep a short always-visible "What this model does not establish" box.
- P1 Setup is one long form of 12 to 30 fields with no summary. Use steps and a summary.
- P2 About 90-word consent checkbox. Use a short list and a one-line confirm.
- P2 Sub-tab order Setup / Runs / Results. Prefer Setup / Results / Runs.
- P2 Run shows only "Working..." with no elapsed time or live announcement.
- P2 "Choose explicitly" on every select adds friction. Say why once.
- P3 Disabled Run gives no reason. "Saved strategies" is a top tab but renders inside Experiments. Raw field names with underscores. Equity chart has no text summary.

Journal
- P1 "Reload saved journal (discard unsaved notes/settings)" throws away unsaved notes with one click. Confirm with a count or disable while there are unsaved changes.
- P1 Position outcomes is a wall of about 12 paragraphs per group. Use one summary row, details underneath.
- P2 "Find decisions" re-draws the page on every key press (may lose focus).
- P2 "Total return (not supported)" can be picked. Disable it with a reason.
- P2 Capture steps span several pages in prose. Add a "Go to capture on Orders" button.
- P2 Account history is one long scroll (chart, three tables, six metrics). Add an anchor list, collapse tables.
- P3 Short ID suffixes in the Notes list. "Journal" vs "Decision journal". Possible error reading `reference.run_id` when `item.research` is missing (not verified).

## Alerts, Settings (helper report)

Scores out of 40: Alerts 22, Settings 27.

Alerts
- P1 Inbox lost its unread count and has no clear top line. Add an unread badge on the Inbox tab, one status badge, compact one-line occurrences. Show "25 restarts recorded" instead of 25 raw JSON blocks.
- P1 The "no price-age limit configured" line reads like a failure but is a setup gap. Use a neutral badge, one "Set price-age limits" action, and hide the empty "Attention occurrences" heading. After a limit is set, closed-market prices will look stale, so add closed-market wording.
- P1 First alert rule needs 6 or more confusing dropdowns (8 kinds, 11 scopes, 13 indicators). Start with templates ("Price above", "Price below", "Source stale") with one threshold. Put the rest under "Advanced".
- P2 Rules pane ends with unrelated research text. "Your alert rules" has no empty message.
- P2 Rule rows and occurrences show raw IDs, hashes and JSON. Show rule name and a plain summary.
- P3 Tabs lack real tab roles. Remove rule has no confirm. Buttons are bare, not the standard style.
- Minor: Delivery section is forced open. Should say "Browser only; email and push not configured". Close of the evidence panel does not return focus.

Settings
- P1 Research tab has about 20 fields at equal weight. Show provider and models. Put run limits and social screening under "Advanced".
- P1 Diagnostics mixes read-only status with the dangerous restore. Lead with three status chips. Give restore its own section with warning style.
- P2 Start/Stop Nautilus is not on the Integrations tab.
- P2 Engineer words in the UI ("epoch", "generation", `bounded_risk_spread_v1`, "Native Portfolio.equity"). Use plain sentences, details behind a disclosure.
- Minor: full account UUID is shown twice. A stray sentence ("Stale observations are not current balances") sits after "Connection controls". "Launch and restart" hard-codes the install path and port 8098 (wrong for dev, 8099). Funding text appears twice.
- Good: password fields and "Leave blank to keep the saved key", unsaved-draft bar, backups exclude credentials, restore needs a typed phrase.

## Research, Workflows (helper report)

Scores out of 40: Research 23, Workflows 27. No P0 from the helper, but see L3 above (Sell badge with no saved recommendation).

Research
- P1 The progress bar is full green and says "24 / 24 finished" while 21 of 24 were cancelled and only 3 completed. It reads as success. Split the bar (completed / failed / cancelled) or say "3 of 24 completed · run cancelled".
- P1 The layout is cramped. About 270px of header, toolbar and delete row sit above a detail area of about 420px. The left list shows about 3 stocks, the selected row can be off-screen, and there are two nested scrollers. "Select failed / unfinished for a new run" is clipped. Use a one-line queue summary, one list scroller, scroll the selected row into view, give the detail more height.
- P1 The Summary tab is not a summary. It is a small badge followed by long Portfolio Manager prose. Lead with rating, date, run and coverage gaps. Put the full text under "Read full decision".
- P2 The delete toolbar (count, Select matching, Select outside universe, Clear selection, Delete, plus a checkbox per row) is always visible. Hide it behind a "Manage research" toggle. Keep the confirm.
- P2 Tabs are `aria-pressed` buttons, not real tabs. 32px targets, hover looks stronger than active. Reuse the Workflows tab pattern at 44px.
- P2 Reports index has 9 equal buttons. Activity shows 40 of 500 events with no date, raw IDs, repeated boilerplate and no styling for errors (HTTP 429). Group reports (Analysts / Decision / Sources). Filter Activity to the selected stock with a whole-run toggle. Add proper empty states for cancelled stocks (Debate currently shows placeholder data).
- P3 Sources are bare URLs and every row says "News analysis". Show domain and saved date. Raw words in the disposition select (`reviewed`, `needs_review`, `deferred`). Raw run ID in the header. Setup buttons touch each other.
- Doc mismatch: `DESIGN.md` promises "stage markers with colored completion indicators" on Research. Only a plain progress bar exists. Build them or correct `DESIGN.md`.
- Doc mismatch: "Proposed portfolio synthesis" is not on Research > Setup. It lives in Portfolio > Proposed.

Workflows
- P1 The diagram cannot show the whole flow. "Fit width" leaves the first node clipped and the flow is about 1,755px tall in a 512px view. Add a real "Fit all" with a lower zoom floor, or give the diagram the full page height.
- P2 The "Details" popover covers the editor and has no Escape or click-outside close found in code. Show it inline or add both.
- P2 The prompt dropdown has 94 options with truncated labels and raw file names. Use the path as the label with the description on a second line. Make clicking a node the main route.
- P2 Leaving or loading with unsaved edits uses the browser's native confirm box. Use an app dialog ("Discard changes / Keep editing").
- P3 Header noise ("Account verified", "Find a symbol"). "Load Default workflow" duplicates "Load". "Workflow loaded." never clears. Disabled Save looks like a dimmed green primary. Zoom shows "88%" under a "Fit width" label.
- Good: real tab behaviour with arrow keys, 44px targets, Save disabled unless changed, Activate blocked while dirty, preview before use, draft kept if the editor fails.

Live facts: 3 completed (AMZN Hold, INTC Underweight, TER Sell), 21 cancelled, 12 with empty reports ("Stopped before dispatch"). Full state download is 8.7 MB. One workflow only ("Default"). Multi-workflow and zero-workflow states were not tested live.

## Themes across all pages

1. Tabs are `aria-pressed` buttons, not real tabs (every page). Needs tab roles and arrow keys.
2. Warnings and "why can't I do this" reasons are hidden in collapsed sections. Show the short version, collapse the long one.
3. Raw internal words, IDs, hashes and JSON in the main view. Show plain labels, keep technical detail behind "Technical record".
4. Charts have no text alternative (Dashboard, Performance, Strategy lab, Journal).
5. Several pages are built by moving page pieces around after drawing them (Orders, Markets, Alerts, Settings). This is fragile and causes the layout problems.
6. Destructive or committing actions lack a confirm and a "done" message (Orders submit, Journal reload, Alert remove).
7. Disabled buttons give no reason.

## Redesign blueprint and review records

All critique items, model council reviews (Sonnet 5.5, Grok 4.7, Gemini 4 Argon), professional stock trader rubber-duck audits, and existing-backend missed opportunities are consolidated into one single canonical specification:

- [TradingAgents UI Redesign Blueprint (Canonical v4 Master Spec)](ui-redesign-blueprint.md) — 5 user personas, 25 user stories with exact backend bindings, 84%–91% data-height budget, 15 existing backend capabilities newly wired into the UI (with zero new backend code), and trader-audited ASCII wireframes for all 10 workspaces.

## Still to do

- Check live during implementation: does the Research panel focus the first batch stock on launch (U2), and does Stage 3 Submit block duplicate clicks?
- Measure contrast and keyboard focus order during the 4 implementation workstreams defined in `docs/ui-redesign-blueprint.md`.
- Execute the 4 implementation workstreams (Shell/Tablist/Icons, Research & Workflows, Dashboard/Markets/Portfolio, Orders/Strategy Lab/Journal/Alerts/Settings), rebuild the app-only payload, and verify live in the Browser Canvas.
