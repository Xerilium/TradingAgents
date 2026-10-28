# Laya social review

This review compares saved decisions with independent human labels. It does not
run inference, fetch posts, change research, or establish trading authority.
Export a saved `/api/runs/<id>` response to a JSON file, then run:

```text
python scripts/laya_review.py export saved-run.json review.json
python scripts/laya_review.py report review.json report.json --source saved-run.json
python scripts/laya_review.py sdk review.json labeled.jsonl --source saved-run.json
```

Outputs must be new files. Keep the exact original run file: report and SDK
export require it, verify its digest and compare every evidence field against it.
Only the review annotations may be edited. Review each original post independently of the model
prediction. Set `review.status` to `reviewed`, supply reviewer and ISO date,
and enter a boolean `about` and a `bullish`, `bearish`, or `neutral` stance.
Use `ambiguous` when a label cannot be decided; leave unreviewed posts blank.
StockTwits tags and model labels are not human ground truth. Preserve the input
hash and record reviewer disagreements in notes. Sample across sources, tickers,
time, language and classification outcomes, including unscreened posts.

The report counts ambiguous, unreviewed, missing-bound-prediction and invalid
rows separately and compares only reviewed, classified rows with recorded policy
model revision and recorded questions. Tables are grouped by exact policy,
model identity and ordered question hash. They show human labels against saved policy outputs,
including `unclear`, rather than an invented aggregate accuracy. Source evidence
can lack recorded questions: those rows remain reviewable but are excluded from
SDK JSONL. Never substitute today's wording for missing historical questions.
SDK JSONL contains only complete reviewed rows with recorded native questions;
running the SDK evaluation itself would perform new inference. Its default
binary relevance threshold is 0.5, distinct from the app's policy.

Acceptance requires a representative, independently labeled sample, documented
review rubric and disagreements, coverage and confusion counts with denominators,
and separate held-out calibration and evaluation data before claiming accuracy
or calibrated probabilities. Existing evidence and synthetic checks do not meet
that bar. CPU/GPU parity, actual throughput, fallback behavior and quality on
real posts remain hardware and data dependent; verify them separately on the
target machine. The multilingual checkpoint ships without fitted temperatures.

