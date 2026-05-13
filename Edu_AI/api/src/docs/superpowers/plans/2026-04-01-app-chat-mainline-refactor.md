# App/Chat Mainline Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不丢失现有 `app/chat` 用户能力的前提下，重建主链路为 `orchestrator + fast path + workflow path`，并将 `RAG/web` 改成前端显式控制、后端策略感知的能力。

**Architecture:** 新入口由 `application/chat_app_service.py` 和 `orchestrator/main_orchestrator.py` 组成，普通聊天直接进入 `runtime/fast_chat_runtime.py`，生成型任务进入 `workflows/*/runtime.py`。现有 `service.py` 退化为 `legacy/compat_service.py` 风格的桥接层，报告能力先包裹 `universal_report_engine.py`，再逐步收敛到 `workflows/report/runtime.py` 单一入口。

**Tech Stack:** FastAPI, Pydantic, 现有 `ChatModelGateway`, JSON file storage, pytest

**Repository Note:** 当前目录不是 git 仓库，本计划中的“提交”步骤统一替换为“记录 checkpoint 文件 + 验证输出”。如果后续初始化 git，可将 checkpoint 步骤等价替换为 commit。

---

## File Structure

### New Files

- `app/chat/application/chat_app_service.py`: 新主服务，负责标准请求入口、调用 orchestrator、统一响应与持久化。
- `app/chat/application/request_normalizer.py`: 将 v1/v2 请求转为内部统一 `ChatRequestV2`。
- `app/chat/application/response_builder.py`: 将运行时结果转为 v1/v2 HTTP 响应与 SSE 事件。
- `app/chat/domain/actions.py`: 产品动作枚举。
- `app/chat/domain/capability_policy.py`: `allow_rag/allow_web/allow_tools` 等能力策略对象。
- `app/chat/domain/artifact_ref.py`: 活跃产物引用。
- `app/chat/domain/workflow_state.py`: 统一工作流状态契约。
- `app/chat/domain/conversation_snapshot.py`: 编排层读取的会话快照。
- `app/chat/domain/route_decision.py`: 路由决策对象。
- `app/chat/domain/contracts.py`: `ChatRequestV2`, `ChatResult`, `SseEvent` 等公共契约。
- `app/chat/orchestrator/main_orchestrator.py`: 主编排器，唯一全局路由入口。
- `app/chat/orchestrator/route_rules.py`: 规则优先路由逻辑。
- `app/chat/orchestrator/route_fallback_model.py`: 轻量模型兜底路由。
- `app/chat/orchestrator/context_builder.py`: 构建 `ConversationSnapshot`。
- `app/chat/orchestrator/workflow_resumer.py`: 续接工作流逻辑。
- `app/chat/orchestrator/workflow_interrupts.py`: 打断、取消、切换规则。
- `app/chat/runtime/fast_chat_runtime.py`: 普通聊天快路径。
- `app/chat/runtime/model_registry.py`: 从现有配置中解析默认模型与 gateway。
- `app/chat/runtime/tool_registry.py`: 基于 `CapabilityPolicy` 暴露工具。
- `app/chat/retrieval/retrieval_policy.py`: 检索/web 能力门控。
- `app/chat/retrieval/retrieval_runtime.py`: 包装本地 RAG 调用。
- `app/chat/retrieval/web_runtime.py`: 包装 web/research 能力。
- `app/chat/workflows/report/runtime.py`: 报告工作流唯一入口。
- `app/chat/workflows/report/state.py`: 报告工作流状态映射。
- `app/chat/workflows/report/contracts.py`: 报告工作流输入输出。
- `app/chat/persistence/conversation_store_adapter.py`: 适配 `core.conversation_storage`。
- `app/chat/persistence/artifact_store_adapter.py`: 产物写入与读取。
- `app/chat/memory/ports.py`: `MemoryReader`, `MemoryWriter`, `ConversationSummarizer` 协议。
- `app/chat/legacy/compat_service.py`: 旧 `service.py` 的兼容桥接。
- `tests/chat/test_request_normalizer.py`
- `tests/chat/test_route_rules.py`
- `tests/chat/test_fast_chat_runtime.py`
- `tests/chat/test_report_workflow_runtime.py`
- `tests/chat/test_capability_policy.py`
- `tests/chat/test_v2_routes.py`

### Modified Files

- `app/chat/routes.py`: 切换为新 `chat_app_service`，保留现有 HTTP/SSE 路由入口。
- `app/chat/schemas.py`: 新增 v2 schema，并保持 v1 响应兼容。
- `app/chat/service.py`: 缩减为旧接口委托层，逐步退出主逻辑。
- `app/chat/report_domain.py`: 保留领域常量，但迁移类型引用。
- `app/chat/tools/search_tools.py`: 仅保留工具实现，不再直接参与主路由。
- `app/chat/tools/agent_tools.py`: 通过 `runtime/tool_registry.py` 间接接入。

