# Orchestrator Examples

## Example 1: Report request with missing slots

Input:
- user: `帮我写一份教学总结`

Flow:
1. `edu-agent-routing` -> `response_type=ask`
2. `edu-report-workflow` -> ask for `period`

## Example 2: KB question with selected docs

Input:
- user: `根据我上传的教材解释牛顿第二定律`

Flow:
1. `edu-agent-routing` -> `response_type=research`
2. `edu-rag-multimodal` -> rag tool -> deep/vision final

## Example 3: Teacher lesson plan generation

Input:
- endpoint context indicates `/teacher/lesson_plan`

Flow:
1. `edu-orchestrator` chooses `edu-teacher-content-factory`
2. enforce schema + persistence contract

## Example 4: Ambiguous request

Input:
- user: `帮我整理一下`

Flow:
1. route uncertain
2. ask one clarification: `你希望我整理成课堂教案、教学报告，还是知识点问答？`
