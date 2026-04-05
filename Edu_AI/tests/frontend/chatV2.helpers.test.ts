import assert from 'node:assert/strict';

import {
  buildReportQuestionFromConfig,
  extractGeneratedFilesFromV2Response,
} from '../../src/services/teacher/chatV2.helpers.ts';

const question = buildReportQuestionFromConfig({
  title: '高一物理课堂观察报告',
  focus_areas: ['课堂纪律', '学生参与度'],
});

assert.match(question, /高一物理课堂观察报告/);
assert.match(question, /课堂纪律/);
assert.match(question, /学生参与度/);

const files = extractGeneratedFilesFromV2Response({
  action: { name: 'generate.report' },
  artifacts: [
    {
      artifact_id: 'outline-1',
      artifact_type: 'report_outline',
      content: [
        {
          chapter_id: 1,
          chapter_title: '问题界定',
          sections: [{ section_id: '1.1', title: '课堂纪律现状' }],
        },
      ],
    },
    {
      artifact_id: 'report-1',
      artifact_type: 'report',
      content: '# 正文\n\n这是报告正文。',
    },
  ],
});

assert.equal(files.length, 2);
assert.equal(files[0].meta?.kind, 'outline');
assert.match(String(files[0].content), /问题界定/);
assert.equal(files[1].meta?.kind, 'final_report');
assert.match(String(files[1].content), /报告正文/);

console.log('chatV2.helpers tests passed');
