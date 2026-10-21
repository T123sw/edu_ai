# HyperFrames AI Classroom Implementation Plan

> **For agentic workers:** Use subagent-driven-development to implement tasks with scoped review and whole-change verification. Checkboxes describe actual completion, not intended capability.

**Goal:** Replace OpenMAIC classroom generation and presentation with native HyperFrames projects, narrated animation, exact-version timeline context, and native video export.

**Architecture:** Keep Edu_AI's course preparation, durable jobs, model gateway, TTS, resource versions, and learning conversations. Preserve a complete pinned upstream HyperFrames source tree and its native CLI/player/skills; put Edu_AI adapters outside that tree. Store native multi-file compositions separately from the semantic teaching timeline. Serve only authorized immutable project files to the player.

**Tech Stack:** Python 3.12/FastAPI/Pydantic, React/TypeScript, HyperFrames 0.8.168, Node >=22, Chromium, FFmpeg/ffprobe.

**Spec:** User agreement in this session: replace all OpenMAIC AI classroom functionality with HyperFrames; retain upstream native capabilities; question context comes from narration + timeline + visual descriptions/events + the position at question submission. Existing design baselines: `docs/architecture/2026-09-17-course-preparation-agent-design-cn.md` and `docs/architecture/2026-09-17-learning-agent-design-cn.md`.

## Global Constraints

- Preserve full upstream source, license, packages, skills, docs, examples, and registry; pin the commit/version and keep local integration outside upstream.
- New classrooms use `format: hyperframes/v1`; never synthesize OpenMAIC slides as an intermediate representation.
- Preserve resource type `classroom`, resource IDs, exact versions, course/topic authorization, immutable question snapshots, task cancellation and durable checkpoints.
- No new independent model content-review gate. Run actual native structure/runtime/layout checks and bounded code repair. Do not impose arbitrary scene, course-duration, or text-length limits.
- TTS is Edu_AI-owned; retain voice configuration and caching. Measure real audio duration; do not claim character-count estimates are audio alignment.
- Preserve old user records; retire old generation/playback dependencies after replacement. Old records may expose archived text/media with an explicit legacy notice, never masquerade as new animated projects.
- PPTX export is retired for new classrooms: HTML project download and MP4/SRT are the new exports. Standalone quiz/practice/PBL/report tools are not removed.
- Generated executable HTML is isolated from parent credentials; source paths, archives, media references and authorization are validated. No shell interpolation or production database tests.
- Work in the isolated snapshot at `.worktrees/hyperframes-classroom-20261017`. Preserve current user's unrelated modifications. Do not deploy unverified changes.

## Contract and API

Native content object:

```json
{"format":"hyperframes/v1","title":"神经网络","project":{"id":"hf_<resource-id>","digest":"sha256","entry":"index.html"},"timeline":{"duration":12.4,"segments":[{"id":"neuron","title":"一个神经元","start":0,"end":12.4,"narration":"输入加权求和，再加偏置。","visual_description":"公式 z=Σwᵢxᵢ+b","audio_path":"assets/neuron.mp3","objective_ids":["o1"],"source_ids":[],"events":[{"start":4,"end":7,"target":"bias","description":"偏置 b 高亮"}]}]},"exports":{"video":"exports/lesson.mp4","subtitles":"exports/lesson.srt","project":"exports/project.zip"}}
```

Time units are seconds throughout. Intervals are `[start,end)`, with the final endpoint mapped to the last segment. Gaps are allowed and yield no current narration, never invented speech. IDs are unique; finite nonnegative times; events remain inside their segment; declared duration covers segments. Project digest binds all published file hashes. The semantic timeline is metadata authored alongside the composition, not a restricted animation DSL: arbitrary native SVG/GSAP/CSS, subcompositions and local media remain supported.

