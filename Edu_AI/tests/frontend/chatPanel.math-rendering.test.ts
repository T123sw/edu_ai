import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const chatPanelFile = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  chatPanelFile,
  /import 'katex\/dist\/katex\.min\.css';/,
  'ChatPanel should load KaTeX styles so rendered formulas display correctly',
);

assert.match(
  chatPanelFile,
  /import remarkMath from 'remark-math';/,
  'ChatPanel should import the remark-math plugin for inline and block formulas',
);

assert.match(
  chatPanelFile,
  /import rehypeKatex from 'rehype-katex';/,
  'ChatPanel should import the rehype-katex plugin for formula rendering',
);

assert.match(
  chatPanelFile,
  /remarkPlugins=\{\[remarkGfm,\s*remarkMath\]\}/,
  'ChatPanel should enable remark-math alongside GitHub-flavored markdown',
);

assert.match(
  chatPanelFile,
  /rehypePlugins=\{\[rehypeKatex\]\}/,
  'ChatPanel should render parsed formulas through rehype-katex',
);

console.log('chatPanel.math-rendering tests passed');
