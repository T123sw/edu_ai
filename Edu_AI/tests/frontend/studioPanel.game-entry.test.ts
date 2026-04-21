import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');
const gameEntryModal = readFileSync(new URL('../../src/components/teacher/GameEntryModal.tsx', import.meta.url), 'utf8');

assert.match(studioPanel, /type:\s*'game'/, 'StudioPanel should expose a dedicated game generation action');
assert.match(studioPanel, /setGameEntryVisible\(true\)/, 'StudioPanel should open the game entry modal for game generation');
assert.match(studioPanel, /generateKnowledgeBaseGameV2\(/, 'StudioPanel should call the direct mini game API');
assert.match(studioPanel, /<GameEntryModal/, 'StudioPanel should render the game entry modal');
assert.match(
  studioPanel,
  /STUDIO_ACTION_DISPLAY_ORDER\s*=\s*\[[\s\S]*'graph'[\s\S]*'game'[\s\S]*\]/,
  'StudioPanel should order the game card after the mind-map card',
);
assert.match(
  studioPanel,
  /type:\s*'game'[\s\S]*featured:\s*true/,
  'StudioPanel should place the game card next to the mind-map card in the featured grid',
);

assert.match(gameEntryModal, /category_sort/, 'GameEntryModal should list the category sort option');
assert.match(gameEntryModal, /drag_match/, 'GameEntryModal should list the drag match option');
assert.match(gameEntryModal, /memory_flip/, 'GameEntryModal should list the memory flip option');
assert.match(gameEntryModal, /生成小游戏/, 'GameEntryModal should expose the submit CTA');

console.log('studioPanel.game-entry tests passed');
