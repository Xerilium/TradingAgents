# User workflows

These stories describe an individual operating the integrated trading platform.
They organize capabilities already present in the application. They do not add
a new trading engine, provider, strategy type, model service or broker authority.

Use [platform reference](platform-reference.md) for boundaries and implementation
sources. Each workflow below has its own starting state; the sequence is not a
mandatory wizard. Research, a joint allocation, a saved-plan simulation and a
human basket remain separate.

## Workspace map

| Workspace | Primary job | Views and actions |
| --- | --- | --- |
| Dashboard | Orient and choose what to inspect | Account observations, selected stocks, chart/research/position/order panels |
| Markets | Find and inspect instruments | Watchlists, Universe, Screener, Saved scans; instrument Chart, Research, Options, Position |
| Research | Launch a chosen batch, follow progress and inspect evidence | Summary, Reports, Debate, Sources, Activity, Setup |
| Portfolio | Understand actual holdings or model a separate allocation | Positions, Model proposal, Performance |
| Orders | Prepare, review and track exact terms | Drafts, Baskets with Targets/Impact/Drafts, Open orders, History |
| Strategy lab | Evaluate supported historical scenarios | Simulations with Setup/Runs/Results, Experiments, Saved strategies |
| Journal | Revisit decisions, notes and available outcomes | Decisions, Position outcomes, Notes, Account history |
| Alerts | Inspect occurrences and manage their conditions | Inbox, Rules, Delivery |
| Workflows / Settings | Configure research and operation | Validated research graph/prompts; accounts, models, rules, integrations, diagnostics |

## 1. Select stocks and start research

**Story:** As an operator, I want to research the stocks I selected without
leaving the list to find the launch button.

**Start:** Dashboard watchlist or Markets Watchlists/Universe, with the configured
stock universe and current readiness state loaded.

1. Select the intended configured stocks. Keep the eligible batch count beside
   Select matches/Clear and the research action.
2. Inspect a different stock if needed. Inspection must not change the batch.
3. Choose the adjacent research action.
4. Review the exact symbols, date, provider/models and relevant workload details.
5. Explicitly confirm. A failure stays visible; closing confirmation starts nothing.
6. Follow progress in Research and open each stock's latest evidence.

**Layout:** List and its selection/action toolbar form one workspace. Secondary
list management belongs in a disclosure. Do not hide launch among column settings.

**Proof:** Two selected stocks and a third inspected stock produce a confirmation
for exactly the two selected names. Zero selection and current busy/read-only/
readiness guards remain effective. Confirmation does not place an order.

**Existing implementation:** `researchSelection`, `researchButton`,
`reviewResearch`, `launchResearch` and the `run` action in
[app.js](../tradingagents/web/static/app.js).

## 2. Discover a stock and decide whether to research it

**Story:** I want to inspect discovery results and deliberately choose which ones
belong in my configured research universe.

**Start:** Markets → Screener or Saved scans.

Run the existing explicit screen/scan, inspect its source, time and coverage,
then open an instrument. A discovery selection is not a research batch.
Use the existing explicit add-to-universe action for an eligible outside-universe
instrument before selecting it for research. Adding to a watchlist alone does not
establish configured-universe membership or broker tradability.

**Layout:** Criteria, results and source context stay together. Selecting a Markets
tab must reveal that tab, rather than leave an unrelated instrument or ticket
covering it. Closing an instrument returns to its actual browsing context.

**Proof:** Empty success differs from a provider error. No universe change,
collection or research run happens merely by viewing a result.

**Existing implementation:** `renderDiscoveryMembers`, `layoutMarkets`,
`openStock` and the discovery/scanner handlers in app.js.

## 3. Read a recommendation and judge its evidence

**Story:** I want to understand the selected stock's conclusion, its supporting
evidence and its gaps before deciding what to do.

**Start:** An actual retained latest result, including partial/failed results.

Select a stock, read Summary, then use Reports, Debate and Sources as needed.
Activity identifies whether events belong to the batch or selected stock.
A batch cancellation must not masquerade as the selected stock's result status.
Keep source dates and completion gaps available. Human notes and review controls
support reading; bulk deletion is secondary and clearly labeled.

**Layout:** Stable collection on the left; selected ticker, status and evidence
on the right. Reading space takes priority over generic toolbars and UUIDs.
Instrument Research leads with its saved evidence, with notes/review secondary.

**Proof:** Changing the inspected stock updates the right-hand evidence. Missing
old research remains unavailable; it is not replaced with another result.
Selecting unfinished research includes results labeled incomplete.

**Existing implementation:** `renderResearch`, `researchCollection`,
`renderReports`, `renderEvents`, `researchRowStatus` and instrument research.

## 4. Compare actual holdings with a separate model proposal

**Story:** I want to examine an AI allocation idea without confusing it with my
account or an executable basket.

**Start:** Portfolio → Positions for observed holdings, or Model proposal for
eligible latest research and cached dated prices.

