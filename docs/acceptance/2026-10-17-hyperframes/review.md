# HyperFrames final migration review

Read-only implementation review against snapshot baseline `617cbe13`, including the working-tree changes. This report was written before the root agent's final fixes; the findings below were sent immediately and the root agent is addressing them. No vendor tree diff, full-suite rerun, production data mutation, or live deployment was performed.

## Findings requiring resolution

### P1 — Concurrent narration jobs share an asyncio lock across different event loops

`backend/src/app/integrations/hyperframes/generation.py:72–76` invokes `asyncio.run(narration_audio(...))` from synchronous generation workers. `backend/src/app/services/classroom_narration.py:15,37–38` shares cache locks globally by destination, but the locks are `asyncio.Lock` instances. Identical narration requested by concurrent worker threads therefore uses the same lock from separate event loops.

Independent reproduction with three daemon threads, an async fake TTS provider and the same narration/cache key produced `RuntimeError: <asyncio.locks.Lock ...> is bound to a different event loop` in the third thread. After the first synthesis completed, the second waiter remained alive/hung (`[False, True, False]`). This can strand durable generation workers, not merely duplicate a TTS call. Use cross-loop-safe serialization or safe atomic concurrent publication, and cover concurrent identical requests.

### P1 — Empty metadata changes ordinary classroom visibility from private to course-wide

`backend/src/app/services/hyperframes_classroom.py:50–52` passes `visibility='course'` whenever `harness_config` is absent. With empty metadata this condition is true. The replaced persistence code (`classroom_persistence.py:90–99`) explicitly requires nonempty `material_metadata` before applying that sharing rule; otherwise storage defaults owned material to private. Ordinary Studio requests have only `_tts_options`, which is removed before persistence, leaving `{}`. The new path therefore automatically shares a user's generated material with all course members. Restore the existing explicit sharing semantics and verify empty metadata/private, standard/shared and Harness/private cases.

### P2 — Native question context can fail on a valid longer lesson because adjacent prose is unbounded

`backend/src/app/self_learning/hyperframes_context.py:26–35` includes complete current, previous and next narration plus the whole directory. The native branch in `resource_reader.excerpt` ignores `max_chars`, and `context_builder.py:85–89,118–125` replaces the excerpt with full classroom JSON, skips shrinking and raises `CONTEXT_BUDGET_EXCEEDED` at 24KB. Three multi-minute Chinese segments can exceed that budget before question/history overhead, although each current segment alone would fit. Bound adjacent context/directory first, preserve exact current position and current narration, and mark omitted context explicitly. Do not impose an arbitrary generation-length cap.

### P2 — Alternate generation path silently drops requested source inputs and selected visuals

`backend/src/app/services/hyperframes_classroom.py:33–43` does not consume `command.pdf_content` or `include_visuals`. `PlatformTaskHandlers.classroom_generate` removed its former `_plan_classroom_visuals` call; frontend generation still sends `include_visuals=true` by default. Previously supplied PDF content reached generation, selected real visuals entered research context, and their provenance entered `source_snapshot`. Native multi-file capability is retained upstream, but the platform adapter currently accepts generated text and narration without packaging these requested real assets. Preserve supplied PDF text and package authorized local selected assets with provenance, or explicitly remove unsupported input promises.

## Reviewed boundaries and evidence

- Exact-version playback tickets bind owner, course/material/version and project digest. File requests recheck current authorization, enforce capability audience/expiry, verify the manifest and bytes, and reject path traversal/symlinks. Scoped sandbox CSP replaces broad same-origin access; final browser CSP evidence remains the frontend agent's responsibility.
- Native rendering uses mandatory bubblewrap namespaces and an environment allowlist; no host networking or model/API secrets are handed to generated JavaScript. Upstream source remains unchanged. Production installation/activation is a separate operational step.
- Native semantic context distinguishes authored visual descriptions from observed screenshots, handles `[start,end)` intervals/gaps/final endpoint, and retains exact version/time locators. Accepted-turn snapshot integration was being completed by the root agent during this review.
- Native draft and immediate revision paths regenerate synchronized audio/project/timeline and pass the revision service as cancellation context. No independent semantic LLM review was introduced.
- Frontend uses the actual native player with opaque iframe, locally served runtime, real audio fallback, seek/rate controls and time locators. The temporary unmatched `</details>` in an in-flight ClassroomForm edit was reported separately for the frontend agent's final build; it is not treated here as a settled implementation finding.
- Full vendor preservation, native CLI/player pins and direct project exports were inspected without expanding the enormous vendor diff.

