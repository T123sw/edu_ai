---
format: 1920x1080
duration: 295s
message: "自注意力看不见顺序，所以要把位置编码加到嵌入上；每个位置再各自过同一个前馈网络，补回非线性"
arc: 承上（自注意力） → 缺口（置换等变） → 注入（同维相加） → 公式（正弦/余弦） → 图像（热力图与波长） → 理由（相对位置/外推） → 对比（可学习嵌入） → 前馈网络（逐位置） → 维度与小结
audience: 希望系统学习 Transformer 的初学者（具体背景未知）
mode: autonomous
---

# STORYBOARD — 位置编码与逐位置前馈网络

总时长 295.5s（9 帧，按实测旁白时长 + 1.2s 呼吸余量）。所有时长单位为秒。

## Frame 1 — 承上启下：看不见顺序

- status: animated
- src: compositions/frames/01-opening.html
- duration: 19.25s
- transition_in: cut
- poster: 9
- scene: 承接自注意力，点出它看不见顺序，抛出本节两块拼图（位置编码 / 逐位置前馈网络）
- voiceover: 上一节我们讲完了自注意力：每个位置都能看到整条序列，靠的是 Query 和 Key 的相似度。但它有一个缺口，一个很隐蔽的缺口——它看不见顺序。这一节我们补上两块拼图：位置编码，和逐位置前馈网络。
- blueprint: compose
- focal: 主判断句「它看不见顺序」与两枚拼图 chip
- roles: 页眉=章节序号 01/09 + 右侧主题标签；hero=判断句（两拍换字）；辅助=两枚 chip 各带一行 label；背景=细网格 + 青色辉光 + 幽灵字 PE
- rules: kinetic-beat-slam, spring-pop-entrance, ambient-glow-bloom

- Scene 1 (0.0–3.2s): 页眉入场——左「01 / 09」（label, ink-mute），右「POSITION & POSITION-WISE FFN」（label, accent），下方 2px line-soft 横线 scaleX 0→1。hero「自注意力」132px ink 字以 scale-slam 落位，subhead「每个位置看见整条序列」随后淡入；这一段结束时整体压暗到 0.28 仍可见。
- Scene 2 (3.2–7.6s): 换拍——第二拍 hero「但它看不见」上移就位，「顺序」以 132px pos 琥珀色砸入其下；一条 pos 轴自左向右点亮 5 段刻度，每格 label「pos 0」…「pos 4」，轴上 5 枚小 chip 依次就位。
- Scene 3 (7.6–12.8s): 两枚大 chip 依次弹入，各带一行 label：左「位置编码」+「补回顺序」（pos 描边），右「逐位置前馈网络」+「补回逐位置非线性」（ffn 描边）；两 chip 之间一条 2px 竖分隔线 scaleY 0→1。
- Scene 4 (12.8–18.5s): 环境动效保持场子——网格缓慢漂移、右侧辉光呼吸、幽灵字「PE」缓慢右移；两 chip 轻微错峰呼吸（±2px），最后一拍停住。

这一帧只做承接与预告，不出现公式，避免与后面抢焦点。

## Frame 2 — 置换等变：输出只是重排

- status: animated
- src: compositions/frames/02-permutation.html
- duration: 35.66s
- transition_in: crossfade
- poster: 16
- scene: 打乱词序只做自注意力，输出只是跟着重排，模型分不清「猫追狗」与「狗追猫」
- voiceover: 先把缺口摆出来。自注意力对输入位置的置换是等变的：同一个句子，把词序打乱，只做自注意力，输出也只是跟着重排，内容一点没变。猫追狗和狗追猫，用的是同一批词向量，注意力给每一对词打的分也完全对称，模型没有任何线索判断谁在前、谁在后。它知道有哪些词，却不知道这些词怎么排。既然 Transformer 既没有循环，也没有卷积，顺序信息就只能显式地注入进去，这就是位置编码要解决的问题。
- blueprint: compose
- focal: 两张 3×3 注意力矩阵（原序 / 置换后）与「模型无法区分」的判断
- roles: 标题；上方 3 枚 token chip 与 pos 轴；中部注意力矩阵；下方输出两联；结语条与公式脚注
- rules: waterfall-entry, discrete-text-sequence, scale-swap-transition

