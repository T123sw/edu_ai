# AI Classroom Focused Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove nonessential page and classroom chrome so the AI classroom center rail contains only the stage and essential export/playback controls, while preserving responsive rail access and continuous page playback.

**Architecture:** Keep the existing `ClassroomWorkspaceLayout` and contextual QA bindings unchanged. Simplify `ClassroomStudioPage` into a full-height workspace host with breakpoint-only drawer launchers, and simplify `ClassroomPlaybackSurface` into a two-row stage/control console. Reuse the existing export components, fullscreen API, playback controller, and `completeAndAdvance` orchestration instead of introducing parallel behavior.

**Tech Stack:** React 18, TypeScript, Vite, Node test runner, CSS Grid/Flexbox, Fullscreen API.

---

## File map

- Modify `Edu_AI/src/stitch/pages/ClassroomStudio.tsx`: remove the page toolbar, search state/filtering, and viewer breadcrumb; add breakpoint-only drawer launchers.
- Modify `Edu_AI/src/stitch/pages/classroomCatalogPage.test.ts`: lock the page-level focused workspace contract.
- Modify `Edu_AI/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.test.ts`: lock responsive launcher and height behavior.
- Modify `Edu_AI/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.tsx`: remove classroom title/catalog/presentation chrome and move both exports into the core footer.
- Modify `Edu_AI/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.test.ts`: lock the focused player DOM contract and existing autoplay integration.
- Modify `Edu_AI/src/stitch/course/classroomCatalog/courseClassroomCatalog.css`: reclaim page-toolbar height and style floating drawer launchers.
- Modify `Edu_AI/src/stitch/styles.css`: reduce the classroom console to stage plus controls and remove dead classroom-catalog/presentation styles.
- Create `docs/acceptance/2026-09-01-ai-classroom-focused-playback.md`: record automated and viewport acceptance evidence.

### Task 1: Remove the AI classroom page toolbar without losing drawer access

**Files:**
- Modify: `Edu_AI/src/stitch/pages/classroomCatalogPage.test.ts`
- Modify: `Edu_AI/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.test.ts`
- Modify: `Edu_AI/src/stitch/pages/ClassroomStudio.tsx`
- Modify: `Edu_AI/src/stitch/course/classroomCatalog/courseClassroomCatalog.css`

- [ ] **Step 1: Write the failing page-shell tests**

Add this focused contract to `classroomCatalogPage.test.ts`:

```ts
test("AI classroom uses a focused workspace without a page toolbar or breadcrumb", async () => {
  const page = await source("./ClassroomStudio.tsx");

  assert.doesNotMatch(page, /course-classroom-catalog__toolbar/);
  assert.doesNotMatch(page, /course-classroom-catalog__search/);
  assert.doesNotMatch(page, /course-classroom-catalog__breadcrumb/);
  assert.doesNotMatch(page, /filterCurriculumTree/);
  assert.match(page, /course-classroom-catalog__mobile-tools/);
  assert.match(page, /aria-controls="classroom-workspace-directory"/);
  assert.match(page, /aria-controls="classroom-workspace-qa"/);
});
```

Extend the responsive test in `ClassroomWorkspaceLayout.test.ts`:

```ts
assert.match(css, /\.course-classroom-catalog__mobile-tools\s*\{[^}]*display:\s*none/s);
assert.match(css, /@media\s*\(max-width:\s*1279px\)[\s\S]*course-classroom-catalog__mobile-tools/);
assert.match(css, /@media\s*\(max-width:\s*959px\)[\s\S]*catalog-qa-toggle/);
assert.match(css, /position:\s*fixed/);
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run from `Edu_AI/`:

```powershell
node --import tsx --test `
  src/stitch/pages/classroomCatalogPage.test.ts `
  src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.test.ts
```

Expected: FAIL because `ClassroomStudio.tsx` still renders `course-classroom-catalog__toolbar`, search, and breadcrumb, and the floating launcher class does not exist.

- [ ] **Step 3: Implement the focused page shell**

In `ClassroomStudio.tsx`:

1. Remove `query` state and the `filterCurriculumTree` import/use.
2. Use `tree` directly for `CurriculumResourceTree` and `openKeys`.
3. Delete the `<header className="course-classroom-catalog__toolbar">…</header>` block.
4. Insert these breakpoint-only launchers immediately inside `<main>`:

```tsx
<nav className="course-classroom-catalog__mobile-tools" aria-label="课堂侧栏入口">
  <button
    ref={directoryTriggerRef}
    type="button"
    className="catalog-directory-toggle"
    aria-label="打开课程目录"
    aria-expanded={drawerOpen}
    aria-controls="classroom-workspace-directory"
    onClick={() => { setQaOpen(false); setDrawerOpen(true); }}
  >
    <MaterialIcon name="menu_book" />
  </button>
  <button
    ref={qaTriggerRef}
    type="button"
    className="catalog-qa-toggle"
    aria-label="打开 AI 问答"
    aria-expanded={qaOpen}
    aria-controls="classroom-workspace-qa"
    onClick={() => { setDrawerOpen(false); setQaOpen(true); }}
  >
    <MaterialIcon name="forum" />
  </button>
