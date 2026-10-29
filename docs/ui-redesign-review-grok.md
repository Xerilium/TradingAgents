# Grok review: cut the blueprint before anyone builds it

Reviewed 28 October 2026. This is a design review of `docs/ui-redesign-blueprint.md` against `docs/ui-design-critique.md`, the current desk source, and `docs/ui-scale-research.md`. No application code was changed. The live desk on port 8098 was not opened, stopped, or modified.

Method: Impeccable Operate, with shape, layout, and distill applied to the proposed screens. The installed-app walk-through already exists in the critique. This review does not repeat that walk-through.

**Do not implement the blueprint as written.** It fixes the right complaints, then spends the recovered space on a second layer of bars, cards, and made-up tasks.

## Verdict

The blueprint understands the injury: Research cannot pick its own stocks, the progress bar treats a cancelled run as success, and labels eat the page. Those three fixes are real. The drawings are not ready.

The 80% data rule is already false on the blueprint's own Research frame. The global bar is drawn as two lines and called 48px. The launch bar is drawn as two lines and called 44px. The detail pane then adds tabs, four cards, and two more cards. That is the old page with nicer boxes.

Worse, several frames invent a product we do not have. Strategy Lab becomes a three-field moving-average toy and drops the saved preview that must exist before a run. "Draft order" is drawn as a hop to Orders. The code opens the existing proposal review on Markets, and approval still does not submit. A four-color progress bar drops `incomplete` and `interrupted`, which is how the current green bar lies. The Activity tab, the trace the product is built on, disappears.

Build the corrected frames below. Do not add a summarizer, a chat box, detachable windows, or a new order path to make the drawings true.

## Design health of the blueprint

Scores are for the proposed frames, not the live app. The live pages already scored about 21–27 out of 40 in the critique.

| # | Heuristic | Score | Why |
|---|-----------|-------|-----|
| 1 | Visibility of status | 2 | Honest counts are started, then Stage 2/5 is invented and incomplete/interrupted are dropped. |
| 2 | Match to the real desk | 2 | SMA setup, Draft order, and a Fundamentals tab are not the current capabilities. |
| 3 | User control | 3 | Manage toggle is right. Run must not skip the existing confirm dialog. |
| 4 | Consistency | 2 | The frames break their own height budget. Pause wording is still unfinished. |
| 5 | Error prevention | 2 | A verdict-to-ticket shortcut and a simplified lab can collapse separate steps. |
| 6 | Recognition rather than recall | 3 | Verdict strip is the right first read, if it uses saved text only. |
| 7 | Flexibility and efficiency | 2 | Paging, search, and the 500-stock selection rules are missing. |
| 8 | Aesthetic and minimal design | 2 | Global account strip, stacked toolbars, four cards, and a permanent alert form. |
| 9 | Error recovery | 2 | Stuck loading text, diagram failure, and raw quote errors have no frame. |
| 10 | Help and documentation | 3 | One-line safety notes are right. Do not grow them back into paragraphs. |
| **Total** | | **23/40** | **Not ready to build.** |

## What to keep

- Research is the place to check stocks and start a run. Markets is not a required stop.
- After start, focus the first stock in that batch. Do not leave the old stock on screen.
- A rating badge appears only when a final recommendation is saved.
- Full Portfolio Manager text stays behind one disclosure.
- Delete, backfill, and advanced filters stay behind one toggle.
- Orders keep a visible readiness line, one pause control, and a confirm plus a receipt.
- Workflows: Fit all, click a node, in-app unsaved dialog.
- Settings: models first, restore in its own danger zone.
- Plain labels. Technical dumps stay in Technical record.
- Research, preparation, approval, and submission stay separate.

## Attacks on the blueprint

### 1. The height budget is a claim, not a drawing

On a 1080p browser the useful height is already under 1000px. The blueprint then stacks:

- a two-line "48px" account bar
- a 40px workspace bar
- a two-line "44px" research launch bar
- a list-tool row
- a tab row inside the detail pane

That is the 270px header the critique called cramped, redrawn with better names. Account equity also appears in the global bar, on Dashboard, and again on Portfolio. Three copies will drift. The critique already found three different AMZN prices on one screen.

**Cut:** one 32px app bar. No account numbers in it. One 36px page toolbar. Progress is a 6px strip, not a second sentence row. Symbol, price, and tabs live inside the right pane. They are data, not page chrome.

### 2. Checked is not the same as highlighted

`selectedSymbols` is the next research batch. `selectedSymbol` is the stock being read. The setup tab already says inspection does not change the batch (`renderResearch`, `app.js` line 744). The scale work says a filter must not silently change the batch.

