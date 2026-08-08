from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

from core import Config
from core.course_storage import storage_manager
from modules.rag_v2.api import get_rag_system

from .langgraph_workflow import run_blog_task_langgraph
from .storage import load_task_state, save_task_state


def _clean_llm_json(text: str) -> str:
    cleaned = str(text or "").strip()

    patterns = [
        r"<think>.*?</think>",
        r"<thinking>.*?</thinking>",
        r"<thought>.*?</thought>",
    ]
    for p in patterns:
        cleaned = re.sub(p, "", cleaned, flags=re.DOTALL | re.IGNORECASE)

    cleaned = cleaned.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.lstrip("`")
        if "\n" in cleaned:
            cleaned = cleaned.split("\n", 1)[1]
        if "```" in cleaned:
            cleaned = cleaned.rsplit("```", 1)[0]

    cleaned = cleaned.strip()

    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]

    return cleaned.strip()


def _dfs_collect_nodes(root: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def rec(node: Any):
        if not isinstance(node, dict):
            return
        out.append(node)
        children = node.get("children")
        if isinstance(children, list):
            for c in children:
                rec(c)

    rec(root)
    return out


def _match_knowledge_graph_subtrees(
    course_id: str, topic: str, top_n: int = 2
) -> Tuple[List[str], List[Dict[str, Any]]]:
    graph = storage_manager.get_knowledge_graph(course_id)
    if not isinstance(graph, dict):
        return [], []

    nodes = _dfs_collect_nodes(graph)

    topic_norm = topic.strip().lower()
    scored: List[Tuple[int, str, Dict[str, Any]]] = []

    for n in nodes:
        nid = str(n.get("id") or "")
        label = str(n.get("label") or "")
        label_norm = label.lower()
        if not nid or not label:
            continue

        score = 0
        if topic_norm and topic_norm in label_norm:
            score += 10

        for part in re.split(r"[\s\-_/，,。；;：:（）()]+", topic_norm):
            part = part.strip()
            if part and part in label_norm:
                score += 2

        if score > 0:
            scored.append((score, nid, n))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = scored[:top_n]

    return [p[1] for p in picked], [p[2] for p in picked]


def _generation_config_text(generation_config: Dict[str, Any] | None) -> str:
    config = dict(generation_config or {})
    effective = {
        key: config.get(key)
        for key in (
            "audience",
            "tone",
            "length",
            "structure",
            "special_requirements",
            "source_mode",
        )
        if config.get(key) not in (None, "")
    }
    source_context = str(config.get("source_context") or "").strip()
    parts = ["【写作配置】", json.dumps(effective, ensure_ascii=False)]
    if source_context:
        parts.extend(
            [
                "【已检索课程资料】",
                source_context,
                "必须以以上资料为事实依据，不得编造资料中不存在的课程事实。",
            ]
        )
    visual_plan = config.get("visual_plan")
    selected_visuals = (
        list(visual_plan.get("selected") or [])
        if isinstance(visual_plan, dict)
        else []
    )
    if selected_visuals:
        slots = [
            f"{{{{VISUAL:{str(item.get('slot_id') or '').strip()}}}}}"
            for item in selected_visuals
            if isinstance(item, dict) and str(item.get("slot_id") or "").strip()
        ]
        parts.extend(
            [
                "【已锁定配图】",
                json.dumps(selected_visuals, ensure_ascii=False),
                "请围绕图片组织相应段落，并只在合适位置原样输出以下图片槽位："
                + "、".join(slots),
                "不得创建其他图片槽位或图片 URL。",
            ]
        )
    return "\n".join(parts)


def _assemble_selected_visuals(
    markdown: str,
    generation_config: Dict[str, Any] | None,
) -> str:
    from app.services.visual_assets.models import SelectedVisual
    from app.services.visual_assets.pipeline import VisualAssetPipeline

    visual_plan = dict((generation_config or {}).get("visual_plan") or {})
    selected: list[SelectedVisual] = []
    for item in list(visual_plan.get("selected") or []):
        if not isinstance(item, dict):
            continue
        try:
            selected.append(
                SelectedVisual(
                    slot_id=str(item.get("slot_id") or ""),
                    local_url=str(item.get("local_url") or ""),
                    title=str(item.get("title") or ""),
                    caption=str(item.get("caption") or ""),
                    source_page=str(item.get("source_page") or ""),
                    source_type=str(item.get("source_type") or "web"),
                    score=float(item.get("score") or 0),
                )
            )
        except (TypeError, ValueError):
            continue
    return VisualAssetPipeline.assemble(markdown, selected)


def _planner_chapters_prompt(
    topic: str,
    course_id: str,
    kg_subtrees: List[Dict[str, Any]],
    generation_config: Dict[str, Any] | None = None,
) -> str:
    kg_text = json.dumps(kg_subtrees, ensure_ascii=False) if kg_subtrees else "[]"
    config_text = _generation_config_text(generation_config)

    return f"""
你是一名经验丰富的教学助教，需要为教师生成一篇教学博客的一级目录（章节）写作大纲。

【课程ID】
{course_id}

【博客主题】
{topic}

{config_text}

【课程知识图谱（与主题相关的子树，作为结构化约束）】
{kg_text}

【要求】
1. 大纲必须围绕上述知识图谱子树中的概念组织，避免引入明显无关内容。
2. 本阶段只输出一级目录：章节（大标题），暂不输出小标题。
3. 章节之间循序渐进，适合教学。
4. 必须输出合法 JSON，不能输出任何多余文字。

【输出JSON结构】
{{
  \"chapters\": [
    {{
      \"id\": \"sec-1\",
      \"title\": \"章节标题（大标题）\",
      \"estimated_word_count\": 1200
    }}
  ]
}}

现在请直接输出唯一一个 JSON 对象。
""".strip()


def _executor_prompt(
    topic: str,
    section_title: str,
    point: Dict[str, Any],
    prev_summary: str = "",
    generation_config: Dict[str, Any] | None = None,
) -> str:
    pt_title = str(point.get("title") or "")
    key_concepts = point.get("key_concepts")
    if not isinstance(key_concepts, list):
        key_concepts = []

    kc_text = "、".join([str(x) for x in key_concepts if str(x).strip()])
    wc = point.get("estimated_word_count")

    prev_text = f"\n\n【上一小节摘要】\n{prev_summary}\n" if prev_summary else ""
    config_text = _generation_config_text(generation_config)

    return f"""
你是一名专业的课程助教，请围绕给定主题与小标题要求，撰写教学博客的一个小节内容。

【博客主题】
{topic}

{config_text}

【所属章节（大标题）】
{section_title}

【本小节标题（小标题）】
{pt_title}

【本小节关键概念】
{kc_text if kc_text else "（无）"}

{prev_text}
【写作要求】
1. 输出为 Markdown（不要包含章节的 ## 标题，只输出该小节正文即可）。
2. 内容要讲清楚概念、给出直观解释与必要的例子；避免空泛。
3. 篇幅控制在约 {wc} 字左右（可上下浮动）。
4. 不要输出与本小节无关的其它小节内容。

现在开始输出本小节 Markdown 内容（不要输出任何解释）。
""".strip()


def _assemble_markdown(outline: List[Dict[str, Any]], drafts: Dict[str, str]) -> str:
    parts: List[str] = []
    for idx, sec in enumerate(outline, start=1):
        sid = str(sec.get("id") or f"sec-{idx}")
        title = str(sec.get("title") or "")
        body = drafts.get(sid) or ""
        if title:
            parts.append(f"## {title}\n\n{body}".strip())
        else:
            parts.append(body.strip())
    return "\n\n".join([p for p in parts if p])


def _normalize_outline(outline: Any) -> List[Dict[str, Any]]:
    if not isinstance(outline, list):
        return []

    def norm_points(points: Any, default_sec_id: str) -> List[Dict[str, Any]]:
        if not isinstance(points, list):
            return []
        out: List[Dict[str, Any]] = []
        for j, pt in enumerate(points, start=1):
            if not isinstance(pt, dict):
                continue
            pid = str(pt.get("id") or f"{default_sec_id}-pt-{j}")
            ptitle = str(pt.get("title") or "").strip()
            pkc = pt.get("key_concepts")
            if not isinstance(pkc, list):
                pkc = []
            try:
                pwc = int(pt.get("estimated_word_count") or 300)
            except Exception:
                pwc = 300
            out.append(
                {
                    "id": pid,
                    "title": ptitle,
                    "key_concepts": [str(x) for x in pkc if str(x).strip()],
                    "estimated_word_count": pwc,
                }
            )
        return out

    normalized: List[Dict[str, Any]] = []
    for i, sec in enumerate(outline, start=1):
        if not isinstance(sec, dict):
            continue
        sid = str(sec.get("id") or f"sec-{i}")
        title = str(sec.get("title") or "").strip()
        try:
            wc = int(sec.get("estimated_word_count") or 1200)
        except Exception:
            wc = 1200

        # 兼容旧结构：如果没有 children，则用 key_concepts 生成一个默认的小标题
        children = sec.get("children")
        points = norm_points(children, sid)
        if not points:
            key_concepts = sec.get("key_concepts")
            if not isinstance(key_concepts, list):
                key_concepts = []
            points = [
                {
                    "id": f"{sid}-pt-1",
                    "title": "知识点",
                    "key_concepts": [str(x) for x in key_concepts if str(x).strip()],
                    "estimated_word_count": max(200, int(wc / 3)) if wc else 300,
                }
            ]

        normalized.append(
            {
                "id": sid,
                "title": title,
                "estimated_word_count": wc,
                "children": points,
            }
        )

    return normalized


def run_blog_task(thread_id: str) -> None:
    """保留原函数签名，内部切换为 LangGraph 工作流执行。"""

    rag = get_rag_system()
    model_config = Config.get_llm_model(Config.DEFAULT_LLM_MODEL_ID)

    def planner_chapters_node(graph_state: Dict[str, Any]) -> Dict[str, Any]:
        """阶段A：仅生成一级目录（章节列表），不生成小标题。"""
        tid = str(graph_state.get("thread_id") or thread_id)
        st = load_task_state(tid)
        if st is None:
            return graph_state

        matched_ids, subtrees = _match_knowledge_graph_subtrees(st.course_id, st.topic, top_n=2)
        st.knowledge_graph_match = {"matched_node_ids": matched_ids}

        st.status = "planning"
        save_task_state(st)

        prompt = _planner_chapters_prompt(
            st.topic, st.course_id, subtrees, st.generation_config
        )

        last_exc: Exception | None = None
        data: Dict[str, Any] | None = None
        for _ in range(2):
            try:
                raw = rag._call_llm(prompt, llm_config=model_config)  # type: ignore[attr-defined]
                cleaned = _clean_llm_json(raw)
                data = json.loads(cleaned)
                break
            except Exception as e:
                last_exc = e
                data = None

        if data is None:
            st.status = "failed"
            st.error_message = f"章节大纲JSON解析失败: {last_exc}. 模型返回内容: {cleaned[:200]}"
            save_task_state(st)
            raise ValueError(st.error_message)

        chapters = data.get("chapters")
        if not isinstance(chapters, list) or not chapters:
            # 兼容：模型可能仍然输出 outline
            alt = data.get("outline")
            if isinstance(alt, list):
                chapters = alt
            else:
                chapters = []

        # chapters 为一级目录：仅保留 id/title/estimated_word_count
        normalized: List[Dict[str, Any]] = []
        for i, sec in enumerate(chapters, start=1):
            if not isinstance(sec, dict):
                continue
            sid = str(sec.get("id") or f"sec-{i}")
            title = str(sec.get("title") or "").strip()
            try:
                wc = int(sec.get("estimated_word_count") or 1200)
            except Exception:
                wc = 1200
            if not title:
                continue
            normalized.append({"id": sid, "title": title, "estimated_word_count": wc})

        if not normalized:
            st.status = "failed"
            # 补充可观测性：输出片段，便于定位模型返回结构问题
            try:
                sample = json.dumps(data, ensure_ascii=False)[:200]
            except Exception:
                sample = str(data)[:200]
            st.error_message = f"章节大纲解析失败：未得到有效章节. 模型返回内容: {sample}"
            save_task_state(st)
            raise ValueError(st.error_message)

        st.outline = normalized
        st.progress.total_sections = len(normalized)
        st.progress.current_section_idx = 0
        st.status = "waiting_for_chapter_review"
        save_task_state(st)

        graph_state["outline"] = st.outline
        graph_state["progress"] = {"current_section_idx": 0, "total_sections": len(st.outline)}
        graph_state["drafts"] = graph_state.get("drafts") or {}
        graph_state["status"] = st.status
        return graph_state

    def wait_for_chapter_review_node(graph_state: Dict[str, Any]) -> Dict[str, Any]:
        """阶段A等待：人工审查一级目录（章节）。"""
        tid = str(graph_state.get("thread_id") or thread_id)
        st = load_task_state(tid)
        if st is None:
            return graph_state

        if st.pending_chapters is not None and len(st.pending_chapters) > 0:
            # 使用教师修改后的章节
            normalized = []
            for i, sec in enumerate(st.pending_chapters, start=1):
                if not isinstance(sec, dict):
                    continue
                sid = str(sec.get("id") or f"sec-{i}")
                title = str(sec.get("title") or "").strip()
                try:
                    wc = int(sec.get("estimated_word_count") or 1200)
                except Exception:
                    wc = 1200
                if not title:
                    continue
                normalized.append({"id": sid, "title": title, "estimated_word_count": wc})

            if not normalized:
                st.status = "failed"
                st.error_message = "章节审查提交无效：未得到有效章节"
                st.pending_chapters = None
                save_task_state(st)
                raise ValueError(st.error_message)

            st.outline = normalized
            st.pending_chapters = None
            st.progress.total_sections = len(normalized)
            st.progress.current_section_idx = 0
            st.status = "planning_points"
            save_task_state(st)

            graph_state["outline"] = st.outline
            graph_state["progress"] = {"current_section_idx": 0, "total_sections": len(st.outline)}
            graph_state["status"] = st.status
        else:
            st.status = "waiting_for_chapter_review"
            save_task_state(st)
            graph_state["status"] = st.status

        return graph_state

    def planner_points_node(graph_state: Dict[str, Any]) -> Dict[str, Any]:
        """阶段B：基于章节列表，为每章生成小标题（知识点）children。"""
        tid = str(graph_state.get("thread_id") or thread_id)
        st = load_task_state(tid)
        if st is None:
            return graph_state

        st.status = "planning_points"
        save_task_state(st)

        outline = graph_state.get("outline") or st.outline or []
        if not isinstance(outline, list):
            outline = []

        # 逐章生成 children；这里复用 normalize 逻辑处理 children
        enriched: List[Dict[str, Any]] = []
        for i, sec in enumerate(outline, start=1):
            if not isinstance(sec, dict):
                continue
            sid = str(sec.get("id") or f"sec-{i}")
            title = str(sec.get("title") or "").strip()
            try:
                wc = int(sec.get("estimated_word_count") or 1200)
            except Exception:
                wc = 1200
            if not title:
                continue

            prompt = f"""
你是一名经验丰富的教学助教，需要基于给定的章节标题，为该章节生成二级目录（小标题/知识点）。

【博客主题】
{st.topic}

【章节标题（大标题）】
{title}

【要求】
1. 输出 3-6 个小标题，每个小标题给出 key_concepts。
2. 小标题要覆盖该章节的核心知识点，循序渐进。
3. 必须输出合法 JSON，不能输出任何多余文字。

【输出JSON结构】
{{
  \"children\": [
    {{
      \"id\": \"{sid}-pt-1\",
      \"title\": \"小标题（知识点）\",
      \"key_concepts\": [\"概念1\", \"概念2\"],
      \"estimated_word_count\": 300
    }}
  ]
}}

现在请直接输出唯一一个 JSON 对象。
""".strip()

            last_exc: Exception | None = None
            data: Dict[str, Any] | None = None
            for _ in range(2):
                try:
                    raw = rag._call_llm(prompt, llm_config=model_config)  # type: ignore[attr-defined]
                    cleaned = _clean_llm_json(raw)
                    data = json.loads(cleaned)
                    break
                except Exception as e:
                    last_exc = e
                    data = None

            if data is None:
                st.status = "failed"
                st.error_message = f"小标题解析失败: {sid}, error={last_exc}"
                save_task_state(st)
                raise ValueError(st.error_message)

            # 用现有 normalize 统一规范 children
            sec_full = {"id": sid, "title": title, "estimated_word_count": wc, "children": data.get("children")}
            sec_full_norm = _normalize_outline([sec_full])
            if not sec_full_norm:
                st.status = "failed"
                st.error_message = f"小标题解析失败：章节无有效 children: {sid}"
                save_task_state(st)
                raise ValueError(st.error_message)
            enriched.append(sec_full_norm[0])

        if not enriched:
            st.status = "failed"
            st.error_message = "小标题解析失败：未得到有效章节"
            save_task_state(st)
            raise ValueError(st.error_message)

        st.outline = enriched
        st.progress.total_sections = len(enriched)
        st.progress.current_section_idx = 0
        st.status = "waiting_for_outline_review"
        save_task_state(st)

        graph_state["outline"] = st.outline
        graph_state["progress"] = {"current_section_idx": 0, "total_sections": len(st.outline)}
        graph_state["status"] = st.status
        return graph_state

    def wait_for_outline_review_node(graph_state: Dict[str, Any]) -> Dict[str, Any]:
        """阶段B等待：人工审查二级目录（章节+小标题）。"""
        tid = str(graph_state.get("thread_id") or thread_id)
        st = load_task_state(tid)
        if st is None:
            return graph_state

        if st.pending_outline is not None and len(st.pending_outline) > 0:
            st.outline = _normalize_outline(st.pending_outline)
            st.progress.total_sections = len(st.outline)
            st.progress.current_section_idx = 0
            st.pending_outline = None
            st.status = "executing"
            save_task_state(st)

            graph_state["outline"] = st.outline
            graph_state["progress"] = {"current_section_idx": 0, "total_sections": len(st.outline)}
            graph_state["status"] = st.status
        else:
            st.status = "waiting_for_outline_review"
            save_task_state(st)
            graph_state["status"] = st.status

        return graph_state

    def executor_node(graph_state: Dict[str, Any]) -> Dict[str, Any]:
        tid = str(graph_state.get("thread_id") or thread_id)
        st = load_task_state(tid)
        if st is None:
            return graph_state

        matched_ids, subtrees = _match_knowledge_graph_subtrees(st.course_id, st.topic, top_n=2)
        st.knowledge_graph_match = {"matched_node_ids": matched_ids}

        st.status = "planning"
        save_task_state(st)

        prompt = _planner_chapters_prompt(
            st.topic, st.course_id, subtrees, st.generation_config
        )

        last_exc: Exception | None = None
        data: Dict[str, Any] | None = None
        for _ in range(2):
            try:
                raw = rag._call_llm(prompt, llm_config=model_config)  # type: ignore[attr-defined]
                cleaned = _clean_llm_json(raw)
                data = json.loads(cleaned)
                break
            except Exception as e:
                last_exc = e
                data = None

        if data is None:
            st.status = "failed"
            st.error_message = f"大纲解析失败: {last_exc}"
            save_task_state(st)
            raise ValueError(st.error_message)

        outline = _normalize_outline(data.get("outline"))
        if not outline:
            st.status = "failed"
            st.error_message = "大纲解析失败：未得到有效章节"
            save_task_state(st)
            raise ValueError(st.error_message)

        st.outline = outline
        st.progress.total_sections = len(outline)
        st.progress.current_section_idx = 0
        save_task_state(st)

        graph_state["outline"] = outline
        graph_state["progress"] = {"current_section_idx": 0, "total_sections": len(outline)}
        graph_state["drafts"] = graph_state.get("drafts") or {}
        graph_state["status"] = "planning"

        return graph_state

    # wait_for_review_node 已废弃：旧的一阶段 HITL 流程（waiting_for_review）已被两阶段流程替代

    def executor_node(graph_state: Dict[str, Any]) -> Dict[str, Any]:
        tid = str(graph_state.get("thread_id") or thread_id)
        st = load_task_state(tid)
        if st is None:
            return graph_state

        st.status = "executing"
        outline = graph_state.get("outline") or []
        progress = graph_state.get("progress") or {}
        idx = int(progress.get("current_section_idx", 0))

        if not isinstance(outline, list) or idx >= len(outline):
            return graph_state

        sec = outline[idx]
        sid = str(sec.get("id") or f"sec-{idx+1}")
        sec_title = str(sec.get("title") or "").strip()

        st.progress.total_sections = len(outline)
        st.progress.current_section_idx = idx
        save_task_state(st)

        drafts = graph_state.get("drafts") or {}
        if not isinstance(drafts, dict):
            drafts = {}

        prev_summary = str(graph_state.get("prev_summary") or "")

        # 三级结构：按小标题（知识点）逐段生成，然后拼接为章节内容
        children = sec.get("children")
        if not isinstance(children, list) or not children:
            children = [
                {
                    "id": f"{sid}-pt-1",
                    "title": "知识点",
                    "key_concepts": [],
                    "estimated_word_count": 300,
                }
            ]

        section_parts: List[str] = []
        for pt in children:
            if not isinstance(pt, dict):
                continue
            pt_title = str(pt.get("title") or "").strip() or "知识点"
            pt_prompt = _executor_prompt(
                st.topic,
                sec_title,
                pt,
                prev_summary=prev_summary,
                generation_config=st.generation_config,
            )

            pt_last_exc: Exception | None = None
            pt_text = ""
            for _ in range(2):
                try:
                    pt_raw = rag._call_llm(pt_prompt, llm_config=model_config)  # type: ignore[attr-defined]
                    pt_text = str(pt_raw or "").strip()
                    if pt_text:
                        break
                except Exception as e:
                    pt_last_exc = e

            if not pt_text:
                st.status = "failed"
                st.error_message = f"小节生成失败: {sid}/{pt_title}, error={pt_last_exc}"
                save_task_state(st)
                raise ValueError(st.error_message)

            # 小标题用 ###
            section_parts.append(f"### {pt_title}\n\n{pt_text}".strip())
            prev_summary = pt_text[:200]

        sec_text = "\n\n".join([p for p in section_parts if p])

        drafts[sid] = sec_text
        graph_state["drafts"] = drafts
        graph_state["prev_summary"] = prev_summary

        # 下一步 idx+1（仍按章节推进，前端显示进度暂按章节；后续可细化到小节）
        graph_state["progress"] = {"current_section_idx": idx + 1, "total_sections": len(outline)}

        # 落盘 drafts
        st.drafts = drafts
        save_task_state(st)

        return graph_state

    def assembler_node(graph_state: Dict[str, Any]) -> Dict[str, Any]:
        tid = str(graph_state.get("thread_id") or thread_id)
        st = load_task_state(tid)
        if st is None:
            return graph_state

        st.status = "assembling"
        save_task_state(st)

        outline = graph_state.get("outline") or []
        drafts = graph_state.get("drafts") or {}
        if not isinstance(outline, list):
            outline = []
        if not isinstance(drafts, dict):
            drafts = {}

        st.final_markdown = _assemble_selected_visuals(
            _assemble_markdown(outline, drafts),
            st.generation_config,
        )
        st.status = "completed"
        st.progress.current_section_idx = len(outline)
        st.progress.total_sections = len(outline)
        save_task_state(st)

        # 永久化存储：写入课程教学资源（generated_materials/blogs）
        try:
            material_id = st.thread_id
            title = f"教学博客：{st.topic}" if st.topic else "教学博客"
            material_data = {
                "material_type": "blog",
                "title": title,
                "topic": st.topic,
                "thread_id": st.thread_id,
                "course_id": st.course_id,
                "created_at": datetime.now().isoformat(),
                "outline": outline,
                "markdown": st.final_markdown,
                "generation_state": {
                    "visuals": dict(st.generation_config.get("visual_plan") or {})
                },
            }
            storage_manager.save_generated_material(
                course_id=st.course_id,
                material_type="blog",
                material_id=material_id,
                material_data=material_data,
            )
        except Exception as e:
            # 不影响主流程完成，但记录错误信息便于排查
            st.error_message = f"保存教学博客到课程资源失败: {e}"
            save_task_state(st)

        graph_state["final_markdown"] = st.final_markdown
        graph_state["status"] = "completed"
        graph_state["progress"] = {"current_section_idx": len(outline), "total_sections": len(outline)}
        return graph_state

    run_blog_task_langgraph(
        thread_id=thread_id,
        planner_chapters_func=planner_chapters_node,
        wait_for_chapter_review_func=wait_for_chapter_review_node,
        planner_points_func=planner_points_node,
        wait_for_outline_review_func=wait_for_outline_review_node,
        executor_func=executor_node,
        assembler_func=assembler_node,
    )
