import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');

assert.match(
  page,
  /const pageMainScrollRef = useRef<HTMLDivElement \| null>\(null\);/,
  'VideoPlayer should keep a ref to the main scroll container so route entry can control its scroll position',
);

assert.match(
  page,
  /const initialMainScrollResetRef = useRef\(true\);/,
  'VideoPlayer should track the initial route-entry scroll reset window',
);

assert.match(
  page,
  /const routeEntryScrollGuardRef = useRef\(\{ active: true, userInteracted: false \}\);/,
  'VideoPlayer should guard against browser-driven internal scrolling during route entry',
);

assert.match(
  page,
  /function resetPageMainScrollToTop\(\) \{[\s\S]*pageMainScrollRef\.current\.scrollTop = 0;[\s\S]*pageMainScrollRef\.current\.scrollLeft = 0;[\s\S]*\}/s,
  'VideoPlayer should centralize resetting the main route scroller to the top',
);

assert.match(
  page,
  /useLayoutEffect\(\(\) => \{[\s\S]*initialMainScrollResetRef\.current = true;[\s\S]*routeEntryScrollGuardRef\.current = \{ active: true, userInteracted: false \};[\s\S]*resetPageMainScrollToTop\(\);[\s\S]*\}, \[course\.id\]\);/s,
  'VideoPlayer should reset its main scroller synchronously when entering a course learning route',
);

assert.match(
  page,
  /pageMain\.addEventListener\("scroll", guardRouteEntryScroll[\s\S]*window\.addEventListener\("wheel", markUserInteracted[\s\S]*window\.addEventListener\("pointerdown", markUserInteracted/s,
  'VideoPlayer should intercept non-user route-entry scrolls while releasing the guard on user interaction',
);

assert.match(
  page,
  /if \(!materialsLoading && !graphLoading && !offlinePptsLoading\) \{[\s\S]*initialMainScrollResetRef\.current = false;[\s\S]*scheduleRouteEntryScrollGuardRelease\(1400\);[\s\S]*\}/s,
  'VideoPlayer should keep the main scroller pinned to the top briefly after initial async content has settled',
);

assert.match(
  page,
  /<main[\s\S]*ref=\{pageMainScrollRef\}[\s\S]*data-route-scroll-root[\s\S]*\[overflow-anchor:none\]/,
  'VideoPlayer should mark the internal main viewport as the route scroll root and opt out of browser scroll anchoring',
);

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
