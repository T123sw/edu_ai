# Stitch Course Resources Teaching Video Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let completed teaching-video artifacts in the teacher workbench jump into the stitch course-resources page and auto-open an in-page video player for the matching course material.

**Architecture:** Keep the backend contract unchanged and finish the feature entirely in the frontend. The teacher workbench will navigate with `#resources?courseId=...&materialId=...`, the stitch shell will stop redirecting `resources`, and the stitch course-resources page will restore course context, select the requested material, and render a dedicated `video` detail branch.

**Tech Stack:** React, TypeScript, hash-based stitch routing, existing teacher workbench store/state, Node built-in text-regex tests (`node --test`)

---

## File Map

- Modify: `frontend/src/components/teacher/StudioPanel.tsx`
  - Change video artifact click behavior so only completed teaching videos navigate to stitch resources.
- Modify: `frontend/tests/frontend/studioPanel.teaching-video-entry.test.ts`
  - Extend the existing text-level assertions for the new jump behavior.
- Modify: `frontend/src/stitch/App.tsx`
  - Register `resources` as a real stitch route and stop redirecting it to `video`.
- Create: `frontend/tests/frontend/stitchApp.resources-route.test.ts`
  - Lock the stitch route behavior with a text-level route test.
- Modify: `frontend/src/stitch/api/courses.ts`
  - Reuse `getCourse()` from stitch API and add any small helper needed for course-summary restoration.
- Modify: `frontend/src/stitch/api/types.ts`
  - Expand stitch `CourseMaterial` typing to include `video`-specific payload fields used by the detail page.
- Modify: `frontend/src/stitch/pages/CourseResources.tsx`
  - Parse hash query params, restore course context from `courseId`, select `materialId`, and render a dedicated video detail view.
- Create: `frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts`
  - Lock parameter parsing, `video` type labels, and `<video>` detail rendering with text-level assertions.

## Task 1: Restore Stitch `resources` Route

**Files:**
- Modify: `frontend/src/stitch/App.tsx`
- Test: `frontend/tests/frontend/stitchApp.resources-route.test.ts`

- [ ] **Step 1: Write the failing route test**

Create `frontend/tests/frontend/stitchApp.resources-route.test.ts` with:

```ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const stitchApp = readFileSync(new URL("../../src/stitch/App.tsx", import.meta.url), "utf8");

assert.match(
  stitchApp,
  /\[routes\.resources,\s*["'][^"']+["'],\s*CourseResourcesPage\]/,
  "Stitch App should register CourseResourcesPage for the resources route",
);

assert.doesNotMatch(
  stitchApp,
  /if\s*\(route\s*===\s*routes\.resources\)\s*\{[\s\S]*routeHref\(routes\.video\)/,
  "Stitch App should not redirect the resources route to the video route",
);

console.log("stitchApp.resources-route tests passed");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/frontend/stitchApp.resources-route.test.ts`

Expected: FAIL because `CourseResourcesPage` is not registered in `pages` and `getCurrentRoute()` still redirects `resources` to `video`.

- [ ] **Step 3: Write minimal implementation**

Update `frontend/src/stitch/App.tsx`:

```ts
import { CourseResourcesPage } from "./pages/CourseResources";

const pages = [
  [routes.profile, "Profile", ProfilePage],
  [routes.home, "首页", HomeDashboardPage],
  [routes.course, "课程详情", CourseDetailPage],
  [routes.workspace, "课程工作台", WorkspaceOverviewPage],
  [routes.video, "视频学习", VideoPlayerPage],
  [routes.ai, "AI 问答", AIWorkspacePage],
  [routes.graph, "知识图谱", KnowledgeGraphPage],
  [routes.ppt, "PPT 工作室", PptStudioPage],
  [routes.resources, "课程资料", CourseResourcesPage],
  [routes.knowledge, "课程知识库", CourseKnowledgeBasePage],
  [routes.edit, "详情编辑", CourseEditPage],
] as const;

function getCurrentRoute(): RouteKey {
  const hash = window.location.hash.replace(/^#/, "");
  const route = hash.split("?")[0] as RouteKey;
  return pages.some(([id]) => id === route) ? route : routes.home;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test frontend/tests/frontend/stitchApp.resources-route.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stitch/App.tsx frontend/tests/frontend/stitchApp.resources-route.test.ts
git commit -m "feat: enable stitch resources route"
```

