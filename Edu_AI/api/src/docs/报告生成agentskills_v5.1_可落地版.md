# 报告生成 AgentSkills 实施规范（v5.1 可落地版）

> 文档目的：融合 `报告生成.md` 与 `报告生成修改.md` 的全部能力点，形成**可直接编码落地**的统一方案。  
> 适用范围：`edu-report-agent`（知识/研究报告）+ `edu-report-workflow`（状态机流程控制）。  
> 核心原则：**先收敛需求，再树状大纲，再精准修改，再分章生成**；同时保证高情商交互、有限追问、可审计、可恢复。

---

## 0. 产品定位与边界

## 0.1 定位
`edu-report-agent` 仅负责**知识性/研究性报告**，例如：
- 《西游记》人物分析
- 黑洞原理报告
- AI 发展史研究综述

## 0.2 明确不做
- 不做课堂互动设计
- 不做教案流程/课时分配（属于教学场景）

## 0.3 关键目标
1. 用户一句话能提取多槽位（Dense Extraction）
2. 话题过宽时，Agent 自动联想并追问高价值限制条件
3. 最多 2 轮硬追问，避免“审讯式”体验
4. 可识别不耐烦并强制放行（force_generate）
5. 大纲采用树状 AST，支持局部 Diff/Patch 修改
6. 正文采用分章循环生成，避免长文偷懒与断片

---

## 1. 总体架构（Agent + Workflow）

## 1.1 技能分工
- `edu-report-agent`：语义提取、追问策略、大纲生成/修改、正文生成提示词规范
- `edu-report-workflow`：流程门禁与状态路由（extractor -> evaluator -> ask -> outline -> generate）

## 1.2 全局流程
1. `extractor`：提取槽位 + 意图识别 + 充分性判断 + 动态联想
2. `evaluator`：路由决策（ask / outline / generate）
3. `ask`：硬追问（L1/L2）或软确认（L3）
4. `outline`：生成树状大纲（AST JSON）
5. `outline_modifier`（逻辑可挂在 outline 节点内）：局部补丁修改 + 修改价值反馈
6. `generate`：分章循环生成 + 连贯拼接 + 断点恢复

---

## 2. 槽位体系（最终版）

## 2.1 L1 绝对必填（Required）
1. `core_topic`：核心主题（如“西游记”）
2. `focus_area`：聚焦方向（如“孙悟空人物形象”）

> 规则：L1 任一缺失，禁止出大纲，必须硬追问。

## 2.2 L2 动态联想槽位（Dynamic Constraints）
- 字段：`dynamic_constraints`（对象）
- 含义：当 `core_topic + focus_area` 仍然太宽泛时，模型临时联想出的限制维度
- 典型动态维度：
  - 文史类：`specific_chapter_or_event`、`comparison_target`、`historical_context`
  - 科学类：`application_scenario`、`boundary_condition`、`time_scope`

> 规则：
> - 每轮最多新增 1 个动态约束维度
> - 以“可写性/可论证性”为标准决定是否追问
> - 若达到追问轮次上限，允许 Auto-fill 后直接放行

## 2.3 L3 选填/静默推断槽位（Optional & Implicit）
1. `length_requirement`（长度）
2. `depth_level`（深度）
3. `format_style`（文风）

> 规则：
> - 不作为硬追问前置条件
> - 可在 L1/L2 满足后进行一次“蓝图打包软确认”
> - 允许默认值

## 2.4 默认值建议
- `length_requirement`：`常规长度（约3-4章）`
- `depth_level`：`标准研报级（逻辑严密、可读）`
- `format_style`：`结构化分块论述`

---

## 3. 状态契约（Graph State）

```json
{
  "user_intent": "provide|modify_outline|confirm_outline|force_generate|chitchat",
  "report_ask_counts": 0,
  "soft_params_confirmed": false,
  "report_slots": {
    "core_topic": "string",
    "focus_area": "string|null",
    "length_requirement": "string|null",
    "depth_level": "string|null",
    "format_style": "string|null"
  },
  "dynamic_constraints": {},
  "report_missing": [
    {
      "slot_name": "string",
      "reason": "string"
    }
  ],
  "report_outline": [],
  "is_generating_content": false,
  "report_meta": {
    "is_report": true,
    "user_intent": "provide"
  }
}
```

---

## 4. 提取器（Extractor）设计

## 4.1 核心职责
1. 意图识别（含不耐烦识别）
2. 多槽位密集提取（一句话拆多字段）
3. 信息充分性审查（Sufficiency Check）
4. 动态约束联想
5. 输出标准 JSON（增量优先）

## 4.2 多槽位提取要求（Dense Extraction）
示例输入：
- “帮我生成孙悟空的人物形象报告，背景为火焰山，风格要正经学术风格。”

