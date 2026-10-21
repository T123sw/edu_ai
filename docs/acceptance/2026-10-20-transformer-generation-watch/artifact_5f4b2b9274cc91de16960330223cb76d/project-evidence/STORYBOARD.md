---
format: 1920x1080
duration: 305s
message: "自注意力让每个位置向全序列发问，用 softmax(QK^T/√dk)V 加权取回内容；多头把这件事在不同子空间里并行做 h 次"
arc: 动机 → 角色拆分 → 公式四步 → 缩放理由 → 手算演示 → 多头 → 配置核对 → 回顾
audience: 希望系统学习 Transformer 的初学者
mode: autonomous
---

# 自注意力与多头注意力 — 分镜

课程视觉契约见 `frame.md`。13 个画面，中文旁白，306 秒左右；每个画面只推进一层信息，玩具矩阵的四步用四张同版式的画面硬切，读作一次连续的手算演示。旁白无逐词时间戳，画面节奏按分镜内的相对时间点推进（按各自 duration 比例）。

## Video direction

深色矩阵课堂：`#0f172a` 底 + 极淡 60px 网格，一个柔和的青色辉光在焦点区后面。信息一律用矩阵单元、箭头、权重条表达；Q 恒为青 `#38bdf8`，K 恒为绿 `#34d399`，V 恒为紫 `#a78bfa`，需要读者核对的数字用暖黄 `#fbbf24`。每屏左上角是场景标题（64px）+ 步骤小字（28px），底部一条 28px 的灰色导航轨。入场一律 0.45–0.7s `power2.out`，矩阵逐行出现（stagger 0.1s），箭头用 `stroke-dashoffset` 画出来，权重条用 `scaleX` 从左生长；不做退场动画，尾帧静止可读。

## Frame 1 — 开场：自注意力是什么

- status: animated
- src: compositions/frames/01-title.html
- duration: 13.8s
- poster: 4s
- transition_in: crossfade
- scene: 标题 + 一句话定义：每个位置去看同一序列的所有位置
- voiceover: "这一节拆开 Transformer 里最关键的一块：自注意力。一句话概括它的作用：让序列里每个位置，都去看同一序列的所有位置，再按相关性更新自己的表示。"
- blueprint: titlecard-reveal
- rules: waterfall-entry

左侧一段 96px 的主标题“自注意力与多头注意力”，其下 48px 副题“Q / K / V 与缩放点积计算思路”，再下 28px 灰色标签“Transformer 基础 · 第 3 节”。右侧一块 `surface` 面板里放公式 `attention(Q, K, V) = softmax(QKᵀ / √dk) · V`（48px，`softmax` 与 `√dk` 用青色），面板下方 28px 标注“一个公式，四个步骤”。时间点：0–1.2s 标签与副题上滑淡入；1.2–2.6s 主标题 waterfall 进场；2.6–4.2s 公式面板淡入，公式里 `Q`、`K`、`V` 依次点亮为青/绿/紫；4.2s 后静止保持，仅面板辉光极缓呼吸（`sine.inOut`，位移 ≤6px 或透明度 ≤0.05）。

## Frame 2 — it 到底指向谁

- status: animated
- src: compositions/frames/02-why.html
- duration: 24.9s
- poster: 8s
- transition_in: crossfade
- scene: 句子里的词元与 it 向 animal / street 的注意力弧线，右侧三条权重条
- voiceover: "先看一个具体的难处。The animal didn't cross the street because it was too tired，这里的 it 指 animal 还是 street？模型只能从句内关系里找答案：把 it 和 animal、street 放在一起比较，看谁更配“太累了”。自注意力让 it 向每个词发问，按相关性把内容取回来，重组成自己的新表示。"
- rules: svg-path-draw, stat-bars-and-fills

