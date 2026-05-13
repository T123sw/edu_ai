# 知识库小游戏生成功能设计（中文）

**状态：** 已完成初版设计，待评审  
**范围：** `D:\Edu_AI_1\Edu_AI\src\components\teacher`、`D:\Edu_AI_1\Edu_AI\src\services\teacher`、`D:\Edu_AI_1\Edu_AI\src\store\teacher`、`D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application`、`D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\api`、`D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat`

## 1. 背景与目标

当前教师工作台已经支持报告、习题、教案、PPT 等知识库直出型产物，但 `dynamic-templates/games` 下新增的 3 个小游戏模板尚未接入正式链路：

- `category-sort`：分类归纳
- `drag-match`：拖拽配对
- `memory-flip`：翻牌记忆

每个模板都由两部分组成：

1. 一个独立 HTML 模板文件
2. 一个与之对应的 JSON Schema 文件

模板中的 `__GAME_DATA_JSON__` 占位符表明，这套能力的核心不是“生成一段自由 HTML”，而是“基于知识库内容生成符合模板 schema 的结构化游戏数据，再注入模板得到可运行的小游戏页面”。

本次设计目标有五个：

1. 在教师工作台新增“小游戏生成”入口，作为独立于 `quiz` 的正式产物类型。
2. 支持“勾选知识库文档 -> 选择小游戏 -> 直接生成”的极简首版流程。
3. 生成后在工作台右侧预览小游戏，并提供“全屏播放”入口。
4. 生成结果保存进课程资料列表，后续可再次打开、预览、播放。
5. 保持首版范围收敛，不引入尚未确认的编辑态、推荐态和复杂播放器壳层。

## 2. 已确认决策

### 2.1 产品决策

本次已经确认以下产品方向：

1. 小游戏作为独立新类型接入工作台，不复用 `quiz` 类型。
2. 工作台内先预览，点击“全屏播放”进入独立页面。
3. 首版不提供老师手动编辑游戏内容的能力。
4. 生成结果需要像 PPT / 教案 / 报告 一样保存进课程资料列表。
5. 当前只有 3 个模板，因此“选择小游戏”就是“选择模板”，不再拆成两层概念。

### 2.2 技术决策

本次采用以下技术方案：

1. 首版仅新增一个知识库直出接口：`POST /api/chat/v2/game/direct`。
2. 前端首版不额外请求“模板列表接口”，而是在工作台内静态展示 3 个已知小游戏卡片。
3. “全屏播放”首版不再套一层新的前端播放器路由，而是直接打开生成后的独立 HTML 页面。
4. 生成产物统一命名为 `game` artifact，并作为新的 `GeneratedFile['type']`。
5. 生成链路必须经过 schema 校验；若 LLM 首次输出非法，则进行一次带错误反馈的修复重试；若仍失败，则返回明确错误。

## 3. 非目标

本次明确不做以下内容：

1. 不做模板推荐排序，不根据文档自动替老师选择游戏类型。
2. 不做生成前或生成后的结构化编辑器。
3. 不做学生分享链接、公开访问链接、匿名访问能力。
4. 不做游戏过程成绩记录、答题上报、排行榜、学习分析。
5. 不做模板市场化扩展接口，首版只接入仓库内已有 3 个模板。
6. 不把小游戏挂在 `quiz` 的产物体系下混合显示。

## 4. 方案对比与选型

### 方案 A：把小游戏塞进现有 `quiz` 类型

做法：

- 前后端继续沿用 `quiz` 类型。
- 使用 `meta.kind = game` 区分小游戏。

问题：

- 语义混乱，工作台中的“习题”和“小游戏”会混在一起。
- 预览逻辑会逐步堆积条件分支。
- 课程资料、图标、筛选和后续扩展都会变脏。

### 方案 B：新增独立 `game` 产物链路

做法：

- 新增独立后端服务、接口、artifact type、前端预览组件与课程资料映射。
- 工作台中把小游戏与报告、PPT、教案等并列。

优势：

- 类型清晰，后续扩展模板时成本最低。
- 预览和播放链路可以围绕 HTML 游戏页面单独演进。
- 与用户已经确认的“保存为正式课程产物”目标一致。

### 方案 C：只生成 HTML 地址，不进入工作台产物体系

做法：

- 后端只返回一个可打开的小游戏 URL。
- 前端不做工作台预览与课程资料持久化。

问题：

- 不符合本次已经确认的产品目标。
- 无法复用现有课程资料流。
- 后续再次打开、再次播放体验不完整。

### 选型

本次采用 **方案 B**。

## 5. 用户体验设计

### 5.1 入口

在教师工作台 `StudioPanel` 的生成能力区新增“小游戏生成”卡片，与现有的：

- 报告
- 教案生成
- 习题
- PPT

