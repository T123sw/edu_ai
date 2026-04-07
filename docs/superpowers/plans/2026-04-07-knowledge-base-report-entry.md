# Knowledge-Base Report Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a NotebookLM-style report-generation entry for the teacher studio so users can choose preset or summary-driven recommended report cards, edit a prefilled Chinese prompt, and generate a report from selected knowledge-base documents without reading conversation context.

**Architecture:** Add a dedicated `report/cards` backend endpoint that resolves selected-document summaries, applies lightweight recommendation rules plus short-lived caching, and returns a unified card model. Keep final report generation on `/api/chat/v2/report`, but introduce `entry_mode = "knowledge_base_report"` so the backend explicitly ignores conversation state and uses selected documents as the primary generation source while preserving the existing artifact persistence flow.

**Tech Stack:** React, TypeScript, Zustand, Ant Design, FastAPI, Pydantic, existing chat v2/report workflow runtime, `new_rag` document summary APIs, pytest, lightweight Node-based frontend tests.

---

## Implementation Scope

This plan covers one coherent subsystem:

- Knowledge-base report card entry UI
- Summary-driven recommendation endpoint
- Knowledge-base-specific report generation contract
- Explicit isolation from chat-context report flow

It does **not** include:

- Chat-driven report generation changes
- Multi-language support
- User-managed custom preset libraries
- Recommendation history persistence

## Current Touchpoints

### Frontend

- `Edu_AI/src/components/teacher/StudioPanel.tsx`
  - Current report entry opens the generic config modal and submits `sendReportV2(...)`.
- `Edu_AI/src/services/teacher/chatV2.ts`
  - Current `/api/chat/v2/report` request client.
- `Edu_AI/src/services/teacher/chatV2.helpers.ts`
  - Current report prompt assembly still references “当前会话”.
- `Edu_AI/src/store/teacher/useStore.ts`
  - Holds `selectedDocs`, generated files, preview state.
- `Edu_AI/src/services/rag.ts`
  - Shows document list/summary capabilities already exist in the frontend layer, even though recommendation logic should live on the backend.

### Backend

- `Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`
  - Current `/api/chat/v2/reply` and `/api/chat/v2/report` entry points.
- `Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
  - Current v2 request/response contracts.
- `Edu_AI/api/Edu_AI/app/chat/application/report_service_v2.py`
  - Current report workflow orchestration and persistence.
- `Edu_AI/api/Edu_AI/new_rag/api.py`
  - Existing document list and summary generation capabilities.
- `Edu_AI/api/Edu_AI/new_rag/system.py`
  - Existing `list_documents(...)` and `summarize_document(...)`.

## File Map

### Frontend files to create

- `Edu_AI/src/components/teacher/ReportEntryModal.tsx`
  - Two-step report card modal UI, including cards screen and prompt editor screen.
- `Edu_AI/src/services/teacher/reportEntry.helpers.ts`
  - Preset card definitions, card-to-editor mapping, editor dirty-check rules, local state helpers.
- `Edu_AI/tests/frontend/reportEntry.helpers.test.ts`
  - Card model helper coverage.
- `Edu_AI/tests/frontend/studioPanel.report-entry.test.ts`
  - Entry wiring, loading state, modal screen switching, and generate payload coverage.

### Frontend files to modify

- `Edu_AI/src/components/teacher/StudioPanel.tsx`
  - Replace the old report config modal flow with the new report-entry modal flow.
- `Edu_AI/src/services/teacher/chatV2.ts`
  - Add report-card request/response types and `fetchReportEntryCardsV2(...)`.
- `Edu_AI/src/services/teacher/chatV2.helpers.ts`
  - Replace conversation-based report question assembly with knowledge-base entry helpers for the new flow.

### Backend files to create

- `Edu_AI/api/Edu_AI/app/chat/application/report_entry_cards_service_v2.py`
  - Builds fixed cards plus summary-driven recommended cards and cache lookup.
- `Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_summary_provider.py`
  - Resolves selected document summaries via `new_rag`, applies missing-summary fallback, and returns summary metadata for caching.
- `Edu_AI/api/Edu_AI/tests/chat/test_report_entry_cards_service_v2.py`
  - Recommendation rules, caching, and fallback coverage.

### Backend files to modify

- `Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
  - Add report-card endpoint contracts and knowledge-base report request fields.
