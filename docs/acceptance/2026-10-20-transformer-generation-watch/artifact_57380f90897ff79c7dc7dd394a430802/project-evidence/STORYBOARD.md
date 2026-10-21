---
format: 1920x1080
duration: 290s
message: "自注意力用常数步顺序操作换来 O(1) 路径长度，代价是每层 O(n²·d) 复杂度；而“完全并行”只对编码器和训练时的解码器成立"
arc: 取舍问题 → 循环的串行代价 → 三个衡量角度 → 逐列填表 → n<d 的条件 → 代价与受限注意力 → 完全并行的边界 → 结论与佐证
audience: 希望系统学习 Transformer 的初学者
---

## Frame 1 — 开场：一个取舍问题

- scene: 大标题抛出问题，右侧三枚衡量角度胶囊依次落位
- duration: 28.9s
- poster: 24s
- transition_in: cut
- status: animated
- voiceover: 前面我们看清了 Transformer 的整体结构，也拆开了缩放点积注意力。这一节只回答一个问题：既然循环网络已经能做序列到序列的任务，为什么还要换成自注意力？那句常听到的“完全并行”，又在什么范围内成立？判断不靠直觉，靠三个可量化的角度：每层计算复杂度、最少顺序操作数、以及任意两个位置之间的最大路径长度。
- blueprint: compose
- rules: waterfall-entry, spring-pop-entrance
- focal: 主标题
- src: compositions/frames/01-opening.html

Scene 1 (0.0–3.0s): 页眉常驻（左 `Transformer · 取舍判断`，右 `01 / 09`）。主标题第一行 `为什么不用循环？` 自下方 20px 上移淡入，字号 84px，字重 800；标题下 4px accent 短线从左向右画出（scaleX 0→1）。
Scene 2 (3.0–8.5s): 主标题第二行 `自注意力取代循环网络的那笔账` 以同样方式淡入，字号 56px、muted；保持两行左对齐，整体位于画面左侧 120–1000px、垂直中线偏上（约 y=300–470）。
Scene 3 (8.5–14.5s): 画面右侧（x≈1180–1800）三枚角度胶囊依次 spring pop（间隔 0.45s，back.out 轻微过冲）：`每层计算复杂度`、`最少顺序操作数`、`最大路径长度`，每枚 40px 文字、panel 底、左侧 6px accent 竖条；第三枚落下后右侧出现 30px muted 小注 `三个可量化的角度`。
Scene 4 (14.5–22.0s): 主标题下方 40px 处淡入一行 34px muted 的短提示 `不靠直觉，看三个指标`（不是旁白原句），与左侧三枚胶囊形成呼应。
Scene 5 (22.0–28.9s): 画面静止可读。第 24 秒在右下角（y≈860，仍在安全线内）淡入出处 chip：一个 6px accent 圆点 + 28px muted `Attention Is All You Need · §4`。

## Frame 2 — 循环的固有串行性

- scene: 五节点隐藏状态链逐节点点亮，下方阶梯标出顺序步数
- duration: 29.5s
- poster: 26s
- transition_in: crossfade 0.35s
- status: animated
- voiceover: 先看被替换的一方。循环模型沿符号位置分解计算：每一步的隐藏状态，都由前一个隐藏状态和当前位置的输入共同决定。对齐到计算时间上，位置 t 必须等位置 t 减一算完，这就形成一条长度等于序列长度的依赖链。代价不只是慢：一个训练样本内部无法并行，只能在样本之间批处理，序列越长，可并行的批量越受显存限制。
- blueprint: compose
- rules: spring-pop-entrance, svg-path-draw
- focal: 五节点依赖链
- src: compositions/frames/02-recurrence.html

