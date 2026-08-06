# Course-Centered Teacher Experience Execution Log

**Spec:** `docs/superpowers/specs/2026-08-06-course-centered-teacher-experience-design.md`
**Plans:** `docs/superpowers/plans/README.md`
**Started:** 2026-08-07 (Asia/Shanghai)
**Execution mode:** Superpowers `executing-plans`, inline execution, test-driven development

## Recording Rules

Each entry records a decision made without pausing for confirmation, the recommended choice taken, its reason, affected scope, verification evidence, and commit when available. Data-destructive choices are not auto-approved.

## Decisions

### D001 — Isolate implementation from the dirty main checkout

- **Context:** The main checkout contains unrelated modified Agent/RAG source files, tests, course data, runtime data, and frontend chat files.
- **Choice:** Commit only the approved Spec/plan/log documents, then create `feat/course-centered-teacher-ux` in an isolated worktree for implementation.
- **Reason:** This prevents unrelated user changes from entering phase commits and satisfies the Superpowers worktree requirement without discarding any current work.
- **Impact:** Implementation commands and commits run in the isolated worktree. The original checkout remains available with its unrelated changes untouched.
- **Evidence:** Plan/Spec commit `1e1e6b8`; linked worktree `D:\github\edu_ai\.worktrees\course-centered-teacher-ux`; branch `feat/course-centered-teacher-ux`; original dirty checkout remains separate.
- **Status:** Applied.

### D002 — Build ignored local OpenMAIC packages in the isolated workspace

- **Context:** A clean dependency install links `mathml2omml`, `pptxgenjs`, `@openmaic/dsl`, and `@openmaic/renderer` from source. Their ignored `dist/` directories are absent in a fresh worktree, so tests/build cannot resolve package exports. The sidecar postinstall also uses Unix `rm`, which fails in Windows PowerShell/cmd.
- **Choice:** Restore the locked sidecar workspace, build the two vendored packages, then build DSL and renderer with their underlying cross-platform TypeScript/Rollup commands. Keep all generated `dist/` and nested dependency folders ignored and outside commits.
- **Reason:** This restores the repository’s intended local-package runtime without altering product source or inventing a different dependency graph.
- **Impact:** Frontend tests and build can run in the isolated worktree. No generated package output is staged.
- **Status:** Applied.

### D003 — Treat system administrators as development editors, not course owners

- **Context:** Development auto-enrollment needs a course role for existing `admin` accounts, while course ownership must remain an explicit creator/audit concept.
- **Choice:** Auto-enroll both `teacher` and `admin` system roles as course `editor`; enroll all other roles as `viewer`. Never overwrite an existing `owner` membership.
- **Reason:** Administrators can exercise teacher workflows during small-scale development without silently becoming the business owner of every course.
- **Impact:** Member-management and course-deletion capabilities still require an explicit owner membership.
- **Status:** Applied.

## Phase Evidence

### Baseline — 2026-08-07

- Frontend unit/contract tests: **137 passed, 0 failed** after local-package build.
- Frontend production build: **passed**; existing chunk-size warnings remain (largest application chunk approximately 3.19 MB).
- Frontend lint: **0 errors, 82 warnings**. Warnings are recorded as the pre-change baseline and must not increase; stage 6 will address in-scope warnings.
- Focused backend baseline: **25 passed, 1 failed**. The failure is `test_get_course_materials_returns_paginated_aggregate_scope` (`total` expected 25, got 0), caused by the current creator/owner visibility filter. This is an explicit Plan 1 Task 5 target, not an environmental failure.
- Worktree source status after dependency setup: clean before the log update.

### Plan 1 / Task 1 — Atomic course membership store

- Red evidence: `tests/test_course_membership_store.py` failed collection with `ModuleNotFoundError` before production code existed.
- Green evidence: `3 passed` using the isolated `edu-ai` Python environment.
- Result: versioned membership JSON, unique upsert, deterministic queries, idempotent delete, and same-directory atomic replacement are implemented.

### Plan 1 / Task 2 — Capability authorization boundary

