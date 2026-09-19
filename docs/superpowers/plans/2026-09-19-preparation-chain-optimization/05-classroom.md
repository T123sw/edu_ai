# 窗口 E：AI 课堂生成与实际播放 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让已有课堂资源真正执行节点教学活动，改善过程展示与检查反馈，并用实际播放器验证有效性。

**Architecture:** 在现有课堂子任务内完成分镜、内容、渲染和审阅，不新增课程资源规划阶段。复用原生 OpenMAIC 数据契约及已有视觉/TTS 组件，所有新增模型调用接 B 的受计量 Harness 入口。

**Tech Stack:** Python、原生课堂场景/动作结构、现有 OpenMAIC/视觉/TTS 服务、浏览器播放器、pytest/Playwright。

**Spec:** [总计划](../2026-09-19-preparation-chain-optimization.md)、[共享契约](00-shared-contracts.md)、[真实课堂样本摘要](../../../acceptance/artifacts/2026-09-19-preparation-agent-audit/full-summary.json)。

## Global Constraints

- 先完成当前课堂参数贯通和可播放性，再扩大视觉能力；不以生成了更多页判定改进。
- 分镜属于单份课堂的制作步骤，不决定课程应该生成哪些资源。
- 不直接切到未计量的 sidecar 模型工作来绕过 B 的要求。外部图片、配音、互动不可用要明示，不能伪造地址或交互。
- 不在前端新增风格表单；不得把 speech 文本存在当作音频已播放。

## 文件范围与接口

- 修改：`backend/src/app/course_preparation/adapters/classroom.py`。
- 新建：准备专用 `classroom_storyboard.py`、`classroom_render_checks.py`、`skills/generate-ai-classroom/SKILL.md`。
- 复用/按需修改：`services/platform_task_handlers.py` 的视觉能力接口及课堂专用 `classroom_service.py`、`classroom_media.py`、`openmaic_tts_service.py`；保持原入口兼容。B 拥有生成 handler，G 拥有最终前端接入修改。
- 测试：`test_native_classroom.py`、新 `test_classroom_teaching_contract.py`、`test_classroom_render_checks.py`；浏览器生产验收交 G。
- 输出：原生 stage/scenes＋共享契约的目标定位/时长信息；`generate_classroom_draft(..., checkpoint=None)` 保持旧签名兼容。

## Task E1：分镜落实教学上下文

- [x] 以真实样本为基线：5/6 页全是文字框＋speech，最后一页直接展示答案。先固化这些事实，不将“结构合法”称为“视觉和互动已验收”。
- [x] 新建受限分镜结构，至少含 scene_id、objective_ids、教学用途、screen 内容、narration、学生动作、反馈方式和预计时长；这些字段必须有对应 renderer/播放行为，不能是无人消费的装饰参数。
- [ ] 使用 A 的学习活动、先修、基础、用户要求和偏好，由 B 的 classroom_write 生成分镜/内容。页数由可执行内容与节点约束决定，设合理配置上限，不把固定 2–6 页当所有节点的质量标准。
- [x] 稳定的程序映射参考：

```python
SCENE_PURPOSES = {'example', 'explanation', 'demonstration', 'practice', 'feedback'}

def assert_scene_plan(scene, known_objective_ids):
    assert scene['purpose'] in SCENE_PURPOSES
    assert set(scene['objective_ids']) <= set(known_objective_ids)
    assert scene['screen'] and scene['narration']
```

- [x] 上述 purpose 只是准备内部教案字段，不能直接当原生 OpenMAIC scene.type；renderer 必须映射到播放器已支持的类型。
- [x] 测试“先例后理”真的让例子先显示并先讲解；题目先出现、答案在明确反馈动作后出现，不能投屏已经给答案却要求独立作答。
- [ ] 调用 D 的 review_classroom 做独立事实与逐场景审阅；结构问题允许在受限范围重建对应场景，不沿用“只能换文字”来掩盖无法修复的结构缺陷。

## Task E2：必要视觉与媒体能力接入

