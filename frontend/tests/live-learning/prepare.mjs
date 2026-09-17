// Usage: LIVE_BACKEND_URL=http://127.0.0.1:8001 node tests/live-learning/prepare.mjs
// Registers isolated real users and submits real generation; no API stubs.
import { randomUUID } from 'node:crypto';
import { writeFileSync } from 'node:fs';
const base = process.env.LIVE_BACKEND_URL || 'http://127.0.0.1:8001';
const output = process.env.LIVE_ACCOUNTS_FILE || '/tmp/edu-live-accounts.json';
async function call(path, data, token) {
  const response = await fetch(base + path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify(data) });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}
const fixture = {};
const suffix = randomUUID().slice(0, 8);
for (const role of ['teacher', 'student']) {
  const password = randomUUID();
  fixture[role] = { ...await call('/api/auth/register', { username: `live_e2e_${role}_${suffix}`, password, role }), password };
}
fixture.create_id = randomUUID();
writeFileSync(output, JSON.stringify(fixture), { mode: 0o600 });
fixture.room = await call('/api/self-learning/courses', { goal: '学习 Python 变量和条件判断，只需要两个入门知识点，用极简实例讲解。', request_id: fixture.create_id }, fixture.teacher.token);
fixture.course_id = fixture.room.id;
writeFileSync(output, JSON.stringify(fixture), { mode: 0o600 });
console.log(`Created real test classroom ${fixture.course_id}; credentials saved outside the repository.`);