The launch chip "AMZN, INTC + Add" blurs the two. A per-row Run button on Dashboard makes it worse: one click can start the wrong set.

**Rule:** Run always uses the checked set. If nothing is checked, Run is disabled and says why. Clicking a row only changes what you are reading. Say it once, in the toolbar: `2 checked to run · reading AMZN`.

### 3. Do not skip the research confirm dialog

`reviewResearch` (`app.js` line 182) already shows the count, models, New York trade date, duration estimate or an explicit "no estimate", and "places no orders". A long run can cross a trading day. The blueprint's Run button reads as one click.

Keep that dialog. Shorten the second paragraph. Do not replace it with a toast.

### 4. The new progress bar can lie in a new way

The live label is `${done} / ${n} latest stocks finished` (`app.js` line 712). `done` includes completed, incomplete, failed, cancelled, and interrupted. Cancelled fills the green bar. The line under it is already honest.

The blueprint's four segments drop incomplete and interrupted. A stock that finished with coverage gaps, or a run that was interrupted, would vanish into a nicer lie. There is no Stage 2/5 field. Do not invent one in the toolbar.

**Use the counts that exist:** completed, incomplete, interrupted, failed, cancelled, running, queued. One line: `3 completed · 21 cancelled · 0 failed · 0 running`. Remaining time only when `DeskLists.estimate` has samples. No samples means "No timing yet", not a fake hour.

### 5. Scorecards must be clipped saved text

Koyfin-style cards are the right idea only if the words already exist. They do not. Reports are prose. A card that says "Neutral-Bull" or "AWS backlog accelerating" is a new summary model. That is a new backend. Banned.

Show the saved rating only when status is completed and a final decision exists. For each analyst report, show the report name and the first two lines. Click opens that report. Bull and bear are the same: two clamped columns, not generated bullets. If a report is missing, the cell says Missing or Stopped. It does not borrow a rating from an older field.

### 6. Do not delete the trace

Activity is how the operator sees HTTP 429, cancel, and "Stopped before dispatch". The product principle is that the trace is the product. Move Activity to a tab named Activity. Filter it to the stock being read, with one "Whole run" toggle. Do not drop it to make Summary look clean.

### 7. "Draft order" is the wrong hop

`human-proposal` leaves Research and opens the proposal review on Markets. It does not open an Orders ticket. Approval and submit stay later, and approval still does not submit.

Replace the button label with **Prepare order**. Open the existing proposal review over the research page so the verdict stays visible. Do not navigate away. Do not pre-check Approve. Do not show Submit on that overlay.

### 8. Strategy Lab was prettied into a different product

The live lab is simulations plus experiments. A run needs a saved strategy revision, a retained history receipt, an explicit hindsight-or-recorded choice, and an immutable preview. Run stays disabled until that preview is exact. The blueprint replaces this with Template, two dates, a cash field, and "I understand this is a model".

That is easier to draw and unsafe to build. The 30-field wall is real. The fix is progressive disclosure of the real steps, not a toy backtester.

### 9. The 500-stock desk is already designed

`docs/ui-scale-research.md` is the density spec the blueprint never cites. Search, 25/50/100 pages, explicit "select visible", clear selection, and "filter does not change the batch" are shipped behavior. A frame that shows all 24 rows with no pager will regress the moment the universe grows. Phone layout stays out of scope. Desktop paging stays in.

### 10. Other bloat to delete before build

- Per-row Run on Dashboard. One Run, in the toolbar, on Research and Markets.
- Four analyst cards with borders. One scorecard table. Cards inside cards are how the page got fat.
- Alerts create-form glued to 45% of the inbox. Inbox is the job. New rule opens on demand.
- Settings gets a third navigation rail. Use the page toolbar tabs instead.
- Markets "Fundamentals" tab. Fundamentals live in Research reports. Do not add a tab with nothing behind it.
- Options: do not delete the evidence view. If the stock has no option evidence, disable the tab and say so.
- A second scroll inside the research list. One scroller per pane. Pages, not a nested box.
- `pageHeader` always prints a description paragraph (`app.js` line 388). Stop passing essays into it.

## Critique coverage

Solved means the corrected frames below cover it. "Blueprint only" means the original drawing claimed a fix that is incomplete or unsafe.

