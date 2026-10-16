# Independent product acceptance audit

Audit date: 2026-10-15. HSM: `session-1792116422951-27833`.
Scope: TradingAgents Laya, feeds, analysis, recommendations and guarded paper trading.
Verdict at this checkpoint: **not yet complete**. This is an evidence audit, not a broker fill test.

## Acceptance matrix

| Requirement | Inspected evidence | Finding |
|---|---|---|
| Laya classifies individual social posts through Maenifold SDK | `service.py` screen factory; `post_screen.py` state/instrument/post and typed questions; graph injection; T110 red report | Correct production source path; generic Laya tools excluded from research tools |
| Actual feed/model path | `.paper-desk/feeds-live-META-2026-10-15-coveragefix.json` | Completed sentiment-only run, actual-post verification true, zero broker calls, identical before/after journal hashes. One classified StockTwits post; remaining posts explicitly unscreened/deferred |
| Complete deployed research/recommendation | One read of `.paper-desk/desk.json`, run `56938b20-afd1-4696-9a0a-a13d48e460d0` | Still running, META rating null. Four report keys present. StockTwits 20 classified; Reddit 1 classified and 12 unscreened at this observation. Must inspect terminal result, report quality and evidence before acceptance |
| Uncertainty and source coverage | Current `post_screen.py`; T110 two-sided relevance and coverage follow-up | Uncertain relevance retained; source coverage, classifier labels, user tags and deferred work distinguished. Live neutral control verified against final question definition by red reviewer |
| No Laya research approval | Current `service.py` and `engine.py` diff; production search for `laya_review` and `approved_review` | Completion, planning and submission no longer require Laya approval. Historical audit rendering remains intentionally |
| Execution safeguards | `service.py::_review`, `_submission_guard`, `submit`, `_require_known_submissions`; `engine.py::_quote`, reservations and `validate_proposal` | Explicit submission, paper identity, pause, current completed research/date/config/account/evidence hash, 15-minute freshness, executable price checks, reserve, allocation, whole shares, long-only and open-order guards remain. Durable intent and unknown-outcome reconciliation prevent blind replay |
| Safeguard regression proof | T110 red runs and current test cases in `test_paper_engine.py`, `test_paper_service.py` | Independent red reported 487 Python tests plus 3 subtests, later scoped 124 Python and 22 UI tests after coverage changes. Tests use fake brokers. Reviewer inspected coverage rather than rerunning duplicate suites |
| UI UAT | `LAYA_T110_UI_UAT.md`, current JS and fixture screenshot | Fixture proves source statuses/counts/provenance and scroll behavior. It does not prove terminal live research rendering or newly loaded service code |
| Bounded backend use | Social budget and lock in `post_screen.py`; red retry review | Shared 30-post/120-second budget, per-call deadline, serialized inference, cooldown and preserved unscreened evidence. Explicit 429 retry correction recorded; no unrestricted retry loop introduced |
| Account untouched by this audit | Reviewer operations were local reads and HSM metadata only | No account, broker, inference, cancellation, order or restart calls. Journal observation had 28 blocked proposals and no new submitted proposal; this alone is not a full broker audit |

## Required completion evidence

1. Observe the existing live META run reaching a terminal successful state; do not restart it merely because observation expires. Verify final rating, complete reports, quote context, consumed source evidence and honest screening coverage.
2. Verify the actual running service loaded accepted source and the live UI renders that run's persisted classifications and recommendation. Fixture screenshots cannot substitute for this.
3. Exercise proposal review in a no-submit path if needed to verify the UI no longer blocks on retired Laya opinion. Market-closed prices remain useful references but do not waive executable quote freshness. A legitimate stale execution quote block is not a reason to weaken the guard.
4. Finish independent Gate acceptance, scoped commit and post-commit provenance. No real paper test order is required or authorized by this audit; fake-broker dispatch/reconciliation tests establish the implementation behavior without changing the account.

## T-1.8 retirement

Current runtime has no `prepare_review` or `approved_review` call dependency. `laya_review.py` remains a historical/test utility and the UI labels persisted entries as historical. `tests/retired/README.md` explicitly explains why the `.py.txt` draft is outside pytest collection. `FEATURE_FREEZE_ACCEPTANCE.md` preserves failed broad-choice findings and identifies the old scope as superseded. This supports closure **as retired/superseded**, never as a semantic model pass. Exact byte-for-byte identity of the uncommitted pre-retirement draft cannot be independently established from its explanatory README alone; preserve any coordinator hash/receipt rather than claiming that identity solely from this review.

## Commit hygiene

A local pattern scan inspected 50 newly untracked text files (Python, Markdown, JSON, text, JS/CJS, HTML and CSS) for private-key markers, recognizable long API tokens and literal credential assignments. No matches were found. This is a bounded heuristic, not a guarantee that arbitrary secrets are absent. Twenty-five binary/other files, primarily existing screenshots, were excluded from text scanning. Selectively stage task-owned files; unrelated design artifacts and screenshots are not implicitly approved for commit. Existing ignored `.paper-desk` receipts should remain local unless separately sanitized.

## Limits and confession

