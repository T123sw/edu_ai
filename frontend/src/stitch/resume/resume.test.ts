import assert from 'node:assert/strict';
import test from 'node:test';
import { recordFromHash, resumeHash, resumeKey, readResume, saveResume, parseResume, type ResumeStorage } from './resumeRecord.ts';
import { validateResume, type ResumeApi } from './validateResume.ts';
import type { AuthUser } from '../authSession';
import type { BackendCourse, CourseMaterial } from '../api/types';
const teacher: AuthUser = { username: 'T1', role: 'teacher' };
const student: AuthUser = { username: 'S1', role: 'student' };
const course = { id: 'c1', title: '数据结构' } as BackendCourse;
function memory(): ResumeStorage {
  const data = new Map<string, string>();
  return { getItem: (key) => data.get(key) ?? null, setItem: (key, value) => { data.set(key, value); }, removeItem: (key) => { data.delete(key); } };
}
const api: ResumeApi = {
  course: async () => course,
  graph: async () => ({ root: { id: 'root', label: '课程', children: [{ id: 'array', label: '数组' }, { id: 'list', label: '链表' }] } }),
  materials: async () => [{ material_id: 'm1', material_type: 'report' } as CourseMaterial],
  catalog: async () => ({ course_id: 'c1', mode: 'learn', leaves: [] }),
  classrooms: async () => [],
  overview: async () => ({}),
};
const visit = (hash = '#ai?course_id=c1&scopeType=knowledge_point&scopeId=array') => recordFromHash(teacher, hash)!;
test('account and role isolation, same-route query changes, and safe versioned fields', () => {
  const storage = memory();
  saveResume(teacher, visit(), () => storage);
  assert.equal(readResume(teacher, () => storage)?.params.scopeId, 'array');
  assert.equal(readResume({ ...teacher, username: 'T2' }, () => storage), null);
  assert.equal(readResume({ ...teacher, role: 'student' }, () => storage), null);
  saveResume(teacher, visit('#ai?course_id=c1&scopeType=knowledge_point&scopeId=list&token=secret&scopeLabel=untrusted'), () => storage);
  assert.equal(readResume(teacher, () => storage)?.params.scopeId, 'list');
  assert.doesNotMatch(storage.getItem(resumeKey(teacher))!, /secret|token|untrusted|scopeLabel/);
});
test('home/settings/login/foreign roles/URLs and corrupt storage cannot create history', () => {
  for (const hash of ['#home?course_id=c1', '#edit?course_id=c1', '#settings?course_id=c1', '#login', '#student-ai?course_id=c1', 'https://evil.test/#ai?course_id=c1', '#ai?course_id=..%2Fx']) assert.equal(recordFromHash(teacher, hash), null);
  for (const raw of ['{', 'null', '{}', JSON.stringify({ ...visit(), route: 'https://evil.test' })]) assert.equal(parseResume(teacher, raw), null);
  const blocked = () => { throw new Error('SecurityError'); };
  assert.equal(readResume(teacher, blocked), null);
  assert.doesNotThrow(() => saveResume(teacher, visit(), blocked));
});
test('canonical scope aliases are read using the existing workspace parser', () => {
  const record = visit('#ai?course_id=c1&scope_type=knowledge_point&scope_id=array');
  assert.equal(resumeHash(teacher, record), '#ai?course_id=c1&scopeType=knowledge_point&scopeId=array');
});
test('student materials and classroom parameters survive only on supported routes', () => {
  for (const hash of ['#student-resources?course_id=c1&material_type=report&material_id=m1', '#student-classroom?course_id=c1&node_id=array&resource_id=m1', '#student-classroom?course_id=c1&personal_classroom_id=m2']) {
    const record = recordFromHash(student, hash)!;
    assert.equal(resumeHash(student, record), hash);
  }
  assert.deepEqual(visit('#course-detail?course_id=c1&material_id=m1&token=x').params, {});
  assert.equal(recordFromHash(student, '#student-classroom?course_id=c1&node_id=array&personal_classroom_id=m2'), null);
  assert.equal(resumeHash(teacher, visit('#teacher-classroom-studio?course_id=c1&node_id=array')), '#classroom-studio?course_id=c1&node_id=array');
});
test('live metadata validates the exact scope, missing scope falls back within the same course', async () => {
  const result = await validateResume(teacher, visit(), api);
  assert.equal(result.status, 'valid');
  if (result.status === 'valid') { assert.equal(result.course.title, '数据结构'); assert.equal(result.label, '数组'); }
  const fallback = await validateResume(teacher, visit('#ai?course_id=c1&scopeType=knowledge_point&scopeId=missing'), api);
  assert.equal(fallback.status, 'fallback');
  if (fallback.status === 'fallback') assert.equal(resumeHash(teacher, fallback.record), '#course-detail?course_id=c1');
});
test('permission loss differs from network failure, including target lookups', async () => {
  for (const status of [403, 404, 410, 401, 500, 0]) {
    const fail = async (): Promise<never> => { throw { status }; };
    assert.equal((await validateResume(teacher, visit(), { ...api, course: fail })).status, [403, 404, 410].includes(status) ? 'invalid' : 'retry');
    assert.equal((await validateResume(teacher, visit(), { ...api, graph: fail })).status, [403, 404, 410].includes(status) ? 'fallback' : 'retry');
  }
});
test('deleted resources are not resolved by title and failed validation does not write history', async () => {
  const storage = memory(); saveResume(teacher, visit(), () => storage);
  const before = storage.getItem(resumeKey(teacher));
  const result = await validateResume(teacher, visit('#resources?course_id=c1&material_type=report&material_id=deleted'), api);
  assert.equal(result.status, 'fallback');
  assert.equal(storage.getItem(resumeKey(teacher)), before);
  assert.equal((await validateResume(student, recordFromHash(student, '#student-classroom?course_id=c1&node_id=array&resource_id=deleted')!, api)).status, 'fallback');
});

test('a page data failure cannot be mistaken for a successful visit', async () => {
  const fail = async (): Promise<never> => { throw { status: 503 }; };
  for (const [route, overrides] of [
    ['resources', { materials: fail }], ['knowledge', { graph: fail }],
    ['classroom-studio', { catalog: fail }], ['learning', { overview: fail }],
  ] as const) {
    assert.equal((await validateResume(teacher, visit(`#${route}?course_id=c1`), { ...api, ...overrides })).status, 'retry');
  }
});