| ID | Problem | Blueprint | This review |
|---|---|---|---|
| U1 | Pick and run on Research | Claimed | Solved. Checked set plus confirm dialog. No Markets hop. |
| U2 | Focus first running stock | Claimed, plus a fake stage | Solved. Focus first symbol in the batch. Summary tab. No Stage 2/5. |
| L1 | Dashboard button clipped | Claimed | Solved. One-line empty state, one action, pane may scroll. |
| L2 | Huge empty performance icon | Claimed | Solved. 120px note, one capture action. |
| L3 | Sell badge with no verdict | Claimed | Solved. Badge only from a saved final rating. |
| L4 | Loading line sticks | Missed | Solved. Clear when load ends or the stock has no reports yet. |
| L5 | Diagram never draws | Happy path only | Solved. Error in the pane, with retry. Fit all is not a substitute. |
| L6 | Two pause phrases | Partial | Solved. One pair: Orders active / Orders paused. |
| L7 | Repeated nav icons | Named, not drawn | Keep. One distinct line icon per page. Text stays. |
| L8 | `human_proposal` | Claimed | Solved. Human proposal. |
| L9 | Raw run ID, nested scroll | Partial | Solved. Run ID in Technical record. One list scroller. |
| L10 | Setup button above heading | Partial | Solved in the lab frame. Load sources is step 1, under the heading. |
| L11 | Empty table header | Claimed for Portfolio | Solved. No column header when the table has no rows. |
| L12 | Three equal alert paragraphs | Partial | Solved. One status line. Rest in details. |
| L13 | AMZN / AMZN, unexplained unsaved | Missed | Solved. Hide the name when it equals the ticker. Unsaved means unsaved edits, or remove the note. |
| L14 | Pause and Resume both live | Partial | Solved. One button. The label is the action that applies. |
| P1 numbers | Portfolio raw numbers | Claimed | Solved. Same money, percent, and color helpers as Dashboard. |
| P1 jargon | atomic package, epoch | Partial | Solved in the main view. Epoch stays inside Technical record. |
| P1 chart | Close colors, no legend, no text | Partial | Solved. Hollow down candles, legend, recent-bars table. |
| P1 research box | Badge only | Claimed | Solved. Rating, date, one gap line, or "No completed research". |
| P1 history form | Ten controls | Too vague | Solved. One line. More opens the existing interval, dates, and adjustment. Default action is the existing 252-session baseline, not a new "1Y" invent. |
| P2 filters | Ten equal buttons | View menu | Solved. Four views in the menu: All, Checked, Needs research, Stale or missing. Rest under More. |
| P2 watchlist | All rows checked, overlap, double scroll | Partial | Solved. Never auto-check the universe. Bulk actions only when something is checked. One scroller. Pager stays. |
| P2 fake tabs | Every page | Contract only | Solved. Real tablist, arrow keys, 40px target, on every page that has tabs. |
| P2 quote age | `24989s old` | Clock only | Solved. `7h 31m old · market closed`. Stale uses the existing freshness rule, not a new one. |
| P2 HTTP 400 | No research chart error | Missed | Solved. "No saved research for this stock." Plus Run, if stocks are checked. |
| P2 thin boxes | Orders and positions | Merged, may clip | Solved. One bottom pane, tabs, one-line empty copy. |
| P2 portfolio lead | Three values, one banner | Four cards plus global strip | Solved. Three values on Portfolio. No global copy. |
| P2 performance dead end | Claimed | Solved. Says what creates a point. One capture action. |
| P3 options | Always shown | Deleted | Rejected. Disable with a reason when empty. |
| P3 chart weight | 13.9 MB, three prices | Missed | Solved. Chart loads for the focused symbol only, which is already the rule. Each price is labeled with its basis. |
| P3 timezone | UTC axis vs New York selector | Missed | Solved. Chart axis and selector both say America/New_York. |
| Orders confirm | No confirm, no receipt | Submit only | Solved. Submit, Cancel, and Replace each confirm exact terms, then show a receipt. Double-click does not send twice. |
| Orders blocker | Hidden in a drawer | Claimed | Solved. First blocker is always one visible line. |
| Review jumps away | Review opens Dashboard | Missed | Solved. Review stays on Orders. |
| Pause words | Three phrases | Partial | Solved. Pause new orders. Not "Stop Nautilus". |
| Disabled reason | Missing | Annotation, not UI | Solved. The disabled control's reason is the next line. |
| Pause note | Note shown but not sent | Missed | Solved. Hide the note unless the action stores it. |
| Order columns | Nine packed columns | Missed | Solved. Symbol, side, qty, type, status, action. Type is "Stop limit", not `STOP_LIMIT`. |
| Lab disclaimer | Folded away | One line | Solved. Always visible. Details holds the rest. |
| Lab wall | 12–30 fields | Toy form | Solved with the real four steps. Advanced stays closed. |
| Lab consent | 90 words | One checkbox | Solved. Three short lines and one confirm. |
| Lab working | No elapsed time | Missed | Solved. Status line includes elapsed time. |
| Lab choose explicitly | Extra friction | Missed | Solved. Say it once beside the first required choice. |
| Journal reload | Discards notes | Renamed, no confirm | Solved. Revert asks for the count. Disabled at zero. |
| Journal wall | 12 paragraphs | Decisions only | Solved. Outcomes and account history have frames. |
| Journal search | Redraws every key | Missed | Solved. Search applies when typing pauses. Focus stays. |
| Total return | Can be picked though unsupported | Missed | Solved. Disable it and say why. |
| Capture path | Prose across pages | Weak | Solved. One "Capture on Orders" action. |
| Alerts unread | Lost | Claimed | Solved. Count on the tab and the nav. |
| Price-age gap | Reads like a failure | Claimed | Solved. Neutral setup line. Not a red error. |
| Alert dropdowns | Six or more | Templates | Solved. Three templates. Advanced closed. |
| Alert research text | Unrelated copy in rules | Missed | Solved. Rules pane has rules only. |
| Alert IDs | Raw JSON rows | Partial | Solved. Name plus one plain line. Expand for the log. |
| Remove rule | No confirm | Missed | Solved. Confirm, then a done line. |
| Settings wall | 20 equal fields | Claimed | Solved. Provider and models. Advanced closed. |
| Restore danger | Mixed with status | Claimed | Solved. Health chips, then backup, then a separate danger zone. |
| Nautilus controls | Not on the connection page | Missed | Solved. Start, stop, and status sit on Broker & connection. |
| Engineer words | epoch, generation, field names | Missed | Solved in the main view. Details keep the exact names. |
| Settings nits | UUID twice, hard-coded port, funding twice | Missed | Solved. Account ID once. Paths come from the running profile. Funding once. |
| Research progress | Green 24/24 | Incomplete | Solved in attack 4. |
| Research chrome | 270px above 3 rows | Recreated | Solved in the corrected Research frame. |
| Summary essay | Not a summary | Cards may invent text | Solved in attack 5. |
| Delete bar | Always on | Behind Edit | Solved. |
| Report buttons | Nine equal buttons | Activity dropped | Solved. Summary, Debate, Reports, Sources, Activity. |
| Sources | Bare URLs, all "News analysis" | No row frame | Solved. Domain, date, report name. |
| Disposition words | `needs_review` | Claimed | Solved. Needs review. |
| Stage markers | DESIGN.md promises them | Fake Stage 2/5 | Solved. Per-stock status is the marker. Do not draw five stages the run does not report. |
| Proposed synthesis | Wrongly expected on Research | Left on Portfolio | Keep on Portfolio. Frame added. |
| Fit all | Clipped diagram | 55% example contradicts Fit all | Solved. Fit all is the default. 55% is not "fit". |
| 94 prompts | Dropdown remains | Not solved | Solved. Click the node. Search is inside the editor, not the golden path. |
| Unsaved dialog | Native confirm | Mentioned, not drawn | Solved. |
| Themes 1–7 | Tabs, reasons, plain words, chart text, confirm, disabled reasons | Partial | Covered by the rules and the stories below. |

