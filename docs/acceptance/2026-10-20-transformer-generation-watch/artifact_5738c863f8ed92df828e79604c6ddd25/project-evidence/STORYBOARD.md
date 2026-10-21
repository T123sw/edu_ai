---
format: 1920x1080
duration: 286s
message: "Transformer 拿掉循环，是为了消除串行瓶颈——代价是必须显式补上顺序信息与深层训练稳定性"
arc: Hook → 串行瓶颈 → 顺序步数对比 → 架构决策 → 三项效果 → 两笔账（位置编码 / 残差与归一化）→ 佐证与收束
audience: 希望系统学习 Transformer 的初学者
mode: autonomous
---

# STORYBOARD — 为什么需要 Transformer

Nine frames, caption-free, Chinese narration measured at 274.3s total. Durations below are the
measured voice length plus a short head/tail breath; they are the render windows and are not edited
downstream.

## Frame 1 — 开场：一个问题

- status: animated
- src: compositions/frames/frame01.html
- duration: 29.8s
- poster: 15s
- transition_in: cut
- scene: 标题落定，三个待答问题依次入位，右下方一条串行链作为预告亮起
- voiceover: 先问一个问题：为什么我们需要 Transformer？在这项工作之前，处理序列的主流做法是循环网络。它把一句话按位置切开，一个位置一个位置往前算。而论文第一段就点出了这种做法的代价：串行。接下来这几分钟，我们只讲清一件事：循环的代价到底是什么，Transformer 做了一次怎样的架构决策，以及拿掉循环之后，它必须补上哪两件事。
- blueprint: compose
- rules: waterfall-entry, spring-pop-entrance, ambient-glow-bloom
- focal: hero statement 为什么需要 Transformer
- roles: eyebrow / hero / subline / three question chips / serial chain preview

Scene 1 (0.0–2.2s): 全画幅深色底 + 48px 工程网格 + 右上角青色径向微光；eyebrow「01 · 循环的代价」在左上角淡入；顶部 hairline 从 88px 向右 scaleX 展开；ghost glyph「h」在右侧缓慢漂移。
Scene 2 (2.2–8.0s): hero statement「为什么需要 Transformer」以 waterfall-entry 逐词自下而上落定（88–104px，700）；其下一行 60px 的「循环网络的串行代价与一次架构决策」自左滑入（x -32 → 0）。
Scene 3 (8.0–16.0s): 三枚问题 chip 以 spring-pop-entrance 依次入场（间隔 0.18s，back.out(1.6)）：`01 循环的代价` / `02 架构决策` / `03 要补的两件事`，每枚左侧带 28px 序号，右侧留一条短 hairline。
Scene 4 (16.0–29.8s): 左下区域出现六个 84×84 位置小格排成一行，amber 箭头逐个点亮（每 0.35s 一格），作为全片的视觉母题预告；其余元素保持静止呼吸，hero 与三枚 chip 不移动。

## Frame 2 — 沿位置分解

- status: animated
- src: compositions/frames/frame02.html
- duration: 34.5s
- poster: 18s
- transition_in: crossfade 0.4s
- scene: 六个位置格就位，x 输入标签在下，隐藏状态 h 的依赖箭头逐条画出，右侧公式卡给出计算式
- voiceover: 先看循环网络的计算方式。给定一条长度为 n 的输入序列，模型是沿着符号位置来分解计算的。在位置 t，模型产生一个隐藏状态 h t，这个 h t 由上一时刻的隐藏状态和位置 t 的输入共同决定。请注意箭头方向：h t 要等前一个，一直退到序列开头。计算没有被分成 n 条并行的路，而是被串成了一条链。
- blueprint: compose
- rules: spring-pop-entrance, svg-path-draw, sine-wave-loop
- focal: 六个位置格与它们之间的 amber 依赖箭头
- roles: eyebrow 02 / scene title / position row / x input tags / h state arcs / formula card / chain bracket

