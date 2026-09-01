# 教师端 P0/P1 最终验收记录

> 验收日期：2026-08-06  
> 分支：`codex/teacher-p0-p1`  
> 结论：P0/P1 约定范围已完成，可进入人工 review；全仓历史测试基线仍有已知失败，详见第 8 节。

## 1. 交付结论

本轮完成了教师端从“入口可见”到“结果可信且可恢复”的基础闭环：

```text
资料上传
→ 文档处理状态可见
→ 单文档检索可验证
→ 生成任务可跨页面恢复
→ 结果原子保存
→ 课程资源统一管理
→ 来源、任务和配置版本可追踪
→ 用户与资源权限隔离
→ 失败可诊断、取消或重试
```

没有新增课程级时间轴编辑器，没有改写 OpenMAIC 渲染主线，也没有处理低优先级的主 Agent 智能与长期记忆。

## 2. P0 验收矩阵

| 范围 | 结果 | 验收证据 |
|---|---|---|
| P0-IA 信息架构 | 通过 | 左侧固定为问答、课程知识库、知识图谱、AI 课堂、课程资源、课程设置；路由测试与 5 组工作台截图 |
| P0-WS 工作台 | 通过 | 1280、1366、1440、1600、1920px 均无横向溢出；窄屏使用知识库/生成工厂抽屉，宽屏显示完整面板 |
| P0-CR 课程资源 | 通过 | AI 课堂与其他资源共用总列表和统一 ID；PPT、闪卡、互动资源有独立筛选与预览适配器 |
| P0-CL 在线课堂 | 通过 | 按页目录、16:9 舞台、当前页提词、播放/暂停/重播、翻页、全屏、演示和导出入口完整；页面无全课程 scrubber |
| P0-JOB 统一任务 | 通过 | owner 隔离的 v2 `EduJob`、原子文件账本、分页、取消、重试、启动恢复、退避与多标签页单轮询租约 |
| P0-STATE 状态系统 | 通过 | 加载、空、运行、部分成功、失败、取消和无权限均有中文状态；空对话不再显示 `No data` |
| P0-ROUTE 路由 | 通过 | 课程 ID 写入 hash；缺少 ID 安全回到课程列表，不生成 `#undefined` |
| P0-QA 质量门禁 | 通过 | 正式前端测试、P0/P1 后端定向测试、lint、生产构建和真实浏览器操作完成 |

### P0 关键行为确认

- AI 课堂既是独立授课入口，也是 `material_type=classroom` 的课程资源；两个入口复用同一 `classroom_id/material_id`。
- 在线课堂只控制当前页。暂停会停止当前运行时并提供“重新播放当前页”，翻页会释放上一页语音、视频、焦点和定时器。
- MP4 导出继续使用内部 `LessonTimeline`，不把全局时间轴暴露给在线授课界面。
- 课堂、视频、报告、教案、博客、习题、PPT、闪卡、思维导图、小游戏和 RAG 处理均接入全局任务源；组件卸载不再删除任务。
- 任务完成只通知并刷新资源，不擅自跳页或触发浏览器下载。

## 3. P1 验收矩阵

| 范围 | 结果 | 验收证据 |
|---|---|---|
| P1-RAG | 通过 | 文档生命周期、失败重建保留旧索引、删除清理、owner 校验和测试检索用例 |
| P1-GEN 可信生成 | 通过 | 八类正式资源注册表；统一 `GenerationCommand` 校验 owner、课程、来源、幂等键；保存失败为 `partially_succeeded` |
| P1-PPT/闪卡 | 通过 | PPT 恢复配置、大纲、后台生成、预览/导出；闪卡支持数量、难度、来源、逐张预览和正式资源保存 |
| P1-RES 资源存储 | 通过 | v2 manifest、稳定 ID、owner、来源任务、配置快照、内容哈希、附件清单、原子写入和完整删除 |
| P1-MIG 旧资源迁移 | 通过 | 默认 dry-run 的迁移工具；显式 owner 归属；`others` 正式类型迁移；损坏/冲突记录不静默删除 |
| P1-CONFIG 配置中心 | 通过 | 对话、Embedding、TTS、搜索、PDF、课堂服务六类配置；草稿、验证、启用、停用、回滚和版本快照 |
| P1-SECRET 密钥安全 | 通过 | AES-GCM 后端加密、响应掩码、浏览器密码输入不回填、sidecar 密钥不经过浏览器 |
| P1-ACCOUNT 用户中心 | 通过 | 资料、头像、改密均来自真实后端；旧 SHA-256 登录后渐进升级 PBKDF2；公开注册不能申请管理员 |
| P1-OBS 可观测性 | 通过 | 任务账本保留状态、步骤、错误、开始/结束时间；任务中心显示最近任务需关注率与平均耗时 |

