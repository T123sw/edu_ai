# Phase 1 具体任务清单（基础设施重构）

> 依据文档：`PLAN.md` + `TASKS.md`  
> 输出目标：形成可直接进入开发执行的 Phase 1 任务分解、依赖顺序与验收标准

---

## 1. Phase 1 目标边界

Phase 1 只做“基础设施重构”，核心目标是为后续统一文本引擎、搜索增强、记忆与多模态能力打地基。

### 必须达成的结果

1. `generate` 请求支持**两步路由**（一级 `intent` + 二级 `resource_type`）。
2. 槽位从 report 专用转为**统一槽位体系**（覆盖 8 类资源）。
3. `GraphState` 完成**泛化重构**并处理旧状态兼容。
4. 主图路由稳定分发到 `chat/research/text_generate/multimodal`。
5. `service_core.py` 与 `service.py` 合并，消除双入口。

### 本阶段不做

- 不实现插件化文本统一引擎（Phase 2）
- 不做搜索降级链与上下文增强（Phase 3）
- 不做记忆系统（Phase 4）
- 不做多模态具体引擎实现（Phase 5）

---

## 2. Phase 1 任务总览（执行顺序）

- [ ] P1-01 新增二级路由器 `resource_type_router.py`
- [ ] P1-02 新增统一槽位定义 `slot_definitions.py`
- [ ] P1-03 重构 `graph_state.py`
- [ ] P1-04 重构 supervisor 与主图条件路由
- [ ] P1-05 合并并废弃 `service_core.py`
- [ ] P1-06 Phase 1 集成验证与回归检查

---

## 3. 详细任务拆解

## P1-01 新增二级路由器 `resource_type_router.py`

**目标**：在一级意图为 `generate` 时，准确识别资源类型。

**文件**：
- `app/chat/resource_type_router.py`（新增）

**实现清单**：
- [ ] 定义合法类型常量 `RESOURCE_TYPES`：
  - `report`, `lesson_plan`, `quiz`, `flashcard`, `blog`, `ppt`, `video`, `podcast`
- [ ] 定义 `RESOURCE_TYPE_ROUTER_PROMPT`：
  - 强约束输出 JSON：`{"resource_type": "..."}`
  - 限制输出必须是合法枚举
- [ ] 定义 `RESOURCE_TYPE_KEYWORDS` 兜底映射：
  - 中英关键词覆盖每类资源
  - 含常见近义词（如：课件/幻灯片 => ppt）
- [ ] 实现 `classify(question: str) -> str`：
  - 先走 LLM 分类
  - LLM 异常/JSON 解析失败/非法值时走关键词匹配
  - 无命中返回默认值（建议 `report`，并打印 fallback 来源）
- [ ] 增加轻量日志：记录分类来源 `llm | keyword | fallback`

**验收标准**：
- [ ] 8 类典型输入均能正确识别
- [ ] LLM 不可用时仍返回可用类型
- [ ] 返回值始终在 `RESOURCE_TYPES` 内

**风险**：
- `ppt/video/podcast` 与文本类型语义重叠导致误判

---

## P1-02 新增统一槽位定义 `slot_definitions.py`

**目标**：建立“资源类型 -> 槽位模型”的统一契约。

**文件**：
- `app/chat/slot_definitions.py`（新增）

**实现清单**：
- [ ] 定义 `BaseSlots(BaseModel)`：
  - `topic`, `audience`, `objective`
- [ ] 定义 8 类扩展槽位模型：
  - [ ] `ReportSlots`
  - [ ] `LessonPlanSlots`
  - [ ] `QuizSlots`
  - [ ] `FlashcardSlots`
  - [ ] `BlogSlots`
  - [ ] `PPTSlots`
  - [ ] `VideoSlots`
  - [ ] `PodcastSlots`
- [ ] 每类定义 `SlotMeta`：
  - [ ] `core_slots`（必须收集）
  - [ ] `secondary_slots`（可批量询问/可默认）
  - [ ] `defaults`（缺省值）
- [ ] 定义 `SLOT_REGISTRY: dict[str, SlotClass]`

**验收标准**：
- [ ] 8 类资源都能通过 `SLOT_REGISTRY[resource_type]` 查到模型
- [ ] 核心槽位与次要槽位边界清晰
- [ ] 字段命名与 `PLAN.md` 保持一致

**风险**：
- 命名不一致导致后续引擎读取失败

---

## P1-03 重构 `graph_state.py`

**目标**：将当前重字段状态升级为可扩展统一状态结构。

**文件**：
- `app/chat/graph_state.py`（重构）

**实现清单**：
- [ ] 清理重复字段（特别是 `need_type`, `user_role_mode`）
- [ ] 新增路由字段：
  - [ ] `resource_type`
  - [ ] `response_type`（扩展包含 `text_generate`、`multimodal_generate`）
