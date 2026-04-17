import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const sourcePanel = readFileSync(
  new URL('../../src/components/teacher/SourcePanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  sourcePanel,
  /source-panel/,
  'SourcePanel should render the dedicated source-panel root class for the beautified shell',
);

assert.match(
  sourcePanel,
  /source-panel__header/,
  'SourcePanel should render a dedicated header section for the materials workbench',
);

assert.match(
  sourcePanel,
  /source-panel__tools/,
  'SourcePanel should render a dedicated retrieval tools section',
);

assert.match(
  sourcePanel,
  /source-panel__search-shell/,
  'SourcePanel should render an inline deep-research search shell',
);

assert.match(
  sourcePanel,
  /source-panel__list/,
  'SourcePanel should render a dedicated document list section',
);

assert.match(
  sourcePanel,
  /source-panel__footer/,
  'SourcePanel should render a dedicated upload footer section',
);

assert.match(
  sourcePanel,
  /\u8d44\u6599\u5217\u8868/,
  'SourcePanel should expose a readable 资料列表 section label',
);

assert.match(
  sourcePanel,
  /\u4e0a\u4f20\u6587\u6863\/\u56fe\u7247\/\u89c6\u9891/,
  'SourcePanel should expose a readable upload call-to-action',
);

assert.doesNotMatch(
  sourcePanel,
  /\u8d44\u6599\u5de5\u4f5c\u53f0/,
  'SourcePanel should drop the extra materials-workbench eyebrow copy after simplification',
);

assert.doesNotMatch(
  sourcePanel,
  /boxShadow:\s*'0 4px 12px rgba\(0,0,0,0\.08\)'/,
  'SourcePanel should stop relying on the flatter inline shell shadow once the beautified shell is implemented',
);

console.log('sourcePanel.layout tests passed');
