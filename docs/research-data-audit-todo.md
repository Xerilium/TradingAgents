# Research data audit and fixes

Requested 20 October 2026: review every generated Intel artifact, fix lossy data
gathering, and inspect the other feeds for the same problems. Keep changes simple.
Do not create tests. Preserve existing research and credentials.

## Finalized work list

Status: all fixes are implemented as one batch. The user clarified that each
completed batch gets one verification cycle; collect any findings from that cycle
before making the next batch of fixes. This preference is recorded in AGENTS.md.
Historical findings below remain as the audit record. Checkboxes close after
the corresponding runtime evidence is reviewed.

### High priority

- [ ] **1. Complete SEC financial evidence.** The extractor selects only six
  income rows, six balance-sheet rows, and four cash-flow rows. It excludes
  filing notes and company-specific facts. Replace these incomplete statement
  representations with source-complete statements and accessible filing context.
  Preserve units, fiscal spans, filing dates, and historical availability.
  File: `tradingagents/dataflows/vendors/sec_edgar.py`.
  Acceptance examples from this Intel run:
  - Explain the Q2 $12.529B non-operating escrowed-share valuation charge instead
    of treating the operating-income/net-loss difference as unexplained.
  - Reconcile total liabilities of $99.296B; distinguish Intel parent equity
    ($87.542B) from total equity including noncontrolling interests ($103.143B).
    My earlier claim that this was merely a missing filer tag was incomplete:
    the published statements contain the information needed.
  - Explain partner cash requirements and financing alongside OCF less capex.
    The report's positive $1.910B first-half simple measure is arithmetically
    valid, but does not cover the Q2 partner outflow. Intel's different,
    company-defined Q2 adjusted FCF measure is negative $8.419B. Do not compare
    those different periods/measures as though they were the same number.

- [ ] **2. Preserve available Yahoo fundamentals.** Its overview also uses a
  fixed field list, omitting available company/business context and other fields.
  Return the available evidence with clear units and provenance rather than
  presenting the selected summary as comprehensive.
  File: `tradingagents/dataflows/vendors/yahoo/fundamentals.py`.

- [ ] **3. Stop cutting social text.** Reddit sends only the first 1,000
  characters to screening and 240 body characters to the analyst. StockTwits
  cuts analyst-visible bodies to 280 characters. Preserve full fetched text;
  if an actual model limit prevents classification, retain the original and
  report that limitation explicitly. Preserve links and publication times.
  Files: `tradingagents/dataflows/vendors/reddit.py`, `stocktwits.py`,
  `tradingagents/agents/post_screen.py`.

- [ ] **4. Stop classifier mistakes deleting evidence.** Relevant Intel price
  targets and a post about losses on Intel were marked off-topic and removed
  from analyst input. Other plainly optimistic posts received bearish raw
  predictions, usually downgraded to unclear. Preserve fetched evidence for
  analyst review and keep classifier judgments distinct from source content.
  Recheck relevance and stance on these saved examples before trusting totals.
  Files: social vendors and `tradingagents/agents/post_screen.py`.

- [ ] **5. Align social acquisition with settings.** The configured 100-post
  allowance controls screening only. StockTwits fetches one recent page and
  displays at most 30; Reddit requests a fixed 100-result combined page, then
  displays at most five retained posts per subreddit. Connect acquisition and
  presentation to the requested scope, disclose upstream limits and pagination,
  and avoid one source silently consuming the shared screening allowance.
  Files: social vendors, `tradingagents/agents/analysts/sentiment_analyst.py`,
  `tradingagents/web/service.py`.

- [ ] **6. Fix global-news coverage.** Yahoo fuzzy search returned an IBM-heavy
  set for broad economic queries. The loop stops when the first query fills
  the overall quota, so later configured topics can be skipped completely.
  Search the configured scope, preserve query provenance, and check relevance
  before claiming broad macro-news coverage. Do not add a replacement fixed
  company/topic whitelist.
  File: `tradingagents/dataflows/vendors/yahoo/news.py`.

- [ ] **7. Preserve news context and dates.** Yahoo parses publication dates but
  drops them from the rendered articles. Search often supplies headlines only;
  neither news nor fundamentals analysts can open a cited filing/article to
  resolve a material gap. Preserve available summaries and dates and provide
  access to primary-source context, with explicit unavailable/paywall results.
  Verify catalysts from primary sources: this run inferred Intel's earnings
  date from a prediction-market resolution date. The date happens to be correct.
  Files: Yahoo news vendor and analyst tool bindings.

