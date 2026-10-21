# MAIC-UI 原生模拟实验接入

2026-10-14：**已确认上线并完成专项复验**。原生实验前端随 04:43 UTC 的资源工具发布一并进入生产，后端 PID 3768187 于代码修改完成后重启；本轮核对并复验，没有重复覆盖发布包。线上 1440/390 宽度新旧页面 4 项回归通过，另 1 项可选旧真实样例跳过；业务 API 使用模拟响应，真实后端健康、路由和未登录鉴权另行通过检查。没有修改生产实验、观察记录或数据库结构。见[部署记录](deployment.json)与[线上桌面截图](production-native-1440.png)。

## 改动与来源

安装脚本现在克隆 [THU-MAIC/MAIC-UI](https://github.com/THU-MAIC/MAIC-UI/tree/aad58ddcc2103058b4c2deffc48a3c13e2c64dd6) 完整仓库，固定提交 `aad58ddcc2103058b4c2deffc48a3c13e2c64dd6`，上游工作树保持干净。后端通过独立包命名空间调用实际 `ScientificEngine`、`HeavyGenerator` 两阶段交互生成/视觉润色及 `PostProcessor`，保留原生提示词、主题、HTML 提取和元数据流程。

平台适配集中在用户模型网关、任务进度/取消、数据隔离和浏览器通信。关闭原生跨用户 HTML 缓存回退，并拒绝不完整阶段或降级占位页面。未启动上游独立账户、数据库或 Next 服务；前端按上游完整文档 iframe 的方式保留生成页面，解除原宿主样式覆盖和窄栏限制，实验伙伴按需展开，观察记录继续使用原接口。

Tailwind 浏览器运行库固定 4.1.18，KaTeX、公式字体使用当前锁文件中的本地安装资源内嵌。iframe 保持 `sandbox="allow-scripts"`，禁止外网访问。新增 DPR=2、最小绘图字体、桌面/手机/恢复宽度、暂停与结果变化检查；失败时允许一次定向修复，再失败则不保存交付。宿主结果消息改为有界合并，避免连续动画一直推迟上报。

## 问题归因

旧快速排序 canvas 位图和 CSS 都是 790×260，在 DPR=2 屏幕没有提供两倍像素，标签只有 11px。旧摩擦实验使用已经放大的 `canvas.height` 再乘 DPR，重绘后 CSS 高度从 150/200 增长到 300/400。去掉宿主注入样式仍能复现，说明主要缺陷位于生成 HTML 的绘图实现和验收遗漏，不能仅归因外层 CSS，也没有证据证明它是上游仓库固定存在的绘图代码错误。证据见 [旧画布测量](before-diagnosis.json)、[去掉宿主后的测量](before-without-host.json)。

## 验收结果与限制

- 后端 12 项、浏览器校验器 7 项通过；类型检查、相关 lint 和 Vite 构建通过。
- 宿主浏览器 4 项通过，覆盖 1440/390 宽度的新旧页面；另一个可选旧真实样例测试因未提供路径而跳过。API 使用隔离模拟响应，iframe 使用真实模型生成的 HTML。
- 原生页面保持布局；DPR=2 位图尺寸匹配、缩放不累积增高；公式加载、单步计数和保存结果一致、开关实验伙伴、切换页签及刷新后观察记录保留均通过。
- 快速排序样例经过定向模型修复数组副本/重复交换问题，并移除生成端丢弃最后一次结果的节流。单步比较为 1，实际排序 `[5,3,8,4,2] → [2,3,4,5,8]`，见 [排序校验](algorithm-after.json)。这些样例修复不能算成原生首轮生成成功。
- 摩擦实验重新生成后通过检查；三组参数的实际停车距离与 `v₀²/(2μg)` 相符，绝对误差约 `10⁻¹³`，见 [数值校验](friction-numerics.json)。
- **原生复用不保证算法正确**：额外独立生成的快速排序页面通过通用浏览器检查，却只更新计数、没有更新数组；实际运行已确认，见 [反例](quicksort-final-semantic.json)。已据此补充生成约束，但约束不是正确性证明。当前验收只对上述经过检查的样例负责，尚无通用学科正确性自动验收。

完整机器记录：[verification.json](verification.json)。视觉效果：[桌面](native-1440.png)、[手机](native-390.png)，对照 [旧高清屏画布](before-quicksort-dpr2-before.png)。

## 安装、启用与回归

1. 按 `DEPENDENCIES.md` 安装后端锁定依赖；在 frontend 执行 `pnpm install --frozen-lockfile`，保留完整依赖（含 Tailwind 浏览器库）。运行 `python scripts/install-maic-ui.py`；统一安装脚本已包含这一步。
2. 后端 PATH 需要 Node，且已安装 Playwright Chromium。没有新迁移。启用需协调发布前端与后端重启；旧 HTML、旧观察记录继续读取，重新生成的实验才进入原生链路。
3. `frontend/dist-practice-native` 是初次本地验收构建，没有单独发布。实际线上使用 `/tmp/edu-resource-tools-release-20261014T044119Z`，已包含原生模拟实验。线上首页与发布包哈希一致，旧版本备份仍保留；具体版本、启动时间及检查范围见 `deployment.json`。

可执行的相关检查：

```sh
PYTHONPATH=backend/src python -m pytest backend/src/tests/practice -q
cd frontend
node --import tsx --test scripts/practice-validation.test.ts
pnpm exec tsc -p tsconfig.self-learning.json
pnpm exec eslint src/practice/Practice.tsx src/practice/presentation.ts
```

本机端到端复验可在运行预览服务后执行：

```sh
PRACTICE_FRONTEND_URL=http://127.0.0.1:5226 \
PRACTICE_NATIVE_ARTIFACT=/home/zxqs_ep/Edu_AI/.runtime/practice-native-acceptance/quicksort.json \
pnpm exec playwright test -c playwright.practice.config.ts
```

真实模型验收产物保存在本机 `.runtime/practice-native-acceptance`，不依赖真实用户账户或生产实验数据。
