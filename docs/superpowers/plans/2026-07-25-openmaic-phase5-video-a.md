# OpenMAIC Phase 5 Video A Implementation Plan

> **Execution:** follow test-driven development and commit after every task.

**Goal:** Turn the same persisted OpenMAIC classroom used by the browser player
into an H.264 MP4 plus measured `LessonTimeline` and sidecar SRT, using a clean
headless 1x playback and pre-generated narration audio.

**Architecture:** Add a render-only classroom route that can play one stable
scene without application chrome and exposes completion/timeline state to an
export worker. A Node/Playwright CLI records each scene to WebM, then invokes
FFmpeg to create H.264 scene segments, concatenate them, place narration audio
at timeline offsets, and write SRT from the narration track. A thin FastAPI job
service launches the CLI, persists artifacts beside the classroom material, and
exposes progress/download APIs. Scene segmentation, timeline, mux and captions
remain reusable by a future frame-driven B renderer.

**Quality gates:** pure timeline/SRT tests, render-page tests, CLI fixture E2E
with ffprobe, backend service/API tests, frontend lint/build, browser workflow,
and classroom regression.

---

## Task 1: Derive reusable video artifacts from LessonTimeline

**Files**

- Create `Edu_AI/src/openmaic/videoExport.ts`
- Create `Edu_AI/src/openmaic/videoExport.test.ts`
- Modify `Edu_AI/src/openmaic/timeline.ts`

1. Add failing tests for SRT time formatting, narration ordering, multiline
   text, invalid/overlapping timeline validation, and scene offset merging.
2. Implement pure `timeline → SRT`, timeline validation, and measured
   per-scene timeline merge helpers.
3. Verify targeted/full frontend tests.
4. Commit as `feat(video): derive artifacts from lesson timeline`.

## Task 2: Add a render-only classroom route

**Files**

- Create `Edu_AI/src/stitch/pages/_dev/ClassroomVideoRender.tsx`
- Create `Edu_AI/src/openmaic/videoRenderState.ts`
- Create `Edu_AI/src/openmaic/videoRenderState.test.ts`
- Modify `Edu_AI/src/stitch/App.tsx`
- Modify `Edu_AI/src/stitch/shared.tsx`

1. Add failing tests for scene selection, unsupported-scene skipping, cumulative
   timeline state, and terminal success/failure state.
2. Build a chrome-free 1920×1080 route accepting
   `course_id/classroom_id/scene_index` and a deterministic local fixture.
3. Expose machine-readable `data-export-status`, scene count, measured timeline
   JSON, and narration resource references; auto-play exactly one selected
   scene and end deterministically.
4. Verify in a cold browser with no console errors.
5. Commit as `feat(video): add headless classroom render route`.

## Task 3: Record scenes and compose MP4/SRT

**Files**

- Modify `Edu_AI/package.json`
- Modify `Edu_AI/package-lock.json`
- Create `Edu_AI/scripts/export-classroom-video.ts`
- Create `Edu_AI/scripts/videoPipeline.ts`
- Create `Edu_AI/scripts/videoPipeline.test.ts`

1. Add Playwright as a dev/runtime export dependency.
2. Add failing tests for FFmpeg concat/mux argument generation, safe output
   paths, audio data extraction, and failed segment cleanup behavior.
3. Record each scene in a fresh Playwright context, close it to finalize WebM,
   convert to H.264, concatenate in scene order, mux narration at measured
   offsets, and emit `timeline.json` + `subtitles.srt`.
4. Run a deterministic fixture E2E; assert MP4 video+audio streams with
   ffprobe, non-empty SRT, measured timeline, and no browser errors.
5. Commit as `feat(video): record and compose classroom segments`.

## Task 4: Add the classroom video job workflow

**Files**

- Create `Edu_AI/api/src/app/services/classroom_video_service.py`
- Modify classroom routes/job types as required
- Add backend service/API tests
- Create `Edu_AI/src/openmaic/VideoExportButton.tsx`
- Modify `Edu_AI/src/stitch/pages/ClassroomPlayer.tsx`

1. Add failing tests for job submission, duplicate active-job guard, progress,
   subprocess failure, artifact persistence, authorization, and downloads.
2. Launch the Node exporter as a bounded subprocess using explicit workspace,
   URL, auth and FFmpeg paths; persist MP4/timeline/SRT under the course
   material directory and expose them only through authenticated routes.
3. Add a classroom action that submits, polls, displays progress, and downloads
   the completed MP4/SRT without blocking the player.
4. Verify backend/frontend tests and browser job flow.
5. Commit as `feat(video): add classroom export job workflow`.

## Task 5: Sign off Phase 5

**Files**

- Create `docs/spec/SPEC-10_视频A导出.md`
- Create `docs/acceptance/ACC-10_视频A导出_验收.md`
- Modify spec/acceptance indexes
- Modify `docs/OpenMAIC复用_实施总纲_2026-06-30.md`
- Modify `项目总览地图.md`

1. Inspect MP4 streams/duration/resolution, measured timeline, SRT timing,
   per-scene segments, and persisted/downloaded artifacts.
2. Run full frontend and relevant backend regression gates.
3. Record exact evidence and remaining B-only work.
4. Commit as `docs(migration): close Phase 5 video A acceptance`.