Scene 1 (0.0–3.5s): eyebrow「02 · 沿位置分解」与 hairline 入场；场景标题「沿着符号位置，一步一步算」在左上 60px 就位；ghost glyph「h_t」在右下 6% 透明度漂移。
Scene 2 (3.5–14.0s): 六个 96×96 位置格以 spring-pop-entrance 从左到右依次弹出（stagger 0.12s，合计 < 0.5s 成型）；每格下方 28px 标签 x₁…x₆；右侧 520px 宽的公式卡（panel）滑入，显示 `h_t = f(h_{t−1}, x_t)` 44px，卡内两行小注 30px「上一时刻的隐藏状态」「位置 t 的输入」。
Scene 3 (14.0–24.0s): 六条 amber 弧线箭头以 svg-path-draw 依次画出（每条 0.45s，strokeDashoffset → 0），箭头落在下一格时该格边框转为 amber 并带柔光；格上方出现 h₁…h₆ 的 28px 下标标签。
Scene 4 (24.0–34.5s): 一行 34px 括号注记「一条链：h_t 依赖 h_{t−1}」在格下方 scaleX 展开；左下 30px note「不是 n 条并行路径」淡入；箭头按 2s 周期做一次轻微的 amber 呼吸（有限次 repeat），公式卡保持。

## Frame 3 — 必须等前一步

- status: animated
- src: compositions/frames/frame03.html
- duration: 24.0s
- poster: 13s
- transition_in: crossfade 0.4s
- scene: 时间轴上播放头逐格推进，每格必须等前一格完成，右上角步数计数器同步走到 6 / 6
- voiceover: 把这条链摆到时间轴上，结论就很直观。位置一算完，位置二才开始；位置二算完，位置三才开始。每一步占用一格时间，谁也没法抢跑。论文把这个性质叫做固有串行性。它不是工程实现得不够好，而是计算图的形状本身决定的。序列有多长，这条链就有多长。
- blueprint: compose
- rules: spring-pop-entrance, svg-path-draw, counting-dynamic-scale
- focal: 时间轴上的播放头与逐格点亮的单元
- roles: eyebrow 03 / scene title / time axis / six step cells / playhead / step counter / chain bracket

Scene 1 (0.0–2.5s): eyebrow「03 · 固有串行性」与 hairline 入场；标题「一步一格，谁也不能抢跑」60px 自左滑入；右上角出现 28px 标签「顺序步数」，其下是即将计数的 `1 / 6`。
Scene 2 (2.5–9.0s): 时间轴基线与六个 108×108 单元自左向右弹出（stagger 0.1s），每个单元下 28px 刻度 t₁…t₆；播放头（3px cyan 竖线 + 顶端小三角）停在轴的最左端。
Scene 3 (9.0–18.0s): 播放头分六段推进（每段 1.4s，power2.inOut）：进入第 k 格时该格转 amber、箭头向 k+1 格画出、计数器从 1/6 走到 6/6（counting-dynamic-scale，tabular-nums）；未到达的格保持 low ink。
Scene 4 (18.0–24.0s): 六个格全部 amber，轴下出现跨全宽的括号与 30px 注记「链长 = 序列长度」；右侧 32px note「固有串行性：由计算图形状决定」淡入，播放头停在末端。

## Frame 4 — 顺序步数

- status: animated
- src: compositions/frames/frame04.html
- duration: 36.0s
- poster: 20s
- transition_in: crossfade 0.4s
- scene: 左右分屏：左侧琥珀色六级阶梯与 O(n) 计数，右侧青色一次展开的全连接扇形与 O(1) 计数
- voiceover: 串行本身还不是最要命的地方，要命的是它出现的位置。训练时我们最希望并行的地方，恰恰是同一个样本内部的不同位置。循环网络做不到：一个样本里的 n 个位置只能排队算。序列一长，显存又限制跨样本的批大小，这条链的长度没法用别的方式补回来。于是顺序步数停在 O(n)。如果所有位置能在同一时刻一次算完，顺序步数就是 O(1)：序列再长，等待的轮次也不再增加。
- blueprint: comparison-split
- rules: split-tilt-cards, counting-dynamic-scale, stat-bars-and-fills
- focal: 两侧的顺序步数对比 O(n) 与 O(1)
- roles: eyebrow 04 / scene title / left serial panel + staircase / left O(n) counter / right parallel panel + fan / right O(1) counter / closing note

