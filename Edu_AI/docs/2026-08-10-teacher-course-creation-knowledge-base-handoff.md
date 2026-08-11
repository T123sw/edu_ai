# 教师端“创建课程 → 一键构建知识库 → 开始使用”工作交接

**交接日期：** 2026-08-10<br>
**仓库：** `D:\github\edu_ai`<br>
**分支：** `main`<br>
**交接基线提交：** `ab29591f12f84df46003aa38b3856bbe914a9913`<br>
**下一阶段目标：** 打通教师从创建一门新课程，到自动构建课程知识库，再到使用课程知识进行问答、备课和资源生成的完整产品闭环。

---

## 1. 给接手对话的结论

当前系统的数据库迁移已经完成，PostgreSQL 已成为业务结构化数据的唯一正式存储，数据库启动已整合到 API 启动脚本。下一阶段不需要继续讨论 JSON、SQLite 或 PostgreSQL 选型，而应集中完成教师端产品闭环。

现状不是“系统完全没有创建课程和自动建库能力”，而是已有能力分散在旧页面、未使用页面和只适配固定课程的后端实现中：

1. 当前实际使用的教师首页没有“创建课程”按钮，这与用户观察一致。
2. 旧版教师课程管理页已经有创建课程弹窗，前后端也已有 `POST /api/courses`。
3. 当前实际使用的课程知识页没有“一键建库”入口。
4. 另一个未接入当前主路由的页面已经有“一键重建真实课程知识库”按钮，并接入后台任务中心。
5. 后端自动建库链路已经具备来源审查、抓取、翻译、知识结构生成、资料持久化、索引、质量补充和进度上报能力，但开放教材来源与课程 ID 硬编码绑定，目前不能可靠支持教师任意新建的课程。

因此下一轮应优先“整合并产品化已有能力”，然后把固定课程建库器泛化为由课程语义信息驱动的通用建库能力。

---

## 2. 用户原始诉求与已做决策

用户提出的核心问题是：

- 教师端看不到创建新课程的入口。
- 创建课程后进入的是空课程，教师不知道下一步做什么。
- “计算思维”知识库过去依赖在 Codex 窗口中人工要求 Codex 查找、审查和补充资料。
- 希望把这项能力固化为系统自有能力，让教师能够一键构建课程知识库，不依赖 Codex 对话。
- 系统原来大量结构化数据存放在 JSON 和业务 SQLite 中，不便管理，希望迁移到 PostgreSQL。

已经确认的产品与技术方向：

- PostgreSQL 存放业务结构化数据。
- 课程原始文件、解析产物和较大二进制文件继续使用文件系统或对象存储式边界，不把所有二进制强塞入数据库。
- Chroma 继续作为 RAG 向量索引，其内部 SQLite 不属于业务数据回退方案，不在本阶段移除。
- 教师创建课程后，应得到清晰的初始化引导，而不是直接落入一个无内容、无行动提示的课程。
- 一键建库必须是系统后台任务，支持进度、失败说明、重试和完成后刷新。
- 新版本建库失败时不能破坏正在使用的旧知识库，应采用构建版本、质量门禁和成功后切换的思路。
- 来源必须记录出处、许可和抓取约束；不能把任意网络内容不经审查直接发布为课程公共知识。

---

## 3. 数据库迁移已完成，不要重复实施

### 3.1 当前状态

- PostgreSQL 已完成部署、迁移、真实 API 端到端验证和重启持久化验证。
- Alembic 当前版本：`20260810_0008`。
- 当前已验证数据库包含 21 张业务表。
- 全量自动化测试结果：`1491 passed, 2 skipped`。
- 已执行真实 HTTP 端到端流程，并清理测试数据。
- API 启动脚本会自动检查 Docker、启动 PostgreSQL、等待健康检查、执行 Alembic 升级，再启动 API。
- 启动入口：`Edu_AI/api/src/start_api.bat`。

### 3.2 已下线的旧存储

- 原 JSON 业务结构化存储已退出正式读写链路。
- 原业务 SQLite 已下线，学习记录、任务、Agent 运行、课程、知识文档等正式数据均使用 PostgreSQL。
- Chroma 自带的 SQLite 仍用于向量索引内部状态，这是预期设计，不应误删。

