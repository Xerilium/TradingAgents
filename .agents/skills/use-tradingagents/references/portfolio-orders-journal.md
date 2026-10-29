# Portfolio, Orders and Journal

## Contents

- Evidence and safety
- Portfolio: Positions, Proposed and Performance
- Orders: drafts, tickets, review, open orders, history and baskets
- Exercise and do-not-exercise instructions
- Journal: Decisions, Position outcomes, Notes and Account history
- Exact controls and workflow details
- Review evidence and limits

## Evidence and safety

This guide separates live observation from source-confirmed behavior. Dated “Observed” entries describe the stated browser pass. “Source only” means the implementation path was read, but its effect was not exercised. Other documentation is a source map, not independent proof. A shown control does not prove broker acceptance or fill.

The live account view showed an Alpaca paper account. It showed $100,000 cash, equity and buying power, $0 long market value, 0 positions and 0 open orders. The app showed a configured FANGMAN list of seven stocks. These values describe that observation only.

This pass did not save a form, run a model, collect broker history, export records, change order controls, review, approve, submit, cancel or replace an order, or send an option instruction. No acceptance was tested.

Current research retention keeps only the latest research result per ticker. Portfolio → Proposed uses eligible latest research and cached dated prices in one joint model run. It is a session-only model proposal. It is not an order, human basket or historical simulation. Do not use an older result as a fallback or invent a missing input.

## Portfolio

Portfolio has Positions, Proposed and Performance. The present source renderer forces the Holdings view and hides its inner Holdings/Stock universe tabs. The live pass showed the Positions summary and holdings table. Source code also contains a Stock universe mode, but this pass did not observe a route to it in the current Portfolio renderer. Do not describe it as a visible Portfolio control. The underlying base component has both modes; its alternate availability in another state is not established here.

### Positions

**Observed.** The page showed account cash, equity, buying power, long market value, position count and open-order count. It showed an empty holdings table and the notice “No open holdings reported in this observation. Pending orders can still exist.” The table headings were Holding / import, Exact quantity, Broker average cost / USD, Observed price / USD, Broker market value / USD, Broker unrealized P/L / USD, Account weight (derived), and Pending exposure. “Connection and quote observations” was a disclosure.

**Source only.** On Portfolio, search, scope and sort sit inside the collapsed **Filters, exposure and source details** disclosure. **Holding scope** options are **All observed holdings**, **Outside configured universe**, **With pending exposure** and **With import gaps**. **Holdings sort** options are **Symbol**, **Exact quantity**, **Broker market value** and **Broker unrealized P/L**. The direction button text is **Ascending** or **Descending**. Account weight is the supplied signed position market value divided by supplied positive account equity, multiplied by 100 and displayed to two decimal places. Unknown values stay unavailable. The Positions table has no CSV button; account exports are in Performance or Journal → Account history. **All account pending exposure · N observations / local commands** expands working-order effects. Linked exit orders are alternatives, not additive exposures. Pending order quantities stay separate from held shares. Sale proceeds do not become available cash until confirmed by account observations.

“Read-only import observations and precision” exposes retained broker/native observations and reconciliation gaps. Missing quantities, prices, costs or fees remain unknown. A position import does not itself prove that all broker orders or fills are present.

**Source-only row route.** A holding symbol uses `data-stock` in `UniverseReview.holdingsTable()`. Its handler calls `openStock()`. In Portfolio, that function selects the instrument’s **Position** tab inside the Portfolio workspace. It does not navigate to Research. **Back to universe** closes that detail; **Escape** also closes it. The label is shared with Markets, even in Portfolio. Dashboard’s separate `positionsTable()` uses `data-action="inspect"` and opens Research. Do not confuse these two tables. Source: `holdingsTable`, `bind`, `openStock`, `closeStock`, and `renderPortfolio` in `tradingagents/web/static/app.js`.

### Proposed

**Observed.** The page described one joint allocation proposal. “Model capital (USD)” defaulted to 10000. “Model portfolio” was visible. The page said the action does not refresh sources, start new stock research or take broker action; it also said the proposal does not approve an order. The idle state said no joint portfolio had been modeled in this app session. This pass did not run the model.

**Source only.** Capital accepts values from 0.01 in 0.01 steps. The input and model button are disabled while a run is active or queued. The renderer shows provider/model, input counts, error state, allocation table, exclusions, saved research bindings and source coverage. The table gives Stock, Target weight, Whole shares, Reference price with time/basis/stale flag, Reference value, Rationale and entry conditions. It shows residual cash and cash target weight. Share counts use deterministic whole-share floor sizing against dated cached prices. This is a model output, not an executable quote or approval.

The result belongs to this app session. A later explicit model run replaces it. A failed or missing research input is not silently replaced, and candidates are not silently truncated. On restart, do not expect this proposal to persist.

### Performance

**Observed.** The Equity panel said “No equity history yet” and offered a read-only connected-account refresh to load recorded equity. Returns said there were not enough saved observations. No saved interval was available, so “Open selected saved interval” was disabled. “Data details, collection and reporting choices” exposed these controls without activating them:

