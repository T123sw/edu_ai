# Patch 003 · 课程准备直接使用 OpenMAIC 原生生成

> 2026-10-13 用户策略更新：生成后的 AI 课堂不再执行额外模型审查。
> 本节优先于下文历史接入方案中的独立课堂审核要求；源码已修改，服务加载状态见验收记录。

课堂生成后只保留结构/格式、场景身份、媒体引用与真实定位校验。关闭逐页/讲解内容审核、
目标定位的独立语义审核；节点和整课模型审核不再传入课堂正文，也不能将课堂列为修复目标。
报告、独立习题及其对应的课程审核仍执行原有策略。全为课堂的审查范围只做确定性校验。
课堂回执明确保存 `decision=skipped`、`method=structural_validation` 与内容/定位摘要，
不会伪造 `model_review=pass`。该策略同样适用于工作台通过共享课堂入口生成的内容。

已在原生课堂审核阶段失败且保有完整、摘要有效候选的任务，可在正常重试时复用候选继续交付。
恢复前验证原任务/当前任务、用户、权限、来源记忆与内容摘要；重新绑定当前 attempt，
保持原截止时间、累计消耗及预算上限，不重写业务库中的失败为成功，也不直接发布候选。
过期任务仍受原截止时间约束。重新进入后台服务后，由正常生成/交付流程完成定位和保存。

使用上一次真实失败的 7 页/43 段讲解候选作源码回放：结构校验通过，额外审查调用为 0，
正文与图片保持不变。此回放不代表后端部署或完整浏览器端到端完成。
见[策略回放记录](../../acceptance/2026-10-13-classroom-no-extra-review/candidate-replay.json)。

日期：2026-10-13。范围：课堂内容生成与修复，不升级或复制上游整站的账号、数据库和工作台。

## 行为

新建的结构化课堂直接调用当前仓库维护的 OpenMAIC 原生大纲、场景内容、动作生成和场景装配函数。
Edu_AI 传入需求分析、当前节点目标、基础、先修、活动、自测、资料证据与修订意见。
不再先生成限制为三条文字要点的 storyboard，也不再套固定的文本框/步骤框版式。

开放幻灯片原生排版、图表、表格、公式、交互 HTML、单选/多选/简答测验、讲解与聚光等现有播放器能力。
白板、多角色讨论和 PBL 在提示和生成结果两层禁用。测验生成后使用原生 question-only 讲解动作，作答前只朗读题干，答案和解析仅在提交反馈中出现。语音继续由现有本地 TTS 播放链路负责，
不把 speech 文本当作已经生成、播放或验收过的音频。

资料除了准确引文和来源，还传递引文周围已读上下文；每个内容生成阶段都能读取需求和资料。
教学要求明确包含完整算例、推理依据、边界/反例、误解与迁移检查。内容量取决于目标，24 页是安全上限。
原生内容仍由模型生成，接入不构成内容正确性的保证。

## 运行路径

`PreparationResourceHandler → generate_classroom_draft → generate_native_draft → run_native`
启动 `openmaic-sidecar/scripts/preparation-bridge.ts`，调用
`lib/server/preparation-generation.ts`，后者复用：

- `generateSceneOutlinesFromRequirements`
- `generateSceneContent`
- `generateSceneActions`
- `createSceneWithActions`

通过 JSONL 请求模型输出。每次调用仍进入 `PreparationHarnessGateway`，保留父预算、租约、取消与截止时间。
Node 不自行解析文本模型密钥，也不绕开计量。stdout 为协议，诊断输出在 stderr。
子进程拥有独立进程组；退出、取消或模型失败时连同 tsx 子进程一并清理。

原生大纲、已完成场景和待装配内容保存至私有 `_native_generation`，同一个 artifact/spec/attempt 下恢复。
持久化失败不确认 checkpoint；先成功保存再推进。审阅阶段仍使用 `_review_candidate`。
审阅通过前不会发布课堂。保存最终 artifact 时由原有验证和交付链路接管。

旧 v1 规格和已经保存 storyboard 的旧任务继续使用原合同恢复，不重写已有断点或摘要。

## 审核与修复

保留逐页、逐条 speech 和目标定位的独立审核。结构校验支持宿主实际能播放的原生元素/动作。
新增 Python 运行库加载器缺失检查，不把会报 `loadPyodide is not defined` 的交互页当作可交付内容。

真实内容问题交回 OpenMAIC 原生函数重生成具体页面。未涉及页面保持字节相等，替换页保留 scene ID；
新动作和元素使用原生身份。只传本页修订基线，避免在每个阶段重复整份含 HTML 的课堂造成上下文超限。
格式错误继续按原机制只恢复审阅，不悄悄重写正文。

交互动作阶段现读取实际 HTML 实现；没有对应状态键、消息处理器或选择器时不得伪造 widget 动作。
课堂内测验审核明确要求独立求解、核对所有选项及 analysis/commentPrompt，特别区分循环开始、处理后和退出时的边界。
审核的六项 criterion 在原生提交 schema 中枚举并限制为六项；逐页/逐讲解回执按真实 scene_index/action_index 绑定位置和数量，避免将交错动作中的讲解序号误作动作下标。

## 图片、视频与运行依赖

后端机器需要 Node >=22 和 vendored sidecar 依赖；`tsx` 从开发依赖移动为运行依赖。
`tsconfig.bridge.json` 为 Node 桥接解析 DSL 源码，解决仅提供 ESM import 导出的包被 CJS 加载的问题。
可用 `OPENMAIC_SOURCE_DIR` 覆盖源码目录，默认按后端文件相对路径定位。

