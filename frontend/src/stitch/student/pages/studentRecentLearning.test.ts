import assert from 'node:assert/strict';
import test from 'node:test';
import { readResume, recordFromHash, saveResume, type ResumeStorage } from '../../resume/resumeRecord.ts';

test('legacy unowned history is ignored and student history records verified locations only', () => {
  const values = new Map<string, string>([['edu-ai-student-recent-learning', JSON.stringify({ version: 1, records: [{ courseId: 'old-course', lastRoute: 'student-ai', visitedAt: new Date().toISOString() }] })]]);
  const storage: ResumeStorage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => { values.set(key, value); }, removeItem: (key) => { values.delete(key); } };
  const user = { username: 'S1', role: 'student' } as const;
  assert.equal(readResume(user, () => storage), null);
  saveResume(user, recordFromHash(user, '#student-ai?course_id=c1&scopeType=knowledge_point&scopeId=array'), () => storage);
  assert.equal(readResume(user, () => storage)?.params.scopeId, 'array');
  assert.equal(readResume({ ...user, username: 'S2' }, () => storage), null);
  assert.equal(recordFromHash(user, '#student-home'), null);
});