- Reporting revision and “Reload saved journal”, which discards unsaved notes/settings.
- Full-account holdings CSV and selected-interval activity CSV. The optional activity symbol field is blank for the full account.
- Full-account selected-period performance CSV.
- Start and end date inputs.
- **Collect read-only broker history for this interval**, with a maximum of 366 days and 2,000 activities. The view reports coverage and page budgets.
- **Saved history collection**, whose empty option is **Choose a saved interval**, and disabled **Open selected saved interval**.
- Comparison symbol; an editable **Comparison currency (USD required for comparison)** field, not a value fixed to USD; and **What the comparison includes**: Decide later, Price change only (dividends excluded), or Price change plus reinvested dividends (not supported).
- “Save reporting choices”.
- Planned review horizon in whole calendar days (optional) and a note.

This pass did not collect, export, or save. Collection reads broker history and can make provider requests. Navigation/reporting preferences can autosave; treat navigation changes as persistent local state.

**Source placement.** Current `renderPerformance` moves **Saved history collection** and **Open selected saved interval** into the Performance chart controls. **Data details, collection and reporting choices** keeps the remaining collection and reporting form, under **Account-history reporting** and **Your reporting choices**. The 25 October observation that the interval selector and open button sat inside that disclosure is historical relative to this placement.

**Source only.** Opening a saved interval shows saved broker equity observations, P&L, activity/cash flows, coverage and paging, receipts, time-weighted return and Modified Dietz where evidence supports them. Missing flow or endpoint data can make a method unavailable; the app must not interpolate it. Benchmark comparison needs matched, split-adjusted USD daily history. The supported price-change method excludes dividends and costs; total return with reinvested dividends is unavailable. The interval view can map benchmark symbols as of a date, save a method report from existing records, or queue selected benchmark history for that interval. Queuing requests market data. Unknown transaction fees remain unknown.

## Orders

Orders has Drafts, Open orders, History and Baskets.

A human proposal is not a broker order. A saved draft is local and has no approval or dispatch authority. Open orders come from the connected broker observation. History contains local command records and receipts; it is not a complete broker order/fill ledger.

**Observed.** Drafts showed seven saved human proposals, all BUY, status rejected, revision 2. Rows offered “Open exact terms / revise / review” and “Revision history and source references”. The page also showed “Account readiness and order guidance”, “Basket orders”, “Pause, approval, and action details”, “Create an order”, “Pause new orders”, “Resume new orders”, and one basket-group review. No action was taken.

Open orders said “Open orders at Alpaca”, identified Alpaca paper Trading API and showed update time 2026-10-24T21:49:13.768978+00:00. It reported no open broker orders. **Find orders** and a **Rows** selector (25, 50 or 100) were available; Previous/Next were disabled on page 1/1. A symbol button opens an inspector with **Terms**, **Timeline** and **Fills**.

History said saved local commands and recorded status do not establish complete broker order or fill history. It showed no saved order commands in this observation. Drafts and command history are separate records.

### Drafts and revisions

Open a proposal to inspect exact terms, rationale, source links and revision history. **Save local proposal draft** or **Save local proposal revision** persists a human proposal locally. “Preview exact terms” computes impact without saving. Existing proposals can offer Reject, Defer and New proposal. Reject/Defer are local decisions. A later saved revision is a new exact terms version; do not assume an older review or approval applies.

Saved draft cards may include historical Nautilus records. Their presence does not prove that the current account, broker connection or execution path supports them.

### Stock order proposal

**Observed fields, source-only writes.** Opening the saved NVDA proposal on 25 October 2026 showed editable BUY, 6 shares, LIMIT 211.50, DAY and Regular session fields. Entry, Exits and Review changed the visible ticket step. No terms were edited or saved. “Create an order” is the separate new-proposal route; the conditional capabilities below come from source. The exact fields depend on side, order type, asset/account capabilities, selected holding and policy. Do not treat a hidden or disabled field as available.

The stock editor can include:

- Optional “Replace an existing working order” selector. Eligible predecessors are listed. Replacement quantity is total quantity, including earlier fills. For linked exit amendments, only limit/stop trigger can change; quantity, side, type and duration remain fixed.
- Side BUY or SELL and total Shares. A linked replacement can make quantity read-only.
- Order type options are the raw codes **MARKET**, **LIMIT**, **STOP_MARKET**, **STOP_LIMIT** and **TRAILING_STOP_MARKET**, plus a disabled **TRAILING_STOP_LIMIT unavailable** option. Trailing orders are restricted to eligible standalone whole-share sells.
- Limit price in USD; required by limit-based types. Stop trigger in USD for Stop Market and Stop Limit. **Trail unit** options are **USD distance** and **Percentage**, with **Initial trail / USD (up to two decimal places)** or **Initial trail / % (up to nine decimal places)**.
- The fieldset legend is **Order session**. The **Session** select offers **Regular session** or **Extended sessions**, where account, asset, order type, duration and dated capability permit it. Extended means pre-market, after-hours or possible overnight session; it is not a quote or execution guarantee. A replacement keeps the original session.
- Duration labels are **Day** and **Good till canceled** (values DAY and GTC), narrowed by policy and capability.
- For eligible BUY market/limit proposals or holding exits: **Profit target / USD**, **Protective stop trigger / USD** and **Stop limit / USD (optional; requires a stop trigger)**. Holding exits are limited to held shares. Paired exits use the same quantity. A buy-linked exit activates only after the full entry fill; a partial entry is not protected. OTO groups cannot be replaced. A stop-market can fill below its trigger; a stop-limit may not fill.
- Optional Order note, up to 10,000 characters.
- “Additional inputs this decision depends on” checks: history, news, corporate_actions, earnings, fundamentals and classification. These select evidence requirements; they do not fetch provider data.
- Optional exact saved report link and revision checkbox; report and rationale; optional revision note.

