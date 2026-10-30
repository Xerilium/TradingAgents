# Strategy Lab cannot create an experiment preview

Status: Reproduced in the installed app; runtime-layout cause confirmed
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

## Confirmed cause

The diagnostic agent verified the running native worker uses
`C:/Users/brett/.cache/trader/production/runtimes/native/python.exe`.
The installed and checkout copies of `conversion_manifest` are identical.
They derive `runtimes/Lib/site-packages`, which does not exist. The helper
assumes a development virtual environment's `Scripts/python.exe` layout.

The actual package directory is `runtimes/native/Lib/site-packages`. It has
exactly one matching `wranglers.cp313-win_amd64.pyd`, `wranglers.pyx`, and
distribution metadata identifying Nautilus 1.231.0. The desktop launcher
explicitly distinguishes development and installed layouts (`backend.rs`).
No dependency installation or version change is indicated. Keep all existing
file/version checks; correct only the interpreter-relative library path.
The failure precedes later history/window validation, so this diagnosis alone
does not establish that the complete experiment can run.

## Reviewed source correction

The implementation changes only `conversion_manifest`: derive the runtime
directory from the interpreter's parent and move up once only for the
development `Scripts` directory. Then read `Lib/site-packages` under that
directory. The change is four added lines and one removed line; it introduces
no search or fallback to another installation.

Independent reviewer `strategy_preview_fresh_review` approved the source logic
at module SHA-256
`55904b8b8843c704f8bdf23637730b56ee4fd23ad7ca73afd0e16ecfb778f722`.
The reviewer independently confirmed the real installed files and unchanged
version/artifact/hash checks. Packaging and the same real UI reproduction are
still pending; this issue is not closed on source review alone.
