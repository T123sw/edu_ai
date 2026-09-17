# 学习 Agent P6：迁移、切换与完整验收

日期：2026-09-17。业务库和业务功能开关未变更。全部写入验证发生在隔离 PostgreSQL schema、临时资料目录或新建后删除的恢复测试数据库。

## 迁移与切换

`migration.py` 与 `migrate_self_learning_cli.py` 提供默认只读的 scan、显式 import/reconcile/activate。扫描保留全部幸存历史、原始 turn ID 和旧 session ID，未知资料版本不绑定最新版本；孤立资料、占位笔记与旧位置进入原始归档及未解决清单，不补造已丢失历史。

导入源有摘要与不可变归档，消息和事件以稳定身份重放；重复导入不增加记录。已有新事实发生冲突时不覆盖。对账核对原始消息、旧身份、导入事件回执与来源归档。激活前检查在途旧答疑和扫描后变化；旧写操作与激活使用同一个数据库锁。

`learning_rollout_scopes` 按用户和课程记录阶段。`LEARNING_SCOPED_ROLLOUT=true` 时，仅已激活范围使用新版能力，worker 按该范围挂载工具。关闭模型功能后仍读取新会话、事实和已提交个人资料，不降回旧 JSON。生产默认开关均未打开。

迁移相关验证：12 passed；迁移 0029 在 SQLite/PostgreSQL 上下行验证 2 passed。额外的 worker 工具范围用例 2 passed，确认阶段 3 用户不会挂载阶段 4/5 工具。

## 备份恢复与并发

[backup-restore.json](artifacts/learning-agent-p6/backup-restore.json) 保存实际 pg_dump/pg_restore 结果：新建隔离数据库恢复原 schema 后，逐表行数及内容摘要、资料文件摘要相同，303 条消息（151 轮加导学）和版本化完成记录可读取。CLI 的 scan/import/reconcile 也实际运行，重放 created=0、对账无不明差异。临时备份及恢复库已清理，审计摘要保留。

`test_postgres_concurrency.py` 使用两个独立子进程，不依赖 Python 锁，验证重复 enter、同事件竞争、同节点提问竞争、租约过期后的迟到写入拒绝、通知事件重投。并发与作答组合首次 20 passed、1 skipped；SQLite 不冒充 PostgreSQL 多进程验收。

## 真实用户路径

`agent-real.spec.ts` 使用真实 `deepseek-v4-pro`、真实浏览器、后端 worker、PostgreSQL 与资料存储，已串行跑通：

1. 生活例子解释变量赋值。
2. 只给一步提示，引导判断变量值。
3. 提供可跳过的理解检查。
4. 生成并保存单选练习，打开资料并提交作答。
5. 生成并保存讲解文档，打开正文。
6. 修改当前文档，生成个人新身份，核对原内容未被覆盖。
7. 打开修订资料、刷新恢复。

第七轮与最终完整浏览器验证连续通过；最终 1 passed，约 1.7 分钟含服务启动。证据为 [real-browser.json](artifacts/learning-agent-p6/real-browser.json) 和 `real-browser-final.log`。此前失败日志与 JSON 均保留，修复包括：禁止无真实收据声称已提交；格式修复分支保留必要工具；历史助手消息向模型传递时保持 JSON 协议；DeepSeek JSON 模式提示约束；通知按发生时间排序并按任务定位打开入口。

额外真实模型边界覆盖跨节点先修、换例子、含糊修改目标、提示注入、无权私有资料与传输超时。最终全部通过（real-boundaries-repaired.log，1 passed in 40.11s），各任务输出、引用和耗时见 real-boundaries.json。JSON 模式曾在工具阶段结束后返回空白；修复为显式最终答复提示，并允许一次保留工具结果的有界空响应修复，重复空响应明确失败。未放宽工具执行、轮数、上下文或截止时间限制。

实际练习 iframe 已接版本化题目快照与作答回执；新版开启时旧 practice 写入口拒绝独立保存。真实课堂 iframe 的 scene_id/版本上报与刷新定位已通过浏览器验证。

