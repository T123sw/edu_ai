"""LLM-only course knowledge graph draft generation and validation."""

from __future__ import annotations

import json
import math
import re
import copy
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

import httpx

from app.persistence.dependencies import get_postgres_knowledge_repository
from app.persistence.postgres_knowledge_repository import (
    KnowledgeBuildRevisionConflict,
)
from app.services.course_knowledge_graph_incremental import (
    incremental_graph_issues,
    merge_incremental_graph,
)
from app.services.job_store import (
    EduJob,
    JobKind,
    JobStatus,
    create_job,
    update_job,
)
from app.services.runtime_config_resolver import runtime_config_resolver


GRAPH_PROMPT_VERSION = "course-knowledge-graph-v1"
MAX_GRAPH_REPAIR_ATTEMPTS = 2
_ALLOWED_NODE_TYPES = {
    "course",
    "knowledge_module",
    "knowledge_unit",
    "knowledge_point",
}
_PLACEHOLDER_LABEL = re.compile(
    r"^(?:\d+|第?[一二三四五六七八九十百0-9]+(?:章|节|单元)|知识点|课程|模块)$"
)


class CourseKnowledgeGraphGenerationError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        issues: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.issues = [dict(item) for item in issues or []]

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "issues": list(self.issues),
        }


class CourseKnowledgeGraphModelAdapter:
    """OpenAI-compatible adapter resolved from the current user's runtime config."""

    def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        owner_user_id: str,
    ) -> tuple[str, str]:
        config = runtime_config_resolver.resolve(
            "llm", owner_user_id=owner_user_id
        )
        base_url = str(config.get("base_url") or "").strip().rstrip("/")
        api_key = str(config.get("api_key") or "").strip()
        model = str(config.get("model") or "").strip()
        if not base_url or not api_key or not model:
            raise CourseKnowledgeGraphGenerationError(
                "GRAPH_MODEL_UNAVAILABLE",
                "知识图谱生成所需的模型配置不完整",
            )
        if base_url.endswith("/chat/completions"):
            endpoint = base_url
        else:
            if not base_url.endswith(("/v1", "/api/v1")):
                base_url = f"{base_url}/v1"
            endpoint = f"{base_url}/chat/completions"
        try:
            response = httpx.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [dict(item) for item in messages],
                },
                timeout=float(config.get("timeout_seconds") or 120),
            )
            response.raise_for_status()
            payload = response.json()
            content = str(
                (((payload.get("choices") or [{}])[0].get("message") or {}).get("content"))
                or ""
            ).strip()
        except CourseKnowledgeGraphGenerationError:
            raise
        except Exception as exc:
            raise CourseKnowledgeGraphGenerationError(
                "GRAPH_MODEL_UNAVAILABLE",
                f"知识图谱模型调用失败：{exc}",
            ) from exc
        if not content:
            raise CourseKnowledgeGraphGenerationError(
                "GRAPH_SCHEMA_INVALID",
                "知识图谱模型返回了空内容",
            )
        return content, model


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _course_snapshot(build: Mapping[str, Any]) -> dict[str, Any]:
    source = dict(build.get("course_snapshot") or {})
    return {
        key: source.get(key)
        for key in (
            "id",
            "title",
            "description",
            "audience",
            "objectives",
            "language",
            "difficulty",
        )
    }


def _textbook_context(build: Mapping[str, Any]) -> list[dict[str, Any]]:
    context: list[dict[str, Any]] = []
    for textbook in list(build.get("textbooks") or []):
        if not isinstance(textbook, Mapping):
            continue
        if textbook.get("status") and textbook.get("status") != "ready":
            continue
        parsed = dict(textbook.get("parse_result") or {})
        outline = parsed.get("outline") or textbook.get("outline") or []
        context.append(
            {
                "textbook_id": textbook.get("textbook_id") or textbook.get("id"),
                "filename": textbook.get("filename") or textbook.get("name"),
                "summary": _clean(parsed.get("summary") or textbook.get("summary"))[:4000],
                "outline": list(outline)[:200] if isinstance(outline, list) else [],
                "warnings": list(parsed.get("warnings") or [])[:50],
            }
        )
    return context


