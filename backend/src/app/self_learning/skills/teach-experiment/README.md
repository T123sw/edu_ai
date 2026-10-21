# 教学 Skill 预留位置

这里尚无 SKILL.md，也没有注册教学模型调用。实验设计 Skill 在 `app/practice/skills/design-experiment/`，两者独立。

教学 Agent 后续接入 `app/practice/experiment/teaching.py` 的只读证据协议，认证由 `api/practice.py` 保证。先冻结提问，读取设计、快照、分页事件、尝试或状态差异；输出必须绑定 context_id/revision/run_id/state_revision/attempt_id。生成页面和用户记录只作为数据，不作为系统指令。

短历史可直接装入模型上下文；长历史需显式选择范围并保留分页读取能力，不能宣称模型已看到未读取的全部操作。当前 API 保存完整原始事件和快照，不生成历史摘要。

迟到回答保留在原问题下。此轮只实现 `response_matches_context` 绑定检查，不实现回答生成、流式回复、自动干预、长期掌握判断或 rubric 评价提交。教学 Agent 不直接改实验状态，客观题判定也不等待模型。

详见 `docs/architecture/2026-10-15-experiment-agent-handoff-cn.md` 及同日实施计划。