- [ ] 新增槽位字段：
  - [ ] `slots`
  - [ ] `slot_meta`
  - [ ] `missing_slots`
  - [ ] `slot_collection_phase`
- [ ] 新增生成过程字段：
  - [ ] `outline`
  - [ ] `outline_confirmed`
  - [ ] `generated_content`
  - [ ] `generation_checkpoint`
- [ ] 新增上下文字段：
  - [ ] `search_context_hint`
  - [ ] `memory_context`
- [ ] 保持既有关键字段不破坏（会话/消息/工具上下文）
- [ ] 增加旧状态兼容处理（字段缺失容忍/默认值）

**验收标准**：
- [ ] 新旧会话读取不崩溃
- [ ] 主图路由字段可被 supervisor 正确读写
- [ ] 重复字段问题消失

**风险**：
- 历史会话反序列化失败

---

## P1-04 重构 supervisor 与主图路由

**目标**：让主图完成“先判意图、再判资源类型”的两步路由。

**文件**：
- `app/chat/agents/supervisor_agent.py`
- `app/chat/service.py`

**实现清单**：
- [ ] 保持一级路由不变：`chat / generate / research`
- [ ] `intent == generate` 时调用 `resource_type_router.classify()`
- [ ] 写入状态：
  - [ ] `state["resource_type"]`
  - [ ] `state["response_type"]`
- [ ] 更新 `_route_after_supervisor(state)`：
  - [ ] `chat -> chat_agent`
  - [ ] `research -> research_agent`
  - [ ] 文本生成类型（report/lesson_plan/quiz/flashcard/blog）-> `text_gen_engine`
  - [ ] `ppt -> ppt_engine`
  - [ ] `video -> video_engine`
  - [ ] `podcast -> podcast_engine`
- [ ] 添加兜底：任何异常回退 `chat`

**验收标准**：
- [ ] 8 类生成输入均能路由到正确引擎
- [ ] chat/research 行为无回归
- [ ] 路由异常不导致主流程中断

**风险**：
- 路由返回值与图节点名不一致

---

## P1-05 合并并废弃 `service_core.py`

**目标**：统一服务入口，去除重复实现与维护负担。

**文件**：
- `app/chat/service_core.py`
- `app/chat/service.py`
- 全局 import 引用点

**实现清单**：
- [ ] 对比 `service_core.py` 与 `service.py`：梳理独有逻辑
- [ ] 将必要逻辑迁移到 `service.py`
- [ ] 全局清理 `service_core` 引用
- [ ] 删除或标记废弃 `service_core.py`（按仓库策略）

**验收标准**：
- [ ] 项目运行不再依赖 `service_core.py`
- [ ] 接口行为与重构前一致

**风险**：
- 隐式引用遗漏导致运行时报错

---

## P1-06 集成验证与回归检查

**目标**：确保 Phase 1 重构可稳定作为后续开发基线。

**验证清单**：
- [ ] 路由覆盖：`chat/research/generate-8types`
- [ ] 状态覆盖：关键节点检查 `resource_type/response_type/slots` 等字段
- [ ] 兼容覆盖：旧会话状态读取验证
- [ ] 异常覆盖：
  - [ ] LLM 路由失败
  - [ ] JSON 非法
  - [ ] 关键词无命中
  - [ ] 非法 `resource_type`
- [ ] 冒烟测试通过并输出简要记录

**验收标准**：
- [ ] 主流程可稳定运行
- [ ] 不阻塞 Phase 2 开始

---

## 4. 依赖关系

- `P1-01` 与 `P1-02`：可并行
- `P1-03`：依赖 `P1-02`
- `P1-04`：依赖 `P1-01` + `P1-03`
- `P1-05`：依赖 `P1-04`
- `P1-06`：依赖 `P1-01`~`P1-05`

---

## 5. 建议执行节奏（按迭代）

### 迭代 A（路由与槽位基础）
- 完成 `P1-01` + `P1-02`

### 迭代 B（状态与主图）
- 完成 `P1-03` + `P1-04`

### 迭代 C（服务收敛与验证）
- 完成 `P1-05` + `P1-06`

---

## 6. Phase 1 完成定义（DoD）

满足以下条件即判定 Phase 1 完成：

- [ ] 两步路由已接入并稳定工作
- [ ] 统一槽位定义已建立并可被主流程读取
- [ ] GraphState 泛化重构完成且通过兼容验证
- [ ] supervisor 路由分发正确
- [ ] `service_core.py` 不再是运行入口
- [ ] 至少完成一轮端到端冒烟验证

---

## 7. 后续执行建议

建议从 `P1-01` 开始逐项实现，每完成一项立即进行最小可验证检查，再进入下一项，以降低主图重构风险。