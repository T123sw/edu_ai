import { test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import { reportAnchors } from './reportAnchors';

test('report markers become real anchors; unsafe HTML and code examples stay text', () => {
  const html = renderToStaticMarkup(React.createElement(ReactMarkdown, {
    rehypePlugins: [reportAnchors],
    children: '<a id="sec-success-example"></a>\n\n## 成功示例\n\n正常正文\n\n<a id="unsafe" onclick="alert(1)"></a>\n\n```html\n<a id="code"></a>\n```',
  }));
  assert.match(html, /<a id="sec-success-example"><\/a>/);
  assert.match(html, /<h2>成功示例<\/h2>/);
  assert.match(html, /正常正文/);
  assert.doesNotMatch(html, /<a id="unsafe"/);
  assert.doesNotMatch(html, /<a id="code"/);
  assert.match(html, /&lt;a id=&quot;code&quot;&gt;/);
});
