from __future__ import annotations

from app.chat.runtime.agent_tools.result import error_result, ok_result

DRAFT_OUTLINE_PROMPTS = {
    "report": (
        "请为以下报告生成一份结构清晰的大纲（Markdown 格式，用 # 表示章节）。\n"
        "报告主题：{subject}\n重点方向：{focus}\n补充约束：{constraints}\n\n"
        "只输出大纲，不要其他说明。"
    ),
    "ppt": (
        "请为以下PPT生成幻灯片大纲（Markdown 格式，每页用 ## 标题，下方 - 列要点）。\n"
        "PPT主题：{subject}\n幻灯片数量：{slide_count}张\n补充约束：{constraints}\n\n"
        "只输出大纲，不要其他说明。"
    ),
    "lesson_plan": (
        "请为以下教案生成教学大纲（Markdown 格式）。\n"
        "课题：{subject}\n年级：{grade}\n课时：{duration_minutes}分钟\n补充约束：{constraints}\n\n"
        "只输出大纲，不要其他说明。"
    ),
}


def handle_draft_outline(name: str, args: dict, ctx) -> dict:
    if ctx.agent_gateway is None:
        return error_result("draft_outline", "agent_gateway_not_available", "Agent 模型网关未配置")
    resource_type = str(args.get("resource_type", "report"))
    subject = str(args.get("subject", ""))
    prompt_template = DRAFT_OUTLINE_PROMPTS.get(resource_type, DRAFT_OUTLINE_PROMPTS["report"])
    prompt = prompt_template.format(
        subject=subject,
        focus=str(args.get("focus", "")),
        constraints=str(args.get("constraints", "")),
        slide_count=int(args.get("slide_count", 10)),
        grade=str(args.get("grade", "")),
        duration_minutes=int(args.get("duration_minutes", 45)),
    )
    outline_text = ctx.agent_gateway.chat(
        [{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=800,
    )
    return ok_result(
        "draft_outline",
        f"已生成 {resource_type} 大纲（{len(outline_text)} 字符）",
        {"outline_markdown": outline_text, "resource_type": resource_type, "subject": subject},
    )
