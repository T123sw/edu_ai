# Teacher Agent Eval — teacher-agent-intelligence-baseline

- Schema: `2026-08-09.v2`
- Generated: `2026-08-09T10:50:54.972521+00:00`
- Repeats: 1
- Pass rate: 98.75%
- Mean structural score: 99.58%
- P50/P95: 0.12 / 0.21 ms

## Failure clusters

| Code | Count |
|---|---:|
| `intent_mismatch` | 1 |
| `missing_required_tool` | 1 |
| `plan_actions_mismatch` | 1 |

## Failed runs

| Case | Run | Score | Failures |
|---|---:|---:|---|
| `qa-none-02` | 1 | 66.67% | intent_mismatch, plan_actions_mismatch, missing_required_tool |
