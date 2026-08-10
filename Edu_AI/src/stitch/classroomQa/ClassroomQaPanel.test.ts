import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { INITIAL_CLASSROOM_QA_STATE } from './classroomQaState.ts';
import { toClassroomQaPresentation } from './classroomQaPresentation.ts';

test('submitting and answering phases disable the composer', () => {
  assert.equal(
    toClassroomQaPresentation({
      ...INITIAL_CLASSROOM_QA_STATE,
      phase: 'submitting',
    }).canSubmit,
    false,
  );
  assert.equal(
    toClassroomQaPresentation({
      ...INITIAL_CLASSROOM_QA_STATE,
      phase: 'playing_answer',
    }).canSubmit,
    false,
  );
  assert.equal(
    toClassroomQaPresentation({
      ...INITIAL_CLASSROOM_QA_STATE,
      phase: 'drafting',
    }).canSubmit,
    true,
  );
});

test('presentation labels expose stable live status text', () => {
  assert.match(
    toClassroomQaPresentation({
      ...INITIAL_CLASSROOM_QA_STATE,
      phase: 'loading_audio',
    }).statusText,
    /语音/,
  );
  assert.equal(
    toClassroomQaPresentation({
      ...INITIAL_CLASSROOM_QA_STATE,
      phase: 'error',
      error: '网络失败',
    }).statusText,
    '网络失败',
  );
});

test('ClassroomPlayer binds the runtime and always renders the QA panel', () => {
  const sourcePath = fileURLToPath(
    new URL('../pages/ClassroomPlayer.tsx', import.meta.url),
  );
  const source = readFileSync(sourcePath, 'utf8');

  assert.match(source, /<ClassroomQaPanel/);
  assert.match(source, /onRuntimeReady=/);
  assert.match(source, /controller\.bindRuntime/);
  assert.doesNotMatch(source, /!presentationMode\s*\?\s*\(\s*<ClassroomQaPanel/);
});
