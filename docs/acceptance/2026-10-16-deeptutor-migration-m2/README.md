# DeepTutor 迁移 M2 接入与验收

2026-10-16：模型、持久任务和资料适配的主体代码已完成，未部署。真实模型的普通出题与已解析 PDF 仿卷链路通过；生产 MinerU 解析返回 401，因此 M2 全部验收尚未完成。考试蓝图、作答、评分和页面仍在 M3–M5，`exam_ready=false`。

入口：[迁移计划](../../architecture/2026-10-16-deeptutor-migration-plan-cn.md)、[服务安装与协议](../../../services/deeptutor/README.md)、[业务适配](../../../backend/src/app/exam_generation)、[生成 API](../../../backend/src/app/api/exam_generations.py)。

## 实现

- 提交时冻结并加密用户模型与解析器配置，包含环境默认值。执行时解密，通过请求上下文传入真实上游 SDK，保持非管理员 owner 隔离，不改共享模型目录。保留现有 Edu_AI 的 DeepSeek/Qwen 思考开关策略。
- 新增 `exam_generate` 工作流并注册到现有持久执行器。私有记录保存输入、文件 hash、配置密文、解析结果、session/turn 映射、原始结果和事件游标；公共任务只持有生成记录 ID。
- 事件分批写入独立记录，与游标在同一事务中提交；失败重连从已提交游标继续。重复请求绑定完整输入，显式重试建立新记录。补齐公开任务创建后、队列入队前崩溃的恢复。
- 复用个人资料权限读取，提交和执行时核对文件 hash。正文、布局和图片进入上游已有解析目录协议；不重复调用上游 PDF 解析。资料角色目前由请求明确指定，自动识别属于 M3。
- 保留原 Explore/Plan/Quiz、修复和工具实现。补齐启动默认 agents 配置、受信请求内模型适配和内置工具范围；M2 默认只允许自动挂载 `read_source`，其他工具需部署配置与验证，没有删除实现。
- 原始答案只在后端保存。上游 turn 为 completed 还不足以成功：必须有成功结果、零失败题、实际结果数量与目标一致；这仍不替代 M3 的独立蓝图与语义检查。

## 自动验证

| 验证 | 结果 | 证据 |
| --- | --- | --- |
| 上游专项与模型选择回归 | 227 passed | [日志](upstream-tests.txt) |
| 最后一次中英仿卷提示变更后的出题专项 | 54 passed（包含在上项范围内，不重复计数） | [日志](question-final-tests.txt) |
| 服务、补丁、来源等价性、并发模型与 SDK 隔离 | 24 passed | [日志](service-tests.txt) |
| 完全隔离的后端、客户端、队列、完成与恢复回归 | 57 passed，1 warning | [日志](backend-isolated-tests.txt) |
| 真实服务进程强杀后重启 | 原 turn 明确失败，同编号不再调用模型，另一 owner 404 | [结果](restart.json) |

共 308 项不同测试通过。进程重启检查使用受控 HTTP 模型替身，真实模型结果另列；不把替身检查当作生成质量验收。固定源码和补丁检查、`pip check` 通过。

## 真实模型样本

模型为当前已配置的 `deepseek-v4-flash`，材料为自行构造的排序知识文本与两题 PDF。业务记录、文件和服务运行目录独立，未向正式用户提交新考试。

| 样本 | 结果 | 时间 | 模型用量 |
| --- | --- | --- | --- |
| 普通资料 → Explore/Plan/Quiz | 1 选择＋1 填空，2/2 完成 | 22.51 秒 | 8 次调用，21,256 tokens |
| 文本 PDF → pypdf 验证解析 → 上游抽题与逐题生成 | 1 选择＋1 填空，2/2 完成 | 8.06 秒 | 3 次调用，6,108 tokens |
| 调整仿卷新题提示后的再次生成 | 1 选择＋1 填空，2/2 完成 | 11.94 秒 | 详见结果内 usage_summary |

[普通资料结果](custom-result.json)、[仿卷链路结果](mimic-result.json)、[提示调整后的结果](mimic-new-question-result.json)、[合成 PDF](sample-paper.pdf)、[输入文本](sample-context.txt)、[原始运行摘要](real-generation.json)。普通资料样本的验证早于最后一次仿卷提示调整；提示调整后另跑了仿卷和出题回归。

上述 PDF 路径使用验证脚本显式提供的 `pypdf-validation-only`，不是生产降级，不验证扫描 OCR、图片理解或 MinerU 的远端服务。生产路径实际调用 MinerU 返回 `HTTP 401 / user authenticate failed`，尚未取得可用解析结果。解析适配的等价性由夹具检查正文、布局、图片字节及上游抽题器读入结果，不能替代真实 MinerU 验收。

内容检查也发现质量缺口：原仿卷提示偏向影射原题，曾直接复制题干；修订后样本第一题从快速排序偏移到归并排序，第二题仍与原题非常接近。因此这里的“通过”只表示链路、结果保存、题型和数量，不表示逐题考点与新颖性全部合格。M3 应优先加入蓝图约束、原题稳定 ID 与逐题语义核对，不能仅靠提示词宣称已解决。

首次样本还暴露了事件提交性能问题：模型用时约 13 秒，逐事件数据库提交使总耗时达到约 290 秒；改为事件批量事务后普通出题约 23 秒，仿卷约 8 秒。原有思考设置未传递时普通样本在 480 秒上限处取消。保留这些观察，不将小样本耗时当作生产容量保证。

## 回归隔离事故与处置

扩展到旧任务回归时，旧测试只使用临时文件目录，项目 `.env` 却启用了 PostgreSQL 持久化，导致共享库的历史测试夹具 `job-1`、`legacy-job`、`course-1/report/report-1` 被写入，并造成两项归属测试互相影响。这次错误运行不作为验收结果。

已核查回归时间窗口：没有其他任务记录被更新，近期资料变动仅为上述测试资料。两个测试任务按可用的历史事件快照恢复，新建的测试资料及两个近期版本清理；没有事前精确行快照，因此不声称逐字节恢复了未记录的测试夹具状态。处置见[记录](isolation-remediation.json)。

新增独立回归入口，在读取项目配置后强制替换所有持久化模式、数据库地址和目录，并阻止 dotenv 再加载。最终 57 项后端回归全部在此隔离入口通过。真实模型样本和进程重启检查本身使用独立存储；不能把它们的 `production_writes=false` 字段扩大解释为本轮所有测试从未触及共享库。

## 复现与下一步

后端回归使用已经安装后端依赖的 Python：

```bash
python services/deeptutor/scripts/verify_m2_backend.py
```

服务检查：

```bash
DEEPTUTOR_HOME=/tmp/deeptutor-service-tests services/deeptutor/.venv/bin/python -m pytest services/deeptutor/tests -q
services/deeptutor/.venv/bin/python services/deeptutor/scripts/verify_m2_restart.py
```

真实生成脚本需后端 Python 和 `PYTHONPATH=backend/src`。默认调用 MinerU；只有显式传入 `--native-pdf-validation` 才使用合成文本 PDF 的验证解析器。源码安装见服务 README，上游 pytest 在新目录运行前需调用 `deeptutor.services.setup.init.init_user_directories()` 初始化默认配置。

后续先更新可用的 MinerU 配置补齐真实 PDF 验收，再推进 M3 的长卷抽取、题型扩展、语义对应和逐题检查点。前端仍未接入，未运行生产发布、浏览器考试闭环或大规模并发验收。