舞台上半部是句子，两个块：第一行 `The  animal  didn't  cross  the  street`（词元 chip：`surface-2` 底、28px、圆角 10px、内边距 18px/24px，词与词间距 12px）；第二行 `because  it  was  too  tired`，其中 `it` chip 用 2px 青色描边高亮。舞台下半部右对齐三条权重条（`weight-bars`）：`animal 0.62`（青）、`street 0.24`（青 45%）、`tired 0.14`（灰）。时间点：0–3.5s 两行词元逐个上浮出现（stagger 0.1s）；3.5–7s 从 `it` 出发画弧线到 `animal` 与 `street`（SVG `stroke-dashoffset`，青 3px，带箭头），弧线在上方绕行不压字；7–13s 三条权重条从左生长，数值以 `warm` 显示；13–20s 在左下加一块 `callout`：“自注意力 = 在句内建立词与词的关系；每个位置关注包括自己在内的所有位置”；20s 后静止。词元 chip 与弧线位置关系：弧线起点是 `it` chip 上沿中点，终点是被关注 chip 的上沿中点。

## Frame 3 — 自注意力 vs 交叉注意力

- status: animated
- src: compositions/frames/03-vs-cross.html
- duration: 22.3s
- poster: 8s
- transition_in: crossfade
- scene: 左右两卡片对照，底部一条判据
- voiceover: "别和上一节的交叉注意力混了。交叉注意力的查询来自解码器，键和值来自编码器，是两个序列之间的对齐；自注意力的查询、键、值都来自同一个序列，每个位置关注包括自己在内的所有位置。判断方法只有一条：看来源是不是同一个。"
- blueprint: comparison-split

两张等宽的 `surface` 卡片（各 780×520，间距 96px，居中于舞台），入场时分别从左右带着 `rotateY(±12deg)` 翻开到位。左卡标题 48px“自注意力 Self-Attention”，下方三个 `role-tag`：`Q · 同一序列`、`K · 同一序列`、`V · 同一序列`，再一行 36px 正文“每个位置关注包括自己在内的所有位置”。右卡标题“交叉注意力 Cross-Attention”，标签：`Q · 解码器`、`K · 编码器输出`、`V · 编码器输出`，正文“解码器每个位置读取输入序列的所有位置”。卡片底部各一行 28px 灰色小字：“来源：一个序列” / “来源：两个序列”。左右卡到位后，各弹一枚 28px 徽章（左：青“同一序列”，右：紫“两个序列”），然后底部 48px 判据行淡入：“判据：看 Q 和 K/V 是不是来自同一个序列”。时间点：0–1.6s 两卡翻开；1.6–6s 左卡标签逐条出现；6–10s 右卡标签逐条出现；10–14s 两枚徽章 spring-pop；14–18s 判据行从下方上滑淡入；18s 后静止。

## Frame 4 — 为什么拆成 Q / K / V

- status: animated
- src: compositions/frames/04-qkv.html
- duration: 30.9s
- poster: 10s
- transition_in: crossfade
- scene: 一张“一身三职”的冲突卡 + Q/K/V 三张投影卡
- voiceover: "为什么一个词要变成三个向量？同一个向量要同时演三个角色：向别人发问、被别人匹配、把自己的内容交出去。而“容易被找到”和“携带有用内容”是两回事，挤在一个向量里会互相牵制。Bahdanau 的 h 下标 j 已经一身两职，换成自注意力更尖锐。解法是乘三个不同的可学习矩阵：Query 负责发问，Key 负责被匹配，Value 负责被取走。"
- blueprint: grid-card-assemble
- rules: spring-pop-entrance

上半部左侧一张 `surface` 卡（560×260）：“一个向量 x” + 三个 28px 标签 `发问` / `被匹配` / `内容` 挤在同一个方块里，用 `danger` 描边并标 28px 小字“三种角色互相牵制”；右侧一张 36px 正文卡：“容易被找到 ≠ 携带有用内容。Bahdanau 的 hⱼ 已经一身两职，自注意力里更尖锐。”下半部三张等宽投影卡（各 480×300，间距 48px）依次出现：卡 1 顶部 `role-tag` 青色 `Q · 发问`，公式 `Q = x·W^Q`（48px），底注 28px“学习‘我在找什么’”；卡 2 绿色 `K · 被匹配`，`K = x·W^K`，注“学习‘我如何被找到’”；卡 3 紫色 `V · 内容`，`V = x·W^V`，注“学习‘我能提供什么’”。三卡下方一行 36px 结论：“三个不同的可学习矩阵 → 三套表示，互不牵制”。时间点：0–4s 上半部冲突卡与正文卡淡入；4–8s 三角色标签在方块里轮流高亮一次（每次 0.5s，青色描边脉冲）；8–12s 冲突卡描边转 `danger` 并出现“互相牵制”注记；12–22s 三张投影卡依次 spring-pop（各 0.55s，错开 0.9s），每卡出现时把对应角色色点亮；22–27s 结论行出现；27s 后静止。

