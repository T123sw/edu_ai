_WORKFLOW_LABELS = {
    "report":      "报告",
    "ppt":         "PPT课件",
    "lesson_plan": "教案",
    "quiz":        "练习题",
}

_TOOL_NAMES_CN = {
    "rag_search":           "知识库检索",
    "web_search":           "联网搜索",
    "draft_outline":        "起草大纲",
    "generate_report":      "生成报告",
    "generate_ppt":         "生成PPT",
    "generate_lesson_plan": "生成教案",
    "generate_quiz":        "生成练习题",
}

_ARG_KEYS_CN = {
    "subject":           "主题",
    "topic":             "主题",
    "query":             "查询",
    "confirmed_outline": "大纲",
    "focus":             "侧重",
    "grade":             "年级",
    "difficulty":        "难度",
    "question_count":    "题数",
    "slide_count":       "页数",
    "duration_minutes":  "时长",
    "question_types":    "题型",
    "outline_type":      "类型",
}

_OBSERVE_HINTS = {
    "rag_search": (
        "\n\n【自检】请评估以上检索结果："
        "内容是否充分？是否有图片/图表？若不足，继续调用 web_search 补充。"
    ),
    "web_search": (
        "\n\n【自检】请评估以上联网结果是否满足需求。"
        "若已充分，进行下一步。"
    ),
    "draft_outline": "",
}
