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
      version: {
        version_id: 'v2',
        version_number: 2,
        parent_artifact_id: 'report-0',
        root_artifact_id: 'report-root',
      },
      generation_state: {
        generation_mode: 'revise_report',
      },
      content: '# 正文\n\n这是报告正文。',
    },
  ],
});

assert.equal(files.length, 1);
assert.equal(files[0].id, 'report-1');
assert.equal(files[0].name, '报告.md');
assert.equal(files[0].meta?.kind, 'final_report');
assert.match(String(files[0].content), /报告正文/);
assert.match(String(files[0].meta?.outlineContent), /问题界定/);
assert.equal(files[0].meta?.versionId, 'v2');
assert.equal(files[0].meta?.versionNumber, 2);
assert.equal(files[0].meta?.parentArtifactId, 'report-0');
assert.equal((files[0].meta?.generationState as any)?.generation_mode, 'revise_report');

const outlineOnlyFiles = extractGeneratedFilesFromV2Response({
  action: { name: 'generate.report' },
  artifacts: [
    {
      artifact_id: 'outline-only',
      artifact_type: 'report_outline',
      content: [
        {
          chapter_id: 1,
          chapter_title: '课堂观察',
          sections: [{ section_id: '1.1', title: '学生参与' }],
        },
      ],
    },
  ],
});

assert.equal(outlineOnlyFiles.length, 1);
assert.equal(outlineOnlyFiles[0].meta?.kind, 'outline');
assert.match(String(outlineOnlyFiles[0].content), /课堂观察/);

const titledFromMarkdown = extractGeneratedFilesFromV2Response({
  action: { name: 'generate.report' },
  artifacts: [
    {
      artifact_id: 'report-2',
      artifact_type: 'report',
      content: '# 高一物理课堂观察报告\n\n正文内容。',
    },
  ],
});

assert.equal(titledFromMarkdown.length, 1);
assert.equal(titledFromMarkdown[0].name, '高一物理课堂观察报告.md');

const titledFromLowInfoArtifact = extractGeneratedFilesFromV2Response({
  action: { name: 'generate.report' },
  artifacts: [
    {
      artifact_id: 'report-3',
      artifact_type: 'report',
      title: '报告.md',
      content: '# 高一物理课堂观察报告\n\n正文内容。',
    },
  ],
});

assert.equal(titledFromLowInfoArtifact.length, 1);
assert.equal(titledFromLowInfoArtifact[0].name, '高一物理课堂观察报告.md');

const titledFromSecondaryHeading = extractGeneratedFilesFromV2Response({
  action: { name: 'generate.report' },
  artifacts: [
    {
      artifact_id: 'report-4',
      artifact_type: 'report',
      title: '报告.md',
      content: '**摘要**：这是一段摘要。\n\n## 狂放不羁与理想主义：李白性格的多维解析\n\n正文内容。',
    },
  ],
});

assert.equal(titledFromSecondaryHeading.length, 1);
assert.equal(titledFromSecondaryHeading[0].name, '狂放不羁与理想主义：李白性格的多维解析.md');

const sanitizedArtifactId = extractGeneratedFilesFromV2Response({
  action: { name: 'generate.report' },
  artifacts: [
    {
      artifact_id: 'conv-887d71fab7b1:content',
      artifact_type: 'report',
      content: '# 高一物理课堂观察报告\n\n正文内容。',
    },
  ],
});

assert.equal(sanitizedArtifactId.length, 1);
assert.equal(sanitizedArtifactId[0].id, 'conv-887d71fab7b1__content');

console.log('chatV2.helpers tests passed');
