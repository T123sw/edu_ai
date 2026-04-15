import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');
const lessonPlanEntryModal = readFileSync(new URL('../../src/components/teacher/LessonPlanEntryModal.tsx', import.meta.url), 'utf8');

assert.match(studioPanel, /import\s+LessonPlanEntryModal\s+from\s+['"]\.\/LessonPlanEntryModal['"]/, 'StudioPanel should use the dedicated lesson plan entry modal');
assert.match(studioPanel, /if\s*\(type\s*===\s*'lesson_plan'\)\s*\{[\s\S]*setLessonPlanEntryVisible\(true\)/, 'StudioPanel should open the lesson plan entry modal for lesson plan generation');
assert.match(studioPanel, /sendChatReplyV2\(/, 'StudioPanel should submit explicit lesson plan generation through chat v2 reply');
assert.match(studioPanel, /action_hint:\s*'generate\.lesson_plan'/, 'StudioPanel should force the lesson plan workflow when starting from the explicit entry');
assert.doesNotMatch(studioPanel, /const response = await generateLessonPlan\(/, 'StudioPanel should no longer call the legacy lesson plan API from the workbench entry');
assert.match(studioPanel, /<LessonPlanEntryModal/, 'StudioPanel should render the lesson plan entry modal');

assert.match(lessonPlanEntryModal, /fetchLessonPlanEntryCardsV2\(/, 'LessonPlanEntryModal should load lesson plan entry cards from the backend');
assert.match(lessonPlanEntryModal, /entryState === 'editing_config'/, 'LessonPlanEntryModal should support the config editing state');
assert.match(lessonPlanEntryModal, /生成大纲/, 'LessonPlanEntryModal should guide the user into outline generation first');

console.log('studioPanel.lesson-plan-entry tests passed');
