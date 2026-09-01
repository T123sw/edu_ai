import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(new URL('../../src/store/teacher/useStore.ts', import.meta.url), 'utf8');

assert.match(
  file,
  /partialize:\s*\(state\)\s*=>\s*\(\{[\s\S]*currentConversationId:\s*state\.currentConversationId[\s\S]*\}\)/,
  'persisted teacher store state should only keep the currentConversationId',
);

assert.match(
  file,
  /merge:\s*\(persistedState,\s*currentState\)\s*=>\s*\(\{[\s\S]*generatedFiles:\s*currentState\.generatedFiles[\s\S]*\}\)/,
  'persist hydration should ignore stale generatedFiles from localStorage',
);

console.log('useStore.persistence tests passed');
