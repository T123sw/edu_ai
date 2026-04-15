import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(file, /viewingFile\.type === 'lesson_plan'/, 'StudioPanel should render a dedicated lesson plan preview branch');
assert.match(file, /const lessonPlanKind = String\(\(viewingFile\.meta as any\)\?\.kind \|\| ''\)\.trim\(\);/, 'Lesson plan preview should read artifact kind metadata');
assert.match(file, /normalizeLessonPlanPreview\(viewingFile\.content,\s*lessonPlanKind\)/, 'Lesson plan preview should normalize outline and final payloads');
assert.match(file, /lessonPlanKind === 'outline'/, 'Lesson plan preview should detect outline artifacts');
assert.match(file, /当前预览的是教案大纲/, 'Lesson plan outline preview should explain that the file is still an outline');
assert.match(file, /教学支持/, 'Lesson plan preview should surface teaching-support metadata');
assert.match(file, />\s*继续生成教案\s*</, 'Lesson plan outline preview should expose a continue-generation button');
assert.match(file, /setQueuedMessage\('确认并继续'\)/, 'Lesson plan outline preview should queue the workflow confirmation phrase');
assert.match(file, /const finalProcess = Array\.isArray\(record\.process\)/, 'Lesson plan preview should normalize final lesson plan process data');
assert.match(file, /const teacherActivities = toTextList\(item\?\.teacherActivities\)/, 'Lesson plan preview should read final lesson plan teacher activities');
assert.match(file, /const studentActivities = toTextList\(item\?\.studentActivities\)/, 'Lesson plan preview should read final lesson plan student activities');
assert.match(file, /goal \? `目标：\$\{goal\}` : ''/, 'Lesson plan preview should compose final lesson plan goal text into process content');
assert.match(file, /assessment \? `评价方式：\$\{assessment\}` : ''/, 'Lesson plan preview should compose final lesson plan assessment text into process content');

console.log('studioPanel.lesson-plan-preview tests passed');