References: [Laya 0.4.14 answers and calibration](https://raw.githubusercontent.com/NandhaKishorM/laya/v0.4.14/docs/questions-and-answers.md),
[Laya evaluation format](https://github.com/NandhaKishorM/laya/blob/main/docs/evals.md).


## Windows release 0.6.15: observed paths

Validation on 27 October 2026 used original retained TER and VECO posts with
Laya Python SDK 0.4.14 and the pinned multilingual checkpoint. No synthetic
posts or model-generated gold labels were used.

- CPU: five TER posts completed on the actual CPU. CUDA: the same five TER
  posts and one VECO post completed on actual CUDA. Input hashes were preserved;
  the five-post CPU and CUDA labels agreed for this small sample.
- Fallback: a process-scoped unavailable-CUDA condition requested GPU and used
  CPU, with the actual device and reason recorded. GPU out-of-memory fallback
  was not exercised.
- Cancellation: cancellation before dispatch and during inference returned no
  prediction, stopped the owned worker and created a replacement. Subsequent
  real inference succeeded in those recovery cases. A separate warm-worker
  cancellation returned 2.266 seconds after cancellation; it was not instant.
- Screening deadline: the interrupted five-post batch recorded zero classified,
  five unscreened and an unknown in-flight outcome. It did not replay the batch
  or accept a late response. A direct deadline case did not establish worker
  replacement because completion and deadline could race.
- Each SDK record contains the exact questions, actual ordered SDK-rendered
  choices, ordered question hash, raw answers and full distributions, inference
  timing, correlation IDs, model revision and input-token coverage. Existing
  application logs record batch identity, count, device and elapsed time without
  post text. The analyst receives these decision records as protected evidence:
  context compaction cannot summarize away the questions or scores. Original
  source text remains separately available to the normal evidence budget.
- Collection availability is separate from screening. An unavailable or limited
  Reddit response remains a gap; only a valid successful empty feed is empty.
  Relevance counts are separate from stance counts and source text retention.
- macOS MPS remains unverified. The user will validate it on a Mac after the
  source is pushed. Windows results do not establish macOS behavior.

These observations prove the exercised integration paths, not classification
accuracy. Real TER examples exposed questionable high-confidence decisions:
a promotion for another ticker was marked relevant/bullish, and a factual
earnings item was marked bearish and off-topic. An independent AI review flagged
these examples, but its judgments are not human ground truth. Preserve them for
human review. Do not tune thresholds or report accuracy from this small sample.
The 0.3 relevance and 0.5 unique-winner stance thresholds remain uncalibrated
application policies; a large probability is not a reliability guarantee.

Local evidence: `laya-validation-20261027/{cpu-ter,cuda-ter,cuda-veco,fallback-ter,
interruptions,screening-deadline,warm-cancel}.json` in the operator's visualization
folder. These are local artifacts, not bundled user data or committed post text.


## Installed research and saved-post acceptance

On 27 October 2026, installed Windows 0.6.15 completed CPU → CUDA → CPU
switching. The CUDA worker exited when CPU was restored; the original CPU
setting and all other research settings were kept.

Real TER run `a217737b-20e5-46dd-9719-1ace8529e2e9` took **50.58 seconds** and
**failed**. The configured Qwen endpoint `http://127.0.0.1:8899/v1` refused the
connection required for token counting. A separate bounded GET of its models
endpoint was also refused. No downstream LLM response, sentiment report or final
recommendation was produced, so this is not a successful full research run.
It was not retried and the configured provider was not changed.

The same run did complete actual CPU screening of all **58 StockTwits posts**:
21 bullish, 30 bearish, 3 neutral and 4 unclear, with zero unscreened. Separate
relevance outcomes were 24 related, 21 uncertain and 13 off topic. Exact questions,
ordered rendered choices, raw answer probabilities, model identity and full-input
coverage were present in saved evidence and the built-in browser.

Reddit was **limited**, because the requested historical window could not be
established from the recent-items interface. Its structured acquisition object
and Social report preserved that reason. The generated Sources prose initially
dropped it; the narrow follow-on service repair preserves acquisition status,
reason, fetched and eligible counts in the coverage gap and prose. No historical
model report was rewritten. A separate small current Reddit query returned a
valid empty sample for its past-week scope. That does not establish historical
absence or exercise an HTTP 429 response. Actual live rate-limit recovery remains
provider-dependent and was not demonstrated in this run.

The saved-run local annotation then screened exactly five retained StockTwits
inputs in **1.531 seconds**, with one dispatch. All existing report values were
unchanged; this failed run had no recommendation to compare. Its five input
hashes, full questions, ordered choices, raw probabilities, model identity and
successful CPU receipt were saved. `run-before.json` and `run-after.json` retain
the before/after evidence. A fresh source-bound `review.json` contains 58 blank
human labels; `review-summary.json` counts them as unreviewed, not correct.

The integrated prompt builder protects the decision record from compaction, but
actual downstream model receipt of that payload remains **unverified** until the
configured model server is running and a request succeeds. Starting that external
server, changing providers and repeating research were not part of this check.


## Follow-on 0.6.16 installation

Windows 0.6.16 includes the independently reviewed acquisition-summary repair.
The installer completed with exit 0 at the canonical Programs location. Actual
installed hashes match committed source for the Laya runtime, post screen,
sentiment analyst, protected evidence builder, Reddit collector, service and UI.
All nine saved-record payload fingerprints match the pre-update live backup.
The paper account reconnected, Laya returned ready on the original CPU setting,
and the preserved Social and Local Laya batch reports opened in the built-in
browser. No further inference or research was run after this diagnostic repair;
the earlier generated coverage prose remains historical evidence.

Installer SHA-256: `d5c1f82ef891b4b8e7feada4bebc05281636f69d03dea5f509f33a3bd9ff9a80`.
The adjacent 448-byte Tauri updater signature was created with the existing key,
bound to version 0.6.16. This is updater signing, not Windows Authenticode.
Local installation snapshots are `packaging/build/release-{before,after}-0616.json`
and `release-installed-0616.json`; the UI capture is `laya-windows-0616.png` in
the operator's visualization folder. Runtime and CUDA dependencies were not rebuilt.
