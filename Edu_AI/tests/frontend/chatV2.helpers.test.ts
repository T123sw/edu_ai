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

const pptDeckFiles = extractGeneratedFilesFromV2Response({
  action: { name: 'generate.ppt' },
  artifacts: [
    {
      artifact_id: 'conv-ppt:outline',
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
      artifact_id: 'conv-ppt:deck:job_001',
      artifact_type: 'ppt_deck',
      title: 'TCP 三次握手课件.pptx',
      content: {
        job_id: 'job_001',
        revision_id: 'rev_0000',
        html_full_url: '/ppt/artifacts/job_001/rev_0000/deck.html',
        pptx_url: '/ppt/artifacts/job_001/rev_0000/deck.pptx',
        manifest_url: '/ppt/artifacts/job_001/rev_0000/manifest.json',
      },
    },
  ],
});

assert.equal(pptDeckFiles.length, 1);
assert.equal(pptDeckFiles[0].id, 'conv-ppt__deck__job_001');
assert.equal(pptDeckFiles[0].type, 'ppt');
assert.equal(pptDeckFiles[0].name, 'TCP 三次握手课件.pptx');
assert.equal(pptDeckFiles[0].meta?.kind, 'ppt_deck');
assert.equal(pptDeckFiles[0].meta?.htmlPreviewUrl, 'http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0000/deck.html');
assert.equal(pptDeckFiles[0].meta?.pptxUrl, 'http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0000/deck.pptx');
assert.match(String(pptDeckFiles[0].meta?.outlineContent), /三次握手过程/);

const lessonPlanOutlineFiles = extractGeneratedFilesFromV2Response({
  action: { name: 'generate.lesson_plan' },
  artifacts: [
    {
      artifact_id: 'lesson-plan:outline',
      artifact_type: 'lesson_plan_outline',
      title: '关羽人物分析-教案大纲.json',
      content: {
        basic_info: {
          topic: '关羽的战绩与形象分析',
          audience: '初中历史/语文',
          duration: '45分钟',
          lesson_type: '新授课',
        },
        teaching_objectives: ['梳理关羽主要战役与文学形象'],
        key_and_hard_points: {
          key_points: ['历史事实与文学塑造的区别'],
          hard_points: ['辩证理解历史人物复杂性'],
          breakthrough_strategy: '通过史料对比引导学生分析',
        },
        lesson_flow: [
          {
            step: '导入',
            goal: '激活已有认知',
            duration: '5分钟',
            teacher_activities: ['展示关羽形象图片'],
            student_activities: ['分享已有印象'],
            assessment: '口头回答',
          },
        ],
        teaching_support: {
          teaching_methods: ['讲授', '讨论'],
          teaching_aids: ['课件'],
          board_plan: ['关羽生平', '战绩', '形象'],
          assessment_method: '课堂提问',
          homework_preview: '整理人物评价短文',
        },
      },
    },
  ],
});

assert.equal(lessonPlanOutlineFiles.length, 1);
assert.equal(lessonPlanOutlineFiles[0].id, 'lesson-plan__outline');
assert.equal(lessonPlanOutlineFiles[0].type, 'lesson_plan');
assert.equal(lessonPlanOutlineFiles[0].name, '关羽人物分析-教案大纲.json');
assert.equal(lessonPlanOutlineFiles[0].meta?.kind, 'outline');
assert.equal((lessonPlanOutlineFiles[0].content as any)?.basic_info?.topic, '关羽的战绩与形象分析');

const lessonPlanFiles = extractGeneratedFilesFromV2Response({
  action: { name: 'generate.lesson_plan' },
  artifacts: [
    {
      artifact_id: 'lesson-plan:outline',
      artifact_type: 'lesson_plan_outline',
      content: {
        basic_info: {
          topic: '关羽的战绩与形象分析',
        },
      },
    },
    {
      artifact_id: 'lesson-plan:content',
      artifact_type: 'lesson_plan',
      title: '关羽人物分析-教案.json',
      content: {
        title: '关羽人物专题教案',
        objectives: ['梳理关羽战绩'],
        keyPoints: ['区分历史与文学'],
        hardPoints: ['理解人物复杂性'],
        process: [
          {
            step: '导入',
            content: '展示关羽形象并导入主题',
            duration: '5分钟',
          },
        ],
        homework: '完成课后人物评价',
      },
    },
  ],
});

assert.equal(lessonPlanFiles.length, 1);
assert.equal(lessonPlanFiles[0].id, 'lesson-plan__content');
assert.equal(lessonPlanFiles[0].type, 'lesson_plan');
assert.equal(lessonPlanFiles[0].name, '关羽人物分析-教案.json');
assert.equal(lessonPlanFiles[0].meta?.kind, 'final_lesson_plan');
assert.equal((lessonPlanFiles[0].meta?.outlineContent as any)?.basic_info?.topic, '关羽的战绩与形象分析');

console.log('chatV2.helpers tests passed');