Scene 1 (0.0–3.0s): eyebrow「04 · 代价落在训练上」；标题「样本内部，无法并行」60px 就位；左右两块 panel 以 split-tilt-cards 的镜像书页倾斜入场（rotateY ±8° → 0，从两侧滑入）。
Scene 2 (3.0–12.0s): 左 panel「串行」：六级 amber 阶梯（stat-bars-and-fills 的 scaleY 阶梯变体）逐级升起，标题下 30px 注「同一个样本里的 n 个位置」；右 panel「一次算完」：一个中心格向另外五格同时拉出五条 cyan 直连线（0.5s 内同时完成）。
Scene 3 (12.0–24.0s): 两个大号计数（counting-dynamic-scale，120px tabular-nums）从左到右数字滚动：左侧 `O(n)` 下方的 n 从 2 增到 64、步数同步增加；右侧 `O(1)` 始终保持 1，计数每跳一次右侧轻弹一下（back.out(1.4) 0.25s）。
Scene 4 (24.0–36.0s): 左侧整体降到 55% 不透明度并轻微后移（scale 0.98），右侧升到 100% 并出现青色柔光；帧底 30px 注记「序列再长，等待的轮次不再增加」淡入；两侧标签保持可读。

## Frame 5 — 架构决策

- status: animated
- src: compositions/frames/frame05.html
- duration: 26.2s
- poster: 14s
- transition_in: crossfade 0.4s
- scene: 循环与卷积被划掉，注意力与逐位置前馈两枚青色 chip 升到中央并组成整个模型
- voiceover: Transformer 的回应，是一次非常干脆的架构决策：不用循环，也不用卷积。整个模型只用两种部件搭起来——注意力和逐位置的前馈网络。这句话听起来像口号，但它是可以逐条兑现的。论文的说法是，完全依靠注意力来建立输入与输出之间的全局依赖。接下来我们看，这个决定换来了什么。
- blueprint: compose
- rules: waterfall-entry, spring-pop-entrance, ambient-glow-bloom
- focal: 「不用循环，也不用卷积」这句决策与其下的两枚部件 chip
- roles: eyebrow 05 / decision headline / two struck-out chips / two surviving chips / brace + note

Scene 1 (0.0–2.5s): eyebrow「05 · 架构决策」；决策 headline「不用循环，也不用卷积」以 waterfall-entry 自下而上落定（96px，700，两行）。
Scene 2 (2.5–8.0s): 两枚灰色 chip「循环」「卷积」自左右 spring-pop 入场；随后各有一条 amber 横线以 scaleX 0 → 1（0.35s，power3.inOut）从左到右划掉它们，chip 文字降到 45%。
Scene 3 (8.0–18.0s): 中央青光辉光 bloom 展开；两枚青色 chip「注意力」「逐位置前馈网络」从下方升起（y 40 → 0，back.out(1.6)），字号 40px，边框 2px accent；两枚 chip 下方出现一个细括号与 30px 注记「整个模型 = 这两个部件」。
Scene 4 (18.0–26.2s): 右侧出现 32px 引文式 note「完全依靠注意力，建立输入与输出之间的全局依赖」；被划掉的两枚 chip 仅作为背景残留（35% 不透明度）；中央两枚 chip 保持轻微呼吸。

## Frame 6 — 三项效果

- status: animated
- src: compositions/frames/frame06.html
- duration: 35.0s
- poster: 20s
- transition_in: crossfade 0.4s
- scene: 三块编号结果卡依次组装：消除串行瓶颈、建立直接连接、统一计算模式，各配一张微型示意图
- voiceover: 第一项，消除串行瓶颈。编码器里所有位置的计算可以一次完成，训练时的解码器也是如此，顺序步数从 O(n) 降到 O(1)。第二项，建立直接连接。自注意力让每个位置直接读取序列中任意一个位置，路径长度是 O(1)。第三项，统一计算模式。整个模型由同构的层堆叠而成，每一层只有注意力子层和前馈子层两种部件。结构简单，也就更容易堆深。
- blueprint: grid-card-assemble
- rules: spring-pop-entrance, stat-bars-and-fills, sine-wave-loop
- focal: 三块结果卡与它们的微型示意图
- roles: eyebrow 06 / scene title / tile 1 / tile 2 / tile 3 / three micro diagrams

