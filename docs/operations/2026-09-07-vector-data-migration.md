# 2026-09-07 Chroma 向量数据库补迁移

状态：服务器补迁移完成，完整性、业务检索及权限验收通过。主机 `server163`，UTC 切换时间 `2026-09-07T05:57:24.008869+00:00`。

## 迁移结果

- 输入：`/home/zxqs_ep/data/edu_ai/vector-data-20260907.tar`。
- 包 SHA-256：`270741bfebe3017bac0e6a4db62633939a03f9edd36ad17c6cd4eac56097c37a`；包内 932 个文件 SHA-256 全部通过。
- 正式 `VECTOR_DB_PATH`：`/home/zxqs_ep/data/edu_ai/staging/vector_db_20260907_linux`。
- 集合：`documents`，5,458 条、3,072 维、cosine；5,277 文本块、181 图片块，325 个来源。
- 生产 Chroma 保持 1.5.9；先在独立 venv 的 1.3.5 原样恢复并核验，再复制为独立 Linux 副本，用生产 1.5.9 完整复验。未升级或降级生产依赖。
- 两次原样核验均逐条比较正文、元数据与全部向量，并通过 15 组已存向量查询。最大向量误差 1.4901161193847656e-08，为 cosine float32 再归一化误差。
- 749 个缺失关联文件补拷，146 个已有文件内容相同；1 个冲突保留服务器版本，旧向量对应原文另存 `storage/migration_versions/20260907/`。896 个交付文件全部核验。
- 323 条现有 PostgreSQL runtime_index_entries 仅更新物理路径字段，采用原值比较与事务提交；1,398 个向量元数据记录适配图片物理路径及结构化 linked_images。ID、source、owner、parent_index_key、父块标识和正文保持不变，适配后再次全量核验 5,458 条。
- 没有覆盖 PostgreSQL 业务库，没有调用 replace_runtime_index，也没有批量重新生成嵌入。

## 模型及业务验收

实际 EmbeddingClient：backend=openai，model=gemini-embedding-2-preview；真实查询输出 3,072 维。配置中的 GEMINI_EMBEDDING_DIMENSIONS=768 为遗留值，当前 openai 分支未发送 dimensions，未为凑维度进行截断或填充。自然语言检索已验证相关性；历史模型来源无法仅由旧配置独立证明。

- 教师计算思维“链表怎么实现”：5 条相关命中。
- 教师人工智能与机器学习问题：5 条相关命中。
- 指定链表资料：3 条命中，父块上下文扩展和原文路径验证通过。
- 181 个图片块的实际文件存在。
- 学生个人检索范围验证通过，教师私有资料不进入学生检索范围。
- 切换后真实 HTTP 图片访问：教师 200，学生访问该教师图片 403。
- 切换后真实 HTTP `/api/rag/query`：200，返回 5 条来源和 2746 字符答案；问题为“链表怎么实现”。
- 后端 active，health=200，新进程确认读取新 VECTOR_DB_PATH；BM25 加载 5,277 文本块。

## 仍保留的历史缺口

- 16 条可检索注册记录没有随本包提供向量，导入日期为 2026-08-11/12，涉及旧循环/条件课程与 e2e-graph-first-20260812。保留这些记录，不冒用其他来源、不清空注册表；本次恢复前旧生产库为 0 条，因此本次没有丢弃服务器新向量。
- 2 个原始文档文件仍缺失：www.idcbest.hk 全球云基础设施服务目录、www.imooc.com 智能体基础入门与实践指南。向量正文保留，不能宣称这两份原文预览恢复。
- 数据编码练习的服务器当前版本和旧向量版本均保留；RAG 注册表物理路径指向独立保存的配套旧版，课程目录保持服务器当前版本。后续若使用新版内容，应单独重新索引该文档。

## 备份、证据与回滚

备份：`/home/zxqs_ep/data/Edu_AI_backups/vector-precutover-20260907T055453Z`，包含完整旧向量目录、切换前环境配置、业务数据库逻辑备份、注册表快照、SHA256SUMS（5 个文件校验通过）。旧向量目录 `/home/zxqs_ep/data/edu_ai/storage/vector_db` 保留。

证据和脚本：`/home/zxqs_ep/data/vector-migration-20260907`，包括 restore-135.json、restore-159.json、acceptance-precutover.json、http-acceptance.json、http-query-result.json、links-before.json、links-after.json、files-applied.json、path-map.json、registry-path-changes.json、vector-path-changes.json、cutover.json。

完整原样恢复库 `vector_db_20260907_original_v2`、原始 tar 和包内 raw_chroma 均保留。最初因隔离环境缺少 posthog 而未完成的 `vector_db_20260907_original` 也保留，未作为正式库使用。

本次通过暂停部署用户自身后端进程、完成备份与原子补丁后，以退出信号触发已有 systemd Restart=on-failure 重启，未修改 systemd 单元；服务于 05:57:36 UTC 完成启动。

如需回滚，先检查并执行 `/home/zxqs_ep/data/vector-migration-20260907/rollback.py --apply`（使用 edu-ai Python）。该脚本只回退本次仍与迁移结果一致的注册表记录及 VECTOR_DB_PATH，保留新文件与新向量库；若记录后来有修改则中止，要求逐字段合并。无需恢复整个 PostgreSQL 数据库。脚本仅做过 dry-run，未执行回滚。