**Preview exact terms** shows current impact and blockers. **Save local proposal draft** or **Save local proposal revision** saves locally. The proposal may be rejected, deferred or revised. “Prepare exit for held shares” and “Prepare standalone trailing protection” appear only when an observed holding makes them eligible.

Impact uses observed account, positions, working commitments, policy and dated price evidence. Missing inputs create blockers. Fees that are not proven remain unknown. A market order has no guaranteed price cap. An impact preview is not an execution reservation unless the later review explicitly creates one.

Session capability evidence includes account mode/endpoint, session and time, asset overnight/halt/fractional eligibility, and quote feed/event time. Unknown capability remains unknown; it is not a negative result.

### Single-option proposal

**Source only.** The manual option premium editor supports long options only, regular session only. It does not open short positions, create linked exits or recommend an option from underlying research.

Fields and choices:

- “Amend an eligible existing option order” or “New order”. Eligible predecessor rows identify side, total quantity, symbol, type, duration, filled quantity and order ID. Replacement locks the contract, intent and order type; replacement quantity includes fills.
- Position intent: Buy to open long or Sell to close held long. For replacement the intent selector is disabled at the predecessor’s existing intent, which can be buy-to-open or sell-to-close. It cannot change the contract, intent or order type.
- Whole contracts.
- The profile-eligible order type, shown as raw codes such as MARKET, LIMIT, STOP_MARKET or STOP_LIMIT, not title-case names.
- Limit premium in USD per underlying unit for Limit/Stop Limit; stop trigger premium for Stop Market/Stop Limit.
- Duration options are the profile’s raw codes, such as DAY or GTC. They are not the stock ticket’s **Day** / **Good till canceled** labels.
- Optional order note; the link checkbox reads **Link exact saved underlying analysis (UNDERLYING); not an option recommendation**. Report revision, rationale and revision note follow.
- **Preview exact premium terms**, and **Save local proposal draft** or **Save local proposal revision**. Existing proposals can offer Reject, Defer and New proposal.

The estimate uses dated option bid/ask and exact deliverable. Premium is per underlying unit; estimated cash is premium × observed deliverable size × contracts. Contract increments are checked without silent rounding. Dated quotes are estimates. A local maximum execution price used in review is a review bound, not a guaranteed fill price. Market and stop-market orders have no guaranteed price.

### Option package

**Source only.** A package is one atomic multi-leg request. It is not a set of independent leg orders.

Execution profile choices are “Long options only” (default) and “Bounded risk option spreads”, subject to account capability. An existing package can be amended only if eligible; amendment locks profile, contracts, intents, ratios and order type.

Each leg selects an exact contract and a profile-allowed intent. Visible intent labels are **BUY · buy to open long**, **SELL · sell to close held long**, and, for the bounded-risk profile, **SELL · sell to open; package protection required** and **BUY · buy to close held short**. Every short leg needs coverage. Whole strategy units multiply each positive whole-leg ratio. The ratios must have greatest common divisor 1; enter 1:1 rather than 2:2. The app does not silently normalize them. All legs require observed metadata for the same underlying stock; the bounded-risk profile also requires the same expiry. The view shows exact contracts, expiration, strike, call/put, multiplier, holding and dated STC availability. **Add leg** adds the next unused retained selected contract, up to four; select another compatible contract first if no unused selection exists. Its enabled appearance alone does not prove a candidate is available. **Remove leg** removes an unsaved row even when fewer than two would remain. Such a draft is incomplete: Preview/Save stay blocked until there are 2–4 distinct compatible legs and all other required terms are valid. These conditional behaviors were traced in the handlers; no option package was created in the browser.

Other fields are whole strategy units, profile-allowed order type and duration as raw codes, **Net limit direction** (or **Expected net direction only; not guaranteed** for MARKET) with lowercase options **debit** and **credit**, signed net limit in USD per package multiplier unit for LIMIT, rationale and revision note. **Preview complete package** checks the draft. **Save local package draft** or **Save local package revision** saves it. Zero net limit is unsupported. Long-only supports 2–4 distinct BTO/STC legs, MARKET or LIMIT, DAY or GTC. Bounded-risk spreads require 2–4 legs with the same expiry, covered shorts and LIMIT. The app revalidates each separately selected session/capability.

A package LIMIT is positive for a debit and negative for a credit. A market package has no guaranteed price or debit/credit direction. Dated leg quotes only estimate net value. The reservation uses net debit plus declared costs once. STC contracts are claimed once. Expected credit cannot fund another commitment. Missing inputs block eligibility; unknown fees are not zero.

### Review, approval and submission

**Review controls.** From **Orders → Drafts**, use the record’s **Open exact terms / revise / review** button, then the ticket’s **Review** step. A readiness card can instead offer **Review this order**. The observed rejected NVDA revision opened directly on Review and said **Order rejected**. That revision has no Check order or Approve action: use **Entry** to edit terms and **Save local proposal revision** before reviewing a new draft revision. Save effects were not exercised. The Position instrument also embeds the same Entry/Review ticket, even when no holding exists. Save the terms first; unsaved form terms cannot be checked or approved. Review shows **Approve exact saved terms**, the exact side, quantity, symbol, order type, limit/stop, account, proposal revision, policy revision, time in force, session and rationale. **Exact saved terms and source identity** discloses the proposal ID, hash and saved JSON.

