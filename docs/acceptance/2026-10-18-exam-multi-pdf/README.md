# 2026-10-18 模拟考试：多 PDF 上线与端到端验收

本轮修复已部署至 **0014**，但**整体只部分通过，不能宣布所有 PDF 都能稳定出卷或答案完全可靠**。当前服务健康正常，完整 DeepTutor 上游及核心生成、独立求解、审核、修复流程保留；上传仍仅由 MinerU 解析，不创建知识库索引。

最终部署证据见 [deployment.json](deployment.json)，06:35 UTC 收尾复核见 [final-health.json](final-health.json)：源码与锁一致、Nginx 200、活动上游任务 0、该部署后旧上下文清理异常 0。补丁 SHA256 `9e9aea41c18d0fa26619effe3ae65f0c49df5c21280212e872dea0480c3ffaeb`。157 项服务回归、85 项隔离后端回归通过。主后端和前端未因本轮桥接修复重发。服务继续明确返回 `exam_ready=false`：计时作答、交卷与评分尚未实现。

## 最有用的结果

“通过题数”表示系统审核接受的顶层题，不代表人工逐题确认正确；复合题子项另行核对。

| 正式运行目录 / 版本 | 抽取顶层题数 | 最后一轮通过题数 | 浏览器结果 |
| --- | ---: | ---: | --- |
| kentucky-0013 | 4 | 4/4 | 页面完整预览通过 |
| kentucky-0014 | 4 | 4/4 | 页面完整预览通过 |
| kentucky-0014-repeat | 4 | 4/4 | 页面完整预览通过 |
| princeton-0013 | 9 | 8/9 | 未通过整卷验收 |
| shanghai-0011 | 45 | 44/45 | 未通过整卷验收 |

Kentucky 0013/0014 是分别重新上传、创建新请求的正式运行，不是打开历史试卷冒充重新生成。0014 的两轮结果单独保留。Princeton 的最后整卷测试版本为 **0013**；上海的最后整卷测试版本为 **0011**。后续修复有定向真实模型或确定性回归证据，但没有把它们写成这两份整卷在 0014 已通过。

本轮共使用 **3 份不同的完整 PDF**，创建 **15 个重新上传案例、26 个生成尝试**；其中 14 个尝试完成完整生成汇总，其余包括抽题失败或为升级受控中断。页面验收通过 3 个案例。按上游 turn_id 关联的模型账本条目为 1150 条（不含 MinerU、未关联 turn 的调用与隔离定向复验，不等同于成功调用或账单计费次数）。完整分母、每轮状态、耗时、调用数与层级核对在 [summary.json](summary.json)，没有把中断任务计作成功。这些尝试混合多个版本、故障复现与升级恢复，不是同版本随机抽样，不能据此估算线上成功率。

## 资料与独立预期

