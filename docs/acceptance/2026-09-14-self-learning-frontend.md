# 自主学习前端 V1：交互验收与交接

本次按用户授权完成前端样式及本地交互，不进行生成、爬取、模型问答或共享发布的真实接口联调。真实登录仍复用 `AuthContext` / `services/auth.ts`。

## 备份与版本

- 完整文件备份：`/home/zxqs_ep/project-backups/Edu_AI-before-frontend-20260914-8CzPNV/project`，包括原 `.git`、依赖、本地配置及未追踪文件。备份父目录权限为 700。
- 文件复制完成后使用只读校验比较源码和本地文件，无差异（校验排除依赖、Git 内部及编译缓存）。不包含外部运行中 PostgreSQL 的一致性快照；本轮未修改数据库。
- 独立 Git 历史包：同目录 `history.bundle`，`git bundle verify` 通过。
- 开发分支：`feat/self-learning-frontend-20260914`。
- 回退标签：`backup/pre-self-learning-frontend-20260914`，对应 `c7f28798`，包含用户原有需求文档修改。
- 旧界面代码保留在 `src/stitch`，`?legacy=1` 可直接打开；`#video-render` 和 `#player-smoke` 继续选择原入口。没有删除旧业务数据和用户已有 `.bak` 文件。

## 体验入口

在 `frontend` 执行 `EDU_AI_VITE_WATCH=1 pnpm dev --host 0.0.0.0 --port 5180`。

- 普通登录：`http://localhost:5180/`。
- 学生开发预览：`http://localhost:5180/?preview=student`。
- 教师开发预览：`http://localhost:5180/?preview=teacher`。
- 原版界面：`http://localhost:5180/?legacy=1`。

预览身份只在 Vite 开发环境可用，不写认证 token。生产构建已验证 `?preview=teacher` 仍显示登录页。

## 已交付流程

| 页面 | 交互与边界 |
| --- | --- |
| 首页 | 大输入框直接进入课堂；最近课堂续学；共享课堂创建个人学习副本；无单独学习路径确认页 |
| AI 课堂 | 左目录、中报告/分镜/练习、右 Agent；保存选择资源、阅读位置、播放位置、完成记录、笔记、答案和对话；提问暂停分镜 |
| 工作台 | 报告、分镜、课件和练习创作；课程知识库只展示待检索范围；后台任务查看、取消、继续仅在此处 |
| 资源中心 | 只收录工作台产物；类型筛选、搜索、预览、重命名、二次确认删除；报告下载 Markdown |
| 教师共享 | 仅教师出现上传入口；检查文件扩展名、最多 10 份、单份 50 MB；本地发布后同浏览器换账号可见；不读取文件正文、不上传、不伪称已解析 |

900px 以上为三栏课堂；601–900px 保留目录并切换学习/Agent；600px 以下切换目录/学习/Agent 单面板。无全局后台任务按钮、班级、课程码、学习任务或师生管理入口。

## 验证

最终验证结果：新模块 TypeScript/ESLint 无错误、无警告；5 个领域测试通过；21 个跨尺寸浏览器用例全部通过（33.8 秒）；最终生产构建退出码 0。浏览器用例也覆盖了局域网 HTTP 不提供 `crypto.randomUUID` 时的课堂创建，以及浏览器前进/后退。

- `pnpm check:self-learning`：新模块严格 TypeScript 与限定 ESLint。
- `pnpm test:self-learning`：领域行为测试，验证准备顺序、取消续跑、幂等完成、共享进度隔离、缓存恢复。
- `pnpm test:e2e:self-learning`：1440×1000、1024×768、390×844，覆盖主路径、播放暂停续播、阅读滚动、笔记、练习、Agent 上下文、任务、发布、账号隔离、下载、整理、失败登录、无横向溢出。
- `pnpm build`：全前端生产构建；旧代码仍有大 chunk 和混合静态/动态导入提示。
- 原版界面手动浏览器检查：登录界面正常，无页面运行异常。
- 截图由浏览器实际渲染生成，位于 `frontend/test-results/self-learning`；交付选图见本目录 `evidence/2026-09-14-self-learning/`。

旧前端全量 `tsc` 在修改前已有大量类型错误（包括测试导入和旧播放器类型），本次未把全量检查表述为通过，也未扩大修改范围去修复旧模块。新模块使用独立 `tsconfig.self-learning.json` 检查。

实际页面截图：[首页](evidence/2026-09-14-self-learning/home-desktop.png)、[课堂阅读](evidence/2026-09-14-self-learning/classroom-report.png)、[课堂讲解与 Agent](evidence/2026-09-14-self-learning/classroom-agent.png)、[工作台](evidence/2026-09-14-self-learning/studio-create.png)、[课程知识库](evidence/2026-09-14-self-learning/knowledge.png)、[资源中心](evidence/2026-09-14-self-learning/resources.png)、[手机首页](evidence/2026-09-14-self-learning/home-mobile.png)。

## 后续联调边界

| 本地适配点 | 下一阶段替换为 |
| --- | --- |
| `model.ts / createClassroom` | Agent 理解需求、规划学习路径，服务端建立课堂与资源槽位 |
| `advanceJobs` 和工作台任务 | 真实任务状态及进度事件；失败、取消、重试和后台持久执行 |
| `Studio` 知识库页 | 爬取/文档解析、实际来源及知识库构建状态 |
| `LearningContent` | 服务端报告正文、媒体地址、真实课件/题目，引用与来源 |
| `agentReply` | 带课堂、资源版本、位置、完成证据、答案和笔记的会话接口；不可把“观看完成”等同“已掌握” |
| `store.ts` | 用户课堂、学习事件和资源持久化；跨设备同步与会话恢复 |
| `PublishDialog` | 真正上传、解析和共享发布；后端落实教师权限、内容版本与个人进度分离 |

限制：当前文本为预置示例，播放为 36 秒三段分镜，没有真实音视频。模拟任务只在页面打开时推进，关闭后保存阶段、重新打开继续，不能冒充服务器后台执行。共享仅当前浏览器可见，不跨设备同步；同账号多标签页编辑尚未做冲突合并。教师上传保存文件元信息，预览显示示例内容，文件正文不持久保存。真实课程、资源和学习记录还未迁移。