### Deleted After Migration

- `app/chat/agents/supervisor_agent.py`
- `app/chat/agents/router_agent.py`
- `app/chat/agents/chat_agent.py`
- `app/chat/agents/research_agent.py`
- `app/chat/intent_router.py`
- `app/chat/resource_type_router.py`
- `app/chat/response_planner.py`
- `app/chat/graph_state.py`

## Capability Migration Matrix

| 能力 | 本轮目标承接方 | 迁移方式 | 删除旧主入口前置条件 |
| --- | --- | --- | --- |
| `chat.reply` | `runtime/fast_chat_runtime.py` | 直接迁入新主链路 | 快路径支持上下文、多轮追问、无默认工具 |
| `chat.rewrite` | `runtime/fast_chat_runtime.py` | 新增 active artifact 感知 | rewrite 不再依赖全局意图分类 |
| `generate.report` | `workflows/report/runtime.py` | 新 runtime 包裹 `universal_report_engine` | report 成为唯一 workflow 入口 |
| `generate.lesson_plan` | `legacy/compat_service.py` 过渡，后续迁入 `workflows/lesson_plan/` | 本轮先保兼容，不删除旧能力实现 | 新入口可通过 compat 正常委托 |
| `generate.quiz` | `legacy/compat_service.py` 过渡 | 本轮先保兼容 | 新入口可通过 compat 正常委托 |
| `generate.flashcard` | `legacy/compat_service.py` 过渡 | 本轮先保兼容 | 新入口可通过 compat 正常委托 |
| `generate.ppt_outline` | `legacy/compat_service.py` 过渡 | 本轮先保兼容 | 新入口可通过 compat 正常委托 |
| `research.lookup` | `legacy/compat_service.py` 过渡，后续迁入 `workflows/research/` | 本轮先做 capability gate 和入口托管 | 明确 web 开关、research 结果契约和 SSE 事件 |
| `workflow.continue` | `orchestrator/workflow_resumer.py` | 统一为内部编排语义 | workflow resume / interrupt / fork 测试通过 |

**执行原则：**

- 旧“默认主入口”可以先摘除，但旧“能力实现”不能在未承接前删除。
- `Task 9` 只删除已脱离主链路且已被新入口或 compat 明确承接的旧文件。
- `lesson_plan / quiz / flashcard / ppt_outline / research` 若本轮未迁入新 runtime，必须先通过 compat 维持可用。

## V1/V2 Compatibility Matrix

| 旧契约 | 新契约 | 兼容策略 |
| --- | --- | --- |
| `answer` | `message.content` | v1 响应继续返回 `answer`，由 `response_builder` 从 `message` 投影 |
| `intent_category` | `action.name` + `trace.path` | v1 继续保留，按 `chat / generate_content / research` 映射 |
| `meta.sources` | `sources` | v1 在 `meta` 里保留镜像，v2 放顶层 |
| `meta.workflow/report_state` | `workflow` | compat 层负责旧字段回填 |
| SSE `meta/status/delta/done` | `trace.meta/workflow.status/message.delta/done` | 迁移期同时发旧事件和新事件，前端切换后再移除旧事件 |
| report 特殊字段 | `artifacts[] + workflow` | compat 层保留旧 report 字段映射，直到前端完成切换 |
| `use_rag` | `allow_rag` | normalizer 同时识别两者，`allow_rag` 优先 |
| 无 `allow_web` | `allow_web` | v1 默认 `false` |

## Feature Flags And Rollback

- `CHAT_USE_NEW_ORCHESTRATOR`: 控制 `/api/chat` 是否走新 orchestrator。
- `CHAT_USE_FAST_RUNTIME`: 控制普通聊天是否直接走新快路径。
- `CHAT_USE_REPORT_WORKFLOW_V2`: 控制报告是否走 `workflows/report/runtime.py`。
- `CHAT_SSE_V2_EVENTS`: 控制是否输出新 SSE 事件协议。
- `CHAT_CAPABILITY_POLICY_ENFORCED`: 控制是否强制执行 `allow_rag / allow_web`。

**Rollback 原则：**

- 任一新链路在验收失败时，可按 feature flag 降回 compat 层。
- 回滚只允许发生在 orchestrator 层，不允许 workflow/runtime 自行选择另一套全局路由。
- 所有 feature flag 默认在测试环境逐个打开，不一次性全开。

## Task 1: 建立 v2 领域契约与测试基线

**Files:**
- Create: `app/chat/domain/actions.py`
- Create: `app/chat/domain/capability_policy.py`
- Create: `app/chat/domain/artifact_ref.py`
- Create: `app/chat/domain/workflow_state.py`
- Create: `app/chat/domain/conversation_snapshot.py`
- Create: `app/chat/domain/route_decision.py`
- Create: `app/chat/domain/contracts.py`
- Create: `tests/chat/test_capability_policy.py`
- Create: `tests/chat/test_contract_models.py`

