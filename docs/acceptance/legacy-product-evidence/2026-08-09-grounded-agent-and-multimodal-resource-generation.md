# 教师端可信 Agent 与多模态资源生成验收记录

> 日期：2026-08-09  
> 当前状态：教师端自动化与本机真实端到端验收完成；八类非 PPT 资源全部通过
> SPEC：`docs/superpowers/specs/2026-08-09-grounded-agent-and-multimodal-resource-generation-design.md`  
> 计划：`docs/superpowers/plans/2026-08-09-grounded-agent-and-multimodal-resource-generation.md`

## 1. 验收环境

| 项目 | 实际值 |
|---|---|
| 工作区 | `D:\github\edu_ai` |
| 项目目录 | `D:\github\edu_ai\Edu_AI` |
| 分支 | `main`（用户明确要求直接执行） |
| 前端 | React 18 / TypeScript / Vite / Playwright |
| 后端 | FastAPI / Python / pytest |
| 初始工作区 | 存在用户尚未提交的专业课程知识库改动；验收不得重置这些改动 |

## 2. 已确认范围

- [x] 教师端为本阶段唯一产品范围。
- [x] PPT 后置，不计入本阶段八类资源通过率。
- [x] 学生端后置。
- [x] Agent 目标是可靠调用基础 RAG、Web 和资源工具，不追求高自治。
- [x] 图文采用“先大纲和图片需求、再找图、再带图写正文”的链路。
- [x] 验收必须包含自动化 E2E 和真实服务冒烟，两者分别记录。

## 3. 初始缺陷基线

| 编号 | 现象 | 初步根因 | 修复状态 |
|---|---|---|---|
| B-001 | 勾选文档后计划先回答、后检索，实际未调用 RAG | planner 只补工具不重排；executor 受当前 step 限制且 final 无证据门禁 | 已修复 |
| B-002 | 资源弹窗默认使用全部课程资料 | GenerationFactory 初始 source 固定为 `course_auto`，未读取左侧选中 | 已修复 |
| B-003 | course_auto 解析可能拼接全部 ready 文档 | resolver 通过 `read_many` 直接形成 context | 已修复 |
| B-004 | 直接生成端点可能依赖 preflight 鉴权 | 前端预检和真正写入为两个独立请求 | 已修复 |
| B-005 | 报告图像为后插，其他资源没有公共图文链路 | 缺少 Visual Brief、候选质量和正文前图片锁定 | 已修复 |
| B-006 | 思维导图缺少完整生成到编辑验收 | graph/mind_map 命名与资源预览链路未完全闭合 | 已修复 |
| B-007 | 资源中心只有管理动作，没有内容编辑 | 缺少按类型校验的内容 PATCH 与简洁编辑器 | 已修复 |

## 4. Agent 工具验收矩阵

| 场景 | 预期来源 | 必须调用 | 顺序/门禁 | 自动化 | 真实冒烟 |
|---|---|---|---|---|---|
| 选中文档 + RAG | selected_documents | rag_search | RAG 成功且有证据后回答 | 通过 | 通过；检索先于回答，5 条证据，约 134.8 秒完成 |
| 无选中文档 + RAG | course_auto | rag_search | 全课程相关检索后回答 | 通过 | 通过；无图片搜索绕行，5 条证据，约 91.4 秒完成 |
| Web | none/独立 | web_search | Web 有证据后回答 | 通过 | 通过；10 条来源，约 7.6 秒完成 |
| RAG + Web | selected/course_auto | rag_search + web_search | 两者都完成后回答 | 通过 | 通过；两个工具并行启动，合计 11 条来源，约 94.3 秒完成 |
| 不启用工具 | none | 无 | 允许直接回答 | 通过 | 不要求 |
| 检索报错 | 任一必需来源 | 对应工具 | 禁止知识性 final，显示失败 | 通过 | 环境待验 |
| 零证据 | 任一必需来源 | 对应工具 | 禁止伪装引用，显示证据不足 | 通过 | 环境待验 |
| 资源意图 | 按用户选择 | 对应生成工具/端点 | 形成 job、material、preview | 通过 | 通过；八类非 PPT 资源均有真实 job 与可见 material |

种子事实验收方法：在指定测试文档中写入不可能由模型常识猜出的唯一事实；selected 与 course_auto 输出必须含该事实和文档来源，none 模式不得引用该文档或声称来自知识库。

## 5. 资源端到端矩阵

| 资源 | 配置有效 | 来源有效 | 任务成功 | 落库 | 预览 | 编辑 | 导出 | 图文 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 教学报告 | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 | Markdown 通过 | 通过 |
| 教案 | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 | Markdown 通过 | 通过 |
| 教学博客 | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 | Markdown 通过 | 通过 |
| 习题 | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 | JSON 通过 | 可用 |
| 闪卡 | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 | JSON 通过 | 可用 |
| 思维导图 | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 | JSON 通过 | 可用 |
| 课堂小游戏 | 通过 | 通过 | 通过 | 通过 | 通过 | 不开放任意 HTML | 现有安全格式 | 可用 |
| AI 课堂 | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 | 现有格式通过 | 通过 |
| PPT | 后置 | 后置 | 后置 | 后置 | 仅回归 | 后置 | 后置 | 后置 |