- Red evidence: access-service and HTTP-adapter tests each failed with the expected missing-module error before their implementation.
- Green evidence: `16 passed` across membership storage, the full role/capability matrix, missing membership, and stable HTTP 403 mapping.
- Result: backend roles now resolve to explicit `read`, `edit`, `generate`, resource-management, member-management, and course-deletion capabilities through one service.

### Plan 1 / Task 3 — Development membership bootstrap and migration

- Red evidence: bootstrap and migration imports failed before implementation; lifespan rejected the membership factory; registration lacked the enrollment hook.
- Green evidence: `10 passed` across sync/idempotency/disabled mode, dry-run/apply migration, startup ordering, runtime lifecycle, and registration enrollment.
- CLI evidence: `python -m scripts.migrate_course_memberships --dry-run` completed with `applied=false` and no membership writes.
- Result: defaults exist before membership backfill, membership sync completes before durable workers start, and new users are enrolled immediately.

### Plan 1 / Task 4 — Authenticated, revision-safe course CRUD

- Red evidence: anonymous course listing returned 200, legacy responses lacked revision, stale writes were accepted, viewer writes were unguarded, and new courses created no memberships.
- Green evidence: `4 passed` for authenticated membership-filtered listing, 409 compare-and-swap behavior, viewer denial, and owner/development membership creation; combined course/lifespan run had `17 passed` plus the already-recorded material-visibility failure assigned to Task 5.
- Result: legacy course files normalize to revision 0; updates are atomic under the course storage lock; course responses include audit/membership fields; public registration/auth dependencies now return 401 when credentials are absent.

### Plan 1 / Task 5 — Course-shared generated materials

- Red evidence: materials created by teacher A were filtered out for teacher B, legacy manifests had no explicit visibility metadata, and viewer mutation routes did not consistently use course capabilities.
- Green evidence: `38 passed` across material permissions/manifests, course CRUD integration, course-scoped chat routes, job completion, and job reconciliation.
- Decision: generated materials default to `course` visibility and record `created_by`; `private` remains available for creator-only artifacts. Legacy manifests normalize to course visibility for compatibility.
- Decision: durable job completion and reconciliation stay creator-scoped even though completed course artifacts are shared. This prevents one teacher's worker task from being satisfied by another teacher's artifact.
- Result: all course members can read course-visible artifacts, editors/owners can manage them, viewers receive 403 for mutations, and task ownership semantics remain intact.

### Plan 1 / Task 6 — Course-wide route authorization

- Red evidence: the new authorization suite produced five viewer-write failures: knowledge-graph save and classroom generation succeeded, while graph allocation and knowledge-document mutations reached resource-level 404 responses instead of failing at the course boundary.
- Green evidence: `67 passed` across the authorization matrix, course scopes, textbook graph import, graph-hour allocation, classroom services/jobs, and material permissions.
- Decision: read-only retrieval testing remains a `read` capability even though it uses POST; indexing/reindexing, textbook graph import, graph-hour allocation, classroom generation, and video export require `generate`; knowledge-base and graph content mutation require `edit`.
- Decision: classroom-video export reconstructs the already-authorized principal context and no longer references undeclared request credential variables. The queued export implementation does not consume the raw token.
- Result: every course-scoped content route now enters through a single read/edit/generate/manage/owner capability boundary with stable 401/403 behavior.

### Plan 1 / Task 7 — URL-derived frontend course context

- Red evidence: the focused Node run failed on the missing route provider and permission modules; the previous App implementation restored a local course first and later overwrote it asynchronously from the URL.
- Green evidence: `8 passed` across route authority, malformed IDs, the permission matrix, and existing teacher-route contracts; the production Vite build passed.
- Decision: a remembered course is consulted only on `#home`. Course detail/workspace routes without `course_id` have no active course, while any valid URL ID wins over remembered state.
- Decision: the authenticated user is normalized into an application context after login or token verification. Invalid stored sessions are removed instead of partially restoring a user.
- Result: course loading, membership role, loading/error state, and reload now live in `CourseRouteProvider`; the sidebar constructs links from the provider's URL-derived identity rather than mutable page state.

### Plan 1 / Task 8 — Canonical links and viewer-safe rendering