- [ ] **Step 1: 写能力策略和路由契约的失败测试**

```python
from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.route_decision import RouteDecision


def test_capability_policy_defaults_disable_rag_and_web():
    policy = CapabilityPolicy()
    assert policy.allow_rag is False
    assert policy.allow_web is False
    assert policy.allow_tools is False


def test_route_decision_for_fast_chat():
    decision = RouteDecision.fast(action="chat.reply", reason="default_chat")
    assert decision.path == "fast"
    assert decision.action == "chat.reply"
    assert decision.workflow_name is None
```

- [ ] **Step 2: 运行测试，确认当前实现缺失**

Run: `pytest tests/chat/test_capability_policy.py -q`  
Expected: FAIL with `ModuleNotFoundError` or missing symbol errors

- [ ] **Step 3: 实现最小领域对象**

```python
# app/chat/domain/capability_policy.py
from pydantic import BaseModel, Field


class CapabilityPolicy(BaseModel):
    allow_rag: bool = False
    allow_web: bool = False
    allow_tools: bool = False
    selected_doc_ids: list[str] = Field(default_factory=list)
    max_tool_steps: int = 0
```

```python
# app/chat/domain/route_decision.py
from pydantic import BaseModel
from typing import Literal, Optional


class RouteDecision(BaseModel):
    path: Literal["fast", "workflow"]
    action: str
    workflow_name: Optional[str] = None
    reason: str

    @classmethod
    def fast(cls, *, action: str, reason: str) -> "RouteDecision":
        return cls(path="fast", action=action, reason=reason)
```

- [ ] **Step 4: 补齐 `ChatRequestV2`, `ChatResult`, `WorkflowState`, `ArtifactRef`, `ConversationSnapshot`**

```python
# app/chat/domain/contracts.py
from pydantic import BaseModel, Field
from .capability_policy import CapabilityPolicy


class MessagePayload(BaseModel):
    role: str
    content: str


class WorkflowPayload(BaseModel):
    type: str
    status: str
    stage: str | None = None


class ArtifactPayload(BaseModel):
    artifact_id: str
    artifact_type: str
    title: str | None = None
    content: str | None = None


class SseEvent(BaseModel):
    event: str
    data: dict | str


class ChatRequestV2(BaseModel):
    question: str
    conversation_id: str | None = None
    owner: str | None = None
    model_id: str | None = None
    course_id: str | None = None
    artifact_id: str | None = None
    action_hint: str | None = None
    capability: CapabilityPolicy = Field(default_factory=CapabilityPolicy)
```

- [ ] **Step 5: 重新运行测试并记录 checkpoint**

Run: `pytest tests/chat/test_capability_policy.py tests/chat/test_contract_models.py -q`  
Expected: PASS  
Checkpoint: 在计划文件尾部追加 `Task 1 complete`、记录新增文件列表

## Task 2: 建立请求规范化与 v2 schema 桥接

**Files:**
- Create: `app/chat/application/request_normalizer.py`
- Modify: `app/chat/schemas.py`
- Create: `tests/chat/test_request_normalizer.py`

- [ ] **Step 1: 写请求规范化失败测试**

```python
from app.chat.application.request_normalizer import normalize_chat_request
from types import SimpleNamespace


def test_normalize_v1_request_maps_to_v2_defaults():
    payload = SimpleNamespace(
        question="你好",
        conversation_id=None,
        model_id=None,
        owner="teacher-a",
        course_id="course-1",
        artifact_id=None,
        use_rag=None,
        allow_rag=False,
        allow_web=False,
        action_hint=None,
        selected_doc_ids=None,
    )
    result = normalize_chat_request(payload)
    assert result.question == "你好"
    assert result.capability.allow_rag is False
    assert result.capability.allow_web is False
    assert result.action_hint is None
```

- [ ] **Step 2: 运行失败测试**

Run: `pytest tests/chat/test_request_normalizer.py::test_normalize_v1_request_maps_to_v2_defaults -q`  
Expected: FAIL with import or attribute errors

- [ ] **Step 3: 实现规范化器与新 schema**

```python
# app/chat/application/request_normalizer.py
from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.capability_policy import CapabilityPolicy


def normalize_chat_request(payload) -> ChatRequestV2:
    allow_rag = getattr(payload, "allow_rag", None)
    if allow_rag is None:
        allow_rag = bool(getattr(payload, "use_rag", False))
    return ChatRequestV2(
        question=payload.question,
        conversation_id=getattr(payload, "conversation_id", None),
        model_id=getattr(payload, "model_id", None),
        action_hint=getattr(payload, "action_hint", None),
        capability=CapabilityPolicy(
            allow_rag=bool(allow_rag),
            allow_web=bool(getattr(payload, "allow_web", False)),
            allow_tools=bool(allow_rag or getattr(payload, "allow_web", False)),
            selected_doc_ids=list(getattr(payload, "selected_doc_ids", None) or []),
        ),
    )
```

