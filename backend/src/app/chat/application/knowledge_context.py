"""Trusted workspace resolution and one durable, actor-bound pending operation.

C integration: pending_operation is shared; kind='artifact_revision' belongs to C.
Only scope operations are consumed here. Replies use the existing result SSE event.
"""
from __future__ import annotations

import re
from uuid import uuid4
from pydantic import BaseModel, Field
from typing import Literal


class ScopeCandidate(BaseModel):
    scope_id: str
    scope_title: str
    scope_path: list[str]
    aliases: list[str] = Field(default_factory=list)


class ResolvedWorkspaceContext(BaseModel):
    course_id: str | None = None
    course_title: str = ""
    scope_type: str = "course"
    scope_id: str | None = None
    scope_title: str = ""
    scope_path: list[str] = Field(default_factory=list)
    resolution: Literal["resolved", "needs_clarification", "invalid"] = "needs_clarification"
    explicit_course: bool = False
    update_workspace: bool = False


class ScopeClarification(BaseModel):
    status: Literal["needs_clarification"] = "needs_clarification"
    operation_id: str
    question: str
    candidates: list[ScopeCandidate] = Field(default_factory=list)


def knowledge_candidates(graph: dict | None) -> list[ScopeCandidate]:
    result = []
    def visit(node, path, root=False):
        if not isinstance(node, dict):
            return
        title = str(node.get("label") or node.get("title") or "").strip()
        path = [*path, title] if title else path
        if not root and node.get("id") and title:
            aliases = node.get("aliases") or []
            if isinstance(aliases, str):
                aliases = [aliases]
            result.append(ScopeCandidate(scope_id=str(node["id"]), scope_title=title, scope_path=path, aliases=aliases))
        for child in node.get("children") or []:
            visit(child, path)
    visit((graph or {}).get("root", graph), [], True)
    return result


def topic_aliases(candidate: ScopeCandidate) -> list[str]:
    # Course nodes often combine related concepts: 数组与链表 / 迭代、递归与终止条件.
    parts = re.split(r"[、，,/与和及]|(?:以及)", candidate.scope_title)
    return [word.strip() for word in [candidate.scope_title, *candidate.aliases, *parts]
            if len(word.strip()) >= 2]


def match_knowledge_topics(question: str, candidates: list[ScopeCandidate]) -> list[ScopeCandidate]:
    explicit = [c for c in candidates if question == c.scope_id or " › ".join(c.scope_path) == question]
    if explicit:
        return explicit
    # A correction or next-topic statement takes precedence over its old topic.
    focus = re.split(r"(?:接下来|改讲|换成|切换到|换到|切到|转而|改为)", question)[-1]
    matches = [c for c in candidates if any(alias in focus for alias in topic_aliases(c))]
    # Prefer a named child to its containing chapter; same-name siblings remain ambiguous.
    return [c for c in matches if not any(c.scope_id != d.scope_id and
            c.scope_path == d.scope_path[:len(c.scope_path)] for d in matches)]


def requires_generation(request) -> bool:
    from app.chat.runtime.planning.task_contract_extractor import extract_task_contract
    intent = extract_task_contract(request, request.capability).intent
    return (str(request.action_hint or "").startswith("generate.")
            or intent in {"generate_single", "prepare_bundle", "confirm"}
            or bool(re.search(r"(?:生成|制作|创建|准备).*(?:资料|材料)", request.question)))


