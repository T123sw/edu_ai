# `content.md` 协议草案 v1

`content.md` 采用纯 Markdown 固定字段协议。

主系统只负责提供页面语义和内容，不传具体版式，也不感知有哪些版式。PPT 模块根据：
- `Role`
- `Blocks` 的内容形态
- 是否包含媒体
- `layout-contracts.md` 的选择规则
- 相邻页避免重复的策略

自动决定最终版式。

---

## 1. 文件整体结构

文件由两部分组成：

1. Deck 级元信息
2. 多个 Slide 块

整体格式如下：

```md
# Deck
- Title: ...
- Subtitle: ...
- Theme: ...

---

## Slide 1
- Role: ...
- Title: ...

### Blocks
- ...

### Notes
...
```

---

## 2. Deck 级字段

`# Deck` 段可选，建议支持：

- `Title`
  整套 PPT 标题

- `Subtitle`
  整套 PPT 副标题

- `Theme`
  主题 ID
  如果缺失，则以接口请求中的 `theme_id` 为准

---

## 3. 每页固定字段

每一页必须以 `## Slide N` 开始，并包含以下固定字段：

- `Role:`
  必填
  允许值：
  - `cover`
  - `toc`
  - `section`
  - `content`
  - `thanks`

- `Title:`
  必填
  当前页主标题

- `### Blocks`
  必填
  当前页内容块，至少 1 个

- `### Notes`
  可选
  当前页讲稿或备注
  这一整节可以完全省略

说明：
- 主系统不传具体版式
- 主系统不传 `layout_hint`
- 具体版式完全由 PPT 模块内部决定

---

## 4. `Blocks` 支持类型

`### Blocks` 下允许以下 block 类型：

### 4.1 `Lead`

用于：
- 封面副标题
- 单句摘要
- 章节导语

写法：

```md
- Lead: From Multi-modal to Omni-modal
```

### 4.2 `Bullets`

用于：
- 普通要点列表
- 解释页
- 结论页

写法：

```md
- Bullets:
  - 要点一
  - 要点二
  - 要点三
```

### 4.3 `Meta`

用于：
- 汇报人
- 导师
- 时间
- 单位

写法：

```md
- Meta:
  - 汇报人：[你的名字]
  - 导师：[导师姓名]
  - 时间：202X年X月
```

### 4.4 `Toc`

用于目录页。

写法：

```md
- Toc:
  - 范式演进与全模态的定义
  - 核心机制：模态的离散化与表征统一
  - SOTA模型微观架构剖析
  - 底层瓶颈挑战与课题组研究契合点
```

### 4.5 `Cards`

用于：
- 三点并列
- 三种特征
- 多卡片信息

写法：

```md
- Cards:
  - Title: 特征1
    Text: 支持任意模态输入与输出
  - Title: 特征2
    Text: 完全共享底层参数权重
  - Title: 特征3
    Text: 支持低延迟时空交互
```

可选附加字段：
- `Subtitle`
- `Icon`

### 4.6 `Comparison`

用于双栏对照。

写法：

```md
- Comparison:
  - Left-Title: Late-Fusion
    Left-Items:
      - 各模态独立处理
      - 延迟高
      - 信息丢失严重
    Right-Title: Early-Fusion
    Right-Items:
      - 原生统一输入
      - 无外挂编码器
      - 可直接跨模态生成
```

### 4.7 `Process`

用于：
- 流程
- 阶段
- 研究路线

写法：

```md
- Process:
  - Step-Title: Stage 1
    Step-Text: 文本预训练
  - Step-Title: Stage 2
    Step-Text: 多模态交错预训练
  - Step-Title: Stage 3
    Step-Text: 指令微调与人类对齐
```

### 4.8 `Media`

用于图片或视频。

写法：

```md
- Media:
  - Kind: image
  - URL: https://example.com/figure.png
  - Alt: 图片描述
  - Caption: 图注
```

或：

```md
- Media:
  - Kind: video
  - URL: https://example.com/demo.mp4
  - Poster-URL: https://example.com/demo-cover.jpg
  - Caption: 视频说明
```

媒体字段定义：

- `Kind`
  必填
  `image` 或 `video`

- `URL`
  必填
  主系统给 PPT 服务的媒体地址
  生产环境通常为远程 URL；本地联调时也允许使用仓库内相对路径，例如 `assets/test/1.jpg`

- `Alt`
  可选
  仅图片推荐提供

- `Poster-URL`
  可选
  仅视频推荐提供

- `Caption`
  可选
  图注或视频说明

---

## 5. 媒体规则

v1 媒体约束如下：

- 每页最多 1 个 `Media` block
- 图片支持：
  - `png`
  - `jpg`
  - `jpeg`
  - `webp`
  - `svg`
- 视频支持：
  - `mp4`
  - `webm`
  - `mov`
- 主系统只传远程 URL
- 本地联调时可直接传仓库内相对路径
- PPT 服务负责下载到当前 revision 本地目录
- 运行时 HTML 里只引用本地相对路径
- 媒体默认保持比例，不强制拉伸
- 媒体展示应使用 `object-fit: contain` 和居中对齐

---

## 6. 版式选择规则

PPT 模块内部按下列逻辑自动选版式：

- `Role = cover`
  使用 `cover`

- `Role = toc`
  使用 `toc`

- `Role = section`
  使用 `section`

- `Role = thanks`
  使用 `thanks`