- Scene 1 (0.0–5.5s): 标题「自注意力：对位置的置换等变」76px 落位，副标题「同一批词，换一个顺序」；一行三枚 chip「猫」「追」「狗」以 waterfall 依次落下，左侧 pos 轴标 0 / 1 / 2。
- Scene 2 (5.5–13.0s): 中部 3×3 注意力矩阵出现（行列标签 猫/追/狗，格 44px），九格数值自左上向右下 stagger 点亮，矩阵关于对角线对称；矩阵下方 label「打分只看两个词是谁，不看它们在哪儿」。
- Scene 3 (13.0–23.0s): 上方 chip 首尾交换成「狗」「追」「猫」（discrete 状态切换），pos 轴标签不变；同一张矩阵整体做行列置换（格子换位），数值一字未改；右侧浮出 label「同一批数值，只是换了位置」。
- Scene 4 (23.0–30.0s): 下方输出两联并排：「输入 A → 输出 A′」「输入 B → 输出 B′」，B′ 逐格对齐到 A′ 的重排位置；中央浮出判断句「模型无法区分」76px，pos 色。
- Scene 5 (30.0–35.0s): 结语条：两枚 badge「无循环」「无卷积」→ 箭头 → 「顺序信息必须显式注入」，accent 下划线自左划出；右下角 meta 一行「Attention(Q,K,V)=softmax(QKᵀ/√dk)V —— 与顺序无关」。

## Frame 3 — 注入方式：同维相加

- status: animated
- src: compositions/frames/03-injection.html
- duration: 32.45s
- transition_in: push-slide LEFT
- poster: 13
- scene: 把位置编码加到编码器/解码器栈底的输入嵌入上；同为 d_model=512，逐元素相加而不是拼接
- voiceover: 注入的方式很直接：把位置编码加到编码器和解码器栈底部的输入嵌入上，注意是相加，不是拼接。位置编码和词嵌入都是 d_model 维，原论文里 d_model 等于 512，两个 512 维向量逐元素相加，维度保持不变，所以上面的每一层都不需要改动，注意力照常工作。换句话说，位置编码给每个词向量做了一次平移，把它挪到属于这个词位置的那片区域。
- blueprint: compose
- focal: 三条 512 维竖条与四行「e_i + PE_i = r_i」的逐元素相加
- roles: 标题；三条数值列；中间加号；四行算式；右侧「拼接=1024」被划掉的对比；底部一行落点说明
- rules: center-outward-expansion, spring-pop-entrance, svg-path-draw

- Scene 1 (0.0–6.0s): 标题「注入方式：加到嵌入上」；三条竖条骨架从画面中心散开就位，自上而下标签「词嵌入」「位置编码」「相加结果」，每条下方 label「512 维」。
- Scene 2 (6.0–14.0s): 左条填成四格 e0…e3（accent 描边），中条填成四格 PE(0,·)…（pos 琥珀描边），中间「+」以 spring-pop 落位；上方 label「d_model = 512：同维才能相加」。
- Scene 3 (14.0–24.0s): 四行算式自下而上逐行出现「e0 + PE0 = r0」…「e3 + PE3 = r3」（tabular 数字），结果条对应格依次点亮；一条 SVG 箭头自两条指向结果条并自绘，收在 label「逐元素相加 → 维度不变」。
- Scene 4 (24.0–31.5s): 右侧对比：一条浅色「拼接 → 1024 维」条被 pos 色斜线划掉；label「不是拼接：维度会变，上面每一层都要跟着改」；底部一行 ink-dim「加在编码器与解码器栈底部的输入嵌入上」。

## Frame 4 — 正弦公式逐项拆解

