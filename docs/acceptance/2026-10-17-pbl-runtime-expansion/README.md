# PBL 多模板、多文件运行环境扩展

本轮修改代码并在隔离环境验证，没有发布生产前端，也没有主动重启生产后端。验证使用独立 SQLite / PostgreSQL 数据库、测试账号、真实配置的模型和真实 Sandpack/CDN，没有用模拟接口替代生成或运行。

## 实现范围

原来的扩展只接入标准测试，本轮将运行类型和工程结构一起扩展。共享目录 `shared/pbl-runtimes.json` 记录实际启用的模板、默认入口、基线文件和依赖。新项目保存 `sandpack-project-v1`、`runtime` 和完整文件清单，支持 1–32 个文件、512 KiB；宿主管理 package.json、启动和测试文件。

| 模板 | 预览与验收 | 边界 |
| --- | --- | --- |
| React / React + TypeScript | Sandpack 真实预览、Jest、页面/布局检查 | 本地浏览器项目 |
| 原生 JavaScript / TypeScript | Sandpack 真实预览、Jest、页面/布局检查 | 本地浏览器项目 |
| Vue / Svelte | 真实页面交互、布局检查 | 不套用 React Testing Library |
| HTML/CSS | Static 客户端、页面/布局检查 | JavaScript 交互请选择 vanilla |
| Node / Express | Nodebox 服务、HTTP 状态/JSON/文本、页面检查 | 只支持不带请求体的请求；CommonJS 和 ESM，多文件路由/函数 |

Vue + TypeScript 模板反复启动超时，固定依赖版本后仍不稳定，因此未开放给生成模型。Python/FastAPI、真实数据库、操作系统工具和外部服务不属于当前能力。

Nodebox 的带请求体 HTTP 在隔离和不受网络拦截的浏览器中均复现挂起，参见上游 [sandpack#1190](https://github.com/codesandbox/sandpack/issues/1190)。本轮不声称支持通用 CRUD 后端。HTTP 检查结构明确拒绝请求体；需求分析允许输出 `unsupportedGoal`，不把用户目标静默改成查询参数方案。修复 data 包装解析顺序后，真实 JSON POST 目标在一次规划调用、2.37 秒内明确返回不支持。

Static 客户端注入的全局脚本与普通脚本中的顶层变量有冲突，当前只开放 HTML/CSS；原生 JS 交互使用已验证的 vanilla 模板。

## 生成与学习流程

规划按需求选择模板和工程结构。正常模型调用数仍为 1 次规划 + 每步 1 次代码 + 1 次验收，修复才追加调用，没有增加独立模型审阅。代码生成后先运行前序检查，验收阶段读取本步完整代码、前序代码、前序验收及实际报告；只允许修复本步验收。

模型的验收 schema 只包含当前模板可执行的引擎，避免 Vue/Node 被误生成 React 测试。保留有限修复、检查点恢复、用户权限、源码哈希、版本、幂等与并发保存保护。启动超时与断言失败分开处理：运行环境不可用时允许以原代码在新环境重试一次，仍不可用则保留检查点，不让模型修复正确代码。

编辑器复用 Sandpack 文件导航、代码标签、预览、Console 和 Tests。Node 服务通过宿主启动文件处理嵌套入口及 CommonJS/ESM；编辑后等待文件写入确认再重启服务。即时测试冻结整份配置，避免结果更新重建运行器并打断 Jest；最终通过仍取服务端独立结果。

每项页面/HTTP 检查在独立匿名上下文运行；服务端限制外部资产域名，阻断本机服务和 WebSocket。Nodebox 页面和 ServiceWorker 访问本机探针均被拒绝。前后端不会在 Python/Node 宿主执行学习者代码。

## 验证材料

真实模型生成了四类两步项目：

| 项目 | 模板 | 最终成功轮耗时 | 模型调用 |
| --- | --- | ---: | ---: |
| 打字统计器 | react-ts | 465.66 秒 | 7 |
| 温度换算器 | vanilla | 337.60 秒 | 7 |
| 活动报名页 | vue | 740.13 秒 | 7 |
| 健康检查与平方查询 API | node | 244.06 秒 | 7 |

人工复查发现第一轮原生 JS 的页面要求被模型写成纯函数测试，覆盖不充分。已把原生 JS/TS 的 ui_scenario 路由到真实 UiCheck，function_case 才使用 Jest；重新生成的两步项目已通过累计验收；只移除按钮事件、保留正确换算函数的独立反例被准确拒绝，见 vanilla-ui-mutation.json。旧材料保存于 diagnostics/，不作为最终语义覆盖证明。

这些是修复期间的实际成功轮，不是一次生成成功率。此前失败涉及 CLI 循环导入、测试运行环境不匹配、模型响应包装、Vue 错选 Jest、模板依赖与 CDN 启动超时；诊断结果保留，不宣称任意项目均稳定生成。

最终完整后端回归 241 通过、6 跳过；生成契约专项 74 通过。旧页面运行器、标准测试与结果适配合计 21 通过。PBL 范围类型检查和完整前端构建通过。新运行器矩阵首轮 12/13 通过，vanilla-ts 的一项外部启动超时在加入仅运行环境重连后定向复验通过（保留首轮失败日志）；覆盖全部八个已启用模板及 Node 两种模块形式。React TS、原生 JS、Vue、Node 四类完整页面流程均通过，合计八步；四类独立预览交互通过，Node 编辑后的自动重启也通过。重新生成后的原生 JS 项目也在重新加载的隔离后端完成完整页面复验（3.7 分钟），8 项累计验收与即时函数测试通过；保留前一次抢在自动编译结束前点击导致的自动化时序失败记录，最终测试等待实际交互结果。实际记录见 logs/、ui/ 与 verification.json。

前端测试覆盖真实编辑、预览、累计检查、标准即时测试（适用模板）、错误实现、恢复与保存刷新、1440/390px 布局。另有独立预览交互与 Node 修改后服务重启测试。运行依赖外部 Sandpack/CDN，冷启动有波动；不可用结果不会记为通过。

## 重放

Python 测试必须通过隔离入口，不能直接加载生产 `.env`：

```sh
export PATH=/home/zxqs_ep/miniforge3/envs/edu-ai/bin:$PATH
python scripts/pbl/isolated.py pytest backend/src/tests/pbl -q
python scripts/pbl/runtime_acceptance_generate.py /tmp/pbl-runtime-new vanilla vue react-ts node-read
cd frontend
node --import tsx --test scripts/pbl-runtime-validation.test.mts
```

页面测试为 `frontend/tests/live-learning/pbl-runtime-live.spec.ts` 与 `pbl-runtime-preview.spec.ts`，依赖单独测试 API、测试账号和已导入的生成材料。环境变量为 `LIVE_FRONTEND_URL`、`PBL_RUNTIME_API`、`PBL_RUNTIME_LIVE_DIR`；不得指向生产账号和数据库。正式发布时需要同时发布前端、共享模板目录和后端，并重启后端加载 v5 生成流程；已有旧项目保留原协议。