### 5.1 本机真实资源生成记录

以下任务均使用教师账号、课程 `computational-thinking`、左侧已选个人知识文档和 `selected_documents` 来源；判定通过要求任务终态为 `succeeded`、存在 `result_ref`，且结果在“我的资源”查询中可见。

| 资源 | 真实任务 | 落库资源 | 结果 | 实测备注 |
|---|---|---|---|---|
| 教学报告 | `job_d57b9e2b957b4b92` | `report-a580a6926b4c9506` | 通过 | 开启图文，约 177.8 秒；4 个 Visual Brief 槽位均选中安全本地图片并全部进入正文；主模型欠费后自动切到可用备用通道 |
| 教案 | `job_b60b3faff8d74a31` | `lesson_plan-7af6ee026fac8b73` | 通过 | 开启图文，约 134.8 秒；修复大纲确认协议后正文正常落库 |
| 教学博客 | `job_a5a973db36a746cb` | `job_a5a973db36a746cb` | 通过 | 开启图文，约 285 秒；完成大纲、章节、正文与保存 |
| 习题 | `job_a404074cf093498b` | `quiz-93cb3fb51322261e` | 通过 | 5 题，答案与解析配置生效 |
| 闪卡 | `job_74c9cd2911614d78` | `flashcard-1ea270828139beb1` | 通过 | 10 张卡片并保留来源 |
| 思维导图 | `job_b311dfffa8b84011` | `graph-f4ec3cb248b05c11` | 通过 | 三层结构并成功落库 |
| 课堂小游戏 | `job_63999b08a7f849d1` | `game-6fed72f2d86a9bbb` | 通过 | 拖拽匹配游戏可保存 |
| AI 课堂 | `job_29b57681878c4762` | `ETlMz1D9DA` | 通过 | 开启图文，6 场景，约 1042.6 秒，最终资源可见 |

## 6. 图文链路验收

- [x] Visual Brief 包含稳定 slot、所属章节、图片目的、检索词和偏好类型。
- [x] 知识库图片严格受 selected/course scope 限制。
- [x] 网页结果保留原图地址、来源页面和题注信息；最终只使用安全本地化地址。
- [x] 下载器拒绝非 HTTP(S)、内网/保留地址、危险重定向、错误 MIME、超大文件和低质量图片。
- [x] 候选完成内容哈希去重、来源偏好、分辨率和可注入相关性评分排序。
- [x] 正文模型只收到已锁定图片，不自行伪造 URL。
- [x] 最终正文中的图片、题注、来源与 selected visual 一一对应。
- [x] 没有合格图片时资源仍可完成，并记录空槽原因。

## 7. 权限与隔离验收

- [x] 直接生成端点不经过 preflight 也会校验课程生成权限。
- [x] selected_doc_ids 中的文档必须属于当前课程，或属于当前教师的个人知识库，并且可用于检索；跨用户个人文档和跨课程文档均被拒绝。
- [x] 资源内容保存校验教师的课程编辑权限和个人资源所有权。
- [x] 不能通过 material ID 修改另一课程资源。
- [x] 游戏编辑不接受任意 HTML；图片下载不能访问内网。

## 8. 执行记录

每次只记录实际运行结果，不预填通过。

