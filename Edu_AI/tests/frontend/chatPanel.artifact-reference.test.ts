import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  type ChatArtifactReference,
  type ChatReplyRequestV2,
  buildChatReplyPayload,
} from '../../src/services/teacher/chatV2.ts';

const reference: ChatArtifactReference = {
  artifact_id: 'report-1',
  artifact_type: 'report',
  version_id: 'v1',
  title: '\u674e\u767d\u6027\u683c\u5206\u6790.md',
  source_conversation_id: 'conv-1',
  source_course_id: 'course-1',
};

const storeFile = readFileSync(new URL('../../src/store/teacher/useStore.ts', import.meta.url), 'utf8');
const chatPanelFile = readFileSync(new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url), 'utf8');

assert.match(storeFile, /artifactReference:\s*ArtifactReference \| null;/, 'store should expose artifactReference state');
assert.match(storeFile, /setArtifactReference:\s*\(reference:\s*ArtifactReference \| null\)\s*=>\s*void;/, 'store should expose setArtifactReference action');
assert.match(storeFile, /clearArtifactReference:\s*\(\)\s*=>\s*void;/, 'store should expose clearArtifactReference action');
assert.match(storeFile, /replaceConversationGeneratedFiles:\s*\(files:\s*GeneratedFile\[\]\)\s*=>\s*void;/, 'store should replace conversation-scoped generated files');
assert.match(storeFile, /clearConversationGeneratedFiles:\s*\(\)\s*=>\s*void;/, 'store should clear conversation-scoped generated files');

assert.match(chatPanelFile, /artifactReference,[\s\S]*setViewingFile\(generatedFiles\[generatedFiles\.length - 1\]\)/, 'ChatPanel should directly open the newest generated file after artifact-based modification');
assert.match(chatPanelFile, /const normalizeArtifactReferenceType = \(/, 'ChatPanel should normalize restored artifact reference types from conversation state');
assert.match(chatPanelFile, /artifact_type:\s*normalizeArtifactReferenceType\(/, 'ChatPanel should preserve ppt artifact references when restoring conversations');
assert.match(chatPanelFile, /artifactReference\?\.artifact_type === 'ppt_deck' && nextPptArtifact/, 'ChatPanel should refresh an active PPT reference to the newest returned deck');
assert.match(chatPanelFile, /artifactReference\.artifact_type === 'ppt_deck'[\s\S]*'PPT \u6587\u4ef6'/, 'ChatPanel should label active PPT deck references explicitly');
assert.match(
  chatPanelFile,
  /\u53ef\u76f4\u63a5\u56f4\u7ed5\u8fd9\u4e2a\u6587\u4ef6\u63d0\u95ee\uff0c\u4e5f\u53ef\u4ee5\u8bf4\u201c\u4fee\u6539\u7b2c 3 \u9875\u201d\u6216\u201c\u91cd\u5199\u7ed3\u8bba\u201d/,
  'ChatPanel should show a hint explaining how to ask about or edit a referenced artifact',
);

const payload = buildChatReplyPayload({
  question: '\u4fdd\u7559\u7ed3\u6784\uff0c\u91cd\u5199\u7ed3\u8bba',
  conversationId: 'conv-1',
  courseId: 'course-1',
  allowRag: false,
  allowWeb: false,
  selectedDocIds: ['doc-1'],
  artifactReference: reference,
});

assert.deepEqual(payload, {
  question: '\u4fdd\u7559\u7ed3\u6784\uff0c\u91cd\u5199\u7ed3\u8bba',
  conversation_id: 'conv-1',
  course_id: 'course-1',
  allow_rag: false,
  allow_web: false,
  selected_doc_ids: ['doc-1'],
  artifact_reference: {
    artifact_id: 'report-1',
    artifact_type: 'report',
    version_id: 'v1',
    title: '\u674e\u767d\u6027\u683c\u5206\u6790.md',
    source_conversation_id: 'conv-1',
    source_course_id: 'course-1',
  },
} satisfies ChatReplyRequestV2);

const payloadWithoutReference = buildChatReplyPayload({
  question: '\u666e\u901a\u8ffd\u95ee',
  conversationId: 'conv-1',
  courseId: 'course-1',
  allowRag: true,
  allowWeb: false,
  selectedDocIds: [],
  artifactReference: null,
});

assert.ok(!('artifact_reference' in payloadWithoutReference));

const pptPayload = buildChatReplyPayload({
  question: '\u628a\u7b2c 3 \u9875\u6539\u6210\u6d41\u7a0b\u56fe\u98ce\u683c',
  conversationId: 'conv-ppt-1',
  courseId: 'course-1',
  allowRag: false,
  allowWeb: false,
  selectedDocIds: ['doc-1'],
  artifactReference: {
    artifact_id: 'ppt-deck-1',
    artifact_type: 'ppt_deck',
    title: 'TCP \u4e09\u6b21\u63e1\u624b\u8bfe\u4ef6.pptx',
    source_conversation_id: 'conv-ppt-1',
    source_course_id: 'course-1',
  },
});

assert.equal(pptPayload.artifact_reference?.artifact_type, 'ppt_deck');
assert.equal(pptPayload.artifact_reference?.artifact_id, 'ppt-deck-1');

console.log('chatPanel.artifact-reference tests passed');
