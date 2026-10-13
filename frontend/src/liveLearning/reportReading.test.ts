import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import { courseMaterialToMarkdown } from '../stitch/api/courses';
import { normalizeKnowledgeMarkdown } from '../stitch/components/knowledgeMarkdown';
import { reportBlockId, reportReadingAnchors, reportFingerprint } from './reportReading';
import type { CourseMaterial } from '../stitch/api/types';

test('rendered paragraph annotations retain distinct positions for repeated text', () => {
  const source = '# 标题 😀\n\n相同 **文字**。\n\n相同 **文字**。';
  const html = renderToStaticMarkup(React.createElement(ReactMarkdown, { rehypePlugins: [reportReadingAnchors], children: source }));
  assert.match(html, /data-report-start="9"/);
  assert.match(html, /<strong>文字<\/strong>/);
  assert.notEqual(reportBlockId(source, 9, 19), reportBlockId(source, 21, 31));
  assert.match(reportBlockId(source, 9, 19), /^report-v1:8:18:/, 'JS UTF-16 offsets are converted to code points');
});

test('frontend report rendering and fingerprints match backend for all supported report forms', () => {
  const fixtures = JSON.parse(readFileSync(new URL('./reportReading.fixtures.json', import.meta.url), 'utf8')) as CourseMaterial[];
  const actual = fixtures.map(material => {
    const text = normalizeKnowledgeMarkdown(courseMaterialToMarkdown(material));
    return { text, fingerprint: reportFingerprint(text) };
  });
  const python = process.env.REPORT_TEST_PYTHON || 'python';
  const expected = JSON.parse(execFileSync(python, ['-c', 'import sys,json; sys.path.insert(0,"../backend/src"); from app.self_learning.report_document import report_markdown,normalize_report,report_fingerprint; values=json.load(sys.stdin); print(json.dumps([dict(text=(s:=normalize_report(report_markdown(v))),fingerprint=report_fingerprint(s)) for v in values],ensure_ascii=False))'], { input: JSON.stringify(fixtures), encoding: 'utf8' }));
  assert.deepEqual(actual, expected);
});
