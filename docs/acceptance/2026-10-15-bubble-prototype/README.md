# 冒泡排序教学交互原型验收

2026-10-15：完成[四阶段计划](../../architecture/2026-10-14-experiment-teaching-phases-plan-cn.md)的第一项交付。原理演示和手动练习可实际操作，供确认教学体验；性能测试、自由探索、模型对话和正式存储尚未接入。随后按用户要求接入正式首页并上线；没有修改后端或执行迁移。

线上入口：刷新网站，进入「互动实验」，点击「冒泡排序 · 分步体验」，或打开本站 `/#/practice/bubble-sort`。这是供体验评审的前两阶段原型，性能测试、自由探索和 AI 对话仍未开放。正式页面按账号隔离标签页进度。基于最新线上源码快照重建一致基线后集成，保留同期资源预览标题及 PBL 修改。7 项规则、类型/lint/构建、8 项发布前及 8 项线上浏览器检查通过；资源预览 24 项回归通过。浏览器使用模拟认证和业务接口，操作规则实际执行，没有写入生产学习数据。见[发布记录](deployment.json)、[桌面](published-1440.png)及[手机](published-390.png)。

[打开独立 HTML 原型](bubble-sort-prototype.html)，下载后可直接用浏览器打开，不需要服务器或网络。当前预览地址为 `http://127.0.0.1:5250/bubble-preview.html`；若开发环境位于远程服务器，可转发 5250 端口，或使用独立 HTML 文件。

原理演示从 `[5, 3, 4, 1]` 开始，每次只比较或交换一次，完整演示一轮后再展示保持顺序的情况。手动练习使用 `[5, 1, 4, 2, 8, 3]`，用户自己选择相邻元素、决定交换或保持，并声明本轮完成。没有通用下一步或自动执行一轮按钮；错误对象、错误判断和提前结束均有解释，数组和算法计数保持原样。两轮完成结果为 `[1, 2, 4, 3, 5, 8]`，共 9 次比较、6 次交换，明确提示整体仍可能无序。

右侧规则讲解随操作更新，桌面滚动时当前反馈保持可见；手机把反馈放在数组和操作按钮之间。提供三级提示、取消选择、当前阶段重试、最近操作记录和阶段独立恢复。进度以语义动作保存在当前标签页的 sessionStorage 中，刷新后重放恢复；关闭标签页后的保留不作保证，也不作为正式学习证据。讲解来自规则，没有伪装成模型对话。

7 项规则单测和 7 项浏览器检查通过。浏览器覆盖 1440/390 宽度完整流程，以及 320/768/1024/1440 宽度短窗口反馈可见性、键盘操作、重试隔离及损坏草稿恢复。类型、局部 lint 和独立构建通过；独立 HTML 在断网环境验证比较、交换及错误反馈。没有验证真实模型回答、生产接口或后续两个教学阶段。

- [原理演示桌面](demo-desktop.png)
- [手动练习桌面](practice-desktop.png)
- [手动练习手机](practice-mobile.png)
- [两轮完成结果](complete-desktop.png)
- [验证记录](verification.json)及[独立 HTML 检查](standalone-check.json)

在 `frontend` 目录复验：

```sh
node --import tsx --test src/practice/teaching/domains/bubbleSort.test.ts
npx tsc -p tsconfig.bubble.json
npx eslint src/practice/teaching
node scripts/build-bubble-prototype.mjs
npx vite preview --config vite.bubble.config.ts
```

预览服务启动后，在另一个终端运行 `npx playwright test --config playwright.bubble.config.ts`。构建只输出到 `.runtime/bubble-prototype-build` 和本验收目录，不使用主应用发布入口。

下一项工作依据体验反馈确定比较/交换粒度、提示程度和布局，再接入正式实验流程。旧 v2 发布仍暂停，不执行旧发布脚本。
