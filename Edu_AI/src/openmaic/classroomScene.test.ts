import assert from 'node:assert/strict';
import test from 'node:test';
import type { ClassroomScene } from '../stitch/api/types.ts';
import { resolveClassroomSceneKind } from './classroomScene.ts';

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
