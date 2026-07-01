# SPEC-03 · ParsePDF 解析迁移（Phase 1）

> **状态**：⏳ 收口中（Python 直连）
> **验收文档**：[`../acceptance/ACC-03_ParsePDF解析迁移_验收.md`](../acceptance/ACC-03_ParsePDF解析迁移_验收.md) · **地图**：[`../../项目总览地图.md`](../../项目总览地图.md)
> 目标：edu_ai 用 **Python 直连 MinerU Cloud provider** 替换 `scripts/mineru.py` 本地解析链路，RAG 入库改走在线解析。
> 这是**最独立、最低风险**的一条链路，先换它。
>
> **架构定位（与最初方案的差异，已实现并真实验证）**：最初 spec 设想「edu_ai 经 OpenMAIC sidecar `/api/parse-pdf` / `OpenMaicClient.parse_pdf()`」。**实际落地改为 Python 直连**：edu_ai 后端进程内直接用 httpx 同步调用 MinerU Cloud v4（batch→PUT 上传→轮询→下载 zip→归一），不经 sidecar、不经 Node。落点：
> - `app/integrations/pdf/base.py`：`PdfParseProvider`(ABC) + `ParsedPdf` + `PdfParseError`
> - `app/integrations/pdf/mineru_cloud.py`：`MinerUCloudProvider`（直连 MinerU Cloud）
> - `app/integrations/pdf/__init__.py`：`get_pdf_parser()` 单例 + `write_parsed_markdown()`
> - 业务侧经 `RAGSystem._parse_pdf_with_mineru(...)` 契约消费（契约不变）。
>
> 直连解析已真实跑通（一份真实教材 PDF ≈13.5s 返回非空结果）。
> 关联：SPEC-06（key/托管）；原 SPEC-07（OpenMaicClient.parse_pdf）在直连形态下不再是本链路依赖。

---

## 1. 解析契约（Python 直连，已实现）

直连形态下**没有 edu_ai 消费的 HTTP 端点**，契约是进程内的 Python 接口：

```python
from app.integrations.pdf import get_pdf_parser, ParsedPdf, PdfParseError

parser = get_pdf_parser()                              # 进程内单例，默认 mineru-cloud（读 .env）
result: ParsedPdf = parser.parse(pdf_bytes, filename="ch1.pdf")   # 同步；async 侧用 parser.parse_async(...)
md = result.text                                       # 解析失败抛 PdfParseError
```

`ParsedPdf`（`app/integrations/pdf/base.py`，dataclass）：
- `text: str` —— 正文（MinerU 为 full.md 的 markdown）
- `images: List[str]` —— base64 data URL 数组
- `tables: List[dict]` / `formulas: List[dict]`（元素含 `latex`）
- `metadata: dict` —— `pageCount` / `parser` / `taskId`(batch_id) / `imageMapping` 等
- `is_empty()` —— text 为空判定

Provider 选择行为（`__init__.py`）：
- `PDF_PARSER_PROVIDER` 缺省即 `mineru-cloud`；`mineru`/`mineru_cloud` 同义。**默认就是 mineru-cloud，不回退 unpdf**。
- 未知 provider 值 → 抛 `PdfParseError`（不静默降级）。
- 托管 key 由 `.env` 的 `PDF_MINERU_CLOUD_API_KEY` / `PDF_MINERU_CLOUD_BASE_URL` 提供（SPEC-06）。

> **业务契约不变**：`RAGSystem._parse_pdf_with_mineru(...)` 仍返回
> `{markdown_text, images:[{path,name,page_offset}], success, error, temp_dirs_to_cleanup}`，
> 内部改为委托 `get_pdf_parser()`。`textbook_knowledge_graph.py` 复用同一方法。

---

## 2. 返回结构 `ParsedPdfContent`（已核对 `lib/types/pdf.ts`）

```ts
interface ParsedPdfContent {
  text: string;                 // 提取正文（MinerU 为 full.md 内容）
  images: string[];             // base64 data URL 数组
  tables?:   { page, data: string[][], caption? }[];
  formulas?: { page, latex, position? }[];           // MinerU 公式→LaTeX
  layout?:   { page, type:'title'|'text'|'image'|'table'|'formula', content, position? }[];
  metadata?: {
    fileName?, fileSize?, pageCount: number, parser?, processingTime?, taskId?,
    imageMapping?: Record<string,string>,             // img_1 → data:image/png;base64,...
    pdfImages?: { id, src, pageNumber, description?, width?, height? }[],
    [k:string]: unknown
  };
}
```

edu_ai 关心：`text`（入 RAG 分块）、`images` / `metadata.imageMapping` / `metadata.pdfImages`（配图定位，衔接已有 Phase6A2 图片本地化）、`formulas`（公式检索）、`metadata.pageCount`。

