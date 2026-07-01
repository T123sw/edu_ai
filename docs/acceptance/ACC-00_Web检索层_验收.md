# ACC-00 · Web 检索层（Bocha + Tavily Extract）· 验收文档

> 对应 spec：[`../spec/SPEC-00_Web检索层_Bocha搜索与Tavily抽取.md`](../spec/SPEC-00_Web检索层_Bocha搜索与Tavily抽取.md)
> Phase：1.5 前置（Phase 2 之前）· 地图：[`../../项目总览地图.md`](../../项目总览地图.md)
> 通用环境：见 [验收 README §2](README.md) · 状态：⏳ 待实现

---

## 1. 功能范围

**做**：edu_ai 侧用 **Bocha 搜索 + Tavily Extract** 替换现有 deepsearch+SearxNG+自建爬虫的"找 URL / 取全文"两步；双档 `basic`（Bocha 摘要）/`full`（Tavily 全文）；结果复用现有清洗/存储/入 RAG 链路；`run_deepsearch_and_crawl` 签名、`/agent/deepsearch-and-crawl` 端点、前端不变。

**不做**：删旧代码（Phase 6 下线）；课件生成（Phase 2）；web 图片入库（Phase 5）；改前端交互（仅"深度研究"映射 `depth=full`）。

---

## 2. 验收标准（DoD）

| 编号 | 标准 | 判定 |
| --- | --- | --- |
| AC-00-1 | **Bocha 搜索通**：中文 query 真实调用 → 返回 ≥1 条 `{url, title, summary}`，秒级 | |
| AC-00-2 | **Tavily Extract 通**：传一批 URL（含中文页面）→ 返回 markdown 全文；部分失败进 `failed_results` 不整批崩 | |
| AC-00-3 | **basic 档**：`depth=basic` 只调 Bocha、用 summary 作内容，不触发 Tavily | |
| AC-00-4 | **full 档**：`depth=full` 先 Bocha 得 URL 再 Tavily Extract 抽全文；批量 ≤20 自动分批 | |
| AC-00-5 | **入 RAG 复用**：`save_to_kb=true` → 落 `DOCUMENTS_ROOT/web/{owner}/*.md`（带来源头）+ `rag_system.import_document` + 可检索；course KB 关联（有 course_id 时） | |
| AC-00-6 | **签名/端点/前端不变**：`run_deepsearch_and_crawl` 主签名与 `POST /agent/deepsearch-and-crawl` 行为兼容（仅新增可选 `depth`）；回归旧调用不报错 | |
| AC-00-7 | **降级**：Bocha 失败 → `{ok:false, message}` 不抛栈；Tavily 全失败 → 退回 basic（用 Bocha summary）；单 URL 失败跳过 | |
| AC-00-8 | **key 不落日志**：`BOCHA_API_KEY`/`TAVILY_API_KEY` 不出现在日志/持久化明文 | |
| AC-00-9 | **不依赖 SearxNG/Selenium**：新链路运行全程不启动 SearxNG、不调 automation_spider（grep 运行日志/进程） | |

---

## 3. 测试方法

### 3.1 Bocha 搜索冒烟（AC-00-1）
```bash
# 配好 BOCHA_API_KEY 后，pytest 或脚本直调 search_bocha("冒泡排序 教学")
# 断言：len(hits)>=1；hits[0].url 以 http 开头；hits[0].content(summary) 非空
```

### 3.2 Tavily Extract 冒烟（AC-00-2/4）
```bash
# 直调 extract_tavily([<bocha 返回的3个中文url>], depth="basic")
# 断言：至少 1 条 status=success 且 content(markdown) 非空；>20 URL 自动分批
```

### 3.3 双档端到端（AC-00-3/4/5）
```bash
curl -X POST http://127.0.0.1:8000/api/agent/deepsearch-and-crawl \
  -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' \
  -d '{"query":"冒泡排序 教学","depth":"basic","save_to_kb":true}'
# 预期 ok:true，results 为 Bocha 摘要，imported_documents 非空
# 再测 depth:"full" → results 为全文，DOCUMENTS_ROOT/web/<owner> 下有 .md
```

### 3.4 回归签名（AC-00-6）
- 不传 `depth` 的旧请求体照常工作（默认 basic）；前端"深度搜索"页无需改即可用（深度按钮映射 full）。

### 3.5 降级注入（AC-00-7）
- 临时置错 `BOCHA_API_KEY` → `ok:false` 且有 message，不 500 栈；置错 `TAVILY_API_KEY`、`depth=full` → 退回 basic 用摘要。

---

## 4. 回归 / 边界

| 用例 | 预期 |
| --- | --- |
| query 为空 | 400 / `ok:false` 明确提示 |
| Bocha 返回 0 条 | `ok:false, message="未找到相关链接"`（沿用现有语义） |
| Tavily 单次 >20 URL | 自动分批，不报 400 |
| 中文页面抽取 | markdown 正文非空（Extract 语言无关） |
| 长文超上下文预算 | `chunks_per_source`/摘要截断，注入前不超模型限制 |

---

## 5. 签收

| 项 | 内容 |
| --- | --- |
| 验收人 / 日期 | |
| 结论 | |
| 遗留 | web 图片入库（Phase 5）；旧链路物理下线（Phase 6）；深度档 reranking 调优 |