```python
# app/chat/schemas.py
class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    model_id: Optional[str] = None
    owner: Optional[str] = None
    artifact_id: Optional[str] = None
    allow_rag: bool = False
    allow_web: bool = False
    action_hint: Optional[str] = None
    selected_doc_ids: List[str] = Field(default_factory=list)
    course_id: Optional[str] = None
```

- [ ] **Step 4: 增加 v2 响应骨架**

```python
class ChatResponseV2(BaseModel):
    message: Dict[str, Any]
    conversation: Dict[str, Any]
    action: Dict[str, Any]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    workflow: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    trace: Dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 5: 运行规范化测试并记录 checkpoint**

Run: `pytest tests/chat/test_request_normalizer.py -q`  
Expected: PASS  
Checkpoint: 记录 `schemas.py`, `request_normalizer.py`

## Task 3: 实现主编排器与规则路由

**Files:**
- Create: `app/chat/orchestrator/main_orchestrator.py`
- Create: `app/chat/orchestrator/route_rules.py`
- Create: `app/chat/orchestrator/route_fallback_model.py`
- Create: `app/chat/orchestrator/context_builder.py`
- Create: `app/chat/orchestrator/workflow_resumer.py`
- Create: `app/chat/orchestrator/workflow_interrupts.py`
- Create: `tests/chat/test_route_rules.py`

- [ ] **Step 1: 写路由规则测试**

```python
from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.orchestrator.route_rules import decide_route


def test_plain_chat_uses_fast_path():
    request = ChatRequestV2(question="帮我解释牛顿第二定律")
    decision = decide_route(request=request, snapshot=None, workflow_state=None)
    assert decision.path == "fast"
    assert decision.action == "chat.reply"


def test_report_command_uses_workflow_path():
    request = ChatRequestV2(question="根据以上内容生成报告", action_hint="generate.report")
    decision = decide_route(request=request, snapshot=None, workflow_state=None)
    assert decision.path == "workflow"
    assert decision.workflow_name == "report"


def test_active_artifact_rewrite_stays_in_fast_path():
    snapshot = SimpleNamespace(active_artifact={"artifact_id": "a1", "artifact_type": "report"})
    request = ChatRequestV2(question="再正式一点")
    decision = decide_route(request=request, snapshot=snapshot, workflow_state=None)
    assert decision.path == "fast"
    assert decision.action == "chat.rewrite"


def test_research_action_prefers_workflow_path():
    request = ChatRequestV2(question="帮我查一下最新课程标准", action_hint="research.lookup")
    decision = decide_route(request=request, snapshot=None, workflow_state=None)
    assert decision.path == "workflow"
    assert decision.workflow_name == "research"
```

- [ ] **Step 2: 运行路由测试，确认失败**

Run: `pytest tests/chat/test_route_rules.py -q`  
Expected: FAIL with missing `decide_route`

- [ ] **Step 3: 实现打断规则和显式动作优先级**

```python
# app/chat/orchestrator/workflow_interrupts.py
INTERRUPT_KEYWORDS = ("算了", "别继续", "重新开始", "先帮我", "顺便查一下")


def should_interrupt_workflow(text: str) -> bool:
    normalized = str(text or "").strip()
    return any(keyword in normalized for keyword in INTERRUPT_KEYWORDS)
```

```python
# app/chat/orchestrator/route_rules.py
from app.chat.domain.route_decision import RouteDecision
from app.chat.orchestrator.workflow_interrupts import should_interrupt_workflow


def decide_route(*, request, snapshot, workflow_state):
    if snapshot and getattr(snapshot, "active_artifact", None) and request.question in {"再正式一点", "缩短一点", "换个说法", "加上案例"}:
        return RouteDecision.fast(action="chat.rewrite", reason="active_artifact_rewrite")
    if workflow_state and not should_interrupt_workflow(request.question) and not request.action_hint:
        return RouteDecision(path="workflow", action=workflow_state.workflow_type, workflow_name=workflow_state.workflow_type, reason="resume_workflow")
    if request.action_hint == "research.lookup":
        return RouteDecision(path="workflow", action="research.lookup", workflow_name="research", reason="explicit_research")
    if request.action_hint == "generate.report" or "报告" in request.question:
        return RouteDecision(path="workflow", action="generate.report", workflow_name="report", reason="explicit_report")
    if request.action_hint == "chat.rewrite":
        return RouteDecision.fast(action="chat.rewrite", reason="explicit_rewrite")
    return RouteDecision.fast(action="chat.reply", reason="default_fast_path")
