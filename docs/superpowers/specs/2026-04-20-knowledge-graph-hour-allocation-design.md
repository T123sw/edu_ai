# Knowledge Graph Hour Allocation Design

## Goal

Add a teacher-facing feature that allocates a course's total teaching hours across the leaf nodes of its knowledge graph, then rolls those hours up to every parent node.

After this change:
- teachers enter the course total hours from the knowledge graph page
- the backend asks the LLM to allocate hours only to leaf nodes
- the backend validates and normalizes the allocation to one decimal place
- every parent node receives the sum of its children
- the updated graph is saved and returned to the frontend

## Scope

This change is limited to course knowledge graph hour allocation.

In scope:
- add a backend allocation API for existing course knowledge graphs
- extract leaf nodes from the stored graph
- call the configured LLM with a constrained JSON allocation prompt
- normalize model output to non-negative one-decimal-hour values
- guarantee the sum of all leaf hours equals the requested total hours
- roll leaf hours up to all ancestor nodes
- persist `data.hours` on every graph node
- update the knowledge graph page button to call the backend API
- show generated hours from `data.hours`
- add backend tests for extraction, normalization, rollup, and API behavior
- add focused frontend tests or helper tests for API wiring and graph hour display if the frontend structure supports it

Out of scope:
- editing the knowledge graph structure itself
- merging leaf nodes when the graph is too detailed
- allocating by minutes or lesson periods
- asynchronous job tracking for long-running allocation
- generating detailed teaching plans from the allocated hours
- backfilling hours for every existing course automatically

## Current Problem

The current knowledge graph page has a local `generateHours` helper. It distributes hours in the browser across the flattened node list, so it does not reflect the intended teaching rule:

- only leaf nodes should receive direct model allocation
- parent nodes should be calculated from children
- allocation should consider the knowledge graph semantics, not just node count
- the saved graph should contain hours for every node
- backend consumers should be able to reuse the same allocation behavior

The `KnowledgeGraphNode` type also does not currently expose `data.hours`, even though the backend stores graph nodes as open dictionaries.

## Recommended Approach

Use a backend-owned allocation workflow and keep the frontend as a trigger and renderer.

Add:

`POST /api/courses/{course_id}/knowledge-graph/allocate-hours`

Request:

```json
{
  "total_hours": 32.5
}
```

Response:

```json
{
  "root": {
    "id": "root",
    "label": "Course graph",
    "data": {
      "hours": 32.5
    },
    "children": []
  },
  "allocation": {
    "total_hours": 32.5,
    "leaf_count": 18,
    "source": "llm",
    "normalized": true
  }
}
```

The route reads the current stored knowledge graph, runs allocation, saves the updated graph through `CourseStorageManager.save_knowledge_graph`, and returns the updated graph.

## Data Model

Store hours on each node under:

```json
{
  "data": {
    "hours": 1.5
  }
}
```

Rules:
- `hours` is a number, not a string
- values are non-negative
- values are rounded to one decimal place
- leaves may have `0` hours
- parent `hours` values are derived only from child sums
- existing `data` fields such as `level`, `summary`, `hasChildren`, and `type` are preserved

Use integer tenths internally:
- `32.5` hours becomes `325` tenths
- model values are converted into tenths
- normalization works on tenths
- final node values are converted back to one decimal place

This avoids floating point drift and makes totals exact.

## Allocation Flow

1. Load the course and current `knowledge_graph.json`.
2. Validate that `total_hours >= 0` and has at most one decimal place.
3. Traverse the graph and collect leaf nodes. A leaf is a node with no non-empty `children` list.
4. Build a compact LLM prompt containing each leaf's `id`, `label`, summary, type, depth, and ancestor path.
5. Ask the model to return strict JSON with leaf allocations only.
6. Parse the model output.
7. Normalize the leaf allocation:
   - unknown node IDs are ignored
   - missing leaf node IDs receive `0`
   - negative values become `0`
   - values are rounded to one decimal place
   - if the total is too high or too low, adjust leaf tenths until the total equals `total_hours`
8. Write normalized leaf hours to each leaf's `data.hours`.
9. Recursively roll child sums up to every parent.
10. Save the updated graph and return it to the frontend.

