# Manual portfolios and sourced index weights

Status is in progress. The user requested automatic index-weight lookup when
symbols enter a universe, editable portfolio allocations, and direct historical
simulation without research or AI portfolio synthesis.

## Required behavior

- A universe addition resolves its available S&P 500 reference weight from a
  cached, dated provider snapshot. Missing membership and provider failures are
  visible. One snapshot supplies all matching symbols.
- A person can create, edit, save and reopen a named portfolio with capital,
  per-symbol weights and residual cash, independently of research.
- Applying a dated index portfolio loads the complete snapshot membership and
  weights. Editing weights identifies the portfolio as custom. A subset is never
  silently normalized into a complete index.
- Portfolio runs open Strategy Lab directly, bind the saved portfolio revision,
  and support explicit dates, fees and fractional shares.
- Missing market inputs can be collected through the same UI workflow. Original
  provider evidence and the resulting simulation inputs remain traceable.
- The year-to-date acceptance case uses the year-start constituent snapshot and
  December 31, 2025 through November 4, 2026. It retains genuine lifecycle events
  and actual security histories, including changed or discontinued symbols.
- Existing research-based proposals, saved simulations and broker controls
  continue to operate separately.

## Verification to complete

1. Add a constituent through universe settings and observe its sourced weight.
2. Create a custom portfolio through the UI, edit its weights and save it.
3. Reload and reopen the same saved revision with the same allocations.
4. Send that portfolio to Strategy Lab, collect any missing inputs, and complete
   a simulation without research or an AI modeling request.
5. Load the dated S&P 500 portfolio, run the full year-to-date case with fractional
   shares, and inspect counts, dates, actions, cash and benchmark values.
6. Independently reconcile the saved result against its retained holdings,
   distributions and closing marks. Attribute material comparison differences.
7. Review the integrated revision and verify the affected UI after fixes.

## Development and preservation

The starting source snapshot is `6e80458` on `codex/sp500-validation`. Its source
matches the running development checkout except for the separately modified
user universe CSV. Implementation uses isolated `codex/manual-portfolio*`
branches and local commits. Integration must preserve pre-existing work and
replace only the verified changed development files. Production remains on its
separate runtime and profile.

The Maenifold Gateway is not exposed in the current tool inventory. Project
lessons cannot yet be retrieved or persisted through it.

## Browser evidence

- Created `Manual allocation smoke check`, revision 1, from the development
  universe. Cleared the draft, then set AAPL to 25% and MSFT to 50%, leaving 25%
  cash. Saved and ran it directly in Strategy Lab without a research run.
- From October 30 through November 4, 2026, the $100,000 fractional-share
  portfolio finished at $103,613.44, with $25,000 cash. The independent closing
  mark calculation is `25000 + 25000 * 349.555 / 344.77 + 50000 * 556.07 / 521.97`
  and rounds to the displayed result.
- Saved and reopened `S&P 500 YTD from IVV`, revision 1, with 503 initial holdings
  and 0.191380589433% residual cash. Strategy Lab selected December 31, 2025 to
  November 4, 2026 from its market calendar. This is a fixed starting portfolio
  from an ETF filing. Its comparison uses SPY adjusted closes over the same dates.
- The first full run exposed three real data cases. Hologic's non-tradable CVR
  needs a separate unmarked entitlement. AVB's merger delivers EQR, whose CUSIP
  matches the existing VMRK position. Comcast's retained raw corporate action
  page contains a VSNT spinoff omitted by the old normalization. Collection and
  simulation now share the same parser and recipient resolution.
