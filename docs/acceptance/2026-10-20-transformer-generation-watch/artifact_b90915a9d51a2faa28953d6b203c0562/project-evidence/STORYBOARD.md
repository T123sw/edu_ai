---
format: 1920x1080
duration: 296s
message: "Transformer 用编码器-解码器加堆叠子层把输入序列变成输出序列：编码器产出连续表示 z，解码器基于 z 自回归逐符号生成"
arc: 结构承诺 → 一次前向总览 → 编码器 → 解码器 → 三种注意力 → 残差与归一化 → 掩码 → 右移一位 → 全链路清单 → 收束
audience: 希望系统学习 Transformer 的初学者
mode: autonomous
---

## Frame 1 — 开场：拆开结构图

- status: outline
- src: compositions/frames/01-opening.html
- duration: 23.54s
- transition_in: cut
- poster: 17s
- blueprint: compose
- rules: waterfall-entry, ambient-glow-bloom, svg-path-draw
- focal: 标题与右侧最小结构骨架
- scene: 标题逐行落下，左右两栈与中间 z 通道的骨架慢慢点亮
- voiceover: 上一节我们看到，循环网络只能一个符号接一个符号地算，训练时一个样本内部没法并行。这一节我们换一张白板，把 Transformer 的结构图拆开，沿着一次前向的数据流从头走到尾。图上左边是编码器，右边是解码器，中间那根箭头，是它们之间最主要的信息通道。

开场：先把这一节的承诺立起来，再用一个极简骨架告诉学生「左边编码器、右边解码器、中间一条 z 通道」。

Scene 1 (0.0–5.0s): 深色网格底铺满全帧（全时长 clip 底层）。kicker「课程节点 · 整体结构」从下方 24px 上浮落位；主标题「Transformer 的结构」以 waterfall-entry 的逐段方式从下方弹入（每段 0.28s，总 ≤ 0.6s 的段落波次），落在 y≈300。
Scene 2 (5.0–14.0s): 副标题「一次前向的数据流」从标题下方 0.6s 处上浮。骨架开始：左侧编码器栈（3 个 `frame.md` block 叠片，accent 描边）在 x≈520 弹出；右侧解码器栈（accent-2 描边）在 x≈1280 弹出。
Scene 3 (14.0–23.5s): 中间的水平通道用 svg-path-draw 从左栈画到右栈，线中点落一个 ok 色 chip「z 连续表示」；通道下方补一个小标签「编码器 → z → 解码器」。最后 ambient-glow-bloom 在 z chip 后方绽开一层柔光（峰值 ≤0.45）并保持到帧尾。左下角页脚「01 / 10」在 21s 淡入。

## Frame 2 — 一次前向的总览

- status: outline
- src: compositions/frames/02-dataflow.html
- duration: 39.86s
- transition_in: crossfade 0.5s
- poster: 34s
- blueprint: compose
- rules: spring-pop-entrance, svg-path-draw, nudge-curve
- focal: 横向主链：输入嵌入 → 编码器栈 → z → 解码器栈 → 线性 + softmax
- scene: 横向数据流链逐段接通，z 被解码器反复读取，右侧补上自回归反馈环
- voiceover: 先看整体骨架。输入的符号序列，x1 到 xn，每个符号先做嵌入，再送进编码器栈。编码器把它们映射成一串连续表示，记作 z，也就是 z1 到 zn。z 是整段输入的连续表示，带着整条输入序列的信息，被解码器的每一层反复读取。解码器拿到 z 之后，自回归地一次生成一个输出符号；生成下一个符号时，把已经生成的符号作为额外输入再接回去。最后一层的输出经过一个线性层和 softmax，得到下一个符号上的概率分布。

总览：一条可跟随的横向链路，按旁白的四个环节分四段接通；反馈环单独放在解码器下方，避免与主链抢视线。

