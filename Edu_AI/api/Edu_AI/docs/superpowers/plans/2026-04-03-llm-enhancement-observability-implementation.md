# LLM Enhancement Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 LLM enhancement 增加默认关闭的可观察性 trace，能看到规则 patch、LLM 候选、guard 接受结果，并同时支持结果 trace 与会话 state 排查。

**Architecture:** 在 `ExtractionGuard` 和 `LLMEnhancementRouter` 之间增加结构化 observation 汇总，不改变默认规则主路径。由 `ConversationStoreAdapter` 与 `RouteChatService` 在 trace 开启时把 observation 挂到 `result.trace.llm_enhancement`，并写入最近一次会话 state。

**Tech Stack:** Python, pytest, existing chat orchestration layer, feature flags

---

### Task 1: 固定 observation 行为测试

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_extraction_guard.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_llm_enhancement_router.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_route_feature_flags.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_route_service_factory.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_route_chat_service.py`

- [ ] **Step 1: 写 failing tests**
- [ ] **Step 2: 跑 focused tests，确认 observation 相关断言先失败**
- [ ] **Step 3: 实现 observation 汇总与 trace 开关**
- [ ] **Step 4: 回跑 focused tests，确认通过**

### Task 2: 把 observation 接到 state 与 result trace

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\extraction_guard.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\llm_enhancement_router.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\persistence\conversation_store_adapter.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\route_chat_service.py`

- [ ] **Step 1: 增加 guard report / router observation**
- [ ] **Step 2: 在 adapter 中返回 patch + observation**
- [ ] **Step 3: trace 开启时写入 `result.trace.llm_enhancement` 与 state 最近一次 observation**
- [ ] **Step 4: 保持默认关闭时无行为变化**

### Task 3: 增加 feature flag wiring

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\route_feature_flags.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\route_service_factory.py`

- [ ] **Step 1: 新增 `CHAT_TRACE_LLM_ENHANCEMENT`**
- [ ] **Step 2: 默认 factory 把 trace 开关传给 route service / adapter**
- [ ] **Step 3: 验证默认关闭、显式开启两种路径**

### Task 4: 验证

**Files:**
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat`

- [ ] **Step 1: 跑 focused tests**
- [ ] **Step 2: 跑 route / memory 相关 regression**
- [ ] **Step 3: 跑完整 `tests/chat` regression**
