# PBL 多类型项目端到端验证（2026-10-17）

结论：当前模块不能认定为通用项目场景下稳定。六个新的本地前端项目只有一个完整生成并通过页面流程；五个在生成验收或前序回归阶段终止。四个后端、命令行或全栈需求超出当前运行环境能力，实际均重复规划后失败，页面未清楚说明不支持。

本轮只验证和定位，没有修改产品代码或扩大运行环境。使用线上已发布前端、隔离 PostgreSQL、完整后端和持久任务工作器、真实模型、真实 Chromium；不写生产用户数据。默认模型为 `deepseek-v4-flash`，配置来自隔离环境继承的环境默认值，当前生成器对 deepseek-v4 固定关闭 thinking。没有复制生产某个用户的私有模型配置，结果不能外推到所有模型。核心源文件在本轮前后哈希一致，见 [environment.json](environment.json)、[model-config.json](model-config.json)。

## 项目结果

用户输入原文见 [cases.json](cases.json)，总计 61 次真实生成阶段调用，没有另外增加模型审阅。

| 项目 | 类型 | 完整生成 | 已完成步骤 | 模型调用 | 终止原因 |
| --- | --- | --- | ---: | ---: | --- |
| 任务看板 | React 状态迁移、重复条目 | 失败 | 1 | 6 | 首步对整列全文精确匹配，下一步新增“前进”按钮就破坏旧断言；修复后仍未恢复兼容 |
| 单选测验 | React 作答、计分、锁定 | 失败 | 1 | 9 | 要验证未选择/已提交时按钮禁用，实际却断言 enabled=true |
| 本地记账 | React 金额校验、分类统计 | 失败 | 1 | 11 | 当前代码和实际累计浏览器验收通过，但计划指定 text 类型，当前 count + visible 被结构校验拒绝 |
| 成绩文本分析器 | React 文本解析、统计、错误行 | 通过 | 3 | 7 | 3 步、7 项累计检查，页面全流程和独立业务测试均通过 |
| 选座 | React 禁用座位、选择上限、确认 | 失败 | 0 | 7 | 验收尝试 click 已售且不可操作的 A2，定位成功但操作等待失败 |
| 两步报名向导 | React 条件校验、单选、勾选 | 失败 | 1 | 9 | 验收误以为再次点击已选 radio 会取消选择，满足条件时却期待提交失败 |
| FastAPI 待办 API | Python + SQLite + HTTP | 不支持，生成失败 | 0 | 3 | 计划把真实 HTTP 验收与 react_app 运行类型混用 |
| Express 库存 API | Node + 文件持久化 + HTTP | 不支持，生成失败 | 0 | 3 | 运行环境不接受 server.js/store.js 等服务工程 |
| CSV 命令行统计 | Python CLI + 文件/退出码 | 不支持，生成失败 | 0 | 3 | 当前仅接受 React App.jsx/styles.css |
| 全栈留言板 | React + FastAPI + SQLite | 不支持，生成失败 | 0 | 3 | 后端 HTTP 检查与 react_app 类型不匹配 |

四个不支持类型不能算“后端端到端验证通过”。本轮没有启动生成的 Python/Node 服务，也没有验证这些服务的 HTTP 或数据库行为；模块本身根本没有交付可执行的对应工程。分类结果见 [verification.json](verification.json)、[case-diagnostics.json](case-diagnostics.json)。

## 失败复核：当前步骤代码与生成验收分开判断

五个失败前端项目均提取最后保存的当前步骤代码，用独立 Playwright 操作验证需求，再原样重放生成验收。独立测试只覆盖失败时的当前步骤，不代表尚未生成的后续功能已经实现。

### 1. 禁用状态无法表达，两个不同项目复现

测验代码初始禁用提交，选择后启用，提交后禁用且锁定原选项，独立测试通过。验收的自然语言与 behaviorCases 都写“不可用”，执行动作却是 `assertion: enabled`，运行器按协议固定比较 true，反复修复后仍失败。

选座第一步正确渲染六个座位、两行三列，A2 标记已售并设置 aria-disabled，其他座位可操作。生成验收对 A2 执行 click，Playwright 按不可操作元素等待并报失败。已有动作无法把“点击被拒绝/不可操作”作为通过条件。

协议位置：`backend/src/app/pbl/project_schemas.py:93` 明确 visible/enabled 只能断言为真；运行器的动作与期望比较也遵守这一限制。这不是前端把结果显示错了。证据见 [failed-step-audit.json](failed-step-audit.json) 与 [remaining-failed-step-audit.json](remaining-failed-step-audit.json)。

### 2. 记账被非必要的断言类型约束拦截

计划要求拒绝非法金额时包含 count、text、visible；本步实际验收填写非法金额，点击添加，检查记录数仍为 0 且错误提示可见。需求没有要求错误提示必须是某段固定文字。独立测试验证了空白备注、0、负数、三位小数、非数字、空金额及随后合法添加，均符合本步目标。

绕开发布前的结构校验，仅将原样代码和原样累计检查交给正式浏览器运行器，全部通过；但 `project_schemas.py:174–181` 的 requiredAssertions 兼容校验仍拒绝该候选，耗尽修复预算后终止。没有人工改检查来制造通过，见 [failed-step-audit.json](failed-step-audit.json)。

### 3. 向导验收误解 radio 行为

