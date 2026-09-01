import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const modal = readFileSync(new URL('../../src/components/teacher/QuizEntryModal.tsx', import.meta.url), 'utf8');
const panel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(modal, /fetchQuizEntryPrefillV2/, 'Quiz entry modal should fetch topic and hard-point prefills from selected documents');
assert.match(modal, /mode="multiple"/, 'Quiz entry modal should allow selecting multiple question types');
assert.match(modal, /name="question_types"/, 'Quiz entry modal should expose a multi-select question type field');
assert.match(modal, /name="hard_points"/, 'Quiz entry modal should expose hard-point configuration');
assert.match(modal, /include_answers/, 'Quiz entry modal should expose answer inclusion toggles');

assert.match(panel, /setQuizEntryVisible\(true\)/, 'StudioPanel should open the dedicated quiz entry modal');
assert.match(panel, /generateKnowledgeBaseQuizV2/, 'StudioPanel should submit quiz generation through the direct quiz V2 endpoint');

console.log('quizEntryModal tests passed');