Scene 1 (0.0–3.0s): eyebrow「06 · 换来了什么」与标题「三项效果」60px 就位；右上方 ghost glyph「3」淡入。
Scene 2 (3.0–14.0s): 第一块卡以 grid-card-assemble 的级联入场（自下方 40px + spring-pop）：编号 01、标题「消除串行瓶颈」38px、下方微型图——六个小格同时转 cyan（一次点亮，0.4s 内完成）；卡右下 44px 公式 `O(n) → O(1)`。
Scene 3 (14.0–24.0s): 第二块卡入场：标题「建立直接连接」；微型图——中心格向其余五格同时画出五条 cyan 直连线（svgPathDraw 一次性完成）；卡右下 32px 注「路径长度 O(1)」。
Scene 4 (24.0–35.0s): 第三块卡入场：标题「统一计算模式」；微型图——三条堆叠带（宽 260px、高 44px）重复两层，每条带内 28px 标签「注意力」「前馈」；卡右下 32px 注「同构层堆叠」。三块卡同时存在时保持一次极轻的整体呼吸。

## Frame 7 — 补上顺序信息

- status: animated
- src: compositions/frames/frame07.html
- duration: 29.4s
- poster: 16s
- transition_in: crossfade 0.4s
- scene: 两种词序坍缩成同一个堆，等号出现；随后位置编号重新贴上，两种词序重新分开
- voiceover: 但拿掉循环，是有账单的。第一笔：顺序信息没有了。循环网络把顺序编码在时间步里，注意力却没有这个概念，它看到的更像一个集合。如果只把词同时丢进去，让每个位置直接读所有位置，那么猫追狗和狗追猫，在模型眼里没有区别。所以必须显式地注入位置信息，这就是位置编码：给每个位置一个可区分的信号，让顺序重新变得可知。
- blueprint: compose
- rules: spring-pop-entrance, waterfall-entry, nudge-curve
- focal: 两个词序坍缩成的同一堆，以及随后重新分离
- roles: eyebrow 07 / scene title / ordering A cells / ordering B cells / collapsed bag / equals mark / position tags / closing label

Scene 1 (0.0–3.0s): eyebrow「07 · 第一笔账」；标题「顺序信息，没有了」64px 就位；左上 ghost glyph「?」低调漂移。
Scene 2 (3.0–12.0s): 上方一行三个词格「猫」「追」「狗」spring-pop 入场，格下 28px 位置标签 1 / 2 / 3；随后三格脱离原位、以 nudge-curve 一起滑向中央并收拢成一个「集合」面板（三格紧贴、位置标签消失），标签「一个集合」30px 出现。
Scene 3 (12.0–20.0s): 第二行三个词格「狗」「追」「猫」出现并做同样坍缩，落在同一个集合面板下方；一个 72px 的等号在两者之间弹出（back.out(2)，0.4s）；右侧 32px note「注意力看不到先后」。
Scene 4 (20.0–29.4s): 两行词格重新展开（反向 nudge-curve），每格右上角贴上一枚 26px 的青色位置码 `+1 / +2 / +3`；两行不再重叠，分别在面板上下保持不同排布；底部 40px cyan 标签「位置编码：让顺序重新可知」scaleX 展开。

## Frame 8 — 撑住深层堆叠

