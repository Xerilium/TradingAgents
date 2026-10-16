# Feature-freeze acceptance

Current verdict: accepted. Functional acceptance and final display UAT passed; T-1.10, T-1.11 and T-1.12 are done. This checklist does not replace Gate stage evidence.

Final functional evidence: source `0287be2`, actual completed run `3f948cc2-5589-41fb-b691-33695ac18e8a`, independent `FINAL_PRODUCT_ACCEPTANCE.md`, and coordinator `LAYA_T110_UI_UAT.md`. T-1.10 and T-1.11 are done. The final run demonstrates actual feed/model/research consumption with uncertainty and deferred coverage disclosed. Paper submission safeguards were exercised with fake brokers; the live blotter is empty and no verification orders were submitted or canceled. This does not certify upstream financial accuracy, general sentiment accuracy, or actual fills.

T-1.12 final evidence: independent `HEADINGS_T112_RED.md` reports 28/28 UI regressions passed. The actual completed report renders one label per field, preserves the original full source and scrolls inside its fixed panel. Final screenshot: `.impeccable/review/social-final-clean-research.png`. No additional inference or broker action was performed for this display correction.

## Corrected product scope: T-1.10

The user rejected the broad research-approval role for Laya. The controls below
remain historical evidence about that integration, not acceptance criteria for
social sentiment. T-1.10 replaces that role; do not tune broad-review prompts or
substitute another reasoning model to clear recommendations.

Required current evidence:

- The actual desk graph sends individual date-filtered social posts through the
  Maenifold MCP SDK to Laya, with instrument context and typed relevance/stance
  questions. Excerpts and unavailable feeds are disclosed.
- Multilingual token preflight, bounded serialized calls, timeout handling and
  explicit rate-limit backoff preserve uncertain or unscreened posts.
- Persisted source counts and individual classifications match the rendered UI;
  unavailable is distinct from neutral. Historical research audits remain intact.
- No research-completion, proposal, or submission decision depends on Laya
  clearance. Completed research and evidence integrity remain required.
- Manual approval, paper identity, pause, current executable quotes, sizing,
  allocation, cash reserve and idempotency guards remain independently tested.
- Broker submission tests use fakes. No verification order may be placed in the
  user's Alpaca account. Live read-only checks are distinct from simulated fills.
- Independent review, bounded live social classification, visible UI UAT and
  accepted-code runtime verification are required before completion.

T-1.9 separately corrects tokenizer head-budget preflight against the selected
checkpoint configuration. Its boundary tests must pass without weakening the
full request limit.

## Actual-model findings after baseline

- Choice v1: correct labels on complete and missing-source controls, wrong consistency labels on deferred and inconsistent controls. All four returned `reconsider`, including the valid positive, so this was not a useful gate. A wrong label was not an authorized proposal.
- Frozen candidate v2: only the positive matched; all three negative/control distinctions returned A/A. The positive still returned `reconsider`. Candidate is not accepted and has not replaced application questions.
- Reversed option order exposed a cache collision: the returned result was cached from forward order and failed exact sequence-hash comparison. No reverse inference occurred in that failed attempt. Adapter cache correction independently passed 58 tests; controlled runtime verification remains pending.
- Raw immutable receipts: `.paper-desk/laya-control-*.json`. Test exit zero proves transport verification, not semantic acceptance.
- Corrected-cache live forward and reverse both ran uncached, matched their own preflight and had different sequence hashes. T-1.7 completed; adapter commit `11b2b4f`, evidence commit `7c3672a`.
- Current choice questions correctly identify incomplete evidence in the unchanged saved META summary. This is a negative-case success, not full acceptance.
- After the cache fix, reversing option order changes missing-source B/B to A/A and deferred B/B to A/A. Original first-pass controls remain fixed. Source audit found no option-index remapping defect; model semantic/order sensitivity remains unresolved.

## Verified baseline, 2026-10-15

- TradingAgents commit `447247e`; installed Laya adapter commit `3e131ad`.
- Service, Gateway, Laya budget/cancellation and quote tests: 319 passed in 26.45 seconds under a 90-second deadline.
- Paper engine, explicit rate-limit retries, server and scale tests: 146 passed in 1.50 seconds under a 60-second deadline.
- Context and preview evidence: `LAYA_T11_FINAL_RED.md`, `LAYA_INPUT_UI_UAT.md`. Exact saved inference matched preflight; this does not establish semantic decision correctness.
- Live desk reconnect restored seven market-closed references. No orders or new full research batch were placed during verification.

## Superseded historical remaining acceptance

The list below records the earlier T-1.7/T-1.8 plan, not work still required by
the current product scope. T-1.7 was completed as recorded above. T-1.8's broad
research approval design was superseded by T-1.10; its neutral-choice acceptance
tests are archived under `tests/retired/`. The current requirements are the
T-1.10 checklist at the top and independent Gate evidence. Do not reintroduce a
research approval model to satisfy these historical items.

1. T-1.7: repair saturated action-head escalation, selected human outcomes, malformed/missing answer behavior and margin telemetry. Require independent adapter regression review and deployed contract verification.
2. T-1.8: neutral-choice evidence checks, strict explicit application mapping, versioned audit and historical-result handling. Require both positive and negative actual-model controls, including option-order reversal and saved META evidence regression. Schema tests alone are insufficient.
3. Verify the actual current UI renders new review inputs and decisions accurately, preserves explicit expansion/inner scrolling, and explains blocked proposals without treating model confidence as permission to submit.
4. Re-run affected integration tests after final changes, preserve manual approval, paper account, quote, sizing and idempotency guards, then commit scoped changes.
5. Advance remaining Gate items only after independent red acceptance; re-read Gate status and verify the running service uses the accepted revision.

Do not claim all work complete while a semantic control, runtime verification or Gate item remains unresolved. Existing historical research must remain historical; validation artifacts must not overwrite it.