Scene 1 (0.0–4.0s): kicker「整体数据流」与标题「一次前向：四个环节」先后落位（y≈150）。左侧 token 行出现：4 个 64×64 圆角小格 x1 x2 x3 x4，下方 label「输入序列」。
Scene 2 (3.0–9.5s): svg-path-draw 从 token 行画到编码器块；编码器块以 spring-pop-entrance 弹入（y≈300，260×180），块内「编码器栈」32px + 「N = 6」+「自注意力 + 前馈」28px。上方 chip「输入嵌入」在 token 行与块之间落位。
Scene 3 (9.5–15.5s): 编码器输出箭头画出，中间 ok 色 chip「z = (z1 … zn)」弹入；chip 下 label「连续表示 · 整段输入的信息」。ambient-glow-bloom 短暂照亮该 chip。
Scene 4 (15.5–24.0s): 解码器块弹入（x≈1240，accent-2 描边，块内「解码器栈」「N = 6」「自回归，一次一个符号」）；z → 解码器的输入箭头以 accent-2 虚线画出，线上 chip「每一层都读取 z」。
Scene 5 (24.0–31.5s): 输出箭头到右侧「线性」块，再短箭头到「softmax」块（两块 200×120，一上一下错开 70px），末尾 chip「下一个符号的概率」；解码器块下方出现 y1 y2 两枚 44px chip 与省略号，label「已生成的符号」。
Scene 6 (31.5–39.86s): 自回归反馈环：一条从「已生成的符号」向上绕回解码器输入的虚线弧用 svg-path-draw 画出，线上小 chip「作为额外输入」；随后一条底部说明条淡入「z 被每一层反复读取」保持到帧尾。

## Frame 3 — 编码器：六层，每层两个子层

- status: outline
- src: compositions/frames/03-encoder.html
- duration: 29.21s
- transition_in: crossfade 0.5s
- poster: 24s
- blueprint: compose
- rules: spring-pop-entrance, svg-path-draw, sine-wave-loop
- focal: 展开的单层：两个子层 + 残差旁路
- scene: 左边六层堆叠，右边展开一层：自注意力 → 前馈网络，各自套残差与归一化
- voiceover: 现在把编码器放大。它由 N 等于 6 个完全相同的层堆叠而成，注意是同一套结构的六份拷贝，不是六种不同的层。每一层只有两个子层。第一个是多头自注意力，让每个位置都能看到输入序列里的所有位置；第二个是逐位置的全连接前馈网络，对每个位置单独做同样的变换。先自注意力，再前馈网络，然后交给上一层。

编码器：先给「六层」的量感，再把一层摊开成两个子层；残差与归一化只做位置提示，留给第 6 帧细讲。

Scene 1 (0.0–4.0s): kicker「编码器」+ 标题「N = 6 个相同的层」（y≈150）。左侧堆叠：3 个 420×86 的横条上下错位 16px 落位，最上层实心并标「×6」，右侧竖排 label「同一套结构」。
Scene 2 (4.0–8.5s): 右侧展开面板以 nudge-curve 从 x+80 滑入落定（x≈1000，宽 720，高 640，surface 底 + stroke 描边），面板顶部 label「一层 Encoder Layer」。
Scene 3 (8.5–16.0s): 子层 1 块弹入：「多头自注意力」32px + 副标「每个位置看所有位置」28px；其右侧残差旁路弧（svg-path-draw）绕过该块，接一个 28px 的「Add & Norm」小药丸；一条从子层 1 顶到子层 2 的箭头画出。
Scene 4 (16.0–23.5s): 子层 2 块弹入：「逐位置前馈网络」+ 「每个位置单独变换」；第二条残差旁路与第二个「Add & Norm」药丸画出；顶部箭头指向「→ 上一层」chip。
Scene 5 (23.5–29.21s): 底部说明 chip「六份拷贝，不是六种层」落位；左侧堆叠三条用 sine-wave-loop 做一次极轻的呼吸（有限次数，幅度 4px），帧尾静止。

## Frame 4 — 解码器：第三子层是交叉注意力

- status: outline
- src: compositions/frames/04-decoder.html
- duration: 27.77s
- transition_in: crossfade 0.5s
- poster: 22s
- blueprint: compose
- rules: spring-pop-entrance, svg-path-draw, ambient-glow-bloom
- focal: 解码器层的三个子层，交叉注意力在中间
- scene: 解码器层展开成三个子层，z 从左侧汇入中间的交叉注意力
- voiceover: 解码器同样是六层，但每层有三个子层。除了自注意力和前馈网络，中间还插入了第三个子层：它对编码器的输出做多头注意力，也就是交叉注意力。查询来自上一层解码器的输出，键和值来自编码器的输出 z。它让解码器的每个位置都能回看整个输入序列。而最下面那个自注意力子层，被改成了带掩码的版本。

解码器：与上一帧同构、多一层，用「塞进第三个子层」的动势表现差异；交叉注意力是这一帧的焦点。

