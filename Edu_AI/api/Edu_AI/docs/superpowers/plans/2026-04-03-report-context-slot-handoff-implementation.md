# Report Context Slot Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让报告生成 workflow 真正消费对话上下文，把 `gathered_context` 先整理成 report 语义输入与槽位候选，自动填充已有信息，只追问关键缺失槽位，再进入大纲生成阶段。

**Architecture:** 在 `ReportAssembler` 中增加 report 专属的上下文整理结果，例如 `slot_hints` 与 `context_digest`；在 `universal_report_engine` 的 extractor 阶段先用这些整理结果预填 `report_slots`，再用 extractor LLM 做补充抽取。evaluator 保持原有状态机，但只会对仍然缺失的关键槽位继续追问。

**Tech Stack:** Python, pytest, existing ReportWorkflowRuntime, GenerationContextBuilder, Universal Report Engine v2

---

### Task 1: 固定 report 承接与自动填槽测试

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_assembler.py`
- Add: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_universal_report_engine_context_slots.py`

- [ ] **Step 1: 增加 assembler 测试，验证 `gathered_context` 中包含 `slot_hints` 与 `context_digest`**
- [ ] **Step 2: 增加 engine 节点测试，验证 `extractor_node` 会先用 `slot_hints` 预填 `report_slots`**
- [ ] **Step 3: 增加 evaluator 测试，验证关键槽位已由上下文填上时不会进入 `asking(core_topic)`**
- [ ] **Step 4: 运行 focused tests，确认先失败**

### Task 2: 实现 report 专属上下文整理

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\report\assembler.py`

- [ ] **Step 1: 增加 report 专属 `slot_hints` 生成逻辑**
- [ ] **Step 2: 增加 `context_digest`，把 summary/topics/issues/facts/evidence 压成 extractor 可读上下文**
- [ ] **Step 3: 保持现有 `gathered_context` 字段兼容，不破坏 runtime/tests**

### Task 3: 实现 engine 上下文预填槽位

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\agents\universal_report_engine.py`

- [ ] **Step 1: 增加 `gathered_context -> report_slots` 的预填辅助函数**
- [ ] **Step 2: 在 `extractor_node` 中先合并上下文预填，再执行 extractor LLM 抽取**
- [ ] **Step 3: 扩展 extractor prompt，让 LLM 能看到 `context_digest` 与 `slot_hints`**
- [ ] **Step 4: 保持 evaluator/asker 状态机不变，只让它处理真正缺失的关键槽位**

### Task 4: 验证

**Files:**
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat`

- [ ] **Step 1: 跑 focused tests**
- [ ] **Step 2: 跑 report 相关 regression**
- [ ] **Step 3: 跑完整 `tests/chat` regression**