```

- [ ] **Step 4: 实现最小 orchestrator**

```python
# app/chat/orchestrator/main_orchestrator.py
class MainOrchestrator:
    def __init__(self, *, fast_runtime, workflow_registry, context_builder):
        self.fast_runtime = fast_runtime
        self.workflow_registry = workflow_registry
        self.context_builder = context_builder

    def dispatch(self, request):
        snapshot = self.context_builder.build(request)
        decision = decide_route(request=request, snapshot=snapshot, workflow_state=snapshot.workflow_state)
        if decision.path == "fast":
            return self.fast_runtime.run(request=request, snapshot=snapshot, decision=decision)
        workflow = self.workflow_registry[decision.workflow_name]
        return workflow.run(request=request, snapshot=snapshot, decision=decision)
```

- [ ] **Step 4.1: 把 `route_fallback_model.py` 接入明确兜底条件**

```python
# app/chat/orchestrator/route_fallback_model.py
def fallback_route(*, question: str, active_task: str | None, active_artifact_type: str | None) -> dict:
    """
    仅在以下条件同时满足时调用：
    1. 无显式 action_hint
    2. 无 pending workflow
    3. 强规则未命中
    4. 输入长度 >= 12 且存在多义性
    输出仅允许: action, confidence, reason
    """
    ...
```

- [ ] **Step 5: 运行路由测试并记录 checkpoint**

Run: `pytest tests/chat/test_route_rules.py -q`  
Expected: PASS  
Checkpoint: 记录 orchestrator 目录新增文件

## Task 4: 实现 fast path 运行时

**Files:**
- Create: `app/chat/runtime/fast_chat_runtime.py`
- Create: `app/chat/runtime/model_registry.py`
- Create: `app/chat/runtime/tool_registry.py`
- Create: `tests/chat/test_fast_chat_runtime.py`
- Modify: `app/chat/model_gateway.py`

- [ ] **Step 1: 写 fast runtime 失败测试**

```python
from app.chat.runtime.fast_chat_runtime import FastChatRuntime
from app.chat.domain.contracts import ChatRequestV2


class DummyGateway:
    call_count = 0

    def chat(self, messages, temperature=0.2, max_tokens=1200):
        self.call_count += 1
        return "这是测试回复"


def test_fast_runtime_builds_direct_reply():
    runtime = FastChatRuntime(model_gateway=DummyGateway())
    result = runtime.run(request=ChatRequestV2(question="你好"), snapshot=None, decision=None)
    assert result["message"]["content"] == "这是测试回复"
    assert result["action"]["name"] == "chat.reply"


def test_fast_runtime_uses_recent_context_without_tools():
    gateway = DummyGateway()
    snapshot = SimpleNamespace(
        recent_messages=[{"role": "user", "content": "上节课我们在讲牛顿第二定律"}],
        active_artifact=None,
    )
    runtime = FastChatRuntime(model_gateway=gateway)
    result = runtime.run(request=ChatRequestV2(question="继续讲下去"), snapshot=snapshot, decision=None)
    assert gateway.call_count == 1
    assert result["trace"]["path"] == "fast"
    assert result["sources"] == []
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/chat/test_fast_chat_runtime.py -q`  
Expected: FAIL with missing runtime

- [ ] **Step 3: 实现 fast runtime，不做 planner/classifier/tool 探测**

```python
# app/chat/runtime/fast_chat_runtime.py
class FastChatRuntime:
    def __init__(self, *, model_gateway):
        self.model_gateway = model_gateway

    def run(self, *, request, snapshot, decision):
        messages = [
            {"role": "system", "content": "你是教学对话助手，请提供准确、清晰、可执行的回答。"},
            *list(getattr(snapshot, "recent_messages", []) or []),
            {"role": "user", "content": request.question},
        ]
        answer = self.model_gateway.chat(messages)
        return {
            "message": {"role": "assistant", "content": answer},
            "action": {"name": getattr(decision, "action", "chat.reply")},
            "artifacts": [],
            "workflow": None,
            "sources": [],
            "trace": {"path": "fast"},
        }
```

- [ ] **Step 4: 用 model registry 包装现有 `ChatModelGateway`**

```python
# app/chat/runtime/model_registry.py
from app.chat.model_gateway import ChatModelGateway
from core.config import Config


def build_default_gateway(model_id: str | None = None) -> ChatModelGateway:
    return ChatModelGateway(
        api_base=Config.OPENAI_BASE_URL,
        api_key=Config.OPENAI_API_KEY,
        model_name=model_id or Config.DEFAULT_LLM_MODEL_ID,
    )
