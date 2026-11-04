# Windows command entry points
- Canonical app start, from C:/src/TradingAgents: .\Start-TradingDesk.cmd.
- Canonical UI: http://127.0.0.1:8098/. Preserve one server; do not choose alternate ports.
- Read-only Git context: git status --short --branch; git log -5 --oneline.
- Use Serena lsp.get_symbols_overview, lsp.find_symbol and lsp.find_referencing_symbols before broad source reads. Serena symbol line numbers are zero-based.
- No test/build/lint command is automatically authorized by onboarding. Read AGENTS.md and the current task first.
## Source
- README.md; AGENTS.md; Start-TradingDesk.cmd; Serena instructions.
