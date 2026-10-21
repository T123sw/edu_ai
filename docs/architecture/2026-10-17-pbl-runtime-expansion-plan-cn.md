# PBL 多运行环境与多文件扩展

状态：功能及隔离验收已完成，尚未发布生产。承接已上线的 Sandpack 标准测试，不将测试扩展误称为运行类型扩展。

## 目标

需求分析选择运行环境，项目保存模板、入口、依赖和文件清单；代码生成、预览、即时测试、服务端验收、恢复与辅导使用同一份配置。保留现有 JavaScript 算法练习、React 双文件项目及旧检查。没有具体业务项目的专用规则，也不增加模型审阅步骤。

## 实施顺序

1. 实际验证当前安装的 Sandpack 模板与 Nodebox，包括浏览器前端和 Node HTTP 服务。以可执行证据区分已支持和外部能力不可用，不把编辑器能显示源码当作运行成功。
2. 引入版本化运行配置和模板能力目录，移除固定 React 类型、两个文件及固定入口限制。允许有界多文件和明确版本的 npm 依赖；宿主管理测试与运行清单，学习代码仍只在隔离浏览器内执行。
3. 生成计划选择模板和工程结构；后续代码与验收分开生成，完整继承配置、前序文件及验收。测试形式按能力选择：标准 Jest、页面操作/布局、Node HTTP 接口；不把所有项目套成 React。
4. 编辑器、文件导航和预览复用 Sandpack 的能力，服务端使用相同模板、文件及依赖启动独立运行环境。通关仍由服务端结果决定，绑定工程哈希、版本及检查编号。
5. 针对 React 多文件/TypeScript、原生 HTML/JS、Vue/Svelte 和 Node/Express 做运行器及真实生成验证；覆盖错误实现、累计回归、保存刷新和旧项目兼容。Python/FastAPI 不是 Nodebox 环境，给出明确不支持说明，不伪装为网页项目。

## 交付判据

- 已启用的每类环境都有真实运行与失败反例证据；外部运行时失效时明确报错，不记通过。
- 至少多种非 React 项目从生成到页面编辑、预览、检查完成完整链路。
- 文件、依赖和模板由可信项目配置驱动，客户端不能替换验收或放宽能力。
- 保留代码/验收分离、前序回归、有限修复、检查点恢复、权限、CAS 和幂等。
- 报告明确已实现、实际验证、部署状态与剩余限制。

## 依据

官方 [Usage](https://sandpack.codesandbox.io/docs/getting-started/usage) 提供模板、文件、依赖和入口配置；[Sandpack Client](https://sandpack.codesandbox.io/docs/advanced-usage/client) 区分 Runtime、Static 与 Node 客户端；[Nodebox 源仓库](https://github.com/Sandpack/nodebox-runtime) 描述浏览器内 Node 运行环境。实际兼容性以本机安装版本和本轮实验为准。

## 实际能力边界

已接入 React/React TS、vanilla/vanilla TS、Vue、Svelte、static、Node 共八个模板。Vue TS 经过依赖固定仍反复启动超时，未开放。static 当前限 HTML/CSS，动态原生 JS 使用 vanilla。Node 只支持无请求体接口；请求体挂起已在不限制网络的浏览器中复现并对应上游 sandpack#1190，未伪装为完整 CRUD 后端。实施与原始失败、最终验证证据见[验收记录](../acceptance/2026-10-17-pbl-runtime-expansion/README.md)。
