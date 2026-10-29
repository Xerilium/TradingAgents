# Laya social review

This review compares saved decisions with independent human labels. It does not
run inference, fetch posts, change research, or establish trading authority.
Export a saved `/api/runs/<id>` response to a JSON file, then run:

```text
rtk proxy python scripts/laya_review.py export saved-run.json review.json
rtk proxy python scripts/laya_review.py report review.json report.json --source saved-run.json
rtk proxy python scripts/laya_review.py sdk review.json labeled.jsonl --source saved-run.json
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
