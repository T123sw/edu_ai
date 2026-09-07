# 外部模型 API 与本地部署清单

核查日期：2026-09-07。根据当前代码及实际 `.env` 整理；已配置不代表已验证调用成功。

| 用途 | 当前模型／服务 | 能否本地部署或替换 |
|---|---|---|
| 文本问答、Agent、课件生成 | DeepSeek V4 Flash / Pro | **可换本地 Qwen3 等模型**；不是把同名云端模型直接搬到本机 |
| 看图、图片理解 | `deepseek-v4-flash-vision-exp`，图片能力待验证 | **可换本地 Qwen3-VL 8B** |
| 文本和图片向量 | Gemini Embedding 2 Preview，经 VectorEngine | **可替换**：文本用 BGE-M3；图片先生成描述再向量化，需重建索引 |
| 知识库重排 | BGE-reranker-v2-m3，经硅基流动；已配置，代码默认未开启 | **可本地部署同款模型** |
| 网页结果重排 | 博查 rerank 接口；实际模型参数需核对 | **可换本地 BGE 重排** |
| PDF、扫描件、公式识别 | MinerU Cloud | **可部署本地 MinerU**，需增加接口适配 |
| 课堂语音合成 | Qwen3-TTS-Flash | **可换本地 VoxCPM** |
| 通用语音识别 | 百度语音 | **可换本地 Whisper** |
| 视频入库语音识别 | faster-whisper，默认 small | **已经是本地实现** |
| 网页、图片搜索和正文抽取 | 博查、Tavily | **不是模型**；保留联网服务，或改成本地资料搜索 |

## 视觉模块怎么解决

- **MinerU**：解析教材、扫描件、表格和公式。
- **Qwen3-VL 8B**：看图、解释图表、生成图片描述。
- **BGE-M3**：检索文字和图片描述；召回后把原图交给视觉模型回答。

注意：BGE-M3 不直接理解图片，不能直接接替现有图片 embedding。切换向量模型需要重建索引；现有部分 Agent 规划复用了视觉配置，替换前需要拆开。

## 部署建议

当前服务器为 **双 RTX 3090，各 24GB 显存**。

优先评估本地部署 **Qwen3-VL、BGE-M3、BGE 重排、MinerU、VoxCPM、Whisper**，文本 DeepSeek 暂时保留。模型需分配显存、后台任务排队，不建议全部同时满负载运行。

PPTX、MP4 和字幕导出已使用本地渲染工具，不需要额外部署文生视频模型。

以上是替换建议，尚未部署或完成本机效果测试。

参考：[Qwen3-VL](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)、[BGE-M3](https://huggingface.co/BAAI/bge-m3)、[BGE 重排](https://huggingface.co/BAAI/bge-reranker-v2-m3)、[MinerU](https://github.com/opendatalab/MinerU)、[VoxCPM](https://github.com/OpenBMB/VoxCPM)、[faster-whisper](https://github.com/SYSTRAN/faster-whisper)。