- status: animated
- src: compositions/frames/04-formula.html
- duration: 36.46s
- transition_in: crossfade
- poster: 15
- scene: PE(pos,2i)=sin(pos/10000^(2i/d_model)) 与 cos 版本，逐项标注 pos / i / 频率项
- voiceover: 位置编码取什么函数？作者没有让它去学，而是直接写了一组不同频率的正弦和余弦。偶数维取 sin，括号里是 pos 除以 10000 的 d_model 分之 2i 次方；奇数维取 cos，括号里完全一样，只是把函数换成余弦。pos 是位置序号，从零开始数；i 是维度编号。也就是说，每一个维度对应一条固定频率的正弦曲线，维度编号越大，分母越大，频率越低，波长越长。
- blueprint: compose
- focal: 两行公式卡与三个符号注释卡
- roles: 标题；sin 公式行；cos 公式行；三张注释卡与 SVG 引线；底部结语与 mini 波形
- rules: discrete-text-sequence, waterfall-entry, ambient-glow-bloom

- Scene 1 (0.0–7.0s): 标题「正弦位置编码」；第一行公式卡弹出：PE(pos, 2i) = sin( pos / 10000^(2i/d_model) )，54px；「PE」与「sin」依次染成 pos 琥珀，其余 ink。
- Scene 2 (7.0–16.0s): 第二行卡出现：PE(pos, 2i+1) = cos( 同一个括号 )，与上一行左对齐同宽；仅 sin→cos、2i→2i+1 两处做离散替换闪亮，括号部分高亮示意「完全一样」。
- Scene 3 (16.0–27.0s): 三张注释卡自下而上浮现，各用一条 SVG 引线指到公式对应片段（引线 strokeDashoffset 自绘）：① pos = 位置序号，从 0 开始 ② i = 维度编号 ③ 10000^(2i/d_model) = 频率项，分母越大频率越低。
- Scene 4 (27.0–35.8s): 结语「每个维度 = 一条固定频率的正弦曲线」；下方一条 mini 波形自左绘出，右侧三条小波形示意「快 / 中 / 慢」，收在 label「维度越大 → 波长越长」。

## Frame 5 — 热力图与波长几何级数

- status: animated
- src: compositions/frames/05-heatmap.html
- duration: 38.69s
- transition_in: blur-crossfade
- poster: 16
- scene: 位置 × 维度的 PE 热力图，波长从 2π 到 10000·2π 的几何级数
- voiceover: 把所有位置、所有维度排成一张表，就是一张热力图：横向是位置，纵向是维度。底部几行是高频快振荡，相邻位置的颜色差别很大；顶部几行是低频慢变化，相邻位置几乎看不出区别。波长正好构成一个几何级数，从 2π 一直到 10000 乘以 2π。所以位置每往前走一格，都会在每一维上留下一个有规律的、可区分的模式：低频维管粗粒度，高频维管细粒度，合起来就是一个位置的指纹。
- blueprint: compose
- focal: 12×16 热力图与右侧三条不同波长的正弦曲线
- roles: 标题；矩阵与两条轴标；右侧三条波形；两条参考行引线；底部几何级数标尺；低频/高频 badge
- rules: stat-bars-and-fills, svg-path-draw, sine-wave-loop

- Scene 1 (0.0–6.5s): 标题「位置 × 维度」；矩阵外框与两条轴出现：横轴 pos 0→15（label, ink-mute），纵轴 d_model 0→11（label, ink-mute），轴名在轴末端。
- Scene 2 (6.5–16.0s): 网格自上而下逐行填色——顶部低频行（琥珀系、缓慢变化）先落，底部高频行（accent 系、跳变）后落，整组 stagger ≤ 0.5s；右侧三条正弦曲线按「长 / 中 / 短」波长依次自绘。
- Scene 3 (16.0–26.0s): 两条参考行高亮（顶部 + 底部），各自拉出引线到右侧放大波形；label「低频：相邻位置差异小」「高频：相邻位置差异大」；放大波形做有限次缓慢呼吸。
- Scene 4 (26.0–37.8s): 底部标尺出现：2π —— 20×2π —— 500×2π —— 10000×2π，刻度逐个点亮、间距按几何级数不均；标尺上方一句「位置每前进一格，每一维都留下可区分的模式」；两枚 badge「低频＝粗粒度」「高频＝细粒度」落在标尺两端。

