import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const panel = fs.readFileSync(path.join(root, 'src/components/teacher/StudioPanel.tsx'), 'utf8');
const modal = fs.readFileSync(path.join(root, 'src/components/teacher/FlashcardEntryModal.tsx'), 'utf8');
const preview = fs.readFileSync(path.join(root, 'src/components/teacher/FlashcardArtifactPreview.tsx'), 'utf8');

test('flashcard entry submits a real recoverable generation job', () => {
  assert.match(panel, /generateKnowledgeBaseFlashcardV2/);
  assert.match(panel, /requestJobRefresh\(task\.task_id\)/);
  assert.match(panel, /setFlashcardEntryVisible\(true\)/);
  assert.doesNotMatch(panel, /type === ['"]flashcard['"][\s\S]{0,300}开发中/);
  assert.match(modal, /卡片数量/);
  assert.match(modal, /显示资料来源/);
});

test('flashcard resources have a card-by-card preview', () => {
  assert.match(panel, /viewingFile\.type === ['"]flashcard['"]/);
  assert.match(panel, /<FlashcardArtifactPreview/);
  assert.match(preview, /上一张/);
  assert.match(preview, /查看答案/);
  assert.match(preview, /source_doc_id/);
});

