# AI 课堂课程资源学习记录设计

日期：2026-08-31

## 1. 背景

教师端已经能够按知识点生成并发布 AI 课堂等课程学习资源。学生在课程资源空间中可以自主学习这些资源，但当前学习域主要以教师发布的 `learning_task` 为中心，无法准确表达“学生自主学过某个课程资源”这一独立事实。

AI 课堂也不是单一 MP4。它由场景、讲解动作、白板或操作演示、嵌入媒体、习题和实时问答组成，不能使用视频当前位置或页面访问数直接判断学习完成。

本设计新增独立的“课程资源学习”领域，以 AI 课堂冻结版本的 `Scene -> Action -> LessonTimeline` 为计量基础，记录普通讲解播放、必答题作答和演示行为。教师任务可以引用同一资源版本的合格学习证据，但课程资源学习状态与教师任务状态始终独立。

## 2. 已确认的产品决策

1. 课程资源学习与教师发布的学习任务是两个独立领域，不共用进度记录。
2. 教师任务引用资源时，可以复用学生此前对同一资源版本产生的合格学习证据。
3. 普通讲解场景计入有效播放完整度，完成阈值为 80%。
4. 所有必答题必须至少提交一次；题目正确率不设置通过线，也不阻止资源完成。
5. 演示场景不进入播放完整度，只记录课堂学习行为。
6. 学生主动向 AI 提问属于学习行为；问答导致的暂停时间不进入播放完整度。
7. 不生成模糊的综合学习分。讲解完整度、习题进度、正确率和演示行为分别展示。
8. 可计算“已完成”的 AI 课堂版本必须至少包含一个普通讲解场景和一道必答题；否则只记录学习行为，不产生完成状态。

## 3. 目标与非目标

### 3.1 目标

- 为每名学生、每门课程、每个 AI 课堂资源版本建立独立学习进度。
- 基于真实播放过的普通讲解时间线区间计算完整度。
- 记录所有必答题的提交事实、答案结果、次数和知识点关联。
- 记录演示访问与交互，但不让演示行为改变完整度。
- 向学生和教师提供一致、可解释的资源学习状态。
- 允许教师任务按精确资源版本复用已有完成证据。
- 保证刷新、重新登录、服务重启和短暂断网后数据一致。

### 3.2 非目标

- 不把 AI 课堂资源习题升级为正式考试或成绩。
- 不设置资源习题正确率通过线。
- 不用停留时长推断知识掌握程度。
- 不把资源完成自动等同于教师任务完成。
- 不修改现有正式测评的版本、作答、评分和复核规则。
- 不建立高风险的摄像头、视线、键鼠监控或身份监考能力。

## 4. 领域边界

### 4.1 课程资源学习

课程资源学习描述学生对已发布资源版本的自主学习事实：

```text
student_id + course_id + resource_id + resource_version
  -> 普通讲解播放完整度
  -> 必答题作答进度与结果
  -> 演示学习行为
  -> 资源学习状态
```

该进度不依赖 `task_id`，也不写入现有以任务为中心的 `learning_events` 和 `learning_progress`。

### 4.2 教师任务

教师任务继续拥有自己的发布时间、截止时间、任务条件、正式测评、提交记录和完成状态。任务可以引用资源学习证据，但只消费一个不可变的证据引用：

```text
task_id
  -> resource_id + resource_version
  -> student resource-learning evidence
  -> 任务中的“资源条件是否满足”
```

资源显示“已完成”只表示任务的一项资源条件可能已经满足。任务是否完成仍由任务域依据自身全部条件独立判断。

### 4.3 正式测评

AI 课堂内的必答题只用于确认学生已经参与作答并形成学习反馈。现有 Assessment 域仍负责正式测评、成绩、通过、掌握、重做和教师复核。两个口径不得在 UI、API 或 Agent 中混用。

## 5. 资源版本学习清单

