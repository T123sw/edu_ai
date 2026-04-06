import assert from 'node:assert/strict';

import { restoreGeneratedFilesFromConversationDetail } from '../../src/services/teacher/chatV2.helpers.ts';

const restored = restoreGeneratedFilesFromConversationDetail({
  conversation_id: 'conv-1',
  history: [],
  message_count: 0,
  state: {
    workflow_state: {
      artifacts: [
        {
          artifact_id: 'outline-1',
          artifact_type: 'report_outline',
          title: '报告大纲.md',
          content: [
            {
              chapter_id: 1,
              chapter_title: '课堂现状',
              sections: [{ section_id: '1.1', title: '纪律问题' }],
            },
          ],
        },
        {
          artifact_id: 'report-1',
          artifact_type: 'report',
          title: '课堂分析报告.md',
          content: '# 正文\n\n这里是报告正文。',
        },
      ],
    },
  },
} as any);

assert.equal(restored.length, 1);
assert.equal(restored[0].id, 'report-1');
assert.equal(restored[0].meta?.conversationId, 'conv-1');
assert.equal(restored[0].meta?.kind, 'final_report');
assert.match(String(restored[0].meta?.outlineContent), /课堂现状/);

const emptyRestore = restoreGeneratedFilesFromConversationDetail({
  conversation_id: 'conv-2',
  history: [],
  message_count: 0,
} as any);

assert.deepEqual(emptyRestore, []);

console.log('generatedFiles.restore tests passed');