### 3.3 迁移文档与回滚点

- 数据库切换说明：`Edu_AI/docs/database-storage-cutover.md`
- 数据库迁移规格：`Edu_AI/docs/specs/2026-08-10-database-migration-spec.md`
- 最终标签：`db-migration-complete-20260810`
- 其余阶段标签：
  - `db-migration-phase0`
  - `db-migration-phase1-postgres`
  - `db-migration-phase1-shadow`
  - `db-migration-phase2-conversations`
  - `db-migration-phase3-jobs`
  - `db-migration-phase3-materials`
  - `db-migration-phase4-knowledge`
  - `db-migration-phase5-state`
  - `db-migration-phase6-tasks`
- 本地数据库备份：`Edu_AI/backup/postgres/edu_ai-cutover-20260810.dump`（已忽略，不进入 Git）。
- 备份 SHA-256：`31f50dbfaf007d32227ef0df8062f7901abb0edbc33660aa0c546ae7655e325d`。

下一轮如果发现问题，应基于现有 PostgreSQL 仓储修复，不要重新引入 JSON 或业务 SQLite 双写。

---

## 4. 当前教师端真实入口与重复实现

### 4.1 当前实际使用的主教师首页

文件：`Edu_AI/src/stitch/pages/HomeDashboard.tsx`

当前能力：

- 展示课程卡片。
- 搜索课程。
- 进入课程。

当前缺口：

- 没有“创建课程”主按钮。
- 没有课程时没有“创建第一门课程”的空状态行动按钮。
- 创建成功后的初始化引导没有接入这里。

这正是用户在教师前端找不到创建按钮的直接原因。

### 4.2 旧版课程管理页已经能创建课程

文件：`Edu_AI/src/pages/teacher/CourseManagementPage.tsx`

已有能力：

- “新建课程”按钮。
- 新建/编辑课程弹窗。
- 调用 `useCourseStore.addCourse`。

相关代码：

- `Edu_AI/src/store/course/useCourseStore.ts`
- `Edu_AI/src/services/teacher/api.ts` 中的 `createCourseBackend`
- `Edu_AI/api/src/app/api/courses.py` 中的 `POST /api/courses`

注意：不要简单把用户导航回旧版课程管理页。推荐抽取或复用创建表单逻辑，把它接入当前 Stitch 教师首页和当前课程外壳，避免继续维护两套教师入口。

### 4.3 当前课程知识主页面

文件：`Edu_AI/src/stitch/pages/CourseKnowledge.tsx`

当前路由使用：

- `KnowledgeStructureView`
- `KnowledgeDocumentsView`

资料视图文件：`Edu_AI/src/stitch/course/knowledge/KnowledgeDocumentsView.tsx`

当前能力：

- 选择知识结构节点。
- 查看课程文档。
- 上传资料。

当前缺口：

- 没有一键构建课程知识库入口。
- 没有新课程初始化状态。
- 没有建库计划预览、来源候选审查、质量报告和发布状态。

还需特别审查：当前上传调用中存在 `libraryType: "personal"` 的语义。按照已有课程知识库设计，教师在“课程知识”页面直接上传，应明确进入课程库；个人上传则应默认进入个人库，发布到课程必须是显式动作。不要在没有测试权限边界的情况下悄悄改动。

### 4.4 未接入当前主流程的一键建库页面

文件：`Edu_AI/src/stitch/pages/CourseKnowledgeBase.tsx`

这个页面已经包含：

- “一键重建真实课程知识库”按钮。
- `buildKnowledgeBaseFromOpenTextbook(course.id)` 调用。
- 后台任务注册。
- 任务中心进度展示。
- 完成/失败提示。

但当前主要课程知识路由使用的是 `CourseKnowledge.tsx`，所以教师在正常操作路径中看不到这个按钮。

前端接口：

- `Edu_AI/src/stitch/api/courses.ts`
- `buildKnowledgeBaseFromOpenTextbook(courseId)`
- 请求：`POST /api/courses/{course_id}/knowledge-base/build-from-open-textbook`

建议把任务提交和进度呈现逻辑抽成可复用组件，接入当前 `KnowledgeDocumentsView` 或新课程初始化引导；不要简单恢复第二套知识库页面。

---