## LLM Prompt Contract

The model receives only leaf candidates and context needed for judgment.

Prompt requirements:
- explain that the total must be allocated across leaf nodes only
- allow `0` hours for minor, optional, or reference-only leaves
- prefer more hours for prerequisite, central, difficult, or practice-heavy concepts
- require one decimal place at most
- require strict JSON only

Expected model output:

```json
{
  "allocations": [
    {
      "node_id": "C1_1_1",
      "hours": 1.5,
      "reason": "Core prerequisite concept"
    }
  ]
}
```

The backend treats `reason` as trace information only. It does not persist reasons in the graph in the first version.

## Normalization Rules

Normalization must be deterministic so tests do not depend on model behavior.

Initial conversion:
- clamp invalid or missing values to `0`
- convert each valid hour value to integer tenths
- include every known leaf exactly once

If the sum is lower than the target:
- distribute the missing tenths one by one to leaves in priority order
- priority order prefers leaves with larger original model allocation, then shallower path, then stable node order

If the sum is higher than the target:
- subtract extra tenths one by one from leaves in priority order
- priority order prefers leaves with larger normalized allocation first, then stable node order
- never subtract below `0`

If the target is `0`, every leaf and parent receives `0`.

## Error Handling

Return `404` when the course does not exist.

Return `404` when the course has no stored knowledge graph.

Return `400` when:
- `total_hours` is negative
- `total_hours` has more than one decimal place
- the graph root is invalid
- no leaf nodes can be found

Return `502` or `500` when the LLM call fails completely or returns no parseable allocation. In that case, do not save a partial graph.

If the LLM returns imperfect but parseable data, normalize it and save the corrected graph.

## Frontend Behavior

Update the knowledge graph page so the "generate node hours" action calls the backend allocation API.

Frontend behavior:
- parse the total-hours input as a one-decimal number
- show a loading state while allocation is running
- replace the local graph state with the returned root
- display `data.hours` for nodes when present
- keep the existing save action for manual graph edits
- show backend errors without changing the current graph state

The existing local browser-only `generateHours` behavior should be removed or kept only as a non-persisting fallback if implementation discovers that backend access is unavailable in a specific local demo context. The production path is backend-owned.

## Architecture

### Backend

Recommended new service module:

`backend/src/app/knowledge_graph_hours.py`

Responsibilities:
- graph traversal
- leaf extraction
- LLM prompt construction
- LLM JSON parsing
- allocation normalization
- parent rollup

Recommended route change:

`backend/src/app/courses.py`

Responsibilities:
- request/response models
- course existence checks
- storage loading and saving
- dependency wiring to the configured LLM/RAG system
- HTTP error mapping

### Frontend

Update:

`frontend/src/stitch/api/types.ts`

Add `hours?: number` under `KnowledgeGraphNode.data`.

Update:

`frontend/src/stitch/api/courses.ts`

Add an `allocateKnowledgeGraphHours(courseId, payload)` API helper.

Update:

`frontend/src/stitch/pages/KnowledgeGraph.tsx`

Use returned `data.hours` when flattening nodes and call the new API from the total-hours button.

## Testing

Backend tests should cover:
- leaf extraction for nested graphs
- preserving existing node metadata while adding `data.hours`
- one-decimal normalization using integer tenths
- allowing leaf nodes to receive `0`
- correcting model totals that are lower than the requested total
- correcting model totals that are higher than the requested total
- rolling child sums up to every parent
- rejecting invalid total hours
- route saves the updated graph only after successful allocation
- route does not save when the LLM call completely fails

Frontend tests should cover, where practical:
- API helper sends `POST /api/courses/{course_id}/knowledge-graph/allocate-hours`
- `KnowledgeGraphNode.data.hours` is flattened into page state
- allocation button replaces graph state with returned data
- allocation errors leave current graph state unchanged

## Open Decisions

No open product decisions remain for the first version.

Confirmed constraints:
- the feature uses a backend API plus a frontend button
- the backend automatically validates and corrects model output
- hours support one decimal place
- leaves may receive `0` hours
- parent hours are always derived from children
- fully failed model calls do not save partial results