- `Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`
  - Add `POST /api/chat/v2/report/cards`.
- `Edu_AI/api/Edu_AI/app/chat/application/report_service_v2.py`
  - Honor `entry_mode`, ignore conversation context for knowledge-base entry requests, and preserve trace metadata.
- `Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`
  - Add route coverage for the new cards endpoint.
- `Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py`
  - Add contract coverage for new request/response models.
- `Edu_AI/api/Edu_AI/tests/chat/test_report_service_v2.py`
  - Add isolation coverage for `entry_mode = "knowledge_base_report"`.

## Interface Contract

### 1. Cards endpoint

Route:

`POST /api/chat/v2/report/cards`

Request:

```json
{
  "course_id": "course-1",
  "selected_doc_ids": [
    "user_t123:D:/storage/file-a.pdf",
    "user_t123:D:/storage/file-b.pdf"
  ]
}
```

Response:

```json
{
  "entry_mode": "knowledge_base_report",
  "cards": [
    {
      "card_id": "preset-brief",
      "card_type": "preset",
      "title": "简要报告",
      "description": "快速提炼材料主旨、关键结论与核心依据。",
      "prompt_draft": "请基于已选文档，生成一份中文简要报告，提炼核心主题、关键结论和主要依据，结构清晰，篇幅适中。",
      "preset_key": "brief"
    },
    {
      "card_id": "rec-comparison",
      "card_type": "recommended",
      "title": "关键观点对比",
      "description": "比较不同材料在核心观点和适用场景上的异同。",
      "prompt_draft": "请基于已选文档，生成一份中文对比分析报告，重点比较各材料在核心观点、方法路径、适用场景和局限性上的异同，并给出归纳结论。",
      "recommendation_type": "comparison",
      "recommendation_source": "doc_summaries",
      "fit_score": "high"
    }
  ],
  "trace": {
    "cache_hit": true,
    "selected_doc_count": 2,
    "summary_doc_count": 2,
    "fallback_used": false
  }
}
```

### 2. Unified card model

Frontend and backend should share the same logical shape:

```ts
type ReportEntryCard = {
  card_id: string;
  card_type: 'preset' | 'recommended';
  title: string;
  description: string;
  prompt_draft: string;
  preset_key?: 'brief' | 'detailed' | 'study_plan' | 'custom';
  recommendation_type?:
    | 'summary'
    | 'comparison'
    | 'risk_analysis'
    | 'teaching_suggestion'
    | 'study_focus'
    | 'theme_outline';
  recommendation_source?: 'doc_summaries';
  fit_score?: 'high' | 'medium' | 'low';
};
```

### 3. Final report request additions

Keep the existing `/api/chat/v2/report` route, but extend the payload:

```json
{
  "entry_mode": "knowledge_base_report",
  "course_id": "course-1",
  "selected_doc_ids": [
    "user_t123:D:/storage/file-a.pdf"
  ],
  "question": "请基于已选文档，生成一份中文简要报告，提炼核心主题、关键结论和主要依据，结构清晰，篇幅适中，并更强调教学启发。",
  "prompt_draft": "请基于已选文档，生成一份中文简要报告，提炼核心主题、关键结论和主要依据，结构清晰，篇幅适中。",
  "final_user_prompt": "请基于已选文档，生成一份中文简要报告，提炼核心主题、关键结论和主要依据，结构清晰，篇幅适中，并更强调教学启发。",
  "selected_card": {
    "card_id": "preset-brief",
    "card_type": "preset",
    "preset_key": "brief"
  },
  "report_config": {
    "title": null,
    "focus_areas": [],
    "source_scope": "selected_documents_only"
  }
}
```

Rules:

- `prompt_draft` is the system-provided default draft.
- `final_user_prompt` is the user-edited final text.
- Final generation uses `final_user_prompt` as the primary instruction.
- `prompt_draft` is retained for trace/debugging and must not be appended again if `question` already equals `final_user_prompt`.