Open **Optional limits for this order**. For a MARKET multi-leg package, the disclosure is **Package MARKET debit bound and optional limits**. Fields are **Quote age limit / seconds (optional)**, **Approval lifetime / seconds (optional)**, conditional BUY MARKET/STOP_MARKET **Observed buy-price limit / USD (optional; market fill is not guaranteed)**, or for a MARKET package **Local net debit review bound / USD per package multiplier unit (required for MARKET; no broker cap or sign guarantee)**, **Fee estimate bound / USD (optional)**, and **Optional review note**. Numeric controls use `min=0`, `step=any`; values must be finite and nonnegative. A supplied approval lifetime must be positive. MARKET package net-debit bound must be positive. Other optional bounds may be blank. A bound is a local review condition; it is not an Alpaca price cap or execution guarantee.

**Check order** sends a review request against saved terms and current account, policy, capability, source and order state. The result shows pass or blockers and **Current / pending / proposed calculations and source bindings**. If inputs or revisions change, the previous evaluation no longer matches. **Approve this order** rechecks review and records approval only if all required checks pass. Browse-only mode disables approval/submission. Approval is tied to exact terms and current bindings. It may show a single-use validity or an expiry. **Revoke approval** records revocation. **Submit [side, quantity, symbol] to configured account** is a separate action. It is enabled only for unchanged terms with valid approval, execution enabled, orders unpaused, current account readiness, no recovery requirement and no active operation. Submit checks current authority and reserves resources before dispatch; an error or uncertain outcome must be resolved from order state and receipts before any retry. Changed terms, account, policy, source, capability or revision can invalidate review and approval.

Approval is a separate action. It binds to the exact reviewed terms and expires at the shown time. Submission is another separate action. The submit control is available only when the exact approval is valid, the account is ready, the order gate is open, and required recovery/revision checks pass. Basket controls select an existing exact approval for each leg. They do not create a blanket group approval. Each leg must pass its own current checks.

After approval, submission can still fail or remain uncertain. Use Open orders to inspect current broker state and History for local command status/receipt. Do not submit again solely because the screen did not update.

Pause blocks new dispatch where implemented; it does not recall a request already sent. Resume changes the local gate, not broker state. Account readiness and Native risk limits are separate from a proposal's local readiness.

The sidebar button `#pause-trading` is not itself a pause or resume action. `renderChrome` sets its text to **New orders paused · manage** or **New orders not paused · manage**. The HTML fallback **Pause execution** is overwritten at runtime. `togglePause` opens Orders and focuses **Pause new orders** (`#account-order-controls`). Use **Pause new orders** or **Resume new orders** in that panel for the gate change.

### Open orders and history

Open orders is a read-only view of orders reported by the connected broker, with **Find orders**, a **Rows** selector of 25, 50 or 100, and Previous/Next. An empty list is one observation, not proof that no broker order exists outside the returned scope or time.

History records local command and status events. `commandActivity` shows these visible labels: **Approved · resources reserved · not sent** (`admitted_not_dispatched`), **Not sent**, **Submission requested**, **Submitting**, **Order outcome unknown**, **Accepted**, **Partly filled**, **Cancellation pending**, **Replacement pending**, **Filled**, **Canceled**, **Rejected** and **Expired**. Command-panel summaries still show the raw state code. These labels describe local command/broker responses available to the app; they do not prove complete history or settlement. Inspect order IDs, events and receipts where present.

The pause and approval panel is on Drafts, inside `#command-activity`, not on History. History shows **Saved order history**. That panel offers **Pause new orders**, **Resume new orders**, an **Optional action note**, and eligible approvals with **Submit these approved terms**. Each saved command can show a **Broker order** selector and a **Separately approved replacement** selector. **Cancel selected order** requires an exact supported broker-order identity. **Replace selected order with approved terms** requires a supported predecessor and separately approved replacement terms. The panel also offers **Check whether submit was never sent**, **Check whether cancel was never sent**, or **Check whether replace was never sent** for matching uncertain/in-flight states. Select an approved replacement only after checking its exact terms and the predecessor.

Cancellation and replacement apply to broker orders. **Cancellation pending** is not confirmation; a fill may arrive while cancellation is pending. There is no cancel-all action. Cancellation follows Alpaca linked-order behavior. Replacement binds the predecessor and exact new terms; the full replacement quantity includes earlier fills. A changed fill/order version can block review. If replacement is rejected, the predecessor remains authoritative. Those names are raw state codes. History headings use the visible labels listed above, not slash forms such as “Cancel pending”. Statuses show app and available broker responses; they do not prove complete history or settlement. A timeout or missing response remains uncertain until reconciled.

A timeout or missing response can leave outcome unknown. A 404 alone does not prove the order was never submitted. Reconcile with broker observations before any new action. Do not blindly retry an uncertain submit.

### Baskets

**Observed.** Baskets → Targets showed one saved basket, revision 4, with no target selected. The page said it was a local human basket, not broker authority. It offered Add target stock, Add selected universe stocks as empty targets, a rationale field, “Preview basket”, “Save local basket draft”, “New empty basket”, and “Review exact leg approvals and basket command controls”. The stock menu listed AAPL, AMZN, GOOGL, META, MSFT, NFLX and NVDA. Columns were Symbol, Target type, Your target, Order type and Limit / USD. “Rationale, fees, and slippage assumptions” was a disclosure. Impact said no allocation preview had been made. No target or preview was entered.

