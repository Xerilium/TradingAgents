# Windows command entry points
- Prefix shell commands with rtk. Use rtk proxy for commands without a wrapper.
- Canonical app start, from C:/src/TradingAgents: rtk proxy .\Start-TradingDesk.cmd.
- Canonical UI: http://127.0.0.1:8098/. Preserve one server; do not choose alternate ports.
- tradingdesk.launch.json selects existing data/native/credential paths. Do not print credential values or substitute an empty data directory.
- Read-only Git context: rtk git status --short --branch; rtk git log -5 --oneline.
- Use Serena lsp.get_symbols_overview, lsp.find_symbol and lsp.find_referencing_symbols before broad source reads. Serena symbol line numbers are zero-based.
- No test/build/lint command is automatically authorized by onboarding. Read AGENTS.md and the current task first.
## Source
- README.md; AGENTS.md; Start-TradingDesk.cmd; tradingdesk.launch.json; Serena instructions. Read 2026-10-24.
