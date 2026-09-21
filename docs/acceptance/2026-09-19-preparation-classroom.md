# E：准备课堂分镜、渲染与交接

状态：E 的受控生成、恢复与播放器组件验证已实现；真实备课、全部模块合并后的计量结算、图片/TTS 服务、生产浏览器验收尚未完成。不能把下面的测试夹具称为真实备课产物。

共同基线：`18080783`（G 已发布的审查/鲁棒性基线）。分支：`feat/preparation-classroom-20260919`；目录：`.worktrees/preparation-classroom-20260919`。实现提交 `cc234811`，接口/审阅/兼容修复提交 `21195202`；证据提交见该分支日志。未改原工作区、其他模块代码或数据库。

## 基线事实

原始 [full-summary.json](artifacts/2026-09-19-preparation-agent-audit/full-summary.json) 的两份真实课堂分别为 5 页/10 个 text/5 个 speech 和 6 页/12 个 text/6 个 speech。末页投屏和旁白直接给出检查题答案；其中一份把“能独立说清楚”直接表述为已掌握。该样本仅完成后端交付，明确没有浏览器播放证据。本次保留历史记录，不追改旧样本质量结论。

## 实现与参数追踪

| 来源 | 消费者与结果 | 验证范围 |
| --- | --- | --- |
| A 的 `teaching_context` | 按原对象传入 `classroom_write`、D 内容审阅及独立映射审阅；不反解析 focus | 网关协议测试；真实参数对照由 G 运行 |
| `requirements[].requirement_id` | 场景候选定位；必须覆盖本节点全部要求，最终逐绑定独立审阅 | 未知 ID、缺失审阅覆盖和语义拒绝会失败 |
| `objective_ids` | `objective_bindings` 定位到 scene/action；测验另有 `question_bindings` 保留题目 ID | 本节点集合校验和审阅后定位回读 |
| 分镜 `purpose/screen/narration/student_action/feedback` | purpose 映射为 slide 或 quiz；screen 实际投屏；步骤逐个 spotlight/speech；answer/on_submit 映射到测验提交按钮 | 对调场景后投屏/讲解顺序同步改变；组件实际作答 |
| `steps` | 受控形状、箭头和文本构成有序过程，聚光指向真实元素 | 示例为 add(12,30)→42→回传→回答；不使用随机图片 |
| `node_budget_minutes` | 作为整节点背景传入；不复制为每份课堂时长 | 9 页测试仍合法；整节点聚合约束归 F |
| `resource_target_minutes` | 非空时才约束单课堂估计时长 | 超限拒绝；默认 null 不自动分配 |
| `estimated_seconds` | 汇总学习用时，包含观察/作答；正文修订后变为 unknown | media_duration 单独标 unknown，无字符数冒充音频实测 |
| `spec_digest/context_digest/content_digest` | 私有候选恢复、最终元数据和审阅绑定 | 任一摘要篡改均阻断；格式失败恢复不重新写正文 |

新分镜有 24 页安全上限，可通过服务端 `classroom_options.max_scenes` 下调；这不是每份课堂的目标页数。写作/场景修复输出预算 12,000，遵守 B 的接口上限。v1 缺版本规格保留旧文字脚本恢复，不伪造 v2 上下文或重算持久化规格摘要；旧资源播放契约未迁移。新能力仅由 v2 上下文进入。

## 原生播放器支持表

| 能力 | 当前播放器 | E 新路径 |
| --- | --- | --- |
| slide、text、shape | `SlidePlayer` / `@openmaic/renderer` | 使用，固定画布和受控 SVG 路径 |
| speech、spotlight、laser | `ActionEngine`；音频→浏览器语音→阅读停顿 | 使用 speech/spotlight；文本不等于音频 |
| quiz 单选/多选/简答 | `QuizScenePlayer` | 首批输出单选；提交后显示答案/解析；刷新和重答复用原生行为 |
| interactive/widget、视频、图表等 | 播放器存在部分支持 | E 未接入，不生成未验证字段 |
| 外部图片 | 画布支持，但需真实授权资产与可达回执 | 未装配；明确要求时 `CLASSROOM_REQUIRED_MEDIA_UNAVAILABLE` |
| 预合成 TTS | 旧服务存在 | 未装配受计量媒体工具；必需配音明确失败，不静默使用浏览器语音替代 |
| 音频失效 | 旁白变化必须清除旧地址 | 提供摘要/URL/实测时长回执校验与失效工具；没有真实音频监听验收 |

画布检查覆盖有限数值、边界、基础字号、空文字/空画布、类型、素材回执、stage/scene/action/element 引用和测验答案引用。字符长度不能证明排版溢出；`browser_layout`、`audio_listening` 默认 `not_checked`。有必要的图片或配音失败进入结构化失败；不是降级成功。

D 审阅返回的结构问题允许一次指定场景重建，经 `classroom_repair` 生成受限分镜；其余场景保持不变，再次独立审阅完整候选。D 审阅内部拒绝而未返回候选的内容故障由 F 恢复，不声称 E 已覆盖 D 内部所有修复路径。

## 实际验证

后端：59 passed，0 failed，0 skipped。禁用 dotenv 自动加载，不使用业务库。命令：