Scene 1 (0.0–4.0s): 页眉 + 标题 `循环：一条长度为 n 的链`（56px）淡入；标题右侧 30px muted `h_t 依赖 h_{t−1}`。
Scene 2 (4.0–10.0s): 五个 96×96 节点从左到右 spring pop（间隔 0.32s，scale 0.8→1 轻微过冲），节点内依次是 `h₁`…`h₅`（40px，italic），节点底为 panel、1px line 边框。
Scene 3 (10.0–16.5s): 四条连接线由左向右依次绘制（scaleX 0→1，3px，line 色），完成后线色转 accent、节点边框同步转 accent；每两个节点之间的弧线上方出现 28px muted `依赖前一步` 只在第一段标注一次即可（不重复铺满）。
Scene 4 (16.5–23.5s): 节点下方出现一条阶梯图：五级台阶依次升起（每级 120px 宽、高度递增 12px），台阶右侧标 30px `O(n) 次顺序操作`；阶梯上方出现 30px warning 色 pill `样本内无法并行`。
Scene 5 (23.5–29.5s): 阶梯下方淡入一行 32px muted `序列越长，可并行的批量越小`。画面静止保持到结束。

## Frame 3 — 三个衡量角度

- scene: 三张角度卡片自下而上组装，底部指向同一张空表格
- duration: 27.5s
- poster: 24s
- transition_in: crossfade 0.35s
- status: animated
- voiceover: 那怎么公平地比较不同的层类型？原论文给了三个角度。第一，每层的计算复杂度，一层要花多少计算量。第二，可以并行化的计算量，用最少顺序操作数衡量，也就是把所有位置并行算完需要几个串行步骤。第三，长程依赖的最大路径长度，信号从一个位置走到另一个位置要穿过多少层；路径越短，长程依赖越容易学。
- blueprint: grid-card-assemble (Adapt)
- rules: spring-pop-entrance
- focal: 三张角度卡片
- src: compositions/frames/03-three-lenses.html

Scene 1 (0.0–4.0s): 页眉 + 标题 `公平比较的三个角度`；标题下 accent 短线画出。
Scene 2 (4.0–11.0s): 第一张卡片（x≈160，宽 520，高 260）弹入：编号 `01` 30px accent、主标签 `每层计算复杂度` 44px、注释 `一层要花多少计算量` 30px muted。
Scene 3 (11.0–18.0s): 第二张卡片（x≈700）弹入：`02` / `最少顺序操作数` / `把所有位置算完要几步`；第三张（x≈1240）：`03` / `最大路径长度` / `信号要穿过几层`。三张卡片高度、圆角、内边距完全一致。
Scene 4 (18.0–23.0s): 三张卡片下方出现一条横向细线（line 色），三根 2px 竖线自每张卡片底部垂落到细线，再在细线下方汇成一条 accent 线，指向画面下方一个空表格轮廓（3 列 3 行的极淡描边，opacity 0.25，不填任何文字）。
Scene 5 (23.0–27.5s): 空表格轮廓上方淡入 30px muted `接下来逐列填满它`，画面静止保持。

## Frame 4 — 第一列：每层计算复杂度

- scene: 三行对比表出现，第一列被点亮并逐行填入复杂度
- duration: 32.2s
- poster: 29s
- transition_in: cut
- status: animated
- voiceover: 先填第一列，每层计算复杂度。自注意力是 n 平方乘 d 的量级：n 个位置两两打分，得到一个 n 乘 n 的注意力矩阵，每个元素是一次长度为 d 的点积。循环层是 n 乘 d 平方：n 个时间步，每步把 d 维输入乘上 d 乘 d 的权重矩阵。卷积层是 k 乘 n 乘 d 平方：核宽 k，深度可分离卷积能压小后面的项，但单个卷积核宽小于序列长度时，连不上所有位置对。
- blueprint: compose
- rules: spring-pop-entrance, depth-of-field-blur
- focal: 对比表第一列
- src: compositions/frames/04-complexity.html

表格几何全片统一：左标签列 x=160–520；三个数据列 x=560–960 / 980–1380 / 1400–1760；表头 y≈300；三行中心 y≈420 / 560 / 700。所有出现表格的帧必须复用这套坐标。

