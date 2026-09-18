# Harness 输入阶段部署准备

代码已整合到实际部署分支 `feat/self-learning-frontend-20260914`，功能提交 `ca48f237`。原有未提交的地图、架构及验收索引改动保留，未将无关备份文件纳入提交。

已完成：

- 数据库与 `.env`、旧前端完整备份：`/home/zxqs_ep/data/Edu_AI_backups/preparation-harness-20260918T065242Z`。数据库使用 pg_dump custom 格式，pg_restore 目录检查通过。
- 业务数据库执行 `20260910_0021 → 20260918_0036`，当前为 head；迁移日志在上述备份目录。
- `.env` 设置 `COURSE_PREPARATION_ENABLED=true`，保持权限 0600。没有开启额外学习阶段开关。
- 使用业务环境配置成功装配准备服务全部九个阶段，未启动重复后台 worker。
- 生产前端构建位于 `frontend/dist-preparation-harness`。浏览器对该构建使用模拟 API 验证上传入口、`/backend` 请求地址、文件名展示和仅附件创建按钮，通过；不等同线上文件上传实测。
- 原 173 项后端回归及真实 Harness 模型验证见 [功能验收](2026-09-18-preparation-harness-cn.md)。

待执行的最后一步：

```bash
bash /home/zxqs_ep/Edu_AI/scripts/activate-preparation-harness.sh
```

脚本通过 sudo 重启 systemd 后端，等待健康检查，再复制新版静态资源并原子替换首页。旧哈希资源保留，避免已打开页面丢失依赖。重启失败时不切换前端。

当前会话 `sudo -n` 提示需要密码，`systemctl --no-ask-password restart edu-ai-backend` 被拒绝，提示需要交互认证。因此尚未执行线上后端重启和前端切换，不能标记上线完成。请由用户在服务器终端运行上述脚本，按 sudo 提示完成本机认证，无需向对话发送密码。

## 启用完成（2026-09-18 06:56 UTC）

用户执行启用脚本后，后端新进程 `683990` 启动，运行进程确认 `COURSE_PREPARATION_ENABLED=true`；直连 `/health` 和 Nginx `/backend/health` 均返回正常。线上 HTML 与新构建完全一致，入口脚本为 `index-D5Mg20pP.js`，上传组件静态资源已核对。脚本退出，前后端切换完成。

启动时知识库 BM25 索引加载造成短暂拒绝连接和健康检查超时，随后恢复。已调整启用脚本：等待期间显示进度提示，不逐次打印预期的 curl 失败；最终超时仍报告失败。未重跑生产环境整课生成或真实文件上传。
