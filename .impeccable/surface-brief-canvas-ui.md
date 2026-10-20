# Surface brief — TradingAgents canvas UI

Scope: single-page Copilot canvas extension UI (Configure / Run / Results) for a multi-ticker portfolio run of TradingAgents. Mode: Operate. Audience: the owner-operator of this repo, running LLM trading analyses on FANGMAN + semiconductor tickers and reading what the 12-agent committee decided. Job: start a run, watch it work, read the verdicts. Constraints: canvas host serves one HTML entry over loopback; host theme tokens where available; no API keys yet, so readiness state must be visible.

## Direction contract

THESIS: This surface owns the committee record — a trading analysis rendered as live minutes of an investment committee, not a dashboard grid or a terminal feed. It refuses the category default of dark dashboards with neon accents and KPI tiles; the reader sits in the chair's seat: one ticker under discussion at a time, its debate unfolding as typed minutes while the rest of the portfolio recedes into an attendee rail.

OWN-WORLD: Deep ink ground with warm off-white record text; system-sans chrome for structure, Courier Prime typewriter mono for the committee's voice — the only face that carries the record. One restrained accent: live red for whatever is speaking or moving now; muted grey for completed entries. Components: phase band with one tick per portfolio ticker; 12-seat attendee rail (filled = done, caret = speaking); minute lines that type on and fade as they complete; a sparkline identity line per ticker; a PENDING rating box that stamps when the verdict lands.

STORY: The user starts a run over their FANGMAN + semis portfolio, then watches the committee work: the phase band shows which ticker is under discussion (7/16), the minute stream shows each agent's entry as it happens, and the side panel holds that ticker's sparkline, live bull/bear tally, and the rating box that fills at the end. When a run completes, they flip through the minutes per ticker to read verdicts — Buy/Hold/Sell with reasoning — and can re-run any subset.

FIRST VIEWPORT: Left: topbar (RUN-0147 · LIVE chip), phase band "TICKER 7/16 · NVDA · DEBATE ROUND 1" over 16 tick marks, then the minute stream in Courier Prime — completed entries faint, current line typing with a caret. Right rail: 12-agent attendee list (analysts → bull/bear → research manager → trader → risk ×3 → portfolio manager) with status dots; below it the NVDA sparkline, PENDING rating box, and BULL/BEAR tally. Primary action (start/stop run) sits in the topbar.

FORM: Single self-contained HTML surface served over loopback, position 1 of the ordered list (single-page canvas UI; multi-file SPA and external browser app were rejected — the canvas host takes one entry point). seed: none (unavailable)

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
