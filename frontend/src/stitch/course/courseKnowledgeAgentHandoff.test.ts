import assert from "node:assert/strict";
import test from "node:test";

import { buildNewCourseKnowledgeAgentPrompt } from "./courseKnowledgeAgentHandoff";


test("new course handoff includes authoritative course fields and review boundary", () => {
  const prompt = buildNewCourseKnowledgeAgentPrompt({
    id: "course-1",
    title: "算法设计",
    description: "面向大二学生的算法课程",
    icon: "school",
    color: "#3366ff",
    objectives: ["掌握复杂度分析", "能设计经典算法"],
    audience: "计算机专业大二学生",
    language: "zh-CN",
    difficulty: "intermediate",
    revision: 1,
    membership_role: "owner",
  }, "共 8 课时；优先 Linux Kernel 官方文档；每章 1 个案例和 3 道带解析练习。");

  assert.match(prompt, /课程知识库/);
  assert.match(prompt, /算法设计/);
  assert.match(prompt, /计算机专业大二学生/);
  assert.match(prompt, /掌握复杂度分析/);
  assert.match(prompt, /先生成可审核方案/);
  assert.match(prompt, /不要直接发布/);
  assert.match(prompt, /优先 Linux Kernel 官方文档/);
  assert.match(prompt, /3 道带解析练习/);
});


test("new course handoff omits empty optional metadata without placeholders", () => {
  const prompt = buildNewCourseKnowledgeAgentPrompt({
    id: "course-2",
    title: "离散数学",
    description: "",
    icon: "school",
    color: "#3366ff",
    revision: 1,
    membership_role: "owner",
  });

  assert.doesNotMatch(prompt, /undefined|null/);
  assert.match(prompt, /课程名称：离散数学/);
});