class KnowledgeContextService:
    def __init__(self, *, course_storage, conversation_storage, authorize):
        self.courses = course_storage
        self.conversations = conversation_storage
        self.authorize = authorize

    def cancel(self, *, owner: str, conversation_id: str, operation_id: str) -> bool:
        self.conversations.get_conversation(conversation_id, owner=owner)
        pending = self.conversations.get_state(conversation_id).get("pending_operation") or {}
        if pending.get("owner") != owner or pending.get("id") != operation_id:
            return False
        self.conversations.update_state(conversation_id, {"pending_operation": None})
        return True

    def resolve(self, request) -> tuple[ResolvedWorkspaceContext, list[ScopeCandidate]]:
        context = ResolvedWorkspaceContext(course_id=request.course_id)
        if not request.course_id:
            return context, []
        self.authorize(request)
        course = self.courses.get_course_info(request.course_id)
        if not course:
            context.resolution = "invalid"
            return context, []
        context.course_title = str(course.get("name") or course.get("title") or request.course_id)
        candidates = knowledge_candidates(self.courses.get_knowledge_graph(request.course_id))
        if request.scope_type not in {None, "course", "knowledge_point"}:
            context.resolution = "invalid"
        elif request.scope_type == "knowledge_point":
            target = next((c for c in candidates if c.scope_id == request.scope_id), None)
            if target is None:
                context.resolution = "invalid"
            else:
                context.scope_type = "knowledge_point"
                context.scope_id = target.scope_id
                context.scope_title = target.scope_title
                context.scope_path = target.scope_path
                context.resolution = "resolved"
        return context, candidates

    def prepare_model(self, request):
        """Validate supplied context without interpreting the user's language."""
        try:
            self.conversations.get_conversation(request.conversation_id, owner=request.owner)
        except KeyError:
            try:
                self.conversations.get_conversation(request.conversation_id)
            except KeyError:
                self.conversations.ensure_conversation(request.conversation_id, request.question, owner=request.owner)
            else:
                raise PermissionError("conversation access denied")
        context, _ = self.resolve(request)
        request.workspace_context = context
        if context.resolution == "invalid":
            return self._result(request, "当前讨论范围已失效，请调整范围后继续。", "workspace.invalid")
        return None

    def prepare(self, request) -> dict | None:
        # Check ownership before reading either history or pending state. Never
        # adopt an existing conversation just because its ID was supplied.
        storage = self.conversations
        try:
            storage.get_conversation(request.conversation_id, owner=request.owner)
        except KeyError:
            try:
                storage.get_conversation(request.conversation_id)
            except KeyError:
                storage.ensure_conversation(request.conversation_id, request.question, owner=request.owner)
            else:
                raise PermissionError("conversation access denied")
        context, candidates = self.resolve(request)
        request.workspace_context = context
        revision_intent = bool(request.artifact_reference) or bool(re.search(r"修改|改写|重写|调整|简化|改一下|删掉", request.question))
        if context.resolution == "invalid" and not revision_intent:
            return self._result(request, "当前知识点已失效或不属于此课程，请重新选择。", "workspace.invalid")
        state = storage.get_state(request.conversation_id)
        pending = state.get("pending_operation") or {}
        if pending and (pending.get("owner") != request.owner or pending.get("course_id") != request.course_id):
            storage.update_state(request.conversation_id, {"pending_operation": None})
            return self._result(request, "讨论范围已改变，已取消原待处理操作。请重新提出需求。", "operation.cancelled")
        # A resolved artifact must retain C's original scope and version.
        if pending and pending.get("scope_id") != request.scope_id:
            storage.update_state(request.conversation_id, {"pending_operation": None})
            return self._result(request, "知识点已切换，已取消原待处理操作。请重新提出需求。", "operation.cancelled")
        question = request.question.strip()
        if pending and question in {"取消", "取消操作", "不用了"}:
            storage.update_state(request.conversation_id, {"pending_operation": None})
            return self._result(request, "已取消待处理操作。", "operation.cancelled")
        if (revision_intent and pending.get("kind") != "workspace_scope") or pending.get("kind") == "artifact_revision":
            return None
        switching = bool(re.search(r"(?:切换到|换到|切到)", question)) or pending.get("operation") == "switch"
        generating = (bool(pending) and pending.get("operation") != "switch") or requires_generation(request)
        from app.chat.runtime.planning.task_contract_extractor import _is_outline_confirmation
        generation_workspace = state.get("generation_workspace") or {}
        if (_is_outline_confirmation(question)
                and generation_workspace.get("owner") == request.owner
                and generation_workspace.get("course_id") == request.course_id
                and generation_workspace.get("page_scope_type") == request.scope_type
                and generation_workspace.get("page_scope_id") == request.scope_id):
            generating = True
            previous = ResolvedWorkspaceContext.model_validate(generation_workspace["context"])
            context, candidates = self.resolve(request.model_copy(update={"scope_type": previous.scope_type, "scope_id": previous.scope_id}))
            context.explicit_course = previous.explicit_course
            if context.explicit_course:
                context.resolution = "resolved"
                context.scope_title, context.scope_path = context.course_title, [context.course_title]
            request.workspace_context = context
            if context.resolution == "invalid":
                return self._result(request, "原任务的知识点已失效，请重新选择。", "workspace.invalid")
        matches = match_knowledge_topics(question, candidates)
        # Resolve topics during ordinary explanation and lesson preparation too.
        # Do not turn a greeting or a comparison into a forced scope picker.
        if not matches and not switching and not re.search(r"整门课程|整个课程|全课程|关于|针对|围绕", question):
            remembered = state.get("discussion_workspace") or {}
            if (context.scope_type == "course" and remembered.get("owner") == request.owner
                    and remembered.get("course_id") == request.course_id):
                previous = remembered.get("context") or {}
                target = next((c for c in candidates if c.scope_id == previous.get("scope_id")), None)
                if target and request.scope_type != "course":
                    matches = [target]
        if not generating and not switching and len(matches) != 1:
            return None
        whole_course = bool(re.search(r"整门课程|全课程|整个课程|所有知识点|全课", question))
        if whole_course:
            context.scope_type, context.scope_id = "course", None
            context.scope_title, context.scope_path = context.course_title, [context.course_title]
            context.resolution, context.explicit_course = "resolved", True
        elif len(matches) == 1:
            target = matches[0]
            context.scope_type, context.scope_id = "knowledge_point", target.scope_id
            context.scope_title, context.scope_path = target.scope_title, target.scope_path
            context.resolution = "resolved"
        elif len(matches) > 1 or switching or pending or re.search(r"(?:围绕|针对|关于)\s*(?!当前|这个|本)(?:[^，。]+)", question):
            context.resolution = "needs_clarification"
        if context.resolution != "resolved":
            operation = pending or {
                "id": uuid4().hex, "kind": "workspace_scope", "operation": "switch" if switching else "generate", "owner": request.owner,
                "course_id": request.course_id, "scope_id": request.scope_id,
                "request": request.model_dump(mode="json", exclude={"workspace_context"}),
            }
            storage.update_state(request.conversation_id, {"pending_operation": operation})
            prompt = "你指的是哪一部分：" + "、".join(" › ".join(c.scope_path[-2:]) for c in matches) + "？" if matches else "这份资料要聚焦哪个主题？可以直接告诉我知识点名称。"
            result = self._result(request, prompt, "workspace.clarify")
            result["clarification"] = ScopeClarification(operation_id=operation["id"], question=prompt, candidates=(matches or candidates)[:30]).model_dump()
            return result
        if pending:
            from app.chat.domain.contracts import ChatRequestV2
            original = ChatRequestV2.model_validate(pending["request"])
            request.question = original.question + "\n用户补充：" + question
            request.capability = original.capability
            request.action_hint = original.action_hint
            request.input_images, request.input_videos = original.input_images, original.input_videos
            storage.update_state(request.conversation_id, {"pending_operation": None})
        switching = switching or pending.get("operation") == "switch"
        if generating:
            storage.update_state(request.conversation_id, {"generation_workspace": {
                "owner": request.owner, "course_id": request.course_id,
                "page_scope_type": request.scope_type, "page_scope_id": request.scope_id,
                "context": context.model_dump(),
            }})
        context.update_workspace = switching or bool(pending) or (
            context.scope_type != request.scope_type or context.scope_id != request.scope_id)
        storage.update_state(request.conversation_id, {"discussion_workspace": {
            "owner": request.owner, "course_id": request.course_id, "context": context.model_dump(),
        }})
        request.scope_type, request.scope_id = context.scope_type, context.scope_id
        if switching and not generating:
            return self._result(request, "已切换到 " + " › ".join(context.scope_path), "workspace.changed")
        return None

    @staticmethod
    def _result(request, message, action):
        return {"message": {"role": "assistant", "content": message},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": action}, "artifacts": [], "sources": [],
                "trace": {"path": "fast"},
                "workspace_context": request.workspace_context.model_dump()}