Scene 1 (0.0–4.5s): 页眉 + 标题 `第一列：每层计算复杂度`。表格骨架淡入：表头 `每层计算复杂度`、`最少顺序操作数`、`最大路径长度`（30px muted），行标签 `自注意力`、`循环`、`卷积`（40px ink），行间 1px line 分隔线，三列数据区暂时为空。
Scene 2 (4.5–13.0s): 第一列点亮（其他两列 opacity 0.28，第一列顶部出现 2px accent 短线与 accent 边框），三个数值依次填入：`O(n²·d)`、`O(n·d²)`、`O(k·n·d²)`（46px italic，每行 spring pop 0.94→1）。
Scene 3 (13.0–23.0s): 每当一个数值落位，其右侧或下方出现 28px muted 注释，依次为 `n×n 打分矩阵`、`每步 d×d 权重`、`核宽 k`。
Scene 4 (23.0–28.5s): 表格下方一行 32px `自注意力：每层随 n 平方增长`（n 平方用 accent 强调），其他两列保持变暗。
Scene 5 (28.5–32.2s): 静止保持，右下角出处 chip `Attention Is All You Need · §4 Table 1`。

## Frame 5 — 第二、三列：顺序操作数与路径长度

- scene: 同一张表继续填第二列与第三列，逐项对比
- duration: 38.9s
- poster: 35s
- transition_in: cut
- status: animated
- voiceover: 第二列，最少顺序操作数。自注意力是常数级：所有位置同时打分、同时加权求和，一层只要常数个串行步骤。循环是 n 级：第 t 步必须等第 t 减一步，顺序步数等于序列长度。卷积也是常数级，每个输出只依赖固定窗口内的输入。第三列，最大路径长度。自注意力是常数：任意两个位置一步直达。循环是 n：信息要沿链一步步传。卷积是对数级：以 k 为底、n 的对数，需要 n 除以 k 层连续卷积，或者用膨胀卷积压到对数层。
- blueprint: compose
- rules: spring-pop-entrance, depth-of-field-blur
- focal: 第二列与第三列
- src: compositions/frames/05-sequential-path.html

Scene 1 (0.0–3.0s): 页眉 + 标题 `第二、三列：并行度与路径长度`。表格与 Frame 4 完全同位置出现，第一列数值保留但整列 opacity 0.28；第二列点亮。
Scene 2 (3.0–13.0s): 第二列逐行填入 `O(1)`、`O(n)`、`O(1)`；每行落位后在其下方出现 28px muted 注释 `所有位置同时算`、`第 t 步等第 t−1 步`、`固定窗口`。
Scene 3 (13.0–16.5s): 第二列保持填充并变暗到 0.55，第三列点亮（accent 边框与顶部短线），标题右侧淡入 30px muted `路径越短越易学`。
Scene 4 (16.5–30.0s): 第三列逐行填入 `O(1)`、`O(n)`、`O(log_k n)`，每行行末出现一个极简路径示意（宽 120px、高 36px 的 CSS/SVG 图形）：一步直达的水平箭头、五段串联箭头、逐级扩张的三层折线；示意为 2px line 色，当前行用 accent。
Scene 5 (30.0–38.9s): 三列同时可见（全部 opacity 1），表格下方出现两行 32px：`顺序操作：O(1) / O(n) / O(1)`、`路径长度：O(1) / O(n) / O(log_k n)`；画面静止保持。

## Frame 6 — 条件：n < d

- scene: 两个复杂度公式约简成 n 与 d 比较，再用具体数字与横条对比
- duration: 36.8s
- poster: 33s
- transition_in: crossfade 0.35s
- status: animated
- voiceover: 这里有个必须说清的条件。比较 n 平方乘 d 和 n 乘 d 平方，同时约掉 n 和 d，剩下就是 n 与 d 比大小：当序列长度 n 小于表示维度 d 时，自注意力每层反而更省。这在句子上通常成立。原论文用 word piece 和 byte pair 表示，句子长度只有几十，而模型维度是五百一十二。比如 n 取四十、d 取五百一十二，n 平方乘 d 约八十二万，n 乘 d 平方约一千万，差一个数量级。
- blueprint: compose
- rules: stat-bars-and-fills, spring-pop-entrance
- focal: n < d 的不等式与两根横条
- src: compositions/frames/06-n-condition.html