早期验收曾定位代码中不存在的 result-name 等标记；最后一次代码修复已经补齐。最终失败剩余如下场景：选择线上 → 未同意条款提交被拒绝 → 勾选条款 → 再次点击已选“线上” → 提交，却期待没有结果。

标准单选按钮再次点击保持选中，因此此时应该提交成功。独立测试确认线上/线下、缺少方式、缺少同意条款、姓名去空格和年龄非法边界均符合当前步骤。生成验收仍期待错误结果。见 [wizard-failed-step-audit.json](wizard-failed-step-audit.json)。

### 4. 看板的旧检查锁死后续结构

首步检查整个 column-todo 的全文为“待办写周报”；第二步在该列加入操作按钮后，全文自然成为“待办写周报前进”。独立测试确认标题去空格、空白拒绝、同名任务独立移动、待办→进行中→完成→进行中→待办、首尾移动边界均正确；前序全文检查仍失败，当前步尚未进入新增验收阶段。

这类问题上一轮已经出现过，本轮在全新项目再次复现。当前传入模型的前序代码、检查和失败证据并未缺失；已有提示词也讲了容器文本边界，但实际修复没解决。见 [remaining-failed-step-audit.json](remaining-failed-step-audit.json) 和对应原始阶段轨迹。

## 后端与全栈能力边界没有正确传达

所有新任务统一走 `project_service`，只支持 `/src/App.jsx`、`/src/styles.css`，编译目标为浏览器，检查只支持 UI 声明式动作；没有用户后端服务生命周期、后端依赖、数据库或 HTTP 验收环境。旧函数类产物的兼容路径不意味着能创建新后端服务。

提示词要求不支持时返回 unsupportedGoal，生成器也有对应错误分支，但给模型的 ProjectPlan schema 只有成功计划结构，没有不支持结果的类型。实测四个需求都返回了不可执行的计划，各调用计划 3 次（初次加 2 次修复）后以 PBL_PLAN_INVALID 结束。这个 schema 与提示要求的不一致是需要处理的设计缺口；不能仅凭它推断全部模型错误的唯一成因。

九个失败项目均从真实页面打开核对，页面没有空白工作区或误发布，但统一显示“生成暂未完成 / 项目计划经过修复仍未通过检查”等，并继续提供重试。四个不支持类型均没有明确“不支持”说明。见 [failure-ui.json](failure-ui.json) 与 [FastAPI 页面截图](fastapi-failure-ui.png)。

## 成功样本与防止漏检的测试

成绩分析器完成三步 CodeMirror 编辑、累计检查、继续步骤、修改代码撤销通过状态、刷新恢复、退回未完成代码失败、恢复代码通过、预览和答案不泄漏检查。390/320px 外宽下预览实际宽 349/279px，均无横向溢出。见 [csv-browser.json](csv-browser.json)。

独立业务测试覆盖混合合法/非法行、空行、同名、0/100 边界、小数平均、原始行号、再次分析替换结果、无有效数据、清空全部结果，5 组通过。见 [independent.json](independent.json)。

随后对这一份新生成代码注入 4 个单点错误：平均分错误取整、再次分析追加旧记录、清空时残留输入、错误行号偏移。先确认独立断言在正确代码上通过、在错误代码上失败，再运行未修改的模型验收，4/4 均被识别。见 [csv-mutations.json](csv-mutations.json)。这一成功样本无法抵消其他类型的生成失败。

## 修复优先方向

1. 扩展通用验收协议表达禁用、未选中等反向状态及常见表单动作，保持 schema、运行器、题面说明一致；不依靠强行点击禁用元素来验证禁用。
2. 去掉不承载实际业务正确性的 requiredAssertions 类型门槛，以可执行检查及需求语义为依据，保留真实错误的拦截。
3. 修复计划与增量验收的协作：初始定位应允许后续扩展；本步验收读实际代码，修复时避免重复已证实错误的动作/预期。已有上下文是必要条件，不等于模型一定利用正确。
4. 以结构化能力契约处理不支持的运行类型，及时给出明确原因。若要支持后端，需要真实隔离的服务/存储/HTTP 检查运行环境，不能以浏览器模拟代替。

这些是通用模块能力与生成流程问题，未新增计算器、记账等项目专用规则。本轮没有实施上述修复，也没有重新测试上一轮已报告的“排队重试仍显示旧任务”问题。

## 可重放材料

`reproduction/fixtures/` 保存测试产物、失败检查点、各阶段输入输出，不包含登录 token。阶段输入可核对代码/验收分离及前序上下文。实时生成和页面脚本保存于 `reproduction/live-scripts/`，使用本机隔离数据库和临时目录；不要改为生产库运行。

以下命令无需模型或数据库，直接在真实 Chromium 中复放已留存的证据，结果写到 reproduction/replay，不覆盖首次结果：

```sh
node docs/acceptance/2026-10-17-pbl-diverse-e2e/reproduction/failed-step-audit.cjs
node docs/acceptance/2026-10-17-pbl-diverse-e2e/reproduction/wizard-audit.cjs
node docs/acceptance/2026-10-17-pbl-diverse-e2e/reproduction/remaining-failed-step-audit.cjs
node docs/acceptance/2026-10-17-pbl-diverse-e2e/reproduction/csv-mutations.mjs
```
