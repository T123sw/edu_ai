# Artifact Reference Intent Precision Design

## Goal

Improve artifact-reference intent detection so the system prefers asking for clarification over making unsafe edits.

This iteration optimizes for:

- minimizing false-positive edits
- requiring confirmation when the edit target is not uniquely identified
- improving `report` / `report_outline` precision first
- keeping `ppt_deck` editing conservative and page-based

## Current State

The artifact-reference flow already supports:

- treating a referenced artifact as chat context by default
- routing explicit edits to `report_edit_runtime` or `ppt_edit_runtime`
- injecting report and PPT summary context into ask paths
- precise report target matching by title, node aliases, order, and quoted snippets

The remaining weakness is intent precision at the routing boundary:

- some vague edit-like phrasing is still classified too eagerly
- the current top-level classifier is mostly keyword-driven
- state persistence now distinguishes `artifact_reference` vs `artifact_edit`, but routing still needs stronger confidence gates
- PPT remains intentionally conservative, but the rules should make that explicit and testable

## Product Principles

### Principle 1: Never Edit on Weak Intent

If the system is not confident that the user wants to edit, it must not edit.

Preferred fallback:

- answer the question if it is clearly an ask
- ask a clarification question if it is ambiguous

### Principle 2: Never Edit on Weak Targeting

Even when the system is confident that the user wants to edit, it must not edit unless the target is safely identified.

Preferred fallback:

- return candidate targets
- require confirmation before editing

### Principle 3: PPT Is More Conservative Than Report

For this phase:

- `report` / `report_outline` may use structure-aware matching
- `ppt_deck` only supports explicit page-based editing
- semantic slide guessing is out of scope

## Scope

In scope:

- strengthen artifact intent classification from a binary `ask_about_artifact` / `edit_artifact` heuristic to a two-stage confidence model
- add candidate-confirmation behavior for report edits
- add stricter top-level guards for PPT edits
- expand tests for ambiguous and low-confidence cases

Out of scope:

- model-based intent classification
- semantic PPT slide guessing without page numbers
- element-level PPT editing
- generic natural-language disambiguation UIs beyond text confirmation

## Decision

Replace the effective routing behavior with a two-stage decision model:

1. `intent_class`
   - `ask`
   - `edit`
   - `unclear`

2. `target_confidence` for edit requests
   - `exact`
   - `candidate`
   - `unclear`

Route behavior:

- `ask`
  - run normal chat answer path with artifact context
- `edit + exact`
  - run edit runtime immediately
- `edit + candidate`
  - return candidates and require confirmation
- `edit + unclear`
  - ask the user to specify the exact target
- `unclear`
  - do not edit; ask a clarifying question

## Architecture Changes

### 1. Top-Level Artifact Intent Classifier

Evolve `artifact_reference_intent.py` from a flat keyword check into a small rule engine that returns richer intent metadata.

Suggested output:

```python
{
    "intent_class": "ask" | "edit" | "unclear",
    "reason": str,
    "requires_confirmation": bool,
}
```

Rules:

- classify as `ask` when the input is a normal question, even if it mentions a page or section, as long as there is no explicit edit verb
- classify as `edit` only when both are present:
  - an explicit edit verb
  - a plausible target anchor
- classify as `unclear` when the language sounds transformative but lacks a safe target

Examples:

- `这份报告的核心观点是什么？` -> `ask`
- `第三页主要讲了什么？` -> `ask`
- `重写结论` -> `edit`
- `把第 3 页改成流程图风格` -> `edit`
- `把这里改一下` -> `unclear`
- `帮我优化一下这个报告` -> `unclear`

### 2. Report Intent Parsing Becomes Confidence-Based

Extend `report_edit_intent_parser.py` so it no longer behaves like "best effort target and edit".

It should return:

```python
{
    "intent_type": "edit_artifact" | "ask_about_artifact",
    "action_type": str,
    "target_confidence": "exact" | "candidate" | "unclear",
    "target_locator_type": str | None,
    "target_node_id": str | None,
    "target_node_label": str | None,
    "candidate_nodes": [{"node_id": str, "label": str}],
    "matched_snippet": str | None,
    "instruction": str,
}
```

Resolution rules for `report`:

- `exact`
  - explicit title exact match
  - quoted snippet matching exactly one node
  - stable aliases like `摘要`, `结论`
  - explicit order references like `第 2 部分`
- `candidate`
  - phrase matches multiple nodes
  - user names a concept that maps to more than one structure node
- `unclear`
  - edit verbs exist but no safe node anchor can be found

Important behavioral change:

- do not fall back to the first node
- do not silently rewrite on weak matches

### 3. Report Edit Runtime Requires Confirmation for Candidates

`report/edit_runtime.py` should interpret parser output as follows:

- `ask_about_artifact`
  - tell the caller this belongs to ask flow or request removal of edit wording if needed
- `target_confidence == "exact"`
  - proceed with current node rewrite flow
- `target_confidence == "candidate"`
  - return `awaiting_input`
  - include candidate labels in a direct confirmation prompt
- `target_confidence == "unclear"`
  - return `awaiting_input`
  - ask for title, section name, or quoted text

Confirmation prompt style:

- concise
- explicit that no change has been made yet
- offer candidate targets as selectable text labels

Example:

`我理解你想修改报告，但还不能安全定位。你要改的是：摘要 / 问题定义 / 课堂观察 / 结论？确认后我再修改。`

### 4. PPT Routing Stays Strict

Top-level PPT editing should only happen when:

- an explicit edit verb exists
- an explicit page reference exists

Examples:

- `第三页讲了什么？` -> `ask`
- `把第三页改成流程图风格` -> `edit`
- `把讲三次握手那页改一下` -> `unclear`

For `ppt_deck`, `candidate` mode is allowed only if we later have a safe slide-label mapping. In this phase, unresolved PPT targets should fall back to `unclear`.

### 5. Reply Service Routing

`reply_service_v2.py` should use the richer intent result rather than a flat string classification.

Required behavior:

- top-level route decides whether to stay in ask flow or enter edit flow
- `unclear` should never route directly to an edit runtime
- stream and non-stream paths must share the same logic

## UX Behavior

### Ask

If the request is classified as `ask`:

- keep artifact reference active
- answer directly using artifact context
- do not mention edit mode

### Edit With Exact Target

If classified as `edit + exact`:

- perform the edit
- return the revised artifact as before

### Edit With Candidate Targets

If classified as `edit + candidate`:

- do not edit yet
- show candidate labels
- ask the user to confirm one target

### Unclear

If classified as `unclear`:

- do not edit
- ask the user to specify the section title, quoted sentence, or page number

## Testing Strategy

### Top-Level Intent Tests

Add tests for:

- report question with section mention but no edit verb -> `ask`
- PPT question with page mention but no edit verb -> `ask`
- vague edit verb with no target -> `unclear`
- explicit edit + explicit page -> `edit`

### Report Parser Tests

Add tests for:

- explicit title -> `exact`
- quoted snippet matching one node -> `exact`
- ambiguous concept mapping to multiple nodes -> `candidate`
- vague edit with no anchor -> `unclear`
- no first-node fallback

### Report Runtime Tests

Add tests for:

- candidate targets return `awaiting_input`
- unclear target returns clarification prompt
- exact target still rewrites only one node

### Reply Service Tests

Add tests for:

- stream and non-stream ask flow consistency
- stream and non-stream edit flow consistency
- `unclear` requests never enter edit runtime

## Rollout Notes

This is a behavior-tightening change, not a capability-expansion change.

Expected tradeoff:

- more clarification turns
- fewer accidental edits

That tradeoff is intentional and preferred for this feature.

## Risks

### Risk 1: Over-Defensive Routing

Too many requests may fall into `unclear`, increasing friction.

Mitigation:

- keep prompts short
- prefer `candidate` over generic `unclear` when viable
- add targeted tests from real examples

### Risk 2: Rule Drift Between Top-Level and Report Parser

The top-level classifier and report parser could disagree.

Mitigation:

- keep top-level logic coarse and conservative
- let report parser own fine-grained target confidence
- share normalized edit verb lists where practical

### Risk 3: PPT False Positives

PPT language often mentions page numbers in questions.

Mitigation:

- require both edit verb and page anchor for PPT edit routing

## Implementation Notes

Recommended execution order:

1. enrich top-level intent output
2. add report target confidence states
3. update report runtime confirmation behavior
4. tighten PPT top-level rules
5. align stream and non-stream tests