AI 课堂版本发布时，服务端冻结一份 `ResourceLearningManifest`。播放器和分析服务只消费该清单，不根据实时资源内容临时猜测场景类型。

每个场景标记为以下一种类型：

| 类型 | 含义 | 进入播放完整度 | 记录行为 |
| --- | --- | --- | --- |
| `explanation` | 普通语音讲解、逐步呈现、讲解型嵌入媒体 | 是 | 播放区间、进入、完成 |
| `exercise` | 选择、判断、填空或其他课堂习题 | 否 | 进入、提交、结果、次数 |
| `demo` | 白板演示、操作演示、非必看互动展示 | 否 | 进入、停留、交互、完成 |

学习清单至少包含：

- `manifest_id`
- `course_id`
- `resource_id`
- `resource_version`
- `content_hash`
- `scene_id`
- `scene_kind`
- `required_action_ids`
- `timeline_start_ms`
- `timeline_end_ms`
- `expected_duration_ms`
- `question_ids`
- `required_question_ids`
- `created_at`

普通讲解场景的标准时长由发布时编译的 `LessonTimeline` 确定。动态实时问答、学生等待和运行时中断不写入标准分母。

资源发布门禁应验证：

- 场景和 Action ID 稳定且唯一；
- 普通讲解场景能够编译出非负标准时长；
- 必答题 ID 稳定且题目可以提交；
- 场景分类完整；
- 内容哈希与资源版本一致。

如果没有普通讲解或没有必答题，该版本仍可发布和学习，但标记为 `behavior_only`，不产生“已完成”状态。

## 6. 播放完整度

### 6.1 计算公式

```text
explanation_coverage_percent
= union(学生已有效覆盖的 explanation 时间线区间).duration
  / sum(所有 explanation 场景 expected_duration_ms)
  * 100
```

计算结果限制在 0 至 100，并按展示需要四舍五入；服务端保存足够精度，完成判断使用未格式化数值。

### 6.2 有效播放规则

- 只有播放器处于正常播放状态且场景属于 `explanation` 时才产生有效区间。
- 暂停、等待、实时问答中断和播放器未运行的时间不累计。
- 跳转跨过的区间不累计。
- 重复播放区间通过区间并集去重，不重复累计。
- 演示和习题场景不进入分子或分母。
- 页面隐藏且播放器停止运行时不累计。
- 学生使用产品允许的播放速度时，以实际覆盖的内容时间线计算，不按墙钟时长惩罚。
- 不同会话可以共同补齐同一版本的覆盖区间。

### 6.3 播放事件

播放器至少产生：

```text
session_started
scene_entered
playback_started
timeline_heartbeat
playback_paused
scene_completed
session_ended
```

`timeline_heartbeat` 建议每 10 至 15 秒发送一次，并携带：

- `event_id`
- `session_id`
- `sequence_number`
- `resource_id`
- `resource_version`
- `scene_id`
- `timeline_from_ms`
- `timeline_to_ms`
- `client_monotonic_ms`
- `occurred_at`

客户端只上报播放事实，不上报百分比、场景类型、标准时长或完成状态。

### 6.4 服务端校验

- 会话必须属于认证学生和当前课程。
- 资源版本、场景和时间线范围必须存在于冻结清单。
- 事件序号必须满足单会话顺序约束。
- 单次区间跨度不能超过允许的心跳容差。
- 时间线终点不能超过场景标准长度。
- 重复 `event_id` 必须幂等返回，不重复累计。
- 同一学生、资源版本同一时间只接受一个有效播放会话；新会话开始时结束旧的有效会话。
- 无法验证的事件可以保留为一般访问行为，但不得进入有效覆盖区间。

## 7. 习题记录

### 7.1 完成规则

所有 `required_question_ids` 均至少存在一次有效 `submitted` 记录时，习题条件满足：

```text
question_completion_percent
= answered_required_question_count / required_question_count * 100
```