付费图片/视频同时要求 sidecar provider 可用以及后台配置单次请求费用上界：

- `OPENMAIC_IMAGE_COST_MICRO_USD_UPPER_BOUND`
- `OPENMAIC_VIDEO_COST_MICRO_USD_UPPER_BOUND`

单位为微美元，默认 0（未配置时不启用付费生成）。由管理员按实际提供商价格设置；不伪造价格。
生成前从父任务预算预留调用数和费用，结束按上界结算；取消/失败仍保守记账。
每份最多 24 个媒体请求，媒体总量上限 40 MiB。生成内容嵌入课堂，避免让学习者浏览器访问 sidecar localhost。
文字审核使用二进制媒体摘要，视觉内容与音频另做浏览器验收。必需媒体生成失败时不交付空占位符。

工作台旧 HTTP 生成入口附带 `capabilityPolicy=edu-ai`，同步排除 PBL/白板/讨论和残缺课堂。
工作台 durable handler 补齐 image/video 参数转发。该兼容入口仍沿用其现有服务端模型配置与任务机制。

## 保存与验收

修改前恢复点：`backup/openmaic-native-20261013T134243Z`，提交 `ba2c74aef3070e5cb0fa0a073423dbbc1ee44ee5`。
归档目录：`/home/zxqs_ep/project-backups/Edu_AI-before-openmaic-native-20261013T134243Z`。
含工作区归档、Git bundle、修改清单和 SHA-256 manifest；配置文件位于权限受限的归档中。
该备份不是业务数据库或模型权重备份。

验证覆盖原生 Node 子进程、逐调用计量接口、资料传递、内容中断后恢复、租约隔离、禁用能力、
局部修复与不受影响页面身份，以及既有备课/工作台回归。
真实模型算例为 Lomuto 分区：幻灯片、交互演示、迁移测验。浏览器实际点击单步按钮，
验证了生成、失败诊断、原生修复、再次审核和目标定位链路。
原始初稿暴露测验错误与运行库缺失；一次模型审核曾返回 pass，但人工复验发现新的循环边界错误，故该版本仍不合格。
最后一轮按正式修复次数上限返回 CLASSROOM_CONTENT_REJECTED，交互页与讲解仍有边界口径不一致；候选未交付，不能据此声称生成质量已稳定提升。
最终未批准候选的浏览器复验还出现生成 HTML 的空 DOM 引用错误（Cannot set properties of null），虽然单步按钮会改变状态，仍不能判定整页运行通过。
这同时验证了审核拒绝与不发布错误课件的路径。软件回归通过不等于模型生成的教学内容通过。
验收产物存于 `/home/zxqs_ep/openmaic-native-validation`，不写入用户业务课程。

代码接入与服务上线分开记录。后端加载新代码需要重启；旧 HTTP sidecar 入口还需重新构建 Next.js 后重启。


## 2026-10-13 媒体配置预留

根目录 `.env` 和 `.env.example` 增加 `IMAGE_QWEN_IMAGE_API_KEY`、`IMAGE_QWEN_IMAGE_BASE_URL`、
`IMAGE_QWEN_IMAGE_MODELS=qwen-image-3.0`。模型使用现有 DashScope 同步接口；域名需与密钥地域一致。
协议参考：https://www.alibabacloud.com/help/en/model-studio/qwen-image-generation-and-editing-api-reference 。
视频按已有 Seedance 适配预留 `VIDEO_SEEDANCE_API_KEY`、`VIDEO_SEEDANCE_BASE_URL` 和 `VIDEO_SEEDANCE_MODELS`，
型号暂留空。初次预留时两类密钥留空、备课单次费用上限为 0；后续启用状态见下方真实验收记录。
修正自动课堂媒体生成忽略服务端模型列表的问题：优先使用配置的第一个模型，未指定时沿用原默认值。
配置解析与媒体相关回归 52 项通过。

### 2026-10-13 首页真实验收：未通过

用户填入密钥并重启后，运行进程已加载 `qwen-image-3.0` 与图片单次费用预留上界
`OPENMAIC_IMAGE_COST_MICRO_USD_UPPER_BOUND=50000`，默认允许生成图片；视频仍为 0。
该数值是保守预算预留，不是供应商账单单价。独立图片调用与真实课堂流程都生成了图片。

使用隔离测试账号从真实 Nginx 首页输入“栈的 LIFO 与入栈、出栈”，未模拟 API。
最终试验持久化了 7 页原生课堂（含交互页、迁移测验、43 段讲解和 1 张真实配图），
报告与习题已成为经过各自审阅的私有草稿。课堂独立审核输入保守字节上界为 202288，
超过 128000 窗口，报 `CONTEXT_BUDGET_EXCEEDED`，因此未交付课程。
不得将这些私有候选或独立图片测试标为完整端到端通过。

测试期间修正了单知识点约束提示、过度回读资料的指令、工具引用数量/理由长度提示，
以及原生大纲重复附加完整需求与证据的问题。研究恢复后投影摘要和整课审核使用媒体摘要
两项 Python 源码修复通过回归，仍需加载到服务；但这两项不会解决剩余的完整课堂审核超限。
剩余工作是对完整课堂审核做有界分批，并保持逐页、逐段讲解及跨页一致性核验与断点恢复。

完整记录见 [首页真实验收证据](../../acceptance/2026-10-13-openmaic-home-e2e/verification.json)。
