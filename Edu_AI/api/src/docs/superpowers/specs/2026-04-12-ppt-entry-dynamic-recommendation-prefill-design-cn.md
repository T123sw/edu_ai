# PPT 入口动态推荐与自动回填设计（中文）

**状态：** 已完成初版设计，待评审  
**范围：** `D:\Edu_AI_1\Edu_AI\src\components\teacher`、`D:\Edu_AI_1\Edu_AI\src\services\teacher`、`D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application`、`D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\api`、`D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat`

## 1. 背景与目标

当前教师端“创建 PPT”弹窗已经具备显式入口和后端卡片接口：

- 前端打开弹窗时会请求 `POST /api/chat/v2/ppt/cards`
- 后端会返回固定模板卡与系统推荐卡
- 用户点击卡片后，前端仅回填 `objective`、`lengthOption`、`styleHint`

这条链路和报告入口相比存在两个明显差距：

1. 报告入口的推荐卡已经是“每次打开实时生成”，而 PPT 入口的推荐仍以规则模板为主。
2. 报告入口的推荐更接近“可直接发起生成的方向建议”，而 PPT 入口卡片无法把标题、副标题、受众、主题、重点等字段一并补齐，导致教师仍需手填大量配置。

本次设计目标有四个：

1. 让 PPT 入口与报告入口保持一致，打开弹窗时通过显式接口动态生成推荐。
2. 支持“打开即自动回填”：接口返回后自动选择最佳卡片，并把可推断字段批量回填到表单。
3. 支持“点卡即切换回填”：教师点击其他卡片时，用该卡的配置重新覆盖表单。
4. 将推荐逻辑集中在后端，前端不再自行猜测标题、主题、受众、重点等配置。

## 2. 非目标

本次不做以下内容：

1. 不改动 PPT 正式生成主链路，即 `outline -> confirm -> generate -> html2ppt` 的执行方式不变。
2. 不扩展新的主题体系，仍只使用现有受支持主题：`heu_academic_elegant`、`heu_academic_basic`。
3. 不在本次引入“用户手改字段差异合并”算法，首版仍采用整卡覆盖回填。
4. 不把推荐卡做成富编辑器或可局部编辑卡片，卡片仍然是选择入口而不是可编辑对象。

## 3. 用户体验设计

### 3.1 打开弹窗

当用户打开“创建 PPT”弹窗时：

1. 前端请求 `POST /api/chat/v2/ppt/cards`
2. 后端基于已选文档摘要实时生成固定模板卡和系统推荐卡
3. 响应中返回：
   - 卡片列表
   - 默认选中卡片 `default_selected_card_id`
   - 每张卡片对应的完整 `prefill_config`
4. 前端自动选中默认卡片，并立即将其配置回填进表单

表现效果上，教师打开弹窗后不再面对“几乎空白的配置表单”，而是直接看到一套系统已经整理好的默认方案。

### 3.2 点击卡片切换

当教师点击其他卡片时：

1. 前端更新当前选中卡片
2. 读取该卡片的 `prefill_config`
3. 使用该配置整体覆盖表单字段

首版不做字段级 merge，目的是保持行为确定：一张卡片就是一套完整方案。

### 3.3 手动编辑后的行为

自动回填并不取消教师手改能力：

1. 教师仍可在表单中继续修改任何字段
2. 若教师修改后又点击其他卡片，首版直接采用新卡片的完整配置覆盖
3. 若后续发现教师经常先编辑再切卡，可在下一阶段加“存在未保存编辑，是否覆盖”提示

## 4. 方案对比与选型

### 方案 A：前端根据卡片 hint 拼配置

做法：

- 后端仍只返回卡片标题、描述、少量 hint
- 前端根据卡片类型自行拼 `deckTitle`、`themeId`、`keyPointsText` 等字段

问题：

- 推荐逻辑被拆散到前后端
- 同一张卡片在不同入口可能表现不一致
- 后续新增字段时前端推断逻辑会持续膨胀

### 方案 B：后端返回完整回填配置，前端只负责展示与回填

做法：

- 后端为每张卡片生成完整 `prefill_config`
- 前端只做三件事：渲染卡片、自动选中默认卡片、调用 `form.setFieldsValue`

优势：

- 逻辑单点收敛
- 与报告入口的“接口动态生成”思路一致
- 后续要新增可回填字段时扩展成本最低

### 方案 C：后端部分生成，前端补齐剩余字段

做法：

- 后端返回部分结构化字段
- 前端对缺失字段做二次推断

问题：

- 最终仍是双端共同持有推荐逻辑
- 调试与验收成本高

### 选型

本次采用 **方案 B**。

## 5. 后端设计

### 5.1 推荐服务总体改造

当前 `PptEntryCardsServiceV2` 的特点是：

- 固定模板卡通过 `_build_preset_cards()` 返回
- 推荐卡通过规则判断文档摘要关键词构造
- 返回字段仅覆盖展示信息和少量 hint

