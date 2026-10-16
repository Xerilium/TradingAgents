# T-1.12 blue-team evidence

Read the completed local META report for run `3f948cc2-5589-41fb-b691-33695ac18e8a`. Its `final_trade_decision` is a Markdown string, not a structured object: outer bold labels wrap values that begin with repeated bold labels. The frozen regression preserves those exact prefix boundaries while shortening the narrative.

Added three tests to `tests/ui_gate_regressions.cjs`:

- Redundant Rating, Executive Summary, and Investment Thesis appear only once in the display; substantive sentences, original input, and escaped raw source remain intact.
- A conflicting embedded Sell rating remains visible, as do later substantive headings and ordinary repeated words.
- Other report names and nonredundant narrative remain unchanged.

Baseline command: `rtk proxy .venv/Scripts/python.exe .paper-desk/run-bounded.py --seconds 60 -- node --test tests/ui_gate_regressions.cjs`.

Result: **27 passed, 1 failed**, 28 total, Node duration 155.8926 ms, exit 1. Failure is `Rating displayed once`, actual 2 versus expected 1. No implementation edits, provider calls, backend requests, broker operations, or journal writes were made. No Gate transition was made. This stage establishes the failing regression only; browser verification and implementation remain unproven.
