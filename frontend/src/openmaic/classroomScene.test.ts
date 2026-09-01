import assert from 'node:assert/strict';
import test from 'node:test';
import type { ClassroomScene } from '../stitch/api/types.ts';
import {
  getClassroomScenePresentation,
  resolveClassroomSceneKind,
} from './classroomScene.ts';

test('resolves the three supported classroom scene kinds', () => {
  const scenes: ClassroomScene[] = [
    {
      id: 'slide',
      type: 'slide',
      content: { type: 'slide', canvas: { id: 'canvas' } },
    },
    {
      id: 'interactive',
      type: 'interactive',
      content: { type: 'interactive', html: '<p>demo</p>' },
    },
    {
      id: 'quiz',
      type: 'quiz',
      content: { type: 'quiz', questions: [] },
    },
  ];

  assert.deepEqual(scenes.map(resolveClassroomSceneKind), [
    'slide',
    'interactive',
    'quiz',
  ]);
});

test('rejects mismatched content and distinguishes unsupported scene types', () => {
  const mismatched: ClassroomScene = {
    id: 'bad',
    type: 'quiz',
    content: { type: 'slide', canvas: { id: 'canvas' } },
  };
  const pbl: ClassroomScene = {
    id: 'pbl',
    type: 'pbl',
    content: { type: 'pbl', projectConfig: {} },
  };

  assert.equal(resolveClassroomSceneKind(mismatched), 'invalid');
  assert.equal(resolveClassroomSceneKind(pbl), 'unsupported');
  assert.equal(
    resolveClassroomSceneKind({ id: 'missing', type: 'slide' }),
    'invalid',
  );
});

test('presents teacher-facing titles and current-page narration without technical ids', () => {
  const scene: ClassroomScene = {
    id: 'scene_internal_42',
    type: 'slide',
    content: { type: 'slide', canvas: { id: 'canvas' } },
    actions: [
      { id: 'a1', type: 'speech', text: '先观察图中的变化。' },
      { id: 'a2', type: 'focus', targetId: 'node-1' },
      { id: 'a3', type: 'speech', text: '再归纳规律。' },
    ],
  };

  assert.deepEqual(getClassroomScenePresentation(scene, 2), {
    title: '第 3 页',
    narration: ['先观察图中的变化。', '再归纳规律。'],
    hasPlayback: true,
    kindLabel: '课件页',
  });
});

test('uses authored scene title and marks a page without actions as static', () => {
  const scene: ClassroomScene = {
    id: 'quiz-1',
    type: 'quiz',
    title: '课堂练习',
    content: { type: 'quiz', questions: [] },
    actions: [],
  };

  assert.deepEqual(getClassroomScenePresentation(scene, 0), {
    title: '课堂练习',
    narration: [],
    hasPlayback: false,
    kindLabel: '互动练习',
  });
});