```

- [ ] **Step 5: 运行 fast runtime 测试并记录 checkpoint**

Run: `pytest tests/chat/test_fast_chat_runtime.py -q`  
Expected: PASS  
Checkpoint: 记录 `fast_chat_runtime.py`, `model_registry.py`

## Task 5: 构建 application service、v2 路由与 SSE 事件协议

**Files:**
- Create: `app/chat/application/chat_app_service.py`
- Create: `app/chat/application/response_builder.py`
- Modify: `app/chat/routes.py`
- Create: `tests/chat/test_v2_routes.py`

- [ ] **Step 1: 写 v2 路由与 SSE 测试**

```python
def test_chat_route_returns_v2_shape(client):
    response = client.post("/api/chat", json={"question": "你好", "allow_rag": False, "allow_web": False})
    assert response.status_code == 200
    payload = response.json()
    assert "message" in payload
    assert "conversation" in payload
    assert "action" in payload
    assert payload["trace"]["path"] in {"fast", "workflow"}


def test_stream_route_emits_normalized_events(client):
    response = client.get("/api/chat/stream", params={"question": "你好", "token": "stub-token"})
    assert response.status_code == 200
    body = response.text
    assert "event: trace.meta" in body
    assert "event: message.delta" in body
    assert "event: done" in body


def test_v1_compat_route_still_returns_answer_shape(client):
    response = client.post("/api/chat", json={"question": "你好", "use_rag": False})
    assert response.status_code == 200
    payload = response.json()
    assert "answer" in payload
    assert "intent_category" in payload
```

- [ ] **Step 2: 运行路由测试，确认失败**

Run: `pytest tests/chat/test_v2_routes.py -q`  
Expected: FAIL with route payload mismatch

- [ ] **Step 3: 实现 `chat_app_service` 与 response builder**

```python
# app/chat/application/chat_app_service.py
class ChatAppService:
    def __init__(self, *, normalizer, orchestrator, response_builder):
        self.normalizer = normalizer
        self.orchestrator = orchestrator
        self.response_builder = response_builder

    def chat(self, payload):
        request = self.normalizer(payload)
        result = self.orchestrator.dispatch(request)
        return self.response_builder.build_http_response(result)
```

```python
# app/chat/application/response_builder.py
def build_sse_events(result):
    yield {"event": "trace.meta", "data": {"path": result["trace"]["path"]}}
    if result.get("workflow"):
        yield {"event": "workflow.status", "data": result["workflow"]}
    yield {"event": "message.delta", "data": {"delta": result["message"]["content"]}}
    yield {"event": "done", "data": "[DONE]"}
```

- [ ] **Step 4: 在 `routes.py` 切到新服务，但保留 v1/v2 兼容**

```python
# app/chat/routes.py
service = ChatAppService(...)

@router.post("")
async def chat(payload: ChatRequest, current_user: dict = Depends(get_current_user)):
    return service.chat(payload)
```

- [ ] **Step 5: 运行路由测试并记录 checkpoint**

Run: `pytest tests/chat/test_v2_routes.py -q`  
Expected: PASS  
Checkpoint: 记录 `chat_app_service.py`, `response_builder.py`, `routes.py`

## Task 6: 建立报告工作流 runtime 并包裹现有 universal engine

**Files:**
- Create: `app/chat/workflows/report/runtime.py`
- Create: `app/chat/workflows/report/state.py`
- Create: `app/chat/workflows/report/contracts.py`
- Create: `tests/chat/test_report_workflow_runtime.py`
- Modify: `app/chat/agents/universal_report_engine.py`
- Modify: `app/chat/report_domain.py`
- Modify: `app/chat/persistence/artifact_store_adapter.py`

- [ ] **Step 1: 写报告 runtime 失败测试**

```python
from app.chat.workflows.report.runtime import ReportWorkflowRuntime
from app.chat.domain.contracts import ChatRequestV2


class DummyEngine:
    def invoke(self, state):
        return {"reply": "这是报告草稿", "status": "awaiting_confirm"}


def test_report_runtime_wraps_engine_result():
    runtime = ReportWorkflowRuntime(engine=DummyEngine())
    result = runtime.run(request=ChatRequestV2(question="生成报告", action_hint="generate.report"), snapshot=None, decision=None)
    assert result["workflow"]["type"] == "report"
    assert result["workflow"]["status"] == "awaiting_confirm"
    assert result["action"]["name"] == "generate.report"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/chat/test_report_workflow_runtime.py -q`  
Expected: FAIL with missing runtime

- [ ] **Step 3: 实现 runtime 包装层，统一输出 `ChatResult`**

```python
# app/chat/workflows/report/runtime.py
class ReportWorkflowRuntime:
    def __init__(self, *, engine):
        self.engine = engine

    def run(self, *, request, snapshot, decision):
        state = {"user_input": request.question, "report_state": getattr(snapshot, "workflow_state", None)}
        raw = self.engine.invoke(state)
        return {
            "message": {"role": "assistant", "content": raw.get("reply", "")},
            "action": {"name": "generate.report"},
            "artifacts": raw.get("artifacts", []),
            "workflow": {"type": "report", "status": raw.get("status", "running")},
            "sources": raw.get("sources", []),
            "trace": {"path": "workflow", "workflow_name": "report"},
        }
