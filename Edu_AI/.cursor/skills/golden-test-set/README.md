# Skill Golden Test Set

This benchmark validates the V2 skill system:
- `edu-agent-routing`
- `edu-rag-multimodal`
- `edu-report-workflow`
- `edu-teacher-content-factory`
- `edu-orchestrator`

## Goal

Provide stable regression checks so future prompt/skill/code changes can be evaluated against fixed expected behavior.

## Directory Layout

- `cases/routing.json`
- `cases/rag_multimodal.json`
- `cases/report_workflow.json`
- `cases/teacher_factory.json`
- `cases/orchestrator.json`
- `scoring.md`

## How To Use

1. Pick one case set (e.g. `routing.json`).
2. Run the corresponding skill workflow with each input.
3. Compare actual output to `expected` and `must_have` fields.
4. Score using `scoring.md`.

## Evaluation Rule

- A case passes only when all `must_have` checks pass.
- `nice_to_have` checks improve quality score but are not hard fail.
- Any `forbidden` pattern appearing counts as fail.

## Suggested Cadence

- Run full set before any major release.
- Run impacted subset before merging skill changes.
- Track trends for pass rate and per-skill score.
