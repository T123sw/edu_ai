# 自主学习页面：真实后端联调与端到端验收

2026-09-14。普通登录入口已切换至真实服务；`?review=1` 和 `?preview=student|teacher` 继续作为隔离的前端演示。此前“仅前端、待联调”的记录属于历史阶段。

## 已接通的流程

- 首页输入学习目标：真实模型规划知识点，创建账号所属课堂，向现有持久化任务队列提交课堂生成；重复提交同一请求不会重复创建课堂或任务。
- 最近学习：读取本人创建和实际进入的课堂；共享列表由教师所有者发布，学生加入后独立保存学习记录。
- AI 课堂：加载真实课件、讲解音频和个人补充资料。笔记、学完标记、知识点自评、当前资源与播放页码保存到后端，刷新可恢复。
- 常驻 Agent：真实模型调用；每个知识点单独存储会话，只携带该知识点最近六轮对话，加上本课堂所有知识点的学习摘要。自评、完成记录和客观练习反馈分别表述，不把完成等同于掌握。
- 工作台：使用原 AIWorkspace、真实登录身份、知识库与生成工厂。仅点击个人作品“引用到工作台”时传入引用，没有课堂资料横幅或自动引用。
- 资源中心：读取个人生成作品，真实预览、置顶、重命名、导出、删除、加入学习目录。学习副本保留独立内容和附件；课程资料仍位于 AI 课堂。
- 练习：真实生成题目；选择题按服务器保存的答案校验，主观题展示参考答案供自查。答案和反馈按用户、资源、版本持久化，进入全局学习摘要。

## 接入位置

| 位置 | 职责 |
| --- | --- |
| `frontend/src/liveLearning/LiveApp.tsx` | 真实状态读取、学习记录保存、创建/加入/发布、作品操作 |
| `frontend/src/liveLearning/WorkbenchEntry.tsx` | 原工作台与真实认证、课程权限、个人引用交接 |
| `frontend/src/liveLearning/MaterialEntry.tsx`、`Quiz.tsx` | 真实课件/资源预览、播放页码回传、练习提交 |
| `backend/src/app/api/self_learning.py` | `/api/self-learning` 接口，复用现有认证、课程、资源和生成任务 |
| `backend/src/app/self_learning/service.py`、`store.py` | 用户学习记录、知识点对话、学习副本和学习摘要 |

当前环境的学习记录使用已有 PostgreSQL 应用状态存储；知识点会话复用现有课堂会话持久化服务。切换到 JSON 模式也有持久化回归覆盖。正式入口不安装前端模拟 API，不用演示数据替代失败的请求。

## 联调中修复的问题

1. 生成工厂的报告走入旧资料生成器，导致主题丢失且审阅前生成错误作品。要求审阅的报告现统一进入报告生成/审阅适配器，通过校验才保存。
2. 指定稳定课堂 ID 后，配音仍使用临时课堂 ID，授权音频请求返回 404。迁移和合成配音改用最终资源 ID，并增加回归测试。
3. 置顶请求字段与后端不一致；首次创建部分提交后的重试没有补交任务。
4. 占位内容变成真实资源时，生成过程中写下的笔记和选中状态丢失。
5. 学习副本附件依赖原件、资源操作尚未成功就显示成功，以及轮询覆盖正在保存的学习状态。
6. 局域网 HTTP 环境的随机 ID 不是合法 UUID。回退生成器现生成符合接口要求的 UUID。

## 验证结果

- **54 项后端测试通过**：学习状态、账号与知识点隔离、模型失败重试、幂等、资料副本、客观练习、报告生成器选择、课堂配音等。
- **30 项前端演示回归通过**：1440、1024、390 三种屏宽，覆盖已有布局、学习与工作台交接。此组使用演示数据，不作为真实联调证据。
- **6 项真实端到端测试通过**：使用真实注册账号、登录、数据库、模型和生成服务；没有 Playwright API 拦截或假响应。覆盖报告生成到删除原件后阅读副本、共享与音频读取、学生习题生成与提交恢复、首页创建及重复请求、1024/390 屏宽。
- `pnpm check:self-learning`、`eslint src/liveLearning`、生产构建通过。
- 仓库全量 TypeScript 检查仍存在历史错误；本次新增入口与修改的课堂播放组件没有出现在错误清单中。没有将全量类型检查表述为通过。

首次真实运行发现了旧进程/旧逻辑问题，因此保留失败记录与修复过程；验收结论以修复后重跑结果为准。测试使用专门账号。早期测试课堂的音频地址曾针对该测试数据迁移，后续首页生成的两间知识点课件已完成，分别有 13、14 段真实音频，均使用最终资源 ID；实际音频请求返回 HTTP 200，无需修复测试数据。

## 重跑

```bash
# 使用项目 Python/Node 环境。后端、模型、配音及前端服务须已启动。
PYTHONPATH=backend/src pytest -q backend/src/tests/test_self_learning.py backend/src/tests/test_generation_task_handlers.py backend/src/tests/test_classroom_service.py

cd frontend
pnpm check:self-learning
pnpm exec eslint src/liveLearning
pnpm exec playwright test -c playwright.self-learning.config.ts frontend.spec.ts conversations.spec.ts review.spec.ts

# 新建真实测试账号及课堂；会实际调用模型、提交生成任务。
node tests/live-learning/prepare.mjs
# 等待课堂生成完成后，以实际前端地址运行。
LIVE_FRONTEND_URL=http://127.0.0.1 pnpm exec playwright test -c playwright.live-learning.config.ts
```

`LIVE_BACKEND_URL` 默认 `http://127.0.0.1:8001`。测试凭据写在仓库外的 `/tmp/edu-live-accounts.json`，权限为 0600；可用 `LIVE_ACCOUNTS_FILE` 指定路径。测试报告、失败截图和 trace 位于 `frontend/test-results/live-learning/`，不要提交包含登录请求的 trace。单元测试显式隔离持久化模式，避免写入运行环境数据库。

模型或配音服务不可用时，页面显示真实错误/任务状态；生成服务没有固定完成时间。当前版本恢复课件页码，页内音频从该页开头播放。
