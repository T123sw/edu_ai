import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
test('all classroom entries share native playback and archive old records without the executable renderer', async () => {
 const source = await readFile(new URL('./ClassroomPlaybackSurface.tsx', import.meta.url), 'utf8');
 assert.match(source, /HyperframesClassroom/); assert.match(source, /ArchivedClassroom/);
 assert.doesNotMatch(source, /openmaic|PptxExport|ClassroomSceneRenderer/);
 for (const path of ['../../pages/ClassroomPlayer.tsx', './CourseResourceViewer.tsx']) assert.match(await readFile(new URL(path, import.meta.url), 'utf8'), /<ClassroomPlaybackSurface/);
});