## 5. 后端一键建库能力：已有基础与关键限制

### 5.1 已有接口与任务链路

接口：`Edu_AI/api/src/app/api/courses.py`

- `POST /api/courses/{course_id}/knowledge-base/build-from-open-textbook`
- 需要教师课程生成权限。
- 调用 `submit_course_knowledge_build_job`，以持久后台任务执行。

核心服务：`Edu_AI/api/src/app/services/course_knowledge_builder.py`

现有流水线已经覆盖：

1. 解析课程与来源。
2. 审计来源、许可和抓取约束。
3. 获取开放教材页面。
4. 必要时翻译中文，并缓存翻译结果。
5. 清理占位内容和不合格旧生成记录。
6. 构建知识结构和节点资料。
7. 按节点持久化文档并写入课程 RAG 索引。
8. 执行质量检查和不足内容补充。
9. 保存知识图谱。
10. 上报任务进度、警告和最终报告。

任务处理入口可继续追踪：`Edu_AI/api/src/app/services/platform_task_handlers.py`。

### 5.2 最大阻塞：只支持预设课程

`course_knowledge_builder.py` 中的 `OPEN_TEXTBOOK_SOURCES` 目前只定义了少量来源，且通过固定 `course_ids` 匹配：

- `hello-algo-zh`：`computational-thinking`、`data-structures`
- `think-and-compute-zh`：`computational-thinking`

`resolve_open_textbook_source(course_id, source_id="auto")` 会按课程 ID 选来源。因此教师新建任意课程，例如 `course-172...`、`linear-algebra` 或 `modern-history`，自动来源解析很可能直接失败。

这是下一阶段必须解决的核心问题。仅仅把已有按钮显示出来，不能算完成“一键构建任意课程知识库”。

### 5.3 已有安全和质量原则

已有实现及设计文档要求保留：

- 来源归属、许可和引用记录。
- robots/AI ingestion 审查。
- 单个资料失败可记录警告，不能让整个任务无提示消失。
- 至少有资料成功持久化后才允许切换活动图谱。
- 系统课程建库资料直接进入 `course:<course_id>` 访问域。
- 用户个人资料不得自动公开到课程库。
- 课程知识库只有一份事实来源，资料页、问答和生成均从同一课程库读取。

---

## 6. 建议的目标教师流程

### 6.1 完整产品流程

1. 教师登录，进入课程首页。
2. 首页右上方显示“创建课程”；没有课程时显示“创建第一门课程”。
3. 教师填写最少必要信息：课程名称、简介、教学对象/年级、课程目标、授课语言和难度。
4. 系统创建课程、写入 owner 成员关系，并跳转到该课程的初始化页。
5. 初始化页明确给出三个选择：
   - 一键构建课程知识库（主行动）。
   - 上传已有课程资料。
   - 暂时跳过，进入空课程。
6. 教师选择一键构建后，系统根据课程语义信息生成建库计划，而不是根据课程 ID 猜测教材。
7. 系统发现候选来源并执行许可、权威性、时效性和课程相关性审查。
8. MVP 可以默认推荐一组来源并让教师确认；真正“一键”也必须在后台保留来源清单和审查证据。
9. 后台任务按阶段展示：
   - 分析课程
   - 规划知识结构
   - 查找与审查来源
   - 获取与解析资料
   - 翻译与清洗
   - 构建知识结构
   - 建立索引
   - 质量检查与补充
   - 准备发布
10. 教师可以离开页面，任务在任务中心继续；可查看进度、取消、失败原因和重试。
11. 构建成功后，系统展示摘要：知识节点数、资料数、来源数、覆盖率、警告和质量结果。
12. 教师确认或系统通过质量门禁后，切换为活动课程知识库。
13. 系统引导教师继续：课程问答、教案/课件生成、AI 课堂、课程资源。

### 6.2 新课程初始化页应避免的体验

- 不要创建成功后直接进入一个空白资料列表。
- 不要把内部课程 ID、任务类型、技术错误堆栈直接展示给教师。
- 不要让“一键构建”看起来已经支持所有课程，而实际上只支持两个固定 ID。
- 不要在构建失败时清空或覆盖已有活动知识库。
- 不要把教师在课程知识页面上传的资料误放进个人库，或把个人资料自动公开到课程库。

