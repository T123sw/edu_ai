# Stitch 课程资料教学视频展示设计

## 背景

当前根据 PPT 生成教学视频的工作台链路已经具备以下能力：

- 教师工作台可以创建教学视频任务，并将视频素材以 `material_type=video` 持久化到课程资料。
- 工作台右侧文件列表里已经能出现教学视频条目。
- 后端课程资料接口 `/api/courses/{course_id}/materials` 已经会返回视频材料，材料内容中包含 `content.video_url`、`generation_state.status` 等字段。

但这条链路还缺一段前端落地能力：

- 教师工作台点击右侧教学视频文件时，当前仍然走本地预览逻辑，而不是进入课程资料。
- `stitch` 的课程资料页 [CourseResources.tsx](/d:/Edu_AI_1/Edu_AI/src/stitch/pages/CourseResources.tsx) 目前默认按 Markdown 资料展示，不支持视频详情分支。
- `stitch` 路由层当前会把 `#resources` 直接重定向到 `#video`，导致课程资料页本身并未真正承接展示入口，[App.tsx](/d:/Edu_AI_1/Edu_AI/src/stitch/App.tsx:35)。

本次目标是打通“工作台文件列表 -> stitch 课程资料 -> 教学视频播放”的最小闭环。

## 目标

1. 教学视频生成成功后，点击教师工作台右侧文件列表中的该视频，直接跳转到 `stitch` 课程资料页。
2. `stitch` 课程资料页能根据跳转参数自动定位到对应教学视频材料。
3. `stitch` 课程资料页在右侧详情区直接播放该视频，而不是继续走 Markdown 预览。
4. 未完成或失败的教学视频仍留在工作台侧提示状态，不进行跳转。

## 非目标

- 不改造教师端真实业务页 [CourseMaterialsPage.tsx](/d:/Edu_AI_1/Edu_AI/src/pages/teacher/CourseMaterialsPage.tsx)。
- 不改造独立的 [VideoPlayer.tsx](/d:/Edu_AI_1/Edu_AI/src/stitch/pages/VideoPlayer.tsx)。
- 不补“课程资料页自动轮询生成中视频直至完成”。
- 不处理聊天主系统中的视频工作流入口。
- 不处理工作台右侧视频本地预览体验，后续如仍需保留再单独设计。

## 方案比较

### 方案 A：工作台直接跳转到 stitch 课程资料页，并通过 hash 查询参数传递 `courseId` / `materialId`

优点：

- 改动集中在工作台点击行为、stitch 路由和课程资料页三个位置。
- 参数可见、可复制、可刷新，便于调试。
- 不要求教师工作台和 stitch 共用运行时状态。

缺点：

- 需要 stitch 页面自己恢复课程上下文。

### 方案 B：工作台通过 `localStorage` 写入“目标视频”，stitch 页面自行读取

优点：

- 实现更快。

缺点：

- 状态不可见且容易残留。
- 多标签页和回退行为容易混乱。

### 方案 C：直接让教师工作台内部承接视频播放，不跳转到课程资料

优点：

- 交互路径更短。

缺点：

- 不符合本次“在课程资源中展示出来”的目标。
- 会继续绑定工作台预览分支，而不是课程资料体系。

## 选定方案

采用方案 A。

核心思路：

- 教师工作台在点击“已完成”的教学视频文件时，不再打开工作台内预览，而是跳转到 `stitch` 的 `resources` 路由。
- 跳转链接使用 `#resources?courseId=<courseId>&materialId=<materialId>`。
- `stitch` 课程资料页读取这两个参数，按 `courseId` 拉取课程资料，并优先选中 `materialId` 对应的视频材料。
- 当选中材料是 `material_type=video` 时，右侧详情区渲染 HTML `<video>` 播放器和视频元数据，而不是 Markdown。

## 详细设计

### 1. 恢复 stitch `resources` 路由

当前 `stitch` 路由解析逻辑会把 `routes.resources` 强制重定向到 `routes.video`，导致课程资料页不可直达。

本次需要：

- 在 [App.tsx](/d:/Edu_AI_1/Edu_AI/src/stitch/App.tsx) 中正式注册 `CourseResourcesPage`。
- 删除或调整 `getCurrentRoute()` 中对 `routes.resources` 的硬编码跳转。
- 保持 `#resources?...` 这类带查询参数的 hash 能被正确识别为 `resources` 路由。

预期结果：

- `#resources`
- `#resources?courseId=...`
- `#resources?courseId=...&materialId=...`

都能进入课程资料页本身，而不是被转去视频页。

### 2. 工作台点击行为

工作台右侧文件列表位于 [StudioPanel.tsx](/d:/Edu_AI_1/Edu_AI/src/components/teacher/StudioPanel.tsx)。

当前行为是：

- 点击文件项统一执行 `setViewingFile(item)`。

本次改造：

- 如果 `item.type !== 'video'`，维持现状。
- 如果 `item.type === 'video'`：
  - 读取 `item.meta.generationState.status`
  - 读取 `item.id` 作为 `materialId`
  - 使用当前工作台 `courseId`

行为规则：

- `status === 'completed'` 且存在 `courseId` 时：
  - 不再打开工作台预览
  - 直接跳转到 `#resources?courseId=<courseId>&materialId=<item.id>`
- `status === 'processing'` 时：
  - 保持当前提示“生成中”
  - 不跳转
- `status === 'failed'` 时：
  - 保持当前失败提示
  - 不跳转

这样可以把“播放”职责转交给课程资料页，同时保留未完成状态的工作台反馈。

### 3. stitch 课程资料页参数解析

