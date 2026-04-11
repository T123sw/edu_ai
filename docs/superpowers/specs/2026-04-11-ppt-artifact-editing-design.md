# PPT 产物引用编辑设计

日期：2026-04-11

## 1. 概要

本设计为已生成的 PPT 增加一条“引用后继续修改”的稳定链路。

目标体验：

- 右侧 PPT 预览页在现有 `全屏预览 / 查看结构 / 导出 PPT` 按钮旁增加 `添加到对话`
- 用户点击后，当前 PPT 成为对话中的活动引用产物
- 后续用户输入默认被理解为“对当前 PPT 的修改意见”
- 系统优先识别目标页并调用 `html2ppt` 的 revision 接口执行单页修订
- 修订完成后生成一个新的 PPT 版本，进入右侧生成物区和课程资源区
- 当前会话中的活动引用自动切换到最新版本，支持连续多轮修改

这条链路不应把整份 PPT 内容塞回输入框，也不应退化成“整份重新生成”的普通聊天。

## 2. 背景与现状

当前仓库已经具备三块可复用能力：

1. 前端已有“报告添加到对话”模式  
右侧预览页支持将报告正文或大纲设置为 `artifact_reference`，聊天请求会附带该结构化引用。

2. 对话状态已支持 PPT 类型引用  
`artifact_reference.artifact_type` 已支持：
- `ppt_outline`
- `ppt_content_markdown`
- `ppt_deck`

3. `html2ppt` 已支持 revision  
Node 侧 PPT 引擎已经暴露：
- `POST /ppt/jobs/{job_id}/revisions`
- `GET /ppt/jobs/{job_id}/revisions/{revision_id}`

但当前系统仍缺少两层连接：

- 前端资格判断仍只允许 `report` 触发“添加到对话”
- 后端 `reply_service_v2` 仅接了 `ReportEditRuntime`，没有 `PptEditRuntime`

因此现在产品层面还不能真正基于当前 PPT 发起修订。

## 3. 目标

- 为 `ppt_deck` 预览界面增加“添加到对话”能力
- 让聊天后端在引用 PPT 时优先进入 PPT 编辑链路
- 首版支持“单页修订”这一最小可用能力
- 修订结果产出新的 `ppt_deck` 版本，不覆盖旧版本
- 新版本保持与现有 PPT 预览、课程资源持久化、会话状态恢复兼容
- 复用现有 `html2ppt revision` 能力，而不是重造一套 PPT 编辑引擎

## 4. 非目标

- 首版不支持一次修改多页
- 首版不支持直接编辑任意外部上传的 `.pptx`
- 首版不做“整份 PPT 智能重构”的独立路径
- 首版不做幻灯片级可视化 diff
- 首版不要求支持“围绕 PPT 问答”和“围绕 PPT 编辑”并存的复杂路由
- 首版不做页面内精确框选元素级编辑，只处理单页内容重写

## 5. 用户请求重述

用户希望在当前 PPT 预览界面顶部按钮区增加一个与报告预览相同的“添加到对话”入口。

点击后：

- 当前 PPT 被显式引用到聊天上下文
- 后续用户输入应优先被解释为对该 PPT 的修改意见
- 这些修改意见需要接入到现有 `html2ppt` 接口，真正驱动 PPT 生成新版本

用户已经确认以下策略：

- 优先自动识别页码或目标页
- 如果无法确定，再向用户追问
- 不直接退回整份 PPT 重新生成

## 6. 方案对比

### 方案 A：只加前端按钮，不做后端编辑运行时

做法：

- 前端允许 PPT 加入 `artifact_reference`
- 后端仍走普通聊天 / 现有 PPT workflow

优点：

- 改动最少
- 很快能看到 UI 入口

缺点：

- 无法真正修改 PPT
- 用户点击后体验与预期不一致
- 会形成“看起来支持，实际上不支持”的误导

### 方案 B：新增 `PptEditRuntime`，走显式引用编辑链路

做法：

- 前端复用报告的“添加到对话”交互
- 后端新增 PPT 专用编辑运行时
- 将用户输入标准化为 `revision request`
- 调用 `html2ppt` revision 接口

优点：

- 与现有报告编辑模式一致
- 能最大化复用现有 `artifact_reference`、会话状态、PPT 预览和 html2ppt revision
- 边界清晰，易于测试和后续增强

缺点：