### 4. Summary vs generation input boundary

- Recommendation layer reads selected-document summaries only.
- Final report generation reads the selected documents as the main evidence source.
- Summaries may still be recorded in trace/debug metadata, but they are not the main content payload for the final report.

### 5. Entry-mode isolation rule

Introduce:

```ts
entry_mode = "knowledge_base_report" | "chat_report"
```

Backend rule:

- When `entry_mode == "knowledge_base_report"`, the service must not read conversation snapshot, conversation memory, or active context.
- If a `conversation_id` is present in the request, the service should keep it only for persistence compatibility and ignore it as an input source.

## Recommendation Rules

### Single-document bias

- Prioritize `summary`, `study_focus`, `theme_outline`, `teaching_suggestion`
- Down-rank `comparison`

### Multi-document bias

- Prioritize `comparison`, `risk_analysis`, `teaching_suggestion`
- Still keep one stable summarization-style fallback in the top 4

### Missing-summary fallback

- If some selected documents already have summaries, use those and continue.
- If selected documents are missing summaries, try `summarize_document(..., force_refresh=False)` only for the missing subset.
- If all summary resolution fails, return four generic recommended cards:
  - `核心内容总结`
  - `主题结构梳理`
  - `学习重点提炼`
  - `应用建议整理`

## Cache Design

Use a short-lived in-memory cache inside `report_entry_cards_service_v2.py`.

Cache key:

```txt
hash(sorted(selected_doc_ids) + summary_updated_at_snapshot)
```

TTL:

- 10 minutes is sufficient for the first version.

Invalidation:

- Different selected-doc set
- Any summary update timestamp change
- Service restart

## Frontend State Rules

State machine:

```ts
type ReportEntryState =
  | 'idle'
  | 'cards_loading'
  | 'cards_ready'
  | 'editing_prompt'
  | 'generating'
  | 'completed'
  | 'error';
```

Transition rules:

- `idle -> cards_loading`
  - User clicks “生成报告” with at least one selected document
- `cards_loading -> cards_ready`
  - Cards endpoint succeeds
- `cards_loading -> error`
  - Cards endpoint fails
- `cards_ready -> editing_prompt`
  - User selects a card
- `editing_prompt -> cards_ready`
  - User clicks “返回”
- `editing_prompt -> generating`
  - User clicks “生成报告”
- `generating -> completed`
  - Report response contains at least one generated report artifact
- `generating -> error`
  - Report request fails

Editor behavior:

- Preserve draft text per selected card during the current modal session.
- If the user edits text and switches cards, prompt once before overwriting the active editor value.
- Returning from the editor to the cards screen should preserve the last selected card and draft map until the modal closes.

## Task 1: Add backend contracts and cards route

**Files:**

- Modify: `Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`

- [ ] **Step 1: Write the failing schema and route tests**
  - Add a schema test that instantiates a cards request and cards response.
  - Add a route test that posts to `/api/chat/v2/report/cards` and expects a `cards` array plus `entry_mode = "knowledge_base_report"`.

- [ ] **Step 2: Run the failing backend contract tests**
  - Run: `python -m pytest tests/chat/test_schemas_v2.py tests/chat/test_routes_v2.py -q`
  - Expected: FAIL because cards request/response models and route do not exist yet.

- [ ] **Step 3: Add the new Pydantic models and route**
  - Add:
    - `ChatReportCardsRequestV2`
    - `ReportEntryCardSelectionV2`
    - `ReportEntryCardV2`
    - `ChatReportCardsResponseV2`
  - Extend `ChatReportRequestV2` with:
    - `entry_mode`
    - `prompt_draft`
    - `final_user_prompt`
    - `selected_card`
  - Add `POST /api/chat/v2/report/cards` in `routes_v2.py`.

- [ ] **Step 4: Re-run the contract tests**
  - Run: `python -m pytest tests/chat/test_schemas_v2.py tests/chat/test_routes_v2.py -q`
  - Expected: PASS

## Task 2: Build summary-backed recommendation service

**Files:**