- Red evidence: source-contract tests showed course-list detail navigation dropped `course_id`, knowledge-graph workspace jumps rebuilt an AI hash without course identity, classroom studio returned to AI instead of course detail, and course settings always mounted editable controls.
- Green evidence: `6 passed` for canonical/source permission contracts; full frontend suite `141 passed`; production build passed.
- Decision: course settings now writes through the revision-aware Stitch API instead of the legacy Zustand update path. A 409 reloads the newest course and asks the teacher to review before retrying rather than overwriting another teacher's edit.
- Decision: viewers retain knowledge-graph, classroom, and player reading/playback. Graph mutation/auto-save, classroom generation, and server-side video export are disabled or unmounted according to capability.
- Result: every course-list/detail/workspace transition preserves `course_id`; copied URLs load the requested course; viewer course settings render semantic text instead of disabled edit controls.

### Plan 1 / Task 9 — Collaboration acceptance gate

- Focused acceptance: backend `2 passed`; frontend copied-link acceptance `1 passed`.
- Affected backend gate: `52 passed` across membership persistence/access/bootstrap/migration, CRUD/revision, all course route capabilities, collaboration, shared materials, and course scopes.
- Frontend gate: `141 passed`; lint completed with `0 errors, 82 warnings`, exactly matching the recorded baseline; production build passed in the preceding full gate and is rerun after this log/spec update before commit.
- Result: executable evidence covers two-teacher shared edits/resources, student backend denial, anonymous denial, stale-write protection, auto-enrollment modes, and URL authority. Verified Stage 0 link and all Stage 1 acceptance boxes are checked in the Spec; unverified visual Stage 0 items remain open.

### Plan 2 / Task 1 — Canonical generation source resolver

- Red evidence: focused collection failed because the generation source boundary did not exist.
- Green evidence: `21 passed` across all source modes and legacy RAG document/provider resolution.
- Decision: `course_auto` with explicit document IDs is rejected as contradictory, matching the strict handling already required for `none`; callers must choose `selected_documents` when IDs are supplied.
- Result: public course document IDs resolve deterministically to ready RAG keys, `none` proves zero catalog/content reads, cross-course and non-ready selections fail with stable codes, and immutable provenance snapshots exclude generated context text.

### Plan 2 / Task 2 — Shared source intent for direct generation

- Red evidence: `20 failed` showed missing `source_mode`, three schemas requiring documents unconditionally, invalid mode/ID combinations being silently accepted, and durable commands refusing no-source generation.
- Green evidence: `46 passed` across shared source contracts, command persistence/backward compatibility, v2 routes, and jobs API.
- Decision: source-bearing API models infer `selected_documents` only for legacy requests that omit `source_mode` but include IDs. New explicit contradictory combinations are rejected. Persisted commands use the same legacy inference without rewriting stored task rows.
- Decision: durable task-submission routes return HTTP 202; synchronous chat and prefill/outline operations retain their existing synchronous status.
- Result: report, quiz, game, flashcard, PPT outline/draft, graph, and blog now carry the same source contract; durable commands persist `source_mode`, public IDs, and bounded `deadline_seconds`.

### Plan 2 / Task 3 — Single-pass source provenance

- Red evidence: provenance tests failed because the task handler accepted no source resolver and material persistence accepted no source/config snapshots.
- Green evidence: `28 passed` across task handlers, provenance, formal material manifests, direct/legacy RAG providers, and job completion.
- Decision: a frozen `GenerationExecutionContext` carries one resolved source and recursively immutable configuration to adapters that opt into the new keyword; existing adapters remain compatible during staged migration.
- Decision: downstream payloads receive canonical RAG keys and the already-resolved context text. Providers expose direct RAG-key reads so public document IDs are not resolved a second time.
- Result: every durable generation resolves source intent once, preserves the same source/config snapshot in both handler-published and generator-published course materials, and records `created_by` plus `source_job_id`.

### Plan 2 / Task 4 — Stable course document identity