- 需要新增一层意图解析与修订编排逻辑
- 需要补齐 html2ppt Python 客户端 revision 能力

### 方案 C：收到修改意见后整份 PPT 重新生成

做法：

- 不走 revision
- 直接基于原大纲或 markdown 重跑整份生成

优点：

- 后端实现简单

缺点：

- 与用户“修改当前 PPT”的心智不一致
- 延迟更高
- 难以做连续局部编辑
- 浪费现有 revision 能力

## 7. 推荐方案

采用 **方案 B：显式引用 + `PptEditRuntime` + html2ppt revision**。

推荐理由：

- 它最符合当前产品已有架构
- 它满足“添加到对话后继续改当前 PPT”的真实需求
- 它可以严格收敛为“单页 revision”这一最小范围，避免首版做大
- 它保留了后续扩展空间，例如：
  - 改多页
  - 基于当前页标题自动匹配
  - 围绕 PPT 问答

## 8. 用户体验设计

### 8.1 入口位置

在 `ppt_deck` 预览界面顶部按钮组中增加：

- `添加到对话`
- 保持与现有按钮并列展示

推荐顺序：

- `添加到对话`
- `全屏预览`
- `查看结构`
- `导出 PPT`

说明：

- 该按钮只在 `ppt_deck` 场景显示
- `ppt_outline` 与 `ppt_content_markdown` 首版不单独暴露添加入口
- 这样可以避免用户引用“中间态”产物后又期待直接改最终 PPT

### 8.2 点击后的行为

点击 `添加到对话` 后：

- 将当前 `ppt_deck` 写入全局 `artifactReference`
- 引用类型为 `ppt_deck`
- 引用元数据至少包含：
  - `artifact_id`
  - `artifact_type`
  - `title`
  - `source_conversation_id`
  - `source_course_id`

聊天区行为：

- 输入区上方展示当前引用卡片
- 卡片文案应明确为“正在编辑当前 PPT”
- 用户输入框内容保持为空
- 发送后该引用不会自动清除

### 8.3 聊天解释规则

当会话中存在 `ppt_deck` 引用时：

- 后续输入优先解释为“对当前 PPT 的修改请求”
- 若输入明显是普通闲聊，可后续再扩展回退逻辑
- 首版不主动支持“围绕当前 PPT 问答”，而是聚焦“编辑”

### 8.4 修改结果呈现

修订完成后：

- 右侧生成物区域追加一个新的 PPT 版本
- 预览区切换到最新版本
- 课程资源区同步更新最新版本
- 当前 `artifact_reference` 自动更新为新版本

用户可继续输入：

- “把第 5 页改得更简洁一些”
- “把刚才那页改成三栏对比”

这类连续操作都应基于最新 revision 执行。

## 9. 功能边界

### 9.1 支持的输入类型

首版支持：

- 明确页码修改  
  例：
  - “把第 3 页改成流程图风格”
  - “第七页增加一个案例”

- 基于页标题的定位  
  例：
  - “把‘工具调用的实现架构与流程’那一页改成左右结构”

- 当前 deck 的局部重写  
  例：
  - “这一页太密了，压缩一点”
  - “这一页改得更适合课堂讲解”

### 9.2 不支持的输入类型

首版不支持：

- “帮我把整份 PPT 重写一遍”
- “第 2、4、6 页一起修改”
- “把字体改成 xx、所有页脚统一调整”
- “把我电脑里的另一个 pptx 合并进来”

对这些请求，系统应明确提示当前能力边界。

## 10. 目标页识别策略

首版采用“能自动识别就自动识别，识别不稳就追问”的策略。

### 10.1 识别优先级

优先级从高到低：

1. 显式页码
2. 页标题精确匹配
3. 页标题模糊匹配
4. 当前预览页或最近一次修改页
5. 无法确定时追问

### 10.2 显式页码识别

支持识别：

- `第3页`
- `第三页`
- `3页`
- `P3`
- `page 3`

识别到后直接映射到 `target_slides = [3]`。

### 10.3 页标题匹配

匹配来源：

- deck 的 manifest
- 或 outline 中的 slide title

策略：

- 先做大小写和空白归一
- 先精确包含匹配
- 再做简化后的模糊匹配

若唯一命中，则直接选中该页。

### 10.4 “这一页 / 刚才那页”处理

首版建议使用两种来源：

