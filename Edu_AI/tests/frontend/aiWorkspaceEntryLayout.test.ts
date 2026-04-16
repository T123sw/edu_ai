import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const aiWorkspaceFile = readFileSync(
  new URL('../../src/stitch/pages/AIWorkspace.tsx', import.meta.url),
  'utf8',
);

assert.match(
  aiWorkspaceFile,
  /ai-studio-context-bar/,
  'AIWorkspace should render the same top context bar shell as the teacher studio page',
);

assert.match(
  aiWorkspaceFile,
  /ai-workspace-shell/,
  'AIWorkspace should render the dedicated beautified workspace shell wrapper',
);

assert.match(
  aiWorkspaceFile,
  /ai-workspace-shell__main/,
  'AIWorkspace should render the layered main workbench wrapper',
);

assert.match(
  aiWorkspaceFile,
  /ai-workspace-shell__frame/,
  'AIWorkspace should render the framed three-column work area',
);

assert.match(
  aiWorkspaceFile,
  /当前课程/,
  'AIWorkspace should show a visible 当前课程 label in the entry header',
);

assert.match(
  aiWorkspaceFile,
  /当前知识点/,
  'AIWorkspace should show a visible 当前知识点 label in the entry header',
);

assert.doesNotMatch(
  aiWorkspaceFile,
  /Teacher Panels/,
  'AIWorkspace should replace the previous decorative mode badge with the simpler context header',
);

assert.doesNotMatch(
  aiWorkspaceFile,
  /rounded-\[24px\] border border-\[var\(--shell-border\)\] bg-\[rgba\(255,255,255,0\.46\)\]/,
  'AIWorkspace should replace the flatter temporary frame classes with the new beautified shell classes',
);

console.log('aiWorkspaceEntryLayout tests passed');
