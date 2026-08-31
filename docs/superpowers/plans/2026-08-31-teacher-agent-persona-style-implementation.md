# Teacher Agent Persona Style Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reposition the teacher Agent as a professional teaching-and-research collaborator whose answer depth is chosen naturally by the model rather than forced to be concise.

**Architecture:** Keep the existing `PersonaPolicy` boundary and update only the teacher persona wording plus the shared closing style phrase that currently reinforces brevity. Lock the new semantics in prompt tests while preserving QA/resource-generation isolation and leaving the student persona text unchanged.

**Tech Stack:** Python 3.12, dataclass persona policy, pytest.

---

## File Structure

- Modify `Edu_AI/api/src/app/chat/domain/persona_policy.py`: update the teacher role, collaboration style, and style metadata.
- Modify `Edu_AI/api/src/app/chat/runtime/nodes/prompts.py`: remove the shared instruction that forces concise expression.
- Modify `Edu_AI/api/src/tests/chat/runtime/test_agent_prompt_boundaries.py`: verify the teacher collaboration persona and absence of fixed length/template rules.
- Test `Edu_AI/api/src/tests/chat/test_fast_chat_runtime.py`: confirm the shared teacher persona still reaches the FastChat fallback.

### Task 1: Make Teacher Answers Professional, Collaborative, and Naturally Detailed

**Files:**
- Modify: `Edu_AI/api/src/app/chat/domain/persona_policy.py:17-41`
- Modify: `Edu_AI/api/src/app/chat/runtime/nodes/prompts.py:26-28`
- Modify: `Edu_AI/api/src/tests/chat/runtime/test_agent_prompt_boundaries.py`
- Test: `Edu_AI/api/src/tests/chat/test_fast_chat_runtime.py`

- [ ] **Step 1: Add failing prompt assertions**

Extend `test_agent_prompt_boundaries.py` with:

```python
def test_teacher_prompt_uses_collaborative_adaptive_answer_style():
    prompt = build_system_content(None, actor_role="teacher")

    assert "教研协作伙伴" in prompt
    assert "专业、清晰、自然、完整" in prompt
    assert "根据问题本身和上下文自行决定回答的详略" in prompt
    assert "不设置固定字数、段落数量或回答模板" in prompt
    assert "不刻意压缩必要的解释" in prompt
    assert "使用简洁、行动导向的表达" not in prompt


def test_student_prompt_keeps_guided_learning_persona():
    prompt = build_system_content(None, actor_role="student")

    assert "学生的引导式教学助手" in prompt
    assert "教研协作伙伴" not in prompt
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
$env:PYTHONPATH='D:\Edu_AI_1\Edu_AI\api\src'
python -m pytest src/tests/chat/runtime/test_agent_prompt_boundaries.py -q
```

Expected: the teacher-style test fails because the current prompt says `使用简洁、行动导向的表达` and does not contain the collaboration/adaptive-detail requirements.

- [ ] **Step 3: Update the teacher persona and style metadata**

Replace the teacher branch of `PersonaPolicy.system_instruction()` with:

```python
return (
    "你是教师的备课与教学资源助手，也是教师的教研协作伙伴。"
    "以同行、平等的方式交流，优先准确、充分地解决教师当前问题。"
    "回答应专业、清晰、自然、完整，根据问题本身和上下文自行决定回答的详略、结构、示例和技术深度；"
    "不设置固定字数、段落数量或回答模板，不刻意压缩必要的解释，也不为了显得详细而堆砌内容。"
    "必要时自然补充原理、实现思路、适用场景和关键注意点。"
    "不要把教师当学生说教，不要连续反问，不要给出无关的延伸学习任务，"
    "也不要展示内部推理。仅在一个会显著改变结果的关键信息缺失时追问一次。"
)
```

Update the teacher metadata:

```python
TEACHER_PERSONA = PersonaPolicy(
    actor_role="teacher",
    goal="teaching_research_collaboration",
    default_style="professional_collaborative_adaptive",
    clarification_budget=1,
    socratic_mode="off",
    avoid_basic_tutoring_tone=True,
)
```

- [ ] **Step 4: Remove the shared forced-brevity wording**

In `COMMON_AGENT_INSTRUCTIONS`, replace:

```python
仅在一个会显著改变结果的关键信息缺失时追问一次。表达自然简洁，不展示内部推理。
```

with:

```python
仅在一个会显著改变结果的关键信息缺失时追问一次。表达自然清晰，不展示内部推理。
```

- [ ] **Step 5: Run focused prompt and fallback tests**

Run:

```powershell
python -m pytest src/tests/chat/runtime/test_agent_prompt_boundaries.py src/tests/chat/test_fast_chat_runtime.py -q
```

Expected: all tests pass; the teacher persona is present in both Agent and FastChat prompts, and the student persona remains unchanged.

- [ ] **Step 6: Run the Agent runtime regression suite and compile check**

Run:

```powershell
python -m pytest src/tests/chat/runtime -q
python -m compileall -q src/app/chat/domain/persona_policy.py src/app/chat/runtime/nodes/prompts.py
git diff --check -- Edu_AI/api/src/app/chat/domain/persona_policy.py Edu_AI/api/src/app/chat/runtime/nodes/prompts.py Edu_AI/api/src/tests/chat/runtime/test_agent_prompt_boundaries.py
```

Expected: all commands exit with code 0.

- [ ] **Step 7: Commit the implementation**

```powershell
git add Edu_AI/api/src/app/chat/domain/persona_policy.py Edu_AI/api/src/app/chat/runtime/nodes/prompts.py Edu_AI/api/src/tests/chat/runtime/test_agent_prompt_boundaries.py
git commit -m "fix: refine teacher agent collaboration persona"
```
