import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../../src/stitch/App.tsx', import.meta.url), 'utf8');

assert.match(app, /import\s+\{\s*CourseResourcesPage\s*\}\s+from\s+"\.\/pages\/CourseResources"/, 'App should import the course resources page');
assert.match(app, /\[routes\.resources,\s*"Course Resources",\s*CourseResourcesPage\]/, 'App should register a resources route');
assert.doesNotMatch(app, /route === routes\.resources[\s\S]*return routes\.video/, 'App should no longer force resources to redirect to the video page');

console.log('app.course-resources-route tests passed');
