# PBL 标准测试接入验收

状态：本记录为首次实现与隔离验证，当时未发布前端、未重启生产后端；后续已上线并完成正式环境验证，见[上线记录](../2026-10-17-pbl-sandpack-online/README.md)。实施范围见[计划](../../architecture/2026-10-17-pbl-sandpack-tests-plan-cn.md)。

## 实现

- 新增 `engine: sandpack-jest` 检查，保存完整标准测试文件；React 18.3.1 与 React Testing Library 14.3.1 支持逻辑、渲染、交互和异步断言。布局及旧检查继续使用原 Playwright 执行器。
- 页面新增即时测试，复用 SandpackTests；服务端在无认证的独立浏览器中使用同一测试组件、依赖、源码组装及结果适配器。客户端不能提交测试或直接写入通关结果。
- 保留代码与验收两次调用、前序代码与测试上下文、累计执行及本步验收修复。普通 requiredAssertions 作为规划提示，不再因断言类型不同阻断正确行为；布局窗口与几何要求仍保留。
- 新提示资源使用 build-pbl-project-v4，避免旧进程直接读到新接口提示。旧项目继续读取旧 UiCheck，没有批量改写历史工程。
- 即时测试绑定冻结的源码快照，代码变更标为过期；超时可重跑。正式结果继续绑定版本、任务、runId 和代码哈希，保留权限、CAS 和幂等。

## 原生兼容性实测与修复

安装版本为 sandpack-react 2.20.0，固定 bundler 为 2-19-8。原生测试可执行 React 组件、纯函数、异步断言和参数化用例，但实测 jest-lite 会漏报钩子错误，且异步 beforeAll/afterAll 与完整 Jest 行为存在差异。

适配层继续复用原生注册、运行和 matcher：包装测试函数以检查实际断言执行，等待异步准备，并将钩子异常/未完成状态合入最终报告。钩子消息只接收来自当前测试 iframe 和固定 bundler origin 的事件。空文件、未执行、跳过、语法错误、准备与清理异常都不能计为通过。此层没有任何具体项目业务规则。

## 生成实验

模型使用隔离环境继承的默认模型配置，未启用额外审阅。生成存储为独立 SQLite，页面核验使用独立 PostgreSQL 数据库 `pbl_acceptance_20261017_native`，正式业务数据未写入。

| 项目 | 首轮 | 调整后的新生成 |
| --- | --- | --- |
| 活动报名表 | 2 步成功，5 次模型调用 | 2 步、6 项标准检查成功，5 次调用，95.78 秒 |
| 阅读清单 | 6 次调用后失败，前序整行 textContent 精确比较阻断新增控件 | 2 步、6 项标准检查成功，5 次调用，104.49 秒 |

首轮失败说明标准测试不能自动消除验收设计错误。修复采用通用提示：按需求定位独立文字、考虑后续增量、修复代码时读取标准测试源码中的实际定位与断言；没有阅读清单专用分支。两轮合计 21 次实际模型调用。

## 自动验证

- PBL 后端：基础回归 205 通过；原先跳过的 6 项 PostgreSQL 用例随后在另一专用库全部通过，共 211 项。
- 新旧运行器与结果适配：21 通过。包含禁用/空列表、同名条目隔离、radio、纯函数、异步检查、错误实现拦截、空/跳过/语法错误、钩子错误、参数化测试，以及旧布局和定位回归。
- 最终代码的类型、专项 ESLint 和前端构建通过。
- 真实页面两项目全部通过：4 步、12 项标准检查，初始工程拒绝、逐步编辑、累计服务端核验、浏览器即时测试、修改失效、错误代码在两端失败、恢复与刷新，以及 320/390/1440px 无横向溢出。见 [signup-flow.json](signup-flow.json)、[reading-flow.json](reading-flow.json) 及同目录截图。
- 即时测试的完整结果面板另外验证了 1440/390/320px，无页面脚本异常与横向溢出，见 [native-layout.json](native-layout.json)。标准测试检查点在发布前中断后可恢复，复用已生成代码与测试并重新执行，不重新调用模型。

汇总见 [verification.json](verification.json)，实现文件校验值见 [source-hashes.json](source-hashes.json)。

生成验收的 5 个定向缺陷均被识别：按钮失去禁用状态、重新填写残留结果、切换一项误改全部、删除一项清空全部、允许空白条目。见 [mutations.json](mutations.json)。

页面接入实测还修复了初始化与重编译问题：使用 SandpackLayout 注册延迟初始化锚点，固定一次运行的 files 对象，并延后 onComplete 的上层状态更新，避免开发模式重复初始化、结果回调触发重新编译，以及已销毁测试环境引起页面报错。即时测试错误边界保护整个工作区。

## 运行边界

本轮仍是本地 React 双文件项目，不代表已支持 Node 后端或 Python。组件测试验证逻辑与 DOM 行为；真实布局由 Playwright 验证。原生测试需要访问 Sandpack bundler 和依赖 CDN，网络不可用或执行超时不会产生通过证据，生成候选保留供重试。

生产服务没有重启，前端没有发布。当前验证基于本地改动与隔离服务。

## 复验入口

```sh
python scripts/pbl/isolated.py pytest backend/src/tests/pbl -q
# PostgreSQL 用例显式提供独立测试库的 PBL_TEST_DATABASE_URL；不使用生产库。
cd frontend
node --import tsx --test scripts/pbl-native-validation.test.mts scripts/pbl-project-validation.test.mts src/pbl/nativeTests.test.ts
```

真实模型生成入口为 `scripts/pbl/native_acceptance_generate.py /tmp/<新的验收目录>`；真实页面用例为 `frontend/tests/live-learning/pbl-native-live.spec.ts`，需提供生成目录、隔离 API 和本地前端地址，并在隔离 API 数据库中装入对应产物。测试代码不包含模型密钥或真实用户凭据。