**Source only.** Preview needs 1–1000 distinct supported stocks and non-empty rationale. Visible **Target type** options are the raw values **quantity** and **weight**. Quantity is whole shares, including zero. Weight is 0 to 100%; weights must sum to at most 100%. Order type options are **MARKET** or **LIMIT**. LIMIT must be positive and have at most two decimals. Fractional shares are not supported. The save button reads **Save local basket draft** or **Save local basket revision**. **Open basket** shows the first eight characters of the id.

The preview uses observed account equity, positions, working orders and dated prices. A weight becomes floor(equity × target weight ÷ price) shares. The difference from current observed shares makes the leg; lower targets produce sells. Pending quantities stay separate. The preview includes complete and partial scenarios, fees/slippage assumptions, turnover, cash, holdings and remaining legs. Optional fee per leg must be non-negative; optional slippage is 0–10,000 basis points. Unknown costs stay unknown, not zero. Sell proceeds do not fund basket buys.

Preview is non-persistent and returns executable=false with account, positions, orders, market and reconciliation snapshot/hash. It does not reserve funds or approve anything. **Save local basket draft** or **Save local basket revision** creates or revises local linked proposals and a basket revision. Removed proposals are deferred. Basket status is draft with no approval. Reject/defer updates local linked records. Any saved leg still needs exact separate review and approval before broker command. A group is not a broker-atomic fill.

“Impact” shows the latest hypothetical preview. It is not an account forecast or guarantee. Re-preview after input or source changes. Save only when you intend to persist local proposal terms.

## Exercise and do-not-exercise instructions

**Source only.** This is an explicit full-position option instruction flow, separate from stock/option orders and research. Current source renders it from `optionInstructionsMarkup` inside the Drafts command panel. It was not available in the 25 October browser pass. No intent, approval or submission was created.

The Contract selector can list currently observed option-contract metadata and contracts from saved instruction history. A listed contract is not proof of an eligible held position. Preview must establish current position/contract eligibility. Eligibility requires a connected account, current account observation within the configured maximum age, reconciled long US option position, no import error, contract identity matching the current broker contract endpoint, positive whole total and available contract quantities, with available no greater than total. The broker session and native epoch must be current. Local sell commitments reduce available exercise quantity. The app does not accept a partial count: “Exercise all available” means every contract then available, not a fixed count. It does not guarantee settlement or cutoff timing.

Controls include the exact contract; new intent “Exercise all available” or “Request DNE” (do_not_exercise); Account observation maximum age in seconds; Approval lifetime in seconds; required action note/reason for interlock release; “Preview current facts”; “Prepare a new intent from these facts”; saved instruction history; a prior-requests/unresolved-outcomes review checkbox; “Approve this exact reviewed instruction”; and a separate “Submit this approved instruction”. Blockers disable preparation, approval or submission.

Preview is read-only and not persisted. Prepare stores a new exact intent, facts and constraints. Review rechecks current account, contract, session, available quantity, policy, history and commitments. Approval binds to the exact reviewed facts/hash, actor, history and expiry. Any changed account version, native epoch, contract, policy, constraints, history, commitment or condition requires fresh preparation, review and approval. Submit requires that exact unexpired approval and current observation. It persists transport intent before the broker call.

Exercise also checks exercise funding and policy limits where evidence exists. DNE does not need exercise funding checks, but it still needs current identity/account facts and must respect unresolved in-flight outcomes. Unknown data stays unknown. No partial exercise, atomic undo or guaranteed cutoff is available.

History retains request ID, account, mode, session, native epoch, exact contract/facts, authority, attempt, receipts, timestamps and status. The instruction row states are prepared, approved, not_sent, transport_intent, transport_unknown, submitted or rejected. Review is stored in the prepared row; it is not a separate row state. Timeline actions record prepare, review, approve, admission block, transport claim, transport result and release. A broker 200 means the request was submitted; it does not prove exercise settlement. An uncertain transport result is one-shot; do not blindly retry. The explicit checkbox acknowledges review of prior unknown outcomes. It does not make a retry safe by itself.

“Record reason and release local interlock only” writes a local actor/reason/time release record for the unresolved request. It does not change the earlier outcome_unknown status, prove what the broker did, cancel the request, create broker authority or authorize a retry. It permits a new preparation/review path to consider history; fresh current checks and a new exact approval are still required. The unresolved broker state remains unknown until broker evidence resolves it.

The order pause blocks new exercise dispatch before sending where implemented. Separately approved DNE and separately authorized cancellations can remain available. Pause cannot recall a started request or establish a DNE cutoff. There is no exercise-instruction cancel action. “Cancel” in the order panel refers to a broker order, including its broker-linked orders. Do not interpret exercise instruction status as cancellable.

## Journal

Journal has Decisions, Position outcomes, Notes and Account history.

### Decisions

**Observed.** The list showed seven rejected human_proposal records and one rejected allocation_basket, revision 2, dated October 23. Controls included Saved reporting revision 0, “Reload saved journal” (discards unsaved notes/settings), Find decisions, and “Export selected records” with zero selected. Selecting NVDA opened decision detail tabs Rationale, Orders, Outcome and Notes.

The observed NVDA record showed rejected human proposal revision 2. Its rationale described a FANGMAN $10,000 paper portfolio, 1.42857% account equity per target (9.99999% total), whole-share rounding and dated limit references. It stated the research batch was still running, zero modeled fees/slippage were assumptions, and no broker order was authorized. Policy revision was 0. Broker order, fills and approval record were None. The Orders tab showed only “Linked orders and receipts” with no rows. This is one record's saved content, not a general broker status.

