# PPT Outline Dedup Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate repeated PPT outline chapters and slides by hardening the outline prompt and adding deterministic dedup/sanitization in the outline builder.

**Architecture:** Keep LLM outline generation, but treat it as a draft instead of a trusted final result. After parsing, sanitize the outline into a stable page-level structure with unique chapter titles, unique content slide titles, sequential slide indexes, and fallback supplementation from `key_points` when the LLM draft collapses into repeated pages.

**Tech Stack:** Python, pytest, Pydantic models, existing PPT workflow contracts

---

### Task 1: Lock Repetition Regression with Tests

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py`

- [ ] **Step 1: Write/keep failing regression tests for repeated outline output**

Cover:
- prompt contains explicit unique-title constraints
- duplicated LLM content slides are normalized into unique output slides
- duplicated chapter titles are normalized away

- [ ] **Step 2: Run the focused test file and verify the regression is red**

Run: `python -m pytest tests\chat\test_ppt_outline_builder.py -q`

Expected: failures around duplicate content titles and missing prompt constraints.

### Task 2: Harden Prompt and Sanitize Draft Outline

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\outline_builder.py`

- [ ] **Step 1: Strengthen the outline prompt**

Add hard constraints:
- all `chapter_title` values must be unique
- all `content` slide titles must be unique
- forbid repeated generic template titles across multiple pages
- require different pedagogical angles when adjacent pages discuss related topics
- require self-check before returning JSON

- [ ] **Step 2: Add parsed-outline sanitization**

Implement deterministic post-processing:
- normalize text for duplicate detection
- dedupe repeated content slides by title
- supplement missing unique content slides from preparation `key_points`
- rebuild sequential slide indexes
- rebuild chapter groupings if parsed chapters remain duplicated or invalid
- preserve cover / toc / thanks pages

- [ ] **Step 3: Keep fallback outline generation as a safe recovery path**

If sanitized LLM draft is still too weak, fall back to deterministic outline generation using unique `key_points`.

### Task 3: Verify the Fix

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py`
- Verify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py`

- [ ] **Step 1: Run the focused outline tests**

Run: `python -m pytest tests\chat\test_ppt_outline_builder.py -q`

Expected: pass

- [ ] **Step 2: Run PPT workflow regression tests**

Run: `python -m pytest tests\chat\test_ppt_workflow_runtime.py -q`

Expected: pass

- [ ] **Step 3: Run adjacent PPT tests if outline contracts changed**

Run: `python -m pytest tests\chat\test_ppt_slide_plan_builder.py tests\chat\test_ppt_content_markdown_assembler.py tests\chat\test_ppt_reply_service_v2.py -q`

Expected: pass
