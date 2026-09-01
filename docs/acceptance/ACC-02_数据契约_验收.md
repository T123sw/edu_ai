# ACC-02 · 数据契约 Stage/Scene/Action/Slide · 验收文档

> 对应 spec：[`../spec/SPEC-02_数据契约_Stage-Scene-Action-Slide.md`](../spec/SPEC-02_数据契约_Stage-Scene-Action-Slide.md)
> 对应 Phase：全阶段地基（随 Phase 2 落库校验落地）· 地图：[`../../项目总览地图.md`](../../项目总览地图.md) §8 数据契约
> 通用环境：见 [验收 README §2](README.md)
> 状态：⏳ 待做

---

## 1. 功能范围

**做**：edu_ai 正确**消费 + 校验 + 落库**上游 `Stage/Scene/Action/Slide`，不重定义类型；实现 SPEC-02 §6 的 6 条不变量校验；实现 SPEC-02 §4 的「整段 JSON 落库 + 稳定 id 索引」。

**不做**：重建等价 Pydantic 字段语义；拆解 DSL 内部字段进关系表；QuizContent/interactive/pbl 的深度处理（原样透传）。

---

## 2. 验收标准（DoD）

| 编号 | 标准 | 判定 |
| --- | --- | --- |
| AC-02-1 | 落库校验实现并生效：违反任一不变量则**拒绝落库**、标记失败、保留原始 JSON | |
| AC-02-2 | 不变量①：`Stage.id / Scene.id / Action.id / element.id` 非空且同层唯一，否则拒绝 | |
| AC-02-3 | 不变量②：`Slide.viewportRatio` 缺失则拒绝 | |
| AC-02-4 | 不变量③：`spotlight/laser.elementId` 在同 Scene 的 `Slide.elements` 找不到 → 拒绝 | |
| AC-02-5 | 不变量④：`play_video.elementId` 指向的元素非 `PPTVideoElement` → 拒绝 | |
| AC-02-6 | 不变量⑤：已配音 `speech.audioUrl` 若仍是 sidecar 临时地址（未改写为 edu_ai 地址）→ 拒绝 | |
| AC-02-7 | 落库结构：`classrooms(stage_json)` + `classroom_scenes(scene_json)`，`(classroom_id, scene_id)` 唯一 | |
| AC-02-8 | 取库→前端渲染 round-trip：落库再取出的 Stage/Scene 能被 renderer 完整渲染，无字段丢失 | |
| AC-02-9 | 编辑不换 id：改一页内容后 `element.id/scene.id` 不变（幂等 upsert） | |

---

## 3. 测试方法

### 3.1 单元测试（校验器，pytest）
落点建议 `backend/tests/test_classroom_contract.py`。构造夹具（fixtures）覆盖每条不变量的**正例 + 反例**。

**T-02-A 合法样本通过（AC-02-1/7）**
- 输入：一份合法 Stage（1 slide scene，含 text+latex 元素，1 speech + 1 spotlight 指向存在元素，audioUrl 为 edu_ai 地址）。
- 预期：校验通过，落库成功，`classroom_scenes` 行数=scene 数。

**T-02-B 反例逐条（AC-02-2~6）**
| 反例夹具 | 预期 |
| --- | --- |
| 两个 element 同 id | 拒绝，错误指明重复 id |
| slide 无 viewportRatio | 拒绝，指明缺字段 |
| spotlight.elementId 指向不存在元素 | 拒绝，指明空指 elementId |
| play_video.elementId 指向 text 元素 | 拒绝，指明类型不符 |
| speech.audioUrl = `http://openmaic-sidecar:3000/tmp/...` | 拒绝，指明未改写 |

每个反例断言：`VALIDATION_FAILED` + 未写库 + 原始 JSON 被保留（可取出排查）。

**T-02-C round-trip（AC-02-8）**
- 落库 → 取出 → 交给前端 renderer 渲染（或前端软校验函数）→ 断言元素数、id、几何一致。

**T-02-D 编辑幂等（AC-02-9）**
- 改一页 text 内容后重新 upsert → 断言 `scene.id/element.id` 不变、行未重复。

### 3.2 契约漂移检查
- CI 加一步：从 `@openmaic/dsl` 源码抽 `ActionType` / `PPTElement` 成员，与 edu_ai 校验器里引用的类型清单比对，**新增成员时告警**（提示复核校验规则），防止上游演进后校验失配。

---

## 4. 回归 / 边界

| 用例 | 预期 |
| --- | --- |
| quiz/interactive/pbl 场景 | 原样透传落库，不因未知 type 报错 |
| 无 actions 的纯 slide | 合法，通过 |
| 超大 Stage（几十 scene）| 落库/取出性能可接受（记录耗时基线）|

---

## 5. 签收

| 项 | 内容 |
| --- | --- |
| 验收人 / 日期 | |
| 结论 | |
| 遗留 | 依赖 Phase 2 落库链路就绪后执行 |
