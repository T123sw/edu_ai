import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import { routes } from './shared';

test('does not expose the AI lecturer video player route', () => {
  assert.equal('video' in routes, false);
});

const source = (relativePath: string) => readFileSync(
  fileURLToPath(new URL(relativePath, import.meta.url)),
  'utf8',
);

test('course navigation has one knowledge destination and graph is redirect-only', () => {
  const navigation = source('./course/courseNavigation.ts');
  const app = source('./App.tsx');
  assert.equal((navigation.match(/id:\s*["']knowledge["']/gu) || []).length, 1);
  assert.doesNotMatch(navigation, /id:\s*["']graph["']/u);
  assert.match(app, /routes\.graph,\s*["']Knowledge Graph["'],\s*LegacyKnowledgeGraphRedirect/u);
});

test('course knowledge renders only the document library', () => {
  const knowledge = source('./pages/CourseKnowledge.tsx');
  const courseDetail = source('./pages/CourseDetail.tsx');
  assert.match(knowledge, /KnowledgeDocumentsView/u);
  assert.doesNotMatch(knowledge, /KnowledgeStructureView|知识图谱|view\s*===\s*["']structure["']/u);
  assert.doesNotMatch(courseDetail, /知识图谱/u);
  assert.match(knowledge, /buildTeacherCourseHash\(["']knowledge["'],\s*courseId\)/u);
});

test('knowledge structure cannot restore a second upload workflow', () => {
  const structure = source('./pages/KnowledgeGraph.tsx');
  assert.doesNotMatch(structure, /textbook-import|上传教材并解析|上传节点文件/u);
});

test('legacy generation modals and raw PPT JSON editor stay removed', () => {
  for (const relativePath of [
    '../components/teacher/ReportEntryModal.tsx',
    '../components/teacher/LessonPlanEntryModal.tsx',
    '../components/teacher/QuizEntryModal.tsx',
    '../components/teacher/FlashcardEntryModal.tsx',
    '../components/teacher/GameEntryModal.tsx',
    '../components/teacher/PptEntryPanel.tsx',
  ]) {
    assert.equal(existsSync(fileURLToPath(new URL(relativePath, import.meta.url))), false, relativePath);
  }
  const factory = source('../components/generation/GenerationFactory.tsx');
  const pptForm = source('../components/generation/forms/PptForm.tsx');
  const outline = source('../components/generation/previews/PptOutlineEditor.tsx');
  assert.equal((factory.match(/<QuizForm\b/gu) || []).length, 1);
  assert.doesNotMatch(`${pptForm}\n${outline}`, /JSON\.stringify|PPT 大纲["']\s*\/?>/u);
});

test('course identity never falls back to local storage on a course page', () => {
  const provider = source('./course/CourseRouteProvider.tsx');
  assert.match(provider, /routeName\(hash\)\s*===\s*["']home["']/u);
  assert.doesNotMatch(provider, /localStorage/u);
});

test('course cards contain no random or decorative progress calculation', () => {
  const card = source('./pages/courseCardPresentation.ts');
  assert.doesNotMatch(card, /Math\.random|charCodeAt|progressPercent|decorativeProgress/u);
});

test('theme controls live in profile instead of a floating app control', () => {
  const app = source('./App.tsx');
  const profile = source('./pages/Profile.tsx');
  const shared = source('./shared.tsx');
  assert.doesNotMatch(app, /ThemeCustomizer/u);
  assert.doesNotMatch(shared, /function ThemeCustomizer/u);
  assert.match(shared, /palette:/u);
  assert.match(profile, /ThemeAppearanceSettings/u);
});
