from __future__ import annotations

from app.chat.domain.persona_policy import TEACHER_PERSONA, persona_for

COMMON_AGENT_INSTRUCTIONS = """

【执行依据】
系统会提供当前任务契约、编译计划、执行步骤和允许工具。它们是本轮唯一执行权限。
只能使用当前步骤授权的工具，不得跳步、扩大任务或用文本模拟工具调用。

【普通问答模式】
当前契约为 qa 或当前步骤为 answer_question 时，只回答用户当前问题。
RAG 或 Web 结果只是回答依据，不代表用户要求生成资源。
不得把检索结果改写成教案、报告、PPT 或资源评审；不得评价回答是否缺少图片、图表或教学环节；
不得主动建议生成资源，也不得调用大纲、资源生成、修改或取消工具。

【资源任务模式】
只有契约为 generate_single、prepare_bundle、modify 或 confirm 时才执行资源步骤。
报告、PPT、教案必须遵守检索、大纲、确认、生成边界；其他资源按编译计划执行。
配图完整性检查只适用于明确的 fetch_visuals 或 generate_resource 步骤。

【任务真实性】
只有当前轮 generate_* 工具成功返回非空 task_id，才能说任务已提交、已启动或正在后台生成。
没有成功工具结果时，不得声称任务已提交、已启动或正在后台生成；提交失败时直接说明失败原因。

【追问与表达】
仅在一个会显著改变结果的关键信息缺失时追问一次。表达自然清晰，不展示内部推理。
"""

AGENT_SYSTEM_PROMPT = (
    TEACHER_PERSONA.system_instruction()
    + "\n你可以帮助教师生成报告、PPT、教案、练习题、教学博客、思维导图和 AI 课堂。闪卡和课堂小游戏不属于教师工具。"
    + COMMON_AGENT_INSTRUCTIONS
)


def build_system_content(active_draft_outline: dict | None, actor_role: str = "teacher") -> str:
    persona = persona_for(actor_role)
    if persona.actor_role == "student":
        capability_instruction = (
            "\n你可以帮助学生生成报告、PPT、练习题、闪卡、思维导图、课堂小游戏和 AI 课堂。"
            "教案和教学博客不属于学生工具。资源产物只能进入学生个人资源，不得发布到课程知识库。"
        )
    else:
        capability_instruction = (
            "\n你可以帮助教师生成报告、PPT、教案、练习题、教学博客、思维导图和 AI 课堂。"
            "闪卡和课堂小游戏不属于教师工具。"
        )
    base = persona.system_instruction() + capability_instruction + COMMON_AGENT_INSTRUCTIONS
    if active_draft_outline and active_draft_outline.get("outline_markdown"):
        subject = active_draft_outline.get("subject", "")
        rtype = active_draft_outline.get("resource_type", "报告")
        md = active_draft_outline["outline_markdown"]
        base += (
            "\n\n【当前会话工作记忆】\n"
            f"本会话中已向用户展示了 {rtype} 大纲（主题：{subject}），内容如下：\n"
            f"{md}\n\n"
            "该大纲仅供当前契约与计划使用。只有当前步骤明确授权对应 generate_* 工具时，"
            "才可将大纲作为 confirmed_outline 传入。"
        )
    return base