## Frame 5 — 缩放点积注意力的四步

- status: animated
- src: compositions/frames/05-formula.html
- duration: 30.1s
- poster: 10s
- transition_in: crossfade
- scene: 公式逐段点亮 + 四个步骤条
- voiceover: "于是公式可以很短。先算查询和所有键的点积，得到打分；再逐项除以根号 dk；然后用 softmax 把分数变成加起来等于一的权重；最后用这些权重对 Value 加权求和。矩阵写法就是 softmax 括号 Q 乘 K 的转置，除以根号 dk，再乘 V。输出的每一行仍是一个向量，维度是 dv，也就是这个位置看过全句之后的新表示。"
- blueprint: kinetic-type-beats

舞台中央一行大公式（64px，`tabular-nums`）：`softmax( QKᵀ / √dk ) · V`，分成四个可独立点亮的部分：`QKᵀ`、`/ √dk`、`softmax( … )`、`· V`。公式下方一条四段式步骤梯（每段宽 340px，56px 圆徽 + 28px 标签 + 32px 说明）：① 打分 `QKᵀ` — 查询与所有键做点积；② 缩放 `÷ √dk` — 把量级拉回；③ 归一 `softmax` — 权重相加为 1；④ 取内容 `· V` — 对 Value 加权求和。说明放在 32px，不要挤成两行以上。底部一行 36px 补充：“每行输出是一个 dv 维向量 = 该位置看过全句后的新表示”。时间点：0–4s 公式骨架（括号与乘号）先出现；4–9s 第一段 `QKᵀ` 点亮为青色、步骤①圆徽填充；9–14s 第二段 `/ √dk` 点亮、步骤②填充；14–19s 第三段 `softmax(…)` 点亮、步骤③填充；19–24s 第四段 `· V` 点亮（`V` 用紫色）、步骤④填充；24–28s 底部补充行上滑出现；28s 后静止，已点亮的段落保持，未点亮的保持 35% 透明度。

## Frame 6 — 为什么除以 √dk

- status: animated
- src: compositions/frames/06-scaling.html
- duration: 26.8s
- poster: 9s
- transition_in: crossfade
- scene: 方差随 dk 增长的条形，softmax 饱和的两组权重对比
- voiceover: "为什么非要除根号 dk？假设 q 和 k 的各分量独立、均值零、方差一，点积的方差大约是 dk。dk 越大，分数越极端，最大的那个会把 softmax 推到接近 one-hot 的饱和区，那里输出几乎不变、梯度接近零，模型就学不动了。除根号 dk 把方差拉回一的量级，让 softmax 留在梯度健康的区间。"
- rules: stat-bars-and-fills, counting-dynamic-scale

左侧（x 96–880）：“点积的方差 ≈ dk”标题（48px），两根竖条（高 420px、宽 96px）：`dk = 4 → 方差 4`（青，标注 `√dk = 2`）与 `dk = 64 → 方差 64`（暖黄，标注 `√dk = 8`），条上数字用 32px `counting-dynamic-scale` 从 0 数到目标值。右侧（x 980–1780）：“未缩放：softmax 饱和”面板，三条 `weight-bars`：`0.998 / 0.001 / 0.001`（暖黄，注明“近 one-hot → 梯度 ≈ 0”，`danger` 小字）；其下“除以 √dk 之后”面板，同样三条：`0.545 / 0.227 / 0.227`（青，注明“梯度健康”）。底部 36px 一行：“论文脚注假设：q、k 各分量独立、均值 0、方差 1 → 点积方差 ≈ dk”。时间点：0–4s 左侧标题与两根空条形出现；4–8s 数字数上去（`dk` 从 4 到 64 的对比只做一次，不做连续计数动画超过 1.2s）；8–14s 右侧“未缩放”面板淡入，三条权重条生长并在数值旁标 `danger` 警告；14–20s “除以 √dk 之后”面板淡入，权重条生长；20–24s 底部脚注行出现；24s 后静止。