并列展示。

点击后打开 `GameEntryModal`。

### 5.2 生成弹窗

`GameEntryModal` 首版只做一件事：让老师在 3 个小游戏中选择一个。

弹窗内容：

1. 顶部显示当前已选文档数量。
2. 中部展示 3 个游戏卡片：
   - 分类归纳
   - 拖拽配对
   - 翻牌记忆
3. 底部提供“取消 / 生成小游戏”。

行为规则：

1. 若未选择任何知识库文档，则生成按钮禁用，并提示先勾选文档。
2. 用户必须显式选择一个小游戏后才能提交。
3. 首版不出现额外配置项，不要求老师填写标题、题目数、难点等字段。

### 5.3 生成后预览

生成成功后，工作台右侧直接进入 `GameArtifactPreview`。

预览区域包含：

1. 返回按钮
2. 产物标题
3. “全屏播放”按钮
4. 预览主体 iframe

预览主体直接加载后端生成出的 HTML 页面。

### 5.4 全屏播放

“全屏播放”按钮首版直接打开生成好的独立 HTML 页面。

首版不额外引入新的前端壳层页面，原因如下：

1. 生成出的 HTML 已经是完整可运行页面。
2. 预览和播放可共享同一份 HTML。
3. 可以显著减少前端路由、壳层布局、状态同步的复杂度。

这里的“全屏播放”在产品语义上表示“进入独立沉浸播放页面”，并不要求首版必须再调用浏览器原生 Fullscreen API。若后续需要，可在独立 HTML 页面内继续追加原生全屏按钮。

### 5.5 再次打开

小游戏被保存为课程资料后，后续老师从课程资料列表再次点开同一产物时：

1. 工作台右侧仍然进入 `GameArtifactPreview`
2. 仍可点击“全屏播放”
3. 不需要重新生成

## 6. 模板与数据模型设计

### 6.1 模板注册表

后端新增一个轻量模板注册表，负责维护以下信息：

- `game_type`
- `template_id`
- `display_name`
- `html_template_path`
- `schema_path`

首版固定包含 3 条注册项：

1. `category_sort`
2. `drag_match`
3. `memory_flip`

其中：

- `category_sort` 对应 `category-sort.html` 与 `category-sort.schema.json`
- `drag_match` 对应 `drag-match.html` 与 `drag-match.schema.json`
- `memory_flip` 对应 `memory-flip.html` 与 `memory-flip.schema.json`

这样前端传入的是稳定的 `game_type`，后端自行映射到本地模板与 schema。

### 6.2 结构化数据协议

三个模板的结构化数据协议分别为：

#### `category_sort`

```json
{
  "title": "古代中国政治制度分类练习",
  "categories": [
    { "id": "central", "name": "中央制度" },
    { "id": "local", "name": "地方制度" }
  ],
  "items": [
    { "id": "i1", "text": "三省六部制", "categoryId": "central" },
    { "id": "i2", "text": "郡县制", "categoryId": "local" }
  ]
}
```

#### `drag_match`

```json
{
  "title": "历史概念配对",
  "pairs": [
    { "id": "p1", "left": "郡县制", "right": "中央直接任免地方官的制度" },
    { "id": "p2", "left": "分封制", "right": "周代按宗法血缘分封诸侯的制度" }
  ]
}
```

#### `memory_flip`

```json
{
  "title": "术语记忆翻牌",
  "matches": [
    { "pair_id": "m1", "card_a": "光合作用", "card_b": "植物利用光能合成有机物" },
    { "pair_id": "m2", "card_a": "蒸腾作用", "card_b": "植物通过叶片散失水分" }
  ]
}
```

### 6.3 模板选择原则

首版不做“自动推荐游戏类型”，而是完全以用户手动选择结果为准。

后端职责是：

1. 接收 `game_type`
2. 加载对应 schema
3. 约束 LLM 输出该 schema 所要求的数据结构

## 7. 后端设计

### 7.1 新增服务

建议新增文件：

- `app/chat/application/knowledge_base_direct_game_service_v2.py`
- `app/chat/application/game_template_registry.py`

如果模板注入和 HTML 输出逻辑较长，可继续拆出：

- `app/chat/application/game_template_renderer.py`

### 7.2 服务职责

`KnowledgeBaseDirectGameServiceV2` 职责如下：

1. 读取并校验 `selected_doc_ids`
2. 通过 `KnowledgeBaseDocumentContentProvider` 拉取已选文档内容
3. 根据 `game_type` 读取对应 schema 与 HTML 模板
4. 构造 LLM 提示词，要求仅输出符合 schema 的 JSON
5. 对返回 JSON 进行解析与 schema 校验
6. 若校验失败，拼接错误原因后发起一次修复重试
7. 将合法 JSON 注入 HTML 模板，生成独立页面文件
8. 构建 `game` artifact
9. 将产物保存到课程资料