### Other confirmed restrictions and output defects

- [ ] **8. Preserve requested macro observations.** FRED fetches a full window
  but sends only its newest 40 observations. Remove the extra output cut or
  provide access to the full requested series. Keep vintage/date guards and
  distinguish observation dates from publication dates. The current header
  discloses this cut; it is still lost evidence.
  File: `tradingagents/dataflows/vendors/fred.py`.

- [ ] **9. Complete prediction-market evidence.** Search fixes the upstream
  event count at 20 and defaults to six markets, then shows only each market's
  first outcome. It omits source links, resolution rules, and other available
  outcomes. Preserve event/outcome context and disclose/configure selection;
  do not treat market resolution as confirmation of a corporate event date.
  File: `tradingagents/dataflows/vendors/polymarket.py`.

- [ ] **10. Separate request success from usable coverage.** The receipt layer
  marks a normal function return successful even when its text says unavailable.
  Keep transport receipts truthful while recording actual data availability,
  omissions, clipping, and unmet requested scope separately. A completed graph
  and four saved reports must not imply complete evidence or sound analysis.
  Files: `tradingagents/dataflows/router.py` and research evidence/reporting.

- [ ] **11. Correct recommendation/action drift.** The committee chose
  Underweight and explicitly rejected Sell; a hard-coded trader instruction
  maps Underweight to Sell. Its stop was above entry, implying a short-style
  proposal, while the final decision meant avoid buying because no Intel is
  held. Preserve the committee's view and distinguish rating from feasible
  portfolio action. File: `tradingagents/agents/trader/trader.py`.

- [ ] **12. Investigate coding-context contamination.** A risk report included
  coding-score bookkeeping. Confirm where it entered before fixing isolation.
  The provider already sets project-document loading to zero, so inherited
  repository instructions are a suspicion, not a demonstrated root cause.
  File: `tradingagents/llm_clients/chatgpt_client.py` and saved prompt history.

- [ ] **13. Recheck sentiment strength.** Of 26 retained posts, 24 have unclear
  classifier stance; the report nevertheless gives a precise 5.1/10 score.
  Low confidence is disclosed. Verify the score's supporting rationale and
  ensure analyst reading of full text can correct classifier mistakes without
  presenting uncertain classifier counts as a reliable directional sample.
  Files: sentiment analyst/schema and saved social classifications.

## Verification and follow-through

- [ ] Sweep all configured and fallback vendor paths for the same fixed-field,
  clipping, early-exit, pagination, provenance, and unavailable-as-success patterns.
  Primary price history and all 12 indicators returned in this run; no specific
  price/indicator failure was established by this audit.
- [ ] Preserve requested limits (600 seconds and 100 posts by default,
  configurable), genuine upstream limits, cancellation, and historical guards.
  Removing arbitrary information loss does not mean claiming unlimited coverage.
- [ ] Verify changed paths using saved evidence and focused static/runtime checks;
  create no tests. Record actual results and any external blockers.
- [ ] Load corrected code, run Intel under the user's existing authorization,
  then inspect receipts, all four reports, both debates, committee, trader, and
  final decision. Do not overwrite or rewrite the historical run.

## Evidence

Latest audited Intel run: `840bac10-b456-4f24-895a-1e17b64d63c5`, completed
20 October 2026. All required requests succeeded; successful collection alone
did not establish complete or correct analysis.

