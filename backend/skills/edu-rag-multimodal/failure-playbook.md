# Failure Playbook - edu-rag-multimodal

## F1: RAG enabled but no tool call emitted

Symptom:
- rag enabled + selected docs present
- no tool call observed

Fix:
1. Apply forced `rag_search_tool` call fallback.
2. Verify tool binding order and message list.

## F2: sources contain images but injected=0

Symptom:
- `sources_images>0`, `injected=0`

Fix:
1. Validate `image_path` extraction from tool payload.
2. Check path normalization and existence.
3. Inspect read/encode errors in inject stats.

## F3: Wrong model switch to vision without images

Symptom:
- `injected=0`, `final_answer_role=vision`

Fix:
1. Enforce hard condition: switch only when `injected>0`.
2. Add assertion in selection logic.

## F4: Vision invoke fails and response crashes

Symptom:
- user sees 500/error when vision call fails

Fix:
1. Wrap vision invoke in try/except.
2. Fallback to text draft.
3. Emit `degraded=true` + error log.

## F5: Deepsearch loop without completion flag

Symptom:
- repeated deepsearch tool calls

Fix:
1. Set and check `deepsearch_done` state.
2. Stop forcing deepsearch when a tool result already exists.