### 7.3 新增接口

首版仅新增一个生成接口：

`POST /api/chat/v2/game/direct`

请求结构建议为：

```json
{
  "course_id": "course-123",
  "scope_type": "course",
  "scope_id": "course-123",
  "selected_doc_ids": ["doc-1", "doc-2"],
  "game_type": "drag_match"
}
```

说明：

1. `selected_doc_ids` 必填
2. `game_type` 必填，允许值仅限 `category_sort / drag_match / memory_flip`
3. 首版不接受额外配置对象

### 7.4 响应结构

新增响应模型 `ChatDirectGameResponseV2`，结构与现有 `report / quiz / ppt` 直出响应保持一致：

```json
{
  "action": { "name": "generate.game.direct" },
  "artifacts": [
    {
      "artifact_id": "game-abcdef123456",
      "artifact_type": "game",
      "title": "历史概念配对.html",
      "content": {
        "game_type": "drag_match",
        "template_id": "drag-match",
        "game_data": {
          "title": "历史概念配对",
          "pairs": []
        },
        "html_url": "/api/chat/v2/games/html?path=teacher_a/course-123/game-abcdef123456/index.html"
      },
      "generation_state": {
        "status": "completed",
        "mode": "knowledge_base_direct",
        "selected_doc_count": 2
      }
    }
  ],
  "trace": {
    "path": "direct",
    "generation_mode": "knowledge_base_direct_game",
    "selected_doc_count": 2,
    "content_doc_count": 2
  }
}
```

### 7.5 HTML 生成与托管

后端需要新增小游戏 HTML 文件托管能力，建议模式与已有图片/视频托管保持一致：

1. 将生成后的 HTML 写入 `Config.STORAGE_ROOT / "chat_games" / owner / scope_or_session / artifact_id / index.html`
2. 对外通过受鉴权保护的接口返回：
   - `/api/chat/v2/games/html?path=...`
3. 服务端验证该路径必须位于当前用户允许访问的目录之下

这样既能支持工作台 iframe 预览，也能支持独立页面播放。

### 7.6 LLM 提示与校验

生成提示需要明确约束：

1. 只能基于已选文档生成
2. 只能返回 JSON
3. JSON 必须严格符合目标 schema
4. 内容必须适合教学场景，避免无关娱乐化扩写

校验流程：

1. 解析 LLM 输出为 JSON
2. 使用目标 schema 校验
3. 若失败，构造带错误摘要的第二次提示词，请模型仅修复结构和字段问题
4. 第二次仍失败则直接报错，不引入规则硬编码兜底生成器

首版不做规则化兜底的原因是：

1. 三种模板结构不同
2. 基于任意知识库文档自动构造高质量游戏数据并不适合简单规则生成
3. 失败时给出明确错误，比生成质量不可控的伪结果更安全

### 7.7 课程资料持久化

生成成功后，小游戏需要像 `quiz` 一样写入课程资料。

建议保存：

- `material_type = "game"`
- `title`
- `content`
- `generation_state`
- `selected_doc_ids`
- `documents_used`

其中 `content` 至少要包含：

- `game_type`
- `template_id`
- `game_data`
- `html_url`

这样课程资料被重新加载时，无需重新生成即可恢复预览与播放。

## 8. 前端设计

### 8.1 类型扩展

需要扩展以下类型定义：

- `src/store/teacher/useStore.ts`
- `src/services/teacher/chatV2.ts`
- `src/services/teacher/chatV2.helpers.ts`
- `src/services/teacher/materials.helpers.ts`

核心变化：

1. `GeneratedFile['type']` 增加 `game`
2. 新增 `KnowledgeBaseDirectGameRequestV2`
3. 新增 `ChatDirectGameResponseV2`
4. 在 `extractGeneratedFilesFromV2Response` 中把 `artifact_type = game` 映射成前端 `GeneratedFile`

### 8.2 生成入口

在 `StudioPanel.tsx` 中：

1. 新增一个 `type: 'game'` 的生成卡片
2. 新增 `GameEntryModal`
3. 新增 `gameEntryVisible` 状态
4. 新增 `handleGameEntrySubmit`

`handleGameEntrySubmit` 行为：

1. 调用 `generateKnowledgeBaseGameV2`
2. 将返回的 artifact 转换为 `GeneratedFile`
3. 写入 `generatedFiles`
4. 自动将最新文件设为 `viewingFile`
5. 若存在 `courseId`，则同步加入课程资料并刷新列表

### 8.3 游戏选择弹窗

建议新增：

- `src/components/teacher/GameEntryModal.tsx`

