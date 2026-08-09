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

SCHEMA_IMAGE_SEARCH = {
    "type": "function",
    "function": {
        "name": "image_search",
        "description": (
            "为正在生成的报告/PPT/教案小节搜索配图。"
            "仅在确实需要视觉素材的章节调用（流程/结构/案例/人物/场景类），"
            "概念定义或纯文字章节不需要调用。"
            "使用英文检索词通常命中率更高；可通过 style 指定 diagram（示意图）、"
            "chart（数据图）、real（照片）或 any（不限）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "图片检索关键词，建议英文"},
                "count": {
                    "type": "integer",
                    "default": 6,
                    "description": "候选数量上限，1-12",
                },
                "style": {
                    "type": "string",
                    "enum": ["real", "diagram", "chart", "any"],
                    "default": "any",
                    "description": "real=照片 / diagram=示意图 / chart=数据图 / any=不限",
                },
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

SCHEMA_GENERATE_BLOG = {
    "type": "function",
    "function": {
        "name": "generate_blog",
        "description": "生成教学博客。只要求主题，其余配置可从对话推断或使用默认值。",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "博客主题"},
                "audience": {"type": "string", "default": "教师"},
                "tone": {
                    "type": "string",
                    "enum": ["academic", "popular", "narrative"],
                    "default": "popular",
                },
                "length": {
                    "type": "string",
                    "enum": ["short", "medium", "long"],
                    "default": "medium",
                },
                "special_requirements": {"type": "string", "default": ""},
                "include_visuals": {"type": "boolean", "default": False},
            },
            "required": ["topic"],
        },
    },
}

SCHEMA_GENERATE_FLASHCARD = {
    "type": "function",
    "function": {
        "name": "generate_flashcard",
        "description": "生成复习闪卡。只要求主题，卡片数量和难度可选。",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "闪卡主题"},
                "count": {"type": "integer", "default": 10},
                "difficulty": {
                    "type": "string",
                    "enum": ["easy", "medium", "hard"],
                    "default": "medium",
                },
                "category": {"type": "string", "default": ""},
                "show_sources": {"type": "boolean", "default": True},
            },
            "required": ["topic"],
        },
    },
}

SCHEMA_GENERATE_GRAPH = {
    "type": "function",
    "function": {
        "name": "generate_graph",
        "description": "生成教学思维导图。只要求主题，说明和层级可选。",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "导图主题"},
                "description": {"type": "string", "default": ""},
                "max_depth": {"type": "integer", "default": 3},
            },
            "required": ["topic"],
        },
    },
}

SCHEMA_GENERATE_GAME = {
    "type": "function",
    "function": {
        "name": "generate_game",
        "description": "生成课堂小游戏。只要求主题，未指定类型时默认拖拽匹配。",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "游戏主题"},
                "game_type": {
                    "type": "string",
                    "enum": ["category_sort", "drag_match", "memory_flip"],
                    "default": "drag_match",
                },
                "card_count": {"type": "integer", "default": 8},
                "difficulty": {
                    "type": "string",
                    "enum": ["easy", "medium", "hard"],
                    "default": "medium",
                },
                "duration_minutes": {"type": "integer", "default": 5},
            },
            "required": ["topic"],
        },
    },
}

SCHEMA_GENERATE_CLASSROOM = {
    "type": "function",
    "function": {
        "name": "generate_classroom",
        "description": "生成可交互的 AI 课堂。只要求主题，其余教学配置可选。",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "AI 课堂主题"},
                "requirement": {"type": "string", "default": ""},
                "audience": {"type": "string", "default": "学习者"},
                "scene_count": {"type": "integer", "default": 6},
                "duration_minutes": {"type": "integer", "default": 25},
                "teaching_style": {
                    "type": "string",
                    "enum": ["guided", "lecture", "inquiry"],
                    "default": "guided",
                },
                "objectives": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
                "include_visuals": {"type": "boolean", "default": True},
                "enable_tts": {"type": "boolean", "default": False},
            },
            "required": ["topic"],
        },
    },
}


def build_tool_schemas(capability) -> list[dict]:
    schemas = []
    if getattr(capability, "allow_rag", False):
        schemas.append(SCHEMA_RAG_SEARCH)
    if getattr(capability, "allow_web", False):
        schemas.append(SCHEMA_WEB_SEARCH)
    if getattr(capability, "allow_image_search", False):
        schemas.append(SCHEMA_IMAGE_SEARCH)
    schemas.extend(
        [
            SCHEMA_DRAFT_OUTLINE,
            SCHEMA_GENERATE_REPORT,
            SCHEMA_GENERATE_PPT,
            SCHEMA_GENERATE_LESSON_PLAN,
            SCHEMA_GENERATE_QUIZ,
            SCHEMA_GENERATE_BLOG,
            SCHEMA_GENERATE_FLASHCARD,
            SCHEMA_GENERATE_GRAPH,
            SCHEMA_GENERATE_GAME,
            SCHEMA_GENERATE_CLASSROOM,
        ]
    )
    return schemas


def filter_schemas_by_step(schemas: list[dict], expected_tools: list[str]) -> list[dict]:
    """Strict mode: keep only schemas whose function.name is in expected_tools."""
    if not expected_tools:
        return schemas
    allowed = set(expected_tools)
    return [s for s in schemas if s.get("function", {}).get("name") in allowed]
