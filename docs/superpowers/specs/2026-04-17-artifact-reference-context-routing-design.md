# Artifact Reference Context Routing Design

## Goal

When a user clicks "添加到对话" on a generated artifact, later chat turns should treat that artifact as the default working context. The system must support both:

- discussing the referenced artifact
- modifying the referenced artifact

The reference should persist across normal follow-up turns, but it must yield when the user explicitly exits, switches tasks, or selects a different artifact.

This revision changes the decision layer from rule-priority routing to model-priority routing. The system should use a model to decide whether the current turn is discussion, modification, exit, or switch, while still reusing the existing report and PPT edit runtimes as the execution layer.

## Scope

This change is limited to the teacher chat V2 artifact-reference flow.

In scope:

- keep artifact reference active across later turns
- classify turns around a referenced artifact with a model-first intent classifier
- distinguish `discuss_current_artifact` from `edit_current_artifact`
- clear or switch artifact context on explicit or model-confirmed user intent
- sync backend state and frontend reference card after clear or switch
- keep existing edit runtimes as the execution path after classification

Out of scope:

- multi-artifact simultaneous editing
- replacing report or PPT edit runtimes
- allowing the model to invent a new artifact reference not present in the request or conversation state
- redesigning the "添加到对话" UI entry

## Current State

The existing flow already has the right primitives:

- frontend sends `artifact_reference` in chat V2 requests
- chat panel restores `artifact_reference` from conversation detail
- backend stores `artifact_reference`, `active_artifact`, and `referenced_artifact_ids`
- `ReplyServiceV2` can route referenced report artifacts into `ReportEditRuntime`
- `ReplyServiceV2` can route referenced PPT artifacts into `PptEditRuntime`

The current missing layer is semantic routing for later turns. The first implementation filled this gap with a deterministic resolver based on edit and exit keywords. That is not sufficient for the desired behavior because the user wants modification handling to be model-driven rather than keyword-driven.

The new target state is:

- the model decides whether the turn is discussion, modification, exit, or switch
- the backend keeps final control over which downstream runtime executes
- editing execution still happens inside the existing report and PPT edit runtimes

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

### 2. Model-priority artifact intent classifier

Add an `artifact_intent_classifier` before the existing `ReplyServiceV2` edit-runtime dispatch.

The classifier is responsible only for intent understanding. It does not directly rewrite content or mutate artifacts. It returns one of four structured outcomes:

- `discuss_current_artifact`
- `edit_current_artifact`
- `switch_artifact`
- `exit_artifact_context`

The main service then maps those outcomes onto the existing execution paths:

- `discuss_current_artifact` -> normal chat path with artifact context injected
- `edit_current_artifact` -> existing report or PPT edit runtime
- `switch_artifact` -> update reference state, then continue routing
- `exit_artifact_context` -> clear reference state, then continue through normal chat

This keeps intent interpretation model-driven while preserving deterministic backend execution boundaries.

### 3. Model input contract

The classifier should not receive the full artifact body by default. It should receive compact but decision-useful context:

- `question`: current user message
- `artifact_reference`: `artifact_id`, `artifact_type`, `title`, `version_id`
- `active_artifact`: current active artifact from conversation state
- `artifact_summary`:
  - report: title, section headings, and a compact summary or excerpt
  - PPT: deck title, slide titles, and compact summary for the most relevant slide or referenced area
- `conversation_hint`: compact summary of the last 1 to 3 artifact-related turns

Goals of this contract:

- give the model enough context to disambiguate "explain" vs "modify"
- control prompt size
- make testing and fallback behavior stable

### 4. Model output contract

The classifier must return fixed JSON rather than free-form text.

Example:

```json
{
  "action": "edit_current_artifact",
  "confidence": "high",
  "reason": "The user explicitly asks to shorten the title of slide 2 in the current referenced deck.",
  "target_hint": {
    "artifact_type": "ppt_deck",
    "target_locator": "slide:2"
  }
}
```

Allowed values:

- `action`
  - `discuss_current_artifact`
  - `edit_current_artifact`
  - `switch_artifact`
  - `exit_artifact_context`
- `confidence`
  - `high`
  - `medium`
  - `low`

`target_hint` is optional. In the first iteration it is advisory only and should not be treated as an executable command.

