# AI Lecturer 主系统接入设计

## 1. 目标

本次接入的目标是把 `Edu_AI/api/Edu_AI/AI_Lecturer` 从“独立可运行模块”接入到当前教师主系统中，让教师可以直接在主系统的生成工厂里基于“已生成的 PPT + 对应 content.md”发起教学视频生成任务，而不需要再手工填写 markdown、图片目录或单独启动额外服务。

本次确认的目标如下：

1. 主系统启动时自动拉起 AI Lecturer 相关后端服务，至少保证离线教学视频链路可用。
2. 现有 PPT 生成链路继续保留，并补齐 `content.md` 的持久化能力，让课程材料中的 PPT 条目能稳定关联到对应讲稿内容。
3. 在教师工作台右侧生成工厂中新增“教学视频”入口。
4. 点击“教学视频”后，前端展示当前课程下可用的 PPT 列表，只允许选择已经生成出真实 PPT deck 的条目。
5. 选中 PPT 后，由主系统后端负责把 PPT 与其关联的 `content.md` 传给 AI Lecturer，启动教学视频生成任务并返回可轮询状态。
6. 视频生成结果要能在主系统中被查看和复用，而不是只停留在 AI Lecturer 的独立接口里。

## 2. 当前上下文

结合现有代码，当前主系统已经具备以下基础：

1. PPT 已通过 `app/chat/api/routes_v2.py` 下的 `/api/chat/v2/ppt/outline` 与 `/api/chat/v2/ppt/generate` 进入主系统工作流。
2. PPT 生成完成后会通过 `report_service_v2._persist_ppt_course_material()` 存入课程材料目录 `course_data/courses/<course_id>/generated_materials/ppts`。
3. 前端 `StudioPanel.tsx`、`CourseMaterialsPage.tsx`、`materials.helpers.ts` 已能把课程材料中的 `ppt` 条目恢复为可预览的产物。
4. `AI_Lecturer` 当前仍是独立 FastAPI 服务，默认由 `unified_gateway.py` 提供 `8008` 端口接口，并通过 `generate_full_video` 接口接受分页图片和文本大纲生成视频。
5. `src/stitch/pages/VideoPlayer.tsx` 仍是旧演示入口，需要手工输入 markdown 和图片目录，不应继续作为正式主系统接入点。

## 3. 当前问题

本次接入前存在以下关键问题：

1. 主系统启动流程没有托管 AI Lecturer，必须人工额外启动。
2. PPT 课程材料当前仅持久化了 deck 内容与 outline，没有稳定保存 `ppt_content_markdown`，导致刷新后无法可靠拿到 `content.md`。
3. AI Lecturer 现有离线接口要求前端传入分页图片路径与文本，和主系统课程材料模型不直接对齐。
4. 右侧生成工厂没有“教学视频”入口，也没有针对课程内已生成 PPT 的选择器。
5. 旧的 `VideoPlayer` 页面与当前教师工作台是两套心智模型，继续扩展会让正式链路和演示链路混淆。

## 4. 范围

### 4.1 本次范围

1. 为主系统增加 AI Lecturer 进程托管与健康检查能力。
2. 为 PPT 课程材料补齐 `content_markdown` 持久化字段。
3. 为主系统新增“教学视频桥接接口”，负责列出可用 PPT、触发任务、查询任务状态。
4. 在 `StudioPanel` 中增加“教学视频”按钮、PPT 列表弹窗与任务触发流程。
5. 将生成结果以主系统可消费的方式回写为 `video` 类型课程材料或至少形成稳定的课程内视频资源条目。
6. 为上述行为补充后端与前端回归测试。

### 4.2 不在本次范围

1. 不重构 AI Lecturer 的实时课堂 WebRTC 页面。
2. 不将旧 `stitch/pages/VideoPlayer.tsx` 改造成正式工作台入口。
3. 不重写现有 PPT 生成工作流本身，只补齐它的持久化字段与桥接能力。
4. 不处理 AI Lecturer 模块内部的模型推理算法或 Wav2Lip 逻辑。

## 5. 方案选项

### 方案 A：继续使用独立前端页面，前端直接调用 AI Lecturer

优点：

1. 改动最少。
2. 不需要主系统新增桥接接口。

缺点：

1. 正式主系统与旧演示页继续分裂。
2. 课程材料与 AI Lecturer 输入无法稳定对齐。
3. 前端仍要知道 AI Lecturer 的底层路径约束，耦合过高。

### 方案 B：主系统后端增加桥接层，前端只面向主系统

优点：

1. 前端只依赖主系统接口，职责边界清晰。
2. 主系统可以把 PPT、content.md、任务状态、课程材料统一建模。
3. 后续无论 AI Lecturer 继续独立部署还是改为内嵌服务，前端都不需要重写。

缺点：

1. 需要新增后端桥接模块与测试。
2. 需要补齐 PPT 材料的 `content_markdown` 存储。

### 方案 C：直接把 AI Lecturer 离线逻辑并入主系统业务代码

优点：

1. 外部依赖最少。

