# OpenMAIC Phase 4 PPTX Export Implementation Plan

> **Execution:** follow test-driven development and commit after every task.

**Goal:** Export the same stored OpenMAIC `Stage/Scene/Slide` source used by the
interactive classroom into a downloadable, offline PPTX with correct slide
order, geometry, Chinese text, editable formulas, and speaker notes.

**Architecture:** Reuse the vendored OpenMAIC fork of PptxGenJS and its
MathML→OMML package as local `file:` dependencies. Keep edu_ai integration in a
small browser-side adapter under `frontend/src/openmaic/`; it accepts plain
classroom scenes and has no dependency on the sidecar's React stores. The
classroom page owns download state and invokes the pure blob builder.

**Quality gates:** Node tests inspect generated OOXML through JSZip; frontend
lint/build must pass; browser acceptance must produce a non-empty `.pptx`.

---

## Task 1: Establish exporter dependencies and contract

**Files**

- Modify `frontend/package.json`
- Modify `Edu_AI/package-lock.json`
- Create `frontend/src/openmaic/pptxExporter.ts`
- Create `frontend/src/openmaic/pptxExporter.test.ts`

1. Add local `pptxgenjs` and `mathml2omml` dependencies plus the minimal
   browser conversion dependencies used by the exporter.
2. Write failing tests for slide filtering/order, valid PPTX ZIP output, slide
   count, and speaker notes sourced from `speech` actions.
3. Implement the export input/result contract and the smallest valid blob
   builder.
4. Run targeted tests, full frontend tests, lint, and build.
5. Commit as `feat(pptx): establish OpenMAIC export contract`.

## Task 2: Preserve core slide visuals

**Files**

- Modify `frontend/src/openmaic/pptxExporter.ts`
- Modify `frontend/src/openmaic/pptxExporter.test.ts`

1. Add failing OOXML tests for background, text content/formatting, geometry,
   z-order, and image embedding.
2. Implement conversion for solid/image backgrounds, text runs, images,
   basic shapes, lines, charts, and tables. Unsupported individual elements
   degrade by omission without invalidating the deck.
3. Verify tests/lint/build.
4. Commit as `feat(pptx): preserve slide visuals and geometry`.

## Task 3: Export formulas and media safely

**Files**

- Create `frontend/src/openmaic/latexToOmml.ts`
- Modify `frontend/src/openmaic/pptxExporter.ts`
- Modify `frontend/src/openmaic/pptxExporter.test.ts`

1. Add failing tests proving LaTeX becomes editable OMML and video poster/media
   failures do not corrupt the deck.
2. Port the OpenMAIC LaTeX→MathML→OMML post-processing pipeline.
3. Embed supported image/audio/video data; retain posters when media cannot be
   embedded.
4. Verify tests/lint/build.
5. Commit as `feat(pptx): export editable formulas and media`.

## Task 4: Add the classroom download workflow

**Files**

- Create `frontend/src/openmaic/PptxExportButton.tsx`
- Modify `frontend/src/stitch/pages/ClassroomPlayer.tsx`

1. Add a button-level test or pure download-helper test for filename
   sanitization, duplicate-click guard, success, and failure cleanup.
2. Add a visible “导出 PPTX” action to the real classroom player. Export all
   slide scenes, show in-progress state, and download `<课件标题>.pptx`.
3. Verify in the browser that a generated file download starts and the page
   remains responsive.
4. Verify tests/lint/build.
5. Commit as `feat(pptx): add classroom download workflow`.

## Task 5: Sign off Phase 4

**Files**

- Create `docs/spec/SPEC-09_PPTX导出.md`
- Create `docs/acceptance/ACC-09_PPTX导出_验收.md`
- Modify `docs/acceptance/README.md`
- Modify `docs/OpenMAIC复用_实施总纲_2026-06-30.md`
- Modify `项目总览地图.md`

1. Inspect an exported PPTX ZIP for slide XML, notes XML, relationships,
   embedded assets, and OMML.
2. Open/download through the browser workflow and record the evidence.
3. Run the full frontend and relevant backend regression gates.
4. Mark only evidenced acceptance items complete and update the roadmap.
5. Commit as `docs(migration): close Phase 4 PPTX export acceptance`.
