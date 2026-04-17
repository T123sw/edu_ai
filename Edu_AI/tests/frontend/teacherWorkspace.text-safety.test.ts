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
  '\u5173\u7fbd\u7684\u6218\u7ee9',
  'decodeDisplayText should decode URL-encoded Chinese file names for display',
);

assert.equal(
  decodeDisplayText('50% \u8fdb\u5ea6'),
  '50% \u8fdb\u5ea6',
  'decodeDisplayText should leave plain text unchanged when it is not URL encoded',
);

assert.match(
  chatPanelFile,
  /message\.success\('\u5df2\u65b0\u5efa\u5bf9\u8bdd'\)/,
  'ChatPanel should show a readable success message when a new conversation starts',
);

assert.match(
  chatPanelFile,
  /message\.success\('\u5386\u53f2\u5bf9\u8bdd\u5df2\u5220\u9664'\)/,
  'ChatPanel should show a readable success message after deleting a conversation',
);

assert.match(
  chatPanelFile,
  /\u5f00\u59cb\u8f93\u5165\u95ee\u9898\u2026\uff08Shift \+ Enter \u6362\u884c\uff09/,
  'ChatPanel should render readable composer placeholder copy',
);

assert.doesNotMatch(
  chatPanelFile,
  /\?\?\?\?\?|\?\?\?\?\?\?\?|\?\?\?\?\?\?\?\?\?|\?\?\?\?\?\?\?\?\?\?\?/,
  'ChatPanel should not contain placeholder question-mark copy',
);

assert.match(
  sourcePanelFile,
  /decodeDisplayText\(doc\.file_name\)/,
  'SourcePanel should decode stored file names before rendering them',
);

assert.match(
  sourcePanelFile,
  /\u4e0a\u4f20\u6587\u6863\/\u56fe\u7247\/\u89c6\u9891/,
  'SourcePanel should keep the upload call-to-action readable',
);

assert.match(
  sourcePanelFile,
  /\u8d44\u6599\u5217\u8868/,
  'SourcePanel should keep the document-list section label readable',
);

assert.doesNotMatch(
  sourcePanelFile,
  /\u8d44\u6599\u5de5\u4f5c\u53f0/,
  'SourcePanel should not keep the extra materials-workbench eyebrow copy',
);

assert.match(
  aiStudioPageFile,
  /\u5f53\u524d\u8bfe\u7a0b/,
  'AiStudioPage should keep the current-course label readable',
);

assert.match(
  aiStudioPageFile,
  /\u5f53\u524d\u77e5\u8bc6\u70b9/,
  'AiStudioPage should keep the current-knowledge-point label readable',
);

console.log('teacherWorkspace.text-safety tests passed');
