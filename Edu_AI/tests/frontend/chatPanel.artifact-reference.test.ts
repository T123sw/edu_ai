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

const storeFile = readFileSync('d:/github/edu_ai/Edu_AI/src/store/teacher/useStore.ts', 'utf8');
assert.match(storeFile, /artifactReference:\s*ArtifactReference \| null;/, 'store should expose artifactReference state');
assert.match(storeFile, /setArtifactReference:\s*\(reference:\s*ArtifactReference \| null\)\s*=>\s*void;/, 'store should expose setArtifactReference action');
assert.match(storeFile, /clearArtifactReference:\s*\(\)\s*=>\s*void;/, 'store should expose clearArtifactReference action');

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

console.log('chatPanel.artifact-reference tests passed');