- [x] 核对当前播放器真正支持的元素、动作和交互类型，记录支持表；无支持的字段不得仅写入 JSON 后声明功能完成。
- [x] 首批至少实现一种服务于理解的非纯文本表示，例如工具调用的有序流程图/参数校验分支图或代码步骤高亮。使用已支持元素，不依赖随机配图。
- [ ] 复用 C 的授权图片资产、已有视觉规划/检索组件时，所有视觉模型调用也经 B；副作用工具必须有真实回执、来源、超时和取消。若现有 sidecar 无法提供逐调用计量，先用已验证的受控渲染路径，不把它算作完整迁移。
- [x] 外部图片不可用时，只有不影响用户明确要求的装饰项可以降级，并记录 limitations；必需图示或明确配音失败必须进入 F 的故障处理。
- [ ] TTS 的输入绑定最终 narration digest；讲解变更后旧音频失效。记录实际音频时长与播放地址验证结果，不用字符数估算冒充 measured。
- [ ] 分别测试图片失败、TTS 失败、取消、慢响应、旁白修订导致音频失效，确保预算可结算、未审资源不交付。

## Task E3：渲染、时间和互动验收

- [x] 新增确定性画布检查：元素边界、文本容器、基础字号、缺失素材、悬空场景/动作引用。需要实际排版的溢出检查交浏览器执行，不能只凭字符长度判断。
- [ ] 测试分镜/旁白/图示指向同一个例子；成功/失败分支数据一致，交互题目标定位可回读。
- [x] 输出 duration 的 measured/estimated/unknown 口径和方法；有题目/停顿时区分媒体时长与学习用时。F 负责整节点总约束，不自行添加资源时间分配阶段。
- [x] 运行 native_classroom、classroom_validation、classroom_visual_planning 及新增测试；分别标明哪些只覆盖旧入口，哪些覆盖备课新路径。
- [ ] 将一份从真实备课产生的课堂交 G，实际打开每页、执行播放、触发题目到反馈、检查图片和音频加载，保存桌面及窄屏截图/trace。没有音频监听证据时不得声称配音验收通过。

## 完成门槛与交付记录

- [ ] 至少一个真实课堂体现节点活动与用户顺序，关键过程有可用视觉，检查不提前泄露答案，播放和交互均有证据。
- [ ] 图像/TTS/互动支持与未支持能力分别列明；所有模型调用经 B，所有失败能被 F 定位恢复。
- [ ] 提供给 G 的资源版本、渲染检查结果、浏览器步骤及预期表现；对比原课堂的具体变化，不给无依据的质量分数。


## E 实施记录（2026-09-19）

共同基线 `18080783`，分支 `feat/preparation-classroom-20260919`，实现提交 `cc234811`、接口对齐提交 `21195202`。完整状态、参数账本、支持表、命令和交接见 [E 验证与交接](../../../acceptance/2026-09-19-preparation-classroom.md)。

- 新路径已连接分镜→原生流程图/测验→D 独立内容审阅→受限结构修复→独立教学映射审阅；缺 A/B/D 接口会明确失败。模型调用使用 B 显式阶段入口；v1 兼容恢复不重算原摘要。
- 59 项后端测试、23 项既有播放器回归通过。桌面/窄屏各一次实际 Chromium 组件路径通过，截图和 trace 已保存。
- 上述组件证据使用确定性测试夹具；先例后理已验证渲染顺序与讲解顺序同步，真实模型的成对要求效果仍交 G；不得把组件测试当真实备课验收。
- 图片/TTS 明确必需但未装配时失败，默认不伪造媒体；摘要失效工具已测试，真实音频时长、地址/解码和监听未验收。预算结算与生产故障恢复依赖 B/F/G 集成。
- 窄屏流程图按比例缩小后文字偏小，G 需完成可读性/缩放适配验收；现有组件通过结果仅覆盖播放和作答行为。
- 完成门槛仍未勾选：没有把本夹具称为从真实备课交付的新资源，也没有宣布全链路完成。未修改其他窗口的文件或状态。