```

- [ ] **Step 4: 统一 workflow state 映射**

```python
# app/chat/workflows/report/state.py
from app.chat.domain.workflow_state import WorkflowState


def from_legacy_report_state(raw_state: dict | None) -> WorkflowState | None:
    if not raw_state:
        return None
    return WorkflowState(
        workflow_id=str(raw_state.get("workflow_id") or raw_state.get("report_id") or ""),
        workflow_type="report",
        status=str(raw_state.get("status") or "running"),
        stage=str(raw_state.get("stage") or raw_state.get("phase") or "collecting"),
        required_slots=list(raw_state.get("required_slots") or []),
        filled_slots=dict(raw_state.get("report_slots") or {}),
        artifacts=list(raw_state.get("artifacts") or []),
        resume_token=str(raw_state.get("resume_token") or ""),
    )
```

- [ ] **Step 4.1: 将 report artifact 写入统一 artifact store**

```python
# app/chat/persistence/artifact_store_adapter.py
class ArtifactStoreAdapter:
    def save(self, *, conversation_id: str, workflow_type: str, artifacts: list[dict]) -> list[dict]:
        # 第一版可以直接写回 conversation state，下轮再抽独立持久化
        ...
```

- [ ] **Step 5: 运行报告工作流测试并记录 checkpoint**

Run: `pytest tests/chat/test_report_workflow_runtime.py -q`  
Expected: PASS  
Checkpoint: 记录 report workflow 新目录

## Task 7: 隔离检索与 web 策略，并实现 capability-aware tool registry

**Files:**
- Create: `app/chat/retrieval/retrieval_policy.py`
- Create: `app/chat/retrieval/retrieval_runtime.py`
- Create: `app/chat/retrieval/web_runtime.py`
- Modify: `app/chat/runtime/tool_registry.py`
- Modify: `app/chat/tools/search_tools.py`
- Create: `tests/chat/test_capability_policy.py`

- [ ] **Step 1: 写能力门控测试**

```python
from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.runtime.tool_registry import build_tool_registry


def test_tool_registry_exposes_no_tools_when_all_capabilities_disabled():
    registry = build_tool_registry(CapabilityPolicy())
    assert registry == {}


def test_tool_registry_exposes_rag_only_when_allow_rag_enabled():
    registry = build_tool_registry(CapabilityPolicy(allow_rag=True, allow_tools=True))
    assert "rag_search" in registry
    assert "deep_research" not in registry
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/chat/test_capability_policy.py -q`  
Expected: FAIL with registry mismatch

- [ ] **Step 3: 实现 retrieval policy 和 tool registry**

```python
# app/chat/retrieval/retrieval_policy.py
def allow_external_retrieval(policy) -> bool:
    return bool(policy.allow_external_retrieval)


def allow_web(policy) -> bool:
    return bool(policy.allow_web)
```

```python
# app/chat/runtime/tool_registry.py
def build_tool_registry(policy, *, rag_factory=None, web_factory=None):
    tools = {}
    if policy.allow_external_retrieval:
        tools["rag_search"] = rag_factory() if rag_factory else object()
    if policy.allow_web:
        tools["deep_research"] = web_factory() if web_factory else object()
    return tools
```

- [ ] **Step 4: 从主链路删除默认工具推断**

```python
# 目标状态
# - routes/service 不再调用 should_use_video_search
# - orchestrator 只读取 request.capability
# - workflow/runtime 在 policy 允许时才拿到 tool registry
```

- [ ] **Step 5: 运行能力门控测试并记录 checkpoint**

Run: `pytest tests/chat/test_capability_policy.py -q`  
Expected: PASS  
Checkpoint: 记录 retrieval/runtime 目录

## Task 8: 统一持久化、memory 预留接口与 legacy compat 收尾

**Files:**
- Create: `app/chat/persistence/conversation_store_adapter.py`
- Create: `app/chat/persistence/artifact_store_adapter.py`
- Create: `app/chat/memory/ports.py`
- Create: `app/chat/legacy/compat_service.py`
- Modify: `app/chat/service.py`
- Modify: `app/chat/routes.py`
- Create: `tests/chat/test_conversation_snapshot.py`

- [ ] **Step 1: 写 conversation snapshot 与 legacy compat 测试**

```python
def test_legacy_service_delegates_to_compat_layer():
    from app.chat.legacy.compat_service import CompatChatService
    service = CompatChatService(delegate=lambda payload: {"answer": "ok", "intent_category": "chat"})
    data = service.chat(question="你好", conversation_id=None, model_id=None, use_rag=False, selected_doc_ids=None, owner="tester", course_id=None)
    assert data["intent_category"] == "chat"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/chat -q`  
Expected: FAIL with missing adapters/compat layer

- [ ] **Step 3: 实现 conversation store adapter 与 memory ports**

```python
# app/chat/persistence/conversation_store_adapter.py
from core.conversation_storage import conversation_storage