---

## 7. 建议实施顺序

### 阶段 A：先打通创建课程入口与空课程引导

1. 在 `HomeDashboard.tsx` 增加“创建课程”主按钮和空状态 CTA。
2. 从旧页抽取创建课程表单，或实现一个当前设计体系下的复用组件。
3. 复用现有 `useCourseStore.addCourse` 和后端 `POST /api/courses`，不要另造并行 API。
4. 创建成功后跳转到新课程的初始化/概览状态。
5. 保证教师可见、学生不可见，键盘可操作，错误可重试。

### 阶段 B：把现有建库任务接入当前课程知识页

1. 从 `CourseKnowledgeBase.tsx` 提取提交任务、注册任务和状态反馈逻辑。
2. 在当前 `KnowledgeDocumentsView` 或课程初始化页加入建库卡片。
3. 新课程没有资料时显示主 CTA；已有知识库时显示“更新/重建”，并明确影响。
4. 完成后自动刷新资料列表和知识结构。
5. 接入任务中心的取消、失败说明和重试能力。

阶段 B 可以先用于验证 UI/任务闭环，但必须明确显示当前支持范围，不能把固定来源实现包装成通用能力后直接交付。

### 阶段 C：把固定教材建库器泛化为课程驱动的建库器

建议新增“建库计划”概念，将“发现/审查”和“正式构建”分开：

1. 根据课程名称、简介、目标、对象、语言和难度生成知识结构草案与检索主题。
2. 来源发现服务返回候选来源，包含：标题、URL、机构/作者、许可、语言、更新时间、相关性、权威性、允许的处理方式和拒绝原因。
3. 教师确认来源，或采用系统推荐并保留审计记录。
4. 提交正式构建任务，使用计划快照和幂等键。
5. 构建在独立版本中进行，质量通过后原子发布。
6. 活动版本可回滚；失败版本保留诊断，不污染正式库。

课程 ID 只用于归属和权限，不再决定内容来源。

### 阶段 D：质量、版本与“使用”闭环

1. 增加覆盖度、重复度、引用完整性、结构完整性、索引成功率和检索抽测。
2. 新库未达到最低门槛时不得标记为“专业课程知识库已完成”。
3. 构建成功页提供进入课程问答、教案、课件、习题和 AI 课堂的入口。
4. 验证这些下游功能确实检索刚创建课程的知识库，而不是默认课程或个人库。
5. 验证另一位课程教师看到同一课程库，学生只有只读权限。

---

## 8. 建议 API 与数据边界

以下是建议方向，不是已实现接口，接手者应先核对现有 jobs、job_events、knowledge libraries/documents、graph versions 等模型，再决定是否需要新表。

建议的业务接口：

- `POST /api/courses`：创建课程，沿用现有接口。
- `POST /api/courses/{course_id}/knowledge-builds/preview`：生成知识结构草案和来源候选。
- `POST /api/courses/{course_id}/knowledge-builds`：根据确认后的计划提交构建。
- `GET /api/courses/{course_id}/knowledge-builds/{build_id}`：状态、阶段、指标和警告。
- `POST /api/courses/{course_id}/knowledge-builds/{build_id}/cancel`：取消。
- `POST /api/courses/{course_id}/knowledge-builds/{build_id}/retry`：按原配置或修改后重试。
- `POST /api/courses/{course_id}/knowledge-builds/{build_id}/publish`：通过质量门禁后发布。
- `POST /api/courses/{course_id}/knowledge-builds/{build_id}/rollback`：回滚活动版本。

关键数据要求：

- build 记录：课程、创建者、状态、阶段、配置快照、进度、幂等键、错误、指标。
- source candidate：URL、来源类型、许可、审查结果、选择状态和拒绝原因。
- graph/document version：构建版本与活动版本分离。
- quality check：检查项、分数、门槛、证据和结果。
- 所有记录都要带课程访问域和审计字段。

当前 PostgreSQL 已有持久任务和知识库基础表。优先复用现有通用任务能力；只有当来源审查、版本发布和质量证据无法可靠表达时再增加专用表和 Alembic 迁移。

---

## 9. 技术原则与容易踩坑的位置

### 9.1 不要依赖课程 ID 选择教材

