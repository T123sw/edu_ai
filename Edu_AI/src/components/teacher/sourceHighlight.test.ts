import assert from 'node:assert/strict';
import test from 'node:test';

import {
  locateSourceHighlightRange,
  stripRetrievalContextPrefix,
} from './sourceHighlight';

test('strips embedding-only chapter context before source matching', () => {
  const source = '【章节上下文】: 链表 > 初始化\n\n```java\nnode.next = head;\n```';

  assert.equal(
    stripRetrievalContextPrefix(source),
    '```java\nnode.next = head;\n```',
  );
});

test('maps whitespace-normalized source content back to the complete raw range', () => {
  const full = '前文\n\n```java\n    node.next = head;\n    head = node;\n```\n\n后文';
  const source = '```java\nnode.next = head;\nhead = node;\n```';

  const range = locateSourceHighlightRange(full, source);

  assert.ok(range);
  assert.equal(full.slice(range.start, range.end), '```java\n    node.next = head;\n    head = node;\n```');
});

test('does not degrade to repeated keyword highlighting when a chunk cannot align', () => {
  const full = '初始化链表\n其他正文\n初始化链表';
  const source = '完全不同的检索片段';

  assert.equal(locateSourceHighlightRange(full, source), null);
});
