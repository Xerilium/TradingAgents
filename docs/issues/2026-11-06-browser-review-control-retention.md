# Preserve review controls across ordinary updates

## Scope and reproduced failure

User-directed surgical fix on `nautilus`, baseline `8cc4605`. In the actual
8099 Browser, Markets search ref e23 accepted AAPL, then the same ref could no
longer clear it after normal updates. A new snapshot renumbered search after a
workspace-conflict warning. Native disclosures had no refs in this tool surface.
No failed consequential action was retried. The existing diagnostic conflict
page was left untouched; verification used a separate fresh page while the
operator left saved-view controls alone.

## Change

`app.js` retains original Markets search, named native disclosure summaries and
SPY review buttons only within the same page, symbol, server and store generation
and only when the freshly bound control markup is unchanged. Current values and
focus are restored; changed labels, disabled states, action identities or context
replace controls normally. Original listeners are not rebound. Native summaries
expose button refs with `aria-expanded` synchronized after render and toggle.
Polling, quote rendering, view revision/conflict protection and all broker guards
are unchanged. No framework, dependency, backend or financial-policy change.

## Actual verification

- Built-in Browser at `http://127.0.0.1:8099/#markets`, 6 November 2026,
  approximately 11:06–11:07 PST, corrected app.js loaded by normal page reload.
- The same search ref e24 remained usable through normal updated snapshots:
  AAPL produced 1 matching stock; clearing returned 503. Search retained focus.
- The same disclosure ref e22 opened and closed Snapshot and source details
  across updates. Real DOM observation confirmed focus remained on the summary
  and `aria-expanded` followed true/false. Search ended blank, disclosure closed,
  and All changes saved was observed. Batch selection remained zero.
- Snapshot advanced from 11:06:32 to 11:07:03 and later 11:07:34; polling was not
  suspended. No injected events, mocks, automated tests or research runs.
- Account15d9, policy revision1, 5% floor, automatic trading off, zero commands
  and approvals remained observed. Native session
  `c55a83b3-6fc7-4b47-8e87-595901f558a8` was not restarted.
- JavaScript syntax and Git whitespace checks passed. Fresh independent reviewer
  found missing expanded-state semantics in the initial change; correction was
  reviewed with no findings at app.js blob
  `d03dd4c49c1f423d6974e496f03d15d956d6bf05`.

## Delivery and limits

The running8099 service serves changed static JavaScript. Existing browser pages
need a normal page reload; no desk/native restart or duplicate instance is needed.
Reload discards a browser's session-only SPY preview; it does not approve or submit.
The original diagnostic workspace-conflict page remains untouched. Do not click
its discard/reload control to overwrite another operator's view.

The change is deliberately scoped, not universal DOM retention. Other workspaces,
row-level controls and dynamic semantic changes can still invalidate refs; read
fresh state before acting. Broker approval/submission/cancellation/replacement
were not exercised. The full-plan preview still does not expose/freeze every
future BUY limit; this fix does not change feed, quote quality, policy or trade scope.
