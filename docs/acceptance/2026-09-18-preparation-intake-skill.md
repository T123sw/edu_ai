# 需求理解独立 Skill

课程准备第一阶段使用 `backend/src/app/course_preparation/skills/understand-learning-request/SKILL.md` 作为流程规则的单一来源。附件理解和需求归纳是同一个 Skill 的两个阶段；检索、规划与生成不属于这个 Skill。

## 执行路径

1. 业务程序解析附件、分段，提供 `input_document` 输入。
2. Harness 原生 Skill 加载器加载本次 Skill 快照；模型调用 `record_input_document` 提交片段理解。
3. 程序校验原文引用并保存检查点，处理后续片段。
4. 全部附件处理完（或没有附件）后，提供 `intent` 输入；模型调用 `save_preparation_brief` 提交目标、基础、预期能力、约束、引用和假设。
5. 程序执行契约与依据校验，保存 brief，再进入研究。

Harness 挂载 `dsh-skill`、`dsh-skill-filesystem` 和 `dsh-tool-skill`。通过 `/understand-learning-request` 在首个模型请求前加载正文，不要求模型额外调用一次加载工具。仅扫描本次临时目录中的 Skill 快照，不读取默认技能目录。模型请求前检查完整正文是否已加载；缺失时失败，不静默退回旧提示词。计量记录保存 Skill 名称和 SHA-256。

本阶段没有新增独立复审。权限、文件解析、预算、引用校验和持久化仍由程序负责；Skill 不代替这些边界。非 Harness 的独立模型适配器测试路径从同一个 Skill 读取正文内联使用。

## 验证

- Skill 格式校验通过。
- 聚焦测试：21 passed，1 skipped。真实 SDK 配合模拟模型验证两个阶段，确认正文只注入一次、工具范围正确，加载失败时不调用上游模型。
- 隔离环境全量课程准备回归：175 passed，77 skipped；跳过项不计入通过结论。
- 真实模型验证：两份合成附件（岗位要求、个人背景）及最终需求归纳，共 6 次调用、21,212 tokens。保留 120 分钟、英文历史偏好、仅上传资料和不训练模型约束，阻止后续联网检索。详见相邻 artifacts 目录中的 JSON。
- 这次调用数和 token 数仅代表该样例，不是固定费用或性能保证。每阶段包含工具提交和工具结果后的结束回复；没有额外 Skill 加载模型调用。
- 初次全量回归受本地 `.env` 的 `COURSE_PREPARATION_ENABLED=true` 影响，一项学习记忆测试误走部署课堂查询。旧配置模块使用 `load_dotenv(override=True)`，仅设置进程环境不足以隔离。隔离回归在测试进程中禁止 dotenv 加载，并设 `COURSE_PREPARATION_ENABLED=false`；业务专项测试仍显式构建其测试依赖，未修改部署配置。

语义正确性仍需持续评估：本次样例的 `assumptions` 中仍混有一条排除项解释，说明仅写清 Skill 不能保证每个字段始终完美。没有为此引入第二个模型复审。

## 生效方式

这是后端改动，不需要重新构建前端。部署服务需要执行 `sudo systemctl restart edu-ai-backend` 才能完整加载新代码；本次执行环境没有免密码 sudo 权限，未重启服务。不要使用会覆盖前端目录的旧激活脚本发布此变更。
