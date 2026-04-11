import assert from 'node:assert/strict';

import {
  buildDirectPptGenerateRequest,
  buildDirectPptOutlineRequest,
} from '../../src/services/teacher/pptEntry.helpers.ts';

const outlinePayload = buildDirectPptOutlineRequest({
  courseId: 'course-1',
  selectedDocIds: ['doc-1'],
  config: {
    deckTitle: 'Agent Basics',
    audience: 'Undergraduate students',
    objective: 'Classroom presentation',
    themeId: 'heu_academic_elegant',
    lengthOption: 'medium',
    keyPoints: ['Definition'],
    generalRequirements: 'Audience is high school students.',
  },
});

assert.equal(outlinePayload.selected_doc_ids?.[0], 'doc-1');
assert.equal(outlinePayload.ppt_config.deck_title, 'Agent Basics');
assert.equal(outlinePayload.ppt_config.length_option, 'medium');

const generatePayload = buildDirectPptGenerateRequest({
  draftId: 'ppt-draft-1',
  outline: { deck_title: 'Agent Basics', slides: [] },
});

assert.equal(generatePayload.draft_id, 'ppt-draft-1');
assert.equal(generatePayload.confirm, true);

console.log('pptEntry.helpers tests passed');