## Frame 6 — 两个设计理由

- status: animated
- src: compositions/frames/06-reasons.html
- duration: 33.26s
- transition_in: zoom-through
- poster: 14
- scene: 两个设计理由：PE(pos+k) 可写成 PE(pos) 的线性函数；公式可外推到更长的序列
- voiceover: 为什么偏偏选正弦函数？两个理由。第一，它让模型容易学按相对位置关注：对任意固定偏移 k，把正弦的和角公式展开，PE(pos 加 k) 就能写成 PE(pos) 的一个线性函数，而且这个变换只和 k 有关，与 pos 本身无关。模型只要学一个线性映射，就能表达往前看 k 个词。第二，这个公式对任意位置都有定义，所以可能外推到训练时没见过的更长序列。
- blueprint: comparison-split (Adapt)
- focal: 左右两张理由卡（和角公式 / 训练长度与外推）
- roles: 标题；左卡公式；右卡 pos 轴；底部结论 badge
- rules: split-tilt-cards, spring-pop-entrance, svg-path-draw

- Scene 1 (0.0–6.0s): 标题「为什么用正弦函数」；两张大卡（高 520px）从左右以镜像 rotateY tilt 进入并落位：左「① 相对位置可学」，右「② 长度可外推」。
- Scene 2 (6.0–18.0s): 左卡展开和角公式 sin(ω(pos+k)) = sin(ωpos)·cos(ωk) + cos(ωpos)·sin(ωk)，逐项高亮（pos 用琥珀、k 用 accent）；下方 label「PE(pos+k) 是 PE(pos) 的线性函数，变换只取决于 k」。
- Scene 3 (18.0–27.0s): 右卡展开 pos 轴：0…L 实线段标「训练长度」，L 之后虚线延伸到 2L 标「未见过长度仍可计算」；虚线自绘，末端 pos 色圆点 pop 落位。
- Scene 4 (27.0–32.6s): 两卡之间落下一枚 badge「相对位置可学 · 长度可外推」，两卡轻微上浮后停住。

## Frame 7 — 与可学习位置嵌入的对比

- status: animated
- src: compositions/frames/07-learned.html
- duration: 20.93s
- transition_in: crossfade
- poster: 10
- scene: 可学习位置嵌入的结果几乎相同；选正弦版本只为外推性
- voiceover: 作者也试过可学习的位置嵌入：给每个位置配一个可训练向量。两种方案的结果几乎一模一样。最终选正弦版本，理由只有外推性：可学习的表只能在训练长度以内查，遇到更长的序列就没有位置可用；公式却可以一直算下去。
- blueprint: compose
- focal: 两张方案卡与「几乎相同」的判定
- roles: 标题；左卡可学习表；右卡正弦公式；中间等号与判定；底部结论
- rules: scale-swap-transition, stat-bars-and-fills, ambient-glow-bloom

- Scene 1 (0.0–5.0s): 标题「另一种做法：可学习的位置嵌入」；左卡「位置 → 向量」表格骨架（L 行 × d_model 列）浮现，右卡「PE 公式」浮现，两卡同高同宽。
- Scene 2 (5.0–12.0s): 两卡之间出现等号与判定「BLEU 几乎相同」（tabular），一条对比条自中间向两侧展开（scaleX）；两卡被同等点亮；label「论文：两种版本结果几乎一致」。
- Scene 3 (12.0–20.2s): 右卡放大前移、左卡退后变暗：左卡 pos 轴超出 L 后标「无定义」并打叉，右卡曲线继续延伸；底部结论「选正弦：只为外推性」。

## Frame 8 — 逐位置前馈网络