新课程 ID 可能是时间戳、slug 或 UUID，不能表达课程语义。来源发现必须基于课程元数据和教师输入。

### 9.2 保证幂等和并发安全

- 双击“一键构建”不得创建两个互相覆盖的任务。
- 同一课程同时构建时要明确拒绝、排队或创建独立版本。
- 前端请求超时后重试不得重复写入大量文档。

### 9.3 使用构建版本和原子发布

- 正在使用的课程库在新构建期间继续可用。
- 新版本在隔离空间写入和评测。
- 达标后一次切换活动版本。
- 失败时保留原版本。

### 9.4 保持资料归属清晰

- 教师在课程知识页直接上传：课程库。
- 教师在个人知识库上传：个人库。
- 个人资料加入课程：显式发布并创建课程副本。
- 系统自动建库资料：课程库，并记录来源和许可。

### 9.5 保持当前存储架构

- PostgreSQL：业务元数据、状态、版本、权限、任务、审计。
- 文件系统/未来对象存储：原始文件、解析产物和较大媒体。
- Chroma：向量索引。
- 不恢复 JSON 或业务 SQLite 为正式事实来源。

### 9.6 注意两套教师页面

不要只修改 `src/pages/teacher/CourseManagementPage.tsx` 就认为用户能看到；当前主流程在 `src/stitch`。实施前先从应用路由确认真正渲染的页面，并删除或收敛重复入口时保持兼容。

### 9.7 课程创建 ID 契约

旧前端使用类似 `course-${Date.now()}` 的客户端 ID。下一阶段应明确：

- 是由服务端生成稳定 UUID/slug；还是
- 继续由客户端提交 ID，但后端严格校验冲突并返回可恢复错误。

不要让课程名称直接成为不可更改的主键，也不要在未设计迁移的情况下改变现有课程 ID。

---

## 10. 必须完成的自动化与端到端验证

### 10.1 前端测试

- 教师首页能看到“创建课程”，学生看不到。
- 无课程时显示“创建第一门课程”。
- 必填校验、提交中状态、后端失败和重试正确。
- 创建成功后进入刚创建的课程，而不是本地缓存中的旧课程。
- 新课程初始化页显示三个下一步选择。
- 有权限教师能看到一键建库，viewer/学生不能执行。
- 任务提交后显示进度；刷新或切换页面后仍能恢复。
- 完成后资料和知识结构自动刷新。
- 失败、取消和重试均有明确状态。

### 10.2 后端测试

- 任意新课程不再因课程 ID 未在白名单中而失败。
- 来源发现和选择记录许可、robots/抓取约束和审查结果。
- 幂等请求不重复创建文档、索引或任务。
- 单来源失败可降级，多数来源失败时能给出可读错误。
- 新构建失败不影响当前活动知识库。
- owner/editor 可建库，viewer/学生返回 403，未登录返回 401。
- 文档、图谱、任务和版本都严格按课程隔离。
- PostgreSQL 重启后构建记录、任务和活动版本仍在。

### 10.3 真实端到端验收

至少完成一次全新课程的真实流程：

1. 启动 `Edu_AI/api/src/start_api.bat`。
2. 教师登录。
3. 从当前主教师首页创建一门此前不存在的课程。
4. 填写课程目标、对象和语言。
5. 点击一键构建，确认不是使用硬编码的 `computational-thinking` 来源分支。
6. 观察后台任务从排队到完成。
7. 打开资料列表与知识结构，验证数量、来源和引用。
8. 刷新页面并重启 API/PostgreSQL，确认数据仍存在。
9. 使用新课程库发起课程问答，验证能引用该课程资料。
10. 生成至少一种教学资源，验证来源为当前课程而非其他课程。
11. 第二位教师读取同一结果。
12. 学生只能读取允许发布的课程内容，不能创建课程、建库、编辑或删除。

不能只用 mock 或单元测试宣布完成。必须保留真实建库任务报告、关键 API 结果和 UI 验收证据。

---

## 11. 本阶段完成定义

同时满足以下条件才算完成：

