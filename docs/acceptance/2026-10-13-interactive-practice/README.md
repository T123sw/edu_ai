# 互动实验首版接入

2026-10-13。入口：学习首页输入主题后点击「生成互动实验」，或顶部「互动实验」。

## 本次范围

- 用户只提交主题；系统设计 3–5 个操作步骤，再进行科学建模、生成自包含 HTML/JS 实验、浏览器检查与一次修复。
- MAIC-UI 固定版本 `aad58ddcc2103058b4c2deffc48a3c13e2c64dd6`，实际调用上游 `anthropic_scientific_prompt` 和 `visual_engine_prompt`。使用 Edu_AI 已配置的模型服务，不需要启动上游完整应用、数据库和登录系统。
- 新增实验工作区、步骤切换、用户手动保存观察、参数/结果传给 AI 辅导、实验列表、持久化记录。任务接入现有 durable queue。
- 本期为浏览器内模拟和参数探索，不包含完整编码 IDE、项目文件系统、容器执行、多阶段项目验收。步骤切换不代表掌握知识或自动通过考核。
- iframe 只有 `allow-scripts` 权限，没有同源权限；CSP 禁止网络请求、外部脚本、嵌套页面、表单提交。宿主页验证 postMessage 来源，AI 只读取提交的有界状态，不访问宿主页认证数据。
- 用户保存观察和对话会持久化。再次打开实验从初始参数开始，不恢复运行中的动画。

## 上游模块安装与启动

```bash
cd /home/zxqs_ep/Edu_AI
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python scripts/install-maic-ui.py
# 前端构建后按项目既有流程部署；后端需要正常重启服务。
sudo systemctl restart edu-ai-backend
```

上游来源：<https://github.com/THU-MAIC/MAIC-UI>。安装脚本从固定 commit 下载单个提示词模块并校验 SHA256，写入被 Git 忽略的 `.runtime/maic-ui/ai_prompts.py`。不把上游代码重新标注为本项目原创或自行指定许可证；外部分发时需要另行确认上游授权。

## 输入与产物

- `POST /api/practice`：`{topic, request_id(UUID)}`，返回任务编号和任务状态。同一账号的同一请求不会重复入队。
- `GET /api/practice`：本人实验列表。
- `GET /api/practice/{id}`：后台任务、成功交付的 `{plan, science, html, validation, source}` 与 `{observations, messages}`。
- `POST /api/practice/{id}/observations`：`{state, step, note}`，保留最近 50 条观察。
- `POST /api/practice/{id}/ask`：`{question, state, step}`，结合实验设计、科学模型、当前状态、最近观察和对话生成引导，保留最近 40 条消息。
- 所有读取/写入均检查登录用户与任务所有者。失败候选不会作为可体验实验交付。

## 验证与边界

- 新增后端测试覆盖所有者隔离、观察持久化、生成未完成时禁止记录、实际状态进入 AI 上下文、创建幂等、运行隔离、检查失败不交付。
- 桌面 1440px 与手机 390px 浏览器流程测试：从首页进入、修改实验参数、保存观察、上下文提问、刷新后记录保留。该流程测试使用模拟 API 和可运行测试页面。
- 真实模型 `deepseek-v4-flash` 生成「摩擦力与小车滑行距离」；首轮输出不完整，调整输出预算后重新生成，经一次自动修复通过浏览器检查。生成结果不是固定模板。
- `desktop.png` / `mobile.png` 使用真实生成 HTML，外层数据请求为视觉验收用模拟传输；不能把截图当作部署后的完整接口验收。
- `numerical-check.json` 验证这个真实样例的三组停车距离，与 `s=v0²/(2μg)` 一致。不能由单个样例推导所有主题都科学正确。
- 自动交付检查涵盖加载、初始结果、调整参数并运行后的结果变化、重置按钮、桌面/窄屏横向布局和 JS 错误。这是运行检查，不是通用科学正确性认证。上游科学建模输出本身也可能出现表述错误，仍需进一步迭代质量审核。

## 本次执行结果与部署状态

- 新增后端用例与 durable runtime 回归：9 passed。
- 桌面/手机端到端流程：2 passed；TypeScript、修改范围 ESLint、前端生产构建通过。
- 额外执行旧 `test_job_completion_service.py`：单独执行 4 passed；与其他测试组合执行曾出现所有权用例失败，存在测试隔离/顺序问题，未宣称全量回归通过，也未修改其业务逻辑。
- 真实 AI 辅导测试见 `tutor-check.json`，模型正确引用当前 v₀=8、μ=0.2 和停车距离，并给出下一步操作建议；该测试隔离了 API 所有权夹具，不代表线上鉴权端到端验证。
- 16:50 UTC：前端已发布到现有 Nginx 目录，首页 HTTP 200；旧首页入口备份在 `.runtime/frontend-before-practice-20261013-165017/index.html`，旧哈希资源保留。
- 可立即体验的真实样例：当前站点 `/practice-preview.html`，HTTP 200。它包含参数操作和模拟，不包含服务端 AI 引导。
- **16:50 时后端尚未重启（历史状态）**：当前 `/backend/api/practice` 返回 404；已向用户说明需要 `sudo systemctl restart edu-ai-backend`，当前会话没有 sudo 密码。重启后应先确认未登录请求变为 401，再登录测试生成和记录。尚未宣称部署后的完整生成链路通过。

后续：用户已于 17:13 重启服务；快速排序失败的检查器修复及线上重试成功见[后续诊断](../2026-10-13-practice-validation-fix/README.md)。