> 上表是 OpenMAIC `ParsedPdfContent` 的完整形状，供理解。直连形态下 edu_ai 的 `ParsedPdf`（§1）取其关心子集。

---

## 3. MinerU Cloud v4 流程（现由 edu_ai 的 `MinerUCloudProvider` 内部实现）

```
POST {base}/file-urls/batch   body: files[].name, enable_formula, enable_table, model_version:'vlm', language:'ch'
  → batch_id + 预签名上传 URL
PUT 预签名URL 上传 PDF        （★ 不能带 Content-Type，OSS 签名敏感）
GET {base}/extract-results/batch/{batch_id}   轮询直到 state=done
  → full_zip_url
下载 ZIP → full.md + content_list.json + images/ → 归一为 ParsedPdf
```

- `language:'ch'` 已是中文默认。
- 该流程原设想在 sidecar 内；**现改由 edu_ai 后端进程 httpx 同步实现**（`mineru_cloud.py`），async 调用点用 `parse_async`（内部 `asyncio.to_thread`，见 `base.py`）避免阻塞事件循环。
- 解析可能耗时数分钟 → provider 内部按长超时轮询。

---

## 4. edu_ai 侧改造（Python 直连，已落地）

### 4.1 调用入口

```python
from app.integrations.pdf import get_pdf_parser
result = get_pdf_parser().parse(pdf_bytes, filename="ch1.pdf")   # 同步
# async 侧：await get_pdf_parser().parse_async(pdf_bytes, filename="ch1.pdf")
```

无需 `OpenMaicClient` / sidecar。

### 4.2 替换点

| 旧 | 新 |
| --- | --- |
| `scripts/mineru.py` 本地解析（GPU/本地权重）| `get_pdf_parser().parse(provider 默认 mineru-cloud)` |
| RAG 入库前的本地 PDF→文本 | 经 `RAGSystem._parse_pdf_with_mineru`（契约不变，内部委托 provider）分块入库；`images` 走已有图片本地化管道 |
| pipeline 批量解析 `app/pipeline/tasks.py` | 已改为 `parse_async` + `write_parsed_markdown` 落盘（`{stem}.md + images/`），兼容旧目录消费方 |

> 影子模式：新旧并行跑同一批 PDF，比对 `text` 覆盖度、公式/表格识别、图片数量，确认不劣化。旧脚本 `scripts/mineru.py` 已随 Phase 1 收口归档删除（见 ACC-03 §1）。

### 4.3 RAG 入库对齐检查

- 分块策略沿用 edu_ai 现有 chunker，输入源换成 provider 的 `text`。
- 图片：`metadata.imageMapping` / `pdfImages[].pageNumber` 保留页码，衔接 `Phase6A2_image_localization`。
- 公式：`formulas[].latex` 可单独入检索，提升「计算思维/数据结构」类公式召回。

---

## 5. 错误与降级

| 场景 | 处理 |
| --- | --- |
| MinerU Cloud 不可达 / 上游报错 | provider 抛 `PdfParseError`；`_parse_pdf_with_mineru` 返回 `success=False + error`，业务标该文档解析失败可重试，不崩 |
| MinerU 超时 | provider 内部长超时轮询；超时抛 `PdfParseError`，同上 |
| 大文件/多页 | 遵守 MinerU 云端配额；分文档提交 |
| provider 未显式指定 | 默认即 `mineru-cloud`（`__init__.py`），**不回退 unpdf**；未知值抛错不静默降级 |
| SSRF（生产传恶意 baseUrl）| 直连形态不接受客户端 baseUrl，base_url 来自服务端 `.env`（托管），原 sidecar SSRF 校验点不再适用；BYOK/边界防护移交后续 Phase |

---

## 6. 验收清单

- [ ] `get_pdf_parser().parse(...)`（默认 mineru-cloud）对一份真实教材 PDF 返回非空 `text` + `images` + `formulas`（LaTeX） —— 已真实验证 ≈13.5s
- [ ] 影子比对：新链路 `text` 覆盖度 ≥ 旧链路；公式/图片不劣化
- [ ] RAG 入库走新链路（经 `_parse_pdf_with_mineru` 契约），检索质量不回退（抽样问答对比）
- [ ] 强制默认 `mineru-cloud` 不回退 unpdf
- [ ] 托管 MinerU key 生效（`.env` 提供，业务侧不传 key 也能解析，SPEC-06）
- [ ] 契约不变：`_parse_pdf_with_mineru` 返回结构键集稳定
- [ ] ~~生产环境客户端传恶意 baseUrl → 403（SSRF）~~ → 直连形态无客户端 baseUrl 入口，**移交后续 Phase**