class ConversationStoreAdapter:
    def load_snapshot(self, conversation_id: str):
        return {
            "messages": conversation_storage.get_messages(conversation_id, limit=20),
            "state": conversation_storage.get_state(conversation_id),
        }

    def append_message(self, conversation_id: str, role: str, content: str, *, sources=None):
        conversation_storage.append_message(conversation_id, role, content, sources=sources)

    def update_workflow_state(self, conversation_id: str, workflow_state: dict):
        conversation_storage.update_state(conversation_id, {"workflow_state": workflow_state})
```

```python
# app/chat/memory/ports.py
from typing import Protocol


class MemoryReader(Protocol):
    def read(self, *, user_id: str, conversation_id: str | None): ...


class MemoryWriter(Protocol):
    def write(self, *, user_id: str, conversation_id: str, result: dict): ...
```

- [ ] **Step 3.1: 在 orchestrator 与 response 阶段接入 memory 调用点验收**

```python
# 目标行为
# - context_builder.build() 读取 MemoryReader
# - response_builder.build_http_response() 或 workflow 完成后调用 MemoryWriter
# - ConversationSummarizer 暂可为空实现，但调用点必须存在且有测试保护
```

- [ ] **Step 4: 将旧 `service.py` 缩为 compat 委托层**

```python
# app/chat/service.py
from app.chat.legacy.compat_service import CompatChatService

service = CompatChatService()
```

- [ ] **Step 5: 运行全量 chat 测试并记录 checkpoint**

Run: `pytest tests/chat -q`  
Expected: PASS  
Checkpoint: 记录最终保留/删除清单；标记 `intent_router.py`, `response_planner.py`, `graph_state.py` 进入删除阶段

## Task 9: 删除旧主入口并完成迁移验收

**Files:**
- Modify: `app/chat/routes.py`
- Delete: `app/chat/agents/supervisor_agent.py`
- Delete: `app/chat/agents/router_agent.py`
- Delete: `app/chat/agents/chat_agent.py`
- Delete: `app/chat/agents/research_agent.py`
- Delete: `app/chat/intent_router.py`
- Delete: `app/chat/resource_type_router.py`
- Delete: `app/chat/response_planner.py`
- Delete: `app/chat/graph_state.py`

- [ ] **Step 1: 写主链路验收清单**

```text
1. 普通聊天仅调用 fast runtime
2. chat.rewrite 能在 active artifact 上工作
3. generate.report 进入 report workflow
4. lesson_plan/quiz/flashcard/ppt_outline/research 若未迁移，则必须通过 compat 可用
5. allow_rag=false 时不暴露检索
6. allow_web=false 时不暴露 web
7. workflow resume / interrupt / fork 行为可验证
8. SSE 统一输出 message.delta / workflow.status / done
```

- [ ] **Step 2: 运行全量验收测试**

Run: `pytest tests/chat -q`  
Expected: PASS

- [ ] **Step 3: 删除旧文件并修复导入**

```text
先从 routes.py、service.py、__init__.py 中移除旧“默认主入口”引用；
先摘主入口，再观察 legacy 能力实现是否仍被 compat 直接委托；
删除旧文件前，先执行 `rg "supervisor_agent|intent_router|response_planner|graph_state|research_agent|chat_agent" app/chat`
只有在能力迁移矩阵中的承接项全部满足前置条件时，才删除对应旧文件。
```

- [ ] **Step 4: 运行回归测试**

Run: `pytest tests/chat -q`  
Expected: PASS

- [ ] **Step 5: 记录最终 checkpoint**

Run: `Get-ChildItem app/chat -Recurse -File | Select-Object FullName`  
Expected: 输出新的目录结构，且不再包含旧主入口壳层文件

## Self-Review

### Spec Coverage

- 快路径：Task 3 + Task 4 + Task 5
- workflow-first：Task 3 + Task 6
- `RAG/web` 默认关闭、前端显式控制：Task 1 + Task 2 + Task 7
- report workflow 单一入口收敛：Task 6 + Task 9
- memory 预留：Task 8
- API 契约与 SSE 统一：Task 2 + Task 5
- 旧主入口退役：Task 8 + Task 9
- 能力迁移矩阵：计划头部矩阵 + Task 9 删除前置条件
- v1/v2 兼容矩阵：计划头部矩阵 + Task 5 compat 测试
- rollback：计划头部 feature flags + compat 委托

### Placeholder Scan

- 未使用任何占位符文本
- 每个任务都包含目标文件、命令和预期结果
- 删除步骤在最终任务中显式列出

### Type Consistency

- 请求对象统一为 `ChatRequestV2`
- 路由结果统一为 `RouteDecision`
- 工作流状态统一为 `WorkflowState`
- 运行时输出统一为 `ChatResult`、`MessagePayload`、`WorkflowPayload`、`ArtifactPayload`
