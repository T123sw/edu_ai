# 学习空间前端部署记录

> 当前状态：2026-10-13 已按用户要求回退到改版前前端。下文为此前发布的历史记录；改动保留于 `601c3068`。前端源码恢复至 `0f3cd72e`，Nginx 入口恢复下述备份。

2026-10-13，按用户“合并一下，我看看效果”的要求，将本轮改动提交到当前业务分支 `feat/self-learning-frontend-20260914`，代码提交为 `601c3068`。本轮没有合并到其他工作树中的 main，也没有推送远端。

## 已更新

- Nginx 原站点继续读取 `/home/zxqs_ep/Edu_AI/frontend/dist`，已发布新版学习空间、科研草稿与面试筹备入口。
- 以 `VITE_API_BASE_URL=/backend` 重新构建，先复制静态资源，再原子替换入口 HTML；保留旧哈希资源供已打开页面使用。
- 旧版完整备份：`/home/zxqs_ep/data/edu_ai/backups/frontend/before-learning-space-20261013T121310Z`。
- 前端发布信息可通过 `/preparation-build.json` 核对；后端、数据库、Nginx 配置未修改，无需重启。

## 验证

TypeScript、修改文件 ESLint、差异格式检查和生产构建通过。构建仍有原有大包体积提示。

通过实际 Nginx 80 端口读取发布资源，在桌面 1440 和手机 390 检查：登录页、新首页、课程到科研草稿、草稿刷新恢复、返回来源资料、面试筹备入口。两种尺寸均无横向溢出、页面异常和 HTTP 错误。

认证和课程 API 使用浏览器拦截的模拟数据，没有使用真实用户凭据或创建业务课程；单独请求实际 `/backend/health` 返回 200。开发预览参数 `?preview=student` 在生产构建中按原有设计关闭，正式站点正常登录后查看。

- [检查结果](results.json)
- [桌面首页](desktop-home.png)、[手机首页](mobile-home.png)
- [桌面科研草稿](desktop-research.png)、[手机科研草稿](mobile-research.png)

## 查看与回退

刷新平时使用的网站即可。按部署文档使用 SSH 映射 8080 时，电脑浏览器地址为 `http://127.0.0.1:8080/`。若页面仍显示旧版，强制刷新。

如需回退本轮界面，将备份中的 `index.html` 和 `preparation-build.json` 通过临时文件原子替换回 `frontend/dist` 即可；旧哈希资源仍保留，不需要更改数据库。科研草稿只是当前浏览器的本地记录，真实科研 Agent 与实验执行尚未开放。