- 当前主教师首页有清晰的创建课程入口和空状态 CTA。
- 教师可以创建一门任意新课程，并稳定进入该课程上下文。
- 新课程不再是无引导的空页面。
- 教师能从初始化页或当前课程知识页启动一键建库。
- 一键建库不再依赖固定课程 ID 白名单。
- 来源有审查、许可、引用和审计记录。
- 后台任务支持进度、刷新恢复、取消、失败原因和重试。
- 新构建失败不破坏已发布知识库，成功后可切换和回滚。
- 资料页、知识结构、问答和资源生成读取同一份课程知识事实数据。
- 权限、跨课程隔离、PostgreSQL 持久化和重启恢复通过自动化与真实 E2E。
- 无业务 JSON/SQLite 回退或双写重新出现。
- 关键阶段分别提交 Git 版本，并保留可回溯标签或清晰提交记录。

---

## 12. 必读文档

接手后先读以下内容，避免破坏已经确定的课程、权限、来源和版本原则：

1. `Edu_AI/docs/2026-08-10-teacher-course-creation-knowledge-base-handoff.md`（本交接）
2. `Edu_AI/docs/superpowers/specs/2026-08-06-course-centered-teacher-experience-design.md`
3. `Edu_AI/docs/superpowers/specs/2026-08-08-professional-multimodal-course-knowledge-base-design.md`
4. `Edu_AI/docs/superpowers/plans/2026-08-08-professional-multimodal-course-knowledge-base.md`
5. `Edu_AI/docs/superpowers/plans/2026-08-06-course-knowledge-generation-reliability.md`
6. `Edu_AI/docs/2026-08-09-teacher-agent-optimization-handoff.md`
7. `Edu_AI/docs/database-storage-cutover.md`
8. `Edu_AI/docs/specs/2026-08-10-database-migration-spec.md`
9. `Edu_AI/docs/acceptance/2026-08-10-teacher-student-learning-loop-real-e2e.md`

---

## 13. 工作区与版本控制保护

交接时 `main` 与 `origin/main` 位于：

`ab29591f12f84df46003aa38b3856bbe914a9913`

工作区已有一处用户改动，不能覆盖、还原、格式化或误提交：

`Edu_AI/api/course_data/courses/computational-thinking/knowledge_base/index.json`

接手者开始前应执行状态检查，并把新阶段拆成可回溯提交。建议提交边界：

1. 创建课程入口与表单。
2. 新课程初始化引导。
3. 当前知识页的一键建库入口与任务状态。
4. 通用建库计划和来源发现。
5. 构建版本、质量门禁与发布/回滚。
6. 自动化和真实端到端验收证据。

不要把上述用户已有 `index.json` 改动混入任何提交。

---

## 14. 可直接复制给新对话窗口的启动提示词

```text
请接手 D:\github\edu_ai 的教师端“创建课程 → 一键构建课程知识库 → 使用课程知识”完整闭环。

先完整阅读：
Edu_AI/docs/2026-08-10-teacher-course-creation-knowledge-base-handoff.md

然后核对其中列出的现有代码入口和主路由，不要假设旧版 CourseManagementPage 或未接入主路由的 CourseKnowledgeBasePage 就是教师当前看到的页面。

数据库迁移已经完成：业务结构化数据只使用 PostgreSQL；不要恢复 JSON 或业务 SQLite。Chroma 内部 SQLite 保留用于向量索引。API 启动脚本已经自动启动 Docker PostgreSQL、健康检查和 Alembic。

请按交接文档的阶段 A → B → C → D 持续实施：
1. 在当前主教师首页增加创建课程入口和空状态；
2. 创建成功后进入有明确下一步的新课程初始化流程；
3. 把已有后台建库任务接入当前课程知识页面；
4. 将只支持固定课程 ID 的开放教材建库器改造成基于课程元数据、来源发现与审查的通用建库能力；
5. 完成构建版本、质量门禁、原子发布、失败恢复和使用闭环；
6. 执行自动化与真实端到端验证，分阶段做好 Git 版本控制。

开始前先检查 git status。必须保护并排除用户已有改动：
Edu_AI/api/course_data/courses/computational-thinking/knowledge_base/index.json

不要只写方案；在确认现状后直接逐步实现，直到交接文档中的完成定义全部满足。遇到设计选择时优先复用现有课程 API、任务中心、PostgreSQL 仓储和课程知识事实来源，不创建平行系统。
```