## Frame 7 — 玩具矩阵：3 个词元，dk = 4

- status: animated
- src: compositions/frames/07-setup.html
- duration: 12.3s
- poster: 4s
- transition_in: cut
- scene: Q、K、V 三个 3×4 矩阵并排，行标签为 猫 / 追 / 老鼠
- voiceover: "下面手算一遍。三个词元：猫、追、老鼠。每个词元的 dk 等于四，所以 Q、K、V 都是三行四列，根号 dk 等于二。"
- rules: waterfall-entry, spring-pop-entrance

舞台横向三个 `matrix-block`（96×96 单元，间距 120px，整体居中）：`Q`（青标题）、`K`（绿标题）、`V`（紫标题）。行标签 28px 灰：猫 / 追 / 老鼠；列标签 `d1 d2 d3 d4`（28px 灰，可只在 Q 上完整标注，K/V 只留列标）。数值（32px tabular，`ink`）：
Q：`[1, 0, 1, 0]`、`[0, 1, 0, 1]`、`[1, 1, 0, 0]`；
K：`[1, 0, 1, 0]`、`[0, 1, 1, 0]`、`[1, 0, 0, 1]`；
V：`[1, 2, 0, 1]`、`[0, 1, 2, 0]`、`[2, 0, 1, 1]`。
每个矩阵下方一行 28px 形状说明：`Q: 3 × 4`、`K: 3 × 4`、`V: 3 × 4`。右上角一枚 28px 徽章“dk = 4 → √dk = 2”（青色描边）。时间点：0–1.5s 三个矩阵标题与行标签出现；1.5–7s 三个矩阵逐行 waterfall（每行 0.35s，整体 stagger ≤0.5s）；7–10s 三行形状说明淡入，徽章 spring-pop；10s 后静止。

## Frame 8 — 第一步 QKᵀ，第二步 ÷ √dk

- status: animated
- src: compositions/frames/08-scores.html
- duration: 20.6s
- poster: 7s
- transition_in: cut
- scene: QKᵀ 得 3×3 打分，再除以 2
- voiceover: "第一步，Q 乘 K 的转置，形状变成三乘三：第 i 行第 j 列就是第 i 个查询和第 j 个键的点积。结果第一行是二、一、一，第二行是零、一、一，第三行是一、一、一。第二步除以根号 dk，第一行变成一、零点五、零点五。"
- rules: stat-bars-and-fills, spring-pop-entrance

与上一屏同一套坐标：左区（x 140 起）是“QKᵀ”计算提示卡——两行 48px 公式 `(3×4) · (4×3) → (3×3)` 与 28px 注“第 i 行第 j 列 = qᵢ · kⱼ”；右区是结果 `matrix-block`（96×96 单元，行/列标签 猫 / 追 / 老鼠），数值用 `heat-cell` 按大小着青（值 2 → 0.62 alpha，1 → 0.30，0 → 0.10）：`[2, 1, 1]`、`[0, 1, 1]`、`[1, 1, 1]`，下方形状说明 `3 × 3`。底部第二行的结果带：`÷ √dk = ÷ 2` 徽章 + 右上角替换后的第一行预览 `1  0.5  0.5`（暖黄）。时间点：0–3s 左区计算卡与右侧 3×3 网格骨架出现；3–9s 九个数按行填入（每行 0.35s，`heat-cell` 背景随数值淡入）；9–12s 形状说明出现；12–16s `÷ 2` 徽章 spring-pop，第一行三个数在原位翻成 `1 / 0.5 / 0.5` 并把整行 `heat-cell` 提亮一次；16s 后静止。同一帧内不再出现第三块内容。

## Frame 9 — 第三步 softmax 归一化

- status: animated
- src: compositions/frames/09-softmax.html
- duration: 27.0s
- poster: 9s
- transition_in: cut
- scene: 3×3 权重矩阵，每行和为 1；每行右侧一条权重条
- voiceover: "第三步，按行做 softmax。第一行取指数是二点七一八、一点六四九、一点六四九，和是六点零一六，归一化得到零点四五二、零点二七四、零点二七四。第二行是零点二三三、零点三八四、零点三八三。第三行三个分数相同，各三分之一。每一行的权重和都是 1。"
- rules: stat-bars-and-fills, counting-dynamic-scale

