# PostgreSQL 存储切换与运维说明

## 当前状态

从 2026-08-10 起，Edu AI 的结构化业务数据以 PostgreSQL 为唯一运行时事实来源。旧 JSON 和 SQLite 文件仅作为迁移证据与紧急人工核对材料保留，不再参与生产读写。

API 通过 `PERSISTENCE_PROFILE=database` 执行强制校验。用户、课程、课程成员、对话、业务任务、材料、知识库元数据、通用应用状态、学习数据和 durable task queue 十个域必须全部配置为 `postgres`；否则 API 在启动阶段直接失败。

图片、PDF、Markdown、音视频、PPTX 等大文件本体仍保存在文件系统。数据库保存业务状态、版本、哈希和文件引用，这不属于旧 JSON 主存储方案。

## 日常启动

继续使用：

```bat
D:\github\edu_ai\Edu_AI\api\src\start_api.bat
```

脚本会自动启动 Docker 中的 PostgreSQL、等待健康检查、执行 Alembic 升级，再启动 API 和前端。无需单独手工启动数据库容器。

只启动并检查数据库：

```bat
D:\github\edu_ai\Edu_AI\api\src\start_api.bat --database-only
```

## 验收与诊断

在 `Edu_AI/api/src` 加载数据库环境变量后执行：

```powershell
python -m app.database.cutover_report_cli
```

验收工具会检查：

- 十个持久化域是否全部为 PostgreSQL；
- 21 张业务表是否齐全；
- Alembic 是否为 `20260810_0008`；
- 每张业务表的当前记录数。

切换时核验的关键数量为：7 个用户、6 门课程、42 条课程成员关系、149 个对话、1155 条消息、272 个业务任务、168 个材料、153 个知识文档、286 个 durable tasks。4 个损坏的历史材料记录进入隔离表，没有被丢弃。

## 备份与恢复

切换备份保存在本机未纳入 Git 的目录：

`D:\github\edu_ai\Edu_AI\backup\postgres\edu_ai-cutover-20260810.dump`

- 格式：PostgreSQL custom format
- SHA-256：`31f50dbfaf007d32227ef0df8062f7901abb0edbc33660aa0c546ae7655e325d`
- 恢复验证：已恢复到独立临时数据库；用户、课程、对话、durable tasks 数量为 `7 / 6 / 149 / 286`

后续正式发布前应再生成一次新备份，不能长期依赖本次切换快照。

## 回滚规则

生产环境禁止重新启用 JSON/SQLite。需要回滚时：

1. 停止 API 写入并记录当前 Git 提交和 Alembic revision。
2. 选择对应的 `db-migration-phase*` Git 标签回退应用。
3. 将已验证的 PostgreSQL 备份恢复到独立数据库，核对后再切换连接。
4. 不直接覆盖或删除当前数据库；保留现场用于差异核对。

主要检查点：

- `db-migration-phase0`
- `db-migration-phase1-shadow`
- `db-migration-phase1-postgres`
- `db-migration-phase2-conversations`
- `db-migration-phase3-jobs`
- `db-migration-phase3-materials`
- `db-migration-phase4-knowledge`
- `db-migration-phase5-state`
- `db-migration-phase6-tasks`

旧文件至少保留 30 天。它们是只读迁移证据，不应再由业务代码更新，也不应在数据库出现新数据后重新导入覆盖。
