# Obtain simulation-ready historical data on demand

Status: Open
Reported: 26 October 2026
Product: TradingAgents, primary checkout C:/src/TradingAgents
Area: Strategy lab -> Simulations and Experiments; Markets -> Source data

## Problem

A user preparing a simulation must be able to obtain the required historical dataset through a clear UI path. Loading saved plans and data currently leaves the user with a dataset that cannot satisfy the simulation requirements and no direct collection action or guided route from that form.

This is a collection-to-simulation workflow gap. Do not assume the application has no historical-data collector: Markets already exposes date ranges, interval and adjustment choices, including raw daily prices. Reuse that collector. Verify its existing calendar, instrument and completeness evidence before deciding which backend changes are necessary.

## Observed evidence

During the internal-browser walkthrough on 26 October 2026:

- Strategy lab -> Simulations -> Setup -> Load saved plans and data listed seven saved order plans.
- The only listed daily dataset was META, 23 October 2024 through 23 October 2026, with split adjustment.
- Simulation profile details required complete raw daily bars, a sourced session calendar and an instrument receipt. It explicitly prohibited relabeling split-adjusted data as raw.
- No simulation-ready dataset was established, and no preview or simulation was run.

The saved selector is evidence for this view, not an inventory claim about every research/chart artifact in the application.

## Required result

1. From Simulations and Experiments setup, provide an obvious action or direct guided route to collect compatible data for the chosen stock and historical window. Reuse existing collection services and retained artifacts; do not build a second collector.
2. Make the required profile explicit: exact symbol, daily interval, raw prices, supported feed/currency/session, sourced calendar and instrument evidence. Identify incompatible existing datasets and explain why they cannot be used.
3. Retain collection provenance and validate paging, duplicate/missing sessions, requested coverage and completed-bar status against the actual simulation eligibility checks. Do not invent calendar sessions, fill missing prices or silently change adjustment labels.
4. Show collection progress and actionable provider/coverage errors. A successful request alone must not be called simulation-ready. Preserve older artifacts and their actual provenance.
5. When collection succeeds, make the exact compatible receipt available in the original setup. Preserve the user's chosen plan/strategy and form entries. Allow eligible retained data to be reused without another download.
6. Keep collection, preview and execution separate. Collecting data must not start research, a simulation, an experiment or a broker action.

## Acceptance evidence

Use the actual UI and installed provider to collect an authorized real dataset, then show that the exact receipt passes the existing simulation preview validation for a compatible saved plan and requested window. Confirm the same data-selection path is available to Experiments without starting an experiment merely to demonstrate collection. Report any unresolved provider or coverage limitation accurately. No mocks, synthetic data, automatic research reruns or duplicate collectors.

This issue records the requirement; it does not authorize running collection or simulations during this logging task.

## Source

- Internal-browser Strategy lab walkthrough, 26 October 2026.
- .agents/skills/use-tradingagents/references/markets-research.md, Current-market retained history form.
- .agents/skills/use-tradingagents/references/strategy-alerts-settings.md, Simulations and Experiments.
- tradingagents/web/market_history.py: explicit adjustment selection and historical collection.
- tradingagents/web/evaluation.py: simulation exact-symbol/raw/daily/completeness checks, calendar hash and artifact references, session coverage validation.
- Source inspected at 580f1c8 with existing working changes preserved.
