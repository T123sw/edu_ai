# SPEC-09 · OpenMAIC 课堂 PPTX 导出

> **验收文档**：[`../acceptance/ACC-09_PPTX导出_验收.md`](../acceptance/ACC-09_PPTX导出_验收.md) · **地图**：[`../../项目总览地图.md`](../../项目总览地图.md)
>
> 对应 Phase：4 · 状态：✅ 已实现并通过验收（2026-07-25）

---

## 1. 目标与边界

edu_ai 使用与交互课堂相同的 `Stage → Scene[] → Slide + Action[]` 落库源数据，
在浏览器端生成可离线打开的 `.pptx`。导出不得依赖 sidecar 的 React store，也不得
重新请求或重新生成课件。

本阶段包含：

- slide scene 过滤、稳定排序和 16:9 / 16:10 / 4:3 布局；
- 中文富文本、背景、图片、基础形状、线、图表、表格和几何/z-order；
- LaTeX → MathML → OMML，可在 PowerPoint 中继续编辑；
- 图片、音频、视频数据内嵌；视频媒体失败时保留 poster；
- `speech` action 写入 speaker notes；
- 真实课堂页“导出 PPTX”入口、进度/错误状态、重复点击保护和安全文件名。

不在本阶段：PPTX 导入、动画时间线写入 PowerPoint、MP4 导出（Phase 5）。

---

## 2. 依赖与模块

依赖固定到仓库内 vendored OpenMAIC fork：

| 包 | 来源 | 用途 |
| --- | --- | --- |
| `pptxgenjs` | `file:../openmaic-sidecar/packages/pptxgenjs` | 生成 OOXML/ZIP、公式与媒体 |
| `mathml2omml` | `file:../openmaic-sidecar/packages/mathml2omml` | MathML → OMML |
| `temml` | npm | LaTeX → MathML |
| `jszip` | dev dependency | OOXML 验收 |

edu_ai 落点：

| 文件 | 职责 |
| --- | --- |
| `src/openmaic/pptxExporter.ts` | 纯数据输入 → PPTX Blob |
| `src/openmaic/latexToOmml.ts` | 公式转换与 PowerPoint 兼容后处理 |
| `src/openmaic/pptxDownload.ts` | 文件名、单飞锁、Blob 下载；按点击懒加载导出器 |
| `src/openmaic/PptxExportButton.tsx` | 课堂页交互和可见状态 |

---

## 3. 输入契约与顺序

```ts
interface ClassroomPptxInput {
  title: string;
  scenes: readonly PptxExportScene[];
}
```

只接收 `content.type === "slide"` 且存在 `content.canvas` 的 scene。优先按
`scene.order` 稳定升序，缺失时使用源数组索引；不得修改输入。没有任何 slide 时
明确失败，不能下载空文件。

---

## 4. 转换规则

| DSL | PPTX |
| --- | --- |
| solid/image/gradient background | slide background；gradient 当前取末端色作为兼容降级 |
| text | HTML runs；支持粗体/斜体/下划线/删除线/颜色/字体/字号及框体样式 |
| image | data URL 直接内嵌；HTTP/blob 先转 base64；保留位置、尺寸、旋转、翻转、透明度 |
| shape | 基础 SVG M/L/H/V/Z path → editable custom geometry；文字为同层 overlay |
| line | editable line，保留颜色、宽度、虚线和箭头 |
| chart/table | editable native chart/table |
| latex | Temml → MathML → `mathml2omml` → `<m:oMath>`，Cambria Math 属性写入 |
| video/audio | 支持 data/path/HTTP 转内嵌 media；视频 poster 作为 cover |
| speech action | 逐条文本写入 speaker notes |

单个不支持或不可用元素按“省略该元素、继续整份 deck”降级；远程视频失败而 poster
可用时导出 poster 图片。任何单元素失败不得破坏其他 slide、后续元素和 notes。

---

## 5. 下载工作流

- 真实入口：`#classroom-player?course_id=...&classroom_id=...` 顶部。
- 文件名为 `<课件标题>.pptx`；替换 Windows/浏览器非法字符、处理保留名和空标题。
- 同一按钮仅允许一个在途任务；重复点击返回但不重复构建。
- 成功后显示“PPTX 已开始下载”；失败显示原因；两条路径均在 `finally` 释放状态。
- `pptxExporter` 使用动态 `import()`，不计入课堂普通播放的首屏主 chunk。

---

## 6. 验收清单

- [x] 有效 OOXML ZIP、slide 数量/顺序、输入不可变
- [x] 背景、文本、图片、几何、z-order、形状、线、图表、表格
- [x] LaTeX 输出 editable OMML
- [x] 音视频内嵌及失败 poster 降级
- [x] `speech` → speaker notes
- [x] 文件名、重复点击、成功/失败清理
- [x] 真实课堂入口与浏览器下载
- [x] 前端测试/lint/build及课堂后端回归

完整证据见 ACC-09。
