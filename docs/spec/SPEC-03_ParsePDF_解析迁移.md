# SPEC-03 · ParsePDF 解析迁移（Phase 1）

> **验收文档**：[`../acceptance/ACC-03_ParsePDF解析迁移_验收.md`](../acceptance/ACC-03_ParsePDF解析迁移_验收.md) · **地图**：[`../../项目总览地图.md`](../../项目总览地图.md)
> 目标：edu_ai 用 sidecar `/api/parse-pdf`（MinerU Cloud）替换 `scripts/mineru.py` 本地解析链路，RAG 入库改走在线解析。
> 这是**最独立、最低风险**的一条链路，先换它验证 sidecar 形态。
> 上游实现（已核对）：`app/api/parse-pdf/route.ts`（93 行）→ `lib/document`（extractDocument / documentArtifactToParsedPdfContent）→ `lib/pdf/pdf-providers.ts` + `mineru-cloud.ts`（339 行）。
> 关联：SPEC-06（key/SSRF）、SPEC-07（OpenMaicClient.parse_pdf）。

---

## 1. 端点契约（已核对源码）

```
POST /api/parse-pdf
Content-Type: multipart/form-data
fields:
  pdf:        File            (必填；缺失 → 400 MISSING_REQUIRED_FIELD)
  providerId: 'unpdf' | 'mineru' | 'mineru-cloud'   (缺省回退 'unpdf')
  apiKey?:    string          (BYOK；托管 provider 时被忽略)
  baseUrl?:   string          (BYOK；托管时忽略；生产环境走 SSRF 校验)
→ 200 { data: ParsedPdfContent }
错误：
  400 INVALID_REQUEST         Content-Type 非 multipart / 无效
  400 MISSING_REQUIRED_FIELD  无 pdf
  403 INVALID_URL             SSRF 校验不通过（生产 + 客户端 baseUrl）
  5xx INTERNAL_ERROR          解析失败
```

关键源码行为（`route.ts`）：
- `effectiveProviderId = providerId || 'unpdf'`。edu_ai **必须显式传 `mineru-cloud`**。
- `managed = isServerConfiguredProvider('pdf', providerId)`；managed 时 `clientBaseUrl/apiKey` 一律忽略（SPEC-06）。
- `clientBaseUrl && NODE_ENV==='production'` → `validateUrlForSSRF`，失败 403。
- key/baseUrl 经 `resolvePDFApiKey / resolvePDFBaseUrl` 解析（托管优先）。

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

---

## 3. MinerU Cloud v4 流程（sidecar 内部，供理解，不需 edu_ai 实现）

```
POST {base}/file-urls/batch   body: files[].name, enable_formula, enable_table, model_version:'vlm', language:'ch'
  → batch_id + 预签名上传 URL
PUT 预签名URL 上传 PDF        （★ 不能带 Content-Type，OSS 签名敏感）
GET {base}/extract-results/batch/{batch_id}   每 2.5s 轮询，最长 15min
  → state=done & full_zip_url
下载 ZIP → full.md + content_list.json + images/ → 归一为 ParsedPdfContent
```

- `language:'ch'` 已是中文默认。
- 解析可能耗时数分钟 → **edu_ai 侧 httpx 超时至少 20min 或走异步**（SPEC-07 §4）。当前 sidecar 的 parse-pdf 是**同步 route**（阻塞到解析完），不是 job/poll；edu_ai 客户端要按长超时同步调用处理，或后续给 parse-pdf 也套 job 协议（SPEC-05 §6 备注）。

---

## 4. edu_ai 侧改造

### 4.1 新增 `OpenMaicClient.parse_pdf()`（详见 SPEC-07）

```python
result: ParsedPdf = await openmaic.parse_pdf(
    file=pdf_bytes, filename=..., provider_id="mineru-cloud",
    # 托管场景不传 api_key/base_url；BYOK 场景由上层传入
)
```

### 4.2 替换点

| 旧 | 新 |
| --- | --- |
| `scripts/mineru.py` 本地解析（GPU/本地权重）| `OpenMaicClient.parse_pdf(provider_id='mineru-cloud')` |
| RAG 入库前的本地 PDF→文本 | 用 `result.text` 分块入库；`result.images/pdfImages` 走已有图片本地化管道 |

> 先**影子模式**：新旧并行跑同一批 PDF，比对 `text` 覆盖度、公式/表格识别、图片数量，确认对齐后再切主链路、下线 `scripts/mineru.py`（下线属 Phase 6）。

### 4.3 RAG 入库对齐检查

- 分块策略沿用 edu_ai 现有 chunker，输入源换成 `result.text`。
- 图片：`metadata.pdfImages[].pageNumber` 保留页码，衔接 `Phase6A2_image_localization`。
- 公式：`formulas[].latex` 可单独入检索，提升「计算思维/数据结构」类公式召回。

---

## 5. 错误与降级

| 场景 | 处理 |
| --- | --- |
| sidecar 不可达 | edu_ai 回退提示「解析服务不可用」，不崩；可选临时回退旧 `scripts/mineru.py`（下线前保留）|
| MinerU 超时（>15min sidecar 内部超时）| 返回 5xx；edu_ai 标记该文档解析失败，允许重试 |
| 大文件/多页 | 遵守 MinerU 云端配额；分文档提交 |
| providerId 未显式传 | 会回退 `unpdf`（弱解析）→ **edu_ai 客户端强制默认 `mineru-cloud`**，避免误走 unpdf |

---

## 6. 验收清单

- [ ] `OpenMaicClient.parse_pdf('mineru-cloud')` 对一份真实教材 PDF 返回非空 `text` + `images` + `formulas`（LaTeX）
- [ ] 影子比对：新链路 `text` 覆盖度 ≥ 旧链路；公式/图片不劣化
- [ ] RAG 入库走新链路，检索质量不回退（抽样问答对比）
- [ ] 托管 MinerU key 生效（客户端不传 key 也能解析，SPEC-06）
- [ ] 生产环境客户端传恶意 baseUrl → 403（SSRF 生效）
