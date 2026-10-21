import test from 'node:test';
import assert from 'node:assert/strict';
import { positionAt, WatchedIntervals } from './timeline';
import type { HyperframesContent } from './types';
import { acceptReadingMessage } from '../liveLearning/readingContext';
import { citationUrl } from '../liveLearning/citationNavigation';
const content: HyperframesContent = { format: 'hyperframes/v1', project: { id: 'p', digest: 'hash', entry: 'index.html' }, timeline: { duration: 12, segments: [ { id: 'a', title: 'A', start: 0, end: 4, narration: '', visual_description: '' }, { id: 'b', title: 'B', start: 6, end: 12, narration: '', visual_description: '' } ] } };
test('native positions use seconds, preserve gaps, and resolve the exact final endpoint', () => {
 assert.equal(positionAt(content, 3.125).seconds, 3.125);
 assert.equal(positionAt(content, 4).segment_id, undefined);
 assert.equal(positionAt(content, 6).segment_id, 'b');
 assert.equal(positionAt(content, 12).segment_id, 'b');
 assert.equal(positionAt(content, NaN).seconds, 0);
});
test('actual watched ranges exclude forward/backward seeks, pause, suspension and rate changes', () => {
 const ranges = new WatchedIntervals();
 assert.equal(ranges.sample(1, true, 1, 0), undefined);
 assert.deepEqual(ranges.sample(1.1, true, 1, 100), [1, 1.1]);
 assert.equal(ranges.sample(10, true, 1, 200), undefined);
 assert.equal(ranges.sample(4, true, 1, 300), undefined);
 assert.equal(ranges.sample(4.1, false, 1, 400), undefined);
 assert.equal(ranges.sample(4.2, true, 1, 500), undefined);
 assert.deepEqual(ranges.sample(4.4, true, 2, 600), [4.2, 4.4]);
 assert.equal(ranges.sample(9, true, 1, 5600), undefined);
});
test('reading bridge accepts native frozen position and rejects invalid seconds', () => {
 const ref = { course_id: 'c', material_type: 'classroom', material_id: 'm', version: 3 };
 const message = { type: 'learning-reading-context', channel_id: 'ch', resource_ref: ref, sequence: 2, reached_end: false, locator: positionAt(content, 7.25), classroom: { status: 'paused', position: { seconds: 7.25, segment_id: 'b' } } };
 assert.ok(acceptReadingMessage(message, 'ch', ref, 1));
 for (const seconds of [-1, NaN, Infinity]) assert.equal(acceptReadingMessage({ ...message, locator: { kind: 'hyperframes', seconds } }, 'ch', ref, 1), false);
 assert.equal(acceptReadingMessage({ ...message, classroom: { status: 'playing', position: { seconds: -1 } } }, 'ch', ref, 1), false);
 const url = citationUrl({ resource_ref: ref, locator: message.locator });
 assert.match(url, /seconds=7.25/); assert.match(url, /version=3/); assert.match(url, /segment_id=b/); assert.doesNotMatch(url, /scene_id/);
});