## Task 2: Make Completed Workbench Videos Jump to Stitch Resources

**Files:**
- Modify: `frontend/src/components/teacher/StudioPanel.tsx`
- Modify: `frontend/tests/frontend/studioPanel.teaching-video-entry.test.ts`

- [ ] **Step 1: Write the failing test**

Append these assertions to `frontend/tests/frontend/studioPanel.teaching-video-entry.test.ts`:

```ts
assert.match(
  studioPanel,
  /window\.location\.hash\s*=\s*`#resources\?courseId=\$\{encodeURIComponent\(courseId\)\}&materialId=\$\{encodeURIComponent\(item\.id\)\}`/,
  "StudioPanel should jump completed teaching videos into stitch resources with courseId and materialId",
);

assert.match(
  studioPanel,
  /if\s*\(item\.type\s*===\s*'video'\)[\s\S]*generationState[\s\S]*status\s*===\s*'completed'/,
  "StudioPanel should gate stitch navigation on completed video status",
);

assert.match(
  studioPanel,
  /status\s*===\s*'processing'[\s\S]*message\.(info|warning)\(/,
  "StudioPanel should keep processing teaching videos in a non-navigation state",
);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/frontend/studioPanel.teaching-video-entry.test.ts`

Expected: FAIL because artifact clicks still call `setViewingFile(item)` for all types.

- [ ] **Step 3: Write minimal implementation**

Add a focused click helper in `frontend/src/components/teacher/StudioPanel.tsx` near the artifact list rendering:

```ts
  const handleArtifactOpen = (item: GeneratedFile) => {
    if (item.type !== 'video') {
      setViewingFile(item);
      return;
    }

    const generationState =
      item.meta?.generationState && typeof item.meta.generationState === 'object'
        ? (item.meta.generationState as Record<string, any>)
        : {};
    const status = String(generationState.status || '').trim().toLowerCase();

    if (status === 'completed' && courseId) {
      window.location.hash = `#resources?courseId=${encodeURIComponent(courseId)}&materialId=${encodeURIComponent(item.id)}`;
      return;
    }

    if (status === 'processing') {
      message.info('教学视频生成中，请稍后再进入课程资料查看。');
      return;
    }

    if (status === 'failed') {
      message.warning('教学视频生成失败，暂时无法跳转到课程资料。');
      return;
    }

    setViewingFile(item);
  };
```

Replace the artifact click sites:

```tsx
onClick={() => handleArtifactOpen(item)}
```

and

```tsx
onClick={(e) => {
  e.stopPropagation();
  handleArtifactOpen(item);
}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test frontend/tests/frontend/studioPanel.teaching-video-entry.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/teacher/StudioPanel.tsx frontend/tests/frontend/studioPanel.teaching-video-entry.test.ts
git commit -m "feat: route completed teaching videos to stitch resources"
```

## Task 3: Restore Course Context and Targeted Material Selection in Stitch Resources

**Files:**
- Modify: `frontend/src/stitch/api/courses.ts`
- Modify: `frontend/src/stitch/api/types.ts`
- Modify: `frontend/src/stitch/pages/CourseResources.tsx`
- Test: `frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts` with:

```ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const courseResources = readFileSync(
  new URL("../../src/stitch/pages/CourseResources.tsx", import.meta.url),
  "utf8",
);

assert.match(
  courseResources,
  /new URLSearchParams\(window\.location\.hash\.split\("\?"\)\[1\] \|\| ""\)/,
  "CourseResources should parse hash query params for courseId and materialId",
);

assert.match(
  courseResources,
  /const requestedCourseId = searchParams\.get\("courseId"\)/,
  "CourseResources should read courseId from the hash params",
);

assert.match(
  courseResources,
  /const requestedMaterialId = searchParams\.get\("materialId"\)/,
  "CourseResources should read materialId from the hash params",
);

assert.match(
  courseResources,
  /setSelectedCourse\(backendCourseToSummary\(courseDetail\)\)/,
  "CourseResources should restore stitch course context from the requested courseId",
);

assert.match(
  courseResources,
  /setActiveId\(requestedMaterialId\)/,
  "CourseResources should auto-select the requested material when present",
);

console.log("stitchCourseResources.teaching-video tests passed");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts`

Expected: FAIL because `CourseResources.tsx` currently only uses `selectedCourse ?? defaultCourse` and always selects the first material.

- [ ] **Step 3: Write minimal implementation**

Update `frontend/src/stitch/pages/CourseResources.tsx` imports and setup:

```ts
import { backendCourseToSummary, getCourse, courseMaterialToMarkdown, getCourseMaterials } from "../api/courses";
```

Read hash params and stitch shell context:

```ts
  const { selectedCourse, setSelectedCourse } = useAppShell();
  const searchParams = new URLSearchParams(window.location.hash.split("?")[1] || "");
  const requestedCourseId = searchParams.get("courseId");
  const requestedMaterialId = searchParams.get("materialId");
  const course = selectedCourse ?? defaultCourse;
```

Restore course context before loading materials:

```ts
  useEffect(() => {
    let cancelled = false;

    async function syncRequestedCourse() {
      if (!requestedCourseId || requestedCourseId === selectedCourse?.id) {
        return;
      }

      const courseDetail = await getCourse(requestedCourseId);
      if (!cancelled) {
        setSelectedCourse(backendCourseToSummary(courseDetail));
      }
    }

    void syncRequestedCourse();
    return () => {
      cancelled = true;
    };
  }, [requestedCourseId, selectedCourse?.id, setSelectedCourse]);
```

Select the requested material after material load:

```ts
        if (!cancelled) {
          setMaterials(data);
          if (requestedMaterialId && data.some((item) => item.material_id === requestedMaterialId)) {
            setActiveId(requestedMaterialId);
          } else {
            setActiveId(data[0]?.material_id ?? null);
          }
        }
```

Extend stitch `CourseMaterial` typing in `frontend/src/stitch/api/types.ts` so the page can read the video payload safely:

```ts
export type CourseMaterial = {
  material_id: string;
  material_type: string;
  title?: string | null;
  summary?: string | null;
  content?: string | Record<string, unknown> | null;
  generation_state?: {
    status?: string | null;
    phase?: string | null;
    message?: string | null;
  } | null;
  is_pinned?: boolean;
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stitch/api/courses.ts frontend/src/stitch/api/types.ts frontend/src/stitch/pages/CourseResources.tsx frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts
git commit -m "feat: restore stitch resource context from video deep links"
```

## Task 4: Render Video Materials Inside Stitch Course Resources

**Files:**
- Modify: `frontend/src/stitch/pages/CourseResources.tsx`
- Modify: `frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts`

- [ ] **Step 1: Write the failing test**

Append these assertions to `frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts`:

```ts
assert.match(
  courseResources,
  /const typeLabels: Record<string, string> = \{[\s\S]*video:\s*"教学视频"/,
  "CourseResources should label video materials in the grouped resource list",
);

assert.match(
  courseResources,
  /if\s*\(activeMaterial\.material_type\s*===\s*"video"\)[\s\S]*<video[\s\S]*src=\{videoUrl\}/,
  "CourseResources should render a dedicated HTML video player for video materials",
);

assert.match(
  courseResources,
  /const videoUrl = typeof videoContent\.video_url === "string" \? videoContent\.video_url : ""/,
  "CourseResources should read the video_url from the material content payload",
);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts`

Expected: FAIL because `CourseResources.tsx` only renders `MarkdownPreview`.

- [ ] **Step 3: Write minimal implementation**

Extend the type label map:

```ts
const typeLabels: Record<string, string> = {
  blog: "博客",
  report: "报告",
  lesson_plan: "教案",
  ppt: "PPT",
  quiz: "测验",
  video: "教学视频",
};
```

Add the video payload extraction near `activeMaterial`:

```ts
  const videoContent =
    activeMaterial?.material_type === "video" && activeMaterial.content && typeof activeMaterial.content === "object"
      ? (activeMaterial.content as Record<string, unknown>)
      : {};
  const videoUrl = typeof videoContent.video_url === "string" ? videoContent.video_url : "";
  const videoStatus = String(activeMaterial?.generation_state?.status || "").trim().toLowerCase();
```

Replace the detail body with a video branch before `MarkdownPreview`:

```tsx
                  <div className="mt-6 max-h-[calc(100vh-220px)] overflow-y-auto pr-2">
                    {activeMaterial.material_type === "video" ? (
                      <div className="space-y-4">
                        <p className="text-sm text-[var(--muted-text)]">
                          {activeMaterial.summary || "这里展示从教师工作台跳转过来的教学视频。"}
                        </p>
                        {videoUrl ? (
                          <video controls preload="metadata" className="w-full rounded-[24px] bg-black" src={videoUrl} />
                        ) : (
                          <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] px-5 py-6 text-sm text-[var(--muted-text)]">
                            {videoStatus === "completed" ? "视频地址暂不可用。" : "当前视频尚未准备好播放。"}
                          </div>
                        )}
                      </div>
                    ) : (
                      <MarkdownPreview content={markdown} />
                    )}
                  </div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stitch/pages/CourseResources.tsx frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts
git commit -m "feat: render teaching videos in stitch course resources"
```

## Task 5: Run Focused Verification

**Files:**
- No code changes required unless a verification failure reveals a missing edge case.
- Test: `frontend/tests/frontend/stitchApp.resources-route.test.ts`
- Test: `frontend/tests/frontend/studioPanel.teaching-video-entry.test.ts`
- Test: `frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts`

- [ ] **Step 1: Run the focused frontend tests**

Run:

```bash
node --test \
  frontend/tests/frontend/stitchApp.resources-route.test.ts \
  frontend/tests/frontend/studioPanel.teaching-video-entry.test.ts \
  frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts
```

Expected: PASS for all three files.

- [ ] **Step 2: Run the existing teaching-video regression test**

Run:

```bash
node --test frontend/tests/frontend/teacherApi.teaching-video.test.ts
```

Expected: PASS, proving the teacher-side API contract was not broken by the navigation changes.

- [ ] **Step 3: Manual verification**

Use this checklist:

```md
- Open the teacher workbench with a course selected.
- Confirm a completed teaching-video artifact exists in the right-side file list.
- Click the completed teaching video.
- Verify the browser hash becomes `#resources?courseId=<courseId>&materialId=<materialId>`.
- Verify stitch opens the course-resources page instead of the video page.
- Verify the left panel contains a `video` group.
- Verify the requested video is auto-selected.
- Verify the right detail pane renders an HTML video player when `content.video_url` is present.
- Verify a processing or failed video artifact does not navigate away from the teacher workbench.
```

- [ ] **Step 4: Commit any final fixups**

```bash
git add frontend/src/components/teacher/StudioPanel.tsx frontend/src/stitch/App.tsx frontend/src/stitch/api/courses.ts frontend/src/stitch/api/types.ts frontend/src/stitch/pages/CourseResources.tsx frontend/tests/frontend/stitchApp.resources-route.test.ts frontend/tests/frontend/stitchCourseResources.teaching-video.test.ts frontend/tests/frontend/studioPanel.teaching-video-entry.test.ts
git commit -m "test: verify stitch teaching video resource playback flow"
```

## Self-Review

### Spec coverage

- Workbench click-to-resources for completed videos: covered in Task 2.
- Restore stitch `resources` route: covered in Task 1.
- Restore target course/material context from hash params: covered in Task 3.
- Render teaching videos inside stitch course resources: covered in Task 4.
- Focused verification and regression coverage: covered in Task 5.

### Placeholder scan

- No `TODO`, `TBD`, or “similar to Task N” placeholders remain.
- Each code-changing step includes a concrete code block.
- Each verification step includes an exact command and expected result.

### Type consistency

- Navigation contract uses `courseId` and `materialId` consistently across Task 2 and Task 3.
- The stitch detail page reads `content.video_url` consistently across Task 3 and Task 4.
- `material_type === "video"` is the discriminator everywhere in the plan.
