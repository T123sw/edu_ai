# Backend integration report

Implemented Tasks 5–7 backend scope in the existing dirty feature branch. No commits, resets, production migrations, or production data writes. Unrelated changes preserved.

## Delivered

- Three SQLAlchemy tables and Alembic `20261013_0038` following inspected `20261013_0037`; metadata registration avoids circular imports. Exercise records separate private candidate/checkpoint/validation from public artifact. Final Alembic script-directory inspection reports the sole head `20261013_0038`.
- Authenticated `/api/pbl` create/list/detail, workspace GET/PUT, and immutable run POST/list, with the requested camelCase wire schemas. Cross-owner PBL operations return 404; unsupported topics and malformed reports return 422; unready workspaces and revision/version/idempotency conflicts return 409. Lists expose `nextCursor`.
- Stable owner/request-based exercise and initial job IDs; same request with changed topic conflicts. PostgreSQL exercise row lock serializes cross-store job creation and enqueue reconciliation. Missing durable queue records recover using the same IDs; existing durable tasks are reused. Failed enqueue recovery has a narrow job-store function restricted to `GENERATE_PBL`, failed status, and `TASK_ENQUEUE_FAILED`, retaining general terminal-job protections.
- Workspace updates use a conditional SQL UPDATE against owner/exercise/artifact version/expected revision, then increment revision. Last mutation payload and ID permit exact latest-request retransmission; changed payload or old revision conflicts. Initial GET creates only once.
- Browser runs recompute the canonical source hash, retain immutable source/cases/results, validate artifact/template and case/result consistency, require complete valid results for a passed report, and always retain `browser_reported` evidence source. Same run ID/body is idempotent, different body conflicts. Reports do not require changing current editor state.
- `GENERATE_PBL`, API router, and version-1 `pbl_generate` durable handler registered. Generation uses the existing bounded adapter's configured gateway and immutable runtime-config resolver snapshot, with a complete structured JSON schema and fixed quicksort contract; no MAIC dependency.
- Persistent candidate/checkpoint stages and repair count, including invalid raw JSON for model repair. Trusted normalization fills baseline cases and rejects wrong expected values. Material failures allow at most two targeted repairs. Environment failures preserve the candidate without spending repair budget. A validated checkpoint matching the runtime template can publish without another model or browser call.
- Publication whitelist excludes referenceSolution. Private browser/source/provider errors never become public PBL error messages; job logs contain stage/model identifiers and safe errors. Readback precedes `saved=true` result delivery.
- Optional durable context `lease_owner`, `attempt_count`, and `is_lease_valid` fields preserve existing handler construction. PBL checks cancellation/lease around long operations. PostgreSQL checkpoint/claim/publish locks and checks the durable task row in the mutation transaction (owner, leased status, attempt, worker, expiry, deadline, cancellation). SQLite tests inject the lease guard.
- Retry claims atomically replace `current_job_id` only from the actual public job's `retry_of_job_id`; simultaneous retry claims yield one winner. Published artifacts are immutable. Expired same-job attempts cannot checkpoint/publish/fail a newer attempt; a valid but superseded retry is explicitly failed. Cancel requests during generation finish as canceled rather than failed.

## Verification

All Python checks ran through `scripts/pbl/isolated.py`, which disables production dotenv override and isolates storage. PostgreSQL tests explicitly target `edu_pbl_acceptance_20261013` on port 55439 and create/drop their own random `pbl_test_*` schemas; they do not clear the database.

Final consolidated result: **63 passed in 59.83s**, no skipped tests. Command:

```sh
PBL_TEST_DATABASE_URL=postgresql+psycopg://zxqs_ep@127.0.0.1:55439/edu_pbl_acceptance_20261013 \
PATH=/home/zxqs_ep/miniforge3/envs/edu-ai/bin:$PATH \
python scripts/pbl/isolated.py pytest \
  backend/src/tests/pbl \
  backend/src/tests/test_durable_task_executor.py \
  backend/src/tests/test_job_retry_service.py -q
```

The suite includes:

- SQLite request/owner isolation, CAS/revision/version/latest-mutation behavior, immutable run/hash/case validation, retry claims, and private-public separation.
- API status/wire shape tests, all cross-owner routes, real enqueue failure recovery, and lost acknowledgment with an already-existing durable task.
- Structured generator invalid JSON/wrong expected payload preservation and snapshot resolution; bounded repairs, environment failure, model timeout, cancellation, checkpoint recovery and template invalidation.
- Actual TaskStore + DurableTaskExecutor + generic job retry integration: failed model → new retry job → same exercise ready; cancellation during model; superseded retry fails without overwriting winner.
- Actual native Playwright browser validator: valid reference/starter passes, wrong reference fails, and starter containing the implementation fails.
- Actual PostgreSQL concurrent independent transactions: same workspace revision has exactly one winner; concurrent retries have exactly one owner; same-job old worker/attempt, cancellation, and expiry reject mutations. Migration 0038 upgrade/downgrade/re-upgrade executes only inside its isolated schema.
- Existing durable executor/retry regression tests.

Earlier checks: repository 13 passed; API initial 4 passed; generation/recovery initial 12 passed; independent PostgreSQL 4 passed; existing executor/retry 11 passed; real browser/generator combined 12 passed. Final enqueue recovery regression exposed the generic terminal transition guard; the narrow recovery function fixed it, and the subsequent API/executor/retry focused check passed all 17 tests.

## Handoff and limits

Root owns the real model + full-app PostgreSQL + hosted Sandpack E2E. Root reported that complete chain passed (15 cases, wrong implementation fails, corrected implementation passes, edit invalidates old report, refresh restores, recheck succeeds); backend agent did not duplicate model calls or substitute fixtures for model evidence. Root's acceptance artifacts are the source for that evidence.

Production PBL fencing expects PostgreSQL PBL tables and durable_tasks in the same database, as configured by the isolated full-app server. Mixed PostgreSQL PBL storage with a SQLite durable queue is intentionally rejected by the transaction guard.

HTTP model cancellation is polled while awaiting and closes its coroutine. Browser validation runs through the existing `asyncio.to_thread` subprocess wrapper; cancellation prevents publication, while that browser subprocess remains bounded by its own 75-second timeout rather than being force-killed by the cancellation signal.

Public state is updated to a new retry job when its handler successfully claims the exercise. Material repair budget is persisted across durable recovery/retry, rather than silently reset per attempt.