Independent bounded verification: `PYTHONPATH=backend/src DATABASE_URL='' COURSE_STORAGE_ROOT=/tmp/edu-hf-final-review HYPERFRAMES_BWRAP_PATH=/tmp/edu-hf-bwrap/usr/bin/bwrap python -m pytest backend/src/tests/hyperframes -q` completed **33 passed** in 2.63 seconds, with only the existing auth datetime deprecation warnings. The cross-event-loop narration reproduction above was a separate independent check and exposes a gap in that passing suite.

## Post-fix re-review

The root agent addressed all four findings above:

- Narration now uses a registry-protected thread lock, acquired asynchronously without blocking each worker's event loop, and releases in `finally`. The three-worker regression passes and proves one synthesis/cache artifact per process.
- Empty metadata again takes storage's private default; explicit standard resources stay shared and Harness resources stay private. All three visibility cases are tested.
- Native context drops adjacent prose and then bounds the directory when needed; exact position and full current narration remain intact. The long-neighbor regression fits the default 24KB budget and preserves current content.
- PDF content reaches the native request; optional selected assets are resolved through existing local asset authorization, passed as trusted bytes under `assets/media/`, included in immutable project/ZIP, and retained in source provenance. Unsupported/local-file/remote sources are not fetched as arbitrary files.

Also reviewed the root agent's additional hash fix: citation `content_hash` now uses the same canonical material-body digest as `LearningAgentRuntime`'s final `SOURCE_CHANGED` check, while the time locator's `content_hash` remains the project digest. This distinction is necessary and correct. The real 36.432-second artifact's accepted question at 25 seconds now succeeds against its original version even after a newer material version is saved.

Independent post-fix verification: native tests, `test_classroom_narration.py` and `self_learning/test_classroom_context.py`, with the same isolated environment and `--import-mode=importlib`, completed **55 passed, 3 skipped** in 13.07 seconds. The skips are PostgreSQL variants requiring an external test database; SQLite-backed accepted-turn tests ran. Existing auth datetime deprecations remain the only warnings.

One additional P2 was reported during this re-review: `artifact_revision/hyperframes.py` excludes the whole `assets/` tree from `original_files`, while its binary preservation only handles `assets/media/`. Authored native text assets such as `assets/diagram.svg`, `assets/custom.js` or CSS therefore disappear from the revision model's source context despite references in the preserved HTML. Exclude only known injected runtime bundles/narration/exports, and preserve other authored text assets. This report awaits that narrow follow-up fix before a final clean conclusion.

## Final delta re-review

The authored-asset revision issue is resolved: only supplied media, exports and the two injected runtime bundles are omitted from `original_files`; authored SVG/JS/CSS/JSON under `assets/` are retained. A focused regression verifies SVG and JS source, supplied image bytes and cancellation context.

Reviewed the deployment correction against the vendored browser manager: native `hyperframes browser ensure` uses the HyperFrames/Puppeteer caches now mounted read-only by bubblewrap; the already-cached path returns before the install lock/download path. Preflight checks the pinned packages, browser, bubblewrap, Node and FFmpeg dependencies. Reviewed classroom QA's `httpx.HTTPError` fallback and its real `ReadTimeout` regression: answer text remains available when audio fails.

The additional report-context fix reclaims optional tool-result reserve after `CONTEXT_BUDGET_EXCEEDED`, retaining mounted-schema accounting and the unchanged complete-payload limit. Initial long-selection regression passes. One narrow P2 follow-up was reported: the effective expanded budget is local, not checkpointed; a resumed packet followed by a successful `update_learning_preference` rebuild still calls `builder.build` with the original smaller budget. Apply the same reserve fallback to that rebuild (or persist the effective budget) so durable recovery does not reintroduce the same accepted-selection failure.

Independent final-delta verification: authored-asset/job tests, sandbox tests, `test_context_budget.py` and classroom QA service tests completed **26 passed, 2 skipped** in 21.66 seconds. The skips are PostgreSQL variants. No full-suite or native render repetition was performed.

## Final conclusion — review closed

The final durable-resume budget finding is resolved by one `build_context()` helper used for both initial assembly and preference-driven rebuilds. It applies the same bounded reserve fallback after a checkpoint is reclaimed without changing the total payload limit.

Independently ran the new `test_resumed_long_selection_rebuild_after_preference_write`: **1 passed, 1 PostgreSQL variant skipped, 4 deselected** in 13.08 seconds. The test saves a real checkpoint with a pending preference write, expires/reclaims its lease, executes the write, rebuilds with a 10,000-character selection and verifies successful completion plus preservation of the selection and preference. Also inspected the root agent's final combined log: **93 passed, 6 PostgreSQL skips**, with existing auth datetime warnings only.

All P1/P2 findings raised in this review are now addressed; no unresolved blocker was found in the reviewed migration delta. This is source and bounded-test acceptance, not a claim of production deployment, a full independent suite, or an independently repeated model/TTS/browser end-to-end run. Original workspace integration, dependency activation and deployment remain the root agent's responsibility.
