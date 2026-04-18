# Lesson Plan Artifact Reference Design

## Goal

Extend the existing artifact-reference feature so generated lesson plans can be added into the current conversation and used in two modes:

- ask about the referenced lesson plan directly
- edit a specific part of the referenced lesson plan safely

This iteration covers both:

- `lesson_plan`
- `lesson_plan_outline`

## Background

The current artifact-reference flow already supports:

- report ask flow with artifact context injection
- report edit flow with structure-aware target matching
- PPT ask flow with context injection
- conservative PPT edit routing

Generated lesson-plan artifacts already exist in the system, but they are not yet treated as first-class referenced artifacts in the same way.

## Product Principles

### Principle 1: Asking Is the Default

When a lesson-plan artifact is referenced, the system should default to treating the user message as a question about the artifact unless there is clear edit intent.

### Principle 2: Editing Must Be Precise

The system must not rewrite the whole lesson plan when the user is trying to update one field or one teaching step.

The edit flow should:

- identify one target block
- rewrite only that block
- preserve the rest of the artifact unchanged

### Principle 3: Ambiguity Requires Confirmation

If the user request suggests an edit but does not uniquely identify the target, the system must:

- not edit yet
- return candidate targets or ask for clarification

This should match the current report-edit safety model.

## Scope

In scope:

- support lesson-plan artifacts in artifact ask flow
- support lesson-plan artifacts in artifact edit flow
- support structure-aware targeting for both `lesson_plan` and `lesson_plan_outline`
- reuse the existing `ask / edit / unclear` routing model
- reuse the existing `exact / candidate / unclear` targeting model

Out of scope:

- free-form whole-document lesson-plan rewrite as the primary edit path
- model-only target guessing without structural anchors
- element-level rich editing UI
- multi-artifact chained editing

## Decision

Use the same high-level model as report artifact reference:

1. top-level routing
   - `ask`
   - `edit`
   - `unclear`

2. edit target confidence
   - `exact`
   - `candidate`
   - `unclear`

Behavior:

- `ask`
  - answer directly with lesson-plan artifact context
- `edit + exact`
  - edit the matched field or step only
- `edit + candidate`
  - return candidate targets and require confirmation
- `edit + unclear`
  - ask for a clearer target
- `unclear`
  - do not enter edit runtime; ask the user to specify what to modify

## Artifact Modeling

### `lesson_plan`

Treat a full lesson plan as a structured artifact with editable nodes.

Suggested node groups:

- top-level field nodes
  - `teaching_objectives`
  - `key_points`
  - `difficult_points`
  - `teaching_preparation`
  - `blackboard_design`
  - `homework`
  - `reflection_tips`
- process-step nodes
  - each item in `process`
- optional nested step-field nodes
  - `step`
  - `goal`
  - `teacher_activity`
  - `student_activity`
  - `duration`

Initial support should allow targeting either:

- a top-level field
- a whole process step
- a stable subfield inside one step when the user explicitly names it

### `lesson_plan_outline`

Treat a lesson-plan outline as a lighter structured artifact.

Suggested node groups:

- top-level outline fields
  - `topic`
  - `audience`
  - `duration`
  - `objective`
- flow-step nodes
  - each item in `lesson_flow`

Initial support should prioritize:

- editing one named step
- editing one numbered step
- editing one top-level outline field

## Ask Flow

When a lesson-plan artifact is referenced and the request is classified as `ask`, the system should inject artifact context into the normal chat path.

### `lesson_plan` ask context

Build a compact context block from:

- title
- main teaching fields
- step list with short summaries

Example supported asks:

- `"what are the core teaching objectives in this lesson plan"`
- `"what happens in step 2"`
- `"what homework does this lesson plan assign"`

### `lesson_plan_outline` ask context

Build a compact context block from:

- topic and basic info
- lesson flow step titles
- step summaries when available

Example supported asks:

- `"how many steps are in this lesson-plan outline"`
- `"what is covered in step 3"`

## Edit Flow

### Top-Level Intent Rules

Apply the same coarse artifact-intent classifier used for other artifacts, extended to recognize lesson-plan-specific anchors.

Classify as `ask` when:

- the user is clearly asking about content
- there is no explicit edit verb

Classify as `edit` when:

- there is an explicit edit verb
- there is a plausible lesson-plan target anchor

Classify as `unclear` when:

- the message sounds transformative
- but there is no safe target anchor

Examples:

- `"what are the teaching key points in this lesson plan"` -> `ask`
- `"what happens in step 2"` -> `ask`
- `"rewrite the teaching objectives"` -> `edit`
- `"shorten the introduction step to 5 minutes"` -> `edit`
- `"optimize this lesson plan"` -> `unclear`

### Target Anchors

Support these locator styles for both lesson-plan artifact types where applicable:

- exact field-name match
  - `"teaching objectives"`
  - `"teaching key points"`
  - `"blackboard design"`
- exact step-name match
  - `"introduction step"`
  - `"guided practice"`
- order match
  - `"the second teaching step"`
  - `"step 3"`
- quoted snippet match
  - quoted text from one field or one step
- stable alias match
  - `"objectives"` => `"teaching objectives"`
  - `"key points"` => `"teaching key points"`

### Target Confidence

Return `exact` when one unique node is identified.

Return `candidate` when:

- the user intent is clearly edit
- but multiple nodes match the target phrase

Example:

- `"revise the activity section"`

If this could match multiple steps, the runtime should return candidates instead of editing.

Return `unclear` when:

- the user wants to edit
- but no safe structural anchor is found

Example:

- `"optimize this lesson plan"`

## Edit Execution

