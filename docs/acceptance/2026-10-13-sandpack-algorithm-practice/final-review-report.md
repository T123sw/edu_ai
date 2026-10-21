# Final PBL integration review

Final verdict: **PASS after fixes** for specification compliance and code quality in the reviewed PBL scope. Both original Important findings are resolved; no remaining Critical or Important findings were identified.

Scope: read-only review of the PBL additions in `final-review-package.md`, current PBL sources, backend/runtime reports, progress ledger and design. Shared-file changes unrelated to PBL were excluded. Established backend 63, unit 18, hosted runtime 2, fixture GUI 3 and real-model 15-case chain results are accepted as supplied evidence; no established suites were rerun. This review does not require deployment or production migration. Root's expanded browser acceptance remains independently pending.

## Original Important findings — resolved (pre-fix line references)

### I1 — A failed conflict read permanently blocks synchronization in the mounted workspace

Evidence: `frontend/src/pbl/usePblWorkspace.ts:48–51` sets `conflictRef.current=true` after PUT returns 409, then requests the current server workspace. If that GET fails (for example connectivity drops between the conflict response and the read), only the status text changes. `conflict` remains null. Both the online handler and the visible Sync button call `flush`, which immediately returns at `usePblWorkspace.ts:20` while that ref is true. The resolving buttons exist only when `state.conflict` is non-null (`frontend/src/pbl/PblWorkspace.tsx:36`). Therefore the promised “连接恢复后重试” cannot work; the user must reload to escape the state.

Fix: represent a conflict requiring a server read explicitly and make manual/online retry fetch that server version, while continuing to prevent an unconfirmed overwrite. Render a usable retry action during that state. Do not merely clear the conflict guard and silently replace either copy.

Focused regression: PUT → 409, conflict GET → network failure, restore connectivity and invoke Sync/online; verify the server revision is fetched, resolution controls appear, and both local and remote code are preserved until the user chooses.

### I2 — Editing during report upload can leave a dirty workspace labeled saved

Evidence: `frontend/src/pbl/usePblWorkspace.ts:23–40` finishes draining workspace mutations before `:41–44` uploads reports. If the user edits while `appendRun` is pending, `change` persists a dirty local draft and starts an 800 ms timer (`:80–85`). When that timer fires while the report upload is still pending, `flush` returns because `saving.current` is true (`:20`). Once the upload resolves, the existing flush never revisits the workspace queue and unconditionally sets “已保存” (`:45`). Its finally block only clears the busy flag (`:53`). The edit consequently remains local until another edit, explicit synchronization or reload, despite the successful saved indication.

Fix: drain workspace changes and reports until both are quiescent, or schedule another drain after a successful in-flight operation when dirty work remains. Only label the workspace saved once neither a dirty/pending workspace mutation nor pending reports remain; preserve the existing immutable mutation replay behavior.

Focused regression: defer a report POST beyond 800 ms, edit code while it is pending, advance the debounce, then resolve the report. Assert a workspace PUT follows with the new code and “已保存” is not displayed before that PUT succeeds.

## Reviewed boundaries without new blocking findings

- Owner predicates protect exercise/workspace/run reads and writes; public artifacts enumerate fields and exclude referenceSolution/private checkpoints. Job lookup verifies owner and PBL kind, and generation errors expose safe messages.
- PostgreSQL workspace mutation uses conditional SQL revision/version update, refreshes after concurrency, and supports exact most-recent mutation replay. Run records are immutable/idempotent, hashes are recomputed, and browser-reported evidence remains explicit.
- Generation mutations lock/check durable lease identity, attempt, expiry/deadline, cancellation and owner in the PostgreSQL transaction. Retry claims conditionally replace only the expected current job; published artifacts remain immutable. Runtime injects context and old same-job attempts are fenced.
- Private candidates/checkpoints and bounded repairs survive restart; validated results are template checked, browser environment failures retain candidates, and publication is followed by readback.
- Fixed runtime sources serve native validation and hosted Sandpack. The earlier forged message, executable destructuring and reconnect callback findings are repaired. Host run ID/hash, runtime session and full-case current-report gates keep old results from being attributed to a new run/code version.
- PBL route checks precede generic practice routes; the mode switch retains the existing simulation route; the PBL job result route precedes course/material requirements. No PBL change was found replacing old simulation artifacts.

Code quality: the new modules are small and boundaries are explicit. The revised synchronization loop now models the conflict read/choice substates and drains both queues together, addressing the original observable recovery defects.


## Scoped fix re-review

Reviewed current `usePblWorkspace.ts`, the added regressions in `frontend/tests/live-learning/pbl.spec.ts`, and `save-fix-report.md`. No source edits or test-suite reruns. The fix agent reports six focused browser checks passing, including existing delayed-save/offline cases and the four new regressions; focused lint and TypeScript checks also pass. These are supplied verification results, not independently rerun results.

- **I1 resolved:** `usePblWorkspace.ts:13,19–34,64–66` separates `needs_read` from `awaiting_choice`. A failed conflict GET retains write protection while the manual Sync and online paths can retry the read. A successful read reveals the existing choice controls. `:108–116` retains the other code copy as backup and only resumes writes after a choice. The manual/online regressions at `pbl.spec.ts:141–172` assert no additional PUT before a choice and verify backup recovery afterward.
- **I2 resolved:** `usePblWorkspace.ts:35–60` uses a combined drain condition and revisits it after each report upload and workspace save. New edits during a pending POST therefore receive a subsequent PUT even if debounce fired while busy. The saved indication at `:61` follows queue exhaustion. The gated regression at `pbl.spec.ts:174–206` holds the report past debounce, then separately holds the subsequent PUT and asserts that saved is not displayed prematurely.
- **Adjacent concurrency checked:** serial request guarding remains intact; an uncertain `pendingPatch` is reused before creating a new mutation, acknowledgement only advances revision while preserving current files/input/task, pending reports are shifted only after success, and errors leave queued work available for retry. The regression at `pbl.spec.ts:208–239` asserts byte-equivalent replay payload, a fresh mutation at the acknowledged revision for newer edits, and preservation of the newer editor value. No new blocking adjacent concurrency regression was found in this scoped review.

The original whole-feature boundary assessment above remains unchanged. Production deployment is outside this handoff review; root owns the final build and broader acceptance record.