## 主设计场景映射

| 场景 | 主要证据 |
| --- | --- |
| 1 首次导学仅一次 | session repository、agent-session 浏览器 |
| 2 知识点会话隔离与恢复 | A→B→A、长历史分页、迟到回答 |
| 3 不聊天也可推进 | quiet-learning 浏览器与事实 API |
| 4 阅读不催促、不自动完成 | 阅读事件、版本与继续入口测试 |
| 5 完成、自评、检查分离 | checks、projections、理解检查浏览器 |
| 6 选区、版本与迟到回答 | readingContext、agent-turns 浏览器 |
| 7 去重、不打断 | PostgreSQL 两进程、通知重放、后台交付浏览器 |
| 8 准备任务不阻塞学习 | preparation-handoff 浏览器 |
| 9 旧引用与个人版本连续性 | 原文不覆盖、新身份、版本事实隔离、迁移测试 |
| 10 权限与偏好删除 | memory lifecycle、账户切换浏览器、无权资料真实模型 |
| 11 模型失败仍可学习 | 超时、取消重试、保存回执、quiet-learning 浏览器 |

## 最终状态

学习 Agent V1 的 P0—P6 实施与隔离验收完成。日志目录：[learning-agent-p6](artifacts/learning-agent-p6/)。

| 验证 | 结果与日志 |
| --- | --- |
| 后端整体回归（含唯一迁移 head） | 202 passed, 3 skipped, 1 warning in 862.86s (0:14:22)；backend-full-final.log |
| 最后协议与回执修改后的受影响模块回归 | 77 passed in 451.74s (0:07:31)；protocol-final.log |
| 独立 P5 检出应用暂存补丁后的 P6 迁移/切换 | 16 passed in 187.59s (0:03:07)；fresh-p6-index.log |
| 既有学习服务兼容 | 6 passed；legacy-service-final.log |
| 常规浏览器 6 组 | 23 passed；browser-*-final.log |
| 真实模型完整浏览器路径 | 1 passed；real-browser-final.log |
| 真实模型边界 6 场景 | 1 passed；real-boundaries-repaired.log |
| 前端领域单测 | 7 passed；frontend-unit.log |
| 前端 TypeScript 与 ESLint | 退出码 0；frontend-types-final.log、frontend-lint-final.log |

整体回归的跳过项为两个 SQLite 不适用的 PostgreSQL 并发用例，以及默认关闭的付费真实模型测试。对应 PostgreSQL 用例已实际运行；真实模型单独显式启用并通过。不同回归集合存在重叠，不相加为独立测试总数。整体回归启动后还有协议收尾变更，因此以最后受影响模块回归、真实模型/浏览器复验共同覆盖最终代码。

环境：Python 3.12.14、PostgreSQL 14 临时本机实例（55441）、Chromium/Playwright，真实模型 deepseek-v4-pro；后端与前端测试服务为 8016/5196。耗时为单机隔离验收观测，不是生产吞吐量或 SLA。失败日志和合成任务完整输出一并保留。

交付边界：学习侧准备工具当前交付讲解文档与练习及其修订，其他类型显式不可用；旧课程使用个人补充 manifest，不伪造整课 ready。业务库未迁移，生产功能默认关闭，尚未做生产流量下长期稳定性观测。

## 性能抽样

Intel(R) Xeon(R) Silver 4210R CPU @ 2.40GHz，40 个逻辑 CPU；单客户端、三节点四文档的合成课程，各 30 次调用。课程读取 p50/p95 为 24.445/29.033 ms，位置事件写入为 73.757/168.811 ms；实际发送 30 个位置事件。均小于设计建议的 500 ms，但使用进程内 ASGI，不包含网络/代理。完整环境与样本统计见 performance.json。

最终真实浏览器 6 轮答疑从点击到轮询确认完成为 4.00—10.13 秒。当前非流式答复，首个最终回答与完整回答一并发布；这个时长含浏览器轮询等待。每轮工具次数、模型轮数在 real-browser.json，各次传输 token 使用量见 real-browser-transport.json；未测生产并发容量。