def authorize_workspace(request):
    from app.api.course_dependencies import get_course_access_service
    get_course_access_service().require(request.course_id, {
        "username": request.owner, "role": request.actor_role,
    }, "read")


def validate_generation_scope(request):
    """Revalidate immediately before a generation side effect; no model override."""
    context = getattr(request, "workspace_context", None)
    if context is None:
        return  # Legacy/internal callers remain compatible; v2 always resolves.
    if context.resolution != "resolved" or (context.scope_type == "course" and not context.explicit_course):
        raise ValueError("needs_clarification: 请先明确知识点或整门课程范围")
    from core.course_storage import storage_manager
    authorize_workspace(request)
    if context.scope_type == "knowledge_point" and not any(
        c.scope_id == context.scope_id for c in knowledge_candidates(storage_manager.get_knowledge_graph(context.course_id))
    ):
        raise ValueError("知识点已失效，请重新选择")


def resolve_direct_workspace(payload, course_storage) -> ResolvedWorkspaceContext:
    """Factory entry: explicit node or unambiguous configured topic is required.

    Authorization remains at the HTTP route; this validates graph membership
    before source retrieval or durable job submission.
    """
    from app.chat.domain.contracts import ChatRequestV2
    topic_parts = [str(getattr(payload, name, '') or '') for name in ('question', 'topic', 'title', 'requirement', 'final_user_prompt')]
    for name in ('report_config', 'quiz_config', 'flashcard_config'):
        config = getattr(payload, name, None)
        if hasattr(config, 'model_dump'):
            config = config.model_dump()
        if isinstance(config, dict):
            topic_parts.extend(str(config.get(key) or '') for key in ('topic', 'title'))
    question = ' '.join(topic_parts)
    request = ChatRequestV2(question=question, course_id=payload.course_id, scope_type=payload.scope_type, scope_id=payload.scope_id)
    resolver = KnowledgeContextService(course_storage=course_storage, conversation_storage=None, authorize=lambda request: None)
    context, candidates = resolver.resolve(request)
    if context.resolution == 'invalid':
        raise ValueError('当前知识点已失效或不属于此课程，请重新选择。')
    matches = [candidate for candidate in candidates if candidate.scope_title in question]
    matches = [c for c in matches if not any(c.scope_id != d.scope_id and c.scope_path == d.scope_path[:len(c.scope_path)] for d in matches)]
    if re.search(r'整门课程|整个课程|全课程|所有知识点', question):
        context.explicit_course, context.resolution = True, 'resolved'
        context.scope_type, context.scope_id = 'course', None
        context.scope_title, context.scope_path = context.course_title, [context.course_title]
    elif len(matches) == 1:
        target = matches[0]
        context.scope_type, context.scope_id = 'knowledge_point', target.scope_id
        context.scope_title, context.scope_path = target.scope_title, target.scope_path
        context.resolution = 'resolved'
    elif len(matches) > 1 or context.resolution != 'resolved':
        raise ValueError('请先在当前讨论范围中选择知识点，再生成资料；如需整门课程，请在主题中明确说明。')
    # Every factory has a topic/title field, but some generators never see
    # the question. Bind those actual generator inputs as well as saved IDs.
    def bind(value):
        text = str(value or '').strip()
        for generic in ('当前课程', '本课程', '当前知识点'):
            text = text.replace(generic, context.scope_title)
        return text if context.scope_title in text else f'{context.scope_title}：{text}' if text else context.scope_title
    for field in ('question', 'topic', 'title', 'requirement', 'prompt_draft', 'final_user_prompt'):
        if hasattr(payload, field) and (getattr(payload, field) or field in {'question', 'topic', 'title', 'requirement'}):
            setattr(payload, field, bind(getattr(payload, field)))
    for field in ('report_config', 'quiz_config', 'flashcard_config'):
        config = getattr(payload, field, None)
        if isinstance(config, dict):
            setattr(payload, field, {**config, **{key: bind(config[key]) for key in ('title', 'topic') if key in config}})
        elif hasattr(config, 'model_dump'):
            for key in ('title', 'topic'):
                if hasattr(config, key):
                    setattr(config, key, bind(getattr(config, key)))
    payload.scope_type, payload.scope_id = context.scope_type, context.scope_id
    return context