### 固定样例基线

| 样例 | 期望 | 结果 |
|---|---|---|
| RAG：`快速排序如何分治` | 命中 `chunk-1`，页码为 1 | 通过 |
| RAG：已有 `idx_active` 时重建失败 | 文档继续 `ready`，旧索引保持激活，记录 `RAG_INDEX_FAILED` | 通过 |
| 生成：相同 owner + 幂等键重复提交 | 返回同一任务，不重复生成 | 通过 |
| 生成：不同 owner 复用同一幂等键 | 相互隔离 | 通过 |
| 生成：内容完成但资源保存失败 | 任务为 `partially_succeeded`，不报告完全成功 | 通过 |
| 资源：12 路并发更新同一 manifest | JSON 完整、版本递增至 12 | 通过 |
| 配置：未验证版本直接启用 | 拒绝启用 | 通过 |
| 配置：新旧任务跨配置切换 | 新任务使用新快照，已运行任务保留原快照 | 通过 |

说明：验收环境未提供真实外部模型、TTS、搜索、PDF 云服务或 OpenMAIC 供应商密钥，因此没有擅自产生外部调用和费用。供应商无关的业务闭环使用固定响应、故障注入和契约测试验证；真实供应商上线前仍应在目标部署环境逐个执行“测试连接”。

## 4. 浏览器与视觉验收

测试环境：Chromium headless，教师账号通过登录界面登录；页面控制台错误为 0。

| 宽度 | 横向溢出 | 生成入口 | 结果 |
|---:|---|---|---|
| 1280 | 无 | 抽屉内 8 类 + AI 课堂 | 通过 |
| 1366 | 无 | 抽屉内 8 类 + AI 课堂 | 通过 |
| 1440 | 无 | 抽屉内 8 类 + AI 课堂 | 通过 |
| 1600 | 无 | 固定面板 8 类 + AI 课堂 | 通过 |
| 1920 | 无 | 固定面板 8 类 + AI 课堂 | 通过 |

关键截图：

- [1280px 工作台](screenshots/teacher-p0-p1/workspace-1280.png)
- [1440px 生成工厂](screenshots/teacher-p0-p1/workspace-1440-factory.png)
- [1920px 工作台](screenshots/teacher-p0-p1/workspace-1920.png)
- [课程资源中心](screenshots/teacher-p0-p1/course-resources-1440.png)
- [按页课堂播放器](screenshots/teacher-p0-p1/classroom-player-1440.png)
- [全局任务中心](screenshots/teacher-p0-p1/global-task-center-1440.png)
- [AI 服务配置](screenshots/teacher-p0-p1/runtime-settings-1440.png)
- [密钥配置弹窗](screenshots/teacher-p0-p1/runtime-settings-modal-1440.png)

浏览器操作同时确认：

- PPT 卡片可获得键盘焦点，Enter 会执行卡片主操作；
- 八类入口为报告、教案、教学博客、习题、PPT、闪卡、思维导图、小游戏；
- 在线课堂播放后出现暂停，暂停后出现重新播放当前页；
- 播放器不存在 `input[type=range]` 全课程拖动条；
- 配置弹窗的 API Key 为未预填的 `password` 输入框；
- 账号中心显示真实用户名 `teacher`，并可进入 AI 服务配置。

## 5. 自动化验证

| 命令/套件 | 结果 |
|---|---|
| `npm test` | 125/125 通过 |
| P0/P1 后端定向套件 | 61/61 通过 |
| 资源 manifest 与迁移隔离套件 | 9/9 通过 |
| `npm run lint` | 0 error；82 个仓库既有 warning |
| `npm run build` | 通过；仅有大 chunk 提示 |
| `git diff --check` | 通过 |
| 完整后端 `pytest backend/src/tests -q` | 851 通过、21 失败、1 error；详见第 8 节 |

P0/P1 后端定向套件覆盖任务状态机/API、RAG 生命周期、资源 manifest/权限/迁移、统一生成命令、运行配置、视频入库、课堂任务/视频导出和真实用户资料。

## 6. 安全与故障检查