居中 `matrix-block`（96×96，行/列标签 猫 / 追 / 老鼠），数值为权重（`heat-cell`，青色 alpha 按行内占比）：`[0.452, 0.274, 0.274]`、`[0.233, 0.384, 0.383]`、`[0.333, 0.333, 0.333]`。每行右侧 300px 处一条 320px 宽的 `weight-bars`，用同一组数值（三色一致：猫青、追绿、老鼠紫的刻度点）并把 `Σ = 1.000` 以 28px `warm` 标在行尾。左侧一行 28px 辅助注：“第一行：e^1, e^0.5, e^0.5 = 2.718, 1.649, 1.649 → 和 6.016”。时间点：0–3s 网格骨架与行标签出现；3–8s 第一行填入（数字以 `counting-dynamic-scale` 从 0 数到位，≤0.8s），行尾出现 `Σ = 1.000` 与权重条；8–15s 第二行同法；15–22s 第三行同法；22–25s 左侧辅助注淡入（可放在网格下方一行，28px）；25s 后静止。

## Frame 10 — 第四步：对 V 加权求和

- status: animated
- src: compositions/frames/10-weighted.html
- duration: 25.6s
- poster: 9s
- transition_in: cut
- scene: 第一行的加权算式 → 3×4 输出矩阵
- voiceover: "第四步，用权重对 V 加权求和。第一行等于零点四五二个 v1 加零点二七四个 v2 加零点二七四个 v3，逐维算是一点零零、一点一八、零点八二、零点七三。三行都这样算，输出仍然是三行四列。这就是猫这个位置看过全句之后的新表示。"
- rules: stat-bars-and-fills, spring-pop-entrance

上方（y≈240）一行 48px 算式：`0.452·v₁ + 0.274·v₂ + 0.274·v₃ = [1.00, 1.18, 0.82, 0.73]`，权重用青、`v` 用紫、结果数字用 `warm`，并把 `v₁ v₂ v₃` 分别标注 28px 小字 猫/追/老鼠。下方居中输出 `matrix-block`（96×96，行标签 猫/追/老鼠，列标签 d1..d4）：`[1.00, 1.18, 0.82, 0.73]`、`[1.00, 0.85, 1.15, 0.62]`、`[1.00, 1.00, 1.00, 0.67]`，形状说明 `3 × 4`；旁注 28px：“输出的每一行 = 该位置的新表示（维度 dv = 4）”。时间点：0–3s 算式骨架出现；3–9s 三个权重与三个 v 逐个抵达（每个 0.5s）；9–14s 等号右侧四个结果数依次弹簧落位（`spring-pop-entrance`，值保持 `warm`）；14–22s 输出矩阵逐行填入（第一行数字与算式结果一致并短暂提亮）；22–24s 形状说明与旁注淡入；24s 后静止。

## Frame 11 — 多头注意力：投影 → 并行 → 拼接 → 再投影

- status: animated
- src: compositions/frames/11-multihead.html
- duration: 28.7s
- poster: 10s
- transition_in: crossfade
- scene: 四个站点的流水线：h 组投影 / 并行注意力 / 拼接 / W^O 投影
- voiceover: "单头注意力只能给出一套平均后的关注模式。多头注意力把 Q、K、V 分别用 h 组不同的可学习矩阵投影到更低维，各自独立跑一遍刚才那四步，然后把 h 个结果拼接，再用一个输出矩阵投影回 d_model。投影、并行注意力、拼接、再投影。每个头能在不同的表示子空间里建立不同关联，不必把所有关系压进一套权重。"
- blueprint: spatial-pan-stations