本次改造后：

1. `PptEntryCardsServiceV2` 仍保留为入口服务
2. 新增 `PptEntryRecommendationGenerator`
3. 服务流程改为：

`selected_doc_ids`
-> `KnowledgeBaseSummaryProvider`
-> `PptEntryRecommendationGenerator`
-> `PptEntryCardsServiceV2`
-> `ChatPptCardsResponseV2`

### 5.2 新增推荐生成器

建议新增文件：

- `app/chat/application/ppt_entry_recommendation_generator.py`

职责：

1. 输入选中文档标题与摘要
2. 结合推荐类型生成 PPT 推荐卡
3. 为每张卡片生成完整 `prefill_config`
4. 选出一个默认卡片并返回 `default_selected_card_id`

其设计应尽量复用报告入口已有模式：

- 优先尝试结构化 LLM 输出
- 若失败则降级到 JSON 提取
- 若仍失败则退回规则兜底

### 5.3 推荐类型

推荐类型保留现有四类，避免影响前端已有分组与埋点语义：

- `concept_focus`
- `process_flow`
- `comparison_view`
- `case_application`

允许后端根据文档内容动态决定输出顺序和默认卡片，但仍要求：

1. 固定模板卡始终存在
2. 推荐卡至少返回一张
3. 存在默认卡片

### 5.4 新增完整回填配置

为每张 `PptEntryCard` 新增 `prefill_config` 字段，直接与前端表单结构对齐。

建议结构：

```json
{
  "deck_title": "AI Agent 中的 Skills 与 MCP",
  "deck_subtitle": "基于 2 份课程资料生成的课堂讲解课件",
  "audience": "本科生",
  "objective": "课堂讲解",
  "theme_id": "heu_academic_elegant",
  "length_option": "medium",
  "target_slide_count": 16,
  "key_points": ["核心定义", "工作流程", "典型案例"],
  "style_hint": "讲解清晰，层次分明",
  "general_requirements": "用于课堂投屏，强调概念辨析与案例说明",
  "special_requirements": "结尾保留总结与提问页"
}
```

字段说明：

- `deck_title`：推荐的 PPT 标题
- `deck_subtitle`：根据课程名、资料数、使用场景自动补充
- `audience`：从文档语境或常见教学对象推断
- `objective`：课堂讲解 / 主题分享 / 对比分析 / 汇报答辩
- `theme_id`：当前支持主题之一
- `length_option`：`short` / `medium` / `long`
- `target_slide_count`：与长度映射一致，允许后端直接给出目标页数
- `key_points`：结构化重点数组，前端负责转成 textarea
- `style_hint`：表达方式与版式风格建议
- `general_requirements`：面向大纲生成的通用说明
- `special_requirements`：附加约束

### 5.5 默认卡片

响应中新增：

```json
{
  "default_selected_card_id": "rec-concept-focus"
}
```

选取规则：

1. 优先选 `fit_score=high` 的推荐卡
2. 若有多张 `high`，优先第一张推荐卡
3. 若推荐生成失败只剩固定模板，则回退到默认固定模板 `preset-knowledge-lecture`

### 5.6 规则兜底

即使 LLM 不可用，也必须返回可自动回填的完整配置。

兜底逻辑建议：

1. 多文档场景优先 `comparison_view`
2. 含“流程 / 机制 / 步骤”关键词优先 `process_flow`
3. 含“案例 / 应用 / 场景”关键词优先 `case_application`
4. 其他场景默认 `concept_focus`

同时由规则模板生成对应 `prefill_config`：

- `theme_id` 默认 `heu_academic_elegant`
- `length_option` 按推荐类型给出默认值
- `target_slide_count` 由长度映射
- `deck_title` 基于主标题词和推荐类型拼接
- `key_points` 从摘要中抽重点词，抽不到则用推荐类型默认重点

## 6. 前端设计

### 6.1 类型定义

需要同步扩展：

- `src/services/teacher/chatV2.ts`
- 如有辅助类型，也同步补充到相关 helper

`PptEntryCard` 需新增：

```ts
prefill_config?: {
  deck_title?: string;
  deck_subtitle?: string;
  audience?: string;
  objective?: string;
  theme_id?: 'heu_academic_elegant' | 'heu_academic_basic';
  length_option?: 'short' | 'medium' | 'long';
  target_slide_count?: number;
  key_points?: string[];
  style_hint?: string;
  general_requirements?: string;
  special_requirements?: string;
};
```

`ChatPptCardsResponseV2` 需新增：

```ts
default_selected_card_id?: string;
```

### 6.2 表单回填行为

`PptEntryPanel` 中新增统一回填函数，例如：

```ts
applyCardPrefill(card: PptEntryCard): void
```

职责：

1. 设置选中卡片
2. 将 `prefill_config` 转为表单值
3. `key_points` 数组转为 textarea 文本
4. 调用 `form.setFieldsValue`

### 6.3 自动回填时机