正确率不参与资源完成判断。即使全部答错，只要全部必答题已有效提交，习题条件仍满足。

### 7.2 作答事实

每次提交至少保存：

- `question_attempt_id`
- `student_id`
- `course_id`
- `resource_id`
- `resource_version`
- `question_id`
- `attempt_number`
- `answer_payload`
- `is_correct`
- `knowledge_point_ids`
- `submitted_at`

选择题、判断题必须提交稳定选项 ID；填空和主观输入必须满足题型的非空校验。重复作答全部保留，分析层分别计算首次答案、最后答案、首次正确率、最终正确率和作答次数。

答案与解析的揭示策略沿用资源本身配置；是否揭示不改变“已提交”事实。

## 8. 演示与实时问答行为

演示场景记录：

- `demo_entered`
- `demo_interacted`
- `demo_completed`
- 有效停留时长
- 交互 Action ID 与次数

这些数据用于描述学生是否接触过演示、哪些演示更常被使用以及学生在哪些位置产生互动，但永远不改变讲解完整度或资源完成状态。

学生主动提问记录为 `classroom_question_asked`，可以关联当时的资源版本、场景和时间线位置。问题正文遵循现有课堂问答隐私与保留策略；资源学习分析默认只展示提问次数，不在聚合页面暴露原文。

## 9. 资源学习状态

### 9.1 状态机

```text
not_started
  -> in_progress
  -> completed
```

- `not_started`：没有有效播放、必答题提交或演示行为。
- `in_progress`：已经产生任一学习事实，但尚未满足完成条件。
- `completed`：`explanation_coverage_percent >= 80` 且 `question_completion_percent = 100`。
- `behavior_only` 资源只在 `not_started` 与 `in_progress` 之间变化，不生成 `completed`。

同一资源版本一旦达到 `completed`，状态不回退，`completed_at` 首次写入后保持不变。资源内容、题目或场景分类变化必须创建新版本，新旧版本进度隔离。

### 9.2 不合成总分

学生端和教师端分别展示：

- 讲解完整度；
- 必答题已作答数/总数；
- 正确题数和正确率；
- 演示访问及交互；
- 资源状态。

不得将这些指标加权为一个无法解释的综合百分比。

## 10. 数据模型

### 10.1 `resource_learning_manifests`

- `manifest_id`
- `course_id`
- `resource_id`
- `resource_version`
- `content_hash`
- `mode`: `completable | behavior_only`
- `manifest_json`
- `created_at`

`course_id + resource_id + resource_version` 唯一，发布后不可变。

### 10.2 `resource_learning_sessions`

- `session_id`
- `course_id`
- `resource_id`
- `resource_version`
- `student_id`
- `status`: `active | ended | invalidated`
- `started_at`
- `last_heartbeat_at`
- `ended_at`
- `invalid_reason`

### 10.3 `resource_learning_events`

- `event_id`
- `session_id`
- `sequence_number`
- `event_type`
- `scene_id`
- `timeline_from_ms`
- `timeline_to_ms`
- `action_id`
- `occurred_at`
- `received_at`
- `validation_status`

`event_id` 全局唯一，`session_id + sequence_number` 唯一。

### 10.4 `resource_learning_coverage`

保存服务端已校验并合并的普通讲解覆盖区间：

- `student_id`
- `course_id`
- `resource_id`
- `resource_version`
- `scene_id`
- `covered_ranges_json`
- `covered_duration_ms`
- `updated_at`

### 10.5 `resource_question_attempts`

字段见第 7.2 节。`student_id + resource_id + resource_version + question_id + attempt_number` 唯一。

### 10.6 `resource_learning_progress`

- `student_id`
- `course_id`
- `resource_id`
- `resource_version`
- `status`
- `explanation_covered_ms`
- `explanation_total_ms`
- `explanation_coverage_percent`
- `required_question_count`
- `answered_question_count`
- `question_completion_percent`
- `correct_count_first`
- `correct_count_latest`
- `demo_view_count`
- `demo_interaction_count`
- `started_at`
- `completed_at`
- `last_activity_at`
- `updated_at`

