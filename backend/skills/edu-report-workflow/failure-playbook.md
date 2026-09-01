# Failure Playbook - edu-report-workflow

## F1: Overwriting prior slots unexpectedly

Symptom:
- user adds one field, previous fields disappear

Fix:
1. Apply delta-only merge.
2. Keep untouched slots as-is.

## F2: Endless questioning loop

Symptom:
- same missing field asked repeatedly

Fix:
1. Track per-slot ask count.
2. Cap at 2 and trigger auto-fill fallback.

## F3: Generates final report before outline confirmation

Symptom:
- jumps from slot-complete directly to long final output

Fix:
1. Enforce `outline` stage first.
2. Require `confirm_outline` intent to unlock `generate`.

## F4: User modifies outline but system ignores edits

Symptom:
- user asks edit, old outline returned unchanged

Fix:
1. Detect `modify` intent while outline pending.
2. Apply localized edits and preserve unchanged sections.

## F5: Force-generate triggered too aggressively

Symptom:
- initial `帮我写报告` treated as force_generate

Fix:
1. Reclassify startup requests to `provide`.
2. Reserve `force_generate` for explicit impatient commands.
