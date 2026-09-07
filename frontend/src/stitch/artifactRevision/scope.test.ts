import assert from "node:assert/strict";
import test from "node:test";
import { buildGenerationRequest, type GenerationDraft } from "../../components/generation/useGenerationSubmission";
import { defaultGenerationConfig } from "../../components/generation/definitions";

for (const kind of ['report', 'lesson_plan', 'blog', 'quiz', 'flashcard', 'mind_map', 'game', 'classroom'] as const) {
  test(`${kind} serializes actual knowledge point after definition defaults`, () => {
    const draft: GenerationDraft = { resourceType: kind, topic: '数组', audience: '', requirements: '', source: { mode: 'course_auto', selectedDocumentIds: [] }, config: defaultGenerationConfig(kind), scopeType: 'knowledge_point', scopeId: 'arrays' };
    const request = buildGenerationRequest(draft, 'course', 'op');
    assert.equal(request.body.scope_type, 'knowledge_point');
    assert.equal(request.body.scope_id, 'arrays');
    assert.throws(() => buildGenerationRequest({ ...draft, scopeId: '' }, 'course'), /知识点/);
  });
}
