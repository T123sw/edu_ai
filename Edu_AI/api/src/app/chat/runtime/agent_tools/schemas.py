from __future__ import annotations


SCHEMA_RAG_SEARCH = {
    "type": "function",
    "function": {
        "name": "rag_search",
        "description": (
            "当用户明确提到'我的资料/知识库/上传的文件'，或问题需要基于用户私有内容回答时调用。"
            "通用知识、概念解释、一般问答不调用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索关键词"},
                "top_k": {"type": "integer", "description": "返回结果数", "default": 5},
            },
            "required": ["query"],
        },
    },
}

SCHEMA_WEB_SEARCH = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "当用户需要实时信息、最新动态、当前数据时调用（'今天/最新/当前'为典型信号）。"
            "历史概念、通用知识不调用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
            },
            "required": ["query"],
        },
    },
}

SCHEMA_DRAFT_OUTLINE = {
    "type": "function",
    "function": {
        "name": "draft_outline",
        "description": (
            "当你已收集到足够信息（主题明确），需要生成结构化大纲供用户确认时调用。"
            "调用后将返回的大纲展示给用户，询问是否需要调整。"
            "resource_type 填写 'report'/'ppt'/'lesson_plan'。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "resource_type": {
                    "type": "string",
                    "enum": ["report", "ppt", "lesson_plan"],
                    "description": "资源类型",
                },
                "subject": {"type": "string", "description": "主题/课题"},
                "focus": {"type": "string", "description": "重点方向（可选）", "default": ""},
                "constraints": {"type": "string", "description": "用户的补充约束，如'加一节量子纠错'", "default": ""},
                "slide_count": {"type": "integer", "description": "PPT 页数（resource_type=ppt 时有效）", "default": 10},
                "grade": {"type": "string", "description": "年级（resource_type=lesson_plan 时有效）", "default": ""},
                "duration_minutes": {"type": "integer", "description": "课时分钟数", "default": 45},
            },
            "required": ["resource_type", "subject"],
        },
    },
}

SCHEMA_GENERATE_REPORT = {
    "type": "function",
    "function": {
        "name": "generate_report",
        "description": (
            "仅在用户已确认大纲内容后调用（必须传入 confirmed_outline）。"
            "这会触发后台报告生成任务，不可中断，确认前不要调用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "报告主题"},
                "confirmed_outline": {"type": "string", "description": "用户已确认的大纲（Markdown 格式）"},
                "focus": {"type": "string", "description": "报告重点", "default": ""},
                "length_hint": {"type": "string", "description": "字数要求（如'5000字'）", "default": ""},
            },
            "required": ["subject", "confirmed_outline"],
        },
    },
}

SCHEMA_GENERATE_PPT = {
    "type": "function",
    "function": {
        "name": "generate_ppt",
        "description": (
            "仅在用户已确认PPT大纲后调用（必须传入 confirmed_outline）。"
            "会触发后台PPT生成任务，不可中断。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "PPT 主题"},
                "confirmed_outline": {"type": "string", "description": "用户已确认的PPT大纲（Markdown格式）"},
                "slide_count": {"type": "integer", "description": "幻灯片数量", "default": 10},
            },
            "required": ["topic", "confirmed_outline"],
        },
    },
}

SCHEMA_GENERATE_LESSON_PLAN = {
    "type": "function",
    "function": {
        "name": "generate_lesson_plan",
        "description": "仅在用户已确认教案大纲后调用（必须传入 confirmed_outline）。",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "课题名称"},
                "confirmed_outline": {"type": "string", "description": "用户已确认的教案大纲"},
                "grade": {"type": "string", "description": "年级", "default": ""},
                "duration_minutes": {"type": "integer", "description": "课时分钟数", "default": 45},
            },
            "required": ["subject", "confirmed_outline"],
        },
    },
}

SCHEMA_GENERATE_QUIZ = {
    "type": "function",
    "function": {
        "name": "generate_quiz",
        "description": (
            "当用户明确要求生成练习题/习题/测试题时直接调用（无需大纲步骤）。"
            "从对话中提取主题、题量、难度后调用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "题目主题"},
                "question_count": {"type": "integer", "description": "题目数量", "default": 10},
                "difficulty": {
                    "type": "string",
                    "enum": ["easy", "medium", "hard"],
                    "default": "medium",
                },
                "question_types": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["choice", "blank", "short", "judge"]},
                    "description": "题型列表，空列表表示混合",
                    "default": [],
                },
            },
            "required": ["subject"],
        },
    },
}


def build_tool_schemas(capability) -> list[dict]:
    schemas = []
    if getattr(capability, "allow_rag", False):
        schemas.append(SCHEMA_RAG_SEARCH)
    if getattr(capability, "allow_web", False):
        schemas.append(SCHEMA_WEB_SEARCH)
    schemas.extend(
        [
            SCHEMA_DRAFT_OUTLINE,
            SCHEMA_GENERATE_REPORT,
            SCHEMA_GENERATE_PPT,
            SCHEMA_GENERATE_LESSON_PLAN,
            SCHEMA_GENERATE_QUIZ,
        ]
    )
    return schemas
