# PPT Outline Prompt Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 强化 PPT 的“对话上下文整理 -> 信息充分性判断 -> 逐页大纲生成”链路，让中文教学场景下的大纲更稳定、更具体、更少重复。

**Architecture:** 保留现有 `PptPreparationResult -> PptReadinessJudge -> PptOutlineBuilder` 三层结构，但把 prompt 和 fallback 文案全面中文化，并把质量约束前移到 organizer 与 outline builder。readiness judge 负责少次追问和合理假设，不再仅做最低可运行判断。

**Tech Stack:** Python, Pydantic, pytest

---

### Task 1: 中文化并强化 preparation/readiness/outline 测试

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_context_organizer.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_readiness_judge.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py`

- [ ] 把乱码样例和断言替换为真实中文业务样例
- [ ] 为 organizer 增加“能提炼教学对象/目标/重点/来源”的断言
- [ ] 为 readiness judge 增加“质量不足仍追问、信息基本充分则允许带假设生成”的断言
- [ ] 为 outline builder 增加“逐页结构、章节拆分、避免重复、中文教学语境 prompt 约束”的断言

### Task 2: 重写 PptContextOrganizer

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\ppt_context_organizer.py`

- [ ] 清理低信号词、追问文案和 LLM prompt 中的乱码
- [ ] 把 prompt 从“抽槽位”升级为“抽取 + 归纳 + 课件策展”
- [ ] 让 organizer 除 topic/audience/objective/key_points 外，也能优先组织 source_basis、style、theme、page_count
- [ ] 让 fallback 路径也返回可读中文文案

### Task 3: 强化 PptReadinessJudge

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\readiness_judge.py`

- [ ] 清理 assumptions 和 question 文案里的乱码
- [ ] 把判定从“最低可运行”提升为“足够稳定地产出逐页大纲”
- [ ] 保持“最多少次追问，不把用户逼成填表”的产品约束

### Task 4: 重写 PptOutlineBuilder

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\outline_builder.py`

- [ ] 把 LLM prompt 改成中文主导，明确章节划分、页级角色、每页目标、避免重复、教学节奏
- [ ] 清理 fallback 里的乱码
- [ ] 让 fallback 结构不再只是“目录 + 平铺 content 页”，而是更像可讲授的大纲
- [ ] 保持 theme_id 归一化逻辑

### Task 5: 定向回归

**Files:**
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_context_organizer.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_readiness_judge.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py`

- [ ] 先跑 organizer/readiness/outline 三组测试
- [ ] 再跑 runtime 回归，确认主链没有被 prompt 重构带坏
- [ ] 只根据最新命令输出汇报结果
