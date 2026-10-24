# Stack authorities
- pyproject.toml owns Python >=3.11, setuptools packaging, dependency extras, Ruff and pytest configuration. requirements.txt delegates installation to that project metadata; follow README.md for portable setup.
- Python backend: tradingagents/web; research graph and analysts: tradingagents/graph and tradingagents/agents; data vendors: tradingagents/dataflows; adapters: tradingagents/integrations and tradingagents/llm_clients.
- Browser JavaScript/CSS and vendored charts: tradingagents/web/static. Serena configures Python and TypeScript language servers. TypeScript serves the JavaScript frontend; symbol lookup in tradingagents/web/static/app.js is verified.
- Existing .venv is the desk environment; .venv-nautilus-v1 is the separate native execution environment. Do not merge them or install packages without the user's specific authorization.
- Integration responsibilities and broker authority are defined in README.md, not inferred from upstream library features.
## Source
- pyproject.toml; README.md; .serena/project.yml. Read 2026-10-24.
