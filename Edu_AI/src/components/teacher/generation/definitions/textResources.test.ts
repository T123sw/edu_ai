import assert from "node:assert/strict";
import test from "node:test";

import { blogDefinition, type BlogConfig } from "./blog";
import { lessonPlanDefinition, type LessonPlanConfig } from "./lessonPlan";
import { reportDefinition, type ReportConfig } from "./report";

const source = { mode: "none" as const, selectedDocumentIds: [] };

test("report fields map to the durable report command", () => {
  const config: ReportConfig = {
    template: "detailed",
    topic: "学习行为分析",
    audience: "教研组",
    depth: "deep",
    structureEmphasis: "先结论后证据",
    specialRequirements: "列出三项改进建议",
  };
  const payload = reportDefinition.serialize({ courseId: "course-1", source, config });
  assert.equal(payload.question, "学习行为分析");
  assert.deepEqual(payload.report_config, {
    template: "detailed",
    audience: "教研组",
    depth: "deep",
    structure_emphasis: "先结论后证据",
    special_requirements: "列出三项改进建议",
  });
});

test("lesson plan required fields and outline intent are serialized", () => {
  const config: LessonPlanConfig = {
    topic: "牛顿第二定律",
    audience: "本科一年级",
    durationMinutes: 45,
    objectives: ["解释合力与加速度的关系", "完成典型受力分析"],
    lessonType: "inquiry_lesson",
    teachingProcess: "问题导入—实验探究—归纳应用",
    specialRequirements: "保留五分钟课堂检测",
    outlinePreview: true,
  };
  const payload = lessonPlanDefinition.serialize({ courseId: "course-1", source, config });
  assert.equal(payload.duration_minutes, 45);
  assert.deepEqual(payload.objectives, config.objectives);
  assert.equal(payload.lesson_type, "inquiry_lesson");
  assert.equal(payload.teaching_process, config.teachingProcess);
  assert.equal(payload.outline_preview, true);
});

test("blog tone and length reach the durable command", () => {
  const config: BlogConfig = {
    topic: "量子隧穿",
    audience: "本科一年级",
    tone: "popular",
    length: "long",
    structure: "概念—例子—总结",
    specialRequirements: "加入一个生活类比",
  };
  const payload = blogDefinition.serialize({ courseId: "course-1", source, config });
  assert.equal(payload.tone, "popular");
  assert.equal(payload.length, "long");
  assert.equal(payload.special_requirements, "加入一个生活类比");
});

test("text definitions report field-specific validation errors", () => {
  assert.equal(reportDefinition.validate({ ...reportDefinition.defaultConfig(), topic: "" }).topic, "请输入报告主题");
  assert.equal(lessonPlanDefinition.validate({ ...lessonPlanDefinition.defaultConfig(), objectives: [] }).objectives, "至少填写一个教学目标");
  assert.equal(blogDefinition.validate({ ...blogDefinition.defaultConfig(), topic: "" }).topic, "请输入博客主题");
});
