import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync('d:/github/edu_ai/Edu_AI/src/components/teacher/StudioPanel.tsx', 'utf8');

assert.match(file, /key:\s*'add-to-chat'/, 'StudioPanel should expose an add-to-chat action');
assert.match(file, /label:\s*'添加到对话'/, 'add-to-chat action should have the expected label');
assert.match(file, /setArtifactReference\(/, 'StudioPanel should write artifact references into the store');

console.log('studioPanel.add-to-chat tests passed');