缺点：

1. 改动面过大。
2. 会把现有独立模块边界打散，风险最高。

### 推荐方案

采用方案 B。

原因：

1. 它最符合“接入主系统”而不是“旁挂一个演示页”的目标。
2. 它允许保留 AI Lecturer 独立模块现状，同时把教师使用路径统一到主系统。
3. 它只要求补齐课程材料的持久化字段和新增桥接接口，风险可控。

## 6. 架构设计

### 6.1 后端分层

后端新增一层 AI Lecturer bridge：

1. 进程托管层
   - 负责在主系统启动时按配置自动拉起 `AI_Lecturer/unified_gateway.py`。
   - 记录子进程句柄，支持健康检查与必要时关闭。
2. 课程材料适配层
   - 从课程材料中筛选出真正可用于教学视频的 `ppt` deck 条目。
   - 要求该条目同时具备 deck 内容和 `content_markdown`。
3. 任务桥接层
   - 接收“根据课程内 PPT 生成教学视频”的请求。
   - 解析 PPT 资源、提取或构造 AI Lecturer 所需的分页图片与内容输入。
   - 调用 AI Lecturer 离线任务接口。
4. 任务结果回写层
   - 将成功生成的视频回写为课程材料中的 `video` 条目，附带来源 PPT、任务 ID、视频 URL 和时间戳。

### 6.2 数据模型补充

现有 `ppt` 课程材料在保存时补充：

1. `content_markdown`
   - 来自 `ppt_content_markdown` artifact 的正文 markdown。
2. `outline`
   - 继续保留现有 outline。
3. `generation_state`
   - 继续保留 deck 的生成状态。

为了兼容已有前端恢复逻辑，deck 的 `content` 中也可镜像保存：

1. `content_markdown`
2. `source_outline`

这样课程材料刷新后，前端无需再依赖会话态 artifact 才能拿到讲稿。

### 6.3 新接口

主系统新增一组教学视频接口：

1. `GET /api/courses/{course_id}/teaching-videos/ppts`
   - 返回当前课程下可用的 PPT deck 列表，仅包含同时拥有 deck 与 `content_markdown` 的条目。
2. `POST /api/courses/{course_id}/teaching-videos`
   - 入参为选中的 `ppt_material_id`。
   - 后端负责定位 PPT、content markdown，并向 AI Lecturer 发起生成任务。
3. `GET /api/courses/{course_id}/teaching-videos/tasks/{task_id}`
   - 查询桥接任务状态；当 AI Lecturer 完成后返回主系统内的视频条目数据。
4. `GET /api/system/ai-lecturer/health`
   - 返回 AI Lecturer 可用性和启动状态，供前端判断按钮是否可用。

### 6.4 前端交互

`StudioPanel` 中新增“教学视频”卡片：

1. 点击后弹出选择框，不直接打开旧页面。
2. 弹窗中调用主系统 PPT 列表接口，展示：
   - 标题
   - 创建时间
   - 页数
   - 是否具备 content markdown
3. 用户选择后点击生成，触发主系统桥接接口。
4. 前端轮询桥接任务状态，成功后：
   - 将视频写入 `generatedFiles`
   - 可选择自动打开该视频预览
   - 课程材料刷新后可持续存在

## 7. 错误处理

需要覆盖以下失败场景：

1. AI Lecturer 未启动或启动失败
   - 返回明确错误，不让前端直接暴露底层连接异常。
2. PPT 条目缺少 `content_markdown`
   - 在 PPT 列表阶段直接过滤，或在创建任务时返回 400。
3. deck 缺少可导出资源
   - 返回“该 PPT 尚未生成完整产物，不能用于教学视频”。
4. AI Lecturer 任务失败
   - 任务状态显示 `failed`，保留错误信息。
5. 回写课程材料失败
   - 任务状态中显示成功生成但持久化失败，并记录日志。

## 8. 测试策略

### 8.1 后端

1. 测试 PPT 材料持久化时会带上 `content_markdown`。
2. 测试教学视频 PPT 列表接口只返回满足条件的 deck 条目。
3. 测试创建教学视频任务时会正确读取课程材料并调用 AI Lecturer 客户端。
4. 测试任务成功后会回写 `video` 材料。
5. 测试 AI Lecturer 进程托管在禁用/启用配置下的行为。

### 8.2 前端

1. 测试 `StudioPanel` 出现“教学视频”入口。
2. 测试点击后会请求可用 PPT 列表。
3. 测试选中 PPT 后会发起生成任务并轮询。
4. 测试成功后视频条目能加入右侧产物列表。

## 9. 成功标准

本次完成后，应满足：

1. 主系统启动后，AI Lecturer 离线能力可被自动托管。
2. 课程材料中的 PPT deck 可以稳定取回对应 `content.md`。
3. 教师在生成工厂中可以直接点击“教学视频”并选择现有 PPT。
4. 生成过程不依赖旧演示页，不要求手工输入 markdown 或图片目录。
5. 生成成功的视频能回到主系统课程材料与右侧产物区中持续可用。