在 `fetchPptEntryCardsV2(...).then(...)` 成功后：

1. 解析卡片列表
2. 读取 `default_selected_card_id`
3. 找到默认卡片
4. 若找到则立即执行 `applyCardPrefill`
5. 若没找到则按回退策略选择第一张推荐卡，再退到第一张固定模板卡

### 6.4 点击卡片时机

点击任意卡片时：

1. 直接执行 `applyCardPrefill`
2. 不再只更新 `objective/length/style`
3. 行为上保持“整卡切换即整套方案切换”

### 6.5 表单字段映射

前端表单字段与 `prefill_config` 的映射如下：

- `deckTitle <- deck_title`
- `deckSubtitle <- deck_subtitle`
- `audience <- audience`
- `objective <- objective`
- `themeId <- theme_id`
- `lengthOption <- length_option`
- `keyPointsText <- key_points.join('\n')`
- `styleHint <- style_hint`
- `generalRequirements <- general_requirements`
- `specialRequirements <- special_requirements`

`target_slide_count` 在本次前端界面仍可不直接展示，但需保留在请求层，保证后续大纲生成使用。

## 7. 接口契约调整

### 7.1 响应模型

后端 `ChatPptCardsResponseV2` 增加：

```python
class PptPrefillConfigV2(BaseModel):
    deck_title: str = ""
    deck_subtitle: Optional[str] = None
    audience: str = ""
    objective: str = ""
    theme_id: str = "heu_academic_elegant"
    length_option: PptLengthOption = "medium"
    target_slide_count: int = 0
    key_points: List[str] = Field(default_factory=list)
    style_hint: Optional[str] = None
    general_requirements: Optional[str] = None
    special_requirements: Optional[str] = None

class PptEntryCardV2(BaseModel):
    ...
    prefill_config: Optional[PptPrefillConfigV2] = None

class ChatPptCardsResponseV2(BaseModel):
    entry_mode: PptEntryMode
    cards: List[PptEntryCardV2] = Field(default_factory=list)
    default_selected_card_id: Optional[str] = None
    trace: Dict[str, Any] = Field(default_factory=dict)
```

### 7.2 与大纲接口的衔接

`KnowledgeBaseDirectPptOutlineRequestV2` 结构不需要新增字段，因为它已经支持：

- `deck_title`
- `deck_subtitle`
- `audience`
- `objective`
- `theme_id`
- `length_option`
- `target_slide_count`
- `key_points`
- `style_hint`
- `special_requirements`
- `general_requirements`

也就是说，本次设计的关键不是修改大纲接口，而是把这些字段在入口阶段尽量填满。

## 8. 测试设计

### 8.1 后端测试

新增或调整测试覆盖：

1. `test_ppt_entry_cards_service_v2.py`
   - 返回推荐卡时包含 `prefill_config`
   - 返回 `default_selected_card_id`
   - LLM 失败时仍有规则兜底配置
2. `test_schemas_v2.py`
   - 校验 `prefill_config` 与 `default_selected_card_id` schema
3. 如新增推荐生成器：
   - 校验 recommendation type 顺序保持
   - 校验主题只能落在受支持主题范围内

### 8.2 前端测试

新增或调整测试覆盖：

1. 弹窗打开后请求卡片接口成功，会自动回填默认卡片配置
2. 点击另一张卡片后，表单字段整体切换
3. `key_points` 数组会正确转成多行文本
4. 无默认卡片时，会按回退规则自动选择

### 8.3 集成验证

至少验证一次从入口到大纲请求的链路：

1. 打开弹窗
2. 自动回填
3. 直接点“生成大纲”
4. 确认提交给 `/api/chat/v2/ppt/outline` 的 `ppt_config` 已携带自动补齐字段

## 9. 风险与约束

### 9.1 覆盖手改内容

风险：

- 教师修改表单后再点卡片，现有设计会整表覆盖

处理：

- 首版接受该行为，后续若反馈明显再补“未保存修改提醒”

### 9.2 LLM 输出不稳定

风险：

- 主题、受众、标题、重点可能出现不稳定或超范围值

处理：

1. 结构化输出约束
2. 服务端归一化主题 ID
3. 缺失字段自动回退到规则默认值

### 9.3 文档摘要质量影响推荐质量

风险：

- 若摘要过短，推荐卡会趋于通用

处理：

- 允许 fallback，但 fallback 也必须给出完整配置，保证体验稳定

## 10. 实施收口

本次改造的核心不是新增更多表单项，而是把 PPT 入口改造成“推荐即配置”的模式：

1. 打开弹窗即动态推荐
2. 系统自动选中最佳卡片并自动回填
3. 点击其他卡片即切换整套配置
4. 自动回填出的配置可直接进入 PPT 大纲生成

完成后，PPT 入口会在交互体验上更接近报告入口，同时比报告入口更进一步，因为它不仅推荐方向，还能直接把生成所需配置尽量补齐。