横向四个站点放在一条 1728px 宽的画布上（y≈470 基线），站点之间用 3px 青色箭头连接；镜头从站点 1 平移到站点 4（每站停 2s，`power2.inOut`，总位移不超过 900px，避免快速移动影响阅读）：站点 1 “① h 组投影”——三行 32px 公式 `Wᵢ^Q: d_model → dk`、`Wᵢ^K: d_model → dk`、`Wᵢ^V: d_model → dv`，配三个小 `role-tag`；站点 2 “② 并行注意力”——一个小 3×3 `heat-cell` 网格（各头各跑一遍 softmax(QKᵀ/√dk)V），上方 28px 注“h 个头同时算”；站点 3 “③ 拼接”——h 个色块并排成一个长条，28px 注 `Concat(head₁ … head_h)`；站点 4 “④ 再投影”——`W^O: h·dv → d_model` 与输出条，28px 注“回到 d_model”。时间点：0–2s 站点 1 与起始箭头出现；2–7s 镜头平移到站点 2（站点 1 保留在左侧，不淡出）；7–13s 到站点 3；13–19s 到站点 4；19–24s 底部一行 36px 结论淡入：“每个头关注不同位置、不同表示子空间；单头只能给出一套平均后的关注”；24s 后静止（镜头已停）。

## Frame 12 — 配置核对：h = 8，dk = dv = 64，8 × 64 = 512

- status: animated
- src: compositions/frames/12-config.html
- duration: 22.6s
- poster: 8s
- transition_in: crossfade
- scene: 512 被切成 8 份，每份 64；等式核对
- voiceover: "原论文用八个头，每个头的 dk 和 dv 都等于 d_model 除以 h，base 配置下就是五百一十二除以八等于六十四。核对一下：八乘六十四正好是五百一十二，所以头不是额外加出来的宽度，而是把 d_model 分成八份。每头维度降低，总计算成本和全维单头相近。"
- rules: counting-dynamic-scale, spring-pop-entrance

上半部：一条 1200×72 的长条代表 `d_model = 512`，被 8 条 4px 分隔线均分成 8 个色块（交替青/绿/紫系，alpha 0.35/0.55），每块内部 28px 标注 `64`。条左侧 48px 标签 `d_model = 512`，条右侧 28px 注 `h = 8`。下半部三行等式（48px，数字 `warm`，`tabular-nums`）：`dk = dv = d_model / h = 512 / 8 = 64`；`h × dk = 8 × 64 = 512 = d_model`（核对通过，行尾一枚 28px 青绿对勾徽章）；`每头维度 = d_model 的 1/8 → 总计算量与全维单头相近`（36px）。时间点：0–3s 长条与 `d_model = 512` 标签出现；3–8s 8 条分隔线依次落位、每块 64 计数出现（`counting-dynamic-scale`，≤0.8s）；8–13s 第一行等式逐段拼出；13–18s 第二行等式拼出并对勾徽章 spring-pop；18–21s 第三行说明上滑淡入；21s 后静止。

## Frame 13 — 回顾与自测提示

- status: animated
- src: compositions/frames/13-recap.html
- duration: 19.6s
- poster: 6s
- transition_in: crossfade
- scene: 四条回顾要点 + 自测提示
- voiceover: "回顾一下：自注意力让每个位置看全序列，Q、K、V 拆开三种角色，缩放让 softmax 留在梯度健康的区间，多头把一套关注变成多套。自测：合上稿子，把从 Q、K、V 到输出的四步写一遍。"
- blueprint: kinetic-type-beats
- rules: waterfall-entry

左侧一列四条要点（每条 36px，行高 1.4，序号 48px 用 `surface-2` 圆角方块）：① 自注意力：每个位置关注全序列（含自身）；② Q / K / V：把发问、被匹配、提供内容三种角色拆开；③ 除以 √dk：把点积方差拉回 1 量级，softmax 才有梯度；④ 多头：h 组投影并行，拼接后用 W^O 回到 d_model。右侧一块 `surface` 面板（620×360）：“自测 · 不看稿”标题 48px，正文 36px：“写出 Attention(Q, K, V) = softmax(QKᵀ/√dk)V 的四个步骤，并说出 h × dk = d_model 为什么成立。”面板用 `accent` 左侧 4px 边。底部 28px 灰色：“下一节：位置编码与前馈网络”。时间点：0–2s 左侧四条要点 waterfall（每条 0.45s，整体 stagger ≤0.5s）；2–6s 右侧面板淡入；6–12s 面板正文逐行出现（`opacity` 0→1，不逐字打）；12–16s 底部导航行淡入；16s 后静止，保持到帧尾。
