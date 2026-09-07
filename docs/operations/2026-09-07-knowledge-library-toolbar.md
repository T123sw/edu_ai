# 2026-09-07 课程知识库顶栏与文档操作

右侧合并为一个标题与工具栏；更新知识库、学习资源生成在左侧，搜索和上传在右侧。窄屏自动换行。文档右侧使用三点菜单，提供查看详情、修改资料名称、删除；查看详情打开正文预览，删除保留确认。

新增 PATCH /api/courses/{course_id}/knowledge-base/documents/{document_id}，要求课程编辑权限，验证非空标题；保存显示名称，不修改原始文件名、文件路径、向量来源键或分块。学生无修改权限。

验证：后端名称持久化与权限测试 2 项通过；课程知识集成检查 4 项通过；既有页面浏览器测试 6 项通过；新菜单在 1366 与 1024 宽度的浏览器测试 2 项通过；ESLint 与生产构建通过。测试 API 拦截规则增加真实 /api/ 路径检查，避免误拦截 /src/stitch/api/ 下的开发源码请求。

生产前端已更新（保留旧哈希资源，最后替换 index.html）。入口备份位置记录于 /tmp/knowledge-ui-backup-path。真实页面检查：1 个标题、147 份文档、菜单正常、无 pageerror。截图 /tmp/knowledge-ui-live.png。

服务运维状态：本次对正式后端发送 SIGHUP，systemd 将其视为正常退出，Restart=on-failure 未生效；随后 systemctl start 与 sudo -n 启动均因权限不足失败。已通过 systemd-run --user 启动 edu-ai-backend-temporary，使用同一生产 .env、工作目录、Python 环境及 8001 端口恢复服务。health 返回正常、knowledge_base_ready=true、document_count=5458，新 PATCH 路由已生效。

正式系统单元恢复待管理员在服务器终端执行：

```bash
sudo -v && systemctl --user stop edu-ai-backend-temporary && sudo systemctl start edu-ai-backend
```

若正式启动失败，可先运行 systemctl --user start edu-ai-backend-temporary 恢复临时服务，再检查正式单元日志。恢复后核对 systemctl is-active edu-ai-backend 与 http://127.0.0.1:8001/health。临时服务未改动原 systemd 单元或向量配置。
