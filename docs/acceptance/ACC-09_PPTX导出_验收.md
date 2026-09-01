# ACC-09 · OpenMAIC 课堂 PPTX 导出 · 验收文档

> 对应 spec：[`../spec/SPEC-09_PPTX导出.md`](../spec/SPEC-09_PPTX导出.md)
>
> 对应 Phase：4 · 地图：[`../../项目总览地图.md`](../../项目总览地图.md)
>
> 通用环境：见 [验收 README §2](README.md)
>
> 状态：✅ Phase 4 已通过（2026-07-25）

---

## 1. 功能范围

从课堂已落库的 OpenMAIC scenes 在浏览器生成离线 PPTX，保留核心视觉、可编辑
公式、媒体和演讲者备注，并在真实课堂播放页提供下载入口。

---

## 2. 验收标准（DoD）

| 编号 | 标准 | 判定与证据 |
| --- | --- | --- |
| AC-09-1 | 只导出 slide scenes；顺序稳定；输入不变；ZIP/slide 数量有效 | ✅ JSZip OOXML tests |
| AC-09-2 | 背景、中文富文本、图片、几何、旋转、z-order 正确 | ✅ 检查 slide XML 的 EMU、字体、颜色和对象顺序 |
| AC-09-3 | 基础形状、线、图表、表格为 native/editable 对象 | ✅ slide XML + `ppt/charts/chart1.xml` |
| AC-09-4 | LaTeX 变为 editable `<m:oMath>`，不含 DOCX-only `xmlns:w` | ✅ 公式单测及浏览器下载件检查 |
| AC-09-5 | 图片/音频/视频可内嵌；媒体失败不破坏 deck，视频保留 poster | ✅ PNG/MP4/MP3 ZIP entries + 404 poster fallback test |
| AC-09-6 | `speech` actions 写入 speaker notes | ✅ notes XML 自动化与下载件检查 |
| AC-09-7 | 文件名安全、重复点击单飞、成功/失败均释放状态 | ✅ 3 项下载 helper tests |
| AC-09-8 | 真实课堂页有可见导出入口；下载非空；页面保持响应 | ✅ 浏览器下载 50,978 bytes，按钮恢复可用、0 console errors |
| AC-09-9 | 前后端相关回归、lint、生产构建通过 | ✅ 前端 44 tests；lint 0 errors；build success；后端 34 tests |

---

## 3. 自动化测试

```powershell
cd Edu_AI
npm test -- --run
# 44 passed

npm run lint
# 0 errors；88 条迁移前存量 warning

npm run build
# success；PPTX exporter 为独立懒加载 chunk

cd backend/src
conda run -n edu-ai python -m pytest `
  tests/test_classroom_media.py `
  tests/test_classroom_service.py `
  tests/test_classroom_validation.py -q
# 34 passed，1 条既有 jieba/pkg_resources deprecation warning
```

`src/openmaic/pptxExporter.test.ts` 使用 JSZip 直接检查：

- `[Content_Types].xml`、slide/notes/rels；
- EMU 几何、旋转、字体、颜色和 z-order；
- chart、PNG、MP4、MP3 entries；
- `<m:oMath>`、Cambria Math、speaker notes；
- 404 媒体失败后的 poster 与后续正文。

---

## 4. 浏览器验收

入口：`http://127.0.0.1:4173/#player-smoke` 的 AC-09 夹具；真实产品入口已接到
`ClassroomPlayerPage` 顶部。

2026-07-25 实测：

| 项 | 结果 |
| --- | --- |
| 下载文件 | `C:\Users\Tang\Downloads\PPTX 浏览器验收_冒泡排序.pptx` |
| 文件大小 | 50,978 bytes（非空） |
| ZIP entries | 39 |
| 关键部件 | `[Content_Types].xml`、`ppt/slides/slide1.xml`、notes、rels 均存在 |
| slide XML | 含中文“冒泡排序”与 editable `<m:oMath>` |
| notes XML | 含 speech“这是冒泡排序” |
| 页面状态 | “PPTX 已开始下载”；按钮恢复 enabled |
| 控制台 | 0 errors |

---

## 5. 回归 / 边界

| 用例 | 预期 / 结果 |
| --- | --- |
| 无 slide scenes | 明确失败，不产生空文件 |
| 重复点击 | 第二次立即返回，不重复构建 |
| 标题含非法字符/保留名 | 安全替换，扩展名固定 `.pptx` |
| 单元素不支持 | 省略该元素，其他内容继续导出 |
| 图片/媒体 HTTP 失败 | 单元素降级；视频有 poster 时保留 poster |
| 公式非法且有 SVG path | 退化为不可编辑 SVG；无 fallback 时省略公式，不损坏 deck |

---

## 6. 签收

| 项 | 内容 |
| --- | --- |
| 验收人 / 日期 | Codex 自动化 + 浏览器验收 / 2026-07-25 |
| 结论 | ✅ Phase 4 通过；课堂同源数据可下载为含视觉、OMML、媒体和 notes 的 PPTX |
| 遗留 | PowerPoint 动画时间线和 PPTX 导入不在 Phase 4；MP4 导出进入 Phase 5 |
