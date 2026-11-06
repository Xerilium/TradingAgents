---
version: 1
slug: "tradingagents-web-static-app-js"
primary_target: "tradingagents/web/static/app.js"
related_targets: ["tradingagents/web/static/index.html","tradingagents/web/static/ui-orders.css"]
---

# SPY portfolio — daily index-management workspace

Mode: Operate. Scope: the existing SPY portfolio route (#spy), its account/fund-plan/rebalance composition and links into supporting workspaces. This registers the current surface and confirmed user requirements; it does not approve a replacement visual world.

## User and job

One owner-operator checks their personal SPY-benchmarked fund daily: understand the account and reserves, review the investment budget and dated holdings, inspect the rebalance, use only specifically authorized execution, and reconcile outcomes or exceptions. Research, charts, simulations and general trading tools support this job.

## Current rendered baseline

At the inspected 1920 × 1080 development viewport, the first sidebar entry is SPY portfolio. An account balance strip and observation time precede the position count/reconciliation line and the existing SPY rebalance panel. That panel contains a compact reserve/budget summary, separate native editing/detail disclosures, automatic-trading status and the existing enable, preview and submit controls. The inspected account was empty, with no saved fund plan and automatic trading off. These are dated observations, not defaults or proof that populated workflows pass.

## Design requirements

- Target actual 1920 × 1080 or larger only. A scaled Browser capture is not a smaller layout.
- Make the current situation, blocking exceptions and next useful action clear at a glance. Keep setup, editing and technical evidence secondary but accessible.
- Preserve the incumbent charcoal surfaces, system typography, tabular figures, native focus/disclosures and explicit labeled states while the critique determines the next coherent refinement.
- Reuse real account, reserve, holdings, rebalance and reconciliation capabilities. Do not add fictional metrics, source dates, performance, tax-lot claims or backend features to fill space.
- Keep unknown/stale observations explicit. A working rebalance does not prove SPY return parity.
- Preserve all supporting workspaces and the separate prepare/approve/submit and standing-authority boundaries. No paper trades, approvals or authority changes are authorized during critique.

## Evidence and unresolved design work

Source baseline: nautilus 6dfccd4; application navigation delivered in 3611b93. Current rendered evidence and the critique backlog belong in docs/issues, not in served assets. Existing tokens are documented in DESIGN.md. The legacy paper-desk brief is historical, not this surface's current task contract.

No new composition, concept seed or visual-quality verdict is selected here. Next: independent design review and detector/browser assessment, then prioritize one coherent improvement batch from their combined findings. Merely registering this context does not complete the SPY journey.
