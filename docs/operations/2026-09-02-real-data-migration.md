# 2026-09-02 真实课程数据迁移记录

## 目标

将 Windows 本地迁移包中的真实 Edu-AI 业务数据恢复到 Linux 生产环境，并将应用文件读写路径统一放到部署用户可见的 `/home/zxqs_ep/data/edu_ai/`。

## 输入与校验

迁移包原位于 `/home/zxqs_ep/data/Edu_AI_migration`，包含 PostgreSQL 自定义格式全量备份、课程文件、OpenMAIC 文件、清单和 SHA-256 校验文件。

迁移前完成了以下只读校验：

- 压缩包和包内文件 SHA-256 全部通过；
- 36 个 JSON 文件全部可解析；
- PostgreSQL 17 自定义格式备份可列出并完整恢复到临时数据库；
- 在临时 PostgreSQL 14 上验证了生产数据库兼容性；
- PostgreSQL 17 导出的 `SET transaction_timeout = 0` 不受 PostgreSQL 14 支持，正式恢复时只过滤这一条会话参数，其余 SQL 在单事务和 `ON_ERROR_STOP` 下执行。

## 数据库切换结果

迁移前服务器数据库基线：

| 表 | 记录数 |
| --- | ---: |
| `courses` | 8 |
| `course_memberships` | 2 |
| `materials` | 2 |
| `knowledge_documents` | 0 |
| `users` | 10 |

迁移完成后的真实数据基线：

| 表 | 记录数 |
| --- | ---: |
| `courses` | 10 |
| `course_memberships` | 52 |
| `materials` | 185 |
| `knowledge_documents` | 261 |
| `users` | 7 |

Alembic 版本为 `20260901_0020`。恢复前对应用进程暂停写入，数据库清理与恢复在单个事务内完成，提交后再合并文件并恢复服务。

## 文件迁移结果

当前正式文件目录：

```text
/home/zxqs_ep/data/edu_ai/storage
/home/zxqs_ep/data/edu_ai/course_data
/home/zxqs_ep/data/edu_ai/openmaic
/home/zxqs_ep/data/edu_ai/tmp
```

切换时先进行在线首轮复制，再暂停应用写入完成增量同步。服务重启后通过 `/proc/<pid>/environ` 验证后端和 OpenMAIC 实际使用新路径。

迁移包中的课程文件和 OpenMAIC 文件与目标目录做了 rsync checksum 校验，源文件子集无差异。迁移完成时课程目录包含 313 个文件，OpenMAIC 目录包含 14 个文件；目标中原有且不冲突的验收文件被保留。

## 服务验证

迁移及路径切换后，下列服务均为 `active`：

```text
postgresql
edu-ai-openmaic
edu-ai-backend
nginx
```

以下端点返回成功：

```text
http://127.0.0.1:3000/api/health
http://127.0.0.1:8001/health
http://127.0.0.1/backend/health
```

服务重启后的错误级日志检查未发现新错误。

## 备份与清理

迁移前回滚备份：

```text
/home/zxqs_ep/data/Edu_AI_backups/migration-precutover-20260902T064000Z
```

迁移后恢复基线：

```text
/home/zxqs_ep/data/Edu_AI_backups/migration-postcutover-20260902T064500Z
```

迁移后备份包含 PostgreSQL dump、课程文件压缩包、OpenMAIC 文件压缩包及 `SHA256SUMS`，校验已通过。用户指定的原始导入目录 `/home/zxqs_ep/data/Edu_AI_migration` 已在迁移验收和迁移后备份完成后清除。

旧 `/data/edu_ai` 目前仅作为临时回滚副本保留，应用已不再读取或写入该目录。

## 已知缺口

源迁移包报告显示，本地原机在打包前已经缺失 227 个数据库引用文件，其中包括 113 个材料附件和 114 个知识文档文件。数据库记录已迁移，但无法从迁移包恢复原本就不存在的文件。后续若从其他备份找到这些文件，应按记录中的引用路径补齐并重新抽样验证。

## 日常启动入口

日常启动、健康检查、日志和回滚注意事项见 [Linux 启动、部署与数据迁移指南](../deployment/README.md)。
