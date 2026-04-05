from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict
from typing_extensions import Literal

from langchain_openai import ChatOpenAI

from .model_gateway import ChatModelGateway


class GraphState(TypedDict):
    # ─── 输入与会话上下文 ───
    question: str
    conversation_id: str
    model_id: Optional[str]
    gateway: ChatModelGateway
    model_cfg: Dict[str, Any]
    history: List[Dict[str, Any]]
    conv_state: Dict[str, Any]

    # ─── 通用槽位（Phase 1 重构） ───
    slots: Dict[str, Any]
    slot_meta: Dict[str, Any]
    missing_slots: List[str]
    slot_collection_phase: str
    expected_slot: Optional[str]
    slot_signal: Dict[str, Any]

    # ─── 路由与分类 ───
    intent_category: str
    resource_type: Optional[str]
    router_reason: str
    awaiting_override_applied: bool
    route_source: str
    response_type: Literal[
        "chat",
        "ask",
        "generate",
        "outline",
        "research",
        "text_generate",
        "multimodal_generate",
    ]

    # ─── 路由/规划解释字段 ───
    video_search_reason: str
    video_search_source: str
    video_override_applied: bool
    extractor_reason: str
    extractor_source: str
    extractor_override_applied: bool
    outline_reason: str
    outline_source: str
    outline_override_applied: bool
    generate_reason: str
    generate_source: str
    generate_override_applied: bool

    # ─── 澄清/规划 ───
    clarify_result: Dict[str, Any]
    plan: Dict[str, Any]
    answer_mode: str
    style_hint: str
    used_clarification: bool
    confidence: Dict[str, Any]
    followup_question: str
    anti_repeat_used: bool
    missing_slot: str
    known_info_prefix: str
    missing_info: List[str]
    ask_counts: Dict[str, int]

    # ─── 运行时消息与模型对象 ───
    messages: List[Any]
    render_messages: List[Dict[str, str]]
    messages_inited: bool
    llm: Optional[ChatOpenAI]
    llm_deep: Optional[ChatOpenAI]
    vlm: Optional[ChatOpenAI]

    # ─── 搜索/工具配置 ───
    rag_tool_enabled: bool
    deepsearch_tool_enabled: bool
    rag_top_k: int
    selected_doc_ids: List[str]
    deepsearch_done: bool
    course_id: Optional[str]
    search_context_hint: str

    # ─── 生成阶段统一字段（Phase 1 预留） ───
    outline: List[Dict[str, Any]]
    outline_confirmed: bool
    generated_content: str
    generation_checkpoint: Dict[str, Any]

    # ─── 现有 report 兼容字段（Phase 2 前保留） ───
    report_slots: Dict[str, str]
    report_missing: List[str]
    report_ask_counts: Dict[str, int]
    report_auto_fill: bool
    report_ready: bool
    report_content: str
    report_meta: Dict[str, Any]
    report_outline: List[Dict[str, Any]]
    report_outline_pending: bool
    report_reflection: Dict[str, Any]
    report_checkpoint: Dict[str, Any]
    soft_params_confirmed: bool

    # ─── 结果输出 ───
    final_answer: str
    final_answer_source: Optional[str]
    final_answer_model: str
    final_answer_role: str

    # ─── 技能/画像/检索中间态 ───
    agent_monologue: str
    user_profile: Dict[str, Any]
    memory_context: str
    video_hits: List[Dict[str, Any]]
    applied_skills: List[str]
    node_skill_map: Dict[str, List[str]]
    skill_used: str
    next_action: str
    needs_more_context: bool

    # ─── 工具授权 ───
    tool_auth_requested: bool
    tool_auth_granted: bool
    tool_auth_type: str
    tool_auth_reason: str
    tool_auth_source: str

    # ─── 需求清晰度与角色模式 ───
    requirement_clear: bool
    requirement_signal_count: int
    requirement_signals: List[str]
    need_type: str
    user_role_mode: str
    dialogue_skill: str
    need_route_reason: str
    degraded: bool