- 当前会话中最近激活的 `ppt_deck` 预览页  
- 最近一次成功 revision 的页码

若这两个来源都没有，就不要猜，直接追问。

### 10.5 追问规则

以下场景必须追问：

- 未识别到页码，且无法唯一匹配标题
- 匹配到多个候选页
- 用户请求明显超出单页边界

追问文案应尽量短，例如：

- “请说明要修改第几页。”
- “我匹配到多页候选，请明确页码或页标题。”

## 11. 后端架构设计

### 11.1 总体思路

在现有 `ReportEditRuntime` 模式旁新增 `PptEditRuntime`。

当 `reply_service_v2` 收到 `artifact_reference` 时：

- 若类型为 `report` 或 `report_outline`，继续走 `ReportEditRuntime`
- 若类型为 `ppt_deck`，进入 `PptEditRuntime`
- 若类型为其他 PPT 中间产物，首版可拒绝并提示“请引用最终 PPT 再修改”

### 11.2 新增组件

建议新增：

- `app/chat/workflows/ppt/edit_runtime.py`
- `app/chat/orchestrator/ppt_edit_intent_parser.py`

必要时补充：

- `app/chat/domain/ppt_artifact_reference.py`  
  如果现有 `ArtifactReferencePayload` 已够用，则不单独新增

### 11.3 `PptEditRuntime` 职责

`PptEditRuntime` 负责：

- 解析 `artifact_reference`
- 读取被引用的源 PPT 产物
- 从 deck 内容中提取 `job_id`、`revision_id`、`manifest_url`、`slide_count`
- 解析用户意图，标准化出 `edit_request`
- 识别目标页
- 调用 html2ppt revision 接口
- 轮询 revision 状态
- 组装新的 `ppt_deck` artifact
- 返回统一的聊天响应结构

它不负责：

- 重新规划整份 PPT 大纲
- 直接编辑任意外部 pptx
- 管理前端当前预览页 UI 状态

## 12. 数据模型设计

### 12.1 `PptArtifactEditRequest`

建议标准化结构：

- `artifact_reference`
- `action_type`
- `instruction`
- `target_slide_index`
- `target_slide_title`
- `candidate_slide_indexes`
- `needs_disambiguation`
- `reason`

其中：

- `action_type` 首版统一收敛为 `revise_slide`
- `instruction` 为去掉页码后的核心修改指令
- `target_slide_index` 为最终唯一目标页

### 12.2 引用源 artifact 要求

进入 revision 的源 artifact 必须是 `ppt_deck`，并具备：

- `content.job_id`
- `content.revision_id`
- `content.manifest_url` 或可推导 manifest 信息

缺失这些字段时，运行时应直接返回错误提示，而不是进入修订。

### 12.3 新 deck artifact 形态

新版本仍沿用现有 `ppt_deck` artifact 结构：

- `artifact_id`
- `artifact_type = "ppt_deck"`
- `title`
- `content`
- `generation_state`

其中 `content` 至少包含：

- `job_id`
- `revision_id`
- `theme_id`
- `slide_count`
- `html_full_url`
- `pptx_url`
- `manifest_url`

### 12.4 版本元信息

建议为 PPT 也补充轻量版本关系：

- `root_artifact_id`
- `parent_artifact_id`
- `version_id`
- `version_number`
- `derived_from_action = "artifact_edit"`

若首版不做完整版本树，也应至少保留：

- `parent_artifact_id`
- `version_number`

这样后续能补齐“基于 v2 修改出 v3”的追溯能力。

## 13. html2ppt 接口设计

### 13.1 Python 客户端扩展

当前 `Html2PptClient` 只有：

- `create_job`
- `get_job_status`
- `get_job_results`

需要新增：

- `create_revision(job_id, payload)`
- `get_revision_status(job_id, revision_id)`

### 13.2 revision 请求体

首版固定为：

- `mode = "single_slide"`
- `target_slides = [目标页码]`
- `user_instruction = 用户修改意见`

可选补充：

- `updated_content`  
  首版可以不传，只依赖 `user_instruction`

首版建议保守处理：

- 默认只传 `user_instruction`
- 待后续需要更高控制力时，再引入更复杂的 `updated_content` 生成

### 13.3 revision 执行流程

后端调用顺序：