</nav>
```

5. Remove `course-classroom-catalog__breadcrumb` from the viewer branch.

In `courseClassroomCatalog.css`, remove the obsolete toolbar/search rules and use this height/launcher basis:

```css
.course-classroom-catalog {
  min-height: calc(100vh - var(--course-header-height));
  padding: 16px clamp(16px, 1.25vw, 24px) 20px;
}

.course-classroom-workspace {
  height: calc(100vh - var(--course-header-height) - 36px);
}

.course-classroom-catalog__mobile-tools {
  position: fixed;
  z-index: 65;
  top: calc(var(--course-header-height) + 12px);
  right: 16px;
  display: none;
  align-items: center;
  gap: 8px;
}
```

At `max-width: 1279px`, display the launcher container and directory button. At `max-width: 959px`, also display the QA button. Keep both buttons hidden at wider breakpoints.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the Step 2 command again.

Expected: all page/catalog workspace tests PASS.

- [ ] **Step 5: Commit the page-shell change**

```powershell
git add -- `
  Edu_AI/src/stitch/pages/ClassroomStudio.tsx `
  Edu_AI/src/stitch/pages/classroomCatalogPage.test.ts `
  Edu_AI/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.test.ts `
  Edu_AI/src/stitch/course/classroomCatalog/courseClassroomCatalog.css