弹窗内部直接维护 3 张游戏卡片常量，不额外请求后端模板列表。

每张卡片包含：

- `gameType`
- `title`
- `description`
- `sampleUseCase`

点击卡片后进入选中态，再点击“生成小游戏”提交。

### 8.4 预览组件

建议新增：

- `src/components/teacher/GameArtifactPreview.tsx`

组件职责：

1. 展示返回按钮
2. 展示标题
3. 展示“全屏播放”按钮
4. 使用 iframe 加载 `html_url`
5. 在 `html_url` 缺失时显示错误占位态

StudioPanel 中新增：

```ts
if (viewingFile.type === 'game') {
  return <GameArtifactPreview ... />
}
```

### 8.5 全屏播放按钮

按钮行为首版定义为：

1. 读取 `viewingFile.meta?.htmlUrl`
2. 直接在新窗口或新标签页打开该地址

首版不强制要求浏览器 Fullscreen API，也不增加新的 React 路由页面。

### 8.6 课程资料回显

课程资料回显时，需要在 `materials.helpers.ts` 中新增 `game` 类型映射逻辑，使课程资料中的小游戏可以恢复为：

```ts
{
  type: 'game',
  content: {
    game_type,
    template_id,
    game_data,
    html_url
  },
  meta: {
    htmlUrl,
    kind: 'game',
    gameType,
    templateId
  }
}
```

这样当老师再次点击课程资料中的小游戏时，预览区可以直接打开。

## 9. 错误处理

### 9.1 文档选择错误

若未选择文档：

- 前端禁用提交按钮
- 后端仍保留校验，返回 `selected_doc_ids is required`

### 9.2 模板类型错误

若前端传入非法 `game_type`：

- 后端返回 `unsupported_game_type`

### 9.3 内容为空

若所选文档无法提取有效内容：

- 后端返回 `selected documents content is empty`

### 9.4 LLM 结构化失败

若两次 schema 校验都失败：

- 后端返回 `game_generation_invalid_schema`
- 前端提示“小游戏生成失败，请更换文档或稍后重试”

### 9.5 HTML 丢失

若课程资料中的 `html_url` 已失效或底层文件不存在：

- 预览区显示“页面资源不存在”
- 不自动删除课程资料记录
- 允许用户重新生成新的小游戏

## 10. 测试设计

### 10.1 后端单测

建议新增：

- `tests/chat/test_knowledge_base_direct_game_service_v2.py`
- `tests/chat/test_routes_v2_game.py` 或并入 `test_routes_v2.py`

至少覆盖以下场景：

1. 未传 `selected_doc_ids` 时返回错误
2. 未传或传错 `game_type` 时返回错误
3. `category_sort` 生成成功时返回 `artifact_type = game`
4. `drag_match` 生成成功时能写出 `html_url`
5. `memory_flip` 首次 schema 校验失败、修复后成功
6. 二次失败时返回明确错误
7. 课程资料持久化写入 `material_type = game`

### 10.2 前端单测

建议新增：

- `tests/frontend/studioPanel.game-entry.test.ts`
- `tests/frontend/gameArtifactPreview.test.ts`

至少覆盖以下场景：

1. 工作台展示“小游戏生成”入口卡片
2. 点击入口后打开 `GameEntryModal`
3. 选中文件前不能提交
4. 提交成功后能把返回结果加入 `generatedFiles`
5. `viewingFile.type === 'game'` 时进入游戏预览组件
6. “全屏播放”按钮使用 `htmlUrl` 打开独立页面
7. 课程资料中的 `game` 类型可以恢复为可预览文件

## 11. 实施顺序

建议按以下顺序实施：

1. 后端先完成模板注册表、生成服务、HTML 托管接口与路由接线
2. 后端补齐响应 schema 与课程资料持久化
3. 前端补齐类型定义与响应解析
4. 前端新增 `GameEntryModal`
5. 前端新增 `GameArtifactPreview`
6. 在 `StudioPanel` 中接入生成入口、提交流程与预览切换
7. 完成课程资料回显与测试

## 12. 设计结论

首版“知识库小游戏生成”功能采用一条独立的 `game` 直出链路：

1. 教师在工作台勾选知识库文档
2. 选择 3 个小游戏之一
3. 后端基于所选模板 schema 生成结构化游戏数据
4. 后端注入本地 HTML 模板并产出独立小游戏页面
5. 工作台内通过 iframe 预览
6. 点击“全屏播放”直接打开该独立 HTML 页面
7. 同时将小游戏作为正式课程资料保存，支持后续再次打开

该方案满足了“工作台内预览 + 独立播放 + 课程资料沉淀”的产品目标，同时避免了首版引入编辑器、推荐系统和播放器壳层等未被确认的复杂度，适合作为最小可用版本推进实现。