Scene 1 (0.0–4.5s): kicker「解码器」+ 标题「每层三个子层」。左侧解码器堆叠（accent-2 描边，3 片，标「×6」）落位；顶部 chip「3 子层」弹入。
Scene 2 (4.5–10.0s): 右侧展开面板滑入（x≈1000，宽 760，高 660，顶部「一层 Decoder Layer」）。子层 A 弹入：「掩码多头自注意力」+ 副标「只看 ≤ i」。
Scene 3 (10.0–17.5s): 子层 B 以 spring-pop-entrance 从上下两个子层之间「挤入」：「交叉注意力」+ 副标「Q 来自解码器 · K、V 来自 z」；左侧 z chip 出现，两条 accent-2 箭头从 z 指入子层 B（标 K、V）；一条从上方子层 A 绕进 B 的短箭头（标 Q）。z 箭头落定时 ambient-glow-bloom 照亮一层柔光。
Scene 4 (17.5–23.5s): 子层 C 弹入：「逐位置前馈网络」；三条残差旁路弧用 svg-path-draw 依次画出，每条接 28px 的「Add & Norm」小药丸。
Scene 5 (23.5–27.77s): 底部说明条「第三个子层：解码器看整个输入的那扇窗」淡入；左侧堆叠轻微呼吸一次后静止。

## Frame 5 — 三种注意力：只看查询、键、值从哪来

- status: outline
- src: compositions/frames/05-attention-roles.html
- duration: 39.53s
- transition_in: crossfade 0.5s
- poster: 34s
- blueprint: compose
- rules: waterfall-entry, spring-pop-entrance, svg-path-draw
- focal: 三列并排的注意力用法对比
- scene: 三列依次立起，每列用 Q/K/V 来源与一张小掩码矩阵说明规则
- voiceover: 把三种注意力并排放，区别只在查询、键、值分别从哪来。编码器自注意力：三者都来自上一层编码器的输出，每个位置可以关注上一层所有位置。解码器自注意力：三者都来自解码器自身，但每个位置只能关注到包括自己在内的、位于它之前的解码器位置。编码器-解码器注意力：查询来自解码器，键和值来自编码器输出。所以自注意力负责整合单个序列内部的信息，交叉注意力负责对齐输入和输出这两个序列。

三种用法：三列等权并置，图例固定在上方；每列只放 Q/K/V 来源 + 一句规则 + 一张 3×3 或 4×4 小矩阵。

Scene 1 (0.0–5.0s): kicker「三种用法」+ 标题「只看 Q K V 从哪来」。图例行在 y≈270：三枚药丸「Q 查询」（accent）、「K 键」（ok）、「V 值」（accent-3），以 waterfall-entry 依次落下。
Scene 2 (5.0–16.0s): 第 1 列（x≈150，宽 480）立起：列头「编码器自注意力」；三枚 Q/K/V 药丸与一个来源块「上一层编码器输出」用箭头相连；规则行「每个位置看所有位置」；底部 3×3 小矩阵 9 格全 ok。
Scene 3 (16.0–27.0s): 第 2 列（x≈720）立起：列头「解码器自注意力」；来源块「解码器自身」；规则行「只看 i 及之前」；底部 4×4 小矩阵下三角 ok、上三角 danger 半透明。
Scene 4 (27.0–36.0s): 第 3 列（x≈1290）立起：列头「编码器-解码器注意力」；两个来源块「上一层解码器」（接 Q）与「编码器输出 z」（接 K、V），箭头用 svg-path-draw 画出；规则行「解码器对齐整个输入」。
Scene 5 (36.0–39.53s): 底部总结条淡入：「自注意力整合单个序列 · 交叉注意力对齐两个序列」，保持到帧尾。

## Frame 6 — 残差与层归一化：为什么能堆六层

- status: outline
- src: compositions/frames/06-residual-norm.html
- duration: 27.22s
- transition_in: crossfade 0.5s
- poster: 23s
- blueprint: compose
- rules: svg-path-draw, spring-pop-entrance, nudge-curve
- focal: 残差旁路 + LayerNorm 汇合点与公式板
- scene: 子层块出现，旁路绕过它汇入加法，公式被逐段写出，最后标出统一维度
- voiceover: 每个子层外面都套了一圈残差连接，再接一个层归一化。所以子层的输出写成：LayerNorm，括号里是 x 加上 Sublayer(x)。x 是子层的输入，残差让梯度有一条直达的捷径，这是能堆到六层甚至更深的原因。为了能做这个加法，所有子层和嵌入层的输出维度都统一成 d_model 等于 512。

残差与归一化：一帧一图一公式。旁路弧是主角，公式板是落点，维度标注收尾。