主键为 `student_id + course_id + resource_id + resource_version`。

### 10.7 `task_resource_evidence_refs`

- `task_id`
- `student_id`
- `resource_id`
- `resource_version`
- `resource_progress_updated_at`
- `resource_completed_at`
- `condition_status`: `pending | satisfied`
- `linked_at`

该表只保存任务对资源学习证据的引用和条件投影，不复制或覆盖原始学习进度。

## 11. 服务组件与依赖方向

| 组件 | 单一职责 |
| --- | --- |
| `ResourceLearningManifestService` | 发布时分类场景、编译时间线并冻结学习清单 |
| `ResourceLearningSessionService` | 创建、续期、结束和校验学生学习会话 |
| `ResourcePlaybackEvidenceService` | 校验播放事件、合并覆盖区间 |
| `ResourceExerciseService` | 保存题目提交并计算作答统计 |
| `ResourceLearningProjectionService` | 计算学生资源进度和完成状态 |
| `ResourceLearningAnalyticsService` | 生成资源、学生、题目和知识点聚合 |
| `TaskResourceEvidenceAdapter` | 将同版本资源完成事实投影为任务资源条件 |

依赖方向保持为：

```text
AI课堂播放器 -> 资源学习事件接口 -> 资源学习服务与仓储
资源学习完成事实 -> TaskResourceEvidenceAdapter -> 任务条件投影
```

任务域不得反向修改资源学习原始记录。资源学习域也不得根据任务状态改变学生进度。

## 12. API 草案

学生资源学习：

```text
GET  /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/me
POST /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/sessions
POST /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/sessions/{session_id}/events:batch
POST /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/questions/{question_id}/attempts
POST /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/sessions/{session_id}/end
```

教师资源分析：

```text
GET /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/analytics
GET /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/students
GET /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/students/{student_id}
```

学生身份始终来自认证上下文。学生接口不得接受可覆盖的 `student_id`，也不得提供其他学生的进度。

## 13. 学生端设计

课程资源卡片和 AI 课堂播放器读取同一份 `resource_learning_progress`。

学习中示例：

```text
讲解完整度：68%
习题进度：2/3
当前状态：学习中
```

完成示例：

```text
讲解完整度：83%
习题进度：3/3
当前状态：已完成
完成时间：2026-08-31 15:20
```

播放器内分区展示：

- 讲解进度：有效播放完整度；
- 习题进度：已作答数量和学习反馈，不使用“通过/未通过”；
- 学习足迹：演示访问、交互和最近学习时间；
- 同步状态：已同步、同步中、待同步或同步失败。

## 14. 教师端设计

新增独立的“课程资源学习分析”，不放入教师任务完成率中。资源版本概览包含：

- 课程学生数；
- 已开始人数；
- 已完成人数及完成率；
- 平均讲解完整度；
- 必答题全部作答人数；
- 每题作答率、首次正确率、最终正确率和选项分布；
- 各知识点错误分布；
- 演示访问人数和交互次数；
- 最近学习时间。

学生明细队列：

- 未开始；
- 已开始但讲解不足 80%；
- 讲解已达标但习题未完成；
- 习题已完成但讲解未达标；
- 已完成。

任务页面只显示资源条件引用，例如：

```text
关联资源：进程调度 AI 课堂 v3
证据来源：课程资源自主学习
资源条件：已满足
证据完成时间：2026-08-30 20:15
任务状态：按任务其他条件独立判断
```

## 15. 任务证据复用

