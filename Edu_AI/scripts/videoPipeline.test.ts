import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildAudioMixArguments,
  buildRenderUrl,
  parseVideoExportArguments,
  serializeConcatManifest,
} from './videoPipeline.ts';

test('buildRenderUrl creates fixture and authenticated classroom routes', () => {
  assert.equal(
    buildRenderUrl({
      baseUrl: 'http://127.0.0.1:4173/',
      fixture: true,
      sceneIndex: 1,
    }),
    'http://127.0.0.1:4173/#video-render?fixture=1&scene_index=1',
  );
  assert.equal(
    buildRenderUrl({
      baseUrl: 'http://localhost:4173',
      courseId: 'course / 中文',
      classroomId: 'lesson?42',
      sceneIndex: 0,
    }),
    'http://localhost:4173/#video-render?course_id=course+%2F+%E4%B8%AD%E6%96%87&classroom_id=lesson%3F42&scene_index=0',
  );
});

test('parseVideoExportArguments enforces one source and an explicit output directory', () => {
  assert.deepEqual(
    parseVideoExportArguments([
      '--base-url',
      'http://127.0.0.1:4173',
      '--output-dir',
      'artifacts/video',
      '--fixture',
      '--ffmpeg',
      'D:/tools/ffmpeg.exe',
      '--overwrite',
    ]),
    {
      baseUrl: 'http://127.0.0.1:4173',
      outputDir: 'artifacts/video',
      fixture: true,
      ffmpegPath: 'D:/tools/ffmpeg.exe',
      overwrite: true,
      timeoutMs: 120000,
    },
  );

  assert.throws(
    () => parseVideoExportArguments(['--base-url', 'http://localhost:4173', '--fixture']),
    /--output-dir is required/,
  );
  assert.throws(
    () =>
      parseVideoExportArguments([
        '--output-dir',
        'out',
        '--course-id',
        'course',
        '--classroom-id',
        'classroom',
      ]),
    /--auth-json is required for a classroom export/,
  );

  assert.equal(
    parseVideoExportArguments([
      '--base-url=http://127.0.0.1:4173',
      '--output-dir=artifacts/npm-video',
      '--fixture',
    ]).outputDir,
    'artifacts/npm-video',
  );
});

test('serializeConcatManifest quotes apostrophes and normalizes Windows separators', () => {
  assert.equal(
    serializeConcatManifest([
      String.raw`C:\exports\scene-0.mp4`,
      String.raw`C:\teacher's deck\scene-1.mp4`,
    ]),
    [
      "file 'C:/exports/scene-0.mp4'",
      "file 'C:/teacher'\\''s deck/scene-1.mp4'",
      '',
    ].join('\n'),
  );
});

test('buildAudioMixArguments delays and mixes narration at global timeline offsets', () => {
  assert.deepEqual(
    buildAudioMixArguments(
      [
        { path: 'speech-0.wav', startMs: 0 },
        { path: 'speech-1.wav', startMs: 1250 },
      ],
      0.8,
    ),
    [
      '-i',
      'speech-0.wav',
      '-i',
      'speech-1.wav',
      '-filter_complex',
      '[1:a]adelay=0|0,volume=0.8[n0];[2:a]adelay=1250|1250,volume=0.8[n1];[n0][n1]amix=inputs=2:duration=longest:dropout_transition=0[aout]',
      '-map',
      '0:v:0',
      '-map',
      '[aout]',
      '-c:v',
      'copy',
      '-c:a',
      'aac',
    ],
  );
  assert.deepEqual(buildAudioMixArguments([], 1), []);
});
