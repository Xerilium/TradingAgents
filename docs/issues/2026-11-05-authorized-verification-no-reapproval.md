# Remove redundant approval gates from authorized local work

## Human correction

On 5 November 2026, the human asked what caused the repeated blocking prompt,
then instructed deletion of the bad rule and a ban on the prompting tool.

The cause was `AGENTS.md`'s rule that an authorized check meant one round and a
failure required fresh authorization. Primary copied that restriction into the
SPY disclosure issue and recurring wakeup prompt. The actual approval widget was
`mcp__ccd_turn__wrap_up` with `ask`/`actions`; no missing tool permission or technical
block required it. `AskUserQuestion` was not used for that prompt.

## Correction

- Remove the failed-local-check reapproval rule. Authorized development includes
  diagnosing, correcting and rechecking affected failures without another prompt.
- Ban `AskUserQuestion` in this checkout and ban app wrap-up approval questions for
  already-authorized development, navigation, static checks and local verification.
  The app's required status recap remains recap-only for that work.
- Remove the human-approval hold from the open SPY item and future wakeups. Preserve
  its failed evidence: the corrected focus behavior is still unverified until the
  affected real check runs; removing a gate is not a pass.
- Preserve broker, credential, destructive-action and new-scope boundaries. No paper
  trade, order approval, submission, cancel/replace or standing-authority change is
  authorized. Existing automated-test and mock restrictions remain unchanged.

Update the canonical brief and tracked operating skill, synchronize only affected
installed skill files after comparing them, independently review scope and commit
locally on `nautilus`. No app check or provider job is started merely because this
operating-rule correction removes the gate; finish this documentation task first.

## Evidence and delivery

Fresh read-only review `wf_3b392f34-b13` against baseline `7cc91e8` found no
actionable contradiction or scope error. It confirmed truthful attribution to
wrap-up question/buttons, preservation of failed evidence and separate boundaries.
Reviewed blobs: AGENTS `9bf20474c9cb239699800bc3139485d84b646dc4`, loop brief
`3cdcdb8b9a3cc109bf9a8f668d536c2d515bce0f`, operating skill
`f5d124479629bcad380bb0b3334cd9f91f1b4563`, current SPY issue
`9a8c8c805b28362db793e23fe3e67e92fc41ccca`.

Primary accepts this operating-rule correction. The changed source/installed skill
matches byte-for-byte; other installed files were untouched. Whitespace checks
passed. Durable correction:
`memory://knowledge/projects/tradingagents/tradingagents-authorized-local-verification-does-not-need-reapproval`.

This changes instructions/documentation only, not application code or tests. No
app check, research/provider job, broker action, credential read, build or production
operation occurred. It supersedes the earlier reapproval restriction; historical
failed checks remain failed evidence, not current approval requirements. The
wakeup prompt is replaced with the corrected rule before this turn ends.
