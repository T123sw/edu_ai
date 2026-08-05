import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const panel = fs.readFileSync(path.join(root, 'src/components/teacher/StudioPanel.tsx'), 'utf8');
const entry = fs.readFileSync(path.join(root, 'src/components/teacher/PptEntryPanel.tsx'), 'utf8');

test('PPT restores configuration, outline confirmation and global job submission', () => {
  assert.match(panel, /generateKnowledgeBasePptOutlineV2/);
  assert.match(panel, /generateKnowledgeBasePptV2/);
  assert.match(panel, /requestJobRefresh\(task\.task_id\)/);
  assert.match(panel, /setPptEntryVisible\(true\)/);
  assert.match(entry, /生成大纲/);
  assert.match(entry, /确认大纲并生成 PPT/);
  assert.match(entry, /PPT 大纲/);
});