| PDF | 页数 | 独立核对的结构 | 来源 |
| --- | ---: | --- | --- |
| Kentucky CS315 Spring 2021 Midterm | 4 | 4 个父题；子题分别为 4、4、5、4，共 17 个 | [大学图书馆发布页](https://manifold.open.umn.edu/projects/data-structures-and-algorithms/resource/data-structures-and-algorithms-midterm-exam-pdf) |
| Princeton COS226 Spring 2023 Midterm | 14 | 9 道知识题；原编号 1 是姓名、考场、承诺签名行政项；表格及子题应保留 | [学校原 PDF](https://www.cs.princeton.edu/courses/archive/spring24/cos226/exams/mid-s23.pdf) |
| 上海科技大学 2023 年 991 数据结构与算法 | 8 | 45 题：10 判断、15 单选、6 多选、14 应用题 | [学校发布页](https://sist.shanghaitech.edu.cn/2024/0930/c7340a1101320/page.htm) |

完整来源、直接下载地址、页数与 SHA256 见 [sources.json](sources.json)。没有裁切成容易通过的样本。另有两个下载地址返回 404，未计入测试。以前的中科大 32 题卷属于上一轮证据，本轮没有将它算成新增 PDF。

## 已修复与证据

1. **英文选项与子题选项格式。** 0010 将 `front/back` 等原始标签按顺序映射为前端字母键，保留原标签；0012 兼容模型给出的完整唯一 `key/text` 选项数组，含复合题子项。缺失、重复、未知键与空文字仍拒绝。真实失败复合题定向生成通过，见 [child-options-quality.json](child-options-quality.json)。
2. **跨页抽题、重复与层级。** 0011 增加一次有界行号纠正、跨页补读前文、包含型同题去重，过滤明确行政填表项，校验非空复合题并保留表格子问。0012 正式 Kentucky 仍曾被展开为 17 顶层题；0013 增加明确父编号与字母子题的层级纠正/拒绝机制。独立真实抽题复验见 [extraction-0011-e.json](extraction-0011-e.json)、[extraction-0011-f.json](extraction-0011-f.json)、[extraction-0013-a.json](extraction-0013-a.json)。不能把题数正确等同于所有语义保真。
3. **允许一个正确项的多选题。** 上海原卷明确允许一个或多个。0010 完整两轮为 43/45、44/45，最后被“至少两项”规则卡住。0011 仿卷允许非空的一项或多项，保留非仿卷原限制。
4. **长调用保活与上下文清理。** 空闲 15 秒发 NDJSON 空行，客户端忽略，不伪造事件。初版每次读取切换协程，引发 ContextVar 清理错误；05:37:29 UTC 改为单个生产协程持有完整迭代生命周期、64 项有界队列。旧实现的回归失败记录、修复后的测试和真实 HTTP 超时对照均保留。[heartbeat-http.json](heartbeat-http.json) 是空闲对照；生产观察期间有持续事件，不能据它宣称已观察到生产空闲心跳。
5. **符号表达式误截断。** 0012 不再把 `|V|-1=5` 的后缀当成 `-1=5`。同一失败产物的确定性复验见 [symbolic-boundary.json](symbolic-boundary.json)。
6. **JSON 内部代码块被当成外包装。** 上海失败题的真实响应是 785 字符合法 JSON、非空答案、正常 `stop`，并非模型没有作答。0013 先解析完整 JSON，保留答案中的伪代码围栏；外层说明由 JSON 对象解码处理。同响应对照见 [json-code-fence-replay.json](json-code-fence-replay.json)，真实求解复验见 [empty-solver-recheck.json](empty-solver-recheck.json)、[empty-solver-fixed.json](empty-solver-fixed.json)。
7. **有效的 false/0 被当作缺失。** 0014 保留布尔 `false` 和数字 `0`，包括复合题中的判断子题；`null` 仍拒绝为缺失。确定性旧/新转换对照见 [scalar-answer-replay.json](scalar-answer-replay.json)。这不能单独证明某次模型输出失败的全部原因都已消除。

## 仍有的问题

- **答案审核存在漏判与误判。** 对 0010 上海卷中已被模型接受的 7 题独立计算，5 题通过、2 题失败：第 8 题路径距离应为 4 却写成 3；第 28 题霍夫曼码长应为 4/4/3/2/1，平均 2.05，正确选项 AB，模型却接受 ABC 并写出 1.75。见 [independent-checks-0010.json](independent-checks-0010.json)。增强提示也未稳定拒绝等长路径歧义题，见 [tie-quality.json](tie-quality.json)。Princeton 0013 审查又把一类插入排序比较次数说成约 4n²，独立枚举得到 2n²+4n−2；候选题自身的解释和改编仍有问题，并非应直接放行，见 [sorting-review-check.json](sorting-review-check.json)。后续新卷同类数值改善，不证明通用问题已根治。
- **成功出卷不等于所有表述正确。** Kentucky 0013 成功卷中 6 道数值子题独立复算全部一致，见 [independent-kentucky-0013.json](independent-kentucky-0013.json)；但随机 BST 期望复杂度的解析出现“不会退化为链”的绝对表述，仍需审校。该抽查不覆盖全部答案与所有改编是否充分。
- **复杂卷仍有失败与较长耗时。** Princeton 出现题型/子题结构、符号计算与答案校验失败；0012 Kentucky 曾出现模型连接重试耗尽。0012 单次完整生成阶段，Princeton 约 14 分 54 秒，展开后的 Kentucky 约 13 分 29 秒；这些时间不包含全部排队与上传开销。已限制模型重试次数，没有为了通过而关闭校验。
- **预览有内容重复。** 某些复合题父题正文已列出子题，前端再渲染结构化子题，出现重复内容；手机未横向溢出，但版面仍需整理。见 [手机预览局部](kentucky-0013/preview-detail-390.png)。
- **取消与排队反馈还需完善。** 曾观察到主任务取消后上游仍运行，测试清理时仅对本测试账号的上游任务显式取消。Kentucky 0011 的一个页面重试返回 202，但排队超过脚本原 60 秒，触发的是测试脚本断言；已延长等待窗口并取消该旧版排队任务，没有将它误写为接口拒绝。
- **完整考试流程尚未实现。** 本轮范围是上传真卷、MinerU、抽题、仿卷生成、刷新/重试和预览；不覆盖尚不存在的计时答卷、提交评分，也不证明普通讲义模式已通过。

## 链路、数据与版本边界

使用专用账号，经正式 Nginx 页面上传、真实模型与持久任务执行，不走 mock。各目录的 `online-browser.json`、`online-audit.json`、`online-boundary.json` 分别记录浏览器、只读生产审计与接口边界；原始模型/数据库内容保存在不公开的运行目录，认证信息不写入报告。

已检查完整卷读取 200、残缺卷读取 409、匿名读取 401，公开卷不含答案/解析字段；完整结果的题型、顺序、子题 ID 与冻结蓝图一致。所有本轮专用账号审计均为知识库/知识文档记录 0。刷新恢复与 1440/390/320px 检查以每个案例记录为准，不能将提前中断脚本算作页面通过。

初版保活故障曾导致主系统多两条终态事件，受控中断记录也可能未完全排空，不作为事件一致性通过证据。修复后完整任务的上下游事件数一致并含 DONE。重启前已接受的 Princeton 2 题、上海 15 题均原样保留；上海 0010 重试也保留原 43 题。新补丁会使旧生成缓存失效，没有跨版本冒用旧答案。

历史结果保留：0009 英文抽题失败；0010 上海 43→44/45，英文中断；0011 Kentucky 两次 3/4、Princeton 恢复后 3/9、上海恢复后 42→44/45；0012 Kentucky 16/17（层级错误）、Princeton 4/9。每次部署的版本、PID、时间和哈希分别在 `deployment-*.json` 中，当前版本只以 `deployment.json` 为准。

复现入口：`verify_online.mjs`、`verify_resume.mjs`、`collect_online.py`、`check_boundaries.py`、`summarize_runs.py`、`independent_checks.py`、`independent_kentucky.py`、`check_sorting_review.py`、`verify_heartbeat.py`。服务回归记录为 [service-tests-0014.txt](service-tests-0014.txt)，隔离后端回归为 [backend-tests.txt](backend-tests.txt)。
