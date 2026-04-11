# PPT Expansion To HTML2PPT Debug Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the missing "outline-expanded content" handoff into `html2ppt`, and add console-visible end-to-end tracing plus persisted debug artifacts for each stage.

**Architecture:** The PPT workflow should emit a traceable chain of artifacts: `PptOutline -> PptSlidePlan -> content_markdown -> html2ppt revision content -> generated fragment/html/pptx`. We will harden the slide-plan expansion path, expose the exact fallback/LLM parse reason, and log every critical intermediate artifact on both Python and Node sides without changing the external workflow contract.

**Tech Stack:** Python, Pydantic, LangChain `ChatOpenAI`, Node.js, existing `html2ppt` service, `pytest`, Node test runner.

---

### Task 1: Reproduce And Freeze The Current Failure

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_slide_plan_builder.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt\test\ppt-service.test.js`

- [ ] **Step 1: Add a failing Python test for LLM parse fallback visibility**

Cover the case where `PptSlidePlanBuilder` receives malformed / incomplete LLM output and must expose why it fell back.

- [ ] **Step 2: Add a failing Python test for runtime debug trace completeness**

Assert `_submit_outline()` surfaces `ppt_slide_plan`, `ppt_content_markdown`, and explicit expansion metadata in the returned trace or persisted debug log payload.

- [ ] **Step 3: Add a failing Node test for html2ppt preprocessing trace**

Assert `ppt-service` records the resolved `content.md` path, parsed slide count, and batch-level markdown snapshot metadata before generation.

- [ ] **Step 4: Run targeted tests to confirm they fail for the expected reason**

Run:
`python -m pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_slide_plan_builder.py -q`

Run:
`python -m pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py -q`

Run:
`node --test d:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt\test\ppt-service.test.js`

- [ ] **Step 5: Commit checkpoint**

Do not commit unless the user explicitly asks for commits.

### Task 2: Harden Slide Expansion Diagnostics On The Python Side

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\slide_plan_builder.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\debug_logging.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_slide_plan_builder.py`

- [ ] **Step 1: Refactor slide-plan expansion to return structured debug metadata**

Capture for each chapter:
- prompt preview
- raw LLM response preview
- JSON extraction success/failure
- model parse success/failure
- whether fallback was used
- final per-slide layout summary

- [ ] **Step 2: Add console logging helper support**

Extend the existing debug helper so important PPT workflow events can also print compact JSON / readable summaries to stdout while keeping file logging non-fatal.

- [ ] **Step 3: Preserve current production behavior while exposing fallback reason**

If expansion fails, keep fallback generation, but log the exact stage that failed instead of silently degrading.

- [ ] **Step 4: Re-run targeted slide-plan tests**

Run:
`python -m pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_slide_plan_builder.py -q`

### Task 3: Trace The Runtime Handoff Into HTML2PPT

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\runtime.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\content_markdown_assembler.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py`

- [ ] **Step 1: Log each major runtime phase**

Add explicit runtime logs for:
- preparation assembled
- outline generated / normalized
- slide plan built
- markdown assembled
- validation finished
- html2ppt request submitted
- html2ppt poll progress
- results loaded

- [ ] **Step 2: Include intermediate artifacts in debug payloads**

Persist / emit compact previews for:
- outline slide titles
- slide-plan per-slide content summary
- full `content_markdown` or a safe preview plus length
- html2ppt request metadata and job id

- [ ] **Step 3: Make markdown assembly logs readable**

Log block types per slide so it is obvious whether a page became `Bullets`, `Cards`, `Comparison`, or `Process` before it reaches Node.

- [ ] **Step 4: Re-run targeted runtime tests**

Run:
`python -m pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py -q`

### Task 4: Trace html2ppt Preprocessing And Batch Inputs

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt\src\services\ppt-service.js`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt\src\domain\content-protocol.js`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt\test\ppt-service.test.js`

- [ ] **Step 1: Log parsed content protocol summary**

Emit console/debug records for:
- deck title/theme
- slide count
- per-slide role/title/blockTypes
- batch count and slide-number ranges

- [ ] **Step 2: Persist intermediate batch snapshots**

Ensure the existing revision/batch debug output clearly shows:
- original `content.md`
- each batch `content.md`
- prompt path
- fragment path

If the files already exist, add logs that announce their exact locations.

- [ ] **Step 3: Log generation stage transitions with artifact paths**

Before and after generation / export, log the output paths for fragment, standalone HTML, manifest, and PPTX.

- [ ] **Step 4: Re-run Node tests**

Run:
`node --test d:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt\test\ppt-service.test.js`

### Task 5: Verify End-To-End Evidence

**Files:**
- Inspect: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\storage\logs\ppt_workflow.log`
- Inspect: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt\data\jobs\...\revisions\...\content.md`
- Inspect: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt\data\jobs\...\revisions\...\batches\...\content.md`
- Inspect: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt\data\jobs\...\revisions\...\deck.fragment.html`

- [ ] **Step 1: Run the targeted Python and Node tests together**

Run:
`python -m pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_slide_plan_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py -q`

Run:
`node --test d:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt\test\ppt-service.test.js`

- [ ] **Step 2: Spot-check a real or fixture-generated job directory**

Confirm the logged / persisted artifacts show the exact expanded content that should appear in the generated PPT.

- [ ] **Step 3: Summarize evidence for the user**

Report:
- root cause
- fixed files
- where to read console logs
- where to inspect intermediate products on disk
- remaining risks, if any