- status: animated
- src: compositions/frames/frame08.html
- duration: 36.0s
- poster: 20s
- transition_in: crossfade 0.4s
- scene: 左侧层堆叠升起，右侧信号线在无残差时逐层衰减；随后残差旁路弧线画出、归一化刻度加入，信号线重新变稳
- voiceover: 第二笔：深层堆叠的训练稳定性。循环网络靠时间步反复复用同一组参数，它的深度是有限的。Transformer 选择把同样的层堆很多次，深度一下子变成了显式设计出来的量。层一深，梯度就容易在传递中衰减，训练难以收敛。残差连接把子层的输入直接加到输出上，给梯度留了一条直通的路；归一化则把每一层的数值尺度稳住。这两件事加在一起，深堆叠才真的训得起来。
- blueprint: compose
- rules: svg-path-draw, spring-pop-entrance, sine-wave-loop
- focal: 残差旁路弧线与右侧信号线
- roles: eyebrow 08 / scene title / layer stack / decaying signal line / residual arcs / norm ticks / closing note

Scene 1 (0.0–3.0s): eyebrow「08 · 第二笔账」；标题「深层堆叠，要撑住」64px 就位。
Scene 2 (3.0–13.0s): 左侧六条层带（高 62px，间隔 18px）自下而上依次升起（stagger 0.1s），每条带内 28px 标签「注意力 + 前馈」；右侧一条 amber 信号线穿过六层，振幅逐层变小（每层 0.8×），末端标 30px note「逐层衰减」。
Scene 3 (13.0–24.0s): 两条 cyan 残差弧线以 svg-path-draw 从最底层右侧绕过每一层画到输出（每条 0.6s）；信号线重画为稳定振幅，末端注释改为「直通的路」；右侧 32px 标签「残差连接」。
Scene 4 (24.0–36.0s): 每层右侧出现一枚 40×8px 的青色归一化刻度条（stat-bars 的 fill 变体，scaleX 0 → 1 依次完成）；信号线末端加一枚小的稳定脉冲点（sine-wave-loop 有限次）；底部 30px 注记「残差 + 归一化 → 深堆叠训得起来」。

## Frame 9 — 佐证与收束

- status: animated
- src: compositions/frames/frame09.html
- duration: 35.4s
- poster: 20s
- transition_in: crossfade 0.4s
- scene: 8 块 P100 与 12 小时两个数字计数到位，随后三行要点收回全片结论，来源标注留在右下
- voiceover: 这些决定换来了什么？论文给了一个很简洁的数据点：这个模型在八块 P100 GPU 上训练十二个小时，就达到了当时新的翻译质量最优。十二小时在今天不算什么，但它说明了关键的一点：这个架构可以显著并行化，训练时间不再被序列长度线性锁住。所以，为什么需要 Transformer？因为它用一次明确的架构决策，把串行瓶颈换成了一笔必须付清的账：显式的位置信息，加上撑住深度的残差与归一化。
- blueprint: dataviz-countup
- rules: counting-dynamic-scale, stat-bars-and-fills, ambient-glow-bloom
- focal: 8 × P100 与 12 小时两个数字，以及最后的结论句
- roles: eyebrow 09 / scene title / two hero stats / proof note / three takeaway lines / source tag

Scene 1 (0.0–3.0s): eyebrow「09 · 佐证」；标题「显著并行化」64px 就位；右下角来自论文的 ghost glyph「12h」淡入。
Scene 2 (3.0–12.0s): 两个大号统计以 counting-dynamic-scale 计数到位：`8` 配 30px 标签「块 P100 GPU」，`12` 配标签「小时」；两者之间一枚 64px 的 `×` 与一条 2px 分隔线；数字合计 0.9s 内完成滚动（power2.out）。
Scene 3 (12.0–24.0s): 右侧 32px note「当时新的翻译质量最优」淡入；随后三行 34px 要点以 stat-bars-and-fills 的微条 + 文本形式自左依次入场：「拿掉循环」「显式注入位置信息」「残差与归一化撑住深度」。
Scene 4 (24.0–35.4s): 两个统计与要点轻微后退（scale 0.97，降低对比），中央 72px 结论句「一次明确的架构决策」以 waterfall-entry 落定并保持到最后一帧；右下角 28px 来源标注「Vaswani et al., Attention Is All You Need, NIPS 2017」淡入并长留。