```bash
COURSE_PREPARATION_ENABLED=false PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python - <<'PY'
import dotenv, pytest
dotenv.load_dotenv = lambda *a, **k: False
raise SystemExit(pytest.main([
 'backend/src/tests/course_preparation/test_native_classroom.py',
 'backend/src/tests/course_preparation/test_classroom_teaching_contract.py',
 'backend/src/tests/course_preparation/test_classroom_render_checks.py',
 'backend/src/tests/test_classroom_validation.py',
 'backend/src/tests/services/test_classroom_visual_planning.py', '-q', '-ra']))
PY
```

`native_classroom` 保证 v1 原生映射；新 teaching_contract/render_checks 覆盖 E 路径。`classroom_validation` 是共享结构验证；`classroom_visual_planning` 仅覆盖旧视觉入口，不代表新图片链路通过。写作、D 审阅和映射审阅的模型响应使用测试替身；取消、超时、格式恢复验证 E 边界，预算结清必须由 B/F 集成验收。

前端现有回归：23 passed，0 failed，0 skipped，包含 actionEngine、quizScene、QuizScenePlayer、classroomScene、ClassroomSceneRenderer。Node `22.23.2`，使用项目已有依赖。这些包含纯函数/源代码断言，不能单独证明页面播放。

```bash
cd frontend
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/node --import tsx --test \
  src/openmaic/actionEngine.test.ts src/openmaic/quizScene.test.ts \
  src/openmaic/QuizScenePlayer.test.ts src/openmaic/classroomScene.test.ts \
  src/openmaic/ClassroomSceneRenderer.test.ts
```

实际 Chromium 组件验证：桌面 1440×1000 和窄屏 390×844，两组通过，页面错误 0。打开三页、执行实际阅读计时播放至完成、提交前答案不可见、作答后答案与解析可见、刷新恢复、重新作答再次隐藏答案。使用原生 React 组件与确定性夹具；禁用浏览器 speechSynthesis 后验证静默阅读播放，未监听音频、未访问模型/业务后端。夹具版本 `classroom-e-contract-fixture-v1`，内容摘要见 [fixture-metadata.json](artifacts/2026-09-19-preparation-classroom/fixture-metadata.json)。截图、trace、运行脚本见 [组件证据目录](artifacts/2026-09-19-preparation-classroom/)。

截图人工检查：桌面流程图和测验内容可显示，窄屏测验可以作答；**窄屏流程图随 1000 单位画布缩小，文字偏小**，需要 G 的缩放/适配策略与可读性验收。这两组 passed 仅指脚本的行为断言，不代表所有窄屏阅读质量达标。

组件复现：把证据目录的 `index.html`、`player-harness.tsx`、`classroom.fixture.json` 复制到当前 worktree 的临时 `frontend/.classroom-e/`，使用已安装依赖，在 frontend 目录启动 `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5189 --strictPort`，再运行证据目录的 `verify_component.py`。这些临时前端文件不纳入产品；验证后删除。

另外只读加载 D 当时工作源码的 `verified_resource`，确认 E 的最终教学映射和独立审阅摘要通过其回读校验；模型回执仍为测试替身，不能称为最终共同提交的集成测试。

## B / D / F / G 交接

- B：注册 `generate-ai-classroom` Skill 到 classroom_write/classroom_repair，使用根 Harness gateway 调用 E；E 内部显式 scope，不修改同一共享 gateway。将 F 的授权 `checkpoint=` 传入。缺 B 接口不直连旧模型。
- A：提供 v2 teaching_context 和持久化 spec_digest；目标/要求 ID 复用共享 Identifier，不额外限制为 ASCII。v1 继续兼容恢复，不能当作新功能产物。
- D：`review_classroom(..., checkpoint=None)` 返回真实逐场景/逐 speech 回执。E 使用独立 resource_review 调用审阅候选需求/目标映射，返回 `preparation_checks` 和最终 `preparation_sha256`。课堂共享 locator 仅 scene/action，题目 ID 单列 question_bindings，兼容 D resolver。
- F：存在 `generation_failures.py` 时 E 的 ClassroomFailure 直接继承 F.GenerationFailure；无 F 的契约测试基线仅保留同形 detail。保留 code/phase/category/retry_scope，不归一成无原因失败；终端 owner/lease/预算/取消检查继续在 F/B。候选外层 review_state 保留 storyboard/context/估算摘要，D 内层 state 使用 review 键，恢复不得覆盖外层。
- G：在最终合并 SHA 上真实生成一份课堂，记录资源 ID、版本、最终摘要与所有 completion/Skill usage。以本证据的三个页面行为作为预期，而不是复用本夹具声称真实生成成功。要求两种顺序、活动/基础/偏好优先级、禁止来源、故障结清的真实参数对照。真实播放需打开每页、检查图形和排版、观察动作推进、作答后反馈、刷新回读，保存桌面/窄屏截图与 trace。

尚未完成：真实备课到播放器的生产闭环；受计量的真实图片/TTS 工具及其取消/慢响应/结算测试；音频 URL 实际解码、实测时长采集和人工抽听；F 的最终交付/故障恢复集成。以上项目保持模块完成门槛未勾选，没有部署或修改其他窗口状态。