## What the other desks actually do

Checked 28 October 2026. These are layout lessons. They are not permission to add their features.

- **Fidelity Active Trader Pro.** Linking means a symbol change updates the linked quote and chart. Sidebars hold tools so the workspace stays uncluttered. Source: [Getting Started help](https://www.fidelity.com/products/atbt/help/ActiveTraderTools_Getting_Started_Help.html). We have one browser window, not detachable tools. Copy the link. Do not build a window manager.
- **IBKR Mosaic.** One workspace holds watchlist, chart, portfolio, order entry, and order monitor. Windows share a symbol by color group. Source: [Mosaic layout](https://www.ibkrguides.com/traderworkstation/mosaic-layout.htm), updated 13 November 2025. Do not copy the always-visible transmit ticket. Our order path is separate on purpose.
- **TradingView.** The watchlist is a narrow metric list. Symbol search is always available. Details open beside or below the list, not on another page. Source: [Watchlists](https://www.tradingview.com/support/solutions/43000745825-mastering-the-tradingview-watchlists/). This is the Research and Markets split. It is not a reason to put Run on every row.
- **Koyfin and Fiscal.ai.** Public comparisons describe Koyfin as a snapshot and chart desk, and Fiscal.ai as a question box. Copy the snapshot header: price, change, and verdict on one row. Do not add a chat pane. Do not treat comparison blogs as proof of a feature.
- **Our own scale note.** Fidelity's list-linking and TradingView's scoped scan were already used to justify search, paging, and "filter does not change selection" (`docs/ui-scale-research.md`). The redesign inherits that. It does not restudy it into a 24-row picture.

## Corrected rules

1. Locked page chrome is 32px plus 36px plus a 6px status strip. Anything else scrolls inside a pane.
2. Account numbers live on Dashboard and Portfolio only.
3. One primary action per page. Everything else is quiet or behind More, Manage, or Advanced.
4. Checked stocks are the batch. The highlighted stock is the reading. Never mix them.
5. Run opens the existing confirm dialog. It places no orders.
6. After confirm, focus the first symbol in that batch, scroll it into view, and open Summary. Clear any loading line when the load ends.
7. Progress uses the seven live counts. Cancelled is not finished.
8. A rating prints only with a saved final recommendation.
9. Summary text is clipped from saved reports. No new summary model.
10. Activity stays. Sources stay. Technical record holds IDs, hashes, and JSON.
11. Prepare order opens the existing proposal review. It does not approve or submit.
12. Strategy Run stays disabled until the exact preview is saved. Say why.
13. Paging, search, and explicit selection survive on every long list.
14. Empty states are one line and one action. No column header on an empty table.
15. Disabled controls show the reason on the next line.
16. Submit, Cancel, Replace, journal revert, and delete rule confirm the exact thing, then show a done line.
17. Real tabs everywhere. One icon per nav item. One pause phrase.
18. Do not add backend fields, windows, or actions to justify a frame.

## Stories that were missing

| ID | Story | Done when |
|---|---|---|
| US-13 | As Alex, checking a stock adds it to the next run. Highlighting a stock only changes the page I am reading. | Toolbar says `N checked to run · reading SYMBOL`. Run uses the checked set only. |
| US-14 | As Alex, I review models, trade date, and the duration note before a run starts. | The existing confirm dialog opens on Research. No Markets hop. No estimate is invented. |
| US-15 | As Alex, a 500-stock universe still pages. | Search and 25/50/100 pages remain. Filter does not change the checked set. |
| US-16 | As Jordan, I can open the run trace for this stock. | Activity tab stays. It defaults to the focused stock. Whole run is a toggle. |
| US-17 | As Jordan, the scorecard never invents a sentence. | Cells are clipped saved reports, or Missing. |
| US-18 | As Alex, Prepare order does not approve or submit. | Existing proposal review opens over Research. Submit is not on that surface. |
| US-19 | As Morgan, I cannot run a simulation from an unsaved form. | Run stays disabled until the immutable preview is the one on screen. The reason is visible. |
| US-20 | As Jordan, every chart has a table of the same numbers. | Dashboard, Markets, Performance, Strategy Lab, and Journal account history each have a text table. |
| US-21 | As Jordan, a cancelled stock never wears a Sell badge or a stuck loading line. | Status word only. Loading line clears. |
| US-22 | As Alex, quote age is a clock phrase, and each price says what it is. | No raw seconds. Last, bar close, and research reference are labeled. |
| US-23 | As Morgan, a diagram that fails tells me it failed. | The pane shows the error and Retry. It does not spin on Rendering. |
| US-24 | As Alex, a disabled button tells me the one reason. | Next line, not a tooltip and not a collapsed essay. |

Personas stay the three in the blueprint. Alex also refuses any control that approves or submits from Research. Jordan's job includes the cancelled-run recovery, not only reading essays. Morgan's job includes the preview gate, not only a prettier graph.

## Corrected wireframes

Example numbers are the observed paper desk: PNIS, 24 stocks, 3 completed, 21 cancelled. They are not a claim that those ratings are current.

### App bar, every page

```text
+----------------------------------------------------------------------------------+
| PAPER DESK   Find symbol [________]   Orders: Active   Alerts 0   Nautilus: On |
+------------------+---------------------------------------------------------------+
| Dashboard        | PAGE TOOLBAR (36px): title, tabs, one primary action         |
| Markets          +---------------------------------------------------------------+
| Research         |###############################################################|
| Portfolio        |# 6px status strip: run, pause, or the one blocker           #|
| Orders           +---------------------------------------------------------------+
| Strategy lab     |                                                               |
| Journal          |              panes fill the rest; the page does not scroll   |
| Alerts           |                                                               |
| Workflows        |                                                               |
| Settings         |                                                               |
|                  |                                                               |
| Market: Closed   |                                                               |
+------------------+---------------------------------------------------------------+
```

No equity in this bar. No second sentence. Connection and market state stay in the rail, where they already are.

### Dashboard

Click a row to link the chart and the research snippet. There is no Run on the row. Empty panes are one line. The bottom-left pane uses tabs so Positions and Orders cannot clip each other.

```text
+------------------------------------------+--------------------------------------+
| WATCHLIST 24   [Search] [View v] [Page]  | AMZN  $252.51 last  +1.14%  16:00 ET |
| none checked                             | [1D] [1W] [1M]  [Legend] [Bars table]|
+------------------------------------------+--------------------------------------+
| SYM     LAST      CHG%    RESEARCH       |                                      |
| AMZN *  $252.51   +1.14%  Hold           |           chart, hollow down candles |
| INTC    $22.40    -0.85%  Underweight    |                                      |
| TER     $108.12   -1.40%  Sell           |  [v Recent bars]                     |
| AAPL    $231.10   +0.42%  Cancelled      |                                      |
+------------------------------------------+--------------------------------------+
| [Positions 0] [Open orders 0]            | AMZN research          [Open Research]|
+------------------------------------------+--------------------------------------+
| No open positions.                       | HOLD · completed 28 Oct · 1 news gap |
| [Research a stock]                       | No final text until you open it.     |
+------------------------------------------+--------------------------------------+
```

Cancelled is the word Cancelled. It is not a red Sell. If there is no completed research: `No completed research. Last run cancelled.`

### Markets

```text
+------------------------------------+-------------------------------------------+
| PNIS 24  [Search] [View v] [Manage]| AMZN · Amazon.com   $252.51 last · 16:00 ET|
| 0 checked                          | [Chart] [Bars] [Options: none] [Run 0]    |
+------------------------------------+-------------------------------------------+
| SYM    LAST     CHG%   BARS        |                                           |
| AMZN * 252.51   +1.14% 1,255       |              focused chart only           |
| AAPL   231.10   +0.42% Missing     |                                           |
| ... one scroller, pager at foot    | No bars for AAPL · [Get 252 daily bars]  |
|                                    | [More: interval, dates, adjustment]       |
| Manage on: checks, Select page,    | Last $252.51 IEX · Bar close labeled     |
| Clear, Remove. Run uses checks.    | Research HOLD is a research price,       |
|                                    | not the last trade.                      |
+------------------------------------+-------------------------------------------+
```

Run is disabled at 0 checked. Reason: `Check stocks to run. This row is only the chart.` Options stays, disabled, with `No option evidence for this stock.` Company name hides when it repeats the ticker. Unsaved appears only when the index edit is unsaved.

### Research

This is the page. Chrome above the split is the app bar, one toolbar, and the 6px strip.

```text
+----------------------------------------------------------------------------------+
| Research   [Search] [Unfinished 21] [Manage]     2 checked · reading AMZN      |
|                                        [Run research (2)]  disabled until checks|
+----------------------------------------------------------------------------------+
|###### 3 completed · 21 cancelled · 0 failed · 0 running · No timing yet ########|
+---------------------------+------------------------------------------------------+
| LIST                      | AMZN  $252.51 last  +1.14% · quote 16:00 ET          |
| one scroller + pager      | [Summary] [Debate] [Reports] [Sources] [Activity]    |
+---------------------------+------------------------------------------------------+
| SYM    STATUS     RATING  | HOLD · 28 Oct 19:42 · final decision saved          |
| AMZN * Completed  Hold    | Coverage 4/4 · News gap: rate limit                 |
| INTC   Completed  Underwt |-----------------------------------------------------|
| TER    Completed  Sell    | REPORT            FIRST LINES                        |
| AAPL   Cancelled  —       | Market            clipped saved text, or Missing    |
| ...                       | Fundamentals      clipped saved text                 |
|                           | News              Stopped · HTTP 429                 |
|                           | Social            Laya result, not a trade signal    |
|                           |-----------------------------------------------------|
|                           | BULL (saved)              BEAR (saved)               |
|                           | two lines                 two lines                  |
|                           | [Read full decision]                                 |
|                           | Disposition [Needs review v]  Note [____] [Save]    |
|                           | [Prepare order]  does not approve or submit         |
+---------------------------+------------------------------------------------------+
```

- Launch focuses AMZN if AMZN was first in the checked batch, even when the old selection was TER.
- While AMZN is running and has no reports: `Running · no verdict yet`. No Sell. No loading line left behind.
- Manage reveals delete checks. Those checks are not the run checks. Label them `Delete`.
- Confirm dialog, over this page: count, models, trade date, estimate or "No timing yet", `Places no orders`, Start.
- Sources rows: domain, saved date, report name. Not a raw URL labeled News analysis.
- Activity defaults to AMZN. Whole run is a toggle. Errors are visually distinct.

### Portfolio

```text
+----------------------------------------------------------------------------------+
| Portfolio   [Positions 0] [Proposed] [Performance]              [Refresh account]|
+----------------------------------------------------------------------------------+
|###### Clean · Alpaca Paper matches the local ledger · 20:35 ET #################|
+----------------------------------------------------------------------------------+
| Equity $100,000.00     Cash $100,000.00     Unrealized P/L $0.00                |
|                                                                                  |
| No open positions.                                                               |
| [Review proposed basket]                                                         |
| [> Technical record]                                                             |
+----------------------------------------------------------------------------------+
```

Performance with no points: a 120px note, `Needs saved position captures. None yet.` and `[Capture current account snapshot]`. No giant icon. No table header.

Proposed, same toolbar, no second essay:

```text
+-------------------------------------------+--------------------------------------+
| HUMAN BASKET                              | MODEL SYNTHESIS                      |
| SGOV  Buy 1  Deferred   [Prepare order]   | Not run. Uses latest completed       |
|                                           | research and cached dated prices.    |
|                                           | Capital [$100,000] [Model portfolio] |
|                                           | Fails stay failed. No invented shares|
+-------------------------------------------+--------------------------------------+
```

Stage to Orders is not on this row. Prepare order is the existing proposal. A model allocation is not an order.

### Orders

```text
+----------------------------------------------------------------------------------+
| Orders   [Ticket] [Open 0] [Proposals 1] [Fills]     [Orders active: Pause]    |
+----------------------------------------------------------------------------------+
|###### Ready · cash $100,000.00 · cash account, no shorting #####################|
+--------------------------------------+-------------------------------------------+
| PREPARE                          40% | OPEN ORDERS                               |
| Symbol AMZN   Last $252.51 IEX       | No open orders.                           |
| Side ( ) Buy  ( ) Sell               |                                           |
| Qty [10]  Type [Limit v]  TIF [Day]  | PROPOSALS                                 |
| Limit [252.00]                       | SGOV Buy 1  Deferred  [Open in ticket]    |
|                                      |                                           |
| Cost about $2,520 · cash after shown | LAST RECEIPT                              |
| Research: HOLD is context, not an OK | None this session.                        |
|                                      |                                           |
| [Approve exact terms]                | [> Technical record]                      |
| [Submit to Alpaca Paper]             |                                           |
| Submit disabled: not approved.       |                                           |
+--------------------------------------+-------------------------------------------+
```

Approve does not submit. Submit, Cancel, and Replace each show the exact terms and wait for a second press. The receipt names time and broker id, or the exact failure. The note field hides when the action does not store a note. Review never leaves Orders.

### Strategy lab

```text
+----------------------------------------------------------------------------------+
| Strategy lab   [Simulations] [Experiments]     Simulations are not account P/L  |
+----------------------------------------------------------------------------------+
|###### Results do not prove a fill, a return, or a broker outcome. [Details] ####|
+--------------------------------------+-------------------------------------------+
| 1 Load sources                       | RESULT                                    |
| [Load saved plans and data]          |                                           |
| Status: not loaded / elapsed 0:12    | Equity chart, or the same numbers         |
|                                      | in a table.                               |
| 2 Strategy revision                  |                                           |
| [Saved revision v]  one symbol       | Return, drawdown, trades: — until a run   |
| [> Parameters]                       | finishes. Failed is not zero.             |
|                                      |                                           |
| 3 History and window                 | RUNS                                      |
| Retained receipt, not a vague 1Y     | Open a saved run. Compare needs two.      |
| Dates, cash, hindsight called out    |                                           |
| [> Walk-forward, fees, search]       |                                           |
|                                      |                                           |
| 4 Preview, then run                  |                                           |
| [Save preview]                       |                                           |
| [Run] disabled: preview not saved.   |                                           |
+--------------------------------------+-------------------------------------------+
```

No SMA template unless that saved strategy already exists. No 90-word checkbox. Three lines: isolated simulation, cached bars only, places no broker order. Then one confirm.

### Journal

```text
+----------------------------------------------------------------------------------+
| Journal   [Decisions] [Outcomes] [Account history]   [Search] [Revert 0]        |
+-------------------------------------------+--------------------------------------+
| DATE   SYM   SOURCE          STATUS       | SGOV · Human proposal · 28 Oct       |
| 28 Oct SGOV  Human proposal  Deferred     | Buy 1 · not submitted                |
| 28 Oct AMZN  AI research     Reviewed     | Disposition [Deferred v]             |
|                                            | Notes [________________]             |
|                                            | [Save] [Prepare order]               |
|                                            | [> Technical record]                 |
+-------------------------------------------+--------------------------------------+
```

Revert at 0 is disabled. Above 0, it asks `Discard N unsaved notes?` Outcomes: one row per group, details closed. Account history: chart plus a metric line, tables collapsed, `[Capture on Orders]`. Total return stays disabled, with the reason beside it.

### Alerts

```text
+----------------------------------------------------------------------------------+
| Alerts   [Inbox 1] [Rules 0]              Delivery: browser only    [New rule]  |
+----------------------------------------------------------------------------------+
|###### Price-age limit not set · market closed · [Set 15 minute limit] ##########|
| [Mark read] [View v]                                                             |
| Service restarted · 25 times · latest 28 Oct 20:14 · [Expand]                    |
| Price-age limit not set · setup, not a failure                                  |
+----------------------------------------------------------------------------------+
```

New rule opens a drawer: Price above, Price below, Data stale. Advanced closed. Remove asks first. The rules page does not contain research copy.

### Workflows

```text
+----------------------------------------------------------------------------------+
| Workflows   [Default v] Active for new research   Saved                          |
| [Fit all] [Preview] [Save] [Use for new research]                                |
+-------------------------------------------+--------------------------------------+
| DIAGRAM                         full height| Market Analyst · Fast               |
| Fit all is the opening zoom.               | [Prompt] [Tools] [YAML]             |
| If draw fails: Diagram failed. [Retry]     | Click a node to load its prompt.    |
| Click a node. Details is inline.           | File search is here, not a 94-list  |
| Escape closes details.                     | in the toolbar.                     |
|                                            | [Save] disabled until edits exist.  |
+-------------------------------------------+--------------------------------------+
```

Leaving with edits uses `Discard changes / Keep editing`. "Workflow loaded" clears on the next edit or after a few seconds. A disabled Save is not green.

### Settings

```text
+----------------------------------------------------------------------------------+
| Settings   [Models] [Broker & connection] [Safety] [Backup]          [Save]     |
+----------------------------------------------------------------------------------+
| Provider [Codex v]  Connected                                                    |
| Deep model [____ v]  Reasoning [High v]                                          |
| Fast model [____ v]  Reasoning [Medium v]                                        |
| [> Budgets, concurrency, social screening]                                       |
|                                                                                  |
| Save disabled: no unsaved changes.                                               |
+----------------------------------------------------------------------------------+
```

Broker & connection holds keys, Nautilus start/stop, and one funding note. The install path and port come from the running profile, not a hard-coded 8098. Safety uses `Orders active` / `Orders paused`. Backup shows three health chips, export, then a separate danger zone with the typed phrase. Account ID appears once.

## Persona check on these frames

**Alex.** Can check AMZN and INTC on Research, read the confirm dialog, and watch AMZN update without a Markets hop. Cannot press Run on a watchlist row by mistake. Cannot reach Submit from the verdict.

**Jordan.** A cancelled row says Cancelled, not Sell. The bar cannot turn 21 cancels into a full green success. The trace is still one tab away. Scorecard cells can be empty. They cannot be fiction.

**Morgan.** The lab still has a preview gate. The diagram can fail visibly. The prompt opens from the node. The 94-file dropdown is no longer the way in.

## Do not invent these

- Stage 2/5, analyst adjectives, or bull/bear bullets that are not in the saved report.
- A Fundamentals tab, a chat box, or detachable broker windows.
- An SMA starter, a 1Y fetch that skips adjustment, or a duration when no completed run matches.
- A Draft order button that approves, submits, or skips proposal review.
- Auto-checking the universe. Silent selection changes when the filter changes.
- New backend fields. If a frame needs data the desk does not store, cut the frame.

## Questions for the merge, not for a rebuild

- Is Prepare order allowed to open the current proposal review as an overlay, or must that review stay on Markets until a later pass? Either way, it must not submit.
- Should the first visit clear a saved "all 24 checked" selection, or only stop new universes from starting fully checked? I recommend both: never persist a selection that equals the whole universe unless the operator used Select all.

## Source

- `docs/ui-redesign-blueprint.md`, `docs/ui-design-critique.md`, `docs/ui-scale-research.md`
- `tradingagents/web/static/app.js` lines 181–182, 388, 712, 741–744
- `PRODUCT.md`, `DESIGN.md`
- Fidelity Active Trader Pro getting started help, IBKR Mosaic layout guide, TradingView watchlist help, accessed 28 October 2026
- memory://knowledge/projects/tradingagents/tradingagents-primary-led-ux-and-documentation-work
