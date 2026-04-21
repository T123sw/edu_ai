import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/CourseResources.tsx', import.meta.url), 'utf8');

assert.match(
  page,
  /<AppSurface className="flex min-h-screen xl:h-screen xl:overflow-hidden">/,
  'Course resources should lock the overall desktop workspace to the viewport height',
);

assert.match(
  page,
  /<main className="flex min-h-0 flex-1 flex-col xl:overflow-hidden">/,
  'Course resources should keep the main content area from being stretched by the resource list',
);

assert.match(
  page,
  /xl:min-h-0 xl:grid-cols-\[360px_minmax\(0,1fr\)\] xl:overflow-hidden/,
  'Course resources should make the desktop two-column content area fill the remaining viewport height',
);

assert.match(
  page,
  /<section className="flex min-h-0 flex-col overflow-hidden">/,
  'Course resources should isolate the resource list column into its own fixed-height region',
);

assert.match(
  page,
  /min-h-0 flex-1 space-y-4 overflow-y-auto pr-2/,
  'Course resources should render the resource list inside an independently scrollable area',
);

assert.match(
  page,
  /<GlassPanel className="flex h-full min-h-0 flex-col border border-\[var\(--shell-border\)\] bg-white\/90 p-6">/,
  'Course resources should stretch the preview panel to match the fixed-height list column',
);

assert.match(
  page,
  /mt-6 min-h-0 flex-1 overflow-y-auto pr-2/,
  'Course resources should keep the preview body inside its own scrollable viewport',
);

console.log('courseResources.scroll-layout tests passed');
