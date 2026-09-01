# Frontend Architecture Refactor Design

**Date:** 2026-05-06

**Scope:** Edu_AI frontend architecture refactor, starting from the currently running React + Vite frontend under `frontend/src`.

**Decision:** Use the currently running `stitch` shell as the first-phase mainline, then reorganize it into a clearer application architecture.

---

## 1. Background

The frontend is not only bloated; it currently contains two competing mental models:

1. The active runtime path:
   - `frontend/src/main.tsx`
   - `frontend/src/stitch/App.tsx`
   - `frontend/src/stitch/pages/*`

2. A mostly disconnected React Router structure:
   - `frontend/src/routes/AppRoutes.tsx`
   - `frontend/src/layout/*`
   - many older pages under `frontend/src/pages`

The production build currently passes, so the first refactor phase should not replace the application shell wholesale. The safer path is to treat the current `stitch` shell as the active product shell, migrate it into a stable architecture, and isolate legacy structures before deleting them.

## 2. Goals

The first frontend refactor phase should achieve these outcomes:

1. Make the active application entry clear.
2. Turn the current `stitch` shell from a temporary merge directory into the recognized main application shell.
3. Reorganize active pages by business capability.
4. Separate shared UI, routing state, providers, and utilities.
5. Isolate unused or superseded frontend structures into `legacy`.
6. Preserve current behavior while making future deletion and optimization safer.

## 3. Non-Goals

This phase does not include:

1. Rewriting the whole frontend routing system to React Router.
2. Rebuilding all pages visually.
3. Rewriting teacher workspace internals.
4. Deleting modules whose reachability or business value is uncertain.
5. Cleaning backend, Python caches, runtime test directories, or repository-level temporary folders.
6. Fixing all existing Chinese text encoding issues.

Those can be handled after the frontend structure is clear.

## 4. Chosen Approach

Use the current `stitch` shell as the mainline.

### 4.1 Why This Approach

This is the lowest-risk first step because:

1. `src/main.tsx` already mounts `src/stitch/App.tsx`.
2. The current frontend build passes.
3. Several active features already depend on `stitch` pages and shared shell helpers.
4. The older `routes/AppRoutes.tsx` path is present but not connected to the runtime entry.

Switching back to React Router immediately would create a larger migration with unclear product benefit in the first phase.

### 4.2 Alternative Approaches Rejected

#### React Router First

This would make the structure more conventional, but it would require reconnecting active `stitch` pages and retesting routing behavior all at once. It is too risky for the first cleanup phase.

#### Full New `src/app + src/features` Rewrite

This would produce the cleanest final shape, but it would mix architecture cleanup with behavior migration. It should happen incrementally, not as a single rewrite.

## 5. Target Frontend Structure

The target first-phase structure is:

```text
frontend/src/
  main.tsx

  app/
    App.tsx
    providers/
      AuthProvider.tsx
      AppShellProvider.tsx
    shell/
      AppSurface.tsx
      SidebarDock.tsx
      SidebarNav.tsx
      ThemeCustomizer.tsx
    routing/
      routes.ts
      routeState.ts

  features/
    home/
      HomeDashboardPage.tsx
      HomeDashboard.css
    courses/
      CourseDetailPage.tsx
      CourseEditPage.tsx
      CourseResourcesPage.tsx
      CourseKnowledgeBasePage.tsx
      api/
      types.ts
    ai-workspace/
      AIWorkspacePage.tsx
      panels/
    knowledge-graph/
      KnowledgeGraphPage.tsx
    teaching-video/
      VideoPlayerPage.tsx
      hooks/
      components/
    ppt/
      PptStudioPage.tsx
    profile/
      ProfilePage.tsx
    auth/
      LoginPage.tsx
      LoginPage.css

  shared/
    api/
      client.ts
      authToken.ts
    ui/
      MaterialIcon.tsx
      MarkdownPreview.tsx
      ProgressBar.tsx
      Badge.tsx
    utils/
      cx.ts
      wordExport.ts

  services/
    teacher/
    rag.ts
    video.ts
    knowledgeBase.ts

  store/
    course/
    teacher/

  legacy/
    routes/
    layout/
    pages/
```

This structure separates application shell, business features, shared utilities, API services, state stores, and legacy code.

## 6. Module Treatment Labels

Every frontend module should receive one of these labels during the refactor:

```text
keep-main      Active mainline code. Keep it and migrate it into the new structure.
keep-shared    Reused by mainline code, but currently in the wrong place. Move to shared or services.
migrate        Valuable behavior in an old structure. Move the behavior, then retire the old entry.
legacy-hold    Uncertain or disconnected code. Move under legacy and prevent new imports.
delete-safe    No active entry, no imports, no business value. Safe to delete.
```

## 7. First-Phase Classification

### 7.1 Keep Main

These are current mainline areas:

1. `src/stitch/App.tsx`
2. `src/stitch/pages/HomeDashboard.tsx`
3. `src/stitch/pages/AIWorkspace.tsx`
4. `src/stitch/pages/CourseResources.tsx`
5. `src/stitch/pages/CourseKnowledgeBase.tsx`
6. `src/stitch/pages/CourseDetail.tsx`
7. `src/stitch/pages/CourseEdit.tsx`
8. `src/stitch/pages/KnowledgeGraph.tsx`
9. `src/stitch/pages/VideoPlayer.tsx`
10. `src/stitch/pages/PptStudio.tsx`
11. `src/stitch/pages/Profile.tsx`
12. `src/stitch/pages/LoginPage.tsx`

These should be migrated into `app` and `features`.