- status: animated
- src: compositions/frames/08-ffn.html
- duration: 46.46s
- transition_in: zoom-through
- poster: 18
- scene: FFN(x)=max(0,xW1+b1)W2+b2 对每个位置分别且相同地施加；位置共享参数、层间不共享；等价于两个 1×1 卷积
- voiceover: 顺序问题解决了，还差一块：逐位置前馈网络。编码器和解码器的每一层，除了注意力子层，还有一个全连接前馈网络，它对每个位置分别且相同地施加。它由两个线性变换夹一个 ReLU 组成：先把向量乘 W1 加 b1，升到更高的维度，再取 max(0, 那一步的结果)，把负数截成零，最后乘 W2 加 b2 回到原维度。不同位置共享同一组权重，但不同层用的是不同参数。ReLU 提供的就是逐位置的非线性：如果没有它，两个线性变换叠起来仍然只是一个线性变换。换个说法，这就等价于两个核大小为 1 的卷积。
- blueprint: compose
- focal: 公式卡与「同一组权重扫过五个位置列」
- roles: 左侧一层子层结构；公式卡；五列位置向量与共享徽标；位置共享/层间不共享两卡；1×1 卷积示意
- rules: center-outward-expansion, spring-pop-entrance, discrete-text-sequence

- Scene 1 (0.0–6.5s): 标题「逐位置前馈网络」；左侧一层结构竖排出现：Multi-Head Attention → Add & Norm → Feed Forward → Add & Norm，其中 Feed Forward 块用 ffn 紫罗兰高亮描边，其余 line 描边。
- Scene 2 (6.5–17.0s): 右侧公式卡弹出：FFN(x) = max(0, xW1 + b1) W2 + b2；分三段依次高亮——线性1（W1、b1）、ReLU（max(0, ·)）、线性2（W2、b2）；下方 label「ReLU 把负数截成零：逐位置的非线性」。
- Scene 3 (17.0–29.0s): 主图：一行五个位置列（pos 0…4），每列一根向量条；同一枚「W1 / W2」徽标自左向右依次扫过五列，扫到哪列哪列亮起并浮出小字「同样权重」；收在 label「分别且相同地施加」。
- Scene 4 (29.0–39.0s): 公式卡下方落两张小卡：「位置之间：共享 W1 / W2」与「层与层：参数不同」；右侧三层小卡 L1/L2/L3 各带不同色标，逐层点亮。
- Scene 5 (39.0–45.8s): 等价说法：一条序列条上，一个 1×1 kernel 小方格自左向右滑动，每停一格输出一格高亮；label「等价于两个核大小为 1 的卷积」。

## Frame 9 — 512 → 2048 → 512

- status: animated
- src: compositions/frames/09-dimensions.html
- duration: 32.38s
- transition_in: blur-crossfade
- poster: 14
- scene: 维度变化 512 → 2048 → 512，以及全节小结
- voiceover: 看维度变化就清楚了：输入是 512 维，W1 把它升到内层的 2048 维，ReLU 之后再由 W2 压回 512 维。每一层都重复这一套。注意力负责在位置之间交换信息，前馈网络负责在每个位置内部做非线性变换；两者合起来，才是一层完整的 Transformer。位置编码补回顺序，前馈网络补回逐位置的非线性——开头那两块拼图，到这里就都装上了。
- blueprint: compose
- focal: 三条维度条（512 / 2048 / 512）与两行小结
- roles: 标题；三条 dimension-bar 与 W1/W2 注；两枚 badge；两行小结；页眉 09/09
- rules: stat-bars-and-fills, counting-dynamic-scale, waterfall-entry

- Scene 1 (0.0–6.0s): 标题「512 → 2048 → 512」；三条 dimension-bar 骨架水平出现，左端 label「输入」「内层」「输出」。
- Scene 2 (6.0–14.0s): 三条依次长成：512（accent）、2048（ffn 紫，最长）、512（accent）；数字自 0 计数到目标值（tabular）；中间条上方标「d_ff = 2048」。
- Scene 3 (14.0–22.0s): 箭头注：W1 512×2048（升维）、W2 2048×512（降维），两枚 badge 落在对应箭头旁；底部 meta「每一层都重复这一套」。
- Scene 4 (22.0–31.6s): 小结两行自下而上落位：「位置编码：补回顺序」（pos 色）「前馈网络：补回逐位置非线性」（ffn 色）；页眉序号变为「09 / 09」，背景辉光收拢、网格缓慢停下。
