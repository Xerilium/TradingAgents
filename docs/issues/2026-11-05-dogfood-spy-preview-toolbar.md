# Dogfood: compact SPY proposed-trade review controls

Status: complete for the scoped toolbar improvement, independently source-reviewed and observed on the real development desk at 1920 × 1080. No paper trades are authorized.

## Observation and scope

Baseline `a98afa6` on `nautilus`. The current loop brief and completed overview/account-exception items were read first; those checkpoints were not repeated. An actual retained, expired 503-trade preview placed search at y719.84, Clear at 761.84, scope text at 807.84, count at 842.94 and the table at 876.03. Stacked controls left little first-view room for proposed trades.

One bounded item: group existing search, Clear and matching count immediately above the full table, keeping the scope explanation and material warnings visible. Preserve IDs, labels, native focus, bindings, full trades, table scrolling, financial math, preview identity/lifetime, authority and all workspaces. Primary owns edits and actual browser checks. No new backend, data, metrics, colors or smaller-layout work.

Installed Impeccable Operate/layout guidance and the craft floor informed implementation; primary context had already run once. Reused the qualified official [Fidelity Positions research](https://www.fidelity.com/trading/trader-desktop-user-guide/positions) recorded in the [read-first issue](2026-11-05-dogfood-spy-read-first-overview.md#independent-upstream-research): group view controls directly above tabular evidence. This is an adapted grouping principle, not broker operation or feature parity. No new critique or score.

## Implementation and independent scrutiny

Layout assessment `wf_d75351b6-3c9` inspected the real supplied capture and adjacent source. It identified the vertical control stack as the material in-scope friction. Primary's baseline and post-change scoped layout detectors returned no findings; neither empty detector output nor source review establishes rendered acceptance.

The toolbar is a wrapping flex row. Search takes remaining width; Clear and the live count align to the existing 36px control token. The unchanged view-only explanation follows, then the complete table. Existing control IDs, accessible label/descriptions, keyboard sequence, delegation and query retention remain. Removed the obsolete direct-child Clear rule. No paragraph caps or authority/financial changes.

Fresh source review `wf_c6296851-fc5` found no actionable issue at:

- `app.js`: `a05513312d8f126de53b89c039d7863900f185fa`
- `ui-orders.css`: `e1a17a1a48fdfd310b023fefa1da32101b134273`

The reviewer inspected primary and legacy SPY entries, filter/render/focus contracts, count/no-match behavior, table scroll and preview/authority predicates. It did not perform browser acceptance. Primary inspected the exact source diff and confirmed the scope remains grouping and alignment only.

## Affected real-browser evidence

Normal development URL on 8099; inspected actual viewport **1920 × 1080**. Normal source reload discarded the old session-only preview. One actual dry-run Preview generated a populated view; no preview, event, clock or account state was injected.

| Path | Actual observation |
| --- | --- |
| Populated review | 503 planned trades. Search, Clear and count aligned at y717.84–753.84, all 36px high; search about 730px wide. Count and scope explanation remained visible. Table began at y796.94 and retained its 512px bounded scroll region. No horizontal page overflow. |
| Native AAPL search | One actual AAPL BUY row, 22.316587347 shares; count **Showing 1 of 503 planned trades**. Filtering did not change the full plan. |
| Ordinary update | Stored old root became disconnected; the same search input remained connected and focused, with AAPL and 1 of 503 retained. No forced replacement/event. |
| Natural expiry | Status became **Preview expired**, Submit disabled, plan and search remained readable. Returned weights date 2026-11-04 and price-check time 5 November 2026 at 21:54:07 PST remained visible. No refresh merely for an image. |
| Keyboard Clear | Native Tab reached `spy-trade-clear`; Enter cleared the query, restored all 503 rows/count, reset table scroll 0 and returned focus to `spy-trade-query`. Expired status/disabled Submit and automatic trading off remained. |
| Native table scroll | A wheel action's immediate same-batch sample preceded wheel processing and reported 0; it is not a pass. Settled inspection showed scrollTop 500 with BRK.B/JPM/MU at the top, all 503 rows retained and main scroll 0. Both stored old root and table panel were disconnected, establishing retained table position through ordinary replacement. |

The baseline was expired while the initial new sample was current. Geometry is qualified layout evidence, not an identical-state expiry comparison, benchmark or performance claim. The final real filtered capture shows natural expiry rather than concealing it.

No approval, submission, cancel/replace, pause/resume, standing-authority change, fund save, research/model/simulation job, automated test/mock, package/build, new server, credential/private configuration read or production operation. Submit was enabled by the existing gate before expiry, never activated. Automatic trading stayed off. No-match, unavailable, blocked, empty/no-trade and alternate-entry states were source-reviewed, not newly live-exercised; prior observations are not silently promoted.

## Guide, preservation and decision

Updated the platform reference and affected operating reference. The installed reference matched its full tracked HEAD baseline after normalizing only CRLF; copied only that file and verified byte-for-byte. No installed-only change was overwritten.

Raw ignored evidence in `.local-workspace/dogfood-20261105/`:

- `spy-preview-toolbar-before-1080p.jpg`
- `spy-preview-toolbar-full-after-1080p.jpg`
- `spy-preview-toolbar-aapl-after-1080p.jpg`

Promoted the filtered capture unchanged to `docs/images/spy-rebalance-preview.jpg`: actual 1920 × 1080, Browser-rendered 800 × 450, blob `9ad8fab692e13be91acacdc78f06b2c7d70a1966`, byte-identical to raw evidence and no EXIF/XMP/IPTC/comment segment. Primary inspected visible privacy: no account identifier, credential, private note or unrelated desktop. Real quantities, dates, expiry and disabled Submit are not repainted. Updated image provenance; the existing README caption still matches, so foreign README edits remain untouched.

Application delta: **8 added/4 removed lines** across JavaScript/CSS; zero backend/test changes. JavaScript syntax and whitespace checks passed. Primary decision: accept this complete scoped toolbar batch on the independently reviewed source and observed affected paths, not full SPY release, broker execution or return parity. Commit locally on `nautilus`, no push. Preserve/exclude unrelated `README.md`, `docs/dogfood-loop.md` and deletion of `docs/issues/dogfood-loop-ledger.md`.