期望提取：
- `core_topic=西游记/孙悟空`（按语义归并）
- `focus_area=孙悟空人物形象（限定：火焰山章节）`
- `format_style=严谨学术风格`
- `depth_level=深度分析`（可推断）

## 4.3 不耐烦识别（Impatience Override）
触发词（示例）：
- “别问了” “快点” “你看着办” “随便” “直接生成”

触发行为：
1. `user_intent=force_generate`
2. 清空 `report_missing`
3. 对缺失项执行最安全 Auto-fill
4. evaluator 必须跳过 ask，直接 outline

## 4.4 追问轮次硬截断
- 若 `report_ask_counts >= 2`，即使仍有缺失，也要强制放行：
  - `user_intent=force_generate`
  - Auto-fill 缺失槽位
  - 进入 outline

## 4.5 输出契约（Extractor）
```json
{
  "user_intent": "provide|modify_outline|confirm_outline|force_generate|chitchat",
  "report_slots": {
    "core_topic": "string|null",
    "focus_area": "string|null",
    "length_requirement": "string|null",
    "depth_level": "string|null",
    "format_style": "string|null"
  },
  "dynamic_constraints": {},
  "report_missing": [
    {
      "slot_name": "string",
      "reason": "string"
    }
  ]
}
```

---

## 5. 评估路由器（Evaluator）门禁规则

## 5.1 决策优先级
1. `force_generate` -> `response_type=outline`（最高优先）
2. `report_ask_counts >= 2` -> `response_type=outline`（强制截断）
3. `report_missing` 非空 -> `response_type=ask`
4. `report_missing` 为空 且 `soft_params_confirmed=false` -> `response_type=ask`（软确认）
5. 已有大纲且 `confirm_outline` -> `response_type=generate`
6. 其他 -> `response_type=outline`

## 5.2 伪代码（落地参考）
```python
def evaluator_router(state):
    intent = state.get("user_intent")
    ask_count = int(state.get("report_ask_counts", 0))
    missing = state.get("report_missing", [])
    has_outline = bool(state.get("report_outline"))
    soft_done = bool(state.get("soft_params_confirmed", False))

    if intent == "force_generate":
        return "outline"
    if ask_count >= 2:
        return "outline"
    if has_outline and intent == "confirm_outline":
        return "generate"
    if missing:
        return "ask"
    if not soft_done:
        return "ask"
    return "outline"
```

---

## 6. 追问节点（Ask）设计

## 6.1 硬追问（Hard Ask）
触发条件：L1/L2 缺失。

规则：
1. 一次只问 1 个最高价值缺失点
2. 必须基于 `reason` 解释“为什么要问”
3. 给 2-3 个启发式选项
4. 结尾给用户退路：可回复“你看着办”

输出模板示例：
- “为了让这份报告更有深度，建议先限定一个具体切口：A... B... C... 你可以选一个，或直接说‘你看着办’。”

## 6.2 软确认（Soft Blueprint Confirm）
触发条件：L1/L2 已齐备，`soft_params_confirmed=false`。

规则：
1. 肯定当前方向
2. 一次打包询问 `length_requirement + depth_level (+format_style可选)`
3. 提供默认锚点（如中等篇幅、标准深度）
4. 允许用户回复“按常规写”

输出示例：
- “方向已很清晰。出大纲前再对齐一下：中等篇幅（约3-4章）可以吗？深度偏通俗科普还是深度分析？你也可以直接说‘按常规写’。”

---

## 7. 大纲节点（Outline AST Generator）

## 7.1 输出必须是树状 JSON（禁止只给纯 Markdown）

```json
[
  {
    "chapter_id": 1,
    "chapter_title": "第一章：...",
    "chapter_goal": "本章目标...",
    "sections": [
      {"section_id": "1.1", "title": "..."},
      {"section_id": "1.2", "title": "..."}
    ]
  }
]
```

## 7.2 章节规模控制（长度槽位映射）
- `简短`：2章 × 每章2节
- `常规`：3-4章 × 每章2-3节
- `详尽`：4-5章 × 每章3节（建议含案例/对比）

> 不强控字数，用结构复杂度控制最终长度。

## 7.3 大纲挂起与确认
- 生成大纲后进入挂起（等待用户“确认/修改”）
- 未确认禁止进入正文生成（除 force_generate 特例）

---

## 8. 大纲修改（Outline Diff & Patch）

## 8.1 修改目标
只改用户指定部分，不重写整份大纲。

## 8.2 Patch 输出契约
```json
{
  "user_intent": "modify_outline",
  "modifications": [
    {
      "action": "update_chapter|add_chapter|delete_chapter|update_section|add_section|delete_section",
      "target_id": "2|2.1",
      "new_content": {}
    }
  ],
  "assistant_feedback": "string"
}
```

## 8.3 执行规则
1. 通过 `chapter_id/section_id` 精准定位
2. 仅执行局部替换（CRUD）
3. 未命中目标时，不得胡改，转 ask 追问定位