- Red evidence: the migration module and lifecycle-ready boundary did not exist; an additional dry-run test proved that constructing the storage manager would create directories during inspection.
- Green evidence: `21 passed` across migration dry-run/apply/idempotency, document lifecycle, stable reindex identity, public response privacy, and legacy RAG resolution.
- Decision: new uploads use opaque UUID public IDs. Migration-only backfills use deterministic UUIDv5 values derived from course ID and normalized legacy path so repeated repair is stable without exposing paths.
- Decision: missing or ambiguous RAG links are never presented as ready; records remain visible with `status=failed` and `error_code=RAG_INDEX_MISSING` so teachers can reindex them.
- Decision: the course document API no longer returns its internal relative filesystem path; subsequent actions use the public document ID.
- Result: dry-run performs zero filesystem writes, apply uses atomic replacement, a second apply reports zero changes, and reindex updates only mutable RAG metadata while preserving the public ID.

### Plan 2 / Task 5 — Durable direct lesson-plan generation

- Red evidence: all three focused tests failed with 404 or a missing service module before implementation.
- Green evidence: `58 passed` across the lesson-plan route/service/publication path, shared source contracts, durable commands, routes, task handlers, and job completion.
- Decision: the response retains the existing standard durable envelope field `task_id` rather than introducing a lesson-plan-only `job_id`; this keeps all generation routes consistent.
- Decision: the direct service runs outline and final-content phases inside the worker, using the immutable resolved source context. The HTTP route only validates and enqueues.
- Result: `/api/chat/v2/lesson-plan/direct` returns 202, persists a recoverable `lesson_plan_direct` command, and publishes a course-visible lesson-plan artifact with source/job provenance.

### Plan 2 / Task 6 — Unified AI classroom sources

- Red evidence: `8 failed` showed the classroom request had no source fields, contradictory selections were ignored, workers had no injectable resolver, and classroom manifests could not persist provenance.
- Green evidence: `58 passed` across all source modes, durable submission, worker resolution, classroom manifests, job orchestration, course authorization, and existing classroom generation/persistence behavior.
- Decision: source intent is persisted at submission and resolved exactly once in the durable worker. The HTTP request does no RAG lookup.
- Decision: `none` excludes both RAG document content and course knowledge-graph context, so it genuinely generates from the teacher's topic/configuration (plus explicitly enabled external web research) rather than silently using course evidence.
- Result: `course_auto`, `selected_documents`, and `none` share the same validation rules as other resources; the final course-visible classroom records `source_snapshot` and `source_job_id`.

### Plan 2 / Task 7 — Bounded durable executor pool

- Red evidence: the pool test initially failed collection because no pool existed; after implementation, the first concurrency assertion exposed that durable terminal status is named `succeeded`, not the legacy callback status `completed`.
- Green evidence: `20 passed` across pool isolation, once-only leasing, executor lifecycle, durable runtime, platform tasks, and application lifespan; the focused pool suite has `4 passed`.
- Decision: the pool defaults to three workers (`DURABLE_JOB_WORKERS`, minimum one) and reuses the existing atomic SQLite lease rather than adding nested model-call thread pools.
- Decision: shutdown signals all workers first and then joins them against one shared deadline; worker IDs that miss the deadline are returned for operational reporting.
- Result: a blocked generation no longer prevents a second queued task from completing, while two workers still execute one leased task exactly once and startup/shutdown remain idempotent.

### Plan 2 / Task 8 — Deadlines and deterministic cancellation recovery

- Red evidence: the focused suite initially produced `5 failed`; the task schema had no `deadline_at`, the executor could not accept a deterministic clock, and a stale leased task with `cancel_requested=1` was only requeued or failed as a lost worker.
- Green evidence: `11 passed` for the first deadline/reconciliation gate, followed by `47 passed` across deadlines, jobs API, reconciliation, runtime, task store/executor, completion, and generation command submission. The final focused gate includes deadline derivation and the cancel-during-completion race.
- Decision: durable rows store an absolute `deadline_at` timestamp. A command's bounded `deadline_seconds` is converted at enqueue time; a retry therefore receives a fresh deadline instead of inheriting an already-expired timestamp.
- Decision: cancellation wins over timeout during stale-lease recovery. Cancellation persists `GENERATION_CANCELLED`; deadline expiry persists `GENERATION_DEADLINE_EXCEEDED`. Both codes are synchronized to the owner-scoped public job ledger.
- Decision: success and partial-success transitions include an atomic cancellation/deadline guard. Reconciliation also refuses to adopt a previously published result for a canceled or expired task.
- Result: expired queued work never invokes its handler, stale cancellation converges after restart, active leases retry only while their deadline remains valid, and a late cancellation cannot be overwritten by a success transition.

