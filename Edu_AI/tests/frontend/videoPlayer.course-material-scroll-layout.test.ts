import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');

assert.match(
  page,
  /<div className="mt-6 grid gap-6 xl:h-\[min\(72vh,760px\)\] xl:min-h-0 xl:grid-cols-\[340px_minmax\(0,1fr\)\]">/,
  'VideoPlayer should constrain the course materials two-column area to a fixed desktop height',
);

assert.match(
  page,
  /<div className="min-h-0 overflow-y-auto pr-2">/,
  'VideoPlayer should render the course materials list inside an independently scrollable column',
);

assert.match(
  page,
  /<div className="space-y-3">/,
  'VideoPlayer should preserve stacked spacing inside the scrollable materials list',
);

assert.match(
  page,
  /<div className="flex min-h-0 min-w-0 flex-col rounded-\[24px\] border border-\[var\(--shell-border\)\] bg-white\/88 p-5">/,
  'VideoPlayer should stretch the material preview card to the fixed course materials height',
);

assert.match(
  page,
  /<div className="mt-5 min-h-0 flex-1 overflow-y-auto pr-2">/,
  'VideoPlayer should keep the material preview body inside its own scrollable viewport',
);

console.log('videoPlayer.course-material-scroll-layout tests passed');
