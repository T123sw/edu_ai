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
  title: '李白性格分析.md',
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
assert.match(chatPanelFile, /artifactReference\.artifact_type === 'ppt_deck'[\s\S]*'PPT 文件'/, 'ChatPanel should label active PPT deck references explicitly');

const payload = buildChatReplyPayload({
  question: '保留结构，重写结论',
  conversationId: 'conv-1',
  courseId: 'course-1',
  allowRag: false,
  allowWeb: false,
  selectedDocIds: ['doc-1'],
  artifactReference: reference,
});

assert.deepEqual(payload, {
  question: '保留结构，重写结论',
  conversation_id: 'conv-1',
  course_id: 'course-1',
  allow_rag: false,
  allow_web: false,
  selected_doc_ids: ['doc-1'],
  artifact_reference: {
    artifact_id: 'report-1',
    artifact_type: 'report',
    version_id: 'v1',
    title: '李白性格分析.md',
    source_conversation_id: 'conv-1',
    source_course_id: 'course-1',
  },
} satisfies ChatReplyRequestV2);

const payloadWithoutReference = buildChatReplyPayload({
  question: '普通追问',
  conversationId: 'conv-1',
  courseId: 'course-1',
  allowRag: true,
  allowWeb: false,
  selectedDocIds: [],
  artifactReference: null,
});

assert.ok(!('artifact_reference' in payloadWithoutReference));

const pptPayload = buildChatReplyPayload({
  question: '把第 3 页改成流程图风格',
  conversationId: 'conv-ppt-1',
  courseId: 'course-1',
  allowRag: false,
  allowWeb: false,
  selectedDocIds: ['doc-1'],
  artifactReference: {
    artifact_id: 'ppt-deck-1',
    artifact_type: 'ppt_deck',
    title: 'TCP 三次握手课件.pptx',
    source_conversation_id: 'conv-ppt-1',
    source_course_id: 'course-1',
  },
});

assert.equal(pptPayload.artifact_reference?.artifact_type, 'ppt_deck');
assert.equal(pptPayload.artifact_reference?.artifact_id, 'ppt-deck-1');

console.log('chatPanel.artifact-reference tests passed');