## 8.4 修改后反馈（必须）
不能只回复“已修改”，必须包含：
1. 修改确认（改了哪里）
2. 合理性分析（结构收益）
3. 下一步引导（是否开始生成正文）

反馈示例：
- “已将第二章改为‘三打白骨精与心智成熟’，并新增 2.2 小节‘唐僧误解’。这个调整显著增强了人物成长线与冲突强度。若你确认，我就按新大纲生成正文。”

---

## 9. 正文生成（Generate：Chunked Sequential）

## 9.1 核心策略
- 按章循环生成（禁止一波流全篇）
- 每轮只写一章，降低认知负荷
- 使用 `previous_ending` 做章节过渡

## 9.2 单章生成输入
- 全局上下文（主题/风格/深度）
- 当前章节结构（title/goal/sections）
- 上一章结尾（previous_ending）

## 9.3 单章生成硬约束
1. 仅写当前章
2. 每节必须有：观点 + 解释 + 示例/证据
3. 开头要与上一章自然衔接
4. 输出 Markdown（`##`章标题，`###`小节）

## 9.4 生成伪代码
```python
report_content = ""
previous_ending = ""
for chapter in report_outline:
    chapter_text = llm_generate_chapter(chapter, previous_ending, global_context)
    report_content += chapter_text + "\n\n"
    previous_ending = extract_last_paragraph(chapter_text)
```

## 9.5 工具按需挂载（可选）
- 若某章需要最新事实，可在该章前触发 web/rag 检索并注入章级参考资料

---

## 10. 降级与兜底（Graceful Degradation）

1. **结构化失败兜底**：大纲 JSON schema 不通过 -> 回退 Markdown 解析
2. **章节超时兜底**：生成中断 -> 从当前章节重试（checkpoint），不重写全篇
3. **修改定位失败兜底**：指令模糊 -> ask 追问 target_id
4. **过度追问兜底**：超过 2 轮 -> force_generate + autofill

---

## 11. 审计与指标

## 11.1 审计字段
- `extractor_reason/source/override_applied`
- `outline_reason/source/override_applied`
- `generate_reason/source/override_applied`
- `user_intent`
- `report_ask_counts`
- `soft_params_confirmed`

## 11.2 指标（必须）
1. `avg_ask_turns`（目标 < 1.5）
2. `force_generate_rate`（过高说明追问压迫感强）
3. `outline_ast_parse_success_rate`
4. `outline_modify_hit_rate`
5. `chapter_avg_tokens`
6. `generate_retry_rate`

---

## 12. 实施分阶段（确保每个功能都落地）

## 12.1 Phase A（提取与追问）
- [ ] L1/L2/L3 槽位落地
- [ ] Dense Extraction few-shot
- [ ] 不耐烦识别（force_generate）
- [ ] `report_ask_counts` 两轮截断
- [ ] 软确认（soft_params_confirmed）

## 12.2 Phase B（大纲与修改）
- [ ] AST 大纲 schema 输出
- [ ] 挂起确认机制
- [ ] Diff/Patch 修改契约与执行器
- [ ] 修改后分析反馈

## 12.3 Phase C（正文生成）
- [ ] 分章循环生成
- [ ] previous_ending 过渡
- [ ] 章节失败断点重试
- [ ] 长度映射（章节规模控制）

---

## 13. 关键 Few-shot（摘要）

## 13.1 话题过宽 -> 动态追问
输入：“写西游记报告”
输出：缺失 `focus_area`，追问提供 2-3 选项。

## 13.2 一句话多槽位
输入：“写孙悟空人物形象，聚焦火焰山，学术风格。”
输出：一次提满 `core_topic/focus_area/format_style/depth_level`。

## 13.3 用户不耐烦
输入：“别问了，快点出大纲。”
输出：`user_intent=force_generate`，清空 missing，直接 outline。

## 13.4 局部修改
输入：“把第二章改成三打白骨精，并加一节讲唐僧误解。”
输出：`update_chapter(target_id=2)` patch + 合理性反馈。

---

## 14. 与现有系统的对齐建议（代码落地提醒）

1. 当前已有 `extractor/evaluator/ask/outline/generate`，可原位升级，不需推翻。
2. `report_slots` 从固定字段迁移到本方案时，建议保留兼容映射层。
3. `outline_modifier` 可作为 outline 节点的分支子流程，避免新增过多节点。
4. 先跑通 AST + patch，再接入章节级生成重试。

---

## 15. 版本记录

### v5.1.0（本文件）
- 融合两份文档全部功能点并补全工程落地细则
- 确认最终槽位分层（L1/L2/L3）
- 明确硬追问/软确认、两轮截断、force_generate
- 引入 AST 大纲 + Diff/Patch + 修改合理性反馈
- 引入分章生成 + previous_ending + checkpoint 兜底