Scene 1 (0.0–4.0s): kicker「每个子层外面」+ 标题「残差 + 层归一化」。中央偏左出现子层块（x≈380，y≈360，520×220）：「Sublayer(x)」+ 副标「多头注意力 / 前馈网络」。
Scene 2 (4.0–11.0s): 输入的 x 标签从左侧进入，一条箭头入块；同时一条上方旁路弧用 svg-path-draw 从 x 出发、绕过块顶到右侧汇合点；汇合点「+」圆形节点 spring-pop-entrance。
Scene 3 (11.0–17.0s): 「LayerNorm」板从汇合点右侧弹出（260×110）；输出箭头指向右端 chip「下一子层」。下方公式板滑入（x≈380，y≈700，宽 1100，高 130）：分四段写出 LayerNorm、括号、x +、Sublayer(x)，每段 0.3s。
Scene 4 (17.0–22.0s): 旁路弧加粗高亮 + 小 chip「梯度直达」；右侧 chip「能堆 N = 6 层」落位。
Scene 5 (22.0–27.22s): 维度标注：一条括号线罩住子层块、公式板与输出，标「d_model = 512」；底部说明「为了能相加，嵌入层与所有子层统一维度」淡入并保持。

## Frame 7 — 掩码：把非法的位置设成负无穷

- status: outline
- src: compositions/frames/07-mask.html
- duration: 36.26s
- transition_in: crossfade 0.5s
- poster: 31s
- blueprint: compose
- rules: spring-pop-entrance, svg-path-draw, ambient-glow-bloom
- focal: 4×4 掩码矩阵与 softmax 前置步骤
- scene: 矩阵逐格铺开，上三角被负无穷吞掉，右侧管线说明顺序
- voiceover: 再看掩码。缩放点积注意力先算查询和键的点积，除以根号 dk，再做 softmax 得到权重。为了让位置 i 只能看到它自己和它左边，我们在 softmax 之前，把矩阵里所有非法连接的位置设成负无穷。负无穷经过 softmax 变成零，权重就全部落在合法位置上。softmax 之后，我们用这些权重对值做加权求和，结果就是这个位置的输出。图上这个四乘四的例子里，右上角被整片置成负无穷。

掩码：左侧矩阵是主角，右侧一条四步管线交代「在 softmax 之前」。非法格用 accent-3 到 danger 的渐变表现，不靠缩小字号。

Scene 1 (0.0–5.0s): kicker「解码器自注意力」+ 标题「把非法连接设成 −∞」。4×4 矩阵容器出现（左上 x≈200，y≈300，格 96 gap 10），行列标签「位置 1…4」28px。
Scene 2 (5.0–11.0s): 16 个格子按行序 spring-pop-entrance 铺开（每格 0.06s 偏移，总 ≤0.5s 波次），全部 ok 描边、格内显示点号。
Scene 3 (11.0–17.0s): 右侧管线（x≈1180，y≈300）四段立起：「QKᵀ / √dk」→「+ mask」→「softmax」→「× V」；箭头逐段画出；「+ mask」段染 accent-3。
Scene 4 (17.0–25.0s): 上三角 6 格依次翻面：填充换成 danger（0.18 透明），格内显示「−∞」，每格 0.16s 偏移；左上到右下的对角线补一道 ok 高亮；标签「位置 i 只能看 ≤ i」落位。
Scene 5 (25.0–31.0s): 矩阵右侧出现一行小示意 4 格：「−∞ → 0」，配 chip「softmax 把 −∞ 变成 0」；ambient-glow-bloom 在矩阵对角线上短暂亮起。
Scene 6 (31.0–36.26s): 底部说明条「权重只落在合法位置 → 对 V 加权求和」淡入，保持到帧尾。

## Frame 8 — 右移一位：掩码与错位的配合

- status: outline
- src: compositions/frames/08-shift.html
- duration: 30.65s
- transition_in: crossfade 0.5s
- poster: 26s
- blueprint: compose
- rules: nudge-curve, spring-pop-entrance, svg-path-draw
- focal: 目标序列与右移后的解码器输入两行对齐
- scene: 两行 token 错开一位，竖线连出「输入位置 j 预测输出位置 j+1」
- voiceover: 光有掩码还不够，还要配合输出嵌入右移一位。训练时，我们把目标序列整体右移一格再喂给解码器，于是位置 i 的输入里只剩位置小于 i 的已知输出，模型的任务就是预测位置 i 上的符号。左向的信息流被切断，错位又保证每个位置都在预测它后面的那一个。两件事合起来，位置 i 的预测只能依赖它之前的已知输出，自回归性质就保住了。

右移一位：两行 token 的错位是唯一主角；掩码只以小矩阵和两枚保证 chip 复述，不重复第 7 帧的细节。