| 检查项 | 结果 |
|---|---|
| 任务 owner 列表、详情、取消、重试隔离 | 通过 |
| 文档和课程资源 owner 隔离 | 通过 |
| 无 owner 历史资源默认不向认证用户公开 | 通过 |
| 管理员迁移默认 dry-run、显式 `--apply` | 通过 |
| 任务与资源并发写入不会产生半个 JSON | 通过 |
| manifest 保存失败回滚暂存附件 | 通过 |
| RAG 重建失败不切走可用旧索引 | 通过 |
| API Key 密文落盘、API 只返回掩码 | 通过 |
| 非管理员不能修改系统配置 | 通过 |
| 配置验证错误不返回密钥或供应商响应体 | 通过 |
| 错误旧密码不会修改账户 | 通过 |

旧资源迁移命令：

```powershell
# 只预览，不写入
.venv\Scripts\python scripts\migrate-course-materials.py <course_id> --owner <username>

# review JSON 清单后显式执行
.venv\Scripts\python scripts\migrate-course-materials.py <course_id> --owner <username> --apply
```

## 7. 架构落点

- `src/stitch/teacherRoutes.ts`：课程级 hash 的唯一构造入口。
- `src/components/teacher/studioActions.ts`：八类正式生成能力注册表。
- `src/openmaic/pagePlaybackController.ts`：当前页运行时所有权和释放边界。
- `src/jobs/`：全局任务 store、单调度器、多标签页租约、任务抽屉与质量概览。
- `backend/src/app/services/job_store.py`：owner-scoped v2 EduJob 原子账本。
- `backend/src/app/services/knowledge_document_service.py`：RAG 文档生命周期与索引版本切换。
- `backend/src/core/course_storage.py`：v2 资源 manifest、原子发布、权限、完整性和旧数据迁移。
- `backend/src/app/services/generation_command.py`：统一生成提交、幂等和部分成功语义。
- `backend/src/app/services/runtime_config_store.py`：不可变配置 revision、密钥加密和审计状态。
- `backend/src/app/services/runtime_config_resolver.py`：个人 → 系统 → 环境默认的解析与任务快照。

## 8. 已知基线与非阻断债务

### 8.1 完整后端套件

最终完整套件为 `851 passed / 21 failed / 1 error`，不能宣称全仓 pytest 全绿：

- 2 项旧测试要求删除 PPT 直达路由和全部 `html2ppt` 引用，与本轮“恢复既有 PPT 正式能力”的产品要求冲突；
- 1 项旧课程范围测试依赖“无 owner 资源对任意认证用户可见”，已由 D-029 的安全边界替代；
- 1 项旧 RAG 直接调用测试仍按同步单文档返回值断言，新接口已按 `202 document + job` 异步契约工作；
- 其余失败集中于执行前已有的聊天/报告/Agent 兼容链路；`test_auth.py::test_get_me` 仍缺独立 fixture。

这些失败均已保留在完整输出中，未通过删除测试、吞异常或撤销产品需求来伪造全绿。

### 8.2 历史前端静态契约

`tests/frontend/*.test.ts` 未接入项目正式 `npm test`。独立运行结果为 59/76 通过、17 项失败，失败主要断言旧 API URL、旧页面命名、旧私有轮询和 Tailwind v3 字符串。与本轮直接相关的导航、课堂、资源、任务、RAG、配置契约已迁入正式套件并通过；历史集合需要单独治理。

### 8.3 代码质量与构建

- ESLint 无 error，仍有 82 个既有 warning，主要是未使用变量、旧页面 Hook 依赖和 Fast Refresh 文件拆分提示；
- 生产构建成功，主 bundle 和 PPTX/语法高亮资源仍有大 chunk 警告；本轮未扩大范围做全站拆包；
- FastAPI 仍有一处 `on_event("startup")` 弃用警告，后续可迁移到 lifespan。

## 9. Review 建议顺序

1. 先看 1280px 工作台、生成工厂和按页课堂；
2. 再看全局任务中心的刷新恢复、取消、重试与质量概览；
3. 用固定文档验证 RAG 状态和测试检索；
4. 检查 PPT/闪卡生成后的课程资源记录与来源追踪；
5. 在测试供应商账号下配置对话、Embedding、TTS，执行测试连接、启用、停用和回滚；
6. 最后复核当期 D-012、D-015、D-022、D-029 和 D-030 决策记录；原决策日志未纳入清理后的当前仓库，本文件仅保留历史验收证据。