No tests, live providers or UI automation were run by this reviewer; test results are explicitly attributed to the independent red evidence. One read-only shell listing had a quoting error and was interrupted; no project state was changed by it. The reviewer edited only this report. The sentiment-only receipt's classified post is largely a link/ticker list, so a nonzero bearish count is transport evidence, not proof of accurate market sentiment or investment merit. Small controls establish limited behavior, not broad classifier calibration.

## Completed live run follow-up

Follow-up HSM: `session-1792116693121-86548`. A second read was explicitly authorized after completion and proposal creation. The prior matrix is a historical checkpoint; the following observations supersede its running-state entries.

Run `56938b20-afd1-4696-9a0a-a13d48e460d0` completed at `2026-10-16T02:10:05.214759+00:00` in 279.863 seconds. META is Overweight, all nine report/debate fields are persisted, and final `laya` is null. This proves research can complete without the retired approval gate. It does not establish corrected classifier behavior: this original run must remain unchanged as failure evidence.

The final sentiment report distinguishes classifier counts from user tags and explicitly limits Reddit coverage to 1/13. It records headline/excerpt limitations and does not invent engagement metrics. It nevertheless calls classifier sentiment bearish-leaning based on the saved 11 bearish versus 4 bullish counts. Inspection finds **16 StockTwits directional labels and one Reddit directional label whose stance grade was `reconsider`**. These labels were admitted by probability alone. Therefore this report is contaminated by the now-confirmed classifier-consumption bug and cannot be acceptance evidence for the pending correction. Corrected mapping must preserve such outputs as uncertain; do not silently rewrite the saved report.

Reddit is partial with 12 unscreened posts, but persisted `error` is an empty string and `stop_reason` absent. Coverage is disclosed, but the interruption cause is not understandable. Timeout/cancellation exception strings may be empty; ensure a plain-language failure reason is persisted without converting unscreened posts into neutral.

The final recommendation explicitly says not to order now, requires a fresh valid two-sided quote, and limits a subsequent starter to 0.05 times a standard allocation that it itself calls undefined. It also corrects an upstream trader's reversed moving-average comparison. These are material restrictions, not merely decorative prose.

The coordinator-created proposal plan has seven blocked rows: META is blocked by stale/future-dated executable quote; the other six lack current completed analysis. This demonstrates that removing Laya approval did not remove the executable-quote and research guards. No submitted order is present in this run's plan.

**Additional recommendation-to-proposal gap:** `engine.py::plan_orders` reads status/date/rating and calculates Overweight as 0.75 times configured equal-weight target, then applies order/cash caps. It does not consume the final recommendation's starter size, prerequisites or undefined-allocation restriction. Today's stale quote happens to block this run, but a fresh quote could create a generic allocation inconsistent with the recommendation. Manual submission is still required, so this is not an automatic broker trade; nevertheless the goal of correct recommendations and paper proposals is not yet proven. Require an explicit, validated executable recommendation contract or a conservative no-proposal state for unresolved restrictions, with fake-broker regression coverage. Do not solve this by reinstating Laya approval or parsing arbitrary prose with an optimistic default.

Overall verdict remains incomplete: the live run proves connectivity and complete orchestration, while exposing a real classification bug and a recommendation/planning mismatch. No broker calls or account mutations were made by this reviewer.

## Sizing architecture clarification for T-1.11

Further source inspection narrows the recommendation/planning issue above. `docs/paper-trading.md:66` expressly assigns sizing to deterministic Python from rating and broker book; line 466 says research opinions do not own sizing. The orders UI describes policy-calculated proposals, lists caps and requires a preview showing exact quantity/notional before manual submission. Thus failure to execute an invented 0.05 multiplier is **not an engine violation of the established sizing contract**. The conflicting model prose is a research-context and user-facing clarity defect. The earlier suggestion to introduce a new executable recommendation contract is broader than needed and is not the recommended fix.

Evidence of the cause: `portfolio_manager.py` asks for a decision sized by how decisively the argument wins; `schemas.py::PortfolioDecision.executive_summary` requests position sizing; research-manager/trader prompts also solicit sizing. The desk supplies actual cash and holdings, but its injected portfolio context does not state the configured deterministic allocation policy. The model therefore invents a standard allocation while the application has an existing, different policy.

Minimal correction:

- Inject the actual desk policy into consumed research context: configured invested allocation/universe denominator, Buy target, Overweight 75% target, Sell/Underweight behavior, caps, reserve, whole shares/long-only, fresh-quote check and explicit manual submission. Keep current observations distinct from future execution checks.
- In desk mode, make the model's role a thesis/rating and conditional risk discussion. Do not ask it to invent numerical order sizes or imply that its prose is the execution plan. Preserve ordinary non-desk research behavior where appropriate.
- Explain in proposal review that quantity comes from configured policy and that research commentary is advisory; show/link the associated research for human review. Existing exact quantity and manual submission remain mandatory.
- Verify actual prompt/context consumption and invariance of deterministic sizing with offline tests. No replacement approval model, prose parser or broker transaction is necessary.

A separate terminology defect remains in research quote context: `fresh=false` means not fresh enough for execution but the prompt says to distinguish available "stale" prices, so reports call valid market-close references stale despite market-aware workspace labels. Use separate reference/session labels and execution freshness rather than weakening execution checks. The saved report remains historical evidence of that wording.
