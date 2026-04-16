import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(file, /currentQuizIndex/, 'Quiz preview should keep a current question index for card-style navigation');
assert.match(file, /const currentQuestion = questions\[safeQuizIndex\]/, 'Quiz preview should render one current question instead of the whole list');
assert.doesNotMatch(file, /questions\.map\(\(q,\s*idx\)/, 'Quiz preview should not render all questions as a vertical list');
assert.match(file, /isCurrentJudgeQuestion/, 'Quiz preview should detect judge questions explicitly');
assert.match(file, /value="正确"/, 'Judge questions should expose a 正确 radio option');
assert.match(file, /value="错误"/, 'Judge questions should expose a 错误 radio option');
assert.match(file, />\s*上一题\s*</, 'Quiz card preview should provide previous-question navigation');
assert.match(file, />\s*下一题\s*</, 'Quiz card preview should provide next-question navigation');

console.log('studioPanel.quiz-card-preview tests passed');
