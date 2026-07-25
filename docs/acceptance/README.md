# edu_ai · OpenMAIC 迁移 · 验收文档（ACCEPTANCE）索引

> 本目录是 **OpenMAIC 迁移**的验收层文档。每份对应 `../spec/` 里的一份 spec，回答三件事：**实现什么功能 / 验收标准（Done 的定义）/ 怎么测试**。
> **三层关系（指针互通）**：
> - **地图** `../../项目总览地图.md` — 全貌，§6 文档索引指向 spec 与本目录。
> - **spec** `../spec/SPEC-0x` — 规格，规定「怎么接、字段/接口长什么样」。每份 spec 顶部指向对应 `ACC-0x`。
> - **验收** 本目录 `ACC-0x` — 验收，规定「怎么证明它对了」。每份 ACC 顶部指回 `SPEC-0x` 与地图。
> 最近更新：2026-07-25 · 状态：持续维护

---

## 0. 对照表（spec ↔ 验收 ↔ Phase）

| 验收文档 | 对应 spec | Phase | 当前状态 |
| --- | --- | --- | --- |
| [ACC-00 Web 检索层（Bocha+Tavily）](ACC-00_Web检索层_验收.md) | SPEC-00 | 1.5 前置 | ⏳ 待实现 |
| [ACC-01 Sidecar 裁剪与部署](ACC-01_Sidecar裁剪与部署_验收.md) | SPEC-01 | 0 | ✅ 核心已验证（2026-06-30），容器化待补 |
| [ACC-02 数据契约](ACC-02_数据契约_验收.md) | SPEC-02 | 全阶段地基 | ⏳ 待做（随 Phase 2 落库校验） |
| [ACC-03 ParsePDF 解析迁移](ACC-03_ParsePDF解析迁移_验收.md) | SPEC-03 | 1 | ⏳ 待做 |
| [ACC-04 GenerateClassroom 课件生成](ACC-04_GenerateClassroom课件生成_验收.md) | SPEC-04 | 2 | ⏳ MVP 待做（切割见 SPEC-04 §0.1）|
| [ACC-05 异步任务协议](ACC-05_异步任务协议_验收.md) | SPEC-05 | 横切 | ⏳ 待做 |
| [ACC-06 Provider 与 BYOK 安全边界](ACC-06_Provider与BYOK安全边界_验收.md) | SPEC-06 | 横切 | ⏳ 待做 |
| [ACC-07 OpenMaicClient 客户端](ACC-07_OpenMaicClient客户端_验收.md) | SPEC-07 | 横切 | ⏳ 待做 |
| [ACC-08 前端集成播放](ACC-08_前端集成播放_验收.md) | SPEC-08 | 3 | ✅ 已通过（2026-07-25；音色自然度保留人工复核） |

---

## 1. 验收文档统一格式（每份 ACC 都按此写）

1. **功能范围**：这块迁移「实现了什么」，边界（做/不做）。
2. **验收标准（DoD）**：逐条**可判定**（有明确通过/不通过条件），编号 `AC-0x-n`，可勾选。
3. **测试方法**：环境准备 + 用例（步骤 + 命令/curl/pytest + **预期输出**）。
4. **回归 / 边界 / 失败用例**：故意触发错误，验证降级与安全边界。
5. **签收**：验收人、日期、结论、遗留项。

---

## 2. 通用测试环境（所有 ACC 共用，各文档不重复）

| 项 | 值 / 说明 |
| --- | --- |
| sidecar | `D:\github\OpenMAIC`，conda env `openmaic`（node22+pnpm10），`pnpm dev` → `http://localhost:3000` |
| 本机代理坑 | curl 测 localhost **必须加** `--noproxy "localhost,127.0.0.1"`（本机 `127.0.0.1:7897` 会拦）；PowerShell `Invoke-WebRequest` 不受影响 |
| PATH 坑 | pnpm install 前把 `C:\Program Files\Git\usr\bin` 加进 PATH（提供 `rm`）|
| 模型名坑 | `DEFAULT_MODEL=deepseek:deepseek-v4-pro`（不是 deepseek-chat）|
| MinerU 前缀坑 | 云端用 `PDF_MINERU_CLOUD_*`（不是 `PDF_MINERU_*`）|
| edu_ai 后端 | `cd Edu_AI/api/Edu_AI` → `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`（conda `edu_ai`）|
| edu_ai 前端 | `cd Edu_AI` → `npm run dev` |
| 测试素材 | 一份真实教材 PDF（计算思维/数据结构任一章），放 `scratchpad/` 或 `scripts/` 测试目录 |

> 这些坑来自 Phase 0 实测（记忆 `openmaic-sidecar-run-notes`）。任何 ACC 的本机测试都先满足这一节。

---

## 3. 验收判定与状态流转

- 每条 `AC-0x-n` 只有 **通过 / 不通过 / 阻塞**（依赖未就绪）三态。
- 一份 ACC「验收通过」= 全部 `AC` 通过（阻塞项需注明依赖并单列）。
- 通过后回填本 README §0 状态列 + 对应 spec 顶部状态 + 地图（若结构性变化）。
- **先影子后下线**：涉及替换旧链路的（ACC-03/04），影子比对通过才算验收，旧链路下线属 Phase 6 另行验收。

---

## 4. 变更记录

| 日期 | 版本 | 变更 |
| --- | --- | --- |
| 2026-07-01 | v0.1 | 建立验收目录，对 SPEC-01~08 各写一份 ACC，打通 地图↔spec↔验收 指针 |
| 2026-07-25 | v0.2 | ACC-08 完成 LessonTimeline、旁白/聚焦、受控视频和中文/公式专项验收 |
