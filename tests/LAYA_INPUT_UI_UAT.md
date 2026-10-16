# Exact Laya input UI UAT — repaired browser verification PASS

## Final browser recheck, 2026-10-15

PASS using the isolated fixture at port 18765 with the saved exact audit and current app assets. Selected META with the mouse: all sections initially collapsed. Explicitly opened Laya: readable six-field summary, multilingual model, 8192 effective/model caps, 256 reserved tokens, one summary attempt, and per-question counts 2673 / 2677. No `[object Object]` appeared. Scrolled inside the selected-stock panel and opened the full raw artifact; complete questions, hashes, token audit and final summary-attempt field remained accessible.

The panel height stayed 369.5px and Run activity top stayed 781.1875px before expansion, after Laya expansion, and after raw expansion. Receipt: `.paper-desk/laya-preview-browser-receipt.json`. Screenshot: [Repaired preview](../.impeccable/review/laya-preview-repaired.png).

No provider inference, research batch, orders or live journal modifications were performed for this fixture check. Separately, one live Connect paper account action restored paper verification and all seven Market closed quote labels.

The sections below preserve the historical failed attempt; their pending verdict is superseded by this recheck.

## Re-UAT attempt after repair

The renderer now uses `reportLayaReview` for structured summary and token metadata. This source observation is **not** a browser PASS. The fresh isolated IAB tab could not be created because IAB was unavailable. Parent then reported an explicit browser security denial and instructed no alternate surface or workaround. No Edge fallback was attempted. Fixture stopped; no test tab was created, no viewport changed. Final reviewer notified. Repaired-render browser acceptance remains pending.

The original observed failure and passed subchecks below remain historical evidence; they do not describe the repaired rendering.

Date: 2026-10-15. Actual app.js, lists.js and app.css in isolated local fixture.
Input: `.paper-desk/laya-saved-packet-review.json`, exact `audit` object exposed as `laya_review`, original source reports alongside it. Original journal unchanged. No providers, research, broker or live backend calls.

## Blocking defect

1. Run `rtk proxy .venv/Scripts/python.exe .paper-desk/run-bounded.py --seconds 600 -- .venv/Scripts/python.exe tests/laya_input_browser_fixture.py`.
2. Open `http://127.0.0.1:18765/#research` in a separate test tab.
3. Select META; every report starts collapsed.
4. Click Laya review.
5. **Review input shows `[object Object]`; Token budget shows `[object Object]`.**

`renderReportArtifact` calls `reportMarkdown` on the structured summary and `esc` on the token-budget object. The nested structured record below renders correctly, so this is presentation, not missing persisted data.

Evidence: [Screenshot](../.impeccable/review/laya-real-input-uat-defect.jpg).

## Checks passed

- Initial open details count 0; Laya opened only after mouse action.
- Nested structured summary shows recommendation Overweight, support, counterarguments, unresolved gaps, execution conditions and source references.
- Model multilingual; full-question token counts 2673 / 2677; effective maximum 8192; reserve 256, summary attempts 1.
- Full source artifact starts collapsed, opens by mouse, includes complete audit JSON ending in reserve and summary-attempt fields.
- Selected-stock scroll region height 369.5px and Run activity document top 781.1875px stayed identical before expansion, after Laya expansion, and after raw source expansion. Browser default viewport used; no viewport override.

Not a live research run and not proof of live journal integration. Acceptance remains blocked on readable summary/budget rendering; repeat this fixture after a fix.
