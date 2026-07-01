# ACC-03 · ParsePDF 解析迁移 · 验收文档

> 对应 spec：[`../spec/SPEC-03_ParsePDF_解析迁移.md`](../spec/SPEC-03_ParsePDF_解析迁移.md)
> 对应 Phase：1（解析替换）· 地图：[`../../项目总览地图.md`](../../项目总览地图.md) §2
> 通用环境：见 [验收 README §2](README.md)
> 状态：⏳ 收口中（Python 直连）

---

## 1. 功能范围

**架构定位**：最初方案设想「经 sidecar `/api/parse-pdf` / `OpenMaicClient.parse_pdf()`」。**实际落地为 Python 直连 MinerU Cloud provider**（`from app.integrations.pdf import get_pdf_parser; get_pdf_parser().parse(pdf_bytes, filename=...)`），业务侧经 `RAGSystem._parse_pdf_with_mineru` 契约消费，不经 sidecar。详见 SPEC-03。

**做**：edu_ai 用**直连 MinerU Cloud provider** 替换 `scripts/mineru.py` 本地解析链路，RAG 入库改走在线解析；强制默认 `mineru-cloud` 不回退 unpdf；影子模式并行比对确认不劣化。

**做（Phase 1 收口新增）**：删 legacy 死目录 `Edu_AI/api/src/modules/rag_v2/rag-main/`（连字符，Python 无法 import 的旧本地 CLI 死代码）；归档删除 `scripts/mineru.py`（已无 Python 引用）。

**不做**：不改分块策略（仅换解析输入源）；直连形态下的 BYOK / job 化前端体验 / SSRF 边界移交后续 Phase。

---

## 2. 验收标准（DoD）

| 编号 | 标准 | 判定 |
| --- | --- | --- |
| AC-03-1 | `get_pdf_parser().parse(...)`（默认 mineru-cloud）对真实教材 PDF 返回非空 `text` + `images` + `formulas[].latex` | |
| AC-03-2 | **强制默认 `mineru-cloud`**，绝不误走 `unpdf`（`__init__.py` 缺省即 mineru-cloud，未知值抛错不降级） | |
| AC-03-3 | 影子比对：新链路 `text` 覆盖度 ≥ 旧链路（字符数/章节完整度不劣化） | |
| AC-03-4 | 影子比对：公式识别数、图片数不劣化 | |
| AC-03-5 | RAG 入库走新链路（经 `_parse_pdf_with_mineru`）后，抽样问答检索质量不回退 | |
| AC-03-6 | 托管 MinerU key 生效：`.env` 提供 key，业务侧不传 key 也能解析成功 | |
| AC-03-10 | **契约不变**：`_parse_pdf_with_mineru` 返回键集 `{markdown_text, images[{path,name,page_offset}], success, error, temp_dirs_to_cleanup}` 稳定，`textbook_knowledge_graph` 复用不破 | |
| ~~AC-03-7~~ | ~~生产环境客户端传非法 baseUrl → 403（SSRF）~~ → **改由直连形态处理**：无客户端 baseUrl 入口，base_url 来自服务端 `.env`；边界防护**移交后续 Phase** | 移交 |
| ~~AC-03-8~~ | ~~解析以 job 形式呈现，前端无需感知同步阻塞~~ → sidecar 形态验收项，直连下由 `parse_async` 线程池化避免阻塞事件循环；job 化前端体验**移交后续 Phase** | 移交 |
| AC-03-9 | MinerU Cloud 不可达时 edu_ai 不崩：provider 抛 `PdfParseError` → `_parse_pdf_with_mineru` 返回 `success=False+error`，可重试 | |

---

## 3. 测试方法

### 3.1 provider 直连冒烟（AC-03-1/2/6）
```python
from app.integrations.pdf import get_pdf_parser
res = get_pdf_parser().parse(pdf_bytes, filename="ch1.pdf")   # 默认 mineru-cloud
assert res.text.strip()
assert any(f.get("latex") for f in res.formulas)
assert res.metadata["pageCount"] > 0
```
- AC-03-2：`PDF_PARSER_PROVIDER` 不设时 `get_pdf_parser()` 返回 `MinerUCloudProvider`（缺省 mineru-cloud），不会走 unpdf。语义已由 `tests/chat/test_rag_v2_runtime_import.py` 覆盖。
- AC-03-6：托管 key 场景（`.env` 提供 `PDF_MINERU_CLOUD_API_KEY`），业务侧不传 key 仍成功。

### 3.2 影子比对（AC-03-3/4）
旧脚本 `scripts/mineru.py` 已随 Phase 1 收口删除，无法再本地并行跑「旧链路」。影子比对以**归档基线**（旧链路历史产物）对同一批 PDF 与新直连产物比对：
```
file | base_chars | new_chars | new/base | base_formulas | new_formulas | base_imgs | new_imgs
```
- 通过判定：每份 `new_chars/base_chars ≥ 0.95`（或人工确认差异是 MinerU 更全）；公式/图片数 `new ≥ base`。

### 3.3 RAG 质量回归（AC-03-5）
- 用同一组测试问答对（golden set），分别用旧/新入库结果检索，比对 Top-K 命中与答案质量（人工或既有评测脚本）。通过：新 ≥ 旧。

### 3.4 job 化体验（移交后续 Phase）
- sidecar 形态的 job 进度组件验收在直连形态下暂不适用；直连以 `parse_async`（线程池）避免阻塞事件循环。前端 job 化体验移交后续 Phase。

### 3.5 失败/边界（AC-03-9）
- 模拟 MinerU Cloud 不可达（错误 base_url / 断网）触发解析：预期 provider 抛 `PdfParseError`，`_parse_pdf_with_mineru` 返回 `success=False + error`，业务标失败可重试，进程不崩。

---

## 4. 回归 / 边界

| 用例 | 预期 |
| --- | --- |
| 超长文档 | provider 内部长超时轮询；超时抛 `PdfParseError` → 标失败可重试 |
| 扫描版/图片型 PDF | MinerU VLM 尽力解析；`text` 可能少，图片多——记录基线不判失败 |
| 中文公式/表格 | `language:'ch'` 下正确；公式进 LaTeX、表格进 tables |
| 未显式设 provider | 默认 mineru-cloud（不落 unpdf）；未知值抛错不静默降级 |

---

## 5. 签收

| 项 | 内容 |
| --- | --- |
| 验收人 / 日期 | |
| 结论 | |
| 遗留 | AC-03-7（SSRF/BYOK 边界）、AC-03-8（job 化前端体验）移交后续 Phase；影子比对以归档基线进行 |