1. 教师发布任务时冻结引用的 `resource_id + resource_version`。
2. 对每名任务对象查询相同课程、学生和资源版本的学习进度。
3. 已经 `completed` 时立即将任务资源条件投影为 `satisfied`，不要求重新学习。
4. 尚未完成时保持 `pending`；资源稍后完成后通过内部幂等事件更新任务条件。
5. 不同资源版本之间不能复用完成证据。
6. 任务删除、关闭、重测或重新发布不修改资源学习记录。
7. 任务条件记录必须保留证据来源、资源版本和资源完成时间，避免只保存一个不可解释的布尔值。

## 16. 权限、隐私与安全

- 学生只能创建和读取本人的资源学习记录。
- 教师 owner/editor 只能查看本课程成员的资源分析。
- 客户端不能写入百分比、正确率、完成状态或 `completed_at`。
- 资源清单、标准时长和场景分类只能由受信发布流程生成。
- 日志不记录完整主观答案或课堂提问正文。
- 聚合指标不得使用学生 ID 作为公共监控标签。
- 原始事件保留时间应由平台数据策略配置；长期分析优先使用区间、计数和投影，而不是无限保留细粒度心跳。
- 服务端对批量事件接口执行大小、频率、时间跨度和序号限制。

## 17. 错误处理与降级

- 学习清单编译失败：该版本不得宣称支持完成度；发布页面明确提示修复或以 `behavior_only` 发布。
- 场景类型无法识别：记录一般访问行为，但不进入完整度。
- 心跳丢失：只计算可验证的连续区间，不根据最后位置补齐。
- 短暂断网：客户端按事件 ID 和序号缓存并补传；UI 显示“待同步”。
- 补传跨度超过服务端容差：保留访问行为，不进入有效覆盖。
- 重复事件：返回首次处理结果，不重复累计。
- 多设备并发：新有效会话结束旧会话；已持久化题目提交不丢失。
- 题目提交成功但进度投影失败：通过内部 outbox 或幂等重算恢复，不要求客户端伪造完成状态。
- 分析聚合失败：不影响播放器、题目提交和原始学习证据；教师页面局部降级并允许重试。
- 任务证据同步失败：资源完成事实保持不变，通过内部幂等事件重试任务条件投影。

## 18. 可观察性

建议新增：

- `resource_learning_session_started_total`
- `resource_learning_event_received_total{event_type,result}`
- `resource_learning_heartbeat_rejected_total{reason}`
- `resource_learning_question_submitted_total`
- `resource_learning_completed_total`
- `resource_learning_projection_lag_seconds`
- `task_resource_evidence_sync_total{result}`

审计记录至少包含资源学习清单冻结、版本切换、资源完成首次形成、人工作废异常会话以及任务证据引用建立。审计数据不保存完整答案正文。

## 19. 测试策略

### 19.1 单元测试

- 时间线区间合并、去重、边界和 80% 阈值。
- 跳转、暂停、重播、实时问答中断和页面隐藏规则。
- `demo` 与 `exercise` 场景不进入播放分母。
- 必答题全部提交的完成判断。
- 全部答错仍满足习题条件。
- 资源完成状态单调、不回退。
- `behavior_only` 资源不产生完成状态。

### 19.2 服务与仓储测试

- 会话认证、课程成员权限和跨课程拒绝。
- 事件 ID 与会话序号幂等。
- 超范围、超跨度和未知场景心跳拒绝。
- 多会话补齐覆盖区间和多设备并发规则。
- 资源版本进度隔离。
- 题目提交成功后的进度重算与失败恢复。
- 同版本任务证据复用和不同版本拒绝复用。
- 任务删除或关闭不影响资源学习数据。

### 19.3 前端测试

- 资源卡片和播放器显示相同进度。
- 学习中、已完成和待同步状态。
- 习题错误不显示为资源未通过。
- 演示行为展示与播放完整度隔离。
- 刷新和重新登录后的学习恢复。
- 教师资源分析与任务分析入口、文案和指标隔离。

### 19.4 真实端到端验收