git commit -m "feat: focus AI classroom workspace on learning content"
```

### Task 2: Reduce the classroom player to stage and essential controls

**Files:**
- Modify: `Edu_AI/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.test.ts`
- Modify: `Edu_AI/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.tsx`
- Modify: `Edu_AI/src/stitch/styles.css`

- [ ] **Step 1: Write the failing player contract test**

Append this test to `ClassroomPlaybackSurface.test.ts`:

```ts
test("focused playback renders only the stage and approved core controls", async () => {
  const [surface, css] = await Promise.all([
    source("./ClassroomPlaybackSurface.tsx"),
    source("../../styles.css"),
  ]);
  const controlsStart = surface.indexOf('<footer className="classroom-console__controls"');
  const controlsEnd = surface.indexOf("</footer>", controlsStart);
  const controls = surface.slice(controlsStart, controlsEnd);

  assert.ok(controlsStart >= 0 && controlsEnd > controlsStart);
  assert.doesNotMatch(surface, /classroom-console__header/);
  assert.doesNotMatch(surface, /classroom-console__catalog/);
  assert.doesNotMatch(surface, /课堂页面目录|打开课堂目录|进入演示/);
  assert.match(controls, /ClassroomVideoExportButton/);
  assert.match(controls, /PptxExportButton/);
  assert.match(controls, /上一页/);
  assert.match(controls, /下一页/);
  assert.match(controls, /togglePlayback/);
  assert.match(controls, /toggleFullscreen/);
  assert.match(controls, /classroom-page-count/);
  assert.doesNotMatch(controls, /classroom-current-scene|subtitles|classroom-voice-status/);
  assert.match(css, /grid-template-rows:\s*minmax\(0,\s*1fr\)\s+auto/);
});
```

Add this integration assertion to the same test so the refactor cannot detach auto-advance:

```ts
assert.match(surface, /onComplete=\{\(\)\s*=>\s*\{[\s\S]*completeAndAdvance\(\{/);
```

- [ ] **Step 2: Run the player tests and verify RED**

Run from `Edu_AI/`:

```powershell
node --import tsx --test `
  src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.test.ts `
  src/stitch/classroomQa/classroomAutoplay.test.ts
```

Expected: the new focused playback test FAILS because the player still has a header, page catalog, presentation action, and non-core footer controls. Existing autoplay tests remain PASS.

- [ ] **Step 3: Implement the focused player**

In `ClassroomPlaybackSurface.tsx`:

1. Remove `presentationMode`, `catalogOpen`, and `subtitlesVisible` state plus `enterPresentation`.
2. Keep `fullscreen` and `toggleFullscreen`; render the console with the stable class `classroom-console classroom-playback-surface`.
3. Remove the complete `classroom-console__header`, compact learning-progress strip, and internal `classroom-console__catalog` markup.
4. Keep the stage renderer and its existing `onComplete` callback unchanged:

```tsx
onComplete={() => {
  learningTrackerRef.current?.completeScene();
  void learningTrackerRef.current?.flush().catch(() => undefined);
  void completeAndAdvance({
    controller,
    sceneIndex: currentIndex,
    revision: playback.revision,
    sceneCount: scenes.length,
  });
}}
```

5. Render narration subtitles automatically during active playback without a footer toggle.
6. Replace the footer contents with the approved order:

```tsx
<footer className="classroom-console__controls" data-testid="classroom-core-controls">
  <div className="classroom-console__export-controls">
    {courseId && classroomId && canGenerate ? (
      <ClassroomVideoExportButton
        courseId={courseId}
        classroomId={classroomId}
        title={material.title || "课堂视频"}
      />
    ) : null}
    <PptxExportButton title={material.title || "课堂课件"} scenes={exportScenes} />
  </div>
  <div className="classroom-console__playback-controls">
    <button
      type="button"
      onClick={() => goTo(currentIndex - 1)}
      disabled={qaLocksPlayback || currentIndex <= 0}
      className="classroom-control-button"
    >
      <MaterialIcon name="skip_previous" />
      <span className="classroom-control-label">上一页</span>
    </button>
    <button
      type="button"
      onClick={togglePlayback}
      disabled={qaLocksPlayback || !currentPresentation?.hasPlayback}
      className="classroom-play-button"
    >
      <MaterialIcon
        name={playback.status === "playing" ? "pause" : playback.status === "completed" ? "replay" : "play_arrow"}
      />
      {playbackLabel(currentPresentation, playback)}
    </button>
    <span className="classroom-page-count">{currentIndex + 1} / {scenes.length}</span>
    <button
      type="button"
      onClick={() => goTo(currentIndex + 1)}
      disabled={qaLocksPlayback || currentIndex >= scenes.length - 1}
      className="classroom-control-button"
    >
      <span className="classroom-control-label">下一页</span>
      <MaterialIcon name="skip_next" />
    </button>
    <button type="button" onClick={toggleFullscreen} className="classroom-control-button">
      <MaterialIcon name={fullscreen ? "fullscreen_exit" : "fullscreen"} />
      <span className="classroom-control-label">{fullscreen ? "退出全屏" : "全屏"}</span>
    </button>
  </div>
</footer>
```

Preserve the exact existing disabled conditions and button handlers when moving the previous, play, next, and fullscreen buttons.

In `styles.css`:

- change `.classroom-console` to `grid-template-rows: minmax(0, 1fr) auto`;
- change `.classroom-console__workspace` and `.classroom-playback-surface .classroom-console__workspace` to one column;
- remove the unused header, internal catalog, scene list, presentation-mode, current-title, voice-status, and secondary-toggle rules;
- add `.classroom-console__export-controls` and `.classroom-console__playback-controls` as non-wrapping flex groups;
- keep the footer horizontally usable with `overflow-x: auto`, visible focus states, and compact labels at narrow widths;
- update `.classroom-stage-shell` height math to account for only one control row.

- [ ] **Step 4: Run the player tests and verify GREEN**

Run the Step 2 command again.

Expected: focused player and all three autoplay behavior tests PASS.

- [ ] **Step 5: Commit the player change**

```powershell
git add -- `
  Edu_AI/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.tsx `
  Edu_AI/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.test.ts `
  Edu_AI/src/stitch/styles.css
git commit -m "feat: reduce classroom player to essential controls"
```

### Task 3: Verify the complete classroom experience and record evidence

**Files:**
- Create: `docs/acceptance/2026-09-01-ai-classroom-focused-playback.md`

- [ ] **Step 1: Run the complete frontend test suite**

Run from `Edu_AI/`:

```powershell
npm test
```

Expected: 0 failed tests; the baseline count is 435 and will increase by the new focused-layout tests.

- [ ] **Step 2: Run the production build**

```powershell
npm run build
```

Expected: Vite exits 0 and writes `dist/`.

- [ ] **Step 3: Inspect the source diff for scope and whitespace**

Run from the worktree root:

```powershell
git diff --check
git diff --stat HEAD~2..HEAD
git status --short
```

Expected: no whitespace errors; only the files listed in this plan are changed; ignored dependency artifacts do not appear.

- [ ] **Step 4: Perform viewport acceptance**

Start the frontend against the existing local API and inspect the real AI classroom route at 1440×900, 1280×800, 959×900, and 375×812. Verify:

- global site navigation remains present;
- AI classroom page toolbar and breadcrumb are absent;
- desktop keeps the left directory, center stage, and right QA rail;
- center has no internal classroom catalog or classroom title;
- MP4, PPTX, previous, play/pause, page count, next, and fullscreen controls remain reachable;
- at 1279px and below the directory launcher opens/closes the directory drawer and restores focus;
- at 959px and below the QA launcher opens/closes the QA drawer and restores focus;
- completing a non-final narrated page advances to and starts the next page;
- completing the final page does not wrap.

- [ ] **Step 5: Record acceptance evidence**

Create `docs/acceptance/2026-09-01-ai-classroom-focused-playback.md` with the following sections, replacing each evidence line with the exact observed command output or viewport result from Steps 1–4:

```markdown
# AI 课堂专注播放模式验收

- 规格：`docs/superpowers/specs/2026-09-01-ai-classroom-focused-playback-design-cn.md`
- 实施分支：`codex/ai-classroom-focused-playback`
- 前端测试
- 生产构建
- 1440、1280、959、375 四组视口结果
- 中间页与末页自动续播结果
- 验收结论
```

- [ ] **Step 6: Commit the acceptance record**

```powershell
git add -- docs/acceptance/2026-09-01-ai-classroom-focused-playback.md
git commit -m "docs: record focused classroom playback acceptance"
```

- [ ] **Step 7: Run final verification from the feature HEAD**

Run again from `Edu_AI/` after the acceptance commit:

```powershell
npm test
npm run build
```

Expected: both commands exit 0. Then run `git status --short` from the worktree root and expect no tracked or untracked source changes.