- Create: `Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_summary_provider.py`
- Create: `Edu_AI/api/Edu_AI/app/chat/application/report_entry_cards_service_v2.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_report_entry_cards_service_v2.py`

- [ ] **Step 1: Write the failing recommendation tests**
  - Cover:
    - fixed first-row preset cards
    - single-document recommendation bias
    - multi-document recommendation bias
    - cache hit on identical summary snapshot
    - generic fallback when all summaries are unavailable

- [ ] **Step 2: Run the new recommendation tests**
  - Run: `python -m pytest tests/chat/test_report_entry_cards_service_v2.py -q`
  - Expected: FAIL because the service files do not exist yet.

- [ ] **Step 3: Implement the summary provider**
  - Resolve selected documents from `new_rag.get_rag_system().list_documents(owner=...)`.
  - For missing summaries, call `summarize_document(file_path, force_refresh=False, owner=...)`.
  - Return:
    - resolved summaries
    - `summary_updated_at` snapshot
    - missing/fallback metadata

- [ ] **Step 4: Implement the cards service**
  - Always return the 4 preset cards:
    - `简要报告`
    - `详细报告`
    - `学习方案`
    - `自定义报告`
  - Compute 4 recommended cards from the supported recommendation intent set.
  - Include internal `fit_score`.
  - Apply the short-lived cache using selected docs plus summary timestamps.

- [ ] **Step 5: Re-run the recommendation tests**
  - Run: `python -m pytest tests/chat/test_report_entry_cards_service_v2.py -q`
  - Expected: PASS

## Task 3: Isolate knowledge-base report generation from conversation context

**Files:**

- Modify: `Edu_AI/api/Edu_AI/app/chat/application/report_service_v2.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_report_service_v2.py`

- [ ] **Step 1: Write the failing isolation tests**
  - Add one test proving `entry_mode = "knowledge_base_report"` ignores conversation-derived snapshot content.
  - Add one test proving `prompt_draft` is preserved in trace while final generation uses `final_user_prompt`.

- [ ] **Step 2: Run the report service tests**
  - Run: `python -m pytest tests/chat/test_report_service_v2.py -q`
  - Expected: FAIL because the service does not yet branch on `entry_mode`.

- [ ] **Step 3: Implement the service branch**
  - Normalize `question` from `final_user_prompt or question`.
  - Preserve `prompt_draft`, `selected_card`, and `entry_mode` in trace.
  - When `entry_mode == "knowledge_base_report"`:
    - do not read conversation-derived summary/memory as report input
    - continue to use `selected_doc_ids` and existing artifact persistence flow
    - keep conversation persistence compatible for output history only

- [ ] **Step 4: Re-run the report service tests**
  - Run: `python -m pytest tests/chat/test_report_service_v2.py -q`
  - Expected: PASS

## Task 4: Add frontend contracts and local report-entry helpers

**Files:**

- Modify: `Edu_AI/src/services/teacher/chatV2.ts`
- Modify: `Edu_AI/src/services/teacher/chatV2.helpers.ts`
- Create: `Edu_AI/src/services/teacher/reportEntry.helpers.ts`
- Create: `Edu_AI/tests/frontend/reportEntry.helpers.test.ts`

- [ ] **Step 1: Write the failing frontend helper test**
  - Cover:
    - preset card ordering
    - recommendation card normalization
    - editor draft preservation per `card_id`
    - dirty-check before switching cards

- [ ] **Step 2: Run the helper test**
  - Run: `node --experimental-strip-types Edu_AI/tests/frontend/reportEntry.helpers.test.ts`
  - Expected: FAIL because the helper module does not exist yet.

- [ ] **Step 3: Implement frontend API types and helper functions**
  - Add `fetchReportEntryCardsV2(...)`.
  - Add request/response types matching the backend cards contract.
  - Add helpers:
    - `getDefaultPresetCards()`
    - `buildKnowledgeBaseReportRequest(...)`
    - `createDraftCacheKey(card)`
    - `shouldConfirmCardSwitch(...)`

