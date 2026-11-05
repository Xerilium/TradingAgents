---
name: run-tradingagents
description: Run, drive, and screenshot TradingAgents using its already-running development desk at http://127.0.0.1:8099/. Use for real UI verification. Do not start an alternate server or operate production.
---

# Drive TradingAgents development

All paths are relative to the repository root. Use `browser.mjs` beside this skill: a JSON-lines Playwright REPL over the **real running app**, not a test suite. Load `use-tradingagents` for workspace controls and action boundaries; reuse its startup and Markets references rather than copying their inventories.

## Run: agent path

Use the built-in browser at **http://127.0.0.1:8099/** for visible interaction. After setup below, run this verified driver flow from Git Bash:

```bash
node .claude/skills/run-tradingagents/browser.mjs <<'EOF'
{"action":"open"}
{"action":"click","selector":"#navigation a[href=\"#markets\"]"}
{"action":"wait","selector":"#stock-search"}
{"action":"fill","selector":"#stock-search","value":"AAPL"}
{"action":"wait","selector":"#result-count:has-text(\"1 matching stocks\")"}
{"action":"text","selector":"#result-count"}
{"action":"screenshot","name":"markets-aapl"}
{"action":"fill","selector":"#stock-search","value":""}
{"action":"wait","selector":"#workspace-save-status:has-text(\"All changes saved\")"}
{"action":"status"}
{"action":"quit"}
EOF
```

This filters Markets, saves an image, clears the filter, and waits for the ordinary workspace save. The observed result was **1 matching stock / 503 configured**, with `errors: []` and `blocked: []`; counts and prices are not constants. Read the saved PNG and confirm it shows the requested view.

Screenshots: `.local-workspace/run-skill-generator/screenshots/<name>.png` (ignored). The driver uses its own temporary Edge context at 1440 × 1000. `quit` or stdin EOF closes **only that browser**, leaving the desk and Nautilus running.

| Action | Fields / result |
| --- | --- |
| `open` | Establish normal cookie session; verify product and standard development-profile identity before opening the UI. |
| `click`, `fill`, `wait` | Playwright `selector`; `fill` also takes `value`. Use real controls, not injected events. |
| `text` | Print the selected element's visible text, not API bodies. |
| `screenshot` | Simple filename stem in `name`; no paths. |
| `status` | Page/console/HTTP errors and blocked requests. Any recorded error/block makes exit nonzero. |
| `quit` | Close the owned browser context. |

## Setup and build boundary

Verified host: Windows 11, Git Bash, Node 26.12.1, installed Microsoft Edge, Playwright 1.65.0. No global package install or browser download is needed. Install the locked driver dependencies:

```bash
npm ci --prefix .claude/skills/run-tradingagents --ignore-scripts --no-audit --no-fund
```

The driver is plain JavaScript; there is no compilation step. Its static syntax check was:

```bash
node --check .claude/skills/run-tradingagents/browser.mjs
```

**Attach only.** The user supplied the existing **Start-TradingDesk-Dev** desktop shortcut as the approved launcher. Do not invoke it while the desk is running. If 8099 is unavailable or profile identity does not match, stop and ask the human; never choose another port, kill a listener, or start a replacement server. Normal development setup is in [the local guide](../../../docs/local-desk-guide.md) and [packaging guide](../../../packaging/README.md). A clean-machine Tauri build/start and shortcut invocation were **not verified in this task**; this skill does not claim otherwise. No test suite was run.

## Boundaries and observed gotchas

- Only port **8099** is approved here. Port 8098 is production. This driver has no server launch, shutdown, broker, research, or credential commands.
- The profile-hash check was verified on this ASCII Windows home path. Unicode case-folding or a symlinked home can cause a safe refusal; it is not a portable identity guarantee or proof of the loaded code revision. Investigate a mismatch rather than removing the check.
- It permits selected retained GETs and incidental `/api/workspace` saves using the app's existing session/CSRF checks. It aborts external **browser** requests and other mutation routes, not server-side background traffic. This is not a sandbox or a grant of authority for arbitrary clicks.
- Account/Integrations credentials and provider-model discovery are deliberately blocked. Do not drive Settings, Refresh, collection, research, approvals, submissions, cancel/replace, or recovery with this read/navigation harness.
- **Search is not inspection.** Filtering AAPL left another instrument open in Stock review. Do not claim the detail panel belongs to the filtered row. Batch selection remained unchanged.
- **Navigation can save preferences.** Wait for **All changes saved**; a screenshot taken immediately after typing can show an unsaved status. These are view changes, not new research or orders.
- **Narrow pane hid the stock table.** The 1440 × 1000 driver viewport showed the row and its real price/source labels. Reset any built-in-browser viewport emulation after inspection.
- **Browser references went stale during polling.** Fresh `find` + `form_input` still failed in the visible pane. Native pointer/keyboard input worked; the driver uses live CSS locators. Do not solve this by injecting change events.
- `chromium-cli` was absent on this host; the committed Playwright REPL is the working replacement. Linux, macOS, desktop tray controls, broker execution, and broader product acceptance were not verified.
