# Artifact Reference Context Routing Design

## Goal

When a user clicks "添加到对话" on a generated artifact, later chat turns should treat that artifact as the default working context. The system must support both:

- discussing the referenced artifact
- modifying the referenced artifact

The reference should persist across normal follow-up turns, but it must yield when the user explicitly exits, switches tasks, or selects a different artifact.

## Scope

This change is limited to the teacher chat V2 artifact-reference flow.

In scope:

- keep artifact reference active across later turns
- distinguish "discuss current artifact" from "edit current artifact"
- clear or switch artifact context on explicit user intent
- sync backend state and frontend reference card after clear or switch
- cover existing supported artifact types already handled by edit runtimes

Out of scope:

- multi-artifact simultaneous editing
- free-form LLM-only intent classification
- new artifact editing runtimes
- redesigning the "添加到对话" UI entry

## Current State

The existing flow already has the right primitives:

- frontend sends `artifact_reference` in chat V2 requests
- chat panel restores `artifact_reference` from conversation detail
- backend stores `artifact_reference`, `active_artifact`, and `referenced_artifact_ids`
- `ReplyServiceV2` routes referenced report artifacts into `ReportEditRuntime`
- `ReplyServiceV2` routes referenced PPT artifacts into `PptEditRuntime`

The missing layer is semantic routing for later turns. Right now a referenced artifact is mainly treated as an edit target. The system lacks an explicit decision between:

- asking about the current artifact
- modifying the current artifact
- leaving the artifact context
- switching to another artifact or task

## Design

### 1. Persistent reference model

Keep the current split of responsibilities:

- `artifact_reference`: the user-visible explicit reference carried by the frontend
- `active_artifact`: the backend-selected active artifact for the current conversation state
- `referenced_artifact_ids`: conversation memory of artifact usage

Rules:

- after "添加到对话", the frontend continues sending the current `artifact_reference`
- normal follow-up questions keep the current artifact context
- selecting another artifact replaces the previous reference
- explicit exit commands clear both `artifact_reference` and active artifact context

### 2. Deterministic artifact-context resolver

Add a small deterministic resolver before the existing `ReplyServiceV2` edit-runtime dispatch.

The resolver returns one of four outcomes:

- `discuss_current_artifact`
- `edit_current_artifact`
- `switch_artifact`
- `exit_artifact_context`

Priority:

1. explicit clear or exit commands
2. explicit new artifact reference in the current request
3. high-confidence edit commands against the active artifact
4. default discussion around the active artifact

This first iteration should stay rule-based rather than model-based.

### 3. Intent rules

#### `exit_artifact_context`

Trigger only on explicit phrases such as:

- 不要基于这个了
- 清除引用
- 移除引用
- 不看这个了
- 我们聊别的
- 新开话题

Effect:

- clear `artifact_reference`
- clear `active_artifact`
- allow downstream routing to treat the turn as normal chat or normal workflow switching

#### `switch_artifact`

Trigger when the request contains a different `artifact_reference` than the current conversation state.

Effect:

- replace stored `artifact_reference`
- replace `active_artifact`
- continue with normal downstream handling for the new artifact

#### `edit_current_artifact`

Trigger on strong edit verbs or rewrite commands, such as:

- 修改
- 重写
- 改写
- 扩写
- 精简
- 删除
- 调整结构
- 改标题
- 合并
- 拆分
- 补充

Effect:

- if artifact type is report or report outline, reuse `ReportEditRuntime`
- if artifact type is PPT-related, reuse `PptEditRuntime`

#### `discuss_current_artifact`

Default when an artifact reference is active and the user is still talking about it without strong edit intent.

Examples:

- 这份报告的核心观点是什么
- 这部分逻辑有什么问题
- 这一页想表达什么
- 不够具体，再展开一点

Effect:

- do not enter edit runtime
- route through normal chat
- inject compact artifact context so the assistant knows which artifact is being discussed

### 4. Chat-context injection for discussion turns

For `discuss_current_artifact`, enrich the normal chat path with compact artifact context instead of forcing an edit workflow.

The injected context should include:

- artifact type
- artifact title
- artifact id
- current version id if present
- a compact summary or preview excerpt if already available in state or persisted material

This keeps the answer grounded in the referenced artifact while preserving normal conversational behavior.

### 5. Backend integration points

Primary backend changes:

- add an artifact-context resolver module near routing/orchestration logic
- invoke it in `reply_service_v2.py` before the current `artifact_reference -> edit_runtime` branch
- extend conversation-state patching so exit and switch outcomes update stored reference state cleanly
- expose the updated reference state in conversation detail and response state payloads already consumed by the frontend

Behavioral contract:

- discussion about a referenced artifact stays in chat
- modification of a referenced artifact stays in existing edit runtimes
- explicit exit clears context immediately
- explicit switch replaces context immediately

### 6. Frontend integration points

Frontend changes should stay minimal:

- keep the existing reference card in `ChatPanel.tsx`
- continue sending `artifact_reference` while the reference card is active
- when backend state says the reference was cleared or switched, sync the store so the card updates immediately
- preserve current "移除引用" manual control as the highest-confidence user action

### 7. Testing

Add focused tests around routing and state sync.

Backend tests:

- referenced report + "这份报告的核心观点是什么" -> discussion path, not report edit runtime
- referenced report + "把第三部分扩写一下" -> report edit runtime
- referenced PPT + "第2页标题改短一点" -> PPT edit runtime
- active reference + "不要基于这个了，我们聊课程目标" -> context cleared, normal chat
- existing reference + new referenced artifact in request -> switch context

Frontend tests:

- reference card persists across normal follow-up send
- backend-cleared reference updates store and hides card
- newly selected artifact replaces previous reference in store

## Risks

Main risks:

- over-matching normal explanation requests as edit intent
- under-matching vague modification requests and falling back to discussion
- state drift between backend-cleared context and frontend-held reference card

Mitigations:

- keep edit detection limited to strong verbs in the first iteration
- keep exit detection explicit only
- use backend response state as the source of truth for frontend reference sync

## Files

- `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- `Edu_AI/api/Edu_AI/app/chat/orchestrator/route_rules.py` or a nearby new resolver module
- `Edu_AI/api/Edu_AI/app/chat/persistence/conversation_store_adapter.py`
- `Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
- `Edu_AI/src/components/teacher/ChatPanel.tsx`
- `Edu_AI/src/services/teacher/chatV2.ts`
- related backend and frontend tests
