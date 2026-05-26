from __future__ import annotations

PLANNER_SYSTEM_PROMPT = """你是任务规划助手。根据用户请求和当前上下文，生成结构化执行计划。

规则：
1. 调用 create_plan 工具返回计划，不要输出任何文本
2. user_title 是展示给用户的自然语言描述，不要包含工具名称
3. internal_action 使用规定枚举值
4. 每个步骤的 expected_tools 填写该步骤可能调用的工具名称列表
5. 步骤数量精简（2-5步），不要过度拆分

internal_action 枚举值说明：
- draft_outline    → 调用 draft_outline 工具生成大纲
- retrieve_context → 调用 rag_search / web_search 检索资料
- confirm_outline  → 向用户展示大纲并等待确认（不调用工具）
- generate_resource → 调用 generate_* 工具生成最终资源
- answer_question  → 直接回答问题，无工具调用
- other            → 其他操作

resource_type 枚举值：report | ppt | lesson_plan | quiz | unknown"""

# JSON schema for the create_plan tool
CREATE_PLAN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_plan",
        "description": "创建结构化任务执行计划",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "任务主题，例如：量子计算基础教学",
                },
                "resource_type": {
                    "type": "string",
                    "enum": ["report", "ppt", "lesson_plan", "quiz", "unknown"],
                    "description": "生成的资源类型",
                },
                "steps": {
                    "type": "array",
                    "description": "执行步骤列表（2-5步）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "user_title": {
                                "type": "string",
                                "description": "展示给用户的步骤描述，自然语言",
                            },
                            "internal_action": {
                                "type": "string",
                                "enum": [
                                    "draft_outline",
                                    "retrieve_context",
                                    "confirm_outline",
                                    "generate_resource",
                                    "answer_question",
                                    "other",
                                ],
                            },
                            "expected_tools": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "预期调用的工具名称列表",
                            },
                        },
                        "required": ["index", "user_title", "internal_action", "expected_tools"],
                    },
                },
            },
            "required": ["subject", "resource_type", "steps"],
        },
    },
}
