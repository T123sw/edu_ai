# Frontend Architecture Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the active Edu_AI frontend around `src/app`, `src/features`, and `src/shared` while preserving current `stitch` hash-route behavior.

**Architecture:** Keep the currently running `stitch` shell as the behavioral source of truth, then move it into the new architecture. Active pages move to feature folders, shared shell helpers are split into smaller modules, old React Router code is isolated under `legacy`, and deletion happens only after import scans pass.

**Tech Stack:** React 18, Vite 6, TypeScript, Ant Design 5, Zustand, PowerShell on Windows.

---

## File Structure Map

Create or modify these files and directories:

- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/styles.css`
- Create: `frontend/src/app/routing/routes.ts`
- Create: `frontend/src/app/routing/routeState.ts`
- Create: `frontend/src/app/routing/index.ts`
- Create: `frontend/src/app/providers/AppShellProvider.tsx`
- Create: `frontend/src/app/providers/index.ts`
- Create: `frontend/src/app/shell/SidebarDock.tsx`
- Create: `frontend/src/app/shell/SidebarNav.tsx`
- Create: `frontend/src/app/shell/ThemeCustomizer.tsx`
- Create: `frontend/src/app/shell/index.ts`
- Create: `frontend/src/shared/ui/AppSurface.tsx`
- Create: `frontend/src/shared/ui/MaterialIcon.tsx`
- Create: `frontend/src/shared/ui/MarkdownPreview.tsx`
- Create: `frontend/src/shared/ui/ProgressBar.tsx`
- Create: `frontend/src/shared/ui/Badge.tsx`
- Create: `frontend/src/shared/ui/GlassPanel.tsx`
- Create: `frontend/src/shared/ui/SectionHeading.tsx`
- Create: `frontend/src/shared/ui/index.ts`
- Create: `frontend/src/shared/utils/cx.ts`
- Create: `frontend/src/shared/utils/wordExport.ts`
- Create: `frontend/src/shared/utils/index.ts`
- Create: `frontend/src/shared/api/client.ts`
- Create: `frontend/src/shared/api/types.ts`
- Create: `frontend/src/shared/api/courses.ts`
- Create: `frontend/src/shared/api/video.ts`
- Create: `frontend/src/shared/api/chat.ts`
- Create: `frontend/src/shared/api/index.ts`
- Create: `frontend/src/features/home/HomeDashboardPage.tsx`
- Create: `frontend/src/features/home/HomeDashboard.css`
- Create: `frontend/src/features/courses/CourseDetailPage.tsx`
- Create: `frontend/src/features/courses/CourseEditPage.tsx`
- Create: `frontend/src/features/courses/CourseResourcesPage.tsx`
- Create: `frontend/src/features/courses/CourseKnowledgeBasePage.tsx`
- Create: `frontend/src/features/ai-workspace/AIWorkspacePage.tsx`
- Create: `frontend/src/features/ai-workspace/WorkspaceOverviewPage.ts`
- Create: `frontend/src/features/ai-workspace/AIWorkspacePage.css`
- Create: `frontend/src/features/knowledge-graph/KnowledgeGraphPage.tsx`
- Create: `frontend/src/features/teaching-video/VideoPlayerPage.tsx`
- Create: `frontend/src/features/teaching-video/components/TransparentAvatarCanvas.tsx`
- Create: `frontend/src/features/teaching-video/components/TransparentAvatarCanvas.test.ts`
- Create: `frontend/src/features/teaching-video/components/avatarTransparency.ts`
- Create: `frontend/src/features/teaching-video/components/index.ts`
- Create: `frontend/src/features/teaching-video/hooks/useAiLecturerWebRtc.ts`
- Create: `frontend/src/features/ppt/PptStudioPage.tsx`
- Create: `frontend/src/features/profile/ProfilePage.tsx`
- Create: `frontend/src/features/auth/LoginPage.tsx`
- Create: `frontend/src/features/auth/LoginPage.css`
- Create: `frontend/src/features/auth/login-bg.png`
- Create: `frontend/src/legacy/routes/AppRoutes.tsx`
- Create: `frontend/src/legacy/layout/GlobalLayout.tsx`
- Create: `frontend/src/legacy/layout/CourseContextLayout.tsx`
- Create: `frontend/src/legacy/layout/SharedHeader.tsx`
- Create: `frontend/src/legacy/layout/GlobalLayout.css`
- Create directory: `frontend/src/legacy/pages`
- Modify: `frontend/src/main.tsx`
- Modify: active feature files after moving to update import paths
- Delete after replacement: `frontend/src/stitch/App.tsx`
- Delete after replacement: `frontend/src/stitch/shared.tsx`
- Delete after replacement: `frontend/src/stitch/styles.css`
- Delete after replacement: `frontend/src/stitch/wordExport.ts`
- Delete after replacement: `frontend/src/stitch/api/*`
- Delete after replacement: `frontend/src/stitch/components/*`
- Delete after replacement: `frontend/src/stitch/hooks/*`
- Delete after replacement: `frontend/src/stitch/pages/*`

Do not modify these active-but-out-of-scope areas in this phase except for import path fallout caused by moved files:

- `frontend/src/components/teacher/*`
- `frontend/src/components/student/*`
- `frontend/src/services/teacher/*`
- `frontend/src/services/rag.ts`
- `frontend/src/services/video.ts`
- `frontend/src/services/knowledgeBase.ts`
- `frontend/src/store/teacher/*`
- `frontend/src/store/course/*`

Known unrelated working tree files must remain untouched:

- `backend/src/AI_Lecturer.zip`
- `backend/src/rag_v2.zip`
- `backend/src/tests/chat/test_report_edit_numbered_section.py`

---

### Task 1: Baseline Verification And Safety Snapshot

**Files:**
- Read: `frontend/src/main.tsx`
- Read: `frontend/src/stitch/App.tsx`
- Read: `frontend/src/stitch/shared.tsx`
- Read: `docs/superpowers/specs/2026-05-06-frontend-architecture-refactor-design-cn.md`
- Modify: none

- [ ] **Step 1: Confirm the working tree has only expected unrelated untracked files**

Run:

```powershell
git status --short
```

Expected: the output may include the three known untracked backend files listed above. It must not include frontend changes from earlier attempts.

- [ ] **Step 2: Confirm the current frontend builds before moving files**

Run from `Edu_AI`:

```powershell
cmd /c npm run build
```

Expected: Vite build succeeds. The existing large chunk warning is acceptable.

- [ ] **Step 3: Record current active `stitch` references**

Run:

```powershell
rg "src/stitch|\\.\\./stitch|\\./stitch|stitch/" frontend/src
```

Expected: references include `src/main.tsx` importing `./stitch/App` and `./stitch/styles.css`. Later tasks remove these references.

- [ ] **Step 4: Commit no changes**

No commit is needed for this read-only task.

---

### Task 2: Move The Active App Shell Into `src/app`

**Files:**
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/styles.css`
- Modify: `frontend/src/main.tsx`
- Delete after move: `frontend/src/stitch/App.tsx`
- Delete after move: `frontend/src/stitch/styles.css`

- [ ] **Step 1: Move shell files with Git**

Run:

```powershell
New-Item -ItemType Directory -Force frontend/src/app | Out-Null
git mv frontend/src/stitch/App.tsx frontend/src/app/App.tsx
git mv frontend/src/stitch/styles.css frontend/src/app/styles.css
```

Expected: `frontend/src/app/App.tsx` and `frontend/src/app/styles.css` exist, and the old files are staged as renames.

- [ ] **Step 2: Update `main.tsx` imports**

Change `frontend/src/main.tsx` to:

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './app/App';
import { AuthProvider } from './context/AuthContext';
import './app/styles.css';

const container = document.getElementById('root');

if (!container) {
  throw new Error("Root element '#root' was not found.");
}

createRoot(container).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
);
```

- [ ] **Step 3: Update temporary relative imports in `app/App.tsx`**

Because pages and shared helpers are still in `src/stitch` after this task, update these imports:

```tsx
import { WorkspaceOverviewPage } from "../stitch/pages/WorkspaceOverview";
import { VideoPlayerPage } from "../stitch/pages/VideoPlayer";
import { CourseResourcesPage } from "../stitch/pages/CourseResources";
import { AIWorkspacePage } from "../stitch/pages/AIWorkspace";
import { HomeDashboardPage } from "../stitch/pages/HomeDashboard";
import { KnowledgeGraphPage } from "../stitch/pages/KnowledgeGraph";
import { PptStudioPage } from "../stitch/pages/PptStudio";
import { CourseKnowledgeBasePage } from "../stitch/pages/CourseKnowledgeBase";
import { CourseDetailPage, CourseListPage } from "../stitch/pages/CourseDetail";
import { CourseEditPage } from "../stitch/pages/CourseEdit";
import { ProfilePage } from "../stitch/pages/Profile";
import { LoginPage } from "../stitch/pages/LoginPage";
```

Also change the shared import to:

```tsx
} from "../stitch/shared";
```

And change the auth import to:

```tsx
import { login, verifyToken, type User } from "../services/auth";
```

- [ ] **Step 4: Build after moving the shell**

Run from `Edu_AI`:

```powershell
cmd /c npm run build
```

Expected: build succeeds.

- [ ] **Step 5: Commit the shell move**

Run:

```powershell
git add frontend/src/main.tsx frontend/src/app/App.tsx frontend/src/app/styles.css
git commit -m "refactor(frontend): move active app shell"
```

Expected: one commit containing only the shell move and `main.tsx` import update.

---

### Task 3: Extract Routing And AppShell Provider From `stitch/shared.tsx`

**Files:**
- Create: `frontend/src/app/routing/routes.ts`
- Create: `frontend/src/app/routing/routeState.ts`
- Create: `frontend/src/app/routing/index.ts`
- Create: `frontend/src/app/providers/AppShellProvider.tsx`
- Create: `frontend/src/app/providers/index.ts`
- Modify: `frontend/src/app/App.tsx`
- Modify later import paths in files that currently import route or provider exports from `../shared`

- [ ] **Step 1: Create routing constants**

Run:

```powershell
New-Item -ItemType Directory -Force frontend/src/app/routing,frontend/src/app/providers | Out-Null
```

Create `frontend/src/app/routing/routes.ts`:

```ts
export const routes = {
  workspace: "workspace",
  course: "course",
  courseDetail: "course-detail",
  video: "video",
  ai: "ai",
  home: "home",
  profile: "profile",
  graph: "graph",
  ppt: "ppt",
  resources: "resources",
  knowledge: "knowledge",
  edit: "edit",
} as const;

export type RouteKey = (typeof routes)[keyof typeof routes];
export type ThemeName = "ocean" | "forest" | "sunset" | "dark";

export function routeHref(route: RouteKey) {
  return `#${route}`;
}
```

- [ ] **Step 2: Create route state helpers**

Create `frontend/src/app/routing/routeState.ts`:

```ts
import { routes, type RouteKey, type ThemeName } from "./routes";
import { defaultCourse, type CourseSummary } from "../providers/AppShellProvider";

export function getCurrentRoute(pages: ReadonlyArray<readonly [RouteKey, string, unknown]>): RouteKey {
  const hash = window.location.hash.replace(/^#/, "");
  const route = hash.split("?")[0] as RouteKey;
  return pages.some(([id]) => id === route) ? route : routes.home;
}

export function getStoredTheme(): ThemeName {
  const stored = window.localStorage.getItem("stitch-theme");
  return stored === "forest" || stored === "sunset" || stored === "dark" ? stored : "ocean";
}

export function getStoredCourse(): CourseSummary | null {
  const raw = window.localStorage.getItem("stitch-course");

  if (!raw) return defaultCourse;

  try {
    return JSON.parse(raw) as CourseSummary;
  } catch {
    return defaultCourse;
  }
}

export function resetRouteScrollPosition() {
  window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
  document.querySelectorAll("[data-route-scroll-root]").forEach((element) => {
    if (element instanceof HTMLElement) {
      element.scrollTop = 0;
      element.scrollLeft = 0;
    }
  });
}
```

- [ ] **Step 3: Create routing barrel**

Create `frontend/src/app/routing/index.ts`:

```ts
export * from "./routes";
export * from "./routeState";
```

- [ ] **Step 4: Create AppShell provider**

Create `frontend/src/app/providers/AppShellProvider.tsx` by moving these exact exports and types from `frontend/src/stitch/shared.tsx` without changing behavior:

```text
CourseSummary
defaultCourse
AppShellProvider
useAppShell
```

Use this import header:

```tsx
import {
  createContext,
  useContext,
  useMemo,
  type PropsWithChildren,
} from "react";
import type { ThemeName } from "../routing/routes";
```

Keep the current `defaultCourse` values exactly as they exist, including existing encoded text.

- [ ] **Step 5: Create provider barrel**

Create `frontend/src/app/providers/index.ts`:

```ts
export * from "./AppShellProvider";
```

- [ ] **Step 6: Update `app/App.tsx` to use the new modules**

Replace the imports for `AppShellProvider`, `defaultCourse`, `routeHref`, `routes`, `CourseSummary`, `RouteKey`, and `ThemeName`.

Use:

```tsx
import { AppShellProvider, type CourseSummary } from "./providers";
import {
  getCurrentRoute,
  getStoredCourse,
  getStoredTheme,
  resetRouteScrollPosition,
  routeHref,
  routes,
  type RouteKey,
  type ThemeName,
} from "./routing";
import { ThemeCustomizer } from "../stitch/shared";
```

Remove the local definitions of `getCurrentRoute`, `getStoredTheme`, `getStoredCourse`, and `resetRouteScrollPosition` from `app/App.tsx`.

Change the route state initializer to:

```tsx
const [current, setCurrent] = useState<RouteKey>(() => getCurrentRoute(pages));
```

Change the hash sync callback to:

```tsx
const syncRoute = () => setCurrent(getCurrentRoute(pages));
```

- [ ] **Step 7: Build after extracting routing/provider code**

Run from `Edu_AI`:

```powershell
cmd /c npm run build
```

Expected: build succeeds.

- [ ] **Step 8: Commit routing and provider extraction**

Run:

```powershell
git add frontend/src/app
git commit -m "refactor(frontend): extract app routing and provider"
```

Expected: one commit containing `app/routing`, `app/providers`, and `app/App.tsx` changes.

---

### Task 4: Extract Shared UI And Shell Components

**Files:**
- Create: `frontend/src/shared/utils/cx.ts`
- Create: `frontend/src/shared/utils/index.ts`
- Create: `frontend/src/shared/ui/MaterialIcon.tsx`
- Create: `frontend/src/shared/ui/AppSurface.tsx`
- Create: `frontend/src/shared/ui/GlassPanel.tsx`
- Create: `frontend/src/shared/ui/SectionHeading.tsx`
- Create: `frontend/src/shared/ui/ProgressBar.tsx`
- Create: `frontend/src/shared/ui/Badge.tsx`
- Create: `frontend/src/shared/ui/index.ts`
- Create: `frontend/src/app/shell/SidebarDock.tsx`
- Create: `frontend/src/app/shell/SidebarNav.tsx`
- Create: `frontend/src/app/shell/ThemeCustomizer.tsx`
- Create: `frontend/src/app/shell/index.ts`
- Modify: files that still import these exports from `src/stitch/shared.tsx`

- [ ] **Step 1: Create `cx` utility**

Run:

```powershell
New-Item -ItemType Directory -Force frontend/src/shared/utils,frontend/src/shared/ui,frontend/src/app/shell | Out-Null
```

Create `frontend/src/shared/utils/cx.ts`:

```ts
export function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}
```

Create `frontend/src/shared/utils/index.ts`:

```ts
export * from "./cx";
```

- [ ] **Step 2: Create `MaterialIcon`**

Create `frontend/src/shared/ui/MaterialIcon.tsx` by moving the existing `MaterialIcon` implementation from `frontend/src/stitch/shared.tsx`.

Use this import:

```tsx
import { cx } from "../utils";
```

Do not change the `iconGlyphs` map in this phase.

- [ ] **Step 3: Create generic UI files**

Move these exports from `frontend/src/stitch/shared.tsx` into separate files:

```text
AppSurface -> frontend/src/shared/ui/AppSurface.tsx
GlassPanel -> frontend/src/shared/ui/GlassPanel.tsx
SectionHeading -> frontend/src/shared/ui/SectionHeading.tsx
ProgressBar -> frontend/src/shared/ui/ProgressBar.tsx
Badge -> frontend/src/shared/ui/Badge.tsx
```

Each file should import only what it needs:

```tsx
import type { PropsWithChildren, ReactNode } from "react";
import { cx } from "../utils";
```

For files that render `MaterialIcon`, import it from:

```tsx
import { MaterialIcon } from "./MaterialIcon";
```

- [ ] **Step 4: Create shared UI barrel**

Create `frontend/src/shared/ui/index.ts`:

```ts
export * from "./AppSurface";
export * from "./Badge";
export * from "./GlassPanel";
export * from "./MaterialIcon";
export * from "./ProgressBar";
export * from "./SectionHeading";
```

- [ ] **Step 5: Create shell files**

Move these exports from `frontend/src/stitch/shared.tsx`:

```text
SidebarDock -> frontend/src/app/shell/SidebarDock.tsx
SidebarLink and SidebarNav -> frontend/src/app/shell/SidebarNav.tsx
SidebarBackLink -> frontend/src/app/shell/SidebarNav.tsx
ThemeCustomizer -> frontend/src/app/shell/ThemeCustomizer.tsx
```

Use these imports in shell files:

```tsx
import { useState, type PropsWithChildren } from "react";
import { routeHref, routes, type RouteKey, type ThemeName } from "../routing";
import { useAppShell } from "../providers";
import { MaterialIcon } from "../../shared/ui";
import { cx } from "../../shared/utils";
```

Keep the current sidebar labels, theme labels, and encoded strings unchanged.

- [ ] **Step 6: Create shell barrel**

Create `frontend/src/app/shell/index.ts`:

```ts
export * from "./SidebarDock";
export * from "./SidebarNav";
export * from "./ThemeCustomizer";
```

- [ ] **Step 7: Update imports from `../shared` in active pages**

Use these replacements:

```text
AppSurface, GlassPanel, MaterialIcon, ProgressBar, SectionHeading, Badge -> shared/ui
SidebarDock, SidebarNav, SidebarBackLink, ThemeCustomizer -> app/shell
routeHref, routes, RouteKey, ThemeName -> app/routing
useAppShell -> app/providers
```

For pages still under `src/stitch/pages`, example imports should look like:

```tsx
import { AppSurface, GlassPanel, MaterialIcon } from "../../shared/ui";
import { SidebarBackLink, SidebarDock, SidebarNav } from "../../app/shell";
import { routeHref, routes } from "../../app/routing";
import { useAppShell } from "../../app/providers";
```

In `frontend/src/app/App.tsx`, replace:

```tsx
import { ThemeCustomizer } from "../stitch/shared";
```

with:

```tsx
import { ThemeCustomizer } from "./shell";
```

- [ ] **Step 8: Build after shared UI extraction**

Run from `Edu_AI`:

```powershell
cmd /c npm run build
```

Expected: build succeeds.

- [ ] **Step 9: Commit shared UI and shell extraction**

Run:

```powershell
git add frontend/src/app frontend/src/shared frontend/src/stitch
git commit -m "refactor(frontend): extract shared shell UI"
```

Expected: one commit with new shared UI and shell modules plus import updates.

---

### Task 5: Move Shared API, Markdown, Video Support, And Word Export

**Files:**
- Create: `frontend/src/shared/api/client.ts`
- Create: `frontend/src/shared/api/types.ts`
- Create: `frontend/src/shared/api/courses.ts`
- Create: `frontend/src/shared/api/video.ts`
- Create: `frontend/src/shared/api/chat.ts`
- Create: `frontend/src/shared/api/index.ts`
- Create: `frontend/src/shared/ui/MarkdownPreview.tsx`
- Create: `frontend/src/shared/utils/wordExport.ts`
- Create: `frontend/src/features/teaching-video/components/TransparentAvatarCanvas.tsx`
- Create: `frontend/src/features/teaching-video/components/TransparentAvatarCanvas.test.ts`
- Create: `frontend/src/features/teaching-video/components/avatarTransparency.ts`
- Create: `frontend/src/features/teaching-video/components/index.ts`
- Create: `frontend/src/features/teaching-video/hooks/useAiLecturerWebRtc.ts`
- Delete after move: `frontend/src/stitch/api/*`
- Delete after move: `frontend/src/stitch/components/*`
- Delete after move: `frontend/src/stitch/hooks/*`
- Delete after move: `frontend/src/stitch/wordExport.ts`

- [ ] **Step 1: Move API files**

Run:

```powershell
New-Item -ItemType Directory -Force frontend/src/shared/api | Out-Null
git mv frontend/src/stitch/api/client.ts frontend/src/shared/api/client.ts
git mv frontend/src/stitch/api/types.ts frontend/src/shared/api/types.ts
git mv frontend/src/stitch/api/courses.ts frontend/src/shared/api/courses.ts
git mv frontend/src/stitch/api/video.ts frontend/src/shared/api/video.ts
git mv frontend/src/stitch/api/chat.ts frontend/src/shared/api/chat.ts
```

- [ ] **Step 2: Update `shared/api/courses.ts` CourseSummary import**

Replace:

```ts
import type { CourseSummary } from "../shared";
```

With:

```ts
import type { CourseSummary } from "../../app/providers";
```

Internal imports such as `./client` and `./types` stay unchanged.

- [ ] **Step 3: Create API barrel**

Create `frontend/src/shared/api/index.ts`:

```ts
export * from "./client";
export * from "./types";
export * from "./courses";
export * from "./video";
export * from "./chat";
```

- [ ] **Step 4: Move Markdown preview**

Run:

```powershell
git mv frontend/src/stitch/components/MarkdownPreview.tsx frontend/src/shared/ui/MarkdownPreview.tsx
```

Add this line to `frontend/src/shared/ui/index.ts`:

```ts
export * from "./MarkdownPreview";
```

- [ ] **Step 5: Move teaching video support components**

Run:

```powershell
New-Item -ItemType Directory -Force frontend/src/features/teaching-video/components,frontend/src/features/teaching-video/hooks | Out-Null
git mv frontend/src/stitch/components/TransparentAvatarCanvas.tsx frontend/src/features/teaching-video/components/TransparentAvatarCanvas.tsx
git mv frontend/src/stitch/components/TransparentAvatarCanvas.test.ts frontend/src/features/teaching-video/components/TransparentAvatarCanvas.test.ts
git mv frontend/src/stitch/components/avatarTransparency.ts frontend/src/features/teaching-video/components/avatarTransparency.ts
git mv frontend/src/stitch/hooks/useAiLecturerWebRtc.ts frontend/src/features/teaching-video/hooks/useAiLecturerWebRtc.ts
```

Create `frontend/src/features/teaching-video/components/index.ts`:

```ts
export * from "./TransparentAvatarCanvas";
```

In `frontend/src/features/teaching-video/hooks/useAiLecturerWebRtc.ts`, replace:

```ts
import { getAiLecturerOfferUrl } from "../api/video";
import type { AiLecturerOfferAnswer } from "../api/types";
```

With:

```ts
import { getAiLecturerOfferUrl } from "../../../shared/api/video";
import type { AiLecturerOfferAnswer } from "../../../shared/api/types";
```

- [ ] **Step 6: Move word export utility**

Run:

```powershell
git mv frontend/src/stitch/wordExport.ts frontend/src/shared/utils/wordExport.ts
```

In `frontend/src/shared/utils/wordExport.ts`, replace:

```ts
import { API_BASE_URL } from "./api/client";
import type { CourseMaterial } from "./api/types";
```

with:

```ts
import { API_BASE_URL } from "../api/client";
import type { CourseMaterial } from "../api/types";
```

Ensure `frontend/src/shared/utils/index.ts` contains:

```ts
export * from "./cx";
export * from "./wordExport";
```

- [ ] **Step 7: Update active imports for moved API and support files**

Use this replacement table:

```text
../api/courses -> ../../shared/api/courses
../api/video -> ../../shared/api/video
../api/client -> ../../shared/api/client
../api/types -> ../../shared/api/types
../components/MarkdownPreview -> ../../shared/ui
../components/TransparentAvatarCanvas -> ../../features/teaching-video/components
../hooks/useAiLecturerWebRtc -> ../../features/teaching-video/hooks/useAiLecturerWebRtc
../wordExport -> ../../shared/utils/wordExport
```

For files still under `src/stitch/pages`, the `../../shared/...` paths are correct.

- [ ] **Step 8: Build after moving API and support files**

Run from `Edu_AI`:

```powershell
cmd /c npm run build
```

Expected: build succeeds.

- [ ] **Step 9: Commit shared API and support moves**

Run:

```powershell
git add frontend/src/shared frontend/src/features/teaching-video frontend/src/stitch
git commit -m "refactor(frontend): move shared api and video support"
```

Expected: one commit with API, Markdown, video support, and word export relocation.

---

### Task 6: Move Active Pages Into `src/features`

**Files:**
- Create: `frontend/src/features/home/HomeDashboardPage.tsx`
- Create: `frontend/src/features/home/HomeDashboard.css`
- Create: `frontend/src/features/courses/CourseDetailPage.tsx`
- Create: `frontend/src/features/courses/CourseEditPage.tsx`
- Create: `frontend/src/features/courses/CourseResourcesPage.tsx`
- Create: `frontend/src/features/courses/CourseKnowledgeBasePage.tsx`
- Create: `frontend/src/features/ai-workspace/AIWorkspacePage.tsx`
- Create: `frontend/src/features/ai-workspace/WorkspaceOverviewPage.ts`
- Create: `frontend/src/features/ai-workspace/AIWorkspacePage.css`
- Create: `frontend/src/features/knowledge-graph/KnowledgeGraphPage.tsx`
- Create: `frontend/src/features/teaching-video/VideoPlayerPage.tsx`
- Create: `frontend/src/features/ppt/PptStudioPage.tsx`
- Create: `frontend/src/features/profile/ProfilePage.tsx`
- Create: `frontend/src/features/auth/LoginPage.tsx`
- Create: `frontend/src/features/auth/LoginPage.css`
- Create: `frontend/src/features/auth/login-bg.png`
- Modify: `frontend/src/app/App.tsx`
- Delete after move: `frontend/src/stitch/pages/*`
- Delete after move: `frontend/src/stitch/login-bg.png`
- Move: `frontend/src/pages/teacher/AiStudioPage.css` to `frontend/src/features/ai-workspace/AIWorkspacePage.css`

- [ ] **Step 1: Move page files**

Run:

```powershell
New-Item -ItemType Directory -Force frontend/src/features/home,frontend/src/features/courses,frontend/src/features/ai-workspace,frontend/src/features/knowledge-graph,frontend/src/features/teaching-video,frontend/src/features/ppt,frontend/src/features/profile,frontend/src/features/auth | Out-Null
git mv frontend/src/stitch/pages/HomeDashboard.tsx frontend/src/features/home/HomeDashboardPage.tsx
git mv frontend/src/stitch/pages/HomeDashboard.css frontend/src/features/home/HomeDashboard.css
git mv frontend/src/stitch/pages/CourseDetail.tsx frontend/src/features/courses/CourseDetailPage.tsx
git mv frontend/src/stitch/pages/CourseEdit.tsx frontend/src/features/courses/CourseEditPage.tsx
git mv frontend/src/stitch/pages/CourseResources.tsx frontend/src/features/courses/CourseResourcesPage.tsx
git mv frontend/src/stitch/pages/CourseKnowledgeBase.tsx frontend/src/features/courses/CourseKnowledgeBasePage.tsx
git mv frontend/src/stitch/pages/AIWorkspace.tsx frontend/src/features/ai-workspace/AIWorkspacePage.tsx
git mv frontend/src/stitch/pages/WorkspaceOverview.tsx frontend/src/features/ai-workspace/WorkspaceOverviewPage.ts
git mv frontend/src/pages/teacher/AiStudioPage.css frontend/src/features/ai-workspace/AIWorkspacePage.css
git mv frontend/src/stitch/pages/KnowledgeGraph.tsx frontend/src/features/knowledge-graph/KnowledgeGraphPage.tsx
git mv frontend/src/stitch/pages/VideoPlayer.tsx frontend/src/features/teaching-video/VideoPlayerPage.tsx
git mv frontend/src/stitch/pages/PptStudio.tsx frontend/src/features/ppt/PptStudioPage.tsx
git mv frontend/src/stitch/pages/Profile.tsx frontend/src/features/profile/ProfilePage.tsx
git mv frontend/src/stitch/pages/LoginPage.tsx frontend/src/features/auth/LoginPage.tsx
git mv frontend/src/stitch/pages/LoginPage.css frontend/src/features/auth/LoginPage.css
git mv frontend/src/stitch/login-bg.png frontend/src/features/auth/login-bg.png
```

- [ ] **Step 2: Fix page-local CSS imports**

In `frontend/src/features/home/HomeDashboardPage.tsx`, replace:

```tsx
import "./HomeDashboard.css";
```

with the same line. The file moved with its CSS, so the import remains valid.

In `frontend/src/features/auth/LoginPage.tsx`, keep:

```tsx
import "./LoginPage.css";
```

In `frontend/src/features/auth/LoginPage.css`, replace:

```css
url("../login-bg.png") center/cover no-repeat;
```

with:

```css
url("./login-bg.png") center/cover no-repeat;
```

In `frontend/src/features/ai-workspace/AIWorkspacePage.tsx`, replace:

```tsx
import "../../pages/teacher/AiStudioPage.css";
```

with:

```tsx
import "./AIWorkspacePage.css";
```

- [ ] **Step 3: Update feature imports to shared modules**

Because pages moved out of `src/stitch/pages`, use these paths:

```text
../../shared/api/courses
../../shared/api/video
../../shared/api/client
../../shared/api/types
../../shared/ui
../../shared/utils/wordExport
../../app/routing
../../app/providers
../../app/shell
```

For `AIWorkspacePage.tsx`, teacher workspace imports become:

```tsx
import SourcePanel from "../../components/teacher/SourcePanel";
import ChatPanel from "../../components/teacher/ChatPanel";
import StudioPanel from "../../components/teacher/StudioPanel";
import { useStore } from "../../store/teacher/useStore";
```

These stay correct from `src/features/ai-workspace`.

- [ ] **Step 4: Update teaching video imports**

In `frontend/src/features/teaching-video/VideoPlayerPage.tsx`, use:

```tsx
import { MarkdownPreview } from "../../shared/ui";
import { TransparentAvatarCanvas } from "./components";
import { useAiLecturerWebRtc } from "./hooks/useAiLecturerWebRtc";
```

Use shared API imports:

```tsx
import { API_BASE_URL } from "../../shared/api/client";
```

And import word export helpers from:

```tsx
import {
  exportCourseMaterialAsWord,
  getCourseMaterialPptExportUrl,
  getCourseMaterialPptPreviewUrl,
  isCourseMaterialWordExportable,
} from "../../shared/utils/wordExport";
```

- [ ] **Step 5: Update `app/App.tsx` page imports**

Replace all temporary `../stitch/pages/...` imports with:

```tsx
import { WorkspaceOverviewPage } from "../features/ai-workspace/WorkspaceOverviewPage";
import { VideoPlayerPage } from "../features/teaching-video/VideoPlayerPage";
import { CourseResourcesPage } from "../features/courses/CourseResourcesPage";
import { AIWorkspacePage } from "../features/ai-workspace/AIWorkspacePage";
import { HomeDashboardPage } from "../features/home/HomeDashboardPage";
import { KnowledgeGraphPage } from "../features/knowledge-graph/KnowledgeGraphPage";
import { PptStudioPage } from "../features/ppt/PptStudioPage";
import { CourseKnowledgeBasePage } from "../features/courses/CourseKnowledgeBasePage";
import { CourseDetailPage, CourseListPage } from "../features/courses/CourseDetailPage";
import { CourseEditPage } from "../features/courses/CourseEditPage";
import { ProfilePage } from "../features/profile/ProfilePage";
import { LoginPage } from "../features/auth/LoginPage";
```

- [ ] **Step 6: Update workspace overview alias**

In `frontend/src/features/ai-workspace/WorkspaceOverviewPage.ts`, replace the old relative export with:

```ts
export { AIWorkspacePage as WorkspaceOverviewPage } from "./AIWorkspacePage";
```

- [ ] **Step 7: Build after moving active pages**

Run from `Edu_AI`:

```powershell
cmd /c npm run build
```

Expected: build succeeds.

- [ ] **Step 8: Commit active page moves**

Run:

```powershell
git add frontend/src/app frontend/src/features frontend/src/stitch frontend/src/pages
git commit -m "refactor(frontend): move active pages into features"
```

Expected: one commit with active page relocation and import updates.

---

### Task 7: Move Disconnected Routes, Layouts, And Old Pages Into `legacy`

**Files:**
- Create: `frontend/src/legacy/routes/AppRoutes.tsx`
- Create: `frontend/src/legacy/layout/*`
- Create: `frontend/src/legacy/pages/*`
- Delete after move: `frontend/src/routes/*`
- Delete after move: `frontend/src/layout/*`
- Delete after move: old files under `frontend/src/pages/*`

- [ ] **Step 1: Move disconnected route and layout folders**

Run:

```powershell
New-Item -ItemType Directory -Force frontend/src/legacy | Out-Null
git mv frontend/src/routes frontend/src/legacy/routes
git mv frontend/src/layout frontend/src/legacy/layout
```

- [ ] **Step 2: Move remaining old pages**

Run:

```powershell
git mv frontend/src/pages frontend/src/legacy/pages
```

This must happen only after Task 6 has moved `src/pages/teacher/AiStudioPage.css` into `src/features/ai-workspace/AIWorkspacePage.css`.

- [ ] **Step 3: Check for mainline imports from legacy**

Run:

```powershell
rg "from ['\\\"].*legacy|from ['\\\"].*/legacy" frontend/src/app frontend/src/features frontend/src/shared frontend/src/components frontend/src/services frontend/src/store
```

Expected: no output.

- [ ] **Step 4: Check for broken old page references**

Run:

```powershell
rg "pages/teacher|pages/student|\\.\\./pages|\\.\\./\\.\\./pages" frontend/src/app frontend/src/features frontend/src/shared frontend/src/components frontend/src/services frontend/src/store
```

Expected: no output.

- [ ] **Step 5: Build after legacy isolation**

Run from `Edu_AI`:

```powershell
cmd /c npm run build
```

Expected: build succeeds.

- [ ] **Step 6: Commit legacy isolation**

Run:

```powershell
git add frontend/src
git commit -m "refactor(frontend): isolate legacy route pages"
```

Expected: one commit moving old route, layout, and pages into `src/legacy`.

---

### Task 8: Remove Empty `stitch` Directory And Verify New Architecture

**Files:**
- Delete if empty: `frontend/src/stitch`
- Modify: none unless import scans reveal missed references

- [ ] **Step 1: Check for remaining `stitch` references**

Run:

```powershell
rg "src/stitch|\\.\\./stitch|\\./stitch|stitch/" frontend/src
```

Expected: no output.

- [ ] **Step 2: Check for remaining files under `src/stitch`**

Run:

```powershell
Get-ChildItem frontend/src/stitch -Recurse -Force
```

Expected: either the directory does not exist, or it contains no files.

- [ ] **Step 3: Remove empty `src/stitch` directory if it still exists**

Run this only if Step 2 shows an empty directory:

```powershell
Remove-Item -LiteralPath frontend/src/stitch -Force
```

Expected: `frontend/src/stitch` no longer exists.

- [ ] **Step 4: Run final build**

Run from `Edu_AI`:

```powershell
cmd /c npm run build
```

Expected: build succeeds. The large chunk warning is acceptable.

- [ ] **Step 5: Run final import scans**

Run:

```powershell
rg "from ['\\\"].*legacy|from ['\\\"].*/legacy" frontend/src/app frontend/src/features frontend/src/shared frontend/src/components frontend/src/services frontend/src/store
rg "src/stitch|\\.\\./stitch|\\./stitch|stitch/" frontend/src
```

Expected: both commands produce no output.

- [ ] **Step 6: Commit final cleanup**

Run:

```powershell
git add frontend/src
git commit -m "refactor(frontend): remove stitch shell leftovers"
```

Expected: one commit removing empty `stitch` leftovers and any final import fixes.

---

### Task 9: Final Review Notes

**Files:**
- Read: `docs/superpowers/specs/2026-05-06-frontend-architecture-refactor-design-cn.md`
- Read: `docs/superpowers/plans/2026-05-06-frontend-architecture-refactor.md`
- Modify: none

- [ ] **Step 1: Confirm spec acceptance criteria**

Check these outcomes:

```text
src/main.tsx imports src/app/App.tsx
active pages live under src/features
shared shell helpers no longer live in src/stitch/shared.tsx
old routes/layout/pages live under src/legacy
mainline code does not import from legacy
mainline code does not import from stitch
cmd /c npm run build passes
```

- [ ] **Step 2: Report known deferred items**

Include these deferred items in the implementation final answer:

```text
ESLint 9 flat config is still missing
route-level lazy loading is still deferred
teacher workspace panel decomposition is still deferred
API client consolidation beyond moved stitch API files is still deferred
Chinese text encoding cleanup is still deferred
```

- [ ] **Step 3: Do not commit unrelated files**

Run:

```powershell
git status --short
```

Expected: no frontend refactor changes remain unstaged. The known unrelated backend untracked files may still appear.

No commit is needed for this read-only review task.
