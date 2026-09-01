# OpenMAIC Phase 6 Legacy Retirement Implementation Plan

**Status:** Completed and accepted by SPEC-11 / ACC-11 on 2026-07-25.

> **For Codex:** Execute each task in order, run its focused regression gate, and
> commit the task before continuing.

**Goal:** Remove the html2ppt, AI_Lecturer, and teaching_video_bridge runtime
chains after the OpenMAIC classroom, PPTX, and Video A replacements have passed
acceptance.

**Architecture:** Retire product entry points and process lifecycle wiring before
deleting their implementations. Keep the OpenMAIC classroom APIs as the single
courseware path. Remove service-specific dependencies, environment variables,
install/start steps, and tests together with each retired boundary. Historical
design documents remain historical, but active maps/specs/deployment documents
must describe only the replacement architecture.

**Verification rule:** Active source, environment templates, install scripts, and
deployment manifests must contain no `html2ppt`, `AI_Lecturer`, or
`teaching_video_bridge` references. The replacement classroom/PPTX/video tests
must stay green.

---

## Task 1: Freeze the retirement contract

**Files**

- Create `docs/superpowers/plans/2026-07-25-openmaic-phase6-legacy-retirement.md`

1. Inventory tracked files, runtime imports, routes, UI entry points, startup
   hooks, environment variables, install steps, and deployment dependencies.
2. Record the safe order: detach AI Lecturer/bridge, detach html2ppt workflow,
   delete vendor trees, then clean deployment/docs.
3. Commit as `docs(migration): plan Phase 6 legacy retirement`.

## Task 2: Retire AI Lecturer and teaching video bridge

**Backend**

- Remove teaching-video and AI lecture-session routes/schemas/services.
- Remove process-manager startup/shutdown wiring and configuration.
- Remove bridge-only material hydration; stored OpenMAIC classroom/PPTX metadata
  remains self-contained.
- Remove bridge and AI Lecturer tests after replacement route coverage is
  confirmed.

**Frontend**

- Remove the legacy Video Player route/page, WebRTC hook, AI Lecturer API
  adapter, legacy teaching-video calls, environment variables, and material
  actions.
- Direct courseware creation/playback/export through Classroom Studio and
  Classroom Player only.

**Vendor**

- Delete `Edu_AI/api/src/modules/AI_Lecturer/`.

**Verification**

1. Add/update tests that assert application startup has no AI Lecturer process
   manager and course routes expose no legacy teaching-video endpoints.
2. Run focused backend route/bootstrap tests and frontend tests/type/lint gates.
3. Assert active runtime source has no AI Lecturer/bridge references.
4. Commit product detachment and vendor deletion as separate commits when each
   is independently green.

## Task 3: Retire html2ppt

**Backend**

- Remove the html2ppt client, polling/edit executors, and old chat PPT entry
  wiring.
- Keep generic content types only where other features still consume them; do
  not leave a dormant network client or `HTML2PPT_BASE_URL`.
- Make Classroom Studio the supported courseware entry and retain OpenMAIC
  classroom generation plus browser-side PPTX export.

**Startup/vendor**

- Remove html2ppt launch/install/config steps.
- Delete `Edu_AI/api/src/modules/html2ppt/`.
- Remove html2ppt-only tests and replace route/tool expectations with an
  explicit unsupported/redirected legacy behavior where needed.

**Verification**

1. Run focused chat import/startup tests to prove no removed module is imported.
2. Run classroom generation/PPTX tests.
3. Assert active runtime source has no html2ppt references.
4. Commit detachment and vendor deletion as separate commits when each is green.

## Task 4: Remove GPU-era deployment dependencies

**Files**

- Modify `DEPENDENCIES.md`
- Modify `docs/deployment/README.md`
- Modify `scripts/install-all.ps1`
- Modify `scripts/install-all.sh`
- Modify `Edu_AI/api/src/start_api.bat`
- Modify active `.env.example` files

1. Remove CUDA, PyTorch, Wav2Lip/MuseTalk, LiveTalking, AI Lecturer ports, and
   html2ppt service requirements.
2. Add the supported Node/OpenMAIC, Playwright Chromium, FFmpeg/ffprobe, and
   Chinese font requirements for classroom/PPTX/video A.
3. Add static checks for removed names and obsolete ports.
4. Commit as `chore(deploy): remove legacy GPU and html2ppt services`.

## Task 5: Sign off Phase 6

**Files**

- Create `docs/spec/SPEC-11_旧模块下线.md`
- Create `docs/acceptance/ACC-11_旧模块下线_验收.md`
- Modify spec/acceptance indexes
- Modify `docs/OpenMAIC复用_实施总纲_2026-06-30.md`
- Modify `项目总览地图.md`

1. Prove tracked vendor paths are absent.
2. Prove active runtime/deployment source has zero legacy references.
3. Run full frontend and backend regression gates plus replacement browser smoke
   checks.
4. Record repository-size reduction, exact tests, remaining historical-doc
   references, and Video B as optional future work.
5. Commit as `docs(migration): close Phase 6 legacy retirement`.