1. 从源 `ppt_deck` 中拿到 `job_id`
2. 构造 revision 请求
3. `POST /ppt/jobs/{job_id}/revisions`
4. 拿到 `revision_id`
5. 轮询 `GET /ppt/jobs/{job_id}/revisions/{revision_id}`
6. 若 revision 成功，再调用 `GET /ppt/jobs/{job_id}/results`

说明：

现有 results 接口返回的是“最新成功 revision”结果，因此 revision 成功后读取 job results 即可得到最新 deck 产物。

## 14. 运行时流程

### 14.1 成功路径

1. 用户在 PPT 预览页点击 `添加到对话`
2. 前端设置 `artifactReference = ppt_deck`
3. 用户输入修改意见并发送
4. `/api/chat/v2/reply` 收到 `artifact_reference`
5. `ReplyServiceV2` 路由到 `PptEditRuntime`
6. 运行时解析目标页与修改指令
7. 调用 html2ppt revision
8. revision 成功后拉取最新 results
9. 组装新的 `ppt_deck` artifact
10. 会话状态与课程资源同步更新
11. 前端显示最新版本并继续保持引用

### 14.2 无法定位页码路径

1. 用户发送模糊修改意见
2. 系统无法唯一确定目标页
3. `PptEditRuntime` 返回 `awaiting_input`
4. 助手提示用户补充页码或页标题
5. 本次不提交 revision

### 14.3 revision 失败路径

1. html2ppt revision 接口失败或超时
2. 返回失败消息
3. 保持当前引用不变
4. 不生成假版本

## 15. 前端设计细节

### 15.1 `isArtifactReferenceEligible`

当前该判断只允许 `report`。

需要改为允许：

- `report`
- `ppt`

但按钮展示仍应结合 `meta.kind` 决定：

- 报告：继续保持当前行为
- PPT：仅 `meta.kind === "ppt_deck"` 时展示

### 15.2 `handleAddToChat`

需要根据文件类型分支生成引用：

报告维持现状。

PPT 新增：

- `artifact_type = "ppt_deck"`
- `artifact_id` 使用原始 artifact id
- `title` 使用当前 deck 标题
- `source_conversation_id` 与 `source_course_id` 沿用现有逻辑

### 15.3 聊天区恢复

当前 `ChatPanel` 从会话状态恢复引用时，仍只按报告类型恢复。

需要扩展为同时识别：

- `ppt_outline`
- `ppt_content_markdown`
- `ppt_deck`

首版实际可只允许恢复 `ppt_deck` 的编辑态。

### 15.4 连续编辑的引用更新

每次返回新的 `ppt_deck` artifact 后：

- 前端需要把新的 artifact 放到生成文件列表
- 如果当前会话存在 `ppt_deck` 引用，且本次响应是 PPT 编辑结果，应自动将引用更新到新 artifact

## 16. 后端设计细节

### 16.1 `ReplyServiceV2`

当前逻辑是：

- 有 `artifact_reference` 时直接进入 `ReportEditRuntime`

需要改成按类型分发：

- `report`, `report_outline` -> `ReportEditRuntime`
- `ppt_deck` -> `PptEditRuntime`
- 其他 -> 返回能力范围提示

### 16.2 源 artifact 查找

`PptEditRuntime.run_from_request(...)` 应优先从以下位置寻找源 artifact：

1. 课程资源持久化
2. 当前会话 `workflow_state.artifacts`

与 `ReportEditRuntime` 保持一致。

### 16.3 edit intent parser

建议新增一个轻量 parser，而不是一开始就上复杂 LLM：

首版优先规则解析：

- 提取页码
- 提取标题引号内容或关键标题片段
- 剩余文本作为 `instruction`

当规则不足时再做有限 LLM 辅助，但不作为首版必需前提。

### 16.4 revision 轮询

轮询逻辑可复用现有 PPT job 轮询风格，但对象改为 revision：

- 状态：`queued / running / succeeded / failed`
- 超时后返回明确错误

### 16.5 返回协议

返回结构保持现有聊天协议：

- `message`
- `conversation`
- `action`
- `workflow`
- `artifacts`
- `sources`
- `trace`

建议：

- `action.name = "ppt.edit"`
- `workflow.type = "ppt"`
- `workflow.status = "completed" | "failed" | "awaiting_input"`

## 17. 错误处理

### 17.1 引用无效

场景：

- `artifact_reference` 缺失
- artifact 不是 `ppt_deck`
- 找不到对应源 artifact

