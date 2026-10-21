# 通用实验设计 Skill 首版验收

2026-10-15。已完成发布；后端新接口及前端新入口已生效。实施范围和实际 API 见 [实施计划](../../architecture/2026-10-15-experiment-implementation-plan-cn.md)。

## 已完成

保留 MAIC-UI 原生科学建模、生成和润色；新增应用内设计 Skill、严格输出校验、通用三阶段运行器与跨学科适配器接口。前端使用既定三栏，展示在上、参数在下，手机就地显示反馈。客观判定无模型等待；学生错误、系统数据不足与开放评价分别处理。

每个动作记录来源、阶段、尝试、前后快照，错误回滚仍保留提交瞬间状态。保存支持幂等和冲突检测，不覆盖既有历史；冻结问题与五个只读工具为独立教学 Skill 预留接口，页面明确标识教学服务尚未接入。

## 实测证据

- 后端 `tests/practice` 全量回归 40 项通过；随后新增并发保存用例并定向复验 `test_experiment.py` 17 项通过。
- 通用运行器 8 项通过，覆盖演示权限、错误/正确路径、组合提交、开放评价保留、力学与随机模型、非法状态和 unknown。
- 浏览器生成验收包含三种适配器正确/错误用例、演示重放、探索、360/1000 宽度与 DPR=2；故意无功能的页面被拒绝。此部分包含于后端全量回归。
- 桌面 1440、手机 390 两项完整前端流程通过：演示禁用手操、按钮和画布手动操作、错误重试、冻结问题、成功自动推进、探索与刷新恢复。认证和业务 API 使用模拟数据，实际运行生产前端组件与沙箱 SDK。
- TypeScript、局部 ESLint、独立目录生产构建、Skill 格式检查通过。
- 截图：[桌面探索](explore-1440.png)、[手机探索](explore-390.png)。图中为协议验证样例，非模型新生成的完整快速排序课程。

## 重现

在仓库根目录，将 Node/Python 环境加入 PATH 后执行：

```sh
PYTHONPATH=backend/src pytest -q backend/src/tests/practice
PYTHONPATH=backend/src python -m tests.practice.experiment_fixtures
```

前端目录：

```sh
node --import tsx --test src/practice/experiment/model.test.ts
pnpm exec tsc -p tsconfig.self-learning.json
pnpm exec eslint src/practice/experiment src/practice/Practice.tsx
pnpm exec vite build --outDir dist-experiment-review
pnpm exec playwright test -c playwright.experiment.config.ts
```

fixture 脚本只写 `.runtime/experiment-fixtures`，不写用户资源。构建仅写 `dist-experiment-review`，没有生产目录替换。上游固定源码需要已安装；浏览器验收需要 Chromium。

## 仍需后续验证

未调用真实模型验证本轮 Skill 的实际生成质量或成功率。测试通过证明协议、控制流程、存储及适配器接口能够工作，不证明任何模型生成的任意科学实验都正确。运行验收也不是独立科学认证。

教学模型、自动干预、流式答疑、rubric 评分提交、课堂逻辑会话接入、长历史摘要均未实现；本轮仅提供与之对接的证据接口和预留位置。旧冒泡样例不迁移、不覆盖；旧 v2 发布继续暂停。

## 发布准备与当前阻塞

已基于最新闪卡提示精简版（包含导图平移、资源历史精简等更新）复现线上 477 个文件，在隔离源码 `/tmp/edu-experiment-publish-source-v3` 仅加入通用实验组件和入口分流。旧 v2 前端未混入发布。新包在 `/tmp/edu-experiment-release`；41 项后端回归、类型/lint/构建、4 项桌面/手机新旧实验检查通过，另 1 项旧真实实验可选样例跳过。

`python scripts/publish-experiment.py --check` 已通过。实际执行 `sudo -n systemctl restart edu-ai-backend` 返回 `sudo: a password is required`，所以没有切换前端入口；当前在线后端尚无新实验接口。这是操作系统管理员权限限制，不是应用审批拒绝。发布记录见 [deployment.json](deployment.json)。

管理员在服务器执行：

```sh
cd /home/zxqs_ep/Edu_AI
sudo systemctl restart edu-ai-backend
python scripts/publish-experiment.py
```

脚本会核验源码和产物摘要、后端新进程和新接口、鉴权以及当前线上基线；保留旧静态资源，原子切换入口后跑线上浏览器复验，失败时恢复旧入口。如果期间有其他前端发布，会停止并要求重新合入，避免覆盖。没有生产学员数据写入，不需要新增数据库迁移。真实模型生成质量尚未验证，教学 Agent 仍未接入。新功能作用于后续新生成实验，已有实验保持原展示。

## 发布完成

用户完成后端重启后，确认 PID 291392 已加载通用实验接口。期间有其他前端更新，重新基于当前首页分享移除版本的已记录源码快照合入实验入口，保留导图点击交互、后台任务默认已完成、个人设置及此前更新；核验基线已发布文件摘要，未宣称本次重新构建复现全部 550 个含历史资源的基线文件。

使用 `/tmp/edu-experiment-publish-source-v5` 构建发布；类型、lint、构建与发布前 4 项浏览器检查通过（1 项可选旧真实样例跳过）。检查新后端进程、接口、鉴权后原子切换前端；480 个发布文件与 Nginx 入口一致，线上 4 项浏览器复验通过（1 项可选样例跳过，业务 API 模拟）。没有生产学员数据写入；教学 Agent 尚未接入、真实模型端到端生成质量仍未验证。

前面的权限阻塞记录是发布过程历史，已经解除。最终状态、入口哈希、后端 PID 与回滚备份以 [deployment.json](deployment.json) 为准。新创建的实验按 `edu-experiment/1` 设计；旧实验和固定冒泡体验保留原行为。
