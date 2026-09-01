import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const chatPanel = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  chatPanel,
  /chat-panel/,
  'ChatPanel should render the dedicated chat-panel root class for the beautified middle area',
);

assert.match(
  chatPanel,
  /chat-panel__controls/,
  'ChatPanel should render a dedicated light control layer above the message stage',
);

assert.match(
  chatPanel,
  /chat-panel__toolbar-button/,
  'ChatPanel should use dedicated lightweight toolbar button styling for the top actions',
);

assert.match(
  chatPanel,
  /chat-panel__history-popover-shell/,
  'ChatPanel should render the history list inside a dedicated lightweight popover shell',
);

assert.match(
  chatPanel,
  /chat-panel__messages/,
  'ChatPanel should render a dedicated message-stage shell',
);

assert.match(
  chatPanel,
  /chat-panel__composer/,
  'ChatPanel should render a dedicated bottom composer shell',
);

assert.match(
  chatPanel,
  /chat-panel__composer-actions/,
  'ChatPanel should render a bottom action row under the taller composer input',
);

assert.match(
  chatPanel,
  /chat-panel__composer-toggle-group/,
  'ChatPanel should move the RAG and Web toggles into the composer action row',
);

assert.match(
  chatPanel,
  /chat-panel__composer-primary-actions/,
  'ChatPanel should group the send and voice buttons as the primary right-side actions',
);

assert.doesNotMatch(
  chatPanel,
  /<StatusCard\s/,
  'ChatPanel should remove the top status card from the middle conversation area',
);

assert.doesNotMatch(
  chatPanel,
  /已引用该对话/,
  'ChatPanel history list should no longer expose the old conversation-reference action',
);

console.log('chatPanel.layout tests passed');
