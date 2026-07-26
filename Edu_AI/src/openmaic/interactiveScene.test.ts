import assert from 'node:assert/strict';
import test from 'node:test';
import type { Action } from '@openmaic/dsl';
import {
  patchInteractiveHtml,
  WidgetMessageBuffer,
  widgetMessageForAction,
} from './interactiveScene.ts';

test('patchInteractiveHtml injects sandbox-safe runtime support into head', () => {
  const patched = patchInteractiveHtml(
    '<!doctype html><html><head><title>Demo</title></head><body>demo</body></html>',
  );

  assert.match(patched, /data-edu-runtime-error-shim/);
  assert.match(patched, /data-edu-storage-shim/);
  assert.match(patched, /data-edu-iframe-style/);
  assert.ok(
    patched.indexOf('data-edu-runtime-error-shim') <
      patched.indexOf('<title>Demo</title>'),
  );
});

test('patchInteractiveHtml prepends runtime support when the document has no head', () => {
  const patched = patchInteractiveHtml('<main>demo</main>');

  assert.match(patched, /^<script data-edu-runtime-error-shim>/);
  assert.match(patched, /<main>demo<\/main>$/);
});

test('patchInteractiveHtml bridges legacy OpenMAIC widget state across scripts', () => {
  const patched = patchInteractiveHtml(`
    <script>
      function applyStateFromMessage(state) {
        if (state.pivotValue) handleCardClick(0);
      }
    </script>
    <script>
      (function () {
        const simState = { pivotValue: null };
        function handleCardClick(idx) { simState.pivotValue = idx; }
      })();
    </script>
  `);

  assert.match(patched, /window\.simState = \{ pivotValue: null \}/);
  assert.match(
    patched,
    /window\.handleCardClick = function\(idx\) \{ simState\.pivotValue = idx; \}/,
  );
});

test('WidgetMessageBuffer preserves actions until the iframe is ready', () => {
  const delivered: Array<{
    type: string;
    payload: Record<string, unknown>;
  }> = [];
  const buffer = new WidgetMessageBuffer();

  buffer.postMessage('SET_WIDGET_STATE', { state: { pivot: 9 } });
  assert.deepEqual(delivered, []);

  buffer.setSender((type, payload) => delivered.push({ type, payload }));
  buffer.postMessage('HIGHLIGHT_ELEMENT', { target: '#pivot' });
  assert.deepEqual(delivered, [
    {
      type: 'SET_WIDGET_STATE',
      payload: { state: { pivot: 9 } },
    },
    {
      type: 'HIGHLIGHT_ELEMENT',
      payload: { target: '#pivot' },
    },
  ]);

  buffer.setSender(null);
  buffer.postMessage('REVEAL_ELEMENT', { target: '#answer' });
  assert.equal(delivered.length, 2);
  buffer.setSender((type, payload) => delivered.push({ type, payload }));
  assert.deepEqual(delivered[2], {
    type: 'REVEAL_ELEMENT',
    payload: { target: '#answer' },
  });
});

test('widgetMessageForAction maps the OpenMAIC widget protocol', () => {
  const actions: Action[] = [
    {
      id: 'state',
      type: 'widget_setState',
      state: { pivot: 6 },
      content: '设置基准',
    },
    {
      id: 'highlight',
      type: 'widget_highlight',
      target: '#pivot',
      content: '观察基准',
    },
    {
      id: 'annotation',
      type: 'widget_annotation',
      target: '#left',
      content: '左指针',
    },
    {
      id: 'reveal',
      type: 'widget_reveal',
      target: '#answer',
      content: '显示结果',
    },
  ];

  assert.deepEqual(actions.map(widgetMessageForAction), [
    {
      type: 'SET_WIDGET_STATE',
      payload: { state: { pivot: 6 }, content: '设置基准' },
    },
    {
      type: 'HIGHLIGHT_ELEMENT',
      payload: { target: '#pivot', content: '观察基准' },
    },
    {
      type: 'ANNOTATE_ELEMENT',
      payload: { target: '#left', content: '左指针' },
    },
    {
      type: 'REVEAL_ELEMENT',
      payload: { target: '#answer', content: '显示结果' },
    },
  ]);
  assert.equal(
    widgetMessageForAction({
      id: 'speech',
      type: 'speech',
      text: '讲解',
    }),
    null,
  );
});
