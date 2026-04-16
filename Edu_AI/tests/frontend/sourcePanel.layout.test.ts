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
  /资料列表/,
  'SourcePanel should expose a readable 资料列表 section label',
);

assert.match(
  sourcePanel,
  /上传资料/,
  'SourcePanel should expose a readable 上传资料 section label',
);

assert.doesNotMatch(
  sourcePanel,
  /boxShadow:\s*'0 4px 12px rgba\(0,0,0,0\.08\)'/,
  'SourcePanel should stop relying on the flatter inline shell shadow once the beautified shell is implemented',
);

console.log('sourcePanel.layout tests passed');
