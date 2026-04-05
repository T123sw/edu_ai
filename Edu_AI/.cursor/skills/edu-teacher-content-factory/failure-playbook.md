# Failure Playbook - edu-teacher-content-factory

## F1: Generated JSON invalid

Symptom:
- parse error at first attempt

Fix:
1. Remove `<think>` blocks and code fences.
2. Extract largest JSON object/array.
3. Apply tolerant parse and field normalization.

## F2: Missing required lesson plan fields

Symptom:
- no `process` or `objectives`

Fix:
1. Run required-field validator.
2. Auto-fill minimal defaults and mark as recovered.

## F3: Quiz choice question has <4 options

Symptom:
- choice item only 2-3 options

Fix:
1. Enforce 4-option repair (A-D).
2. Keep answer key consistent with repaired options.

## F4: Empty artifact returned silently

Symptom:
- empty list/string but no error

Fix:
1. Add non-empty guard before return.
2. If empty, return explicit error and retry recommendation.

## F5: Storage write failed for course artifact

Symptom:
- generation succeeds but material not persisted

Fix:
1. Separate generation success from storage status.
2. Return artifact + explicit storage failure message.
3. Include retry-safe storage payload.