### 7.2 Keep Shared

These are reused by the active mainline but need clearer homes:

1. `src/stitch/shared.tsx`
2. `src/stitch/styles.css`
3. `src/stitch/wordExport.ts`
4. `src/stitch/api/*`
5. `src/stitch/components/MarkdownPreview.tsx`
6. `src/stitch/components/TransparentAvatarCanvas.tsx`
7. `src/stitch/hooks/useAiLecturerWebRtc.ts`

They should be split between `app/shell`, `app/routing`, `shared/ui`, `shared/utils`, and feature-specific folders.

### 7.3 Keep For Now

These files are old in location but active in behavior:

1. `src/components/teacher/*`
2. `src/services/teacher/*`
3. `src/services/rag.ts`
4. `src/services/video.ts`
5. `src/services/knowledgeBase.ts`
6. `src/store/teacher/*`
7. `src/store/course/*`

They are used by the active AI workspace and related course features. They should not be deleted in the first phase. Later phases can split them by feature.

### 7.4 Legacy Hold

These are disconnected from the current entry or represent the older routing model:

1. `src/routes/AppRoutes.tsx`
2. `src/layout/GlobalLayout.tsx`
3. `src/layout/CourseContextLayout.tsx`
4. older standalone pages under `src/pages`
5. older teacher and student pages not reached from the current `stitch` shell

They should be moved into `src/legacy` before any deletion decision.

### 7.5 Delete-Safe Candidates

Delete only after reachability checks and user confirmation:

1. pages with no active route and no imports
2. duplicate test/demo pages outside the current shell
3. placeholder-only student pages that are not connected to current product flow
4. old route wrappers after their useful redirects or behavior have been migrated

## 8. Deletion Rules

A file or directory can be deleted only when all three conditions are true:

1. It is not reachable from `src/main.tsx` through the current app shell.
2. It is not imported by any kept module.
3. Its capability has either been migrated or confirmed as unnecessary.

The first phase should prefer moving uncertain files into `legacy` instead of deleting them.

## 9. Migration Sequence

### Step 1: Create The New Skeleton

Create `app`, `features`, `shared`, and `legacy` without changing behavior.

Move the active application shell from `src/stitch/App.tsx` to `src/app/App.tsx`, and update `src/main.tsx` to import the new path.

### Step 2: Migrate Active Pages

Move active `stitch/pages/*` into `features/*`.

The hash route behavior should remain unchanged during this step.

### Step 3: Split `stitch/shared.tsx`

Split mixed responsibilities:

1. route constants and hash helpers -> `app/routing`
2. shell context provider -> `app/providers`
3. shell UI components -> `app/shell`
4. generic UI helpers -> `shared/ui`
5. `cx` and other pure helpers -> `shared/utils`

This split should be mechanical. Do not rewrite logic while moving it.

### Step 4: Isolate The Old React Router System

Move disconnected route and layout code into `legacy`.

New mainline files must not import from `legacy`.

### Step 5: Verify And Then Delete

After build and reachability checks pass, delete only files that meet the delete rules.

## 10. Acceptance Criteria

First-phase refactor is complete when:

1. `src/main.tsx` imports `src/app/App.tsx`.
2. `src/stitch/App.tsx` is no longer the active shell.
3. Active pages have `features/*` homes.
4. Shared shell and UI utilities are no longer bundled in one large `stitch/shared.tsx`.
5. Disconnected React Router structures are under `legacy`.
6. Mainline code does not import from `legacy`.
7. `cmd /c npm run build` passes from `Edu_AI`.
8. Current hash routes continue to work.
9. Login, home, AI workspace, course resources, knowledge graph, video playback, PPT, and profile remain reachable.

## 11. Verification

Minimum verification for this phase:

```bash
cmd /c npm run build
```

The lint command currently cannot run because ESLint 9 requires `eslint.config.js` and the project does not have one. This is a separate tooling fix and should not block the architecture migration.

After the migration, run import scans to verify:

```bash
rg "from ['\\\"].*legacy|from ['\\\"].*/legacy" frontend/src
rg "src/stitch|\\.\\./stitch|\\./stitch" frontend/src
```

## 12. Risks And Controls

### Risk: Imports Break During File Moves

Control: migrate one group at a time and build after each group.

### Risk: Active Teacher Workspace Code Is Mistaken For Old Code

Control: keep `src/components/teacher`, `src/services/teacher`, and related stores until the AI workspace is decomposed in a later phase.

### Risk: Splitting `shared.tsx` Changes Behavior

Control: split mechanically first. Do not combine moving files with refactoring logic.

### Risk: Chinese Text Encoding Issues Spread

Control: preserve existing strings during this phase. Fix encoding and copy in a separate pass.

### Risk: Bundle Size Remains Large

Control: keep current behavior first. Add route-level lazy loading after the structure is stable.

## 13. Follow-Up Phases

After this phase:

1. Add route-level lazy loading.
2. Create a real ESLint 9 flat config.
3. Decompose `components/teacher/StudioPanel.tsx`, `SourcePanel.tsx`, and `ChatPanel.tsx`.
4. Consolidate duplicate API clients.
5. Delete confirmed `legacy` modules.
6. Run a focused encoding and UX copy cleanup.

## 14. Conclusion

The frontend refactor should begin by making the currently running application understandable. The system should not immediately switch routers or delete large areas of code. Instead, it should promote the active `stitch` shell into `app`, organize business pages under `features`, extract shared utilities, isolate legacy code, and only then delete modules with evidence.

This gives the project a clear architecture without sacrificing the currently working product flow.
