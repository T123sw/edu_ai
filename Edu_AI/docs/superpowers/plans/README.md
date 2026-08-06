# Course-Centered Optimization Execution Roadmap

This directory contains the canonical implementation sequence for `../specs/2026-08-06-course-centered-teacher-experience-design.md`.

## Execution Order

| Order | Priority | Plan | Phase goal | Entry condition | Exit evidence |
|---:|---|---|---|---|---|
| 1 | P0 | [Course Membership, Permissions, and Routing](2026-08-06-course-membership-permissions-routing.md) | Make the course the shared data and authorization boundary; make URL course context authoritative | Current regression baseline recorded | Two teachers share course changes/resources; student writes return 403; anonymous access returns 401; stale writes return 409; copied URLs preserve the course |
| 2 | P0 | [Course Knowledge, Generation Sources, and Job Reliability](2026-08-06-course-knowledge-generation-reliability.md) | Unify public course-document identity and RAG sources; isolate durable generation jobs | Plan 1 completion gate passes | Nine resources pass all three source modes; selected documents provide real context; one blocked task does not block others; cancel/timeout converge |
| 3 | P0 baseline, then P1 | [Teacher Frontend Information Architecture, Generation UX, and Visual QA](2026-08-06-teacher-frontend-ia-generation-ux.md) | Rebuild the course shell, knowledge IA, nine-resource configuration/result UX, and visual quality gate | Plans 1–2 completion gates pass | Five viewports pass overflow/keyboard/visual checks; all nine visible configs map to stored command snapshots; duplicate routes and generation branches are retired |

## Release Gates

1. **P0 data boundary gate:** do not redesign pages against creator-isolated or route-ambiguous data.
2. **P0 knowledge/reliability gate:** do not expose the new generation factory until all source modes and job terminal states are stable.
3. **P1 teacher experience gate:** do not start the student UI or Agent memory work until teacher workflows and shared course facts are accepted.

## Deferred P2 Work

- Student minimum access: reuse course, knowledge, Q&A, and published-resource facts; add a read-focused interface and student-only learning tools.
- Agent performance and memory: establish latency/quality baselines, then optimize routing, concurrency, caching, and course-scoped visible/deletable memory.

These are deliberately separate plans because their architecture depends on the accepted P0/P1 data and interaction contracts.

## Execution Method

For each plan:

1. Use `superpowers:subagent-driven-development` for isolated task-by-task execution, or `superpowers:executing-plans` for inline execution.
2. Follow red-green-refactor and run the focused command after every implementation step.
3. Stop at the plan completion gate; attach test, screenshot, or manual-review evidence before checking Spec acceptance items.
4. Keep migrations dry-run capable and do not delete legacy data automatically.
5. Do not combine later-phase visual cleanup with an unverified P0 backend change in the same review unit.