- Existing exact-material route continues returning the resource and its `content` plus flattened classroom body.
- `POST /api/self-learning/courses/{course_id}/materials/classroom/{material_id}/versions/{version}/playback`: authorize exact version, issue short-lived project-file capability, return `project_url`, video/subtitle/project download URLs and expiry.
- `GET /api/hyperframes/projects/{ticket}/{path:path}`: validate signed scoped ticket, expiry, current resource permission and matching project digest; serve allowlisted manifest files only. Relative URLs stay inside the same project capability path. CSP and opaque player frame prevent parent access.
- Existing learning `agent-turns` endpoint remains. Add `kind: hyperframes` locator `{seconds, segment_id?, content_hash?}`; add timeline position to classroom playback snapshot. Resolve current segment/events server-side from the authorized stored version. Client does not submit authoritative narration or visual descriptions.
- Source citations accept the same locator and reopen exact version/time. Reading facts retain explicit completion semantics; seeking does not count the skipped span as watched.

## Task 1: Native upstream runtime and project generation

**Files:** create `vendor/hyperframes/`, `hyperframes-runtime/package.json`, `backend/src/app/integrations/hyperframes/{contracts,projects,runtime,generation}.py`, `backend/src/tests/hyperframes/`; modify `backend/src/app/course_preparation/adapters/classroom.py` and generation validators only after adapters are ready.

**Interfaces:** `validate_content(content) -> dict`; `ProjectStore(root=None).publish(project_id, files) -> dict` and `.file(project, path) -> Path`; `generate_classroom(payload, *, gateway, context, artifact, checkpoint=None) -> artifact envelope`. Exact published contracts in `contracts.py` are authoritative for consumers.

- [x] Pin full upstream SHA `b18b3e958aa199529fa5fa06728e81b97d520021`; install native CLI/player 0.8.168 in an independent runtime with a lockfile. Record provenance and update instructions.
- [x] Test project traversal, symlinks, immutability, digest mismatch, invalid times, interval gaps and final endpoint before implementing storage/contracts.
- [x] Generate structured narration/visual scene plan with the existing gateway; synthesize semantic segments through existing TTS; probe each audio with ffprobe; create timeline from measured durations.
- [x] Load relevant full native authoring instructions and produce complete files, including composition IDs, GSAP timelines, audio tags and real audio durations. Preserve multi-file composition structure; no hard-coded lesson template.
- [x] Execute native lint/check and bounded model repairs with error output; persist plan/audio/code/check phases. Render actual MP4 via native CLI, write SRT and downloadable source archive. Refuse success if mandatory audio/video missing.
- [x] Cancellation terminates the entire subprocess group; runtime errors remain actionable. Reuse already completed stages when retrying identical input; changed specs invalidate stale stages.
- [x] Run isolated tests and a real native CLI sample check/render; record which inputs used model/TTS and which were fixtures.

## Task 2: Versioned serving, question context, delivery contracts

**Files:** create `backend/src/app/api/hyperframes.py`, `backend/src/app/self_learning/hyperframes_context.py`; modify `bootstrap.py`, `self_learning/{contracts,resource_reader,classroom_context}.py`, request snapshot DTOs, `artifact_revision/adapters.py`, `chat/harness/{reviewed_resource,classroom_policy}.py`, `course_preparation/resource_alignment.py`, `resource_learning/manifest.py`.

**Interfaces:** consume Task 1 content/project contracts. `timeline_context(content, seconds, segment_id=None)` returns authored metadata and interval quality, explicitly marking visual descriptions as metadata, not observed screenshots.

- [x] Test unauthorized/expired ticket, wrong version/digest, encoded traversal, invalid frame position and segment mismatch. Use dependency overrides and temporary stores, never production data.
- [x] Implement authorized playback-session and file routes; support range-capable media delivery and safe attachment download; no credentials enter generated files.
- [x] Branch validators/digests on `format`, retaining legacy read validation; update preparation receipts/duration and learning manifest to actual native timeline.
- [x] Resolve current and adjacent segments, active visual events and source IDs from server content. Freeze at accepted turn; preserve historic question references.
- [x] Test final endpoint, gaps, forward/backward seek, unknown locator, old records and exact-version retrieval.

## Task 3: Native player and current classroom replacement

**Files:** create `frontend/src/hyperframes/{types,HyperframesClassroom,timeline}.tsx/ts`; modify shared `ClassroomPlaybackSurface.tsx`, `liveLearning/{MaterialEntry,readingContext}.tsx/ts`, self-learning reference handling and relevant API types; update frontend dependencies.

