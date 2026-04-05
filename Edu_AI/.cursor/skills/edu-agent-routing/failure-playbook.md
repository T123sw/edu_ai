# Failure Playbook - edu-agent-routing

## F1: Awaiting state ignored

Symptom:
- user only says `可以`
- route goes to `chat`

Fix:
1. Check `conv_state.awaiting_clarification` and report awaiting flags first.
2. Force `intent_category=generate_content` before classifier.
3. Mark `awaiting_override_applied=true`.

## F2: Report request misrouted to chat

Symptom:
- `帮我写报告` routed to `chat`

Fix:
1. Ensure report intent detector runs after intent classification.
2. Add report-specific trigger terms.
3. Validate `is_report=true` when trigger hit.

## F3: Excessive fallback routing

Symptom:
- `router_reason` mostly fallback

Fix:
1. Inspect JSON parse robustness.
2. Add markdown fence stripping before parse.
3. Cap fallback rate and alert when threshold exceeded.

## F4: response_type inconsistent with intent

Symptom:
- `intent_category=generate_content` but `response_type=chat`

Fix:
1. Add consistency rule in final routing stage.
2. For report-mode states, force `ask|outline|generate` only.

## F5: Determinism drift across same input/state

Symptom:
- same input produces different routes repeatedly

Fix:
1. Keep temperature low for classifier.
2. Make precedence order explicit and deterministic.
3. Persist decision context fields for replay debugging.