1. 学生正常播放 80% 普通讲解并完成所有必答题，资源变为已完成。
2. 学生播放 100% 但少做一道必答题，资源保持学习中。
3. 学生所有题目答错但全部提交且播放达到 80%，资源仍为已完成。
4. 学生快速翻到最后一页，完整度不会变成 100%。
5. 学生重复播放同一区间，覆盖时长不重复累计。
6. 学生完整观看演示，演示行为有记录但播放完整度不增加。
7. 学生向 AI 提问导致播放暂停，问答时间不计入完整度。
8. 学生此前自主完成资源，后发布任务引用同一版本时复用证据。
9. 任务引用不同版本时不能复用旧版本证据。
10. 删除或关闭任务不影响课程资源学习记录。
11. 刷新、重新登录和服务重启后数据保持一致。
12. 学生修改请求试图写入完整度、正确率或完成状态时被拒绝。

## 20. 功能需求编号

| 编号 | 要求 |
| --- | --- |
| CRLT-FR-001 | 课程资源学习必须与教师任务进度独立保存 |
| CRLT-FR-002 | 必须按学生、课程、资源和资源版本聚合学习进度 |
| CRLT-FR-003 | 普通讲解完整度必须按有效时间线覆盖区间计算 |
| CRLT-FR-004 | 普通讲解完整度达到 80% 才满足播放条件 |
| CRLT-FR-005 | 所有必答题至少提交一次才满足习题条件 |
| CRLT-FR-006 | 正确率不得作为资源完成门槛 |
| CRLT-FR-007 | 演示只记录学习行为，不进入播放完整度 |
| CRLT-FR-008 | 资源完成必须同时满足播放条件和习题条件 |
| CRLT-FR-009 | 教师必须获得资源、学生、题目和知识点分析 |
| CRLT-FR-010 | 教师任务可以复用同一资源版本的既有完成证据 |
| CRLT-FR-011 | 不同资源版本不得复用完成证据 |
| CRLT-FR-012 | 学生端必须分别展示讲解、习题、演示和资源状态 |
| CRLT-NFR-001 | 客户端不得直接写入计算指标或完成状态 |
| CRLT-NFR-002 | 播放、题目和任务证据写入必须幂等 |
| CRLT-NFR-003 | 资源版本学习清单发布后不可变 |
| CRLT-NFR-004 | 刷新、重登和服务重启后学习事实必须一致 |
| CRLT-NFR-005 | 分析故障不得阻断学习和作答主链路 |
| CRLT-NFR-006 | 所有接口必须执行认证身份、课程和角色权限校验 |

## 21. 建议实施分片

1. **学习清单与基础数据模型**：场景分类、版本清单、会话、事件、覆盖区间和进度表。
2. **播放器证据采集**：时间线心跳、暂停/中断、断网缓存、服务端校验和 80% 投影。
3. **课堂习题与演示行为**：必答题提交、作答分析、演示事件和完成状态。
4. **双端展示与任务复用**：学生资源进度、教师资源分析、同版本任务证据适配。
5. **上线加固**：权限、幂等、恢复、可观察性、数据保留和真实端到端验收。

## 22. 完成定义

本能力只有在以下条件全部满足后才能宣称完成：

1. 课程资源学习与教师任务在数据、API、UI 和 Agent 文案中均明确分离。
2. 讲解完整度由服务端基于有效时间线区间计算，客户端无法伪造百分比。
3. 80% 普通讲解覆盖和全部必答题提交共同形成资源完成状态。
4. 正确率不阻止完成，演示行为不改变完整度。
5. 同版本历史学习证据可以被后发布任务复用，不同版本不能复用。
6. 学生和教师对同一资源版本看到一致的指标与状态。
7. 核心单元、服务、权限、恢复和真实端到端场景均有自动化证据。
8. 现有 AI 课堂播放、实时问答、正式测评、课程资源和教师任务主链路无 P0/P1 回归。
