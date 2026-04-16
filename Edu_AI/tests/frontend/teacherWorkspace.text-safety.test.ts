import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { decodeDisplayText } from '../../src/services/teacher/displayText.helpers.ts';

const chatPanelFile = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

const sourcePanelFile = readFileSync(
  new URL('../../src/components/teacher/SourcePanel.tsx', import.meta.url),
  'utf8',
);

const aiStudioPageFile = readFileSync(
  new URL('../../src/pages/teacher/AiStudioPage.tsx', import.meta.url),
  'utf8',
);

assert.equal(
  decodeDisplayText('%E5%85%B3%E7%BE%BD%E7%9A%84%E6%88%98%E7%BB%A9'),
  '关羽的战绩',
  'decodeDisplayText should decode URL-encoded Chinese file names for display',
);

assert.equal(
  decodeDisplayText('50% 进度'),
  '50% 进度',
  'decodeDisplayText should leave plain text unchanged when it is not URL encoded',
);

assert.match(
  chatPanelFile,
  /message\.success\('已新建对话'\)/,
  'ChatPanel should show a readable success message when a new conversation starts',
);

assert.match(
  chatPanelFile,
  /message\.success\('历史对话已删除'\)/,
  'ChatPanel should show a readable success message after deleting a conversation',
);

assert.match(
  chatPanelFile,
  /message\.success\('语音已转换为文本'\)/,
  'ChatPanel should show a readable success message after speech transcription',
);

assert.match(
  chatPanelFile,
  /placeholder=\{isTranscribing \? '正在识别语音\.\.\.' : '开始输入问题…（Shift \+ Enter 换行）'\}/,
  'ChatPanel should render readable composer placeholder copy',
);

assert.doesNotMatch(
  chatPanelFile,
  /\?\?\?\?\?|\?\?\?\?\?\?\?|\?\?\?\?\?\?\?\?\?|\?\?\?\?\?\?\?\?\?\?\?/,
  'ChatPanel should not contain placeholder question-mark copy',
);

assert.doesNotMatch(
  chatPanelFile,
  /鍔犺浇|鍘嗗彶瀵硅瘽|鏂板缓瀵硅瘽|璇煶|涓婁紶鍥剧墖|姝ｅ湪璇嗗埆/,
  'ChatPanel should not contain mojibake copy in user-facing labels',
);

assert.match(
  sourcePanelFile,
  /decodeDisplayText\(doc\.file_name\)/,
  'SourcePanel should decode stored file names before rendering them',
);

assert.match(
  sourcePanelFile,
  /上传文档\/图片\/视频/,
  'SourcePanel should keep the upload call-to-action readable',
);

assert.match(
  sourcePanelFile,
  /资料列表/,
  'SourcePanel should keep the document-list section label readable',
);

assert.match(
  sourcePanelFile,
  /上传资料/,
  'SourcePanel should keep the upload section label readable',
);

assert.match(
  aiStudioPageFile,
  /当前课程/,
  'AiStudioPage should keep the current-course label readable',
);

assert.match(
  aiStudioPageFile,
  /当前知识点/,
  'AiStudioPage should keep the current-knowledge-point label readable',
);

console.log('teacherWorkspace.text-safety tests passed');