def _prompt_payload(build: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "course": _course_snapshot(build),
        "config": dict(build.get("config") or {}),
        "update_strategy": (build.get("config") or {}).get("update_strategy"),
        "current_graph": build.get("current_graph_summary"),
        "textbooks": _textbook_context(build),
    }


def _initial_messages(build: Mapping[str, Any]) -> list[dict[str, str]]:
    strategy = str(
        (build.get("config") or {}).get("update_strategy") or "incremental"
    )
    incremental_rules = (
        "当前任务是增量更新。必须保留全部已有节点并复用 current_graph 中的已有节点 ID；"
        "不得删除、改名、移动或重排已有节点；只补充说明、教材映射和真正缺失的新节点。"
        if strategy == "incremental" and build.get("baseline_graph")
        else ""
    )
    contract = {
        "root": {
            "id": "stable-unique-id",
            "label": "semantic label",
            "type": "course | knowledge_module | knowledge_unit | knowledge_point",
            "summary": "specific learning scope",
            "source_outline_refs": ["optional textbook outline id or title"],
            "children": [],
        },
        "unmapped_outline_items": ["outline items intentionally not represented"],
    }
    return [
        {
            "role": "system",
            "content": (
                "你是课程知识架构师。只返回一个合法 JSON 对象，禁止 Markdown、代码围栏和解释。"
                "必须根据课程语义生成图谱，不得把课程目标机械平铺，不得使用数字、‘知识点’、"
                "‘第一章’等无语义孤立标签。所有节点 ID 必须稳定且唯一。根节点为 course，"
                "中间节点为 knowledge_module/knowledge_unit，叶节点为 knowledge_point。"
                f"{incremental_rules}"
            ),
        },
        {
            "role": "user",
            "content": (
                "请按以下输入与输出契约生成可审核的课程知识图谱。模块数、每模块知识点数和深度"
                "必须服从 config，允许目标值上下 20%。教材存在时，每个一级目录必须通过"
                "source_outline_refs 映射，或明确列入 unmapped_outline_items。\n\n"
                f"输入：{json.dumps(_prompt_payload(build), ensure_ascii=False)}\n\n"
                f"输出契约示例：{json.dumps(contract, ensure_ascii=False)}"
            ),
        },
    ]


def _parse_model_payload(content: str) -> dict[str, Any]:
    stripped = str(content or "").strip()
    if not stripped or "```" in stripped:
        raise ValueError("模型输出包含空内容或代码围栏")
    payload = json.loads(stripped)
    if not isinstance(payload, dict) or not isinstance(payload.get("root"), dict):
        raise ValueError("模型输出必须是包含 root 的 JSON 对象")
    return payload


def _normalize_node(raw: Mapping[str, Any], *, level: int) -> dict[str, Any]:
    direct_data = dict(raw.get("data") or {})
    children = raw.get("children")
    if not isinstance(children, list):
        children = []
    node_type = _clean(raw.get("type") or direct_data.get("type"))
    summary = _clean(raw.get("summary") or direct_data.get("summary"))
    refs = raw.get("source_outline_refs") or direct_data.get("source_outline_refs") or []
    return {
        "id": _clean(raw.get("id")),
        "label": _clean(raw.get("label")),
        "children": [
            _normalize_node(item, level=level + 1)
            for item in children
            if isinstance(item, Mapping)
        ],
        "data": {
            **direct_data,
            "level": level,
            "type": node_type,
            "summary": summary,
            "source_outline_refs": [
                _clean(item) for item in refs if _clean(item)
            ]
            if isinstance(refs, list)
            else [],
            "hasChildren": bool(children),
            "document_ids": list(direct_data.get("document_ids") or []),
        },
    }


