# Paper desk

Primary target: tradingagents/web/static/index.html
Related targets: tradingagents/web/static/app.css, tradingagents/web/static/app.js
Mode: Operate. Local desktop-first application with a fully usable narrow-screen layout.

The operator needs to inspect actual account exposure, run research for a configurable universe, understand the resulting evidence, and place explicit paper orders within deterministic limits. Every financial value comes from the connected broker. Missing data stays missing. The earlier canvas brief and PRODUCT.md remain historical context and are not modified.

## Research and decisions

The user explicitly replaced design questions with research and independent judgment, then pinned the product direction: "Imagine an agentic version of fidelity active trader pro, using alpacca paper trading via maenifold." This supersedes the initial candidate roll. The delivered direction is a dense linked trading workspace with watchlist, daily OHLC chart, research inspector, positions and order blotter. Paper mode and connection identity remain visible; research and execution have separate actions. No order is implied by launching research.

Primary references accessed 2026-10-13:
- https://docs.alpaca.markets/us/docs/paper-trading — paper account identity, simulated execution, order status.
- https://docs.alpaca.markets/us/v1.1/reference/getaccountportfoliohistory-1 — broker equity timeseries.
- https://www.interactivebrokers.com/campus/trading-lessons/portfolioanalyst-widgets/ — allocation, concentration, performance, activity.
- https://www.langchain.com/langsmith/observability — stepwise traces, failures, outputs.
- https://www.fidelity.com/products/atbt/help/ActiveTraderTools_Layouts_Help.html — linked tools preserve selected-symbol context.
- https://www.fidelity.com/products/atbt/help/ActiveTraderTools_Watch_List_Help.html — sortable watchlists, positions and exports.
- https://www.fidelity.com/products/atbt/help/ActiveTraderTools_Trade_Help.html — preview, placement and broker confirmation.

Seven grounded directions considered: annual-report schedules; stock-exchange listing book; statistical atlas; modernist timetable; investment committee agenda; catalog sleeve; research-library finding aid. The roll assigned position six, catalog sleeve. The category rut is a wall of quote tiles; its predictable opposite is a monochrome terminal. Neither determines this desk.

Challenger judgments: emission rail competitive on clarity; metro tiles declined on density; cassette J-card declined on financial reading; event catalog competitive on browseability; centre rail competitive on hierarchy; Saville sleeve reinforces the assigned direction. The assigned design takes disciplined continuous reading from the rail, explicit selection from metro, restrained sectional color from the catalog, and compact labeling from the sleeve without borrowing ornamental motifs.

## Direction contract

THESIS: Portfolio, evidence, and execution are adjacent readings of one account; the desk uses a continuous ledger, not disconnected quote cards.

OWN-WORLD: User-pinned Active Trader Pro familiarity: charcoal navy workspace, lighter instrument headers, green execution controls, muted cool lines, 3px controls, tabular figures, Segoe UI system typography. A trader keeps several linked tools open for long sessions, so the low-luminance workspace separates instruments through rules and compact headers rather than bright tiles.

STORY: Establish connection and paper identity, inspect capital and concentration, select a universe, run research, read each agent artifact, inspect deterministic proposals, explicitly submit or pause paper orders.

FIRST VIEWPORT: A horizontal workspace navigation and account strip precede three linked instruments: compact FANGMAN watchlist at left, daily OHLC chart in the larger center, selected-symbol agent evidence at right. Positions and the order blotter form a second row. Run research sits at upper right and execution pause remains in the global navigation. Account equity is a second chart tab; no invented prices or chart points appear before broker data arrives.

FORM: Active Trader Pro linked workstation, directly pinned by the user after the successful roll. The user's explicit direction supersedes the generated candidate and its seed contract. Signature interaction: selecting a ticker links the watchlist, OHLC chart, quote, and agent evidence; opening research preserves run and symbol context. State motion is limited to a short activity pulse and 160ms control transitions; reduced motion is honored.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
