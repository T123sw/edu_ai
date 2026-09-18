# 课程准备第一阶段迁移至 DeepSeek Harness

## 范围与行为

附件理解（`input_document`）和需求归纳（`intent`）由 `DeepSeekHarness` Python SDK 的 `sdk-minimal` 运行层执行模型与 MCP 工具循环。生产工厂已安装 `HarnessIntakeAdapter`，不再在这两个阶段运行原 `ResearchModelAdapter` 的直接 function-calling 决策逻辑。研究、路径规划和审阅继续使用原运行层；本次不是整个课程准备流程的运行层迁移。

链路：用户描述/附件 → 原有授权与文件解析 → Harness + 阶段 MCP 工具 → 原文引用与业务契约校验 → SQL checkpoint → 下一附件片段或需求归纳 → 研究阶段。

- 附件阶段仅挂载 `record_input_document`；需求阶段仅挂载 `save_preparation_brief`。
- 禁用 shell 和文件编辑工具。SDK 工作目录与 home 每步隔离，工具访问经随机令牌保护的本机 MCP bridge。
- 原文校验、来源限制、明确设置优先级、解析失败、逐段检查点恢复和恢复时重新授权沿用原业务代码。
- 必须通过 MCP 提交唯一结果。纯文字、不同的二次提交、模型截断、SDK 异常均不能冒充成功，也不回退到旧决策循环。
- Harness 内部每次模型请求经本机传输适配器，发请求前预留预算，响应后记录实际用量及 `runtime=deepseek-harness`。单步最多四次上游请求（含备用候选），并执行上下文、输出和时间限制。
- 传输适配器取得非流式完整响应并检查协议，再转换为 SDK 所需的 SSE。工具循环、工具执行调度和会话仍由真实 Harness 执行。MCP 提交只暂存本步结果，业务持久化在完整运行与校验成功后执行。

## 验证

证据位于 [artifacts/2026-09-18-preparation-harness](artifacts/2026-09-18-preparation-harness/)。

- 新增 Harness 定向测试 12 项通过：包含真实已安装 SDK 与 MCP 子进程对模拟模型服务的完整调用，确认仅暴露当前阶段工具、两次模型调用均计量；覆盖纯文本、冲突提交、截断、SDK 异常、预算拒绝、上下文超限、次数上限及后续阶段继续走原适配器。
- 课程准备完整回归 **173 项通过、77 项跳过**，结果见 [regression.log](artifacts/2026-09-18-preparation-harness/regression.log)。未配置隔离 PostgreSQL 测试数据库的用例及相应 SQLite 不支持场景跳过，不将其计为通过。
- 真实 `deepseek-v4-pro` + Harness 验证通过：两份合成附件分别识别为岗位要求和学习背景；正确归纳面试目标、120 分钟、仅附件来源及不涉及模型训练，进入 `research`。包含附件恶意指令干扰、已有偏好和本次用户要求的优先级验证。
- 真实测试记录 8 次模型调用、25,692 tokens；全部调用的原始响应带 Harness 运行层标记。未调用网络检索。

真实验证止于第一阶段和研究权限交接，没有重跑整课制作。运行服务未重启，前端构建未更新；本记录是代码与隔离验证结果，不代表已部署。