**Source only.** **Find decisions** is one search. It matches the combined symbol, status and kind text. It is not three separate filters. Row checkboxes select decision records for **Export selected records (N)**. That action downloads `tradingagents-selected-decisions.json`, not CSV. Account-history export buttons are the separate CSV actions. Clicking a symbol opens its record. Detail tabs show stored rationale, linked local/broker order evidence, outcomes and notes. A replaced research result is unavailable; Journal does not rebind to newer research. Missing order/fill evidence remains missing.

### Position outcomes

The observed empty view said no attributable outcomes were captured. Its text warns that native realized P&L includes applied settlement-currency commissions and is not independently verified net profit or tax-lot accounting. Source capture is manual: open Settings → Trading rules → **Native risk limits and cached reports**, choose **positions** in **Table**, use **Capture native table**, then return and reload Journal. The Journal page still says to open Orders and expand that panel; `nativeEnginePanel` is rendered only in the Trading rules category, not on Orders. This pass did not capture. No background refresh or provider call is implied.

When captured, rows can include native open/closed status, quantities/P&L, fee provenance, cached mark event and receive times, data gaps, fills, decision rationale, exact research and terms hash, and source capture. Missing proof stays unavailable.

### Notes

**Observed.** The top-level **Notes** tab lists eight decision shortcuts, each marked **No saved note**; these are not eight saved notes. Each button includes symbols, decision type, source date and a short decision ID. Selecting the NFLX shortcut opened **NFLX · saved decision** with its **Notes** detail tab selected. Use **Decisions** to find a record, then its detail **Notes** tab, or use the top-level shortcut directly.

**Observed fields, source-only save.** A decision note binds to its exact decision and source research/revision. The form showed **Investor assumptions**, **Investor review date**, **Later outcome notes**, **Save journal note**, **No saved follow-up note**, and **Follow-up note history**. The two note texts allow up to 20,000 characters in source. No note was entered or saved. The view shows saved version/date and Follow-up note history. Saving persists a local note; it does not change an order, approval or broker instruction. “Reload saved journal” discards unsaved notes/settings.

### Account history

Journal Account history shares Performance’s saved interval and reporting controls. The observed state had revision 0, no saved interval, empty equity/returns, and the history/export/benchmark controls listed under Performance. Opening an interval or collecting data was not performed. Read-only collection still calls the broker/history path; benchmark queuing requests market data. Exports can contain account data. Save reporting choices only when intended.

## Exact controls and workflow details

### Portfolio and saved performance

**Reload saved journal (discard unsaved notes/settings)** rereads reporting records and discards local notes/reporting edits. It does not request new broker history. On a broker order row, **Broker identity, classes, nested legs and import assessment** expands the observed mapping/classification and nested-order evidence.

- **Filters, exposure and source details** contains **Filter held symbols / import status**, **Holding scope**, **Holdings sort**, and a direction button whose text is **Ascending** or **Descending**, plus totals, pending exposure and import evidence. These are shared saved workspace preferences, not broker changes. The whole-account totals stay separate from the filtered subset.
- **Performance → Equity / Returns** changes which saved series/methods are displayed. Missing observations are not filled. The chart controls hold **Saved history collection** and **Open selected saved interval**. **Data details, collection and reporting choices** exposes the rest of the shared Account history form.
- The exact form labels are **Optional activity export symbols · blank = full account**, **Saved history collection**, **Comparison symbol (optional)**, **Comparison currency (USD required for comparison)**, **What the comparison includes**, **Planned review horizon (whole calendar days, optional)**, and **Optional note about these reporting choices**.
- **Export full-account holdings CSV**, **Export selected interval activity CSV**, and **Export full-account selected-period performance CSV** produce different local files. The optional symbols field filters activity export only; do not describe it as narrowing full-account performance.
- **Collect read-only broker history for this interval** makes broker requests and saves a collection. **Open selected saved interval** reads a retained collection without fetching new broker history. **Retry saved source** retries that read.
- **Save method report from existing records** writes recalculated method evidence for the selected saved collection. It is not a provider refresh.
- **Benchmark symbol mapping as-of date** applies to the explicit **Queue selected benchmark history for this interval** action. That action requests market data; choosing a symbol or saved interval does not.
- **Named methods, daily-close convention and source semantics**, **Benchmark comparison and method inputs**, **Calculation inputs and broker cash-flow series**, and **Original source receipts** expand saved evidence. Each **Open receipt N** opens the exact retained receipt.
- Captured allocation beside a performance interval is the account observation at capture time. It does not reconstruct holdings at the interval’s historical dates.
- A modeled Proposed result has **Allocation rationale and conditions**, **Entry conditions**, and **Saved research bindings and source coverage** disclosures. These expand model rationale and pinned inputs. They do not convert the model into a human basket.

Source: `holdingsTable`, `showPortfolio`, `renderProposedPortfolio`, `renderPerformance`, `accountHistoryWorkspace`, `accountHistoryView`, and `journalAction` in `tradingagents/web/static/app.js`. Account-history routes are `reporting`, `reporting_detail` and `reporting_csv` in `tradingagents/web/service.py`, with collection in `tradingagents/web/account_history.py`. Do not use top-level `tradingagents/reporting.py` for this guide; that module writes research report files.

### Ticket layout, quantity and evidence