Scene 1 (0.0–4.5s): 页眉 + 标题 `条件：n < d`；标题右侧 30px muted `不是无条件更快`。
Scene 2 (4.5–12.0s): 左上方出现两枚公式胶囊 `O(n²·d)` 与 `O(n·d²)`（并列，40px italic）；中间出现 30px muted `同时约掉 n 和 d`，随后两枚胶囊向中间收拢，合并成一个大号 64px `n vs d`（spring pop）。
Scene 3 (12.0–22.0s): 画面下方出现数字示例：`n = 40`、`d = 512` 两枚数值胶囊（34px）；其下两根水平条（stat-bars，高度 44px、圆角 8px，从 0 以 scaleX 展开）：上条 accent、标签 `n²·d ≈ 82 万`；下条 warning、标签 `n·d² ≈ 1000 万`。两根条长度比约 1 : 12，右侧标 36px `差一个数量级`。
Scene 4 (22.0–30.5s): 右侧竖排两块注记淡入：`word-piece / byte-pair`（34px）与其下 28px muted `句子长度只有几十`；`d_model = 512`（34px）与其下 28px muted `表示维度通常更大`。
Scene 5 (30.5–36.8s): 顶部留一行 32px accent `n < d 时，自注意力每层更省`；画面静止保持。

## Frame 7 — 代价与受限自注意力

- scene: 平方增长曲线上升，再用邻域窗口说明受限自注意力的交换
- duration: 30.7s
- poster: 27s
- transition_in: crossfade 0.35s
- status: animated
- voiceover: 代价也要摆在同一张表上。自注意力的复杂度对 n 是平方的：序列翻倍，每层计算量和注意力矩阵的内存都变成四倍，长序列下这就是瓶颈。原论文给出一条缓解路径：每个位置只看邻域 r 以内的位置，就是受限自注意力。复杂度从 n 平方乘 d 降到 r 乘 n 乘 d，代价是最大路径长度从常数升到 n 除以 r。账没有消失，只是换了位置。
- blueprint: compose
- rules: svg-path-draw, spring-pop-entrance
- focal: 平方曲线与邻域窗口
- src: compositions/frames/07-cost.html

Scene 1 (0.0–4.0s): 页眉 + 标题 `代价：n 的平方`；标题右侧 30px warning `序列翻倍，计算变四倍`。
Scene 2 (4.0–13.0s): 左侧（x≈160–840，y≈320–780）出现坐标轴（2px line）与两条曲线：accent 的平方曲线由左下向右上陡升（stroke-dasharray 绘制 1.2s），muted 的线性参考线同步出现；横轴标 `n`、纵轴标 `每层计算量`（28px muted）。曲线末端出现 30px accent `O(n²·d)`。
Scene 3 (13.0–22.0s): 右侧（x≈940–1780）出现一条由 11 个小方块组成的位置序列（每块 56×56，间隔 8）；中间位置用 accent 括号圈出 5 个方块，括号下标注 30px `邻域 r`；方块上方 34px `受限自注意力`，其下 40px italic `O(r·n·d)`（accent）。
Scene 4 (22.0–27.0s): 右下出现两枚并排胶囊：`计算 ↓`（positive 边框）与 `路径长度 O(1) → O(n/r)`（warning 边框，内文 30px）；上方 30px muted `用计算换路径`。
Scene 5 (27.0–30.7s): 底部一行 32px muted `账没有消失，只是换了位置`；静止保持。

## Frame 8 — 完全并行的边界

- scene: 左右分屏：训练一次前向并行 vs 生成 m 个词元 m 次前向
- duration: 32.9s
- poster: 29s
- transition_in: crossfade 0.35s
- status: animated
- voiceover: 现在说那句最容易误解的“完全并行”。它只对编码器，以及训练时的解码器成立。训练用教师强制：解码器输入是真实目标句右移一位的结果，因果掩码保证位置 i 只能看到位置一到 i，于是所有位置的预测能在一次前向里同时算出。推理时没有真实答案，第 i 个词元必须等第 i 减一个选出来，才能作为输入。生成 m 个词元，仍然需要 m 次顺序前向。
- blueprint: compose
- rules: waterfall-entry, spring-pop-entrance
- focal: 左右分屏对照
- src: compositions/frames/08-parallel-boundary.html

