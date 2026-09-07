# 首页继续备课／学习：验收文档（Agent A）

状态：A 前端实现与模拟 API 验收已完成；真实后端及 B 组合验收仍待验证。设计：[A 设计](../specs/2026-09-07-home-resume-design-cn.md)；计划：[A 计划](../plans/2026-09-07-home-resume-plan-cn.md)。

## 环境与数据

记录前后端提交、浏览器、端口。准备教师 T1／T2、学生 S1、课程“数据结构”和“大学物理”，数据结构含数组／链表。使用专用测试数据，避免改变真实课程。教师可访问两门课，学生只加入数据结构。

## 验收矩阵

| ID | 操作 | 必须观察的结果 | 状态 |
| --- | --- | --- | --- |
| A01 | T1 访问数据结构数组后回首页 | 首项直接显示数据结构；仅一个继续备课按钮；点击恢复对应工作位置 | 通过：教师浏览器用例，数组／链表 AI 工作区 |
| A02 | S1 学习后回首页 | 显示课程名＋继续学习；不再重复旧最近学习大块区域 | 通过：学生浏览器用例，加入课程入口保留 |
| A03 | 同一路由从数组切到链表后回首页 | 继续入口恢复链表，不能仅记第一次路由 | 通过：同路由 hash 查询变化与课堂 replaceState |
| A04 | 访问首页、个人设置再返回 | 有效工作记录不被覆盖 | 通过：首页／个人中心不覆盖；设置路由模块测试 |
| A05 | 同浏览器退出 T1 登录 T2 | 无 T1 课程名称或位置泄漏；T2 独立记录 | 通过：同浏览器重新认证 T2；真实退出／登录待集成 |
| A06 | 新账号、坏 JSON、storage 禁用 | 无虚假历史入口，主页面可正常用 | 通过：新账号、坏 JSON、旧历史及历史存储禁用 |
| A07 | 课程删除／退出／失权 | 不继续进入无权目标，失效记录清理 | 通过：403 浏览器清理，403／404／410 模块测试 |
| A08 | 子资料／知识点失效，课程仍有效 | 提示并降级同课程入口，不跳其他资料 | 通过：知识点／资源删除降级同课程 |
| A09 | 验证请求临时失败 | 记录保留，可重试，不误判删除 | 通过：503 保留记录、重试恢复 |
| A10 | 写入非法路由、外站 URL、未知参数 | 不执行任意导航，仅接受白名单 | 通过：非法路由、外站、未知参数白名单 |
| A11 | 1366px／390px、长课程名、键盘访问 | 名称可辨认、完整名称可访问、无横向溢出，按钮焦点可见 | 通过：师生桌面／390px，长名称、键盘焦点及入口高度 |
| A12 | 刷新后继续，含支持的资料定位参数 | 恢复符合声明粒度，无凭据写入记录 | 通过：刷新后 AI 知识点／资料恢复；课堂目录定位 |

## 证据与通过标准

- A01／A02 提供截图和导航前后 URL（去除敏感信息）；A03／A05 提供交互测试结果。
- 模块测试验证实际读写及路由解析，不以源码字符串检查替代。
- 全部用例有结果、构建通过，且没有账号混用、失权访问和虚假恢复，方可标记通过。
- 未实现的恢复粒度明确列出；不得声称恢复播放进度或未保存内容。

## 执行结果

实现提交：`6ad477dd224e2f9c03499d560743b5f2792aee16`。日期：2026-09-07。

环境：Node 22.23.2、pnpm 10.28.0、Playwright Chromium，Vite 独占端口 5181，desktop1366；窄屏在测试内设置 390×844。使用测试账号 T1／T2／S1、专用模拟 API 数据（course-physics 的显示名覆写为“数据结构”），未读写真实课程资料。原始前后端基线 `511ba6b3`；运行时工作区也包含 B／C 尚在实施的改动，故不能把此次运行视为组合验收。

以下命令均在 `frontend/` 执行；当前 shell 需先将 `/home/zxqs_ep/miniforge3/envs/edu-ai/bin` 加入 PATH。