### 5. Routing and fallback strategy

The backend remains the source of truth for what actually happens after classification.

Routing rules:

- if classifier output is valid and `confidence` is `high`, follow the returned `action`
- if classifier output is valid but confidence is `medium` or `low`, default to `discuss_current_artifact`
- if classifier output is invalid JSON, times out, or the model call fails, default to `discuss_current_artifact`
- only `exit_artifact_context` clears the current artifact reference
- `switch_artifact` is only allowed when the current request already carries a new `artifact_reference`; the model must not invent a new artifact target

This fallback policy is intentionally conservative. A failure should result in "did not modify" rather than "modified the wrong artifact".

### 6. Discussion path behavior

For `discuss_current_artifact`, the request should stay on the normal chat path rather than entering an edit runtime.

The normal chat path should be enriched with compact artifact context:

- artifact type
- artifact title
- artifact id
- current version id if present
- compact summary or preview excerpt if available

This keeps the assistant grounded in the referenced artifact while preserving normal conversational behavior.

### 7. Edit path behavior

For `edit_current_artifact`, the classifier only decides that the turn is a modification request. The system should then reuse the current edit execution chain:

- report-like artifacts -> `ReportEditRuntime`
- PPT-like artifacts -> `PptEditRuntime`

In this phase, the classifier does not replace the runtime-specific execution logic. It changes the decision layer, not the edit engine.

That means:

- report content rewriting can continue using the existing model-backed report editing flow
- PPT revisions can continue using the current PPT revision flow
- future work may let the classifier or a second model produce richer structured edit intent, but that is not required in this phase

### 8. Backend integration points

Primary backend changes:

- replace or bypass the deterministic artifact-context resolver with a model-priority classifier module
- invoke it in `reply_service_v2.py` before the current `artifact_reference -> edit_runtime` branch
- extend conversation-state patching so exit and switch outcomes update stored reference state cleanly
- expose the updated reference state in conversation detail and response state payloads already consumed by the frontend

Behavioral contract:

- discussion about a referenced artifact stays in chat
- modification of a referenced artifact stays in existing edit runtimes
- explicit or model-confirmed exit clears context immediately
- switch updates context only when backed by an actual incoming reference

### 9. Frontend integration points

Frontend changes should stay minimal:

- keep the existing reference card in `ChatPanel.tsx`
- continue sending `artifact_reference` while the reference card is active
- when backend state says the reference was cleared or switched, sync the store so the card updates immediately
- preserve current "移除引用" manual control as the highest-confidence explicit user action

### 10. Testing

Add focused tests around classification, routing, and state sync.

Backend tests:

- referenced report + "这份报告的核心观点是什么" -> classifier returns discussion, normal chat path, not report edit runtime
- referenced report + "把第三部分扩写一下" -> classifier returns edit, report edit runtime executes
- referenced PPT + "第 2 页标题改短一点" -> classifier returns edit, PPT edit runtime executes
- active reference + "不要基于这个了，我们聊课程目标" -> classifier returns exit, context cleared, normal chat
- existing reference + request carries a new `artifact_reference` -> classifier may return switch, state updates to the new artifact
- classifier returns invalid JSON or low confidence -> no edit runtime execution, stay on discussion path

Frontend tests:

- reference card persists across normal follow-up send
- backend-cleared reference updates store and hides card
- newly selected artifact replaces previous reference in store

## Risks

Main risks:

- the classifier may over-call edit intent for analysis requests
- the classifier may under-call edit intent for vague rewrite requests
- model output may be malformed or too uncertain to trust directly
- state may drift between backend-cleared context and frontend-held reference card

Mitigations:

- keep the output contract strict and machine-validated
- treat low-confidence and malformed output as discussion, not edit
- keep backend response state as the source of truth for frontend reference sync
- keep `switch_artifact` constrained by the actual incoming request payload

## Files

- `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- `Edu_AI/api/Edu_AI/app/chat/orchestrator/artifact_context_resolver.py` or a replacement classifier module nearby
- `Edu_AI/api/Edu_AI/app/chat/persistence/conversation_store_adapter.py`
- `Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
- `Edu_AI/src/components/teacher/ChatPanel.tsx`
- `Edu_AI/src/services/teacher/chatV2.ts`
- related backend and frontend tests
