# Runtime/contracts review

Scope: Tasks 1–2 and the delivered runtime/source-validation portion of Task 3, using runtime-contract-review.md plus the task briefs, Task 1 report and current source. Root's unfinished backend validation and production workspace are excluded. No source edits or existing suite reruns. The supplied hosted 2/2, runtime unit 2/2, Python contract 11/11 and TypeScript contract 3/3 evidence is accepted as reported.

**Specification verdict: PASS after fixes.** The three original findings below are resolved in the reviewed source.

**Code quality verdict: PASS after fixes.** No blocking findings remain in this bounded runtime/contracts re-review.

## Original findings — resolved

### P1 — Student `postMessage` can manufacture a passing verdict

Location: `frontend/src/pbl/runtime/runner.js:59–62`; related `sourceValidation.ts:4`, `worker-source.js:14–16`.

`export function quickSort(a){postMessage({passed:true});return [];}` passes `validateSource` with `{ok:true,issues:[]}`. A targeted real Chromium run of the current shared `createExecution` with input `[3,1,2]` and expected `[1,2,3]` returned `status:"passed"`, with a case containing `passed:true,status:"passed"` and no actual array. The first worker message wins; the evaluator's later failure is ignored. This is an ordinary exposed Worker global, without devtools or host-page tampering, so the browser_reported disclaimer does not explain the false result. Arbitrary spread of worker fields also bypasses the stated output bounds and authoritative case identity.

Fix: make evaluator completion distinguishable from direct student messages (capture native send and use a private per-case completion identity/channel), reject unsupported unbound globals including postMessage in the supported source subset, and validate/whitelist bounded result fields before merging them. Keep caseId/expected authoritative from the requested case. Add one negative reproduction proving invalid algorithm output cannot win by posting its own verdict. This recommendation does not require claiming a fully adversarial JavaScript sandbox.

### P2 — Top-level destructuring can execute code despite the declaration gate

Location: `frontend/src/pbl/runtime/sourceValidation.ts:20–23`.

The top-level gate validates the initializer's node type but not the binding pattern. `const {x = postMessage({passed:true})} = 1; export function quickSort(a){return [];}` also returns `{ok:true,issues:[]}`. A default initializer in a destructuring binding runs during module evaluation even though the outer initializer is a Literal. Replacing postMessage with any function call retains the semantic problem. Task 3 explicitly rejects top-level execution; rejecting only ExpressionStatement and nonliteral declaration initializers does not enforce it.

Fix: restrict top-level variable declarator identifiers to simple Identifier nodes (or explicitly inspect all binding defaults/computed keys for evaluation), and require the intended declaration kind. Reject executable binding patterns before creating a Worker. A scope-aware supported-global policy would also be clearer than extending the current denylist indefinitely; computed constructor access currently bypasses the property-name check, though this review does not require a complete malicious-code isolation guarantee.

### P2 — Reconnecting a running preview relabels the old completion with the new session

Location: `frontend/src/pbl/runtime/index.js:29`, `:33`, `:40–41`, `:52–56` (current source after root's result-card update; equivalent original lines 10,14,21–22,32–36).

`close()` stops an execution but leaves activeRun unchanged. A new connect immediately assigns the new global port/sessionId. The canceled execution resolves asynchronously: its onCase callback calls the global send helper, then its awaited continuation passes the activeRun-only check. Both events are now transmitted over the new port with the new sessionId. Thus a replaced session can receive a previous session's case-result/run-finished, contrary to the specified old-session invalidation. Host runId checks may suppress some effects, but the runtime should not relabel stale events as current.

Fix: invalidate activeRun/session generation before stopping; capture the current session and execution identity for each run; guard both onCase and the final continuation against that identity. Do not send through a newly assigned port from an older callback. Cover a connect/run/reconnect sequence while execution is active.

## Reviewed strengths and limits

- Host handshake validates the exact preview window and fixed bundler origin before transferring a dedicated port. The actual direct iframe topology has supplied hosted evidence.
- Explicit snapshots run in one Worker per case; stop prevents additional cases, and timers/Workers/outer Blob URLs are cleaned on settlement. The fixed shell does not import algorithm.js.
- Reports preserve exercise/artifact/template/task/hash identity; full-check matching rejects sample, missing/duplicate cases and nonpassed cases.
- Publication enumerates public fields and drops referenceSolution/private validation details; normalization verifies numeric expected values and adds all nine baseline categories. Python and TS use matching ordinary UTF-8 JSON code-hash representations, backed by the supplied shared-fixture evidence.
- No missing Task 4+ feature is counted as a defect. No new hosted-bundler claim is made: the only fresh browser action was a focused local-origin Chromium Worker reproduction of P1 using the existing source.


## Fix re-review

Reviewed the updated runner.js, worker-source.js, sourceValidation.ts and index.js; no source edits, full test-suite reruns or expansion into unfinished backend/UI scope.

- P1 resolved: the Worker captures native send, disables direct postMessage, and attaches a private per-case token checked by the runner. Unsupported message globals are rejected statically. A fresh targeted Chromium Worker reproduction bypassing AST now reports failed/OUTPUT_MISMATCH for the original forged-postMessage source. Final runner code whitelists public fields and does not expose completionToken or the internal passed boolean.
- Top-level declaration P2 resolved: non-Identifier binding patterns are rejected. A focused AST call for a destructuring default that invokes an arrow function returned ok:false/UNSUPPORTED_SOURCE, independent of the postMessage denylist.
- Session P2 resolved: callbacks capture connection port/session and guard both incremental and final messages; old continuations cannot use the new channel. close() now also resets busy(false) and activeRun before stopping, avoiding disabled preview controls after reconnect.
- Root reports five combined unit checks and native validation passing, followed by a real-model production exercise with 15 cases and persisted failed/passed reports. Those broader results are supplied evidence, not rerun by this reviewer.

The short-lived concern that completionToken would directly break persistence was corrected after confirming the existing host already projected allowed fields; final runner whitelisting removes the internal-field leak at its source. No remaining blocking regression was found. The static syntax check remains a supported-subset filter rather than a complete adversarial JavaScript sandbox, consistent with the design.