**Entry**, optional **Exits**, and **Review** are ticket view steps. Selecting Review does not evaluate or approve the order. **Exits** appears when the stock ticket supports optional exits, including an eligible BUY MARKET/LIMIT with blank exit fields; its presence does not mean an exit plan was entered or saved. Holding-exit tickets can start in Exits. Action buttons remain in the shared footer.

**Replacement, notes, and decision inputs** holds predecessor selection, notes, evidence dependencies, and **Link the selected saved report, exact revision**. **Quantity, session, and proposal details** and **Extended-session terms** contain explanatory boundaries. **Dated session capabilities and separate price evidence** expands the actual dated capability facts. An eligible research-preparation ticket has **Return to retained symbol draft**, which switches back to that symbol’s other local draft; it does not save the research ticket.

Stock entry labels include **Replace an existing working order (optional)** and **Limit price / USD**. The stock **Shares (total includes prior fills for replacement)** field accepts exact decimal text. Up to nine fractional places are supported only when current asset evidence permits fractional orders. Simple fractional orders require DAY; linked exits and GTC require whole shares. Extended fractional LIMIT also needs explicit extended fractional eligibility. A fractional replacement preserves total quantity and supports eligible price-only changes; it is not a quantity amendment. BUY STOP_MARKET remains unavailable; enter reviewed STOP_LIMIT terms instead. No fractional broker acceptance was demonstrated here.

A standalone trailing sell uses **Trail unit** with **USD distance** or **Percentage**, then **Initial trail / USD (up to two decimal places)** or **Initial trail / % (up to nine decimal places)**. The nine-place quantity limit is separate: it applies to eligible simple DAY share quantity, not to the trail percent alone. It requires an eligible existing long holding, whole shares and regular session. It cannot be an entry, paired exit, or unsupported trail amendment. **Broker-managed trailing stop** shows the broker’s latest trail distance, high-water mark and moving stop; it does not reconstruct earlier movements.

Option package exact labels include **Existing package to amend**, **Exact selected contract**, **Intent**, **Whole ratio**, **Whole strategy units**, **Order type**, **Duration**, **Net limit direction** (or **Expected net direction only; not guaranteed** for MARKET), **Signed net limit / USD per package multiplier unit**, **Human rationale**, and **Revision note**. **Add leg** and **Remove leg** edit the draft. **Preview complete package** checks it. **Save local package draft** or **Save local package revision** saves it. **Net limit direction** options are lowercase **debit** and **credit**. **Exact contract, dated premium and current holding evidence** expands each leg’s source facts.

For a single option the exact price labels are **Limit premium / USD per underlying unit** and **Stop trigger premium / USD per underlying unit**. The underlying’s stock price is not an option premium. **Actual option quote and source receipt** and **Exact versioned broker contract / deliverables** expose the corresponding evidence.

Other impact disclosures are inspection only:

- **Exact historical price references and normalization**
- **Known working-order commitments**
- **Current / pending / proposed policy calculations**
- **Exact parent, sibling and native identities reviewed**
- **Exact funding basis and reservation / replacement treatment**
- **Exact exercise / delivery readiness**
- **Exact signed holdings, available long/short close claims, opening/residual protection and blockers**
- **Derived native spread valuation and original risk-cap provenance**
- **Exact review basis, old/new terms, actual account facts and known fee assumptions**
- **Actual retained replacement requests/outcomes · separate from approval-time assumptions**
- **Package funding, leg quantities/holdings, costs and policy source evidence**
- **Exact complete package terms and contract revisions**
- **Exact valuation retained with this approval**
- **Exact approved replacement routing basis**

**Reload saved investor records (discard policy/proposal edits)** is shown after a load/save conflict or error. It rereads saved records and discards local policy/proposal edits. It is not a forced overwrite.

Source: `proposalEditor`, `bindSharedTicket`, `trailingProposalMarkup`, `optionProposalEditor`, `packageEditor`, `impactMarkup`, `approvalPanel`, `bindInvestor`, `investor.py`, and `approval_review.py`.

### Basket targets, impact, drafts and dispatch

Baskets has **Targets**, **Impact**, and its own **Drafts** tab, separate from Orders → Drafts.

- **Targets** edits symbol, quantity/weight, value, MARKET/LIMIT, and limit. Row **Remove** removes an unsaved target. **Rationale, fees, and slippage assumptions** holds **Target / revision / review rationale**, **Estimated fee per leg / USD · optional, unset until entered**, and **Estimated slippage / basis points · optional**.
- **Impact** shows preview quantities/cash/policy scenarios. **Assume [symbol] filled** checks hypothetical legs; **Recalculate assumed fills** recomputes only that preview. It does not record a fill or execute anything.
- **Drafts** shows generated individual proposal terms and saved baskets. Open **Orders → Baskets → Drafts**, then **Open basket** plus the first eight characters of the id. The observed revision 2 returned to **Targets** and loaded its seven targets. **Impact** displayed its saved October 23 observation, policy revision and source hash; opening the basket did not make that evidence current. In **Drafts**, expand an individual leg to see retained terms and **Review exact saved order**. The leg-review route is source-confirmed but was not completed during this browser pass. **Revision history** expands saved versions. For a verified route to the saved proposal, use the separate **Orders → Drafts → Open exact terms / revise / review** action.
- **Reject basket and linked proposals** / **Defer basket and linked proposals** write those local decisions. They do not cancel broker orders.
- **Current / pending / proposed exposure, sector, correlation, liquidity and loss checks** and **Working orders and conflicting proposals** expose the preview’s saved evidence.

