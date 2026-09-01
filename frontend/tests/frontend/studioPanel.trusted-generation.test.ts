import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const panel = fs.readFileSync(path.join(root, 'src/components/teacher/StudioPanel.tsx'), 'utf8');
const graphPreview = fs.readFileSync(
  path.join(root, 'src/components/teacher/MindMapArtifactPreview.tsx'),
  'utf8',
);

test('mind-map and blog entries use durable global generation jobs', () => {
  assert.match(panel, /generateKnowledgeBaseGraphV2/);
  assert.match(panel, /generateKnowledgeBaseBlogV2/);
  assert.match(panel, /requestJobRefresh\(task\.task_id\)/);
  assert.doesNotMatch(panel, /getBlogTaskStatus\(/);
  assert.doesNotMatch(panel, /setInterval\(/);
});

test('mind-map resources have a hierarchical artifact preview', () => {
  assert.match(panel, /viewingFile\.type === ['"]graph['"]/);
  assert.match(panel, /<MindMapArtifactPreview/);
  assert.match(graphPreview, /children/);
  assert.match(graphPreview, /导图/);
});
