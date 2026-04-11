# PPT Explicit Workbench Entry Design

## Summary

Add a dedicated PPT generation entry in the right-side workbench so teachers can generate a PPT without sending setup context through chat.

The user flow is:

1. Select knowledge-base documents in the existing document list.
2. Open a PPT setup entry in the right workbench.
3. Fill structured PPT options such as theme, focus points, length, audience, and title.
4. Submit the setup to generate a draft outline from the selected documents plus the explicit configuration.
5. Review and confirm the outline inside the workbench.
6. After confirmation, continue with the existing PPT generation pipeline so content generation, html2ppt submission, polling, artifact persistence, and preview behavior stay aligned with today’s PPT workflow.

This entry must not depend on chat history and must not require a conversation-based context handoff.

More precisely:

- it must not depend on `conversation_id`, chat summary, recent messages, or active conversation context
- it may create a lightweight direct-flow draft/run object used only for workbench generation state

This draft/run object is **not** a conversation container. It is a generation draft that persists:

- selected document snapshot
- normalized PPT config
- draft outline
- trace/debug metadata
- generation status

## User Request Restated

The user wants a PPT-specific explicit entry similar to the current report-generation entry pattern:

- UI lives in the right workbench.
- Input comes from:
  - user-selected knowledge-base documents
  - direct PPT configuration fields
- It must not rely on conversational context collection.
- The selected documents and explicit config should first be summarized into a PPT outline.
- Once the outline is ready, the later stages should reuse the current PPT workflow as much as possible.

The user explicitly does **not** want this flow to create or depend on a separate conversation container.
The user requirement does **not** forbid a lightweight non-chat draft entity used to carry outline-stage state into generation.

## Goals

- Provide a visible, structured, non-chat PPT entry point in the workbench.
- Reuse the existing selected-document flow already proven by report entry UX.
- Reuse existing PPT outline/content/html2ppt generation components wherever possible.
- Keep generated PPT artifacts appearing in the same right-side generated-files area and course-material persistence path.
- Keep the source scope explicit and bounded to selected documents plus user-entered PPT config.

## Non-Goals

- Replacing the existing chat-based PPT generation workflow.
- Adding web search or free-form conversation context into this new entry in v1.
- Rebuilding the html2ppt engine.
- Introducing a new cross-session conversation state machine for the workbench flow.
- Designing a complex recommendation-card system for PPT in v1.

## Approaches Considered

### Approach A: Dedicated workbench PPT entry plus direct PPT draft/execute APIs

Frontend owns the explicit setup flow. Backend exposes PPT-specific direct endpoints for:

- draft preparation
- draft confirmation and generation

The backend reuses existing PPT internals after the explicit setup is collected.

Pros:

- Matches the user’s “not via chat context” requirement cleanly.
- Keeps the right workbench in control of setup and outline confirmation.
- Avoids hidden chat coupling.
- Easy to reason about source boundaries.

Cons:

- Requires new API schemas and service layer glue.
- Some PPT runtime logic must be extracted into reusable internal helpers.

### Approach B: Frontend explicit form but submit a hidden synthetic chat request

Frontend still collects structured config, but backend converts it into a hidden chat request that enters the current `/api/chat/v2/reply` or PPT workflow route.

Pros:

- Lower initial backend surface area.
- Reuses more of the current workflow wrapper.

Cons:

- Violates the spirit of “not through conversation”.
- Makes debugging harder because the workbench UI would secretly depend on chat state.
- Creates awkward coupling between a direct tool flow and a chat-oriented workflow contract.

### Approach C: Fully separate direct PPT generation pipeline

Build an entirely new direct PPT engine path from explicit config to outline to content to html2ppt.

Pros:

- Maximum isolation.
- Could be optimized specifically for workbench usage.

Cons:

- Duplicates current PPT workflow logic.
- High maintenance risk.
- Most likely to drift from the existing PPT experience.

## Recommendation

Choose **Approach A**.

It best matches the user request:

- explicit workbench entry
- no conversation dependency
- same downstream PPT generation behavior

It also gives us a clean pattern parallel to report direct-entry services without forcing PPT generation to piggyback on hidden chat state.

## Proposed UX

### Entry Point

Add a new explicit PPT setup trigger to the existing right-side workbench card area in `StudioPanel`.

Expected user action:

- Click `生成PPT` or the PPT card’s configure action.

