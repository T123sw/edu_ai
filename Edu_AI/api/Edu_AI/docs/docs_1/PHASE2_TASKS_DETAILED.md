# Phase 2 具体任务清单（文本统一引擎）

> 依据文档：`docs/PLAN.md` + `docs/TASKS.md`  
> 目标：将 Phase 2 拆解为可直接执行的任务序列，为 Phase 3/5 提供稳定生成底座

---

## 1. Phase 2 目标边界

Phase 2 只聚焦**文本统一生成引擎**，不进入搜索增强（Phase 3）、记忆系统（Phase 4）和多模态具体引擎（Phase 5）。

### 必须达成的结果

1. 建立统一插件协议 `GenPlugin`，支持多资源类型扩展。
2. 建立 `TextGenEngine` 子图（slot_collector → planner → validator → executor → analyzer）。
3. 完成 5 类文本资源插件：`report / lesson_plan / quiz / flashcard / blog`。
4. 完成统一槽位收集器 `SlotCollector`（核心单问 + 次要批问 + 不耐烦默认填充）。
5. 主图中文本生成类型切换到 `text_gen_engine`（最少灰度切换，支持回退）。

### 本阶段不做

- 不实现 `ppt/video/podcast` 引擎（Phase 5）。
- 不实现搜索降级链与上下文提示增强（Phase 3）。
- 不实现长期记忆注入（Phase 4）。

---

## 2. Phase 2 任务总览（执行顺序）

- [ ] P2-01 抽取插件基类 `plugin_base.py`
- [ ] P2-02 构建 `TextGenEngine` 子图骨架
- [ ] P2-03 实现 `ReportPlugin`（迁移现有报告能力）
- [ ] P2-04 实现 `LessonPlanPlugin`
- [ ] P2-05 实现 `QuizPlugin`
- [ ] P2-06 实现 `FlashcardPlugin`
- [ ] P2-07 实现 `BlogPlugin`（迁移 blog_agent 逻辑）
- [ ] P2-08 实现统一 `SlotCollector`
- [ ] P2-09 接入主图路由与灰度开关
- [ ] P2-10 集成验证与回归检查

---

## 3. 详细任务拆解

## P2-01 抽取插件基类 `plugin_base.py`

**目标**：定义统一插件契约，约束所有文本资源实现。

**文件**：
- `app/chat/engines/plugin_base.py`（新增）

**实现清单**：
- [ ] 定义 `GenPlugin(ABC)` 抽象类。
- [ ] 抽象属性：
  - [ ] `resource_type: str`
  - [ ] `slot_class: type[BaseModel]`
- [ ] 抽象方法：
  - [ ] `needs_outline_review() -> bool`
  - [ ] `build_outline(slots, context) -> list[dict]`
  - [ ] `generate_content(slots, outline, context) -> str`
- [ ] 可选方法：
  - [ ] `post_process(content: str) -> str`（默认透传）

**验收标准**：
- [ ] 插件类可静态检查通过。
- [ ] 任一插件必须实现抽象接口，否则实例化失败。

---

## P2-02 构建 `TextGenEngine` 子图骨架

**目标**：把报告专用流程泛化为文本统一引擎。

**文件**：
- `app/chat/engines/text_gen_engine.py`（新增）
- `app/chat/engines/__init__.py`（新增/更新）

**实现清单**：
- [ ] 定义 `TextGenState`（复用/映射 GraphState 必要字段）。
- [ ] 建立节点：
  - [ ] `slot_collector`
  - [ ] `planner`
  - [ ] `validator`
  - [ ] `executor`
  - [ ] `analyzer`
- [ ] 建立状态流转：
  - [ ] `collecting -> planning -> executing -> reviewing`
  - [ ] `reviewing -> finished | replanning | awaiting_human`
- [ ] 实现 `PLUGIN_REGISTRY` 动态分发。
- [ ] 增加异常降级：节点异常时返回 `ask` 或安全失败信息，不中断主图。

**验收标准**：
- [ ] 子图可独立编译。
- [ ] 在无具体插件执行时，返回可解释错误（非崩溃）。

---

## P2-03 实现 `ReportPlugin`

**目标**：迁移并保真现有报告能力，作为首个生产级插件。

**文件**：
- `app/chat/engines/plugins/report_plugin.py`（新增）
- `app/chat/engines/plugins/__init__.py`（新增/更新）