Scene 1 (0.0–6.0s): kicker「自回归」+ 标题「掩码 + 右移一位」。上排 token 行出现（y≈330，4 格 96×96 gap 24）：y1 y2 y3 y4，左侧 label「目标输出」。
Scene 2 (6.0–13.0s): 下排 token 行以 nudge-curve 从左侧滑入并向右错开一格（x 偏移 120，y≈520）：<s> y1 y2 y3，label「解码器输入（右移一位）」；下排与上排的错位关系用 4 条竖向细虚线连出（svg-path-draw），每条连「下排第 j 格」到「上排第 j+1 格」。
Scene 3 (13.0–21.0s): 高亮位置 i 的一组：上排 y3 描边加粗并放大到 1.06；左侧小矩阵（4×4，格 44）出现，下三角 ok、上三角 danger；chip「预测 y3 只看 y1、y2 和 <s>」落位。
Scene 4 (21.0–27.0s): 两枚保证 chip 依次弹入：「左向信息流切断」、「错位一位」；下方一行 40px「位置 i 只依赖位置 < i 的已知输出」。
Scene 5 (27.0–30.65s): 收束行「自回归性质保住了」以 48px accent 色落位并保持到帧尾。

## Frame 9 — 把链路连起来：一次前向的清单

- status: outline
- src: compositions/frames/09-recap.html
- duration: 27.05s
- transition_in: crossfade 0.5s
- poster: 23s
- blueprint: compose
- rules: grid-card-assemble, control-target-sync, svg-path-draw
- focal: 左侧清单与右侧链路图逐行同步高亮
- scene: 清单逐行落下，右侧同一张链路图对应环节同时点亮
- voiceover: 现在把整条链路连起来。输入嵌入加上位置编码，进入六层编码器，每层先自注意力再前馈网络，每个子层外面是残差和层归一化，最后输出 z。解码器六层，每层掩码自注意力、交叉注意力、前馈网络，同样套残差和归一化。最后一层接线性层和 softmax，给出下一个符号的概率分布。

回顾：把前八帧的零件合成一张可带走的清单；左侧条目与右侧链路图在同一拍高亮（control-target-sync）。

Scene 1 (0.0–4.0s): kicker「一次前向」+ 标题「把链路连起来」。左侧清单容器出现（x≈150，宽 800），右侧链路图骨架（x≈1080，宽 640）以低透明度先可见。
Scene 2 (4.0–24.0s): 6 条清单以 grid-card-assemble 逐条落下（每条约 3s 间隔）：①「输入嵌入 + 位置编码」②「编码器 ×6：自注意力 → 前馈」③「每个子层：LayerNorm(x + Sublayer(x))」④「z」⑤「解码器 ×6：掩码自注意力 → 交叉注意力 → 前馈」⑥「线性 + softmax → 概率」。每条落位时，右侧链路图对应节点同步变色（同一时间点、同一缓动）。
Scene 3 (24.0–27.05s): 右侧链路图补一条贯通的主箭头（svg-path-draw），底部收束行「嵌入 → 编码 → z → 解码 → 概率」落位并保持。

## Frame 10 — 收束：记住三件事

- status: outline
- src: compositions/frames/10-close.html
- duration: 14.89s
- transition_in: crossfade 0.5s
- poster: 12s
- blueprint: compose
- rules: waterfall-entry, ambient-glow-bloom, spring-pop-entrance
- focal: 三枚回顾卡
- scene: 三枚要点卡依次落位，结尾给出下一节方向
- voiceover: 这一节记住三件事：左右两个栈、每个子层的残差加归一化写法，还有掩码配合右移一位。下一节我们钻进自注意力内部，把打分和加权求和算清楚。

收束：三枚卡对应三条可自测的要点；不设题、不列作业，只留下下一节的入口。

Scene 1 (0.0–5.0s): kicker「本节收束」+ 标题「记住三件事」以 waterfall-entry 落位（y≈240）。
Scene 2 (5.0–11.0s): 三枚 420×300 卡片在 y≈420 依次 spring-pop-entrance：①「两个栈」+ 两枚竖向小叠片示意；②「LayerNorm(x + Sublayer(x))」+ 32px 公式；③「掩码 + 右移一位」+ 4×4 小矩阵示意。卡内副标 28px。
Scene 3 (11.0–14.89s): 下一节 chip「下一节：自注意力内部 —— 打分与加权求和」在 y≈800 落位，ambient-glow-bloom 在卡片后方轻亮一次，帧尾静止保持。
