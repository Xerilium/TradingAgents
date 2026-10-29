# UI redesign blueprint: Sonnet review

Reviewer: Sonnet. Scope: design review only. No application code was changed.
Reviewed: `docs/ui-redesign-blueprint.md` against `docs/ui-design-critique.md`,
`docs/ui-scale-research.md`, the real UI source in `tradingagents/web/static/`
(`index.html`, `app.js`, `workflows.js`, `ui-*.css`), and a read-only snapshot of the
live compact state (`/api/state?compact=1`). The live service was not changed.
Design rules used: `PRODUCT.md`, `DESIGN.md` and the Impeccable `shape`, `layout`,
`distill` and `operate` playbooks (Operate mode).

---

## 1. Verdict

The blueprint is a strong start. It fixes the right headline problems: the research
page has no stock picker, data gets a small share of the page, and there are too many
labels and boxes. Its shell, its anti-clutter budget and its personas are good.

It is **not ready to build from**. Four problems would bring back the dog's breakfast:

1. **Several wireframes show data the backend does not have.** Company names, analyst
   scorecards ("Neutral-Bull"), a "Stage 2/5" live stage, Day P/L, and a Fundamentals tab
   have no data source. `PRODUCT.md` says to drop elements without a real source.
2. **The research launch flow skips safeguards that exist today.** The blueprint's one
   click "Run Research (N)" ignores the review dialog (workload, ETA, models, "places no
   orders") and the revision check on the saved configuration.
3. **It does not define one focus symbol and one batch selection.** Today there are two
   separate ideas (the inspected stock and the checked stocks). Mixing them up is the
   root cause of the user's two research complaints. The blueprint repeats the mix.
4. **It leaves out capabilities that already exist.** Multiple watchlists, saved
   screens, notes, drawings, column choices, option chains, the Proposed portfolio,
   baskets, retry and delete of research, recovery after restart, and 1,000 symbol
   paging.

The fixes are small and do not need new backend features. Sections 2 to 6 list them.
Section 8 gives upgraded wireframes for all ten workspaces.

### Top fixes, ranked

| # | Fix | Why |
|---|-----|-----|
| P0-1 | Define one **focus symbol** and one **batch set** with a visible "N selected" chip that follows you across tabs. | Fixes research complaint U1 and U2 at the root. |
| P0-2 | Remove every element with no data source (company name, analyst scorecard, stage, Day P/L, Fundamentals tab). Use real substitutes from section 2. | Honest data, `PRODUCT.md` rule. |
| P0-3 | Keep the research **review dialog** before launch. Make it small and inline instead of a modal wall. | Safety: ETA, models, revision check. |
| P0-4 | Make "Prepare order" stage a **proposal** (the existing model), not a pre-filled ticket. Keep prepare, approve and submit as three visible steps. | Separate approval and submission is a product rule. |
| P0-5 | Add paging and a result cap to every table wireframe. Universe can be 1,000 symbols. | Scale already verified in `ui-scale-research.md`. |
| P1-1 | One shared **stock table** component used by Dashboard, Markets and Research with per-page default columns. | Three bespoke lists today. |
| P1-2 | Merge the three status areas (sidebar footer, topbar, page notices) into one header strip. Delete the footer. | Chrome budget. |
| P1-3 | Add first-run, recovery and paused states for every workspace. | Missing stories. |
| P1-4 | Keep the three non-negotiable safety notices as one line each (see section 4). | Critique asked for them. |
| P1-5 | Render by pane, not by whole `#main`. | Linked panes break if the whole page is rebuilt. |

---

## 2. Data reality check

I compared every number and label in the blueprint wireframes with what the backend
returns. "Source" means a field or endpoint that exists today.

| Blueprint element | Reality | Change |
|---|---|---|
| Company name next to a ticker ("Amazon.com Inc.") | `company_names` is empty in the live state. | Show the ticker only. Show a name only if the field is present. Never type names into wireframes as if real. |
| Quote change "+1.14%" | Quote has `price`, `change_pct`, `timestamp`, `age_seconds`, `session`, `stale`, `error`. Values in the blueprint are invented. | Wireframes must use placeholders like `±0.00%`. Keep a "stale" and "age" marker, they are real. |
| Day P/L in the top bar | No day P/L field. Account has equity, cash, buying power, long market value. | Replace with the four real account values. Add "Unrealized P&L" only from positions when present. |
| Four analyst scorecard with verdict text ("Neutral-Bull", "Above 50d SMA") | The backend stores prose reports: `market_report`, `sentiment_report`, `news_report`, `fundamentals_report`, plus `investment_plan`, `investment_debate_state`, `trader_investment_plan`, `risk_debate_state`, `final_trade_decision`. No structured per-analyst verdict. | Show the four reports as tabs with the **first paragraph as an excerpt**, labelled "excerpt". Show real structured values only: `rating`, `trade_date`, `status`, `completion_gaps`, `elapsed_seconds`, social stance counts. |
| Bull and bear bullet summary | The debate state has history and a judge decision. No bullet summary. | Two column view of the saved debate text (the existing `reportDebate`). No generated bullets. |
| "Stage 2/5: Bull vs Bear" live progress | No stage field. Run has `counts`, per-symbol `status` and 40 of 500 recent `events` (kind `source` or `tool`). | Progress is **stocks done of total**, plus the status words (running, queued, completed, incomplete, failed, interrupted, cancelled). Show the last event line as plain text. |
| Fundamentals tab on Markets or instrument | No fundamentals feed outside the research report. | Remove. Fundamentals appear only inside the saved report. |
| SMA20 overlay promise | Chart indicators are saved definitions (critique lists 13). | Say "indicators" and show only what the chart definitions offer. |
| One click "Run Research (N)" | `reviewResearch()` opens a workload and ETA review. The server rejects a stale `config_revision`. | Keep a review step (section 8.4). One extra click is the safety cost, and it is small. |
| Typing any symbol in the launch bar | Research only runs for the configured universe. Body is `{symbols, config_revision}`. | The picker searches the **universe**. A symbol outside it shows "Not in universe. Add in Settings > Universe" with a link. |
| "Draft order opens Orders pre-filled" | Today: research report opens a **proposal** with human limit price, impact, evidence readiness, then approval, then separate submission. | Rename to "Prepare order". It stages a proposal and shows it in Orders > Drafts. Keep the two later steps. |
| "Order ticket Step 1 Approve / Step 2 Submit" | Correct idea. The real ticket has more fields: side, quantity, order type, limit and stop, session, duration, exit plan, evidence scopes, linked research. | Keep the two steps. Show the real fields in a collapsed "Terms" row and expand on edit. Do not drop fields. |
| Flat 24 row tables, no pager | Lists have 25, 50 or 100 per page and a universe of up to 1,000. | Every table wireframe shows a pager and result count. |
| Ten icons | Today five tabs share one icon (critique L7). | Keep the idea. Each tab gets its own icon. |
| CodeMirror editor for Workflows | New dependency. The current editor is a plain file editor with a diagram. | Keep the existing editor. Only add a library if a short spike proves it is worth it. |
| Per-analyst "Confidence %" | Not a field. | Remove. |
| "Research age" colour | `trade_date` is real. `DeskLists.dateNY` gives today in New York. | Show "Researched 2 days ago". Colour only by a rule the user sets. Do not invent thresholds. |

---

## 3. Gaps in the blueprint

### 3.1 Flawed assumptions

1. **"Click a row updates everything."** It needs one named focus symbol. Today
   `selectedSymbol` is shared, but `selectedRunId` follows it, and the batch selection
   (`selectedSymbols`) is separate and only set on Markets and Dashboard. Research Setup
   only links to `#markets`. The blueprint does not say which one a click changes.
2. **Research can start from the research page.** True, but the rule must be written:
   the batch set is chosen **on the research page** (picker over the universe), and the
   same set is shown on Markets. Both pages edit the same set.
3. **Research history on the Research page.** Only the latest result per ticker is kept.
   No history, no resume, no replay. Any "previous runs" or "compare to last time"
   control is out of scope. The blueprint's Research queue is fine if it means the
   latest run state per ticker.
4. **Live updates.** Idle polling was removed after traffic problems. Polling runs only
   during an active research run. "Live" widgets must update from a refresh, a run poll,
   or a user action.
5. **The 48 px bar can hold search, five KPIs, execution state and alerts** at 1280 px
   wide with 1,000 symbol search. It cannot hold all of them at 1024 px. Define what
   collapses first (section 4).

### 3.2 Chrome and clutter still left

* The blueprint keeps a top bar **and** keeps connection state in the sidebar bottom and
  a page header with a description line and a toolbar. That is four horizontal bands
  before data starts. The user's complaint was exactly this.
* A footer exists today. The blueprint does not remove it.
* Page header descriptions ("Review exact saved terms...") are explanations, not
  navigation. Move them into one help popover per page.
* "Orders only" notice (`#order-status`) is a fifth band. Fold it into the header strip.
* Three safety paragraphs appear on several pages. Keep one sentence each, in the one
  place they matter (section 4).

### 3.3 Cross-tab workflows that break

| Flow | Break in the blueprint | Fix |
|---|---|---|
| Markets → Research | Research page has its own picker but Markets still has "Review research for selected stocks". The blueprint does not say they share a set. | One shared batch set. The chip shows "3 selected" on both pages. |
| Research launch → review | After launch, today the panel keeps the old stock (U2). | After launch, focus moves to the first stock in the batch and the queue shows the run. The focus rule is written down. |
| Research → Orders | "Draft order" jumps to Orders. Today it goes to Markets first, then opens a proposal with research context (run id, report key, revision). | Stay on the research page. Show a "Prepare order" side drawer that stages the proposal. Link "Open in Orders". |
| Portfolio Proposed → Orders | Blueprint shows "Stage all". Real flow stages sized whole-share proposals one at a time, each with its own approval. | "Stage as proposals (N)" creates N draft rows. No batch approval. |
| Dashboard attention → source | "Review this order" jumps to Dashboard today (critique). The blueprint does not name the target. | The link opens Orders > Open orders with the order focused. |
| Journal ↔ Research disposition | Disposition lives under Journal and the blueprint adds one on Research. Two editors. | One editor (Journal). Research shows it read-only with "Edit in Journal". |
| Alerts → symbol | Alert rows do not say where "open" goes. | Opens the symbol on Markets with the chart tab and the alert line visible. |
| Settings → research launch | Out of universe symbol leads to a dead end. | "Add to universe" link goes to Settings with the symbol prefilled (revision saved). |
| After restart | `commands.recovery_required` has no home in the blueprint. | A banner in the header strip: "Recovery needed" with one action that opens Orders. |

### 3.4 Missing from the blueprint (existing capabilities)

Multiple watchlists and the Shortlist, saved screens and saved scans, per-stock notes,
chart drawings and indicators, column order and visibility, option chain and option
packages (account is options level 3), the Proposed portfolio and its session only
status, baskets (targets, impact, drafts), retry failed and "select failed or unfinished
for a new run", delete research with preview, Stop run, universe CSV import with preview
(merge or replace), Nautilus start and stop, and recovery.

---

## 4. Chrome budget (corrected)

Rule: **at most 88 px of fixed chrome above data** on a 1080 px screen
(one 40 px header strip, one 40 px page toolbar, 8 px gap). The sidebar is 56 px wide
(icons) and expands to 200 px on hover or pin.

Header strip content, left to right, with what collapses first when width is tight:

| Slot | Content | Collapses at |
|---|---|---|
| Page title | "Research" | never |
| Symbol search | "Find a symbol" (Ctrl+K) | becomes an icon below 1100 px |
| Account | Equity · Cash · Buying power | Buying power hides below 1280 px |
| Market | "Closed" or "Open · pre" | icon only below 1100 px |
| Connection | Nautilus and broker dot with word on hover | dot only |
| Orders gate | "New orders paused" or "Not paused" (button) | never |
| Alerts | bell with count | never |
| Refresh | "Updated 10:42" and a button | time hides first |

Removed: sidebar bottom block, footer, page description lines, separate order notice.
Banners (recovery, stale data, failed state) appear **under** the strip, are one line,
and are hidden when there is nothing to say.

Three safety sentences stay, one line each, in the place they apply:

1. Research page, beside Run: "Research places no orders."
2. Orders ticket: "Approval and submission are separate. Nothing is sent until you submit."
3. Strategy lab results: "Scenarios are not broker fills."

---

## 5. One focus symbol, one batch set

The whole UI depends on two small ideas. Write them down and enforce them.

| Concept | Meaning | Changed by | Shown as |
|---|---|---|---|
| **Focus symbol** | The one stock the detail panes show. | Click a row, search, link from an alert or order. | Highlighted row, symbol in every detail pane title. |
| **Batch set** | The stocks an action will use (research run, add to list, export). | Row checkboxes, "Select filtered", picker on Research, "Select failed or unfinished". | "N selected" chip in the toolbar, same on every page, with Clear. |

Rules:

1. Clicking a row **never** changes the batch set. Checking a box **never** changes the focus.
2. The batch set survives tab changes and is cleared only by Clear or after a launch
   that you confirm ("Keep selection" is a checkbox in the review dialog, default off).
3. Every action button names its scope: "Research 3 selected" vs "Open AMZN research".
4. After a launch, focus moves to the first stock of the run and the Research queue
   opens with that run (fixes U2).
5. Run, report key and revision follow the focus symbol and are never stored separately
   from it. No stale run id with a new symbol.

Why this matches the leaders: IBKR, Fidelity and TradingView all use link groups, a
"link colour" or a symbol bar so many panes follow one symbol. None of them uses the
click to change a checkbox set.

---

## 6. Personas and user stories

The blueprint's three personas (Alex, Jordan, Morgan) stay. Add two and one anti
persona.

| Persona | Needs | Risk if missing |
|---|---|---|
| **Sam, first-run operator** | Empty account or empty universe. Needs to know what to do first. | A blank grid of "Unavailable". |
| **Riley, recovery operator** | App restarted, order state unclear, broker or Nautilus offline. | Hidden failure; duplicate submit. |
| **Not a persona: autonomous trader** | Nobody uses this to place trades on autopilot. | Do not design "one click trade". |

### New stories with acceptance criteria

| ID | Story | Acceptance |
|---|---|---|
| US-13 | As Sam, I see what to do first on an empty desk. | Each page with no data shows one sentence and one button (for example "Add stocks to the universe"). No "Unavailable" grid. |
| US-14 | As Alex, I choose which stocks to research on the Research page. | Picker searches the universe, supports "Select filtered", paste a list, and "Select failed or unfinished". Shows the count and an estimated time (when samples exist). |
| US-15 | As Alex, I see which stocks failed and retry only those. | Queue filter "Failed" and a "Retry failed (N)" that fills the batch set and opens the review dialog. |
| US-16 | As Alex, I stop a run in progress. | "Stop run" is visible while running, asks once, and shows "cancelled" per stock afterwards. |
| US-17 | As Alex, I delete a saved report safely. | Delete shows a preview of what is removed and needs one confirm. |
| US-18 | As Jordan, I keep several watchlists and a Shortlist. | Switcher in the table toolbar, "Add to list" from the batch set, list management in a menu. |
| US-19 | As Jordan, I save a screen and run it again. | "Save screen" on the Screener. Saved screens list. Results are dated. |
| US-20 | As Jordan, I write a note on a stock. | Note field in the detail panel, saved with the workspace store, visible as a dot in tables. |
| US-21 | As Jordan, I draw on a chart and set an alert from the drawing. | Drawing tools and "Alert from drawing" exist today. Keep them in the chart toolbar. |
| US-22 | As Morgan, I review the Proposed portfolio and stage proposals. | Shows eligible research, cash used, whole-share sizes, failed research excluded with reason. Stage creates proposals, no approval. |
| US-23 | As Morgan, I approve and submit as two steps with exact terms. | Ticket shows exact terms. "Approve" and "Submit" are different buttons. Submit is disabled until approved. Double click is safe (one command). |
| US-24 | As Riley, I recover after a restart. | Header banner "Recovery needed". One action opens the recovery panel with what is unsure and what to do. |
| US-25 | As Riley, I see when orders are paused or blocked, and why. | Gate button shows paused state. Blocked reason is plain text. |
| US-26 | As any user, I use the keyboard. | Ctrl+K search, J and K move rows, Space checks, Enter opens, G then a letter changes page. A help popover lists keys. |
| US-27 | As any user, I read a chart without seeing it. | Chart has a text summary (last price, range, indicator values) and a data table option. |
| US-28 | As Alex, I import or export the universe (up to 1,000). | CSV import preview with accepted, rejected and duplicate counts, merge or replace, then save with revision. |

---

## 7. Industry comparison

Sources are the ones cited in blueprint section 1 and `ui-scale-research.md`. I
checked what each product does at the level of layout and interaction only.

| Product | Pattern | Verdict for this desk |
|---|---|---|
| **Fidelity Active Trader Pro** | Linked windows by colour group. Watchlist drives Quote, Chart and Order ticket. Dense tables, few labels. | **Adopt** the focus symbol that drives panes. **Adapt**: no free floating windows, use fixed panes. |
| **IBKR Desktop (Mosaic)** | One workspace of tiles, one symbol link, order ticket inside the workspace, account strip fixed. | **Adopt** the fixed account strip and the in-page ticket. **Reject** tile dragging (maintenance cost). |
| **TradingView** | Chart first, watchlist right, detail below. One toolbar per pane. Alerts attach to chart lines. | **Adopt** chart first on Markets detail and "alert from drawing". **Reject** Pine style scripting. |
| **Koyfin** | Dense screener with saved columns and saved screens. Watchlist with many columns. | **Adopt** saved screens, column sets, paging. |
| **FinChat / Fiscal.ai** | Research summary first, with sources cited, then detail. Chat style answers. | **Adapt**: show the report summary first, with sources (links) listed beside each claim. **Reject** chat style input (this is not a chat tool, and there is no backend for it). |
| **Bloomberg style terminals** | Command line navigation, keyboard first. | **Adapt** only as Ctrl+K search and G-key shortcuts. |

Common patterns that all of them share and the blueprint should follow:

1. One toolbar per pane, never one per page plus one per section.
2. Table first. Filters sit in one row, advanced filters in a popover.
3. A stable account strip.
4. Right-hand detail pane that opens on selection and does not navigate away.
5. Dense numbers, right aligned, tabular figures.

---

## 8. Upgraded wireframes

Conventions. `[x]` checkbox, `( )` radio, `[ Button ]`, `[v]` menu, `▸` collapsed,
`░` skeleton or progress, `●` status dot. Values are placeholders. Widths are 1280 px
desktop. Any table has a pager and a result count.

### 8.1 Shell

```
┌────┬─────────────────────────────────────────────────────────────────────────────────────────┐
│ ▣  │ Research        [ Find a symbol  Ctrl+K ]   Equity $— · Cash $— · BP $—   Closed ● Nautilus │
│ ◫  │                                              [ New orders: Not paused ]  🔔 2  Updated 10:42 ⟳│
│ ◧  ├─────────────────────────────────────────────────────────────────────────────────────────┤
│ ◈  │ ⚠ Recovery needed: 1 command unsure.  [ Open recovery ]        (shown only when true)    │
│ ◉  ├─────────────────────────────────────────────────────────────────────────────────────────┤
│ ◐  │ (page toolbar, 40 px: tabs · scope · actions)                                           │
│ ◔  │                                                                                         │
│ ◑  │ (page body: data first)                                                                 │
│ ◒  │                                                                                         │
│ ⚙  │                                                                                         │
└────┴─────────────────────────────────────────────────────────────────────────────────────────┘
 56 px icon rail. Hover or pin to show labels. No footer. No sidebar status block.
```

Notes: the gate button, not a sidebar button, shows paused state. Account values read
from `account` and show "—" with a tooltip "Not observed" if missing. The strip never
says "Unavailable" in a grid.

### 8.2 Dashboard

Job: "Is anything wrong, and what should I look at?" In under 10 seconds.
Remove the five tab version. Remove empty boxes.

```
┌ Needs attention (only rows that exist; hidden when empty) ───────────────────────────────────┐
│ ● 1 order working > 1 day   AMZN BUY 2 LMT     [ Open in Orders ]                           │
│ ● 3 research failed                              [ Retry failed ]                           │
│ ● Prices stale for 5 stocks                      [ Refresh ]                                │
├ Watch (shared stock table, 8 rows, pager) ──────────────────────┬ Focus: AMZN ──────────────┤
│ [ ] Sym    Price   Chg %   Age    Research        Note          │  chart (60% of height)    │
│ [ ] AMZN   —       —       2m     Hold · 10-28    •             │                           │
│ [ ] INTC   —       —       2m     —                              │                           │
│ ... 8 of 24                         [‹] 1/3 [›]  [ Markets ▸ ]   ├───────────────────────────┤
│                                                                  │ Research: Hold · 2026-10-28│
│                                                                  │ [ Open research ]          │
├ Account ─────────────────────────────────────────────────────────┴───────────────────────────┤
│ Positions 0 · Open orders 0 · Equity $— · Long value $—     (one line, expands if non-empty)│
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

Changes from the blueprint: the 2x2 grid becomes one table plus one focus pane. Empty
positions and orders become one account line. "Needs attention" comes from the existing
`dashboardAttentionSummary`. The research card shows a rating badge only when a rating
is saved (fixes critique L3).

### 8.3 Markets

Four tabs, which exist today: Watchlists, Universe, Screener, Saved scans. Keep them.

```
Markets   [ Watchlists ][ Universe ][ Screener ][ Saved scans ]
List: [ Shortlist v ] [ + New ]   🔍 [ Search ticker ]   Filters [v]   Columns [v]   3 selected [Clear]
[ Research 3 ]  [ Add to list v ]  [ Export CSV ]                                    24 stocks · 1–25
┌────────────────────────────────────────────────────────────────┬─ AMZN ─────────────────────────┐
│ [ ] Sym   Price   Chg %   Age   Session  Research     Note     │ [Chart][Research][Options][Position]│
│ [x] AMZN  —       —       2m    closed   Hold·10-28   •        │                                │
│ [x] INTC  —       —       2m    closed   —                      │   chart (Lightweight Charts)   │
│ [ ] NVDA  …                                                     │   indicators [v]  draw [v]     │
│ ...                                          [‹] 1 / 1 [›] 25 v │   alert from drawing           │
│                                                                 │                                │
│                                                                 │ [ Open research ] [ Prepare order ]│
└────────────────────────────────────────────────────────────────┴────────────────────────────────┘
```

Screener tab: left criteria (collapsed to a summary line once run), right results with
the same stock table. "Save screen" button. Results show the date of the data.
Saved scans: list on the left, tabs Definition / Runs / Matches on the right (as now).
Filters live in one popover: minimum move, view (all, owned, unresearched today, etc.).
The "Options" tab on the detail pane shows only for symbols with option data.

### 8.4 Research

Two parts: a **queue and picker** (left) and the **review** of the focused stock (right).
This answers the user's main complaint: stocks are picked here.

```
Research   [ Queue ][ Review ]                                   3 selected [Clear]  Research places no orders.
┌ Pick stocks ───────────────────────────────────────┬ Run ─────────────────────────────────────────────┐
│ 🔍 [ Search universe ]  List [Shortlist v]          │ Status: Idle      Last run: 10-28 · 12 done       │
│ [Select filtered] [Failed or unfinished]            │ [ Research 3 stocks… ]   est. 18 min              │
│ [x] AMZN    Hold · 10-28 · 3d ago                   │ ░░░░░░░░░ 4 / 12 done · 1 running · 7 queued     │
│ [x] INTC    — never                                 │ [ Stop run ]       last event: AMZN source check  │
│ [ ] NVDA    Buy · 10-27                             ├───────────────────────────────────────────────────┤
│ [ ] ...                          [‹] 1/1 [›] 25 v   │ Queue                                              │
│ Not in universe? [ Add in Settings ]                │ Filter: [All v]  AMZN  running 3m                  │
│                                                     │         INTC  queued                                │
│                                                     │         MSFT  failed  [ Retry ]                     │
└─────────────────────────────────────────────────────┴───────────────────────────────────────────────────┘
```

Review dialog opened by "Research 3 stocks…" (small popover, not a full page):

```
┌ Review research run ────────────────────────────────────────┐
│ 3 stocks: AMZN, INTC, NVDA                                  │
│ Models: quick <name> · deep <name>      Est. 18 min (from 9 completed runs) │
│ Places no orders.   Replaces the saved research for these stocks.           │
│ [ ] Keep selection after launch                               │
│                              [ Cancel ]  [ Start research ]   │
└─────────────────────────────────────────────────────────────┘
```

If the saved configuration changed since the page loaded, the dialog shows "Settings
changed. Reload to continue." (the server already rejects the stale revision). If no
completed timing samples exist, show "Estimate not available yet".

**Review tab** (focus stock). Data first, no decoration.

```
AMZN   Hold   2026-10-28 · 3 days ago · took 11m                                [ Prepare order ] [ ⋯ ]
Completeness: 1 gap: "social screening not complete"   ← from completion_gaps, shown only if non-empty
[ Summary ][ Analysts ][ Debate ][ Risk ][ Decision ][ Sources ][ Activity ]
┌ Final decision (excerpt) ──────────────────────────────────────┬ Social stance (Reddit · StockTwits) ┐
│ first paragraph of final_trade_decision …   [ Read full ]       │ bull 12 · neutral 8 · bear 3        │
│                                                                 │ unscreened 4                        │
└─────────────────────────────────────────────────────────────────┴─────────────────────────────────────┘
```

* Summary shows the excerpt of the final decision, the rating, the date and gaps.
  Excerpts are labelled "excerpt". No scorecard, no generated bullets.
* Analysts tab: four report sub tabs (market, sentiment, news, fundamentals) with the
  full text and a "Sources" list showing the real source title and domain, not a bare URL.
* Debate tab: two columns from the saved bull and bear history, then the judge decision.
  For a cancelled or incomplete stock, show "No debate saved" (not placeholder text).
* Activity tab: show date and time on every row, the symbol, and the message. State "40 of
  500 events shown" and offer "Show older" if the endpoint supports it.
* "Prepare order" is disabled with a reason until a saved report is open.
* Delete research is in the ⋯ menu and shows a preview first.

### 8.5 Portfolio

Tabs: Holdings, Proposed, Performance.

```
Portfolio   [ Holdings ][ Proposed ][ Performance ]            Equity $— · Cash $— · BP $—     Account observed 10:41
┌ Holdings ──────────────────────────────────────────────────────────────────────────────────────┐
│ Sym   Qty   Avg cost   Mkt value   Unrealized P&L   Weight   Research   Orders                  │
│ (none)  → "No positions observed. Cash account, long only."          [ Open Markets ]          │
│                                                                    [ Export CSV of selected ]  │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Proposed tab (session only, kept apart from per stock research):

```
Proposed portfolio                                  Model capital [ $ 10,000 ]   [ Synthesize ]
Eligible research: 9 of 12     Excluded: MSFT (failed), NVDA (incomplete) — never filled in for you
┌ Sym   Action   Whole shares   Est. cost   Weight   Reason (from the saved report)  ──────────────┐
│ AMZN  Buy      3              $—          18%      …                                            │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
Cash used $— of $10,000      This proposal is not saved and is not a trade.   [ Stage as proposals (N) ]
```

Rules: failed research is shown and excluded, never silently replaced. Candidates are not
truncated. Allocation numbers come only from the synthesis result. Staging creates draft
proposals in Orders; approval is separate.

### 8.6 Orders

Tabs match the code: Drafts, Open orders, History, Baskets. Add the count to each tab.

```
Orders  [ Drafts 2 ][ Open orders 1 ][ History ][ Baskets ]          New orders: Not paused    Broker ● reconciled
┌ Drafts ───────────────────────────────────────────────┬ Ticket: AMZN ────────────────────────────────┐
│ Sym   Side  Qty  Type   Limit   Est. principal  Status │ Terms  BUY 3 · LIMIT $— · DAY · regular       │
│ AMZN  BUY   3    LIMIT  $—      $—              ready  │        [ Edit terms ▸ ]                       │
│ INTC  SELL  2    …                     needs evidence  │ Evidence: ✔ account  ✔ dated quote  ✔ research │
│                                                         │ Impact: cash after $— · exposure +x%          │
│                                                         │ ─────────────────────────────────────────    │
│                                                         │ 1  [ Approve exact terms ]   not approved     │
│                                                         │ 2  [ Submit to broker ]      disabled         │
│                                                         │ Approval is not submission. Nothing is sent   │
│                                                         │ until you submit.                             │
└─────────────────────────────────────────────────────────┴───────────────────────────────────────────────┘
```

* The ticket shows the real fields: side, quantity, order type, limit, stop trigger,
  session, duration, exit plan, evidence scopes, linked research (run, report, revision),
  replacement of a working order. Fields beyond side, quantity, type and limit sit in
  "Edit terms".
* Submit shows one in-flight state and ignores a second click. After submit the row
  moves to Open orders and the result shows broker status, not a guess.
* `conditions_stale` or `evidence_ready: false` disables Approve and says why in one line.
* Open orders: cancel and replace only where the broker action says supported.
* History: saved local commands. Say once: "Not full broker history."
* Baskets: sub tabs Targets, Impact, Drafts, as now.
* Pause, native risk limits and cached reports move to Settings > Diagnostics. Keep a
  link "Why are orders paused?" in the gate popover.

### 8.7 Strategy lab

```
Strategy lab                                  Scenarios are not broker fills.
┌ Setup ─────────────────────────┬ Result ───────────────────────────────────────────────────────┐
│ Universe  [ Shortlist v ]      │ Return · Max drawdown · Trades          (what the run really    │
│ Period    [ 1y v ]             │ [ equity curve ]                          computes)             │
│ Rule      [ …v ]               │ Assumptions: fees, slippage, data dates  (one line, expands)   │
│ [ Run scenario ]               │ [ Export ]                                                      │
└────────────────────────────────┴─────────────────────────────────────────────────────────────────┘
```

Remove "Total return" if the option says "not supported". Show only what the run returns.

### 8.8 Journal

```
Journal   [ Decisions ][ Outcomes ]                                  🔍 [ Search ]  Disposition [All v]
Date        Symbol  Decision   Disposition      Outcome            Research
10-28       AMZN    Hold       Reviewed         —                  [ Open ]
```

One disposition editor lives here. Research and Dashboard link to it. Reload confirm is
replaced by a "Discard changes?" prompt only if there are unsaved edits.

### 8.9 Alerts

```
Alerts (browser only: you see them while this page or a tab is open)         [ + New alert ]
Rule                               State      Last observed     Source
AMZN price above $—                waiting    10:41             quote
drawing line AMZN (trend)          triggered  10:12             drawing         [ Open chart ]
```

Rule builder opens in a side drawer. Kinds: price, indicator, drawing. State names are
the ones the rules return.

### 8.10 Workflows

```
Workflows   [ Diagram ][ Files ]            18 nodes · 94 prompt files             Preview is stale  [ Refresh preview ]
┌ Files ─────────────┬ Editor (current editor, no new library) ─────────┬ Node ──────────────────────┐
│ ▸ analysts         │ prompt text                                       │ Primary prompt, shared     │
│ ▸ debate           │                                                   │ fragments, outputs         │
└────────────────────┴───────────────────────────────────────────────────┴────────────────────────────┘
[ Save ]  [ Revert ]  Saving changes affects the next run only.
```

Diagram can fit to width and zoom. Keep the stale preview indicator that exists.

### 8.11 Settings

Tabs: Account, Research, Integrations, Diagnostics (keep the four that exist).

```
Settings   [ Account ][ Research ][ Integrations ][ Diagnostics ]                         [ Save changes ]  rev 14
Universe: 24 stocks   [ Import CSV ] [ Export ] [ Edit list ]          ← preview before replace
Research: provider · models · token limits · retries
Integrations: credentials stored in Windows Credential Manager (never shown) · Nautilus [ Start ] [ Stop ]
Diagnostics: native risk limits, cached tables, recovery, runtime
```

Remove hard coded port or install path from help text. Read them from the state.
Saving credentials does not reconnect Nautilus: say that once.

---

## 9. Implementation risks

1. **Whole page re-render.** `main.innerHTML = markup` runs on each state update, with
   code to restore scroll, focus and open details. Linked panes, the picker and the
   review dialog will lose state. Update panes separately and keep stable DOM for the
   table, the chart and the ticket.
2. **Pages built by moving DOM after render** (`layoutMarkets`, `layoutOrders`). A
   redesign should emit the final structure and delete these layout fixes, or it will
   fight them.
3. **Tables at 1,000 rows.** Keep paging (25, 50, 100). No infinite scroll without a
   virtual list.
4. **No polling.** Only the active run polls. Do not add timers.
5. **No new backend.** Every control in section 8 maps to an existing route. Where it
   did not (company names, stage, day P/L), the element was removed.
6. **Plain static JS.** Prefer a small shared table and a small pane helper over a
   framework. A new dependency needs a short spike first.
7. **Accessibility.** Page tabs use `aria-pressed` buttons, not `role="tab"`. Pick one
   pattern. Add chart text summaries (US-27) and keep focus after render.

---

## 10. Open questions for the Grok and Argon reviewers

1. Should the Research page default to **Queue** or **Review**? I chose Queue because
   picking is the missing job. Is that right when a run is idle and a report exists?
2. Is a 56 px icon rail better than the 200 px labelled rail for these ten names?
3. Should "Prepare order" stage the proposal in place (drawer) or move to Orders?
4. Are the three kept safety sentences enough, or should the cash only, long only note
   also show on the ticket?
5. Is the batch set better cleared after launch (my default) or kept?
6. Is it worth a one day spike to replace the plain workflow editor with a code editor?