**Interfaces:** consume playback session API and native content. Emit `kind: hyperframes` locator with seconds and optional segment ID; emit snapshot version/resource reference through existing reading channel.

- [x] Use actual `@hyperframes/player` with isolated origin, local runtime assets, controls and real audio. Preserve pause/seek/speed/volume/fullscreen capabilities; expose chapters, transcript and downloads.
- [x] Pause/resume for learning questions, restore precise time after refresh; suppress stale responses/events after resource switch. Handle session expiry with visible retry and position restoration.
- [x] Update bridge parsing, citations, snapshot contracts and player controls. No scene-index/time conflation. Preserve explicit completion and actual watched intervals.
- [x] Replace shared classroom surface so all classroom entry points reach native player; render archived legacy text/available media explicitly, without loading OpenMAIC renderer.
- [x] Run focused TypeScript tests/typecheck and real browser checks: sound, seek, pause, chapter jump, question snapshot, refresh, desktop/mobile, browser autoplay rejection.

## Task 4: Retire old classroom path and deploy integration

**Files:** `backend/src/app/services/classroom_service.py`, remaining classroom job handlers, old revision routing; `frontend/src/openmaic/` and old renderer/export routes; `scripts/{install-all,start-production,start-dev}.*`, `deploy/systemd`, `.env.example`, `DEPENDENCIES.md`, docs.

- [x] Inventory every OpenMAIC runtime import, package, process and API; classify new replacement, archived reader, or unrelated resource consumer. Replace alternate generation/revision paths too, not only course preparation.
- [x] Remove default OpenMAIC startup and renderer/PPTX dependency chain. Move reusable TTS and learning utilities to product-neutral modules; preserve compatibility only where old stored records require it.
- [x] Retain source history outside active runtime; no deletion of production classroom records or media. Document existing exports and regeneration path for archived classrooms.
- [x] Provide installer/runtime preflight for pinned native CLI, Chromium, ffmpeg, fonts and writable project store; update production start scripts to use HyperFrames.
- [x] Source scan proves no active classroom generation/playback still invokes OpenMAIC. Review remaining mentions individually; historical docs need not be renamed.

## Task 5: End-to-end verification and handoff

- [x] Unit/integration tests for contracts, serving/auth, timeline context, cancellation, retry and exact versions; broad relevant old-resource regression.
- [x] Generate a real Chinese lesson with configured model + TTS in isolated storage, native check/render, ffprobe audio stream/duration, original project replay and export downloads.
- [x] Browser test new course classroom and real accepted question at a known time, pause/resume, speed/seek, refresh and mobile readability. Isolate all writes and clearly label mocked UI-only checks.
- [x] Independent spec/code review; fix findings; final source/dependency scan; build application.
- [x] Update this checklist, acceptance evidence, project map and operational documentation. Integrate only migration delta against baseline, detect concurrent changes before copying. Report exact implemented/verified/deployed state and any external blockers; do not label an incomplete replacement complete.

## Decisions and cleanup order

1. Add native contracts/runtime before switching generation.
2. Switch generation + delivery + player + question context together in isolated workspace.
3. Stop old generation and remove live imports only once new path is verified.
4. Keep historical resource IDs/versions; old content is read-only archival data. Never silently rewrite old lessons or learning evidence.
5. Native upstream Studio/SDK/catalog/skills remain available in the vendored source/runtime. Exposing its editing server to users requires our authorization/version flow; retaining native code does not mean exposing an unauthenticated service.
6. No additional human confirmation between implementation tasks: the user explicitly requested planning followed by execution.

## Verification notes

Implementation and real-generation evidence: `docs/acceptance/2026-10-17-hyperframes/README.md`. The accepted-question test uses the real generated lesson and actual isolated persistence/context logic with a deterministic answer model. Browser business APIs are mocked, while player/audio/compositions are real. Production deployment is not performed by this plan execution.

Source integration completed into `/home/zxqs_ep/Edu_AI`: 9,683 migration paths copied and hash-verified, with pre-existing changes preserved and the concurrent project-map update merged. Rollback evidence: `/home/zxqs_ep/data/main-review/hyperframes-integration-backup-20261017/manifest.json`. Pinned runtime/frontend dependencies installed in original checkout; native preflight passed. Production frontend dist and services were not changed.