- [ ] **Step 4: Re-run the helper test**
  - Run: `node --experimental-strip-types Edu_AI/tests/frontend/reportEntry.helpers.test.ts`
  - Expected: PASS

## Task 5: Replace the old report modal flow in StudioPanel

**Files:**

- Create: `Edu_AI/src/components/teacher/ReportEntryModal.tsx`
- Modify: `Edu_AI/src/components/teacher/StudioPanel.tsx`
- Create: `Edu_AI/tests/frontend/studioPanel.report-entry.test.ts`

- [ ] **Step 1: Write the failing StudioPanel entry test**
  - Assert:
    - clicking the report action opens a cards-loading flow instead of the old report config form
    - the first screen shows four preset cards
    - the editor screen does not show a language selector
    - generation uses `entry_mode = "knowledge_base_report"`
    - successful generation still auto-opens the latest report

- [ ] **Step 2: Run the StudioPanel test**
  - Run: `node --experimental-strip-types Edu_AI/tests/frontend/studioPanel.report-entry.test.ts`
  - Expected: FAIL because the new modal/component flow does not exist yet.

- [ ] **Step 3: Implement `ReportEntryModal`**
  - Cards screen:
    - load recommended cards on open
    - show loading, error, and fallback states
  - Editor screen:
    - show selected card title
    - prefill `prompt_draft`
    - preserve per-card editor text in-session
    - no language selector

- [ ] **Step 4: Integrate the modal into `StudioPanel`**
  - Replace the old `configType === 'report'` form path with the new modal flow.
  - Keep existing generated-file insertion and auto-open behavior.
  - Keep the existing simple file ordering behavior intact.

- [ ] **Step 5: Re-run the StudioPanel test**
  - Run: `node --experimental-strip-types Edu_AI/tests/frontend/studioPanel.report-entry.test.ts`
  - Expected: PASS

## Task 6: Verify the end-to-end surface

**Files:**

- No new files required unless verification reveals issues

- [ ] **Step 1: Run targeted frontend tests**
  - Run:
    - `node --experimental-strip-types Edu_AI/tests/frontend/reportEntry.helpers.test.ts`
    - `node --experimental-strip-types Edu_AI/tests/frontend/studioPanel.report-entry.test.ts`
    - `node --experimental-strip-types Edu_AI/tests/frontend/studioPanel.refresh-order.test.ts`
    - `node --experimental-strip-types Edu_AI/tests/frontend/studioPanel.course-material-sync.test.ts`
  - Expected: PASS

- [ ] **Step 2: Run targeted backend tests**
  - Run:
    - `python -m pytest tests/chat/test_schemas_v2.py -q`
    - `python -m pytest tests/chat/test_routes_v2.py -q`
    - `python -m pytest tests/chat/test_report_entry_cards_service_v2.py -q`
    - `python -m pytest tests/chat/test_report_service_v2.py -q`
  - Expected: PASS

- [ ] **Step 3: Run frontend build**
  - Run: `cmd /c npm run build`
  - Working directory: `Edu_AI`
  - Expected: build succeeds without TypeScript or bundling errors.

## Spec Coverage Check

- Card entry layer: covered by Tasks 4-5
- Two-row card model: covered by Tasks 2 and 5
- Summary-driven recommendation: covered by Task 2
- Recommendation fallback and cache: covered by Task 2
- No language selector: covered by Task 5
- Knowledge-base-only context: covered by Task 3
- Final generation still opens the new report: covered by Task 5
- Existing simple file-list behavior remains intact: covered by Task 6 regression verification

## Implementation Notes

- Do not reuse the old `buildReportQuestionFromConfig(...)` string that references “当前会话”.
- Do not route cards recommendation through the chat reply service.
- Keep recommendation generation and final report generation as separate services even if they share some prompt utilities.
- Prefer extracting the modal UI into `ReportEntryModal.tsx` instead of making `StudioPanel.tsx` larger.

## Commit Strategy

Use small commits after each task:

- `feat: add report entry cards contracts`
- `feat: add summary-driven report card service`
- `feat: isolate knowledge-base report generation`
- `feat: add report entry frontend helpers`
- `feat: add report entry modal flow`