- [Intel Q2 2026 filing](https://www.sec.gov/Archives/edgar/data/50863/000005086326000157/intc-20260627.htm)
- [Intel Q2 earnings release and cash-flow reconciliation](https://www.intc.com/news-events/press-releases/detail/1776/intel-reports-second-quarter-2026-financial-results)
- [Intel confirmed Q3 earnings date](https://www.intc.com/news-events/press-releases/detail/1782/intel-to-report-third-quarter-2026-financial-results)
- Source ledger and saved reports: configured application data directory,
  `reports/840bac10-b456-4f24-895a-1e17b64d63c5`.

## Progress

- Reviewed all four analyst reports, investment and risk debate contributions,
  committee recommendation, trader plan, final portfolio decision, collection
  receipts, and all 34 saved social classifications.
- Confirmed the SEC statement field selection in
  `tradingagents/dataflows/vendors/sec_edgar.py`.
- Confirmed Reddit screening clips text to 1,000 characters and report text to
  240 characters; StockTwits report text clips to 280 characters.
- Reviewed collection code for SEC, Yahoo fundamentals/news/prices/indicators,
  Reddit, StockTwits, FRED, Polymarket, Alpha Vantage news, router receipts,
  analyst tool binding, and trader recommendation mapping.
- Existing patch score before this audit: -96. The list was finalized before
  implementation, then the user authorized all fixes and verification. No tests
  created. Current retained-line score is recorded at final verification below.

### Implementation and focused verification

- SEC fixed field lists removed. All statement tools return the complete filed
  document and its notes, with source links and filing/period dates. Quarterly
  and annual filings are requested; duplicate tool responses are included only
  once in the model prompt, while original source receipts are preserved.
- Live Intel quarterly filing retrieval returned the escrow charge explanation
  and complete equity/liability components. Annual filing retrieval returned the
  2025 Form 10-K filed 23 January 2026. The source reader retrieved the full Q2
  issuer release and its GAAP/adjusted cash-flow reconciliation.
- Full Yahoo profile preserved alongside the unit-labelled summary.
- Social source text and quoted-post context preserved. Classifier predictions
  no longer delete posts. Acquisition follows the configured post allowance;
  Reddit is fetched first and StockTwits uses the remaining sample allowance.
  The shared classification time/post budgets still apply. A setting of one post
  cannot fully classify both sources; any remainder is explicitly unscreened.
- Reddit retains source links and all returned bodies. Live StockTwits paging
  worked beyond one page; requested counts apply after date filtering.
- Global-news queries all execute. Live checks established that combined long
  phrases were unsupported by Yahoo search. The configurable defaults now use
  individual economic topics: all eight returned 60 unique in-window matches,
  sampled fairly to the configured article limit, with no IBM-heavy substitution.
  Dates, query provenance and headline-only limitations are explicit.
- Primary-source reading is available to fundamentals and news analysts. SEC
  direct reads now use its required identifying header; the earlier 403 was
  corrected and verified. Publisher rate limits/paywalls remain explicit external
  limitations, not fabricated article contents.
- FRED no longer drops older rows from the requested window; missing observations
  are shown as missing. Prediction markets retain all returned matches by default,
  every outcome, source links and resolution rules. Live check returned ten
  markets with ten rule descriptions and links, instead of the previous six.
- Receipts retain transport outcomes and separately record unavailable/partial
  data. Evidence snapshots explicitly disclaim relevance/accuracy validation.
- Underweight is no longer automatically converted to Sell. Trader instructions
  distinguish relative exposure from feasible action and avoid unsupported shorts.
- Confirmed the coding-instruction source: personal global AGENTS guidance still
  loads despite project-document suppression. Research now runs from a temporary
  working directory with explicit developer-level financial-only scope. A live
  provider check returned only the requested operating-margin analysis.
- Sentiment requires reading original posts, correcting classifier judgments and
  explaining score weighting; scores are explicitly judgments, not probabilities.
- Automatic input collection no longer consumes agent search rounds. The saved
  two-round allowance was restored to the standard twenty via the existing
  configuration API, preserving all other settings.
- Changed collection/analysis modules pass focused Ruff checks and Python syntax
  parsing; `git diff --check` passes. `web/store.py` has pre-existing unused-import
  and import-order findings outside this change. No tests were written or run.

### End-to-end verification

- First verification pass: `0154fe75-fdd5-497f-b446-968b39207a35`. Its fundamentals
  report correctly explains the non-cash loss, equity distinction and partner
  buyout. It exposed the direct SEC header issue and remaining collection/search
  budget issues. Cancelled deliberately before loading the final corrections;
  its saved artifacts remain intact.
- Final pass: `d086a72c-b987-4182-a61b-38430bfe7915`, started 20 October 2026
  after the final restart, with all four analysts, 600-second/100-post social
  limits and twenty research tool rounds. Verification found a quarter/YTD
  number mix-up in the draft fundamentals report and remaining market-input
  shortcuts. Stopped deliberately to load those corrections; artifacts preserved.
- Additional confirmed fixes from that verification:
  - Removed forward/backward filling of missing prices and volume. Excluded
    incomplete bars are dated explicitly; raw inputs remain in source receipts.
  - Use vendor-reported OHLCV, with adjusted close separate, in a distinct cache;
    the prior cache is preserved. No adjusted or missing cell is represented as
    an observed trade price.
  - Removed the hidden 30-row maximum from requested verification snapshots.
  - Removed the eight-indicator report limit. One shared vendor registry now
    drives collection and snapshots, also recovering the previously omitted MFI:
    thirteen supported indicators are collected rather than a duplicated list of twelve.
  - Snapshot output itself is now saved as source evidence.
  - Fundamentals gets a numerical review against the original full filings
    before publication, covering period, unit and attribution consistency.
  - Upcoming earnings discussions require an issuer calendar/date-announcement
    check instead of leaving an available primary-source check unattempted.
- Current pass: `00cbc073-54c0-4983-b3d4-19c528dffeee`, all corrections loaded.
  Cancellation requested after the user directed that verification should stop.
  End-to-end verification is not complete; do not claim a fully verified pass.
  Current retained-line score: -542; no tests added or run. No further runs planned.
- External source gap confirmed independently: Yahoo's October 20 raw history
  row currently has no Close, even after a fresh request with adjustment disabled.
  October 19 is the last complete observed daily bar. The application records
  the incomplete October 20 bar and does not manufacture a replacement close.
- Batch verification resumed under the clarified instruction:
  `8854aca2-5c78-474d-9734-e7439d145a57`. One complete cycle for the current batch;
  do not interrupt it for individual findings or start additional cycles for
  individual fixes. Collect and assess the whole result first.

### Social completion correction — 21 October 2026

- That pass finished its reports but classified only 68/100 posts: 28
  StockTwits and four Reddit posts remained unscreened after the shared
  600-second deadline. It was incorrectly reported as fully complete.
- Remove the duplicate per-post `count_context` request. Validate the exact
  full-input token receipt returned by `decide` itself; retain every post.
- Require both social sources and classification of every fetched post before
  recording a completed research result. Retain reports from failed screening.
- Correct the completion status of saved partial runs without rewriting reports.
- The historical-screening UI warning incorrectly rejected version 2 receipts;
  accept both supported versions while retaining checks for uncertain labels.
- First batch verification: `ceec4a30-80f8-4174-bbab-2b9de15226e4`.
  The first Laya request hit a separate 60-second outer timeout during cold
  model loading/inference after reboot. Both sources remained unscreened.
  The new completion check correctly failed the run and retained its reports.
- Follow-up batch removes that conflicting timeout and the artificial global
  cooldown. The social Gateway transport and outer request now use the configured
  shared screening deadline. No change to the 600-second/100-post settings.
- Follow-up `df22ad21-c70b-443f-b6a0-918271233f34` failed before screening:
  the MCP transport rejected the configured 600-second deadline because of an
  additional 300-second constructor limit. Remove that arbitrary limit; retain
  positive finite timeout validation and the configured screening deadline.
- Final verification: `65317690-3277-4f16-a3a1-01d26b643ddf`, completed
  21 October 2026. StockTwits 96/96 and Reddit 4/4 classified; zero unscreened
  posts, no screening errors. The 100 invocation receipts total 400.7 seconds,
  within the configured shared 600-second deadline. All four analyst reports,
  debates, trader proposal and final portfolio decision are saved.
- Visible browser verification shows completed social coverage and no false
  historical warning. The earlier partial run is visibly failed, not completed.
  Low-confidence classifications remain explicit: 83 posts are marked unclear;
  complete processing does not certify prediction accuracy.
- Scope of this pass: social-screening completion and the false UI warning.
  Macro requests also returned errors in this pass; no claim of complete feed
  coverage or verified recommendation accuracy is made here.
- No tests created or run. Syntax checks and diff whitespace checks passed.
  Code score: -571 (28 code lines written in this correction after -543).

### Complete-run audit — 21 October 2026

Objective: use INTC; every analysis succeeds; no unresolved warnings, missing
inputs, collection failures, or known report inconsistencies. Read every report.
This objective is not achieved by the completed-social-only pass above.

- Read all nine generated reports, the unique bull/bear and risk debate
  histories, and all 100 retained social posts. Read/hash-checked every unique
  source artifact (36); duplicate source artifacts matched their stored hashes.
- Confirmed nine failed FRED requests. Direct authenticated retrieval returned
  HTTP 200 with an HTML "Site Maintenance" page instead of JSON. The public
  FRED home page independently showed the same maintenance notice. This is an
  external outage, not a missing key; no macro values may be invented or silently
  substituted. Source: https://fred.stlouisfed.org/ (accessed 21 October 2026).
- Fixed duplicate-response handling: only complete SEC filings may be folded
  in model input. Distinct indicators must retain their own results and identity,
  even if their returned error strings happen to match.
- Quote collection now awaits the existing native refresh acknowledgement
  before capturing the research book and rejects missing selected-symbol prices.
- Corrected MFI tool units: the installed Stockstats implementation returns a
  0–1 fraction. The report's 0.20 to 20/100 conversion was correct; the old
  tool description's 80/20 thresholds were inconsistent with its output units.
- Required indicator snapshots cannot silently contain calculation errors or
  missing latest values. Required input failures stop before report generation;
  remaining source failures prevent research completion. Saved failed-input runs
  are no longer labelled completed; their original reports remain intact.
- Social classification questions now name the actual instrument and pass the
  original post as plain text. Sentiment instructions prohibit deriving market
  direction from aggregate classifier counts and require author/quotation review.
  Three saved diagnostic posts confirmed that the original labels are fallible;
  changing questions does not establish classifier accuracy on all posts.
- Fundamentals instructions require explicit total-liability and equity
  reconciliation and appropriate cash-flow/financing bridges.
- Research-manager prompts now receive the same captured portfolio context as
  trader/portfolio-manager prompts, preventing advice to trim a zero holding.
- Batch passed focused Ruff checks (excluding pre-existing import-only findings),
  Python syntax parsing and `git diff --check`; no tests created or run. Loaded
  using `.\Start-TradingDesk.cmd`. Code score: -628.
- FRED recheck after implementation still returned its maintenance page; the
  corrected collector raised `VendorUnavailableError` with the maintenance cause.
  Full INTC verification remains pending until usable FRED responses return.
  The active goal remains incomplete; this is progress, not a passed full run.

### Continued artifact audit — 21 October 2026

- Revalidated the FRED blocker: authenticated CPI retrieval still returns the
  maintenance response. No research run is active; the latest INTC run remains
  accurately failed. This is the second consecutive goal turn with that blocker.
- Reconstructed the captured OHLCV frame and checked all 1,255 rows: finite
  prices/volume, unique trading dates, no dates beyond the analysis date, and
  zero invalid high/low/open/close/volume relationships. Independently recomputed
  all thirteen indicators; every rounded latest value matches the saved snapshot
  and market report. The historical October 5 EMA of 117.38 matches its source.
- Read the complete insider feed. Clarified its ownership legend: D/I means
  direct/indirect ownership, not acquisition/disposition. Transaction details
  determine buying/selling; blanks do not identify discretionary sales. Source:
  https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000032/form4.html
  (accessed 21 October 2026). This output clarification is pending the next batch
  reload/full verification; no additional research run was launched during outage.
- Code score: -630. No tests created. Full goal remains unachieved.

### External blocker audit — third consecutive goal turn

- Revalidated authenticated FRED CPI retrieval on 21 October 2026: the same
  provider-maintenance response persists. No macro observations were returned.
- Revalidated authoritative run state: no queued/running/cancelling research;
  latest INTC run is failed, not a live job awaiting a polling response.
- Loaded the remaining insider ownership clarification through the canonical
  launcher. Its focused lint and diff checks had already passed. No additional
  full research cycle or test files were created during the known outage.
- The full required INTC run, report audit of that new run, and zero-warning /
  zero-issue acceptance remain unproven. Do not mark the goal complete or replace
  missing macro observations with invented/currently unverified values.
- All remaining end-to-end acceptance requires usable FRED data. The same
  external blocker has recurred for three consecutive goal turns; mark the goal
  blocked pending provider recovery. Score remains -630.

### Operator-authorized run without FRED — 21 October 2026

- Run `88eb16c7-4b92-48c8-aed7-b6d52dc4a042` explicitly excluded FRED;
  default runs still request it. All four analysts ran and all nine reports
  were saved and read, including the unique bull/bear and risk discussions.
- All 55 source attempts returned successfully: fundamentals, quarterly/annual
  filings, insiders, company/global news, prediction markets, OHLCV, all thirteen
  indicators, verified market snapshot and both social feeds. No FRED calls.
- StockTwits 96/96 and Reddit 4/4 screened, zero unscreened; all original post
  texts were read. Processing completion does not establish label accuracy.
  Several accepted labels contradict the author's view or refer to other content;
  87 labels were unclear. This run's sentiment report used original text and user
  tags rather than treating classifier counts as directional evidence.
- Report findings: market report's "two-session uptick" is unsupported by the
  October 19–21 closes (92.03, 91.69, 92.96); this wording propagated into debate
  and final assessment. Sentiment report attaches Reddit's bearish label to the
  wrong post. Some news remains headline-only or lacks primary confirmation.
  These are observations about this run, not deterministic agent guarantees.
- Committee Underweight, trader Hold/no initiation, final Sell/avoid entry:
  different investment ratings, same proposed behavior for a flat account.
  Price observations and FRED exclusion are explicitly distinguished throughout.
- Run correctly remains FAILED: one public news article receipt was withheld by
  secret screening. A read-only diagnosis reproduced a false API-key match on an
  SK Hynix URL slug. Narrowed the key pattern to credential formats and included
  failed capture operations in completion errors. Original evidence is preserved;
  no retrospective success claim. Full workflow not rerun after this correction.
- No tests created. Code score -650. Macro coverage remains unverified.

### G11 source correction batch — 21 October 2026

- `dataflows/vendors/yahoo/snapshot.py` now computes dated, signed changes and
  up/down/unchanged directions between adjacent available closes. It identifies
  excluded incomplete bars between observations and insufficient close history;
  exchange-session completeness remains explicitly unverified. The market analyst
  prompt requires movement and streak claims to cite these dates and closes.
- `agents/post_screen.py` now returns compact source/text-SHA256-to-existing-label
  annotations to the sentiment analyst. Reddit and StockTwits rendering includes
  the matching exact screened-text hashes without duplicating post bodies. The
  mapping preserves status, admitted stance, raw prediction and stance grade.
  The analyst must match individual label claims to this identity and distinguish
  a recorded label from its own interpretation. Uncertainty thresholds and
  retained evidence are unchanged. The sentiment docstring now says structured,
  rather than deterministic, output.
- One bounded offline check passed: six changed Python files parsed; the closes
  92.03 → 91.69 → 92.96 produced down (-0.34) then up (+1.27); an excluded
  middle bar was marked nonconsecutive; one close reported insufficient history.
  A fake Laya receipt preserved unclear/bearish raw prediction/reconsider, and
  exact input hashes matched both vendor renderings, including multiline text.
  No test files or functions were created; no live feed or model was called.
- Changes reduce known input ambiguity; they do not establish analytical
  accuracy, correct historical reports, resolve headline-only evidence, or prove
  a new complete run. Retained reports, provider settings and evidence remain
  intact. No restart or research rerun was performed. This batch adds 29
  production lines and zero test lines (score delta -29; documentation excluded).

Pending: DNS/TLS error receipts from `read_research_source` omit the requested
URL and withhold the cause, limiting diagnosis. Retained v2 reports remain unchanged.


Reddit acquisition status now travels separately from screening: unavailable and
limited feeds remain coverage gaps, while a successful empty feed stays empty.
Validate this with a live source receipt and inspect the source and aggregate UI;
a rate-limited run cannot establish successful Reddit acquisition.

Real TER validation exposed that stance counts include off-topic posts. Relevance
counts are now separate; retained source text and stance predictions are unchanged.


### Laya Windows acceptance — 27 October 2026

- Installed 0.6.15 matches the reviewed source. Actual CPU/CUDA/CPU switching
  stopped the CUDA worker and restored the original CPU setting. Real retained
  CPU, CUDA, unavailable-CUDA fallback, cancellation/recovery and screening
  deadline observations are recorded in [the Laya guide](laya-validation.md).
- One TER run `a217737b-20e5-46dd-9719-1ace8529e2e9` failed in 50.58 seconds:
  the configured Qwen tokenization endpoint on local port 8899 refused the
  connection. No sentiment report or final decision was produced. No rerun.
- All 58 StockTwits posts were classified and retained. Exact questions, choices,
  scores, token coverage and separate relevance counts are visible in the UI.
  Reddit is limited, with its actual history-window reason, rather than empty.
- A separate valid current Reddit query returned an empty sample within its
  declared recent scope. This does not prove historical absence or 429 recovery.
- Five saved posts were annotated in 1.531 seconds; all existing reports stayed
  unchanged. The source-bound human review packet has 58 unreviewed labels.
- The Sources prose dropped Reddit's acquisition reason although structured
  evidence retained it. A narrow service repair now carries that evidence into
  the coverage summary. Historical model reports remain unchanged.
- MPS is explicitly unverified; the user will validate Mac after GitHub push.
  Laya prediction accuracy and successful downstream Qwen receipt are not proven.
  No tests, synthetic posts, unrelated checks or broad research reruns were used.
