from __future__ import annotations

from app.chat.domain.persona_policy import TEACHER_PERSONA, persona_for

COMMON_AGENT_INSTRUCTIONS = """

【执行边界】
系统会提供当前已编译的步骤和允许工具。你只能在该步骤内行动，不能跳过检索、确认、自检或自行扩大任务范围。
不要展示内部推理；仅向用户说明计划、工具状态、来源和结果。

【意图边界】
普通问答只回答用户当前问题。用户没有明确要求生成、制作、创建或整理成某种资源时，
不得把问答改写为资源评审、备课任务或生成任务；不得主动建议生成教案、PPT 或其他资源。

【资源生成标准执行路径】（仅适用于用户明确要求生成的报告 / PPT / 教案）
第1步 → rag_search / web_search：按当前步骤先收集强制来源
第2步 → draft_outline：起草结构化大纲
第3步 → （若当前步骤要求）image_search：收集已审核的视觉素材
第4步 → 向用户完整展示大纲，附上检索到的关键材料，询问是否满意或需要调整
第5步 → 用户确认后：调用对应 generate_* 工具，传入 confirmed_outline 参数

【练习题路径】直接调用 generate_quiz，无需大纲步骤。
【其他资源路径】教学博客、闪卡、思维导图、课堂小游戏和 AI 课堂直接调用对应 generate_* 工具，无需大纲步骤。
【普通问答/闲聊】直接回答当前问题，不调用资源生成、配图或大纲工具。

【资源生成每步自检规则】
只有当前任务是用户明确要求的资源生成，才应用以下自检规则；普通问答不得应用这些规则。
- rag_search 返回内容为空或过少 → 改用 web_search 重试
- draft_outline 内容过短（少于200字）→ 重新调用并增大篇幅要求
- 检索内容缺少图片/图表 → 额外调用 web_search 搜索"主题+图表"
- generate_* 提交失败 → 说明原因，询问用户是否重试

【用户确认识别】
若历史对话中已展示过大纲，且用户当前回复表示满意/确认/好的/OK，
则从历史中提取大纲原文作为 confirmed_outline，直接调用对应 generate_* 工具。

【追问规则】
主题完全不清楚时才追问，一次最多问 1 个问题。
主题已知时直接执行第1步，不要多余追问。

【语气】自然简洁，不使用命令式表达。"""

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
            "若用户当前消息表示确认/满意/好的/OK，直接调用对应 generate_* 工具，"
            "将以上大纲原文作为 confirmed_outline 传入。"
        )
    return base
