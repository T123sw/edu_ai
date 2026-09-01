# Scoring Rubric

## 1) Per-Case Scoring

Each case total = 100 points.

- `expected` exact match: 50 points
- all `must_have` satisfied: 40 points
- no `forbidden` hit: 10 points

If any `forbidden` condition is hit, case score = 0 (hard fail).

## 2) Per-Skill Score

`skill_score = average(case_scores)`

Suggested release gate:
- routing >= 90
- rag_multimodal >= 88
- report_workflow >= 90
- teacher_factory >= 92
- orchestrator >= 90

## 3) Overall Score

Weighted average:
- routing: 20%
- rag_multimodal: 25%
- report_workflow: 25%
- teacher_factory: 20%
- orchestrator: 10%

`overall_score = Σ(skill_score * weight)`

Recommended thresholds:
- >= 92: excellent
- 88-91.99: acceptable
- 80-87.99: needs improvement
- < 80: blocked

## 4) Regression Policy

A run is regression-failed if any condition is true:
1. overall score drops by >= 3 points vs previous baseline
2. any skill score drops by >= 5 points
3. any new hard-fail case appears in critical paths (`R-003`, `M-004`, `W-003`, `T-004`, `O-001`)

## 5) Execution Template

Use this result table template:

```markdown
| Case ID | Pass/Fail | Score | Notes |
|--------|-----------|-------|-------|
| R-001  | Pass      | 100   |       |
```

Then summarize:
- per-skill pass rate
- per-skill score
- overall score
- newly failed cases
- top 3 fixes