`stitch` 课程资料页位于 [CourseResources.tsx](/d:/Edu_AI_1/Edu_AI/src/stitch/pages/CourseResources.tsx)。

本次增加一个轻量参数解析层：

- 从 `window.location.hash` 读取查询字符串
- 识别两个参数：
  - `courseId`
  - `materialId`

使用策略：

- 若存在 `courseId`，优先按该值拉取课程资料，而不是只依赖 `useAppShell().selectedCourse`
- 若存在 `materialId`，在资料加载完成后优先选中该材料
- 若 `materialId` 不存在或无匹配项，则回退到现有默认逻辑：选中第一个可用材料

### 4. stitch 课程上下文恢复

`stitch` 当前课程上下文依赖 `AppShell` 中的 `selectedCourse`，并持久化到 `localStorage('stitch-course')`。

教师工作台无法可靠构造完整的 `CourseSummary`，因此本次由 stitch 目标页自行恢复上下文。

策略如下：

- 当路由参数中存在 `courseId` 且与当前 `selectedCourse?.id` 不一致时：
  - 调用 stitch 课程接口读取后端课程详情
  - 将后端课程信息转换成 `CourseSummary`
  - 调用 `setSelectedCourse`，同步 stitch 当前课程上下文

这样可以保证：

- 页面标题、侧边栏上下文、资源请求都和跳转目标课程一致
- 不需要教师工作台知道 stitch 内部课程对象结构

### 5. 视频材料详情渲染

当前 `CourseResources` 右侧详情统一走 `courseMaterialToMarkdown(material)`，这对视频材料不适用。

本次为 `material_type === 'video'` 增加专门详情分支。

渲染内容：

- 标题：`material.title || material.material_id`
- 类型标识：`video`
- 状态文案：
  - 从 `material.generation_state.status` 推导
  - 优先展示 `completed`
- 视频播放器：
  - `src = material.content.video_url`
  - 使用原生 `<video controls preload="metadata">`
- 辅助信息：
  - `material.summary` 若存在则展示
  - `video_url` 可作为只读文本或外链按钮展示

回退规则：

- 若视频材料没有 `content.video_url`：
  - 不渲染播放器
  - 渲染“视频地址暂不可用”的占位说明

### 6. 左侧资源列表展示

`CourseResources` 左侧当前已经按 `material_type` 分组，不需要新增数据结构。

本次只需补齐以下内容：

- `typeLabels` 中加入 `video`
- 视频材料列表项的摘要文案：
  - 有 `summary` 时展示 `summary`
  - 否则展示固定描述，如“点击查看教学视频播放”

这样左侧列表能自然出现一个 `video` 分组，并承接跳转后自动选中的视频。

## 数据契约

本次依赖后端课程资料接口继续返回当前视频材料结构：

```json
{
  "material_type": "video",
  "material_id": "teaching_video__course_task_001",
  "title": "TCP 三次握手-教学视频.mp4",
  "content": {
    "task_id": "course_task_001",
    "video_url": "http://127.0.0.1:8008/api/v1/offline/download/course_task_001.mp4"
  },
  "generation_state": {
    "status": "completed",
    "phase": "completed",
    "message": "教学视频生成完成"
  }
}
```

本次不新增后端接口，也不修改现有视频材料 schema。

## 错误处理

### 工作台侧

- 无 `courseId`：继续提示“请先进入具体课程”
- 视频未完成：提示“生成中”或“生成失败”，不跳转
- 视频缺失 `item.id`：提示“视频资源缺少标识，暂时无法跳转”

### stitch 课程资料页

- `courseId` 无效：显示课程资料加载失败
- `materialId` 无匹配：正常打开课程资料页并回退到默认材料
- 视频 `video_url` 为空：显示不可播放占位，不报页面级错误

## 测试策略

### 前端单元/文本测试

1. `StudioPanel`
   - 已完成视频点击时生成 `#resources?...` 跳转，而不是 `setViewingFile`
   - 生成中视频点击时不跳转
   - 失败视频点击时不跳转

2. `stitch/App`
   - `#resources`
   - `#resources?courseId=...&materialId=...`
   均能识别为 `resources` 路由，不再重定向到 `video`

3. `CourseResources`
   - 能解析 hash 中的 `courseId` / `materialId`
   - `material_type=video` 时渲染 `<video>`
   - `materialId` 缺失或无匹配时回退到默认材料

### 手工验证

1. 在教师工作台生成一个教学视频并等待完成
2. 点击右侧文件列表中的该视频
3. 页面跳转到 `stitch` 课程资料页
4. 目标课程上下文正确
5. 左侧 `video` 分组可见
6. 右侧详情区自动选中该视频并开始可播放

## 影响文件

- [StudioPanel.tsx](/d:/Edu_AI_1/Edu_AI/src/components/teacher/StudioPanel.tsx)
- [App.tsx](/d:/Edu_AI_1/Edu_AI/src/stitch/App.tsx)
- [CourseResources.tsx](/d:/Edu_AI_1/Edu_AI/src/stitch/pages/CourseResources.tsx)
- [courses.ts](/d:/Edu_AI_1/Edu_AI/src/stitch/api/courses.ts)
- [types.ts](/d:/Edu_AI_1/Edu_AI/src/stitch/api/types.ts)

## 实施边界

本次只交付“工作台跳转 + stitch 课程资料视频展示”。

后续如果要继续完善，可另起需求处理：

- 教学视频生成中的课程资料页自动刷新
- stitch 独立视频播放页与课程资料打通
- 教师端真实业务页课程资料的视频展示
- 工作台内视频预览是否保留为备用入口