### Preconditions

- At least one knowledge-base document must be selected.
- If no documents are selected, show an inline warning similar to the current report entry flow.

### Modal / Panel Flow

Introduce a dedicated workbench setup surface with a neutral component name such as:

- `PptEntryPanel`
- `PptDraftPanel`
- `PptEntryWorkbench`

V1 may render this as a modal for speed, but the interaction should be designed so it can later expand into an inline workbench panel without changing the domain model.

Expected states:

- `idle`
- `configuring`
- `outline_loading`
- `outline_ready`
- `generating`
- `completed`
- `error`

### Required Input Fields

V1 should support the smallest useful set of explicit PPT controls:

- `deck_title`
- `audience`
- `objective`
- `theme_id`
- `target_slide_count`
- `key_points`

Optional but recommended:

- `deck_subtitle`
- `style_hint`
- `notes_to_avoid` or `special_requirements`

Field notes:

- Use `deck_title` only. Do not expose both `topic` and `deck_title` in v1.
- `key_points` should be collected as a list, not one large free-form blob.
- `target_slide_count` should be treated as a soft target with bounded deviation, not a strict hard-equals count.
- `theme_id` should mean the visual template/theme used by html2ppt.
- `style_hint` should mean the content-expression style, not the visual theme.

### Interaction Rules

- The user-selected documents remain the only knowledge input.
- The form configuration acts as strong hints for outline generation.
- The outline preview is shown in the workbench setup surface before generation.
- The user can:
  - confirm and generate
  - go back and edit config
- Final PPT result appears in the same generated-files list and preview area as today.

## Backend Design

### New API Surface

Add PPT direct-entry endpoints parallel to the report direct-entry pattern.

Recommended endpoints:

- `POST /api/chat/v2/ppt/outline`
- `POST /api/chat/v2/ppt/generate`

Why two endpoints:

- the first produces and stores a direct PPT draft from selected docs plus config
- the second confirms that draft and triggers the current generation path

This keeps outline review explicit and avoids hidden workflow transitions.

Naming note:

- Keeping these routes under `/api/chat/v2/` is acceptable in v1 because it reuses the current auth, envelope, and trace conventions.
- Domain-wise this flow is a workbench direct action, not a conversation action.
- A future migration to a namespace like `/api/workbench/v1/ppt/*` should remain possible without changing the core domain model.

### Request/Response Shapes

#### `POST /api/chat/v2/ppt/outline`

Request should include:

- `course_id`
- `selected_doc_ids`
- `ppt_config`

`ppt_config` v1 fields:

- `deck_title`
- `deck_subtitle`
- `audience`
- `objective`
- `theme_id`
- `target_slide_count`
- `key_points`
- `style_hint`
- `special_requirements`

Response should include:

- `action.name = generate.ppt.outline.direct`
- `draft_id`
- `outline_artifact`
- `trace.path = direct`
- normalized `ppt_config`
- selected document snapshot metadata
- optional `outline_preview`

#### `POST /api/chat/v2/ppt/generate`

Request should include:

- `draft_id`
- optional edited `outline`
- explicit confirm flag

Why `draft_id` instead of resubmitting the full payload:

- keeps outline-stage and generation-stage inputs consistent
- prevents the frontend from accidentally drifting document selection or config between steps
- gives the backend a natural retry/resume anchor
- makes trace/debugging much easier

Response should mirror the current PPT workflow execution model, not a fake synchronous one:

- `action.name = generate.ppt.direct`
- `run_id`
- `workflow` or direct-run status
- `artifacts` when available
- `trace`

The main returned final artifact should stay compatible with existing `ppt_deck` handling in the frontend and course-material sync layer.
The request should start an asynchronous run that the frontend can poll or observe, rather than holding a single HTTP request open until final completion.

## Internal Service Layer

### New Services

Add direct-service classes analogous to report direct-entry services:

- `KnowledgeBaseDirectPptOutlineServiceV2`
- `KnowledgeBaseDirectPptGenerationServiceV2`
- a lightweight draft store/repository for direct PPT drafts

### Reused Existing Components

The direct PPT services should reuse these current building blocks rather than duplicate them:

- `KnowledgeBaseSummaryProvider` or document content provider
- `PptContextOrganizer` only if it can operate solely from selected docs plus explicit config
- `PptOutlineBuilder`
- `PptContentMarkdownGenerator`
- `PptContentGate`
- `Html2PptClient`
- existing artifact persistence logic for PPT course materials