- `Role = content`
  根据 `Blocks` 自动判断：
  - `Cards` -> `card-layout`
  - `Comparison` -> `standard-text-comparison`
  - `Process` -> `standard-text-process`
  - `Media + Bullets` -> 媒体版式
  - 普通 `Bullets / Lead / Meta` -> `standard-text` 系列自动选择

附加规则：
- 尽量避免相邻页重复使用同一种文本版式
- 若存在媒体，优先选择媒体版式
- 具体选择细节以 `layout-contracts.md` 为准

---

## 完整示例

```md
# Deck
- Title: 全模态大模型（Omni-modal LLMs）：底层机制、前沿架构与未来挑战
- Subtitle: 哈尔滨工程大学 计算机本博班大二组会汇报
- Theme: heu_academic_elegant

---

## Slide 1
- Role: cover
- Title: 全模态大模型的底层机制、前沿架构与挑战

### Blocks
- Lead: From Multi-modal to Omni-modal: Tokenization, Alignment, and Beyond
- Meta:
  - 汇报人：[你的名字]（本博班大二）
  - 导师：[导师姓名]
  - 时间：202X年X月

### Notes
各位老师、师兄师姐，大家上午好。今天我汇报的主题是《全模态大模型的底层机制、前沿架构与挑战》。

---

## Slide 2
- Role: toc
- Title: 目录

### Blocks
- Toc:
  - 范式演进与全模态的定义
  - 核心机制：模态的离散化与表征统一
  - SOTA模型微观架构剖析
  - 底层瓶颈挑战与课题组研究契合点

### Notes
本次汇报分为四个部分。首先梳理架构演进，其次分析模态离散化机制，接着介绍前沿模型，最后讨论瓶颈与研究规划。

---

## Slide 3
- Role: content
- Title: 架构拓扑的演进：从“级联拼图”到“原生统一”

### Blocks
- Comparison:
  - Left-Title: Mid / Late Fusion
    Left-Items:
      - 各模态分阶段处理
      - 延迟较高
      - 信息在模块间传递时可能损失
    Right-Title: Early Fusion
    Right-Items:
      - 图像、语音、文本一开始即统一进入模型
      - 无外挂编码器
      - 更适合 Any-to-Any 生成

### Notes
这一页的重点是说明融合时间点不断提前，最终走向原生统一输入。

---

## Slide 4
- Role: content
- Title: 真正的全模态（Omni-modal）核心特征

### Blocks
- Cards:
  - Title: Any-to-Any
    Text: 支持任意模态输入，并能直接输出任意模态结果。
  - Title: Native Integration
    Text: 各模态共享底层参数与统一表征空间。
  - Title: Real-time Spatial-temporal
    Text: 支持低延迟、流式输入与时空感知。

### Notes
这一页适合三列卡片布局，强调 omni-modal 的三个核心标准。

---

## Slide 5
- Role: section
- Title: 核心机制：Continuous to Discrete

### Blocks
- Lead: 全模态系统的底层关键，在于如何把连续信号压缩为离散 Token。

### Notes
接下来进入核心机制部分，重点讨论图像和音频为什么必须离散化。

---

## Slide 6
- Role: content
- Title: 核心痛点：为什么必须“离散化”？

### Blocks
- Bullets:
  - 连续特征适合分类和理解，但难以直接做自回归生成
  - 离散特征天然契合 LLM 的 Next-Token Prediction 机制
  - 万物皆可 Token 化，是 Any-to-Any 生成的前提

### Notes
这一页主要解释为什么多模态生成最终还是要回到 token 体系。

---

## Slide 7
- Role: content
- Title: 视觉离散化：VQ 与密码本机制

### Blocks
- Bullets:
  - 连续特征提取 -> 在 Codebook 中寻找最相似特征向量 -> 输出索引
  - 索引即为一个 Visual Token
  - 最新进展：MAGVIT-v2 通过 LFQ 缓解密码本坍缩
- Media:
  - Kind: image
  - URL: https://example.com/vq-diagram.png
  - Alt: VQ 与 Codebook 机制示意图
  - Caption: 图：VQ 量化流程与密码本索引机制

### Notes
这页建议采用媒体版式，一边展示示意图，一边解释 VQ 的步骤。

---

## Slide 8
- Role: content
- Title: 音频离散化：解耦与 RVQ

### Blocks
- Bullets:
  - 语义 Token 提取“说了什么”
  - 声学 Token 保留音色、情绪与背景音
  - RVQ 通过多级量化保留更丰富的高频细节
- Media:
  - Kind: video
  - URL: https://example.com/audio-demo.mp4
  - Poster-URL: https://example.com/audio-demo-cover.jpg
  - Caption: 演示：语义与声学解耦后的重建效果

### Notes
这页适合大媒体加少量文字，便于突出视频演示效果。

---

## Slide 9
- Role: content
- Title: 三阶段训练范式：从“会说话”到“看懂并会表达”

### Blocks
- Process:
  - Step-Title: Stage 1
    Step-Text: 纯文本预训练，得到强大的语言逻辑能力。
  - Step-Title: Stage 2
    Step-Text: 多模态交错预训练，学习跨模态对齐。
  - Step-Title: Stage 3
    Step-Text: 指令微调与人类对齐，提升真实交互效果。

### Notes
这里强调多模态系统通常不是一次训练完成，而是分阶段构建能力。

---

## Slide 10
- Role: thanks
- Title: 感谢聆听

### Blocks
- Lead: Q & A
- Bullets:
  - 请各位老师与师兄师姐批评指正
  - 汇报人：[你的名字]
  - 哈尔滨工程大学 计算机学院

### Notes
以上就是今天的汇报内容，欢迎大家提问交流。
```
