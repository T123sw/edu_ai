# 新版学习配置补齐与业务验收（2026-09-22）

**配置已在业务进程生效，默认网站桌面和窄屏的新建课程端到端验证均通过。**

用户再次重启后，进程为 `1492723`，启动于 `2026-09-22 06:31:55 UTC`，应用来源 `2e088914`。五个运行时开关均为 true，实际课程接口的 `sessionPersistence`、`progressPersistence`、`agentRuntime`、`enrichmentEnabled`、`preparationEnabled` 和练习接口 `checks_enabled` 均为 true。此前因管理员认证而未重启的状态已解除。

## 配置与部署

- 根目录业务 `.env` 已开启 `LEARNING_SESSION_V1_ENABLED`、`LEARNING_PROGRESS_V1_ENABLED`、`LEARNING_AGENT_V1_ENABLED`、`LEARNING_ENRICHMENT_V1_ENABLED`、`LEARNING_PREPARATION_V1_ENABLED`。其他模型、预算、存储与功能设置不变，文件权限维持 0600。
- 数据库已是 `20260918_0036`，本轮没有执行 schema 迁移。七项学习服务初始化检查通过，没有启动第二套业务 worker。
- Nginx 默认网站已更新为实测前端构建 `e0003454`。其 frontend Git tree 与本轮来源一致，后续提交仅文档；备份旧构建、先发布资源，再原子替换首页，保留旧哈希资源。HTTP 内容核对和默认网站登录检查通过。
- 现有七条学习 overlay 已备份，未发现需要转换的已完成标记或自评。未标明版本的旧位置不推断为新版版本化事实；原始记录、旧练习答案和文件保留。旧会话由现有首次进入逻辑导入；`LEARNING_SCOPED_ROLLOUT` 保持未开启。

## 默认网站真实验证

测试直接访问 `http://127.0.0.1`，经 Nginx `/backend` 到业务 8001、业务 PostgreSQL 和真实 worker，使用独立测试账号及每个视口独立新上传的 DOCX，未用本机验证代理、旧课程回读或 mock 替代端到端。

| 视口 | 整课交付秒数 | 浏览器总秒数 | 结果 |
| --- | ---: | ---: | --- |
| desktop | 221.88 | 346.74 | passed |
| narrow | 268.31 | 348.97 | passed |

逐份验证两节点各三类精确版本资源、新版会话初始化、报告真实锚点且无原始标签、习题首题提交与刷新恢复、课堂全部页和提交后显答、旁白/页面实际推进、字幕不遮挡画布、文本边界与图片解码、横向溢出。两轮均无页面/控制台/HTTP 错误；35 条已完成会话请求均返回 200；trace 另有 1 条未记录到响应（status=-1），原样保留且不计入 HTTP 成功数，见 [请求记录](production-session-requests.json)。

另在上一轮合成课程上实际提交一条学习答疑，约 6.59 秒完成；进入与读取关联同一会话，回答已保存并从知识点历史回读，没有触发资料生成或修改。它是补充冒烟，不计作第三轮新建课程端到端。

桌面课程没有内容返工；窄屏课程因节点目标 `node-2-branch-tracing:o4` 缺少学习检查对应关系，定向修订一份习题后通过，其他资源保留。该修订与学习时长无关。

所有整课模型 completion 均经原生 DeepSeekHarness，请求 `deepseek-v4-flash`、供应商返回 `deepseek-flash`，详见 [账本](production-ledger.json) 和 [协议检查](production-transport.json)。学习时长仍为 advisory，未改为交付门槛；整课交付时间不等于单份报告生成或学习时长。全部本轮备课任务终态已结清预留。

## 证据与边界

- [状态和实际接口开关](status.json)
- [两轮浏览器结果](production-browser-results.json)
- [新版逐题检查截图](desktop-versioned-quiz.png)、[窄屏报告](narrow-report.png)、[字幕截图](desktop-subtitles.png)

本次确认主流程在业务部署中生效，不表示全部功能专项完成。真实 TTS 解码/音频时钟、完整联网/长资料/记忆生命周期/局部修改/故障并发矩阵仍未全部覆盖；准备交接在本轮验证启用状态，未新增一次局部制作任务。原学习答疑路径不因开关启用自动变成原生 Harness，本轮不宣称整个平台所有模型调用均已迁移。

配置、旧构建和旧记录备份以及原始 trace/回执均保存在本机私有目录 `/tmp/edu-ai-learning-enable-20260922`，不提交凭据。后端、Nginx 和 TTS 保持运行。