Important boundary:

- reuse **PPT capability-layer components**
- do not reuse chat-specific request ingestion, chat memory assembly, chat readiness heuristics, or chat response assembly

### Required Refactor

Extract the “post-outline execution” part of `PptWorkflowRuntime` into a reusable lower-level executor, for example:

- `PptPostOutlineExecutor`
- `PptGenerationOrchestrator`
- `PptArtifactPipeline`

Reason:

- chat workflow and workbench direct flow should share the same post-outline execution path
- we want one implementation for:
  - content markdown generation
  - content validation/gating
  - html2ppt submission
  - polling
  - artifact shaping
  - persistence

This executor should sit below both:

- chat workflow shell
- workbench direct-entry shell

The direct path must not reuse the chat wrapper itself.

### Source Boundary

This direct PPT flow must not read:

- chat summary
- recent messages
- active conversation context

It may only use:

- selected document summaries/content
- explicit user PPT config

This boundary should be visible in trace/debug metadata.

Recommended trace fields:

- `source_scope = selected_documents_only`
- `uses_chat_context = false`
- `draft_id`
- `selected_doc_snapshot_id`

## Direct Draft State Model

Introduce a lightweight `DirectPptDraft` domain object.

Suggested fields:

- `draft_id`
- `course_id`
- `selected_doc_ids`
- `selected_doc_snapshot_id`
- `selected_doc_snapshot`
- `normalized_ppt_config`
- `draft_outline`
- `status`
- `trace`
- `created_by`
- `created_at`
- `updated_at`

Status examples:

- `draft_created`
- `outline_ready`
- `generation_queued`
- `generation_running`
- `completed`
- `failed`

This object is not a conversation. It is a workbench generation draft.

## Outline Generation Strategy

The outline step should behave like a compact non-chat preparation stage.

Input synthesis:

- selected document summaries provide factual basis
- explicit PPT config provides:
  - audience
  - teaching goal
  - expected length
  - emphasized points
  - theme preference

Output:

- a normal `PptOutline` object compatible with the current PPT generation pipeline

The prompt should explicitly state that the outline comes from:

- selected documents
- teacher-provided PPT settings

and must not assume any extra dialogue context.

Input validation in this direct path should be treated as structured completeness validation, not chat-style readiness inference.

Examples:

- selected docs must be non-empty
- required config fields must be present
- `target_slide_count` must be in a valid range
- `theme_id` must be supported
- document snapshot must be resolvable

## Frontend Integration

### New Component

Add a new PPT entry surface next to the report entry UX.

Recommended component naming should stay neutral to presentation form:

- `PptEntryPanel.tsx`
- `PptDraftPanel.tsx`

V1 may still render it as a modal if that is fastest to ship.

Responsibilities:

- validate document selection
- collect PPT config
- call outline endpoint
- render outline preview
- submit confirmed outline
- show loading/error states

### StudioPanel Wiring

In `StudioPanel`:

- route PPT configure/generate clicks to the new PPT entry surface
- preserve current report flow unchanged
- on successful PPT generation:
  - convert backend response to generated files
  - add generated file to store
  - set current preview file
  - refresh course materials

### Shared Helpers

Add PPT-specific helpers similar in style to `reportEntry.helpers.ts`:

- build request payload
- normalize `ppt_config`
- map outline preview sections for UI

Possible file:

- `src/services/teacher/pptEntry.helpers.ts`

## Document Snapshot Consistency

This direct flow depends heavily on the selected document set, so snapshot consistency must be explicit.

Rules:

- outline creation records the exact `selected_doc_ids`
- backend also records a `selected_doc_snapshot_id`
- if document summaries/content are versioned, store the version metadata alongside the draft
- generation must default to the exact snapshot captured at outline time
- if the user changes the selected document set after outline creation, the UI must require regenerating the outline instead of silently reusing the old draft

This prevents a mismatch where outline and final deck are based on different documents.

## Persistence and Generated Files

The final PPT result should continue to land in the existing generated-files and course-material pathways.

Requirements:

- generated file type stays `ppt`
- preview continues to use current PPT preview URL resolution
- completed artifacts persist into course materials with the same material type

No new storage category is needed for v1.

## Error Handling

### User Errors

- no selected documents
- missing required PPT fields
- invalid slide count