### Plan 2 / Task 9 — Generation source preflight

- Red evidence: all `7` endpoint-contract tests returned 404 before implementation.
- Green evidence: the focused preflight suite has `7 passed`; the combined preflight, course authorization, source-contract/resolver, and lesson-plan route gate has `47 passed`.
- Decision: preflight accepts the same nine resource identifiers used by the reliability matrix, but resource type does not change source validation. This keeps one source contract across report, lesson plan, blog, quiz, PPT, flashcard, graph, game, and classroom.
- Decision: `course_auto` with zero ready documents is valid and returns `NO_READY_COURSE_DOCUMENTS` as a non-blocking warning. Explicit missing, cross-course, or non-ready selections remain blocking 422 responses with stable source error codes.
- Result: `POST /api/chat/v2/generation/preflight` requires course `generate`, reads only catalog metadata through `GenerationSourceResolver.validate`, exposes no RAG keys, creates no durable job, and never reads document content or invokes a model.

### Plan 2 / Task 10 — Nine-resource reliability matrix

- Red evidence: the first 27-case run exposed three test-harness failures because the Windows event loop uses a loopback socket pair; the network guard was narrowed to block non-loopback connections. A corrected source-job lookup then exposed a real late-publication race: a canceled blocked blog reached terminal `canceled` but still wrote an artifact under its job-derived material ID.
- Green evidence: the deterministic matrix has `28 passed` (27 resource/source-mode combinations plus blocked-blog cancellation isolation). The complete Plan 2 affected gate has `96 passed`; the specified jobs/completion/reconciliation/document-lifecycle/course-route regression has `30 passed`.
- Decision: the no-network guard allows only the operating system's loopback event-loop plumbing; all generation and classroom providers remain deterministic fakes. Each case also proves the declared production route exists.
- Decision: `GenerationTaskHandler` checks cancellation immediately before model work and again before publishing or adopting a result reference. This closes the handler-return race in addition to the durable terminal-state guard.
- Decision: a stale route regression expected the public knowledge-document API to expose the server's relative file path for web documents. The test now preserves the established privacy boundary: public source URL and stable document ID are visible, internal path is not.
- Result: report, lesson plan, blog, quiz, PPT, flashcard, mind map, game, and AI classroom all pass `course_auto`, `selected_documents`, and `none`; wrong-course selections fail before a provider call; artifacts preserve source snapshots and are readable by another course teacher; canceled blocked work publishes no late artifact while unrelated jobs complete.

### Plan 3 / Task 1 — Reproducible browser fixtures and visual baseline

- Red evidence: the target navigation smoke failed in every viewport because the home course card is not a semantic link and the six-item course hierarchy does not yet exist. The first harness run also showed that waiting for full page load and taking full-page screenshots was unstable under five parallel Vite clients.
- Green evidence: the browser baseline command reports `10 passed`: five explicitly documented expected navigation failures plus five successful nine-page diagnostic inventories. The inventory-only rerun has `5 passed`; the frontend unit gate has `141 passed`; the production build passes.
- Decision: until Task 2 implements the target hierarchy, the traversal test uses Playwright's expected-failure annotation rather than leaving the committed suite red. Task 2 must remove that annotation and make the same test pass normally.
- Decision: screenshots use the configured viewport rather than unbounded full-page capture. This is the correct baseline for the five release dimensions and avoids animation/polling content extending capture indefinitely.
- Decision: fixed API interception covers authentication, courses, documents, knowledge structure, jobs, classroom materials, resources, runtime configuration, and chat. Internal Playwright outputs are ignored; the durable evidence is the fixture, route/viewport inventory, and repeatable command.
- Visual evidence: real 1366×768 renders confirmed a nearly invisible primary action on course detail, a non-link course card and student-oriented home copy, mixed knowledge/generation language in the workspace, and a second textbook-upload workflow in the knowledge graph. A fixture-only RAG response-shape warning was corrected before the final capture.
- Result: five deterministic viewport projects now render the real frontend against stable local data with no backend dependency, providing a repeatable before/after surface for every remaining Plan 3 task.

