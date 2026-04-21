# Realtime PPT Single Slide Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the realtime lecture stage show exactly one PPT slide at a time and switch slides discretely on page changes, without affecting the lower course-content preview.

**Architecture:** Keep the realtime stage iframe stable, but change the generated `deck.html` runtime so it supports a dedicated single-slide preview mode. The frontend continues to message the iframe on slide changes, while the deck runtime hides non-active slides and swaps the visible slide instead of scrolling the whole deck.

**Tech Stack:** React, TypeScript, Vite, html2ppt standalone deck runtime, Node test runner

---

### Task 1: Lock the single-slide contract in tests

**Files:**
- Modify: `Edu_AI/tests/frontend/videoPlayer.realtime-ppt-stage.test.ts`
- Modify: `Edu_AI/tests/frontend/videoPlayer.ai-lecture-realtime-bootstrap.test.ts`
- Modify: `Edu_AI/tests/frontend/videoPlayer.ai-lecture-session.test.ts`
- Modify: `Edu_AI/api/Edu_AI/html2ppt/test/ppt-service.test.js`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run the targeted tests to verify they fail for the missing single-slide behavior**
- [ ] **Step 3: Commit the red-state test updates**

### Task 2: Add single-slide preview mode to generated deck runtime

**Files:**
- Modify: `Edu_AI/api/Edu_AI/html2ppt/src/lib/build-standalone-html.js`
- Test: `Edu_AI/api/Edu_AI/html2ppt/test/ppt-service.test.js`

- [ ] **Step 1: Teach the standalone deck runtime to enter single-slide preview mode**
- [ ] **Step 2: Make `ppt-preview-go-to-slide` switch the active visible slide instead of scrolling the full deck**
- [ ] **Step 3: Keep initial `slide/page/hash` bootstrapping working in single-slide mode**
- [ ] **Step 4: Run `node --test test/ppt-service.test.js` and verify green**
- [ ] **Step 5: Commit the deck runtime change**

### Task 3: Keep realtime stage on the new single-slide contract

**Files:**
- Modify: `Edu_AI/src/stitch/pages/VideoPlayer.tsx`
- Test: `Edu_AI/tests/frontend/videoPlayer.realtime-ppt-stage.test.ts`
- Test: `Edu_AI/tests/frontend/videoPlayer.ai-lecture-realtime-bootstrap.test.ts`
- Test: `Edu_AI/tests/frontend/videoPlayer.ai-lecture-session.test.ts`

- [ ] **Step 1: Keep the realtime iframe in preview mode only**
- [ ] **Step 2: Ensure slide-change messages continue to target the active page index**
- [ ] **Step 3: Preserve PPT full-width fit and digital-human lower-right placement**
- [ ] **Step 4: Run the realtime frontend tests and verify green**
- [ ] **Step 5: Commit the realtime stage integration**

### Task 4: Final verification

**Files:**
- Modify: `Edu_AI/src/stitch/pages/VideoPlayer.tsx`
- Modify: `Edu_AI/api/Edu_AI/html2ppt/src/lib/build-standalone-html.js`

- [ ] **Step 1: Run the full targeted frontend regression set**
- [ ] **Step 2: Run the html2ppt runtime regression set**
- [ ] **Step 3: Run `npm run build` from `Edu_AI/`**
- [ ] **Step 4: Review diffs for scope drift and stop once only realtime single-slide behavior changed**
