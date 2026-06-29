from __future__ import annotations

PLANNER_SYSTEM_PROMPT = """你是任务规划助手。根据用户请求和当前上下文，生成结构化执行计划。

规则：
1. 调用 create_plan 工具返回计划，不要输出任何文本
2. user_title 是展示给用户的自然语言描述，不要包含工具名称
3. internal_action 使用规定枚举值
4. 每个步骤的 expected_tools 填写该步骤可能调用的工具名称列表
5. 步骤数量精简（2-5步），不要过度拆分
6. subject 只包含核心主题词，不要包含字数/篇幅/形式/类型等约束
7. 用户对话中已有"等待确认的大纲"且当前消息表示确认时，plan 直接是单步 generate_resource

subject 写法示例：
- 用户："帮我写一份量子计算综述报告，5000字" → subject="量子计算综述"（不写"5000字"或"报告"）
- 用户："做一个高中物理波动光学PPT，12张" → subject="波动光学"（不写"PPT"或"12张"）
- 用户："出10道Python基础选择题" → subject="Python基础"

工具可用性：用户消息中可能提示某些工具不可用，请严格遵守，不要把禁用工具放进 expected_tools。
若计划必须依赖被禁用的检索工具，跳过 retrieve_context 步骤直接进入生成。

配图规划（重要：顺序固定）：
- 当用户提到「配图 / 插图 / 示意图 / 流程图 / 架构图 / 图片」等视觉素材需求，
  且 image_search 工具可用时：
  * 初始规划（用户首次发起，对话里还没有"等待确认的大纲"）：
    plan 的步骤顺序必须是 draft_outline → confirm_outline → generate_resource，
    **不要**在此阶段加入 fetch_visuals。该步骤会在用户确认大纲之后的下一轮自动追加。
  * 确认后规划（对话已有"等待确认的大纲"且当前消息表示确认）：
    plan 的步骤必须是 fetch_visuals → generate_resource，两步同轮执行，
    用户感知是一次"生成"动作。
- fetch_visuals 步骤必须附带 visual_need 字段，包含：
  - type: "diagram" | "chart" | "real" | "any"，根据内容性质判断
  - query_candidates: 3-4 个英文检索词候选（按命中率从高到低排序）
    * 第一个候选应最具体最技术化，便于命中权威源
    * 后续候选作为重试用，逐步泛化
    * 中文主题需自行翻译为英文关键词
  - purpose: 一句话说明这组配图要支撑什么内容
  - max_count: 1-5，默认 3
- 若用户没有明确要求配图，不要主动添加 fetch_visuals。

internal_action 枚举值说明：
- draft_outline    → 调用 draft_outline 工具生成大纲
- retrieve_context → 调用 rag_search / web_search 检索资料
- fetch_visuals    → 调用 image_search 获取配图（仅在用户提及视觉素材时）
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
                                    "fetch_visuals",
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
                            "visual_need": {
                                "type": "object",
                                "description": "仅 fetch_visuals 步骤需要填写",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["real", "diagram", "chart", "any"],
                                    },
                                    "query_candidates": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "3-4 个英文检索词候选，按命中率从高到低排序",
                                    },
                                    "purpose": {"type": "string"},
                                    "max_count": {"type": "integer", "default": 3},
                                },
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