| 时间 | 命令/动作 | 结果 | 证据或备注 |
|---|---|---|---|
| 2026-08-09 | 检查分支与工作区 | 完成 | `main`；存在用户知识库改动，已记录保护约束 |
| 2026-08-09 | 读取 Superpowers `writing-plans`、`executing-plans`、`test-driven-development` | 完成 | 文档、执行和测试先行规则已纳入计划 |
| 2026-08-09 | 后端关键链路回归 | 通过 | 181 passed、2 deselected；覆盖 Agent、来源、图文、资源、权限和课堂 |
| 2026-08-09 | 前端全量单元测试 | 通过 | 216 passed，0 failed |
| 2026-08-09 | Playwright 教师端 E2E | 通过 | desktop1366 + compact1024 共 18 passed |
| 2026-08-09 | 前端生产构建 | 通过 | 5541 modules transformed；仅原有 chunk 体积提示 |
| 2026-08-09 | ESLint | 通过 | 0 errors；72 个仓库既有 warnings |
| 2026-08-09 | Python 编译 | 通过 | `compileall src/app` |
| 2026-08-09 | 后端全量套件 | 通过 | 最终回归 1270 passed、2 skipped、0 failed、0 errors；包含新增故障转移、教案协议和个人文档来源测试 |
| 2026-08-09 | 真实冒烟工具自测 | 通过 | 6 passed；Agent 五种工具矩阵与八类非 PPT 资源矩阵均可预览，真实执行要求显式 `--execute` |
| 2026-08-09 | 本机配置与模型可用性核查 | 完成 | 教师令牌、博查/Tavily 与多模型令牌均存在；阿里云主通道真实调用返回 `Arrearage`，OpenRouter 与 DeepSeek 最小调用通过；已实现主配置优先的自动故障转移 |
| 2026-08-09 | Agent 本机真实工具矩阵 | 通过 | selected RAG、course_auto RAG、Web、RAG+Web 均从 `/api/chat/v2/stream` 完成；检索严格先于最终回答 |
| 2026-08-09 | 八类非 PPT 资源本机真实 E2E | 通过 | 全部使用同一已选知识文档；8/8 任务成功、有结果引用且在“我的资源”可见；PPT 按范围后置 |
| 2026-08-09 | 额外五视口并发压力跑 | 非阻断观察 | 41 passed；desktop1920 在 6 worker 同时 reload 时 4 项因 DOM 替换点击超时；目标 1366/1024 改为 1 worker 后 18/18 通过 |
| 2026-08-09 | 新增生产文件占位扫描 | 通过 | `TODO|PLACEHOLDER|待补|假数据` 无命中 |
| 2026-08-09 | `git diff --check` | 通过 | 无空白错误；CRLF 提示不影响内容 |
| 2026-08-09 | Agent 对话资源工具矩阵 | 通过 | 报告、教案、练习题、博客、闪卡、思维导图、课堂小游戏、AI 课堂均经真实对话调用对应工具并最终落库；PPT 延期 |
| 2026-08-09 | Web→报告重规划与 grounding | 通过 | 确认轮严格为 `web_search → generate_report`；10 条来源进入 Job 快照和最终材料，`retrieval_context_used=true` |
| 2026-08-09 | RAG 优先级复验 | 通过 | selected 与 course_auto 均真实调用 `rag_search`；检索步骤固定为计划第一步，非标准计划动作不能绕过 |
| 2026-08-09 | Agent AI 课堂真实 E2E | 通过 | `job_c5479be4afb34ea8` → `FmWASHm287`；约 13 分钟，任务中心持续显示场景进度 |
| 2026-08-09 | Agent 工具扩展后最终全量回归 | 通过 | 1280 passed、2 skipped、0 failed；2 条既有弃用 warning |

## 9. 最终回归命令

本次实际执行的可复验命令：

```powershell
cd api
$env:PYTHONPATH='src'
python -m pytest -q
python -m compileall src/app src/scripts/smoke_teacher_agent_tools.py src/scripts/smoke_teacher_generation.py src/scripts/teacher_smoke_common.py -q
python src/scripts/smoke_teacher_agent_tools.py --course-id <课程ID>
python src/scripts/smoke_teacher_generation.py --course-id <课程ID> --source-mode none
python src/scripts/smoke_teacher_agent_generation.py --course-id <课程ID>
# 部署环境真实执行：先设置 EDU_AI_SMOKE_TOKEN，再显式增加 --execute；Web 冒烟另加 --include-web
cd ..
pnpm test
pnpm lint
pnpm build
pnpm exec playwright test tests/e2e/generation-factory-shell.spec.ts tests/e2e/generation-text-resources.spec.ts tests/e2e/generation-practice-resources.spec.ts tests/e2e/generation-visual-resources.spec.ts tests/e2e/resources-and-classroom.spec.ts --project=desktop1366 --project=compact1024
git diff --check
```

## 10. 最终签收

- [x] SPEC 的全部实现项有对应自动化证据。
- [x] 本次新增/修改功能的自动化测试通过。
- [x] 真实服务冒烟已完成；本机令牌和博查配置存在，Agent Web 与图文资源链路已有真实成功记录。
- [x] 八类非 PPT 资源端到端矩阵没有“待”。
- [x] 没有遗留假按钮、静默降级或把未检索回答标成已检索。
- [x] 用户原有工作区改动完整保留。
- [x] 当前限制、后续 PPT 与学生端工作清晰列出。

## 11. 剩余限制与明早人工验收重点

1. 人工抽查已生成的报告、博客、教案和 AI 课堂图片题注、来源页与本地图片地址是否符合教学预期；自动化与真实任务已验证链路和落库，不替代内容审美判断。
2. 关注性能：selected/course_auto RAG 约 86—131 秒，博客约 285 秒，6 场景 AI 课堂约 17 分钟；功能已通过，但进度提示和耗时仍需后续优化。
3. 阿里云主模型账户当前返回欠费；系统会自动使用本机已配置且实测可用的 OpenRouter/DeepSeek 通道。若希望固定使用阿里云，需要在供应商侧恢复账户状态。
4. PPT 只做现有能力回归，不作为本阶段签收阻断；学生端不在本次范围。
5. 人工验收重点检查任务中心、个人资源、预览、编辑与发布交互是否符合使用习惯；真实 E2E 已生成可直接抽查的八类资源 ID，见 5.1。
6. Agent 能力、真实 Job/材料证据及后续优化优先级见 `docs/acceptance/2026-08-09-agent-capability-status.md`。