### Plan 3 / Task 2 — Unified course workspace shell

- Red evidence: the navigation unit test failed on the missing `courseNavigation` module; the committed traversal baseline could not find a semantic course link or the six target destinations.
- Green evidence: the frontend unit gate has `144 passed`; the production build passes. The browser matrix produced `14 passed` across five viewports, with the only failure showing that 1024px correctly hid the desktop sidebar; after teaching the traversal acceptance test to use the compact drawer, the 1024px rerun passed.
- Decision: the six teacher concepts are course overview, Q&A/generation, course knowledge, AI classroom, course resources, and settings. Knowledge documents and knowledge graph share one active top-level destination; Task 4 will complete their in-page unification.
- Decision: viewers do not receive a settings destination. Owners and editors share the same workspace shell, while the membership badge makes their capability context visible.
- Decision: below 1180px the sidebar becomes an explicit drawer instead of reducing the existing pages' working width. URL-derived `course_id` remains the navigation identity, and remembered course state remains only a home-page convenience.
- Decision: the global job store stays mounted once in `App`; its floating launcher is disabled on course routes and the shell supplies the single inline task-center trigger. Legacy page sidebars are suppressed through shell context during staged migration.
- Result: every core course route now has a stable breadcrumb, course identity, page title, active navigation item, task center, responsive menu, shared loading/empty/error/offline/forbidden/conflict presentation, and no root horizontal overflow in the browser acceptance suite.

### Plan 3 / Task 3 — Teacher core-page hierarchy

- Red evidence: the course-card test failed on the missing factual presentation boundary; the previous adapter synthesized a decorative progress percentage from course-ID character codes.
- Green evidence: the frontend unit suite has `146 passed`, the production build passes, and `20 passed` across login, course home, overview, and viewer settings in all five target viewports. The in-app browser render was also inspected directly after implementation.
- Decision: the course home owns the only course list. The old course-list route reuses that page instead of maintaining a carousel/list variant.
- Decision: card counts are loaded from the course document and course material APIs, while active task counts come from the shared job store. Failed counter requests degrade to factual zero rather than guessed progress.
- Decision: the overview removes the duplicated full-height image hero. It prioritizes description, objectives, indexing readiness, latest resources, active tasks, course revision, one primary action, and the six stable course destinations.
- Decision: 409 settings conflicts preserve a copyable local draft while loading the newest server revision. Viewers receive only factual read-only fields; system runtime settings are linked from the profile only for administrators.
- Result: login copy now explains the teacher role and reports errors inline; demo-account help is absent unless explicitly enabled by `VITE_SHOW_DEMO_ACCOUNT`; course cards contain no randomized progress and remain searchable without horizontal overflow.

### Plan 3 / Task 4 — Unified course knowledge

- Red evidence: the teacher-route suite showed separate knowledge-base and graph destinations and had no view-aware route reader. The browser baseline exposed a textbook parser plus a second node-file uploader inside the graph.
- Green evidence: the frontend unit gate has `147 passed`; the production build passes. The five-viewport browser run produced `14 passed` with one compact-only association-action visibility failure; moving the association action to the structure header and adding compact panel tabs produced `3 passed` on the 1024px rerun.
- Decision: `#knowledge?course_id=...&view=documents|structure` is the only new course-knowledge route. The legacy `#graph` hash redirects to `view=structure` and preserves course identity.
- Decision: document upload exists only in the documents view. The structure view links back to existing course documents through “关联课程资料”; its legacy textbook and node upload controls are no longer visible or actionable.
- Decision: below 1180px, structure settings, canvas, and node detail are explicit tabs. The canvas is the default and receives the full available width; desktop keeps the three-panel arrangement.
- Result: course navigation now has one “课程知识” destination with two durable subviews, one visible uploader, deep-link refresh, legacy redirect compatibility, and an operable 1024px canvas.