**实现清单**：
- [ ] 迁移当前 `report_agent` 的大纲构建与正文生成核心逻辑。
- [ ] `needs_outline_review() -> True`。
- [ ] 支持 `outline` 用户确认与局部修改。
- [ ] 输出 Markdown 长文。
- [ ] 与现有 `report_slots`/默认值体系兼容。

**验收标准**：
- [ ] 与当前 report 主流程输出行为等价（核心字段/状态一致）。
- [ ] 回归脚本通过（报告场景）。

**风险**：
- 报告回归是高风险，必须先通过对照测试再切主路由。

---

## P2-04 实现 `LessonPlanPlugin`

**目标**：提供教案生成标准流程。

**文件**：
- `app/chat/engines/plugins/lesson_plan_plugin.py`（新增）

**实现清单**：
- [ ] `needs_outline_review() -> True`。
- [ ] 依据 `LessonPlanSlots` 构建教案框架。
- [ ] 章节至少包含：教学目标/导入/新授/练习/小结。
- [ ] 输出结构化 Markdown。

**验收标准**：
- [ ] 输入“教案”类请求可进入该插件。
- [ ] 输出结构稳定，字段齐全。

---

## P2-05 实现 `QuizPlugin`

**目标**：提供习题批量生成能力。

**文件**：
- `app/chat/engines/plugins/quiz_plugin.py`（新增）

**实现清单**：
- [ ] `needs_outline_review() -> False`。
- [ ] 基于 `QuizSlots` 生成指定数量题目。
- [ ] 题型支持混合（选择/填空/简答等）。
- [ ] 输出 `JSON + Markdown`（题目 + 答案 + 解析）。

**验收标准**：
- [ ] 最少覆盖基础/中等/进阶难度。
- [ ] 数量与题型控制有效。

---

## P2-06 实现 `FlashcardPlugin`

**目标**：提供闪卡生成能力。

**文件**：
- `app/chat/engines/plugins/flashcard_plugin.py`（新增）

**实现清单**：
- [ ] `needs_outline_review() -> False`。
- [ ] 基于 `FlashcardSlots` 批量生成卡片。
- [ ] 输出结构统一：`[{front, back}]`。

**验收标准**：
- [ ] 卡片数符合槽位约束。
- [ ] 可直接被前端消费（JSON 格式稳定）。

---

## P2-07 实现 `BlogPlugin`

**目标**：将独立博客生成能力纳入统一引擎。

**文件**：
- `app/chat/engines/plugins/blog_plugin.py`（新增）
- `app/chat/blog_agent/*`（读取迁移来源，先不删除）

**实现清单**：
- [ ] `needs_outline_review() -> True`。
- [ ] 迁移 `blog_agent` 的大纲与段落生成逻辑。
- [ ] 保留两阶段 HITL 能力（章节审查 + 大纲审查）。
- [ ] 输出 Markdown 文章。

**验收标准**：
- [ ] 博客场景可在 `text_gen_engine` 正常执行。
- [ ] 输出质量与旧 blog_agent 基本一致。

---

## P2-08 实现统一 `SlotCollector`

**目标**：实现跨资源类型一致的槽位追问策略。

**文件**：
- `app/chat/engines/slot_collector.py`（新增）

**实现清单**：
- [ ] 实现 `get_next_question(resource_type, current_slots)`。
- [ ] 核心槽位：单轮单槽位追问（`mode=single`）。
- [ ] 次要槽位：批量追问 2-3 个（`mode=batch`）。
- [ ] 支持可跳过并使用默认值（`can_skip=True`）。
- [ ] 实现 `check_impatient()`：命中关键词时自动填充默认值。
- [ ] 统一追问话术模板（至少覆盖 report/lesson_plan/quiz）。

**验收标准**：
- [ ] 8 类资源槽位策略可由注册表驱动。
- [ ] 不耐烦输入可快速推进到生成阶段。

---

## P2-09 接入主图路由与灰度开关

**目标**：在不破坏线上行为前提下，把文本生成入口切到 `text_gen_engine`。

**文件**：
- `app/chat/service.py`
- `app/chat/agents/supervisor_agent.py`（若需）

