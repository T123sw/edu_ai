# Teacher Agent Eval — teacher-agent-intelligence-baseline

- Schema: `2026-08-09.v2`
- Generated: `2026-08-09T10:51:07.123240+00:00`
- Repeats: 5
- Pass rate: 98.75%
- Mean structural score: 99.58%
- P50/P95: 0.11 / 0.14 ms

## Failure clusters

| Code | Count |
|---|---:|
| `intent_mismatch` | 5 |
| `missing_required_tool` | 5 |
| `plan_actions_mismatch` | 5 |

## Failed runs

| Case | Run | Score | Failures |
|---|---:|---:|---|
| `qa-none-02` | 1 | 66.67% | intent_mismatch, plan_actions_mismatch, missing_required_tool |
| `qa-none-02` | 2 | 66.67% | intent_mismatch, plan_actions_mismatch, missing_required_tool |
| `qa-none-02` | 3 | 66.67% | intent_mismatch, plan_actions_mismatch, missing_required_tool |
| `qa-none-02` | 4 | 66.67% | intent_mismatch, plan_actions_mismatch, missing_required_tool |
| `qa-none-02` | 5 | 66.67% | intent_mismatch, plan_actions_mismatch, missing_required_tool |