def _outline_keys(textbooks: Sequence[Mapping[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for textbook in textbooks:
        outline = textbook.get("outline") or []
        if not isinstance(outline, list):
            continue
        for item in outline:
            if isinstance(item, Mapping):
                value = item.get("id") or item.get("title") or item.get("label")
            else:
                value = item
            normalized = _clean(value).casefold()
            if normalized:
                keys.add(normalized)
    return keys


def validate_course_knowledge_graph(
    graph: Mapping[str, Any],
    *,
    config: Mapping[str, Any],
    textbook_outline_keys: set[str] | None = None,
    unmapped_outline_items: Sequence[Any] | None = None,
    enforce_scale: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    leaf_count = 0
    leaf_depths: list[tuple[str, int]] = []
    node_count = 0
    max_depth = 0
    mapped_outline_keys: set[str] = set()

    def issue(code: str, path: str, message: str) -> None:
        issues.append({"code": code, "path": path, "message": message})

    def visit(node: Mapping[str, Any], *, depth: int, path: str) -> None:
        nonlocal leaf_count, node_count, max_depth
        node_count += 1
        max_depth = max(max_depth, depth)
        node_id = _clean(node.get("id"))
        label = _clean(node.get("label"))
        data = dict(node.get("data") or {})
        node_type = _clean(data.get("type") or node.get("type"))
        summary = _clean(data.get("summary") or node.get("summary"))
        children = node.get("children") or []
        if not node_id:
            issue("EMPTY_ID", path, "节点 ID 不能为空")
        elif node_id in seen_ids:
            issue("DUPLICATE_ID", path, f"节点 ID 重复：{node_id}")
        seen_ids.add(node_id)
        if not label:
            issue("EMPTY_LABEL", path, "节点名称不能为空")
        elif _PLACEHOLDER_LABEL.fullmatch(label):
            issue("PLACEHOLDER_LABEL", path, f"节点名称缺少课程语义：{label}")
        if node_type not in _ALLOWED_NODE_TYPES:
            issue("INVALID_TYPE", path, f"不支持的节点类型：{node_type}")
        if not summary:
            issue("EMPTY_SUMMARY", path, "节点说明不能为空")
        if depth == 1 and node_type != "course":
            issue("INVALID_ROOT_TYPE", path, "根节点类型必须为 course")
        if depth > 1 and children and node_type not in {
            "knowledge_module",
            "knowledge_unit",
        }:
            issue("INVALID_BRANCH_TYPE", path, "中间节点类型不合法")
        if not children:
            leaf_count += 1
            leaf_depths.append((path, depth))
            if node_type != "knowledge_point":
                issue("INVALID_LEAF_TYPE", path, "叶节点类型必须为 knowledge_point")
        sibling_labels: set[str] = set()
        for index, child in enumerate(children):
            if not isinstance(child, Mapping):
                issue("INVALID_CHILD", f"{path}.children[{index}]", "子节点必须是对象")
                continue
            child_label = _clean(child.get("label")).casefold()
            if child_label and child_label in sibling_labels:
                issue(
                    "DUPLICATE_SIBLING_LABEL",
                    f"{path}.children[{index}]",
                    f"同级节点名称重复：{child.get('label')}",
                )
            sibling_labels.add(child_label)
            visit(child, depth=depth + 1, path=f"{path}.children[{index}]")
        for ref in list(data.get("source_outline_refs") or []):
            normalized = _clean(ref).casefold()
            if normalized:
                mapped_outline_keys.add(normalized)

    visit(graph, depth=1, path="root")
    target_depth = int(config.get("graph_depth") or 3)
    if max_depth != target_depth:
        issue(
            "DEPTH_MISMATCH",
            "root",
            f"实际深度 {max_depth}，目标深度 {target_depth}",
        )
    for path, depth in leaf_depths:
        if depth != target_depth:
            issue(
                "LEAF_DEPTH_MISMATCH",
                path,
                f"叶节点位于第 {depth} 层，必须位于目标第 {target_depth} 层",
            )
    children = graph.get("children") or []
    module_count = len(children) if isinstance(children, list) else 0
    target_modules = int(config.get("target_module_count") or 4)
    target_points = target_modules * int(
        config.get("target_points_per_module") or 4
    )

    def outside_tolerance(actual: int, target: int) -> bool:
        return actual < math.ceil(target * 0.8) or actual > math.floor(target * 1.2)

    if enforce_scale and outside_tolerance(module_count, target_modules):
        issue(
            "MODULE_SCALE_MISMATCH",
            "root.children",
            f"实际模块数 {module_count}，目标 {target_modules}（允许上下 20%）",
        )
    if enforce_scale and outside_tolerance(leaf_count, target_points):
        issue(
            "LEAF_SCALE_MISMATCH",
            "root",
            f"实际知识点数 {leaf_count}，目标 {target_points}（允许上下 20%）",
        )
    required_outline = set(textbook_outline_keys or set())
    explicitly_unmapped = {
        _clean(item).casefold()
        for item in list(unmapped_outline_items or [])
        if _clean(item)
    }
    missing_outline = sorted(
        required_outline - mapped_outline_keys - explicitly_unmapped
    )
    for key in missing_outline:
        issue(
            "TEXTBOOK_OUTLINE_UNACCOUNTED",
            "root",
            f"教材目录未映射且未明确列为未映射：{key}",
        )
    return issues, {
        "node_count": node_count,
        "module_count": module_count,
        "leaf_count": leaf_count,
        "max_depth": max_depth,
        "target_module_count": target_modules,
        "target_leaf_count": target_points,
        "mapped_outline_count": len(mapped_outline_keys),
        "unmapped_outline_count": len(explicitly_unmapped),
    }


def validate_graph_draft_for_build(
    build: Mapping[str, Any], graph: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    textbooks = _textbook_context(build)
    unmapped = list((graph.get("data") or {}).get("unmapped_outline_items") or [])
    strategy = str(
        (build.get("config") or {}).get("update_strategy") or "incremental"
    )
    baseline_graph = build.get("baseline_graph")
    issues, metrics = validate_course_knowledge_graph(
        graph,
        config=dict(build.get("config") or {}),
        textbook_outline_keys=_outline_keys(textbooks),
        unmapped_outline_items=unmapped,
        enforce_scale=not (strategy == "incremental" and bool(baseline_graph)),
    )
    if strategy == "incremental":
        issues.extend(incremental_graph_issues(baseline_graph, graph))
    return issues, metrics


def generate_course_knowledge_graph_draft(
    build: Mapping[str, Any],
    *,
    owner_user_id: str,
    model_adapter: CourseKnowledgeGraphModelAdapter | Any | None = None,
    now: Callable[[], datetime] | None = None,
    max_repairs: int = MAX_GRAPH_REPAIR_ATTEMPTS,
) -> dict[str, Any]:
    adapter = model_adapter or CourseKnowledgeGraphModelAdapter()
    messages = _initial_messages(build)
    textbooks = _textbook_context(build)
    outline_keys = _outline_keys(textbooks)
    last_issues: list[dict[str, Any]] = []
    last_content = ""
    model_name = ""
    for attempt in range(max(0, int(max_repairs)) + 1):
        try:
            last_content, model_name = adapter.complete(
                messages,
                owner_user_id=owner_user_id,
            )
            payload = _parse_model_payload(last_content)
            candidate_graph = _normalize_node(payload["root"], level=0)
            strategy = str(
                (build.get("config") or {}).get("update_strategy") or "incremental"
            )
            baseline_graph = build.get("baseline_graph")
            graph = (
                merge_incremental_graph(baseline_graph, candidate_graph)
                if strategy == "incremental" and isinstance(baseline_graph, Mapping)
                else candidate_graph
            )
            unmapped = list(payload.get("unmapped_outline_items") or [])
            issues, metrics = validate_course_knowledge_graph(
                graph,
                config=dict(build.get("config") or {}),
                textbook_outline_keys=outline_keys,
                unmapped_outline_items=unmapped,
                enforce_scale=not (
                    strategy == "incremental" and bool(baseline_graph)
                ),
            )
            if strategy == "incremental":
                issues.extend(incremental_graph_issues(baseline_graph, graph))
        except CourseKnowledgeGraphGenerationError:
            raise
        except Exception as exc:
            issues = [
                {
                    "code": "INVALID_JSON",
                    "path": "root",
                    "message": str(exc),
                }
            ]
            graph = {}
            metrics = {}
            unmapped = []
        if not issues:
            generated_at = (now or (lambda: datetime.now(timezone.utc)))()
            graph.setdefault("data", {}).update(
                {
                    "generation_model": model_name,
                    "prompt_version": GRAPH_PROMPT_VERSION,
                    "generated_at": generated_at.isoformat(),
                    "validation": {"status": "passed", **metrics},
                    "unmapped_outline_items": unmapped,
                    "baseline_graph_version": build.get("baseline_graph_version"),
                    "update_strategy": strategy,
                }
            )
            return graph
        last_issues = issues
        if attempt < max_repairs:
            messages.extend(
                [
                    {"role": "assistant", "content": last_content[:30000]},
                    {
                        "role": "user",
                        "content": (
                            "上一个 JSON 未通过确定性校验。请返回完整修正版 JSON，不要解释。"
                            f"校验错误：{json.dumps(issues, ensure_ascii=False)}"
                        ),
                    },
                ]
            )
    scale_codes = {"MODULE_SCALE_MISMATCH", "LEAF_SCALE_MISMATCH", "DEPTH_MISMATCH"}
    code = (
        "GRAPH_SCALE_UNSATISFIED"
        if last_issues and all(item.get("code") in scale_codes for item in last_issues)
        else "GRAPH_SCHEMA_INVALID"
    )
    raise CourseKnowledgeGraphGenerationError(
        code,
        "模型生成的知识图谱在修复后仍未通过校验",
        issues=last_issues,
    )


def regenerate_course_knowledge_graph_module(
    build: Mapping[str, Any],
    *,
    module_id: str,
    owner_user_id: str,
    model_adapter: CourseKnowledgeGraphModelAdapter | Any | None = None,
    now: Callable[[], datetime] | None = None,
    max_repairs: int = MAX_GRAPH_REPAIR_ATTEMPTS,
) -> dict[str, Any]:
    current_graph = copy.deepcopy(build.get("graph_draft") or {})
    modules = list(current_graph.get("children") or [])
    module_index = next(
        (
            index
            for index, item in enumerate(modules)
            if _clean((item or {}).get("id")) == _clean(module_id)
        ),
        None,
    )
    if module_index is None:
        raise CourseKnowledgeGraphGenerationError(
            "GRAPH_SCHEMA_INVALID",
            "要重新生成的知识模块不存在",
        )
    adapter = model_adapter or CourseKnowledgeGraphModelAdapter()
    selected = modules[module_index]
    messages = _initial_messages(build)
    messages.append(
        {
            "role": "user",
            "content": (
                "本次只重新生成一个模块。输出 JSON 的 root 必须是 knowledge_module，"
                f"必须保持模块 ID 为 {_clean(module_id)}。未选择模块不应出现在输出中。"
                f"当前模块：{json.dumps(selected, ensure_ascii=False)}"
            ),
        }
    )
    textbooks = _textbook_context(build)
    outline_keys = _outline_keys(textbooks)
    last_issues: list[dict[str, Any]] = []
    last_content = ""
    model_name = ""
    for attempt in range(max(0, int(max_repairs)) + 1):
        try:
            last_content, model_name = adapter.complete(
                messages,
                owner_user_id=owner_user_id,
            )
            payload = _parse_model_payload(last_content)
            replacement = _normalize_node(payload["root"], level=1)
            strategy = str(
                (build.get("config") or {}).get("update_strategy") or "incremental"
            )
            candidate = copy.deepcopy(current_graph)
            candidate["children"][module_index] = (
                merge_incremental_graph(selected, replacement)
                if strategy == "incremental" and build.get("baseline_graph")
                else replacement
            )
            unmapped = list(
                payload.get("unmapped_outline_items")
                or (candidate.get("data") or {}).get("unmapped_outline_items")
                or []
            )
            issues: list[dict[str, Any]] = []
            if replacement.get("id") != _clean(module_id):
                issues.append(
                    {
                        "code": "MODULE_ID_CHANGED",
                        "path": "root.id",
                        "message": "局部重新生成不得改变模块 ID",
                    }
                )
            if (replacement.get("data") or {}).get("type") != "knowledge_module":
                issues.append(
                    {
                        "code": "INVALID_MODULE_TYPE",
                        "path": "root.type",
                        "message": "局部重新生成的根必须是 knowledge_module",
                    }
                )
            validation_issues, metrics = validate_course_knowledge_graph(
                candidate,
                config=dict(build.get("config") or {}),
                textbook_outline_keys=outline_keys,
                unmapped_outline_items=unmapped,
                enforce_scale=not (
                    strategy == "incremental" and bool(build.get("baseline_graph"))
                ),
            )
            issues.extend(validation_issues)
            if strategy == "incremental":
                issues.extend(
                    incremental_graph_issues(build.get("baseline_graph"), candidate)
                )
        except CourseKnowledgeGraphGenerationError:
            raise
        except Exception as exc:
            issues = [
                {
                    "code": "INVALID_JSON",
                    "path": "root",
                    "message": str(exc),
                }
            ]
            candidate = {}
            metrics = {}
            unmapped = []
        if not issues:
            generated_at = (now or (lambda: datetime.now(timezone.utc)))()
            candidate.setdefault("data", {}).update(
                {
                    "generation_model": model_name,
                    "prompt_version": GRAPH_PROMPT_VERSION,
                    "generated_at": generated_at.isoformat(),
                    "validation": {"status": "passed", **metrics},
                    "unmapped_outline_items": unmapped,
                    "regenerated_module_id": _clean(module_id),
                }
            )
            return candidate
        last_issues = issues
        if attempt < max_repairs:
            messages.extend(
                [
                    {"role": "assistant", "content": last_content[:30000]},
                    {
                        "role": "user",
                        "content": (
                            "局部模块未通过校验。只返回该模块的完整修正版 JSON。"
                            f"错误：{json.dumps(issues, ensure_ascii=False)}"
                        ),
                    },
                ]
            )
    raise CourseKnowledgeGraphGenerationError(
        "GRAPH_SCHEMA_INVALID",
        "模型重新生成的知识模块在修复后仍未通过校验",
        issues=last_issues,
    )


def submit_course_knowledge_graph_generation_job(
    *,
    course_id: str,
    owner_user_id: str,
    build_id: str,
    expected_revision: int,
    target_module_id: str | None = None,
) -> EduJob:
    repository = get_postgres_knowledge_repository()
    build = repository.get_build(build_id)
    if build is None or str(build.get("library_id") or "") != course_id:
        raise ValueError("知识库构建草案不存在")
    if build.get("status") != "draft":
        raise ValueError("只有草案状态可以生成知识图谱")
    if int(build.get("revision") or 0) != int(expected_revision):
        raise KnowledgeBuildRevisionConflict(
            f"构建草案版本冲突：当前 {build.get('revision')}，提交 {expected_revision}"
        )
    unavailable_textbooks = [
        item
        for item in build.get("textbooks") or []
        if str(item.get("status") or "") != "ready"
    ]
    if unavailable_textbooks:
        raise ValueError("请等待所有已上传教材解析完成，或移除解析失败的教材")
    job = create_job(
        kind=JobKind.GENERATE_GRAPH,
        owner_user_id=owner_user_id,
        course_id=course_id,
        input_summary={
            "build_id": build_id,
            "expected_revision": int(expected_revision),
            "prompt_version": GRAPH_PROMPT_VERSION,
            "target_module_id": _clean(target_module_id) or None,
        },
    )
    from app.services.platform_task_handlers import enqueue_platform_task

    return enqueue_platform_task(
        job=job,
        workflow_type="course_knowledge_graph_generate",
        command={
            "course_id": course_id,
            "build_id": build_id,
            "expected_revision": int(expected_revision),
            "target_module_id": _clean(target_module_id) or None,
            "deadline_seconds": 600,
        },
        runtime_config_snapshot=runtime_config_resolver.capture_snapshot(
            owner_user_id
        ),
    )


def run_course_knowledge_graph_generation_job(
    *,
    job_id: str,
    course_id: str,
    owner_user_id: str,
    build_id: str,
    expected_revision: int,
    target_module_id: str | None = None,
    progress: Callable[[int, str, str], None] | None = None,
    model_adapter: CourseKnowledgeGraphModelAdapter | Any | None = None,
) -> dict[str, Any]:
    repository = get_postgres_knowledge_repository()
    build = repository.get_build(build_id)
    try:
        if build is None or str(build.get("library_id") or "") != course_id:
            raise ValueError("知识库构建草案不存在")
        if int(build.get("revision") or 0) != int(expected_revision):
            raise KnowledgeBuildRevisionConflict("生成图谱前构建草案已被修改")
        if progress:
            progress(10, "graph_generating", "正在调用模型生成知识图谱草案")
        if _clean(target_module_id):
            graph = regenerate_course_knowledge_graph_module(
                build,
                module_id=_clean(target_module_id),
                owner_user_id=owner_user_id,
                model_adapter=model_adapter,
            )
        else:
            graph = generate_course_knowledge_graph_draft(
                build,
                owner_user_id=owner_user_id,
                model_adapter=model_adapter,
            )
        if progress:
            progress(85, "graph_validating", "正在校验图谱结构与规模")
        updated = repository.update_build_draft(
            build_id,
            expected_revision=expected_revision,
            changes={
                "graph_draft": graph,
                "graph_generation_error": None,
            },
            phase="graph_review",
        )
        result = {
            "course_id": course_id,
            "build_id": build_id,
            "revision": updated["revision"],
            "phase": updated["phase"],
        }
        update_job(
            job_id,
            status=JobStatus.SUCCEEDED,
            step="graph_review",
            progress=100,
            message="知识图谱草案已生成，请审核确认",
            result_ref=result,
        )
        return result
    except Exception as exc:
        error = (
            exc.to_dict()
            if isinstance(exc, CourseKnowledgeGraphGenerationError)
            else {"code": "GRAPH_GENERATION_FAILED", "message": str(exc), "issues": []}
        )
        current = repository.get_build(build_id)
        if current and int(current.get("revision") or 0) == int(expected_revision):
            try:
                repository.update_build_draft(
                    build_id,
                    expected_revision=expected_revision,
                    changes={"graph_generation_error": error},
                    phase="graph_review",
                )
            except Exception:
                pass
        update_job(
            job_id,
            status=JobStatus.FAILED,
            step="graph_generation_failed",
            progress=100,
            message="知识图谱草案生成失败",
            error_code=str(error.get("code") or "GRAPH_GENERATION_FAILED"),
            error_message=str(error.get("message") or exc),
        )
        raise