### Plan 3 / Task 5 — Shared generation workflow

- Red evidence: the source-selection and registry tests initially failed because no shared generation modules existed; the previous `StudioPanel` contained thousands of lines of resource-specific branches. The first 1920px browser run also exposed an unstable assumption that the generation panel was already rendered immediately after navigation.
- Green evidence: the frontend unit gate has `151 passed`; the production build passes; lint has no errors. The generation browser suite has `10 passed` across all five release viewports, including keyboard progression, reachable confirmation footer, durable submission, and refresh recovery.
- Decision: nine resource types share one registry, three source modes, one four-screen configuration/confirmation flow, one preflight/submission hook, and the global owner-scoped job store. The background-job state is the fifth conceptual workflow stage rather than a separate modal page.
- Decision: `StudioPanel` is now a thin compatibility adapter. The current Stitch workspace exposes a stable top-bar “生成工厂” action so loading timing and responsive layout no longer determine whether the factory can be opened; the legacy routed workspace receives the same affordance for compatibility.
- Decision: drafts cache only resource type, source identifiers, and editable configuration by course. Tokens and generated content are not stored. Leaving selected-document mode clears stale document IDs.
- Result: chat remains the primary surface, opening the factory never applies an opaque chat-blocking overlay, 1024px uses the existing responsive panel behavior, and submitted jobs remain visible/recoverable through the single global task center.

### Plan 3 / Task 6 — Long-form generation configurations

- Red evidence: the exact serialization suite failed on missing report, lesson-plan, and blog definitions. The former generic form could not prove that report depth, lesson process, or blog tone/length reached a durable command.
- Green evidence: all four definition/validation tests pass; the two backend request-schema tests pass; the production build passes. The browser request-interception suite has `5 passed` across every release viewport and proves all three forms keep their primary action reachable at 1024×768.
- Decision: fixed report templates are local immediate choices; optional recommendation failures do not own or overwrite form state. Lesson-plan objectives use one editable line per objective and the primary action reflects whether outline confirmation is enabled.
- Decision: backend request schemas now explicitly accept and persist the visible lesson process/outline intent and blog audience/tone/length/structure/requirements fields. This avoids a visually successful form whose extra fields Pydantic would silently discard.
- Decision: unreachable report and lesson-plan legacy modal implementations were removed after the shared factory gained equivalent typed forms and browser coverage.
- Result: every visible long-form field has a named validation rule, one auditable serializer, an accepted API field, and intercepted end-to-end request evidence.

### Plan 3 / Task 7 — Practice generation configurations

- Red evidence: the practice serialization suite failed because quiz, flashcard, and game definitions did not exist. The previous game endpoint accepted only `game_type`, so topic, count, difficulty, and classroom duration could not survive submission.
- Green evidence: all five frontend definition tests pass; two backend schema/boundary tests pass; the production build passes. The browser suite has `5 passed` across all release viewports and intercepts exact quiz, flashcard, and game request bodies.
- Decision: quiz uses only the four question types accepted by the backend (`choice`, `blank`, `short`, `judge`). Answer and explanation switches are independent. Flashcard titles are plain text, including URL-shaped text, and are never opened as links.
- Decision: game type choices are real buttons with `aria-pressed`, so arrow/tab navigation and Enter activation use browser semantics. A compact preview summarizes selected template, count, difficulty, and duration before submission.
- Decision: backend schemas and durable command snapshots now preserve quiz audience plus the complete game configuration. Unused quiz, flashcard, and game legacy entry modals were removed after the shared forms gained coverage.
- Result: all practice resource settings are bounded, retry-safe through the retained shared draft, keyboard-operable, and auditable from form through request payload.

### Plan 3 / Task 8 — Visual generation configurations

