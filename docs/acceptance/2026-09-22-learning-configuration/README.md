# 新版学习配置补齐（2026-09-22）

**业务配置与默认网站前端已更新；后台仍需管理员重启才能加载新增开关。**

按用户“补齐配置”的要求，在根目录业务 `.env` 增加以下五项 `true`，保留其他模型、预算、存储与功能设置，文件权限维持 `0600`：

- `LEARNING_SESSION_V1_ENABLED=true`
- `LEARNING_PROGRESS_V1_ENABLED=true`
- `LEARNING_AGENT_V1_ENABLED=true`
- `LEARNING_ENRICHMENT_V1_ENABLED=true`
- `LEARNING_PREPARATION_V1_ENABLED=true`

数据库已处于 `20260918_0036`，本轮不执行数据库迁移。启用配置后的独立服务初始化检查确认 sessions、progress、answers、checks、memory、summaries、preparation_handoff 七项均已建立；该检查没有启动第二套业务 worker。

现有七条学习 overlay 已备份，未发现需要转换的已完成标记或自评。未标明资料版本的旧位置不推断为新版版本化事实；原始记录、旧练习答案和文件均保留。旧知识点会话由现有首次进入逻辑导入，不批量改写用户历史。`LEARNING_SCOPED_ROLLOUT` 保持原设置（未开启）。

默认 Nginx 网站已更新到此前实测通过的前端构建 `e0003454`。更新前确认其 frontend Git tree 与当前工作区完全一致（后续提交仅文档）；备份旧构建后先放置新版资源，再原子替换首页，并保留旧哈希资源供已打开页面使用。HTTP 回读确认首页和入口资源与本地构建一致，默认网站真实浏览器登录、首页展示通过，无页面或 HTTP 错误。

业务后端仍为进程 `1479608`。自动执行 `systemctl --no-ask-password restart edu-ai-backend.service` 被系统拒绝，原因是需要管理员认证。因此不能把 `.env` 已写好或独立初始化成功称为业务进程已生效。已请求用户执行：

```bash
sudo systemctl restart edu-ai-backend.service
```

重启后的真实默认网站验收脚本已准备，要求进程 ID 更新、五个运行时开关均为 true，验证新上传课程、持久化会话、逐题作答与刷新恢复、报告和课堂。当前尚未执行，不能记为通过。

状态见 [status.json](status.json)。私有配置备份、旧前端和原始学习记录位于 `/tmp/edu-ai-learning-enable-20260922`；凭据不提交仓库。