The model proposal shows its own capital, input eligibility/exclusions, dated
prices, deterministic whole shares and residual cash. One joint deep-model
synthesis produces a session-only proposal starting from model cash.
Inspect its evidence and reasoning. If choosing to act, prepare human terms
through the existing Orders/Baskets controls; no automatic transfer or approval
is implied.

**Layout:** Actual Positions and Performance are distinct from Model proposal.
State the modeled basis beside capital and results, not in distant help.

**Proof:** Generating an allocation does not alter holdings, create an approved
order or silently replace failed research.

**Existing implementation:** `renderProposedPortfolio`,
[portfolio_model.py](../tradingagents/web/portfolio_model.py).

## 5. Prepare a human order or basket

**Story:** I want to express exact terms, understand their impact and return to my
saved work without losing its identity.

**Start:** An instrument/research preparation action, an existing draft, or
Orders → Baskets.

For a single order, enter supported exact terms and review the existing preview.
For a basket, add deliberate targets, choose quantity/weight and enter terms;
preview Impact before saving linked drafts. Inspect current/pending/target
exposure and available cash using the actual dated basis. Saving does not approve.

**Layout:** Targets → Impact → Drafts are sibling basket views. An opened order
shows its symbol, exact revision, status and terms prominently. Its return control
names the originating list: drafts, baskets, positions or Markets context.

**Proof:** Editing targets/fees/slippage makes an old preview visibly stale or
removes it. Every basket field identifies both symbol and field for accessibility.
Legs remain separately reviewed and may fill independently.

**Existing implementation:** `basketPanel`, `layoutOrders`, `openTicket`,
[investor.py](../tradingagents/web/investor.py),
[baskets.py](../tradingagents/web/baskets.py).

## 6. Simulate a supported saved plan or strategy

**Story:** I want to inspect a hypothetical outcome under explicit historical
assumptions before deciding whether to act.

**Start:** Strategy lab, a supported saved plan/strategy and qualified retained data.

Load existing plans/data, select the exact supported plan or strategy revision,
set the available history window and assumptions, then preview/run explicitly.
Use Runs/Results to inspect the output. Experiments have their own training,
validation, out-of-sample and optimization requirements.

This single-plan simulation does not imply that a whole human basket or joint
model portfolio can be simulated by the same control. Do not preselect an
unsupported plan or invent an automatic model-to-simulation handoff.

**Layout:** Explain Setup, saved Runs and Results and whether sources are unloaded,
empty, failed or available. The load action stays discoverable in each relevant
empty state. Keep assumptions adjacent to the run action and results.

**Proof:** Missing inputs remain unavailable; loading does not run. Modeled returns
and fill assumptions never appear as broker results.

**Existing implementation:** `evaluationMarkup`, `renderStrategy`,
[evaluation.py](../tradingagents/web/evaluation.py),
[evaluation_worker.py](../tradingagents/web/evaluation_worker.py).

## 7. Approve, submit and track an order

**Story:** I want control over the exact order sent and a truthful account of what
the broker has acknowledged.

**Start:** A saved draft with current readiness/check results.

Review exact instrument, side, quantity, prices/type, duration/session, account
and revision. Approve the exact terms. Submit is a separate explicit action
with current admission checks. Inspect pending/accepted/partial/filled or unknown
status in Orders. Cancel and replace remain separately authorized actions.

**Layout:** Put status and blockers beside the reviewed terms. Keep approval and
submission visually and semantically distinct. Preserve command/order identity
and a clear path back to Drafts, Open orders or History.

**Proof:** Approval never dispatches. An unknown result is not filled and never
automatically resubmitted. Changed terms require the existing renewed review.

**Existing implementation:** [command-controls.js](../tradingagents/web/static/command-controls.js),
[approval_review.py](../tradingagents/web/approval_review.py),
[admission.py](../tradingagents/web/admission.py).

## 8. Evaluate performance and revisit decisions

**Story:** I want to understand observed account outcomes and revisit my reasoning
without treating missing records as profit or loss.

**Start:** Portfolio → Positions/Performance, Orders history or Journal.

Inspect the observed account and timestamp, select an available performance
interval, and read its basis and gaps. Use Journal for saved decisions, notes
and available position outcomes. Follow actual retained references; missing old
research is explicitly unavailable. Alerts are a separate attention inbox.

**Layout:** Positions lead with holdings, Performance with available history and
its method, Journal with saved decisions. Keep model allocations and simulations
out of actual-account performance totals.

**Proof:** Too little history produces an informative empty state, not invented
points. Source time, missing fees and incomplete coverage remain visible.

**Existing implementation:** `renderPerformance`, `renderJournal`,
[performance.py](../tradingagents/web/performance.py),
[decision_journal.py](../tradingagents/web/decision_journal.py).

## Delivery boundary

These stories define intended use and review criteria. They are not a claim that
all runtime cases have passed. Source/static checks, read-only visual observations,
new research, simulation execution and actual broker actions are different evidence.
Verify changed paths with existing retained data where possible; do not generate
data or exercise broker authority just to make a demonstration look complete.