These should be caught in the workbench entry surface before API submission when possible.

### Backend Errors

- selected documents missing or inaccessible
- outline generation failure
- html2ppt unavailable
- PPT generation timeout

Response style should match the current v2 direct/report error envelope style.

### Partial Success

If outline generation succeeds but final PPT generation fails:

- keep the outline visible in the entry surface
- allow retrying generation without re-entering all config

## Execution Model

The generation stage should remain asynchronous and task-oriented.

Recommended sequence:

1. `POST /ppt/outline` creates `DirectPptDraft`
2. `POST /ppt/generate` confirms the draft and creates a run
3. frontend polls run status
4. completed artifacts are written into the existing generated-files/course-material flow

This should not be implemented as a long blocking request that waits for `html2ppt` to finish before responding.

## Trace and Observability

Add direct-flow trace markers so debugging remains straightforward.

Suggested trace fields:

- `path = direct`
- `workflow_name = ppt_direct_entry`
- `draft_id`
- `run_id`
- `selected_doc_count`
- `summary_doc_count` or `content_doc_count`
- `ppt_config`
- `outline_generation_mode`
- `generation_mode`
- `source_scope = selected_documents_only`

## Testing Plan

### Frontend

- `StudioPanel` opens the PPT entry surface only when docs are selected
- entry surface validates required fields
- outline request payload includes selected docs plus `ppt_config`
- confirm action sends outline plus config to generate endpoint
- successful response adds a `ppt` generated file and opens preview

### Backend

- schema tests for new PPT direct request/response models
- route tests for new endpoints
- direct outline service tests:
  - rejects empty `selected_doc_ids`
  - builds outline from docs plus config
  - does not depend on conversation context
- direct generation service tests:
  - accepts `draft_id`
  - reuses post-outline executor path
  - returns `ppt_deck` artifact on success
  - persists course material on success
  - refuses generation when document snapshot has been invalidated

### Regression

- current chat-based PPT workflow remains unchanged
- current report entry and direct report flows remain unchanged

## Rollout Plan

### Phase 1

- add backend schemas, routes, and direct services
- add direct draft store/repository
- add frontend workbench entry surface and wiring
- support minimal config fields
- reuse current PPT pipeline after outline confirmation through a shared executor

### Phase 2

- add richer PPT presets or recommendations
- add config persistence within the workbench session
- optionally add template-specific guidance or smart defaults from selected docs

## Risks

- Duplicating too much PPT runtime logic if outline submission is not properly extracted.
- Letting direct PPT entry silently drift from the existing chat PPT behavior.
- Overloading v1 with too many form fields and making the entry surface harder to use than chat.

## Recommended Implementation Shape

### Backend

- add new schema models in `app/chat/api/schemas_v2.py`
- add new routes in `app/chat/api/routes_v2.py`
- add new direct services under `app/chat/application/`
- add a lightweight direct PPT draft repository/store
- extract shared post-outline execution logic from `PptWorkflowRuntime` into a lower-level executor

### Frontend

- add `src/components/teacher/PptEntryPanel.tsx` or equivalent
- add `src/services/teacher/pptEntry.helpers.ts`
- add request helpers in `src/services/teacher/chatV2.ts`
- wire `StudioPanel.tsx` PPT button to the entry surface

## Must-Fix Clarifications From Review

- “No conversation dependency” means no chat context dependency, not “no intermediate state”.
- The two-step API should be `draft_id` based, not independent stateless full-payload re-submission.
- Shared reuse should happen at the PPT capability/executor layer, not by reusing the chat workflow shell.
- The frontend entry should be designed as a workbench setup surface first, modal second.
- Generation should stay task-oriented and asynchronous.
- Document snapshot consistency must be explicit across outline and generation phases.

## Open Questions Resolved For This Spec

- Should this direct entry depend on chat conversation context?

Resolved: **No chat conversation dependency. Use a direct PPT draft/run object instead.**

- Should downstream PPT generation stay aligned with the current PPT workflow?

Resolved: **Yes. Reuse the existing post-outline generation path through a shared lower-level executor.**

## Final Recommendation

Build a **direct workbench PPT entry with a two-step direct API**:

1. selected documents + explicit PPT config -> draft outline
2. confirm outline -> run the existing PPT generation path

This is the cleanest way to satisfy the user request while preserving current PPT generation behavior and minimizing long-term divergence.
