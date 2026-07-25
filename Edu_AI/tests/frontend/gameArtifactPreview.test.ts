import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { extractGeneratedFilesFromV2Response } from '../../src/services/teacher/chatV2.helpers.ts';
import { resolveGameHtmlUrl } from '../../src/services/teacher/gameAssets.ts';
import { toGeneratedFileFromCourseMaterial } from '../../src/services/teacher/materials.helpers.ts';

const files = extractGeneratedFilesFromV2Response({
  artifacts: [
    {
      artifact_id: 'game-1',
      artifact_type: 'game',
      title: '历史概念配对.html',
      content: {
        game_type: 'drag_match',
        template_id: 'drag-match',
        game_data: {
          title: '历史概念配对',
          pairs: [],
        },
        html_url: '/api/chat/v2/games/html?path=tester/course-1/game-1/index.html',
      },
      generation_state: {
        status: 'completed',
      },
    },
  ],
});

assert.equal(files.length, 1);
assert.equal(files[0].type, 'game');
assert.equal(files[0].name, '历史概念配对.html');
assert.equal((files[0].meta as any)?.kind, 'game');
assert.equal((files[0].meta as any)?.htmlUrl, '/api/chat/v2/games/html?path=tester/course-1/game-1/index.html');
assert.equal((files[0].meta as any)?.gameType, 'drag_match');
assert.equal((files[0].meta as any)?.templateId, 'drag-match');

const restoredGame = toGeneratedFileFromCourseMaterial({
  id: 'game-1',
  name: '历史概念配对.html',
  type: 'game',
  content: {
    game_type: 'drag_match',
    template_id: 'drag-match',
    game_data: {
      title: '历史概念配对',
      pairs: [],
    },
    html_url: '/api/chat/v2/games/html?path=tester/course-1/game-1/index.html',
  },
  courseId: 'course-1',
  scopeType: 'course',
  addedAt: '2026-04-21T10:00:00.000Z',
  generationState: {
    status: 'completed',
  },
} as any);

assert.equal(restoredGame?.type, 'game');
assert.equal((restoredGame?.meta as any)?.origin, 'course_material');
assert.equal((restoredGame?.meta as any)?.kind, 'game');
assert.equal((restoredGame?.meta as any)?.htmlUrl, '/api/chat/v2/games/html?path=tester/course-1/game-1/index.html');
assert.equal((restoredGame?.meta as any)?.gameType, 'drag_match');
assert.equal((restoredGame?.meta as any)?.templateId, 'drag-match');

assert.equal(
  resolveGameHtmlUrl('/api/chat/v2/games/html?path=tester/course-1/game-1/index.html'),
  'http://localhost:8000/api/chat/v2/games/html?path=tester/course-1/game-1/index.html',
);

const chatV2Source = readFileSync(new URL('../../src/services/teacher/chatV2.ts', import.meta.url), 'utf8');
const storeSource = readFileSync(new URL('../../src/store/teacher/useStore.ts', import.meta.url), 'utf8');
const previewSource = readFileSync(new URL('../../src/components/teacher/GameArtifactPreview.tsx', import.meta.url), 'utf8');
const studioPanelSource = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(chatV2Source, /export type GameTypeV2 = 'category_sort' \| 'drag_match' \| 'memory_flip'/);
assert.match(chatV2Source, /export interface KnowledgeBaseDirectGameRequestV2[\s\S]*game_type:\s*GameTypeV2/);
assert.match(chatV2Source, /export async function generateKnowledgeBaseGameV2\(/);
assert.match(chatV2Source, /\/api\/chat\/v2\/game\/direct/);
assert.match(storeSource, /type:\s*'report' \| 'ppt' \| 'quiz' \| 'blog' \| 'lesson_plan' \| 'audio' \| 'graph' \| 'video' \| 'flashcard' \| 'game'/);
assert.match(previewSource, /iframe/, 'GameArtifactPreview should render an iframe for HTML preview');
assert.match(previewSource, /全屏播放/, 'GameArtifactPreview should expose a play-mode button');
assert.match(previewSource, /srcDoc/, 'GameArtifactPreview should render fetched HTML instead of navigating the iframe to the frontend app');
assert.match(previewSource, /Authorization/, 'GameArtifactPreview should fetch protected game HTML with the auth token');
assert.match(previewSource, /window\.open\(/, 'GameArtifactPreview should open the standalone HTML URL');
assert.match(studioPanelSource, /viewingFile\.type === 'game'/, 'StudioPanel should route game files into the dedicated preview');
assert.match(studioPanelSource, /<GameArtifactPreview/, 'StudioPanel should render GameArtifactPreview for game files');

console.log('gameArtifactPreview tests passed');