| 命令／用例 | 结果 | 证据 | 限制 |
| --- | --- | --- | --- |
| `node --import tsx --test 'src/stitch/resume/*.test.ts' 'src/stitch/student/pages/studentRecentLearning.test.ts' 'src/stitch/student/pages/studentHomeLayout.test.ts'` | 12/12 通过 | [模块日志](evidence/2026-09-07-home-resume/unit.txt) | 其中 8 个 resume 行为测试、1 个历史迁移行为测试、3 个既有布局测试 |
| `PLAYWRIGHT_PORT=5181 pnpm exec playwright test tests/e2e/home-resume.spec.ts --project=desktop1366 --output=test-results/home-resume` | 15/15 通过，51.8s | [浏览器日志](evidence/2026-09-07-home-resume/e2e.txt) | 使用模拟 API；学生懒加载约 7–10 秒，断言等待窗口 30 秒 |
| `pnpm exec eslint src/stitch/resume src/stitch/App.tsx src/stitch/pages/HomeDashboard.tsx src/stitch/student/StudentApp.tsx src/stitch/student/pages/StudentHome.tsx` | 通过，无诊断 | [检查摘要](evidence/2026-09-07-home-resume/checks.txt) | 仅修改范围 |
| `pnpm build` | 通过，19.21s | [检查摘要](evidence/2026-09-07-home-resume/checks.txt) | 既有大 chunk／sourcemap 警告，不代表类型检查通过 |
| `pnpm exec tsc --noEmit --allowImportingTsExtensions` | 不通过；当前 72 个错误，A 修改文件无错误 | [当前诊断](evidence/2026-09-07-home-resume/types-current.txt)、[基线诊断](evidence/2026-09-07-home-resume/types-baseline.txt) | 原始 `511ba6b3` 临时只读源码副本同命令有 80 个错误；当前差异也包含 B／C 并行改动，不能归因于 A |

截图：[教师桌面](evidence/2026-09-07-home-resume/teacher-resume.png) · [学生桌面](evidence/2026-09-07-home-resume/student-resume.png) · [教师 390px](evidence/2026-09-07-home-resume/teacher-resume-390.png) · [学生 390px](evidence/2026-09-07-home-resume/student-resume-390.png)。已查看窄屏截图，入口紧凑且无横向溢出，完整名称保留在可访问文本中。

导航证据：教师 `#ai?course_id=course-physics&scopeType=knowledge_point&scopeId=array` → 同路由 `scopeId=list` → `#profile` → `#home` → 刷新 → 继续后恢复 `#ai?course_id=course-physics&scopeType=knowledge_point&scopeId=list`。学生 `#student-ai?course_id=course-physics&scopeType=knowledge_point&scopeId=array` → `#student-home` → 继续后恢复原 URL。测试文件对以上目标 URL 有精确断言。

## 交给 B 的实际契约

- `resume/resumeRecord.ts`：`recordFromHash(user, hash, now?) → ResumeRecord | null`；`readResume(user, storage?)`；`saveResume(user, record | null, storage?)`；`resumeHash(user, record) → string`。实际记录为 `{ version: 1, courseId, route, params, visitedAt }`。存储键为 `edu-ai-resume:v1:<role>:<encodeURIComponent(username)>`，身份来自 `useAuthSession` 已验证用户。
- `validateResume(user, record, api) → Promise<ResumeResult>`，状态 `valid/fallback/invalid/retry`。课程名称只取实时课程响应，知识点 label 只取实时图谱；403／404／410 明确失效，401／5xx／网络异常保留供重试。资源列表、图谱、课堂目录或学习概览读取失败也不能当作成功访问。
- `ResumeTracker` 统一挂载在 `App.tsx` 认证且角色路由已通过的分支；删除 StudentApp 旧 tracker 与 StudentHome 点击即写入。监听 hashchange、popstate 及已有 classroom replaceState；离开或换账号会取消旧验证结果，失败访问不覆盖记录。
- `ResumeEntry` 分别是两端主内容的首项，点击时重新验证权限；子位置若刚失效，留在首页提示后由同一个继续按钮进入该课程概览。StudentHome 退课／刷新以 `refreshToken` 重新验证。
- AI 工作区只依赖 B 拥有的 `readWorkspaceScopeFromSearch`，输出保持 `scopeType=knowledge_point&scopeId=<id>`，没有新 URL 别名或第二套知识点状态。恢复示例见上文。B 无需额外挂载 tracker。
- 资料页恢复 `material_type/material_id`（现有个人资源空间）；课堂恢复 `node_id/resource_id` 或 `personal_classroom_id`。当前课堂构造器会写 `teacher-classroom-studio`，A 读取后转为现有 App 支持的 `classroom-studio` 恢复，不修改 C 的构造器。
- 旧 `studentRecentLearning.ts` 保留 StudentShell 所需的只读兼容函数 `loadRecentLearning(availableCourseIds?, user?)`。未传已验证身份时返回空数组，绝不导入旧无账号历史；StudentShell 继续使用已有的可访问课程回退。旧写入 API 已退役。

## 恢复粒度与未验证范围

已支持课程页面、AI 工作区知识点、个人资源资料 ID、课堂目录及个人课堂 URL 定位。知识目录树的内部选中项没有可靠 URL 恢复协议，仅恢复目录页面；不恢复对话、未发送文本、未保存编辑、播放秒数或资源版本快照，也不从同名资料推测目标。

历史存储禁用已作模块和浏览器验证；整个浏览器存储不可用时 App 的持久化访问已增加容错，但真实认证与会话保持仍遵循原有认证实现，不新增无存储登录机制。

验收结论：A 可交付集成，前端模拟 API 验收通过。真实后端权限／删除行为、实际退出登录、I01–I05 的跨模块生成与修改／发布版本路径仍待 B 最终集成验证；本表不代表 B／C 验收通过。全项目类型检查仍不通过，诊断已保留。