**Observed basket limitations (25 October 2026).** The saved basket was rejected and marked **Preview needs review**. Its Impact values were retained hypothetical calculations, not a refreshed account preview or real fills. A target `weight` is a percentage of observed account equity; the displayed 1.42857 meant 1.42857%, followed by whole-share floor sizing. Loading did not preview again, save a revision, recalculate assumed fills or create orders.

**Refresh repair verified, 25 October 2026.** Basket legs, working-order conflicts and saved revision histories now have stable disclosure IDs, which the existing render path restores. The saved AAPL leg and basket revision history stayed open across the normal refresh interval. **Review exact saved order** then opened AAPL’s exact saved BUY 4 LIMIT 347.69 order on the Review step. Its rejected revision remained blocked from approval/submission. This later check resolves the earlier disclosure fault; it does not validate broker execution.

The separate **Basket orders** command panel has these source-only actions:

| Control | Effect |
| --- | --- |
| **Leg [id] approval** | Selects an existing exact approval for that proposal. It creates no approval. |
| **Wait for preceding leg to complete** | Adds a dependency on the preceding leg. Disabled for the first leg. |
| **Submit next approved leg** | Binds the saved basket revision, exact per-leg approval IDs and terms hashes, then requests dispatch of the next eligible leg. This is a broker action. |
| **Submit next approved order** | Advances an existing basket execution after current checks. It does not submit every leg atomically. |
| **Pause basket** | Stops further dispatch for that local execution group. It does not cancel sent broker orders. |
| **Resume valid basket orders** | Revalidates the paused group for further dispatch. It does not renew stale per-leg approvals. |

An imported order has **Cancel this broker order** and **Replace this broker order with approved terms**, plus a **Separately approved replacement** selector. No original app submission approval is claimed. A reserved local command can show **Submit approved order**. All are separate from reading the order and need the relevant user authorization.

Source: `basketPanel`, `basketEvidence`, `bindBaskets`, `layoutBasketGroups`, and `tradingagents/web/static/command-controls.js`.

### Option instructions and Journal evidence

The option-instruction form uses **New full-position intent**, **Account observation maximum age / seconds**, **Approval lifetime / seconds**, and **Action note / required reason for interlock release**. The exact saved-record buttons are **Review current exact facts and history**, **Approve this exact reviewed instruction**, and **Submit this approved instruction separately**. The last action is not the review action. **Exact saved facts, authority, attempt, receipts and history** expands the record. Prepared/approved instruction records hold no resources.

Journal controls:

- **Open referenced latest research** is offered only when the exact referenced run/revision is still the ticker’s retained latest result. Replaced research stays unavailable; no substitution occurs.
- **Shared position outcome [id]** opens the corresponding captured outcome.
- **Exact decision, source research and revision history** expands the decision record.
- **Command approval, exact terms, broker receipts and historical native receipts** expands linked command evidence.
- **Non-atomic basket completion and paused legs** expands basket execution evidence.
- **Order identifiers, events and source records** / **Review saved approval and command status** expose local command and broker identity/state where present.
- **Recorded entry/increase and exit/reduction inputs: quantities, prices, times and fees**, **Exact original report reference and approved terms identity**, **Native open/closed snapshot, source precision, capture epochs and fee evidence**, and **Retained capture identities and source artifacts** expand saved outcome evidence.
- **Download complete captured table JSON** downloads a previously captured native table. **Capture, reconciliation and fee provenance** expands its source facts. Capturing a new table is the separate Settings action.
- A historical proposal dialog is read-only. **Close order preview** closes it; **Review associated research** opens its source if retained. It cannot approve a legacy record.
- **Open saved source result** and **Read saved research** read a retained research reference; unavailable references remain unavailable.

Source: `journalNote`, `journalNoteContent`, `decisionOutcomeMarkup`, `positionOutcomesMarkup`, `nativeEnginePanel`, `previewOrder`, and `optionInstructionsMarkup`.

## Review evidence

**Follow-up at `580f1c8`, 25 October 2026.** Browser checks exercised a rejected NVDA proposal’s Entry/Exits/Review steps; saved basket loading, its Targets/Impact/Drafts panes and one leg’s retained terms; Journal symbol filtering and export-selection count (restored to zero, no export); NVDA Rationale/Orders/Outcome/Notes; and the NFLX Notes shortcut. NVDA filtering also matched the multi-stock basket containing NVDA. The saved basket-leg review button initially disappeared on refresh; the later repair and successful leg-review route are recorded above. No authored record, approval, new preview, collection, export, note, broker action or research was created. Ordinary view preferences can autosave.


Reviewed against `b632a22` on 2026-10-25. Current browser observations covered Portfolio’s three tabs, Orders’ four tabs and all three basket panes, Journal’s four tabs and an existing decision’s four detail tabs. Empty holdings, broker orders, captures and interval data limited populated-state observation. No draft, preview, approval, command, collection, export or note was created during the review. Conditional effects above remain source-only.

Use named handlers in `tradingagents/web/static/app.js`, `command-controls.js`, `tradingagents/web/investor.py`, `approval_review.py`, `admission.py`, `execution_lifecycle.py`, `service.py` and `account_history.py` to resolve changed behavior. This file cites those names, not line numbers. Dated 25 October observations stay historical; they are not a new live check.
