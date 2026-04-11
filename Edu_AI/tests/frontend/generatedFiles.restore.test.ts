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

const restoredPpt = restoreGeneratedFilesFromConversationDetail({
  conversation_id: 'conv-ppt-1',
  history: [],
  message_count: 0,
  state: {
    workflow_state: {
      artifacts: [
        {
          artifact_id: 'ppt-outline-1',
          artifact_type: 'ppt_outline',
          title: 'TCP 三次握手课件-大纲',
          content: {
            deck_title: 'TCP 三次握手课件',
            slides: [
              { slide_index: 1, title: '封面', role: 'cover' },
              { slide_index: 2, title: '三次握手过程', role: 'content' },
            ],
          },
        },
        {
          artifact_id: 'ppt-deck-1',
          artifact_type: 'ppt_deck',
          title: 'TCP 三次握手课件.pptx',
          content: {
            job_id: 'job_001',
            revision_id: 'rev_0000',
            html_full_url: '/ppt/artifacts/job_001/rev_0000/deck.html',
            pptx_url: '/ppt/artifacts/job_001/rev_0000/deck.pptx',
          },
        },
      ],
    },
  },
} as any);

assert.equal(restoredPpt.length, 1);
assert.equal(restoredPpt[0].type, 'ppt');
assert.equal(restoredPpt[0].meta?.conversationId, 'conv-ppt-1');
assert.equal(restoredPpt[0].meta?.kind, 'ppt_deck');
assert.equal(restoredPpt[0].meta?.htmlPreviewUrl, 'http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0000/deck.html');
assert.equal(restoredPpt[0].meta?.pptxUrl, 'http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0000/deck.pptx');
assert.match(String(restoredPpt[0].meta?.outlineContent), /三次握手过程/);

const emptyRestore = restoreGeneratedFilesFromConversationDetail({
  conversation_id: 'conv-2',
  history: [],
  message_count: 0,
} as any);

assert.deepEqual(emptyRestore, []);

console.log('generatedFiles.restore tests passed');
