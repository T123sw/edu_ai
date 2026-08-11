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
      phase: 'ready',
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
  assert.match(source, /classroom-console__workspace[\s\S]*<ClassroomQaPanel/);
  assert.doesNotMatch(source, /讲解提词|secondaryPanel === "transcript"/);
});

test('the QA panel is a persistent non-dialog rail with optimistic messages', () => {
  const sourcePath = fileURLToPath(new URL('./ClassroomQaPanel.tsx', import.meta.url));
  const source = readFileSync(sourcePath, 'utf8');

  assert.match(source, /selectVisibleTurns/);
  assert.match(source, /aria-label="课堂实时问答"/);
  assert.match(source, /classroom-qa-turn__question/);
  assert.match(source, /classroom-qa-turn__answer/);
  assert.doesNotMatch(source, /role="dialog"|classroom-qa-entry|关闭问答面板/);
});

test('the persistent rail uses document flow on narrow screens', () => {
  const cssPath = fileURLToPath(
    new URL('./ClassroomQaPanel.css', import.meta.url),
  );
  const css = readFileSync(cssPath, 'utf8');

  assert.doesNotMatch(css, /\.classroom-qa-panel\s*\{[^}]*(?:position:\s*(?:fixed|absolute)|bottom:)/s);
  assert.match(css, /classroom-qa-turn__question[^}]*justify-content:\s*flex-end/s);
  assert.match(css, /@media \(max-width:\s*960px\)[\s\S]*classroom-qa-panel/s);
});
