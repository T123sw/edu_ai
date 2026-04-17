import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');
const preview = readFileSync(new URL('../../src/components/teacher/QuizArtifactPreview.tsx', import.meta.url), 'utf8');
const previewCss = readFileSync(new URL('../../src/components/teacher/QuizArtifactPreview.css', import.meta.url), 'utf8');

assert.match(studioPanel, /currentQuizIndex/, 'Quiz preview should keep a current question index for card-style navigation');
assert.match(studioPanel, /import\s+QuizArtifactPreview\s+from\s+['"]\.\/QuizArtifactPreview['"]/, 'StudioPanel should use the dedicated quiz artifact preview component');
assert.match(studioPanel, /<QuizArtifactPreview[\s\S]*onAnswerChange=\{handleAutoAnswer\}[\s\S]*onSubmitCurrent=\{handleSubmitCurrent\}/, 'StudioPanel should route quiz interaction through the new preview component');
assert.match(studioPanel, /setQuizChecked\(\(prev\) => \(\{ \.\.\.prev, \[currentQuestionId\]: Boolean\(autoCheck\) \}\)\)/, 'Choice and judge questions should be able to auto-check on click');
assert.match(preview, /onAnswerChange\(option,\s*true\)/, 'Choice questions should auto-submit when an option is clicked');
assert.match(preview, /onAnswerChange\(value,\s*true\)/, 'Judge questions should auto-submit when an option is clicked');
assert.match(preview, /提交并判题/, 'Subjective questions should still keep an explicit submit button');
assert.match(preview, /typeLabel\(currentQuestionType\)/, 'Quiz preview should show an explicit type label');
assert.match(preview, /重做本测验/, 'Quiz preview should keep a reset action');
assert.match(preview, /一键查看答案/, 'Quiz preview should keep a check-all action');
assert.match(preview, /上一题/, 'Quiz preview should provide previous-question navigation');
assert.match(preview, /下一题/, 'Quiz preview should provide next-question navigation');
assert.match(previewCss, /\.quiz-artifact-preview__option--correct/, 'Quiz preview should style correct answers distinctly');
assert.match(previewCss, /\.quiz-artifact-preview__option--wrong/, 'Quiz preview should style wrong answers distinctly');
assert.match(previewCss, /\.quiz-artifact-preview__pager-item--checked/, 'Quiz preview should show checked state in the pager');

console.log('studioPanel.quiz-card-preview tests passed');
