# PBL 多运行环境上线与正式端到端验证

2026-10-17：前端已发布，四类真实项目的生成与八步页面流程最终全部通过；不能认定生成内容完全无误。新发现的 Python 协议兼容修复已通过隔离回归，仍待再次重启后端。当前进程为 PID 1852133、15:56:29 UTC，早于该修复；本机 `sudo -n` 提示需要密码，未代替用户强杀服务。

## 发布范围与线上版本

基于当时最新实验页面快照 `/tmp/edu-experiment-unified-scroll-source`，仅叠加 PBL 前端和共享模板目录。旧基线构建的 481 个文件逐一复现一致；新前端构建、PBL 范围类型检查通过。16:01 发布后全部 481 个文件通过 Nginx SHA256 校验，保留旧资产及入口备份。

16:06:31 另一次 HyperFrames 发布基于本次版本继续上线。已确认其 55 个 PBL 源文件/共享目录文件与本次快照一致，并核对当前 169 个发布文件的 Nginx 哈希。没有覆盖或回滚该后续发布。详见 [release.json](release.json)、[scope.json](scope.json)、[源码哈希](source-sha256.json)。

支持范围仍为 React/React TS、原生 JS/TS、Vue、Svelte、HTML/CSS、Node 无请求体接口。八模板运行矩阵见[此前隔离验证](../2026-10-17-pbl-runtime-expansion/README.md)；本轮正式环境实测四种，不把隔离验证说成八种全部线上实测。

## 真实项目结果

使用独立测试账号，经正式页面、真实后端、模型和 Sandpack/CDN 执行。参考代码仅通过账号限定的只读数据库导出供自动化填入编辑器，未由公开 API 暴露。账号口令、令牌和参考答案保存在受限临时目录，不在本报告中。

| 项目 | 模板 | 步骤 | 最终累计检查 | 完整页面流程 |
| --- | --- | ---: | ---: | --- |
| 温度换算与重置 | vanilla | 2 | 7 | 通过 |
| 健康检查与平方查询 | node | 2 | 5 | 通过 |
| 活动报名与重新填写 | vue | 2 | 7 | 通过 |
| 打字统计与清空 | react-ts | 2 | 5 | 通过 |

八步均实际编辑多文件、预览、执行服务端累计检查；适用时运行 Sandpack 即时测试。空骨架拒绝、语法错误拒绝、修改后旧结果失效、恢复后通过、保存刷新和 1440/390px 无横向溢出均通过。逐项目结果与截图见同目录 `*-live.json`、`*-1440.png`、`*-390.png`。

三个前端项目另做 19 组独立预览操作。Node 的 7 组正常/缺参/常规非法参数 HTTP 场景及修改模块后的自动重启、恢复通过；额外无效输入测试有缺陷，见下文。旧版 `react-app-v1` 双文件项目预览交互和 6 项即时测试通过，原文件未改。未登录 401、旧 revision 保存 409 且文件不变、重复 runId 不新增记录均通过。

初始四次生成中三项成功，原生 JS 先后因协议解析和空文本误判失败；修复后第二次任务重试成功，不能把最终四项成功当作一次生成成功率。Node 初始流程有一次内部修复，Vue/TS 无内部修复。各轮原始结果、排队在内的耗时见 [generation-initial.json](generation-initial.json)、[generation.json](generation.json)、[vanilla-retry-before-empty-fix.json](vanilla-retry-before-empty-fix.json)、[vanilla-retry.json](vanilla-retry.json)。

## 本轮定位和修正

1. **显式 UI 引擎字段被拒绝**：模型写出 `engine: "ui"`，原解析器报多余字段。现只将这个无歧义标记归一为既有 UI 检查结构；未知引擎、缺少断言等仍拒绝。没有更改业务通过标准。Python 修复与真实旧格式的等价解析、错误引擎拒绝测试通过，后端全量 242 通过、6 跳过；此项尚待重启加载。验收字段说明已补充，后续调用可立即读取。
2. **正确的空文本被误判**：空行内元素自然成为零尺寸，旧检查将它误报不可见。现在允许唯一、仍在 DOM 且未被 CSS 隐藏的空文本目标；缺失、重复、显式隐藏仍失败，单独的 visible 断言仍保持原含义。15 项新旧运行器回归通过；失败快照的原代码和原检查不变，3 项复验全部通过，见 [empty-text-original-retest.json](empty-text-original-retest.json)。服务端每次新启动 Node 检查进程，因此该修复已生效，正式生成与页面复验也通过。
3. **不支持能力的规划说明矛盾**：移除“能力不足可交付待接入计划”的旧说明，同次规划先按实际能力决定是否返回 unsupportedGoal，不增加模型审阅。初次 JSON 请求体目标错误地进入生成并最终失败；修改说明后，新目标明确返回 UNSUPPORTED_PROJECT_RUNTIME，未发布伪项目。见 [unsupported-before.json](unsupported-before.json)、[unsupported.json](unsupported.json)。

以上均为通用协议、运行器和生成说明修改，没有加入温度换算器、报名表或计算器专用规则。

## 已知问题和实际边界

- **生成内容覆盖仍不足**：Node 示例对 `n=Infinity` 返回 200 / `{"result":null}`，对纯空格返回 200 / `{"result":0}`；模型生成的检查没有覆盖这些无效输入。独立结果明确记为失败，未修改示例答案或放宽预期来宣称通过。见 [node-independent.json](node-independent.json)。本轮没有宣称解决所有生成质量问题。
- **繁忙时检查返回 503**：运行器容量为 2；同时生成和操作多个项目会遇到暂不可用。Node 和 TS 的首次页面测试各遇到一次；保留日志/跟踪，降低测试并发后完整复验通过。这不是错误代码通过，也不是一次运行全部成功。
- **兼容修复仍待重启**：`sudo systemctl restart edu-ai-backend`。用户尚未确认本轮新增 Python 修复的重启；当前线上主要通过字段说明避免生成该额外字段，解析容错尚未激活。
- 依赖外部 Sandpack/CDN。Vue TS 尚未启用；Node 仅无请求体 HTTP，Python、真实数据库、外部服务不在当前运行范围内。

[汇总结果](verification.json)区分线上测试、隔离回归、已生效修复与待重启修改。浏览器流程测试保留于 `frontend/tests/live-learning/pbl-runtime-live.spec.ts`；独立诊断脚本在 [test-scripts](test-scripts/)，只使用本轮专用测试账号和私有材料，不得套用真实用户工作区。
