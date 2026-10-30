# Strategy Lab cannot create an experiment preview

Status: Reproduced in the installed app; root cause under investigation
Owner: Codex subagent `strategy_preview_repro` (diagnosis)
Coordinator: Codex parent
Reported: 30 October 2026

## Observed failure

In the installed production desk on port 8098, **Save Immutable Preview**
returns `Exact installed native 1.231.0 converter metadata is unavailable`.
The preview and its result cannot be displayed. The [[Strategy Lab]] form
retains its entered values, and **Run this exact experiment** remains disabled.

## Real reproduction before any fix

1. Open Strategy Lab > Walk-Forward Experiments in the built-in browser.
2. Load the existing strategies and retained data.
3. Select `Amazon 50-day moving average demonstration`, revision 1, with its
   existing one-share entry/exit rules; select the retained raw AMZN history
   covering 2024-10-28 through 2026-10-27.
4. Set the experiment window to `2025-02-03T00:00:00-05:00` through
   `2025-12-31T23:59:59-05:00`, with explicit hindsight availability.
5. Use USD 1000 of simulated cash; rolling windows of 126 training sessions,
   21 validation sessions, one session per gap, 21 later test sessions and
   21-session steps. Use the single fixed strategy (grid, one trial, seed 0).
6. Select return/maximize, drawdown/minimize as tie-break, minimum one closed
   trade, at most 12 native runs, 180 seconds overall and 30 seconds per trial.
   Use one scenario: zero fee per order, fill probability 1, slippage
   probability 0 and seed 0. These are teaching assumptions, not broker facts.
7. Click **Save Immutable Preview** once. Observe the error above.

The coordinator observed this failure at about 14:50 Pacific. The read-only
`/api/evaluations` endpoint returned an empty `items` list both before and
after. No experiment execution, research run, order or retry was started.

## Evidence and scope

- Screenshot: `C:/src/printer/.local/strategy-preview-error-20261030.jpg`.
- Source checkout: `86fc737fb01957294154b1bf49d13b1aa92fb653`.
- Installed application source: `5b8fc417d29fc37511149f4f99a064ae6b51073e`.
- Investigation target: `tradingagents/web/evaluation.py::conversion_manifest`
  and the configured native runtime's actual installation layout.
- No source fix, dependency change or installation has been made for this issue.

## Acceptance

Identify the observed cause, apply only a targeted fix supported by this real
reproduction, obtain a fresh independent review, then verify the same saved
inputs can produce a preview with exact converter provenance. Keep preview
creation separate from execution and preserve all broker controls. No mocks,
invented results, implicit data fetches or unrelated UI changes.
