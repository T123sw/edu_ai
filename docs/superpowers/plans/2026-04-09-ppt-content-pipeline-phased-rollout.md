# PPT Content Pipeline Phased Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the PPT content pipeline in phases so chapter-level TOC, a minimal pre-html2ppt gate, layout-aware compression, and stable regression fixtures land first, with semantic-slot refactoring deferred to later phases.

**Architecture:** Keep the current `outline -> slide_plan -> content_markdown -> html2ppt` pipeline intact for the first rollout, but insert a stable chapter/TOC source and a new validation gate before rendering. Internally, the gate should be split into inspectors, transformers, and an adjudicator so issue reporting, deterministic shrinking, and pass/fail decisions stay testable and isolated.

**Tech Stack:** Python, Pydantic, pytest, PPT workflow runtime, markdown assembly pipeline

---

### Task 1: Lock the current failures with regression tests

**Files:**
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_outline_builder.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_slide_plan_builder.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_markdown_assembler.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime.py`

- [ ] **Step 1: Add a failing test that TOC only shows chapter-level entries**

Target behavior:

- Given a 15-slide outline derived from 3 key points
- The TOC should render 3-4 top-level chapter labels
- It must not render every content slide title

- [ ] **Step 2: Add a failing test that over-budget cards or bullets are rejected or compressed before html2ppt**

Target behavior:

- When a slide exceeds its layout budget
- The pipeline either compresses or rejects it before rendering

- [ ] **Step 3: Add a failing test that placeholder card text is flagged**

Target behavior:

- `Title == Text`
- or repeated “为什么重要 / 课堂结论” style placeholders
- should not pass the validation gate

- [ ] **Step 4: Run targeted tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; python -m pytest `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_slide_plan_builder.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_markdown_assembler.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py -q
```

Expected:

- New TOC, budget, and placeholder tests fail against the current pipeline.

- [ ] **Step 5: Add a fixed Agent sample fixture for end-to-end regression**

Fixture contents:

- `preparation`
- `outline`
- `slide_plan`
- `content_markdown`

Target assertions:

- TOC item count is 3
- obvious placeholder-only pages fail
- runtime can still process valid markdown

### Task 2: Introduce a stable chapter-level TOC source

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/domain/ppt_outline.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/domain/ppt_slide_plan.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/outline_builder.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/slide_plan_builder.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_markdown_assembler.py`

- [ ] **Step 1: Extend outline/slide plan models with explicit chapter metadata**

Add the minimum fields needed for stable TOC generation:

- `chapter_id`
- `chapter_order`
- `toc_label`
- `chapter_goal` / `chapter_summary`
- `show_in_toc`

- [ ] **Step 2: Update the outline builder so expanded slides remain attached to one top-level chapter**

Target behavior:

- The first 3 key points become the stable chapter layer
- Expanded pages remain internal chapter pages
- Expanded pages must not become TOC items

- [ ] **Step 3: Update the assembler so TOC uses chapters, not content slide titles**

Target behavior:

- `toc_items` should be derived from `slide_plan.chapters`
- If `chapters` exist, `slides` must not be used as a fallback unless the outline is malformed

- [ ] **Step 4: Run targeted tests and verify GREEN for TOC behavior**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; python -m pytest `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_markdown_assembler.py -q
```

Expected:

- TOC-level tests pass and the TOC renders only top-level chapters.

### Task 3: Add a minimal pre-html2ppt validation gate (Phase 1A)

**Files:**
- Create: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_gate.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_validator.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/runtime.py`

- [ ] **Step 1: Create a gate object that evaluates markdown before html2ppt submission**

The gate must return:

- `ok`
- `errors`
- `warnings`
- `transformations`
- `final_markdown`
- `issues`

- [ ] **Step 2: Define a structured issue model for all gate inspectors**

Minimum issue fields:

- `code`
- `severity`
- `slide_index`
- `field_path`
- `message`
- `suggested_action`

- [ ] **Step 3: Implement Phase-1A inspectors only**

Phase-1A checks must include:

- structure validity
- TOC item count limit

- [ ] **Step 4: Wire the runtime so html2ppt is called only after gate approval**

Target behavior:

- `runtime.py` assembles markdown
- passes markdown into the content gate
- only approved markdown goes to `html2ppt_client.create_job`

- [ ] **Step 5: Log issue payloads into ppt workflow debug logs**

Expected log events:

- `content_gate_started`
- `content_gate_failed`
- `content_gate_transformed`
- `content_gate_passed`

- [ ] **Step 6: Run runtime and validator tests and verify GREEN**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; python -m pytest `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_markdown_assembler.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py -q
```

Expected:

- Invalid content is blocked before html2ppt.

### Task 4: Add conservative layout budgets and compression fallbacks (Phase 1B)

**Files:**
- Create: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/layout_budget.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_gate.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/slide_plan_builder.py`