**实现清单**：
- [ ] 为 `text_generate` 增加实际节点接入（替代当前 report 过渡映射）。
- [ ] 增加灰度开关（建议 env：`TEXT_GEN_ENGINE_ENABLED`）。
- [ ] 关闭开关时回退旧路径；开启开关走新引擎。
- [ ] 更新 audit 元数据，记录走新旧哪条路径。

**验收标准**：
- [ ] 开关切换不需要改代码。
- [ ] 回退路径可用，失败可快速止损。

---

## P2-10 集成验证与回归检查

**目标**：确认 Phase 2 可作为后续阶段基础线。

**验证清单**：
- [ ] 路由覆盖：`text_generate` 下 5 插件可正确命中。
- [ ] 槽位覆盖：核心追问/次要追问/默认填充。
- [ ] 生成覆盖：outline-required 与 no-outline 两类均通过。
- [ ] 异常覆盖：
  - [ ] 插件缺失
  - [ ] 插件异常
  - [ ] outline 解析失败
  - [ ] 用户拒绝继续追问
- [ ] 回归覆盖：chat/research 不回退。
- [ ] Lint + Smoke + 脚本化回归全部通过。

**验收标准**：
- [ ] 主流程稳定。
- [ ] report 不回退。
- [ ] 能无阻塞进入 Phase 3。

---

## 4. 依赖关系

- `P2-01` -> `P2-02`
- `P2-02` -> `P2-03/04/05/06/07`（可并行）
- `P2-08` 依赖 `Phase1 slot_definitions`（已完成）
- `P2-09` 依赖 `P2-03`（最小可用）
- `P2-10` 依赖 `P2-01~P2-09`

---

## 5. 建议执行节奏（迭代）

### 迭代 A（骨架）
- 完成 `P2-01` + `P2-02` + `P2-08`

### 迭代 B（保真迁移）
- 完成 `P2-03` + `P2-09`（仅接 report，先灰度）

### 迭代 C（能力扩展）
- 完成 `P2-04` + `P2-05` + `P2-06` + `P2-07`

### 迭代 D（验收）
- 完成 `P2-10`

---

## 6. Phase 2 完成定义（DoD）

满足以下条件即判定 Phase 2 完成：

- [ ] `text_gen_engine` 可稳定接管文本类生成。
- [ ] 5 类文本插件全部可用。
- [ ] 统一槽位收集器已接入并验证。
- [ ] 路由可灰度切换且支持回退。
- [ ] 报告能力无回退。
- [ ] 回归与 lint 通过。

---

## 7. 交付物清单（Phase 2）

- 新增：
  - `app/chat/engines/plugin_base.py`
  - `app/chat/engines/text_gen_engine.py`
  - `app/chat/engines/slot_collector.py`
  - `app/chat/engines/plugins/report_plugin.py`
  - `app/chat/engines/plugins/lesson_plan_plugin.py`
  - `app/chat/engines/plugins/quiz_plugin.py`
  - `app/chat/engines/plugins/flashcard_plugin.py`
  - `app/chat/engines/plugins/blog_plugin.py`
- 修改：
  - `app/chat/service.py`
  - `app/chat/agents/supervisor_agent.py`（按实际）
- 测试：
  - `scripts/test_text_gen_engine_*.py`（建议新增）
  - `scripts/test_slot_collector.py`（建议新增）
  - `scripts/test_plugins_*.py`（建议新增）

---

## 8. 风险与控制点

| 风险 | 等级 | 控制措施 |
|---|---|---|
| ReportPlugin 迁移导致报告质量回退 | 高 | 先单独灰度 report；对比回归后再放量 |
| 插件接口定义不稳导致后续频繁改动 | 中 | 先冻结 `GenPlugin` 最小接口，避免过度设计 |
| SlotCollector 话术与状态机耦合过深 | 中 | 追问策略独立模块化，减少 service.py 侵入 |
| Blog 迁移影响旧 blog_agent | 中 | 先迁移不删除；Phase 6 再清理 |
| 主图切换风险 | 高 | 必须提供开关回退 |

---

## 9. 下一步建议

建议按“**先骨架、再 report 保真、再扩展插件、最后全量切换**”执行，避免一次性改动过大。

如需，我可以在本文件基础上继续输出 `PHASE2_EXECUTION_CHECKLIST.md`（按天/按提交粒度的执行清单）。