Scene 1 (0.0–4.5s): 页眉 + 标题 `完全并行：到哪里为止`。画面分成左右两栏（左 x=120–920，右 x=1000–1800），中缝一条 1px line 竖线；左栏标题 `训练 · 并行`（44px，accent），右栏标题 `生成 · 串行`（44px，warning），两栏标题各带一条 2px 下划线。
Scene 2 (4.5–13.0s): 左栏出现两行词元方块（每块 88×64、28px 字）：第一行 `BOS 我 爱 学 习`，第二行整体右移一格显示输入序列（第一格为淡色占位），下方 28px muted `真实目标句右移一位`；两行自左向右以 waterfall 依次落入（每块间隔 0.12s）。
Scene 3 (13.0–21.0s): 左栏词元下方出现 5×5 的因果掩码小网格（每格 26×26，space 6）：下三角（含对角线）accent 填充、上三角 line 描边；网格右侧 30px muted `位置 i 只看 1 … i`；网格下方一条横向 accent 箭头，贯穿整行词元，标注 30px accent `一次前向，所有位置同时出预测`。
Scene 4 (21.0–28.5s): 右栏自上而下出现三个词元方块 `y₁`、`y₂`、`y₃`（88×64），每个方块右侧一条折返箭头指回下一次前向；三个方块依次以 spring pop 点亮（间隔 0.9s），每次点亮时其左侧出现 28px muted `第 m 次前向`；右栏底部 34px `m 个词元 = m 次顺序前向`（warning 强调 m）。
Scene 5 (28.5–32.9s): 画面底部贯通两栏的一行 36px：`训练：并行`（accent） · `生成：串行`（warning），两侧各有一条短线；静止保持到结束。

## Frame 9 — 结论与工程佐证

- scene: 三行小结逐行落位，工程数据与最后判断句收束
- duration: 32.2s
- poster: 29s
- transition_in: crossfade 0.4s
- status: animated
- voiceover: 把这些放在一起，判断就清楚了。自注意力用常数个顺序操作，换来常数级的路径长度，代价是每层随 n 平方增长的复杂度；“完全并行”只覆盖编码器和训练时的解码器，不覆盖自回归生成。工程上的回报是真实的：原论文的模型在八块 P100 上训练十二小时，就达到了新的翻译质量最优。所以下次有人问 Transformer 为什么快，先问他一句：你说的是训练，还是生成？
- blueprint: compose
- rules: waterfall-entry, spring-pop-entrance
- focal: 三行小结与最终判断句
- src: compositions/frames/09-conclusion.html

Scene 1 (0.0–4.0s): 页眉 + 标题 `判断：一笔清楚的账`。
Scene 2 (4.0–13.0s): 三行小结自上而下逐行落入（每行 34px，左侧 40px 符号）：`＋ 顺序操作 O(1) · 路径长度 O(1)`（accent 符号）、`− 每层复杂度 O(n²·d)`（warning 符号）、`± 范围：编码器 + 训练时的解码器`（muted 符号）；行间 1px line 分隔。
Scene 3 (13.0–21.0s): 小结下方出现一枚工程佐证面板（宽 1080，高 140）：左 `8 × P100`（44px accent），中 `12 小时`（44px ink），右 `翻译质量 SOTA`（40px muted），三者以竖线分隔，依次 spring pop；面板左侧一条 4px accent 竖条。
Scene 4 (21.0–28.5s): 画面下方出现最终判断句，两段横排、字号 56px 字重 700：`训练并行`（accent） + 30px muted `≠` + `生成并行`（warning），整行由中间向两侧展开（scaleX 0→1 作用于底衬细线，文字淡入）。
Scene 5 (28.5–32.2s): 全部内容静止保持；右下角 28px muted 出处 chip `Attention Is All You Need · §4`，最后 1.5 秒做一次极轻的整体亮度收束（不淡出到黑，保持末帧可读）。