- [ ] **Step 1: Define per-layout budgets for both item-level and page-density rules**

Initial conservative defaults:

- `lead`: 48 Chinese chars
- `bullets`: max 4 items, 36 chars each
- `cards`: max 4 cards, 12-char title, 32-char body
- `process`: max 4 steps, 10-char title, 30-char body
- `comparison`: max 2-3 items per side, 30 chars each

Density rules must also cover combinations such as:

- `lead + 5 bullets`
- `lead + 4 cards + long titles`
- `lead + 4 process steps + long bodies`
- `lead + 3x3 comparison`

- [ ] **Step 2: Implement automatic compression before rejection**

Compression order:

1. shorten text
2. reduce item count
3. downgrade layout

Compression rule:

- remove modifiers, transitions, and classroom filler first
- preserve actor, action, object, and differentiator when shortening

- [ ] **Step 3: Record every deterministic transformation in a structured transformation log**

Minimum log fields:

- `strategy`
- `slide_index`
- `field_path`
- `reason`
- `before`
- `after`

- [ ] **Step 4: Restrict slide plan enrichment so it does not immediately refill compressed layouts**

Target behavior:

- enrichment helpers must respect budget-aware max counts
- builder should not expand a slide back to a rejected density

- [ ] **Step 5: Run regression tests and inspect the Agent sample manually**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; python -m pytest `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_slide_plan_builder.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py -q
```

Expected:

- Budget tests pass
- The Agent sample no longer overflows obvious high-density pages

### Task 5: Add placeholder detection for rigid pages

**Files:**
- Create: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/placeholder_detector.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_gate.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_slide_plan_builder.py`

- [ ] **Step 1: Detect only the hardest placeholder patterns in Phase 1**

Minimum phase-1 rules:

- card/body duplicates title
- body is a near-direct restatement of title
- repeated “为什么重要 / 课堂结论 / 最值得强调” style filler without concrete nouns, actions, or examples

- [ ] **Step 2: Route placeholder failures through transform-or-reject behavior**

Phase-1 strategy:

- warn on mild duplication
- fail on obvious placeholder-only pages

Out of scope for this phase:

- sibling semantic overlap scoring
- card-to-card information-role analysis

- [ ] **Step 3: Run targeted tests and verify GREEN**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; python -m pytest `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_slide_plan_builder.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py -q
```

Expected:

- Placeholder-only pages are caught before rendering.

### Task 6: Phase 2 follow-up for semantic payload refactor

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/domain/ppt_slide_plan.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/slide_plan_builder.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_markdown_assembler.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_slide_plan_builder.py`

- [ ] **Step 1: Introduce a minimal `semantic_payload` structure**

Phase-2 starter slots:

- `definition`
- `mechanism`
- `example`
- `value`
- `takeaway`
- `pitfall`

- [ ] **Step 2: Map semantic slots into visible blocks and notes**

Target behavior:

- high-value examples move into visible blocks when space allows
- longer explanation stays in notes
- `builder` remains responsible for candidate generation
- `gate` remains limited to deterministic renderability transforms

- [ ] **Step 3: Run the full PPT workflow test suite**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; python -m pytest `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_slide_plan_builder.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_markdown_assembler.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py -q
```

Expected:

- All workflow tests pass with the semantic-payload bridge in place.

---

## Phase Boundaries

**Phase 1A ships when:**

- TOC only shows chapter-level items
- pre-html2ppt gate is active
- gate blocks structure and TOC failures using a structured issue model

**Phase 1B ships when:**

- layout budgets and compression are active
- placeholder-only pages are blocked
- transformation logs are emitted for deterministic shrink/downgrade actions
- the fixed Agent sample passes end-to-end regression

**Phase 2 starts after:**

- the Agent sample is stable under the new gate
- no frequent false positives are observed in the validator

---

## Execution Notes

- Do not start with the semantic-payload rewrite.
- Do not modify `html2ppt` engine behavior in this rollout.
- Keep all validation and fallback logic in the chat PPT pipeline.
- Preserve debug logging at each transformation boundary so failed decks can still be inspected from logs.
- Keep `content_gate` as orchestration only; inspectors find problems, transformers shrink content, adjudicator decides pass/fail.