- Red evidence: the focused definition suite failed because PPT, mind-map, and classroom definitions did not exist. The previous PPT entry exposed a raw JSON outline, the mind-map request dropped its description, and the standalone classroom page used a separate one-textarea configuration path.
- Green evidence: all four visual-resource definition tests pass; the two backend contract tests pass; the production build passes. The browser suite has `5 passed` across all release viewports and verifies edited PPT slides, mind-map depth/description, classroom voice/scene settings, and the shared standalone classroom form.
- Decision: PPT outline editing uses structured slide fields for title, key points, speaker notes, and visual instructions. The outline endpoint supplies the durable draft identity, while the final generate request sends the explicitly edited slide array; raw JSON is not exposed.
- Decision: a generated mind map is an independent course resource named “思维导图”. It never changes the course knowledge structure implicitly.
- Decision: the factory and standalone classroom page reference the exact same generation definition and form. Voice selection is persisted with the job and applied to that classroom's runtime snapshot when speech is enabled.
- Result: all three visual resources preserve their visible configuration end to end, PPT slides support accessible add/remove/reorder operations, and the confirmation footer remains reachable at 1024×768.

### Plan 3 / Task 9 — Responsive resources and classroom playback

- Red evidence: the constraint suite failed on the missing preview boundary. Course resources rendered every known non-classroom artifact as generic Markdown, exposed no consistent factual provenance block, and used the 1280px framework breakpoint instead of the specified 1180px content threshold.
- Green evidence: the frontend gate has `167 passed`; the production build passes. The hostile-content and classroom browser suite has `10 passed` across all five release viewports.
- Decision: report and lesson-plan content retain a constrained rich-text presentation, while blog, quiz, flashcard, PPT, mind map, and game use type-aware interactions. Tables and code may scroll inside their own containers; links, images, citations, and unbroken strings cannot widen the page root.
- Decision: resource metadata is limited to type, creator, teacher-facing source range, creation time, and status. RAG keys, storage paths, renderer names, and material IDs are not presented to teachers.
- Decision: below 1180px the resource list sits above the preview instead of compressing both. At 1390px and below, classroom catalog and transcript become explicit overlay panels so a 1280×720 first screen retains the stage, previous/play/next, progress, scene title, and voice state.
- Result: hostile 200-character titles, wide tables, long URLs, code, large images, and long citations remain inside the resource surface; all core classroom controls stay visible without page scrolling.

### Plan 3 / Task 10 — Teacher frontend quality gate

- Red evidence: the first full browser gate had `14 failed` because two early baseline tests still targeted the removed generic topic field and an ambiguous course-overview link. After updating those contracts, the second full gate reached `120 passed` but exposed two intermittent empty-state failures during rapid cross-course navigation.
- Green evidence: the retired-mainline guard has `6 passed`; the focused legacy generation/navigation rerun has `20 passed`; the cross-course state race passed `10/10` repeated runs across 1920×1080 and 1280×720. The final gates report `172/172` unit/contract tests, lint with `0 errors`, a successful production build, and Playwright with `122 passed`, `3 skipped`, `0 failed` across all five projects.
- Decision: approved light snapshots cover 11 core pages at all five viewports; dark snapshots cover 1366×768 and 1024×768. The three skipped tests are the intentionally omitted duplicate dark runs at the other viewports, not untested product paths.
- Decision: visual baselines use a 1% comparison tolerance for rendering noise, but the final approved images were once regenerated at zero tolerance so small semantic fixes—deferred classroom validation, teacher-facing document metadata, and explicit compact classroom controls—are present in the stored goldens.
- Decision: the knowledge structure no longer contains hidden textbook import, node upload, active-document loading, or fabricated node-resource branches. The remaining legacy graph route is redirect-only and the structure view links to the single course document source.
- Decision: a route course object may be used only when its ID matches the URL `course_id`. This prevents a previous course's resources from appearing during rapid navigation and keeps the URL as the sole course identity authority.
- Human review: Codex reviewed login, home, overview, question/generation, both knowledge views, classroom list/player, resources, settings, and profile in the approved page matrix on 2026-08-07. The detailed disposition is recorded in `docs/qa/teacher-frontend-release-checklist.md`.
- Result: stage 4–6 acceptance items backed by automated assertions or named visual review are complete. Page roots do not overflow, configuration actions remain reachable, the main workflow is keyboard operable, critical colors meet WCAG AA, hostile resource content is contained, and removed duplicate flows are protected by regression tests.
