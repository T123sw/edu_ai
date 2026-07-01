# ACC-03 · ParsePDF 解析迁移 · 验收文档

> 对应 spec：[`../spec/SPEC-03_ParsePDF_解析迁移.md`](../spec/SPEC-03_ParsePDF_解析迁移.md)
> 对应 Phase：1（解析替换）· 地图：[`../../项目总览地图.md`](../../项目总览地图.md) §2
> 通用环境：见 [验收 README §2](README.md)
> 状态：⏳ 待做

---

## 1. 功能范围

**做**：edu_ai 用 `OpenMaicClient.parse_pdf(mineru-cloud)` 替换 `scripts/mineru.py`，RAG 入库改走在线解析；影子模式并行比对，确认对齐后切主链路。

**不做**：本轮不删 `scripts/mineru.py`（下线属 Phase 6）；不改分块策略（仅换解析输入源）。

---

## 2. 验收标准（DoD）

| 编号 | 标准 | 判定 |
| --- | --- | --- |
| AC-03-1 | `parse_pdf('mineru-cloud')` 对真实教材 PDF 返回非空 `text` + `images` + `formulas[].latex` | |
| AC-03-2 | 客户端**强制默认 `mineru-cloud`**，绝不误走 `unpdf` | |
| AC-03-3 | 影子比对：新链路 `text` 覆盖度 ≥ 旧链路（字符数/章节完整度不劣化） | |
| AC-03-4 | 影子比对：公式识别数、图片数不劣化 | |
| AC-03-5 | RAG 入库走新链路后，抽样问答检索质量不回退 | |
| AC-03-6 | 托管 MinerU key 生效：客户端不传 key 也能解析成功 | |
| AC-03-7 | 生产环境客户端传非法 baseUrl → 403（SSRF，见 ACC-06） | |
| AC-03-8 | 解析以 job 形式呈现（SPEC-05 §6 做法1），前端无需感知同步阻塞 | |
| AC-03-9 | sidecar 不可达时 edu_ai 不崩，给「解析服务不可用」，可重试 | |

---

## 3. 测试方法

### 3.1 客户端冒烟（AC-03-1/2/6）
落点建议 `Edu_AI/api/tests/test_parse_pdf.py`（pytest-asyncio）。
```python
res = await client.parse_pdf(file=pdf_bytes, filename="ch1.pdf")  # 默认 mineru-cloud
assert res["text"].strip()
assert any(f.get("latex") for f in res.get("formulas", []))
assert res["metadata"]["pageCount"] > 0
```
- AC-03-2：断言默认 provider_id 为 `mineru-cloud`（不传时）。
- AC-03-6：托管 key 场景不传 api_key，仍成功。

### 3.2 影子比对脚本（AC-03-3/4）
建 `scripts/e2e/shadow_parse_compare.py`：对同一批 PDF 跑「旧 `scripts/mineru.py`」与「新 parse_pdf」，输出对比表：
```
file | old_chars | new_chars | new/old | old_formulas | new_formulas | old_imgs | new_imgs
```
- 通过判定：每份 `new_chars/old_chars ≥ 0.95`（或人工确认差异是 MinerU 更全）；公式/图片数 `new ≥ old`。

### 3.3 RAG 质量回归（AC-03-5）
- 用同一组测试问答对（golden set），分别用旧/新入库结果检索，比对 Top-K 命中与答案质量（人工或既有评测脚本）。通过：新 ≥ 旧。

### 3.4 job 化体验（AC-03-8）
- 前端上传 PDF → 观察走统一 job 进度组件（排队→解析中→完成），无长时间白屏卡死。

### 3.5 失败/边界（AC-03-9）
```bash
# 停 sidecar 后触发解析：预期 edu_ai job=failed(SIDECAR_UNAVAILABLE)，前端提示可重试
```

---

## 4. 回归 / 边界

| 用例 | 预期 |
| --- | --- |
| 超长文档（>15min）| sidecar 内部超时 → 5xx → edu_ai 标失败可重试 |
| 扫描版/图片型 PDF | MinerU VLM 尽力解析；`text` 可能少，图片多——记录基线不判失败 |
| 中文公式/表格 | `language:'ch'` 下正确；公式进 LaTeX、表格进 tables |
| 未显式传 providerId | 客户端补默认 mineru-cloud（不落 unpdf）|

---

## 5. 签收

| 项 | 内容 |
| --- | --- |
| 验收人 / 日期 | |
| 结论 | |
| 遗留 | 旧链路下线待 Phase 6（ACC 另立）|