处理：

- 返回明确错误提示
- 不进入 revision

### 17.2 缺少 job 上下文

场景：

- deck artifact 缺少 `job_id`
- deck artifact 缺少最新 `revision_id`

处理：

- 返回“当前 PPT 缺少可修订上下文，请重新生成后再修改”

### 17.3 目标页不存在

场景：

- 用户指定页码超出范围

处理：

- 返回“目标页不存在，请输入 1 到 N 之间的页码”

### 17.4 html2ppt 不可用

场景：

- 本地服务未启动
- revision 请求失败

处理：

- 返回与现有 PPT 生成一致的引擎不可用提示

## 18. 测试设计

### 18.1 前端测试

需要覆盖：

- `ppt_deck` 预览页显示 `添加到对话`
- `ppt_outline` / `ppt_content_markdown` 不显示该按钮
- 点击按钮后 store 中写入 `artifactReference`
- 会话详情恢复时能正确恢复 `ppt_deck` 引用
- PPT 编辑返回新 artifact 后，引用能切换到最新版本

### 18.2 后端单元测试

需要覆盖：

- `Html2PptClient` 新增 revision 请求方法
- `ReplyServiceV2` 按引用类型分发到 `PptEditRuntime`
- `PptEditRuntime` 能从 deck artifact 中提取 `job_id`
- 显式页码识别成功
- 标题匹配成功
- 无法匹配时返回 `awaiting_input`
- html2ppt revision 失败时返回失败结果

### 18.3 集成测试

需要覆盖：

- 带 `ppt_deck` 引用的 `/api/chat/v2/reply` 请求
- 成功返回新 `ppt_deck` artifact
- 会话状态中 `active_artifact`、`artifact_reference`、`workflow_state` 正确更新
- 课程资源持久化保存最新 PPT 版本

## 19. 分阶段实施建议

### Phase 1

- 前端按钮接入
- `artifact_reference` 恢复与展示
- `PptEditRuntime`
- `Html2PptClient` revision 能力
- 显式页码识别
- revision 成功后新版本 artifact 回填

### Phase 2

- 标题模糊匹配优化
- “这一页 / 刚才那页”基于 UI 状态定位
- 更好的版本关系展示

### Phase 3

- `updated_content` 自动生成
- 多页 revision
- 围绕 PPT 问答与编辑并存

## 20. 关键取舍

### 20.1 为什么首版只支持 `ppt_deck`

因为真正可修订的执行上下文在最终 deck 上，而不是中间大纲或 markdown 文稿。

先只允许引用 `ppt_deck`，能显著降低用户预期混乱和实现复杂度。

### 20.2 为什么首版不直接生成 `updated_content`

`html2ppt revision` 已允许只传 `user_instruction`。

这使首版可以先打通链路，再逐步提高修订控制力。

### 20.3 为什么不直接整份重生

用户要的是“修改当前 PPT”，不是“重新做一份新的 PPT”。

revision 保持了更自然的连续编辑心智，也更节约计算资源。

## 21. 文件影响范围

前端主要涉及：

- `Edu_AI/src/components/teacher/StudioPanel.tsx`
- `Edu_AI/src/components/teacher/ChatPanel.tsx`
- `Edu_AI/src/services/teacher/chatV2.ts`
- `Edu_AI/src/services/teacher/materials.helpers.ts`
- `Edu_AI/src/store/teacher/useStore.ts`

后端主要涉及：

- `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/html2ppt_client.py`
- `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/edit_runtime.py`
- `Edu_AI/api/Edu_AI/app/chat/orchestrator/ppt_edit_intent_parser.py`

测试主要涉及：

- `Edu_AI/api/Edu_AI/tests/chat/test_html2ppt_client.py`
- 新增 `test_ppt_edit_runtime.py`
- 前端 `StudioPanel` / `ChatPanel` / helper 测试

## 22. 验收标准

以下条件同时满足时，认为功能达成：

- 在最终 PPT 预览页能看到 `添加到对话`
- 点击后聊天请求会附带 `ppt_deck` 引用
- 用户输入“把第 3 页改成流程图风格”会触发 revision
- revision 成功后右侧出现新的 PPT 版本，并可预览和导出
- 后续继续输入时默认基于最新版本继续改
- 模糊请求在无法定位时会追问，而不是静默失败或乱改