Once a lesson-plan target is identified:

- rewrite only the matched node
- preserve all untouched fields and steps
- rebuild the lesson-plan artifact in its original structured shape

### `lesson_plan`

Supported initial edit granularity:

- top-level field rewrite
- whole-step rewrite
- explicit subfield rewrite inside one matched step

Examples:

- `"rewrite the teaching objectives"`
- `"make the teacher activity in the introduction step more specific"`
- `"shorten the practice step to 8 minutes"`

### `lesson_plan_outline`

Supported initial edit granularity:

- top-level outline field rewrite
- whole-step rewrite
- step reordering when explicitly requested

Examples:

- `"revise the second teaching step"`
- `"move the practice step to the end"`

## Runtime UX

### Exact Match

If `edit + exact`:

- perform the edit
- return the revised lesson-plan artifact

### Candidate Match

If `edit + candidate`:

- do not edit yet
- return `awaiting_input`
- show candidate labels for confirmation

Example:

`I have not started editing yet. Do you want to change: introduction step / group activity / guided practice? Confirm one and I will edit it.`

### Unclear Target

If `edit + unclear`:

- do not edit yet
- ask the user to specify the field name, step name, quoted text, or numbered step

Example:

`Tell me which part you want to change. You can name the field, the step, quote one sentence, or say which numbered step to edit.`

## Architecture Changes

### 1. Artifact Context Loader

Extend `artifact_context_loader.py` to load and summarize:

- `lesson_plan`
- `lesson_plan_outline`

The loader should normalize lesson-plan storage payloads into a compact text context suitable for ask flow.

### 2. Artifact Intent Classifier

Extend `artifact_reference_intent.py` so lesson-plan artifacts can use:

- lesson-plan field anchors
- lesson-plan step anchors

This keeps top-level routing conservative and aligned with the current artifact model.

### 3. Lesson Plan Structure Parser

Add a dedicated structure parser for lesson-plan artifacts.

The parser should normalize either artifact type into node records with:

- node id
- node label
- node type
- optional parent id
- order index
- content or field value

This becomes the lesson-plan equivalent of the report structure parser.

### 4. Lesson Plan Edit Intent Parser

Add a parser dedicated to lesson-plan edit intent.

Suggested output:

```python
{
    "intent_type": "edit_artifact" | "ask_about_artifact",
    "target_type": "lesson_plan" | "lesson_plan_outline",
    "target_confidence": "exact" | "candidate" | "unclear",
    "target_locator_type": str | None,
    "target_node_id": str | None,
    "target_node_label": str | None,
    "candidate_nodes": [{"node_id": str, "label": str}],
    "matched_snippet": str | None,
    "action_type": str,
    "instruction": str,
}
```

### 5. Lesson Plan Edit Runtime

Add a dedicated lesson-plan edit runtime rather than forcing lesson-plan edits through the report edit runtime.

It should:

- load the referenced lesson-plan artifact
- parse structure nodes
- parse edit intent
- branch on `exact / candidate / unclear`
- rewrite only the matched node
- persist a revised lesson-plan artifact

### 6. Reply Service Routing

Update `reply_service_v2.py` so referenced lesson-plan artifacts:

- load ask context in sync and stream paths
- route explicit edits into the new lesson-plan edit runtime
- never route `unclear` directly into edit

## Testing Strategy

Add tests for:

### Artifact Intent

- lesson-plan question with field mention -> `ask`
- lesson-plan question with step number -> `ask`
- explicit lesson-plan edit with field anchor -> `edit`
- vague lesson-plan edit -> `unclear`

### Artifact Context Loader

- `lesson_plan` ask path injects a readable context block
- `lesson_plan_outline` ask path injects a readable context block

### Lesson Plan Edit Intent Parser

- exact field match
- exact step-name match
- exact numbered-step match
- quoted snippet exact match
- candidate match with multiple steps
- unclear target with no anchor

### Lesson Plan Edit Runtime

- exact field edit rewrites only one field
- exact step edit rewrites only one step
- candidate edit returns `awaiting_input`
- unclear edit returns clarification prompt
- ask-like message returns edit fallback guidance

### Reply Service

- sync ask path for lesson-plan artifact
- stream ask path for lesson-plan artifact
- sync edit path for lesson-plan artifact
- stream edit path for lesson-plan artifact
- unclear request never enters lesson-plan edit runtime

## Rollout Notes

This is a behavior-expansion for artifact references, but it should preserve the same safety posture as report editing:

- direct answers for clear questions
- precise edits for clear targets
- more clarification turns instead of unsafe rewrites

## Risks

### Risk 1: Lesson Plan Shapes Are Less Uniform

Generated lesson plans may vary in field names or nesting.

Mitigation:

- normalize known shapes before parsing
- keep alias mapping explicit
- limit initial supported editable fields to stable keys

### Risk 2: Step Names May Repeat

Multiple lesson steps may contain similar labels such as `"activity"`.

Mitigation:

- prefer numbered-step and exact-title matching
- use candidate confirmation when labels are not unique

### Risk 3: Editing Nested Step Fields Can Get Too Broad

Subfield editing may introduce complexity if the runtime tries to rewrite too much surrounding content.

Mitigation:

- support only explicit subfield requests in phase one
- otherwise rewrite the whole matched step, not arbitrary nested fragments

## Implementation Notes

Recommended order:

1. add lesson-plan artifact context loading
2. add top-level lesson-plan artifact intent tests
3. add lesson-plan structure parser
4. add lesson-plan edit intent parser
5. add lesson-plan edit runtime
6. wire reply service sync and stream paths
7. run focused artifact-reference regression suite
