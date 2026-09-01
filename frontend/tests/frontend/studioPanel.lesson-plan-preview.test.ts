import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');
const preview = readFileSync(new URL('../../src/components/teacher/LessonPlanArtifactPreview.tsx', import.meta.url), 'utf8');
const previewCss = readFileSync(new URL('../../src/components/teacher/LessonPlanArtifactPreview.css', import.meta.url), 'utf8');

assert.match(
  studioPanel,
  /import\s+LessonPlanArtifactPreview\s+from\s+['"]\.\/LessonPlanArtifactPreview['"]/,
  'StudioPanel should use the structured lesson plan artifact preview component',
);

assert.match(
  studioPanel,
  /<LessonPlanArtifactPreview[\s\S]*kind=\{lessonPlanKind\}[\s\S]*onContinueFromOutline=/,
  'Lesson plan artifacts should render through the structured preview surface',
);

assert.match(
  preview,
  /function\s+normalizeLessonPlanContent\(/,
  'Lesson plan preview should normalize raw generated content before rendering',
);

assert.match(preview, /teaching_objectives/, 'Lesson plan preview should read outline teaching objectives');
assert.match(preview, /key_and_hard_points/, 'Lesson plan preview should read outline key and hard points');
assert.match(preview, /teaching_support/, 'Lesson plan preview should read teaching support metadata');
assert.match(preview, /teacherActivities/, 'Lesson plan preview should read final teacher activities');
assert.match(preview, /studentActivities/, 'Lesson plan preview should read final student activities');
assert.match(preview, /当前预览的是教案大纲/, 'Lesson plan outline preview should explain that the file is still an outline');
assert.match(preview, /本课目标/, 'Lesson plan preview should expose lesson objectives as a clear section');
assert.match(preview, /重点与难点/, 'Lesson plan preview should group key and hard points');
assert.match(preview, /课堂过程/, 'Lesson plan preview should expose a clear classroom process section');
assert.match(preview, /教学支持/, 'Lesson plan preview should surface teaching support metadata');
assert.match(preview, /课后安排/, 'Lesson plan preview should expose homework or after-class tasks');
assert.match(preview, /继续生成教案/, 'Lesson plan outline preview should keep the continue-generation action');

assert.match(
  previewCss,
  /\.lesson-plan-artifact-preview__document/,
  'Lesson plan preview should use a document-style reading layout',
);

assert.match(
  previewCss,
  /\.lesson-plan-artifact-preview__timeline/,
  'Lesson plan preview should render process steps as a clear timeline',
);

console.log('studioPanel.lesson-plan-preview tests passed');
