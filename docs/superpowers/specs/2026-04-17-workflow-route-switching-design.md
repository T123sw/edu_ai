# Workflow Route Switching Design

## Goal

When a user is inside any workflow, explicit routing intent must win immediately. A report workflow should not trap later requests such as "回到普通对话" or "基于以上内容，生成PPT", even if the old workflow is unfinished or still stored as completed state.

## Scope

This change is limited to backend chat route selection.

In scope:
- route explicit chat-exit phrases to the fast chat path
- route explicit artifact generation phrases to their target workflow before resuming old workflow state
- keep existing follow-up behavior for ambiguous "继续" and "确认" replies
- cover report-to-chat and report-to-PPT transitions for both running and completed workflow states

Out of scope:
- frontend UI changes
- clearing persisted artifacts
- changing workflow runtime internals
- LLM-based intent classification

## Approach

Use deterministic route rules in `app/chat/orchestrator/route_rules.py`. The router will evaluate high-confidence switch commands before the existing `resume_workflow` branch.

Priority order:
1. active artifact rewrite commands
2. explicit workflow switch or chat-exit commands
3. existing interrupt handling
4. existing resume workflow behavior
5. existing context follow-up and default routing

Explicit switches include:
- chat exit: "回到普通对话", "普通对话", "退出工作流", "结束工作流", "先聊天"
- PPT: text containing `ppt` or "课件"
- report: text containing "报告"
- lesson plan: existing lesson-plan markers
- quiz: existing quiz markers

## Testing

Add route-rule tests that prove:
- report workflow running + "回到普通对话" routes to fast chat
- report workflow completed + "回到普通对话" routes to fast chat
- report workflow running + "基于以上内容，生成PPT" routes to PPT workflow
- report workflow completed + "基于以上内容，生成PPT" routes to PPT workflow
- ambiguous "继续" still resumes the old workflow

## Risks

The main risk is over-matching normal instructional text as a workflow switch. To limit that, only high-confidence generation keywords and explicit chat-exit phrases run before resume. Generic follow-up words stay with the old workflow.
